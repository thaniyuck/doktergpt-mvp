# -*- coding: utf-8 -*-
"""
DokterGPT API Server
--------------------
Wraps the existing RAG pipeline (src/core/ask.py logic) into a FastAPI
endpoint so the Next.js frontend can talk to it.

The frontend (app/page.tsx) already calls:
    POST http://127.0.0.1:8000/ask   with body { "query": "..." }
and expects:
    { "answer": str, "sources": list, "latency": float }

Run from the project root (dokterGPT_Pipeline/):
    uvicorn src.api:app --host 127.0.0.1 --port 8000
"""

import time

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from langchain_ollama import ChatOllama

from src.core.retrieve import retrieve
from src.config import LLM_MODEL

# --- ETL pipeline imports for the agentic PubMed fallback ---
from src.etl.fetcher import fetch_top_indonesian_clinical_research
from src.etl.extractor import extract_metadata
from src.etl.database import push_to_databases

# ==========================================
# LLM INITIALIZATION (same as ask.py)
# ==========================================
llm = ChatOllama(model=LLM_MODEL)
judge_llm = ChatOllama(model=LLM_MODEL, temperature=0.0)

# ==========================================
# FASTAPI APP + CORS
# ==========================================
app = FastAPI(title="DokterGPT API")

# Allow the Next.js dev server to call this API from the browser
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:3000",
        "http://127.0.0.1:3000",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


class AskRequest(BaseModel):
    query: str


# ==========================================
# HELPERS (ported from src/core/ask.py)
# ==========================================
def generate_pubmed_query(user_query: str) -> str:
    """Converts a conversational user question into a PubMed Boolean search string."""
    prompt = f"""You are an expert medical search query generator for PubMed.
    Extract the core concepts from the user query and convert them into a clean Boolean search string.
    Always include common generic drug synonyms if applicable (e.g., paracetamol OR acetaminophen).

    CRITICAL: Output ONLY the raw Boolean query. No markdown formatting, no quotes, no conversational text.
    Example: "Is IV paracetamol better than oral for pediatric dengue shock?" -> "(paracetamol OR acetaminophen) AND (intravenous OR oral) AND dengue shock"

    User Query: {user_query}
    Query:"""

    response = judge_llm.invoke(prompt).content.strip()

    # Fail-safe for chatty LLMs
    clean_query = response.split("\n")[-1].strip()
    if ":" in clean_query:
        clean_query = clean_query.split(":")[-1].strip()
    clean_query = clean_query.replace('"', "").replace("'", "")
    return clean_query


def evaluate_context(query: str, results: list) -> bool:
    """
    RELEVANCE gate (not a sufficiency gate).

    We only check whether the retrieved context is ON-TOPIC for the question.
    Whether it FULLY answers the question is decided later by the answer
    generator, which is instructed to say so honestly if evidence is lacking.
    This prevents needless PubMed fallbacks when relevant local evidence exists.

    IMPORTANT: "The evidence shows X is NOT recommended" is still a valid,
    relevant answer -- relevance does not require the context to confirm the
    premise of the question.
    """
    if not results:
        return False

    temp_context = "\n\n".join([r["text"][:800] for r in results])
    prompt = f"""[INST] You are an AI relevance judge for a medical search system.
    Decide if the medical context below is RELEVANT to the user's question -- i.e.
    it discusses the same drugs, conditions, or topic, even if it only partially
    addresses the question or shows the answer is "no / not recommended".

    Reply "YES" if the context is on-topic and could help answer the question.
    Reply "NO" only if the context is about a completely different topic.
    Reply with ONLY the word YES or NO. No explanations.

    Question: {query}
    Context: {temp_context}
    [/INST]"""

    response = judge_llm.invoke(prompt).content.strip().upper()
    return "YES" in response


# ==========================================
# INTENT ROUTER (fast path for non-clinical messages)
# ==========================================
import re

# Instant shortcut: obvious greetings/small talk never touch the LLM at all
GREETING_PATTERN = re.compile(
    r"^(hi|hii+|hello|hey|halo|hai|yo|good (morning|afternoon|evening|night)|"
    r"how are you( doing)?|what'?s up|thanks?( you)?|thank you|terima kasih|"
    r"ok(ay)?|test(ing)?|ping)[\s!?.]*$",
    re.IGNORECASE,
)

def is_clinical_query(query: str) -> bool:
    """One cheap LLM call to decide whether to run the full RAG pipeline."""
    prompt = f"""[INST] You are a strict message classifier for a clinical evidence assistant.
    Reply ONLY with the word "CLINICAL" if the message is a medical, health, drug, disease, treatment, or clinical research question.
    Reply ONLY with the word "CHAT" if the message is a greeting, small talk, a test message, or unrelated to medicine.
    No explanations.

    Message: {query}
    [/INST]"""
    response = judge_llm.invoke(prompt).content.strip().upper()
    return "CLINICAL" in response


def small_talk_reply(query: str) -> str:
    """Short, friendly reply for non-clinical messages. No retrieval, no fallback."""
    prompt = f"""You are DokterGPT, a friendly evidence-grounded clinical AI assistant for Indonesian healthcare.
    The user sent a casual, non-clinical message. Reply warmly in 1-2 short sentences,
    and invite them to ask a clinical or medical research question. Do not invent medical facts.

    User message: {query}
    Reply:"""
    return llm.invoke(prompt).content.strip()


def build_context(results: list) -> str:
    context = ""
    for i, r in enumerate(results):
        content = r["text"][:1200]
        context += f"""
        --- EVIDENCE {i + 1} ---
        TITLE: {r['title']}
        TRUST TIER: Tier {r['trust_tier']} (SCImago)
        STUDY DESIGN: {r['study_design']}
        PICO INTERVENTION: {r['intervention']}
        PICO OUTCOME: {r['outcome']}
        RAW TEXT:
        {content}
        """
    return context


def format_sources(results: list, min_display_score: float = 0.40) -> list:
    """
    Dedupe by DOI and shape the payload for the EvidencePanel component.

    Only show papers that clear a display relevance bar AND aren't far weaker
    than the best match -- this stops low-relevance 'padding' papers (e.g. an
    unrelated Tier-5 article scraping the retrieval floor) from appearing as
    citations next to a genuinely relevant result.
    """
    if not results:
        return []

    top_score = max(r["score"] for r in results)
    # Drop anything well below the best hit (more than 0.15 similarity behind).
    gap_floor = top_score - 0.15

    sources = []
    seen_dois = set()

    for r in results:
        doi = r["doi"]
        if doi in seen_dois:
            continue

        # Skip weak / off-topic padding for the citation panel.
        if r["score"] < min_display_score or r["score"] < gap_floor:
            continue

        seen_dois.add(doi)

        sources.append({
            "title": r["title"],
            "doi": r["doi"],
            "score": r["score"],
            "trust_tier": r["trust_tier"],
            "study_design": r["study_design"],
            "publication_date": str(r["publication_date"]),  # date -> string for JSON
            "patient_demographic": r["patient_demographic"],
            "intervention": r["intervention"],
            "outcome": r["outcome"],
        })

    return sources


def translate_to_english(query: str) -> str:
    """
    Translate the query to English for retrieval, because the paper corpus is in
    English. An Indonesian query ('kunyit', 'akupunktur') won't keyword-match
    English chunks ('turmeric', 'acupuncture') and embeds less precisely, which
    causes shallow answers and off-topic padding. Returns the query unchanged if
    it's already English.
    """
    prompt = f"""Translate the following medical question to English for a literature search.
    If it is already in English, return it EXACTLY as-is.
    Output ONLY the translated question. No quotes, no preamble, no explanation.

    Question: {query}"""
    try:
        translated = judge_llm.invoke(prompt).content.strip()
        # Guard against chatty output: take the last non-empty line.
        translated = [ln for ln in translated.splitlines() if ln.strip()][-1].strip()
        return translated or query
    except Exception:
        return query  # fail open: never block retrieval on a translation error


# ==========================================
# ENDPOINTS
# ==========================================
@app.get("/")
def health():
    return {"status": "ok", "service": "DokterGPT API"}


@app.post("/ask")
def ask(req: AskRequest):
    query = req.query.strip()
    start_time = time.time()

    if not query:
        return {"answer": "Please enter a question.", "sources": [], "latency": 0}

    # 0. INTENT ROUTING: skip the entire RAG pipeline for non-clinical messages
    if GREETING_PATTERN.match(query):
        latency = round(time.time() - start_time, 2)
        return {
            "answer": "Hello! I'm DokterGPT, your evidence-grounded clinical assistant. Ask me a medical or clinical research question and I'll back the answer with cited literature.",
            "sources": [],
            "latency": latency,
        }

    if not is_clinical_query(query):
        answer = small_talk_reply(query)
        latency = round(time.time() - start_time, 2)
        return {"answer": answer, "sources": [], "latency": latency}

    # 0b. TRANSLATE to English for retrieval (corpus is English).
    # We keep the ORIGINAL query for the final answer so the model can still
    # respond in the user's language.
    search_query = translate_to_english(query)

    # 1. RETRIEVE CLINICAL CONTEXT FROM POSTGRES (using the English search query)
    results = retrieve(search_query, top_k=5)

    # --- PUBMED FALLBACK ---
    # Rule: if the DB returns ANY relevant papers, use them and DO NOT call PubMed,
    # no matter how few. PubMed is only consulted as a last resort -- when local
    # retrieval comes back empty, or when the relevance judge says everything
    # retrieved is off-topic for this question.
    local_is_relevant = len(results) > 0 and evaluate_context(query, results)

    if not local_is_relevant:
        pubmed_query = generate_pubmed_query(query)
        downloaded_papers = fetch_top_indonesian_clinical_research(pubmed_query, max_results=3)

        if downloaded_papers:
            extract_metadata()
            push_to_databases()
            time.sleep(2)  # let pgvector index the new chunks
            results = retrieve(query, top_k=5)

    if len(results) == 0:
        latency = round(time.time() - start_time, 2)
        return {
            "answer": "No reliable medical context found in the database for this question.",
            "sources": [],
            "latency": latency,
        }

    # 2. BUILD THE CONTEXT PAYLOAD
    context = build_context(results)

    # 3. CONSTRUCT THE MEDICAL PROMPT (identical to ask.py)
    prompt = f"""
    You are DokterGPT, an evidence-grounded clinical AI assistant operating in Indonesia.

    CRITICAL INSTRUCTIONS:
    - Use ONLY the provided medical context to answer the question.
    - Do NOT fabricate information.
    - You have exactly TWO mutually exclusive response modes. Choose ONE:
        (A) If the context DOES address the question: give the answer based on the
            evidence. Do NOT include any disclaimer about insufficient data.
        (B) If the context does NOT address the question at all: reply with ONLY this
            single sentence and nothing else: "The retrieved clinical data does not
            contain sufficient information to answer this."
      NEVER combine modes A and B. If you provided an answer, do not append the
      insufficient-data sentence. They cannot both appear in one response.
    - Do not start the reply with filler like "Based on the provided evidence, I can
      answer as follows". State the finding directly.
    - Pay close attention to the "TRUST TIER". Tier 1 is the most reliable (Q1 Journals). If Tier 1 evidence conflicts with Tier 4/5 evidence, always trust Tier 1.
    - Leverage the PICO (Intervention and Outcome) data provided to give concise, structured clinical insights.
    - Answer concisely in 3-5 sentences.

    CONTEXT:
    {context}

    QUESTION:
    {query}
    """

    # 4. GENERATE RESPONSE
    response = llm.invoke(prompt)

    latency = round(time.time() - start_time, 2)

    # 5. RETURN THE PAYLOAD THE FRONTEND EXPECTS
    return {
        "answer": response.content,
        "sources": format_sources(results),
        "latency": latency,
    }
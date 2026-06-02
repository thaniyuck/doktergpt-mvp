from fastapi import FastAPI
from pydantic import BaseModel
from fastapi.middleware.cors import CORSMiddleware

from langchain_ollama import ChatOllama

from src.core.retrieve import retrieve
from src.config import *

import time

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


class QueryRequest(BaseModel):
    query: str


@app.get("/")
def root():
    return {"status": "DokterGPT API Running"}


@app.post("/ask")
def ask(req: QueryRequest):
    try:
        start_time = time.time()

        results = retrieve(req.query, top_k=3)

        retrieval_latency = round(time.time() - start_time, 2)

        if len(results) == 0:
            return {
                "answer": "No reliable medical evidence found.",
                "latency": retrieval_latency,
                "sources": []
            }

        context = ""

        for i, r in enumerate(results):

            content = r["text"][:1200]

            context += f"""
            --- EVIDENCE {i+1} ---
            TITLE: {r['title']}
            TRUST TIER: Tier {r['trust_tier']}
            STUDY DESIGN: {r['study_design']}
            INTERVENTION: {r['intervention']}
            OUTCOME: {r['outcome']}

            RAW TEXT:
            {content}
            """

        prompt = f"""
        You are DokterGPT, an evidence-grounded clinical AI assistant.

        CRITICAL INSTRUCTIONS:
        - Use ONLY the provided evidence.
        - Do not fabricate information.
        - Prioritize higher trust tiers.
        - Provide concise evidence-based answers.

        CONTEXT:
        {context}

        QUESTION:
        {req.query}
        """

        llm = ChatOllama(
            model=LLM_MODEL
        )

        response = llm.invoke(prompt)

        seen_dois = set()

        sources = []

        for r in results:

            if r["doi"] in seen_dois:
                continue

            seen_dois.add(r["doi"])

            sources.append({
                "title": r["title"],
                "doi": r["doi"],
                "score": r["score"],
                "trust_tier": r["trust_tier"],
                "study_design": r["study_design"],
                "publication_date": str(r["publication_date"])
            })

        return {
            "answer": response.content,
            "latency": retrieval_latency,
            "sources": sources
        }
    except Exception as e:
        return {
            "answer": f"Backend Error: {str(e)}",
            "latency": 0,
            "sources": []
        }
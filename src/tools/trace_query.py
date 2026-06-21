# -*- coding: utf-8 -*-
"""
End-to-end pipeline trace for a single query.
Run from project root:  py -m src.tools.trace_query

Shows, in order:
  1. What keywords retrieve() extracts.
  2. What papers retrieve() ACTUALLY returns (the real hybrid function).
  3. What the judge LLM decides about that context (YES = answer locally,
     NO = trigger PubMed).

This tells you EXACTLY which stage is failing.
"""

from src.core.retrieve import retrieve, _extract_keywords
from src.config import LLM_MODEL
from langchain_ollama import ChatOllama

QUERY = "Is Ivermectin recommended as a standard antiviral treatment for severe COVID-19 patients in Indonesian hospitals?"

print("=" * 70)
print("QUERY:", QUERY)
print("=" * 70)

# --- 1. Keywords ---
print("\n[1] Keywords extracted:", _extract_keywords(QUERY))

# --- 2. What does retrieve() actually return? ---
print("\n[2] retrieve() returned these papers:")
results = retrieve(QUERY, top_k=5, debug=True)
if not results:
    print("    ❌ NOTHING returned. (min_score filter or empty merge.)")
else:
    for i, r in enumerate(results, 1):
        print(f"    [{i}] score={r['score']}  {r['title'][:65]}")
        print(f"         DOI: {r['doi']}")

# --- 3. What does the judge decide? ---
judge_llm = ChatOllama(model=LLM_MODEL, temperature=0.0)

def evaluate_context(query, results):
    if not results:
        return False, "(no results, auto-NO)"
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
    raw = judge_llm.invoke(prompt).content.strip()
    return ("YES" in raw.upper()), raw

print("\n[3] Judge verdict on the retrieved context:")
verdict, raw = evaluate_context(QUERY, results)
print(f"    Raw LLM reply: {raw!r}")
print(f"    -> {'YES (answers locally, NO PubMed)' if verdict else 'NO (TRIGGERS PUBMED)'}")

print("\n" + "=" * 70)
print("INTERPRETATION")
print("=" * 70)
if not results:
    print("Retrieval returned nothing -> problem is in retrieve.py / min_score.")
elif not any("ivermectin" in (r["title"] or "").lower() or
             "ivermectin" in (r["text"] or "").lower() for r in results):
    print("Retrieval ran but did NOT surface Ivermectin chunks -> keyword channel")
    print("or merge is not working as expected. Share this output.")
elif not verdict:
    print("Retrieval DID surface Ivermectin papers, but the JUDGE said NO and")
    print("triggered PubMed. The bug is the judge being too strict, NOT retrieval.")
else:
    print("Everything works here. If the live app still hits PubMed, the running")
    print("server is using OLD code -> it did not reload. Fully restart uvicorn.")
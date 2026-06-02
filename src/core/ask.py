from langchain_ollama import ChatOllama
from src.core.retrieve import retrieve
from src.config import *

# Initialize the LLM (Llama 3 via Ollama)
llm = ChatOllama(
    model=LLM_MODEL
)

print("\n========================================")
print(" 🏥 DOKTER-GPT MVP (LIVE DATABASE) 🏥")
print("========================================")
print(f"Embedding Engine: {EMBED_MODEL}")
print(f"Reasoning Engine: {LLM_MODEL}")
print("Type 'exit' to quit.\n")

while True:
    query = input("Question: ")

    if query.lower() == "exit":
        print("Shutting down DokterGPT. Goodbye!")
        break

    # 1. RETRIEVE CLINICAL CONTEXT FROM POSTGRES
    print("\n[Retrieving evidence from Supabase...]")
    results = retrieve(query, top_k=3)

    if len(results) == 0:
        print("\n⚠️ No reliable medical context found in the database.\n")
        continue

    # 2. BUILD THE CONTEXT PAYLOAD
    context = ""
    for i, r in enumerate(results):
        content = r['text'][:1200]
        context += f"""
        --- EVIDENCE {i+1} ---
        TITLE: {r['title']}
        TRUST TIER: Tier {r['trust_tier']} (SCImago)
        STUDY DESIGN: {r['study_design']}
        PICO INTERVENTION: {r['intervention']}
        PICO OUTCOME: {r['outcome']}
        RAW TEXT:
        {content}
        """

    # 3. CONSTRUCT THE MEDICAL PROMPT
    prompt = f"""
    You are DokterGPT, an evidence-grounded clinical AI assistant operating in Indonesia.

    CRITICAL INSTRUCTIONS:
    - Use ONLY the provided medical context to answer the question.
    - Do NOT fabricate information. If the evidence does not contain the answer, explicitly state: "The retrieved clinical data does not contain sufficient information to answer this."
    - Pay close attention to the "TRUST TIER". Tier 1 is the most reliable (Q1 Journals). If Tier 1 evidence conflicts with Tier 4/5 evidence, always trust Tier 1.
    - Leverage the PICO (Intervention and Outcome) data provided to give concise, structured clinical insights.
    - Answer concisely in 3-5 sentences.

    CONTEXT:
    {context}

    QUESTION:
    {query}
    """

    # 4. GENERATE RESPONSE
    print("[Generating clinical response...]\n")
    response = llm.invoke(prompt)

    print("\n🩺 ANSWER:\n")
    print(response.content)
    print("\n" + "="*40 + "\n")

    # 5. PRINT TRACEABLE CITATIONS
    print("📚 VERIFIED SOURCES:\n")
    seen_dois = set()
    citation_number = 1

    for r in results:
        doi = r['doi']

        # Skip duplicate papers if multiple chunks from the same paper were retrieved
        if doi in seen_dois:
            continue
            
        seen_dois.add(doi)

        print(f"[{citation_number}] {r['title']}")
        print(f"    DOI                : {r['doi']}")
        print(f"    SCImago Trust Tier : Tier {r['trust_tier']}")
        print(f"    Publication Date   : {r['publication_date']}")
        print(f"    Study Design       : {r['study_design']}")
        print(f"    Patient Group      : {r['patient_demographic']}")
        print(f"    Intervention       : {r['intervention']}")
        print(f"    Outcome            : {r['outcome']}")
        print(f"    Vector Similarity  : {r['score']}")
        print()

        citation_number += 1
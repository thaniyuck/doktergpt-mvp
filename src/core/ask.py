import time
from langchain_ollama import ChatOllama
from src.core.retrieve import retrieve
from src.config import *

# --- IMPORT ETL PIPELINE SCRIPTS FOR THE FALLBACK ---
from src.etl.fetcher import fetch_top_indonesian_clinical_research
from src.etl.extractor import extract_metadata
from src.etl.database import push_to_databases

# Initialize the LLM (Llama 3 via Ollama)
llm = ChatOllama(
    model=LLM_MODEL
)
# Strict low-temperature judge for evaluation and keyword extraction
judge_llm = ChatOllama(model=LLM_MODEL, temperature=0.0) 

def generate_pubmed_query(user_query):
    """Converts a conversational user question into a professional PubMed Boolean search string."""
    prompt = f"""You are an expert medical search query generator for PubMed.
    Extract the core concepts from the user query and convert them into a clean Boolean search string.
    Always include common generic drug synonyms if applicable (e.g., paracetamol OR acetaminophen).
    
    CRITICAL: Output ONLY the raw Boolean query. No markdown formatting, no quotes, no conversational text.
    Example: "Is IV paracetamol better than oral for pediatric dengue shock?" -> "(paracetamol OR acetaminophen) AND (intravenous OR oral) AND dengue shock"
    
    User Query: {user_query}
    Query:"""
    
    response = judge_llm.invoke(prompt).content.strip()
    
    # --- FAIL-SAFE FOR CHATTY LLMs ---
    clean_query = response.split('\n')[-1].strip()
    if ":" in clean_query:
        clean_query = clean_query.split(":")[-1].strip()
    clean_query = clean_query.replace('"', '').replace("'", "")
    return clean_query

def evaluate_context(query, results):
    """Asks the LLM to judge if the retrieved context actually answers the question."""
    if not results:
        return False
        
    temp_context = "\n\n".join([r['text'][:800] for r in results])
    prompt = f"""[INST] You are a strict AI judge. 
    Does the medical context below contain sufficient information to answer the user's question?
    Reply ONLY with the word "YES" or "NO". No explanations.
    
    Question: {query}
    Context: {temp_context}
    [/INST]"""
    
    response = judge_llm.invoke(prompt).content.strip().upper()
    return "YES" in response


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

    # --- AGENTIC PUBMED FALLBACK LOGIC ---
    has_answer = evaluate_context(query, results)

    if not has_answer:
        print("\n⚠️ Database lacks sufficient context. Triggering PubMed Researcher...")
        pubmed_query = generate_pubmed_query(query)
        downloaded_papers = fetch_top_indonesian_clinical_research(pubmed_query, max_results=3)
        
        if downloaded_papers:
            print(f"\n📥 Found {len(downloaded_papers)} new papers. Processing...")
            print("🧠 Extracting structured metadata via Local LLM...")
            extract_metadata()
            
            print("🗄️ Pushing new vectors to Postgres and syncing Google Sheets...")
            push_to_databases()
            
            # Wait a brief moment for Supabase pgvector to index the new chunks
            time.sleep(2) 
            
            print("\n[🔄 Re-retrieving updated evidence from Supabase...]")
            results = retrieve(query, top_k=3)
        else:
            print("❌ PubMed could not find relevant papers globally for this query.")
    # ------------------------------------------

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
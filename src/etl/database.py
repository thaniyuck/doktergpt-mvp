import os
import json
import uuid
import csv
import psycopg2
import gspread
import time
import warnings
import torch
from sentence_transformers import SentenceTransformer
from src.config import CREDENTIALS_PATH

# --- LangChain Semantic Chunker Imports ---
from langchain_experimental.text_splitter import SemanticChunker
from langchain_huggingface import HuggingFaceEmbeddings

warnings.filterwarnings("ignore")

# =====================================================================
# 1. CONFIGURATION & FILE PATHS
# =====================================================================
OVERWRITE_MODE = False  # 🛑 KEEP FALSE so we never wipe the 875 historical papers!

DRIVE_BASE = "G:/My Drive/dokterGPT_Data" 
JSON_DIR = os.path.join(DRIVE_BASE, "extracted_json")
MD_DIR = os.path.join(DRIVE_BASE, "parsed_md")
SCIMAGO_PATH = os.path.join(DRIVE_BASE, "scimago.csv")

GSHEET_NAME = 'dokterGPT_Database'
DB_URL = "postgresql://postgres.cviumnakesybhqiuwdij:doktergpt123@aws-1-ap-southeast-1.pooler.supabase.com:6543/postgres"

def gen_id(prefix): return f"{prefix}_{uuid.uuid4().hex[:8]}"

print("🧠 Loading BAAI/bge-m3 (For Supabase Vectors)...")
embedder = SentenceTransformer('BAAI/bge-m3')

# =====================================================================
# 2. SCIMAGO TRUST TIER ENGINE
# =====================================================================
print("📊 Loading SCImago Database for Auto-Scoring...")
scimago_ranks = {}

if os.path.exists(SCIMAGO_PATH):
    with open(SCIMAGO_PATH, mode='r', encoding='utf-8') as f:
        reader = csv.DictReader(f, delimiter=';') 
        for row in reader:
            title = row.get('Title', '').strip().lower()
            q_rank = row.get('SJR Best Quartile', '').strip()
            if title and q_rank:
                scimago_ranks[title] = q_rank
else:
    print(f"⚠️ SCImago file not found at {SCIMAGO_PATH}. Defaulting to Tier 5.")

def get_scimago_tier(journal_name):
    clean_name = journal_name.strip().lower()
    rank = scimago_ranks.get(clean_name, "Unranked")
    if rank == 'Q1': return "1"
    elif rank == 'Q2': return "2"
    elif rank == 'Q3': return "3"
    elif rank == 'Q4': return "4"
    else: return "5"  

# =====================================================================
# 3. CHUNKING ENGINE (MiniLM Semantic Chunker for FUTURE papers)
# =====================================================================
# Auto-detects if you have a GPU, otherwise uses CPU (which is perfectly fine for 1-3 new papers)
device_target = "cuda" if torch.cuda.is_available() else "cpu"
print(f"🧠 Loading all-MiniLM-L6-v2 (For Semantic Text Slicing) on {device_target.upper()}...")

semantic_embeddings = HuggingFaceEmbeddings(
    model_name="all-MiniLM-L6-v2",
    model_kwargs={"device": device_target}
)

semantic_chunker = SemanticChunker(
    semantic_embeddings, 
    breakpoint_threshold_type="percentile"
)

def semantic_chunk_text(text):
    """Uses AI to detect topic changes and split paragraphs perfectly."""
    try:
        return semantic_chunker.split_text(text)
    except Exception as e:
        print(f"⚠️ Chunking error: {e}")
        return [text]

# =====================================================================
# 4. POSTGRES & PGVECTOR SETUP
# =====================================================================
def setup_postgres():
    print("🗄️ Connecting to PostgreSQL & Enabling pgvector...")
    conn = psycopg2.connect(DB_URL)
    cursor = conn.cursor()
    cursor.execute('CREATE EXTENSION IF NOT EXISTS vector;')

    cursor.execute('''CREATE TABLE IF NOT EXISTS sources (source_id TEXT PRIMARY KEY, name TEXT, source_type TEXT, trust_tier TEXT)''')
    cursor.execute('''CREATE TABLE IF NOT EXISTS papers (paper_id TEXT PRIMARY KEY, source_id TEXT, title TEXT, abstract TEXT, doi TEXT, publication_date TEXT, url TEXT, context_type TEXT, study_design TEXT, sample_size_n TEXT, patient_demographic TEXT, clinical_specialty TEXT, ethical_clearance_status TEXT, validation_type TEXT)''')
    cursor.execute('''CREATE TABLE IF NOT EXISTS clinical_pico (pico_id TEXT PRIMARY KEY, paper_id TEXT, population TEXT, intervention TEXT, comparison TEXT, outcome TEXT)''')
    cursor.execute('''CREATE TABLE IF NOT EXISTS authors (author_id TEXT PRIMARY KEY, full_name TEXT, primary_affiliation TEXT)''')
    cursor.execute('''CREATE TABLE IF NOT EXISTS drugs_and_substances (drug_id TEXT PRIMARY KEY, generic_name TEXT, atc_code TEXT)''')
    cursor.execute('''CREATE TABLE IF NOT EXISTS icd_codes (icd_code TEXT PRIMARY KEY, disease_description TEXT, category TEXT)''')
    cursor.execute('''CREATE TABLE IF NOT EXISTS keywords (keyword_id TEXT PRIMARY KEY, term TEXT, is_mesh_term TEXT)''')
    cursor.execute('''CREATE TABLE IF NOT EXISTS paper_authors (paper_id TEXT, author_id TEXT, author_order INTEGER)''')
    cursor.execute('''CREATE TABLE IF NOT EXISTS paper_drugs (paper_id TEXT, drug_id TEXT)''')
    cursor.execute('''CREATE TABLE IF NOT EXISTS paper_icd (paper_id TEXT, icd_code TEXT)''')
    cursor.execute('''CREATE TABLE IF NOT EXISTS paper_keywords (paper_id TEXT, keyword_id TEXT)''')

    # 🌟 VECTOR TABLE 🌟
    cursor.execute('''CREATE TABLE IF NOT EXISTS chunks (
        chunk_id TEXT PRIMARY KEY, paper_id TEXT, chunk_index INTEGER, chunk_text TEXT, token_count INTEGER, embedding vector(1024)
    )''')
    conn.commit()
    return conn, cursor

# =====================================================================
# 5. GOOGLE SHEETS SETUP
# =====================================================================
def get_gsheets_worksheets():
    print("🔐 Authenticating with Google Sheets locally...")
    try:
        gc = gspread.service_account(filename=str(CREDENTIALS_PATH))
        sh = gc.open(GSHEET_NAME)
        return {
            "sources": sh.worksheet("sources"), "papers": sh.worksheet("papers"), "clinical_pico": sh.worksheet("clinical_pico"),
            "authors": sh.worksheet("authors"), "drugs_and_substances": sh.worksheet("drugs_and_substances"),
            "icd_codes": sh.worksheet("icd_codes"), "keywords": sh.worksheet("keywords"),
            "paper_authors": sh.worksheet("paper_authors"), "paper_drugs": sh.worksheet("paper_drugs"),
            "paper_icd": sh.worksheet("paper_icd"), "paper_keywords": sh.worksheet("paper_keywords"),
            "chunks": sh.worksheet("chunks")
        }, sh.url
    except Exception as e:
        print(f"❌ Google Sheets Error: {e}")
        return None, None

# =====================================================================
# 6. THE STREAMLINED ETL ROUTER
# =====================================================================
def push_to_databases():
    if not os.path.exists(JSON_DIR):
        return print(f"📂 JSON directory not found at {JSON_DIR}")
        
    json_files = [f for f in os.listdir(JSON_DIR) if f.endswith('.json')]
    if not json_files: return print("📂 No JSON files found!")

    conn, cursor = setup_postgres()
    tabs, sheet_url = get_gsheets_worksheets()
    if not tabs: return

    # --- ANTI-DUPLICATION FOR GSHEETS ---
    existing_gsheet_titles = set()
    print("📊 Checking existing records in Google Sheets...")
    try:
        titles_col = tabs["papers"].col_values(3)
        existing_gsheet_titles = {str(t).strip().lower() for t in titles_col[1:]}
    except Exception as e:
        print(f"   ⚠️ Could not fetch existing GSheet titles: {e}")

    payloads = {k: [] for k in tabs.keys()}
    success_count = 0
    print(f"🚀 Processing {len(json_files)} papers into Postgres + Vector DB + GSheets...")

    for file in json_files:
        with open(os.path.join(JSON_DIR, file), 'r', encoding='utf-8') as f:
            data = json.load(f)

            raw_title = data.get('title', '').strip()

            # Check Postgres Deduplication (Instantly skips the 875 old ones!)
            cursor.execute('SELECT paper_id FROM papers WHERE LOWER(title) = LOWER(%s)', (raw_title,))
            if cursor.fetchone():
                print(f"   ⏭️ Skipping fully synced duplicate: {raw_title[:50]}...")
                continue

            # Check GSheets Deduplication
            add_to_gsheets = raw_title.lower() not in existing_gsheet_titles
            if not add_to_gsheets: print(f"   🔄 Restoring to Postgres/Vector DB (Already in GSheets): {raw_title[:50]}...")

            # --- DYNAMIC SOURCE W/ SCIMAGO OVERRIDE ---
            source_data = data.get('source', {})
            source_name = str(source_data.get('name', 'Unknown Local PDF'))
            calculated_tier = get_scimago_tier(source_name)

            cursor.execute('SELECT source_id FROM sources WHERE name = %s', (source_name,))
            existing_source = cursor.fetchone()

            if existing_source: 
                source_id = existing_source[0]
            else:
                source_id = gen_id("SRC")
                source_row = [source_id, source_name, str(source_data.get('source_type', 'Journal')), calculated_tier]
                cursor.execute('INSERT INTO sources VALUES (%s,%s,%s,%s)', source_row)
                if add_to_gsheets: payloads["sources"].append(source_row)

            # --- PAPERS ---
            paper_id = gen_id("PPR")
            context_val = "Indonesian Context" if data.get('is_indonesian_context') else "General Context"
            paper_row = [paper_id, source_id, str(data.get('title', 'Not specified')), str(data.get('abstract', 'Not specified')), str(data.get('doi', 'Not specified')), str(data.get('publication_date', 'Unknown')), str(data.get('url', 'Not specified')), context_val, str(data.get('study_design', 'Not specified')), str(data.get('sample_size_n', 'Not specified')), str(data.get('patient_demographic', 'Unknown')), str(data.get('clinical_specialty', 'Unknown')), str(data.get('ethical_clearance_status', '')), "AI Extracted"]
            cursor.execute('INSERT INTO papers VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)', paper_row)
            if add_to_gsheets: payloads["papers"].append(paper_row)

            # --- PICO ---
            pico = data.get('pico', {})
            pico_row = [gen_id("PICO"), paper_id, pico.get('population'), pico.get('intervention'), pico.get('comparison'), pico.get('outcome')]
            cursor.execute('INSERT INTO clinical_pico VALUES (%s,%s,%s,%s,%s,%s)', pico_row)
            if add_to_gsheets: payloads["clinical_pico"].append(pico_row)

            # --- AUTHORS, DRUGS, ICD, KEYWORDS ---
            for index, author in enumerate(data.get('authors', [])):
                author_id = gen_id("AUTH")
                cursor.execute('INSERT INTO authors VALUES (%s,%s,%s) ON CONFLICT DO NOTHING', [author_id, author.get('full_name'), author.get('primary_affiliation')])
                cursor.execute('INSERT INTO paper_authors VALUES (%s,%s,%s)', [paper_id, author_id, index + 1])
                if add_to_gsheets:
                    payloads["authors"].append([author_id, author.get('full_name'), author.get('primary_affiliation')])
                    payloads["paper_authors"].append([paper_id, author_id, index + 1])

            for drug in data.get('drugs_and_substances', []):
                drug_id = gen_id("DRUG")
                cursor.execute('INSERT INTO drugs_and_substances VALUES (%s,%s,%s) ON CONFLICT DO NOTHING', [drug_id, drug.get('generic_name', 'Unknown'), drug.get('atc_code', 'Not specified')])
                cursor.execute('INSERT INTO paper_drugs VALUES (%s,%s)', [paper_id, drug_id])
                if add_to_gsheets:
                    payloads["drugs_and_substances"].append([drug_id, drug.get('generic_name', 'Unknown'), drug.get('atc_code', 'Not specified')])
                    payloads["paper_drugs"].append([paper_id, drug_id])

            for icd in data.get('icd_10_suggestions', []):
                icd_code = str(icd.get('code', 'Unknown'))
                cursor.execute('INSERT INTO icd_codes VALUES (%s,%s,%s) ON CONFLICT DO NOTHING', [icd_code, icd.get('disease_description', 'Not specified'), icd.get('category', 'Not specified')])
                cursor.execute('INSERT INTO paper_icd VALUES (%s,%s)', [paper_id, icd_code])
                if add_to_gsheets:
                    payloads["icd_codes"].append([icd_code, icd.get('disease_description', 'Not specified'), icd.get('category', 'Not specified')])
                    payloads["paper_icd"].append([paper_id, icd_code])

            for kw in data.get('keywords', []):
                kw_id = gen_id("KW")
                cursor.execute('INSERT INTO keywords VALUES (%s,%s,%s) ON CONFLICT DO NOTHING', [kw_id, kw.get('term', 'Unknown'), str(kw.get('is_mesh_term', 'FALSE'))])
                cursor.execute('INSERT INTO paper_keywords VALUES (%s,%s)', [paper_id, kw_id])
                if add_to_gsheets:
                    payloads["keywords"].append([kw_id, kw.get('term', 'Unknown'), str(kw.get('is_mesh_term', 'FALSE'))])
                    payloads["paper_keywords"].append([paper_id, kw_id])

            # =========================================================
            # 🌟 PARALLEL CHUNKING & EMBEDDING (Now uses MiniLM!) 🌟
            # =========================================================
            md_filename = file.replace('.json', '.md')
            md_filepath = os.path.join(MD_DIR, md_filename)

            if os.path.exists(md_filepath):
                with open(md_filepath, 'r', encoding='utf-8') as md_file:
                    raw_text = md_file.read()

                # Passes text through the new AI semantic chunker
                chunks = semantic_chunk_text(raw_text)
                print(f"     🧩 Generating {len(chunks)} Semantic AI vector embeddings for {md_filename}...")
                embeddings = embedder.encode(chunks)

                for i, (chunk_txt, embed_vector) in enumerate(zip(chunks, embeddings)):
                    chunk_id = gen_id("CHK")
                    token_count = len(chunk_txt.split())
                    embed_list = embed_vector.tolist()

                    cursor.execute('''
                        INSERT INTO chunks (chunk_id, paper_id, chunk_index, chunk_text, token_count, embedding)
                        VALUES (%s, %s, %s, %s, %s, %s)
                    ''', (chunk_id, paper_id, i+1, chunk_txt, token_count, embed_list))

                    if add_to_gsheets:
                        payloads["chunks"].append([chunk_id, paper_id, i+1, chunk_txt, "Full Text", token_count])

            # --- FIX: MICRO-COMMIT AFTER EVERY PAPER ---
            conn.commit()
            success_count += 1

    # Close the connection safely after all papers are done
    conn.close()

    print("\n☁️ Pushing batch updates to Google Sheets...")
    for tab_name, payload in payloads.items():
        if payload:
            tabs[tab_name].append_rows(payload)
            print(f"   ✅ Appended {len(payload)} rows to '{tab_name}'")

    if success_count > 0: print(f"\n🎉 SUCCESS! Processed {success_count} NEW papers with Semantic Chunking.")
    else: print("\n✅ All databases are up to date. No new papers to chunk.")

if __name__ == "__main__":
    push_to_databases()
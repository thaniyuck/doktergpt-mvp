# -*- coding: utf-8 -*-
"""
Retrieval Diagnostic
--------------------
Figures out WHY specific papers (e.g. your Ivermectin papers) do or don't
surface for a query, instead of guessing.

Run from the project root (F:\\dokterGPT_Pipeline):
    py -m src.tools.diagnose_retrieval

It does three things:
  1. Confirms the keyword ("ivermectin") actually exists in your chunks/titles.
  2. Shows the raw vector-similarity ranking of the top 40 chunks for a query,
     so you can see exactly what score your target papers get and where they rank.
  3. Tells you which of the three failure modes you're in.
"""

import psycopg2
from sentence_transformers import SentenceTransformer
from src.config import DB_URL, EMBED_MODEL

# -------- EDIT THESE TWO --------
QUERY = "Is Ivermectin recommended as a standard antiviral treatment for severe COVID-19 patients in Indonesian hospitals?"
KEYWORD = "ivermectin"   # the term you expect to find
# --------------------------------

print("Loading embedding model:", EMBED_MODEL)
embeddings = SentenceTransformer(EMBED_MODEL)

conn = psycopg2.connect(DB_URL)
cur = conn.cursor()

# =====================================================================
# STEP 1: Does the keyword even exist in the database? (pure text search)
# =====================================================================
print("\n" + "=" * 70)
print(f"STEP 1: Text search for '{KEYWORD}' in chunks + titles")
print("=" * 70)

cur.execute("""
    SELECT p.paper_id, p.title, COUNT(c.chunk_id) AS hits
    FROM chunks c
    JOIN papers p ON c.paper_id = p.paper_id
    WHERE c.chunk_text ILIKE %s OR p.title ILIKE %s
    GROUP BY p.paper_id, p.title
    ORDER BY hits DESC;
""", (f"%{KEYWORD}%", f"%{KEYWORD}%"))

text_hits = cur.fetchall()
if text_hits:
    print(f"Found {len(text_hits)} paper(s) literally containing '{KEYWORD}':")
    for pid, title, hits in text_hits:
        print(f"  - [{hits} chunk(s)] {title[:80]}  (paper_id={pid})")
else:
    print(f"❌ NO chunk or title contains the text '{KEYWORD}'.")
    print("   -> The papers may not be chunked/embedded, or the term is spelled differently.")

target_paper_ids = {row[0] for row in text_hits}

# =====================================================================
# STEP 2: Vector ranking — where do those papers land by similarity?
# =====================================================================
print("\n" + "=" * 70)
print("STEP 2: Vector similarity ranking (top 40 chunks for the query)")
print("=" * 70)
print("Query:", QUERY, "\n")

qvec = embeddings.encode(QUERY).tolist()

cur.execute("""
    SELECT
        p.paper_id,
        p.title,
        1 - (c.embedding <=> %s::vector) AS similarity
    FROM chunks c
    JOIN papers p ON c.paper_id = p.paper_id
    ORDER BY c.embedding <=> %s::vector
    LIMIT 40;
""", (qvec, qvec))

rows = cur.fetchall()
target_ranks = []
for rank, (pid, title, sim) in enumerate(rows, start=1):
    marker = "  <<< TARGET" if pid in target_paper_ids else ""
    if pid in target_paper_ids:
        target_ranks.append((rank, sim))
    print(f"  #{rank:>2}  sim={sim:.3f}  {title[:60]}{marker}")

conn.close()

# =====================================================================
# STEP 3: Diagnosis
# =====================================================================
print("\n" + "=" * 70)
print("DIAGNOSIS")
print("=" * 70)

if not text_hits:
    print("CAUSE: The papers aren't in the searchable chunks at all (embedding/ingest gap),")
    print("       OR the keyword is spelled differently. Re-run with a different KEYWORD,")
    print("       or check that these papers went through chunk.py + database.py push.")
elif not target_ranks:
    print("CAUSE: Papers EXIST in the DB but none of their chunks landed in the top 40")
    print("       by vector similarity. This is a semantic/embedding mismatch — the")
    print("       embedding model doesn't see your query and these chunks as similar.")
    print("       Fixes: hybrid search (vector + keyword), or check the chunks were")
    print("       embedded with the SAME model (BAAI/bge-m3) used here.")
else:
    best_rank, best_sim = min(target_ranks, key=lambda x: x[0])
    print(f"CAUSE: Target papers DO rank — best is #{best_rank} at similarity {best_sim:.3f}.")
    if best_rank > 3:
        print("       They were just CROWDED OUT of the old top_k=3. The retrieve.py")
        print("       widen-the-net + dedupe fix should now surface them.")
    if best_sim < 0.3:
        print(f"       Their score ({best_sim:.3f}) is below the old 0.3 threshold —")
        print("       the lowered min_score=0.25 helps, but a low score also hints the")
        print("       embeddings only weakly match. Consider hybrid search for robustness.")
    if best_rank <= 3 and best_sim >= 0.3:
        print("       They should have appeared already — double-check the running server")
        print("       actually reloaded the patched retrieve.py.")
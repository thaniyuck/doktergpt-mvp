import re
import math
import psycopg2
from sentence_transformers import SentenceTransformer
from src.config import *

# Initialize your local embedding model
embeddings = SentenceTransformer(EMBED_MODEL)

# Common words we never keyword-match on (they'd match almost everything).
_STOPWORDS = {
    "the", "a", "an", "is", "are", "was", "were", "be", "been", "being",
    "of", "to", "in", "on", "for", "with", "as", "by", "at", "from", "and",
    "or", "but", "if", "then", "than", "that", "this", "these", "those",
    "it", "its", "what", "which", "who", "whom", "how", "why", "when",
    "recommended", "standard", "treatment", "patients", "patient", "use",
    "used", "using", "does", "do", "did", "can", "could", "should", "would",
    "hospital", "hospitals", "severe", "indonesian", "indonesia",
}

# Drop a keyword only if it's near-ubiquitous (appears in > this fraction of the
# corpus). Everything else gets its OWN weighted channel, so rarity is handled
# by IDF weighting rather than by an all-or-nothing cutoff.
_DROP_DF_RATIO = 0.50

# How many distinct keyword channels to run (rarest terms first).
_MAX_KEYWORD_CHANNELS = 4

# Baseline weight for the dense/semantic channel in the fusion.
_DENSE_WEIGHT = 1.5


def _extract_keywords(query, max_terms=8):
    """Pull candidate terms (drug names, conditions) out of the query."""
    words = re.findall(r"[A-Za-z0-9\-]{3,}", query.lower())
    keywords = []
    for w in words:
        if w in _STOPWORDS:
            continue
        if w not in keywords:
            keywords.append(w)
    return keywords[:max_terms]


def _keyword_doc_frequencies(cursor, keywords):
    """[(keyword, df), ...] using the SAME predicate as the keyword channel
    (chunk_text OR title), sorted rarest-first. Drops df==0 terms."""
    scored = []
    for kw in keywords:
        cursor.execute(
            """SELECT COUNT(*)
               FROM chunks c JOIN papers p ON c.paper_id = p.paper_id
               WHERE c.chunk_text ILIKE %s OR p.title ILIKE %s;""",
            (f"%{kw}%", f"%{kw}%"),
        )
        df = cursor.fetchone()[0]
        if df > 0:
            scored.append((kw, df))
    scored.sort(key=lambda x: x[1])  # rarest first
    return scored


def _weighted_keywords(cursor, keywords, debug=False):
    """
    Return [(keyword, idf_weight), ...] for the distinctive terms.

    Each kept keyword gets its OWN channel, weighted by IDF = log(total / df).
    Rare terms (ivermectin) get a large weight; common terms (covid-19) get a
    small one. Near-ubiquitous terms (>50% of corpus) are dropped entirely.
    The single rarest term is always kept so the channel never goes empty.
    """
    if not keywords:
        return []

    cursor.execute("SELECT COUNT(*) FROM chunks;")
    total = cursor.fetchone()[0] or 1

    scored = _keyword_doc_frequencies(cursor, keywords)
    if not scored:
        return []

    usable = [(kw, df) for kw, df in scored if df <= _DROP_DF_RATIO * total]
    if not usable:
        usable = [scored[0]]  # guarantee the rarest term survives

    usable = usable[:_MAX_KEYWORD_CHANNELS]
    weighted = [(kw, math.log(total / df)) for kw, df in usable]

    if debug:
        print(f"    [debug] total_chunks={total}")
        dfmap = dict(scored)
        print("    [debug] per-keyword df / idf-weight (rarest first):")
        for kw, w in weighted:
            print(f"        {kw:<14} df={dfmap[kw]:<5} weight={w:.2f}")

    return weighted


def _fetch_metadata_rows(cursor, where_sql, params, limit):
    """SELECT the standard enriched columns given a WHERE/ORDER clause."""
    cursor.execute(f"""
        SELECT
            c.chunk_text,
            1 - (c.embedding <=> %s::vector) AS similarity_score,
            c.chunk_id,
            p.title,
            p.doi,
            p.publication_date,
            p.study_design,
            p.clinical_specialty,
            p.patient_demographic,
            s.trust_tier,
            cp.intervention,
            cp.outcome
        FROM chunks c
        JOIN papers p ON c.paper_id = p.paper_id
        LEFT JOIN sources s ON p.source_id = s.source_id
        LEFT JOIN clinical_pico cp ON p.paper_id = cp.paper_id
        {where_sql}
        LIMIT %s;
    """, params + [limit])
    return cursor.fetchall()


def _row_to_dict(row):
    return {
        "text": row[0],
        "score": round(row[1], 3),
        "chunk_id": row[2],
        "title": row[3],
        "doi": row[4],
        "publication_date": row[5],
        "study_design": row[6],
        "clinical_specialty": row[7],
        "patient_demographic": row[8],
        "trust_tier": row[9],
        "intervention": row[10],
        "outcome": row[11],
    }


def retrieve(query, top_k=3, fetch_k=20, min_score=0.25, kw_limit=15, debug=False):
    """
    HYBRID retrieval = dense vector channel + ONE weighted channel PER
    distinctive keyword, fused with Reciprocal Rank Fusion (RRF).

    Giving each keyword its own channel (instead of OR-ing them) means a rare
    term like 'ivermectin' gets dedicated, high-weight slots that a common term
    like 'covid-19' cannot crowd out. Chunks that match a rare term AND are
    semantically close rise to the top.
    """
    query_vector = embeddings.encode(query).tolist()
    raw_keywords = _extract_keywords(query)

    conn = psycopg2.connect(DB_URL)
    cursor = conn.cursor()

    # ---- CHANNEL A: DENSE VECTOR SEARCH ----
    dense_rows = _fetch_metadata_rows(
        cursor,
        where_sql="ORDER BY c.embedding <=> %s::vector",
        params=[query_vector, query_vector],
        limit=fetch_k,
    )

    # ---- CHANNELS B..n: ONE WEIGHTED CHANNEL PER DISTINCTIVE KEYWORD ----
    weighted_keywords = _weighted_keywords(cursor, raw_keywords, debug=debug)
    keyword_channels = []  # list of (rows, weight, keyword)
    for kw, weight in weighted_keywords:
        rows = _fetch_metadata_rows(
            cursor,
            where_sql=(
                "WHERE c.chunk_text ILIKE %s OR p.title ILIKE %s "
                "ORDER BY c.embedding <=> %s::vector"
            ),
            params=[query_vector, f"%{kw}%", f"%{kw}%", query_vector],
            limit=kw_limit,
        )
        keyword_channels.append((rows, weight, kw))

    conn.close()

    if debug:
        print(f"    [debug] dense channel: {len(dense_rows)} rows")
        for rows, weight, kw in keyword_channels:
            print(f"    [debug] keyword channel '{kw}' (weight {weight:.2f}): {len(rows)} rows")

    # ---- MERGE with weighted Reciprocal Rank Fusion (RRF) ----
    RRF_K = 60
    fused = {}  # chunk_id -> {"row", "rrf", "sim"}

    def add_channel(rows, weight):
        for rank, row in enumerate(rows, start=1):
            chunk_id = row[2]
            sim = row[1]
            contribution = weight / (RRF_K + rank)
            entry = fused.get(chunk_id)
            if entry is None:
                fused[chunk_id] = {"row": row, "rrf": contribution, "sim": sim}
            else:
                entry["rrf"] += contribution

    add_channel(dense_rows, _DENSE_WEIGHT)
    for rows, weight, _kw in keyword_channels:
        add_channel(rows, weight)

    ranked = sorted(fused.values(), key=lambda e: e["rrf"], reverse=True)

    # ---- FILTER + DEDUPE BY PAPER + CAP AT top_k ----
    enriched_results = []
    seen_dois = set()
    for entry in ranked:
        row = entry["row"]
        sim = entry["sim"]

        if sim < min_score:
            continue

        doi = row[4]
        if doi in seen_dois:
            continue
        seen_dois.add(doi)

        enriched_results.append(_row_to_dict(row))

        if len(enriched_results) >= top_k:
            break

    if debug:
        print("    [debug] final fused top papers:")
        for r in enriched_results:
            print(f"        sim={r['score']}  {r['title'][:55]}")

    return enriched_results
import psycopg2
from sentence_transformers import SentenceTransformer
from src.config import *

# Initialize your local embedding model
embeddings = SentenceTransformer(EMBED_MODEL)

def retrieve(query, top_k=2):
    # 1. Vectorize the user's question
    query_vector = embeddings.encode(query).tolist()

    enriched_results = []
    
    # 2. Connect to Supabase
    conn = psycopg2.connect(DB_URL)
    cursor = conn.cursor()

    # 3. Query pgvector (Cosine Distance: <=>) and JOIN metadata tables
    cursor.execute("""
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
        JOIN sources s ON p.source_id = s.source_id
        LEFT JOIN clinical_pico cp ON p.paper_id = cp.paper_id
        ORDER BY c.embedding <=> %s::vector
        LIMIT %s;
    """, (query_vector, query_vector, top_k))
    
    results = cursor.fetchall()
    conn.close()

    # 4. Format the output
    for row in results:
        score = row[1]
        
        # Filter low confidence results
        if score < 0.3:
            continue
            
        enriched_results.append({
            "text": row[0],
            "score": round(score, 3),
            "chunk_id": row[2],
            "title": row[3],
            "doi": row[4],
            "publication_date": row[5],
            "study_design": row[6],
            "clinical_specialty": row[7],
            "patient_demographic": row[8],
            "trust_tier": row[9],
            "intervention": row[10],
            "outcome": row[11]
        })

    return enriched_results
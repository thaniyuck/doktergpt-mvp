import os
import time
import torch
import tracemalloc
import numpy as np
import pandas as pd
import math
import re
from sentence_transformers import SentenceTransformer, util
import warnings

warnings.filterwarnings("ignore")

# =====================================================================
# 1. CONFIGURATION
# =====================================================================
os.environ["HF_HOME"] = "D:/HuggingFace_Cache"
os.environ["SENTENCE_TRANSFORMERS_HOME"] = "D:/HuggingFace_Cache"

# The Winning Model
EMBEDDING_MODEL = "BAAI/bge-m3"
K_VALUE = 5  

# The 3 Chunking Strategies you just generated
CHUNKING_STRATEGIES = [
    {"name": "Recursive Large (1000c)", "file": "chunks_recursive_large.csv"},
    {"name": "Recursive Small (400c)", "file": "chunks_recursive_small.csv"},
    {"name": "Semantic Chunking (MiniLM)", "file": "chunks_semantic.csv"}
]

# =====================================================================
# 2. METRICS CALCULATOR
# =====================================================================
def clean_paper_ids(raw_string):
    if pd.isna(raw_string): return set()
    return set(re.findall(r'[A-Za-z0-9_]+', str(raw_string)))

def calculate_ndcg(found_ranks, total_relevant_count, k=K_VALUE):
    if not found_ranks: return 0.0
    dcg = sum([1.0 / math.log2(rank + 1) for rank in found_ranks if rank <= k])
    idcg = sum([1.0 / math.log2(i + 1) for i in range(1, min(k, total_relevant_count) + 1)])
    return dcg / idcg if idcg > 0 else 0.0

def calculate_context_precision(found_ranks, k=K_VALUE):
    if not found_ranks: return 0.0
    precision_sum = 0
    hits_so_far = 0
    for rank in range(1, k + 1):
        if rank in found_ranks:
            hits_so_far += 1
            precision_sum += hits_so_far / rank
    return precision_sum / len(found_ranks)

# =====================================================================
# 3. MAIN EXECUTION
# =====================================================================
if __name__ == "__main__":
    # --- 1. Find Golden Dataset ---
    possible_golden_names = ['dokterGPT-embedding-golden-dataset.csv', 'dokterGPT_Database - embedding-golden-dataset.csv']
    resolved_golden_path = None
    
    for name in possible_golden_names:
        if os.path.exists(os.path.join(os.getcwd(), name)):
            resolved_golden_path = os.path.join(os.getcwd(), name)
            break
        elif os.path.exists(os.path.join(os.path.dirname(os.path.abspath(__file__)), name)):
            resolved_golden_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), name)
            break
            
    if not resolved_golden_path:
        print("❌ Missing Golden Dataset! Please ensure the CSV is in the folder.")
        exit()

    golden_df = pd.read_csv(resolved_golden_path).dropna(subset=['query', 'relevant_papers'])
    queries = golden_df['query'].tolist()
    
    # --- 2. Initialize Hardware & Model ---
    device = "cuda" if torch.cuda.is_available() else "cpu"
    print(f"\n🚀 Loading Winning Embedder: {EMBEDDING_MODEL} on {device.upper()}...")
    model = SentenceTransformer(EMBEDDING_MODEL, device=device)
    
    # Embed queries once (huge time saver!)
    print(f"🧠 Embedding {len(queries)} Golden Queries...")
    query_embeddings = model.encode(queries, convert_to_tensor=True, show_progress_bar=False)

    results = []

    # --- 3. Evaluate Each Chunking Strategy ---
    for strategy in CHUNKING_STRATEGIES:
        strat_name = strategy["name"]
        strat_file = strategy["file"]
        
        print(f"\n{'='*60}\n⚔️ EVALUATING STRATEGY: {strat_name}\n{'='*60}")
        
        if not os.path.exists(strat_file):
            print(f"❌ Missing file: {strat_file}. Skipping...")
            continue
            
        chunks_df = pd.read_csv(strat_file).dropna(subset=['chunk_text', 'paper_id'])
        corpus_paper_ids = chunks_df['paper_id'].tolist()
        corpus_texts = chunks_df['chunk_text'].tolist()
        
        print(f"📚 Loaded {len(corpus_texts)} chunks. Embedding Database...")
        start_embed_time = time.time()
        corpus_embeddings = model.encode(corpus_texts, convert_to_tensor=True, show_progress_bar=True, batch_size=8)
        embed_time = time.time() - start_embed_time
        
        print("🔍 Simulating Vector Search...")
        cos_scores = util.cos_sim(query_embeddings, corpus_embeddings)
        
        hits, mrr_sum, ndcg_sum, recall_sum, precision_sum = 0, 0, 0, 0, 0
        
        for query_idx, row in golden_df.iterrows():
            target_ids = clean_paper_ids(row['relevant_papers'])
            if not target_ids: continue
                
            top_results = torch.topk(cos_scores[query_idx], k=K_VALUE)
            
            found_ranks = []
            found_paper_ids = set()
            
            for rank_idx, corpus_idx in enumerate(top_results[1]):
                retrieved_paper_id = corpus_paper_ids[corpus_idx.item()]
                if retrieved_paper_id in target_ids and retrieved_paper_id not in found_paper_ids:
                    found_ranks.append(rank_idx + 1) 
                    found_paper_ids.add(retrieved_paper_id)
                    
            if found_ranks:
                hits += 1
                mrr_sum += (1.0 / found_ranks[0])
                ndcg_sum += calculate_ndcg(found_ranks, len(target_ids), K_VALUE)
                recall_sum += len(found_ranks) / len(target_ids)  
                precision_sum += calculate_context_precision(found_ranks, K_VALUE)
                
        total_queries = len(golden_df)
        
        results.append({
            "Chunking Strategy": strat_name,
            "Total Chunks": len(corpus_texts),
            "Recall@5": round(recall_sum / total_queries, 3),
            "Ctx Precision": round(precision_sum / total_queries, 3),
            "NDCG@5": round(ndcg_sum / total_queries, 3),
            "Hit Rate": round(hits / total_queries, 3)
        })

    # --- 4. Print the Final Leaderboard ---
    if results:
        print("\n\n" + "="*95)
        print("🏆 CHUNKING STRATEGY LEADERBOARD 🏆")
        print("="*95)
        
        results_df = pd.DataFrame(results)
        results_df = results_df.sort_values(by=["Recall@5", "NDCG@5"], ascending=[False, False]).reset_index(drop=True)
        
        print(results_df.to_string(index=False))
        results_df.to_csv("arena_chunking_results.csv", index=False)
        print("\n💾 Results saved to 'arena_chunking_results.csv'")
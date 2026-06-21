import os
import time
import torch
import pandas as pd
import numpy as np
from sentence_transformers import SentenceTransformer, util
from rouge_score import rouge_scorer
import requests
import warnings

warnings.filterwarnings("ignore")

# =====================================================================
# 1. CONFIGURATION
# =====================================================================
os.environ["HF_HOME"] = "D:/HuggingFace_Cache"
os.environ["SENTENCE_TRANSFORMERS_HOME"] = "D:/HuggingFace_Cache"

DATASET_NAME = "Prompt Engineering_DokterGPT - main.csv"
OUTPUT_CSV = "llm_evaluation_results.csv"

# The Embedding Model to use as the Evaluator (Judging Semantic Meaning)
EVALUATOR_MODEL = "BAAI/bge-m3"

# The LLMs you want to evaluate via your local Ollama instance
MODELS_TO_EVALUATE = [
    "llama3",
    "qwen2.5",
    "tinyllama"
]

# =====================================================================
# 2. INFERENCE / GENERATION SETUP
# =====================================================================
def generate_answer(query, model_name):
    """
    Sends the query to a local LLM via Ollama API (Default port 11434).
    If you use HuggingFace or a cloud API (OpenAI/Groq), modify this block.
    """
    try:
        url = "http://localhost:11434/api/generate"
        
        # Base clinical prompt instructions
        prompt = f"Please answer the following clinical question accurately based on medical evidence:\n\n{query}"
        
        payload = {
            "model": model_name,
            "prompt": prompt,
            "stream": False
        }
        
        # Timeout set to 180s to allow heavy models to process without failing
        response = requests.post(url, json=payload, timeout=180)
        
        if response.status_code == 200:
            return response.json().get("response", "").strip()
        else:
            return f"[API Error {response.status_code}]"
            
    except requests.exceptions.ConnectionError:
        return f"[Connection Error: Ensure Ollama is running and has '{model_name}' installed.]"
    except Exception as e:
        return f"[Error: {str(e)}]"

# =====================================================================
# 3. METRICS CALCULATOR
# =====================================================================
def calculate_semantic_similarity(embedder, text1, text2):
    """Calculates Cosine Similarity between two strings (e.g., Output vs Expected)."""
    if not text1 or not text2 or pd.isna(text1) or pd.isna(text2):
        return 0.0
    emb1 = embedder.encode(str(text1), convert_to_tensor=True, show_progress_bar=False)
    emb2 = embedder.encode(str(text2), convert_to_tensor=True, show_progress_bar=False)
    return util.cos_sim(emb1, emb2).item()

def calculate_rouge(scorer, prediction, reference):
    """Calculates ROUGE-L score (longest common lexical overlap sequence)."""
    if not prediction or not reference or pd.isna(prediction) or pd.isna(reference):
        return 0.0
    scores = scorer.score(str(reference), str(prediction))
    return scores['rougeL'].fmeasure

# =====================================================================
# 4. MAIN EXECUTION
# =====================================================================
if __name__ == "__main__":
    print(f"\n🚀 Initializing LLM Generation Evaluation...")
    
    # --- 1. Find and Load Dataset ---
    resolved_dataset_path = None
    
    # Check current working directory (where terminal is running from)
    if os.path.exists(os.path.join(os.getcwd(), DATASET_NAME)):
        resolved_dataset_path = os.path.join(os.getcwd(), DATASET_NAME)
    # Check the directory where this script file actually lives
    elif os.path.exists(os.path.join(os.path.dirname(os.path.abspath(__file__)), DATASET_NAME)):
        resolved_dataset_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), DATASET_NAME)
            
    if not resolved_dataset_path:
        print(f"❌ Missing dataset! Could not find '{DATASET_NAME}' in either location:")
        print(f"   -> {os.getcwd()}")
        print(f"   -> {os.path.dirname(os.path.abspath(__file__))}")
        exit()
        
    print(f"📬 Found dataset at: {resolved_dataset_path}")
    df = pd.read_csv(resolved_dataset_path).dropna(subset=['Query'])
    queries = df['Query'].tolist()
    expected_evidences = df['Expected Evidence / Paper'].tolist()
    
    print(f"📚 Loaded {len(queries)} queries for generation evaluation.")
    
    # --- 2. Initialize Evaluator Models ---
    device = "cuda" if torch.cuda.is_available() else "cpu"
    print(f"🧠 Loading Evaluator Model: {EVALUATOR_MODEL} on {device.upper()}...")
    embedder = SentenceTransformer(EVALUATOR_MODEL, device=device)
    scorer = rouge_scorer.RougeScorer(['rougeL'], use_stemmer=True)
    
    all_results = []
    
    # --- 3. Evaluate Each LLM ---
    for model_name in MODELS_TO_EVALUATE:
        print(f"\n{'='*60}\n⚙️ EVALUATING MODEL: {model_name}\n{'='*60}")
        
        model_metrics = {
            "semantic_sim_sum": 0.0,
            "rouge_l_sum": 0.0,
            "answer_relevance_sum": 0.0,
            "latency_sum": 0.0,
            "valid_responses": 0
        }
        
        # Process each query
        for idx, query in enumerate(queries):
            # Using Expected Evidence as ground truth to verify clinical accuracy
            expected_text = expected_evidences[idx] if idx < len(expected_evidences) else ""
            
            # Generate LLM Response
            start_time = time.time()
            generated_answer = generate_answer(query, model_name)
            latency = time.time() - start_time
            
            # Skip scoring if the API failed to connect
            if "[Connection Error" in generated_answer or "[API Error" in generated_answer:
                print(f"[{idx+1}/{len(queries)}] ⚠️ Setup Error for {model_name}. Skipping query.")
                all_results.append({
                    "Model": model_name, "Query": query, "Expected Evidence": expected_text,
                    "Generated Answer": generated_answer, "Latency (s)": 0, "SemSim vs Expected": 0,
                    "ROUGE-L": 0, "Answer Relevance": 0
                })
                continue

            # Calculate Evaluation Metrics
            sem_sim = calculate_semantic_similarity(embedder, generated_answer, expected_text)
            rouge_l = calculate_rouge(scorer, generated_answer, expected_text)
            ans_rel = calculate_semantic_similarity(embedder, query, generated_answer)
            
            # Save raw data matrix entry
            all_results.append({
                "Model": model_name,
                "Query": query,
                "Expected Evidence": expected_text,
                "Generated Answer": generated_answer,
                "Latency (s)": round(latency, 2),
                "SemSim vs Expected": round(sem_sim, 3),
                "ROUGE-L": round(rouge_l, 3),
                "Answer Relevance": round(ans_rel, 3)
            })
            
            # Accumulate totals for summary reporting
            model_metrics["semantic_sim_sum"] += sem_sim
            model_metrics["rouge_l_sum"] += rouge_l
            model_metrics["answer_relevance_sum"] += ans_rel
            model_metrics["latency_sum"] += latency
            model_metrics["valid_responses"] += 1
            
            print(f"[{idx+1}/{len(queries)}] Latency: {latency:.1f}s | SemSim: {sem_sim:.2f} | ROUGE: {rouge_l:.2f}")

    # --- 4. Process Results and Print Leaderboard ---
    results_df = pd.DataFrame(all_results)
    
    # Save raw outputs file with all structural columns intact
    results_df.to_csv(OUTPUT_CSV, index=False)
    
    print("\n\n" + "="*95)
    print("🏆 FINAL GENERATIVE LLM LEADERBOARD 🏆")
    print("="*95)
    
    # Exclude failed connections from calculating final metric averages
    valid_results = results_df[~results_df['Generated Answer'].str.contains(r'\[Connection Error|\[API Error', na=False, regex=True)]
    
    if not valid_results.empty:
        leaderboard = valid_results.groupby("Model").agg(
            Avg_Correctness_SemSim=("SemSim vs Expected", "mean"),
            Avg_Completeness_ROUGE=("ROUGE-L", "mean"),
            Avg_Answer_Relevance=("Answer Relevance", "mean"),
            Avg_Latency_Seconds=("Latency (s)", "mean")
        ).reset_index()
        
        # Sort by best alignment to the golden reference evidence
        leaderboard = leaderboard.sort_values(by="Avg_Correctness_SemSim", ascending=False).round(3)
        print(leaderboard.to_string(index=False))
        
    print(f"\n💾 Full Generated Answers & Metric logs saved to '{OUTPUT_CSV}'")
# -*- coding: utf-8 -*-
import os
os.environ["HF_HOME"] = "F:/HuggingFace_Cache"
os.environ["SENTENCE_TRANSFORMERS_HOME"] = "F:/HuggingFace_Cache"

import time
import sys

from src.etl.fetcher import fetch_top_indonesian_clinical_research
from src.etl.extractor import extract_metadata
from src.etl.database import push_to_databases

RESEARCH_TOPICS = [
    "Rabies OR Lyssavirus",
    "COPD OR Chronic Obstructive Pulmonary Disease",
    "Hypertension OR Cardiovascular",
    "Maternal Mortality",
    "Vaccine Efficacy",
    "Stunting OR Malnutrition",
    "Leprosy",
    "HIV AIDS",
    "Dengue Fever OR DBD",
    "Tuberculosis OR TB",
    "Diabetes Mellitus Type 2",
    "Malaria Endemic"
]

def run_continuous_pipeline():
    print(" STARTING CONTINUOUS DOKTER-GPT PIPELINE...")
    print(" Press Ctrl + C in this terminal at any time to safely stop the script.\n")
    
    cycle_count = 1
    target_quota = 5  # The exact number of valid papers you want per topic
    
    try:
        while True:
            print(f"--- STARTING SWEEP CYCLE {cycle_count} ---")
            
            for topic in RESEARCH_TOPICS:
                print(f"\n=======================================================")
                print(f"CURRENT TARGET: {topic}")
                print(f"=======================================================\n")
                
                valid_papers_found = 0
                current_page = 1
                
                # 🌟 THE SELF-HEALING QUOTA LOOP 🌟
                while valid_papers_found < target_quota:
                    papers_needed = target_quota - valid_papers_found
                    print(f"📉 Quota status: {valid_papers_found}/{target_quota}. Fetching {papers_needed} more from Page {current_page}...")
                    
                    # 1. Fetch the exact amount needed from the current page
                    papers = fetch_top_indonesian_clinical_research(
                        search_query=topic, 
                        max_results=papers_needed, 
                        page=current_page
                    )
                    
                    # Failsafe: If OpenAlex literally runs out of papers for this topic
                    if not papers:
                        print(f"OpenAlex has no more papers for '{topic}'. Moving to database push.")
                        break
                    
                    # 2. Extract JSONs. The extractor will return how many survived the guillotine.
                    accepted_this_round = extract_metadata()
                    
                    valid_papers_found += accepted_this_round
                    current_page += 1 # Turn the page for the next loop in case we still need more
                
                print(f"\nQuota filled (or maxed out) for {topic}. Pushing to databases...")
                
                # 3. Push to PGVector, Supabase, and Google Sheets
                push_to_databases()
                
                print(f"\n⏳ Topic complete. Resting for 15 seconds to cool down hardware...")
                time.sleep(15) 
            
            print(f"\nCycle {cycle_count} finished! All topics swept.")
            print("⏳ Taking a 60-second break before restarting the cycle...")
            time.sleep(60)
            cycle_count += 1
            
    except KeyboardInterrupt:
        print("\n\n🛑 MANUAL STOP DETECTED: Shutting down the pipeline gracefully.")
        print("All completed extractions and database pushes have been safely saved.")
        sys.exit(0)

if __name__ == "__main__":
    run_continuous_pipeline()
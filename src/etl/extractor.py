import os
import json
import requests
import json_repair 
import concurrent.futures 
from pydantic import BaseModel, Field
from typing import List, Union, Dict, Any

# =====================================================================
# 1. UPGRADED SCHEMA (WITH FAULT TOLERANCE)
# =====================================================================
class AuthorData(BaseModel):
    full_name: str
    primary_affiliation: str = "Not specified"

class DrugData(BaseModel):
    generic_name: str
    atc_code: str = "Not specified"

class ICDCodeData(BaseModel):
    code: str
    disease_description: str = "Not specified"
    category: str = "Not specified"

class KeywordData(BaseModel):
    term: str
    is_mesh_term: Union[bool, str] = False

class SourceData(BaseModel):
    name: str = "Not specified"
    source_type: str = "Not specified"
    trust_tier: Union[int, str] = "Not specified" # <-- Added safe default

class PICOData(BaseModel):
    population: str = "Not specified"
    intervention: str = "Not specified"
    comparison: str = "Not specified"
    outcome: str = "Not specified"

class AbstractData(BaseModel):
    background_and_objective: str = "Not specified"
    methods: str = "Not specified"
    results: str = "Not specified"
    conclusion: str = "Not specified"

class PaperExtraction(BaseModel):
    title: str = "Not specified"
    abstract: AbstractData  
    doi: str = "Not specified"
    publication_date: Union[str, int] = "Not specified"
    study_design: str = "Not specified"
    sample_size_n: Union[str, int] = "Not specified"
    patient_demographic: Union[str, Dict[str, Any]] = "Not specified"
    clinical_specialty: str = "Not specified"
    ethical_clearance_status: str = "Not specified"
    study_limitations: str = "Not specified"
    statistical_significance: str = "Not specified"
    source: SourceData = Field(default_factory=SourceData)
    authors: List[AuthorData] = []
    icd_10_suggestions: List[ICDCodeData] = []
    drugs_and_substances: List[DrugData] = []
    keywords: List[KeywordData] = []
    pico: PICOData = Field(default_factory=PICOData)
    is_indonesian_context: bool = False # <-- Safely defaults to False if AI forgets it

# =====================================================================
# 2. CONFIGURATION & PATHS
# =====================================================================
DRIVE_BASE = "G:/My Drive/dokterGPT_Data"
MD_DIR = os.path.join(DRIVE_BASE, "parsed_md")
JSON_DIR = os.path.join(DRIVE_BASE, "extracted_json")

os.makedirs(JSON_DIR, exist_ok=True)

# 🌟 THE ANTI-HALLUCINATION JSON TEMPLATE 🌟
json_template = """{
  "title": "[Insert Exact Paper Title Here]",
  "abstract": {
    "background_and_objective": "[Insert detailed background, context, and study objective]",
    "methods": "[Insert comprehensive methodology, study design, and settings]",
    "results": "[Insert detailed results, including specific numbers, data points, and statistics]",
    "conclusion": "[Insert main conclusions and clinical recommendations]"
  },
  "doi": "[Insert DOI or 'Not specified']",
  "publication_date": "[Insert Year/Date or 'Not specified']",
  "study_design": "[Insert Study Design, e.g., Randomized Controlled Trial, Systematic Review]",
  "sample_size_n": "[Insert number of participants/samples or 'Not specified']",
  "patient_demographic": "[Insert Age, Gender, or Location]",
  "clinical_specialty": "[Insert Specialty, e.g., Cardiology, Neurology]",
  "ethical_clearance_status": "[Insert Clearance Info or 'Not specified']",
  "study_limitations": "[Insert stated limitations, e.g., Small sample size, or 'Not specified']",
  "statistical_significance": "[Insert p-values, Confidence Intervals, or 'Not specified']",
  "source": {
    "name": "[Insert EXACT Journal Name (e.g., Acta Medica Indonesiana) or Publishing Institution]",
    "source_type": "[Insert Type, e.g., Peer-Reviewed Journal, Government Guideline, Clinical Trial]",
    "trust_tier": "[Insert Tier 1, 2, 3, 4, or 5]"
  },
  "authors": [
    {
      "full_name": "[Insert Author 1 Name]",
      "primary_affiliation": "[Insert Author 1 Institution/Hospital]"
    }
  ],
  "icd_10_suggestions": [
    {
      "code": "[Insert Code 1]",
      "disease_description": "[Insert Description]",
      "category": "[Insert Category]"
    }
  ], 
  "drugs_and_substances": [
    {
      "generic_name": "[Insert Drug/Substance 1]",
      "atc_code": "[Insert ATC Code or 'Not specified']"
    }
  ], 
  "keywords": [
    {
      "term": "[Insert Keyword]",
      "is_mesh_term": true
    }
  ],
  "pico": {
    "population": "[Insert Patient Group/Disease]",
    "intervention": "[Insert Treatment/Test]",
    "comparison": "[Insert Comparison/Placebo]",
    "outcome": "[Insert Findings]"
  },
  "is_indonesian_context": true
}"""

# =====================================================================
# 3. EXTRACTION LOGIC
# =====================================================================

def process_single_paper(filename):
    json_filename = filename.replace('.md', '.json')

    if os.path.exists(os.path.join(JSON_DIR, json_filename)):
        print(f"   ⏭️ Skipping already extracted file: {filename}...")
        return 0

    print(f"🧠 Asking local Ollama AI to analyze: {filename}...")

    md_filepath = os.path.join(MD_DIR, filename)
    with open(md_filepath, "r", encoding="utf-8") as f:
        content = f.read()

    if "## Authors & Affiliations" in content and "## Keywords & Categorization" in content:
        top_part = content.split("## Authors & Affiliations")[0]
        middle_part = content.split("## Authors & Affiliations")[1].split("## Keywords & Categorization")[0]
        bottom_part = "## Keywords & Categorization" + content.split("## Keywords & Categorization")[1]
        
        author_lines = [line for line in middle_part.split('\n') if line.strip().startswith('- ')]
        if len(author_lines) > 5:
            middle_part = '\n'.join(author_lines[:5]) + '\n- et al. (Remaining authors truncated)\n\n'
            
        content = top_part + "## Authors & Affiliations\n" + middle_part + bottom_part

    content = content[:6000] 

    prompt = f"""[INST] You are an expert Indonesian Medical Data Extractor.
Read the MEDICAL PAPER below. You must extract the metadata and format it EXACTLY like the JSON TEMPLATE.

CRITICAL INSTRUCTIONS:
1. Do NOT output the template verbatim.
2. You MUST replace the placeholder text in the brackets with actual information from the text.
3. If information is missing, use the string "Not specified".
4. SOURCE EXTRACTION RULE: Look carefully for the Journal Name, Publisher, or Conference where this paper was published. Use that as the source "name".
5. Output ONLY the filled JSON object. No explanations.
6. CRITICAL: Do NOT use unescaped double quotes inside your text values.
7. INDONESIAN CONTEXT RULE: Set "is_indonesian_context" to true if the text mentions Indonesian patients, Indonesian cities/hospitals, OR if the authors are from Indonesian institutions.
8. HALLUCINATION RULE: If you cannot find a specific drug, substance, or ICD code, return an empty array [].
9. DEEP ABSTRACT RULE: DO NOT SUMMARIZE THE ABSTRACT. You must extract the maximum amount of detail possible for the background, methods, results, and conclusion fields. Preserve specific data points, percentages, and clinical findings.

JSON TEMPLATE TO FILL OUT:
{json_template}

MEDICAL PAPER:
{content}
[/INST]
"""

    try:
        response = requests.post('http://localhost:11434/api/generate', json={
            "model": "llama3", 
            "prompt": prompt,
            "stream": False,
            "format": "json",
            "keep_alive": 0,          
            "options": {              
                "num_ctx": 4096,
                "num_predict": 1000,
                "temperature": 0.1   
            }
        })               
        
        response.raise_for_status()
        raw_output = response.json().get('response', '')

        start = raw_output.find('{')
        end = raw_output.rfind('}')
        json_str = raw_output[start:end+1] if (start != -1 and end != -1 and end >= start) else raw_output

        repaired_json_dict = json_repair.loads(json_str) 

        # 🛠️ THE ADVANCED AI TYPO FIXER 🛠️
        
        # 1. Fix context boolean key
        if "is_indonesian" in repaired_json_dict and "is_indonesian_context" not in repaired_json_dict:
            repaired_json_dict["is_indonesian_context"] = repaired_json_dict.pop("is_indonesian")
            
        # 2. Fix the Array Generators
        for key in ["drugs_and_substances", "icd_10_suggestions", "keywords", "authors"]:
            if key in repaired_json_dict and isinstance(repaired_json_dict[key], list):
                cleaned_list = []
                for item in repaired_json_dict[key]:
                    # Standard Objects
                    if isinstance(item, dict):
                        item_str = str(item).lower()
                        if "insert" not in item_str and "not specified" not in item_str and "extract" not in item_str:
                            cleaned_list.append(item)
                    
                    # LLM Laziness Rescue (It listed strings instead of objects)
                    elif isinstance(item, str):
                        if key == "keywords":
                            cleaned_list.append({"term": item, "is_mesh_term": False})
                        elif key == "authors":
                            cleaned_list.append({"full_name": item, "primary_affiliation": "Not specified"})
                        elif key == "drugs_and_substances":
                            cleaned_list.append({"generic_name": item, "atc_code": "Not specified"})
                        elif key == "icd_10_suggestions":
                            cleaned_list.append({"code": item, "disease_description": "Not specified", "category": "Not specified"})
                
                repaired_json_dict[key] = cleaned_list

        # Now hand it to Pydantic (With new safe defaults)
        structured_data = PaperExtraction(**repaired_json_dict)

        # 🛑 THE STRICT INDONESIAN CONTEXT GUILLOTINE 🛑
        if not structured_data.is_indonesian_context:
            print(f"   🚫 REJECTED: '{structured_data.title[:60]}...' lacks local context.")
            if os.path.exists(md_filepath):
                os.remove(md_filepath)
            return 0 

        # Save to G: Drive
        with open(os.path.join(JSON_DIR, json_filename), "w", encoding="utf-8") as f:
            json.dump(structured_data.model_dump(), f, indent=4)

        print(f"✅ Extracted data saved to {json_filename}\n")
        return 1

    except Exception as e:
        print(f"❌ Error extracting data from {filename}: {str(e)}\n")
        return 0


def extract_metadata():
    if not os.path.exists(MD_DIR):
        print(f"📂 Markdown directory not found at {MD_DIR}")
        return 0

    md_files = [f for f in os.listdir(MD_DIR) if f.endswith('.md')]

    if not md_files:
        print("📂 No markdown files found!")
        return 0

    print(f"🚀 Found {len(md_files)} papers. Starting Sequential Local AI Extraction...\n")

    papers_accepted = 0 
    
    with concurrent.futures.ThreadPoolExecutor(max_workers=1) as executor:
        results = executor.map(process_single_paper, md_files)
        papers_accepted = sum(results)
            
    return papers_accepted

if __name__ == "__main__":
    extract_metadata()
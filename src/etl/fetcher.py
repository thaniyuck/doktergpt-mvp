# -*- coding: utf-8 -*-
import os
import time
import requests
import xml.etree.ElementTree as ET

# --- CONFIGURATION ---
DRIVE_BASE = "G:/My Drive/dokterGPT_Data" 
MD_DIR = os.path.join(DRIVE_BASE, "parsed_md")
os.makedirs(MD_DIR, exist_ok=True)

# NCBI E-utilities endpoints
ESEARCH_URL = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esearch.fcgi"
EFETCH_URL = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/efetch.fcgi"

def fetch_top_indonesian_clinical_research(search_query, max_results=5, page=1):
    # Modify the query to enforce the Indonesian context and require an abstract
    pubmed_query = f"({search_query}) AND Indonesia[Affiliation] AND hasabstract[text]"
    print(f"🔍 Searching PubMed for: '{pubmed_query}'...")
    
    # STEP 1: Search for PMIDs
    search_params = {
        "db": "pubmed",
        "term": pubmed_query,
        "retmode": "json",
        "retmax": max_results * 3, # Fetch extra in case we drop some during filtering
        "retstart": (page - 1) * (max_results * 3)
    }
    
    try:
        search_response = requests.get(ESEARCH_URL, params=search_params)
        search_response.raise_for_status()
        id_list = search_response.json().get("esearchresult", {}).get("idlist", [])
    except Exception as e:
        print(f"❌ PubMed Search Error: {e}")
        return []

    if not id_list:
        return []

    # STEP 2: Fetch the actual XML data for those PMIDs
    fetch_params = {
        "db": "pubmed",
        "id": ",".join(id_list),
        "retmode": "xml"
    }
    
    try:
        fetch_response = requests.get(EFETCH_URL, params=fetch_params)
        fetch_response.raise_for_status()
        root = ET.fromstring(fetch_response.content)
    except Exception as e:
        print(f"❌ PubMed Fetch Error: {e}")
        return []

    papers_downloaded = []
    
    # STEP 3: Parse the XML and build the Markdown files
    for article in root.findall(".//PubmedArticle"):
        try:
            pmid = article.findtext(".//PMID")
            title = article.findtext(".//ArticleTitle")
            
            # Reconstruct the abstract (sometimes broken into sections like "Background", "Methods")
            abstract_texts = article.findall(".//AbstractText")
            abstract_text = " ".join([elem.text for elem in abstract_texts if elem.text])
            
            if not title or not abstract_text:
                continue
                
            # 🛑 DEFENSIVE TRUNCATION FILTERS
            if len(abstract_text) < 600: continue
            if abstract_text.endswith("...") or abstract_text.endswith(".."): continue
            if not abstract_text[-1] in [".", "!", "?"]: continue

            # Extract Year
            pub_year = article.findtext(".//PubDate/Year")
            if not pub_year:
                pub_year = article.findtext(".//ArticleDate/Year") or "Unknown"

            # Extract Journal
            journal = article.findtext(".//Title") or "Unknown Journal"

            # Extract DOI
            doi = "DOI not provided"
            for el in article.findall(".//ArticleId"):
                if el.get("IdType") == "doi":
                    doi = el.text
                    break

            # Extract Authors
            authors_list = []
            for author in article.findall(".//Author"):
                last_name = author.findtext("LastName") or ""
                fore_name = author.findtext("ForeName") or ""
                affiliation = author.findtext(".//Affiliation") or "Indonesian Institution"
                if last_name or fore_name:
                    authors_list.append(f"- {fore_name} {last_name} ({affiliation.split(',')[0]})")
            
            authors_str = "\n".join(authors_list) if authors_list else "- Unknown Author"

            # Extract MeSH Terms / Keywords
            mesh_list = [mesh.text for mesh in article.findall(".//DescriptorName")]
            mesh_str = ", ".join(mesh_list) if mesh_list else "Clinical Research"

            # Format the Markdown to exactly match what `extractor.py` expects
            filepath = os.path.join(MD_DIR, f"PUBMED_{pmid}.md")
            
            md_content = f"""# {title}

**Publication Year:** {pub_year}
**DOI:** {doi}
**PubMed URL:** https://pubmed.ncbi.nlm.nih.gov/{pmid}/
**Journal/Source:** {journal}
**Publication Types:** Journal Article

## Authors & Affiliations
{authors_str}

## Keywords & Categorization
**MeSH Terms:** {mesh_str}
**Author Keywords:** {mesh_str}
**Chemicals & Drugs Used:** Extracted via AI

## Abstract
{abstract_text}
"""
            with open(filepath, "w", encoding="utf-8") as f:
                f.write(md_content)
                
            print(f"   📄 Downloaded: {title[:40]}...")
            papers_downloaded.append(pmid)
            
            if len(papers_downloaded) >= max_results:
                break
                
        except Exception as e:
            # Skip corrupted XML entries
            continue

    # Respect NCBI's rate limits
    time.sleep(0.5) 
    return papers_downloaded
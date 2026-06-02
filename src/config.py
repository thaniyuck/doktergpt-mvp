# -*- coding: utf-8 -*-
import os
os.environ["HF_HOME"] = "D:/HuggingFace_Cache"
os.environ["SENTENCE_TRANSFORMERS_HOME"] = "D:/HuggingFace_Cache"
from pathlib import Path

# ==========================================
# 1. DIRECTORY PATHS (Dynamic absolute paths)
# ==========================================
# This automatically points to F:\dokterGPT_Pipeline (the root folder)
BASE_DIR = Path(__file__).resolve().parent.parent 

DATA_DIR = BASE_DIR / "data"
SECRETS_DIR = BASE_DIR / "secrets"
ASSETS_DIR = BASE_DIR / "assets"

# ==========================================
# 2. SPECIFIC FILE PATHS
# ==========================================
CREDENTIALS_PATH = SECRETS_DIR / "credentials.json"
SCIMAGO_PATH = ASSETS_DIR / "scimago.csv"

# ==========================================
# 3. GLOBAL VARIABLES
# ==========================================
DB_URL = "postgresql://postgres.cviumnakesybhqiuwdij:doktergpt123@aws-1-ap-southeast-1.pooler.supabase.com:6543/postgres"

# Make sure this matches exactly what is in database.py
EMBED_MODEL = "BAAI/bge-m3" 
LLM_MODEL = "llama3"
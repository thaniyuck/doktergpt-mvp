import os
import pandas as pd
import warnings
from langchain_core.documents import Document
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_experimental.text_splitter import SemanticChunker
from langchain_huggingface import HuggingFaceEmbeddings

# Suppress the langchain-experimental deprecation warning for a clean terminal
warnings.filterwarnings("ignore")

# =====================================================================
# 1. CONFIGURATION
# =====================================================================
os.environ["HF_HOME"] = "D:/HuggingFace_Cache"

# THE FIX: We use the gviz trick to explicitly target the 'papers' sheet by name!
SHEETS_PAPERS_URL = 'https://docs.google.com/spreadsheets/d/1VDVKplT4ZpN2G2znlazu64hLfL_MGxRTgsVtBYcQ0Yg/gviz/tq?tqx=out:csv&sheet=papers'

# Output files for the Arena
OUTPUT_LARGE = "chunks_recursive_large.csv"
OUTPUT_SMALL = "chunks_recursive_small.csv"
OUTPUT_SEMANTIC = "chunks_semantic.csv"

# =====================================================================
# 2. LOAD DATA FROM GOOGLE SHEETS
# =====================================================================
print("📥 Downloading raw papers from Google Sheets (papers tab)...")
try:
    df = pd.read_csv(SHEETS_PAPERS_URL).dropna(subset=['abstract', 'paper_id'])
    print(f"✅ Successfully loaded {len(df)} papers.")
except Exception as e:
    print(f"❌ Failed to load from Google Sheets. Error: {e}")
    exit()

# Convert Pandas rows into LangChain Document objects
documents = []
for _, row in df.iterrows():
    content = f"Title: {row['title']}\nAbstract: {row['abstract']}"
    doc = Document(page_content=content, metadata={"paper_id": row['paper_id']})
    documents.append(doc)

# =====================================================================
# 3. INITIALIZE THE CHUNKERS
# =====================================================================
print("\n⚙️ Initializing LangChain Chunking Engines...")

# Strategy 1: Large & Contextual (Standard)
splitter_large = RecursiveCharacterTextSplitter(
    chunk_size=1000, 
    chunk_overlap=200,
    separators=["\n\n", "\n", ".", " ", ""]
)

# Strategy 2: Small & Precise
splitter_small = RecursiveCharacterTextSplitter(
    chunk_size=400, 
    chunk_overlap=50,
    separators=["\n\n", "\n", ".", " ", ""]
)

# Strategy 3: Semantic Chunker
print("Loading lightweight embedding model for Semantic Chunking...")
semantic_embeddings = HuggingFaceEmbeddings(model_name="all-MiniLM-L6-v2")
splitter_semantic = SemanticChunker(
    semantic_embeddings, 
    breakpoint_threshold_type="percentile" 
)

# =====================================================================
# 4. EXECUTE CHUNKING & SAVE
# =====================================================================
def process_and_save(splitter, documents, output_filename, strategy_name):
    print(f"\n🔪 Executing {strategy_name}...")
    
    chunks = splitter.split_documents(documents)
    
    chunk_data = []
    for i, chunk in enumerate(chunks):
        chunk_data.append({
            "chunk_id": f"CHK_EVAL_{i}", # Added a mock chunk_id for the DataFrame
            "paper_id": chunk.metadata["paper_id"],
            "chunk_text": chunk.page_content
        })
        
    chunk_df = pd.DataFrame(chunk_data)
    chunk_df.to_csv(output_filename, index=False)
    print(f"✅ Generated {len(chunk_df)} chunks. Saved to '{output_filename}'")

# Run all three strategies
process_and_save(splitter_large, documents, OUTPUT_LARGE, "Strategy 1: Recursive Large (1000c)")
process_and_save(splitter_small, documents, OUTPUT_SMALL, "Strategy 2: Recursive Small (400c)")
process_and_save(splitter_semantic, documents, OUTPUT_SEMANTIC, "Strategy 3: Semantic Chunking")

print("\n🎉 All chunking strategies generated successfully! You are ready for the Arena.")
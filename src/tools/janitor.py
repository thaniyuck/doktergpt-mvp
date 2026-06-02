# -*- coding: utf-8 -*-
import os
import time
import psycopg2
import gspread

# =====================================================================
# 1. CONFIGURATION & FILE PATHS
# =====================================================================
DRIVE_BASE = "G:/My Drive/dokterGPT_Data"
MD_DIR = os.path.join(DRIVE_BASE, "parsed_md")
JSON_DIR = os.path.join(DRIVE_BASE, "extracted_json")

DB_URL = "postgresql://postgres.cviumnakesybhqiuwdij:doktergpt123@aws-1-ap-southeast-1.pooler.supabase.com:6543/postgres"
GSHEET_NAME = 'dokterGPT_Database'

# =====================================================================
# 2. THE SUPER GARBAGE SWEEPER (Cleans Hallucinations & Typos)
# =====================================================================
def run_garbage_sweeper():
    """Removes AI placeholder artifacts from Postgres AND Google Sheets."""
    print("\n🧹 Starting Super Garbage Sweeper...")
    
    # --- SCRUB POSTGRES (Backend) ---
    print("   Scrubbing Postgres Database...")
    try:
        conn = psycopg2.connect(DB_URL)
        cursor = conn.cursor()

        # Catch "Extraced", "Extracted", "Not specified", and blank AI artifacts
        garbage_sql = "generic_name ILIKE '%Not specified%' OR generic_name ILIKE '%Extrac%'"
        
        cursor.execute(f"""
            DELETE FROM paper_drugs 
            WHERE drug_id IN (SELECT drug_id FROM drugs_and_substances WHERE {garbage_sql});
        """)
        cursor.execute(f"DELETE FROM drugs_and_substances WHERE {garbage_sql};")
        
        cursor.execute("""
            DELETE FROM paper_icd 
            WHERE icd_code IN (SELECT icd_code FROM icd_codes WHERE disease_description ILIKE '%Not specified%');
        """)
        cursor.execute("DELETE FROM icd_codes WHERE disease_description ILIKE '%Not specified%';")

        conn.commit()
        conn.close()
        print("   ✅ Postgres is clean.")
    except Exception as e:
        print(f"   ❌ Postgres Error: {e}")

    # --- SCRUB GOOGLE SHEETS (Frontend) ---
    print("   Scrubbing Google Sheets (This takes a moment to respect API limits)...")
    try:
        gc = gspread.service_account(filename='credentials.json')
        sh = gc.open(GSHEET_NAME)
        
        # Scrub Drugs Sheet
        drug_sheet = sh.worksheet("drugs_and_substances")
        drug_records = drug_sheet.get_all_records()
        
        drug_rows_to_delete = [
            i + 2 for i, row in enumerate(drug_records) 
            if 'not specified' in str(row.get('generic_name', '')).lower() 
            or 'extrac' in str(row.get('generic_name', '')).lower()
        ]
        
        if drug_rows_to_delete:
            print(f"      Found {len(drug_rows_to_delete)} garbage drug rows. Deleting...")
            for row_idx in reversed(drug_rows_to_delete):
                drug_sheet.delete_rows(row_idx)
                print(f"         🗑️ Removed garbage drug at row {row_idx}")
                time.sleep(1.5) 

        # Scrub ICD Sheet
        icd_sheet = sh.worksheet("icd_codes")
        icd_records = icd_sheet.get_all_records()
        icd_rows_to_delete = [
            i + 2 for i, row in enumerate(icd_records) 
            if 'not specified' in str(row.get('disease_description', '')).lower()
        ]
        
        if icd_rows_to_delete:
            print(f"      Found {len(icd_rows_to_delete)} garbage ICD rows. Deleting...")
            for row_idx in reversed(icd_rows_to_delete):
                icd_sheet.delete_rows(row_idx)
                print(f"         🗑️ Removed garbage ICD code at row {row_idx}")
                time.sleep(1.5)

        print("   ✅ Google Sheets are clean.")

    except Exception as e:
        print(f"   ❌ GSheets Error: {e}")

    print("✨ Super Sweeper complete. All AI artifacts have been purged.\n")


# =====================================================================
# 3. THE ORPHAN SWEEPER (Hunts Disconnected Relationships)
# =====================================================================
def run_orphan_sweeper():
    """Finds and deletes drugs, authors, codes, etc. linked to a deleted paper_id."""
    print("\n👻 Starting Orphan Sweeper (Hunting disconnected relationships)...")
    
    # --- SCRUB POSTGRES ---
    try:
        conn = psycopg2.connect(DB_URL)
        cursor = conn.cursor()
        tables_to_clean = ["chunks", "clinical_pico", "paper_authors", "paper_drugs", "paper_icd", "paper_keywords"]
        total_deleted = 0
        
        for table in tables_to_clean:
            cursor.execute(f"DELETE FROM {table} WHERE paper_id NOT IN (SELECT paper_id FROM papers);")
            deleted_rows = cursor.rowcount
            total_deleted += deleted_rows
            if deleted_rows > 0: 
                print(f"      🗑️ Cleared {deleted_rows} orphaned rows from Postgres table: {table}.")
            
        conn.commit()
        conn.close()
        print("   ✅ Postgres orphaned sweep complete.")
    except Exception as e:
        print(f"   ❌ Postgres Error: {e}")

    # --- SCRUB GOOGLE SHEETS ---
    print("   Scrubbing Google Sheets for orphans (Respecting API limits)...")
    try:
        gc = gspread.service_account(filename='credentials.json')
        sh = gc.open(GSHEET_NAME)
        
        # Get all valid paper_ids from the main 'papers' sheet (Column 1)
        try:
            paper_sheet = sh.worksheet("papers")
            valid_papers = set(paper_sheet.col_values(1)[1:]) # skip header
        except Exception as e:
            print("   ❌ Could not fetch valid papers from main sheet. Aborting GSheets sweep.")
            return

        sheets_to_check = ["clinical_pico", "paper_authors", "paper_drugs", "paper_icd", "paper_keywords"]
        
        for sheet_name in sheets_to_check:
            try:
                sheet = sh.worksheet(sheet_name)
                records = sheet.get_all_records()
                
                # Find rows where paper_id is missing from the valid set
                rows_to_delete = [
                    i + 2 for i, row in enumerate(records) 
                    if row.get('paper_id') and str(row['paper_id']) not in valid_papers
                ]
                
                if rows_to_delete:
                    print(f"      Found {len(rows_to_delete)} orphans in '{sheet_name}'. Deleting...")
                    for row_idx in reversed(rows_to_delete):
                        sheet.delete_rows(row_idx)
                        print(f"         🗑️ Eliminated orphan at row {row_idx}")
                        time.sleep(1.5)
                    
            except gspread.exceptions.WorksheetNotFound:
                continue
                
        print("   ✅ Google Sheets orphan sweep complete.\n")
    except Exception as e:
        print(f"   ❌ GSheets Error: {e}")


# =====================================================================
# 4. THE SNIPER DELETE (Surgical Removal)
# =====================================================================
def sniper_delete_paper(target_paper_id, silent=False):
    """Deletes a single paper and all its relationships across everywhere."""
    if not silent: print(f"\n🎯 Sniper targeting paper: {target_paper_id}...")
    
    # 1. Delete Local Files
    for directory in [MD_DIR, JSON_DIR]:
        if os.path.exists(directory):
            for filename in os.listdir(directory):
                if target_paper_id in filename:
                    os.remove(os.path.join(directory, filename))
                    if not silent: print(f"      🗑️ Deleted local file: {filename}")

    # 2. Delete from Postgres
    try:
        conn = psycopg2.connect(DB_URL)
        cursor = conn.cursor()
        tables_to_scrub = [
            "chunks", "clinical_pico", "paper_authors", 
            "paper_drugs", "paper_icd", "paper_keywords", "papers"
        ]
        for table in tables_to_scrub:
            cursor.execute(f"DELETE FROM {table} WHERE paper_id = %s", (target_paper_id,))
        
        conn.commit()
        conn.close()
        if not silent: print("      🗑️ Deleted from Postgres.")
    except Exception as e:
        if not silent: print(f"      ❌ Postgres Error: {e}")

    # 3. Delete from Google Sheets (OMNISCIENT SNIPER)
    try:
        gc = gspread.service_account(filename='credentials.json')
        sh = gc.open(GSHEET_NAME)
        
        sheets_to_check = [
            "papers", "clinical_pico", "paper_authors", 
            "paper_drugs", "paper_icd", "paper_keywords"
        ]
        
        for sheet_name in sheets_to_check:
            try:
                sheet = sh.worksheet(sheet_name)
                cells = sheet.findall(target_paper_id)
                
                if cells:
                    rows_to_delete = sorted(list(set([cell.row for cell in cells])), reverse=True)
                    for row_idx in rows_to_delete:
                        sheet.delete_rows(row_idx)
                        time.sleep(1.5)
                    if not silent: 
                        print(f"      🗑️ Removed {len(rows_to_delete)} row(s) from GSheet tab: '{sheet_name}'.")
            
            except gspread.exceptions.WorksheetNotFound:
                continue

    except Exception as e:
        print(f"   ❌ GSheets Error on {target_paper_id}: {e}")

    if not silent: print(f"✅ Target {target_paper_id} successfully eliminated.\n")


# =====================================================================
# 5. THE ABSTRACT SWEEPER (Hunts Paywalled / Broken Papers)
# =====================================================================
def run_abstract_sweeper():
    """Finds and eliminates papers with truncated or paywalled abstracts."""
    print("\n🕵️ Scanning database for incomplete abstracts...")
    try:
        conn = psycopg2.connect(DB_URL)
        cursor = conn.cursor()

        cursor.execute("""
            SELECT paper_id, title FROM papers 
            WHERE LENGTH(abstract) < 600 
            OR abstract LIKE '%...' 
            OR abstract LIKE '%..' 
            OR abstract !~ '[.!?]\s*$';
        """)
        
        bad_papers = cursor.fetchall()
        conn.close()
    except Exception as e:
        print(f"❌ Database error during scan: {e}")
        return

    if not bad_papers:
        return print("✅ No incomplete abstracts found! Your database is pristine.\n")

    print(f"🚨 Found {len(bad_papers)} papers with incomplete abstracts:")
    for pid, title in bad_papers:
        print(f"   - [{pid}] {title[:60]}...")

    confirm = input(f"\nDo you want to permanently delete these {len(bad_papers)} papers? (YES/NO): ")
    
    if confirm == 'YES':
        print("\n🗑️ Commencing mass deletion (This might take a minute due to GSheets API limits)...")
        for i, (pid, _) in enumerate(bad_papers):
            print(f"   Eliminating {i+1}/{len(bad_papers)}: {pid}...")
            sniper_delete_paper(pid, silent=True)
            time.sleep(1.5) 
            
        print("✅ Abstract Sweep complete. All corrupted papers have been purged.\n")
    else:
        print("Abort. No papers were deleted.\n")


# =====================================================================
# 6. COMMAND LINE MENU
# =====================================================================
if __name__ == "__main__":
    while True:
        print("========================================")
        print(" 🧽 THE DOKTER-GPT DATA JANITOR 🧽 ")
        print("========================================")
        print("1: Run Garbage Sweeper (Clean AI artifacts like 'Not specified' & Typos)")
        print("2: Run Abstract Sweeper (Purge truncated/paywalled papers)")
        print("3: Run Orphan Sweeper (Delete disconnected relationships)")
        print("4: Sniper Delete (Manually eliminate a specific Paper ID)")
        print("0: Exit")
        
        choice = input("Select an option: ")
        
        if choice == '1':
            run_garbage_sweeper()
        elif choice == '2':
            run_abstract_sweeper()
        elif choice == '3':
            run_orphan_sweeper()
        elif choice == '4':
            target = input("Enter the EXACT paper_id (e.g., 38624108): ")
            sniper_delete_paper(target)
        elif choice == '0':
            print("Exiting Janitor. Goodbye!")
            break
        else:
            print("Invalid choice. Try again.\n")
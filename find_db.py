
import os
import sys

def find_cosmetic_db():
    """시스템에서 cosmetic.db 파일 찾기"""
    candidates = []
    
    # 1. 사용자 문서 폴더
    doc_folder = os.path.expanduser("~/Documents")
    if os.path.exists(doc_folder):
        for root, dirs, files in os.walk(doc_folder):
            if "cosmetic.db" in files:
                candidates.append(os.path.join(root, "cosmetic.db"))
    
    # 2. AppData 폴더
    appdata = os.getenv("APPDATA")
    if appdata and os.path.exists(appdata):
        cosrnd = os.path.join(appdata, "CosRnD")
        if os.path.exists(cosrnd):
            for root, dirs, files in os.walk(cosrnd):
                if "cosmetic.db" in files:
                    candidates.append(os.path.join(root, "cosmetic.db"))
    
    # 3. 바탕화면
    desktop = os.path.expanduser("~/Desktop")
    if os.path.exists(desktop):
        for root, dirs, files in os.walk(desktop):
            if "cosmetic.db" in files:
                candidates.append(os.path.join(root, "cosmetic.db"))
    
    # 4. 현재 폴더
    current = os.getcwd()
    for root, dirs, files in os.walk(current):
        if "cosmetic.db" in files:
            candidates.append(os.path.join(root, "cosmetic.db"))
    
    return candidates

# DB 파일 찾기
print("Finding cosmetic.db files...")
db_files = find_cosmetic_db()

if db_files:
    print(f"\nFound {len(db_files)} DB files:")
    for i, db_file in enumerate(db_files, 1):
        print(f"\n{i}. {db_file}")
        
        # DB 구조 확인
        try:
            import sqlite3
            conn = sqlite3.connect(db_file)
            cursor = conn.cursor()
            
            print("\n   clients table columns:")
            cursor.execute("PRAGMA table_info(clients)")
            for col in cursor.fetchall():
                print(f"   - {col[1]} ({col[2]})")
            
            print("\n   materials table columns:")
            cursor.execute("PRAGMA table_info(materials)")
            for col in cursor.fetchall():
                print(f"   - {col[1]} ({col[2]})")
            
            conn.close()
        except Exception as e:
            print(f"   Error: {e}")
else:
    print("\nNo DB files found!")

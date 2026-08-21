
import sqlite3
import os

db_path = r"C:\Users\neon5\AppData\Roaming\CosRnD\Data\cosmetic.db"

print(f"DB: {db_path}")

conn = sqlite3.connect(db_path)
cursor = conn.cursor()

print("=== 누락된 컬럼 추가 중... ===")

# 1. clients 테이블
print("\n1. clients 테이블...")
cursor.execute("PRAGMA table_info(clients)")
client_cols = [row[1] for row in cursor.fetchall()]
print(f"현재 컬럼: {client_cols}")

if 'name_en' not in client_cols:
    cursor.execute("ALTER TABLE clients ADD COLUMN name_en VARCHAR(100)")
    print("  OK: name_en 추가")
else:
    print("  OK: name_en 이미 있음")

if 'change_log' not in client_cols:
    cursor.execute("ALTER TABLE clients ADD COLUMN change_log TEXT")
    print("  OK: change_log 추가")
else:
    print("  OK: change_log 이미 있음")

# 2. materials 테이블
print("\n2. materials 테이블...")
cursor.execute("PRAGMA table_info(materials)")
mat_cols = [row[1] for row in cursor.fetchall()]
print(f"현재 컬럼: {mat_cols}")

if 'name_en' not in mat_cols:
    cursor.execute("ALTER TABLE materials ADD COLUMN name_en VARCHAR(255)")
    print("  OK: name_en 추가")
else:
    print("  OK: name_en 이미 있음")

if 'origin' not in mat_cols:
    cursor.execute("ALTER TABLE materials ADD COLUMN origin VARCHAR(100)")
    print("  OK: origin 추가")
else:
    print("  OK: origin 이미 있음")

if 'supplier_id' not in mat_cols:
    cursor.execute("ALTER TABLE materials ADD COLUMN supplier_id INTEGER")
    print("  OK: supplier_id 추가")
else:
    print("  OK: supplier_id 이미 있음")

if 'change_log' not in mat_cols:
    cursor.execute("ALTER TABLE materials ADD COLUMN change_log TEXT")
    print("  OK: change_log 추가")
else:
    print("  OK: change_log 이미 있음")

if 'updated_at' not in mat_cols:
    cursor.execute("ALTER TABLE materials ADD COLUMN updated_at DATETIME")
    print("  OK: updated_at 추가")
else:
    print("  OK: updated_at 이미 있음")

# materials.client_id -> supplier_id 복사
if 'client_id' in mat_cols and 'supplier_id' in mat_cols:
    try:
        cursor.execute("UPDATE materials SET supplier_id = client_id WHERE supplier_id IS NULL AND client_id IS NOT NULL")
        print("  OK: client_id -> supplier_id 데이터 복사")
    except Exception as e:
        print(f"  INFO: 데이터 복사 - {e}")

# 3. production_formulations 테이블
print("\n3. production_formulations 테이블...")
cursor.execute("PRAGMA table_info(production_formulations)")
prod_cols = [row[1] for row in cursor.fetchall()]
print(f"현재 컬럼: {prod_cols}")

if 'client_name' not in prod_cols:
    cursor.execute("ALTER TABLE production_formulations ADD COLUMN client_name TEXT")
    print("  OK: client_name 추가")
else:
    print("  OK: client_name 이미 있음")

if 'items_snapshot' not in prod_cols:
    cursor.execute("ALTER TABLE production_formulations ADD COLUMN items_snapshot TEXT")
    print("  OK: items_snapshot 추가")
else:
    print("  OK: items_snapshot 이미 있음")

# 4. formulations 테이블
print("\n4. formulations 테이블...")
cursor.execute("PRAGMA table_info(formulations)")
form_cols = [row[1] for row in cursor.fetchall()]
print(f"현재 컬럼: {form_cols}")

# 5. change_log 테이블 생성
print("\n5. change_log 테이블...")
cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='change_log'")
has_change_log = cursor.fetchone()
if not has_change_log:
    cursor.execute("""
        CREATE TABLE change_log (
            id INTEGER NOT NULL,
            table_name TEXT NOT NULL,
            operation TEXT NOT NULL,
            entity_id INTEGER,
            entity_name TEXT,
            changed_at TEXT NOT NULL,
            PRIMARY KEY (id)
        )
    """)
    print("  OK: change_log 테이블 생성")
else:
    print("  OK: change_log 테이블 이미 있음")

conn.commit()
conn.close()

print("\n=== 완료! 이제 프로그램을 실행하세요! ===")


import sqlite3
import os

# 가능한 모든 DB 경로 확인
db_paths = [
    r"C:\Users\neon5\Documents\RnD_데이터관리\data\cosmetic.db",
    r"C:\Users\neon5\Documents\CosRnD\Data\cosmetic.db",
    r"C:\Users\neon5\AppData\Roaming\CosRnD\Data\cosmetic.db",
    r"C:\Users\ace\Documents\CosRnD_data\cosmetic.db",
]

found_db = None

for db_path in db_paths:
    if os.path.exists(db_path):
        print(f"발견된 DB: {db_path}")
        found_db = db_path
        break

if not found_db:
    print("DB 파일을 찾을 수 없습니다!")
    print("아래 경로들을 확인해보세요:")
    for p in db_paths:
        print(f"  - {p}")
    exit(1)

print(f"\n사용할 DB: {found_db}")

try:
    conn = sqlite3.connect(found_db)
    cursor = conn.cursor()
    
    print("\n=== clients 테이블 현재 컬럼 ===")
    cursor.execute("PRAGMA table_info(clients)")
    cols = cursor.fetchall()
    client_cols = [c[1] for c in cols]
    for c in cols:
        print(f"  {c[1]}")
    
    print("\n=== materials 테이블 현재 컬럼 ===")
    cursor.execute("PRAGMA table_info(materials)")
    cols = cursor.fetchall()
    mat_cols = [c[1] for c in cols]
    for c in cols:
        print(f"  {c[1]}")
    
    print("\n=== 누락된 컬럼 추가 ===")
    
    # clients 테이블
    if 'name_en' not in client_cols:
        try:
            cursor.execute("ALTER TABLE clients ADD COLUMN name_en VARCHAR(100)")
            print("OK: clients.name_en 추가")
        except Exception as e:
            print(f"ERROR: clients.name_en - {e}")
    
    if 'change_log' not in client_cols:
        try:
            cursor.execute("ALTER TABLE clients ADD COLUMN change_log TEXT")
            print("OK: clients.change_log 추가")
        except Exception as e:
            print(f"ERROR: clients.change_log - {e}")
    
    # materials 테이블
    if 'name_en' not in mat_cols:
        try:
            cursor.execute("ALTER TABLE materials ADD COLUMN name_en VARCHAR(255)")
            print("OK: materials.name_en 추가")
        except Exception as e:
            print(f"ERROR: materials.name_en - {e}")
    
    if 'origin' not in mat_cols:
        try:
            cursor.execute("ALTER TABLE materials ADD COLUMN origin VARCHAR(100)")
            print("OK: materials.origin 추가")
        except Exception as e:
            print(f"ERROR: materials.origin - {e}")
    
    if 'supplier_id' not in mat_cols:
        try:
            cursor.execute("ALTER TABLE materials ADD COLUMN supplier_id INTEGER")
            print("OK: materials.supplier_id 추가")
        except Exception as e:
            print(f"ERROR: materials.supplier_id - {e}")
    
    if 'change_log' not in mat_cols:
        try:
            cursor.execute("ALTER TABLE materials ADD COLUMN change_log TEXT")
            print("OK: materials.change_log 추가")
        except Exception as e:
            print(f"ERROR: materials.change_log - {e}")
    
    if 'updated_at' not in mat_cols:
        try:
            cursor.execute("ALTER TABLE materials ADD COLUMN updated_at DATETIME")
            print("OK: materials.updated_at 추가")
        except Exception as e:
            print(f"ERROR: materials.updated_at - {e}")
    
    # client_id -> supplier_id 복사
    if 'client_id' in mat_cols and 'supplier_id' in mat_cols:
        try:
            cursor.execute("UPDATE materials SET supplier_id = client_id WHERE supplier_id IS NULL AND client_id IS NOT NULL")
            print("OK: client_id -> supplier_id 데이터 복사")
        except Exception as e:
            print(f"INFO: 데이터 복사 - {e}")
    
    conn.commit()
    
    print("\n=== 최종 확인 ===")
    cursor.execute("PRAGMA table_info(clients)")
    print("clients:", [c[1] for c in cursor.fetchall()])
    
    cursor.execute("PRAGMA table_info(materials)")
    print("materials:", [c[1] for c in cursor.fetchall()])
    
    conn.close()
    print("\n완료! 이제 프로그램을 실행하세요.")
    
except Exception as e:
    print(f"\n오류 발생: {e}")
    print("\n프로그램이 실행 중이면 먼저 종료해주세요!")

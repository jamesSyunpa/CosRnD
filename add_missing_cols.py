
import sqlite3
import os

db_path = r"C:\Users\neon5\AppData\Roaming\CosRnD\Data\cosmetic.db"

print(f"DB: {db_path}")

conn = sqlite3.connect(db_path)
cursor = conn.cursor()

print("\n=== production_formulations 테이블 ===")
cursor.execute("PRAGMA table_info(production_formulations)")
cols = [row[1] for row in cursor.fetchall()]
print(f"현재 컬럼: {cols}")

# client_name 컬럼 추가
if 'client_name' not in cols:
    try:
        cursor.execute("ALTER TABLE production_formulations ADD COLUMN client_name TEXT")
        print("OK: client_name 추가")
    except Exception as e:
        print(f"INFO: {e}")
else:
    print("OK: client_name 이미 존재")

# formulations 테이블에서 is_deleted 컬럼 확인 (혹시 문제가 있을까봐)
print("\n=== formulations 테이블 ===")
cursor.execute("PRAGMA table_info(formulations)")
cols_f = [row[1] for row in cursor.fetchall()]
print(f"현재 컬럼: {cols_f}")

conn.commit()
conn.close()

print("\n완료! 이제 프로그램을 실행하세요!")

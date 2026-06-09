
import sqlite3
import os
import shutil

# 원본 DB
old_db = r"C:\Users\neon5\Documents\RnD_데이터관리\data\cosmetic.db"
temp_db = r"C:\Users\neon5\Documents\RnD_데이터관리\data\cosmetic_temp.db"
backup_db = r"C:\Users\neon5\Documents\RnD_데이터관리\data\cosmetic_backup_{}.db".format(os.path.getmtime(old_db))

print(f"원본 DB: {old_db}")

# 1. 백업 생성
shutil.copy2(old_db, backup_db)
print(f"백업 완료: {backup_db}")

# 2. 임시 복사본 생성
shutil.copy2(old_db, temp_db)
print(f"임시 복사본 생성: {temp_db}")

# 3. 임시 DB에 컬럼 추가
conn = sqlite3.connect(temp_db)
cursor = conn.cursor()

print("\n=== 컬럼 추가 중... ===")

# clients 테이블
try:
    cursor.execute("ALTER TABLE clients ADD COLUMN name_en VARCHAR(100)")
    print("OK: clients.name_en")
except Exception as e:
    print(f"INFO: clients.name_en - {e}")

try:
    cursor.execute("ALTER TABLE clients ADD COLUMN change_log TEXT")
    print("OK: clients.change_log")
except Exception as e:
    print(f"INFO: clients.change_log - {e}")

# materials 테이블
try:
    cursor.execute("ALTER TABLE materials ADD COLUMN name_en VARCHAR(255)")
    print("OK: materials.name_en")
except Exception as e:
    print(f"INFO: materials.name_en - {e}")

try:
    cursor.execute("ALTER TABLE materials ADD COLUMN origin VARCHAR(100)")
    print("OK: materials.origin")
except Exception as e:
    print(f"INFO: materials.origin - {e}")

try:
    cursor.execute("ALTER TABLE materials ADD COLUMN supplier_id INTEGER")
    print("OK: materials.supplier_id")
except Exception as e:
    print(f"INFO: materials.supplier_id - {e}")

try:
    cursor.execute("ALTER TABLE materials ADD COLUMN change_log TEXT")
    print("OK: materials.change_log")
except Exception as e:
    print(f"INFO: materials.change_log - {e}")

try:
    cursor.execute("ALTER TABLE materials ADD COLUMN updated_at DATETIME")
    print("OK: materials.updated_at")
except Exception as e:
    print(f"INFO: materials.updated_at - {e}")

# 데이터 복사
try:
    cursor.execute("UPDATE materials SET supplier_id = client_id WHERE supplier_id IS NULL AND client_id IS NOT NULL")
    print("OK: client_id -> supplier_id 복사")
except Exception as e:
    print(f"INFO: 데이터 복사 - {e}")

conn.commit()

# 확인
print("\n=== 최종 확인 ===")
cursor.execute("PRAGMA table_info(clients)")
print("clients:", [c[1] for c in cursor.fetchall()])

cursor.execute("PRAGMA table_info(materials)")
print("materials:", [c[1] for c in cursor.fetchall()])

conn.close()

# 4. 원본 DB를 임시 DB로 교체
print("\n=== DB 교체 중... ===")
os.replace(temp_db, old_db)
print("OK: DB 교체 완료!")

print("\n=== 완료! 이제 프로그램을 실행하세요. ===")

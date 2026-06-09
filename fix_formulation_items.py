
import sqlite3
import os

db_path = r"C:\Users\neon5\Documents\RnD_데이터관리\data\cosmetic.db"
backup_path = r"C:\Users\neon5\Documents\RnD_데이터관리\data\cosmetic_backup_formulations.db"

print(f"DB: {db_path}")

# 백업
import shutil
shutil.copy2(db_path, backup_path)

conn = sqlite3.connect(db_path)
cursor = conn.cursor()

print("\n=== formulation_items 데이터 복구 ===")

# 백업 DB에서 데이터 가져오기
backup_conn = sqlite3.connect(backup_path.replace('cosmetic_backup_formulations.db', 'cosmetic_backup_1781000618.db'))
backup_cursor = backup_conn.cursor()

backup_cursor.execute("SELECT * FROM formulation_items")
rows = backup_cursor.fetchall()

backup_cursor.execute("PRAGMA table_info(formulation_items)")
backup_cols = [row[1] for row in backup_cursor.fetchall()]

print(f"백업 데이터: {len(rows)}행")
print(f"백업 컬럼: {backup_cols}")

# 새 DB에 삽입
if rows:
    # order는 SQL 키워드라서 따옴표로 감쌈
    cols_quoted = [f'"{col}"' if col == 'order' else col for col in backup_cols]
    placeholders = ', '.join(['?'] * len(backup_cols))
    cols_str = ', '.join(cols_quoted)
    
    cursor.executemany(
        f"INSERT INTO formulation_items ({cols_str}) VALUES ({placeholders})",
        rows
    )
    print(f"OK: {len(rows)}행 복구")

conn.commit()
backup_conn.close()
conn.close()

print("\n완료!")

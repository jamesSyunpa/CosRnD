
import os
import sqlite3

db_path = "C:/Users/neon5/AppData/Roaming/CosRnD/Data/cosmetic.db"

print("DB 경로:", db_path)
if not os.path.exists(db_path):
    print("DB 파일이 없음")
else:
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    print("\n--- production_formulations 테이블 구조 ---")
    cursor.execute("PRAGMA table_info(production_formulations)")
    for row in cursor.fetchall():
        print(row)
    
    print("\n--- production_runs 테이블 구조 ---")
    cursor.execute("PRAGMA table_info(production_runs)")
    for row in cursor.fetchall():
        print(row)
    
    # payment_room 컬럼이 production_formulations에 있는지 확인
    cursor.execute("PRAGMA table_info(production_formulations)")
    cols = [row[1] for row in cursor.fetchall()]
    if "payment_room" not in cols:
        print("\npayment_room 컬럼 추가 중...")
        cursor.execute("ALTER TABLE production_formulations ADD COLUMN payment_room VARCHAR(255)")
        conn.commit()
        print("추가 완료!")
    else:
        print("\npayment_room 컬럼이 이미 존재합니다.")
    
    # production_runs도 확인
    cursor.execute("PRAGMA table_info(production_runs)")
    cols_run = [row[1] for row in cursor.fetchall()]
    if "payment_room" not in cols_run:
        print("\nproduction_runs.payment_room 컬럼 추가 중...")
        cursor.execute("ALTER TABLE production_runs ADD COLUMN payment_room VARCHAR(255)")
        conn.commit()
        print("추가 완료!")
    else:
        print("\nproduction_runs.payment_room 컬럼이 이미 존재합니다.")
    
    conn.close()
    print("\n완료!")

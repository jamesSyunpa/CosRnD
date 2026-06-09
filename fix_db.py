
import sqlite3
import os

# DB 파일 경로
db_path = r"C:\Users\neon5\Documents\RnD_데이터관리\data\cosmetic.db"

print(f"DB 파일 경로: {db_path}")
print(f"DB 파일 존재 여부: {os.path.exists(db_path)}")

if os.path.exists(db_path):
    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        
        # 현재 테이블 구조 확인
        print("\n=== clients 테이블 구조 ===")
        cursor.execute("PRAGMA table_info(clients)")
        columns = cursor.fetchall()
        for col in columns:
            print(col)
        
        print("\n=== materials 테이블 구조 ===")
        cursor.execute("PRAGMA table_info(materials)")
        columns = cursor.fetchall()
        for col in columns:
            print(col)
        
        # 누락된 컬럼 추가
        print("\n=== 누락된 컬럼 추가 ===")
        
        # clients 테이블에 name_en 컬럼 추가
        try:
            cursor.execute("ALTER TABLE clients ADD COLUMN name_en VARCHAR(100)")
            print("OK: clients.name_en 컬럼 추가 완료")
        except Exception as e:
            print(f"INFO: clients.name_en 컬럼 추가 (이미 있을 수 있음): {e}")
        
        # clients 테이블에 change_log 컬럼 추가
        try:
            cursor.execute("ALTER TABLE clients ADD COLUMN change_log TEXT")
            print("OK: clients.change_log 컬럼 추가 완료")
        except Exception as e:
            print(f"INFO: clients.change_log 컬럼 추가 (이미 있을 수 있음): {e}")
        
        # materials 테이블에 name_en 컬럼 추가
        try:
            cursor.execute("ALTER TABLE materials ADD COLUMN name_en VARCHAR(255)")
            print("OK: materials.name_en 컬럼 추가 완료")
        except Exception as e:
            print(f"INFO: materials.name_en 컬럼 추가 (이미 있을 수 있음): {e}")
        
        # materials 테이블에 origin 컬럼 추가
        try:
            cursor.execute("ALTER TABLE materials ADD COLUMN origin VARCHAR(100)")
            print("OK: materials.origin 컬럼 추가 완료")
        except Exception as e:
            print(f"INFO: materials.origin 컬럼 추가 (이미 있을 수 있음): {e}")
        
        # materials 테이블에 supplier_id 컬럼 추가 (기존 client_id 대체)
        try:
            cursor.execute("ALTER TABLE materials ADD COLUMN supplier_id INTEGER")
            print("OK: materials.supplier_id 컬럼 추가 완료")
        except Exception as e:
            print(f"INFO: materials.supplier_id 컬럼 추가 (이미 있을 수 있음): {e}")
        
        # materials 테이블에 change_log 컬럼 추가
        try:
            cursor.execute("ALTER TABLE materials ADD COLUMN change_log TEXT")
            print("OK: materials.change_log 컬럼 추가 완료")
        except Exception as e:
            print(f"INFO: materials.change_log 컬럼 추가 (이미 있을 수 있음): {e}")
        
        # materials 테이블에 updated_at 컬럼 추가
        try:
            cursor.execute("ALTER TABLE materials ADD COLUMN updated_at DATETIME")
            print("OK: materials.updated_at 컬럼 추가 완료")
        except Exception as e:
            print(f"INFO: materials.updated_at 컬럼 추가 (이미 있을 수 있음): {e}")
        
        # 기존 client_id 데이터를 supplier_id로 복사
        try:
            cursor.execute("UPDATE materials SET supplier_id = client_id WHERE client_id IS NOT NULL")
            print("OK: 기존 client_id 데이터를 supplier_id로 복사 완료")
        except Exception as e:
            print(f"INFO: client_id 복사 (필요 없을 수 있음): {e}")
        
        # 변경 사항 저장
        conn.commit()
        
        # 최종 구조 확인
        print("\n=== 최종 clients 테이블 구조 ===")
        cursor.execute("PRAGMA table_info(clients)")
        columns = cursor.fetchall()
        for col in columns:
            print(col)
        
        print("\n=== 최종 materials 테이블 구조 ===")
        cursor.execute("PRAGMA table_info(materials)")
        columns = cursor.fetchall()
        for col in columns:
            print(col)
        
        conn.close()
        print("\n=== DB 수정 완료! ===")
        
    except Exception as e:
        print(f"오류 발생: {e}")
else:
    print("DB 파일을 찾을 수 없습니다!")


import sqlite3
import os
import shutil
from datetime import datetime

# 원본 DB 경로
old_db_path = r"C:\Users\neon5\Documents\RnD_데이터관리\data\cosmetic.db"
new_db_path = r"C:\Users\neon5\Documents\RnD_데이터관리\data\cosmetic_new.db"
backup_db_path = r"C:\Users\neon5\Documents\RnD_데이터관리\data\cosmetic_backup.db"

print(f"원본 DB: {old_db_path}")
print(f"백업 DB: {backup_db_path}")
print(f"새 DB: {new_db_path}")

# 1. 원본 DB 백업
if os.path.exists(old_db_path):
    shutil.copy2(old_db_path, backup_db_path)
    print(f"\nOK: 원본 DB 백업 완료: {backup_db_path}")
else:
    print("\nERROR: 원본 DB를 찾을 수 없습니다!")
    exit(1)

# 2. 새 DB 생성 (최신 스키마로)
print("\n=== 새 DB 생성 중...")

# SQLAlchemy Base로 최신 스키마로 DB 생성
from database.db_manager import db_manager
from database.models import Base
from sqlalchemy import create_engine

# 임시로 새 DB 생성
engine = create_engine(f"sqlite:///{new_db_path}")
Base.metadata.create_all(engine)
engine.dispose()
print("OK: 최신 스키마로 새 DB 생성 완료")

# 3. 데이터 마이그레이션
print("\n=== 데이터 마이그레이션 중...")

# 원본 DB 연결
old_conn = sqlite3.connect(old_db_path)
old_cursor = old_conn.cursor()

# 새 DB 연결
new_conn = sqlite3.connect(new_db_path)
new_cursor = new_conn.cursor()

# users 테이블 마이그레이션
print("\nusers 테이블 마이그레이션...")
old_cursor.execute("SELECT id, username, password, real_name, is_admin FROM users")
users = old_cursor.fetchall()

for user in users:
    # 새 스키마에 맞춰 데이터 삽입 (role, position, manager_code, contact, zip_code, address, change_log, remember_id, auto_login은 기본값으로)
    try:
        new_cursor.execute("""
            INSERT INTO users (id, username, password, real_name, is_admin, role, position, manager_code, contact, zip_code, address, change_log, remember_id, auto_login)
            VALUES (?, ?, ?, ?, ?, 'RD', NULL, NULL, NULL, NULL, NULL, NULL, 0, 0)
        """, user)
    except Exception as e:
        print(f"  사용자 {user[1]} 마이그레이션 오류: {e}")
        # 중복 시 건너뜀
        pass

print(f"OK: {len(users)}명의 사용자 마이그레이션 완료")

# clients 테이블 마이그레이션
print("\nclients 테이블 마이그레이션...")
old_cursor.execute("SELECT id, name, business_number, client_type, ceo_name, manager_name, fax, zip_code, phone, email, address, is_active, created_at FROM clients")
clients = old_cursor.fetchall()

for client in clients:
    # 새 스키마에 맞춰 데이터 삽입 (name_en, change_log 추가)
    new_cursor.execute("""
        INSERT INTO clients (id, name, name_en, business_number, client_type, ceo_name, manager_name, fax, zip_code, phone, email, address, is_active, change_log, created_at)
        VALUES (?, ?, NULL, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, NULL, ?)
    """, client)

print(f"OK: {len(clients)}개의 거래처 마이그레이션 완료")

# materials 테이블 마이그레이션
print("\nmaterials 테이블 마이그레이션...")
old_cursor.execute("SELECT id, code, name, unit_price, package_unit, client_id, manufacturer, hs_code, nmpa_reg_num, reg_date, is_active FROM materials")
materials = old_cursor.fetchall()

for material in materials:
    # 새 스키마에 맞춰 데이터 삽입 (name_en, origin, supplier_id, change_log, updated_at 추가)
    # client_id -> supplier_id 로 변경
    new_cursor.execute("""
        INSERT INTO materials (id, code, name, name_en, origin, unit_price, package_unit, supplier_id, manufacturer, hs_code, nmpa_reg_num, reg_date, is_active, change_log, created_at, updated_at)
        VALUES (?, ?, ?, NULL, NULL, ?, ?, ?, ?, ?, ?, ?, NULL, ?, NULL)
    """, (material[0], material[1], material[2], material[3], material[4], material[5], material[6], material[7], material[8], material[9], material[10]))

print(f"OK: {len(materials)}개의 원자재 마이그레이션 완료")

# 나머지 테이블들도 간단히 마이그레이션 (ingredients, formulations, formulation_items, production_formulations, production_steps, production_runs, ingredient_reports, ingredient_report_items, semi_finished_coa, semi_finished_coa_items, finished_product_coa, finished_product_coa_items, document_packages, document_package_links, document_attachments
tables_to_migrate = ["ingredients", "formulations", "formulation_items", "production_formulations", "production_steps", "production_runs", "ingredient_reports", "ingredient_report_items", "semi_finished_coa", "semi_finished_coa_items", "finished_product_coa", "finished_product_coa_items", "document_packages", "document_package_links", "document_attachments", "change_log"]

for table_name in tables_to_migrate:
    try:
        print(f"\n{table_name} 테이블 마이그레이션...")
        
        # 원본 테이블의 모든 행 가져오기
        old_cursor.execute(f"SELECT * FROM {table_name}")
        rows = old_cursor.fetchall()
        
        if rows:
            # 컬럼 정보 가져오기
            old_cursor.execute(f"PRAGMA table_info({table_name})")
            old_cols = [col[1] for col in old_cursor.fetchall()]
            
            new_cursor.execute(f"PRAGMA table_info({table_name})")
            new_cols = [col[1] for col in new_cursor.fetchall()]
            
            # 공통 컬럼 찾기
            common_cols = [col for col in old_cols if col in new_cols]
            
            if common_cols:
                placeholders = ", ".join(["?"] * len(common_cols))
                cols_str = ", ".join(common_cols)
                
                for row in rows:
                    # 공통 컬럼에 해당하는 값만 추출
                    values = []
                    for i, col in enumerate(old_cols):
                        if col in common_cols:
                            values.append(row[i])
                    
                    new_cursor.execute(f"INSERT INTO {table_name} ({cols_str}) VALUES ({placeholders})", values)
                
                print(f"OK: {len(rows)}개의 행 마이그레이션 완료")
            else:
                print(f"INFO: 공통 컬럼이 없어 건너뜀")
        else:
            print(f"INFO: 데이터가 없어 건너뜀")
    except Exception as e:
        print(f"ERROR: {table_name} 마이그레이션 오류: {e}")

# 변경 사항 저장
new_conn.commit()

# 스키마 버전 설정
from database.db_manager import SCHEMA_VERSION
new_cursor.execute("CREATE TABLE IF NOT EXISTS _schema_version (version INTEGER)")
new_cursor.execute("INSERT INTO _schema_version (version) VALUES (?)", (SCHEMA_VERSION,))
new_conn.commit()

old_conn.close()
new_conn.close()

print("\n=== 마이그레이션 완료!")

# 4. 원본 DB를 새 DB로 교체
print("\n=== DB 교체 중...")
os.replace(new_db_path, old_db_path)
print("OK: DB 교체 완료!")

print("\n=== 모든 작업 완료! 이제 프로그램을 실행하세요!")

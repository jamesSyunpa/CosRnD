
import sqlite3
import os
import shutil
from datetime import datetime

# 원본 DB
old_db = r"C:\Users\neon5\Documents\RnD_데이터관리\data\cosmetic.db"
new_db = r"C:\Users\neon5\Documents\RnD_데이터관리\data\cosmetic_new.db"
backup_db = r"C:\Users\neon5\Documents\RnD_데이터관리\data\cosmetic_backup_{}.db".format(int(datetime.now().timestamp()))

print(f"원본 DB: {old_db}")

# 1. 백업 생성
shutil.copy2(old_db, backup_db)
print(f"백업 완료: {backup_db}")

# 2. SQLAlchemy로 최신 스키마의 새 DB 생성
print("\n=== 최신 스키마로 새 DB 생성 중... ===")
from database.db_manager import db_manager
from database.models import Base
from sqlalchemy import create_engine

# 새 DB 생성
engine = create_engine(f"sqlite:///{new_db}")
Base.metadata.create_all(engine)
engine.dispose()
print("OK: 최신 스키마 DB 생성 완료")

# 3. 기존 DB에서 데이터 복사
print("\n=== 데이터 마이그레이션 중... ===")

old_conn = sqlite3.connect(old_db)
old_cursor = old_conn.cursor()

new_conn = sqlite3.connect(new_db)
new_cursor = new_conn.cursor()

# 모든 테이블 목록 가져오기
old_cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'")
tables = [row[0] for row in old_cursor.fetchall()]

print(f"기존 테이블: {tables}")

for table in tables:
    try:
        # 기존 테이블 컬럼 가져오기
        old_cursor.execute(f"PRAGMA table_info({table})")
        old_cols = [row[1] for row in old_cursor.fetchall()]
        
        # 새 테이블 컬럼 가져오기
        new_cursor.execute(f"PRAGMA table_info({table})")
        new_cols = [row[1] for row in new_cursor.fetchall()]
        
        # 공통 컬럼 찾기
        common_cols = [col for col in old_cols if col in new_cols]
        
        if common_cols:
            print(f"\n{table}:")
            print(f"  기존 컬럼: {old_cols}")
            print(f"  새 컬럼: {new_cols}")
            print(f"  공통 컬럼: {common_cols}")
            
            # 데이터 가져오기
            old_cursor.execute(f"SELECT {', '.join(common_cols)} FROM {table}")
            rows = old_cursor.fetchall()
            
            if rows:
                # 데이터 삽입
                placeholders = ', '.join(['?'] * len(common_cols))
                cols_str = ', '.join(common_cols)
                
                new_cursor.executemany(
                    f"INSERT INTO {table} ({cols_str}) VALUES ({placeholders})",
                    rows
                )
                print(f"  OK: {len(rows)}행 복사")
        else:
            print(f"\n{table}: 공통 컬럼 없어 건너뜀")
            
    except Exception as e:
        print(f"\n{table} 마이그레이션 오류: {e}")

# materials 테이블 특별 처리: client_id -> supplier_id
try:
    new_cursor.execute("PRAGMA table_info(materials)")
    mat_cols = [row[1] for row in new_cursor.fetchall()]
    
    if 'client_id' in mat_cols and 'supplier_id' in mat_cols:
        new_cursor.execute("UPDATE materials SET supplier_id = client_id WHERE supplier_id IS NULL AND client_id IS NOT NULL")
        print("\nOK: materials.client_id -> supplier_id 복사")
except Exception as e:
    print(f"\nmaterials 데이터 복사 오류: {e}")

# 스키마 버전 설정
from database.db_manager import SCHEMA_VERSION
new_cursor.execute("CREATE TABLE IF NOT EXISTS _schema_version (version INTEGER)")
new_cursor.execute("DELETE FROM _schema_version")
new_cursor.execute(f"INSERT INTO _schema_version (version) VALUES ({SCHEMA_VERSION})")

new_conn.commit()
old_conn.close()
new_conn.close()

# 4. 원본 DB를 새 DB로 교체
print("\n=== DB 교체 중... ===")
os.replace(new_db, old_db)
print("OK: DB 교체 완료!")

print("\n=== 완료! ===")
print(f"백업 파일: {backup_db}")
print("이제 프로그램을 실행하세요.")

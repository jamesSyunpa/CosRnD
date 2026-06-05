"""
기존 DB에 role 컬럼을 추가하는 마이그레이션 스크립트
"""
import sqlite3
import os

# DB 경로 설정
db_path = os.path.join(os.path.dirname(__file__), 'data', 'cosmetic.db')

if not os.path.exists(db_path):
    print(f"DB 파일을 찾을 수 없습니다: {db_path}")
    exit(1)

print(f"DB 경로: {db_path}")
print("마이그레이션 시작...")

conn = sqlite3.connect(db_path)
cursor = conn.cursor()

try:
    # role 컬럼 존재 여부 확인
    cursor.execute("PRAGMA table_info(users)")
    columns = [column[1] for column in cursor.fetchall()]
    
    if 'role' not in columns:
        print("role 컬럼 추가 중...")
        
        # role 컬럼 추가
        cursor.execute("ALTER TABLE users ADD COLUMN role TEXT DEFAULT 'RD'")
        
        # 기존 is_admin=True인 사용자는 MSAD로 설정
        cursor.execute("UPDATE users SET role = 'MSAD' WHERE is_admin = 1")
        
        # 기존 is_admin=False인 사용자는 RD로 설정 (이미 기본값)
        cursor.execute("UPDATE users SET role = 'RD' WHERE is_admin = 0 OR is_admin IS NULL")
        
        conn.commit()
        print("✓ role 컬럼 추가 완료")
        
        # 결과 확인
        cursor.execute("SELECT username, is_admin, role FROM users")
        users = cursor.fetchall()
        print("\n현재 사용자 목록:")
        for username, is_admin, role in users:
            print(f"  - {username}: is_admin={is_admin}, role={role}")
    else:
        print("✓ role 컬럼이 이미 존재합니다.")
    
    print("\n마이그레이션 완료!")
    
except Exception as e:
    print(f"오류 발생: {e}")
    conn.rollback()
finally:
    conn.close()

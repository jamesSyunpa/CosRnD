# migrate_add_real_name.py
"""
기존 사용자 테이블에 real_name 필드를 추가하고 기본값을 설정하는 마이그레이션 스크립트
"""

import os
import sys
from sqlalchemy import text
from database.db_manager import db_manager
from database.models import User

def migrate_add_real_name():
    """User 테이블에 real_name 컬럼을 추가하고 기존 사용자들에게 기본값을 설정합니다."""
    
    print("=== 사용자 테이블 real_name 필드 추가 마이그레이션 시작 ===")
    
    # 데이터베이스 설정
    current_dir = os.path.dirname(os.path.abspath(__file__))
    db_manager.setup_database(current_dir, os.path.join(current_dir, 'config.ini'))
    
    session = db_manager.get_session()
    try:
        # 1. real_name 컬럼이 이미 존재하는지 확인
        try:
            result = session.execute(text("SELECT real_name FROM users LIMIT 1"))
            print("  * real_name 컬럼이 이미 존재합니다.")
            column_exists = True
        except Exception:
            print("  * real_name 컬럼이 존재하지 않습니다. 추가를 진행합니다.")
            column_exists = False
        
        # 2. 컬럼이 존재하지 않으면 추가
        if not column_exists:
            try:
                session.execute(text("ALTER TABLE users ADD COLUMN real_name VARCHAR(50)"))
                session.commit()
                print("  * real_name 컬럼 추가 완료")
            except Exception as e:
                print(f"  * 컬럼 추가 실패: {e}")
                session.rollback()
                return False
        
        # 3. 기존 사용자들의 real_name이 비어있으면 username으로 설정
        users = session.query(User).all()
        updated_count = 0
        
        for user in users:
            if not user.real_name or user.real_name.strip() == "":
                user.real_name = user.username  # 기본값으로 사용자 ID 사용
                updated_count += 1
                print(f"  * 사용자 '{user.username}'의 실명을 '{user.username}'으로 설정")
        
        if updated_count > 0:
            session.commit()
            print(f"  * {updated_count}명의 사용자 실명 기본값 설정 완료")
        else:
            print("  * 업데이트할 사용자 없음")
        
        print("=== 마이그레이션 완료 ===")
        return True
        
    except Exception as e:
        session.rollback()
        print(f"  * 마이그레이션 실패: {e}")
        return False
    finally:
        session.close()

if __name__ == "__main__":
    success = migrate_add_real_name()
    if success:
        print("\n마이그레이션이 성공적으로 완료되었습니다.")
    else:
        print("\n마이그레이션 중 오류가 발생했습니다.")
        sys.exit(1)
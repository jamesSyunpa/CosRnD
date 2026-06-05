#!/usr/bin/env python3
"""
manager_code 필드의 빈 문자열을 NULL로 변환하는 마이그레이션
UNIQUE 제약조건 오류 해결을 위한 스크립트
"""

import os
import sys
import configparser
from pathlib import Path

# 현재 디렉토리를 Python path에 추가
sys.path.append(os.getcwd())

from database.db_manager import DBManager
from database.models import User

def migrate_manager_code():
    """빈 문자열로 된 manager_code를 NULL로 변경"""
    print("=== manager_code 마이그레이션 시작 ===")
    
    # 데이터베이스 연결
    db = DBManager()
    current_dir = os.getcwd()
    config_path = os.path.join(current_dir, 'config.ini')
    
    try:
        db.setup_database(current_dir, config_path)
        session = db.Session()
        
        # 빈 문자열로 된 manager_code 찾기
        users_with_empty_code = session.query(User).filter(User.manager_code == '').all()
        
        print(f"빈 문자열 manager_code를 가진 사용자 수: {len(users_with_empty_code)}")
        
        for user in users_with_empty_code:
            print(f"사용자 '{user.username}' (ID: {user.id})의 manager_code를 NULL로 변경")
            user.manager_code = None
        
        # 변경사항 저장
        session.commit()
        print("✅ 마이그레이션 완료")
        
        # 결과 확인
        null_count = session.query(User).filter(User.manager_code.is_(None)).count()
        empty_count = session.query(User).filter(User.manager_code == '').count()
        non_empty_count = session.query(User).filter(
            User.manager_code.isnot(None) & (User.manager_code != '')
        ).count()
        
        print(f"\n=== 마이그레이션 결과 ===")
        print(f"NULL manager_code: {null_count}개")
        print(f"빈 문자열 manager_code: {empty_count}개")
        print(f"값이 있는 manager_code: {non_empty_count}개")
        
    except Exception as e:
        session.rollback()
        print(f"❌ 마이그레이션 실패: {e}")
        import traceback
        traceback.print_exc()
    finally:
        session.close()

if __name__ == "__main__":
    migrate_manager_code()
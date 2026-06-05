#!/usr/bin/env python3
"""
처방 테이블의 manager_name 필드에서 ID를 실명으로 변환하는 마이그레이션
기존 처방에서 담당자가 ID로 저장된 경우 실명으로 변환
"""

import os
import sys
import configparser
from pathlib import Path

# 현재 디렉토리를 Python path에 추가
sys.path.append(os.getcwd())

from database.db_manager import DBManager
from database.models import User, Formulation

def migrate_formulation_manager_names():
    """처방 테이블의 manager_name에서 ID를 실명으로 변환"""
    print("=== 처방 담당자 이름 마이그레이션 시작 ===")
    
    # 데이터베이스 연결
    db = DBManager()
    current_dir = os.getcwd()
    config_path = os.path.join(current_dir, 'config.ini')
    
    try:
        db.setup_database(current_dir, config_path)
        session = db.Session()
        
        # 모든 처방 조회
        formulations = session.query(Formulation).all()
        print(f"총 처방 수: {len(formulations)}")
        
        # 모든 사용자 정보를 미리 로드 (성능 향상)
        users = session.query(User).all()
        user_map = {}
        for user in users:
            # real_name이 있고 username과 다르면 real_name 사용, 그렇지 않으면 변환하지 않음
            real_name = user.real_name if user.real_name and user.real_name != user.username else None
            if real_name:
                user_map[str(user.id)] = real_name
                user_map[user.username] = real_name
        
        updated_count = 0
        
        for formulation in formulations:
            if formulation.manager_name:
                manager_name = formulation.manager_name.strip()
                
                # 숫자로만 이루어진 경우 ID로 판단
                if manager_name.isdigit():
                    real_name = user_map.get(manager_name)
                    if real_name and real_name != manager_name:
                        print(f"처방 ID {formulation.id}: '{manager_name}' → '{real_name}'")
                        formulation.manager_name = real_name
                        updated_count += 1
                    else:
                        print(f"처방 ID {formulation.id}: 사용자 ID '{manager_name}'에 대한 실명을 찾을 수 없음")
                # username인 경우도 실명으로 변환
                elif manager_name in user_map and user_map[manager_name] != manager_name:
                    real_name = user_map[manager_name]
                    print(f"처방 ID {formulation.id}: '{manager_name}' → '{real_name}'")
                    formulation.manager_name = real_name
                    updated_count += 1
        
        # 변경사항 저장
        if updated_count > 0:
            session.commit()
            print(f"✅ 마이그레이션 완료: {updated_count}개 처방의 담당자명을 업데이트했습니다.")
        else:
            print("✅ 업데이트할 처방이 없습니다.")
        
        # 결과 확인
        numeric_count = 0
        real_name_count = 0
        empty_count = 0
        
        # 변경사항 반영을 위해 세션 새로고침
        for formulation in session.query(Formulation).all():
            if not formulation.manager_name:
                empty_count += 1
            elif formulation.manager_name.isdigit():
                numeric_count += 1
            else:
                real_name_count += 1
        
        print(f"\n=== 마이그레이션 결과 ===")
        print(f"실명으로 저장된 처방: {real_name_count}개")
        print(f"ID로 저장된 처방: {numeric_count}개")
        print(f"담당자명이 없는 처방: {empty_count}개")
        
    except Exception as e:
        session.rollback()
        print(f"❌ 마이그레이션 실패: {e}")
        import traceback
        traceback.print_exc()
    finally:
        session.close()

if __name__ == "__main__":
    migrate_formulation_manager_names()
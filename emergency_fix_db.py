import sqlite3
import configparser
import os
import sys

def fix_database():
    print("=== 데이터베이스 긴급 복구 도구 ===")
    
    # 1. config.ini에서 경로 읽기
    config_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'config.ini')
    if not os.path.exists(config_path):
        print(f"[오류] 설정 파일을 찾을 수 없습니다: {config_path}")
        return False

    config = configparser.ConfigParser()
    config.read(config_path, encoding='utf-8')
    
    shared_db_path = config.get('Paths', 'shared_db_path', fallback=None)
    if not shared_db_path:
        print("[오류] 공유 DB 경로가 설정되어 있지 않습니다.")
        return False
        
    # 경로 정규화 (db_manager.py 로직과 동일)
    path = shared_db_path.split('#')[0].strip().strip('"').strip("'")
    if path.lower().endswith('.db') or os.path.basename(path).lower() == 'cosmetic.db':
        db_file = path
    else:
        db_file = os.path.join(path, 'cosmetic.db')
        
    db_file = os.path.normpath(db_file)
    print(f"[정보] 대상 데이터베이스 파일: {db_file}")
    
    if not os.path.exists(db_file):
        print(f"[오류] 데이터베이스 파일이 존재하지 않습니다: {db_file}")
        # 디렉토리 내용 확인
        dir_path = os.path.dirname(db_file)
        if os.path.exists(dir_path):
            print(f"[정보] 폴더 내용 ({dir_path}):")
            try:
                for f in os.listdir(dir_path):
                    print(f"  - {f}")
            except Exception as e:
                print(f"  (목록 조회 실패: {e})")
        return False
        
    # 2. SQLite 연결 및 컬럼 추가
    import shutil
    import time
    
    try:
        file_size = os.path.getsize(db_file)
        print(f"[정보] 파일 크기: {file_size} bytes")
        
        # 임시 파일로 복사 시도
        temp_db_file = "temp_fix_cosmetic.db"
        print(f"[정보] 임시 파일로 복사 중... ({temp_db_file})")
        shutil.copy2(db_file, temp_db_file)
        
        print("[정보] 임시 파일 패치 시작...")
        conn = sqlite3.connect(temp_db_file)
        cursor = conn.cursor()
        
        # formulations 테이블 확인
        print(">> formulations 테이블 점검 중...")
        cursor.execute("PRAGMA table_info(formulations)")
        columns = [info[1] for info in cursor.fetchall()]
        
        if 'manufacturing_date' in columns:
            print("  - manufacturing_date 컬럼: 이미 존재함 (OK)")
        else:
            print("  - manufacturing_date 컬럼: 누락됨 -> 추가 시도...")
            cursor.execute("ALTER TABLE formulations ADD COLUMN manufacturing_date VARCHAR(20)")
            print("  - 컬럼 추가 완료")
            
        # production_runs 테이블 확인
        print(">> production_runs 테이블 점검 중...")
        cursor.execute("PRAGMA table_info(production_runs)")
        columns = [info[1] for info in cursor.fetchall()]
        
        if 'production_date' in columns:
            print("  - production_date 컬럼: 이미 존재함 (OK)")
        else:
            print("  - production_date 컬럼: 누락됨 -> 추가 시도...")
            cursor.execute("ALTER TABLE production_runs ADD COLUMN production_date DATE")
            print("  - 컬럼 추가 완료")
            
        conn.commit()
        conn.close()
        
        print("[정보] 패치된 파일을 원본 위치로 덮어쓰기 시도...")
        # 원본 백업
        backup_file = db_file + f".bak_{int(time.time())}"
        shutil.move(db_file, backup_file)
        print(f"  - 원본 백업 완료: {backup_file}")
        
        shutil.move(temp_db_file, db_file)
        print("\n[성공] 데이터베이스 패치가 완료되었습니다.")
        return True
        
    except Exception as e:
        print(f"\n[오류] 데이터베이스 수정 중 오류 발생: {e}")
        return False

if __name__ == "__main__":
    if fix_database():
        print("프로그램을 다시 실행해주세요.")
    else:
        print("복구에 실패했습니다. 관리자에게 문의하세요.")

"""
마이그레이션: formulations 테이블에 is_deleted 컬럼 추가
실행: python migrate_add_is_deleted.py [db_file_path]
"""
import sqlite3
import os
import sys
import configparser

def get_shared_db_path():
    """config.ini에서 공유 DB 경로를 가져옵니다."""
    config_path = os.path.join(os.path.dirname(__file__), 'config.ini')
    
    if not os.path.exists(config_path):
        return None
    
    try:
        config = configparser.ConfigParser(interpolation=None)
        config.read(config_path, encoding='utf-8')
        
        # shared_db_path 또는 database_dir 확인
        db_dir = config.get('Paths', 'shared_db_path', fallback=None)
        if not db_dir:
            db_dir = config.get('Paths', 'database_dir', fallback=None)
        
        if db_dir and os.path.exists(db_dir):
            db_file = os.path.join(db_dir, 'cosmetic.db')
            if os.path.exists(db_file):
                return db_file
    except Exception as e:
        print(f"⚠️ config.ini 읽기 실패: {e}")
    
    return None

def migrate(db_path):
    """formulations 테이블에 is_deleted 컬럼을 추가합니다."""
    
    if not os.path.exists(db_path):
        print(f"❌ 데이터베이스 파일을 찾을 수 없습니다: {db_path}")
        return False
    
    print(f"📂 DB 경로: {db_path}")
    
    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        
        # 1. is_deleted 컬럼이 이미 있는지 확인
        cursor.execute("PRAGMA table_info(formulations)")
        columns = [row[1] for row in cursor.fetchall()]
        
        if 'is_deleted' in columns:
            print("✅ is_deleted 컬럼이 이미 존재합니다.")
            conn.close()
            return True
        
        # 2. is_deleted 컬럼 추가 (기본값 False = 0)
        print("➕ is_deleted 컬럼 추가 중...")
        cursor.execute("""
            ALTER TABLE formulations 
            ADD COLUMN is_deleted INTEGER DEFAULT 0
        """)
        
        conn.commit()
        print("✅ is_deleted 컬럼이 추가되었습니다.")
        
        # 3. 확인
        cursor.execute("PRAGMA table_info(formulations)")
        columns = [row[1] for row in cursor.fetchall()]
        print(f"📋 현재 컬럼 목록: {', '.join(columns)}")
        
        conn.close()
        return True
        
    except Exception as e:
        print(f"❌ 마이그레이션 실패: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    print("=" * 60)
    print("마이그레이션: formulations.is_deleted 컬럼 추가")
    print("=" * 60)
    
    # 명령줄 인자로 DB 경로가 제공된 경우
    if len(sys.argv) > 1:
        db_paths = [sys.argv[1]]
    else:
        # 기본: 공유 DB와 로컬 DB 모두 마이그레이션
        db_paths = []
        
        # 1. 공유 DB (config.ini에서 읽기)
        shared_db = get_shared_db_path()
        if shared_db:
            db_paths.append(shared_db)
            print(f"✓ 공유 DB 발견: {shared_db}")
        
        # 2. 로컬 DB (AppData)
        appdata_path = os.path.join(os.environ.get('APPDATA', ''), 'CoRQD')
        local_db = os.path.join(appdata_path, '.cosdb')
        if os.path.exists(local_db):
            db_paths.append(local_db)
            print(f"✓ 로컬 DB 발견: {local_db}")
        
        if not db_paths:
            print("❌ 마이그레이션할 DB 파일을 찾을 수 없습니다.")
            sys.exit(1)
    
    print(f"\n📋 총 {len(db_paths)}개 DB 파일을 마이그레이션합니다.\n")
    
    success_count = 0
    for db_path in db_paths:
        print(f"\n{'='*60}")
        if migrate(db_path):
            success_count += 1
    
    print(f"\n{'='*60}")
    print(f"✅ {success_count}/{len(db_paths)} DB 마이그레이션 완료!")
    print(f"{'='*60}")

# PyInstaller runtime hook for SQLite
# 이 파일은 PyInstaller 실행 시점에 SQLite 모듈을 안전하게 로드하는 역할을 합니다.

import sys
import os

def ensure_sqlite():
    """SQLite 모듈이 제대로 로드되도록 보장합니다."""
    
    # _MEIPASS 경로 우선 추가
    if hasattr(sys, '_MEIPASS'):
        meipass = sys._MEIPASS
        
        # PATH에 _MEIPASS 및 하위 디렉토리 추가 (DLL 검색 경로)
        paths_to_add = [
            meipass,
            os.path.join(meipass, 'DLLs'),
            os.path.join(meipass, 'Library', 'bin'),
        ]
        
        for path in paths_to_add:
            if os.path.exists(path) and path not in os.environ.get('PATH', ''):
                os.environ['PATH'] = path + os.pathsep + os.environ.get('PATH', '')
                print(f"[RUNTIME-HOOK] PATH에 추가: {path}")
    
    try:
        # 1. _sqlite3 모듈 먼저 로드 (C 확장)
        try:
            import _sqlite3
            print("[RUNTIME-HOOK] _sqlite3 모듈 로드 성공")
        except ImportError as e:
            print(f"[RUNTIME-HOOK] _sqlite3 모듈 로드 실패: {e}")
        
        # 2. sqlite3 모듈 로드
        import sqlite3
        print("[RUNTIME-HOOK] sqlite3 모듈 로드 성공")
        
        # 3. 간단한 테스트
        conn = sqlite3.connect(':memory:')
        conn.execute('CREATE TABLE test (id INTEGER)')
        conn.close()
        print("[RUNTIME-HOOK] SQLite 기능 테스트 성공")
        
        return True
        
    except Exception as e:
        print(f"[RUNTIME-HOOK] SQLite 초기화 실패: {e}")
        
        # 디버깅 정보 출력
        if hasattr(sys, '_MEIPASS'):
            print(f"[RUNTIME-HOOK] _MEIPASS: {sys._MEIPASS}")
            try:
                sqlite_files = [f for f in os.listdir(sys._MEIPASS) if 'sqlite' in f.lower()]
                print(f"[RUNTIME-HOOK] SQLite 관련 파일: {sqlite_files}")
            except Exception as list_err:
                print(f"[RUNTIME-HOOK] 파일 목록 실패: {list_err}")
        
        return False

# Hook 실행
if __name__ == "__main__":
    ensure_sqlite()
else:
    ensure_sqlite()

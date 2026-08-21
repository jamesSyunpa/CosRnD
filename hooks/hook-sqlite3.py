# PyInstaller hook for sqlite3 module
# 파일명: hook-sqlite3.py

from PyInstaller.utils.hooks import collect_submodules, collect_dynamic_libs
import sys
import os

# SQLite3의 모든 서브모듈 수집
hiddenimports = collect_submodules('sqlite3')

# 추가 숨겨진 imports
hiddenimports += [
    '_sqlite3',
    'sqlite3.dbapi2',
    'sqlite3.dump'
]

# SQLite3 관련 바이너리 파일들 수집
binaries = collect_dynamic_libs('sqlite3')

# Windows에서 SQLite DLL 찾기
if sys.platform.startswith('win'):
    import glob
    python_dir = os.path.dirname(sys.executable)
    
    # 가능한 SQLite DLL 위치들
    possible_paths = [
        os.path.join(python_dir, 'sqlite3.dll'),
        os.path.join(python_dir, 'DLLs', 'sqlite3.dll'),
        os.path.join(python_dir, 'Library', 'bin', 'sqlite3.dll'),
        os.path.join(python_dir, 'Library', 'bin', 'sqlite3.exe')
    ]
    
    for path in possible_paths:
        if os.path.exists(path):
            binaries.append((path, '.'))
            print(f"[HOOK] Found SQLite binary: {path}")
    
    # _sqlite3.pyd 파일 찾기
    sqlite_pyd_patterns = [
        os.path.join(python_dir, 'DLLs', '_sqlite3*.pyd'),
        os.path.join(python_dir, 'Lib', 'site-packages', '_sqlite3*.pyd')
    ]
    
    for pattern in sqlite_pyd_patterns:
        for pyd_file in glob.glob(pattern):
            binaries.append((pyd_file, '.'))
            print(f"[HOOK] Found SQLite PYD: {pyd_file}")
# PyInstaller hook for ensuring SQLite support
# 파일명: hook-_sqlite3.py

from PyInstaller.utils.hooks import collect_data_files, collect_dynamic_libs
import os

# SQLite 관련 모든 데이터와 바이너리 수집
datas = []
binaries = []

# SQLite 바이너리 파일들 수집
binaries += collect_dynamic_libs('sqlite3')
binaries += collect_dynamic_libs('_sqlite3')

# 숨겨진 imports 추가
hiddenimports = [
    'sqlite3',
    '_sqlite3',
    'sqlite3.dbapi2'
]
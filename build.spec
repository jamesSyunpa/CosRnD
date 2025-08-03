# -*- mode: python ; coding: utf-8 -*-

import os
import sys
from PyInstaller.utils.hooks import collect_data_files

# --- 프로젝트 루트 경로 설정 ---
# 이 spec 파일이 프로젝트 루트에 있다고 가정합니다.
project_root = os.path.dirname(os.path.abspath(sys.argv[0]))

# --- 데이터 파일 수집 ---
# customtkinter의 테마 파일들을 포함시킵니다.
datas = collect_data_files('customtkinter')

# --- 숨겨진 import 추가 ---
# PyInstaller가 자동으로 찾지 못할 수 있는 모듈들을 명시적으로 추가합니다.
hiddenimports = [
    'babel.numbers', 'babel.dates',
    'sqlalchemy.sql.default_comparator',
    # SQLAlchemy dialects
    'sqlalchemy.dialects.sqlite',
    'sqlalchemy.dialects.mysql',
    'sqlalchemy.dialects.postgresql',
    # Pillow and tkcalendar
    'PIL', 'PIL._tkinter_finder', 'tkcalendar',
    # Pandas and openpyxl dependencies
    'pandas', 'openpyxl',
    # Other potential hidden imports
    'pkg_resources.py2_warn'
]

a = Analysis(
    ['main.py'],
    pathex=[
        project_root,
        os.path.join(project_root, 'modules'),
        os.path.join(project_root, 'database'),
        os.path.join(project_root, 'utils')
    ],
    binaries=[],
    datas=collect_data_files('customtkinter'),
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=None,
    noarchive=False,
)
pyz = PYZ(a.pure, a.zipped_data, cipher=None)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.zipfiles,
    a.datas,
    [],
    name='RnD_Management_System',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,         # GUI 애플리케이션이므로 콘솔 창을 숨깁니다.
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon='icon.ico'
)

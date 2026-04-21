# -*- mode: python ; coding: utf-8 -*-

import os
import sys
from PyInstaller.utils.hooks import collect_data_files
import customtkinter

# --- 프로젝트 루트 경로 설정 ---
# 이 spec 파일이 프로젝트 루트에 있다고 가정합니다.
project_root = os.path.dirname(os.path.abspath(sys.argv[0]))

# --- 데이터 파일 수집 ---
# customtkinter 패키지의 모든 데이터 파일을 안전하게 수집합니다.
# collect_data_files는 패키지 내부의 assets 등 필요한 리소스를 모두 반환합니다.
datas = collect_data_files('customtkinter', include_py_files=False)

# 프로젝트 루트의 설정 파일을 추가합니다. (icon은 프로젝트에 있는 정확한 파일명을 사용하세요)
datas += [('config.ini', '.')]

# 주의: 아이콘 파일이 프로젝트 루트에 있다면 아래처럼 추가하세요.
# datas += [('icon.ico', '.')]

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
    'pandas', 'openpyxl', 'openpyxl.cell.cell',
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
    datas=datas,
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
    console=True,         # 디버깅 중에는 콘솔을 켜서 런타임 로그를 확인합니다.
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon='Icon.ico'
)

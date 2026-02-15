# -*- mode: python ; coding: utf-8 -*-
import sys
import os

# ✅ 프로젝트 루트 경로 확인
project_root = os.path.dirname(os.path.abspath(__file__))
if hasattr(sys, '_MEIPASS'):
    # PyInstaller가 실행 중일 때
    project_root = sys.prefix

hooks_path = os.path.join(project_root, 'hooks')

a = Analysis(
    [os.path.join(project_root, 'main.py')],
    pathex=[project_root],  # ✅ 절대 경로 추가
    binaries=[],  # SQLite3는 PyInstaller가 자동으로 포함함
    datas=[
        (os.path.join(project_root, 'assets'), 'assets'),
        (os.path.join(project_root, 'data'), 'data'),
        (os.path.join(project_root, 'database'), 'database'),
        (os.path.join(project_root, 'modules'), 'modules'),
        (os.path.join(project_root, 'utils'), 'utils'),
        (os.path.join(project_root, 'config.ini'), '.'),
        (os.path.join(project_root, 'VERSION'), '.'),
        (os.path.join(project_root, 'Icon.ico'), '.'),
    ],
    # ✅ hiddenimports: 동적으로 import되는 모듈들을 명시적으로 추가
    hiddenimports=[
        # 데이터베이스 모듈
        'database.db_manager',
        'database.models',
        # UI 모듈
        'modules.login',
        'modules.signup',
        'modules.home_frame',
        'modules.security',
        'modules.translation',
        'modules.ui_components',
        'modules.document_management',
        'modules.formulation_popup',
        'modules.material_management',
        'modules.quality_management',
        'modules.excel_handler',
        # 유틸리티 모듈
        'utils.address_search',
        'utils.autocomplete',
        # 주요 라이브러리
        'customtkinter',
        'PIL',
        'sqlalchemy',
        'sqlalchemy.orm',
        'sqlalchemy.sql',
        'bcrypt',
        'openpyxl',
        'pandas',
        'tkcalendar',
        'babel',
        'pydoc_data',
    ],
    hookspath=[hooks_path],  # ✅ 절대 경로 추가
    hooksconfig={},
    runtime_hooks=[],  # PyInstaller 5.0+ 이상에서는 자동 관리
    excludes=[
        'matplotlib',
        'numpy',
        'scipy',
        'pytest',
        'unittest',
    ],
    noarchive=False,
    optimize=0,
)

pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    name='화장품연구관리_v59',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,  # ✅ 콘솔 창 비활성화
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=[os.path.join(project_root, 'Icon.ico')],
)

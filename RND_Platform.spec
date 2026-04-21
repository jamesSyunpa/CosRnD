# -*- mode: python ; coding: utf-8 -*-

import os
import sys
from glob import glob
from PyInstaller.utils.hooks import collect_data_files

block_cipher = None

# ==================== Analysis ====================
a = Analysis(
    ['main.py'],
    pathex=['.'],
    binaries=[],
    datas=[],
    hiddenimports=[
        'babel.numbers',
        'sqlalchemy.dialects.sqlite',
        'sqlalchemy.ext.declarative',  # 추가
        'customtkinter',
        'customtkinter.windows.widgets.ctk_button', # 명시적 추가
        'tkcalendar',
        'openpyxl',
        'bcrypt',
        # 프로젝트 모듈
        'modules',
        'modules.login',
        'modules.home_frame',
        'modules.document_management',
        'modules.comparison_popup',
        'modules.folder_history_popup',
        'modules.history_popup',
        'modules.settings_management',
        'modules.data_management',
        'modules.excel_handler',
        'modules.formulation_popup',
        'modules.material_management',
        'modules.signup',
        'modules.ui_components',
        'modules.translation',
        'modules.quality_management',
        'database',
        'database.db_manager',
        'database.models',  # 이게 핵심!
        'utils.address_search',
        'utils.autocomplete',
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    cipher=block_cipher,
)

print("\n========== 데이터 파일 수집 시작 ==========\n")

# 1. config.ini 추가
if os.path.exists('config.ini'):
    a.datas.append(('config.ini', 'config.ini', 'DATA'))
    print("✓ config.ini 추가됨")

# 2. 아이콘
icon_path = None
if os.path.exists('icon.ico'):
    icon_path = os.path.abspath('icon.ico')
    print("✓ icon.ico 발견됨")

# 6. customtkinter 데이터 파일
try:
    a.datas += collect_data_files('customtkinter')
    print("✓ customtkinter assets 추가됨")
except Exception as e:
    print(f"⚠ customtkinter 수집 실패: {e}")

# 7. tkcalendar 로케일
try:
    import tkcalendar
    tkcalendar_path = os.path.dirname(tkcalendar.__file__)
    a.datas += collect_data_files('tkcalendar')
    print("✓ tkcalendar 로케일 추가됨")
except Exception as e:
    print(f"⚠ tkcalendar 수집 실패: {e}")

print(f"\n✓ 총 {len(a.datas)}개 항목 포함\n")

# 데이터 검증
invalid = [i for i, item in enumerate(a.datas) if not isinstance(item, tuple) or len(item) != 3]
if invalid:
    print(f"❌ 잘못된 항목: {invalid[:5]}")
    sys.exit(1)

print("========== 데이터 파일 수집 완료 ==========\n")

# ==================== PYZ ====================
pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)


print("\n========== EXE 입력 검증 ==========")
for name, items in [('scripts', a.scripts), ('binaries', a.binaries), ('datas', a.datas)]:
    print(f"\n{name} 검증:")
    invalid = []
    for i, item in enumerate(items):
        if not isinstance(item, tuple) or len(item) != 3:
            invalid.append((i, item))
    if invalid:
        print(f"  ❌ 잘못된 항목 {len(invalid)}개:")
        for i, item in invalid[:3]:
            print(f"    [{i}] {item}")
    else:
        print(f"  ✓ 정상 ({len(items)}개)")

# ==================== EXE ====================
exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    name='RND_Platform',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=True,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=icon_path
)
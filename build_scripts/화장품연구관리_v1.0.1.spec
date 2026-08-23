# -*- mode: python ; coding: utf-8 -*-
import os

# Get the directory of the spec file to resolve paths relatively
spec_dir = os.path.abspath(SPECPATH)
project_root = os.path.dirname(spec_dir)

a = Analysis(
    [os.path.join(project_root, 'main.py')],
    pathex=[project_root],
    binaries=[],
    datas=[
        (os.path.join(project_root, 'assets', '*'), 'assets'),
        (os.path.join(project_root, 'data', '*'), 'data'),
        (os.path.join(project_root, 'database', '*'), 'database'),
        (os.path.join(project_root, 'modules', '*'), 'modules'),
        (os.path.join(project_root, 'utils', '*'), 'utils'),
        (os.path.join(project_root, 'Icon.ico'), '.')
    ],
    hiddenimports=['win32event', 'win32api', 'winerror', 'sqlite3', 'sqlalchemy.ext.baked', 'babel.numbers'],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
    optimize=0,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name='화장품연구관리_v1.0.1',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=False,  # 콘솔창 숨기기
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=[os.path.join(project_root, 'Icon.ico')],
)
coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=False,
    upx_exclude=[],
    name='화장품연구관리_v1.0.1',
)


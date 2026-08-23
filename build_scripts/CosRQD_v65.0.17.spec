# -*- mode: python ; coding: utf-8 -*-
import os

spec_dir = os.path.abspath(SPECPATH)
project_root = os.path.dirname(spec_dir)

a = Analysis(
    [os.path.join(project_root, 'main.py')],
    pathex=[project_root],
    binaries=[],
    datas=[
        (os.path.join(project_root, 'assets'), 'assets'),
        (os.path.join(project_root, 'data'), 'data'),
        (os.path.join(project_root, 'database'), 'database'),
        (os.path.join(project_root, 'modules'), 'modules'),
        (os.path.join(project_root, 'utils'), 'utils'),
        (os.path.join(project_root, 'Icon.ico'), '.'),
        (os.path.join(project_root, 'VERSION'), '.'),
        (os.path.join(project_root, 'config.ini'), '.'),
    ] + ([(__import__('certifi').where(), 'certifi')] if hasattr(__import__('certifi'), 'where') else []),
    hiddenimports=[
        'win32event', 'win32api', 'winerror', 'sqlite3', 
        'sqlalchemy.ext.baked', 'babel.numbers', 'customtkinter', 
        'PIL', 'PIL._tkinter_finder', 'pandas', 'openpyxl', 
        'bs4', 'requests', 'bcrypt', 'cryptography',
        'certifi', 'urllib3', 'charset_normalizer', 'idna'
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[
        'llvmlite', 'pyarrow', 'scipy', 'scipy.libs', 'matplotlib', 
        'IPython', 'notebook', 'torch', 'sympy', 'PyQt5', 'PySide2', 'PySide6',
        'pytest', 'unittest', 'test', 'pkg_resources', 'setuptools'
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
    name='CosRQD',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=[os.path.join(project_root, 'Icon.ico')],
)

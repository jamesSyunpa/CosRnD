# -*- mode: python ; coding: utf-8 -*-
import os

spec_dir = os.path.abspath(SPECPATH)
project_root = os.path.dirname(spec_dir)

a = Analysis(
    [os.path.join(project_root, 'launcher.py')],
    pathex=[project_root],
    binaries=[],
    datas=[
        (os.path.join(project_root, 'dist', 'app.zip'), '.'),
        (os.path.join(project_root, 'Icon.ico'), '.'),
        (os.path.join(project_root, 'launcher'), 'launcher')
    ],
    hiddenimports=[
        'launcher', 'launcher.installer', 'launcher.launcher_gui', 
        'launcher.config_manager', 'launcher.process_manager', 'launcher.updater',
        'PyQt6', 'PyQt6.QtCore', 'PyQt6.QtGui', 'PyQt6.QtWidgets',
        'psutil', 'requests', 'customtkinter', 'PIL', 'win32api', 'win32con',
        'win32com', 'win32com.client', 'pythoncom'
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=['PyQt5', 'PySide2', 'PySide6'],
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
    name='Setup_CosRQD_v65.0.2',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,  # 콘솔창 숨기기
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=[os.path.join(project_root, 'Icon.ico')],
    version=os.path.join(spec_dir, 'version_info.txt'),
)

# -*- mode: python ; coding: utf-8 -*-


a = Analysis(
    ['c:\\Users\\USER\\원드라이브\\OneDrive\\문서\\RnD_시스템_문서\\Test\\CosRnD_v58\\main.py'],
    pathex=[],
    binaries=[],
    datas=[('assets\\*', 'assets'), ('data\\*', 'data'), ('database\\*', 'database'), ('modules\\*', 'modules'), ('utils\\*', 'utils'), ('config.ini', '.')],
    hiddenimports=[],
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
    name='화장품연구관리_v58',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=True,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=['c:\\Users\\USER\\원드라이브\\OneDrive\\문서\\RnD_시스템_문서\\Test\\CosRnD_v58\\Icon.ico'],
)
coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name='화장품연구관리_v58',
)

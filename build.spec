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

# tkcalendar 패키지에서 필요한 리소스가 있는 경우 포함 (안전망)
try:
    datas += collect_data_files('tkcalendar', include_py_files=False)
    print("[SPEC] tkcalendar 데이터 파일 포함 완료")
except Exception as _e:
    print(f"[SPEC] tkcalendar 데이터 파일 수집 스킵: {_e}")

# Babel 지역화 데이터 포함 (tkcalendar가 Babel을 사용하므로 필수)
try:
    # 패키지 내부 경로 기준이므로 includes에 'babel/...'가 아니라 'locale-data/*'를 사용하거나
    # subdir='locale-data'를 사용하는 것이 정확합니다.
    datas += collect_data_files('babel', subdir='locale-data', include_py_files=False)
    print("[SPEC] Babel locale-data 포함 완료 (subdir=locale-data)")
except Exception as _e:
    try:
        # 일부 환경에서 subdir 인식이 다를 수 있어 includes 대안 경로도 시도
        datas += collect_data_files('babel', includes=['locale-data/*'], include_py_files=False)
        print("[SPEC] Babel locale-data 포함 완료 (includes=locale-data/*)")
    except Exception as _e2:
        print(f"[SPEC] Babel locale-data 수집 실패: {_e} | 대안도 실패: {_e2}")

# customtkinter 테마 파일들을 강제로 포함
import customtkinter
ctk_path = os.path.dirname(customtkinter.__file__)
ctk_assets_path = os.path.join(ctk_path, 'assets')
if os.path.exists(ctk_assets_path):
    datas += [(ctk_assets_path, 'customtkinter/assets')]
    print(f"[SPEC] CustomTkinter assets 추가: {ctk_assets_path}")

# CustomTkinter 아이콘 파일들을 별도로 포함
ctk_icons_path = os.path.join(ctk_path, 'assets', 'icons')
if os.path.exists(ctk_icons_path):
    datas += [(ctk_icons_path, 'customtkinter/assets/icons')]
    print(f"[SPEC] CustomTkinter icons 추가: {ctk_icons_path}")
    
    # 개별 아이콘 파일들도 명시적으로 포함
    icon_files = ['CustomTkinter_icon_Windows.ico', 'CustomTkinter_icon_macOS.icns']
    for icon_file in icon_files:
        icon_file_path = os.path.join(ctk_icons_path, icon_file)
        if os.path.exists(icon_file_path):
            datas += [(icon_file_path, 'customtkinter/assets/icons')]
            print(f"[SPEC] CustomTkinter 개별 아이콘 추가: {icon_file}")

# CustomTkinter 테마 파일들도 별도로 포함
ctk_themes_path = os.path.join(ctk_path, 'assets', 'themes')
if os.path.exists(ctk_themes_path):
    datas += [(ctk_themes_path, 'customtkinter/assets/themes')]
    print(f"[SPEC] CustomTkinter themes 추가: {ctk_themes_path}")

# 아이콘 파일 추가 - 간단하고 효과적인 방법으로
icon_added = False
main_icon_path = os.path.join(project_root, 'Icon.ico')

if os.path.exists(main_icon_path):
    # 메인 아이콘 파일만 추가 (PyInstaller가 자동으로 처리하도록)
    datas += [(main_icon_path, '.')]
    print(f"[SPEC] 메인 아이콘 추가: {main_icon_path}")
    icon_added = True

if not icon_added:
    print("[SPEC] 경고: Icon.ico 파일을 찾을 수 없습니다!")

# config.ini와 data 폴더도 포함 (재시작 시 필요)
config_path = os.path.join(project_root, 'config.ini')
if os.path.exists(config_path):
    datas += [(config_path, '.')]
    print(f"[SPEC] 설정 파일 추가: {config_path}")

# data 폴더가 있으면 포함
data_path = os.path.join(project_root, 'data')
if os.path.exists(data_path):
    datas += [(data_path, 'data')]
    print(f"[SPEC] 데이터 폴더 추가: {data_path}")

# --- 숨겨진 import 추가 ---
# PyInstaller가 자동으로 찾지 못할 수 있는 모듈들을 명시적으로 추가합니다.
hiddenimports = [
    # SQLite 관련 - 중요!
    '_sqlite3', 'sqlite3', 
    'sqlite3.dbapi2',
    'sqlite3.dump',
    # SQLAlchemy 관련
    'babel.numbers', 'babel.dates',
    'sqlalchemy.sql.default_comparator',
    'sqlalchemy.engine.strategies',
    'sqlalchemy.pool',
    'sqlalchemy.engine.base',
    'sqlalchemy.event',
    'sqlalchemy.orm',
    'sqlalchemy.orm.session',
    'sqlalchemy.orm.query',
    'sqlalchemy.orm.relationships',
    # SQLAlchemy dialects
    'sqlalchemy.dialects.sqlite',
    'sqlalchemy.dialects.sqlite.pysqlite',
    'sqlalchemy.dialects.sqlite.base',
    # 암호화 및 보안
    'bcrypt',
    '_bcrypt',
    # 설정 관리
    'configparser',
    # Pillow 관련
    'PIL', 
    'PIL._tkinter_finder', 
    'PIL.Image',
    'PIL.ImageDraw',
    'PIL.ImageTk',
    # tkcalendar
    'tkcalendar',
    'tkcalendar.calendar_',
    'tkcalendar.dateentry',
    # Pandas and openpyxl dependencies
    'pandas', 
    'pandas.io.excel',
    'pandas.io.formats.excel',
    'openpyxl', 
    'openpyxl.cell.cell',
    'openpyxl.cell._writer',
    'openpyxl.styles',
    'openpyxl.worksheet.worksheet',
    'openpyxl.workbook.workbook',
    'et_xmlfile',
    'jdcal',
    # Tkinter 관련
    'tkinter', 
    'tkinter.messagebox', 
    'tkinter.filedialog',
    'tkinter.ttk',
    'tkinter.font',
    # CustomTkinter 관련
    'customtkinter',
    'customtkinter.windows',
    'customtkinter.widgets',
    # Pillow 추가 컴포넌트 (미리보기에서 truetype 사용)
    'PIL.ImageFont',
    # 프로젝트 모듈들
    'database',
    'database.db_manager',
    'database.models',
    'modules',
    'modules.translation',
    'modules.login',
    'modules.signup',
    'modules.home_frame',
    'modules.settings_management',
    'modules.data_management',
    'modules.document_management',
    'modules.quality_management',
    'modules.material_management',
    'modules.formulation_popup',
    'modules.excel_handler',
    'modules.print_preview',
    'modules.ui_components',
    'modules.comparison_popup',
    'modules.history_popup',
    'modules.folder_history_popup',
    'utils',
    'utils.address_search',
    'utils.autocomplete',
    # 기타 필수 모듈
    'decimal',
    'datetime',
    'collections',
    'collections.abc',
    'subprocess',
    'shutil',
    'pkg_resources.py2_warn',
]

# --- 바이너리 파일 수집 ---
import glob
import site

binaries = []

# SQLite3 DLL 파일들을 찾아서 포함
python_path = os.path.dirname(sys.executable)
sqlite_dll_paths = [
    os.path.join(python_path, 'sqlite3.dll'),
    os.path.join(python_path, 'DLLs', 'sqlite3.dll'),
    os.path.join(python_path, 'Library', 'bin', 'sqlite3.dll')
]

for dll_path in sqlite_dll_paths:
    if os.path.exists(dll_path):
        binaries.append((dll_path, '.'))
        print(f"Found SQLite DLL: {dll_path}")
        break

# site-packages에서 _sqlite3 관련 파일들 찾기
for site_path in site.getsitepackages():
    sqlite_files = glob.glob(os.path.join(site_path, '_sqlite3*'))
    for file in sqlite_files:
        if os.path.isfile(file):
            binaries.append((file, '.'))
            print(f"Found SQLite module: {file}")

a = Analysis(
    ['main.py'],
    pathex=[
        project_root,
        os.path.join(project_root, 'modules'),
        os.path.join(project_root, 'database'),
        os.path.join(project_root, 'utils')
    ],
    binaries=binaries,
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[os.path.join(project_root, 'hooks')],
    hooksconfig={},
    runtime_hooks=[
        os.path.join(project_root, 'hooks', 'pyi_rth_sqlite.py'),
        os.path.join(project_root, 'hooks', 'pyi_rth_gui_excepthook.py'),
    ],
    excludes=[
        # 큰 과학 계산 라이브러리들 제외 (필요한 경우만 포함)
        'scipy', 'scipy.linalg', 'scipy.special', 'scipy.spatial',
        'matplotlib.backends.backend_qt5agg', 'matplotlib.backends.backend_qtagg',
        'matplotlib.backends.backend_gtk3agg', 'matplotlib.backends.backend_tkagg',
        'numba.tests', 'pandas.tests', 
        'IPython', 'jupyter', 'notebook',
        # 불필요한 테스트 모듈들
        'test', 'tests', '_test', '_tests',
        'setuptools.tests', 'pkg_resources.tests',
        # GUI 백엔드 (tkinter만 사용)
        'PyQt5', 'PyQt6', 'PySide2', 'PySide6',
        # 웹 관련 (사용하지 않음)
        'tornado', 'flask', 'django',
        # 기타 불필요한 모듈들
        'pygments.lexers', 'pygments.styles',
    ],
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
    console=False,         # 실사용 버전에서는 콘솔 창 숨김
    disable_windowed_traceback=True,   # PyInstaller 기본 오류 대화상자 비활성화 (커스텀 훅 사용)
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon='Icon.ico'
)

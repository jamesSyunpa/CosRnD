import sys
import os
import subprocess
import time

# 프로젝트 루트 경로 정의 및 sys.path 등록
PROJECT_ROOT = os.path.dirname(os.path.abspath(sys.executable if getattr(sys, 'frozen', False) else __file__))
if PROJECT_ROOT not in sys.path:
    sys.path.append(PROJECT_ROOT)

# [보안 & 안정성] 부모 프로세스로부터 상속된 잔여 PyInstaller 임시 환경변수 방어
if os.name == 'nt':
    for _k in ['_MEIPASS2', 'PYINSTALLER_STRICT_UNLOAD_MODE', 'PYINSTALLER_SUPPRESS_TEMP_ERRORS']:
        if _k in os.environ:
            del os.environ[_k]

# [핵심 안정성] PyInstaller 임시 경로 및 zipimport 캐시 완전 정화 (부모 _MEI 경로 오염 원천 차단)
if getattr(sys, 'frozen', False):
    cur_mei = getattr(sys, '_MEIPASS', '')
    clean_sys_path = []
    for p in sys.path:
        p_str = str(p)
        if '_MEI' in p_str:
            if cur_mei and cur_mei in p_str:
                clean_sys_path.append(p)
        else:
            clean_sys_path.append(p)
    sys.path[:] = clean_sys_path
    
    try:
        dead_keys = [k for k in sys.path_importer_cache if '_MEI' in k and (not cur_mei or cur_mei not in k)]
        for k in dead_keys:
            del sys.path_importer_cache[k]
    except Exception:
        pass

# [SSL & Certifi 안정성 보장] certifi.where() 경로 유효성 검사 및 안전 복구
try:
    import certifi
    ca_path = certifi.where()
    if not os.path.exists(ca_path):
        cur_meipass = getattr(sys, '_MEIPASS', '')
        for candidate in [
            os.path.join(cur_meipass, 'certifi', 'cacert.pem'),
            os.path.join(cur_meipass, 'cacert.pem'),
            os.path.join(os.path.dirname(sys.executable), 'cacert.pem')
        ]:
            if os.path.exists(candidate):
                certifi.where = lambda c=candidate: c
                os.environ['SSL_CERT_FILE'] = candidate
                os.environ['REQUESTS_CA_BUNDLE'] = candidate
                break
except Exception:
    pass

def unblock_self():
    """
    최초 실행 시 인터넷에서 다운로드되어 발생하는 Windows 스마트스크린 차단(MotW)을
    프로그램 내부에서 스스로 감지하여 자동으로 해제(Unblock)합니다.
    """
    if sys.platform.startswith('win'):
        try:
            # 1. 메인 실행 파일 경로 확인
            if getattr(sys, 'frozen', False):
                exe_path = sys.executable
            else:
                exe_path = os.path.abspath(__file__)
            
            # 2. NTFS 대체 데이터 스트림(Zone.Identifier) 경로 확인 및 삭제
            ads_path = f"{exe_path}:Zone.Identifier"
            if os.path.exists(ads_path):
                os.remove(ads_path)
                print(f"[보안] 자가 차단 해제 완료: {exe_path}")
        except Exception as e:
            print(f"[보안] 자가 차단 해제 시도 실패 (권한 등의 원인): {e}")

# 프로그램 구동 즉시 차단 해제 실행
unblock_self()

# 만약 --uninstall 인자가 전달된 경우 메인 앱 대신 언인스톨러 즉시 실행
if any(arg.lower() in ['--uninstall', '/uninstall', '-uninstall', 'uninstall'] for arg in sys.argv[1:]):
    try:
        from launcher.config_manager import ConfigManager
        from launcher.launcher_gui import run_uninstaller_gui
        cfg = ConfigManager()
        run_uninstaller_gui(cfg, "65.0.3")
    except Exception as uninst_err:
        try:
            import tkinter as tk
            from tkinter import messagebox
            root = tk.Tk()
            root.withdraw()
            messagebox.showerror("제거 오류", f"프로그램 제거 중 오류가 발생했습니다: {uninst_err}")
        except Exception:
            pass
    sys.exit(0)


def get_clean_subproc_env(extra_env=None):
    """
    서브프로세스 실행 시 PyInstaller 내부 임시 디렉토리 환경변수(_MEIPASS, _MEIPASS2 등)를
    완전히 제거하여, 새로 실행되는 자식 프로세스가 부모 프로세스의 임시 폴더에 종속되지 않고
    자신만의 고유한 새 임시 환경을 올바르게 생성하도록 보장합니다.
    """
    env = os.environ.copy()
    # 임시 디렉토리 및 파이썬 경로 오염을 유발하는 환경변수 목록 제거
    keys_to_remove = [
        '_MEIPASS',
        '_MEIPASS2',
        'PYTHONPATH',
        'PYTHONHOME',
        'PYINSTALLER_STRICT_UNLOAD_MODE',
        'PYINSTALLER_SUPPRESS_TEMP_ERRORS'
    ]
    for key in keys_to_remove:
        if key in env:
            del env[key]

    if extra_env:
        for k, v in extra_env.items():
            if v is not None:
                env[k] = str(v)
            elif k in env:
                del env[k]

    return env


def safe_restart_application(exe_path=None, extra_env=None):
    """
    Windows 환경에서 부모 프로세스가 완전히 종료(PID 소멸 및 DLL/임시폴더 락 해제)된 것을
    외부 스크립트가 직접 확인한 후, 깨끗한 환경에서 새 프로세스를 안전하게 실행합니다.
    """
    if not exe_path:
        exe_path = sys.executable if getattr(sys, 'frozen', False) else os.path.join(PROJECT_ROOT, "main.py")
    
    current_pid = os.getpid()

    # 1. Windows OS 레벨 환경변수 테이블에서 _MEIPASS, _MEIPASS2 강제 삭제
    if sys.platform.startswith('win'):
        try:
            import ctypes
            for k in ['_MEIPASS', '_MEIPASS2', 'PYTHONPATH', 'PYTHONHOME', 'PYINSTALLER_STRICT_UNLOAD_MODE', 'PYINSTALLER_SUPPRESS_TEMP_ERRORS']:
                ctypes.windll.kernel32.SetEnvironmentVariableW(k, None)
                if k in os.environ:
                    del os.environ[k]
        except Exception:
            pass

    # 2. 프로세스 소멸 감시 및 안전 재실행 배치 스크립트 실행
    if sys.platform.startswith('win'):
        try:
            import tempfile
            bat_file = os.path.join(tempfile.gettempdir(), f"cosrqd_restart_{int(time.time())}.bat")
            
            if getattr(sys, 'frozen', False):
                # 윈도우 쉘(explorer.exe)을 통해 100% 클린한 새 환경에서 실행 (환경변수 상속 완전 차단)
                run_target = f'explorer.exe "{exe_path}"'
            else:
                py_exe = sys.executable
                run_target = f'start "" "{py_exe}" "{exe_path}"'

            bat_content = f'''@echo off
setlocal
chcp 65001 > NUL
set PID={current_pid}

:WAIT_PROCESS
tasklist /fi "pid eq %PID%" 2>nul | find "%PID%" >nul
if not errorlevel 1 (
    timeout /t 1 /nobreak >nul
    goto WAIT_PROCESS
)

:: 이전 프로세스 종료 후 DLL 락 해제 및 임시폴더 정리 대기
timeout /t 1 /nobreak >nul

:: Windows Explorer Shell 독립 실행 (상속된 _MEIPASS2 완전 단절)
{run_target}

(goto) 2>nul & del "%~f0"
'''
            with open(bat_file, "w", encoding="utf-8") as f:
                f.write(bat_content)

            flags = subprocess.CREATE_NO_WINDOW if os.name == 'nt' else 0
            subprocess.Popen(f'cmd.exe /c "{bat_file}"', shell=True, creationflags=flags)
            print(f"[재시작] PID {current_pid} 소멸 감시 재실행 배치 시작: {bat_file}")
        except Exception as err:
            print(f"[재시작] 배치 생성 실패, 폴백 재시작 시도: {err}")
            ps_cmd = f"Wait-Process -Id {current_pid} -ErrorAction SilentlyContinue; Start-Sleep -Milliseconds 800; Start-Process '{exe_path}'"
            subprocess.Popen(["powershell", "-NoProfile", "-WindowStyle", "Hidden", "-Command", ps_cmd])
    else:
        clean_env = get_clean_subproc_env(extra_env)
        subprocess.Popen([exe_path], cwd=os.path.dirname(exe_path), env=clean_env)

    # 3. 현재 프로세스 즉시 안전 종료
    import os as _os
    _os._exit(0)


# 로그인/회원가입 시 표시할 법적고지 및 일반사항 전문
LEGAL_NOTICE_FULL_TEXT = '''
[법적 고지 및 저작권 이용 약관]
본 프로그램의 저작권 및 모든 지식재산권은 원저작권자(luckfortma)에게 있으며, 대한민국 저작권법 및 관련 법률의 보호를 받습니다. 사용자는 본 약관을 완전히 숙지하고 동의한 경우에만 본 프로그램을 사용할 수 있습니다.

0.1 프로그램 개요 및 개발 정보
    0.1.1 프로그램 명칭: 화장품 연구소 관리 시스템 (Cosmetic Research & Quality Data System)
    0.1.2 원저작권자: luckfortma (이메일: luckfortma@gmail.com)
    0.1.3 사용 목적: 화장품 연구 개발(R&D) 데이터 관리, 성분 정보 데이터베이스 관리 및 연구소 내부 관리 업무 지원

0.2 라이선스 및 배포 권한 제한 (중요)
    0.2.1 다운로드 및 사용 제한
        - 본 프로그램은 원저작권자가 공식적으로 게시하고 제공한 지정 경로(블로그, 깃허브 등 공식 채널)를 통해서만 다운로드받아 실행할 수 있습니다.
        - 비공식적인 경로를 통해 배포된 파일을 다운로드하거나 사용하는 행위는 금지되며, 이로 인해 발생하는 보안적·기술적 책임은 전적으로 사용자에게 있습니다.
    0.2.2 2차 수정 및 변형 금지 (반대급부 처벌 조항)
        - 본 프로그램의 소스코드, UI 설계, 템플릿, 데이터 구조 등을 무단으로 디컴파일(Reverse Engineering), 분석, 수정, 편집, 변형하거나 이를 기반으로 2차적 저작물을 작성하여 배포 및 사용하는 행위를 엄격히 금지합니다.
        - 저작권자의 사전 서면 동의 없이 프로그램의 일부 또는 전부를 상업적 목적으로 판매, 대여, 양도, 재배포하는 행위는 엄격한 민·형사상의 형사처벌 및 손해배상 청구의 대상이 됩니다.

0.3 법적 처벌 조항 명시 (저작권 침해)
    - 본 프로그램의 소스코드를 무단으로 복제, 변형, 개작하여 배포하거나 동일·유사한 프로그램을 제작하여 사용할 경우, 대한민국 저작권법 제136조(벌칙)에 따라 "5년 이하의 징역 또는 5천만 원 이하의 벌금"에 처해질 수 있으며, 이와는 별도로 저작권 침해로 발생한 경제적 손실에 대해 법적으로 강력한 손해배상(민사책임)을 청구받게 됩니다.

0.4 책임 범위 및 면책 조항 (Disclaimer)
    - 본 프로그램은 사용자의 연구 및 데이터 관리 효율을 지원하기 위한 도구입니다. 프로그램 내에서 계산되는 모든 결과(배합비, 단가 계산, 수치 분석 등)는 참고용 자료이며, 최종 제품의 법적 적합성, 안전성 및 최종 품질은 사용자가 관련 규정(INCI, 식약처 가이드라인 등)에 따라 최종 검증하여 판단해야 합니다.
    - 사용자의 입력 오류, 관리 부주의, 데이터 유실 또는 프로그램의 오용으로 발생한 유·무형의 결과에 대해 원저작권자는 어떠한 법률적·도의적 책임도 지지 않습니다.

0.5 저작권 귀속 고지
    Copyright © 2025-2026 luckfortma. All rights reserved.
    본 약관에 기재되지 않은 사항은 대한민국 저작권법 및 컴퓨터프로그램 보호법을 따릅니다.
'''


# Auto-install dependencies if missing (Self-Healing - Optimized)
def install_and_import(package_name, import_name=None):
    if import_name is None:
        import_name = package_name
    if import_name in sys.modules:
        return
    try:
        __import__(import_name)
    except ImportError:
        print(f"[Self-Healing] Installing missing package: {package_name}...")
        try:
            subprocess.check_call([sys.executable, "-m", "pip", "install", package_name], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            print(f"[Self-Healing] Successfully installed {package_name}")
        except Exception as e:
            print(f"[Self-Healing] Failed to install {package_name}: {e}")


# Ensure critical dependencies are present
install_and_import("customtkinter")
install_and_import("Pillow", "PIL")
install_and_import("sqlalchemy")
install_and_import("bcrypt")
install_and_import("openpyxl")
install_and_import("pandas")
install_and_import("tkcalendar")

# --- Fix for Tcl/Tk Encoding Issue on Windows (Korean Path) ---
try:
    base_path = sys.exec_prefix
    # Common locations for Tcl/Tk in Conda/Python environments on Windows
    # 1. Standard Python: tcl/tcl8.6
    # 2. Conda: Library/lib/tcl8.6
    
    potential_tcl_paths = [
        os.path.join(base_path, 'tcl', 'tcl8.6'),
        os.path.join(base_path, 'Library', 'lib', 'tcl8.6'),
        os.path.join(base_path, 'lib', 'tcl8.6'),
    ]
    
    for path in potential_tcl_paths:
        if os.path.exists(path):
            os.environ['TCL_LIBRARY'] = path
            # Assume tk is in the same parent dir
            tk_path = path.replace('tcl8.6', 'tk8.6')
            if os.path.exists(tk_path):
                os.environ['TK_LIBRARY'] = tk_path
            print(f"[Fix] Set TCL_LIBRARY to: {path}")
            break
            
except Exception as e:
    print(f"[Fix] Failed to set Tcl/Tk paths: {e}")
# -------------------------------------------------------------

import tkinter as tk
import customtkinter as ctk
import configparser
from tkinter import messagebox
from tkinter import ttk
from collections import deque
import tkinter.font as tkfont
import re
from PIL import Image

# ==================== 단일 인스턴스 실행 체크 (v64 스마트 소켓 락) ====================
_instance_socket = None

def check_single_instance():
    """로컬 소켓 바인딩 방식으로 중복 실행을 100% 안전하게 판별하고 프로세스 종료 시 자동 해제되도록 합니다."""
    global _instance_socket
    import socket
    try:
        _instance_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        # 로컬 고유 포트 바인딩 (Cosmetic R&D 고유 포트 49281)
        _instance_socket.bind(('127.0.0.1', 49281))
        print("[단일 인스턴스] 락 획득 완료 - 프로그램 정상 구동 허용")
        return True
    except (socket.error, OSError) as sock_err:
        print(f"[단일 인스턴스] 이미 다른 인스턴스가 포트를 사용 중입니다: {sock_err}")
        try:
            import tkinter as tk
            from tkinter import messagebox
            root = tk.Tk()
            root.withdraw()
            messagebox.showwarning(
                "프로그램 실행 알림",
                "프로그램이 이미 실행 중입니다.\n\n작업표시줄 또는 실행 중인 창을 확인해주세요.",
                parent=root
            )
            root.destroy()
        except Exception:
            pass
        return False
    except Exception as e:
        print(f"[단일 인스턴스] 체크 예외 발생(허용): {e}")
        return True

from utils import center_window_on_mouse_display, resource_path
from utils.update_manager import UpdateManager

if getattr(sys, 'frozen', False):
    # PyInstaller로 빌드된 경우, .exe 파일이 있는 폴더
    application_path = os.path.dirname(sys.executable)
else:
    # 일반 Python 스크립트로 실행된 경우
    application_path = os.path.dirname(os.path.abspath(__file__))


def create_fallback_icon(meipass_path: str | None) -> str | None:
    """Create a simple fallback .ico file inside `meipass_path` (or cwd) and return its path.

    The produced icon is a plain circle image saved as an ICO. Returns None on failure.
    """
    try:
        from PIL import Image, ImageDraw
        import os

        target_dir = meipass_path if (meipass_path and os.path.isdir(meipass_path)) else os.getcwd()
        os.makedirs(target_dir, exist_ok=True)

        size = (256, 256)
        img = Image.new('RGBA', size, (0, 0, 0, 0))
        draw = ImageDraw.Draw(img)

        # Draw a rounded colored circle as a neutral fallback logo
        margin = 32
        draw.ellipse((margin, margin, size[0] - margin, size[1] - margin), fill=(100, 149, 237, 255))

        out_path = os.path.join(target_dir, 'fallback_icon.ico')
        # Save as ICO (Pillow supports ICO); include common sizes
        img.save(out_path, format='ICO', sizes=[(256, 256), (128, 128), (64, 64)])
        print(f"[RUNTIME-ASSETS] 생성된 대체 아이콘: {out_path}")
        return out_path
    except Exception as e:
        try:
            print(f"[RUNTIME-ASSETS] create_fallback_icon 실패: {e}")
        except Exception:
            pass
        return None

def get_persistent_config_path(app_dir_name: str = 'CosRQD') -> str:
    r"""사용자 AppData 폴더 내 config.ini 경로를 제공합니다.
    
    - 기존 사용자가 있는 경우 기존 local config.ini 또는 AppData\CosRnD / AppData\RnD_플랫폼의 설정을 복사/이동하여 적용해 줍니다.
    """

    try:
        # 1. 새 AppData 경로 설정 (%APPDATA%\CosRQD\config.ini)
        appdata_root = os.getenv('APPDATA', os.path.join(os.path.expanduser('~'), 'AppData', 'Roaming'))
        appdata_dir = os.path.join(appdata_root, app_dir_name)
        os.makedirs(appdata_dir, exist_ok=True)
        target_config = os.path.join(appdata_dir, 'config.ini')
        
        # 2. 마이그레이션 로직: 기존 설정이 있고 새 경로에 없을 때 복사
        local_config = os.path.join(application_path, 'config.ini')
        old_cosrnd_config = os.path.join(appdata_root, 'CosRnD', 'config.ini')
        old_appdata_config = os.path.join(appdata_root, 'RnD_플랫폼', 'config.ini')

        if not os.path.exists(target_config):
            if os.path.exists(old_cosrnd_config):
                try:
                    import shutil
                    shutil.copy2(old_cosrnd_config, target_config)
                    print(f"[CONFIG] 기존 CosRnD config.ini를 CosRQD로 복사했습니다: {target_config}")
                except Exception as copy_err:
                    print(f"[CONFIG] 기존 CosRnD 복사 실패: {copy_err}")
            elif os.path.exists(local_config):
                try:
                    import shutil
                    shutil.copy2(local_config, target_config)
                    print(f"[CONFIG] 기존 로컬 config.ini를 AppData로 복사했습니다: {target_config}")
                except Exception as copy_err:
                    print(f"[CONFIG] 기존 로컬 복사 실패: {copy_err}")
            elif os.path.exists(old_appdata_config):
                try:
                    import shutil
                    shutil.copy2(old_appdata_config, target_config)
                    print(f"[CONFIG] 이전 AppData config.ini를 복사했습니다: {target_config}")
                except Exception as copy_err:
                    print(f"[CONFIG] 이전 AppData 복사 실패: {copy_err}")
                except Exception as copy_err:
                    print(f"[CONFIG] 이전 AppData 복사 실패: {copy_err}")

        # 3. 만약 여전히 존재하지 않거나 새 생성이 필요한 경우
        if not os.path.exists(target_config):
            try:
                default_db_dir = os.path.join(appdata_dir, 'Data').replace('\\', '/')
                default_backup_dir = os.path.join(appdata_dir, 'backup').replace('\\', '/')
                doc_dir = os.path.join(os.path.expanduser('~'), 'Documents', 'CosRQD')
                default_excel_dir = os.path.join(doc_dir, 'ExcelData').replace('\\', '/')
                
                default_content = f"""[Paths]
excel_dir = {default_excel_dir}
shared_db_path = {default_db_dir}
database_dir = {default_db_dir}
backup_dir = {default_backup_dir}

[Database]
initialized = False

[Legal]
agreed_version = 
"""
                with open(target_config, 'w', encoding='utf-8') as f:
                    f.write(default_content)
                print(f"[CONFIG] 새 기본 config.ini 생성: {target_config}")
            except Exception as create_error:
                print(f"[CONFIG] config.ini 생성 실패: {create_error}")

        return target_config
    except Exception as e:
        print(f"[CONFIG] AppData 설정 경로 확보 실패: {e}")
        return os.path.join(application_path, 'config.ini')

# config.ini는 AppData 경로의 파일을 사용합니다.
CONFIG_FILE_PATH = get_persistent_config_path()
print(f"[CONFIG] 최종 설정 파일 경로: {CONFIG_FILE_PATH}")


from sqlalchemy import text
from database.db_manager import db_manager
from datetime import datetime

# 모듈 정적 임포트 (IDE 린터 및 런타임 정적 분석 완벽 지원)
from modules.translation import get_texts
import modules.translation as _translation
from modules.login import LoginWindow
from modules.settings_management import SettingsManagementFrame
from modules.quality_management import QualityManagementFrame
from modules.data_management import DataManagementFrame
from modules.home_frame import HomeFrame
from modules.document_management import DocumentManagementFrame

# PyInstaller 빌드 환경을 고려한 안전한 모듈 경로 보강
def safe_import_modules():
    """빌드 환경에서 안전하게 모듈 경로를 보강하고 로드 상태를 검증합니다."""
    global get_texts, _translation, LoginWindow, SettingsManagementFrame
    global QualityManagementFrame, DataManagementFrame, HomeFrame
    global DocumentManagementFrame
    
    try:
        # 경로 설정 (빌드 환경 고려)
        if getattr(sys, 'frozen', False):
            # PyInstaller 빌드된 환경
            app_meipass = getattr(sys, '_MEIPASS', os.path.dirname(sys.executable))
            for sub_dir in ['modules', 'database', 'utils']:
                p = os.path.join(app_meipass, sub_dir)
                if p not in sys.path:
                    sys.path.insert(0, p)
        
        print("[DEBUG] 모든 모듈 임포트 성공")
        return True
        
    except ImportError as e:
        print(f"[ERROR] 모듈 임포트 실패: {e}")
        try:
            # 대안 임포트 시도
            import importlib.util
            
            # 모듈별 개별 임포트 시도
            modules_to_import = [
                ('translation', 'get_texts'),
                ('login', 'LoginWindow'),
                ('settings_management', 'SettingsManagementFrame'),
                ('quality_management', 'QualityManagementFrame'),
                ('data_management', 'DataManagementFrame'),
                ('home_frame', 'HomeFrame'),
                ('document_management', 'DocumentManagementFrame')
            ]
            
            for module_name, class_name in modules_to_import:
                try:
                    if getattr(sys, 'frozen', False):
                        module_path = os.path.join(sys._MEIPASS, 'modules', f'{module_name}.py')
                    else:
                        module_path = os.path.join('modules', f'{module_name}.py')
                    
                    spec = importlib.util.spec_from_file_location(module_name, module_path)
                    module = importlib.util.module_from_spec(spec)
                    spec.loader.exec_module(module)
                    
                    globals()[class_name] = getattr(module, class_name)
                    if module_name == 'translation':
                        globals()['get_texts'] = getattr(module, 'get_texts')
                        globals()['_translation'] = module
                    
                    print(f"[DEBUG] {module_name} 모듈 동적 임포트 성공")
                except Exception as module_error:
                    print(f"[ERROR] {module_name} 모듈 동적 임포트 실패: {module_error}")
                    return False
            
            return True
        except Exception as fallback_error:
            print(f"[ERROR] 대안 임포트도 실패: {fallback_error}")
            return False

# 모듈 임포트 실행
if not safe_import_modules():
    print("[CRITICAL] 필수 모듈 임포트 실패 - 프로그램을 종료합니다.")
    sys.exit(1)

# 프레임 이름을 상수로 정의
FRAME_SETTINGS = "settings"
FRAME_HOME = "home"
FRAME_DATA = "data"
FRAME_DOCUMENT = "document"
FRAME_QUALITY = "quality" # 품질관리 프레임 이름 추가
FRAME_PACKAGE = "package" # 패키지 관리 프레임 이름 추가

class App(ctk.CTk):
    def __init__(self):
        super().__init__()
        self.withdraw()  # 앱 시작 시 메인 창이 깜빡 뜨는 현상 방지를 위해 즉시 숨김
        # Install global safe wrappers for widget focus operations to avoid
        # TclError when scheduled callbacks try to focus a widget that was
        # destroyed before the callback runs.
        try:
            import tkinter as _tk

            _orig_misc_focus_set = getattr(_tk.Misc, 'focus_set', None)
            _orig_misc_focus_force = getattr(_tk.Misc, 'focus_force', None)

            def _safe_misc_focus_set(self, *a, **kw):
                try:
                    if getattr(self, 'winfo_exists', lambda: False)():
                        if callable(_orig_misc_focus_set):
                            return _orig_misc_focus_set(self, *a, **kw)
                except Exception:
                    try:
                        import traceback as _tb
                        txt = '[SAFE-FOCUS] focus_set ignored for destroyed widget.\n' + ''.join(_tb.format_stack(limit=10))
                        try:
                            # attempt to write to app log if available
                            try:
                                self._log_error(txt)
                            except Exception:
                                # fallback to stderr
                                print(txt)
                        except Exception:
                            print(txt)
                    except Exception:
                        pass
                return None

            def _safe_misc_focus_force(self, *a, **kw):
                try:
                    if getattr(self, 'winfo_exists', lambda: False)():
                        if callable(_orig_misc_focus_force):
                            return _orig_misc_focus_force(self, *a, **kw)
                except Exception:
                    try:
                        import traceback as _tb
                        txt = '[SAFE-FOCUS] focus_force ignored for destroyed widget.\n' + ''.join(_tb.format_stack(limit=10))
                        try:
                            self._log_error(txt)
                        except Exception:
                            print(txt)
                    except Exception:
                        pass
                return None

            try:
                if _orig_misc_focus_set:
                    _tk.Misc.focus_set = _safe_misc_focus_set
            except Exception:
                pass
            try:
                if _orig_misc_focus_force:
                    _tk.Misc.focus_force = _safe_misc_focus_force
            except Exception:
                pass
        except Exception:
            pass
        # Protect against TclErrors from scheduled 'focus' calls targeting
        # windows that may be destroyed before the callback runs. Wrap the
        # underlying tk interpreter call to ignore 'focus' errors.
        try:
            orig_tk_call = getattr(self.tk, 'call')
            def _safe_tk_call(*a, **kw):
                try:
                    return orig_tk_call(*a, **kw)
                except Exception as e:
                    try:
                        import _tkinter
                        # If it's a TclError caused by focusing a destroyed window,
                        # ignore it. Different callers may pass args in different
                        # orders, so check both command name and common message text.
                        if isinstance(e, _tkinter.TclError):
                            msg = str(e).lower()
                            cmd0 = (a[0].lower() if a and len(a) > 0 and isinstance(a[0], str) else '')
                            if cmd0 == 'focus' or 'bad window path name' in msg:
                                return None
                    except Exception:
                        pass
                    raise
            try:
                self.tk.call = _safe_tk_call
            except Exception:
                # assignment may fail in some environments; ignore
                pass
        except Exception:
            pass
        self.language = "korean" # 기본 언어 설정
        self.texts = get_texts(self.language) # 중앙 번역 객체 생성
        self.title("화장품 연구소 관리 시스템")

        # Tkinter 콜백 예외를 GUI 메시지로 표시하도록 훅 설정
        try:
            self.report_callback_exception = self._gui_exception_hook
        except Exception:
            pass

        # PyInstaller 임시 폴더 관련 오류 처리
        self.handle_pyinstaller_temp_issues()

        # 빌드 런타임 필수 리소스 보강 (아이콘/locale 등)
        self.ensure_runtime_assets()

        self.db_sync_timer = None
        self.db_path_warning_shown = False
        self.last_shared_db_info = (0, 0)

        # 최근 활동 기록을 위한 설정
        self.recent_actions = deque(maxlen=5) # 화면에 표시할 최대 개수
        
        self.current_user = None
        self.pending_frame_states = {}
        self.withdraw()  # 메인 창 숨김

        # 창 닫기 버튼(X)을 눌렀을 때 처리할 함수 지정
        self.protocol("WM_DELETE_WINDOW", self.on_closing)
        
        # 메인 창 및 작업 표시줄 아이콘 설정
        try:
            icon_file = resource_path('Icon.ico')
            if os.path.exists(icon_file):
                self.iconbitmap(icon_file)
        except Exception as icon_err:
            print(f"[ICON] 메인 창 아이콘 설정 실패: {icon_err}")
        
        # 앱 시작 시 로딩 스플래시 화면 표시
        self.after(50, self.show_pre_login_splash)

    def ensure_runtime_assets(self):
        """패키징 런타임에서 누락되면 크래시를 유발하는 리소스를 사전에 보강합니다.

        - CustomTkinter 기본 아이콘이 누락된 경우, 로컬 Icon.ico로 대체 복사
        - Babel locale-data 존재 여부를 점검하고 없으면 경고 로그(폴백은 개별 위젯 래퍼가 처리)
        """
        try:
            if getattr(sys, 'frozen', False) and hasattr(sys, '_MEIPASS'):
                meipass = sys._MEIPASS
                # 1) CustomTkinter 아이콘 보강
                try:
                    ctk_icon_dir = os.path.join(meipass, 'customtkinter', 'assets', 'icons')
                    ctk_icon_file = os.path.join(ctk_icon_dir, 'CustomTkinter_icon_Windows.ico')
                    if not os.path.exists(ctk_icon_file):
                        os.makedirs(ctk_icon_dir, exist_ok=True)
                        # 앱 리소스에서 아이콘 경로 탐색 후 복사
                        src_icon = resource_path('Icon.ico')
                        if src_icon and os.path.exists(src_icon):
                            import shutil
                            shutil.copy2(src_icon, ctk_icon_file)
                            print(f"[RUNTIME-ASSETS] CustomTkinter 아이콘 대체 복사 완료: {ctk_icon_file}")
                        else:
                            # 임시 아이콘 생성 후 복사
                            fallback = create_fallback_icon(meipass)
                            if fallback and os.path.exists(fallback):
                                import shutil
                                shutil.copy2(fallback, ctk_icon_file)
                                print(f"[RUNTIME-ASSETS] 임시 아이콘을 CustomTkinter 아이콘으로 사용: {ctk_icon_file}")
                except Exception as e:
                    print(f"[RUNTIME-ASSETS] CustomTkinter 아이콘 보강 실패(무시): {e}")

                # 2) Babel locale-data 존재 여부 점검 (tkcalendar가 필요로 함)
                try:
                    babel_locale_dir = os.path.join(meipass, 'babel', 'locale-data')
                    if not os.path.isdir(babel_locale_dir):
                        print("[RUNTIME-ASSETS][경고] Babel locale-data가 패키지에 없음. DateEntry는 안전 래퍼로 폴백됩니다.")
                        # 여기서 즉시 복구는 어렵기 때문에, UI 쪽 SafeDateEntry가 폴백 처리함.
                except Exception as e:
                    print(f"[RUNTIME-ASSETS] Babel locale-data 점검 실패(무시): {e}")
        except Exception as e:
            print(f"[RUNTIME-ASSETS] 보강 처리 중 오류(무시): {e}")

    # ---- GUI 예외 처리/로깅 유틸 ----
    def _log_error(self, text: str) -> str | None:
        try:
            base_dir = os.getenv('APPDATA') or os.path.expanduser('~')
            log_dir = os.path.join(base_dir, 'CosRQD', 'logs')
            os.makedirs(log_dir, exist_ok=True)
            from datetime import datetime as _dt
            fname = f"error_{_dt.now().strftime('%Y%m%d_%H%M%S')}.log"
            path = os.path.join(log_dir, fname)
            with open(path, 'w', encoding='utf-8') as f:
                f.write(text)
            return path
        except Exception:
            return None

    def _format_friendly_message(self, log_path: str | None) -> str:
        msg = (
            "프로그램 실행 중 예기치 않은 오류가 발생했습니다.\n"
            "작업이 중단되었을 수 있으니, 저장 후 프로그램을 다시 시작해 주세요."
        )
        if log_path:
            msg += f"\n\n오류 로그 위치:\n{log_path}"
        return msg

    def _gui_exception_hook(self, exctype, value, tb):
        """Tkinter 콜백 예외를 잡아 사용자에게 안내하고 luckfortma@gmail.com으로 전송할지 물어본 뒤 보고합니다."""
        try:
            import traceback as _tb
            tb_text = ''.join(_tb.format_exception(exctype, value, tb))
            log_path = self._log_error(tb_text)
            
            # 클립보드 복사 시도
            copied = False
            try:
                import pyperclip
                pyperclip.copy(tb_text)
                copied = True
            except Exception:
                try:
                    import tkinter as tk
                    r = tk.Tk()
                    r.withdraw()
                    r.clipboard_clear()
                    r.clipboard_append(tb_text)
                    r.update()
                    copied = True
                except Exception:
                    pass
            
            # 이메일 전송 여부 묻기
            msg = (
                "프로그램 실행 중 예기치 않은 오류가 발생했습니다.\n\n"
            )
            if copied:
                msg += "오류 세부 정보가 자동으로 [클립보드]에 복사되었습니다.\n\n"
            else:
                msg += "오류 세부 정보 복사에 실패했습니다.\n\n"
                
            msg += (
                "오류 원인을 파악하고 개선하기 위해 개발자(luckfortma@gmail.com)에게 에러 보고서를 전송하시겠습니까?\n\n"
                "※ 전송 버튼을 누르시면 메일 전송이 진행됩니다."
            )
            
            result = messagebox.askyesno('시스템 오류 및 보고', msg, parent=self)
            if result:
                self._send_error_report_email(tb_text)
            else:
                messagebox.showinfo('알림', '에러 보고서 전송이 취소되었습니다. 로그 파일이 로컬에 기록되었습니다.', parent=self)
                
        except Exception as e:
            try:
                messagebox.showerror('오류', f'치명적 오류가 발생했습니다. 프로그램을 종료합니다.\n{e}', parent=self)
            except Exception:
                pass

    def _send_error_report_email(self, traceback_text: str):
        """에러 보고서를 luckfortma@gmail.com으로 이메일 전송합니다."""
        import smtplib
        from email.mime.text import MIMEText
        import threading

        def send_mail_thread():
            try:
                sender_email = "cosrqd.reporter@gmail.com"
                receiver_email = "luckfortma@gmail.com"
                
                msg = MIMEText(traceback_text)
                msg['Subject'] = '[CosRQD 에러 보고서] 프로그램 예외 발생'
                msg['From'] = sender_email
                msg['To'] = receiver_email
                
                try:
                    raise smtplib.SMTPException("SMTP credentials not configured. Using fallback client.")
                except Exception:
                    # fallback: 사용자의 기본 메일 프로그램을 통해 luckfortma@gmail.com으로 메일 작성창 열기
                    import urllib.parse
                    import webbrowser
                    subject = urllib.parse.quote("[CosRQD 에러 보고서] 프로그램 예외 발생")
                    body = urllib.parse.quote(traceback_text[:1500] + "\n\n...(이하 생략 - 전체 로그는 %APPDATA%/CosRQD/logs 폴더의 파일을 첨부해 주세요.)")
                    mailto_url = f"mailto:luckfortma@gmail.com?subject={subject}&body={body}"
                    webbrowser.open(mailto_url)
                    
                self.after(500, lambda: messagebox.showinfo('보고 완료', '이메일 클라이언트를 통해 에러 보고 준비를 마쳤습니다. 메일을 보내주세요.', parent=self))
            except Exception as e:
                self.after(500, lambda: messagebox.showerror('보고 실패', f'메일 발송 도중 오류가 발생했습니다: {e}', parent=self))

        # 메인 UI가 얼지 않도록 별도 스레드로 발송 진행
        t = threading.Thread(target=send_mail_thread, daemon=True)
        t.start()

    def handle_pyinstaller_temp_issues(self):
        """PyInstaller 임시 폴더 관련 문제를 처리합니다."""
        try:
            if getattr(sys, 'frozen', False):
                # PyInstaller 실행 환경
                if hasattr(sys, '_MEIPASS'):
                    meipass = sys._MEIPASS
                    # 임시 폴더 접근성 확인
                    if not os.path.exists(meipass):
                        print(f"[PYINSTALLER] _MEIPASS 폴더 접근 불가: {meipass}")
                        # 임시 폴더가 접근 불가능한 경우 환경 변수 제거
                        if '_MEIPASS' in os.environ:
                            del os.environ['_MEIPASS']
                            print("[PYINSTALLER] 환경 변수에서 _MEIPASS 제거")
                    else:
                        print(f"[PYINSTALLER] _MEIPASS 정상 접근: {meipass}")
                        
                        # 임시 폴더 내 필수 파일들 존재 여부 확인
                        essential_files = ['modules', 'database', 'utils', 'customtkinter']
                        missing_files = []
                        for file_or_dir in essential_files:
                            path = os.path.join(meipass, file_or_dir)
                            if not os.path.exists(path):
                                missing_files.append(file_or_dir)
                        
                        if missing_files:
                            print(f"[PYINSTALLER] 누락된 파일/폴더: {missing_files}")
                        else:
                            print("[PYINSTALLER] 필수 파일들 정상 확인")
                            
        except Exception as e:
            print(f"[PYINSTALLER] 임시 폴더 처리 중 오류: {e}")
            # 오류 발생 시에도 계속 진행

    def show_login_window(self):
        print(f"{datetime.now()}: show_login_window 호출")
        # 재시작 시 자동 로그인 확인
        if self.check_restart_login():
            return

        # 먼저 로그인 창을 생성/표시한 뒤, 법적고지가 필요하면 그 위에 표시합니다.
        self.login_window = LoginWindow(
            master=self, 
            on_login_success=self.on_login_success,
            config_path=CONFIG_FILE_PATH,
            application_path=application_path
        )
        self.login_window.deiconify()
        self.login_window.lift()
        try:
            self.login_window.focus_force()
        except Exception:
            try:
                self.login_window.focus_set()
            except Exception:
                pass
        print(f"{datetime.now()}: 로그인 창 강제 표시")

        # 법적고지는 로그인 시 사용자가 입력을 완료하거나 로그인 시도할 때 확인합니다.

    def check_legal_notice_agreement(self, continue_callback=None):
        """법적 고지 동의 여부를 확인하고 필요한 경우 팝업을 띄웁니다.
        
        계정당 한 번만 동의하면 영구 저장됩니다 (버전 변경 시에도 재승인 불필요).
        """
        try:
            # 1. Config 확인 - 동의 여부만 확인 (버전 비교 없음)
            config = configparser.ConfigParser()
            config.read(CONFIG_FILE_PATH, encoding='utf-8')
            
            has_agreed = False
            if config.has_section('Legal'):
                agreed_value = config.get('Legal', 'agreed_version', fallback=None)
                # 동의 값이 존재하면 이미 동의한 것으로 간주
                has_agreed = agreed_value is not None and agreed_value.strip() != ''
            
            print(f"[LEGAL] Has agreed: {has_agreed}")

            # 2. 동의하지 않은 경우에만 팝업 표시
            if not has_agreed:
                print("[LEGAL] 법적 고지 동의 필요")
                # LegalNoticeDialog 생성 및 on_agree 콜백을 안전하게 래핑합니다.
                try:
                    from modules.legal_notice import LegalNoticeDialog

                    def on_agree():
                        print("[LEGAL] 사용자가 동의했습니다.")
                        # Config 업데이트 (안전하게 처리) - 버전 대신 "agreed" 플래그 저장
                        try:
                            if not config.has_section('Legal'):
                                config.add_section('Legal')
                            config.set('Legal', 'agreed_version', 'agreed')  # 영구 동의 플래그
                            try:
                                with open(CONFIG_FILE_PATH, 'w', encoding='utf-8') as f:
                                    config.write(f)
                            except Exception as e:
                                print(f"[LEGAL] Agreed version write failed: {e}")
                        except Exception as e:
                            print(f"[LEGAL] Config update failed: {e}")

                        # Continue via provided callback if present, else try to show login window
                        try:
                            if continue_callback and callable(continue_callback):
                                try:
                                    continue_callback()
                                except Exception as e:
                                    print(f"[LEGAL] continue callback 호출 실패(무시): {e}")
                            else:
                                try:
                                    self.show_login_window()
                                except Exception as e:
                                    print(f"[LEGAL] show_login_window 호출 실패(무시): {e}")
                        except Exception:
                            pass

                    try:
                        LegalNoticeDialog(self, "v64", on_agree, CONFIG_FILE_PATH)
                    except Exception as e:
                        # 다이얼로그 생성 실패 시 에러창을 띄우지 않고 계속 진행하도록 처리
                        print(f"[LEGAL] LegalNoticeDialog 생성 실패(무시): {e}")
                        try:
                            messagebox.showwarning("법적 고지", "법적 고지 창을 표시할 수 없습니다. 프로그램을 계속합니다.", parent=self)
                        except Exception:
                            pass
                        return True

                except Exception as e:
                    print(f"[LEGAL] 법적 고지 처리 중 오류(무시): {e}")
                    return True

                return False # 로그인 창 표시 보류
            
            return True # 이미 동의함 -> 로그인 창 진행

        except Exception as e:
            print(f"[LEGAL] 체크 중 오류 발생: {e}")
            return True # 오류 시 차단하지 않고 진행

    
    def check_restart_login(self):
        """재시작 시 이전 로그인 정보로 자동 로그인"""
        restart_flag = os.environ.get('APP_RESTARTING')
        if not restart_flag:
            return False
            
        # 환경 변수에서 사용자 정보 복원
        user_id = os.environ.get('RESTART_USER_ID')
        
        if user_id:
            # DB에서 실제 User 객체 가져오기
            session = db_manager.get_session()
            try:
                from database.models import User
                restart_user = session.query(User).filter_by(id=user_id).first()
                
                if restart_user:
                    self.current_user = restart_user
                    print(f"[RESTART] 자동 로그인: {restart_user.username} (권한: {restart_user.role})")
                    
                    # 환경 변수 정리
                    for key in ['APP_RESTARTING', 'RESTART_USER_ID', 'RESTART_USER_IS_ADMIN']:
                        if key in os.environ:
                            del os.environ[key]
                    
                    self.on_login_success(restart_user)
                    return True
                else:
                    print(f"[RESTART] 사용자 ID {user_id}를 찾을 수 없음")
            except Exception as e:
                print(f"[RESTART] 자동 로그인 실패: {e}")
            finally:
                session.close()
        
        return False
    
    def show_initial_signup_window(self):
        """최초 실행 시 첫 관리자 계정 생성을 위한 회원가입 창을 띄웁니다."""
        from modules.signup import SignupWindow
        # on_success 콜백으로 on_login_success를 전달하여 가입 후 바로 로그인되도록 함
        signup_win = SignupWindow(self, is_initial_setup=True, on_success=self.on_first_login_success)
        signup_win.deiconify()
        signup_win.lift()
        signup_win.focus_force()

    def on_first_login_success(self, user):
        """첫 로그인 성공 시 공유 DB 설정을 안내합니다."""
        print(f"{datetime.now()}: 첫 로그인 성공")
        
        # 1. 현재 DB 경로를 config.ini에 저장
        # interpolation=None으로 설정하여 경로에 '%' 문자가 포함되어도 안전하게 처리
        config = configparser.ConfigParser(interpolation=None)
        config.read(CONFIG_FILE_PATH, encoding='utf-8')
        
        current_db_path = db_manager.get_local_db_path()
        
        if not config.has_section('Paths'):
            config.add_section('Paths')
            
        # shared_db_path에는 파일 경로가 아닌 디렉토리 경로를 저장하여 일관성 유지
        try:
            config.set('Paths', 'shared_db_path', os.path.dirname(current_db_path))
        except Exception:
            # 문제 발생 시에도 최소한 파일 경로라도 저장
            config.set('Paths', 'shared_db_path', current_db_path)
        with open(CONFIG_FILE_PATH, 'w', encoding='utf-8') as configfile:
            config.write(configfile)
            
        # 2. 공유 DB 설정 안내
        messagebox.showinfo("초기 설정 안내",
            "첫 관리자 계정이 생성되었습니다.\n\n"
            "다른 사용자와 데이터를 공유하려면 설정 메뉴에서\n"
            "공유 DB 경로를 네트워크 드라이브나 공유 폴더로 변경해주세요.",
            parent=self)
            
        # 3. 일반적인 로그인 성공 처리
        self.on_login_success(user)

    def on_initial_setup(self):
        """DB가 처음 생성될 때 호출되는 콜백."""
        # admin 계정을 미리 생성하지 않음 -> 사용자가 직접 등록하게 함
        print("[초기화] DB 생성 완료 - 관리자 계정은 첫 사용자 등록 시 생성됩니다.")
        pass

    def show_pre_login_splash(self):
        """[v64] 앱 시작 시 프리미엄 모던 카드 스플래시 및 고화질 로고 & 슬릭 프로그레스바"""
        splash = ctk.CTkToplevel(self)
        splash.withdraw()
        splash.overrideredirect(True)

        width, height = 400, 360
        try:
            center_window_on_mouse_display(splash, width=width, height=height)
        except Exception:
            x = (splash.winfo_screenwidth() // 2) - (width // 2)
            y = (splash.winfo_screenheight() // 2) - (height // 2)
            splash.geometry(f'{width}x{height}+{x}+{y}')
        
        splash.lift()
        splash.focus_force()
        
        # 모던 다크/라이트 카드 배경 프레임 (메인 프로그램 테마 색상과 완벽 일치: 다크=#242424, 라이트=#EBEBEB)
        card_frame = ctk.CTkFrame(
            splash, 
            fg_color=("gray86", "gray17"),
            border_width=1,
            border_color=("gray75", "gray30"),
            corner_radius=12
        )
        card_frame.pack(fill="both", expand=True, padx=2, pady=2)
        splash.deiconify()

        # 상단 아이콘 이미지 영역
        img_label = ctk.CTkLabel(card_frame, text="", fg_color="transparent")
        img_label.pack(pady=(25, 8))

        # 로고 로딩
        try:
            icon_path = resource_path("Icon.png")
            if not os.path.exists(icon_path):
                icon_path = resource_path("Icon.ico")
            if os.path.exists(icon_path):
                pil_img = Image.open(icon_path).convert("RGBA")
                pil_img.thumbnail((100, 100), Image.Resampling.LANCZOS)
                splash_img = ctk.CTkImage(light_image=pil_img, dark_image=pil_img, size=pil_img.size)
                img_label.configure(image=splash_img)
        except Exception as err:
            print(f"[PRE-SPLASH] Logo load error: {err}")

        # 시스템 타이틀
        title_label = ctk.CTkLabel(
            card_frame,
            text="화장품 연구소 관리 시스템",
            font=ctk.CTkFont(size=16, weight="bold"),
            text_color=("black", "white")
        )
        title_label.pack(pady=(0, 2))

        sub_title_label = ctk.CTkLabel(
            card_frame,
            text="Cosmetic R&D Platform v64",
            font=ctk.CTkFont(size=11),
            text_color=("gray40", "gray70")
        )
        sub_title_label.pack(pady=(0, 16))

        # 상태 텍스트 및 작업 목록
        task_descriptions = [
            "설정 파일 로드 중...",
            "데이터베이스 연결 중...",
        ] if self.language == 'korean' else [
            "Loading settings...",
            "Connecting to database...",
        ]
        initial_text = "시스템 초기화 준비 중... 0%" if self.language == 'korean' else "Initializing system... 0%"
        done_text = "초기화 완료!" if self.language == 'korean' else "Ready!"

        progress_label = ctk.CTkLabel(
            card_frame, 
            text=initial_text, 
            font=ctk.CTkFont(size=11, weight="bold"),
            text_color=("#3B8ED0", "#1F6AA5")
        )
        progress_label.pack(pady=(0, 6))

        # 메인 프로그램 테마와 100% 동일한 프로그레스바 (#3B8ED0 / #1F6AA5)
        progress_bar = ctk.CTkProgressBar(
            card_frame, 
            width=320,
            height=10,
            corner_radius=5,
            fg_color=("#939BA2", "#4A4D50"),
            progress_color=("#3B8ED0", "#1F6AA5")
        )
        progress_bar.set(0)
        progress_bar.pack(pady=(0, 20))

        splash.update()

        # Patch Logic Import
        # Ensure project root is in sys.path to find build_scripts
        project_root = os.path.dirname(os.path.abspath(__file__))
        if project_root not in sys.path:
            sys.path.insert(0, project_root)
        try:
            from build_scripts import apply_patches
        except ImportError as e:
            print(f"[Patch] 패치 모듈을 로드할 수 없어 건너뜁니다: {e}")

        def init_database():
            try:
                print("\n=== 데이터베이스 초기화 시작 ===")
                
                # 재시작 시 DB 동기화 처리
                if self.handle_restart_db_sync():
                    print("=== 재시작 DB 동기화 완료 ===")
                
                # 재시작 시 DB 이동 처리
                if self.handle_restart_db_move():
                    print("=== 재시작 DB 이동 완료 ===")
                
                db_manager.setup_database(application_path, CONFIG_FILE_PATH, self.on_initial_setup)
                print("=== 데이터베이스 초기화 완료 ===\n")
                return True
            except Exception as e:
                print(f"데이터베이스 초기화 실패: {e}")
                return False

        def run_auto_patches():
            """자동 패치를 수행하고 결과를 스플래시 화면에 표시합니다."""
            try:
                print("\n=== 자동 패치 시작 ===")
                logs = apply_patches.run_patches()
                
                # 로그가 있으면 잠시 보여주기 위해 텍스트 업데이트
                for log in logs:
                    print(f"[PATCH] {log}")
                    progress_label.configure(text=log)
                    splash.update()
                    time.sleep(0.5) # 사용자가 볼 수 있게 짧은 대기
                    
                print("=== 자동 패치 완료 ===\n")
                return True
            except Exception as e:
                print(f"자동 패치 실패: {e}")
                return False

        tasks = [
            (task_descriptions[0], self.load_app_settings),
            ("Applying latest patches...", run_auto_patches), 
            (task_descriptions[1], init_database),
        ]
        
        total_tasks = len(tasks)

        def on_load_complete():
            try:
                # 데이터베이스 연결 테스트
                print("\n=== DB 최종 연결 테스트 시작 ===")
                
                # 만약 db_manager가 준비되지 않았거나 연결 오류가 난 경우 자가 복구 시도
                if not db_manager.Session or not db_manager.engine:
                    print("[자가치유] DB 세션/엔진이 없어 재초기화 시도")
                    db_manager.setup_database(application_path, CONFIG_FILE_PATH, self.on_initial_setup)

                with db_manager.get_session() as session:
                    result = session.execute(text("SELECT 1"))
                    print("  - 연결 테스트 성공")
                    result.fetchall()  # 결과 소비
                print("=== DB 최종 연결 테스트 완료 ===\n")
                
                # DB 동기화 완료 알림 확인
                if os.environ.get('DB_SYNC_COMPLETED') == 'True':
                    print("[재시작-DB동기화] 동기화 완료 알림 준비")
                    if 'DB_SYNC_COMPLETED' in os.environ:
                        del os.environ['DB_SYNC_COMPLETED']
                    # 로그인 후에 알림이 표시되도록 플래그 설정
                    self.show_sync_completed_message = True
                else:
                    self.show_sync_completed_message = False
                
                # DB 작업 완료/오류 알림 확인
                if os.environ.get('DB_OPERATION_ERROR'):
                    self.db_operation_error = os.environ['DB_OPERATION_ERROR']
                    del os.environ['DB_OPERATION_ERROR']
                else:
                    self.db_operation_error = None
                
                if os.environ.get('DB_OPERATION_COMPLETED'):
                    self.db_operation_message = os.environ['DB_OPERATION_MESSAGE']
                    del os.environ['DB_OPERATION_COMPLETED']
                    del os.environ['DB_OPERATION_MESSAGE']
                else:
                    self.db_operation_message = None
                
                # 항상 로그인 창 표시 (사용자가 직접 회원가입 버튼 클릭)
                self.show_login_window()
                    
            except Exception as e:
                print(f"\n[오류] 데이터베이스 1차 테스트 실패: {e}")
                print("[자가치유] 새로운 로컬 DB를 강제 생성하여 연결 복구를 시도합니다...")
                try:
                    # 기존 엔진 및 락 완전 정리 후 재생성 시도
                    db_manager.dispose_engine()
                    db_manager.setup_database(application_path, CONFIG_FILE_PATH, self.on_initial_setup)
                    
                    # 2차 검증
                    with db_manager.get_session() as session:
                        session.execute(text("SELECT 1")).fetchall()
                    print("[자가치유] DB 복구 및 연결 2차 테스트 성공!")
                    self.show_login_window()
                except Exception as e2:
                    error_msg = f"데이터베이스 최종 초기화 실패:\n{str(e2)}\n\n(이전 오류: {e})"
                    print(f"\n[치명적 오류] {error_msg}")
                    
                    # 상세 상태 진단 로그 출력
                    print("\nDB 상태 진단:")
                    print(f"  - Session 객체 존재: {db_manager.Session is not None}")
                    print(f"  - Engine 객체 존재: {db_manager.engine is not None}")
                    
                    messagebox.showerror("데이터베이스 오류", error_msg)
                    self.destroy()


        def run_tasks(task_index=0):
            if task_index < total_tasks:
                description, task_func = tasks[task_index]
                start_progress = task_index / total_tasks
                end_progress = (task_index + 1) / total_tasks
                
                progress_label.configure(text=f"{description}")
                splash.update_idletasks()

                try:
                    task_func()
                    print(f"Task completed successfully: {description}")
                except Exception as e:
                    print(f"Error in task '{description}': {e}")
                    messagebox.showerror("초기화 오류", 
                                       f"다음 작업 중 오류가 발생했습니다:\n{description}\n\n{str(e)}")
                    return
                
                steps = 10
                for i in range(steps + 1):
                    current_progress = start_progress + (end_progress - start_progress) * (i / steps)
                    progress_bar.set(current_progress)
                    progress_label.configure(text=f"{description} {int(current_progress * 100)}%")
                    splash.update_idletasks()
                    time.sleep(0.02)

                self.after(50, lambda: run_tasks(task_index + 1))
            else:
                progress_label.configure(text=done_text)
                progress_bar.set(1)
                splash.update_idletasks()
                
                # run_tasks 완료 후, 내부 검증 단계를 안전 래퍼가 가미된 on_load_complete()에 일임하여 직접 처리
                self.after(300, lambda: (splash.destroy(), on_load_complete()))


        self.after(100, run_tasks)

    def show_post_login_splash(self, on_complete):
        """[v64] 로그인 후 프리미엄 모던 카드 스플래시 및 고화질 로고 & 슬릭 프로그레스바"""
        splash = ctk.CTkToplevel(self)
        splash.withdraw()
        splash.overrideredirect(True)

        width, height = 400, 360
        try:
            center_window_on_mouse_display(splash, width=width, height=height)
        except Exception:
            x = (splash.winfo_screenwidth() // 2) - (width // 2)
            y = (splash.winfo_screenheight() // 2) - (height // 2)
            splash.geometry(f'{width}x{height}+{x}+{y}')
        
        splash.lift()
        splash.focus_force()
        
        # 모던 다크/라이트 카드 배경 프레임 (메인 프로그램 테마와 100% 동일)
        card_frame = ctk.CTkFrame(
            splash, 
            fg_color=("gray86", "gray17"),
            border_width=1,
            border_color=("gray75", "gray30"),
            corner_radius=12
        )
        card_frame.pack(fill="both", expand=True, padx=2, pady=2)
        splash.deiconify()

        # 상단 아이콘 이미지 영역
        img_label = ctk.CTkLabel(card_frame, text="", fg_color="transparent")
        img_label.pack(pady=(25, 8))

        try:
            icon_path = resource_path("Icon.png")
            if not os.path.exists(icon_path):
                icon_path = resource_path("Icon.ico")
            if os.path.exists(icon_path):
                pil_img = Image.open(icon_path).convert("RGBA")
                pil_img.thumbnail((100, 100), Image.Resampling.LANCZOS)
                splash_img = ctk.CTkImage(light_image=pil_img, dark_image=pil_img, size=pil_img.size)
                img_label.configure(image=splash_img)
        except Exception as err:
            print(f"[POST-SPLASH] Logo load error: {err}")

        # 환영 타이틀
        user_name = getattr(self.current_user, 'real_name', None) or getattr(self.current_user, 'username', '사용자')
        title_label = ctk.CTkLabel(
            card_frame,
            text=f"환영합니다, {user_name}님!",
            font=ctk.CTkFont(size=16, weight="bold"),
            text_color=("black", "white")
        )
        title_label.pack(pady=(0, 2))

        sub_title_label = ctk.CTkLabel(
            card_frame,
            text="연구소 데이터베이스 및 워크스페이스 로드 중",
            font=ctk.CTkFont(size=11),
            text_color=("gray40", "gray70")
        )
        sub_title_label.pack(pady=(0, 16))

        # 상태 텍스트
        initial_text = "로그인 성공! 시스템 준비 중... 0%" if self.language == 'korean' else "Initializing... 0%"
        task_descriptions = [
            "이전 세션 정리 중...",
            "최근 작업 이력 로드 중...",
            "메인 화면 구성 중...",
            "테마 적용 중..."
        ] if self.language == 'korean' else [
            "Clearing old session...",
            "Loading user history...",
            "Building main interface...",
            "Applying visual theme..."
        ]
        done_text = "완료!" if self.language == 'korean' else "Done!"

        progress_label = ctk.CTkLabel(
            card_frame, 
            text=initial_text, 
            font=ctk.CTkFont(size=11, weight="bold"),
            text_color=("#3B8ED0", "#1F6AA5")
        )
        progress_label.pack(pady=(0, 6))

        # 모던 슬림 프로그레스바 (메인 프로그램 테마와 100% 동일)
        progress_bar = ctk.CTkProgressBar(
            card_frame, 
            width=320,
            height=10,
            corner_radius=5,
            fg_color=("#939BA2", "#4A4D50"),
            progress_color=("#3B8ED0", "#1F6AA5")
        )
        progress_bar.set(0)
        progress_bar.pack(pady=(0, 20))

        splash.update()

        tasks = [
            (task_descriptions[0], lambda: self.recent_actions.clear()),
            (task_descriptions[1], self.load_recent_actions),
            (task_descriptions[2], self.setup_main_ui),
            (task_descriptions[3], self.update_treeview_style),
        ]
        
        total_tasks = len(tasks)

        def run_tasks(task_index=0):
            if task_index < total_tasks:
                description, task_func = tasks[task_index]
                start_progress = task_index / total_tasks
                end_progress = (task_index + 1) / total_tasks
                
                progress_label.configure(text=f"{description}")
                splash.update_idletasks()

                task_func()
                
                steps = 10
                for i in range(steps + 1):
                    current_progress = start_progress + (end_progress - start_progress) * (i / steps)
                    progress_bar.set(current_progress)
                    progress_label.configure(text=f"{description} {int(current_progress * 100)}%")
                    splash.update_idletasks()
                    time.sleep(0.02)

                self.after(50, lambda: run_tasks(task_index + 1))
            else:
                progress_label.configure(text=done_text)
                progress_bar.set(1)
                splash.update_idletasks()
                self.after(300, lambda: (splash.destroy(), on_complete()))

        self.after(100, run_tasks)

    def on_login_success(self, user):
        print(f"{datetime.now()}: on_login_success 호출")
        self.current_user = user

        if hasattr(self, 'login_window') and self.login_window:
            self.login_window.destroy()
            self.login_window = None

        def show_splash_and_main_ui():
            """로그인 창이 완전히 파괴된 후 스플래시 화면과 메인 UI를 표시합니다."""
            def show_main_window():
                self.center_on_mouse_screen()
                self.deiconify()
                
                # DB 동기화 완료 메시지 표시
                if hasattr(self, 'show_sync_completed_message') and self.show_sync_completed_message:
                    self.after(1000, lambda: messagebox.showinfo(
                        "동기화 완료", 
                        "데이터베이스가 성공적으로 동기화되었습니다.\n"
                        "최신 데이터로 업데이트되었습니다.", 
                        parent=self
                    ))
                    self.show_sync_completed_message = False
                
                # DB 작업 완료 메시지 표시
                if hasattr(self, 'db_operation_message') and self.db_operation_message:
                    self.after(1000, lambda: messagebox.showinfo(
                        "작업 완료", 
                        self.db_operation_message, 
                        parent=self
                    ))
                    self.db_operation_message = None
                
                # DB 작업 오류 메시지 표시
                if hasattr(self, 'db_operation_error') and self.db_operation_error:
                    self.after(1000, lambda: messagebox.showerror(
                        "작업 오류", 
                        f"데이터베이스 작업 중 오류가 발생했습니다:\n{self.db_operation_error}", 
                        parent=self
                    ))
                    self.db_operation_error = None
                
                if self.current_user.is_admin:
                    self.start_db_sync_check()
                print(f"{datetime.now()}: Main window displayed")

                # [자동 업데이트] 실행 시 자동 버전 체크 및 팝업 안내 기동
                self.after(600, self._check_auto_update_on_startup)

            self.show_post_login_splash(on_complete=show_main_window)

        self.after(50, show_splash_and_main_ui)

    def _check_auto_update_on_startup(self):
        """프로그램 실행 시 업데이트 모드가 'auto'인 경우 최신 버전을 감지하여 팝업으로 안내합니다."""
        try:
            from utils.update_manager import UpdateManager, UpdateDialog
            if UpdateManager.get_update_mode() != 'auto':
                return

            def _worker():
                try:
                    is_available, cur_ver, lat_ver, info = UpdateManager.check_for_remote_update()
                    if is_available:
                        def _show_dialog():
                            try:
                                if self.winfo_exists():
                                    UpdateDialog(self, cur_ver, lat_ver, info, is_new=True)
                            except Exception as pop_err:
                                print(f"[Update] 시작 시 업데이트 팝업 오류: {pop_err}")
                        self.after(0, _show_dialog)
                except Exception as e:
                    print(f"[Update] 시작 시 버전 체크 오류: {e}")

            import threading
            threading.Thread(target=_worker, daemon=True).start()
        except Exception as ex:
            print(f"[Update] 자동 업데이트 체크 기동 실패: {ex}")

    def load_app_settings(self):
        """config.ini에서 앱 설정을 로드합니다 (테마, 언어 등)."""
        config = configparser.ConfigParser(interpolation=None)
        try:
            if os.path.exists(CONFIG_FILE_PATH):
                config.read(CONFIG_FILE_PATH, encoding='utf-8')
            
            theme = config.get('Appearance', 'theme', fallback='system')
            ctk.set_appearance_mode(theme)
            
            lang_setting = config.get('Appearance', 'language', fallback='korean').lower()
            self.language = 'english' if lang_setting == 'english' else 'korean'
            print(f"로드된 언어 설정: {self.language}")
        except Exception as e:
            print(f"[경고] config.ini 파일 로드 실패: {e}. 기본 설정으로 계속합니다.")
            ctk.set_appearance_mode("System")
            self.language = "korean"

    def setup_main_ui(self):
        print(f"{datetime.now()}: setup_main_ui 호출")
        
        # 테마에 따른 메뉴 색상 결정 (Dark 모드면 어두운 톤, Light 모드면 밝은 톤)
        current_mode = ctk.get_appearance_mode().lower() # "dark" 또는 "light" (system인 경우 시스템 환경을 감안하여 실제 다크/라이트 반영)
        if current_mode == "system":
            # 실제 현재 모드 판별을 위해 CTkThemeManager 활용
            try:
                bg_color = self._apply_appearance_mode(ctk.ThemeManager.theme["CTk"]["fg_color"])
                if "2b" in bg_color.lower() or "1c" in bg_color.lower() or "12" in bg_color.lower() or "dark" in bg_color.lower() or bg_color.lower() == "gray10":
                    current_mode = "dark"
                else:
                    current_mode = "light"
            except Exception:
                current_mode = "dark" # 기본 폴백

        # 테마에 따른 메뉴 색상 결정 (Dark 모드면 어두운 톤, Light 모드면 밝은 톤)
        current_mode = ctk.get_appearance_mode().lower() # "dark" 또는 "light" (system인 경우 시스템 환경을 감안하여 실제 다크/라이트 반영)
        if current_mode == "system":
            try:
                bg_color = self._apply_appearance_mode(ctk.ThemeManager.theme["CTk"]["fg_color"])
                if "2b" in bg_color.lower() or "1c" in bg_color.lower() or "12" in bg_color.lower() or "dark" in bg_color.lower() or bg_color.lower() == "gray10":
                    current_mode = "dark"
                else:
                    current_mode = "light"
            except Exception:
                current_mode = "dark" # 기본 폴백

        # [v64] Windows 네이티브 메뉴바의 흰색 강제 렌더링을 완전히 제거하고,
        # 세련된 다크 탑바(Custom Dark Menubar)를 프로그램 최상단에 마운트합니다.
        self.config(menu="") # 윈도우 기본 메뉴바 제거

        # 상단 메뉴바 컨테이너 프레임 (다크 배경: #1E1E1E / #181818)
        self.top_menubar_frame = ctk.CTkFrame(
            self,
            height=34,
            corner_radius=0,
            fg_color=("#E0E0E0", "#18191A"), # 라이트 모드 연회색, 다크 모드 딥 차콜
            border_width=1,
            border_color=("#CCCCCC", "#2A2B2D")
        )
        self.top_menubar_frame.grid(row=0, column=0, sticky="ew", padx=0, pady=0)
        self.top_menubar_frame.pack_propagate(False)

        # [v64] 마우스 이동(Hover) 시 차단 없이 스무스하게 메뉴가 따라오는 CTk 기반 모던 드롭다운 구현
        self._current_dropdown_window = None
        self._current_active_btn = None

        # 메뉴 데이터 구조 정의
        menu_data = {}

        # 1. 파일 메뉴
        menu_data['file'] = [
            ("홈 화면", lambda: self.navigate_and_record(FRAME_HOME)),
            ("로그아웃", self.logout),
            ("종료", self.on_closing),
        ]

        # 2. 연구소 메뉴
        if self.current_user.has_research_access():
            menu_data['research'] = [
                ("원료/성분 조회", lambda: self.navigate_and_record("document/lookup")),
                ("처방 목록", lambda: self.navigate_and_record("document/list")),
                ("견적 작성", lambda: self.navigate_and_record("document/quote")),
                ("전성분 분석", lambda: self.navigate_and_record("document/ingredient")),
                ("생산 처방", lambda: self.navigate_and_record("document/production")),
                ("실험일지 (물성 규격)", lambda: self.navigate_and_record("document/property_spec")),
                ("기능성 보고서", lambda: self.navigate_and_record("document/report")),
            ]

        # 3. 품질관리 메뉴
        if self.current_user.has_quality_access():
            menu_data['quality'] = [
                ("COA (성적서)", lambda: self.navigate_and_record("quality/coa")),
                ("MSDS (물질안전보건자료)", lambda: self.navigate_and_record("quality/msds")),
                ("원료목록보고", lambda: self.navigate_and_record("quality/ingredient_report")),
                ("원료 입고검사", lambda: self.navigate_and_record("quality/mat_inspection")),
                ("제품표준서", lambda: self.navigate_and_record("quality/prod_standard")),
                ("제조관리기록서 (BMR)", lambda: self.navigate_and_record("quality/mfg_record")),
                ("안정성 시험 (경시변화)", lambda: self.navigate_and_record("quality/stability_test")),
                ("용기 상용성 시험", lambda: self.navigate_and_record("quality/compatibility_test")),
            ]

        # 4. 데이터 & 설정 메뉴
        if self.current_user.can_access_data_management():
            data_items = [
                ("성분 관리", lambda: self.navigate_and_record("data/ingredient_mgt")),
            ]
            if self.current_user.is_admin or self.current_user.role in ['RQD', 'MSAD']:
                data_items.append(("거래처 관리", lambda: self.navigate_and_record("data/client_mgt")))
                data_items.append(("사용자 관리", lambda: self.navigate_and_record("data/user_mgt")))
            data_items.append(("시스템 설정", lambda: self.navigate_and_record("settings/settings_sub")))
            menu_data['data'] = data_items

        def close_dropdown():
            if self._current_dropdown_window:
                try:
                    self._current_dropdown_window.destroy()
                except Exception:
                    pass
                self._current_dropdown_window = None
            if self._current_active_btn:
                try:
                    self._current_active_btn.configure(fg_color="transparent")
                except Exception:
                    pass
                self._current_active_btn = None

        self._last_dropdown_toggle_time = 0

        def show_dropdown(key, btn_widget):
            cur_time = time.time()
            if self._current_dropdown_window and self._current_active_btn == btn_widget:
                # 같은 버튼 클릭 시 0.2초 이내 중복 토글 방지 및 닫기
                if cur_time - self._last_dropdown_toggle_time > 0.15:
                    close_dropdown()
                return

            close_dropdown()
            items = menu_data.get(key, [])
            if not items:
                return

            self._last_dropdown_toggle_time = cur_time
            self._current_active_btn = btn_widget
            btn_widget.configure(fg_color=("#D0D0D0", "#333333"))

            # 드롭다운 창 생성 (메인 창에 종속되는 모던 플랫 서브 윈도우)
            dropdown = ctk.CTkToplevel(self)
            dropdown.overrideredirect(True)
            dropdown.transient(self)  # 메인 창에 귀속
            self._current_dropdown_window = dropdown

            # 메인 컨테이너 프레임
            container = ctk.CTkFrame(
                dropdown,
                corner_radius=6,
                fg_color=("#F5F5F5", "#202124"),
                border_width=1,
                border_color=("#D0D0D0", "#3C4043")
            )
            container.pack(fill="both", expand=True, padx=0, pady=0)

            # 항목 렌더링 (구분선 없이 균일하고 정갈한 원터치 리스트)
            for label, cmd in items:
                def make_click_cmd(target_cmd):
                    return lambda: (close_dropdown(), target_cmd())

                item_btn = ctk.CTkButton(
                    container,
                    text=label,
                    height=28,
                    anchor="w",
                    font=ctk.CTkFont(size=12),
                    fg_color="transparent",
                    hover_color=("#E8EAED", "#2E3134"),
                    text_color=("#202124", "#E8EAED"),
                    corner_radius=4,
                    command=make_click_cmd(cmd)
                )
                item_btn.pack(fill="x", padx=4, pady=2)

            # 위치 계산 (버튼 바로 아래에 밀착)
            dropdown.update_idletasks()
            x = btn_widget.winfo_rootx()
            y = btn_widget.winfo_rooty() + btn_widget.winfo_height() + 2
            dropdown.geometry(f"+{x}+{y}")
            dropdown.lift()

        def on_hover_btn(key, btn_widget):
            # 이미 다른 메뉴가 열려 있는 상태라면 마우스가 이동하는 순간 해당 메뉴로 즉시 전환
            if self._current_dropdown_window is not None and self._current_active_btn != btn_widget:
                show_dropdown(key, btn_widget)

        def bind_menu_button(btn_widget, key):
            # 마우스 클릭 및 호버 바인딩
            btn_widget.configure(command=lambda: show_dropdown(key, btn_widget))
            for widget in [btn_widget, getattr(btn_widget, '_canvas', None), getattr(btn_widget, '_text_label', None)]:
                if widget:
                    widget.bind("<Button-1>", lambda e, k=key, b=btn_widget: show_dropdown(k, b), add="+")
                    widget.bind("<Enter>", lambda e, k=key, b=btn_widget: on_hover_btn(k, b), add="+")
                    widget.bind("<Motion>", lambda e, k=key, b=btn_widget: on_hover_btn(k, b), add="+")

        # 전역 클릭 시 메뉴 바깥 클릭이면 안전하게 닫기
        def on_global_click(event):
            if not self._current_dropdown_window:
                return

            # 방금 버튼을 클릭해서 드롭다운이 열린 경우(0.15초 이내)는 닫기 무시
            if time.time() - self._last_dropdown_toggle_time < 0.15:
                return

            w = event.widget
            # 드롭다운 창 자체나 그 내부 위젯을 클릭한 경우 닫지 않음
            try:
                if w == self._current_dropdown_window or str(w).startswith(str(self._current_dropdown_window)):
                    return
            except Exception:
                pass

            # 메뉴바 버튼들 클릭한 경우도 내부 처리되도록 허용
            menubar_widgets = [self.top_menubar_frame, self.btn_file]
            if hasattr(self, 'btn_research'): menubar_widgets.append(self.btn_research)
            if hasattr(self, 'btn_quality'): menubar_widgets.append(self.btn_quality)
            if hasattr(self, 'btn_data'): menubar_widgets.append(self.btn_data)

            for mw in menubar_widgets:
                if w == mw or (hasattr(mw, '_text_label') and w == mw._text_label) or (hasattr(mw, '_canvas') and w == mw._canvas):
                    return

            # 그 외의 모든 외부 클릭 시 드롭다운 닫기
            close_dropdown()

        self.bind_all("<Button-1>", on_global_click, add="+")
        self.bind("<Escape>", lambda e: close_dropdown(), add="+")

        btn_font = ctk.CTkFont(size=12, weight="normal")

        # [파일 버튼]
        self.btn_file = ctk.CTkButton(
            self.top_menubar_frame,
            text="파일",
            width=50,
            height=26,
            font=btn_font,
            fg_color="transparent",
            hover_color=("#D0D0D0", "#333333"),
            text_color=("#1A1A1A", "#D4D4D4"),
            anchor="center",
            corner_radius=4
        )
        bind_menu_button(self.btn_file, 'file')
        self.btn_file.pack(side="left", padx=(8, 2), pady=4)

        # [연구소 버튼]
        if self.current_user.has_research_access():
            self.btn_research = ctk.CTkButton(
                self.top_menubar_frame,
                text="연구소",
                width=60,
                height=26,
                font=btn_font,
                fg_color="transparent",
                hover_color=("#D0D0D0", "#333333"),
                text_color=("#1A1A1A", "#D4D4D4"),
                anchor="center",
                corner_radius=4
            )
            bind_menu_button(self.btn_research, 'research')
            self.btn_research.pack(side="left", padx=2, pady=4)

        # [품질관리 버튼]
        if self.current_user.has_quality_access():
            self.btn_quality = ctk.CTkButton(
                self.top_menubar_frame,
                text="품질관리",
                width=68,
                height=26,
                font=btn_font,
                fg_color="transparent",
                hover_color=("#D0D0D0", "#333333"),
                text_color=("#1A1A1A", "#D4D4D4"),
                anchor="center",
                corner_radius=4
            )
            bind_menu_button(self.btn_quality, 'quality')
            self.btn_quality.pack(side="left", padx=2, pady=4)

        # [데이터 & 설정 버튼]
        if self.current_user.can_access_data_management():
            self.btn_data = ctk.CTkButton(
                self.top_menubar_frame,
                text="데이터 & 설정",
                width=90,
                height=26,
                font=btn_font,
                fg_color="transparent",
                hover_color=("#D0D0D0", "#333333"),
                text_color=("#1A1A1A", "#D4D4D4"),
                anchor="center",
                corner_radius=4
            )
            bind_menu_button(self.btn_data, 'data')
            self.btn_data.pack(side="left", padx=2, pady=4)

        # 우측 상단 상태/정보 표시 (사용자명 및 권한 배지)
        role_label = getattr(self.current_user, 'role', '')
        real_name = getattr(self.current_user, 'real_name', '') or getattr(self.current_user, 'username', '')
        self.top_user_badge = ctk.CTkLabel(
            self.top_menubar_frame,
            text=f"{real_name} ({role_label})",
            font=ctk.CTkFont(size=11),
            text_color=("gray40", "gray65")
        )
        self.top_user_badge.pack(side="right", padx=(0, 12), pady=4)

        # [상단 상시 업데이트 확인 버튼]
        self.top_update_btn = ctk.CTkButton(
            self.top_menubar_frame,
            text="🚀 업데이트 확인",
            height=24,
            width=105,
            font=ctk.CTkFont(size=11),
            fg_color="#334155",
            hover_color="#475569",
            text_color="#F8FAFC",
            corner_radius=12,
            command=self.on_top_update_clicked
        )
        self.top_update_btn.pack(side="right", padx=(0, 8), pady=4)

        # [스마트 동기화 알림 배지 버튼] (새 데이터 감지 시 표시되는 조용한 배지)
        self.sync_notice_btn = ctk.CTkButton(
            self.top_menubar_frame,
            text="🔄 새 데이터 감지 | 동기화",
            height=24,
            font=ctk.CTkFont(size=11, weight="bold"),
            fg_color="#0284C7",
            hover_color="#0369A1",
            text_color="#FFFFFF",
            corner_radius=12,
            command=self.on_sync_badge_clicked
        )
        self.pending_shared_db_file = None
        self._sync_badge_hide_timer = None


        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(0, weight=1)

        self.navigation_frame = ctk.CTkFrame(self, corner_radius=0, width=200)
        # self.navigation_frame.grid(row=0, column=0, sticky="nsew") # 왼쪽 사이드바 영역 숨김
        self.navigation_frame.grid_columnconfigure(0, weight=1)

        # Static keys for actions
        self.ACTION_CONFIG = {
            # 연구소 (Document / Research)
            "document/lookup": {"icon": "🔍", "title": "원료/성분 조회"},
            "document/ingredient_lookup": {"icon": "🔍", "title": "원료/성분 조회"},
            "document/list": {"icon": "📋", "title": "처방 목록"},
            "document/formulation_list": {"icon": "📋", "title": "처방 목록"},
            "document/quote": {"icon": "💰", "title": "견적 작성"},
            "document/quotation": {"icon": "💰", "title": "견적 작성"},
            "document/ingredient": {"icon": "🧪", "title": "전성분 분석"},
            "document/ingredient_list": {"icon": "🧪", "title": "전성분 분석"},
            "ingredient_list": {"icon": "🧪", "title": "전성분 분석"},
            "document/production": {"icon": "🏭", "title": "생산 처방"},
            "document/production_formulation": {"icon": "🏭", "title": "생산 처방"},
            "production_formulation": {"icon": "🏭", "title": "생산 처방"},
            "production_form": {"icon": "🏭", "title": "생산 처방"},
            "document/property_spec": {"icon": "📝", "title": "실험일지 (물성 규격)"},
            "document/report": {"icon": "📊", "title": "기능성 보고서"},
            "document/formulation_mgt": {"icon": "℞", "title": self.texts.get('formulation_mgt', '처방 관리')},
            "document/document_sub": {"icon": "📄", "title": self.texts.get('document_sub', '연구 서류')},

            # 품질관리 (Quality Management)
            "quality/coa": {"icon": "📄", "title": "COA (성적서)"},
            "quality/msds": {"icon": "📑", "title": "MSDS (물질안전보건자료)"},
            "quality/ingredient_report": {"icon": "📋", "title": "원료목록보고"},
            "quality/mat_inspection": {"icon": "🔍", "title": "원료 입고검사"},
            "quality/prod_standard": {"icon": "📜", "title": "제품표준서"},
            "quality/mfg_record": {"icon": "🏭", "title": "제조관리기록서 (BMR)"},
            "quality/stability_test": {"icon": "⏳", "title": "안정성 시험 (경시변화)"},
            "quality/compatibility_test": {"icon": "🧴", "title": "용기 상용성 시험"},

            # 데이터 & 설정 (Data & Settings)
            "data/ingredient_mgt": {"icon": "🧪", "title": self.texts.get('ingredient_mgt', '성분 관리')},
            "data/client_mgt": {"icon": "🏢", "title": self.texts.get('client_mgt', '거래처 관리')},
            "data/user_mgt": {"icon": "👥", "title": self.texts.get('user_mgt', '사용자 관리')},
            "settings/settings_sub": {"icon": "⚙️", "title": self.texts.get('settings_sub', '시스템 설정')},
            "package": {"icon": "📦", "title": "문서 관리 (패키지)"},
            "document/package": {"icon": "📦", "title": "문서 관리 (패키지)"},
        }

        # Build reverse lookup from displayed title -> action key for resolving
        # recent/legacy entries that may store localized titles.
        def rebuild_action_title_map():
            self.ACTION_TITLE_TO_KEY = {}
            for k, v in self.ACTION_CONFIG.items():
                title = v.get('title')
                if title:
                    self.ACTION_TITLE_TO_KEY[title] = k

        # initialize the reverse map
        rebuild_action_title_map()

        # Normalize any recent_actions loaded earlier (they may contain
        # localized titles or legacy keys). Replace entries in-place with
        # canonical ACTION_CONFIG keys where possible so icons are resolved.
        try:
            normalized = deque(maxlen=self.recent_actions.maxlen)
            for act in list(self.recent_actions):
                normalized.append(self._normalize_action_name(act))
            self.recent_actions = normalized
        except Exception:
            # Defensive: if normalization fails, keep existing recent_actions
            pass

        # Persist normalized recent actions so subsequent runs don't show '?'
        try:
            self.save_recent_actions()
        except Exception:
            pass

        # Rebuild title map in case normalization or ACTION_CONFIG changed
        rebuild_action_title_map()
        
        # 현재 버전 동적 로드
        try:
            from utils.update_manager import UpdateManager
            current_app_ver = UpdateManager.get_current_version()
        except:
            current_app_ver = "v65.0.3"
            
        self.title(f"R&D Management System ({current_app_ver})" if self.language == "english" else f"화장품 연구소 관리 시스템 ({current_app_ver})")

        self.navigation_frame_label = ctk.CTkLabel(
            self.navigation_frame, 
            text=self.texts["menu"],
            font=ctk.CTkFont(size=16, weight="bold")
        )
        self.navigation_frame_label.grid(row=0, column=0, padx=15, pady=(20, 30))

        button_style = {
            "width": 160,
            "height": 40,
            "font": ctk.CTkFont(size=13),
            "anchor": "center"
        }
        
        self.nav_buttons = {}
        all_nav_items = [
            {"name": FRAME_HOME, "text": self.texts["home"], "requires": None},
            {"name": FRAME_DOCUMENT, "text": self.texts["document"], "requires": "research"},
            {"name": FRAME_QUALITY, "text": self.texts["quality"], "requires": "quality"},
            {"name": FRAME_PACKAGE, "text": "문서 관리", "requires": "package", "hidden": True},
        ]

        current_row = 1
        for item in all_nav_items:
            # 숨김 항목 건너뛰기
            if item.get("hidden", False):
                continue
                
            # 권한 체크
            show_item = False
            if item["requires"] is None:
                show_item = True  # 홈은 모두 표시
            elif item["requires"] == "research":
                show_item = self.current_user.has_research_access()
            elif item["requires"] == "quality":
                show_item = self.current_user.has_quality_access()
            elif item["requires"] == "admin":
                show_item = self.current_user.is_admin
            elif item["requires"] == "package":
                checker = getattr(self.current_user, 'has_package_management_access', None)
                if callable(checker):
                    show_item = checker()
                else:
                    show_item = bool(getattr(self.current_user, 'is_admin', False))
            
            if show_item:
                button = ctk.CTkButton(
                    self.navigation_frame,
                    text=item["text"],
                    command=lambda name=item["name"]: self.navigate_and_record(name),
                    **button_style
                )
                button.grid(row=current_row, column=0, padx=15, pady=8)
                self.nav_buttons[item["name"]] = button
                current_row += 1

        self.navigation_frame.grid_rowconfigure(current_row, weight=1)
        empty_space = ctk.CTkFrame(self.navigation_frame, fg_color="transparent", height=0)
        empty_space.grid(row=current_row, column=0, sticky="nsew")
        current_row += 1
 
        # 데이터 관리 버튼 - 모든 권한이 접근 가능
        if self.current_user.can_access_data_management():
            self.data_button = ctk.CTkButton(
                self.navigation_frame,
                text=self.texts["data"],
                command=lambda: self.navigate_and_record("data/ingredient_mgt"),
                width=140, height=35, font=ctk.CTkFont(size=12),
                fg_color="#E65100", hover_color="#BF360C", anchor="center"
            )
            self.data_button.grid(row=current_row, column=0, padx=15, pady=8)
            current_row += 1

        self.settings_button = ctk.CTkButton(
            self.navigation_frame,
            text=self.texts["settings"],
            command=lambda: self.navigate_and_record("settings/settings_sub"),
            width=140, height=35, font=ctk.CTkFont(size=12), fg_color="gray50", hover_color="gray30", anchor="center"
        )
        self.settings_button.grid(row=current_row, column=0, padx=15, pady=8)
        current_row += 1

        self.logout_button = ctk.CTkButton(
            self.navigation_frame, 
            text=self.texts["logout"],
            command=self.logout,
            width=140,
            height=35,
            font=ctk.CTkFont(size=12),
            fg_color="#D32F2F",
            hover_color="#B71C1C",
            anchor="center"
        )
        self.logout_button.grid(row=current_row, column=0, padx=15, pady=(10, 30))

        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(0, weight=0) # 상단 커스텀 메뉴바
        self.grid_rowconfigure(1, weight=1) # 메인 컨텐츠 영역
        self.grid_rowconfigure(2, weight=0) # 하단 카피라이트

        self.main_content_frame = ctk.CTkFrame(self, corner_radius=0, fg_color="transparent")
        self.main_content_frame.grid(row=1, column=0, sticky="nsew", padx=(20, 20), pady=(10, 5))
        self.main_content_frame.grid_columnconfigure(0, weight=1)
        self.main_content_frame.grid_rowconfigure(0, weight=1)
        
        self.frames = {}

        self.frames[FRAME_HOME] = HomeFrame(
            self.main_content_frame,
            self.current_user,
            self,
            self.recent_actions, # noqa
            self.ACTION_CONFIG,
        )
        self.frames[FRAME_HOME].grid(row=0, column=0, sticky="nsew")
        
        # 지연 초기화(Lazy Loading)를 도입하여 로그인 완료 시에는 FRAME_HOME만 생성하고
        # 나머지 대용량 프레임들은 실제 메뉴 클릭 시 비동기/동적 생성하여 로그인 프리징 제거
        
        # 복구할 수 있는 작업 상태가 있으면 복구하고, 없으면 홈 화면을 띄웁니다.
        if not self.restore_working_state():
            self.select_frame_by_name(FRAME_HOME)

        # 우측 하단 카피라이트 표기 (버전 동적 연동 및 2025-2026 저작권 표기)
        self.copyright_label = ctk.CTkLabel(
            self,
            text=f"{current_app_ver} | Copyright © 2025-2026 luckfortma. All rights reserved.",
            font=ctk.CTkFont(size=10),
            text_color="gray50"
        )
        self.copyright_label.grid(row=2, column=0, sticky="se", padx=20, pady=(0, 6))

    def get_or_create_frame(self, frame_name):
        """요청된 프레임이 없으면 실시간 생성(Lazy Loading)하고 그리드 배치합니다."""
        if frame_name in self.frames:
            return self.frames[frame_name]

        print(f"{datetime.now()}: [LazyLoad] '{frame_name}' 프레임 초기화 시작")
        
        if frame_name == FRAME_SETTINGS:
            self.frames[FRAME_SETTINGS] = SettingsManagementFrame(
                self.main_content_frame, 
                self.current_user, 
                self,
                config_path=CONFIG_FILE_PATH,
                application_path=application_path,
            )
            self.frames[FRAME_SETTINGS].grid(row=0, column=0, sticky="nsew")
            
        elif frame_name == FRAME_DATA:
            self.frames[FRAME_DATA] = DataManagementFrame(
                self.main_content_frame,
                self.current_user,
                self,
            )
            self.frames[FRAME_DATA].grid(row=0, column=0, sticky="nsew")
            
        elif frame_name == FRAME_DOCUMENT:
            from modules.document_management import DocumentManagementFrame
            self.frames[FRAME_DOCUMENT] = DocumentManagementFrame(
                self.main_content_frame,
                self.current_user,
                self,
                texts=self.texts,
                mode="research"
            )
            self.frames[FRAME_DOCUMENT].grid(row=0, column=0, sticky="nsew")
            
        elif frame_name == FRAME_QUALITY:
            from modules.quality_management import QualityManagementFrame
            self.frames[FRAME_QUALITY] = QualityManagementFrame(
                self.main_content_frame,
                self.current_user,
                self,
                texts=self.texts
            )
            self.frames[FRAME_QUALITY].grid(row=0, column=0, sticky="nsew")
            
        elif frame_name == FRAME_PACKAGE:
            from modules.document_management import DocumentManagementFrame
            self.frames[FRAME_PACKAGE] = DocumentManagementFrame(
                self.main_content_frame,
                self.current_user,
                self,
                texts=self.texts,
                mode="package_only"
            )
            self.frames[FRAME_PACKAGE].grid(row=0, column=0, sticky="nsew")
        print(f"{datetime.now()}: [LazyLoad] '{frame_name}' 프레임 초기화 완료")
        
        frame = self.frames.get(frame_name)
        if frame and hasattr(self, 'pending_frame_states') and frame_name in self.pending_frame_states:
            frame_state = self.pending_frame_states.pop(frame_name)
            if hasattr(frame, 'restore_working_state') and callable(frame.restore_working_state):
                try:
                    frame.restore_working_state(frame_state)
                    print(f"[State] [LazyRestore] '{frame_name}' 상태 복구 완료")
                except Exception as e:
                    print(f"[State] [LazyRestore] '{frame_name}' 상태 복구 실패: {e}")

        return frame

    def navigate_and_record(self, name: str):
        """활동을 기록하고 해당 화면으로 이동합니다."""
        self.record_action(name)
        self.select_frame_by_name(name)

    def record_action(self, action_name: str):
        """사용자 활동을 기록하고, 홈 화면을 업데이트합니다."""
        if action_name == FRAME_HOME:
            return

        # Normalize action_name: accept localized titles or legacy keys and
        # convert them to canonical ACTION_CONFIG keys when possible.
        action_name = self._normalize_action_name(action_name)

        allowed_prefixes = ("data/", "document/", "quality/", "settings/", "package/")
        is_allowed = (action_name in self.ACTION_CONFIG) or any(action_name.startswith(p) for p in allowed_prefixes)
        if not is_allowed:
            return

        if action_name in self.recent_actions:
            self.recent_actions.remove(action_name)
        self.recent_actions.appendleft(action_name)

        if action_name not in self.ACTION_CONFIG:
            title = action_name.split('/', 1)[-1] if '/' in action_name else action_name
            self.ACTION_CONFIG[action_name] = {"icon": "❓", "title": title}

        # Keep reverse title map in sync
        try:
            self.ACTION_TITLE_TO_KEY[self.ACTION_CONFIG[action_name]['title']] = action_name
        except Exception:
            pass
        home_frame = self.frames.get(FRAME_HOME)
        if home_frame:
            home_frame.recent_actions = self.recent_actions
            try:
                self.frames[FRAME_HOME].refresh_cards()
            except Exception:
                pass

        print(f"활동 기록: {action_name}. 현재 목록: {list(self.recent_actions)}")

    def load_recent_actions(self):
        """config.ini에서 현재 사용자의 최근 활동을 불러옵니다."""
        config = configparser.ConfigParser(interpolation=None)
        config.read(CONFIG_FILE_PATH, encoding='utf-8')
        section = f"RecentHistory_{self.current_user.username}"
        if config.has_section(section):
            items_str = config.get(section, 'items', fallback='')
            if items_str:
                items = items_str.split(',')[:self.recent_actions.maxlen]
                # Normalize loaded items to canonical keys where possible
                for it in items:
                    self.recent_actions.append(self._normalize_action_name(it))
        print(f"불러온 활동 기록: {list(self.recent_actions)}")

    def _normalize_action_name(self, name: str) -> str:
        """Try to resolve various forms of action identifiers to the
        canonical keys used in ACTION_CONFIG.

        Examples handled:
        - 'data/성분 관리' -> 'data/ingredient_mgt' (matching by displayed title)
        - 'ingredient_mgt' -> 'data/ingredient_mgt' (matching by suffix key)
        - already canonical keys are returned as-is.
        """
        if not name:
            return name

        # If ACTION_CONFIG isn't set up yet (startup path), avoid accessing it
        # because `self.ACTION_CONFIG` would trigger tkinter's __getattr__ and
        # raise. In that case, just return the original name and let later
        # initialization normalize it.
        if not hasattr(self, 'ACTION_CONFIG') or not isinstance(self.ACTION_CONFIG, dict):
            return name

        # already canonical
        if name in self.ACTION_CONFIG:
            return name

        # If name is a displayed title (without the frame prefix), try to map
        # directly from title->key
        title_map = getattr(self, 'ACTION_TITLE_TO_KEY', {})
        if name in title_map:
            return title_map[name]

        # If name includes a frame prefix like 'settings/설정', try to match the
        # right-hand side (tab label) to an action whose key starts with the
        # same frame.
        if '/' in name:
            frame_part, tab_part = name.split('/', 1)
            # check title mapping first
            if tab_part in title_map:
                candidate = title_map[tab_part]
                # ensure candidate has same frame prefix
                if candidate.startswith(frame_part + '/'):
                    return candidate

            # try to match by key suffix (e.g., 'ingredient_mgt')
            for k in self.ACTION_CONFIG.keys():
                if k.endswith('/' + tab_part) or k.endswith(tab_part):
                    return k

        # If given a short internal key like 'ingredient_mgt', attempt to find
        # a canonical key that endswith it
        for k in self.ACTION_CONFIG.keys():
            if k.endswith('/' + name) or k == name:
                return k

        # No resolution found; return original
        return name

    def save_recent_actions(self):
        """현재 사용자의 최근 활동을 config.ini에 저장합니다."""
        if not self.current_user: return
        config = configparser.ConfigParser(interpolation=None)
        config.read(CONFIG_FILE_PATH, encoding='utf-8')

        section = f"RecentHistory_{self.current_user.username}"
        if not config.has_section(section):
            config.add_section(section)

        items_str = ",".join(self.recent_actions)
        config.set(section, 'items', items_str)

        with open(CONFIG_FILE_PATH, 'w', encoding='utf-8') as configfile:
            config.write(configfile)
        print(f"저장된 활동 기록: {items_str}")

    def select_frame_by_name(self, name):
        """요청된 이름의 프레임과 탭으로 화면을 전환합니다."""
        frame_name = name
        tab_name = None
        if '/' in name:
            frame_name, tab_name = name.split('/', 1)
        
        # 현재 선택된 프레임과 탭 기록
        self.current_frame = name

        # 지연 초기화(Lazy Loading) 적용
        frame = self.get_or_create_frame(frame_name)
        if not frame:
            print(f"'{frame_name}' 프레임을 로드할 수 없습니다.")
            return

        if frame_name == FRAME_PACKAGE:
            checker = getattr(self.current_user, 'has_package_management_access', None)
            allowed = checker() if callable(checker) else bool(getattr(self.current_user, 'is_admin', False))
            if not allowed:
                messagebox.showwarning("권한 없음", "문서 관리(패키지) 화면은 RQ 이상만 접근할 수 있습니다.")
                return
        
        frame.tkraise()
        # 홈으로 전환 시, 최신 변경 이력과 카드 섹션을 즉시 새로고침하여 방금 변경한 내용이 보이도록 함
        try:
            if frame_name == FRAME_HOME and hasattr(frame, 'refresh_data'):
                frame.refresh_data()
        except Exception as e:
            print(f"[경고] 홈 새로고침 실패: {e}")
        if tab_name and hasattr(frame, 'switch_to_tab'):
            frame.switch_to_tab(tab_name)

    def open_material_by_id(self, material_id: int):
        """데이터 관리 > 성분 관리로 이동하여 해당 원료를 선택합니다."""
        try:
            # 먼저 데이터 관리/성분 관리 탭으로 이동
            self.select_frame_by_name('data/ingredient_mgt')
            # 프레임이 준비될 시간을 소폭 준 뒤 포커스 시도
            def _do_focus():
                try:
                    data_frame = self.get_or_create_frame(FRAME_DATA)
                    if data_frame and hasattr(data_frame, 'focus_material_by_id'):
                        ok = data_frame.focus_material_by_id(material_id)
                        if not ok:
                            # 한번 더 재시도 (목록 갱신 타이밍 대비)
                            self.after(100, lambda: data_frame.focus_material_by_id(material_id))
                except Exception as e:
                    print(f"[경고] 원료 열기 실패: {e}")
            self.after(50, _do_focus)
        except Exception as e:
            print(f"[경고] 성분 화면 이동 실패: {e}")

    def update_menubar_style(self):
        """현재 테마에 맞게 상단 메뉴바와 하위 메뉴들의 색상을 업데이트합니다."""
        current_mode = ctk.get_appearance_mode().lower()
        if current_mode == "system":
            try:
                bg_color = self._apply_appearance_mode(ctk.ThemeManager.theme["CTk"]["fg_color"])
                if "2b" in bg_color.lower() or "1c" in bg_color.lower() or "12" in bg_color.lower() or "dark" in bg_color.lower() or bg_color.lower() == "gray10":
                    current_mode = "dark"
                else:
                    current_mode = "light"
            except Exception:
                current_mode = "dark"

        if current_mode == "dark":
            m_bg = "#242526"
            m_fg = "#E4E6EB"
            m_abg = "#3A3B3C"
            m_afg = "#FFFFFF"
            bar_bg = ("#E0E0E0", "#18191A")
        else:
            m_bg = "#FFFFFF"
            m_fg = "#050505"
            m_abg = "#E4E6EB"
            m_afg = "#000000"
            bar_bg = ("#E0E0E0", "#18191A")

        if hasattr(self, 'top_menubar_frame') and self.top_menubar_frame:
            try:
                self.top_menubar_frame.configure(fg_color=bar_bg)
            except Exception:
                pass

        for menu_attr in ['file_menu', 'research_menu', 'quality_menu', 'data_menu']:
            if hasattr(self, menu_attr):
                menu = getattr(self, menu_attr)
                if menu:
                    try:
                        menu.configure(bg=m_bg, fg=m_fg, activebackground=m_abg, activeforeground=m_afg)
                    except Exception as e:
                        print(f"[경고] 메뉴 '{menu_attr}' 색상 업데이트 실패: {e}")

    def update_treeview_style(self):
        """현재 테마에 맞게 모든 Treeview의 스타일 및 행 태그(oddrow/evenrow)를 실시간 업데이트합니다."""
        theme = ctk.get_appearance_mode()
        style = ttk.Style()
        
        if theme.lower() == 'light':
            style.theme_use("default")
            tree_bg = "#FFFFFF"
            tree_fg = "#1F2937"
            odd_bg = "#F9FAFB"
            even_bg = "#FFFFFF"
            head_bg = "#F3F4F6"
            head_fg = "#111827"
            head_act = "#E5E7EB"
            sel_bg = "#3B82F6"
            sel_fg = "#FFFFFF"
        else: # 다크 테마 설정 (차분하고 세련된 모던 슬레이트 다크)
            style.theme_use("default")
            tree_bg = "#202124"
            tree_fg = "#E8EAED"
            odd_bg = "#282A2E"
            even_bg = "#202124"
            head_bg = "#2D3035"
            head_fg = "#F1F3F4"
            head_act = "#3C4043"
            sel_bg = "#1A73E8"
            sel_fg = "#FFFFFF"

        style.configure("Treeview", background=tree_bg, foreground=tree_fg, fieldbackground=tree_bg, borderwidth=0, rowheight=26, font=('Malgun Gothic', 9))
        style.configure("Treeview.Heading", background=head_bg, foreground=head_fg, font=('Malgun Gothic', 9, 'bold'), borderwidth=1, relief="flat")
        style.map('Treeview', background=[('selected', sel_bg)], foreground=[('selected', sel_fg)])
        style.map('Treeview.Heading', background=[('active', head_act)])
        style.configure("folder", font=('Malgun Gothic', 9, 'bold'))
        style.configure("group_odd", background=odd_bg)
        style.configure("group_even", background=even_bg)
        style.map("group_odd", background=[('selected', sel_bg)])
        style.map("group_even", background=[('selected', sel_bg)])

        # 모든 현재 열려있는 화면/팝업 내의 ttk.Treeview 위젯을 찾아 태그 색상 동적 갱신
        def _update_all_treeviews(widget):
            try:
                if isinstance(widget, ttk.Treeview):
                    widget.tag_configure("oddrow", background=odd_bg, foreground=tree_fg)
                    widget.tag_configure("evenrow", background=even_bg, foreground=tree_fg)
                    widget.tag_configure("group_odd", background=odd_bg, foreground=tree_fg)
                    widget.tag_configure("group_even", background=even_bg, foreground=tree_fg)
                    widget.tag_configure("material_row", foreground=tree_fg)
                    widget.configure(style="Treeview")
            except Exception:
                pass
            
            try:
                for child in widget.winfo_children():
                    _update_all_treeviews(child)
            except Exception:
                pass

        try:
            _update_all_treeviews(self)
        except Exception as e:
            print(f"[경고] 하위 Treeview 태그 업데이트 실패: {e}")

        try:
            self.update_menubar_style()
        except Exception as e:
            print(f"[경고] 메뉴바 스타일 업데이트 실패: {e}")

        print(f"{datetime.now()}: Treeview 및 메뉴바 스타일을 '{theme}' 테마로 완벽 업데이트했습니다.")

    def autosize_treeview_columns(self, treeview, padding=10, min_width=20, max_width=None):
        """
        Treeview의 각 열과 트리 컬럼('#0') 너비를 해당 열의 가장 긴 텍스트에 맞춰 자동 조절합니다.
        """
        try:
            try:
                font = tkfont.Font(font=treeview.cget("font"))
            except Exception:
                font = tkfont.nametofont("TkDefaultFont")

            try:
                header = treeview.heading('#0').get('text', '') or ''
                max_w = font.measure(str(header))
                for iid in treeview.get_children():
                    txt = treeview.item(iid).get('text', '') or ''
                    w = font.measure(str(txt))
                    if w > max_w:
                        max_w = w
                width = max(min_width, max_w + padding)
                if max_width:
                    width = min(width, max_width)
                treeview.column('#0', width=int(width))
            except Exception:
                pass

            cols = list(treeview["columns"]) if treeview["columns"] else []
            for col in cols:
                header = treeview.heading(col).get('text', '') or col
                max_w = font.measure(str(header))
                for iid in treeview.get_children():
                    try:
                        val = treeview.set(iid, col) or ''
                    except Exception:
                        try:
                            vals = treeview.item(iid).get('values', ()) # noqa
                            val = vals[cols.index(col)] if cols.index(col) < len(vals) else ''
                        except Exception:
                            val = ''
                    w = font.measure(str(val))
                    if w > max_w:
                        max_w = w
                width = max(min_width, max_w + padding)
                if max_width:
                    width = min(width, max_width)
                treeview.column(col, width=int(width))
            self.apply_zebra_striping(treeview)
        except Exception as e:
            print(f"[경고] autosize_treeview_columns 실패: {e}")

    def move_total_between_en_and_cas(self, treeview, total_candidates=None, en_candidates=None, cas_candidates=None):
        """
        Treeview에서 '총합량' 열을 '영문명' 열 뒤, 'CAS No.' 열 앞에 위치시키는 유틸리티.
        """
        try:
            if total_candidates is None:
                total_candidates = ['total', '총합', '총합량', '총량', 'total_amount', 'amount_total']
            if en_candidates is None:
                en_candidates = ['english', '영문', 'eng_name', 'english_name']
            if cas_candidates is None:
                cas_candidates = ['cas', 'cas no', 'cas_no', 'casno']

            cols = list(treeview["columns"]) if treeview["columns"] else []

            def find_col_by_candidates(candidates):
                for c in cols:
                    if any(k.lower() in str(c).lower() for k in candidates):
                        return c
                    try:
                        hdr = treeview.heading(c).get('text', '') or ''
                        if any(k.lower() in str(hdr).lower() for k in candidates):
                            return c
                    except Exception:
                        pass
                try:
                    hdr0 = treeview.heading('#0').get('text', '') or ''
                    if any(k.lower() in str(hdr0).lower() for k in candidates):
                        return '#0'
                except Exception:
                    pass
                return None

            en_col = find_col_by_candidates(en_candidates)
            cas_col = find_col_by_candidates(cas_candidates)
            total_col = find_col_by_candidates(total_candidates)

            if not total_col or not en_col:
                return False

            if total_col == '#0' or en_col == '#0' or cas_col == '#0':
                return False

            if total_col in cols and en_col in cols:
                cols.remove(total_col)
                en_index = cols.index(en_col)
                insert_index = en_index + 1
                if cas_col in cols:
                    cas_index = cols.index(cas_col)
                    if insert_index > cas_index:
                        insert_index = cas_index
                cols.insert(insert_index, total_col)
                treeview["columns"] = tuple(cols)
                return True

            return False
        except Exception as e:
            print(f"[경고] move_total_between_en_and_cas 실패: {e}")
            return False

    def reorder_treeview_columns_by_headers(self, treeview, desired_headers_order, match_partial=True):
        """
        Treeview 컬럼을 헤더 텍스트 기준으로 재배열합니다.
        """
        try:
            cols = list(treeview["columns"]) if treeview["columns"] else []
            col_map = {}
            for c in cols:
                try:
                    hdr = str(treeview.heading(c).get('text', '') or '')
                except Exception:
                    hdr = ''
                col_map[c] = hdr

            root_hdr = ''
            try:
                root_hdr = str(treeview.heading('#0').get('text', '') or '')
            except Exception:
                root_hdr = ''

            def normalize(s: str):
                return ''.join(ch for ch in (s or '').lower() if ch.isalnum())

            norm_map = {c: normalize(h) for c, h in col_map.items()}
            norm_root = normalize(root_hdr)

            new_order = []
            used = set()

            for desired in desired_headers_order:
                nd = normalize(desired)
                found = None
                for c, nh in norm_map.items():
                    if c in used:
                        continue
                    if (nh == nd) or (match_partial and nd in nh) or (match_partial and nh in nd):
                        found = c
                        break
                if not found and norm_root:
                    if (norm_root == nd) or (match_partial and nd in norm_root) or (match_partial and norm_root in nd):
                        found = None
                if found:
                    new_order.append(found)
                    used.add(found)

            for c in cols:
                if c not in used:
                    new_order.append(c)

            if len(new_order) == len(cols) and tuple(new_order) != tuple(cols):
                treeview["columns"] = tuple(new_order)
                return True
            return False
        except Exception as e:
            print(f"[경고] reorder_treeview_columns_by_headers 실패: {e}")
            return False

    def reorder_ingredient_sum_columns(self, treeview):
        """
        전성분 합계 탭(복합 전성분, 서류용) 전용 래퍼.
        """
        desired = ['구분', '국문명', '영문명', '총함량(%)', 'cas no.', '기능']
        res = self.reorder_treeview_columns_by_headers(treeview, desired, match_partial=True)
        try:
            self.normalize_group_column_to_row_numbers(treeview, header_name='구분', force=True)
        except Exception:
            pass
        return res

    def apply_zebra_striping(self, treeview):
        """지정된 Treeview의 모든 행에 oddrow / evenrow 교차 줄무늬를 100% 전수 적용합니다."""
        if not treeview:
            return
        theme = ctk.get_appearance_mode().lower()
        if theme == 'light':
            odd_bg = "#F9FAFB"
            even_bg = "#FFFFFF"
            tree_fg = "#1F2937"
        else:
            odd_bg = "#282A2E"
            even_bg = "#202124"
            tree_fg = "#E8EAED"

        try:
            treeview.tag_configure("oddrow", background=odd_bg, foreground=tree_fg)
            treeview.tag_configure("evenrow", background=even_bg, foreground=tree_fg)
            treeview.tag_configure("group_odd", background=odd_bg, foreground=tree_fg)
            treeview.tag_configure("group_even", background=even_bg, foreground=tree_fg)
            treeview.tag_configure("material_row", foreground=tree_fg)
        except Exception:
            pass

        try:
            for idx, iid in enumerate(treeview.get_children()):
                tag = 'oddrow' if idx % 2 == 0 else 'evenrow'
                current_tags = list(treeview.item(iid, 'tags') or ())
                base_tags = [t for t in current_tags if t not in ['oddrow', 'evenrow', 'group_odd', 'group_even']]
                base_tags.append(tag)
                treeview.item(iid, tags=tuple(base_tags))
        except Exception:
            pass

    def normalize_group_column_to_row_numbers(self, treeview, header_name='구분', force=False):
        """
        '구분' 헤더의 값이 ID 목록일 때 행 번호로 대체하고, 모든 행의 교차 줄무늬를 재적용합니다.
        """
        cols = list(treeview["columns"]) if treeview["columns"] else []
        target_col = None
        header_norm = ''.join(ch for ch in (header_name or '').lower() if ch.isalnum())

        for c in cols:
            try:
                hdr = str(treeview.heading(c).get('text', '') or '')
            except Exception:
                hdr = ''
            nh = ''.join(ch for ch in hdr.lower() if ch.isalnum())
            if header_norm in nh or nh in header_norm:
                target_col = c
                break

        if not target_col:
            try:
                hdr0 = str(treeview.heading('#0').get('text', '') or '')
                nh0 = ''.join(ch for ch in hdr0.lower() if ch.isalnum())
                if header_norm in nh0 or nh0 in header_norm:
                    target_col = '#0'
            except Exception:
                pass

        if target_col:
            listnum_re = re.compile(r'^\s*\d+(?:\s*,\s*\d+\s*)*$')

            for idx, iid in enumerate(treeview.get_children(), start=1):
                try:
                    if target_col == '#0':
                        cur = str(treeview.item(iid).get('text', '') or '')
                    else:
                        cur = str(treeview.set(iid, target_col) or '')
                except Exception:
                    cur = ''

                need_replace = force or (cur and listnum_re.match(cur))
                if need_replace:
                    new_val = str(idx)
                    if target_col == '#0':
                        try:
                            treeview.item(iid, text=new_val)
                        except Exception:
                            pass
                    else:
                        try:
                            treeview.set(iid, target_col, new_val)
                            continue
                        except Exception:
                            pass
                        try:
                            vals = list(treeview.item(iid).get('values', ())) # noqa
                            col_index = cols.index(target_col) if target_col in cols else None
                            if col_index is not None:
                                while len(vals) <= col_index:
                                    vals.append('')
                                vals[col_index] = new_val
                                treeview.item(iid, values=tuple(vals))
                        except Exception:
                            pass

        self.apply_zebra_striping(treeview)
        return

    def logout(self):
        print(f"{datetime.now()}: logout 호출")

        try:
            self.save_recent_actions()
            LoginWindow.disable_auto_login_on_logout(CONFIG_FILE_PATH, self.current_user.username)
            print(f"{datetime.now()}: 자동 로그인 설정 해제 완료")
        except Exception as e:
            print(f"{datetime.now()}: 자동 로그인 해제 중 오류: {e}")

        self.current_user = None
        for widget in self.winfo_children():
            widget.destroy()
        self.withdraw()
        self.show_login_window()

    def handle_restart_db_sync(self):
        """재시작 시 DB 동기화를 처리합니다"""
        try:
            sync_required = os.environ.get('DB_SYNC_REQUIRED')
            sync_source = os.environ.get('DB_SYNC_SOURCE')
            
            if sync_required == 'True' and sync_source:
                print(f"[재시작-DB동기화] 동기화 처리 시작: {sync_source}")
                
                # 환경 변수 정리
                if 'DB_SYNC_REQUIRED' in os.environ:
                    del os.environ['DB_SYNC_REQUIRED']
                if 'DB_SYNC_SOURCE' in os.environ:
                    del os.environ['DB_SYNC_SOURCE']
                
                # 실제 DB 파일 동기화 수행
                if os.path.exists(sync_source):
                    import shutil
                    local_db_path = os.path.join(application_path, db_manager.get_db_relative_path(), "cosmetic.db")
                    
                    # 기존 DB 연결 완전히 해제
                    try:
                        db_manager.dispose_engine()
                        print("[재시작-DB동기화] 기존 DB 연결 해제 완료")
                    except Exception as e:
                        print(f"[재시작-DB동기화] DB 연결 해제 중 오류: {e}")
                    
                    # 잠시 대기 (파일 잠금 해제)
                    import time
                    time.sleep(1)
                    
                    # 파일 복사
                    shutil.copy2(sync_source, local_db_path)
                    print(f"[재시작-DB동기화] DB 파일 복사 완료: {local_db_path}")
                    
                    # 동기화 완료 플래그 설정
                    os.environ['DB_SYNC_COMPLETED'] = 'True'
                    
                    return True
                else:
                    print(f"[재시작-DB동기화] 소스 파일을 찾을 수 없음: {sync_source}")
                    
            return False
            
        except Exception as e:
            print(f"[재시작-DB동기화] 처리 중 오류: {e}")
            return False

    def handle_restart_db_move(self):
        """재시작 시 DB를 새 경로로 이동하는 작업을 처리합니다"""
        try:
            move_required = os.environ.get('DB_MOVE_REQUIRED')
            new_db_path = os.environ.get('DB_MOVE_TARGET_DB')
            new_excel_path = os.environ.get('DB_MOVE_TARGET_EXCEL')
            
            if move_required == 'True' and new_db_path and new_excel_path:
                print(f"[재시작-DB이동] DB 이동 처리 시작: {new_db_path}, Excel: {new_excel_path}")
                
                # 환경 변수 정리
                for key in ['DB_MOVE_REQUIRED', 'DB_MOVE_TARGET_DB', 'DB_MOVE_TARGET_EXCEL']:
                    if key in os.environ:
                        del os.environ[key]
                
                current_db_path = db_manager.db_path
                db_backup_path = f"{current_db_path}.backup"
                
                # 기존 DB 연결 해제
                try:
                    db_manager.dispose_engine()
                    print("[재시작-DB이동] 기존 DB 연결 해제 완료")
                except Exception as e:
                    print(f"[재시작-DB이동] DB 연결 해제 중 오류: {e}")
                
                # 잠시 대기 (파일 잠금 해제)
                import time
                import shutil
                time.sleep(1.5)
                
                # 백업 생성
                shutil.copy2(current_db_path, db_backup_path)
                print(f"[재시작-DB이동] 백업 생성 완료: {db_backup_path}")
                
                # 대상 디렉토리 생성
                target_dir = os.path.dirname(new_db_path)
                os.makedirs(target_dir, exist_ok=True)
                print(f"[재시작-DB이동] 대상 디렉토리 생성 완료: {target_dir}")
                
                # 파일 이동 (copy + delete)
                shutil.copy2(current_db_path, new_db_path)
                print(f"[재시작-DB이동] DB 파일 복사 완료: {new_db_path}")
                
                # 원본 파일 삭제
                os.remove(current_db_path)
                print(f"[재시작-DB이동] 원본 DB 파일 삭제 완료")
                
                # 파일 속성 정상화 (읽기 전용/숨김 파일 해제)
                from database.db_manager import ensure_file_accessible
                ensure_file_accessible(new_db_path)
                print("[재시작-DB이동] 새 DB 파일 속성 정상화 완료")
                
                # 설정 저장 (database_dir와 shared_db_path 둘 다 설정)
                config = configparser.ConfigParser(interpolation=None)
                config.read(CONFIG_FILE_PATH, encoding='utf-8')
                if not config.has_section('Paths'):
                    config.add_section('Paths')
                config.set('Paths', 'database_dir', target_dir)
                config.set('Paths', 'shared_db_path', target_dir)
                config.set('Paths', 'excel_dir', new_excel_path)
                with open(CONFIG_FILE_PATH, 'w', encoding='utf-8') as f:
                    config.write(f)
                
                print("[재시작-DB이동] 설정 저장 완료")
                
                # 백업 삭제
                if os.path.exists(db_backup_path):
                    try:
                        os.remove(db_backup_path)
                        print("[재시작-DB이동] 백업 파일 삭제 완료")
                    except Exception:
                        pass
                
                os.environ['DB_OPERATION_COMPLETED'] = 'move'
                os.environ['DB_OPERATION_MESSAGE'] = f"DB가 새 경로로 이동되었습니다: {new_db_path}"
                
                return True
                
            return False
        except Exception as e:
            print(f"[재시작-DB이동] 처리 중 오류: {e}")
            os.environ['DB_OPERATION_ERROR'] = str(e)
            return False

    def restart_app(self, save_state=False, **env_vars):
        """현재 상태를 저장한 뒤 프로그램을 재시작합니다 (환경변수로 작업 전달)
        
        Args:
            save_state: 작업 상태를 저장하고 복원할지 여부 (기본값: False)
        """
        try:
            print(f"[재시작] 프로그램 재시작 준비 중... 전달 인자: {env_vars}")
            
            # 1. 필요시 현재 상태 저장
            if save_state:
                self.save_working_state()
            
            # 2. DB 연결 해제
            db_manager.dispose_engine()
            print("[재시작] DB 연결 해제 완료")
            
            # 3. 사용자 및 상태 전달용 환경 변수 사전 구성
            pass_env = dict(env_vars)
            if self.current_user:
                pass_env['APP_RESTARTING'] = 'True'
                pass_env['RESTART_USER_ID'] = str(self.current_user.id)
                if save_state:
                    pass_env['RESTORE_STATE'] = 'True'
            
            # 4. PyInstaller 임시 디렉토리 충돌을 방지하기 위한 정돈된 환경 변수 생성
            clean_env = get_clean_subproc_env(pass_env)
            
            # 5. 새 프로세스 시작
            import subprocess
            import sys
            
            exe_path = sys.executable if getattr(sys, 'frozen', False) else os.path.abspath(__file__)
            safe_restart_application(exe_path, clean_env)
            
        except Exception as e:
            print(f"[재시작] 재시작 중 오류: {e}")
            messagebox.showerror("재시작 오류", f"프로그램을 재시작할 수 없습니다:\n{e}", parent=self)

    def save_working_state(self):
        """현재 화면 상태와 입력값을 로컬에 백업합니다."""
        if not self.current_user:
            return
        try:
            import json
            state = {
                "user_id": self.current_user.id,
                "username": self.current_user.username,
                "timestamp": datetime.now().isoformat(),
                "recent_actions": list(self.recent_actions),
                "current_frame": getattr(self, 'current_frame', FRAME_HOME),
                "frames": {}
            }
            # 각 프레임이 상태 저장을 지원하는 경우 상태 정보를 수집
            for frame_name, frame in self.frames.items():
                if hasattr(frame, 'get_working_state') and callable(frame.get_working_state):
                    try:
                        state["frames"][frame_name] = frame.get_working_state()
                    except Exception as e:
                        print(f"[State] {frame_name} 상태 수집 실패: {e}")
            
            state_file = os.path.join(application_path, 'temp_state.json')
            with open(state_file, 'w', encoding='utf-8') as f:
                json.dump(state, f, ensure_ascii=False, indent=4)
            print(f"[State] 현재 작업 상태 백업 완료: {state_file}, 프레임: {state['current_frame']}")
        except Exception as e:
            print(f"[State] 작업 상태 백업 중 오류: {e}")

    def restore_working_state(self) -> bool:
        """이전 저장된 작업 상태를 복구합니다 (RESTORE_STATE 환경변수가 True일 때만)"""
        if os.environ.get('RESTORE_STATE') != 'True':
            state_file = os.path.join(application_path, 'temp_state.json')
            if os.path.exists(state_file):
                try:
                    os.remove(state_file)
                    print("[State] 기존 상태 파일 삭제 (RESTORE_STATE가 False이므로)")
                except Exception:
                    pass
            return False
        
        state_file = os.path.join(application_path, 'temp_state.json')
        if not os.path.exists(state_file):
            return False
        try:
            import json
            with open(state_file, 'r', encoding='utf-8') as f:
                state = json.load(f)
            
            # 사용자 일치 여부 검증
            if not self.current_user or state.get("username") != self.current_user.username:
                return False
                
            print(f"[State] 작업 상태 복구 시작 (저장일시: {state.get('timestamp')})")
            
            # 최근 활동 목록 복원
            if "recent_actions" in state:
                self.recent_actions = deque(state["recent_actions"], maxlen=5)
                
            # 각 프레임 상태를 지연 복원하기 위해 변수에 저장
            self.pending_frame_states = state.get("frames", {})
            
            # 저장된 프레임으로 복원 (after로 지연 실행)
            saved_frame = state.get("current_frame", FRAME_HOME)
            print(f"[State] 저장된 프레임으로 복원 예정: {saved_frame}")
            self.after(100, lambda: self.select_frame_by_name(saved_frame))
                
            # 복구 완료 후 파일 삭제
            try:
                os.remove(state_file)
                if 'RESTORE_STATE' in os.environ:
                    del os.environ['RESTORE_STATE']
            except Exception as e:
                print(f"[State] 임시 상태 파일 삭제 실패: {e}")
                
            return True
        except Exception as e:
            print(f"[State] 작업 상태 복구 중 오류: {e}")
            return False

    def on_closing(self):
        """프로그램이 종료될 때 호출되는 함수입니다."""
        print(f"{datetime.now()}: 프로그램 종료 중...")
        try:
            # 1. DB 동기화 타이머 중지
            self.stop_db_sync_check()
            
            # 2. 설정 및 활동 기록 저장
            self.save_app_settings()
            self.save_recent_actions()
            
            # 3. DB 연결 완전히 해제
            print(f"{datetime.now()}: DB 연결 해제 중...")
            db_manager.dispose_engine()
            print(f"{datetime.now()}: DB 연결 해제 완료")
            
            # 4. 모든 자식 창 강제 종료
            for child in self.winfo_children():
                try:
                    if hasattr(child, 'destroy'):
                        child.destroy()
                except:
                    pass
            
            # 5. 메인 창 파괴
            self.destroy()
            
            # 6. 완전한 프로세스 종료
            print(f"{datetime.now()}: 프로그램 종료 완료")
            
        except Exception as e:
            print(f"{datetime.now()}: 종료 중 오류 발생: {e}")
        finally:
            # 강제 종료 (모든 스레드와 프로세스 완전 종료)
            try:
                # 메인 루프 종료 시도
                self.quit()
            except:
                pass
            try:
                self.destroy()
            except:
                pass
            # Windows 환경에서 드물게 프로세스가 남는 경우를 대비한 최후의 수단
            try:
                if os.name == 'nt':
                    import threading, ctypes
                    def _force_kill():
                        try:
                            ctypes.windll.kernel32.TerminateProcess(ctypes.windll.kernel32.GetCurrentProcess(), 0)
                        except Exception:
                            pass
                    t = threading.Timer(0.5, _force_kill)
                    t.daemon = True
                    t.start()
            except Exception:
                pass

            # 즉시/지연 이중 종료 보장
            try:
                # 1) 짧게 지연된 강제 종료 (데몬 타이머)
                import threading
                t2 = threading.Timer(0.2, lambda: os._exit(0))
                t2.daemon = True
                t2.start()
            except Exception:
                pass
            try:
                # 2) 정상 종료 시도
                sys.exit(0)
            except Exception:
                # 3) 최후의 수단: 즉시 종료
                os._exit(0)

    def get_config_value(self, section, option, fallback=None):
        """config.ini에서 값을 읽어옵니다."""
        config = configparser.ConfigParser()
        config.read(CONFIG_FILE_PATH, encoding='utf-8')
        return config.get(section, option, fallback=fallback)

    def load_app_settings(self):
        """어플리케이션의 주요 설정을 config.ini에서 로드합니다."""
        config = configparser.ConfigParser(interpolation=None)
        try:
            if os.path.exists(CONFIG_FILE_PATH):
                config.read(CONFIG_FILE_PATH, encoding='utf-8')
            
            theme = config.get('Appearance', 'theme', fallback='system')
            ctk.set_appearance_mode(theme)
            
            lang_setting = config.get('Appearance', 'language', fallback='korean').lower()
            self.language = 'english' if lang_setting == 'english' else 'korean'
            print(f"로드된 언어 설정: {self.language}")
        except Exception as e:
            print(f"[경고] config.ini 파일 로드 실패: {e}. 기본 설정으로 계속합니다.")
            ctk.set_appearance_mode("System")
            self.language = "korean"

    def save_app_settings(self):
        """어플리케이션의 주요 UI 설정을 저장합니다."""
        if not hasattr(self, 'frames') or FRAME_DOCUMENT not in self.frames:
            return
        config = configparser.ConfigParser(interpolation=None)
        config.read(CONFIG_FILE_PATH, encoding='utf-8')
        if not config.has_section('Appearance'):
            config.add_section('Appearance')
        icon_size = self.frames[FRAME_DOCUMENT].icon_size_slider.get()
        config.set('Appearance', 'folder_icon_size', str(icon_size))
        with open(CONFIG_FILE_PATH, 'w', encoding='utf-8') as configfile:
            config.write(configfile)
            
        # 문서 관리 탭의 설정 저장
        doc_frame = self.frames.get(FRAME_DOCUMENT)
        if doc_frame and hasattr(doc_frame, 'save_journal_settings'):
            doc_frame.save_journal_settings(config)

    def center_on_mouse_screen(self):
        """마우스 커서가 위치한 모니터의 중앙에 창을 배치하고, 해당 모니터 기준 비율로 크기를 조절합니다."""
        try:
            if sys.platform.startswith('win'):
                import ctypes

                class POINT(ctypes.Structure):
                    _fields_ = [("x", ctypes.c_long), ("y", ctypes.c_long)]

                class RECT(ctypes.Structure):
                    _fields_ = [("left", ctypes.c_long), ("top", ctypes.c_long), ("right", ctypes.c_long), ("bottom", ctypes.c_long)]

                class MONITORINFO(ctypes.Structure):
                    _fields_ = [("cbSize", ctypes.c_ulong), ("rcMonitor", RECT), ("rcWork", RECT), ("dwFlags", ctypes.c_ulong)]

                user32 = ctypes.windll.user32
                pt = POINT()
                if not user32.GetCursorPos(ctypes.byref(pt)):
                    raise RuntimeError("GetCursorPos failed")

                MONITOR_DEFAULTTONEAREST = 2
                hmon = user32.MonitorFromPoint(pt, MONITOR_DEFAULTTONEAREST)
                if not hmon:
                    raise RuntimeError("MonitorFromPoint failed")

                mi = MONITORINFO()
                mi.cbSize = ctypes.sizeof(MONITORINFO)
                if not user32.GetMonitorInfoW(hmon, ctypes.byref(mi)):
                    raise RuntimeError("GetMonitorInfoW failed")

                work = mi.rcWork
                mon_w = max(100, work.right - work.left)
                mon_h = max(100, work.bottom - work.top)

                width = int(mon_w * 0.70)
                height = int(mon_h * 0.75)

                center_window_on_mouse_display(self, width=width, height=height)
                self.minsize(int(mon_w * 0.5), int(mon_h * 0.6))
                return

            self.update_idletasks()
            sw = self.winfo_screenwidth()
            sh = self.winfo_screenheight()
            width = int(sw * 0.70)
            height = int(sh * 0.75)
            center_window_on_mouse_display(self, width=width, height=height)
            self.minsize(int(sw * 0.5), int(sh * 0.6))
        except Exception:
            self.update_idletasks()
            sw = self.winfo_screenwidth()
            sh = self.winfo_screenheight()
            width = int(sw * 0.70)
            height = int(sh * 0.75)
            x = (sw // 2) - (width // 2)
            y = (sh // 2) - (height // 2)
            self.geometry(f"{width}x{height}+{x}+{y}")
            self.minsize(int(sw * 0.5), int(sh * 0.6))

    def recreate_main_ui(self):
        """메인 UI를 재생성하여 언어 변경 등을 반영합니다."""
        for widget in self.winfo_children():
            widget.destroy()

        self.texts = get_texts(self.language)

        self.setup_main_ui()
        self.update_treeview_style()

    def refresh_data_in_all_frames(self):
        """모든 프레임을 순회하며 refresh_data 메소드가 있으면 호출합니다."""
        print("모든 프레임의 데이터 새로고침 시작...")
        for frame_name, frame_instance in self.frames.items():
            if hasattr(frame_instance, 'refresh_data'):
                try:
                    print(f"  - {frame_name} 프레임 새로고침 중...")
                    frame_instance.refresh_data()
                except Exception as e:
                    print(f"[오류] 프레임 '{frame_name}' 새로고침 실패: {e}")

    def check_for_app_updates(self):
        """서버 또는 공유 폴더에서 최신 업데이트 정보를 확인합니다."""
        def _check_thread():
            try:
                import json
                import urllib.request
                
                config = configparser.ConfigParser(interpolation=None)
                config.read(CONFIG_FILE_PATH, encoding='utf-8')
                
                update_server_url = config.get('Update', 'update_server_url', fallback=None)
                
                if not update_server_url:
                    shared_db_path = config.get('Paths', 'shared_db_path', fallback=None)
                    if shared_db_path and os.path.exists(shared_db_path):
                        fallback_path = os.path.join(shared_db_path, 'updates', 'latest.json')
                        if os.path.exists(fallback_path):
                            update_server_url = fallback_path
                
                if not update_server_url:
                    return
                
                from utils.update_manager import UpdateManager
                current_version = UpdateManager.get_current_version()
                curr_tuple = UpdateManager.parse_version_tuple(current_version)
                
                latest_info = None
                if update_server_url.startswith("http://") or update_server_url.startswith("https://"):
                    req = urllib.request.Request(update_server_url, headers={'User-Agent': 'Mozilla/5.0'})
                    with urllib.request.urlopen(req, timeout=10) as response:
                        latest_info = json.loads(response.read().decode('utf-8'))
                else:
                    if os.path.exists(update_server_url):
                        with open(update_server_url, 'r', encoding='utf-8') as f:
                            latest_info = json.load(f)
                
                if not latest_info:
                    return
                
                latest_version = latest_info.get("version")
                changelog = latest_info.get("changelog", "변경 사항 없음")
                
                if latest_version:
                    latest_tuple = UpdateManager.parse_version_tuple(latest_version)
                    if latest_tuple > curr_tuple:
                        self.after(50, lambda: self.prompt_user_for_update(latest_version, changelog))
            except Exception as e:
                print(f"[UPDATE-CHECK] Failed to check for updates: {e}")
                
        import threading
        t = threading.Thread(target=_check_thread)
        t.daemon = True
        t.start()

    def prompt_user_for_update(self, latest_version, changelog):
        """사용자에게 업데이트 진행 여부를 묻는 알림창을 표시합니다."""
        home_frame = self.frames.get(FRAME_HOME)
        if home_frame and hasattr(home_frame, 'notice_textbox'):
            try:
                home_frame.notice_textbox.configure(state="normal")
                notice_text = f"📢 [신규 업데이트 알림] 새로운 버전({latest_version})이 출시되었습니다!\n"
                notice_text += f"변경 사항:\n{changelog}\n"
                notice_text += f"--------------------------------------------------\n"
                home_frame.notice_textbox.insert("1.0", notice_text)
                home_frame.notice_textbox.configure(state="disabled")
            except Exception:
                pass
        
        msg = f"새로운 업데이트({latest_version})가 준비되었습니다.\n\n[변경 사항]\n{changelog}\n\n지금 프로그램을 종료하고 자동 업데이트를 진행하시겠습니까?"
        if messagebox.askyesno("업데이트 알림", msg, parent=self):
            self.execute_auto_update()

    def execute_auto_update(self):
        """런처를 구동하여 자동 업데이트를 적용하고 앱을 종료합니다."""
        try:
            import subprocess
            import os
            import sys
            
            parent_dir = os.path.dirname(application_path)
            paths_to_try = [
                os.path.join(parent_dir, 'launcher.exe'),
                os.path.join(application_path, 'launcher.exe'),
                os.path.join(application_path, 'launcher.py'),
                os.path.join(parent_dir, 'launcher.py'),
            ]
            
            launcher_exec = None
            for path in paths_to_try:
                if os.path.exists(path):
                    launcher_exec = path
                    break
            
            if launcher_exec:
                clean_env = get_clean_subproc_env()
                flags = subprocess.CREATE_NEW_PROCESS_GROUP if os.name == 'nt' else 0
                if launcher_exec.endswith('.py'):
                    subprocess.Popen([sys.executable, launcher_exec], env=clean_env, creationflags=flags)
                else:
                    subprocess.Popen([launcher_exec], env=clean_env, creationflags=flags)
                
                self.on_closing()
            else:
                messagebox.showerror("업데이트 오류", "업데이트 설치 프로그램(launcher.exe)을 찾을 수 없습니다.\n수동 업데이트를 진행해주세요.", parent=self)
        except Exception as e:
            messagebox.showerror("업데이트 오류", f"업데이트 실행 중 오류가 발생했습니다: {e}", parent=self)

    def start_db_sync_check(self):
        """공유 DB의 변경 사항을 주기적으로 확인하는 타이머를 시작합니다."""
        self.initialize_db_sync_baseline()
        self.db_sync_timer = self.after(60000, self.start_periodic_sync_check)

    def initialize_db_sync_baseline(self):
        """DB 동기화 기준선을 조용히 설정합니다."""
        try:
            config = configparser.ConfigParser(interpolation=None)
            config.read(CONFIG_FILE_PATH, encoding='utf-8')
            shared_db_path = config.get('Paths', 'shared_db_path', fallback=None)

            def resolve_shared_file(path):
                if not path:
                    return None
                path = path.strip().strip('"').strip("'")
                if path.lower().endswith('.db') or os.path.basename(path).lower() == 'cosmetic.db':
                    return path
                return os.path.join(path, 'cosmetic.db')

            shared_db_file = resolve_shared_file(shared_db_path)

            if shared_db_file and os.path.exists(shared_db_file):
                shared_db_stat = os.stat(shared_db_file)
                self.last_shared_db_info = (shared_db_stat.st_size, int(shared_db_stat.st_mtime))
                print(f"[DB동기화] 기준선 설정 완료: 파일={shared_db_file}, 크기={self.last_shared_db_info[0]}, 수정시간={self.last_shared_db_info[1]}")

                self.last_change_log_id = 0
                try:
                    import sqlite3
                    conn = sqlite3.connect(shared_db_file, timeout=2.0)
                    cur = conn.cursor()
                    cur.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='change_log'")
                    if cur.fetchone():
                        cur.execute("SELECT IFNULL(MAX(id), 0) FROM change_log")
                        row = cur.fetchone()
                        self.last_change_log_id = int(row[0] or 0)
                        print(f"[DB동기화] 변경 로그 기준선 ID={self.last_change_log_id}")
                    conn.close()
                except Exception as e:
                    print(f"[DB동기화] 변경 로그 기준선 설정 실패(무시): {e}")
            else:
                print("[DB동기화] 공유 DB 경로가 설정되지 않음 또는 파일 없음")
        except Exception as e:
            print(f"[DB동기화] 기준선 설정 중 오류: {e}")

    def show_sync_badge(self, summary_text: str, shared_db_file: str):
        """상단 메뉴바에 연구원을 방해하지 않는 조용한 동기화 알림 배지를 표시합니다."""
        try:
            if not hasattr(self, 'sync_notice_btn') or not self.sync_notice_btn:
                return

            self.pending_shared_db_file = shared_db_file

            if hasattr(self, '_sync_badge_hide_timer') and self._sync_badge_hide_timer:
                try:
                    self.after_cancel(self._sync_badge_hide_timer)
                except Exception:
                    pass
                self._sync_badge_hide_timer = None

            display_text = f"🔄 새 데이터 감지 ({summary_text}) | 동기화"
            self.sync_notice_btn.configure(
                text=display_text,
                fg_color="#D97706",
                hover_color="#B45309",
                state="normal"
            )
            # 상단 메뉴바의 사용자 배지 바로 왼쪽에 부드럽게 마운트
            self.sync_notice_btn.pack(side="right", padx=(0, 10), pady=4)
            print(f"[DB동기화] 상단 알림 배지 활성화: {display_text}")
        except Exception as e:
            print(f"[DB동기화] 알림 배지 표시 실패: {e}")

    def hide_sync_badge(self):
        """상단 메뉴바의 동기화 알림 배지를 숨깁니다."""
        try:
            if hasattr(self, 'sync_notice_btn') and self.sync_notice_btn:
                self.sync_notice_btn.pack_forget()
            self.pending_shared_db_file = None
            self._sync_badge_hide_timer = None
        except Exception as e:
            print(f"[DB동기화] 알림 배지 숨김 실패: {e}")

    def on_sync_badge_clicked(self):
        """연구원이 상단 동기화 배지를 클릭했을 때 실시간으로 안전하게 최신 데이터를 반영합니다."""
        if not self.pending_shared_db_file:
            self.hide_sync_badge()
            return

        target_db = self.pending_shared_db_file
        try:
            self.sync_notice_btn.configure(text="⏳ 동기화 진행 중...", state="disabled", fg_color="#4B5563")
            self.update_idletasks()

            # 조용한 동기화 수행
            success = self.sync_with_shared_db_safe(target_db, show_success_popup=False)

            if success:
                self.sync_notice_btn.configure(text="✅ 최신 데이터 반영 완료", fg_color="#059669")
                # 3초 후 배지 자동 숨김
                self._sync_badge_hide_timer = self.after(3000, self.hide_sync_badge)
            else:
                self.sync_notice_btn.configure(text="⚠️ 동기화 실패 (재시도)", fg_color="#DC2626", state="normal")
        except Exception as e:
            print(f"[DB동기화] 배지 클릭 동기화 처리 실패: {e}")
            self.hide_sync_badge()

    def on_top_update_clicked(self):
        """상단 메뉴바의 [업데이트 확인] 버튼 클릭 시 최신 버전을 비동기로 조회하고 다이얼로그를 표시합니다."""
        try:
            self.top_update_btn.configure(text="⏳ 확인 중...", state="disabled")
        except Exception:
            pass

        def _worker():
            try:
                from utils.update_manager import UpdateManager, UpdateDialog
                is_available, cur_ver, lat_ver, info = UpdateManager.check_for_remote_update()
            except Exception as e:
                from utils.update_manager import UpdateManager
                is_available, cur_ver, lat_ver, info = False, UpdateManager.get_current_version(), UpdateManager.get_current_version(), {"summary": f"조회 중 오류 발생: {e}"}

            def _show():
                try:
                    self.top_update_btn.configure(text="🚀 업데이트 확인", state="normal")
                    from utils.update_manager import UpdateDialog
                    UpdateDialog(self, cur_ver, lat_ver, info, is_new=is_available)
                except Exception as ex:
                    print(f"[Main] 업데이트 다이얼로그 오류: {ex}")

            self.after(0, _show)

        import threading
        threading.Thread(target=_worker, daemon=True).start()

    def start_periodic_sync_check(self):
        """주기적인 DB 동기화 검사를 시작합니다 (기본 60초 주기)."""
        self.check_shared_db()
        
        interval_ms = 60000
        try:
            config = configparser.ConfigParser(interpolation=None)
            config.read(CONFIG_FILE_PATH, encoding='utf-8')
            sec = config.getint('Sync', 'check_interval_sec', fallback=60)
            if sec >= 15:
                interval_ms = sec * 1000
        except Exception:
            interval_ms = 60000

        self.db_sync_timer = self.after(interval_ms, self.start_periodic_sync_check)

    def stop_db_sync_check(self):
        """DB 동기화 검사 타이머를 중지합니다."""
        if self.db_sync_timer:
            self.after_cancel(self.db_sync_timer)
            self.db_sync_timer = None

    def update_db_sync_baseline(self):
        """DB 동기화 기준선을 현재 상태로 업데이트합니다 (자체 변경사항 반영으로 내 PC 알림 방지)."""
        try:
            config = configparser.ConfigParser(interpolation=None)
            config.read(CONFIG_FILE_PATH, encoding='utf-8')
            shared_db_path = config.get('Paths', 'shared_db_path', fallback=None)

            def resolve_shared_file(path):
                if not path:
                    return None
                path = path.strip().strip('"').strip("'")
                if path.lower().endswith('.db') or os.path.basename(path).lower() == 'cosmetic.db':
                    return path
                return os.path.join(path, 'cosmetic.db')

            shared_db_file = resolve_shared_file(shared_db_path)

            if shared_db_file and os.path.exists(shared_db_file):
                shared_db_stat = os.stat(shared_db_file)
                self.last_shared_db_info = (shared_db_stat.st_size, int(shared_db_stat.st_mtime))

                # change_log 최신 ID로 기준선 갱신
                try:
                    import sqlite3
                    conn = sqlite3.connect(shared_db_file, timeout=2.0)
                    cur = conn.cursor()
                    cur.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='change_log'")
                    if cur.fetchone():
                        cur.execute("SELECT IFNULL(MAX(id), 0) FROM change_log")
                        row = cur.fetchone()
                        self.last_change_log_id = int(row[0] or 0)
                        print(f"[DB동기화] 기준선 갱신 완료: ID={self.last_change_log_id}")
                    conn.close()
                except Exception as e:
                    print(f"[DB동기화] 기준선 ID 갱신 실패(무시): {e}")

                # 배지가 떠 있었다면 조용히 숨김
                self.hide_sync_badge()
            else:
                print("[DB동기화] 공유 DB 경로 없음 - 기준선 업데이트 스킵")
        except Exception as e:
            print(f"[DB동기화] 기준선 업데이트 중 오류: {e}")

    def check_shared_db(self):
        """공유 DB 파일의 change_log를 확인하고 타 연구원의 변경사항이 있을 때만 상단 배지에 조용히 알립니다."""
        try:
            config = configparser.ConfigParser(interpolation=None)
            config.read(CONFIG_FILE_PATH, encoding='utf-8')

            # 동기화 알림 모드 확인 (disabled이면 검사 생략)
            sync_mode = config.get('Sync', 'mode', fallback='badge')
            if sync_mode == 'disabled':
                return

            shared_db_path = config.get('Paths', 'shared_db_path', fallback=None)
            if not shared_db_path:
                return

            def resolve_shared_file(path):
                if not path:
                    return None
                if '#' in path:
                    path = path.split('#')[0]
                path = path.strip().strip('"').strip("'")
                if path.lower().endswith('.db') or os.path.basename(path).lower() == 'cosmetic.db':
                    return path
                return os.path.join(path, 'cosmetic.db')

            shared_db_file = resolve_shared_file(shared_db_path)
            if not shared_db_file or not os.path.exists(shared_db_file):
                return

            # change_log 기반 신규 변경 수집
            import sqlite3
            last_id = getattr(self, 'last_change_log_id', 0)

            conn = sqlite3.connect(shared_db_file, timeout=2.0)
            cur = conn.cursor()
            cur.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='change_log'")
            if not cur.fetchone():
                conn.close()
                return

            cur.execute("SELECT id, table_name, operation, entity_name FROM change_log WHERE id > ? ORDER BY id", (last_id,))
            rows = cur.fetchall()
            conn.close()

            if not rows:
                # 신규 변경 없음 -> 알림 불필요
                return

            # 변경된 테이블 및 항목 집계
            table_counts = {}
            sample_names = {}
            for r_id, tbl, op, ename in rows:
                table_counts[tbl] = table_counts.get(tbl, 0) + 1
                if ename and tbl not in sample_names:
                    sample_names[tbl] = str(ename)

            # 사용자 권한/사용처에 따른 관심 테이블 매핑
            interested = set()
            try:
                if hasattr(self.current_user, 'has_research_access') and self.current_user.has_research_access():
                    interested.update({"formulations", "formulation_items"})
                if hasattr(self.current_user, 'can_view_material_data') and self.current_user.can_view_material_data():
                    interested.update({"materials", "ingredients"})
                if hasattr(self.current_user, 'can_view_client_data') and self.current_user.can_view_client_data():
                    interested.update({"clients"})
                if getattr(self.current_user, 'is_admin', False):
                    interested.update({"users"})
            except Exception:
                interested = {"formulations", "materials", "ingredients", "clients"}

            relevant_tables = set(table_counts.keys()) & interested
            if not relevant_tables:
                # 관심 없는 테이블 변경이면 기준선만 넘기고 알림 생략
                self.last_change_log_id = rows[-1][0]
                return

            # 사람이 읽기 쉬운 요약 문자열 생성
            summary_parts = []
            if 'formulations' in table_counts or 'formulation_items' in table_counts:
                cnt = table_counts.get('formulations', 0) + table_counts.get('formulation_items', 0)
                name = sample_names.get('formulations', '')
                summary_parts.append(f"처방({name})" if name else f"처방 {cnt}건")
            if 'materials' in table_counts or 'ingredients' in table_counts:
                cnt = table_counts.get('materials', 0) + table_counts.get('ingredients', 0)
                name = sample_names.get('materials', '') or sample_names.get('ingredients', '')
                summary_parts.append(f"원료({name})" if name else f"원료 {cnt}건")
            if 'clients' in table_counts:
                cnt = table_counts['clients']
                name = sample_names.get('clients', '')
                summary_parts.append(f"거래처({name})" if name else f"거래처 {cnt}건")
            if 'users' in table_counts:
                summary_parts.append(f"사용자 {table_counts['users']}건")

            summary_text = ", ".join(summary_parts) if summary_parts else f"데이터 {len(rows)}건"

            # 기준선 ID를 최신으로 올려 중복 감지 방지
            self.last_change_log_id = rows[-1][0]

            # 상단 배지 알림 띄우기 (강제 모달 팝업 없이 조용하게 표시)
            self.show_sync_badge(summary_text, shared_db_file)

        except (FileNotFoundError, OSError):
            pass
        except Exception as e:
            print(f"[DB동기화] 공유 DB 확인 중 오류(무시): {e}")

    def sync_with_shared_db_safe(self, shared_db_path, show_success_popup=False):
        """안전한 공유 DB 동기화 - 실시간으로 데이터를 다시 불러오고 모든 프레임을 새로고침합니다."""
        try:
            print(f"[DB동기화] 실시간 동기화 시작: {shared_db_path}")

            def resolve_shared_file(path):
                if not path:
                    return None
                path = path.strip().strip('"').strip("'")
                if path.lower().endswith('.db') or os.path.basename(path).lower() == 'cosmetic.db':
                    return path
                return os.path.join(path, 'cosmetic.db')

            shared_db_file = resolve_shared_file(shared_db_path)

            if not shared_db_file or not os.path.exists(shared_db_file):
                print(f"[DB동기화] 공유 DB 파일을 찾을 수 없습니다: {shared_db_file}")
                return False

            local_db_path = db_manager.get_local_db_path()

            # 1. DB 연결 완전히 해제
            try:
                db_manager.dispose_engine()
                import gc
                gc.collect()
            except Exception as e:
                print(f"[DB동기화] DB 연결 해제 중 오류: {e}")

            # 2. 파일 복사 (재시도 로직 포함)
            import shutil
            import time
            max_retries = 3
            copy_success = False

            for attempt in range(max_retries):
                try:
                    # 백업 생성
                    backup_path = local_db_path + ".backup"
                    if os.path.exists(local_db_path):
                        try:
                            shutil.copy2(local_db_path, backup_path)
                        except Exception:
                            pass

                    # 공유 DB를 로컬로 복사
                    shutil.copy2(shared_db_file, local_db_path)
                    copy_success = True
                    break
                except Exception as copy_error:
                    print(f"[DB동기화] 파일 복사 시도 {attempt + 1}/{max_retries} 실패: {copy_error}")
                    time.sleep(0.5)

            # 3. DB 재연결
            try:
                db_manager.setup_database(application_path, CONFIG_FILE_PATH, None)
            except Exception as reconnect_error:
                print(f"[DB동기화] DB 재연결 실패: {reconnect_error}")
                return False

            # 4. 모든 화면 데이터 새로고침
            try:
                self.refresh_data_in_all_frames()
                print("[DB동기화] 모든 프레임 데이터 새로고침 완료")
            except Exception as refresh_error:
                print(f"[DB동기화] 데이터 새로고침 중 오류: {refresh_error}")

            # 5. 동기화 기준선 업데이트
            self.update_db_sync_baseline()

            if show_success_popup:
                messagebox.showinfo("동기화 완료", "데이터베이스가 성공적으로 동기화되었습니다.\n최신 데이터로 업데이트되었습니다.", parent=self)

            print("[DB동기화] 실시간 동기화 완료")
            return True

        except Exception as e:
            print(f"[DB동기화] 실시간 동기화 중 오류: {e}")
            return False
    def sync_with_shared_db(self, shared_db_path):
        """기존 동기화 메서드 (레거시 호환용)"""
        print("[DB동기화] 기존 동기화 메서드 호출 - 안전한 실시간 동기화로 전환")
        self.sync_with_shared_db_safe(shared_db_path, show_success_popup=True)

    def restart_program(self):
        """프로그램을 재시작합니다."""
        restart_error = None
        
        try:
            print(f"{datetime.now()}: 프로그램 재시작 시작...")
            
            # 1. DB 연결 완전히 해제
            try:
                print(f"{datetime.now()}: DB 연결 해제 중...")
                db_manager.dispose_engine()
                print(f"{datetime.now()}: DB 연결 해제 완료")
            except Exception as db_error:
                error_msg = f"DB 해제 중 오류: {db_error}"
                print(f"{datetime.now()}: {error_msg}")
                restart_error = error_msg
            
            # 2. 설정 저장
            try:
                self.save_app_settings()
                self.save_recent_actions()
                print(f"{datetime.now()}: 설정 저장 완료")
            except Exception as save_error:
                error_msg = f"설정 저장 중 오류: {save_error}"
                print(f"{datetime.now()}: {error_msg}")
                if not restart_error:
                    restart_error = error_msg
            
            # 3. 타이머 중지
            try:
                self.stop_db_sync_check()
                print(f"{datetime.now()}: 타이머 중지 완료")
            except Exception as timer_error:
                error_msg = f"타이머 중지 중 오류: {timer_error}"
                print(f"{datetime.now()}: {error_msg}")
                if not restart_error:
                    restart_error = error_msg
            
            # 4. GUI 리소스 정리
            try:
                for widget in self.winfo_children():
                    widget.destroy()
                self.withdraw()
                print(f"{datetime.now()}: GUI 리소스 정리 완료")
            except Exception as gui_error:
                error_msg = f"GUI 정리 중 오류: {gui_error}"
                print(f"{datetime.now()}: {error_msg}")
                if not restart_error:
                    restart_error = error_msg
            
            # 5. 파일 및 DB 정리 완료 대기 (재시작 시 파일 접근 보장)
            import time
            time.sleep(2.0)  # 대기 시간 증가하여 파일 잠금 해제 보장
            
            # 6. 추가 파일 정리 확인
            try:
                # 설정 파일과 데이터 파일 접근 가능 확인
                import gc
                gc.collect()  # 가비지 컬렉션으로 리소스 정리
                print(f"{datetime.now()}: 리소스 정리 완료")
            except Exception as cleanup_error:
                print(f"{datetime.now()}: 리소스 정리 중 오류: {cleanup_error}")

            # 6. 오류 발생 시 사용자에게 알리고 수동 재시작 안내
            if restart_error:
                try:
                    result = messagebox.askyesno("재시작 오류 발생", 
                                               f"재시작 준비 중 오류가 발생했습니다:\n\n{restart_error}\n\n"
                                               f"그래도 재시작을 시도하시겠습니까?\n\n"
                                               f"'아니요'를 선택하면 수동으로 프로그램을 다시 실행해주세요.", 
                                               parent=None)  # parent=None으로 독립 창
                    
                    if not result:
                        print(f"{datetime.now()}: 사용자가 재시작 취소")
                        return
                        
                except Exception as msg_error:
                    print(f"{datetime.now()}: 메시지박스 표시 실패: {msg_error}")

            # 7. 새 프로세스 시작 (경로와 환경 설정 보장)
            print(f"{datetime.now()}: 새 프로세스 시작...")
            
            try:
                # 실행 파일 경로 결정
                if getattr(sys, 'frozen', False):
                    executable_path = sys.executable
                else:
                    executable_path = os.path.abspath(__file__)
                
                # 사용자 정보 및 재시작 상태 전달용 환경 변수 구성
                pass_env = {}
                if hasattr(self, 'current_user') and self.current_user:
                    pass_env['APP_RESTARTING'] = 'True'
                    pass_env['RESTART_USER_ID'] = str(self.current_user.id)
                    pass_env['RESTART_USER_IS_ADMIN'] = str(self.current_user.is_admin)
                    print(f"[재시작] 사용자 정보 전달: {self.current_user.id} (관리자: {self.current_user.is_admin})")

                # VBS 1.2초 무창 안전 독립 재실행
                safe_restart_application(executable_path, pass_env)
            except Exception as process_error:
                error_msg = f"새 프로세스 시작 실패: {process_error}"
                print(f"{datetime.now()}: {error_msg}")
                try:
                    messagebox.showerror("재시작 실패", 
                                       f"{error_msg}\n\n"
                                       f"프로그램을 수동으로 종료하고 다시 실행해주세요.", 
                                       parent=None)
                except Exception:
                    pass
                return
            
        except Exception as e:
            error_msg = f"프로그램 재시작 실패: {e}"
            print(f"{datetime.now()}: {error_msg}")
            
            # 재시작 실패 시 사용자에게 수동 재시작 안내
            try:
                messagebox.showerror("심각한 재시작 오류", 
                                   f"자동 재시작에 실패했습니다.\n\n"
                                   f"오류: {str(e)}\n\n"
                                   f"프로그램을 수동으로 종료하고 다시 실행해주세요.", 
                                   parent=None)
            except Exception:
                pass

_old_get_texts = get_texts
def safe_get_texts(lang):
    try:
        texts = _old_get_texts(lang) or {}
    except Exception:
        texts = {}

    defaults_korean = {
        'export_formulation_name_empty': '내보낼 제형명을 입력해주세요.',
        'warning': '경고',
    }
    defaults_english = {
        'export_formulation_name_empty': 'Please enter a name for the formulation to export.',
        'warning': 'Warning',
    }

    lang_key = (lang or '').lower()
    defaults = defaults_english if 'eng' in lang_key or lang_key.startswith('en') else defaults_korean

    for k, v in defaults.items():
        if k not in texts:
            texts[k] = v

    return texts

try:
    _translation.get_texts = safe_get_texts
    get_texts = safe_get_texts
except Exception as e:
    print(f"[경고] 번역 래퍼 적용 실패: {e}")

def check_sqlite_availability():
    """SQLite 모듈 가용성을 확인합니다."""
    try:
        import sqlite3
        # 간단한 메모리 DB 생성 테스트
        conn = sqlite3.connect(':memory:')
        conn.execute('CREATE TABLE test (id INTEGER)')
        conn.close()
        print("[STARTUP] SQLite 모듈 정상 작동 확인")
        return True
    except Exception as e:
        print(f"[STARTUP] SQLite 모듈 오류: {e}")
        
        # 오류 발생 시 상세 진단
        print("[STARTUP] SQLite 진단 시작...")
        
        try:
            import _sqlite3
            print("[STARTUP] _sqlite3 모듈 가져오기 성공")
        except ImportError as ie:
            print(f"[STARTUP] _sqlite3 모듈 가져오기 실패: {ie}")
        
        if hasattr(sys, '_MEIPASS'):
            import os
            meipass_files = [f for f in os.listdir(sys._MEIPASS) if 'sqlite' in f.lower()]
            print(f"[STARTUP] _MEIPASS 내 SQLite 관련 파일들: {meipass_files}")
        
        return False

if __name__ == "__main__":
    # 윈도우 작업표시줄 아이콘 정합성을 위한 AppUserModelID 설정
    try:
        import ctypes
        myappid = 'Luckfortma.CosRQD.MainApp.v65.0.3'
        ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(myappid)
    except Exception as appid_err:
        print(f"[STARTUP] AppUserModelID 설정 실패: {appid_err}")
        
    # 단일 인스턴스 체크 (프로그램 중복 실행 방지)
    if not check_single_instance():
        print("[STARTUP] 프로그램이 이미 실행 중입니다. 종료합니다.")
        sys.exit(0)
    
    # PyInstaller 임시 폴더 관련 전역 오류 처리
    try:
        if getattr(sys, 'frozen', False) and hasattr(sys, '_MEIPASS'):
            temp_path = sys._MEIPASS
            if not os.path.exists(temp_path) or not os.access(temp_path, os.R_OK):
                print(f"[STARTUP] PyInstaller 임시 폴더 접근 문제 감지: {temp_path}")
                print("[STARTUP] 오류가 발생할 수 있지만 계속 진행합니다...")
    except Exception as temp_error:
        print(f"[STARTUP] 임시 폴더 체크 중 오류: {temp_error}")
    
    # SQLite 가용성 확인
    if not check_sqlite_availability():
        import tkinter as tk
        from tkinter import messagebox
        
        root = tk.Tk()
        root.withdraw()
        
        messagebox.showerror(
            "시스템 오러",
            "SQLite 데이터베이스 모듈을 로드할 수 없습니다.\n\n"
            "이는 빌드 과정에서 필요한 모듈이 포함되지 않았기 때문입니다.\n"
            "개발자에게 문의해주세요.\n\n"
            "오류 코드: SQLITE_MODULE_MISSING"
        )
        sys.exit(1)
    
    # CustomTkinter 테마 설정 (안전한 방식)
    try:
        ctk.set_default_color_theme("blue")
        print("[STARTUP] CustomTkinter 테마 설정 완료")
    except Exception as theme_error:
        print(f"[WARNING] CustomTkinter 테마 설정 실패: {theme_error}")
        try:
            # 기본 테마로 폴백
            ctk.set_default_color_theme("dark-blue")
            print("[STARTUP] 기본 테마로 폴백 완료")
        except Exception as fallback_error:
            print(f"[WARNING] 기본 테마도 실패: {fallback_error}")
            # 테마 없이 진행

    # Hardware binding validation removed to allow unrestricted execution
    
    try:
        app = App()
        app.mainloop()
    except Exception as fatal_err:
        import traceback
        import webbrowser
        import urllib.parse
        
        # 1. 예외 역추적 로그 포맷팅
        err_msg = traceback.format_exc()
        
        # 2. 클립보드 복사 시도
        try:
            import pyperclip
            pyperclip.copy(err_msg)
            copied = True
        except Exception:
            try:
                import tkinter as tk
                r = tk.Tk()
                r.withdraw()
                r.clipboard_clear()
                r.clipboard_append(err_msg)
                r.update()
                copied = True
            except Exception:
                copied = False
                
        # 3. 사용자 안내 및 이메일 전송 팝업
        import tkinter as tk
        from tkinter import messagebox
        
        root = tk.Tk()
        root.withdraw()
        
        info_msg = "프로그램 실행 중 치명적인 오류가 발생했습니다.\n\n"
        if copied:
            info_msg += "오류 세부 정보가 자동으로 [클립보드]에 복사되었습니다.\n"
        else:
            info_msg += "오류 정보 클립보드 복사에 실패했습니다.\n"
            
        info_msg += "이메일 보내기 창이 열리면 오류 내용을 붙여넣기(Ctrl+V)하여 보내주세요.\n\n"
        info_msg += f"오류 요약: {fatal_err}"
        
        messagebox.showerror("실행 오류", info_msg)
        
        # 4. 이메일 보내기(기본 메일 클라이언트 브라우저 링크 호출)
        try:
            email_addr = "luckfortma@naver.com"  # 사용자 이메일 주소
            subject = urllib.parse.quote("[오류 보고] 화장품 연구소 관리 시스템 구동 에러")
            body = urllib.parse.quote("아래에 클립보드에 복사된 에러 로그를 붙여넣기(Ctrl+V) 해주세요:\n\n\n\n" + err_msg[:500])
            mail_url = f"mailto:{email_addr}?subject={subject}&body={body}"
            webbrowser.open(mail_url)
        except Exception as mail_err:
            print(f"[ERROR] 메일 호출 실패: {mail_err}")
            
        sys.exit(1)
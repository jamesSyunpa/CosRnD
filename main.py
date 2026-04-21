# main.py
import customtkinter as ctk
import configparser
import sys
from tkinter import messagebox
from tkinter import ttk
from collections import deque
import os
import tkinter.font as tkfont
import re
import subprocess
import time
from PIL import Image

# ==================== 단일 인스턴스 실행 체크 ====================
def check_single_instance():
    """프로그램이 이미 실행 중인지 확인하고, 중복 실행을 방지합니다."""
    try:
        if sys.platform.startswith('win'):
            # Windows: Named Mutex 사용
            import win32event
            import win32api
            import winerror
            
            mutex_name = "Global\\RnD_Platform_Cosmetic_Management_System_Mutex"
            try:
                # 뮤텍스 생성 시도
                mutex = win32event.CreateMutex(None, False, mutex_name)
                last_error = win32api.GetLastError()
                
                if last_error == winerror.ERROR_ALREADY_EXISTS:
                    # 이미 실행 중
                    import tkinter as tk
                    root = tk.Tk()
                    root.withdraw()
                    messagebox.showerror(
                        "프로그램 실행 오류",
                        "프로그램이 이미 실행 중입니다.\n"
                        "작업 관리자에서 기존 프로세스를 종료하거나,\n"
                        "실행 중인 프로그램 창을 확인해주세요.",
                        parent=root
                    )
                    root.destroy()
                    return False
                
                # 뮤텍스를 전역 변수로 저장 (프로그램 종료 시까지 유지)
                globals()['_app_mutex'] = mutex
                print("[단일 인스턴스] 프로그램 실행 허용")
                return True
                
            except Exception as e:
                print(f"[단일 인스턴스] Windows 뮤텍스 생성 실패: {e}")
                # 뮤텍스 생성 실패 시에도 프로그램은 계속 실행
                return True
        else:
            # 다른 OS: 락 파일 사용
            import fcntl
            lock_file_path = os.path.join(
                os.path.expanduser('~'),
                '.rnd_platform_lock'
            )
            
            try:
                lock_file = open(lock_file_path, 'w')
                fcntl.flock(lock_file.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
                
                # 락 파일을 전역 변수로 저장 (프로그램 종료 시까지 유지)
                globals()['_app_lock_file'] = lock_file
                print("[단일 인스턴스] 프로그램 실행 허용")
                return True
                
            except IOError:
                # 이미 실행 중
                import tkinter as tk
                root = tk.Tk()
                root.withdraw()
                messagebox.showerror(
                    "프로그램 실행 오류",
                    "프로그램이 이미 실행 중입니다.\n"
                    "실행 중인 프로그램 창을 확인해주세요.",
                    parent=root
                )
                root.destroy()
                return False
            except Exception as e:
                print(f"[단일 인스턴스] 락 파일 생성 실패: {e}")
                return True
                
    except Exception as e:
        print(f"[단일 인스턴스] 체크 중 오류 발생: {e}")
        # 오류 발생 시에도 프로그램은 계속 실행
        return True

# ==================== PyInstaller 경로 처리 ====================
def resource_path(relative_path):
    """ Get absolute path to resource, works for dev and for PyInstaller """
    try:
        # PyInstaller creates a temp folder and stores path in _MEIPASS
        base_path = sys._MEIPASS
        # 임시 폴더 접근 가능 여부 확인
        if not os.path.exists(base_path) or not os.access(base_path, os.R_OK):
            raise Exception(f"_MEIPASS 경로 접근 불가: {base_path}")
        print(f"[RESOURCE] Using _MEIPASS: {base_path}")
    except Exception as e:
        base_path = os.path.dirname(os.path.abspath(__file__))
        print(f"[RESOURCE] _MEIPASS 사용 불가 ({e}), 스크립트 디렉토리 사용: {base_path}")
    
    # 아이콘 파일 특별 처리 (더 포괄적)
    if relative_path.lower() in ['icon.ico', 'Icon.ico', 'app.ico', 'application.ico']:
        icon_variants = [
            'Icon.ico',           # 대문자 I
            'icon.ico',           # 소문자 i
            'ICON.ICO',           # 모두 대문자
            'Icon.ICO',           # 혼합
            'app.ico',            # 앱 아이콘
            'application.ico',    # 어플리케이션 아이콘
            'main.ico',           # 메인 아이콘
        ]
        
        # 기본 경로에서 검색
        for variant in icon_variants:
            icon_path = os.path.join(base_path, variant)
            if os.path.exists(icon_path):
                print(f"[RESOURCE] Found icon at: {icon_path}")
                return icon_path
        
        # data 폴더에서 검색
        data_path = os.path.join(base_path, 'data')
        if os.path.exists(data_path):
            for variant in icon_variants:
                icon_path = os.path.join(data_path, variant)
                if os.path.exists(icon_path):
                    print(f"[RESOURCE] Found icon in data folder: {icon_path}")
                    return icon_path
        
        # assets 폴더에서 검색
        assets_path = os.path.join(base_path, 'assets')
        if os.path.exists(assets_path):
            for variant in icon_variants:
                icon_path = os.path.join(assets_path, variant)
                if os.path.exists(icon_path):
                    print(f"[RESOURCE] Found icon in assets folder: {icon_path}")
                    return icon_path
        
        # 아이콘을 찾지 못한 경우 디렉토리 내용 출력 (더 상세히)
        try:
            base_files = [f for f in os.listdir(base_path) if f.lower().endswith(('.ico', '.png', '.jpg', '.jpeg'))]
            print(f"[RESOURCE] Available image files in {base_path}: {base_files}")
            
            # 하위 폴더들도 검사
            for subdir in ['data', 'assets', 'icons', 'images']:
                subdir_path = os.path.join(base_path, subdir)
                if os.path.exists(subdir_path):
                    sub_files = [f for f in os.listdir(subdir_path) if f.lower().endswith(('.ico', '.png', '.jpg', '.jpeg'))]
                    if sub_files:
                        print(f"[RESOURCE] Available image files in {subdir_path}: {sub_files}")
        except Exception as e:
            print(f"[RESOURCE] Cannot list directory: {e}")
        
        # 기본 아이콘이 없는 경우 대체 아이콘 생성 (임시 해결책)
        print("[RESOURCE] Creating fallback icon path")
        return create_fallback_icon(base_path)
    
    # 일반 파일 처리
    possible_paths = [
        os.path.join(base_path, relative_path),  # 기본 경로
        os.path.join(base_path, 'data', relative_path),  # data 폴더
        os.path.join(base_path, 'assets', relative_path),  # assets 폴더
        os.path.join(base_path, relative_path.capitalize()),  # 첫 글자 대문자
        os.path.join(base_path, relative_path.upper()),  # 모두 대문자
        os.path.join(base_path, relative_path.lower()),  # 모두 소문자
    ]
    
    for path in possible_paths:
        if os.path.exists(path):
            print(f"[RESOURCE] Found resource at: {path}")
            return path
    
    print(f"[RESOURCE] Resource not found: {relative_path}")
    print(f"[RESOURCE] Tried paths: {possible_paths}")
    return possible_paths[0]  # 기본 경로 반환

def create_fallback_icon(base_path):
    """아이콘 파일이 없는 경우 임시 아이콘을 생성합니다"""
    try:
        from PIL import Image, ImageDraw
        
        # base_path 내 data/temp 폴더 사용 (AppData 사용 금지)
        temp_dir = os.path.join(base_path, 'data', 'temp')
        os.makedirs(temp_dir, exist_ok=True)
        temp_icon_path = os.path.join(temp_dir, 'rnd_platform_temp_icon.ico')
        print(f"[RESOURCE] 프로젝트 폴더 사용: {temp_dir}")
        
        # 간단한 임시 아이콘 생성
        size = (64, 64)
        image = Image.new('RGBA', size, (70, 130, 180, 255))  # Steel Blue
        draw = ImageDraw.Draw(image)
        
        # 간단한 'R' 문자 그리기 (R&D를 의미)
        draw.text((20, 20), "R", fill=(255, 255, 255, 255))
        
        # 임시 파일로 저장
        image.save(temp_icon_path, format='ICO')
        
        print(f"[RESOURCE] Created fallback icon: {temp_icon_path}")
        return temp_icon_path
        
    except Exception as e:
        print(f"[RESOURCE] Failed to create fallback icon: {e}")
        # 최후의 수단: None 반환하여 기본 아이콘 사용
        return None


# --- build/debug helper: print where runtime will look for bundled data ---
try:
    import customtkinter as _ctk
    print(f"[BUILD-DEBUG] customtkinter.__file__ = {_ctk.__file__}")
except Exception as _e:
    print(f"[BUILD-DEBUG] customtkinter import failed: {_e}")

import pprint
from utils import center_window_on_mouse_display
print(f"[BUILD-DEBUG] sys._MEIPASS = {getattr(sys, '_MEIPASS', None)}")

_mp = getattr(sys, '_MEIPASS', None)
if _mp:
    try:
        sample = os.listdir(_mp)[:80]
        print("[BUILD-DEBUG] sample _MEIPASS contents:")
        pprint.pprint(sample)
    except Exception as _e:
        print(f"[BUILD-DEBUG] failed listing _MEIPASS: {_e}")

try:
    # also print where customtkinter assets should be found
    import customtkinter
    ctk_path = os.path.join(os.path.dirname(customtkinter.__file__), 'assets', 'themes')
    print(f"[BUILD-DEBUG] expected customtkinter themes path: {ctk_path}")
    try:
        print("[BUILD-DEBUG] themes folder sample:", os.listdir(ctk_path)[:50])
    except Exception as _e:
        print(f"[BUILD-DEBUG] cannot list themes folder: {_e}")
except Exception:
    pass

if getattr(sys, 'frozen', False):
    # PyInstaller로 빌드된 경우, .exe 파일이 있는 폴더
    application_path = os.path.dirname(sys.executable)
else:
    # 일반 Python 스크립트로 실행된 경우
    application_path = os.path.dirname(os.path.abspath(__file__))

def get_persistent_config_path(app_dir_name: str = 'RnD_플랫폼') -> str:
    """프로젝트 폴더 내 config.ini 경로를 제공합니다.
    
    - AppData 폴더 사용을 완전히 중단하고 프로젝트 폴더만 사용합니다.
    - 프로젝트 실행 경로(application_path) 내에 config.ini를 저장합니다.
    """
    try:
        # 프로젝트 폴더를 직접 사용 (AppData 사용 금지)
        target_config = os.path.join(application_path, 'config.ini')
        
        # config.ini가 없으면 기본 템플릿 생성
        if not os.path.exists(target_config):
            try:
                default_content = """[Paths]
excel_dir = 

[Database]
db_path = 
"""
                with open(target_config, 'w', encoding='utf-8') as f:
                    f.write(default_content)
                print(f"[CONFIG] 기본 config.ini 생성: {target_config}")
            except Exception as create_error:
                print(f"[CONFIG] config.ini 생성 실패: {create_error}")

        return target_config
    except Exception as e:
        # 문제가 있으면 기존 동작(실행 경로)을 사용
        print(f"[CONFIG] 사용자 설정 경로 확보 실패, exe 폴더 사용: {e}")
        return os.path.join(application_path, 'config.ini')

# config.ini는 프로젝트 폴더의 고정 경로를 사용 (AppData 사용 금지)
CONFIG_FILE_PATH = get_persistent_config_path()
print(f"[CONFIG] 최종 설정 파일 경로: {CONFIG_FILE_PATH}")


from sqlalchemy import text
from database.db_manager import db_manager
from datetime import datetime

# PyInstaller 빌드 환경을 고려한 안전한 모듈 임포트
def safe_import_modules():
    """빌드 환경에서 안전하게 모듈을 임포트합니다."""
    global get_texts, _translation, LoginWindow, SettingsManagementFrame
    global QualityManagementFrame, DataManagementFrame, HomeFrame
    
    try:
        # 경로 설정 (빌드 환경 고려)
        if getattr(sys, 'frozen', False):
            # PyInstaller 빌드된 환경
            application_path = sys._MEIPASS
            sys.path.insert(0, os.path.join(application_path, 'modules'))
            sys.path.insert(0, os.path.join(application_path, 'database'))
            sys.path.insert(0, os.path.join(application_path, 'utils'))
        
        from modules.translation import get_texts
        import modules.translation as _translation
        from modules.login import LoginWindow
        from modules.settings_management import SettingsManagementFrame
        from modules.quality_management import QualityManagementFrame
        from modules.data_management import DataManagementFrame
        from modules.home_frame import HomeFrame
        
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
                ('home_frame', 'HomeFrame')
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

class App(ctk.CTk):
    def __init__(self):
        super().__init__()
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
        self.db_initial_setup_complete = False  # 초기 DB 설정 완료 여부

        # 최근 활동 기록을 위한 설정
        self.recent_actions = deque(maxlen=5) # 화면에 표시할 최대 개수
        
        self.current_user = None
        self.withdraw()  # 메인 창 숨김

        # 창 닫기 버튼(X)을 눌렀을 때 처리할 함수 지정
        self.protocol("WM_DELETE_WINDOW", self.on_closing)
        
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
            base_dir = os.getenv('LOCALAPPDATA') or os.path.expanduser('~')
            log_dir = os.path.join(base_dir, 'RnD_플랫폼', 'logs')
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
        """Tkinter 콜백 예외를 잡아 사용자에게 안내하고 로그를 남깁니다."""
        try:
            import traceback as _tb
            tb_text = ''.join(_tb.format_exception(exctype, value, tb))
            log_path = self._log_error(tb_text)
            message = self._format_friendly_message(log_path)
            messagebox.showerror('오류', message, parent=self)
        except Exception:
            # 최후의 수단: 간단 메시지
            try:
                messagebox.showerror('오류', '치명적 오류가 발생했습니다. 프로그램을 종료합니다.', parent=self)
            except Exception:
                pass

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
        
        self.login_window = LoginWindow(
            master=self, 
            on_login_success=self.on_login_success,
            config_path=CONFIG_FILE_PATH
        )
        self.login_window.deiconify()
        self.login_window.lift()
        self.login_window.focus_force()
        print(f"{datetime.now()}: 로그인 창 강제 표시")
    
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
        
        current_db_path = os.path.join(application_path, 
                                     db_manager.get_db_relative_path(),
                                     "cosmetic.db")
        
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
        """DB가 처음 생성될 때 호출되는 콜백. (admin 계정 생성하지 않음)"""
        # admin 계정은 생성하지 않고, 사용자가 직접 회원가입하도록 유도
        print("[초기화] DB 생성 완료 - admin 계정 생성하지 않음")
        pass

    def show_pre_login_splash(self):
        """앱 시작 시 초기화 작업을 보여주는 스플래시 화면"""
        splash = ctk.CTkToplevel(self)
        splash.overrideredirect(True)

        width, height = 350, 350
        try:
            center_window_on_mouse_display(splash, width=width, height=height)
        except Exception:
            x = (splash.winfo_screenwidth() // 2) - (width // 2)
            y = (splash.winfo_screenheight() // 2) - (height // 2)
            splash.geometry(f'{width}x{height}+{x}+{y}')
        
        splash.lift()
        splash.focus_force()
        
        bg_color = splash._apply_appearance_mode(ctk.ThemeManager.theme["CTk"]["fg_color"])
        splash.configure(fg_color=bg_color)

        try:
            splash.wm_attributes("-transparentcolor", bg_color)
        except Exception:
            pass

        bg_label = ctk.CTkLabel(splash, text="", fg_color="transparent")
        bg_label.pack(fill="both", expand=True)

        # 아이콘 로딩 시도
        icon_loaded = False
        splash_image = None
        
        try:
            # 다양한 아이콘 이름으로 시도
            icon_names = ["Icon.ico", "icon.ico", "ICON.ICO", "icon.png", "Icon.png"]
            
            for icon_name in icon_names:
                try:
                    icon_path = resource_path(icon_name)
                    print(f"[PRE-SPLASH] Trying icon: {icon_path}")
                    
                    if os.path.exists(icon_path):
                        print(f"[PRE-SPLASH] Icon file exists: {icon_path}")
                        pil_img = Image.open(icon_path)
                        
                        # 이미지 크기 조정 및 형식 변환
                        if pil_img.mode != 'RGBA':
                            pil_img = pil_img.convert("RGBA")
                        
                        # 이미지 크기를 스플래시 화면에 맞게 조정
                        pil_img = pil_img.resize((width-40, height-100), Image.Resampling.LANCZOS)
                        
                        splash_image = ctk.CTkImage(light_image=pil_img, size=(width-40, height-100))
                        bg_label.configure(image=splash_image, text="")
                        print(f"[PRE-SPLASH] Successfully loaded icon: {icon_path}")
                        icon_loaded = True
                        break
                        
                except Exception as icon_error:
                    print(f"[PRE-SPLASH] Failed to load {icon_name}: {icon_error}")
                    continue
            
            if not icon_loaded:
                print("[PRE-SPLASH] No icon file found, using fallback")
                raise FileNotFoundError("No icon file found in any variant")
                
        except Exception as e:
            print(f"[PRE-SPLASH] Icon loading completely failed: {e}")
            # 아이콘 로딩 실패 시 간단한 텍스트만 표시 (배경색 제거)
            bg_label.configure(
                text="R&D Management System\n화장품 연구소 관리 시스템", 
                font=ctk.CTkFont(size=16, weight="bold"),
                text_color=("gray20", "gray80"),
                fg_color="transparent"
            )

        # 언어 설정에 따라 텍스트 선택
        if self.language == 'korean':
            initial_text = "애플리케이션 시작 중... 0%"
            task_descriptions = [
                "설정 파일 로드 중...",
                "데이터베이스 연결 중...",
            ]
            done_text = "완료!"
        else: # English or other
            initial_text = "Starting application... 0%"
            task_descriptions = [
                "Loading settings...",
                "Connecting to database...",
            ]
            done_text = "Done!"

        progress_label = ctk.CTkLabel(splash, text=initial_text, font=ctk.CTkFont(size=12),
                                      fg_color=("white", "black"), text_color=("black", "white"), corner_radius=5)
        progress_label.place(relx=0.5, rely=0.93, anchor="center")

        progress_bar = ctk.CTkProgressBar(
            splash, 
            width=280,
            fg_color="#E0F2F1",
            progress_color="#69F0AE"
        )
        progress_bar.set(0)
        progress_bar.place(relx=0.5, rely=0.98, anchor="center")

        splash.update()

        def init_database():
            try:
                print("\n=== 데이터베이스 초기화 시작 ===")
                
                # 재시작 시 DB 동기화 처리
                if self.handle_restart_db_sync():
                    print("=== 재시작 DB 동기화 완료 ===")
                
                db_manager.setup_database(application_path, CONFIG_FILE_PATH, self.on_initial_setup)
                print("=== 데이터베이스 초기화 완료 ===\n")
                return True
            except Exception as e:
                print(f"데이터베이스 초기화 실패: {e}")
                return False

        tasks = [
            (task_descriptions[0], self.load_app_settings),
            (task_descriptions[1], init_database),
        ]
        
        total_tasks = len(tasks)

        def on_load_complete():
            try:
                # 데이터베이스 연결 테스트
                print("\n=== DB 최종 연결 테스트 시작 ===")
                
                if not db_manager.Session:
                    raise RuntimeError("Session이 생성되지 않았습니다.")
                print("  - Session 객체 확인 완료")
                    
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
                
                if not db_manager.has_users():
                    self.show_initial_signup_window()
                else:
                    self.show_login_window()
                    
            except Exception as e:
                error_msg = f"데이터베이스 초기화 확인 실패:\n{str(e)}"
                print(f"\n[오류] {error_msg}")
                
                # DB 엔진과 세션 상태 확인
                print("\nDB 상태 진단:")
                print(f"  - Session 객체 존재: {db_manager.Session is not None}")
                print(f"  - Engine 객체 존재: {db_manager.engine is not None}")
                
                try:
                    if db_manager.engine:
                        print("  - Engine 연결 테스트 시도...")
                        with db_manager.engine.connect() as conn:
                            conn.execute(text("SELECT 1"))
                            print("    * Engine 직접 연결 성공")
                    else:
                        print("    * Engine이 없어 연결 테스트 불가")
                except Exception as e2:
                    print(f"    * Engine 연결 실패: {e2}")
                
                messagebox.showerror("초기화 오류", error_msg)
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
                
                try:
                    # DB 연결이 활성 상태인지 한 번 더 확인
                    if not db_manager.Session:
                        raise RuntimeError("데이터베이스 연결이 없습니다.")
                        
                    with db_manager.get_session() as session:
                        session.execute(text("SELECT 1"))
                        print("최종 DB 연결 테스트 성공")
                    
                    self.after(300, lambda: (splash.destroy(), on_load_complete()))
                except Exception as e:
                    error_msg = f"최종 연결 테스트 실패:\n{str(e)}"
                    print(error_msg)
                    messagebox.showerror("데이터베이스 오류", error_msg)
                    self.destroy()

        self.after(100, run_tasks)

    def show_post_login_splash(self, on_complete):
        """로그인 후 메인 UI 로딩 시 보여주는 스플래시 화면"""
        splash = ctk.CTkToplevel(self)
        splash.overrideredirect(True)

        width, height = 350, 350
        try:
            center_window_on_mouse_display(splash, width=width, height=height)
        except Exception:
            x = (splash.winfo_screenwidth() // 2) - (width // 2)
            y = (splash.winfo_screenheight() // 2) - (height // 2)
            splash.geometry(f'{width}x{height}+{x}+{y}')
        
        splash.lift()
        splash.focus_force()
        
        bg_color = splash._apply_appearance_mode(ctk.ThemeManager.theme["CTk"]["fg_color"])
        splash.configure(fg_color=bg_color)

        try:
            splash.wm_attributes("-transparentcolor", bg_color)
        except Exception:
            pass

        bg_label = ctk.CTkLabel(splash, text="", fg_color="transparent")
        bg_label.pack(fill="both", expand=True)

        # 아이콘 로딩 시도
        icon_loaded = False
        splash_image = None
        
        try:
            # 다양한 아이콘 이름으로 시도
            icon_names = ["Icon.ico", "icon.ico", "ICON.ICO", "icon.png", "Icon.png"]
            
            for icon_name in icon_names:
                try:
                    icon_path = resource_path(icon_name)
                    print(f"[POST-SPLASH] Trying icon: {icon_path}")
                    
                    if os.path.exists(icon_path):
                        print(f"[POST-SPLASH] Icon file exists: {icon_path}")
                        pil_img = Image.open(icon_path)
                        
                        # 이미지 크기 조정 및 형식 변환
                        if pil_img.mode != 'RGBA':
                            pil_img = pil_img.convert("RGBA")
                        
                        # 이미지 크기를 스플래시 화면에 맞게 조정
                        pil_img = pil_img.resize((width-40, height-100), Image.Resampling.LANCZOS)
                        
                        splash_image = ctk.CTkImage(light_image=pil_img, size=(width-40, height-100))
                        bg_label.configure(image=splash_image, text="")
                        print(f"[POST-SPLASH] Successfully loaded icon: {icon_path}")
                        icon_loaded = True
                        break
                        
                except Exception as icon_error:
                    print(f"[POST-SPLASH] Failed to load {icon_name}: {icon_error}")
                    continue
            
            if not icon_loaded:
                print("[POST-SPLASH] No icon file found, using fallback")
                raise FileNotFoundError("No icon file found in any variant")
                
        except Exception as e:
            print(f"[POST-SPLASH] Icon loading completely failed: {e}")
            # 아이콘 로딩 실패 시 간단한 텍스트만 표시 (배경색 제거)
            bg_label.configure(
                text="R&D Management System\n화장품 연구소 관리 시스템", 
                font=ctk.CTkFont(size=16, weight="bold"),
                text_color=("gray20", "gray80"),
                fg_color="transparent"
            )

        if self.language == 'korean':
            initial_text = "초기화 중... 0%"
            task_descriptions = [
                "이전 세션 정리 중...",
                "사용자 기록 불러오는 중...",
                "메인 화면 구성 중...",
                "테마 적용 중..."
            ]
            done_text = "완료!"
        else: # English or other
            initial_text = "Initializing... 0%"
            task_descriptions = [
                "Clearing old session...",
                "Loading user history...",
                "Building main interface...",
                "Applying visual theme..."
            ]
            done_text = "Done!"

        progress_label = ctk.CTkLabel(splash, text=initial_text, font=ctk.CTkFont(size=12),
                                      fg_color=("white", "black"), text_color=("black", "white"), corner_radius=5)
        progress_label.place(relx=0.5, rely=0.93, anchor="center")

        progress_bar = ctk.CTkProgressBar(
            splash, 
            width=280,
            fg_color="#E0F2F1",
            progress_color="#69F0AE"
        )
        progress_bar.set(0)
        progress_bar.place(relx=0.5, rely=0.98, anchor="center")

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
                
                if self.current_user.is_admin:
                    self.start_db_sync_check()
                print(f"{datetime.now()}: Main window displayed")

            self.show_post_login_splash(on_complete=show_main_window)

        self.after(50, show_splash_and_main_ui)

    def load_app_settings(self):
        """config.ini에서 앱 설정을 로드합니다 (테마, 언어 등)."""
        # interpolation=None으로 설정하여 '%' 등의 특수 문자가 포함된 값도 안전하게 처리
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
        
        self.grid_columnconfigure(1, weight=1)
        self.grid_rowconfigure(0, weight=1)

        self.navigation_frame = ctk.CTkFrame(self, corner_radius=0, width=200)
        self.navigation_frame.grid(row=0, column=0, sticky="nsew")
        self.navigation_frame.grid_columnconfigure(0, weight=1)

        # Static keys for actions
        self.ACTION_CONFIG = {
            "document/formulation_mgt": {"icon": "℞", "title": self.texts.get('formulation_mgt', 'Formulation Mgt.')},
            "document/document_sub": {"icon": "📄", "title": self.texts.get('document_sub', 'Documents')},
            "data/ingredient_mgt": {"icon": "🧪", "title": self.texts.get('ingredient_mgt', 'Ingredient Mgt.')},
            "data/client_mgt": {"icon": "🏢", "title": self.texts.get('client_mgt', 'Client Mgt.')},
            "data/user_mgt": {"icon": "👥", "title": self.texts.get('user_mgt', 'User Mgt.')},
            "settings/settings_sub": {"icon": "⚙️", "title": self.texts.get('settings_sub', 'Settings')},
            "quality/coa": {"icon": "🔬", "title": self.texts.get('coa', 'COA')},
            "quality/msds": {"icon": "🔬", "title": self.texts.get('msds', 'MSDS')},
            "quality/prod_standard": {"icon": "🔬", "title": self.texts.get('prod_standard', 'Product Standard')},
            "quality/mfg_record": {"icon": "🔬", "title": self.texts.get('mfg_record', 'Mfg. Record')},
            "quality/ingredient_report": {"icon": "🔬", "title": self.texts.get('ingredient_report', 'Ingredient Report')},
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
        self.title("R&D Management System" if self.language == "english" else "화장품 연구소 관리 시스템")

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
        ]

        current_row = 1
        for item in all_nav_items:
            # 권한 체크
            show_item = False
            if item["requires"] is None:
                show_item = True  # 홈은 모두 표시
            elif item["requires"] == "research":
                show_item = self.current_user.has_research_access()
            elif item["requires"] == "quality":
                show_item = self.current_user.has_quality_access()
            
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

        self.main_content_frame = ctk.CTkFrame(self, corner_radius=0, fg_color="transparent")
        self.main_content_frame.grid(row=0, column=1, sticky="nsew", padx=(10, 20), pady=20)
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
        
        self.frames[FRAME_SETTINGS] = SettingsManagementFrame(
            self.main_content_frame, 
            self.current_user, 
            self,
            config_path=CONFIG_FILE_PATH,
            application_path=application_path,
        )
        self.frames[FRAME_SETTINGS].grid(row=0, column=0, sticky="nsew")
        
        from modules.document_management import DocumentManagementFrame
        self.frames[FRAME_DATA] = DataManagementFrame(
            self.main_content_frame,
            self.current_user,
            self,
        )
        self.frames[FRAME_DATA].grid(row=0, column=0, sticky="nsew")

        self.frames[FRAME_DOCUMENT] = DocumentManagementFrame(
            self.main_content_frame,
            self.current_user,
            self,
            texts=self.texts
        )
        self.frames[FRAME_DOCUMENT].grid(row=0, column=0, sticky="nsew")

        self.frames[FRAME_QUALITY] = QualityManagementFrame(
            self.main_content_frame,
            self.current_user,
            self,
            texts=self.texts
        )
        self.frames[FRAME_QUALITY].grid(row=0, column=0, sticky="nsew")
        self.select_frame_by_name(FRAME_HOME)

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

        allowed_prefixes = ("data/", "document/", "quality/", "settings/")
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

        if frame_name not in self.frames:
            print(f"'{frame_name}' 프레임을 찾을 수 없습니다.")
            return
        
        self.frames[frame_name].tkraise()
        # 홈으로 전환 시, 최신 변경 이력과 카드 섹션을 즉시 새로고침하여 방금 변경한 내용이 보이도록 함
        try:
            if frame_name == FRAME_HOME and hasattr(self.frames[FRAME_HOME], 'refresh_data'):
                self.frames[FRAME_HOME].refresh_data()
        except Exception as e:
            print(f"[경고] 홈 새로고침 실패: {e}")
        if tab_name and hasattr(self.frames[frame_name], 'switch_to_tab'):
            self.frames[frame_name].switch_to_tab(tab_name)

    def open_material_by_id(self, material_id: int):
        """데이터 관리 > 성분 관리로 이동하여 해당 원료를 선택합니다."""
        try:
            # 먼저 데이터 관리/성분 관리 탭으로 이동
            self.select_frame_by_name('data/ingredient_mgt')
            # 프레임이 준비될 시간을 소폭 준 뒤 포커스 시도
            def _do_focus():
                try:
                    data_frame = self.frames.get(FRAME_DATA)
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

    def update_treeview_style(self):
        """현재 테마에 맞게 모든 Treeview의 스타일을 업데이트합니다."""
        theme = ctk.get_appearance_mode()
        style = ttk.Style()
        
        if theme.lower() == 'light':
            style.theme_use("default")
            style.configure("Treeview", background="white", foreground="black", fieldbackground="white", borderwidth=0, rowheight=30, font=('Malgun Gothic', 11))
            style.configure("Treeview.Heading", background="#f0f0f0", foreground="black", font=('Malgun Gothic', 12, 'bold'))
            style.map('Treeview', background=[('selected', '#3475d9')])
            style.map('Treeview.Heading', background=[('active', '#dcdcdc')])
            style.configure("folder", font=('Malgun Gothic', 11, 'bold'))
            style.configure("group_odd", background="#F0F8FF")
            style.configure("group_even", background="white")
            style.map("group_odd", background=[('selected', '#3475d9')])
            style.map("group_even", background=[('selected', '#3475d9')])
        else: # 다크 테마 설정
            style.theme_use("default")
            style.configure("Treeview", background="#2b2b2b", foreground="white", fieldbackground="#2b2b2b", borderwidth=0, rowheight=30, font=('Malgun Gothic', 11))
            style.configure("Treeview.Heading", background="#333333", foreground="white", font=('Malgun Gothic', 12, 'bold'))
            style.map('Treeview', background=[('selected', '#253655')])
            style.map('Treeview.Heading', background=[('active', '#4a4a4a')])
            style.configure("folder", font=('Malgun Gothic', 11, 'bold'))
            style.configure("group_odd", background="#2c3e50")
            style.configure("group_even", background="#2b2b2b")
            style.map("group_odd", background=[('selected', '#253655')])
            style.map("group_even", background=[('selected', '#253655')])

        print(f"{datetime.now()}: Treeview 스타일을 '{theme}' 테마로 업데이트했습니다.")

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

    def normalize_group_column_to_row_numbers(self, treeview, header_name='구분', force=False):
        """
        '구분' 헤더의 값이 ID 목록일 때 행 번호로 대체합니다.
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

        if not target_col:
            return

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

    def on_closing(self):
        """프로그램이 종료될 때 호출되는 함수입니다."""
        print(f"{datetime.now()}: 프로그램 종료 중... 활동 기록 저장")
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
                    # os._exit 실패/무시 대비해서 0.5초 후 강제 종료 시도
                    t = threading.Timer(0.5, _force_kill)
                    t.daemon = True  # 종료 방해하지 않도록 데몬 스레드로 실행
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
                # 3) 최후의 수단: 즉시 종료 (남아있는 비-데몬 스레드가 있어도 종료)
                os._exit(0)

    def get_config_value(self, section, option, fallback=None):
        """config.ini에서 값을 읽어옵니다."""
        config = configparser.ConfigParser()
        config.read(CONFIG_FILE_PATH, encoding='utf-8')
        return config.get(section, option, fallback=fallback)

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
        """
        마우스 커서가 위치한 모니터의 중앙에 창을 배치하고, 해당 모니터 기준 비율로 크기를 조절합니다.
        """
        try:
            # Windows에서는 마우스가 있는 모니터의 작업 영역을 기준으로 크기를 산정
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

                # 마우스가 위치한 모니터 정중앙 배치
                center_window_on_mouse_display(self, width=width, height=height)
                # 최소 크기도 해당 모니터 기준으로 설정
                self.minsize(int(mon_w * 0.5), int(mon_h * 0.6))
                return

            # 기타 OS: 단일 스크린 기준 폴백
            self.update_idletasks()
            sw = self.winfo_screenwidth()
            sh = self.winfo_screenheight()
            width = int(sw * 0.70)
            height = int(sh * 0.75)
            center_window_on_mouse_display(self, width=width, height=height)
            self.minsize(int(sw * 0.5), int(sh * 0.6))
        except Exception:
            # 최후 폴백: 기존 중앙 배치 로직
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

    def start_db_sync_check(self):
        """공유 DB의 변경 사항을 주기적으로 확인하는 타이머를 시작합니다."""
        # 초기 DB 상태를 조용히 설정 (알림 없이)
        self.initialize_db_sync_baseline()
        # 첫 체크는 1분 후부터 시작 (초기 설정 시간 여유)
        self.db_sync_timer = self.after(60000, self.start_periodic_sync_check)
        
    def initialize_db_sync_baseline(self):
        """DB 동기화 기준선을 조용히 설정합니다."""
        try:
            # interpolation=None으로 설정하여 경로 내 '%' 등으로 인한 파싱 오류 방지
            config = configparser.ConfigParser(interpolation=None)
            config.read(CONFIG_FILE_PATH, encoding='utf-8')
            shared_db_path = config.get('Paths', 'shared_db_path', fallback=None)

            # 공유 DB 파일 경로 해석 (폴더/파일 입력 모두 지원)
            def resolve_shared_file(path):
                if not path:
                    return None
                path = path.strip().strip('"').strip("'")
                if path.lower().endswith('.db') or os.path.basename(path).lower() == 'cosmetic.db':
                    return path
                return os.path.join(path, 'cosmetic.db')

            shared_db_file = resolve_shared_file(shared_db_path)

            # 기준선: 실제 DB 파일을 기준으로 설정 (폴더 아님)
            if shared_db_file and os.path.exists(shared_db_file):
                shared_db_stat = os.stat(shared_db_file)
                self.last_shared_db_info = (shared_db_stat.st_size, int(shared_db_stat.st_mtime))
                print(f"[DB동기화] 기준선 설정 완료: 파일={shared_db_file}, 크기={self.last_shared_db_info[0]}, 수정시간={self.last_shared_db_info[1]}")

                # 변경 로그 기준선도 설정 (있을 경우)
                self.last_change_log_id = 0
                try:
                    import sqlite3
                    conn = sqlite3.connect(shared_db_file)
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
            
    def start_periodic_sync_check(self):
        """주기적인 DB 동기화 검사를 시작합니다."""
        self.check_shared_db()
        self.db_sync_timer = self.after(30000, self.start_periodic_sync_check)

    def stop_db_sync_check(self):
        """DB 동기화 검사 타이머를 중지합니다."""
        if self.db_sync_timer:
            self.after_cancel(self.db_sync_timer)
            self.db_sync_timer = None
            
    def update_db_sync_baseline(self):
        """DB 동기화 기준선을 현재 상태로 업데이트합니다 (자체 변경사항 반영용)."""
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
                print(f"[DB동기화] 기준선 업데이트: 파일={shared_db_file}, 크기={self.last_shared_db_info[0]}, 수정시간={self.last_shared_db_info[1]}")
            else:
                print("[DB동기화] 공유 DB 경로 없음 - 기준선 업데이트 스킵")
        except Exception as e:
            print(f"[DB동기화] 기준선 업데이트 중 오류: {e}")

    def check_shared_db(self):
        """공유 DB 파일의 상태를 확인하고, '특정 체크'로 의미 있는 변경 시에만 업데이트를 제안합니다."""
        try:
            config = configparser.ConfigParser(interpolation=None)
            config.read(CONFIG_FILE_PATH, encoding='utf-8')
            shared_db_path = config.get('Paths', 'shared_db_path', fallback=None)

            if not shared_db_path:
                if self.current_user.is_admin and not self.db_path_warning_shown:
                    messagebox.showinfo(
                        "DB 동기화 설정 안내",
                        "공유 데이터베이스 동기화 기능이 활성화되었지만, 경로가 설정되지 않았습니다.\n\n[설정] 메뉴에서 공유 DB 파일의 경로를 지정해주세요.",
                        parent=self
                    )
                    self.db_path_warning_shown = True
                return

            # 실제 DB 파일 경로로 변환
            def resolve_shared_file(path):
                if not path:
                    return None
                path = path.strip()
                if path.lower().endswith('.db') or os.path.basename(path).lower() == 'cosmetic.db':
                    return path
                return os.path.join(path, 'cosmetic.db')

            shared_db_file = resolve_shared_file(shared_db_path)

            if not shared_db_file or not os.path.exists(shared_db_file):
                if self.current_user.is_admin and not self.db_path_warning_shown:
                     messagebox.showwarning(
                        "DB 동기화 경로 오류",
                        f"설정된 공유 DB 파일을 찾을 수 없습니다:\n{shared_db_file or shared_db_path}\n\n[설정] 메뉴에서 경로를 다시 확인해주세요.",
                        parent=self
                    )
                     self.db_path_warning_shown = True
                return
            
            shared_db_stat = os.stat(shared_db_file)
            # 파일 크기와 수정 시간을 더 정확하게 체크
            current_db_info = (shared_db_stat.st_size, int(shared_db_stat.st_mtime))

            # 초기 설정 시에는 현재 정보와 change_log ID만 저장하고 알림 표시하지 않음
            if self.last_shared_db_info == (0, 0):
                self.last_shared_db_info = current_db_info
                
                # change_log 기준선도 초기 설정 (전체 DB 업데이트 날짜 기록)
                try:
                    import sqlite3
                    conn = sqlite3.connect(shared_db_file)
                    cur = conn.cursor()
                    cur.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='change_log'")
                    if cur.fetchone():
                        cur.execute("SELECT IFNULL(MAX(id), 0) FROM change_log")
                        row = cur.fetchone()
                        self.last_change_log_id = int(row[0] or 0)
                        if self.last_change_log_id > 0:
                            print(f"[DB동기화] 전체 DB 업데이트 기록 완료 (change_log ID={self.last_change_log_id})")
                        else:
                            print(f"[DB동기화] 변경 로그 없음 - 초기 DB 상태")
                    conn.close()
                except Exception as e:
                    print(f"[DB동기화] 초기 변경 로그 기준선 설정 실패(무시): {e}")
                
                # 초기 설정 완료 플래그 설정
                self.db_initial_setup_complete = True
                print(f"[DB동기화] 초기 설정 완료 (이후 개별 변경사항만 알림) - 크기={current_db_info[0]}, 수정시간={current_db_info[1]}")
                return

            # 실제 변경사항이 있는지 더 엄격하게 체크
            if self.last_shared_db_info != current_db_info:
                # 파일 크기가 다르거나, 수정 시간이 15초 이상 차이날 때만 변경으로 간주 (더 보수적)
                size_changed = self.last_shared_db_info[0] != current_db_info[0]
                time_diff = abs(self.last_shared_db_info[1] - current_db_info[1])
                
                # 최소 변경 임계값 더 증가 (15초 이상, 크기는 2KB 이상 변경)
                significant_size_change = size_changed and abs(self.last_shared_db_info[0] - current_db_info[0]) > 2048
                significant_time_change = time_diff > 15
                
                if significant_size_change or significant_time_change:
                    # 특정 체크: change_log의 최근 변경 테이블을 수집하여 '사용자에게 관련 있는 변경'인지 판별
                    specific_change_detected = True  # 기본값 (change_log 없으면 보수적으로 True)
                    try:
                        import sqlite3
                        conn = sqlite3.connect(shared_db_file)
                        cur = conn.cursor()
                        cur.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='change_log'")
                        if cur.fetchone():
                            last_id = getattr(self, 'last_change_log_id', 0)
                            cur.execute("SELECT id, table_name, operation, entity_name FROM change_log WHERE id > ? ORDER BY id", (last_id,))
                            rows = cur.fetchall()

                            # 변경된 테이블 집합
                            changed_tables = {r[1] for r in rows}

                            # 변경 요약(성분/거래처 이름 표시)
                            changed_names = {
                                'ingredients': [],
                                'clients': []
                            }
                            for _id, tbl, op, ename in rows:
                                if tbl in changed_names and ename:
                                    changed_names[tbl].append(str(ename))

                            def summarize_names(names, limit=5):
                                uniq = []
                                seen = set()
                                for n in names:
                                    if n not in seen:
                                        uniq.append(n)
                                        seen.add(n)
                                if not uniq:
                                    return None
                                if len(uniq) > limit:
                                    return ", ".join(uniq[:limit]) + f" 외 {len(uniq)-limit}건"
                                return ", ".join(uniq)

                            ing_summary = summarize_names(changed_names['ingredients'])
                            cli_summary = summarize_names(changed_names['clients'])
                            change_human = []
                            if ing_summary:
                                change_human.append(f"성분: {ing_summary}")
                            if cli_summary:
                                change_human.append(f"거래처: {cli_summary}")
                            changes_summary_text = "\n".join(change_human) if change_human else ""

                            # 사용자 권한/사용처에 따른 관심 테이블 구성
                            interested = set()
                            try:
                                if hasattr(self.current_user, 'has_research_access') and self.current_user.has_research_access():
                                    interested.update({"formulations", "formulation_items"})
                                if hasattr(self.current_user, 'can_view_material_data') and self.current_user.can_view_material_data():
                                    interested.update({"materials", "ingredients"})
                                if hasattr(self.current_user, 'can_view_client_data') and self.current_user.can_view_client_data():
                                    interested.update({"clients"})
                                # 사용자 관리 변경은 관리자에게만 의미가 있으므로 관리자에게만 알림
                                if getattr(self.current_user, 'is_admin', False):
                                    interested.update({"users"})
                            except Exception:
                                pass

                            specific_change_detected = bool(changed_tables & interested)

                            # 기준선 ID 업데이트 (항상 수행)
                            if rows:
                                self.last_change_log_id = rows[-1][0]
                        conn.close()
                    except Exception as e:
                        print(f"[DB동기화] 특정 변경 확인 실패(무시): {e}")

                    if not specific_change_detected:
                        # 관련 없는 변경이면 조용히 기준선만 갱신 (사용자에게 메시지/재시동 미제안)
                        print("[DB동기화] 관련 없는 변경 감지 -> 알림 없이 기준선만 갱신")
                        self.last_shared_db_info = current_db_info
                        return

                    print(f"[DB동기화] 실제 변경 감지! 크기변경: {significant_size_change} ({self.last_shared_db_info[0]} -> {current_db_info[0]}), 시간차: {time_diff}초")
                    
                    # 초기 설정이 아닌 실제 변경이므로 플래그 해제
                    self.db_initial_setup_complete = False
                    
                    # 관리자(is_admin 또는 MSAD, RQD)는 자동 업데이트 (알림 없음)
                    is_admin_level = (
                        getattr(self.current_user, 'is_admin', False) or 
                        getattr(self.current_user, 'role', None) in ['MSAD', 'RQD']
                    )
                    
                    if is_admin_level:
                        # 관리자는 조용히 기준선만 업데이트 (다음 로그인 시 자동 반영)
                        print(f"[DB동기화] 관리자 권한 사용자 - 조용히 기준선 업데이트 (시간차: {time_diff}초)")
                        self.last_shared_db_info = current_db_info
                    else:
                        # 일반 사용자(데이터관리자 이하)는 업데이트 알림 표시
                        self.last_shared_db_info = current_db_info
                        user_details = "관리자에 의해 데이터가 변경되었습니다."
                        if changes_summary_text:
                            user_details += f"\n\n변경된 항목 요약:\n{changes_summary_text}"
                        user_details += ("\n\n최신 데이터로 동기화하시겠습니까?\n\n"
                                         "※ '아니오'를 선택하면 다음 재접속 시 자동으로 업데이트됩니다.\n"
                                         "※ '예'를 선택하면 프로그램이 재시작됩니다.")
                        if messagebox.askyesno("데이터베이스 업데이트", user_details, parent=self):
                            self.sync_with_shared_db_safe(shared_db_file)
                        else:
                            print(f"[DB동기화] 사용자가 동기화 거부 - 다음 재접속 시 자동 업데이트 예정")
                else:
                    # 미미한 변경사항은 무시하고 정보만 업데이트
                    print(f"[DB동기화] 미미한 변경 무시 (크기차: {abs(self.last_shared_db_info[0] - current_db_info[0])}바이트, 시간차: {time_diff}초)")
                    self.last_shared_db_info = current_db_info

        except (FileNotFoundError, OSError):
            pass
        except Exception as e:
            print(f"[경고] 공유 DB 확인 중 오류 발생: {e}")
            # 오류 발생시 동기화 타이머를 일시 중지 (오류 누적 방지)
            self.stop_db_sync_check()
            print("[DB동기화] 오류로 인해 동기화 타이머를 일시 중지합니다.")

    def sync_with_shared_db_safe(self, shared_db_path):
        """안전한 공유 DB 동기화 - 재시작을 통해 안정성 보장"""
        try:
            print(f"[DB동기화] 안전한 동기화 시작: {shared_db_path}")
            
            # 현재 작업 저장 안내
            if messagebox.askyesno("동기화 전 확인", 
                                "동기화를 위해 프로그램이 재시작됩니다.\n\n"
                                "저장하지 않은 작업이 있다면 지금 저장하세요.\n"
                                "계속 진행하시겠습니까?", parent=self):
                
                # 동기화 정보를 환경변수에 저장
                os.environ['DB_SYNC_REQUIRED'] = 'True'
                os.environ['DB_SYNC_SOURCE'] = shared_db_path
                
                print("[DB동기화] 재시작을 통한 동기화 진행")
                self.restart_program()
            else:
                print("[DB동기화] 사용자가 동기화를 취소했습니다.")
                
        except Exception as e:
            print(f"[DB동기화] 안전한 동기화 중 오류: {e}")
            messagebox.showerror("동기화 오류", 
                               f"데이터베이스 동기화 준비 중 오류가 발생했습니다:\n\n{e}\n\n"
                               f"프로그램을 재시작해보세요.", parent=self)
    
    def sync_with_shared_db(self, shared_db_path):
        """기존 동기화 메서드 (레거시 호환용)"""
        print("[DB동기화] 기존 동기화 메서드 호출 - 안전한 동기화로 전환")
        self.sync_with_shared_db_safe(shared_db_path)

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
                    # 패키징된 실행 파일인 경우
                    executable_path = sys.executable
                    current_dir = os.path.dirname(sys.executable)
                else:
                    # 개발 환경인 경우
                    executable_path = sys.executable
                    current_dir = os.path.dirname(os.path.abspath(__file__))
                
                print(f"{datetime.now()}: 실행 경로: {executable_path}")
                print(f"{datetime.now()}: 작업 디렉토리: {current_dir}")
                
                # 환경 변수 설정 (모듈 경로 보장 및 사용자 정보 전달)
                env = os.environ.copy()
                if getattr(sys, 'frozen', False):
                    # PyInstaller 환경에서 모듈 경로 설정
                    env['PYTHONPATH'] = os.pathsep.join([
                        os.path.join(current_dir, 'modules'),
                        os.path.join(current_dir, 'database'),
                        os.path.join(current_dir, 'utils'),
                        env.get('PYTHONPATH', '')
                    ])
                    
                    # 임시 폴더 오류 방지를 위한 추가 설정
                    env['PYINSTALLER_SUPPRESS_TEMP_ERRORS'] = '1'
                    
                    # 이전 _MEIPASS 환경 변수 제거 (새 프로세스가 새 임시 폴더 생성하도록)
                    if '_MEIPASS' in env:
                        del env['_MEIPASS']
                        print(f"{datetime.now()}: 이전 _MEIPASS 환경 변수 제거")
                
                # 재시작 시 사용자 정보 전달
                if hasattr(self, 'current_user') and self.current_user:
                    env['APP_RESTARTING'] = 'True'
                    env['RESTART_USER_ID'] = str(self.current_user.id)
                    env['RESTART_USER_IS_ADMIN'] = str(self.current_user.is_admin)
                    print(f"[RESTART] 사용자 정보 전달: {self.current_user.id} (관리자: {self.current_user.is_admin})")
                
                # 새 프로세스 시작 (작업 디렉토리 및 환경 변수 명시적 설정)
                # 개발 환경(non-frozen)에서는 스크립트 경로를 명시적으로 전달해야 함
                if not getattr(sys, 'frozen', False):
                    script_path = os.path.abspath(__file__)
                    cmd = [executable_path, script_path] + sys.argv[1:]
                else:
                    # 패키징된 실행 파일은 자체적으로 진입점을 포함하므로 추가 스크립트 경로 불필요
                    cmd = [executable_path] + sys.argv[1:]

                subprocess.Popen(
                    cmd,
                    cwd=current_dir,  # 작업 디렉토리 명시적 설정
                    env=env,  # 환경 변수 설정
                    creationflags=subprocess.CREATE_NEW_PROCESS_GROUP if os.name == 'nt' else 0
                )
                print(f"{datetime.now()}: 새 프로세스 시작 성공 (환경 변수 포함)")
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

            # 8. 현재 프로세스 종료
            print(f"{datetime.now()}: 현재 프로세스 종료")
            import os as _os
            _os._exit(0)
            
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

    # 실행 PC 하드웨어 바인딩 검증 (최초 실행 시 회원가입에서 생성)
    try:
        from utils.hw_binding import ensure_machine_binding
        ensure_machine_binding()
        print("[STARTUP] 하드웨어 바인딩 검증 완료")
    except SystemExit:
        # ensure_machine_binding에서 차단 시 종료
        raise
    except Exception as bind_e:
        # 바인딩 로직 실패 시 경고만 표시 (첫 실행은 회원가입 시 생성)
        print(f"[WARNING] 하드웨어 바인딩 처리 중 오류: {bind_e}")
    
    # 데이터베이스 자동 백업
    try:
        from database.db_manager import db_manager
        db_manager.backup_database()
        print("[STARTUP] 데이터베이스 자동 백업 완료")
    except Exception as backup_e:
        print(f"[WARNING] 데이터베이스 백업 실패: {backup_e}")
    
    app = App()
    app.mainloop()
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

# ==================== PyInstaller 경로 처리 ====================
def resource_path(relative_path):
    """ Get absolute path to resource, works for dev and for PyInstaller """
    try:
        # PyInstaller creates a temp folder and stores path in _MEIPASS
        base_path = sys._MEIPASS
    except Exception:
        base_path = os.path.dirname(os.path.abspath(__file__))
    return os.path.join(base_path, relative_path)


# --- build/debug helper: print where runtime will look for bundled data ---
try:
    import customtkinter as _ctk
    print(f"[BUILD-DEBUG] customtkinter.__file__ = {_ctk.__file__}")
except Exception as _e:
    print(f"[BUILD-DEBUG] customtkinter import failed: {_e}")

import pprint
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

# config.ini는 리소스 경로에서 찾도록 수정
CONFIG_FILE_PATH = resource_path('config.ini')


from sqlalchemy import text
from database.db_manager import db_manager
from modules.translation import get_texts
import modules.translation as _translation
from modules.login import LoginWindow
from modules.settings_management import SettingsManagementFrame
from modules.quality_management import QualityManagementFrame # 품질관리 프레임 import
from modules.data_management import DataManagementFrame
from modules.home_frame import HomeFrame
from datetime import datetime

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

        self.db_sync_timer = None
        self.db_path_warning_shown = False
        self.last_shared_db_info = (0, 0)

        # 최근 활동 기록을 위한 설정
        self.recent_actions = deque(maxlen=5) # 화면에 표시할 최대 개수
        
        self.current_user = None
        self.withdraw()  # 메인 창 숨김

        # 창 닫기 버튼(X)을 눌렀을 때 처리할 함수 지정
        self.protocol("WM_DELETE_WINDOW", self.on_closing)
        
        # 앱 시작 시 로딩 스플래시 화면 표시
        self.after(50, self.show_pre_login_splash)

    def show_login_window(self):
        print(f"{datetime.now()}: show_login_window 호출")
        self.login_window = LoginWindow(
            master=self, 
            on_login_success=self.on_login_success,
            config_path=CONFIG_FILE_PATH
        )
        self.login_window.deiconify()
        self.login_window.lift()
        self.login_window.focus_force()
        print(f"{datetime.now()}: 로그인 창 강제 표시")
    
    def show_initial_signup_window(self):
        """최초 실행 시 관리자 계정 생성을 위한 회원가입 창을 띄웁니다."""
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
        config = configparser.ConfigParser()
        config.read(CONFIG_FILE_PATH, encoding='utf-8')
        
        current_db_path = os.path.join(application_path, 
                                     db_manager.get_db_relative_path(),
                                     "cosmetic.db")
        
        if not config.has_section('Paths'):
            config.add_section('Paths')
            
        config.set('Paths', 'shared_db_path', current_db_path)
        with open(CONFIG_FILE_PATH, 'w', encoding='utf-8') as configfile:
            config.write(configfile)
            
        # 2. 공유 DB 설정 안내
        messagebox.showinfo("초기 설정 안내",
            "프로그램 초기 설정이 완료되었습니다.\n\n"
            "다른 사용자와 데이터를 공유하려면 설정 메뉴에서\n"
            "공유 DB 경로를 네트워크 드라이브나 공유 폴더로 변경해주세요.",
            parent=self)
            
        # 3. 일반적인 로그인 성공 처리
        self.on_login_success(user)

    def on_initial_setup(self):
        """DB가 처음 생성될 때 호출되는 콜백. 기본 admin 계정을 생성합니다."""
        db_manager.create_default_admin()

    def show_pre_login_splash(self):
        """앱 시작 시 초기화 작업을 보여주는 스플래시 화면"""
        splash = ctk.CTkToplevel(self)
        splash.overrideredirect(True)

        width, height = 350, 350
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

        try:
            icon_path = resource_path("icon.ico")
            if os.path.exists(icon_path):
                pil_img = Image.open(icon_path).convert("RGBA")
                ctk_splash_image = ctk.CTkImage(light_image=pil_img, size=(width, height))
                bg_label.configure(image=ctk_splash_image)
            else:
                raise FileNotFoundError("icon.ico not found")
        except Exception as e:
            print(f"Splash icon error: {e}")
            bg_label.configure(fg_color=("gray85", "gray15"), text=f"Icon Load Error:\n{e}", font=ctk.CTkFont(size=12))

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

        try:
            icon_path = resource_path("icon.ico")
            if os.path.exists(icon_path):
                pil_img = Image.open(icon_path).convert("RGBA")
                ctk_splash_image = ctk.CTkImage(light_image=pil_img, size=(width, height))
                bg_label.configure(image=ctk_splash_image)
            else:
                raise FileNotFoundError("icon.ico not found")
        except Exception as e:
            print(f"Splash icon error: {e}")
            bg_label.configure(fg_color=("gray85", "gray15"), text=f"Icon Load Error:\n{e}", font=ctk.CTkFont(size=12))

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
            if user.username == 'admin' and db_manager.get_admin_user_count() == 1:
                messagebox.showinfo("초기 설정 필요", "초기 관리자 계정(admin)으로 로그인했습니다.\n보안을 위해 새로운 관리자 계정을 생성해주세요.")
                self.show_initial_signup_window()
                return

            def show_main_window():
                self.center_on_mouse_screen()
                self.deiconify()
                if self.current_user.is_admin:
                    self.start_db_sync_check()
                print(f"{datetime.now()}: Main window displayed")

            self.show_post_login_splash(on_complete=show_main_window)

        self.after(50, show_splash_and_main_ui)

    def load_app_settings(self):
        """config.ini에서 앱 설정을 로드합니다 (테마, 언어 등)."""
        config = configparser.ConfigParser()
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
            {"name": FRAME_HOME, "text": self.texts["home"], "admin_only": False},
            {"name": FRAME_DOCUMENT, "text": self.texts["document"], "admin_only": False},
            {"name": FRAME_QUALITY, "text": self.texts["quality"], "admin_only": False},
        ]

        current_row = 1
        for item in all_nav_items:
            if not item["admin_only"] or self.current_user.is_admin:
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
        config = configparser.ConfigParser()
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
        if tab_name and hasattr(self.frames[frame_name], 'switch_to_tab'):
            self.frames[frame_name].switch_to_tab(tab_name)

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

    def on_closing(self):
        """프로그램이 종료될 때 호출되는 함수입니다."""
        print(f"{datetime.now()}: 프로그램 종료 중... 활동 기록 저장")
        self.stop_db_sync_check() # DB 동기화 타이머 중지
        self.save_app_settings()
        self.save_recent_actions()
        self.destroy()

    def get_config_value(self, section, option, fallback=None):
        """config.ini에서 값을 읽어옵니다."""
        config = configparser.ConfigParser()
        config.read(CONFIG_FILE_PATH, encoding='utf-8')
        return config.get(section, option, fallback=fallback)

    def save_app_settings(self):
        """어플리케이션의 주요 UI 설정을 저장합니다."""
        if not hasattr(self, 'frames') or FRAME_DOCUMENT not in self.frames:
            return
        config = configparser.ConfigParser()
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
        마우스 커서가 위치한 모니터의 중앙에 창을 배치하고 크기를 조절합니다.
        """
        self.update_idletasks()

        pointer_x = self.winfo_pointerx()
        pointer_y = self.winfo_pointery()

        self.geometry(f'+{pointer_x}+{pointer_y}')
        self.update_idletasks()
        
        screen_width = self.winfo_screenwidth()
        screen_height = self.winfo_screenheight()

        width = int(screen_width * 0.85)
        height = int(screen_height * 0.8)

        x = (screen_width // 2) - (width // 2)
        y = (screen_height // 2) - (height // 2)

        self.geometry(f"{width}x{height}+{x}+{y}")
        self.minsize(int(screen_width * 0.6), int(screen_height * 0.7))

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
        self.check_shared_db()
        self.db_sync_timer = self.after(30000, self.start_db_sync_check)

    def stop_db_sync_check(self):
        """DB 동기화 검사 타이머를 중지합니다."""
        if self.db_sync_timer:
            self.after_cancel(self.db_sync_timer)
            self.db_sync_timer = None

    def check_shared_db(self):
        """공유 DB 파일의 상태를 확인하고, 변경 시 업데이트를 제안합니다."""
        config = configparser.ConfigParser()
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

        if not os.path.exists(shared_db_path):
            if self.current_user.is_admin and not self.db_path_warning_shown:
                 messagebox.showwarning(
                    "DB 동기화 경로 오류",
                    f"설정된 공유 DB 경로를 찾을 수 없습니다:\n{shared_db_path}\n\n[설정] 메뉴에서 경로를 다시 확인해주세요.",
                    parent=self
                )
                 self.db_path_warning_shown = True
            return
        
        try:
            shared_db_stat = os.stat(shared_db_path)
            current_db_info = (shared_db_stat.st_size, shared_db_stat.st_mtime)

            if self.last_shared_db_info == (0, 0):
                self.last_shared_db_info = current_db_info
                return

            if self.last_shared_db_info != current_db_info:
                print("공유 DB 변경 감지! 업데이트 제안")
                self.last_shared_db_info = current_db_info
                if messagebox.askyesno("데이터베이스 업데이트", "다른 사용자가 데이터를 업데이트했습니다.\n최신 데이터로 동기화하시겠습니까?\n\n(UI가 새로고침됩니다.)"):
                    self.sync_with_shared_db(shared_db_path)

        except (FileNotFoundError, OSError):
            pass
        except Exception as e:
            print(f"[경고] 공유 DB 확인 중 오류 발생: {e}")

    def sync_with_shared_db(self, shared_db_path):
        """공유 DB 파일을 로컬 DB로 복사하고 UI를 새로고침합니다."""
        import shutil
        local_db_path = os.path.join(application_path, db_manager.get_db_relative_path(), "cosmetic.db")
        
        try:
            db_manager.dispose_engine()
            shutil.copy(shared_db_path, local_db_path)
            db_manager.setup_database(application_path, CONFIG_FILE_PATH, self.on_initial_setup)
            self.refresh_data_in_all_frames()
            messagebox.showinfo("동기화 완료", "데이터가 성공적으로 동기화되었습니다.", parent=self)

        except Exception as e:
            messagebox.showerror("동기화 오류", f"데이터베이스 동기화 중 오류가 발생했습니다: {e}", parent=self)
            if messagebox.askyesno("재시작 필요", "오류로 인해 동기화에 실패했습니다. 프로그램을 재시작하시겠습니까?"):
                self.restart_program()

    def restart_program(self):
        """프로그램을 재시작합니다."""
        try:
            print("프로그램 재시작...")
            # 먼저 윈도우/GUI 리소스를 정리
            try:
                self.destroy()
            except Exception:
                pass

            # 새 프로세스를 백그라운드로 시작
            subprocess.Popen([sys.executable] + sys.argv)

            # 즉시 현재 프로세스를 종료하여 PyInstaller가
            # 임시 디렉터리(_MEIPASS)를 정리할 수 있도록 합니다.
            # os._exit(0)은 인터프리터 종료 시 cleanup 핸들러를
            # 우회하므로 안전하게 프로세스를 종료합니다.
            import os as _os
            _os._exit(0)
        except Exception as e:
            print(f"프로그램 재시작 실패: {e}")

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

if __name__ == "__main__":
    ctk.set_default_color_theme("blue")
    
    app = App()
    app.mainloop()
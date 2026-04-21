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

# ==================== PyInstaller 경로 처리 ====================
if getattr(sys, 'frozen', False):
    # PyInstaller로 빌드된 경우, .exe 파일이 있는 폴더
    application_path = os.path.dirname(sys.executable)
else:
    # 일반 Python 스크립트로 실행된 경우
    application_path = os.path.dirname(os.path.abspath(__file__))

# config.ini는 항상 .exe 파일 옆에 위치하도록 경로 수정
CONFIG_FILE_PATH = os.path.join(application_path, 'config.ini')

from database.db_manager import db_manager
from modules.translation import get_texts
import modules.translation as _translation
from modules.login import LoginWindow
from modules.settings_management import SettingsManagementFrame
from modules.quality_management import QualityManagementFrame # 품질관리 프레임 import
from modules.data_management import DataManagementFrame
from modules.home_frame import HomeFrame
from modules.progress_window import ProgressWindow
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
        
        # 아이콘 설정
        icon_path = os.path.join(application_path, 'icon.ico')
        if os.path.exists(icon_path):
            self.iconbitmap(icon_path)
            
        self.language = "korean" # 기본 언어 설정
        self.texts = get_texts(self.language) # 중앙 번역 객체 생성
        self.title("화장품 연구소 관리 시스템")

        self.last_shared_db_info = (0, 0) # (size, mtime)
        self.db_sync_timer = None

        # 최근 활동 기록을 위한 설정
        self.recent_actions = deque(maxlen=5) # 화면에 표시할 최대 개수
        
        self.current_user = None
        self.withdraw()  # 메인 창 숨김
        self.load_app_settings() # UI 생성 전 설정 로드
        
        # DB 초기화 (application_path 전달)
        db_manager.setup_database(application_path, CONFIG_FILE_PATH, self.on_initial_setup)

        # 사용자가 한 명도 없으면, 초기 관리자 생성 창을 띄움
        if not db_manager.has_users():
            self.show_initial_signup_window()
        else:
            # DB 및 Treeview 스타일 초기화
            self.show_login_window()

        # 창 닫기 버튼(X)을 눌렀을 때 처리할 함수 지정
        self.protocol("WM_DELETE_WINDOW", self.on_closing)
        
    def on_closing(self):
        """프로그램 종료 시 처리"""
        try:
            # DB 연결 종료
            if hasattr(db_manager, 'close_connection'):
                db_manager.close_connection()
            
            # 타이머 정리
            if self.db_sync_timer:
                self.after_cancel(self.db_sync_timer)
                self.db_sync_timer = None
            
            # 모든 창 닫기
            if hasattr(self, 'login_window') and self.login_window.winfo_exists():
                self.login_window.destroy()
            
            self.quit()
            self.destroy()
        except Exception as e:
            print(f"프로그램 종료 중 오류 발생: {e}")
            self.quit()
            self.destroy()

    def show_login_window(self):
        print(f"{datetime.now()}: show_login_window 호출")
        try:
            if hasattr(self, 'login_window'):
                try:
                    self.login_window.destroy()
                except:
                    pass
                    
            # 메인 윈도우를 숨김
            self.withdraw()
            
            # 로그인 윈도우 생성
            self.login_window = LoginWindow(
                master=self, 
                on_login_success=self.on_login_success,
                config_path=CONFIG_FILE_PATH
            )
            
            # 로그인 윈도우가 완전히 생성될 때까지 대기
            self.wait_visibility(self.login_window)
            
            # 창 위치 조정 (화면 중앙)
            window_width = 400
            window_height = 500
            screen_width = self.login_window.winfo_screenwidth()
            screen_height = self.login_window.winfo_screenheight()
            x = (screen_width - window_width) // 2
            y = (screen_height - window_height) // 2
            self.login_window.geometry(f"{window_width}x{window_height}+{x}+{y}")
            
            # 모달 설정
            self.login_window.grab_set()
            self.login_window.focus_set()
            
            print(f"{datetime.now()}: 로그인 창 표시")
        except Exception as e:
            print(f"로그인 창 표시 중 오류 발생: {e}")
            # 오류 발생 시 메인 윈도우 복구
            self.deiconify()
    
    def show_initial_signup_window(self):
        """최초 실행 시 관리자 계정 생성을 위한 회원가입 창을 띄웁니다."""
        from modules.signup import SignupWindow
        # on_success 콜백으로 on_login_success를 전달하여 가입 후 바로 로그인되도록 함
        signup_win = SignupWindow(self, is_initial_setup=True, on_success=self.on_login_success)
        signup_win.deiconify()
        signup_win.lift()
        signup_win.focus_force()

    def on_initial_setup(self):
        """DB가 처음 생성될 때 호출되는 콜백. 기본 admin 계정을 생성합니다."""
        db_manager.create_default_admin()

    def on_login_success(self, user):
        print(f"{datetime.now()}: on_login_success 호출")
        
        progress_window = ProgressWindow(self, "시스템 초기화 중...", 
                                      os.path.join(application_path, 'icon.ico'))
        progress_window.start_animation(duration_ms=2000) # 2초로 애니메이션 시간 조정

        # 설정 작업을 위한 제너레이터 생성
        setup_generator = self._run_setup_tasks_generator(user, progress_window)
        
        # 제너레이터 실행기 호출
        self.after(50, self._execute_setup_generator, setup_generator, progress_window)

    def _execute_setup_generator(self, generator, progress_window):
        """설정 제너레이터의 다음 단계를 실행하고, 완료될 때까지 반복 호출합니다."""
        try:
            # 제너레이터의 다음 작업 실행
            next(generator)
            # 다음 단계 실행 예약 (간격을 20ms로 짧게 하여 더 부드럽게)
            self.after(20, self._execute_setup_generator, generator, progress_window)
        except StopIteration:
            # 제너레이터가 완료되면 최종 처리
            print(f"{datetime.now()}: 모든 설정 작업 완료")
            
            # 메인 창을 화면에 표시하고 중앙에 배치
            self.deiconify()
            self.center_on_mouse_screen()
            
            progress_window.finish()
        except Exception as e:
            print(f"로그인 처리 중 심각한 오류 발생: {e}")
            if progress_window and progress_window.winfo_exists():
                progress_window.finish()
            self.on_closing()

    def _run_setup_tasks_generator(self, user, progress_window):
        """로그인 설정 작업을 매우 세분화하여 단계별로 실행하는 제너레이터입니다."""
        
        # --- 1단계: 사용자 및 기본 UI 설정 ---
        self.current_user = user
        if hasattr(self, 'login_window'):
            try: self.login_window.destroy()
            except: pass
        yield

        # --- 2단계: 최근 활동 기록 로드 ---
        self.recent_actions.clear()
        self.load_recent_actions()
        yield

        # --- 3단계: 메인 UI 골격 생성 ---
        self.grid_columnconfigure(1, weight=1)
        self.grid_rowconfigure(0, weight=1)
        self.navigation_frame = ctk.CTkFrame(self, corner_radius=0, width=200)
        self.navigation_frame.grid(row=0, column=0, sticky="nsew")
        self.navigation_frame.grid_columnconfigure(0, weight=1)
        self.main_content_frame = ctk.CTkFrame(self, corner_radius=0, fg_color="transparent")
        self.main_content_frame.grid(row=0, column=1, sticky="nsew", padx=(10, 20), pady=20)
        self.main_content_frame.grid_columnconfigure(0, weight=1)
        self.main_content_frame.grid_rowconfigure(0, weight=1)
        yield

        # --- 4단계: 네비게이션 UI 생성 (ACTION_CONFIG 및 제목) ---
        self.ACTION_CONFIG = {
            f"document/{self.texts['formulation_mgt']}": {"icon": "℞", "title": self.texts['formulation_mgt']},
            f"document/{self.texts['document_sub']}": {"icon": "📄", "title": self.texts['document_sub']},
            f"data/{self.texts['ingredient_mgt']}": {"icon": "🧪", "title": self.texts['ingredient_mgt']},
            f"data/{self.texts['client_mgt']}": {"icon": "🏢", "title": self.texts['client_mgt']},
            f"data/{self.texts['user_mgt']}": {"icon": "👥", "title": self.texts['user_mgt']},
            f"settings/{self.texts['settings_sub']}": {"icon": "⚙️", "title": self.texts['settings_sub']},
            f"quality/{self.texts['coa']}": {"icon": "🔬", "title": self.texts['coa']},
            f"quality/{self.texts['msds']}": {"icon": "🔬", "title": self.texts['msds']},
            f"quality/{self.texts['prod_standard']}": {"icon": "🔬", "title": self.texts['prod_standard']},
            f"quality/{self.texts['mfg_record']}": {"icon": "🔬", "title": self.texts['mfg_record']},
        }
        if 'ingredient_report' in self.texts:
            self.ACTION_CONFIG[f"quality/{self.texts['ingredient_report']}"] = {"icon": "🔬", "title": self.texts['ingredient_report']}
        if 'finished_product_report' in self.texts:
            self.ACTION_CONFIG[f"quality/{self.texts['finished_product_report']}"] = {"icon": "🔬", "title": self.texts['finished_product_report']}
        for act in list(self.recent_actions):
            if act not in self.ACTION_CONFIG:
                title = act.split('/', 1)[-1] if '/' in act else act
                self.ACTION_CONFIG[act] = {"icon": "❓", "title": title}
        self.title("R&D Management System" if self.language == "english" else "화장품 연구소 관리 시스템")
        self.navigation_frame_label = ctk.CTkLabel(self.navigation_frame, text=self.texts["menu"], font=ctk.CTkFont(size=16, weight="bold"))
        self.navigation_frame_label.grid(row=0, column=0, padx=15, pady=(20, 30))
        yield

        # --- 5단계: 네비게이션 버튼 생성 ---
        button_style = {"width": 160, "height": 40, "font": ctk.CTkFont(size=13), "anchor": "center"}
        self.nav_buttons = {}
        all_nav_items = [
            {"name": FRAME_HOME, "text": self.texts["home"], "admin_only": False},
            {"name": FRAME_DOCUMENT, "text": self.texts["document"], "admin_only": False},
            {"name": FRAME_QUALITY, "text": self.texts["quality"], "admin_only": False},
        ]
        current_row = 1
        for item in all_nav_items:
            if not item["admin_only"] or self.current_user.is_admin:
                button = ctk.CTkButton(self.navigation_frame, text=item["text"], command=lambda name=item["name"]: self.navigate_and_record(name), **button_style)
                button.grid(row=current_row, column=0, padx=15, pady=8)
                self.nav_buttons[item["name"]] = button
                current_row += 1
        yield
        
        self.navigation_frame.grid_rowconfigure(current_row, weight=1)
        ctk.CTkFrame(self.navigation_frame, fg_color="transparent", height=0).grid(row=current_row, column=0, sticky="nsew")
        current_row += 1
        self.data_button = ctk.CTkButton(self.navigation_frame, text=self.texts["data"], command=lambda: self.navigate_and_record("data/" + self.texts["ingredient_mgt"]), width=140, height=35, font=ctk.CTkFont(size=12), fg_color="#E65100", hover_color="#BF360C", anchor="center")
        self.data_button.grid(row=current_row, column=0, padx=15, pady=8)
        current_row += 1
        yield

        if self.current_user.is_admin:
            self.settings_button = ctk.CTkButton(self.navigation_frame, text=self.texts["settings"], command=lambda: self.navigate_and_record("settings/" + self.texts["settings_sub"]), width=140, height=35, font=ctk.CTkFont(size=12), fg_color="gray50", hover_color="gray30", anchor="center")
            self.settings_button.grid(row=current_row, column=0, padx=15, pady=8)
            current_row += 1
        self.logout_button = ctk.CTkButton(self.navigation_frame, text=self.texts["logout"], command=self.logout, width=140, height=35, font=ctk.CTkFont(size=12), fg_color="#D32F2F", hover_color="#B71C1C", anchor="center")
        self.logout_button.grid(row=current_row, column=0, padx=15, pady=(10, 30))
        yield

        # --- 6단계: 메인 프레임들 생성 ---
        self.frames = {}
        from modules.document_management import DocumentManagementFrame
        
        self.frames[FRAME_HOME] = HomeFrame(self.main_content_frame, self.current_user, self, self.recent_actions, self.ACTION_CONFIG)
        self.frames[FRAME_HOME].grid(row=0, column=0, sticky="nsew")
        yield
        
        self.frames[FRAME_SETTINGS] = SettingsManagementFrame(self.main_content_frame, self.current_user, self, config_path=CONFIG_FILE_PATH, application_path=application_path)
        self.frames[FRAME_SETTINGS].grid(row=0, column=0, sticky="nsew")
        yield

        self.frames[FRAME_DATA] = DataManagementFrame(self.main_content_frame, self.current_user, self)
        self.frames[FRAME_DATA].grid(row=0, column=0, sticky="nsew")
        yield

        self.frames[FRAME_DOCUMENT] = DocumentManagementFrame(self.main_content_frame, self.current_user, self, texts=self.texts)
        self.frames[FRAME_DOCUMENT].grid(row=0, column=0, sticky="nsew")
        yield

        self.frames[FRAME_QUALITY] = QualityManagementFrame(self.main_content_frame, self.current_user, self, texts=self.texts)
        self.frames[FRAME_QUALITY].grid(row=0, column=0, sticky="nsew")
        yield

        # --- 7단계: 최종 UI 설정 ---
        self.select_frame_by_name(FRAME_HOME)
        self.update_treeview_style()
        yield

        # --- 8단계: DB 연결 확인 ---
        if not self.check_database_connection():
            progress_window.finish()
            messagebox.showinfo("초기 설정 필요", "초기 관리자 계정(admin)으로 로그인했습니다.\n보안을 위해 새로운 관리자 계정을 생성해주세요.")
            self.show_initial_signup_window()
            return
        yield

    def check_database_connection(self):
        """데이터베이스 연결 확인"""
        try:
            # 데이터베이스 연결 확인 및 초기화 코드
            if self.current_user and self.current_user.username == 'admin' and db_manager.get_admin_user_count() == 1:
                return False
            return True
        except Exception as e:
            print(f"데이터베이스 연결 확인 중 오류 발생: {e}")
            return False


    def load_app_settings(self):
        """config.ini에서 앱 설정을 로드합니다 (테마, 언어 등)."""
        config = configparser.ConfigParser()
        try:
            if os.path.exists(CONFIG_FILE_PATH):
                config.read(CONFIG_FILE_PATH, encoding='utf-8')
            
            # 테마 설정 로드 및 적용
            theme = config.get('Appearance', 'theme', fallback='system')
            ctk.set_appearance_mode(theme)
            
            # 언어 설정 로드
            lang_setting = config.get('Appearance', 'language', fallback='korean').lower()
            self.language = 'english' if lang_setting == 'english' else 'korean'
            print(f"로드된 언어 설정: {self.language}")
        except Exception as e:
            print(f"[경고] config.ini 파일 로드 실패: {e}. 기본 설정으로 계속합니다.")
            # 오류 발생 시 기본값으로 안전하게 진행
            ctk.set_appearance_mode("System")
            self.language = "korean"

    def setup_main_ui(self):
        print(f"{datetime.now()}: setup_main_ui 호출")
        
        # 전체 그리드 설정
        self.grid_columnconfigure(1, weight=1)
        self.grid_rowconfigure(0, weight=1)

        # --- 네비게이션 프레임 ---
        self.navigation_frame = ctk.CTkFrame(self, corner_radius=0, width=200)
        self.navigation_frame.grid(row=0, column=0, sticky="nsew")
        self.navigation_frame.grid_columnconfigure(0, weight=1)

 
        # ACTION_CONFIG를 언어에 맞게 동적으로 생성
        self.ACTION_CONFIG = {
            f"document/{self.texts['formulation_mgt']}": {"icon": "℞", "title": self.texts['formulation_mgt']},
            f"document/{self.texts['document_sub']}": {"icon": "📄", "title": self.texts['document_sub']},
            f"data/{self.texts['ingredient_mgt']}": {"icon": "🧪", "title": self.texts['ingredient_mgt']},
            f"data/{self.texts['client_mgt']}": {"icon": "🏢", "title": self.texts['client_mgt']},
            f"data/{self.texts['user_mgt']}": {"icon": "👥", "title": self.texts['user_mgt']},
            f"settings/{self.texts['settings_sub']}": {"icon": "⚙️", "title": self.texts['settings_sub']},
            f"quality/{self.texts['coa']}": {"icon": "🔬", "title": self.texts['coa']},
            f"quality/{self.texts['msds']}": {"icon": "🔬", "title": self.texts['msds']},
            f"quality/{self.texts['prod_standard']}": {"icon": "🔬", "title": self.texts['prod_standard']},
            f"quality/{self.texts['mfg_record']}": {"icon": "🔬", "title": self.texts['mfg_record']},
        }
        # 품질 관리 탭에 동적으로 추가된 항목들을 ACTION_CONFIG에 반영
        # '원료목록보고 자료'와 같이 quality_management.py에서 추가된 탭을 자동으로 인식
        if 'ingredient_report' in self.texts:
            self.ACTION_CONFIG[f"quality/{self.texts['ingredient_report']}"] = {"icon": "🔬", "title": self.texts['ingredient_report']}
        # '완제품 시험성적서' 탭 추가
        if 'finished_product_report' in self.texts:
            self.ACTION_CONFIG[f"quality/{self.texts['finished_product_report']}"] = {"icon": "🔬", "title": self.texts['finished_product_report']}


        # --- 변경: recent_actions에 들어있는 항목이 ACTION_CONFIG에 없으면 표시용 플레이스홀더 추가 ---
        # (삭제된 거래처 등으로 인해 ACTION_CONFIG에서 사라졌더라도 홈 화면에서 항목이 사라지지 않도록 함)
        for act in list(self.recent_actions):
            if act not in self.ACTION_CONFIG:
                # act 형식: "scope/name" 이라고 가정. 마지막 부분을 제목으로 사용
                title = act.split('/', 1)[-1] if '/' in act else act
                # 번역 키가 있을 경우 그대로 사용, 없으면 제목으로 표시
                self.ACTION_CONFIG[act] = {"icon": "❓", "title": title}

        # 프로그램 제목 설정
        self.title("R&D Management System" if self.language == "english" else "화장품 연구소 관리 시스템")

        # 네비게이션 제목
        self.navigation_frame_label = ctk.CTkLabel(
            self.navigation_frame, 
            text=self.texts["menu"],
            font=ctk.CTkFont(size=16, weight="bold")
        )
        self.navigation_frame_label.grid(row=0, column=0, padx=15, pady=(20, 30))

        # ===== 네비게이션 버튼 생성 (데이터 기반) =====
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
 
        # 빈 공간 (하단 버튼들을 아래로 밀어내기 위해)
        self.navigation_frame.grid_rowconfigure(current_row, weight=1)
        empty_space = ctk.CTkFrame(self.navigation_frame, fg_color="transparent", height=0)
        empty_space.grid(row=current_row, column=0, sticky="nsew")
        current_row += 1
 
        # 데이터 관리 버튼
        self.data_button = ctk.CTkButton(
            self.navigation_frame,
            text=self.texts["data"],
            command=lambda: self.navigate_and_record("data/" + self.texts["ingredient_mgt"]),
            width=140, height=35, font=ctk.CTkFont(size=12),
            fg_color="#E65100", hover_color="#BF360C", anchor="center"  # 주황색 계열
        )
        self.data_button.grid(row=current_row, column=0, padx=15, pady=8)
        current_row += 1

        # 설정 관리 버튼 (관리자 전용)
        if self.current_user.is_admin:
            self.settings_button = ctk.CTkButton(
                self.navigation_frame,
                text=self.texts["settings"],
                command=lambda: self.navigate_and_record("settings/" + self.texts["settings_sub"]),
                width=140, height=35, font=ctk.CTkFont(size=12), fg_color="gray50", hover_color="gray30", anchor="center"
            )
            self.settings_button.grid(row=current_row, column=0, padx=15, pady=8)
            current_row += 1

        # 로그아웃 버튼 (다른 스타일)
        self.logout_button = ctk.CTkButton(
            self.navigation_frame, 
            text=self.texts["logout"],
            command=self.logout,
            width=140,
            height=35,
            font=ctk.CTkFont(size=12),
            fg_color="#D32F2F",          # 빨간색 배경
            hover_color="#B71C1C",       # 호버시 더 진한 빨간색
            anchor="center"
        )
        self.logout_button.grid(row=current_row, column=0, padx=15, pady=(10, 30))

        # ===== 메인 컨텐츠 프레임 =====
        self.main_content_frame = ctk.CTkFrame(self, corner_radius=0, fg_color="transparent")
        self.main_content_frame.grid(row=0, column=1, sticky="nsew", padx=(10, 20), pady=20)
        self.main_content_frame.grid_columnconfigure(0, weight=1)
        self.main_content_frame.grid_rowconfigure(0, weight=1)
        
        # ===== 프레임 생성 =====
        self.frames = {}

        # 메인 화면 프레임
        self.frames[FRAME_HOME] = HomeFrame(
            self.main_content_frame,
            self.current_user,
            self,  # App 인스턴스 전달
            self.recent_actions, # noqa
            self.ACTION_CONFIG,
        )
        self.frames[FRAME_HOME].grid(row=0, column=0, sticky="nsew")
        
        # 설정 관리 프레임
        self.frames[FRAME_SETTINGS] = SettingsManagementFrame(
            self.main_content_frame, 
            self.current_user, 
            self,
            config_path=CONFIG_FILE_PATH,
            application_path=application_path,
        )
        self.frames[FRAME_SETTINGS].grid(row=0, column=0, sticky="nsew")
        
        # 데이터 관리 프레임
        from modules.document_management import DocumentManagementFrame
        self.frames[FRAME_DATA] = DataManagementFrame(
            self.main_content_frame,
            self.current_user,
            self,
        )
        self.frames[FRAME_DATA].grid(row=0, column=0, sticky="nsew")

        # 서류 관리 프레임
        self.frames[FRAME_DOCUMENT] = DocumentManagementFrame(
            self.main_content_frame,
            self.current_user,
            self,
            texts=self.texts
        )
        self.frames[FRAME_DOCUMENT].grid(row=0, column=0, sticky="nsew")

        # 품질 관리 프레임
        self.frames[FRAME_QUALITY] = QualityManagementFrame(
            self.main_content_frame,
            self.current_user,
            self,
            texts=self.texts
        )
        self.frames[FRAME_QUALITY].grid(row=0, column=0, sticky="nsew")
        # 기본 선택
        self.select_frame_by_name(FRAME_HOME)

    def navigate_and_record(self, name: str):
        """활동을 기록하고 해당 화면으로 이동합니다."""
        self.record_action(name)
        self.select_frame_by_name(name)

    def record_action(self, action_name: str):
        """사용자 활동을 기록하고, 홈 화면을 업데이트합니다."""
        # 유효한 활동인지 검사: ACTION_CONFIG에 있어야 하는 기존 규칙을 완화.
        # data/, document/, quality/, settings/ 등 주요 스코프는 ACTION_CONFIG에 없어도 허용.
        if action_name == FRAME_HOME:
            return

        allowed_prefixes = ("data/", "document/", "quality/", "settings/")
        is_allowed = (action_name in self.ACTION_CONFIG) or any(action_name.startswith(p) for p in allowed_prefixes)
        if not is_allowed:
            # 허용되지 않는 형식이면 무시
            return

        # 중복 제거 후 맨 앞에 추가
        if action_name in self.recent_actions:
            self.recent_actions.remove(action_name)
        self.recent_actions.appendleft(action_name)

        # ACTION_CONFIG에 없는 항목이면 표시용 플레이스홀더 등록 (홈 화면에서 보이도록)
        if action_name not in self.ACTION_CONFIG:
            title = action_name.split('/', 1)[-1] if '/' in action_name else action_name
            self.ACTION_CONFIG[action_name] = {"icon": "❓", "title": title}

        # HomeFrame의 recent_actions를 직접 업데이트하고 카드를 새로고침합니다.
        home_frame = self.frames.get(FRAME_HOME)
        if home_frame:
            home_frame.recent_actions = self.recent_actions
            try:
                self.frames[FRAME_HOME].refresh_cards()
            except Exception:
                # HomeFrame이 아직 초기화되지 않았거나 refresh 실패 시 무시
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
                # maxlen을 초과하지 않도록 슬라이싱
                items = items_str.split(',')[:self.recent_actions.maxlen]
                self.recent_actions.extend(items)
        print(f"불러온 활동 기록: {list(self.recent_actions)}")

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
            # 라이트 테마 설정
            style.theme_use("default")
            # 글씨 크기(11pt)와 행 높이(30)를 키워 가독성 향상
            style.configure("Treeview", background="white", foreground="black", fieldbackground="white", borderwidth=0, rowheight=30, font=('Malgun Gothic', 11))
            style.configure("Treeview.Heading", background="#f0f0f0", foreground="black", font=('Malgun Gothic', 12, 'bold'))
            style.map('Treeview', background=[('selected', '#3475d9')])
            style.map('Treeview.Heading', background=[('active', '#dcdcdc')])
            # 폴더 스타일 추가 (굵은 글씨)
            style.configure("folder", font=('Malgun Gothic', 11, 'bold'))
            # 원료 그룹별 배경색 스타일 추가
            style.configure("group_odd", background="#F0F8FF") # AliceBlue
            style.configure("group_even", background="white")
            style.map("group_odd", background=[('selected', '#3475d9')])
            style.map("group_even", background=[('selected', '#3475d9')])
        else: # 다크 테마 설정
            style.theme_use("default")
            # 글씨 크기(11pt)와 행 높이(30)를 키워 가독성 향상
            style.configure("Treeview", background="#2b2b2b", foreground="white", fieldbackground="#2b2b2b", borderwidth=0, rowheight=30, font=('Malgun Gothic', 11))
            style.configure("Treeview.Heading", background="#333333", foreground="white", font=('Malgun Gothic', 12, 'bold'))
            style.map('Treeview', background=[('selected', '#253655')])
            style.map('Treeview.Heading', background=[('active', '#4a4a4a')])
            # 폴더 스타일 추가 (굵은 글씨)
            style.configure("folder", font=('Malgun Gothic', 11, 'bold'))
            # 원료 그룹별 배경색 스타일 추가
            style.configure("group_odd", background="#2c3e50") # Dark Slate Blue
            style.configure("group_even", background="#2b2b2b")
            style.map("group_odd", background=[('selected', '#253655')])
            style.map("group_even", background=[('selected', '#253655')])

        print(f"{datetime.now()}: Treeview 스타일을 '{theme}' 테마로 업데이트했습니다.")

    def autosize_treeview_columns(self, treeview, padding=10, min_width=20, max_width=None):
        """
        Treeview의 각 열과 트리 컬럼('#0') 너비를 해당 열의 가장 긴 텍스트에 맞춰 자동 조절합니다.
        - treeview: ttk.Treeview 인스턴스
        - padding: 측정된 텍스트 너비에 더할 여유 픽셀
        - min_width: 최소 너비
        - max_width: (선택) 최대 너비로 제한
        사용 예: app.autosize_treeview_columns(my_treeview, padding=18)
        """
        try:
            # 가능한 경우 Treeview에서 사용 중인 폰트를 얻어 측정에 사용
            try:
                font = tkfont.Font(font=treeview.cget("font"))
            except Exception:
                font = tkfont.nametofont("TkDefaultFont")

            # 트리 컬럼('#0') 처리 (있을 경우)
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
                # '#0' 컬럼이 없거나 접근 불가하면 무시
                pass

            # 일반 컬럼들 처리
            cols = list(treeview["columns"]) if treeview["columns"] else []
            for col in cols:
                header = treeview.heading(col).get('text', '') or col
                max_w = font.measure(str(header))
                for iid in treeview.get_children():
                    try:
                        val = treeview.set(iid, col) or ''
                    except Exception:
                        # 안전하게 item values에서 시도 (인덱스 불확실 시 빈 문자열)
                        try:
                            vals = treeview.item(iid).get('values', ())
                            # 값이 튜플/리스트이고 컬럼 인덱스를 찾을 수 있으면 사용
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
        - treeview: ttk.Treeview 인스턴스
        - total_candidates: 총합량 컬럼을 식별할 문자열 목록(컬럼 id 또는 헤더 텍스트 일부). 기본값 포함.
        - en_candidates: 영문명 컬럼 식별 목록(기본값 포함)
        - cas_candidates: CAS No. 컬럼 식별 목록(기본값 포함)
        반환: True(성공적으로 이동) / False(대상 컬럼을 찾지 못함)
        사용: app.move_total_between_en_and_cas(my_treeview)
        """
        try:
            # 기본 후보 키워드
            if total_candidates is None:
                total_candidates = ['total', '총합', '총합량', '총량', 'total_amount', 'amount_total']
            if en_candidates is None:
                en_candidates = ['english', '영문', 'eng_name', 'english_name']
            if cas_candidates is None:
                cas_candidates = ['cas', 'cas no', 'cas_no', 'casno']

            cols = list(treeview["columns"]) if treeview["columns"] else []

            # helper: 컬럼 id 또는 heading 텍스트로 매칭
            def find_col_by_candidates(candidates):
                for c in cols:
                    # 컬럼 id로 먼저 검사
                    if any(k.lower() in str(c).lower() for k in candidates):
                        return c
                    # heading 텍스트 검사
                    try:
                        hdr = treeview.heading(c).get('text', '') or ''
                        if any(k.lower() in str(hdr).lower() for k in candidates):
                            return c
                    except Exception:
                        pass
                # '#0' (tree column) 검사
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

            # 못 찾으면 실패
            if not total_col or not en_col:
                return False

            # '#0'이 포함될 수 있으므로 처리: columns 튜플에는 '#0'이 없음 -> 별도 처리 필요
            # 여기서는 '#0'이 총합량/영문명인 경우를 고려하되, 일반적인 컬럼 재배열은 columns 항목만 변경.
            if total_col == '#0' or en_col == '#0' or cas_col == '#0':
                # 단순한 케이스가 아니면 프레임 쪽에서 수동으로 처리하도록 False 반환
                return False

            # cols 리스트에서 total_col 제거 후 en_col 다음 위치로 삽입
            if total_col in cols and en_col in cols:
                cols.remove(total_col)
                en_index = cols.index(en_col)
                insert_index = en_index + 1
                # 만약 cas_col 존재하면 그 앞에 들어가도록 보장
                if cas_col in cols:
                    cas_index = cols.index(cas_col)
                    # insert_index가 cas_index보다 크면 cas_index 위치로 조정
                    if insert_index > cas_index:
                        insert_index = cas_index
                cols.insert(insert_index, total_col)
                # 재할당하여 순서 변경
                treeview["columns"] = tuple(cols)
                return True

            return False
        except Exception as e:
            print(f"[경고] move_total_between_en_and_cas 실패: {e}")
            return False

    def reorder_treeview_columns_by_headers(self, treeview, desired_headers_order, match_partial=True):
        """
        Treeview 컬럼을 헤더 텍스트 기준으로 재배열합니다.
        - treeview: ttk.Treeview 인스턴스
        - desired_headers_order: 재배열할 헤더 문자열 목록(예: ['국문명','영문명','총함량(%)','cas no.','기능'])
        - match_partial: True면 부분 일치 허용
        반환: True/False (성공 여부)
        사용: app.reorder_treeview_columns_by_headers(my_treeview, ['국문명','영문명','총함량(%)','cas no.','기능'])
        """
        try:
            # 현재 컬럼 리스트 (('#0'은 columns에 없음))
            cols = list(treeview["columns"]) if treeview["columns"] else []

            # 컬럼 id와 heading 텍스트 매핑 수집
            col_map = {}
            for c in cols:
                try:
                    hdr = str(treeview.heading(c).get('text', '') or '')
                except Exception:
                    hdr = ''
                col_map[c] = hdr

            # '#0' 헤더도 검사 대상에 포함될 수 있으므로 따로 저장
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
                # 1) header 텍스트로 정확/부분 매칭
                for c, nh in norm_map.items():
                    if c in used:
                        continue
                    if (nh == nd) or (match_partial and nd in nh) or (match_partial and nh in nd):
                        found = c
                        break
                # 2) '#0' 매칭 검사
                if not found and norm_root:
                    if (norm_root == nd) or (match_partial and nd in norm_root) or (match_partial and norm_root in nd):
                        # '#0'는 columns 튜플에 포함되지 않으므로 무시하고 실패 처리
                        # 프레임 쪽에서 '#0'을 컬럼으로 사용하면 별도 처리 필요
                        found = None
                if found:
                    new_order.append(found)
                    used.add(found)

            # 나머지(사용되지 않은) 컬럼은 기존 순서대로 뒤에 붙인다.
            for c in cols:
                if c not in used:
                    new_order.append(c)

            # 유효성: 새 순서가 기존 columns와 같은 길이를 가지면 적용
            if len(new_order) == len(cols) and tuple(new_order) != tuple(cols):
                treeview["columns"] = tuple(new_order)
                return True
            # 길이가 다르거나 변경 없음이면 False 반환
            return False
        except Exception as e:
            print(f"[경고] reorder_treeview_columns_by_headers 실패: {e}")
            return False

    def reorder_ingredient_sum_columns(self, treeview):
        """
        전성분 합계 탭(복합 전성분, 서류용) 전용 래퍼.
        요청된 순서: [국문명, 영문명, 총함량(%), cas no., 기능]
        """
        desired = ['구분', '국문명', '영문명', '총함량(%)', 'cas no.', '기능']
        res = self.reorder_treeview_columns_by_headers(treeview, desired, match_partial=True)
        # 전성분 합계 탭은 항상 '구분'을 행 번호로 표시해야 하므로 강제 교정
        try:
            self.normalize_group_column_to_row_numbers(treeview, header_name='구분', force=True)
        except Exception:
            pass
        return res

    def normalize_group_column_to_row_numbers(self, treeview, header_name='구분', force=False):
        """
        '구분' 헤더(또는 지정한 header_name)에 들어있는 값이
        "1,10,18,..." 처럼 쉼표로 연결된 ID 목록으로 보일 때,
        각 행에 대해 해당 값을 해당 행의 순번(1-based)으로 대체합니다.

        - treeview: ttk.Treeview 인스턴스
        - header_name: 헤더 텍스트(부분일치 허용)
        - force: True면 내용과 상관없이 모든 행을 해당 행 번호로 덮어씀
        동작: 변경이 필요할 때만 수정. '#0' 컬럼(트리 텍스트)도 지원.
        """
        # 컬럼 id 찾기 (헤더 텍스트 기준, 부분 일치 허용)
        cols = list(treeview["columns"]) if treeview["columns"] else []
        target_col = None
        header_norm = ''.join(ch for ch in (header_name or '').lower() if ch.isalnum())

        # 먼저 columns에서 헤더 텍스트 매칭
        for c in cols:
            try:
                hdr = str(treeview.heading(c).get('text', '') or '')
            except Exception:
                hdr = ''
            nh = ''.join(ch for ch in hdr.lower() if ch.isalnum())
            if header_norm in nh or nh in header_norm:
                target_col = c
                break

        # '#0' 헤더도 가능성 검사
        if not target_col:
            try:
                hdr0 = str(treeview.heading('#0').get('text', '') or '')
                nh0 = ''.join(ch for ch in hdr0.lower() if ch.isalnum())
                if header_norm in nh0 or nh0 in header_norm:
                    target_col = '#0'
            except Exception:
                pass

        if not target_col:
            # 대상 컬럼을 찾지 못하면 아무 작업 안 함
            return

        # 값이 "숫자(,숫자...)" 형태인지 확인하는 정규식
        listnum_re = re.compile(r'^\s*\d+(?:\s*,\s*\d+\s*)*$')

        # 각 행 순회하며 필요 시 교정 (force=True면 무조건 교정)
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
                    # 시도 1: set 사용
                    try:
                        treeview.set(iid, target_col, new_val)
                        continue
                    except Exception:
                        pass
                    # 시도 2: item values로 재설정
                    try:
                        vals = list(treeview.item(iid).get('values', ()))
                        col_index = cols.index(target_col) if target_col in cols else None
                        if col_index is not None:
                            # 확장 필요 시 빈값으로 채움
                            while len(vals) <= col_index:
                                vals.append('')
                            vals[col_index] = new_val
                            treeview.item(iid, values=tuple(vals))
                    except Exception:
                        pass
        return

    def logout(self):
        print(f"{datetime.now()}: logout 호출")

        # 자동 로그인 설정 해제
        try:
            self.save_recent_actions() # 로그아웃 전 활동 기록 저장
            LoginWindow.disable_auto_login_on_logout(CONFIG_FILE_PATH, self.current_user.username)
            print(f"{datetime.now()}: 자동 로그인 설정 해제 완료")
        except Exception as e:
            print(f"{datetime.now()}: 자동 로그인 해제 중 오류: {e}")

        # UI 리셋
        self.current_user = None
        for widget in self.winfo_children():
            widget.destroy()
        self.withdraw()
        self.show_login_window()

    def on_closing(self):
        """프로그램이 종료될 때 호출되는 함수입니다."""
        print(f"{datetime.now()}: 프로그램 종료 중... 활동 기록 저장")
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
        멀티 모니터 환경에서 각기 다른 해상도를 지원합니다.
        """
        self.update_idletasks()

        # 마우스 커서의 현재 위치를 가져와서 해당 모니터의 정보를 얻습니다.
        pointer_x = self.winfo_pointerx()
        pointer_y = self.winfo_pointery()

        # 창을 임시로 마우스 위치에 옮겨서 해당 모니터의 정보를 얻습니다.
        self.geometry(f'+{pointer_x}+{pointer_y}')
        self.update_idletasks()
        
        screen_width = self.winfo_screenwidth()
        screen_height = self.winfo_screenheight()

        # [수정] 창 크기를 화면 크기에 비례하여 설정
        width = int(screen_width * 0.85)
        height = int(screen_height * 0.7) # [수정] 높이를 1/3 줄여서 60%로 설정

        # [수정] 모니터의 중앙에 위치하도록 좌표 계산
        x = (screen_width // 2) - (width // 2)
        y = (screen_height // 2) - (height // 2)

        # [수정] 크기와 위치를 한 번에 설정하여 정확도를 높입니다.
        self.geometry(f"{width}x{height}+{x}+{y}")
        self.minsize(int(screen_width * 0.6), int(screen_height * 0.6))

    def recreate_main_ui(self):
        """메인 UI를 재생성하여 언어 변경 등을 반영합니다."""
        # ACTION_CONFIG와 같은 동적 설정을 다시 생성하기 위해 기존 UI 위젯을 먼저 제거합니다.
        for widget in self.winfo_children():
            widget.destroy()

        # 언어 설정에 따라 번역 텍스트를 다시 로드합니다.
        self.texts = get_texts(self.language)

        # 최근 활동 기록은 유지되어야 하므로 그대로 둡니다.
        # self.recent_actions.clear() # 기존 기록을 유지해야 하므로 주석 처리

        # 메인 UI를 새로운 설정으로 다시 설정합니다.
        self.setup_main_ui()
        self.update_treeview_style()
        # 기존 메인 UI 위젯들 제거

    def start_db_sync_check(self):
        """공유 DB의 변경 사항을 주기적으로 확인하는 타이머를 시작합니다."""
        # 30초마다 check_shared_db 함수를 호출
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

        if not shared_db_path or not os.path.exists(shared_db_path):
            return # 공유 경로가 설정되지 않았거나 존재하지 않으면 중단

        try:
            # 공유 DB 파일의 정보 가져오기
            shared_db_stat = os.stat(shared_db_path)
            current_db_info = (shared_db_stat.st_size, shared_db_stat.st_mtime)

            # 처음 확인하는 경우, 현재 상태를 저장만 함
            if self.last_shared_db_info == (0, 0):
                self.last_shared_db_info = current_db_info
                return

            # 이전 정보와 다를 경우, 변경된 것으로 간주
            if self.last_shared_db_info != current_db_info:
                print("공유 DB 변경 감지! 업데이트 제안")
                self.last_shared_db_info = current_db_info # 다음 비교를 위해 최신 정보로 업데이트

                if messagebox.askyesno("데이터베이스 업데이트", "다른 사용자가 데이터를 업데이트했습니다.\n최신 데이터로 동기화하시겠습니까?\n\n(프로그램이 재시작됩니다.)"):
                    self.sync_with_shared_db(shared_db_path)

        except (FileNotFoundError, OSError):
            # 공유 DB 파일이 없거나 접근 권한 문제 등으로 오류 발생 시 무시
            pass
        except Exception as e:
            print(f"[경고] 공유 DB 확인 중 오류 발생: {e}")

    def sync_with_shared_db(self, shared_db_path):
        """공유 DB 파일을 로컬 DB로 복사하고 프로그램을 재시작합니다."""
        import shutil
        local_db_path = os.path.join(application_path, db_manager.get_db_relative_path(), "cosmetic.db")
        
        try:
            db_manager.dispose_engine() # DB 연결 해제
            shutil.copy(shared_db_path, local_db_path) # 파일 복사
            self.restart_program() # 프로그램 재시작
        except Exception as e:
            messagebox.showerror("동기화 오류", f"데이터베이스 동기화 중 오류가 발생했습니다: {e}")

    def restart_program(self):
        """프로그램을 재시작합니다."""
        try:
            print("프로그램 재시작...")
            self.destroy()  # 현재 창 닫기

            # 현재 실행 파일 경로와 인자들을 사용하여 새 프로세스 시작
            # sys.executable은 python.exe 또는 빌드된 .exe 파일의 경로
            subprocess.Popen([sys.executable] + sys.argv)
        except Exception as e:
            print(f"프로그램 재시작 실패: {e}")

# --- 변경: get_texts에 안전한 기본값 주입용 래퍼 추가 ---
# 기존 get_texts를 보존한 뒤, 누락된 키가 있으면 언어에 맞는 기본 문자열을 삽입합니다.
_old_get_texts = get_texts
def safe_get_texts(lang):
    try:
        texts = _old_get_texts(lang) or {}
    except Exception:
        texts = {}

    # 기본 메시지 (한국어 / 영어)
    defaults_korean = {
        'export_formulation_name_empty': '내보낼 제형명을 입력해주세요.',
        'warning': '경고',
        'finished_product_report': '완제품 시험성적서',
        'ingredient_report': '원료목록보고',
    }
    defaults_english = {
        'export_formulation_name_empty': 'Please enter a name for the formulation to export.',
        'warning': 'Warning',
        'finished_product_report': 'Finished Product Test Report',
        'ingredient_report': 'Ingredient List Report',
    }

    lang_key = (lang or '').lower()
    defaults = defaults_english if 'eng' in lang_key or lang_key.startswith('en') else defaults_korean

    # 누락된 키를 채움
    for k, v in defaults.items():
        if k not in texts:
            texts[k] = v

    return texts

# 모듈 전체에 적용 (다른 모듈들이 import할 때도 안전한 버전 사용)
try:
    _translation.get_texts = safe_get_texts
    get_texts = safe_get_texts  # 로컬 참조도 교체
except Exception as e:
    print(f"[경고] 번역 래퍼 적용 실패: {e}")

if __name__ == "__main__":
    # App 생성자에서 설정을 로드하므로 여기서 미리 적용할 필요 없음
    ctk.set_default_color_theme("blue")
    
    app = App()
    app.mainloop()

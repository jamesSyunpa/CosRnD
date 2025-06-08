# main.py
import customtkinter as ctk
import configparser
import sys
from tkinter import messagebox
from tkinter import ttk
from collections import deque
import os

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
        self.title("화장품 연구소 관리 시스템")

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
        signup_win = SignupWindow(self, is_initial_setup=True, on_success=self.on_login_success)
        signup_win.deiconify()
        signup_win.lift()
        signup_win.focus_force()

    def on_initial_setup(self):
        """DB가 처음 생성될 때 호출되는 콜백. 기본 admin 계정을 생성합니다."""
        db_manager.create_default_admin()

    def on_login_success(self, user):
        print(f"{datetime.now()}: on_login_success 호출")
        self.current_user = user

        # 만약 로그인한 사용자가 'admin'이고, 유일한 관리자라면 새 관리자 생성을 강제
        if user.username == 'admin' and db_manager.get_admin_user_count() == 1:
            messagebox.showinfo("초기 설정 필요", "초기 관리자 계정(admin)으로 로그인했습니다.\n보안을 위해 새로운 관리자 계정을 생성해주세요.")
            self.show_initial_signup_window()
            return # 메인 UI를 띄우지 않고 종료

        self.recent_actions.clear() # 새 로그인 시 이전 기록 초기화
        self.load_recent_actions()
        self.setup_main_ui()
        self.update_treeview_style() # Treeview 스타일을 현재 테마에 맞게 업데이트
        self.center_on_mouse_screen()
        self.deiconify()

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

        # ===== 네비게이션 프레임 =====
        self.navigation_frame = ctk.CTkFrame(self, corner_radius=0, width=200)
        self.navigation_frame.grid(row=0, column=0, sticky="nsew")
        self.navigation_frame.grid_columnconfigure(0, weight=1)

        # --- 언어별 텍스트 ---
        current_texts = get_texts(self.language)

        # ACTION_CONFIG를 언어에 맞게 동적으로 생성
        self.ACTION_CONFIG = {
            f"document/{current_texts['formulation_mgt']}": {"icon": "℞", "title": current_texts['formulation_mgt']},
            f"document/{current_texts['document_sub']}": {"icon": "📄", "title": current_texts['document_sub']},
            f"data/{current_texts['ingredient_mgt']}": {"icon": "🧪", "title": current_texts['ingredient_mgt']},
            f"data/{current_texts['client_mgt']}": {"icon": "🏢", "title": current_texts['client_mgt']},
            f"data/{current_texts['user_mgt']}": {"icon": "👥", "title": current_texts['user_mgt']},
            f"settings/{current_texts['settings_sub']}": {"icon": "⚙️", "title": current_texts['settings_sub']},
            f"quality/{current_texts['coa']}": {"icon": "🔬", "title": current_texts['coa']},
            f"quality/{current_texts['msds']}": {"icon": "🔬", "title": current_texts['msds']},
            f"quality/{current_texts['prod_standard']}": {"icon": "🔬", "title": current_texts['prod_standard']},
            f"quality/{current_texts['mfg_record']}": {"icon": "🔬", "title": current_texts['mfg_record']},
        }

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
            text=current_texts["menu"],
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
            {"name": FRAME_HOME, "text": current_texts["home"], "admin_only": False},
            {"name": FRAME_DOCUMENT, "text": current_texts["document"], "admin_only": False},
            {"name": FRAME_QUALITY, "text": current_texts["quality"], "admin_only": False},
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
            text=current_texts["data"],
            command=lambda: self.navigate_and_record("data/" + current_texts["ingredient_mgt"]),
            width=140, height=35, font=ctk.CTkFont(size=12),
            fg_color="#E65100", hover_color="#BF360C", anchor="center"  # 주황색 계열
        )
        self.data_button.grid(row=current_row, column=0, padx=15, pady=8)
        current_row += 1

        # 설정 관리 버튼 (관리자 전용)
        if self.current_user.is_admin:
            self.settings_button = ctk.CTkButton(
                self.navigation_frame,
                text=current_texts["settings"],
                command=lambda: self.navigate_and_record("settings/" + current_texts["settings_sub"]),
                width=140, height=35, font=ctk.CTkFont(size=12), fg_color="gray50", hover_color="gray30", anchor="center"
            )
            self.settings_button.grid(row=current_row, column=0, padx=15, pady=8)
            current_row += 1

        # 로그아웃 버튼 (다른 스타일)
        self.logout_button = ctk.CTkButton(
            self.navigation_frame, 
            text=current_texts["logout"],
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
            language=self.language
        )
        self.frames[FRAME_SETTINGS].grid(row=0, column=0, sticky="nsew")
        
        # 데이터 관리 프레임
        from modules.document_management import DocumentManagementFrame
        self.frames[FRAME_DATA] = DataManagementFrame(
            self.main_content_frame,
            self.current_user,
            self,
            language=self.language
        )
        self.frames[FRAME_DATA].grid(row=0, column=0, sticky="nsew")

        # 서류 관리 프레임
        self.frames[FRAME_DOCUMENT] = DocumentManagementFrame(
            self.main_content_frame,
            self.current_user,
            self,
            language=self.language
        )
        self.frames[FRAME_DOCUMENT].grid(row=0, column=0, sticky="nsew")

        # 품질 관리 프레임
        self.frames[FRAME_QUALITY] = QualityManagementFrame(
            self.main_content_frame,
            self.current_user,
            self,
            language=self.language
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
        print(f"{datetime.now()}: center_on_mouse_screen 호출")
        self.update_idletasks()

        # 마우스 커서의 현재 위치를 가져옵니다.
        pointer_x = self.winfo_pointerx()
        pointer_y = self.winfo_pointery()

        # 마우스 위치를 기반으로 현재 모니터의 정보를 가져옵니다.
        # geometry()는 'widthxheight+x+y' 형식의 문자열을 반환합니다.
        # 이 정보는 창이 위치할 모니터의 크기와 위치를 나타냅니다.
        # Tkinter는 이 메서드를 호출할 때 가장 적합한 모니터 정보를 자동으로 찾습니다.
        geom = self.winfo_geometry()
        self.geometry(f'1x1+{pointer_x}+{pointer_y}') # 임시로 창을 마우스 위치로 이동시켜 올바른 모니터 감지
        self.update_idletasks()
        
        # 마우스가 있는 모니터의 너비와 높이를 가져옵니다.
        screen_width = self.winfo_screenwidth()
        screen_height = self.winfo_screenheight()
        
        # 모니터의 작업 영역(작업 표시줄 제외)을 고려하여 위치를 계산합니다.
        screen_x = self.winfo_screenmmwidth() # 이 값은 실제 좌표가 아니므로 사용하지 않음
        screen_y = self.winfo_screenmmheight() # 이 값은 실제 좌표가 아니므로 사용하지 않음

        width = int(screen_width * 0.9)
        height = int(screen_height * 0.9)
        x = (screen_width // 2) - (width // 2)
        y = (screen_height // 2) - (height // 2)
        
        self.geometry(f"{width}x{height}+{x}+{y}") # 최종 크기와 위치 설정
        self.minsize(int(screen_width * 0.6), int(screen_height * 0.6))

    def recreate_main_ui(self):
        """메인 UI를 재생성하여 언어 변경 등을 반영합니다."""
        # 기존 메인 UI 위젯들 제거
        for widget in self.winfo_children():
            widget.destroy()
        
        # 메인 UI 재생성
        self.setup_main_ui()
        self.update_treeview_style()

    def restart_program(self):
        """프로그램을 재시작합니다."""
        print("프로그램 재시작...")
        self.destroy() # 현재 창 닫기
        # 새 프로세스로 현재 스크립트 다시 실행
        os.execv(sys.executable, ['python'] + sys.argv)

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
    }
    defaults_english = {
        'export_formulation_name_empty': 'Please enter a name for the formulation to export.',
        'warning': 'Warning',
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

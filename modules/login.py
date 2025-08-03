import customtkinter as ctk
import os
import sys
import tkinter as tk
from tkinter import messagebox

# 프로젝트 루트 경로를 sys.path에 추가 (상대 경로 import를 위함)
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if PROJECT_ROOT not in sys.path:
    sys.path.append(PROJECT_ROOT)

from database.db_manager import db_manager
from modules.signup import SignupWindow
from datetime import datetime
import configparser
import base64

class LoginWindow(ctk.CTkToplevel):
    def __init__(self, master=None, on_login_success=None, config_path=None):
        print(f"{datetime.now()}: LoginWindow 초기화 시작")
        
        # 부모 클래스 초기화 전에 변수 저장
        self._master = master
        self._on_login_success = on_login_success
        self._config_path = config_path
        
        # 부모 클래스 초기화
        super().__init__(master)
        
        # 기본 창 설정
        self.title("로그인")
        self.resizable(False, False)
        
        # 윈도우 크기 및 위치 설정
        window_width = 400
        window_height = 500
        screen_width = self.winfo_screenwidth()
        screen_height = self.winfo_screenheight()
        x = (screen_width - window_width) // 2
        y = (screen_height - window_height) // 2
        self.geometry(f"{window_width}x{window_height}+{x}+{y}")
        
        # 초기화 직후 업데이트
        self.update_idletasks()
        
        # 나머지 초기화는 지연 실행
        self.after(100, self._complete_init)
        
        print(f"{datetime.now()}: LoginWindow 기본 초기화 완료")
    
    def _complete_init(self):
        """지연된 초기화를 완료하는 메서드"""
        try:
            # Config 파일 설정
            self.config = configparser.ConfigParser()
            if os.path.exists(self._config_path):
                self.config.read(self._config_path, encoding='utf-8')
                print(f"{datetime.now()}: config.ini 읽기 성공")
            else:
                print(f"{datetime.now()}: config.ini 파일이 없어 새로 생성합니다.")
                self.config.add_section('User')
            
            # UI 설정
            self.setup_ui()
            self.load_last_user_info()
            
            # 자동 로그인 체크
            self.check_auto_login()
            
            # 윈도우 설정
            self.attributes('-topmost', True)
            self.grab_set()
            self.focus_force()
            
            # 창 닫기 이벤트 설정
            self.protocol("WM_DELETE_WINDOW", self.on_closing)
            
        except Exception as e:
            print(f"LoginWindow 초기화 중 오류 발생: {e}")
            self.on_closing()
        
    def on_closing(self):
        """창이 닫힐 때의 처리"""
        try:
            self.grab_release()
            if self._master:
                self._master.deiconify()
        except:
            pass
        finally:
            self.destroy()
        
    def quit_application(self):
        """프로그램 종료"""
        try:
            self.grab_release()
            self.master.on_closing()  # 메인 창의 종료 처리 호출
        except:
            print("프로그램 종료 중 오류 발생")
            if self.master:
                self.master.destroy()
            self.destroy()

    def setup_ui(self):
        print(f"{datetime.now()}: setup_ui 호출")
        self.main_frame = ctk.CTkFrame(self, corner_radius=15)
        self.main_frame.pack(padx=20, pady=20, fill="both", expand=True)
        
        # 로고 또는 아이콘 영역
        self.logo_frame = ctk.CTkFrame(self.main_frame, fg_color="transparent")
        self.logo_frame.pack(pady=(20, 10))
        
        self.title_label = ctk.CTkLabel(
            self.logo_frame, 
            text="🔐 시스템 로그인", 
            font=ctk.CTkFont(size=24, weight="bold")
        )
        self.title_label.pack(pady=10)

        # 입력 필드 프레임
        self.input_frame = ctk.CTkFrame(self.main_frame, fg_color="transparent")
        self.input_frame.pack(pady=20, padx=30, fill="x")

        # 아이디 입력
        self.id_label = ctk.CTkLabel(self.input_frame, text="아이디", font=ctk.CTkFont(size=12))
        self.id_label.pack(anchor="w", pady=(0, 5))
        
        self.id_entry = ctk.CTkEntry(
            self.input_frame, 
            placeholder_text="아이디를 입력하세요", 
            width=300, 
            height=35,
            font=ctk.CTkFont(size=12)
        )
        self.id_entry.pack(pady=(0, 15))
        self.id_entry.bind('<FocusOut>', self.on_id_change)

        # 비밀번호 입력
        self.pw_label = ctk.CTkLabel(self.input_frame, text="비밀번호", font=ctk.CTkFont(size=12))
        self.pw_label.pack(anchor="w", pady=(0, 5))
        
        self.pw_entry = ctk.CTkEntry(
            self.input_frame, 
            placeholder_text="비밀번호를 입력하세요", 
            show="*", 
            width=300, 
            height=35,
            font=ctk.CTkFont(size=12)
        )
        self.pw_entry.pack(pady=(0, 20))
        self.pw_entry.bind("<Return>", self.login_event)

        # 체크박스 프레임
        self.checkbox_frame = ctk.CTkFrame(self.main_frame, fg_color="transparent")
        self.checkbox_frame.pack(pady=10, padx=30, fill="x")
        # 중앙 정렬을 위해 grid 레이아웃 사용 및 컬럼 가중치 설정
        self.checkbox_frame.grid_columnconfigure(0, weight=1)
        self.checkbox_frame.grid_columnconfigure(3, weight=1)

        # 아이디 저장 체크박스
        self.remember_id_var = ctk.BooleanVar()
        self.remember_id_check = ctk.CTkCheckBox(
            self.checkbox_frame, 
            text="아이디 저장", 
            variable=self.remember_id_var,
            font=ctk.CTkFont(size=11)
        )
        self.remember_id_check.grid(row=0, column=1, padx=(0, 10))
        
        # 자동 로그인 체크박스
        self.auto_login_var = ctk.BooleanVar()
        self.auto_login_check = ctk.CTkCheckBox(
            self.checkbox_frame, 
            text="자동 로그인", 
            variable=self.auto_login_var,
            font=ctk.CTkFont(size=11),
            command=self.on_auto_login_change
        )
        self.auto_login_check.grid(row=0, column=2, padx=(10, 0))

        # 자동 로그인 경고 라벨
        self.auto_login_warning = ctk.CTkLabel(
            self.main_frame,
            text="⚠️ 개인 컴퓨터에서만 사용하세요",
            font=ctk.CTkFont(size=10),
            text_color=("orange", "orange")
        )

        # 버튼 프레임
        self.buttons_frame = ctk.CTkFrame(self.main_frame, fg_color="transparent")
        self.buttons_frame.pack(pady=25, padx=30, fill="x")

        # 로그인 버튼
        self.login_button = ctk.CTkButton(
            self.buttons_frame, 
            text="로그인", 
            command=self.login_event, 
            width=300, 
            height=40,
            font=ctk.CTkFont(size=14, weight="bold"),
            corner_radius=8
        )
        self.login_button.pack(pady=(0, 10))

        # 회원가입 버튼
        self.signup_button = ctk.CTkButton(
            self.buttons_frame, 
            text="회원가입", 
            fg_color="transparent", 
            border_width=2,
            border_color=("gray70", "gray30"),
            text_color=("gray10", "#DCE4EE"), # 라이트/다크 모드에 맞는 텍스트 색상 추가
            command=self.open_signup, 
            width=300,
            height=35,
            font=ctk.CTkFont(size=12),
            corner_radius=8
        )
        self.signup_button.pack()
        
        # 메시지 라벨
        self.message_label = ctk.CTkLabel(
            self.main_frame, 
            text="", 
            font=ctk.CTkFont(size=11),
            text_color="red"
        )
        self.message_label.pack(pady=(10, 5))

    def on_auto_login_change(self):
        """자동 로그인 체크박스 변경 시 경고 표시/숨김"""
        if self.auto_login_var.get():
            self.auto_login_warning.pack(pady=(0, 10))
            # 자동 로그인 선택 시 아이디 저장도 자동 체크
            self.remember_id_var.set(True)
        else:
            self.auto_login_warning.pack_forget()

    def simple_encrypt(self, text):
        """간단한 문자열 암호화 (base64 + 간단한 변환)"""
        try:
            # 단순 base64 인코딩 (보안성은 낮지만 평문 저장보다는 나음)
            encoded = base64.b64encode(text.encode('utf-8')).decode('utf-8')
            return encoded
        except:
            return ""

    def simple_decrypt(self, encoded_text):
        """간단한 문자열 복호화"""
        try:
            decoded = base64.b64decode(encoded_text.encode('utf-8')).decode('utf-8')
            return decoded
        except:
            return ""

    def load_last_user_info(self):
        print(f"{datetime.now()}: load_last_user_info 호출")
        last_user = self.config.get('User', 'last_login_id', fallback='')
        if last_user:
            self.id_entry.insert(0, last_user)
            self.fetch_user_settings_from_db(last_user)
            
            # 자동 로그인이 설정되어 있고 비밀번호가 저장되어 있다면 비밀번호도 복원
            if self.config.getboolean('User', 'auto_login', fallback=False):
                saved_pw = self.config.get('User', 'saved_password', fallback='')
                if saved_pw:
                    decrypted_pw = self.simple_decrypt(saved_pw)
                    if decrypted_pw:
                        self.pw_entry.insert(0, decrypted_pw)

    def check_auto_login(self):
        """자동 로그인 체크 및 실행"""
        if (self.auto_login_var.get() and 
            self.id_entry.get() and 
            self.pw_entry.get()):
            print(f"{datetime.now()}: 자동 로그인 시도")
            self.after(1000, self.login_event)  # 1초 후 자동 로그인

    def on_id_change(self, event):
        username = self.id_entry.get()
        if username:
            self.fetch_user_settings_from_db(username)

    def fetch_user_settings_from_db(self, username):
        print(f"{datetime.now()}: DB에서 '{username}'의 설정 가져오기")
        settings = db_manager.get_user_settings(username)
        if settings:
            self.remember_id_var.set(settings.get('remember_id', False))
            self.auto_login_var.set(settings.get('auto_login', False))
            # 자동 로그인 체크 시 경고 표시
            if settings.get('auto_login', False):
                self.auto_login_warning.pack(pady=(0, 10))
        else:
            self.remember_id_var.set(False)
            self.auto_login_var.set(False)
            self.auto_login_warning.pack_forget()

    def save_settings_to_config(self, username, password=None):
        """설정을 로컬 config.ini에 저장"""
        print(f"{datetime.now()}: 로컬 config.ini에 설정 저장")
        config = configparser.ConfigParser()
        config.read(self._config_path, encoding='utf-8')

        if not config.has_section('User'):
            config.add_section('User')
        
        # 아이디 저장
        if self.remember_id_var.get():
            config.set('User', 'last_login_id', username)
        else:
            config.set('User', 'last_login_id', '')
        
        # 자동 로그인 설정
        config.set('User', 'auto_login', str(self.auto_login_var.get()))
        
        # 자동 로그인 체크 시에만 비밀번호 저장 (암호화)
        if self.auto_login_var.get() and password:
            encrypted_pw = self.simple_encrypt(password)
            config.set('User', 'saved_password', encrypted_pw)
            print(f"{datetime.now()}: 비밀번호 암호화하여 저장")
        else:
            config.set('User', 'saved_password', '')

        try:
            with open(self._config_path, 'w', encoding='utf-8') as f:
                config.write(f)
            print(f"{datetime.now()}: config.ini 저장 성공")
        except Exception as e:
            print(f"{datetime.now()}: config.ini 저장 실패: {e}")

    @staticmethod
    def disable_auto_login_on_logout(config_path, username=None):
        """로그아웃 시 자동 로그인 설정만 해제 (아이디 저장은 유지)"""
        print(f"{datetime.now()}: 로그아웃으로 인한 자동 로그인 해제 (아이디 저장은 유지)")
        
        config = configparser.ConfigParser()
        try:
            if os.path.exists(config_path):
                config.read(config_path, encoding='utf-8')
            else:
                return
            
            # 현재 저장된 사용자 정보 가져오기
            current_user = username or (config.get('User', 'last_login_id', fallback='') if config.has_section('User') else '')
            remember_id = config.getboolean('User', 'remember_id', fallback=True) if config.has_section('User') else True
            
            # 자동 로그인만 해제 (아이디 저장은 유지)
            config.set('User', 'auto_login', 'False')
            config.set('User', 'saved_password', '')  # 저장된 비밀번호만 삭제
            # last_login_id는 remember_id가 True면 유지
            
            # DB에서도 자동 로그인 설정만 해제 (아이디 저장은 유지)
            if current_user:
                db_manager.update_user_settings(current_user, remember_id, False)  # auto_login만 False로
                print(f"{datetime.now()}: DB에서 '{current_user}'의 자동 로그인 설정 해제 (아이디 저장: {remember_id})")
            
            # config.ini 파일 저장
            with open(config_path, 'w', encoding='utf-8') as configfile:
                config.write(configfile)
            print(f"{datetime.now()}: 로그아웃 시 자동 로그인 설정 해제 완료 (아이디 저장 유지)")
            
        except Exception as e:
            print(f"{datetime.now()}: 로그아웃 시 자동 로그인 해제 실패: {e}")

    def login_event(self, event=None):
        username = self.id_entry.get().strip()
        password = self.pw_entry.get()

        if not username or not password:
            self.show_message("아이디와 비밀번호를 모두 입력하세요.")
            return

        # 로그인 버튼 비활성화 (중복 클릭 방지)
        self.login_button.configure(state="disabled", text="로그인 중...")
        self.update()

        login_success = False
        try:
            user = db_manager.verify_user(username, password)

            if user:
                print(f"{datetime.now()}: 사용자 '{username}' 인증 성공")
                self.show_message("로그인 성공!", "green")
                
                # DB에 사용자 설정 업데이트
                db_manager.update_user_settings(username, self.remember_id_var.get(), self.auto_login_var.get())
                
                # 로컬 설정 저장 (자동 로그인 시 비밀번호도 포함)
                self.save_settings_to_config(username, password if self.auto_login_var.get() else None)
                
                login_success = True
            else:
                self.show_message("아이디 또는 비밀번호가 일치하지 않습니다.")
                
        except Exception as e:
            print(f"{datetime.now()}: 로그인 중 오류: {e}")
            self.show_message("로그인 중 오류가 발생했습니다.")
        
        # 로그인 실패한 경우에만 버튼 상태 복원
        if not login_success:
            try:
                self.login_button.configure(state="normal", text="로그인")
            except:
                pass  # 창이 파괴된 경우 무시
        else:
            # 성공한 경우에만 콜백 호출
            if self._on_login_success:
                self._on_login_success(user)
            
    def open_signup(self):
        print(f"{datetime.now()}: open_signup 호출")
        signup_win = SignupWindow(self)
        signup_win.transient(self)
        signup_win.grab_set()
        self.wait_window(signup_win)

    def show_message(self, message, color="red"):
        self.message_label.configure(text=message, text_color=color)
        # 성공 메시지는 2초 후 사라짐
        if color == "green":
            self.after(2000, lambda: self.message_label.configure(text=""))

    def center_on_screen(self):
        self.update_idletasks()
        win_width = self.winfo_width()
        win_height = self.winfo_height()
        screen_width = self.winfo_screenwidth()
        screen_height = self.winfo_screenheight()
        x = max(0, (screen_width // 2) - (win_width // 2))
        y = max(0, (screen_height // 2) - (win_height // 2))
        self.geometry(f'{win_width}x{win_height}+{x}+{y}')
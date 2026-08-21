# modules/signup.py
import customtkinter as ctk
import tkinter
import os
import re
from tkinter import messagebox
import bcrypt
from database.db_manager import db_manager
from database.models import User
from utils import center_window_on_mouse_display

class SignupWindow(ctk.CTkToplevel):
    def __init__(self, master=None, is_initial_setup=False, on_success=None):
        super().__init__(master)
        self.withdraw()  # 초기 드로잉 깜빡임 및 드드득 방지를 위해 숨김
        self.is_initial_setup = is_initial_setup
        self.on_success = on_success

        self.title("회원가입")

        self.geometry("450x750")  # 높이 증가
        self.resizable(False, False)
        self.transient(master)
        self.grab_set()

        # 회원가입 창 아이콘 설정
        try:
            from utils import resource_path
            icon_file = resource_path('Icon.ico')
            if os.path.exists(icon_file):
                self.iconbitmap(icon_file)
        except Exception as icon_err:
            print(f"[ICON] 회원가입 창 아이콘 설정 실패: {icon_err}")

        self.setup_ui()
        try:
            center_window_on_mouse_display(self)
        except Exception:
            pass

        self.deiconify()  # 배치 완료 후 표시
        # 회원가입 창이 뜰 때 법적 고지(약관) 내용도 자동으로 띄움
        # 동의하지 않고 닫으면 프로그램 종료됨 (LegalNoticeDialog 로직)
        self.after(200, self.open_legal_notice)


    def setup_ui(self):
        """회원가입 창의 UI 요소를 설정합니다."""
        main_frame = ctk.CTkFrame(self)
        main_frame.pack(padx=20, pady=20, fill="both", expand=True)

        title_label = ctk.CTkLabel(main_frame, text="신규 사용자 등록", font=ctk.CTkFont(size=20, weight="bold"))
        title_label.pack(pady=(15, 5))
        
        # 새 PC / 공유 DB 연동 상태 프레임
        db_conn_frame = ctk.CTkFrame(main_frame, fg_color=("gray90", "gray20"), corner_radius=8)
        db_conn_frame.pack(fill="x", padx=20, pady=(0, 10))
        
        cur_db = getattr(db_manager, 'db_path', '기본 DB')
        cur_db_display = os.path.basename(os.path.dirname(cur_db)) if cur_db else "기본"
        self.db_status_label = ctk.CTkLabel(
            db_conn_frame, 
            text=f"📁 연동 DB: {os.path.basename(cur_db)} ({cur_db_display})",
            font=ctk.CTkFont(size=11),
            text_color=("gray30", "gray80")
        )
        self.db_status_label.pack(side="left", padx=10, pady=6)
        
        self.db_change_btn = ctk.CTkButton(
            db_conn_frame,
            text="DB 경로 연동",
            width=85,
            height=24,
            font=ctk.CTkFont(size=11),
            command=self.open_db_settings
        )
        self.db_change_btn.pack(side="right", padx=8, pady=6)

        info_label = ctk.CTkLabel(main_frame, text="※ 새 PC인 경우 [DB 경로 연동]을 통해 기존 공유 데이터와 연결할 수 있습니다.\n(DB에 첫 번째 사용자로 등록 시 자동으로 관리자 권한이 부여됩니다.)", 
                                  wraplength=380, font=ctk.CTkFont(size=10), text_color="gray")
        info_label.pack(pady=(0, 8))

        input_frame = ctk.CTkFrame(main_frame, fg_color="transparent")
        input_frame.pack(fill="x", padx=20)
        input_frame.grid_columnconfigure(1, weight=1)

        self.entries = {}
        labels = {
            "사용자 ID": "username",
            "실명": "real_name",
            "비밀번호": "password",
            "비밀번호 확인": "password_confirm",
            "직책": "position",
            "담당번호": "manager_code",
            "연락처": "contact",
            "우편번호": "zip_code",
            "주소": "address"
        }

        current_row = 1
        for label_text, key in labels.items():
            label = ctk.CTkLabel(input_frame, text=label_text)
            label.grid(row=current_row, column=0, padx=(0, 10), pady=5, sticky="w")
            
            entry = ctk.CTkEntry(input_frame)
            entry.grid(row=current_row, column=1, pady=5, sticky="ew")
            
            if "비밀번호" in label_text:
                entry.configure(show="*")

            self.entries[key] = entry
            current_row += 1

        # 권한 선택 추가
        # 권한 선택 및 도움말(?) 버튼
        role_label = ctk.CTkLabel(input_frame, text="권한")
        role_label.grid(row=current_row, column=0, padx=(0, 10), pady=5, sticky="w")
        
        # 관리자 존재 여부 확인
        if not self.is_initial_setup:
            from database.db_manager import db_manager
            self.has_admin = db_manager.has_admin_users()
        else:
            self.has_admin = False
        
        if self.is_initial_setup:
            self.role_options = {"MSAD - 모든 관리자": "MSAD"}
            default_role = "MSAD - 모든 관리자"
        else:
            self.role_options = {"RD - 연구원": "RD"}
            default_role = "RD - 연구원"
        
        signup_role_frame = ctk.CTkFrame(input_frame, fg_color="transparent")
        signup_role_frame.grid(row=current_row, column=1, pady=5, sticky="ew")
        signup_role_frame.grid_columnconfigure(0, weight=1)

        self.role_combo = ctk.CTkOptionMenu(
            signup_role_frame,
            values=list(self.role_options.keys()),
            state="disabled"
        )
        self.role_combo.set(default_role)
        self.role_combo.grid(row=0, column=0, sticky="ew")

        # [?] 권한 설명 도움말 버튼
        self.role_help_btn = ctk.CTkButton(
            signup_role_frame,
            text="?",
            width=28,
            height=28,
            font=ctk.CTkFont(size=13, weight="bold"),
            fg_color=("#3B82F6", "#2563EB"),
            hover_color=("#2563EB", "#1D4ED8"),
            command=self.show_role_help
        )
        self.role_help_btn.grid(row=0, column=1, padx=(6, 0))
        current_row += 1

        button_frame = ctk.CTkFrame(main_frame, fg_color="transparent")
        button_frame.pack(pady=20, padx=20, fill="x")

        # Legal Notice Agreement Section
        legal_frame = ctk.CTkFrame(main_frame, fg_color="transparent")
        legal_frame.pack(pady=(10, 0), padx=20, fill="x")
        
        self.legal_agreed = ctk.BooleanVar(value=False)
        
        self.legal_check = ctk.CTkCheckBox(
            legal_frame, 
            text="이용약관 및 법적고지에 동의합니다.", 
            variable=self.legal_agreed,
            font=ctk.CTkFont(size=12)
        )
        self.legal_check.pack(side="left")
        
        self.view_legal_btn = ctk.CTkButton(
            legal_frame,
            text="내용 보기",
            width=80,
            height=24,
            fg_color="gray",
            font=ctk.CTkFont(size=11),
            command=self.open_legal_notice
        )
        self.view_legal_btn.pack(side="right")

        register_button = ctk.CTkButton(button_frame, text="등록하기", command=self.register_user)
        register_button.pack(side="right")

    def show_role_help(self):
        """권한별 상세 기능 및 권한 안내를 팝업으로 표시합니다."""
        from modules.ui_components import ModernInfoDialog
        help_msg = (
            "【 시스템 5대 권한 체계 안내 】\n\n"
            "🔹 QC (품질관리원)\n"
            "  - 품질 서류 관리: 원료목록보고, COA, MSDS, 제품표준서, 제조관리기록서\n"
            "  - 거래처 관리 (검색/참고 조회 전용)\n\n"
            "🔹 RD (연구원)\n"
            "  - 연구 서류 관리: 처방, 견적, 전성분, 물성치/SPEC, 기능성보고/참고자료\n"
            "  - 성분 / 거래처 관리 (검색/참고 조회 전용)\n\n"
            "🔹 RQ (연구/품질 통합관리자)\n"
            "  - RD + QC 모든 연구 및 품질 서류 통합 관리\n\n"
            "🔹 RQD (연구/품질/데이터 관리자)\n"
            "  - RQ 모든 기능 + 성분/거래처 원천 데이터의 등록/수정/삭제 권한\n\n"
            "🔹 MSAD (마스터 관리자)\n"
            "  - 시스템 최고 권한: 모든 서류 + 모든 데이터 + 회원 관리 + 백업 권한\n\n"
            "※ 신규 가입 시 기본적으로 'RD(연구원)' 권한으로 생성되며,\n"
            "   가입 완료 후 관리자가 필요한 권한으로 변경할 수 있습니다."
        )
        ModernInfoDialog(self, title="권한 체계 안내", message=help_msg)

    def open_legal_notice(self):
        """법적 고지 팝업을 엽니다."""
        from modules.legal_notice import LegalNoticeDialog
        import os
        
        # 프로젝트 루트 경로 찾기 (sys.path에 이미 추가되어 있다고 가정하거나 상대경로 사용)
        # signup.py는 modules 폴더에 있으므로 상위 폴더가 프로젝트 루트
        PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        
        # 현재 버전 가져오기 시도
        try:
            with open(os.path.join(PROJECT_ROOT, 'VERSION'), 'r', encoding='utf-8') as f:
                ver = f.read().strip()
                # Normalize version string (ensure leading 'v')
                if ver and not ver.startswith('v') and re.match(r'^\d+(?:\.\d+)*$', ver):
                    ver = 'v' + ver
        except:
             ver = "v??"

        # 회원가입 시에는 무조건 동의를 받아야 함 (already_agreed=False)
        # 동의 시 체크박스 자동 선택 콜백
        def on_dialog_agree():
            self.legal_agreed.set(True)

        LegalNoticeDialog(self, ver, on_dialog_agree, None, already_agreed=False)


    def open_db_settings(self):
        """회원가입 창에서 DB 경로를 설정하고 즉시 재연결합니다."""
        from tkinter import filedialog
        import configparser
        
        # config 경로 획득
        config_path = getattr(self.master, 'config_path', None)
        if not config_path or not os.path.exists(config_path):
            config_path = os.path.join(os.getenv('APPDATA', os.path.expanduser('~')), 'CosRnD', 'config.ini')
            if not os.path.exists(config_path):
                config_path = os.path.join(PROJECT_ROOT, 'config.ini')

        config = configparser.ConfigParser(interpolation=None)
        try:
            if os.path.exists(config_path):
                config.read(config_path, encoding='utf-8')
        except Exception:
            pass

        current = config.get('Paths', 'shared_db_path', fallback='') if config.has_section('Paths') else ''
        folder = filedialog.askdirectory(
            title="공유 DB 저장 폴더 선택",
            initialdir=current if current and os.path.exists(current) else os.path.expanduser('~')
        )
        
        if folder:
            try:
                if not config.has_section('Paths'):
                    config.add_section('Paths')
                config.set('Paths', 'shared_db_path', folder)
                config.set('Paths', 'database_dir', folder)
                with open(config_path, 'w', encoding='utf-8') as f:
                    config.write(f)

                # DB 재연결
                app_path = getattr(self.master, 'application_path', PROJECT_ROOT)
                db_manager.dispose_engine()
                db_manager.setup_database(app_path, config_path, None)

                # 라벨 텍스트 갱신
                cur_db = getattr(db_manager, 'db_path', folder)
                cur_db_display = os.path.basename(os.path.dirname(cur_db)) if cur_db else "지정폴더"
                self.db_status_label.configure(text=f"📁 연동 DB: {os.path.basename(cur_db)} ({cur_db_display})")
                
                # 마스터(LoginWindow)의 메시지 라벨도 업데이트
                if hasattr(self.master, 'show_message'):
                    self.master.show_message(f"DB 연결 성공!\n{folder}", "green")

                messagebox.showinfo("DB 연동 완료", f"선택한 공유 DB와 성공적으로 연결되었습니다.\n\n경로: {folder}", parent=self)
            except Exception as e:
                messagebox.showerror("DB 연동 오류", f"DB 연결 중 오류가 발생했습니다:\n{e}", parent=self)

    def register_user(self):
        """사용자 등록 로직을 처리합니다."""
        # 입력 값 가져오기
        username = self.entries["username"].get().strip()
        password = self.entries["password"].get().strip()
        password_confirm = self.entries["password_confirm"].get().strip()
        position = self.entries["position"].get().strip()
        contact = self.entries["contact"].get().strip()
        zip_code = self.entries["zip_code"].get().strip()
        address = self.entries["address"].get().strip()
        
        # 권한 가져오기
        role_display = self.role_combo.get()
        role_code = self.role_options.get(role_display, "RD")
        # 정책: 초기 설정이 아닌 경우 무조건 RD로 강제
        if not self.is_initial_setup:
            role_code = "RD"

        # 1. 필수 입력 값 확인
        if not username or not password or not password_confirm:
            messagebox.showwarning("입력 오류", "사용자 ID와 비밀번호는 필수 항목입니다.", parent=self)
            return

        # 1-1. 이용약관 동의 확인 (추가)
        if not self.legal_agreed.get():
            messagebox.showwarning("동의 필요", "이용약관 및 법적고지에 동의해야 가입할 수 있습니다.\n[내용 보기]를 눌러 확인해주세요.", parent=self)
            return

        # config.ini 경로 찾기
        import os
        config_path = None
        if hasattr(self, 'master') and self.master:
            if hasattr(self.master, 'config_path'):
                config_path = self.master.config_path
        if not config_path:
            PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
            config_path = os.path.join(PROJECT_ROOT, 'config.ini')

        # 약관 동의 상태를 config.ini에 영구 기록
        try:
            import configparser
            config = configparser.ConfigParser(interpolation=None)
            if os.path.exists(config_path):
                config.read(config_path, encoding='utf-8')
            if not config.has_section('Legal'):
                config.add_section('Legal')
            config.set('Legal', 'agreed_version', 'agreed')
            with open(config_path, 'w', encoding='utf-8') as f:
                config.write(f)
            print("[SIGNUP] 이용약관 및 법적고지 동의 상태를 config.ini에 저장 완료")
        except Exception as config_err:
            print(f"[SIGNUP] config.ini 동의 상태 저장 실패: {config_err}")

        # 2. 비밀번호 일치 여부 확인
        if password != password_confirm:
            messagebox.showwarning("입력 오류", "비밀번호가 일치하지 않습니다.", parent=self)
            return

        session = db_manager.get_session()
        try:
            # 3. 사용자 ID 중복 확인
            existing_user = session.query(User).filter_by(username=username).first()
            if existing_user:
                messagebox.showwarning("입력 오류", "이미 사용 중인 ID입니다.", parent=self)
                return

            # 3-0. 첫 번째 사용자 확인
            user_count = session.query(User).count()
            is_first_user = (user_count == 0)
            
            if is_first_user:
                print("  * [첫 사용자] 자동으로 관리자(MSAD) 권한 부여")
                role_code = "MSAD"
                messagebox.showinfo("첫 사용자", 
                    "DB에 첫 번째 사용자를 등록합니다.\n"
                    "자동으로 최고 관리자(MSAD) 권한이 부여됩니다.", 
                    parent=self)

            # 3-1. 일반 가입 시 MSAD/RQD 권한 제한
            if not self.is_initial_setup and not is_first_user and role_code in ("MSAD", "RQD"):
                messagebox.showerror("권한 오류", 
                    "일반 회원가입으로는 관리자 권한을 부여할 수 없습니다.\n"
                    "관리자에게 요청하여 권한을 변경하세요.", parent=self)
                return

            # 3-2. 담당번호(manager_code) 중복 검사 및 빈값 처리
            raw_manager_code = self.entries["manager_code"].get().strip()
            manager_code_val = raw_manager_code if raw_manager_code else None
            if manager_code_val:
                existing_manager = session.query(User).filter_by(manager_code=manager_code_val).first()
                if existing_manager:
                    messagebox.showerror("입력 오류", 
                        f"담당번호 '{manager_code_val}'는 이미 사용 중입니다.\n"
                        f"사용자: {existing_manager.username} ({existing_manager.real_name or '이름 없음'})",
                        parent=self)
                    return

            print("\n=== 사용자 등록 시작 ===")
            
            # 4. 비밀번호 암호화 및 사용자 생성
            hashed_password = bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt())
            print("  * 비밀번호 암호화 완료")
            
            from datetime import datetime
            timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            real_name_val = self.entries["real_name"].get().strip()
            
            initial_log = (
                f"[{timestamp}] by {username} - 신규 가입\n"
                f"- 사용자 ID: '{username}'\n"
                f"- 실명: '{real_name_val}'\n"
                f"- 직책: '{position}'\n"
                f"- 담당번호: '{raw_manager_code}'\n"
                f"- 권한: '{role_code}'"
            )
            
            new_user = User(
                username=username,
                real_name=real_name_val,
                password=hashed_password.decode('utf-8'),
                position=position,
                manager_code=manager_code_val,
                contact=contact,
                zip_code=zip_code,
                address=address,
                # 정책: RQD도 관리자(True) 처리
                is_admin=(role_code in ('MSAD', 'RQD')),
                role=role_code,  # 권한 코드 저장
                change_log=initial_log
            )
            
            print(f"  * 새 사용자 객체 생성 - ID: {username}, 권한: {role_code}")
            
            # 단일 트랜잭션에서 모든 작업 수행
            try:
                # 새 사용자 추가
                session.add(new_user)
                session.commit()
                print("  * DB 저장 완료")
                
                # 사용자 정보 다시 로드 (세션에서 최신 상태로)
                session.refresh(new_user)
                
                print(f"  * 사용자 정보 준비 완료 - ID: {new_user.id}, 권한: {new_user.role}")
                
                # UI 업데이트는 commit 이후에 수행
                messagebox.showinfo("성공", 
                    "첫 관리자 계정이 생성되었습니다." if self.is_initial_setup else "회원가입이 완료되었습니다.", 
                    parent=self)
                    
                # 성공 콜백 호출 (가입 후 자동 로그인) - User 객체 그대로 전달
                if self.on_success:
                    print("  * 로그인 콜백 호출")
                    self.on_success(new_user)
                
                self.destroy()
                print("=== 사용자 등록 완료 ===\n")
                
            except Exception as e:
                print(f"  * [오류] 사용자 등록 실패: {e}")
                session.rollback()
                raise

        except Exception as e:
            session.rollback()
            messagebox.showerror("데이터베이스 오류", f"등록 중 오류가 발생했습니다: {e}", parent=self)
        finally:
            session.close()

    def on_closing_initial_setup(self):
        """초기 설정 창을 닫으려고 할 때 프로그램을 종료합니다."""
        if messagebox.askyesno("프로그램 종료", 
                              "관리자 계정을 생성하지 않고 종료하시겠습니까?\n"
                              "계정이 없으면 프로그램을 사용할 수 없습니다.", 
                              parent=self):
            print("회원가입 창 닫기 - 프로그램 종료")
            try:
                # DB 연결 해제
                db_manager.dispose_engine()
                print("DB 연결 해제 완료")
            except Exception as e:
                print(f"DB 연결 해제 중 오류: {e}")
            
            try:
                # 회원가입 창 파괴
                self.destroy()
                
                # 메인 앱도 파괴
                if self.master:
                    self.master.destroy()
            except Exception as e:
                print(f"창 파괴 중 오류: {e}")
            
            # 강제 종료
            import os
            os._exit(0)

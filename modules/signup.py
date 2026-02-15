# modules/signup.py
import customtkinter as ctk
import tkinter
from tkinter import messagebox
import bcrypt
from database.db_manager import db_manager
from database.models import User
from utils import center_window_on_mouse_display

class SignupWindow(ctk.CTkToplevel):
    def __init__(self, master=None, is_initial_setup=False, on_success=None):
        super().__init__(master)
        self.is_initial_setup = is_initial_setup
        self.on_success = on_success

        self.title("회원가입")

        self.geometry("450x720")  # 높이 증가
        self.resizable(False, False)
        self.transient(master)
        self.grab_set()

        self.setup_ui()
        try:
            center_window_on_mouse_display(self)
        except Exception:
            pass

        # 회원가입 창이 뜰 때 법적 고지(약관) 내용도 자동으로 띄움
        # 동의하지 않고 닫으면 프로그램 종료됨 (LegalNoticeDialog 로직)
        self.after(200, self.open_legal_notice)


    def setup_ui(self):
        """회원가입 창의 UI 요소를 설정합니다."""
        main_frame = ctk.CTkFrame(self)
        main_frame.pack(padx=20, pady=20, fill="both", expand=True)

        title_label = ctk.CTkLabel(main_frame, text="신규 사용자 등록", font=ctk.CTkFont(size=20, weight="bold"))
        title_label.pack(pady=20)
        
        info_label = ctk.CTkLabel(main_frame, text="※ DB에 첫 번째 사용자로 등록하면\n자동으로 관리자 권한이 부여됩니다.", 
                                  wraplength=350, font=ctk.CTkFont(size=10), text_color="gray")
        info_label.pack(pady=(0, 10))

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
        role_label = ctk.CTkLabel(input_frame, text="권한")
        role_label.grid(row=current_row, column=0, padx=(0, 10), pady=5, sticky="w")
        
        # 관리자 존재 여부 확인 (권한 설명에서도 사용)
        if not self.is_initial_setup:
            from database.db_manager import db_manager
            self.has_admin = db_manager.has_admin_users()
        else:
            self.has_admin = False
        
        if self.is_initial_setup:
            # 초기 설정 시에는 MSAD만 선택 가능
            self.role_options = {
                "MSAD - 모든 관리자": "MSAD"
            }
            default_role = "MSAD - 모든 관리자"
            self.role_combo = ctk.CTkOptionMenu(
                input_frame,
                values=["MSAD - 모든 관리자"],
                state="disabled"
            )
        else:
            # 일반 가입은 무조건 일반(RD)로 생성, 권한 선택 비활성화
            self.role_options = {
                "RD - 연구원": "RD"
            }
            default_role = "RD - 연구원"
            self.role_combo = ctk.CTkOptionMenu(
                input_frame,
                values=["RD - 연구원"],
                state="disabled"
            )
        
        self.role_combo.set(default_role)
        self.role_combo.grid(row=current_row, column=1, pady=5, sticky="ew")
        current_row += 1
        
        # 권한 설명 라벨 (새로운 권한 체계)
        if self.is_initial_setup:
            role_info_text = "MSAD: 마스터 관리자 (모든 권한 + 데이터 백업 권한)"
        else:
            role_info_text = (
                "신규 사용자는 기본적으로 'RD - 연구원' 권한으로 생성됩니다.\n"
                "필요 시 관리자가 권한을 부여/변경합니다."
            )
        role_info = ctk.CTkLabel(
            input_frame, 
            text=role_info_text,
            font=ctk.CTkFont(size=10),
            text_color="gray",
            justify="left"
        )
        role_info.grid(row=current_row, column=1, pady=(0, 10), sticky="w")
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


    def register_user(self):
        """사용자 등록 로직을 처리합니다."""
        # 입력 값 가져오기
        username = self.entries["username"].get()
        password = self.entries["password"].get()
        password_confirm = self.entries["password_confirm"].get()
        position = self.entries["position"].get()
        contact = self.entries["contact"].get()
        zip_code = self.entries["zip_code"].get()
        address = self.entries["address"].get()
        
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

            print("\n=== 사용자 등록 시작 ===")
            
            # 4. 비밀번호 암호화 및 사용자 생성
            hashed_password = bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt())
            print("  * 비밀번호 암호화 완료")
            
            new_user = User(
                username=username,
                real_name=self.entries["real_name"].get().strip(),
                password=hashed_password.decode('utf-8'),
                position=position,
                contact=contact,
                zip_code=zip_code,
                address=address,
                # 정책: RQD도 관리자(True) 처리
                is_admin=(role_code in ('MSAD', 'RQD')),
                role=role_code  # 권한 코드 저장
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

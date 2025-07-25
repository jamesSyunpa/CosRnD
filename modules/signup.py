# modules/signup.py
import customtkinter as ctk
from tkinter import messagebox
import bcrypt
from database.db_manager import db_manager
from database.models import User

class SignupWindow(ctk.CTkToplevel):
    def __init__(self, master=None, is_initial_setup=False, on_success=None):
        super().__init__(master)
        self.is_initial_setup = is_initial_setup
        self.on_success = on_success

        if self.is_initial_setup:
            self.title("초기 관리자 계정 생성")
            self.protocol("WM_DELETE_WINDOW", self.on_closing_initial_setup) # 창 닫기 방지
        else:
            self.title("회원가입")

        self.geometry("400x600")
        self.resizable(False, False)
        self.transient(master)
        self.grab_set()

        self.setup_ui()


    def setup_ui(self):
        """회원가입 창의 UI 요소를 설정합니다."""
        main_frame = ctk.CTkFrame(self)
        main_frame.pack(padx=20, pady=20, fill="both", expand=True)

        title_text = "초기 관리자 계정 생성" if self.is_initial_setup else "신규 사용자 등록"
        title_label = ctk.CTkLabel(main_frame, text=title_text, font=ctk.CTkFont(size=20, weight="bold"))
        title_label.pack(pady=20)

        if self.is_initial_setup:
            info_label = ctk.CTkLabel(main_frame, text="프로그램을 사용하기 위한 첫 관리자 계정을 생성합니다.", wraplength=300)
            info_label.pack(pady=(0, 20))

        input_frame = ctk.CTkFrame(main_frame, fg_color="transparent")
        input_frame.pack(fill="x", padx=20)
        input_frame.grid_columnconfigure(1, weight=1)

        self.entries = {}
        labels = {
            "사용자 ID": "username",
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

        button_frame = ctk.CTkFrame(main_frame, fg_color="transparent")
        button_frame.pack(pady=20, padx=20, fill="x")

        register_button = ctk.CTkButton(button_frame, text="등록하기", command=self.register_user)
        register_button.pack(side="right")


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

        # 1. 필수 입력 값 확인
        if not username or not password or not password_confirm:
            messagebox.showwarning("입력 오류", "사용자 ID와 비밀번호는 필수 항목입니다.", parent=self)
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

            print("\n=== 사용자 등록 시작 ===")
            
            # 4. 비밀번호 암호화 및 사용자 생성
            hashed_password = bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt())
            print("  * 비밀번호 암호화 완료")
            
            new_user = User(
                username=username,
                password=hashed_password.decode('utf-8'),
                position=position,
                contact=contact,
                zip_code=zip_code,
                address=address,
                is_admin=self.is_initial_setup  # 초기 설정 시 관리자로 생성
            )
            
            print(f"  * 새 사용자 객체 생성 - ID: {username}, 관리자: {self.is_initial_setup}")
            
            # 단일 트랜잭션에서 모든 작업 수행
            try:
                # 초기 설정인 경우 기존 admin 계정 삭제
                if self.is_initial_setup:
                    admin = session.query(User).filter_by(username='admin').first()
                    if admin:
                        session.delete(admin)
                        print("  * 기존 admin 계정 삭제됨")
                
                # 새 사용자 추가
                session.add(new_user)
                session.commit()
                print("  * DB 저장 완료")
                
                # 사용자 정보 다시 로드 (세션에서 최신 상태로)
                session.refresh(new_user)
                
                # SimpleNamespace 객체 생성 (로그인용)
                from types import SimpleNamespace
                user_info = SimpleNamespace(
                    id=new_user.id,
                    username=new_user.username,
                    is_admin=new_user.is_admin,
                    position=new_user.position,
                    contact=new_user.contact,
                    zip_code=new_user.zip_code,
                    address=new_user.address
                )
                print(f"  * 사용자 정보 준비 완료 - ID: {user_info.id}, 관리자: {user_info.is_admin}")
                
                # UI 업데이트는 commit 이후에 수행
                messagebox.showinfo("성공", 
                    "초기 관리자 계정이 생성되었습니다." if self.is_initial_setup else "회원가입이 완료되었습니다.", 
                    parent=self)
                    
                # 성공 콜백 호출 (가입 후 자동 로그인)
                if self.on_success:
                    print("  * 로그인 콜백 호출")
                    self.on_success(user_info)
                
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
        """초기 설정 창을 닫으려고 할 때 경고 메시지를 표시합니다."""
        messagebox.showwarning("경고", "초기 관리자 계정을 생성해야 프로그램을 사용할 수 있습니다.", parent=self)

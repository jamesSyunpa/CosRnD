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

        self.geometry("450x720")  # 높이 증가
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
            # 일반 가입 시에는 관리자 존재 여부에 따라 권한 결정
            if self.has_admin:
                # 이미 관리자가 있으면 MSAD 제외
                self.role_options = {
                    "QC - 품질관리원": "QC",
                    "RD - 연구원": "RD",
                    "RQ - 연구/품질 통합관리자": "RQ",
                    "RQD - 연구/품질/데이터 관리자": "RQD"
                }
            else:
                # 관리자가 없으면 모든 권한 허용
                self.role_options = {
                    "QC - 품질관리원": "QC",
                    "RD - 연구원": "RD",
                    "RQ - 연구/품질 통합관리자": "RQ",
                    "RQD - 연구/품질/데이터 관리자": "RQD",
                    "MSAD - 모든 관리자": "MSAD"
                }
            
            default_role = "RD - 연구원"
            self.role_combo = ctk.CTkOptionMenu(
                input_frame,
                values=list(self.role_options.keys())
            )
        
        self.role_combo.set(default_role)
        self.role_combo.grid(row=current_row, column=1, pady=5, sticky="ew")
        current_row += 1
        
        # 권한 설명 라벨 (새로운 권한 체계)
        if self.is_initial_setup:
            role_info_text = "MSAD: 마스터 관리자 (모든 권한 + 데이터 백업 권한)"
        else:
            if self.has_admin:
                role_info_text = (
                    "QC: 품질 서류 관리 (원료목록보고, COA, MSDS, 제품표준서, 제조관리기록서)\n"
                    "     + 거래처 관리 (검색/참고만)\n"
                    "RD: 연구 서류 관리 (처방, 견적, 전성분, 물성치/SPEC, 기능성보고/참고자료)\n"
                    "     + 성분/거래처 관리 (검색/참고만)\n"
                    "RQ: 연구/품질 통합관리 (RD + QC 모든 기능)\n"
                    "RQD: RQ 기능 + 모든 데이터 수정/삭제 권한\n"
                    "\n※ 관리자 계정이 이미 존재하여 MSAD 권한은 선택할 수 없습니다."
                )
            else:
                role_info_text = (
                    "QC: 품질 서류 관리 (원료목록보고, COA, MSDS, 제품표준서, 제조관리기록서)\n"
                    "     + 거래처 관리 (검색/참고만)\n"
                    "RD: 연구 서류 관리 (처방, 견적, 전성분, 물성치/SPEC, 기능성보고/참고자료)\n"
                    "     + 성분/거래처 관리 (검색/참고만)\n"
                    "RQ: 연구/품질 통합관리 (RD + QC 모든 기능)\n"
                    "RQD: RQ 기능 + 모든 데이터 수정/삭제 권한\n"
                    "MSAD: 마스터 관리자 (모든 기능 + 데이터 삭제 전 백업 권한)"
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
        
        # 권한 가져오기
        role_display = self.role_combo.get()
        role_code = self.role_options.get(role_display, "RD")

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

            # 3-1. 일반 가입 시 MSAD 권한 제한 검증
            if not self.is_initial_setup and role_code == "MSAD":
                if db_manager.has_admin_users():
                    messagebox.showerror("권한 오류", 
                        "이미 관리자 계정이 존재합니다.\n"
                        "보안상 추가 관리자 계정 생성은 제한됩니다.\n"
                        "다른 권한을 선택해주세요.", parent=self)
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
                is_admin=(role_code == 'MSAD'),  # MSAD만 is_admin=True
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

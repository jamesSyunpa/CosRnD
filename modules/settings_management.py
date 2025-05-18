# modules/settings_management.py
import customtkinter as ctk
from tkinter import messagebox, filedialog
import configparser
import os
import modules.excel_handler as excel_handler
from database.models import Formulation, FormulationItem, Material, Client, User # 모델 import 추가
from modules.ui_components import HelpPopup # HelpPopup 클래스를 ui_components에서 가져옵니다.

class SettingsManagementFrame(ctk.CTkFrame):
    def __init__(self, master, current_user, app, config_path, application_path):
        super().__init__(master)
        self.current_user = current_user
        self.app = app  # 메인 App 인스턴스를 저장
        self.config_path = config_path
        self.application_path = application_path

        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(0, weight=1)

        # --- 상단 프레임 (탭 뷰 + 도움말 버튼) ---
        top_frame = ctk.CTkFrame(self, fg_color="transparent")
        top_frame.grid(row=0, column=0, sticky="nsew")
        top_frame.grid_columnconfigure(0, weight=1)
        top_frame.grid_rowconfigure(0, weight=1)

        # 탭의 위치를 가운데(center)로 설정
        self.tab_view = ctk.CTkTabview(top_frame, anchor="center", command=self.on_tab_change)
        self.tab_view.grid(row=0, column=0, sticky="nsew", padx=10, pady=10)

        # 도움말 버튼
        self.help_button = ctk.CTkButton(top_frame, text="도움말", width=80, command=self.show_help)
        self.help_button.place(relx=0.98, y=10, anchor="ne")

        self.tab_view.add("설정")

        # 각 탭의 컨텐츠 구성
        self.setup_path_settings_tab(self.tab_view.tab("설정"))

    def show_help(self):
        """설정 관리 도움말을 표시합니다."""
        title = "설정 관리 도움말"
        message = """
        [설정 관리 사용법]
        
        이 화면에서는 프로그램의 동작 환경을 설정합니다.
        (이 기능은 관리자만 사용할 수 있습니다)
        
        1. 테마 설정: 프로그램의 전체적인 디자인 테마(Light/Dark/System)를 변경합니다.
        
        2. 경로 설정: DB 파일과 엑셀 파일의 기본 저장/불러오기 위치를 지정합니다.
           - DB 저장 경로는 변경 후 프로그램을 재시작해야 완전히 적용됩니다.
           
        3. 엑셀 폼 내보내기: 데이터 대량 입력을 위한 엑셀 템플릿 파일을 다운로드합니다.
        """
        HelpPopup(self, title, message)

    def on_tab_change(self):
        """탭이 변경될 때마다 활동을 기록합니다."""
        selected_tab = self.tab_view.get()
        self.app.record_action(f"settings/{selected_tab}")

    def switch_to_tab(self, tab_name):
        """외부에서 특정 탭으로 전환하는 메서드 (단순화)"""
        self.tab_view.set(tab_name)

    def change_appearance_mode_event(self, new_appearance_mode: str):
        """테마 변경 이벤트를 처리하고 설정에 저장합니다."""
        # CustomTkinter의 테마 변경 함수 호출
        ctk.set_appearance_mode(new_appearance_mode)

        # 메인 앱의 Treeview 스타일 업데이트 함수 호출
        self.app.update_treeview_style()
        
        # 변경된 설정을 config.ini 파일에 저장
        config = configparser.ConfigParser()
        config.read(self.config_path, encoding='utf-8')
        if not config.has_section('Appearance'):
            config.add_section('Appearance')
        # 옵션 메뉴의 값(Light, Dark)을 소문자로 변환하여 저장
        config.set('Appearance', 'theme', new_appearance_mode.lower())
        
        try:
            with open(self.config_path, 'w', encoding='utf-8') as configfile:
                config.write(configfile, space_around_delimiters=False)
        except Exception as e:
            # 파일 저장 실패 시 사용자에게 알림
            messagebox.showerror("오류", f"테마 설정 저장 중 오류가 발생했습니다: {e}")

    def setup_path_settings_tab(self, tab_frame):
        """경로 설정 탭의 UI를 설정하고, 관리자 전용 데이터 리셋 버튼을 추가합니다."""
        # --- 경로 설정 프레임 ---
        path_frame = ctk.CTkFrame(tab_frame)
        path_frame.pack(padx=20, pady=20, fill="x")
        path_frame.grid_columnconfigure(1, weight=1)

        # --- 테마 설정 ---
        ctk.CTkLabel(path_frame, text="테마 설정").grid(row=0, column=0, padx=10, pady=10, sticky="w")
        self.theme_menu = ctk.CTkOptionMenu(
            path_frame, 
            values=["Light", "Dark", "System"],
            command=self.change_appearance_mode_event
        )
        self.theme_menu.grid(row=0, column=1, padx=10, pady=10, sticky="w")

        ctk.CTkLabel(path_frame, text="DB 저장 경로").grid(row=1, column=0, padx=10, pady=10, sticky="w")
        self.db_path_entry = ctk.CTkEntry(path_frame)
        self.db_path_entry.grid(row=1, column=1, padx=10, pady=10, sticky="ew")
        db_browse_button = ctk.CTkButton(path_frame, text="찾아보기...", command=self.browse_db_path)
        db_browse_button.grid(row=1, column=2, padx=10, pady=10)

        ctk.CTkLabel(path_frame, text="엑셀 기본 경로").grid(row=2, column=0, padx=10, pady=10, sticky="w")
        self.excel_path_entry = ctk.CTkEntry(path_frame)
        self.excel_path_entry.grid(row=2, column=1, padx=10, pady=10, sticky="ew")
        excel_browse_button = ctk.CTkButton(path_frame, text="찾아보기...", command=self.browse_excel_path)
        excel_browse_button.grid(row=2, column=2, padx=10, pady=10)

        save_button = ctk.CTkButton(tab_frame, text="경로 저장", command=self.save_paths)
        save_button.pack(pady=20, padx=20, anchor="e")
        
        info_label = ctk.CTkLabel(
            tab_frame, 
            text="* DB 저장 경로는 프로그램 재시작 시 적용됩니다.", 
            text_color=("#B00020", "#FF8A80")  # (라이트 모드 색상, 다크 모드 색상)
        )
        info_label.pack(pady=10, padx=20, anchor="e")

        # --- 관리자 전용 기능 ---
        if self.current_user.is_admin:
            # --- 엑셀 폼 내보내기 프레임 ---
            export_frame = ctk.CTkFrame(tab_frame)
            export_frame.pack(padx=20, pady=(20, 10), fill="x")
            export_frame.grid_columnconfigure((0, 1, 2), weight=1)

            ctk.CTkLabel(export_frame, text="엑셀 폼 내보내기", font=ctk.CTkFont(weight="bold")).grid(row=0, column=0, columnspan=3, pady=(10, 5))

            ctk.CTkButton(export_frame, text="성분 폼 내보내기", command=self.export_material_template).grid(row=1, column=0, padx=5, pady=10, sticky="ew")
            ctk.CTkButton(export_frame, text="거래처 폼 내보내기", command=self.export_client_template).grid(row=1, column=1, padx=5, pady=10, sticky="ew")
            ctk.CTkButton(export_frame, text="사용자 폼 내보내기", command=self.export_user_template).grid(row=1, column=2, padx=5, pady=10, sticky="ew")

            # --- 데이터 리셋 프레임 ---
            reset_frame = ctk.CTkFrame(tab_frame)
            reset_frame.pack(padx=20, pady=(50, 20), fill="x", anchor="s")
            reset_frame.grid_columnconfigure((0, 1, 2, 3), weight=1)

            ctk.CTkLabel(reset_frame, text="데이터 리셋 (주의: 되돌릴 수 없음)", font=ctk.CTkFont(weight="bold")).grid(row=0, column=0, columnspan=4, pady=(10, 5))

            reset_button_style = {"fg_color": "#D32F2F", "hover_color": "#B71C1C"}

            ctk.CTkButton(reset_frame, text="성분 데이터 리셋", command=lambda: self.confirm_reset("materials"), **reset_button_style).grid(row=1, column=0, padx=5, pady=10, sticky="ew")
            ctk.CTkButton(reset_frame, text="거래처 데이터 리셋", command=lambda: self.confirm_reset("clients"), **reset_button_style).grid(row=1, column=1, padx=5, pady=10, sticky="ew")
            ctk.CTkButton(reset_frame, text="사용자 데이터 리셋", command=lambda: self.confirm_reset("users"), **reset_button_style).grid(row=1, column=2, padx=5, pady=10, sticky="ew")
            
            all_reset_style = {"fg_color": "#B71C1C", "hover_color": "#7f0000"}
            ctk.CTkButton(reset_frame, text="전체 데이터 리셋", command=lambda: self.confirm_reset("all"), **all_reset_style).grid(row=1, column=3, padx=5, pady=10, sticky="ew")

        else:
            # 관리자가 아니면 경로 설정 비활성화
            self.db_path_entry.configure(state="disabled")
            db_browse_button.configure(state="disabled")
            self.excel_path_entry.configure(state="disabled")
            excel_browse_button.configure(state="disabled")
            save_button.configure(state="disabled")

        self.load_settings()

    def load_settings(self):
        """config.ini에서 설정(경로, 테마)을 읽어와 UI에 표시합니다."""
        config = configparser.ConfigParser()
        config.read(self.config_path, encoding='utf-8')
        
        # 테마 설정 로드
        theme = config.get('Appearance', 'theme', fallback='system').capitalize()
        self.theme_menu.set(theme)

        # 경로 설정 로드
        db_dir = config.get('Paths', 'database_dir', fallback='data')
        excel_dir = config.get('Paths', 'excel_dir', fallback='')
        self.db_path_entry.delete(0, 'end')
        self.db_path_entry.insert(0, db_dir)
        self.excel_path_entry.delete(0, 'end')
        self.excel_path_entry.insert(0, excel_dir)

    def browse_db_path(self):
        path = filedialog.askdirectory(title="DB 저장 폴더 선택")
        # 사용자가 폴더를 선택한 경우에만 경로를 업데이트합니다.
        if path:
            # 선택된 절대 경로를 프로그램 실행 파일 기준의 상대 경로로 변환합니다.
            # 만약 변환할 수 없는 다른 드라이브 등의 경로라면 절대 경로를 그대로 사용합니다.
            try:
                relative_path = os.path.relpath(path, self.application_path)
            except ValueError:
                relative_path = path # 다른 드라이브일 경우 절대경로 사용
            self.db_path_entry.delete(0, 'end')
            self.db_path_entry.insert(0, relative_path)

    def browse_excel_path(self):
        path = filedialog.askdirectory(title="엑셀 기본 경로 선택")
        if path:
            self.excel_path_entry.delete(0, 'end')
            self.excel_path_entry.insert(0, path)

    def save_paths(self):
        from database.db_manager import db_manager # db_manager를 함수 내에서 import

        config = configparser.ConfigParser()
        config.read(self.config_path, encoding='utf-8')

        if not config.has_section('Paths'):
            config.add_section('Paths')

        old_db_dir_relative = config.get('Paths', 'database_dir', fallback='data')
        new_db_dir_relative = self.db_path_entry.get().strip()

        # DB 경로가 변경되었는지 확인
        if old_db_dir_relative != new_db_dir_relative:
            old_db_path = os.path.join(self.application_path, old_db_dir_relative, "cosmetic.db")
            
            # 이전 경로에 DB 파일이 존재하는지 확인
            if os.path.exists(old_db_path):
                # 사용자에게 선택 요청
                dialog = ctk.CTkToplevel(self)
                dialog.title("DB 파일 처리")
                dialog.geometry("450x180")
                dialog.transient(self)
                dialog.grab_set()
                
                result = {"action": None}

                def set_action(action):
                    result["action"] = action
                    dialog.destroy()

                ctk.CTkLabel(dialog, text="기존 DB 파일을 어떻게 처리하시겠습니까?", font=ctk.CTkFont(size=14)).pack(pady=20)
                
                btn_frame = ctk.CTkFrame(dialog, fg_color="transparent")
                btn_frame.pack(pady=10)
                
                ctk.CTkButton(btn_frame, text="새 경로로 이동", command=lambda: set_action("move")).pack(side="left", padx=10)
                ctk.CTkButton(btn_frame, text="새로 생성 (기존 파일 유지)", command=lambda: set_action("create")).pack(side="left", padx=10)
                ctk.CTkButton(btn_frame, text="취소", fg_color="gray", command=lambda: set_action("cancel")).pack(side="left", padx=10)
                
                self.wait_window(dialog) # 대화상자가 닫힐 때까지 대기

                if result["action"] == "move":
                    # 1. DB 연결 해제
                    db_manager.dispose_engine()

                    new_db_dir_absolute = os.path.join(self.application_path, new_db_dir_relative)
                    os.makedirs(new_db_dir_absolute, exist_ok=True)
                    new_db_path = os.path.join(new_db_dir_absolute, "cosmetic.db")
                    try:
                        # 2. 파일 이동
                        os.rename(old_db_path, new_db_path)
                        
                        # 3. 설정 파일에 새 경로 저장
                        config.set('Paths', 'database_dir', new_db_dir_relative)
                        with open(self.config_path, 'w', encoding='utf-8') as configfile:
                            config.write(configfile)
                        
                        # 4. DB 연결 재설정 및 안내
                        db_manager.setup_database(self.application_path)
                        messagebox.showinfo("성공", "DB 파일이 새 경로로 이동되었으며, 연결이 재설정되었습니다.")
                        # 재시작하지 않고 계속 진행

                    except Exception as e:
                        messagebox.showerror("오류", f"DB 파일 이동 중 오류 발생: {e}")
                        # 이동 실패 시, 기존 경로로 다시 연결 시도
                        db_manager.setup_database(self.application_path)
                        return # 오류 발생 시 저장 중단
                elif result["action"] == "cancel":
                    messagebox.showinfo("취소", "경로 저장이 취소되었습니다.")
                    return # 저장 작업 취소

        # 설정 파일에 새로운 경로 저장
        config.set('Paths', 'database_dir', new_db_dir_relative)
        config.set('Paths', 'excel_dir', self.excel_path_entry.get())
        
        try:
            with open(self.config_path, 'w', encoding='utf-8') as configfile:
                config.write(configfile)
            messagebox.showinfo("성공", "경로가 저장되었습니다.\nDB 경로는 프로그램 재시작 시 적용됩니다.")
        except Exception as e:
            messagebox.showerror("오류", f"설정 저장 중 오류가 발생했습니다: {e}")

    # ===== 엑셀 폼 내보내기 메서드들 =====
    def export_material_template(self):
        """성분(원료) 데이터용 엑셀 템플릿을 내보냅니다."""
        sheets = {
            "원료정보": ["코드", "원료명", "단가", "포장단위", "거래처", "제조원명", "HS CODE", "원산지", "영문원료명", "NMPA등록번호", "사용여부(Y/N)"],
            "전성분정보": ["원료코드", "한글전성분", "INGREDIENT", "CAS NO.", "조성비(%)", "기능", "EWG등급", "EWG등급데이터"]
        }
        excel_handler.export_multisheet_template(sheets, "원료_템플릿.xlsx")

    def export_client_template(self):
        """거래처 데이터용 엑셀 템플릿을 내보냅니다."""
        headers = ["거래처 유형", "거래처코드(사업자번호)", "거래처명", "대표자명", "담당자명", "연락처", "팩스", "이메일", "우편번호", "주소", "사용여부(Y/N)"] # noqa
        excel_handler.export_template(headers, "거래처_템플릿.xlsx")

    def export_user_template(self):
        """사용자 데이터용 엑셀 템플릿을 내보냅니다."""
        headers = ["사용자 ID", "비밀번호", "직책", "연락처", "우편번호", "주소", "관리자여부(True/False)"]
        excel_handler.export_template(headers, "사용자_템플릿.xlsx")

    def confirm_reset(self, reset_type: str):
        """데이터 리셋 전 사용자에게 확인을 받는 대화상자를 띄웁니다."""
        
        messages = {
            "materials": "모든 성분(원료) 데이터가 삭제됩니다.",
            "clients": "모든 거래처 데이터가 삭제됩니다.",
            "users": "기본 admin 계정을 제외한 모든 사용자 데이터가 삭제됩니다.",
            "all": "모든 처방, 성분, 거래처, 사용자(admin 제외) 데이터가 영구적으로 삭제됩니다."
        }
        
        message = messages.get(reset_type, "선택된 데이터가 삭제됩니다.")
        
        dialog = ctk.CTkToplevel(self)
        dialog.title("경고")
        dialog.geometry("420x150")
        dialog.transient(self)
        dialog.grab_set()
        dialog.resizable(False, False)

        label = ctk.CTkLabel(dialog, text=f"⚠ {message}\n\n이 작업은 되돌릴 수 없습니다. 계속하시겠습니까?", 
                               font=ctk.CTkFont(size=14))
        label.pack(pady=20, padx=20, fill="both", expand=True)

        button_frame = ctk.CTkFrame(dialog, fg_color="transparent")
        button_frame.pack(pady=(0, 20))

        confirm_btn = ctk.CTkButton(button_frame, text="삭제 실행", fg_color="red", hover_color="#aa0000",
                                    command=lambda: self.execute_reset(dialog, reset_type))
        confirm_btn.pack(side="left", padx=10)

        cancel_btn = ctk.CTkButton(button_frame, text="취소", command=dialog.destroy)
        cancel_btn.pack(side="left", padx=10)

    def _reset_all_data(self, session, deleted_counts):
        """모든 데이터를 참조 역순으로 안전하게 삭제합니다. (ORM 객체 로드 후 삭제)"""
        # 참조의 역순으로 삭제: Formulation -> Material -> Client -> User.
        # FormulationItem과 Ingredient는 각각의 부모가 삭제될 때 cascade 설정으로 자동 삭제됩니다.
        
        # 1. 모든 처방 삭제 (FormulationItem은 cascade로 삭제됨)
        formulations = session.query(Formulation).all()
        if formulations:
            deleted_counts["formulations"] = len(formulations)
            for f in formulations: session.delete(f)
            session.flush() # DB에 대한 반영을 위해 FormulationItem이 삭제되도록 함

        # 2. 모든 원료 삭제 (Ingredient는 cascade로 삭제됨)
        materials = session.query(Material).all()
        if materials:
            deleted_counts["materials"] = len(materials)
            for m in materials: session.delete(m)
            session.flush()

        # 3. 모든 거래처 삭제
        clients = session.query(Client).all()
        if clients:
            deleted_counts["clients"] = len(clients)
            for c in clients: session.delete(c)
            session.flush()

        # 4. 모든 사용자 삭제
        users = session.query(User).all()
        if users:
            deleted_counts["users"] = len(users)
            for u in users: session.delete(u)

    def _reset_materials_data(self, session, deleted_counts):
        """성분(원료) 관련 데이터를 안전하게 삭제합니다. (ORM 객체 로드 후 삭제)"""
        # 1. 원료를 참조하는 FormulationItem의 material_id를 NULL로 설정
        session.query(FormulationItem).update({"material_id": None}, synchronize_session=False)
        session.flush()

        # 2. 모든 원료 삭제
        materials = session.query(Material).all()
        if materials:
            deleted_counts["materials"] = len(materials)
            for m in materials:
                session.delete(m)
        session.flush()


    def execute_reset(self, dialog, reset_type: str):
        """선택된 타입의 데이터를 삭제합니다."""
        dialog.destroy()
        from database.db_manager import db_manager
        from database.models import User, Client, Material, Ingredient, Formulation, FormulationItem

        session = db_manager.get_session()        
        deleted_counts = {"users": 0, "clients": 0, "materials": 0, "formulations": 0}

        try:
            if reset_type == "all":
                self._reset_all_data(session, deleted_counts)
            elif reset_type == "users":
                users = session.query(User).filter(User.username != 'admin').all() # noqa
                deleted_counts["users"] = len(users)
                for u in users: session.delete(u)
            elif reset_type == "clients":
                # 거래처를 참조하는 Material, Formulation의 필드를 먼저 NULL로 업데이트
                session.query(Material).update({Material.client_id: None}, synchronize_session=False) # noqa
                session.query(Formulation).update({
                    Formulation.target_client_id: None,
                    Formulation.oem_odm_client_id: None
                }, synchronize_session=False)
                clients = session.query(Client).all()
                deleted_counts["clients"] = len(clients)
                for c in clients: session.delete(c)
            elif reset_type == "materials":
                self._reset_materials_data(session, deleted_counts)
            
            session.commit()
            
            # 성공 메시지 생성
            msg_parts = []
            if deleted_counts["formulations"] > 0: msg_parts.append(f"- 처방: {deleted_counts['formulations']}개")
            if deleted_counts["materials"] > 0: msg_parts.append(f"- 성분(원료): {deleted_counts['materials']}개")
            if deleted_counts["clients"] > 0: msg_parts.append(f"- 거래처: {deleted_counts['clients']}개")
            if deleted_counts["users"] > 0: msg_parts.append(f"- 사용자: {deleted_counts['users']}명")
            
            if not msg_parts:
                final_msg = "삭제할 데이터가 없습니다."
            else:
                final_msg = "데이터가 성공적으로 리셋되었습니다.\n" + "\n".join(msg_parts)

            messagebox.showinfo(
                "완료",
                final_msg
            )

        except Exception as e:
            session.rollback()
            messagebox.showerror("오류", f"데이터 리셋 중 오류 발생: {e}")
        finally:
            session.close()
            self.refresh_all_data_views()

    def refresh_all_data_views(self):
        """데이터 관리 화면의 모든 목록을 새로고침합니다."""
        try:
            data_frame = self.app.frames.get("data")
            if data_frame:
                # 각 탭의 목록 새로고침 메서드 호출
                if hasattr(data_frame, "load_clients"):
                    data_frame.load_clients()
                if hasattr(data_frame, "load_users"):
                    data_frame.load_users()
                
                # 성분 관리 프레임은 중첩되어 있으므로 찾아가서 호출
                material_tab = data_frame.tab_view.tab("성분 관리")
                if material_tab and material_tab.winfo_children():
                    material_frame = material_tab.winfo_children()[0]
                    if hasattr(material_frame, "refresh_data"):
                        material_frame.refresh_data()
            print("데이터 뷰 새로고침 완료")
        except Exception as e:
            print(f"데이터 뷰 새로고침 중 오류: {e}")

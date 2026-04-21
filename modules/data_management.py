# modules/data_management.py
import customtkinter as ctk
from tkinter import ttk, messagebox
import bcrypt
from modules.material_management import MaterialManagementFrame
from modules.document_management import CustomDropdown # CustomDropdown을 여기서 가져옵니다.
from database.db_manager import db_manager
from database.models import User, Client, Formulation
import modules.excel_handler as excel_handler
from datetime import datetime # noqa
from modules.ui_components import HelpPopup
from modules.history_popup import HistoryPopup
from modules.translation import get_texts

class DataManagementFrame(ctk.CTkFrame):
    def __init__(self, master, current_user, app, language="korean"):
        super().__init__(master)
        self.current_user = current_user
        self.app = app
        self.language = language

        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(0, weight=1)

        # --- 상단 프레임 (탭 뷰 + 도움말 버튼) ---
        top_frame = ctk.CTkFrame(self, fg_color="transparent")
        top_frame.grid(row=0, column=0, sticky="nsew")
        top_frame.grid_columnconfigure(0, weight=1)
        top_frame.grid_rowconfigure(0, weight=1)

        self.tab_view = ctk.CTkTabview(
            top_frame,
            command=self.on_tab_change,
            border_width=1,
            border_color=("gray80", "gray30"),
            segmented_button_selected_color=("#3B8ED0", "#1F6AA5"),
            segmented_button_unselected_color=("gray92", "gray20"),
            text_color=("black", "white"),
            segmented_button_selected_hover_color=("#3671A8", "#144870"),
            segmented_button_unselected_hover_color=("gray85", "gray28")
        )
        self.tab_view.grid(row=0, column=0, sticky="nsew", padx=10, pady=10)

        # 도움말 버튼
        self.texts = get_texts(self.language)
        self.help_button = ctk.CTkButton(top_frame, text=self.texts['help'], width=80, command=self.show_help)
        self.help_button.place(relx=0.98, y=10, anchor="ne")

        # --- 언어별 텍스트 ---
        texts = {
            "korean": {"ingredient": "성분 관리", "client": "거래처 관리", "user": "회원 관리"},
            "english": {"ingredient": "Ingredient Mgt.", "client": "Client Mgt.", "user": "User Mgt."}
        }
        current_texts = texts[self.language]

        self.tab_view.add(current_texts["ingredient"])
        self.setup_material_management_tab(self.tab_view.tab(current_texts["ingredient"]))

        # 관리자일 경우에만 거래처 및 회원 관리 탭 추가
        if self.current_user.is_admin:
            self.tab_view.add(current_texts["client"])
            self.tab_view.add(current_texts["user"])
            self.setup_client_management_tab(self.tab_view.tab(current_texts["client"]))
            self.setup_user_management_tab(self.tab_view.tab(current_texts["user"]))

    def show_help(self):
        """데이터 관리 도움말을 표시합니다."""
        title = self.texts['data_mgt_help_title']
        message = self.texts['data_mgt_help_message']
        HelpPopup(self, title, message)

    def on_tab_change(self):
        """탭이 변경될 때마다 활동을 기록합니다."""
        selected_tab = self.tab_view.get()
        self.app.record_action(f"data/{selected_tab}")

    def switch_to_tab(self, tab_name):
        """외부에서 특정 탭으로 전환하는 메서드"""
        try:
            self.tab_view.set(tab_name)
        except Exception as e:
            print(f"데이터 관리 탭 '{tab_name}'으로 전환 실패: {e}")

    def refresh_data(self):
        """데이터 새로고침이 필요한 경우 호출될 메서드"""
        pass # 추후 필요시 구현

    # ==============================================================================
    # 아래는 settings_management.py에서 이동 및 통합된 UI 설정 메서드들입니다.
    # ==============================================================================

    def setup_material_management_tab(self, tab_frame):
        """성분 관리 탭의 UI를 설정합니다."""
        tab_frame.grid_columnconfigure(0, weight=1)
        tab_frame.grid_rowconfigure(0, weight=1)
        material_frame = MaterialManagementFrame(tab_frame, self.current_user)
        material_frame.grid(row=0, column=0, sticky="nsew") # MaterialManagementFrame needs language

    def setup_user_management_tab(self, tab_frame):
        tab_frame.grid_columnconfigure(1, weight=1)
        tab_frame.grid_rowconfigure(0, weight=1)

        user_form_frame = ctk.CTkFrame(tab_frame)
        user_form_frame.grid(row=0, column=0, padx=10, pady=10, sticky="ns")
        
        form_label = ctk.CTkLabel(user_form_frame, text=self.texts['user_info'], font=ctk.CTkFont(size=14, weight="bold"))
        form_label.grid(row=0, column=0, columnspan=2, pady=(10, 20))

        user_labels = self.texts['user_labels']
        self.user_entries = {}
        current_row = 1
        for key, label_text in user_labels.items():
            ctk.CTkLabel(user_form_frame, text=label_text).grid(row=current_row, column=0, padx=10, pady=5, sticky="w")
            entry = ctk.CTkEntry(user_form_frame, width=200)
            entry.grid(row=current_row, column=1, padx=10, pady=5, sticky="ew")
            if key == "password":
                entry.configure(show="*")
                ctk.CTkLabel(user_form_frame, text=self.texts['password_helper'], font=ctk.CTkFont(size=10)).grid(row=current_row+1, column=1, padx=10, sticky="w")
                current_row += 1
            self.user_entries[key] = entry
            current_row += 1
        
        self.is_admin_var = ctk.StringVar(value="off")
        is_admin_check = ctk.CTkCheckBox(user_form_frame, text=self.texts['admin_privilege'], variable=self.is_admin_var, onvalue="on", offvalue="off")
        is_admin_check.grid(row=current_row, column=1, padx=10, pady=10, sticky="e")
        current_row += 1

        # 이력 보기 버튼
        self.user_history_button = ctk.CTkButton(user_form_frame, text=self.texts['view_selected_history'], command=self.show_selected_user_history, state="disabled")
        self.user_history_button.grid(row=current_row, column=1, padx=10, pady=10, sticky="e")
        current_row += 1

        user_button_frame = ctk.CTkFrame(user_form_frame, fg_color="transparent")
        user_button_frame.grid(row=current_row, column=0, columnspan=2, pady=20)
        
        self.user_save_button = ctk.CTkButton(user_button_frame, text=self.texts['save'], command=self.save_user)
        self.user_save_button.pack(side="left", padx=5)
        self.user_new_button = ctk.CTkButton(user_button_frame, text=self.texts['new'], command=self.clear_user_form)
        self.user_new_button.pack(side="left", padx=5)
        self.user_delete_button = ctk.CTkButton(user_button_frame, text=self.texts['delete'], command=self.delete_user, fg_color="#D32F2F", hover_color="#B71C1C")
        self.user_delete_button.pack(side="left", padx=5)

        user_list_frame = ctk.CTkFrame(tab_frame)
        user_list_frame.grid(row=0, column=1, padx=10, pady=10, sticky="nsew")
        user_list_frame.grid_rowconfigure(1, weight=1)
        user_list_frame.grid_columnconfigure(0, weight=1)

        list_header_frame = ctk.CTkFrame(user_list_frame, fg_color="transparent")
        list_header_frame.grid(row=0, column=0, pady=10, sticky="ew")
        list_header_frame.grid_columnconfigure(2, weight=1) # 오른쪽 정렬을 위한 빈 공간

        ctk.CTkLabel(list_header_frame, text=self.texts['user_list'], font=ctk.CTkFont(size=14, weight="bold")).grid(row=0, column=0, sticky="w")
        ctk.CTkButton(list_header_frame, text=self.texts['view_all_history'], command=self.show_all_user_history).grid(row=0, column=1, padx=(20, 0), sticky="w")

        # pack 대신 grid를 사용하여 오른쪽 정렬
        user_excel_frame = ctk.CTkFrame(list_header_frame, fg_color="transparent")
        user_excel_frame.grid(row=0, column=3, sticky="e")
        ctk.CTkButton(user_excel_frame, text=self.texts['export_data'], command=self.export_user_data).pack(side="left", padx=5)
        self.user_import_button = ctk.CTkButton(user_excel_frame, text=self.texts['import_data'], command=self.import_user_data)
        self.user_import_button.pack(side="left", padx=5)

        if not self.current_user.is_admin:
            self.user_save_button.configure(state="disabled")
            self.user_new_button.configure(state="disabled")
            self.user_delete_button.configure(state="disabled")
            is_admin_check.configure(state="disabled")
            self.user_import_button.configure(state="disabled")

        user_tree_columns = self.texts['user_tree_columns']
        user_column_ids = [k for k in user_tree_columns if k != 'id']
        self.user_tree = ttk.Treeview(user_list_frame, columns=user_column_ids, show="headings", selectmode="browse")
        self.user_tree.heading("username", text=user_tree_columns['username']); self.user_tree.column("username", width=150) # noqa
        self.user_tree.heading("manager_code", text=user_tree_columns['manager_code']); self.user_tree.column("manager_code", width=100, anchor="center") # noqa
        self.user_tree.heading("position", text=user_tree_columns['position']); self.user_tree.column("position", width=120) # noqa
        self.user_tree.heading("contact", text=user_tree_columns['contact']); self.user_tree.column("contact", width=120) # noqa
        self.user_tree.heading("is_admin", text=user_tree_columns['is_admin']); self.user_tree.column("is_admin", width=100, anchor="center") # noqa
        self.user_tree.grid(row=1, column=0, sticky="nsew")

        user_scrollbar = ttk.Scrollbar(user_list_frame, orient="vertical", command=self.user_tree.yview)
        self.user_tree.configure(yscrollcommand=user_scrollbar.set)
        user_scrollbar.grid(row=1, column=1, sticky="ns")

        self.user_tree.bind("<<TreeviewSelect>>", self.on_user_tree_select)
        self.load_users()

    def setup_client_management_tab(self, tab_frame):
        tab_frame.grid_columnconfigure(1, weight=1)
        tab_frame.grid_rowconfigure(0, weight=1)

        form_frame = ctk.CTkFrame(tab_frame)
        form_frame.grid(row=0, column=0, padx=10, pady=10, sticky="ns")
        
        form_label = ctk.CTkLabel(form_frame, text=self.texts['client_info'], font=ctk.CTkFont(size=14, weight="bold"))
        form_label.grid(row=2, column=0, columnspan=2, pady=(20, 10))

        # --- 거래처 검색 섹션 ---
        search_frame = ctk.CTkFrame(form_frame, fg_color="transparent")
        search_frame.grid(row=0, column=0, columnspan=2, pady=10, sticky="ew")
        search_frame.grid_columnconfigure(1, weight=1)

        ctk.CTkLabel(search_frame, text=self.texts['client_search'], font=ctk.CTkFont(weight="bold")).grid(row=0, column=0, columnspan=2, pady=(0, 5))
        
        self.client_search_type_combo = CustomDropdown(search_frame, values=self.texts['client_type_filter_values'], command=self.update_client_name_combo)
        self.client_search_type_combo.grid(row=1, column=0, padx=(0, 5), pady=5, sticky="ew")

        self.client_search_name_combo = CustomDropdown(search_frame, values=[self.texts['select_client']], command=self.load_selected_client_from_combo)
        self.client_search_name_combo.grid(row=1, column=1, padx=(5, 0), pady=5, sticky="ew")

        # 구분선
        separator = ttk.Separator(form_frame, orient='horizontal')
        separator.grid(row=1, column=0, columnspan=2, sticky='ew', pady=10)

        # 거래처 유형 필드 추가
        ctk.CTkLabel(form_frame, text=self.texts['client_type']).grid(row=3, column=0, padx=10, pady=5, sticky="w")
        self.client_type_combobox = ctk.CTkComboBox(form_frame, values=self.texts['client_type_values'], width=200)
        self.client_type_combobox.grid(row=3, column=1, padx=10, pady=5)

        labels = self.texts['client_labels']
        self.client_entries = {}
        for i, (key, label_text) in enumerate(labels.items()):
            label = ctk.CTkLabel(form_frame, text=label_text)
            label.grid(row=i+4, column=0, padx=10, pady=5, sticky="w")
            entry = ctk.CTkEntry(form_frame, width=200)
            entry.grid(row=i+4, column=1, padx=10, pady=5)
            self.client_entries[key] = entry

        self.is_active_var = ctk.StringVar(value="on")
        ctk.CTkCheckBox(form_frame, text=self.texts['is_active'], variable=self.is_active_var, onvalue="on", offvalue="off").grid(row=len(labels)+4, column=1, padx=10, pady=10, sticky="e")
        
        current_row = len(labels) + 5
        self.client_history_button = ctk.CTkButton(form_frame, text=self.texts['view_selected_history'], command=self.show_selected_client_history, state="disabled")
        self.client_history_button.grid(row=current_row, column=1, padx=10, pady=10, sticky="e")

        button_frame = ctk.CTkFrame(form_frame, fg_color="transparent")
        button_frame.grid(row=len(labels)+5, column=0, columnspan=2, pady=10)
        
        self.client_save_button = ctk.CTkButton(button_frame, text=self.texts['save'], command=self.save_client)
        self.client_save_button.pack(side="left", padx=5)
        self.client_new_button = ctk.CTkButton(button_frame, text=self.texts['new'], command=self.clear_client_form)
        self.client_new_button.pack(side="left", padx=5)
        self.client_delete_button = ctk.CTkButton(button_frame, text=self.texts['delete'], command=self.delete_client, fg_color="#D32F2F", hover_color="#B71C1C")
        self.client_delete_button.pack(side="left", padx=5)

        list_frame = ctk.CTkFrame(tab_frame)
        list_frame.grid(row=0, column=1, padx=10, pady=10, sticky="nsew")
        list_frame.grid_rowconfigure(1, weight=1)
        list_frame.grid_columnconfigure(0, weight=1)

        client_list_header_frame = ctk.CTkFrame(list_frame, fg_color="transparent")
        client_list_header_frame.grid(row=0, column=0, pady=10, sticky="ew")
        client_list_header_frame.grid_columnconfigure(2, weight=1) # 오른쪽 정렬을 위한 빈 공간

        ctk.CTkLabel(client_list_header_frame, text=self.texts['client_list'], font=ctk.CTkFont(size=14, weight="bold")).grid(row=0, column=0, sticky="w")
        ctk.CTkButton(client_list_header_frame, text=self.texts['view_all_history'], command=self.show_all_client_history).grid(row=0, column=1, padx=(20, 0), sticky="w")

        # pack 대신 grid를 사용하여 오른쪽 정렬
        client_excel_frame = ctk.CTkFrame(client_list_header_frame, fg_color="transparent")
        client_excel_frame.grid(row=0, column=3, sticky="e")
        ctk.CTkButton(client_excel_frame, text=self.texts['export_data'], command=self.export_client_data).pack(side="left", padx=5)
        self.client_import_button = ctk.CTkButton(client_excel_frame, text=self.texts['import_data'], command=self.import_client_data)
        self.client_import_button.pack(side="left", padx=5)

        if not self.current_user.is_admin:
            self.client_save_button.configure(state="disabled")
            self.client_new_button.configure(state="disabled")
            self.client_delete_button.configure(state="disabled")
            self.client_import_button.configure(state="disabled")

        tree_columns = self.texts['client_tree_columns']
        client_column_ids = [k for k in tree_columns if k != 'id']
        self.client_tree = ttk.Treeview(list_frame, columns=client_column_ids, show="headings", selectmode="browse")
        self.client_tree.heading("type", text=tree_columns['type']); self.client_tree.column("type", width=80, anchor="center") # noqa
        self.client_tree.heading("code", text=tree_columns['code']); self.client_tree.column("code", width=120) # noqa
        self.client_tree.heading("name", text=tree_columns['name']); self.client_tree.column("name", width=150) # noqa
        self.client_tree.heading("ceo", text=tree_columns['ceo']); self.client_tree.column("ceo", width=100) # noqa
        self.client_tree.heading("manager", text=tree_columns['manager']); self.client_tree.column("manager", width=100) # noqa
        self.client_tree.heading("contact", text=tree_columns['contact']); self.client_tree.column("contact", width=120) # noqa
        self.client_tree.heading("fax", text=tree_columns['fax']); self.client_tree.column("fax", width=120) # noqa
        self.client_tree.heading("email", text=tree_columns['email']); self.client_tree.column("email", width=150) # noqa
        self.client_tree.heading("zip", text=tree_columns['zip']); self.client_tree.column("zip", width=80, anchor="center") # noqa
        self.client_tree.heading("address", text=tree_columns['address']); self.client_tree.column("address", width=250) # noqa
        self.client_tree.heading("active", text=tree_columns['active']); self.client_tree.column("active", width=80, anchor="center") # noqa
        self.client_tree.grid(row=1, column=0, sticky="nsew")
        
        client_scrollbar = ttk.Scrollbar(list_frame, orient="vertical", command=self.client_tree.yview)
        self.client_tree.configure(yscrollcommand=client_scrollbar.set)
        client_scrollbar.grid(row=1, column=1, sticky="ns")

        # 가로 스크롤바 추가
        client_h_scrollbar = ttk.Scrollbar(list_frame, orient="horizontal", command=self.client_tree.xview)
        self.client_tree.configure(xscrollcommand=client_h_scrollbar.set)
        client_h_scrollbar.grid(row=2, column=0, sticky="ew")

        self.client_tree.bind("<<TreeviewSelect>>", self.on_client_tree_select)
        self.load_clients()

    def export_user_data(self): # 이 함수는 그대로 둡니다.
        session = db_manager.get_session()
        users = session.query(User).all()
        session.close()

        if not users:
            messagebox.showinfo("정보", "내보낼 사용자 데이터가 없습니다.")
            return

        headers = ["사용자 ID", "직책", "연락처", "우편번호", "주소", "관리자여부", "생성일"]
        data_rows = [
            (
                user.username,
                user.position,
                user.contact,
                user.zip_code,
                user.address,
                user.is_admin,
                user.created_at.strftime("%Y-%m-%d %H:%M:%S") if user.created_at else ""
            ) for user in users
        ]
        excel_handler.export_data_to_excel(headers, data_rows, "사용자_데이터.xlsx")

    def import_user_data(self):
        data = excel_handler.import_data()
        if not data: return

        def get_val(row, kor_key, eng_key):
            return row.get(kor_key, row.get(eng_key))

        session = db_manager.get_session()
        try:
            for row in data:
                username = get_val(row, "사용자 ID", "username")
                password = get_val(row, "비밀번호", "password")
                if not username or not password: continue

                user = session.query(User).filter_by(username=username).first()
                if not user:
                    user = User(username=username)
                    session.add(user)
                
                hashed_password = bcrypt.hashpw(str(password).encode('utf-8'), bcrypt.gensalt())
                user.password = hashed_password.decode('utf-8')
                user.position = get_val(row, "직책", "position")
                user.contact = get_val(row, "연락처", "contact")
                user.zip_code = get_val(row, "우편번호", "zip_code")
                user.address = get_val(row, "주소", "address")
                is_admin_val = get_val(row, "관리자여부(True/False)", "is_admin(True/False)")
                user.is_admin = str(is_admin_val).upper() == "TRUE"

            session.commit()
            messagebox.showinfo("성공", f"{len(data)}개의 사용자 정보가 처리되었습니다.")
        except Exception as e:
            session.rollback()
            messagebox.showerror("데이터베이스 오류", f"가져오기 중 오류 발생: {e}")
        finally:
            session.close()
            self.load_users()

    def export_client_data(self):
        session = db_manager.get_session()
        clients = session.query(Client).all()
        session.close()

        if not clients:
            messagebox.showinfo("정보", "내보낼 거래처 데이터가 없습니다.")
            return

        headers = ["거래처 유형", "거래처코드(사업자번호)", "거래처명", "대표자명", "담당자명", "연락처", "팩스", "이메일", "우편번호", "주소", "사용여부(Y/N)"]
        data_rows = [
            (
                client.client_type or "기타",
                client.business_number,
                client.name,
                getattr(client, 'ceo_name', ''),
                client.manager_name,
                client.phone,
                getattr(client, 'fax', ''),
                client.email,
                getattr(client, 'zip_code', ''),
                client.address,
                "Y" if client.is_active else "N"
            ) for client in clients
        ]
        excel_handler.export_data_to_excel(headers, data_rows, "거래처_데이터.xlsx")

    def import_client_data(self):
        data = excel_handler.import_data()
        if not data: return

        def get_val(row, kor_key, eng_key):
            return row.get(kor_key, row.get(eng_key))

        session = db_manager.get_session()
        try:
            for row in data:
                biz_num = get_val(row, "거래처코드(사업자번호)", "business_number")
                if not biz_num: continue
                
                client = session.query(Client).filter_by(business_number=str(biz_num)).first()
                if not client:
                    client = Client(business_number=str(biz_num))
                    session.add(client)

                client.client_type = get_val(row, "거래처 유형", "client_type") or "기타" # noqa
                client.name = get_val(row, "거래처명", "name")
                setattr(client, 'ceo_name', get_val(row, "대표자명", "ceo_name"))
                client.manager_name = get_val(row, "담당자명", "manager_name")
                client.phone = get_val(row, "연락처", "phone")
                setattr(client, 'fax', get_val(row, "팩스", "fax"))
                client.email = get_val(row, "이메일", "email") # noqa
                setattr(client, 'zip_code', get_val(row, "우편번호", "zip_code"))
                client.address = get_val(row, "주소", "address")
                is_active_val = get_val(row, "사용여부(Y/N)", "is_active(Y/N)") or "Y"
                client.is_active = str(is_active_val).upper() == "Y"

            session.commit()
            messagebox.showinfo("성공", f"{len(data)}개의 거래처 정보가 처리되었습니다.")
        except Exception as e:
            session.rollback()
            messagebox.showerror("데이터베이스 오류", f"가져오기 중 오류 발생: {e}")
        finally:
            session.close()
            self.load_clients()

    def load_users(self):
        for item in self.user_tree.get_children(): self.user_tree.delete(item)
        session = db_manager.get_session()
        users = session.query(User).all()
        session.close()
        for i, user in enumerate(users):
            admin_status = "Admin" if user.is_admin else "General"
            tag = 'oddrow' if i % 2 == 0 else 'evenrow'
            self.user_tree.insert("", "end", iid=user.id, tags=(tag,), values=( # iid에 user.id 할당
                user.username,
                user.manager_code or "",
                user.position or "",
                user.contact or "",
                admin_status
            ))

    def on_user_tree_select(self, event):
        selected_item = self.user_tree.selection()
        if not selected_item: return
        
        user_id = selected_item[0]

        session = db_manager.get_session()
        user = session.query(User).filter_by(id=user_id).first()
        session.close()

        if user:
            for key, entry in self.user_entries.items():
                entry.delete(0, "end")

            self.user_entries["username"].insert(0, user.username or "")
            self.user_entries["username"].configure(state="disabled") # ID는 수정 불가
            self.user_entries["manager_code"].insert(0, user.manager_code or "")
            self.user_entries["position"].insert(0, user.position or "")
            self.user_entries["contact"].insert(0, user.contact or "")
            self.user_entries["zip_code"].insert(0, user.zip_code or "")
            self.user_entries["address"].insert(0, user.address or "")
            self.is_admin_var.set("on" if user.is_admin else "off")
            self._selected_user_id = user.id
            self.user_history_button.configure(state="normal")

    def save_user(self):
        username = self.user_entries["username"].get()
        password = self.user_entries["password"].get()
        if not username:
            messagebox.showwarning("입력 오류", "사용자 ID는 필수 항목입니다.")
            return

        log_entries = []
        log_action = ""
        session = db_manager.get_session()
        try:
            if hasattr(self, '_selected_user_id') and self._selected_user_id:
                user = session.query(User).filter_by(id=self._selected_user_id).first()
                if not user:
                    raise Exception("선택된 사용자를 찾을 수 없습니다.")
            else:
                # 신규 사용자
                if not password:
                    messagebox.showwarning("입력 오류", "새 사용자는 비밀번호를 반드시 입력해야 합니다.")
                    return
                existing_user = session.query(User).filter_by(username=username).first()
                if existing_user:
                    messagebox.showerror("저장 오류", "이미 존재하는 사용자 ID입니다.")
                    return
                user = User(username=username)
                session.add(user)

            # --- 변경 사항 로깅 ---
            new_values = {
                "manager_code": self.user_entries["manager_code"].get(),
                "position": self.user_entries["position"].get(),
                "contact": self.user_entries["contact"].get(),
                "zip_code": self.user_entries["zip_code"].get(),
                "address": self.user_entries["address"].get(),
                "관리자 권한": self.is_admin_var.get() == "on"
            }

            if not user.id: # 신규 생성
                log_action = "신규 생성"
                log_entries.append(f"사용자 ID: '{username}'")
                for field, value in new_values.items():
                    log_entries.append(f"{self.get_user_label_by_key(field)}: '{value}'")
                if password:
                    log_entries.append("초기 비밀번호 설정됨")
            else: # 수정
                log_action = "정보 수정"
                def log_change(field_name, old_val, new_val):
                    if old_val != new_val:
                        log_entries.append(f"{self.get_user_label_by_key(field_name)}: '{old_val}' -> '{new_val}'")
                
                log_change("manager_code", user.manager_code or "", new_values["manager_code"])
                log_change("position", user.position or "", new_values["position"])
                log_change("contact", user.contact or "", new_values["contact"])
                log_change("zip_code", user.zip_code or "", new_values["zip_code"])
                log_change("address", user.address or "", new_values["address"])
                log_change("관리자 권한", user.is_admin, new_values["관리자 권한"])
                if password:
                    log_entries.append("비밀번호가 변경되었습니다.")

            # --- 데이터베이스 업데이트 ---
            if password:
                hashed_password = bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt())
                user.password = hashed_password.decode('utf-8')
            
            user.manager_code = new_values["manager_code"]
            user.position = new_values["position"]
            user.contact = new_values["contact"]
            user.zip_code = new_values["zip_code"]
            user.address = new_values["address"]
            user.is_admin = new_values["관리자 권한"]
            
            if log_entries:
                timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                log_header = f"[{timestamp}] by {self.current_user.username} - {log_action}"
                log_message = f"{log_header}\n- " + "\n- ".join(log_entries)
                
                user.change_log = (user.change_log + "\n\n" if user.change_log else "") + log_message

            session.commit()
            messagebox.showinfo("성공", "사용자 정보가 저장되었습니다.")
        except Exception as e:
            session.rollback()
            messagebox.showerror("데이터베이스 오류", f"저장 중 오류 발생: {e}")
        finally:
            session.close()
            self.clear_user_form()
            self.load_users()

    def delete_user(self):
        if not hasattr(self, '_selected_user_id') or not self._selected_user_id:
            messagebox.showwarning("선택 오류", "삭제할 사용자를 목록에서 선택하세요.")
            return
        
        if self.user_entries["username"].get() == 'admin': # username은 수정 불가 상태이므로 안전
            messagebox.showerror("삭제 불가", "기본 관리자 계정(admin)은 삭제할 수 없습니다.")
            return

        if not messagebox.askyesno("삭제 확인", "정말로 선택한 사용자를 삭제하시겠습니까?"):
            return

        session = db_manager.get_session()
        try:
            user_to_delete = session.query(User).filter_by(id=self._selected_user_id).first()
            if user_to_delete:
                session.delete(user_to_delete)
                session.commit()
                messagebox.showinfo("성공", "사용자가 삭제되었습니다.")
        except Exception as e:
            session.rollback()
            messagebox.showerror("데이터베이스 오류", f"삭제 중 오류가 발생했습니다: {e}")
        finally:
            session.close()
            self.clear_user_form()
            self.load_users()

    def clear_user_form(self):
        self._selected_user_id = None
        for entry in self.user_entries.values():
            # username 필드만 state를 변경
            if entry is self.user_entries["username"]:
                entry.configure(state="normal")
            entry.delete(0, "end")
        self.is_admin_var.set("off")
        self.user_history_button.configure(state="disabled")
        if self.user_tree.selection():
            self.user_tree.selection_remove(self.user_tree.selection()[0])

    def get_user_label_by_key(self, key):
        """user_entries의 키(영문)로 레이블(한글)을 찾습니다."""
        user_labels = {"username": "사용자 ID", "password": "비밀번호", "manager_code": "담당번호", "position": "직책", "contact": "연락처", "zip_code": "우편번호", "address": "주소"}
        # 역 매핑을 생성하거나 직접 찾기
        reverse_map = {v: k for k, v in user_labels.items()}
        return reverse_map.get(key, key)

    def update_client_name_combo(self, selected_type: str):
        """선택된 유형에 따라 거래처명 콤보박스를 업데이트합니다."""
        self.client_search_name_combo.set("- 업체 선택 -")
        if selected_type == "- 유형 선택 -":
            self.client_search_name_combo.configure(values=["- 업체 선택 -"])
            return

        session = db_manager.get_session()
        try:
            clients = session.query(Client).filter_by(client_type=selected_type, is_active=True).order_by(Client.name).all()
            client_names = [client.name for client in clients]
            self.filtered_client_map = {client.name: client.id for client in clients}

            if not client_names:
                self.client_search_name_combo.configure(values=["- 해당 업체 없음 -"])
            else:
                self.client_search_name_combo.configure(values=["- 업체 선택 -"] + client_names)
        except Exception as e:
            print(f"거래처명 콤보박스 업데이트 중 오류: {e}")
        finally:
            session.close()

    def load_selected_client_from_combo(self, selected_name: str):
        """콤보박스에서 선택된 거래처 정보를 폼에 로드합니다."""
        if selected_name in ["- 업체 선택 -", "- 해당 업체 없음 -"]:
            self.clear_client_form()
            return

        client_id = self.filtered_client_map.get(selected_name)
        if not client_id:
            return

        # Treeview에서 해당 항목을 찾아 선택 이벤트를 발생시킴
        for item in self.client_tree.get_children():
            if item == str(client_id):
                self.client_tree.selection_set(item)
                self.client_tree.focus(item)
                return

    def load_clients(self):
        for item in self.client_tree.get_children(): self.client_tree.delete(item)
        session = db_manager.get_session()
        clients = session.query(Client).all()
        session.close()
        for i, client in enumerate(clients):
            active_status = "Y" if client.is_active else "N"
            tag = 'oddrow' if i % 2 == 0 else 'evenrow'
            self.client_tree.insert("", "end", iid=client.id, tags=(tag,), values=( # iid에 client.id 할당
                client.client_type, 
                client.business_number,
                client.name,
                getattr(client, 'ceo_name', ''),
                client.manager_name, 
                client.phone, 
                getattr(client, 'fax', ''), 
                client.email,
                getattr(client, 'zip_code', ''),
                client.address,
                active_status
            ))

    def on_client_tree_select(self, event):
        selected_item = self.client_tree.selection()
        if not selected_item: return
        
        client_id = selected_item[0]

        session = db_manager.get_session()
        client = session.query(Client).filter_by(id=client_id).first()
        session.close()

        if client:
            def set_entry_value(entry_key, value):
                entry = self.client_entries[entry_key]
                entry.delete(0, "end")
                entry.insert(0, value or "")

            self.client_type_combobox.set(client.client_type or "기타")
            set_entry_value("거래처코드(사업자번호)", client.business_number)
            set_entry_value("거래처명", client.name)
            set_entry_value("대표자명", getattr(client, 'ceo_name', ""))
            set_entry_value("담당자명", client.manager_name)
            set_entry_value("연락처", client.phone)
            set_entry_value("팩스", getattr(client, 'fax', ""))
            set_entry_value("이메일", client.email)
            set_entry_value("우편번호", getattr(client, 'zip_code', ""))
            set_entry_value("주소", client.address)

            self.is_active_var.set("on" if client.is_active else "off")
            self._selected_client_id = client.id 
            self.client_history_button.configure(state="normal")
    
    def save_client(self):
        code = self.client_entries["거래처코드(사업자번호)"].get()
        name = self.client_entries["거래처명"].get()
        if not code or not name:
            messagebox.showwarning("입력 오류", "거래처코드와 거래처명은 필수 항목입니다.")
            return

        log_entries = []
        log_action = ""
        session = db_manager.get_session()
        try:
            if hasattr(self, '_selected_client_id') and self._selected_client_id:
                client_to_update = session.query(Client).filter_by(id=self._selected_client_id).first()
            else:
                client_to_update = None

            if client_to_update:
                client = client_to_update
            else:
                existing_client = session.query(Client).filter_by(business_number=code).first()
                if existing_client:
                    messagebox.showerror("저장 오류", "이미 존재하는 거래처코드입니다.")
                    return
                client = Client()
                session.add(client)
            
            # --- 변경 사항 로깅 ---
            new_values = {
                "거래처 유형": self.client_type_combobox.get(),
                "거래처코드": code,
                "거래처명": name,
                "대표자명": self.client_entries["대표자명"].get(),
                "담당자명": self.client_entries["담당자명"].get(),
                "연락처": self.client_entries["연락처"].get(),
                "팩스": self.client_entries["팩스"].get(),
                "이메일": self.client_entries["이메일"].get(),
                "우편번호": self.client_entries["우편번호"].get(),
                "주소": self.client_entries["주소"].get(),
                "사용 여부": self.is_active_var.get() == "on"
            }

            if not client.id: # 신규 생성
                log_action = "신규 생성"
                for field, value in new_values.items():
                    log_entries.append(f"{field}: '{value}'")
            else: # 수정
                log_action = "정보 수정"
                def log_change(field_name, old_val, new_val):
                    if old_val != new_val:
                        log_entries.append(f"{field_name}: '{old_val}' -> '{new_val}'")
                
                log_change("거래처 유형", client.client_type or "", new_values["거래처 유형"])
                log_change("거래처코드", client.business_number or "", new_values["거래처코드"])
                log_change("거래처명", client.name or "", new_values["거래처명"])
                log_change("대표자명", client.ceo_name or "", new_values["대표자명"])
                log_change("담당자명", client.manager_name or "", new_values["담당자명"])
                log_change("연락처", client.phone or "", new_values["연락처"])
                log_change("팩스", client.fax or "", new_values["팩스"])
                log_change("이메일", client.email or "", new_values["이메일"])
                log_change("우편번호", client.zip_code or "", new_values["우편번호"])
                log_change("주소", client.address or "", new_values["주소"])
                log_change("사용 여부", client.is_active, new_values["사용 여부"])

            client.client_type = new_values["거래처 유형"]
            client.business_number = code
            client.name = name
            client.ceo_name = new_values["대표자명"]
            client.manager_name = new_values["담당자명"]
            client.phone = new_values["연락처"]
            client.fax = new_values["팩스"]
            client.email = new_values["이메일"]
            client.zip_code = new_values["우편번호"]
            client.address = new_values["주소"]
            client.is_active = new_values["사용 여부"]
            
            if log_entries:
                timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                log_header = f"[{timestamp}] by {self.current_user.username} - {log_action}"
                log_message = f"{log_header}\n- " + "\n- ".join(log_entries)
                client.change_log = (client.change_log + "\n\n" if client.change_log else "") + log_message

            session.commit()
            messagebox.showinfo("성공", "거래처 정보가 성공적으로 저장되었습니다.")
        
        except Exception as e:
            session.rollback()
            messagebox.showerror("데이터베이스 오류", f"저장 중 오류가 발생했습니다: {e}")
        finally:
            session.close()
            self.clear_client_form()
            self.load_clients()

            # 저장 후 검색 콤보박스도 최신 상태로 업데이트
            current_type = self.client_search_type_combo.get()
            if current_type != "- 유형 선택 -":
                self.update_client_name_combo(current_type)

    def delete_client(self):
        if not hasattr(self, '_selected_client_id') or not self._selected_client_id:
            messagebox.showwarning("선택 오류", "삭제할 거래처를 목록에서 선택하세요.")
            return

        if not messagebox.askyesno("삭제 확인", "정말로 선택한 거래처를 삭제하시겠습니까?"):
            return

        session = db_manager.get_session()
        try:
            client_to_delete = session.query(Client).filter_by(id=self._selected_client_id).first()
            if client_to_delete:
                session.delete(client_to_delete)
                session.commit()
                messagebox.showinfo("성공", "거래처가 삭제되었습니다.")
        except Exception as e:
            session.rollback()
            messagebox.showerror("데이터베이스 오류", f"삭제 중 오류가 발생했습니다: {e}")
        finally:
            session.close()
            self.clear_client_form()
            self.load_clients()

            # 삭제 후 검색 콤보박스도 최신 상태로 업데이트
            current_type = self.client_search_type_combo.get()
            if current_type != "- 유형 선택 -":
                self.update_client_name_combo(current_type)

    def clear_client_form(self):
        # 검색 콤보박스 초기화
        self.client_search_type_combo.set("- 유형 선택 -")
        self.client_search_name_combo.configure(values=["- 업체 선택 -"])
        self.client_search_name_combo.set("- 업체 선택 -")

        # 폼 필드 초기화
        for entry in self.client_entries.values():
            entry.delete(0, "end")
        self.client_type_combobox.set("") # 폼 내부 유형 콤보박스 초기화
        self.client_history_button.configure(state="disabled")
        self.is_active_var.set("on")

        # 선택 상태 초기화
        self._selected_client_id = None
        if self.client_tree.selection():
            self.client_tree.selection_remove(self.client_tree.selection()[0])

    # --- 이력 조회 메서드들 ---
    def show_selected_user_history(self):
        if not hasattr(self, '_selected_user_id') or not self._selected_user_id:
            messagebox.showwarning("오류", "사용자를 먼저 선택해주세요.", parent=self)
            return
        session = db_manager.get_session()
        user = session.query(User).filter_by(id=self._selected_user_id).first()
        session.close()
        if user:
            HistoryPopup(self, f"'{user.username}' 변경 이력", [user], item_name_key='username')

    def show_all_user_history(self):
        session = db_manager.get_session()
        all_users = session.query(User).all()
        session.close()
        if not all_users:
            messagebox.showinfo("정보", "조회할 사용자가 없습니다.", parent=self)
            return
        HistoryPopup(self, "전체 사용자 변경 이력", all_users, item_name_key='username')

    def show_selected_client_history(self):
        if not hasattr(self, '_selected_client_id') or not self._selected_client_id:
            messagebox.showwarning("오류", "거래처를 먼저 선택해주세요.", parent=self)
            return
        session = db_manager.get_session()
        client = session.query(Client).filter_by(id=self._selected_client_id).first()
        session.close()
        if client:
            HistoryPopup(self, f"'{client.name}' 변경 이력", [client], item_name_key='name', item_code_key='business_number')

    def show_all_client_history(self):
        session = db_manager.get_session()
        all_clients = session.query(Client).all()
        session.close()
        if not all_clients:
            messagebox.showinfo("정보", "조회할 거래처가 없습니다.", parent=self)
            return
        HistoryPopup(self, "전체 거래처 변경 이력", all_clients, item_name_key='name', item_code_key='business_number')
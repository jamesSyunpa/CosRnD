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
import traceback  # 상단에 추가

class DataManagementFrame(ctk.CTkFrame):
    def __init__(self, master, current_user, app, language="korean"):
        super().__init__(master)
        self.current_user = current_user
        self.app = app
        self.language = language
        self.client_search_timer = None

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

        # --- 변경: 탭 텍스트를 texts에서 가져오되 기본값 지정 ---
        tab_texts = {
            "ingredient": self.texts.get("ingredient_mgt", "성분 관리"),
            "client": self.texts.get("client_mgt", "거래처 관리"),
            "user": self.texts.get("user_mgt", "회원 관리")
        }

        self.tab_map = {
            tab_texts["ingredient"]: "data/ingredient_mgt",
            tab_texts["client"]: "data/client_mgt",
            tab_texts["user"]: "data/user_mgt"
        }

        # Reverse mapping: stable/internal keys -> displayed tab label
        # e.g. 'ingredient_mgt' or 'data/ingredient_mgt' -> tab_texts['ingredient']
        self.tab_key_map = {}
        try:
            self.tab_key_map['ingredient_mgt'] = tab_texts['ingredient']
            self.tab_key_map['client_mgt'] = tab_texts['client']
            self.tab_key_map['user_mgt'] = tab_texts['user']
            self.tab_key_map['data/ingredient_mgt'] = tab_texts['ingredient']
            self.tab_key_map['data/client_mgt'] = tab_texts['client']
            self.tab_key_map['data/user_mgt'] = tab_texts['user']
        except Exception:
            # Defensive: if texts missing, leave map possibly incomplete
            pass

        # 성분 관리 탭 - RD, RQ, RQD, MSAD만 접근 가능
        if self.current_user.can_view_material_data():
            self.tab_view.add(tab_texts["ingredient"])
            self.setup_material_management_tab(self.tab_view.tab(tab_texts["ingredient"]))

        # 거래처 관리 탭 - QC, RD, RQ, RQD, MSAD 모두 접근 가능 (검색/참고)
        if self.current_user.can_view_client_data():
            self.tab_view.add(tab_texts["client"])
            self.setup_client_management_tab(self.tab_view.tab(tab_texts["client"]))

        # 회원 관리 탭 - RQD, MSAD만 접근 가능
        if self.current_user.can_manage_all_data():
            self.tab_view.add(tab_texts["user"])
            self.setup_user_management_tab(self.tab_view.tab(tab_texts["user"]))
            
            # 사용자 관리 탭 초기화 후 권한 옵션 업데이트
            self.update_role_options()

    def show_help(self):
        """데이터 관리 도움말을 표시합니다."""
        title = self.texts['data_mgt_help_title']
        message = self.texts['data_mgt_help_message']
        HelpPopup(self, title, message)

    def on_tab_change(self):
        """탭이 변경될 때마다 활동을 기록합니다."""
        selected_tab = self.tab_view.get()
        static_key = self.tab_map.get(selected_tab)
        if static_key:
            self.app.record_action(static_key)

    def switch_to_tab(self, tab_name):
        """외부에서 특정 탭으로 전환하는 메서드"""
        try:
            self.tab_view.set(tab_name)
        except Exception as e:
            # Try resolving tab_name as an internal key (e.g., 'ingredient_mgt' or 'data/ingredient_mgt')
            resolved_label = None
            if tab_name in self.tab_key_map:
                resolved_label = self.tab_key_map[tab_name]
            else:
                # If full action provided like 'data/ingredient_mgt', try the part after '/'
                if '/' in tab_name:
                    _, maybe_key = tab_name.split('/', 1)
                    resolved_label = self.tab_key_map.get(maybe_key)

            if resolved_label:
                try:
                    self.tab_view.set(resolved_label)
                    return
                except Exception as e2:
                    print(f"데이터 관리 탭 '{tab_name}'을(를) '{resolved_label}'로 변환했으나 전환 실패: {e2}")
                    return

            print(f"데이터 관리 탭 '{tab_name}'으로 전환 실패: {e}")

    def refresh_data(self):
        """데이터 관리 프레임의 모든 탭에 있는 데이터를 새로고침합니다."""
        print("데이터 관리 프레임 새로고침...")

        # 1. 회원 관리 탭 새로고침 (존재하는 경우)
        if hasattr(self, 'load_users'):
            try:
                print("  - 사용자 목록 새로고침...")
                self.load_users()
                self.clear_user_form()
            except Exception as e:
                print(f"[오류] 사용자 목록 새로고침 실패: {e}")

        # 2. 거래처 관리 탭 새로고침 (존재하는 경우)
        if hasattr(self, 'load_clients'):
            try:
                print("  - 거래처 목록 새로고침...")
                self.load_clients()
                self.clear_client_form()
            except Exception as e:
                print(f"[오류] 거래처 목록 새로고침 실패: {e}")

        # 3. 성분 관리 탭(MaterialManagementFrame) 새로고침
        try:
            # 탭 이름은 self.texts에서 가져옴
            ingredient_tab_name = self.texts.get("ingredient", "성분 관리")
            material_tab_frame = self.tab_view.tab(ingredient_tab_name)
            
            # material_tab_frame의 자식 위젯(MaterialManagementFrame)을 찾아서 refresh_data 호출
            for child in material_tab_frame.winfo_children():
                if hasattr(child, 'refresh_data'):
                    print("  - 성분 관리 탭 새로고침...")
                    child.refresh_data()
                    break # MaterialManagementFrame은 하나만 있다고 가정
        except Exception as e:
            # 탭이 아직 생성되지 않았거나 다른 오류 발생 시
            print(f"[오류] 성분 관리 탭 새로고침 실패: {e}")

    def focus_material_by_id(self, material_id: int):
        """외부에서 원료 ID를 받아 성분 관리 탭을 열고 해당 항목을 선택합니다."""
        try:
            # 성분 관리 탭으로 전환
            self.switch_to_tab('data/ingredient_mgt')
            # 탭의 자식 중 MaterialManagementFrame을 찾아 위임
            ingredient_tab_label = self.tab_key_map.get('data/ingredient_mgt') or self.tab_key_map.get('ingredient_mgt')
            tab_widget = None
            try:
                if ingredient_tab_label:
                    tab_widget = self.tab_view.tab(ingredient_tab_label)
            except Exception:
                # 라벨 해석 실패 시 현재 탭 컨테이너에서 탐색
                tab_widget = self.tab_view
            if not tab_widget:
                tab_widget = self.tab_view
            for child in tab_widget.winfo_children():
                if hasattr(child, 'focus_material_by_id'):
                    ok = child.focus_material_by_id(material_id)
                    if ok:
                        return True
            return False
        except Exception as e:
            print(f"[경고] 성분 관리 탭 포커스 실패: {e}")
            return False

    # ==============================================================================
    # 아래는 settings_management.py에서 이동 및 통합된 UI 설정 메서드들입니다.
    # ==============================================================================

    def setup_material_management_tab(self, tab_frame):
        """성분 관리 탭의 UI를 설정합니다."""
        tab_frame.grid_columnconfigure(0, weight=1)
        tab_frame.grid_rowconfigure(0, weight=1)
        material_frame = MaterialManagementFrame(tab_frame, self.current_user, self.app)
        material_frame.grid(row=0, column=0, sticky="nsew") # MaterialManagementFrame needs language

    def setup_user_management_tab(self, tab_frame):
        tab_frame.grid_columnconfigure(0, weight=0, minsize=500) # 좌측 폼 (고정 너비)
        tab_frame.grid_columnconfigure(1, weight=1) # 우측 리스트 (가변 너비)
        tab_frame.grid_rowconfigure(0, weight=1)

        # 좌측 폼 영역에 세로 스크롤이 가능하도록 ScrollableFrame 적용
        user_scrollable = ctk.CTkScrollableFrame(tab_frame, fg_color="transparent")
        user_scrollable.grid(row=0, column=0, padx=10, pady=10, sticky="nsew")
        user_scrollable.grid_columnconfigure(0, weight=1)

        user_form_frame = ctk.CTkFrame(user_scrollable)
        user_form_frame.grid(row=0, column=0, padx=10, pady=10, sticky="nsew")
        user_form_frame.grid_columnconfigure(1, weight=1) # 입력 필드가 너비를 채우도록 설정
        
        form_label = ctk.CTkLabel(user_form_frame, text=self.texts['user_info'], font=ctk.CTkFont(size=14, weight="bold"))
        form_label.grid(row=0, column=0, columnspan=2, pady=(10, 20))

        user_labels = self.texts['user_labels']
        self.user_entries = {}
        current_row = 1
        for key, label_text in user_labels.items():
            ctk.CTkLabel(user_form_frame, text=label_text).grid(row=current_row, column=0, padx=10, pady=5, sticky="w")
            entry = ctk.CTkEntry(user_form_frame) # 고정 너비 제거
            entry.grid(row=current_row, column=1, padx=10, pady=5, sticky="ew")
            if key == "password":
                entry.configure(show="*")
                ctk.CTkLabel(user_form_frame, text=self.texts['password_helper'], font=ctk.CTkFont(size=10)).grid(row=current_row+1, column=1, padx=10, sticky="w")
                current_row += 1
            self.user_entries[key] = entry
            current_row += 1
        
        # 권한 선택 추가
        ctk.CTkLabel(user_form_frame, text="권한").grid(row=current_row, column=0, padx=10, pady=5, sticky="w")
        
        # 관리자 존재 여부에 따라 권한 옵션 결정
        self.has_admin = db_manager.has_admin_users()
        
        if self.has_admin:
            # 이미 관리자가 있으면 MSAD 제외
            self.role_options = {
                "QC - 품질관리원": "QC",
                "RD - 연구원": "RD",
                "RQ - 연구/품질 통합관리자": "RQ",
                "RQD - 연구/품질/데이터 관리자": "RQD"
            }
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
            # 관리자가 없으면 모든 권한 허용
            self.role_options = {
                "QC - 품질관리원": "QC",
                "RD - 연구원": "RD",
                "RQ - 연구/품질 통합관리자": "RQ",
                "RQD - 연구/품질/데이터 관리자": "RQD",
                "MSAD - 모든 관리자": "MSAD"
            }
            role_info_text = (
                "QC: 품질 서류 관리 (원료목록보고, COA, MSDS, 제품표준서, 제조관리기록서)\n"
                "     + 거래처 관리 (검색/참고만)\n"
                "RD: 연구 서류 관리 (처방, 견적, 전성분, 물성치/SPEC, 기능성보고/참고자료)\n"
                "     + 성분/거래처 관리 (검색/참고만)\n"
                "RQ: 연구/품질 통합관리 (RD + QC 모든 기능)\n"
                "RQD: RQ 기능 + 모든 데이터 수정/삭제 권한\n"
                "MSAD: 마스터 관리자 (모든 기능 + 데이터 삭제 전 백업 권한)"
            )
        
        self.user_role_combo = ctk.CTkOptionMenu(
            user_form_frame,
            values=list(self.role_options.keys()),
            width=250
        )
        self.user_role_combo.set("RD - 연구원")
        self.user_role_combo.grid(row=current_row, column=1, padx=10, pady=5, sticky="w")
        current_row += 1
        
        # 권한 설명
        role_info = ctk.CTkLabel(
            user_form_frame, 
            text=role_info_text,
            font=ctk.CTkFont(size=9),
            text_color="gray",
            justify="left"
        )
        role_info.grid(row=current_row, column=1, padx=10, sticky="w")
        current_row += 1
        
        # 마스터 권한 불변 안내 라벨 (필요 시 표시)
        self.master_guard_label = ctk.CTkLabel(
            user_form_frame,
            text="마스터 계정의 권한은 변경할 수 없습니다.",
            font=ctk.CTkFont(size=10, weight="bold"),
            text_color="#D32F2F",
            justify="left"
        )
        self.master_guard_label.grid(row=current_row, column=1, padx=10, sticky="w")
        # 기본은 숨김
        self.master_guard_label.grid_remove()
        current_row += 1
        
        # 관리자 체크박스는 숨기고 권한 콤보박스로만 관리
        self.is_admin_var = ctk.StringVar(value="off")
        # is_admin_check는 표시하지 않음 (권한이 자동으로 결정됨)
        
        # 권한 정보 안내
        ctk.CTkLabel(
            user_form_frame, 
            text="※ 권한은 위의 드롭다운에서 선택하신 항목으로 자동 설정됩니다.",
            font=ctk.CTkFont(size=9),
            text_color="#1f538d"
        ).grid(row=current_row, column=1, padx=10, pady=5, sticky="w")
        current_row += 1

        # 사용자 변경 이력 미리보기
        ctk.CTkLabel(user_form_frame, text="변경 이력", font=ctk.CTkFont(size=12, weight="bold")).grid(row=current_row, column=0, padx=10, pady=(5, 0), sticky="nw")
        self.user_history_preview = ctk.CTkTextbox(user_form_frame, height=120, wrap="word")
        self.user_history_preview.grid(row=current_row, column=1, padx=10, pady=(5, 0), sticky="nsew")
        self.user_history_preview.configure(state="disabled")
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

        # 사용자 관리는 MSAD(마스터 관리자)만 가능
        if not self.current_user.is_master_admin():
            self.user_save_button.configure(state="disabled")
            self.user_new_button.configure(state="disabled")
            self.user_delete_button.configure(state="disabled")
            self.user_role_combo.configure(state="disabled")
            user_role = getattr(self.current_user, 'role', 'Unknown')
            print(f"사용자 관리 - 조회 전용 모드 (권한: {user_role}) - 사용자 관리는 MSAD 권한 필요")
        else:
            # MSAD일 때만 가져오기 버튼 표시
            self.user_import_button.pack(side="left", padx=5)

        user_tree_columns = self.texts['user_tree_columns']
        user_column_ids = [k for k in user_tree_columns if k != 'id']
        self.user_tree = ttk.Treeview(user_list_frame, columns=user_column_ids, show="headings", selectmode="browse")
        self.user_tree.heading("username", text=user_tree_columns['username']); self.user_tree.column("username", width=120) # noqa
        self.user_tree.heading("real_name", text=user_tree_columns['real_name']); self.user_tree.column("real_name", width=100) # noqa
        self.user_tree.heading("manager_code", text=user_tree_columns['manager_code']); self.user_tree.column("manager_code", width=100, anchor="center") # noqa
        self.user_tree.heading("position", text=user_tree_columns['position']); self.user_tree.column("position", width=120) # noqa
        self.user_tree.heading("contact", text=user_tree_columns['contact']); self.user_tree.column("contact", width=120) # noqa
        self.user_tree.heading("role", text=user_tree_columns['role']); self.user_tree.column("role", width=80, anchor="center") # noqa
        self.user_tree.heading("is_admin", text=user_tree_columns['is_admin']); self.user_tree.column("is_admin", width=100, anchor="center") # noqa
        self.user_tree.grid(row=1, column=0, sticky="nsew")

        user_scrollbar = ttk.Scrollbar(user_list_frame, orient="vertical", command=self.user_tree.yview)
        self.user_tree.configure(yscrollcommand=user_scrollbar.set)
        user_scrollbar.grid(row=1, column=1, sticky="ns")

        self.user_tree.bind("<<TreeviewSelect>>", self.on_user_tree_select)
        self.load_users()

    def setup_client_management_tab(self, tab_frame):
        tab_frame.grid_columnconfigure(0, weight=0, minsize=500) # 좌측 폼 (고정 너비)
        tab_frame.grid_columnconfigure(1, weight=1) # 우측 리스트 (가변 너비)
        tab_frame.grid_rowconfigure(0, weight=1)

        # 스크롤 가능한 프레임을 생성하여 모든 위젯을 담습니다.
        scrollable_frame = ctk.CTkScrollableFrame(tab_frame, fg_color="transparent")
        scrollable_frame.grid(row=0, column=0, padx=(10, 0), pady=10, sticky="nsew")

        form_frame = ctk.CTkFrame(scrollable_frame)
        form_frame.grid(row=0, column=0, padx=10, pady=10, sticky="ew")
        form_frame.grid_columnconfigure(1, weight=1) # 입력 필드가 너비를 채우도록 설정
        
        form_label = ctk.CTkLabel(form_frame, text=self.texts['client_info'], font=ctk.CTkFont(size=14, weight="bold"))
        form_label.grid(row=2, column=0, columnspan=2, pady=(20, 10))

        # 거래처 유형 필드 추가
        ctk.CTkLabel(form_frame, text=self.texts['client_type']).grid(row=3, column=0, padx=10, pady=5, sticky="w")
        self.client_type_combobox = ctk.CTkComboBox(form_frame, values=self.texts['client_type_values']) # noqa
        self.client_type_combobox.grid(row=3, column=1, padx=10, pady=5, sticky="ew")

        labels = self.texts['client_labels']
        self.client_entries = {}
        for i, (key, label_text) in enumerate(labels.items()):
            label = ctk.CTkLabel(form_frame, text=label_text)
            label.grid(row=i+4, column=0, padx=10, pady=5, sticky="w")
            entry = ctk.CTkEntry(form_frame) # 고정 너비 제거
            entry.grid(row=i+4, column=1, padx=10, pady=5, sticky="ew")
            self.client_entries[key] = entry

        self.is_active_var = ctk.StringVar(value="on")
        ctk.CTkCheckBox(form_frame, text=self.texts['is_active'], variable=self.is_active_var, onvalue="on", offvalue="off").grid(row=len(labels)+4, column=1, padx=10, pady=10, sticky="e") # noqa
        
        current_row = len(labels) + 5
        # 거래처 변경 이력 미리보기
        ctk.CTkLabel(form_frame, text="변경 이력", font=ctk.CTkFont(size=12, weight="bold")).grid(row=current_row, column=0, padx=10, pady=(5, 0), sticky="nw")
        self.client_history_preview = ctk.CTkTextbox(form_frame, height=120, wrap="word")
        self.client_history_preview.grid(row=current_row, column=1, padx=10, pady=(5, 0), sticky="nsew")
        self.client_history_preview.configure(state="disabled")
        current_row += 1
        self.client_history_button = ctk.CTkButton(form_frame, text=self.texts['view_selected_history'], command=self.show_selected_client_history, state="disabled")
        self.client_history_button.grid(row=current_row, column=1, padx=10, pady=10, sticky="e")

        # 다음 행으로 이동 후 버튼 프레임 배치 (이전 위젯과 겹치지 않도록)
        current_row += 1
        button_frame = ctk.CTkFrame(form_frame, fg_color="transparent")
        button_frame.grid(row=current_row, column=0, columnspan=2, pady=10, sticky="w")
        
        self.client_save_button = ctk.CTkButton(button_frame, text=self.texts['save'], command=self.save_client)
        self.client_save_button.pack(side="left", padx=5)
        self.client_new_button = ctk.CTkButton(button_frame, text=self.texts['new'], command=self.clear_client_form)
        self.client_new_button.pack(side="left", padx=5)
        self.client_delete_button = ctk.CTkButton(button_frame, text=self.texts['delete'], command=self.delete_client, fg_color="#D32F2F", hover_color="#B71C1C")
        self.client_delete_button.pack(side="left", padx=5)

        # --- 우측: 거래처 목록 ---
        list_frame = ctk.CTkFrame(tab_frame)
        list_frame.grid(row=0, column=1, padx=10, pady=10, sticky="nsew")
        list_frame.grid_rowconfigure(1, weight=1)
        list_frame.grid_columnconfigure(0, weight=1)
        
        # --- 거래처 목록 헤더 (검색 및 버튼 포함) ---
        client_list_header_frame = ctk.CTkFrame(list_frame, fg_color="transparent")
        client_list_header_frame.grid(row=0, column=0, columnspan=2, pady=(10, 5), padx=10, sticky="ew")
        client_list_header_frame.grid_columnconfigure(1, weight=1) # 가변 공간

        ctk.CTkLabel(client_list_header_frame, text=self.texts['client_list'], font=ctk.CTkFont(size=14, weight="bold")).grid(row=0, column=0, sticky="w")
        # 거래처 전체 이력 조회 버튼 추가
        ctk.CTkButton(client_list_header_frame, text=self.texts['view_all_history'], command=self.show_all_client_history).grid(row=0, column=1, padx=(20, 0), sticky="w")
        
        # --- 우측 컨트롤 (검색, 초기화, 엑셀 버튼) ---
        right_header_frame = ctk.CTkFrame(client_list_header_frame, fg_color="transparent")
        right_header_frame.grid(row=0, column=2, sticky="e")

        ctk.CTkLabel(right_header_frame, text=f"{self.texts['search']}:").pack(side="left", padx=(0, 5))
        self.client_search_entry = ctk.CTkEntry(right_header_frame, width=150)
        self.client_search_entry.pack(side="left", padx=5)
        self.client_search_entry.bind("<KeyRelease>", self.on_client_search)
        ctk.CTkButton(right_header_frame, text=self.texts['reset'], width=60, command=self.reset_client_search).pack(side="left", padx=5)

        # 엑셀 버튼 프레임
        client_excel_frame = ctk.CTkFrame(right_header_frame, fg_color="transparent")
        client_excel_frame.pack(side="left", padx=(10, 0))

        ctk.CTkButton(client_excel_frame, text=self.texts['export_data'], command=self.export_client_data).pack(side="left", padx=5)
        self.client_import_button = ctk.CTkButton(client_excel_frame, text=self.texts['import_data'], command=self.import_client_data)

        # 거래처 데이터 편집 권한 확인 (RQD, MSAD만 가능)
        if not self.current_user.can_edit_client_data():
            self.client_save_button.configure(state="disabled")
            self.client_new_button.configure(state="disabled")
            self.client_delete_button.configure(state="disabled")
            # QC, RD는 검색/참고만 가능한 메시지 추가
            user_role = getattr(self.current_user, 'role', 'Unknown')
            print(f"거래처 관리 - 검색/참고 전용 모드 (권한: {user_role})")
        else:
            # RQD, MSAD일 때만 가져오기 버튼 표시
            self.client_import_button.pack(side="left", padx=5)

        tree_columns = self.texts['client_tree_columns']
        client_column_ids = [k for k in tree_columns if k != 'id']
        # 구분 컬럼을 포함한 전체 컬럼 리스트 생성
        all_columns = ['division'] + client_column_ids
        self.client_tree = ttk.Treeview(list_frame, columns=all_columns, show="headings", selectmode="browse")
        
        # 구분 컬럼 설정 (맨 앞에 추가)
        self.client_tree.heading("division", text="구분")
        self.client_tree.column("division", width=60, anchor="center")
        
        # 기존 컬럼들 설정
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

        headers = ["사용자 ID", "실명", "직책", "연락처", "우편번호", "주소", "관리자여부", "생성일"]
        data_rows = [
            (
                user.username,
                user.real_name or "",
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
                is_existing = bool(user)
                if not user:
                    user = User(username=username)
                    session.add(user)
                
                hashed_password = bcrypt.hashpw(str(password).encode('utf-8'), bcrypt.gensalt())
                user.password = hashed_password.decode('utf-8')
                user.real_name = get_val(row, "실명", "real_name")
                user.position = get_val(row, "직책", "position")
                user.contact = get_val(row, "연락처", "contact")
                user.zip_code = get_val(row, "우편번호", "zip_code")
                user.address = get_val(row, "주소", "address")
                is_admin_val = get_val(row, "관리자여부(True/False)", "is_admin(True/False)")
                # 기존 마스터 계정(admin 또는 MSAD)은 관리자여부 변경 금지
                if is_existing and ((user.username == 'admin') or (getattr(user, 'role', '') == 'MSAD')):
                    user.is_admin = True
                else:
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
                if not biz_num: 
                    continue

                # 기존/신규 판별 및 이전 스냅샷 확보
                prev = None
                client = session.query(Client).filter_by(business_number=str(biz_num)).first()
                is_new = False
                if not client:
                    client = Client(business_number=str(biz_num))
                    session.add(client)
                    is_new = True
                else:
                    prev = {
                        'name': client.name or '',
                        'client_type': client.client_type or '',
                        'ceo_name': getattr(client, 'ceo_name', '') or '',
                        'manager_name': client.manager_name or '',
                        'phone': client.phone or '',
                        'fax': getattr(client, 'fax', '') or '',
                        'email': client.email or '',
                        'zip_code': getattr(client, 'zip_code', '') or '',
                        'address': client.address or '',
                        'is_active': bool(client.is_active),
                    }

                # 값 업데이트
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

                # 변경 이력 기록: (엑셀 가져오기) 표시로 일괄 업로드 집계 가능하게
                try:
                    timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                    user_name = getattr(self.current_user, 'username', 'unknown')
                    action = "신규 생성" if is_new else "정보 수정"
                    header = f"[{timestamp}] by {user_name} - {action} (엑셀 가져오기)"
                    lines = []
                    def add_nonempty(label, val):
                        if val is None:
                            return
                        if isinstance(val, str) and not val.strip():
                            return
                        lines.append(f"{label}: '{val}'")
                    def add_change(label, old, new):
                        if (old or "") != (new or ""):
                            lines.append(f"{label}: '{old}' -> '{new}'")

                    if is_new:
                        add_nonempty("거래처명", client.name)
                        add_nonempty("사업자번호", client.business_number)
                        add_nonempty("유형", client.client_type)
                        add_nonempty("연락처", client.phone)
                        add_nonempty("이메일", client.email)
                        add_nonempty("주소", client.address)
                        add_nonempty("사용여부", "Y" if client.is_active else "N")
                    else:
                        add_change("거래처명", prev['name'], client.name or '')
                        add_change("유형", prev['client_type'], client.client_type or '')
                        add_change("대표자명", prev['ceo_name'], getattr(client, 'ceo_name', '') or '')
                        add_change("담당자명", prev['manager_name'], client.manager_name or '')
                        add_change("연락처", prev['phone'], client.phone or '')
                        add_change("팩스", prev['fax'], getattr(client, 'fax', '') or '')
                        add_change("이메일", prev['email'], client.email or '')
                        add_change("우편번호", prev['zip_code'], getattr(client, 'zip_code', '') or '')
                        add_change("주소", prev['address'], client.address or '')
                        add_change("사용여부", 'Y' if prev['is_active'] else 'N', 'Y' if client.is_active else 'N')

                    if lines:
                        body = "- " + "\n- ".join(lines)
                        client.change_log = (client.change_log + "\n\n" if getattr(client, 'change_log', None) else "") + f"{header}\n{body}"
                except Exception:
                    # 로깅 실패는 전체 처리를 막지 않음
                    pass

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
            # 권한 표시 개선
            user_role = getattr(user, 'role', 'RD')
            role_display = {
                'QC': 'QC',
                'RD': 'RD', 
                'RQ': 'RQ',
                'RQD': 'RQD',
                'MSAD': 'MSAD'
            }.get(user_role, user_role)
            
            admin_status = "Yes" if user.is_admin else "No"
            tag = 'oddrow' if i % 2 == 0 else 'evenrow'
            self.user_tree.insert("", "end", iid=user.id, tags=(tag,), values=( # iid에 user.id 할당
                user.username,
                user.real_name or "",
                user.manager_code or "",
                user.position or "",
                user.contact or "",
                role_display,
                admin_status
            ))
    
    def update_role_options(self):
        """관리자 존재 여부에 따라 권한 옵션을 업데이트합니다."""
        self.has_admin = db_manager.has_admin_users()
        
        if self.has_admin:
            # 이미 관리자가 있으면 MSAD 제외
            new_role_options = {
                "QC - 품질관리원": "QC",
                "RD - 연구원": "RD", 
                "RQ - 연구/품질 통합관리자": "RQ",
                "RQD - 연구/품질/데이터 관리자": "RQD"
            }
        else:
            # 관리자가 없으면 모든 권한 허용
            new_role_options = {
                "QC - 품질관리원": "QC",
                "RD - 연구원": "RD",
                "RQ - 연구/품질 통합관리자": "RQ", 
                "RQD - 연구/품질/데이터 관리자": "RQD",
                "MSAD - 마스터 관리자": "MSAD"
            }
        
        # 권한 옵션이 변경된 경우에만 업데이트
        if new_role_options != self.role_options:
            self.role_options = new_role_options
            current_value = self.user_role_combo.get()
            
            # 콤보박스 값 업데이트
            self.user_role_combo.configure(values=list(self.role_options.keys()))
            
            # 현재 선택된 값이 새 옵션에 없으면 기본값으로 설정
            if current_value not in self.role_options.keys():
                self.user_role_combo.set("RD - 연구원")

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
            self.user_entries["real_name"].insert(0, user.real_name or "")
            self.user_entries["manager_code"].insert(0, user.manager_code or "")
            self.user_entries["position"].insert(0, user.position or "")
            self.user_entries["contact"].insert(0, user.contact or "")
            self.user_entries["zip_code"].insert(0, user.zip_code or "")
            self.user_entries["address"].insert(0, user.address or "")
            
            # 권한 설정 (role 필드 기준으로 설정)
            user_role = getattr(user, 'role', 'RD')  # 기본값 RD
            role_display = None
            for display, code in self.role_options.items():
                if code == user_role:
                    role_display = display
                    break
            if role_display:
                self.user_role_combo.set(role_display)
            else:
                self.user_role_combo.set("RD - 연구원")  # 기본값
            
            # is_admin은 자동으로 설정 (표시용)
            self.is_admin_var.set("on" if user_role == "MSAD" else "off")
            
            self._selected_user_id = user.id
            self.user_history_button.configure(state="normal")

            # 변경 이력 미리보기 업데이트
            try:
                self.user_history_preview.configure(state="normal")
                self.user_history_preview.delete("1.0", "end")
                if getattr(user, 'change_log', None):
                    self.user_history_preview.insert("1.0", str(user.change_log))
                else:
                    self.user_history_preview.insert("1.0", "저장된 변경 이력이 없습니다.")
                self.user_history_preview.configure(state="disabled")
            except Exception:
                pass

            # 마스터 계정 선택 시 권한/삭제 비활성화 및 안내 표시
            is_master_target = (user.username == 'admin') or (getattr(user, 'role', '') == 'MSAD')
            if is_master_target:
                try:
                    self.user_role_combo.configure(state="disabled")
                except Exception:
                    pass
                if hasattr(self, 'master_guard_label'):
                    self.master_guard_label.grid()
                # 삭제 버튼 비활성화
                try:
                    self.user_delete_button.configure(state="disabled")
                except Exception:
                    pass
            else:
                # 마스터가 아닌 경우 안내 숨김 및 상태 복구 (현재 사용자가 관리 권한 보유 시)
                if hasattr(self, 'master_guard_label'):
                    self.master_guard_label.grid_remove()
                if self.current_user.is_master_admin():
                    try:
                        self.user_role_combo.configure(state="normal")
                        self.user_delete_button.configure(state="normal")
                    except Exception:
                        pass

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
            is_edit = hasattr(self, '_selected_user_id') and self._selected_user_id
            if is_edit:
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
            # 권한 가져오기
            role_display = self.user_role_combo.get()
            role_code = self.role_options.get(role_display, "RD")
            
            # 편집 대상이 마스터 계정이면 권한 변경 금지
            if is_edit:
                is_master_target = (user.username == 'admin') or (getattr(user, 'role', '') == 'MSAD')
                if is_master_target:
                    role_code = 'MSAD'
            
            # 신규 사용자에 대한 MSAD 권한 제한 검증
            if not (hasattr(self, '_selected_user_id') and self._selected_user_id):  # 신규 사용자인 경우
                if role_code == "MSAD" and self.has_admin:  # 이미 관리자가 있는데 MSAD 권한을 시도하는 경우
                    messagebox.showerror("권한 오류", 
                        "이미 관리자 계정이 존재합니다.\n"
                        "보안상 추가 관리자 계정 생성은 제한됩니다.\n"
                        "다른 권한을 선택해주세요.")
                    return
            
            # is_admin은 권한 코드에 따라 자동 설정 (정책: RQD도 관리자 취급)
            is_admin_value = (role_code in ("MSAD", "RQD"))
            self.is_admin_var.set("on" if is_admin_value else "off")
            
            new_values = {
                "real_name": self.user_entries["real_name"].get(),
                "manager_code": self.user_entries["manager_code"].get(),
                "position": self.user_entries["position"].get(),
                "contact": self.user_entries["contact"].get(),
                "zip_code": self.user_entries["zip_code"].get(),
                "address": self.user_entries["address"].get(),
                "관리자 권한": is_admin_value,
                "role": role_code
            }

            # manager_code 중복 검사 (빈 문자열은 제외)
            manager_code = new_values["manager_code"].strip()
            if manager_code:  # 값이 있을 때만 중복 검사
                existing_manager = session.query(User).filter(
                    User.manager_code == manager_code,
                    User.id != user.id  # 자기 자신은 제외
                ).first()
                if existing_manager:
                    messagebox.showerror("저장 오류", 
                        f"담당번호 '{manager_code}'는 이미 사용 중입니다.\n"
                        f"사용자: {existing_manager.username} ({existing_manager.real_name or '이름 없음'})")
                    return

            if not user.id: # 신규 생성
                log_action = "신규 생성"
                # 화이트리스트 필드만 기록 + 빈값은 생략
                def add_nonempty(label, value):
                    if value is None:
                        return
                    if isinstance(value, str) and not value.strip():
                        return
                    log_entries.append(f"{label}: '{value}'")

                log_entries.append(f"사용자 ID: '{username}'")
                add_nonempty("실명", new_values.get("real_name"))
                add_nonempty("담당번호", new_values.get("manager_code"))
                add_nonempty("직책", new_values.get("position"))
                add_nonempty("연락처", new_values.get("contact"))
                add_nonempty("권한", new_values.get("role"))
                if password:
                    log_entries.append("초기 비밀번호 설정됨")
            else: # 수정
                log_action = "정보 수정"
                def log_change(field_name, old_val, new_val):
                    if old_val != new_val:
                        log_entries.append(f"{self.get_user_label_by_key(field_name)}: '{old_val}' -> '{new_val}'")
                # 화이트리스트 변경만 기록 (실명, 담당번호, 직책, 연락처, 권한, 관리자 권한)
                log_change("real_name", user.real_name or "", new_values["real_name"])
                log_change("manager_code", user.manager_code or "", new_values["manager_code"])
                log_change("position", user.position or "", new_values["position"])
                log_change("contact", user.contact or "", new_values["contact"])
                log_change("관리자 권한", user.is_admin, new_values["관리자 권한"])
                
                # 권한 변경 로깅
                old_role = getattr(user, 'role', 'RD')
                if old_role != new_values["role"]:
                    log_entries.append(f"권한: '{old_role}' -> '{new_values['role']}'")
                
                if password:
                    log_entries.append("비밀번호가 변경되었습니다.")

            # --- 데이터베이스 업데이트 ---
            if password:
                hashed_password = bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt())
                user.password = hashed_password.decode('utf-8')
            
            user.real_name = new_values["real_name"]
            # manager_code가 빈 문자열이면 None으로 설정 (UNIQUE 제약조건 회피)
            user.manager_code = new_values["manager_code"] if new_values["manager_code"].strip() else None
            user.position = new_values["position"]
            user.contact = new_values["contact"]
            user.zip_code = new_values["zip_code"]
            user.address = new_values["address"]
            # 마스터 계정은 권한/관리자값 불변 유지
            if is_edit and ((user.username == 'admin') or (getattr(user, 'role', '') == 'MSAD')):
                user.is_admin = True
                user.role = 'MSAD'
            else:
                user.is_admin = new_values["관리자 권한"]
                user.role = new_values["role"]  # 권한 저장
            
            if log_entries:
                timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                log_header = f"[{timestamp}] by {self.current_user.username} - {log_action}"
                log_message = f"{log_header}\n- " + "\n- ".join(log_entries)
                
                user.change_log = (user.change_log + "\n\n" if user.change_log else "") + log_message

            session.commit()
            messagebox.showinfo("성공", "사용자 정보가 저장되었습니다.")
        except Exception as e:
            session.rollback()
            import traceback
            error_details = traceback.format_exc()
            print(f"사용자 저장 에러: {e}")
            print(f"상세 에러: {error_details}")
            messagebox.showerror("데이터베이스 오류", f"저장 중 오류 발생: {e}\n\n상세 정보는 콘솔을 확인하세요.")
        finally:
            session.close()
            self.clear_user_form()
            self.load_users()
            # 권한 옵션 업데이트 (관리자 생성/삭제 시 권한 선택지 변경)
            self.update_role_options()

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
            # 마스터 권한 사용자는 삭제 금지 (admin 또는 MSAD)
            if user_to_delete and ((user_to_delete.username == 'admin') or (getattr(user_to_delete, 'role', '') == 'MSAD')):
                messagebox.showerror("삭제 불가", "마스터 관리자(MSAD)는 삭제할 수 없습니다.")
                return
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
            # 권한 옵션 업데이트 (관리자 삭제 시 권한 선택지 변경 가능)
            self.update_role_options()

    def clear_user_form(self):
        self._selected_user_id = None
        for entry in self.user_entries.values():
            # username 필드만 state를 변경
            if entry is self.user_entries["username"]:
                entry.configure(state="normal")
            entry.delete(0, "end")
        self.is_admin_var.set("off")
        self.user_role_combo.set("RD - 연구원")  # 권한 초기화
        self.user_history_button.configure(state="disabled")
        # 폼 초기화 시 마스터 안내 숨김 및 상태 복구
        if hasattr(self, 'master_guard_label'):
            self.master_guard_label.grid_remove()
        if self.current_user.is_master_admin():
            try:
                self.user_role_combo.configure(state="normal")
                self.user_delete_button.configure(state="normal")
            except Exception:
                pass
        if self.user_tree.selection():
            self.user_tree.selection_remove(self.user_tree.selection()[0])
        # 이력 미리보기 초기화
        try:
            self.user_history_preview.configure(state="normal")
            self.user_history_preview.delete("1.0", "end")
            self.user_history_preview.insert("1.0", "")
            self.user_history_preview.configure(state="disabled")
        except Exception:
            pass

    def get_user_label_by_key(self, key):
        """user_entries의 키(영문)로 레이블(한글)을 찾습니다."""
        user_labels = {"username": "사용자 ID", "real_name": "실명", "password": "비밀번호", "manager_code": "담당번호", "position": "직책", "contact": "연락처", "zip_code": "우편번호", "address": "주소"}
        # 역 매핑을 생성하거나 직접 찾기
        reverse_map = {v: k for k, v in user_labels.items()}
        return reverse_map.get(key, key)

    def on_client_search(self, event=None):
        """거래처 검색창 입력 시 디바운싱을 적용하여 검색을 실행합니다."""
        if self.client_search_timer:
            self.after_cancel(self.client_search_timer)
        self.client_search_timer = self.after(500, self.load_clients)

    def reset_client_search(self):
        """거래처 검색창을 초기화하고 전체 목록을 다시 불러옵니다."""
        self.client_search_entry.delete(0, "end")
        self.load_clients()

    def load_clients(self):
        search_term = self.client_search_entry.get().strip()
        for item in self.client_tree.get_children(): self.client_tree.delete(item)
        clients = db_manager.search_clients(search_term)

        for i, client in enumerate(clients):
            active_status = "Y" if client.is_active else "N"
            tag = 'oddrow' if i % 2 == 0 else 'evenrow'
            self.client_tree.insert("", "end", iid=client.id, tags=(tag,), values=(
                str(i + 1),  # 구분 번호
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
            set_entry_value("code", client.business_number)
            set_entry_value("name", client.name)
            set_entry_value("ceo", getattr(client, 'ceo_name', ""))
            set_entry_value("manager", client.manager_name)
            set_entry_value("contact", client.phone)
            set_entry_value("fax", getattr(client, 'fax', ""))
            set_entry_value("email", client.email)
            set_entry_value("zip", getattr(client, 'zip_code', ""))
            set_entry_value("address", client.address)

            self.is_active_var.set("on" if client.is_active else "off")
            self._selected_client_id = client.id 
            self.client_history_button.configure(state="normal")
            # 변경 이력 미리보기 업데이트
            try:
                self.client_history_preview.configure(state="normal")
                self.client_history_preview.delete("1.0", "end")
                if getattr(client, 'change_log', None):
                    self.client_history_preview.insert("1.0", str(client.change_log))
                else:
                    self.client_history_preview.insert("1.0", "저장된 변경 이력이 없습니다.")
                self.client_history_preview.configure(state="disabled")
            except Exception:
                pass
    
    def save_client(self):
        code = self.client_entries["code"].get()
        name = self.client_entries["name"].get()
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
                "대표자명": self.client_entries["ceo"].get(),
                "담당자명": self.client_entries["manager"].get(),
                "연락처": self.client_entries["contact"].get(),
                "팩스": self.client_entries["fax"].get(),
                "이메일": self.client_entries["email"].get(),
                "우편번호": self.client_entries["zip"].get(),
                "주소": self.client_entries["address"].get(),
                "사용 여부": self.is_active_var.get() == "on"
            }

            if not client.id: # 신규 생성
                log_action = "신규 생성"
                # 화이트리스트 + 비어있지 않은 값만 기록
                def add_nonempty(label, value):
                    if value is None:
                        return
                    if isinstance(value, str) and not value.strip():
                        return
                    log_entries.append(f"{label}: '{value}'")

                add_nonempty("거래처 유형", new_values["거래처 유형"])
                add_nonempty("거래처코드", new_values["거래처코드"])
                add_nonempty("거래처명", new_values["거래처명"])
                add_nonempty("담당자명", new_values["담당자명"])
                add_nonempty("연락처", new_values["연락처"])
                add_nonempty("이메일", new_values["이메일"])
                # 사용 여부는 기본값(on)이 많아 노이즈가 될 수 있어 신규 생성 시에는 생략
            else: # 수정
                log_action = "정보 수정"
                def log_change(field_name, old_val, new_val):
                    if old_val != new_val:
                        log_entries.append(f"{field_name}: '{old_val}' -> '{new_val}'")
                # 화이트리스트 필드만 변경 기록
                log_change("거래처 유형", client.client_type or "", new_values["거래처 유형"])
                log_change("거래처코드", client.business_number or "", new_values["거래처코드"])
                log_change("거래처명", client.name or "", new_values["거래처명"])
                log_change("담당자명", client.manager_name or "", new_values["담당자명"])
                log_change("연락처", client.phone or "", new_values["연락처"])
                log_change("이메일", client.email or "", new_values["이메일"])
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

    def clear_client_form(self):
        # 검색창 초기화
        self.client_search_entry.delete(0, "end")

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
        # 이력 미리보기 초기화
        try:
            self.client_history_preview.configure(state="normal")
            self.client_history_preview.delete("1.0", "end")
            self.client_history_preview.insert("1.0", "")
            self.client_history_preview.configure(state="disabled")
        except Exception:
            pass

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

    def load_client_data(self):
        """거래처 데이터를 로드하고 표시합니다."""
        try:
            # 수정: 명확한 컬럼 지정과 중복 방지를 위한 쿼리
            query = """
                SELECT 
                    c.id,
                    c.name,
                    c.contact_person,
                    c.phone,
                    c.email,
                    c.address,
                    c.website,
                    c.notes,
                    GROUP_CONCAT(DISTINCT i.name) as ingredients
                FROM clients c
                LEFT JOIN ingredients i ON i.supplier_id = c.id
                GROUP BY 
                    c.id, c.name, c.contact_person, 
                    c.phone, c.email, c.address, 
                    c.website, c.notes
                ORDER BY c.name
            """
            
            results = db_manager.execute_query(query)
            
            # 결과 검증
            if results:
                print(f"거래처 데이터 로드: {len(results)}개 항목")
                for idx, row in enumerate(results[:3]):  # 처음 3개 항목만 로깅
                    print(f"Sample {idx+1}: {row}")
            
            self.client_tree.delete(*self.client_tree.get_children())
            
            for row in results:
                values = [
                    row['name'],
                    row['contact_person'] or "",
                    row['phone'] or "",
                    row['email'] or "",
                    row['address'] or "",
                    row['website'] or "",
                    row['notes'] or "",
                    row['ingredients'] or ""
                ]
                self.client_tree.insert('', 'end', text=str(row['id']), values=values)
                
            # 결과 검증을 위한 카운트 출력
            print(f"Treeview에 추가된 항목 수: {len(self.client_tree.get_children())}")
        except Exception as e:
            print(f"거래처 데이터 로드 실패: {e}\n{traceback.format_exc()}")
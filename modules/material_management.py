# modules/material_management.py
import customtkinter as ctk
import tkinter as tk
from tkinter import ttk, messagebox
from database.db_manager import db_manager
from database.models import Material, Ingredient, Client
import modules.excel_handler as excel_handler
from datetime import datetime
from sqlalchemy.orm import joinedload
from modules.history_popup import HistoryPopup
from utils.autocomplete import AutocompleteEntry

class MaterialManagementFrame(ctk.CTkFrame):
    def __init__(self, master, user, app=None):
        super().__init__(master)
        
        self.current_user = user
        self.app = app
        self.db_manager = db_manager
        self.temp_ingredients = []
        self._selected_material_id = None
        self._selected_ingredient_id = None
        self.is_new_mode = True
        self.bulk_importing = False
        self.search_timer = None # 검색 디바운싱을 위한 타이머
        
        # 탭 뷰가 필요 없으므로, UI를 프레임에 직접 구성합니다.
        self.setup_data_management_tab(self)
        
        # 권한에 따른 UI 요소 제어
        self.setup_permission_controls()

        self.refresh_data()

    def get_client_list(self, db_manager):
        return [row[0] for row in db_manager.get_all_clients()]

    def can_edit_data(self):
        """현재 사용자가 성분 데이터를 편집할 수 있는지 확인합니다."""
        if not self.current_user:
            return False
        
        # 관리자(MSAD)만 편집 가능
        return self.current_user.can_edit_material_data()
    
    def can_view_data(self):
        """현재 사용자가 성분 데이터를 조회할 수 있는지 확인합니다."""
        if not self.current_user:
            return False
        
        # 모든 연구원(QC, RD, RQ, RQD, MSAD) 조회 가능
        return self.current_user.can_view_material_data()

    def start_new_mode(self):
        self.is_new_mode = True
        if hasattr(self, 'client_entry'):
            self.client_entry.grid_remove()
        if hasattr(self, 'client_combobox'):
            self.client_combobox.grid()
            self.client_combobox.configure(state="normal")
            self.client_combobox.set("")

    def load_material(self, material_id):
        self.is_new_mode = False
        if hasattr(self, 'client_combobox'):
            self.client_combobox.grid_remove()
        if hasattr(self, 'client_entry'):
            self.client_entry.grid()
            self.client_entry.configure(state="normal")

        session = self.db_manager.get_session()
        try:
            material = session.query(Material).get(material_id)
            if material:
                self.client_entry.delete(0, tk.END)
                self.client_entry.insert(0, material.client.name)
                self.client_entry.configure(state="readonly")
        finally:
            session.close()
            
    def refresh_data(self):
        """이 화면에 필요한 모든 데이터를 DB에서 새로 불러옵니다."""
        self.load_clients_to_combobox()
        self.load_materials()

    def setup_permission_controls(self):
        """사용자 권한에 따라 UI 요소들을 제어합니다."""
        # 권한 제어는 setup_data_management_tab에서 처리되므로 여기서는 추가 설정만
        can_edit = self.can_edit_data()
        
        if not can_edit:
            # 공급처 선택 비활성화
            if hasattr(self, 'supplier_entry'):
                self.supplier_entry.configure(state="disabled")
                
    def setup_data_management_tab(self, tab_frame):
        """원료 데이터 관리 UI를 설정합니다."""

        # ===== 탭 전체 그리드 구조 =====
        tab_frame.grid_columnconfigure(0, weight=0, minsize=500)  # 좌측 폼 (고정 너비 영역)
        tab_frame.grid_columnconfigure(1, weight=0)  # 가운데 조절바
        tab_frame.grid_columnconfigure(2, weight=1)  # 우측 리스트 (가변 너비)
        tab_frame.grid_rowconfigure(0, weight=1)

        # ===== 좌측: 원료 입력 폼 =====
        self.form_container = ctk.CTkScrollableFrame(tab_frame, label_text="원료 정보 입력")
        self.form_container.grid(row=0, column=0, padx=(0, 0), pady=0, sticky="nsew")
        self.form_container.grid_columnconfigure(0, weight=0)
        self.form_container.grid_columnconfigure(1, weight=1)  # 입력 필드 가변

        material_labels = ["코드", "원료명", "단가", "포장단위", "공급처", "제조원명", "HS CODE", "원산지", "영문원료명", "NMPA등록번호", "등록일"]
        self.material_entries = {}
        for i, text in enumerate(material_labels):
            ctk.CTkLabel(self.form_container, text=text).grid(row=i, column=0, padx=10, pady=5, sticky="w")
            if text == "공급처":
                self.supplier_entry = AutocompleteEntry(self.form_container)
                self.supplier_entry.grid(row=i, column=1, padx=10, pady=5, sticky="ew")
                self.material_entries[text] = self.supplier_entry
            else:
                entry = ctk.CTkEntry(self.form_container)
                entry.grid(row=i, column=1, padx=10, pady=5, sticky="ew")
                self.material_entries[text] = entry

        # 사용 여부 체크박스
        self.material_active_var = ctk.StringVar(value="on")
        ctk.CTkCheckBox(
            self.form_container, text="사용 여부",
            variable=self.material_active_var, onvalue="on", offvalue="off"
        ).grid(row=len(material_labels), column=1, padx=10, pady=10, sticky="e")

        # 이력 보기 버튼
        self.material_history_button = ctk.CTkButton(self.form_container, text="선택 항목 이력 보기", command=self.show_selected_material_history, state="disabled")
        self.material_history_button.grid(row=len(material_labels)+1, column=1, padx=10, pady=10, sticky="e")

        # ===== 전성분 영역 =====
        ingredient_frame = ctk.CTkFrame(self.form_container, fg_color="transparent")
        ingredient_frame.grid(row=len(material_labels)+1, column=0, columnspan=2, padx=5, pady=10, sticky="nsew")
        ingredient_frame.grid_columnconfigure(0, weight=0)
        ingredient_frame.grid_columnconfigure(1, weight=1)

        # 전성분 헤더 프레임 (레이블 + 열 선택 버튼)
        ing_header_frame = ctk.CTkFrame(ingredient_frame, fg_color="transparent")
        ing_header_frame.grid(row=0, column=0, columnspan=2, pady=5, sticky="ew")
        ing_header_frame.grid_columnconfigure(1, weight=1) # 버튼을 오른쪽으로 밀기 위한 빈 공간

        ctk.CTkLabel(ing_header_frame, text="전성분 목록", font=ctk.CTkFont(weight="bold")).pack(side="left", padx=5)
        self.ing_col_select_button = ctk.CTkButton(ing_header_frame, text="열 선택", width=80)
        self.ing_col_select_button.pack(side="right", padx=5)
        # 전성분 트리뷰 컬럼 설정
        self.ing_cols_config = {
            "id": {"text": "ID", "width": 40, "anchor": "center", "visible": False},
            "name_ko": {"text": "한글전성분", "width": 100, "anchor": "w", "visible": True},
            "name_en": {"text": "INGREDIENT", "width": 100, "anchor": "w", "visible": True},
            "cas_no": {"text": "CAS NO.", "width": 80, "anchor": "w", "visible": True},
            "ratio": {"text": "조성비(%)", "width": 60, "anchor": "e", "visible": True},
            "function": {"text": "기능", "width": 80, "anchor": "w", "visible": True},
            "ewg_grade": {"text": "EWG등급", "width": 80, "anchor": "w", "visible": True},
            "ewg_data": {"text": "EWG데이터", "width": 80, "anchor": "w", "visible": True},
            "remark": {"text": "비고", "width": 100, "anchor": "w", "visible": True}
        }

        self.ingredient_tree = ttk.Treeview(ingredient_frame, columns=list(self.ing_cols_config.keys()), show="headings", height=5)
        self._setup_treeview_columns(self.ingredient_tree, self.ing_cols_config)
        # 열 선택 메뉴 생성 및 버튼에 연결
        self._create_column_selection_menu(self.ingredient_tree, self.ing_cols_config, self.ing_col_select_button)

        self.ingredient_tree.grid(row=1, column=0, columnspan=2, padx=5, pady=(5,0), sticky="nsew")
        self.ingredient_tree.bind("<<TreeviewSelect>>", self.on_ingredient_tree_select)

        # 전성분 트리뷰 스크롤바
        ing_v_scroll = ttk.Scrollbar(ingredient_frame, orient="vertical", command=self.ingredient_tree.yview)
        self.ingredient_tree.configure(yscrollcommand=ing_v_scroll.set)
        ing_v_scroll.grid(row=1, column=2, sticky='ns', pady=(5,0))
        ing_h_scroll = ttk.Scrollbar(ingredient_frame, orient="horizontal", command=self.ingredient_tree.xview)
        self.ingredient_tree.configure(xscrollcommand=ing_h_scroll.set)
        ing_h_scroll.grid(row=2, column=0, columnspan=2, sticky='ew', padx=5)

        ing_labels = ["한글전성분", "INGREDIENT", "CAS NO.", "조성비(%)", "기능", "EWG등급", "EWG등급데이터", "비고"]
        self.ingredient_entries = {}
        for i, text in enumerate(ing_labels):
            ctk.CTkLabel(ingredient_frame, text=text).grid(row=i+3, column=0, padx=5, pady=2, sticky="w")
            entry = ctk.CTkEntry(ingredient_frame)
            entry.grid(row=i+3, column=1, padx=5, pady=2, sticky="ew")
            self.ingredient_entries[text] = entry

        ing_button_frame = ctk.CTkFrame(ingredient_frame, fg_color="transparent")
        ing_button_frame.grid(row=len(ing_labels)+3, column=1, pady=5, sticky="e")
        self.ing_add_button = ctk.CTkButton(ing_button_frame, text="추가", width=60, command=self.add_ingredient)
        self.ing_add_button.pack(side="left", padx=2)
        self.ing_update_button = ctk.CTkButton(ing_button_frame, text="수정", width=60, command=self.update_ingredient)
        self.ing_update_button.pack(side="left", padx=2)
        self.ing_remove_button = ctk.CTkButton(
            ing_button_frame, text="삭제", width=60,
            fg_color="#D32F2F", hover_color="#B71C1C", command=self.remove_ingredient
        )
        self.ing_remove_button.pack(side="left", padx=2)

        # 원료 저장 관련 버튼
        main_button_frame = ctk.CTkFrame(self.form_container, fg_color="transparent")
        main_button_frame.grid(row=len(material_labels)+4, column=0, columnspan=2, pady=10)
        self.mat_save_button = ctk.CTkButton(main_button_frame, text="원료 저장", command=self.save_material)
        self.mat_save_button.pack(side="left", padx=5)
        self.mat_new_button = ctk.CTkButton(main_button_frame, text="신규 작성", command=self.clear_material_form)
        self.mat_new_button.pack(side="left", padx=5)
        self.mat_delete_button = ctk.CTkButton(
            main_button_frame, text="원료 삭제",
            fg_color="#D32F2F", hover_color="#B71C1C", command=self.delete_material
        )
        self.mat_delete_button.pack(side="left", padx=5)

        # ===== 가운데 조절바 =====
        self.sash = ctk.CTkFrame(tab_frame, width=7, cursor="sb_h_double_arrow")
        self.sash.grid(row=0, column=1, padx=2, pady=0, sticky="ns")
        self.sash.bind("<ButtonPress-1>", self.on_sash_press)
        self.sash.bind("<B1-Motion>", self.on_sash_drag)

        # ===== 우측: 원료 목록 =====
        list_frame = ctk.CTkFrame(tab_frame)
        list_frame.grid(row=0, column=2, padx=(0, 0), pady=0, sticky="nsew")
        list_frame.grid_rowconfigure(1, weight=1)     # 세로 확장 (row 1로 변경)
        list_frame.grid_columnconfigure(0, weight=1)  # 가로 확장

        # --- 헤더 및 검색/버튼 프레임 ---
        list_header_frame = ctk.CTkFrame(list_frame, fg_color="transparent")
        list_header_frame.grid(row=0, column=0, columnspan=2, pady=(10, 5), padx=10, sticky="ew")
        list_header_frame.grid_columnconfigure(1, weight=1) # 가변 공간

        # 좌측 위젯 (레이블)
        ctk.CTkLabel(list_header_frame, text="원료 목록", font=ctk.CTkFont(size=14, weight="bold")).grid(row=0, column=0, sticky="w")

        # 우측 위젯 (버튼 및 검색창)
        right_header_frame = ctk.CTkFrame(list_header_frame, fg_color="transparent")
        right_header_frame.grid(row=0, column=2, sticky="e")

        ctk.CTkButton(right_header_frame, text="전체 이력 조회", command=self.show_all_material_history).pack(side="left", padx=(0, 10))
        ctk.CTkLabel(right_header_frame, text="검색:").pack(side="left", padx=(0, 5))
        self.material_search_entry = ctk.CTkEntry(right_header_frame, width=150)
        self.material_search_entry.pack(side="left", padx=5)
        self.material_search_entry.bind("<KeyRelease>", self.on_material_search)
        ctk.CTkButton(right_header_frame, text="초기화", width=60, command=self.reset_material_search).pack(side="left", padx=5)
        ctk.CTkButton(right_header_frame, text="데이터 내보내기", command=self.export_material_data).pack(side="left", padx=5)
        self.excel_import_button = ctk.CTkButton(right_header_frame, text="데이터 가져오기", command=self.import_material_data)

        # 데이터 편집 권한 접근 제한
        if not self.can_edit_data():
            self.material_active_var.set("off")
            user_role = getattr(self.current_user, 'role', 'Unknown')
            self.form_container.configure(label_text=f"원료 정보 조회 전용 (현재 권한: {user_role}) - 편집은 RQD/MSAD 권한 필요")
            # 데이터 수정/관리 관련 버튼 숨기기
            self.ing_add_button.pack_forget()
            self.ing_update_button.pack_forget()
            self.ing_remove_button.pack_forget()
            self.mat_save_button.pack_forget()
            self.mat_new_button.pack_forget()
            self.mat_delete_button.pack_forget()
            # 모든 입력 필드 비활성화
            for entry in self.material_entries.values():
                entry.configure(state="readonly")
            for entry in self.ingredient_entries.values():
                entry.configure(state="readonly")

        # ===== 원료 목록 트리뷰 =====        
        else: # 데이터 편집 권한이 있는 경우에만 가져오기 버튼 표시
            self.excel_import_button.pack(side="left", padx=5)

        # 트리뷰 생성
        mat_tree_cols = ("group", "id", "code", "name", "unit_price", "package_unit", "client", "manufacturer", "hs_code", "origin", "name_en", "nmpa_reg_num")
        self.material_tree = ttk.Treeview(list_frame, columns=mat_tree_cols, show="headings", selectmode="browse")

        # 컬럼 설정
        # 'id' 컬럼은 숨김 처리
        self.material_tree.heading("group", text="구분");           self.material_tree.column("group", width=50, anchor="center")
        self.material_tree.heading("id", text="ID");                self.material_tree.column("id", width=0, stretch=tk.NO) # ID 컬럼 숨기기
        self.material_tree.heading("code", text="코드");            self.material_tree.column("code", width=100, anchor="w")
        self.material_tree.heading("name", text="원료명");          self.material_tree.column("name", width=200, anchor="w")
        self.material_tree.heading("unit_price", text="단가");       self.material_tree.column("unit_price", width=80, anchor="e")
        self.material_tree.heading("package_unit", text="포장단위"); self.material_tree.column("package_unit", width=80, anchor="center")
        self.material_tree.heading("client", text="공급처");        self.material_tree.column("client", width=150, anchor="w")
        self.material_tree.heading("manufacturer", text="제조원명"); self.material_tree.column("manufacturer", width=150, anchor="w")
        self.material_tree.heading("hs_code", text="HS CODE");      self.material_tree.column("hs_code", width=100, anchor="w")
        self.material_tree.heading("origin", text="원산지");        self.material_tree.column("origin", width=100, anchor="w")
        self.material_tree.heading("name_en", text="영문원료명");    self.material_tree.column("name_en", width=200, anchor="w")
        self.material_tree.heading("nmpa_reg_num", text="NMPA등록번호"); self.material_tree.column("nmpa_reg_num", width=120, anchor="w")

        # 'id' 컬럼을 숨깁니다.
        self.material_tree.configure(displaycolumns=[col for col in mat_tree_cols if col != 'id'])

        # 배치
        self.material_tree.grid(row=1, column=0, sticky="nsew", padx=(10, 0), pady=(0, 5))

        # 스크롤바
        v_scrollbar = ttk.Scrollbar(list_frame, orient="vertical", command=self.material_tree.yview)
        self.material_tree.configure(yscrollcommand=v_scrollbar.set)
        v_scrollbar.grid(row=1, column=1, sticky="ns", pady=(0, 5))

        h_scrollbar = ttk.Scrollbar(list_frame, orient="horizontal", command=self.material_tree.xview)
        self.material_tree.configure(xscrollcommand=h_scrollbar.set)
        h_scrollbar.grid(row=2, column=0, columnspan=2, sticky="ew", padx=(10, 0), pady=(0, 10))
        
        # 선택 이벤트 바인딩
        self.material_tree.bind("<<TreeviewSelect>>", self.on_material_tree_select)

    def _create_column_selection_menu(self, treeview, columns_config, button_widget):
        """열 선택 체크박스 메뉴를 생성하고 버튼에 연결합니다."""
        column_menu = tk.Menu(button_widget, tearoff=0)
        
        for col_id, config in columns_config.items():
            # ID 숨김 열은 제외 처리
            if col_id == 'id':
                continue
            
            var = tk.BooleanVar(value=config.get("visible", True))
            column_menu.add_checkbutton(
                label=config["text"],
                variable=var,
                command=lambda tv=treeview, cfg=columns_config: self._update_visible_columns(tv, cfg)
            )
            config["variable"] = var

        button_widget.configure(command=lambda: column_menu.tk_popup(
            button_widget.winfo_rootx(), 
            button_widget.winfo_rooty() + button_widget.winfo_height()
        ))

    def on_sash_press(self, event):
        self._sash_drag_start_x = event.x_root
        self._form_start_width = self.form_container.winfo_width()

    def on_sash_drag(self, event):
        tab_frame = self.sash.master
        delta_x = event.x_root - self._sash_drag_start_x
        new_width = self._form_start_width + delta_x

        if new_width < 400: new_width = 400
        if new_width > tab_frame.winfo_width() - 400: new_width = tab_frame.winfo_width() - 400
        
        tab_frame.grid_columnconfigure(0, minsize=new_width)

    def export_material_data(self):
        session = db_manager.get_session()
        materials = session.query(Material).all()
        
        if not materials:
            messagebox.showinfo("정보", "내보낼 원료 데이터가 없습니다.")
            session.close()
            return
            
        mat_headers = ["코드", "원료명", "단가", "포장단위", "거래처", "제조원명", "HS CODE", "원산지", "영문원료명", "NMPA등록번호", "사용여부"]
        mat_rows = []
        for mat in materials:
            supplier_name = session.query(Client.name).filter_by(id=mat.supplier_id).scalar() or ""
            mat_rows.append((
                mat.code, mat.name, mat.unit_price, mat.package_unit,
                supplier_name, mat.manufacturer, mat.hs_code, mat.origin, mat.name_en, mat.nmpa_reg_num, "Y" if mat.is_active else "N"
            ))

        ing_headers = ["원료코드", "한글전성분", "INGREDIENT", "CAS NO.", "조성비(%)", "기능", "EWG등급", "EWG등급데이터", "HS CODE", "NMPA등록번호", "비고"]
        ing_rows = []
        for mat in materials:
            for ing in mat.ingredients:
                ing_rows.append((
                    mat.code, ing.name_ko, ing.name_en, ing.cas_no, ing.composition_ratio,
                    ing.function, ing.ewg_grade, ing.ewg_data, ing.hs_code, ing.nmpa_reg_num, ing.remark
                ))
        
        session.close()

        sheets_data = {
            "원료정보": {"headers": mat_headers, "data": mat_rows},
            "전성분정보": {"headers": ing_headers, "data": ing_rows}
        }
        excel_handler.export_multisheet_data_to_excel(sheets_data, "원료_데이터.xlsx")

    def import_material_data(self):
        """엑셀 파일에서 원료 및 전성분 데이터를 가져와서 데이터베이스에 저장합니다."""
        # 편집 권한 확인
        if not self.can_edit_data():
            messagebox.showwarning("권한 오류", "성분 데이터를 편집할 권한이 없습니다.\n편집은 RQD/MSAD 권한이 필요합니다.\n현재 권한으로는 검색/참고만 가능합니다.")
            return
            
        # 대량 가져오기 시작
        self.bulk_importing = True
        
        # DB 동기화 체크 임시 중단 (대량 가져오기로 인한 성능 방지)
        sync_was_running = False
        if hasattr(self.app, 'stop_db_sync_check'):
            # 현재 동기화가 실행 중인지 확인
            sync_was_running = hasattr(self.app, 'db_sync_timer') and self.app.db_sync_timer is not None
            self.app.stop_db_sync_check()
            print("[원료가져오기] DB 동기화 체크 임시 중단")
        
        try:
            imported_data = excel_handler.import_multisheet_data()
            if not imported_data:
                return
            
            materials_data = imported_data.get("원료정보") or imported_data.get("Materials")
            ingredients_data = imported_data.get("전성분정보") or imported_data.get("Ingredients")

            if materials_data is None or ingredients_data is None:
                messagebox.showerror("오류", "엑셀 파일에 '원료정보(Materials)'와 '전성분정보(Ingredients)' 시트가 모두 필요합니다.")
                return

            def get_val(row, kor_key, eng_key):
                """한글에 실패하면 영문으로 값을 가져옵니다."""
                value = row.get(kor_key, row.get(eng_key))
                return value.strip() if isinstance(value, str) else value

            session = db_manager.get_session()
            
            try:
                # 기존 클라이언트 맵 생성
                clients = session.query(Client).all()
                client_map_by_biz_num = {}
                client_map_by_name = {}
                
                for c in clients:
                    if c.business_number:
                        client_map_by_biz_num[str(c.business_number).strip()] = c.id
                    if c.name:
                        client_map_by_name[str(c.name).strip()] = c.id
                
                print(f"기존 클라이언트 맵 생성 완료:")
                print(f"  - 사업자번호 맵: {len(client_map_by_biz_num)}개")
                print(f"  - 이름 맵: {len(client_map_by_name)}개")
                
                # 처리된 재료들을 저장할 딕셔너리
                processed_materials = {}
                # 변경 이력 작성을 위한 이전 스냅샷 및 액션 기록
                prev_snapshots = {}
                actions_by_code = {}
                materials_count = 0
                ingredients_count = 0
                new_clients_count = 0
                # 이번 가져오기 과정에서 새로 생성된 거래처 목록 (집계 및 이력 기록용)
                created_clients = []  # [(Client, name, business_number)]
                
                print(f"가져올 원료 데이터: {len(materials_data)}개")
                print(f"가져올 전성분 데이터: {len(ingredients_data)}개")
                
                # 1단계: 원료 정보 처리 (개선된 거래처 처리 포함)
                for i, mat_row in enumerate(materials_data):
                    try:
                        code = get_val(mat_row, "코드", "code")
                        if not code:
                            print(f"원료 {i+1}: 코드가 없어서 건너뜀")
                            continue
                        
                        # 기존 재료 찾기 또는 새로 생성
                        material = session.query(Material).filter_by(code=code).first()
                        if not material:
                            material = Material(code=code)
                            session.add(material)
                            actions_by_code[code] = "신규 생성"
                            # 신규의 이전 스냅샷은 빈 값
                            prev_snapshots[code] = {
                                "code": code,
                                "name": "",
                                "name_en": "",
                                "unit_price": 0.0,
                                "package_unit": "",
                                "supplier_id": None,
                                "supplier_name": "",
                                "manufacturer": "",
                                "hs_code": "",
                                "origin": "",
                                "nmpa_reg_num": "",
                                "reg_date": "",
                                "is_active": True,
                                "ingredients": [],
                            }
                            print(f"새 재료 생성: {code}")
                        else:
                            actions_by_code[code] = "정보 수정"
                            # 기존값 스냅샷 (필드 + 기존 전성분)
                            try:
                                prev_snapshots[code] = {
                                    "code": material.code or "",
                                    "name": material.name or "",
                                    "name_en": material.name_en or "",
                                    "unit_price": material.unit_price if material.unit_price is not None else 0.0,
                                    "package_unit": material.package_unit or "",
                                    "supplier_id": material.supplier_id,
                                    "supplier_name": (material.supplier.name if material.supplier else ""),
                                    "manufacturer": material.manufacturer or "",
                                    "hs_code": material.hs_code or "",
                                    "origin": material.origin or "",
                                    "nmpa_reg_num": material.nmpa_reg_num or "",
                                    "reg_date": material.reg_date or "",
                                    "is_active": bool(material.is_active),
                                    "ingredients": [
                                        {
                                            "name_ko": ing.name_ko or "",
                                            "name_en": ing.name_en or "",
                                            "cas_no": ing.cas_no or "",
                                            "composition_ratio": ing.composition_ratio or 0.0,
                                            "function": ing.function or "",
                                            "ewg_grade": ing.ewg_grade or "",
                                            "ewg_data": ing.ewg_data or "",
                                            "remark": ing.remark or "",
                                        }
                                        for ing in (material.ingredients or [])
                                    ],
                                }
                            except Exception:
                                # 스냅샷 실패는 치명적이지 않음
                                prev_snapshots[code] = {
                                    "code": material.code or "",
                                    "ingredients": [],
                                }
                            print(f"기존 재료 업데이트: {code}")

                        # 재료 기본 정보 설정
                        material.name = get_val(mat_row, "원료명", "name") or ""
                        material.name_en = get_val(mat_row, "영문원료명", "name_en") or ""
                        
                        # 단가 처리
                        unit_price_val = get_val(mat_row, "단가", "unit_price")
                        try:
                            material.unit_price = float(unit_price_val) if unit_price_val else 0.0
                        except (ValueError, TypeError):
                            material.unit_price = 0.0
                        
                        material.package_unit = get_val(mat_row, "포장단위", "package_unit") or ""
                        
                        # ========== 개선된 거래처 ID 설정 ==========
                        client_id = None

                        # 1순위: '거래처사업자번호' 열이 있으면 해당 번호로 찾기
                        biz_num_val = get_val(mat_row, "거래처코드(사업자번호)", "client_business_number") # 거래처 템플릿과 키 맞춤
                        if biz_num_val:
                            biz_num_str = str(biz_num_val).strip()
                            client_id = client_map_by_biz_num.get(biz_num_str)
                            if not client_id:
                                # 해당 사업자번호의 거래처가 없으면 새로 생성
                                client_name_val = get_val(mat_row, "거래처명", "client_name") or biz_num_str
                                new_client = Client(
                                    name=str(client_name_val).strip(), 
                                    business_number=biz_num_str, 
                                    is_active=True,
                                    client_type='원료'  # 공급처이므로 타입을 '원료'로 지정
                                )
                                session.add(new_client)
                                session.flush()
                                client_id = new_client.id
                                # 새 거래처 생성 기록용으로 보관 (가져오기 일괄 업로드 집계를 위해)
                                try:
                                    created_clients.append((new_client, str(client_name_val).strip(), biz_num_str))
                                except Exception:
                                    pass
                                client_map_by_biz_num[biz_num_str] = client_id
                                # 이름 맵에도 추가하여 일관성 유지
                                client_map_by_name[str(client_name_val).strip()] = client_id
                                new_clients_count += 1
                                print(f"  새 거래처 생성 (사업자번호 기준): {client_name_val} ({biz_num_str}) -> ID {client_id}")
                            else:
                                print(f"  거래처 매칭 성공 (사업자번호): {biz_num_str} -> ID {client_id}")

                        # 2순위: '거래처사업자번호'가 없을 경우, '거래처명'으로 찾기
                        else:
                            client_name_val = get_val(mat_row, "거래처", "client_name") or get_val(mat_row, "거래처명", None)
                            if client_name_val:
                                client_name_str = str(client_name_val).strip()
                                client_id = client_map_by_name.get(client_name_str)
                                if not client_id:
                                    # 이름으로도 거래처를 찾을 수 없으면 새로 생성 (사업자번호 없이)
                                    new_client = Client(
                                        name=client_name_str, 
                                        business_number=None, 
                                        is_active=True,
                                        client_type='원료' # 공급처이므로 타입을 '원료'로 지정
                                    )
                                    session.add(new_client)
                                    session.flush()
                                    client_id = new_client.id
                                    # 새 거래처 생성 기록용으로 보관
                                    try:
                                        created_clients.append((new_client, client_name_str, None))
                                    except Exception:
                                        pass
                                    # 새로 생성된 클라이언트를 이름 맵에 추가하여 중복 생성을 방지합니다.
                                    client_map_by_name[client_name_str] = client_id
                                    new_clients_count += 1
                                    print(f"  새 거래처 생성 (이름만): {client_name_str} -> ID {client_id}")
                                else:
                                    print(f"  거래처 매칭 성공 (이름): {client_name_str} -> ID {client_id}")
                        
                        material.supplier_id = client_id
                        
                        material.manufacturer = get_val(mat_row, "제조원명", "manufacturer") or ""
                        material.hs_code = get_val(mat_row, "HS CODE", "hs_code") or ""
                        material.origin = get_val(mat_row, "원산지", "origin") or ""
                        material.name_en = get_val(mat_row, "영문원료명", "name_en") or ""
                        material.nmpa_reg_num = get_val(mat_row, "NMPA등록번호", "nmpa_reg_num") or ""
                        
                        # 사용여부 처리
                        is_active_val = get_val(mat_row, "사용여부(Y/N)", "is_active") or "Y"
                        material.is_active = str(is_active_val).upper() in ["Y", "TRUE", "1", "YES"]

                        # 기존 전성분 삭제 (새로운 전성분으로 대체하기 위해)
                        material.ingredients.clear()
                        
                        processed_materials[code] = material
                        materials_count += 1
                        
                    except Exception as e:
                        print(f"재료 {i+1} 처리 중 오류: {e}")
                        continue

                # 세션 플러시하여 재료 ID 생성
                session.flush()
                print(f"재료 처리 완료: {materials_count}개, 새 거래처: {new_clients_count}개")

                # 2단계: 전성분 정보 처리 (기존 로직과 동일)
                ingredient_groups = {}
                
                for i, ing_row in enumerate(ingredients_data):
                    try:
                        material_code = get_val(ing_row, "원료코드", "material_code")
                        if not material_code:
                            print(f"전성분 {i+1}: 원료코드가 없어서 건너뜀")
                            continue
                        
                        material_code = str(material_code).strip()
                        if material_code not in processed_materials:
                            print(f"전성분 {i+1}: 원료코드 '{material_code}'에 해당하는 재료를 찾을 수 없음")
                            continue
                        
                        if material_code not in ingredient_groups:
                            ingredient_groups[material_code] = []
                        
                        ingredient_data = {
                            'name_ko': get_val(ing_row, "한글전성분", "name_ko") or "",
                            'name_en': get_val(ing_row, "INGREDIENT", "name_en") or "",
                            'cas_no': get_val(ing_row, "CAS NO.", "cas_no") or "",
                            'function': get_val(ing_row, "기능", "function") or "",
                            'ewg_grade': get_val(ing_row, "EWG등급", "ewg_grade") or "",
                            'ewg_data': get_val(ing_row, "EWG등급데이터", "ewg_data") or "",
                            'hs_code': get_val(ing_row, "HS CODE", "hs_code") or "",
                            'nmpa_reg_num': get_val(ing_row, "NMPA등록번호", "nmpa_reg_num") or "",
                            'remark': get_val(ing_row, "비고", "remark") or ""
                        }                        
                        
                        # 조성비 처리
                        composition_ratio_val = get_val(ing_row, "조성비(%)", "composition_ratio")
                        try:
                            ingredient_data['composition_ratio'] = float(composition_ratio_val) if composition_ratio_val else 0.0
                        except (ValueError, TypeError):
                            ingredient_data['composition_ratio'] = 0.0
                        
                        ingredient_groups[material_code].append(ingredient_data)
                        
                    except Exception as e:
                        print(f"전성분 {i+1} 처리 중 오류: {e}")
                        continue
                
                # 원료별로 전성분 추가
                for material_code, ingredients_list in ingredient_groups.items():
                    try:
                        parent_material = processed_materials[material_code]
                        print(f"원료 '{material_code}'에 {len(ingredients_list)}개의 전성분 추가")
                        
                        for ing_data in ingredients_list:
                            new_ingredient = Ingredient(
                                name_ko=ing_data['name_ko'],
                                name_en=ing_data['name_en'],
                                cas_no=ing_data['cas_no'],
                                composition_ratio=ing_data['composition_ratio'],
                                function=ing_data['function'],
                                ewg_grade=ing_data['ewg_grade'],
                                ewg_data=ing_data['ewg_data'],
                                hs_code=ing_data['hs_code'],
                                nmpa_reg_num=ing_data['nmpa_reg_num'],
                                remark=ing_data['remark']
                            )
                            parent_material.ingredients.append(new_ingredient)
                            ingredients_count += 1
                    
                    except Exception as e:
                        print(f"원료 '{material_code}' 전성분 추가 중 오류: {e}")
                        continue

                # --- 변경 이력 기록 (가져오기 전용) ---
                try:
                    timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                    user_name = getattr(self.current_user, 'username', 'unknown')

                    def key_of(ing):
                        return (
                            (ing.get('name_ko') or '').strip().lower(),
                            (ing.get('name_en') or '').strip().lower(),
                            (ing.get('cas_no') or '').strip().lower(),
                        )

                    for code, material in processed_materials.items():
                        action = actions_by_code.get(code, "정보 수정")
                        prev = prev_snapshots.get(code, {"ingredients": []})

                        # 현재 스냅샷 구성
                        curr_supplier_name = ""
                        try:
                            if material.supplier_id and hasattr(self, 'supplier_id_map'):
                                curr_supplier_name = self.supplier_id_map.get(material.supplier_id, "")
                            elif material.supplier:
                                curr_supplier_name = material.supplier.name or ""
                        except Exception:
                            pass

                        curr = {
                            "code": material.code or "",
                            "name": material.name or "",
                            "name_en": material.name_en or "",
                            "unit_price": material.unit_price if material.unit_price is not None else 0.0,
                            "package_unit": material.package_unit or "",
                            "supplier_id": material.supplier_id,
                            "supplier_name": curr_supplier_name,
                            "manufacturer": material.manufacturer or "",
                            "hs_code": material.hs_code or "",
                            "origin": material.origin or "",
                            "nmpa_reg_num": material.nmpa_reg_num or "",
                            "reg_date": material.reg_date or "",
                            "is_active": bool(material.is_active),
                            "ingredients": [
                                {
                                    "name_ko": ing.name_ko or "",
                                    "name_en": ing.name_en or "",
                                    "cas_no": ing.cas_no or "",
                                    "composition_ratio": ing.composition_ratio or 0.0,
                                    "function": ing.function or "",
                                    "ewg_grade": ing.ewg_grade or "",
                                    "ewg_data": ing.ewg_data or "",
                                    "remark": ing.remark or "",
                                }
                                for ing in (material.ingredients or [])
                            ],
                        }

                        log_entries = []
                        log_header = f"[{timestamp}] by {user_name} - {action} (엑셀 가져오기)"

                        def add_change(label, old, new):
                            if (old or "") != (new or ""):
                                log_entries.append(f"{label}: '{old}' -> '{new}'")

                        if action == "신규 생성":
                            # 신규 생성: 화이트리스트 필드만 기록 (빈칸/기본값 제외)
                            def add_nonempty(label, value, *, skip_zero=False):
                                try:
                                    if value is None:
                                        return
                                    if isinstance(value, str):
                                        if not value.strip():
                                            return
                                    if skip_zero and (isinstance(value, (int, float)) and float(value) == 0.0):
                                        return
                                    log_entries.append(f"{label}: '{value}'")
                                except Exception:
                                    pass

                            # 화이트리스트: 코드, 원료명, 단가, 포장단위, 공급처
                            add_nonempty("코드", curr['code'])
                            add_nonempty("원료명", curr['name'])
                            add_nonempty("단가", curr['unit_price'], skip_zero=True)
                            add_nonempty("포장단위", curr['package_unit'])
                            supplier_disp = curr['supplier_name'] or curr['supplier_id']
                            add_nonempty("공급처", supplier_disp)

                            # 전성분 초기 등록: 의미 있는 항목만 (이름 비어있고 0%는 제외)
                            if curr['ingredients']:
                                filtered_lines = []
                                for ing in curr['ingredients']:
                                    name_label = ing.get('name_ko') or ing.get('name_en') or ing.get('cas_no')
                                    comp = ing.get('composition_ratio', 0) or 0.0
                                    if (not name_label) and float(comp) == 0.0:
                                        continue
                                    label = name_label or '(이름 없음)'
                                    filtered_lines.append(f"- {label} | 조성비 {comp}")
                                if filtered_lines:
                                    log_entries.append("전성분 초기 등록:")
                                    log_entries.extend(filtered_lines)
                        else:
                            # 필드 변경 비교: 화이트리스트만 기록
                            add_change("원료명", prev.get('name'), curr.get('name'))
                            add_change("단가", prev.get('unit_price'), curr.get('unit_price'))
                            add_change("포장단위", prev.get('package_unit'), curr.get('package_unit'))
                            add_change("공급처", prev.get('supplier_name') or prev.get('supplier_id'), curr.get('supplier_name') or curr.get('supplier_id'))

                            prev_map = {key_of(ing): ing for ing in (prev.get('ingredients') or [])}
                            curr_map = {key_of(ing): ing for ing in (curr.get('ingredients') or [])}

                            # 추가 (의미 있는 항목만 기록)
                            for k, v in curr_map.items():
                                if k not in prev_map:
                                    name_label = v.get('name_ko') or v.get('name_en') or v.get('cas_no')
                                    comp = v.get('composition_ratio', 0) or 0.0
                                    if (not name_label) and float(comp) == 0.0:
                                        continue
                                    label = name_label or '(이름 없음)'
                                    log_entries.append(f"전성분 추가: {label} | 조성비 {comp}")
                            # 삭제
                            for k, v in prev_map.items():
                                if k not in curr_map:
                                    label = v['name_ko'] or v['name_en'] or v['cas_no'] or '(이름 없음)'
                                    log_entries.append(f"전성분 삭제: {label}")
                            # 변경(조성비) - 의미 있는 항목만 기록
                            for k in set(prev_map.keys()) & set(curr_map.keys()):
                                pv = prev_map[k]; cv = curr_map[k]
                                if (pv.get('composition_ratio') or 0.0) != (cv.get('composition_ratio') or 0.0):
                                    name_label = cv.get('name_ko') or cv.get('name_en') or cv.get('cas_no')
                                    if not name_label and float(cv.get('composition_ratio') or 0.0) == 0.0 and float(pv.get('composition_ratio') or 0.0) == 0.0:
                                        continue
                                    label = name_label or '(이름 없음)'
                                    log_entries.append(f"전성분 변경: {label} | 조성비 {pv.get('composition_ratio', 0)} -> {cv.get('composition_ratio', 0)}")

                        if log_entries:
                            log_body = "- " + "\n- ".join([str(e) for e in log_entries])
                            material.change_log = (material.change_log + "\n\n" if material.change_log else "") + f"{log_header}\n{log_body}"
                except Exception as _log_err:
                    print(f"[경고] 가져오기 변경 이력 기록 실패: {_log_err}")

                # --- 거래처(공급처) 신규 생성 이력도 남김: 일괄 업로드 집계를 위해 (엑셀 가져오기) 마커 포함 ---
                try:
                    if created_clients:
                        timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                        user_name = getattr(self.current_user, 'username', 'unknown')
                        for cli_obj, cli_name, cli_biz in created_clients:
                            try:
                                header = f"[{timestamp}] by {user_name} - 신규 생성 (엑셀 가져오기)"
                                lines = []
                                if cli_name:
                                    lines.append(f"거래처명: '{cli_name}'")
                                if cli_biz:
                                    lines.append(f"사업자번호: '{cli_biz}'")
                                # 타입 정보가 있으면 추가
                                try:
                                    if getattr(cli_obj, 'client_type', None):
                                        lines.append(f"유형: '{getattr(cli_obj, 'client_type')}'")
                                except Exception:
                                    pass
                                if lines:
                                    body = "- " + "\n- ".join(lines)
                                    cli_obj.change_log = (cli_obj.change_log + "\n\n" if getattr(cli_obj, 'change_log', None) else "") + f"{header}\n{body}"
                            except Exception:
                                continue
                        # 변경 사항 DB 반영
                        session.flush()
                except Exception as _cli_log_err:
                    print(f"[경고] 거래처 가져오기 변경 이력 기록 실패: {_cli_log_err}")

                # 데이터베이스 커밋
                session.commit()
                
                # 성공 메시지
                success_msg = f"엑셀 가져오기 완료!\n원료: {materials_count}개\n전성분: {ingredients_count}개\n새 거래처: {new_clients_count}개"
                messagebox.showinfo("성공", success_msg)
                print(success_msg)

                # 모든 DB 작업이 끝난 후 UI 새로고침
                self.bulk_importing = False
                self.refresh_data() # UI 전체 새로고침으로 변경

            except Exception as e:
                session.rollback()
                error_msg = f"가져오기 중 오류 발생: {str(e)}"
                print(f"오류 상세: {e}")
                import traceback
                traceback.print_exc()
                messagebox.showerror("데이터베이스 오류", error_msg)
                self.bulk_importing = False # 오류 발생 시에도 플래그 해제
                
            finally:
                session.close()
                
        except Exception as e:
            error_msg = f"파일 처리 중 오류 발생: {str(e)}"
            print(f"파일 오류 상세: {e}")
            messagebox.showerror("파일 오류", error_msg)
            self.bulk_importing = False # 오류 발생 시에도 플래그 해제
        
        # DB 동기화 기준선 업데이트 및 체크 재시작
        if hasattr(self.app, 'update_db_sync_baseline'):
            # 즉시 기준선 업데이트 (전체 변경사항 반영)
            self.app.update_db_sync_baseline()
            
        if sync_was_running and hasattr(self.app, 'start_db_sync_check'):
            # 3초 후에 동기화 체크 재시작 (DB 변경사항 정착될 시간)
            self.app.after(3000, lambda: (
                print("[원료가져오기] DB 동기화 체크 재시작"),
                self.app.start_db_sync_check()
            ))
        
        print("import_material_data 완료")

    # 나머지 메서드들은 다음 파일에서 계속...
    
    def reset_material_search(self):
        """원료 검색창을 초기화하고 전체 목록을 다시 불러옵니다."""
        self.material_search_entry.delete(0, "end")
        self.load_materials()

    def on_material_search(self, event=None):
        """검색창 입력 시 디바운싱을 적용하여 검색을 실행합니다."""
        if self.search_timer:
            self.after_cancel(self.search_timer)
        # 500ms(0.5초) 후에 load_materials 함수를 실행
        self.search_timer = self.after(500, self.load_materials)

    def load_materials(self):
        """DB에서 원료 목록을 검색하고 Treeview에 표시합니다."""
        search_term = self.material_search_entry.get().strip()
        # 검색 시에는 전성분도 함께 검색하도록 search_ingredients=True로 변경합니다.
        # 목록 표시에는 전성분 정보가 필요 없으므로 load_ingredients=False로 유지합니다.
        materials = db_manager.search_materials(search_term, load_ingredients=False, search_ingredients=True)
        
        # 1. UI 렌더링 성능 최적화 - 데이터를 먼저 메모리에 리스트로 준비
        material_data_list = []
        try:
            for i, mat in enumerate(materials):
                supplier_name = mat.supplier.name if mat.supplier else ""
                tag = 'oddrow' if i % 2 == 0 else 'evenrow'
                values = (
                    i + 1, mat.id, mat.code, mat.name,
                    f"{mat.unit_price:,.0f}" if mat.unit_price is not None else "",
                    mat.package_unit, supplier_name, mat.manufacturer, mat.hs_code,
                    mat.origin, mat.name_en or "", mat.nmpa_reg_num or "",
                )
                material_data_list.append((values, tag))

            # 2. Treeview를 한번에 업데이트
            # 기존 모든 행 삭제
            for item in self.material_tree.get_children():
                self.material_tree.delete(item)
            # 메모리에 준비된 데이터로 Treeview 채우기
            for values, tag in material_data_list:
                self.material_tree.insert("", "end", tags=(tag,), values=values)

        except Exception as e:
            print(f"원료 목록 로드 중 오류 발생: {e}")

    def load_clients_to_combobox(self):
        """거래처 정보를 콤보박스와 자동완성에 로드합니다 - 개선된 버전"""
        # 대량 가져오기 중일 때는 불필요한 호출 방지
        if getattr(self, "bulk_importing", False):
            print("대량 가져오기 중이므로 콤보박스 업데이트 건너뜀")
            return
        
        session = db_manager.get_session()
        try:
            # '원료' 타입의 활성 거래처만 불러옵니다.
            suppliers = session.query(Client).filter_by(is_active=True, client_type='원료').all()
            
            # 거래처 매핑 딕셔너리 생성
            self.supplier_map = {s.name: s.id for s in suppliers}  # 이름 -> ID
            self.supplier_id_map = {s.id: s.name for s in suppliers}  # ID -> 이름
            
            supplier_names = list(self.supplier_map.keys())
            
            print(f"로드된 공급처: {len(suppliers)}개")
            
            # AutocompleteEntry에 거래처 목록 설정 (오류 수정)
            if hasattr(self, 'supplier_entry'):
                self.supplier_entry.set_completion_list(supplier_names)
                print(f"AutocompleteEntry에 {len(supplier_names)}개 공급처 설정 완료")

        except Exception as e:
            print(f"거래처 로드 중 오류: {e}")
            import traceback
            traceback.print_exc()
        finally:
            session.close()

    def on_material_tree_select(self, event):
        """원료 트리뷰에서 항목 선택 시 호출되는 메서드 - 개선된 버전"""
        # 대량 가져오기 중이면 차단 (콤보박스 업데이트 방지)
        if getattr(self, "bulk_importing", False):
            print("대량 가져오기 중이므로 트리 선택 이벤트 무시")
            return
            
        if not hasattr(self, "supplier_entry"):
            return

        selected_item = self.material_tree.selection()
        if not selected_item:
            return

        mat_id = self.material_tree.item(selected_item[0], "values")[1]
        self._selected_material_id = mat_id

        # db_manager.search_materials에서 이미 client와 ingredients를 로드하므로
        # 여기서는 DB에 다시 접근할 필요 없이 트리뷰의 값을 활용합니다.
        # 단, 트리뷰에 모든 정보가 없을 수 있으므로, 상세 정보는 DB에서 다시 가져옵니다.
        session = db_manager.get_session()
        try:
            material = session.query(Material).options(
                joinedload(Material.ingredients),
                joinedload(Material.supplier)
            ).filter_by(id=mat_id).first()
            if not material:
                print(f"원료 ID {mat_id}를 찾을 수 없습니다.")
                return

            # 비관리자인 경우, 폼을 채우기 전에 입력 필드를 임시로 활성화
            if not self.current_user.is_admin:
                for entry in self.material_entries.values():
                    entry.configure(state="normal")
                for entry in self.ingredient_entries.values():
                    entry.configure(state="normal")

            print(f"선택된 원료: {material.name} (코드: {material.code})")

            # 기본 원료 정보 폼 초기화
            for key, entry in self.material_entries.items():
                if isinstance(entry, ctk.CTkComboBox):
                    entry.set("")
                else:
                    entry.delete(0, "end")

            # 원료 기본 정보 입력
            self.material_entries["코드"].insert(0, material.code or "")
            self.material_entries["원료명"].insert(0, material.name or "")
            self.material_entries["영문원료명"].insert(0, material.name_en or "")
            self.material_entries["단가"].insert(0, str(material.unit_price or 0.0))
            self.material_entries["포장단위"].insert(0, material.package_unit or "")
            self.material_entries["제조원명"].insert(0, material.manufacturer or "")
            self.material_entries["HS CODE"].insert(0, material.hs_code or "")
            self.material_entries["원산지"].insert(0, material.origin or "")
            self.material_entries["NMPA등록번호"].insert(0, material.nmpa_reg_num or "")
            self.material_entries["등록일"].insert(0, material.reg_date or "")

            # 거래처 정보 처리 (개선된 버전)
            supplier_name = ""
            if material.supplier:
                supplier_name = material.supplier.name
            elif hasattr(self, 'supplier_id_map') and material.supplier_id in self.supplier_id_map:
                supplier_name = self.supplier_id_map.get(material.supplier_id, "")
            
            # 거래처 입력 필드에 설정
            self.supplier_entry.delete(0, "end")
            if supplier_name:
                self.supplier_entry.insert(0, supplier_name)

            # 사용여부 체크박스 설정
            self.material_active_var.set("on" if material.is_active else "off")

            # 이력 보기 버튼 활성화
            self.material_history_button.configure(state="normal")
            # 전성분 정보를 temp_ingredients에 복사
            self.temp_ingredients = []
            
            for ing in material.ingredients:
                ingredient_data = {
                    "id": ing.id, 
                    "name_ko": ing.name_ko or "", 
                    "name_en": ing.name_en or "", 
                    "cas_no": ing.cas_no or "",
                    "composition_ratio": ing.composition_ratio or 0.0, 
                    "function": ing.function or "", 
                    "ewg_grade": ing.ewg_grade or "",
                    "ewg_data": ing.ewg_data or "",
                    "remark": ing.remark or ""
                }
                self.temp_ingredients.append(ingredient_data)
            
            print(f"temp_ingredients에 저장된 전성분 개수: {len(self.temp_ingredients)}")
            
            # 비관리자인 경우, 폼을 채운 후 다시 모든 필드를 비활성화
            if not self.current_user.is_admin:
                for entry in self.material_entries.values():
                    entry.configure(state="readonly")
                for entry in self.ingredient_entries.values():
                    entry.configure(state="readonly")

        except Exception as e:
            print(f"원료 선택 처리 중 오류: {e}")
            import traceback
            traceback.print_exc()
            messagebox.showerror("데이터베이스 오류", f"원료 정보 로드 중 오류 발생: {e}")
            return
            
        finally:
            session.close()
        
        # 세션을 닫힌 후에 UI 업데이트 (메모리의 데이터 활용)
        try:
            self.refresh_ingredient_tree()
            self.clear_ingredient_form()
            
        except Exception as e:
            print(f"UI 업데이트 중 오류: {e}")
            messagebox.showerror("UI 오류", f"화면 업데이트 중 오류 발생: {e}")

    def refresh_ingredient_tree(self):
        """
        전성분 트리뷰를 새로고침합니다.
        - 개선: 기존 모든 항목을 먼저 삭제하여 UI 불일치 문제를 해결합니다.
        """
        try:
            # 기존 모든 항목을 삭제
            for item in self.ingredient_tree.get_children(): 
                self.ingredient_tree.delete(item)
            
            print(f"트리뷰 새로고침: {len(self.temp_ingredients)}개 전성분 표시")
            
            # temp_ingredients의 모든 항목을 트리뷰에 추가
            for i, ing in enumerate(self.temp_ingredients):
                tag = 'oddrow' if i % 2 == 0 else 'evenrow'
                # 컬럼 설정에 따라 값을 정적으로 구성
                values = (
                    ing.get("id", f"temp_{i}"), 
                    ing.get("name_ko", ""), 
                    ing.get("name_en", ""), 
                    ing.get("cas_no", ""),
                    ing.get("composition_ratio", ""),
                    ing.get("function", ""),
                    ing.get("ewg_grade", ""),
                    ing.get("ewg_data", ""),
                    ing.get("remark", "")
                )
                
                item_id = self.ingredient_tree.insert("", "end", tags=(tag,), values=values)
                print(f"  {i+1}. {ing.get('name_ko', '')} ({ing.get('name_en', '')}) 추가됨")
                
            print(f"트리뷰 새로고침 완료: 총 {len(self.ingredient_tree.get_children())}개 항목 표시")
            
        except Exception as e:
            print(f"트리뷰 새로고침 중 오류: {e}")
            import traceback
            traceback.print_exc()

    def _setup_treeview_columns(self, treeview, columns_config):
        """Treeview의 컬럼을 헤더를 설정하고 초기 가시성을 적용합니다."""
        treeview.configure(columns=list(columns_config.keys()))
        for col_id, config in columns_config.items():
            treeview.heading(col_id, text=config["text"])
            treeview.column(col_id, width=config["width"], anchor=config.get("anchor", "w"))
        
        visible_columns = [col_id for col_id, config in columns_config.items() if config.get("visible", True)]
        treeview.configure(displaycolumns=visible_columns)

    def _update_visible_columns(self, treeview, columns_config):
        """체크박스 상태에 따라 Treeview의 열을 업데이트합니다."""
        visible_columns = [col_id for col_id, config in columns_config.items() if config.get("variable") and config["variable"].get()]
        # ID 컬럼은 항상 숨겨져야 하므로 visible_columns에 포함되지 않도록 합니다.
        if 'id' not in visible_columns:
            treeview.configure(displaycolumns=visible_columns)

    def on_ingredient_tree_select(self, event):
        selected_item = self.ingredient_tree.selection()
        if not selected_item:
            return
        
        ing_id_val = self.ingredient_tree.item(selected_item[0], "values")[self.get_column_index("id")]
        if str(ing_id_val).isdigit():
            ing_id = int(ing_id_val)
        else:
            ing_id = ing_id_val

        self._selected_ingredient_id = ing_id
        selected_ing = next((ing for ing in self.temp_ingredients if ing.get("id") == ing_id), None)
        if not selected_ing:
            return
        
        # 비관리자인 경우, 폼을 채우기 전에 입력 필드를 임시로 활성화
        if not self.can_edit_data():
            for entry in self.ingredient_entries.values():
                entry.configure(state="normal")

        for key, entry in self.ingredient_entries.items():
            entry.delete(0, "end")
        self.ingredient_entries["한글전성분"].insert(0, selected_ing.get("name_ko", ""))
        self.ingredient_entries["INGREDIENT"].insert(0, selected_ing.get("name_en", ""))
        self.ingredient_entries["CAS NO."].insert(0, selected_ing.get("cas_no", ""))
        self.ingredient_entries["조성비(%)"].insert(0, str(selected_ing.get("composition_ratio", "")))
        self.ingredient_entries["기능"].insert(0, selected_ing.get("function", ""))
        self.ingredient_entries["EWG등급"].insert(0, selected_ing.get("ewg_grade", ""))
        self.ingredient_entries["EWG등급데이터"].insert(0, selected_ing.get("ewg_data", ""))
        self.ingredient_entries["비고"].insert(0, selected_ing.get("remark", ""))

        # 비관리자인 경우, 폼을 채운 후 다시 모든 필드를 비활성화
        if not self.can_edit_data():
            for entry in self.ingredient_entries.values():
                entry.configure(state="readonly")

    def get_column_index(self, col_name):
        """특정 컬럼 리스트에서 특정 컬럼의 인덱스를 반환합니다."""
        return list(self.ing_cols_config.keys()).index(col_name)

    def clear_material_form(self):
        self._selected_material_id = None
        # 비관리자인 경우, 폼을 지우기 전에 입력 필드를 임시로 활성화
        if not self.can_edit_data():
            for entry in self.material_entries.values():
                entry.configure(state="normal")
            for entry in self.ingredient_entries.values():
                entry.configure(state="normal")
                
        for entry in self.material_entries.values():
            if isinstance(entry, ctk.CTkComboBox):
                entry.set("")
            else:
                entry.delete(0, "end")
        
        today_date = datetime.now().strftime("%Y-%m-%d")
        self.material_entries["등록일"].insert(0, today_date)

        self.material_active_var.set("on")
        self.temp_ingredients = []
        self.material_history_button.configure(state="disabled")

        self.clear_ingredient_form()
        if self.material_tree.selection():
            self.material_tree.selection_remove(self.material_tree.selection()[0])
            
        # 비관리자인 경우, 폼을 지운 후 다시 모든 필드를 비활성화
        if not self.can_edit_data():
            for entry in self.material_entries.values():
                entry.configure(state="readonly")
            for entry in self.ingredient_entries.values():
                entry.configure(state="readonly")
        
        self.refresh_ingredient_tree()

    def clear_ingredient_form(self):
        self._selected_ingredient_id = None
        # 비관리자인 경우, 폼을 지우기 전에 입력 필드를 임시로 활성화
        if not self.can_edit_data():
            for entry in self.ingredient_entries.values():
                entry.configure(state="normal")
                
        for entry in self.ingredient_entries.values():
            entry.delete(0, "end")
        if self.ingredient_tree.selection():
            self.ingredient_tree.selection_remove(self.ingredient_tree.selection()[0])
            
        # 비관리자인 경우, 폼을 지운 후 다시 모든 필드를 비활성화
        if not self.can_edit_data():
            for entry in self.ingredient_entries.values():
                entry.configure(state="readonly")

    def add_ingredient(self):
        # 편집 권한 확인
        if not self.can_edit_data():
            messagebox.showwarning("권한 오류", "성분 데이터를 편집할 권한이 없습니다.\n편집은 RQD/MSAD 권한이 필요합니다.\n현재 권한으로는 검색/참고만 가능합니다.")
            return
            
        try:
            name_ko = self.ingredient_entries["한글전성분"].get().strip()
            name_en = self.ingredient_entries["INGREDIENT"].get().strip()
            if not name_ko and not name_en:
                messagebox.showwarning("입력 오류", "한글전성분 또는 영문전성분을 입력해주세요.")
                return

            composition_ratio_str = self.ingredient_entries["조성비(%)"].get().strip()
            try:
                composition_ratio = float(composition_ratio_str) if composition_ratio_str else 0.0
            except ValueError:
                messagebox.showwarning("입력 오류", "조성비는 숫자로 입력해주세요.")
                return

            new_ingredient = {
                "id": f"temp_{len(self.temp_ingredients)}",
                "name_ko": name_ko,
                "name_en": name_en,
                "cas_no": self.ingredient_entries["CAS NO."].get().strip(),
                "composition_ratio": composition_ratio,
                "function": self.ingredient_entries["기능"].get().strip(),
                "ewg_grade": self.ingredient_entries["EWG등급"].get().strip(),
                "ewg_data": self.ingredient_entries["EWG등급데이터"].get().strip(),
                "remark": self.ingredient_entries["비고"].get().strip()
            }

            self.temp_ingredients.append(new_ingredient)
            self.refresh_ingredient_tree()
            self.clear_ingredient_form()
            
        except Exception as e:
            messagebox.showerror("오류", f"전성분 추가 중 오류 발생: {e}")

    def update_ingredient(self):
        # 편집 권한 확인
        if not self.can_edit_data():
            messagebox.showwarning("권한 오류", "성분 데이터를 편집할 권한이 없습니다.\n편집은 RQD/MSAD 권한이 필요합니다.\n현재 권한으로는 검색/참고만 가능합니다.")
            return
            
        if self._selected_ingredient_id is None:
            messagebox.showwarning("선택 오류", "수정할 전성분을 선택해주세요.")
            return

        try:
            name_ko = self.ingredient_entries["한글전성분"].get().strip()
            name_en = self.ingredient_entries["INGREDIENT"].get().strip()
            if not name_ko and not name_en:
                messagebox.showwarning("입력 오류", "한글전성분 또는 영문전성분을 입력해주세요.")
                return

            composition_ratio_str = self.ingredient_entries["조성비(%)"].get().strip()
            try:
                composition_ratio = float(composition_ratio_str) if composition_ratio_str else 0.0
            except ValueError:
                messagebox.showwarning("입력 오류", "조성비는 숫자로 입력해주세요.")
                return

            for ing in self.temp_ingredients:
                if ing.get("id") == self._selected_ingredient_id:
                    ing.update({
                        "name_ko": name_ko,
                        "name_en": name_en,
                        "cas_no": self.ingredient_entries["CAS NO."].get().strip(),
                        "composition_ratio": composition_ratio,
                        "function": self.ingredient_entries["기능"].get().strip(),
                        "ewg_grade": self.ingredient_entries["EWG등급"].get().strip(),
                        "ewg_data": self.ingredient_entries["EWG등급데이터"].get().strip(),
                        "remark": self.ingredient_entries["비고"].get().strip()
                    })
                    break

            self.refresh_ingredient_tree()
            self.clear_ingredient_form()
            
        except Exception as e:
            messagebox.showerror("오류", f"전성분 수정 중 오류 발생: {e}")

    def remove_ingredient(self):
        # 편집 권한 확인
        if not self.can_edit_data():
            messagebox.showwarning("권한 오류", "성분 데이터를 편집할 권한이 없습니다.\n편집은 RQD/MSAD 권한이 필요합니다.\n현재 권한으로는 검색/참고만 가능합니다.")
            return
            
        if self._selected_ingredient_id is None:
            messagebox.showwarning("선택 오류", "삭제할 전성분을 선택해주세요.")
            return

        if messagebox.askyesno("삭제 확인", "선택한 전성분을 삭제하시겠습니까?"):
            self.temp_ingredients = [ing for ing in self.temp_ingredients if ing.get("id") != self._selected_ingredient_id]
            self.refresh_ingredient_tree()
            self.clear_ingredient_form()

    def save_material(self):
        # 편집 권한 확인
        if not self.can_edit_data():
            messagebox.showwarning("권한 오류", "성분 데이터를 편집할 권한이 없습니다.\n편집은 RQD/MSAD 권한이 필요합니다.\n현재 권한으로는 검색/참고만 가능합니다.")
            return
            
        try:
            # 필수 필드 검증
            code = self.material_entries["코드"].get().strip()
            name = self.material_entries["원료명"].get().strip()
            
            if not code:
                messagebox.showwarning("입력 오류", "원료 코드를 입력해주세요.")
                return
            if not name:
                messagebox.showwarning("입력 오류", "원료명을 입력해주세요.")
                return

            # 단가 검증
            unit_price_str = self.material_entries["단가"].get().strip()
            try:
                unit_price = float(unit_price_str) if unit_price_str else 0.0
            except ValueError:
                messagebox.showwarning("입력 오류", "단가는 숫자로 입력해주세요.")
                return

            # 공급처 처리
            supplier_name = self.supplier_entry.get().strip()
            supplier_id = None
            if supplier_name and hasattr(self, 'supplier_map'):
                supplier_id = self.supplier_map.get(supplier_name)
                if not supplier_id:
                    # 새 공급처 생성
                    session = db_manager.get_session()
                    try:
                        new_supplier = Client(
                            name=supplier_name,
                            is_active=True,
                            client_type='원료'
                        )
                        session.add(new_supplier)
                        session.flush()
                        supplier_id = new_supplier.id
                        session.commit()
                        
                        # 로컬 매핑 업데이트
                        self.supplier_map[supplier_name] = supplier_id
                        self.supplier_id_map[supplier_id] = supplier_name
                        
                    except Exception as e:
                        session.rollback()
                        messagebox.showerror("공급처 생성 오류", f"새 공급처 생성 중 오류: {e}")
                        return
                    finally:
                        session.close()

            session = db_manager.get_session()
            try:
                # --- 변경 이력 작성을 위해 '이전 상태' 스냅샷 준비 ---
                prev_snapshot = None
                action = "신규 생성"

                if self._selected_material_id:
                    # 기존 원료 수정
                    material = session.query(Material).get(self._selected_material_id)
                    if not material:
                        messagebox.showerror("오류", "수정할 원료를 찾을 수 없습니다.")
                        return
                    # 이전 상태 스냅샷
                    prev_snapshot = {
                        "code": material.code or "",
                        "name": material.name or "",
                        "name_en": material.name_en or "",
                        "unit_price": material.unit_price if material.unit_price is not None else 0.0,
                        "package_unit": material.package_unit or "",
                        "supplier_id": material.supplier_id,
                        "supplier_name": (material.supplier.name if material.supplier else ""),
                        "manufacturer": material.manufacturer or "",
                        "hs_code": material.hs_code or "",
                        "origin": material.origin or "",
                        "nmpa_reg_num": material.nmpa_reg_num or "",
                        "reg_date": material.reg_date or "",
                        "is_active": bool(material.is_active),
                        "ingredients": [
                            {
                                "name_ko": ing.name_ko or "",
                                "name_en": ing.name_en or "",
                                "cas_no": ing.cas_no or "",
                                "composition_ratio": ing.composition_ratio or 0.0,
                                "function": ing.function or "",
                                "ewg_grade": ing.ewg_grade or "",
                                "ewg_data": ing.ewg_data or "",
                                "remark": ing.remark or "",
                            }
                            for ing in (material.ingredients or [])
                        ],
                    }
                    action = "정보 수정"
                else:
                    # 새 원료 생성
                    # 코드 중복 검사
                    existing = session.query(Material).filter_by(code=code).first()
                    if existing:
                        messagebox.showwarning("중복 오류", f"코드 '{code}'는 이미 사용 중입니다.")
                        return
                    
                    material = Material(code=code)
                    session.add(material)

                # 원료 정보 업데이트
                material.name = name
                material.name_en = self.material_entries["영문원료명"].get().strip()
                material.unit_price = unit_price
                material.package_unit = self.material_entries["포장단위"].get().strip()
                material.supplier_id = supplier_id
                material.manufacturer = self.material_entries["제조원명"].get().strip()
                material.hs_code = self.material_entries["HS CODE"].get().strip()
                material.origin = self.material_entries["원산지"].get().strip()
                material.nmpa_reg_num = self.material_entries["NMPA등록번호"].get().strip()
                material.reg_date = self.material_entries["등록일"].get().strip()
                material.is_active = self.material_active_var.get() == "on"

                # 기존 전성분 삭제
                material.ingredients.clear()

                # 새 전성분 추가
                for ing_data in self.temp_ingredients:
                    ingredient = Ingredient(
                        name_ko=ing_data.get("name_ko", ""),
                        name_en=ing_data.get("name_en", ""),
                        cas_no=ing_data.get("cas_no", ""),
                        composition_ratio=ing_data.get("composition_ratio", 0.0),
                        function=ing_data.get("function", ""),
                        ewg_grade=ing_data.get("ewg_grade", ""),
                        ewg_data=ing_data.get("ewg_data", ""),
                        remark=ing_data.get("remark", "")
                    )
                    material.ingredients.append(ingredient)
                
                # --- 변경 이력 기록 ---
                try:
                    timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                    user_name = getattr(self.current_user, 'username', 'unknown')
                    log_header = f"[{timestamp}] by {user_name} - {action}"

                    log_entries = []

                    # 현재 값 스냅샷 (로깅 용)
                    curr_supplier_name = ""
                    if material.supplier_id:
                        try:
                            # 가능하면 이름으로 표기
                            if hasattr(self, 'supplier_id_map'):
                                curr_supplier_name = self.supplier_id_map.get(material.supplier_id, "")
                        except Exception:
                            pass

                    curr_snapshot = {
                        "code": material.code or "",
                        "name": material.name or "",
                        "name_en": material.name_en or "",
                        "unit_price": material.unit_price if material.unit_price is not None else 0.0,
                        "package_unit": material.package_unit or "",
                        "supplier_id": material.supplier_id,
                        "supplier_name": curr_supplier_name,
                        "manufacturer": material.manufacturer or "",
                        "hs_code": material.hs_code or "",
                        "origin": material.origin or "",
                        "nmpa_reg_num": material.nmpa_reg_num or "",
                        "reg_date": material.reg_date or "",
                        "is_active": bool(material.is_active),
                        "ingredients": [
                            {
                                "name_ko": ing.name_ko or "",
                                "name_en": ing.name_en or "",
                                "cas_no": ing.cas_no or "",
                                "composition_ratio": ing.composition_ratio or 0.0,
                                "function": ing.function or "",
                                "ewg_grade": ing.ewg_grade or "",
                                "ewg_data": ing.ewg_data or "",
                                "remark": ing.remark or "",
                            }
                            for ing in (material.ingredients or [])
                        ],
                    }

                    def add_change(label, old, new):
                        if (old or "") != (new or ""):
                            log_entries.append(f"{label}: '{old}' -> '{new}'")

                    if action == "신규 생성":
                        # 신규 생성 시 화이트리스트 필드만 기록 (빈칸/기본값 제외)
                        def add_nonempty(label, value, *, skip_zero=False):
                            try:
                                if value is None:
                                    return
                                if isinstance(value, str):
                                    if not value.strip():
                                        return
                                if skip_zero and (isinstance(value, (int, float)) and float(value) == 0.0):
                                    return
                                log_entries.append(f"{label}: '{value}'")
                            except Exception:
                                pass

                        # 화이트리스트: 코드, 원료명, 단가, 포장단위, 공급처
                        add_nonempty("코드", curr_snapshot['code'])
                        add_nonempty("원료명", curr_snapshot['name'])
                        add_nonempty("단가", curr_snapshot['unit_price'], skip_zero=True)
                        add_nonempty("포장단위", curr_snapshot['package_unit'])
                        supplier_disp = curr_snapshot['supplier_name'] or curr_snapshot['supplier_id']
                        add_nonempty("공급처", supplier_disp)

                        # 전성분 초기 목록: 의미 있는 항목만 기록 (이름이 비어있고 조성비 0은 제외)
                        ing_lines = []
                        for ing in curr_snapshot['ingredients']:
                            name_label = ing['name_ko'] or ing['name_en'] or ing['cas_no']
                            comp = ing.get('composition_ratio', 0) or 0.0
                            if (not name_label) and float(comp) == 0.0:
                                continue
                            label = name_label or '(이름 없음)'
                            ing_lines.append(f"- {label} | 조성비 {comp}")
                        if ing_lines:
                            log_entries.append("전성분 초기 등록:")
                            log_entries.extend(ing_lines)
                    else:
                        # 필드 변경 비교: 화이트리스트만 기록
                        add_change("원료명", prev_snapshot['name'], curr_snapshot['name'])
                        add_change("단가", prev_snapshot['unit_price'], curr_snapshot['unit_price'])
                        add_change("포장단위", prev_snapshot['package_unit'], curr_snapshot['package_unit'])
                        add_change("공급처", prev_snapshot.get('supplier_name') or prev_snapshot.get('supplier_id'), curr_snapshot.get('supplier_name') or curr_snapshot.get('supplier_id'))

                        # 전성분 변경 비교 (키: (ko,en,cas))
                        def key_of(ing):
                            return (
                                (ing.get('name_ko') or '').strip().lower(),
                                (ing.get('name_en') or '').strip().lower(),
                                (ing.get('cas_no') or '').strip().lower(),
                            )
                        prev_map = {key_of(ing): ing for ing in (prev_snapshot.get('ingredients') or [])}
                        curr_map = {key_of(ing): ing for ing in (curr_snapshot.get('ingredients') or [])}

                        # 추가 (의미 있는 항목만)
                        for k, v in curr_map.items():
                            if k not in prev_map:
                                name_label = v.get('name_ko') or v.get('name_en') or v.get('cas_no')
                                comp = v.get('composition_ratio', 0) or 0.0
                                if (not name_label) and float(comp) == 0.0:
                                    continue
                                label = name_label or '(이름 없음)'
                                log_entries.append(f"전성분 추가: {label} | 조성비 {comp}")
                        # 삭제
                        for k, v in prev_map.items():
                            if k not in curr_map:
                                label = v['name_ko'] or v['name_en'] or v['cas_no'] or '(이름 없음)'
                                log_entries.append(f"전성분 삭제: {label}")
                        # 변경(주요: 조성비) - 의미 있는 항목만
                        for k in set(prev_map.keys()) & set(curr_map.keys()):
                            prev_v = prev_map[k]
                            curr_v = curr_map[k]
                            if (prev_v.get('composition_ratio') or 0.0) != (curr_v.get('composition_ratio') or 0.0):
                                name_label = curr_v.get('name_ko') or curr_v.get('name_en') or curr_v.get('cas_no')
                                if not name_label and float(curr_v.get('composition_ratio') or 0.0) == 0.0 and float(prev_v.get('composition_ratio') or 0.0) == 0.0:
                                    continue
                                label = name_label or '(이름 없음)'
                                log_entries.append(f"전성분 변경: {label} | 조성비 {prev_v.get('composition_ratio', 0)} -> {curr_v.get('composition_ratio', 0)}")

                    if log_entries:
                        log_body = "- " + "\n- ".join([str(e) for e in log_entries])
                        material.change_log = (material.change_log + "\n\n" if material.change_log else "") + f"{log_header}\n{log_body}"
                except Exception as _log_err:
                    # 로깅 실패는 저장을 막지 않되 콘솔에 표시
                    print(f"[경고] 원료 변경 이력 기록 실패: {_log_err}")

                session.commit()
                messagebox.showinfo("성공", "원료가 성공적으로 저장되었습니다.")
                
                # UI 새로고침
                self.refresh_data()
                self.clear_material_form()
                # 홈 화면도 즉시 최신 이력을 반영하도록 새로고침 (사용자가 홈으로 돌아가면 바로 보이도록)
                try:
                    if hasattr(self, 'app') and getattr(self.app, 'frames', None) and self.app.frames.get('home'):
                        self.app.frames['home'].refresh_data()
                except Exception as _e:
                    print(f"[경고] 홈 화면 새로고침 실패(무시): {_e}")
                
            except Exception as e:
                session.rollback()
                messagebox.showerror("저장 오류", f"원료 저장 중 오류 발생: {e}")
            finally:
                session.close()
                
        except Exception as e:
            messagebox.showerror("오류", f"원료 저장 중 오류 발생: {e}")

    def delete_material(self):
        # 편집 권한 확인
        if not self.can_edit_data():
            messagebox.showwarning("권한 오류", "성분 데이터를 편집할 권한이 없습니다.\n편집은 RQD/MSAD 권한이 필요합니다.\n현재 권한으로는 검색/참고만 가능합니다.")
            return
            
        if not self._selected_material_id:
            messagebox.showwarning("선택 오류", "삭제할 원료를 선택해주세요.")
            return

        if messagebox.askyesno("삭제 확인", "선택한 원료를 삭제하시겠습니까?\n이 작업은 되돌릴 수 없습니다."):
            session = db_manager.get_session()
            try:
                material = session.query(Material).get(self._selected_material_id)
                if material:
                    session.delete(material)
                    session.commit()
                    messagebox.showinfo("성공", "원료가 성공적으로 삭제되었습니다.")
                    
                    # UI 새로고침
                    self.refresh_data()
                    self.clear_material_form()
                else:
                    messagebox.showerror("오류", "삭제할 원료를 찾을 수 없습니다.")
                    
            except Exception as e:
                session.rollback()
                messagebox.showerror("삭제 오류", f"원료 삭제 중 오류 발생: {e}")
            finally:
                session.close()

    def show_selected_material_history(self):
        if not self._selected_material_id:
            messagebox.showwarning("선택 오류", "이력을 조회할 원료를 선택해주세요.")
            return
        # 선택된 원료 객체를 조회하여 단일 항목 이력 팝업을 띄웁니다.
        session = db_manager.get_session()
        try:
            material = session.query(Material).get(self._selected_material_id)
            if not material:
                messagebox.showerror("오류", "선택한 원료를 찾을 수 없습니다.")
                return
            if not material.change_log:
                messagebox.showinfo("정보", "선택한 원료의 변경 이력이 없습니다.")
                return
            # HistoryPopup은 items의 iterable을 기대하므로 단일 항목도 리스트로 감쌉니다.
            HistoryPopup(self, "원료 변경 이력", [material], item_name_key='name', item_code_key='code')
        finally:
            session.close()

    def show_all_material_history(self):
        # 전체 원료 목록을 조회하여 이력 팝업을 띄웁니다.
        session = db_manager.get_session()
        try:
            materials = session.query(Material).all()
            if not materials or not any(m.change_log for m in materials):
                messagebox.showinfo("정보", "표시할 변경 이력이 없습니다.")
                return
            HistoryPopup(self, "전체 원료 변경 이력", materials, item_name_key='name', item_code_key='code')
        finally:
            session.close()
    
    def focus_material_by_id(self, material_id: int):
        """원료 목록에서 해당 ID를 찾아 선택하고 상세를 표시합니다."""
        try:
            # 목록 최신화 후 탐색
            self.load_materials()
            target_iid = None
            for iid in self.material_tree.get_children():
                try:
                    vals = self.material_tree.item(iid, 'values')
                    # values 구조: (group, id, code, name, ...)
                    if len(vals) >= 2 and str(vals[1]) == str(material_id):
                        target_iid = iid
                        break
                except Exception:
                    continue
            if target_iid:
                self.material_tree.selection_set(target_iid)
                self.material_tree.focus(target_iid)
                self.material_tree.see(target_iid)
                # 선택 핸들러 호출로 상세 로드
                self.on_material_tree_select(event=None)
                return True
            return False
        except Exception as e:
            print(f"[경고] 원료 포커스 실패: {e}")
            return False
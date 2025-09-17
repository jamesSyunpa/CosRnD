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
        self.form_container.grid_columnconfigure(1, weight=1)  # ?�력 ?�드 가변

        material_labels = ["코드", "원료명", "용도", "보관온도", "공급처", "제조회사명", "HS CODE", "원산지", "영문원료명", "NMPA등록번호", "등록일"]
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

        self.ingredient_tree = ttk.Treeview(ingredient_frame, columns=list(self.ing_cols_config.keys()), show="headings", height=5) # noqa
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

        ing_labels = ["전성분명", "INGREDIENT", "CAS NO.", "조성비(%)", "기능", "EWG등급", "EWG등급데이터", "비고"]
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
            self.form_container.configure(label_text=f"원료 정보 조회 전용 (현재 권한: {user_role}) - 편집은 관리자(MSAD) 권한 필요")
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

        # ?�리�??�성
        mat_tree_cols = ("group", "id", "code", "name", "unit_price", "package_unit", "client", "manufacturer", "hs_code", "origin", "name_en", "nmpa_reg_num")
        self.material_tree = ttk.Treeview(list_frame, columns=mat_tree_cols, show="headings", selectmode="browse")

        # 컬럼 ?�정
        # 'id' 컬럼?� ?��? 처리
        self.material_tree.heading("group", text="구분");           self.material_tree.column("group", width=50, anchor="center")
        self.material_tree.heading("id", text="ID");                self.material_tree.column("id", width=0, stretch=tk.NO) # ID 컬럼 숨기기
        self.material_tree.heading("code", text="코드");            self.material_tree.column("code", width=100, anchor="w")
        self.material_tree.heading("name", text="자료명");          self.material_tree.column("name", width=200, anchor="w")
        self.material_tree.heading("unit_price", text="단가");       self.material_tree.column("unit_price", width=80, anchor="e")
        self.material_tree.heading("package_unit", text="포장단위"); self.material_tree.column("package_unit", width=80, anchor="center")
        self.material_tree.heading("client", text="공급처");        self.material_tree.column("client", width=150, anchor="w")
        self.material_tree.heading("manufacturer", text="제조회사명"); self.material_tree.column("manufacturer", width=150, anchor="w")
        self.material_tree.heading("hs_code", text="HS CODE");      self.material_tree.column("hs_code", width=100, anchor="w")
        self.material_tree.heading("origin", text="원산지");        self.material_tree.column("origin", width=100, anchor="w")
        self.material_tree.heading("name_en", text="영문자료명");    self.material_tree.column("name_en", width=200, anchor="w")
        self.material_tree.heading("nmpa_reg_num", text="NMPA등록번호"); self.material_tree.column("nmpa_reg_num", width=120, anchor="w")

        # 'id' 컬럼???�깁?�다.
        self.material_tree.configure(displaycolumns=[col for col in mat_tree_cols if col != 'id'])

        # 배치
        self.material_tree.grid(row=1, column=0, sticky="nsew", padx=(10, 0), pady=(0, 5))

        # ?�크롤바
        v_scrollbar = ttk.Scrollbar(list_frame, orient="vertical", command=self.material_tree.yview)
        self.material_tree.configure(yscrollcommand=v_scrollbar.set)
        v_scrollbar.grid(row=1, column=1, sticky="ns", pady=(0, 5))

        h_scrollbar = ttk.Scrollbar(list_frame, orient="horizontal", command=self.material_tree.xview)
        self.material_tree.configure(xscrollcommand=h_scrollbar.set)
        h_scrollbar.grid(row=2, column=0, columnspan=2, sticky="ew", padx=(10, 0), pady=(0, 10))
        
        # ?�택 ?�벤??바인??
        self.material_tree.bind("<<TreeviewSelect>>", self.on_material_tree_select)
                               
    def _create_column_selection_menu(self, treeview, columns_config, button_widget):
        """???�택 체크박스 메뉴�??�성?�고 버튼???�결?�니??"""
        column_menu = tk.Menu(button_widget, tearoff=0)
        
        for col_id, config in columns_config.items():
            # ID ?��? ??�� ?��? 처리
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
            messagebox.showwarning("권한 오류", "성분 데이터를 편집할 권한이 없습니다.\n편집은 관리자(MSAD) 권한이 필요합니다.\n현재 권한으로는 조회만 가능합니다.")
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
                # 기존 ?�라?�언??�??�성
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
                
                # 처리된 자료들을 저장할 딕셔너리
                processed_materials = {}
                materials_count = 0
                ingredients_count = 0
                new_clients_count = 0
                
                print(f"가져올 자료 데이터: {len(materials_data)}개")
                print(f"가져올 성분 데이터: {len(ingredients_data)}개")
                
                # 1단계: 자료 정보 처리 (개선된 거래처 처리 포함)
                for i, mat_row in enumerate(materials_data):
                    try:
                        code = get_val(mat_row, "코드", "code")
                        if not code:
                            print(f"자료 {i+1}: 코드가 없어서 건너뜀")
                            continue
                        
                        # 기존 자료 찾기 또는 새로 생성
                        material = session.query(Material).filter_by(code=code).first()
                        if not material:
                            material = Material(code=code)
                            session.add(material)
                            print(f"새 자료 생성: {code}")
                        else:
                            print(f"기존 자료 업데이트: {code}")

                        # 자료 기본 정보 설정
                        material.name = get_val(mat_row, "자료명", "name") or ""
                        material.name_en = get_val(mat_row, "영문자료명", "name_en") or ""
                        
                        # ?��? 처리
                        unit_price_val = get_val(mat_row, "?��?", "unit_price")
                        try:
                            material.unit_price = float(unit_price_val) if unit_price_val else 0.0
                        except (ValueError, TypeError):
                            material.unit_price = 0.0
                        
                        material.package_unit = get_val(mat_row, "?�장?�위", "package_unit") or ""
                        
                        # ========== 개선??거래�?ID ?�정 ==========
                        client_id = None

                        # 1?�위: '거래처사?�자번호' ?�이 ?�으�??�당 번호�?찾기
                        biz_num_val = get_val(mat_row, "거래처코???�업?�번??", "client_business_number") # 거래�??�플릿과 ??맞춤
                        if biz_num_val:
                            biz_num_str = str(biz_num_val).strip()
                            client_id = client_map_by_biz_num.get(biz_num_str)
                            if not client_id:
                                # ?�당 ?�업?�번?�의 거래처�? ?�으�??�로 ?�성
                                client_name_val = get_val(mat_row, "거래처명", "client_name") or biz_num_str
                                new_client = Client(
                                    name=str(client_name_val).strip(), 
                                    business_number=biz_num_str, 
                                    is_active=True,
                                    client_type='?�료'  # 공급처이므�??�?�을 '?�료'�?지??
                                )
                                session.add(new_client)
                                session.flush()
                                client_id = new_client.id
                                client_map_by_biz_num[biz_num_str] = client_id
                                # ?�름 맵에??추�??�여 ?��????��?
                                client_map_by_name[str(client_name_val).strip()] = client_id
                                new_clients_count += 1
                                print(f"  ??거래�??�성 (?�업?�번??기�?): {client_name_val} ({biz_num_str}) -> ID {client_id}")
                            else:
                                print(f"  거래�?매칭 ?�공 (?�업?�번??: {biz_num_str} -> ID {client_id}")

                        # 2?�위: '거래처사?�자번호'가 ?�을 경우, '거래처명'?�로 찾기
                        else:
                            client_name_val = get_val(mat_row, "거래�?, "client_name") or get_val(mat_row, "거래처명", None)
                            if client_name_val:
                                client_name_str = str(client_name_val).strip()
                                client_id = client_map_by_name.get(client_name_str)
                                if not client_id:
                                    # ?�름?�로??거래처�? 찾을 ???�으�??�로 ?�성 (?�업?�번???�이)
                                    new_client = Client(
                                        name=client_name_str, 
                                        business_number=None, 
                                        is_active=True,
                                        client_type='?�료' # 공급처이므�??�?�을 '?�료'�?지??
                                    )
                                    session.add(new_client)
                                    session.flush()
                                    client_id = new_client.id
                                    # ?�로 ?�성???�라?�언?��? ?�름 맵에 추�??�여 중복 ?�성??방�??�니??
                                    client_map_by_name[client_name_str] = client_id
                                    new_clients_count += 1
                                    print(f"  ??거래�??�성 (?�름�?: {client_name_str} -> ID {client_id}")
                                else:
                                    print(f"  거래�?매칭 ?�공 (?�름): {client_name_str} -> ID {client_id}")
                        
                        material.supplier_id = client_id
                        
                        material.manufacturer = get_val(mat_row, "?�조?�명", "manufacturer") or ""
                        material.hs_code = get_val(mat_row, "HS CODE", "hs_code") or ""
                        material.origin = get_val(mat_row, "?�산지", "origin") or ""
                        material.name_en = get_val(mat_row, "?�문?�료�?, "name_en") or ""
                        material.nmpa_reg_num = get_val(mat_row, "NMPA?�록번호", "nmpa_reg_num") or ""
                        
                        # ?�용?��? 처리
                        is_active_val = get_val(mat_row, "?�용?��?(Y/N)", "is_active") or "Y"
                        material.is_active = str(is_active_val).upper() in ["Y", "TRUE", "1", "YES"]

                        # 기존 ?�성�???�� (?�로???�성분으�??�체하�??�해)
                        material.ingredients.clear()
                        
                        processed_materials[code] = material
                        materials_count += 1
                        
                    except Exception as e:
                        print(f"?�료 {i+1} 처리 �??�류: {e}")
                        continue

                # ?�션 ?�러?�하???�료 ID ?�성
                session.flush()
                print(f"?�료 처리 ?�료: {materials_count}�? ??거래�? {new_clients_count}�?)

                # 2?�계: ?�성�??�보 처리 (기존 로직�??�일)
                ingredient_groups = {}
                
                for i, ing_row in enumerate(ingredients_data):
                    try:
                        material_code = get_val(ing_row, "?�료코드", "material_code")
                        if not material_code:
                            print(f"?�성�?{i+1}: ?�료코드가 ?�어??건너?�")
                            continue
                        
                        material_code = str(material_code).strip()
                        if material_code not in processed_materials:
                            print(f"?�성�?{i+1}: ?�료코드 '{material_code}'???�당?�는 ?�료�?찾을 ???�음")
                            continue
                        
                        if material_code not in ingredient_groups:
                            ingredient_groups[material_code] = []
                        
                        ingredient_data = {
                            'name_ko': get_val(ing_row, "?��??�성�?, "name_ko") or "",
                            'name_en': get_val(ing_row, "INGREDIENT", "name_en") or "",
                            'cas_no': get_val(ing_row, "CAS NO.", "cas_no") or "",
                            'function': get_val(ing_row, "기능", "function") or "",
                            'ewg_grade': get_val(ing_row, "EWG?�급", "ewg_grade") or "",
                            'ewg_data': get_val(ing_row, "EWG?�급?�이??, "ewg_data") or "",
                            'hs_code': get_val(ing_row, "HS CODE", "hs_code") or "",
                            'nmpa_reg_num': get_val(ing_row, "NMPA?�록번호", "nmpa_reg_num") or "",
                            'remark': get_val(ing_row, "비고", "remark") or ""
                        }                        
                        
                        # 조성�?처리
                        composition_ratio_val = get_val(ing_row, "조성�?%)", "composition_ratio")
                        try:
                            ingredient_data['composition_ratio'] = float(composition_ratio_val) if composition_ratio_val else 0.0
                        except (ValueError, TypeError):
                            ingredient_data['composition_ratio'] = 0.0
                        
                        ingredient_groups[material_code].append(ingredient_data)
                        
                    except Exception as e:
                        print(f"?�성�?{i+1} 처리 �??�류: {e}")
                        continue
                
                # ?�료별로 ?�성�?추�?
                for material_code, ingredients_list in ingredient_groups.items():
                    try:
                        parent_material = processed_materials[material_code]
                        print(f"?�료 '{material_code}'??{len(ingredients_list)}개의 ?�성�?추�?")
                        
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
                        print(f"?�료 '{material_code}' ?�성�?추�? �??�류: {e}")
                        continue

                # ?�이?�베?�스 커밋
                session.commit()
                
                # ?�공 메시지
                success_msg = f"?�이??가?�오�??�료!\n?�료: {materials_count}�?n?�성�? {ingredients_count}�?n??거래�? {new_clients_count}�?
                messagebox.showinfo("?�공", success_msg)
                print(success_msg)

                # 모든 DB ?�업???�난 ??UI ?�로고침
                self.bulk_importing = False
                self.refresh_data() # UI ?�체 ?�로고침?�로 변�?

            except Exception as e:
                session.rollback()
                error_msg = f"가?�오�?�??�류 발생: {str(e)}"
                print(f"?�류 ?�세: {e}")
                import traceback
                traceback.print_exc()
                messagebox.showerror("?�이?�베?�스 ?�류", error_msg)
                self.bulk_importing = False # ?�류 발생 ?�에???�래�??�제
                
            finally:
                session.close()
                
        except Exception as e:
            error_msg = f"?�일 처리 �??�류 발생: {str(e)}"
            print(f"?�일 ?�류 ?�세: {e}")
            messagebox.showerror("?�일 ?�류", error_msg)
            self.bulk_importing = False # ?�류 발생 ?�에???�래�??�제
        
        # DB ?�기??기�????�데?�트 �?체크 ?�시??
        if hasattr(self.app, 'update_db_sync_baseline'):
            # 즉시 기�????�데?�트 (?�체 변경사??반영)
            self.app.update_db_sync_baseline()
            
        if sync_was_running and hasattr(self.app, 'start_db_sync_check'):
            # 3�??�에 ?�기??체크 ?�시??(DB 변경사???�정???��?
            self.app.after(3000, lambda: (
                print("[?�료가?�오�? DB ?�기??체크 ?�시??),
                self.app.start_db_sync_check()
            ))
        
        print("import_material_data ?�료")

    def reset_material_search(self):
        """?�료 검?�창??초기?�하�??�체 목록???�시 불러?�니??"""
        self.material_search_entry.delete(0, "end")
        self.load_materials()

    def on_material_search(self, event=None):
        """검?�창 ?�력 ???�바?�싱???�용?�여 검?�을 ?�행?�니??"""
        if self.search_timer:
            self.after_cancel(self.search_timer)
        # 500ms(0.5�? ?�에 load_materials ?�수�??�행
        self.search_timer = self.after(500, self.load_materials)

    def load_materials(self):
        """DB?�서 ?�료 목록??검?�하??Treeview???�시?�니??"""
        search_term = self.material_search_entry.get().strip()
        # 검???�에???�성분도 ?�께 검?�하?�록 search_ingredients=True�?변경합?�다.
        # 목록 ?�시?�는 ?�성�??�용???�요 ?�으므�?load_ingredients=False???��??�니??
        materials = db_manager.search_materials(search_term, load_ingredients=False, search_ingredients=True)
        
        # 1. UI ?�더�??�능 최적?? ?�이?��? 먼�? 메모리에 리스?�로 준�?
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

            # 2. Treeview�???번에 ?�데?�트
            # 기존 ??�� 모두 ??��
            for item in self.material_tree.get_children():
                self.material_tree.delete(item)
            # 메모리에 준비된 ?�이?�로 Treeview 채우�?
            for values, tag in material_data_list:
                self.material_tree.insert("", "end", tags=(tag,), values=values)

        except Exception as e:
            print(f"?�료 목록 로드 �??�류 발생: {e}")

    def load_clients_to_combobox(self):
        """거래�??�보�?콤보박스?� ?�동?�성??로드?�니?? - 개선??버전"""
        # ?�??가?�오�?중일 ?�는 불필?�한 ?�출 방�?
        if getattr(self, "bulk_importing", False):
            print("?�??가?�오�?중이므�?콤보박스 ?�데?�트 건너?�")
            return
        
        session = db_manager.get_session()
        session = self.db_manager.get_session()
        try:
            # '?�료' ?�?�의 ?�성 거래처만 불러?�니??
            suppliers = session.query(Client).filter_by(is_active=True, client_type='?�료').all()
            
            # 거래�?매핑 ?�셔?�리 ?�성
            self.supplier_map = {s.name: s.id for s in suppliers}  # ?�름 -> ID
            self.supplier_id_map = {s.id: s.name for s in suppliers}  # ID -> ?�름
            
            supplier_names = list(self.supplier_map.keys())
            
            print(f"로드??공급�??? {len(suppliers)}")
            
            # AutocompleteEntry??거래�?목록 ?�정 (?�류 ?�정)
            if hasattr(self, 'supplier_entry'):
                self.supplier_entry.set_completion_list(supplier_names)
                print(f"AutocompleteEntry??{len(supplier_names)}�?공급�??�정 ?�료")

        except Exception as e:
            print(f"거래�?로드 �??�류: {e}")
            import traceback
            traceback.print_exc()
        finally:
            session.close()

    def on_material_tree_select(self, event):
        """?�료 ?�리뷰에????�� ?�택 ???�출?�는 메서??- 개선??버전"""
        # ?�??가?�오�?중이�?차단 (콤보박스 ?�데?�트 방�?)
        if getattr(self, "bulk_importing", False):
            print("?�??가?�오�?중이므�??�리 ?�택 ?�벤??무시")
            return
            
        if not hasattr(self, "supplier_entry"):
            return

        selected_item = self.material_tree.selection()
        if not selected_item:
            return

        mat_id = self.material_tree.item(selected_item[0], "values")[0]
        self._selected_material_id = mat_id

        # db_manager.search_materials?�서 ?��? client?� ingredients�?로드?�으므�?
        # ?�기?�는 DB???�시 ?�근???�요 ?�이 ?�리뷰의 값을 ?�용?�니??
        # ?? ?�리뷰에 모든 ?�보가 ?�을 ???�으므�? ?�세 ?�보??DB?�서 ?�시 가?�옵?�다.
        session = db_manager.get_session()
        try:
            material = session.query(Material).options(
                joinedload(Material.ingredients),
                joinedload(Material.supplier)
            ).filter_by(id=mat_id).first()
            if not material:
                print(f"?�료 ID {mat_id}�?찾을 ???�습?�다.")
                return

            # 비�?리자??경우, ?�을 채우�??�에 ?�력 ?�드�??�시?�으�??�성??
            if not self.current_user.is_admin:
                for entry in self.material_entries.values():
                    entry.configure(state="normal")
                for entry in self.ingredient_entries.values():
                    entry.configure(state="normal")

            print(f"?�택???�료: {material.name} (코드: {material.code})")

            # 기본 ?�료 ?�보 ??초기??
            for key, entry in self.material_entries.items():
                if isinstance(entry, ctk.CTkComboBox):
                    entry.set("")
                else:
                    entry.delete(0, "end")

            # ?�료 기본 ?�보 ?�력
            self.material_entries["코드"].insert(0, material.code or "")
            self.material_entries["?�료�?].insert(0, material.name or "")
            self.material_entries["?�문?�료�?].insert(0, material.name_en or "")
            self.material_entries["?��?"].insert(0, str(material.unit_price or 0.0))
            self.material_entries["?�장?�위"].insert(0, material.package_unit or "")
            self.material_entries["?�조?�명"].insert(0, material.manufacturer or "")
            self.material_entries["HS CODE"].insert(0, material.hs_code or "")
            self.material_entries["?�산지"].insert(0, material.origin or "")
            self.material_entries["NMPA?�록번호"].insert(0, material.nmpa_reg_num or "")
            self.material_entries["?�록??].insert(0, material.reg_date or "")

            # 거래�??�보 처리 (개선??버전)
            supplier_name = ""
            if material.supplier:
                supplier_name = material.supplier.name
            elif hasattr(self, 'supplier_id_map') and material.supplier_id in self.supplier_id_map:
                supplier_name = self.supplier_id_map.get(material.supplier_id, "")
            
            # 거래�??�력 ?�드???�정
            self.supplier_entry.delete(0, "end")
            if supplier_name:
                self.supplier_entry.insert(0, supplier_name)

            # ?�용?��? 체크박스 ?�정
            self.material_active_var.set("on" if material.is_active else "off")

            # ?�력 보기 버튼 ?�성??
            self.material_history_button.configure(state="normal")
            # ?�성�??�보�?temp_ingredients??복사
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
            
            print(f"temp_ingredients???�?�된 ?�성�?개수: {len(self.temp_ingredients)}")
            
            # 비�?리자??경우, ?�을 채운 ???�시 모든 ?�드�?비활?�화
            if not self.current_user.is_admin:
                for entry in self.material_entries.values():
                    entry.configure(state="readonly")
                for entry in self.ingredient_entries.values():
                    entry.configure(state="readonly")

        except Exception as e:
            print(f"?�료 ?�택 처리 �??�류: {e}")
            import traceback
            traceback.print_exc()
            messagebox.showerror("?�이?�베?�스 ?�류", f"?�료 ?�보 로드 �??�류 발생: {e}")
            return
            
        finally:
            session.close()
        
        # ?�션???�힌 ?�에 UI ?�데?�트 (메모리의 ?�이???�용)
        try:
            self.refresh_ingredient_tree()
            self.clear_ingredient_form()
            
        except Exception as e:
            print(f"UI ?�데?�트 �??�류: {e}")
            messagebox.showerror("UI ?�류", f"?�면 ?�데?�트 �??�류 발생: {e}")

    def refresh_ingredient_tree(self):
        """
        ?�성�??�리뷰�? ?�로고침?�니??
        - ?�정: 기존 ??��??먼�? ??��?�여 UI 불일�?문제�??�결?�니??
        """
        try:
            # 기존 ??��??모두 ??��
            for item in self.ingredient_tree.get_children(): 
                self.ingredient_tree.delete(item)
            
            print(f"?�리�??�로고침: {len(self.temp_ingredients)}�??�성�??�시")
            
            # temp_ingredients??모든 ??��???�리뷰에 추�?
            for i, ing in enumerate(self.temp_ingredients):
                tag = 'oddrow' if i % 2 == 0 else 'evenrow'
                # 컬럼 ?�정???�라 값을 ?�적?�로 구성
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
                print(f"  {i+1}. {ing.get('name_ko', '')} ({ing.get('name_en', '')}) 추�???)
                
            print(f"?�리�??�로고침 ?�료: �?{len(self.ingredient_tree.get_children())}�???�� ?�시")
            
        except Exception as e:
            print(f"?�리�??�로고침 �??�류: {e}")
            import traceback
            traceback.print_exc()

    def _setup_treeview_columns(self, treeview, columns_config):
        """Treeview??컬럼�??�더�??�정?�고 초기 가?�성???�용?�니??"""
        treeview.configure(columns=list(columns_config.keys()))
        for col_id, config in columns_config.items():
            treeview.heading(col_id, text=config["text"])
            treeview.column(col_id, width=config["width"], anchor=config.get("anchor", "w"))
        
        visible_columns = [col_id for col_id, config in columns_config.items() if config.get("visible", True)]
        treeview.configure(displaycolumns=visible_columns)


    def debug_material_ingredients(self, material_id):
        """?�정 ?�료???�성분을 직접 DB?�서 조회?�여 ?�인"""
        session = db_manager.get_session()
        try:
            # Material 조회
            material = session.query(Material).filter_by(id=material_id).first()
            if not material:
                print(f"?�료 ID {material_id}�?찾을 ???�습?�다.")
                return
            
            print(f"?�료: {material.name} (코드: {material.code})")
            print(f"?�결???�성�?개수: {len(material.ingredients)}")
            
            # �??�성�??�보 출력
            for i, ing in enumerate(material.ingredients):
                print(f"  {i+1}. {ing.name_ko} ({ing.name_en}) - CAS: {ing.cas_no}")
            
            # 직접 SQL 쿼리로도 ?�인
            from database.models import Ingredient
            direct_ingredients = session.query(Ingredient).filter_by(material_id=material_id).all()
            print(f"직접 쿼리 결과 ?�성�?개수: {len(direct_ingredients)}")
            
            for i, ing in enumerate(direct_ingredients):
                print(f"  직접쿼리 {i+1}. {ing.name_ko} ({ing.name_en}) - CAS: {ing.cas_no}")
                
        except Exception as e:
            print(f"?�버�?�??�류: {e}")
        finally:
            session.close()
            # UI 리프?�시
            self.clear_material_form()
            self.load_materials()

    def _update_visible_columns(self, treeview, columns_config):
        """체크박스 ?�태???�라 Treeview???�을 ?�데?�트?�니??"""
        visible_columns = [col_id for col_id, config in columns_config.items() if config.get("variable") and config["variable"].get()]
        # ID ?��? ??�� ?�겨???�어???��?�? visible_columns???�함?��? ?�도�??�니??
        if 'id' not in visible_columns:
            treeview.configure(displaycolumns=visible_columns)

    def on_ingredient_tree_select(self, event):
        selected_item = self.ingredient_tree.selection()
        if not selected_item: return
        
        ing_id_val = self.ingredient_tree.item(selected_item[0], "values")[self.get_column_index("id")]
        if str(ing_id_val).isdigit():
            ing_id = int(ing_id_val)
        else:
            ing_id = ing_id_val

        self._selected_ingredient_id = ing_id
        selected_ing = next((ing for ing in self.temp_ingredients if ing.get("id") == ing_id), None)
        if not selected_ing: return
        
        # 비�?리자??경우, ?�을 채우�??�에 ?�력 ?�드�??�시?�으�??�성??
        if not self.current_user.is_admin:
            for entry in self.ingredient_entries.values():
                entry.configure(state="normal")

        for key, entry in self.ingredient_entries.items(): entry.delete(0, "end")
        self.ingredient_entries["?��??�성�?].insert(0, selected_ing.get("name_ko", ""))
        self.ingredient_entries["INGREDIENT"].insert(0, selected_ing.get("name_en", ""))
        self.ingredient_entries["CAS NO."].insert(0, selected_ing.get("cas_no", ""))
        self.ingredient_entries["조성�?%)"].insert(0, str(selected_ing.get("composition_ratio", "")))
        self.ingredient_entries["기능"].insert(0, selected_ing.get("function", ""))
        self.ingredient_entries["EWG?�급"].insert(0, selected_ing.get("ewg_grade", ""))
        self.ingredient_entries["EWG?�급?�이??].insert(0, selected_ing.get("ewg_data", ""))
        self.ingredient_entries["비고"].insert(0, selected_ing.get("remark", ""))

        # 비�?리자??경우, ?�을 채운 ???�시 모든 ?�드�?비활?�화
        if not self.current_user.is_admin:
            for entry in self.ingredient_entries.values():
                entry.configure(state="readonly")

    def get_column_index(self, col_name):
        """?�정??컬럼 리스?�에???�정 컬럼???�덱?��? 반환?�니??"""
        return list(self.ing_cols_config.keys()).index(col_name)



    def clear_material_form(self):
        self._selected_material_id = None
        # 비�?리자??경우, ?�을 지?�기 ?�에 ?�력 ?�드�??�시?�으�??�성??
        if not self.current_user.is_admin:
            for entry in self.material_entries.values():
                entry.configure(state="normal")
            for entry in self.ingredient_entries.values():
                entry.configure(state="normal")
        for entry in self.material_entries.values():
            if isinstance(entry, ctk.CTkComboBox):
                if entry.cget("values"):
                    entry.set(entry.cget("values")[0])
            else:
                entry.delete(0, "end")
        
        today_date = datetime.now().strftime("%Y-%m-%d")
        self.material_entries["?�록??].insert(0, today_date)

        self.material_active_var.set("on")
        self.temp_ingredients = []
        self.material_history_button.configure(state="disabled")

        self.clear_ingredient_form()
        if self.material_tree.selection(): 
            self.material_tree.selection_remove(self.material_tree.selection()[0])
        # 비�?리자??경우, ?�을 지?????�시 모든 ?�드�?비활?�화
        if not self.current_user.is_admin:
            for entry in self.material_entries.values():
                entry.configure(state="readonly")
            for entry in self.ingredient_entries.values():
                entry.configure(state="readonly")
        
        self.refresh_ingredient_tree()

    def clear_ingredient_form(self):
        self._selected_ingredient_id = None
        for entry in self.ingredient_entries.values(): 
            entry.delete(0, "end")
        if self.ingredient_tree.selection(): 
            self.ingredient_tree.selection_remove(self.ingredient_tree.selection()[0])

    def add_ingredient(self):
        # ?�집 권한 ?�인
        if not self.can_edit_data():
            messagebox.showwarning("권한 ?�류", "?�분 ?�이?��? ?�집??권한???�습?�다.\n?�재 권한?�로??조회�?가?�합?�다.")
            return
            
        try:
            ratio = float(self.ingredient_entries["조성�?%)"].get()) if self.ingredient_entries["조성�?%)"].get() else 0.0
        except (ValueError, TypeError):
            messagebox.showwarning("?�력 ?�류", "조성비는 ?�자�??�력 가?�합?�다.")
            return

        temp_id = (max([ing.get("id", 0) for ing in self.temp_ingredients if isinstance(ing.get("id"), int)] + [0]) + 1)
        
        new_ingredient = {
            "id": temp_id,
            "name_ko": self.ingredient_entries["?��??�성�?].get(), 
            "name_en": self.ingredient_entries["INGREDIENT"].get(), 
            "cas_no": self.ingredient_entries["CAS NO."].get(),
            "composition_ratio": ratio, 
            "function": self.ingredient_entries["기능"].get(),
            "ewg_grade": self.ingredient_entries["EWG?�급"].get(),
            "ewg_data": self.ingredient_entries["EWG?�급?�이??].get(),
            "remark": self.ingredient_entries["비고"].get()
        }
        self.temp_ingredients.append(new_ingredient)
        self.refresh_ingredient_tree()
        self.clear_ingredient_form()

    def update_ingredient(self):
        # ?�집 권한 ?�인
        if not self.can_edit_data():
            messagebox.showwarning("권한 ?�류", "?�분 ?�이?��? ?�집??권한???�습?�다.\n?�재 권한?�로??조회�?가?�합?�다.")
            return
            
        if self._selected_ingredient_id is None:
            messagebox.showwarning("?�택 ?�류", "?�정???�성분을 목록?�서 ?�택?�세??")
            return
        
        selected_ing = next((ing for ing in self.temp_ingredients if ing.get("id") == self._selected_ingredient_id), None)
        if not selected_ing: return

        try:
            ratio = float(self.ingredient_entries["조성�?%)"].get()) if self.ingredient_entries["조성�?%)"].get() else 0.0
        except (ValueError, TypeError):
            messagebox.showwarning("?�력 ?�류", "조성비는 ?�자�??�력 가?�합?�다.")
            return

        selected_ing["name_ko"] = self.ingredient_entries["?��??�성�?].get()
        selected_ing["name_en"] = self.ingredient_entries["INGREDIENT"].get()
        selected_ing["cas_no"] = self.ingredient_entries["CAS NO."].get()
        selected_ing["composition_ratio"] = ratio
        selected_ing["function"] = self.ingredient_entries["기능"].get()
        selected_ing["ewg_grade"] = self.ingredient_entries["EWG?�급"].get()
        selected_ing["ewg_data"] = self.ingredient_entries["EWG?�급?�이??].get()
        selected_ing["remark"] = self.ingredient_entries["비고"].get()
        
        self.refresh_ingredient_tree()
        self.clear_ingredient_form()

    def remove_ingredient(self):
        # ?�집 권한 ?�인
        if not self.can_edit_data():
            messagebox.showwarning("권한 ?�류", "?�분 ?�이?��? ?�집??권한???�습?�다.\n?�재 권한?�로??조회�?가?�합?�다.")
            return
            
        if self._selected_ingredient_id is None:
            messagebox.showwarning("?�택 ?�류", "??��???�성분을 목록?�서 ?�택?�세??")
            return
        
        self.temp_ingredients = [ing for ing in self.temp_ingredients if ing.get("id") != self._selected_ingredient_id]
        self.refresh_ingredient_tree()
        self.clear_ingredient_form()

    def save_material(self):
        # ?�집 권한 ?�인
        if not self.can_edit_data():
            messagebox.showwarning("권한 ?�류", "?�분 ?�이?��? ?�집??권한???�습?�다.\n?�재 권한?�로??조회�?가?�합?�다.")
            return
            
        code = self.material_entries["코드"].get().strip()
        name = self.material_entries["?�료�?].get().strip()

        # ?�수�??�인
        if not code or not name:
            messagebox.showwarning("?�력 ?�류", "코드?� ?�료명�? ?�수?�니??")
            return

        log_entries = []
        log_action = ""
        new_is_active = self.material_active_var.get() == "on"
        session = db_manager.get_session()
        try:
            material = None
            if self._selected_material_id:
                material = session.query(Material).filter_by(id=self._selected_material_id).first()

            # 코드 중복 검??(?�규 ?�는 코드 변�???
            # 1. ?�규 ?�????(material is None)
            # 2. ?�정 ??코드가 변경된 경우 (material.code != code)
            if material is None or material.code != code:
                existing = session.query(Material).filter_by(code=code).first()
                if existing:
                    messagebox.showerror("?�???�류", f"코드 '{code}'???��? 존재?�는 ?�료 코드?�니??")
                    return

            if material: # ?�정 모드
                log_action = "?�보 ?�정"
            else: # ?�규 ?�성 모드
                log_action = "?�규 ?�성"
                material = Material()
                session.add(material)

            supplier_name_input = self.supplier_entry.get().strip()
            new_supplier_id = self.supplier_map.get(supplier_name_input)

            # --- 변�??�항 로깅 ---
            if log_action == "?�규 ?�성":
                log_action = "?�규 ?�성"
                log_entries.append(f"코드: '{code}'")
                log_entries.append(f"?�료�? '{name}'")
                log_entries.append(f"?�문?�료�? '{self.material_entries['?�문?�료�?].get()}'")
                log_entries.append(f"?��?: '{self.material_entries['?��?'].get() or '0.0'}'")
                log_entries.append(f"?�장?�위: '{self.material_entries['?�장?�위'].get()}'")
                log_entries.append(f"공급�? '{supplier_name_input}'")
                log_entries.append(f"?�조?�명: '{self.material_entries['?�조?�명'].get()}'")
                log_entries.append(f"HS CODE: '{self.material_entries['HS CODE'].get()}'")
                log_entries.append(f"?�산지: '{self.material_entries['?�산지'].get()}'")
                log_entries.append(f"?�문?�료�? '{self.material_entries['?�문?�료�?].get()}'")
                log_entries.append(f"NMPA?�록번호: '{self.material_entries['NMPA?�록번호'].get()}'")
                log_entries.append(f"?�록?? '{self.material_entries['?�록??].get()}'") # ??부분�? 로그 기록?��?�?그�?�??�니??
                log_entries.append(f"?�용 ?��?: '{self.material_active_var.get() == 'on'}'")
                for temp_ing in self.temp_ingredients:
                    log_entries.append(f"?�성�?추�?: {temp_ing['name_ko']} ({temp_ing['name_en']}) - {temp_ing['composition_ratio']}%")
            else: # ?�정
                log_action = "?�보 ?�정"
                def log_change(field_name, old_val, new_val):
                    if old_val != new_val:
                        log_entries.append(f"{field_name}: '{old_val}' -> '{new_val}'")

                log_change("코드", material.code or "", code)
                log_change("?�료�?, material.name or "", name)
                log_change("?�문?�료�?, material.name_en or "", self.material_entries["?�문?�료�?].get())
                log_change("?��?", str(material.unit_price or 0.0), self.material_entries["?��?"].get() or "0.0")
                log_change("?�장?�위", material.package_unit or "", self.material_entries["?�장?�위"].get())
                
                if material.supplier_id != new_supplier_id:
                    old_supplier_name = self.supplier_id_map.get(material.supplier_id, "")
                    log_entries.append(f"공급�? '{old_supplier_name}' -> '{supplier_name_input}'")

                log_change("?�조?�명", material.manufacturer or "", self.material_entries["?�조?�명"].get())
                log_change("HS CODE", material.hs_code or "", self.material_entries["HS CODE"].get())
                log_change("?�산지", material.origin or "", self.material_entries["?�산지"].get())
                log_change("?�문?�료�?, material.name_en or "", self.material_entries["?�문?�료�?].get())
                log_change("NMPA?�록번호", material.nmpa_reg_num or "", self.material_entries["NMPA?�록번호"].get())
                log_change("?�록??, material.reg_date or "", self.material_entries["?�록??].get())
                
                if material.is_active != new_is_active:
                    log_entries.append(f"?�용 ?��?: '{material.is_active}' -> '{new_is_active}'")

                # ?�성�?변�?로깅
                old_ingredients = {ing.id: ing for ing in material.ingredients}
                new_ingredients_map = {ing.get('id'): ing for ing in self.temp_ingredients if isinstance(ing.get('id'), int)}

                # ??��???�성�?
                for old_id, old_ing in old_ingredients.items():
                    if old_id not in new_ingredients_map:
                        log_entries.append(f"?�성�???��: {old_ing.name_ko} ({old_ing.name_en})")

                # 추�?/?�정???�성�?
                for temp_ing in self.temp_ingredients:
                    ing_id = temp_ing.get('id')
                    if isinstance(ing_id, int) and ing_id in old_ingredients: # ?�정
                        old_ing = old_ingredients[ing_id]
                        # ?�세 ?�드 비교 로직 추�? 가??(?? ?�량, ?�름 ??
                        if old_ing.composition_ratio != temp_ing['composition_ratio']:
                            log_entries.append(f"?�성�??�량 변�?- {temp_ing['name_ko']}: {old_ing.composition_ratio}% -> {temp_ing['composition_ratio']}%")
                    else: # 추�?
                        log_entries.append(f"?�성�?추�?: {temp_ing['name_ko']} ({temp_ing['name_en']}) - {temp_ing['composition_ratio']}%")

            # 공통 ?�드 ?�??
            material.code = code
            material.name = name
            material.name_en = self.material_entries["?�문?�료�?].get()
            material.unit_price = float(self.material_entries["?��?"].get() or 0.0)
            material.package_unit = self.material_entries["?�장?�위"].get()
            material.supplier_id = new_supplier_id
            material.manufacturer = self.material_entries["?�조?�명"].get()
            material.hs_code = self.material_entries["HS CODE"].get()
            material.origin = self.material_entries["?�산지"].get()
            material.name_en = self.material_entries["?�문?�료�?].get()
            material.nmpa_reg_num = self.material_entries["NMPA?�록번호"].get()
            material.reg_date = self.material_entries["?�록??].get() or datetime.now().strftime("%Y-%m-%d") # ?�록?�이 비어?�으�??�재 ?�짜�??�??
            material.is_active = new_is_active

            # 기존 ?�분 ??�� ???�로 추�?
            material.ingredients.clear()
            session.flush()
            
            if log_entries:
                timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                log_header = f"[{timestamp}] by {self.current_user.username} - {log_action}"
                log_message = f"{log_header}\n- " + "\n- ".join(log_entries)
                material.change_log = (material.change_log + "\n\n" if material.change_log else "") + log_message

            for ing_data in self.temp_ingredients:
                material.ingredients.append(Ingredient(
                    name_ko=ing_data["name_ko"],
                    name_en=ing_data["name_en"],
                    cas_no=ing_data["cas_no"],
                    composition_ratio=ing_data["composition_ratio"],
                    function=ing_data["function"],
                    ewg_grade=ing_data["ewg_grade"],
                    ewg_data=ing_data.get("ewg_data"),
                    remark=ing_data.get("remark")
                ))

            session.commit()
            messagebox.showinfo("?�공", "?�료 ?�보가 ?�?�되?�습?�다.")

        except Exception as e:
            session.rollback()
            messagebox.showerror("?�이?�베?�스 ?�류", f"?�??�??�류 발생: {e}")
        finally:
            session.close()
            self.clear_material_form()
            self.load_materials()

    def show_selected_material_history(self):
        if not self._selected_material_id:
            messagebox.showwarning("?�류", "?�료�?먼�? ?�택?�주?�요.", parent=self)
            return
        session = db_manager.get_session()
        material = session.query(Material).filter_by(id=self._selected_material_id).first()
        session.close()
        if material:
            HistoryPopup(self, f"'{material.name}' 변�??�력", [material], item_name_key='name', item_code_key='code')

    def show_all_material_history(self):
        session = db_manager.get_session()
        all_materials = session.query(Material).all()
        session.close()
        if not all_materials:
            messagebox.showinfo("?�보", "조회???�료가 ?�습?�다.", parent=self)
            return
        HistoryPopup(self, "?�체 ?�분 변�??�력", all_materials, item_name_key='name', item_code_key='code')
            # ?�?????�규 모드 ?�제
        self.is_new_mode = False # ------------------------------------------------------------------------

    def delete_material(self):
        # ?�집 권한 ?�인
        if not self.can_edit_data():
            messagebox.showwarning("권한 ?�류", "?�분 ?�이?��? ?�집??권한???�습?�다.\n?�재 권한?�로??조회�?가?�합?�다.")
            return
            
        if not self._selected_material_id:
            messagebox.showwarning("?�택 ?�류", "??��???�료�?목록?�서 ?�택?�세??")
            return
        if not messagebox.askyesno("??�� ?�인", "?�말�??�택???�료�???��?�시겠습?�까? 모든 ?�위 ?�성�??�보???�께 ??��?�니??"):
            return
        
        session = db_manager.get_session()
        try:
            mat_to_delete = session.query(Material).filter_by(id=self._selected_material_id).first()
            if mat_to_delete:
                session.delete(mat_to_delete)
                session.commit()
                messagebox.showinfo("?�공", "?�료가 ??��?�었?�니??")
        except Exception as e:
            session.rollback()
            messagebox.showerror("?�이?�베?�스 ?�류", f"??�� �??�류 발생: {e}")
        finally:
            session.close()
            self.clear_material_form()
            self.load_materials()

# modules/material_management.py
import customtkinter as ctk
import tkinter as tk
from tkinter import ttk, messagebox
from database.db_manager import db_manager
from database.models import Material, Ingredient, Client
import modules.excel_handler as excel_handler
from datetime import datetime
from modules.history_popup import HistoryPopup
from utils.autocomplete import AutocompleteEntry

class MaterialManagementFrame(ctk.CTkFrame):
    def __init__(self, master, user):
        super().__init__(master)
        
        self.current_user = user
        self.db_manager = db_manager
        self.temp_ingredients = []
        self._selected_material_id = None
        self._selected_ingredient_id = None
        self.is_new_mode = True
        self.bulk_importing = False
        
        # 탭 뷰가 필요 없으므로, UI를 프레임에 직접 구성합니다.
        self.setup_data_management_tab(self)

        self.refresh_data()

    def get_client_list(self, db_manager):
        return [row[0] for row in db_manager.get_all_clients()]

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
                
    def setup_data_management_tab(self, tab_frame):
        """원료 데이터 관리 UI를 설정합니다."""

        # ===== 탭 전체 그리드 구조 =====
        tab_frame.grid_columnconfigure(0, weight=1, minsize=450)  # 좌측 폼
        tab_frame.grid_columnconfigure(1, weight=0)               # 가운데 조절바
        tab_frame.grid_columnconfigure(2, weight=2, minsize=600)  # 우측 리스트
        tab_frame.grid_rowconfigure(0, weight=1)

        # ===== 좌측: 원료 입력 폼 =====
        self.form_container = ctk.CTkScrollableFrame(tab_frame, label_text="원료 정보 입력")
        self.form_container.grid(row=0, column=0, padx=(0, 0), pady=0, sticky="nsew")
        self.form_container.grid_columnconfigure(0, weight=0)
        self.form_container.grid_columnconfigure(1, weight=1)  # 입력 필드 가변

        material_labels = ["코드", "원료명", "단가", "포장단위", "거래처", "제조원명", "HS CODE", "NMPA등록번호", "등록일"]
        self.material_entries = {}
        for i, text in enumerate(material_labels):
            ctk.CTkLabel(self.form_container, text=text).grid(row=i, column=0, padx=10, pady=5, sticky="w")
            if text == "거래처":
                self.client_entry = AutocompleteEntry(self.form_container)
                self.client_entry.grid(row=i, column=1, padx=10, pady=5, sticky="ew")
                self.material_entries[text] = self.client_entry
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

        ctk.CTkLabel(ingredient_frame, text="전성분 목록", font=ctk.CTkFont(weight="bold")).grid(
            row=0, column=0, columnspan=2, pady=5
        )

        ing_tree_cols = ("id", "name_ko", "name_en", "cas_no", "ratio", "function", "hs_code", "nmpa_reg_num", "remark")
        self.ingredient_tree = ttk.Treeview(ingredient_frame, columns=ing_tree_cols, show="headings", height=5)
        col_settings = {
            "id": (40, "center"), "name_ko": (100, "w"), "name_en": (100, "w"),
            "cas_no": (80, "w"), "ratio": (60, "e"), "function": (80, "w"),
            "hs_code": (80, "w"), "nmpa_reg_num": (100, "w"), "remark": (100, "w")
        }
        for col, (w, anchor) in col_settings.items():
            self.ingredient_tree.heading(col, text=col.upper() if col != "name_ko" else "한글전성분")
            self.ingredient_tree.column(col, width=w, anchor=anchor)

        self.ingredient_tree.grid(row=1, column=0, columnspan=2, padx=5, pady=5, sticky="nsew")
        self.ingredient_tree.bind("<<TreeviewSelect>>", self.on_ingredient_tree_select)
        ing_labels = ["한글전성분", "INGREDIENT", "CAS NO.", "조성비(%)", "기능", "EWG등급", "EWG등급데이터", "HS CODE", "NMPA등록번호", "비고"]
        self.ingredient_entries = {}
        for i, text in enumerate(ing_labels):
            ctk.CTkLabel(ingredient_frame, text=text).grid(row=i+2, column=0, padx=5, pady=2, sticky="w")
            entry = ctk.CTkEntry(ingredient_frame)
            entry.grid(row=i+2, column=1, padx=5, pady=2, sticky="ew")
            self.ingredient_entries[text] = entry

        ing_button_frame = ctk.CTkFrame(ingredient_frame, fg_color="transparent")
        ing_button_frame.grid(row=len(ing_labels)+2, column=1, pady=5, sticky="e")
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
        main_button_frame.grid(row=len(material_labels)+3, column=0, columnspan=2, pady=10)
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
        
        ctk.CTkLabel(list_header_frame, text="원료 목록", font=ctk.CTkFont(size=14, weight="bold")).pack(side="left")
        
        # 오른쪽 정렬을 위한 버튼/검색 프레임
        right_header_frame = ctk.CTkFrame(list_header_frame, fg_color="transparent")
        right_header_frame.pack(side="right")

        ctk.CTkButton(right_header_frame, text="전체 이력 조회", command=self.show_all_material_history).pack(side="left", padx=5)
        ctk.CTkLabel(right_header_frame, text="검색:").pack(side="left", padx=(10, 5))

        self.material_search_entry = ctk.CTkEntry(right_header_frame, width=150)
        self.material_search_entry.pack(side="left", fill="x", expand=True)
        self.material_search_entry.bind("<KeyRelease>", lambda e: self.load_materials())
        ctk.CTkButton(right_header_frame, text="초기화", width=60, command=self.reset_material_search).pack(side="left", padx=5)
        ctk.CTkButton(right_header_frame, text="데이터 내보내기", command=self.export_material_data).pack(side="left", padx=5)
        self.excel_import_button = ctk.CTkButton(right_header_frame, text="데이터 가져오기", command=self.import_material_data)
        self.excel_import_button.pack(side="left", padx=5)

        # 비관리자 접근 제한
        if not self.current_user.is_admin:
            self.material_active_var.set("off")
            self.form_container.configure(label_text="원료 정보 조회 (관리자만 수정 가능)")
            # 모든 버튼 비활성화
            for btn in [self.material_history_button,
                self.ing_add_button, self.ing_update_button, self.ing_remove_button, self.mat_save_button,
                self.mat_new_button, self.mat_delete_button, self.excel_import_button
            ]:
                btn.configure(state="disabled")
            # 모든 입력 필드 비활성화
            for entry in self.material_entries.values():
                entry.configure(state="readonly")
            for entry in self.ingredient_entries.values():
                entry.configure(state="readonly")

        # ===== 원료 목록 트리뷰 =====        
        # 트리뷰 생성
        mat_tree_cols = ("id", "code", "name", "unit_price", "package_unit", "client", "manufacturer", "hs_code", "nmpa_reg_num")
        self.material_tree = ttk.Treeview(list_frame, columns=mat_tree_cols, show="headings", selectmode="browse")
        
        # 컬럼 설정
        self.material_tree.heading("id", text="ID");                self.material_tree.column("id", width=40, anchor="center")
        self.material_tree.heading("code", text="코드");            self.material_tree.column("code", width=100, anchor="w")
        self.material_tree.heading("name", text="원료명");          self.material_tree.column("name", width=200, anchor="w")
        self.material_tree.heading("unit_price", text="단가");       self.material_tree.column("unit_price", width=80, anchor="e")
        self.material_tree.heading("package_unit", text="포장단위"); self.material_tree.column("package_unit", width=80, anchor="center")
        self.material_tree.heading("client", text="거래처");        self.material_tree.column("client", width=150, anchor="w")
        self.material_tree.heading("manufacturer", text="제조원명"); self.material_tree.column("manufacturer", width=150, anchor="w")
        self.material_tree.heading("hs_code", text="HS CODE");      self.material_tree.column("hs_code", width=100, anchor="w")
        self.material_tree.heading("nmpa_reg_num", text="NMPA등록번호"); self.material_tree.column("nmpa_reg_num", width=120, anchor="w")

        # 배치
        self.material_tree.grid(row=1, column=0, sticky="nsew", padx=(10, 0), pady=(0, 10))

        # 스크롤바
        scrollbar = ttk.Scrollbar(list_frame, orient="vertical", command=self.material_tree.yview)
        self.material_tree.configure(yscrollcommand=scrollbar.set)
        scrollbar.grid(row=1, column=1, sticky="ns", pady=(0, 10))

        # 선택 이벤트 바인딩
        self.material_tree.bind("<<TreeviewSelect>>", self.on_material_tree_select)
                               
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
            
        mat_headers = ["코드", "원료명", "단가", "포장단위", "거래처", "제조원명", "HS CODE", "NMPA등록번호", "등록일", "사용여부"]
        mat_rows = []
        for mat in materials:
            client_name = session.query(Client.name).filter_by(id=mat.client_id).scalar() or ""
            mat_rows.append((
                mat.code, mat.name, mat.unit_price, mat.package_unit, client_name,
                mat.manufacturer, mat.hs_code, mat.nmpa_reg_num, mat.reg_date, "Y" if mat.is_active else "N"
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
        # 대량 가져오기 시작
        self.bulk_importing = True
        
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
                """행에서 한글키 또는 영문키로 값을 가져옵니다."""
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
                
                # 처리될 재료들을 저장할 딕셔너리
                processed_materials = {}
                materials_count = 0
                ingredients_count = 0
                new_clients_count = 0
                
                print(f"가져올 재료 데이터: {len(materials_data)}개")
                print(f"가져올 전성분 데이터: {len(ingredients_data)}개")
                
                # 1단계: 재료 정보 처리 (개선된 거래처 처리 포함)
                for i, mat_row in enumerate(materials_data):
                    try:
                        code = get_val(mat_row, "코드", "code")
                        if not code:
                            print(f"재료 {i+1}: 코드가 없어서 건너뜀")
                            continue
                        
                        # 기존 재료 찾기 또는 새로 생성
                        material = session.query(Material).filter_by(code=code).first()
                        if not material:
                            material = Material(code=code)
                            session.add(material)
                            print(f"새 재료 생성: {code}")
                        else:
                            print(f"기존 재료 업데이트: {code}")

                        # 재료 기본 정보 설정
                        material.name = get_val(mat_row, "원료명", "name") or ""
                        
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
                                new_client = Client(name=str(client_name_val).strip(), business_number=biz_num_str, is_active=True)
                                session.add(new_client)
                                session.flush()
                                client_id = new_client.id
                                client_map_by_biz_num[biz_num_str] = client_id
                                client_map_by_name[str(client_name_val).strip()] = client_id
                                new_clients_count += 1
                                print(f"  새 거래처 생성 (사업자번호 기준): {client_name_val} ({biz_num_str}) -> ID {client_id}")
                            else:
                                print(f"  거래처 매칭 성공 (사업자번호): {biz_num_str} -> ID {client_id}")

                        # 2순위: '거래처사업자번호'가 없을 경우, '거래처명'으로 찾기
                        else:
                            client_name_val = get_val(mat_row, "거래처", "client_name") # 내보내기 헤더와 키 맞춤
                            if client_name_val:
                                client_name_str = str(client_name_val).strip()
                                client_id = client_map_by_name.get(client_name_str)
                                if not client_id:
                                    # 이름으로도 거래처를 찾을 수 없으면 새로 생성 (사업자번호 없이)
                                    new_client = Client(name=client_name_str, business_number=None, is_active=True)
                                    session.add(new_client)
                                    session.flush()
                                    client_id = new_client.id
                                    client_map_by_name[client_name_str] = client_id
                                    new_clients_count += 1
                                    print(f"  새 거래처 생성 (이름만): {client_name_str} -> ID {client_id}")
                                else:
                                    print(f"  거래처 매칭 성공 (이름): {client_name_str} -> ID {client_id}")
                        
                        material.client_id = client_id
                        
                        material.manufacturer = get_val(mat_row, "제조원명", "manufacturer") or ""
                        material.hs_code = get_val(mat_row, "HS CODE", "hs_code") or ""
                        material.nmpa_reg_num = get_val(mat_row, "NMPA등록번호", "nmpa_reg_num") or ""
                        material.reg_date = get_val(mat_row, "등록일", "reg_date") or ""
                        
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
                
                # 재료별로 전성분 추가
                for material_code, ingredients_list in ingredient_groups.items():
                    try:
                        parent_material = processed_materials[material_code]
                        print(f"재료 '{material_code}'에 {len(ingredients_list)}개의 전성분 추가")
                        
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
                        print(f"재료 '{material_code}' 전성분 추가 중 오류: {e}")
                        continue

                # 데이터베이스 커밋
                session.commit()
                
                # 성공 메시지
                success_msg = f"데이터 가져오기 완료!\n재료: {materials_count}개\n전성분: {ingredients_count}개\n새 거래처: {new_clients_count}개"
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
        
        print("import_material_data 완료")

    def reset_material_search(self):
        """원료 검색창을 초기화하고 전체 목록을 다시 불러옵니다."""
        self.material_search_entry.delete(0, "end")
        self.load_materials()

    def load_materials(self):
        """DB에서 원료 목록을 검색하여 Treeview에 표시합니다."""
        for item in self.material_tree.get_children(): self.material_tree.delete(item)
        
        search_term = self.material_search_entry.get().strip()
        materials = db_manager.search_materials(search_term)
        
        session = db_manager.get_session() # client_name을 가져오기 위해 세션 사용
        for i, mat in enumerate(materials):
            client_name = session.query(Client.name).filter_by(id=mat.client_id).scalar() or ""
            tag = 'oddrow' if i % 2 == 0 else 'evenrow'
            self.material_tree.insert("", "end", tags=(tag,), values=(
                mat.id, 
                mat.code,
                mat.name, 
                mat.unit_price, 
                mat.package_unit, 
                client_name, 
                mat.manufacturer, 
                mat.hs_code, 
                mat.nmpa_reg_num
            ))
        session.close()

    def load_clients_to_combobox(self):
        """거래처 정보를 콤보박스와 자동완성에 로드합니다. - 개선된 버전"""
        # 대량 가져오기 중일 때는 불필요한 호출 방지
        if getattr(self, "bulk_importing", False):
            print("대량 가져오기 중이므로 콤보박스 업데이트 건너뜀")
            return
        
        session = db_manager.get_session()
        try:
            clients = session.query(Client).filter_by(is_active=True).all()
            
            # 거래처 매핑 딕셔너리 생성
            self.client_map = {client.name: client.id for client in clients}  # 이름 -> ID
            self.client_id_map = {client.id: client.name for client in clients}  # ID -> 이름
            
            client_names = list(self.client_map.keys())
            
            print(f"로드된 거래처 수: {len(clients)}")
            
            # AutocompleteEntry에 거래처 목록 설정 (오류 수정)
            if hasattr(self, 'material_entries') and '거래처' in self.material_entries:
                client_widget = self.material_entries['거래처']
                if isinstance(client_widget, AutocompleteEntry):
                    client_widget.set_completion_list(client_names)
                    print(f"AutocompleteEntry에 {len(client_names)}개 거래처 설정 완료")
        except Exception as e:
            print(f"거래처 로드 중 오류: {e}")
            import traceback
            traceback.print_exc()
        finally:
            session.close()

    def on_material_tree_select(self, event):
        """재료 트리뷰에서 항목 선택 시 호출되는 메서드 - 개선된 버전"""
        # 대량 가져오기 중이면 차단 (콤보박스 업데이트 방지)
        if getattr(self, "bulk_importing", False):
            print("대량 가져오기 중이므로 트리 선택 이벤트 무시")
            return
            
        if not hasattr(self, "client_entry"):
            return

        selected_item = self.material_tree.selection()
        if not selected_item:
            return

        mat_id = self.material_tree.item(selected_item[0], "values")[0]
        self._selected_material_id = mat_id

        session = db_manager.get_session()
        try:
            # SQLAlchemy의 joinedload를 사용하여 한 번의 쿼리로 재료와 모든 전성분을 함께 로드
            from sqlalchemy.orm import joinedload
            
            material = session.query(Material).options(
                joinedload(Material.ingredients),
                joinedload(Material.client)
            ).filter_by(id=mat_id).first()
            
            if not material:
                print(f"재료 ID {mat_id}를 찾을 수 없습니다.")
                return

            # 비관리자일 경우, 폼을 채우기 전에 입력 필드를 일시적으로 활성화
            if not self.current_user.is_admin:
                for entry in self.material_entries.values():
                    entry.configure(state="normal")
                for entry in self.ingredient_entries.values():
                    entry.configure(state="normal")


            print(f"선택된 재료: {material.name} (코드: {material.code})")

            # 기본 재료 정보 폼 초기화
            for key, entry in self.material_entries.items():
                if isinstance(entry, ctk.CTkComboBox):
                    entry.set("")
                else:
                    entry.delete(0, "end")

            # 재료 기본 정보 입력
            self.material_entries["코드"].insert(0, material.code or "")
            self.material_entries["원료명"].insert(0, material.name or "")
            self.material_entries["단가"].insert(0, str(material.unit_price or 0.0))
            self.material_entries["포장단위"].insert(0, material.package_unit or "")
            self.material_entries["제조원명"].insert(0, material.manufacturer or "")
            self.material_entries["HS CODE"].insert(0, material.hs_code or "")
            self.material_entries["NMPA등록번호"].insert(0, material.nmpa_reg_num or "")
            self.material_entries["등록일"].insert(0, material.reg_date or "")

            # 거래처 정보 처리 (개선된 버전)
            client_name = ""
            if material.client_id:
                # 1순위: 조인된 client 객체에서 가져오기
                if material.client and hasattr(material.client, 'name'):
                    client_name = material.client.name
                    print(f"거래처 이름 (join): {client_name}")
                # 2순위: client_id_map에서 가져오기
                elif hasattr(self, 'client_id_map') and material.client_id in self.client_id_map:
                    client_name = self.client_id_map[material.client_id]
                    print(f"거래처 이름 (map): {client_name}")
                # 3순위: 직접 DB에서 조회
                else:
                    client = session.query(Client).filter_by(id=material.client_id).first()
                    if client:
                        client_name = client.name
                        print(f"거래처 이름 (direct query): {client_name}")
                    else:
                        print(f"거래처 ID {material.client_id}에 해당하는 거래처를 찾을 수 없음")
            
            # 거래처 입력 필드에 설정
            self.client_entry.delete(0, "end")
            if client_name:
                self.client_entry.insert(0, client_name)

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
                    "hs_code": ing.hs_code or "",
                    "nmpa_reg_num": ing.nmpa_reg_num or "",
                    "remark": ing.remark or ""
                }
                self.temp_ingredients.append(ingredient_data)
            
            print(f"temp_ingredients에 저장된 전성분 개수: {len(self.temp_ingredients)}")
            
            # 비관리자일 경우, 폼을 채운 후 다시 모든 필드를 비활성화
            if not self.current_user.is_admin:
                for entry in self.material_entries.values():
                    entry.configure(state="readonly")
                for entry in self.ingredient_entries.values():
                    entry.configure(state="readonly")

        except Exception as e:
            print(f"재료 선택 처리 중 오류: {e}")
            import traceback
            traceback.print_exc()
            messagebox.showerror("데이터베이스 오류", f"재료 정보 로드 중 오류 발생: {e}")
            return
            
        finally:
            session.close()
        
        # 세션이 닫힌 후에 UI 업데이트 (메모리의 데이터 사용)
        try:
            self.refresh_ingredient_tree()
            self.clear_ingredient_form()
            
        except Exception as e:
            print(f"UI 업데이트 중 오류: {e}")
            messagebox.showerror("UI 오류", f"화면 업데이트 중 오류 발생: {e}")

    def refresh_ingredient_tree(self):
        """전성분 트리뷰를 새로고침합니다."""
        try:
            # 기존 항목들 모두 삭제
            for item in self.ingredient_tree.get_children(): 
                self.ingredient_tree.delete(item)
            
            print(f"트리뷰 새로고침: {len(self.temp_ingredients)}개 전성분 표시")
            
            # temp_ingredients의 모든 항목을 트리뷰에 추가
            for i, ing in enumerate(self.temp_ingredients):
                tag = 'oddrow' if i % 2 == 0 else 'evenrow'
                values = (
                    ing.get("id", f"temp_{i}"), 
                    ing.get("name_ko", ""), 
                    ing.get("name_en", ""), 
                    ing.get("cas_no", ""),
                    ing.get("composition_ratio", ""),
                    ing.get("function", ""),
                    ing.get("ewg_grade", ""),
                    ing.get("hs_code", ""),
                    ing.get("nmpa_reg_num", ""),
                    ing.get("remark", "")
                )
                
                item_id = self.ingredient_tree.insert("", "end", tags=(tag,), values=values)
                print(f"  {i+1}. {ing.get('name_ko', '')} ({ing.get('name_en', '')}) 추가됨")
                
            print(f"트리뷰 새로고침 완료: 총 {len(self.ingredient_tree.get_children())}개 항목 표시")
            
        except Exception as e:
            print(f"트리뷰 새로고침 중 오류: {e}")
            import traceback
            traceback.print_exc()

    def debug_material_ingredients(self, material_id):
        """특정 재료의 전성분을 직접 DB에서 조회하여 확인"""
        session = db_manager.get_session()
        try:
            # Material 조회
            material = session.query(Material).filter_by(id=material_id).first()
            if not material:
                print(f"재료 ID {material_id}를 찾을 수 없습니다.")
                return
            
            print(f"재료: {material.name} (코드: {material.code})")
            print(f"연결된 전성분 개수: {len(material.ingredients)}")
            
            # 각 전성분 정보 출력
            for i, ing in enumerate(material.ingredients):
                print(f"  {i+1}. {ing.name_ko} ({ing.name_en}) - CAS: {ing.cas_no}")
            
            # 직접 SQL 쿼리로도 확인
            from database.models import Ingredient
            direct_ingredients = session.query(Ingredient).filter_by(material_id=material_id).all()
            print(f"직접 쿼리 결과 전성분 개수: {len(direct_ingredients)}")
            
            for i, ing in enumerate(direct_ingredients):
                print(f"  직접쿼리 {i+1}. {ing.name_ko} ({ing.name_en}) - CAS: {ing.cas_no}")
                
        except Exception as e:
            print(f"디버깅 중 오류: {e}")
        finally:
            session.close()
            # UI 리프레시
            self.clear_material_form()
            self.load_materials()

    def on_ingredient_tree_select(self, event):
        selected_item = self.ingredient_tree.selection()
        if not selected_item: return
        
        ing_id_val = self.ingredient_tree.item(selected_item[0], "values")[0]
        if str(ing_id_val).isdigit():
            ing_id = int(ing_id_val)
        else:
            ing_id = ing_id_val

        self._selected_ingredient_id = ing_id
        selected_ing = next((ing for ing in self.temp_ingredients if ing.get("id") == ing_id), None)
        if not selected_ing: return
        
        # 비관리자일 경우, 폼을 채우기 전에 입력 필드를 일시적으로 활성화
        if not self.current_user.is_admin:
            for entry in self.ingredient_entries.values():
                entry.configure(state="normal")

        for key, entry in self.ingredient_entries.items(): entry.delete(0, "end")
        self.ingredient_entries["한글전성분"].insert(0, selected_ing.get("name_ko", ""))
        self.ingredient_entries["INGREDIENT"].insert(0, selected_ing.get("name_en", ""))
        self.ingredient_entries["CAS NO."].insert(0, selected_ing.get("cas_no", ""))
        self.ingredient_entries["조성비(%)"].insert(0, str(selected_ing.get("composition_ratio", "")))
        self.ingredient_entries["기능"].insert(0, selected_ing.get("function", ""))
        self.ingredient_entries["EWG등급"].insert(0, selected_ing.get("ewg_grade", ""))
        self.ingredient_entries["EWG등급데이터"].insert(0, selected_ing.get("ewg_data", ""))
        self.ingredient_entries["HS CODE"].insert(0, selected_ing.get("hs_code", ""))
        self.ingredient_entries["NMPA등록번호"].insert(0, selected_ing.get("nmpa_reg_num", ""))
        self.ingredient_entries["비고"].insert(0, selected_ing.get("remark", ""))

        # 비관리자일 경우, 폼을 채운 후 다시 모든 필드를 비활성화
        if not self.current_user.is_admin:
            for entry in self.ingredient_entries.values():
                entry.configure(state="readonly")

    

    def clear_material_form(self):
        self._selected_material_id = None
        # 비관리자일 경우, 폼을 지우기 전에 입력 필드를 일시적으로 활성화
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
        self.material_entries["등록일"].insert(0, today_date)

        self.material_active_var.set("on")
        self.temp_ingredients = []
        self.material_history_button.configure(state="disabled")

        self.clear_ingredient_form()
        if self.material_tree.selection(): 
            self.material_tree.selection_remove(self.material_tree.selection()[0])
        # 비관리자일 경우, 폼을 지운 후 다시 모든 필드를 비활성화
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
        try:
            ratio = float(self.ingredient_entries["조성비(%)"].get()) if self.ingredient_entries["조성비(%)"].get() else 0.0
        except (ValueError, TypeError):
            messagebox.showwarning("입력 오류", "조성비는 숫자만 입력 가능합니다.")
            return

        temp_id = (max([ing.get("id", 0) for ing in self.temp_ingredients if isinstance(ing.get("id"), int)] + [0]) + 1)
        
        new_ingredient = {
            "id": temp_id,
            "name_ko": self.ingredient_entries["한글전성분"].get(), 
            "name_en": self.ingredient_entries["INGREDIENT"].get(), 
            "cas_no": self.ingredient_entries["CAS NO."].get(),
            "composition_ratio": ratio, 
            "function": self.ingredient_entries["기능"].get(),
            "ewg_grade": self.ingredient_entries["EWG등급"].get(),
            "ewg_data": self.ingredient_entries["EWG등급데이터"].get(),
            "hs_code": self.ingredient_entries["HS CODE"].get(),
            "nmpa_reg_num": self.ingredient_entries["NMPA등록번호"].get(),
            "remark": self.ingredient_entries["비고"].get()
        }
        self.temp_ingredients.append(new_ingredient)
        self.refresh_ingredient_tree()
        self.clear_ingredient_form()

    def update_ingredient(self):
        if self._selected_ingredient_id is None:
            messagebox.showwarning("선택 오류", "수정할 전성분을 목록에서 선택하세요.")
            return
        
        selected_ing = next((ing for ing in self.temp_ingredients if ing.get("id") == self._selected_ingredient_id), None)
        if not selected_ing: return

        try:
            ratio = float(self.ingredient_entries["조성비(%)"].get()) if self.ingredient_entries["조성비(%)"].get() else 0.0
        except (ValueError, TypeError):
            messagebox.showwarning("입력 오류", "조성비는 숫자만 입력 가능합니다.")
            return

        selected_ing["name_ko"] = self.ingredient_entries["한글전성분"].get()
        selected_ing["name_en"] = self.ingredient_entries["INGREDIENT"].get()
        selected_ing["cas_no"] = self.ingredient_entries["CAS NO."].get()
        selected_ing["composition_ratio"] = ratio
        selected_ing["function"] = self.ingredient_entries["기능"].get()
        selected_ing["ewg_grade"] = self.ingredient_entries["EWG등급"].get()
        selected_ing["ewg_data"] = self.ingredient_entries["EWG등급데이터"].get()
        selected_ing["hs_code"] = self.ingredient_entries["HS CODE"].get()
        selected_ing["nmpa_reg_num"] = self.ingredient_entries["NMPA등록번호"].get()
        selected_ing["remark"] = self.ingredient_entries["비고"].get()
        
        self.refresh_ingredient_tree()
        self.clear_ingredient_form()

    def remove_ingredient(self):
        if self._selected_ingredient_id is None:
            messagebox.showwarning("선택 오류", "삭제할 전성분을 목록에서 선택하세요.")
            return
        
        self.temp_ingredients = [ing for ing in self.temp_ingredients if ing.get("id") != self._selected_ingredient_id]
        self.refresh_ingredient_tree()
        self.clear_ingredient_form()

    def save_material(self):
        code = self.material_entries["코드"].get().strip()
        name = self.material_entries["원료명"].get().strip()

        # 필수값 확인
        if not code or not name:
            messagebox.showwarning("입력 오류", "코드와 원료명은 필수입니다.")
            return

        log_entries = []
        log_action = ""
        new_is_active = self.material_active_var.get() == "on" # 변수를 미리 선언
        session = db_manager.get_session()
        try:
            # 수정 모드: 선택된 ID가 있고, 폼의 코드와 선택된 코드의 DB 정보가 일치할 때
            if self._selected_material_id:
                material = session.query(Material).filter_by(id=self._selected_material_id).first()
                if not material:
                    messagebox.showerror("오류", "선택된 원료를 찾을 수 없습니다.")
                    return
                # 코드가 변경되었는지 확인
                if material.code != code:
                    # 코드를 변경하려고 하면 중복 체크
                    if session.query(Material).filter_by(code=code).first():
                        messagebox.showerror("저장 오류", "변경하려는 코드가 이미 존재합니다.")
                        return
            # 신규 등록 모드
            else:
                # 코드 중복 체크
                if session.query(Material).filter_by(code=code).first():
                    messagebox.showerror("저장 오류", "이미 존재하는 코드입니다.")
                    return
                material = Material()
                session.add(material)

            client_name_input = self.client_entry.get().strip()
            new_client_id = self.client_map.get(client_name_input)

            # --- 변경 사항 로깅 ---
            if not material.id: # 신규 생성
                log_action = "신규 생성"
                log_entries.append(f"코드: '{code}'")
                log_entries.append(f"원료명: '{name}'")
                log_entries.append(f"단가: '{self.material_entries['단가'].get() or '0.0'}'")
                log_entries.append(f"포장단위: '{self.material_entries['포장단위'].get()}'")
                log_entries.append(f"거래처: '{client_name_input}'")
                log_entries.append(f"제조원명: '{self.material_entries['제조원명'].get()}'")
                log_entries.append(f"HS CODE: '{self.material_entries['HS CODE'].get()}'")
                log_entries.append(f"NMPA등록번호: '{self.material_entries['NMPA등록번호'].get()}'")
                log_entries.append(f"등록일: '{self.material_entries['등록일'].get()}'")
                log_entries.append(f"사용 여부: '{self.material_active_var.get() == 'on'}'")
                for temp_ing in self.temp_ingredients:
                    log_entries.append(f"전성분 추가: {temp_ing['name_ko']} ({temp_ing['name_en']}) - {temp_ing['composition_ratio']}%")
            else: # 수정
                log_action = "정보 수정"
                def log_change(field_name, old_val, new_val):
                    if old_val != new_val:
                        log_entries.append(f"{field_name}: '{old_val}' -> '{new_val}'")

                log_change("코드", material.code or "", code)
                log_change("원료명", material.name or "", name)
                log_change("단가", str(material.unit_price or 0.0), self.material_entries["단가"].get() or "0.0")
                log_change("포장단위", material.package_unit or "", self.material_entries["포장단위"].get())
                
                if material.client_id != new_client_id:
                    old_client_name = self.client_id_map.get(material.client_id, "")
                    log_entries.append(f"거래처: '{old_client_name}' -> '{client_name_input}'")

                log_change("제조원명", material.manufacturer or "", self.material_entries["제조원명"].get())
                log_change("HS CODE", material.hs_code or "", self.material_entries["HS CODE"].get())
                log_change("NMPA등록번호", material.nmpa_reg_num or "", self.material_entries["NMPA등록번호"].get())
                log_change("등록일", material.reg_date or "", self.material_entries["등록일"].get())
                
                if material.is_active != new_is_active:
                    log_entries.append(f"사용 여부: '{material.is_active}' -> '{new_is_active}'")

                # 전성분 변경 로깅
                old_ingredients = {ing.id: ing for ing in material.ingredients}
                new_ingredients_map = {ing.get('id'): ing for ing in self.temp_ingredients if isinstance(ing.get('id'), int)}

                # 삭제된 전성분
                for old_id, old_ing in old_ingredients.items():
                    if old_id not in new_ingredients_map:
                        log_entries.append(f"전성분 삭제: {old_ing.name_ko} ({old_ing.name_en})")

                # 추가/수정된 전성분
                for temp_ing in self.temp_ingredients:
                    ing_id = temp_ing.get('id')
                    if isinstance(ing_id, int) and ing_id in old_ingredients: # 수정
                        old_ing = old_ingredients[ing_id]
                        # 상세 필드 비교 로직 추가 가능 (예: 함량, 이름 등)
                        if old_ing.composition_ratio != temp_ing['composition_ratio']:
                            log_entries.append(f"전성분 함량 변경 - {temp_ing['name_ko']}: {old_ing.composition_ratio}% -> {temp_ing['composition_ratio']}%")
                    else: # 추가
                        log_entries.append(f"전성분 추가: {temp_ing['name_ko']} ({temp_ing['name_en']}) - {temp_ing['composition_ratio']}%")

            # 공통 필드 저장
            material.code = code
            material.name = name
            material.unit_price = float(self.material_entries["단가"].get() or 0.0)
            material.package_unit = self.material_entries["포장단위"].get()
            material.client_id = new_client_id
            material.manufacturer = self.material_entries["제조원명"].get()
            material.hs_code = self.material_entries["HS CODE"].get()
            material.nmpa_reg_num = self.material_entries["NMPA등록번호"].get()
            material.reg_date = self.material_entries["등록일"].get()
            material.is_active = new_is_active

            # 기존 성분 삭제 후 새로 추가
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
                    hs_code=ing_data.get("hs_code"),
                    nmpa_reg_num=ing_data.get("nmpa_reg_num"),
                    remark=ing_data.get("remark")
                ))

            session.commit()
            messagebox.showinfo("성공", "원료 정보가 저장되었습니다.")

        except Exception as e:
            session.rollback()
            messagebox.showerror("데이터베이스 오류", f"저장 중 오류 발생: {e}")
        finally:
            session.close()
            self.clear_material_form()
            self.load_materials()

    def show_selected_material_history(self):
        if not self._selected_material_id:
            messagebox.showwarning("오류", "원료를 먼저 선택해주세요.", parent=self)
            return
        session = db_manager.get_session()
        material = session.query(Material).filter_by(id=self._selected_material_id).first()
        session.close()
        if material:
            HistoryPopup(self, f"'{material.name}' 변경 이력", [material], item_name_key='name', item_code_key='code')

    def show_all_material_history(self):
        session = db_manager.get_session()
        all_materials = session.query(Material).all()
        session.close()
        if not all_materials:
            messagebox.showinfo("정보", "조회할 원료가 없습니다.", parent=self)
            return
        HistoryPopup(self, "전체 성분 변경 이력", all_materials, item_name_key='name', item_code_key='code')
            # 저장 후 신규 모드 해제
        self.is_new_mode = False # ------------------------------------------------------------------------

    def delete_material(self):
        if not self._selected_material_id:
            messagebox.showwarning("선택 오류", "삭제할 원료를 목록에서 선택하세요.")
            return
        if not messagebox.askyesno("삭제 확인", "정말로 선택한 원료를 삭제하시겠습니까? 모든 하위 전성분 정보도 함께 삭제됩니다."):
            return
        
        session = db_manager.get_session()
        try:
            mat_to_delete = session.query(Material).filter_by(id=self._selected_material_id).first()
            if mat_to_delete:
                session.delete(mat_to_delete)
                session.commit()
                messagebox.showinfo("성공", "원료가 삭제되었습니다.")
        except Exception as e:
            session.rollback()
            messagebox.showerror("데이터베이스 오류", f"삭제 중 오류 발생: {e}")
        finally:
            session.close()
            self.clear_material_form()
            self.load_materials()
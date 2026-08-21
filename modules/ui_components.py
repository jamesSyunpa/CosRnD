# modules/ui_components.py
import customtkinter as ctk
import tkinter as tk
from tkinter import ttk, messagebox
import json
from database.db_manager import db_manager
from modules.translation import get_texts

class ModernInfoDialog(ctk.CTkToplevel):
    """시스템 다크/라이트 테마를 완벽하게 추종하는 모던 안내 대화상자"""
    def __init__(self, master, title="안내", message="", width=520, height=430):
        super().__init__(master)
        self.withdraw()
        self.title(title)
        self.geometry(f"{width}x{height}")
        self.resizable(False, False)
        self.transient(master)
        self.grab_set()

        main_frame = ctk.CTkFrame(self, corner_radius=10)
        main_frame.pack(padx=16, pady=16, fill="both", expand=True)

        # 상단 타이틀
        top_frame = ctk.CTkFrame(main_frame, fg_color="transparent")
        top_frame.pack(fill="x", padx=16, pady=(16, 10))
        
        icon_label = ctk.CTkLabel(top_frame, text="💡", font=ctk.CTkFont(size=22))
        icon_label.pack(side="left", padx=(0, 10))
        
        title_label = ctk.CTkLabel(top_frame, text=title, font=ctk.CTkFont(size=16, weight="bold"))
        title_label.pack(side="left")

        # 본문 메시지 텍스트박스 (다크/라이트 테마 완벽 대응)
        textbox = ctk.CTkTextbox(
            main_frame, 
            wrap="word", 
            font=ctk.CTkFont(size=13),
            fg_color=("white", "#2B2B2B"),
            text_color=("black", "#F3F4F6"),
            border_width=1,
            border_color=("gray80", "#3E3E3E"),
            corner_radius=8
        )
        textbox.pack(padx=16, pady=(0, 14), fill="both", expand=True)
        textbox.insert("1.0", message)
        textbox.configure(state="disabled")

        # 하단 닫기 버튼
        close_btn = ctk.CTkButton(
            main_frame, 
            text="확인", 
            width=100, 
            height=32,
            font=ctk.CTkFont(size=13, weight="bold"),
            command=self.destroy
        )
        close_btn.pack(pady=(0, 14))

        # 부모 중앙 배치
        self.update_idletasks()
        try:
            parent = master
            if parent:
                parent_x = parent.winfo_rootx()
                parent_y = parent.winfo_rooty()
                parent_w = parent.winfo_width()
                parent_h = parent.winfo_height()
                win_w = self.winfo_width()
                win_h = self.winfo_height()
                x = parent_x + (parent_w - win_w) // 2
                y = parent_y + (parent_h - win_h) // 2
                self.geometry(f"+{x}+{y}")
        except Exception:
            pass
        self.deiconify()

class HelpPopup(ctk.CTkToplevel):
    """도움말 내용을 표시하는 스크롤 가능한 팝업 창"""
    def __init__(self, master, title, message):
        super().__init__(master)
        self.withdraw()  # 초기 렌더링 랙 방지
        self.texts = get_texts(master.language if hasattr(master, 'language') else 'korean')
        self.title(title)
        self.geometry("600x450")

        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(0, weight=1)

        scrollable_frame = ctk.CTkScrollableFrame(self, label_text=self.texts['help'])
        scrollable_frame.grid(row=0, column=0, padx=15, pady=15, sticky="nsew")

        label = ctk.CTkLabel(scrollable_frame, text=message, justify="left", anchor="nw")
        label.pack(padx=10, pady=10, fill="both", expand=True)

        close_button = ctk.CTkButton(self, text=self.texts['close'], command=self.destroy)
        close_button.grid(row=1, column=0, padx=15, pady=(0, 15))

        # 메인 창 중앙에 배치 후 deiconify
        self.update_idletasks()
        parent = master
        if parent:
            parent_x = parent.winfo_rootx()
            parent_y = parent.winfo_rooty()
            parent_w = parent.winfo_width()
            parent_h = parent.winfo_height()
            win_w = self.winfo_width()
            win_h = self.winfo_height()
            x = parent_x + (parent_w - win_w) // 2
            y = parent_y + (parent_h - win_h) // 2
            self.geometry(f"+{x}+{y}")
        self.deiconify()

class CustomErrorDialog(ctk.CTkToplevel):
    """'클립보드로 복사' 기능이 포함된 커스텀 오류 대화상자"""
    def __init__(self, master, title="오류", error_message=""):
        super().__init__(master)
        self.withdraw()  # 초기 렌더링 랙 방지
        self.title(title)
        self.resizable(False, False)

        self.error_message = str(error_message)

        main_frame = ctk.CTkFrame(self)
        main_frame.pack(padx=20, pady=20, fill="both", expand=True)

        # 상단 메시지
        top_frame = ctk.CTkFrame(main_frame, fg_color="transparent")
        top_frame.pack(pady=(0, 10), padx=10, fill="x")
        icon_label = ctk.CTkLabel(top_frame, text="❌", font=ctk.CTkFont(size=24))
        icon_label.pack(side="left", padx=(0, 10))
        message_label = ctk.CTkLabel(top_frame, text="오류가 발생했습니다.", font=ctk.CTkFont(size=16, weight="bold"))
        message_label.pack(side="left")

        # 오류 상세 내용
        self.error_textbox = ctk.CTkTextbox(main_frame, height=150, wrap="word")
        self.error_textbox.pack(pady=10, padx=10, fill="both", expand=True)
        self.error_textbox.insert("1.0", self.error_message)
        self.error_textbox.configure(state="disabled")

        # 하단 버튼
        button_frame = ctk.CTkFrame(main_frame, fg_color="transparent")
        button_frame.pack(pady=(10, 0), padx=10, fill="x")

        close_button = ctk.CTkButton(button_frame, text="닫기", command=self.destroy)
        close_button.pack(side="right")

        copy_button = ctk.CTkButton(button_frame, text="클립보드로 복사", command=self.copy_to_clipboard)
        copy_button.pack(side="right", padx=10)

        # 메인 창 중앙에 배치 후 deiconify
        self.update_idletasks()
        parent = master
        if parent:
            parent_x = parent.winfo_rootx()
            parent_y = parent.winfo_rooty()
            parent_w = parent.winfo_width()
            parent_h = parent.winfo_height()
            win_w = self.winfo_width()
            win_h = self.winfo_height()
            x = parent_x + (parent_w - win_w) // 2
            y = parent_y + (parent_h - win_h) // 2
            self.geometry(f"+{x}+{y}")
        self.deiconify()

    def copy_to_clipboard(self):
        self.clipboard_clear()
        self.clipboard_append(self.error_message)
        messagebox.showinfo("복사 완료", "오류 메시지가 클립보드에 복사되었습니다.", parent=self)

class CustomDropdown(ctk.CTkFrame):
    """[v64 네이티브 초고속 콤보박스] 팝업 렉 없이 즉각 반응하고 타이핑 검색 및 선택 완벽 보장"""
    def __init__(self, master, values=None, command=None, width=150, **kwargs):
        super().__init__(master, fg_color="transparent", width=width)
        self.raw_values = list(values) if values else []
        self.command = command
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(0, weight=1)

        self.combobox = ctk.CTkComboBox(
            self,
            values=self.raw_values if self.raw_values else ["- 선택 -"],
            command=self._on_combo_change,
            width=width,
            height=28
        )
        self.combobox.grid(row=0, column=0, sticky="ew")

        # [요청 반영] 텍스트창 수정 클릭/포커스 시 전체 텍스트 자동 선택
        self._bind_auto_select_all()

    def _bind_auto_select_all(self):
        """내부 Entry 위젯에 포커스/클릭 시 전체 선택 바인딩"""
        try:
            entry_widget = getattr(self.combobox, '_entry', None)
            if entry_widget:
                entry_widget.bind("<FocusIn>", self._select_all_text, add="+")
                entry_widget.bind("<Button-1>", self._select_all_text_on_click, add="+")
        except Exception:
            pass

    def _select_all_text(self, event=None):
        try:
            entry_widget = getattr(self.combobox, '_entry', None)
            if entry_widget:
                entry_widget.after(10, lambda: entry_widget.select_range(0, 'end'))
        except Exception:
            pass

    def _select_all_text_on_click(self, event=None):
        try:
            entry_widget = getattr(self.combobox, '_entry', None)
            if entry_widget:
                # 마우스 클릭 후 커서가 풀리지 않도록 비동기 20ms 후 전체 선택 실행
                entry_widget.after(20, lambda: entry_widget.select_range(0, 'end'))
        except Exception:
            pass

    def _on_combo_change(self, value):
        if self.command:
            self.command(value)

    def set(self, value):
        self.combobox.set(value)

    def get(self):
        return self.combobox.get()

    def configure(self, **kwargs):
        if 'values' in kwargs:
            vals = kwargs.pop('values')
            self.raw_values = list(vals) if vals else []
            self.combobox.configure(values=self.raw_values)
        if 'state' in kwargs:
            self.combobox.configure(state=kwargs.pop('state'))
        if kwargs:
            super().configure(**kwargs)

class AddMaterialDialog(ctk.CTkToplevel):
    """처방에 원료를 추가하기 위한 팝업창"""
    def __init__(self, master, on_add_callback, on_line_break_callback):
        import re
        super().__init__(master)
        self.withdraw()  # 초기 렌더링 랙 방지
        self.on_add_callback = on_add_callback
        self.on_line_break_callback = on_line_break_callback

        self.language = master.language
        self.texts = get_texts(self.language)
        self.title(self.texts['add_material_title'])
        self.geometry("600x500")

        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(1, weight=1)
        self.search_timer = None # 검색 디바운싱을 위한 타이머

        # --- 검색 프레임 ---
        search_frame = ctk.CTkFrame(self, fg_color="transparent")
        search_frame.grid(row=0, column=0, padx=10, pady=10, sticky="ew")
        search_frame.grid_columnconfigure(1, weight=1)

        ctk.CTkLabel(search_frame, text=self.texts['material_search']).grid(row=0, column=0, padx=5)
        self.search_entry = ctk.CTkEntry(search_frame)
        self.search_entry.grid(row=0, column=1, padx=5, sticky="ew")
        self.search_entry.bind("<Return>", self.search_materials)
        self.search_entry.bind("<KeyRelease>", self.on_material_search)
        ctk.CTkButton(search_frame, text=self.texts['search'], width=60, command=self.search_materials).grid(row=0, column=2, padx=5)
        ctk.CTkButton(search_frame, text=self.texts['reset'], width=60, command=self.reset_search).grid(row=0, column=3, padx=5)

        # --- 원료 목록 Treeview (탭 뷰 제거) ---
        tree_frame = ctk.CTkFrame(self, fg_color="transparent")
        tree_frame.grid(row=1, column=0, padx=10, pady=5, sticky="nsew")
        tree_frame.grid_columnconfigure(0, weight=1)
        tree_frame.grid_rowconfigure(0, weight=1)

        tree_columns = ("code", "name", "ingredients")
        self.material_tree = ttk.Treeview(tree_frame, columns=tree_columns, show="headings", selectmode="browse")
        self.material_tree.heading("code", text=self.texts['code']); self.material_tree.column("code", width=120) # noqa
        self.material_tree.heading("name", text=self.texts['material_name']); self.material_tree.column("name", width=150) # noqa
        self.material_tree.heading("ingredients", text=self.texts['all_ingredients']); self.material_tree.column("ingredients", width=200, stretch=True) # noqa

        self.material_tree.grid(row=0, column=0, sticky="nsew")

        scrollbar = ttk.Scrollbar(tree_frame, orient="vertical", command=self.material_tree.yview)
        self.material_tree.configure(yscrollcommand=scrollbar.set)
        scrollbar.grid(row=0, column=1, sticky="ns")
        self.material_tree.bind("<<TreeviewSelect>>", self.on_material_select)
        self.material_tree.bind("<Double-1>", self.on_double_click_add)

        # --- 전성분 상세 정보 프레임 ---
        details_frame = ctk.CTkFrame(self, fg_color="transparent")
        details_frame.grid(row=2, column=0, padx=10, pady=5, sticky="ew")
        details_frame.grid_columnconfigure(1, weight=1)

        ctk.CTkLabel(details_frame, text=f"{self.texts['all_ingredients']}:").grid(row=0, column=0, padx=5, sticky="nw")
        self.ingredient_details_textbox = ctk.CTkTextbox(details_frame, height=60, state="disabled", wrap="word")
        self.ingredient_details_textbox.grid(row=0, column=1, padx=5, sticky="ew")


        # --- 버튼 프레임 ---
        button_frame = ctk.CTkFrame(self, fg_color="transparent")
        button_frame.grid(row=3, column=0, pady=10)
        ctk.CTkButton(button_frame, text=self.texts['add_material'], command=self.on_add).pack(side="left", padx=5)
        ctk.CTkButton(button_frame, text=self.texts['line_break'], command=self.on_line_break_callback).pack(side="left", padx=5)
        ctk.CTkButton(button_frame, text=self.texts['close'], fg_color="gray50", hover_color="gray35", command=self.destroy).pack(side="left", padx=10)

        self.search_materials() # 초기 전체 목록 로드

        # 메인 창 중앙에 배치 후 deiconify
        self.update_idletasks()
        parent = master
        if parent:
            parent_x = parent.winfo_rootx()
            parent_y = parent.winfo_rooty()
            parent_w = parent.winfo_width()
            parent_h = parent.winfo_height()
            win_w = self.winfo_width()
            win_h = self.winfo_height()
            x = parent_x + (parent_w - win_w) // 2
            y = parent_y + (parent_h - win_h) // 2
            self.geometry(f"+{x}+{y}")
        self.deiconify()

    def reset_search(self):
        """검색창을 비우고 전체 목록을 다시 불러옵니다."""
        self.search_entry.delete(0, "end")
        self.search_materials()

    def on_material_search(self, event=None):
        """검색창 입력 시 디바운싱을 적용하여 검색을 실행합니다."""
        if self.search_timer:
            self.after_cancel(self.search_timer)
        # 500ms(0.5초) 후에 search_materials 함수를 실행
        self.search_timer = self.after(500, self.search_materials)

    def _get_numeric_part(self, code_str: str):
        """문자열에서 숫자 부분을 추출하여 정수로 반환합니다."""
        import re
        if not isinstance(code_str, str):
            return None
        match = re.search(r'\d+', code_str)
        return int(match.group(0)) if match else None

    def search_materials(self, event=None):
        """DB에서 원료를 검색하여 단일 Treeview에 표시합니다."""
        search_term = self.search_entry.get().strip()

        # Treeview 초기화
        for item in self.material_tree.get_children():
            self.material_tree.delete(item)

        # `load_ingredients=True`를 전달하여 전성분 정보를 함께 로드합니다.
        materials = db_manager.search_materials(search_term, load_ingredients=True, search_ingredients=True)

        try:
            for mat in materials:
                # 전성분 목록을 문자열로 만듭니다 (최대 3개).
                # 이제 mat.ingredients에 접근해도 DetachedInstanceError가 발생하지 않습니다.
                ing_names = [ing.name_en for ing in mat.ingredients[:3]]
                ing_str = ", ".join(ing_names)
                if len(mat.ingredients) > 3:
                    ing_str += "..."
                self.material_tree.insert("", "end", iid=mat.id, values=(mat.code, mat.name, ing_str))
        except Exception as e:
            print(f"원료 목록 표시 중 오류 발생: {e}")

    def on_material_select(self, event=None):
        """트리뷰에서 원료 선택 시 전성분 목록을 표시합니다."""
        selected_item = self.material_tree.selection()
        # 텍스트박스 초기화
        self.ingredient_details_textbox.configure(state="normal")
        self.ingredient_details_textbox.delete("1.0", "end")

        if not selected_item:
            self.ingredient_details_textbox.configure(state="disabled")
            return

        material_id = selected_item[0]

        session = db_manager.get_session()
        try:
            from database.models import Ingredient
            # 전성분 목록 가져오기
            ingredients = session.query(Ingredient).filter_by(material_id=material_id).order_by(Ingredient.id).all()
            
            if ingredients:
                # 영문명과 한글명을 함께 표시
                ingredient_texts = [f"{ing.name_en} ({ing.name_ko})" for ing in ingredients]
                details_text = ", ".join(ingredient_texts)
            else:
                details_text = self.texts['no_ingredients_registered']
            self.ingredient_details_textbox.insert("1.0", details_text)
        finally:
            session.close()
            self.ingredient_details_textbox.configure(state="disabled")

    def on_double_click_add(self, event):
        """Treeview에서 항목을 더블클릭하여 바로 추가합니다."""
        # 더블클릭된 위젯(Treeview)을 식별합니다.
        tree = event.widget
        
        # 더블클릭된 행을 식별합니다.
        item_id = tree.identify_row(event.y)
        if not item_id:
            return

        # 해당 행을 선택하고 포커스를 줍니다.
        tree.selection_set(item_id)
        tree.focus(item_id)
        self.on_add() # 기존 추가 로직을 호출합니다.

    def on_add(self):
        """'추가' 버튼 클릭 시 콜백 함수를 호출합니다."""
        selected_item = self.material_tree.selection()
        if not selected_item:
            messagebox.showwarning(self.texts['selection_error'], self.texts['select_material_to_add'], parent=self)
            return

        material_id = selected_item[0]
        self.on_add_callback(material_id)

        # 추가 후 입력 필드 초기화
        self.material_tree.selection_remove(selected_item)

def try_convert_to_float(value):
    """값을 float으로 변환 시도, 실패 시 원래 값 반환"""
    if value is None:
        return None
    try:
        val = float(value)
        # 10자리 정도에서 반올림하여 부동소수점 오차(45.57 -> 45.569999...) 제거
        # 일반적인 화장품 함량에서는 4~6자리도 충분하지만 안전하게 8자리 사용
        return round(val, 8)
    except (ValueError, TypeError):
        return value


class ProductionPreviewPane(ctk.CTkFrame):
    """생산처방 미리보기용 재사용 가능한 두-컬럼(좌 레시피 / 우 도식) 패널.

    - production: ProductionFormulation ORM 인스턴스 (items_snapshot, base_weight_g 사용)
    - steps: List[ProductionStep] (step_no 순으로 전달 권장)
    - on_export_excel: 엑셀 내보내기 콜백 (권장)
    - on_export_json: (하위호환) JSON 내보내기 콜백
    """
    def __init__(self, master, production, steps, on_export_excel=None, on_export_json=None, on_print_preview=None, **kwargs):
        super().__init__(master, **kwargs)
        self.production = production
        self.steps = steps or []
        self.on_export_excel = on_export_excel
        self.on_export_json = on_export_json
        self.on_print_preview = on_print_preview

        # 스타일(카드 느낌)
        self.configure(fg_color="transparent")

        # 상단 툴바
        toolbar = ctk.CTkFrame(self, fg_color="transparent")
        toolbar.pack(fill="x", padx=0, pady=(0, 6))
        if self.on_export_excel:
            ctk.CTkButton(toolbar, text="엑셀 내보내기", width=120, command=self.on_export_excel).pack(side="left")
        if self.on_print_preview:
            ctk.CTkButton(toolbar, text="인쇄 미리보기", width=120, command=self.on_print_preview).pack(side="left", padx=(6,0))
        elif self.on_export_json:
            ctk.CTkButton(toolbar, text="JSON 내보내기", width=120, command=self.on_export_json).pack(side="left")

        # 분할(좌/우) - PanedWindow 사용으로 너비 조절 가능
        # 주의: CTk의 'transparent' 색상은 tkinter에선 유효하지 않으므로 bg 지정 생략
        paned = tk.PanedWindow(self, orient=tk.HORIZONTAL, sashwidth=8)
        paned.pack(fill="both", expand=True)

        # 좌측 카드
        left_card = ctk.CTkFrame(paned, corner_radius=10)
        left_card.grid_columnconfigure(0, weight=1)
        left_card.grid_rowconfigure(1, weight=1)
        ctk.CTkLabel(left_card, text="레시피(처방내용)", font=ctk.CTkFont(weight="bold")).grid(row=0, column=0, sticky="w", padx=10, pady=(10,4))
        left_wrap = ctk.CTkFrame(left_card, fg_color="transparent")
        left_wrap.grid(row=1, column=0, sticky="nsew", padx=8, pady=(0,8))
        rcols = ("order","phase","code","name","ratio","amount","calc_g","process","inspection")
        self.recipe_tree = ttk.Treeview(left_wrap, columns=rcols, show="headings")
        self.recipe_tree.heading("order", text="Ph."); self.recipe_tree.column("order", width=60, anchor="center")
        self.recipe_tree.heading("phase", text="구분"); self.recipe_tree.column("phase", width=80)
        self.recipe_tree.heading("code", text="코드"); self.recipe_tree.column("code", width=120)
        self.recipe_tree.heading("name", text="원료명"); self.recipe_tree.column("name", width=240, stretch=True)
        self.recipe_tree.heading("ratio", text="함량(%)"); self.recipe_tree.column("ratio", width=90, anchor="e")
        self.recipe_tree.heading("amount", text="중량(실험)"); self.recipe_tree.column("amount", width=100, anchor="e")
        self.recipe_tree.heading("calc_g", text="생산량(kg)"); self.recipe_tree.column("calc_g", width=110, anchor="e")
        self.recipe_tree.heading("process", text="제조공정"); self.recipe_tree.column("process", width=360, stretch=True)
        self.recipe_tree.heading("inspection", text="공정검사"); self.recipe_tree.column("inspection", width=240, stretch=True)
        self.recipe_tree.grid(row=0, column=0, sticky="nsew")
        rscroll = ttk.Scrollbar(left_wrap, orient="vertical", command=self.recipe_tree.yview)
        rscroll.grid(row=0, column=1, sticky="ns")
        self.recipe_tree.configure(yscrollcommand=rscroll.set)

        # PanedWindow에 카드 추가 (우측 카드는 제거하고 좌측 통합표만 사용)
        paned.add(left_card)
        try:
            paned.sash_place(0, int(self.winfo_screenwidth()*0.28), 0)
        except Exception:
            pass

        # 초기 렌더
        self.render_recipe()

    def set_data(self, production, steps):
        self.production = production
        self.steps = steps or []
        self.render_recipe()

    def render_recipe(self):
        # 트리 초기화
        for i in self.recipe_tree.get_children():
            self.recipe_tree.delete(i)
        # 데이터 채우기
        # 단계 -> Phase별 (제조공정/공정검사) 텍스트 맵 구성
        phase_map = {}
        def _norm_phase(x):
            return (str(x or '').strip().upper())
        try:
            for st in (self.steps or []):
                instr = (getattr(st, 'instruction', '') or '').strip()
                if not instr:
                    continue
                ph = _norm_phase(getattr(st, 'phase', None))
                proc_lines = phase_map.get(ph, {}).get('proc', [])
                insp_lines = phase_map.get(ph, {}).get('insp', [])
                # 분리
                lines = instr.splitlines()
                prefixes = ("시간", "온도", "HE/M", "H/M", "P/M", "HE/M:", "H/M:", "P/M:")
                for ln in lines:
                    lt = ln.strip()
                    if not lt:
                        continue
                    if lt.startswith(prefixes):
                        insp_lines.append(lt)
                    else:
                        proc_lines.append(lt)
                phase_map[ph] = {'proc': proc_lines, 'insp': insp_lines}
        except Exception:
            phase_map = {}
        try:
            items = json.loads(self.production.items_snapshot) if getattr(self.production, 'items_snapshot', None) else []
        except Exception:
            items = []
        base_w = getattr(self.production, 'base_weight_g', 0) or 0
        def to_phase_letter(n):
            try:
                n = int(n)
            except Exception:
                s = str(n or '').strip()
                return s.upper() if s else ""
            if n <= 0:
                return ""
            out = ""
            while n > 0:
                n, rem = divmod(n-1, 26)
                out = chr(65+rem) + out
            return out
        for it in sorted(items, key=lambda x: (x.get('order') or 0)):
            ratio = it.get('ratio') or 0
            calc_g = (base_w * float(ratio) / 100.0) if base_w and isinstance(ratio, (int, float)) else ""
            calc_kg = (calc_g / 1000.0) if isinstance(calc_g, (int, float)) else ""
            try:
                calc_disp = f"{calc_kg:,.1f}" if isinstance(calc_kg, (int, float)) else ""
            except Exception:
                calc_disp = str(calc_kg) if calc_kg is not None else ""
            ph_key = _norm_phase(it.get('phase'))
            pm = phase_map.get(ph_key) or {'proc': [], 'insp': []}
            proc_text = "\n".join(pm.get('proc') or [])
            insp_text = "\n".join(pm.get('insp') or [])
            self.recipe_tree.insert("", "end", values=(
                to_phase_letter(it.get('order') or ""),
                it.get('phase') or "",
                it.get('material_code') or "",
                it.get('material_name') or "",
                f"{(ratio or 0):.4f}" if isinstance(ratio, (int, float)) else (ratio or ""),
                it.get('amount') or "",
                calc_disp,
                proc_text,
                insp_text,
            ))
# modules/ui_components.py
import customtkinter as ctk
import tkinter as tk
from tkinter import ttk, messagebox
import json
from database.db_manager import db_manager
from modules.translation import get_texts

class HelpPopup(ctk.CTkToplevel):
    """도움말 내용을 표시하는 스크롤 가능한 팝업 창"""
    def __init__(self, master, title, message):
        super().__init__(master)
        self.texts = get_texts(master.language if hasattr(master, 'language') else 'korean')
        self.title(title)
        self.geometry("600x450")
        self.transient(master)
        self.grab_set()

        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(0, weight=1)

        scrollable_frame = ctk.CTkScrollableFrame(self, label_text=self.texts['help'])
        scrollable_frame.grid(row=0, column=0, padx=15, pady=15, sticky="nsew")

        label = ctk.CTkLabel(scrollable_frame, text=message, justify="left", anchor="nw")
        label.pack(padx=10, pady=10, fill="both", expand=True)

        close_button = ctk.CTkButton(self, text=self.texts['close'], command=self.destroy)
        close_button.grid(row=1, column=0, padx=15, pady=(0, 15))

class CustomErrorDialog(ctk.CTkToplevel):
    """'클립보드로 복사' 기능이 포함된 커스텀 오류 대화상자"""
    def __init__(self, master, title="오류", error_message=""):
        super().__init__(master)
        self.title(title)
        self.transient(master)
        self.grab_set()
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

    def copy_to_clipboard(self):
        self.clipboard_clear()
        self.clipboard_append(self.error_message)
        messagebox.showinfo("복사 완료", "오류 메시지가 클립보드에 복사되었습니다.", parent=self)

class CustomDropdown(ctk.CTkFrame):
    """스크롤바가 있는 안정적인 커스텀 드롭다운 메뉴 위젯"""
    def __init__(self, master, values=None, command=None, width=120, **kwargs):
        super().__init__(master, **kwargs)
        self.values = values if values else []
        self.command = command
        self.width = width
        self.configure(fg_color="transparent", width=self.width)

        self.button = ctk.CTkButton(self, text=self.values[0] if self.values else "", width=self.width, 
                                    anchor="w", command=self.toggle_dropdown)
        self.button.pack()
        self.dropdown_toplevel = None

    def toggle_dropdown(self):
        if self.dropdown_toplevel and self.dropdown_toplevel.winfo_exists():
            self.close_dropdown()
        else:
            self.open_dropdown()

    def open_dropdown(self):
        if self.dropdown_toplevel and self.dropdown_toplevel.winfo_exists():
            return

        self.dropdown_toplevel = ctk.CTkToplevel(self)
        self.dropdown_toplevel.overrideredirect(True)
        x = self.button.winfo_rootx()
        y = self.button.winfo_rooty() + self.button.winfo_height()
        width = self.button.winfo_width()
        self.dropdown_toplevel.geometry(f"{width}x200+{x}+{y}")

        scroll_frame = ctk.CTkScrollableFrame(self.dropdown_toplevel, label_text="")
        scroll_frame.pack(fill="both", expand=True)

        # --- 이벤트 전파 방지 (최종 수정) ---
        # 드롭다운 메뉴가 열려 있는 동안, 마우스 휠 이벤트가 다른 위젯으로 전파되는 것을 막습니다.
        # bind_all을 사용하여 이벤트를 가로채고, 드롭다운이 닫힐 때 unbind_all로 해제합니다.
        def _block_scroll(event):
            # 이벤트가 드롭다운 메뉴 내부에서 발생했는지 확인합니다.
            # 이벤트 위젯이 드롭다운의 자식이 아니면 이벤트를 처리하지 않습니다.
            if event.widget.winfo_toplevel() != self.dropdown_toplevel:
                return
            return "break"
        self.dropdown_toplevel.bind_all("<MouseWheel>", _block_scroll, add="+")
        
        # 드롭다운이 닫힐 때 bind_all로 등록한 마우스 휠 이벤트를 해제합니다.
        # unbind_all은 특정 함수를 지정할 수 없으므로, 이벤트 타입만 전달합니다.
        self.dropdown_toplevel.bind("<Destroy>", lambda e: self.dropdown_toplevel.unbind_all("<MouseWheel>"))

        for value in self.values:
            item_button = ctk.CTkButton(scroll_frame, text=value, anchor="w",
                                        command=lambda v=value: self.select_item(v))
            item_button.pack(fill="x", expand=True, pady=1)

        self.dropdown_toplevel.bind("<FocusOut>", lambda e: self.close_dropdown())
        # Schedule a safe focus set (check existence before calling)
        self.dropdown_toplevel.after(10, lambda: self.dropdown_toplevel.focus_set() if self.dropdown_toplevel and self.dropdown_toplevel.winfo_exists() else None)

    def close_dropdown(self):
        if self.dropdown_toplevel:
            self.dropdown_toplevel.destroy()
            self.dropdown_toplevel = None

    def select_item(self, value):
        self.set(value)
        if self.command: self.command(value)
        self.close_dropdown()

    def set(self, value): self.button.configure(text=value)
    def get(self): return self.button.cget("text")
    def configure(self, **kwargs):
        if 'values' in kwargs: self.values = kwargs.pop('values')
        if 'state' in kwargs: self.button.configure(state=kwargs.pop('state'))
        super().configure(**kwargs)

class AddMaterialDialog(ctk.CTkToplevel):
    """처방에 원료를 추가하기 위한 팝업창"""
    def __init__(self, master, on_add_callback, on_line_break_callback):
        import re
        super().__init__(master)
        self.on_add_callback = on_add_callback
        self.on_line_break_callback = on_line_break_callback

        self.language = master.language
        self.texts = get_texts(self.language)
        self.title(self.texts['add_material_title'])
        self.geometry("600x500")
        self.transient(master)
        self.grab_set()

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
# modules/ui_components.py
import customtkinter as ctk
import tkinter as tk
from tkinter import ttk, messagebox
from database.db_manager import db_manager

class HelpPopup(ctk.CTkToplevel):
    """도움말 내용을 표시하는 스크롤 가능한 팝업 창"""
    def __init__(self, master, title, message):
        super().__init__(master)
        self.title(title)
        self.geometry("600x450")
        self.transient(master)
        self.grab_set()

        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(0, weight=1)

        scrollable_frame = ctk.CTkScrollableFrame(self, label_text="도움말")
        scrollable_frame.grid(row=0, column=0, padx=15, pady=15, sticky="nsew")

        label = ctk.CTkLabel(scrollable_frame, text=message, justify="left", anchor="nw")
        label.pack(padx=10, pady=10, fill="both", expand=True)

        close_button = ctk.CTkButton(self, text="닫기", command=self.destroy)
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

        for value in self.values:
            item_button = ctk.CTkButton(scroll_frame, text=value, anchor="w",
                                        command=lambda v=value: self.select_item(v))
            item_button.pack(fill="x", expand=True, pady=1)

        self.dropdown_toplevel.bind("<FocusOut>", lambda e: self.close_dropdown())
        self.dropdown_toplevel.after(10, self.dropdown_toplevel.focus_set)

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

        self.title("원료 추가")
        self.geometry("600x500")
        self.transient(master)
        self.grab_set()

        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(1, weight=1)
        self.treeviews = {} # 탭별 Treeview 위젯을 저장할 딕셔너리

        # --- 검색 프레임 ---
        search_frame = ctk.CTkFrame(self, fg_color="transparent")
        search_frame.grid(row=0, column=0, padx=10, pady=10, sticky="ew")
        search_frame.grid_columnconfigure(1, weight=1)
        
        ctk.CTkLabel(search_frame, text="원료 검색:").grid(row=0, column=0, padx=5)
        self.search_entry = ctk.CTkEntry(search_frame)
        self.search_entry.grid(row=0, column=1, padx=5, sticky="ew")
        self.search_entry.bind("<Return>", self.search_materials)
        self.search_entry.bind("<KeyRelease>", self.search_materials) # 실시간 검색을 위한 바인딩
        ctk.CTkButton(search_frame, text="검색", width=60, command=lambda: self.search_materials()).grid(row=0, column=2, padx=5)
        ctk.CTkButton(search_frame, text="초기화", width=60, command=self.reset_search).grid(row=0, column=3, padx=5)

        # --- 원료 목록 탭 뷰 ---
        self.tab_view = ctk.CTkTabview(self, border_width=1)
        self.tab_view.grid(row=1, column=0, padx=10, pady=5, sticky="nsew")

        # --- 전성분 상세 정보 프레임 ---
        details_frame = ctk.CTkFrame(self, fg_color="transparent")
        details_frame.grid(row=2, column=0, padx=10, pady=5, sticky="ew")
        details_frame.grid_columnconfigure(1, weight=1)

        ctk.CTkLabel(details_frame, text="전성분:").grid(row=0, column=0, padx=5, sticky="nw")
        self.ingredient_details_textbox = ctk.CTkTextbox(details_frame, height=60, state="disabled", wrap="word")
        self.ingredient_details_textbox.grid(row=0, column=1, padx=5, sticky="ew")


        # --- 버튼 프레임 ---
        button_frame = ctk.CTkFrame(self, fg_color="transparent")
        button_frame.grid(row=3, column=0, pady=10)
        ctk.CTkButton(button_frame, text="원료 추가", command=self.on_add).pack(side="left", padx=5)
        ctk.CTkButton(button_frame, text="줄 내림", command=self.on_line_break_callback).pack(side="left", padx=5)
        ctk.CTkButton(button_frame, text="닫기", fg_color="gray50", hover_color="gray35", command=self.destroy).pack(side="left", padx=10)

        self.search_materials() # 초기 전체 목록 로드

    def reset_search(self):
        """검색창을 비우고 전체 목록을 다시 불러옵니다."""
        self.search_entry.delete(0, "end")
        self.search_materials()

    def _get_numeric_part(self, code_str: str):
        """문자열에서 숫자 부분을 추출하여 정수로 반환합니다."""
        import re
        if not isinstance(code_str, str):
            return None
        match = re.search(r'\d+', code_str)
        return int(match.group(0)) if match else None

    def search_materials(self, event=None):
        """DB에서 원료를 검색하여 1000단위 탭으로 나누어 표시합니다."""
        search_term = self.search_entry.get().strip()
        
        # 검색 전 현재 활성화된 탭 이름 저장
        active_tab_name = self.tab_view.get()

        # 기존 탭과 트리뷰를 모두 초기화합니다.
        for tab_name in list(self.treeviews.keys()):
            self.tab_view.delete(tab_name)
        self.treeviews.clear()

        materials = db_manager.search_materials(search_term)
        
        # 원료를 코드 1000단위로 그룹화
        grouped_materials = {}
        other_materials = [] # 숫자 코드가 없는 원료를 위한 리스트
        for mat in materials:
            num_part = self._get_numeric_part(mat.code)
            if num_part is not None:
                group_key = (num_part // 1000) * 1000
                if group_key not in grouped_materials:
                    grouped_materials[group_key] = []
                grouped_materials[group_key].append(mat)
            else:
                other_materials.append(mat)

        created_tabs = []
        # 그룹화된 원료를 기반으로 탭과 Treeview를 순서대로 생성합니다.
        for group_key in sorted(grouped_materials.keys()):
            created_tabs.append(str(group_key))
            tab_name = str(group_key)
            tab = self.tab_view.add(tab_name)
            tab.grid_columnconfigure(0, weight=1)
            tab.grid_rowconfigure(0, weight=1)

            tree = ttk.Treeview(tab, columns=("id", "code", "name", "ingredients"), show="headings", selectmode="browse")
            tree.heading("id", text="ID"); tree.column("id", width=50, anchor="center")
            tree.heading("code", text="코드"); tree.column("code", width=120)
            tree.heading("name", text="원료명"); tree.column("name", width=150)
            tree.heading("ingredients", text="전성분"); tree.column("ingredients", width=200, stretch=True)
            tree.grid(row=0, column=0, sticky="nsew")

            scrollbar = ttk.Scrollbar(tab, orient="vertical", command=tree.yview)
            tree.configure(yscrollcommand=scrollbar.set)
            scrollbar.grid(row=0, column=1, sticky="ns")

            tree.bind("<<TreeviewSelect>>", self.on_material_select)
            tree.bind("<Double-1>", self.on_double_click_add)
            self.treeviews[tab_name] = tree

            for mat in grouped_materials[group_key]:
                # 전성분 목록을 문자열로 만듭니다 (최대 3개).
                ing_names = [ing.name_en for ing in mat.ingredients[:3]]
                ing_str = ", ".join(ing_names)
                if len(mat.ingredients) > 3:
                    ing_str += "..."
                tree.insert("", "end", values=(mat.id, mat.code, mat.name, ing_str))

    def on_material_select(self, event=None):
        """트리뷰에서 원료 선택 시 전성분 목록을 표시합니다."""
        active_tab_name = self.tab_view.get()
        if not active_tab_name: return
        active_treeview = self.treeviews.get(active_tab_name)
        if not active_treeview: return

        selected_item = active_treeview.selection()
        # 텍스트박스 초기화
        self.ingredient_details_textbox.configure(state="normal")
        self.ingredient_details_textbox.delete("1.0", "end")

        if not selected_item:
            self.ingredient_details_textbox.configure(state="disabled")
            return

        material_id = active_treeview.item(selected_item[0], "values")[0]

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
                details_text = "등록된 전성분이 없습니다."
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
        active_tab_name = self.tab_view.get()
        active_treeview = self.treeviews.get(active_tab_name)
        if not active_treeview: return

        selected_item = active_treeview.selection()
        if not selected_item:
            messagebox.showwarning("선택 오류", "목록에서 추가할 원료를 선택하세요.", parent=self)
            return
        
        material_id = active_treeview.item(selected_item[0], "values")[0]
        self.on_add_callback(material_id)
        
        # 추가 후 입력 필드 초기화
        active_treeview.selection_remove(selected_item)

def try_convert_to_float(value):
    """값을 float으로 변환 시도, 실패 시 원래 값 반환"""
    if value is None:
        return None
    try:
        return float(value)
    except (ValueError, TypeError):
        return value
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
    """[v65 고속 스마트 검색 콤보박스] 실시간 타이핑 자동완성, 마우스 휠 초고속 스크롤, 초성/부분 일치 검색 지원"""
    def __init__(self, master, values=None, command=None, width=150, placeholder="- 선택 -", **kwargs):
        super().__init__(master, fg_color="transparent", width=width)
        self.raw_values = list(values) if values else []
        self.filtered_values = list(self.raw_values)
        self.command = command
        self.placeholder = placeholder
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(0, weight=1)

        self.combobox = ctk.CTkComboBox(
            self,
            values=self.raw_values if self.raw_values else [self.placeholder],
            command=self._on_combo_change,
            width=width,
            height=28
        )
        self.combobox.grid(row=0, column=0, sticky="ew")

        self._filter_timer = None
        self._bind_search_and_scroll_events()

    def _bind_search_and_scroll_events(self):
        """내부 Entry 및 드롭다운 위젯에 실시간 타이핑 필터링과 휠 가속 바인딩"""
        try:
            entry_widget = getattr(self.combobox, '_entry', None)
            if entry_widget:
                entry_widget.bind("<FocusIn>", self._on_focus_in, add="+")
                entry_widget.bind("<Button-1>", self._on_click, add="+")
                entry_widget.bind("<KeyRelease>", self._on_key_release, add="+")
                entry_widget.bind("<Return>", self._on_enter_press, add="+")

            # CTkComboBox의 _open_dropdown_menu 메서드 후킹하여 원본 전체 목록 복원 및 휠 스크롤 가속 주입
            orig_open = self.combobox._open_dropdown_menu
            def _wrapped_open():
                if self.raw_values:
                    self.combobox.configure(values=self.raw_values)
                orig_open()
                self._apply_wheel_acceleration()
            self.combobox._open_dropdown_menu = _wrapped_open
        except Exception:
            pass

    def _apply_wheel_acceleration(self):
        """드롭다운 팝업 메뉴의 마우스 휠 스크롤 속도를 4~5배 가속하여 대량 항목도 시원하게 스크롤"""
        try:
            dropdown = getattr(self.combobox, '_dropdown_menu', None)
            if not dropdown:
                return

            # CTkScrollableFrame 내부 canvas 탐색
            scrollable = getattr(dropdown, '_scrollable_frame', dropdown)
            canvas = getattr(scrollable, '_parent_canvas', None) or getattr(scrollable, 'canvas', None)
            if not canvas:
                # 자식 위젯 순회로 canvas 찾기
                for child in scrollable.winfo_children():
                    if isinstance(child, tk.Canvas):
                        canvas = child
                        break

            if canvas:
                def _accelerated_scroll(event):
                    if event.delta:
                        # 기본 1단위 -> 4단위로 시원하게 가속 스크롤
                        step = -1 * int(event.delta / 120 * 4)
                        canvas.yview_scroll(step, "units")
                        return "break"
                
                # 드롭다운 전체와 canvas에 바인딩
                canvas.bind("<MouseWheel>", _accelerated_scroll, add="+")
                scrollable.bind("<MouseWheel>", _accelerated_scroll, add="+")
                dropdown.bind("<MouseWheel>", _accelerated_scroll, add="+")
                for w in scrollable.winfo_children():
                    try:
                        w.bind("<MouseWheel>", _accelerated_scroll, add="+")
                    except:
                        pass
        except Exception:
            pass

    def _on_focus_in(self, event=None):
        try:
            if self.raw_values:
                self.filtered_values = list(self.raw_values)
                self.combobox.configure(values=self.raw_values)
            entry_widget = getattr(self.combobox, '_entry', None)
            if entry_widget:
                entry_widget.after(10, lambda: entry_widget.select_range(0, 'end'))
        except Exception:
            pass

    def _on_click(self, event=None):
        try:
            if self.raw_values:
                self.filtered_values = list(self.raw_values)
                self.combobox.configure(values=self.raw_values)
            entry_widget = getattr(self.combobox, '_entry', None)
            if entry_widget:
                entry_widget.after(20, lambda: entry_widget.select_range(0, 'end'))
        except Exception:
            pass

    def _on_key_release(self, event=None):
        """타이핑 시 0.001초 실시간 목록 필터링"""
        if event and event.keysym in ("Up", "Down", "Return", "Escape", "Tab", "Shift_L", "Shift_R", "Control_L", "Control_R"):
            return

        if self._filter_timer:
            self.after_cancel(self._filter_timer)
        self._filter_timer = self.after(100, self._filter_values_by_text)

    def _filter_values_by_text(self):
        """입력된 검색어로 드롭다운 목록 실시간 갱신"""
        try:
            current_text = self.combobox.get().strip().lower()
            if not current_text or current_text == self.placeholder.lower():
                matching = list(self.raw_values)
            else:
                # 부분 일치 검색
                matching = [v for v in self.raw_values if current_text in str(v).lower()]
                if not matching:
                    # 일치 항목이 없을 경우 원본 유지
                    matching = list(self.raw_values)

            self.filtered_values = matching if matching else [self.placeholder]
            self.combobox.configure(values=self.filtered_values)
        except Exception:
            pass

    def _on_enter_press(self, event=None):
        """Enter 키 입력 시 현재 텍스트 또는 첫 번째 일치 항목 확정 및 콜백 실행"""
        try:
            val = self.combobox.get().strip()
            # 정확 일치 항목 탐색
            matched = next((v for v in self.raw_values if v.lower() == val.lower()), None)
            if not matched and self.filtered_values:
                matched = self.filtered_values[0]

            if matched:
                self.combobox.set(matched)
                self._on_combo_change(matched)
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
            self.filtered_values = list(self.raw_values)
            self.combobox.configure(values=self.raw_values)
        if 'state' in kwargs:
            self.combobox.configure(state=kwargs.pop('state'))
        if kwargs:
            super().configure(**kwargs)

class AddMaterialDialog(ctk.CTkToplevel):
    """처방에 원료를 추가하기 위한 팝업창 (단일/복합/코드/원료명/전성분 다기준 초고속 정렬 지원)"""
    def __init__(self, master, on_add_callback, on_line_break_callback):
        import re
        super().__init__(master)
        self.withdraw()  # 초기 렌더링 랙 방지
        self.on_add_callback = on_add_callback
        self.on_line_break_callback = on_line_break_callback

        self.language = getattr(master, 'language', 'korean')
        self.texts = get_texts(self.language)
        self.title(self.texts.get('add_material_title', '원료 추가'))
        self.geometry("700x560")
        self.minsize(620, 480)

        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(2, weight=1)
        self.search_timer = None # 검색 디바운싱 타이머

        # 정렬 및 필터 상태
        self.raw_search_results = []   # 검색된 원본 원료 리스트
        self.filtered_materials = []   # 필터/정렬 적용된 원료 리스트
        self.current_sort_col = "code" # 현재 정렬 컬럼
        self.sort_reverse = False      # 내림차순 여부
        self.current_type_filter = "전체" # 전체 / 단일 / 복합

        # --- 1. 상단 검색 프레임 ---
        search_frame = ctk.CTkFrame(self, fg_color="transparent")
        search_frame.grid(row=0, column=0, padx=12, pady=(10, 4), sticky="ew")
        search_frame.grid_columnconfigure(1, weight=1)

        ctk.CTkLabel(search_frame, text=self.texts.get('material_search', '원료 검색:'), font=ctk.CTkFont(weight="bold")).grid(row=0, column=0, padx=(0, 5))
        self.search_entry = ctk.CTkEntry(search_frame, placeholder_text="원료코드, 원료명(한글/영문), 전성분명 검색...")
        self.search_entry.grid(row=0, column=1, padx=5, sticky="ew")
        self.search_entry.bind("<Return>", self.search_materials)
        self.search_entry.bind("<KeyRelease>", self.on_material_search)
        ctk.CTkButton(search_frame, text=self.texts.get('search', '검색'), width=60, command=self.search_materials).grid(row=0, column=2, padx=3)
        ctk.CTkButton(search_frame, text=self.texts.get('reset', '초기화'), width=60, fg_color="gray50", hover_color="gray40", command=self.reset_search).grid(row=0, column=3, padx=3)

        # --- 2. 정렬 및 유형 필터 툴바 ---
        filter_toolbar = ctk.CTkFrame(self, fg_color=("gray92", "#242526"), corner_radius=6)
        filter_toolbar.grid(row=1, column=0, padx=12, pady=4, sticky="ew")
        filter_toolbar.grid_columnconfigure(3, weight=1)

        # 단일/복합 유형 세그먼트 버튼
        ctk.CTkLabel(filter_toolbar, text="유형:", font=ctk.CTkFont(size=12, weight="bold")).grid(row=0, column=0, padx=(10, 4), pady=6)
        self.type_filter_seg = ctk.CTkSegmentedButton(
            filter_toolbar,
            values=["전체", "단일 원료", "복합 원료"],
            command=self._on_type_filter_changed,
            height=26,
            font=ctk.CTkFont(size=11)
        )
        self.type_filter_seg.set("전체")
        self.type_filter_seg.grid(row=0, column=1, padx=4, pady=6)

        # 정렬 기준 콤보박스
        ctk.CTkLabel(filter_toolbar, text="정렬:", font=ctk.CTkFont(size=12, weight="bold")).grid(row=0, column=2, padx=(12, 4), pady=6)
        self.sort_combo = ctk.CTkComboBox(
            filter_toolbar,
            values=[
                "코드순 (오름차순 ▲)",
                "코드순 (내림차순 ▼)",
                "단일 원료 우선 (단일 ➡️ 복합)",
                "복합 원료 우선 (복합 ➡️ 단일)",
                "원료명 (가나다순 ▲)",
                "원료명 (역순 ▼)",
                "전성분 (가나다순 ▲)",
                "전성분 개수 (많은순 ▼)",
                "전성분 개수 (적은순 ▲)"
            ],
            width=185,
            height=26,
            command=self._on_sort_combo_changed,
            state="readonly",
            font=ctk.CTkFont(size=11)
        )
        self.sort_combo.set("코드순 (오름차순 ▲)")
        self.sort_combo.grid(row=0, column=3, padx=(4, 10), pady=6, sticky="w")

        # 결과 건수 라벨
        self.count_label = ctk.CTkLabel(filter_toolbar, text="총 0건", font=ctk.CTkFont(size=11), text_color=("gray40", "gray70"))
        self.count_label.grid(row=0, column=4, padx=(0, 12), pady=6, sticky="e")

        # --- 3. 원료 목록 Treeview ---
        tree_frame = ctk.CTkFrame(self, fg_color="transparent")
        tree_frame.grid(row=2, column=0, padx=12, pady=4, sticky="nsew")
        tree_frame.grid_columnconfigure(0, weight=1)
        tree_frame.grid_rowconfigure(0, weight=1)

        tree_columns = ("type", "code", "name", "ingredients")
        self.material_tree = ttk.Treeview(tree_frame, columns=tree_columns, show="headings", selectmode="browse")
        
        # 헤더 설정 및 클릭 정렬 이벤트 연결
        self.material_tree.heading("type", text="구분 ↕", command=lambda: self._sort_by_column("type"))
        self.material_tree.column("type", width=70, minwidth=60, anchor="center", stretch=False)
        
        self.material_tree.heading("code", text="코드 ▲", command=lambda: self._sort_by_column("code"))
        self.material_tree.column("code", width=110, minwidth=80, stretch=False)
        
        self.material_tree.heading("name", text="원료명 ↕", command=lambda: self._sort_by_column("name"))
        self.material_tree.column("name", width=180, minwidth=130, stretch=False)
        
        self.material_tree.heading("ingredients", text="대표 전성분 (배합비 순) ↕", command=lambda: self._sort_by_column("ingredients"))
        self.material_tree.column("ingredients", width=280, stretch=True)

        self.material_tree.grid(row=0, column=0, sticky="nsew")

        scrollbar = ttk.Scrollbar(tree_frame, orient="vertical", command=self.material_tree.yview)
        self.material_tree.configure(yscrollcommand=scrollbar.set)
        scrollbar.grid(row=0, column=1, sticky="ns")
        self.material_tree.bind("<<TreeviewSelect>>", self.on_material_select)
        self.material_tree.bind("<Double-1>", self.on_double_click_add)
        self.material_tree.bind("<Return>", lambda e: self.on_add())

        # --- 4. 전성분 상세 정보 프레임 ---
        details_frame = ctk.CTkFrame(self, fg_color="transparent")
        details_frame.grid(row=3, column=0, padx=12, pady=4, sticky="ew")
        details_frame.grid_columnconfigure(1, weight=1)

        ctk.CTkLabel(details_frame, text=f"{self.texts.get('all_ingredients', '전성분 상세')}:", font=ctk.CTkFont(size=11, weight="bold")).grid(row=0, column=0, padx=5, sticky="nw")
        self.ingredient_details_textbox = ctk.CTkTextbox(details_frame, height=55, state="disabled", wrap="word", font=ctk.CTkFont(size=11))
        self.ingredient_details_textbox.grid(row=0, column=1, padx=5, sticky="ew")

        # --- 5. 버튼 프레임 ---
        button_frame = ctk.CTkFrame(self, fg_color="transparent")
        button_frame.grid(row=4, column=0, pady=(4, 12))
        ctk.CTkButton(button_frame, text=f"➕ {self.texts.get('add_material', '원료 추가')}", font=ctk.CTkFont(weight="bold"), command=self.on_add).pack(side="left", padx=5)
        ctk.CTkButton(button_frame, text=self.texts.get('line_break', '줄 내림'), command=self.on_line_break_callback).pack(side="left", padx=5)
        ctk.CTkButton(button_frame, text=self.texts.get('close', '닫기'), fg_color="gray50", hover_color="gray35", command=self.destroy).pack(side="left", padx=10)

        # 초기 전체 목록 로드
        self.search_materials()

        # 메인 창 중앙에 배치 및 포커스 락인
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
        self.after(50, lambda: self.search_entry.focus_set())
        self.after(50, lambda: self.search_entry.focus_force())

    def reset_search(self):
        """검색창 및 필터를 초기화하고 전체 목록을 다시 불러옵니다."""
        self.search_entry.delete(0, "end")
        self.type_filter_seg.set("전체")
        self.current_type_filter = "전체"
        self.sort_combo.set("코드순 (오름차순 ▲)")
        self.current_sort_col = "code"
        self.sort_reverse = False
        self.search_materials()
        self.after(30, lambda: self.search_entry.focus_set())

    def on_material_search(self, event=None):
        """검색창 입력 시 디바운싱을 적용하여 검색을 실행합니다."""
        if self.search_timer:
            self.after_cancel(self.search_timer)
        self.search_timer = self.after(300, self.search_materials)

    def _get_numeric_part(self, code_str: str):
        """문자열에서 숫자 부분을 추출하여 정수로 반환합니다."""
        import re
        if not isinstance(code_str, str):
            return 0
        match = re.search(r'\d+', code_str)
        return int(match.group(0)) if match else 0

    def _natural_sort_key(self, s: str):
        """자연스러운 정렬을 위한 키 생성 (예: MAT-2가 MAT-10보다 먼저 오도록 처리)"""
        import re
        if not s:
            return []
        return [int(text) if text.isdigit() else text.lower() for text in re.split(r'(\d+)', str(s))]

    def search_materials(self, event=None):
        """DB에서 원료를 검색하여 인메모리에 적재 후 필터 및 정렬을 적용합니다."""
        search_term = self.search_entry.get().strip()

        # 전성분 정보를 함께 고속 로드
        materials = db_manager.search_materials(search_term, load_ingredients=True, search_ingredients=True)

        processed_data = []
        for mat in materials:
            ings = mat.ingredients if mat.ingredients else []
            ing_count = len(ings)
            is_blend = ing_count >= 2

            # 구분 텍스트 (단일 / 복합)
            if ing_count == 0:
                type_text = "단일"
            elif ing_count == 1:
                type_text = "단일"
            else:
                type_text = f"복합({ing_count})"

            # 대표 전성분 문자열 (배합비 높은 순 상위 3개)
            sorted_ings = sorted(ings, key=lambda x: getattr(x, 'composition_ratio', 0) or 0, reverse=True)
            ing_names = []
            for ing in sorted_ings[:3]:
                n = ing.name_ko or ing.name_en or ""
                r = f"({ing.composition_ratio}%)" if getattr(ing, 'composition_ratio', None) else ""
                ing_names.append(f"{n}{r}")
            
            ing_str = ", ".join(ing_names) if ing_names else "-"
            if ing_count > 3:
                ing_str += f" 외 {ing_count - 3}종"

            # 전체 전성분 상세 문자열
            full_ing_list = []
            for ing in sorted_ings:
                n_ko = ing.name_ko or ""
                n_en = ing.name_en or ""
                name_disp = f"{n_ko} ({n_en})" if n_ko and n_en else (n_ko or n_en)
                r_str = f" [{ing.composition_ratio}%]" if getattr(ing, 'composition_ratio', None) else ""
                full_ing_list.append(f"{name_disp}{r_str}")
            full_ing_str = ", ".join(full_ing_list) if full_ing_list else self.texts.get('no_ingredients_registered', '등록된 전성분이 없습니다.')

            processed_data.append({
                "id": mat.id,
                "code": mat.code or "",
                "name": mat.name or "",
                "name_en": mat.name_en or "",
                "type_text": type_text,
                "is_blend": is_blend,
                "ing_count": ing_count,
                "ing_str": ing_str,
                "full_ing_str": full_ing_str,
                "raw_mat": mat
            })

        self.raw_search_results = processed_data
        self._apply_filter_and_sort()

    def _on_type_filter_changed(self, selected_type):
        """단일/복합 유형 세그먼트 변경 시 인메모리 필터링 즉각 반영"""
        self.current_type_filter = selected_type
        self._apply_filter_and_sort()

    def _on_sort_combo_changed(self, selected_option):
        """정렬 콤보박스 변경 시 정렬 기준 갱신 및 즉각 반영"""
        if "코드순 (오름차순" in selected_option:
            self.current_sort_col = "code"
            self.sort_reverse = False
        elif "코드순 (내림차순" in selected_option:
            self.current_sort_col = "code"
            self.sort_reverse = True
        elif "단일 원료 우선" in selected_option:
            self.current_sort_col = "single_first"
            self.sort_reverse = False
        elif "복합 원료 우선" in selected_option:
            self.current_sort_col = "complex_first"
            self.sort_reverse = False
        elif "원료명 (가나다순" in selected_option:
            self.current_sort_col = "name"
            self.sort_reverse = False
        elif "원료명 (역순" in selected_option:
            self.current_sort_col = "name"
            self.sort_reverse = True
        elif "전성분 (가나다순" in selected_option:
            self.current_sort_col = "ingredients"
            self.sort_reverse = False
        elif "전성분 개수 (많은순" in selected_option:
            self.current_sort_col = "ing_count"
            self.sort_reverse = True
        elif "전성분 개수 (적은순" in selected_option:
            self.current_sort_col = "ing_count"
            self.sort_reverse = False

        self._update_header_indicators()
        self._apply_filter_and_sort()

    def _sort_by_column(self, col):
        """Treeview 헤더 클릭 시 오름차순/내림차순 토글 정렬"""
        if self.current_sort_col == col:
            self.sort_reverse = not self.sort_reverse
        else:
            self.current_sort_col = col
            self.sort_reverse = False

        # 콤보박스 값도 일치하도록 동기화
        if col == "code":
            self.sort_combo.set("코드순 (내림차순 ▼)" if self.sort_reverse else "코드순 (오름차순 ▲)")
        elif col == "type":
            self.sort_combo.set("복합 원료 우선 (복합 ➡️ 단일)" if self.sort_reverse else "단일 원료 우선 (단일 ➡️ 복합)")
        elif col == "name":
            self.sort_combo.set("원료명 (역순 ▼)" if self.sort_reverse else "원료명 (가나다순 ▲)")
        elif col == "ingredients":
            self.sort_combo.set("전성분 (가나다순 ▲)")

        self._update_header_indicators()
        self._apply_filter_and_sort()

    def _update_header_indicators(self):
        """컬럼 헤더 텍스트의 정렬 화살표(▲/▼/↕) 인디케이터 업데이트"""
        headers = {
            "type": "구분",
            "code": "코드",
            "name": "원료명",
            "ingredients": "대표 전성분 (배합비 순)"
        }
        for col_name, text in headers.items():
            if self.current_sort_col == col_name or (self.current_sort_col in ("single_first", "complex_first") and col_name == "type"):
                arrow = " ▼" if self.sort_reverse or self.current_sort_col == "complex_first" else " ▲"
                self.material_tree.heading(col_name, text=f"{text}{arrow}")
            else:
                self.material_tree.heading(col_name, text=f"{text} ↕")

    def _apply_filter_and_sort(self):
        """인메모리에서 단일/복합 필터링 및 다기준 고속 정렬을 실행하고 Treeview를 즉각 갱신합니다 (0.001초)."""
        # 1. 유형 필터 적용
        items = list(self.raw_search_results)
        if self.current_type_filter == "단일 원료":
            items = [item for item in items if not item["is_blend"]]
        elif self.current_type_filter == "복합 원료":
            items = [item for item in items if item["is_blend"]]

        # 2. 정렬 키 함수 정의
        if self.current_sort_col == "code":
            items.sort(key=lambda x: self._natural_sort_key(x["code"]), reverse=self.sort_reverse)
        elif self.current_sort_col in ("type", "single_first"):
            # 단일(0) -> 복합(1) -> 코드순
            items.sort(key=lambda x: (1 if x["is_blend"] else 0, self._natural_sort_key(x["code"])), reverse=self.sort_reverse)
        elif self.current_sort_col == "complex_first":
            # 복합(0) -> 단일(1) -> 성분개수 많은순 -> 코드순
            items.sort(key=lambda x: (0 if x["is_blend"] else 1, -x["ing_count"], self._natural_sort_key(x["code"])))
        elif self.current_sort_col == "name":
            items.sort(key=lambda x: (x["name"].lower(), self._natural_sort_key(x["code"])), reverse=self.sort_reverse)
        elif self.current_sort_col == "ingredients":
            items.sort(key=lambda x: (x["ing_str"].lower(), self._natural_sort_key(x["code"])), reverse=self.sort_reverse)
        elif self.current_sort_col == "ing_count":
            items.sort(key=lambda x: (x["ing_count"], self._natural_sort_key(x["code"])), reverse=self.sort_reverse)
        else:
            items.sort(key=lambda x: self._natural_sort_key(x["code"]))

        self.filtered_materials = items

        # 3. Treeview 렌더링
        for item_id in self.material_tree.get_children():
            self.material_tree.delete(item_id)

        theme = ctk.get_appearance_mode().lower()
        odd_bg = "#F9FAFB" if theme == 'light' else "#282A2E"
        even_bg = "#FFFFFF" if theme == 'light' else "#202124"
        tree_fg = "#1F2937" if theme == 'light' else "#E8EAED"
        
        self.material_tree.tag_configure("oddrow", background=odd_bg, foreground=tree_fg)
        self.material_tree.tag_configure("evenrow", background=even_bg, foreground=tree_fg)
        self.material_tree.tag_configure("blend_tag", foreground="#0284C7" if theme == 'light' else "#38BDF8")

        for idx, item in enumerate(items):
            tag = 'oddrow' if idx % 2 == 0 else 'evenrow'
            self.material_tree.insert(
                "",
                "end",
                iid=item["id"],
                tags=(tag,),
                values=(item["type_text"], item["code"], item["name"], item["ing_str"])
            )

        # 카운트 갱신
        filter_str = f" ({self.current_type_filter})" if self.current_type_filter != "전체" else ""
        self.count_label.configure(text=f"검색 결과: 총 {len(items)}건{filter_str}")

        # 첫 번째 행 자동 선택 및 상세정보 표시
        if items:
            first_id = items[0]["id"]
            self.material_tree.selection_set(first_id)
            self.material_tree.focus(first_id)
            self.on_material_select()
        else:
            self.ingredient_details_textbox.configure(state="normal")
            self.ingredient_details_textbox.delete("1.0", "end")
            self.ingredient_details_textbox.insert("1.0", "일치하는 원료가 없습니다.")
            self.ingredient_details_textbox.configure(state="disabled")

    def on_material_select(self, event=None):
        """트리뷰에서 원료 선택 시 전성분 상세 목록을 텍스트박스에 표시합니다."""
        selected_item = self.material_tree.selection()
        self.ingredient_details_textbox.configure(state="normal")
        self.ingredient_details_textbox.delete("1.0", "end")

        if not selected_item:
            self.ingredient_details_textbox.configure(state="disabled")
            return

        try:
            material_id = int(selected_item[0])
            # 캐시된 목록에서 즉시 탐색 (DB 쿼리 없이 0ms 응답)
            matched = next((item for item in self.filtered_materials if item["id"] == material_id), None)
            if matched:
                self.ingredient_details_textbox.insert("1.0", matched["full_ing_str"])
            else:
                self.ingredient_details_textbox.insert("1.0", self.texts.get('no_ingredients_registered', '등록된 전성분이 없습니다.'))
        except Exception as e:
            self.ingredient_details_textbox.insert("1.0", f"전성분 조회 오류: {e}")
        finally:
            self.ingredient_details_textbox.configure(state="disabled")

    def on_double_click_add(self, event):
        """Treeview에서 항목을 더블클릭하여 바로 추가합니다."""
        tree = event.widget
        item_id = tree.identify_row(event.y)
        if not item_id:
            return

        tree.selection_set(item_id)
        tree.focus(item_id)
        self.on_add()

    def on_add(self):
        """'추가' 버튼 클릭 시 콜백 함수를 호출하여 처방/견적서에 원료를 추가합니다."""
        selected_item = self.material_tree.selection()
        if not selected_item:
            messagebox.showwarning(
                self.texts.get('selection_error', '선택 오류'),
                self.texts.get('select_material_to_add', '목록에서 추가할 원료를 선택하세요.'),
                parent=self
            )
            return

        material_id = int(selected_item[0])
        self.on_add_callback(material_id)

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


class ClientQuickSearchPopup(ctk.CTkToplevel):
    """[v65 초고속 거래처 검색 & 선택 팝업] 수천 개 거래처 실시간 검색, 모든 유형별 필터 가로 스크롤, 휠 스크롤 4배 가속 및 선택된 거래처 자동 활성화"""
    def __init__(self, master, on_select_callback, initial_type=None, initial_client=None):
        super().__init__(master)
        self.withdraw()
        self.on_select_callback = on_select_callback
        self.initial_type = initial_type
        self.initial_client = initial_client

        self.title("거래처 빠른 검색")
        self.geometry("780x560")
        self.minsize(680, 440)

        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(2, weight=1)

        self.raw_clients = []
        self.filtered_clients = []
        self.search_timer = None

        # --- 1. 상단 검색바 ---
        search_frame = ctk.CTkFrame(self, fg_color="transparent")
        search_frame.grid(row=0, column=0, padx=12, pady=(10, 4), sticky="ew")
        search_frame.grid_columnconfigure(1, weight=1)

        ctk.CTkLabel(search_frame, text="거래처 검색:", font=ctk.CTkFont(weight="bold")).grid(row=0, column=0, padx=(0, 5))
        self.search_entry = ctk.CTkEntry(search_frame, placeholder_text="거래처명, 담당자명, 연락처, 주소 검색...")
        self.search_entry.grid(row=0, column=1, padx=5, sticky="ew")
        self.search_entry.bind("<KeyRelease>", self._on_search_key_release)
        self.search_entry.bind("<Return>", lambda e: self._on_confirm_select())

        ctk.CTkButton(search_frame, text="검색", width=60, command=self._apply_filter).grid(row=0, column=2, padx=3)
        ctk.CTkButton(search_frame, text="초기화", width=60, fg_color="gray50", hover_color="gray40", command=self._reset_search).grid(row=0, column=3, padx=3)

        # --- 2. 유형 필터 툴바 (모든 거래처 카테고리 가로 스크롤 지원) ---
        filter_toolbar = ctk.CTkFrame(self, fg_color=("gray92", "#242526"), corner_radius=6)
        filter_toolbar.grid(row=1, column=0, padx=12, pady=4, sticky="ew")

        filter_scroll = ctk.CTkScrollableFrame(filter_toolbar, orientation="horizontal", height=34, fg_color="transparent")
        filter_scroll.pack(side="left", fill="x", expand=True, padx=4, pady=2)

        unique_types = ["전체"] + db_manager.get_unique_client_types()
        self.type_filter_seg = ctk.CTkSegmentedButton(
            filter_scroll,
            values=unique_types,
            command=self._on_type_changed,
            height=26,
            font=ctk.CTkFont(size=11)
        )
        default_type = initial_type if (initial_type and initial_type in unique_types) else "전체"
        self.type_filter_seg.set(default_type)
        self.type_filter_seg.pack(side="left", padx=2, pady=2)

        self.count_label = ctk.CTkLabel(filter_toolbar, text="총 0건", font=ctk.CTkFont(size=11), text_color=("gray40", "gray70"))
        self.count_label.pack(side="right", padx=12, pady=2)

        # --- 3. 거래처 목록 Treeview ---
        tree_frame = ctk.CTkFrame(self, fg_color="transparent")
        tree_frame.grid(row=2, column=0, padx=12, pady=4, sticky="nsew")
        tree_frame.grid_columnconfigure(0, weight=1)
        tree_frame.grid_rowconfigure(0, weight=1)

        tree_cols = ("type", "name", "manager", "phone", "address")
        self.client_tree = ttk.Treeview(tree_frame, columns=tree_cols, show="headings", selectmode="browse")
        self.client_tree.heading("type", text="구분"); self.client_tree.column("type", width=80, anchor="center")
        self.client_tree.heading("name", text="거래처명"); self.client_tree.column("name", width=170)
        self.client_tree.heading("manager", text="담당자"); self.client_tree.column("manager", width=90)
        self.client_tree.heading("phone", text="연락처"); self.client_tree.column("phone", width=110)
        self.client_tree.heading("address", text="주소"); self.client_tree.column("address", width=220, stretch=True)
        self.client_tree.grid(row=0, column=0, sticky="nsew")

        scrollbar = ttk.Scrollbar(tree_frame, orient="vertical", command=self.client_tree.yview)
        self.client_tree.configure(yscrollcommand=scrollbar.set)
        scrollbar.grid(row=0, column=1, sticky="ns")

        self.client_tree.bind("<Double-1>", lambda e: self._on_confirm_select())
        self.client_tree.bind("<Return>", lambda e: self._on_confirm_select())

        # 휠 4배 가속 스크롤
        def _fast_scroll(event):
            if event.delta:
                self.client_tree.yview_scroll(-1 * int(event.delta / 120 * 4), "units")
                return "break"
        self.client_tree.bind("<MouseWheel>", _fast_scroll)

        # --- 4. 하단 버튼 ---
        btn_frame = ctk.CTkFrame(self, fg_color="transparent")
        btn_frame.grid(row=3, column=0, pady=(6, 12))
        ctk.CTkButton(btn_frame, text="✔ 거래처 선택", font=ctk.CTkFont(weight="bold"), command=self._on_confirm_select).pack(side="left", padx=6)
        ctk.CTkButton(btn_frame, text="닫기", fg_color="gray50", hover_color="gray40", command=self.destroy).pack(side="left", padx=6)

        self._load_clients_data()

        # 중앙 배치 및 포커스
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
        self.after(50, lambda: self.search_entry.focus_set())
        self.after(50, lambda: self.search_entry.focus_force())

    def _load_clients_data(self):
        """DB에서 활성 거래처 전체 로드 (0.01초 캐싱)"""
        session = db_manager.get_session()
        try:
            from database.models import Client
            clients = session.query(Client).filter_by(is_active=True).order_by(Client.name).all()
            self.raw_clients = [
                {
                    "id": c.id,
                    "name": c.name or "",
                    "type": c.client_type or "",
                    "manager": c.manager_name or "-",
                    "phone": c.phone or "-",
                    "address": c.address or "-"
                }
                for c in clients
            ]

            # 만약 initial_client가 있고 initial_type이 없었다면 해당 업체의 유형으로 탭 자동 동기화
            if self.initial_client and (not self.initial_type or self.initial_type == "전체"):
                found_c = next((c for c in self.raw_clients if c["name"].strip().lower() == self.initial_client.strip().lower()), None)
                if found_c and found_c.get("type"):
                    self.type_filter_seg.set(found_c["type"])

            self._apply_filter()
        finally:
            session.close()

    def _on_search_key_release(self, event=None):
        if event and event.keysym in ("Return", "Escape", "Up", "Down"):
            return
        self.initial_client = None  # 직접 타이핑 검색 시에는 자동 지정 해제
        if self.search_timer:
            self.after_cancel(self.search_timer)
        self.search_timer = self.after(150, self._apply_filter)

    def _on_type_changed(self, selected_type):
        self._apply_filter()

    def _reset_search(self):
        self.initial_client = None
        self.search_entry.delete(0, "end")
        self.type_filter_seg.set("전체")
        self._apply_filter()
        self.after(30, lambda: self.search_entry.focus_set())

    def _apply_filter(self):
        """인메모리에서 실시간 필터링 및 Treeview 갱신 (0.0001초)"""
        q = self.search_entry.get().strip().lower()
        selected_type = self.type_filter_seg.get()

        matched = []
        for c in self.raw_clients:
            if selected_type != "전체" and c["type"] != selected_type:
                continue
            if q:
                if (q not in c["name"].lower()) and (q not in c["manager"].lower()) and (q not in c["phone"].lower()) and (q not in c["address"].lower()):
                    continue
            matched.append(c)

        self.filtered_clients = matched

        for item_id in self.client_tree.get_children():
            self.client_tree.delete(item_id)

        theme = ctk.get_appearance_mode().lower()
        odd_bg = "#F9FAFB" if theme == 'light' else "#282A2E"
        even_bg = "#FFFFFF" if theme == 'light' else "#202124"
        tree_fg = "#1F2937" if theme == 'light' else "#E8EAED"
        self.client_tree.tag_configure("oddrow", background=odd_bg, foreground=tree_fg)
        self.client_tree.tag_configure("evenrow", background=even_bg, foreground=tree_fg)

        for idx, c in enumerate(matched):
            tag = 'oddrow' if idx % 2 == 0 else 'evenrow'
            self.client_tree.insert(
                "",
                "end",
                iid=str(c["id"]),
                tags=(tag,),
                values=(c["type"], c["name"], c["manager"], c["phone"], c["address"])
            )

        self.count_label.configure(text=f"검색 결과: 총 {len(matched)}건")

        # 선택된 거래처(initial_client)가 있으면 해당 항목으로 즉시 활성화 및 화면 스크롤
        target_iid = None
        if self.initial_client:
            for c in matched:
                if c["name"].strip().lower() == self.initial_client.strip().lower():
                    target_iid = str(c["id"])
                    break

        if target_iid and self.client_tree.exists(target_iid):
            self.client_tree.selection_set(target_iid)
            self.client_tree.focus(target_iid)
            self.client_tree.see(target_iid)
        elif matched:
            first_iid = str(matched[0]["id"])
            self.client_tree.selection_set(first_iid)
            self.client_tree.focus(first_iid)
            self.client_tree.see(first_iid)

    def _on_confirm_select(self):
        selected = self.client_tree.selection()
        if not selected:
            messagebox.showwarning("선택 필요", "선택할 거래처를 목록에서 클릭하세요.", parent=self)
            return

        client_id = int(selected[0])
        matched = next((c for c in self.filtered_clients if c["id"] == client_id), None)
        if matched:
            self.on_select_callback(matched["name"], matched["type"])
            self.destroy()
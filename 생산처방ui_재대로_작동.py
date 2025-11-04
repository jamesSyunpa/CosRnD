import customtkinter as ctk
from tkinter import ttk

ctk.set_appearance_mode("light")
ctk.set_default_color_theme("blue")

class ProcessTemplateApp(ctk.CTk):
    def __init__(self):
        super().__init__()
        self.title("생산처방 템플릿 (확장형)")
        self.geometry("1400x800")
        self.minsize(1000, 600)
        self.configure(padx=20, pady=20)

        # === 전체 프레임 ===
        self.grid_rowconfigure(0, weight=1)
        self.grid_columnconfigure(0, weight=1)

        main_frame = ctk.CTkFrame(self)
        main_frame.grid(row=0, column=0, sticky="nsew")

        main_frame.grid_columnconfigure(0, weight=1)
        main_frame.grid_columnconfigure(1, weight=2)
        main_frame.grid_rowconfigure(0, weight=1)

        # 왼쪽: 처방내용
        left_frame = ctk.CTkFrame(main_frame)
        left_frame.grid(row=0, column=0, padx=(10,5), pady=10, sticky="nsew")
        left_frame.grid_rowconfigure(1, weight=1)

        ctk.CTkLabel(left_frame, text="처방내용", font=("맑은 고딕", 16, "bold")).grid(row=0, column=0, pady=(10,5))

        self.recipe_text = ctk.CTkTextbox(left_frame)
        self.recipe_text.grid(row=1, column=0, padx=10, pady=10, sticky="nsew")

        # 오른쪽: 제조공정 / 공정검사
        right_frame = ctk.CTkFrame(main_frame)
        right_frame.grid(row=0, column=1, padx=(5,10), pady=10, sticky="nsew")
        right_frame.grid_rowconfigure(1, weight=1)

        ctk.CTkLabel(right_frame, text="제조공정 / 공정검사", font=("맑은 고딕", 16, "bold")).grid(row=0, column=0, columnspan=2, pady=10)

        # 테이블 프레임
        table_frame = ctk.CTkFrame(right_frame)
        table_frame.grid(row=1, column=0, columnspan=2, padx=10, pady=10, sticky="nsew")
        table_frame.grid_rowconfigure(0, weight=1)
        table_frame.grid_columnconfigure(0, weight=1)

        # Treeview 생성
        columns = ("제조공정", "공정검사")
        self.tree = ttk.Treeview(table_frame, columns=columns, show="headings", height=12)
        self.tree.heading("제조공정", text="제조공정")
        self.tree.heading("공정검사", text="공정검사")
        self.tree.column("제조공정", anchor="nw", width=300)
        self.tree.column("공정검사", anchor="nw", width=300)
        self.tree.grid(row=0, column=0, sticky="nsew")
        
        # 스타일 설정
        style = ttk.Style()
        style.configure('Treeview', 
                       wraplength=280, 
                       padding=5, 
                       borderwidth=2, 
                       relief='solid',
                       rowheight=30)
        style.configure('Treeview.Treeheading', 
                       padding=5,
                       borderwidth=2,
                       relief='solid')
        style.map('Treeview',
                  background=[('selected', '#0078d4')],
                  foreground=[('selected', 'white')])
        
        # 행의 배경색 교대로 설정
        self.tree.tag_configure('oddrow', background='#f0f0f0')
        self.tree.tag_configure('evenrow', background='white')

        scrollbar = ttk.Scrollbar(table_frame, orient="vertical", command=self.tree.yview)
        scrollbar.grid(row=0, column=1, sticky="ns")
        self.tree.configure(yscroll=scrollbar.set)

        # 버튼 프레임
        button_frame = ctk.CTkFrame(right_frame)
        button_frame.grid(row=2, column=0, columnspan=2, sticky="ew", pady=(5,10))
        button_frame.grid_columnconfigure(0, weight=1)

        add_button = ctk.CTkButton(button_frame, text="행 추가", command=self.add_row, width=100)
        add_button.grid(row=0, column=0, padx=5, pady=5, sticky="w")

        delete_button = ctk.CTkButton(button_frame, text="선택 삭제", command=self.delete_row, width=100)
        delete_button.grid(row=0, column=1, padx=5, pady=5, sticky="w")

        auto_size_button = ctk.CTkButton(button_frame, text="자동 크기조정", command=self.auto_size_all, width=120, fg_color="green")
        auto_size_button.grid(row=0, column=2, padx=5, pady=5, sticky="w")

        # 이벤트 바인딩
        self.tree.bind("<Double-1>", self.start_edit)
        self.tree.bind("<Configure>", self._on_tree_resize)

        self.edit_entry = None

    def add_row(self):
        """새 행 추가"""
        row_count = len(self.tree.get_children())
        tag = 'evenrow' if row_count % 2 == 0 else 'oddrow'
        self.tree.insert("", "end", values=("", ""), tags=(tag,))
        self.after(100, self.auto_size_all)

    def delete_row(self):
        """선택된 행 삭제"""
        selected = self.tree.selection()
        for item in selected:
            self.tree.delete(item)

    def start_edit(self, event):
        """셀 더블클릭 시 직접 편집 시작"""
        item = self.tree.identify_row(event.y)
        col = self.tree.identify_column(event.x)
        
        if not item or not col:
            return

        try:
            col_idx = int(col.replace('#', '')) - 1
        except (ValueError, IndexError):
            return
            
        if col_idx < 0 or col_idx >= len(self.tree["columns"]):
            return
            
        col_name = self.tree["columns"][col_idx]
        
        # 공정검사 칼럼이면 테이블 편집 창 열기
        if col_name == "공정검사":
            self.open_inspection_editor(item)
        else:
            # 제조공정은 multiline textbox
            self.open_process_editor(item)

    def open_process_editor(self, item):
        """제조공정 편집 (multiline textbox)"""
        current_value = self.tree.set(item, "제조공정")
        bbox = self.tree.bbox(item, "#1")
        if not bbox:
            return

        x, y, width, height = bbox

        if self.edit_entry:
            self.edit_entry.destroy()

        self.edit_entry = ctk.CTkTextbox(self.tree, width=width, height=max(height, 80), wrap="word")
        self.edit_entry.insert("1.0", current_value)
        self.edit_entry.place(x=self.tree.winfo_x() + x, y=self.tree.winfo_y() + y)
        self.edit_entry.focus()

        def save_value(event=None):
            new_value = self.edit_entry.get("1.0", "end-1c").strip()
            new_value = new_value.replace("가", "")
            new_value = new_value.replace('"', '')
            new_value = new_value.strip()
            
            self.tree.set(item, "제조공정", new_value)
            if self.edit_entry:
                self.edit_entry.destroy()
            self.edit_entry = None
            self.after(50, self.auto_size_all)

        def cancel_edit(event=None):
            if self.edit_entry:
                self.edit_entry.destroy()
                self.edit_entry = None

        def handle_key(event):
            if event.keysym == "Return" and not event.state & 0x1:
                save_value()
                return "break"
            elif event.keysym == "Escape":
                cancel_edit()
                return "break"

        self.edit_entry.bind("<Key-Return>", handle_key)
        self.edit_entry.bind("<Escape>", cancel_edit)
        self.edit_entry.bind("<FocusOut>", save_value)

    def open_inspection_editor(self, item):
        """공정검사 편집 (체크박스 폼)"""
        current_value = self.tree.set(item, "공정검사")
        
        # 기존 값 파싱 (줄바꿈으로 분리)
        checked_fields = set()
        if current_value:
            for line in current_value.split('\n'):
                line = line.strip()
                if line.startswith("시간"):
                    checked_fields.add("시간")
                elif line.startswith("온도"):
                    checked_fields.add("온도")
                elif line.startswith("H/M"):
                    checked_fields.add("H/M")
                elif line.startswith("P/M"):
                    checked_fields.add("P/M")

        # 편집 창
        edit_window = ctk.CTkToplevel(self)
        edit_window.title("공정검사 편집")
        edit_window.geometry("400x300")
        edit_window.resizable(False, False)

        edit_window.grid_rowconfigure(1, weight=1)
        edit_window.grid_columnconfigure(0, weight=1)

        # 설명
        ctk.CTkLabel(edit_window, text="필요한 공정검사 항목을 선택하세요:", font=("맑은 고딕", 12, "bold")).grid(row=0, column=0, pady=(15, 10), padx=20, sticky="w")

        # 스크롤 프레임
        scroll_frame = ctk.CTkScrollableFrame(edit_window)
        scroll_frame.grid(row=1, column=0, padx=20, pady=10, sticky="nsew")

        # 체크박스 항목들 - 실제 출력 형식 정의
        inspection_items = [
            ("시간", "시간", "시간 :"),
            ("온도", "온도", "온도 :             ℃"),
            ("호모믹서(H/M)", "H/M", "H/M:              rpm"),
            ("패들믹서(P/M)", "P/M", "P/M:              rpm")
        ]

        check_vars = {}
        for label, key, output_format in inspection_items:
            var = ctk.BooleanVar(value=key in checked_fields)
            check_vars[key] = (var, output_format)
            checkbox = ctk.CTkCheckBox(scroll_frame, text=label, variable=var, font=("맑은 고딕", 11))
            checkbox.pack(anchor="w", pady=8)

        # 버튼 프레임
        btn_frame = ctk.CTkFrame(edit_window)
        btn_frame.grid(row=2, column=0, padx=20, pady=15, sticky="ew")
        btn_frame.grid_columnconfigure(0, weight=1)

        def save_inspection():
            # 선택된 항목들을 형식에 맞춰 저장
            selected_lines = []
            for key, (var, output_format) in check_vars.items():
                if var.get():
                    selected_lines.append(output_format)
            
            final_value = "\n".join(selected_lines)
            self.tree.set(item, "공정검사", final_value)
            edit_window.destroy()
            self.after(50, self.auto_size_all)

        ctk.CTkButton(btn_frame, text="저장", command=save_inspection, width=100, fg_color="green").pack(side="left", padx=5)
        ctk.CTkButton(btn_frame, text="취소", command=edit_window.destroy, width=100).pack(side="left", padx=5)

    def auto_size_all(self):
        """자동으로 컬럼 너비와 행 높이를 조정"""
        self.auto_size_columns()
        self.auto_size_rows()

    def auto_size_columns(self):
        """컬럼 너비 자동 조정"""
        for col_name in ["제조공정", "공정검사"]:
            max_width = len(col_name) * 8 + 40
            
            for item in self.tree.get_children():
                value = str(self.tree.set(item, col_name))
                lines = value.split('\n')
                longest_line = max(lines, key=len) if lines else ""
                width = len(longest_line) * 7 + 40
                max_width = max(max_width, width)
            
            final_width = min(max_width, 600)
            self.tree.column(col_name, width=final_width)
            
            style = ttk.Style()
            style.configure('Treeview', wraplength=final_width - 30, padding=5)

    def auto_size_rows(self):
        """행 높이 자동 조정"""
        if not self.tree.get_children():
            return

        max_height = 25
        
        for item in self.tree.get_children():
            max_lines = 1
            for col in self.tree["columns"]:
                value = str(self.tree.set(item, col))
                lines = value.count('\n') + 1
                max_lines = max(max_lines, lines)
            
            item_height = 20 + (max_lines - 1) * 18
            max_height = max(max_height, item_height)

        style = ttk.Style()
        style.configure('Treeview', rowheight=max_height)

    def _on_tree_resize(self, event):
        """테이블 리사이즈 시 컬럼 자동조정"""
        self.after(50, self.auto_size_columns)

    def show_preview(self):
        preview = ctk.CTkToplevel(self)
        preview.title("미리보기")
        preview.geometry("900x600")
        preview.minsize(700, 500)

        preview.grid_rowconfigure(2, weight=1)
        preview.grid_columnconfigure(0, weight=1)

        # 처방내용
        ctk.CTkLabel(preview, text="처방내용", font=("맑은 고딕", 14, "bold")).grid(row=0, column=0, pady=(10,5))
        recipe_text = ctk.CTkTextbox(preview, height=120)
        recipe_text.grid(row=1, column=0, sticky="ew", padx=20)
        recipe_text.insert("1.0", self.recipe_text.get("1.0", "end"))
        recipe_text.configure(state="disabled")

        # 제조공정 / 공정검사
        ctk.CTkLabel(preview, text="제조공정 / 공정검사", font=("맑은 고딕", 14, "bold")).grid(row=2, column=0, pady=(10,5))

        frame = ctk.CTkFrame(preview)
        frame.grid(row=3, column=0, sticky="nsew", padx=20, pady=10)
        frame.grid_rowconfigure(0, weight=1)
        frame.grid_columnconfigure(0, weight=1)

        tree = ttk.Treeview(frame, columns=("제조공정", "공정검사"), show="headings")
        tree.heading("제조공정", text="제조공정")
        tree.heading("공정검사", text="공정검사")
        tree.column("제조공정", anchor="nw", width=self.tree.column("제조공정", "width"))
        tree.column("공정검사", anchor="nw", width=self.tree.column("공정검사", "width"))

        for item in self.tree.get_children():
            values = (self.tree.set(item, "제조공정"), self.tree.set(item, "공정검사"))
            tree.insert("", "end", values=values)

        tree.grid(row=0, column=0, sticky="nsew")
        scrollbar = ttk.Scrollbar(frame, orient="vertical", command=tree.yview)
        scrollbar.grid(row=0, column=1, sticky="ns")
        tree.configure(yscroll=scrollbar.set)

# 실행
if __name__ == "__main__":
    app = ProcessTemplateApp()
    app.mainloop()

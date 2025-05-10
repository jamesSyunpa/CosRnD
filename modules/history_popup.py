import customtkinter as ctk
import re

class HistoryPopup(ctk.CTkToplevel):
    """
    개별 항목 또는 전체 항목의 변경 이력을 시간순으로 보여주는 팝업 창
    """

    def __init__(self, master, title, items, item_name_key='name', item_code_key=None):
        super().__init__(master)
        self.items = items
        self.item_name_key = item_name_key
        self.item_code_key = item_code_key

        self.title(title)
        self.geometry("800x700")
        self.transient(master)
        self.grab_set()

        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(1, weight=1)

        self.all_log_entries = []
        self.setup_ui()
        self.prepare_and_load_history()

    def setup_ui(self):
        """UI 기본 구조를 설정합니다."""
        search_frame = ctk.CTkFrame(self, fg_color="transparent")
        search_frame.grid(row=0, column=0, padx=15, pady=(15, 0), sticky="ew")
        search_frame.grid_columnconfigure(1, weight=1)

        ctk.CTkLabel(search_frame, text="검색:").grid(row=0, column=0, padx=(0, 5))
        self.search_entry = ctk.CTkEntry(search_frame)
        self.search_entry.grid(row=0, column=1, sticky="ew")
        self.search_entry.bind("<Return>", lambda event: self.filter_history())

        search_button = ctk.CTkButton(search_frame, text="검색", width=80, command=self.filter_history)
        search_button.grid(row=0, column=2, padx=5)

        reset_button = ctk.CTkButton(search_frame, text="초기화", width=80, command=self.reset_search)
        reset_button.grid(row=0, column=3, padx=(0, 5))

        self.scrollable_frame = ctk.CTkScrollableFrame(self, label_text="변경 이력 목록")
        self.scrollable_frame.grid(row=1, column=0, padx=15, pady=15, sticky="nsew")
        self.scrollable_frame.grid_columnconfigure(0, weight=1)

        close_button = ctk.CTkButton(self, text="닫기", command=self.destroy)
        close_button.grid(row=2, column=0, padx=15, pady=(0, 15))

    def prepare_and_load_history(self):
        """데이터베이스에서 이력을 불러와 파싱하고 UI에 표시합니다."""
        self.all_log_entries = []
        for item in self.items:
            if not item.change_log:
                continue

            item_name = getattr(item, self.item_name_key, 'N/A')
            item_identifier = item_name
            if self.item_code_key:
                item_code = getattr(item, self.item_code_key, None)
                if item_code:
                    item_identifier = f"{item_name} ({item_code})"

            log_blocks = item.change_log.strip().split('\n\n')
            for block in log_blocks:
                match = re.match(r"\[(.*?)\] by (.*?)\n((?:- .*\n?)*)", block, re.DOTALL)
                if match:
                    timestamp_str, user, changes = match.groups()
                    self.all_log_entries.append({
                        "timestamp": timestamp_str,
                        "user": user,
                        "changes": changes.strip(),
                        "identifier": item_identifier
                    })

        # 시간순으로 정렬 (최신이 위로)
        self.all_log_entries.sort(key=lambda x: x['timestamp'], reverse=True)
        self.display_history(self.all_log_entries)

    def display_history(self, log_entries):
        """파싱된 로그 항목들을 UI에 표시합니다."""
        for widget in self.scrollable_frame.winfo_children():
            widget.destroy()

        if not log_entries:
            message = "검색 결과가 없습니다." if self.search_entry.get() else "저장된 이력이 없습니다."
            ctk.CTkLabel(self.scrollable_frame, text=message).pack(pady=20)
            return

        for entry in log_entries:
            entry_frame = ctk.CTkFrame(self.scrollable_frame, border_width=1)
            entry_frame.pack(fill="x", padx=10, pady=10)
            entry_frame.grid_columnconfigure(1, weight=1)

            header_text = f"항목: {entry['identifier']}"
            date_text = f"변경일: {entry['timestamp']} (작업자: {entry['user']})"

            header_label = ctk.CTkLabel(entry_frame, text=header_text, font=ctk.CTkFont(size=14, weight="bold"))
            header_label.grid(row=0, column=0, columnspan=2, padx=10, pady=(10, 2), sticky="w")
            date_label = ctk.CTkLabel(entry_frame, text=date_text, font=ctk.CTkFont(size=11), text_color="gray")
            date_label.grid(row=1, column=0, columnspan=2, padx=10, pady=(0, 10), sticky="w")

            log_text = ctk.CTkTextbox(entry_frame, height=100, wrap="word", fg_color="transparent")
            log_text.grid(row=2, column=0, columnspan=2, padx=10, pady=(0, 10), sticky="ew")
            log_text.insert("1.0", entry['changes'])
            log_text.configure(state="disabled")

    def filter_history(self):
        """검색어에 따라 이력을 필터링하여 보여줍니다."""
        search_term = self.search_entry.get().lower()
        if not search_term:
            self.display_history(self.all_log_entries)
            return

        filtered_entries = [
            entry for entry in self.all_log_entries
            if search_term in entry['identifier'].lower() or search_term in entry['changes'].lower() or search_term in entry['user'].lower()
        ]
        self.display_history(filtered_entries)

    def reset_search(self):
        """검색창을 비우고 전체 목록을 다시 불러옵니다."""
        self.search_entry.delete(0, "end")
        self.filter_history()
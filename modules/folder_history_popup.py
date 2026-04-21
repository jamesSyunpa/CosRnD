import customtkinter as ctk
import sys
import os

# 프로젝트 루트 경로를 sys.path에 추가 (상대 경로 import를 위함)
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if PROJECT_ROOT not in sys.path:
    sys.path.append(PROJECT_ROOT)

from database.db_manager import db_manager
from database.models import Formulation, or_

class FolderHistoryPopup(ctk.CTkToplevel):
    """
    특정 실험품명(폴더)에 속한 모든 처방의 변경 이력을
    시간 순서대로 보여주는 팝업 창
    """

    def __init__(self, master, folder_name):
        super().__init__(master)
        self.folder_name = folder_name

        self.title(f"'{folder_name}' 전체 이력")
        self.geometry("800x700")
        self.transient(master)
        self.grab_set()

        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(1, weight=1) # 스크롤 프레임을 위한 행

        self.setup_ui()
        self.load_history()

    def setup_ui(self):
        """UI 기본 구조를 설정합니다."""
        # --- 검색 프레임 ---
        search_frame = ctk.CTkFrame(self, fg_color="transparent")
        search_frame.grid(row=0, column=0, padx=15, pady=(15, 0), sticky="ew")
        search_frame.grid_columnconfigure(1, weight=1)

        ctk.CTkLabel(search_frame, text="검색:").grid(row=0, column=0, padx=(0, 5))
        self.search_entry = ctk.CTkEntry(search_frame)
        self.search_entry.grid(row=0, column=1, sticky="ew")
        self.search_entry.bind("<Return>", lambda event: self.load_history())

        search_button = ctk.CTkButton(search_frame, text="검색", width=80, command=self.load_history)
        search_button.grid(row=0, column=2, padx=5)

        reset_button = ctk.CTkButton(search_frame, text="초기화", width=80, command=self.reset_search)
        reset_button.grid(row=0, column=3, padx=(0, 5))

        # --- 스크롤 프레임 ---
        self.scrollable_frame = ctk.CTkScrollableFrame(self, label_text="변경 이력 목록")
        self.scrollable_frame.grid(row=1, column=0, padx=15, pady=15, sticky="nsew")
        self.scrollable_frame.grid_columnconfigure(0, weight=1)

        close_button = ctk.CTkButton(self, text="닫기", command=self.destroy)
        close_button.grid(row=2, column=0, padx=15, pady=(0, 15))

    def load_history(self, event=None):
        """데이터베이스에서 이력을 불러와 UI에 표시합니다."""
        search_term = self.search_entry.get().strip()

        # 기존 위젯 삭제
        for widget in self.scrollable_frame.winfo_children():
            widget.destroy()

        session = db_manager.get_session()
        try:
            # 생성된 시간 순서대로 모든 버전을 가져옵니다.
            query = session.query(Formulation).filter_by(
                experiment_name=self.folder_name
            )

            # 검색어가 있으면 필터링 조건 추가
            if search_term:
                search_pattern = f"%{search_term}%"
                query = query.filter(
                    or_(
                        Formulation.lab_no.ilike(search_pattern),
                        Formulation.change_log.ilike(search_pattern),
                        Formulation.experiment_comment.ilike(search_pattern)
                    )
                )

            formulations = query.order_by(Formulation.created_at).all()

            if not formulations:
                message = "검색 결과가 없습니다." if search_term else "저장된 이력이 없습니다."
                ctk.CTkLabel(self.scrollable_frame, text=message).pack(pady=20)
                return

            for form in formulations:
                # 각 버전을 담을 프레임
                entry_frame = ctk.CTkFrame(self.scrollable_frame, border_width=1)
                entry_frame.pack(fill="x", padx=10, pady=10)
                entry_frame.grid_columnconfigure(1, weight=1)

                # --- 버전 정보 (LAB NO, 차수, 날짜) ---
                header_text = f"LAB NO: {form.lab_no or 'N/A'} (차수: {form.revision or 'N/A'})"
                date_text = f"저장일: {form.created_at.strftime('%Y-%m-%d %H:%M:%S')}"
                
                header_label = ctk.CTkLabel(entry_frame, text=header_text, font=ctk.CTkFont(size=14, weight="bold"))
                header_label.grid(row=0, column=0, columnspan=2, padx=10, pady=(10, 5), sticky="w")
                date_label = ctk.CTkLabel(entry_frame, text=date_text, font=ctk.CTkFont(size=11), text_color="gray")
                date_label.grid(row=1, column=0, columnspan=2, padx=10, pady=(0, 10), sticky="w")

                # 각 항목을 표시할 때 사용할 행 번호
                row_counter = 2

                # --- 변경 이력 ---
                if form.change_log:
                    log_label = ctk.CTkLabel(entry_frame, text="[변경 이력]", font=ctk.CTkFont(weight="bold"), anchor="w")
                    log_label.grid(row=row_counter, column=0, columnspan=2, padx=10, pady=(5, 2), sticky="w")
                    row_counter += 1 # 라벨 다음 행
                    log_text = ctk.CTkTextbox(entry_frame, height=120, wrap="word", fg_color="transparent")
                    log_text.grid(row=row_counter, column=0, columnspan=2, padx=10, pady=(0, 10), sticky="ew")
                    log_text.insert("1.0", form.change_log)
                    log_text.configure(state="disabled")
                    row_counter += 1

                # --- 품평결과 및 특이사항 ---
                if form.experiment_comment:
                    comment_label = ctk.CTkLabel(entry_frame, text="[품평결과 및 특이사항]", font=ctk.CTkFont(weight="bold"), anchor="w")
                    comment_label.grid(row=row_counter, column=0, columnspan=2, padx=10, pady=(5, 2), sticky="w")
                    row_counter += 1 # 라벨 다음 행
                    comment_text = ctk.CTkTextbox(entry_frame, height=80, wrap="word", fg_color="transparent")
                    comment_text.grid(row=row_counter, column=0, columnspan=2, padx=10, pady=(0, 10), sticky="ew")
                    comment_text.insert("1.0", form.experiment_comment)
                    comment_text.configure(state="disabled")

        finally:
            session.close()

    def reset_search(self):
        """검색창을 비우고 전체 목록을 다시 불러옵니다."""
        self.search_entry.delete(0, "end")
        self.load_history()
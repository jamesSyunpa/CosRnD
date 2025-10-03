import customtkinter as ctk
import sys
import os

# 프로젝트 루트 경로를 sys.path에 추가 (상대 경로 import를 위함)
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if PROJECT_ROOT not in sys.path:
    sys.path.append(PROJECT_ROOT)

from database.db_manager import db_manager
from database.models import Formulation, or_
from datetime import datetime, date
from utils import center_window_on_mouse_display

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
        try:
            center_window_on_mouse_display(self)
        except Exception:
            pass

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

            # 동일 LAB NO. 기준으로 이전 버전을 기억하여 '변경된 항목만' 비교
            prev_by_lab = {}
            shown_count = 0

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

                # --- 변경된 항목만 계산하여 표시 ---
                lab_key = form.lab_no or f"__{form.experiment_name}__"
                prev = prev_by_lab.get(lab_key)
                diffs = self._compute_formulation_diff(prev, form)

                if prev is None:
                    # 최초 기록: 메타만 보여주고 '초기 등록' 표시
                    init_label = ctk.CTkLabel(entry_frame, text="[초기 등록]", text_color="gray")
                    init_label.grid(row=row_counter, column=0, padx=10, pady=(0, 8), sticky="w")
                    row_counter += 1
                    shown_count += 1
                else:
                    if diffs:
                        diff_label = ctk.CTkLabel(entry_frame, text="[변경 항목]", font=ctk.CTkFont(weight="bold"), anchor="w")
                        diff_label.grid(row=row_counter, column=0, columnspan=2, padx=10, pady=(5, 2), sticky="w")
                        row_counter += 1

                        # 변경 항목만 리스트로 출력
                        for line in diffs:
                            ctk.CTkLabel(entry_frame, text=f"- {line}", anchor="w", justify="left").grid(
                                row=row_counter, column=0, columnspan=2, padx=16, pady=2, sticky="w"
                            )
                            row_counter += 1
                        shown_count += 1
                    else:
                        # 변경 없음이면 이 항목은 최소한의 헤더만 남기고 안내 표시
                        ctk.CTkLabel(entry_frame, text="(변경 없음)", text_color="gray").grid(
                            row=row_counter, column=0, padx=10, pady=(0, 8), sticky="w"
                        )
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

                # 현재를 이전값으로 등록
                prev_by_lab[lab_key] = form

            # 만약 하나도 표시될 게 없으면 안내 메시지 출력
            if shown_count == 0:
                ctk.CTkLabel(self.scrollable_frame, text="변경된 항목이 없습니다.").pack(pady=20)

        finally:
            session.close()

    def reset_search(self):
        """검색창을 비우고 전체 목록을 다시 불러옵니다."""
        self.search_entry.delete(0, "end")
        self.load_history()

    # ---------------- 내부 유틸: 변경 항목 비교 ----------------
    def _compute_formulation_diff(self, prev, curr):
        """두 Formulation을 비교해 변경된 항목만 텍스트로 반환합니다."""
        if prev is None or curr is None:
            return []

        def norm(v):
            if isinstance(v, (datetime, date)):
                return v.strftime('%Y-%m-%d')
            return '' if v is None else str(v)

        # 비교할 필드와 라벨
        fields = [
            ('manager_name', '담당자'),
            ('experiment_date', '실험일'),
            ('experiment_ph_initial', 'pH(초기)'),
            ('experiment_ph_next_day', 'pH(익일)'),
            ('experiment_viscosity_initial', '점도(초기)'),
            ('experiment_viscosity_next_day', '점도(익일)'),
            ('experiment_machine', 'Pin'),
            ('sample_sent_count', '샘플발송 횟수'),
            ('sample_delivery_date', '샘플발송일'),
            ('oem_odm_client_id', 'OEM/ODM 거래처'),
            ('target_client_id', '타겟 거래처'),
        ]

        changes = []
        for key, label in fields:
            old = norm(getattr(prev, key, None))
            new = norm(getattr(curr, key, None))
            if old != new:
                # 숫자 포맷 보정 (샘플발송 횟수)
                if key == 'sample_sent_count':
                    try:
                        old_i = int(old) if old != '' else 0
                        new_i = int(new) if new != '' else 0
                        old, new = f"{old_i}", f"{new_i}"
                    except:
                        pass
                changes.append(f"{label}: {old or '-'} → {new or '-'}")

        return changes
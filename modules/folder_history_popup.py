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
        self.geometry("800x700")  # 메인 창보다 작음
        self.resizable(True, True)  # 크기 조절 및 최대화 버튼 활성화
        self.minsize(600, 500)  # 최소 크기만 제한
        # self.transient(master)  # 최대화 버튼을 활성화하기 위해 transient 제거
        self.grab_set()
        self.after(100, lambda: print(f"[WINDOW SIZE] '{folder_name}' 전체 이력 | geometry: {self.winfo_width()}x{self.winfo_height()} | requested: 800x700"))

        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(1, weight=1) # 스크롤 프레임을 위한 행

        self.setup_ui()
        self.load_history()
        
        # 메인 창 중앙에 배치
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
            
            # 디버깅: 조회된 처방 개수 출력
            print(f"[전체이력조회] 폴더 '{self.folder_name}': {len(formulations)}개 처방 조회됨")
            for idx, f in enumerate(formulations, 1):
                print(f"  [{idx}] LAB NO: {f.lab_no}, 차수: {f.revision}, 생성일: {f.created_at}")

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

                # --- 변경된 항목만 상세 표시 ---
                lab_key = form.lab_no or f"__{form.experiment_name}__"
                prev = prev_by_lab.get(lab_key)
                
                # 변경 이력 계산
                diffs = self._compute_formulation_diff(prev, form)
                
                if prev is None:
                    # 최초 기록 - 전체 정보 표시 (이전 버전 없음)
                    status_label = ctk.CTkLabel(entry_frame, text="[초기 등록]", text_color="green", font=ctk.CTkFont(weight="bold"))
                    status_label.grid(row=row_counter, column=0, padx=10, pady=(0, 8), sticky="w")
                    row_counter += 1
                    
                    # 초기 등록 시 전체 정보 표시 (이전 버전 없음)
                    items_text = self._format_formulation_items(form, prev_form=None)
                    if items_text:
                        items_textbox = ctk.CTkTextbox(entry_frame, height=120, wrap="word", fg_color="#2b2b2b")
                        items_textbox.grid(row=row_counter, column=0, columnspan=2, padx=10, pady=(0, 10), sticky="ew")
                        items_textbox.insert("1.0", items_text)
                        items_textbox.configure(state="disabled")
                        row_counter += 1
                    
                    shown_count += 1
                else:
                    # 변경 이력이 있는 경우만 상세 표시
                    if diffs:
                        status_label = ctk.CTkLabel(entry_frame, text="[변경된 항목]", text_color="orange", font=ctk.CTkFont(weight="bold"))
                        status_label.grid(row=row_counter, column=0, columnspan=2, padx=10, pady=(5, 2), sticky="w")
                        row_counter += 1
                        
                        for line in diffs:
                            ctk.CTkLabel(entry_frame, text=f"  • {line}", anchor="w", justify="left").grid(
                                row=row_counter, column=0, columnspan=2, padx=16, pady=2, sticky="w"
                            )
                            row_counter += 1
                        
                        # 변경된 처방의 전체 정보 표시 (이전 버전과 비교)
                        all_info_label = ctk.CTkLabel(entry_frame, text="[전체 정보 (함량 변경 내역 포함)]", font=ctk.CTkFont(weight="bold"), anchor="w")
                        all_info_label.grid(row=row_counter, column=0, columnspan=2, padx=10, pady=(10, 2), sticky="w")
                        row_counter += 1
                        
                        items_text = self._format_formulation_items(form, prev_form=prev)
                        if items_text:
                            items_textbox = ctk.CTkTextbox(entry_frame, height=120, wrap="word", fg_color="#2b2b2b")
                            items_textbox.grid(row=row_counter, column=0, columnspan=2, padx=10, pady=(0, 10), sticky="ew")
                            items_textbox.insert("1.0", items_text)
                            items_textbox.configure(state="disabled")
                            row_counter += 1
                        
                        shown_count += 1
                    else:
                        # 변경 없음 - 헤더만 표시하고 상세 정보는 숨김
                        status_label = ctk.CTkLabel(entry_frame, text="[변경 없음]", text_color="gray")
                        status_label.grid(row=row_counter, column=0, padx=10, pady=(0, 8), sticky="w")
                        row_counter += 1
                        # shown_count는 증가시키지 않음 (변경 없는 항목은 카운트 제외)

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

    # ---------------- 내부 유틸: 처방 아이템 포맷팅 ----------------
    def _format_formulation_items(self, form, prev_form=None):
        """처방의 모든 아이템을 텍스트로 포맷팅합니다. 이전 버전과 비교하여 함량 차이를 표시합니다."""
        if not form.items:
            return "처방 아이템 없음"
        
        lines = []
        lines.append(f"담당자: {form.manager_name or '-'}")
        
        # 실험일 포맷팅 (날짜 객체 또는 문자열 처리)
        exp_date_str = '-'
        if form.experiment_date:
            if isinstance(form.experiment_date, str):
                exp_date_str = form.experiment_date
            elif hasattr(form.experiment_date, 'strftime'):
                exp_date_str = form.experiment_date.strftime('%Y-%m-%d')
        lines.append(f"실험일: {exp_date_str}")
        
        lines.append(f"pH: 초기 {form.experiment_ph_initial or '-'} / 익일 {form.experiment_ph_next_day or '-'}")
        lines.append(f"점도: 초기 {form.experiment_viscosity_initial or '-'} / 익일 {form.experiment_viscosity_next_day or '-'}")
        lines.append(f"Pin: {form.experiment_machine or '-'}")
        lines.append(f"샘플발송: {form.sample_sent_count or 0}회")
        lines.append("")
        lines.append("=== 처방 아이템 ===")
        
        # 이전 버전의 아이템을 딕셔너리로 변환 (material_code를 키로)
        prev_items = {}
        if prev_form and prev_form.items:
            for item in prev_form.items:
                if item.material_code and item.material_code not in ["---", "-", "--"]:
                    prev_items[item.material_code] = float(item.ratio) if item.ratio else 0.0
        
        # 현재 버전의 아이템 표시
        for item in sorted(form.items, key=lambda x: x.order if x.order is not None else 999999):
            if item.material_code and item.material_code not in ["---", "-", "--"]:
                current_ratio = float(item.ratio) if item.ratio else 0.0
                ratio_str = f"{current_ratio:.4f}%"
                
                # 이전 버전과 비교하여 차이 계산
                if prev_form and item.material_code in prev_items:
                    prev_ratio = prev_items[item.material_code]
                    diff = current_ratio - prev_ratio
                    if abs(diff) > 0.0001:  # 차이가 있는 경우
                        sign = "+" if diff > 0 else ""
                        lines.append(f"  [{item.order or '-'}] {item.material_code} - {item.material_name or ''}")
                        lines.append(f"      함량: {ratio_str} (이전: {prev_ratio:.4f}%, 차이: {sign}{diff:.4f}%)")
                    else:
                        lines.append(f"  [{item.order or '-'}] {item.material_code} - {item.material_name or ''}")
                        lines.append(f"      함량: {ratio_str}")
                else:
                    # 새로 추가된 항목이거나 이전 버전이 없는 경우
                    lines.append(f"  [{item.order or '-'}] {item.material_code} - {item.material_name or ''}")
                    if prev_form:
                        lines.append(f"      함량: {ratio_str} (신규 추가)")
                    else:
                        lines.append(f"      함량: {ratio_str}")
        
        return "\n".join(lines)
    
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
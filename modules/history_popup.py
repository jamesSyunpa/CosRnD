import customtkinter as ctk
import re
from utils import center_window_on_mouse_display

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

        # 성능 최적화 관련 상태
        self.all_log_entries = []  # 현재 화면에 적재된 항목들
        self.items_info = []       # 각 아이템별 블록 수/로딩 상태
        self.initial_per_item = 5  # 처음에는 항목당 최근 N블록만 로딩
        self.more_per_item = 5     # '더 보기' 클릭 시 항목당 추가 로딩 개수

        self.setup_ui()
        self.prepare_and_load_history()
        try:
            center_window_on_mouse_display(self)
        except Exception:
            pass

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

        # 더 보기 / 닫기 버튼 영역
        btn_frame = ctk.CTkFrame(self, fg_color="transparent")
        btn_frame.grid(row=2, column=0, padx=15, pady=(0, 15), sticky="ew")
        btn_frame.grid_columnconfigure(0, weight=1)
        self.load_more_button = ctk.CTkButton(btn_frame, text="더 보기", command=self.load_more)
        self.load_more_button.pack(side="left")
        close_button = ctk.CTkButton(btn_frame, text="닫기", command=self.destroy)
        close_button.pack(side="right")

    def prepare_and_load_history(self):
        """큰 데이터를 한 번에 모두 적재하지 않고, 항목당 최근 일부만 로딩합니다.
        추가: 엑셀 가져오기(일괄 업로드) 로그는 개별 항목 대신 하나의 '전체 성분 업로드' 항목으로 집계합니다.
        """
        self.all_log_entries = []
        self.items_info = []

        # 메타만 우선 구성 (이름/코드/총 블록 수) 및 엑셀 가져오기 집계 사전 스캔
        bulk_total = 0
        bulk_created = 0
        bulk_updated = 0
        bulk_latest_ts = ''

        # 1차 패스: 블록 수 카운트와 일괄 업로드 블록 집계(헤더만 빠르게 스캔)
        for item in self.items:
            try:
                if not getattr(item, 'change_log', None):
                    continue
                item_name = getattr(item, self.item_name_key, 'N/A')
                identifier = item_name
                if self.item_code_key:
                    item_code = getattr(item, self.item_code_key, None)
                    if item_code:
                        identifier = f"{item_name} ({item_code})"
                text = item.change_log.strip()
                if not text:
                    continue
                # 총 블록 수(대략): 공백 라인(두 줄 개행) 기준
                total_blocks = 1 + text.count('\n\n')
                self.items_info.append({
                    'item': item,
                    'identifier': identifier,
                    'total': total_blocks,
                    'loaded': 0,
                })

                # 엑셀 가져오기 블록 탐지 (헤더만 빠르게 확인)
                # 오른쪽부터 일부만 분할하여 최신 헤더를 우선 스캔
                parts = text.rsplit('\n\n')
                for block in parts:
                    m = re.match(r"\[(.*?)\] by (.*?)\n", block)
                    if not m:
                        continue
                    ts, user_hdr = m.groups()
                    if '엑셀 가져오기' in (user_hdr or ''):
                        bulk_total += 1
                        if '신규 생성' in (user_hdr or ''):
                            bulk_created += 1
                        else:
                            bulk_updated += 1
                        # 최신 타임스탬프 추적 (문자열 비교로 충분: YYYY-MM-DD HH:MM)
                        try:
                            if not bulk_latest_ts or str(ts) > bulk_latest_ts:
                                bulk_latest_ts = str(ts)
                        except Exception:
                            pass
            except Exception:
                continue

        # 초기 로딩: 일괄 업로드 블록은 개별 로딩 대신 집계만 표시
        self._load_recent_blocks(per_item=self.initial_per_item)

        # 일괄 업로드 집계 항목 삽입 (맨 위에 가까이 오도록 최신 타임스탬프 사용)
        if bulk_total > 0:
            # 컨텍스트에 맞는 라벨 결정 (원료/성분/거래처/사용자)
            try:
                window_title = self.title() or ""
            except Exception:
                window_title = ""
            if any(k in window_title for k in ["거래처"]):
                agg_label = "전체 거래처 업로드"
            elif any(k in window_title for k in ["사용자", "회원"]):
                agg_label = "전체 사용자 업로드"
            elif any(k in window_title for k in ["원료", "성분"]):
                agg_label = "전체 성분 업로드"
            else:
                agg_label = "전체 업로드"

            summary_changes = f"- {agg_label}: 총 {bulk_total}건"
            # 부가 요약 (신규/수정 비율)
            try:
                if bulk_created > 0 or bulk_updated > 0:
                    summary_changes += f" (신규 {bulk_created}, 수정 {bulk_updated})"
            except Exception:
                pass
            self.all_log_entries.append({
                'timestamp': bulk_latest_ts or '9999-99-99 99:99',
                'user': '일괄 업로드',
                'changes': summary_changes,
                'identifier': agg_label,
            })

        self._refresh_view()

    def _load_recent_blocks(self, per_item=5):
        """각 항목에서 최근 per_item 블록을 추가로 읽어들여 self.all_log_entries에 누적합니다."""
        for info in self.items_info:
            try:
                item = info['item']
                text = item.change_log.strip()
                total = info['total']
                if total <= info['loaded']:
                    continue
                # 이번에 로드할 개수
                to_load = min(per_item, total - info['loaded'])
                # 오른쪽부터 블록 분할: 이미 로드한 개수 + to_load 만큼만 역분할
                need = info['loaded'] + to_load
                parts = text.rsplit('\n\n', maxsplit=need)
                recent_blocks = parts[-to_load:] if len(parts) >= to_load else parts

                for block in recent_blocks:
                    match = re.match(r"\[(.*?)\] by (.*?)\n((?:- .*\n?)*)", block, re.DOTALL)
                    if not match:
                        continue
                    timestamp_str, user, changes = match.groups()
                    # 엑셀 가져오기는 개별 항목 추가하지 않고 집계로 대체하므로 스킵
                    if '엑셀 가져오기' in (user or ''):
                        continue
                    # 장문 최적화: 초기 등록 상세 다건을 축약
                    compact_changes = self._compact_changes(changes.strip())
                    self.all_log_entries.append({
                        'timestamp': timestamp_str,
                        'user': user,
                        'changes': compact_changes,
                        'identifier': info['identifier'],
                    })
                info['loaded'] += to_load
            except Exception:
                continue

    def _compact_changes(self, changes: str) -> str:
        """전성분 초기 등록 등의 장문을 축약하여 표시 텍스트 길이를 줄입니다."""
        try:
            lines = [ln for ln in changes.splitlines() if ln.strip()]
            out = []
            i = 0
            while i < len(lines):
                ln = lines[i].strip()
                # 전성분 초기 등록 블록 축약
                if ln.startswith('- 전성분 초기 등록'):
                    j = i + 1
                    detail_count = 0
                    while j < len(lines) and lines[j].strip().startswith('- -'):
                        detail_count += 1
                        j += 1
                    if detail_count > 0:
                        out.append(f"- 전성분 초기 등록: ({detail_count}개)")
                        i = j
                        continue
                # 전성분 추가/삭제/변경 연속 묶음 축약(상위 5개만)
                prefix = None
                if ln.startswith('- 전성분 추가:'):
                    prefix = '- 전성분 추가:'
                elif ln.startswith('- 전성분 삭제:'):
                    prefix = '- 전성분 삭제:'
                elif ln.startswith('- 전성분 변경:'):
                    prefix = '- 전성분 변경:'
                if prefix:
                    group = [ln]
                    j = i + 1
                    while j < len(lines) and lines[j].strip().startswith(prefix):
                        group.append(lines[j].strip())
                        j += 1
                    SHOW_MAX = 5
                    out.extend(group[:SHOW_MAX])
                    if len(group) > SHOW_MAX:
                        out.append(f"... ({len(group) - SHOW_MAX}건 더)")
                    i = j
                    continue
                # 일반 라인
                out.append(ln)
                i += 1
            return '\n'.join(out)
        except Exception:
            return changes

    def _refresh_view(self):
        # 최신순 정렬로 표시
        self.all_log_entries.sort(key=lambda x: x['timestamp'], reverse=True)
        self.display_history(self.all_log_entries)
        # 더 보기 버튼 표시/숨김
        has_more = any(info['loaded'] < info['total'] for info in self.items_info)
        try:
            self.load_more_button.configure(state=("normal" if has_more else "disabled"))
        except Exception:
            pass

    def load_more(self):
        """'더 보기' 클릭 시 항목당 일정량씩 추가 로딩."""
        self._load_recent_blocks(per_item=self.more_per_item)
        self._refresh_view()

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
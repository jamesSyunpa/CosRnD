# modules/home_frame.py
import customtkinter as ctk
from tkinter import ttk # noqa
import sys
import os
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if PROJECT_ROOT not in sys.path:
    sys.path.append(PROJECT_ROOT)

from database.db_manager import db_manager
from database.models import Material
from sqlalchemy import desc
from datetime import datetime
import re

class HomeFrame(ctk.CTkFrame):
    def __init__(self, master, user, app, recent_actions, action_config):
        super().__init__(master, fg_color="transparent")
        self.current_user = user
        self.app = app
        self.recent_actions = recent_actions
        self.action_config = action_config

        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(0, weight=0) # 최근 활동 섹션 (고정 높이)
        self.grid_rowconfigure(1, weight=1) # 하단 섹션 (확장)

        # --- 상단: 최근 활동 섹션 ---
        self.recent_actions_frame = ctk.CTkFrame(self, fg_color="transparent")
        self.recent_actions_frame.grid(row=0, column=0, sticky="new", padx=10, pady=10)
        self.recent_actions_frame.grid_columnconfigure(0, weight=1)

        ctk.CTkLabel(self.recent_actions_frame, text="최근 활동", font=ctk.CTkFont(size=18, weight="bold")).pack(anchor="w", pady=(0, 10))
        
        self.cards_frame = ctk.CTkFrame(self.recent_actions_frame, fg_color="transparent")
        self.cards_frame.pack(fill="x")

        # --- 하단: 공지사항 및 변경 이력 섹션 ---
        bottom_frame = ctk.CTkFrame(self, fg_color="transparent")
        bottom_frame.grid(row=1, column=0, sticky="nsew", padx=10, pady=10)
        bottom_frame.grid_columnconfigure(0, weight=1) # 좌측 공지사항
        bottom_frame.grid_columnconfigure(1, weight=1) # 우측 변경 이력
        bottom_frame.grid_rowconfigure(0, weight=1)

        # --- 하단 좌측: 공지사항 ---
        notice_frame = ctk.CTkFrame(bottom_frame)
        notice_frame.grid(row=0, column=0, sticky="nsew", padx=(0, 5))
        notice_frame.grid_rowconfigure(1, weight=1)
        notice_frame.grid_columnconfigure(0, weight=1)

        ctk.CTkLabel(notice_frame, text="공지사항 / 업데이트", font=ctk.CTkFont(size=16, weight="bold")).grid(row=0, column=0, padx=15, pady=10, sticky="w")
        
        self.notice_textbox = ctk.CTkTextbox(notice_frame, wrap="word", font=ctk.CTkFont(family="Malgun Gothic", size=13))
        self.notice_textbox.grid(row=1, column=0, sticky="nsew", padx=15, pady=(0, 15))
        self.notice_textbox.insert("1.0", "시스템 공지사항 또는 업데이트 내역이 여기에 표시됩니다.\n\n"
                                          "v1.0.0 (2024-07-30)\n"
                                          "- 최초 버전 릴리즈\n"
                                          "- 주요 기능: 처방 관리, 데이터 관리, 품질 관리")
        self.notice_textbox.configure(state="disabled")

        # --- 하단 우측: 최근 성분 변경 이력 (가로 셀 나열) ---
        changes_frame = ctk.CTkFrame(bottom_frame)
        changes_frame.grid(row=0, column=1, sticky="nsew", padx=(5, 0))
        changes_frame.grid_rowconfigure(1, weight=1)
        changes_frame.grid_columnconfigure(0, weight=1)

        ctk.CTkLabel(changes_frame, text="최근 성분 변경 이력", font=ctk.CTkFont(size=16, weight="bold")).grid(row=0, column=0, padx=15, pady=10, sticky="w")

        # 가로 카드 레이아웃 컨테이너
        self.changes_panel = ctk.CTkFrame(changes_frame, fg_color="transparent")
        self.changes_panel.grid(row=1, column=0, sticky="nsew", padx=15, pady=(0, 15))
        # 2열 레이아웃: [원료명] [변경된 항목들(콤마로 나열)]
        self.changes_panel.grid_columnconfigure(0, weight=0)
        self.changes_panel.grid_columnconfigure(1, weight=1)

        self.refresh_cards()
        self.load_recent_material_changes()

    def refresh_cards(self):
        """최근 활동 카드를 다시 그립니다."""
        for widget in self.cards_frame.winfo_children():
            widget.destroy()

        if not self.recent_actions:
            ctk.CTkLabel(self.cards_frame, text="최근 활동이 없습니다.", font=ctk.CTkFont(size=14), text_color="gray").pack(pady=20)
            return

        # [수정] pack() 대신 grid()를 사용하여 5열 레이아웃으로 꽉 채워 표시
        num_columns = 5
        self.cards_frame.grid_columnconfigure(tuple(range(num_columns)), weight=1)

        for i, action in enumerate(self.recent_actions):
            config = self.action_config.get(action, {"icon": "❓", "title": action})
            card = self.create_action_card(self.cards_frame, config["icon"], config["title"], action)
            card.grid(row=0, column=i, padx=10, pady=10, sticky="nsew")

    def create_action_card(self, master, icon, title, action_name):
        """클릭 가능한 활동 카드를 생성합니다."""
        card = ctk.CTkFrame(master, corner_radius=15, cursor="hand2")
        card.grid_columnconfigure(0, weight=1)

        icon_label = ctk.CTkLabel(card, text=icon, font=ctk.CTkFont(size=40))
        icon_label.pack(pady=(20, 10))

        title_label = ctk.CTkLabel(card, text=title, font=ctk.CTkFont(size=14, weight="bold"), wraplength=120)
        title_label.pack(pady=(0, 20), padx=10)

        for widget in [card, icon_label, title_label]:
            widget.bind("<Button-1>", lambda e, name=action_name: self.app.navigate_and_record(name))
        
        return card

    def load_recent_material_changes(self):
        """DB에서 최근 변경된 원료(성분)를 다음 형식으로 표시합니다.
        - 좌측: [YYYY-MM-DD HH:MM] 변경명 • 원료명 (N건)  ← 전체 클릭 가능
        - 우측: 변경된 항목 요약 (콤마로 나열)         ← 클릭 시 동일 동작
        클릭 시 성분 관리 화면으로 이동하여 해당 원료를 선택합니다.
        """
        # 패널 초기화
        for w in list(self.changes_panel.winfo_children()):
            try:
                w.destroy()
            except Exception:
                pass

        session = db_manager.get_session()
        try:
            # 최신 항목을 넉넉히 가져와서(예: 50개) 실제 '변경'이 있는 것만 골라 10개 표시
            candidates = session.query(Material).order_by(
                desc(Material.updated_at), desc(Material.created_at)
            ).limit(50).all()

            # 요약 생성 및 필터링
            rows = []
            for material in candidates:
                info = self._get_latest_change_info(material, max_items=8)
                if info and info.get('summary'):
                    rows.append((material, info))
                if len(rows) >= 10:
                    break

            if not rows:
                empty = ctk.CTkLabel(self.changes_panel, text="최근 성분 변경 이력이 없습니다.", text_color="gray")
                empty.grid(row=0, column=0, padx=6, pady=6, sticky="w")
            else:
                # 행 구성: [원료명] [변경된 항목들을 콤마(,)로 나열]
                for r_idx, (material, info) in enumerate(rows):
                    ts = info.get('timestamp') or ''
                    action = info.get('action') or ''
                    count = info.get('count') or 0
                    header_text = f"[{ts}] {action} • {material.name or ''} ({count}건)".strip()

                    # 왼쪽: 타임스탬프/액션/원료명/건수 (클릭 가능)
                    name_label = ctk.CTkLabel(
                        self.changes_panel,
                        text=header_text,
                        font=ctk.CTkFont(size=13, weight="bold"),
                        cursor="hand2"
                    )
                    name_label.grid(row=r_idx, column=0, padx=(6, 10), pady=6, sticky="w")

                    # 오른쪽: 변경된 항목 요약 (클릭 가능)
                    changes_label = ctk.CTkLabel(
                        self.changes_panel,
                        text=info.get('summary', ''),
                        font=ctk.CTkFont(size=12),
                        text_color="gray70",
                        wraplength=520,
                        justify="left",
                        cursor="hand2"
                    )
                    changes_label.grid(row=r_idx, column=1, padx=(0, 6), pady=6, sticky="w")

                    # 클릭 시 해당 원료 상세로 이동
                    for w in (name_label, changes_label):
                        w.bind("<Button-1>", lambda e, mid=material.id: self._open_material(mid))

                # 각 행 높이 균등 확장은 필요 없으나, 두 번째 열은 넓게 사용
                for r in range(len(rows)):
                    self.changes_panel.grid_rowconfigure(r, weight=0)

        except Exception as e:
            print(f"최근 성분 변경 이력 로드 중 오류: {e}")
            # 오류 셀 표시
            err = ctk.CTkLabel(self.changes_panel, text="이력 로드 중 오류가 발생했습니다.", text_color="red")
            err.grid(row=0, column=0, padx=6, pady=6, sticky="w")
        finally:
            session.close()

    def refresh_data(self):
        """홈 프레임에 표시되는 데이터를 새로고침합니다."""
        print("홈 프레임 데이터 새로고침...")
        self.refresh_cards()
        self.load_recent_material_changes()

    # ------------------------- 내부 헬퍼 -------------------------
    def _open_material(self, material_id: int):
        """해당 원료 ID로 데이터 관리/성분 관리 탭을 열고 선택합니다."""
        try:
            if hasattr(self.app, 'open_material_by_id'):
                self.app.open_material_by_id(material_id)
            else:
                # 폴백: 탭만 전환
                self.app.navigate_and_record("data/ingredient_mgt")
        except Exception as e:
            print(f"[경고] 원료 열기 실패: {e}")

    def _get_latest_change_info(self, material: Material, max_items: int = 6):
        """가장 최근 변경 블록에서 타임스탬프/액션/요약/건수를 추출합니다."""
        try:
            if not getattr(material, 'change_log', None):
                return None

            text = material.change_log.strip()
            blocks = [b.strip() for b in text.split('\n\n') if b.strip()]
            if not blocks:
                return None

            latest = list(reversed(blocks))[0]
            lines = [ln for ln in latest.splitlines() if ln.strip()]
            if not lines:
                return None

            header = lines[0]
            # 헤더에서 [YYYY-MM-DD HH:MM(SS)] 추출
            ts = ''
            try:
                if header.startswith('[') and ']' in header:
                    inside = header.split(']', 1)[0].lstrip('[').strip()
                    ts = inside
            except Exception:
                pass
            # 액션 추출: " - " 이후 텍스트에서 괄호 접미사는 제거
            action = ''
            try:
                if ' - ' in header:
                    action_part = header.split(' - ', 1)[1]
                    action = action_part.split('(', 1)[0].strip()
            except Exception:
                pass

            # 본문에서 변경 항목 추출 (home 요약 로직과 동일하게 간결화)
            items = []
            def add_item(x):
                if x and x not in items:
                    items.append(x)

            import re
            pat_field_change = re.compile(r"^\-\s*([^:]+):\s*'.*?'\s*->\s*'.*?'")
            pat_add = re.compile(r"^\-\s*전성분\s*추가:\s*([^|\n]+)")
            pat_del = re.compile(r"^\-\s*전성분\s*삭제:\s*([^\n]+)")
            pat_mod = re.compile(r"^\-\s*전성분\s*변경:\s*([^|\n]+)")
            pat_initial = re.compile(r"^\-\s*전성분\s*초기\s*등록\s*:\s*$")

            # 신규 생성 여부
            is_create = ('신규 생성' in header)
            if is_create:
                add_item('신규 생성')

            for ln in lines[1:]:
                if not ln.lstrip().startswith('-'):
                    continue
                if ln.lstrip().startswith('- -'):
                    continue
                if pat_initial.match(ln):
                    add_item('전성분 초기 등록')
                    continue
                m = pat_field_change.match(ln)
                if m:
                    add_item(m.group(1).strip())
                    if len(items) >= max_items:
                        break
                    continue
                m = pat_add.match(ln)
                if m:
                    add_item(f"전성분 추가 {m.group(1).strip()}")
                    if len(items) >= max_items:
                        break
                    continue
                m = pat_del.match(ln)
                if m:
                    add_item(f"전성분 삭제 {m.group(1).strip()}")
                    if len(items) >= max_items:
                        break
                    continue
                m = pat_mod.match(ln)
                if m:
                    add_item(f"전성분 변경 {m.group(1).strip()}")
                    if len(items) >= max_items:
                        break
                    continue

            if not items:
                if is_create:
                    items = ['신규 생성']
                else:
                    return None

            return {
                'timestamp': ts,
                'action': action,
                'summary': ", ".join(items[:max_items]),
                'count': len(items)
            }
        except Exception as e:
            print(f"변경 메타 추출 실패: {e}")
            return None
    def _summarize_material_changes(self, material: Material, max_items: int = 6, lookback_blocks: int = 1) -> str:
        """가장 최근 변경 블록에서 실제 바뀐 내용만 간단히 콤마로 나열합니다.

        - 날짜/헤더는 제외하고, 필드 변경 라벨(예: 단가, 포장단위)과 전성분 추가/삭제/변경만 표시합니다.
        - '전성분 초기 등록' 상세 항목은 한 줄짜리 토큰으로 축약합니다.
        - 신규 생성만 있는 경우에는 '신규 생성'만 반환합니다.
        """
        try:
            if not getattr(material, 'change_log', None):
                return ""

            text = material.change_log.strip()
            blocks = [b.strip() for b in text.split('\n\n') if b.strip()]
            if not blocks:
                return "변경 이력이 없습니다."

            # 가장 최근 블록 하나만 요약
            selected = [list(reversed(blocks))[0]]
            items = []  # 변경 항목 라벨들

            # 패턴 정규식 (안전하고 단순한 형태)
            # 예: "- 단가: '1000' -> '1200'" 처럼 실제 변경(->) 라인만 캡처하여 라벨만 추출
            pat_field_change = re.compile(r"^\-\s*([^:]+):\s*'.*?'\s*->\s*'.*?'")
            pat_add = re.compile(r"^\-\s*전성분\s*추가:\s*([^|\n]+)")
            pat_del = re.compile(r"^\-\s*전성분\s*삭제:\s*([^\n]+)")
            pat_mod = re.compile(r"^\-\s*전성분\s*변경:\s*([^|\n]+)")
            pat_initial = re.compile(r"^\-\s*전성분\s*초기\s*등록\s*:\s*$")

            def add_item(label: str):
                if label and label not in items:
                    items.append(label)
            for block in selected:
                lines = [ln for ln in block.splitlines() if ln.strip()]
                header = lines[0] if lines else ""
                is_create = ('신규 생성' in header)

                # 신규 생성은 우선 토큰 추가 (상세 라벨 나열 대신 간단히)
                if is_create:
                    add_item('신규 생성')

                # 헤더 제외하고 본문에서 추출
                for ln in lines[1:]:
                    if not ln.lstrip().startswith('-'):
                        continue
                    # 전성분 초기 등록은 한 항목으로 축약
                    if pat_initial.match(ln):
                        add_item('전성분 초기 등록')
                        continue
                    # 전성분 상세 라인(이중 대시) 무시
                    if ln.lstrip().startswith('- -'):
                        continue
                    # 필드 변경 라벨
                    m = pat_field_change.match(ln)
                    if m:
                        add_item(m.group(1).strip())
                        if len(items) >= max_items:
                            break
                        continue
                    # 전성분 추가/삭제/변경 + 대상 라벨 일부
                    m = pat_add.match(ln)
                    if m:
                        add_item(f"전성분 추가 {m.group(1).strip()}")
                        if len(items) >= max_items:
                            break
                        continue
                    m = pat_del.match(ln)
                    if m:
                        add_item(f"전성분 삭제 {m.group(1).strip()}")
                        if len(items) >= max_items:
                            break
                        continue
                    m = pat_mod.match(ln)
                    if m:
                        add_item(f"전성분 변경 {m.group(1).strip()}")
                        if len(items) >= max_items:
                            break
                        continue

                # 블록 하나만 요약하므로 추가 반복 불필요
                break

            # 항목이 비어 있으면(예: 헤더만 있는 경우) 신규 생성이면 '신규 생성'만, 아니면 빈 문자열
            if not items:
                # header 스코프 밖에서 is_create 참조 불가하므로 재판단
                last_header = [ln for ln in selected[0].splitlines() if ln.strip()][0]
                return '신규 생성' if ('신규 생성' in last_header) else ""

            # 콤마로 나열하여 반환
            return ", ".join(items[:max_items])
        except Exception as e:
            print(f"변경 요약 생성 중 오류: {e}")
            return "변경 이력 요약을 생성할 수 없습니다."
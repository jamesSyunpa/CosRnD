# modules/home_frame.py
import customtkinter as ctk
from tkinter import ttk, messagebox # noqa
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

        header_frame = ctk.CTkFrame(self.recent_actions_frame, fg_color="transparent")
        header_frame.pack(fill="x", pady=(0, 10))
        
        ctk.CTkLabel(header_frame, text="최근 활동", font=ctk.CTkFont(size=14, weight="bold")).pack(side="left")
        
        # 도움말 버튼 추가
        self.help_btn = ctk.CTkButton(
            header_frame, 
            text="도움말 (?)", 
            width=80, 
            height=24,
            font=ctk.CTkFont(size=11),
            command=self.open_help
        )
        self.help_btn.pack(side="right")
        
        # 법적 고지 버튼 추가 (도움말 왼쪽에)
        self.legal_btn = ctk.CTkButton(
            header_frame,
            text="법적 고지",
            width=80,
            height=24,
            fg_color="gray", # 회색 계열로 튀지 않게
            font=ctk.CTkFont(size=11),
            command=self.open_legal_notice
        )
        self.legal_btn.pack(side="right", padx=(0, 5))
        
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

        ctk.CTkLabel(notice_frame, text="공지사항 / 업데이트", font=ctk.CTkFont(size=12, weight="bold")).grid(row=0, column=0, padx=15, pady=10, sticky="w")
        
        self.notice_textbox = ctk.CTkTextbox(notice_frame, wrap="word", font=ctk.CTkFont(family="Malgun Gothic", size=10))
        self.notice_textbox.grid(row=1, column=0, sticky="nsew", padx=15, pady=(0, 15))
        self.notice_textbox.insert("1.0", "시스템 공지사항 또는 업데이트 내역이 여기에 표시됩니다.\n\n"
                                          "v59 (2026-02-03)\n"
                                          "- DB 자동 동기화 기능 개선 (안전한 교체 방식)\n"
                                          "- 업데이트 알림 설정 및 메인 화면 알림 기능 추가\n"
                                          "- 성분/처방 관리 기능 안정화")
        self.notice_textbox.configure(state="disabled")

        # --- 하단 우측: 최근 성분 변경 이력 (가로 셀 나열) ---
        changes_frame = ctk.CTkFrame(bottom_frame)
        changes_frame.grid(row=0, column=1, sticky="nsew", padx=(5, 0))
        changes_frame.grid_rowconfigure(1, weight=1)
        changes_frame.grid_columnconfigure(0, weight=1)

        ctk.CTkLabel(changes_frame, text="최근 성분 변경 이력", font=ctk.CTkFont(size=12, weight="bold")).grid(row=0, column=0, padx=15, pady=10, sticky="w")

        # 변경 이력 리스트 컨테이너 (행 단위로 2단 색상 적용)
        self.changes_panel = ctk.CTkFrame(changes_frame, fg_color="transparent")
        self.changes_panel.grid(row=1, column=0, sticky="nsew", padx=15, pady=(0, 15))
        self.changes_panel.grid_columnconfigure(0, weight=1)

        self.refresh_cards()
        self.load_recent_material_changes()

    def show_update_available_notice(self, message, sync_callback):
        """메인 화면 좌측 공지사항 영역에 업데이트 알림을 표시합니다."""
        try:
            # 텍스트 박스 업데이트
            self.notice_textbox.configure(state="normal")
            self.notice_textbox.delete("1.0", "end")
            self.notice_textbox.insert("1.0", f"🔔 [새로운 업데이트 알림]\n\n{message}")
            self.notice_textbox.configure(state="disabled")
            
            # 업데이트 버튼 추가 (이미 있으면 제거 후 재생성)
            if hasattr(self, 'sync_btn'):
                self.sync_btn.destroy()
                
            self.sync_btn = ctk.CTkButton(
                self.notice_textbox.master,
                text="지금 동기화 (Update Now)",
                command=lambda: [self._hide_sync_btn(), sync_callback()],
                fg_color="#E65100", # 주황색 계열 강조
                hover_color="#EF6C00"
            )
            self.sync_btn.grid(row=2, column=0, pady=10, padx=15, sticky="ew")
            
            # 반짝이는 효과나 강조 효과를 줄 수도 있음
            print("[Home] 업데이트 알림 표시됨")
            
        except Exception as e:
            print(f"[Home] 업데이트 알림 표시 실패: {e}")

    def _hide_sync_btn(self):
        """동기화 버튼을 숨기고 원래 공지사항으로 복구"""
        if hasattr(self, 'sync_btn'):
            self.sync_btn.destroy()
            delattr(self, 'sync_btn')
        
        # 공지사항 텍스트 복구 (기본 메시지)
        self.notice_textbox.configure(state="normal")
        self.notice_textbox.delete("1.0", "end")
        self.notice_textbox.insert("1.0", "시스템 공지사항 또는 업데이트 내역이 여기에 표시됩니다.\n\n"
                                          "v1.0.0 (2024-07-30)\n"
                                          "- 최초 버전 릴리즈\n"
                                          "- 주요 기능: 처방 관리, 데이터 관리, 품질 관리")
        self.notice_textbox.configure(state="disabled")

    def refresh_cards(self):
        """최근 활동 카드를 다시 그립니다."""
        for widget in self.cards_frame.winfo_children():
            widget.destroy()

        if not self.recent_actions:
            ctk.CTkLabel(self.cards_frame, text="최근 활동이 없습니다.", font=ctk.CTkFont(size=11), text_color="gray").pack(pady=20)
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

        icon_label = ctk.CTkLabel(card, text=icon, font=ctk.CTkFont(size=32))
        icon_label.pack(pady=(15, 8))

        title_label = ctk.CTkLabel(card, text=title, font=ctk.CTkFont(size=10, weight="bold"), wraplength=100)
        title_label.pack(pady=(0, 15), padx=8)

        for widget in [card, icon_label, title_label]:
            widget.bind("<Button-1>", lambda e, name=action_name: self.app.navigate_and_record(name))
        
        return card
            
    def open_help(self):
        """사용자 가이드 PDF를 엽니다 (외부 뷰어)."""
        from utils import resource_path
        
        # PDF 파일 경로 찾기
        target_path = resource_path("assets/UserGuide.pdf")
        
        if target_path and os.path.exists(target_path):
            try:
                print(f"[Help] Opening PDF: {target_path}")
                os.startfile(target_path)
            except Exception as e:
                print(f"[Help] Failed to open PDF: {e}")
                messagebox.showerror("오류", f"도움말 파일을 여는 도중 오류가 발생했습니다.\n{e}")
        else:
            print("[Help] PDF not found.")
            messagebox.showinfo("안내", "사용자 가이드 파일(UserGuide.pdf)을 찾을 수 없습니다.\nassets 폴더를 확인해주세요.")

    def open_legal_notice(self):
        """법적 고지 팝업을 엽니다."""
        from modules.legal_notice import LegalNoticeDialog
        import configparser
        
        # 현재 버전 가져오기 시도
        try:
            with open(os.path.join(PROJECT_ROOT, 'VERSION'), 'r', encoding='utf-8') as f:
                ver = f.read().strip()
                # Normalize version string (ensure leading 'v')
                if ver and not ver.startswith('v') and re.match(r'^\d+(?:\.\d+)*$', ver):
                    ver = 'v' + ver
        except:
             ver = "v??"

        # 동의 여부 확인
        already_agreed = False
        config_path = None
        try:
            # 1. exe 실행 폴더의 config.ini 확인
            exe_dir = os.path.dirname(sys.executable) if getattr(sys, 'frozen', False) else PROJECT_ROOT
            config_path = os.path.join(exe_dir, 'config.ini')
            
            # config 파일이 없으면 생성하지 않고, 있으면 읽어서 확인
            if os.path.exists(config_path):
                config = configparser.ConfigParser()
                config.read(config_path, encoding='utf-8')
                
                if config.has_section('Legal'):
                    agreed_ver = config.get('Legal', 'agreed_version', fallback=None)
                    # Normalize agreed_ver for comparison
                    if agreed_ver:
                        agreed_ver = agreed_ver.strip()
                        if not agreed_ver.startswith('v') and re.match(r'^\d+(?:\.\d+)*$', agreed_ver):
                            agreed_ver = 'v' + agreed_ver
                    if agreed_ver == ver:
                        already_agreed = True
        except Exception as e:
            print(f"[Home] Config check failed: {e}")

        # callbacks and config_path are not needed if already_agreed is True
        # config_path를 명시적으로 전달하여 Dialog에서도 동일한 경로를 사용하도록 함
        LegalNoticeDialog(self.winfo_toplevel(), ver, lambda: None, config_path, already_agreed=already_agreed)

    def load_recent_material_changes(self):
        """DB에서 최근 변경된 원료(성분)를 비동기적으로 로드하여 표시합니다."""
        # 패널 초기화
        for w in list(self.changes_panel.winfo_children()):
            try:
                w.destroy()
            except Exception:
                pass

        # 로딩 표시
        loading_label = ctk.CTkLabel(self.changes_panel, text="최근 변경 이력을 불러오는 중...", text_color="gray")
        loading_label.grid(row=0, column=0, padx=6, pady=6, sticky="w")

        # 비동기 로드 시작
        import threading
        threading.Thread(target=self._fetch_recent_changes_thread, daemon=True).start()

    def _fetch_recent_changes_thread(self):
        """백그라운드 스레드에서 최근 변경 이력을 조회합니다."""
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
                    # UI 업데이트를 위해 필요한 데이터만 추출 (객체 분리)
                    rows.append((material.id, material.name, info))
                if len(rows) >= 10:
                    break
            
            # UI 업데이트 예약
            self.after(0, lambda: self._update_changes_panel(rows))
            
            # 슬라이딩 애니메이션 시작 예약 (행이 있을 때만)
            if rows:
                self.after(2000, self._start_sliding_animation)
            
        except Exception as e:
            print(f"최근 성분 변경 이력 로드 중 오류: {e}")
            self.after(0, lambda: self._show_error_in_panel())
        finally:
            session.close()

    def _start_sliding_animation(self):
        """변경 이력 패널을 슬라이딩(자동 스크롤)하는 애니메이션을 시작합니다."""
        # 이미 실행 중이면 중복 실행 방지
        if getattr(self, '_sliding_running', False):
            return
        self._sliding_running = True
        self._slide_step()

    def _slide_step(self):
        """
        주기적으로 호출되어 맨 위의 행을 맨 아래로 이동시키는 효과를 줍니다.
        (실제로는 grid row 인덱스를 재배치하는 방식 대신, 위젯 리스트를 순환시킵니다)
        """
        try:
            # 패널이 파괴되었으면 중단
            if not self.changes_panel.winfo_exists():
                self._sliding_running = False
                return

            # 자식 위젯(행) 목록 가져오기
            children = self.changes_panel.winfo_children()
            if len(children) <= 1: # 행이 1개 이하면 슬라이딩 필요 없음
                self._sliding_running = False
                return

            # 첫 번째 행(가장 오래된 것 or 현재 상단)을 맨 아래로 이동
            # pack/grid 매니저 특성상 forget 후 다시 append 하면 맨 아래로 감
            first_row = children[0]
            first_row.grid_forget()
            
            # 나머지 행들의 row 인덱스를 하나씩 당김 (선택적)
            # 하지만 grid를 다시 하면 자동으로 아래에 붙으므로,
            # 전체를 다시 grid 하는 것이 깔끔함
            
            # 리스트 순서 변경: [0, 1, 2...] -> [1, 2, ..., 0]
            new_order = children[1:] + [first_row]
            
            for i, widget in enumerate(new_order):
                widget.grid(row=i, column=0, sticky="ew", pady=(0, 8))
                
                # 색상 재적용 (홀/짝수 행 배경색 유지)
                # 내부 구조: row_container -> [left_cell, right_cell]
                try:
                    left_cell = widget.winfo_children()[0]
                    right_cell = widget.winfo_children()[1]
                    left_color, right_color, hover_tint = self._get_dual_tone_colors(i)
                    left_cell.configure(fg_color=left_color)
                    right_cell.configure(fg_color=right_color)
                    
                    # 호버 이벤트 재바인딩 (클로저 변수 캡처 문제 방지 위해 다시 설정)
                    self._bind_hover_tint([left_cell, right_cell], [left_color, right_color], hover_tint)
                except Exception:
                    pass

            # 다음 스텝 예약 (예: 3초마다)
            self.after(3000, self._slide_step)

        except Exception as e:
            print(f"Sliding animation error: {e}")
            self._sliding_running = False

    def _update_changes_panel(self, rows):
        """메인 스레드에서 변경 이력 패널을 업데이트합니다."""
        # 패널 초기화 (로딩 메시지 제거)
        for w in list(self.changes_panel.winfo_children()):
            try:
                w.destroy()
            except Exception:
                pass

        if not rows:
            empty = ctk.CTkLabel(self.changes_panel, text="최근 성분 변경 이력이 없습니다.", text_color="gray")
            empty.grid(row=0, column=0, padx=6, pady=6, sticky="w")
            return

        # 행 구성
        for r_idx, (material_id, material_name, info) in enumerate(rows):
            ts = info.get('timestamp') or ''
            action = info.get('action') or ''
            count = info.get('count') or 0
            header_text = f"[{ts}] {action} • {material_name or ''} ({count}건)".strip()

            left_color, right_color, hover_tint = self._get_dual_tone_colors(r_idx)

            # 행 컨테이너
            row_container = ctk.CTkFrame(self.changes_panel, corner_radius=10, fg_color="transparent")
            row_container.grid(row=r_idx, column=0, sticky="ew", pady=(0, 8))
            row_container.grid_columnconfigure(0, weight=0)
            row_container.grid_columnconfigure(1, weight=1)

            # 좌측 영역
            left_cell = ctk.CTkFrame(row_container, fg_color=left_color, corner_radius=10, cursor="hand2")
            left_cell.grid(row=0, column=0, sticky="nsw")
            left_label = ctk.CTkLabel(
                left_cell,
                text=header_text,
                font=ctk.CTkFont(size=10, weight="bold"),
                anchor="w"
            )
            left_label.pack(padx=8, pady=6)

            # 우측 영역
            right_cell = ctk.CTkFrame(row_container, fg_color=right_color, corner_radius=10, cursor="hand2")
            right_cell.grid(row=0, column=1, sticky="nsew")
            right_label = ctk.CTkLabel(
                right_cell,
                text=info.get('summary', ''),
                font=ctk.CTkFont(size=12),
                text_color="gray70",
                wraplength=520,
                justify="left",
                anchor="w"
            )
            right_label.pack(padx=8, pady=6)

            # 클릭: 행 전체 어느 영역을 눌러도 이동
            self._bind_click_open([row_container, left_cell, left_label, right_cell, right_label], material_id)

            # 호버
            self._bind_hover_tint([left_cell, right_cell], [left_color, right_color], hover_tint)

        # 레이아웃 늘림
        self.changes_panel.grid_rowconfigure(tuple(range(len(rows))), weight=0)

    def _show_error_in_panel(self):
        """패널에 오류 메시지를 표시합니다."""
        for w in list(self.changes_panel.winfo_children()):
            try: w.destroy()
            except: pass
        err = ctk.CTkLabel(self.changes_panel, text="이력 로드 중 오류가 발생했습니다.", text_color="red")
        err.grid(row=0, column=0, padx=6, pady=6, sticky="w")

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

    # ------------------------- 스타일 & 바인딩 헬퍼 -------------------------
    def _get_dual_tone_colors(self, index: int):
        """행 인덱스에 따라 좌/우 셀 배경색을 다르게(2단 색상) 반환합니다.
        - 모드별(light/dark) 팔레트 지정
        - 짝/홀수 행 교차 색상
        반환: (left_color, right_color, hover_tint)
        """
        mode = ctk.get_appearance_mode() or "Light"
        if mode == "Dark":
            palette_a = ("#2C313C", "#232730")  # 좌/우
            palette_b = ("#2A2F39", "#20242C")
            hover_tint = "#3A3F4A"
        else:
            palette_a = ("#F4F6FA", "#E9EFF7")
            palette_b = ("#F0F3F8", "#E6ECF5")
            hover_tint = "#DDE7F4"
        return (palette_a if index % 2 == 0 else palette_b) + (hover_tint,)

    def _bind_click_open(self, widgets, material_id: int):
        for w in widgets:
            try:
                w.bind("<Button-1>", lambda e, mid=material_id: self._open_material(mid))
            except Exception:
                pass

    def _bind_hover_tint(self, cells, base_colors, hover_tint: str):
        """셀들에 동일한 hover 효과를 주어 인터랙션을 강조합니다."""
        def on_enter(_):
            for c in cells:
                try:
                    c.configure(fg_color=hover_tint)
                except Exception:
                    pass
        def on_leave(_):
            for c, base in zip(cells, base_colors):
                try:
                    c.configure(fg_color=base)
                except Exception:
                    pass
        for c in cells:
            try:
                c.bind("<Enter>", on_enter)
                c.bind("<Leave>", on_leave)
            except Exception:
                pass
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
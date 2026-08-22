# modules/home_frame.py
import customtkinter as ctk
from tkinter import ttk, messagebox # noqa
import sys
import os
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if PROJECT_ROOT not in sys.path:
    sys.path.append(PROJECT_ROOT)

from database.db_manager import db_manager
from database.models import Material, Formulation, Client
from sqlalchemy import desc
from datetime import datetime
import re
import threading
import webbrowser
from utils.cafe_manager import CafeNoticeManager
from utils.update_manager import UpdateManager, UpdateDialog

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
        
        ctk.CTkLabel(header_frame, text="최근 활동", font=ctk.CTkFont(size=12, weight="bold")).pack(side="left")
        
        # 도움말/설명서 버튼 추가
        self.help_btn = ctk.CTkButton(
            header_frame, 
            text="도움말/설명서", 
            width=95, 
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

        # --- 하단 좌측: 공지사항 & 업데이트 컨테이너 (상하 2단 분리) ---
        left_bottom_frame = ctk.CTkFrame(bottom_frame, fg_color="transparent")
        left_bottom_frame.grid(row=0, column=0, sticky="nsew", padx=(0, 5))
        left_bottom_frame.grid_columnconfigure(0, weight=1)
        left_bottom_frame.grid_rowconfigure(0, weight=1) # 상단 공지사항: 남은 화면 영역을 100% 독점 확장
        left_bottom_frame.grid_rowconfigure(1, weight=0) # 하단 업데이트: 컴팩트 고정 높이만 차지하여 바닥에 착 붙음

        # 1. 상단: 공지사항 프레임 (대폭 확장)
        notice_frame = ctk.CTkFrame(left_bottom_frame)
        notice_frame.grid(row=0, column=0, sticky="nsew", pady=(0, 6))
        notice_frame.grid_rowconfigure(1, weight=1)
        notice_frame.grid_columnconfigure(0, weight=1)

        notice_header = ctk.CTkFrame(notice_frame, fg_color="transparent")
        notice_header.grid(row=0, column=0, padx=15, pady=(8, 4), sticky="ew")
        notice_header.grid_columnconfigure(1, weight=1)

        ctk.CTkLabel(notice_header, text="📢 공지사항", font=ctk.CTkFont(size=12, weight="bold")).grid(row=0, column=0, sticky="w")

        notice_btn_box = ctk.CTkFrame(notice_header, fg_color="transparent")
        notice_btn_box.grid(row=0, column=2, sticky="e")

        ctk.CTkButton(
            notice_btn_box,
            text="🌐 카페 바로가기",
            width=95,
            height=24,
            font=ctk.CTkFont(size=11),
            fg_color="#3b82f6",
            hover_color="#2563eb",
            command=lambda: webbrowser.open("https://cafe.naver.com/cosrqd")
        ).pack(side="left", padx=(0, 4))

        ctk.CTkButton(
            notice_btn_box,
            text="🔄",
            width=28,
            height=24,
            font=ctk.CTkFont(size=12),
            fg_color="gray50",
            hover_color="gray40",
            command=self.load_cafe_notices
        ).pack(side="left")
        
        # 공지사항 리스트 스크롤 컨테이너 (시원하게 넓은 공간 확보)
        self.notice_panel = ctk.CTkScrollableFrame(notice_frame, fg_color="transparent")
        self.notice_panel.grid(row=1, column=0, sticky="nsew", padx=10, pady=(0, 10))
        self.notice_panel.grid_columnconfigure(0, weight=1)

        # 2. 하단: 업데이트 내역 프레임 (슬림하게 하단 고정)
        update_frame = ctk.CTkFrame(left_bottom_frame, height=130)
        update_frame.grid(row=1, column=0, sticky="ew", pady=(2, 0))
        update_frame.grid_rowconfigure(1, weight=1)
        update_frame.grid_columnconfigure(0, weight=1)

        update_header = ctk.CTkFrame(update_frame, fg_color="transparent")
        update_header.grid(row=0, column=0, padx=15, pady=(6, 2), sticky="ew")
        update_header.grid_columnconfigure(1, weight=1)

        ctk.CTkLabel(update_header, text="🚀 시스템 업데이트 내역", font=ctk.CTkFont(size=12, weight="bold")).grid(row=0, column=0, sticky="w")
        
        self.update_textbox = ctk.CTkTextbox(update_frame, height=100, wrap="word", font=ctk.CTkFont(family="Malgun Gothic", size=11))
        self.update_textbox.grid(row=1, column=0, sticky="nsew", padx=15, pady=(0, 8))
        self._load_system_updates()

        # --- 하단 우측: 최근 R&D 변경 이력 (통합 피드 & 다운로드) ---
        changes_frame = ctk.CTkFrame(bottom_frame)
        changes_frame.grid(row=0, column=1, sticky="nsew", padx=(5, 0))
        changes_frame.grid_rowconfigure(1, weight=1)
        changes_frame.grid_columnconfigure(0, weight=1)

        # 상단 툴바 프레임 (제목, 필터 세그먼트, 엑셀 다운로드/새로고침 버튼)
        changes_header = ctk.CTkFrame(changes_frame, fg_color="transparent")
        changes_header.grid(row=0, column=0, padx=15, pady=(8, 4), sticky="ew")
        changes_header.grid_columnconfigure(1, weight=1)

        ctk.CTkLabel(changes_header, text="📋 최근 R&D 변경 이력", font=ctk.CTkFont(size=12, weight="bold")).grid(row=0, column=0, sticky="w")

        # 피드 필터 (전체 / 처방 / 원료 / 거래처)
        self.feed_filter_var = ctk.StringVar(value="전체")
        self.feed_filter_segmented = ctk.CTkSegmentedButton(
            changes_header,
            values=["전체", "🧪 처방", "🌿 원료", "🏢 거래처"],
            variable=self.feed_filter_var,
            command=self._on_filter_changed,
            height=24,
            font=ctk.CTkFont(size=11)
        )
        self.feed_filter_segmented.grid(row=0, column=1, padx=10, sticky="w")

        # 엑셀 다운로드 버튼 & 새로고침 버튼
        btn_box = ctk.CTkFrame(changes_header, fg_color="transparent")
        btn_box.grid(row=0, column=2, sticky="e")

        ctk.CTkButton(
            btn_box,
            text="📥 이력 다운로드",
            width=90,
            height=24,
            font=ctk.CTkFont(size=11, weight="bold"),
            fg_color="#2FA572",
            hover_color="#106A43",
            command=self.export_feed_history_to_excel
        ).pack(side="left", padx=(0, 4))

        ctk.CTkButton(
            btn_box,
            text="🔄",
            width=28,
            height=24,
            font=ctk.CTkFont(size=12),
            fg_color="gray50",
            hover_color="gray40",
            command=self.load_recent_material_changes
        ).pack(side="left")

        # 변경 이력 리스트 스크롤 컨테이너
        self.changes_panel = ctk.CTkScrollableFrame(changes_frame, fg_color="transparent")
        self.changes_panel.grid(row=1, column=0, sticky="nsew", padx=10, pady=(0, 10))
        self.changes_panel.grid_columnconfigure(0, weight=1)

        self.refresh_cards()
        self.load_recent_material_changes()
        self.load_cafe_notices()

    def refresh_cards(self):
        """최근 활동 카드를 다시 그립니다."""
        for widget in self.cards_frame.winfo_children():
            widget.destroy()

        def resolve_config(act):
            if act in self.action_config:
                return act, self.action_config[act]
            for k, v in self.action_config.items():
                if k.endswith('/' + act) or k == act:
                    return k, v
            return act, {"icon": "📌", "title": act}

        valid_items = []
        for act in self.recent_actions:
            resolved_key, cfg = resolve_config(act)
            valid_items.append((resolved_key, cfg))

        if not valid_items:
            ctk.CTkLabel(self.cards_frame, text="최근 활동이 없습니다.", font=ctk.CTkFont(size=11), text_color="gray").pack(pady=20)
            return

        # 5열 레이아웃으로 꽉 채워 표시
        self.cards_frame.grid_columnconfigure(tuple(range(5)), weight=1)

        for i, (resolved_key, config) in enumerate(valid_items[:5]):
            card = self.create_action_card(self.cards_frame, config.get("icon", "📌"), config.get("title", resolved_key), resolved_key)
            card.grid(row=0, column=i, padx=10, pady=10, sticky="nsew")

    def create_action_card(self, master, icon, title, action_name):
        """클릭 가능한 모던 활동 카드를 생성합니다."""
        card = ctk.CTkFrame(
            master,
            corner_radius=10,
            cursor="hand2",
            fg_color=("#FFFFFF", "#242526"),
            border_width=1,
            border_color=("#E5E7EB", "#333538")
        )
        card.grid_columnconfigure(0, weight=1)

        icon_label = ctk.CTkLabel(card, text=icon, font=ctk.CTkFont(size=26))
        icon_label.pack(pady=(14, 6))

        title_label = ctk.CTkLabel(
            card,
            text=title,
            font=ctk.CTkFont(size=11, weight="bold"),
            text_color=("#1F2937", "#E4E6EB"),
            wraplength=100
        )
        title_label.pack(pady=(0, 14), padx=8)

        # 부드러운 호버 피드백
        def on_enter(e):
            card.configure(fg_color=("#F3F4F6", "#2D3035"), border_color=("#D1D5DB", "#4B5563"))
        def on_leave(e):
            card.configure(fg_color=("#FFFFFF", "#242526"), border_color=("#E5E7EB", "#333538"))

        card.bind("<Enter>", on_enter)
        card.bind("<Leave>", on_leave)

        for widget in [card, icon_label, title_label]:
            widget.bind("<Button-1>", lambda e, name=action_name: self.app.navigate_and_record(name))
            if widget != card:
                widget.bind("<Enter>", on_enter)
                widget.bind("<Leave>", on_leave)
        
        return card
            
    def open_help(self):
        """도움말 및 네이버 카페 가이드 센터를 엽니다."""
        from modules.help_viewer import HelpViewer
        HelpViewer(self.winfo_toplevel())

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
        try:
            # 1. AppData 및 로컬 config.ini 경로 탐색
            appdata_dir = os.path.join(os.getenv('APPDATA', os.path.expanduser('~')), 'CosRnD')
            target_config = os.path.join(appdata_dir, 'config.ini')
            exe_dir = os.path.dirname(sys.executable) if getattr(sys, 'frozen', False) else PROJECT_ROOT
            local_config = os.path.join(exe_dir, 'config.ini')

            config_path = target_config if os.path.exists(target_config) else local_config

            if os.path.exists(config_path):
                config = configparser.ConfigParser()
                config.read(config_path, encoding='utf-8')
                if config.has_section('Legal'):
                    agreed_ver = config.get('Legal', 'agreed_version', fallback='')
                    # 동의 값이 존재하면 이미 동의한 것으로 처리 (체크박스 체크됨)
                    if agreed_ver and agreed_ver.strip() != '':
                        already_agreed = True
        except Exception as e:
            print(f"[Home] Config check failed: {e}")

        # callbacks and config_path are not needed if already_agreed is True
        LegalNoticeDialog(self.winfo_toplevel(), ver, lambda: None, None, already_agreed=already_agreed)

    def load_cafe_notices(self):
        """네이버 카페에서 최신 공지사항 목록과 본문을 비동기로 가져와 아코디언 카드 리스트로 렌더링합니다."""
        for w in list(self.notice_panel.winfo_children()):
            try:
                w.destroy()
            except:
                pass

        loading_label = ctk.CTkLabel(
            self.notice_panel,
            text="⏳ 네이버 카페(CosRQD)에서 최신 공지사항을 불러오는 중입니다...",
            font=ctk.CTkFont(size=11),
            text_color="gray"
        )
        loading_label.pack(pady=20)

        def _fetch_worker():
            try:
                articles = CafeNoticeManager.get_notice_list(menu_ids=[13], per_page=10)
                # 각 글의 본문도 긁어와 딕셔너리에 추가
                for a in articles:
                    a['content'] = CafeNoticeManager.get_article_content(a.get('id')) or a.get('summary', '')
            except Exception as e:
                print(f"[Home] 공지 로드 실패: {e}")
                articles = []

            def _update_ui():
                try:
                    if hasattr(self, 'notice_panel') and self.notice_panel.winfo_exists():
                        self._render_notice_cards(articles)
                except Exception as ex:
                    print(f"[Home] 공지사항 UI 갱신 실패: {ex}")

            self.after(0, _update_ui)

        threading.Thread(target=_fetch_worker, daemon=True).start()

    def _render_notice_cards(self, articles):
        """공지사항 목록을 우측 변경이력처럼 모던한 아코디언 카드(칸칸)로 렌더링합니다."""
        for w in list(self.notice_panel.winfo_children()):
            try:
                w.destroy()
            except:
                pass

        if not articles:
            empty = ctk.CTkLabel(
                self.notice_panel,
                text="📢 현재 등록된 공지사항이 없습니다.",
                font=ctk.CTkFont(size=12),
                text_color="gray"
            )
            empty.pack(pady=20)
            return

        card_bg = ("#F4F6FA", "#2B2B2B")
        card_hover = ("#E9EFF7", "#363636")
        border_color = ("#E2E8F0", "#3E3E3E")

        for r_idx, item in enumerate(articles):
            art_id = item.get("id")
            raw_subject = item.get("subject", "제목 없음")
            clean_subject = raw_subject
            for prefix in ["📢 [공지]", "[공지]", "📢"]:
                if clean_subject.startswith(prefix):
                    clean_subject = clean_subject[len(prefix):].strip()

            date_str = item.get("date", "")
            writer = item.get("writer", "관리자")
            content = item.get("content", "").strip() or "본문 내용이 없습니다."
            url = item.get("url", "https://cafe.naver.com/cosrqd")

            # 개별 공지 카드 프레임 (칸칸)
            card = ctk.CTkFrame(
                self.notice_panel,
                corner_radius=8,
                fg_color=card_bg,
                border_width=1,
                border_color=border_color,
                cursor="hand2"
            )
            card.pack(fill="x", pady=(0, 6), padx=2)

            # 1. 헤더 구역 (항상 보임)
            header_frame = ctk.CTkFrame(card, fg_color="transparent")
            header_frame.pack(fill="x", padx=10, pady=8)
            header_frame.grid_columnconfigure(2, weight=1)

            # 날짜 라벨
            ctk.CTkLabel(
                header_frame,
                text=f"[{date_str}]",
                font=ctk.CTkFont(size=11),
                text_color=("gray50", "gray65")
            ).grid(row=0, column=0, sticky="w", padx=(0, 6))

            # 📢 공지 뱃지
            ctk.CTkLabel(
                header_frame,
                text="📢 공지",
                font=ctk.CTkFont(size=11, weight="bold"),
                text_color=("#0284C7", "#38BDF8")
            ).grid(row=0, column=1, sticky="w", padx=(0, 8))

            # 제목 라벨 (길면 자동 줄바꿈)
            title_lbl = ctk.CTkLabel(
                header_frame,
                text=clean_subject,
                font=ctk.CTkFont(size=11, weight="bold"),
                text_color=("#1E293B", "#FFFFFF"),
                anchor="w"
            )
            title_lbl.grid(row=0, column=2, sticky="ew")

            # 우측 버튼/토글 구역
            btn_area = ctk.CTkFrame(header_frame, fg_color="transparent")
            btn_area.grid(row=0, column=3, sticky="e", padx=(8, 0))

            # 원문 보기 작은 버튼
            link_btn = ctk.CTkButton(
                btn_area,
                text="🌐 원문",
                width=48,
                height=20,
                font=ctk.CTkFont(size=10),
                fg_color="#3b82f6",
                hover_color="#2563eb",
                command=lambda u=url: webbrowser.open(u)
            )
            link_btn.pack(side="left", padx=(0, 4))

            # 토글 화살표 라벨
            toggle_lbl = ctk.CTkLabel(
                btn_area,
                text="펼치기 ▼",
                font=ctk.CTkFont(size=10, weight="bold"),
                text_color=("gray50", "gray65")
            )
            toggle_lbl.pack(side="left")

            # 2. 본문 구역 (펼치기/접기 대상)
            body_frame = ctk.CTkFrame(card, fg_color="transparent")

            # 구분선
            ctk.CTkFrame(body_frame, height=1, fg_color=border_color).pack(fill="x", pady=(2, 6))

            # 본문 텍스트박스 (워드랩 적용)
            content_box = ctk.CTkTextbox(
                body_frame,
                wrap="word",
                font=ctk.CTkFont(family="Malgun Gothic", size=11),
                fg_color=("#FFFFFF", "#1E1E1E"),
                border_width=0,
                height=130
            )
            content_box.pack(fill="x", expand=True, pady=(0, 6))
            content_box.insert("1.0", content)
            content_box.configure(state="disabled")

            # 첫 번째 글은 기본으로 펼쳐둠, 나머지는 접힘
            is_expanded = [r_idx == 0]
            if is_expanded[0]:
                body_frame.pack(fill="x", padx=10, pady=(0, 8))
                toggle_lbl.configure(text="접기 ▲", text_color=("#0284C7", "#38BDF8"))

            # 토글 함수 (클릭 시 펼치기/접기)
            def make_toggle(b_frame=body_frame, t_lbl=toggle_lbl, exp=is_expanded):
                def _toggle(e=None):
                    if exp[0]:
                        b_frame.pack_forget()
                        t_lbl.configure(text="펼치기 ▼", text_color=("gray50", "gray65"))
                        exp[0] = False
                    else:
                        b_frame.pack(fill="x", padx=10, pady=(0, 8))
                        t_lbl.configure(text="접기 ▲", text_color=("#0284C7", "#38BDF8"))
                        exp[0] = True
                return _toggle

            toggle_fn = make_toggle()

            # 헤더 전체 클릭 시 토글 연결
            for w in [card, header_frame, title_lbl, toggle_lbl]:
                w.bind("<Button-1>", lambda e, fn=toggle_fn: fn())

            # 마우스 호버 피드백
            def make_hover(c=card):
                def on_enter(e):
                    c.configure(fg_color=card_hover)
                def on_leave(e):
                    c.configure(fg_color=card_bg)
                return on_enter, on_leave

            enter_fn, leave_fn = make_hover()
            card.bind("<Enter>", enter_fn)
            card.bind("<Leave>", leave_fn)


    def _load_system_updates(self):
        """GitHub Releases 실시간 패치노트 및 현재 프로그램의 버전 정보를 연동하여 표시합니다."""
        try:
            with open(os.path.join(PROJECT_ROOT, 'VERSION'), 'r', encoding='utf-8') as f:
                ver = f.read().strip()
                if ver and not ver.startswith('v') and re.match(r'^\d+(?:\.\d+)*$', ver):
                    ver = 'v' + ver
        except:
            ver = "v65.0.1"

        # 기본 로컬 패치노트 (즉시 렌더링)
        default_text = (
            f"🚀 [현재 버전: {ver} - 태성 배포용]\n"
            f"--------------------------------------------------\n"
            f"✨ [{ver} 주요 기능 및 변경 내역]\n"
            f"• 🌿 태성켐 원료 1순위 추천 및 샘플/견적 신청 연동\n"
            f"• 📄 품질관리 시험성적서(COA) 및 원료목록보고서 자동화\n"
            f"• 📢 네이버 공식 카페(CosRQD) 실시간 공지사항 연동\n"
            f"• ⚙️ 시스템 설정에서 업데이트 방식(자동/수동) 제어 지원\n"
            f"• 🔒 다중 실행 방지 소켓 락 및 시스템 무결성 보안 강화\n"
            f"• 🧪 처방 개발 버전 관리 및 통합 R&D 변경 타임라인 피드\n"
            f"• ⚡ 데이터베이스(DB) 마이그레이션 및 자동 복구 스위트 탑재\n"
            f"--------------------------------------------------\n"
            f"🌐 공식 배포처: 네이버 카페 (https://cafe.naver.com/cosrqd)"
        )

        self.update_textbox.configure(state="normal")
        self.update_textbox.delete("1.0", "end")
        self.update_textbox.insert("1.0", default_text)
        self.update_textbox.configure(state="disabled")

        # 네이버 공식 카페 및 GitHub Releases API로부터 실시간 최신 공지/패치노트 비동기 로드
        def _fetch_live_updates():
            try:
                # 1. 네이버 카페 13번(공지 및 업데이트) 최신글 로드
                cafe_articles = CafeNoticeManager.get_notice_list(menu_ids=[13], per_page=5)
                found, tag, info = UpdateManager.check_github_release()
                
                live_text = ""
                if cafe_articles:
                    latest_art = cafe_articles[0]
                    art_id = latest_art.get("id")
                    title = latest_art.get("subject", "")
                    date_str = latest_art.get("date", "")
                    writer = latest_art.get("writer", "관리자")
                    content = CafeNoticeManager.get_article_content(art_id) or latest_art.get("summary", "")
                    
                    live_text = (
                        f"📢 [네이버 카페 공식 공지: {title}]\n"
                        f"작성일: {date_str} | 작성자: {writer}\n"
                        f"--------------------------------------------------\n"
                        f"{content.strip()}\n\n"
                        f"--------------------------------------------------\n"
                        f"🌐 카페 원문 보기: https://cafe.naver.com/cosrqd/{art_id}"
                    )
                elif found and info:
                    body = info.get("summary", "").strip()
                    title = info.get("title", f"CosRQD {tag}")
                    pub_date = info.get("date", "")
                    
                    live_text = (
                        f"🚀 [공식 릴리즈 업데이트: {tag} ({pub_date})]\n"
                        f"📢 {title}\n"
                        f"--------------------------------------------------\n"
                        f"{body if body else '태성켐 원료 추천 및 시스템 성능 안정화 패치가 포함되어 있습니다.'}\n\n"
                        f"--------------------------------------------------\n"
                        f"🌐 공식 배포처: 네이버 카페 (https://cafe.naver.com/cosrqd)"
                    )

                if live_text:
                    def _update_ui():
                        if hasattr(self, 'update_textbox') and self.update_textbox.winfo_exists():
                            self.update_textbox.configure(state="normal")
                            self.update_textbox.delete("1.0", "end")
                            self.update_textbox.insert("1.0", live_text)
                            self.update_textbox.configure(state="disabled")

                    self.after(0, _update_ui)
            except Exception as e:
                print(f"[Home] 실시간 업데이트 내역 로드 오류: {e}")

        threading.Thread(target=_fetch_live_updates, daemon=True).start()


    def _on_filter_changed(self, value=None):
        """필터 탭 변경 시 피드를 다시 로드합니다."""
        self.load_recent_material_changes()

    def load_recent_material_changes(self):
        """DB에서 처방, 원료, 거래처의 최신 변경 이력을 수집하여 깔끔하고 세련된 통합 타임라인 피드로 표시합니다."""
        for w in list(self.changes_panel.winfo_children()):
            try:
                w.destroy()
            except Exception:
                pass

        filter_mode = getattr(self, 'feed_filter_var', None).get() if hasattr(self, 'feed_filter_var') else "전체"

        session = db_manager.get_session()
        try:
            feed_items = []

            # 1. 처방 변경 이력 수집
            if filter_mode in ["전체", "🧪 처방"]:
                formulations = session.query(Formulation).filter(
                    Formulation.change_log.isnot(None),
                    Formulation.change_log != ""
                ).order_by(desc(Formulation.created_at)).limit(30).all()
                
                for form in formulations:
                    info = self._parse_change_blocks(form.change_log, entity_type="처방", target_name=form.experiment_name or form.lab_no)
                    if info:
                        info['entity_type'] = "처방"
                        info['id'] = form.id
                        info['target_name'] = form.experiment_name or form.lab_no
                        info['code'] = form.lab_no or ""
                        feed_items.append(info)

            # 2. 원료 변경 이력 수집 (실제 변경이 있는 항목 우선, 없으면 신규 항목 수집)
            if filter_mode in ["전체", "🌿 원료"]:
                materials = session.query(Material).filter(
                    Material.change_log.isnot(None),
                    Material.change_log != ""
                ).order_by(desc(Material.updated_at), desc(Material.created_at)).limit(50).all()

                for mat in materials:
                    info = self._parse_change_blocks(mat.change_log, entity_type="원료", target_name=mat.name)
                    if info:
                        info['entity_type'] = "원료"
                        info['id'] = mat.id
                        info['target_name'] = mat.name or ""
                        info['code'] = mat.code or ""
                        feed_items.append(info)

            # 3. 거래처 변경 이력 수집
            if filter_mode in ["전체", "🏢 거래처"]:
                clients = session.query(Client).filter(
                    Client.change_log.isnot(None),
                    Client.change_log != ""
                ).order_by(desc(Client.created_at)).limit(30).all()

                for cli in clients:
                    info = self._parse_change_blocks(cli.change_log, entity_type="거래처", target_name=cli.name)
                    if info:
                        info['entity_type'] = "거래처"
                        info['id'] = cli.id
                        info['target_name'] = cli.name or ""
                        info['code'] = cli.client_type or ""
                        feed_items.append(info)

            # 1순위: '신규 생성 (엑셀 가져오기)'가 아닌 실제 수정/갱신된 내역 우선
            # 2순위: 타임스탬프 최신순
            feed_items.sort(key=lambda x: (not x.get('is_excel_init', False), x.get('timestamp', '')), reverse=True)
            rows = feed_items[:12]

            if not rows:
                empty = ctk.CTkLabel(
                    self.changes_panel, 
                    text=f"선택한 조건({filter_mode})에 해당하는 최근 변경 이력이 없습니다.", 
                    text_color="gray",
                    font=ctk.CTkFont(size=12)
                )
                empty.grid(row=0, column=0, padx=10, pady=30, sticky="w")
            else:
                is_dark = (ctk.get_appearance_mode() == "Dark")
                # CustomTkinter 표준 다크 테마(Level 2/3)와 완벽한 조화를 이루는 팔레트
                card_bg = ("#F4F6FA", "#2B2B2B")
                card_hover = ("#E9EFF7", "#363636")
                border_color = ("#E2E8F0", "#3E3E3E")

                icon_map = {"처방": "🧪", "원료": "🌿", "거래처": "🏢"}
                tag_color_map = {
                    "처방": ("#0284C7", "#38BDF8"),
                    "원료": ("#16A34A", "#4ADE80"),
                    "거래처": ("#EA580C", "#FB923C"),
                }

                for r_idx, item in enumerate(rows):
                    etype = item.get('entity_type', '원료')
                    ts = item.get('timestamp') or ''
                    action = item.get('action') or ''
                    target_name = item.get('target_name') or ''
                    summary = item.get('summary') or ''
                    tag_color = tag_color_map.get(etype, ("#888888", "#AAAAAA"))

                    # 하나의 통합 모던 카드
                    card = ctk.CTkFrame(
                        self.changes_panel,
                        corner_radius=8,
                        fg_color=card_bg,
                        border_width=1,
                        border_color=border_color,
                        cursor="hand2"
                    )
                    card.grid(row=r_idx, column=0, sticky="ew", pady=(0, 6), padx=2)
                    card.grid_columnconfigure(1, weight=1)

                    # 1열: 고정폭 메타 구역 [날짜 | 아이콘 구분 | 대상명]
                    meta_frame = ctk.CTkFrame(card, fg_color="transparent")
                    meta_frame.grid(row=0, column=0, padx=(12, 8), pady=8, sticky="w")

                    # 날짜 라벨
                    ctk.CTkLabel(
                        meta_frame,
                        text=f"[{ts}]",
                        font=ctk.CTkFont(size=11),
                        text_color=("gray50", "gray65")
                    ).pack(side="left", padx=(0, 6))

                    # 구분 텍스트 (깔끔한 텍스트 뱃지)
                    ctk.CTkLabel(
                        meta_frame,
                        text=f"{icon_map.get(etype, '')} {etype}",
                        font=ctk.CTkFont(size=11, weight="bold"),
                        text_color=tag_color
                    ).pack(side="left", padx=(0, 8))

                    # 대상 명칭 (볼드)
                    ctk.CTkLabel(
                        meta_frame,
                        text=target_name,
                        font=ctk.CTkFont(size=11, weight="bold"),
                        text_color=("#1E293B", "#FFFFFF")
                    ).pack(side="left")

                    # 2열: 우측 변경 상세 내용 구역
                    desc_frame = ctk.CTkFrame(card, fg_color="transparent")
                    desc_frame.grid(row=0, column=1, padx=(0, 12), pady=8, sticky="ew")

                    # [액션유형] + 변경요약 텍스트
                    summary_display = f"• [{action}] {summary}" if action else f"• {summary}"
                    ctk.CTkLabel(
                        desc_frame,
                        text=summary_display,
                        font=ctk.CTkFont(size=11),
                        text_color=("gray30", "gray80"),
                        anchor="w"
                    ).pack(side="left", fill="x", expand=True)

                    # 클릭 이벤트 바인딩
                    all_click_widgets = [card, meta_frame, desc_frame] + meta_frame.winfo_children() + desc_frame.winfo_children()
                    self._bind_entity_click(all_click_widgets, etype, item.get('id'))

                    # 호버 인터랙션
                    self._bind_single_card_hover(card, card_bg, card_hover)

                self.changes_panel.grid_rowconfigure(tuple(range(len(rows))), weight=0)

        except Exception as e:
            print(f"통합 R&D 변경 피드 로드 중 오류: {e}")
            err = ctk.CTkLabel(self.changes_panel, text="이력 로드 중 오류가 발생했습니다.", text_color="red")
            err.grid(row=0, column=0, padx=6, pady=6, sticky="w")
        finally:
            session.close()

    def export_feed_history_to_excel(self):
        """현재 DB에 축적된 처방, 원료, 거래처의 전체 R&D 변경 이력을 변경 항목별 1행씩 일렬로 상세히 엑셀로 내보냅니다."""
        session = db_manager.get_session()
        try:
            sheets = {}
            from modules import excel_handler

            # 1. 항목별 1행 데이터 취합
            all_rows = []

            # (1) 처방
            for f in session.query(Formulation).filter(Formulation.change_log.isnot(None)).all():
                parsed_items = self._split_all_log_lines(f.change_log, "처방", f.experiment_name or f.lab_no, f.lab_no or "", f.manager_name or "")
                all_rows.extend(parsed_items)

            # (2) 원료
            for m in session.query(Material).filter(Material.change_log.isnot(None)).all():
                parsed_items = self._split_all_log_lines(m.change_log, "원료", m.name or "", m.code or "", "")
                all_rows.extend(parsed_items)

            # (3) 거래처
            for c in session.query(Client).filter(Client.change_log.isnot(None)).all():
                parsed_items = self._split_all_log_lines(c.change_log, "거래처", c.name or "", c.client_type or "", c.manager_name or "")
                all_rows.extend(parsed_items)

            if not all_rows:
                messagebox.showinfo("알림", "내보낼 변경 이력 데이터가 없습니다.", parent=self)
                return

            # 일시 기준 최신순 정렬
            all_rows.sort(key=lambda x: x.get("발생일시", ""), reverse=True)

            # 표준 테이블 헤더: [발생일시, 구분, 식별코드/LAB, 대상명, 작업자, 구분(생성/변경), 변경항목, 변경 전 내용, 변경 후 내용, 전체로그]
            excel_headers = ["발생일시", "구분", "식별코드/LAB", "대상명", "작업자", "변경유형", "변경항목", "변경 전 내용", "변경 후 내용", "전체로그"]
            
            def make_table_data(row_list):
                return [
                    [r["발생일시"], r["구분"], r["식별코드/LAB"], r["대상명"], r["작업자"], r["변경유형"], r["변경항목"], r["변경전"], r["변경후"], r["전체로그"]]
                    for r in row_list
                ]

            # 시트 1: 통합 타임라인
            sheets["통합 타임라인"] = {"headers": excel_headers, "data": make_table_data(all_rows), "style": True}

            # 시트 2: 처방 이력
            form_logs = [r for r in all_rows if r["구분"] == "처방"]
            if form_logs:
                sheets["처방 변경 이력"] = {"headers": excel_headers, "data": make_table_data(form_logs), "style": True}

            # 시트 3: 원료 이력
            mat_logs = [r for r in all_rows if r["구분"] == "원료"]
            if mat_logs:
                sheets["원료_성분 변경 이력"] = {"headers": excel_headers, "data": make_table_data(mat_logs), "style": True}

            # 시트 4: 거래처 이력
            cli_logs = [r for r in all_rows if r["구분"] == "거래처"]
            if cli_logs:
                sheets["거래처 변경 이력"] = {"headers": excel_headers, "data": make_table_data(cli_logs), "style": True}

            default_filename = f"RD_통합변경이력_{datetime.now().strftime('%Y%m%d_%H%M')}.xlsx"
            excel_handler.export_all_change_logs(sheets, default_filename=default_filename)

        except Exception as e:
            messagebox.showerror("오류", f"이력 내보내기 중 오류가 발생했습니다:\n{e}", parent=self)
        finally:
            session.close()

    def _split_all_log_lines(self, change_log_text: str, entity_type: str, target_name: str, code: str, default_user: str):
        """로그 블록 내의 각 변경 항목(줄)마다 1행씩 분리하여 엑셀용 정밀 데이터를 생성합니다."""
        if not change_log_text:
            return []
        blocks = [b.strip() for b in str(change_log_text).split('\n\n') if b.strip()]
        result = []

        for b in blocks:
            lines = [ln.strip() for ln in b.splitlines() if ln.strip()]
            if not lines:
                continue
            header = lines[0]
            ts = ""
            user = default_user
            action = ""
            if header.startswith('[') and ']' in header:
                ts = header.split(']', 1)[0].lstrip('[').strip()
            if ' by ' in header:
                try:
                    user = header.split(' by ', 1)[1].split(' - ', 1)[0].strip()
                except Exception:
                    pass
            if ' - ' in header:
                try:
                    action = header.split(' - ', 1)[1].split('(', 1)[0].strip()
                except Exception:
                    pass

            detail_lines = [ln.lstrip('- ').strip() for ln in lines[1:] if ln.startswith('-')]

            if not detail_lines:
                # 상세 라인이 없으면 블록 자체를 1행으로
                result.append({
                    "발생일시": ts,
                    "구분": entity_type,
                    "식별코드/LAB": code,
                    "대상명": target_name,
                    "작업자": user,
                    "변경유형": action or "정보 갱신",
                    "변경항목": "전체",
                    "변경전": "-",
                    "변경후": action,
                    "전체로그": b
                })
            else:
                for dln in detail_lines:
                    field_name = ""
                    before_val = ""
                    after_val = ""

                    if "->" in dln:
                        # 예: "단가: '15000' -> '18000'"
                        parts = dln.split('->', 1)
                        left_part = parts[0].strip()
                        after_val = parts[1].strip().strip("'\"")
                        if ':' in left_part:
                            field_name = left_part.split(':', 1)[0].strip()
                            before_val = left_part.split(':', 1)[1].strip().strip("'\"")
                        else:
                            field_name = left_part
                            before_val = "-"
                    elif ':' in dln:
                        # 예: "전성분 추가: 판테놀 | 조성비 2.0"
                        field_name = dln.split(':', 1)[0].strip()
                        after_val = dln.split(':', 1)[1].strip()
                        before_val = "-"
                    else:
                        field_name = "기타"
                        after_val = dln
                        before_val = "-"

                    result.append({
                        "발생일시": ts,
                        "구분": entity_type,
                        "식별코드/LAB": code,
                        "대상명": target_name,
                        "작업자": user,
                        "변경유형": action or "수정",
                        "변경항목": field_name,
                        "변경전": before_val,
                        "변경후": after_val,
                        "전체로그": b
                    })

        return result

    def _parse_change_blocks(self, change_log_text: str, entity_type: str = "원료", target_name: str = ""):
        """가장 최근 로그 블록을 분석하여 [변경항목: 전 -> 후 (외 N건)] 형식으로 깔끔하게 축약합니다."""
        if not change_log_text:
            return None
        blocks = [b.strip() for b in str(change_log_text).split('\n\n') if b.strip()]
        if not blocks:
            return None
        
        # 1. '신규 생성 (엑셀 가져오기)'가 아닌 실제 변경 블록을 우선 탐색
        selected_block = None
        for b in reversed(blocks):
            if "신규 생성 (엑셀 가져오기)" not in b and "신규 생성" not in b:
                selected_block = b
                break
        
        is_excel_init = False
        if not selected_block:
            selected_block = blocks[-1]
            if "엑셀 가져오기" in selected_block:
                is_excel_init = True

        lines = [ln.strip() for ln in selected_block.splitlines() if ln.strip()]
        if not lines:
            return None

        header = lines[0]
        ts = ""
        action = ""
        if header.startswith('[') and ']' in header:
            ts = header.split(']', 1)[0].lstrip('[').strip()
            if len(ts) > 16:
                ts = ts[:16]
        if ' - ' in header:
            try:
                action = header.split(' - ', 1)[1].split('(', 1)[0].strip()
            except Exception:
                pass

        # 본문 변경 상세 항목 파싱
        change_items = []
        for ln in lines[1:]:
            if not ln.startswith('-'):
                continue
            ln_clean = ln.lstrip('- ').strip()
            
            if '->' in ln_clean:
                # "단가: '15000' -> '18000'" -> "단가: 15000 → 18000"
                parts = ln_clean.split('->', 1)
                left = parts[0].strip()
                after_val = parts[1].strip().strip("'\"")
                if ':' in left:
                    field = left.split(':', 1)[0].strip()
                    before_val = left.split(':', 1)[1].strip().strip("'\"")
                    change_items.append(f"{field}: {before_val} → {after_val}")
                else:
                    change_items.append(f"{left} → {after_val}")
            elif '전성분 추가' in ln_clean or '전성분 삭제' in ln_clean or '전성분 변경' in ln_clean:
                change_items.append(ln_clean)
            elif '신규 생성' in action or is_excel_init:
                field = ln_clean.split(':', 1)[0].strip()
                if field not in ["코드", "원료명"]:
                    val = ln_clean.split(':', 1)[1].strip().strip("'\"") if ':' in ln_clean else ""
                    change_items.append(f"{field}: {val}" if val else field)

        # 포맷팅: 1개면 그대로, 여러 개면 "첫 번째 항목 (외 N건)"으로 간결화
        if change_items:
            first_item = change_items[0]
            if len(change_items) > 1:
                summary = f"{first_item} (외 {len(change_items)-1}건)"
            else:
                summary = first_item
        else:
            summary = action or "정보 갱신"

        return {
            'timestamp': ts,
            'action': action or "수정",
            'summary': summary,
            'is_excel_init': is_excel_init
        }

    def _bind_single_card_hover(self, card, base_color: str, hover_color: str):
        """단일 카드에 마우스 진입/이탈 시 부드러운 호버 배경색 적용"""
        def on_enter(_):
            try:
                card.configure(fg_color=hover_color)
            except Exception:
                pass
        def on_leave(_):
            try:
                card.configure(fg_color=base_color)
            except Exception:
                pass
        try:
            card.bind("<Enter>", on_enter)
            card.bind("<Leave>", on_leave)
        except Exception:
            pass

    def _bind_entity_click(self, widgets, entity_type: str, target_id: int):
        """엔티티 유형별 1클릭 화면 이동 핸들러 바인딩"""
        for w in widgets:
            try:
                w.bind("<Button-1>", lambda e, et=entity_type, tid=target_id: self._open_entity(et, tid))
            except Exception:
                pass

    def _open_entity(self, entity_type: str, target_id: int):
        """클릭 시 해당 엔티티 화면(처방/원료/거래처)으로 바로 이동합니다."""
        try:
            if entity_type == "처방":
                self.app.navigate_and_record("formulation/all")
            elif entity_type == "원료":
                self._open_material(target_id)
            elif entity_type == "거래처":
                self.app.navigate_and_record("data/client_mgt")
        except Exception as e:
            print(f"[경고] 화면 이동 실패: {e}")

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
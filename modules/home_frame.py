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

        # --- 하단 우측: 최근 성분 변경 이력 ---
        changes_frame = ctk.CTkFrame(bottom_frame)
        changes_frame.grid(row=0, column=1, sticky="nsew", padx=(5, 0))
        changes_frame.grid_rowconfigure(1, weight=1)
        changes_frame.grid_columnconfigure(0, weight=1)

        ctk.CTkLabel(changes_frame, text="최근 성분 변경 이력", font=ctk.CTkFont(size=16, weight="bold")).grid(row=0, column=0, padx=15, pady=10, sticky="w")

        # [수정] Treeview를 Textbox로 변경하여 게시판 형태로 표시
        self.changes_textbox = ctk.CTkTextbox(changes_frame, wrap="word", font=ctk.CTkFont(family="Malgun Gothic", size=13))
        self.changes_textbox.grid(row=1, column=0, sticky="nsew", padx=15, pady=(0, 15))
        self.changes_textbox.configure(state="disabled")

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
        """DB에서 최근 변경된 원료(성분) 목록을 가져와 Treeview에 표시합니다."""
        # [수정] Textbox 내용 초기화
        self.changes_textbox.configure(state="normal")
        self.changes_textbox.delete("1.0", "end")

        session = db_manager.get_session()
        try:
            # updated_at 또는 created_at을 기준으로 최신 5개 항목을 가져옴
            recent_materials = session.query(Material).order_by(
                desc(Material.updated_at), desc(Material.created_at)
            ).limit(5).all()

            if not recent_materials:
                self.changes_textbox.insert("1.0", "최근 성분 변경 이력이 없습니다.")
            else:
                for material in recent_materials:
                    # change_log가 있으면 마지막 로그를, 없으면 생성 로그를 표시
                    if material.change_log:
                        log_entry = material.change_log.split('\n\n')[-1] # 가장 마지막 로그 블록
                        # 로그에서 날짜와 사용자 정보 파싱
                        if " by " in log_entry:
                            # 예: "[2024-07-31 10:00] by admin - 정보 수정"
                            summary = f"'{material.name}' {log_entry.split(' - ', 1)[-1]}"
                            date_str = log_entry.split(']')[0].strip('[')
                            display_text = f"[{date_str}] {summary}\n"
                        else: # 파싱 실패 시
                            display_text = f"'{material.name}' 정보가 변경되었습니다.\n"
                    else: # change_log가 없는 신규 원료
                        date_str = material.created_at.strftime('%Y-%m-%d %H:%M:%S')
                        display_text = f"[{date_str}] 신규 원료 '{material.name}'이(가) 추가되었습니다.\n"
                    
                    self.changes_textbox.insert("end", display_text)

        except Exception as e:
            print(f"최근 성분 변경 이력 로드 중 오류: {e}")
            self.changes_textbox.insert("1.0", "이력 로드 중 오류가 발생했습니다.")
        finally:
            session.close()
            self.changes_textbox.configure(state="disabled")

    def refresh_data(self):
        """홈 프레임에 표시되는 데이터를 새로고침합니다."""
        print("홈 프레임 데이터 새로고침...")
        self.refresh_cards()
        self.load_recent_material_changes()
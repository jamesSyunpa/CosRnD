# -*- coding: utf-8 -*-
import customtkinter as ctk
from tkinter import messagebox
import webbrowser
import os

# 기본 도움말 가이드 목록 (네이버 카페 연동)
DEFAULT_HELP_TOPICS = [
    {
        "category": "기초 시작",
        "title": "CosRQD 화장품 연구관리 시스템 시작 가이드",
        "desc": "프로그램 최초 로그인, 사내 공유 DB 설정 및 기본 테마 설정 안내",
        "keywords": ["시작", "로그인", "설정", "설치", "DB", "기초", "공유"],
        "url": "https://cafe.naver.com/ca-fe/cafes/31737320/articles/4"
    },
    {
        "category": "처방 개발",
        "title": "신규 처방 작성 및 배합비(%) 자동 계산 가이드",
        "desc": "성분 배합비 자동 산출, 원료 검색 및 처방 이력 버전 관리 방법",
        "keywords": ["처방", "배합비", "처방전", "원료", "함량", "레시피", "이력"],
        "url": "https://cafe.naver.com/ca-fe/cafes/31737320/articles/4"
    },
    {
        "category": "원료 관리",
        "title": "화장품 표준 원료 데이터베이스 및 기술서류(TDS/MSDS/COA) 관리",
        "desc": "원료 검색, 성분 분석, 규격서/성적서 등록 및 처방 연동 관리 가이드",
        "keywords": ["원료", "성분", "샘플", "견적", "TDS", "MSDS", "COA", "다운로드", "서류"],
        "url": "https://cafe.naver.com/cosrqd"
    },
    {
        "category": "품질 서류",
        "title": "시험성적서(COA) 및 원료목록보고서 엑셀 원클릭 발행",
        "desc": "완제품/반제품 시험성적서 작성 및 원료목록보고서 자동 생성 가이드",
        "keywords": ["성적서", "COA", "품질", "원료목록", "보고서", "엑셀", "출력"],
        "url": "https://cafe.naver.com/ca-fe/cafes/31737320/articles/4"
    },
    {
        "category": "생산 처방",
        "title": "생산처방전 생성 및 제조 파트/결재방 연동 가이드",
        "desc": "연구 처방을 실제 생산 배치(Batch)용 생산처방전으로 변환 및 결재 승인",
        "keywords": ["생산", "생산처방", "제조", "배치", "결재", "공정", "파트"],
        "url": "https://cafe.naver.com/ca-fe/cafes/31737320/articles/4"
    },
    {
        "category": "공식 카페",
        "title": "CosRQD 공식 네이버 카페 전체 게시판 바로가기",
        "desc": "질의응답(Q&A), 기능 개선 요청 및 최신 화장품 R&D 정보 커뮤니티",
        "keywords": ["카페", "커뮤니티", "질문", "Q&A", "게시판", "업데이트", "건의"],
        "url": "https://cafe.naver.com/ca-fe/cafes/31737320"
    }
]

class HelpViewer(ctk.CTkToplevel):
    """네이버 카페 도움말 검색 및 새창 뷰어 팝업 다이얼로그"""
    def __init__(self, master=None, title="CosRQD 도움말/사용 설명서"):
        super().__init__(master)
        
        self.title(title)
        self.geometry("780x560") 
        self.minsize(650, 450)
        
        # 화면 중앙 정렬
        try:
            self.update_idletasks()
            sw = self.winfo_screenwidth()
            sh = self.winfo_screenheight()
            w, h = 780, 560
            x = (sw - w) // 2
            y = (sh - h) // 2
            self.geometry(f"{w}x{h}+{x}+{y}")
        except Exception:
            pass

        self.attributes("-topmost", True)
        self.topics = DEFAULT_HELP_TOPICS
        
        # 1. 헤더 영역
        hdr_frame = ctk.CTkFrame(self, fg_color="transparent")
        hdr_frame.pack(fill="x", padx=20, pady=(15, 10))
        
        ctk.CTkLabel(
            hdr_frame, 
            text="📖 CosRQD 도움말 / 사용 설명서", 
            font=ctk.CTkFont(size=17, weight="bold")
        ).pack(side="left")
        
        # 공식 카페 바로가기 버튼
        cafe_btn = ctk.CTkButton(
            hdr_frame,
            text="☕ 공식 카페 바로가기",
            width=130,
            height=28,
            fg_color="#03c75a",
            hover_color="#02b150",
            font=ctk.CTkFont(size=12, weight="bold"),
            command=lambda: self.open_url("https://cafe.naver.com/f-e/cafes/31737320")
        )
        cafe_btn.pack(side="right")

        # 2. 검색창 영역
        search_frame = ctk.CTkFrame(self, fg_color="transparent")
        search_frame.pack(fill="x", padx=20, pady=(0, 10))
        
        self.search_entry = ctk.CTkEntry(
            search_frame,
            placeholder_text="🔍 찾으시는 도움말 주제 또는 키워드를 입력하세요 (예: 처방, 성적서, 원료, 샘플)...",
            height=36,
            font=ctk.CTkFont(size=12)
        )
        self.search_entry.pack(fill="x")
        self.search_entry.bind("<KeyRelease>", self.on_search)

        # 3. 도움말 목록 스크롤 프레임
        self.list_frame = ctk.CTkScrollableFrame(self)
        self.list_frame.pack(fill="both", expand=True, padx=20, pady=(0, 10))

        # 4. 하단 닫기 푸터
        footer_frame = ctk.CTkFrame(self, fg_color="transparent", height=40)
        footer_frame.pack(fill="x", padx=20, pady=(0, 15))
        
        ctk.CTkLabel(
            footer_frame,
            text="※ 도움말 항목을 클릭하시면 네이버 카페의 상세 가이드가 새 창으로 열립니다.",
            font=ctk.CTkFont(size=11),
            text_color="gray"
        ).pack(side="left")
        
        close_btn = ctk.CTkButton(
            footer_frame,
            text="닫기",
            width=90,
            height=30,
            command=self.destroy
        )
        close_btn.pack(side="right")

        # 초기 목록 렌더링
        self.render_topics(self.topics)

    def on_search(self, event=None):
        query = self.search_entry.get().strip().lower()
        if not query:
            self.render_topics(self.topics)
            return

        filtered = []
        for t in self.topics:
            title_match = query in t["title"].lower()
            desc_match = query in t["desc"].lower()
            cat_match = query in t["category"].lower()
            kw_match = any(query in kw.lower() for kw in t.get("keywords", []))
            
            if title_match or desc_match or cat_match or kw_match:
                filtered.append(t)

        self.render_topics(filtered, is_empty=(len(filtered) == 0))

    def render_topics(self, topics, is_empty=False):
        for widget in self.list_frame.winfo_children():
            widget.destroy()

        if is_empty or not topics:
            empty_lbl = ctk.CTkLabel(
                self.list_frame,
                text="검색된 도움말 항목이 없습니다.\n검색어를 다시 확인하시거나 공식 카페에 문의해 주세요.",
                font=ctk.CTkFont(size=13),
                text_color="gray"
            )
            empty_lbl.pack(pady=40)
            return

        for item in topics:
            card = ctk.CTkFrame(self.list_frame, corner_radius=6)
            card.pack(fill="x", pady=5, padx=5)

            # 좌측 텍스트
            info_frame = ctk.CTkFrame(card, fg_color="transparent")
            info_frame.pack(side="left", fill="both", expand=True, padx=12, pady=10)

            # 카테고리 뱃지 + 제목
            top_line = ctk.CTkFrame(info_frame, fg_color="transparent")
            top_line.pack(fill="x", anchor="w")

            cat_badge = ctk.CTkLabel(
                top_line,
                text=f"[{item['category']}]",
                font=ctk.CTkFont(size=12, weight="bold"),
                text_color="#38c9a8"
            )
            cat_badge.pack(side="left", padx=(0, 6))

            title_lbl = ctk.CTkLabel(
                top_line,
                text=item["title"],
                font=ctk.CTkFont(size=13, weight="bold")
            )
            title_lbl.pack(side="left")

            # 설명
            desc_lbl = ctk.CTkLabel(
                info_frame,
                text=item["desc"],
                font=ctk.CTkFont(size=11),
                text_color="gray",
                wraplength=520,
                justify="left"
            )
            desc_lbl.pack(anchor="w", pady=(3, 0))

            # 우측 새창 열기 버튼
            url = item["url"]
            open_btn = ctk.CTkButton(
                card,
                text="가이드 보기 ↗",
                width=100,
                height=32,
                font=ctk.CTkFont(size=12, weight="bold"),
                command=lambda u=url: self.open_url(u)
            )
            open_btn.pack(side="right", padx=12, pady=10)

    def open_url(self, url):
        try:
            webbrowser.open_new_tab(url)
        except Exception as e:
            messagebox.showerror("오류", f"웹 브라우저를 여는 중 오류가 발생했습니다:\n{e}")


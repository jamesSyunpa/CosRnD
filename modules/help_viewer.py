# -*- coding: utf-8 -*-
"""
CosRQD 도움말 및 동영상 사용 설명서 뷰어 모듈
- YouTube 동영상 사용 설명서 (웹 브라우저 새 창 재생 지원)
- 네이버 카페 공식 기술 문서 및 매뉴얼 연동
- 실시간 키워드/번호 검색 및 탭 필터링 지원
- 추후 동영상 항목을 리스트에 간단히 추가할 수 있는 구조
"""
import customtkinter as ctk
from tkinter import messagebox
import webbrowser
import os

# ==============================================================================
# 1. YouTube 동영상 가이드 목록 (추후 새 영상 추가 시 아래 리스트에 추가만 하면 자동 반영)
# ==============================================================================
YOUTUBE_VIDEO_GUIDES = [
    {
        "category": "동영상 가이드",
        "num": "1",
        "title": "1. 다운로드",
        "desc": "CosRQD 시스템 최신 설치 패키지 다운로드 및 준비 방법",
        "keywords": ["다운로드", "다운", "download", "설치파일", "1", "시작"],
        "url": "https://youtu.be/AmDBc2OD_5E",
        "type": "youtube"
    },
    {
        "category": "동영상 가이드",
        "num": "2",
        "title": "2. 설치",
        "desc": "프로그램 PC 설치 마법사 진행 및 바탕화면 바로가기 아이콘 생성",
        "keywords": ["설치", "인스톨", "install", "setup", "셋업", "2"],
        "url": "https://youtu.be/imvQcH6x620",
        "type": "youtube"
    },
    {
        "category": "동영상 가이드",
        "num": "3",
        "title": "3. 회원가입",
        "desc": "연구소 마스터 관리자 신규 계정 가입 및 사내 공유 데이터베이스 연결",
        "keywords": ["회원가입", "가입", "계정", "로그인", "마스터", "관리자", "3"],
        "url": "https://youtu.be/vLr4rn1_TNc",
        "type": "youtube"
    },
    {
        "category": "동영상 가이드",
        "num": "3-1",
        "title": "3-1. 직원 회원가입",
        "desc": "사내 연구원 및 부서별 실무자 계정 등록 및 권한 설정 방법",
        "keywords": ["직원", "직원회원가입", "연구원", "사원", "계정", "권한", "3-1", "3.1"],
        "url": "https://youtu.be/40aMhrpvgzE",
        "type": "youtube"
    },
    {
        "category": "동영상 가이드",
        "num": "4",
        "title": "4. 원료 등록",
        "desc": "신규 화장품 원료 등록, TDS/MSDS/COA 서류 및 성분 매핑 가이드",
        "keywords": ["원료", "원료등록", "신규원료", "INCI", "원료사", "등록", "4"],
        "url": "https://youtu.be/Iveeo4jjz6A",
        "type": "youtube"
    },
    {
        "category": "동영상 가이드",
        "num": "5",
        "title": "5. 거래처 등록",
        "desc": "원료 공급사, 외주 제조사 및 완제품 브랜드 고객사 정보 등록",
        "keywords": ["거래처", "거래처등록", "공급사", "고객사", "원료사", "제조사", "5"],
        "url": "https://youtu.be/Pl9DRWgb9uA",
        "type": "youtube"
    },
    {
        "category": "동영상 가이드",
        "num": "6",
        "title": "6. 처방 원료 추가",
        "desc": "개발 중인 연구 처방에 원료를 검색하여 추가하고 배합비(%) 설정",
        "keywords": ["처방", "원료추가", "배합비", "함량", "처방원료", "추가", "6"],
        "url": "https://youtu.be/JIS6md8otwk",
        "type": "youtube"
    },
    {
        "category": "동영상 가이드",
        "num": "7",
        "title": "7. 원료 성분 조회",
        "desc": "원료별 배합 성분(INCI/ICID, CAS 번호, 배합한도 규제) 상세 조회",
        "keywords": ["성분", "원료성분", "성분조회", "INCI", "ICID", "CAS", "배합한도", "7"],
        "url": "https://youtu.be/z60Z9_KjJAE",
        "type": "youtube"
    },
    {
        "category": "동영상 가이드",
        "num": "8",
        "title": "8. 처방 생성",
        "desc": "신규 화장품 제형 처방전 생성, 기본 물성 및 연구 개발 데이터 작성",
        "keywords": ["처방생성", "처방", "신규처방", "레시피", "제형", "개발", "8"],
        "url": "https://youtu.be/nKhPC0ESQsg",
        "type": "youtube"
    },
    {
        "category": "동영상 가이드",
        "num": "9",
        "title": "9. 처방 불러오기",
        "desc": "기존 연구 처방 불러오기, 버전별 이력 비교 및 처방 복사/수정 개발",
        "keywords": ["처방불러오기", "불러오기", "처방복사", "이력", "버전", "처방목록", "9"],
        "url": "https://youtu.be/Zg37gSPSVjU",
        "type": "youtube"
    },
    {
        "category": "동영상 가이드",
        "num": "10",
        "title": "10. 실험 처방 견적 및 내보내기",
        "desc": "개발 처방의 kg당 원가/단가 자동 산출, 견적서 작성 및 엑셀 내보내기",
        "keywords": ["견적", "원가", "단가", "처방견적", "내보내기", "엑셀", "견적서", "10"],
        "url": "https://youtu.be/7B3aaZfvlNA",
        "type": "youtube"
    },
    {
        "category": "동영상 가이드",
        "num": "11",
        "title": "11. 실험 처방 전성분 생성 및 내보내기",
        "desc": "법적 표시기재용 국문/영문 전성분 목록 자동 생성 및 엑셀 보고서 출력",
        "keywords": ["전성분", "전성분생성", "표시기재", "원료목록", "내보내기", "성분표", "11"],
        "url": "https://youtu.be/5X2oW0vwVd0",
        "type": "youtube"
    }
]

# ==============================================================================
# 2. 네이버 카페 공식 문서/매뉴얼 목록
# ==============================================================================
CAFE_DOC_GUIDES = [
    {
        "category": "카페 문서",
        "title": "CosRQD 화장품 연구관리 시스템 시작 가이드",
        "desc": "프로그램 최초 로그인, 사내 공유 DB 설정 및 기본 테마 설정 안내",
        "keywords": ["시작", "로그인", "설정", "설치", "DB", "기초", "공유"],
        "url": "https://cafe.naver.com/ca-fe/cafes/31737320/articles/4",
        "type": "cafe"
    },
    {
        "category": "카페 문서",
        "title": "신규 처방 작성 및 배합비(%) 자동 계산 가이드",
        "desc": "성분 배합비 자동 산출, 원료 검색 및 처방 이력 버전 관리 방법",
        "keywords": ["처방", "배합비", "처방전", "원료", "함량", "레시피", "이력"],
        "url": "https://cafe.naver.com/ca-fe/cafes/31737320/articles/4",
        "type": "cafe"
    },
    {
        "category": "카페 문서",
        "title": "화장품 표준 원료 데이터베이스 및 기술서류(TDS/MSDS/COA) 관리",
        "desc": "원료 검색, 성분 분석, 규격서/성적서 등록 및 처방 연동 관리 가이드",
        "keywords": ["원료", "성분", "샘플", "견적", "TDS", "MSDS", "COA", "다운로드", "서류"],
        "url": "https://cafe.naver.com/cosrqd",
        "type": "cafe"
    },
    {
        "category": "카페 문서",
        "title": "시험성적서(COA) 및 원료목록보고서 엑셀 원클릭 발행",
        "desc": "완제품/반제품 시험성적서 작성 및 원료목록보고서 자동 생성 가이드",
        "keywords": ["성적서", "COA", "품질", "원료목록", "보고서", "엑셀", "출력"],
        "url": "https://cafe.naver.com/ca-fe/cafes/31737320/articles/4",
        "type": "cafe"
    },
    {
        "category": "카페 문서",
        "title": "생산처방전 생성 및 제조 파트/결재방 연동 가이드",
        "desc": "연구 처방을 실제 생산 배치(Batch)용 생산처방전으로 변환 및 결재 승인",
        "keywords": ["생산", "생산처방", "제조", "배치", "결재", "공정", "파트"],
        "url": "https://cafe.naver.com/ca-fe/cafes/31737320/articles/4",
        "type": "cafe"
    },
    {
        "category": "카페 커뮤니티",
        "title": "CosRQD 공식 네이버 카페 전체 게시판 바로가기",
        "desc": "질의응답(Q&A), 기능 개선 요청 및 최신 화장품 R&D 정보 커뮤니티",
        "keywords": ["카페", "커뮤니티", "질문", "Q&A", "게시판", "업데이트", "건의"],
        "url": "https://cafe.naver.com/ca-fe/cafes/31737320",
        "type": "cafe"
    }
]


class HelpViewer(ctk.CTkToplevel):
    """YouTube 동영상 설명서 및 네이버 카페 가이드 통합 뷰어 팝업 다이얼로그"""
    def __init__(self, master=None, title="CosRQD 도움말 / 동영상 사용 설명서"):
        super().__init__(master)
        
        self.title(title)
        self.geometry("820x620") 
        self.minsize(720, 500)
        
        # 화면 중앙 정렬
        try:
            self.update_idletasks()
            sw = self.winfo_screenwidth()
            sh = self.winfo_screenheight()
            w, h = 820, 620
            x = (sw - w) // 2
            y = (sh - h) // 2
            self.geometry(f"{w}x{h}+{x}+{y}")
        except Exception:
            pass

        self.attributes("-topmost", True)
        
        # 전체 데이터 통합
        self.video_topics = YOUTUBE_VIDEO_GUIDES
        self.doc_topics = CAFE_DOC_GUIDES
        self.all_topics = self.video_topics + self.doc_topics
        
        self.current_tab = "동영상 가이드"
        
        # 1. 헤더 영역
        hdr_frame = ctk.CTkFrame(self, fg_color="transparent")
        hdr_frame.pack(fill="x", padx=20, pady=(15, 8))
        
        title_box = ctk.CTkFrame(hdr_frame, fg_color="transparent")
        title_box.pack(side="left")
        
        ctk.CTkLabel(
            title_box, 
            text="🎬 CosRQD 도움말 & 동영상 가이드", 
            font=ctk.CTkFont(size=18, weight="bold")
        ).pack(anchor="w")
        
        ctk.CTkLabel(
            title_box,
            text="각 항목의 '영상 보기'를 클릭하시면 브라우저 새 창에서 고화질 동영상이 재생됩니다.",
            font=ctk.CTkFont(size=11),
            text_color="gray"
        ).pack(anchor="w", pady=(2, 0))
        
        # 우측 공식 카페 버튼
        cafe_btn = ctk.CTkButton(
            hdr_frame,
            text="☕ 공식 카페 바로가기",
            width=140,
            height=30,
            fg_color="#03c75a",
            hover_color="#02b150",
            font=ctk.CTkFont(size=12, weight="bold"),
            command=lambda: self.open_url("https://cafe.naver.com/cosrqd")
        )
        cafe_btn.pack(side="right")

        # 2. 카테고리 필터 탭 (SegmentedButton)
        tab_frame = ctk.CTkFrame(self, fg_color="transparent")
        tab_frame.pack(fill="x", padx=20, pady=(4, 8))
        
        self.seg_btn = ctk.CTkSegmentedButton(
            tab_frame,
            values=[
                f"🎬 동영상 가이드 ({len(self.video_topics)})",
                f"📋 전체 보기 ({len(self.all_topics)})",
                f"📄 카페 문서 ({len(self.doc_topics)})"
            ],
            command=self.on_tab_changed,
            font=ctk.CTkFont(size=12, weight="bold"),
            height=32
        )
        self.seg_btn.pack(side="left")
        self.seg_btn.set(f"🎬 동영상 가이드 ({len(self.video_topics)})")

        # 3. 검색창 영역
        search_frame = ctk.CTkFrame(self, fg_color="transparent")
        search_frame.pack(fill="x", padx=20, pady=(0, 10))
        
        self.search_entry = ctk.CTkEntry(
            search_frame,
            placeholder_text="🔍 찾으시는 영상 번호, 제목, 키워드를 검색하세요 (예: 1, 3-1, 원료, 처방, 견적, 전성분)...",
            height=36,
            font=ctk.CTkFont(size=12)
        )
        self.search_entry.pack(fill="x")
        self.search_entry.bind("<KeyRelease>", self.on_search)

        # 4. 도움말 목록 스크롤 프레임
        self.list_frame = ctk.CTkScrollableFrame(self)
        self.list_frame.pack(fill="both", expand=True, padx=20, pady=(0, 10))

        # 5. 하단 닫기 푸터
        footer_frame = ctk.CTkFrame(self, fg_color="transparent", height=40)
        footer_frame.pack(fill="x", padx=20, pady=(0, 15))
        
        ctk.CTkLabel(
            footer_frame,
            text="💡 유튜브 영상 및 카페 가이드는 PC 웹 브라우저 새 창에서 편리하게 시청하실 수 있습니다.",
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

        # 초기 렌더링 (동영상 가이드 탭)
        self.render_topics(self.video_topics)

    def on_tab_changed(self, value):
        if "동영상" in value:
            self.current_tab = "동영상 가이드"
        elif "카페" in value:
            self.current_tab = "카페 문서"
        else:
            self.current_tab = "전체"
        self.on_search()

    def get_tab_topics(self):
        if self.current_tab == "동영상 가이드":
            return self.video_topics
        elif self.current_tab == "카페 문서":
            return self.doc_topics
        else:
            return self.all_topics

    def on_search(self, event=None):
        query = self.search_entry.get().strip().lower()
        base_topics = self.get_tab_topics()
        
        if not query:
            self.render_topics(base_topics)
            return

        filtered = []
        for t in base_topics:
            num_match = query == t.get("num", "").lower()
            title_match = query in t["title"].lower()
            desc_match = query in t["desc"].lower()
            cat_match = query in t["category"].lower()
            kw_match = any(query in kw.lower() for kw in t.get("keywords", []))
            
            if num_match or title_match or desc_match or cat_match or kw_match:
                filtered.append(t)

        self.render_topics(filtered, is_empty=(len(filtered) == 0))

    def render_topics(self, topics, is_empty=False):
        for widget in self.list_frame.winfo_children():
            widget.destroy()

        if is_empty or not topics:
            empty_box = ctk.CTkFrame(self.list_frame, fg_color="transparent")
            empty_box.pack(pady=50)
            
            ctk.CTkLabel(
                empty_box,
                text="🔍 검색된 가이드 항목이 없습니다.",
                font=ctk.CTkFont(size=14, weight="bold")
            ).pack(pady=(0, 6))
            
            ctk.CTkLabel(
                empty_box,
                text="검색어를 다시 확인하시거나 공식 카페 Q&A 게시판에 문의해 주세요.",
                font=ctk.CTkFont(size=12),
                text_color="gray"
            ).pack()
            return

        for item in topics:
            is_youtube = item.get("type") == "youtube"
            card = ctk.CTkFrame(self.list_frame, corner_radius=8)
            card.pack(fill="x", pady=5, padx=5)

            # 좌측 텍스트 영역
            info_frame = ctk.CTkFrame(card, fg_color="transparent")
            info_frame.pack(side="left", fill="both", expand=True, padx=14, pady=10)

            # 카테고리 뱃지 + 제목 라인
            top_line = ctk.CTkFrame(info_frame, fg_color="transparent")
            top_line.pack(fill="x", anchor="w")

            if is_youtube:
                badge_text = "🎬 동영상 가이드"
                badge_color = "#FF0000"
            else:
                badge_text = f"[{item['category']}]"
                badge_color = "#0284C7"

            cat_badge = ctk.CTkLabel(
                top_line,
                text=badge_text,
                font=ctk.CTkFont(size=11, weight="bold"),
                text_color=badge_color
            )
            cat_badge.pack(side="left", padx=(0, 8))

            title_lbl = ctk.CTkLabel(
                top_line,
                text=item["title"],
                font=ctk.CTkFont(size=14, weight="bold")
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
            desc_lbl.pack(anchor="w", pady=(4, 0))

            # 우측 새창 열기 액션 버튼
            url = item["url"]
            if is_youtube:
                action_btn = ctk.CTkButton(
                    card,
                    text="▶ 영상 보기 ↗",
                    width=115,
                    height=34,
                    fg_color="#CC0000",
                    hover_color="#990000",
                    font=ctk.CTkFont(size=12, weight="bold"),
                    command=lambda u=url: self.open_url(u)
                )
            else:
                action_btn = ctk.CTkButton(
                    card,
                    text="문서 보기 ↗",
                    width=115,
                    height=34,
                    fg_color="#2563EB",
                    hover_color="#1D4ED8",
                    font=ctk.CTkFont(size=12, weight="bold"),
                    command=lambda u=url: self.open_url(u)
                )
            action_btn.pack(side="right", padx=14, pady=10)

    def open_url(self, url):
        """웹 브라우저를 통해 새 창/새 탭에서 동영상 또는 가이드 페이지를 엽니다."""
        try:
            webbrowser.open_new_tab(url)
        except Exception as e:
            messagebox.showerror("오류", f"웹 브라우저를 여는 중 오류가 발생했습니다:\n{e}")


# -*- coding: utf-8 -*-
"""
네이버 카페(CosRQD) 실시간 공지사항 및 게시글 연동 모듈
- 카페 ID: 31737320 (CosRQD)
- 주요 대상 메뉴: 3 (전체공지 / 필독사항), 4 (자료 다운로드 / 배포공지)
"""

import urllib.request
import urllib.error
import ssl
import json
from datetime import datetime
from bs4 import BeautifulSoup

class CafeNoticeManager:
    CAFE_ID = 31737320
    CAFE_URL = "https://cafe.naver.com/cosrqd"
    
    # 기본 헤더 설정 (네이버 게이트웨이 호출용)
    HEADERS = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Referer": "https://cafe.naver.com/cosrqd"
    }

    @classmethod
    def _http_get_json(cls, url: str) -> dict:
        """urllib 표준 라이브러리를 사용하여 안전하게 JSON 데이터를 가져옵니다."""
        req = urllib.request.Request(url, headers=cls.HEADERS)
        ctx = ssl.create_default_context()
        ctx.check_hostname = False
        ctx.verify_mode = ssl.CERT_NONE
        try:
            with urllib.request.urlopen(req, timeout=4.0, context=ctx) as response:
                if response.status == 200:
                    return json.loads(response.read().decode('utf-8'))
        except Exception as e:
            print(f"[CafeNotice] HTTP 요청 실패 ({url}): {e}")
        return {}

    @classmethod
    def get_notice_list(cls, menu_ids=[13], per_page=10):
        """
        공지사항 게시판(오직 메뉴 13: 공지 및 업데이트 단독)의 글 목록을 가져옵니다.
        """
        articles = []
        for m_id in menu_ids:
            api_url = f"https://apis.naver.com/cafe-web/cafe-boardlist-api/v1/cafes/{cls.CAFE_ID}/menus/{m_id}/articles?page=1&perPage={per_page}"
            try:
                data = cls._http_get_json(api_url)
                item_list = data.get("result", {}).get("articleList", [])
                for entry in item_list:
                    item = entry.get("item", {})
                    art_id = item.get("articleId")
                    subject = item.get("subject", "")
                    ts = item.get("writeDateTimestamp", 0)
                    summary = item.get("summary", "")
                    writer = item.get("writerInfo", {}).get("nickName", "관리자")
                    
                    date_str = ""
                    if ts:
                        try:
                            date_str = datetime.fromtimestamp(ts / 1000.0).strftime("%Y-%m-%d")
                        except:
                            date_str = ""
                            
                    if art_id and subject:
                        articles.append({
                            "id": art_id,
                            "menu_id": m_id,
                            "subject": subject,
                            "date": date_str,
                            "timestamp": ts,
                            "summary": summary,
                            "writer": writer,
                            "url": f"https://cafe.naver.com/cosrqd/{art_id}"
                        })
            except Exception as e:
                print(f"[CafeNotice] 메뉴 {m_id} 목록 로드 실패: {e}")
                
        # 작성일 최신순 정렬
        articles.sort(key=lambda x: x.get("timestamp", 0), reverse=True)
        return articles

    @classmethod
    def get_article_content(cls, article_id):
        """
        특정 게시글의 전체 본문 텍스트를 가져옵니다.
        """
        if not article_id:
            return ""
        api_url = f"https://apis.naver.com/cafe-web/cafe-articleapi/v2.1/cafes/{cls.CAFE_ID}/articles/{article_id}"
        try:
            data = cls._http_get_json(api_url)
            article = data.get("result", {}).get("article", {})
            content_html = article.get("contentHtml", "")
            
            if content_html:
                soup = BeautifulSoup(content_html, "html.parser")
                text = soup.get_text(separator="\n", strip=True)
                return text
        except Exception as e:
            print(f"[CafeNotice] 글 ID {article_id} 본문 로드 실패: {e}")
            
        return ""

    @classmethod
    def get_latest_notice_full_text(cls):
        """
        홈 화면에 그대로 뿌려줄 수 있는 최신 공지사항 전문(제목+날짜+본문)을 가공하여 반환합니다.
        """
        articles = cls.get_notice_list(menu_ids=[13])
        
        if not articles:
            # 공지글이 없을 경우 기본 안내 텍스트
            return (
                "📢 [시스템 공지사항 및 업데이트]\n"
                "--------------------------------------------------\n"
                "현재 등록된 최신 공지사항이 없습니다.\n\n"
                "CosRQD 공식 네이버 카페:\n"
                "https://cafe.naver.com/cosrqd"
            )
            
        # 가장 최신 글 1건 가져오기
        latest = articles[0]
        art_id = latest["id"]
        subject = latest["subject"]
        date_str = latest["date"]
        writer = latest["writer"]
        
        # 본문 가져오기
        content = cls.get_article_content(art_id)
        if not content:
            content = latest.get("summary", "본문 내용을 불러올 수 없습니다.")
            
        output = [
            f"📢 [공지] {subject}",
            f"작성일: {date_str} | 작성자: {writer}",
            "--------------------------------------------------",
            content,
            "\n--------------------------------------------------",
            f"🌐 카페 원문: https://cafe.naver.com/cosrqd/{art_id}"
        ]
        
        # 2번째 이후 최신 글이 더 있다면 하단에 목록으로 첨부
        if len(articles) > 1:
            output.append("\n[📋 다른 최근 공지 목록]")
            for other in articles[1:4]:
                output.append(f"• {other['subject']} ({other['date']})")
                
        return "\n".join(output)

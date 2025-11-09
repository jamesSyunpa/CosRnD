import os
import math
from typing import List, Tuple, Optional
from PIL import Image, ImageDraw, ImageFont, ImageTk
import tkinter as tk
import customtkinter as ctk

# A4 at 144 DPI
DPI = 144
A4_WIDTH_IN = 8.27
A4_HEIGHT_IN = 11.69
PAGE_W = int(A4_WIDTH_IN * DPI)
PAGE_H = int(A4_HEIGHT_IN * DPI)
# Margins (match revised export roughly): L/R=0.3in, T/B=0.4in
MARGIN_L = int(0.3 * DPI)
MARGIN_R = int(0.3 * DPI)
MARGIN_T = int(0.4 * DPI)
MARGIN_B = int(0.4 * DPI)
CONTENT_W = PAGE_W - MARGIN_L - MARGIN_R
CONTENT_H = PAGE_H - MARGIN_T - MARGIN_B

# Fixed column widths mapping from revised export (A..H)
COLS = ['A','B','C','D','E','F','G','H']
COL_WIDTHS = [8, 10, 15, 45, 12, 12, 26, 22]
COL_SUM = sum(COL_WIDTHS)
COL_PIX = [int(CONTENT_W * (w / COL_SUM)) for w in COL_WIDTHS]

LINE_H = 18  # base line height for wrapped cells
ROW_H_BASE = 24
TITLE_H = 60
HEADER_H = 28
INFO_ROW_H = 24
APPROVAL_H = 2 * INFO_ROW_H
GRID_COLOR = (44, 62, 80)
HEADER_FILL = (91, 155, 213)   # 5B9BD5
LABEL_FILL = (213, 232, 240)   # D5E8F0
HEADER_TEXT = (255, 255, 255)
TEXT_COLOR = (44, 62, 80)


def _load_font(pref: str, size: int):
    try:
        return ImageFont.truetype(pref, size)
    except Exception:
        try:
            # Fallback to Malgun Gothic variants commonly available
            return ImageFont.truetype("malgun.ttf", size)
        except Exception:
            return ImageFont.load_default()


TITLE_FONT = _load_font("malgunbd.ttf", 28)
HEADER_FONT = _load_font("malgunbd.ttf", 16)
BOLD_FONT = _load_font("malgunbd.ttf", 14)
NORMAL_FONT = _load_font("malgun.ttf", 14)
SMALL_FONT = _load_font("malgun.ttf", 12)


def _draw_text_center(draw: ImageDraw.ImageDraw, box: Tuple[int,int,int,int], text: str, font, fill=TEXT_COLOR):
    x0, y0, x1, y1 = box
    w, h = draw.textbbox((0,0), text or "", font=font)[2:4]
    cx = (x0 + x1) // 2
    cy = (y0 + y1) // 2
    draw.text((cx - w//2, cy - h//2), text or "", font=font, fill=fill)


def _draw_text_left_top(draw: ImageDraw.ImageDraw, box: Tuple[int,int,int,int], text: str, font, fill=TEXT_COLOR, pad=6):
    x0, y0, x1, y1 = box
    y = y0 + pad
    for line in (text or "").splitlines() or [""]:
        draw.text((x0 + pad, y), line, font=font, fill=fill)
        y += LINE_H


def _calc_lines(text: Optional[str]) -> int:
    if not text:
        return 1
    return max(1, text.count('\n') + 1)


def render_production_preview_pages(production_data: dict) -> List[Image.Image]:
    pages: List[Image.Image] = []

    def new_page():
        img = Image.new('RGB', (PAGE_W, PAGE_H), 'white')
        d = ImageDraw.Draw(img)
        # page border (optional)
        # d.rectangle([0,0,PAGE_W-1,PAGE_H-1], outline=(200,200,200))
        return img, d

    img, draw = new_page()
    y = MARGIN_T
    x = MARGIN_L

    # 1) Title A1:F2 (left area merged)
    title_w = sum(COL_PIX[:6])
    draw.rectangle([x, y, x + title_w, y + TITLE_H], outline=GRID_COLOR, width=1)
    _draw_text_center(draw, (x, y, x + title_w, y + TITLE_H), "생산지시서", TITLE_FONT)

    # 2) Approval G1:H2: 스탬프 그리드(왼쪽 '결/재' + 상단 '작성/검토/승인' + 하단 서명칸)
    appr_x = x + title_w
    appr_w = CONTENT_W - title_w  # G+H 폭
    # 바깥 테두리
    draw.rectangle([appr_x, y, appr_x + appr_w, y + TITLE_H], outline=GRID_COLOR, width=2)
    # 왼쪽 라벨 영역 폭
    left_w = max(28, int(appr_w * 0.12))
    # 세로 구분선 (왼쪽 라벨/3분할)
    draw.line([appr_x + left_w, y, appr_x + left_w, y + TITLE_H], fill=GRID_COLOR, width=2)
    # 3분할
    col_w = (appr_w - left_w) // 3
    draw.line([appr_x + left_w + col_w, y, appr_x + left_w + col_w, y + TITLE_H], fill=GRID_COLOR, width=2)
    draw.line([appr_x + left_w + col_w*2, y, appr_x + left_w + col_w*2, y + TITLE_H], fill=GRID_COLOR, width=2)
    # 헤더/서명 구분선: 왼쪽 라벨 칸은 위 칸과 병합되도록 선을 비켜서 그림
    header_h = int(TITLE_H * 0.55)
    draw.line([appr_x + left_w, y + header_h, appr_x + appr_w, y + header_h], fill=GRID_COLOR, width=2)
    # 내부 구분선 없이, 왼쪽 라벨 전체 높이를 반으로 나눠 각 절반의 가운데 정렬
    _draw_text_center(draw, (appr_x, y, appr_x + left_w, y + TITLE_H//2), '결', BOLD_FONT)
    _draw_text_center(draw, (appr_x, y + TITLE_H//2, appr_x + left_w, y + TITLE_H), '재', BOLD_FONT)
    # 헤더 텍스트
    for i, txt in enumerate(["작성","검토","승인"]):
        cx0 = appr_x + left_w + i*col_w
        _draw_text_center(draw, (cx0, y, cx0 + col_w, y + header_h), txt, BOLD_FONT)
    y += TITLE_H

    # 3) Basic info per revised layout
    details = production_data.get('details', {})

    def ensure_page_space(min_height: int):
        nonlocal img, draw, y
        if y + min_height > PAGE_H - MARGIN_B:
            pages.append(img)
            img, draw = new_page()
            y = MARGIN_T
    # Row 3 (제품명 A3:D3, 생산코드 E3:F3, 제조자 G3:H3)
    ensure_page_space(INFO_ROW_H)
    # A3 라벨 셀
    a0 = x + sum(COL_PIX[:0]); a1 = x + sum(COL_PIX[:1])
    draw.rectangle([a0, y, a1, y + INFO_ROW_H], fill=LABEL_FILL, outline=GRID_COLOR, width=1)
    _draw_text_center(draw, (a0, y, a1, y + INFO_ROW_H), '제품명', BOLD_FONT)
    # B3:D3 병합 값 영역
    bd0 = x + sum(COL_PIX[:1]); bd1 = x + sum(COL_PIX[:4])
    draw.rectangle([bd0, y, bd1, y + INFO_ROW_H], outline=GRID_COLOR, width=1)
    prod_name = str(details.get('제품명','') or '')
    _draw_text_left_top(draw, (bd0, y, bd1, y + INFO_ROW_H), prod_name, NORMAL_FONT)
    # E3:F3 생산코드
    e0 = x + sum(COL_PIX[:4]); e1 = x + sum(COL_PIX[:5])
    draw.rectangle([e0, y, e1, y + INFO_ROW_H], fill=LABEL_FILL, outline=GRID_COLOR, width=1)
    _draw_text_center(draw, (e0, y, e1, y + INFO_ROW_H), '생산코드', BOLD_FONT)
    f0 = x + sum(COL_PIX[:5]); f1 = x + sum(COL_PIX[:6])
    draw.rectangle([f0, y, f1, y + INFO_ROW_H], outline=GRID_COLOR, width=1)
    _draw_text_left_top(draw, (f0, y, f1, y + INFO_ROW_H), str(details.get('생산코드','') or ''), NORMAL_FONT)
    # G3:H3 제조자
    g0 = x + sum(COL_PIX[:6]); g1 = x + sum(COL_PIX[:7])
    draw.rectangle([g0, y, g1, y + INFO_ROW_H], fill=LABEL_FILL, outline=GRID_COLOR, width=1)
    _draw_text_center(draw, (g0, y, g1, y + INFO_ROW_H), '제조자', BOLD_FONT)
    h0 = x + sum(COL_PIX[:7]); h1 = x + sum(COL_PIX[:8])
    draw.rectangle([h0, y, h1, y + INFO_ROW_H], outline=GRID_COLOR, width=1)
    _draw_text_left_top(draw, (h0, y, h1, y + INFO_ROW_H), str(details.get('제조자','') or ''), NORMAL_FONT)
    y += INFO_ROW_H

    # Row 4: 지시일/적용일/생산량(kg)/수득량
    ensure_page_space(INFO_ROW_H)
    # A4 라벨/값
    ax0 = x + sum(COL_PIX[:0]); ax1 = x + sum(COL_PIX[:1])
    draw.rectangle([ax0, y, ax1, y + INFO_ROW_H], fill=LABEL_FILL, outline=GRID_COLOR, width=1)
    _draw_text_center(draw, (ax0, y, ax1, y + INFO_ROW_H), '지시일', BOLD_FONT)
    bx0 = x + sum(COL_PIX[:1]); bx1 = x + sum(COL_PIX[:2])
    draw.rectangle([bx0, y, bx1, y + INFO_ROW_H], outline=GRID_COLOR, width=1)
    _draw_text_left_top(draw, (bx0, y, bx1, y + INFO_ROW_H), str(details.get('지시일', details.get('출력일시','')) or ''), NORMAL_FONT)
    # C/D
    cx0 = x + sum(COL_PIX[:2]); cx1 = x + sum(COL_PIX[:3])
    draw.rectangle([cx0, y, cx1, y + INFO_ROW_H], fill=LABEL_FILL, outline=GRID_COLOR, width=1)
    _draw_text_center(draw, (cx0, y, cx1, y + INFO_ROW_H), '적용일', BOLD_FONT)
    dx0 = x + sum(COL_PIX[:3]); dx1 = x + sum(COL_PIX[:4])
    draw.rectangle([dx0, y, dx1, y + INFO_ROW_H], outline=GRID_COLOR, width=1)
    _draw_text_left_top(draw, (dx0, y, dx1, y + INFO_ROW_H), str(details.get('적용일','') or ''), NORMAL_FONT)
    # E/F
    ex0 = x + sum(COL_PIX[:4]); ex1 = x + sum(COL_PIX[:5])
    draw.rectangle([ex0, y, ex1, y + INFO_ROW_H], fill=LABEL_FILL, outline=GRID_COLOR, width=1)
    _draw_text_center(draw, (ex0, y, ex1, y + INFO_ROW_H), '생산량(kg)', BOLD_FONT)
    fx0 = x + sum(COL_PIX[:5]); fx1 = x + sum(COL_PIX[:6])
    draw.rectangle([fx0, y, fx1, y + INFO_ROW_H], outline=GRID_COLOR, width=1)
    _draw_text_left_top(draw, (fx0, y, fx1, y + INFO_ROW_H), str(details.get('생산량(kg)','') or ''), NORMAL_FONT)
    # G/H
    gx0 = x + sum(COL_PIX[:6]); gx1 = x + sum(COL_PIX[:7])
    draw.rectangle([gx0, y, gx1, y + INFO_ROW_H], fill=LABEL_FILL, outline=GRID_COLOR, width=1)
    _draw_text_center(draw, (gx0, y, gx1, y + INFO_ROW_H), '수득량', BOLD_FONT)
    hx0 = x + sum(COL_PIX[:7]); hx1 = x + sum(COL_PIX[:8])
    draw.rectangle([hx0, y, hx1, y + INFO_ROW_H], outline=GRID_COLOR, width=1)
    _draw_text_left_top(draw, (hx0, y, hx1, y + INFO_ROW_H), str(details.get('수득량','') or ''), NORMAL_FONT)
    y += INFO_ROW_H

    # Spacer
    ensure_page_space(8)
    y += 8

    # 4) Table header (A..H)
    ensure_page_space(HEADER_H)
    cx = x
    for c_idx, head in enumerate(["Ph", "구분", "코드", "원료명", "함량(%)", "생산량(kg)", "제조공정", "공정검사"]):
        cw = COL_PIX[c_idx]
        draw.rectangle([cx, y, cx + cw, y + HEADER_H], fill=HEADER_FILL, outline=GRID_COLOR, width=1)
        _draw_text_center(draw, (cx, y, cx + cw, y + HEADER_H), head, HEADER_FONT, fill=HEADER_TEXT)
        cx += cw
    y += HEADER_H

    # 5) Rows with vertical merges for A/G/H per phase group
    def norm_phase(v: Optional[str]) -> str:
        s = str(v).strip() if v is not None else ''
        return s.replace('Ph.', '').replace('PH', '').strip() if s else ''

    items = production_data.get('items', []) or []
    # build groups of consecutive same phase
    groups: List[Tuple[str, int, int]] = []
    if items:
        cur = norm_phase(items[0].get('Ph') or items[0].get('Ph.', ''))
        start_idx = 0
        for idx in range(1, len(items)):
            ph = norm_phase(items[idx].get('Ph') or items[idx].get('Ph.', ''))
            if ph != cur:
                groups.append((cur, start_idx, idx-1))
                start_idx = idx; cur = ph
        groups.append((cur, start_idx, len(items)-1))

    total_ratio = 0.0
    for ph, s_idx, e_idx in groups:
        # compute per-row heights first and ensure group fits page
        row_heights: List[int] = []
        group_proc_texts: List[str] = []
        group_insp_texts: List[str] = []
        for i in range(s_idx, e_idx+1):
            it = items[i]
            ptxt = (str(it.get('제조공정','') or '').replace('"','').replace("'", ''))
            itxt = (str(it.get('공정검사','') or '').replace('"','').replace("'", ''))
            group_proc_texts.append(ptxt)
            group_insp_texts.append(itxt)
            lines = max(_calc_lines(ptxt), _calc_lines(itxt))
            row_heights.append(max(ROW_H_BASE, LINE_H * lines + 6))
        # if not enough space, start new page before the group
        group_total_h = sum(row_heights)
        ensure_page_space(group_total_h)
        group_y_start = y

        # draw rows for columns B..F
        for rel, hgt in enumerate(row_heights):
            ensure_page_space(hgt)
            it = items[s_idx + rel]
            cx = x
            values = [
                None,  # A merged later
                it.get('구분'), it.get('코드'), it.get('원료명'),
                it.get('함량(%)'), it.get('생산량(kg)')
            ]
            for c_idx, val in enumerate(values):
                # actual column index = c_idx + 0; but skip A(0)
                if c_idx == 0:
                    # skip A
                    cx += COL_PIX[0]
                    continue
                cw = COL_PIX[c_idx]
                box = (cx, y, cx + cw, y + hgt)
                draw.rectangle(box, outline=GRID_COLOR, width=1)
                if c_idx in (1,2):
                    _draw_text_center(draw, box, str(val or ''), NORMAL_FONT)
                elif c_idx == 3:
                    _draw_text_left_top(draw, box, str(val or ''), NORMAL_FONT)
                elif c_idx in (4,5):
                    text = ""
                    try:
                        fval = float(val)
                        if c_idx == 4:
                            total_ratio += fval
                            text = f"{fval:.4f}"
                        else:
                            text = f"{fval:,.1f}"
                    except Exception:
                        text = str(val or "")
                    _draw_text_center(draw, box, text, NORMAL_FONT)
                cx += cw
            # skip G/H per-row; merged later
            y += hgt

        # merged cells for A, G, H across group
        group_y_end = y
        # A column merged
        a_x0 = x; a_x1 = x + COL_PIX[0]
        draw.rectangle([a_x0, group_y_start, a_x1, group_y_end], outline=GRID_COLOR, width=1)
        _draw_text_center(draw, (a_x0, group_y_start, a_x1, group_y_end), ph or '', BOLD_FONT)
        # G column merged (use longest text in group)
        g_text = max(group_proc_texts, key=len) if group_proc_texts else ''
        g_x0 = x + sum(COL_PIX[:6]); g_x1 = x + sum(COL_PIX[:7])
        draw.rectangle([g_x0, group_y_start, g_x1, group_y_end], outline=GRID_COLOR, width=1)
        _draw_text_left_top(draw, (g_x0, group_y_start, g_x1, group_y_end), g_text, NORMAL_FONT)
        # H column merged
        h_text = max(group_insp_texts, key=len) if group_insp_texts else ''
        h_x0 = x + sum(COL_PIX[:7]); h_x1 = x + sum(COL_PIX[:8])
        draw.rectangle([h_x0, group_y_start, h_x1, group_y_end], outline=GRID_COLOR, width=1)
        _draw_text_left_top(draw, (h_x0, group_y_start, h_x1, group_y_end), h_text, NORMAL_FONT)

    # 6) Sum row
    sum_h = HEADER_H
    ensure_page_space(sum_h)
    cx = x
    for c_idx in range(8):
        cw = COL_PIX[c_idx]
        box = (cx, y, cx + cw, y + sum_h)
        draw.rectangle(box, fill=HEADER_FILL, outline=GRID_COLOR, width=1)
        if c_idx == 0:
            _draw_text_center(draw, box, "합계 (Total)", HEADER_FONT, fill=HEADER_TEXT)
        if c_idx == 4:
            _draw_text_center(draw, box, f"{total_ratio:.4f}", HEADER_FONT, fill=HEADER_TEXT)
        cx += cw
    y += sum_h

    # finalize last page
    pages.append(img)

    # --- Footer: Page X / N  ·  Printed at yyyy-mm-dd HH:MM ---
    try:
        import datetime as _dt
        printed = _dt.datetime.now().strftime('%Y-%m-%d %H:%M')
    except Exception:
        printed = ""
    total = len(pages)
    for idx, p in enumerate(pages):
        d = ImageDraw.Draw(p)
        footer_text = f"Page {idx+1} / {total}    Printed: {printed}"
        # draw at bottom within margins
        y_footer = PAGE_H - MARGIN_B + int(0.15 * DPI)
        d.text((MARGIN_L, y_footer), footer_text, font=SMALL_FONT, fill=(120,120,120))

    return pages


class _PreviewWindow(ctk.CTkToplevel):
    def __init__(self, master, pages: List[Image.Image]):
        super().__init__(master)
        self.title("인쇄 미리보기 (A4)")
        self.geometry("980x720")
        self.pages = pages
        self.page_index = 0
        # 최초 표시를 최소 배율로 설정
        self.zoom = 0.2  # 초기값(곧 캔버스 크기에 맞게 자동 조정됨)
        self.user_zoom = False  # 사용자가 수동으로 확대/축소했는지 여부

        top = ctk.CTkFrame(self)
        top.pack(fill="x", padx=8, pady=(8,4))
        ctk.CTkButton(top, text="◀ 이전", width=80, command=self.prev_page).pack(side="left")
        ctk.CTkButton(top, text="다음 ▶", width=80, command=self.next_page).pack(side="left", padx=(6,0))
        ctk.CTkLabel(top, text="확대/축소").pack(side="left", padx=(16,4))
        self.zoom_var = tk.DoubleVar(value=self.zoom)
        # 최소 배율을 0.2로 낮추고, 초기값도 최소값으로 지정
        z = ctk.CTkSlider(top, from_=0.2, to=2.0, number_of_steps=36, variable=self.zoom_var, command=self.on_zoom)
        z.pack(side="left", fill="x", expand=True, padx=(0,8))

        mid = ctk.CTkFrame(self)
        mid.pack(fill="both", expand=True, padx=8, pady=8)

        # Canvas + Scrollbars 컨테이너
        container = tk.Frame(mid)
        container.pack(fill="both", expand=True)

        self.canvas = tk.Canvas(container, bg="#888888", highlightthickness=0)
        hbar = tk.Scrollbar(container, orient="horizontal", command=self.canvas.xview)
        vbar = tk.Scrollbar(container, orient="vertical", command=self.canvas.yview)
        self.canvas.configure(xscrollcommand=hbar.set, yscrollcommand=vbar.set)

        # 배치: 캔버스는 중앙, 스크롤바는 하단/우측
        self.canvas.grid(row=0, column=0, sticky="nsew")
        vbar.grid(row=0, column=1, sticky="ns")
        hbar.grid(row=1, column=0, sticky="ew")
        container.rowconfigure(0, weight=1)
        container.columnconfigure(0, weight=1)

        # Ctrl + MouseWheel 줌 바인딩 (Windows)
        self.canvas.bind("<Control-MouseWheel>", self.on_ctrl_wheel)
        # 캔버스 리사이즈 시, 사용자 수동 줌이 없으면 창 크기에 비례해 A4 전체가 보이도록 맞춤
        self.canvas.bind("<Configure>", self.on_canvas_configure)

        # 창이 열릴 때 내용이 반드시 보이도록, 캔버스 준비 후 맞춤 적용
        self.after(30, self.fit_page_to_canvas)
        self.render_current_page()
        try:
            self.transient(master)
            self.grab_set()
        except Exception:
            pass

    def on_zoom(self, *_):
        self.user_zoom = True
        self.zoom = float(self.zoom_var.get())
        self.render_current_page()

    def prev_page(self):
        if self.page_index > 0:
            self.page_index -= 1
            self.render_current_page()

    def next_page(self):
        if self.page_index < len(self.pages) - 1:
            self.page_index += 1
            self.render_current_page()

    def render_current_page(self):
        # 현재 뷰 위치 저장(스크롤 비율)
        try:
            x0, _ = self.canvas.xview()
            y0, _ = self.canvas.yview()
        except Exception:
            x0 = y0 = 0.0

        img = self.pages[self.page_index]
        w = int(img.width * self.zoom)
        h = int(img.height * self.zoom)
        disp = img.resize((w, h), Image.LANCZOS)
        self.tk_img = ImageTk.PhotoImage(disp)
        self.canvas.delete("all")
        # (0,0)부터 시작하여 스크롤로 이동
        self.canvas.create_image(0, 0, anchor="nw", image=self.tk_img)
        self.canvas.configure(scrollregion=(0, 0, w, h))
        # 이전 스크롤 위치 복원
        try:
            self.canvas.xview_moveto(x0)
            self.canvas.yview_moveto(y0)
        except Exception:
            pass

    def on_ctrl_wheel(self, event):
        # Windows: event.delta 양수=위(줌 인), 음수=아래(줌 아웃)
        step = 0.1
        new_zoom = self.zoom + (step if event.delta > 0 else -step)
        # 슬라이더 범위와 동기화 (0.2 ~ 2.0)
        new_zoom = max(0.2, min(2.0, new_zoom))
        if abs(new_zoom - self.zoom) < 1e-6:
            return
        self.user_zoom = True
        self.zoom = new_zoom
        self.zoom_var.set(self.zoom)
        self.render_current_page()

    def on_canvas_configure(self, _event):
        # 사용자가 수동으로 줌을 조정하지 않았다면 창 크기에 맞게 자동 맞춤
        if not self.user_zoom:
            self.fit_page_to_canvas()

    def fit_page_to_canvas(self):
        # 캔버스 실제 크기에 맞춰 A4 페이지 전체가 보이도록 배율 계산
        cw = self.canvas.winfo_width()
        ch = self.canvas.winfo_height()
        if cw <= 1 or ch <= 1:
            return
        pad = 4
        fit_w = (cw - pad) / PAGE_W
        fit_h = (ch - pad) / PAGE_H
        fit_zoom = max(0.2, min(2.0, min(fit_w, fit_h)))
        if abs(fit_zoom - self.zoom) > 1e-3:
            self.zoom = fit_zoom
            self.zoom_var.set(self.zoom)
            self.render_current_page()


def show_production_print_preview(production_data: dict, parent):
    pages = render_production_preview_pages(production_data)
    _PreviewWindow(parent, pages)

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
# '계량량(kg)' 열을 생산량 옆에 추가: A..I (Ph, 구분, 코드, 원료명, 함량, 생산량, 계량량, 제조공정, 공정검사)
COL_WIDTHS = [8, 10, 15, 45, 12, 12, 12, 12, 12, 12, 15, 15, 15]
COL_SUM = sum(COL_WIDTHS)
COL_PIX = [int(CONTENT_W * (w / COL_SUM)) for w in COL_WIDTHS]

LINE_H = 14  # base line height for wrapped cells (reduced for tighter rows)
ROW_H_BASE = 16  # minimal row height for single-line rows
TITLE_H = 60
HEADER_H = 22  # table header height reduced
INFO_ROW_H = 20  # info rows slightly reduced
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


def _draw_text_left_top(draw: ImageDraw.ImageDraw, box: Tuple[int,int,int,int], text: str, font, fill=TEXT_COLOR, pad=4):
    x0, y0, x1, y1 = box
    y = y0 + pad
    for line in (text or "").splitlines() or [""]:
        draw.text((x0 + pad, y), line, font=font, fill=fill)
        y += LINE_H

def _draw_text_left_vcenter(draw: ImageDraw.ImageDraw, box: Tuple[int,int,int,int], text: str, font, fill=TEXT_COLOR, pad=4):
    """왼쪽 정렬 + 세로 중앙 정렬로 여러 줄 텍스트를 그립니다.
    실제 글꼴 bbox를 사용해 줄 높이를 계산하여 잘림을 방지합니다.
    """
    x0, y0, x1, y1 = box
    lines = (text or "").splitlines() or [""]
    # 실제 라인 높이 추정 (대표 문자열로 측정)
    try:
        lh = draw.textbbox((0,0), "Ag한", font=font)[3]
    except Exception:
        lh = LINE_H
    line_h = max(LINE_H, lh)
    total_h = max(line_h, len(lines) * line_h)
    box_h = max(0, y1 - y0)
    # 상하 여백을 고려한 중앙 배치 (최소 pad 유지)
    y = y0 + max(pad, (box_h - total_h) // 2)
    for line in lines:
        draw.text((x0 + pad, y), line, font=font, fill=fill)
        y += line_h


def _wrap_text_by_width(draw: ImageDraw.ImageDraw, text: str, font, max_width: int) -> str:
    """Wrap text to fit within max_width using draw.textbbox for measurement.
    Works for languages without spaces by falling back to char-based wrapping.
    Preserves existing newlines by wrapping per paragraph.
    """
    if not text:
        return ""
    paragraphs = str(text).splitlines() or [""]
    wrapped_lines = []
    for para in paragraphs:
        if not para:
            wrapped_lines.append("")
            continue
        line = ""
        # Try word-based first
        tokens = para.split(" ")
        if len(tokens) == 1:
            # No spaces -> char-based wrapping
            for ch in para:
                test = line + ch
                w = draw.textbbox((0,0), test, font=font)[2]
                if w <= max_width or not line:
                    line = test
                else:
                    wrapped_lines.append(line)
                    line = ch
            if line:
                wrapped_lines.append(line)
        else:
            for idx, tok in enumerate(tokens):
                test = (line + (" " if line else "") + tok)
                w = draw.textbbox((0,0), test, font=font)[2]
                if w <= max_width or not line:
                    line = test
                else:
                    wrapped_lines.append(line)
                    line = tok
            if line:
                wrapped_lines.append(line)
    return "\n".join(wrapped_lines)


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
    details = production_data.get('details', {})

    # 1) a1:e2 (생산지시서) merged
    title_w = sum(COL_PIX[:5])  # A-E is indices 0-4
    draw.rectangle([x, y, x + title_w, y + TITLE_H], outline=GRID_COLOR, width=1)
    _draw_text_center(draw, (x, y, x + title_w, y + TITLE_H), "생산지시서", TITLE_FONT)

    # 2) f1:f2 (결제방) merged
    fy1 = y
    fy2 = y + TITLE_H
    fx0 = x + sum(COL_PIX[:5])  # F is index 5
    fx1 = x + sum(COL_PIX[:6])
    draw.rectangle([fx0, fy1, fx1, fy2], fill=LABEL_FILL, outline=GRID_COLOR, width=1)
    f1f2_value = str(details.get('결제방','') or '')
    if f1f2_value:
        _draw_text_center(draw, (fx0, fy1, fx1, fy2), "결제방: " + f1f2_value, BOLD_FONT)
    else:
        _draw_text_center(draw, (fx0, fy1, fx1, fy2), "결제방", BOLD_FONT)
    
    # 3) g1 (작성) g2 (빈칸)
    gy1_top = y
    gy1_mid = y + TITLE_H // 2
    gy1_bottom = y + TITLE_H
    gx0 = x + sum(COL_PIX[:6])  # G is index 6
    gx1 = x + sum(COL_PIX[:7])
    draw.rectangle([gx0, gy1_top, gx1, gy1_mid], fill=LABEL_FILL, outline=GRID_COLOR, width=1)
    _draw_text_center(draw, (gx0, gy1_top, gx1, gy1_mid), "작성", BOLD_FONT)
    draw.rectangle([gx0, gy1_mid, gx1, gy1_bottom], outline=GRID_COLOR, width=1)
    # 4) h1 (검토) h2 (빈칸)
    hx0 = x + sum(COL_PIX[:7])  # H is index7
    hx1 = x + sum(COL_PIX[:8])
    draw.rectangle([hx0, gy1_top, hx1, gy1_mid], fill=LABEL_FILL, outline=GRID_COLOR, width=1)
    _draw_text_center(draw, (hx0, gy1_top, hx1, gy1_mid), "검토", BOLD_FONT)
    draw.rectangle([hx0, gy1_mid, hx1, gy1_bottom], outline=GRID_COLOR, width=1)
    #5) i1 (승인) i2 (빈칸)
    ix0 = x + sum(COL_PIX[:8])  # I is index8
    ix1 = x + sum(COL_PIX[:9])
    draw.rectangle([ix0, gy1_top, ix1, gy1_mid], fill=LABEL_FILL, outline=GRID_COLOR, width=1)
    _draw_text_center(draw, (ix0, gy1_top, ix1, gy1_mid), "승인", BOLD_FONT)
    draw.rectangle([ix0, gy1_mid, ix1, gy1_bottom], outline=GRID_COLOR, width=1)
    y += TITLE_H

    def ensure_page_space(min_height: int):
        nonlocal img, draw, y
        if y + min_height > PAGE_H - MARGIN_B:
            pages.append(img)
            img, draw = new_page()
            y = MARGIN_T
    # Row3
    ensure_page_space(INFO_ROW_H)
    # A3: 제품명 label, B3:D3: product name
    a3x0 = x + sum(COL_PIX[:0]); a3x1 = x + sum(COL_PIX[:1])
    draw.rectangle([a3x0, y, a3x1, y + INFO_ROW_H], fill=LABEL_FILL, outline=GRID_COLOR, width=1)
    _draw_text_center(draw, (a3x0, y, a3x1, y + INFO_ROW_H), '제품명', BOLD_FONT)
    b3x0 = x + sum(COL_PIX[:1]); b3x1 = x + sum(COL_PIX[:4])  # B-D (1-3)
    draw.rectangle([b3x0, y, b3x1, y + INFO_ROW_H], outline=GRID_COLOR, width=1)
    prod_name = str(details.get('제품명','') or '')
    _draw_text_left_vcenter(draw, (b3x0, y, b3x1, y + INFO_ROW_H), prod_name, NORMAL_FONT)
    #6. e3 (생산코드) f3:g3 (생산실제코드)
    e3x0 = x + sum(COL_PIX[:4]); e3x1 = x + sum(COL_PIX[:5])
    draw.rectangle([e3x0, y, e3x1, y + INFO_ROW_H], fill=LABEL_FILL, outline=GRID_COLOR, width=1)
    _draw_text_center(draw, (e3x0, y, e3x1, y + INFO_ROW_H), '생산코드', BOLD_FONT)
    f3x0 = x + sum(COL_PIX[:5]); f3x1 = x + sum(COL_PIX[:7])  # F-G (5-6)
    draw.rectangle([f3x0, y, f3x1, y + INFO_ROW_H], outline=GRID_COLOR, width=1)
    _draw_text_left_vcenter(draw, (f3x0, y, f3x1, y + INFO_ROW_H), str(details.get('생산코드','') or ''), NORMAL_FONT)
    #7. h3 (제조자) i3 (빈칸)
    h3x0 = x + sum(COL_PIX[:7]); h3x1 = x + sum(COL_PIX[:8])
    draw.rectangle([h3x0, y, h3x1, y + INFO_ROW_H], fill=LABEL_FILL, outline=GRID_COLOR, width=1)
    _draw_text_center(draw, (h3x0, y, h3x1, y + INFO_ROW_H), '제조자', BOLD_FONT)
    i3x0 = x + sum(COL_PIX[:8]); i3x1 = x + sum(COL_PIX[:9])
    draw.rectangle([i3x0, y, i3x1, y + INFO_ROW_H], outline=GRID_COLOR, width=1)
    y += INFO_ROW_H

    # Row4
    ensure_page_space(INFO_ROW_H)
    a4x0 = x + sum(COL_PIX[:0]); a4x1 = x + sum(COL_PIX[:1])
    draw.rectangle([a4x0, y, a4x1, y + INFO_ROW_H], fill=LABEL_FILL, outline=GRID_COLOR, width=1)
    _draw_text_center(draw, (a4x0, y, a4x1, y + INFO_ROW_H), '지시일', BOLD_FONT)
    b4x0 = x + sum(COL_PIX[:1]); b4x1 = x + sum(COL_PIX[:2])
    draw.rectangle([b4x0, y, b4x1, y + INFO_ROW_H], outline=GRID_COLOR, width=1)
    instruction_date_raw = details.get('지시일', details.get('출력일시',''))
    if instruction_date_raw and ' ' in str(instruction_date_raw):
        instruction_date = str(instruction_date_raw).split(' ')[0] 
    else:
        instruction_date = instruction_date_raw
    _draw_text_left_vcenter(draw, (b4x0, y, b4x1, y + INFO_ROW_H), str(instruction_date or ''), NORMAL_FONT)
    c4x0 = x + sum(COL_PIX[:2]); c4x1 = x + sum(COL_PIX[:3])
    draw.rectangle([c4x0, y, c4x1, y + INFO_ROW_H], fill=LABEL_FILL, outline=GRID_COLOR, width=1)
    _draw_text_center(draw, (c4x0, y, c4x1, y + INFO_ROW_H), '제조일', BOLD_FONT)
    d4x0 = x + sum(COL_PIX[:3]); d4x1 = x + sum(COL_PIX[:4])
    draw.rectangle([d4x0, y, d4x1, y + INFO_ROW_H], outline=GRID_COLOR, width=1)
    _draw_text_left_vcenter(draw, (d4x0, y, d4x1, y + INFO_ROW_H), str(details.get('제조일','') or ''), NORMAL_FONT)
    e4x0 = x + sum(COL_PIX[:4]); e4x1 = x + sum(COL_PIX[:5])
    draw.rectangle([e4x0, y, e4x1, y + INFO_ROW_H], fill=LABEL_FILL, outline=GRID_COLOR, width=1)
    _draw_text_center(draw, (e4x0, y, e4x1, y + INFO_ROW_H), '생산량(kg)', BOLD_FONT)
    f4x0 = x + sum(COL_PIX[:5]); f4x1 = x + sum(COL_PIX[:7])  # F-G merged
    draw.rectangle([f4x0, y, f4x1, y + INFO_ROW_H], outline=GRID_COLOR, width=1)
    _draw_text_left_vcenter(draw, (f4x0, y, f4x1, y + INFO_ROW_H), str(details.get('생산량(kg)','') or ''), NORMAL_FONT)
    #8. h4 (수득량) i4 (빈칸)
    h4x0 = x + sum(COL_PIX[:7]); h4x1 = x + sum(COL_PIX[:8])
    draw.rectangle([h4x0, y, h4x1, y + INFO_ROW_H], fill=LABEL_FILL, outline=GRID_COLOR, width=1)
    _draw_text_center(draw, (h4x0, y, h4x1, y + INFO_ROW_H), '수득량', BOLD_FONT)
    i4x0 = x + sum(COL_PIX[:8]); i4x1 = x + sum(COL_PIX[:9])
    draw.rectangle([i4x0, y, i4x1, y + INFO_ROW_H], outline=GRID_COLOR, width=1)
    y += INFO_ROW_H

    # Spacer
    ensure_page_space(8)
    y += 8

    # 4) Table header (A..H)
    ensure_page_space(HEADER_H)
    cx = x
    for c_idx, head in enumerate(["Ph", "구분", "코드", "원료명", "함량(%)", "생산량(kg)", "계량량(kg)", "제조공정", "공정검사"]):
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
    # build groups: empty phase rows belong to the last non-empty phase until next appears
    groups: List[Tuple[str, int, int]] = []
    if items:
        def eff_phase(i: int, last_non_empty: Optional[str]) -> Tuple[str, Optional[str]]:
            raw = norm_phase(items[i].get('Ph') or items[i].get('Ph.', ''))
            if raw:
                return raw, raw
            return (last_non_empty or ''), last_non_empty

        start_idx = 0
        last_non_empty: Optional[str] = None
        cur, last_non_empty = eff_phase(0, last_non_empty)
        for idx in range(1, len(items)):
            ph, last_non_empty = eff_phase(idx, last_non_empty)
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
        # group-level wrap for 제조공정(G) and 공정검사(H)
        g_text = max(group_proc_texts, key=len) if group_proc_texts else ''
        h_text = max(group_insp_texts, key=len) if group_insp_texts else ''
        # compute available widths in pixels
        g_x0 = x + sum(COL_PIX[:6]); g_x1 = x + sum(COL_PIX[:7])
        h_x0 = x + sum(COL_PIX[:7]); h_x1 = x + sum(COL_PIX[:8])
        g_wrap = _wrap_text_by_width(draw, g_text, NORMAL_FONT, max(10, g_x1 - g_x0 - 12))
        h_wrap = _wrap_text_by_width(draw, h_text, NORMAL_FONT, max(10, h_x1 - h_x0 - 12))
        # ensure group height can fit wrapped text
        need_lines = max(_calc_lines(g_wrap), _calc_lines(h_wrap))
        pre_h = sum(row_heights) if row_heights else 0
        need_h = max(pre_h, max(ROW_H_BASE, LINE_H * need_lines + 6))
        if need_h > pre_h and row_heights:
            row_heights[-1] += (need_h - pre_h)
        # if not enough space, start new page before the group
        group_total_h = sum(row_heights)
        ensure_page_space(group_total_h)
        group_y_start = y

        # draw rows for columns B..G (F=생산량, G=계량량)
        for rel, hgt in enumerate(row_heights):
            ensure_page_space(hgt)
            it = items[s_idx + rel]
            cx = x
            values = [
                None,  # A merged later
                it.get('구분'), it.get('코드'), it.get('원료명'),
                it.get('함량(%)'), it.get('생산량(kg)'), it.get('계량량(kg)')
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
                    _draw_text_left_vcenter(draw, box, str(val or ''), NORMAL_FONT)
                elif c_idx in (4,5,6):
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
            # skip H/I per-row; merged later
            y += hgt

        # merged cells for A, H, I across group
        group_y_end = y
        # A column (Ph): always merge across group until next phase; text may be empty
        a_x0 = x; a_x1 = x + COL_PIX[0]
        draw.rectangle([a_x0, group_y_start, a_x1, group_y_end], outline=GRID_COLOR, width=1)
        _draw_text_center(draw, (a_x0, group_y_start, a_x1, group_y_end), ph or '', BOLD_FONT)
        # H column merged (wrap to width) - 제조공정
        g_x0 = x + sum(COL_PIX[:7]); g_x1 = x + sum(COL_PIX[:8])
        draw.rectangle([g_x0, group_y_start, g_x1, group_y_end], outline=GRID_COLOR, width=1)
        _draw_text_left_vcenter(draw, (g_x0, group_y_start, g_x1, group_y_end), g_wrap, NORMAL_FONT)
        # I column merged (wrap to width) - 공정검사
        h_x0 = x + sum(COL_PIX[:8]); h_x1 = x + sum(COL_PIX[:9])
        draw.rectangle([h_x0, group_y_start, h_x1, group_y_end], outline=GRID_COLOR, width=1)
        _draw_text_left_vcenter(draw, (h_x0, group_y_start, h_x1, group_y_end), h_wrap, NORMAL_FONT)

    # 6) Sum row (A:D merged visually)
    sum_h = HEADER_H
    ensure_page_space(sum_h)
    # Draw merged A:D block
    ad_w = sum(COL_PIX[:4])
    ad_box = (x, y, x + ad_w, y + sum_h)
    draw.rectangle(ad_box, fill=HEADER_FILL, outline=GRID_COLOR, width=1)
    _draw_text_center(draw, ad_box, "합계 (Total)", HEADER_FONT, fill=HEADER_TEXT)
    # Draw remaining E..I cells normally
    cx = x + ad_w
    for c_idx in range(4, 9):
        cw = COL_PIX[c_idx]
        box = (cx, y, cx + cw, y + sum_h)
        draw.rectangle(box, fill=HEADER_FILL, outline=GRID_COLOR, width=1)
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
        self.withdraw()  # 초기 렌더링 랙 방지를 위해 즉시 숨김
        self.title("인쇄 미리보기 (A4)")
        self.geometry("980x720")  # 메인 창보다 작음
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

        # 창 중앙 배치 및 deiconify
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
        self.deiconify()  # 정렬 완료 후 화면 노출

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

# modules/excel_handler.py
import openpyxl
from openpyxl import Workbook
from tkinter import filedialog, messagebox
from openpyxl.styles import Border, Side, Alignment, Font, PatternFill
from openpyxl.drawing.image import Image as XLImage
import configparser
from datetime import datetime
import os
from PIL import Image, ImageDraw, ImageFont
import tempfile

# --- 경로 설정을 읽기 위한 설정 ---
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CONFIG_FILE_PATH = os.path.join(PROJECT_ROOT, 'config.ini')

def _get_display_length(text):
    """Calculate display length of a string, considering East Asian characters."""
    if not text:
        return 0
    text = str(text)
    length = 0
    # East Asian characters (Hangul, Japanese, Chinese) are wider.
    for char in text:
        if '\uac00' <= char <= '\uD7A3' or \
           '\u3040' <= char <= '\u309F' or \
           '\u30a0' <= char <= '\u30FF' or \
           '\u4E00' <= char <= '\u9FFF':
            length += 2
        else:
            length += 1
    return length

def get_excel_path():
    """config.ini에서 엑셀 기본 경로를 읽어옵니다."""
    config = configparser.ConfigParser()
    config.read(CONFIG_FILE_PATH, encoding='utf-8')
    # 경로가 비어있으면 사용자 문서 폴더를 기본값으로 사용
    path = config.get('Paths', 'excel_dir', fallback='').strip()
    if not path or not os.path.isdir(path):
        return os.path.join(os.path.expanduser('~'), 'Documents')
    return path

def save_excel_path(path):
    """선택된 경로를 config.ini에 저장합니다."""
    config = configparser.ConfigParser()
    config.read(CONFIG_FILE_PATH, encoding='utf-8')
    if not config.has_section('Paths'):
        config.add_section('Paths')
    config.set('Paths', 'excel_dir', path)
    with open(CONFIG_FILE_PATH, 'w', encoding='utf-8') as configfile:
        config.write(configfile)

def get_timestamped_filename(default_filename):
    """파일 이름에 타임스탬프를 추가합니다 (확장자 앞)."""
    now = datetime.now().strftime("%Y%m%d_%H%M%S")
    name, ext = os.path.splitext(default_filename)
    return f"{name}_{now}{ext}"

def export_template(headers, default_filename="template.xlsx"):
    """단일 시트를 가진 엑셀 템플릿을 내보냅니다."""
    initial_dir = get_excel_path()
    timestamped_filename = get_timestamped_filename(default_filename)
    file_path = filedialog.asksaveasfilename(
        defaultextension=".xlsx",
        filetypes=[("Excel files", "*.xlsx")],
        initialdir=initial_dir,
        initialfile=timestamped_filename,
        title="엑셀 폼 저장"
    )
    if not file_path:
        return

    save_excel_path(os.path.dirname(file_path))

    try:
        workbook = Workbook()
        sheet = workbook.active
        sheet.append(headers)
        workbook.save(file_path)
        messagebox.showinfo("성공", f"엑셀 폼이 '{file_path}'에 저장되었습니다.")
    except Exception as e:
        messagebox.showerror("오류", f"파일 저장 중 오류가 발생했습니다: {e}")

def import_data():
    initial_dir = get_excel_path()
    file_path = filedialog.askopenfilename(
        filetypes=[("Excel files", "*.xlsx")],
        initialdir=initial_dir,
        title="가져올 엑셀 파일 선택"
    )
    if not file_path:
        return None

    save_excel_path(os.path.dirname(file_path))

    def clean_cell(cell):
        """
        셀 값 정리:
        - None 또는 '-' → 빈 문자열
        - 문자열이면 앞뒤 공백 제거
        """
        if cell is None:
            return ""
        if isinstance(cell, str):
            cell = cell.strip()
            if cell == "-":
                return ""
        return cell

    try:
        workbook = openpyxl.load_workbook(file_path, data_only=True)
        sheet = workbook.active
        headers = [cell.value for cell in sheet[1]]
        data_list = []
        for row in sheet.iter_rows(min_row=2, values_only=True):
            # 전부 비어있으면 건너뜀
            if all(cell is None or str(cell).strip() in ("", "-") for cell in row):
                continue
            # 헤더 개수에 맞춰 길이 조정
            row = list(row) + [None] * (len(headers) - len(row))
            # 각 셀 값 정리
            row = [clean_cell(cell) for cell in row]
            row_data = dict(zip(headers, row))
            data_list.append(row_data)
        return data_list
    except Exception as e:
        messagebox.showerror("오류", f"파일을 읽는 중 오류가 발생했습니다: {e}")
        return None

def export_multisheet_template(sheets_with_headers, default_filename="template.xlsx"):
    """여러 시트를 가진 엑셀 템플릿을 내보냅니다."""
    initial_dir = get_excel_path()
    timestamped_filename = get_timestamped_filename(default_filename)
    file_path = filedialog.asksaveasfilename(
        defaultextension=".xlsx",
        filetypes=[("Excel files", "*.xlsx")],
        initialdir=initial_dir,
        initialfile=timestamped_filename,
        title="엑셀 폼 저장"
    )
    if not file_path:
        return

    save_excel_path(os.path.dirname(file_path))

    try:
        workbook = Workbook()
        workbook.remove(workbook.active)
        # NOTE: revised exporter is defined at module level; this function handles only multi-sheet template export.
    except Exception as e:
        messagebox.showerror("내보내기 오류", f"파일 저장 중 오류가 발생했습니다: {e}")

def export_production_formulation_revised_to_excel(
    production_data,
    default_filename: str = "production_revised.xlsx",
    file_path: str | None = None,
    open_print_preview: bool = False,
):
    """수정본 템플릿(생산처방ui.py의 병합/모양 준용)으로 단일 시트 내보내기.
    - 상단 레이아웃을 생산처방ui.py처럼 구성:
        • 제목: A1:F2 병합, 중앙 정렬("생산지시서")
        • 결재란 자리: G1:H2 병합(텍스트 라벨만), 기존 색상/테두리는 유지
        • 기본정보: 3행/4행에 제품명과 핵심 정보 배치 (병합 위치는 ui.py 참고)
    - 본문 표: A..H = [Ph, 구분, 코드, 원료명, 함량(%), 생산량(kg), 제조공정, 공정검사]
        • 같은 Ph 구간은 A열을 세로 병합
        • 제조공정/공정검사도 Ph 구간 단위로 각각 세로 병합
        • 각 구간의 텍스트는 해당 구간 아이템들 중 가장 긴 내용으로 채움
    - 색상/테두리/폰트 등 스타일은 기존(원래) 정의를 그대로 사용
    - 인쇄 설정은 기존 수정본과 동일(세로, 여백 축소, 머리글/바닥글 등)
    """

    # 파일 경로 결정
    if file_path is None:
        if open_print_preview:
            tmp = tempfile.NamedTemporaryFile(delete=False, suffix=".xlsx")
            file_path = tmp.name
            tmp.close()
        else:
            initial_dir = get_excel_path()
            timestamped_filename = get_timestamped_filename(default_filename)
            chosen = filedialog.asksaveasfilename(
                defaultextension=".xlsx",
                filetypes=[["Excel files", "*.xlsx"]],
                initialdir=initial_dir,
                initialfile=timestamped_filename,
                title="생산처방(수정본) 저장"
            )
            if not chosen:
                return
            file_path = chosen
            save_excel_path(os.path.dirname(file_path))

    # 스타일
    thin = Side(style='thin', color='2C3E50')
    medium = Side(style='medium', color='2C3E50')
    thin_border = Border(left=thin, right=thin, top=thin, bottom=thin)
    medium_border = Border(left=medium, right=medium, top=medium, bottom=medium)
    title_font = Font(name='맑은 고딕', size=20, bold=True, color='1F4E78')
    header_font = Font(name='맑은 고딕', size=11, bold=True, color='2C3E50')
    header_font_white = Font(name='맑은 고딕', size=11, bold=True, color='FFFFFF')
    label_font = Font(name='맑은 고딕', size=10, bold=True, color='34495E')
    default_font = Font(name='맑은 고딕', size=10, color='2C3E50')
    center = Alignment(horizontal='center', vertical='center', wrap_text=True)
    left = Alignment(horizontal='left', vertical='center', wrap_text=True)
    left_top = Alignment(horizontal='left', vertical='top', wrap_text=True)
    right = Alignment(horizontal='right', vertical='center', wrap_text=True)
    header_fill = PatternFill(start_color="E8F4F8", end_color="E8F4F8", fill_type="solid")
    table_header_fill = PatternFill(start_color="5B9BD5", end_color="5B9BD5", fill_type="solid")
    label_fill = PatternFill(start_color="D5E8F0", end_color="D5E8F0", fill_type="solid")

    try:
        wb = Workbook()
        ws = wb.active
        ws.title = "생산처방"

        # 1) 제목: A1:F2 병합 (ui.py 준용)
        ws.merge_cells('A1:F2')
        tcell = ws['A1']
        tcell.value = "생산지시서"
        tcell.font = title_font
        tcell.alignment = center
        ws.row_dimensions[1].height = 30
        ws.row_dimensions[2].height = 22

        # 2) 결재란: G1:H2 영역에 승인 스탬프 이미지를 삽입(오른쪽 정렬 폭에 맞춤)
        #    - 왼쪽에 '결' '재' 세로 라벨, 상단에 '작성/검토/승인', 하단 서명칸
        from openpyxl.drawing.image import Image as XLImage  # type: ignore
        def create_approval_image_v2(canvas_width: int) -> str:
            base_h = 140  # 기본 높이(여유 확보, 잘림 방지)
            img = Image.new('RGB', (canvas_width, base_h), 'white')
            drw = ImageDraw.Draw(img)
            col_left_w = max(28, int(canvas_width * 0.12))
            rest_w = canvas_width - col_left_w
            col_w = rest_w // 3
            header_h = int(base_h * 0.45)
            # 바깥 테두리
            drw.rectangle([0, 0, canvas_width-1, base_h-1], outline='#2C3E50', width=2)
            # 세로 구분선 (왼쪽 라벨/3분할)
            drw.line([col_left_w, 0, col_left_w, base_h], fill='#2C3E50', width=1)
            drw.line([col_left_w + col_w, 0, col_left_w + col_w, base_h], fill='#2C3E50', width=1)
            drw.line([col_left_w + col_w*2, 0, col_left_w + col_w*2, base_h], fill='#2C3E50', width=1)
            # 가로 구분선(헤더/서명칸): 왼쪽 라벨 칸은 위 칸과 병합되도록 선을 비켜감
            drw.line([col_left_w, header_h, canvas_width, header_h], fill='#2C3E50', width=1)
            # 헤더 배경 제거(흰색 유지)
            try:
                f_bold = ImageFont.truetype("malgunbd.ttf", 16)
            except Exception:
                f_bold = ImageFont.load_default()
            # 왼쪽 세로 '결' '재' 배치
            # - '결'은 헤더 영역과 바로 아래 칸을 병합한 상단 블록 중앙
            # - '재'는 하단 블록 중앙 (상단/하단을 내부 구분선으로 나눔)
            w_g, h_g = drw.textbbox((0,0), '결', font=f_bold)[2:4]
            w_j, h_j = drw.textbbox((0,0), '재', font=f_bold)[2:4]
            # 내부 구분선 없이, 전체 높이를 반으로 나누어 각 절반의 가운데에 배치
            y_k = int(base_h * 0.25) - h_g//2
            y_j = int(base_h * 0.75) - h_j//2
            drw.text((max(2, (col_left_w - w_g)//2), max(2, y_k)), '결', fill='#2C3E50', font=f_bold)
            drw.text((max(2, (col_left_w - w_j)//2), max(2, y_j)), '재', fill='#2C3E50', font=f_bold)
            # 헤더 텍스트
            heads = ['작성','검토','승인']
            for i, txt in enumerate(heads):
                x0 = col_left_w + i*col_w
                x1 = x0 + col_w
                tw, th = drw.textbbox((0,0), txt, font=f_bold)[2:4]
                drw.text((x0 + (col_w - tw)//2, (header_h - th)//2), txt, fill='#2C3E50', font=f_bold)
            tf = tempfile.NamedTemporaryFile(delete=False, suffix='.png')
            img.save(tf.name, 'PNG'); tf.close()
            return tf.name

        # G/H 폭을 기준으로 이미지 너비 산정 (엑셀 폭 단위를 픽셀로 근사: *7)
        gh_px = int((26 + 22) * 7)  # G=26, H=22 (fixed widths). 여백 없이 정확히 맞춤
        ap_img_path = create_approval_image_v2(gh_px)
        ap_img = XLImage(ap_img_path)
        ap_img.anchor = 'G1'
        ws.add_image(ap_img)
        # 행 높이 보정(이미지를 수용)
        ws.row_dimensions[1].height = 90
        ws.row_dimensions[2].height = 0

        # 3) 기본정보 (ui.py 배치 준용)
        details = production_data.get('details', {})
        # Row 3: 제품명(A3 라벨, B3:D3 값 병합), 생산코드(E3:F3), 제조자(G3:H3)
        prod_name = details.get('제품명', '')
        # A3 라벨
        ws['A3'].value = '제품명'; ws['A3'].font = label_font; ws['A3'].fill = label_fill; ws['A3'].alignment = center; ws['A3'].border = thin_border
        # B3:D3 병합 값
        ws.merge_cells('B3:D3')
        ws['B3'].value = prod_name
        ws['B3'].font = default_font
        ws['B3'].alignment = left
        # 개별 셀 테두리 유지
        ws['B3'].border = thin_border
        ws['C3'].border = thin_border
        ws['D3'].border = thin_border
        ws['E3'].value = '생산코드'; ws['E3'].font = label_font; ws['E3'].fill = label_fill; ws['E3'].alignment = center; ws['E3'].border = thin_border
        ws['F3'].value = details.get('생산코드', ''); ws['F3'].font = default_font; ws['F3'].alignment = left; ws['F3'].border = thin_border
        ws['G3'].value = '제조자'; ws['G3'].font = label_font; ws['G3'].fill = label_fill; ws['G3'].alignment = center; ws['G3'].border = thin_border
        ws['H3'].value = details.get('제조자', ''); ws['H3'].font = default_font; ws['H3'].alignment = left; ws['H3'].border = thin_border
        # 라벨/값 셀 테두리 보강
        for c in ['A','B','C','D']:
            ws[f"{c}3"].border = thin_border
        ws.row_dimensions[3].height = 24

        # Row 4: 지시일/적용일/생산량/수득량
        ws['A4'].value = '지시일'; ws['A4'].font = label_font; ws['A4'].fill = label_fill; ws['A4'].alignment = center; ws['A4'].border = thin_border
        ws['B4'].value = details.get('지시일', details.get('출력일시','')); ws['B4'].font = default_font; ws['B4'].alignment = left; ws['B4'].border = thin_border
        ws['C4'].value = '적용일'; ws['C4'].font = label_font; ws['C4'].fill = label_fill; ws['C4'].alignment = center; ws['C4'].border = thin_border
        ws['D4'].value = details.get('적용일',''); ws['D4'].font = default_font; ws['D4'].alignment = left; ws['D4'].border = thin_border
        ws['E4'].value = '생산량(kg)'; ws['E4'].font = label_font; ws['E4'].fill = label_fill; ws['E4'].alignment = center; ws['E4'].border = thin_border
        ws['F4'].value = details.get('생산량(kg)',''); ws['F4'].font = default_font; ws['F4'].alignment = right; ws['F4'].border = thin_border
        ws['G4'].value = '수득량'; ws['G4'].font = label_font; ws['G4'].fill = label_fill; ws['G4'].alignment = center; ws['G4'].border = thin_border
        ws['H4'].value = details.get('수득량',''); ws['H4'].font = default_font; ws['H4'].alignment = right; ws['H4'].border = thin_border
        ws.row_dimensions[4].height = 24

        # Row 5: 빈 줄(여백)
        ws.row_dimensions[5].height = 6

        # 4) 테이블 헤더 (UI 기준 A..H)
        headers = ["Ph", "구분", "코드", "원료명", "함량(%)", "생산량(kg)", "제조공정", "공정검사"]
        header_row = 6
        ws.row_dimensions[header_row].height = 28
        for c_idx, h in enumerate(headers, 1):
            hc = ws.cell(row=header_row, column=c_idx, value=h)
            hc.font = header_font_white
            hc.fill = table_header_fill
            hc.alignment = center
            hc.border = medium_border

        # 5) 데이터 행 (Ph 구간 병합: A/G/H)
        current = header_row + 1
        total_ratio = 0.0
        items = production_data.get('items', [])

        def norm_phase(v):
            s = str(v).strip() if v is not None else ''
            return s.replace('Ph.', '').replace('PH', '').strip() if s else ''

        # 연속 구간으로 그룹화
        groups = []  # list of (phase, start_idx, end_idx) on items index (0-based)
        if items:
            start = 0
            cur_ph = norm_phase(items[0].get('Ph', items[0].get('Ph.', '')))
            for idx in range(1, len(items)):
                ph = norm_phase(items[idx].get('Ph', items[idx].get('Ph.', '')))
                if ph != cur_ph:
                    groups.append((cur_ph, start, idx-1))
                    start = idx; cur_ph = ph
            groups.append((cur_ph, start, len(items)-1))

        for ph, s_idx, e_idx in groups:
            group_len = e_idx - s_idx + 1
            # 그룹 내 최대 줄 수(공정/검사 텍스트)로 행 높이 가늠
            proc_texts = []
            insp_texts = []
            for i in range(s_idx, e_idx+1):
                proc_texts.append(str(items[i].get('제조공정', '') or '').replace('"','').replace("'", ''))
                insp_texts.append(str(items[i].get('공정검사', '') or '').replace('"','').replace("'", ''))
            group_proc = max(proc_texts, key=len) if proc_texts else ''
            group_insp = max(insp_texts, key=len) if insp_texts else ''
            max_lines = max(group_proc.count('\n')+1 if group_proc else 1, group_insp.count('\n')+1 if group_insp else 1)
            per_row_height = max(24, int(18 * max_lines / group_len) + 2)

            # 각 아이템 행 작성
            for i in range(s_idx, e_idx+1):
                item = items[i]
                # 생산량(kg) 보정
                qty_kg = item.get('생산량(kg)')
                if qty_kg in (None, ""):
                    try:
                        g = float(item.get('기준중량(g)'))
                        qty_kg = g / 1000.0
                    except Exception:
                        qty_kg = item.get('생산량(kg)')

                vals = [
                    norm_phase(item.get('Ph', item.get('Ph.', ''))),
                    item.get('구분'), item.get('코드'), item.get('원료명'),
                    item.get('함량(%)'), qty_kg,
                    '', ''  # 병합 예정(G,H)
                ]

                ws.row_dimensions[current].height = per_row_height
                for c_idx, val in enumerate(vals, 1):
                    cell = ws.cell(row=current, column=c_idx, value=val)
                    cell.border = thin_border
                    cell.font = default_font
                    if c_idx in (1,2,3):
                        cell.alignment = center
                    elif c_idx == 4:
                        cell.alignment = left
                    elif c_idx in (5,6):
                        try:
                            fval = float(val)
                            cell.value = fval
                            if c_idx == 5:
                                cell.number_format = '0.0000'
                                total_ratio += fval
                            else:
                                cell.number_format = '#,##0.0'
                        except Exception:
                            pass
                        cell.alignment = right
                    else:
                        cell.alignment = left_top
                current += 1

            # A열, G열, H열을 그룹 단위로 병합 후 값/정렬 적용
            start_row = header_row + 1 + s_idx if groups and groups[0][1] == 0 else (current - group_len)
            # start_row 계산 보정: current는 그룹 끝 다음 행이므로...
            start_row = current - group_len
            end_row = current - 1
            if group_len >= 1:
                # A열 병합 및 표시
                if start_row < end_row:
                    ws.merge_cells(start_row=start_row, start_column=1, end_row=end_row, end_column=1)
                a_cell = ws.cell(row=start_row, column=1, value=(ph or ''))
                a_cell.alignment = center; a_cell.border = thin_border; a_cell.font = header_font

                # G열 병합 및 텍스트
                if start_row < end_row:
                    ws.merge_cells(start_row=start_row, start_column=7, end_row=end_row, end_column=7)
                g_cell = ws.cell(row=start_row, column=7, value=group_proc)
                g_cell.alignment = left_top; g_cell.border = thin_border; g_cell.font = default_font

                # H열 병합 및 텍스트
                if start_row < end_row:
                    ws.merge_cells(start_row=start_row, start_column=8, end_row=end_row, end_column=8)
                h_cell = ws.cell(row=start_row, column=8, value=group_insp)
                h_cell.alignment = left_top; h_cell.border = thin_border; h_cell.font = default_font

        # 6) 합계 행 (병합 없이 표시)
        sum_row = current
        ws.row_dimensions[sum_row].height = 28
        for col in range(1, 9):
            c = ws.cell(row=sum_row, column=col)
            c.fill = table_header_fill
            c.border = medium_border
        ws.cell(row=sum_row, column=1, value="합계 (Total)").font = header_font_white
        sr = ws.cell(row=sum_row, column=5, value=total_ratio)
        sr.font = header_font_white
        sr.number_format = '0.0000'
        sr.alignment = right

        # 7) 필터/고정
        ws.auto_filter.ref = f"A{header_row}:H{sum_row}"
        ws.freeze_panes = f"A{header_row+1}"

        # 8) 컬럼 폭 고정
        fixed_widths = {
            'A': 8, 'B': 10, 'C': 15, 'D': 45, 'E': 12, 'F': 12, 'G': 26, 'H': 22
        }
        for col, w in fixed_widths.items():
            ws.column_dimensions[col].width = w

        # 9) 인쇄 설정 (세로 + 여백 축소) + 머리글/바닥글 + 타이틀 행 반복/인쇄 영역
        try:
            ws.page_setup.orientation = ws.ORIENTATION_PORTRAIT
            ws.page_setup.fitToWidth = 1
            ws.page_setup.fitToHeight = 0
            ws.sheet_properties.pageSetUpPr.fitToPage = True
            ws.print_options.horizontalCentered = True
            ws.page_margins.left = 0.3; ws.page_margins.right = 0.3
            ws.page_margins.top = 0.4; ws.page_margins.bottom = 0.4
            # 머리글/바닥글: 날짜/시간, 문서명, 페이지 번호
            try:
                ws.header_footer.left_header = "&D &T"
                title_text = f"생산지시서 - {details.get('제품명','')}"
                ws.header_footer.center_header = title_text
                ws.header_footer.right_footer = "Page &[Page] / &[Pages]"
            except Exception:
                pass
            # 각 페이지에 표 헤더 반복
            try:
                ws.print_title_rows = f"1:{header_row}"
            except Exception:
                pass
            # 인쇄 영역 지정
            try:
                ws.print_area = f"A1:H{sum_row}"
            except Exception:
                pass
        except Exception:
            pass

        wb.save(file_path)

        # 미리보기/출력 처리
        if open_print_preview:
            try:
                import win32com.client as win32  # type: ignore
                excel = win32.Dispatch("Excel.Application")
                excel.Visible = True
                wb_com = excel.Workbooks.Open(os.path.abspath(file_path))
                try:
                    wb_com.ActiveSheet.PrintPreview()
                finally:
                    wb_com.Close(SaveChanges=False)
                    excel.Quit()
            except Exception:
                try:
                    os.startfile(os.path.abspath(file_path))
                except Exception:
                    try:
                        os.startfile(os.path.abspath(file_path), "print")
                    except Exception:
                        pass
        else:
            messagebox.showinfo("성공", f"생산지시서가 '{file_path}'에 저장되었습니다.")
    except Exception as e:
        messagebox.showerror("내보내기 오류", f"파일 저장 중 오류가 발생했습니다: {e}")


def export_production_formulation_original_to_excel(
    production_data,
    default_filename: str = "production.xlsx",
    file_path: str | None = None,
    open_print_preview: bool = False,
):
    """원래 템플릿으로 생산처방을 내보냅니다.
    - 제목: A1:F2 병합, "생산처방서\nProduction Formulation Sheet"
    - 결재란: G-H 영역 이미지(우측 정렬, 약 1/3 확대), H열 우측 끝 정렬
    - 기본정보: 좌측 B–E 병합, 우측 G/H 라벨/값(병합 없음)
    - 비고: 2–8 병합
    - 본문: "계량량(kg)" 포함, Phase/H/I 병합, 지브라 스트라이프, 합계 행
    - 컬럼폭: H=26.25, I=17.25, D는 30~50, 기타 최대 20
    - 인쇄: 가로 모드, fitToWidth=1, 여백 0.3/0.5
    - 추가 시트: 제조공정, 원료 환산
    """

    # 파일 경로 결정
    if file_path is None:
        if open_print_preview:
            tmp = tempfile.NamedTemporaryFile(delete=False, suffix=".xlsx")
            file_path = tmp.name
            tmp.close()
        else:
            initial_dir = get_excel_path()
            timestamped_filename = get_timestamped_filename(default_filename)
            chosen = filedialog.asksaveasfilename(
                defaultextension=".xlsx",
                filetypes=[["Excel files", "*.xlsx"]],
                initialdir=initial_dir,
                initialfile=timestamped_filename,
                title="생산처방 저장"
            )
            if not chosen:
                return
            file_path = chosen
            save_excel_path(os.path.dirname(file_path))

    # 스타일 정의
    thin = Side(style='thin', color='2C3E50')
    medium = Side(style='medium', color='2C3E50')
    thin_border = Border(left=thin, right=thin, top=thin, bottom=thin)
    medium_border = Border(left=medium, right=medium, top=medium, bottom=medium)
    title_font = Font(name='맑은 고딕', size=20, bold=True, color='1F4E78')
    header_font = Font(name='맑은 고딕', size=11, bold=True, color='2C3E50')
    header_font_white = Font(name='맑은 고딕', size=11, bold=True, color='FFFFFF')
    label_font = Font(name='맑은 고딕', size=10, bold=True, color='34495E')
    default_font = Font(name='맑은 고딕', size=10, color='2C3E50')
    center = Alignment(horizontal='center', vertical='center', wrap_text=True)
    left = Alignment(horizontal='left', vertical='center', wrap_text=True)
    left_top = Alignment(horizontal='left', vertical='top', wrap_text=True)
    right = Alignment(horizontal='right', vertical='center')
    header_fill = PatternFill(start_color="E8F4F8", end_color="E8F4F8", fill_type="solid")
    label_fill = PatternFill(start_color="D5E8F0", end_color="D5E8F0", fill_type="solid")
    table_header_fill = PatternFill(start_color="5B9BD5", end_color="5B9BD5", fill_type="solid")

    # 결재란 이미지 생성 함수
    def create_approval_image(canvas_width=None, scale=4/3):
        base_w, base_h = 300, 117
        width = int(canvas_width) if canvas_width else int(base_w * scale)
        content_w = min(int(base_w * scale), width)
        height = int(content_w * (base_h / base_w))
        img = Image.new('RGB', (width, height), 'white')
        draw = ImageDraw.Draw(img)
        try:
            font_title = ImageFont.truetype("malgunbd.ttf", 15)
            font_small = ImageFont.truetype("malgun.ttf", 10)
        except Exception:
            font_title = ImageFont.load_default(); font_small = font_title
        margin_left = width - content_w
        box_w = content_w // 3
        header_h = int(height * 0.28)
        for i in range(3):
            x0 = margin_left + i * box_w
            draw.rectangle([x0, 0, x0 + box_w, header_h], fill='#E8F4F8', outline='black', width=2)
        draw.rectangle([margin_left, 0, margin_left + content_w - 1, height - 1], outline='#2C3E50', width=3)
        draw.line([margin_left + box_w, 0, margin_left + box_w, height], fill='#2C3E50', width=2)
        draw.line([margin_left + box_w*2, 0, margin_left + box_w*2, height], fill='#2C3E50', width=2)
        draw.line([margin_left, header_h, margin_left + content_w, header_h], fill='#2C3E50', width=2)
        for i, label in enumerate(["작성","검토","승인"]):
            x0 = margin_left + i * box_w
            xr = x0 + box_w - 10
            draw.text((xr, header_h//2), label, fill='#2C3E50', font=font_title, anchor='rm')
            sy = header_h + (height - header_h)//2 + 15
            draw.text((xr, sy), "(인)", fill='#95A5A6', font=font_small, anchor='rm')
        tf = tempfile.NamedTemporaryFile(delete=False, suffix='.png')
        img.save(tf.name, 'PNG'); tf.close()
        return tf.name

    try:
        wb = Workbook()
        ws = wb.active
        ws.title = "생산처방"

        # 제목 & 결재란
        ws.merge_cells('A1:F2')
        tc = ws['A1']
        tc.value = "생산처방서\nProduction Formulation Sheet"
        tc.font = title_font; tc.alignment = center
        tc.fill = PatternFill(start_color="FFFFFF", end_color="FFFFFF", fill_type="solid")
        try:
            g_w = ws.column_dimensions['G'].width or 26.25
            h_w = ws.column_dimensions['H'].width or 17.25
            gh_px = int((float(g_w) + float(h_w)) * 7 + 4)
        except Exception:
            gh_px = 300
        approval_img_path = create_approval_image(canvas_width=gh_px, scale=4/3)
        img = XLImage(approval_img_path)
        img.anchor = 'G1'
        ws.add_image(img)
        ws.row_dimensions[1].height = 70
        ws.row_dimensions[2].height = 0
        ws.row_dimensions[3].height = 10

        # 기본정보
        details = production_data.get('details', {})
        left_pairs = [("제품명", details.get("제품명","")), ("LAB NO.", details.get("LAB NO.","")), ("거래처", details.get("거래처","")), ("적용일", details.get("적용일","")), ("승인자", details.get("승인자",""))]
        right_pairs = [("생산코드", details.get("생산코드","")), ("차수", details.get("차수","")), ("생산량(kg)", details.get("생산량(kg)","")), ("상태", details.get("상태","")), ("출력일시", details.get("출력일시",""))]
        r = 4
        for i in range(max(len(left_pairs), len(right_pairs))):
            ws.row_dimensions[r].height = 28
            if i < len(left_pairs):
                label, value = left_pairs[i]
                lc = ws.cell(row=r, column=1, value=label)
                lc.font = label_font; lc.fill = label_fill; lc.alignment = center; lc.border = thin_border
                ws.merge_cells(start_row=r, start_column=2, end_row=r, end_column=5)
                vc = ws.cell(row=r, column=2, value=value)
                vc.font = default_font; vc.alignment = left; vc.border = thin_border
                for c in range(2,6): ws.cell(row=r, column=c).border = thin_border
            else:
                for c in range(1,6): ws.cell(row=r, column=c).border = thin_border
            if i < len(right_pairs):
                label, value = right_pairs[i]
                rc = ws.cell(row=r, column=7, value=label)
                rc.font = label_font; rc.fill = label_fill; rc.alignment = center; rc.border = thin_border
                rv = ws.cell(row=r, column=8, value=value)
                rv.font = default_font; rv.alignment = left; rv.border = thin_border
            else:
                for c in range(7,9): ws.cell(row=r, column=c).border = thin_border
            ws.cell(row=r, column=6).border = thin_border
            r += 1

        # 비고
        if details.get('비고'):
            ws.row_dimensions[r].height = 45
            nl = ws.cell(row=r, column=1, value="비고\nNote")
            nl.font = label_font; nl.fill = label_fill; nl.alignment = center; nl.border = thin_border
            ws.merge_cells(start_row=r, start_column=2, end_row=r, end_column=8)
            nv = ws.cell(row=r, column=2, value=details.get('비고'))
            nv.font = default_font; nv.alignment = left; nv.border = thin_border
            for c in range(2,9): ws.cell(row=r, column=c).border = thin_border
            r += 1

        ws.row_dimensions[r].height = 8; r += 1

        # 테이블 헤더
        headers = ["Ph.", "구분", "코드", "원료명", "함량(%)", "생산량(kg)", "계량량(kg)", "제조공정", "공정검사"]
        header_row = r
        ws.row_dimensions[header_row].height = 32
        for idx, h in enumerate(headers, 1):
            hc = ws.cell(row=header_row, column=idx, value=h)
            hc.font = header_font_white; hc.fill = table_header_fill; hc.alignment = center; hc.border = medium_border

        # 데이터
        current = header_row + 1
        total_ratio = 0.0
        phase_merge_info = []
        current_phase = None
        phase_start_row = None
        phase_max_lines = 1
        for item in production_data.get('items', []):
            ph_val = str(item.get('Ph.', '')).strip()
            proc_text = str(item.get('제조공정', '')).strip()
            insp_text = str(item.get('공정검사', '')).strip()
            proc_lines = proc_text.count('\n') + 1 if proc_text else 1
            insp_lines = insp_text.count('\n') + 1 if insp_text else 1
            max_lines_row = max(proc_lines, insp_lines)
            if ph_val:
                if current_phase is not None and phase_start_row is not None:
                    phase_merge_info.append((current_phase, phase_start_row, current - 1, phase_max_lines))
                current_phase = ph_val; phase_start_row = current; phase_max_lines = max_lines_row
            else:
                phase_max_lines = max(phase_max_lines, max_lines_row)

            qty_kg = item.get('생산량(kg)')
            if qty_kg in (None, ""):
                try:
                    g = float(item.get('기준중량(g)')); qty_kg = g/1000.0
                except Exception:
                    qty_kg = item.get('생산량(kg)')
            weigh_kg = item.get('계량량(kg)')  # 수기 기입 전제(자동 채움 없음)

            vals = [ph_val if ph_val else "", item.get('구분'), item.get('코드'), item.get('원료명'), item.get('함량(%)'), qty_kg, weigh_kg, item.get('제조공정'), item.get('공정검사')]
            row_fill = PatternFill(start_color="F8FBFD", end_color="F8FBFD", fill_type="solid") if (current - header_row) % 2 == 0 else None
            for c_idx, val in enumerate(vals, 1):
                cell = ws.cell(row=current, column=c_idx, value=val)
                cell.border = thin_border; cell.font = default_font
                if row_fill and c_idx not in [1,8,9]: cell.fill = row_fill
                if c_idx in (1,2,3):
                    cell.alignment = center
                elif c_idx == 4:
                    cell.alignment = left
                elif c_idx in (5,6,7):
                    try:
                        fval = float(val); cell.value = fval
                        if c_idx == 5:
                            cell.number_format = '0.0000'; total_ratio += fval
                        else:
                            cell.number_format = '#,##0.0'
                    except Exception:
                        pass
                    cell.alignment = right
                else:
                    if val:
                        cleaned = str(val).replace('"','').replace("'", '')
                        cell.value = cleaned
                    cell.alignment = left_top
            ws.row_dimensions[current].height = 26
            current += 1

        if current_phase is not None and phase_start_row is not None:
            phase_merge_info.append((current_phase, phase_start_row, current - 1, phase_max_lines))

        for phase_val, start_row, end_row, max_lines in phase_merge_info:
            num_rows = end_row - start_row + 1
            total_h = max(24, max_lines * 18 + 6)
            row_h = total_h / num_rows
            for rr in range(start_row, end_row + 1): ws.row_dimensions[rr].height = row_h
            if start_row < end_row:
                ws.merge_cells(start_row=start_row, start_column=1, end_row=end_row, end_column=1)
                mc = ws.cell(row=start_row, column=1); mc.value = phase_val; mc.alignment = center; mc.border = thin_border; mc.font = header_font
                ws.merge_cells(start_row=start_row, start_column=8, end_row=end_row, end_column=8)
                pc = ws.cell(row=start_row, column=8); pc.alignment = left_top; pc.border = thin_border
                ws.merge_cells(start_row=start_row, start_column=9, end_row=end_row, end_column=9)
                ic = ws.cell(row=start_row, column=9); ic.alignment = left_top; ic.border = thin_border
            else:
                ws.row_dimensions[start_row].height = total_h

        # 합계 행
        sum_row = current
        ws.row_dimensions[sum_row].height = 32
        ws.merge_cells(start_row=sum_row, start_column=1, end_row=sum_row, end_column=4)
        sl = ws.cell(row=sum_row, column=1, value="합계 (Total)")
        sl.font = header_font_white; sl.fill = table_header_fill; sl.alignment = center; sl.border = medium_border
        sr = ws.cell(row=sum_row, column=5, value=total_ratio)
        sr.font = header_font_white; sr.fill = table_header_fill; sr.number_format = '0.0000'; sr.alignment = right; sr.border = medium_border
        for col in [1,2,3,4]: ws.cell(row=sum_row, column=col).border = medium_border
        for col in [6,7,8]:
            ec = ws.cell(row=sum_row, column=col); ec.fill = table_header_fill; ec.border = medium_border

        # 필터/고정
        ws.auto_filter.ref = f"A{header_row}:I{sum_row}"
        ws.freeze_panes = f"A{header_row+1}"

        # 컬럼 너비
        for col_idx, col_letter in enumerate(['A','B','C','D','E','F','G','H','I'], 1):
            max_w = 10
            try:
                hc = ws.cell(row=header_row, column=col_idx)
                if hc.value: max_w = max(max_w, len(str(hc.value)) * 1.2)
            except Exception: pass
            for row_idx in range(header_row + 1, sum_row):
                try:
                    cv = ws.cell(row=row_idx, column=col_idx).value
                    if cv:
                        s = str(cv)
                        if '\n' in s:
                            cell_len = max(len(line) for line in s.split('\n')) * 1.1
                        else:
                            cell_len = len(s) * 1.1
                        max_w = max(max_w, cell_len)
                except Exception: pass
            if col_letter == 'H':
                max_w = 26.25
            elif col_letter == 'I':
                max_w = 17.25
            elif col_letter == 'D':
                max_w = min(max_w, 50); max_w = max(max_w, 30)
            else:
                max_w = min(max_w, 20)
            ws.column_dimensions[col_letter].width = max_w

        # 인쇄 설정
        try:
            ws.page_setup.orientation = ws.ORIENTATION_LANDSCAPE
            ws.page_setup.fitToWidth = 1
            ws.page_setup.fitToHeight = 0
            ws.sheet_properties.pageSetUpPr.fitToPage = True
            ws.print_options.horizontalCentered = True
            ws.page_margins.left = 0.3; ws.page_margins.right = 0.3
            ws.page_margins.top = 0.5; ws.page_margins.bottom = 0.5
        except Exception:
            pass

        # 요청에 따라 엑셀 내보내기 시 추가 시트(제조공정, 원료 환산)는 생성하지 않습니다.

        wb.save(file_path)
        try:
            if os.path.exists(approval_img_path): os.remove(approval_img_path)
        except Exception:
            pass

        if open_print_preview:
            try:
                import win32com.client as win32  # type: ignore
                excel = win32.Dispatch("Excel.Application"); excel.Visible = True
                wb_com = excel.Workbooks.Open(os.path.abspath(file_path))
                try:
                    wb_com.ActiveSheet.PrintPreview()
                finally:
                    wb_com.Close(SaveChanges=False); excel.Quit()
            except Exception:
                try:
                    os.startfile(os.path.abspath(file_path))
                except Exception:
                    pass
        else:
            messagebox.showinfo("성공", f"생산처방이 '{file_path}'에 저장되었습니다.")
    except Exception as e:
        messagebox.showerror("내보내기 오류", f"파일 저장 중 오류가 발생했습니다: {e}")

    

def export_data_to_excel(headers, data_rows, default_filename="export.xlsx"):
    """헤더와 데이터 행들을 단일 시트 엑셀 파일로 내보냅니다."""
    initial_dir = get_excel_path()
    timestamped_filename = get_timestamped_filename(default_filename)
    file_path = filedialog.asksaveasfilename(
        defaultextension=".xlsx",
        filetypes=[("Excel files", "*.xlsx")],
        initialdir=initial_dir,
        initialfile=timestamped_filename,
        title="데이터 저장"
    )
    if not file_path:
        return

    save_excel_path(os.path.dirname(file_path))

    # --- 스타일 정의 ---
    thin_border = Border(left=Side(style='thin'), 
                         right=Side(style='thin'), 
                         top=Side(style='thin'), 
                         bottom=Side(style='thin'))
    header_font = Font(name='맑은 고딕', size=11, bold=True)
    default_font = Font(name='맑은 고딕', size=10)
    center_align = Alignment(horizontal='center', vertical='center')
    left_align = Alignment(horizontal='left', vertical='center', wrap_text=True)
    header_fill = PatternFill(start_color="F2F2F2", end_color="F2F2F2", fill_type="solid")

    try:
        workbook = Workbook()
        sheet = workbook.active

        # 헤더 쓰기 및 스타일 적용
        for col_idx, header_text in enumerate(headers, 1):
            cell = sheet.cell(row=1, column=col_idx, value=header_text)
            cell.font = header_font
            cell.fill = header_fill
            cell.alignment = center_align
            cell.border = thin_border

        # 데이터 쓰기 및 스타일 적용
        for row_idx, row in enumerate(data_rows, 2):
            for col_idx, cell_value in enumerate(row, 1):
                cell = sheet.cell(row=row_idx, column=col_idx, value=cell_value)
                cell.font = default_font
                cell.border = thin_border
                cell.alignment = left_align

        # 컬럼 너비 자동 조절
        for col in sheet.columns:
            max_length = 0
            safe_cell = next((c for c in col if not isinstance(c, openpyxl.cell.cell.MergedCell)), None)
            if not safe_cell:
                continue
            column_letter = safe_cell.column_letter
            for cell in col:
                if cell.value:
                    # _get_display_length 함수를 사용하여 한글/영문 길이를 고려
                    length = _get_display_length(cell.value)
                    if length > max_length:
                        max_length = length
            adjusted_width = max_length + 2
            if adjusted_width > 5:
                sheet.column_dimensions[column_letter].width = adjusted_width

        workbook.save(file_path)
        messagebox.showinfo("성공", f"데이터가 '{file_path}'에 저장되었습니다.")
    except Exception as e:
        messagebox.showerror("오류", f"파일 저장 중 오류가 발생했습니다: {e}")

def export_multisheet_data_to_excel(sheets_data, default_filename="export.xlsx"):
    """데이터를 여러 시트를 가진 엑셀 파일로 내보냅니다."""
    initial_dir = get_excel_path()
    timestamped_filename = get_timestamped_filename(default_filename)
    file_path = filedialog.asksaveasfilename(
        defaultextension=".xlsx",
        filetypes=[("Excel files", "*.xlsx")],
        initialdir=initial_dir,
        initialfile=timestamped_filename,
        title="데이터 저장"
    )
    if not file_path:
        return

    save_excel_path(os.path.dirname(file_path))

    # --- 스타일 정의 ---
    thin_border = Border(left=Side(style='thin'), 
                         right=Side(style='thin'), 
                         top=Side(style='thin'), 
                         bottom=Side(style='thin'))
    header_font = Font(name='맑은 고딕', size=11, bold=True)
    default_font = Font(name='맑은 고딕', size=10)
    center_align = Alignment(horizontal='center', vertical='center')
    left_align = Alignment(horizontal='left', vertical='center', wrap_text=True)
    header_fill = PatternFill(start_color="F2F2F2", end_color="F2F2F2", fill_type="solid")

    try:
        workbook = Workbook()
        workbook.remove(workbook.active)
        for sheet_name, sheet_content in sheets_data.items():
            sheet = workbook.create_sheet(title=sheet_name)
            headers = sheet_content.get('headers', [])
            data_rows = sheet_content.get('data', [])
            apply_style = sheet_content.get('style', False)

            # 헤더 쓰기 및 스타일 적용
            for col_idx, header_text in enumerate(headers, 1):
                cell = sheet.cell(row=1, column=col_idx, value=header_text)
                if apply_style:
                    cell.font = header_font
                    cell.fill = header_fill
                    cell.alignment = center_align
                    cell.border = thin_border

            # 데이터 쓰기 및 스타일 적용
            for row_idx, row in enumerate(data_rows, 2):
                for col_idx, cell_value in enumerate(row, 1):
                    cell = sheet.cell(row=row_idx, column=col_idx, value=cell_value)
                    if apply_style:
                        cell.font = default_font
                        cell.border = thin_border
                        cell.alignment = left_align

            # 컬럼 너비 자동 조절
            for column_cells in sheet.columns:
                max_length = 0
                safe_cell = next((c for c in column_cells if not isinstance(c, openpyxl.cell.cell.MergedCell)), None)
                if not safe_cell:
                    continue
                column_letter = safe_cell.column_letter
                for cell in column_cells:
                    if cell.value is not None:
                        length = _get_display_length(cell.value)
                        if length > max_length:
                            max_length = length
                adjusted_width = max_length + 2
                if adjusted_width > 5: # 최소 너비
                    sheet.column_dimensions[column_letter].width = adjusted_width

        workbook.save(file_path)
        messagebox.showinfo("성공", f"데이터가 '{file_path}'에 저장되었습니다.")
    except Exception as e:
        messagebox.showerror("오류", f"파일 저장 중 오류가 발생했습니다: {e}")


def export_all_change_logs(sheets, default_filename="change_logs.xlsx"):
    """
    이미 준비된 sheets 구조(엔티티별 headers/data)를 받아서 멀티시트 엑셀로 저장합니다.
    호출자는 DB에서 change_log를 모아 sheets dict를 만들어 전달하면 됩니다.
    """
    # 단순히 기존 export_multisheet_data_to_excel과 동일한 동작을 수행
    return export_multisheet_data_to_excel(sheets, default_filename=default_filename)

def export_formulation_template(formulation_data, default_filename="formulation.xlsx", is_lab_journal=False):
    """처방 정보를 특정 템플릿 형식의 엑셀 파일로 내보냅니다."""
    initial_dir = get_excel_path()
    timestamped_filename = get_timestamped_filename(default_filename)
    file_path = filedialog.asksaveasfilename(
        defaultextension=".xlsx",
        filetypes=[("Excel files", "*.xlsx")],
        initialdir=initial_dir,
        initialfile=timestamped_filename,
        title="처방 내보내기"
    )
    if not file_path:
        return

    save_excel_path(os.path.dirname(file_path))

    # --- 스타일 정의 ---
    # 테두리
    thin = Side(style='thin')
    medium = Side(style='medium')
    thin_border = Border(left=thin, right=thin, top=thin, bottom=thin)
    medium_border = Border(left=medium, right=medium, top=medium, bottom=medium)
    
    # 폰트
    title_font = Font(name='맑은 고딕', size=18, bold=True)
    header_font = Font(name='맑은 고딕', size=11, bold=True)
    default_font = Font(name='맑은 고딕', size=10)
    total_font = Font(name='맑은 고딕', size=10, bold=True)

    # 정렬
    center_align = Alignment(horizontal='center', vertical='center')
    left_align = Alignment(horizontal='left', vertical='center', wrap_text=True)
    right_align = Alignment(horizontal='right', vertical='center')

    # 채우기
    header_fill = PatternFill(start_color="F2F2F2", end_color="F2F2F2", fill_type="solid")
    total_fill = PatternFill(start_color="E7E6E6", end_color="E7E6E6", fill_type="solid")

    def set_column_widths_for_sheet(sheet):
        """시트의 컬럼 너비를 설정하는 헬퍼 함수"""
        sheet.column_dimensions['A'].width = 18
        sheet.column_dimensions['B'].width = 20
        sheet.column_dimensions['C'].width = 40
        sheet.column_dimensions['D'].width = 15
        sheet.column_dimensions['E'].width = 15
        sheet.column_dimensions['F'].width = 25 # 비고 열 추가

    try:
        wb = Workbook()
        wb.remove(wb.active) # 기본 시트 제거

        # --- 상세 정보 쓰기 ---
        def write_sheet_data(sheet, sheet_details, sheet_items, set_column_widths=True, is_target_sheet=False):
            """
            시트에 상세 정보와 아이템 목록을 쓰는 헬퍼 함수
            is_lab_journal 플래그에 따라 헤더와 내용을 다르게 처리합니다.
            """
            
            def apply_border_to_range(cell_range, border_style):
                """지정된 범위의 모든 셀에 테두리를 적용합니다."""
                rows = sheet[cell_range]
                for row in rows:
                    for cell in row:
                        cell.border = border_style

            # --- 문서 제목 ---
            if is_lab_journal:
                # 실험일지는 전체 너비(J열까지)로 병합
                sheet.merge_cells('A1:J2')
            else:
                # 처방전은 결재란을 제외하고 병합
                sheet.merge_cells('A1:C2')
            
            title_cell = sheet['A1'] # 병합된 셀의 첫 번째 셀
            if is_lab_journal:
                title_cell.value = "실험일지 (Lab Journal)"
            else:
                title_cell.value = "타겟 정보 (Target Information)" if is_target_sheet else "처방전 (Formulation Sheet)"
            title_cell.font = title_font; title_cell.alignment = center_align
            
            # --- 결재란 추가 (실험일지, 타겟 정보 시트에는 없음) ---
            if not is_target_sheet and not is_lab_journal:
                approval_labels = ["작성", "검토", "승인"]
                for i, label in enumerate(approval_labels):
                    col_idx = i + 4 # D, E, F 열로 수정
                    sheet.column_dimensions[chr(ord('A') + col_idx - 1)].width = 15 # 결재란 각 칸 너비 동일하게
                    # 직책 셀
                    label_cell = sheet.cell(row=1, column=col_idx)
                    label_cell.value = label
                    label_cell.font = header_font
                    label_cell.alignment = center_align
                    label_cell.border = thin_border
                    # 서명 셀
                    sign_cell = sheet.cell(row=2, column=col_idx)
                    sign_cell.border = thin_border
                    sheet.row_dimensions[2].height = 40 # 서명 공간 높이
            
                # 결재란 전체에 중간 테두리 적용
                approval_range = f"D1:F2"
                for row in sheet[approval_range]:
                    for cell in row:
                        cell.border = thin_border


            # --- 상단 정보 섹션 (실험일지에는 없음) ---
            row_idx = 4
            if is_target_sheet:
                info_layout = [
                    ("타겟 샘플명", sheet_details.get("타겟 샘플명")),
                    ("타겟 거래처", sheet_details.get("타겟 거래처")),
                ]
            else:
                info_layout = [
                    ("실험품명", sheet_details.get("실험품명")),
                    ("실험년월일", sheet_details.get("실험년월일")),
                    ("담당자", sheet_details.get("담당자")),
                    ("거래처", sheet_details.get("거래처")),
                    ("LAB NO.", str(sheet_details.get("LAB NO.") or "").upper()), ("차수", str(sheet_details.get("차수") or "").upper()),
                    ("담당번호", str(sheet_details.get("담당번호") or "").upper()), ("총 실험량", sheet_details.get("총 실험량")),
                ]

            if not is_lab_journal:
                for i in range(0, len(info_layout), 2):
                    sheet.row_dimensions[row_idx].height = 25
                    # 레이블
                    cell_a = sheet[f"A{row_idx}"]; cell_a.value = info_layout[i][0]; cell_a.font = header_font; cell_a.fill = header_fill; cell_a.alignment = center_align
                    if i + 1 < len(info_layout):
                        cell_d = sheet[f"D{row_idx}"]; cell_d.value = info_layout[i+1][0]; cell_d.font = header_font; cell_d.fill = header_fill; cell_d.alignment = center_align
                    # 값
                    sheet.merge_cells(f"B{row_idx}:C{row_idx}")
                    cell_b = sheet[f"B{row_idx}"]; cell_b.value = info_layout[i][1]; cell_b.alignment = left_align
                    if i + 1 < len(info_layout):
                        cell_e = sheet[f"E{row_idx}"]; cell_e.value = info_layout[i+1][1]; cell_e.alignment = left_align
                    row_idx += 1
                # 상단 정보 섹션 테두리
                apply_border_to_range(f"A4:F{row_idx-1}", thin_border)

            # --- 타겟 정보 시트 처리 ---
            if is_target_sheet:
                row_idx += 1 # 한 줄 띄우기
                result_start_row = row_idx

                # pH 행
                sheet.row_dimensions[row_idx].height = 25
                sheet[f"A{row_idx}"].value = "타겟 pH"; sheet[f"A{row_idx}"].font = header_font; sheet[f"A{row_idx}"].fill = header_fill; sheet[f"A{row_idx}"].alignment = center_align
                sheet[f"B{row_idx}"].value = f"당일: {sheet_details.get('타겟 pH (당일)', '')}"; sheet[f"B{row_idx}"].alignment = left_align
                sheet[f"C{row_idx}"].value = f"익일: {sheet_details.get('타겟 pH (익일)', '')}"; sheet[f"C{row_idx}"].alignment = left_align
                row_idx += 1

                # 점도 행
                sheet.row_dimensions[row_idx].height = 25
                sheet[f"A{row_idx}"].value = "타겟 점도"; sheet[f"A{row_idx}"].font = header_font; sheet[f"A{row_idx}"].fill = header_fill; sheet[f"A{row_idx}"].alignment = center_align
                sheet[f"B{row_idx}"].value = f"당일: {sheet_details.get('타겟 점도 (당일)', '')}"; sheet[f"B{row_idx}"].alignment = left_align
                sheet[f"C{row_idx}"].value = f"익일: {sheet_details.get('타겟 점도 (익일)', '')}"; sheet[f"C{row_idx}"].alignment = left_align
                row_idx += 1

                # 사용핀 및 기계 행
                sheet.row_dimensions[row_idx].height = 25
                sheet[f"A{row_idx}"].value = "사용핀 및 기계"; sheet[f"A{row_idx}"].font = header_font; sheet[f"A{row_idx}"].fill = header_fill; sheet[f"A{row_idx}"].alignment = center_align
                sheet.merge_cells(f"B{row_idx}:F{row_idx}")
                sheet[f"B{row_idx}"].value = sheet_details.get("사용핀 및 기계", ""); sheet[f"B{row_idx}"].alignment = left_align
                row_idx += 1

                # 타겟 결과 섹션 테두리 (F열까지)
                apply_border_to_range(f"A{result_start_row}:F{row_idx-1}", thin_border)
                
                if set_column_widths: set_column_widths_for_sheet(sheet)
                return # 타겟 시트는 여기서 종료

            # --- 처방 정보 시트 처리 (아래는 is_target_sheet=False 일 때만 실행) ---
            
            # --- 처방 내용 헤더 ---
            if is_lab_journal:
                item_headers = ["실험 날짜", "품명", "pH", "점도", "비중", "Pin", "실험번호", "업체", "샘플 전달", "기타"]
                item_header_row_num = 4 # 상단 정보가 없으므로 4행부터 시작
            else:
                item_headers = ["구분", "코드", "원료명", "함량(%)", "실험량(g)", "비고"]
                item_header_row_num = row_idx + 1
            sheet.row_dimensions[item_header_row_num].height = 25
            for col_idx, header_text in enumerate(item_headers, 1):
                cell = sheet.cell(row=item_header_row_num, column=col_idx, value=header_text) # noqa
                cell.border = thin_border; cell.font = header_font; cell.alignment = center_align; cell.fill = header_fill
                # 실험일지 너비 자동 조절을 위해 헤더 길이도 계산에 포함
                if is_lab_journal:
                    sheet.column_dimensions[cell.column_letter].max_len = len(header_text)

            # --- 처방 내용 데이터 ---
            current_item_row = item_header_row_num + 1
            total_ratio = 0.0; total_amount = 0.0 # noqa
            for item in sheet_items:
                sheet.row_dimensions[current_item_row].height = 20
                code_value = item.get("코드", "")
                # 줄내림 체크: 코드가 ---, -, --, ―, ㅡ 중 하나인지 확인
                is_separator = isinstance(code_value, str) and code_value.strip() in ["---", "-", "--", "―", "ㅡ"]

                if is_lab_journal:
                    item_values = [item.get(h) for h in item_headers]
                else:
                    # 줄내림일 경우 함량과 실험량을 빈 문자열로 처리
                    item_values = [item.get("구분"), code_value, item.get("원료명"), 
                                   "" if is_separator else try_convert_to_float(item.get("함량(%)")),
                                   "" if is_separator else try_convert_to_float(item.get("실험량(g)")), ""] # 비고 칸 추가

                for col_idx, value in enumerate(item_values, 1):
                    cell = sheet.cell(row=current_item_row, column=col_idx, value=value)
                    cell.border = thin_border; cell.font = default_font
                    if is_lab_journal:
                        # 실험일지는 모든 셀을 가운데 정렬
                        cell.alignment = center_align
                        # 컬럼 너비 자동 조절을 위해 최대 길이 계산
                        if not hasattr(sheet.column_dimensions[cell.column_letter], 'max_len'): # noqa
                            sheet.column_dimensions[cell.column_letter].max_len = 0
                        sheet.column_dimensions[cell.column_letter].max_len = max(sheet.column_dimensions[cell.column_letter].max_len, len(str(value)))
                    else:
                        if is_separator:
                            cell.fill = total_fill # 합계 행과 같은 회색 배경
                            cell.alignment = center_align
                        else:
                            if col_idx in [1, 2]: cell.alignment = center_align
                            elif col_idx == 3: cell.alignment = left_align
                            else: 
                                cell.alignment = right_align
                                if isinstance(value, (int, float)):
                                    cell.number_format = '0.0000'
                                    if col_idx == 4: total_ratio += value
                                    if col_idx == 5: total_amount += value
                current_item_row += 1

            # --- 합계 행 추가 ---
            total_row = current_item_row
            sheet.row_dimensions[total_row].height = 25
            sheet.merge_cells(f'A{total_row}:C{total_row}')
            total_label_cell = sheet[f'A{total_row}']
            total_label_cell.value = "합계 (Total)"; total_label_cell.font = total_font; total_label_cell.alignment = center_align; total_label_cell.fill = total_fill

            total_ratio_cell = sheet[f'D{total_row}']
            total_ratio_cell.value = total_ratio; total_ratio_cell.font = total_font; total_ratio_cell.alignment = right_align; total_ratio_cell.number_format = '0.0000'; total_ratio_cell.fill = total_fill

            total_amount_cell = sheet[f'E{total_row}']
            total_amount_cell.value = total_amount; total_amount_cell.font = total_font; total_amount_cell.alignment = right_align; total_amount_cell.number_format = '0.0000'; total_amount_cell.fill = total_fill

            for col_char in "ABCDEF": sheet[f'{col_char}{total_row}'].border = thin_border
            
            # 실험일지인 경우 합계 행과 실험 결과 섹션을 숨깁니다.
            if is_lab_journal:
                sheet.row_dimensions[total_row].hidden = True
            else:
                # --- 실험 결과 섹션 ---
                row_idx = total_row + 2
                result_start_row = row_idx

                # pH 행
                sheet.row_dimensions[row_idx].height = 25
                sheet[f"A{row_idx}"].value = "pH"; sheet[f"A{row_idx}"].font = header_font; sheet[f"A{row_idx}"].fill = header_fill; sheet[f"A{row_idx}"].alignment = center_align
                sheet[f"B{row_idx}"].value = f"당일: {sheet_details.get('pH (당일)', '')}"; sheet[f"B{row_idx}"].alignment = left_align
                sheet[f"C{row_idx}"].value = f"익일: {sheet_details.get('pH (익일)', '')}"; sheet[f"C{row_idx}"].alignment = left_align
                row_idx += 1

                # 점도 행
                sheet.row_dimensions[row_idx].height = 25
                sheet[f"A{row_idx}"].value = "점도"; sheet[f"A{row_idx}"].font = header_font; sheet[f"A{row_idx}"].fill = header_fill; sheet[f"A{row_idx}"].alignment = center_align
                sheet[f"B{row_idx}"].value = f"당일: {sheet_details.get('점도 (당일)', '')}"; sheet[f"B{row_idx}"].alignment = left_align
                sheet[f"C{row_idx}"].value = f"익일: {sheet_details.get('점도 (익일)', '')}"; sheet[f"C{row_idx}"].alignment = left_align
                row_idx += 1

                # 사용핀 및 기계 행
                sheet.row_dimensions[row_idx].height = 25
                sheet[f"A{row_idx}"].value = "사용핀 및 기계"; sheet[f"A{row_idx}"].font = header_font; sheet[f"A{row_idx}"].fill = header_fill; sheet[f"A{row_idx}"].alignment = center_align
                sheet.merge_cells(f"B{row_idx}:F{row_idx}")
                sheet[f"B{row_idx}"].value = sheet_details.get("사용핀 및 기계", ""); sheet[f"B{row_idx}"].alignment = left_align
                row_idx += 1

                # 품평결과 및 특이사항 행
                sheet.row_dimensions[row_idx].height = 80
                sheet[f"A{row_idx}"].value = "품평결과 및 특이사항"; sheet[f"A{row_idx}"].font = header_font; sheet[f"A{row_idx}"].fill = header_fill; sheet[f"A{row_idx}"].alignment = center_align
                sheet.merge_cells(f"B{row_idx}:F{row_idx}")
                sheet[f"B{row_idx}"].value = sheet_details.get("품평결과 및 특이사항", ""); sheet[f"B{row_idx}"].alignment = left_align
                row_idx += 1

                # 실험 결과 섹션 테두리 (F열까지)
                apply_border_to_range(f"A{result_start_row}:F{row_idx-1}", thin_border)

            # 처방 내용 섹션 테두리 (실험일지일 경우 F열이 아닌 마지막 열까지)
            end_col_char = 'J' if is_lab_journal else 'F'
            apply_border_to_range(f"A{item_header_row_num}:{end_col_char}{total_row}", thin_border)

            # --- 컬럼 너비 설정 ---
            if set_column_widths:
                if is_lab_journal:
                    for col_dim in sheet.column_dimensions.values():
                        if hasattr(col_dim, 'max_len'):
                            col_dim.width = col_dim.max_len + 5
                else:
                    # 컬럼 너비 자동 조절 (개선된 로직)
                    for column_cells in sheet.columns:
                        max_length = 0
                        safe_cell = next((c for c in column_cells if not isinstance(c, openpyxl.cell.cell.MergedCell)), None)
                        if not safe_cell:
                            continue
                        column_letter = safe_cell.column_letter
                        for cell in column_cells:
                            if cell.value is not None:
                                length = _get_display_length(cell.value)
                                if length > max_length:
                                    max_length = length
                        adjusted_width = max_length + 2
                        if adjusted_width > 2:
                            sheet.column_dimensions[column_letter].width = adjusted_width

        details = formulation_data.get("details", {}); items = formulation_data.get("items", [])
        target_details = formulation_data.get("target_details")
        if target_details:
            # 타겟 정보가 있을 경우: 2개 시트 생성
            ws_formulation = wb.create_sheet("처방 정보")
            write_sheet_data(ws_formulation, details, items)

            ws_target = wb.create_sheet("타겟 정보")
            # 타겟 정보 시트에는 처방 내용(items)이 없으므로 빈 리스트 전달
            write_sheet_data(ws_target, target_details, [], is_target_sheet=True)
        else:
            # 타겟 정보가 없을 경우: 기존 방식대로 1개 시트 생성
            ws_formulation = wb.create_sheet("처방 정보")
            write_sheet_data(ws_formulation, details, items)

        wb.save(file_path)
        messagebox.showinfo("성공", f"처방 정보가 '{file_path}'에 저장되었습니다.")

    except Exception as e:
        messagebox.showerror("내보내기 오류", f"파일 저장 중 오류가 발생했습니다: {e}")
        # 오류 발생 시에도 파일은 생성되도록 복구 로직 추가
        details = formulation_data.get("details", {}); items = formulation_data.get("items", [])
        target_details = formulation_data.get("target_details")
        if target_details:
            # 타겟 정보가 있을 경우: 2개 시트 생성 (실험일지 모드에서는 실행되지 않음)
            ws_formulation = wb.create_sheet("처방 정보")
            write_sheet_data(ws_formulation, details, items)

            ws_target = wb.create_sheet("타겟 정보")
            # 타겟 정보 시트에는 처방 내용(items)이 없으므로 빈 리스트 전달
            write_sheet_data(ws_target, target_details, [], is_target_sheet=True)
        elif is_lab_journal:
            ws_journal = wb.create_sheet("실험일지")
            write_sheet_data(ws_journal, details, items, is_lab_journal=True)
        else:
            ws_formulation = wb.create_sheet("처방 정보")
            write_sheet_data(ws_formulation, details, items)
        wb.save(file_path)

def try_convert_to_float(value):
    """값을 float으로 변환 시도, 실패 시 원래 값 반환. 줄내림(---) 체크"""
    if value is None:
        return None
    # 줄내림 구분자 체크 (---, -, 등)
    if isinstance(value, str):
        stripped = value.strip()
        if stripped in ["---", "-", "--", "―", "ㅡ"]:
            return "---"  # 줄내림으로 명시적 반환
    try:
        return float(value)
    except (ValueError, TypeError):
        return value
def import_formulation_template():
    """(최종 수정) 특정 템플릿 형식의 엑셀 파일에서 처방 정보를 안정적으로 읽어옵니다."""
    initial_dir = get_excel_path()
    file_path = filedialog.askopenfilename(
        filetypes=[("Excel files", "*.xlsx")],
        initialdir=initial_dir,
        title="가져올 처방 파일 선택"
    )
    if not file_path:
        return None

    save_excel_path(os.path.dirname(file_path))

    try:
        wb = openpyxl.load_workbook(file_path, data_only=True)
        ws = wb["처방 정보"] if "처방 정보" in wb.sheetnames else wb.active

        formulation_data = {"details": {}, "items": []}

        # 읽기 상태를 관리하는 변수 (상세정보, 처방내용, 실험결과)
        reading_state = "details" # 'details', 'items', 'results'

        # 헤더를 저장할 리스트
        item_headers = []

        for row in ws.iter_rows(values_only=True):
            key_cell = row[0]
            key = str(key_cell).strip() if key_cell is not None else ""

            # 상태 전환 로직
            # 헤더 행은 '구분', '코드', '원료명', '함량(%)' 등을 포함하므로 더 명확하게 체크
            row_str_values = [str(c).strip() for c in row if c is not None]
            if "함량(%)" in row_str_values and "원료명" in row_str_values:
                reading_state = "items"
                item_headers = [h for h in row_str_values if h]
                continue # 헤더 행은 건너뜀
            elif key == "합계 (Total)":
                reading_state = "results"
                continue # 합계 행은 건너뜀

            # 상태에 따른 데이터 처리
            if reading_state == "details":
                # A, B열 키-값 쌍 (row[0], row[1])
                if key:
                    formulation_data["details"][key] = row[1]
                # D, E열 키-값 쌍 (row[3], row[4])
                if len(row) > 3 and row[3]:
                    key_d = str(row[3]).strip()
                    if key_d:
                        formulation_data["details"][key_d] = row[4]

            elif reading_state == "items":
                if all(c is None or str(c).strip() == "" for c in row): continue

                row_list = list(row)
                item_data = dict(zip(item_headers, row_list))

                # 줄내림 체크: 코드가 줄내림이면 함량과 실험량을 빈 문자열로 처리
                code_val = item_data.get('코드', '')
                is_separator = isinstance(code_val, str) and code_val.strip() in ["---", "-", "--", "―", "ㅡ"]
                
                if is_separator:
                    # 줄내림인 경우 함량과 실험량을 빈 문자열로
                    item_data['함량(%)'] = ""
                    item_data['실험량(g)'] = ""
                else:
                    # 일반 원료인 경우 숫자 변환
                    if '함량(%)' in item_data:
                        item_data['함량(%)'] = try_convert_to_float(item_data['함량(%)'])
                    if '실험량(g)' in item_data:
                        item_data['실험량(g)'] = try_convert_to_float(item_data['실험량(g)'])
                
                formulation_data["items"].append(item_data)

            elif reading_state == "results":
                if key == "pH" and len(row) > 2:
                    formulation_data["details"]["pH (당일)"] = str(row[1]).replace("당일:", "").strip() if row[1] else ""
                    formulation_data["details"]["pH (익일)"] = str(row[2]).replace("익일:", "").strip() if row[2] else ""
                elif key == "점도" and len(row) > 2:
                    formulation_data["details"]["점도 (당일)"] = str(row[1]).replace("당일:", "").strip() if row[1] else ""
                    formulation_data["details"]["점도 (익일)"] = str(row[2]).replace("익일:", "").strip() if row[2] else ""
                elif key in ["사용핀 및 기계", "품평결과 및 특이사항"]:
                    formulation_data["details"][key] = row[1]

        # --- 타겟 정보 시트가 있으면 추가로 읽기 ---
        if "타겟 정보" in wb.sheetnames:
            ws_target = wb["타겟 정보"]
            target_details = {}
            for row in ws_target.iter_rows(max_col=5, values_only=True):
                if not row or not row[0]: continue
                key = str(row[0]).strip()
                if key == "타겟 샘플명" and len(row) > 1:
                    target_details["타겟 샘플명"] = row[1]
                elif key == "타겟 거래처" and len(row) > 1:
                    target_details["타겟 거래처"] = row[1]
                elif key == "타겟 pH" and len(row) > 2:
                    target_details["타겟 pH (당일)"] = str(row[1]).replace("당일:", "").strip() if row[1] else ""
                    target_details["타겟 pH (익일)"] = str(row[2]).replace("익일:", "").strip() if row[2] else ""
                elif key == "타겟 점도" and len(row) > 2:
                    target_details["타겟 점도 (당일)"] = str(row[1]).replace("당일:", "").strip() if row[1] else ""
                    target_details["타겟 점도 (익일)"] = str(row[2]).replace("익일:", "").strip() if row[2] else ""
                elif key == "사용핀 및 기계" and len(row) > 1:
                    target_details["사용핀 및 기계"] = row[1]
            formulation_data["target_details"] = target_details

        return formulation_data
    except Exception as e:
        # document_management 모듈에서 ClipboardErrorDialog를 동적으로 가져옵니다.
        from modules.document_management import ClipboardErrorDialog
        # 오류 발생 시 클립보드 복사 기능이 있는 다이얼로그를 사용합니다.
        ClipboardErrorDialog(None, title="가져오기 오류", error_message=f"파일을 읽는 중 오류가 발생했습니다:\n\n{e}")
        return None

def export_ingredient_report_multiple(products_data):
    """여러 제품의 원료목록 보고서 데이터를 템플릿 형식의 엑셀 파일로 내보냅니다."""
    if not products_data:
        messagebox.showwarning("데이터 없음", "내보낼 제품 데이터가 없습니다.")
        return
    
    default_filename = f"원료목록보고서_{len(products_data)}개제품.xlsx"
    initial_dir = get_excel_path()
    timestamped_filename = get_timestamped_filename(default_filename)
    file_path = filedialog.asksaveasfilename(
        defaultextension=".xlsx",
        filetypes=[("Excel files", "*.xlsx")],
        initialdir=initial_dir,
        initialfile=timestamped_filename,
        title="원료목록 보고서 저장"
    )
    if not file_path:
        return

    save_excel_path(os.path.dirname(file_path))

    try:
        wb = Workbook()
        ws = wb.active
        ws.title = "원료목록보고서"

        # --- 스타일 정의 ---
        header_font = Font(name='맑은 고딕', size=11, bold=True)
        default_font = Font(name='맑은 고딕', size=10)
        center_align = Alignment(horizontal='center', vertical='center')
        left_align = Alignment(horizontal='left', vertical='center')
        header_fill = PatternFill(start_color="F2F2F2", end_color="F2F2F2", fill_type="solid")

        # --- 헤더 작성 ---
        headers = [
            "일련번호", "제품명", "유형표시", "기능성화장품유형", "기능성화장품품목코드",
            "제조업자상호", "원료성분명", "용도(E:수출용)", "맞춤형내용물(C1:혼합용/C2:소분용)"
        ]
        for col_idx, header_text in enumerate(headers, 1):
            cell = ws.cell(row=1, column=col_idx, value=header_text)
            cell.font = header_font
            cell.fill = header_fill
            cell.alignment = center_align

        # --- 여러 제품의 데이터 작성 ---
        current_row = 2
        for product_data in products_data:
            items = product_data.get('items', [])
            for item in items:
                row_data = [
                    item.get("일련번호"),
                    product_data.get("제품명"),
                    product_data.get("유형표시"),
                    product_data.get("기능성화장품유형"),
                    product_data.get("기능성화장품품목코드"),
                    product_data.get("제조업자상호"),
                    item.get("원료성분명"),
                    item.get("용도(E:수출용)"),
                    item.get("맞춤형내용물(C1:혼합용/C2:소분용)")
                ]
                for col_idx, cell_value in enumerate(row_data, 1):
                    cell = ws.cell(row=current_row, column=col_idx, value=cell_value)
                    cell.font = default_font
                    cell.alignment = left_align
                current_row += 1

        # --- 컬럼 너비 자동 조절 ---
        for col in ws.columns:
            max_length = 0
            column = col[0].column_letter
            for cell in col:
                try:
                    if cell.value:
                        length = _get_display_length(cell.value)
                        if length > max_length:
                            max_length = length
                except:
                    pass
            adjusted_width = max_length + 2
            ws.column_dimensions[column].width = adjusted_width

        wb.save(file_path)
        messagebox.showinfo("성공", f"원료목록 보고서가 '{file_path}'에 저장되었습니다.\n총 {len(products_data)}개 제품, {current_row-2}개 원료성분")
    except Exception as e:
        messagebox.showerror("오류", f"파일 저장 중 오류가 발생했습니다: {e}")

def export_ingredient_report(report_data):
    """원료목록 보고서 데이터를 템플릿 형식의 엑셀 파일로 내보냅니다."""
    default_filename = f"{report_data.get('제품명', '화장품')}_원료목록보고서.xlsx"
    initial_dir = get_excel_path()
    timestamped_filename = get_timestamped_filename(default_filename)
    file_path = filedialog.asksaveasfilename(
        defaultextension=".xlsx",
        filetypes=[("Excel files", "*.xlsx")],
        initialdir=initial_dir,
        initialfile=timestamped_filename,
        title="원료목록 보고서 저장"
    )
    if not file_path:
        return

    save_excel_path(os.path.dirname(file_path))

    try:
        wb = Workbook()
        ws = wb.active
        ws.title = "원료목록보고서"

        # --- 스타일 정의 ---
        header_font = Font(name='맑은 고딕', size=11, bold=True)
        default_font = Font(name='맑은 고딕', size=10)
        center_align = Alignment(horizontal='center', vertical='center')
        left_align = Alignment(horizontal='left', vertical='center')
        header_fill = PatternFill(start_color="F2F2F2", end_color="F2F2F2", fill_type="solid")

        # --- 헤더 작성 ---
        headers = [
            "일련번호", "제품명", "유형표시", "기능성화장품유형", "기능성화장품품목코드",
            "제조업자상호", "원료성분명", "용도(E:수출용)", "맞춤형내용물(C1:혼합용/C2:소분용)"
        ]
        for col_idx, header_text in enumerate(headers, 1):
            cell = ws.cell(row=1, column=col_idx, value=header_text)
            cell.font = header_font
            cell.fill = header_fill
            cell.alignment = center_align

        # --- 데이터 작성 ---
        items = report_data.get('items', [])
        for row_idx, item in enumerate(items, 2):
            row_data = [
                item.get("일련번호"),
                report_data.get("제품명"),
                report_data.get("유형표시"),
                report_data.get("기능성화장품유형"),
                report_data.get("기능성화장품품목코드"),
                report_data.get("제조업자상호"),
                item.get("원료성분명"),
                item.get("용도(E:수출용)"),
                item.get("맞춤형내용물(C1:혼합용/C2:소분용)")
            ]
            for col_idx, cell_value in enumerate(row_data, 1):
                cell = ws.cell(row=row_idx, column=col_idx, value=cell_value)
                cell.font = default_font
                cell.alignment = left_align

        # --- 컬럼 너비 자동 조절 ---
        for col in ws.columns:
            max_length = 0
            column = col[0].column_letter
            for cell in col:
                try:
                    if cell.value:
                        length = _get_display_length(cell.value)
                        if length > max_length:
                            max_length = length
                except:
                    pass
            adjusted_width = max_length + 2
            ws.column_dimensions[column].width = adjusted_width

        wb.save(file_path)
        messagebox.showinfo("성공", f"원료목록 보고서가 '{file_path}'에 저장되었습니다.")
    except Exception as e:
        messagebox.showerror("오류", f"파일 저장 중 오류가 발생했습니다: {e}")

def export_quotation_to_excel(quotation_data, default_filename="quotation.xlsx"):
    """견적서 데이터를 특정 템플릿 형식의 엑셀 파일로 내보냅니다."""
    initial_dir = get_excel_path()
    timestamped_filename = get_timestamped_filename(default_filename)
    file_path = filedialog.asksaveasfilename(
        defaultextension=".xlsx",
        filetypes=[("Excel files", "*.xlsx")],
        initialdir=initial_dir,
        initialfile=timestamped_filename,
        title="견적서 저장"
    )
    if not file_path:
        return

    save_excel_path(os.path.dirname(file_path))

    try:
        wb = Workbook()
        sheet = wb.active
        sheet.title = "견적서"

        # --- 스타일 정의 ---
        thin = Side(style='thin')
        thin_border = Border(left=thin, right=thin, top=thin, bottom=thin)
        title_font = Font(name='맑은 고딕', size=18, bold=True)
        header_font = Font(name='맑은 고딕', size=11, bold=True)
        default_font = Font(name='맑은 고딕', size=10)
        total_font = Font(name='맑은 고딕', size=10, bold=True)
        center_align = Alignment(horizontal='center', vertical='center')
        left_align = Alignment(horizontal='left', vertical='center')
        right_align = Alignment(horizontal='right', vertical='center')
        header_fill = PatternFill(start_color="F2F2F2", end_color="F2F2F2", fill_type="solid")
        total_fill = PatternFill(start_color="E7E6E6", end_color="E7E6E6", fill_type="solid")

        # --- 문서 제목 및 결재란 ---
        sheet.merge_cells('A1:C2') # 제목이 더 넓은 공간을 차지하도록 수정
        title_cell = sheet['A1']
        title_cell.value = "견적서 (Quotation)"
        title_cell.font = title_font
        title_cell.alignment = center_align

        approval_labels = ["작성", "검토", "승인"]
        for i, label in enumerate(approval_labels):
            col_idx = i + 4 # D, E, F 열
            sheet.column_dimensions[chr(ord('A') + col_idx - 1)].width = 15 # 결재란 각 칸 너비 동일하게
            sheet.cell(row=1, column=col_idx, value=label).font = header_font
            sheet.cell(row=1, column=col_idx).alignment = center_align
            sheet.cell(row=1, column=col_idx).border = thin_border
            sheet.cell(row=2, column=col_idx).border = thin_border
            sheet.row_dimensions[2].height = 40

        # --- 기본 정보 ---
        details = quotation_data.get("details", {})
        info_layout = [
            ("실험품명", details.get("실험품명")),
            ("담당자", details.get("담당자")),
            ("LAB NO.", details.get("LAB NO.")),
            ("기준 중량", details.get("기준 중량")),
        ]
        row_idx = 4
        for label, value in info_layout:
            sheet.cell(row=row_idx, column=1, value=label).font = header_font
            sheet.cell(row=row_idx, column=2, value=value)
            row_idx += 1

        # --- 견적 항목 헤더 ---
        row_idx += 1
        item_headers = ["구분", "코드", "원료명", "함량(%)", "단가(원/kg)", "원가(원)"]
        for col_idx, header in enumerate(item_headers, 1):
            cell = sheet.cell(row=row_idx, column=col_idx, value=header)
            cell.font = header_font; cell.alignment = center_align; cell.fill = header_fill; cell.border = thin_border

        # --- 견적 항목 데이터 ---
        row_idx += 1
        for item_values in quotation_data.get("items", []):
            for col_idx, value in enumerate(item_values, 1):
                # 숫자 변환 시도 (단, 쉼표 제거 후)
                if isinstance(value, str):
                    try_val = try_convert_to_float(value.replace(",", ""))
                    value = try_val if isinstance(try_val, (int, float)) else value

                cell = sheet.cell(row=row_idx, column=col_idx, value=value)
                cell.font = default_font; cell.border = thin_border
                if col_idx == 3: # 원료명
                    cell.alignment = left_align
                else:
                    cell.alignment = right_align
                
                if isinstance(value, (int, float)):
                    if col_idx == 4: cell.number_format = '0.0000' # 함량
                    elif col_idx == 5: cell.number_format = '#,##0' # 단가
                    elif col_idx == 6: cell.number_format = '#,##0.00' # 원가
            row_idx += 1

        # --- 요약 정보 ---
        row_idx += 1
        summary = quotation_data.get("summary", {})
        for label, value in summary.items(): # "총 함량", "총 원료 원가" 등
            label_cell = sheet.cell(row=row_idx, column=5, value=label)
            label_cell.font = total_font; label_cell.alignment = right_align
            value_cell = sheet.cell(row=row_idx, column=6, value=value)
            value_cell.font = total_font; value_cell.alignment = right_align; value_cell.number_format = '#,##0.00'
            row_idx += 1

        # --- 컬럼 너비 자동 조절 ---
        for column_cells in sheet.columns:
            max_length = 0
            safe_cell = next((c for c in column_cells if not isinstance(c, openpyxl.cell.cell.MergedCell)), None)
            if not safe_cell:
                continue
            column_letter = safe_cell.column_letter
            for cell in column_cells:
                if cell.value is not None:
                    length = _get_display_length(cell.value)
                    if length > max_length:
                        max_length = length
            adjusted_width = max_length + 2
            if adjusted_width > 2:
                sheet.column_dimensions[column_letter].width = adjusted_width

        wb.save(file_path)
        messagebox.showinfo("성공", f"견적서가 '{file_path}'에 저장되었습니다.")
    except Exception as e:
        messagebox.showerror("내보내기 오류", f"파일 저장 중 오류가 발생했습니다: {e}")

def export_ingredient_lists_to_excel(sheets_data, default_filename="ingredient_list.xlsx"):
    """
    다양한 형식의 전성분 목록 데이터를 여러 시트로 구성된 엑셀 파일로 내보냅니다.
    - sheets_data: {'시트명': {'type': 'table' or 'text', 'content': ...}}
    """
    initial_dir = get_excel_path()
    timestamped_filename = get_timestamped_filename(default_filename)
    file_path = filedialog.asksaveasfilename(
        defaultextension=".xlsx",
        filetypes=[("Excel files", "*.xlsx")],
        initialdir=initial_dir,
        initialfile=timestamped_filename,
        title="전성분 목록 저장"
    )
    if not file_path:
        return

    save_excel_path(os.path.dirname(file_path))

    try:
        wb = Workbook()
        wb.remove(wb.active)

        # 스타일 정의
        header_font = Font(name='맑은 고딕', size=11, bold=True)
        default_font = Font(name='맑은 고딕', size=10)
        center_align = Alignment(horizontal='center', vertical='center')
        left_align = Alignment(horizontal='left', vertical='center')
        right_align = Alignment(horizontal='right', vertical='center')
        header_fill = PatternFill(start_color="F2F2F2", end_color="F2F2F2", fill_type="solid")

        for sheet_name, sheet_content in sheets_data.items():
            sheet = wb.create_sheet(title=sheet_name)
            content_type = sheet_content.get('type')
            content = sheet_content.get('content')

            if content_type == 'table':
                headers = content.get('headers', [])
                data_rows = content.get('data', [])
                number_formats = content.get('number_formats', {})
                
                # 헤더 쓰기
                for col_idx, header_text in enumerate(headers, 1): # noqa
                    cell = sheet.cell(row=1, column=col_idx, value=header_text.replace('\n', ' '))
                    cell.font = header_font
                    cell.fill = header_fill
                    cell.alignment = center_align
                
                # 데이터 쓰기
                # 먼저 'NO' 또는 '구분'이 포함된 첫 번째 열을 찾아, 그 열부터 모두 중앙 정렬합니다.
                # '함량' 또는 '%'가 포함된 열은 숫자이므로 오른쪽 정렬을 유지합니다.
                special_indices = []
                for idx, h in enumerate(headers, 1):
                    ht = str(h)
                    if ht.strip().upper() == 'NO' or '구분' in ht or '함량' in ht or '%' in ht:
                        special_indices.append(idx)
                last_special_idx = max(special_indices) if special_indices else 0

                # 'NO' 또는 '구분'이 포함된 첫 번째 열의 인덱스를 찾습니다.
                center_align_start_col = -1
                for idx, h in enumerate(headers, 1):
                    if str(h).strip().upper() == 'NO' or '구분' in str(h):
                        center_align_start_col = idx
                        break

                for row_idx, row_data in enumerate(data_rows, 2): # noqa
                    for col_idx, cell_value in enumerate(row_data, 1): # 1-based index
                        cell = sheet.cell(row=row_idx, column=col_idx)
                        header_text = headers[col_idx - 1] # 0-based index for headers

                        # 숫자 형식 적용 대상인지 확인
                        num_format = number_formats.get(header_text)
                        if num_format:
                            # [수정] 빈 문자열이나 None일 경우를 안전하게 처리
                            if cell_value is None or cell_value == '':
                                cell.value = None # 빈 셀로 남겨둠
                            else:
                                try:
                                    cell.value = float(cell_value)
                                except (ValueError, TypeError):
                                    cell.value = cell_value # 변환 실패 시 원본 값 유지
                            cell.number_format = num_format
                        elif '함량' in header_text or '%' in header_text:
                            converted_value = try_convert_to_float(cell_value)
                            cell.value = converted_value
                        else:
                            cell.value = cell_value
                        cell.font = default_font

                        # 'NO' 또는 '구분' 열부터 시작하여 중앙 정렬 적용
                        if center_align_start_col != -1 and col_idx >= center_align_start_col:
                            cell.alignment = center_align
                        else:
                            # 숫자이면 오른쪽 정렬, 아니면 왼쪽 정렬을 기본으로 둡니다.
                            if isinstance(cell.value, (int, float)):
                                cell.alignment = right_align
                            else: # noqa
                                cell.alignment = left_align
                
                # 컬럼 너비 자동 조절 (개선된 로직)
                for column_cells in sheet.columns:
                    max_length = 0
                    safe_cell = next((c for c in column_cells if not isinstance(c, openpyxl.cell.cell.MergedCell)), None)
                    if not safe_cell:
                        continue
                    column_letter = safe_cell.column_letter
                    for cell in column_cells:
                        if cell.value is not None:
                            length = _get_display_length(cell.value)
                            if length > max_length:
                                max_length = length
                    
                    adjusted_width = (max_length + 2)
                    if adjusted_width > 2:
                        sheet.column_dimensions[column_letter].width = adjusted_width
                
                # --- 셀 병합 로직 추가 (원료별 목록 시트에만 적용) ---
                if sheet_name == "원료별 목록":
                    try:
                        # 병합할 열의 인덱스 찾기 (0-based for data, 1-based for openpyxl)
                        no_col_idx = headers.index("NO") + 1
                        material_name_col_idx = headers.index("원료명") + 1
                        rm_ratio_col_idx = headers.index("RM 함량(%)") + 1
                        # '구분' 열이 존재할 경우에만 인덱스 찾기
                        phase_col_idx = headers.index("구분") + 1 if "구분" in headers else None

                        cols_to_merge = [no_col_idx, material_name_col_idx, rm_ratio_col_idx]
                        if phase_col_idx:
                            cols_to_merge.append(phase_col_idx)

                        merge_start_row = 2  # 데이터는 2행부터 시작
                        for current_row_idx, row_data in enumerate(data_rows, start=2):
                            # 새로운 원료 그룹 시작 (NO 컬럼에 값이 있음)
                            if row_data[no_col_idx - 1]:
                                # 이전 그룹에 대한 병합 처리 (병합할 행이 2개 이상일 때)
                                if current_row_idx > merge_start_row:
                                    for col_to_merge in cols_to_merge:
                                        sheet.merge_cells(start_row=merge_start_row, start_column=col_to_merge, end_row=current_row_idx - 1, end_column=col_to_merge)
                                # 새 그룹의 시작 행 업데이트
                                merge_start_row = current_row_idx

                        # 마지막 그룹에 대한 병합 처리
                        if len(data_rows) + 1 >= merge_start_row:
                            for col_to_merge in cols_to_merge:
                                sheet.merge_cells(start_row=merge_start_row, start_column=col_to_merge, end_row=len(data_rows) + 1, end_column=col_to_merge)

                        # 병합된 셀의 세로 정렬을 '가운데'로 설정
                        for col_idx in cols_to_merge:
                            for row in sheet.iter_rows(min_row=2, max_row=sheet.max_row, min_col=col_idx, max_col=col_idx):
                                for cell in row:
                                    cell.alignment = Alignment(vertical='center', horizontal=cell.alignment.horizontal, wrap_text=True)

                    except (ValueError, IndexError) as e:
                        print(f"'{sheet_name}' 시트 셀 병합 중 오류 발생 (필수 컬럼 부재): {e}")
                        # 병합에 실패하더라도 데이터는 그대로 기록되도록 계속 진행
                # --- 셀 병합 로직 종료 ---

        # '디자인용 전성분' 시트에 대한 특별 스타일링
        if "디자인용 전성분" in wb.sheetnames:
            sheet = wb["디자인용 전성분"]
            # 헤더 삭제
            sheet.delete_rows(1)
            # 셀 스타일 적용
            for row in sheet.iter_rows(min_row=1, max_row=sheet.max_row):
                row[0].font = header_font # 구분 (국문:, 영문:)
                row[0].alignment = left_align
                row[1].font = default_font # 전성분 목록
                row[1].alignment = Alignment(wrap_text=True, vertical='top')
            # 자동 너비 조절 적용
            for column_cells in sheet.columns:
                max_length = 0
                safe_cell = next((c for c in column_cells if not isinstance(c, openpyxl.cell.cell.MergedCell)), None)
                if not safe_cell:
                    continue
                column_letter = safe_cell.column_letter
                for cell in column_cells:
                    if cell.value is not None:
                        length = _get_display_length(cell.value)
                        if length > max_length: max_length = length
                sheet.column_dimensions[column_letter].width = max_length + 2
            sheet.column_dimensions['B'].width = 100

        wb.save(file_path)
        messagebox.showinfo("성공", f"전성분 목록이 '{file_path}'에 저장되었습니다.")
    except Exception as e:
        messagebox.showerror("내보내기 오류", f"파일 저장 중 오류가 발생했습니다: {e}")

def export_functional_cosmetics_report_template(report_data=None):
    """UI에서 작성된 내용을 바탕으로 기능성화장품 심사제외품목 보고서를 생성하고 내보냅니다."""
    if report_data is None:
        report_data = {}

    initial_dir = get_excel_path()
    product_name = report_data.get("제품명(국문)", "기능성보고서")
    default_filename = f"{product_name}_심사제외보고서.xlsx"
    timestamped_filename = get_timestamped_filename(default_filename)
    file_path = filedialog.asksaveasfilename(
        defaultextension=".xlsx",
        filetypes=[("Excel files", "*.xlsx")],
        initialdir=initial_dir,
        initialfile=timestamped_filename,
        title="심사제외 품목 보고서 저장"
    )
    if not file_path:
        return

    save_excel_path(os.path.dirname(file_path))

    try:
        wb = Workbook()
        ws = wb.active
        ws.title = "기능성심사제외보고서"

        # --- Styles ---
        title_font = Font(name='맑은 고딕', size=16, bold=True)
        header_font = Font(name='맑은 고딕', size=11, bold=True)
        default_font = Font(name='맑은 고딕', size=10)
        
        center_align = Alignment(horizontal='center', vertical='center')
        left_align_top_wrap = Alignment(horizontal='left', vertical='top', wrap_text=True)
        
        thin_border = Border(left=Side(style='thin'), right=Side(style='thin'), top=Side(style='thin'), bottom=Side(style='thin'))

        # --- Column widths ---
        ws.column_dimensions['A'].width = 30
        ws.column_dimensions['B'].width = 45
        ws.column_dimensions['C'].width = 50

        # --- Title ---
        ws.merge_cells("A1:C1")
        title_cell = ws['A1']
        title_cell.value = "기능성화장품 심사제외품목 보고서"
        title_cell.font = title_font
        title_cell.alignment = center_align
        ws.row_dimensions[1].height = 30

        row_idx = 3

        def write_row_and_style(r_idx, values, is_header=False):
            """Helper to write a row and apply styles"""
            cells = []
            for c_idx, value in enumerate(values, 1):
                cell = ws.cell(row=r_idx, column=c_idx, value=value)
                cells.append(cell)
            
            for cell in cells:
                cell.border = thin_border
                cell.font = default_font
                cell.alignment = left_align_top_wrap
            
            if is_header and cells:
                cells[0].font = header_font
            
            # Auto row height for multiline content in the last cell
            if len(values) > 2 and values[2] and isinstance(values[2], str):
                num_lines = values[2].count('\n') + 1
                if num_lines > 1:
                    ws.row_dimensions[r_idx].height = 15 * num_lines

        # --- Data Parsing ---
        spf_pa_text = report_data.get("자외선 관련 (SPF / PA)", "")
        spf, pa = "", ""
        if "/" in spf_pa_text:
            parts = [p.strip() for p in spf_pa_text.split('/')]
            spf, pa = (parts[0], parts[1]) if len(parts) > 1 else (parts[0], "")
        else:
            if "spf" in spf_pa_text.lower(): spf = spf_pa_text
            elif "pa" in spf_pa_text.lower(): pa = spf_pa_text
        
        effects = report_data.get("효능·효과", "").replace(", ", "\n")

        # --- Report Layout ---
        layout = [
            ("보고정보", "제품명", report_data.get("제품명(국문)")),
            (None, "제품의 pH 기준치", report_data.get("pH (실측값)")),
            (None, "대상구분", report_data.get("제출유형")),
            ("제10조 제1항 제3호에 해당하는 경우", "이미 심사받은 품목", report_data.get("이미 심사받은 품목")),
            (None, "활성물질용량", report_data.get("활성물질용량")),
            (None, "자외선차단지수(SPF)", spf),
            (None, "자외선 A차단등급(PA)", pa),
            (None, "고시한 기준 및 시험방법", report_data.get("고시한 기준 및 시험방법")),
            (None, "효능효과", effects),
            (None, "용법용량", report_data.get("용법·용량")),
            (None, "사용할 때의 주의사항", report_data.get("사용할 때의 주의사항")),
            ("총량관리", "자동 입력", ""),
        ]

        # --- Write data and merge cells ---
        merge_start_row = 3
        for val_a, val_b, val_c in layout:
            if val_a is not None and row_idx > merge_start_row:
                ws.merge_cells(start_row=merge_start_row, start_column=1, end_row=row_idx - 1, end_column=1)
                ws.cell(merge_start_row, 1).alignment = left_align_top_wrap
                merge_start_row = row_idx
            
            write_row_and_style(row_idx, [val_a, val_b, val_c], is_header=(val_a is not None))
            row_idx += 1
        ws.merge_cells(start_row=merge_start_row, start_column=1, end_row=row_idx - 1, end_column=1)
        ws.cell(merge_start_row, 1).alignment = left_align_top_wrap

        # --- Section: 원료성분 및 배합 비율 ---
        start_row = row_idx
        
        ingredients_text = report_data.get("원료성분 및 배합비율", "")
        ingredients_list = []
        if ingredients_text and "예시:" not in ingredients_text:
            for line in ingredients_text.splitlines():
                if ":" in line:
                    parts = line.split(":", 1)
                    name = parts[0].strip()
                    amount = parts[1].strip()
                    ingredients_list.append((name, amount))
                elif line.strip():
                    ingredients_list.append((line.strip(), ""))
        
        if not ingredients_list:
            write_row_and_style(row_idx, ["원료성분 및 배합 비율", "(내용 없음)", ""], is_header=True)
            ws.merge_cells(start_row=row_idx, start_column=2, end_row=row_idx, end_column=3)
            row_idx += 1
        else:
            first_ing_name, first_ing_amount = ingredients_list[0]
            write_row_and_style(row_idx, ["원료성분 및 배합 비율", first_ing_name, first_ing_amount], is_header=True)
            row_idx += 1
            for name, amount in ingredients_list[1:]:
                write_row_and_style(row_idx, [None, name, amount])
                row_idx += 1

        ws.merge_cells(start_row=start_row, start_column=1, end_row=row_idx - 1, end_column=1)
        ws.cell(start_row, 1).alignment = left_align_top_wrap

        wb.save(file_path)
        messagebox.showinfo("성공", f"보고서 파일이 '{file_path}'에 저장되었습니다.")
    except Exception as e:
        messagebox.showerror("내보내기 오류", f"보고서 파일 저장 중 오류가 발생했습니다: {e}")

def export_production_formulation_to_excel(production_data, default_filename="production.xlsx", file_path: str | None = None, open_print_preview: bool = False, mode: str = "original"):
    """생산처방 정보를 엑셀로 내보냅니다.
    mode:
      - "original": 원래 템플릿(제목+영문부제, 결재란 이미지, 병합 포함, 추가 시트 포함)
      - "revised": 수정본 템플릿(결재란 텍스트 셀, 기본정보 병합 없음, 고정폭, 세로 인쇄, 단일 시트)
    """
    if (mode or "original").lower() == "revised":
        return export_production_formulation_revised_to_excel(
            production_data,
            default_filename=default_filename,
            file_path=file_path,
            open_print_preview=open_print_preview,
        )
    else:
        return export_production_formulation_original_to_excel(
            production_data,
            default_filename=default_filename,
            file_path=file_path,
            open_print_preview=open_print_preview,
        )

    
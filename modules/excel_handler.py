# modules/excel_handler.py
import openpyxl
from openpyxl import Workbook
from tkinter import filedialog, messagebox
from openpyxl.styles import Border, Side, Alignment, Font, PatternFill
import configparser
from datetime import datetime
import os

# --- 경로 설정을 읽기 위한 설정 ---
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CONFIG_FILE_PATH = os.path.join(PROJECT_ROOT, 'config.ini')

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
        for sheet_name, headers in sheets_with_headers.items():
            sheet = workbook.create_sheet(title=sheet_name)
            sheet.append(headers)
        workbook.save(file_path)
        messagebox.showinfo("성공", f"엑셀 폼이 '{file_path}'에 저장되었습니다.")
    except Exception as e:
        messagebox.showerror("오류", f"파일 저장 중 오류가 발생했습니다: {e}")

def import_multisheet_data():
    """여러 시트를 가진 엑셀 파일에서 데이터를 가져옵니다."""
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
        - 문자열은 앞뒤 공백 제거
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
        all_data = {}
        for sheet_name in workbook.sheetnames:
            sheet = workbook[sheet_name]
            headers = [cell.value for cell in sheet[1]]
            data_list = []
            for row in sheet.iter_rows(min_row=2, values_only=True):
                # 전부 비거나 '-'인 행 건너뜀
                if all(cell is None or str(cell).strip() in ("", "-") for cell in row):
                    continue
                # 헤더 개수 맞추기
                row = list(row) + [None] * (len(headers) - len(row))
                # 셀 값 정리
                row = [clean_cell(cell) for cell in row]
                row_data = dict(zip(headers, row))
                data_list.append(row_data)
            all_data[sheet_name] = data_list
        return all_data
    except Exception as e:
        messagebox.showerror("오류", f"파일을 읽는 중 오류가 발생했습니다: {e}")
        return None

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

    try:
        workbook = Workbook()
        sheet = workbook.active
        sheet.append(headers)
        for row in data_rows:
            sheet.append(row)
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

    try:
        workbook = Workbook()
        workbook.remove(workbook.active)
        for sheet_name, sheet_content in sheets_data.items():
            sheet = workbook.create_sheet(title=sheet_name)
            sheet.append(sheet_content['headers'])
            for row in sheet_content['data']:
                sheet.append(row)
        workbook.save(file_path)
        messagebox.showinfo("성공", f"데이터가 '{file_path}'에 저장되었습니다.")
    except Exception as e:
        messagebox.showerror("오류", f"파일 저장 중 오류가 발생했습니다: {e}")

def export_formulation_template(formulation_data, default_filename="formulation.xlsx"):
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

    try:
        wb = Workbook()
        wb.remove(wb.active) # 기본 시트 제거

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

        # --- 상세 정보 쓰기 ---
        def write_sheet_data(sheet, sheet_details, sheet_items, set_column_widths=True, is_target_sheet=False):
            """시트에 상세 정보와 아이템 목록을 쓰는 헬퍼 함수"""
            
            def apply_border_to_range(cell_range, border_style):
                """지정된 범위의 모든 셀에 테두리를 적용합니다."""
                rows = sheet[cell_range]
                for row in rows:
                    for cell in row:
                        cell.border = border_style

            # --- 문서 제목 ---
            sheet.merge_cells('A1:C2') # 제목 셀 병합 (결재란과 겹치지 않도록)
            title_cell = sheet['A1']
            title_cell.value = "타겟 정보 (Target Information)" if is_target_sheet else "처방전 (Formulation Sheet)"
            title_cell.font = title_font; title_cell.alignment = center_align
            
            # --- 결재란 추가 (오른쪽 위) ---
            if not is_target_sheet:
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

            # --- 상단 정보 섹션 ---
            row_idx = 4 # 결재란 아래부터 시작
            if is_target_sheet:
                info_layout = [
                    ("타겟 샘플명", sheet_details.get("타겟 샘플명")), ("타겟 거래처", sheet_details.get("타겟 거래처")),
                ]
            else:
                info_layout = [
                    ("실험품명", sheet_details.get("실험품명")), ("실험년월일", sheet_details.get("실험년월일")),
                    ("담당자", sheet_details.get("담당자")), ("거래처", sheet_details.get("거래처")),
                    ("LAB NO.", str(sheet_details.get("LAB NO.") or "").upper()), ("차수", str(sheet_details.get("차수") or "").upper()),
                    ("담당번호", str(sheet_details.get("담당번호") or "").upper()), ("총 실험량", sheet_details.get("총 실험량")),
                ]

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
            item_headers = ["구분", "코드", "원료명", "함량(%)", "실험량(g)", "비고"]
            item_header_row_num = row_idx + 1
            sheet.row_dimensions[item_header_row_num].height = 25
            for col_idx, header_text in enumerate(item_headers, 1):
                cell = sheet.cell(row=item_header_row_num, column=col_idx, value=header_text)
                cell.border = thin_border; cell.font = header_font; cell.alignment = center_align; cell.fill = header_fill

            # --- 처방 내용 데이터 ---
            current_item_row = item_header_row_num + 1
            total_ratio = 0.0; total_amount = 0.0
            for item in sheet_items:
                sheet.row_dimensions[current_item_row].height = 20
                is_separator = item.get("코드") == "---"
                
                item_values = [item.get("구분"), item.get("코드"), item.get("원료명"), 
                               try_convert_to_float(item.get("함량(%)")) if not is_separator else "---",
                               try_convert_to_float(item.get("실험량(g)")) if not is_separator else "---", ""] # 비고 칸 추가

                for col_idx, value in enumerate(item_values, 1):
                    cell = sheet.cell(row=current_item_row, column=col_idx, value=value)
                    cell.border = thin_border; cell.font = default_font
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
            
            # 처방 내용 섹션 테두리
            apply_border_to_range(f"A{item_header_row_num}:F{total_row}", thin_border)

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

            # --- 컬럼 너비 설정 ---
            if set_column_widths:
                set_column_widths_for_sheet(sheet)

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

def try_convert_to_float(value):
    """값을 float으로 변환 시도, 실패 시 원래 값 반환"""
    if value is None:
        return None
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

        # --- 컬럼 너비 설정 (수정) ---
        sheet.column_dimensions['A'].width = 10 # 구분
        sheet.column_dimensions['B'].width = 15 # 코드
        sheet.column_dimensions['C'].width = 40 # 원료명
        sheet.column_dimensions['D'].width = 15 # 함량
        sheet.column_dimensions['E'].width = 18 # 단가
        sheet.column_dimensions['F'].width = 20 # 원가

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
                
                # 헤더 쓰기
                for col_idx, header_text in enumerate(headers, 1):
                    cell = sheet.cell(row=1, column=col_idx, value=header_text.replace('\n', ' '))
                    cell.font = header_font
                    cell.fill = header_fill
                    cell.alignment = center_align
                
                # 데이터 쓰기
                for row_idx, row_data in enumerate(data_rows, 2):
                    for col_idx, cell_value in enumerate(row_data, 1): # 1-based index
                        cell = sheet.cell(row=row_idx, column=col_idx)
                        header_text = headers[col_idx - 1] # 0-based index for headers

                        # '함량' 또는 '%'가 포함된 헤더의 열은 숫자로 변환 시도
                        if '함량' in header_text or '%' in header_text:
                            converted_value = try_convert_to_float(cell_value)
                            cell.value = converted_value
                        else:
                            cell.value = cell_value
                        cell.font = default_font
                
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

                # 컬럼 너비 자동 조절
                for col in sheet.columns:
                    max_length = 0
                    column = col[0].column_letter
                    for cell in col:
                        try:
                            if len(str(cell.value)) > max_length:
                                max_length = len(str(cell.value))
                        except:
                            pass
                    adjusted_width = (max_length + 2)
                    sheet.column_dimensions[column].width = adjusted_width

            elif content_type == 'text':
                # 이 로직은 이제 '디자인용 전성분' 시트에서는 사용되지 않지만,
                # 다른 텍스트 타입의 시트를 위해 유지합니다.
                sheet['A1'].value = content
                sheet['A1'].font = default_font
                sheet['A1'].alignment = Alignment(wrap_text=True, vertical='top')
                sheet.column_dimensions['A'].width = 100

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
            sheet.column_dimensions['B'].width = 100

        wb.save(file_path)
        messagebox.showinfo("성공", f"전성분 목록이 '{file_path}'에 저장되었습니다.")
    except Exception as e:
        messagebox.showerror("내보내기 오류", f"파일 저장 중 오류가 발생했습니다: {e}")

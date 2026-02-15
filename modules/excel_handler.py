import os
from datetime import datetime
from tkinter import filedialog, messagebox
import openpyxl
from openpyxl.styles import Font, Alignment, Border, Side

def export_data_to_excel(headers, data, default_filename="export.xlsx", sheet_name="Sheet1"):
    """
    일반적인 데이터 리스트를 엑셀로 내보내는 함수
    headers: 헤더 리스트 ['col1', 'col2', ...]
    data: 데이터 리스트 [[val1, val2, ...], ...]
    default_filename: 저장할 파일명 기본값
    sheet_name: 시트 이름
    """
    try:
        # 파일 저장 대화상자 열기
        file_path = filedialog.asksaveasfilename(
            defaultextension=".xlsx",
            filetypes=[("Excel files", "*.xlsx"), ("All files", "*.*")],
            initialfile=default_filename
        )

        if not file_path:
            return False

        # 워크북 생성
        wb = openpyxl.Workbook()
        ws = wb.active
        ws.title = sheet_name

        # 헤더 스타일 설정
        header_font = Font(bold=True)
        center_alignment = Alignment(horizontal="center", vertical="center")
        thin_border = Border(left=Side(style='thin'), 
                             right=Side(style='thin'), 
                             top=Side(style='thin'), 
                             bottom=Side(style='thin'))

        # 헤더 쓰기
        for col_idx, header in enumerate(headers, 1):
            cell = ws.cell(row=1, column=col_idx, value=str(header))
            cell.font = header_font
            cell.alignment = center_alignment
            cell.border = thin_border

        # 데이터 쓰기
        for row_idx, row_data in enumerate(data, 2):
            for col_idx, value in enumerate(row_data, 1):
                cell = ws.cell(row=row_idx, column=col_idx, value=str(value) if value is not None else "")
                cell.alignment = center_alignment
                cell.border = thin_border

        # 컬럼 너비 자동 조정 (대략적으로)
        for col in ws.columns:
            max_length = 0
            column = col[0].column_letter # Get the column name
            for cell in col:
                try:
                    if len(str(cell.value)) > max_length:
                        max_length = len(str(cell.value))
                except:
                    pass
            adjusted_width = (max_length + 2) * 1.2
            ws.column_dimensions[column].width = adjusted_width

        # 파일 저장
        wb.save(file_path)
        messagebox.showinfo("성공", "파일이 성공적으로 저장되었습니다.")
        
        # 파일 열기 시도 (Windows only)
        try:
            os.startfile(file_path)
        except:
            pass
            
        return True

    except Exception as e:
        messagebox.showerror("오류", f"엑셀 저장 중 오류가 발생했습니다:\n{str(e)}")
        return False

def export_production_history_list(data_list):
    """
    생산 이력 목록을 엑셀로 내보냅니다.
    data_list: 딕셔너리 리스트 [{'지시일자': '...', '생산일자': '...', ...}, ...]
    """
    if not data_list:
        messagebox.showwarning("경고", "내보낼 데이터가 없습니다.")
        return

    # 헤더 정의 (순서 보장)
    headers = [
        "지시일자", 
        "생산일자", 
        "제조번호", 
        "비중", 
        "점도(당일/익일)", 
        "pH(당일/익일)", 
        "비고", 
        "기록일"
    ]
    
    data_rows = []
    for item in data_list:
        row = [item.get(h, "") for h in headers]
        data_rows.append(row)
        
    export_data_to_excel(
        headers=headers, 
        data=data_rows, 
        default_filename=f"생산이력목록_{datetime.now().strftime('%Y%m%d')}.xlsx",
        sheet_name="생산이력"
    )

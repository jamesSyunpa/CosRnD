# modules/quality_management.py
import customtkinter as ctk
from tkinter import messagebox
from openpyxl import Workbook
from openpyxl.styles import Font, Alignment, Border, Side, PatternFill
from openpyxl.utils import get_column_letter
import tkinter.filedialog as fd

from modules.translation import get_texts

class QualityManagementFrame(ctk.CTkFrame):
    """품질 관리 관련 기능을 포함하는 프레임"""
    def __init__(self, master, user, app, texts):
        super().__init__(master)
        self.current_user = user
        self.app = app
        self.texts = texts

        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(0, weight=1)

        # --- 메인 탭 뷰 ---
        self.tab_view = ctk.CTkTabview(
            self, border_width=1, border_color=("gray80", "gray30"),
            segmented_button_selected_color=("#3B8ED0", "#1F6AA5"),
            segmented_button_unselected_color=("gray92", "gray20"),
            text_color=("black", "white"),
            segmented_button_selected_hover_color=("#3671A8", "#144870"),
            segmented_button_unselected_hover_color=("gray85", "gray28")
        )
        self.tab_view.grid(row=0, column=0, sticky="nsew", padx=10, pady=10)

        # --- 탭 추가 ---
        self.tab_view.add(self.texts['ingredient_report'])
        self.tab_view.add(self.texts['coa'])
        self.tab_view.add(self.texts['msds'])
        self.tab_view.add(self.texts['prod_standard'])
        self.tab_view.add(self.texts['mfg_record'])

        # --- 각 탭 UI 설정 ---
        self.setup_placeholder_tab(self.tab_view.tab(self.texts['ingredient_report']), self.texts['ingredient_report'])
        self.setup_coa_tab(self.tab_view.tab(self.texts['coa']))
        self.setup_placeholder_tab(self.tab_view.tab(self.texts['msds']), self.texts['msds'])
        self.setup_placeholder_tab(self.tab_view.tab(self.texts['prod_standard']), self.texts['prod_standard'])
        self.setup_placeholder_tab(self.tab_view.tab(self.texts['mfg_record']), self.texts['mfg_record'])

    def setup_coa_tab(self, tab_frame):
        """COA 탭의 UI를 설정합니다."""
        tab_frame.grid_columnconfigure(0, weight=1)
        tab_frame.grid_rowconfigure(0, weight=1)

        # --- COA 서브 탭 뷰 ---
        coa_sub_tab_view = ctk.CTkTabview(tab_frame, border_width=1, border_color=("gray80", "gray30"))
        coa_sub_tab_view.grid(row=0, column=0, padx=10, pady=10, sticky="nsew")

        coa_sub_tab_view.add(self.texts['semi_finished_product_report'])
        # coa_sub_tab_view.add(self.texts['finished_product_report']) # 추후 확장용

        self.setup_semi_finished_product_tab(coa_sub_tab_view.tab(self.texts['semi_finished_product_report']))

    def setup_semi_finished_product_tab(self, tab_frame):
        """반제품 시험성적서 탭의 UI를 더 깔끔하게 재구성합니다."""
        tab_frame.grid_columnconfigure(0, weight=1)
        tab_frame.grid_rowconfigure(0, weight=1)

        # --- 스크롤 가능한 메인 프레임 ---
        scrollable_frame = ctk.CTkScrollableFrame(tab_frame, label_text=self.texts['semi_finished_product_report_title'])
        scrollable_frame.grid(row=0, column=0, sticky="nsew", padx=10, pady=10)
        scrollable_frame.grid_columnconfigure(0, weight=1)

        self.semi_product_entries = {}

        # --- 기본 정보 섹션 ---
        info_frame = ctk.CTkFrame(scrollable_frame)
        info_frame.grid(row=0, column=0, sticky="ew", padx=10, pady=(10, 20))
        info_frame.grid_columnconfigure((1, 3), weight=1)

        # Row 0: 제품명, LOT
        ctk.CTkLabel(info_frame, text="제 품 명", font=ctk.CTkFont(weight="bold")).grid(row=0, column=0, padx=10, pady=5, sticky="w")
        self.semi_product_entries["제품명"] = ctk.CTkEntry(info_frame)
        self.semi_product_entries["제품명"].grid(row=0, column=1, padx=10, pady=5, sticky="ew")
        
        ctk.CTkLabel(info_frame, text="LOT", font=ctk.CTkFont(weight="bold")).grid(row=0, column=2, padx=10, pady=5, sticky="w")
        self.semi_product_entries["LOT"] = ctk.CTkEntry(info_frame)
        self.semi_product_entries["LOT"].grid(row=0, column=3, padx=10, pady=5, sticky="ew")

        # Row 1: 제조일자, 시험일자
        ctk.CTkLabel(info_frame, text="제조일자", font=ctk.CTkFont(weight="bold")).grid(row=1, column=0, padx=10, pady=5, sticky="w")
        self.semi_product_entries["제조일자"] = ctk.CTkEntry(info_frame)
        self.semi_product_entries["제조일자"].grid(row=1, column=1, padx=10, pady=5, sticky="ew")

        ctk.CTkLabel(info_frame, text="시험일자", font=ctk.CTkFont(weight="bold")).grid(row=1, column=2, padx=10, pady=5, sticky="w")
        self.semi_product_entries["시험일자"] = ctk.CTkEntry(info_frame)
        self.semi_product_entries["시험일자"].grid(row=1, column=3, padx=10, pady=5, sticky="ew")

        # --- 시험 항목 테이블 ---
        table_frame = ctk.CTkFrame(scrollable_frame)
        table_frame.grid(row=1, column=0, sticky="ew", padx=10, pady=10)
        table_frame.grid_columnconfigure(0, weight=0, minsize=60)  # 구분
        table_frame.grid_columnconfigure(1, weight=2)             # 시험항목
        table_frame.grid_columnconfigure(2, weight=3)             # 시험기준
        table_frame.grid_columnconfigure(3, weight=3)             # 시험결과
        table_frame.grid_columnconfigure(4, weight=1)             # 비고

        # Table Header
        headers = self.texts['semi_product_table_headers']
        for i, h in enumerate(headers):
            header_label = ctk.CTkLabel(table_frame, text=h, font=ctk.CTkFont(weight="bold"), fg_color=("gray85", "gray20"), corner_radius=0)
            header_label.grid(row=0, column=i, sticky="ew", padx=(1,0), pady=(1,0))

        # Table Rows
        test_items = [
            ("1", "성상", "표준품과 일치", "성상", "판정_성상"),
            ("2", "향취", "표준품과 일치", "향취", "판정_향취"),
            ("3", "사용감", "표준품과 일치", "사용감", "판정_사용감"),
            ("4", "pH (30℃)", "6.50 ± 1.00", "pH(30℃)", "판정_pH"),
            ("5", "점도(30℃)", "33,000 ± 5,000", "점도(30℃)", "판정_점도"),
            ("6", "비중(25℃)", "0.980 ± 0.02", "비중(25℃)", "판정_비중"),
            ("7", "미생물(일반세균)", "100 cfu/ml 이하", "일반세균", "판정_일반세균"),
            ("", "미생물(효모/곰팡이)", "10 cfu/ml 이하", "효모/곰팡이", "판정_효모곰팡이"),
            ("", "미생물(대장균)", "불검출", "대장균", "판정_대장균"),
        ]

        for i, item in enumerate(test_items, start=1):
            # 구분
            ctk.CTkLabel(table_frame, text=item[0]).grid(row=i, column=0, sticky="ew", padx=(1,0), pady=(1,0))
            # 시험항목
            ctk.CTkLabel(table_frame, text=item[1], anchor="w").grid(row=i, column=1, sticky="ew", padx=5, pady=(1,0))
            
            # 시험기준 (Entry)
            self.semi_product_entries[f"기준_{item[3]}"] = ctk.CTkEntry(table_frame, corner_radius=0, border_width=0)
            self.semi_product_entries[f"기준_{item[3]}"].insert(0, item[2])
            self.semi_product_entries[f"기준_{item[3]}"].grid(row=i, column=2, sticky="ew", padx=(1,0), pady=(1,0))
            
            # 시험결과 (Entry)
            self.semi_product_entries[f"결과_{item[3]}"] = ctk.CTkEntry(table_frame, corner_radius=0, border_width=0)
            self.semi_product_entries[f"결과_{item[3]}"].grid(row=i, column=3, sticky="ew", padx=(1,0), pady=(1,0))

            # 비고 (Entry)
            self.semi_product_entries[item[4]] = ctk.CTkEntry(table_frame, corner_radius=0, border_width=0)
            self.semi_product_entries[item[4]].grid(row=i, column=4, sticky="ew", padx=(1,0), pady=(1,0))

        # --- 판정 정보 섹션 ---
        conclusion_frame = ctk.CTkFrame(scrollable_frame)
        conclusion_frame.grid(row=2, column=0, sticky="ew", padx=10, pady=(20, 10))
        conclusion_frame.grid_columnconfigure((1, 3, 5), weight=1)

        ctk.CTkLabel(conclusion_frame, text="시험자", font=ctk.CTkFont(weight="bold")).grid(row=0, column=0, padx=10, pady=5, sticky="w")
        self.semi_product_entries["시험자"] = ctk.CTkEntry(conclusion_frame)
        self.semi_product_entries["시험자"].grid(row=0, column=1, padx=10, pady=5, sticky="ew")

        ctk.CTkLabel(conclusion_frame, text="일자", font=ctk.CTkFont(weight="bold")).grid(row=0, column=2, padx=10, pady=5, sticky="w")
        self.semi_product_entries["일자"] = ctk.CTkEntry(conclusion_frame)
        self.semi_product_entries["일자"].grid(row=0, column=3, padx=10, pady=5, sticky="ew")

        ctk.CTkLabel(conclusion_frame, text="종합판정", font=ctk.CTkFont(weight="bold")).grid(row=0, column=4, padx=10, pady=5, sticky="w")
        self.semi_product_entries["종합판정"] = ctk.CTkEntry(conclusion_frame)
        self.semi_product_entries["종합판정"].grid(row=0, column=5, padx=10, pady=5, sticky="ew")

        # --- 하단 버튼 프레임 ---
        button_frame = ctk.CTkFrame(tab_frame, fg_color="transparent")
        button_frame.grid(row=1, column=0, padx=10, pady=10, sticky="e")

        ctk.CTkButton(button_frame, text=self.texts['create_excel_report'], command=self.generate_semi_product_report).pack(side="left", padx=5)
        ctk.CTkButton(button_frame, text=self.texts['reset'], command=self.clear_semi_product_form, fg_color="gray50", hover_color="gray35").pack(side="left", padx=5)

    def clear_semi_product_form(self):
        """반제품 시험성적서 폼의 모든 입력 필드를 초기화합니다."""
        for entry in self.semi_product_entries.values():
            entry.delete(0, "end")
        messagebox.showinfo(self.texts['notification'], self.texts['form_cleared'], parent=self)

    def generate_semi_product_report(self):
        """입력된 데이터를 기반으로 깔끔한 서식의 반제품 시험성적서 엑셀 파일을 생성합니다."""
        from openpyxl.styles import Font, Alignment, Border, Side, PatternFill

        try:
            # --- 데이터 수집 ---
            kor_data = {key: entry.get() for key, entry in self.semi_product_entries.items()}
            
            if not all(kor_data.get(key) for key in ["제품명", "LOT", "종합판정"]):
                messagebox.showwarning(self.texts['input_error'], self.texts['required_fields_missing'], parent=self)
                return

            # --- Excel 워크북 및 스타일 정의 ---
            wb = Workbook()
            
            # 스타일
            title_font = Font(name='맑은 고딕', size=18, bold=True)
            header_font = Font(name='맑은 고딕', size=11, bold=True, color="FFFFFF")
            label_font = Font(name='맑은 고딕', size=10, bold=True)
            cell_font = Font(name='맑은 고딕', size=10)
            
            center_align = Alignment(horizontal="center", vertical="center", wrap_text=True)
            left_align = Alignment(horizontal="left", vertical="center", indent=1, wrap_text=True)
            
            thin_border = Border(left=Side(style='thin'), right=Side(style='thin'), top=Side(style='thin'), bottom=Side(style='thin'))
            header_fill = PatternFill(start_color="4F81BD", end_color="4F81BD", fill_type="solid")
            label_fill = PatternFill(start_color="DCE6F1", end_color="DCE6F1", fill_type="solid")

            def apply_style_to_range(ws, cell_range, font=None, border=None, fill=None, alignment=None):
                rows = ws[cell_range]
                if not isinstance(rows, tuple):
                    rows = ((rows,),)
                for row in rows:
                    for cell in row:
                        if font: cell.font = font
                        if border: cell.border = border
                        if fill: cell.fill = fill
                        if alignment: cell.alignment = alignment

            # === [1] 한글 시험성적서 시트 생성 ===
            ws1 = wb.active
            ws1.title = "반제품 시험성적서"

            # --- 문서 제목 ---
            ws1.merge_cells('A1:F2')
            ws1['A1'] = "반제품 시험성적서"
            ws1['A1'].font = title_font
            ws1['A1'].alignment = center_align
            
            # --- 기본 정보 ---
            ws1.merge_cells('B4:C4'); ws1.merge_cells('E4:F4')
            ws1.merge_cells('B5:C5'); ws1.merge_cells('E5:F5')
            ws1['A4'] = "제 품 명"; ws1['B4'] = kor_data.get("제품명")
            ws1['D4'] = "L O T"; ws1['E4'] = kor_data.get("LOT")
            ws1['A5'] = "제조일자"; ws1['B5'] = kor_data.get("제조일자")
            ws1['D5'] = "시험일자"; ws1['E5'] = kor_data.get("시험일자")

            apply_style_to_range(ws1, 'A4:F5', border=thin_border)
            apply_style_to_range(ws1, 'A4:A5', font=label_font, fill=label_fill, alignment=center_align)
            apply_style_to_range(ws1, 'D4:D5', font=label_font, fill=label_fill, alignment=center_align)
            apply_style_to_range(ws1, 'B4:C5', font=cell_font, alignment=left_align)
            apply_style_to_range(ws1, 'E4:F5', font=cell_font, alignment=left_align)

            # --- 시험 항목 테이블 ---
            ws1.append([]) # 공백 행
            table_start_row = ws1.max_row + 1
            
            headers = ["구분", "시험항목", "시험기준", "시험결과", "비고"]
            ws1.append(headers)
            ws1.merge_cells(start_row=table_start_row, start_column=5, end_row=table_start_row, end_column=6)

            for col_idx in range(1, 7):
                cell = ws1.cell(row=table_start_row, column=col_idx)
                cell.font = header_font
                cell.fill = header_fill
                cell.alignment = center_align
                cell.border = thin_border

            test_items = [
                ("1", "성상", kor_data.get("기준_성상"), kor_data.get("결과_성상"), kor_data.get("판정_성상")),
                ("2", "향취", kor_data.get("기준_향취"), kor_data.get("결과_향취"), kor_data.get("판정_향취")),
                ("3", "사용감", kor_data.get("기준_사용감"), kor_data.get("결과_사용감"), kor_data.get("판정_사용감")),
                ("4", "pH (30℃)", kor_data.get("기준_pH(30℃)"), kor_data.get("결과_pH(30℃)"), kor_data.get("판정_pH")),
                ("5", "점도(30℃)", kor_data.get("기준_점도(30℃)"), kor_data.get("결과_점도(30℃)"), kor_data.get("판정_점도")),
                ("6", "비중(25℃)", kor_data.get("기준_비중(25℃)"), kor_data.get("결과_비중(25℃)"), kor_data.get("판정_비중")),
                ("7", "미생물(일반세균)", kor_data.get("기준_일반세균"), kor_data.get("결과_일반세균"), kor_data.get("판정_일반세균")),
                ("", "미생물(효모/곰팡이)", kor_data.get("기준_효모/곰팡이"), kor_data.get("결과_효모/곰팡이"), kor_data.get("판정_효모곰팡이")),
                ("", "미생물(대장균)", kor_data.get("기준_대장균"), kor_data.get("결과_대장균"), kor_data.get("판정_대장균")),
            ]
            
            for item in test_items:
                ws1.append(item)
                current_row = ws1.max_row
                ws1.merge_cells(start_row=current_row, start_column=5, end_row=current_row, end_column=6)
                apply_style_to_range(ws1, f'A{current_row}:F{current_row}', font=cell_font, border=thin_border, alignment=center_align)
                ws1[f'B{current_row}'].alignment = left_align
                ws1[f'C{current_row}'].alignment = left_align
                ws1[f'D{current_row}'].alignment = left_align

            ws1.merge_cells(f'A{table_start_row+7}:A{table_start_row+9}')
            ws1.merge_cells(f'B{table_start_row+7}:B{table_start_row+9}')

            # --- 종합판정 ---
            ws1.append([])
            ws1.append(["종합판정", kor_data.get("종합판정")])
            current_row = ws1.max_row
            ws1.merge_cells(start_row=current_row, start_column=2, end_row=current_row, end_column=6)
            apply_style_to_range(ws1, f'A{current_row}:F{current_row}', border=thin_border)
            ws1[f'A{current_row}'].font = label_font; ws1[f'A{current_row}'].fill = label_fill; ws1[f'A{current_row}'].alignment = center_align
            ws1[f'B{current_row}'].font = Font(name='맑은 고딕', size=10, bold=True); ws1[f'B{current_row}'].alignment = center_align

            # --- 시험자 ---
            ws1.append(["시험자", kor_data.get("시험자"), "", "시험일자", kor_data.get("일자")])
            current_row = ws1.max_row
            ws1.merge_cells(f'B{current_row}:C{current_row}'); ws1.merge_cells(f'E{current_row}:F{current_row}')
            apply_style_to_range(ws1, f'A{current_row}:F{current_row}', border=thin_border)
            apply_style_to_range(ws1, f'A{current_row}', font=label_font, fill=label_fill, alignment=center_align)
            apply_style_to_range(ws1, f'D{current_row}', font=label_font, fill=label_fill, alignment=center_align)
            apply_style_to_range(ws1, f'B{current_row}:C{current_row}', font=cell_font, alignment=center_align)
            apply_style_to_range(ws1, f'E{current_row}:F{current_row}', font=cell_font, alignment=center_align)

            # --- 열 너비 조정 ---
            ws1.column_dimensions['A'].width = 15
            ws1.column_dimensions['B'].width = 25
            ws1.column_dimensions['C'].width = 25
            ws1.column_dimensions['D'].width = 15
            ws1.column_dimensions['E'].width = 25
            ws1.column_dimensions['F'].width = 10

            # 영문 시트는 생략 (유사 로직)

            # --- 파일 저장 ---
            default_filename = f"{kor_data['제품명']}_{kor_data['LOT']}_시험성적서.xlsx"
            file_path = fd.asksaveasfilename(
                defaultextension=".xlsx",
                filetypes=[("Excel 통합 문서", "*.xlsx")],
                initialfile=default_filename,
                title=self.texts['save_report_as']
            )

            if file_path:
                wb.save(file_path)
                messagebox.showinfo(self.texts['success'], f"{self.texts['report_saved_success']}:\n{file_path}", parent=self)

        except Exception as e:
            messagebox.showerror(self.texts['error'], f"{self.texts['report_generation_error']}:\n{e}", parent=self)

    def setup_placeholder_tab(self, tab_frame, tab_name):
        """개발 예정인 탭의 플레이스홀더 UI를 설정합니다."""
        tab_frame.grid_columnconfigure(0, weight=1)
        tab_frame.grid_rowconfigure(0, weight=1)
        
        label = ctk.CTkLabel(tab_frame, text=f"{tab_name}\n{self.texts['dev_in_progress']}", font=ctk.CTkFont(size=20, weight="bold"))
        label.grid(row=0, column=0, padx=20, pady=20)

    def switch_to_tab(self, tab_name):
        """요청된 이름의 탭으로 화면을 전환합니다."""
        if tab_name in self.tab_view._name_list: # pylint: disable=protected-access
            self.tab_view.set(tab_name)

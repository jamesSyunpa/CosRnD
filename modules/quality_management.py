# modules/quality_management.py
import customtkinter as ctk
from tkinter import messagebox
from modules.progress_window import ProgressWindow
from openpyxl import Workbook
from openpyxl.styles import Font, Alignment, Border, Side, PatternFill
from openpyxl.utils import get_column_letter
import tkinter.filedialog as fd

from modules.translation import get_texts
from modules.finished_product_report import FinishedProductReportFrame
from modules.ingredient_report_frame_export import IngredientReportFrame_Export

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
            segmented_button_selected_hover_color=("#3671A8", "#144870"), # noqa
            command=self.on_main_tab_change,
            segmented_button_unselected_hover_color=("gray85", "gray28")
        )
        self.tab_view.grid(row=0, column=0, sticky="nsew", padx=10, pady=10)

        # --- 탭 추가 ---
        self.tab_view.add(self.texts.get('ingredient_report', '원료목록보고'))
        self.tab_view.add(self.texts['coa'])
        self.tab_view.add(self.texts['msds'])
        self.tab_view.add(self.texts['prod_standard'])
        self.tab_view.add(self.texts['mfg_record'])

        # 초기에는 프레임만 만들고, 탭 클릭 시 내용 생성
        self.tab_frames = {}
        for tab_name in self.tab_view._name_list: # pylint: disable=protected-access
            self.tab_frames[tab_name] = self.tab_view.tab(tab_name)
            self.tab_frames[tab_name].grid_columnconfigure(0, weight=1)
            self.tab_frames[tab_name].grid_rowconfigure(0, weight=1)

        # 첫 번째 탭의 UI는 메인 창이 완전히 나타난 후에 로드되도록 스케줄링합니다.
        self.after(100, self.on_main_tab_change)
        
    def on_main_tab_change(self, tab_name=None):
        """메인 탭이 변경될 때 해당 탭의 UI를 생성합니다."""
        selected_tab = self.tab_view.get()
        
        # 이미 내용이 생성되었으면 다시 생성하지 않음 (자식 위젯이 있는지 확인)
        if self.tab_frames[selected_tab].winfo_children():
            return

        if selected_tab == self.texts.get('ingredient_report', '원료목록보고'):
            self.setup_ingredient_report_tab(self.tab_frames[selected_tab])
        elif selected_tab == self.texts['coa']:
            self.setup_coa_tab(self.tab_frames[selected_tab])
        elif selected_tab == self.texts['msds']:
            self.setup_placeholder_tab(self.tab_frames[selected_tab], self.texts['msds'])
        elif selected_tab == self.texts['prod_standard']:
            self.setup_placeholder_tab(self.tab_frames[selected_tab], self.texts['prod_standard'])
        elif selected_tab == self.texts['mfg_record']:
            self.setup_placeholder_tab(self.tab_frames[selected_tab], self.texts['mfg_record'])

    def setup_coa_tab(self, tab_frame):
        """COA 탭의 UI를 설정합니다."""
        tab_frame.grid_columnconfigure(0, weight=1)
        tab_frame.grid_rowconfigure(0, weight=1)

        # --- COA 서브 탭 뷰 ---
        coa_sub_tab_view = ctk.CTkTabview(tab_frame, border_width=1, border_color=("gray80", "gray30"))
        coa_sub_tab_view.grid(row=0, column=0, padx=10, pady=10, sticky="nsew")

        coa_sub_tab_view.add(self.texts['semi_finished_product_report'])
        coa_sub_tab_view.add(self.texts['finished_product_report'])

        self.setup_semi_finished_product_tab(coa_sub_tab_view.tab(self.texts['semi_finished_product_report']))
        self.setup_finished_product_tab(coa_sub_tab_view.tab(self.texts['finished_product_report']))

    def setup_semi_finished_product_tab(self, tab_frame):
        """반제품 시험성적서 탭의 UI를 동적으로 행 추가/삭제가 가능하도록 재구성합니다."""
        tab_frame.grid_columnconfigure(0, weight=1)
        tab_frame.grid_rowconfigure(1, weight=1) # 테이블 프레임이 확장되도록 설정

        # --- 상단 정보 프레임 ---
        info_frame = ctk.CTkFrame(tab_frame, fg_color="transparent")
        info_frame.grid(row=0, column=0, sticky="ew", padx=10, pady=(10, 5)) # 상단 여백, 하단 여백 축소
        info_frame.grid_columnconfigure((1, 3), weight=1)

        self.semi_product_entries = {}

        # 기본 정보 섹션
        ctk.CTkLabel(info_frame, text="제 품 명", font=ctk.CTkFont(weight="bold")).grid(row=0, column=0, padx=10, pady=5, sticky="w")
        self.semi_product_entries["제품명"] = ctk.CTkEntry(info_frame)
        self.semi_product_entries["제품명"].grid(row=0, column=1, padx=10, pady=5, sticky="ew")
        
        ctk.CTkLabel(info_frame, text="LOT", font=ctk.CTkFont(weight="bold")).grid(row=0, column=2, padx=10, pady=5, sticky="w")
        self.semi_product_entries["LOT"] = ctk.CTkEntry(info_frame)
        self.semi_product_entries["LOT"].grid(row=0, column=3, padx=10, pady=5, sticky="ew")

        ctk.CTkLabel(info_frame, text="제조일자", font=ctk.CTkFont(weight="bold")).grid(row=1, column=0, padx=10, pady=5, sticky="w")
        self.semi_product_entries["제조일자"] = ctk.CTkEntry(info_frame)
        self.semi_product_entries["제조일자"].grid(row=1, column=1, padx=10, pady=5, sticky="ew")

        ctk.CTkLabel(info_frame, text="시험일자", font=ctk.CTkFont(weight="bold")).grid(row=1, column=2, padx=10, pady=5, sticky="w")
        self.semi_product_entries["시험일자"] = ctk.CTkEntry(info_frame)
        self.semi_product_entries["시험일자"].grid(row=1, column=3, padx=10, pady=5, sticky="ew")

        # --- 시험 항목 테이블을 담을 스크롤 프레임 ---
        self.table_scroll_frame = ctk.CTkScrollableFrame(tab_frame, label_text="내용 목록")
        self.table_scroll_frame.grid(row=1, column=0, sticky="nsew", padx=10, pady=0) # 여백 제거
        self.table_scroll_frame.grid_columnconfigure(1, weight=2) # 시험항목
        self.table_scroll_frame.grid_columnconfigure(2, weight=3) # 시험기준
        self.table_scroll_frame.grid_columnconfigure(3, weight=3) # 시험결과
        self.table_scroll_frame.grid_columnconfigure(4, weight=1) # 비고
        self.table_scroll_frame.grid_columnconfigure(5, weight=0) # 삭제

        # --- 테이블 헤더 ---
        headers = ["구분", "시험항목", "시험기준", "시험결과", "비고", "삭제"]
        for i, h in enumerate(headers):
            header_label = ctk.CTkLabel(self.table_scroll_frame, text=h, font=ctk.CTkFont(weight="bold"))
            header_label.grid(row=0, column=i, sticky="ew", padx=(1,0), pady=1)

        # --- 동적 행 데이터 및 위젯 관리 ---
        self.test_item_rows = []
        self._create_initial_rows()

        # --- 판정 정보 섹션 ---
        conclusion_frame = ctk.CTkFrame(tab_frame)
        conclusion_frame.grid(row=2, column=0, sticky="ew", padx=10, pady=10)
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
        bottom_button_frame = ctk.CTkFrame(tab_frame, fg_color="transparent")
        bottom_button_frame.grid(row=3, column=0, padx=10, pady=10, sticky="ew")
        
        ctk.CTkButton(bottom_button_frame, text="행 추가", command=self._add_row).pack(side="left", padx=5)
        
        # 오른쪽 정렬을 위한 프레임
        right_button_frame = ctk.CTkFrame(bottom_button_frame, fg_color="transparent")
        right_button_frame.pack(side="right")
        ctk.CTkButton(right_button_frame, text="엑셀 보고서 생성", command=self.generate_semi_product_report, fg_color="#3B8ED0").pack(side="left", padx=5)
        ctk.CTkButton(right_button_frame, text=self.texts['reset'], command=self.clear_semi_product_form, fg_color="gray50", hover_color="gray35").pack(side="left", padx=5)

    def _create_initial_rows(self):
        """초기 시험 항목 행들을 생성합니다."""
        initial_items = [
            {"id": "1", "item": "성상", "spec": "표준품과 일치", "result": "", "note": ""},
            {"id": "2", "item": "향취", "spec": "표준품과 일치", "result": "", "note": ""},
            {"id": "3", "item": "사용감", "spec": "표준품과 일치", "result": "", "note": ""},
            {"id": "4", "item": "pH (30℃)", "spec": "6.50 ± 1.00", "result": "", "note": ""},
            {"id": "5", "item": "점도(30℃)", "spec": "33,000 ± 5,000", "result": "", "note": ""},
            {"id": "6", "item": "비중(25℃)", "spec": "0.980 ± 0.02", "result": "", "note": ""},
            {"id": "7", "item": "미생물(일반세균)", "spec": "100 cfu/ml 이하", "result": "", "note": ""},
            {"id": "", "item": "미생물(효모/곰팡이)", "spec": "10 cfu/ml 이하", "result": "", "note": ""},
            {"id": "", "item": "미생물(대장균)", "spec": "불검출", "result": "", "note": ""},
        ]
        for item_data in initial_items:
            self._add_row(item_data, is_initial=True)

    def _add_row(self, data=None, is_initial=False):
        """테이블에 새로운 행을 추가합니다."""
        if data is None:
            data = {"id": "", "item": "", "spec": "", "result": "", "note": ""}

        row_index = len(self.test_item_rows) + 1
        
        row_widgets = {
            "id_label": ctk.CTkLabel(self.table_scroll_frame, text=data.get("id", ""))
        }

        # Entry 위젯 생성
        entry_keys = ["item", "spec", "result", "note"]
        for key in entry_keys:
            entry = ctk.CTkEntry(self.table_scroll_frame, corner_radius=0, border_width=0)
            entry.insert(0, data.get(key, ""))
            row_widgets[key + "_entry"] = entry

        # 삭제 버튼
        remove_button = ctk.CTkButton(self.table_scroll_frame, text="삭제", width=40, fg_color="gray50", hover_color="gray35",
                                        command=lambda r=row_widgets: self._remove_row(r))
        row_widgets["remove_button"] = remove_button
        
        self.test_item_rows.append(row_widgets)
        self._grid_row_widgets(row_widgets, row_index)
        if not is_initial:
            self._redraw_table()

    def _grid_row_widgets(self, row_widgets, row_index):
        """특정 행의 위젯들을 그리드에 배치합니다."""
        row_widgets["id_label"].grid(row=row_index, column=0, sticky="ew", padx=(1,0), pady=(1,0))
        row_widgets["item_entry"].grid(row=row_index, column=1, sticky="ew", padx=(1,0), pady=(1,0))
        row_widgets["spec_entry"].grid(row=row_index, column=2, sticky="ew", padx=(1,0), pady=(1,0))
        row_widgets["result_entry"].grid(row=row_index, column=3, sticky="ew", padx=(1,0), pady=(1,0))
        row_widgets["note_entry"].grid(row=row_index, column=4, sticky="ew", padx=(1,0), pady=(1,0))
        row_widgets["remove_button"].grid(row=row_index, column=5, padx=5, pady=1)

    def _remove_row(self, row_to_remove):
        """테이블에서 특정 행을 제거합니다."""
        for widget in row_to_remove.values():
            widget.destroy()
        self.test_item_rows.remove(row_to_remove)
        self._redraw_table()

    def _redraw_table(self):
        """행이 제거된 후 테이블 전체를 다시 그립니다."""
        for i, row_widgets in enumerate(self.test_item_rows, start=1):
            # Update the ID label before gridding
            row_widgets["id_label"].configure(text=str(i) if i <= 7 else "")
            self._grid_row_widgets(row_widgets, i)


    def clear_semi_product_form(self):
        """반제품 시험성적서 폼의 모든 입력 필드를 초기화하고 테이블을 기본값으로 되돌립니다."""
        # 기본 정보 초기화
        for entry in self.semi_product_entries.values():
            entry.delete(0, "end")
        
        # 테이블의 모든 동적 행 제거
        for row_widgets in self.test_item_rows[:]:
            for widget in row_widgets.values():
                widget.destroy()
        self.test_item_rows.clear()
            
        # 초기 행 다시 생성
        self._create_initial_rows()
        
        messagebox.showinfo(self.texts['notification'], self.texts['form_cleared'], parent=self)

    def setup_finished_product_tab(self, tab_frame):
        """완제품 시험성적서 탭의 UI를 설정합니다."""
        tab_frame.grid_columnconfigure(0, weight=1)
        tab_frame.grid_rowconfigure(0, weight=1)
        finished_product_frame = FinishedProductReportFrame(tab_frame)
        finished_product_frame.pack(expand=True, fill="both")

    def setup_ingredient_report_tab(self, tab_frame):
        """원료목록보고 탭의 UI를 설정합니다."""
        tab_frame.grid_columnconfigure(0, weight=1)
        tab_frame.grid_rowconfigure(0, weight=1)
        ingredient_report_frame = IngredientReportFrame_Export(tab_frame)
        ingredient_report_frame.pack(expand=True, fill="both")
        return ingredient_report_frame

    def generate_semi_product_report(self):
        """입력된 데이터를 기반으로 깔끔한 서식의 반제품 시험성적서 엑셀 파일을 생성합니다."""
        from openpyxl.styles import Font, Alignment, Border, Side, PatternFill

        try:
            # --- 데이터 수집 ---
            kor_data = {key: entry.get() for key, entry in self.semi_product_entries.items()}
            
            if not all(kor_data.get(key) for key in ["제품명", "LOT", "종합판정"]):
                messagebox.showwarning(self.texts['input_error'], self.texts['required_fields_missing'], parent=self)
                return

            # --- 동적 테이블에서 데이터 수집 ---
            test_items = []
            for row_widgets in self.test_item_rows:
                item_id = row_widgets["id_label"].cget("text")
                item = row_widgets["item_entry"].get()
                spec = row_widgets["spec_entry"].get()
                result = row_widgets["result_entry"].get()
                note = row_widgets["note_entry"].get()
                test_items.append((item_id, item, spec, result, note))

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

            # 동적으로 수집한 데이터 사용
            for item in test_items:
                ws1.append(item)
                current_row = ws1.max_row
                ws1.merge_cells(start_row=current_row, start_column=5, end_row=current_row, end_column=6)
                apply_style_to_range(ws1, f'A{current_row}:F{current_row}', font=cell_font, border=thin_border, alignment=center_align)
                ws1[f'B{current_row}'].alignment = left_align
                ws1[f'C{current_row}'].alignment = left_align
                ws1[f'D{current_row}'].alignment = left_align

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

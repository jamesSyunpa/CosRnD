# modules/quality_management.py
import customtkinter as ctk
from tkinter import messagebox
from openpyxl import Workbook
from openpyxl.styles import Font, Alignment, Border, Side
from openpyxl.utils import get_column_letter
import tkinter.filedialog as fd

from modules.translation import get_texts

class QualityManagementFrame(ctk.CTkFrame):
    """품질 관리 관련 기능을 포함하는 프레임"""
    def __init__(self, master, user, app, language="korean"):
        super().__init__(master)
        self.current_user = user
        self.app = app
        self.language = language
        self.texts = get_texts(language)

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
        self.tab_view.add(self.texts['coa'])
        self.tab_view.add(self.texts['msds'])
        self.tab_view.add(self.texts['prod_standard'])
        self.tab_view.add(self.texts['mfg_record'])

        # --- 각 탭 UI 설정 ---
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
        """반제품 시험성적서 탭의 UI를 설정합니다."""
        tab_frame.grid_columnconfigure(0, weight=1)
        tab_frame.grid_rowconfigure(0, weight=1)

        scrollable_frame = ctk.CTkScrollableFrame(tab_frame, label_text=self.texts['semi_finished_product_report_title'])
        scrollable_frame.grid(row=0, column=0, sticky="nsew", padx=10, pady=10)
        scrollable_frame.grid_columnconfigure(1, weight=1)

        self.semi_product_entries = {}
        fields = self.texts['semi_product_coa_fields']

        for i, (key, label_text) in enumerate(fields.items()):
            ctk.CTkLabel(scrollable_frame, text=label_text).grid(row=i, column=0, padx=10, pady=5, sticky="w")
            entry = ctk.CTkEntry(scrollable_frame)
            entry.grid(row=i, column=1, padx=10, pady=5, sticky="ew")
            self.semi_product_entries[key] = entry

        # --- 하단 버튼 프레임 ---
        button_frame = ctk.CTkFrame(tab_frame)
        button_frame.grid(row=1, column=0, padx=10, pady=10, sticky="e")

        ctk.CTkButton(button_frame, text=self.texts['create_excel_report'], command=self.generate_semi_product_report).pack(side="left", padx=5)
        ctk.CTkButton(button_frame, text=self.texts['reset'], command=self.clear_semi_product_form, fg_color="gray50", hover_color="gray35").pack(side="left", padx=5)

    def clear_semi_product_form(self):
        """반제품 시험성적서 폼의 모든 입력 필드를 초기화합니다."""
        for entry in self.semi_product_entries.values():
            entry.delete(0, "end")
        messagebox.showinfo(self.texts['notification'], self.texts['form_cleared'], parent=self)

    def generate_semi_product_report(self):
        """입력된 데이터를 기반으로 반제품 시험성적서 엑셀 파일을 생성합니다."""
        try:
            # --- 데이터 수집 ---
            kor_data = {key: entry.get() for key, entry in self.semi_product_entries.items()}
            
            # 필수 입력 필드 검사
            if not all(kor_data.get(key) for key in ["제품명", "LOT", "판정"]):
                messagebox.showwarning(self.texts['input_error'], self.texts['required_fields_missing'], parent=self)
                return

            # 영문 데이터는 한글 데이터를 기반으로 생성 (필요시 수정)
            eng_data = {
                "Product Name": kor_data.get("제품명"), "Product Code": kor_data.get("제품코드명"),
                "Lot No.": kor_data.get("LOT"), "Manufacturing Date": kor_data.get("제조일자"),
                "Testing Date": kor_data.get("시험일자"), "Appearance": "Cream", "Color": "Milky White",
                "Odor": "Corresponds with standard sample", "pH (30℃)": kor_data.get("pH(30℃)"),
                "Viscosity (30℃)": f'{kor_data.get("점도(30℃)")} (LV, 12rpm, Spindle-4, 1min)',
                "Relative Density (25℃)": kor_data.get("비중(25℃)"),
                "Microbial test": f'Total Bacteria ≤{kor_data.get("일반세균")}, Yeast&Mold ≤{kor_data.get("효모/곰팡이")}, E.Coli {kor_data.get("대장균")}',
                "Analyst": kor_data.get("시험자"), "Date": kor_data.get("일자"),
                "Conclusion": "PASS" if kor_data.get("판정") == "적합" else "FAIL"
            }

            # --- Excel 서식 생성 ---
            wb = Workbook()
            bold = Font(bold=True)
            center = Alignment(horizontal="center", vertical="center", wrap_text=True)
            thin = Side(style="thin")
            border = Border(top=thin, bottom=thin, left=thin, right=thin)

            # === [1] 한글 시험성적서 ===
            ws1 = wb.active
            ws1.title = "반제품 시험성적서"

            ws1.merge_cells("A1:E1")
            ws1.merge_cells("A1:G1")
            ws1["A1"] = "반제품 시험성적서"
            ws1["A1"].font = Font(size=14, bold=True)
            ws1["A1"].alignment = center

            ws1.append(["제 품 명", kor_data["제품명"], "제품코드명", kor_data["제품코드명"], "LOT", kor_data["LOT"]])
            ws1.append(["반제품 제조일", kor_data["제조일자"], "시험 일자", kor_data["시험일자"], "", ""])
            # --- 기본 정보 (양식에 맞게 재구성) ---
            ws1.merge_cells("B2:C2"); ws1.merge_cells("E2:G2")
            ws1.append(["제 품 명", kor_data["제품명"], "", "제품코드명", kor_data["제품코드명"], "LOT", kor_data["LOT"]])
            ws1.merge_cells("B3:C3"); ws1.merge_cells("E3:G3")
            ws1.append(["반제품 제조일", kor_data["제조일자"], "", "시험 일자", kor_data["시험일자"], "", ""])

            rows = [
                ["구분", "시험항목", "시험기준", "시험결과", "비고"],
                ["1", "성상", "표준품과 일치", kor_data["성상"], kor_data["판정"]],
                ["2", "향취", "표준품과 일치", kor_data["향취"], kor_data["판정"]],
                ["3", "사용감", "표준품과 일치", kor_data["사용감"], kor_data["판정"]],
                ["4", "pH (30℃)", "6.50 ± 1.00", kor_data["pH(30℃)"], kor_data["판정"]],
                ["5", "점도(30℃)", "33,000 ± 5,000", kor_data["점도(30℃)"], kor_data["판정"]],
                ["6", "비중(25℃)", "0.980 ± 0.02", kor_data["비중(25℃)"], kor_data["판정"]],
                ["7", "일반세균", "100cfu/ml 이하", kor_data["일반세균"], kor_data["판정"]],
                ["8", "효모/곰팡이", "10cfu/ml 이하", kor_data["효모/곰팡이"], kor_data["판정"]],
                ["9", "대장균", "불검출", kor_data["대장균"], kor_data["판정"]],
                ["구분", "시험항목", "시험기준", "시험결과", "비고", "", ""],
                ["1", "성상", "표준품과 일치", kor_data["성상"], kor_data["판정"], "", ""],
                ["2", "향취", "표준품과 일치", kor_data["향취"], kor_data["판정"], "", ""],
                ["3", "사용감", "표준품과 일치", kor_data["사용감"], kor_data["판정"], "", ""],
                ["4", "pH (30℃)", "6.50 ± 1.00", kor_data["pH(30℃)"], kor_data["판정"], "", ""],
                ["5", "점도(30℃)", "33,000 ± 5,000", kor_data["점도(30℃)"], kor_data["판정"], "", ""],
                ["6", "비중(25℃)", "0.980 ± 0.02", kor_data["비중(25℃)"], kor_data["판정"], "", ""],
                ["7", "일반세균", "100cfu/ml 이하", kor_data["일반세균"], kor_data["판정"], "", ""],
                ["8", "효모/곰팡이", "10cfu/ml 이하", kor_data["효모/곰팡이"], kor_data["판정"], "", ""],
                ["9", "대장균", "불검출", kor_data["대장균"], kor_data["판정"], "", ""],
            ]
            for r in rows: ws1.append(r)

            ws1.append(["시험자", kor_data["시험자"], "일자", kor_data["일자"], "종합판정", kor_data["판정"]])
            # --- 판정 정보 (양식에 맞게 재구성) ---
            ws1.merge_cells("B15:C15"); ws1.merge_cells("E15:G15")
            ws1.append(["시험자", kor_data["시험자"], "", "일자", kor_data["일자"], "", ""])
            ws1.merge_cells("B16:C16"); ws1.merge_cells("E16:G16")
            ws1.append(["종합판정", kor_data["판정"], "", "", "", "", ""])

            for row in ws1.iter_rows():
            # --- 서식 적용 ---
            # 전체 셀에 기본 서식 적용
            for row in ws1.iter_rows(min_row=1, max_row=ws1.max_row, min_col=1, max_col=7):
                for cell in row:
                    cell.border = border
                    cell.alignment = center
            
            # 특정 셀 서식 재정의
            for row_idx in [2, 3, 15, 16]:
                ws1[f'B{row_idx}'].alignment = Alignment(horizontal="left", vertical="center", indent=1)
                ws1[f'E{row_idx}'].alignment = Alignment(horizontal="left", vertical="center", indent=1)
            for row_idx in range(5, 15):
                ws1[f'D{row_idx}'].alignment = Alignment(horizontal="left", vertical="center", indent=1)

            # 컬럼 너비 자동 조절
            for col in ws1.columns:
                max_length = 0
                column = col[0].column_letter
                for cell in col:
                    try:
                        if len(str(cell.value)) > max_length:
                            max_length = len(str(cell.value))
                    except: pass
                adjusted_width = (max_length + 2) * 1.2
                ws1.column_dimensions[column].width = adjusted_width

            # === [2] 영어 COA 시트 ===
            ws2 = wb.create_sheet("COA (EN)")
            ws2.merge_cells("A1:E1")
            ws2.merge_cells("A1:G1")
            ws2["A1"] = "Certificate of Analysis"
            ws2["A1"].font = Font(size=14, bold=True)
            ws2["A1"].alignment = center

            ws2.append(["Product Name", eng_data["Product Name"], "Product Code", eng_data["Product Code"], "Lot No.", eng_data["Lot No."]])
            ws2.append(["Manufacturing Date", eng_data["Manufacturing Date"], "Testing Date", eng_data["Testing Date"], "", ""])
            ws2.merge_cells("B2:C2"); ws2.merge_cells("E2:G2")
            ws2.append(["Product Name", eng_data["Product Name"], "", "Product Code", eng_data["Product Code"], "Lot No.", eng_data["Lot No."]])
            ws2.merge_cells("B3:C3"); ws2.merge_cells("E3:G3")
            ws2.append(["Manufacturing Date", eng_data["Manufacturing Date"], "", "Testing Date", eng_data["Testing Date"], "", ""])

            rows_en = [
                ["Field", "Specification", "Result", "Method", "Conclusion"],
                ["Appearance", "Cream", eng_data["Appearance"], "Sensory", "Pass"],
                ["Color", "Milky White", eng_data["Color"], "Sensory", "Pass"],
                ["Odor", "Corresponds with Std.", eng_data["Odor"], "Sensory", "Pass"],
                ["pH (30℃)", "6.50 ± 1.00", eng_data["pH (30℃)"], "pH Meter", "Pass"],
                ["Viscosity (30℃)", "33,000 ± 5,000", eng_data["Viscosity (30℃)"], "Brookfield", "Pass"],
                ["Relative Density (25℃)", "0.980 ± 0.02", eng_data["Relative Density (25℃)"], "Pycnometer", "Pass"],
                ["Microbial test", "Total Bacteria: ≤100cfu/ml\nYeast&Mold: ≤10cfu/ml\nE.Coli: Absent", eng_data["Microbial test"], "3M™ Petrifilm", "Pass"],
            ]
            for r in rows_en: ws2.append(r)
            
            ws2.append(["Analyst", eng_data["Analyst"], "", "Date", eng_data["Date"]])
            ws2.append(["Conclusion", eng_data["Conclusion"], "", "", ""])

            for row in ws2.iter_rows():
            # --- 판정 정보 (양식에 맞게 재구성) ---
            ws2.merge_cells("B13:C13"); ws2.merge_cells("E13:G13")
            ws2.append(["Analyst", eng_data["Analyst"], "", "Date", eng_data["Date"], "", ""])
            ws2.merge_cells("B14:C14"); ws2.merge_cells("E14:G14")
            ws2.append(["Conclusion", eng_data["Conclusion"], "", "", "", "", ""])

            # --- 서식 적용 ---
            for row in ws2.iter_rows(min_row=1, max_row=ws2.max_row, min_col=1, max_col=7):
                for cell in row:
                    cell.border = border
                    cell.alignment = center
            
            for row_idx in [2, 3, 13, 14]:
                ws2[f'B{row_idx}'].alignment = Alignment(horizontal="left", vertical="center", indent=1)
                ws2[f'E{row_idx}'].alignment = Alignment(horizontal="left", vertical="center", indent=1)
            
            # 컬럼 너비 자동 조절
            for col in ws2.columns:
                max_length = 0
                column = col[0].column_letter
                for cell in col:
                    try:
                        if len(str(cell.value)) > max_length:
                            max_length = len(str(cell.value))
                    except: pass
                adjusted_width = (max_length + 2) * 1.2
                ws2.column_dimensions[column].width = adjusted_width

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
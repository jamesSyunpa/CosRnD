# modules/quality_management.py
import customtkinter as ctk
from tkinter import messagebox
from openpyxl import Workbook
from openpyxl.styles import Font, Alignment, Border, Side, PatternFill
from openpyxl.utils import get_column_letter
import tkinter.filedialog as fd
from modules import excel_handler

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
            segmented_button_selected_color=('#3B8ED0', '#1F6AA5'),
            segmented_button_unselected_color=("gray92", "gray20"),
            text_color=("black", "white"),
            segmented_button_selected_hover_color=('#3671A8', '#144870'),
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
        self.setup_ingredient_report_tab(self.tab_view.tab(self.texts['ingredient_report']))
        self.setup_coa_tab(self.tab_view.tab(self.texts['coa']))
        self.setup_placeholder_tab(self.tab_view.tab(self.texts['msds']), self.texts['msds'])
        self.setup_placeholder_tab(self.tab_view.tab(self.texts['prod_standard']), self.texts['prod_standard'])
        self.setup_placeholder_tab(self.tab_view.tab(self.texts['mfg_record']), self.texts['mfg_record'])

    def setup_ingredient_report_tab(self, tab_frame):
        """원료목록보고 탭의 UI를 설정합니다."""
        self.cosmetic_type_map = {
            "가": {"name": "만 3세 이하 영유아용 제품류", "items": {"가1": "영유아용 샴푸, 린스", "가2": "영유아용 로션, 크림", "가3": "영유아용 오일", "가4": "영유아용 인체 세정용 제품", "가5": "영유아용 목욕용 제품"}},
            "나": {"name": "목욕용 제품류", "items": {"나1": "목욕용 오일·정제·캡슐", "나2": "목욕용 소금류", "나3": "버블 배스", "나4": "그 밖의 목욕용 제품류"}},
            "다": {"name": "인체 세정용 제품류", "items": {"다1": "폼 클렌저", "다2": "바디 클렌저", "다3": "액체비누", "다3-1": "화장비누(고체형)", "다4": "외음부 세정제", "다5": "물휴지", "다6": "그 밖의 인체 세정용 제품류"}},
            "라": {"name": "눈화장용 제품류", "items": {"라1": "아이브로 제품", "라2": "아이라이너", "라3": "아이섀도", "라4": "마스카라", "라5": "아이 메이크업 리무버", "라6": "그 밖의 눈화장용 제품류"}},
            "마": {"name": "방향용 제품류", "items": {"마1": "향수", "마4": "코롱", "마5": "그 밖의 방향용 제품류"}},
            "바": {"name": "두발 염색용 제품류", "items": {"바1": "헤어 틴트", "바2": "헤어 칼라 스프레이", "바3": "그 밖의 염모용 제품류", "바4": "염모제", "바5": "탈염·탈색용 제품"}},
            "사": {"name": "색조 화장용 제품류", "items": {"사1": "볼연지", "사2": "페이스 파우더", "사3": "리퀴드·크림·케익 파운데이션", "사4": "메이크업 베이스", "사5": "메이크업 픽서티브", "사6": "립스틱·립라이너", "사7": "립글로스·립밤", "사8": "바디·페이스 페인팅·분장용 제품", "사9": "그 밖의 색조화장용 제품류"}},
            "아": {"name": "두발용 제품류", "items": {"아1": "헤어컨디셔너·트리트먼트·팩", "아2": "헤어토닉·헤어에센스", "아3": "헤어그루밍에이드", "아4": "헤어크림·로션", "아5": "헤어오일", "아6": "포마드", "아7": "헤어스프레이·무스·왁스·젤", "아8": "샴푸", "아9": "퍼머넌트 웨이브", "아10": "헤어스트레이트너", "아11": "그 밖의 두발용 제품류", "아12": "흑채"}},
            "자": {"name": "손발톱용 제품류", "items": {"자1": "베이스코트·언더코트", "자2": "네일폴리시·네일에나멜", "자3": "탑코트", "자4": "네일크림·로션·에센스·오일", "자5": "네일폴리시·네일에나멜 리무버", "자6": "그 밖의 손발톱용 제품류"}},
            "차": {"name": "면도용 제품류", "items": {"차1": "애프터셰이브 로션", "차3": "프리셰이브 로션", "차4": "세이빙 크림", "차5": "세이빙 폼", "차6": "그 밖의 면도용 제품류"}},
            "카": {"name": "기초화장용 제품류", "items": {"카1": "수렴·유연·영양화장수", "카2": "마사지 크림", "카3": "에센스·오일", "카4": "파우더", "카5": "바디 제품", "카6": "팩·마스크", "카7": "눈 주위 제품", "카8": "로션·크림", "카9": "손·발의 피부연화 제품", "카10": "클렌징워터·오일·로션·크림", "카11": "그 밖의 기초화장용 제품류"}},
            "타": {"name": "체취방지용 제품류", "items": {"타1": "데오도런트", "타2": "그 밖의 체취방지용 제품류"}},
            "파": {"name": "체모 제거용 제품류", "items": {"파1": "제모제", "파2": "그 밖의 체모 제거용 제품류", "파3": "제모 왁스"}},
        }
        self.functional_types = {
            "F1": "미백", "F2": "주름개선", "F3": "자외선차단", "F4": "미백+주름개선",
            "F5": "미백+자외선차단", "F6": "주름개선+자외선차단", "F7": "미백+주름개선+자외선차단",
            "F8": "염모/탈염/탈색", "F9": "체모 제모", "F10": "탈모증상 완화",
            "F11": "여드름성 피부 완화", "F12": "피부 장벽 기능 회복", "F13": "튼살로 인한 붉은 선 완화",
            "F14": "기타 복합유형"
        }

        tab_frame.grid_columnconfigure(0, weight=1)
        tab_frame.grid_rowconfigure(0, weight=1)

        scrollable_frame = ctk.CTkScrollableFrame(tab_frame, label_text="화장품 원료목록 보고서")
        scrollable_frame.grid(row=0, column=0, sticky="nsew", padx=10, pady=10)
        scrollable_frame.grid_columnconfigure(0, weight=1)

        self.report_entries = {}
        self.report_item_rows = []

        info_frame = ctk.CTkFrame(scrollable_frame)
        info_frame.grid(row=0, column=0, sticky="ew", padx=10, pady=(10, 20))
        info_frame.grid_columnconfigure((1, 3), weight=1)

        ctk.CTkLabel(info_frame, text="제품명", font=ctk.CTkFont(weight="bold")).grid(row=0, column=0, padx=10, pady=5, sticky="w")
        self.report_entries["제품명"] = ctk.CTkEntry(info_frame)
        self.report_entries["제품명"].grid(row=0, column=1, columnspan=3, padx=10, pady=5, sticky="ew")

        ctk.CTkLabel(info_frame, text="제조업자상호", font=ctk.CTkFont(weight="bold")).grid(row=1, column=0, padx=10, pady=5, sticky="w")
        self.report_entries["제조업자상호"] = ctk.CTkEntry(info_frame)
        self.report_entries["제조업자상호"].grid(row=1, column=1, columnspan=3, padx=10, pady=5, sticky="ew")

        ctk.CTkLabel(info_frame, text="유형표시", font=ctk.CTkFont(weight="bold")).grid(row=2, column=0, padx=10, pady=5, sticky="w")
        category_main_options = [f"{k} : {v['name']}" for k, v in self.cosmetic_type_map.items()]
        self.report_entries["유형표시_대분류"] = ctk.CTkComboBox(info_frame, values=category_main_options, command=self._update_subcategory_combo, width=250)
        self.report_entries["유형표시_대분류"].grid(row=2, column=1, padx=10, pady=5, sticky="ew")
        
        self.report_entries["유형표시"] = ctk.CTkComboBox(info_frame, values=[], width=250)
        self.report_entries["유형표시"].grid(row=2, column=3, padx=10, pady=5, sticky="ew")
        self._update_subcategory_combo(category_main_options[0])

        ctk.CTkLabel(info_frame, text="기능성화장품유형", font=ctk.CTkFont(weight="bold")).grid(row=3, column=0, padx=10, pady=5, sticky="w")
        self.report_entries["기능성화장품유형"] = ctk.CTkComboBox(info_frame, values=[f"{k} : {v}" for k, v in self.functional_types.items()], width=250)
        self.report_entries["기능성화장품유형"].grid(row=3, column=1, padx=10, pady=5, sticky="ew")

        ctk.CTkLabel(info_frame, text="기능성화장품품목코드", font=ctk.CTkFont(weight="bold")).grid(row=3, column=2, padx=10, pady=5, sticky="w")
        self.report_entries["기능성화장품품목코드"] = ctk.CTkEntry(info_frame)
        self.report_entries["기능성화장품품목코드"].grid(row=3, column=3, padx=10, pady=5, sticky="ew")

        self.report_table_frame = ctk.CTkFrame(scrollable_frame)
        self.report_table_frame.grid(row=1, column=0, sticky="ew", padx=10, pady=10)
        self.report_table_frame.grid_columnconfigure(2, weight=2) # 원료성분명
        self.report_table_frame.grid_columnconfigure(3, weight=1)
        self.report_table_frame.grid_columnconfigure(4, weight=1)

        table_controls_frame = ctk.CTkFrame(scrollable_frame)
        table_controls_frame.grid(row=2, column=0, sticky="w", padx=10, pady=(0, 10))
        ctk.CTkButton(table_controls_frame, text="항목 추가", command=self._add_report_item_row).pack(side="left")
        ctk.CTkButton(table_controls_frame, text="선택 항목 제거", command=self._remove_selected_report_item_row).pack(side="left", padx=10)

        button_frame = ctk.CTkFrame(tab_frame, fg_color="transparent")
        button_frame.grid(row=1, column=0, padx=10, pady=10, sticky="e")
        ctk.CTkButton(button_frame, text="엑셀 보고서 생성", command=self.generate_ingredient_report).pack(side="left", padx=5)
        ctk.CTkButton(button_frame, text="초기화", command=self.clear_ingredient_report_form, fg_color="gray50", hover_color="gray35").pack(side="left", padx=5)

        self._redraw_report_table()

    def _update_subcategory_combo(self, selected_main_category):
        main_code = selected_main_category.split(" : ")[0]
        sub_items = self.cosmetic_type_map.get(main_code, {}).get("items", {})
        sub_options = [f"{k} : {v}" for k, v in sub_items.items()]
        self.report_entries["유형표시"].configure(values=sub_options)
        if sub_options:
            self.report_entries["유형표시"].set(sub_options[0])
        else:
            self.report_entries["유형표시"].set("")

    def _redraw_report_table(self):
        for row_widgets in self.report_item_rows:
            for widget in row_widgets.values():
                widget.destroy()
        self.report_item_rows.clear()

        headers = ["", "일련번호", "원료성분명", "용도(E:수출용)", "맞춤형내용물(C1:혼합용/C2:소분용)"]
        for i, h in enumerate(headers):
            header_label = ctk.CTkLabel(self.report_table_frame, text=h, font=ctk.CTkFont(weight="bold"), fg_color=("gray85", "gray20"), corner_radius=0)
            header_label.grid(row=0, column=i, sticky="ew", padx=(1,0), pady=(1,0))
        
        for _ in range(5): # Add 5 initial empty rows
            self._add_report_item_row(redraw=False)

    def _add_report_item_row(self, item_data=None, redraw=True):
        if item_data is None:
            item_data = {'num': str(len(self.report_item_rows) + 1), 'name': "", 'use': "", 'custom': ""}

        row_index = len(self.report_item_rows) + 1
        widgets = {'selected': ctk.BooleanVar()}
        
        chk = ctk.CTkCheckBox(self.report_table_frame, text="", variable=widgets['selected'])
        chk.grid(row=row_index, column=0, sticky="ew", padx=2)
        widgets['chk'] = chk

        widgets['num_label'] = ctk.CTkLabel(self.report_table_frame, text=item_data['num'])
        widgets['num_label'].grid(row=row_index, column=1, sticky="ew")

        widgets['name'] = ctk.CTkEntry(self.report_table_frame, corner_radius=0, border_width=0)
        widgets['name'].insert(0, item_data['name'])
        widgets['name'].grid(row=row_index, column=2, sticky="ew", padx=(1,0), pady=(1,0))

        widgets['use'] = ctk.CTkEntry(self.report_table_frame, corner_radius=0, border_width=0)
        widgets['use'].insert(0, item_data['use'])
        widgets['use'].grid(row=row_index, column=3, sticky="ew", padx=(1,0), pady=(1,0))

        widgets['custom'] = ctk.CTkEntry(self.report_table_frame, corner_radius=0, border_width=0)
        widgets['custom'].insert(0, item_data['custom'])
        widgets['custom'].grid(row=row_index, column=4, sticky="ew", padx=(1,0), pady=(1,0))
        
        self.report_item_rows.append(widgets)
        if redraw:
            self._update_row_numbers()

    def _remove_selected_report_item_row(self):
        selected_rows = [i for i, row in enumerate(self.report_item_rows) if row['selected'].get()]
        if not selected_rows:
            messagebox.showwarning("선택 오류", "삭제할 항목을 선택하세요.", parent=self)
            return

        for i in sorted(selected_rows, reverse=True):
            for widget in self.report_item_rows[i].values():
                if isinstance(widget, (ctk.CTkEntry, ctk.CTkLabel, ctk.CTkCheckBox)):
                    widget.destroy()
            del self.report_item_rows[i]
        self._update_row_numbers()

    def _update_row_numbers(self):
        for i, row_widgets in enumerate(self.report_item_rows):
            row_widgets['num_label'].configure(text=str(i + 1))

    def clear_ingredient_report_form(self):
        for entry in self.report_entries.values():
            if isinstance(entry, ctk.CTkComboBox):
                entry.set(entry.cget("values")[0])
            else:
                entry.delete(0, "end")
        self._redraw_report_table()
        messagebox.showinfo("알림", "폼이 초기화되었습니다.", parent=self)

    def generate_ingredient_report(self):
        report_data = {key: widget.get() for key, widget in self.report_entries.items() if key not in ["유형표시_대분류"]}
        
        # UI에 표시된 "코드 : 설명" 형식에서 코드만 추출하여 저장
        type_full_str = report_data.get("유형표시", "")
        report_data["유형표시"] = type_full_str.split(" : ")[0]
        
        func_full_str = report_data.get("기능성화장품유형", "")
        report_data["기능성화장품유형"] = func_full_str.split(" : ")[0]

        items = []
        for row_widgets in self.report_item_rows:
            name = row_widgets['name'].get()
            if name:
                items.append({
                    "일련번호": row_widgets['num_label'].cget("text"),
                    "원료성분명": name,
                    "용도(E:수출용)": row_widgets['use'].get(),
                    "맞춤형내용물(C1:혼합용/C2:소분용)": row_widgets['custom'].get()
                })
        report_data['items'] = items
        
        excel_handler.export_ingredient_report(report_data)

    def setup_coa_tab(self, tab_frame):
        """COA 탭의 UI를 설정합니다."""
        tab_frame.grid_columnconfigure(0, weight=1)
        tab_frame.grid_rowconfigure(0, weight=1)

        coa_sub_tab_view = ctk.CTkTabview(tab_frame, border_width=1, border_color=("gray80", "gray30"))
        coa_sub_tab_view.grid(row=0, column=0, padx=10, pady=10, sticky="nsew")

        coa_sub_tab_view.add(self.texts['semi_finished_product_report'])
        self.setup_semi_finished_product_tab(coa_sub_tab_view.tab(self.texts['semi_finished_product_report']))

    def setup_semi_finished_product_tab(self, tab_frame):
        """반제품 시험성적서 탭의 UI를 동적으로 재구성합니다."""
        tab_frame.grid_columnconfigure(0, weight=1)
        tab_frame.grid_rowconfigure(0, weight=1)

        scrollable_frame = ctk.CTkScrollableFrame(tab_frame, label_text=self.texts['semi_finished_product_report_title'])
        scrollable_frame.grid(row=0, column=0, sticky="nsew", padx=10, pady=10)
        scrollable_frame.grid_columnconfigure(0, weight=1)

        self.semi_product_entries = {}
        self.coa_item_rows = [] 

        info_frame = ctk.CTkFrame(scrollable_frame)
        info_frame.grid(row=0, column=0, sticky="ew", padx=10, pady=(10, 20))
        info_frame.grid_columnconfigure((1, 3), weight=1)

        info_fields = [("제 품 명", 0, 0), ("LOT", 0, 2), ("제조일자", 1, 0), ("시험일자", 1, 2)]
        for label, r, c in info_fields:
            ctk.CTkLabel(info_frame, text=label, font=ctk.CTkFont(weight="bold")).grid(row=r, column=c, padx=10, pady=5, sticky="w")
            entry = ctk.CTkEntry(info_frame)
            entry.grid(row=r, column=c+1, padx=10, pady=5, sticky="ew")
            self.semi_product_entries[label] = entry

        self.table_frame = ctk.CTkFrame(scrollable_frame)
        self.table_frame.grid(row=1, column=0, sticky="ew", padx=10, pady=10)
        self.table_frame.grid_columnconfigure(2, weight=2) 
        self.table_frame.grid_columnconfigure(3, weight=3) 
        self.table_frame.grid_columnconfigure(4, weight=3) 
        self.table_frame.grid_columnconfigure(5, weight=1) 

        self.table_controls_frame = ctk.CTkFrame(scrollable_frame)
        self.table_controls_frame.grid(row=2, column=0, sticky="w", padx=10, pady=(0, 10))
        ctk.CTkButton(self.table_controls_frame, text="시험항목 추가", command=self._add_coa_item_row).pack(side="left")
        ctk.CTkButton(self.table_controls_frame, text="선택 항목 제거", command=self._remove_selected_coa_item_row).pack(side="left", padx=10)

        conclusion_frame = ctk.CTkFrame(scrollable_frame)
        conclusion_frame.grid(row=3, column=0, sticky="ew", padx=10, pady=(20, 10))
        conclusion_frame.grid_columnconfigure((1, 3, 5), weight=1)

        conclusion_fields = [("시험자", 0, 0), ("일자", 0, 2), ("종합판정", 0, 4)]
        for label, r, c in conclusion_fields:
            ctk.CTkLabel(conclusion_frame, text=label, font=ctk.CTkFont(weight="bold")).grid(row=r, column=c, padx=10, pady=5, sticky="w")
            entry = ctk.CTkEntry(conclusion_frame)
            entry.grid(row=r, column=c+1, padx=10, pady=5, sticky="ew")
            self.semi_product_entries[label] = entry

        button_frame = ctk.CTkFrame(tab_frame, fg_color="transparent")
        button_frame.grid(row=1, column=0, padx=10, pady=10, sticky="e")

        ctk.CTkButton(button_frame, text=self.texts['create_excel_report'], command=self.generate_semi_product_report).pack(side="left", padx=5)
        ctk.CTkButton(button_frame, text=self.texts['reset'], command=self.clear_semi_product_form, fg_color="gray50", hover_color="gray35").pack(side="left", padx=5)

        self._redraw_coa_table()

    def _redraw_coa_table(self, initial_items=None):
        for row_widgets in self.coa_item_rows:
            for widget in row_widgets.values():
                if isinstance(widget, (ctk.CTkEntry, ctk.CTkLabel, ctk.CTkCheckBox)):
                    widget.destroy()
        self.coa_item_rows.clear()

        headers = ["", "구분", "시험항목", "시험기준", "시험결과", "비고"]
        for i, h in enumerate(headers):
            header_label = ctk.CTkLabel(self.table_frame, text=h, font=ctk.CTkFont(weight="bold"), fg_color=("gray85", "gray20"), corner_radius=0)
            header_label.grid(row=0, column=i, sticky="ew", padx=(1,0), pady=(1,0))

        if initial_items:
            for item in initial_items:
                self._add_coa_item_row(item_data=item, redraw=False)
        elif not self.coa_item_rows: 
            initial_data = [
                {'num': "1", 'name': "성상", 'criteria': "표준품과 일치", 'result': "", 'remarks': ""},
                {'num': "2", 'name': "향취", 'criteria': "표준품과 일치", 'result': "", 'remarks': ""},
                {'num': "3", 'name': "사용감", 'criteria': "표준품과 일치", 'result': "", 'remarks': ""},
                {'num': "4", 'name': "pH (30℃)", 'criteria': "6.50 ± 1.00", 'result': "", 'remarks': ""},
                {'num': "5", 'name': "점도(30℃)", 'criteria': "33,000 ± 5,000", 'result': "", 'remarks': ""},
                {'num': "6", 'name': "비중(25℃)", 'criteria': "0.980 ± 0.02", 'result': "", 'remarks': ""},
                {'num': "7", 'name': "미생물(일반세균)", 'criteria': "100 cfu/ml 이하", 'result': "", 'remarks': ""},
                {'num': "", 'name': "미생물(효모/곰팡이)", 'criteria': "10 cfu/ml 이하", 'result': "", 'remarks': ""},
                {'num': "", 'name': "미생물(대장균)", 'criteria': "불검출", 'result': "", 'remarks': ""},
            ]
            for item in initial_data:
                self._add_coa_item_row(item_data=item, redraw=False)

    def _add_coa_item_row(self, item_data=None, redraw=True):
        if item_data is None:
            item_data = {'num': str(len(self.coa_item_rows) + 1), 'name': "", 'criteria': "", 'result': "", 'remarks': ""}

        row_index = len(self.coa_item_rows) + 1
        widgets = {'selected': ctk.BooleanVar()}

        chk = ctk.CTkCheckBox(self.table_frame, text="", variable=widgets['selected'])
        chk.grid(row=row_index, column=0, sticky="ew", padx=2)
        widgets['chk'] = chk

        widgets['num_label'] = ctk.CTkLabel(self.table_frame, text=item_data['num'])
        widgets['num_label'].grid(row=row_index, column=1, sticky="ew", padx=(1,0), pady=(1,0))

        widgets['name'] = ctk.CTkEntry(self.table_frame, corner_radius=0, border_width=0)
        widgets['name'].insert(0, item_data['name'])
        widgets['name'].grid(row=row_index, column=2, sticky="ew", padx=(1,0), pady=(1,0))

        widgets['criteria'] = ctk.CTkEntry(self.table_frame, corner_radius=0, border_width=0)
        widgets['criteria'].insert(0, item_data['criteria'])
        widgets['criteria'].grid(row=row_index, column=3, sticky="ew", padx=(1,0), pady=(1,0))

        widgets['result'] = ctk.CTkEntry(self.table_frame, corner_radius=0, border_width=0)
        widgets['result'].insert(0, item_data['result'])
        widgets['result'].grid(row=row_index, column=4, sticky="ew", padx=(1,0), pady=(1,0))

        widgets['remarks'] = ctk.CTkEntry(self.table_frame, corner_radius=0, border_width=0)
        widgets['remarks'].insert(0, item_data['remarks'])
        widgets['remarks'].grid(row=row_index, column=5, sticky="ew", padx=(1,0), pady=(1,0))

        self.coa_item_rows.append(widgets)
        if redraw:
            self._update_coa_row_numbers()

    def _remove_selected_coa_item_row(self):
        selected_rows = [i for i, row in enumerate(self.coa_item_rows) if row['selected'].get()]
        if not selected_rows:
            messagebox.showwarning("선택 오류", "삭제할 항목을 선택하세요.", parent=self)
            return

        for i in sorted(selected_rows, reverse=True):
            for widget in self.coa_item_rows[i].values():
                if isinstance(widget, (ctk.CTkEntry, ctk.CTkLabel, ctk.CTkCheckBox)):
                    widget.destroy()
            del self.coa_item_rows[i]
        self._update_coa_row_numbers()

    def _update_coa_row_numbers(self):
        for i, row_widgets in enumerate(self.coa_item_rows):
            row_widgets['num_label'].configure(text=str(i + 1))

    def clear_semi_product_form(self):
        """반제품 시험성적서 폼의 모든 입력 필드를 초기화합니다."""
        for entry in self.semi_product_entries.values():
            entry.delete(0, "end")
        
        self._redraw_coa_table(initial_items=None)

        messagebox.showinfo(self.texts['notification'], self.texts['form_cleared'], parent=self)

    def generate_semi_product_report(self):
        """입력된 데이터를 기반으로 동적 행을 포함한 엑셀 파일을 생성합니다."""
        try:
            kor_data = {key: entry.get() for key, entry in self.semi_product_entries.items()}
            
            if not all(kor_data.get(key) for key in ["제 품 명", "LOT", "종합판정"]):
                messagebox.showwarning(self.texts['input_error'], self.texts['required_fields_missing'], parent=self)
                return

            dynamic_test_items = []
            for i, row_widgets in enumerate(self.coa_item_rows):
                item_data = (
                    row_widgets['num'].cget("text"),
                    row_widgets['name'].get(),
                    row_widgets['criteria'].get(),
                    row_widgets['result'].get(),
                    row_widgets['remarks'].get()
                )
                dynamic_test_items.append(item_data)

            wb = Workbook()
            ws1 = wb.active
            ws1.title = "반제품 시험성적서"
            
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

            ws1.merge_cells('A1:F2')
            ws1['A1'] = "반제품 시험성적서"
            ws1['A1'].font = title_font
            ws1['A1'].alignment = center_align
            
            ws1.merge_cells('B4:C4'); ws1.merge_cells('E4:F4')
            ws1.merge_cells('B5:C5'); ws1.merge_cells('E5:F5')
            ws1['A4'] = "제 품 명"; ws1['B4'] = kor_data.get("제 품 명")
            ws1['D4'] = "L O T"; ws1['E4'] = kor_data.get("LOT")
            ws1['A5'] = "제조일자"; ws1['B5'] = kor_data.get("제조일자")
            ws1['D5'] = "시험일자"; ws1['E5'] = kor_data.get("시험일자")

            apply_style_to_range(ws1, 'A4:F5', border=thin_border)
            apply_style_to_range(ws1, 'A4:A5', font=label_font, fill=label_fill, alignment=center_align)
            apply_style_to_range(ws1, 'D4:D5', font=label_font, fill=label_fill, alignment=center_align)
            apply_style_to_range(ws1, 'B4:C5', font=cell_font, alignment=left_align)
            apply_style_to_range(ws1, 'E4:F5', font=cell_font, alignment=left_align)

            ws1.append([])
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

            for item in dynamic_test_items:
                ws1.append(item)
                current_row = ws1.max_row
                ws1.merge_cells(start_row=current_row, start_column=5, end_row=current_row, end_column=6)
                apply_style_to_range(ws1, f'A{current_row}:F{current_row}', font=cell_font, border=thin_border, alignment=center_align)
                ws1[f'B{current_row}'].alignment = left_align
                ws1[f'C{current_row}'].alignment = left_align
                ws1[f'D{current_row}'].alignment = left_align
            
            ws1.append([])
            ws1.append(["종합판정", kor_data.get("종합판정")])
            current_row = ws1.max_row
            ws1.merge_cells(start_row=current_row, start_column=2, end_row=current_row, end_column=6)
            apply_style_to_range(ws1, f'A{current_row}:F{current_row}', border=thin_border)
            ws1[f'A{current_row}'].font = label_font; ws1[f'A{current_row}'].fill = label_fill; ws1[f'A{current_row}'].alignment = center_align
            ws1[f'B{current_row}'].font = Font(name='맑은 고딕', size=10, bold=True); ws1[f'B{current_row}'].alignment = center_align

            ws1.append(["시험자", kor_data.get("시험자"), "", "시험일자", kor_data.get("일자")])
            current_row = ws1.max_row
            ws1.merge_cells(f'B{current_row}:C{current_row}'); ws1.merge_cells(f'E{current_row}:F{current_row}')
            apply_style_to_range(ws1, f'A{current_row}:F{current_row}', border=thin_border)
            apply_style_to_range(ws1, f'A{current_row}', font=label_font, fill=label_fill, alignment=center_align)
            apply_style_to_range(ws1, f'D{current_row}', font=label_font, fill=label_fill, alignment=center_align)
            apply_style_to_range(ws1, f'B{current_row}:C{current_row}', font=cell_font, alignment=center_align)
            apply_style_to_range(ws1, f'E{current_row}:F{current_row}', font=cell_font, alignment=center_align)

            ws1.column_dimensions['A'].width = 15
            ws1.column_dimensions['B'].width = 25
            ws1.column_dimensions['C'].width = 25
            ws1.column_dimensions['D'].width = 15
            ws1.column_dimensions['E'].width = 25
            ws1.column_dimensions['F'].width = 10

            default_filename = f"{kor_data['제 품 명']}_{kor_data['LOT']}_시험성적서.xlsx"
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

    def refresh_data(self):
        """품질 관리 프레임의 데이터를 새로고침합니다."""
        print("품질 관리 프레임 데이터 새로고침... (현재는 플레이스홀더)")
        # 향후 이 곳에 COA, MSDS 등 각 탭의 데이터를 다시 조회하고
        # UI를 업데이트하는 코드를 추가할 수 있습니다.
        # 예: self.setup_semi_finished_product_tab(self.tab_view.tab(self.texts['semi_finished_product_report']))
        pass

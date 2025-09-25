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
        # 구현 예정인 탭들은 숨김 처리
        # self.tab_view.add(self.texts['msds'])
        # self.tab_view.add(self.texts['prod_standard'])
        # self.tab_view.add(self.texts['mfg_record'])

        # --- 각 탭 UI 설정 ---
        self.setup_ingredient_report_tab(self.tab_view.tab(self.texts['ingredient_report']))
        self.setup_coa_tab(self.tab_view.tab(self.texts['coa']))
        # self.setup_placeholder_tab(self.tab_view.tab(self.texts['msds']), self.texts['msds'])
        # self.setup_placeholder_tab(self.tab_view.tab(self.texts['prod_standard']), self.texts['prod_standard'])
        # self.setup_placeholder_tab(self.tab_view.tab(self.texts['mfg_record']), self.texts['mfg_record'])

    def setup_ingredient_report_tab(self, tab_frame):
        """원료목록보고 탭의 UI를 설정합니다."""
        self.saved_products = []  # 저장된 제품 데이터 리스트
        
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

        self.scrollable_frame = ctk.CTkScrollableFrame(tab_frame, label_text="화장품 원료목록 보고서")
        self.scrollable_frame.grid(row=0, column=0, sticky="nsew", padx=10, pady=10)
        self.scrollable_frame.grid_columnconfigure(0, weight=1)

        self.report_entries = {}
        self.report_item_rows = []

        info_frame = ctk.CTkFrame(self.scrollable_frame)
        info_frame.grid(row=0, column=0, sticky="ew", padx=10, pady=(10, 20))
        info_frame.grid_columnconfigure(1, weight=3)  # 제품명 필드가 더 넓게
        info_frame.grid_columnconfigure(3, weight=1)  # 제조업자상호 필드

        ctk.CTkLabel(info_frame, text="제품명", font=ctk.CTkFont(weight="bold")).grid(row=0, column=0, padx=10, pady=5, sticky="w")
        self.report_entries["제품명"] = ctk.CTkEntry(info_frame)
        self.report_entries["제품명"].grid(row=0, column=1, padx=10, pady=5, sticky="ew")

        ctk.CTkLabel(info_frame, text="제조업자상호", font=ctk.CTkFont(weight="bold")).grid(row=0, column=2, padx=10, pady=5, sticky="w")
        self.report_entries["제조업자상호"] = ctk.CTkEntry(info_frame)
        self.report_entries["제조업자상호"].grid(row=0, column=3, padx=10, pady=5, sticky="ew")

        ctk.CTkLabel(info_frame, text="유형표시", font=ctk.CTkFont(weight="bold")).grid(row=1, column=0, padx=10, pady=5, sticky="w")
        ctk.CTkLabel(info_frame, text="유형표시", font=ctk.CTkFont(weight="bold")).grid(row=1, column=0, padx=10, pady=5, sticky="w")
        category_main_options = [f"{k} : {v['name']}" for k, v in self.cosmetic_type_map.items()]
        self.report_entries["유형표시_대분류"] = ctk.CTkComboBox(info_frame, values=category_main_options, command=self._update_subcategory_combo, width=250)
        self.report_entries["유형표시_대분류"].grid(row=1, column=1, padx=10, pady=5, sticky="ew")
        
        self.report_entries["유형표시"] = ctk.CTkComboBox(info_frame, values=[], width=250)
        self.report_entries["유형표시"].grid(row=1, column=3, padx=10, pady=5, sticky="ew")
        self._update_subcategory_combo(category_main_options[0])

        ctk.CTkLabel(info_frame, text="기능성화장품유형", font=ctk.CTkFont(weight="bold")).grid(row=2, column=0, padx=10, pady=5, sticky="w")
        self.report_entries["기능성화장품유형"] = ctk.CTkComboBox(info_frame, values=[f"{k} : {v}" for k, v in self.functional_types.items()], width=250)
        self.report_entries["기능성화장품유형"].grid(row=2, column=1, padx=10, pady=5, sticky="ew")

        ctk.CTkLabel(info_frame, text="기능성화장품품목코드", font=ctk.CTkFont(weight="bold")).grid(row=2, column=2, padx=10, pady=5, sticky="w")
        self.report_entries["기능성화장품품목코드"] = ctk.CTkEntry(info_frame)
        self.report_entries["기능성화장품품목코드"].grid(row=2, column=3, padx=10, pady=5, sticky="ew")

        ctk.CTkLabel(info_frame, text="용도(수출전용 여부)", font=ctk.CTkFont(weight="bold")).grid(row=3, column=0, padx=10, pady=5, sticky="w")
        self.report_entries["용도"] = ctk.CTkComboBox(info_frame, values=["", "E"], state="readonly", width=200)
        self.report_entries["용도"].grid(row=3, column=1, padx=10, pady=5, sticky="w")

        ctk.CTkLabel(info_frame, text="맞춤형 내용물(C1/C2)", font=ctk.CTkFont(weight="bold")).grid(row=3, column=2, padx=10, pady=5, sticky="w")
        self.report_entries["맞춤형내용물"] = ctk.CTkComboBox(info_frame, values=["", "C1", "C2"], state="readonly", width=200)
        self.report_entries["맞춤형내용물"].grid(row=3, column=3, padx=10, pady=5, sticky="w")

        # 원료성분명 일괄 입력 프레임
        paste_frame = ctk.CTkFrame(self.scrollable_frame)
        paste_frame.grid(row=1, column=0, sticky="ew", padx=10, pady=(10, 5))
        paste_frame.grid_columnconfigure(1, weight=1)
        
        ctk.CTkLabel(paste_frame, text="원료성분명(붙여넣기):", font=ctk.CTkFont(weight="bold")).grid(row=0, column=0, padx=10, pady=5, sticky="w")
        self.bulk_ingredient_entry = ctk.CTkTextbox(paste_frame, height=80)
        self.bulk_ingredient_entry.grid(row=0, column=1, padx=10, pady=5, sticky="ew")
        
        help_label = ctk.CTkLabel(paste_frame, text="※ 여러 성분을 ', ' (쉼표+공백) 또는 줄바꿈으로 구분하여 붙여넣으세요. 예: 물, 글리세린, 부틸렌글라이콜", 
                                 font=ctk.CTkFont(size=10), text_color="gray")
        help_label.grid(row=1, column=0, columnspan=2, padx=10, pady=(0, 5), sticky="w")

        self.report_table_frame = ctk.CTkFrame(self.scrollable_frame)
        self.report_table_frame.grid(row=2, column=0, sticky="ew", padx=10, pady=10)
        for i in range(9):  # 9개 열: 일련번호, 제품명, 유형표시, 기능성유형, 품목코드, 제조업자상호, 원료성분명, 용도, 맞춤형내용물
            self.report_table_frame.grid_columnconfigure(i, weight=1)

        # 테이블 헤더 생성은 _redraw_report_table에서 수행

        button_frame = ctk.CTkFrame(tab_frame, fg_color="transparent")
        button_frame.grid(row=1, column=0, padx=10, pady=10, sticky="e")
        
        ctk.CTkButton(button_frame, text="현재 제품 저장 후 계속", command=self.save_and_continue_report,
                     fg_color="#2FA572", hover_color="#106A43", width=150).pack(side="left", padx=5)
        ctk.CTkButton(button_frame, text="엑셀 보고서 생성", command=self.generate_ingredient_report,
                     fg_color="#3B8ED0", hover_color="#1F6AA5", width=150).pack(side="left", padx=5)
        ctk.CTkButton(button_frame, text="초기화", command=self.clear_ingredient_report_form, 
                     fg_color="gray50", hover_color="gray35").pack(side="left", padx=5)

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
        """테이블을 초기화하고 저장된 제품들을 표시합니다."""
        for row_widgets in self.report_item_rows:
            for key, widget in row_widgets.items():
                if hasattr(widget, 'destroy'):
                    widget.destroy()
        self.report_item_rows.clear()

        # 테이블 헤더
        headers = ["일련번호", "제품명", "유형표시", "기능성화장품유형", "기능성화장품품목코드", "제조업자상호", "원료성분명", "용도", "맞춤형내용물"]
        for i, h in enumerate(headers):
            header_label = ctk.CTkLabel(self.report_table_frame, text=h, font=ctk.CTkFont(weight="bold"), 
                                       fg_color=("gray85", "gray20"), corner_radius=0)
            header_label.grid(row=0, column=i, sticky="ew", padx=(1,0), pady=(1,0))

        # 저장된 제품들을 테이블에 표시
        if self.saved_products:
            row_number = 1
            for product in self.saved_products:
                for ingredient in product["원료성분명"]:
                    self._add_report_item_row_with_data(
                        row_number=row_number,
                        product_name=product["제품명"],
                        type_code=product["유형표시"],
                        functional_type=product["기능성화장품유형"],
                        functional_code=product["기능성화장품품목코드"],
                        manufacturer=product["제조업자상호"],
                        ingredient=ingredient,
                        usage=product["용도"],
                        custom_content=product["맞춤형내용물"]
                    )
                    row_number += 1

    def _add_report_item_row(self, ingredient_name=""):
        """테이블에 행을 추가합니다."""
        r = len(self.report_item_rows) + 1
        widgets = {}
        for i in range(9):
            e = ctk.CTkEntry(self.report_table_frame, corner_radius=0, border_width=0)
            if i == 0:  # 일련번호
                e.insert(0, str(r))
                e.configure(state="readonly", fg_color=("gray90", "gray25"))
            elif i == 6:  # 원료성분명
                e.insert(0, ingredient_name)
            e.grid(row=r, column=i, padx=(1,0), pady=(1,0), sticky="ew")
            widgets[f"col{i}"] = e
        self.report_item_rows.append(widgets)

    def _add_report_item_row_with_data(self, row_number, product_name, type_code, functional_type, functional_code, manufacturer, ingredient, usage, custom_content):
        """저장된 데이터로 테이블에 행을 추가합니다."""
        r = len(self.report_item_rows) + 1
        widgets = {}
        
        data = [str(row_number), product_name, type_code, functional_type, functional_code, manufacturer, ingredient, usage, custom_content]
        
        for i in range(9):
            e = ctk.CTkEntry(self.report_table_frame, corner_radius=0, border_width=0)
            e.insert(0, data[i])
            e.configure(state="readonly", fg_color=("gray90", "gray25"))
            e.grid(row=r, column=i, padx=(1,0), pady=(1,0), sticky="ew")
            widgets[f"col{i}"] = e
        self.report_item_rows.append(widgets)

    def clear_ingredient_report_form(self):
        """폼을 초기화합니다."""
        for entry in self.report_entries.values():
            if isinstance(entry, ctk.CTkComboBox):
                values = entry.cget("values")
                if values:
                    entry.set(values[0] if values else "")
            else:
                entry.delete(0, "end")
        self.bulk_ingredient_entry.delete("1.0", "end")
        self._redraw_report_table()
        self.saved_products.clear()  # 저장된 제품 목록도 초기화
        messagebox.showinfo("알림", "폼이 초기화되었습니다.", parent=self)

    def save_and_continue_report(self):
        """현재 제품 데이터를 저장하고 폼을 초기화하여 다음 제품을 입력받습니다."""
        # 필수 필드 확인
        if not self.report_entries["제품명"].get():
            messagebox.showwarning("입력 오류", "제품명을 입력해주세요.", parent=self)
            return

        # 원료성분명 붙여넣기 데이터 파싱
        pasted_text = self.bulk_ingredient_entry.get("1.0", "end-1c").strip()
        if ', ' in pasted_text:
            pasted_ingredients = pasted_text.split(', ')
        elif ',' in pasted_text:
            pasted_ingredients = pasted_text.split(',')
        else:
            pasted_ingredients = pasted_text.split('\n')
        pasted_ingredients = [line.strip() for line in pasted_ingredients if line.strip()]

        if not pasted_ingredients:
            messagebox.showwarning("입력 오류", "원료성분명을 입력해주세요.", parent=self)
            return

        # 제품 데이터 수집
        product_name = self.report_entries["제품명"].get()
        
        type_selected = self.report_entries["유형표시"].get()
        type_code = type_selected.split(" : ")[0] if " : " in type_selected else type_selected
        
        functional_selected = self.report_entries["기능성화장품유형"].get()
        functional_type_code = functional_selected.split(" : ")[0] if " : " in functional_selected else ""

        functional_code = self.report_entries["기능성화장품품목코드"].get()
        manufacturer = self.report_entries["제조업자상호"].get()
        usage = self.report_entries.get("용도", ctk.CTkComboBox(self, values=[])).get()
        custom_content = self.report_entries.get("맞춤형내용물", ctk.CTkComboBox(self, values=[])).get()

        # 제품 데이터 저장
        product_data = {
            "제품명": product_name,
            "유형표시": type_code,
            "기능성화장품유형": functional_type_code,
            "기능성화장품품목코드": functional_code,
            "제조업자상호": manufacturer,
            "용도": usage,
            "맞춤형내용물": custom_content,
            "원료성분명": pasted_ingredients
        }
        self.saved_products.append(product_data)

        # 폼 초기화 (제조업자상호는 유지)
        for key, entry in self.report_entries.items():
            if key == "제조업자상호":
                continue  # 제조업자상호는 유지
            elif isinstance(entry, ctk.CTkComboBox):
                values = entry.cget("values")
                if values:
                    entry.set(values[0] if values else "")
            else:
                entry.delete(0, "end")
        
        self.bulk_ingredient_entry.delete("1.0", "end")
        self._redraw_report_table()
        
        messagebox.showinfo("저장 완료", 
                          f"제품 '{product_name}'이(가) 저장되었습니다.\n"
                          f"현재 저장된 제품 수: {len(self.saved_products)}개\n\n"
                          f"계속해서 다음 제품을 입력하거나\n"
                          f"'엑셀 보고서 생성' 버튼을 눌러 모든 제품을 한 번에 출력하세요.", 
                          parent=self)

    def generate_ingredient_report(self):
        """원료목록 보고서를 엑셀로 생성합니다."""
        # 저장된 제품이 있는지 확인
        if not self.saved_products:
            # 저장된 제품이 없으면 현재 화면의 데이터를 사용
            if not self.report_entries["제품명"].get():
                messagebox.showwarning("입력 오류", "제품명을 입력해주세요.", parent=self)
                return

            # 원료성분명 붙여넣기 데이터 파싱
            pasted_text = self.bulk_ingredient_entry.get("1.0", "end-1c").strip()
            if ', ' in pasted_text:
                pasted_ingredients = pasted_text.split(', ')
            elif ',' in pasted_text:
                pasted_ingredients = pasted_text.split(',')
            else:
                pasted_ingredients = pasted_text.split('\n')
            pasted_ingredients = [line.strip() for line in pasted_ingredients if line.strip()]

            if not pasted_ingredients:
                messagebox.showwarning("입력 오류", "원료성분명을 입력해주세요.", parent=self)
                return

            # 단일 제품 처리
            self._generate_single_product_report(pasted_ingredients)
        else:
            # 여러 제품 처리
            self._generate_multiple_product_report()
    def _generate_single_product_report(self, pasted_ingredients):
        """단일 제품 보고서를 생성합니다."""
        # 테이블 재생성 및 데이터 채우기
        self._redraw_report_table()
        for ingredient in pasted_ingredients:
            self._add_report_item_row(ingredient_name=ingredient)

        # 상단 입력 데이터 수집
        product_name = self.report_entries["제품명"].get()
        
        type_selected = self.report_entries["유형표시"].get()
        type_code = type_selected.split(" : ")[0] if " : " in type_selected else type_selected
        
        functional_selected = self.report_entries["기능성화장품유형"].get()
        functional_type_code = functional_selected.split(" : ")[0] if " : " in functional_selected else ""

        functional_code = self.report_entries["기능성화장품품목코드"].get()
        manufacturer = self.report_entries["제조업자상호"].get()
        usage = self.report_entries.get("용도", ctk.CTkComboBox(self, values=[])).get()
        custom_content = self.report_entries.get("맞춤형내용물", ctk.CTkComboBox(self, values=[])).get()

        # 각 행에 데이터 채우기
        for row_widgets in self.report_item_rows:
            row_widgets["col1"].configure(state="normal")
            row_widgets["col1"].delete(0, "end")
            row_widgets["col1"].insert(0, product_name)
            row_widgets["col1"].configure(state="readonly", fg_color=("gray90", "gray25"))

            row_widgets["col2"].configure(state="normal")
            row_widgets["col2"].delete(0, "end")
            row_widgets["col2"].insert(0, type_code)
            row_widgets["col2"].configure(state="readonly", fg_color=("gray90", "gray25"))

            row_widgets["col3"].configure(state="normal")
            row_widgets["col3"].delete(0, "end")
            row_widgets["col3"].insert(0, functional_type_code)
            row_widgets["col3"].configure(state="readonly", fg_color=("gray90", "gray25"))

            row_widgets["col4"].configure(state="normal")
            row_widgets["col4"].delete(0, "end")
            row_widgets["col4"].insert(0, functional_code)
            row_widgets["col4"].configure(state="readonly", fg_color=("gray90", "gray25"))

            row_widgets["col5"].configure(state="normal")
            row_widgets["col5"].delete(0, "end")
            row_widgets["col5"].insert(0, manufacturer)
            row_widgets["col5"].configure(state="readonly", fg_color=("gray90", "gray25"))

            row_widgets["col7"].configure(state="normal")
            row_widgets["col7"].delete(0, "end")
            row_widgets["col7"].insert(0, usage)
            row_widgets["col7"].configure(state="readonly", fg_color=("gray90", "gray25"))

            row_widgets["col8"].configure(state="normal")
            row_widgets["col8"].delete(0, "end")
            row_widgets["col8"].insert(0, custom_content)
            row_widgets["col8"].configure(state="readonly", fg_color=("gray90", "gray25"))

        # 엑셀로 내보내기
        self._export_to_excel(usage, custom_content)

    def _generate_multiple_product_report(self):
        """여러 제품 보고서를 생성합니다."""
        wb = Workbook()
        ws = wb.active
        ws.title = "원료목록보고"
        
        # 스타일 정의
        header_font = Font(name='맑은 고딕', size=11, bold=True, color="FFFFFF")
        cell_font = Font(name='맑은 고딕', size=10)
        center_align = Alignment(horizontal="center", vertical="center", wrap_text=True)
        left_align = Alignment(horizontal="left", vertical="center", wrap_text=True)
        thin_border = Border(left=Side(style='thin'), right=Side(style='thin'), 
                           top=Side(style='thin'), bottom=Side(style='thin'))
        header_fill = PatternFill(start_color="4F81BD", end_color="4F81BD", fill_type="solid")

        # 헤더
        headers = ["일련번호", "제품명", "유형표시", "기능성화장품유형", "기능성화장품품목코드", 
                  "제조업자상호", "원료성분명", "용도", "맞춤형 내용물(혼합용'C1',소분용'C2')"]
        ws.append(headers)
        for col_idx, header_text in enumerate(headers, 1):
            cell = ws.cell(row=1, column=col_idx)
            cell.font = header_font
            cell.fill = header_fill
            cell.alignment = center_align
            cell.border = thin_border

        # 모든 저장된 제품 데이터 추가
        row_number = 1
        for product in self.saved_products:
            for ingredient in product["원료성분명"]:
                excel_row = [
                    str(row_number),
                    product["제품명"],
                    product["유형표시"],
                    product["기능성화장품유형"],
                    product["기능성화장품품목코드"],
                    product["제조업자상호"],
                    ingredient,
                    product["용도"],
                    product["맞춤형내용물"]
                ]
                
                current_row_num = ws.max_row + 1
                for col_idx, value in enumerate(excel_row, 1):
                    cell = ws.cell(row=current_row_num, column=col_idx, value=value)
                    cell.font = cell_font
                    cell.border = thin_border
                    cell.alignment = left_align
                
                row_number += 1

        # 열 너비 자동 조절
        for col in ws.columns:
            max_length = 0
            column_letter = col[0].column_letter
            
            # 헤더 길이 계산
            header_cell = ws[f"{column_letter}1"]
            if header_cell.value:
                header_lines = str(header_cell.value).split('\n')
                for line in header_lines:
                    if len(line) * 1.2 > max_length:
                        max_length = len(line) * 1.2
            
            # 데이터 길이 계산
            for cell in col:
                if cell.value:
                    length = sum(2 if '\uac00' <= char <= '\ud7a3' else 1 for char in str(cell.value))
                    if length > max_length:
                        max_length = length
            
            adjusted_width = (max_length + 2)
            ws.column_dimensions[column_letter].width = adjusted_width

        # 파일 저장
        default_name = f"원료목록보고_{len(self.saved_products)}개제품.xlsx"
        file_path = fd.asksaveasfilename(defaultextension=".xlsx", 
                                        filetypes=[("Excel Files", "*.xlsx")], 
                                        initialfile=default_name, 
                                        title="엑셀로 저장")
        if file_path:
            wb.save(file_path)
            messagebox.showinfo("성공", f"엑셀 파일이 성공적으로 저장되었습니다:\n{file_path}", parent=self)

    def _export_to_excel(self, usage, custom_content):
        """테이블 데이터를 엑셀로 내보냅니다."""
        wb = Workbook()
        ws = wb.active
        ws.title = "원료목록보고"
        
        # 스타일 정의
        header_font = Font(name='맑은 고딕', size=11, bold=True, color="FFFFFF")
        cell_font = Font(name='맑은 고딕', size=10)
        center_align = Alignment(horizontal="center", vertical="center", wrap_text=True)
        left_align = Alignment(horizontal="left", vertical="center", wrap_text=True)
        thin_border = Border(left=Side(style='thin'), right=Side(style='thin'), 
                           top=Side(style='thin'), bottom=Side(style='thin'))
        header_fill = PatternFill(start_color="4F81BD", end_color="4F81BD", fill_type="solid")

        # 헤더
        headers = ["일련번호", "제품명", "유형표시", "기능성화장품유형", "기능성화장품품목코드", 
                  "제조업자상호", "원료성분명", "용도", "맞춤형 내용물(혼합용'C1',소분용'C2')"]
        ws.append(headers)
        for col_idx, header_text in enumerate(headers, 1):
            cell = ws.cell(row=1, column=col_idx)
            cell.font = header_font
            cell.fill = header_fill
            cell.alignment = center_align
            cell.border = thin_border

        # 데이터 행
        for row_widgets in self.report_item_rows:
            excel_row = [row_widgets[f"col{i}"].get() for i in range(7)]
            excel_row.append(usage)  # 용도
            excel_row.append(custom_content)  # 맞춤형 내용물
            
            current_row_num = ws.max_row + 1
            for col_idx, value in enumerate(excel_row, 1):
                cell = ws.cell(row=current_row_num, column=col_idx, value=value)
                cell.font = cell_font
                cell.border = thin_border
                cell.alignment = left_align

        # 열 너비 자동 조절
        for col in ws.columns:
            max_length = 0
            column_letter = col[0].column_letter
            
            # 헤더 길이 계산
            header_cell = ws[f"{column_letter}1"]
            if header_cell.value:
                header_lines = str(header_cell.value).split('\n')
                for line in header_lines:
                    if len(line) * 1.2 > max_length:
                        max_length = len(line) * 1.2
            
            # 데이터 길이 계산
            for cell in col:
                if cell.value:
                    length = sum(2 if '\uac00' <= char <= '\ud7a3' else 1 for char in str(cell.value))
                    if length > max_length:
                        max_length = length
            
            adjusted_width = (max_length + 2)
            ws.column_dimensions[column_letter].width = adjusted_width

        # 파일 저장
        default_name = f"원료목록보고_{self.report_entries['제품명'].get()}.xlsx"
        file_path = fd.asksaveasfilename(defaultextension=".xlsx", 
                                        filetypes=[("Excel Files", "*.xlsx")], 
                                        initialfile=default_name, 
                                        title="엑셀로 저장")
        if file_path:
            wb.save(file_path)
            messagebox.showinfo("성공", f"엑셀 파일이 성공적으로 저장되었습니다:\n{file_path}", parent=self)

    def setup_coa_tab(self, tab_frame):
        """COA 탭의 UI를 설정합니다."""
        tab_frame.grid_columnconfigure(0, weight=1)
        tab_frame.grid_rowconfigure(0, weight=1)

        coa_sub_tab_view = ctk.CTkTabview(tab_frame, border_width=1, border_color=("gray80", "gray30"))
        coa_sub_tab_view.grid(row=0, column=0, padx=10, pady=10, sticky="nsew")

        coa_sub_tab_view.add(self.texts['semi_finished_product_report'])
        coa_sub_tab_view.add("완제품 시험성적서")
        
        self.setup_semi_finished_product_tab(coa_sub_tab_view.tab(self.texts['semi_finished_product_report']))
        self.setup_finished_product_tab(coa_sub_tab_view.tab("완제품 시험성적서"))

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

    def setup_finished_product_tab(self, tab_frame):
        """완제품 시험성적서 탭의 UI를 설정합니다."""
        tab_frame.grid_columnconfigure(0, weight=1)
        tab_frame.grid_rowconfigure(0, weight=1)

        scrollable_frame = ctk.CTkScrollableFrame(tab_frame, label_text="완제품 시험성적서")
        scrollable_frame.grid(row=0, column=0, sticky="nsew", padx=10, pady=10)
        scrollable_frame.grid_columnconfigure(0, weight=1)

        self.finished_product_entries = {}
        self.finished_item_rows = []

        # 상단 기본 정보
        info_frame = ctk.CTkFrame(scrollable_frame)
        info_frame.grid(row=0, column=0, sticky="ew", padx=10, pady=(10, 20))
        info_frame.grid_columnconfigure((1, 3), weight=1)

        info_items = [
            ("제 품 명", 0, 0, 3),
            ("반제품 제조일자", 1, 0, 1), ("반제품제조번호(LOT)", 1, 2, 1),
            ("포장 일자", 2, 0, 1), ("완제품제조번호(LOT)", 2, 2, 1),
            ("사용 기한", 3, 0, 1), ("단위 용량 (ml)", 3, 2, 1),
            ("샘플링 방법", 4, 0, 1), ("시험 일자", 4, 2, 1),
        ]

        for text, r, c, colspan in info_items:
            ctk.CTkLabel(info_frame, text=text, font=ctk.CTkFont(weight="bold")).grid(row=r, column=c, padx=10, pady=5, sticky="w")
            entry = ctk.CTkEntry(info_frame)
            entry.grid(row=r, column=c + 1, columnspan=colspan, padx=10, pady=5, sticky="ew")
            self.finished_product_entries[text] = entry

        # 시험항목 테이블
        self.finished_table_frame = ctk.CTkFrame(scrollable_frame)
        self.finished_table_frame.grid(row=1, column=0, sticky="ew", padx=10, pady=10)
        self.finished_table_frame.grid_columnconfigure(0, weight=0)  # 체크박스 컬럼
        self.finished_table_frame.grid_columnconfigure(1, weight=1)  # 구분 컬럼
        self.finished_table_frame.grid_columnconfigure(2, weight=2)  # 시험항목 컬럼
        self.finished_table_frame.grid_columnconfigure(3, weight=3)  # 시험기준 컬럼
        self.finished_table_frame.grid_columnconfigure(4, weight=3)  # 시험결과 컬럼
        self.finished_table_frame.grid_columnconfigure(5, weight=1)  # 비고 컬럼

        # 테이블 헤더
        headers = ["선택", "구분", "시험항목", "시험기준", "시험결과", "비고"]
        for i, h in enumerate(headers):
            ctk.CTkLabel(self.finished_table_frame, text=h, font=ctk.CTkFont(weight="bold"), 
                        fg_color=("gray85", "gray20"), corner_radius=0).grid(row=0, column=i, sticky="ew", padx=2, pady=2)

        # 초기 행 생성
        self._create_initial_finished_product_rows()

        # 테이블 컨트롤 버튼 (판정/시험자 정보 바로 위에 배치)
        finished_table_controls = ctk.CTkFrame(scrollable_frame)
        finished_table_controls.grid(row=2, column=0, sticky="w", padx=10, pady=(10, 5))
        ctk.CTkButton(finished_table_controls, text="시험항목 추가", command=self._add_finished_item_row).pack(side="left")
        ctk.CTkButton(finished_table_controls, text="선택 항목 제거", command=self._remove_selected_finished_item_row).pack(side="left", padx=10)

        # 판정/시험자 정보 (특이사항)
        conclusion_frame = ctk.CTkFrame(scrollable_frame)
        conclusion_frame.grid(row=3, column=0, sticky="ew", padx=10, pady=(5, 10))
        conclusion_frame.grid_columnconfigure((1, 3, 5), weight=1)

        for idx, (label, key) in enumerate([("시험자", "시험자"), ("검토자", "검토자"), ("종합판정", "종합판정")]):
            ctk.CTkLabel(conclusion_frame, text=label, font=ctk.CTkFont(weight="bold")).grid(row=0, column=idx*2, padx=10, pady=5, sticky="w")
            self.finished_product_entries[key] = ctk.CTkEntry(conclusion_frame)
            self.finished_product_entries[key].grid(row=0, column=idx*2+1, padx=10, pady=5, sticky="ew")

        # 버튼 (스크롤 프레임 밖에 고정)
        button_frame = ctk.CTkFrame(tab_frame, fg_color="transparent")
        button_frame.grid(row=1, column=0, sticky="e", padx=10, pady=10)
        ctk.CTkButton(button_frame, text="엑셀 보고서 생성", command=self.generate_finished_product_report, 
                     fg_color="#3B8ED0", hover_color="#1F6AA5").pack(side="left", padx=5)
        ctk.CTkButton(button_frame, text="초기화", command=self.clear_finished_product_form, 
                     fg_color="gray50", hover_color="gray35").pack(side="left", padx=5)

        self._redraw_finished_product_table()

    def _create_initial_finished_product_rows(self):
        """완제품 시험성적서의 초기 시험 항목들을 생성합니다."""
        initial_items = [
            {"id": "1", "item": "성 상", "spec": "유백색 크림상", "result": "", "note": "관능검사 / 표준품과 비교"},
            {"id": "2", "item": "향 취", "spec": "표준품과 일치", "result": "", "note": "관능검사 / 표준품과 비교"},
            {"id": "3", "item": "이물질", "spec": "미발견", "result": "", "note": "관능검사 / 표준품과 비교"},
            {"id": "4", "item": "내용량", "spec": "표시량의 97% 이상", "result": "", "note": "화장품 기준 및 시험방법 중 2.시험방법 1)내용량 가)용량으로 표시된 제품에 따른다"},
            {"id": "5", "item": "사용감", "spec": "표준품과 일치", "result": "", "note": "관능검사 / 표준품과 비교"},
            {"id": "6", "item": "pH(25℃)", "spec": "5.80 ± 1.00", "result": "", "note": "pH Meter 사용"},
            {"id": "7", "item": "점도(25℃)", "spec": "19,000 ± 4,000", "result": "", "note": "Helipath, 50rpm, Spindle-E, 1min"},
            {"id": "8", "item": "비중(25℃)", "spec": "1.010 ± 0.050", "result": "", "note": "비중병 사용"},
            {"id": "9", "item": "외관 및 용기상태", "spec": "표준품과 비교", "result": "", "note": "관능검사 / 표준품과 비교"},
            {"id": "10", "item": "인쇄상태", "spec": "육안 식별", "result": "", "note": "관능검사 / 표준품과 비교"},
            {"id": "11", "item": "법적 표시사항", "spec": "법적 규정에 적합", "result": "", "note": "화장품법 및 화장품법 시행규칙 참고"},
            {"id": "12", "item": "아데노신 함량 시험", "spec": "표시량의 90% 이상 (0.04%)", "result": "", "note": "기능성화장품 기준 및 시험방법 참고"},
            {"id": "13", "item": "아데노신 확인 시험", "spec": "검체와 표준액의 RT가 같다", "result": "", "note": "기능성화장품 기준 및 시험방법 참고"},
            {"id": "14", "item": "미생물(일반세균)", "spec": "100 cfu/ml 이하", "result": "", "note": "화장품의 미생물 한도 기준을 참고. 3M™ Petrifilm Plate법 사용"},
            {"id": "", "item": "미생물(진균(효모/곰팡이))", "spec": "10 cfu/ml 이하", "result": "", "note": ""},
            {"id": "", "item": "미생물(대장균)", "spec": "불검출", "result": "", "note": ""},
        ]
        for item_data in initial_items:
            self._add_finished_item_row_with_data(item_data)
        
        # 특이사항 줄을 맨 마지막에 추가
        self._add_special_remarks_row()

    def _redraw_finished_product_table(self):
        """완제품 시험성적서 테이블 헤더를 다시 그립니다."""
        # 헤더만 다시 그리기 (이미 _create_initial_finished_product_rows에서 행이 추가됨)
        pass

    def _add_finished_item_row(self, item_data=None, redraw=True):
        """완제품 시험항목 행을 추가합니다."""
        if item_data is None:
            item_data = {'id': '', 'item': '', 'spec': '', 'result': '', 'note': ''}

        # 특이사항 줄이 아닌 경우에만 번호를 부여
        if item_data.get('id') != "특이사항":
            # 현재 특이사항 줄을 제외한 행의 개수를 계산
            non_special_count = 0
            for row in self.finished_item_rows:
                if row.get('id_label') and row['id_label'].cget("text") != "특이사항":
                    non_special_count += 1
            item_data['id'] = str(non_special_count + 1)

        # 행 인덱스 계산 (특이사항은 항상 마지막에)
        if item_data.get('id') == "특이사항":
            row_index = len(self.finished_item_rows) + 1
        else:
            # 특이사항 줄이 있다면 그 바로 앞에 삽입
            special_index = None
            for i, row in enumerate(self.finished_item_rows):
                if row.get('id_label') and row['id_label'].cget("text") == "특이사항":
                    special_index = i
                    break
            
            if special_index is not None:
                row_index = special_index + 1
            else:
                row_index = len(self.finished_item_rows) + 1

        widgets = {'selected': ctk.BooleanVar()}

        # 체크박스 (column 0)
        chk = ctk.CTkCheckBox(self.finished_table_frame, text="", variable=widgets['selected'])
        chk.grid(row=row_index, column=0, sticky="w", padx=2, pady=2)
        widgets['chk'] = chk

        # 구분(ID) 라벨 (column 1)
        widgets['id_label'] = ctk.CTkLabel(self.finished_table_frame, text=item_data['id'])
        widgets['id_label'].grid(row=row_index, column=1, sticky="ew", padx=2, pady=2)

        # 시험항목, 시험기준, 시험결과, 비고 (columns 2-5)
        for i, key in enumerate(['item', 'spec', 'result', 'note'], start=2):
            entry = ctk.CTkEntry(self.finished_table_frame, corner_radius=0, border_width=0)
            entry.insert(0, item_data.get(key, ''))
            entry.grid(row=row_index, column=i, sticky="ew", padx=(1,0), pady=(1,0))
            widgets[key] = entry

        # 특이사항 줄이 아닌 경우, 특이사항 줄 바로 앞에 삽입
        if item_data.get('id') != "특이사항" and special_index is not None:
            self.finished_item_rows.insert(special_index, widgets)
            # 특이사항 줄과 그 뒤의 모든 행들을 한 칸씩 아래로 이동
            self._reposition_rows_from_index(special_index + 1)
        else:
            self.finished_item_rows.append(widgets)
            
        if redraw:
            self._update_finished_row_numbers()

    def _reposition_rows_from_index(self, start_index):
        """지정된 인덱스부터 모든 행들을 한 칸씩 아래로 이동시킵니다."""
        for i in range(start_index, len(self.finished_item_rows)):
            row = self.finished_item_rows[i]
            new_row_index = i + 2  # grid row는 1부터 시작하고 헤더가 있으므로 +2
            
            # 각 위젯을 새로운 행 위치로 이동
            if 'chk' in row:
                row['chk'].grid(row=new_row_index, column=0, sticky="w", padx=2, pady=2)
            if 'id_label' in row:
                row['id_label'].grid(row=new_row_index, column=1, sticky="ew", padx=2, pady=2)
            
            for j, key in enumerate(['item', 'spec', 'result', 'note'], start=2):
                if key in row:
                    row[key].grid(row=new_row_index, column=j, sticky="ew", padx=(1,0), pady=(1,0))

    def _add_finished_item_row_with_data(self, item_data):
        """완제품 시험항목 행을 데이터와 함께 추가합니다."""
        self._add_finished_item_row(item_data, redraw=False)

    def _add_special_remarks_row(self):
        """특이사항 줄을 맨 마지막에 추가합니다."""
        if not self._has_special_remarks_row():
            special_data = {"id": "특이사항", "item": "", "spec": "", "result": "", "note": ""}
            self._add_finished_item_row(special_data, redraw=False)

    def _has_special_remarks_row(self):
        """특이사항 줄이 있는지 확인합니다."""
        for row in self.finished_item_rows:
            if row.get('id_label') and row['id_label'].cget("text") == "특이사항":
                return True
        return False

    def _remove_selected_finished_item_row(self):
        """선택된 완제품 시험항목 행을 제거합니다. (특이사항 줄 제외)"""
        selected_rows = []
        for i, row in enumerate(self.finished_item_rows):
            # 특이사항 줄은 삭제 대상에서 제외
            if row['selected'].get() and row['id_label'].cget("text") != "특이사항":
                selected_rows.append(i)
        
        if not selected_rows:
            messagebox.showwarning("선택 오류", "삭제할 항목을 선택하세요. (특이사항 줄은 삭제할 수 없습니다)", parent=self)
            return

        for i in sorted(selected_rows, reverse=True):
            for widget in self.finished_item_rows[i].values():
                if hasattr(widget, 'destroy'):
                    widget.destroy()
            del self.finished_item_rows[i]
        
        # 삭제 후 모든 행을 다시 배치
        self._reposition_all_rows()
        self._update_finished_row_numbers()

    def _reposition_all_rows(self):
        """모든 행을 다시 배치합니다."""
        for i, row in enumerate(self.finished_item_rows):
            new_row_index = i + 2  # grid row는 1부터 시작하고 헤더가 있으므로 +2
            
            # 각 위젯을 새로운 행 위치로 이동
            if 'chk' in row:
                row['chk'].grid(row=new_row_index, column=0, sticky="w", padx=2, pady=2)
            if 'id_label' in row:
                row['id_label'].grid(row=new_row_index, column=1, sticky="ew", padx=2, pady=2)
            
            for j, key in enumerate(['item', 'spec', 'result', 'note'], start=2):
                if key in row:
                    row[key].grid(row=new_row_index, column=j, sticky="ew", padx=(1,0), pady=(1,0))

    def _update_finished_row_numbers(self):
        """완제품 시험항목의 일련번호를 업데이트합니다. (특이사항 줄 제외)"""
        number = 1
        for row_widgets in self.finished_item_rows:
            current_id = row_widgets['id_label'].cget("text")
            # 특이사항 줄이 아니고 기존에 숫자였던 경우만 번호 업데이트
            if current_id != "특이사항" and (current_id == "" or current_id.isdigit()):
                row_widgets['id_label'].configure(text=str(number))
                number += 1

    def clear_finished_product_form(self):
        """완제품 시험성적서 폼을 초기화합니다."""
        for entry in self.finished_product_entries.values():
            entry.delete(0, "end")

        for row_widgets in self.finished_item_rows[:]:
            for widget in row_widgets.values():
                if hasattr(widget, 'destroy'):
                    widget.destroy()
        self.finished_item_rows.clear()

        self._create_initial_finished_product_rows()
        messagebox.showinfo("알림", "양식이 초기화되었습니다.", parent=self)

    def generate_finished_product_report(self):
        """완제품 시험성적서 엑셀 파일을 생성합니다."""
        try:
            # 데이터 수집
            info_data = {key: entry.get() for key, entry in self.finished_product_entries.items()}

            if not all(info_data.get(key) for key in ["제 품 명", "완제품제조번호(LOT)", "종합판정"]):
                messagebox.showwarning("입력 오류", "제품명, 완제품 LOT, 종합판정은 필수 입력 항목입니다.", parent=self)
                return

            test_items = []
            for row_widgets in self.finished_item_rows:
                item_id = row_widgets["id_label"].cget("text")
                item = row_widgets["item"].get()
                spec = row_widgets["spec"].get()
                result = row_widgets["result"].get()
                note = row_widgets["note"].get()
                test_items.append({"id": item_id, "item": item, "spec": spec, "result": result, "note": note})

            # Excel 생성
            wb = Workbook()
            ws = wb.active
            ws.title = "완제품 시험성적서"

            # 스타일 정의
            title_font = Font(name='맑은 고딕', size=18, bold=True)
            header_font = Font(name='맑은 고딕', size=11, bold=True, color="FFFFFF")
            label_font = Font(name='맑은 고딕', size=10, bold=True)
            cell_font = Font(name='맑은 고딕', size=10)
            center_align = Alignment(horizontal="center", vertical="center", wrap_text=True)
            left_align = Alignment(horizontal="left", vertical="center", indent=1, wrap_text=True)
            thin_border = Border(left=Side(style='thin'), right=Side(style='thin'), top=Side(style='thin'), bottom=Side(style='thin'))
            header_fill = PatternFill(start_color="4F81BD", end_color="4F81BD", fill_type="solid")
            label_fill = PatternFill(start_color="DCE6F1", end_color="DCE6F1", fill_type="solid")

            def apply_style(cell, font=None, border=None, fill=None, alignment=None):
                if font: cell.font = font
                if border: cell.border = border
                if fill: cell.fill = fill
                if alignment: cell.alignment = alignment

            # 문서 제목
            ws.merge_cells('A1:E2')
            ws['A1'] = "완제품 시험성적서"
            apply_style(ws['A1'], font=title_font, alignment=center_align)

            # 기본 정보
            info_layout = [
                ("제 품 명", info_data.get("제 품 명")), ("반제품 제조일자", info_data.get("반제품 제조일자")), ("반제품제조번호(LOT)", info_data.get("반제품제조번호(LOT)")),
                ("포장 일자", info_data.get("포장 일자")), ("완제품제조번호(LOT)", info_data.get("완제품제조번호(LOT)")), ("사용 기한", info_data.get("사용 기한")),
                ("단위 용량 (ml)", info_data.get("단위 용량 (ml)")), ("샘플링 방법", info_data.get("샘플링 방법")), ("시험 일자", info_data.get("시험 일자"))
            ]
            row = 4
            # 제품명 행
            apply_style(ws.cell(row, 1, info_layout[0][0]), font=label_font, fill=label_fill, alignment=center_align, border=thin_border)
            ws.merge_cells(start_row=row, start_column=2, end_row=row, end_column=5)
            apply_style(ws.cell(row, 2, info_layout[0][1]), font=cell_font, alignment=left_align, border=thin_border)
            for c in range(3, 6): apply_style(ws.cell(row, c), border=thin_border)
            row += 1
            # 나머지 정보 행
            for i in range(1, len(info_layout), 2):
                apply_style(ws.cell(row, 1, info_layout[i][0]), font=label_font, fill=label_fill, alignment=center_align, border=thin_border)
                apply_style(ws.cell(row, 2, info_layout[i][1]), font=cell_font, alignment=left_align, border=thin_border)
                if i + 1 < len(info_layout):
                    apply_style(ws.cell(row, 3, info_layout[i+1][0]), font=label_font, fill=label_fill, alignment=center_align, border=thin_border)
                    ws.merge_cells(start_row=row, start_column=4, end_row=row, end_column=5)
                    apply_style(ws.cell(row, 4, info_layout[i+1][1]), font=cell_font, alignment=left_align, border=thin_border)
                    apply_style(ws.cell(row, 5), border=thin_border)
                row += 1

            # 시험 항목 테이블
            ws.append([])
            table_start_row = ws.max_row + 1
            headers = ["구분", "시험항목", "시험기준", "시험결과", "비고"]
            ws.append(headers)
            for col_idx, header_text in enumerate(headers, 1):
                apply_style(ws.cell(table_start_row, col_idx), font=header_font, fill=header_fill, alignment=center_align, border=thin_border)

            for item in test_items:
                ws.append([item["id"], item["item"], item["spec"], item["result"], item["note"]])
                for col in range(1, 6):
                    apply_style(ws.cell(ws.max_row, col), font=cell_font, border=thin_border, alignment=center_align)

            # 종합판정 및 시험자
            ws.append([])
            conclusion_row = ws.max_row + 1
            apply_style(ws.cell(conclusion_row, 1, "시험자"), font=label_font, fill=label_fill, alignment=center_align, border=thin_border)
            apply_style(ws.cell(conclusion_row, 2, info_data.get("시험자")), font=cell_font, alignment=center_align, border=thin_border)
            apply_style(ws.cell(conclusion_row, 3, "검토자"), font=label_font, fill=label_fill, alignment=center_align, border=thin_border)
            apply_style(ws.cell(conclusion_row, 4, info_data.get("검토자")), font=cell_font, alignment=center_align, border=thin_border)
            ws.cell(conclusion_row, 5).border = thin_border

            conclusion_row += 1
            apply_style(ws.cell(conclusion_row, 1, "종합판정"), font=label_font, fill=label_fill, alignment=center_align, border=thin_border)
            ws.merge_cells(start_row=conclusion_row, start_column=2, end_row=conclusion_row, end_column=5)
            apply_style(ws.cell(conclusion_row, 2, info_data.get("종합판정")), font=Font(name='맑은 고딕', size=10, bold=True), alignment=center_align, border=thin_border)
            for c in range(3, 6): apply_style(ws.cell(conclusion_row, c), border=thin_border)

            # 열 너비 조정
            ws.column_dimensions['A'].width = 15
            ws.column_dimensions['B'].width = 25
            ws.column_dimensions['C'].width = 30
            ws.column_dimensions['D'].width = 20
            ws.column_dimensions['E'].width = 35

            # 파일 저장
            default_filename = f"{info_data['제 품 명']}_{info_data['완제품제조번호(LOT)']}_완제품시험성적서.xlsx"
            file_path = fd.asksaveasfilename(
                defaultextension=".xlsx",
                filetypes=[("Excel 통합 문서", "*.xlsx")],
                initialfile=default_filename,
                title="보고서 다른 이름으로 저장"
            )

            if file_path:
                wb.save(file_path)
                messagebox.showinfo("성공", f"보고서가 성공적으로 저장되었습니다:\n{file_path}", parent=self)

        except Exception as e:
            messagebox.showerror("오류", f"보고서 생성 중 오류가 발생했습니다:\n{e}", parent=self)

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
        print("품질 관리 프레임 데이터 새로고침...")
        try:
            # 각 탭의 UI를 다시 설정하여 데이터를 새로고침합니다.
            self.setup_ingredient_report_tab(self.tab_view.tab(self.texts['ingredient_report']))
            self.setup_coa_tab(self.tab_view.tab(self.texts['coa']))
        except Exception as e:
            print(f"[오류] 품질 관리 프레임 새로고침 실패: {e}")

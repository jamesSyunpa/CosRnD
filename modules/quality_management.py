# modules/quality_management.py
import os
from datetime import datetime, date
import customtkinter as ctk
from tkinter import messagebox
import openpyxl
from openpyxl import Workbook
from openpyxl.styles import Font, Alignment, Border, Side, PatternFill
from openpyxl.utils import get_column_letter
import tkinter.filedialog as fd
from modules import excel_handler
from modules.excel_handler import _get_display_length

from sqlalchemy.orm import joinedload
from modules.translation import get_texts
from database.db_manager import db_manager
from database.models import (
    IngredientReport, IngredientReportItem,
    SemiFinishedCOA, SemiFinishedCOAItem,
    FinishedProductCOA, FinishedProductCOAItem,
    MaterialInspectionReport, ProductStandard,
    BatchManufacturingRecord, StabilityTestReport,
    PackagingCompatibilityReport, MSDSReport, Material, Formulation
)

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

        # --- 품질관리 8대 핵심 서류 탭 추가 (COA 바로 다음에 MSDS 배치) ---
        self.tab_labels = {
            'coa': self.texts.get('coa', 'COA (시험성적서)'),
            'msds': self.texts.get('msds', 'MSDS (물질안전보건자료)'),
            'ingredient_report': self.texts.get('ingredient_report', '원료목록보고'),
            'mat_inspection': self.texts.get('mat_inspection', '원료 입고검사'),
            'prod_standard': self.texts.get('prod_standard', '제품표준서'),
            'mfg_record': self.texts.get('mfg_record', '제조관리기록서'),
            'stability_test': self.texts.get('stability_test', '안정성 시험'),
            'compatibility_test': self.texts.get('compatibility_test', '용기 상용성 시험')
        }

        self.tab_view.add(self.tab_labels['coa'])
        self.tab_view.add(self.tab_labels['msds'])
        self.tab_view.add(self.tab_labels['ingredient_report'])
        self.tab_view.add(self.tab_labels['mat_inspection'])
        self.tab_view.add(self.tab_labels['prod_standard'])
        self.tab_view.add(self.tab_labels['mfg_record'])
        self.tab_view.add(self.tab_labels['stability_test'])
        self.tab_view.add(self.tab_labels['compatibility_test'])

        # --- 품질관리 8대 탭 지연 초기화(Lazy Tab Loading) 등록 ---
        self._initialized_tabs = set()
        self._tab_setup_handlers = {
            'coa': self.setup_coa_tab,
            'msds': self.setup_msds_tab,
            'ingredient_report': self.setup_ingredient_report_tab,
            'mat_inspection': self.setup_material_inspection_tab,
            'prod_standard': self.setup_product_standard_tab,
            'mfg_record': self.setup_batch_manufacturing_tab,
            'stability_test': self.setup_stability_test_tab,
            'compatibility_test': self.setup_packaging_compatibility_tab
        }

    def ensure_tab_initialized(self, tab_key):
        """요청된 탭이 아직 초기화되지 않았다면 즉시 빌드합니다 (초고속 지연 로딩)."""
        if tab_key in self._initialized_tabs:
            return
        handler = self._tab_setup_handlers.get(tab_key)
        tab_label = self.tab_labels.get(tab_key)
        if handler and tab_label:
            tab_frame = self.tab_view.tab(tab_label)
            handler(tab_frame)
            self._initialized_tabs.add(tab_key)

    def setup_ingredient_report_tab(self, tab_frame):
        """원료목록보고 탭의 UI를 설정합니다."""
        self.saved_products = []  # 저장된 제품 데이터 리스트 (엑셀용 버퍼)
        self.current_ingredient_report_id = None  # DB 로드 시 편집 중인 ID
        
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
            "없음": "기능성화장품 아님",
            "F1": "미백", "F2": "주름개선", "F3": "자외선차단", "F4": "미백+주름개선",
            "F5": "미백+자외선차단", "F6": "주름개선+자외선차단", "F7": "미백+주름개선+자외선차단",
            "F8": "염모/탈염/탈색", "F9": "체모 제모", "F10": "탈모증상 완화",
            "F11": "여드름성 피부 완화", "F12": "피부 장벽 기능 회복", "F13": "튼살로 인한 붉은 선 완화",
            "F14": "기타 복합유형"
        }

        tab_frame.grid_columnconfigure(0, weight=1)
        tab_frame.grid_rowconfigure(0, weight=1)

        self.scrollable_frame = ctk.CTkScrollableFrame(tab_frame, label_text="화장품 원료목록 보고")
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

        # DB 저장/불러오기 UI
        db_frame = ctk.CTkFrame(tab_frame, fg_color="transparent")
        db_frame.grid(row=2, column=0, padx=10, pady=(0, 10), sticky="ew")
        db_frame.grid_columnconfigure(1, weight=1)

        ctk.CTkButton(db_frame, text="DB 저장", command=self.save_ingredient_report_to_db,
                      fg_color="#2FA572", hover_color="#106A43", width=120).grid(row=0, column=0, padx=(0, 8))
        self.ingredient_report_picker = ctk.CTkComboBox(db_frame, values=[], width=500)
        self.ingredient_report_picker.grid(row=0, column=1, padx=(0, 8), sticky="ew")
        ctk.CTkButton(db_frame, text="불러오기", command=self.load_selected_ingredient_report,
                      fg_color="#4C9AFF", hover_color="#1F6AA5", width=100).grid(row=0, column=2)
        ctk.CTkButton(db_frame, text="삭제", command=self.delete_selected_ingredient_report,
                      fg_color="#D32F2F", hover_color="#B71C1C", width=80).grid(row=0, column=3)

        self._redraw_report_table()
        # 최근 저장 목록 로드
        self.refresh_ingredient_report_list()

    def delete_selected_ingredient_report(self):
        """선택한 원료목록보고를 DB에서 삭제합니다."""
        if not getattr(self.current_user, 'can_delete', None) or not self.current_user.can_delete():
            messagebox.showwarning("권한 없음", "삭제 권한이 없습니다.", parent=self)
            return
        sel = self.ingredient_report_picker.get()
        if not sel or '|' not in sel:
            messagebox.showwarning("선택 필요", "삭제할 항목을 선택하세요.", parent=self)
            return
        try:
            report_id = int(sel.split('|')[0].strip())
        except Exception:
            messagebox.showwarning("선택 오류", "선택된 항목을 해석할 수 없습니다.", parent=self)
            return
        name_preview = ' | '.join([p.strip() for p in sel.split('|')[1:3]]) if '|' in sel else ''
        if not messagebox.askyesno("삭제 확인", f"선택한 원료목록보고를 삭제하시겠습니까?\n\n{sel}\n\n이 작업은 되돌릴 수 없습니다.", parent=self):
            return
        session = db_manager.get_session()
        try:
            header = session.query(IngredientReport).filter_by(id=report_id).first()
            if not header:
                messagebox.showwarning("오류", "선택한 데이터가 존재하지 않습니다.", parent=self)
                return
            session.delete(header)
            session.commit()
            if self.current_ingredient_report_id == report_id:
                self.current_ingredient_report_id = None
            self.refresh_ingredient_report_list()
            messagebox.showinfo("삭제 완료", "원료목록보고가 삭제되었습니다.", parent=self)
        except Exception as e:
            session.rollback()
            messagebox.showerror("오류", f"삭제 중 오류가 발생했습니다: {e}", parent=self)
        finally:
            session.close()

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
        self.current_ingredient_report_id = None
        messagebox.showinfo("알림", "폼이 초기화되었습니다.", parent=self)

    def _collect_current_ingredient_report_data(self):
        """현재 화면 또는 저장 버퍼의 원료목록 데이터를 수집합니다.
        반환: 리스트[dict]: 각 제품 단위의 헤더 및 아이템 목록
        """
        collected = []
        if self.saved_products:
            # 여러 제품 버퍼를 각각 하나의 보고서로 저장
            for product in self.saved_products:
                collected.append({
                    'product_name': product.get("제품명", ""),
                    'type_code': product.get("유형표시", ""),
                    'functional_type_code': product.get("기능성화장품유형", ""),
                    'functional_code': product.get("기능성화장품품목코드", ""),
                    'manufacturer': product.get("제조업자상호", ""),
                    'usage': product.get("용도", ""),
                    'custom_content': product.get("맞춤형내용물", ""),
                    'ingredients': product.get("원료성분명", [])
                })
        else:
            # 현재 화면 데이터로 단일 저장
            pasted_text = self.bulk_ingredient_entry.get("1.0", "end-1c").strip()
            if ', ' in pasted_text:
                pasted_ingredients = pasted_text.split(', ')
            elif ',' in pasted_text:
                pasted_ingredients = pasted_text.split(',')
            else:
                pasted_ingredients = pasted_text.split('\n')
            pasted_ingredients = [line.strip() for line in pasted_ingredients if line.strip()]

            if not self.report_entries["제품명"].get() or not pasted_ingredients:
                return []

            type_selected = self.report_entries["유형표시"].get()
            type_code = type_selected.split(" : ")[0] if " : " in type_selected else type_selected
            functional_selected = self.report_entries["기능성화장품유형"].get()
            functional_type_code = functional_selected.split(" : ")[0] if " : " in functional_selected else ""
            
            # "없음"이 선택된 경우 기능성 유형과 품목코드를 빈칸으로 처리
            if functional_type_code == "없음":
                functional_type_code = ""
                functional_code = ""
            else:
                functional_code = self.report_entries["기능성화장품품목코드"].get()

            collected.append({
                'product_name': self.report_entries["제품명"].get(),
                'type_code': type_code,
                'functional_type_code': functional_type_code,
                'functional_code': functional_code,
                'manufacturer': self.report_entries["제조업자상호"].get(),
                'usage': self.report_entries.get("용도").get() if self.report_entries.get("용도") else "",
                'custom_content': self.report_entries.get("맞춤형내용물").get() if self.report_entries.get("맞춤형내용물") else "",
                'ingredients': pasted_ingredients
            })
        return collected

    def save_ingredient_report_to_db(self):
        """원료목록보고 현재 데이터를 DB에 저장하거나 업데이트합니다."""
        data_list = self._collect_current_ingredient_report_data()
        if not data_list:
            messagebox.showwarning("입력 오류", "제품명과 원료성분명을 확인해주세요.", parent=self)
            return

        session = db_manager.get_session()
        try:
            saved_count = 0
            # 편집 중인 단일 레코드가 있는 경우 업데이트, 아니면 새로 생성
            if self.current_ingredient_report_id and len(data_list) == 1:
                header = session.query(IngredientReport).filter_by(id=self.current_ingredient_report_id).first()
                if not header:
                    self.current_ingredient_report_id = None  # fallback to create
                else:
                    d = data_list[0]
                    header.product_name = d['product_name']
                    header.manufacturer = d['manufacturer']
                    header.type_code = d['type_code']
                    header.functional_type_code = d['functional_type_code']
                    header.functional_code = d['functional_code']
                    header.usage = d['usage']
                    header.custom_content = d['custom_content']
                    # replace items
                    header.items.clear()
                    for idx, ing in enumerate(d['ingredients'], start=1):
                        header.items.append(IngredientReportItem(row_no=idx, ingredient_name=ing))
                    session.commit()
                    saved_count = 1
            if saved_count == 0:
                # 새 레코드(들) 생성
                for d in data_list:
                    header = IngredientReport(
                        product_name=d['product_name'], manufacturer=d['manufacturer'],
                        type_code=d['type_code'], functional_type_code=d['functional_type_code'],
                        functional_code=d['functional_code'], usage=d['usage'], custom_content=d['custom_content']
                    )
                    for idx, ing in enumerate(d['ingredients'], start=1):
                        header.items.append(IngredientReportItem(row_no=idx, ingredient_name=ing))
                    session.add(header)
                    saved_count += 1
                session.commit()

            self.refresh_ingredient_report_list()
            messagebox.showinfo("저장 완료", f"원료목록보고 {saved_count}건 저장되었습니다.", parent=self)
        except Exception as e:
            session.rollback()
            messagebox.showerror("오류", f"DB 저장 중 오류가 발생했습니다: {e}", parent=self)
        finally:
            session.close()

    def refresh_ingredient_report_list(self):
        """최근 저장된 원료목록보고 목록을 콤보에 로드."""
        try:
            session = db_manager.get_session()
            recs = session.query(IngredientReport).order_by(IngredientReport.created_at.desc()).limit(50).all()
            values = [f"{r.id} | {r.product_name} | {r.manufacturer or ''} | {r.created_at.strftime('%Y-%m-%d %H:%M')}" for r in recs]
            self.ingredient_report_picker.configure(values=values)
            if values:
                self.ingredient_report_picker.set(values[0])
        except Exception as e:
            print(f"[경고] 원료목록보고 목록 로드 실패: {e}")
        finally:
            try:
                session.close()
            except Exception:
                pass

    def load_selected_ingredient_report(self):
        """콤보에서 선택된 원료목록보고를 폼에 로드합니다."""
        sel = self.ingredient_report_picker.get()
        if not sel or '|' not in sel:
            messagebox.showwarning("선택 필요", "불러올 항목을 선택하세요.", parent=self)
            return
        try:
            report_id = int(sel.split('|')[0].strip())
        except Exception:
            messagebox.showwarning("선택 오류", "선택된 항목을 해석할 수 없습니다.", parent=self)
            return
        session = db_manager.get_session()
        try:
            header = session.query(IngredientReport).filter_by(id=report_id).first()
            if not header:
                messagebox.showwarning("오류", "선택한 데이터가 존재하지 않습니다.", parent=self)
                return
            # 폼 채우기
            self.report_entries["제품명"].delete(0, 'end'); self.report_entries["제품명"].insert(0, header.product_name or '')
            self.report_entries["제조업자상호"].delete(0, 'end'); self.report_entries["제조업자상호"].insert(0, header.manufacturer or '')
            # 유형표시 콤보 값 구성과 세팅
            # 대분류는 유지, 소분류 코드만 있는 경우 그대로 세팅 시도
            try:
                # 소분류 전체 값 목록
                main_selected = self.report_entries["유형표시_대분류"].get()
                # 대분류 변경 없이 소분류 값 직접 세팅
                if header.type_code:
                    # value는 "코드 : 이름" 형식이지만 직접 코드만 세팅해도 표시됨
                    self.report_entries["유형표시"].set(header.type_code)
            except Exception:
                pass
            # 기능성 유형 설정 - 빈 문자열이면 "없음"으로 표시
            if header.functional_type_code:
                self.report_entries["기능성화장품유형"].set(header.functional_type_code)
            else:
                self.report_entries["기능성화장품유형"].set("없음 : 기능성화장품 아님")
            
            # 기능성 품목코드 설정
            self.report_entries["기능성화장품품목코드"].delete(0, 'end')
            if header.functional_type_code:  # 기능성 유형이 있을 때만 품목코드 표시
                self.report_entries["기능성화장품품목코드"].insert(0, header.functional_code or '')
            
            self.report_entries["용도"].set(header.usage or '')
            self.report_entries["맞춤형내용물"].set(header.custom_content or '')

            # 테이블
            for row_widgets in self.report_item_rows:
                for key, widget in row_widgets.items():
                    if hasattr(widget, 'destroy'):
                        widget.destroy()
            self.report_item_rows.clear()
            for idx, item in enumerate(sorted(header.items, key=lambda x: (x.row_no or 0, x.id)) , start=1):
                self._add_report_item_row_with_data(
                    row_number=idx,
                    product_name=header.product_name or '',
                    type_code=header.type_code or '',
                    functional_type=header.functional_type_code or '',
                    functional_code=header.functional_code or '',
                    manufacturer=header.manufacturer or '',
                    ingredient=item.ingredient_name or '',
                    usage=header.usage or '',
                    custom_content=header.custom_content or ''
                )
            self.current_ingredient_report_id = header.id
            self.saved_products.clear()
            messagebox.showinfo("불러오기 완료", "원료목록보고 데이터가 로드되었습니다.", parent=self)
        except Exception as e:
            messagebox.showerror("오류", f"불러오기 중 오류가 발생했습니다: {e}", parent=self)
        finally:
            session.close()

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
            try:
                os.startfile(os.path.abspath(file_path))
            except Exception:
                pass

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
            try:
                os.startfile(os.path.abspath(file_path))
            except Exception:
                pass

    def setup_coa_tab(self, tab_frame):
        """COA 탭의 UI를 설정합니다. (서브탭 지연 로딩 적용으로 초고속 진입)"""
        tab_frame.grid_columnconfigure(0, weight=1)
        tab_frame.grid_rowconfigure(0, weight=1)

        self.coa_sub_tab_view = ctk.CTkTabview(
            tab_frame, 
            border_width=1, 
            border_color=("gray80", "gray30"),
            command=self._on_coa_subtab_changed
        )
        self.coa_sub_tab_view.grid(row=0, column=0, padx=10, pady=10, sticky="nsew")

        self.coa_semi_tab_label = self.texts['semi_finished_product_report']
        self.coa_finished_tab_label = "완제품 시험성적서"

        self.coa_sub_tab_view.add(self.coa_semi_tab_label)
        self.coa_sub_tab_view.add(self.coa_finished_tab_label)
        
        self._initialized_coa_subtabs = set()
        # 기본 첫 탭인 반제품 시험성적서만 즉각 초기화 (약 0.15초)
        self.setup_semi_finished_product_tab(self.coa_sub_tab_view.tab(self.coa_semi_tab_label))
        self._initialized_coa_subtabs.add('semi')

    def _on_coa_subtab_changed(self):
        """COA 내부 서브탭 전환 시 완제품 탭 온디맨드 빌드"""
        current_tab = self.coa_sub_tab_view.get()
        if current_tab == self.coa_finished_tab_label and 'finished' not in self._initialized_coa_subtabs:
            self.setup_finished_product_tab(self.coa_sub_tab_view.tab(self.coa_finished_tab_label))
            self._initialized_coa_subtabs.add('finished')

    def setup_semi_finished_product_tab(self, tab_frame):
        """반제품 시험성적서 탭의 UI를 동적으로 재구성합니다."""
        tab_frame.grid_columnconfigure(0, weight=1)
        tab_frame.grid_rowconfigure(0, weight=1)

        scrollable_frame = ctk.CTkScrollableFrame(tab_frame, label_text=self.texts['semi_finished_product_report_title'])
        scrollable_frame.grid(row=0, column=0, sticky="nsew", padx=10, pady=10)
        scrollable_frame.grid_columnconfigure(0, weight=1)

        self.semi_product_entries = {}
        self.coa_item_rows = [] 
        self.current_semi_coa_id = None

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

        ctk.CTkButton(button_frame, text="📊 시험성적서 (KO)", command=lambda: self.generate_semi_product_report(lang="ko")).pack(side="left", padx=5)
        ctk.CTkButton(button_frame, text="🌐 영문 COA (EN)", fg_color="#1565C0", hover_color="#0D47A1", command=lambda: self.generate_semi_product_report(lang="en")).pack(side="left", padx=5)
        ctk.CTkButton(button_frame, text=self.texts['reset'], command=self.clear_semi_product_form, fg_color="gray50", hover_color="gray35").pack(side="left", padx=5)

        # DB 저장/불러오기 UI
        db_frame = ctk.CTkFrame(tab_frame, fg_color="transparent")
        db_frame.grid(row=2, column=0, padx=10, pady=(0, 10), sticky="ew")
        db_frame.grid_columnconfigure(1, weight=1)
        ctk.CTkButton(db_frame, text="DB 저장", command=self.save_semi_coa_to_db,
                      fg_color="#2FA572", hover_color="#106A43", width=120).grid(row=0, column=0, padx=(0, 8))
        self.semi_coa_picker = ctk.CTkComboBox(db_frame, values=[], width=500)
        self.semi_coa_picker.grid(row=0, column=1, padx=(0, 8), sticky="ew")
        ctk.CTkButton(db_frame, text="불러오기", command=self.load_selected_semi_coa,
                      fg_color="#4C9AFF", hover_color="#1F6AA5", width=100).grid(row=0, column=2)
        ctk.CTkButton(db_frame, text="삭제", command=self.delete_selected_semi_coa,
                      fg_color="#D32F2F", hover_color="#B71C1C", width=80).grid(row=0, column=3)

        self._redraw_coa_table()
        self.refresh_semi_coa_list()

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

        self.current_semi_coa_id = None
        messagebox.showinfo(self.texts['notification'], self.texts['form_cleared'], parent=self)

    def _collect_semi_coa_data(self):
        return {
            'product_name': self.semi_product_entries.get("제 품 명").get(),
            'lot_no': self.semi_product_entries.get("LOT").get(),
            'manufacture_date': self.semi_product_entries.get("제조일자").get(),
            'test_date': self.semi_product_entries.get("시험일자").get(),
            'examiner': self.semi_product_entries.get("시험자").get(),
            'overall_result': self.semi_product_entries.get("종합판정").get(),
            'items': [
                {
                    'seq_no': i+1,
                    'item_name': row['name'].get(),
                    'spec': row['criteria'].get(),
                    'result': row['result'].get(),
                    'remark': row['remarks'].get(),
                }
                for i, row in enumerate(self.coa_item_rows)
            ]
        }

    def save_semi_coa_to_db(self):
        data = self._collect_semi_coa_data()
        if not data.get('product_name') or not data.get('overall_result'):
            messagebox.showwarning(self.texts['input_error'], self.texts['required_fields_missing'], parent=self)
            return
        from datetime import datetime
        def to_date(s):
            try:
                # 허용 가능한 몇 가지 포맷 시도
                for fmt in ("%Y-%m-%d", "%Y.%m.%d", "%Y/%m/%d", "%Y%m%d"):
                    try:
                        return datetime.strptime(s.strip(), fmt).date()
                    except Exception:
                        continue
            except Exception:
                pass
            return None
        session = db_manager.get_session()
        try:
            if self.current_semi_coa_id:
                header = session.query(SemiFinishedCOA).filter_by(id=self.current_semi_coa_id).first()
                if not header:
                    self.current_semi_coa_id = None
                else:
                    header.product_name = data['product_name']
                    header.lot_no = data['lot_no']
                    header.manufacture_date = to_date(data['manufacture_date']) if data['manufacture_date'] else None
                    header.test_date = to_date(data['test_date']) if data['test_date'] else None
                    header.examiner = data['examiner']
                    header.overall_result = data['overall_result']
                    header.items.clear()
                    for it in data['items']:
                        header.items.append(SemiFinishedCOAItem(**it))
                    session.commit()
                    messagebox.showinfo(self.texts['success'], "DB에 업데이트되었습니다.", parent=self)
                    self.refresh_semi_coa_list()
                    return
            # create new
            header = SemiFinishedCOA(
                product_name=data['product_name'], lot_no=data['lot_no'],
                manufacture_date=to_date(data['manufacture_date']) if data['manufacture_date'] else None,
                test_date=to_date(data['test_date']) if data['test_date'] else None,
                examiner=data['examiner'], overall_result=data['overall_result']
            )
            for it in data['items']:
                header.items.append(SemiFinishedCOAItem(**it))
            session.add(header)
            session.commit()
            self.current_semi_coa_id = header.id
            self.refresh_semi_coa_list()
            messagebox.showinfo(self.texts['success'], "DB에 저장되었습니다.", parent=self)
        except Exception as e:
            session.rollback()
            messagebox.showerror(self.texts['error'], f"DB 저장 중 오류: {e}", parent=self)
        finally:
            session.close()

    def refresh_semi_coa_list(self):
        try:
            session = db_manager.get_session()
            recs = session.query(SemiFinishedCOA).order_by(SemiFinishedCOA.created_at.desc()).limit(50).all()
            values = [f"{r.id} | {r.product_name} | {r.lot_no or ''} | {r.created_at.strftime('%Y-%m-%d %H:%M')}" for r in recs]
            self.semi_coa_picker.configure(values=values)
            if values:
                self.semi_coa_picker.set(values[0])
        except Exception as e:
            print(f"[경고] 반제품 COA 목록 로드 실패: {e}")
        finally:
            try:
                session.close()
            except Exception:
                pass

    def load_selected_semi_coa(self):
        sel = self.semi_coa_picker.get()
        if not sel or '|' not in sel:
            messagebox.showwarning("선택 필요", "불러올 항목을 선택하세요.", parent=self)
            return
        try:
            header_id = int(sel.split('|')[0].strip())
        except Exception:
            messagebox.showwarning("선택 오류", "선택된 항목을 해석할 수 없습니다.", parent=self)
            return
        session = db_manager.get_session()
        try:
            header = session.query(SemiFinishedCOA).filter_by(id=header_id).first()
            if not header:
                messagebox.showwarning("오류", "선택한 데이터가 존재하지 않습니다.", parent=self)
                return
            # 기본 정보
            for key, entry in self.semi_product_entries.items():
                entry.delete(0, 'end')
            self.semi_product_entries["제 품 명"].insert(0, header.product_name or '')
            self.semi_product_entries["LOT"].insert(0, header.lot_no or '')
            self.semi_product_entries["제조일자"].insert(0, header.manufacture_date.strftime('%Y-%m-%d') if header.manufacture_date else '')
            self.semi_product_entries["시험일자"].insert(0, header.test_date.strftime('%Y-%m-%d') if header.test_date else '')
            self.semi_product_entries["시험자"].insert(0, header.examiner or '')
            self.semi_product_entries["종합판정"].insert(0, header.overall_result or '')

            # 테이블 재구성
            for row_widgets in self.coa_item_rows:
                for widget in row_widgets.values():
                    if isinstance(widget, (ctk.CTkEntry, ctk.CTkLabel, ctk.CTkCheckBox)):
                        widget.destroy()
            self.coa_item_rows.clear()
            for i, it in enumerate(header.items):
                self._add_coa_item_row({
                    'num': str(it.seq_no) if it.seq_no else '',
                    'name': it.item_name or '',
                    'criteria': it.spec or '',
                    'result': it.result or '',
                    'remarks': it.remark or ''
                }, redraw=False)
            self._update_coa_row_numbers()
            self.current_semi_coa_id = header.id
            messagebox.showinfo("불러오기 완료", "반제품 시험성적서가 로드되었습니다.", parent=self)
        except Exception as e:
            messagebox.showerror("오류", f"불러오기 중 오류가 발생했습니다: {e}", parent=self)
        finally:
            session.close()

    def delete_selected_semi_coa(self):
        """선택한 반제품 COA를 DB에서 삭제합니다."""
        if not getattr(self.current_user, 'can_delete', None) or not self.current_user.can_delete():
            messagebox.showwarning("권한 없음", "삭제 권한이 없습니다.", parent=self)
            return
        sel = self.semi_coa_picker.get()
        if not sel or '|' not in sel:
            messagebox.showwarning("선택 필요", "삭제할 항목을 선택하세요.", parent=self)
            return
        try:
            header_id = int(sel.split('|')[0].strip())
        except Exception:
            messagebox.showwarning("선택 오류", "선택된 항목을 해석할 수 없습니다.", parent=self)
            return
        if not messagebox.askyesno("삭제 확인", f"선택한 반제품 시험성적서를 삭제하시겠습니까?\n\n{sel}\n\n이 작업은 되돌릴 수 없습니다.", parent=self):
            return
        session = db_manager.get_session()
        try:
            header = session.query(SemiFinishedCOA).filter_by(id=header_id).first()
            if not header:
                messagebox.showwarning("오류", "선택한 데이터가 존재하지 않습니다.", parent=self)
                return
            session.delete(header)
            session.commit()
            if self.current_semi_coa_id == header_id:
                self.current_semi_coa_id = None
            self.refresh_semi_coa_list()
            messagebox.showinfo("삭제 완료", "반제품 시험성적서가 삭제되었습니다.", parent=self)
        except Exception as e:
            session.rollback()
            messagebox.showerror("오류", f"삭제 중 오류가 발생했습니다: {e}", parent=self)
        finally:
            session.close()

    def generate_semi_product_report(self, lang="ko"):
        """입력된 데이터를 기반으로 반제품 시험성적서(COA) 엑셀 파일을 생성합니다. (국문 / 영문 지원)"""
        is_eng = (lang == "en")
        try:
            kor_data = {key: entry.get() for key, entry in self.semi_product_entries.items()}
            
            if not all(kor_data.get(key) for key in ["제 품 명", "LOT", "종합판정"]):
                messagebox.showwarning(self.texts['input_error'], self.texts['required_fields_missing'], parent=self)
                return

            # 영문 항목명/기준 매핑 딕셔너리
            item_en_map = {
                "성상": ("Appearance", "Matches standard (Homogeneous cream)"),
                "향취": ("Odor", "Matches standard (Characteristic)"),
                "사용감": ("Texture/Feel", "Matches standard"),
                "pH": ("pH (30℃)", "6.50 ± 1.00"),
                "점도": ("Viscosity (30℃)", "33,000 ± 5,000 cps"),
                "비중": ("Specific Gravity (25℃)", "0.980 ± 0.020"),
                "미생물(일반세균)": ("Microbial Count (Total Aerobic)", "≤ 100 cfu/g (mL)"),
                "미생물(효모/곰팡이)": ("Microbial Count (Yeast/Mold)", "≤ 10 cfu/g (mL)"),
                "미생물(대장균)": ("Pathogens (E.coli)", "Negative (Not Detected)"),
            }

            dynamic_test_items = []
            for i, row_widgets in enumerate(self.coa_item_rows):
                raw_name = row_widgets['name'].get()
                raw_spec = row_widgets['criteria'].get()
                raw_res = row_widgets['result'].get()
                raw_rem = row_widgets['remarks'].get()
                
                if is_eng:
                    for k_key, (en_name, en_spec) in item_en_map.items():
                        if k_key in raw_name:
                            raw_name = en_name
                            if not raw_spec or raw_spec == "표준품과 일치":
                                raw_spec = en_spec
                            break
                    if "적합" in raw_res:
                        raw_res = raw_res.replace("적합", "Pass (Complies)")
                    elif "부적합" in raw_res:
                        raw_res = raw_res.replace("부적합", "Fail (Non-compliant)")

                item_data = (
                    row_widgets['num_label'].cget("text"),
                    raw_name,
                    raw_spec,
                    raw_res,
                    raw_rem
                )
                dynamic_test_items.append(item_data)

            wb = Workbook()
            ws1 = wb.active
            ws1.title = "COA (Semi-finished)" if is_eng else "반제품 시험성적서"
            
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
            ws1['A1'] = "CERTIFICATE OF ANALYSIS (Semi-Finished)" if is_eng else "반제품 시험성적서"
            ws1['A1'].font = title_font
            ws1['A1'].alignment = center_align
            
            ws1.merge_cells('B4:C4'); ws1.merge_cells('E4:F4')
            ws1.merge_cells('B5:C5'); ws1.merge_cells('E5:F5')
            ws1['A4'] = "Product Name" if is_eng else "제 품 명"; ws1['B4'] = kor_data.get("제 품 명")
            ws1['D4'] = "Batch / Lot No." if is_eng else "L O T"; ws1['E4'] = kor_data.get("LOT")
            ws1['A5'] = "Mfg. Date" if is_eng else "제조일자"; ws1['B5'] = kor_data.get("제조일자")
            ws1['D5'] = "Test Date" if is_eng else "시험일자"; ws1['E5'] = kor_data.get("시험일자")

            apply_style_to_range(ws1, 'A4:F5', border=thin_border)
            apply_style_to_range(ws1, 'A4:A5', font=label_font, fill=label_fill, alignment=center_align)
            apply_style_to_range(ws1, 'D4:D5', font=label_font, fill=label_fill, alignment=center_align)
            apply_style_to_range(ws1, 'B4:C5', font=cell_font, alignment=left_align)
            apply_style_to_range(ws1, 'E4:F5', font=cell_font, alignment=left_align)

            ws1.append([])
            table_start_row = ws1.max_row + 1
            
            headers = ["No.", "Test Parameters", "Specifications", "Results", "Remarks"] if is_eng else ["구분", "시험항목", "시험기준", "시험결과", "비고"]
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
            overall_val = kor_data.get("종합판정", "")
            if is_eng:
                if "적합" in overall_val: overall_val = "PASS / CONFORMS TO SPECIFICATION"
                elif "부적합" in overall_val: overall_val = "FAIL / NON-CONFORMING"
                
            ws1.append(["Overall Judgment" if is_eng else "종합판정", overall_val])
            current_row = ws1.max_row
            ws1.merge_cells(start_row=current_row, start_column=2, end_row=current_row, end_column=6)
            apply_style_to_range(ws1, f'A{current_row}:F{current_row}', border=thin_border)
            ws1[f'A{current_row}'].font = label_font; ws1[f'A{current_row}'].fill = label_fill; ws1[f'A{current_row}'].alignment = center_align
            ws1[f'B{current_row}'].font = Font(name='맑은 고딕', size=10, bold=True); ws1[f'B{current_row}'].alignment = center_align

            ws1.append(["Tester/Analyst" if is_eng else "시험자", kor_data.get("시험자"), "", "Date" if is_eng else "시험일자", kor_data.get("일자")])
            current_row = ws1.max_row
            ws1.merge_cells(f'B{current_row}:C{current_row}'); ws1.merge_cells(f'E{current_row}:F{current_row}')
            apply_style_to_range(ws1, f'A{current_row}:F{current_row}', border=thin_border)
            apply_style_to_range(ws1, f'A{current_row}', font=label_font, fill=label_fill, alignment=center_align)
            apply_style_to_range(ws1, f'D{current_row}', font=label_font, fill=label_fill, alignment=center_align)
            apply_style_to_range(ws1, f'B{current_row}:C{current_row}', font=cell_font, alignment=center_align)
            apply_style_to_range(ws1, f'E{current_row}:F{current_row}', font=cell_font, alignment=center_align)

            ws1.column_dimensions['A'].width = 16
            ws1.column_dimensions['B'].width = 28
            ws1.column_dimensions['C'].width = 28
            ws1.column_dimensions['D'].width = 16
            ws1.column_dimensions['E'].width = 25
            ws1.column_dimensions['F'].width = 12

            default_filename = f"{kor_data['제 품 명']}_{kor_data['LOT']}_COA_EN.xlsx" if is_eng else f"{kor_data['제 품 명']}_{kor_data['LOT']}_시험성적서.xlsx"
            file_path = fd.asksaveasfilename(
                defaultextension=".xlsx",
                filetypes=[("Excel 통합 문서", "*.xlsx")],
                initialfile=default_filename,
                title="Save COA (English)" if is_eng else self.texts['save_report_as']
            )

            if file_path:
                wb.save(file_path)
                try:
                    os.startfile(os.path.abspath(file_path))
                except Exception:
                    pass

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
        self.current_finished_coa_id = None

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
        ctk.CTkButton(button_frame, text="📊 시험성적서 (KO)", command=lambda: self.generate_finished_product_report(lang="ko"), 
                      fg_color="#3B8ED0", hover_color="#1F6AA5").pack(side="left", padx=5)
        ctk.CTkButton(button_frame, text="🌐 영문 COA (EN)", command=lambda: self.generate_finished_product_report(lang="en"), 
                      fg_color="#1565C0", hover_color="#0D47A1").pack(side="left", padx=5)
        ctk.CTkButton(button_frame, text="초기화", command=self.clear_finished_product_form, 
                      fg_color="gray50", hover_color="gray35").pack(side="left", padx=5)

        # DB 저장/불러오기 UI
        db_frame = ctk.CTkFrame(tab_frame, fg_color="transparent")
        db_frame.grid(row=2, column=0, padx=10, pady=(0, 10), sticky="ew")
        db_frame.grid_columnconfigure(1, weight=1)
        ctk.CTkButton(db_frame, text="DB 저장", command=self.save_finished_coa_to_db,
                      fg_color="#2FA572", hover_color="#106A43", width=120).grid(row=0, column=0, padx=(0, 8))
        self.finished_coa_picker = ctk.CTkComboBox(db_frame, values=[], width=500)
        self.finished_coa_picker.grid(row=0, column=1, padx=(0, 8), sticky="ew")
        ctk.CTkButton(db_frame, text="불러오기", command=self.load_selected_finished_coa,
                      fg_color="#4C9AFF", hover_color="#1F6AA5", width=100).grid(row=0, column=2)
        ctk.CTkButton(db_frame, text="삭제", command=self.delete_selected_finished_coa,
                      fg_color="#D32F2F", hover_color="#B71C1C", width=80).grid(row=0, column=3)

        self._redraw_finished_product_table()
        self.refresh_finished_coa_list()

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
        self.current_finished_coa_id = None
        messagebox.showinfo("알림", "양식이 초기화되었습니다.", parent=self)

    def generate_finished_product_report(self, lang="ko"):
        """입력된 데이터를 기반으로 완제품 시험성적서(COA) 엑셀 파일을 생성합니다. (국문 / 영문 지원)"""
        is_eng = (lang == "en")
        try:
            # 데이터 수집
            info_data = {key: entry.get() for key, entry in self.finished_product_entries.items()}

            if not all(info_data.get(key) for key in ["제 품 명", "완제품제조번호(LOT)", "종합판정"]):
                messagebox.showwarning("입력 오류", "제품명, 완제품 LOT, 종합판정은 필수 입력 항목입니다.", parent=self)
                return

            finished_item_en_map = {
                "성 상": ("Appearance", "Matches standard (Homogeneous cream)"),
                "향 취": ("Odor", "Matches standard (Characteristic)"),
                "이물질": ("Foreign Matter", "None detected"),
                "내용량": ("Net Contents", "≥ 97% of labeled volume"),
                "사용감": ("Application Feel", "Matches standard"),
                "pH": ("pH (25℃)", "5.80 ± 1.00"),
                "점도": ("Viscosity (25℃)", "19,000 ± 4,000 cps"),
                "비중": ("Specific Gravity (25℃)", "1.010 ± 0.050"),
                "외관 및 용기상태": ("Packaging / Container Integrity", "Matches standard"),
                "인쇄상태": ("Label Printing & Legibility", "Legible & Matches standard"),
                "법적 표시사항": ("Regulatory Compliance", "Complies with Cosmetics Act"),
                "아데노신 함량 시험": ("Assay (Adenosine)", "≥ 90.0% of labeled amount (0.04%)"),
                "아데노신 확인 시험": ("Identification (Adenosine)", "Retention time matches reference standard"),
                "미생물(일반세균)": ("Total Aerobic Microbial Count (TAMC)", "≤ 100 cfu/g (mL)"),
                "미생물(진균(효모/곰팡이))": ("Total Combined Yeasts/Molds (TYMC)", "≤ 10 cfu/g (mL)"),
                "미생물(대장균)": ("Pathogens (E.coli)", "Negative (Not Detected)"),
            }

            test_items = []
            for row_widgets in self.finished_item_rows:
                item_id = row_widgets["id_label"].cget("text")
                item = row_widgets["item"].get()
                spec = row_widgets["spec"].get()
                result = row_widgets["result"].get()
                note = row_widgets["note"].get()

                if is_eng:
                    for k_key, (en_name, en_spec) in finished_item_en_map.items():
                        if k_key in item:
                            item = en_name
                            if not spec or "표준품과 일치" in spec or "표준품과 비교" in spec:
                                spec = en_spec
                            break
                    if "적합" in result:
                        result = result.replace("적합", "Pass (Complies)")
                    elif "부적합" in result:
                        result = result.replace("부적합", "Fail (Non-compliant)")

                test_items.append({"id": item_id, "item": item, "spec": spec, "result": result, "note": note})

            # Excel 생성
            wb = Workbook()
            ws = wb.active
            ws.title = "COA (Finished Product)" if is_eng else "완제품 시험성적서"

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
            ws['A1'] = "CERTIFICATE OF ANALYSIS (Finished Product)" if is_eng else "완제품 시험성적서"
            apply_style(ws['A1'], font=title_font, alignment=center_align)

            # 기본 정보
            if is_eng:
                info_layout = [
                    ("Product Name", info_data.get("제 품 명")), ("Bulk Mfg. Date", info_data.get("반제품 제조일자")), ("Bulk Lot No.", info_data.get("반제품제조번호(LOT)")),
                    ("Packaging Date", info_data.get("포장 일자")), ("Finished Lot No.", info_data.get("완제품제조번호(LOT)")), ("Expiry Date", info_data.get("사용 기한")),
                    ("Net Volume (ml)", info_data.get("단위 용량 (ml)")), ("Sampling Method", info_data.get("샘플링 방법")), ("Test Date", info_data.get("시험 일자"))
                ]
            else:
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
            headers = ["No.", "Test Parameters", "Specifications", "Results", "Remarks"] if is_eng else ["구분", "시험항목", "시험기준", "시험결과", "비고"]
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
            apply_style(ws.cell(conclusion_row, 1, "Tester" if is_eng else "시험자"), font=label_font, fill=label_fill, alignment=center_align, border=thin_border)
            apply_style(ws.cell(conclusion_row, 2, info_data.get("시험자")), font=cell_font, alignment=center_align, border=thin_border)
            apply_style(ws.cell(conclusion_row, 3, "Reviewer" if is_eng else "검토자"), font=label_font, fill=label_fill, alignment=center_align, border=thin_border)
            apply_style(ws.cell(conclusion_row, 4, info_data.get("검토자")), font=cell_font, alignment=center_align, border=thin_border)
            ws.cell(conclusion_row, 5).border = thin_border

            conclusion_row += 1
            overall_val = info_data.get("종합판정", "")
            if is_eng:
                if "적합" in overall_val: overall_val = "PASS / CONFORMS TO SPECIFICATION"
                elif "부적합" in overall_val: overall_val = "FAIL / NON-CONFORMING"

            apply_style(ws.cell(conclusion_row, 1, "Overall Judgment" if is_eng else "종합판정"), font=label_font, fill=label_fill, alignment=center_align, border=thin_border)
            ws.merge_cells(start_row=conclusion_row, start_column=2, end_row=conclusion_row, end_column=5)
            apply_style(ws.cell(conclusion_row, 2, overall_val), font=Font(name='맑은 고딕', size=10, bold=True), alignment=center_align, border=thin_border)
            for c in range(3, 6): apply_style(ws.cell(conclusion_row, c), border=thin_border)

            # 열 너비 조정
            ws.column_dimensions['A'].width = 16
            ws.column_dimensions['B'].width = 28
            ws.column_dimensions['C'].width = 32
            ws.column_dimensions['D'].width = 22
            ws.column_dimensions['E'].width = 35

            # 파일 저장
            default_filename = f"{info_data['제 품 명']}_{info_data['완제품제조번호(LOT)']}_COA_Finished_EN.xlsx" if is_eng else f"{info_data['제 품 명']}_{info_data['완제품제조번호(LOT)']}_완제품시험성적서.xlsx"
            file_path = fd.asksaveasfilename(
                defaultextension=".xlsx",
                filetypes=[("Excel 통합 문서", "*.xlsx")],
                initialfile=default_filename,
                title="Save Finished Product COA (English)" if is_eng else "보고서 다른 이름으로 저장"
            )

            if file_path:
                wb.save(file_path)
                try:
                    os.startfile(os.path.abspath(file_path))
                except Exception:
                    pass

        except Exception as e:
            messagebox.showerror("오류" if not is_eng else "Error", f"보고서 생성 중 오류가 발생했습니다:\n{e}", parent=self)

    def _collect_finished_coa_data(self):
        info = {k: e.get() for k, e in self.finished_product_entries.items()}
        items = []
        for row in self.finished_item_rows:
            items.append({
                'item_id': row['id_label'].cget('text'),
                'item_name': row['item'].get(),
                'spec': row['spec'].get(),
                'result': row['result'].get(),
                'note': row['note'].get(),
            })
        return info, items

    def save_finished_coa_to_db(self):
        info, items = self._collect_finished_coa_data()
        if not info.get('제 품 명') or not info.get('완제품제조번호(LOT)') or not info.get('종합판정'):
            messagebox.showwarning("입력 오류", "제품명, 완제품 LOT, 종합판정은 필수입니다.", parent=self)
            return
        from datetime import datetime
        def to_date(s):
            try:
                for fmt in ("%Y-%m-%d", "%Y.%m.%d", "%Y/%m/%d", "%Y%m%d"):
                    try:
                        return datetime.strptime(s.strip(), fmt).date()
                    except Exception:
                        continue
            except Exception:
                pass
            return None
        session = db_manager.get_session()
        try:
            if self.current_finished_coa_id:
                header = session.query(FinishedProductCOA).filter_by(id=self.current_finished_coa_id).first()
                if header:
                    header.product_name = info.get('제 품 명')
                    header.semi_mfg_date = to_date(info.get('반제품 제조일자') or '')
                    header.semi_lot_no = info.get('반제품제조번호(LOT)')
                    header.pack_date = to_date(info.get('포장 일자') or '')
                    header.finished_lot_no = info.get('완제품제조번호(LOT)')
                    header.expiry_date = to_date(info.get('사용 기한') or '')
                    try:
                        header.unit_volume_ml = float(info.get('단위 용량 (ml)') or 0)
                    except Exception:
                        header.unit_volume_ml = None
                    header.sampling_method = info.get('샘플링 방법')
                    header.test_date = to_date(info.get('시험 일자') or '')
                    header.examiner = info.get('시험자')
                    header.reviewer = info.get('검토자')
                    header.overall_result = info.get('종합판정')
                    header.items.clear()
                    for it in items:
                        header.items.append(FinishedProductCOAItem(**it))
                    session.commit()
                    self.refresh_finished_coa_list()
                    messagebox.showinfo("저장 완료", "DB에 업데이트되었습니다.", parent=self)
                    return
                else:
                    self.current_finished_coa_id = None

            header = FinishedProductCOA(
                product_name=info.get('제 품 명'),
                semi_mfg_date=to_date(info.get('반제품 제조일자') or ''),
                semi_lot_no=info.get('반제품제조번호(LOT)'),
                pack_date=to_date(info.get('포장 일자') or ''),
                finished_lot_no=info.get('완제품제조번호(LOT)'),
                expiry_date=to_date(info.get('사용 기한') or ''),
                unit_volume_ml=float(info.get('단위 용량 (ml)')) if (info.get('단위 용량 (ml)') or '').strip().replace('.', '', 1).isdigit() else None,
                sampling_method=info.get('샘플링 방법'),
                test_date=to_date(info.get('시험 일자') or ''),
                examiner=info.get('시험자'),
                reviewer=info.get('검토자'),
                overall_result=info.get('종합판정')
            )
            for it in items:
                header.items.append(FinishedProductCOAItem(**it))
            session.add(header)
            session.commit()
            self.current_finished_coa_id = header.id
            self.refresh_finished_coa_list()
            messagebox.showinfo("저장 완료", "DB에 저장되었습니다.", parent=self)
        except Exception as e:
            session.rollback()
            messagebox.showerror("오류", f"DB 저장 중 오류: {e}", parent=self)
        finally:
            session.close()

    def refresh_finished_coa_list(self):
        try:
            session = db_manager.get_session()
            recs = session.query(FinishedProductCOA).order_by(FinishedProductCOA.created_at.desc()).limit(50).all()
            values = [f"{r.id} | {r.product_name} | {r.finished_lot_no or ''} | {r.created_at.strftime('%Y-%m-%d %H:%M')}" for r in recs]
            self.finished_coa_picker.configure(values=values)
            if values:
                self.finished_coa_picker.set(values[0])
        except Exception as e:
            print(f"[경고] 완제품 COA 목록 로드 실패: {e}")
        finally:
            try:
                session.close()
            except Exception:
                pass

    def load_selected_finished_coa(self):
        sel = self.finished_coa_picker.get()
        if not sel or '|' not in sel:
            messagebox.showwarning("선택 필요", "불러올 항목을 선택하세요.", parent=self)
            return
        try:
            header_id = int(sel.split('|')[0].strip())
        except Exception:
            messagebox.showwarning("선택 오류", "선택된 항목을 해석할 수 없습니다.", parent=self)
            return
        session = db_manager.get_session()
        try:
            header = session.query(FinishedProductCOA).filter_by(id=header_id).first()
            if not header:
                messagebox.showwarning("오류", "선택한 데이터가 존재하지 않습니다.", parent=self)
                return
            # 입력 초기화
            for entry in self.finished_product_entries.values():
                entry.delete(0, 'end')
            # 헤더 채우기
            self.finished_product_entries['제 품 명'].insert(0, header.product_name or '')
            self.finished_product_entries['반제품 제조일자'].insert(0, header.semi_mfg_date.strftime('%Y-%m-%d') if header.semi_mfg_date else '')
            self.finished_product_entries['반제품제조번호(LOT)'].insert(0, header.semi_lot_no or '')
            self.finished_product_entries['포장 일자'].insert(0, header.pack_date.strftime('%Y-%m-%d') if header.pack_date else '')
            self.finished_product_entries['완제품제조번호(LOT)'].insert(0, header.finished_lot_no or '')
            self.finished_product_entries['사용 기한'].insert(0, header.expiry_date.strftime('%Y-%m-%d') if header.expiry_date else '')
            self.finished_product_entries['단위 용량 (ml)'].insert(0, str(header.unit_volume_ml or ''))
            self.finished_product_entries['샘플링 방법'].insert(0, header.sampling_method or '')
            self.finished_product_entries['시험 일자'].insert(0, header.test_date.strftime('%Y-%m-%d') if header.test_date else '')
            self.finished_product_entries['시험자'].insert(0, header.examiner or '')
            self.finished_product_entries['검토자'].insert(0, header.reviewer or '')
            self.finished_product_entries['종합판정'].insert(0, header.overall_result or '')

            # 테이블 재구성
            for row_widgets in self.finished_item_rows[:]:
                for widget in row_widgets.values():
                    if hasattr(widget, 'destroy'):
                        widget.destroy()
            self.finished_item_rows.clear()
            for it in header.items:
                self._add_finished_item_row_with_data({
                    'id': it.item_id or '',
                    'item': it.item_name or '',
                    'spec': it.spec or '',
                    'result': it.result or '',
                    'note': it.note or '',
                })
            if not any(r.get('id_label') and r['id_label'].cget('text') == '특이사항' for r in self.finished_item_rows):
                self._add_special_remarks_row()
            self.current_finished_coa_id = header.id
            messagebox.showinfo("불러오기 완료", "완제품 시험성적서가 로드되었습니다.", parent=self)
        except Exception as e:
            messagebox.showerror("오류", f"불러오기 중 오류가 발생했습니다: {e}", parent=self)
        finally:
            session.close()

    def delete_selected_finished_coa(self):
        """선택한 완제품 COA를 DB에서 삭제합니다."""
        # 권한 확인
        if not getattr(self.current_user, 'can_delete', None) or not self.current_user.can_delete():
            messagebox.showwarning("권한 없음", "삭제 권한이 없습니다.", parent=self)
            return
        # 선택값 파싱
        sel = self.finished_coa_picker.get()
        if not sel or '|' not in sel:
            messagebox.showwarning("선택 필요", "삭제할 항목을 선택하세요.", parent=self)
            return
        try:
            header_id = int(sel.split('|')[0].strip())
        except Exception:
            messagebox.showwarning("선택 오류", "선택된 항목을 해석할 수 없습니다.", parent=self)
            return
        # 확인 다이얼로그
        if not messagebox.askyesno("삭제 확인", f"선택한 완제품 시험성적서를 삭제하시겠습니까?\n\n{sel}\n\n이 작업은 되돌릴 수 없습니다.", parent=self):
            return
        # 삭제 실행
        session = db_manager.get_session()
        try:
            header = session.query(FinishedProductCOA).filter_by(id=header_id).first()
            if not header:
                messagebox.showwarning("오류", "선택한 데이터가 존재하지 않습니다.", parent=self)
                return
            session.delete(header)
            session.commit()
            if self.current_finished_coa_id == header_id:
                self.current_finished_coa_id = None
            self.refresh_finished_coa_list()
            messagebox.showinfo("삭제 완료", "완제품 시험성적서가 삭제되었습니다.", parent=self)
        except Exception as e:
            session.rollback()
            messagebox.showerror("오류", f"삭제 중 오류가 발생했습니다: {e}", parent=self)
        finally:
            session.close()

    # =========================================================================
    # 1. 원료 입고검사성적서 (Raw Material Incoming Inspection Report)
    # =========================================================================
    def setup_material_inspection_tab(self, tab_frame):
        tab_frame.grid_columnconfigure(0, weight=1)
        tab_frame.grid_rowconfigure(0, weight=1)

        scroll = ctk.CTkScrollableFrame(tab_frame, label_text="원료 입고검사성적서 (Raw Material Incoming Test)")
        scroll.grid(row=0, column=0, sticky="nsew", padx=10, pady=10)
        scroll.grid_columnconfigure(0, weight=1)

        self.mat_insp_entries = {}
        self.current_mat_insp_id = None

        # 헤더 & 불러오기 툴바
        top_bar = ctk.CTkFrame(scroll, fg_color="transparent")
        top_bar.grid(row=0, column=0, sticky="ew", padx=10, pady=(5, 15))
        top_bar.grid_columnconfigure(1, weight=1)

        ctk.CTkLabel(top_bar, text="이력 선택:", font=ctk.CTkFont(weight="bold")).grid(row=0, column=0, padx=5, pady=5)
        self.mat_insp_picker = ctk.CTkComboBox(top_bar, values=["-- 저장된 검사성적서 선택 --"], width=350)
        self.mat_insp_picker.grid(row=0, column=1, padx=5, pady=5, sticky="ew")

        ctk.CTkButton(top_bar, text="불러오기", width=80, command=self.load_selected_mat_insp).grid(row=0, column=2, padx=5, pady=5)
        ctk.CTkButton(top_bar, text="새로작성", width=80, fg_color="gray50", command=self.clear_mat_insp_form).grid(row=0, column=3, padx=5, pady=5)
        ctk.CTkButton(top_bar, text="삭제", width=70, fg_color="#D32F2F", hover_color="#B71C1C", command=self.delete_mat_insp).grid(row=0, column=4, padx=5, pady=5)

        # 기본 정보 프레임
        info_frame = ctk.CTkFrame(scroll)
        info_frame.grid(row=1, column=0, sticky="ew", padx=10, pady=5)
        info_frame.grid_columnconfigure((1, 3, 5), weight=1)

        fields = [
            ("원료코드", 0, 0), ("원료명", 0, 2), ("공급업체", 0, 4),
            ("입고일자", 1, 0), ("입고LOT", 1, 2), ("입고수량(kg)", 1, 4),
            ("시험자", 2, 0), ("종합판정", 2, 2), ("포장상태", 2, 4)
        ]

        for label_text, r, c in fields:
            ctk.CTkLabel(info_frame, text=label_text, font=ctk.CTkFont(weight="bold")).grid(row=r, column=c, padx=10, pady=6, sticky="w")
            if label_text == "종합판정":
                cb = ctk.CTkComboBox(info_frame, values=["적합 (Pass)", "부적합 (Fail)", "조건부 적합"], width=160)
                cb.set("적합 (Pass)")
                cb.grid(row=r, column=c+1, padx=10, pady=6, sticky="ew")
                self.mat_insp_entries[label_text] = cb
            elif label_text == "포장상태":
                cb = ctk.CTkComboBox(info_frame, values=["정상 (밀봉양호)", "파손/오염", "라벨불량"], width=160)
                cb.set("정상 (밀봉양호)")
                cb.grid(row=r, column=c+1, padx=10, pady=6, sticky="ew")
                self.mat_insp_entries[label_text] = cb
            else:
                entry = ctk.CTkEntry(info_frame)
                if label_text == "입고일자":
                    entry.insert(0, datetime.now().strftime("%Y-%m-%d"))
                entry.grid(row=r, column=c+1, padx=10, pady=6, sticky="ew")
                self.mat_insp_entries[label_text] = entry

        # 검사 항목 테이블 프레임 (동적 추가/제거 지원)
        self.mat_insp_test_frame = ctk.CTkFrame(scroll)
        self.mat_insp_test_frame.grid(row=2, column=0, sticky="ew", padx=10, pady=15)
        self.mat_insp_test_frame.grid_columnconfigure(1, weight=2)
        self.mat_insp_test_frame.grid_columnconfigure(2, weight=3)
        self.mat_insp_test_frame.grid_columnconfigure(3, weight=2)
        self.mat_insp_test_frame.grid_columnconfigure(4, weight=1)

        # 항목 관리 헤더 툴바
        test_header_bar = ctk.CTkFrame(self.mat_insp_test_frame, fg_color="transparent")
        test_header_bar.grid(row=0, column=0, columnspan=6, sticky="ew", padx=10, pady=(5, 5))
        test_header_bar.grid_columnconfigure(0, weight=1)
        
        ctk.CTkLabel(test_header_bar, text="🧪 시험 항목 및 판정 기준 (자유 추가/제거 가능)", font=ctk.CTkFont(weight="bold", size=13), text_color=("#1F497D", "#38BDF8")).grid(row=0, column=0, sticky="w")
        ctk.CTkButton(test_header_bar, text="➕ 시험 항목 추가", width=120, height=28, fg_color="#0284C7", hover_color="#0369A1", command=lambda: self.add_mat_insp_item_row()).grid(row=0, column=1, padx=5, sticky="e")

        # 테이블 헤더 라벨
        ctk.CTkLabel(self.mat_insp_test_frame, text="NO", font=ctk.CTkFont(weight="bold"), width=35).grid(row=1, column=0, padx=4, pady=5)
        ctk.CTkLabel(self.mat_insp_test_frame, text="시험 항목명", font=ctk.CTkFont(weight="bold")).grid(row=1, column=1, padx=4, pady=5)
        ctk.CTkLabel(self.mat_insp_test_frame, text="시험 기준 (Specification)", font=ctk.CTkFont(weight="bold")).grid(row=1, column=2, padx=4, pady=5)
        ctk.CTkLabel(self.mat_insp_test_frame, text="시험 결과 (Result)", font=ctk.CTkFont(weight="bold")).grid(row=1, column=3, padx=4, pady=5)
        ctk.CTkLabel(self.mat_insp_test_frame, text="판정", font=ctk.CTkFont(weight="bold"), width=70).grid(row=1, column=4, padx=4, pady=5)
        ctk.CTkLabel(self.mat_insp_test_frame, text="관리", font=ctk.CTkFont(weight="bold"), width=50).grid(row=1, column=5, padx=4, pady=5)

        self.mat_insp_item_rows = []
        self._init_default_mat_insp_items()

        # 비고 및 버튼
        note_frame = ctk.CTkFrame(scroll, fg_color="transparent")
        note_frame.grid(row=3, column=0, sticky="ew", padx=10, pady=10)
        note_frame.grid_columnconfigure(1, weight=1)

        ctk.CTkLabel(note_frame, text="특이사항/비고:", font=ctk.CTkFont(weight="bold")).grid(row=0, column=0, padx=10, pady=5, sticky="nw")
        self.mat_insp_note = ctk.CTkTextbox(note_frame, height=60)
        self.mat_insp_note.grid(row=0, column=1, padx=10, pady=5, sticky="ew")

        btn_bar = ctk.CTkFrame(scroll, fg_color="transparent")
        btn_bar.grid(row=4, column=0, sticky="e", padx=10, pady=15)

        ctk.CTkButton(btn_bar, text="💾 DB 저장/수정", width=120, command=self.save_mat_insp_to_db).pack(side="left", padx=5)
        ctk.CTkButton(btn_bar, text="📊 엑셀 성적서 출력", width=140, fg_color="#2E7D32", hover_color="#1B5E20", command=self.export_mat_insp_to_excel).pack(side="left", padx=5)

        self.refresh_mat_insp_list()

    def _init_default_mat_insp_items(self):
        """기본 표준 검사 항목들 로드"""
        self._clear_mat_insp_item_rows()
        default_items = [
            ("성상/외관", "고유의 성상을 띰", "적합", "적합"),
            ("색상", "고유의 색상", "적합", "적합"),
            ("향취", "고유의 취", "적합", "적합"),
            ("굴절률 (20℃)", "1.300 ~ 1.500", "1.334", "적합"),
            ("비중 (20℃)", "0.900 ~ 1.100", "1.002", "적합"),
            ("pH (10% soln)", "4.50 ~ 7.50", "6.20", "적합")
        ]
        for name, spec, res, judge in default_items:
            self.add_mat_insp_item_row(name, spec, res, judge)

    def _clear_mat_insp_item_rows(self):
        for row in self.mat_insp_item_rows:
            for w in row['widgets'].values():
                w.destroy()
        self.mat_insp_item_rows.clear()

    def add_mat_insp_item_row(self, name="", spec="", result="", judge="적합"):
        """새로운 시험 항목 행을 동적으로 추가합니다."""
        row_idx = len(self.mat_insp_item_rows) + 2  # 헤더가 0, 1행 차지
        
        no_lbl = ctk.CTkLabel(self.mat_insp_test_frame, text=str(len(self.mat_insp_item_rows) + 1), width=35)
        no_lbl.grid(row=row_idx, column=0, padx=4, pady=3)
        
        name_entry = ctk.CTkEntry(self.mat_insp_test_frame, placeholder_text="항목명 (예: 순도, 점도, 중금속 등)")
        name_entry.insert(0, name)
        name_entry.grid(row=row_idx, column=1, padx=4, pady=3, sticky="ew")

        spec_entry = ctk.CTkEntry(self.mat_insp_test_frame, placeholder_text="기준 규격")
        spec_entry.insert(0, spec)
        spec_entry.grid(row=row_idx, column=2, padx=4, pady=3, sticky="ew")

        result_entry = ctk.CTkEntry(self.mat_insp_test_frame, placeholder_text="시험 결과")
        result_entry.insert(0, result)
        result_entry.grid(row=row_idx, column=3, padx=4, pady=3, sticky="ew")

        judge_cb = ctk.CTkComboBox(self.mat_insp_test_frame, values=["적합", "부적합", "해당없음"], width=80)
        judge_cb.set(judge)
        judge_cb.grid(row=row_idx, column=4, padx=4, pady=3, sticky="ew")

        del_btn = ctk.CTkButton(
            self.mat_insp_test_frame, text="❌", width=36, height=28,
            fg_color="#EF4444", hover_color="#DC2626",
            command=lambda r_idx=len(self.mat_insp_item_rows): self.delete_mat_insp_item_row(r_idx)
        )
        del_btn.grid(row=row_idx, column=5, padx=4, pady=3)

        row_data = {
            "name": name_entry,
            "spec": spec_entry,
            "result": result_entry,
            "judge": judge_cb,
            "widgets": {
                "no": no_lbl,
                "name": name_entry,
                "spec": spec_entry,
                "result": result_entry,
                "judge": judge_cb,
                "del": del_btn
            }
        }
        self.mat_insp_item_rows.append(row_data)

    def delete_mat_insp_item_row(self, index):
        """특정 인덱스의 시험 항목 행을 삭제하고 재배치합니다."""
        if 0 <= index < len(self.mat_insp_item_rows):
            # 삭제할 행의 위젯 파괴
            for w in self.mat_insp_item_rows[index]['widgets'].values():
                w.destroy()
            self.mat_insp_item_rows.pop(index)
            
            # 남은 행들의 위치 및 번호 재정렬
            for new_idx, row in enumerate(self.mat_insp_item_rows):
                r_num = new_idx + 2
                row['widgets']['no'].configure(text=str(new_idx + 1))
                row['widgets']['no'].grid(row=r_num, column=0, padx=4, pady=3)
                row['widgets']['name'].grid(row=r_num, column=1, padx=4, pady=3, sticky="ew")
                row['widgets']['spec'].grid(row=r_num, column=2, padx=4, pady=3, sticky="ew")
                row['widgets']['result'].grid(row=r_num, column=3, padx=4, pady=3, sticky="ew")
                row['widgets']['judge'].grid(row=r_num, column=4, padx=4, pady=3, sticky="ew")
                row['widgets']['del'].configure(command=lambda i=new_idx: self.delete_mat_insp_item_row(i))
                row['widgets']['del'].grid(row=r_num, column=5, padx=4, pady=3)

    def refresh_mat_insp_list(self):
        try:
            session = db_manager.get_session()
            recs = session.query(MaterialInspectionReport).order_by(MaterialInspectionReport.created_at.desc()).limit(50).all()
            vals = [f"{r.id} | {r.material_name} ({r.material_code}) | LOT:{r.lot_no or ''} | {r.overall_result}" for r in recs]
            self.mat_insp_picker.configure(values=vals if vals else ["-- 저장된 검사성적서 없음 --"])
            if vals: self.mat_insp_picker.set(vals[0])
            session.close()
        except Exception as e:
            print(f"[경고] 원료 입고검사 목록 로드 실패: {e}")

    def load_selected_mat_insp(self):
        sel = self.mat_insp_picker.get()
        if not sel or '|' not in sel: return
        rec_id = int(sel.split('|')[0].strip())
        session = db_manager.get_session()
        try:
            r = session.query(MaterialInspectionReport).get(rec_id)
            if not r: return
            self.current_mat_insp_id = r.id
            self.mat_insp_entries["원료코드"].delete(0, "end"); self.mat_insp_entries["원료코드"].insert(0, r.material_code or "")
            self.mat_insp_entries["원료명"].delete(0, "end"); self.mat_insp_entries["원료명"].insert(0, r.material_name or "")
            self.mat_insp_entries["공급업체"].delete(0, "end"); self.mat_insp_entries["공급업체"].insert(0, r.supplier_name or "")
            self.mat_insp_entries["입고일자"].delete(0, "end"); self.mat_insp_entries["입고일자"].insert(0, str(r.incoming_date or ""))
            self.mat_insp_entries["입고LOT"].delete(0, "end"); self.mat_insp_entries["입고LOT"].insert(0, r.lot_no or "")
            self.mat_insp_entries["입고수량(kg)"].delete(0, "end"); self.mat_insp_entries["입고수량(kg)"].insert(0, str(r.incoming_amount_kg or ""))
            self.mat_insp_entries["시험자"].delete(0, "end"); self.mat_insp_entries["시험자"].insert(0, r.examiner or "")
            self.mat_insp_entries["종합판정"].set(r.overall_result or "적합 (Pass)")
            self.mat_insp_entries["포장상태"].set(r.packaging_status or "정상 (밀봉양호)")
            
            # 시험 항목들 로드
            self._clear_mat_insp_item_rows()
            if r.test_items_json:
                import json
                try:
                    items_list = json.loads(r.test_items_json)
                    for it in items_list:
                        self.add_mat_insp_item_row(it.get('name', ''), it.get('spec', ''), it.get('result', ''), it.get('judge', '적합'))
                except Exception:
                    self._init_default_mat_insp_items()
            else:
                # 레거시 단일 필드 호환
                self.add_mat_insp_item_row("성상/외관", r.appearance_spec or "고유의 성상을 띰", r.appearance_result or "적합")
                self.add_mat_insp_item_row("색상", r.color_spec or "고유의 색상", r.color_result or "적합")
                self.add_mat_insp_item_row("향취", r.odor_spec or "고유의 취", r.odor_result or "적합")
                self.add_mat_insp_item_row("굴절률 (20℃)", "1.300 ~ 1.500", r.refractive_index or "1.334")
                self.add_mat_insp_item_row("비중 (20℃)", "0.900 ~ 1.100", r.specific_gravity or "1.002")
                self.add_mat_insp_item_row("pH (10% soln)", "4.50 ~ 7.50", r.ph_val or "6.20")

            self.mat_insp_note.delete("1.0", "end")
            self.mat_insp_note.insert("1.0", r.notes or "")
            messagebox.showinfo("불러오기 완료", f"원료 입고검사성적서 '{r.material_name}' 데이터를 불러왔습니다.", parent=self)
        finally:
            session.close()

    def clear_mat_insp_form(self):
        self.current_mat_insp_id = None
        for k, e in self.mat_insp_entries.items():
            if isinstance(e, ctk.CTkComboBox): e.set(e.cget("values")[0])
            else:
                e.delete(0, "end")
                if k == "입고일자": e.insert(0, datetime.now().strftime("%Y-%m-%d"))
        self._init_default_mat_insp_items()
        self.mat_insp_note.delete("1.0", "end")

    def save_mat_insp_to_db(self):
        mat_name = self.mat_insp_entries["원료명"].get().strip()
        mat_code = self.mat_insp_entries["원료코드"].get().strip()
        if not mat_name or not mat_code:
            messagebox.showwarning("입력 필요", "원료코드와 원료명은 필수입니다.", parent=self); return

        import json
        items_payload = []
        for row in self.mat_insp_item_rows:
            i_name = row['name'].get().strip()
            if i_name:
                items_payload.append({
                    "name": i_name,
                    "spec": row['spec'].get().strip(),
                    "result": row['result'].get().strip(),
                    "judge": row['judge'].get().strip()
                })

        session = db_manager.get_session()
        try:
            r = session.query(MaterialInspectionReport).get(self.current_mat_insp_id) if self.current_mat_insp_id else MaterialInspectionReport()
            r.material_code = mat_code
            r.material_name = mat_name
            r.supplier_name = self.mat_insp_entries["공급업체"].get().strip()
            
            try: r.incoming_date = datetime.strptime(self.mat_insp_entries["입고일자"].get().strip(), "%Y-%m-%d").date()
            except: r.incoming_date = None
            
            r.lot_no = self.mat_insp_entries["입고LOT"].get().strip()
            try: r.incoming_amount_kg = float(self.mat_insp_entries["입고수량(kg)"].get().strip())
            except: r.incoming_amount_kg = 0.0
            
            r.examiner = self.mat_insp_entries["시험자"].get().strip()
            r.overall_result = self.mat_insp_entries["종합판정"].get().strip()
            r.packaging_status = self.mat_insp_entries["포장상태"].get().strip()
            
            # 동적 항목 전체 JSON 저장
            r.test_items_json = json.dumps(items_payload, ensure_ascii=False)
            r.notes = self.mat_insp_note.get("1.0", "end-1c").strip()

            if not self.current_mat_insp_id:
                session.add(r)
            session.commit()
            self.current_mat_insp_id = r.id
            self.refresh_mat_insp_list()
            messagebox.showinfo("저장 완료", "원료 입고검사성적서가 DB에 성공적으로 저장되었습니다.", parent=self)
        except Exception as e:
            session.rollback()
            messagebox.showerror("오류", f"저장 실패: {e}", parent=self)
        finally:
            session.close()

    def delete_mat_insp(self):
        if not self.current_mat_insp_id:
            messagebox.showwarning("선택 오류", "삭제할 항목을 먼저 불러오세요.", parent=self); return
        if not messagebox.askyesno("삭제 확인", "선택한 원료 입고검사성적서를 삭제하시겠습니까?", parent=self): return
        session = db_manager.get_session()
        try:
            r = session.query(MaterialInspectionReport).get(self.current_mat_insp_id)
            if r:
                session.delete(r)
                session.commit()
                self.clear_mat_insp_form()
                self.refresh_mat_insp_list()
                messagebox.showinfo("완료", "삭제되었습니다.", parent=self)
        finally:
            session.close()

    def export_mat_insp_to_excel(self):
        mat_name = self.mat_insp_entries["원료명"].get().strip() or "원료"
        wb = Workbook()
        ws = wb.active
        ws.title = "원료입고검사성적서"
        
        ws.merge_cells("A1:E2")
        ws["A1"] = f"원료 입고검사성적서 ({mat_name})"
        ws["A1"].font = Font(name="맑은 고딕", size=16, bold=True, color="1F497D")
        ws["A1"].alignment = Alignment(horizontal="center", vertical="center")

        ws.append([])
        ws.append(["원료코드", self.mat_insp_entries["원료코드"].get(), "", "입고일자", self.mat_insp_entries["입고일자"].get()])
        ws.append(["원료명", mat_name, "", "입고LOT", self.mat_insp_entries["입고LOT"].get()])
        ws.append(["공급업체", self.mat_insp_entries["공급업체"].get(), "", "입고수량(kg)", self.mat_insp_entries["입고수량(kg)"].get()])
        ws.append(["포장상태", self.mat_insp_entries["포장상태"].get(), "", "종합판정", self.mat_insp_entries["종합판정"].get()])
        ws.append([])
        ws.append(["NO", "시험 항목", "시험 기준", "시험 결과", "판정"])
        
        for idx, row in enumerate(self.mat_insp_item_rows, 1):
            ws.append([idx, row['name'].get(), row['spec'].get(), row['result'].get(), row['judge'].get()])

        file_path = fd.asksaveasfilename(defaultextension=".xlsx", filetypes=[("Excel Files", "*.xlsx")], initialfile=f"원료입고검사_{mat_name}.xlsx", title="성적서 엑셀 저장")
        if file_path:
            wb.save(file_path)
            messagebox.showinfo("완료", f"성적서가 저장되었습니다:\n{file_path}", parent=self)
            try: os.startfile(os.path.abspath(file_path))
            except: pass

    # =========================================================================
    # 2. 완제품/반제품 제품표준서 (Product Specification Standard) - CGMP 12대 공식 규격서
    # =========================================================================
    def setup_product_standard_tab(self, tab_frame):
        tab_frame.grid_columnconfigure(0, weight=1)
        tab_frame.grid_rowconfigure(0, weight=1)

        scroll = ctk.CTkScrollableFrame(tab_frame, label_text="제품표준서 (Product Specification Standard - CGMP 12대 공식 규격서)")
        scroll.grid(row=0, column=0, sticky="nsew", padx=10, pady=10)
        scroll.grid_columnconfigure(0, weight=1)

        self.prod_std_entries = {}
        self.current_prod_std_id = None

        # 상단 툴바 & 이력/연동
        top_bar = ctk.CTkFrame(scroll, fg_color="transparent")
        top_bar.grid(row=0, column=0, sticky="ew", padx=10, pady=(5, 10))
        top_bar.grid_columnconfigure(1, weight=1)

        ctk.CTkLabel(top_bar, text="표준서 이력:", font=ctk.CTkFont(weight="bold")).grid(row=0, column=0, padx=5, pady=5)
        self.prod_std_picker = ctk.CTkComboBox(top_bar, values=["-- 저장된 제품표준서 선택 --"], width=300)
        self.prod_std_picker.grid(row=0, column=1, padx=5, pady=5, sticky="ew")

        ctk.CTkButton(top_bar, text="불러오기", width=75, command=self.load_selected_prod_std).grid(row=0, column=2, padx=4, pady=5)
        ctk.CTkButton(top_bar, text="처방연동", width=75, fg_color="#6A1B9A", hover_color="#4A148C", command=self.import_from_formulation_to_prod_std).grid(row=0, column=3, padx=4, pady=5)
        ctk.CTkButton(top_bar, text="새로작성", width=75, fg_color="gray50", command=self.clear_prod_std_form).grid(row=0, column=4, padx=4, pady=5)
        ctk.CTkButton(top_bar, text="삭제", width=65, fg_color="#D32F2F", command=self.delete_prod_std).grid(row=0, column=5, padx=4, pady=5)

        # 5대 세부 규격 서브 탭뷰
        self.prod_std_subtabs = ctk.CTkTabview(scroll, height=480)
        self.prod_std_subtabs.grid(row=1, column=0, sticky="nsew", padx=10, pady=5)
        
        tab_p1 = self.prod_std_subtabs.add("1. 제품개요 및 참고사항")
        tab_p2 = self.prod_std_subtabs.add("2. 원료성분 기준 및 함량표")
        tab_p3 = self.prod_std_subtabs.add("3. 공정규격 및 제조공정(SOP)")
        tab_p4 = self.prod_std_subtabs.add("4. 완제품 시험기준 및 규격")
        tab_p5 = self.prod_std_subtabs.add("5. 제품사양 및 포장자재")

        # =====================================================================
        # Part 1: 제품개요 및 참고사항 (하이브리드 ComboBox + Entry)
        # =====================================================================
        tab_p1.grid_columnconfigure((1, 3), weight=1)
        p1_combos = {
            "화장품유형": ["기초화장용 제품류 (로션/크림)", "세정용 제품류 (클렌저/바디워시)", "두발용 제품류 (샴푸/린스)", "면도용 제품류 (쉐이빙 젤/폼)", "직접 입력"],
            "기능성 여부": ["해당사항없음 (일반화장품)", "주름개선 기능성화장품 (보고 완료)", "미백 기능성화장품 (보고 완료)", "미백·주름개선 2중 기능성", "자외선차단 기능성화장품", "직접 입력"],
            "사용기한(개봉전)": ["제조일로부터 36개월", "제조일로부터 24개월", "제조일로부터 12개월", "직접 입력"],
            "개봉후 사용기간": ["개봉 후 12개월", "개봉 후 6개월", "개봉 후 24개월", "직접 입력"],
            "보관조건": ["통풍이 잘되는 차광된 장소에서 상온(1~30℃) 보관", "직사광선을 피하고 서늘한 곳에 밀폐 보관", "직접 입력"],
            "효능/효과": ["피부 보습 및 장벽 강화, 진정", "피부 보습 및 주름개선", "피부 미백 및 톤 케어", "자료없음", "직접 입력"]
        }
        p1_fields = [
            ("제품명(국문)", 0, 0), ("제품명(영문)", 0, 2),
            ("제품코드", 1, 0), ("화장품유형", 1, 2),
            ("의뢰/판매업체", 2, 0), ("포장용량", 2, 2),
            ("효능/효과", 3, 0), ("기능성 여부", 3, 2),
            ("사용기한(개봉전)", 4, 0), ("개봉후 사용기간", 4, 2),
            ("보관조건", 5, 0), ("용법/용량", 5, 2)
        ]
        for lbl, r, c in p1_fields:
            ctk.CTkLabel(tab_p1, text=lbl, font=ctk.CTkFont(weight="bold")).grid(row=r, column=c, padx=10, pady=6, sticky="w")
            if lbl in p1_combos:
                cb = ctk.CTkComboBox(tab_p1, values=p1_combos[lbl])
                cb.set(p1_combos[lbl][0])
                cb.grid(row=r, column=c+1, padx=10, pady=6, sticky="ew")
                self.prod_std_entries[lbl] = cb
            else:
                ent = ctk.CTkEntry(tab_p1, placeholder_text=f"{lbl} 입력")
                ent.grid(row=r, column=c+1, padx=10, pady=6, sticky="ew")
                self.prod_std_entries[lbl] = ent

        # =====================================================================
        # Part 2: 원료 성분 기준 및 함량 (표준 표 Grid + 직접 추가/삭제)
        # =====================================================================
        tab_p2.grid_columnconfigure(0, weight=1)
        p2_header_bar = ctk.CTkFrame(tab_p2, fg_color="transparent")
        p2_header_bar.grid(row=0, column=0, sticky="ew", padx=8, pady=(5, 4))
        p2_header_bar.grid_columnconfigure(0, weight=1)

        ctk.CTkLabel(p2_header_bar, text="📋 [원료 성분 기준 및 함량표 (100g당 / Phase별 표준 표)]", font=ctk.CTkFont(weight="bold", size=13), text_color=("#1F497D", "#38BDF8")).grid(row=0, column=0, sticky="w")
        
        p2_btn_box = ctk.CTkFrame(p2_header_bar, fg_color="transparent")
        p2_btn_box.grid(row=0, column=1, sticky="e")
        ctk.CTkButton(p2_btn_box, text="➕ 원료 행 추가", width=100, height=26, fg_color="#0284C7", hover_color="#0369A1", command=self.add_prod_std_ingredient_row).pack(side="left", padx=3)
        ctk.CTkButton(p2_btn_box, text="➖ 선택 행 삭제", width=100, height=26, fg_color="#EF4444", hover_color="#DC2626", command=self.remove_selected_prod_std_ingredient_row).pack(side="left", padx=3)

        self.prod_std_sec2_table_frame = ctk.CTkFrame(tab_p2)
        self.prod_std_sec2_table_frame.grid(row=1, column=0, padx=8, pady=5, sticky="nsew")
        self.prod_std_sec2_table_frame.grid_columnconfigure(0, weight=0) # 선택
        self.prod_std_sec2_table_frame.grid_columnconfigure(1, weight=1) # Phase
        self.prod_std_sec2_table_frame.grid_columnconfigure(2, weight=2) # 원료코드
        self.prod_std_sec2_table_frame.grid_columnconfigure(3, weight=3) # 원료명
        self.prod_std_sec2_table_frame.grid_columnconfigure(4, weight=3) # INCI명/허가명
        self.prod_std_sec2_table_frame.grid_columnconfigure(5, weight=2) # 시험기준
        self.prod_std_sec2_table_frame.grid_columnconfigure(6, weight=2) # 배합비(%)

        p2_headers = ["선택", "Phase", "원료코드", "원료명", "허가명 (INCI)", "시험기준", "함량 (%)"]
        for idx, h_text in enumerate(p2_headers):
            ctk.CTkLabel(self.prod_std_sec2_table_frame, text=h_text, font=ctk.CTkFont(weight="bold"), fg_color=("gray85", "gray20"), corner_radius=0).grid(row=0, column=idx, sticky="ew", padx=1, pady=1)

        self.prod_std_ingredient_rows = []

        # 레거시 백업 텍스트박스 (숨김/내부용)
        self.prod_std_formula_snap = ctk.CTkTextbox(tab_p2, height=1)

        # =====================================================================
        # Part 3: 공정규격 및 제조공정 관리기준(SOP)
        # =====================================================================
        tab_p3.grid_columnconfigure(0, weight=1)
        tab_p3.grid_rowconfigure(1, weight=1)
        ctk.CTkLabel(tab_p3, text="[단계별 제조공정 지침, 투입온도(℃), RPM 교반조건, 여과 및 공정검사(IPC) 관리기준 (직접 추가/편집 가능)]:", font=ctk.CTkFont(weight="bold")).grid(row=0, column=0, padx=10, pady=5, sticky="w")
        self.prod_std_mfg_summary = ctk.CTkTextbox(tab_p3, height=350)
        self.prod_std_mfg_summary.grid(row=1, column=0, padx=10, pady=5, sticky="nsew")
        self.prod_std_mfg_summary.insert("1.0", "[1. Phase A 수상공정]\n- 정제수 및 보습제 투입 후 75~80℃ 가열, 패들 25~30 RPM 교반 용해\n\n[2. Phase B 유상공정]\n- 유화제 및 왁스/오일류 75~80℃ 가열 완전 용해 확인\n\n[3. 유화 및 균질화 공정]\n- 메인 가마에 Phase B 서서히 투입\n- 호모믹서 3,500~3,800 RPM (5분간 고속 유화) / 아지믹서 25 RPM 병행\n- 진공도 -0.08 MPa 감압 탈포 진행\n\n[4. 냉각 및 후첨가 Phase C]\n- 45℃까지 서서히 감온 (냉각수 순환)\n- Phase C 첨가제 및 향료 투입 후 15분간 균일 분산\n\n[5. 완제품 여과 및 보관]\n- 100 mesh SUS 여과망 통과 후 전용 SUS 드럼에 밀폐 포장 이송")

        # =====================================================================
        # Part 4: 완제품 시험기준 및 규격 (하이브리드 ComboBox + 직접 입력)
        # =====================================================================
        tab_p4.grid_columnconfigure((1, 3), weight=1)
        p4_combos = {
            "성상기준": ["고유의 성상을 가진 유백색의 크림 제형", "무색 투명 겔상", "투명한 액상 제형", "직접 입력"],
            "색상기준": ["유백색 또는 고유의 미황색", "무색 투명", "미백색", "직접 입력"],
            "향취기준": ["고유의 은은한 플로럴 향취", "무취", "특이취", "자사 표준품과 동일", "직접 입력"],
            "pH규격(25℃)": ["5.50 ± 1.00 (pH Meter)", "5.50 ~ 7.00", "6.00 ± 0.50", "직접 입력"],
            "점도규격(cps)": ["12,000 ± 3,000 cps (Helipath, 50rpm, Spindle-E, 1min)", "30,000 ~ 50,000 cps", "19,000 ± 4,000 cps", "직접 입력"],
            "비중규격(25℃)": ["1.010 ± 0.050 (비중병)", "0.980 ~ 1.020", "1.000 ± 0.050", "직접 입력"],
            "중금속(납/비소/수은)": ["납 20ppm 이하, 비소 10ppm 이하, 수은 1ppm 이하", "화장품 안전기준 적합", "직접 입력"],
            "미생물한도규격": ["총호기성생균수 100 CFU/g 이하, 대장균/녹농균/황색포도상구균 불검출", "일반세균 100cfu/ml 이하, 진균 불검출", "직접 입력"]
        }
        p4_fields = [
            ("성상기준", 0, 0), ("색상기준", 0, 2),
            ("향취기준", 1, 0), ("pH규격(25℃)", 1, 2),
            ("점도규격(cps)", 2, 0), ("비중규격(25℃)", 2, 2),
            ("중금속(납/비소/수은)", 3, 0), ("미생물한도규격", 3, 2)
        ]
        for lbl, r, c in p4_fields:
            ctk.CTkLabel(tab_p4, text=lbl, font=ctk.CTkFont(weight="bold")).grid(row=r, column=c, padx=10, pady=8, sticky="w")
            cb = ctk.CTkComboBox(tab_p4, values=p4_combos[lbl])
            cb.set(p4_combos[lbl][0])
            cb.grid(row=r, column=c+1, padx=10, pady=8, sticky="ew")
            self.prod_std_entries[lbl] = cb

        # =====================================================================
        # Part 5: 제품사양 및 포장자재 (하이브리드 ComboBox + 직접 입력)
        # =====================================================================
        tab_p5.grid_columnconfigure((1, 3), weight=1)
        p5_combos = {
            "1차 용기재질/사양": ["튜브 250ml (외관 스크래치/이물 무)", "50ml 헤비블로우 PET 용기", "100ml 유리용기", "직접 입력"],
            "펌프/캡 토출규격": ["원터치 캡 (누액 무)", "PP 에어리스 펌프 (1회 토출량: 0.20 ± 0.03g)", "스프레이 미스트 펌프", "직접 입력"],
            "2차 포장(단상자)": ["FSC 인증 CCP 350g 단상자 (금박 코팅)", "골판지 카톤박스 포장", "해당없음", "직접 입력"],
            "포장 표시사항 기준": ["화장품법 제10조 전성분/바코드/제조번호/사용기한 완전 표시", "법적 규정에 적합", "직접 입력"],
            "운송/취급 주의사항": ["낙하 충격 방지, 고온 다습 환경 노출 금지", "직사광선 차단 및 실온 운송", "직접 입력"]
        }
        p5_fields = [
            ("1차 용기재질/사양", 0, 0), ("펌프/캡 토출규격", 0, 2),
            ("2차 포장(단상자)", 1, 0), ("포장 표시사항 기준", 1, 2),
            ("운송/취급 주의사항", 2, 0), ("수율 기준", 2, 2)
        ]
        for lbl, r, c in p5_fields:
            ctk.CTkLabel(tab_p5, text=lbl, font=ctk.CTkFont(weight="bold")).grid(row=r, column=c, padx=10, pady=8, sticky="w")
            if lbl in p5_combos:
                cb = ctk.CTkComboBox(tab_p5, values=p5_combos[lbl])
                cb.set(p5_combos[lbl][0])
                cb.grid(row=r, column=c+1, padx=10, pady=8, sticky="ew")
                self.prod_std_entries[lbl] = cb
            else:
                ent = ctk.CTkEntry(tab_p5, placeholder_text=f"{lbl} 입력 (예: 충진 포장 수율기준 95% 이상)")
                ent.grid(row=r, column=c+1, padx=10, pady=8, sticky="ew")
                self.prod_std_entries[lbl] = ent

        btn_bar = ctk.CTkFrame(scroll, fg_color="transparent")
        btn_bar.grid(row=2, column=0, sticky="e", padx=10, pady=15)
        ctk.CTkButton(btn_bar, text="💾 표준서 DB 저장", width=120, command=self.save_prod_std_to_db).pack(side="left", padx=5)
        ctk.CTkButton(btn_bar, text="📊 국문 표준서 엑셀 (12대 공식 서식)", width=180, fg_color="#2E7D32", hover_color="#1B5E20", command=lambda: self.export_prod_std_to_excel("ko")).pack(side="left", padx=5)
        ctk.CTkButton(btn_bar, text="🌐 영문 표준서 엑셀 (Product Spec)", width=180, fg_color="#1565C0", hover_color="#0D47A1", command=lambda: self.export_prod_std_to_excel("en")).pack(side="left", padx=5)

        ws["A1"].font = Font(name="맑은 고딕", size=16, bold=True, color="1F497D")
        ws["A1"].alignment = Alignment(horizontal="center", vertical="center")

        ws.append([])
        ws.append(["원료코드", self.mat_insp_entries["원료코드"].get(), "", "입고일자", self.mat_insp_entries["입고일자"].get()])
        ws.append(["원료명", mat_name, "", "입고LOT", self.mat_insp_entries["입고LOT"].get()])
        ws.append(["공급업체", self.mat_insp_entries["공급업체"].get(), "", "입고수량(kg)", self.mat_insp_entries["입고수량(kg)"].get()])
        ws.append(["포장상태", self.mat_insp_entries["포장상태"].get(), "", "종합판정", self.mat_insp_entries["종합판정"].get()])
        ws.append([])
        ws.append(["NO", "시험 항목", "시험 기준", "시험 결과", "판정"])
        
        for idx, row in enumerate(self.mat_insp_item_rows, 1):
            ws.append([idx, row['name'].get(), row['spec'].get(), row['result'].get(), row['judge'].get()])

        file_path = fd.asksaveasfilename(defaultextension=".xlsx", filetypes=[("Excel Files", "*.xlsx")], initialfile=f"원료입고검사_{mat_name}.xlsx", title="성적서 엑셀 저장")
        if file_path:
            wb.save(file_path)
            messagebox.showinfo("완료", f"성적서가 저장되었습니다:\n{file_path}", parent=self)
            try: os.startfile(os.path.abspath(file_path))
            except: pass

        session = db_manager.get_session()
        try:
            r = session.query(MaterialInspectionReport).get(self.current_mat_insp_id) if self.current_mat_insp_id else MaterialInspectionReport()
            r.material_code = mat_code
            r.material_name = mat_name
            r.supplier_name = self.mat_insp_entries["공급업체"].get().strip()
            
            try: r.incoming_date = datetime.strptime(self.mat_insp_entries["입고일자"].get().strip(), "%Y-%m-%d").date()
            except: r.incoming_date = None
            
            r.lot_no = self.mat_insp_entries["입고LOT"].get().strip()
            try: r.incoming_amount_kg = float(self.mat_insp_entries["입고수량(kg)"].get().strip())
            except: r.incoming_amount_kg = 0.0
            
            r.examiner = self.mat_insp_entries["시험자"].get().strip()
            r.overall_result = self.mat_insp_entries["종합판정"].get().strip()
            r.packaging_status = self.mat_insp_entries["포장상태"].get().strip()
            
            r.appearance_spec = self.mat_insp_item_entries["성상/외관"]["spec"].get().strip()
            r.appearance_result = self.mat_insp_item_entries["성상/외관"]["result"].get().strip()
            r.color_spec = self.mat_insp_item_entries["색상"]["spec"].get().strip()
            r.color_result = self.mat_insp_item_entries["색상"]["result"].get().strip()
            r.odor_spec = self.mat_insp_item_entries["향취"]["spec"].get().strip()
            r.odor_result = self.mat_insp_item_entries["향취"]["result"].get().strip()
            r.refractive_index = self.mat_insp_item_entries["굴절률 (20℃)"]["result"].get().strip()
            r.specific_gravity = self.mat_insp_item_entries["비중 (20℃)"]["result"].get().strip()
            r.ph_val = self.mat_insp_item_entries["pH (10% soln)"]["result"].get().strip()
            r.notes = self.mat_insp_note.get("1.0", "end-1c").strip()

            if not self.current_mat_insp_id:
                session.add(r)
            session.commit()
            self.current_mat_insp_id = r.id
            self.refresh_mat_insp_list()
            messagebox.showinfo("저장 완료", "원료 입고검사성적서가 DB에 성공적으로 저장되었습니다.", parent=self)
        except Exception as e:
            session.rollback()
            messagebox.showerror("오류", f"저장 실패: {e}", parent=self)
        finally:
            session.close()

    def delete_mat_insp(self):
        if not self.current_mat_insp_id:
            messagebox.showwarning("선택 오류", "삭제할 항목을 먼저 불러오세요.", parent=self); return
        if not messagebox.askyesno("삭제 확인", "선택한 원료 입고검사성적서를 삭제하시겠습니까?", parent=self): return
        session = db_manager.get_session()
        try:
            r = session.query(MaterialInspectionReport).get(self.current_mat_insp_id)
            if r:
                session.delete(r)
                session.commit()
                self.clear_mat_insp_form()
                self.refresh_mat_insp_list()
                messagebox.showinfo("완료", "삭제되었습니다.", parent=self)
        finally:
            session.close()

    def export_mat_insp_to_excel(self):
        mat_name = self.mat_insp_entries["원료명"].get().strip() or "원료"
        wb = Workbook()
        ws = wb.active
        ws.title = "원료입고검사성적서"
        
        ws.merge_cells("A1:E2")
        ws["A1"] = f"원료 입고검사성적서 ({mat_name})"
        ws["A1"].font = Font(name="맑은 고딕", size=16, bold=True, color="1F497D")
        ws["A1"].alignment = Alignment(horizontal="center", vertical="center")

        ws.append([])
        ws.append(["원료코드", self.mat_insp_entries["원료코드"].get(), "", "입고일자", self.mat_insp_entries["입고일자"].get()])
        ws.append(["원료명", mat_name, "", "입고LOT", self.mat_insp_entries["입고LOT"].get()])
        ws.append(["공급업체", self.mat_insp_entries["공급업체"].get(), "", "입고수량(kg)", self.mat_insp_entries["입고수량(kg)"].get()])
        ws.append(["포장상태", self.mat_insp_entries["포장상태"].get(), "", "종합판정", self.mat_insp_entries["종합판정"].get()])
        ws.append([])
        ws.append(["시험 항목", "시험 기준", "시험 결과", "판정", "비고"])
        
        for k, v in self.mat_insp_item_entries.items():
            ws.append([k, v["spec"].get(), v["result"].get(), "적합", ""])

        file_path = fd.asksaveasfilename(defaultextension=".xlsx", filetypes=[("Excel Files", "*.xlsx")], initialfile=f"원료입고검사_{mat_name}.xlsx", title="성적서 엑셀 저장")
        if file_path:
            wb.save(file_path)
            messagebox.showinfo("완료", f"성적서가 저장되었습니다:\n{file_path}", parent=self)
            try: os.startfile(os.path.abspath(file_path))
            except: pass

    # =========================================================================
    # 2. 완제품/반제품 제품표준서 (Product Specification Standard) - CGMP 5대 심층 파트
    # =========================================================================
    def setup_product_standard_tab(self, tab_frame):
        tab_frame.grid_columnconfigure(0, weight=1)
        tab_frame.grid_rowconfigure(0, weight=1)

        scroll = ctk.CTkScrollableFrame(tab_frame, label_text="제품표준서 (Product Specification Standard - CGMP 5대 심층 규격서)")
        scroll.grid(row=0, column=0, sticky="nsew", padx=10, pady=10)
        scroll.grid_columnconfigure(0, weight=1)

        self.prod_std_entries = {}
        self.current_prod_std_id = None

        # 상단 툴바 & 이력/연동
        top_bar = ctk.CTkFrame(scroll, fg_color="transparent")
        top_bar.grid(row=0, column=0, sticky="ew", padx=10, pady=(5, 10))
        top_bar.grid_columnconfigure(1, weight=1)

        ctk.CTkLabel(top_bar, text="표준서 이력:", font=ctk.CTkFont(weight="bold")).grid(row=0, column=0, padx=5, pady=5)
        self.prod_std_picker = ctk.CTkComboBox(top_bar, values=["-- 저장된 제품표준서 선택 --"], width=300)
        self.prod_std_picker.grid(row=0, column=1, padx=5, pady=5, sticky="ew")

        ctk.CTkButton(top_bar, text="불러오기", width=75, command=self.load_selected_prod_std).grid(row=0, column=2, padx=4, pady=5)
        ctk.CTkButton(top_bar, text="처방연동", width=75, fg_color="#6A1B9A", hover_color="#4A148C", command=self.import_from_formulation_to_prod_std).grid(row=0, column=3, padx=4, pady=5)
        ctk.CTkButton(top_bar, text="새로작성", width=75, fg_color="gray50", command=self.clear_prod_std_form).grid(row=0, column=4, padx=4, pady=5)
        ctk.CTkButton(top_bar, text="삭제", width=65, fg_color="#D32F2F", command=self.delete_prod_std).grid(row=0, column=5, padx=4, pady=5)

        # 5대 세부 규격 서브 탭뷰
        self.prod_std_subtabs = ctk.CTkTabview(scroll, height=480)
        self.prod_std_subtabs.grid(row=1, column=0, sticky="nsew", padx=10, pady=5)
        
        tab_p1 = self.prod_std_subtabs.add("1. 제품개요 및 참고사항")
        tab_p2 = self.prod_std_subtabs.add("2. 원료성분 기준 및 함량표")
        tab_p3 = self.prod_std_subtabs.add("3. 공정규격 및 제조공정(SOP)")
        tab_p4 = self.prod_std_subtabs.add("4. 완제품 시험기준 및 규격")
        tab_p5 = self.prod_std_subtabs.add("5. 제품사양 및 포장자재")

        # =====================================================================
        # Part 1: 제품개요 및 참고사항 (하이브리드 ComboBox + Entry)
        # =====================================================================
        tab_p1.grid_columnconfigure((1, 3), weight=1)
        p1_combos = {
            "화장품유형": ["기초화장용 제품류 (로션/크림)", "세정용 제품류 (클렌저/바디워시)", "두발용 제품류 (샴푸/린스)", "면도용 제품류 (쉐이빙 젤/폼)", "직접 입력"],
            "기능성 여부": ["해당사항없음 (일반화장품)", "주름개선 기능성화장품 (보고 완료)", "미백 기능성화장품 (보고 완료)", "미백·주름개선 2중 기능성", "자외선차단 기능성화장품", "직접 입력"],
            "사용기한(개봉전)": ["제조일로부터 36개월", "제조일로부터 24개월", "제조일로부터 12개월", "직접 입력"],
            "개봉후 사용기간": ["개봉 후 12개월", "개봉 후 6개월", "개봉 후 24개월", "직접 입력"],
            "보관조건": ["통풍이 잘되는 차광된 장소에서 상온(1~30℃) 보관", "직사광선을 피하고 서늘한 곳에 밀폐 보관", "직접 입력"],
            "효능/효과": ["피부 보습 및 장벽 강화, 진정", "피부 보습 및 주름개선", "피부 미백 및 톤 케어", "자료없음", "직접 입력"]
        }
        p1_fields = [
            ("제품명(국문)", 0, 0), ("제품명(영문)", 0, 2),
            ("제품코드", 1, 0), ("화장품유형", 1, 2),
            ("의뢰/판매업체", 2, 0), ("포장용량", 2, 2),
            ("효능/효과", 3, 0), ("기능성 여부", 3, 2),
            ("사용기한(개봉전)", 4, 0), ("개봉후 사용기간", 4, 2),
            ("보관조건", 5, 0), ("용법/용량", 5, 2)
        ]
        for lbl, r, c in p1_fields:
            ctk.CTkLabel(tab_p1, text=lbl, font=ctk.CTkFont(weight="bold")).grid(row=r, column=c, padx=10, pady=6, sticky="w")
            if lbl in p1_combos:
                cb = ctk.CTkComboBox(tab_p1, values=p1_combos[lbl])
                cb.set(p1_combos[lbl][0])
                cb.grid(row=r, column=c+1, padx=10, pady=6, sticky="ew")
                self.prod_std_entries[lbl] = cb
            else:
                ent = ctk.CTkEntry(tab_p1, placeholder_text=f"{lbl} 입력")
                ent.grid(row=r, column=c+1, padx=10, pady=6, sticky="ew")
                self.prod_std_entries[lbl] = ent

        # =====================================================================
        # Part 2: 원료 성분 기준 및 함량 (표준 표 Grid + 직접 추가/삭제)
        # =====================================================================
        tab_p2.grid_columnconfigure(0, weight=1)
        p2_header_bar = ctk.CTkFrame(tab_p2, fg_color="transparent")
        p2_header_bar.grid(row=0, column=0, sticky="ew", padx=8, pady=(5, 4))
        p2_header_bar.grid_columnconfigure(0, weight=1)

        ctk.CTkLabel(p2_header_bar, text="📋 [원료 성분 기준 및 함량표 (100g당 / Phase별 표준 표)]", font=ctk.CTkFont(weight="bold", size=13), text_color=("#1F497D", "#38BDF8")).grid(row=0, column=0, sticky="w")
        
        p2_btn_box = ctk.CTkFrame(p2_header_bar, fg_color="transparent")
        p2_btn_box.grid(row=0, column=1, sticky="e")
        ctk.CTkButton(p2_btn_box, text="➕ 원료 행 추가", width=100, height=26, fg_color="#0284C7", hover_color="#0369A1", command=self.add_prod_std_ingredient_row).pack(side="left", padx=3)
        ctk.CTkButton(p2_btn_box, text="➖ 선택 행 삭제", width=100, height=26, fg_color="#EF4444", hover_color="#DC2626", command=self.remove_selected_prod_std_ingredient_row).pack(side="left", padx=3)

        self.prod_std_sec2_table_frame = ctk.CTkFrame(tab_p2)
        self.prod_std_sec2_table_frame.grid(row=1, column=0, padx=8, pady=5, sticky="nsew")
        self.prod_std_sec2_table_frame.grid_columnconfigure(0, weight=0) # 선택
        self.prod_std_sec2_table_frame.grid_columnconfigure(1, weight=1) # Phase
        self.prod_std_sec2_table_frame.grid_columnconfigure(2, weight=2) # 원료코드
        self.prod_std_sec2_table_frame.grid_columnconfigure(3, weight=3) # 원료명
        self.prod_std_sec2_table_frame.grid_columnconfigure(4, weight=3) # INCI명/허가명
        self.prod_std_sec2_table_frame.grid_columnconfigure(5, weight=2) # 시험기준
        self.prod_std_sec2_table_frame.grid_columnconfigure(6, weight=2) # 배합비(%)

        p2_headers = ["선택", "Phase", "원료코드", "원료명", "허가명 (INCI)", "시험기준", "함량 (%)"]
        for idx, h_text in enumerate(p2_headers):
            ctk.CTkLabel(self.prod_std_sec2_table_frame, text=h_text, font=ctk.CTkFont(weight="bold"), fg_color=("gray85", "gray20"), corner_radius=0).grid(row=0, column=idx, sticky="ew", padx=1, pady=1)

        self.prod_std_ingredient_rows = []

        # 레거시 백업 텍스트박스 (숨김/내부용)
        self.prod_std_formula_snap = ctk.CTkTextbox(tab_p2, height=1)

        # =====================================================================
        # Part 3: 공정규격 및 제조공정 관리기준(SOP)
        # =====================================================================
        tab_p3.grid_columnconfigure(0, weight=1)
        tab_p3.grid_rowconfigure(1, weight=1)
        ctk.CTkLabel(tab_p3, text="[단계별 제조공정 지침, 투입온도(℃), RPM 교반조건, 여과 및 공정검사(IPC) 관리기준 (직접 추가/편집 가능)]:", font=ctk.CTkFont(weight="bold")).grid(row=0, column=0, padx=10, pady=5, sticky="w")
        self.prod_std_mfg_summary = ctk.CTkTextbox(tab_p3, height=350)
        self.prod_std_mfg_summary.grid(row=1, column=0, padx=10, pady=5, sticky="nsew")
        self.prod_std_mfg_summary.insert("1.0", "[1. Phase A 수상공정]\n- 정제수 및 보습제 투입 후 75~80℃ 가열, 패들 25~30 RPM 교반 용해\n\n[2. Phase B 유상공정]\n- 유화제 및 왁스/오일류 75~80℃ 가열 완전 용해 확인\n\n[3. 유화 및 균질화 공정]\n- 메인 가마에 Phase B 서서히 투입\n- 호모믹서 3,500~3,800 RPM (5분간 고속 유화) / 아지믹서 25 RPM 병행\n- 진공도 -0.08 MPa 감압 탈포 진행\n\n[4. 냉각 및 후첨가 Phase C]\n- 45℃까지 서서히 감온 (냉각수 순환)\n- Phase C 첨가제 및 향료 투입 후 15분간 균일 분산\n\n[5. 완제품 여과 및 보관]\n- 100 mesh SUS 여과망 통과 후 전용 SUS 드럼에 밀폐 포장 이송")

        # =====================================================================
        # Part 4: 완제품 시험기준 및 규격 (하이브리드 ComboBox + 직접 입력)
        # =====================================================================
        tab_p4.grid_columnconfigure((1, 3), weight=1)
        p4_combos = {
            "성상기준": ["고유의 성상을 가진 유백색의 크림 제형", "무색 투명 겔상", "투명한 액상 제형", "직접 입력"],
            "색상기준": ["유백색 또는 고유의 미황색", "무색 투명", "미백색", "직접 입력"],
            "향취기준": ["고유의 은은한 플로럴 향취", "무취", "특이취", "자사 표준품과 동일", "직접 입력"],
            "pH규격(25℃)": ["5.50 ± 1.00 (pH Meter)", "5.50 ~ 7.00", "6.00 ± 0.50", "직접 입력"],
            "점도규격(cps)": ["12,000 ± 3,000 cps (Helipath, 50rpm, Spindle-E, 1min)", "30,000 ~ 50,000 cps", "19,000 ± 4,000 cps", "직접 입력"],
            "비중규격(25℃)": ["1.010 ± 0.050 (비중병)", "0.980 ~ 1.020", "1.000 ± 0.050", "직접 입력"],
            "중금속(납/비소/수은)": ["납 20ppm 이하, 비소 10ppm 이하, 수은 1ppm 이하", "화장품 안전기준 적합", "직접 입력"],
            "미생물한도규격": ["총호기성생균수 100 CFU/g 이하, 대장균/녹농균/황색포도상구균 불검출", "일반세균 100cfu/ml 이하, 진균 불검출", "직접 입력"]
        }
        p4_fields = [
            ("성상기준", 0, 0), ("색상기준", 0, 2),
            ("향취기준", 1, 0), ("pH규격(25℃)", 1, 2),
            ("점도규격(cps)", 2, 0), ("비중규격(25℃)", 2, 2),
            ("중금속(납/비소/수은)", 3, 0), ("미생물한도규격", 3, 2)
        ]
        for lbl, r, c in p4_fields:
            ctk.CTkLabel(tab_p4, text=lbl, font=ctk.CTkFont(weight="bold")).grid(row=r, column=c, padx=10, pady=8, sticky="w")
            cb = ctk.CTkComboBox(tab_p4, values=p4_combos[lbl])
            cb.set(p4_combos[lbl][0])
            cb.grid(row=r, column=c+1, padx=10, pady=8, sticky="ew")
            self.prod_std_entries[lbl] = cb

        # =====================================================================
        # Part 5: 제품사양 및 포장자재 (하이브리드 ComboBox + 직접 입력)
        # =====================================================================
        tab_p5.grid_columnconfigure((1, 3), weight=1)
        p5_combos = {
            "1차 용기재질/사양": ["튜브 250ml (외관 스크래치/이물 무)", "50ml 헤비블로우 PET 용기", "100ml 유리용기", "직접 입력"],
            "펌프/캡 토출규격": ["원터치 캡 (누액 무)", "PP 에어리스 펌프 (1회 토출량: 0.20 ± 0.03g)", "스프레이 미스트 펌프", "직접 입력"],
            "2차 포장(단상자)": ["FSC 인증 CCP 350g 단상자 (금박 코팅)", "골판지 카톤박스 포장", "해당없음", "직접 입력"],
            "포장 표시사항 기준": ["화장품법 제10조 전성분/바코드/제조번호/사용기한 완전 표시", "법적 규정에 적합", "직접 입력"],
            "운송/취급 주의사항": ["낙하 충격 방지, 고온 다습 환경 노출 금지", "직사광선 차단 및 실온 운송", "직접 입력"]
        }
        p5_fields = [
            ("1차 용기재질/사양", 0, 0), ("펌프/캡 토출규격", 0, 2),
            ("2차 포장(단상자)", 1, 0), ("포장 표시사항 기준", 1, 2),
            ("운송/취급 주의사항", 2, 0), ("수율 기준", 2, 2)
        ]
        for lbl, r, c in p5_fields:
            ctk.CTkLabel(tab_p5, text=lbl, font=ctk.CTkFont(weight="bold")).grid(row=r, column=c, padx=10, pady=8, sticky="w")
            if lbl in p5_combos:
                cb = ctk.CTkComboBox(tab_p5, values=p5_combos[lbl])
                cb.set(p5_combos[lbl][0])
                cb.grid(row=r, column=c+1, padx=10, pady=8, sticky="ew")
                self.prod_std_entries[lbl] = cb
            else:
                ent = ctk.CTkEntry(tab_p5, placeholder_text=f"{lbl} 입력 (예: 충진 포장 수율기준 95% 이상)")
                ent.grid(row=r, column=c+1, padx=10, pady=8, sticky="ew")
                self.prod_std_entries[lbl] = ent

        btn_bar = ctk.CTkFrame(scroll, fg_color="transparent")
        btn_bar.grid(row=2, column=0, sticky="e", padx=10, pady=15)
        ctk.CTkButton(btn_bar, text="💾 표준서 DB 저장", width=120, command=self.save_prod_std_to_db).pack(side="left", padx=5)
        ctk.CTkButton(btn_bar, text="📊 국문 표준서 엑셀 (12대 공식 서식)", width=180, fg_color="#2E7D32", hover_color="#1B5E20", command=lambda: self.export_prod_std_to_excel("ko")).pack(side="left", padx=5)
        ctk.CTkButton(btn_bar, text="🌐 영문 표준서 엑셀 (Product Spec)", width=180, fg_color="#1565C0", hover_color="#0D47A1", command=lambda: self.export_prod_std_to_excel("en")).pack(side="left", padx=5)

        self.refresh_prod_std_list()

    def refresh_prod_std_list(self):
        try:
            session = db_manager.get_session()
            recs = session.query(ProductStandard).order_by(ProductStandard.created_at.desc()).limit(50).all()
            vals = [f"{r.id} | {r.product_name} | {r.cosmetic_type or ''} | {r.created_at.strftime('%Y-%m-%d')}" for r in recs]
            self.prod_std_picker.configure(values=vals if vals else ["-- 저장된 제품표준서 없음 --"])
            if vals: self.prod_std_picker.set(vals[0])
            session.close()
        except Exception as e:
            print(f"[경고] 제품표준서 목록 로드 실패: {e}")

    def add_prod_std_ingredient_row(self, item_data=None):
        """Part 2 원료 성분 표에 새로운 행을 추가합니다."""
        if not hasattr(self, 'prod_std_ingredient_rows'):
            self.prod_std_ingredient_rows = []

        row_idx = len(self.prod_std_ingredient_rows) + 1
        widgets = {'selected': ctk.BooleanVar()}

        chk = ctk.CTkCheckBox(self.prod_std_sec2_table_frame, text="", variable=widgets['selected'], width=24)
        chk.grid(row=row_idx, column=0, padx=2, pady=2)
        widgets['chk'] = chk

        ent_phase = ctk.CTkEntry(self.prod_std_sec2_table_frame, width=50, placeholder_text="A")
        ent_phase.grid(row=row_idx, column=1, padx=1, pady=2, sticky="ew")
        if item_data and 'phase' in item_data: ent_phase.insert(0, item_data['phase'])
        widgets['phase'] = ent_phase

        ent_code = ctk.CTkEntry(self.prod_std_sec2_table_frame, width=90, placeholder_text="RM-001")
        ent_code.grid(row=row_idx, column=2, padx=1, pady=2, sticky="ew")
        if item_data and 'code' in item_data: ent_code.insert(0, item_data['code'])
        widgets['code'] = ent_code

        ent_name = ctk.CTkEntry(self.prod_std_sec2_table_frame, placeholder_text="원료명")
        ent_name.grid(row=row_idx, column=3, padx=1, pady=2, sticky="ew")
        if item_data and 'name' in item_data: ent_name.insert(0, item_data['name'])
        widgets['name'] = ent_name

        ent_inci = ctk.CTkEntry(self.prod_std_sec2_table_frame, placeholder_text="허가명 / INCI")
        ent_inci.grid(row=row_idx, column=4, padx=1, pady=2, sticky="ew")
        if item_data and 'inci' in item_data: ent_inci.insert(0, item_data['inci'])
        widgets['inci'] = ent_inci

        ent_spec = ctk.CTkEntry(self.prod_std_sec2_table_frame, width=90, placeholder_text="자사규격")
        ent_spec.grid(row=row_idx, column=5, padx=1, pady=2, sticky="ew")
        if item_data and 'spec' in item_data: ent_spec.insert(0, item_data['spec'])
        else: ent_spec.insert(0, "자사규격")
        widgets['spec'] = ent_spec

        ent_ratio = ctk.CTkEntry(self.prod_std_sec2_table_frame, width=80, placeholder_text="0.00%")
        ent_ratio.grid(row=row_idx, column=6, padx=1, pady=2, sticky="ew")
        if item_data and 'ratio' in item_data: ent_ratio.insert(0, item_data['ratio'])
        widgets['ratio'] = ent_ratio

        self.prod_std_ingredient_rows.append(widgets)

    def remove_selected_prod_std_ingredient_row(self):
        """Part 2 원료 성분 표에서 선택된 행을 삭제합니다."""
        if not hasattr(self, 'prod_std_ingredient_rows') or not self.prod_std_ingredient_rows:
            return
        remaining = []
        for r in self.prod_std_ingredient_rows:
            if r['selected'].get():
                for w in r.values():
                    if hasattr(w, 'destroy'): w.destroy()
            else:
                remaining.append(r)
        self.prod_std_ingredient_rows = remaining
        for idx, r in enumerate(self.prod_std_ingredient_rows, start=1):
            r['chk'].grid(row=idx, column=0, padx=2, pady=2)
            r['phase'].grid(row=idx, column=1, padx=1, pady=2, sticky="ew")
            r['code'].grid(row=idx, column=2, padx=1, pady=2, sticky="ew")
            r['name'].grid(row=idx, column=3, padx=1, pady=2, sticky="ew")
            r['inci'].grid(row=idx, column=4, padx=1, pady=2, sticky="ew")
            r['spec'].grid(row=idx, column=5, padx=1, pady=2, sticky="ew")
            r['ratio'].grid(row=idx, column=6, padx=1, pady=2, sticky="ew")

    def _clear_prod_std_ingredient_rows(self):
        if hasattr(self, 'prod_std_ingredient_rows'):
            for r in self.prod_std_ingredient_rows:
                for w in r.values():
                    if hasattr(w, 'destroy'): w.destroy()
            self.prod_std_ingredient_rows.clear()

    def import_from_formulation_to_prod_std(self):
        session = db_manager.get_session()
        try:
            forms = session.query(Formulation).order_by(Formulation.created_at.desc()).limit(30).all()
            if not forms:
                messagebox.showinfo("알림", "등록된 연구 처방이 없습니다.", parent=self); return
            
            pop = ctk.CTkToplevel(self)
            pop.title("처방 선택")
            pop.geometry("450x200")
            pop.transient(self)
            
            ctk.CTkLabel(pop, text="표준서로 연동할 처방을 선택하세요:", font=ctk.CTkFont(weight="bold")).pack(pady=(15, 5))
            f_vals = [f"{f.id} | {f.experiment_name} | LAB:{f.lab_no or ''}" for f in forms]
            cb = ctk.CTkComboBox(pop, values=f_vals, width=380)
            cb.pack(pady=10)

            def apply_f():
                sel = cb.get()
                if not sel: return
                fid = int(sel.split('|')[0].strip())
                target_f = session.query(Formulation).options(joinedload(Formulation.items)).filter_by(id=fid).first()
                if target_f:
                    if "제품명(국문)" in self.prod_std_entries:
                        self.prod_std_entries["제품명(국문)"].delete(0, "end"); self.prod_std_entries["제품명(국문)"].insert(0, target_f.experiment_name or "")
                    if "pH규격(25℃)" in self.prod_std_entries:
                        self.prod_std_entries["pH규격(25℃)"].set(target_f.experiment_ph_initial or target_f.target_ph_initial or "5.50 ± 1.00 (pH Meter)")
                    if "점도규격(cps)" in self.prod_std_entries:
                        self.prod_std_entries["점도규격(cps)"].set(target_f.experiment_viscosity_initial or target_f.target_viscosity_initial or "12,000 ± 3,000 cps (Helipath, 50rpm, Spindle-E, 1min)")
                    
                    mat_ids = [it.material_id for it in (target_f.items or []) if it.material_id]
                    mats_map = {}
                    if mat_ids:
                        mats = session.query(Material).options(joinedload(Material.ingredients)).filter(Material.id.in_(mat_ids)).all()
                        mats_map = {m.id: m for m in mats}

                    # Part 2 테이블 행 자동 구성
                    self._clear_prod_std_ingredient_rows()
                    for it in (target_f.items or []):
                        m_obj = mats_map.get(it.material_id)
                        inci_name = ""
                        if m_obj and m_obj.ingredients:
                            inci_name = ", ".join([ing.name_ko or ing.name_en or '' for ing in m_obj.ingredients if (ing.name_ko or ing.name_en)])
                        elif m_obj and m_obj.name_en:
                            inci_name = m_obj.name_en

                        ratio_val = f"{it.ratio:.3f}%" if it.ratio is not None else ""
                        self.add_prod_std_ingredient_row({
                            'phase': it.phase or 'A',
                            'code': it.material_code or 'RAW',
                            'name': it.material_name or '',
                            'inci': inci_name,
                            'spec': '자사규격',
                            'ratio': ratio_val
                        })

                pop.destroy()
                messagebox.showinfo("연동 완료", "처방 원료 및 성분이 제품표준서 표준 표에 반영되었습니다.", parent=self)

            ctk.CTkButton(pop, text="확인 및 반영", command=apply_f).pack(pady=10)
        finally:
            session.close()

    def clear_prod_std_form(self):
        self.current_prod_std_id = None
        for k, e in self.prod_std_entries.items():
            if isinstance(e, ctk.CTkComboBox):
                vals = e.cget("values")
                if vals: e.set(vals[0])
            else:
                e.delete(0, "end")
        self._clear_prod_std_ingredient_rows()
        self.prod_std_mfg_summary.delete("1.0", "end")

    def load_selected_prod_std(self):
        sel = self.prod_std_picker.get()
        if not sel or '|' not in sel: return
        rec_id = int(sel.split('|')[0].strip())
        session = db_manager.get_session()
        try:
            r = session.query(ProductStandard).get(rec_id)
            if not r: return
            self.current_prod_std_id = r.id
            if "제품명(국문)" in self.prod_std_entries:
                self.prod_std_entries["제품명(국문)"].delete(0, "end"); self.prod_std_entries["제품명(국문)"].insert(0, r.product_name or "")
            if "제품명(영문)" in self.prod_std_entries:
                self.prod_std_entries["제품명(영문)"].delete(0, "end"); self.prod_std_entries["제품명(영문)"].insert(0, r.product_name_en or "")
            if "제품코드" in self.prod_std_entries:
                self.prod_std_entries["제품코드"].delete(0, "end"); self.prod_std_entries["제품코드"].insert(0, r.product_code or "")
            if "화장품유형" in self.prod_std_entries:
                self.prod_std_entries["화장품유형"].set(r.cosmetic_type or "")
            if "의뢰/판매업체" in self.prod_std_entries:
                self.prod_std_entries["의뢰/판매업체"].delete(0, "end"); self.prod_std_entries["의뢰/판매업체"].insert(0, r.target_client or "")
            if "포장용량" in self.prod_std_entries:
                self.prod_std_entries["포장용량"].delete(0, "end"); self.prod_std_entries["포장용량"].insert(0, r.package_volume or "")
            if "성상기준" in self.prod_std_entries:
                self.prod_std_entries["성상기준"].set(r.appearance_criteria or "")
            if "색상기준" in self.prod_std_entries:
                self.prod_std_entries["색상기준"].set(r.color_criteria or "")
            if "향취기준" in self.prod_std_entries:
                self.prod_std_entries["향취기준"].set(r.odor_criteria or "")
            if "pH규격(25℃)" in self.prod_std_entries:
                self.prod_std_entries["pH규격(25℃)"].set(r.ph_spec or "")
            if "점도규격(cps)" in self.prod_std_entries:
                self.prod_std_entries["점도규격(cps)"].set(r.viscosity_spec or "")
            if "비중규격(25℃)" in self.prod_std_entries:
                self.prod_std_entries["비중규격(25℃)"].set(r.specific_gravity_spec or "")
            if "미생물한도규격" in self.prod_std_entries:
                self.prod_std_entries["미생물한도규격"].set(r.microbial_spec or "")
            if "보관조건" in self.prod_std_entries:
                self.prod_std_entries["보관조건"].set(r.storage_condition or "")
            if "1차 용기재질/사양" in self.prod_std_entries:
                self.prod_std_entries["1차 용기재질/사양"].set(r.packaging_specs_json or "")
            
            # Part 2 복구
            self._clear_prod_std_ingredient_rows()
            if r.formulation_snapshot:
                try:
                    import json
                    p2_data = json.loads(r.formulation_snapshot)
                    if isinstance(p2_data, list):
                        for row_d in p2_data:
                            self.add_prod_std_ingredient_row(row_d)
                except Exception:
                    pass

            self.prod_std_mfg_summary.delete("1.0", "end"); self.prod_std_mfg_summary.insert("1.0", r.mfg_process_summary or "")
            messagebox.showinfo("불러오기 완료", f"제품표준서 '{r.product_name}' 데이터를 불러왔습니다.", parent=self)
        finally:
            session.close()

    def save_prod_std_to_db(self):
        p_name = self.prod_std_entries["제품명(국문)"].get().strip() if "제품명(국문)" in self.prod_std_entries else ""
        if not p_name:
            messagebox.showwarning("입력 필요", "제품명은 필수 항목입니다.", parent=self); return
        session = db_manager.get_session()
        try:
            import json
            r = session.query(ProductStandard).get(self.current_prod_std_id) if self.current_prod_std_id else ProductStandard()
            r.product_name = p_name
            r.product_name_en = self.prod_std_entries.get("제품명(영문)", ctk.CTkEntry(self)).get().strip()
            r.product_code = self.prod_std_entries.get("제품코드", ctk.CTkEntry(self)).get().strip()
            r.cosmetic_type = self.prod_std_entries.get("화장품유형", ctk.CTkEntry(self)).get().strip()
            r.target_client = self.prod_std_entries.get("의뢰/판매업체", ctk.CTkEntry(self)).get().strip()
            r.package_volume = self.prod_std_entries.get("포장용량", ctk.CTkEntry(self)).get().strip()
            r.expiry_period = self.prod_std_entries.get("사용기한(개봉전)", ctk.CTkEntry(self)).get().strip()
            r.storage_condition = self.prod_std_entries.get("보관조건", ctk.CTkEntry(self)).get().strip()
            r.appearance_criteria = self.prod_std_entries.get("성상기준", ctk.CTkEntry(self)).get().strip()
            r.color_criteria = self.prod_std_entries.get("색상기준", ctk.CTkEntry(self)).get().strip()
            r.odor_criteria = self.prod_std_entries.get("향취기준", ctk.CTkEntry(self)).get().strip()
            r.ph_spec = self.prod_std_entries.get("pH규격(25℃)", ctk.CTkEntry(self)).get().strip()
            r.viscosity_spec = self.prod_std_entries.get("점도규격(cps)", ctk.CTkEntry(self)).get().strip()
            r.specific_gravity_spec = self.prod_std_entries.get("비중규격(25℃)", ctk.CTkEntry(self)).get().strip()
            r.microbial_spec = self.prod_std_entries.get("미생물한도규격", ctk.CTkEntry(self)).get().strip()
            r.packaging_specs_json = self.prod_std_entries.get("1차 용기재질/사양", ctk.CTkEntry(self)).get().strip()
            
            # Part 2 표 JSON 직렬화
            p2_list = []
            for row in self.prod_std_ingredient_rows:
                p2_list.append({
                    'phase': row['phase'].get().strip(),
                    'code': row['code'].get().strip(),
                    'name': row['name'].get().strip(),
                    'inci': row['inci'].get().strip(),
                    'spec': row['spec'].get().strip(),
                    'ratio': row['ratio'].get().strip()
                })
            r.formulation_snapshot = json.dumps(p2_list, ensure_ascii=False)
            r.mfg_process_summary = self.prod_std_mfg_summary.get("1.0", "end-1c").strip()
            
            if not self.current_prod_std_id: session.add(r)
            session.commit()
            self.current_prod_std_id = r.id
            self.refresh_prod_std_list()
            messagebox.showinfo("저장 완료", "제품표준서가 DB에 성공적으로 저장되었습니다.", parent=self)
        except Exception as e:
            session.rollback()
            messagebox.showerror("오류", f"저장 실패: {e}", parent=self)
        finally:
            session.close()

    def delete_prod_std(self):
        if not self.current_prod_std_id: return
        if not messagebox.askyesno("삭제 확인", "선택한 제품표준서를 삭제하시겠습니까?", parent=self): return
        session = db_manager.get_session()
        try:
            r = session.query(ProductStandard).get(self.current_prod_std_id)
            if r:
                session.delete(r); session.commit()
                self.clear_prod_std_form()
                self.refresh_prod_std_list()
                messagebox.showinfo("완료", "삭제되었습니다.", parent=self)
        finally:
            session.close()

    def export_prod_std_to_excel(self, lang="ko"):
        is_en = (lang == "en")
        p_name = self.prod_std_entries.get("제품명(영문)" if is_en else "제품명(국문)", ctk.CTkEntry(self)).get().strip() or self.prod_std_entries.get("제품명(국문)", ctk.CTkEntry(self)).get().strip() or ("Product_Standard" if is_en else "제품표준서")
        wb = Workbook()

        # 공통 스타일 정의
        thin_side = Side(style="thin", color="D0D7DE")
        border_all = Border(left=thin_side, right=thin_side, top=thin_side, bottom=thin_side)
        fill_header = PatternFill(start_color="F1F5F9", end_color="F1F5F9", fill_type="solid")
        fill_sub_hdr = PatternFill(start_color="F8FAFC", end_color="F8FAFC", fill_type="solid")
        font_title = Font(name="맑은 고딕", size=15, bold=True, color="0F172A")
        font_hdr = Font(name="맑은 고딕", size=10, bold=True, color="1E293B")
        font_cell = Font(name="맑은 고딕", size=9.5, color="334155")
        align_c = Alignment(horizontal="center", vertical="center", wrap_text=True)
        align_l = Alignment(horizontal="left", vertical="center", wrap_text=True)

        def style_cells(ws_obj, min_r, max_r, min_c, max_c, font=font_cell, fill=None, align=align_c, border=border_all):
            for r in range(min_r, max_r + 1):
                for c in range(min_c, max_c + 1):
                    cell = ws_obj.cell(row=r, column=c)
                    if font: cell.font = font
                    if fill: cell.fill = fill
                    if align: cell.alignment = align
                    if border: cell.border = border

        p_code = self.prod_std_entries.get("제품코드", ctk.CTkEntry(self)).get() or "HG117142"
        p_type = self.prod_std_entries.get("화장품유형", ctk.CTkEntry(self)).get() or "기초화장용 제품류"
        p_vol = self.prod_std_entries.get("포장용량", ctk.CTkEntry(self)).get() or "250ml"
        p_exp = self.prod_std_entries.get("사용기한(개봉전)", ctk.CTkEntry(self)).get() or "제조일로부터 36개월"
        p_pao = self.prod_std_entries.get("개봉후 사용기간", ctk.CTkEntry(self)).get() or "개봉 후 12개월"
        p_storage = self.prod_std_entries.get("보관조건", ctk.CTkEntry(self)).get() or "통풍이 잘되는 차광된 장소에서 상온 보관"

        std_trans = {
            "제품명": "Product Name",
            "제품명(국문)": "Product Name (Korean)",
            "제품명(영문)": "Product Name (English)",
            "제품코드": "Product Code",
            "화장품유형": "Cosmetic Product Category",
            "의뢰/판매업체": "Client / Distributor",
            "의뢰업체": "Client / Distributor",
            "포장용량": "Net Volume / Weight",
            "제품용량": "Net Volume / Weight",
            "효능/효과": "Efficacy & Claims",
            "효능효과": "Efficacy & Claims",
            "기능성 여부": "Functional Cosmetic Status",
            "허가(보고)여부": "Regulatory Status",
            "작성일자": "Issue Date",
            "사용기한": "Shelf Life",
            "사용기한(개봉전)": "Shelf Life (Unopened)",
            "개봉후 사용기간": "Period After Opening (PAO)",
            "성상": "Appearance",
            "성상기준": "Appearance Specification",
            "색상기준": "Color Specification",
            "향취기준": "Odor Specification",
            "용법용량": "Directions for Use",
            "용법/용량": "Directions for Use",
            "pH규격(25℃)": "pH (at 25°C)",
            "점도규격(cps)": "Viscosity (at 25°C, cps)",
            "비중규격(25℃)": "Specific Gravity (at 25°C)",
            "중금속(납/비소/수은)": "Heavy Metals (Pb, As, Hg, Sb, Cd)",
            "미생물한도규격": "Microbial Limits",
            "1차 용기재질/사양": "Primary Container Specs",
            "펌프/캡 토출규격": "Pump/Cap Dispensing Specs",
            "2차 포장(단상자)": "Secondary Packaging (Box)",
            "포장 표시사항 기준": "Labeling Requirements",
            "보관조건": "Storage Conditions",
            "보관방법": "Storage Conditions",
            "운송/취급 주의사항": "Handling & Transport Precautions",
            "기초화장용 제품류 (로션/크림)": "Skin Care Products (Lotion / Cream)",
            "세정용 제품류 (클렌저/바디워시)": "Cleansing Products (Cleanser / Body Wash)",
            "두발용 제품류 (샴푸/린스)": "Hair Care Products (Shampoo / Conditioner)",
            "면도용 제품류 (쉐이빙 젤/폼)": "Shaving Products (Shaving Gel / Foam)",
            "피부 보습 및 장벽 강화, 진정": "Skin moisturizing, barrier strengthening & soothing",
            "피부 보습 및 장벽 강화, 주름개선": "Skin moisturizing, barrier care & anti-wrinkle",
            "피부 보습 및 주름개선": "Skin moisturizing & anti-wrinkle care",
            "피부 미백 및 톤 케어": "Skin whitening & tone brightening care",
            "해당사항없음 (일반화장품)": "Not Applicable (General Cosmetic)",
            "주름개선 기능성화장품 (보고 완료)": "Anti-wrinkle functional cosmetic (Reported)",
            "미백 기능성화장품 (보고 완료)": "Whitening functional cosmetic (Reported)",
            "미백·주름개선 2중 기능성": "Dual functional cosmetic (Whitening & Anti-wrinkle)",
            "자외선차단 기능성화장품": "UV Protection functional cosmetic",
            "제조일로부터 36개월": "36 months from manufacturing date",
            "제조일로부터 24개월": "24 months from manufacturing date",
            "제조일로부터 12개월": "12 months from manufacturing date",
            "개봉 후 12개월": "12 months after opening",
            "개봉 후 6개월": "6 months after opening",
            "개봉 후 24개월": "24 months after opening",
            "통풍이 잘되는 차광된 장소에서 상온(1~30℃) 보관": "Store at room temperature (1~30°C) in a well-ventilated, shaded place",
            "통풍이 잘되는 차광된 장소에서 상온 보관": "Store at room temperature in a well-ventilated shaded place",
            "직사광선을 피하고 서늘한 곳에 밀폐 보관": "Keep tightly closed in a cool place away from direct sunlight",
            "자사": "In-house",
            "적합": "Pass (Complies)",
            "자사규격": "In-house Spec",
            "공정서 시험법": "Compendial Test Method",
            "상온 보관 (1~30℃)": "Store at room temperature (1~30°C)",
            "본 품 적당량을 취해 피부에 골고루 펴 바릅니다.": "Take an appropriate amount and spread evenly over the skin.",
            "고유의 성상을 가진 유백색의 크림 제형": "Milky white cream formulation with characteristic appearance",
            "무색 투명 겔상": "Colorless transparent gel",
            "투명한 액상 제형": "Transparent liquid formulation",
            "유백색 또는 고유의 미황색": "Milky white or characteristic pale yellow",
            "고유의 은은한 플로럴 향취": "Characteristic subtle floral fragrance",
            "무취": "Odorless",
            "특이취": "Characteristic odor",
            "자사 표준품과 동일": "Same as in-house standard",
            "화장품법 제10조 전성분/바코드/제조번호/사용기한 완전 표시": "Fully labeled under Article 10 of Cosmetic Act (Ingredients/Batch/Expiry)",
            "낙하 충격 방지, 고온 다습 환경 노출 금지": "Prevent drop impact, avoid high temperature/humidity",
            "직사광선 차단 및 실온 운송": "Block direct sunlight and transport at room temperature",
            "튜브 250ml (외관 스크래치/이물 무)": "Tube 250ml (Free of exterior scratches/foreign matter)",
            "50ml 헤비블로우 PET 용기": "50ml Heavy Blow PET Bottle",
            "100ml 유리용기": "100ml Glass Bottle",
            "원터치 캡 (누액 무)": "One-touch Cap (Leak-free)",
            "PP 에어리스 펌프 (1회 토출량: 0.20 ± 0.03g)": "PP Airless Pump (Discharge volume: 0.20 ± 0.03g)",
            "스프레이 미스트 펌프": "Spray Mist Pump",
            "FSC 인증 CCP 350g 단상자 (금박 코팅)": "FSC Certified CCP 350g Unit Box (Gold Foil Coated)",
            "골판지 카톤박스 포장": "Corrugated cardboard carton packaging",
            "해당없음": "Not Applicable",
            "법적 규정에 적합": "Complies with statutory regulations",
            # 시험규격 관련 어휘 및 문장
            "납 20ppm 이하, 비소 10ppm 이하, 수은 1ppm 이하": "Pb <= 20ppm, As <= 10ppm, Hg <= 1ppm",
            "화장품 안전기준 적합": "Complies with Cosmetic Safety Standards",
            "총호기성생균수 100 CFU/g 이하, 대장균/녹농균/황색포도상구균 불검출": "Total Aerobic Count <= 100 CFU/g, E. coli/P. aeruginosa/S. aureus: Not Detected",
            "일반세균 100cfu/ml 이하, 진균 불검출": "Aerobic Bacteria <= 100 CFU/ml, Fungi: Not Detected",
            "관능검사 / 표준품 비교": "Organoleptic test / Comparison with standard",
            "육안 검사": "Visual inspection",
            "관능 후각 시험": "Olfactory sensory test",
            "pH 측정기 (25℃)": "pH Meter (25°C)",
            "회전점도계 측정": "Rotational Viscometer (25°C)",
            "비중병 시험": "Pycnometer (25°C)",
            "기기분석법": "Instrumental analysis (ICP-MS)",
            "3M Petrifilm 배양법": "3M Petrifilm Culture Method",
            "비중병": "Pycnometer",
            "회전점도계": "Rotational Viscometer",
            "이하": "or less",
            "이상": "or more",
            "불검출": "Not Detected",
            "자료없음": "No Data",
            # 제조공정 SOP 세부 문장 및 헤더 자동 번역
            "[1. Phase A 수상공정]": "[1. Phase A Aqueous Phase Process]",
            "[2. Phase B 유상공정]": "[2. Phase B Oil Phase Process]",
            "[3. 유화 및 균질화 공정]": "[3. Emulsification & Homogenization Process]",
            "[4. 냉각 및 후첨가 Phase C]": "[4. Cooling & Phase C Post-Addition]",
            "[5. 완제품 여과 및 보관]": "[5. Finished Bulk Filtration & Storage]",
            "정제수 및 보습제 투입 후 75~80℃ 가열, 패들 25~30 RPM 교반 용해": "Charge purified water and humectants, heat to 75~80°C, and dissolve with paddle mixer at 25~30 RPM.",
            "유화제 및 왁스/오일류 75~80℃ 가열 완전 용해 확인": "Heat emulsifiers, waxes, and oils to 75~80°C and verify complete dissolution.",
            "메인 가마에 Phase B 서서히 투입": "Slowly introduce Phase B into the main manufacturing tank.",
            "호모믹서 3,500~3,800 RPM (5분간 고속 유화) / 아지믹서 25 RPM 병행": "Operate homomixer at 3,500~3,800 RPM (high-speed emulsification for 5 min) concurrently with agimixer at 25 RPM.",
            "진공도 -0.08 MPa 감압 탈포 진행": "Perform vacuum deaeration under reduced pressure of -0.08 MPa.",
            "45℃까지 서서히 감온 (냉각수 순환)": "Cool down gradually to 45°C (circulating chilled water).",
            "Phase C 첨가제 및 향료 투입 후 15분간 균일 분산": "Add Phase C additives and fragrance, then disperse uniformly for 15 minutes.",
            "100 mesh SUS 여과망 통과 후 전용 SUS 드럼에 밀폐 포장 이송": "Filter through a 100-mesh SUS strainer and transfer sealed into dedicated SUS drums.",
            "정제수": "Purified Water",
            "글리세린": "Glycerin",
            "부틸렌글라이콜": "Butylene Glycol",
            "나이아신아마이드": "Niacinamide",
            "아데노신": "Adenosine",
            "향료": "Fragrance",
            "디소듐이디티에이": "Disodium EDTA",
            "수상공정": "Aqueous Phase",
            "유상공정": "Oil Phase",
            "유화공정": "Emulsification",
            "냉각공정": "Cooling",
            "여과": "Filtration",
            "보관": "Storage"
        }
        def tr_std(t):
            if not is_en or not t: return t
            s = str(t).strip()
            if s in std_trans: return std_trans[s]
            for k, v in std_trans.items():
                if k in s: s = s.replace(k, v)
            return s

        # -------------------------------------------------------------
        # 시트 1: 1.표지 및 목차 (Cover & Index)
        # -------------------------------------------------------------
        ws1 = wb.active
        ws1.title = "1.Cover_Index" if is_en else "1.표지_목차"
        ws1.merge_cells("A2:F3")
        ws1["A2"] = f"PRODUCT SPECIFICATION STANDARD" if is_en else "제  품  표  준  서"
        ws1["A2"].font = font_title
        ws1["A2"].alignment = align_c

        ws1["A5"] = "Product Name" if is_en else "제 품 명"
        ws1.merge_cells("B5:F5")
        ws1["B5"] = f"{p_name} ({p_code})"
        style_cells(ws1, 5, 5, 1, 6, font=font_hdr, fill=fill_header, align=align_l)
        ws1["A5"].alignment = align_c

        ws1["A7"] = "NO."
        ws1.merge_cells("B7:F7")
        ws1["B7"] = "Table of Contents" if is_en else "목          차"
        style_cells(ws1, 7, 7, 1, 6, font=font_hdr, fill=fill_sub_hdr, align=align_c)

        toc_items = [
            ("1", "변경이력", "Revision History"),
            ("2", "제품참고사항", "General Product Information"),
            ("3", "공정규격", "Process Specifications & Flow"),
            ("4", "원료성분 기준 및 시험방법 (배합비)", "Raw Material Specs & Formulation"),
            ("5", "계량 지시 및 기록서", "Weighing Instruction & Record"),
            ("6", "제조 지시 및 기록서", "Batch Manufacturing Record (BMR)"),
            ("7", "제품사양 (포장재규격포함)", "Packaging & Component Specifications"),
            ("8", "충진·포장 지시 및 기록서", "Filling & Packaging Record"),
            ("9", "제품 규격서", "Finished Product Specification"),
            ("10", "반제품 시험성적서 (COA)", "Semi-Finished Product COA"),
            ("11", "완제품 시험성적서 (COA)", "Finished Product COA"),
            ("12", "제조 및 품질관리에 필요한 시설 및 기구", "Facility & Equipment List")
        ]
        for idx, (num, ko_t, en_t) in enumerate(toc_items, start=8):
            ws1[f"A{idx}"] = num
            ws1.merge_cells(f"B{idx}:F{idx}")
            ws1[f"B{idx}"] = en_t if is_en else ko_t
            style_cells(ws1, idx, idx, 1, 6, font=font_cell, align=align_l)
            ws1[f"A{idx}"].alignment = align_c

        # -------------------------------------------------------------
        # 시트 2: 2.제품참고사항 (Product Overview & Details)
        # -------------------------------------------------------------
        ws2 = wb.create_sheet(title="2.Product_Info" if is_en else "2.제품참고사항")
        ws2.merge_cells("A1:D1")
        ws2["A1"] = "PRODUCT REFERENCE INFORMATION" if is_en else "제 품 참 고 사 항"
        ws2["A1"].font = font_title
        ws2["A1"].alignment = align_c

        p_info_rows = [
            ("제품명", "Product Name", p_name, "제품코드", "Product Code", p_code),
            ("허가(보고)여부", "Regulatory Status", self.prod_std_entries.get("기능성 여부", ctk.CTkEntry(self)).get(), "작성일자", "Issue Date", datetime.now().strftime("%Y-%m-%d")),
            ("제품용량", "Net Volume", p_vol, "화장품유형", "Cosmetic Type", p_type),
            ("사용기한", "Shelf Life", f"{p_exp} / {p_pao}", "성상", "Appearance", self.prod_std_entries.get("성상기준", ctk.CTkEntry(self)).get()),
            ("보관방법", "Storage", p_storage, "효능효과", "Efficacy", self.prod_std_entries.get("효능/효과", ctk.CTkEntry(self)).get()),
            ("용법용량", "Directions", self.prod_std_entries.get("용법/용량", ctk.CTkEntry(self)).get() or "본 품 적당량을 취해 피부에 골고루 펴 바릅니다.", "의뢰업체", "Client", self.prod_std_entries.get("의뢰/판매업체", ctk.CTkEntry(self)).get() or "자사")
        ]
        r_curr = 3
        for k1_ko, k1_en, v1, k2_ko, k2_en, v2 in p_info_rows:
            ws2[f"A{r_curr}"] = k1_en if is_en else k1_ko
            ws2[f"B{r_curr}"] = tr_std(v1)
            ws2[f"C{r_curr}"] = k2_en if is_en else k2_ko
            ws2[f"D{r_curr}"] = tr_std(v2)
            style_cells(ws2, r_curr, r_curr, 1, 1, font=font_hdr, fill=fill_sub_hdr, align=align_c)
            style_cells(ws2, r_curr, r_curr, 2, 2, font=font_cell, align=align_l)
            style_cells(ws2, r_curr, r_curr, 3, 3, font=font_hdr, fill=fill_sub_hdr, align=align_c)
            style_cells(ws2, r_curr, r_curr, 4, 4, font=font_cell, align=align_l)
            r_curr += 1

        # -------------------------------------------------------------
        # 시트 3: 3.원료성분기준및함량 (Raw Material & Formulation 100g)
        # -------------------------------------------------------------
        ws3 = wb.create_sheet(title="3.Master_Formula" if is_en else "3.원료성분기준및함량")
        ws3.merge_cells("A1:G1")
        ws3["A1"] = f"RAW MATERIAL SPECIFICATIONS & FORMULATION (per 100g) - {p_name}" if is_en else f"원료 성분 기준 및 함량 (100g당) - {p_name}"
        ws3["A1"].font = font_title
        ws3["A1"].alignment = align_c

        headers_f = ["No.", "Phase", "Raw Material Code" if is_en else "원료코드", "Raw Material Name" if is_en else "원료명", "INCI / Common Name" if is_en else "허가명 (INCI)", "Test Spec" if is_en else "시험기준", "Ratio (%)" if is_en else "배합비(%)"]
        ws3.append([])
        ws3.append(headers_f)
        style_cells(ws3, 3, 3, 1, 7, font=font_hdr, fill=fill_header, align=align_c)

        r_f = 4
        if hasattr(self, 'prod_std_ingredient_rows') and self.prod_std_ingredient_rows:
            for idx, row in enumerate(self.prod_std_ingredient_rows, start=1):
                ph = row['phase'].get().strip() or "A"
                cd = row['code'].get().strip() or f"RM-{idx:03d}"
                nm = tr_std(row['name'].get().strip())
                inci = row['inci'].get().strip() or nm
                sp = tr_std(row['spec'].get().strip()) or ("In-house Spec" if is_en else "자사규격")
                rt = row['ratio'].get().strip() or "0.00%"
                ws3.append([idx, ph, cd, nm, inci, sp, rt])
                style_cells(ws3, r_f, r_f, 1, 7, font=font_cell, align=align_c)
                ws3[f"D{r_f}"].alignment = align_l
                ws3[f"E{r_f}"].alignment = align_l
                r_f += 1
        else:
            ws3.append([1, "A", "RM-001", "Water" if is_en else "정제수", "Water", "In-house Spec" if is_en else "자사규격", "100.00%"])
            style_cells(ws3, 4, 4, 1, 7, font=font_cell, align=align_c)

        # -------------------------------------------------------------
        # 시트 4: 4.공정규격및제조SOP (Process SOP)
        # -------------------------------------------------------------
        ws4 = wb.create_sheet(title="4.Mfg_Process_SOP" if is_en else "4.제조공정지침및SOP")
        ws4.merge_cells("A1:E1")
        ws4["A1"] = "MANUFACTURING PROCESS & SOP" if is_en else "공 정 규 격 및 제 조 지 침 (SOP)"
        ws4["A1"].font = font_title
        ws4["A1"].alignment = align_c

        ws4.append([])
        for line in self.prod_std_mfg_summary.get("1.0", "end-1c").split('\n'):
            ws4.append([tr_std(line), "", "", "", ""])

        # -------------------------------------------------------------
        # 시트 5: 5.제품규격서 (Finished Product Specifications)
        # -------------------------------------------------------------
        ws5 = wb.create_sheet(title="5.Product_Criteria" if is_en else "5.제품규격서")
        ws5.merge_cells("A1:E1")
        ws5["A1"] = f"FINISHED PRODUCT SPECIFICATION - {p_name}" if is_en else f"제 품 규 격 서 - {p_name}"
        ws5["A1"].font = font_title
        ws5["A1"].alignment = align_c

        headers_q = ["No.", "Test Parameter" if is_en else "시험 항목", "Specifications" if is_en else "기준 및 규격", "Test Method" if is_en else "시험 방법", "Judgment" if is_en else "판정"]
        ws5.append([])
        ws5.append(headers_q)
        style_cells(ws5, 3, 3, 1, 5, font=font_hdr, fill=fill_header, align=align_c)

        test_keys_full = [
            ("성상", "Appearance", self.prod_std_entries.get("성상기준", ctk.CTkEntry(self)).get(), "Organoleptic / Visual" if is_en else "관능검사 / 표준품 비교"),
            ("색상", "Color", self.prod_std_entries.get("색상기준", ctk.CTkEntry(self)).get(), "Visual inspection" if is_en else "육안 검사"),
            ("향취", "Odor", self.prod_std_entries.get("향취기준", ctk.CTkEntry(self)).get(), "Olfactory test" if is_en else "관능 후각 시험"),
            ("pH (25℃)", "pH (at 25°C)", self.prod_std_entries.get("pH규격(25℃)", ctk.CTkEntry(self)).get(), "pH Meter (25°C)" if is_en else "pH 측정기 (25℃)"),
            ("점도 (25℃)", "Viscosity (at 25°C)", self.prod_std_entries.get("점도규격(cps)", ctk.CTkEntry(self)).get(), "Helipath / Brookfield" if is_en else "회전점도계 측정"),
            ("비중 (25℃)", "Specific Gravity", self.prod_std_entries.get("비중규격(25℃)", ctk.CTkEntry(self)).get(), "Pycnometer (25°C)" if is_en else "비중병 시험"),
            ("중금속", "Heavy Metals", self.prod_std_entries.get("중금속(납/비소/수은)", ctk.CTkEntry(self)).get() or "Lead <= 20ppm, Arsenic <= 10ppm", "ICP-MS / AAS" if is_en else "기기분석법"),
            ("미생물 한도", "Microbial Limits", self.prod_std_entries.get("미생물한도규격", ctk.CTkEntry(self)).get() or "Total Aerobic Count <= 100 CFU/g", "Petrifilm Plate Method" if is_en else "3M Petrifilm 배양법")
        ]
        r_q = 4
        for idx, (t_ko, t_en, spec_val, method_val) in enumerate(test_keys_full, start=1):
            ws5.append([idx, t_en if is_en else t_ko, tr_std(spec_val), method_val, "Pass" if is_en else "적합"])
            style_cells(ws5, r_q, r_q, 1, 5, font=font_cell, align=align_c)
            ws5[f"C{r_q}"].alignment = align_l
            r_q += 1

        # 컬럼 너비 자동 조정
        for sheet_item in [ws1, ws2, ws3, ws4, ws5]:
            for col in sheet_item.columns:
                max_len = 0
                safe_cell = next((c for c in col if not isinstance(c, openpyxl.cell.cell.MergedCell)), None)
                if not safe_cell: continue
                for cell in col:
                    if cell.value:
                        l = _get_display_length(cell.value)
                        if l > max_len: max_len = l
                sheet_item.column_dimensions[safe_cell.column_letter].width = max(max_len + 3, 12)

        f_prefix = f"ProductStandard_EN_{p_name}" if is_en else f"제품표준서_공식12대규격_{p_name}"
        file_path = fd.asksaveasfilename(
            defaultextension=".xlsx",
            filetypes=[("Excel Files", "*.xlsx")],
            initialfile=f"{f_prefix}.xlsx",
            title="Save Product Standard (English)" if is_en else "제품표준서 공식 규격 엑셀 저장"
        )
        if file_path:
            wb.save(file_path)
            messagebox.showinfo("완료" if not is_en else "Export Complete", 
                                f"제품표준서가 저장되었습니다:\n{file_path}" if not is_en else f"Product Standard exported successfully:\n{file_path}", 
                                parent=self)
            try:
                os.startfile(os.path.abspath(file_path))
            except Exception:
                pass

    # =========================================================================
    # 3. 제조지시 및 기록서 (Batch Manufacturing Record - BMR) - CGMP 배치 심층 구조
    # =========================================================================
    def setup_batch_manufacturing_tab(self, tab_frame):
        tab_frame.grid_columnconfigure(0, weight=1)
        tab_frame.grid_rowconfigure(0, weight=1)

        scroll = ctk.CTkScrollableFrame(tab_frame, label_text="제조지시 및 기록서 (Batch Manufacturing Record - CGMP BMR 심층 기록)")
        scroll.grid(row=0, column=0, sticky="nsew", padx=10, pady=10)
        scroll.grid_columnconfigure(0, weight=1)

        self.bmr_entries = {}
        self.current_bmr_id = None

        top_bar = ctk.CTkFrame(scroll, fg_color="transparent")
        top_bar.grid(row=0, column=0, sticky="ew", padx=10, pady=(5, 10))
        top_bar.grid_columnconfigure(1, weight=1)

        ctk.CTkLabel(top_bar, text="제조기록 이력:", font=ctk.CTkFont(weight="bold")).grid(row=0, column=0, padx=5, pady=5)
        self.bmr_picker = ctk.CTkComboBox(top_bar, values=["-- 저장된 제조기록서 선택 --"], width=300)
        self.bmr_picker.grid(row=0, column=1, padx=5, pady=5, sticky="ew")

        ctk.CTkButton(top_bar, text="불러오기", width=80, command=self.load_selected_bmr).grid(row=0, column=2, padx=5, pady=5)
        ctk.CTkButton(top_bar, text="새로작성", width=80, fg_color="gray50", command=self.clear_bmr_form).grid(row=0, column=3, padx=5, pady=5)
        ctk.CTkButton(top_bar, text="삭제", width=70, fg_color="#D32F2F", command=self.delete_bmr).grid(row=0, column=4, padx=5, pady=5)

        # BMR 심층 서브 탭뷰 (지시서 / 칭량검증표 / 공정로그 / IPC검사 / 수율정산)
        self.bmr_subtabs = ctk.CTkTabview(scroll, height=450)
        self.bmr_subtabs.grid(row=1, column=0, sticky="nsew", padx=10, pady=5)

        tab_b1 = self.bmr_subtabs.add("1. 제조지시 및 배치개요")
        tab_b2 = self.bmr_subtabs.add("2. 원료 칭량 및 교차검증표")
        tab_b3 = self.bmr_subtabs.add("3. 단계별 제조공정 일지")
        tab_b4 = self.bmr_subtabs.add("4. 공정검사(IPC) 및 수율정산")

        # BMR 1: 제조지시 및 배치개요
        tab_b1.grid_columnconfigure((1, 3, 5), weight=1)
        b1_fields = [
            ("제품명", 0, 0), ("제조번호(LOT)", 0, 2), ("제조일자", 0, 4),
            ("제조지시량(kg)", 1, 0), ("제조설비(Tank)", 1, 2), ("제조지시자", 1, 4),
            ("제조작업자", 2, 0), ("제조책임자(승인)", 2, 2), ("배치 완료상태", 2, 4)
        ]
        for lbl, r, c in b1_fields:
            ctk.CTkLabel(tab_b1, text=lbl, font=ctk.CTkFont(weight="bold")).grid(row=r, column=c, padx=8, pady=8, sticky="w")
            if lbl == "배치 완료상태":
                cb = ctk.CTkComboBox(tab_b1, values=["제조 진행중", "공정완료 (적합)", "보류 / 재작업", "불합격 (폐기)"])
                cb.set("공정완료 (적합)")
                cb.grid(row=r, column=c+1, padx=8, pady=8, sticky="ew")
                self.bmr_entries[lbl] = cb
            else:
                ent = ctk.CTkEntry(tab_b1)
                if lbl == "제조일자": ent.insert(0, datetime.now().strftime("%Y-%m-%d"))
                elif lbl == "제조지시량(kg)": ent.insert(0, "500.00")
                elif lbl == "제조설비(Tank)": ent.insert(0, "MAIN-TANK-01 (1,000L 진공유화기)")
                ent.grid(row=r, column=c+1, padx=8, pady=8, sticky="ew")
                self.bmr_entries[lbl] = ent

        # BMR 2: 원료 칭량 및 교차검증표
        tab_b2.grid_columnconfigure(0, weight=1)
        tab_b2.grid_rowconfigure(1, weight=1)
        ctk.CTkLabel(tab_b2, text="원료별 처방배합비(%) -> 지시량(kg) vs 실측량(kg) vs 칭량 오차율(%) vs 칭량자/확인자 2중 서명:", font=ctk.CTkFont(weight="bold")).grid(row=0, column=0, padx=10, pady=5, sticky="w")
        self.bmr_weighing_textbox = ctk.CTkTextbox(tab_b2, height=350)
        self.bmr_weighing_textbox.grid(row=1, column=0, padx=10, pady=5, sticky="nsew")
        self.bmr_weighing_textbox.insert("1.0", "• [Phase A] 1. 정제수: 지시 350.00kg | 실측 350.02kg (오차 +0.01% - 적합) | 칭량자: 홍길동, 확인자: 김책임\n• [Phase A] 2. 글리세린: 지시 25.00kg | 실측 25.00kg (오차 0.00% - 적합) | 칭량자: 홍길동, 확인자: 김책임\n• [Phase A] 3. 1,2-헥산다이올: 지시 10.00kg | 실측 10.00kg (적합)\n• [Phase B] 4. 세테아릴알코올: 지시 15.00kg | 실측 15.01kg (오차 +0.07% - 적합)\n• [Phase B] 5. 카프릴릭/카프릭트라이글리세라이드: 지시 40.00kg | 실측 40.00kg (적합)\n• [Phase B] 6. 폴리솔베이트60: 지시 10.00kg | 실측 10.00kg (적합)\n• [Phase C] 7. 아데노신(주성분): 지시 0.200kg (200.0g) | 정밀저울 실측 200.1g (적합) | 칭량자: 홍길동, 확인자: 김책임\n• [Phase C] 8. 향료 및 보존보조제: 지시 2.50kg | 실측 2.50kg (적합)\n=======================================================\n[총 칭량 합계] 지시량: 500.00kg | 실칭량 합계: 500.03kg (칭량 공정 적합 완료)")

        # BMR 3: 단계별 제조공정 일지
        tab_b3.grid_columnconfigure(0, weight=1)
        tab_b3.grid_rowconfigure(1, weight=1)
        ctk.CTkLabel(tab_b3, text="공정별 실시간 작업 로그 (투입시각, 설정온도/실측온도, 교반 RPM, 진공도, 냉각, 여과):", font=ctk.CTkFont(weight="bold")).grid(row=0, column=0, padx=10, pady=5, sticky="w")
        self.bmr_log_textbox = ctk.CTkTextbox(tab_b3, height=350)
        self.bmr_log_textbox.grid(row=1, column=0, padx=10, pady=5, sticky="nsew")
        self.bmr_log_textbox.insert("1.0", "[09:00~09:30] 제조 가마 CIP/SIP 세척 및 청결 상태 확인 (검사자: 홍길동 - 적합)\n[09:30~10:15] Phase A 수상 탱크 투입 및 승온 (설정: 80℃, 실측: 78.5℃ 도달 완전 용해)\n[10:00~10:20] Phase B 유상 서브탱크 투입 및 가열 용해 (78℃ 투명 액상 확인)\n[10:30~10:45] 유화 공정: 메인 호모믹서 3,600 RPM 가동 (5분간 고속 유화) / 아지믹서 25 RPM\n[10:45~11:00] 진공 탈포: 진공 펌프 가동 (진공도 -0.082 MPa, 기포 완전 제거 확인)\n[11:00~11:40] 냉각 공정: 냉각수 순환 (45℃ 도달 시 Phase C 주성분 및 첨가제 투입 균일 교반)\n[11:40~12:00] 최종 여과: 100 mesh 여과망 통과 후 완제품 드럼 이송 (이물 불검출 확인)")

        # BMR 4: 공정검사(IPC) 및 수율정산
        tab_b4.grid_columnconfigure((1, 3), weight=1)
        b4_fields = [
            ("실생산량(kg)", 0, 0), ("공정수율(%)", 0, 2),
            ("제조중 pH(25℃)", 1, 0), ("제조중 점도(cps)", 1, 2),
            ("제조중 비중", 2, 0), ("외관/유화입도 IPC", 2, 2),
            ("손실량(Loss kg)", 3, 0), ("종합 품질 판정", 3, 2)
        ]
        b4_defaults = {
            "실생산량(kg)": "496.50",
            "공정수율(%)": "99.30%",
            "제조중 pH(25℃)": "6.12 (적합)",
            "제조중 점도(cps)": "38,500 cps (적합)",
            "제조중 비중": "0.998 (적합)",
            "외관/유화입도 IPC": "현미경 입도 균일, 층분리 없음 (적합)",
            "손실량(Loss kg)": "3.50 kg (배관 잔류 및 샘플링 손실)",
            "종합 품질 판정": "적합 (포장 공정 이관 승인)"
        }
        for lbl, r, c in b4_fields:
            ctk.CTkLabel(tab_b4, text=lbl, font=ctk.CTkFont(weight="bold")).grid(row=r, column=c, padx=10, pady=8, sticky="w")
            ent = ctk.CTkEntry(tab_b4)
            if lbl in b4_defaults: ent.insert(0, b4_defaults[lbl])
            ent.grid(row=r, column=c+1, padx=10, pady=8, sticky="ew")
            self.bmr_entries[lbl] = ent

        btn_bar = ctk.CTkFrame(scroll, fg_color="transparent")
        btn_bar.grid(row=2, column=0, sticky="e", padx=10, pady=15)
        ctk.CTkButton(btn_bar, text="💾 제조기록 DB 저장", width=120, command=self.save_bmr_to_db).pack(side="left", padx=5)
        ctk.CTkButton(btn_bar, text="📊 국문 BMR 엑셀 (4대 시트)", width=170, fg_color="#2E7D32", hover_color="#1B5E20", command=lambda: self.export_bmr_to_excel("ko")).pack(side="left", padx=5)
        ctk.CTkButton(btn_bar, text="🌐 영문 BMR 엑셀 (4 Sheets)", width=170, fg_color="#1565C0", hover_color="#0D47A1", command=lambda: self.export_bmr_to_excel("en")).pack(side="left", padx=5)

        self.refresh_bmr_list()

    def refresh_bmr_list(self):
        try:
            session = db_manager.get_session()
            recs = session.query(BatchManufacturingRecord).order_by(BatchManufacturingRecord.created_at.desc()).limit(50).all()
            vals = [f"{r.id} | {r.product_name} | LOT:{r.batch_no} | {r.batch_size_kg or 0}kg" for r in recs]
            self.bmr_picker.configure(values=vals if vals else ["-- 저장된 제조기록서 없음 --"])
            if vals: self.bmr_picker.set(vals[0])
            session.close()
        except Exception as e:
            print(f"[경고] 제조기록서 목록 로드 실패: {e}")

    def clear_bmr_form(self):
        self.current_bmr_id = None
        for k, e in self.bmr_entries.items():
            if isinstance(e, ctk.CTkComboBox):
                vals = e.cget("values")
                if vals: e.set(vals[0])
            else:
                e.delete(0, "end")
        if "제조일자" in self.bmr_entries: self.bmr_entries["제조일자"].insert(0, datetime.now().strftime("%Y-%m-%d"))
        self.bmr_log_textbox.delete("1.0", "end")
        self.bmr_weighing_textbox.delete("1.0", "end")

    def load_selected_bmr(self):
        sel = self.bmr_picker.get()
        if not sel or '|' not in sel: return
        rec_id = int(sel.split('|')[0].strip())
        session = db_manager.get_session()
        try:
            r = session.query(BatchManufacturingRecord).get(rec_id)
            if not r: return
            self.current_bmr_id = r.id
            if "제품명" in self.bmr_entries: self.bmr_entries["제품명"].delete(0, "end"); self.bmr_entries["제품명"].insert(0, r.product_name or "")
            if "제조번호(LOT)" in self.bmr_entries: self.bmr_entries["제조번호(LOT)"].delete(0, "end"); self.bmr_entries["제조번호(LOT)"].insert(0, r.batch_no or "")
            if "제조일자" in self.bmr_entries: self.bmr_entries["제조일자"].delete(0, "end"); self.bmr_entries["제조일자"].insert(0, str(r.manufacture_date or ""))
            if "제조지시량(kg)" in self.bmr_entries: self.bmr_entries["제조지시량(kg)"].delete(0, "end"); self.bmr_entries["제조지시량(kg)"].insert(0, str(r.batch_size_kg or ""))
            if "실생산량(kg)" in self.bmr_entries: self.bmr_entries["실생산량(kg)"].delete(0, "end"); self.bmr_entries["실생산량(kg)"].insert(0, str(r.actual_yield_kg or ""))
            if "공정수율(%)" in self.bmr_entries: self.bmr_entries["공정수율(%)"].delete(0, "end"); self.bmr_entries["공정수율(%)"].insert(0, f"{r.yield_rate or 99.0}%")
            if "제조설비(Tank)" in self.bmr_entries: self.bmr_entries["제조설비(Tank)"].delete(0, "end"); self.bmr_entries["제조설비(Tank)"].insert(0, r.tank_no or "")
            if "제조작업자" in self.bmr_entries: self.bmr_entries["제조작업자"].delete(0, "end"); self.bmr_entries["제조작업자"].insert(0, r.operator_name or "")
            if "제조책임자(승인)" in self.bmr_entries: self.bmr_entries["제조책임자(승인)"].delete(0, "end"); self.bmr_entries["제조책임자(승인)"].insert(0, r.supervisor_name or "")
            if "제조중 pH(25℃)" in self.bmr_entries: self.bmr_entries["제조중 pH(25℃)"].delete(0, "end"); self.bmr_entries["제조중 pH(25℃)"].insert(0, r.ph_result or "")
            if "제조중 점도(cps)" in self.bmr_entries: self.bmr_entries["제조중 점도(cps)"].delete(0, "end"); self.bmr_entries["제조중 점도(cps)"].insert(0, r.viscosity_result or "")
            
            self.bmr_log_textbox.delete("1.0", "end"); self.bmr_log_textbox.insert("1.0", r.process_log or "")
            self.bmr_weighing_textbox.delete("1.0", "end"); self.bmr_weighing_textbox.insert("1.0", r.weighing_records_json or "")
            messagebox.showinfo("불러오기 완료", f"제조기록서 '{r.product_name}'를 불러왔습니다.", parent=self)
        finally:
            session.close()

    def save_bmr_to_db(self):
        p_name = self.bmr_entries.get("제품명", ctk.CTkEntry(self)).get().strip()
        b_no = self.bmr_entries.get("제조번호(LOT)", ctk.CTkEntry(self)).get().strip()
        if not p_name or not b_no:
            messagebox.showwarning("입력 필요", "제품명과 제조번호(LOT)는 필수입니다.", parent=self); return
        session = db_manager.get_session()
        try:
            r = session.query(BatchManufacturingRecord).get(self.current_bmr_id) if self.current_bmr_id else BatchManufacturingRecord()
            r.product_name = p_name
            r.batch_no = b_no
            try: r.manufacture_date = datetime.strptime(self.bmr_entries.get("제조일자", ctk.CTkEntry(self)).get().strip(), "%Y-%m-%d").date()
            except: r.manufacture_date = None
            try: r.batch_size_kg = float(self.bmr_entries.get("제조지시량(kg)", ctk.CTkEntry(self)).get().strip())
            except: r.batch_size_kg = 0.0
            try: r.actual_yield_kg = float(self.bmr_entries.get("실생산량(kg)", ctk.CTkEntry(self)).get().strip())
            except: r.actual_yield_kg = 0.0
            
            if r.batch_size_kg > 0 and r.actual_yield_kg > 0:
                r.yield_rate = round((r.actual_yield_kg / r.batch_size_kg) * 100, 2)
            else:
                r.yield_rate = 100.0

            r.tank_no = self.bmr_entries.get("제조설비(Tank)", ctk.CTkEntry(self)).get().strip()
            r.operator_name = self.bmr_entries.get("제조작업자", ctk.CTkEntry(self)).get().strip()
            r.supervisor_name = self.bmr_entries.get("제조책임자(승인)", ctk.CTkEntry(self)).get().strip()
            r.ph_result = self.bmr_entries.get("제조중 pH(25℃)", ctk.CTkEntry(self)).get().strip()
            r.viscosity_result = self.bmr_entries.get("제조중 점도(cps)", ctk.CTkEntry(self)).get().strip()
            if "배치 완료상태" in self.bmr_entries: r.overall_status = self.bmr_entries["배치 완료상태"].get().strip()
            r.process_log = self.bmr_log_textbox.get("1.0", "end-1c").strip()
            r.weighing_records_json = self.bmr_weighing_textbox.get("1.0", "end-1c").strip()
            
            if not self.current_bmr_id: session.add(r)
            session.commit()
            self.current_bmr_id = r.id
            self.refresh_bmr_list()
            messagebox.showinfo("저장 완료", "제조지시 및 기록서가 DB에 성공적으로 저장되었습니다.", parent=self)
        except Exception as e:
            session.rollback(); messagebox.showerror("오류", f"저장 실패: {e}", parent=self)
        finally:
            session.close()

    def delete_bmr(self):
        if not self.current_bmr_id: return
        if not messagebox.askyesno("삭제 확인", "선택한 제조기록서를 삭제하시겠습니까?", parent=self): return
        session = db_manager.get_session()
        try:
            r = session.query(BatchManufacturingRecord).get(self.current_bmr_id)
            if r:
                session.delete(r); session.commit()
                self.clear_bmr_form(); self.refresh_bmr_list()
                messagebox.showinfo("완료", "삭제되었습니다.", parent=self)
        finally:
            session.close()

    def export_bmr_to_excel(self, lang="ko"):
        is_en = (lang == "en")
        p_name = self.bmr_entries.get("제품명", ctk.CTkEntry(self)).get().strip() or ("BMR_Product" if is_en else "제조기록서")
        wb = Workbook()
        
        # 시트 1: 배치 제조 지시 및 총괄 (Order & Summary)
        ws1 = wb.active
        ws1.title = "1.Batch_Order" if is_en else "1.제조지시및총괄"
        ws1.merge_cells("A1:E2")
        ws1["A1"] = f"BATCH MANUFACTURING RECORD (BMR) - {p_name}" if is_en else f"제조지시 및 기록서 [제1부 배치개요] - {p_name}"
        ws1["A1"].font = Font(name="맑은 고딕", size=15, bold=True, color="1F497D")
        ws1["A1"].alignment = Alignment(horizontal="center", vertical="center")
        ws1.append([])
        for k in ["제품명", "제조번호(LOT)", "제조일자", "제조지시량(kg)", "제조설비(Tank)", "제조지시자", "제조작업자", "제조책임자(승인)", "배치 완료상태"]:
            if k in self.bmr_entries: ws1.append([k, self.bmr_entries[k].get(), "", ""])

        # 시트 2: 원료 칭량 검증표 (Weighing Verification)
        ws2 = wb.create_sheet(title="2.Weighing_Sheet" if is_en else "2.원료칭량검증표")
        ws2.append(["[원료 칭량 지시량 vs 실측량 vs 교차 검증표 / Weighing Verification]"])
        for line in self.bmr_weighing_textbox.get("1.0", "end-1c").split('\n'): ws2.append([line])

        # 시트 3: 공정 작업 일지 (Processing Log)
        ws3 = wb.create_sheet(title="3.Process_Log" if is_en else "3.공정작업일지")
        ws3.append(["[제조 공정 실시간 작업 일지 / Real-time Processing Log]"])
        for line in self.bmr_log_textbox.get("1.0", "end-1c").split('\n'): ws3.append([line])

        # 시트 4: 공정검사(IPC) 및 수율 정산 (IPC & Yield)
        ws4 = wb.create_sheet(title="4.IPC_Yield" if is_en else "4.공정검사및수율")
        ws4.append(["검사 및 정산 항목", "결과값 / 측정치", "기준 규격", "판정"])
        for k in ["실생산량(kg)", "공정수율(%)", "제조중 pH(25℃)", "제조중 점도(cps)", "제조중 비중", "외관/유화입도 IPC", "손실량(Loss kg)", "종합 품질 판정"]:
            if k in self.bmr_entries: ws4.append([k, self.bmr_entries[k].get(), "BMR 기준치", "적합"])

        f_prefix = f"BMR_EN_4Sheets_{p_name}" if is_en else f"제조기록서_BMR4대시트_{p_name}"
        file_path = fd.asksaveasfilename(defaultextension=".xlsx", filetypes=[("Excel Files", "*.xlsx")], initialfile=f"{f_prefix}.xlsx", title=f"제조기록서 (4대 시트) 엑셀 저장")
        if file_path:
            wb.save(file_path)
            messagebox.showinfo("완료", f"제조기록서 (4개 시트)가 저장되었습니다:\n{file_path}", parent=self)
            try: os.startfile(os.path.abspath(file_path))
            except: pass

    # =========================================================================
    # 0. 물질안전보건자료 (Material Safety Data Sheet - MSDS) 16대 표준 파트 전수 심층 구조
    # =========================================================================
    def setup_msds_tab(self, tab_frame):
        tab_frame.grid_columnconfigure(0, weight=1)
        tab_frame.grid_rowconfigure(0, weight=1)

        scroll = ctk.CTkScrollableFrame(tab_frame, label_text="물질안전보건자료 (Material Safety Data Sheet - MSDS 16대 전 섹션 표준)")
        scroll.grid(row=0, column=0, sticky="nsew", padx=10, pady=10)
        scroll.grid_columnconfigure(0, weight=1)

        self.msds_entries = {}
        self.current_msds_id = None

        top_bar = ctk.CTkFrame(scroll, fg_color="transparent")
        top_bar.grid(row=0, column=0, sticky="ew", padx=10, pady=(5, 10))
        top_bar.grid_columnconfigure(1, weight=1)

        ctk.CTkLabel(top_bar, text="MSDS 이력:", font=ctk.CTkFont(weight="bold")).grid(row=0, column=0, padx=5, pady=5)
        self.msds_picker = ctk.CTkComboBox(top_bar, values=["-- 저장된 MSDS 선택 --"], width=300)
        self.msds_picker.grid(row=0, column=1, padx=5, pady=5, sticky="ew")

        ctk.CTkButton(top_bar, text="불러오기", width=75, command=self.load_selected_msds).grid(row=0, column=2, padx=4, pady=5)
        ctk.CTkButton(top_bar, text="처방연동", width=75, fg_color="#6A1B9A", hover_color="#4A148C", command=self.import_from_formulation_to_msds).grid(row=0, column=3, padx=4, pady=5)
        ctk.CTkButton(top_bar, text="새로작성", width=75, fg_color="gray50", command=self.clear_msds_form).grid(row=0, column=4, padx=4, pady=5)
        ctk.CTkButton(top_bar, text="삭제", width=65, fg_color="#D32F2F", command=self.delete_msds).grid(row=0, column=5, padx=4, pady=5)

        # 16대 섹션 서브 탭뷰
        self.msds_subtabs = ctk.CTkTabview(scroll, height=480)
        self.msds_subtabs.grid(row=1, column=0, sticky="nsew", padx=10, pady=5)

        tab_m1 = self.msds_subtabs.add("Sec 1~3. 제품·유해성·전성분")
        tab_m2 = self.msds_subtabs.add("Sec 4~8. 응급·화재·누출·취급·보호구")
        tab_m3 = self.msds_subtabs.add("Sec 9~11. 물리화학·안정성·독성")
        tab_m4 = self.msds_subtabs.add("Sec 12~16. 환경·폐기·운송·법적규제")

        # =====================================================================
        # Tab M1: Sec 1~3 (화학제품과 회사 / 유해성위험성 / 구성성분의 명칭 및 함유량)
        # =====================================================================
        tab_m1.grid_columnconfigure((1, 3), weight=1)
        
        # Sec 1 기본 정보
        m1_combos = {
            "권장용도": ["화장품 및 개인위생용품", "인체 피부 보습 및 세정용", "두발 및 바디 케어용", "직접 입력"],
            "사용상의 제한": ["화장품 용도 이외 사용 금지", "의약품 용도 사용 금지", "자료없음", "직접 입력"],
            "GHS 유해성분류": [
                "해당없음 (화장품 안전기준 적합 - 유해성 미해당)",
                "피부 부식성/피부 자극성 : 구분 2",
                "심한 눈 손상성/눈 자극성 : 구분 2",
                "인화성 액체 : 구분 3",
                "급성 독성 (경구) : 구분 4",
                "만성 수생환경 유해성 : 만성 3",
                "직접 입력"
            ],
            "그림문자/신호어": [
                "해당없음 / 없음 (None)",
                "느낌표 (!) / 경고 (Warning)",
                "불꽃 (인화성) / 경고 (Warning)",
                "부식성 / 위험 (Danger)",
                "건강유해성 / 경고 (Warning)",
                "환경유해성 / 없음",
                "직접 입력"
            ],
            "유해위험문구": [
                "통상적인 사용 조건 하에서 유해·위험성 없음",
                "H315 : 피부에 자극을 일으킴",
                "H319 : 눈에 심한 자극을 일으킴",
                "H226 : 인화성 액체 및 증기",
                "H302 : 삼키면 유해함",
                "H412 : 장기적인 영향에 의해 수생생물에게 유해함",
                "직접 입력"
            ]
        }

        m1_fields = [
            ("화학제품명(제품명)", 0, 0), ("제품코드", 0, 2),
            ("제조/공급사명", 1, 0), ("긴급전화번호", 1, 2),
            ("권장용도", 2, 0), ("사용상의 제한", 2, 2),
            ("GHS 유해성분류", 3, 0), ("그림문자/신호어", 3, 2),
            ("유해위험문구", 4, 0), ("작성자/담당부서", 4, 2)
        ]
        for lbl, r, c in m1_fields:
            ctk.CTkLabel(tab_m1, text=lbl, font=ctk.CTkFont(weight="bold")).grid(row=r, column=c, padx=8, pady=5, sticky="w")
            if lbl in m1_combos:
                cb = ctk.CTkComboBox(tab_m1, values=m1_combos[lbl])
                cb.set(m1_combos[lbl][0])
                cb.grid(row=r, column=c+1, padx=8, pady=5, sticky="ew")
                self.msds_entries[lbl] = cb
            else:
                ent = ctk.CTkEntry(tab_m1, placeholder_text=f"{lbl} 입력")
                ent.grid(row=r, column=c+1, padx=8, pady=5, sticky="ew")
                self.msds_entries[lbl] = ent

        # --- Section 3. 구성성분의 명칭 및 함유량 표준 테이블 UI ---
        sec3_header_bar = ctk.CTkFrame(tab_m1, fg_color="transparent")
        sec3_header_bar.grid(row=5, column=0, columnspan=4, sticky="ew", padx=8, pady=(12, 4))
        sec3_header_bar.grid_columnconfigure(0, weight=1)

        ctk.CTkLabel(sec3_header_bar, text="📋 [Section 3. 구성성분의 명칭 및 함유량 (표준 표 & 직접 추가 가능)]", font=ctk.CTkFont(weight="bold", size=13), text_color=("#1F497D", "#38BDF8")).grid(row=0, column=0, sticky="w")
        
        btn_box = ctk.CTkFrame(sec3_header_bar, fg_color="transparent")
        btn_box.grid(row=0, column=1, sticky="e")
        ctk.CTkButton(btn_box, text="➕ 성분 행 추가", width=100, height=26, fg_color="#0284C7", hover_color="#0369A1", command=self.add_msds_ingredient_row).pack(side="left", padx=3)
        ctk.CTkButton(btn_box, text="➖ 선택 행 삭제", width=100, height=26, fg_color="#EF4444", hover_color="#DC2626", command=self.remove_selected_msds_ingredient_row).pack(side="left", padx=3)

        self.msds_sec3_table_frame = ctk.CTkFrame(tab_m1)
        self.msds_sec3_table_frame.grid(row=6, column=0, columnspan=4, padx=8, pady=5, sticky="nsew")
        self.msds_sec3_table_frame.grid_columnconfigure(0, weight=0) # 선택 체크박스
        self.msds_sec3_table_frame.grid_columnconfigure(1, weight=3) # 화학물질명
        self.msds_sec3_table_frame.grid_columnconfigure(2, weight=3) # 관용명 및 이명(INCI)
        self.msds_sec3_table_frame.grid_columnconfigure(3, weight=2) # CAS 번호
        self.msds_sec3_table_frame.grid_columnconfigure(4, weight=2) # 식별번호
        self.msds_sec3_table_frame.grid_columnconfigure(5, weight=2) # 함유량 범위(%)
        self.msds_sec3_table_frame.grid_columnconfigure(6, weight=2) # 단일/대표값(%)

        # 테이블 헤더 렌더링
        sec3_headers = ["선택", "화학물질명", "관용명 및 이명 (INCI)", "CAS 번호", "식별번호", "함유량 범위(%)", "대표값(%)"]
        for idx, h_text in enumerate(sec3_headers):
            ctk.CTkLabel(self.msds_sec3_table_frame, text=h_text, font=ctk.CTkFont(weight="bold"), fg_color=("gray85", "gray20"), corner_radius=0).grid(row=0, column=idx, sticky="ew", padx=1, pady=1)

        self.msds_ingredient_rows = []

        # =====================================================================
        # Tab M2: Sec 4~8 (응급조치 / 화재대처 / 누출사고 / 취급저장 / 노출방지보호구)
        # =====================================================================
        tab_m2.grid_columnconfigure((1, 3), weight=1)
        m2_combos = {
            "4. 응급조치요령": [
                "눈 접촉 시 흐르는 물로 15분 이상 세척, 피부 접촉 시 비누로 세척",
                "신선한 공기가 있는 곳으로 이동, 이상 시 즉시 의사진료",
                "입을 헹구고 즉시 의료조치를 취할 것 (구토 유도 금지)",
                "통상적인 화장품 사용 조건 하 응급조치 불필요",
                "직접 입력"
            ],
            "5. 화재시 대처방법": [
                "분말소화기, CO2, 내알코올포말, 물분무 소화약제 사용",
                "비인화성 수계 물질로 화재 위험성 없음",
                "직접 입력"
            ],
            "6. 누출사고시 대처": [
                "모래나 흡유포로 흡착 수거하여 화학폐기물 용기 회수",
                "다량 누출 시 방제턱 설치 및 수로 유입 차단",
                "직접 입력"
            ],
            "7. 취급 및 저장방법": [
                "직사광선을 피하고 통풍이 잘되는 서늘한 실온(1~30℃) 밀폐 보관",
                "용기는 항상 밀폐하여 건조하고 서늘한 곳에 보관",
                "직접 입력"
            ],
            "8. 노출방지 및 보호구": [
                "일반 환기 설비 유지, 작업 시 위생 보호안경 및 보호장갑 착용",
                "국소배기장치 가동, 방진마스크 및 화학용 장갑 착용",
                "직접 입력"
            ],
            "적절한 소화약제": [
                "물분무, 분말, 포말, 이산화탄소 (CO2)",
                "해당없음 (비인화성)",
                "직접 입력"
            ]
        }
        m2_fields = [
            ("4. 응급조치요령", 0, 0), ("5. 화재시 대처방법", 0, 2),
            ("6. 누출사고시 대처", 1, 0), ("7. 취급 및 저장방법", 1, 2),
            ("8. 노출방지 및 보호구", 2, 0), ("적절한 소화약제", 2, 2)
        ]
        for lbl, r, c in m2_fields:
            ctk.CTkLabel(tab_m2, text=lbl, font=ctk.CTkFont(weight="bold")).grid(row=r, column=c, padx=8, pady=6, sticky="w")
            cb = ctk.CTkComboBox(tab_m2, values=m2_combos[lbl])
            cb.set(m2_combos[lbl][0])
            cb.grid(row=r, column=c+1, padx=8, pady=6, sticky="ew")
            self.msds_entries[lbl] = cb

        ctk.CTkLabel(tab_m2, text="[Section 4~8. 상세 취급·저장 및 응급조치 보조 텍스트 (직접 추가/편집 가능)]:", font=ctk.CTkFont(weight="bold")).grid(row=3, column=0, columnspan=4, padx=8, pady=(10, 2), sticky="w")
        self.msds_precaution_textbox = ctk.CTkTextbox(tab_m2, height=130)
        self.msds_precaution_textbox.grid(row=4, column=0, columnspan=4, padx=8, pady=5, sticky="nsew")

        # =====================================================================
        # Tab M3: Sec 9~11 (물리화학적 특성 / 안정성반응성 / 독성정보)
        # =====================================================================
        tab_m3.grid_columnconfigure((1, 3, 5), weight=1)
        m3_combos = {
            "외관(성상/색상)": ["액체 / 투명", "액체 / 무색", "유백색 크림 제형", "고체 / 흰색", "점조성 겔", "직접 입력"],
            "냄새(향취)": ["무취", "은은한 고유 향취", "특이취", "자료없음", "직접 입력"],
            "pH(25℃)": ["5.0 ~ 7.0", "5.50 ± 0.50", "6.0 ~ 8.0", "자료없음", "해당없음", "직접 입력"],
            "녹는점/어는점": ["자료없음", "약 0℃", "해당없음", "직접 입력"],
            "초기끓는점": ["약 100℃ (수용성)", "자료없음", "직접 입력"],
            "인화점": ["해당없음 (비인화성 수계 제형)", "자료없음", "직접 입력"],
            "비중(25℃)": ["0.980 ~ 1.020", "1.000 ± 0.05", "자료없음", "직접 입력"],
            "점도(cps)": ["35,000 cps", "10,000 ~ 50,000 cps", "액상 (저점도)", "자료없음", "직접 입력"],
            "용해도(수용성)": ["수용성", "분산 가용화", "지용성/불용", "자료없음", "직접 입력"],
            "10. 화학적안정성": ["상온 상압에서 매우 안정", "통상적인 보관 조건 하 안정", "자료없음", "직접 입력"],
            "유해중합반응": ["일어나지 않음", "해당없음", "자료없음", "직접 입력"],
            "피해야할 조건": ["직사광선 및 고열, 동결", "열, 스파크, 화염 등 점화원", "자료없음", "직접 입력"],
            "11. 급성독성(경구)": ["자료없음 (화장품 안전기준 적합)", "LD50 > 2,000 mg/kg (저독성)", "자료없음", "직접 입력"],
            "피부부식성/자극성": ["인체 피부 저자극 판정 (비자극)", "경미한 일시적 자극 가능", "피부 자극성 구분 2", "자료없음", "직접 입력"],
            "심한 눈손상/자극": ["경미한 일시적 자극 가능", "자극 없음", "눈 자극성 구분 2", "자료없음", "직접 입력"]
        }
        m3_fields = [
            ("외관(성상/색상)", 0, 0), ("냄새(향취)", 0, 2), ("pH(25℃)", 0, 4),
            ("녹는점/어는점", 1, 0), ("초기끓는점", 1, 2), ("인화점", 1, 4),
            ("비중(25℃)", 2, 0), ("점도(cps)", 2, 2), ("용해도(수용성)", 2, 4),
            ("10. 화학적안정성", 3, 0), ("유해중합반응", 3, 2), ("피해야할 조건", 3, 4),
            ("11. 급성독성(경구)", 4, 0), ("피부부식성/자극성", 4, 2), ("심한 눈손상/자극", 4, 4)
        ]
        for lbl, r, c in m3_fields:
            ctk.CTkLabel(tab_m3, text=lbl, font=ctk.CTkFont(weight="bold")).grid(row=r, column=c, padx=6, pady=6, sticky="w")
            cb = ctk.CTkComboBox(tab_m3, values=m3_combos[lbl])
            cb.set(m3_combos[lbl][0])
            cb.grid(row=r, column=c+1, padx=6, pady=6, sticky="ew")
            self.msds_entries[lbl] = cb

        # =====================================================================
        # Tab M4: Sec 12~16 (환경 / 폐기 / 운송 / 규제 / 기타)
        # =====================================================================
        tab_m4.grid_columnconfigure((1, 3), weight=1)
        m4_combos = {
            "12. 수생 생태독성": ["수계 환경에 유의미한 위해 없음", "만성 3 유해성", "자료없음", "직접 입력"],
            "잔류성 및 분해성": ["생분해성 양호 (쉽게 생분해됨)", "난분해성", "자료없음", "직접 입력"],
            "13. 폐기방법": ["폐기물관리법에 규정된 절차에 따라 전문 위탁 처리", "소각 또는 재활용", "직접 입력"],
            "폐기시 주의사항": ["하수도나 하천에 무단 방류 금지", "밀폐 용기에 담아 배출", "직접 입력"],
            "14. UN 번호": ["해당없음 (비위험물 Non-hazardous)", "UN 1993", "UN 1170", "직접 입력"],
            "운송위험등급": ["해당없음 (항공/해상 비위험물)", "Class 3 (인화성 액체)", "직접 입력"],
            "15. 법적규제현황": [
                "대한민국 화장품법 및 산업안전보건법 준수",
                "산업안전보건법 제110조에 따른 MSDS 작성·비치 대상",
                "화학물질관리법 유독물질 비해당",
                "직접 입력"
            ],
            "16. 작성일 및 버전": [
                f"{datetime.now().strftime('%Y-%m-%d')} (Rev. 1.0)",
                f"{datetime.now().strftime('%Y-%m-%d')} (개정 0회)",
                "직접 입력"
            ]
        }
        m4_fields = [
            ("12. 수생 생태독성", 0, 0), ("잔류성 및 분해성", 0, 2),
            ("13. 폐기방법", 1, 0), ("폐기시 주의사항", 1, 2),
            ("14. UN 번호", 2, 0), ("운송위험등급", 2, 2),
            ("15. 법적규제현황", 3, 0), ("16. 작성일 및 버전", 3, 2)
        ]
        for lbl, r, c in m4_fields:
            ctk.CTkLabel(tab_m4, text=lbl, font=ctk.CTkFont(weight="bold")).grid(row=r, column=c, padx=8, pady=8, sticky="w")
            cb = ctk.CTkComboBox(tab_m4, values=m4_combos[lbl])
            cb.set(m4_combos[lbl][0])
            cb.grid(row=r, column=c+1, padx=8, pady=8, sticky="ew")
            self.msds_entries[lbl] = cb

        ctk.CTkLabel(tab_m4, text="[Section 15~16. 법적 규제 세부 및 참고문헌·자료 출처 (직접 추가/편집 가능)]:", font=ctk.CTkFont(weight="bold")).grid(row=4, column=0, columnspan=4, padx=8, pady=(10, 2), sticky="w")
        self.msds_sections_textbox = ctk.CTkTextbox(tab_m4, height=110)
        self.msds_sections_textbox.grid(row=5, column=0, columnspan=4, padx=8, pady=5, sticky="nsew")

        btn_bar = ctk.CTkFrame(scroll, fg_color="transparent")
        btn_bar.grid(row=2, column=0, sticky="e", padx=10, pady=15)
        ctk.CTkButton(btn_bar, text="💾 MSDS DB 저장", width=120, command=self.save_msds_to_db).pack(side="left", padx=5)
        ctk.CTkButton(btn_bar, text="📊 국문 MSDS 엑셀 (16개 전 섹션)", width=180, fg_color="#2E7D32", hover_color="#1B5E20", command=lambda: self.export_msds_to_excel("ko")).pack(side="left", padx=5)
        ctk.CTkButton(btn_bar, text="🌐 영문 MSDS 엑셀 (16 Sections)", width=180, fg_color="#1565C0", hover_color="#0D47A1", command=lambda: self.export_msds_to_excel("en")).pack(side="left", padx=5)

        self.refresh_msds_list()

    def add_msds_ingredient_row(self, item_data=None):
        """Section 3 구성성분 테이블에 새로운 행을 추가합니다."""
        if not hasattr(self, 'msds_ingredient_rows'):
            self.msds_ingredient_rows = []

        row_idx = len(self.msds_ingredient_rows) + 1
        widgets = {'selected': ctk.BooleanVar()}

        chk = ctk.CTkCheckBox(self.msds_sec3_table_frame, text="", variable=widgets['selected'], width=24)
        chk.grid(row=row_idx, column=0, padx=2, pady=2)
        widgets['chk'] = chk

        # 1. 화학물질명
        e_chem = ctk.CTkEntry(self.msds_sec3_table_frame, placeholder_text="화학물질명")
        e_chem.grid(row=row_idx, column=1, sticky="ew", padx=2, pady=2)
        widgets['chem_name'] = e_chem

        # 2. 관용명 및 이명 (INCI)
        e_inci = ctk.CTkEntry(self.msds_sec3_table_frame, placeholder_text="관용명/INCI")
        e_inci.grid(row=row_idx, column=2, sticky="ew", padx=2, pady=2)
        widgets['inci_name'] = e_inci

        # 3. CAS 번호
        e_cas = ctk.CTkEntry(self.msds_sec3_table_frame, placeholder_text="CAS No.")
        e_cas.grid(row=row_idx, column=3, sticky="ew", padx=2, pady=2)
        widgets['cas_no'] = e_cas

        # 4. 식별번호
        e_ident = ctk.CTkEntry(self.msds_sec3_table_frame, placeholder_text="식별번호(선택)")
        e_ident.grid(row=row_idx, column=4, sticky="ew", padx=2, pady=2)
        widgets['ident_no'] = e_ident

        # 5. 함유량 범위(%)
        e_range = ctk.CTkEntry(self.msds_sec3_table_frame, placeholder_text="예: 65-75")
        e_range.grid(row=row_idx, column=5, sticky="ew", padx=2, pady=2)
        widgets['range_pct'] = e_range

        # 6. 단일/대표값(%)
        e_single = ctk.CTkEntry(self.msds_sec3_table_frame, placeholder_text="예: 70.0")
        e_single.grid(row=row_idx, column=6, sticky="ew", padx=2, pady=2)
        widgets['single_pct'] = e_single

        if item_data:
            if item_data.get('chem_name'): e_chem.insert(0, str(item_data['chem_name']))
            if item_data.get('inci_name'): e_inci.insert(0, str(item_data['inci_name']))
            if item_data.get('cas_no'): e_cas.insert(0, str(item_data['cas_no']))
            if item_data.get('ident_no'): e_ident.insert(0, str(item_data['ident_no']))
            if item_data.get('range_pct'): e_range.insert(0, str(item_data['range_pct']))
            if item_data.get('single_pct'): e_single.insert(0, str(item_data['single_pct']))

        self.msds_ingredient_rows.append(widgets)

    def remove_selected_msds_ingredient_row(self):
        """선택된 성분 행들을 테이블에서 삭제합니다."""
        remaining = []
        for r in self.msds_ingredient_rows:
            if r['selected'].get():
                for k, w in r.items():
                    if hasattr(w, 'destroy'):
                        w.destroy()
            else:
                remaining.append(r)
        self.msds_ingredient_rows = remaining
        # 행 재정렬
        for idx, r in enumerate(self.msds_ingredient_rows, start=1):
            r['chk'].grid(row=idx, column=0, padx=2, pady=2)
            r['chem_name'].grid(row=idx, column=1, sticky="ew", padx=2, pady=2)
            r['inci_name'].grid(row=idx, column=2, sticky="ew", padx=2, pady=2)
            r['cas_no'].grid(row=idx, column=3, sticky="ew", padx=2, pady=2)
            r['ident_no'].grid(row=idx, column=4, sticky="ew", padx=2, pady=2)
            r['range_pct'].grid(row=idx, column=5, sticky="ew", padx=2, pady=2)
            r['single_pct'].grid(row=idx, column=6, sticky="ew", padx=2, pady=2)

    def _clear_msds_ingredient_rows(self):
        for r in self.msds_ingredient_rows:
            for k, w in r.items():
                if hasattr(w, 'destroy'):
                    w.destroy()
        self.msds_ingredient_rows.clear()

    def refresh_msds_list(self):
        try:
            session = db_manager.get_session()
            recs = session.query(MSDSReport).order_by(MSDSReport.created_at.desc()).limit(50).all()
            vals = [f"{r.id} | {r.product_name} | {r.company_name or ''} | {r.created_at.strftime('%Y-%m-%d')}" for r in recs]
            self.msds_picker.configure(values=vals if vals else ["-- 저장된 MSDS 없음 --"])
            if vals: self.msds_picker.set(vals[0])
            session.close()
        except Exception as e:
            print(f"[경고] MSDS 목록 로드 실패: {e}")

    def import_from_formulation_to_msds(self):
        session = db_manager.get_session()
        try:
            forms = session.query(Formulation).order_by(Formulation.created_at.desc()).limit(30).all()
            if not forms:
                messagebox.showinfo("알림", "등록된 연구 처방이 없습니다.", parent=self); return
            
            pop = ctk.CTkToplevel(self)
            pop.title("MSDS 처방 연동")
            pop.geometry("450x200")
            pop.transient(self)
            
            ctk.CTkLabel(pop, text="MSDS로 연동할 처방을 선택하세요:", font=ctk.CTkFont(weight="bold")).pack(pady=(15, 5))
            f_vals = [f"{f.id} | {f.experiment_name} | LAB:{f.lab_no or ''}" for f in forms]
            cb = ctk.CTkComboBox(pop, values=f_vals, width=380)
            cb.pack(pady=10)

            def apply_f():
                sel = cb.get()
                if not sel: return
                fid = int(sel.split('|')[0].strip())
                target_f = session.query(Formulation).options(joinedload(Formulation.items)).filter_by(id=fid).first()
                if target_f:
                    if "화학제품명(제품명)" in self.msds_entries:
                        self.msds_entries["화학제품명(제품명)"].delete(0, "end")
                        self.msds_entries["화학제품명(제품명)"].insert(0, target_f.experiment_name or "")
                    
                    mat_ids = [it.material_id for it in (target_f.items or []) if it.material_id]
                    mats_map = {}
                    if mat_ids:
                        mats = session.query(Material).options(joinedload(Material.ingredients)).filter(Material.id.in_(mat_ids)).all()
                        mats_map = {m.id: m for m in mats}

                    # Section 3 테이블 행 재구성
                    self._clear_msds_ingredient_rows()
                    for it in (target_f.items or []):
                        m_obj = mats_map.get(it.material_id)
                        chem_name = it.material_name or ""
                        inci_name = ""
                        cas_no = ""
                        if m_obj and m_obj.ingredients:
                            inci_name = ", ".join([ing.name_en or ing.name_ko or '' for ing in m_obj.ingredients if (ing.name_en or ing.name_ko)])
                            cas_no = ", ".join([ing.cas_no for ing in m_obj.ingredients if ing.cas_no])

                        ratio_val = f"{it.ratio:.2f}%" if it.ratio is not None else ""
                        self.add_msds_ingredient_row({
                            'chem_name': chem_name,
                            'inci_name': inci_name,
                            'cas_no': cas_no or '자료없음',
                            'ident_no': '해당없음',
                            'range_pct': ratio_val,
                            'single_pct': ratio_val
                        })

                pop.destroy()
                messagebox.showinfo("연동 완료", "처방 성분이 Section 3 표준 표에 성공적으로 반영되었습니다.", parent=self)

            ctk.CTkButton(pop, text="확인 및 반영", command=apply_f).pack(pady=10)
        finally:
            session.close()

    def clear_msds_form(self):
        self.current_msds_id = None
        for k, e in self.msds_entries.items():
            if isinstance(e, ctk.CTkComboBox):
                vals = e.cget("values")
                if vals: e.set(vals[0])
            else:
                e.delete(0, "end")
        self._clear_msds_ingredient_rows()
        self.msds_precaution_textbox.delete("1.0", "end")
        self.msds_sections_textbox.delete("1.0", "end")

    def load_selected_msds(self):
        sel = self.msds_picker.get()
        if not sel or '|' not in sel: return
        rec_id = int(sel.split('|')[0].strip())
        session = db_manager.get_session()
        try:
            r = session.query(MSDSReport).get(rec_id)
            if not r: return
            self.current_msds_id = r.id
            if "화학제품명(제품명)" in self.msds_entries: self.msds_entries["화학제품명(제품명)"].delete(0, "end"); self.msds_entries["화학제품명(제품명)"].insert(0, r.product_name or "")
            if "제품코드" in self.msds_entries: self.msds_entries["제품코드"].delete(0, "end"); self.msds_entries["제품코드"].insert(0, r.product_code or "")
            if "제조/공급사명" in self.msds_entries: self.msds_entries["제조/공급사명"].delete(0, "end"); self.msds_entries["제조/공급사명"].insert(0, r.company_name or "")
            if "권장용도" in self.msds_entries: self.msds_entries["권장용도"].delete(0, "end"); self.msds_entries["권장용도"].insert(0, r.usage or "")
            if "긴급전화번호" in self.msds_entries: self.msds_entries["긴급전화번호"].delete(0, "end"); self.msds_entries["긴급전화번호"].insert(0, r.emergency_contact or "")
            if "작성자/담당부서" in self.msds_entries: self.msds_entries["작성자/담당부서"].delete(0, "end"); self.msds_entries["작성자/담당부서"].insert(0, r.author or "")
            if "유해위험문구" in self.msds_entries: self.msds_entries["유해위험문구"].delete(0, "end"); self.msds_entries["유해위험문구"].insert(0, r.hazard_statement or "")
            
            # Section 3 복구
            self._clear_msds_ingredient_rows()
            if r.formulation_snapshot:
                try:
                    import json
                    sec3_data = json.loads(r.formulation_snapshot)
                    if isinstance(sec3_data, list):
                        for row_d in sec3_data:
                            self.add_msds_ingredient_row(row_d)
                except Exception:
                    # 레거시 텍스트 포맷 폴백
                    for line in r.formulation_snapshot.split('\n'):
                        if line.strip():
                            self.add_msds_ingredient_row({'chem_name': line.strip()})

            self.msds_precaution_textbox.delete("1.0", "end"); self.msds_precaution_textbox.insert("1.0", r.precaution_statement or "")
            self.msds_sections_textbox.delete("1.0", "end"); self.msds_sections_textbox.insert("1.0", r.sections_json or "")
            messagebox.showinfo("불러오기 완료", f"MSDS '{r.product_name}' 데이터를 성공적으로 불러왔습니다.", parent=self)
        finally:
            session.close()

    def save_msds_to_db(self):
        p_name = self.msds_entries.get("화학제품명(제품명)", ctk.CTkEntry(self)).get().strip()
        if not p_name:
            messagebox.showwarning("입력 필요", "제품명은 필수 항목입니다.", parent=self); return
        session = db_manager.get_session()
        try:
            import json
            r = session.query(MSDSReport).get(self.current_msds_id) if self.current_msds_id else MSDSReport()
            r.product_name = p_name
            r.product_code = self.msds_entries.get("제품코드", ctk.CTkEntry(self)).get().strip()
            r.company_name = self.msds_entries.get("제조/공급사명", ctk.CTkEntry(self)).get().strip()
            r.usage = self.msds_entries.get("권장용도", ctk.CTkEntry(self)).get().strip()
            r.emergency_contact = self.msds_entries.get("긴급전화번호", ctk.CTkEntry(self)).get().strip()
            r.author = self.msds_entries.get("작성자/담당부서", ctk.CTkEntry(self)).get().strip()
            if "GHS 유해성분류" in self.msds_entries: r.ghs_classification = self.msds_entries["GHS 유해성분류"].get().strip()
            if "그림문자/신호어" in self.msds_entries: r.warning_mark = self.msds_entries["그림문자/신호어"].get().strip()
            r.hazard_statement = self.msds_entries.get("유해위험문구", ctk.CTkEntry(self)).get().strip()
            
            # Section 3 표 데이터 JSON 직렬화 저장
            sec3_list = []
            for row in self.msds_ingredient_rows:
                sec3_list.append({
                    'chem_name': row['chem_name'].get().strip(),
                    'inci_name': row['inci_name'].get().strip(),
                    'cas_no': row['cas_no'].get().strip(),
                    'ident_no': row['ident_no'].get().strip(),
                    'range_pct': row['range_pct'].get().strip(),
                    'single_pct': row['single_pct'].get().strip()
                })
            r.formulation_snapshot = json.dumps(sec3_list, ensure_ascii=False)

            r.precaution_statement = self.msds_precaution_textbox.get("1.0", "end-1c").strip()
            r.sections_json = self.msds_sections_textbox.get("1.0", "end-1c").strip()

            if not self.current_msds_id: session.add(r)
            session.commit()
            self.current_msds_id = r.id
            self.refresh_msds_list()
            messagebox.showinfo("저장 완료", "MSDS(물질안전보건자료)가 DB에 성공적으로 저장되었습니다.", parent=self)
        except Exception as e:
            session.rollback(); messagebox.showerror("오류", f"저장 실패: {e}", parent=self)
        finally:
            session.close()

    def delete_msds(self):
        if not self.current_msds_id: return
        if not messagebox.askyesno("삭제 확인", "선택한 MSDS를 삭제하시겠습니까?", parent=self): return
        session = db_manager.get_session()
        try:
            r = session.query(MSDSReport).get(self.current_msds_id)
            if r:
                session.delete(r); session.commit()
                self.clear_msds_form(); self.refresh_msds_list()
                messagebox.showinfo("완료", "삭제되었습니다.", parent=self)
        finally:
            session.close()

    def export_msds_to_excel(self, lang="ko"):
        """
        공식 표준 16대 섹션 MSDS(물질안전보건자료) 문서를 
        국문/영문(자동 번역 엔진 탑재)으로 완벽한 서식/테두리/표 구조로 내보냅니다.
        """
        is_en = (lang == "en")

        # 전문 영문 번역 사전 (화장품 화학, GHS, 법규, 안전 규정 전수 매핑)
        translation_map = {
            # 일반 및 GHS
            "해당없음 (화장품 안전기준 적합 - 유해성 미해당)": "Not Classified (Complies with cosmetic safety standards - Non-hazardous)",
            "해당없음 (화장품 안전기준 적합)": "Not Classified (Complies with cosmetic safety standards)",
            "해당없음": "Not Applicable",
            "자료없음": "No data available",
            "직접 입력": "Custom entry",
            "피부 부식성/피부 자극성 : 구분 2": "Skin corrosion/irritation : Category 2",
            "심한 눈 손상성/눈 자극성 : 구분 2": "Serious eye damage/eye irritation : Category 2",
            "인화성 액체 : 구분 3": "Flammable liquid : Category 3",
            "급성 독성 (경구) : 구분 4": "Acute toxicity (oral) : Category 4",
            "만성 수생환경 유해성 : 만성 3": "Hazardous to the aquatic environment (chronic) : Category 3",
            "해당없음 / 없음 (None)": "None / Not Applicable",
            "느낌표 (!) / 경고 (Warning)": "Exclamation mark (!) / Warning",
            "불꽃 (인화성) / 경고 (Warning)": "Flame / Warning",
            "부식성 / 위험 (Danger)": "Corrosion / Danger",
            "건강유해성 / 경고 (Warning)": "Health Hazard / Warning",
            "환경유해성 / 없음": "Environment / None",
            "통상적인 사용 조건 하에서 유해·위험성 없음": "No significant hazards under normal conditions of intended use.",
            "H315 : 피부에 자극을 일으킴": "H315 : Causes skin irritation",
            "H319 : 눈에 심한 자극을 일으킴": "H319 : Causes serious eye irritation",
            "H226 : 인화성 액체 및 증기": "H226 : Flammable liquid and vapour",
            "H302 : 삼키면 유해함": "H302 : Harmful if swallowed",
            "H412 : 장기적인 영향에 의해 수생생물에게 유해함": "H412 : Harmful to aquatic life with long lasting effects",
            
            # 용도 및 응급조치
            "화장품 및 개인위생용품": "Cosmetics and personal care products",
            "인체 피부 보습 및 세정용": "Human skin moisturizing and cleansing products",
            "두발 및 바디 케어용": "Hair and body care products",
            "화장품 용도 이외 사용 금지": "Do not use for purposes other than cosmetic use.",
            "의약품 용도 사용 금지": "Do not use for pharmaceutical purposes.",
            "눈 접촉 시 흐르는 물로 15분 이상 세척, 피부 접촉 시 비누로 세척": "In case of eye contact, rinse cautiously with water for at least 15 minutes. In case of skin contact, wash thoroughly with soap and water.",
            "신선한 공기가 있는 곳으로 이동, 이상 시 즉시 의사진료": "Move to fresh air. If symptoms persist or develop, seek immediate medical attention.",
            "입을 헹구고 즉시 의료조치를 취할 것 (구토 유도 금지)": "Rinse mouth thoroughly. Seek immediate medical attention. Do NOT induce vomiting unless directed by medical personnel.",
            "통상적인 화장품 사용 조건 하 응급조치 불필요": "No specific first aid measures required under normal cosmetic usage conditions.",
            
            # 소화 및 방제
            "분말소화기, CO2, 내알코올포말, 물분무 소화약제 사용": "Use ABC dry chemical, carbon dioxide (CO2), alcohol-resistant foam, or water spray.",
            "비인화성 수계 물질로 화재 위험성 없음": "Non-flammable water-based mixture; no significant fire hazard.",
            "물분무, 분말, 포말, 이산화탄소 (CO2)": "Water spray, dry chemical, alcohol-resistant foam, CO2",
            "해당없음 (비인화성)": "Not Applicable (Non-flammable)",
            "모래나 흡유포로 흡착 수거하여 화학폐기물 용기 회수": "Absorb spillage with sand, earth, or oil-absorbing pads and collect into chemical waste containers.",
            "다량 누출 시 방제턱 설치 및 수로 유입 차단": "Dike far ahead of large spills to prevent runoff into waterways, drains, or soil.",
            
            # 취급, 보관, 보호구
            "직사광선을 피하고 통풍이 잘되는 서늘한 실온(1~30℃) 밀폐 보관": "Store tightly closed in a cool, well-ventilated dry place (1~30°C), protected from direct sunlight.",
            "용기는 항상 밀폐하여 건조하고 서늘한 곳에 보관": "Keep container tightly closed in a dry and cool place.",
            "일반 환기 설비 유지, 작업 시 위생 보호안경 및 보호장갑 착용": "Provide adequate general ventilation. Wear safety goggles and protective gloves during handling.",
            "국소배기장치 가동, 방진마스크 및 화학용 장갑 착용": "Operate local exhaust ventilation. Wear dust/vapor mask and chemical-resistant gloves.",
            
            # 물리화학적 특성
            "액체 / 투명": "Liquid / Transparent",
            "액체 / 무색": "Liquid / Colorless",
            "유백색 크림 제형": "Milky white cream emulsion",
            "고체 / 흰색": "Solid / White",
            "점조성 겔": "Viscous gel",
            "무취": "Odorless",
            "은은한 고유 향취": "Faint characteristic scent",
            "특이취": "Characteristic odor",
            "약 0℃": "Approx. 0 °C",
            "약 100℃ (수용성)": "Approx. 100 °C (Water-based)",
            "해당없음 (비인화성 수계 제형)": "Not Applicable (Non-flammable aqueous formulation)",
            "비인화성": "Non-flammable",
            "수용성": "Water-soluble",
            "분산 가용화": "Dispersible / Solubilized in water",
            "지용성/불용": "Oil-soluble / Insoluble in water",
            "상온 상압에서 매우 안정": "Stable under standard ambient temperature and pressure.",
            "통상적인 보관 조건 하 안정": "Stable under recommended storage conditions.",
            "일어나지 않음": "Will not occur (Hazardous polymerization does not occur)",
            "직사광선 및 고열, 동결": "Direct sunlight, high temperatures, heat sources, and freezing conditions",
            "열, 스파크, 화염 등 점화원": "Heat, sparks, open flames, and other ignition sources",
            "자료없음 (화장품 안전기준 적합)": "No data available (Meets cosmetic safety standards)",
            "LD50 > 2,000 mg/kg (저독성)": "LD50 > 2,000 mg/kg (Low acute toxicity)",
            "인체 피부 저자극 판정 (비자극)": "Non-irritating / Mild to human skin (Primary irritation test passed)",
            "경미한 일시적 자극 가능": "May cause mild, temporary irritation.",
            "자극 없음": "Non-irritating",
            "눈 자극성 구분 2": "Eye irritation Category 2",
            "피부 자극성 구분 2": "Skin irritation Category 2",
            
            # 환경, 폐기, 운송, 규제
            "수계 환경에 유의미한 위해 없음": "No significant adverse effects on aquatic ecosystems.",
            "만성 3 유해성": "Chronic aquatic toxicity Category 3",
            "생분해성 양호 (쉽게 생분해됨)": "Readily biodegradable",
            "난분해성": "Not readily biodegradable",
            "폐기물관리법에 규정된 절차에 따라 전문 위탁 처리": "Dispose of contents/container in accordance with local, regional, national regulations via licensed waste disposal contractors.",
            "소각 또는 재활용": "Incineration or recycling in accordance with regulations",
            "하수도나 하천에 무단 방류 금지": "Do not allow product to enter drains, sewers, surface waters, or soil.",
            "밀폐 용기에 담아 배출": "Collect in sealed containers for disposal.",
            "해당없음 (비위험물 Non-hazardous)": "Not Applicable (Non-hazardous cargo)",
            "해당없음 (항공/해상 비위험물)": "Not Applicable (Not classified as dangerous goods for transport)",
            "Class 3 (인화성 액체)": "Class 3 (Flammable liquids)",
            "대한민국 화장품법 및 산업안전보건법 준수": "Complies with the Republic of Korea Cosmetics Act and Occupational Safety & Health Act.",
            "산업안전보건법 제110조에 따른 MSDS 작성·비치 대상": "Subject to MSDS preparation and placement pursuant to Article 110 of Occupational Safety & Health Act.",
            "화학물질관리법 유독물질 비해당": "Not classified as toxic substance under Chemical Control Act.",
        }

        def tr(text):
            if not is_en or not text:
                return text
            text_s = str(text).strip()
            if text_s in translation_map:
                return translation_map[text_s]
            # 부분 치환
            for k, v in translation_map.items():
                if k in text_s and len(k) > 2:
                    text_s = text_s.replace(k, v)
            return text_s

        p_name = self.msds_entries.get("화학제품명(제품명)", ctk.CTkEntry(self)).get().strip() or ("MSDS_Product" if is_en else "MSDS제품")
        p_code = self.msds_entries.get("제품코드", ctk.CTkEntry(self)).get().strip() or "AA28311-0000000001"
        comp_name = self.msds_entries.get("제조/공급사명", ctk.CTkEntry(self)).get().strip() or ("ROCPOMA COSMETIC CO., LTD." if is_en else "(주)럭포마 코스메틱")
        emer_tel = self.msds_entries.get("긴급전화번호", ctk.CTkEntry(self)).get().strip() or "031-000-0000"
        usage_txt = tr(self.msds_entries.get("권장용도", ctk.CTkEntry(self)).get().strip()) or ("Cosmetics and personal care products" if is_en else "화장품 및 개인위생용품")
        usage_limit = tr(self.msds_entries.get("사용상의 제한", ctk.CTkEntry(self)).get().strip()) or ("Do not use for purposes other than cosmetic use." if is_en else "화장품 용도 이외 사용 금지")
        ghs_class = tr(self.msds_entries.get("GHS 유해성분류", ctk.CTkEntry(self)).get().strip()) or ("Not Classified (Complies with cosmetic safety standards)" if is_en else "해당없음 (화장품 안전기준 적합)")
        ghs_mark = tr(self.msds_entries.get("그림문자/신호어", ctk.CTkEntry(self)).get().strip()) or ("None / Not Applicable" if is_en else "해당없음 / 없음 (None)")
        ghs_hazard = tr(self.msds_entries.get("유해위험문구", ctk.CTkEntry(self)).get().strip()) or ("No significant hazards under normal conditions of intended use." if is_en else "통상적인 사용 조건 하에서 유해·위험성 없음")

        wb = Workbook()
        ws = wb.active
        ws.title = "MSDS (16 Sections)" if is_en else "물질안전보건자료"
        ws.views.sheetView[0].showGridLines = True

        # 스타일 정의
        font_title = Font(name="맑은 고딕", size=16, bold=True)
        font_subtitle = Font(name="맑은 고딕", size=11, bold=True)
        font_sec_header = Font(name="맑은 고딕", size=11, bold=True, color="1F497D")
        font_tbl_header = Font(name="맑은 고딕", size=10, bold=True, color="FFFFFF")
        font_label = Font(name="맑은 고딕", size=10, bold=True)
        font_bold = Font(name="맑은 고딕", size=10, bold=True)
        font_body = Font(name="맑은 고딕", size=9.5)
        font_sub = Font(name="맑은 고딕", size=9)

        align_center = Alignment(horizontal="center", vertical="center", wrap_text=True)
        align_left = Alignment(horizontal="left", vertical="center", wrap_text=True)

        fill_sec = PatternFill(start_color="E9EFF7", end_color="E9EFF7", fill_type="solid")
        fill_tbl_header = PatternFill(start_color="4F81BD", end_color="4F81BD", fill_type="solid")
        thin = Side(style="thin", color="A6B9D0")
        thin_dark = Side(style="thin", color="595959")
        thin_border = Border(left=thin, right=thin, top=thin, bottom=thin)
        table_border = Border(left=thin_dark, right=thin_dark, top=thin_dark, bottom=thin_dark)

        def style_range(cell_range, font=None, alignment=None, fill=None, border=None):
            for r in ws[cell_range]:
                for c in r:
                    if font: c.font = font
                    if alignment: c.alignment = alignment
                    if fill: c.fill = fill
                    if border: c.border = border

        # 1. 문서 메인 타이틀 & MSDS 번호 박스
        ws.row_dimensions[1].height = 24
        ws.row_dimensions[2].height = 22
        ws.row_dimensions[3].height = 10
        ws.row_dimensions[4].height = 20

        ws.merge_cells("A1:F1")
        ws["A1"] = "MATERIAL SAFETY DATA SHEET (MSDS)" if is_en else "물질안전보건자료"
        ws["A1"].font = font_title
        ws["A1"].alignment = align_center

        ws.merge_cells("A2:F2")
        ws["A2"] = "(In accordance with GHS & Article 110 of Occupational Safety and Health Act)" if is_en else "(Material Safety Data Sheet)"
        ws["A2"].font = font_subtitle
        ws["A2"].alignment = align_center

        ws.merge_cells("E4:F4")
        ws["E4"] = f"MSDS No. : {p_code}" if is_en else f"MSDS 번호 : {p_code}"
        ws["E4"].font = font_sub
        ws["E4"].alignment = align_center
        style_range("E4:F4", border=table_border)

        curr_row = 6

        def add_section_header(sec_title_ko, sec_title_en):
            nonlocal curr_row
            ws.merge_cells(f"A{curr_row}:F{curr_row}")
            c = ws[f"A{curr_row}"]
            c.value = sec_title_en if is_en else sec_title_ko
            c.font = font_sec_header
            c.alignment = align_left
            c.fill = fill_sec
            style_range(f"A{curr_row}:F{curr_row}", fill=fill_sec, border=thin_border)
            curr_row += 1

        def add_sub_item(lbl_ko, lbl_en, val, sub_tag=""):
            nonlocal curr_row
            ws[f"A{curr_row}"] = sub_tag
            ws[f"A{curr_row}"].font = font_bold
            ws[f"A{curr_row}"].alignment = align_left

            ws[f"B{curr_row}"] = lbl_en if is_en else lbl_ko
            ws[f"B{curr_row}"].font = font_label
            ws[f"B{curr_row}"].alignment = align_left

            ws.merge_cells(f"C{curr_row}:F{curr_row}")
            ws[f"C{curr_row}"] = tr(val)
            ws[f"C{curr_row}"].font = font_body
            ws[f"C{curr_row}"].alignment = align_left
            curr_row += 1

        # Section 1
        add_section_header("1. 화학제품과 회사에 관한 정보", "1. IDENTIFICATION OF THE SUBSTANCE/MIXTURE AND OF THE COMPANY")
        add_sub_item("제품명", "Product Name", p_name, " A." if is_en else " 가.")
        add_sub_item("제품의 권고 용도와 사용상의 제한", "Relevant Identified Uses & Restrictions", "", " B." if is_en else " 나.")
        add_sub_item("권고 용도", "Recommended Use", usage_txt, "    •")
        add_sub_item("사용상의 제한", "Restrictions on Use", usage_limit, "    •")
        add_sub_item("공급자 정보 (제조자/공급사)", "Supplier / Manufacturer Details", "", " C." if is_en else " 다.")
        add_sub_item("회사명", "Company Name", comp_name, "    •")
        add_sub_item("긴급전화번호", "Emergency Phone", emer_tel, "    •")
        add_sub_item("제조사 / 공급자 추가 정보", "Additional Information", "No data available" if is_en else "자료없음", " D." if is_en else " 라.")
        curr_row += 1

        # Section 2
        add_section_header("2. 유해성·위험성", "2. HAZARDS IDENTIFICATION")
        add_sub_item("유해성·위험성 분류", "GHS Classification", ghs_class, " A." if is_en else " 가.")
        add_sub_item("경고 표지 항목", "GHS Label Elements", "", " B." if is_en else " 나.")
        add_sub_item("그림문자 및 신호어", "Signal Word & Pictogram", ghs_mark, "    •")
        add_sub_item("유해·위험 문구", "Hazard Statements", ghs_hazard, "    •")
        add_sub_item("예방조치 문구", "Precautionary Statements", 
                     "P264: Wash hands thoroughly after handling. / P280: Wear protective gloves and eye protection. / P501: Dispose of contents in accordance with local regulations." if is_en else "P264: 취급 후 철저히 씻을 것 / P280: 적절한 보호구 착용 / P501: 관련 법령에 따라 폐기", "    •")
        add_sub_item("기타 유해성·위험성", "Other Hazards", "No dust explosion hazard / No data available" if is_en else "분진폭발 위험성 없음 / 자료없음", " C." if is_en else " 다.")
        curr_row += 1

        # Section 3
        add_section_header("3. 구성성분의 명칭 및 함유량", "3. COMPOSITION / INFORMATION ON INGREDIENTS")
        
        ws.merge_cells(f"A{curr_row}:A{curr_row+1}")
        ws[f"A{curr_row}"] = "Chemical Name" if is_en else "화학물질명"
        
        ws.merge_cells(f"B{curr_row}:B{curr_row+1}")
        ws[f"B{curr_row}"] = "INCI / Common Name" if is_en else "관용명 및 이명 (INCI)"
        
        ws.merge_cells(f"C{curr_row}:D{curr_row}")
        ws[f"C{curr_row}"] = "CAS No. or Identifier" if is_en else "CAS 번호 또는 식별번호"
        ws[f"C{curr_row+1}"] = "CAS No." if is_en else "CAS 번호"
        ws[f"D{curr_row+1}"] = "Identifier" if is_en else "식별번호"

        ws.merge_cells(f"E{curr_row}:F{curr_row}")
        ws[f"E{curr_row}"] = "Concentration (%)" if is_en else "함유량 (%)"
        ws[f"E{curr_row+1}"] = "Range (%)" if is_en else "범위 (%)"
        ws[f"F{curr_row+1}"] = "Representative (%)" if is_en else "대표값/단일"

        style_range(f"A{curr_row}:F{curr_row+1}", font=font_tbl_header, fill=fill_tbl_header, alignment=align_center, border=table_border)
        curr_row += 2

        parsed_rows = []
        if hasattr(self, 'msds_ingredient_rows') and self.msds_ingredient_rows:
            for row in self.msds_ingredient_rows:
                c_name = row['chem_name'].get().strip()
                i_name = row['inci_name'].get().strip()
                cas = row['cas_no'].get().strip() or ("No data" if is_en else "자료없음")
                ident = row['ident_no'].get().strip() or ("N/A" if is_en else "해당없음")
                r_range = row['range_pct'].get().strip()
                r_single = row['single_pct'].get().strip()
                if c_name or i_name or cas:
                    # 영문 모드 시 INCI명이 있으면 화학물질명에 INCI명 우선 매핑
                    if is_en and i_name:
                        display_chem = i_name
                        display_inci = i_name
                    else:
                        display_chem = tr(c_name)
                        display_inci = i_name or tr(c_name)
                    parsed_rows.append((display_chem, display_inci, cas, ident, r_range, r_single))

        if not parsed_rows:
            parsed_rows = [
                (p_name, "Cosmetic Formulation Mixture", "N/A" if is_en else "혼합물", "N/A" if is_en else "해당없음", "100.0%", "100.0%")
            ]

        for r_chem, r_inci, r_cas, r_ident, r_range, r_single in parsed_rows:
            ws[f"A{curr_row}"] = r_chem
            ws[f"B{curr_row}"] = r_inci
            ws[f"C{curr_row}"] = r_cas
            ws[f"D{curr_row}"] = r_ident
            ws[f"E{curr_row}"] = r_range
            ws[f"F{curr_row}"] = r_single
            style_range(f"A{curr_row}:F{curr_row}", font=font_body, alignment=align_center, border=table_border)
            ws[f"A{curr_row}"].alignment = align_left
            ws[f"B{curr_row}"].alignment = align_left
            curr_row += 1
        curr_row += 1

        # Section 4
        add_section_header("4. 응급조치 요령", "4. FIRST-AID MEASURES")
        add_sub_item("눈에 들어갔을 때", "Eye Contact", "In case of contact with eyes, rinse immediately with plenty of flowing water for at least 15 minutes. If irritation persists, seek medical advice." if is_en else "물질과 접촉 시 즉시 15분 이상 흐르는 물에 눈을 씻어내시오. 자극 지속 시 안과의사 진료.", " A." if is_en else " 가.")
        add_sub_item("피부에 접촉했을 때", "Skin Contact", "Remove contaminated clothing. Wash skin thoroughly with soap and water. If irritation develops, seek medical attention." if is_en else "오염된 의복을 벗고 다량의 물과 비누로 씻어내시오. 자극 발생 시 전문의 진료.", " B." if is_en else " 나.")
        add_sub_item("흡입했을 때", "Inhalation", "Move person to fresh air. If breathing is difficult, administer oxygen or seek immediate medical attention." if is_en else "신선한 공기가 있는 곳으로 이동하시오. 호흡 곤란 시 산소 공급 또는 의료조치.", " C." if is_en else " 다.")
        add_sub_item("먹었을 때", "Ingestion", "Rinse mouth thoroughly. Seek immediate medical attention. Do NOT induce vomiting unless directed by a doctor." if is_en else "입을 헹구어 내고 즉시 의료조치를 취하시오. 의식이 없는 경우 구토를 유도하지 마시오.", " D." if is_en else " 라.")
        add_sub_item("의사의 주의사항", "Notes to Physician", "Provide this MSDS to medical personnel so they can take proper protective and treatment precautions." if is_en else "의료진이 해당 물질의 특성을 인지하고 보호조치를 취할 수 있도록 MSDS를 제시하시오.", " E." if is_en else " 마.")
        curr_row += 1

        # Section 5
        add_section_header("5. 폭발·화재시 대처방법", "5. FIRE-FIGHTING MEASURES")
        add_sub_item("적절한 소화제", "Suitable Extinguishing Media", tr(self.msds_entries.get("적절한 소화약제", ctk.CTkEntry(self)).get()) or ("ABC dry chemical, CO2, alcohol-resistant foam, water spray" if is_en else "분말소화약제, 이산화탄소(CO2), 포말 소화제"), " A." if is_en else " 가.")
        add_sub_item("특정 유해성", "Specific Hazards", "Thermal decomposition may release irritating and toxic combustion gases (carbon oxides)." if is_en else "연소 시 열분해에 의해 자극성 탄소산화물 및 미세 유해가스가 발생할 수 있음", " B." if is_en else " 나.")
        add_sub_item("화재 진압 보호구", "Protective Equipment for Firefighters", "Wear self-contained breathing apparatus (SCBA) and full protective bunker gear. Fight fire from safe distance." if is_en else "자급식 공기호흡기 및 전신 방호복을 착용하고 안전거리를 유지하여 진압", " C." if is_en else " 다.")
        curr_row += 1

        # Section 6
        add_section_header("6. 누출 사고 시 대처방법", "6. ACCIDENTAL RELEASE MEASURES")
        add_sub_item("인체 보호 조치", "Personal Precautions", "Wear appropriate protective gloves and safety glasses. Avoid contact with skin and eyes." if is_en else "적절한 보호장갑 및 보호안경을 착용하고 피부/눈 접촉을 피하시오.", " A." if is_en else " 가.")
        add_sub_item("환경 보호 조치", "Environmental Precautions", "Prevent entry into waterways, sewers, basements, or confined areas. Avoid environmental release." if is_en else "수로, 하수도, 토양으로의 대량 유입 및 환경 배출을 방지하시오.", " B." if is_en else " 나.")
        add_sub_item("정화/제거 방법", "Methods for Containment & Clean-up", "Absorb spillage with sand, earth, or absorbent pads and collect in sealed chemical waste containers." if is_en else "모래나 흡유 시트로 흡착 수거하여 밀폐된 화학폐기물 전용 용기에 회수 폐기하시오.", " C." if is_en else " 다.")
        curr_row += 1

        # Section 7
        add_section_header("7. 취급 및 저장방법", "7. HANDLING AND STORAGE")
        add_sub_item("안전취급요령", "Precautions for Safe Handling", "Handle in well-ventilated areas. Wash hands thoroughly after handling." if is_en else "환기가 원활한 장소에서 취급하고, 취급 후에는 손을 깨끗이 씻으시오.", " A." if is_en else " 가.")
        add_sub_item("안전한 저장방법", "Conditions for Safe Storage", "Store in tightly closed containers in a cool, dry, well-ventilated room (1~30°C), protected from sunlight." if is_en else "직사광선을 피하고 통풍이 잘되는 서늘한 실온(1~30℃)에 용기를 밀폐하여 보관.", " B." if is_en else " 나.")
        curr_row += 1

        # Section 8
        add_section_header("8. 노출방지 및 개인보호구", "8. EXPOSURE CONTROLS / PERSONAL PROTECTION")
        add_sub_item("노출기준", "Control Parameters / Limits", "Domestic limits: None established / ACGIH TLV: None established" if is_en else "국내 규정: 자료없음 / ACGIH 규정: 자료없음", " A." if is_en else " 가.")
        add_sub_item("공학적 관리", "Engineering Controls", "Provide general ventilation or local exhaust to maintain airborne concentrations low." if is_en else "작업장 내 국소 배기장치 또는 일반 환기 설비를 유지하시오.", " B." if is_en else " 나.")
        add_sub_item("개인보호구", "Personal Protective Equipment (PPE)", "Respiratory: Dust/mist mask / Eye: Safety goggles / Hand: Chemical-resistant gloves / Body: Clean workwear" if is_en else "호흡기: 방진마스크 / 눈: 보호보안경 / 손: 화학물질용 보호장갑 / 신체: 위생 작업복", " C." if is_en else " 다.")
        curr_row += 1

        # Section 9
        add_section_header("9. 물리화학적 특성", "9. PHYSICAL AND CHEMICAL PROPERTIES")
        
        ws.merge_cells(f"A{curr_row}:B{curr_row}")
        ws[f"A{curr_row}"] = "Parameter" if is_en else "구분"
        ws.merge_cells(f"C{curr_row}:F{curr_row}")
        ws[f"C{curr_row}"] = "Specifications / Value" if is_en else "시험 항목 세부 내용 및 기준치"
        style_range(f"A{curr_row}:F{curr_row}", font=font_tbl_header, fill=fill_tbl_header, alignment=align_center, border=table_border)
        curr_row += 1

        phys_props = [
            (("가. 외관 (성상 및 색상)", "A. Appearance (Physical state & Color)"), self.msds_entries.get("외관(성상/색상)", ctk.CTkEntry(self)).get() or "유백색 크림 제형"),
            (("나. 냄새 (향취)", "B. Odor"), self.msds_entries.get("냄새(향취)", ctk.CTkEntry(self)).get() or "은은한 고유 향취"),
            (("다. 냄새역치", "C. Odor Threshold"), "No data available" if is_en else "자료없음"),
            (("라. pH (25℃)", "D. pH (at 25°C)"), self.msds_entries.get("pH(25℃)", ctk.CTkEntry(self)).get() or "5.50 ~ 7.00"),
            (("마. 녹는점 / 어는점", "E. Melting Point / Freezing Point"), "Approx. 0 °C" if is_en else "약 0℃"),
            (("바. 초기 끓는점", "F. Initial Boiling Point"), "Approx. 100 °C (Water-based)" if is_en else "약 100℃ (수용성 제형)"),
            (("사. 인화점", "G. Flash Point"), "Not Applicable (Non-flammable)" if is_en else "해당없음 (비인화성 수계 제형)"),
            (("아. 증발속도", "H. Evaporation Rate"), "No data available" if is_en else "자료없음"),
            (("자. 인화성", "I. Flammability (Solid, Gas)"), "Non-flammable" if is_en else "비인화성"),
            (("차. 폭발 한계", "J. Flammability / Explosive Limits"), "Not Applicable" if is_en else "해당없음"),
            (("카. 증기압", "K. Vapor Pressure"), "No data available" if is_en else "자료없음"),
            (("타. 용해도", "L. Solubility"), "Water-soluble / Dispersible" if is_en else "수용성 분산 가용화"),
            (("파. 증기밀도", "M. Vapor Density"), "No data available" if is_en else "자료없음"),
            (("하. 비중 (25℃)", "N. Specific Gravity (at 25°C)"), self.msds_entries.get("비중(25℃)", ctk.CTkEntry(self)).get() or "0.980 ~ 1.020"),
            (("거. 분배계수", "O. Partition Coefficient (n-octanol/water)"), "No data available" if is_en else "자료없음"),
            (("너. 자연발화온도", "P. Auto-ignition Temperature"), "No data available" if is_en else "자료없음"),
            (("더. 분해온도", "Q. Decomposition Temperature"), "No data available" if is_en else "자료없음"),
            (("러. 점도 (25℃)", "R. Viscosity (at 25°C)"), self.msds_entries.get("점도(cps)", ctk.CTkEntry(self)).get() or "35,000 cps"),
            (("머. 분자량", "S. Molecular Weight"), "Not Applicable (Mixture)" if is_en else "해당없음 (혼합물 Mixture)")
        ]

        for p_label_pair, p_val in phys_props:
            ws.merge_cells(f"A{curr_row}:B{curr_row}")
            ws[f"A{curr_row}"] = p_label_pair[1] if is_en else p_label_pair[0]
            ws[f"A{curr_row}"].alignment = align_left
            ws.merge_cells(f"C{curr_row}:F{curr_row}")
            ws[f"C{curr_row}"] = tr(p_val)
            ws[f"C{curr_row}"].alignment = align_left
            style_range(f"A{curr_row}:F{curr_row}", font=font_body, border=table_border)
            curr_row += 1
        curr_row += 1

        # Section 10
        add_section_header("10. 안정성 및 반응성", "10. STABILITY AND REACTIVITY")
        add_sub_item("화학적 안정성 및 유해 반응", "Chemical Stability & Hazardous Reactions", "Stable under standard ambient temperature, storage, and handling conditions." if is_en else "상온 상압 및 통상적인 보관 조건 하에서 매우 안정함.", " A." if is_en else " 가.")
        add_sub_item("피해야 할 조건", "Conditions to Avoid", "Direct sunlight, high temperatures, heat sources, and freezing conditions." if is_en else "직사광선, 고온 고열, 동결 상태 및 점화원 노출을 피하시오.", " B." if is_en else " 나.")
        add_sub_item("피해야 할 물질", "Incompatible Materials", "Strong oxidizing agents, strong acids, strong bases." if is_en else "강산화제, 강산, 강염기성 물질과의 혼합을 피하시오.", " C." if is_en else " 다.")
        add_sub_item("분해시 생성 유해물질", "Hazardous Decomposition Products", "Carbon oxides and irritating vapors may form upon thermal decomposition." if is_en else "열분해 시 일산화탄소, 이산화탄소 등 자극성 흄이 발생할 수 있음.", " D." if is_en else " 라.")
        curr_row += 1

        # Section 11
        add_section_header("11. 독성에 관한 정보", "11. TOXICOLOGICAL INFORMATION")
        add_sub_item("가능성이 높은 노출 경로", "Likely Routes of Exposure", "Oral, dermal, eye contact (Safe under intended cosmetic usage)." if is_en else "경구, 경피, 눈 접촉 (통상적인 화장품 사용 조건 하 안전)", " A." if is_en else " 가.")
        add_sub_item("건강 유해성 정보", "Health Hazard Information", "", " B." if is_en else " 나.")
        
        tox_rows = [
            (("급성독성 (경구)", "Acute Oral Toxicity"), "No data available (Meets cosmetic ingredient safety standards)" if is_en else "자료없음 (화장품 원료 안전기준 적합)"),
            (("피부부식성 또는 자극성", "Skin Corrosion / Irritation"), self.msds_entries.get("피부부식성/자극성", ctk.CTkEntry(self)).get() or "인체 피부 저자극 판정"),
            (("심한 눈손상 또는 자극성", "Serious Eye Damage / Irritation"), self.msds_entries.get("심한 눈손상/자극", ctk.CTkEntry(self)).get() or "경미한 일시적 자극 가능"),
            (("호흡기/피부 과민성", "Respiratory / Skin Sensitization"), "Non-sensitizing" if is_en else "자료없음 / 과민 반응 없음"),
            (("발암성 (IARC, NTP, OSHA)", "Carcinogenicity (IARC, NTP, OSHA)"), "Not listed as carcinogen by IARC, NTP, or OSHA." if is_en else "IARC / NTP / OSHA 미분류 (발암성 물질 미포함)"),
            (("생식세포 변이원성 / 생식독성", "Germ Cell Mutagenicity / Reproductive"), "No mutagenic or reproductive toxicity observed." if is_en else "자료없음 (변이원성 해당없음)"),
            (("특정 표적장기 독성", "Specific Target Organ Toxicity (STOT)"), "Not classified / No target organ toxicity" if is_en else "자료없음 / 해당사항 없음"),
            (("흡인유해성", "Aspiration Hazard"), "Not classified" if is_en else "자료없음")
        ]
        for t_pair, t_val in tox_rows:
            add_sub_item(t_pair[0], t_pair[1], t_val, "    •")
        curr_row += 1

        # Section 12
        add_section_header("12. 환경에 미치는 영향", "12. ECOLOGICAL INFORMATION")
        add_sub_item("수생 생태독성", "Aquatic Ecotoxicity", self.msds_entries.get("12. 수생 생태독성", ctk.CTkEntry(self)).get() or "수계 환경에 유의미한 위해 없음", " A." if is_en else " 가.")
        add_sub_item("잔류성 및 분해성", "Persistence & Degradability", self.msds_entries.get("잔류성 및 분해성", ctk.CTkEntry(self)).get() or "생분해성 양호", " B." if is_en else " 나.")
        add_sub_item("생물 농축성", "Bioaccumulative Potential", "Low bioaccumulation potential." if is_en else "생체 내 축적성 없음", " C." if is_en else " 다.")
        add_sub_item("토양 이동성", "Mobility in Soil", "No data available" if is_en else "자료없음", " D." if is_en else " 라.")
        add_sub_item("기타 유해 영향", "Other Adverse Effects", "No other adverse environmental effects known." if is_en else "자료없음", " E." if is_en else " 마.")
        curr_row += 1

        # Section 13
        add_section_header("13. 폐기시 주의사항", "13. DISPOSAL CONSIDERATIONS")
        add_sub_item("폐기방법", "Disposal Methods", self.msds_entries.get("13. 폐기방법", ctk.CTkEntry(self)).get() or "폐기물관리법에 규정된 절차에 따라 전문 위탁 처리", " A." if is_en else " 가.")
        add_sub_item("폐기시 주의사항", "Disposal Precautions", self.msds_entries.get("폐기시 주의사항", ctk.CTkEntry(self)).get() or "하수도, 하천 또는 토양에 무단 방류하지 마시오.", " B." if is_en else " 나.")
        curr_row += 1

        # Section 14
        add_section_header("14. 운송에 필요한 정보", "14. TRANSPORT INFORMATION")
        add_sub_item("유엔 번호 (UN No.)", "UN Number", self.msds_entries.get("14. UN 번호", ctk.CTkEntry(self)).get() or "해당없음 (비위험물 Non-hazardous)", " A." if is_en else " 가.")
        add_sub_item("유엔 적정 선적명", "UN Proper Shipping Name", "Not Regulated" if is_en else "자료없음 (해당없음)", " B." if is_en else " 나.")
        add_sub_item("운송 위험성 등급", "Transport Hazard Class", self.msds_entries.get("운송위험등급", ctk.CTkEntry(self)).get() or "해당없음 (항공/해상 운송 규제 비해당)", " C." if is_en else " 다.")
        add_sub_item("용기등급", "Packing Group", "Not Applicable" if is_en else "해당없음", " D." if is_en else " 라.")
        add_sub_item("해양오염물질", "Marine Pollutant", "Non-pollutant (No)" if is_en else "비해당 (Non-pollutant)", " E." if is_en else " 마.")
        add_sub_item("특별 안전대책", "Special Precautions for User", "Ensure container integrity to prevent leakage during transit. Protect from direct heat." if is_en else "용기 파손 및 누출 방지, 직사광선 및 고온 노출 차단", " F." if is_en else " 바.")
        curr_row += 1

        # Section 15
        add_section_header("15. 법적 규제현황", "15. REGULATORY INFORMATION")
        add_sub_item("산업안전보건법 규제", "Occupational Safety and Health Act", "Subject to MSDS placement pursuant to Article 110." if is_en else "MSDS 작성 및 경고표시 대상물질 (산업안전보건법 제110조 준수)", " A." if is_en else " 가.")
        add_sub_item("화학물질관리법 규제", "Chemicals Control Act", "Not classified as toxic, prohibited, or restricted substance." if is_en else "유독물질, 허가물질, 제한물질 비해당", " B." if is_en else " 나.")
        add_sub_item("화장품법 규제", "Cosmetics Act (Korea / Global)", "Complies with Republic of Korea Cosmetics Act and safety criteria." if is_en else "대한민국 화장품법 및 안전기준 준수 제품", " C." if is_en else " 다.")
        add_sub_item("기타 법적 규제", "Other Safety / Waste Regulations", self.msds_entries.get("15. 법적규제현황", ctk.CTkEntry(self)).get() or "비위험물 / 지정폐기물 관리기준 준수", " D." if is_en else " 라.")
        curr_row += 1

        # Section 16
        add_section_header("16. 그 밖의 참고사항", "16. OTHER INFORMATION")
        add_sub_item("자료의 출처", "References & Data Sources", "KOSHA Chemical Database, ECHA REACH Dossiers, Ministry of Food and Drug Safety (MFDS)" if is_en else "한국산업안전보건공단(KOSHA) MSDS DB, 식품의약품안전처 화장품 성분 DB, ECHA", " A." if is_en else " 가.")
        add_sub_item("최초 작성일자", "First Creation Date", datetime.now().strftime("%Y-%m-%d"), " B." if is_en else " 나.")
        add_sub_item("개정 횟수 및 버전", "Revision & Version", self.msds_entries.get("16. 작성일 및 버전", ctk.CTkEntry(self)).get() or "Rev. 1.0 (Latest Edition)", " C." if is_en else " 다.")
        add_sub_item("기타 안내사항", "Notice / Disclaimer", "This safety data sheet provides health and safety information to aid in safe handling and management of cosmetics." if is_en else "본 자료는 화장품 원료 및 제품 취급 시 안전 대책 수립을 위해 작성된 공인 기술 자료입니다.", " D." if is_en else " 라.")

        # 열 너비 설정
        ws.column_dimensions['A'].width = 8
        ws.column_dimensions['B'].width = 28
        ws.column_dimensions['C'].width = 26
        ws.column_dimensions['D'].width = 16
        ws.column_dimensions['E'].width = 16
        ws.column_dimensions['F'].width = 18

        f_prefix = f"MSDS_EN_{p_name}" if is_en else f"MSDS_국문16대섹션_{p_name}"
        file_path = fd.asksaveasfilename(
            defaultextension=".xlsx",
            filetypes=[("Excel Files", "*.xlsx")],
            initialfile=f"{f_prefix}.xlsx",
            title="Save MSDS (English 16 Sections)" if is_en else "MSDS (16대 전 섹션 표준 엑셀) 저장"
        )
        if file_path:
            wb.save(file_path)
            messagebox.showinfo("저장 완료" if not is_en else "Export Complete", 
                                f"공식 16대 표준 서식의 MSDS가 성공적으로 생성되었습니다:\n{file_path}" if not is_en else f"MSDS (16 Sections Full English Edition) exported successfully:\n{file_path}", 
                                parent=self)
            try:
                os.startfile(os.path.abspath(file_path))
            except Exception:
                pass

    # =========================================================================
    # 4. 안정성(경시변화) 시험보고서 (Stability Test Report)
    # =========================================================================
    def setup_stability_test_tab(self, tab_frame):
        tab_frame.grid_columnconfigure(0, weight=1)
        tab_frame.grid_rowconfigure(0, weight=1)

        scroll = ctk.CTkScrollableFrame(tab_frame, label_text="안정성(경시변화) 시험보고서 (Stability Test Report)")
        scroll.grid(row=0, column=0, sticky="nsew", padx=10, pady=10)
        scroll.grid_columnconfigure(0, weight=1)

        self.stab_entries = {}
        self.current_stab_id = None

        top_bar = ctk.CTkFrame(scroll, fg_color="transparent")
        top_bar.grid(row=0, column=0, sticky="ew", padx=10, pady=(5, 15))
        top_bar.grid_columnconfigure(1, weight=1)

        ctk.CTkLabel(top_bar, text="안정성 이력:", font=ctk.CTkFont(weight="bold")).grid(row=0, column=0, padx=5, pady=5)
        self.stab_picker = ctk.CTkComboBox(top_bar, values=["-- 저장된 안정성보고서 선택 --"], width=300)
        self.stab_picker.grid(row=0, column=1, padx=5, pady=5, sticky="ew")

        ctk.CTkButton(top_bar, text="불러오기", width=80, command=self.load_selected_stab).grid(row=0, column=2, padx=5, pady=5)
        ctk.CTkButton(top_bar, text="새로작성", width=80, fg_color="gray50", command=self.clear_stab_form).grid(row=0, column=3, padx=5, pady=5)
        ctk.CTkButton(top_bar, text="삭제", width=70, fg_color="#D32F2F", command=self.delete_stab).grid(row=0, column=4, padx=5, pady=5)

        info_frame = ctk.CTkFrame(scroll)
        info_frame.grid(row=1, column=0, sticky="ew", padx=10, pady=5)
        info_frame.grid_columnconfigure((1, 3, 5), weight=1)

        fields = [
            ("제품명", 0, 0), ("제조번호(LOT)", 0, 2), ("시험시작일", 0, 4),
            ("시험담당자", 1, 0), ("종합평가", 1, 2)
        ]

        for label_text, r, c in fields:
            ctk.CTkLabel(info_frame, text=label_text, font=ctk.CTkFont(weight="bold")).grid(row=r, column=c, padx=8, pady=5, sticky="w")
            if label_text == "종합평가":
                cb = ctk.CTkComboBox(info_frame, values=["안정 (양호)", "경미한 변화(허용범위)", "불안정(변색/분리)"], width=160)
                cb.set("안정 (양호)")
                cb.grid(row=r, column=c+1, padx=8, pady=5, sticky="ew")
                self.stab_entries[label_text] = cb
            else:
                entry = ctk.CTkEntry(info_frame)
                if label_text == "시험시작일": entry.insert(0, datetime.now().strftime("%Y-%m-%d"))
                entry.grid(row=r, column=c+1, padx=8, pady=5, sticky="ew")
                self.stab_entries[label_text] = entry

        # 가혹 조건별 경시변화 매트릭스 테이블
        cond_frame = ctk.CTkFrame(scroll)
        cond_frame.grid(row=2, column=0, sticky="ew", padx=10, pady=10)
        cond_frame.grid_columnconfigure((1, 2, 3, 4, 5), weight=1)

        headers = ["보관 조건", "초기 (0주)", "2주 경과", "4주 경과", "8주 경과", "12주 경과"]
        for idx, h in enumerate(headers):
            ctk.CTkLabel(cond_frame, text=h, font=ctk.CTkFont(weight="bold")).grid(row=0, column=idx, padx=5, pady=5)

        conditions = [
            "실온 (25℃)",
            "고온 (45℃)",
            "극고온 (50℃)",
            "저온 (4℃)",
            "Cycle (-10~40℃)",
            "광안정성 (UV)"
        ]

        self.stab_matrix_entries = {}
        for r_idx, cond in enumerate(conditions, 1):
            ctk.CTkLabel(cond_frame, text=cond, font=ctk.CTkFont(weight="bold")).grid(row=r_idx, column=0, padx=5, pady=4, sticky="w")
            self.stab_matrix_entries[cond] = []
            for c_idx in range(1, 6):
                e = ctk.CTkEntry(cond_frame, width=90)
                e.insert(0, "이상없음" if c_idx < 3 else "안정")
                e.grid(row=r_idx, column=c_idx, padx=4, pady=4, sticky="ew")
                self.stab_matrix_entries[cond].append(e)

        btn_bar = ctk.CTkFrame(scroll, fg_color="transparent")
        btn_bar.grid(row=3, column=0, sticky="e", padx=10, pady=15)
        ctk.CTkButton(btn_bar, text="💾 안정성보고서 DB 저장", width=140, command=self.save_stab_to_db).pack(side="left", padx=5)
        ctk.CTkButton(btn_bar, text="📊 안정성 엑셀 출력", width=140, fg_color="#2E7D32", hover_color="#1B5E20", command=self.export_stab_to_excel).pack(side="left", padx=5)

        self.refresh_stab_list()

    def refresh_stab_list(self):
        try:
            session = db_manager.get_session()
            recs = session.query(StabilityTestReport).order_by(StabilityTestReport.created_at.desc()).limit(50).all()
            vals = [f"{r.id} | {r.product_name} | LOT:{r.lot_no or ''} | {r.overall_evaluation or ''}" for r in recs]
            self.stab_picker.configure(values=vals if vals else ["-- 저장된 안정성보고서 없음 --"])
            if vals: self.stab_picker.set(vals[0])
            session.close()
        except Exception as e:
            print(f"[경고] 안정성보고서 목록 로드 실패: {e}")

    def clear_stab_form(self):
        self.current_stab_id = None
        for k, e in self.stab_entries.items():
            if isinstance(e, ctk.CTkComboBox): e.set(e.cget("values")[0])
            else: e.delete(0, "end")
        self.stab_entries["시험시작일"].insert(0, datetime.now().strftime("%Y-%m-%d"))

    def load_selected_stab(self):
        sel = self.stab_picker.get()
        if not sel or '|' not in sel: return
        rec_id = int(sel.split('|')[0].strip())
        session = db_manager.get_session()
        try:
            r = session.query(StabilityTestReport).get(rec_id)
            if not r: return
            self.current_stab_id = r.id
            self.stab_entries["제품명"].delete(0, "end"); self.stab_entries["제품명"].insert(0, r.product_name or "")
            self.stab_entries["제조번호(LOT)"].delete(0, "end"); self.stab_entries["제조번호(LOT)"].insert(0, r.lot_no or "")
            self.stab_entries["시험시작일"].delete(0, "end"); self.stab_entries["시험시작일"].insert(0, str(r.test_start_date or ""))
            self.stab_entries["시험담당자"].delete(0, "end"); self.stab_entries["시험담당자"].insert(0, r.examiner or "")
            self.stab_entries["종합평가"].set(r.overall_evaluation or "안정 (양호)")
            
            if r.test_results_json:
                import json
                matrix = json.loads(r.test_results_json)
                for cond, vals in matrix.items():
                    if cond in self.stab_matrix_entries:
                        for i, v in enumerate(vals):
                            if i < len(self.stab_matrix_entries[cond]):
                                self.stab_matrix_entries[cond][i].delete(0, "end")
                                self.stab_matrix_entries[cond][i].insert(0, str(v))
            messagebox.showinfo("불러오기 완료", f"안정성보고서 '{r.product_name}'를 불러왔습니다.", parent=self)
        finally:
            session.close()

    def save_stab_to_db(self):
        p_name = self.stab_entries["제품명"].get().strip()
        if not p_name:
            messagebox.showwarning("입력 필요", "제품명은 필수 항목입니다.", parent=self); return
        import json
        matrix_data = {}
        for cond, entries in self.stab_matrix_entries.items():
            matrix_data[cond] = [e.get().strip() for e in entries]

        session = db_manager.get_session()
        try:
            r = session.query(StabilityTestReport).get(self.current_stab_id) if self.current_stab_id else StabilityTestReport()
            r.product_name = p_name
            r.lot_no = self.stab_entries["제조번호(LOT)"].get().strip()
            try: r.test_start_date = datetime.strptime(self.stab_entries["시험시작일"].get().strip(), "%Y-%m-%d").date()
            except: r.test_start_date = None
            r.examiner = self.stab_entries["시험담당자"].get().strip()
            r.overall_evaluation = self.stab_entries["종합평가"].get().strip()
            r.test_results_json = json.dumps(matrix_data, ensure_ascii=False)

            if not self.current_stab_id: session.add(r)
            session.commit()
            self.current_stab_id = r.id
            self.refresh_stab_list()
            messagebox.showinfo("저장 완료", "안정성 시험보고서가 DB에 성공적으로 저장되었습니다.", parent=self)
        except Exception as e:
            session.rollback(); messagebox.showerror("오류", f"저장 실패: {e}", parent=self)
        finally:
            session.close()

    def delete_stab(self):
        if not self.current_stab_id: return
        if not messagebox.askyesno("삭제 확인", "선택한 안정성보고서를 삭제하시겠습니까?", parent=self): return
        session = db_manager.get_session()
        try:
            r = session.query(StabilityTestReport).get(self.current_stab_id)
            if r:
                session.delete(r); session.commit()
                self.clear_stab_form(); self.refresh_stab_list()
                messagebox.showinfo("완료", "삭제되었습니다.", parent=self)
        finally:
            session.close()

    def export_stab_to_excel(self):
        p_name = self.stab_entries["제품명"].get().strip() or "안정성보고서"
        wb = Workbook(); ws = wb.active; ws.title = "안정성보고서"
        ws.merge_cells("A1:F2")
        ws["A1"] = f"화장품 안정성(경시변화) 시험보고서 - {p_name}"
        ws["A1"].font = Font(name="맑은 고딕", size=16, bold=True, color="1F497D")
        ws["A1"].alignment = Alignment(horizontal="center", vertical="center")
        ws.append([])
        ws.append(["제품명", p_name, "", "제조번호(LOT)", self.stab_entries["제조번호(LOT)"].get(), ""])
        ws.append(["시험시작일", self.stab_entries["시험시작일"].get(), "", "시험담당자", self.stab_entries["시험담당자"].get(), ""])
        ws.append(["종합평가", self.stab_entries["종합평가"].get(), "", "", "", ""])
        ws.append([])
        ws.append(["보관 조건", "초기 (0주)", "2주 경과", "4주 경과", "8주 경과", "12주 경과"])
        for cond, entries in self.stab_matrix_entries.items():
            row = [cond] + [e.get().strip() for e in entries]
            ws.append(row)

        file_path = fd.asksaveasfilename(defaultextension=".xlsx", filetypes=[("Excel Files", "*.xlsx")], initialfile=f"안정성보고서_{p_name}.xlsx", title="안정성보고서 엑셀 저장")
        if file_path:
            wb.save(file_path)
            messagebox.showinfo("완료", f"안정성보고서가 저장되었습니다:\n{file_path}", parent=self)
            try: os.startfile(os.path.abspath(file_path))
            except: pass

    # =========================================================================
    # 5. 내용물-용기 상용성(적합성) 시험보고서 (Packaging Compatibility Report)
    # =========================================================================
    def setup_packaging_compatibility_tab(self, tab_frame):
        tab_frame.grid_columnconfigure(0, weight=1)
        tab_frame.grid_rowconfigure(0, weight=1)

        scroll = ctk.CTkScrollableFrame(tab_frame, label_text="용기-내용물 상용성(적합성) 시험보고서 (Packaging Compatibility)")
        scroll.grid(row=0, column=0, sticky="nsew", padx=10, pady=10)
        scroll.grid_columnconfigure(0, weight=1)

        self.comp_entries = {}
        self.current_comp_id = None

        top_bar = ctk.CTkFrame(scroll, fg_color="transparent")
        top_bar.grid(row=0, column=0, sticky="ew", padx=10, pady=(5, 15))
        top_bar.grid_columnconfigure(1, weight=1)

        ctk.CTkLabel(top_bar, text="상용성 이력:", font=ctk.CTkFont(weight="bold")).grid(row=0, column=0, padx=5, pady=5)
        self.comp_picker = ctk.CTkComboBox(top_bar, values=["-- 저장된 상용성보고서 선택 --"], width=300)
        self.comp_picker.grid(row=0, column=1, padx=5, pady=5, sticky="ew")

        ctk.CTkButton(top_bar, text="불러오기", width=80, command=self.load_selected_comp).grid(row=0, column=2, padx=5, pady=5)
        ctk.CTkButton(top_bar, text="새로작성", width=80, fg_color="gray50", command=self.clear_comp_form).grid(row=0, column=3, padx=5, pady=5)
        ctk.CTkButton(top_bar, text="삭제", width=70, fg_color="#D32F2F", command=self.delete_comp).grid(row=0, column=4, padx=5, pady=5)

        info_frame = ctk.CTkFrame(scroll)
        info_frame.grid(row=1, column=0, sticky="ew", padx=10, pady=5)
        info_frame.grid_columnconfigure((1, 3, 5), weight=1)

        fields = [
            ("제품명", 0, 0), ("LAB NO", 0, 2), ("의뢰업체", 0, 4),
            ("용기명", 1, 0), ("용기재질", 1, 2), ("캡/펌프사양", 1, 4),
            ("코팅/인쇄", 2, 0), ("시험담당자", 2, 2), ("종합판정", 2, 4)
        ]

        for label_text, r, c in fields:
            ctk.CTkLabel(info_frame, text=label_text, font=ctk.CTkFont(weight="bold")).grid(row=r, column=c, padx=8, pady=5, sticky="w")
            if label_text == "종합판정":
                cb = ctk.CTkComboBox(info_frame, values=["적합 (Pass)", "부적합 (Fail)", "조건부 적합"], width=160)
                cb.set("적합 (Pass)")
                cb.grid(row=r, column=c+1, padx=8, pady=5, sticky="ew")
                self.comp_entries[label_text] = cb
            elif label_text == "용기재질":
                cb = ctk.CTkComboBox(info_frame, values=["PET", "PP", "PE", "HDPE", "아크릴", "유리", "알루미늄", "복합튜브"], width=160)
                cb.set("PET")
                cb.grid(row=r, column=c+1, padx=8, pady=5, sticky="ew")
                self.comp_entries[label_text] = cb
            else:
                entry = ctk.CTkEntry(info_frame)
                entry.grid(row=r, column=c+1, padx=8, pady=5, sticky="ew")
                self.comp_entries[label_text] = entry

        # 핵심 평가 6대 검사 항목
        eval_frame = ctk.CTkFrame(scroll)
        eval_frame.grid(row=2, column=0, sticky="ew", padx=10, pady=10)
        eval_frame.grid_columnconfigure((1, 3), weight=1)

        eval_fields = [
            ("감량율 (45℃ 4주, %)", 0, 0, "0.32% (기준 1.5% 이하 적합)"),
            ("용기외관 변형여부", 0, 2, "함몰/팽창/크랙 없음 (정상)"),
            ("인쇄/코팅 박리여부", 1, 0, "박리 및 번짐 없음 (이상무)"),
            ("펌프/토출 작동성", 1, 2, "토출량 편차 없음 / 누액 없음"),
            ("진공감압 누액시험", 2, 0, "-0.08MPa 10분 누액 없음 (적합)"),
            ("내용물 변질여부", 2, 2, "변색/취변/분리 없음 (정상)")
        ]

        for label_text, r, c, default_val in eval_fields:
            ctk.CTkLabel(eval_frame, text=label_text, font=ctk.CTkFont(weight="bold")).grid(row=r, column=c, padx=8, pady=6, sticky="w")
            entry = ctk.CTkEntry(eval_frame)
            entry.insert(0, default_val)
            entry.grid(row=r, column=c+1, padx=8, pady=6, sticky="ew")
            self.comp_entries[label_text] = entry

        # 권고사항 및 비고
        note_frame = ctk.CTkFrame(scroll)
        note_frame.grid(row=3, column=0, sticky="ew", padx=10, pady=10)
        note_frame.grid_columnconfigure(1, weight=1)

        ctk.CTkLabel(note_frame, text="개선 권고사항 및 종합 소견:", font=ctk.CTkFont(weight="bold")).grid(row=0, column=0, padx=10, pady=5, sticky="nw")
        self.comp_recom_textbox = ctk.CTkTextbox(note_frame, height=70)
        self.comp_recom_textbox.grid(row=0, column=1, padx=10, pady=5, sticky="ew")
        self.comp_recom_textbox.insert("1.0", "내용물과 용기 간 감량율 및 토출 작동성이 매우 우수하여 양산 적합 판정함.")

        btn_bar = ctk.CTkFrame(scroll, fg_color="transparent")
        btn_bar.grid(row=4, column=0, sticky="e", padx=10, pady=15)
        ctk.CTkButton(btn_bar, text="💾 상용성보고서 DB 저장", width=150, command=self.save_comp_to_db).pack(side="left", padx=5)
        ctk.CTkButton(btn_bar, text="📊 상용성 엑셀 출력", width=150, fg_color="#2E7D32", hover_color="#1B5E20", command=self.export_comp_to_excel).pack(side="left", padx=5)

        self.refresh_comp_list()

    def refresh_comp_list(self):
        try:
            session = db_manager.get_session()
            recs = session.query(PackagingCompatibilityReport).order_by(PackagingCompatibilityReport.created_at.desc()).limit(50).all()
            vals = [f"{r.id} | {r.product_name} | 용기:{r.container_name or ''} | {r.overall_result}" for r in recs]
            self.comp_picker.configure(values=vals if vals else ["-- 저장된 상용성보고서 없음 --"])
            if vals: self.comp_picker.set(vals[0])
            session.close()
        except Exception as e:
            print(f"[경고] 상용성보고서 목록 로드 실패: {e}")

    def clear_comp_form(self):
        self.current_comp_id = None
        for k, e in self.comp_entries.items():
            if isinstance(e, ctk.CTkComboBox): e.set(e.cget("values")[0])
            else: e.delete(0, "end")
        self.comp_recom_textbox.delete("1.0", "end")

    def load_selected_comp(self):
        sel = self.comp_picker.get()
        if not sel or '|' not in sel: return
        rec_id = int(sel.split('|')[0].strip())
        session = db_manager.get_session()
        try:
            r = session.query(PackagingCompatibilityReport).get(rec_id)
            if not r: return
            self.current_comp_id = r.id
            self.comp_entries["제품명"].delete(0, "end"); self.comp_entries["제품명"].insert(0, r.product_name or "")
            self.comp_entries["LAB NO"].delete(0, "end"); self.comp_entries["LAB NO"].insert(0, r.lab_no or "")
            self.comp_entries["의뢰업체"].delete(0, "end"); self.comp_entries["의뢰업체"].insert(0, r.client_name or "")
            self.comp_entries["용기명"].delete(0, "end"); self.comp_entries["용기명"].insert(0, r.container_name or "")
            self.comp_entries["용기재질"].set(r.container_material or "PET")
            self.comp_entries["캡/펌프사양"].delete(0, "end"); self.comp_entries["캡/펌프사양"].insert(0, r.pump_specs or "")
            self.comp_entries["코팅/인쇄"].delete(0, "end"); self.comp_entries["코팅/인쇄"].insert(0, r.coating_printing or "")
            self.comp_entries["시험담당자"].delete(0, "end"); self.comp_entries["시험담당자"].insert(0, r.examiner or "")
            self.comp_entries["종합판정"].set(r.overall_result or "적합 (Pass)")
            
            self.comp_entries["감량율 (45℃ 4주, %)"].delete(0, "end"); self.comp_entries["감량율 (45℃ 4주, %)"].insert(0, r.weight_loss_rate or "")
            self.comp_entries["용기외관 변형여부"].delete(0, "end"); self.comp_entries["용기외관 변형여부"].insert(0, r.container_deformation or "")
            self.comp_entries["인쇄/코팅 박리여부"].delete(0, "end"); self.comp_entries["인쇄/코팅 박리여부"].insert(0, r.coating_peeling or "")
            self.comp_entries["펌프/토출 작동성"].delete(0, "end"); self.comp_entries["펌프/토출 작동성"].insert(0, r.pump_operability or "")
            self.comp_entries["진공감압 누액시험"].delete(0, "end"); self.comp_entries["진공감압 누액시험"].insert(0, r.leakage_test or "")
            self.comp_entries["내용물 변질여부"].delete(0, "end"); self.comp_entries["내용물 변질여부"].insert(0, r.contents_change or "")

            self.comp_recom_textbox.delete("1.0", "end"); self.comp_recom_textbox.insert("1.0", r.recommendations or "")
            messagebox.showinfo("불러오기 완료", f"상용성보고서 '{r.product_name}'를 불러왔습니다.", parent=self)
        finally:
            session.close()

    def save_comp_to_db(self):
        p_name = self.comp_entries["제품명"].get().strip()
        if not p_name:
            messagebox.showwarning("입력 필요", "제품명은 필수 항목입니다.", parent=self); return
        session = db_manager.get_session()
        try:
            r = session.query(PackagingCompatibilityReport).get(self.current_comp_id) if self.current_comp_id else PackagingCompatibilityReport()
            r.product_name = p_name
            r.lab_no = self.comp_entries["LAB NO"].get().strip()
            r.client_name = self.comp_entries["의뢰업체"].get().strip()
            r.container_name = self.comp_entries["용기명"].get().strip()
            r.container_material = self.comp_entries["용기재질"].get().strip()
            r.pump_specs = self.comp_entries["캡/펌프사양"].get().strip()
            r.coating_printing = self.comp_entries["코팅/인쇄"].get().strip()
            r.examiner = self.comp_entries["시험담당자"].get().strip()
            r.overall_result = self.comp_entries["종합판정"].get().strip()
            
            r.weight_loss_rate = self.comp_entries["감량율 (45℃ 4주, %)"].get().strip()
            r.container_deformation = self.comp_entries["용기외관 변형여부"].get().strip()
            r.coating_peeling = self.comp_entries["인쇄/코팅 박리여부"].get().strip()
            r.pump_operability = self.comp_entries["펌프/토출 작동성"].get().strip()
            r.leakage_test = self.comp_entries["진공감압 누액시험"].get().strip()
            r.contents_change = self.comp_entries["내용물 변질여부"].get().strip()
            r.recommendations = self.comp_recom_textbox.get("1.0", "end-1c").strip()

            if not self.current_comp_id: session.add(r)
            session.commit()
            self.current_comp_id = r.id
            self.refresh_comp_list()
            messagebox.showinfo("저장 완료", "용기-내용물 상용성 시험보고서가 DB에 성공적으로 저장되었습니다.", parent=self)
        except Exception as e:
            session.rollback(); messagebox.showerror("오류", f"저장 실패: {e}", parent=self)
        finally:
            session.close()

    def delete_comp(self):
        if not self.current_comp_id: return
        if not messagebox.askyesno("삭제 확인", "선택한 상용성보고서를 삭제하시겠습니까?", parent=self): return
        session = db_manager.get_session()
        try:
            r = session.query(PackagingCompatibilityReport).get(self.current_comp_id)
            if r:
                session.delete(r); session.commit()
                self.clear_comp_form(); self.refresh_comp_list()
                messagebox.showinfo("완료", "삭제되었습니다.", parent=self)
        finally:
            session.close()

    def export_comp_to_excel(self):
        p_name = self.comp_entries["제품명"].get().strip() or "상용성보고서"
        wb = Workbook(); ws = wb.active; ws.title = "용기상용성보고서"
        ws.merge_cells("A1:D2")
        ws["A1"] = f"용기-내용물 상용성(적합성) 시험보고서 - {p_name}"
        ws["A1"].font = Font(name="맑은 고딕", size=16, bold=True, color="1F497D")
        ws["A1"].alignment = Alignment(horizontal="center", vertical="center")
        ws.append([])
        for k, v in self.comp_entries.items():
            ws.append([k, v.get(), "", ""])

        file_path = fd.asksaveasfilename(defaultextension=".xlsx", filetypes=[("Excel Files", "*.xlsx")], initialfile=f"용기상용성보고서_{p_name}.xlsx", title="상용성보고서 엑셀 저장")
        if file_path:
            wb.save(file_path)
            messagebox.showinfo("완료", f"용기 상용성보고서가 저장되었습니다:\n{file_path}", parent=self)
            try: os.startfile(os.path.abspath(file_path))
            except: pass



    # =========================================================================
    # 네비게이션 및 새로고침
    # =========================================================================
    def switch_to_tab(self, tab_name):
        try:
            if hasattr(self, 'tab_view') and hasattr(self.tab_view, '_segmented_button'):
                self.tab_view._segmented_button.grid_forget()
        except Exception:
            pass

        tab_key = tab_name
        tab_name_mapping = {
            "coa": self.texts.get('coa', 'COA (시험성적서)'),
            "msds": self.texts.get('msds', 'MSDS (물질안전보건자료)'),
            "ingredient_report": self.texts.get('ingredient_report', '원료목록보고'),
            "mat_inspection": self.texts.get('mat_inspection', '원료 입고검사'),
            "prod_standard": self.texts.get('prod_standard', '제품표준서'),
            "mfg_record": self.texts.get('mfg_record', '제조관리기록서'),
            "stability_test": self.texts.get('stability_test', '안정성 시험'),
            "compatibility_test": self.texts.get('compatibility_test', '용기 상용성 시험')
        }
        
        # 키 매핑 역탐색
        for k, v in tab_name_mapping.items():
            if tab_name in (k, v):
                tab_key = k
                break

        # 해당 탭이 아직 초기화되지 않았다면 즉시 빌드
        self.ensure_tab_initialized(tab_key)

        target_tab = tab_name_mapping.get(tab_key, tab_name)
        if hasattr(self, 'tab_view') and target_tab in self.tab_view._name_list:
            self.tab_view.set(target_tab)

    def refresh_data(self):
        """품질 관리 프레임의 전체 데이터를 새로고침합니다. (초기화된 탭만 선별 갱신)"""
        try:
            if 'coa' in self._initialized_tabs:
                if hasattr(self, 'refresh_semi_coa_list'): self.refresh_semi_coa_list()
                if hasattr(self, 'refresh_finished_coa_list'): self.refresh_finished_coa_list()
            if 'msds' in self._initialized_tabs and hasattr(self, 'refresh_msds_list'):
                self.refresh_msds_list()
            if 'ingredient_report' in self._initialized_tabs and hasattr(self, 'refresh_ingredient_report_list'):
                self.refresh_ingredient_report_list()
            if 'mat_inspection' in self._initialized_tabs and hasattr(self, 'refresh_mat_insp_list'):
                self.refresh_mat_insp_list()
            if 'prod_standard' in self._initialized_tabs and hasattr(self, 'refresh_prod_std_list'):
                self.refresh_prod_std_list()
            if 'mfg_record' in self._initialized_tabs and hasattr(self, 'refresh_bmr_list'):
                self.refresh_bmr_list()
            if 'stability_test' in self._initialized_tabs and hasattr(self, 'refresh_stab_list'):
                self.refresh_stab_list()
            if 'compatibility_test' in self._initialized_tabs and hasattr(self, 'refresh_comp_list'):
                self.refresh_comp_list()
        except Exception as e:
            print(f"[오류] 품질 관리 프레임 새로고침 실패: {e}")

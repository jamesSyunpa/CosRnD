import customtkinter as ctk
import tkinter as tk
from tkinter import ttk, messagebox
from sqlalchemy import func, desc
import sys
import os

# 프로젝트 루트 경로를 sys.path에 추가 (상대 경로 import를 위함)
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if PROJECT_ROOT not in sys.path:
    sys.path.append(PROJECT_ROOT)

from tkcalendar import DateEntry
from database.db_manager import db_manager
from database.models import Client, Formulation, FormulationItem, Material
from datetime import datetime, date
from modules import excel_handler
from modules.comparison_popup import FormulationComparisonPopup
from modules.folder_history_popup import FolderHistoryPopup
from modules.ui_components import HelpPopup, CustomErrorDialog, CustomDropdown, AddMaterialDialog, try_convert_to_float
from modules.formulation_popup import FormulationEditPopup # FormulationEditPopup은 그대로 둡니다.

class ClipboardErrorDialog(ctk.CTkToplevel):
    """오류 메시지를 표시하고 클립보드에 자동으로 복사하는 대화상자"""
    def __init__(self, master, title="오류", error_message=""):
        super().__init__(master)
        self.title(title)
        self.transient(master)
        self.grab_set()
        self.resizable(False, False)

        # 오류 메시지를 클립보드에 복사
        self.clipboard_clear()
        self.clipboard_append(error_message)

        main_frame = ctk.CTkFrame(self)
        main_frame.pack(padx=20, pady=20, fill="both", expand=True)

        ctk.CTkLabel(main_frame, text="오류가 발생했습니다.", font=ctk.CTkFont(size=16, weight="bold")).pack(pady=(0, 10))

        error_textbox = ctk.CTkTextbox(main_frame, width=500, height=200)
        error_textbox.pack(fill="both", expand=True)
        error_textbox.insert("1.0", error_message)
        error_textbox.configure(state="disabled")

        ctk.CTkLabel(main_frame, text="상세 오류 내용이 클립보드에 복사되었습니다.", font=ctk.CTkFont(size=11), text_color="gray").pack(pady=(10, 5))

        close_button = ctk.CTkButton(main_frame, text="확인", command=self.destroy)
        close_button.pack(pady=(10, 0))

class AddMaterialDialog(ctk.CTkToplevel):
    """처방에 원료를 추가하기 위한 팝업창"""
    def __init__(self, master, on_add_callback, on_line_break_callback):
        import re
        super().__init__(master)
        self.on_add_callback = on_add_callback
        self.on_line_break_callback = on_line_break_callback

        self.title("원료 추가")
        self.geometry("600x500")
        self.transient(master)
        self.grab_set()

        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(1, weight=1)
        self.treeviews = {} # 탭별 Treeview 위젯을 저장할 딕셔너리

        # --- 검색 프레임 ---
        search_frame = ctk.CTkFrame(self, fg_color="transparent")
        search_frame.grid(row=0, column=0, padx=10, pady=10, sticky="ew")
        search_frame.grid_columnconfigure(1, weight=1)
        
        ctk.CTkLabel(search_frame, text="원료 검색:").grid(row=0, column=0, padx=5)
        self.search_entry = ctk.CTkEntry(search_frame)
        self.search_entry.grid(row=0, column=1, padx=5, sticky="ew")
        self.search_entry.bind("<Return>", self.search_materials)
        self.search_entry.bind("<KeyRelease>", self.search_materials) # 실시간 검색을 위한 바인딩
        ctk.CTkButton(search_frame, text="검색", width=60, command=lambda: self.search_materials()).grid(row=0, column=2, padx=5)
        ctk.CTkButton(search_frame, text="초기화", width=60, command=self.reset_search).grid(row=0, column=3, padx=5)

        # --- 원료 목록 탭 뷰 ---
        self.tab_view = ctk.CTkTabview(self, border_width=1)
        self.tab_view.grid(row=1, column=0, padx=10, pady=5, sticky="nsew")

        # --- 전성분 상세 정보 프레임 ---
        details_frame = ctk.CTkFrame(self, fg_color="transparent")
        details_frame.grid(row=2, column=0, padx=10, pady=5, sticky="ew")
        details_frame.grid_columnconfigure(1, weight=1)

        ctk.CTkLabel(details_frame, text="전성분:").grid(row=0, column=0, padx=5, sticky="nw")
        self.ingredient_details_textbox = ctk.CTkTextbox(details_frame, height=60, state="disabled", wrap="word")
        self.ingredient_details_textbox.grid(row=0, column=1, padx=5, sticky="ew")


        # --- 버튼 프레임 ---
        button_frame = ctk.CTkFrame(self, fg_color="transparent")
        button_frame.grid(row=3, column=0, pady=10)
        ctk.CTkButton(button_frame, text="원료 추가", command=self.on_add).pack(side="left", padx=5)
        ctk.CTkButton(button_frame, text="줄 내림", command=self.on_line_break_callback).pack(side="left", padx=5)
        ctk.CTkButton(button_frame, text="닫기", fg_color="gray50", hover_color="gray35", command=self.destroy).pack(side="left", padx=10)

        self.search_materials() # 초기 전체 목록 로드

    def reset_search(self):
        """검색창을 비우고 전체 목록을 다시 불러옵니다."""
        self.search_entry.delete(0, "end")
        self.search_materials()

    def _get_numeric_part(self, code_str: str):
        """문자열에서 숫자 부분을 추출하여 정수로 반환합니다."""
        import re
        if not isinstance(code_str, str):
            return None
        match = re.search(r'\d+', code_str)
        return int(match.group(0)) if match else None

    def search_materials(self, event=None):
        """DB에서 원료를 검색하여 1000단위 탭으로 나누어 표시합니다."""
        search_term = self.search_entry.get().strip()
        
        # 검색 전 현재 활성화된 탭 이름 저장
        active_tab_name = self.tab_view.get()

        # 기존 탭과 트리뷰를 모두 초기화합니다.
        for tab_name in list(self.treeviews.keys()):
            self.tab_view.delete(tab_name)
        self.treeviews.clear()

        materials = db_manager.search_materials(search_term)
        
        # 원료를 코드 1000단위로 그룹화
        grouped_materials = {}
        other_materials = [] # 숫자 코드가 없는 원료를 위한 리스트
        for mat in materials:
            num_part = self._get_numeric_part(mat.code)
            if num_part is not None:
                group_key = (num_part // 1000) * 1000
                if group_key not in grouped_materials:
                    grouped_materials[group_key] = []
                grouped_materials[group_key].append(mat)
            else:
                other_materials.append(mat)

        created_tabs = []
        # 그룹화된 원료를 기반으로 탭과 Treeview를 순서대로 생성합니다.
        for group_key in sorted(grouped_materials.keys()):
            created_tabs.append(str(group_key))
            tab_name = str(group_key)
            tab = self.tab_view.add(tab_name)
            tab.grid_columnconfigure(0, weight=1)
            tab.grid_rowconfigure(0, weight=1)

            tree = ttk.Treeview(tab, columns=("id", "code", "name", "ingredients"), show="headings", selectmode="browse")
            tree.heading("id", text="ID"); tree.column("id", width=50, anchor="center")
            tree.heading("code", text="코드"); tree.column("code", width=120)
            tree.heading("name", text="원료명"); tree.column("name", width=150)
            tree.heading("ingredients", text="전성분"); tree.column("ingredients", width=200, stretch=True)
            tree.grid(row=0, column=0, sticky="nsew")

            scrollbar = ttk.Scrollbar(tab, orient="vertical", command=tree.yview)
            tree.configure(yscrollcommand=scrollbar.set)
            scrollbar.grid(row=0, column=1, sticky="ns")

            tree.bind("<<TreeviewSelect>>", self.on_material_select)
            tree.bind("<Double-1>", self.on_double_click_add)
            self.treeviews[tab_name] = tree

            for mat in grouped_materials[group_key]:
                # 전성분 목록을 문자열로 만듭니다 (최대 3개).
                ing_names = [ing.name_en for ing in mat.ingredients[:3]]
                ing_str = ", ".join(ing_names)
                if len(mat.ingredients) > 3:
                    ing_str += "..."
                tree.insert("", "end", values=(mat.id, mat.code, mat.name, ing_str))

        # 숫자 코드가 없는 원료가 있으면 'NEW' 탭을 마지막에 추가합니다.
        if other_materials:
            created_tabs.append("NEW")
            tab_name = "NEW"
            tab = self.tab_view.add(tab_name)
            tab.grid_columnconfigure(0, weight=1)
            tab.grid_rowconfigure(0, weight=1)

            tree = ttk.Treeview(tab, columns=("id", "code", "name", "ingredients"), show="headings", selectmode="browse")
            tree.heading("id", text="ID"); tree.column("id", width=50, anchor="center")
            tree.heading("code", text="코드"); tree.column("code", width=120)
            tree.heading("name", text="원료명"); tree.column("name", width=150)
            tree.heading("ingredients", text="전성분"); tree.column("ingredients", width=200, stretch=True)
            tree.grid(row=0, column=0, sticky="nsew")

            scrollbar = ttk.Scrollbar(tab, orient="vertical", command=tree.yview)
            tree.configure(yscrollcommand=scrollbar.set)
            scrollbar.grid(row=0, column=1, sticky="ns")

            tree.bind("<<TreeviewSelect>>", self.on_material_select)
            tree.bind("<Double-1>", self.on_double_click_add)
            self.treeviews[tab_name] = tree

            for mat in other_materials:
                # 전성분 목록을 문자열로 만듭니다 (최대 3개).
                ing_names = [ing.name_en for ing in mat.ingredients[:3]]
                ing_str = ", ".join(ing_names)
                if len(mat.ingredients) > 3:
                    ing_str += "..."
                tree.insert("", "end", values=(mat.id, mat.code, mat.name, ing_str))
        
        # 검색 후 탭을 다시 선택하여 UI 갱신을 강제합니다.
        if not created_tabs: # 검색 결과가 없는 경우
            self.on_material_select() # 전성분 창 클리어
            return

        if active_tab_name not in created_tabs:
            active_tab_name = created_tabs[0]
        
        # UI 갱신을 확실하게 하기 위한 수정된 로직
        self.update_idletasks()
        # 짧은 지연 후 탭을 다시 설정하여 화면 그리기를 강제합니다.
        # 이때, 해당 탭이 존재하는지 확인하여 오류를 방지합니다.
        def safe_set_tab():
            if active_tab_name in self.tab_view._name_list:
                self.tab_view.set(active_tab_name)
        self.after(10, safe_set_tab)

    def on_material_select(self, event=None):
        """트리뷰에서 원료 선택 시 전성분 목록을 표시합니다."""
        active_tab_name = self.tab_view.get()
        if not active_tab_name: return
        active_treeview = self.treeviews.get(active_tab_name)
        if not active_treeview: return

        selected_item = active_treeview.selection()
        # 텍스트박스 초기화
        self.ingredient_details_textbox.configure(state="normal")
        self.ingredient_details_textbox.delete("1.0", "end")

        if not selected_item:
            self.ingredient_details_textbox.configure(state="disabled")
            return

        material_id = active_treeview.item(selected_item[0], "values")[0]

        session = db_manager.get_session()
        try:
            from database.models import Ingredient
            # 전성분 목록 가져오기
            ingredients = session.query(Ingredient).filter_by(material_id=material_id).order_by(Ingredient.id).all()
            
            if ingredients:
                # 영문명과 한글명을 함께 표시
                ingredient_texts = [f"{ing.name_en} ({ing.name_ko})" for ing in ingredients]
                details_text = ", ".join(ingredient_texts)
            else:
                details_text = "등록된 전성분이 없습니다."
            self.ingredient_details_textbox.insert("1.0", details_text)
        finally:
            session.close()
            self.ingredient_details_textbox.configure(state="disabled")

    def on_double_click_add(self, event):
        """Treeview에서 항목을 더블클릭하여 바로 추가합니다."""
        # 더블클릭된 위젯(Treeview)을 식별합니다.
        tree = event.widget
        
        # 더블클릭된 행을 식별합니다.
        item_id = tree.identify_row(event.y)
        if not item_id:
            return

        # 해당 행을 선택하고 포커스를 줍니다.
        tree.selection_set(item_id)
        tree.focus(item_id)
        self.on_add() # 기존 추가 로직을 호출합니다.

    def on_add(self):
        """'추가' 버튼 클릭 시 콜백 함수를 호출합니다."""
        active_tab_name = self.tab_view.get()
        active_treeview = self.treeviews.get(active_tab_name)
        if not active_treeview: return

        selected_item = active_treeview.selection()
        if not selected_item:
            messagebox.showwarning("선택 오류", "목록에서 추가할 원료를 선택하세요.", parent=self)
            return
        
        material_id = active_treeview.item(selected_item[0], "values")[0]
        self.on_add_callback(material_id)
        
        # 추가 후 입력 필드 초기화
        active_treeview.selection_remove(selected_item)

def try_convert_to_float(value):
    """값을 float으로 변환 시도, 실패 시 원래 값 반환"""
    if value is None:
        return None
    try:
        return float(value)
    except (ValueError, TypeError):
        return value

class DocumentManagementFrame(ctk.CTkFrame):
    def __init__(self, master, user, app):
        super().__init__(master)
        self.current_user = user
        self.app = app
        self.client_map = {} # 처방 목록 필터용
        self._selected_formulation_id = None
        self.current_view = "folders"  # 현재 뷰 상태 ('folders' 또는 'files')
        self.quotation_edit_entry = None # 견적 탭의 인라인 수정을 위한 Entry 위젯
        self.current_folder_name = None # 현재 보고 있는 폴더(실험품명)
        
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(0, weight=1)

        # --- 상단 프레임 (탭 뷰 + 도움말 버튼) ---
        top_frame = ctk.CTkFrame(self, fg_color="transparent")
        top_frame.grid(row=0, column=0, sticky="nsew")
        top_frame.grid_columnconfigure(0, weight=1)
        top_frame.grid_rowconfigure(0, weight=1)

        # '처방 관리'와 '문서'를 담을 최상위 탭 뷰를 다시 생성합니다.
        self.tab_view = ctk.CTkTabview(
            self, command=self.on_tab_change, border_width=1,
            border_color=("gray80", "gray30"),
            segmented_button_selected_color=("#3B8ED0", "#1F6AA5"),
            segmented_button_unselected_color=("gray92", "gray20"),
            text_color=("black", "white"),
            segmented_button_selected_hover_color=("#3671A8", "#144870"),
            segmented_button_unselected_hover_color=("gray85", "gray28")
        )
        self.tab_view.grid(row=0, column=0, sticky="nsew", padx=10, pady=10)

        # 도움말 버튼
        self.help_button = ctk.CTkButton(top_frame, text="도움말", width=80, command=self.show_help)
        self.help_button.place(relx=0.98, y=10, anchor="ne")

        # '처방 관리'와 '문서' 탭을 추가합니다.
        self.tab_view.add("처방 관리")
        self.tab_view.add("문서")

        # '처방 관리' 탭 설정
        self.setup_formulation_tab(self.tab_view.tab("처방 관리"))
        # '문서' 탭에 서브 탭들 설정
        self.setup_document_sub_tabs(self.tab_view.tab("문서"))
        
        self.load_formulations()

    def setup_document_sub_tabs(self, tab_frame):
        """'문서' 탭 내부에 서브 탭들을 설정합니다."""
        tab_frame.grid_columnconfigure(0, weight=1)
        tab_frame.grid_rowconfigure(0, weight=1)

        doc_sub_tab_view = ctk.CTkTabview(tab_frame, border_width=1, border_color=("gray80", "gray30"))
        doc_sub_tab_view.grid(row=0, column=0, padx=10, pady=10, sticky="nsew")

        # 요청된 하위 탭들 추가
        doc_sub_tab_view.add("물성치/SPEC")
        doc_sub_tab_view.add("안정도")
        doc_sub_tab_view.add("기능성 보고/참고 자료")

        # 각 탭에 플레이스홀더 UI 설정
        for tab_name in ["물성치/SPEC", "안정도", "기능성 보고/참고 자료"]:
            self.setup_placeholder_tab(doc_sub_tab_view.tab(tab_name), tab_name)

    def show_help(self):
        """서류 관리 도움말을 표시합니다."""
        title = "처방 관리 도움말"
        message = """
        [처방 관리 사용법]
        
        [처방 목록 탭]
        1. 폴더/파일 보기: 각 '실험품명'이 하나의 폴더입니다. 폴더를 클릭하면 해당 실험품명의 모든 차수(버전) 목록을 볼 수 있습니다.
        2. 처방 생성/수정: '신규' 버튼으로 새 처방을, 목록에서 처방 선택 후 '수정' 버튼(또는 더블클릭)으로 기존 처방을 수정합니다.
        3. 샘플 관리: 처방 선택 후 '샘플발송' 버튼으로 발송 횟수를 1 증가시킬 수 있습니다. '발송수정' 버튼으로 횟수를 직접 수정할 수 있습니다.
        4. 거래처 필터: 특정 거래처와 관련된 처방 폴더만 필터링하여 볼 수 있습니다.
        
        [견적 탭]
        1. 견적 생성: '처방 목록' 탭에서 처방을 선택한 후, '견적' 탭으로 와서 '견적 생성' 버튼을 누르면 해당 처방의 원료 목록이 불러와집니다.
        2. 원가 계산: 기준 중량(g)을 입력하면 총 원료 원가와 VAT, 이윤이 포함된 가격이 자동으로 계산됩니다.
        3. 원료 추가/삭제/수정: '원료 추가', '선택 삭제', '함량 수정' 버튼으로 견적 내용을 자유롭게 편집할 수 있습니다.
        4. 내보내기: '견적서 내보내기' 버튼으로 현재 견적 내용을 엑셀 파일로 저장합니다.
        
        [전성분 탭]
        1. 목록 생성: '처방 목록' 탭에서 처방을 선택한 후, '전성분' 탭으로 와서 '전체 목록 생성' 버튼을 누르면 모든 전성분 목록이 한 번에 생성됩니다.
        2. 목록 종류:
           - 복합 전성분 (서류용): 원료별 상세 목록과 전성분 합계 목록을 제공합니다.
           - 단일 전성분 (함량순): 화장품 패키지 기재용으로, 모든 전성분을 최종 함량 순으로 정렬하여 표시합니다.
           - 디자인용 전성분: 패키지 디자인에 바로 사용할 수 있도록 국문/영문 전성분 목록을 텍스트로 제공합니다.
        3. 내보내기: '엑셀로 내보내기' 버튼으로 생성된 모든 전성분 목록을 하나의 엑셀 파일에 각각 다른 시트로 저장합니다.
        
        [처방 생성/수정 창]
        - 가져오기/내보내기: '가져오기'로 엑셀 파일의 처방을 불러오거나, '내보내기'로 현재 처방을 엑셀 파일로 저장할 수 있습니다.
        - LAB NO. 자동생성: '담당번호', '실험년월일', '차수'를 모두 입력하면 'LAB NO.'가 자동으로 생성됩니다.
        - 새 버전으로 저장: 기존 처방을 수정할 때 'LAB NO.'가 변경되면 자동으로 새로운 버전의 처방으로 저장됩니다.
        """
        HelpPopup(self, title, message)

    def on_tab_change(self):
        selected_tab = self.tab_view.get()
        # 현재 선택된 탭의 활동을 기록합니다.
        self.app.record_action(f"document/{selected_tab}")

    def switch_to_tab(self, tab_name):
        if tab_name in self.tab_view._name_list: # pylint: disable=protected-access
            self.tab_view.set(tab_name)

    def refresh_formulation_filters(self):
        print("처방 필터 새로고침...")
        all_client_types = ["- 유형 선택 -"] + db_manager.get_unique_client_types()
        self.list_filter_client_type_combo.configure(values=all_client_types)
        self.list_filter_client_type_combo.set("- 유형 선택 -")
        self.update_list_filter_client_name_combo("- 유형 선택 -")

    def setup_formulation_tab(self, tab_frame):
        """처방 관리 탭의 UI를 설정합니다."""
        tab_frame.grid_columnconfigure(0, weight=1)
        tab_frame.grid_rowconfigure(0, weight=1)

        self.formulation_sub_tab_view = ctk.CTkTabview(
            tab_frame, border_width=1, border_color=("gray80", "gray30"), # 부모를 tab_frame으로 설정
            segmented_button_selected_color=("#3B8ED0", "#1F6AA5"),
            segmented_button_unselected_color=("gray92", "gray20"),
            text_color=("black", "white"),
            segmented_button_selected_hover_color=("#3671A8", "#144870"),
            segmented_button_unselected_hover_color=("gray85", "gray28")
        )
        self.formulation_sub_tab_view.grid(row=0, column=0, padx=10, pady=10, sticky="nsew")

        self.formulation_sub_tab_view.add("처방 목록")
        self.formulation_sub_tab_view.add("견적")
        self.formulation_sub_tab_view.add("전성분")
        self.formulation_sub_tab_view.add("생산 처방")

        self.setup_formulation_list_tab(self.formulation_sub_tab_view.tab("처방 목록"))
        self.setup_quotation_tab(self.formulation_sub_tab_view.tab("견적"))
        self.setup_ingredient_list_tab(self.formulation_sub_tab_view.tab("전성분"))
        self.setup_placeholder_tab(self.formulation_sub_tab_view.tab("생산 처방"), "생산 처방")

    def setup_formulation_list_tab(self, parent_tab):
        """'처방 목록' 서브 탭의 UI를 설정합니다. (폴더 카드 UI)"""
        parent_tab.grid_columnconfigure(0, weight=1)
        parent_tab.grid_rowconfigure(1, weight=1)

        # --- 헤더 및 필터 ---
        header_frame = ctk.CTkFrame(parent_tab, fg_color="transparent")
        header_frame.grid(row=0, column=0, sticky="ew", padx=10, pady=(10, 5))
        header_frame.grid_columnconfigure(1, weight=1)

        self.list_header_label = ctk.CTkLabel(header_frame, text="처방 폴더", font=ctk.CTkFont(size=16, weight="bold"))
        self.list_header_label.grid(row=0, column=0, sticky="w")

        filter_frame = ctk.CTkFrame(header_frame, fg_color="transparent")
        filter_frame.grid(row=0, column=1, sticky="e")

        # 아이콘 크기 조절 슬라이더 추가
        ctk.CTkLabel(filter_frame, text="아이콘 크기:").pack(side="left", padx=(10, 5))
        self.icon_size_slider = ctk.CTkSlider(filter_frame, from_=20, to=80, number_of_steps=6, command=self.on_icon_size_change)
        self.icon_size_slider.set(40) # 기본값
        self.icon_size_slider.pack(side="left", padx=(0, 20))

        ctk.CTkLabel(filter_frame, text="거래처 필터:").pack(side="left", padx=(0, 5))
        self.list_filter_client_type_combo = CustomDropdown(filter_frame, values=["- 유형 선택 -"], width=120, command=self.update_list_filter_client_name_combo)
        self.list_filter_client_type_combo.pack(side="left", padx=(0, 5))
        self.list_filter_client_name_combo = CustomDropdown(filter_frame, values=["- 업체 선택 -"], width=250, command=self.filter_formulations_by_client)
        self.list_filter_client_name_combo.pack(side="left", padx=(0, 10))
        self.list_filter_reset_button = ctk.CTkButton(filter_frame, text="초기화", width=80, command=lambda: self.load_formulations())
        self.list_filter_reset_button.pack(side="left")

        # --- 컨텐츠 영역 (폴더/파일 목록) ---
        self.content_frame = ctk.CTkFrame(parent_tab, fg_color="transparent")
        self.content_frame.grid(row=1, column=0, sticky="nsew", padx=10, pady=5)
        self.content_frame.grid_columnconfigure(0, weight=1)
        self.content_frame.grid_rowconfigure(0, weight=1)

        # 폴더 뷰 (카드 형식)
        self.folder_view = ctk.CTkScrollableFrame(self.content_frame, label_text="")
        self.folder_view.grid_columnconfigure((0, 1, 2, 3, 4), weight=1) # 5열 그리드

        # 파일 뷰 (Treeview)
        self.file_view = ctk.CTkFrame(self.content_frame, fg_color="transparent")
        self.file_view.grid_columnconfigure(0, weight=1)
        self.file_view.grid_rowconfigure(1, weight=1)

        file_view_header = ctk.CTkFrame(self.file_view, fg_color="transparent")
        file_view_header.grid(row=0, column=0, sticky="ew", pady=(0, 5))
        self.back_button = ctk.CTkButton(file_view_header, text="◀ 뒤로 가기", width=100, command=self.show_folder_view)
        self.back_button.pack(side="left", padx=(0, 10))

        self.compare_button = ctk.CTkButton(file_view_header, text="이력 비교", width=100, command=self.open_comparison_popup)
        self.compare_button.pack(side="left", padx=(0, 10))

        self.folder_history_button = ctk.CTkButton(file_view_header, text="전체 이력 보기", width=120, command=self.open_folder_history_popup)
        self.folder_history_button.pack(side="left", padx=(0, 10))

        # 선택 초기화 버튼 추가
        self.reset_selection_button = ctk.CTkButton(file_view_header, text="선택 초기화", width=100, command=self.reset_selection_and_tabs)
        self.reset_selection_button.pack(side="left", padx=(0, 10))

        self.edit_sample_button = ctk.CTkButton(file_view_header, text="발송수정", width=100, command=self.edit_sample_sent_count)
        self.edit_sample_button.pack(side="right", padx=(5, 0))

        self.send_sample_button = ctk.CTkButton(file_view_header, text="샘플발송", width=100, command=self.increment_sample_sent_count)
        self.send_sample_button.pack(side="right")

        formulation_cols = ("id", "revision", "manager_code", "date", "lab_no", "sample_sent")
        self.formulation_tree = ttk.Treeview(self.file_view, columns=formulation_cols, show="headings", selectmode="extended")
        self.formulation_tree.heading("id", text="ID"); self.formulation_tree.column("id", width=40, anchor="center")
        self.formulation_tree.heading("revision", text="차수"); self.formulation_tree.column("revision", width=100, stretch=True)
        self.formulation_tree.heading("manager_code", text="담당번호"); self.formulation_tree.column("manager_code", width=100)
        self.formulation_tree.heading("date", text="실험일"); self.formulation_tree.column("date", width=100, anchor="center")
        self.formulation_tree.heading("lab_no", text="LAB NO."); self.formulation_tree.column("lab_no", width=150)
        self.formulation_tree.heading("sample_sent", text="샘플발송"); self.formulation_tree.column("sample_sent", width=80, anchor="center")
        self.formulation_tree.grid(row=1, column=0, sticky="nsew")
        self.formulation_tree.bind("<<TreeviewSelect>>", self.on_formulation_tree_select)
        self.formulation_tree.bind("<Double-1>", lambda e: self.open_formulation_popup(edit_mode=True))

        # --- 하단 버튼 ---
        bottom_button_frame = ctk.CTkFrame(parent_tab, fg_color="transparent")
        bottom_button_frame.grid(row=2, column=0, padx=10, pady=(5, 10), sticky="e")

        self.new_button = ctk.CTkButton(bottom_button_frame, text="신규", width=100, command=lambda: self.open_formulation_popup(edit_mode=False))
        self.new_button.pack(side="left", padx=5)
        self.edit_button = ctk.CTkButton(bottom_button_frame, text="수정", width=100, command=lambda: self.open_formulation_popup(edit_mode=True))
        self.edit_button.pack(side="left", padx=5)
        self.delete_button = ctk.CTkButton(bottom_button_frame, text="삭제", width=100, fg_color="#D32F2F", hover_color="#B71C1C", command=self.delete_formulation)
        self.delete_button.pack(side="left", padx=(5, 20)) # 오른쪽에 여백 추가

        if not self.current_user.is_admin:
            self.delete_button.configure(state="disabled")
        
        self.show_folder_view() # 초기 화면은 폴더 뷰

    def setup_quotation_tab(self, tab_frame):
        """견적 탭의 UI를 설정합니다."""
        tab_frame.grid_columnconfigure(0, weight=1)
        tab_frame.grid_rowconfigure(1, weight=1)

        # --- 컨트롤 프레임 ---
        control_frame = ctk.CTkFrame(tab_frame, fg_color="transparent")
        control_frame.grid(row=0, column=0, padx=10, pady=10, sticky="ew")

        # --- 좌측 버튼들 ---
        left_button_frame = ctk.CTkFrame(control_frame, fg_color="transparent")
        left_button_frame.pack(side="left")
        ctk.CTkButton(left_button_frame, text="견적 생성", command=self.load_formulation_for_quotation).pack(side="left")
        ctk.CTkButton(left_button_frame, text="견적서 내보내기", command=self.export_quotation).pack(side="left", padx=(10, 0))
        ctk.CTkButton(left_button_frame, text="선택 삭제", fg_color="#D32F2F", hover_color="#B71C1C", command=self.delete_selected_quotation_item).pack(side="left", padx=(10, 0))

        # --- 우측 버튼 및 입력창 ---
        right_control_frame = ctk.CTkFrame(control_frame, fg_color="transparent")
        right_control_frame.pack(side="right")
        
        ctk.CTkLabel(right_control_frame, text="기준 중량(g):").pack(side="left", padx=(20, 5))
        self.quotation_weight_entry = ctk.CTkEntry(right_control_frame, width=100, justify="right")
        self.quotation_weight_entry.insert(0, "1000") # 기본값 1kg
        self.quotation_weight_entry.bind("<KeyRelease>", lambda e: self.recalculate_quotation())
        self.quotation_weight_entry.pack(side="left")
        ctk.CTkButton(right_control_frame, text="원료 추가", command=self.open_add_material_for_quotation).pack(side="left", padx=(10, 5))
        ctk.CTkButton(right_control_frame, text="함량 수정", command=self.edit_selected_quotation_item).pack(side="left", padx=5)

        # --- 견적 내용 Treeview ---
        quotation_cols = ("phase", "code", "name", "ratio", "unit_price", "cost")
        self.quotation_tree = ttk.Treeview(tab_frame, columns=quotation_cols, show="headings", selectmode="browse")
        self.quotation_tree.heading("phase", text="구분"); self.quotation_tree.column("phase", width=80, anchor="center")
        self.quotation_tree.heading("code", text="코드"); self.quotation_tree.column("code", width=100, anchor="w")
        self.quotation_tree.heading("name", text="원료명"); self.quotation_tree.column("name", width=250, stretch=True)
        self.quotation_tree.heading("ratio", text="함량(%)"); self.quotation_tree.column("ratio", width=100, anchor="e")
        self.quotation_tree.heading("unit_price", text="단가(원/kg)"); self.quotation_tree.column("unit_price", width=120, anchor="e")
        self.quotation_tree.heading("cost", text="원가(원)"); self.quotation_tree.column("cost", width=120, anchor="e")
        self.quotation_tree.grid(row=1, column=0, padx=10, pady=5, sticky="nsew")
        self.quotation_tree.bind("<Double-1>", self.on_quotation_tree_double_click)

        # --- 최종 견적 계산 프레임 (수정) ---
        calculation_frame = ctk.CTkFrame(tab_frame, fg_color="transparent")
        calculation_frame.grid(row=2, column=0, padx=10, pady=10, sticky="e")
        calculation_frame.grid_columnconfigure(1, weight=1)

        # 총 함량
        ctk.CTkLabel(calculation_frame, text="총 함량:", font=ctk.CTkFont(size=14, weight="bold")).grid(row=0, column=0, padx=10, pady=5, sticky="w")
        self.quotation_total_ratio_label = ctk.CTkLabel(calculation_frame, text="0.0000 %", font=ctk.CTkFont(size=14), anchor="e")
        self.quotation_total_ratio_label.grid(row=0, column=1, padx=10, pady=5, sticky="ew")

        # 총 원료 원가
        ctk.CTkLabel(calculation_frame, text="총 원료 원가:", font=ctk.CTkFont(size=14, weight="bold")).grid(row=1, column=0, padx=10, pady=5, sticky="w")
        self.total_raw_cost_label = ctk.CTkLabel(calculation_frame, text="0 원", font=ctk.CTkFont(size=14), anchor="e")
        self.total_raw_cost_label.grid(row=1, column=1, padx=10, pady=5, sticky="ew")

        # VAT 10% 포함가
        ctk.CTkLabel(calculation_frame, text="VAT(10%) 포함가:", font=ctk.CTkFont(size=14, weight="bold")).grid(row=2, column=0, padx=10, pady=5, sticky="w")
        self.price_with_vat_label = ctk.CTkLabel(calculation_frame, text="0 원", font=ctk.CTkFont(size=14), anchor="e")
        self.price_with_vat_label.grid(row=2, column=1, padx=10, pady=5, sticky="ew")

        # 이윤 15% 포함가
        ctk.CTkLabel(calculation_frame, text="이윤(15%) 포함가:", font=ctk.CTkFont(size=14, weight="bold")).grid(row=3, column=0, padx=10, pady=5, sticky="w")
        self.price_with_profit_label = ctk.CTkLabel(calculation_frame, text="0 원", font=ctk.CTkFont(size=14), anchor="e")
        self.price_with_profit_label.grid(row=3, column=1, padx=10, pady=5, sticky="ew")

    def load_formulation_for_quotation(self):
        """'처방 목록'에서 선택된 처방을 '견적' 탭의 Treeview로 불러옵니다."""
        if not self._selected_formulation_id:
            messagebox.showwarning("선택 오류", "먼저 '처방 목록' 탭에서 처방을 선택해주세요.", parent=self)
            return

        for item in self.quotation_tree.get_children():
            self.quotation_tree.delete(item)

        session = db_manager.get_session()
        try:
            formulation = session.query(Formulation).filter_by(id=self._selected_formulation_id).first()
            if not formulation: return

            for item in formulation.items:
                if not item.material_code or item.material_code == "---": continue
                
                material = session.query(Material).filter_by(code=item.material_code).first()
                unit_price = material.unit_price if material else 0.0

                self.quotation_tree.insert("", "end", values=(
                    item.phase or "", item.material_code, item.material_name, f"{item.ratio:.4f}", f"{unit_price or 0:,.0f}", "0.00"
                ))
            
            self.recalculate_quotation()

        except Exception as e:
            messagebox.showerror("견적 생성 오류", f"견적을 생성하는 중 오류가 발생했습니다: {e}", parent=self)
        finally:
            session.close()

    def recalculate_quotation(self):
        """현재 Treeview의 내용을 바탕으로 원가와 최종 가격을 다시 계산합니다."""
        try:
            total_weight = float(self.quotation_weight_entry.get())
        except (ValueError, TypeError):
            # 기준 중량이 숫자가 아니면 계산 중지
            return

        if not self.quotation_tree.get_children():
            self.quotation_total_ratio_label.configure(text="0.0000 %")
            self.total_raw_cost_label.configure(text="0 원")
            self.price_with_vat_label.configure(text="0 원")
            self.price_with_profit_label.configure(text="0 원")
            return

        total_raw_cost = 0.0
        total_ratio = 0.0
        for item_id in self.quotation_tree.get_children():
            values = self.quotation_tree.item(item_id, "values")
            try:
                ratio = float(values[3])
                total_ratio += ratio
                unit_price = float(values[4].replace(",", ""))
                cost = (ratio / 100.0) * (total_weight / 1000.0) * unit_price # 1g당 원가 계산
                total_raw_cost += cost
                # Treeview의 원가 컬럼 업데이트
                self.quotation_tree.item(item_id, values=(values[0], values[1], values[2], values[3], f"{unit_price:,.0f}", f"{cost:,.2f}"))
            except (ValueError, TypeError, IndexError):
                continue

        # 최종 가격 계산 및 표시
        self.quotation_total_ratio_label.configure(text=f"{total_ratio:.4f} %")
        self.total_raw_cost_label.configure(text=f"{total_raw_cost:,.2f} 원") # 기준 중량에 대한 총 원가
        self.price_with_vat_label.configure(text=f"{total_raw_cost * 1.1:,.2f} 원") # VAT 포함가
        self.price_with_profit_label.configure(text=f"{total_raw_cost * 1.15:,.2f} 원") # 이윤 포함가

    def open_add_material_for_quotation(self):
        """견적용 원료 추가 다이얼로그를 엽니다."""
        # AddMaterialDialog는 하나의 콜백만 받으므로, 람다로 감싸서 필요한 인자 전달
        AddMaterialDialog(self, lambda mat_id: self.add_material_to_quotation(mat_id), lambda: None)

    def add_material_to_quotation(self, material_id):
        """선택된 원료를 견적 Treeview에 추가합니다."""
        session = db_manager.get_session()
        try:
            material = session.query(Material).filter_by(id=material_id).first()
            if material:
                self.quotation_tree.insert("", "end", values=(
                    "", material.code, material.name, "0.0000", f"{material.unit_price or 0:,.0f}", "0.00"
                ))
                self.recalculate_quotation()
        finally:
            session.close()

    def on_quotation_tree_double_click(self, event):
        """견적 트리뷰에서 더블클릭 시 인라인 편집을 시작합니다."""
        region = self.quotation_tree.identify("region", event.x, event.y)
        if region != "cell":
            return
        
        column = self.quotation_tree.identify_column(event.x)
        if column == "#4": # 함량(%) 컬럼
            selected_item = self.quotation_tree.focus()
            if selected_item:
                self.start_quotation_ratio_editing(selected_item)

    def edit_selected_quotation_item(self):
        """'함량 수정' 버튼 클릭 시 선택된 항목의 인라인 편집을 시작합니다."""
        selected_item = self.quotation_tree.selection()
        if not selected_item:
            messagebox.showwarning("선택 오류", "함량을 수정할 항목을 목록에서 선택하세요.", parent=self)
            return
        self.start_quotation_ratio_editing(selected_item[0])

    def start_quotation_ratio_editing(self, item_id):
        """지정된 항목의 함량(%) 셀에 인라인 수정용 Entry를 생성합니다."""
        if self.quotation_edit_entry:
            self.quotation_edit_entry.destroy()

        # Treeview의 보이는 영역 내에서 셀의 상대적인 위치와 크기를 가져옵니다.
        x, y, width, height = self.quotation_tree.bbox(item_id, "#4")
        current_value = self.quotation_tree.item(item_id, "values")[3]

        # Entry 위젯의 부모를 Treeview가 아닌, Treeview를 포함하는 탭 프레임으로 설정합니다.
        # 이렇게 하면 Entry가 다른 위젯(예: 하단 요약 프레임)에 가려지지 않고 항상 위에 표시됩니다.
        parent_frame = self.quotation_tree.master
        self.quotation_edit_entry = ctk.CTkEntry(parent_frame, width=width, height=height, justify='right', border_width=0)

        # Treeview의 부모 프레임 내에서 Entry가 위치할 절대 좌표를 계산합니다.
        # 1. Treeview 위젯 자체의 y 위치를 가져옵니다.
        tree_y_position = self.quotation_tree.winfo_y()
        # 2. bbox에서 반환된 y값(보이는 영역 기준)을 더하여 최종 y 좌표를 계산합니다.
        final_y = tree_y_position + y

        self.quotation_edit_entry.place(x=x, y=final_y)
        self.quotation_edit_entry.insert(0, current_value)
        self.quotation_edit_entry.select_range(0, 'end')
        self.quotation_edit_entry.focus_set()

        self.quotation_edit_entry.bind("<Return>", lambda e, i=item_id: self.on_quotation_edit_commit(i))
        self.quotation_edit_entry.bind("<FocusOut>", lambda e, i=item_id: self.on_quotation_edit_commit(i))

    def on_quotation_edit_commit(self, item_id):
        """인라인 수정 완료 시 값을 업데이트하고 Entry를 제거합니다."""
        if not self.quotation_edit_entry: return
        
        try:
            new_ratio = float(self.quotation_edit_entry.get())
            current_values = list(self.quotation_tree.item(item_id, "values"))
            current_values[3] = f"{new_ratio:.4f}"
            self.quotation_tree.item(item_id, values=tuple(current_values))
        except (ValueError, TypeError):
            pass # 잘못된 값이면 변경하지 않음
        finally:
            self.quotation_edit_entry.destroy()
            self.quotation_edit_entry = None
            self.recalculate_quotation()

    def delete_selected_quotation_item(self):
        """선택된 항목을 견적 Treeview에서 삭제합니다."""
        selected_item = self.quotation_tree.selection()
        if not selected_item:
            messagebox.showwarning("선택 오류", "삭제할 항목을 목록에서 선택하세요.", parent=self)
            return
        
        self.quotation_tree.delete(selected_item)
        self.recalculate_quotation()

    def generate_quotation(self):
        """선택된 처방을 기반으로 견적을 생성합니다."""
        if not self._selected_formulation_id:
            messagebox.showwarning("선택 오류", "먼저 '처방 목록' 탭에서 처방을 선택해주세요.", parent=self)
            return
        self.load_formulation_for_quotation()

    def export_quotation(self):
        """현재 견적 내용을 엑셀 파일로 내보냅니다."""
        if not self.quotation_tree.get_children():
            messagebox.showwarning("내보내기 오류", "내보낼 견적 내용이 없습니다. '견적 생성'을 먼저 실행해주세요.", parent=self)
            return

        # 처방 정보는 선택된 ID를 기반으로 가져옴
        formulation_name = "가상 견적"
        lab_no = ""
        manager_name = self.current_user.username

        if self._selected_formulation_id:
            session = db_manager.get_session()
            try:
                formulation = session.query(Formulation).filter_by(id=self._selected_formulation_id).first()
                if formulation:
                    formulation_name = formulation.experiment_name
                    lab_no = formulation.lab_no
                    manager_name = formulation.manager_name
            finally:
                session.close()

        quotation_data = {
            "details": {
                "실험품명": formulation_name,
                "담당자": manager_name,
                "LAB NO.": lab_no,
                "기준 중량": self.quotation_weight_entry.get() + "g",
            },
            "items": [self.quotation_tree.item(item, "values") for item in self.quotation_tree.get_children()],
            "summary": {
                "총 함량": self.quotation_total_ratio_label.cget("text"),
                "총 원료 원가": self.total_raw_cost_label.cget("text"),
                "VAT(10%) 포함가": self.price_with_vat_label.cget("text"),
                "이윤(15%) 포함가": self.price_with_profit_label.cget("text"),
            }
        }
        
        default_filename = f"{formulation_name}_견적서.xlsx"
        excel_handler.export_quotation_to_excel(quotation_data, default_filename)

    def show_folder_view(self):
        """폴더 뷰를 표시하고 파일 뷰를 숨깁니다."""
        self.file_view.grid_forget()
        self.folder_view.grid(row=0, column=0, sticky="nsew")
        self.list_header_label.configure(text="처방 폴더")
        self.current_view = "folders"
        self.current_folder_name = None
        self._selected_formulation_id = None
        self.update_button_states()
        self.load_formulations()

    def export_quotation(self):
        """현재 견적 내용을 엑셀 파일로 내보냅니다."""
        if not self._selected_formulation_id:
            messagebox.showwarning("선택 오류", "먼저 '처방 목록' 탭에서 처방을 선택하고 '견적 생성'을 실행해주세요.", parent=self)
            return

        session = db_manager.get_session()
        try:
            formulation = session.query(Formulation).filter_by(id=self._selected_formulation_id).first()
            if not formulation: return

            quotation_data = {
                "details": {
                    "실험품명": formulation.experiment_name,
                    "담당자": formulation.manager_name,
                    "LAB NO.": formulation.lab_no,
                    "기준 중량": self.quotation_weight_entry.get() + "g",
                },
                "items": [self.quotation_tree.item(item, "values") for item in self.quotation_tree.get_children()],
                "summary": {
                    "총 원료 원가": self.total_raw_cost_label.cget("text"),
                    "VAT(10%) 포함가": self.price_with_vat_label.cget("text"),
                    "이윤(15%) 포함가": self.price_with_profit_label.cget("text"),
                }
            }
            
            default_filename = f"{formulation.experiment_name}_견적서.xlsx"
            excel_handler.export_quotation_to_excel(quotation_data, default_filename)

        finally:
            session.close()

    def show_folder_view(self, client_id_to_load=None):
        """폴더 뷰를 표시하고 파일 뷰를 숨깁니다."""
        self.file_view.grid_forget()
        self.folder_view.grid(row=0, column=0, sticky="nsew")
        self.list_header_label.configure(text="처방 폴더")
        self.current_view = "folders"
        self.current_folder_name = None
        self._selected_formulation_id = None
        self.update_button_states()
        # 폴더 뷰로 전환될 때, 저장된 아이콘 크기를 불러와서 표시합니다.
        self.load_folders(client_id=client_id_to_load, is_initial_load=True)

    def reset_selection_and_tabs(self):
        """
        현재 선택된 처방을 해제하고, 견적 및 전성분 탭의 내용을 모두 초기화합니다.
        """
        # 1. Treeview 선택 해제
        if self.formulation_tree.selection():
            self.formulation_tree.selection_remove(self.formulation_tree.selection()[0])
        
        # 2. 선택된 ID 초기화 및 버튼 상태 업데이트
        self._selected_formulation_id = None
        self.update_button_states()

        # 3. 견적 및 전성분 탭 초기화
        self.quotation_tree.delete(*self.quotation_tree.get_children())
        self.recalculate_quotation()
        self.generate_all_ingredient_lists()

    def show_file_view(self, folder_name):
        """파일 뷰를 표시하고 폴더 뷰를 숨깁니다."""
        self.folder_view.grid_forget()
        self.file_view.grid(row=0, column=0, sticky="nsew")
        self.list_header_label.configure(text=f"폴더: {folder_name}")
        self.current_view = "files"
        self.current_folder_name = folder_name
        self._selected_formulation_id = None
        self.update_button_states()
        self.load_formulations()

    def update_button_states(self):
        """현재 뷰 상태에 따라 버튼 활성화/비활성화를 조절합니다."""
        if self.current_view == "folders":
            self.edit_button.configure(state="disabled")
            self.compare_button.configure(state="disabled")
            self.folder_history_button.configure(state="disabled")
            self.edit_sample_button.configure(state="disabled")
            self.send_sample_button.configure(state="disabled")
            self.reset_selection_button.configure(state="disabled")
            if self.current_user.is_admin:
                self.delete_button.configure(state="disabled")
        else: # files view
            selection_count = len(self.formulation_tree.selection())
            
            # 폴더에 들어오면 항상 활성화
            self.folder_history_button.configure(state="normal")
            
            # 1개 선택 시: 수정, 샘플 관련 버튼 활성화
            is_single_selected = selection_count == 1
            self.edit_button.configure(state="normal" if is_single_selected else "disabled")
            self.send_sample_button.configure(state="normal" if is_single_selected else "disabled")
            self.edit_sample_button.configure(state="normal" if is_single_selected else "disabled")
            
            # 2개 선택 시: 비교 버튼 활성화
            self.compare_button.configure(state="normal" if selection_count == 2 else "disabled")
            
            # 1개 이상 선택 시: 삭제, 선택 초기화 버튼 활성화
            if self.current_user.is_admin:
                self.delete_button.configure(state="normal" if selection_count > 0 else "disabled")
            self.reset_selection_button.configure(state="normal" if selection_count > 0 else "disabled")

    def create_folder_card(self, master, folder_name, count):
        """슬라이더 값에 따라 크기가 조절되는 폴더 카드 위젯을 생성합니다."""
        card = ctk.CTkFrame(master, corner_radius=10, cursor="hand2")
        card.grid_columnconfigure(0, weight=1)

        # 슬라이더 값에 따라 폰트 크기 동적 계산
        icon_size = int(self.icon_size_slider.get())
        title_size = int(icon_size / 2.8) # 아이콘 크기에 비례하여 조절
        count_size = int(icon_size / 3.6) # 아이콘 크기에 비례하여 조절
        wraplength = int(icon_size * 3.75)

        icon_label = ctk.CTkLabel(card, text="📁", font=ctk.CTkFont(size=icon_size))
        icon_label.pack(pady=(15, 5))

        title_label = ctk.CTkLabel(card, text=folder_name, font=ctk.CTkFont(size=title_size, weight="bold"), wraplength=wraplength)
        title_label.pack(pady=5, padx=10)

        count_label = ctk.CTkLabel(card, text=f"({count}개 처방)", font=ctk.CTkFont(size=count_size), text_color="gray")
        count_label.pack(pady=(0, 15))

        for widget in [card, icon_label, title_label, count_label]:
            widget.bind("<Button-1>", lambda e, name=folder_name: self.show_file_view(name))
        
        return card

    def on_icon_size_change(self, value):
        """아이콘 크기 슬라이더 값 변경 시 폴더 뷰를 다시 로드합니다."""
        # 현재 폴더 뷰일 때만, 설정 파일 로드 없이 현재 슬라이더 값으로 다시 로드합니다.
        if self.current_view == "folders":
            self.load_folders(is_initial_load=False)

    def open_formulation_popup(self, edit_mode: bool):
        """처방 생성/수정 팝업을 엽니다."""
        formulation_id = None
        selected_items = self.formulation_tree.selection()

        if edit_mode:
            if not selected_items:
                messagebox.showwarning("알림", "수정할 처방을 목록에서 선택하세요.", parent=self)
                return
            if len(selected_items) > 1:
                messagebox.showwarning("알림", "하나의 처방만 선택하여 수정할 수 있습니다.", parent=self)
                return
            
            item_values = self.formulation_tree.item(selected_items[0], "values")
            if item_values and str(item_values[0]).isdigit():
                formulation_id = int(item_values[0])
        
        
        popup = FormulationEditPopup( # 분리된 클래스 사용
            master=self,
            user=self.current_user,
            app=self.app,
            on_save_callback=self.load_formulations, # 저장 후 목록 새로고침
            formulation_id=formulation_id
        )
        # 신규 작성 시, 현재 폴더 이름을 기본 실험품명으로 설정
        if not edit_mode and self.current_folder_name:
            popup.exp_name_entry.insert(0, self.current_folder_name)

    def open_comparison_popup(self):
        """선택된 두 처방을 비교하는 팝업을 엽니다."""
        selected_ids = self.get_selected_formulation_ids()
        if len(selected_ids) != 2:
            messagebox.showwarning("선택 오류", "비교할 두 개의 처방을 선택해주세요.", parent=self)
            return
        
        formulation_id1, formulation_id2 = selected_ids
        FormulationComparisonPopup(self, formulation_id1, formulation_id2)

    def open_folder_history_popup(self):
        """현재 폴더(실험품명)의 전체 변경 이력을 보여주는 팝업을 엽니다."""
        if not self.current_folder_name:
            messagebox.showwarning("오류", "폴더를 먼저 선택해주세요.", parent=self)
            return
        
        FolderHistoryPopup(self, folder_name=self.current_folder_name)

    def filter_formulations_by_client(self, selected_client_name: str):
        """선택된 거래처에 따라 처방 목록을 필터링합니다. (폴더 뷰에서만 동작)"""
        if selected_client_name == "- 업체 선택 -":
            # 필터 초기화 시, 폴더 뷰로 전환하며 초기 로드
            self.show_folder_view()
        else:
            client_id = self.client_map.get(selected_client_name)
            # 파일 뷰에 있었다면 폴더 뷰로 전환하고 필터링된 결과를 로드
            if self.current_view != "folders":
                self.show_folder_view(client_id_to_load=client_id)
            else: # 이미 폴더 뷰라면 필터링된 결과만 다시 로드
                self.load_folders(client_id=client_id, is_initial_load=True)

    def update_list_filter_client_name_combo(self, selected_type: str):
        """선택된 유형에 따라 처방 목록 필터의 거래처 콤보박스를 업데이트합니다."""
        if selected_type == "- 유형 선택 -":
            self.list_filter_client_name_combo.set("- 업체 선택 -")
            self.list_filter_client_name_combo.configure(values=["- 업체 선택 -"])
            return

        session = db_manager.get_session()
        try:
            clients = session.query(Client).filter_by(is_active=True, client_type=selected_type).order_by(Client.name).all()
            self.client_map.update({client.name: client.id for client in clients})
            client_names = [client.name for client in clients]
            
            values = ["- 업체 선택 -"] + client_names if client_names else ["- 해당 업체 없음 -"]
            self.list_filter_client_name_combo.configure(values=values)
            self.list_filter_client_name_combo.set("- 업체 선택 -")
        except Exception as e:
            messagebox.showerror("오류", f"거래처 목록 갱신 중 오류: {e}", parent=self)
        finally:
            session.close()

    def setup_complex_ingredient_tab(self, tab_frame):
        """'복합 전성분 (서류용)' 탭의 UI를 설정합니다."""
        tab_frame.grid_columnconfigure(0, weight=1)
        tab_frame.grid_rowconfigure(0, weight=1)

        # --- 서브 탭 뷰 생성 ---
        sub_tab_view = ctk.CTkTabview(
            tab_frame, border_width=1, border_color=("gray80", "gray30"),
            command=self.on_complex_ingredient_sub_tab_change # 복합 전성분 내 서브탭 변경 감지
        )
        self.complex_ingredient_sub_tab_view = sub_tab_view # 서브 탭뷰를 인스턴스 변수로 저장
        self.complex_ingredient_sub_tab_view.grid(row=0, column=0, padx=10, pady=(0, 10), sticky="nsew")

        raw_material_tab = sub_tab_view.add("원료별 목록")
        summed_list_tab = sub_tab_view.add("전성분 합계")

        # --- 원료별 목록 탭 UI ---
        raw_material_tab.grid_columnconfigure(0, weight=1)
        raw_material_tab.grid_rowconfigure(0, weight=1) # Treeview가 차지할 공간
        raw_material_tab.grid_rowconfigure(1, weight=0) # 합계 라벨이 차지할 공간
        
        # 열 정의는 여기에 유지합니다.
        self.complex_ing_cols = {
            "no": {"text": "NO", "width": 40, "anchor": "center", "visible": True},
            "material_name": {"text": "원료명", "width": 200, "visible": True},
            "inci_name": {"text": "INCI Name", "width": 200, "visible": True},
            "name_ko": {"text": "성분의 한글명", "width": 200, "visible": True},
            "rm_ratio": {"text": "RM 함량(%)", "width": 120, "anchor": "e", "visible": True},
            "ing_ratio": {"text": "성분 함량(%)", "width": 120, "anchor": "e", "visible": True},
            "actual_wt": {"text": "Actual Wt (%)", "width": 120, "anchor": "e", "visible": True},
            "cas_no": {"text": "CAS No.", "width": 120, "visible": True},
            "function": {"text": "Ingredient function", "width": 150, "visible": True},
            "hs_code": {"text": "HS CODE", "width": 100, "visible": False}, # HS CODE 열 추가
            "nmpa_reg_num": {"text": "NMPA", "width": 120, "visible": False}, # NMPA 열 추가
            "remark": {"text": "Remark", "width": 100, "visible": True},
        }

        self.raw_material_ingredient_tree = ttk.Treeview(raw_material_tab, show="headings")
        self._setup_treeview_columns(self.raw_material_ingredient_tree, self.complex_ing_cols)
        self.raw_material_ingredient_tree.grid(row=0, column=0, sticky="nsew", padx=10, pady=(0, 5))
        self.raw_material_ingredient_tree.tag_configure('material_row', font=('Malgun Gothic', 11, 'bold'))

        # 원료별 목록 합계 프레임
        raw_material_summary_frame = ctk.CTkFrame(raw_material_tab, fg_color="transparent")
        raw_material_summary_frame.grid(row=1, column=0, sticky="e", padx=10, pady=5)
        ctk.CTkLabel(raw_material_summary_frame, text="RM or ingredient % in fla 합계:", font=ctk.CTkFont(weight="bold")).pack(side="left", padx=(0, 5))
        self.raw_material_rm_ratio_total_label = ctk.CTkLabel(raw_material_summary_frame, text="0.0000", font=ctk.CTkFont(weight="bold"))
        self.raw_material_rm_ratio_total_label.pack(side="left", padx=(0, 20))
        ctk.CTkLabel(raw_material_summary_frame, text="Actual Wt (%) 합계:", font=ctk.CTkFont(weight="bold")).pack(side="left", padx=(0, 5))
        self.raw_material_actual_wt_total_label = ctk.CTkLabel(raw_material_summary_frame, text="0.000000", font=ctk.CTkFont(weight="bold"))
        self.raw_material_actual_wt_total_label.pack(side="left")

        # --- 전성분 합계 탭 UI ---
        summed_list_tab.grid_columnconfigure(0, weight=1)
        summed_list_tab.grid_rowconfigure(0, weight=1) # Treeview
        summed_list_tab.grid_rowconfigure(1, weight=0) # 합계 라벨

        summed_cols = ("name_ko", "name_en", "cas_no", "function", "total_ratio")
        self.summed_ingredient_tree = ttk.Treeview(summed_list_tab, columns=summed_cols, show="headings")
        self.summed_ingredient_tree.heading("name_ko", text="국문명"); self.summed_ingredient_tree.column("name_ko", width=200)
        self.summed_ingredient_tree.heading("name_en", text="영문명"); self.summed_ingredient_tree.column("name_en", width=200)
        self.summed_ingredient_tree.heading("cas_no", text="CAS No."); self.summed_ingredient_tree.column("cas_no", width=120)
        self.summed_ingredient_tree.heading("function", text="기능"); self.summed_ingredient_tree.column("function", width=150)
        self.summed_ingredient_tree.heading("total_ratio", text="총 함량(%)"); self.summed_ingredient_tree.column("total_ratio", width=100, anchor="e")
        self.summed_ingredient_tree.grid(row=0, column=0, sticky="nsew")

        # 전성분 합계 요약 프레임
        summed_summary_frame = ctk.CTkFrame(summed_list_tab, fg_color="transparent")
        summed_summary_frame.grid(row=1, column=0, sticky="e", padx=10, pady=5)
        ctk.CTkLabel(summed_summary_frame, text="총 함량(%) 합계:", font=ctk.CTkFont(weight="bold")).pack(side="left", padx=(0, 5))
        self.summed_total_ratio_label = ctk.CTkLabel(summed_summary_frame, text="0.000000", font=ctk.CTkFont(weight="bold"))
        self.summed_total_ratio_label.pack(side="left")

    def generate_raw_material_ingredient_list(self):
        """선택된 처방을 기반으로 원료별 전성분 목록을 생성합니다."""
        if not self._selected_formulation_id:
            messagebox.showwarning("선택 오류", "먼저 '처방 목록' 탭에서 처방을 선택해주세요.", parent=self)
            return
        
        # Treeview 초기화
        for item in self.raw_material_ingredient_tree.get_children():
            self.raw_material_ingredient_tree.delete(item)

        session = db_manager.get_session()
        try:
            # 처방에 포함된 원료 아이템들을 가져옵니다.
            formulation_items = session.query(FormulationItem).filter_by(formulation_id=self._selected_formulation_id).order_by(desc(FormulationItem.ratio)).all()
            total_rm_ratio = 0.0
            total_actual_wt = 0.0
            material_no = 1
            for item in formulation_items:
                # 구분선(---)은 건너뜁니다.
                if not item.material_code or item.material_code == "---": continue

                # 원료 정보와 전성분 정보를 함께 가져옵니다.
                material = session.query(Material).filter_by(code=item.material_code).first()
                if not material or not material.ingredients:
                    # 전성분이 없는 원료 처리
                    actual_wt = item.ratio
                    total_rm_ratio += item.ratio
                    total_actual_wt += actual_wt
                    group_tag = 'group_odd' if (material_no -1) % 2 != 0 else 'group_even'
                    self.raw_material_ingredient_tree.insert("", "end", values=(
                        material_no, material.name if material else item.material_name, "", item.material_name,
                        f"{item.ratio:.4f}", "100.0000", f"{actual_wt:.6f}", "", "", "", "", "" # hs_code, nmpa_reg_num 자리에 빈 문자열 추가
                    ), tags=('material_row', group_tag))
                    material_no += 1
                    continue

                # 전성분이 있는 원료 처리
                group_tag = 'group_odd' if (material_no - 1) % 2 != 0 else 'group_even' # noqa
                for i, ing in enumerate(sorted(material.ingredients, key=lambda x: x.id)):
                    actual_wt = item.ratio * (ing.composition_ratio / 100.0)
                    total_actual_wt += actual_wt
                    if i == 0: # 첫 번째 전성분 행
                        total_rm_ratio += item.ratio
                        self.raw_material_ingredient_tree.insert("", "end", values=(
                            material_no, material.name, ing.name_en or "", ing.name_ko, f"{item.ratio:.4f}", f"{ing.composition_ratio:.4f}", f"{actual_wt:.6f}", ing.cas_no, ing.function, "",
                            ing.hs_code or "", ing.nmpa_reg_num or "", ing.remark or ""
                        ), tags=('material_row', group_tag))
                    else: # 두 번째 이후 전성분 행
                        self.raw_material_ingredient_tree.insert("", "end", values=(
                            "", "", ing.name_en or "", ing.name_ko, "", f"{ing.composition_ratio:.4f}", f"{actual_wt:.6f}", ing.cas_no, ing.function, "",
                            ing.hs_code or "", ing.nmpa_reg_num or "", ing.remark or ""
                        ), tags=(group_tag,))
                material_no += 1
            
            # 합계 업데이트
            self.raw_material_rm_ratio_total_label.configure(text=f"{total_rm_ratio:.4f}")
            self.raw_material_actual_wt_total_label.configure(text=f"{total_actual_wt:.6f}")
        finally:
            session.close()

    def generate_summed_ingredient_list(self):
        """선택된 처방의 모든 전성분 함량을 합산하여 목록을 생성합니다."""
        if not self._selected_formulation_id:
            messagebox.showwarning("선택 오류", "먼저 '처방 목록' 탭에서 처방을 선택해주세요.", parent=self)
            return

        # Treeview 초기화
        for item in self.summed_ingredient_tree.get_children():
            self.summed_ingredient_tree.delete(item)

        total_summed_ratio = 0.0 # { (name_ko, name_en): {data} }
        summed_ingredients = {} 
        session = db_manager.get_session()
        try:
            formulation_items = session.query(FormulationItem).filter_by(formulation_id=self._selected_formulation_id).all()

            for item in formulation_items:
                if not item.material_code or item.material_code == "---" or item.ratio is None: continue

                # 원료 정보와 전성분 정보를 함께 가져옵니다.
                material = session.query(Material).filter_by(code=item.material_code).first()
                if material:
                    if material.ingredients: # 전성분이 있는 원료
                        for ing in material.ingredients:
                            # 원료 내 전성분의 실제 함량 계산 (원료 함량 * (전성분 함량 / 100))
                            actual_ratio = item.ratio * (ing.composition_ratio / 100.0)
                            
                            key = (ing.name_ko or "", ing.name_en or "")
                            if key not in summed_ingredients:
                                summed_ingredients[key] = {
                                    'total_ratio': 0, 'cas_no': ing.cas_no or "", 'function': ing.function or ""
                                }
                            summed_ingredients[key]['total_ratio'] += actual_ratio

            # 함량이 높은 순으로 정렬
            sorted_ingredients = sorted(summed_ingredients.items(), key=lambda x: x[1]['total_ratio'], reverse=True)

            for (name_ko, name_en), data in sorted_ingredients:
                total_ratio = data['total_ratio']
                cas_no = data['cas_no']
                function = data['function']
                total_summed_ratio += data['total_ratio']
                self.summed_ingredient_tree.insert("", "end", values=(
                    name_ko, name_en, cas_no, function, f"{total_ratio:.6f}"
                ))
            
            # 합계 업데이트
            self.summed_total_ratio_label.configure(text=f"{total_summed_ratio:.6f}")
        finally:
            session.close()

    def _create_column_selection_menu(self, parent, treeview, columns_config, button_widget):
        """열 선택 체크박스 메뉴를 생성합니다."""
        column_menu = tk.Menu(button_widget, tearoff=0)
        
        # 각 열에 대한 체크박스 변수와 메뉴 아이템 생성
        for col_id, config in columns_config.items():
            var = tk.BooleanVar(value=config.get("visible", True))
            column_menu.add_checkbutton(
                label=config["text"],
                variable=var,
                command=lambda tv=treeview, cfg=columns_config: self._update_visible_columns(tv, cfg)
            )
            config["variable"] = var # BooleanVar를 config에 저장

        # 버튼 클릭 시 메뉴가 나타나도록 command 설정
        button_widget.configure(command=lambda: column_menu.tk_popup(
            button_widget.winfo_rootx(), 
            button_widget.winfo_rooty() + button_widget.winfo_height()
        ))

    def _update_visible_columns(self, treeview, columns_config):
        """체크박스 상태에 따라 Treeview의 열을 업데이트합니다."""
        visible_columns = [col_id for col_id, config in columns_config.items() if config["variable"].get()]
        treeview.configure(displaycolumns=visible_columns)

    def _setup_treeview_columns(self, treeview, columns_config):
        """Treeview의 컬럼과 헤더를 설정하고 초기 가시성을 적용합니다."""
        treeview.configure(columns=list(columns_config.keys()))
        for col_id, config in columns_config.items():
            treeview.heading(col_id, text=config["text"])
            treeview.column(col_id, width=config["width"], anchor=config.get("anchor", "w"))
        
        visible_columns = [col_id for col_id, config in columns_config.items() if config.get("visible", True)]
        treeview.configure(displaycolumns=visible_columns)

    def copy_complex_ingredients_to_clipboard(self):
        """복합 전성분 텍스트박스의 내용을 클립보드에 복사합니다."""
        # TODO: 현재 활성화된 Treeview의 내용을 복사하도록 수정 필요
        messagebox.showinfo("알림", "클립보드 복사 기능은 개발 예정입니다.", parent=self)

    def setup_single_ingredient_tab(self, tab_frame):
        """'단일 전성분 (함량순)' 탭의 UI를 설정합니다."""
        tab_frame.grid_columnconfigure(0, weight=1); tab_frame.grid_rowconfigure(1, weight=1)

        # --- 컨트롤 프레임 ---
        # 컨트롤 프레임이 더 이상 필요 없으므로 삭제합니다.

        # --- 열 선택 메뉴 ---
        self.single_ing_cols = {
            "no": {"text": "NO", "width": 40, "anchor": "center", "visible": True},
            "name_en": {"text": "INGREDIENT", "width": 250, "visible": True},
            "ci_no": {"text": "C.I NO", "width": 80, "visible": False},
            "total_ratio": {"text": "% (W/W)", "width": 100, "anchor": "e", "visible": True},
            "cas_no": {"text": "CAS. NO", "width": 120, "visible": True},
            "function": {"text": "FUNCTION", "width": 150, "visible": True},
            "hs_code": {"text": "HS CODE", "width": 100, "visible": False},
            "nmpa_reg_num": {"text": "NMPA", "width": 120, "visible": False},
            "remark": {"text": "비고", "width": 150, "visible": False},
        }

        # --- 결과 표시 Treeview ---
        self.single_ingredient_tree = ttk.Treeview(tab_frame, show="headings")
        self._setup_treeview_columns(self.single_ingredient_tree, self.single_ing_cols)
        self.single_ingredient_tree.grid(row=0, column=0, padx=10, pady=10, sticky="nsew") # Treeview를 맨 위로 이동

        # 단일 전성분 합계 프레임
        single_summary_frame = ctk.CTkFrame(tab_frame, fg_color="transparent")
        single_summary_frame.grid(row=2, column=0, sticky="e", padx=10, pady=5)
        ctk.CTkLabel(single_summary_frame, text="총 함량(% (W/W)) 합계:", font=ctk.CTkFont(weight="bold")).pack(side="left", padx=(0, 5))
        self.single_total_ratio_label = ctk.CTkLabel(single_summary_frame, text="0.000000", font=ctk.CTkFont(weight="bold"))
        self.single_total_ratio_label.pack(side="left")

    def generate_single_ingredient_list(self):
        """선택된 처방의 모든 전성분을 합산하고 함량순으로 정렬하여 목록을 생성합니다."""
        if not self._selected_formulation_id:
            messagebox.showwarning("선택 오류", "먼저 '처방 목록' 탭에서 처방을 선택해주세요.", parent=self)
            return

        # Treeview 초기화
        for item in self.single_ingredient_tree.get_children():
            self.single_ingredient_tree.delete(item)

        total_summed_ratio = 0.0
        summed_ingredients = {} # { (name_ko, name_en): {data} }
        session = db_manager.get_session()
        try:
            formulation_items = session.query(FormulationItem).filter_by(formulation_id=self._selected_formulation_id).all()
            for item in formulation_items:
                if not item.material_code or item.material_code == "---" or item.ratio is None: continue
                material = session.query(Material).filter_by(code=item.material_code).first()
                if material and material.ingredients: # 전성분이 있는 원료
                    for ing in material.ingredients:
                        actual_ratio = item.ratio * (ing.composition_ratio / 100.0)
                        key = (ing.name_ko or "", ing.name_en or "")
                        if key not in summed_ingredients:
                            summed_ingredients[key] = {
                                'total_ratio': 0, 'cas_no': ing.cas_no or "", 'function': ing.function or "",
                                'hs_code': ing.hs_code or "", 'nmpa_reg_num': ing.nmpa_reg_num or "", 'remark': ing.remark or ""
                            }
                        summed_ingredients[key]['total_ratio'] += actual_ratio

            # 함량이 높은 순으로 정렬
            sorted_ingredients = sorted(summed_ingredients.items(), key=lambda x: x[1]['total_ratio'], reverse=True)

            for i, ((name_ko, name_en), data) in enumerate(sorted_ingredients, 1):
                total_summed_ratio += data['total_ratio']
                # TODO: C.I. No. 파싱 로직 추가 필요

                self.single_ingredient_tree.insert("", "end", values=(
                    i, name_en, "", f"{data['total_ratio']:.6f}",
                    data['cas_no'], data['function'], data['hs_code'], 
                    data['nmpa_reg_num'], data['remark']
                ))

            # 합계 업데이트
            self.single_total_ratio_label.configure(text=f"{total_summed_ratio:.6f}")
        finally:
            session.close()

    def confirm_reset_all_formulations(self):
        """모든 처방 데이터를 리셋하기 전에 사용자에게 확인을 받습니다."""
        if not messagebox.askyesno(
            "처방 참조 초기화 확인", 
            "모든 처방의 원료 참조를 초기화하시겠습니까?\n\n"
            "이 작업은 처방전 자체를 삭제하지 않지만,\n"
            "각 처방에 연결된 모든 원료 정보를 '참조 없음' 상태로 변경합니다.\n"
            "이 작업은 되돌릴 수 없습니다.", 
            parent=self
        ):
            return

        session = db_manager.get_session()
        try:
            # 모든 FormulationItem의 원료 참조를 해제합니다.
            num_items_updated = session.query(FormulationItem).update({
                FormulationItem.material_id: None,
                FormulationItem.material_code: "---",
                FormulationItem.material_name: "참조가 초기화되었습니다."
            })
            
            session.commit()
            
            messagebox.showinfo(
                "초기화 완료",
                f"모든 처방의 원료 참조가 초기화되었습니다.\n(총 {num_items_updated}개 항목)",
                parent=self
            )
            
            # 화면 새로고침
            self.load_formulations()
            
            # 다른 탭들도 새로고침 (예: 견적, 전성분)
            self.quotation_tree.delete(*self.quotation_tree.get_children())
            self.recalculate_quotation()
            self.generate_all_ingredient_lists()

        except Exception as e:
            session.rollback()
            messagebox.showerror("데이터베이스 오류", f"처방 참조 초기화 중 오류 발생: {e}", parent=self)
        finally:
            session.close()

    def setup_design_ingredient_tab(self, tab_frame):
        """'디자인용 전성분' 탭의 UI를 설정합니다."""
        tab_frame.grid_columnconfigure(0, weight=1)
        tab_frame.grid_rowconfigure(1, weight=1) # 국문 텍스트박스
        tab_frame.grid_rowconfigure(3, weight=1) # 영문 텍스트박스

        # --- 컨트롤 프레임 ---
        control_frame = ctk.CTkFrame(tab_frame, fg_color="transparent", height=40)
        control_frame.grid(row=0, column=0, padx=10, pady=10, sticky="ew")

        # --- 국문 결과 표시 ---
        ko_frame = ctk.CTkFrame(tab_frame, fg_color="transparent")
        ko_frame.grid(row=1, column=0, padx=10, pady=(0, 5), sticky="nsew")
        ko_frame.grid_columnconfigure(0, weight=1)
        ctk.CTkLabel(ko_frame, text="국문 전성분", font=ctk.CTkFont(weight="bold")).pack(anchor="w", pady=(0,2))
        self.design_ko_textbox = ctk.CTkTextbox(ko_frame, wrap="word", font=ctk.CTkFont(family="Malgun Gothic", size=14))
        self.design_ko_textbox.pack(fill="both", expand=True)

        # --- 영문 결과 표시 ---
        en_frame = ctk.CTkFrame(tab_frame, fg_color="transparent")
        en_frame.grid(row=3, column=0, padx=10, pady=(5, 10), sticky="nsew")
        en_frame.grid_columnconfigure(0, weight=1)
        ctk.CTkLabel(en_frame, text="영문 전성분 (INCI)", font=ctk.CTkFont(weight="bold")).pack(anchor="w", pady=(0,2))
        self.design_en_textbox = ctk.CTkTextbox(en_frame, wrap="word", font=ctk.CTkFont(family="Malgun Gothic", size=14))
        self.design_en_textbox.pack(fill="both", expand=True)

    def generate_design_ingredient_list(self):
        """선택된 처방을 기반으로 디자인용 전성분 목록(문자열)을 생성합니다."""
        if not self._selected_formulation_id:
            messagebox.showwarning("선택 오류", "먼저 '처방 목록' 탭에서 처방을 선택해주세요.", parent=self)
            return

        # '전성분 합계' 로직을 재사용하여 데이터를 가져옵니다.
        summed_ingredients = {} # { (name_ko, name_en): total_ratio }
        session = db_manager.get_session()
        try:
            formulation_items = session.query(FormulationItem).filter_by(formulation_id=self._selected_formulation_id).all()
            for item in formulation_items:
                if not item.material_code or item.material_code == "---" or item.ratio is None: continue
                material = session.query(Material).filter_by(code=item.material_code).first()
                if material and material.ingredients:
                    for ing in material.ingredients:
                        actual_ratio = item.ratio * (ing.composition_ratio / 100.0)
                        # 디자인용은 이름만 중요하므로 이름으로 그룹화
                        key = (ing.name_ko or "", ing.name_en or "")
                        summed_ingredients[key] = summed_ingredients.get(key, 0) + actual_ratio

            # 함량이 높은 순으로 정렬
            sorted_ingredients = sorted(summed_ingredients.items(), key=lambda x: x[1], reverse=True)

            # 1% 초과 성분과 1% 이하 성분 분리
            above_1_percent = [item for item in sorted_ingredients if item[1] > 1.0]
            at_or_below_1_percent = [item for item in sorted_ingredients if item[1] <= 1.0]

            # 국문 리스트와 영문 리스트를 각각 생성
            final_ko_list = [item[0][0] for item in above_1_percent] + [item[0][0] for item in at_or_below_1_percent]
            final_en_list = [item[0][1] for item in above_1_percent] + [item[0][1] for item in at_or_below_1_percent]
            
            ko_string = ", ".join(final_ko_list)
            en_string = ", ".join(final_en_list)

            self.design_ko_textbox.configure(state="normal")
            self.design_ko_textbox.delete("1.0", "end")
            self.design_ko_textbox.insert("1.0", ko_string)

            self.design_en_textbox.configure(state="normal")
            self.design_en_textbox.delete("1.0", "end")
            self.design_en_textbox.insert("1.0", en_string)
        finally:
            session.close()

    def copy_design_ingredients_to_clipboard(self):
        """디자인용 전성분 텍스트박스의 내용을 클립보드에 복사합니다."""
        # TODO: 국문/영문 중 어떤 것을 복사할지 선택하는 기능 추가 필요
        messagebox.showinfo("알림", "클립보드 복사 기능은 개발 예정입니다.", parent=self)

    def setup_ingredient_list_tab(self, tab_frame):
        """'전성분' 탭의 UI를 설정합니다."""
        tab_frame.grid_columnconfigure(0, weight=1)
        tab_frame.grid_rowconfigure(1, weight=1)
        
        # --- 상단 컨트롤 프레임 ---
        top_control_frame = ctk.CTkFrame(tab_frame, fg_color="transparent")
        top_control_frame.grid(row=0, column=0, padx=10, pady=10, sticky="ew")

        ctk.CTkButton(top_control_frame, text="전체 목록 생성", command=self.generate_all_ingredient_lists).pack(side="left")
        ctk.CTkButton(top_control_frame, text="엑셀로 내보내기", command=self.export_all_ingredient_lists).pack(side="left", padx=(10, 0))

        # --- 열 선택 메뉴 버튼 (컨트롤 프레임에 추가) ---
        # 이 버튼은 나중에 생성될 Treeview를 참조해야 하므로, UI 구성 후 마지막에 command를 설정합니다.
        self.column_selection_button = ctk.CTkButton(top_control_frame, text="표시할 열 선택", width=120)
        self.column_selection_button.pack(side="right", padx=(10, 0))

        # 전성분 탭 내부에 또 다른 탭 뷰를 생성합니다.
        self.ingredient_tab_view = ctk.CTkTabview(
            tab_frame, border_width=1, border_color=("gray85", "gray28"),
            command=self.on_ingredient_tab_change # 탭 변경 시 호출될 함수 연결
        )
        self.ingredient_tab_view.grid(row=1, column=0, padx=10, pady=(0, 10), sticky="nsew")
        
        # 1. 복합 전성분 탭
        complex_tab = self.ingredient_tab_view.add("복합 전성분 (서류용)")
        complex_tab.grid_columnconfigure(0, weight=1); complex_tab.grid_rowconfigure(0, weight=1)
        self.setup_complex_ingredient_tab(complex_tab)

        # 2. 단일 전성분 탭
        single_tab = self.ingredient_tab_view.add("단일 전성분 (함량순)")
        single_tab.grid_columnconfigure(0, weight=1); single_tab.grid_rowconfigure(1, weight=1)
        self.setup_single_ingredient_tab(single_tab)

        # 3. 디자인용 전성분 탭
        design_tab = self.ingredient_tab_view.add("디자인용 전성분")
        self.setup_design_ingredient_tab(design_tab)

        # --- 열 선택 메뉴 최종 설정 ---
        # Treeview가 모두 생성된 후, 메뉴와 버튼의 command를 연결합니다.
        self._create_column_selection_menu(top_control_frame, 
                                           self.raw_material_ingredient_tree, 
                                           self.complex_ing_cols, 
                                           self.column_selection_button)

        # 초기 탭 상태에 따라 버튼 가시성 설정
        self.on_ingredient_tab_change()

    def on_ingredient_tab_change(self):
        """전성분 서브 탭 변경 시 '표시할 열 선택' 버튼의 가시성을 조절합니다."""
        selected_main_tab = self.ingredient_tab_view.get()
        if selected_main_tab == "복합 전성분 (서류용)":
            # 복합 전성분 탭이 선택된 경우, 서브탭 상태에 따라 버튼 가시성 결정
            self.on_complex_ingredient_sub_tab_change()
        else:
            # 다른 메인 탭이 선택된 경우, 버튼 숨김
            self.column_selection_button.pack_forget()

    def on_complex_ingredient_sub_tab_change(self):
        """'복합 전성분' 내의 서브 탭 변경 시 버튼 가시성을 조절합니다."""
        selected_sub_tab = self.complex_ingredient_sub_tab_view.get()
        if selected_sub_tab == "원료별 목록":
            self.column_selection_button.pack(side="right", padx=(10, 0))
        else:
            self.column_selection_button.pack_forget()

    def generate_all_ingredient_lists(self):
        """모든 종류의 전성분 목록을 한 번에 생성합니다."""
        # 처방이 선택되었을 때만 목록 생성
        if self._selected_formulation_id:
            self.generate_raw_material_ingredient_list()
            self.generate_summed_ingredient_list()
            self.generate_single_ingredient_list()
            self.generate_design_ingredient_list()
        else:
            # 처방 선택이 해제되면 모든 목록을 비웁니다.
            for tree in [self.raw_material_ingredient_tree, self.summed_ingredient_tree, self.single_ingredient_tree]:
                tree.delete(*tree.get_children())
            self.raw_material_rm_ratio_total_label.configure(text="0.0000")
            self.raw_material_actual_wt_total_label.configure(text="0.000000")
            self.summed_total_ratio_label.configure(text="0.000000")
            self.single_total_ratio_label.configure(text="0.000000")
            self.design_ko_textbox.delete("1.0", "end")
            self.design_en_textbox.delete("1.0", "end")

    def export_all_ingredient_lists(self):
        """생성된 모든 전성분 목록을 하나의 엑셀 파일에 여러 시트로 내보냅니다."""
        if not self._selected_formulation_id:
            messagebox.showwarning("선택 오류", "먼저 처방을 선택하고 '전체 목록 생성'을 실행해주세요.", parent=self)
            return

        sheets_data = {}

        # 1. 원료별 목록 데이터 추출
        def extract_tree_data(treeview, sheet_name):
            if not treeview.get_children():
                return
            
            all_cols = treeview["columns"]
            # displaycolumns가 #all일 경우 모든 컬럼을 사용
            visible_cols = list(treeview["displaycolumns"])
            if not visible_cols or visible_cols == ['#all']:
                visible_cols = all_cols

            visible_headers = [treeview.heading(col)["text"] for col in visible_cols if col in all_cols]
            col_mapping = {col: i for i, col in enumerate(all_cols)}
            
            # visible_cols에 있는 컬럼의 인덱스만 추출
            try:
                visible_indices = [col_mapping[col] for col in visible_cols]
            except KeyError as e:
                print(f"'{sheet_name}' 시트 처리 중 오류: 컬럼 '{e}'를 찾을 수 없습니다.")
                return

            data = []
            for item_id in treeview.get_children():
                all_values = treeview.item(item_id)["values"]
                # all_values가 문자열일 경우 튜플로 변환 (예외 처리)
                if isinstance(all_values, str):
                    # 이 경우는 데이터가 잘못 들어간 것이므로 건너뛰거나 로깅
                    print(f"경고: {sheet_name}의 Treeview 항목 {item_id}에 잘못된 데이터가 있습니다: {all_values}")
                    continue
                
                # all_values의 길이가 인덱스보다 짧은 경우를 대비
                visible_values = [all_values[i] if i < len(all_values) else "" for i in visible_indices]
                data.append(visible_values)
            
            if data:
                sheets_data[sheet_name] = {"type": "table", "content": {"headers": visible_headers, "data": data}}

        # 1. 복합 전성분 (원료별 목록) 데이터 추출
        # RM 함량으로 정렬하기 위해 데이터를 다시 생성
        session = db_manager.get_session()
        try:
            formulation_items = session.query(FormulationItem).filter_by(formulation_id=self._selected_formulation_id).order_by(FormulationItem.ratio.desc()).all()
            
            raw_material_data = []
            material_no = 1
            for item in formulation_items:
                if not item.material_code or item.material_code == "---":
                    continue

                material = session.query(Material).filter_by(code=item.material_code).first()
                actual_wt_total_for_item = 0

                if not material or not material.ingredients:
                    actual_wt = item.ratio or 0
                    raw_material_data.append([
                        material_no, material.name if material else item.material_name, "", item.material_name,
                        f"{item.ratio or 0:.4f}", "100.0000", f"{actual_wt:.6f}", "", "", "", "", ""
                    ])
                    material_no += 1
                else:
                    for i, ing in enumerate(sorted(material.ingredients, key=lambda x: x.id)):
                        actual_wt = (item.ratio or 0) * ((ing.composition_ratio or 0) / 100.0)
                        actual_wt_total_for_item += actual_wt
                        if i == 0:
                            raw_material_data.append([
                                material_no, material.name, ing.name_en or "", ing.name_ko, f"{item.ratio or 0:.4f}", f"{ing.composition_ratio or 0:.4f}", f"{actual_wt:.6f}", ing.cas_no, ing.function, ing.hs_code or "", ing.nmpa_reg_num or "", ing.remark or ""
                            ])
                        else:
                            raw_material_data.append([
                                "", "", ing.name_en or "", ing.name_ko, "", f"{ing.composition_ratio or 0:.4f}", f"{actual_wt:.6f}", ing.cas_no, ing.function, ing.hs_code or "", ing.nmpa_reg_num or "", ing.remark or ""
                            ])
                    material_no += 1
            raw_headers = ["NO", "원료명", "INCI Name", "성분의 한글명", "RM 함량(%)", "성분 함량(%)", "Actual Wt (%)", "CAS No.", "Ingredient function", "HS CODE", "NMPA", "Remark"]
            sheets_data["원료별 목록"] = {"type": "table", "content": {"headers": raw_headers, "data": raw_material_data}}
        finally:
            session.close()

        # 2. 전성분 합계 데이터 추출
        extract_tree_data(self.summed_ingredient_tree, "전성분 합계")

        # 3. 단일 전성분 데이터 추출 (국문/영문 분리)
        summed_ingredients = {}
        session = db_manager.get_session()
        try:
            formulation_items = session.query(FormulationItem).filter_by(formulation_id=self._selected_formulation_id).all()
            for item in formulation_items:
                if not item.material_code or item.material_code == "---" or item.ratio is None: continue
                material = session.query(Material).filter_by(code=item.material_code).first()
                if material and material.ingredients:
                    for ing in material.ingredients:
                        actual_ratio = item.ratio * (ing.composition_ratio / 100.0)
                        key = (ing.name_ko or "", ing.name_en or "")
                        if key not in summed_ingredients:
                            summed_ingredients[key] = {
                                'total_ratio': 0, 'cas_no': ing.cas_no or "", 'function': ing.function or "",
                                'hs_code': ing.hs_code or "", 'nmpa_reg_num': ing.nmpa_reg_num or "", 'remark': ing.remark or ""
                            }
                        summed_ingredients[key]['total_ratio'] += actual_ratio
        finally:
            session.close()

        if summed_ingredients:
            sorted_ingredients = sorted(summed_ingredients.items(), key=lambda x: x[1]['total_ratio'], reverse=True)
            
            # 국문 시트 데이터
            ko_headers = ["NO", "성분명", "C.I NO", "% (W/W)", "CAS. NO", "FUNCTION"]
            ko_data = []
            for i, ((name_ko, name_en), data) in enumerate(sorted_ingredients, 1):
                ko_data.append([i, name_ko, "", f"{data['total_ratio']:.6f}", data['cas_no'], data['function']])
            sheets_data["단일 전성분 (국문)"] = {"type": "table", "content": {"headers": ko_headers, "data": ko_data}}

            # 영문 시트 데이터
            en_headers = ["NO", "INGREDIENT", "C.I NO", "% (W/W)", "CAS. NO", "FUNCTION"]
            en_data = []
            for i, ((name_ko, name_en), data) in enumerate(sorted_ingredients, 1):
                en_data.append([i, name_en, "", f"{data['total_ratio']:.6f}", data['cas_no'], data['function']])
            sheets_data["단일 전성분 (영문)"] = {"type": "table", "content": {"headers": en_headers, "data": en_data}}


        # 4. 디자인용 전성분 데이터 추출
        ko_text = self.design_ko_textbox.get("1.0", "end-1c").strip()
        en_text = self.design_en_textbox.get("1.0", "end-1c").strip()
        if ko_text and "버튼을 눌러주세요" not in ko_text:
            design_headers = ["구분", "전성분 목록"]
            design_data = [
                ("국문:", ko_text),
                ("영문 (INCI):", en_text)
            ]
            # 'table' 형식으로 데이터를 구성하여 전달합니다.
            sheets_data["디자인용 전성분"] = {"type": "table", "content": {"headers": design_headers, "data": design_data}}

        if not sheets_data:
            messagebox.showwarning("내보내기 오류", "내보낼 데이터가 없습니다. '전체 목록 생성'을 먼저 실행해주세요.", parent=self)
            return

        session = db_manager.get_session()
        formulation = session.query(Formulation).filter_by(id=self._selected_formulation_id).first()
        session.close()
        default_filename = f"{formulation.experiment_name}_전성분목록.xlsx" if formulation else "전성분목록.xlsx"
        
        excel_handler.export_ingredient_lists_to_excel(sheets_data, default_filename)

    def setup_placeholder_tab(self, tab_frame, tab_name):
        """개발 예정인 탭의 플레이스홀더 UI를 설정합니다."""
        tab_frame.grid_columnconfigure(0, weight=1)
        tab_frame.grid_rowconfigure(0, weight=1)
        
        label = ctk.CTkLabel(tab_frame, text=f"{tab_name}\n기능 개발 예정입니다.", font=ctk.CTkFont(size=20, weight="bold"))
        label.grid(row=0, column=0, padx=20, pady=20)

    def load_formulations(self, client_id=None):
        """DB에서 처방 목록을 불러와 현재 뷰에 맞게 표시합니다."""
        if self.current_view == "folders":
            self.load_folders(client_id=client_id, is_initial_load=True)
        elif self.current_view == "files":
            self.load_files_in_folder(self.current_folder_name, client_id)

    def load_folders(self, client_id=None, is_initial_load=True):
        """실험품명 그룹을 폴더 카드로 표시합니다."""
        for widget in self.folder_view.winfo_children():
            widget.destroy()

        # 거래처 필터 목록과 맵을 새로고침합니다.
        session = db_manager.get_session()
        self.client_map = {c.name: c.id for c in session.query(Client).all()}
        all_client_types = ["- 유형 선택 -"] + db_manager.get_unique_client_types()
        self.list_filter_client_type_combo.configure(values=all_client_types)
        
        if client_id is None:
            self.list_filter_client_type_combo.set("- 유형 선택 -")
            self.update_list_filter_client_name_combo("- 유형 선택 -")

        # 초기 로드 시에만 설정 파일에서 슬라이더 값을 읽어옵니다.
        if is_initial_load:
            try:
                icon_size_str = self.app.get_config_value('Appearance', 'folder_icon_size', '40')
                # 문자열을 float으로 먼저 변환한 후 int로 변환하여 '40.0' 같은 형태도 처리
                self.icon_size_slider.set(int(float(icon_size_str)))
            except Exception as e:
                print(f"폴더 아이콘 크기 로드 실패: {e}")
                self.icon_size_slider.set(40)
        try:
            query = session.query(Formulation.experiment_name, func.count(Formulation.id))
            if client_id:
                query = query.filter(Formulation.oem_odm_client_id == client_id) # 타겟 거래처는 텍스트이므로 필터에서 제외
            grouped_data = query.group_by(Formulation.experiment_name).order_by(Formulation.experiment_name).all()

            if not grouped_data:
                ctk.CTkLabel(self.folder_view, text="처방 데이터가 없습니다.\n'신규' 버튼을 눌러 새 처방을 작성하세요.", font=ctk.CTkFont(size=16)).pack(pady=50)
                return

            row, col = 0, 0
            for name, count in grouped_data:
                card = self.create_folder_card(self.folder_view, name, count)
                card.grid(row=row, column=col, padx=10, pady=10, sticky="nsew")
                col += 1
                if col >= 5:
                    col = 0
                    row += 1
        finally:
            session.close()

    def load_files_in_folder(self, folder_name, client_id=None):
        """특정 폴더(실험품명)에 속한 처방들을 파일 목록으로 표시합니다."""
        for item in self.formulation_tree.get_children():
            self.formulation_tree.delete(item)

        session = db_manager.get_session()
        try:
            query = session.query(Formulation).filter_by(experiment_name=folder_name)
            if client_id:
                 query = query.filter(Formulation.oem_odm_client_id == client_id) # 타겟 거래처는 텍스트이므로 필터에서 제외
            
            formulations = query.order_by(Formulation.created_at.desc()).all()

            for i, form in enumerate(formulations):
                tag = 'oddrow' if i % 2 == 0 else 'evenrow'
                self.formulation_tree.insert("", "end", tags=(tag,), values=(
                    form.id,
                    form.revision or "N/A",
                    form.manager_code or "",
                    form.experiment_date if form.experiment_date else "",
                    form.lab_no or "",
                    f"{form.sample_sent_count:02d}" if form.sample_sent_count > 0 else ""
                ))
        finally:
            session.close()

    def on_formulation_tree_select(self, event):
        """Treeview에서 처방 선택 시 ID를 저장하고 버튼 상태를 업데이트합니다."""
        selected_items = self.formulation_tree.selection()
        if selected_items:
            # 여러 개가 선택되어도, 단일 선택 기반 기능(수정, 견적 등)을 위해 첫 번째 항목의 ID를 저장합니다.
            first_item_values = self.formulation_tree.item(selected_items[0], "values")
            if first_item_values and str(first_item_values[0]).isdigit():
                self._selected_formulation_id = int(first_item_values[0])
            else:
                self._selected_formulation_id = None
        else:
            self._selected_formulation_id = None
        self.update_button_states()

    def get_selected_formulation_ids(self):
        """Treeview에서 선택된 모든 처방의 ID 목록을 반환합니다."""
        selected_ids = []
        selected_items = self.formulation_tree.selection()
        for item_id in selected_items:
            item_values = self.formulation_tree.item(item_id, "values")
            if item_values and str(item_values[0]).isdigit():
                selected_ids.append(int(item_values[0]))
        return selected_ids

    def delete_formulation(self):
        """선택된 처방을 삭제합니다."""
        selected_ids = self.get_selected_formulation_ids()
        if not selected_ids:
            messagebox.showwarning("선택 오류", "삭제할 처방을 목록에서 선택하세요.", parent=self)
            return
        
        if not messagebox.askyesno("삭제 확인", f"정말로 선택한 {len(selected_ids)}개의 처방을 삭제하시겠습니까?", parent=self):
            return

        session = db_manager.get_session()
        try:
            # 선택된 모든 ID에 대해 삭제를 수행합니다.
            query = session.query(Formulation).filter(Formulation.id.in_(selected_ids))
            deleted_count = query.delete(synchronize_session=False)
            
            session.commit()
            
            messagebox.showinfo("성공", f"{deleted_count}개의 처방이 삭제되었습니다.", parent=self)
            self._selected_formulation_id = None # ID 초기화
            self.update_button_states() # 버튼 상태 업데이트
            self.load_formulations()

        except Exception as e:
            session.rollback()
            messagebox.showerror("데이터베이스 오류", f"삭제 중 오류 발생: {e}", parent=self)
        finally:
            session.close()

    def increment_sample_sent_count(self):
        """선택된 처방의 샘플 발송 횟수를 1 증가시킵니다."""
        if not self._selected_formulation_id:
            messagebox.showwarning("선택 오류", "샘플 발송 처리할 처방을 목록에서 선택하세요.", parent=self)
            return

        if not messagebox.askyesno("샘플 발송 확인", "선택한 처방의 샘플 발송 횟수를 1 증가시키겠습니까?", parent=self):
            return

        session = db_manager.get_session()
        try:
            formulation = session.query(Formulation).filter_by(id=self._selected_formulation_id).first()
            if formulation:
                formulation.sample_sent_count = (formulation.sample_sent_count or 0) + 1
                session.commit()
                messagebox.showinfo("성공", f"샘플 발송 횟수가 {formulation.sample_sent_count}로 업데이트되었습니다.", parent=self)
                # 목록을 다시 로드하여 화면에 즉시 반영
                self.load_files_in_folder(self.current_folder_name)
            else:
                messagebox.showerror("오류", "선택된 처방을 찾을 수 없습니다.", parent=self)
        except Exception as e:
            session.rollback()
            messagebox.showerror("데이터베이스 오류", f"샘플 발송 횟수 업데이트 중 오류 발생: {e}", parent=self)
        finally:
            session.close()

    def edit_sample_sent_count(self):
        """선택된 처방의 샘플 발송 횟수를 사용자가 입력한 값으로 수정합니다."""
        if not self._selected_formulation_id:
            messagebox.showwarning("선택 오류", "수정할 처방을 목록에서 선택하세요.", parent=self)
            return

        session = db_manager.get_session()
        try:
            formulation = session.query(Formulation).filter_by(id=self._selected_formulation_id).first()
            if not formulation:
                messagebox.showerror("오류", "선택된 처방을 찾을 수 없습니다.", parent=self)
                return

            dialog = ctk.CTkInputDialog(
                text=f"'{formulation.experiment_name}' ({formulation.lab_no})\n\n새로운 샘플 발송 횟수를 입력하세요:",
                title="샘플 발송 횟수 수정"
            )
            new_count_str = dialog.get_input()

            if new_count_str is None: # 사용자가 취소한 경우
                return

            try:
                new_count = int(new_count_str)
                if new_count < 0:
                    messagebox.showwarning("입력 오류", "발송 횟수는 0 이상의 숫자여야 합니다.", parent=self)
                    return
            except ValueError:
                messagebox.showwarning("입력 오류", "숫자만 입력해주세요.", parent=self)
                return

            formulation.sample_sent_count = new_count
            session.commit()
            messagebox.showinfo("성공", f"샘플 발송 횟수가 {new_count}로 업데이트되었습니다.", parent=self)
            self.load_files_in_folder(self.current_folder_name)

        except Exception as e:
            session.rollback()
            messagebox.showerror("데이터베이스 오류", f"샘플 발송 횟수 수정 중 오류 발생: {e}", parent=self)
        finally:
            session.close()
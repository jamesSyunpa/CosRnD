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
from database.models import Client, Formulation, FormulationItem, Material, User
from datetime import datetime, date
from modules import excel_handler
from modules.comparison_popup import FormulationComparisonPopup
from modules.folder_history_popup import FolderHistoryPopup
from modules.ui_components import HelpPopup, CustomErrorDialog, CustomDropdown, AddMaterialDialog, try_convert_to_float
from modules.translation import get_texts
from modules.formulation_popup import FormulationEditPopup, to_decimal, decimal_to_str_full # FormulationEditPopup은 그대로 둡니다.
from decimal import Decimal

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
        self.search_timer = None # 검색 디바운싱을 위한 타이머

        # --- 검색 프레임 ---
        search_frame = ctk.CTkFrame(self, fg_color="transparent")
        search_frame.grid(row=0, column=0, padx=10, pady=10, sticky="ew")
        search_frame.grid_columnconfigure(1, weight=1)
        
        ctk.CTkLabel(search_frame, text="원료 검색:").grid(row=0, column=0, padx=5)
        self.search_entry = ctk.CTkEntry(search_frame)
        self.search_entry.grid(row=0, column=1, padx=5, sticky="ew")
        self.search_entry.bind("<Return>", self.search_materials)
        self.search_entry.bind("<KeyRelease>", self.on_material_search) # 디바운싱 적용
        ctk.CTkButton(search_frame, text="검색", width=60, command=self.search_materials).grid(row=0, column=2, padx=5)
        ctk.CTkButton(search_frame, text="초기화", width=60, command=self.reset_search).grid(row=0, column=3, padx=5)

        # --- 원료 목록 Treeview (탭 뷰 제거) ---
        tree_frame = ctk.CTkFrame(self, fg_color="transparent")
        tree_frame.grid(row=1, column=0, padx=10, pady=5, sticky="nsew")
        tree_frame.grid_columnconfigure(0, weight=1)
        tree_frame.grid_rowconfigure(0, weight=1)

        self.material_tree = ttk.Treeview(tree_frame, columns=("id", "code", "name", "ingredients"), show="headings", selectmode="browse")
        self.material_tree.heading("id", text="ID"); self.material_tree.column("id", width=50, anchor="center")
        self.material_tree.heading("code", text="코드"); self.material_tree.column("code", width=120)
        self.material_tree.heading("name", text="원료명"); self.material_tree.column("name", width=150)
        self.material_tree.heading("ingredients", text="전성분"); self.material_tree.column("ingredients", width=200, stretch=True)
        self.material_tree.grid(row=0, column=0, sticky="nsew")

        scrollbar = ttk.Scrollbar(tree_frame, orient="vertical", command=self.material_tree.yview)
        self.material_tree.configure(yscrollcommand=scrollbar.set)
        scrollbar.grid(row=0, column=1, sticky="ns")
        self.material_tree.bind("<<TreeviewSelect>>", self.on_material_select)
        self.material_tree.bind("<Double-1>", self.on_double_click_add)

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

    def on_material_search(self, event=None):
        """검색창 입력 시 디바운싱을 적용하여 검색을 실행합니다."""
        if self.search_timer:
            self.after_cancel(self.search_timer)
        # 500ms(0.5초) 후에 search_materials 함수를 실행
        self.search_timer = self.after(500, self.search_materials)

    def search_materials(self, event=None):
        """DB에서 원료를 검색하여 단일 Treeview에 표시합니다."""
        search_term = self.search_entry.get().strip()
        
        # Treeview 초기화
        for item in self.material_tree.get_children():
            self.material_tree.delete(item)

        # 전성분 이름으로도 검색하고, Treeview에 표시할 전성분 정보를 함께 로드하도록
        # load_ingredients와 search_ingredients 옵션을 모두 True로 설정합니다.
        materials = db_manager.search_materials(search_term, load_ingredients=True, search_ingredients=True)
        
        for mat in materials:
            # 전성분 목록을 문자열로 만듭니다 (최대 3개).
            ing_names = [ing.name_en for ing in mat.ingredients[:3]]
            ing_str = ", ".join(ing_names)
            if len(mat.ingredients) > 3:
                ing_str += "..."
            self.material_tree.insert("", "end", values=(mat.id, mat.code, mat.name, ing_str))

    def on_material_select(self, event=None):
        """트리뷰에서 원료 선택 시 전성분 목록을 표시합니다."""
        selected_item = self.material_tree.selection()
        # 텍스트박스 초기화
        self.ingredient_details_textbox.configure(state="normal")
        self.ingredient_details_textbox.delete("1.0", "end")

        if not selected_item:
            self.ingredient_details_textbox.configure(state="disabled")
            return

        material_id = self.material_tree.item(selected_item[0], "values")[0]

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
        selected_item = self.material_tree.selection()
        if not selected_item:
            messagebox.showwarning("선택 오류", "목록에서 추가할 원료를 선택하세요.", parent=self)
            return
        
        material_id = self.material_tree.item(selected_item[0], "values")[0]
        self.on_add_callback(material_id)
        
        # 추가 후 입력 필드 초기화
        self.material_tree.selection_remove(selected_item)

def try_convert_to_float(value):
    """값을 float으로 변환 시도, 실패 시 원래 값 반환"""
    if value is None:
        return None
    try:
        return float(value)
    except (ValueError, TypeError):
        return value

class DocumentManagementFrame(ctk.CTkFrame):
    def __init__(self, master, user, app, texts):
        super().__init__(master)
        self.current_user = user
        self.app = app
        self.texts = texts # App으로부터 중앙 texts 객체를 전달받음
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
        self.help_button = ctk.CTkButton(top_frame, text=self.texts['help'], width=80, command=self.show_help)
        self.help_button.place(relx=0.98, y=10, anchor="ne")

        # '처방 관리'와 '문서' 탭을 추가합니다.
        self.tab_map = {
            self.texts["formulation_mgt"]: "document/formulation_mgt",
            self.texts["document_sub"]: "document/document_sub"
        }
        for tab_name in self.tab_map.keys():
            self.tab_view.add(tab_name)

        # 탭 설정
        self.setup_formulation_tab(self.tab_view.tab(self.texts["formulation_mgt"]))
        self.setup_document_sub_tabs(self.tab_view.tab(self.texts["document_sub"]))
        
        self.load_formulations()

    def setup_document_sub_tabs(self, tab_frame):
        """'문서' 탭 내부에 서브 탭들을 설정합니다."""
        tab_frame.grid_columnconfigure(0, weight=1)
        tab_frame.grid_rowconfigure(0, weight=1)

        doc_sub_tab_view = ctk.CTkTabview(tab_frame, border_width=1, border_color=("gray80", "gray30"))
        doc_sub_tab_view.grid(row=0, column=0, padx=10, pady=10, sticky="nsew")

        # 요청된 하위 탭들 추가
        doc_sub_tab_view.add(self.texts["property_spec"])
        doc_sub_tab_view.add(self.texts["report"])

        # 각 탭의 UI 설정
        self.setup_lab_journal_tab(doc_sub_tab_view.tab(self.texts["property_spec"]))
        self.setup_functional_report_tab(doc_sub_tab_view.tab(self.texts["report"]))


    def show_help(self):
        """서류 관리 도움말을 표시합니다."""
        title = self.texts['doc_mgt_help_title']
        message = self.texts['doc_mgt_help_message']
        HelpPopup(self, title, message)

    def on_tab_change(self):
        selected_tab = self.tab_view.get()
        # 탭 이름에 해당하는 고유 키를 찾아서 활동을 기록합니다.
        static_key = self.tab_map.get(selected_tab)
        if static_key:
            self.app.record_action(static_key)

    def switch_to_tab(self, tab_name):
        if tab_name in self.tab_view._name_list: # pylint: disable=protected-access
            self.tab_view.set(tab_name)

    def refresh_data(self):
        """문서 관리 프레임의 데이터를 새로고침합니다. (선택 유지)"""
        print("문서 관리 프레임 데이터 새로고침...")
        try:
            # 현재 선택된 ID와 뷰 상태 저장
            selected_ids = self.get_selected_formulation_ids()
            current_view = self.current_view
            current_folder = self.current_folder_name

            # 데이터 새로고침
            self.load_formulations() # 폴더 또는 파일 뷰 새로고침
            self.load_lab_journal()    # 실험일지 탭 새로고침
            self.refresh_formulation_filters() # 필터 새로고침

            # 이전에 선택했던 항목 다시 선택 (파일 뷰일 때만)
            if current_view == "files" and selected_ids:
                self.formulation_tree.selection_set(selected_ids)
            
            # 선택된 항목에 따라 다른 탭들 내용 업데이트
            self.generate_all_ingredient_lists()

        except Exception as e:
            print(f"[오류] 문서 관리 프레임 새로고침 실패: {e}")

    def refresh_formulation_filters(self):
        print("처방 필터 새로고침...")
        all_client_types = [self.texts['select_type']] + db_manager.get_unique_client_types()
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

        # --- 언어별 텍스트 ---
        texts = {
            "korean": {"list": "처방 목록", "quote": "견적", "ingredient": "전성분"},
            "english": {"list": "Formulation List", "quote": "Quotation", "ingredient": "Ingredient List"}
        }
        current_texts = texts[self.app.language]

        self.formulation_sub_tab_view.add(current_texts["list"])
        self.formulation_sub_tab_view.add(current_texts["quote"])
        self.formulation_sub_tab_view.add(current_texts["ingredient"])
        # self.formulation_sub_tab_view.add("생산 처방")

        self.setup_formulation_list_tab(self.formulation_sub_tab_view.tab(current_texts["list"]))
        self.setup_quotation_tab(self.formulation_sub_tab_view.tab(current_texts["quote"]))
        self.setup_ingredient_list_tab(self.formulation_sub_tab_view.tab(current_texts["ingredient"]))
        # self.setup_placeholder_tab(self.formulation_sub_tab_view.tab("생산 처방"), "생산 처방")

    def setup_formulation_list_tab(self, parent_tab):
        """'처방 목록' 서브 탭의 UI를 설정합니다. (폴더 카드 UI)"""
        parent_tab.grid_columnconfigure(0, weight=1)
        parent_tab.grid_rowconfigure(1, weight=1)

        # --- 헤더 및 필터 ---
        header_frame = ctk.CTkFrame(parent_tab, fg_color="transparent")
        header_frame.grid(row=0, column=0, sticky="ew", padx=10, pady=(10, 5))
        header_frame.grid_columnconfigure(1, weight=1)

        self.list_header_label = ctk.CTkLabel(header_frame, text=self.texts['formulation_folders'], font=ctk.CTkFont(size=16, weight="bold"))
        self.list_header_label.grid(row=0, column=0, sticky="w")

        filter_frame = ctk.CTkFrame(header_frame, fg_color="transparent")
        filter_frame.grid(row=0, column=1, sticky="e")

        # 아이콘 크기 조절 슬라이더 추가
        ctk.CTkLabel(filter_frame, text=self.texts['icon_size']).pack(side="left", padx=(10, 5))
        self.icon_size_slider = ctk.CTkSlider(filter_frame, from_=20, to=80, number_of_steps=6, command=self.on_icon_size_change)
        self.icon_size_slider.set(40) # 기본값
        self.icon_size_slider.pack(side="left", padx=(0, 20))

        ctk.CTkLabel(filter_frame, text=self.texts['client_filter']).pack(side="left", padx=(0, 5))
        self.list_filter_client_type_combo = CustomDropdown(filter_frame, values=[self.texts['select_type']], width=120, command=self.update_list_filter_client_name_combo)
        self.list_filter_client_type_combo.pack(side="left", padx=(0, 5))
        self.list_filter_client_name_combo = CustomDropdown(filter_frame, values=[self.texts['select_client']], width=250, command=self.filter_formulations_by_client)
        self.list_filter_client_name_combo.pack(side="left", padx=(0, 10))
        self.list_filter_reset_button = ctk.CTkButton(filter_frame, text=self.texts['reset'], width=80, command=lambda: self.load_formulations())
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
        self.back_button = ctk.CTkButton(file_view_header, text=self.texts['back_to_folders'], width=100, command=self.show_folder_view)
        self.back_button.pack(side="left", padx=(0, 10))

        self.compare_button = ctk.CTkButton(file_view_header, text=self.texts['compare_history'], width=100, command=self.open_comparison_popup)
        self.compare_button.pack(side="left", padx=(0, 10))

        self.folder_history_button = ctk.CTkButton(file_view_header, text=self.texts['view_all_history'], width=120, command=self.open_folder_history_popup)
        self.folder_history_button.pack(side="left", padx=(0, 10))

        # 선택 초기화 버튼 추가
        self.reset_selection_button = ctk.CTkButton(file_view_header, text=self.texts['reset_selection'], width=100, command=self.reset_selection_and_tabs)
        self.reset_selection_button.pack(side="left", padx=(0, 10))

        # 샘플 발송/수정: QC를 제외한 연구권한(RD/RQ/RQD/MSAD)에게만 표시
        if hasattr(self.current_user, 'has_research_access') and self.current_user.has_research_access():
            self.edit_sample_button = ctk.CTkButton(file_view_header, text=self.texts['edit_sample_count'], width=100, command=self.edit_sample_sent_count)
            self.edit_sample_button.pack(side="right", padx=(5, 0))

            self.send_sample_button = ctk.CTkButton(file_view_header, text=self.texts['send_sample'], width=100, command=self.increment_sample_sent_count)
            self.send_sample_button.pack(side="right")

        formulation_cols_def = self.texts['formulation_tree_columns']
        # 'id'는 Treeview의 내부 식별자(iid)로 사용되므로 columns 리스트에서는 제외합니다.
        # 사용자가 요청한 순서대로 컬럼 ID를 정의합니다. ('id'는 iid로 사용되므로 제외)
        # 컬럼 순서를 'date', 'experiment_name', 'lab_no', 'revision', 'sample_sent', 'sample_delivery_date'로 변경
        formulation_col_ids = ['date', 'experiment_name', 'lab_no', 'revision', 'sample_sent', 'sample_delivery_date']
        self.formulation_tree = ttk.Treeview(self.file_view, columns=formulation_col_ids, show="headings", selectmode="extended")
        for col_id in formulation_col_ids:
            # 'id'가 아닌 컬럼에 대해서만 헤더와 너비를 설정합니다.
            # 'revision'과 'experiment_name' 컬럼은 넓게 표시하도록 조정합니다.
            # 샘플 발송 컬럼의 기본 너비를 120으로 보고, 차수(revision)는 샘플 발송과 동일하게 설정
            if col_id == 'experiment_name':
                width = 260  # 제품명은 가장 크게 표시
            elif col_id == 'revision' or col_id == 'sample_sent':
                width = 120  # 샘플 발송과 차수는 동일 너비
            else:
                width = 120

            # 제품명만 확장 가능하도록 설정(가로 공간이 남을 때 늘어남)
            stretch = True if col_id == 'experiment_name' else False
            self.formulation_tree.heading(col_id, text=formulation_cols_def.get(col_id, col_id), command=lambda c=col_id: self.sort_treeview_column(self.formulation_tree, c, False))
            self.formulation_tree.column(col_id, width=width, stretch=stretch)
        self.formulation_tree.grid(row=1, column=0, columnspan=2, sticky="nsew")
        self.formulation_tree.bind("<<TreeviewSelect>>", self.on_formulation_tree_select)
        self.formulation_tree.bind("<Double-1>", lambda e: self.open_formulation_popup(edit_mode=True))

        # 처방 목록 스크롤바
        form_v_scroll = ttk.Scrollbar(self.file_view, orient="vertical", command=self.formulation_tree.yview)
        self.formulation_tree.configure(yscrollcommand=form_v_scroll.set)
        form_v_scroll.grid(row=1, column=2, sticky='ns')
        form_h_scroll = ttk.Scrollbar(self.file_view, orient="horizontal", command=self.formulation_tree.xview)
        self.formulation_tree.configure(xscrollcommand=form_h_scroll.set)
        form_h_scroll.grid(row=2, column=0, columnspan=2, sticky='ew')

        # --- 하단 버튼 ---
        bottom_button_frame = ctk.CTkFrame(parent_tab, fg_color="transparent")
        bottom_button_frame.grid(row=2, column=0, padx=10, pady=(5, 10), sticky="ew")
        
        # 관리자 전용 버튼들 (왼쪽 정렬)
        if self.current_user.is_admin:
            self.export_logs_button = ctk.CTkButton(bottom_button_frame, text="이력 내보내기", width=120, command=self.export_change_logs)
            self.export_logs_button.pack(side="left", padx=(0, 5))
        
        # --- 오른쪽 정렬 버튼들 ---
        # pack을 right로 하면 역순으로 추가해야 원하는 순서대로 보입니다.
        if self.current_user.is_admin:
            self.import_all_button = ctk.CTkButton(bottom_button_frame, text="처방 전체 가져오기", width=140, command=self.import_all_formulations)
            self.import_all_button.pack(side="right", padx=5)
            self.export_all_button = ctk.CTkButton(bottom_button_frame, text="처방 전체 내보내기", width=140, command=self.export_all_formulations)
            self.export_all_button.pack(side="right", padx=5)
        self.delete_button = ctk.CTkButton(bottom_button_frame, text=self.texts['delete'], width=100, fg_color="#D32F2F", hover_color="#B71C1C", command=self.delete_formulation)
        self.delete_button.pack(side="right", padx=5) # 오른쪽에 여백 추가
        self.edit_button = ctk.CTkButton(bottom_button_frame, text=self.texts['edit'], width=100, command=lambda: self.open_formulation_popup(edit_mode=True))
        self.edit_button.pack(side="right", padx=5)
        self.new_button = ctk.CTkButton(bottom_button_frame, text=self.texts['new'], width=100, command=lambda: self.open_formulation_popup(edit_mode=False))
        self.new_button.pack(side="right", padx=5)

        self.show_folder_view() # 초기 화면은 폴더 뷰

    def setup_quotation_tab(self, tab_frame):
        """견적 탭의 UI를 설정합니다."""
        tab_frame.grid_columnconfigure(0, weight=1)
        tab_frame.grid_rowconfigure(1, weight=1) # Treeview

        # --- 컨트롤 프레임 ---
        control_frame = ctk.CTkFrame(tab_frame, fg_color="transparent")
        control_frame.grid(row=0, column=0, padx=10, pady=10, sticky="ew")

        # --- 좌측 버튼들 ---
        left_button_frame = ctk.CTkFrame(control_frame, fg_color="transparent")
        left_button_frame.pack(side="left")
        ctk.CTkButton(left_button_frame, text=self.texts['create_quotation'], command=self.load_formulation_for_quotation).pack(side="left")
        ctk.CTkButton(left_button_frame, text=self.texts['export_quotation'], command=self.export_quotation).pack(side="left", padx=(10, 0))
        ctk.CTkButton(left_button_frame, text=self.texts['delete_selected'], fg_color="#D32F2F", hover_color="#B71C1C", command=self.delete_selected_quotation_item).pack(side="left", padx=(10, 0))

        # --- 우측 버튼 및 입력창 ---
        right_control_frame = ctk.CTkFrame(control_frame, fg_color="transparent")
        right_control_frame.pack(side="right")
        
        ctk.CTkLabel(right_control_frame, text=self.texts['base_weight_g']).pack(side="left", padx=(20, 5))
        self.quotation_weight_entry = ctk.CTkEntry(right_control_frame, width=100, justify="right")
        self.quotation_weight_entry.insert(0, "1000") # 기본값 1kg
        self.quotation_weight_entry.bind("<KeyRelease>", lambda e: self.recalculate_quotation())
        self.quotation_weight_entry.pack(side="left")
        ctk.CTkButton(right_control_frame, text=self.texts['add_material'], command=self.open_add_material_for_quotation).pack(side="left", padx=(10, 5))
        ctk.CTkButton(right_control_frame, text=self.texts['edit_ratio'], command=self.edit_selected_quotation_item).pack(side="left", padx=5)

        # --- 견적 내용 Treeview ---
        quotation_cols = self.texts['quotation_tree_columns']
        # columns 인자에는 딕셔너리의 키 리스트를 명시적으로 전달해야 합니다.
        self.quotation_tree = ttk.Treeview(tab_frame, columns=list(quotation_cols.keys()), show="headings", selectmode="browse")
        self.quotation_tree.heading("phase", text=quotation_cols['phase']); self.quotation_tree.column("phase", width=80, anchor="center")
        self.quotation_tree.heading("code", text=quotation_cols['code']); self.quotation_tree.column("code", width=100, anchor="w")
        self.quotation_tree.heading("name", text=quotation_cols['name']); self.quotation_tree.column("name", width=250, stretch=True)
        self.quotation_tree.heading("ratio", text=quotation_cols['ratio']); self.quotation_tree.column("ratio", width=100, anchor="e")
        self.quotation_tree.heading("unit_price", text=quotation_cols['unit_price']); self.quotation_tree.column("unit_price", width=120, anchor="e")
        self.quotation_tree.heading("cost", text=quotation_cols['cost']); self.quotation_tree.column("cost", width=120, anchor="e")
        self.quotation_tree.grid(row=1, column=0, columnspan=2, padx=(10,0), pady=(5,0), sticky="nsew")
        self.quotation_tree.bind("<Double-1>", self.on_quotation_tree_double_click)

        # 견적 Treeview 스크롤바
        quot_v_scroll = ttk.Scrollbar(tab_frame, orient="vertical", command=self.quotation_tree.yview)
        self.quotation_tree.configure(yscrollcommand=quot_v_scroll.set)
        quot_v_scroll.grid(row=1, column=2, padx=(0,10), pady=(5,0), sticky='ns')
        quot_h_scroll = ttk.Scrollbar(tab_frame, orient="horizontal", command=self.quotation_tree.xview)
        self.quotation_tree.configure(xscrollcommand=quot_h_scroll.set)
        quot_h_scroll.grid(row=2, column=0, columnspan=2, padx=(10,0), sticky='ew')

        # --- 최종 견적 계산 프레임 (수정) ---
        calculation_frame = ctk.CTkFrame(tab_frame, fg_color="transparent") # row 3으로 변경
        calculation_frame.grid(row=3, column=0, padx=10, pady=10, sticky="e")
        calculation_frame.grid_columnconfigure(1, weight=1)

        # 총 함량
        ctk.CTkLabel(calculation_frame, text=self.texts['total_ratio'], font=ctk.CTkFont(size=14, weight="bold")).grid(row=0, column=0, padx=10, pady=5, sticky="w")
        self.quotation_total_ratio_label = ctk.CTkLabel(calculation_frame, text="0.0000 %", font=ctk.CTkFont(size=14), anchor="e")
        self.quotation_total_ratio_label.grid(row=0, column=1, padx=10, pady=5, sticky="ew")

        # 총 원료 원가
        ctk.CTkLabel(calculation_frame, text=self.texts['total_raw_cost'], font=ctk.CTkFont(size=14, weight="bold")).grid(row=1, column=0, padx=10, pady=5, sticky="w")
        self.total_raw_cost_label = ctk.CTkLabel(calculation_frame, text="0 원", font=ctk.CTkFont(size=14), anchor="e")
        self.total_raw_cost_label.grid(row=1, column=1, padx=10, pady=5, sticky="ew")

        # VAT 10% 포함가
        ctk.CTkLabel(calculation_frame, text=self.texts['price_with_vat'], font=ctk.CTkFont(size=14, weight="bold")).grid(row=2, column=0, padx=10, pady=5, sticky="w")
        self.price_with_vat_label = ctk.CTkLabel(calculation_frame, text="0 원", font=ctk.CTkFont(size=14), anchor="e")
        self.price_with_vat_label.grid(row=2, column=1, padx=10, pady=5, sticky="ew")

        # 이윤 15% 포함가
        ctk.CTkLabel(calculation_frame, text=self.texts['price_with_profit'], font=ctk.CTkFont(size=14, weight="bold")).grid(row=3, column=0, padx=10, pady=5, sticky="w")
        self.price_with_profit_label = ctk.CTkLabel(calculation_frame, text="0 원", font=ctk.CTkFont(size=14), anchor="e")
        self.price_with_profit_label.grid(row=3, column=1, padx=10, pady=5, sticky="ew")

    def load_formulation_for_quotation(self):
        """'처방 목록'에서 선택된 처방을 '견적' 탭의 Treeview로 불러옵니다."""
        if not self._selected_formulation_id:
            messagebox.showwarning(self.texts['selection_error'], self.texts['select_formulation_first'], parent=self)
            return

        for item in self.quotation_tree.get_children():
            self.quotation_tree.delete(item)

        session = db_manager.get_session()
        try:
            formulation = session.query(Formulation).filter_by(id=self._selected_formulation_id).first()
            if not formulation: return

            # item.order를 기준으로 처방 항목을 정렬합니다. None인 경우 마지막으로 보냅니다.
            sorted_items = sorted(formulation.items, key=lambda i: i.order if i.order is not None else float('inf'))

            for item in sorted_items:
                if not item.material_code or item.material_code == "---": continue
                
                material = session.query(Material).filter_by(code=item.material_code).first()
                unit_price = material.unit_price if material else 0.0

                self.quotation_tree.insert("", "end", values=(
                    item.phase or "", item.material_code, item.material_name, f"{item.ratio:.4f}", f"{unit_price or 0:,.0f}", "0.00"
                ))
            
            self.recalculate_quotation()
            
            # [추가] '구분' 열을 행 번호로 정규화하여 순서대로 표시합니다.
            self.app.normalize_group_column_to_row_numbers(self.quotation_tree, header_name='구분', force=True)

        except Exception as e:
            messagebox.showerror(self.texts['quotation_creation_error'], f"{self.texts['quotation_creation_error_msg']}: {e}", parent=self)
        finally:
            session.close()

    def recalculate_quotation(self):
        """현재 Treeview의 내용을 바탕으로 원가와 최종 가격을 다시 계산합니다. (중복 원료 자동 합산)"""
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

        print("[견적계산] 중복 원료 합산 처리 시작")
        
        # 중복 원료 합산 로직
        material_groups = {}
        duplicate_count = 0
        
        # 1단계: 같은 원료 코드끼리 그룹화하여 합산
        for item_id in self.quotation_tree.get_children():
            values = self.quotation_tree.item(item_id, "values")
            try:
                material_code = values[1].strip()  # 원료 코드 (공백 제거)
                material_name = values[2].strip()  # 원료명
                ratio = float(values[3])   # 함량
                unit_price_str = str(values[4]).replace(",", "").strip()
                unit_price = float(unit_price_str) if unit_price_str else 0.0
                
                # 빈 코드나 구분선은 건너뛰기
                if not material_code or material_code == "---":
                    continue
                
                # 같은 원료 코드가 있으면 함량 합산
                if material_code in material_groups:
                    print(f"[견적계산] 중복 원료 발견: {material_code} ({material_name}) - 함량 {material_groups[material_code]['ratio']:.4f}% + {ratio:.4f}%")
                    material_groups[material_code]['ratio'] += ratio
                    material_groups[material_code]['duplicate_items'].append(item_id)
                    duplicate_count += 1
                else:
                    material_groups[material_code] = {
                        'phase': values[0],
                        'name': material_name,
                        'ratio': ratio,
                        'unit_price': unit_price,
                        'original_item_id': item_id,
                        'duplicate_items': []  # 중복된 항목들의 ID 목록
                    }
                    
            except (ValueError, TypeError, IndexError) as e:
                print(f"[견적계산] 항목 처리 중 오류 (항목 {item_id}): {e}")
                continue

        if duplicate_count > 0:
            print(f"[견적계산] 총 {duplicate_count}개의 중복 원료 발견, 합산 처리 중...")

        # 2단계: 중복 항목 제거 및 합산된 결과로 업데이트
        total_raw_cost = 0.0
        total_ratio = 0.0
        updated_items = []
        
        for material_code, material_info in material_groups.items():
            ratio = material_info['ratio']
            unit_price = material_info['unit_price']
            total_ratio += ratio
            
            # 원가 계산: (함량% / 100) * (총중량 / 1000kg) * 단가(원/kg)
            cost = (ratio / 100.0) * (total_weight / 1000.0) * unit_price
            total_raw_cost += cost
            
            # 원래 항목 업데이트 (첫 번째 발견된 항목만 업데이트)
            original_item_id = material_info['original_item_id']
            if self.quotation_tree.exists(original_item_id):
                self.quotation_tree.item(original_item_id, values=(
                    material_info['phase'],
                    material_code,
                    material_info['name'],
                    f"{ratio:.4f}",  # 합산된 함량
                    f"{unit_price:,.0f}",
                    f"{cost:,.2f}"
                ))
                updated_items.append((material_code, ratio))
            
            # 중복 항목들 삭제
            for dup_item_id in material_info['duplicate_items']:
                if self.quotation_tree.exists(dup_item_id):
                    self.quotation_tree.delete(dup_item_id)
                    print(f"[견적계산] 중복 항목 삭제: {material_code}")

        if duplicate_count > 0:
            print(f"[견적계산] 중복 원료 합산 완료: {len(updated_items)}개 원료")
            for code, final_ratio in updated_items:
                print(f"  - {code}: 최종 함량 {final_ratio:.4f}%")

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
            messagebox.showwarning(self.texts['selection_error'], self.texts['select_item_to_edit_ratio'], parent=self)
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
            messagebox.showwarning(self.texts['selection_error'], self.texts['select_item_to_delete'], parent=self)
            return
        
        self.quotation_tree.delete(selected_item)
        self.recalculate_quotation()

    def generate_quotation(self):
        """선택된 처방을 기반으로 견적을 생성합니다."""
        if not self._selected_formulation_id:
            messagebox.showwarning(self.texts['selection_error'], self.texts['select_formulation_first'], parent=self)
            return
        self.load_formulation_for_quotation()

    def export_quotation(self):
        """현재 견적 내용을 엑셀 파일로 내보냅니다."""
        if not self.quotation_tree.get_children():
            messagebox.showwarning(self.texts['export_error'], self.texts['no_quotation_to_export'], parent=self)
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
                    # 담당자명을 ID에서 이름으로 변환
                    manager_name = self.get_manager_display_name(formulation.manager_name or "", session)
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
        self.list_header_label.configure(text=self.texts['formulation_folders'])
        self.current_view = "folders"
        self.current_folder_name = None
        self._selected_formulation_id = None
        self.update_button_states()
        self.load_formulations()

    def export_quotation(self):
        """현재 견적 내용을 엑셀 파일로 내보냅니다."""
        if not self._selected_formulation_id:
            messagebox.showwarning(self.texts['selection_error'], self.texts['select_formulation_and_create_quotation'], parent=self)
            return

        session = db_manager.get_session()
        try:
            formulation = session.query(Formulation).filter_by(id=self._selected_formulation_id).first()
            if not formulation: return

            quotation_data = {
                "details": {
                    "실험품명": formulation.experiment_name,
                    "담당자": self.get_manager_display_name(formulation.manager_name or "", session),
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
        self.list_header_label.configure(text=self.texts['formulation_folders'])
        self.current_view = "folders"
        self.current_folder_name = None
        self._selected_formulation_id = None
        self.update_button_states()
        # 폴더 뷰로 전환될 때, 저장된 아이콘 크기를 불러와서 표시합니다.
        self.load_folders(client_id=client_id_to_load, is_initial_load=True)

    def export_all_formulations(self):
        """
        관리자 기능: DB에 저장된 모든 처방과 그 구성 원료를 엑셀 파일로 내보냅니다.
        시트 구성: 각 처방 정보를 행 단위로 정리한 '처방 목록' 시트와,
        원료별 상세(필요시) 시트를 추가합니다.
        """
        if not self.current_user.is_admin:
            messagebox.showwarning("권한 오류", "관리자만 전체 처방을 내보낼 수 있습니다.", parent=self)
            return

        session = db_manager.get_session()
        try:
            formulations = session.query(Formulation).order_by(Formulation.id).all()
            if not formulations:
                messagebox.showinfo("정보", "내보낼 처방 데이터가 없습니다.", parent=self)
                return

            # '처방 목록' 시트: 헤더 및 행 구성
            headers = [
                "ID", "실험일", "제품명", "LAB NO.", "차수", "샘플 발송 횟수", "샘플 발송일", "담당자", "비고"
            ]
            data_rows = []
            # 또한 원료별 시트(간단)를 위한 매핑도 생성
            raw_rows = []
            for f in formulations:
                exp_date = f.experiment_date or ""
                sample_date = f.sample_delivery_date.isoformat() if getattr(f, 'sample_delivery_date', None) else ""
                # 담당자명을 ID에서 이름으로 변환
                manager_name = self.get_manager_display_name(f.manager_name or "", session)
                data_rows.append([
                    f.id, exp_date, f.experiment_name or "", f.lab_no or "", f.revision or "", f.sample_sent_count or 0, sample_date, manager_name, f.experiment_comment or ""
                ])

                # 각 처방의 원료들을 원료별 목록 시트용으로 확장
                for item in f.items:
                    raw_rows.append([
                        f.id, f.experiment_name or "", item.order or "", item.phase or "", item.material_code or "", item.material_name or "", f"{(item.ratio or 0):.4f}", item.amount or ""
                    ])

            sheets_data = {
                "처방 목록": {"type": "table", "content": {"headers": headers, "data": data_rows}},
                "처방별 원료 목록": {"type": "table", "content": {"headers": ["처방ID", "제품명", "순번", "구분", "원료코드", "원료명", "함량(%)", "중량"], "data": raw_rows}}
            }

            # 기존 excel_handler의 범용 엑셀 내보내기 사용
            excel_handler.export_ingredient_lists_to_excel(sheets_data, default_filename="전체_처방_내보내기.xlsx")

        except Exception as e:
            messagebox.showerror("내보내기 오류", f"전체 처방 내보내기 중 오류가 발생했습니다: {e}", parent=self)
        finally:
            session.close()

    def get_manager_display_name(self, manager_value, session):
        """담당자 필드의 값을 표시용 이름으로 변환합니다"""
        if not manager_value or not manager_value.strip():
            return ""
        
        manager_value = manager_value.strip()
        
        # 숫자로만 이루어진 경우 사용자 ID로 판단하여 이름으로 변환
        if manager_value.isdigit():
            try:
                from database.models import User
                user = session.query(User).filter_by(id=int(manager_value)).first()
                if user:
                    # real_name이 있으면 우선 사용, 없으면 username 사용
                    return user.real_name or user.username
                else:
                    return manager_value  # 사용자를 찾을 수 없으면 원래 값 반환
            except Exception as e:
                print(f"담당자 이름 변환 중 오류: {e}")
                return manager_value
        
        # 이미 이름인 경우 그대로 반환
        return manager_value

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
        self.list_header_label.configure(text=f"{self.texts['folder']}: {folder_name}")
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
            self.reset_selection_button.configure(state="disabled")
            self.delete_button.configure(state="disabled")
            # 관리자 전용 버튼이므로 일반 사용자는 비활성화
            if hasattr(self, 'edit_sample_button'): self.edit_sample_button.configure(state="disabled")
            if hasattr(self, 'send_sample_button'): self.send_sample_button.configure(state="disabled")

        else: # files view
            selection_count = len(self.formulation_tree.selection())
            
            # 폴더에 들어오면 항상 활성화
            self.folder_history_button.configure(state="normal")
            
            # 1개 선택 시: 수정, 샘플 관련 버튼 활성화
            is_single_selected = selection_count == 1
            self.edit_button.configure(state="normal" if is_single_selected else "disabled")
            if hasattr(self, 'send_sample_button'): self.send_sample_button.configure(state="normal" if is_single_selected else "disabled")
            if hasattr(self, 'edit_sample_button'): self.edit_sample_button.configure(state="normal" if is_single_selected else "disabled")
            
            # 2개 선택 시: 비교 버튼 활성화
            self.compare_button.configure(state="normal" if selection_count == 2 else "disabled")
            
            # 1개 이상 선택 시: 삭제, 선택 초기화 버튼 활성화
            # 관리자만 삭제 버튼을 활성화할 수 있습니다.
            if self.current_user.is_admin:
                self.delete_button.configure(state="normal" if selection_count > 0 else "disabled")
            self.reset_selection_button.configure(state="normal" if selection_count > 0 else "disabled")

    def sort_treeview_column(self, tree, col, reverse):
        """Treeview의 컬럼을 클릭하여 정렬하는 함수"""
        try:
            # 컬럼의 데이터와 아이템 ID를 리스트로 추출
            l = [(tree.set(k, col), k) for k in tree.get_children('')]
            
            # 데이터 타입을 확인하여 정렬 (숫자 > 문자)
            try:
                # 숫자 변환 시도 (소수점, 콤마 등 처리)
                l.sort(key=lambda t: float(str(t[0]).replace(',','')), reverse=reverse)
            except (ValueError, TypeError):
                # 숫자 변환 실패 시 문자열로 정렬
                l.sort(key=lambda t: str(t[0]), reverse=reverse)

            # 정렬된 순서대로 아이템을 다시 삽입
            for index, (val, k) in enumerate(l):
                tree.move(k, '', index)

            # 정렬 방향을 다음 클릭을 위해 반대로 설정
            tree.heading(col, command=lambda: self.sort_treeview_column(tree, col, not reverse))
        except Exception as e:
            print(f"Treeview 정렬 오류: {e}")

    def sort_treeview_column(self, tree, col, reverse):
        """Treeview의 컬럼을 클릭하여 정렬하는 함수"""
        try:
            # 컬럼의 데이터와 아이템 ID를 리스트로 추출
            l = [(tree.set(k, col), k) for k in tree.get_children('')]
            
            # 데이터 타입을 확인하여 정렬 (숫자 > 문자)
            try:
                # 숫자 변환 시도 (소수점, 콤마 등 처리)
                l.sort(key=lambda t: float(str(t[0]).replace(',','')), reverse=reverse)
            except (ValueError, TypeError):
                # 숫자 변환 실패 시 문자열로 정렬
                l.sort(key=lambda t: str(t[0]), reverse=reverse)

            # 정렬된 순서대로 아이템을 다시 삽입
            for index, (val, k) in enumerate(l):
                tree.move(k, '', index)

            # 정렬 방향을 다음 클릭을 위해 반대로 설정
            tree.heading(col, command=lambda: self.sort_treeview_column(tree, col, not reverse))
        except Exception as e:
            print(f"Treeview 정렬 오류: {e}")

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

        count_label = ctk.CTkLabel(card, text=f"({count} {self.texts['formulations']})", font=ctk.CTkFont(size=count_size), text_color="gray")
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
                messagebox.showwarning(self.texts['notification'], self.texts['select_formulation_to_edit'], parent=self)
                return
            if len(selected_items) > 1:
                messagebox.showwarning(self.texts['notification'], self.texts['select_one_formulation_to_edit'], parent=self)
                return
            
            formulation_id = int(selected_items[0])
        
        
        popup = FormulationEditPopup( # 분리된 클래스 사용
            master=self,
            user=self.current_user,
            app=self.app,
            on_save_callback=self.app.refresh_data_in_all_frames, # 저장 후 앱 전체 새로고침
            formulation_id=formulation_id
        )
        # 신규 작성 시, 현재 폴더 이름을 기본 실험품명으로 설정
        if not edit_mode and self.current_folder_name:
            popup.exp_name_entry.insert(0, self.current_folder_name)

    def open_comparison_popup(self):
        """선택된 두 처방을 비교하는 팝업을 엽니다."""
        selected_ids = self.get_selected_formulation_ids()
        if len(selected_ids) != 2:
            messagebox.showwarning(self.texts['selection_error'], self.texts['select_two_formulations_to_compare'], parent=self)
            return
        
        formulation_id1, formulation_id2 = selected_ids
        FormulationComparisonPopup(self, formulation_id1, formulation_id2)

    def open_folder_history_popup(self):
        """현재 폴더(실험품명)의 전체 변경 이력을 보여주는 팝업을 엽니다."""
        if not self.current_folder_name:
            messagebox.showwarning(self.texts['error'], self.texts['select_folder_first'], parent=self)
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
        if selected_type == self.texts['select_type']:
            self.list_filter_client_name_combo.set(self.texts['select_client'])
            self.list_filter_client_name_combo.configure(values=[self.texts['select_client']])
            return

        session = db_manager.get_session()
        try:
            clients = session.query(Client).filter_by(is_active=True, client_type=selected_type).order_by(Client.name).all()
            self.client_map.update({client.name: client.id for client in clients})
            client_names = [client.name for client in clients]
            
            values = [self.texts['select_client']] + client_names if client_names else [self.texts['no_clients_found']]
            self.list_filter_client_name_combo.configure(values=values)
            self.list_filter_client_name_combo.set(self.texts['select_client'])
        except Exception as e:
            messagebox.showerror(self.texts['error'], f"{self.texts['client_list_update_error']}: {e}", parent=self)
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

        raw_material_tab = sub_tab_view.add(self.texts['by_raw_material'])
        summed_list_tab = sub_tab_view.add(self.texts['summed_ingredients'])

        # --- 원료별 목록 탭 UI ---
        raw_material_tab.grid_columnconfigure(0, weight=1)
        raw_material_tab.grid_rowconfigure(0, weight=1)  # Treeview가 차지할 공간
        raw_material_tab.grid_rowconfigure(1, weight=0)  # 가로 스크롤바
        raw_material_tab.grid_rowconfigure(2, weight=0)  # 합계 프레임
        
        # 열 정의는 여기에 유지합니다.
        self.complex_ing_cols = self.texts['complex_ingredient_tree_columns']

        self.raw_material_ingredient_tree = ttk.Treeview(raw_material_tab, columns=list(self.complex_ing_cols.keys()), show="headings")
        self._setup_treeview_columns(self.raw_material_ingredient_tree, self.complex_ing_cols)
        self.raw_material_ingredient_tree.grid(row=0, column=0, columnspan=2, sticky="nsew", padx=(10,0), pady=(0, 5))
        self.raw_material_ingredient_tree.tag_configure('material_row', font=('Malgun Gothic', 11, 'bold'))

        # 원료별 목록 스크롤바
        raw_v_scroll = ttk.Scrollbar(raw_material_tab, orient="vertical", command=self.raw_material_ingredient_tree.yview)
        self.raw_material_ingredient_tree.configure(yscrollcommand=raw_v_scroll.set)
        raw_v_scroll.grid(row=0, column=2, sticky='ns', pady=(0,5))
        raw_h_scroll = ttk.Scrollbar(raw_material_tab, orient="horizontal", command=self.raw_material_ingredient_tree.xview)
        self.raw_material_ingredient_tree.configure(xscrollcommand=raw_h_scroll.set)
        raw_h_scroll.grid(row=1, column=0, columnspan=2, sticky='ew', padx=(10,0))

        # 원료별 목록 합계 프레임
        raw_material_summary_frame = ctk.CTkFrame(raw_material_tab, fg_color="transparent")
        raw_material_summary_frame.grid(row=2, column=0, sticky="e", padx=10, pady=5)
        ctk.CTkLabel(raw_material_summary_frame, text=self.texts['total_rm_ratio_label'], font=ctk.CTkFont(weight="bold")).pack(side="left", padx=(0, 5))
        self.raw_material_rm_ratio_total_label = ctk.CTkLabel(raw_material_summary_frame, text="0.0000", font=ctk.CTkFont(weight="bold"))
        self.raw_material_rm_ratio_total_label.pack(side="left", padx=(0, 20))
        ctk.CTkLabel(raw_material_summary_frame, text=self.texts['total_actual_wt_label'], font=ctk.CTkFont(weight="bold")).pack(side="left", padx=(0, 5))
        self.raw_material_actual_wt_total_label = ctk.CTkLabel(raw_material_summary_frame, text="0.000000", font=ctk.CTkFont(weight="bold"))
        self.raw_material_actual_wt_total_label.pack(side="left")

        # --- 전성분 합계 탭 UI ---
        summed_list_tab.grid_columnconfigure(0, weight=1)
        summed_list_tab.grid_rowconfigure(0, weight=1)  # Treeview가 차지할 공간
        summed_list_tab.grid_rowconfigure(1, weight=0)  # 가로 스크롤바
        summed_list_tab.grid_rowconfigure(2, weight=0)  # 합계 프레임

        summed_cols = self.texts['summed_ingredient_tree_columns']
        self.summed_ingredient_tree = ttk.Treeview(summed_list_tab, columns=list(summed_cols.keys()), show="headings") # noqa
        self.summed_ingredient_tree.heading("phase", text=summed_cols['phase']); self.summed_ingredient_tree.column("phase", width=80, anchor="center")
        self.summed_ingredient_tree.heading("name_en", text=summed_cols['name_en']); self.summed_ingredient_tree.column("name_en", width=200, stretch=True) # noqa
        self.summed_ingredient_tree.heading("name_ko", text=summed_cols['name_ko']); self.summed_ingredient_tree.column("name_ko", width=200, stretch=True) # noqa
        self.summed_ingredient_tree.heading("total_ratio", text=summed_cols['total_ratio']); self.summed_ingredient_tree.column("total_ratio", width=120, anchor="e") # noqa
        self.summed_ingredient_tree.heading("cas_no", text=summed_cols['cas_no']); self.summed_ingredient_tree.column("cas_no", width=120) # noqa
        self.summed_ingredient_tree.heading("function", text=summed_cols['function']); self.summed_ingredient_tree.column("function", width=150) # noqa
        self.summed_ingredient_tree.grid(row=0, column=0, columnspan=2, sticky="nsew", padx=(10,0), pady=(0,5))

        # 전성분 합계 스크롤바
        sum_v_scroll = ttk.Scrollbar(summed_list_tab, orient="vertical", command=self.summed_ingredient_tree.yview)
        self.summed_ingredient_tree.configure(yscrollcommand=sum_v_scroll.set)
        sum_v_scroll.grid(row=0, column=2, sticky='ns', pady=(0,5))
        sum_h_scroll = ttk.Scrollbar(summed_list_tab, orient="horizontal", command=self.summed_ingredient_tree.xview)
        self.summed_ingredient_tree.configure(xscrollcommand=sum_h_scroll.set)
        sum_h_scroll.grid(row=1, column=0, columnspan=2, sticky='ew', padx=(10,0))

        # 전성분 합계 요약 프레임
        summed_summary_frame = ctk.CTkFrame(summed_list_tab, fg_color="transparent")
        summed_summary_frame.grid(row=2, column=0, sticky="e", padx=10, pady=5)
        ctk.CTkLabel(summed_summary_frame, text=self.texts['total_ratio_sum'], font=ctk.CTkFont(weight="bold")).pack(side="left", padx=(0, 5))
        self.summed_total_ratio_label = ctk.CTkLabel(summed_summary_frame, text="0.000000", font=ctk.CTkFont(weight="bold"))
        self.summed_total_ratio_label.pack(side="left")

    def generate_raw_material_ingredient_list(self):
        """선택된 처방을 기반으로 원료별 전성분 목록을 생성합니다."""
        if not self._selected_formulation_id:
            messagebox.showwarning(self.texts['selection_error'], self.texts['select_formulation_first'], parent=self)
            return
        
        # Treeview 초기화
        for item in self.raw_material_ingredient_tree.get_children():
            self.raw_material_ingredient_tree.delete(item)

        # 데이터를 먼저 수집하고, 최대 소수점 자릿수를 계산한 후 포맷팅합니다.
        tree_data_to_process = []
        session = db_manager.get_session()
        try:
            # 처방에 포함된 원료 아이템들을 가져옵니다.
            formulation_items = session.query(FormulationItem).filter_by(formulation_id=self._selected_formulation_id).order_by(FormulationItem.order).all()
            total_rm_ratio = Decimal('0')
            total_actual_wt = Decimal('0')
            material_no = 1

            # UI 표시를 위해 RM 함량(ratio) 기준으로 내림차순 정렬
            formulation_items.sort(key=lambda x: (to_decimal(x.ratio) if x.ratio is not None else Decimal('-1')), reverse=True)

            for item in formulation_items:
                # 구분선(---)은 건너뜁니다.
                if not item.material_code or item.material_code == "---": continue

                # 원료 정보와 전성분 정보를 함께 가져옵니다.
                material = session.query(Material).filter_by(code=item.material_code).first()
                group_tag = 'group_odd' if (material_no - 1) % 2 != 0 else 'group_even'

                if not material or not material.ingredients:
                    # 전성분이 없는 원료 처리 (100% 단일 성분으로 간주)
                    rm_ratio_dec = to_decimal(item.ratio)
                    ing_ratio_dec = Decimal('100')
                    actual_wt_dec = rm_ratio_dec # 100%이므로 RM 함량과 동일

                    total_rm_ratio += rm_ratio_dec
                    total_actual_wt += actual_wt_dec

                    tree_data_to_process.append({
                        "is_first": True, "is_separator": False, "group_tag": group_tag,
                        "values": [
                            material_no, material.name if material else item.material_name, "", item.material_name,
                            rm_ratio_dec, ing_ratio_dec, actual_wt_dec, "", "", "", "", ""
                        ]
                    })
                    material_no += 1
                    continue

                # 전성분이 있는 원료 처리
                item_ratio_dec = to_decimal(item.ratio)
                total_rm_ratio += item_ratio_dec

                for i, ing in enumerate(sorted(material.ingredients, key=lambda x: x.id)):
                    ing_comp_ratio_dec = to_decimal(ing.composition_ratio)
                    actual_wt = item_ratio_dec * (ing_comp_ratio_dec / Decimal('100'))
                    total_actual_wt += actual_wt
                    
                    is_first = (i == 0)
                    values = [
                        material_no if is_first else "",
                        material.name if is_first else "",
                        ing.name_en or "", ing.name_ko,
                        item_ratio_dec if is_first else None, # RM 함량은 첫 행에만
                        ing_comp_ratio_dec, # 성분 함량
                        actual_wt, # 실제 함량
                        ing.cas_no, ing.function, "",
                        ing.hs_code or "", ing.nmpa_reg_num or "", ing.remark or ""
                    ]
                    tree_data_to_process.append({
                        "is_first": is_first, "is_separator": False, "group_tag": group_tag,
                        "values": values
                    })
                material_no += 1
            
            # 최대 소수점 자릿수 계산
            max_dp_rm = 0
            max_dp_ing = 0
            max_dp_actual = 0
            for row in tree_data_to_process:
                vals = row["values"]
                # vals[4]: RM 함량, vals[5]: 성분 함량, vals[6]: 실제 함량
                if isinstance(vals[4], Decimal):
                    max_dp_rm = max(max_dp_rm, -vals[4].as_tuple().exponent)
                if isinstance(vals[5], Decimal):
                    max_dp_ing = max(max_dp_ing, -vals[5].as_tuple().exponent)
                if isinstance(vals[6], Decimal):
                    max_dp_actual = max(max_dp_actual, -vals[6].as_tuple().exponent)

            # 포맷팅하여 Treeview에 삽입
            for row_data in tree_data_to_process:
                vals = row_data["values"]
                
                # Decimal 값을 포맷팅된 문자열로 변환
                vals[4] = f"{vals[4]:.{max_dp_rm}f}" if isinstance(vals[4], Decimal) else ""
                vals[5] = f"{vals[5]:.{max_dp_ing}f}" if isinstance(vals[5], Decimal) else ""
                vals[6] = f"{vals[6]:.{max_dp_actual}f}" if isinstance(vals[6], Decimal) else ""

                tags = [row_data["group_tag"]]
                if row_data["is_first"]:
                    tags.append('material_row')

                self.raw_material_ingredient_tree.insert("", "end", values=tuple(vals), tags=tuple(tags))

            # 합계 업데이트
            self.raw_material_rm_ratio_total_label.configure(text=f"{total_rm_ratio:.{max_dp_rm}f}")
            self.raw_material_actual_wt_total_label.configure(text=f"{total_actual_wt:.{max_dp_actual}f}")

        finally:
            session.close()

    def generate_summed_ingredient_list(self):
        """선택된 처방의 모든 전성분 함량을 합산하여 목록을 생성합니다."""
        if not self._selected_formulation_id:
            messagebox.showwarning(self.texts['selection_error'], self.texts['select_formulation_first'], parent=self)
            return

        # Treeview 초기화
        for item in self.summed_ingredient_tree.get_children():
            self.summed_ingredient_tree.delete(item)

        tree_data_to_process = []
        total_summed_ratio = Decimal('0') # { (name_ko, name_en): {data} }
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
                            item_ratio_dec = to_decimal(item.ratio)
                            ing_comp_ratio_dec = to_decimal(ing.composition_ratio)
                            # 원료 내 전성분의 실제 함량 계산 (원료 함량 * (전성분 함량 / 100))
                            actual_ratio = item_ratio_dec * (ing_comp_ratio_dec / Decimal('100'))
                            
                            key = (ing.name_ko or "", ing.name_en or "")
                            if key not in summed_ingredients:
                                summed_ingredients[key] = {
                                    'total_ratio': 0,
                                    'cas_no': ing.cas_no or "",
                                    'function': ing.function or "",
                                    'phases': set()  # 수정: phases를 집합으로 수집
                                }
                            # 합산 및 phases 누적 (중복 제거 위해 set 사용)
                           
                            summed_ingredients[key]['total_ratio'] += actual_ratio
                            summed_ingredients[key]['phases'].add(item.phase or 'N/A')

            # 함량이 높은 순으로 정렬
            sorted_ingredients = sorted(summed_ingredients.items(), key=lambda x: x[1]['total_ratio'], reverse=True)

            # 데이터 수집
            for i, ((name_ko, name_en), data) in enumerate(sorted_ingredients, 1):
                total_ratio = data['total_ratio'] # noqa
                cas_no = data.get('cas_no', '')
                function = data.get('function', '')
                total_summed_ratio += data.get('total_ratio', 0)
                # [수정] '구분' 열에 행 번호를 표시하도록 변경
                tree_data_to_process.append([
                    i, name_en, name_ko, data.get('total_ratio', 0), cas_no, function
                ])

            # 최대 소수점 자릿수 계산
            max_dp_total_ratio = 0
            for row in tree_data_to_process: # [구분, 영문, 국문, 함량, CAS, 기능]
                # [수정] 함량 인덱스가 3에서 3으로 동일 (순서 변경 없음)
                ratio_val = row[3]
                if isinstance(ratio_val, Decimal):
                    max_dp_total_ratio = max(max_dp_total_ratio, -ratio_val.as_tuple().exponent)

            # 포맷팅하여 Treeview에 삽입
            for row_data in tree_data_to_process:
                row_data[3] = f"{row_data[3]:.{max_dp_total_ratio}f}"
                self.summed_ingredient_tree.insert("", "end", values=tuple(row_data))

            # 합계 업데이트
            self.summed_total_ratio_label.configure(text=f"{total_summed_ratio:.{max_dp_total_ratio}f}")
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
        # 특정 Treeview(복합 전성분)의 경우, 일부 열은 다른 열과 함께 활성화되어야 합니다.
        # 예: 'hs_code'가 선택되면 'origin'도 함께 선택, 'nmpa_reg_num'이 선택되면 'material_name_en'도 함께 선택.
        try:
            # 안전하게 BooleanVar 접근
            if columns_config is getattr(self, 'complex_ing_cols', None):
                # HS CODE -> origin
                hs_cfg = columns_config.get('hs_code')
                origin_cfg = columns_config.get('origin')
                if hs_cfg and origin_cfg and hs_cfg.get('variable') and origin_cfg.get('variable'):
                    if hs_cfg['variable'].get():
                        origin_cfg['variable'].set(True)

                # NMPA -> material_name_en
                nmpa_cfg = columns_config.get('nmpa_reg_num')
                name_en_cfg = columns_config.get('material_name_en')
                if nmpa_cfg and name_en_cfg and nmpa_cfg.get('variable') and name_en_cfg.get('variable'):
                    if nmpa_cfg['variable'].get():
                        name_en_cfg['variable'].set(True)

        except Exception:
            # 실패하더라도 기본 동작 계속
            pass

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
        messagebox.showinfo(self.texts['notification'], self.texts['clipboard_copy_dev'], parent=self)

    def setup_single_ingredient_tab(self, tab_frame):
        """'단일 전성분 (함량순)' 탭의 UI를 설정합니다."""
        tab_frame.grid_columnconfigure(0, weight=1)
        tab_frame.grid_rowconfigure(0, weight=1) # Treeview가 차지할 공간
        tab_frame.grid_rowconfigure(1, weight=0) # 가로 스크롤바
        tab_frame.grid_rowconfigure(2, weight=0) # 합계 프레임
        # --- 컨트롤 프레임 ---
        # 컨트롤 프레임이 더 이상 필요 없으므로 삭제합니다.

        # --- 열 선택 메뉴 ---
        self.single_ing_cols = self.texts['single_ingredient_tree_columns']

        # --- 결과 표시 Treeview ---
        self.single_ingredient_tree = ttk.Treeview(tab_frame, columns=list(self.single_ing_cols.keys()), show="headings")
        self._setup_treeview_columns(self.single_ingredient_tree, self.single_ing_cols)
        self.single_ingredient_tree.grid(row=0, column=0, columnspan=2, padx=(10,0), pady=(10,5), sticky="nsew") # Treeview를 맨 위로 이동

        # 단일 전성분 스크롤바
        single_v_scroll = ttk.Scrollbar(tab_frame, orient="vertical", command=self.single_ingredient_tree.yview)
        self.single_ingredient_tree.configure(yscrollcommand=single_v_scroll.set)
        single_v_scroll.grid(row=0, column=2, padx=(0,10), pady=(10,5), sticky='ns')
        single_h_scroll = ttk.Scrollbar(tab_frame, orient="horizontal", command=self.single_ingredient_tree.xview)
        self.single_ingredient_tree.configure(xscrollcommand=single_h_scroll.set)
        single_h_scroll.grid(row=1, column=0, columnspan=2, padx=(10,0), sticky='ew')
        
        # 단일 전성분 합계 프레임
        single_summary_frame = ctk.CTkFrame(tab_frame, fg_color="transparent")
        single_summary_frame.grid(row=2, column=0, sticky="e", padx=10, pady=5)
        ctk.CTkLabel(single_summary_frame, text=self.texts['total_ratio_ww_sum'], font=ctk.CTkFont(weight="bold")).pack(side="left", padx=(0, 5))
        self.single_total_ratio_label = ctk.CTkLabel(single_summary_frame, text="0.000000", font=ctk.CTkFont(weight="bold"))
        self.single_total_ratio_label.pack(side="left")

    def generate_single_ingredient_list(self):
        """선택된 처방의 모든 전성분을 합산하고 함량순으로 정렬하여 목록을 생성합니다."""
        if not self._selected_formulation_id:
            messagebox.showwarning(self.texts['selection_error'], self.texts['select_formulation_first'], parent=self)
            return

        # Treeview 초기화
        for item in self.single_ingredient_tree.get_children():
            self.single_ingredient_tree.delete(item)

        tree_data_to_process = []
        total_summed_ratio = Decimal('0')
        summed_ingredients = {} # { (name_ko, name_en): {data} }
        session = db_manager.get_session()
        try:
            formulation_items = session.query(FormulationItem).filter_by(formulation_id=self._selected_formulation_id).all()
            for item in formulation_items:
                if not item.material_code or item.material_code == "---" or item.ratio is None: continue
                material = session.query(Material).filter_by(code=item.material_code).first()
                if material and material.ingredients: # 전성분이 있는 원료
                    item_ratio_dec = to_decimal(item.ratio)
                    for ing in material.ingredients:
                        ing_comp_ratio_dec = to_decimal(ing.composition_ratio)
                        actual_ratio = item_ratio_dec * (ing_comp_ratio_dec / Decimal('100'))
                        key = (ing.name_ko or "", ing.name_en or "")
                        if key not in summed_ingredients:
                            summed_ingredients[key] = {
                                'total_ratio': 0,
                                'cas_no': ing.cas_no or "", 'function': ing.function or "",
                                'hs_code': ing.hs_code or "", 'nmpa_reg_num': ing.nmpa_reg_num or "", 'remark': ing.remark or ""
                            }
                        summed_ingredients[key]['total_ratio'] += actual_ratio

            # 함량이 높은 순으로 정렬
            sorted_ingredients = sorted(summed_ingredients.items(), key=lambda x: x[1]['total_ratio'], reverse=True)

            # 데이터 수집
            for i, ((name_ko, name_en), data) in enumerate(sorted_ingredients, 1):
                total_summed_ratio += data['total_ratio']
                # TODO: C.I. No. 파싱 로직 추가 필요
                tree_data_to_process.append([
                    i, name_en, "", data['total_ratio'],
                    data['cas_no'], data['function'], data['hs_code'], 
                    data['nmpa_reg_num'], data['remark']
                ])

            # 최대 소수점 자릿수 계산
            max_dp_total_ratio = 0
            for row in tree_data_to_process:
                ratio_val = row[3]
                if isinstance(ratio_val, Decimal):
                    max_dp_total_ratio = max(max_dp_total_ratio, -ratio_val.as_tuple().exponent)

            # 포맷팅하여 Treeview에 삽입
            for row_data in tree_data_to_process:
                row_data[3] = f"{row_data[3]:.{max_dp_total_ratio}f}"
                self.single_ingredient_tree.insert("", "end", values=tuple(row_data))

            # 합계 업데이트
            self.single_total_ratio_label.configure(text=f"{total_summed_ratio:.{max_dp_total_ratio}f}")
        finally:
            session.close()

    def confirm_reset_all_formulations(self):
        """모든 처방 데이터를 리셋하기 전에 사용자에게 확인을 받습니다."""
        if not messagebox.askyesno(self.texts['reset_formulation_ref_title'], self.texts['reset_formulation_ref_confirm'], parent=self):
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
                self.texts['reset_complete'],
                self.texts['reset_formulation_ref_success'].format(count=num_items_updated),
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
            messagebox.showerror(self.texts['db_error'], f"{self.texts['reset_formulation_ref_error']}: {e}", parent=self)
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
        ctk.CTkLabel(ko_frame, text=self.texts['korean_ingredients'], font=ctk.CTkFont(weight="bold")).pack(anchor="w", pady=(0,2))
        self.design_ko_textbox = ctk.CTkTextbox(ko_frame, wrap="word", font=ctk.CTkFont(family="Malgun Gothic", size=14))
        self.design_ko_textbox.pack(fill="both", expand=True)

        # --- 영문 결과 표시 ---
        en_frame = ctk.CTkFrame(tab_frame, fg_color="transparent")
        en_frame.grid(row=3, column=0, padx=10, pady=(5, 10), sticky="nsew")
        en_frame.grid_columnconfigure(0, weight=1)
        ctk.CTkLabel(en_frame, text=self.texts['english_ingredients_inci'], font=ctk.CTkFont(weight="bold")).pack(anchor="w", pady=(0,2))
        self.design_en_textbox = ctk.CTkTextbox(en_frame, wrap="word", font=ctk.CTkFont(family="Malgun Gothic", size=14))
        self.design_en_textbox.pack(fill="both", expand=True)

    def generate_design_ingredient_list(self):
        """선택된 처방을 기반으로 디자인용 전성분 목록(문자열)을 생성합니다."""
        if not self._selected_formulation_id:
            messagebox.showwarning(self.texts['selection_error'], self.texts['select_formulation_first'], parent=self)
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
                    item_ratio_dec = to_decimal(item.ratio)
                    for ing in material.ingredients:
                        ing_comp_ratio_dec = to_decimal(ing.composition_ratio)
                        actual_ratio = item_ratio_dec * (ing_comp_ratio_dec / Decimal('100'))
                        # 디자인용은 이름만 중요하므로 이름으로 그룹화
                        key = (ing.name_ko or "", ing.name_en or "")
                        summed_ingredients[key] = summed_ingredients.get(key, 0) + actual_ratio

            # 함량이 높은 순으로 정렬
            sorted_ingredients = sorted(summed_ingredients.items(), key=lambda x: x[1], reverse=True)

            # 1% 초과 성분과 1% 이하 성분 분리
            above_1_percent = [item for item in sorted_ingredients if item[1] > Decimal('1.0')]
            at_or_below_1_percent = [item for item in sorted_ingredients if item[1] <= Decimal('1.0')]

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
        messagebox.showinfo(self.texts['notification'], self.texts['clipboard_copy_dev'], parent=self)

    def setup_ingredient_list_tab(self, tab_frame):
        """'전성분' 탭의 UI를 설정합니다."""
        tab_frame.grid_columnconfigure(0, weight=1)
        tab_frame.grid_rowconfigure(1, weight=1)
        
        # --- 상단 컨트롤 프레임 ---
        top_control_frame = ctk.CTkFrame(tab_frame, fg_color="transparent")
        top_control_frame.grid(row=0, column=0, padx=10, pady=10, sticky="ew")

        ctk.CTkButton(top_control_frame, text=self.texts['create_all_lists'], command=self.generate_all_ingredient_lists).pack(side="left")
        ctk.CTkButton(top_control_frame, text=self.texts['export_to_excel'], command=self.export_all_ingredient_lists).pack(side="left", padx=(10, 0))

        # --- 열 선택 메뉴 버튼 (컨트롤 프레임에 추가) ---
        # 이 버튼은 나중에 생성될 Treeview를 참조해야 하므로, UI 구성 후 마지막에 command를 설정합니다.
        self.column_selection_button = ctk.CTkButton(top_control_frame, text=self.texts['select_columns_to_display'], width=120)
        self.column_selection_button.pack(side="right", padx=(10, 0))

        # 전성분 탭 내부에 또 다른 탭 뷰를 생성합니다.
        self.ingredient_tab_view = ctk.CTkTabview(
            tab_frame, border_width=1, border_color=("gray85", "gray28"),
            command=self.on_ingredient_tab_change # 탭 변경 시 호출될 함수 연결
        )
        self.ingredient_tab_view.grid(row=1, column=0, padx=10, pady=(0, 10), sticky="nsew")
        
        # 1. 복합 전성분 탭
        complex_tab = self.ingredient_tab_view.add(self.texts['complex_ingredients_for_docs'])
        complex_tab.grid_columnconfigure(0, weight=1); complex_tab.grid_rowconfigure(0, weight=1)
        self.setup_complex_ingredient_tab(complex_tab)

        # 2. 단일 전성분 탭
        single_tab = self.ingredient_tab_view.add(self.texts['single_ingredients_by_ratio'])
        single_tab.grid_columnconfigure(0, weight=1); single_tab.grid_rowconfigure(1, weight=1)
        self.setup_single_ingredient_tab(single_tab)

        # 3. 디자인용 전성분 탭
        design_tab = self.ingredient_tab_view.add(self.texts['ingredients_for_design'])
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
        if selected_main_tab == self.texts['complex_ingredients_for_docs']:
            # 복합 전성분 탭이 선택된 경우, 서브탭 상태에 따라 버튼 가시성 결정
            self.on_complex_ingredient_sub_tab_change()
        else:
            # 다른 메인 탭이 선택된 경우, 버튼 숨김
            self.column_selection_button.pack_forget()

    def on_complex_ingredient_sub_tab_change(self):
        """'복합 전성분' 내의 서브 탭 변경 시 버튼 가시성을 조절합니다."""
        selected_sub_tab = self.complex_ingredient_sub_tab_view.get()
        if selected_sub_tab == self.texts['by_raw_material']:
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
            self.raw_material_actual_wt_total_label.configure(text="0")
            self.summed_total_ratio_label.configure(text="0")
            self.single_total_ratio_label.configure(text="0")
            self.design_ko_textbox.delete("1.0", "end")
            self.design_en_textbox.delete("1.0", "end")

    def export_all_ingredient_lists(self):
        """생성된 모든 전성분 목록을 하나의 엑셀 파일에 여러 시트로 내보냅니다."""
        if not self._selected_formulation_id:
            messagebox.showwarning(self.texts['selection_error'], self.texts['select_formulation_and_create_list'], parent=self)
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
            formulation_items = session.query(FormulationItem).filter_by(formulation_id=self._selected_formulation_id).order_by(FormulationItem.order).all()
            
            # UI와 동일하게 RM 함량(ratio) 기준으로 내림차순 정렬
            formulation_items.sort(key=lambda x: (to_decimal(x.ratio) if x.ratio is not None else Decimal('-1')), reverse=True)
            
            # Build raw material data as dict rows keyed by complex_ing_cols keys.
            col_order = [
                'no', 'material_name', 'inci_name', 'name_ko', 'rm_ratio', 'ing_ratio', 'actual_wt',
                'cas_no', 'function', 'hs_code', 'origin', 'material_name_en', 'nmpa_reg_num', 'remark'
            ]

            raw_rows = []
            raw_rows_decimal = [] # Decimal 객체를 그대로 저장할 리스트
            material_no = 1
            for item in formulation_items:
                if not item.material_code or item.material_code == "---":
                    continue

                material = session.query(Material).filter_by(code=item.material_code).first()
                item_ratio_dec = to_decimal(item.ratio)

                if not material or not material.ingredients:
                    actual_wt = item_ratio_dec
                    row = {
                        'no': material_no,
                        'material_name': material.name if material else item.material_name,
                        'inci_name': "",
                        'name_ko': item.material_name,
                        'rm_ratio': actual_wt,
                        'ing_ratio': Decimal('100'),
                        'actual_wt': actual_wt,
                        'cas_no': "-",
                        'function': "-",
                        'hs_code': "",
                        'origin': material.origin if material else "",
                        'material_name_en': material.name_en if material else "",
                        'nmpa_reg_num': "",
                        'remark': ""
                    }
                    raw_rows_decimal.append(row)
                    material_no += 1
                else:
                    for i, ing in enumerate(sorted(material.ingredients, key=lambda x: x.id)):
                        ing_comp_ratio_dec = to_decimal(ing.composition_ratio)
                        actual_wt = item_ratio_dec * (ing_comp_ratio_dec / Decimal('100'))
                        if i == 0:
                            row = {
                                'no': material_no,
                                'material_name': material.name,
                                'inci_name': ing.name_en or "",
                                'name_ko': ing.name_ko,
                                'rm_ratio': item_ratio_dec,
                                'ing_ratio': ing_comp_ratio_dec,
                                'actual_wt': actual_wt,
                                'cas_no': ing.cas_no or "-",
                                'function': ing.function or "-",
                                'hs_code': ing.hs_code or "",
                                'origin': material.origin if material else "",
                                'material_name_en': material.name_en if material else "",
                                'nmpa_reg_num': ing.nmpa_reg_num or "",
                                'remark': ing.remark or ""
                            }
                        else:
                            row = {
                                'no': "",
                                'material_name': "",
                                'inci_name': ing.name_en or "",
                                'name_ko': ing.name_ko,
                                'rm_ratio': "",
                                'ing_ratio': ing_comp_ratio_dec,
                                'actual_wt': actual_wt,
                                'cas_no': ing.cas_no or "-",
                                'function': ing.function or "-",
                                'hs_code': ing.hs_code or "",
                                'origin': material.origin if material else "",
                                'material_name_en': material.name_en if material else "",
                                'nmpa_reg_num': ing.nmpa_reg_num or "",
                                'remark': ing.remark or ""
                            }
                        raw_rows_decimal.append(row)
                    material_no += 1

            # 최대 소수점 자릿수 계산
            max_dp_rm = 0
            max_dp_ing = 0
            max_dp_actual = 0
            for row in raw_rows_decimal:
                if isinstance(row['rm_ratio'], Decimal):
                    max_dp_rm = max(max_dp_rm, -row['rm_ratio'].as_tuple().exponent)
                if isinstance(row['ing_ratio'], Decimal):
                    max_dp_ing = max(max_dp_ing, -row['ing_ratio'].as_tuple().exponent)
                if isinstance(row['actual_wt'], Decimal):
                    max_dp_actual = max(max_dp_actual, -row['actual_wt'].as_tuple().exponent)

            # 포맷팅하여 최종 raw_rows 생성

            # raw_rows는 이제 포맷팅된 문자열을 가진 딕셔너리 리스트입니다.
            # 이후 로직은 이 raw_rows를 사용합니다.

            # Decide which columns are visible according to complex_ing_cols variables
            visible_cols = []
            cols_config = getattr(self, 'complex_ing_cols', None) or {}
            for col in col_order:
                cfg = cols_config.get(col)
                if cfg is None:
                    # default to visible
                    visible = True
                else:
                    var = cfg.get('variable')
                    if var is None:
                        visible = cfg.get('visible', True)
                    else:
                        visible = var.get()
                if visible:
                    visible_cols.append(col)

            # Map visible_cols to header labels using the columns config when available
            visible_headers = []
            for col in visible_cols:
                if col in cols_config and isinstance(cols_config[col], dict):
                    visible_headers.append(cols_config[col].get('text', col))
                else:
                    # fallback labels
                    label_map = {
                        'no': 'NO', 'material_name': '원료명', 'inci_name': 'INCI Name', 'name_ko': '성분의 한글명',
                        'rm_ratio': 'RM 함량(%)', 'ing_ratio': '성분 함량(%)', 'actual_wt': 'Actual Wt (%)',
                        'cas_no': 'CAS No.', 'function': 'Ingredient function', 'hs_code': 'HS CODE',
                        'origin': '원산지', 'material_name_en': '영문원료명', 'nmpa_reg_num': 'NMPA', 'remark': 'Remark'
                    }
                    visible_headers.append(label_map.get(col, col))

            # Build final data rows in order of visible_cols
            final_data = []
            for row in raw_rows_decimal:
                final_data.append([row.get(col, "") for col in visible_cols])

            if final_data:
                sheets_data["원료별 목록"] = {
                    "type": "table", 
                    "content": {
                        "headers": visible_headers, 
                        "data": final_data,
                        "number_formats": {
                            "RM 함량(%)": f'0.{"0"*max_dp_rm}' if max_dp_rm > 0 else '0',
                            "성분 함량(%)": f'0.{"0"*max_dp_ing}' if max_dp_ing > 0 else '0',
                            "Actual Wt (%)": f'0.{"0"*max_dp_actual}' if max_dp_actual > 0 else '0'
                        }
                    }}
            else:
                # 빈 데이터일 때에도 headers를 채워 넣어 엑셀 시트 구조 유지
                sheets_data["원료별 목록"] = {"type": "table", "content": {"headers": visible_headers, "data": []}}
        finally:
            session.close()
        
        # [수정] 엑셀 내보내기 시 '전성분 합계' 데이터 생성 로직을 UI와 동일하게 수정
        # 기존 extract_tree_data는 Treeview의 현재 보이는 값을 가져오므로,
        # '구분' 열이 Phase 목록으로 잘못 표시될 수 있습니다.
        # 따라서 UI에 표시하는 로직과 동일하게 데이터를 직접 생성합니다.
        summed_ingredients_for_excel = {}
        session = db_manager.get_session()
        try:
            formulation_items = session.query(FormulationItem).filter_by(formulation_id=self._selected_formulation_id).all()
            for item in formulation_items:
                if not item.material_code or item.material_code == "---" or item.ratio is None: continue
                material = session.query(Material).filter_by(code=item.material_code).first()
                if material and material.ingredients:
                    item_ratio_dec = to_decimal(item.ratio)
                    for ing in material.ingredients:
                        ing_comp_ratio_dec = to_decimal(ing.composition_ratio)
                        actual_ratio = item_ratio_dec * (ing_comp_ratio_dec / Decimal('100'))
                        # [수정] 키 생성 시 빈 값을 '-'로 처리
                        key = (ing.name_ko or "", ing.name_en or "", ing.cas_no or "-", ing.function or "-")
                        summed_ingredients_for_excel[key] = summed_ingredients_for_excel.get(key, Decimal('0')) + actual_ratio
        finally:
            session.close()

        if summed_ingredients_for_excel:
            sorted_ingredients = sorted(summed_ingredients_for_excel.items(), key=lambda x: x[1], reverse=True)
            
            max_dp_total_ratio = 0
            for (name_ko, name_en, cas_no, function), total_ratio in sorted_ingredients:
                if isinstance(total_ratio, Decimal):
                    max_dp_total_ratio = max(max_dp_total_ratio, -total_ratio.as_tuple().exponent)

            summed_headers = [self.summed_ingredient_tree.heading(col)["text"] for col in self.summed_ingredient_tree["columns"]]
            summed_data = []
            for i, ((name_ko, name_en, cas_no, function), total_ratio) in enumerate(sorted_ingredients, 1):
                # [수정] 엑셀 데이터 생성 시에도 빈 값을 '-'로 처리 (안전장치)
                summed_data.append([i, name_en, name_ko, total_ratio, cas_no or "-", function or "-"])

            sheets_data["전성분 합계"] = {
                "type": "table", 
                "content": {
                    "headers": summed_headers, 
                    "data": summed_data,
                    "number_formats": {
                        "총 함량(%)": f'0.{"0"*max_dp_total_ratio}' if max_dp_total_ratio > 0 else '0'
                    }
                }}

        # 2. 전성분 합계 데이터 추출
        # extract_tree_data(self.summed_ingredient_tree, "전성분 합계") # [삭제] 위에서 직접 생성하는 로직으로 대체

        # 3. 단일 전성분 데이터 추출 (국문/영문 분리)
        summed_ingredients = {}
        session = db_manager.get_session()
        try:
            formulation_items = session.query(FormulationItem).filter_by(formulation_id=self._selected_formulation_id).all()
            for item in formulation_items:
                if not item.material_code or item.material_code == "---" or item.ratio is None: continue
                material = session.query(Material).filter_by(code=item.material_code).first()
                if material and material.ingredients:
                    item_ratio_dec = to_decimal(item.ratio)
                    for ing in material.ingredients:
                        ing_comp_ratio_dec = to_decimal(ing.composition_ratio)
                        actual_ratio = item_ratio_dec * (ing_comp_ratio_dec / Decimal('100'))
                        key = (ing.name_ko or "", ing.name_en or "")
                        if key not in summed_ingredients:
                            summed_ingredients[key] = {
                                'total_ratio': 0,
                                'cas_no': ing.cas_no or "", 'function': ing.function or "",
                                'hs_code': ing.hs_code or "", 'nmpa_reg_num': ing.nmpa_reg_num or "", 'remark': ing.remark or ""
                            }
                        summed_ingredients[key]['total_ratio'] += actual_ratio
        finally:
            session.close()

        if summed_ingredients:
            sorted_ingredients = sorted(summed_ingredients.items(), key=lambda x: x[1]['total_ratio'], reverse=True)
            
            # 최대 소수점 자릿수 계산
            max_dp_total_ratio = 0
            # [수정] 단일 전성분 목록에 대한 최대 소수점 자릿수 계산 로직 추가
            for _, data in sorted_ingredients:
                ratio_val = data.get('total_ratio')
                if isinstance(ratio_val, Decimal):
                    max_dp_total_ratio = max(max_dp_total_ratio, -ratio_val.as_tuple().exponent)

            # 국문 시트 데이터
            ko_headers = ["NO", "성분명", "% (W/W)", "CAS. NO", "FUNCTION"]
            ko_data = []
            for i, ((name_ko, _), data) in enumerate(sorted_ingredients, 1):
                ko_data.append([i, name_ko, data['total_ratio'], data.get('cas_no') or "-", data.get('function') or "-"])
            sheets_data[self.texts['single_ingredients_korean']] = {
                "type": "table", 
                "content": {
                    "headers": ko_headers, 
                    "data": ko_data,
                    "number_formats": {
                        "% (W/W)": f'0.{"0"*max_dp_total_ratio}' if max_dp_total_ratio > 0 else '0'
                    }
                }}

            # 영문 시트 데이터
            en_headers = ["NO", "INGREDIENT", "% (W/W)", "CAS. NO", "FUNCTION"]
            en_data = []
            for i, ((_, name_en), data) in enumerate(sorted_ingredients, 1):
                en_data.append([i, name_en, data['total_ratio'], data.get('cas_no') or "-", data.get('function') or "-"])
            sheets_data[self.texts['single_ingredients_english']] = {
                "type": "table", 
                "content": {
                    "headers": en_headers, 
                    "data": en_data,
                    "number_formats": {
                        "% (W/W)": f'0.{"0"*max_dp_total_ratio}' if max_dp_total_ratio > 0 else '0'
                    }
                }}


        # 4. 디자인용 전성분 데이터 추출
        ko_text = self.design_ko_textbox.get("1.0", "end-1c").strip()
        en_text = self.design_en_textbox.get("1.0", "end-1c").strip()
        if ko_text and self.texts['press_button_placeholder'] not in ko_text:
            design_headers = ["구분", "전성분 목록"]
            design_data = [
                ("국문:", ko_text),
                ("영문 (INCI):", en_text)
            ]
            # 'table' 형식으로 데이터를 구성하여 전달합니다.
            sheets_data[self.texts['ingredients_for_design']] = {"type": "table", "content": {"headers": design_headers, "data": design_data}}

        if not sheets_data:
            messagebox.showwarning(self.texts['export_error'], self.texts['no_data_to_export_create_list'], parent=self)
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
        
        label = ctk.CTkLabel(tab_frame, text=f"{tab_name}\n{self.texts['dev_in_progress']}", font=ctk.CTkFont(size=20, weight="bold"))
        label.grid(row=0, column=0, padx=20, pady=20)

    def clear_functional_report_form(self):
        """기능성 보고서 폼의 모든 내용을 초기화합니다."""
        for key, widget in self.report_entries.items():
            if key == "효능·효과":
                for var in widget.values():
                    var.set(False)
            elif isinstance(widget, ctk.CTkComboBox):
                widget.set(widget.cget("values")[0])
            elif isinstance(widget, ctk.CTkTextbox):
                widget.delete("1.0", "end")
            else:
                widget.delete(0, "end")
        # 용법/용량 기본값 재설정
        self.report_entries["용법·용량"].insert("1.0", self.texts['usage_default'])
        self.report_entries["사용할 때의 주의사항"].insert("1.0", self.texts['precautions_default'])
        self.report_entries["활성물질용량"].insert("1.0", self.texts['active_substance_default'])
        self.report_entries["원료성분 및 배합비율"].insert("1.0", self.texts['ingredients_ratio_default'])

    def export_functional_report(self):
        """폼에 입력된 데이터를 엑셀 보고서로 내보냅니다."""
        report_data = {}
        for key, widget in self.report_entries.items():
            if key == "효능·효과":
                selected_effects = [effect for effect, var in widget.items() if var.get()]
                report_data[key] = ", ".join(selected_effects)
            elif isinstance(widget, ctk.CTkTextbox):
                report_data[key] = widget.get("1.0", "end-1c")
            else:
                report_data[key] = widget.get()
        excel_handler.export_functional_cosmetics_report_template(report_data)

    def setup_functional_report_tab(self, tab_frame):
        """기능성 보고/참고 자료 탭의 UI를 COA 반제품 템플릿과 유사하게 재구성합니다."""
        tab_frame.grid_columnconfigure(0, weight=1)
        tab_frame.grid_rowconfigure(1, weight=1) # 스크롤 프레임

        # --- 상단 버튼 프레임 ---
        top_button_frame = ctk.CTkFrame(tab_frame, fg_color="transparent")
        top_button_frame.grid(row=0, column=0, padx=10, pady=10, sticky="e")
        ctk.CTkButton(top_button_frame, text=self.texts['export_report'], command=self.export_functional_report).pack(side="left", padx=5)
        ctk.CTkButton(top_button_frame, text=self.texts['reset'], command=self.clear_functional_report_form, fg_color="gray50", hover_color="gray35").pack(side="left", padx=5)

        # --- 스크롤 가능한 메인 프레임 ---
        scrollable_frame = ctk.CTkScrollableFrame(tab_frame, label_text=self.texts['functional_report_title'])
        scrollable_frame.grid(row=1, column=0, padx=10, pady=(0, 10), sticky="nsew")
        scrollable_frame.grid_columnconfigure(0, weight=1)

        self.report_entries = {}

        # --- 기본 정보 섹션 ---
        info_frame = ctk.CTkFrame(scrollable_frame)
        info_frame.grid(row=0, column=0, sticky="ew", padx=10, pady=(10, 20))
        info_frame.grid_columnconfigure((1, 3), weight=1)

        info_fields = [
            ("제출유형", ["1호 (고시품목)", "2호 (심사품목)", "3호 (혼합)"], "combo", 0, 0),
            ("업체명", "", "entry", 0, 2),
            ("책임판매업자", "", "entry", 1, 0),
            ("제조원", "", "entry", 1, 2),
            ("제품명(국문)", "", "entry", 2, 0),
            ("제품명(영문)", "", "entry", 2, 2),
            ("제형", ["액제", "로션", "크림", "에센스", "쿠션", "에어로졸"], "combo", 3, 0),
            ("자외선 관련 (SPF / PA)", "", "entry", 3, 2),
            ("pH (실측값)", "", "entry", 4, 0),
            ("이미 심사받은 품목", "", "entry", 4, 2),
            ("고시한 기준 및 시험방법", "", "entry", 5, 0, 3), # 3칸 병합
        ]

        for field_info in info_fields:
            label_text, options, widget_type, r, c = field_info[:5]
            colspan = field_info[5] if len(field_info) > 5 else 1

            label = ctk.CTkLabel(info_frame, text=label_text, font=ctk.CTkFont(weight="bold"))
            label.grid(row=r, column=c, padx=10, pady=5, sticky="w")
            
            if widget_type == "combo":
                widget = ctk.CTkComboBox(info_frame, values=options)
                widget.set(options[0])
            else:
                widget = ctk.CTkEntry(info_frame)

            widget.grid(row=r, column=c + 1, columnspan=colspan, padx=10, pady=5, sticky="ew")
            self.report_entries[label_text] = widget

        # --- 효능·효과 섹션 ---
        effects_frame = ctk.CTkFrame(scrollable_frame)
        effects_frame.grid(row=1, column=0, sticky="ew", padx=10, pady=10)
        effects_frame.grid_columnconfigure(0, weight=1)
        ctk.CTkLabel(effects_frame, text="효능·효과", font=ctk.CTkFont(weight="bold")).pack(anchor="w", padx=10, pady=(5,0))
        
        effects_checkbox_frame = ctk.CTkFrame(effects_frame, fg_color="transparent")
        effects_checkbox_frame.pack(fill="x", padx=10, pady=5)
        
        effects_options = ["자외선차단", "미백", "주름개선", "탈모증상 완화", "여드름성 피부 완화"]
        effects_widget = {}
        for option_text in effects_options:
            var = ctk.BooleanVar()
            chk = ctk.CTkCheckBox(effects_checkbox_frame, text=option_text, variable=var)
            chk.pack(side="left", padx=(0, 15))
            effects_widget[option_text] = var
        self.report_entries["효능·효과"] = effects_widget

        # --- 상세 설명 섹션 ---
        details_frame = ctk.CTkFrame(scrollable_frame)
        details_frame.grid(row=2, column=0, sticky="ew", padx=10, pady=10)
        details_frame.grid_columnconfigure(1, weight=1)

        textbox_fields = [
            ("활성물질용량", "예시:\n총 에칠헥실트리아존으로서 4.00그램\n총 폴리실리콘-15로서 3.00그램", 0),
            ("용법·용량", self.texts['usage_default'], 1),
            ("사용할 때의 주의사항", self.texts['precautions_default'], 2),
            ("원료성분 및 배합비율", self.texts['ingredients_ratio_default'], 3),
        ]

        for label_text, default_value, r in textbox_fields:
            label = ctk.CTkLabel(details_frame, text=label_text, font=ctk.CTkFont(weight="bold"))
            label.grid(row=r, column=0, padx=10, pady=10, sticky="nw")
            widget = ctk.CTkTextbox(details_frame, height=80)
            widget.insert("1.0", default_value)
            widget.grid(row=r, column=1, padx=10, pady=10, sticky="ew")
            self.report_entries[label_text] = widget

    def setup_lab_journal_tab(self, tab_frame):
        """물성치 및 실험일지 탭의 UI를 설정합니다."""
        tab_frame.grid_columnconfigure(0, weight=1)
        tab_frame.grid_rowconfigure(1, weight=1)
        
        # --- 필터 프레임 ---
        filter_frame = ctk.CTkFrame(tab_frame, fg_color="transparent")
        filter_frame.grid(row=0, column=0, padx=10, pady=10, sticky="ew")
        filter_frame.grid_columnconfigure(6, weight=1) # 오른쪽 정렬을 위한 빈 공간
        
        current_year = datetime.now().year
        years = [str(y) for y in range(current_year - 5, current_year + 2)]
        months = [f"{m:02d}" for m in range(1, 13)]
        
        # --- 조회 기간 필터 ---
        self.journal_use_date_filter_var = ctk.BooleanVar()
        self.journal_date_filter_checkbox = ctk.CTkCheckBox(
            filter_frame, text=self.texts['use_date_filter'], 
            variable=self.journal_use_date_filter_var,
            command=self.on_toggle_date_filter
        )
        self.journal_date_filter_checkbox.grid(row=0, column=0, padx=(0, 10))

        self.journal_year_combo = ctk.CTkComboBox(filter_frame, values=years, width=100, command=self.load_lab_journal)
        self.journal_year_combo.set(str(current_year))
        self.journal_year_combo.grid(row=0, column=1, padx=5)
        ctk.CTkLabel(filter_frame, text=self.texts['year']).grid(row=0, column=2)
        
        self.journal_month_combo = ctk.CTkComboBox(filter_frame, values=months, width=80, command=self.load_lab_journal)
        self.journal_month_combo.set(f"{datetime.now().month:02d}")
        self.journal_month_combo.grid(row=0, column=3, padx=5)
        ctk.CTkLabel(filter_frame, text=self.texts['month']).grid(row=0, column=4)
        
        # --- 상세 검색 프레임 ---
        search_frame = ctk.CTkFrame(filter_frame, fg_color="transparent")
        search_frame.grid(row=0, column=5, padx=(20, 0))

        ctk.CTkLabel(search_frame, text=self.texts['detailed_search']).pack(side="left")
        
        self.journal_search_field_combo = ctk.CTkComboBox(
            search_frame, 
            values=self.texts['journal_search_fields'],
            width=100
        )
        self.journal_search_field_combo.set(self.texts['journal_search_fields'][0])
        self.journal_search_field_combo.pack(side="left", padx=5)

        self.journal_search_entry = ctk.CTkEntry(search_frame, placeholder_text=self.texts['enter_search_term'])
        self.journal_search_entry.pack(side="left", padx=5, fill="x", expand=True)
        self.journal_search_entry.bind("<Return>", self.load_lab_journal)

        ctk.CTkButton(search_frame, text=self.texts['search'], width=60, command=self.load_lab_journal).pack(side="left", padx=5)

        # --- 우측 버튼 프레임 ---
        right_button_frame = ctk.CTkFrame(filter_frame, fg_color="transparent")
        right_button_frame.grid(row=0, column=7, sticky="e")
        ctk.CTkButton(right_button_frame, text=self.texts['export_data'], command=self.export_lab_journal_data).pack(side="left", padx=5)
        if self.current_user.is_admin:
            self.journal_import_button = ctk.CTkButton(right_button_frame, text=self.texts['import_data'], command=self.import_lab_journal_data)
            self.journal_import_button.pack(side="left", padx=5)

        # --- 실험일지 Treeview ---
        journal_cols = self.texts['journal_tree_columns']
        self.journal_tree = ttk.Treeview(tab_frame, columns=list(journal_cols.keys()), show="headings", selectmode="browse")
        
        self.journal_tree.heading("date", text="실험 날짜"); self.journal_tree.column("date", width=100, anchor="center")
        self.journal_tree.heading("name", text="품명"); self.journal_tree.column("name", width=200)
        self.journal_tree.heading("ph", text="pH"); self.journal_tree.column("ph", width=120, anchor="center")
        self.journal_tree.heading("viscosity", text="점도"); self.journal_tree.column("viscosity", width=120, anchor="center")
        self.journal_tree.heading("gravity", text="비중"); self.journal_tree.column("gravity", width=80, anchor="center")
        self.journal_tree.heading("pin", text="Pin"); self.journal_tree.column("pin", width=100)
        self.journal_tree.heading("lab_no", text="실험번호"); self.journal_tree.column("lab_no", width=120)
        self.journal_tree.heading("client", text="업체"); self.journal_tree.column("client", width=150)
        self.journal_tree.heading("sample_delivery", text="샘플 전달"); self.journal_tree.column("sample_delivery", width=100, anchor="center")
        self.journal_tree.heading("comment", text="기타"); self.journal_tree.column("comment", width=200, stretch=True)
        
        self.journal_tree.grid(row=1, column=0, sticky="nsew", padx=10, pady=(0, 10))
        self.journal_tree.bind("<Double-1>", self.edit_journal_comment)

        # 스크롤바
        v_scroll = ttk.Scrollbar(tab_frame, orient="vertical", command=self.journal_tree.yview)
        self.journal_tree.configure(yscrollcommand=v_scroll.set)
        v_scroll.grid(row=1, column=1, sticky="ns", pady=(0, 10))
        h_scroll = ttk.Scrollbar(tab_frame, orient="horizontal", command=self.journal_tree.xview)
        self.journal_tree.configure(xscrollcommand=h_scroll.set)
        h_scroll.grid(row=2, column=0, sticky="ew", padx=10, pady=(0, 10))

        self.load_lab_journal() # 초기 데이터 로드
        self.load_journal_settings() # 저장된 설정 불러오기

    def on_toggle_date_filter(self):
        """조회 기간 체크박스 상태에 따라 연/월 콤보박스를 활성화/비활성화합니다."""
        if self.journal_use_date_filter_var.get():
            self.journal_year_combo.configure(state="normal")
            self.journal_month_combo.configure(state="normal")
        else:
            self.journal_year_combo.configure(state="disabled")
            self.journal_month_combo.configure(state="disabled")
        self.load_lab_journal()

    def load_journal_settings(self):
        """config.ini에서 실험일지 탭의 필터 설정을 불러옵니다."""
        section = f"JournalFilter_{self.current_user.username}"
        use_date_filter = self.app.get_config_value(section, 'use_date_filter', 'true').lower() == 'true'
        self.journal_use_date_filter_var.set(use_date_filter)

        year = self.app.get_config_value(section, 'year', str(datetime.now().year))
        month = self.app.get_config_value(section, 'month', f"{datetime.now().month:02d}")
        self.journal_year_combo.set(year)
        self.journal_month_combo.set(month)

        search_field = self.app.get_config_value(section, 'search_field', '전체')
        search_term = self.app.get_config_value(section, 'search_term', '')
        self.journal_search_field_combo.set(search_field)
        self.journal_search_entry.delete(0, "end"); self.journal_search_entry.insert(0, search_term)

        self.on_toggle_date_filter() # UI 상태 업데이트 및 데이터 로드

    def save_journal_settings(self, config):
        """현재 실험일지 탭의 필터 설정을 config.ini에 저장합니다."""
        section = f"JournalFilter_{self.current_user.username}"
        if not config.has_section(section): config.add_section(section)
        config.set(section, 'use_date_filter', str(self.journal_use_date_filter_var.get()))
        config.set(section, 'year', self.journal_year_combo.get())
        config.set(section, 'month', self.journal_month_combo.get())
        config.set(section, 'search_field', self.journal_search_field_combo.get())
        config.set(section, 'search_term', self.journal_search_entry.get())
        
    def export_lab_journal_data(self):
        """현재 실험일지 목록을 서식이 적용된 엑셀 파일로 내보냅니다."""
        if not self.journal_tree.get_children():
            messagebox.showwarning("내보내기 오류", "내보낼 데이터가 없습니다.", parent=self)
            return

        year = self.journal_year_combo.get()
        month = self.journal_month_combo.get()

        # export_formulation_template 함수 형식에 맞게 데이터 구조화
        journal_data = {
            "details": {
                "실험품명": f"{year}년 {month}월 실험일지",
                "실험년월일": datetime.now().strftime('%Y-%m-%d'),
                "담당자": self.current_user.username,
                "LAB NO.": "", # 실험일지는 특정 LAB NO.가 아니므로 비워둠
            },
            "items": [
                {
                    "실험 날짜": values[0],
                    "품명": values[1],
                    "pH": values[2],
                    "점도": values[3],
                    "비중": values[4],
                    "Pin": values[5],
                    "실험번호": values[6],
                    "업체": values[7],
                    "샘플 전달": values[8],
                    "기타": values[9]
                }
                for values in (self.journal_tree.item(item, "values") for item in self.journal_tree.get_children())
            ]
        }
        
        default_filename = "실험일지.xlsx"
        # 기존의 서식 적용 함수(export_formulation_template)를 재사용하여 내보냅니다.
        # is_lab_journal 플래그를 추가하여 실험일지용 헤더를 사용하도록 합니다.
        excel_handler.export_formulation_template(journal_data, default_filename, is_lab_journal=True)

    def import_lab_journal_data(self):
        """엑셀 파일에서 실험일지 데이터를 가져와 DB에 업데이트/추가합니다."""
        if not messagebox.askyesno(self.texts['import_confirm'], self.texts['import_journal_confirm_msg'], parent=self):
            return

        data = excel_handler.import_data()
        if not data:
            return

        session = db_manager.get_session()
        try:
            updated_count = 0
            added_count = 0
            for row in data:
                lab_no = row.get("실험번호") or row.get("lab_no")
                if not lab_no:
                    continue

                formulation = session.query(Formulation).filter_by(lab_no=lab_no).first()
                if not formulation:
                    formulation = Formulation(lab_no=lab_no)
                    session.add(formulation)
                    added_count += 1
                else:
                    updated_count += 1

                # 데이터 매핑
                date_str = row.get("실험 날짜") or row.get("date")
                if date_str:
                    try:
                        formulation.experiment_date = datetime.strptime(date_str, '%Y-%m-%d').date()
                    except (ValueError, TypeError):
                        pass # 날짜 형식이 잘못된 경우 무시
                
                formulation.experiment_name = row.get("품명") or row.get("name")
                formulation.experiment_comment = row.get("기타") or row.get("comment")
                
                # pH, 점도 값 파싱 (예: "8.5/8.4" -> initial/next_day)
                ph_val = row.get("pH") or row.get("ph", "")
                if '/' in ph_val:
                    formulation.experiment_ph_initial, formulation.experiment_ph_next_day = ph_val.split('/', 1)
                
                viscosity_val = row.get("점도") or row.get("viscosity", "")
                if '/' in viscosity_val:
                    formulation.experiment_viscosity_initial, formulation.experiment_viscosity_next_day = viscosity_val.split('/', 1)

            session.commit()
            messagebox.showinfo(self.texts['success'], self.texts['import_journal_success_msg'].format(added=added_count, updated=updated_count), parent=self)
        except Exception as e:
            session.rollback()
            messagebox.showerror(self.texts['db_error'], f"{self.texts['import_error_msg']}: {e}", parent=self)
        finally:
            session.close()
            self.load_lab_journal() # 목록 새로고침

    def load_lab_journal(self, event=None):
        """선택된 연/월에 해당하는 실험일지 데이터를 불러옵니다."""
        for item in self.journal_tree.get_children():
            self.journal_tree.delete(item)

        year = int(self.journal_year_combo.get())
        month = int(self.journal_month_combo.get())

        session = db_manager.get_session()
        try:
            from sqlalchemy import or_
            query = session.query(Formulation)

            # '조회 기간 사용'이 체크된 경우에만 날짜 필터 적용
            if self.journal_use_date_filter_var.get():
                date_pattern = f"{year}-{month:02d}-%"
                query = query.filter(Formulation.experiment_date.like(date_pattern))

            # 상세 검색 조건 추가
            search_field = self.journal_search_field_combo.get()
            search_term = self.journal_search_entry.get().strip()

            if search_term:
                search_pattern = f"%{search_term}%"
                if search_field == "전체":
                    query = query.join(Formulation.oem_odm_client, isouter=True).filter(
                        or_(
                            Formulation.experiment_name.ilike(search_pattern),
                            Formulation.experiment_ph_initial.ilike(search_pattern),
                            Formulation.experiment_ph_next_day.ilike(search_pattern),
                            Formulation.experiment_viscosity_initial.ilike(search_pattern),
                            Formulation.experiment_viscosity_next_day.ilike(search_pattern),
                            Formulation.experiment_machine.ilike(search_pattern),
                            Formulation.lab_no.ilike(search_pattern),
                            Client.name.ilike(search_pattern)
                        )
                    )
                elif search_field == "품명":
                    query = query.filter(Formulation.experiment_name.ilike(search_pattern))
                elif search_field == "pH":
                    query = query.filter(or_(Formulation.experiment_ph_initial.ilike(search_pattern), Formulation.experiment_ph_next_day.ilike(search_pattern)))
                elif search_field == "점도":
                    query = query.filter(or_(Formulation.experiment_viscosity_initial.ilike(search_pattern), Formulation.experiment_viscosity_next_day.ilike(search_pattern)))
                elif search_field == "Pin":
                    query = query.filter(Formulation.experiment_machine.ilike(search_pattern))
                elif search_field == "실험번호":
                    query = query.filter(Formulation.lab_no.ilike(search_pattern))
                elif search_field == "업체":
                    query = query.join(Formulation.oem_odm_client).filter(Client.name.ilike(search_pattern))

            journals = query.order_by(Formulation.experiment_date).all()
            
            for i, form in enumerate(journals):
                ph = f"{form.experiment_ph_initial or '-'}/{form.experiment_ph_next_day or '-'}"
                viscosity = f"{form.experiment_viscosity_initial or '-'}/{form.experiment_viscosity_next_day or '-'}"
                client_name = form.oem_odm_client.name if form.oem_odm_client else ""
                
                # 샘플 전달 정보 표시 (횟수 / 날짜)
                sample_delivery = ""
                if form.sample_sent_count > 0:
                    # sample_delivery_date 속성이 존재하고, 값이 None이 아닌지 확인
                    delivery_date = getattr(form, 'sample_delivery_date', None)
                    date_part = delivery_date.strftime('%Y-%m-%d') if delivery_date else self.texts['no_date']
                    sample_delivery = f"{form.sample_sent_count}회 / {date_part}"

                # experiment_date가 문자열로 저장된 경우를 대비한 방어 코드
                date_str = ""
                if isinstance(form.experiment_date, (datetime, date)):
                    date_str = form.experiment_date.strftime('%Y-%m-%d')
                elif isinstance(form.experiment_date, str):
                    date_str = form.experiment_date

                tag = 'oddrow' if i % 2 == 0 else 'evenrow'
                self.journal_tree.insert("", "end", iid=form.id, tags=(tag,), values=(
                    date_str,
                    form.experiment_name,
                    ph,
                    viscosity,
                    "-", # 비중은 아직 모델에 없음
                    form.experiment_machine,
                    form.lab_no,
                    client_name,
                    sample_delivery,
                    form.experiment_comment
                ))
        finally:
            session.close()

    def edit_journal_comment(self, event):
        """실험일지 '기타' 항목을 수정하는 다이얼로그를 엽니다."""
        region = self.journal_tree.identify("region", event.x, event.y)
        if region != "cell" or self.journal_tree.identify_column(event.x) != "#10": # '기타' 컬럼
            return

        selected_item_id = self.journal_tree.focus()
        if not selected_item_id:
            return

        current_comment = self.journal_tree.item(selected_item_id, "values")[9]

        dialog = ctk.CTkInputDialog(
            text=self.texts['enter_comment_to_edit'],
            title=self.texts['edit_comment_title']
        )
        dialog.entry.insert(0, current_comment)
        new_comment = dialog.get_input()

        if new_comment is not None:
            # DB 업데이트
            success = db_manager.update_formulation_field(selected_item_id, 'experiment_comment', new_comment)
            if success:
                # Treeview 업데이트
                current_values = list(self.journal_tree.item(selected_item_id, "values"))
                current_values[9] = new_comment
                self.journal_tree.item(selected_item_id, values=tuple(current_values))
                messagebox.showinfo(self.texts['success'], self.texts['comment_updated_success'], parent=self)
            else:
                messagebox.showerror(self.texts['error'], self.texts['data_update_failed'], parent=self)

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
        all_client_types = [self.texts['select_type']] + db_manager.get_unique_client_types()
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
                ctk.CTkLabel(self.folder_view, text=self.texts['no_formulation_data'], font=ctk.CTkFont(size=16)).pack(pady=50)
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

            date_format = '%Y-%m-%d'
            for i, form in enumerate(formulations):
                tag = 'oddrow' if i % 2 == 0 else 'evenrow'
                # Treeview의 컬럼 순서(date, experiment_name, lab_no, revision, sample_sent, sample_delivery_date)에 맞춰 값 배치
                date_str = form.experiment_date.strftime(date_format) if isinstance(form.experiment_date, (datetime, date)) else form.experiment_date or ""
                exp_name = form.experiment_name or ""
                lab_no = form.lab_no or ""
                revision = form.revision or "N/A"
                sample_sent = f"{form.sample_sent_count:02d}" if (form.sample_sent_count and form.sample_sent_count > 0) else ""
                sample_delivery = form.sample_delivery_date.strftime(date_format) if getattr(form, 'sample_delivery_date', None) else ""

                self.formulation_tree.insert("", "end", iid=form.id, tags=(tag,), values=(
                    date_str,
                    exp_name,
                    lab_no,
                    revision,
                    sample_sent,
                    sample_delivery
                ))
        finally:
            session.close()

    def on_formulation_tree_select(self, event):
        """Treeview에서 처방 선택 시 ID를 저장하고 버튼 상태를 업데이트합니다."""
        selected_items = self.formulation_tree.selection()
        if selected_items:
            # 여러 개가 선택되어도, 단일 선택 기반 기능(수정, 견적 등)을 위해 첫 번째 항목의 ID를 저장합니다.
            first_item_id = selected_items[0]
            if str(first_item_id).isdigit():
                self._selected_formulation_id = int(first_item_id)
            else:
                self._selected_formulation_id = None
        else:
            self._selected_formulation_id = None
        self.update_button_states()

    def get_selected_formulation_ids(self):
        """Treeview에서 선택된 모든 처방의 ID 목록을 반환합니다."""
        selected_ids = []
        selected_items = self.formulation_tree.selection()
        for iid in selected_items:
            if str(iid).isdigit():
                selected_ids.append(int(iid))
        return selected_ids

    def delete_formulation(self):
        """선택된 처방을 삭제합니다."""
        selected_ids = self.get_selected_formulation_ids()
        if not selected_ids:
            messagebox.showwarning(self.texts['selection_error'], self.texts['select_formulation_to_delete'], parent=self)
            return
        
        if not messagebox.askyesno(self.texts['delete_confirm'], self.texts['delete_formulation_confirm_msg'].format(count=len(selected_ids)), parent=self):
            return

        session = db_manager.get_session()
        try:
            # 선택된 모든 ID에 대해 삭제를 수행합니다.
            query = session.query(Formulation).filter(Formulation.id.in_(selected_ids))
            deleted_count = query.delete(synchronize_session=False)
            
            session.commit()
            
            messagebox.showinfo(self.texts['success'], self.texts['delete_formulation_success_msg'].format(count=deleted_count), parent=self)
            self._selected_formulation_id = None # ID 초기화
            self.update_button_states() # 버튼 상태 업데이트
            self.load_formulations()

        except Exception as e:
            session.rollback()
            messagebox.showerror(self.texts['db_error'], f"{self.texts['delete_error_msg']}: {e}", parent=self)
        finally:
            session.close()

    def increment_sample_sent_count(self):
        """선택된 처방의 샘플 발송 횟수를 1 증가시킵니다."""
        # 권한 체크: QC는 변경 불가, 연구권한(RD/RQ/RQD/MSAD)만 가능
        if not getattr(self.current_user, 'has_research_access', None) or not self.current_user.has_research_access():
            messagebox.showwarning("권한 오류", "샘플 발송 정보는 연구권한 사용자만 수정할 수 있습니다.", parent=self)
            return
        if not self._selected_formulation_id:
            messagebox.showwarning(self.texts['selection_error'], self.texts['select_formulation_for_sample'], parent=self)
            return

        if not messagebox.askyesno(self.texts['send_sample_confirm'], self.texts['send_sample_confirm_msg'], parent=self):
            return

        session = db_manager.get_session()
        try:
            formulation = session.query(Formulation).filter_by(id=self._selected_formulation_id).first()
            if formulation:
                formulation.sample_sent_count = (formulation.sample_sent_count or 0) + 1
                formulation.sample_delivery_date = datetime.now().date() # 오늘 날짜로 발송일 업데이트
                session.commit()
                messagebox.showinfo(self.texts['success'], self.texts['sample_count_updated_msg'].format(count=formulation.sample_sent_count), parent=self)

                # 1) 현재 트리뷰(처방 목록)의 해당 행만 즉시 업데이트하여 사용자가 바로 변화를 보도록 함
                selected_iid = str(self._selected_formulation_id)
                if hasattr(self, 'formulation_tree') and self.formulation_tree.exists(selected_iid):
                    current_values = list(self.formulation_tree.item(selected_iid, 'values'))
                    # 컬럼 순서: date, experiment_name, lab_no, revision, sample_sent, sample_delivery_date
                    new_sample_sent = f"{formulation.sample_sent_count:02d}" if (formulation.sample_sent_count and formulation.sample_sent_count > 0) else ""
                    new_sample_date = formulation.sample_delivery_date.strftime('%Y-%m-%d') if getattr(formulation, 'sample_delivery_date', None) else ""
                    # 방어 코드: values 길이 확인
                    while len(current_values) < 6:
                        current_values.append("")
                    current_values[4] = new_sample_sent
                    current_values[5] = new_sample_date
                    self.formulation_tree.item(selected_iid, values=tuple(current_values))

                # 2) 물성치/실험일지 탭도 새로고침하여 '샘플 전달' 컬럼 반영
                if hasattr(self, 'load_lab_journal'):
                    self.load_lab_journal()

                # 3) 앱의 모든 프레임에 데이터 새로고침을 알립니다.
                self.app.refresh_data_in_all_frames()
            else:
                messagebox.showerror(self.texts['error'], self.texts['formulation_not_found'], parent=self)
        except Exception as e:
            session.rollback()
            messagebox.showerror(self.texts['db_error'], f"{self.texts['sample_count_update_error']}: {e}", parent=self)
        finally:
            session.close()

    def edit_sample_sent_count(self):
        """선택된 처방의 샘플 발송 횟수를 사용자가 입력한 값으로 수정합니다."""
        # 권한 체크: QC는 변경 불가, 연구권한(RD/RQ/RQD/MSAD)만 가능
        if not getattr(self.current_user, 'has_research_access', None) or not self.current_user.has_research_access():
            messagebox.showwarning("권한 오류", "샘플 발송 정보는 연구권한 사용자만 수정할 수 있습니다.", parent=self)
            return
        if not self._selected_formulation_id:
            messagebox.showwarning(self.texts['selection_error'], self.texts['select_formulation_to_edit'], parent=self)
            return

        session = db_manager.get_session()
        try:
            formulation = session.query(Formulation).filter_by(id=self._selected_formulation_id).first()
            if not formulation:
                messagebox.showerror(self.texts['error'], self.texts['formulation_not_found'], parent=self)
                return

            dialog = ctk.CTkToplevel(self)
            dialog.title(self.texts['edit_sample_info_title'])
            dialog.transient(self)
            dialog.grab_set()

            main_frame = ctk.CTkFrame(dialog)
            main_frame.pack(padx=20, pady=20)

            ctk.CTkLabel(main_frame, text=f"'{formulation.experiment_name}' ({formulation.lab_no})").pack(pady=(0, 10))

            ctk.CTkLabel(main_frame, text=self.texts['sent_count']).pack(anchor="w", padx=10)
            count_entry = ctk.CTkEntry(main_frame)
            count_entry.insert(0, str(formulation.sample_sent_count or 0))
            count_entry.pack(padx=10, pady=(0, 10), fill="x")

            ctk.CTkLabel(main_frame, text=self.texts['last_sent_date']).pack(anchor="w", padx=10)
            date_entry = ctk.CTkEntry(main_frame)
            if formulation.sample_delivery_date:
                date_entry.insert(0, formulation.sample_delivery_date.strftime('%Y-%m-%d'))
            date_entry.pack(padx=10, pady=(0, 20), fill="x")

            result = {"saved": False}

            def save_and_close():
                try:
                    new_count = int(count_entry.get())
                    new_date_str = date_entry.get().strip()
                    new_date = datetime.strptime(new_date_str, '%Y-%m-%d').date() if new_date_str else None

                    formulation.sample_sent_count = new_count
                    formulation.sample_delivery_date = new_date
                    session.commit()
                    messagebox.showinfo(self.texts['success'], self.texts['sample_info_updated_success'], parent=self)

                    # 즉시 트리뷰(처방 목록) 반영
                    selected_iid = str(self._selected_formulation_id)
                    if hasattr(self, 'formulation_tree') and self.formulation_tree.exists(selected_iid):
                        current_values = list(self.formulation_tree.item(selected_iid, 'values'))
                        while len(current_values) < 6:
                            current_values.append("")
                        current_values[4] = f"{new_count:02d}" if (new_count and new_count > 0) else ""
                        current_values[5] = new_date.strftime('%Y-%m-%d') if new_date else ""
                        self.formulation_tree.item(selected_iid, values=tuple(current_values))

                    # 물성치/실험일지 탭도 새로고침
                    if hasattr(self, 'load_lab_journal'):
                        self.load_lab_journal()

                    # 앱 전역 새로고침
                    self.app.refresh_data_in_all_frames()

                    result["saved"] = True
                    dialog.destroy()
                except ValueError:
                    messagebox.showwarning(self.texts['input_error'], self.texts['invalid_number_date_format'], parent=dialog)
                except Exception as ex:
                    session.rollback()
                    messagebox.showerror(self.texts['db_error'], f"{self.texts['update_error_msg']}: {ex}", parent=dialog)

            def cancel_and_close():
                dialog.destroy()

            button_frame = ctk.CTkFrame(main_frame, fg_color="transparent")
            button_frame.pack(fill="x", pady=(10, 0))

            save_button = ctk.CTkButton(button_frame, text=self.texts['save'], command=save_and_close)
            save_button.pack(side="left", padx=(0, 5), expand=True, fill="x")

            cancel_button = ctk.CTkButton(button_frame, text=self.texts['cancel'], fg_color="gray", command=cancel_and_close)
            cancel_button.pack(side="right", padx=(5, 0), expand=True, fill="x")

            dialog.protocol("WM_DELETE_WINDOW", cancel_and_close)

            dialog.update_idletasks()
            x = self.winfo_x() + (self.winfo_width() // 2) - (dialog.winfo_width() // 2)
            y = self.winfo_y() + (self.winfo_height() // 2) - (dialog.winfo_height() // 2)
            dialog.geometry(f"+{x}+{y}")

            self.wait_window(dialog)

        except Exception as e:
            session.rollback()
            messagebox.showerror(self.texts['db_error'], f"{self.texts['sample_count_edit_error']}: {e}", parent=self)
        finally:
            session.close()
    def import_all_formulations(self):
        """
        관리자 전용: 엑셀(다중 시트) 파일에서 처방들을 가져와 DB에 저장합니다.
        - 기존 데이터와 충돌 시 간단한 중복 방지(예: 동일 LAB NO. 또는 실험일+제품명)가 적용됩니다.
        - 가져온 처방은 experiment_name을 기준으로 폴더로 분류되어 보여집니다.
        """
        if not self.current_user.is_admin:
            messagebox.showwarning("권한 오류", "관리자만 가져오기 기능을 사용할 수 있습니다.", parent=self)
            return

        from modules import excel_handler
        imported = excel_handler.import_multisheet_data()
        if not imported:
            return

        # 우선적으로 export에서 생성한 시트 포맷을 찾습니다:
        # - '처방 목록' 시트: 처방별 한 행(헤더에 'ID','제품명' 포함)
        # - '처방별 원료 목록' 시트: 각 처방의 원료들이 처방ID로 참조됨
        forms_sheet = None
        items_sheet = None
        for sname, rows in imported.items():
            if not rows:
                continue
            keys = set()
            # rows는 dict 리스트이므로 keys를 합칩니다.
            for r in rows[:3]:
                keys.update(r.keys())
            keys_norm = {str(k).strip() for k in keys}
            if {'ID', '제품명'} <= keys_norm or {'ID', 'Experiment Name'} <= keys_norm or {'ID', '실험품명'} <= keys_norm:
                forms_sheet = (sname, rows)
            if {'처방ID', '원료명'} <= keys_norm or {'처방ID', '원료코드'} <= keys_norm:
                items_sheet = (sname, rows)

        # 만약 위 표준 포맷이 아니라면 기존 generic 파싱으로 fallback (기존 동작 유지)
        session = db_manager.get_session()
        try:
            if forms_sheet and items_sheet:
                form_rows = forms_sheet[1]
                item_rows = items_sheet[1]

                orig_to_new = {}
                added = 0
                # 먼저 처방 생성
                for row in form_rows:
                    try:
                        orig_id = row.get('ID') or row.get('id')
                        exp_name = row.get('제품명') or row.get('실험품명') or row.get('Experiment Name') or ''
                        lab_no = row.get('LAB NO.') or row.get('Lab No') or row.get('LAB_NO') or row.get('LAB') or None
                        date_str = row.get('실험일') or row.get('Date') or None
                        sample_sent = row.get('샘플 발송 횟수') or row.get('sample_sent_count') or None
                        sample_delivery = row.get('샘플 발송일') or row.get('sample_delivery_date') or None
                        manager = row.get('담당자') or row.get('manager') or None
                        # 담당번호(manager_code) 매핑: 다양한 헤더 이름을 시도
                        manager_code_val = row.get('담당번호') or row.get('담당 번호') or row.get('manager_code') or row.get('Manager Code') or row.get('문서 번호') or None
                        comment = row.get('비고') or row.get('remark') or None
                        # 차수(revision) 필드 매핑: 다양한 헤더 이름을 시도
                        revision = row.get('차수') or row.get('revision') or row.get('Revision') or row.get('rev') or None

                        f = Formulation(
                            experiment_name=exp_name or f'Imported_{orig_id}',
                            experiment_date=date_str,
                            lab_no=str(lab_no) if lab_no is not None else None,
                            manager_name=manager,
                            manager_code=str(manager_code_val).strip().upper() if manager_code_val is not None else None,
                            revision=str(revision) if revision is not None else None,
                            experiment_comment=comment,
                        )
                        if sample_sent is not None:
                            try:
                                f.sample_sent_count = int(sample_sent)
                            except Exception:
                                pass
                        # sample_delivery may be ISO date string
                        if sample_delivery:
                            try:
                                from datetime import date as _date
                                f.sample_delivery_date = _date.fromisoformat(sample_delivery)
                            except Exception:
                                pass

                        session.add(f)
                        session.flush()
                        orig_to_new[str(orig_id)] = f.id
                        added += 1
                    except Exception:
                        session.rollback()
                        continue

                # 다음으로 원료 항목들을 원래 처방ID에 매핑하여 생성
                for irow in item_rows:
                    try:
                        parent_orig = irow.get('처방ID') or irow.get('처방 Id') or irow.get('FormulationID') or irow.get('Formulation Id') or irow.get('처방 Id')
                        if parent_orig is None:
                            continue
                        parent_new_id = orig_to_new.get(str(parent_orig))
                        if not parent_new_id:
                            continue

                        order = irow.get('순번') or irow.get('order') or None
                        # order가 문자열로 들어올 수 있으므로 int로 변환 시도
                        if order is not None:
                            try:
                                order = int(float(order))
                            except Exception:
                                # 변환 불가 시 None으로 두어 정렬 시 뒤로 오게 함
                                order = None
                        phase = irow.get('구분') or irow.get('phase') or None
                        mat_code = irow.get('원료코드') or irow.get('원료 코드') or irow.get('원료코드') or irow.get('코드') or None
                        mat_name = irow.get('원료명') or irow.get('원료 명') or irow.get('원료명') or irow.get('원료명') or irow.get('원료명') or irow.get('원료명') or irow.get('원료명') or irow.get('원료명') or irow.get('원료명') or irow.get('원료명') or irow.get('원료명') or irow.get('원료명') or irow.get('원료명')
                        mat_name = mat_name or irow.get('원료명') or irow.get('material_name') or irow.get('name') or None
                        ratio = try_convert_to_float(irow.get('함량(%)') or irow.get('함량') or irow.get('%') or irow.get('ratio') or 0) or 0
                        amount = try_convert_to_float(irow.get('중량') or irow.get('실험량(g)') or irow.get('amount') or 0) or 0

                        fi = FormulationItem(
                            formulation_id=parent_new_id,
                            order=order,
                            phase=phase,
                            material_code=mat_code,
                            material_name=mat_name,
                            ratio=ratio,
                            amount=amount
                        )
                        session.add(fi)
                    except Exception:
                        continue

                session.commit()
                messagebox.showinfo(self.texts['success'], f"{added}개의 처방을 가져왔습니다.")
                self.load_folders(is_initial_load=True)
                return
            else:
                # 표준 포맷을 찾지 못하면 기존 generic 동작 (한 행 당 처방)로 처리
                added = 0
                updated = 0
                for sheet_name, rows in imported.items():
                    for row in rows:
                        exp_name = row.get('제품명') or row.get('실험품명') or row.get('Experiment Name') or sheet_name
                        lab_no = row.get('LAB NO.') or row.get('Lab No') or None
                        date_str = row.get('실험일') or row.get('Date') or None

                        existing = None
                        if lab_no:
                            existing = session.query(Formulation).filter_by(lab_no=str(lab_no)).first()

                        if existing:
                            existing.experiment_name = exp_name
                            existing.experiment_date = date_str
                            existing.manager_name = row.get('담당자') or existing.manager_name
                            # 기존 레코드에 담당번호가 있다면 업데이트
                            manager_code_val = row.get('담당번호') or row.get('담당 번호') or row.get('manager_code') or row.get('문서 번호') or None
                            if manager_code_val is not None:
                                existing.manager_code = str(manager_code_val).strip().upper()
                            updated += 1
                        else:
                            manager_code_val = row.get('담당번호') or row.get('담당 번호') or row.get('manager_code') or row.get('문서 번호') or None
                            newf = Formulation(
                                experiment_name=exp_name or 'Imported',
                                experiment_date=date_str,
                                lab_no=lab_no,
                                manager_name=row.get('담당자') or None,
                                manager_code=str(manager_code_val).strip().upper() if manager_code_val is not None else None,
                                experiment_comment=row.get('비고') or None
                            )
                            session.add(newf)
                            session.flush()
                            added += 1
                            if any(k in row for k in ('원료코드', '원료명', '함량(%)', '코드', 'name', 'ratio')):
                                try:
                                    fi = FormulationItem(
                                        formulation_id=newf.id,
                                        material_code=row.get('원료코드') or row.get('코드') or None,
                                        material_name=row.get('원료명') or row.get('name') or None,
                                        ratio=try_convert_to_float(row.get('함량(%)') or row.get('ratio') or 0) or 0,
                                        amount=try_convert_to_float(row.get('실험량(g)') or row.get('amount') or 0) or 0,
                                        phase=row.get('구분') or row.get('phase') or None,
                                        order=row.get('순번') or None
                                    )
                                    session.add(fi)
                                except Exception:
                                    pass

                session.commit()
                messagebox.showinfo(self.texts['success'], f"가져오기 완료: 추가 {added}개, 업데이트 {updated}개")
                self.load_folders(is_initial_load=True)
                return
        except Exception as e:
            session.rollback()
            messagebox.showerror(self.texts['db_error'], f"가져오기 중 오류: {e}", parent=self)
        finally:
            session.close()

    def export_change_logs(self):
        """
        전체 이력을 엑셀로 내보냅니다. 엔티티별로 시트를 생성하고, 각 시트에는 (Entity, ID, Identifier, Changed At, User, Summary, Full Log) 열을 둡니다.
        """
        if not self.current_user.is_admin:
            messagebox.showwarning("권한 오류", "관리자만 이력 내보내기를 사용할 수 있습니다.", parent=self)
            return

        session = db_manager.get_session()
        try:
            # 수집 대상 엔티티: Formulation, FormulationItem, Material, Client, User
            sheets = {}

            # Helper: split change_log into blocks and extract first line timestamp if present
            def summarize_log(log_text, entity_type=""):
                if not log_text:
                    return ("", "", "")
                blocks = [b.strip() for b in str(log_text).split('\n\n') if b.strip()]
                # 원료, 거래처의 경우 '신규 생성' 로그는 제외
                if entity_type in ["원료", "거래처"]:
                    blocks = [b for b in blocks if "신규 생성" not in b]

                full = "\n\n".join(blocks)
                summary = blocks[0] if blocks else ""
                # try to parse leading [YYYY-MM-DD HH:MM] pattern
                import re
                m = re.match(r'^\[(\d{4}-\d{2}-\d{2} \d{2}:\d{2})\]\s*(.*)$', summary)
                if m:
                    changed_at = m.group(1)
                    summary_text = m.group(2)
                else:
                    changed_at = ""
                    summary_text = summary
                return (changed_at, summary_text, full)

            # Formulations
            form_rows = []
            forms = session.query(Formulation).order_by(Formulation.created_at).all()
            for f in forms:
                changed_at, summary_text, full = summarize_log(f.change_log, "처방")
                # 변경 이력이 있는 경우만 추가
                if full and summary_text:
                    identifier = f.lab_no or f.experiment_name
                    form_rows.append(("처방", f.id, identifier, changed_at, f.manager_name or "", summary_text, full))
            if form_rows:  # 데이터가 있을 때만 시트 추가
                sheets['처방'] = {'headers': ["엔티티", "ID", "식별자", "변경일", "사용자", "요약", "전체 이력"], 'data': form_rows, 'style': True}

            # Materials
            mat_rows = []
            mats = session.query(Material).order_by(Material.id).all()
            for m in mats:
                changed_at, summary_text, full = summarize_log(m.change_log, "원료")
                # 변경 이력이 있는 경우만 추가
                if full and summary_text:
                    identifier = m.code or m.name
                    mat_rows.append(("원료", m.id, identifier, changed_at, "", summary_text, full))
            if mat_rows:  # 데이터가 있을 때만 시트 추가
                sheets['원료'] = {'headers': ["엔티티", "ID", "식별자", "변경일", "사용자", "요약", "전체 이력"], 'data': mat_rows, 'style': True}

            # Clients
            client_rows = []
            clients = session.query(Client).order_by(Client.id).all()
            for c in clients:
                changed_at, summary_text, full = summarize_log(c.change_log, "거래처")
                # 변경 이력이 있는 경우만 추가
                if full and summary_text:
                    identifier = c.name
                    client_rows.append(("거래처", c.id, identifier, changed_at, c.manager_name or "", summary_text, full))
            if client_rows:  # 데이터가 있을 때만 시트 추가
                sheets['거래처'] = {'headers': ["엔티티", "ID", "식별자", "변경일", "사용자", "요약", "전체 이력"], 'data': client_rows, 'style': True}

            # Users
            user_rows = []
            users = session.query(User).order_by(User.id).all()
            for u in users:
                changed_at, summary_text, full = summarize_log(u.change_log)
                # 변경 이력이 있는 경우만 추가
                if full and summary_text:
                    identifier = u.username
                    user_rows.append(("사용자", u.id, identifier, changed_at, u.username or "", summary_text, full))
            if user_rows:  # 데이터가 있을 때만 시트 추가
                sheets['사용자'] = {'headers': ["엔티티", "ID", "식별자", "변경일", "사용자", "요약", "전체 이력"], 'data': user_rows, 'style': True}

            # 호출하여 엑셀로 저장
            excel_handler.export_multisheet_data_to_excel(sheets, default_filename="이력_내보내기.xlsx")

        except Exception as e:
            messagebox.showerror(self.texts['error'], f"이력 내보내기 중 오류: {e}", parent=self)
        finally:
            session.close()
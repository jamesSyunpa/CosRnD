import customtkinter as ctk
import tkinter as tk
from tkinter import ttk, messagebox, filedialog
from sqlalchemy import func, desc, or_, and_
from sqlalchemy.orm import joinedload
import sys
import os
import shutil

# 프로젝트 루트 경로를 sys.path에 추가 (상대 경로 import를 위함)
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if PROJECT_ROOT not in sys.path:
    sys.path.append(PROJECT_ROOT)

from tkcalendar import DateEntry
import configparser
from datetime import datetime, timedelta, date
from database.db_manager import db_manager
from database.models import (
    Client,
    Formulation,
    FormulationItem,
    Material,
    User,
    DocumentPackage,
    DocumentPackageLink,
    DocumentAttachment,
    IngredientReport,
    SemiFinishedCOA,
    FinishedProductCOA,
    ProductionFormulation,
    ProductionStep,
    Ingredient,
)
import json
from datetime import datetime, date
from modules import excel_handler
from modules.comparison_popup import FormulationComparisonPopup
from modules.folder_history_popup import FolderHistoryPopup
from modules.ui_components import HelpPopup, CustomErrorDialog, CustomDropdown, AddMaterialDialog, try_convert_to_float
from utils import center_window_on_mouse_display, safe_focus
from modules.translation import get_texts
from modules.ui_components import ProductionPreviewPane
from modules.print_preview import show_production_print_preview
from modules.formulation_popup import FormulationEditPopup, to_decimal, decimal_to_str_full # FormulationEditPopup은 그대로 둡니다.
from decimal import Decimal

class ColumnSelectionPopup(ctk.CTkToplevel):
    """열 선택을 위한 팝업 창 (여러 개 선택 가능, 드래그 미지원하지만 클릭으로 유지됨)"""
    def __init__(self, master, treeview, columns_config, callback, x, y):
        super().__init__(master)
        
        # 창 설정
        self.title("컬럼 선택")
        # 위치 조정
        self.geometry(f"+{x}+{y}")
        self.resizable(False, False)
        self.attributes("-topmost", True)
        self.transient(master)  # 부모 창 위에 표시
        
        self.treeview = treeview
        self.columns_config = columns_config
        self.callback = callback

        # 메인 프레임 (스크롤 가능하도록 변경)
        self.frame = ctk.CTkScrollableFrame(self, width=200, height=400)
        self.frame.pack(fill="both", expand=True, padx=5, pady=5)

        self.is_dragging = False
        self.drag_target = None
        self.checkbox_items = []

        # 체크박스 목록 생성
        for col_id, config in columns_config.items():
            # BooleanVar가 없으면 생성 (config에 저장하여 상태 유지)
            if "variable" not in config:
                config["variable"] = tk.BooleanVar(value=config.get("visible", True))
            
            var = config["variable"]
            
            cb = ctk.CTkCheckBox(
                self.frame, 
                text=config["text"], 
                variable=var,
                command=lambda: self.callback(self.treeview, self.columns_config)
            )
            cb.pack(anchor="w", padx=10, pady=2)
            
            # 드래그 선택을 위한 이벤트 바인딩
            # ButtonPress-1: 드래그 시작. 우리가 직접 토글 로직을 제어하기 위해 return "break" 사용
            cb.bind("<ButtonPress-1>", lambda event, v=var: self.start_drag(event, v))
            cb._canvas.bind("<ButtonPress-1>", lambda event, v=var: self.start_drag(event, v)) # 내부 캔버스에도 바인딩
            cb._text_label.bind("<ButtonPress-1>", lambda event, v=var: self.start_drag(event, v)) # 내부 텍스트에도 바인딩

            # B1-Motion: 드래그 중 다른 항목 토글
            cb.bind("<B1-Motion>", self.on_drag)
            cb._canvas.bind("<B1-Motion>", self.on_drag)
            cb._text_label.bind("<B1-Motion>", self.on_drag)

            # ButtonRelease-1: 드래그 종료
            cb.bind("<ButtonRelease-1>", self.stop_drag)
            cb._canvas.bind("<ButtonRelease-1>", self.stop_drag)
            cb._text_label.bind("<ButtonRelease-1>", self.stop_drag)
            
            self.checkbox_items.append((cb, var))
        
        # 닫기 버튼
        ctk.CTkButton(self.frame, text="닫기", width=100, command=self.destroy).pack(pady=10)

        # 포커스 설정: 창이 파괴되기 전에 focus_force가 호출되어 TclError가 발생하는 것을 방지
        self.after(10, lambda: self.focus_force() if getattr(self, 'winfo_exists', lambda: False)() and self.winfo_exists() else None)

    def start_drag(self, event, var):
        """드래그 시작: 클릭한 항목의 상태를 반전시키고, 이 상태를 타겟으로 설정"""
        self.is_dragging = True
        # 현재 값의 반대로 타겟 설정 (토글)
        self.drag_target = not var.get()
        
        # 첫 항목 강제 토글 (네이티브 동작 무시하고 직접 제어)
        var.set(self.drag_target)
        self.callback(self.treeview, self.columns_config)
        
        # 중요: 기본 위젯 동작 방해 (직접 제어하므로 네이티브 토글 동작 차단)
        return "break"

    def on_drag(self, event):
        """드래그 중: 마우스 위치에 있는 체크박스를 찾아 타겟 상태로 변경"""
        if not self.is_dragging: return
        
        x, y = event.x_root, event.y_root
        
        # 모든 체크박스를 순회하며 히트 테스트 (단순 Bounding Box 체크)
        for cb, var in self.checkbox_items:
            # 위젯의 화면상 좌표 및 크기
            wx = cb.winfo_rootx()
            wy = cb.winfo_rooty()
            ww = cb.winfo_width()
            wh = cb.winfo_height()
            
            # 마우스가 위젯 영역 안에 있는지 확인
            if wx <= x <= wx + ww and wy <= y <= wy + wh:
                # 상태가 다를 경우에만 업데이트 (불필요한 콜백 호출 방지)
                if var.get() != self.drag_target:
                    var.set(self.drag_target)
                    self.callback(self.treeview, self.columns_config)

    def stop_drag(self, event):
        """드래그 종료"""
        self.is_dragging = False
        return "break"

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
        try:
            center_window_on_mouse_display(self)
        except Exception:
            pass

class DocumentManagementFrame(ctk.CTkFrame):
    """문서/처방/생산/패키지 관리 메인 프레임 (세련된 UI + 재사용 패턴)."""
    def __init__(self, master, current_user, app, texts=None, mode="research"):
        super().__init__(master, corner_radius=0, fg_color="transparent")
        self.current_user = current_user
        self.app = app
        self.language = getattr(app, 'language', 'korean')
        self.texts = texts or get_texts(self.language)
        self.mode = mode or "research"
        self._selected_formulation_id = None
        
        # 폴더 계층 구조 상태 변수
        self.current_view_level = "client"  # "client" | "item" | "formulation"
        self.current_client_id = None       # 선택된 업체 ID (None이면 미지정)
        self.current_client_name = None     # 선택된 업체 이름

        # 레이아웃 기본 설정
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(0, weight=1)

        # 도움말 버튼 (place로 겹치게 배치)
        self.help_button = ctk.CTkButton(self, text=self.texts['help'], width=80, command=self.show_help)
        self.help_button.place(relx=0.98, y=10, anchor="ne")

        # 패키지 전용 모드일 경우 별도 레이아웃으로 처리
        if self.mode == "package_only":
            self.tab_view = None
            self.tab_map = {}
            self.package_tab_label = None
            package_container = ctk.CTkFrame(self, fg_color="transparent")
            package_container.grid(row=0, column=0, sticky="nsew", padx=10, pady=10)
            package_container.grid_columnconfigure(0, weight=1)
            package_container.grid_rowconfigure(0, weight=1)

            self.setup_package_tab(package_container)
            try:
                self.refresh_package_list()
            except Exception:
                pass
            return

        # 최상위 단일 탭 뷰 (1단 플랫 통합 구조, 테두리 겹침 원천 방지)
        self.tab_view = ctk.CTkTabview(
            self, command=self.on_tab_change, border_width=0,
            border_color=("gray80", "gray30"),
            segmented_button_selected_color=("#3B8ED0", "#1F6AA5"),
            segmented_button_unselected_color=("gray92", "gray20"),
            text_color=("black", "white"),
            segmented_button_selected_hover_color=("#3671A8", "#144870"),
            segmented_button_unselected_hover_color=("gray85", "gray28")
        )
        self.tab_view.grid(row=0, column=0, sticky="nsew", padx=6, pady=(0, 6))

        # 탭 정의 (단일 플랫 통합 구조)
        self.tab_map = {}
        
        tab_list_label = "처방 목록"
        tab_lookup_label = "원료/성분 조회"
        tab_quote_label = "견적"
        tab_ingredient_label = "전성분"
        tab_production_label = self.texts.get("production_formulation", "생산 처방")
        tab_spec_label = self.texts.get("property_spec", "물성규격")
        tab_report_label = self.texts.get("report", "기능성보고서")
        tab_package_label = self.texts.get("package", "패키지")

        self.tab_map[tab_list_label] = "document/formulation_mgt"
        self.tab_map[tab_lookup_label] = "document/ingredient_lookup"
        self.tab_map[tab_quote_label] = "document/quotation"
        self.tab_map[tab_ingredient_label] = "document/ingredient_list"
        self.tab_map[tab_production_label] = "document/production_formulation"
        self.tab_map[tab_spec_label] = "document/property_spec"
        self.tab_map[tab_report_label] = "document/report"
        self.tab_map[tab_package_label] = "document/package"

        # 단일 탭뷰에 8대 핵심 탭 직접 등록 (이중 중첩 완전 제거)
        self.tab_view.add(tab_list_label)
        self.tab_view.add(tab_lookup_label)
        self.tab_view.add(tab_quote_label)
        self.tab_view.add(tab_ingredient_label)
        self.tab_view.add(tab_production_label)
        self.tab_view.add(tab_spec_label)
        self.tab_view.add(tab_report_label)
        self.tab_view.add(tab_package_label)

        # 각 탭의 UI 1:1 직접 연결
        self.setup_formulation_list_tab(self.tab_view.tab(tab_list_label))
        self.setup_ingredient_lookup_tab(self.tab_view.tab(tab_lookup_label))
        self.setup_quotation_tab(self.tab_view.tab(tab_quote_label))
        self.setup_ingredient_list_tab(self.tab_view.tab(tab_ingredient_label))
        self.setup_production_tab(self.tab_view.tab(tab_production_label))
        self.setup_lab_journal_tab(self.tab_view.tab(tab_spec_label))
        self.setup_functional_report_tab(self.tab_view.tab(tab_report_label))
        self.setup_package_tab(self.tab_view.tab(tab_package_label))

        self.package_tab_label = tab_package_label
        self.production_tab_label = tab_production_label
        self.ingredient_lookup_tab_label = tab_lookup_label

        # 초기 데이터 로드
        try:
            self.load_formulations()
        except Exception:
            pass

    # ------------------------------
    # 권한/상태 헬퍼
    # ------------------------------
    def _role_level(self) -> int:
        """사용자 역할을 정수 레벨로 환산합니다. QC=0 < RD=1 < RQ=2 < RQD=3 < MSAD/Admin=4"""
        try:
            if getattr(self.current_user, 'is_admin', False):
                return 4
            role = (getattr(self.current_user, 'role', '') or '').upper()
        except Exception:
            role = ''
        mapping = {
            'QC': 0,
            'RD': 1,
            'RQ': 2,
            'RQD': 3,
            'MSAD': 4,
        }
        return mapping.get(role, 0)

    def _min_level_for_status(self, status: str) -> int:
        """상태별 최소 요구 레벨을 반환합니다. 초안=RD+(1), 검토중=RQ+(2), 확정=RQD+(3)"""
        s = (status or '').strip()
        if s == '초안':
            return 1
        if s == '검토중':
            return 2
        if s == '확정':
            return 3
        # 알 수 없는 상태는 보수적으로 최고 레벨 요구
        return 4

    def can_view_production(self, prod) -> bool:
        """해당 생산처방을 목록/열람할 수 있는지 여부."""
        try:
            need = self._min_level_for_status(getattr(prod, 'status', None))
            return self._role_level() >= need
        except Exception:
            return False

    def can_use_production(self, prod) -> bool:
        """해당 생산처방을 '사용'(편집/내보내기/미리보기 등)할 수 있는지 여부."""
        # 현재 정책상 사용 권한은 열람과 동일 레벨로 적용
        return self.can_view_production(prod)

    def allowed_status_values_for_create(self):
        """현재 사용자 기준 생성 시 선택 가능한 상태 목록을 반환합니다."""
        lvl = self._role_level()
        if lvl >= 3:
            return ['초안', '검토중', '확정']
        if lvl == 2:
            return ['초안', '검토중']
        if lvl == 1:
            return ['초안']
        return []

    def setup_document_sub_tabs(self, tab_frame, include_package_tab=True):
        """'문서' 탭 내부에 서브 탭들을 설정합니다."""
        tab_frame.grid_columnconfigure(0, weight=1)
        tab_frame.grid_rowconfigure(0, weight=1)

        doc_sub_tab_view = ctk.CTkTabview(tab_frame, command=self.on_doc_sub_tab_change, border_width=0, border_color=("gray80", "gray30"))
        doc_sub_tab_view.grid(row=0, column=0, padx=10, pady=(0, 10), sticky="nsew")
        self.doc_sub_tab_view = doc_sub_tab_view  # switch_to_tab에서 참조 가능하도록 저장

        # 요청된 하위 탭들 추가
        doc_sub_tab_view.add(self.texts["property_spec"])
        doc_sub_tab_view.add(self.texts["report"])
        package_tab_label = None
        if include_package_tab:
            try:
                package_tab_label = self.texts.get("package", "패키지")
            except Exception:
                package_tab_label = "패키지"
            doc_sub_tab_view.add(package_tab_label)

        # 패키지 탭 라벨 저장 (탭 변경 감지용)
        self.package_tab_label = package_tab_label

        # 각 탭의 UI 설정
        self.setup_lab_journal_tab(doc_sub_tab_view.tab(self.texts["property_spec"]))
        self.setup_functional_report_tab(doc_sub_tab_view.tab(self.texts["report"]))
        if include_package_tab and package_tab_label:
            self.setup_package_tab(doc_sub_tab_view.tab(package_tab_label))

    def on_doc_sub_tab_change(self):
        """문서 관리 하위 탭 전환 시, '패키지' 탭이 선택되면 목록을 자동 갱신합니다."""
        try:
            if hasattr(self, 'package_tree') and hasattr(self, 'package_tab_label'):
                # 패키지 탭이 선택되면 항상 목록 갱신 (처방 선택 여부 무관)
                self.refresh_package_list()
        except Exception as e:
            print(f"패키지 탭 전환 중 오류: {e}")
            pass


    def show_help(self):
        """서류 관리 도움말을 표시합니다."""
        title = self.texts['doc_mgt_help_title']
        message = self.texts['doc_mgt_help_message']
        HelpPopup(self, title, message)

    def on_tab_change(self):
        if not getattr(self, 'tab_view', None):
            return
        selected_tab = self.tab_view.get()
        # 탭 이름에 해당하는 고유 키를 찾아서 활동을 기록합니다.
        static_key = self.tab_map.get(selected_tab)
        if static_key:
            self.app.record_action(static_key)

        # 탭 전환 시 데이터 자동 동기화
        try:
            if selected_tab == "처방 목록":
                self.load_formulations()
            elif selected_tab == "원료/성분 조회":
                pass
            elif selected_tab == "견적":
                self.load_formulation_for_quotation(silent=True)
            elif selected_tab == "전성분":
                self.generate_all_ingredient_lists()
            elif selected_tab == self.texts.get("production_formulation", "생산 처방"):
                if hasattr(self, 'search_production_list'):
                    self.search_production_list()
            elif selected_tab == self.texts.get("property_spec", "물성규격"):
                if hasattr(self, 'load_lab_journal'):
                    self.load_lab_journal()
            elif selected_tab == self.texts.get("package", "패키지"):
                if hasattr(self, 'refresh_package_list'):
                    self.refresh_package_list()
        except Exception as e:
            print(f"[DocumentManagement] 탭 전환 데이터 동기화 실패: {e}")

    def switch_to_tab(self, tab_name):
        if not getattr(self, 'tab_view', None):
            return
        
        # 1. 상단 탭 버튼들 숨기기 + row minsize 0으로 리셋
        def _hide_tabview_header(tv):
            try:
                if hasattr(tv, '_segmented_button'):
                    tv._segmented_button.grid_forget()
                for r in (0, 1, 2):
                    tv.grid_rowconfigure(r, weight=0, minsize=0)
            except Exception as e:
                print(f"[UI] 탭 헤더 숨기기 실패: {e}")

        try:
            _hide_tabview_header(self.tab_view)
        except Exception:
            pass
            
        # 2. 탭 이름 매핑 사전 구성 (모든 기존 서브 탭 키를 단일 탭으로 100% 호환 매핑)
        tab_name_mapping = {
            "formulation_mgt": "처방 목록",
            "document_sub": self.texts.get("property_spec", "물성규격"),
            "lookup": "원료/성분 조회",
            "list": "처방 목록",
            "quote": "견적",
            "ingredient": "전성분",
            "production": self.texts.get("production_formulation", "생산 처방"),
            "property_spec": self.texts.get("property_spec", "물성규격"),
            "report": self.texts.get("report", "기능성보고서"),
            "package": self.texts.get("package", "패키지")
        }
        
        target_tab = tab_name_mapping.get(tab_name, tab_name)
        
        # 최상위 단일 탭 전환
        if target_tab in self.tab_view._name_list:
            self.tab_view.set(target_tab)
            self.on_tab_change()
            return

    def refresh_data(self):
        """문서 관리 프레임의 데이터를 새로고침합니다. (선택 유지)"""
        print("문서 관리 프레임 데이터 새로고침...")
        if self.mode == "package_only":
            try:
                self.refresh_package_list()
            except Exception as e:
                print(f"[오류] 패키지 목록 새로고침 실패: {e}")
            return
        try:
            # 현재 선택된 ID와 뷰 상태 저장
            selected_ids = self.get_selected_formulation_ids()
            current_view = self.current_view
            current_folder = self.current_folder_name

            # Reset to client view level to avoid empty folder issues when Formulation client changed
            self.current_view_level = "client"
            self.current_client_id = None
            self.current_client_name = None

            # 데이터 새로고침
            self.load_formulations(maintain_position=True) # 폴더 또는 파일 뷰 새로고침 (위치 유지)
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
        if hasattr(self, 'list_filter_client_type_combo') and self.list_filter_client_type_combo:
            all_client_types = [self.texts['select_type']] + db_manager.get_unique_client_types()
            self.list_filter_client_type_combo.configure(values=all_client_types)
            self.list_filter_client_type_combo.set("- 유형 선택 -")
            self.update_list_filter_client_name_combo("- 유형 선택 -")

    def setup_formulation_tab(self, tab_frame):
        """처방 관리 탭의 UI를 설정합니다."""
        tab_frame.grid_columnconfigure(0, weight=1)
        tab_frame.grid_rowconfigure(0, weight=1)

        self.formulation_sub_tab_view = ctk.CTkTabview(
            tab_frame,
            command=self.on_formulation_sub_tab_change,
            border_width=0, border_color=("gray80", "gray30"), # 부모를 tab_frame으로 설정
            segmented_button_selected_color=("#3B8ED0", "#1F6AA5"),
            segmented_button_unselected_color=("gray92", "gray20"),
            text_color=("black", "white"),
            segmented_button_selected_hover_color=("#3671A8", "#144870"),
            segmented_button_unselected_hover_color=("gray85", "gray28")
        )
        self.formulation_sub_tab_view.grid(row=0, column=0, padx=4, pady=(0, 4), sticky="nsew")

        # --- 언어별 텍스트 ---
        texts = {
            "korean": {"lookup": "원료/성분 조회", "list": "처방 목록", "quote": "견적", "ingredient": "전성분"},
            "english": {"lookup": "Material/Ingredient Lookup", "list": "Formulation List", "quote": "Quotation", "ingredient": "Ingredient List"}
        }
        current_texts = texts[self.app.language]

        # 성분 조회 탭을 첫 번째로 추가
        self.ingredient_lookup_tab_label = current_texts["lookup"]
        self.formulation_sub_tab_view.add(current_texts["lookup"])
        self.formulation_sub_tab_view.add(current_texts["list"])
        self.formulation_sub_tab_view.add(current_texts["quote"])
        self.formulation_sub_tab_view.add(current_texts["ingredient"])
        # 생산 처방 탭 추가
        prod_tab_label = self.texts.get("production_formulation", "생산 처방")
        # 현재 선택 탭 변경 시 비교를 위해 보관
        self.production_tab_label = prod_tab_label
        self.formulation_sub_tab_view.add(prod_tab_label)

        self.setup_ingredient_lookup_tab(self.formulation_sub_tab_view.tab(current_texts["lookup"]))
        self.setup_formulation_list_tab(self.formulation_sub_tab_view.tab(current_texts["list"]))
        self.setup_quotation_tab(self.formulation_sub_tab_view.tab(current_texts["quote"]))
        self.setup_ingredient_list_tab(self.formulation_sub_tab_view.tab(current_texts["ingredient"]))
        self.setup_production_tab(self.formulation_sub_tab_view.tab(prod_tab_label))

    def setup_ingredient_lookup_tab(self, tab_frame):
        """성분 조회 탭의 UI를 설정합니다."""
        tab_frame.grid_columnconfigure(0, weight=1)
        tab_frame.grid_rowconfigure(1, weight=1)

        # --- 상단 입력 영역 ---
        input_frame = ctk.CTkFrame(tab_frame, fg_color="transparent")
        input_frame.grid(row=0, column=0, sticky="ew", padx=10, pady=(0, 5))
        input_frame.grid_columnconfigure(0, weight=1)

        # 타이틀 및 안내
        header_frame = ctk.CTkFrame(input_frame, fg_color="transparent")
        header_frame.grid(row=0, column=0, sticky="ew")
        
        ctk.CTkLabel(header_frame, text=self.texts.get("ingredient_lookup", "성분 조회"), 
                     font=ctk.CTkFont(size=16, weight="bold")).pack(side="left")
        
        # 검색 유형 선택 콤보박스
        ctk.CTkLabel(header_frame, text="  검색 유형:", font=ctk.CTkFont(size=12)).pack(side="left", padx=(15, 5))
        search_type_values = ["전체", "성분명(한글)", "성분명(영문)", "CAS No", "원료명"]
        self.lookup_search_type_combo = ctk.CTkComboBox(header_frame, values=search_type_values, width=130, state="readonly")
        self.lookup_search_type_combo.set("전체")
        self.lookup_search_type_combo.pack(side="left")
        
        # 버튼 프레임 (우측 정렬)
        btn_frame = ctk.CTkFrame(input_frame, fg_color="transparent")
        btn_frame.grid(row=0, column=1, sticky="e")
        
        ctk.CTkButton(btn_frame, text="🔍 검색", 
                      width=70, command=self.search_ingredients_by_list).pack(side="left", padx=2)
        ctk.CTkButton(btn_frame, text="✨ 복합원료 스마트 매칭", 
                      width=135, command=self.analyze_complex_ingredients, 
                      fg_color="#6200EA", hover_color="#5000CA").pack(side="left", padx=2)
        ctk.CTkButton(btn_frame, text="초기화", 
                      width=55, command=self.clear_ingredient_lookup_results, 
                      fg_color="gray50", hover_color="gray40").pack(side="left", padx=2)
        ctk.CTkButton(btn_frame, text=self.texts.get("export_lookup_to_excel", "Excel로 내보내기"), 
                      width=120, command=self.export_ingredient_lookup_to_excel,
                      fg_color="#2B7A3B", hover_color="#236030").pack(side="left", padx=2)
        ctk.CTkButton(btn_frame, text=self.texts.get("import_lookup_from_excel", "Excel에서 가져오기"), 
                      width=130, command=self.import_ingredient_lookup_from_excel,
                      fg_color="#1976D2", hover_color="#1565C0").pack(side="left", padx=2)

        # 텍스트 입력 영역
        text_frame = ctk.CTkFrame(input_frame, fg_color="transparent")
        text_frame.grid(row=1, column=0, columnspan=2, sticky="ew", pady=(8, 0))
        text_frame.grid_columnconfigure(0, weight=1)
        
        # 상단 안내 가이드 라벨
        guide_lbl = ctk.CTkLabel(
            text_frame, 
            text="📝 검색할 성분명(한글/영문) 또는 CAS No를 아래에 줄 단위로 입력하세요 (단축키: Ctrl + Enter)",
            font=ctk.CTkFont(size=12),
            text_color=("gray40", "gray70")
        )
        guide_lbl.grid(row=0, column=0, sticky="w", pady=(0, 4))
        
        # 순수 네이티브 텍스트박스 (가짜 플레이스홀더 없이 언제나 즉시 100% 타이핑 가능)
        self.ingredient_lookup_textbox = ctk.CTkTextbox(text_frame, height=100, font=ctk.CTkFont(size=12))
        self.ingredient_lookup_textbox.grid(row=1, column=0, sticky="ew")
        self.ingredient_lookup_textbox.bind("<Control-Return>", lambda e: self.search_ingredients_by_list())

        # --- 결과 표시 영역 ---
        result_frame = ctk.CTkFrame(tab_frame, fg_color="transparent")
        result_frame.grid(row=1, column=0, sticky="nsew", padx=10, pady=(5, 10))
        result_frame.grid_columnconfigure(0, weight=1)
        result_frame.grid_rowconfigure(1, weight=1)
        self.lookup_result_frame = result_frame  # 참조 저장

        # 결과 카운트 라벨
        self.lookup_result_label = ctk.CTkLabel(result_frame, 
            text=self.texts.get("lookup_results_count", "검색 결과: {count}건").format(count=0),
            font=ctk.CTkFont(size=12))
        self.lookup_result_label.grid(row=0, column=0, sticky="w", pady=(0, 2))

        # [v64 신규] 상단 틀고정 헤더 & 빠른선택 툴바 전용 컨테이너 (스크롤 시에도 상단에 영구 고정)
        self.lookup_sticky_header_frame = ctk.CTkFrame(result_frame, fg_color="transparent")
        self.lookup_sticky_header_frame.grid(row=1, column=0, sticky="ew", pady=(0, 4))
        self.lookup_sticky_header_frame.grid_columnconfigure(0, weight=1)

        # 결과 Treeview (성분명/CAS No 검색용)
        lookup_cols = self.texts.get("ingredient_lookup_columns", {
            "material_code": "원료코드", "name_ko": "성분명(한글)", 
            "name_en": "성분명(영문)", "function": "효능(기능)", "cas_no": "CAS No."
        })
        col_ids = list(lookup_cols.keys())

        # Treeview 컨테이너 프레임
        self.lookup_tree_frame = ctk.CTkFrame(result_frame, fg_color="transparent")
        self.lookup_tree_frame.grid(row=2, column=0, sticky="nsew")
        self.lookup_tree_frame.grid_columnconfigure(0, weight=1)
        self.lookup_tree_frame.grid_rowconfigure(0, weight=1)
        
        self.ingredient_lookup_tree = ttk.Treeview(self.lookup_tree_frame, columns=col_ids, show="headings", selectmode="extended")
        
        # 컬럼 설정
        col_widths = {"material_code": 100, "name_ko": 200, "name_en": 200, "function": 150, "cas_no": 120}
        for col_id in col_ids:
            self.ingredient_lookup_tree.heading(col_id, text=lookup_cols.get(col_id, col_id),
                command=lambda c=col_id: self.sort_treeview_column(self.ingredient_lookup_tree, c, False))
            width = col_widths.get(col_id, 120)
            stretch = col_id in ["name_ko", "name_en"]
            self.ingredient_lookup_tree.column(col_id, width=width, stretch=stretch)
        
        self.ingredient_lookup_tree.grid(row=0, column=0, sticky="nsew")
        
        # 스크롤바
        lookup_v_scroll = ttk.Scrollbar(self.lookup_tree_frame, orient="vertical", command=self.ingredient_lookup_tree.yview)
        self.ingredient_lookup_tree.configure(yscrollcommand=lookup_v_scroll.set)
        lookup_v_scroll.grid(row=0, column=1, sticky='ns')
        
        lookup_h_scroll = ttk.Scrollbar(self.lookup_tree_frame, orient="horizontal", command=self.ingredient_lookup_tree.xview)
        self.ingredient_lookup_tree.configure(xscrollcommand=lookup_h_scroll.set)
        lookup_h_scroll.grid(row=1, column=0, sticky='ew')

        # [v64 UI 통일] 단일 통합 결과 스크롤 프레임 (헤더 아래 row=2에 위치하여 카드 목록만 스크롤됨)
        result_frame.grid_rowconfigure(2, weight=1)
        self.lookup_unified_frame = ctk.CTkScrollableFrame(result_frame, label_text="")
        self.lookup_unified_frame.grid(row=2, column=0, sticky="nsew")
        self.lookup_unified_frame.grid_columnconfigure(0, weight=1)
        self.lookup_unified_rows = []
        self.selected_lookup_items = {}

        # 하위 호환용 참조
        self.lookup_material_frame = self.lookup_unified_frame
        self.lookup_complex_frame = self.lookup_unified_frame
        self.lookup_material_rows = []
        self.lookup_complex_rows = []
        self.selected_complex_materials = self.selected_lookup_items

    def search_ingredients_by_list(self):
        """입력된 성분명/CAS No 리스트로 DB에서 검색"""
        # 입력 텍스트 가져오기
        input_text = self.ingredient_lookup_textbox.get("0.0", "end-1c").strip()
        if not input_text:
            messagebox.showwarning(self.texts.get("warning", "경고"), 
                self.texts.get("enter_search_terms", "검색할 성분명 또는 CAS No를 입력하세요."), parent=self)
            return

        # 줄 단위로 분리하여 검색어 리스트 생성
        raw_lines = [line.strip() for line in input_text.split('\n') if line.strip()]
        search_terms = []
        for line in raw_lines:
            # 사용자가 ', ' (콤마+공백)으로 구분된 데이터를 넣었을 경우 처리
            # (단, 'N,N-...' 같이 이름 내부에 콤마가 있는 경우를 위해 콤마+공백으로 한정)
            if ', ' in line:
                for part in line.split(', '):
                    clean_part = part.strip().rstrip(',') # 끝에 붙은 콤마 제거
                    if clean_part:
                        search_terms.append(clean_part)
            else:
                search_terms.append(line)

        
        if not search_terms:
            return

        # 검색 유형 가져오기
        search_type = self.lookup_search_type_combo.get() if hasattr(self, 'lookup_search_type_combo') else "전체"

        # 원료명 전용 검색 모드 분기 (사용자가 콤보박스에서 '원료명'을 명시적으로 선택했을 때만)
        if search_type == "원료명":
            search_terms_with_empty = [line.strip() for line in input_text.split('\n')]
            self._search_by_material_name(search_terms_with_empty)
            return

        # [핵심 개편] 성분 데이터(Ingredients 테이블) 기준으로 원료를 검색하고,
        # 사용자의 요구대로 '단일 성분(성분 1개짜리 원료)'부터 우선 차례대로 나열한 뒤
        # 그 다음 복합 원료들을 성분 수 및 매칭도 순으로 정렬 표시합니다.
        is_eng = getattr(self, 'lookup_export_lang_var', None) and "영문" in self.lookup_export_lang_var.get()
        session = db_manager.get_session()
        try:
            # 1. 활성 원료 및 연관 성분/공급처를 일괄 로드
            all_materials = session.query(Material).options(
                joinedload(Material.ingredients),
                joinedload(Material.supplier)
            ).filter(Material.is_active == True).all()

            normalized_terms = {t.lower().replace(" ", ""): t for t in search_terms if t.strip()}
            matched_items = []
            seen_material_ids = set()

            for mat in all_materials:
                if not mat.ingredients:
                    continue

                matched_ing_list = []
                for ing in mat.ingredients:
                    ing_ko = (ing.name_ko or "").strip()
                    ing_en = (ing.name_en or "").strip()
                    ing_cas = (ing.cas_no or "").strip()

                    ko_norm = ing_ko.lower().replace(" ", "")
                    en_norm = ing_en.lower().replace(" ", "")
                    cas_norm = ing_cas.lower().replace(" ", "")

                    is_match = False
                    for norm_t in normalized_terms.keys():
                        if not norm_t:
                            continue
                        if search_type == "성분명(한글)":
                            if (norm_t in ko_norm) or (ko_norm and ko_norm in norm_t):
                                is_match = True
                                break
                        elif search_type == "성분명(영문)":
                            if (norm_t in en_norm) or (en_norm and en_norm in norm_t):
                                is_match = True
                                break
                        elif search_type == "CAS No":
                            if norm_t == cas_norm or (norm_t in cas_norm):
                                is_match = True
                                break
                        else:  # 전체 검색
                            if (norm_t in ko_norm) or (ko_norm and ko_norm in norm_t) or \
                               (norm_t in en_norm) or (en_norm and en_norm in norm_t) or \
                               (cas_norm and norm_t == cas_norm):
                                is_match = True
                                break

                    if is_match:
                        matched_ing_list.append({
                            "name_ko": ing_ko,
                            "name_en": ing_en,
                            "cas_no": ing_cas,
                            "function": ing.function or "",
                            "ratio": ing.composition_ratio or 0.0
                        })

                m_count = len(matched_ing_list)
                total_ing_count = len(mat.ingredients)

                # 일치하는 성분이 하나라도 있으면 후보 목록에 추가
                if m_count > 0 and mat.id not in seen_material_ids:
                    seen_material_ids.add(mat.id)
                    is_blend = (total_ing_count >= 2)
                    supplier_name = mat.supplier.name if mat.supplier else (mat.manufacturer or "-")
                    reg_info = f"입고: {mat.reg_date or (mat.created_at.strftime('%Y-%m-%d') if mat.created_at else '-')}"
                    price_info = f"₩{mat.unit_price:,.0f}/kg" if mat.unit_price else "단가 미등록"

                    tags = []
                    cas_list = []
                    func_list = []
                    for ing_info in matched_ing_list:
                        r_str = f" ({ing_info['ratio']}%)" if ing_info['ratio'] > 0 else ""
                        name_display = ing_info['name_en'] if is_eng and ing_info['name_en'] else ing_info['name_ko']
                        tags.append(f"✓ {name_display}{r_str}")
                        if ing_info['cas_no'] and ing_info['cas_no'] not in cas_list:
                            cas_list.append(ing_info['cas_no'])
                        if ing_info['function'] and ing_info['function'] not in func_list:
                            func_list.append(ing_info['function'])

                    if not is_blend:
                        badge = "단일 성분" if not is_eng else "Single Ingredient"
                        b_color = "#0288D1"
                    else:
                        badge = f"복합원료 ({m_count}/{total_ing_count}개 일치)" if not is_eng else f"Blend ({m_count}/{total_ing_count} Match)"
                        b_color = "#4F46E5"

                    matched_items.append({
                        "material": mat,
                        "code": mat.code,
                        "name": mat.name_en if is_eng and mat.name_en else mat.name,
                        "badge_text": badge,
                        "badge_color": b_color,
                        "supplier_text": supplier_name,
                        "stock_text": f"{reg_info} | {price_info}",
                        "tags": tags,
                        "cas_no": ", ".join(cas_list),
                        "function": ", ".join(func_list),
                        "primary_ing": matched_ing_list[0]["name_ko"] if matched_ing_list else (mat.name or ""),
                        "match_count": m_count,
                        "total_ing_count": total_ing_count,
                        "is_blend": is_blend
                    })

            # [정렬 규칙]:
            # 1. 단일 성분(total_ing_count == 1)을 최우선으로 배치 (is_blend == False)
            # 2. 단일 성분들은 검색된 성분명 카테고리(primary_ing)별로 모아서 그룹화 정렬
            # 3. 그 다음 복합 원료는 성분 수(total_ing_count) 적은 순서 -> 매칭 수 많은 순
            # 4. 원료코드 및 원료명 순으로 정렬
            matched_items.sort(key=lambda x: (
                0 if not x["is_blend"] else 1,      # 단일 성분 0순위
                x["primary_ing"] if not x["is_blend"] else "", # 단일 성분인 경우 해당 성분 카테고리별로 정렬
                x["total_ing_count"],               # 성분 수 적은 순서(1개, 2개, 3개...)
                -x["match_count"],                  # 매칭 개수 많은 순
                x["code"] or "",                    # 원료코드 순
                x["name"] or ""                     # 원료명 순
            ))

            title_info = f"성분 조회 결과 (검색어 {len(search_terms)}개)" if not is_eng else f"Ingredient Search Results ({len(search_terms)} queries)"
            self._render_unified_lookup_results(title_info, matched_items, len(search_terms))

            if not matched_items:
                messagebox.showinfo(self.texts.get("notification", "알림"),
                    self.texts.get("no_search_results", "검색 결과가 없습니다."), parent=self)

        except Exception as e:
            messagebox.showerror(self.texts.get("error", "오류"), f"성분 조회 중 오류 발생: {e}", parent=self)
            print(f"[LOOKUP-ERROR] {e}")
        finally:
            session.close()

    def _clear_unified_lookup_frame(self):
        """통합 결과 프레임 및 틀고정 헤더의 모든 위젯 및 데이터 초기화"""
        if hasattr(self, 'lookup_sticky_header_frame'):
            for widget in self.lookup_sticky_header_frame.winfo_children():
                try:
                    widget.destroy()
                except Exception:
                    pass

        if hasattr(self, 'lookup_unified_frame'):
            for widget in self.lookup_unified_frame.winfo_children():
                try:
                    widget.destroy()
                except Exception:
                    try:
                        widget.tk.call('destroy', widget._w)
                    except Exception:
                        pass
        self.lookup_unified_rows = []
        self.selected_lookup_items = {}
        self.lookup_material_rows = []
        self.lookup_complex_rows = []
        self.selected_complex_materials = self.selected_lookup_items

    def _show_lookup_treeview(self):
        pass

    def _show_lookup_material_frame(self):
        pass

    def _update_quick_select_button_styles(self):
        """체크박스 상태에 따라 빠른 선택 버튼들의 활성/비활성 색상을 동적으로 갱신합니다."""
        if not hasattr(self, 'quick_select_buttons') or not hasattr(self, 'selected_lookup_items'):
            return
        
        # 카테고리별 대상 및 활성 상태 계산 (100% 일치는 복합원료 중 100% 일치만 대상으로 하여 단일성분과 완전 분리)
        targets = {"exact_100": [], "blend_only": [], "single_only": [], "all": []}
        
        for mat_id, item_tuple in self.selected_lookup_items.items():
            chk_var = item_tuple[0]
            item_info = item_tuple[2] if len(item_tuple) >= 3 else {}
            
            is_blend = item_info.get("is_blend", False)
            is_exact = item_info.get("is_exact_full_match", False)

            targets["all"].append(chk_var)
            if is_blend:
                targets["blend_only"].append(chk_var)
                if is_exact:
                    targets["exact_100"].append(chk_var)
            else:
                targets["single_only"].append(chk_var)

        color_map = {
            "exact_100": ("#16A34A", "#15803D"),   # 활성 초록
            "blend_only": ("#4F46E5", "#4338CA"),  # 활성 보라
            "single_only": ("#0288D1", "#0277BD"), # 활성 파랑
            "all": ("#00897B", "#00695C"),         # 활성 청록
        }
        inactive_color = ("gray75", "gray30")
        inactive_hover = ("gray65", "gray40")

        for key, btn in self.quick_select_buttons.items():
            chk_list = targets.get(key, [])
            if chk_list and all(v.get() for v in chk_list):
                # 전부 체크된 경우 -> 활성화 컬러 적용
                act_fg, act_hov = color_map.get(key, ("#16A34A", "#15803D"))
                btn.configure(fg_color=act_fg, hover_color=act_hov, text_color="white")
            else:
                # 미선택 / 일부 선택인 경우 -> 세련된 기본 회색 적용
                btn.configure(fg_color=inactive_color, hover_color=inactive_hover, text_color=("black", "gray90"))

    def _toggle_lookup_selection(self, filter_type="all"):
        """검색 결과에서 조건별(100%일치 복합원료, 복합원료 전체, 단일성분, 전체)로 중복 선택 및 재클릭 시 토글 해제 처리합니다."""
        if not hasattr(self, 'selected_lookup_items'):
            return
        
        # 1. 전체 해제 요청인 경우
        if filter_type == "none":
            for mat_id, item_tuple in self.selected_lookup_items.items():
                item_tuple[0].set(False)
            self._update_quick_select_button_styles()
            return

        # 2. 해당 필터 조건에 부합하는 대상 아이템들 추출
        target_items = []
        for mat_id, item_tuple in self.selected_lookup_items.items():
            chk_var = item_tuple[0]
            item_info = item_tuple[2] if len(item_tuple) >= 3 else {}
            is_blend = item_info.get("is_blend", False)
            is_exact = item_info.get("is_exact_full_match", False)

            is_match = False
            if filter_type == "all":
                is_match = True
            elif filter_type == "exact_100":
                # 복합원료 중 100% 일치만 선택 (단일성분과 완전 격리)
                is_match = bool(is_blend and is_exact)
            elif filter_type == "blend_only":
                is_match = bool(is_blend)
            elif filter_type == "single_only":
                is_match = not bool(is_blend)
            
            if is_match:
                target_items.append(chk_var)

        if not target_items:
            return

        # 3. 토글 판단: 대상 아이템들이 '모두' 체크되어 있는 경우에만 '해제(False)'하고,
        # 하나라도 체크 안 된 것이 있다면 '선택(True)'
        all_checked = all(var.get() for var in target_items)
        new_val = not all_checked

        for var in target_items:
            var.set(new_val)

        # 4. 버튼 색상 즉시 동기화
        self._update_quick_select_button_styles()

    def _render_unified_lookup_results(self, title_info, items_data, search_terms_count=0):
        """모든 검색 결과를 단일 통일된 프리미엄 카드 그리드로 일관되게 렌더링 (헤더 틀고정 지원)"""
        self._clear_unified_lookup_frame()
        if not hasattr(self, 'lookup_unified_frame'):
            return

        is_eng = getattr(self, 'lookup_export_lang_var', None) and "영문" in self.lookup_export_lang_var.get()

        # [헤더 틀고정]: 스크롤되지 않는 lookup_sticky_header_frame에 헤더 대시보드 고정 마운트
        header_parent = getattr(self, 'lookup_sticky_header_frame', self.lookup_unified_frame)
        dash_frame = ctk.CTkFrame(header_parent, fg_color=("gray90", "gray20"), corner_radius=6)
        dash_frame.pack(fill="x", padx=2, pady=(0, 4))
        dash_frame.grid_columnconfigure(0, weight=1)

        # 상단 요약 타이틀 및 통계
        top_info_row = ctk.CTkFrame(dash_frame, fg_color="transparent")
        top_info_row.pack(fill="x", padx=10, pady=(6, 4))

        summary_text = f"📊 {title_info} (발견 {len(items_data)}건)" if not is_eng else f"📊 {title_info} (Found {len(items_data)} items)"
        ctk.CTkLabel(top_info_row, text=summary_text, font=ctk.CTkFont(size=13, weight="bold")).pack(side="left")

        btn_txt = "🚀 선택한 원료로 신규 처방 개발" if not is_eng else "🚀 Create Formulation with Selected"
        ctk.CTkButton(
            top_info_row,
            text=btn_txt,
            font=ctk.CTkFont(size=12, weight="bold"),
            fg_color="#00897B", hover_color="#00695C",
            height=30,
            command=self._create_formulation_from_selected_complex
        ).pack(side="right")

        # [신규 기능] 부분부분 원터치 일괄 선택 액션 툴바 (기본 미선택 회색 -> 체크 시 컬러 활성화)
        select_bar = ctk.CTkFrame(dash_frame, fg_color="transparent")
        select_bar.pack(fill="x", padx=10, pady=(0, 6))

        ctk.CTkLabel(select_bar, text="⚡ 빠른 선택:", font=ctk.CTkFont(size=11, weight="bold"), text_color=("gray30", "gray70")).pack(side="left", padx=(0, 6))

        self.quick_select_buttons = {}
        inactive_color = ("gray75", "gray30")
        inactive_hover = ("gray65", "gray40")

        # 1. 100% 정확 일치만 선택 (복합원료 대상)
        exact_100_count = sum(1 for item in items_data if item.get("is_blend", False) and item.get("is_exact_full_match", False))
        btn_exact_text = f"🎯 100% 일치 복합원료 ({exact_100_count}건)" if not is_eng else f"🎯 100% Blend ({exact_100_count})"
        self.quick_select_buttons["exact_100"] = ctk.CTkButton(
            select_bar,
            text=btn_exact_text,
            font=ctk.CTkFont(size=11, weight="bold"),
            fg_color=inactive_color, hover_color=inactive_hover,
            text_color=("black", "gray90"),
            height=24,
            command=lambda: self._toggle_lookup_selection("exact_100")
        )
        self.quick_select_buttons["exact_100"].pack(side="left", padx=3)

        # 2. 복합원료만 선택
        blend_count = sum(1 for item in items_data if item.get("is_blend", False))
        btn_blend_text = f"⭐ 복합원료만 ({blend_count}건)" if not is_eng else f"⭐ Blends ({blend_count})"
        self.quick_select_buttons["blend_only"] = ctk.CTkButton(
            select_bar,
            text=btn_blend_text,
            font=ctk.CTkFont(size=11, weight="bold"),
            fg_color=inactive_color, hover_color=inactive_hover,
            text_color=("black", "gray90"),
            height=24,
            command=lambda: self._toggle_lookup_selection("blend_only")
        )
        self.quick_select_buttons["blend_only"].pack(side="left", padx=3)

        # 3. 단일성분만 선택
        single_count = len(items_data) - blend_count
        btn_single_text = f"🧪 단일성분만 ({single_count}건)" if not is_eng else f"🧪 Singles ({single_count})"
        self.quick_select_buttons["single_only"] = ctk.CTkButton(
            select_bar,
            text=btn_single_text,
            font=ctk.CTkFont(size=11, weight="bold"),
            fg_color=inactive_color, hover_color=inactive_hover,
            text_color=("black", "gray90"),
            height=24,
            command=lambda: self._toggle_lookup_selection("single_only")
        )
        self.quick_select_buttons["single_only"].pack(side="left", padx=3)

        # 4. 전체 선택
        self.quick_select_buttons["all"] = ctk.CTkButton(
            select_bar,
            text="✓ 전체 선택" if not is_eng else "✓ Select All",
            font=ctk.CTkFont(size=11),
            fg_color=inactive_color, hover_color=inactive_hover,
            text_color=("black", "gray90"),
            height=24,
            command=lambda: self._toggle_lookup_selection("all")
        )
        self.quick_select_buttons["all"].pack(side="left", padx=3)

        # 5. 선택 해제
        ctk.CTkButton(
            select_bar,
            text="✕ 선택 해제" if not is_eng else "✕ Deselect",
            font=ctk.CTkFont(size=11),
            fg_color=("gray75", "gray30"), hover_color=("gray65", "gray40"),
            text_color=("black", "gray90"),
            height=24,
            command=lambda: self._toggle_lookup_selection("none")
        ).pack(side="left", padx=3)

        row_idx = 1
        for item in items_data:
            mat = item.get("material")
            m_code = item.get("code") or (mat.code if mat else "-")
            m_name = (mat.name_en if is_eng and mat and mat.name_en else (mat.name if mat else item.get("name", "-")))
            badge_text = item.get("badge_text", "원료 정보")
            badge_color = item.get("badge_color", "#0288D1")
            supplier_text = item.get("supplier_text", "-")
            stock_text = item.get("stock_text", "-")
            sub_tags = item.get("tags", [])
            cas_no = item.get("cas_no", "")
            func_desc = item.get("function", "")

            # 현재 프로그램 폼 색상과 100% 일치하는 모던 카드 배경 (단일성분/복합원료 테마 톤 통일)
            is_blend = item.get("is_blend", False)
            card_bg = ("#F1F5F9", "#1E293B") if is_blend else ("gray95", "gray17")
            card_border = ("#94A3B8", "#475569") if is_blend else ("gray80", "gray30")

            card = ctk.CTkFrame(self.lookup_unified_frame, fg_color=card_bg, corner_radius=6, border_width=1, border_color=card_border)
            card.grid(row=row_idx, column=0, sticky="ew", padx=5, pady=3)
            card.grid_columnconfigure(1, weight=1)

            chk_var = tk.BooleanVar(value=False)
            if mat:
                # 3단 튜플로 저장하여 조건별 선택 시 메타 정보 활용
                self.selected_lookup_items[mat.id] = (chk_var, mat, item)
                chk = ctk.CTkCheckBox(card, text="", variable=chk_var, width=20, command=self._update_quick_select_button_styles)
                chk.grid(row=0, column=0, rowspan=2, padx=(8, 4), pady=4, sticky="n")
            else:
                ctk.CTkLabel(card, text="", width=20).grid(row=0, column=0, padx=4)

            # 1행: 뱃지 + 코드 + 원료명 + 공급처/입고정보 (단일 패스)
            r1_frame = ctk.CTkFrame(card, fg_color="transparent")
            r1_frame.grid(row=0, column=1, sticky="ew", padx=2, pady=(4, 1))

            ctk.CTkLabel(r1_frame, text=badge_text, fg_color=badge_color, text_color="white",
                         corner_radius=4, font=ctk.CTkFont(size=11, weight="bold"), padx=6, pady=1).pack(side="left", padx=(0, 6))

            code_display = f"[{m_code}]" if m_code and m_code != "-" else "[-]"
            ctk.CTkLabel(r1_frame, text=f"{code_display} {m_name}", font=ctk.CTkFont(size=12, weight="bold")).pack(side="left", padx=(0, 6))

            right_info = f"🏢 {supplier_text}  |  📦 {stock_text}"
            ctk.CTkLabel(r1_frame, text=right_info, font=ctk.CTkFont(size=11), text_color=("gray30", "gray70")).pack(side="right", padx=10)

            # 2행: 전성분 목록 및 부가 메타 (초고속 병합 라벨로 렌더링 랙 100% 제거)
            r2_frame = ctk.CTkFrame(card, fg_color="transparent")
            r2_frame.grid(row=1, column=1, sticky="ew", padx=2, pady=(1, 5))

            tag_str = "   ".join(sub_tags) if sub_tags else "-"
            meta_parts = []
            if cas_no: meta_parts.append(f"CAS: {cas_no}")
            if func_desc: meta_parts.append(f"기능: {func_desc}")
            if meta_parts:
                meta_suffix = "  •  " + "  •  ".join(meta_parts)
            else:
                meta_suffix = ""

            full_desc_txt = f"{tag_str}{meta_suffix}"
            desc_lbl = ctk.CTkLabel(
                r2_frame, 
                text=full_desc_txt, 
                font=ctk.CTkFont(size=11), 
                text_color=("gray20", "gray85"),
                anchor="w",
                justify="left"
            )
            desc_lbl.pack(side="left", fill="x", expand=True)

            self.lookup_unified_rows.append(card)
            row_idx += 1

        self.lookup_result_label.configure(text=f"검색 완료 (총 {len(items_data)}건 표시)")

    def _search_ingredients_grouped(self, search_terms, search_type):
        """성분 검색 결과를 검색어별 콤보박스로 표시 (보완 정보: 한글→영문/CAS/기능, 영문→한글/CAS/기능)"""
        self._show_lookup_material_frame()
        
        # 기존 위젯 제거 (CTkComboBox.destroy() 버그 우회: try/except 처리)
        for widget in self.lookup_material_frame.winfo_children():
            try:
                widget.destroy()
            except Exception:
                try:
                    widget.tk.call('destroy', widget._w)
                except Exception:
                    pass
            
        session = db_manager.get_session()
        try:
            # [추가] 내보내기용 데이터 저장 (콤보박스 참조 + 원본 데이터)
            self.lookup_grouped_rows = []
            
            # 헤더 생성
            ctk.CTkLabel(self.lookup_material_frame, text="검색어", font=ctk.CTkFont(weight="bold"), width=150).grid(row=0, column=0, padx=5, pady=5, sticky="w")
            ctk.CTkLabel(self.lookup_material_frame, text="검색 결과 선택", font=ctk.CTkFont(weight="bold"), width=350).grid(row=0, column=1, padx=5, pady=5, sticky="w")
            
            row_idx = 1
            found_count_total = 0
            
            for term in search_terms:
                search_pattern = f"%{term}%"
                
                # 검색 필터 (성분 기준)
                if search_type == "성분명(한글)":
                    filter_condition = Ingredient.name_ko.ilike(search_pattern)
                elif search_type == "성분명(영문)":
                    filter_condition = Ingredient.name_en.ilike(search_pattern)
                elif search_type == "CAS No":
                    filter_condition = Ingredient.cas_no.ilike(search_pattern)
                else:  # 전체
                    filter_condition = or_(
                        Ingredient.name_ko.ilike(search_pattern),
                        Ingredient.name_en.ilike(search_pattern),
                        Ingredient.cas_no.ilike(search_pattern)
                    )
                
                # 성분 검색
                ingredients = session.query(Ingredient).filter(filter_condition).all()
                
                # 중복 제거 (name_ko + name_en + cas_no 조합 기준)
                seen_keys = set()
                unique_ingredients = []
                for ing in ingredients:
                    key = (ing.name_ko or "", ing.name_en or "", ing.cas_no or "")
                    if key not in seen_keys:
                        seen_keys.add(key)
                        unique_ingredients.append(ing)
                
                # 검색어 라벨
                ctk.CTkLabel(self.lookup_material_frame, text=term, width=150, anchor="w").grid(row=row_idx, column=0, padx=5, pady=3, sticky="w")
                
                if unique_ingredients:
                    # 콤보박스 값 생성 (검색 유형에 따라 보완 정보 표시)
                    # 드롭다운 폭 자동 확장 방지: 표시 텍스트를 최대 50자로 제한
                    _MAX_DISPLAY = 50
                    combo_values = []
                    combo_data_list = []  # 인덱스 기반 원본 데이터 리스트

                    for ing in unique_ingredients:
                        if search_type == "성분명(한글)":
                            # 한글 검색 → 영문, CAS, 기능 표시
                            display_text = f"{ing.name_en or '(영문없음)'} | CAS: {ing.cas_no or '-'} | 기능: {ing.function or '-'}"
                        elif search_type == "성분명(영문)":
                            # 영문 검색 → 한글, CAS, 기능 표시
                            display_text = f"{ing.name_ko or '(한글없음)'} | CAS: {ing.cas_no or '-'} | 기능: {ing.function or '-'}"
                        else:
                            # 전체/CAS No 검색 → 모든 정보 표시
                            display_text = f"{ing.name_ko or '-'} | {ing.name_en or '-'} | CAS: {ing.cas_no or '-'} | 기능: {ing.function or '-'}"

                        # 표시 텍스트 길이 제한 (드롭다운 폭 고정 목적)
                        if len(display_text) > _MAX_DISPLAY:
                            display_text = display_text[:_MAX_DISPLAY] + "…"

                        combo_values.append(display_text)
                        combo_data_list.append({
                            "name_ko": ing.name_ko or "",
                            "name_en": ing.name_en or "",
                            "cas_no": ing.cas_no or "",
                            "function": ing.function or ""
                        })

                    combo = ctk.CTkComboBox(self.lookup_material_frame, values=combo_values, width=350)
                    combo.set(combo_values[0])
                    combo.grid(row=row_idx, column=1, padx=5, pady=3, sticky="w")
                    found_count_total += len(unique_ingredients)

                    # 내보내기용 저장 (콤보박스 참조 + 인덱스 기반 데이터 리스트)
                    self.lookup_grouped_rows.append({
                        "search_term": term,
                        "combo": combo,
                        "combo_values": combo_values,
                        "data_list": combo_data_list,
                        "has_result": True
                    })
                else:
                    # 검색 결과 없음
                    ctk.CTkLabel(self.lookup_material_frame, text="(검색 결과 없음)", text_color="gray", width=350).grid(row=row_idx, column=1, padx=5, pady=3, sticky="w")
                    
                    self.lookup_grouped_rows.append({
                        "search_term": term,
                        "combo": None,
                        "data_map": None,
                        "has_result": False
                    })
                
                row_idx += 1
            
            # 결과 카운트 라벨 업데이트
            count_text = f"검색 완료 (총 {len(search_terms)}개 검색어, {found_count_total}개 성분 발견)"
            self.lookup_result_label.configure(text=count_text)
            
        except Exception as e:
            messagebox.showerror(self.texts.get("error", "오류"), f"검색 중 오류 발생: {e}", parent=self)
            print(f"Error details: {e}")
        finally:
            session.close()




    def _search_by_material_name(self, search_terms_with_empty):
        """원료명으로 검색 - 비슷한 원료 콤보박스 포함 UI (빈 줄 포함)"""
        # 기존 행들 삭제
        self._clear_material_lookup_rows()
        
        # 원료명 프레임 표시
        self._show_lookup_material_frame()
        
        # 헤더 추가
        ctk.CTkLabel(self.lookup_material_frame, text="검색어", font=ctk.CTkFont(weight="bold"), width=150).grid(row=0, column=0, padx=5, pady=5, sticky="w")
        ctk.CTkLabel(self.lookup_material_frame, text="코드", font=ctk.CTkFont(weight="bold"), width=100).grid(row=0, column=1, padx=5, pady=5, sticky="w")
        ctk.CTkLabel(self.lookup_material_frame, text="원료명", font=ctk.CTkFont(weight="bold"), width=200).grid(row=0, column=2, padx=5, pady=5, sticky="w")
        ctk.CTkLabel(self.lookup_material_frame, text="비슷한 원료 선택", font=ctk.CTkFont(weight="bold"), width=250).grid(row=0, column=3, padx=5, pady=5, sticky="w")
        
        session = db_manager.get_session()
        try:
            for row_idx, term in enumerate(search_terms_with_empty, start=1):
                # 빈 줄인 경우 빈 행 추가
                if not term.strip():
                    # 빈 행 추가
                    empty_label = ctk.CTkLabel(self.lookup_material_frame, text="", width=150)
                    empty_label.grid(row=row_idx, column=0, padx=5, pady=3, sticky="w")
                    
                    self.lookup_material_rows.append({
                        "term_label": empty_label,
                        "code_label": None,
                        "name_label": None,
                        "row": row_idx,
                        "is_empty": True
                    })
                    continue
                
                search_pattern = f"%{term}%"
                
                # 먼저 정확히 일치하는 원료 검색
                exact_match = session.query(Material).filter(
                    or_(
                        Material.name == term,
                        Material.name_en == term
                    )
                ).first()
                
                # 비슷한 원료 검색 (정확 일치 제외)
                similar_materials = session.query(Material).filter(
                    or_(
                        Material.name.ilike(search_pattern),
                        Material.name_en.ilike(search_pattern)
                    )
                ).limit(20).all()
                
                # 검색어 라벨
                term_label = ctk.CTkLabel(self.lookup_material_frame, text=term, width=150, anchor="w")
                term_label.grid(row=row_idx, column=0, padx=5, pady=3, sticky="w")
                
                # 코드 라벨 (선택 시 업데이트)
                code_label = ctk.CTkLabel(self.lookup_material_frame, text="", width=100, anchor="w")
                code_label.grid(row=row_idx, column=1, padx=5, pady=3, sticky="w")
                
                # 원료명 라벨 (선택 시 업데이트)  
                name_label = ctk.CTkLabel(self.lookup_material_frame, text="", width=200, anchor="w")
                name_label.grid(row=row_idx, column=2, padx=5, pady=3, sticky="w")
                
                # 정확히 일치하는 원료가 있으면 자동 선택
                if exact_match:
                    code_label.configure(text=exact_match.code)
                    name_label.configure(text=exact_match.name)
                    
                    # 정확 일치 표시 + 변경 버튼
                    match_frame = ctk.CTkFrame(self.lookup_material_frame, fg_color="transparent")
                    match_frame.grid(row=row_idx, column=3, padx=5, pady=3, sticky="w")
                    
                    match_label = ctk.CTkLabel(match_frame, text="✓ 정확 일치", 
                                               text_color="green", font=ctk.CTkFont(weight="bold"))
                    match_label.pack(side="left", padx=(0, 10))
                    
                    # 변경 검색 버튼
                    change_btn = ctk.CTkButton(
                        match_frame,
                        text="변경 검색",
                        width=80,
                        height=25,
                        fg_color="gray50",
                        hover_color="gray40",
                        command=lambda t=term, cl=code_label, nl=name_label, mf=match_frame, ri=row_idx: 
                            self._show_material_search_ui(t, cl, nl, mf, ri)
                    )
                    change_btn.pack(side="left")
                    
                elif similar_materials:
                    # 첫 번째 항목을 기본값으로 설정
                    first_material = similar_materials[0]
                    code_label.configure(text=first_material.code)
                    name_label.configure(text=first_material.name)
                    
                    # 콤보박스 + 검색 버튼 프레임
                    combo_frame = ctk.CTkFrame(self.lookup_material_frame, fg_color="transparent")
                    combo_frame.grid(row=row_idx, column=3, padx=5, pady=3, sticky="w")
                    
                    # 콤보박스 값 생성: "코드 - 원료명"
                    combo_values = [f"{m.code} - {m.name}" for m in similar_materials]
                    
                    combo = ctk.CTkComboBox(
                        combo_frame, 
                        values=combo_values, 
                        width=200,
                        state="normal",  # 편집 가능
                        command=lambda val, cl=code_label, nl=name_label: self._on_material_combo_select(val, cl, nl)
                    )
                    combo.set(combo_values[0])
                    combo.pack(side="left", padx=(0, 5))
                    
                    # 검색 버튼
                    search_btn = ctk.CTkButton(
                        combo_frame,
                        text="🔍",
                        width=30,
                        command=lambda sc=combo, cl=code_label, nl=name_label: self._search_material_in_combo(sc, cl, nl)
                    )
                    search_btn.pack(side="left")
                else:
                    # 검색 결과 없음 - 입력 가능한 콤보박스와 검색 버튼 제공
                    code_label.configure(text="-")
                    name_label.configure(text="(일치하는 원료 없음)")
                    
                    # 검색용 프레임
                    search_frame = ctk.CTkFrame(self.lookup_material_frame, fg_color="transparent")
                    search_frame.grid(row=row_idx, column=3, padx=5, pady=3, sticky="w")
                    
                    # 편집 가능한 콤보박스 (검색어 입력용)
                    search_combo = ctk.CTkComboBox(
                        search_frame,
                        values=[],
                        width=200,
                        state="normal"  # 편집 가능
                    )
                    search_combo.set(term)  # 기존 검색어를 기본값으로
                    search_combo.pack(side="left", padx=(0, 5))
                    
                    # 검색 버튼
                    search_btn = ctk.CTkButton(
                        search_frame,
                        text="🔍",
                        width=30,
                        command=lambda sc=search_combo, cl=code_label, nl=name_label: self._search_material_in_combo(sc, cl, nl)
                    )
                    search_btn.pack(side="left")
                
                # 행 정보 저장 (나중에 초기화용)
                self.lookup_material_rows.append({
                    "term_label": term_label,
                    "code_label": code_label,
                    "name_label": name_label,
                    "row": row_idx
                })
            
            # 결과 카운트 업데이트 (빈 줄 제외)
            actual_count = len([r for r in self.lookup_material_rows if not r.get("is_empty")])
            count_text = self.texts.get("lookup_results_count", "검색 결과: {count}건").format(count=actual_count)
            self.lookup_result_label.configure(text=count_text)
            
        except Exception as e:
            messagebox.showerror(self.texts.get("error", "오류"), f"원료명 검색 중 오류 발생: {e}", parent=self)
        finally:
            session.close()

    def _on_material_combo_select(self, selected_value, code_label, name_label):
        """원료 콤보박스에서 선택 시 코드/원료명 라벨 업데이트"""
        if " - " in selected_value:
            parts = selected_value.split(" - ", 1)
            code_label.configure(text=parts[0])
            name_label.configure(text=parts[1])

    def _search_material_in_combo(self, search_combo, code_label, name_label):
        """콤보박스에서 입력한 검색어로 원료 검색 후 결과를 콤보박스에 표시"""
        search_term = search_combo.get().strip()
        if not search_term:
            return
        
        session = db_manager.get_session()
        try:
            search_pattern = f"%{search_term}%"
            
            # 원료 검색
            materials = session.query(Material).filter(
                or_(
                    Material.name.ilike(search_pattern),
                    Material.name_en.ilike(search_pattern),
                    Material.code.ilike(search_pattern)
                )
            ).limit(20).all()
            
            if materials:
                # 콤보박스 값 업데이트 (편집 가능 상태 유지)
                combo_values = [f"{m.code} - {m.name}" for m in materials]
                search_combo.configure(values=combo_values)  # state는 normal 유지
                search_combo.set(combo_values[0])
                
                # 첫 번째 항목으로 라벨 업데이트
                first_material = materials[0]
                code_label.configure(text=first_material.code)
                name_label.configure(text=first_material.name)
                
                # 콤보박스에 선택 이벤트 연결
                search_combo.configure(
                    command=lambda val, cl=code_label, nl=name_label: self._on_material_combo_select(val, cl, nl)
                )
            else:
                messagebox.showinfo(self.texts.get("notification", "알림"),
                    f"'{search_term}'에 대한 검색 결과가 없습니다.", parent=self)
        except Exception as e:
            messagebox.showerror(self.texts.get("error", "오류"), f"검색 중 오류 발생: {e}", parent=self)
        finally:
            session.close()

    def _show_material_search_ui(self, term, code_label, name_label, match_frame, row_idx):
        """정확 일치 항목에서 변경 검색 UI로 전환"""
        # 기존 match_frame 내용 삭제
        for widget in match_frame.winfo_children():
            widget.destroy()
        
        # 편집 가능한 콤보박스 추가
        search_combo = ctk.CTkComboBox(
            match_frame,
            values=[],
            width=250,
            state="normal"
        )
        search_combo.set(term)
        search_combo.pack(side="left", padx=(0, 5))
        
        # 검색 버튼
        search_btn = ctk.CTkButton(
            match_frame,
            text="🔍",
            width=30,
            command=lambda: self._search_material_in_combo(search_combo, code_label, name_label)
        )
        search_btn.pack(side="left")

    def _clear_material_lookup_rows(self):
        """원료명 검색 결과 행들 삭제"""
        # 스크롤 프레임의 모든 자식 위젯 삭제
        if hasattr(self, 'lookup_material_frame'):
            for widget in self.lookup_material_frame.winfo_children():
                widget.destroy()
        self.lookup_material_rows = []

    def clear_ingredient_lookup_results(self):
        """검색 결과 초기화"""
        # Treeview 초기화
        for item in self.ingredient_lookup_tree.get_children():
            self.ingredient_lookup_tree.delete(item)
        # 원료명 검색 결과 초기화
        self._clear_material_lookup_rows()
        # 그룹화된 성분 검색 결과 초기화
        self.lookup_grouped_rows = []
        # Treeview 표시
        self._show_lookup_treeview()
        # 카운트 초기화
        self.lookup_result_label.configure(
            text=self.texts.get("lookup_results_count", "검색 결과: {count}건").format(count=0))
        # 텍스트박스 초기화
        self.ingredient_lookup_textbox.delete("0.0", "end")

    def export_ingredient_lookup_to_excel(self):
        """성분/원료 조회 결과를 표준 Excel로 내보냅니다. (선택된 원료가 있으면 선택된 것만 내보내고, 없으면 안내 또는 전체 내보내기)"""
        data = []

        # 1. 스마트 매칭 / 원료 조회 카드 뷰 데이터 수집
        if hasattr(self, 'selected_lookup_items') and self.selected_lookup_items:
            # 먼저 체크박스가 활성화된 항목이 있는지 확인
            checked_items = [
                (mat_id, item_tuple) 
                for mat_id, item_tuple in self.selected_lookup_items.items() 
                if item_tuple[0].get()
            ]

            # 선택된 항목이 있다면 선택된 원료만 타겟으로 하고, 없다면 전체 표시된 원료를 타겟으로 함
            target_items = checked_items if checked_items else list(self.selected_lookup_items.items())

            row_num = 0
            for mat_id, item_tuple in target_items:
                chk_var = item_tuple[0]
                mat = item_tuple[1]
                row_num += 1
                supplier_name = mat.supplier.name if mat.supplier else (mat.manufacturer or "-")
                reg_date = mat.reg_date or (mat.created_at.strftime('%Y-%m-%d') if mat.created_at else "-")
                price = mat.unit_price or 0.0

                ing_names = []
                if mat.ingredients:
                    for ing in mat.ingredients:
                        i_name = f"{ing.name_ko} ({ing.name_en})" if ing.name_en else ing.name_ko
                        r_str = f" [{ing.composition_ratio}%]" if ing.composition_ratio else ""
                        ing_names.append(f"{i_name}{r_str}")
                ing_summary = ", ".join(ing_names) if ing_names else "-"

                data.append({
                    "No.": row_num,
                    "원료코드": mat.code or "",
                    "원료명(국문)": mat.name or "",
                    "영문원료명(INCI)": mat.name_en or "",
                    "공급처": supplier_name,
                    "입고/등록일": reg_date,
                    "단가(₩/kg)": price,
                    "포함전성분": ing_summary
                })

        # 2. 일반 Treeview 검색 모드 데이터 수집
        elif hasattr(self, 'ingredient_lookup_tree'):
            # Treeview에서 선택된 행이 있는지 확인
            selected_iids = self.ingredient_lookup_tree.selection()
            target_iids = selected_iids if selected_iids else self.ingredient_lookup_tree.get_children()

            cols = self.ingredient_lookup_tree["columns"]
            headings = [self.ingredient_lookup_tree.heading(col)["text"] for col in cols]

            row_num = 0
            for iid in target_iids:
                row_num += 1
                vals = self.ingredient_lookup_tree.item(iid)["values"]
                row_dict = {"No.": row_num}
                for h, v in zip(headings, vals):
                    row_dict[h] = v
                data.append(row_dict)

        if not data:
            messagebox.showwarning(self.texts.get("warning", "경고"),
                self.texts.get("no_data_to_export", "내보낼 데이터가 없습니다. 먼저 원료를 선택하거나 검색하세요."), parent=self)
            return

        from datetime import datetime
        default_filename = f"원료_성분조회_{datetime.now().strftime('%Y%m%d_%H%M')}.xlsx"

        file_path = filedialog.asksaveasfilename(
            initialfile=default_filename,
            defaultextension=".xlsx",
            filetypes=[("Excel files", "*.xlsx"), ("All files", "*.*")],
            title=self.texts.get("export_lookup_to_excel", "Excel로 내보내기"),
            parent=self
        )

        if not file_path:
            return

        try:
            import pandas as pd
            from openpyxl.styles import Border, Side, Alignment
            from openpyxl import load_workbook

            df = pd.DataFrame(data)
            df.to_excel(file_path, index=False, engine='openpyxl')

            wb = load_workbook(file_path)
            ws = wb.active

            thin_border = Border(
                left=Side(style='thin'),
                right=Side(style='thin'),
                top=Side(style='thin'),
                bottom=Side(style='thin')
            )

            for col in ws.columns:
                max_length = 0
                column_letter = col[0].column_letter

                for cell in col:
                    cell.border = thin_border
                    cell.alignment = Alignment(vertical='center', wrap_text=True)

                    if cell.value:
                        cell_length = 0
                        for char in str(cell.value):
                            if ord(char) > 127:
                                cell_length += 2
                            else:
                                cell_length += 1
                        max_length = max(max_length, cell_length)

                adjusted_width = max(max_length + 2, 12)
                ws.column_dimensions[column_letter].width = adjusted_width

            wb.save(file_path)
            try:
                os.startfile(os.path.abspath(file_path))
            except Exception:
                pass

        except Exception as e:
            messagebox.showerror(self.texts.get("export_error", "내보내기 오류"),
                f"Excel 내보내기 중 오류 발생: {e}", parent=self)


    def import_ingredient_lookup_from_excel(self):
        """Excel에서 성분명/CAS No 리스트를 가져와서 검색"""
        file_path = filedialog.askopenfilename(
            filetypes=[("Excel files", "*.xlsx *.xls"), ("All files", "*.*")],
            title=self.texts.get("import_lookup_from_excel", "Excel에서 가져오기"),
            parent=self
        )
        
        if not file_path:
            return

        try:
            import pandas as pd
            
            df = pd.read_excel(file_path, engine='openpyxl')
            
            # 첫 번째 컬럼의 값들을 검색어로 사용
            if df.empty or len(df.columns) == 0:
                messagebox.showwarning(self.texts.get("warning", "경고"),
                    "Excel 파일에 데이터가 없습니다.", parent=self)
                return
            
            # [수정] 컬럼명 기반으로 데이터 추출 우선 (한글전성분 -> CAS NO. -> 첫번째 컬럼 순)
            target_col = None
            
            # 컬럼명 정규화 (공백 제거 등)
            normalized_cols = {str(col).strip(): col for col in df.columns}
            
            if '한글전성분' in normalized_cols:
                target_col = normalized_cols['한글전성분']
            elif 'CAS NO.' in normalized_cols:
                target_col = normalized_cols['CAS NO.']
            elif 'CAS No.' in normalized_cols: # 대소문자 변형 대응
                 target_col = normalized_cols['CAS No.']
            
            if target_col:
                search_terms = df[target_col].dropna().astype(str).tolist()
            else:
                # 지정된 헤더가 없으면 첫 번째 컬럼 사용
                search_terms = df.iloc[:, 0].dropna().astype(str).tolist()
            
            if not search_terms:
                messagebox.showwarning(self.texts.get("warning", "경고"),
                    "검색할 데이터가 없습니다.", parent=self)
                return
            
            # 텍스트박스에 검색어 입력
            self.ingredient_lookup_textbox.delete("0.0", "end")
            self.ingredient_lookup_textbox.insert("0.0", "\n".join(search_terms))
            
            # 자동 검색 실행
            self.search_ingredients_by_list()
            
        except Exception as e:
            messagebox.showerror(self.texts.get("error", "오류"),
                f"Excel 파일 읽기 중 오류 발생: {e}", parent=self)

    # ==================== [v64] 복합원료 스마트 매칭 & 처방 연동 엔진 ====================
    def analyze_complex_ingredients(self):
        """고객사 의뢰 전성분 목록을 분석하여 복합원료 다중 일치도 및 창고 보유 이력을 우선순위로 정렬 표시"""
        input_text = self.ingredient_lookup_textbox.get("0.0", "end-1c").strip()
        placeholder = self.texts.get("ingredient_lookup_placeholder", "")
        
        if not input_text or input_text == placeholder:
            messagebox.showwarning("입력 확인", "분석할 전성분 목록을 줄 단위 또는 콤마로 입력하세요.", parent=self)
            return

        raw_lines = [line.strip() for line in input_text.split('\n') if line.strip()]
        search_terms = []
        for line in raw_lines:
            if ',' in line:
                for part in line.split(','):
                    clean_p = part.strip().rstrip(',')
                    if clean_p and clean_p not in search_terms:
                        search_terms.append(clean_p)
            else:
                if line not in search_terms:
                    search_terms.append(line)

        if not search_terms:
            return

        is_eng = getattr(self, 'lookup_export_lang_var', None) and "영문" in self.lookup_export_lang_var.get()

        session = db_manager.get_session()
        try:
            all_materials = session.query(Material).options(
                joinedload(Material.ingredients),
                joinedload(Material.supplier)
            ).filter(Material.is_active == True).all()

            matched_items = []
            normalized_terms = {t.lower().replace(" ", ""): t for t in search_terms}
            
            for mat in all_materials:
                if not mat.ingredients:
                    continue
                
                matched_ing_list = []
                exact_match_count = 0

                for ing in mat.ingredients:
                    ing_ko = (ing.name_ko or "").strip()
                    ing_en = (ing.name_en or "").strip()
                    ing_cas = (ing.cas_no or "").strip()
                    
                    ko_norm = ing_ko.lower().replace(" ", "")
                    en_norm = ing_en.lower().replace(" ", "")
                    cas_norm = ing_cas.lower().replace(" ", "")
                    
                    is_match = False
                    is_exact = False
                    for norm_t in normalized_terms.keys():
                        if not norm_t:
                            continue
                        # 1) 정확 일치 (Exact Match)
                        if norm_t == ko_norm or norm_t == en_norm or (cas_norm and norm_t == cas_norm):
                            is_match = True
                            is_exact = True
                            break
                        # 2) 부분 일치 (Partial Match)
                        elif (norm_t in ko_norm) or (ko_norm and ko_norm in norm_t) or \
                             (norm_t in en_norm) or (en_norm and en_norm in norm_t):
                            is_match = True
                            break
                    
                    if is_match:
                        if is_exact:
                            exact_match_count += 1
                        matched_ing_list.append({
                            "name_ko": ing_ko,
                            "name_en": ing_en,
                            "is_exact": is_exact,
                            "ratio": ing.composition_ratio or 0.0
                        })

                m_count = len(matched_ing_list)
                t_count = len(mat.ingredients)
                
                if m_count > 0:
                    is_blend = t_count >= 2
                    supplier_name = mat.supplier.name if mat.supplier else (mat.manufacturer or "-")
                    reg_info = f"입고: {mat.reg_date or (mat.created_at.strftime('%Y-%m-%d') if mat.created_at else '-')}"
                    price_info = f"₩{mat.unit_price:,.0f}/kg" if mat.unit_price else "단가 미등록"
                    
                    # 원료에 포함된 모든 전성분을 배합비 순서대로 태그로 구성 (정확일치 성분은 '✓' 강조)
                    tags = []
                    cas_list = []
                    func_list = []
                    
                    sorted_all_ings = sorted(mat.ingredients, key=lambda ig: ig.composition_ratio or 0.0, reverse=True)
                    for ing in sorted_all_ings:
                        i_ko = (ing.name_ko or "").strip()
                        i_en = (ing.name_en or "").strip()
                        i_cas = (ing.cas_no or "").strip()
                        r_str = f" ({ing.composition_ratio}%)" if ing.composition_ratio and ing.composition_ratio > 0 else ""
                        name_display = i_en if is_eng and i_en else i_ko
                        
                        # 정확 일치 여부 확인
                        i_ko_n = i_ko.lower().replace(" ", "")
                        i_en_n = i_en.lower().replace(" ", "")
                        i_cas_n = i_cas.lower().replace(" ", "")
                        
                        is_exact_tag = any(
                            norm_t == i_ko_n or norm_t == i_en_n or (i_cas_n and norm_t == i_cas_n)
                            for norm_t in normalized_terms.keys()
                        )
                        is_partial_tag = any(
                            (norm_t in i_ko_n) or (i_ko_n and i_ko_n in norm_t) or
                            (norm_t in i_en_n) or (i_en_n and i_en_n in norm_t)
                            for norm_t in normalized_terms.keys()
                        )
                        
                        if is_exact_tag:
                            mark = "✓ "
                        elif is_partial_tag:
                            mark = "△ "
                        else:
                            mark = "• "
                            
                        tags.append(f"{mark}{name_display}{r_str}")

                        if ing.cas_no and ing.cas_no not in cas_list:
                            cas_list.append(ing.cas_no)
                        if ing.function and ing.function not in func_list:
                            func_list.append(ing.function)
                    
                    # 원료 성분이 제시된 검색 성분에 100% 정확하게 모두 매칭되는지
                    is_exact_full_match = (exact_match_count == t_count)
                    exact_rate = (exact_match_count / max(t_count, 1)) * 100.0
                    match_rate = (m_count / max(t_count, 1)) * 100.0

                    if is_exact_full_match:
                        badge = f"🎯 100% 정확 일치 ({exact_match_count}/{t_count}개)" if not is_eng else f"🎯 Exact Match ({exact_match_count}/{t_count})"
                        b_color = "#16A34A"  # 선명한 초록색
                    elif is_blend:
                        badge = f"복합원료 (정확 {exact_match_count}개 | 총 {m_count}/{t_count}개)" if not is_eng else f"Blend (Exact {exact_match_count} | {m_count}/{t_count})"
                        b_color = "#4F46E5"
                    else:
                        badge = "단일 성분" if not is_eng else "Single Ingredient"
                        b_color = "#0288D1"

                    matched_items.append({
                        "material": mat,
                        "code": mat.code,
                        "name": mat.name_en if is_eng and mat.name_en else mat.name,
                        "badge_text": badge,
                        "badge_color": b_color,
                        "supplier_text": supplier_name,
                        "stock_text": f"{reg_info} | {price_info}",
                        "tags": tags,
                        "cas_no": ", ".join(cas_list),
                        "function": ", ".join(func_list),
                        "exact_match_count": exact_match_count,
                        "match_count": m_count,
                        "total_ing_count": t_count,
                        "is_blend": is_blend,
                        "is_exact_full_match": is_exact_full_match,
                        "exact_rate": exact_rate,
                        "match_rate": match_rate,
                    })

            # [스마트 매칭 엄격한 정합도 정렬 규칙]:
            # 1. 원료 내 전성분이 검색 성분과 100% 정확 일치하는 원료 최상단 (0순위: 🎯 100% 정확 일치)
            # 2. 정확 일치 성분 개수(exact_match_count) 많은 순서 (3개 > 2개 > 1개)
            # 3. 정확 일치율(exact_rate) 높은 순서 (예: 2/2개 100% > 2/3개 66% > 2/5개 40%)
            # 4. 전체 일치 개수(match_count) 많은 순서
            # 5. 불필요한 성분이 적은 순서 (total_ing_count 오름차순: 1개, 2개, 3개...)
            # 6. 코드번호 순
            matched_items.sort(key=lambda x: (
                0 if x["is_exact_full_match"] else 1, # 100% 정확 일치 0순위
                -x["exact_match_count"],              # 정확 일치 개수 많은 순 (내림차순)
                -x["exact_rate"],                     # 정확 일치율 높은 순 (내림차순)
                -x["match_count"],                    # 전체 일치 개수 많은 순 (내림차순)
                x["total_ing_count"],                 # 전체 성분 수 적은 순 (오름차순)
                0 if x["is_blend"] else 1,            # 복합원료 우선
                x["code"] or ""                       # 코드번호 순
            ))

            title_info = f"✨ 복합원료 스마트 매칭 분석 (의뢰 성분 {len(search_terms)}개)" if not is_eng else f"✨ Complex Blend Smart Match ({len(search_terms)} inputs)"
            self._render_unified_lookup_results(title_info, matched_items, len(search_terms))

            if not matched_items:
                messagebox.showinfo("분석 알림", "의뢰된 전성분과 일치하는 원료를 창고에서 찾을 수 없습니다.", parent=self)

        except Exception as e:
            messagebox.showerror("분석 오류", f"스마트 매칭 분석 중 오류: {e}", parent=self)
            print(f"[COMPLEX-ERROR] {e}")
        finally:
            session.close()

    def _create_formulation_from_selected_complex(self):
        """스마트 매칭에서 체크된 원료들을 신규 처방 개발창으로 전달하여 즉시 처방 작성"""
        selected_mats = []
        if hasattr(self, 'selected_lookup_items'):
            for mat_id, item_tuple in self.selected_lookup_items.items():
                chk_var = item_tuple[0]
                mat = item_tuple[1]
                if chk_var.get():
                    selected_mats.append(mat)

        if not selected_mats:
            messagebox.showwarning("선택 필요", "처방에 추가할 원료를 1개 이상 체크박스로 선택하세요.", parent=self)
            return

        try:
            popup = FormulationEditPopup(
                master=self,
                user=self.current_user,
                app=self.app,
                on_save_callback=self.app.refresh_data_in_all_frames,
                formulation_id=None
            )
            if hasattr(popup, 'add_materials_from_lookup'):
                popup.add_materials_from_lookup(selected_mats)
            popup.focus()
        except Exception as e:
            messagebox.showerror("처방 생성 오류", f"처방 작성 창 연동 중 오류 발생: {e}", parent=self)


    def on_formulation_sub_tab_change(self):
        """하위 탭 전환 시, '생산 처방' 탭이 선택되면 목록을 자동 복구/갱신합니다."""
        try:
            current = self.formulation_sub_tab_view.get()
        except Exception:
            return
        if getattr(self, 'production_tab_label', None) and current == self.production_tab_label:
            # 생산처방 트리가 비어있다면 '전체 목록'로 자동 복구
            if hasattr(self, 'production_tree'):
                try:
                    if len(self.production_tree.get_children()) == 0:
                        # 선택된 실험처방이 있으면 필터된 목록, 없으면 전역 목록을 표시합니다.
                        # 기존 show_all_production_list는 선택된 처방 ID를 해제하므로 사용하지 않습니다.
                        self.refresh_production_list()
                except Exception:
                    # 문제가 있어도 치명적이지 않으므로 조용히 무시
                    pass

    def setup_production_catalog_tab(self, tab_frame):
        tab_frame.grid_columnconfigure(0, weight=1)
        tab_frame.grid_rowconfigure(1, weight=1)

        header = ctk.CTkFrame(tab_frame, fg_color="transparent")
        header.grid(row=0, column=0, sticky="ew", padx=10, pady=(10,5))
        ctk.CTkLabel(header, text="모든 생산처방 목록", font=ctk.CTkFont(size=16, weight="bold")).pack(side="left")
        ctk.CTkButton(header, text="새로고침", width=90, command=self.load_production_catalog).pack(side="right")

        list_frame = ctk.CTkFrame(tab_frame, fg_color="transparent")
        list_frame.grid(row=1, column=0, sticky="nsew", padx=10, pady=(0,10))
        list_frame.grid_columnconfigure(0, weight=1)
        list_frame.grid_rowconfigure(0, weight=1)

        cols = ("name","pcode","revision","status","eff","base","created","lab")
        self.prod_catalog_tree = ttk.Treeview(list_frame, columns=cols, show="headings", selectmode="browse")
        self.prod_catalog_tree.heading("name", text="제품명"); self.prod_catalog_tree.column("name", width=260, stretch=True)
        self.prod_catalog_tree.heading("pcode", text="생산코드"); self.prod_catalog_tree.column("pcode", width=120)
        self.prod_catalog_tree.heading("revision", text="차수"); self.prod_catalog_tree.column("revision", width=80)
        self.prod_catalog_tree.heading("status", text="상태"); self.prod_catalog_tree.column("status", width=80)
        self.prod_catalog_tree.heading("eff", text="제조일"); self.prod_catalog_tree.column("eff", width=120)
        self.prod_catalog_tree.heading("base", text="생산량(kg)"); self.prod_catalog_tree.column("base", width=120, anchor="e")
        self.prod_catalog_tree.heading("created", text="생성일"); self.prod_catalog_tree.column("created", width=140)
        self.prod_catalog_tree.heading("lab", text="LAB NO."); self.prod_catalog_tree.column("lab", width=120)
        self.prod_catalog_tree.grid(row=0, column=0, sticky="nsew")
        pc_scroll = ttk.Scrollbar(list_frame, orient="vertical", command=self.prod_catalog_tree.yview)
        pc_scroll.grid(row=0, column=1, sticky="ns")
        self.prod_catalog_tree.configure(yscrollcommand=pc_scroll.set)

        self.load_production_catalog()

    def load_production_catalog(self):
        if not hasattr(self, 'prod_catalog_tree'):
            return
        for i in self.prod_catalog_tree.get_children():
            self.prod_catalog_tree.delete(i)
        session = db_manager.get_session()
        try:
            rows = (
                session.query(ProductionFormulation)
                .order_by(ProductionFormulation.created_at.desc())
                .all()
            )
            for r in rows:
                # 상태/권한 정책: 열람 가능한 항목만 목록에 표시
                try:
                    if not self.can_view_production(r):
                        continue
                except Exception:
                    pass
                eff = r.effective_date.strftime('%Y-%m-%d') if r.effective_date else ''
                created = r.created_at.strftime('%Y-%m-%d %H:%M') if r.created_at else ''
                try:
                    base = f"{((r.base_weight_g or 0)/1000):,.1f}"
                except Exception:
                    base = f"{(r.base_weight_g or 0)}"
                self.prod_catalog_tree.insert('', 'end', iid=r.id, values=(r.product_name or '', r.production_code or '', r.revision or '', r.status or '', eff, base, created, r.lab_no or ''))
        finally:
            session.close()

    def setup_formulation_list_tab(self, parent_tab):
        """'처방 목록' 서브 탭의 UI를 설정합니다. (폴더 카드 UI)"""
        parent_tab.grid_columnconfigure(0, weight=1)
        parent_tab.grid_rowconfigure(0, weight=0)
        parent_tab.grid_rowconfigure(1, weight=1)
        parent_tab.grid_rowconfigure(2, weight=0, minsize=54)

        # --- 헤더 및 필터 ---
        header_frame = ctk.CTkFrame(parent_tab, fg_color="transparent")
        header_frame.grid(row=0, column=0, sticky="ew", padx=10, pady=(4, 4))
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

        # 검색창 및 검색 버튼 추가
        self.list_search_entry = ctk.CTkEntry(filter_frame, width=200, placeholder_text=self.texts['search'])
        self.list_search_entry.pack(side="left", padx=(0, 5))
        self.list_search_entry.bind("<Return>", lambda e: self.load_folders()) # 엔터키 검색

        self.list_search_button = ctk.CTkButton(filter_frame, text=self.texts['search'], width=60, command=lambda: self.load_folders())
        self.list_search_button.pack(side="left")

        # --- 컨텐츠 영역 (폴더/파일 목록) ---
        self.content_frame = ctk.CTkFrame(parent_tab, fg_color="transparent")
        self.content_frame.grid(row=1, column=0, sticky="nsew", padx=10, pady=(2, 6))
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
        self.back_button = ctk.CTkButton(file_view_header, text=self.texts['back_to_folders'], width=75, command=self.show_folder_view, font=("", 11))
        self.back_button.pack(side="left", padx=(0, 5))

        self.compare_button = ctk.CTkButton(file_view_header, text=self.texts['compare_history'], width=75, command=self.open_comparison_popup, font=("", 11))
        self.compare_button.pack(side="left", padx=(0, 5))

        self.folder_history_button = ctk.CTkButton(file_view_header, text=self.texts['view_all_history'], width=90, command=self.open_folder_history_popup, font=("", 11))
        self.folder_history_button.pack(side="left", padx=(0, 5))

        # 선택 초기화 버튼 추가
        self.reset_selection_button = ctk.CTkButton(file_view_header, text=self.texts['reset_selection'], width=75, command=self.reset_selection_and_tabs, font=("", 11))
        self.reset_selection_button.pack(side="left", padx=(0, 5))

        # 샘플 발송/수정: QC를 제외한 연구권한(RD/RQ/RQD/MSAD)에게만 표시
        if hasattr(self.current_user, 'has_research_access') and self.current_user.has_research_access():
            self.edit_sample_button = ctk.CTkButton(file_view_header, text=self.texts['edit_sample_count'], width=80, command=self.edit_sample_sent_count, font=("", 11))
            self.edit_sample_button.pack(side="right", padx=(5, 0))

            self.send_sample_button = ctk.CTkButton(file_view_header, text=self.texts['send_sample'], width=75, command=self.increment_sample_sent_count, font=("", 11))
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

        # --- [v65 하단 액션 바: 상단 헤더와 일관된 깔끔한 투명 레이아웃] ---
        bottom_button_frame = ctk.CTkFrame(parent_tab, fg_color="transparent")
        bottom_button_frame.grid(row=2, column=0, padx=10, pady=(4, 14), sticky="ew")
        bottom_button_frame.grid_columnconfigure(0, weight=1)

        bar_inner = ctk.CTkFrame(bottom_button_frame, fg_color="transparent")
        bar_inner.pack(fill="x", expand=True)

        # [좌측 그룹: 핵심 작성 & 편집]
        left_grp = ctk.CTkFrame(bar_inner, fg_color="transparent")
        left_grp.pack(side="left")

        btn_font = ctk.CTkFont(size=12, weight="bold")
        btn_h = 32

        self.new_button = ctk.CTkButton(
            left_grp, text="➕ 신규 처방", width=95, height=btn_h, corner_radius=6,
            font=btn_font, fg_color="#1D4ED8", hover_color="#1E40AF",
            command=lambda: self.open_formulation_popup(edit_mode=False)
        )
        self.new_button.pack(side="left", padx=3)

        self.edit_button = ctk.CTkButton(
            left_grp, text="✏️ 수정", width=75, height=btn_h, corner_radius=6,
            font=btn_font, fg_color="#0284C7", hover_color="#0369A1",
            command=lambda: self.open_formulation_popup(edit_mode=True)
        )
        self.edit_button.pack(side="left", padx=3)

        self.copy_button = ctk.CTkButton(
            left_grp, text="📋 처방 복사", width=90, height=btn_h, corner_radius=6,
            font=btn_font, fg_color="#16A34A", hover_color="#15803D",
            command=self.copy_formulation
        )
        self.copy_button.pack(side="left", padx=3)

        self.change_client_button = ctk.CTkButton(
            left_grp, text="🏢 업체 변경", width=90, height=btn_h, corner_radius=6,
            font=btn_font, fg_color="#EA580C", hover_color="#C2410C",
            command=self.change_formulation_client
        )
        self.change_client_button.pack(side="left", padx=3)

        self.create_package_button = ctk.CTkButton(
            left_grp, text="📦 패키지 저장", width=95, height=btn_h, corner_radius=6,
            font=btn_font, fg_color="#475569", hover_color="#334155",
            command=self.create_document_package
        )
        self.create_package_button.pack(side="left", padx=3)

        self.delete_button = ctk.CTkButton(
            left_grp, text="🗑️ 삭제", width=70, height=btn_h, corner_radius=6,
            font=btn_font, fg_color="#DC2626", hover_color="#B91C1C",
            command=self.delete_formulation
        )
        self.delete_button.pack(side="left", padx=3)

        # [우측 그룹: 엑셀 출력 & 관리자 일괄 관리]
        right_grp = ctk.CTkFrame(bar_inner, fg_color="transparent")
        right_grp.pack(side="right", fill="y")

        # 단일/전체 엑셀 내보내기
        self.export_single_button = ctk.CTkButton(
            right_grp, text="📥 처방 엑셀 내보내기", width=145, height=btn_h, corner_radius=6,
            font=btn_font, fg_color="#0D9488", hover_color="#0F766E",
            command=self.export_selected_formulation_to_excel
        )
        self.export_single_button.pack(side="left", padx=3)

        if self.current_user.is_admin:
            # 관리자 일괄 옵션 메뉴
            self.export_all_button = ctk.CTkButton(
                right_grp, text="📤 전체 내보내기", width=105, height=btn_h, corner_radius=6,
                font=btn_font, fg_color="#4B5563", hover_color="#374151",
                command=self.export_all_formulations
            )
            self.export_all_button.pack(side="left", padx=3)

            self.import_all_button = ctk.CTkButton(
                right_grp, text="📂 전체 가져오기", width=105, height=btn_h, corner_radius=6,
                font=btn_font, fg_color="#4B5563", hover_color="#374151",
                command=self.import_all_formulations
            )
            self.import_all_button.pack(side="left", padx=3)

            self.export_logs_button = ctk.CTkButton(
                right_grp, text="📜 이력", width=65, height=btn_h, corner_radius=6,
                font=btn_font, fg_color="#4B5563", hover_color="#374151",
                command=self.export_change_logs
            )
            self.export_logs_button.pack(side="left", padx=3)

            self.delete_all_button = ctk.CTkButton(
                right_grp, text="⚠️ 전체 삭제", width=85, height=btn_h, corner_radius=6,
                font=btn_font, fg_color="#B91C1C", hover_color="#991B1B",
                command=self.delete_all_formulations
            )
            self.delete_all_button.pack(side="left", padx=3)

        self.show_folder_view() # 초기 화면은 폴더 뷰

    def setup_quotation_tab(self, tab_frame):
        """견적 탭의 UI를 설정합니다."""
        tab_frame.grid_columnconfigure(0, weight=1)
        tab_frame.grid_rowconfigure(1, weight=1) # Treeview

        # --- 컨트롤 프레임 ---
        control_frame = ctk.CTkFrame(tab_frame, fg_color="transparent")
        control_frame.grid(row=0, column=0, padx=10, pady=(0, 5), sticky="ew")

        # --- 좌측 버튼들 ---
        left_button_frame = ctk.CTkFrame(control_frame, fg_color="transparent")
        left_button_frame.pack(side="left")
        ctk.CTkButton(left_button_frame, text=self.texts['create_quotation'], width=80, command=self.load_formulation_for_quotation, font=("", 11)).pack(side="left")
        ctk.CTkButton(left_button_frame, text="📊 견적서 (KO)", width=85, command=lambda: self.export_quotation(lang="ko"), font=("", 11)).pack(side="left", padx=(4, 0))
        ctk.CTkButton(left_button_frame, text="🌐 영문 견적 (EN)", width=95, fg_color="#1565C0", hover_color="#0D47A1", command=lambda: self.export_quotation(lang="en"), font=("", 11)).pack(side="left", padx=(4, 0))
        ctk.CTkButton(left_button_frame, text=self.texts['delete_selected'], width=75, fg_color="#D32F2F", hover_color="#B71C1C", command=self.delete_selected_quotation_item, font=("", 11)).pack(side="left", padx=(4, 0))

        # --- 우측 버튼 및 입력창 ---
        right_control_frame = ctk.CTkFrame(control_frame, fg_color="transparent")
        right_control_frame.pack(side="right")
        
        ctk.CTkLabel(right_control_frame, text=self.texts['base_weight_g'], font=("", 11)).pack(side="left", padx=(20, 5))
        self.quotation_weight_entry = ctk.CTkEntry(right_control_frame, width=80, justify="right", font=("", 11))
        self.quotation_weight_entry.insert(0, "1000") # 기본값 1kg
        self.quotation_weight_entry.bind("<KeyRelease>", lambda e: self.recalculate_quotation())
        self.quotation_weight_entry.pack(side="left")
        ctk.CTkButton(right_control_frame, text="to 100", width=60, fg_color="#2B7A3B", hover_color="#236030", command=self.normalize_quotation_to_100, font=("", 11)).pack(side="left", padx=(5, 5))
        ctk.CTkButton(right_control_frame, text=self.texts['add_material'], width=75, command=self.open_add_material_for_quotation, font=("", 11)).pack(side="left", padx=3)
        ctk.CTkButton(right_control_frame, text=self.texts['edit_ratio'], width=75, command=self.edit_selected_quotation_item, font=("", 11)).pack(side="left", padx=3)

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

        # --- [v64] 견적 하단 통합 영역 (좌: 제조/원가 부가비용 및 단가 산출, 우: 원료 원가 및 최종 견적) ---
        bottom_summary_container = ctk.CTkFrame(tab_frame, fg_color="transparent")
        bottom_summary_container.grid(row=3, column=0, columnspan=2, padx=10, pady=(5, 10), sticky="ew")
        bottom_summary_container.grid_columnconfigure(0, weight=1) # 좌측 부가비용 (50%)
        bottom_summary_container.grid_columnconfigure(1, weight=1) # 우측 원가/최종견적 (50%)

        # ----------------------------------------------------
        # [좌측 영역] 추가 부가 비용 (반제품/완제품 모드 지원)
        # ----------------------------------------------------
        self.quotation_type_var = ctk.StringVar(value="semi") # 기본 활성화: "semi" (반제품)

        left_extra_frame = ctk.CTkFrame(bottom_summary_container, fg_color=("#F9FAFB", "#242526"), border_width=1, border_color=("#E5E7EB", "#333538"), corner_radius=8)
        left_extra_frame.grid(row=0, column=0, padx=(0, 10), pady=0, sticky="nsew")
        left_extra_frame.grid_columnconfigure(1, weight=1)
        left_extra_frame.grid_columnconfigure(3, weight=1)
        self.quotation_left_extra_frame = left_extra_frame

        # 좌측 상단: 타이틀 및 반제품/완제품 토글 세그먼트
        title_box = ctk.CTkFrame(left_extra_frame, fg_color="transparent")
        title_box.grid(row=0, column=0, columnspan=4, padx=10, pady=(8, 6), sticky="ew")
        title_box.grid_columnconfigure(0, weight=1)

        ctk.CTkLabel(
            title_box, 
            text="견적 산출 구분", 
            font=ctk.CTkFont(size=12, weight="bold"),
            text_color=("#111827", "#F3F4F6")
        ).pack(side="left")

        self.quotation_type_segmented = ctk.CTkSegmentedButton(
            title_box,
            values=["반제품 (벌크)", "완제품 (용기포함)"],
            variable=self.quotation_type_var,
            command=self._on_quotation_type_changed,
            height=26,
            font=ctk.CTkFont(size=11)
        )
        self.quotation_type_segmented.set("반제품 (벌크)")
        self.quotation_type_segmented.pack(side="right")

        # 1행: 인력비 / 제조비 (반제품/완제품 공통)
        self.quotation_labor_lbl = ctk.CTkLabel(left_extra_frame, text="인력비 (원):", font=ctk.CTkFont(size=11))
        self.quotation_labor_lbl.grid(row=1, column=0, padx=(10, 4), pady=3, sticky="w")
        self.quotation_labor_entry = ctk.CTkEntry(left_extra_frame, width=90, height=26, justify="right", font=("", 11))
        self.quotation_labor_entry.insert(0, "0")
        self.quotation_labor_entry.grid(row=1, column=1, padx=(0, 10), pady=3, sticky="ew")
        self.quotation_labor_entry.bind("<KeyRelease>", lambda e: self.recalculate_quotation())

        self.quotation_mfg_lbl = ctk.CTkLabel(left_extra_frame, text="제조비 (원):", font=ctk.CTkFont(size=11))
        self.quotation_mfg_lbl.grid(row=1, column=2, padx=(5, 4), pady=3, sticky="w")
        self.quotation_mfg_cost_entry = ctk.CTkEntry(left_extra_frame, width=90, height=26, justify="right", font=("", 11))
        self.quotation_mfg_cost_entry.insert(0, "0")
        self.quotation_mfg_cost_entry.grid(row=1, column=3, padx=(0, 10), pady=3, sticky="ew")
        self.quotation_mfg_cost_entry.bind("<KeyRelease>", lambda e: self.recalculate_quotation())

        # 2행: 운송비(공통) / 용기비(완제품 전용)
        self.quotation_shipping_lbl = ctk.CTkLabel(left_extra_frame, text="운송비 (원):", font=ctk.CTkFont(size=11))
        self.quotation_shipping_lbl.grid(row=2, column=0, padx=(10, 4), pady=3, sticky="w")
        self.quotation_shipping_entry = ctk.CTkEntry(left_extra_frame, width=90, height=26, justify="right", font=("", 11))
        self.quotation_shipping_entry.insert(0, "0")
        self.quotation_shipping_entry.grid(row=2, column=1, padx=(0, 10), pady=3, sticky="ew")
        self.quotation_shipping_entry.bind("<KeyRelease>", lambda e: self.recalculate_quotation())

        self.quotation_container_lbl = ctk.CTkLabel(left_extra_frame, text="용기 (원):", font=ctk.CTkFont(size=11))
        self.quotation_container_lbl.grid(row=2, column=2, padx=(5, 4), pady=3, sticky="w")
        self.quotation_container_entry = ctk.CTkEntry(left_extra_frame, width=90, height=26, justify="right", font=("", 11))
        self.quotation_container_entry.insert(0, "0")
        self.quotation_container_entry.grid(row=2, column=3, padx=(0, 10), pady=3, sticky="ew")
        self.quotation_container_entry.bind("<KeyRelease>", lambda e: self.recalculate_quotation())

        # 3행: 개당 용량(g) & 생산 수량(EA) - 완제품 전용
        self.quotation_capacity_lbl = ctk.CTkLabel(left_extra_frame, text="개당 용량(g):", font=ctk.CTkFont(size=11, weight="bold"))
        self.quotation_capacity_lbl.grid(row=3, column=0, padx=(10, 4), pady=3, sticky="w")
        self.quotation_unit_capacity_entry = ctk.CTkEntry(left_extra_frame, width=90, height=26, justify="right", font=("", 11))
        self.quotation_unit_capacity_entry.insert(0, "50")
        self.quotation_unit_capacity_entry.grid(row=3, column=1, padx=(0, 10), pady=3, sticky="ew")
        self.quotation_unit_capacity_entry.bind("<KeyRelease>", self._on_unit_capacity_changed)

        self.quotation_count_lbl = ctk.CTkLabel(left_extra_frame, text="생산 수량(EA):", font=ctk.CTkFont(size=11, weight="bold"))
        self.quotation_count_lbl.grid(row=3, column=2, padx=(5, 4), pady=3, sticky="w")
        self.quotation_unit_count_entry = ctk.CTkEntry(left_extra_frame, width=90, height=26, justify="right", font=("", 11))
        self.quotation_unit_count_entry.insert(0, "1")
        self.quotation_unit_count_entry.grid(row=3, column=3, padx=(0, 10), pady=3, sticky="ew")
        self.quotation_unit_count_entry.bind("<KeyRelease>", self._on_unit_count_changed)

        # 4행: 산출 결과 (kg당 단가 및 개당 단가)
        self.quotation_result_subframe = ctk.CTkFrame(left_extra_frame, fg_color=("#EDF2F7", "#1E1F22"), border_width=1, border_color=("#E2E8F0", "#2D3035"), corner_radius=6)
        self.quotation_result_subframe.grid(row=4, column=0, columnspan=4, padx=8, pady=(6, 8), sticky="ew")
        self.quotation_result_subframe.grid_columnconfigure((1, 3), weight=1)

        self.quotation_cost_per_kg_title = ctk.CTkLabel(self.quotation_result_subframe, text="1kg당 총단가:", font=ctk.CTkFont(size=11, weight="bold"), text_color=("#0284C7", "#38BDF8"))
        self.quotation_cost_per_kg_title.grid(row=0, column=0, padx=(8, 4), pady=5, sticky="w")
        self.quotation_cost_per_kg_label = ctk.CTkLabel(self.quotation_result_subframe, text="0 원/kg", font=ctk.CTkFont(size=12, weight="bold"), text_color=("#0284C7", "#38BDF8"), anchor="e")
        self.quotation_cost_per_kg_label.grid(row=0, column=1, padx=(0, 10), pady=5, sticky="ew")

        self.quotation_cost_per_unit_title = ctk.CTkLabel(self.quotation_result_subframe, text="개당(EA) 총단가:", font=ctk.CTkFont(size=11, weight="bold"), text_color=("#16A34A", "#4ADE80"))
        self.quotation_cost_per_unit_title.grid(row=0, column=2, padx=(5, 4), pady=5, sticky="w")
        self.quotation_cost_per_unit_label = ctk.CTkLabel(self.quotation_result_subframe, text="0 원/개", font=ctk.CTkFont(size=12, weight="bold"), text_color=("#16A34A", "#4ADE80"), anchor="e")
        self.quotation_cost_per_unit_label.grid(row=0, column=3, padx=(0, 8), pady=5, sticky="ew")

        # ----------------------------------------------------
        # [우측 영역] 원료 원가 및 최종 견적 계산 프레임
        # ----------------------------------------------------
        calculation_frame = ctk.CTkFrame(bottom_summary_container, fg_color=("#F9FAFB", "#242526"), border_width=1, border_color=("#E5E7EB", "#333538"), corner_radius=8)
        calculation_frame.grid(row=0, column=1, padx=(10, 0), pady=0, sticky="nsew")
        calculation_frame.grid_columnconfigure(1, weight=1)

        # 이윤율 설정
        ctk.CTkLabel(calculation_frame, text="이윤율 (%)", font=ctk.CTkFont(size=12, weight="bold")).grid(row=0, column=0, padx=12, pady=(8, 2), sticky="w")
        self.quotation_profit_margin_entry = ctk.CTkEntry(calculation_frame, width=90, height=26, justify="right", font=("", 11))
        self.quotation_profit_margin_entry.insert(0, "15.0")
        self.quotation_profit_margin_entry.bind("<KeyRelease>", lambda e: self._on_profit_margin_changed())
        self.quotation_profit_margin_entry.grid(row=0, column=1, padx=12, pady=(8, 2), sticky="ew")

        # 총 함량
        ctk.CTkLabel(calculation_frame, text=self.texts['total_ratio'], font=ctk.CTkFont(size=12)).grid(row=1, column=0, padx=12, pady=2, sticky="w")
        self.quotation_total_ratio_label = ctk.CTkLabel(calculation_frame, text="0.0000 %", font=ctk.CTkFont(size=12), anchor="e")
        self.quotation_total_ratio_label.grid(row=1, column=1, padx=12, pady=2, sticky="ew")

        # 총 원료 원가
        ctk.CTkLabel(calculation_frame, text=self.texts['total_raw_cost'], font=ctk.CTkFont(size=12)).grid(row=2, column=0, padx=12, pady=2, sticky="w")
        self.total_raw_cost_label = ctk.CTkLabel(calculation_frame, text="0 원", font=ctk.CTkFont(size=12), anchor="e")
        self.total_raw_cost_label.grid(row=2, column=1, padx=12, pady=2, sticky="ew")

        # 총 제조원가 (원료원가 + 인력+제조+운송+용기)
        ctk.CTkLabel(calculation_frame, text="총 제조 원가", font=ctk.CTkFont(size=12, weight="bold")).grid(row=3, column=0, padx=12, pady=2, sticky="w")
        self.total_combined_cost_label = ctk.CTkLabel(calculation_frame, text="0 원", font=ctk.CTkFont(size=12, weight="bold"), anchor="e")
        self.total_combined_cost_label.grid(row=3, column=1, padx=12, pady=2, sticky="ew")

        # 이윤 포함가
        self.price_with_profit_text_label = ctk.CTkLabel(calculation_frame, text="이윤 (15%) 포함 공급가", font=ctk.CTkFont(size=12, weight="bold"), text_color=("#0284C7", "#38BDF8"))
        self.price_with_profit_text_label.grid(row=4, column=0, padx=12, pady=2, sticky="w")
        self.price_with_profit_label = ctk.CTkLabel(calculation_frame, text="0 원", font=ctk.CTkFont(size=13, weight="bold"), text_color=("#0284C7", "#38BDF8"), anchor="e")
        self.price_with_profit_label.grid(row=4, column=1, padx=12, pady=2, sticky="ew")

        # VAT 10% 포함 최종가
        ctk.CTkLabel(calculation_frame, text="최종가 (VAT 10% 포함)", font=ctk.CTkFont(size=13, weight="bold"), text_color=("#DC2626", "#F87171")).grid(row=5, column=0, padx=12, pady=(2, 8), sticky="w")
        self.price_with_vat_label = ctk.CTkLabel(calculation_frame, text="0 원", font=ctk.CTkFont(size=14, weight="bold"), text_color=("#DC2626", "#F87171"), anchor="e")
        self.price_with_vat_label.grid(row=5, column=1, padx=12, pady=(2, 8), sticky="ew")

        # 인라인 편집용 Entry 초기화
        self.quotation_edit_entry = None

        # [기본 모드: 반제품] UI 필드 초기 상태 즉시 반영 (용기비/수량 등 숨김 처리)
        self._on_quotation_type_changed()

    def load_formulation_for_quotation(self, silent: bool = False):
        """'처방 목록'에서 선택된 처방을 '견적' 탭의 Treeview로 불러옵니다."""
        if not self._selected_formulation_id:
            if not silent:
                messagebox.showwarning(self.texts['selection_error'], self.texts['select_formulation_first'], parent=self)
            return

        for item in self.quotation_tree.get_children():
            self.quotation_tree.delete(item)

        session = db_manager.get_session()
        try:
            formulation = session.query(Formulation).filter_by(id=self._selected_formulation_id).first()
            if not formulation: return

            # Load profit margin
            profit_margin = formulation.profit_margin if formulation.profit_margin is not None else 15.0
            self.quotation_profit_margin_entry.delete(0, "end")
            self.quotation_profit_margin_entry.insert(0, f"{profit_margin:.1f}")
            self.price_with_profit_text_label.configure(text=f"이윤 ({profit_margin:.0f}%) 포함가")

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

    def _on_quotation_type_changed(self, value=None):
        """반제품/완제품 모드 전환 시 UI 컨트롤들을 시각적으로 보이거나 숨깁니다."""
        mode_val = self.quotation_type_var.get() if hasattr(self, 'quotation_type_var') else "finished"
        is_semi = ("반제품" in mode_val or mode_val == "semi")

        if is_semi:
            # 반제품: 용기비, 개당 용량, 생산 수량, 개당 총단가 숨김
            if hasattr(self, 'quotation_container_lbl'):
                self.quotation_container_lbl.grid_remove()
                self.quotation_container_entry.grid_remove()
            if hasattr(self, 'quotation_capacity_lbl'):
                self.quotation_capacity_lbl.grid_remove()
                self.quotation_unit_capacity_entry.grid_remove()
            if hasattr(self, 'quotation_count_lbl'):
                self.quotation_count_lbl.grid_remove()
                self.quotation_unit_count_entry.grid_remove()
            if hasattr(self, 'quotation_cost_per_unit_title'):
                self.quotation_cost_per_unit_title.grid_remove()
                self.quotation_cost_per_unit_label.grid_remove()
            # 1kg당 총단가를 중앙 또는 전체 너비로 확장
            if hasattr(self, 'quotation_cost_per_kg_title'):
                self.quotation_cost_per_kg_title.grid(row=0, column=0, padx=(10, 4), pady=5, sticky="w")
                self.quotation_cost_per_kg_label.grid(row=0, column=1, columnspan=3, padx=(0, 10), pady=5, sticky="ew")
        else:
            # 완제품: 모든 항목 다시 표시
            if hasattr(self, 'quotation_container_lbl'):
                self.quotation_container_lbl.grid()
                self.quotation_container_entry.grid()
            if hasattr(self, 'quotation_capacity_lbl'):
                self.quotation_capacity_lbl.grid()
                self.quotation_unit_capacity_entry.grid()
            if hasattr(self, 'quotation_count_lbl'):
                self.quotation_count_lbl.grid()
                self.quotation_unit_count_entry.grid()
            if hasattr(self, 'quotation_cost_per_unit_title'):
                self.quotation_cost_per_unit_title.grid()
                self.quotation_cost_per_unit_label.grid()
            if hasattr(self, 'quotation_cost_per_kg_title'):
                self.quotation_cost_per_kg_title.grid(row=0, column=0, padx=(8, 4), pady=5, sticky="w")
                self.quotation_cost_per_kg_label.grid(row=0, column=1, columnspan=1, padx=(0, 10), pady=5, sticky="ew")

        self.recalculate_quotation()

    def recalculate_quotation(self):
        """현재 Treeview의 내용을 바탕으로 원가와 최종 가격을 다시 계산합니다. (반제품/완제품 모드 동적 반영)"""
        try:
            total_weight = float(self.quotation_weight_entry.get().strip())
        except (ValueError, TypeError):
            return

        # 기준 중량 표시 타이틀 갱신
        if total_weight >= 1000 and total_weight % 1000 == 0:
            weight_display_title = f"⚖️ {int(total_weight // 1000)}kg당 총단가:"
            weight_display_unit = f"원/{int(total_weight // 1000)}kg" if total_weight > 1000 else "원/kg"
        elif total_weight == 1000:
            weight_display_title = "⚖️ 1kg당 총단가:"
            weight_display_unit = "원/kg"
        else:
            weight_display_title = f"⚖️ {total_weight:,.0f}g당 총단가:"
            weight_display_unit = f"원/{total_weight:,.0f}g"

        if hasattr(self, 'quotation_cost_per_kg_title'):
            self.quotation_cost_per_kg_title.configure(text=weight_display_title)

        if not self.quotation_tree.get_children():
            self.quotation_total_ratio_label.configure(text="0.0000 %")
            self.total_raw_cost_label.configure(text="0 원")
            self.price_with_vat_label.configure(text="0 원")
            self.price_with_profit_label.configure(text="0 원")
            if hasattr(self, 'quotation_cost_per_kg_label'):
                self.quotation_cost_per_kg_label.configure(text=f"0 {weight_display_unit}")
            if hasattr(self, 'quotation_cost_per_unit_label'):
                self.quotation_cost_per_unit_label.configure(text="0 원/개")
            return

        # 모드 판별
        mode_val = self.quotation_type_var.get() if hasattr(self, 'quotation_type_var') else "finished"
        is_semi = ("반제품" in mode_val or mode_val == "semi")

        # 중복 원료 합산 로직
        material_groups = {}
        for item_id in self.quotation_tree.get_children():
            values = self.quotation_tree.item(item_id, "values")
            try:
                material_code = values[1].strip()
                material_name = values[2].strip()
                ratio = float(values[3])
                unit_price_str = str(values[4]).replace(",", "").strip()
                unit_price = float(unit_price_str) if unit_price_str else 0.0

                if not material_code or material_code == "---":
                    continue

                if material_code in material_groups:
                    material_groups[material_code]['ratio'] += ratio
                    material_groups[material_code]['duplicate_items'].append(item_id)
                else:
                    material_groups[material_code] = {
                        'phase': values[0],
                        'name': material_name,
                        'ratio': ratio,
                        'unit_price': unit_price,
                        'original_item_id': item_id,
                        'duplicate_items': []
                    }
            except (ValueError, TypeError, IndexError):
                continue

        total_raw_cost = 0.0
        total_ratio = 0.0

        for material_code, material_info in material_groups.items():
            ratio = material_info['ratio']
            unit_price = material_info['unit_price']
            total_ratio += ratio

            cost = (ratio / 100.0) * (total_weight / 1000.0) * unit_price
            total_raw_cost += cost

            original_item_id = material_info['original_item_id']
            if self.quotation_tree.exists(original_item_id):
                self.quotation_tree.item(original_item_id, values=(
                    material_info['phase'],
                    material_code,
                    material_info['name'],
                    f"{ratio:.4f}",
                    f"{unit_price:,.0f}",
                    f"{cost:,.2f}"
                ))

            for dup_item_id in material_info['duplicate_items']:
                if self.quotation_tree.exists(dup_item_id):
                    self.quotation_tree.delete(dup_item_id)

        # 부가 비용 계산
        try:
            labor_cost = float(self.quotation_labor_entry.get().strip() or 0)
        except Exception:
            labor_cost = 0.0

        try:
            mfg_cost = float(self.quotation_mfg_cost_entry.get().strip() or 0)
        except Exception:
            mfg_cost = 0.0

        try:
            shipping_cost = float(self.quotation_shipping_entry.get().strip() or 0)
        except Exception:
            shipping_cost = 0.0

        # 반제품이면 용기비는 0원 처리
        if is_semi:
            container_cost = 0.0
            produced_units = 1.0
        else:
            try:
                container_cost = float(self.quotation_container_entry.get().strip() or 0)
            except Exception:
                container_cost = 0.0

            try:
                produced_units = float(self.quotation_unit_count_entry.get().strip() or 1)
                if produced_units <= 0: produced_units = 1.0
            except Exception:
                produced_units = 1.0

        extra_expenses = labor_cost + mfg_cost + shipping_cost + container_cost
        total_combined_cost = total_raw_cost + extra_expenses

        # 기준 중량에 맞춘 단가 타이틀 및 텍스트 동적 표시
        weight_kg = (total_weight / 1000.0) if total_weight > 0 else 1.0
        cost_per_kg = (total_combined_cost / weight_kg) if weight_kg > 0 else 0.0
        cost_per_unit = (total_combined_cost / produced_units) if produced_units > 0 else 0.0

        # 기준 중량 표시 문자열 (예: 500g 또는 1kg)
        if total_weight >= 1000 and total_weight % 1000 == 0:
            weight_display_title = f"⚖️ {int(total_weight // 1000)}kg당 총단가:"
            weight_display_unit = f"원/{int(total_weight // 1000)}kg" if total_weight > 1000 else "원/kg"
            cost_for_base_weight = total_combined_cost
        elif total_weight == 1000:
            weight_display_title = "⚖️ 1kg당 총단가:"
            weight_display_unit = "원/kg"
            cost_for_base_weight = cost_per_kg
        else:
            weight_display_title = f"⚖️ {total_weight:,.0f}g당 총단가:"
            weight_display_unit = f"원/{total_weight:,.0f}g"
            cost_for_base_weight = total_combined_cost

        if hasattr(self, 'quotation_cost_per_kg_title'):
            self.quotation_cost_per_kg_title.configure(text=weight_display_title)
        if hasattr(self, 'quotation_cost_per_kg_label'):
            self.quotation_cost_per_kg_label.configure(text=f"{cost_for_base_weight:,.0f} {weight_display_unit} (1kg: {cost_per_kg:,.0f}원)")
        if hasattr(self, 'quotation_cost_per_unit_label'):
            self.quotation_cost_per_unit_label.configure(text=f"{cost_per_unit:,.0f} 원/개")

        try:
            profit_margin = float(self.quotation_profit_margin_entry.get().strip())
        except (ValueError, TypeError):
            profit_margin = 15.0

        profit_factor = 1.0 + (profit_margin / 100.0)
        price_with_profit = total_combined_cost * profit_factor
        final_price_with_vat = price_with_profit * 1.10

        self.quotation_total_ratio_label.configure(text=f"{total_ratio:.4f} %")
        self.total_raw_cost_label.configure(text=f"{total_raw_cost:,.0f} 원")
        if hasattr(self, 'total_combined_cost_label'):
            self.total_combined_cost_label.configure(text=f"{total_combined_cost:,.0f} 원")
        self.price_with_profit_label.configure(text=f"{price_with_profit:,.0f} 원")
        self.price_with_vat_label.configure(text=f"{final_price_with_vat:,.0f} 원")

    
    def _on_unit_capacity_changed(self, event=None):
        """개당 용량이 변경되면 총 중량 대비 생산 수량(EA)을 자동 계산합니다."""
        try:
            cap = float(self.quotation_unit_capacity_entry.get().strip() or 0)
            tot = float(self.quotation_weight_entry.get().strip() or 0)
            if cap > 0 and tot > 0:
                units = tot / cap
                self.quotation_unit_count_entry.delete(0, "end")
                self.quotation_unit_count_entry.insert(0, f"{units:.1f}" if units % 1 != 0 else f"{int(units)}")
        except Exception:
            pass
        self.recalculate_quotation()

    def _on_unit_count_changed(self, event=None):
        """생산 수량이 사용자에 의해 직접 1개, 10개 등으로 변경되면 총단가를 즉시 재계산합니다."""
        self.recalculate_quotation()

    def _on_profit_margin_changed(self):
        """When profit margin entry changes, save to Formulation and recalculate"""
        try:
            profit_margin = float(self.quotation_profit_margin_entry.get().strip())
        except (ValueError, TypeError):
            return
        
        # Update label text
        self.price_with_profit_text_label.configure(text=f"이윤 ({profit_margin:.0f}%) 포함가")
        
        # Save to Formulation if selected
        if self._selected_formulation_id:
            session = db_manager.get_session()
            try:
                formulation = session.query(Formulation).filter_by(id=self._selected_formulation_id).first()
                if formulation:
                    formulation.profit_margin = profit_margin
                    session.commit()
            except Exception as e:
                print(f"[Error] Saving profit margin: {e}")
            finally:
                session.close()
        
        # Recalculate
        self.recalculate_quotation()

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
                # 새 항목 추가
                new_item = self.quotation_tree.insert("", "end", values=(
                    "", material.code, material.name, "0.0000", f"{material.unit_price or 0:,.0f}", "0.00"
                ))
                self.recalculate_quotation()
                
                # 추가된 항목을 선택하고 자동으로 함량 편집 모드 열기
                self.quotation_tree.selection_set(new_item)
                self.quotation_tree.focus(new_item)
                self.quotation_tree.see(new_item)
                
                # 약간의 지연 후 편집 모드 시작 (UI 업데이트 대기)
                self.after(100, lambda: self.start_quotation_ratio_editing(new_item))
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
        safe_focus(self.quotation_edit_entry)

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
    
    def normalize_quotation_to_100(self):
        """선택된(포커스된) 원료에 (100 - 다른 원료들의 합계)를 자동 입력합니다."""
        # 현재 선택/포커스된 항목 확인
        focused_item = self.quotation_tree.focus()
        if not focused_item:
            messagebox.showwarning("선택 필요", "함량을 자동 입력할 원료를 선택해주세요.", parent=self)
            return
        
        # 선택된 항목이 유효한지 확인
        try:
            focused_values = self.quotation_tree.item(focused_item, "values")
            focused_code = focused_values[1].strip() if len(focused_values) > 1 else ""
            if not focused_code or focused_code == "---":
                messagebox.showwarning("선택 오류", "구분선이 아닌 원료를 선택해주세요.", parent=self)
                return
        except (IndexError, TypeError):
            messagebox.showwarning("선택 오류", "유효한 원료를 선택해주세요.", parent=self)
            return
        
        # 다른 원료들의 함량 합계 계산
        other_total = 0.0
        
        for item_id in self.quotation_tree.get_children():
            if item_id == focused_item:
                continue  # 선택된 항목은 제외
            
            try:
                values = self.quotation_tree.item(item_id, "values")
                material_code = values[1].strip() if len(values) > 1 else ""
                
                # 빈 코드나 구분선은 건너뛰기
                if not material_code or material_code == "---":
                    continue
                
                ratio = float(values[3]) if values[3] else 0.0
                other_total += ratio
            except (ValueError, TypeError, IndexError):
                continue
        
        # 선택된 원료에 입력할 함량 계산: 100 - 다른 원료들의 합계
        remaining_ratio = 100.0 - other_total
        
        if remaining_ratio < 0:
            messagebox.showwarning("함량 초과", 
                                 f"다른 원료들의 합계가 이미 {other_total:.4f}%입니다.\n"
                                 f"100%를 초과하여 자동 입력할 수 없습니다.", 
                                 parent=self)
            return
        
        # 선택된 원료의 함량 업데이트
        updated_values = list(focused_values)
        updated_values[3] = f"{remaining_ratio:.4f}"
        self.quotation_tree.item(focused_item, values=tuple(updated_values))
        
        # 재계산
        self.recalculate_quotation()
        
        # 결과 메시지
        material_name = focused_values[2] if len(focused_values) > 2 else "선택된 원료"
        messagebox.showinfo("자동 입력 완료", 
                          f"'{material_name}'의 함량이 자동 입력되었습니다.\n\n"
                          f"다른 원료 합계: {other_total:.4f}%\n"
                          f"자동 입력 함량: {remaining_ratio:.4f}%\n"
                          f"총 함량: 100.0000%", 
                          parent=self)

    def generate_quotation(self):
        """선택된 처방을 기반으로 견적을 생성합니다."""
        if not self._selected_formulation_id:
            messagebox.showwarning(self.texts['selection_error'], self.texts['select_formulation_first'], parent=self)
            return
        self.load_formulation_for_quotation()

    def export_quotation(self, lang="ko"):
        """현재 견적 내용을 엑셀 파일로 내보냅니다. (국문/영문 다국어 지원)"""
        if not self.quotation_tree.get_children():
            messagebox.showwarning(self.texts['export_error'], self.texts['no_quotation_to_export'], parent=self)
            return

        is_eng = (lang == "en")

        # 처방 정보는 선택된 ID를 기반으로 가져옴
        formulation_name = "Quotation" if is_eng else "가상 견적"
        lab_no = ""
        manager_name = self.current_user.username

        if self._selected_formulation_id:
            session = db_manager.get_session()
            try:
                formulation = session.query(Formulation).filter_by(id=self._selected_formulation_id).first()
                if formulation:
                    formulation_name = (formulation.experiment_name_en or formulation.experiment_name) if is_eng else formulation.experiment_name
                    lab_no = formulation.lab_no
                    manager_name = self.get_manager_display_name(formulation.manager_name or "", session)
            finally:
                session.close()

        # Get profit margin for summary label
        try:
            profit_margin = float(self.quotation_profit_margin_entry.get().strip())
        except (ValueError, TypeError):
            profit_margin = 15.0
        
        # 영문 모드 시 원료명을 영문(INCI)으로 변환
        items_data = []
        session = db_manager.get_session()
        try:
            for item in self.quotation_tree.get_children():
                vals = list(self.quotation_tree.item(item, "values"))
                if is_eng and len(vals) > 2 and vals[1]:
                    # 코드(vals[1])로 영문 원료명 조회
                    mat = session.query(Material).filter_by(code=vals[1]).first()
                    if mat and mat.name_en:
                        vals[2] = mat.name_en
                items_data.append(vals)
        finally:
            session.close()

        # 반제품 / 완제품 모드 확인
        mode_val = self.quotation_type_var.get() if hasattr(self, 'quotation_type_var') else "finished"
        is_semi = ("반제품" in mode_val or mode_val == "semi")

        # [v64] 엑셀 내보내기용 추가 부가비용 및 단위 단가 데이터 취합
        details_map = {
            "실험품명": formulation_name,
            "담당자": manager_name,
            "LAB NO.": lab_no,
            "기준 중량": self.quotation_weight_entry.get() + "g",
        }
        if not is_semi:
            details_map["개당 용량"] = (self.quotation_unit_capacity_entry.get() if hasattr(self, 'quotation_unit_capacity_entry') else "50") + "g"
            details_map["산출 수량"] = (self.quotation_unit_count_entry.get() + " EA") if hasattr(self, 'quotation_unit_count_entry') else "1 EA"

        extra_map = {
            "인력비": (self.quotation_labor_entry.get() if hasattr(self, 'quotation_labor_entry') else "0") + " 원",
            "제조비": (self.quotation_mfg_cost_entry.get() if hasattr(self, 'quotation_mfg_cost_entry') else "0") + " 원",
            "운송비": (self.quotation_shipping_entry.get() if hasattr(self, 'quotation_shipping_entry') else "0") + " 원",
        }
        if not is_semi:
            extra_map["용기"] = (self.quotation_container_entry.get() if hasattr(self, 'quotation_container_entry') else "0") + " 원"
        
        extra_map["1kg당 총단가"] = self.quotation_cost_per_kg_label.cget("text") if hasattr(self, 'quotation_cost_per_kg_label') else "-"
        if not is_semi:
            extra_map["개당(EA) 총단가"] = self.quotation_cost_per_unit_label.cget("text") if hasattr(self, 'quotation_cost_per_unit_label') else "-"

        quotation_data = {
            "is_semi": is_semi,
            "details": details_map,
            "extra_expenses": extra_map,
            "items": items_data,
            "summary": {
                "총 함량": self.quotation_total_ratio_label.cget("text"),
                "총 원료 원가": self.total_raw_cost_label.cget("text"),
                "총 제조 원가": self.total_combined_cost_label.cget("text") if hasattr(self, 'total_combined_cost_label') else self.total_raw_cost_label.cget("text"),
                f"이윤({profit_margin:.0f}%) 포함 공급가": self.price_with_profit_label.cget("text"),
                "최종가 (VAT 10% 포함)": self.price_with_vat_label.cget("text"),
            }
        }
        
        default_filename = f"{formulation_name}_Quotation_EN.xlsx" if is_eng else f"{formulation_name}_견적서.xlsx"
        excel_handler.export_quotation_to_excel(quotation_data, default_filename, lang=lang)

    def show_folder_view(self):
        """폴더 뷰를 표시하고 파일 뷰를 숨깁니다. (아이템 레벨로 돌아감)"""
        self.file_view.grid_forget()
        self.folder_view.grid(row=0, column=0, sticky="nsew")
        self.list_header_label.configure(text=self.texts['formulation_folders'])
        self.current_view = "folders"
        self.current_folder_name = None
        self._selected_formulation_id = None
        self.update_button_states()
        # 아이템 폴더 레벨로 돌아가기 (폴더 새로 로드하지 않음 - 이미 상태 유지됨)
        self.current_view_level = "item"
        self.load_folders(is_initial_load=False)

    # ------------------------------
    # 패키지 탭
    # ------------------------------
    def setup_package_tab(self, tab_frame):
        tab_frame.grid_columnconfigure(0, weight=1)
        tab_frame.grid_rowconfigure(1, weight=1)

        header = ctk.CTkFrame(tab_frame, fg_color="transparent")
        header.grid(row=0, column=0, sticky="ew", padx=10, pady=(10,5))

        create_btn = ctk.CTkButton(header, text="새 패키지 저장", width=90, command=self.create_document_package, font=("", 11))
        create_btn.pack(side="left")
        ctk.CTkButton(header, text="패키지 상세", width=80, command=self.open_selected_package_detail, font=("", 11)).pack(side="left", padx=(5,0))
        ctk.CTkButton(header, text="문서 링크 추가", width=95, command=self.add_package_link, font=("", 11)).pack(side="left", padx=(5,0))
        ctk.CTkButton(header, text="첨부 추가", width=75, command=self.add_package_attachment, font=("", 11)).pack(side="left", padx=(5,0))
        ctk.CTkButton(header, text="내보내기", width=75, command=self.export_selected_package, font=("", 11)).pack(side="left", padx=(5,0))
        ctk.CTkButton(header, text="패키지 삭제", width=80, command=self.delete_selected_package, 
                     fg_color="darkred", hover_color="red", font=("", 11)).pack(side="left", padx=(5,0))
        
        ctk.CTkLabel(header, text="선택된 처방의 통합 자료를 하나로 저장/관리합니다.", text_color="gray", font=("", 10)).pack(side="left", padx=(10,0))

        if self.mode == "package_only":
            self.create_package_redirect_button = create_btn
            create_btn.configure(command=self._redirect_to_document_for_package)

        list_frame = ctk.CTkFrame(tab_frame, fg_color="transparent")
        list_frame.grid(row=1, column=0, sticky="nsew", padx=10, pady=(0,10))
        list_frame.grid_columnconfigure(0, weight=1)
        list_frame.grid_rowconfigure(0, weight=1)

        self.package_tree = ttk.Treeview(list_frame, columns=("name","created","creator","revision"), show="headings", selectmode="browse")
        self.package_tree.heading("name", text="패키지명"); self.package_tree.column("name", width=260, stretch=True)
        self.package_tree.heading("created", text="생성일"); self.package_tree.column("created", width=160)
        self.package_tree.heading("creator", text="작성자"); self.package_tree.column("creator", width=140)
        self.package_tree.heading("revision", text="차수"); self.package_tree.column("revision", width=80, anchor="center")
        self.package_tree.grid(row=0, column=0, sticky="nsew")
        pkg_v_scroll = ttk.Scrollbar(list_frame, orient="vertical", command=self.package_tree.yview)
        pkg_v_scroll.grid(row=0, column=1, sticky="ns")
        self.package_tree.configure(yscrollcommand=pkg_v_scroll.set)
        # 패키지 선택 핸들러
        self.package_tree.bind("<<TreeviewSelect>>", self.on_package_tree_select)

    def _redirect_to_document_for_package(self):
        """패키지 생성 기능을 연구소 문서 화면으로 안내합니다."""
        try:
            messagebox.showinfo("안내", "패키지 생성을 위해 연구소 > 문서 화면에서 처방을 선택한 뒤 '패키지 저장' 버튼을 사용하세요.", parent=self)
        except Exception:
            pass
        try:
            if hasattr(self.app, 'navigate_and_record'):
                self.app.navigate_and_record("document")
        except Exception:
            pass

    # ------------------------------
    # 생산 처방 탭
    # ------------------------------
    def setup_production_tab(self, tab_frame):
        tab_frame.grid_columnconfigure(0, weight=1)
        # [수정] row 2 weight 제거 (runs_frame 이동으로 인해 불필요)
        tab_frame.grid_rowconfigure(1, weight=1)
        tab_frame.grid_rowconfigure(2, weight=0)

        header = ctk.CTkFrame(tab_frame, fg_color="transparent")
        header.grid(row=0, column=0, sticky="ew", padx=10, pady=(0, 5))

        # 생성은 RD+만 노출
        try:
            if self._role_level() >= 1:
                ctk.CTkButton(header, text="생산처방 생성", width=90, command=self.create_production_formulation, font=("", 11)).pack(side="left")
        except Exception:
            # 문제 시 기본 노출 (이후 내부에서 한 번 더 권한 체크)
            ctk.CTkButton(header, text="생산처방 생성", width=90, command=self.create_production_formulation, font=("", 11)).pack(side="left")
        ctk.CTkButton(header, text="공정(제법) 편집", width=100, command=self.edit_production_process, font=("", 11)).pack(side="left", padx=(5,0))

        # 관리자 이상만 보이는 삭제 버튼 (버튼 군과 같이 좌측에 배치)
        try:
            if hasattr(self.current_user, 'can_delete') and self.current_user.can_delete():
                ctk.CTkButton(header, text="삭제", width=60, fg_color="#D32F2F", hover_color="#B71C1C", command=self.delete_selected_production, font=("", 11)).pack(side="left", padx=(5,0))
        except Exception:
            if getattr(self.current_user, 'is_admin', False):
                ctk.CTkButton(header, text="삭제", width=60, fg_color="#D32F2F", hover_color="#B71C1C", command=self.delete_selected_production, font=("", 11)).pack(side="left", padx=(5,0))

        # 검색 영역 (단일 검색창: 업체/생산코드/제품명 통합)
        search_frame = ctk.CTkFrame(header, fg_color="transparent")
        search_frame.pack(side="right")
        self.prod_search_entry = ctk.CTkEntry(search_frame, width=300, placeholder_text="검색 (업체/생산코드/제품명)", font=("", 11))
        self.prod_search_entry.pack(side="left", padx=(0,5))
        self.prod_search_entry.bind("<Return>", lambda e: self.search_production_list())
        ctk.CTkButton(search_frame, text="검색", width=55, command=self.search_production_list, font=("", 11)).pack(side="left", padx=(5,0))
        ctk.CTkButton(search_frame, text="초기화", width=55, fg_color="gray", command=self.clear_production_search, font=("", 11)).pack(side="left", padx=(5,0))

        # 메인 컨텐츠 영역 (폴더 뷰 / 리스트 뷰 교체)
        content_frame = ctk.CTkFrame(tab_frame, fg_color="transparent")
        content_frame.grid(row=1, column=0, sticky="nsew", padx=10, pady=(0,6))
        content_frame.grid_columnconfigure(0, weight=1)
        content_frame.grid_rowconfigure(0, weight=0) # [수정] 헤더는 고정 높이
        content_frame.grid_rowconfigure(1, weight=1) # [수정] 폴더 뷰가 확장됨

        # 1. 폴더 뷰 (Scrollable Frame)
        # [NEW] 폴더 네비게이션 헤더 (업체로 돌아가기 등)
        self.folder_nav_frame = ctk.CTkFrame(content_frame, fg_color="transparent", height=40)
        self.folder_nav_frame.grid(row=0, column=0, sticky="ew", padx=10, pady=(5,0))
        self.folder_nav_frame.grid_remove() # 초기에는 숨김 (업체 레벨)
        
        self.btn_back_to_clients = ctk.CTkButton(
            self.folder_nav_frame, 
            text="🔙 업체 목록으로", 
            width=120, 
            fg_color="transparent", 
            border_width=1, 
            text_color=("gray10", "gray90"),
            command=lambda: self.show_production_folder_view(go_back=True),
            font=("", 11)
        )
        self.btn_back_to_clients.pack(side="left")
        
        self.prod_folder_view = ctk.CTkScrollableFrame(content_frame, label_text="업체별 보기")
        self.prod_folder_view.grid(row=1, column=0, sticky="nsew")
        self.prod_folder_view.grid_columnconfigure((0, 1, 2, 3, 4), weight=1)

        # 2. 파일 목록 뷰 (Frame + Treeview)
        self.prod_file_view = ctk.CTkFrame(content_frame, fg_color="transparent")
        self.prod_file_view.grid_columnconfigure(0, weight=1)
        # [수정] row 1(Treeview)와 row 2(History)에 가중치 분배
        self.prod_file_view.grid_rowconfigure(1, weight=3)
        self.prod_file_view.grid_rowconfigure(2, weight=2)

        # 파일 뷰 헤더 (뒤로가기 버튼 등)
        file_view_header = ctk.CTkFrame(self.prod_file_view, fg_color="transparent")
        file_view_header.grid(row=0, column=0, sticky="ew", pady=(0, 5))
        ctk.CTkButton(file_view_header, text="🔙 뒤로가기", width=120, command=lambda: self.show_production_folder_view(go_back=False), font=("", 11)).pack(side="left")
        self.prod_current_folder_label = ctk.CTkLabel(file_view_header, text="", font=ctk.CTkFont(weight="bold"))
        self.prod_current_folder_label.pack(side="left", padx=10)

        self.production_tree = ttk.Treeview(self.prod_file_view, columns=("name","pcode","client","eff","status","approver","base","created"), show="headings", selectmode="browse")
        self.production_tree.heading("name", text="제품명/차수"); self.production_tree.column("name", width=260, stretch=True)
        self.production_tree.heading("pcode", text="생산코드"); self.production_tree.column("pcode", width=120)
        self.production_tree.heading("client", text="업체"); self.production_tree.column("client", width=160, stretch=True)
        self.production_tree.heading("eff", text="제조일"); self.production_tree.column("eff", width=120)
        self.production_tree.heading("status", text="상태"); self.production_tree.column("status", width=80)
        self.production_tree.heading("approver", text="승인자"); self.production_tree.column("approver", width=120)
        self.production_tree.heading("base", text="생산량(kg)"); self.production_tree.column("base", width=120, anchor="e")
        self.production_tree.heading("created", text="생성일"); self.production_tree.column("created", width=140)
        self.production_tree.grid(row=1, column=0, sticky="nsew")
        prod_v_scroll = ttk.Scrollbar(self.prod_file_view, orient="vertical", command=self.production_tree.yview)
        prod_v_scroll.grid(row=1, column=1, sticky="ns")
        self.production_tree.configure(yscrollcommand=prod_v_scroll.set)
        self.production_tree.bind("<<TreeviewSelect>>", self.on_production_tree_select)
        self.production_tree.bind("<Double-1>", self.on_production_tree_double_click)

        # 초기 상태 변수
        self.prod_view_level = "client" # client -> product -> list
        self.current_prod_client_id = None
        self.current_prod_client_name = ""
        self.current_prod_product_name = ""

        # 초기 상태: 폴더 뷰 표시
        self.show_production_folder_view()

        # --- 생산 이력(런) 리스트 ---
        # [수정] 부모를 tab_frame -> self.prod_file_view로 변경하고 위치 조정
        runs_frame = ctk.CTkFrame(self.prod_file_view, fg_color="transparent")
        runs_frame.grid(row=2, column=0, sticky="nsew", padx=0, pady=(10,0)) # padding 조정
        runs_frame.grid_columnconfigure(0, weight=1)
        runs_frame.grid_rowconfigure(1, weight=1)
        ctk.CTkLabel(runs_frame, text="생산 이력", font=ctk.CTkFont(weight="bold", size=11)).grid(row=0, column=0, sticky="w")
        runs_toolbar = ctk.CTkFrame(runs_frame, fg_color="transparent")
        runs_toolbar.grid(row=0, column=0, sticky="e")

        ctk.CTkButton(runs_toolbar, text="추가", width=55, command=self.add_production_run, font=("", 11)).pack(side="left", padx=(0,5))
        ctk.CTkButton(runs_toolbar, text="삭제", width=55, command=self.delete_selected_production_run, font=("", 11)).pack(side="left", padx=(0,5))
        ctk.CTkButton(runs_toolbar, text="엑셀 내보내기", width=85, command=self.export_selected_run_to_excel, font=("", 11), fg_color="#27ae60", hover_color="#219150").pack(side="left", padx=(0,5))
        ctk.CTkButton(runs_toolbar, text="인쇄", width=55, command=self.print_selected_run, font=("", 11), fg_color="#2980b9", hover_color="#2471a3").pack(side="left")

        self.runs_tree = ttk.Treeview(runs_frame, columns=("date","lot","qty","sg","visc_init","visc_next","ph_init","ph_next","notes","created"), show="headings", selectmode="browse")
        self.runs_tree.heading("date", text="생산일자"); self.runs_tree.column("date", width=100)
        self.runs_tree.heading("lot", text="제조번호"); self.runs_tree.column("lot", width=120)
        self.runs_tree.heading("qty", text="생산량(kg)"); self.runs_tree.column("qty", width=90, anchor="e")
        self.runs_tree.heading("sg", text="비중"); self.runs_tree.column("sg", width=70, anchor="center")
        self.runs_tree.heading("visc_init", text="점도(당일)"); self.runs_tree.column("visc_init", width=90, anchor="center")
        self.runs_tree.heading("visc_next", text="점도(익일)"); self.runs_tree.column("visc_next", width=90, anchor="center")
        self.runs_tree.heading("ph_init", text="pH(당일)"); self.runs_tree.column("ph_init", width=80, anchor="center")
        self.runs_tree.heading("ph_next", text="pH(익일)"); self.runs_tree.column("ph_next", width=80, anchor="center")
        self.runs_tree.heading("notes", text="비고"); self.runs_tree.column("notes", width=200, stretch=True)
        self.runs_tree.heading("created", text="기록일"); self.runs_tree.column("created", width=120)
        self.runs_tree.grid(row=1, column=0, sticky="nsew")
        runs_scroll = ttk.Scrollbar(runs_frame, orient="vertical", command=self.runs_tree.yview)
        runs_scroll.grid(row=1, column=1, sticky="ns")
        self.runs_tree.configure(yscrollcommand=runs_scroll.set)
        self.runs_tree.bind("<Double-1>", lambda e: self.edit_production_run())
        # 초기 목록 로드: 선택된 실험처방이 없으면 전역 목록 표시
        try:
            self.refresh_production_list()
        except Exception:
            pass

    def show_production_folder_view(self, go_back=False):
        """생산처방 폴더 뷰를 표시합니다."""
        if not hasattr(self, 'prod_folder_view'): return
        
        self.prod_file_view.grid_forget()
        
        # 폴더 뷰 보이기 (헤더는 아래에서 제어)
        self.prod_folder_view.grid(row=1, column=0, sticky="nsew")
        
        if go_back:
            # 명시적으로 상위 레벨로 이동 요청 시 (제품 폴더 ->업체 폴더)
            if self.prod_view_level == "product":
                self.prod_view_level = "client"
                self.current_prod_client_id = None
                self.current_prod_client_name = ""
                self.prod_current_folder_label.configure(text="")
        
        # 헤더 제어
        if self.prod_view_level == "product":
            self.folder_nav_frame.grid(row=0, column=0, sticky="ew", padx=10, pady=(5,0))
            self.prod_folder_view.configure(label_text=f"{self.current_prod_client_name} > 제품별 보기")
        else:
            self.folder_nav_frame.grid_remove()
            self.prod_folder_view.configure(label_text="업체별 보기")

        self.load_production_folders()

    def show_production_products_view(self, client_id, client_name):
        """업체 선택 -> 제품명 폴더 보기"""
        self.prod_view_level = "product"
        self.current_prod_client_id = client_id
        self.current_prod_client_name = client_name
        self.prod_current_folder_label.configure(text=f"> {client_name}")
        
        self.prod_file_view.grid_forget()
        self.folder_nav_frame.grid(row=0, column=0, sticky="ew", padx=10, pady=(5,0))
        self.prod_folder_view.grid(row=1, column=0, sticky="nsew")
        
        self.prod_folder_view.configure(label_text=f"{client_name} > 제품별 보기")
        
        self.load_production_folders()

    def show_production_file_view(self, product_name=None):
        """생산처방 목록(버전들) 뷰를 표시합니다."""
        if not hasattr(self, 'prod_file_view'): return

        self.prod_folder_view.grid_forget()
        self.folder_nav_frame.grid_forget() # 헤더도 숨김
        
        self.prod_file_view.grid(row=0, column=0, rowspan=2, sticky="nsew") # rowspan=2로 전체 덮음
        
        self.current_prod_product_name = product_name
        
        # 헤더 텍스트: 업체명 > 제품명
        header_text = f"> {self.current_prod_client_name}"
        if product_name:
            header_text += f" > {product_name}"
        self.prod_current_folder_label.configure(text=header_text)
        
        self.refresh_production_list()

    def load_production_folders(self):
        """레벨에 따라 생산처방 폴더(업체 or 제품)를 로드합니다."""
        for widget in self.prod_folder_view.winfo_children():
            widget.destroy()
            
        if self.prod_view_level == "client":
            self._load_prod_client_folders()
        elif self.prod_view_level == "product":
            self._load_prod_product_folders()

    def _load_prod_client_folders(self):
        """업체별 폴더 표시"""
        session = db_manager.get_session()
        try:
            pfs = session.query(ProductionFormulation).options(
                joinedload(ProductionFormulation.source_formulation).joinedload(Formulation.oem_odm_client)
            ).all()
            
            client_groups = {}
            for pf in pfs:
                if not self.can_view_production(pf): continue
                
                sf = pf.source_formulation
                c_name = "미지정"
                c_id = "UNKNOWN"
                
                if sf:
                    if sf.target_client_id and sf.target_client_id.strip():
                        c_name = sf.target_client_id.strip()
                        c_id = f"TARGET:{c_name}"
                    elif sf.oem_odm_client:
                        c_name = sf.oem_odm_client.name
                        c_id = f"OEM:{sf.oem_odm_client.id}"
                
                if c_name not in client_groups:
                    client_groups[c_name] = {'count': 0, 'id_key': c_id}
                client_groups[c_name]['count'] += 1
                
            sorted_clients = sorted(client_groups.keys())
            self._render_prod_folders(client_groups, sorted_clients, is_client_level=True)
            
        finally:
            session.close()

    def _load_prod_product_folders(self):
        """선택된 업체 내 제품별 폴더 표시"""
        session = db_manager.get_session()
        try:
            pfs = session.query(ProductionFormulation).options(
                joinedload(ProductionFormulation.source_formulation).joinedload(Formulation.oem_odm_client)
            ).all() # 최적화 여지 있음
            
            product_groups = {}
            filter_cid = self.current_prod_client_id
            
            for pf in pfs:
                if not self.can_view_production(pf): continue
                
                # 먼저 업체 필터링
                sf = pf.source_formulation
                c_id = "UNKNOWN"
                if sf:
                    if sf.target_client_id and sf.target_client_id.strip():
                        c_id = f"TARGET:{sf.target_client_id.strip()}"
                    elif sf.oem_odm_client:
                        c_id = f"OEM:{sf.oem_odm_client.id}"
                
                if c_id != filter_cid: continue
                
                # 제품명으로 그룹화 (ProductionFormulation.product_name)
                p_name = pf.product_name or "(이름 없음)"
                if p_name not in product_groups:
                    product_groups[p_name] = {'count': 0, 'id_key': p_name}
                product_groups[p_name]['count'] += 1
                
            sorted_products = sorted(product_groups.keys())
            self._render_prod_folders(product_groups, sorted_products, is_client_level=False)
            
        finally:
            session.close()

    def _render_prod_folders(self, groups, sorted_keys, is_client_level):
        """폴더 렌더링 공통 로직"""
        icon_size = 40
        if hasattr(self, 'icon_size_slider'):
            try: icon_size = int(self.icon_size_slider.get())
            except: pass
            
        card_width = int(icon_size * 4) + 20
        self.prod_folder_view.update_idletasks()
        container_width = self.prod_folder_view.winfo_width()
        if container_width < 100: container_width = 800
        max_cols = max(1, container_width // card_width)
        
        row = 0
        col = 0
        
        row = 0
        col = 0
        
        # [삭제됨] 그리드 내 버튼은 제거됨 (상단 헤더로 이동)
        
        for key in sorted_keys:
            info = groups[key]
            count = info['count']
            id_key = info['id_key'] # client info or product name
            
            card = self._create_production_folder_card(
                self.prod_folder_view, id_key, key, count, icon_size, is_client_level
            )
            card.grid(row=row, column=col, padx=10, pady=10, sticky="nsew")
            
            col += 1
            if col >= max_cols:
                col = 0
                row += 1

    def _create_production_folder_card(self, parent, id_key, display_name, item_count, icon_size, is_client_level):
        """생산처방용 폴더 카드 위젯을 생성합니다."""
        card_width = int(icon_size * 4)
        card_height = int(icon_size * 3)
        title_size = max(11, int(icon_size / 3))
        count_size = max(9, int(icon_size / 4))
        wraplength = int(icon_size * 3)
        
        card = ctk.CTkFrame(parent, corner_radius=10, fg_color=("gray95", "gray20"),
                           border_width=1, border_color=("gray80", "gray40"),
                           width=card_width, height=card_height)
        card.pack_propagate(False)
        
        # 클릭 이벤트 핸들러
        def on_click(e):
            if is_client_level:
                self.show_production_products_view(client_id=id_key, client_name=display_name)
            else:
                self.show_production_file_view(product_name=id_key)
            
        card.bind("<Button-1>", on_click)
        card.bind("<Enter>", lambda e: card.configure(fg_color=("gray85", "gray30")))
        card.bind("<Leave>", lambda e: card.configure(fg_color=("gray95", "gray20")))
        
        # 아이콘
        if is_client_level:
            icon_text = "🏭" # 공장 (Production Client)
        else:
            icon_text = "📦" # 패키지/제품 (Product)
            
        icon_label = ctk.CTkLabel(card, text=icon_text, font=ctk.CTkFont(size=icon_size))
        icon_label.pack(pady=(max(5, int(icon_size/8)), 3))
        icon_label.bind("<Button-1>", on_click)
        
        # 이름
        name_label = ctk.CTkLabel(card, text=display_name, font=ctk.CTkFont(size=title_size, weight="bold"),
                                 wraplength=wraplength, text_color=("black", "white"))
        name_label.pack()
        name_label.bind("<Button-1>", on_click)
        
        # 건수
        count_label = ctk.CTkLabel(card, text=f"{item_count} items", font=ctk.CTkFont(size=count_size),
                                  text_color="gray")
        count_label.pack(side="bottom", pady=(0, 5))
        count_label.bind("<Button-1>", on_click)
        
        return card

    def refresh_production_list(self):
        if not hasattr(self, 'production_tree'):
            return
        for item in self.production_tree.get_children():
            self.production_tree.delete(item)
            
        # 1. 일반 필터 (폴더 구조)
        filter_cid = getattr(self, 'current_prod_client_id', None)
        filter_pname = getattr(self, 'current_prod_product_name', None)
        
        # 2. 검색 필터 (전역 검색 시에만 설정됨)
        # search_production_list가 호출되면 show_production_file_view가 param 없이 호출되어 
        # filter_cid, filter_pname이 초기화됨. 그러나 검색어가 유지되어야 함.
        # 하지만 현재 구조상 검색 시에는 current_prod_... 변수들이 None이 됨.
        # 검색은 search_production_list에서 직접 쿼리 후 채우므로, 여기서는 무시해도 되지만
        # search_production_list가 refresh_production_list를 부르지 않도록 주의.
        # -> search_production_list는 독자적으로 insert함.
        # -> 즉 이 함수는 "폴더 탐색" 모드일 때만 데이터 채움.
        
        session = db_manager.get_session()
        try:
            q = session.query(ProductionFormulation).options(
                joinedload(ProductionFormulation.source_formulation).joinedload(Formulation.oem_odm_client)
            )
            
            all_rows = q.order_by(ProductionFormulation.created_at.desc()).all()
            
            for r in all_rows:
                # 1. 권한 체크
                try:
                    if not self.can_view_production(r): continue
                except: pass
                
                sf = r.source_formulation
                c_id = "UNKNOWN"
                c_name = "미지정"
                if sf:
                    if sf.target_client_id and sf.target_client_id.strip():
                        c_id = f"TARGET:{sf.target_client_id.strip()}"
                    elif sf.oem_odm_client:
                        c_id = f"OEM:{sf.oem_odm_client.id}"
                
                # 폴더 필터링
                if filter_cid:
                    if c_id != filter_cid: continue
                    
                if filter_pname:
                    # 제품명 필터 (정확히 일치 or 포함? 폴더명은 정확히 일치로 생성했음)
                    if (r.product_name or "") != filter_pname: continue

                # 표시 데이터 구성
                approver = ""
                try:
                    approver = (r.approved_by.real_name or r.approved_by.username) if r.approved_by else ""
                except: pass
                
                name_field = f"{r.product_name or ''} ({r.revision or ''})".strip()
                eff = r.effective_date.strftime("%Y-%m-%d") if r.effective_date else ""
                created = r.created_at.strftime("%Y-%m-%d %H:%M") if r.created_at else ""
                
                client_name = ""
                try:
                    sf = r.source_formulation
                    if sf:
                        client_name = (sf.target_client_id or "").strip() or ((sf.oem_odm_client.name or "") if sf.oem_odm_client else "")
                except: pass
                
                self.production_tree.insert("", "end", iid=r.id, values=(
                    name_field,
                    r.production_code or '',
                    client_name,
                    eff,
                    r.status or '',
                    approver,
                    f"{((r.base_weight_g or 0)/1000):,.1f}",
                    created
                ))
        finally:
            session.close()
        
        # 첫 번째 항목 선택 및 생산 이력 로드
        children = self.production_tree.get_children()
        if children:
            first_item = children[0]
            self.production_tree.selection_set(first_item)
            self.production_tree.see(first_item)
            # on_production_tree_select를 호출하거나 직접 refresh
            sel = self.production_tree.selection()
            if sel:
                try:
                    self._selected_production_id = int(sel[0])
                except Exception:
                    self._selected_production_id = None
                self.refresh_production_runs()

    def search_production_list(self):
        """단일 검색창(업체/생산코드/제품명)으로 전역 검색합니다."""
        if not hasattr(self, 'production_tree'):
            return
        # 입력값 수집 (단일 검색어)
        term = (self.prod_search_entry.get().strip() if hasattr(self, 'prod_search_entry') else '')
        
        # 검색 시에는 파일 뷰로 강제 전환 (검색 결과 표시)
        if hasattr(self, 'prod_file_view') and not self.prod_file_view.winfo_ismapped():
             self.show_production_file_view(client_id=None, client_name="") # 전체 검색 모드로 진입

        # 목록 초기화
        for item in self.production_tree.get_children():
            self.production_tree.delete(item)

        session = db_manager.get_session()
        try:
            q = (
                session.query(ProductionFormulation)
                .outerjoin(Formulation, ProductionFormulation.source_formulation_id == Formulation.id)
                .outerjoin(Client, Formulation.oem_odm_client_id == Client.id)
            )
            if term:
                pat = f"%{term}%"
                q = q.filter(or_(
                    ProductionFormulation.product_name.like(pat),
                    ProductionFormulation.production_code.like(pat),
                    Formulation.target_client_id.like(pat),
                    Client.name.like(pat)
                ))
            rows = q.order_by(ProductionFormulation.created_at.desc()).all()

            for r in rows:
                # 상태/권한 정책
                try:
                    if not self.can_view_production(r): continue
                except: pass
                
                approver = ""
                try:
                    approver = (r.approved_by.real_name or r.approved_by.username) if r.approved_by else ""
                except: pass
                
                name_field = f"{r.product_name or ''} ({r.revision or ''})".strip()
                eff = r.effective_date.strftime("%Y-%m-%d") if r.effective_date else ""
                created = r.created_at.strftime("%Y-%m-%d %H:%M") if r.created_at else ""
                
                client_name = ""
                try:
                    sf = r.source_formulation
                    if sf:
                        client_name = (sf.target_client_id or "").strip() or ((sf.oem_odm_client.name or "") if sf.oem_odm_client else "")
                except: pass
                
                self.production_tree.insert("", "end", iid=r.id, values=(
                    name_field,
                    r.production_code or '',
                    client_name,
                    eff,
                    r.status or '',
                    approver,
                    f"{((r.base_weight_g or 0)/1000):,.1f}",
                    created
                ))
        finally:
            session.close()
        
        # 첫 번째 항목 선택 및 생산 이력 로드
        children = self.production_tree.get_children()
        if children:
            first_item = children[0]
            self.production_tree.selection_set(first_item)
            self.production_tree.see(first_item)
            # on_production_tree_select를 호출하거나 직접 refresh
            sel = self.production_tree.selection()
            if sel:
                try:
                    self._selected_production_id = int(sel[0])
                except Exception:
                    self._selected_production_id = None
                self.refresh_production_runs()

    def clear_production_search(self):
        """검색 입력을 초기화하고 폴더 뷰로 복귀"""
        try:
            if hasattr(self, 'prod_search_entry'):
                self.prod_search_entry.delete(0, 'end')
        except: pass
        
        self.show_production_folder_view()


    

    def delete_selected_production(self):
        """관리자 이상: 선택된 생산처방 삭제 (연결 패키지의 참조는 해제)."""
        prod_id = getattr(self, '_selected_production_id', None)
        if not prod_id:
            messagebox.showwarning('선택 필요', '삭제할 생산처방을 선택하세요.', parent=self)
            return
        # 권한 확인
        try:
            if hasattr(self.current_user, 'can_delete'):
                allowed = self.current_user.can_delete()
            else:
                allowed = bool(getattr(self.current_user, 'is_admin', False))
        except Exception:
            allowed = bool(getattr(self.current_user, 'is_admin', False))
        if not allowed:
            messagebox.showwarning('권한 없음', '삭제 권한이 없습니다.', parent=self)
            return
        if not messagebox.askyesno('삭제 확인', '선택한 생산처방을 삭제할까요?\n연결된 생산 이력/공정은 함께 삭제되며, 패키지의 참조는 해제됩니다.', parent=self):
            return
        session = db_manager.get_session()
        try:
            from database.models import ProductionFormulation, DocumentPackage
            prod = session.query(ProductionFormulation).filter_by(id=prod_id).first()
            if not prod:
                messagebox.showerror('오류', '생산처방을 찾을 수 없습니다.', parent=self)
                return
            # 패키지 참조 해제
            pkgs = session.query(DocumentPackage).filter_by(production_formulation_id=prod_id).all()
            for p in pkgs:
                p.production_formulation_id = None
            # 삭제
            session.delete(prod)
            session.commit()
            messagebox.showinfo('완료', '생산처방이 삭제되었습니다.', parent=self)
            # 목록/선택 갱신
            self._selected_production_id = None
            self.refresh_production_list()
            if hasattr(self, 'runs_tree'):
                for i in self.runs_tree.get_children():
                    self.runs_tree.delete(i)
        except Exception as ex:
            session.rollback()
            messagebox.showerror('오류', f'삭제 실패: {ex}', parent=self)
        finally:
            session.close()

    def on_production_tree_select(self, event):
        sel = self.production_tree.selection()
        if not sel:
            self._selected_production_id = None
            # 선택 해제 시 생산 이력 리스트 비우기
            if hasattr(self, 'runs_tree'):
                for i in self.runs_tree.get_children():
                    self.runs_tree.delete(i)
            return
        try:
            self._selected_production_id = int(sel[0])
        except Exception:
            self._selected_production_id = None
        # 선택된 생산처방의 생산 이력 로드
        self.refresh_production_runs()

    def on_production_tree_double_click(self, event):
        """생산처방 목록 더블클릭 시 공정 편집 창 열기"""
        if not hasattr(self, 'production_tree'):
            return
        sel = self.production_tree.selection()
        if not sel:
            return
        try:
            prod_id = int(sel[0])
            self.edit_production_process(prod_id)
        except Exception as e:
            print(f"생산처방 편집 오류: {e}")
            messagebox.showerror("오류", f"생산처방 편집 중 오류가 발생했습니다:\n{e}", parent=self)

    def refresh_production_runs(self):
        if not hasattr(self, 'runs_tree'):
            return
        for i in self.runs_tree.get_children():
            self.runs_tree.delete(i)
        prod_id = getattr(self, '_selected_production_id', None)
        if not prod_id:
            return
        session = db_manager.get_session()
        try:
            from database.models import ProductionRun
            runs = (
                session.query(ProductionRun)
                .filter_by(production_formulation_id=prod_id)
                .order_by(ProductionRun.run_date.desc().nullslast(), ProductionRun.id.desc())
                .all()
            )
            for r in runs:
                date_str = r.run_date.strftime('%Y-%m-%d') if r.run_date else ''
                created_str = r.created_at.strftime('%Y-%m-%d %H:%M') if r.created_at else ''
                qty_kg = ((r.quantity_g or 0) / 1000.0) if r.quantity_g is not None else None
                qty = f"{qty_kg:,.1f}" if qty_kg is not None else ''
                self.runs_tree.insert('', 'end', iid=r.id, values=(
                    date_str, 
                    r.lot_no or '', 
                    qty, 
                    r.specific_gravity or '', 
                    r.viscosity_initial or '', 
                    r.viscosity_next_day or '', 
                    r.ph_initial or '', 
                    r.ph_next_day or '', 
                    r.notes or '', 
                    created_str
                ))
        finally:
            session.close()
    def add_production_run(self):
        prod_id = getattr(self, '_selected_production_id', None)
        if not prod_id:
            messagebox.showwarning('선택 필요', '생산 이력을 추가할 생산처방을 선택하세요.', parent=self)
            return
        dlg = ctk.CTkToplevel(self)
        dlg.title('생산 이력 추가')
        dlg.transient(self); dlg.grab_set()

        frm = ctk.CTkFrame(dlg)
        frm.pack(padx=20, pady=20, fill='both', expand=True)
        frm.grid_columnconfigure(1, weight=1)

        ctk.CTkLabel(frm, text='생산일자').grid(row=0, column=0, sticky='w', pady=4)
        date_e = ctk.CTkEntry(frm, width=140)
        date_e.grid(row=0, column=1, sticky='w', pady=4)
        date_e.insert(0, datetime.now().strftime('%Y-%m-%d'))

        ctk.CTkLabel(frm, text='제조번호').grid(row=1, column=0, sticky='w', pady=4)
        lot_e = ctk.CTkEntry(frm)
        lot_e.grid(row=1, column=1, sticky='ew', pady=4)

        ctk.CTkLabel(frm, text='생산량(kg)').grid(row=2, column=0, sticky='w', pady=4)
        qty_e = ctk.CTkEntry(frm)
        qty_e.grid(row=2, column=1, sticky='ew', pady=4)

        # 물성치 섹션
        ctk.CTkLabel(frm, text='', font=ctk.CTkFont(size=11, weight='bold')).grid(row=3, column=0, columnspan=2, sticky='w', pady=(8,4))
        
        # 비중 (클릭 시 계산 기능)
        ctk.CTkLabel(frm, text='비중').grid(row=4, column=0, sticky='w', pady=4)
        sg_frame = ctk.CTkFrame(frm, fg_color='transparent')
        sg_frame.grid(row=4, column=1, sticky='ew', pady=4)
        sg_e = ctk.CTkEntry(sg_frame)
        sg_e.pack(side='left', fill='x', expand=True)
        
        def calc_specific_gravity():
            calc_win = ctk.CTkToplevel(dlg)
            calc_win.title('비중 계산')
            calc_win.geometry('350x250')
            calc_win.transient(dlg)
            calc_win.grab_set()
            
            calc_frm = ctk.CTkFrame(calc_win)
            calc_frm.pack(padx=20, pady=20, fill='both', expand=True)
            calc_frm.grid_columnconfigure(1, weight=1)
            
            ctk.CTkLabel(calc_frm, text='총무게 (g)').grid(row=0, column=0, sticky='w', pady=4)
            total_e = ctk.CTkEntry(calc_frm)
            total_e.grid(row=0, column=1, sticky='ew', pady=4)
            
            ctk.CTkLabel(calc_frm, text='빈비중컵 무게 (g)').grid(row=1, column=0, sticky='w', pady=4)
            empty_e = ctk.CTkEntry(calc_frm)
            empty_e.grid(row=1, column=1, sticky='ew', pady=4)
            
            ctk.CTkLabel(calc_frm, text='비중컵 용량 (mL)').grid(row=2, column=0, sticky='w', pady=4)
            volume_e = ctk.CTkEntry(calc_frm)
            volume_e.grid(row=2, column=1, sticky='ew', pady=4)
            
            result_label = ctk.CTkLabel(calc_frm, text='', font=ctk.CTkFont(weight='bold'))
            result_label.grid(row=3, column=0, columnspan=2, pady=(10,0))
            
            def calculate():
                try:
                    total_weight = float(total_e.get().replace(',',''))
                    empty_cup = float(empty_e.get().replace(',',''))
                    cup_volume = float(volume_e.get().replace(',',''))
                    sg = (total_weight - empty_cup) / cup_volume
                    sg_e.delete(0, 'end')
                    sg_e.insert(0, f'{sg:.4f}')
                    result_label.configure(text=f'비중: {sg:.4f}', text_color='green')
                except Exception as ex:
                    result_label.configure(text=f'오류: {ex}', text_color='red')
            
            calc_btn_frm = ctk.CTkFrame(calc_frm, fg_color='transparent')
            calc_btn_frm.grid(row=4, column=0, columnspan=2, pady=(10,0))
            ctk.CTkButton(calc_btn_frm, text='계산', command=calculate).pack(side='left', padx=5)
            ctk.CTkButton(calc_btn_frm, text='닫기', fg_color='gray', command=calc_win.destroy).pack(side='left', padx=5)
        
        ctk.CTkButton(sg_frame, text='계산', width=60, command=calc_specific_gravity).pack(side='left', padx=(5,0))
        
        # 점도 (당일/익일)
        ctk.CTkLabel(frm, text='점도(당일)').grid(row=5, column=0, sticky='w', pady=4)
        visc_init_e = ctk.CTkEntry(frm)
        visc_init_e.grid(row=5, column=1, sticky='ew', pady=4)
        
        # pH (당일/익일)
        ctk.CTkLabel(frm, text='pH(당일)').grid(row=6, column=0, sticky='w', pady=4)
        ph_init_e = ctk.CTkEntry(frm)
        ph_init_e.grid(row=6, column=1, sticky='ew', pady=4)
        
        ctk.CTkLabel(frm, text='점도(익일)').grid(row=7, column=0, sticky='w', pady=4)
        visc_next_e = ctk.CTkEntry(frm)
        visc_next_e.grid(row=7, column=1, sticky='ew', pady=4)
        
        ctk.CTkLabel(frm, text='pH(익일)').grid(row=8, column=0, sticky='w', pady=4)
        ph_next_e = ctk.CTkEntry(frm)
        ph_next_e.grid(row=8, column=1, sticky='ew', pady=4)

        ctk.CTkLabel(frm, text='결제방').grid(row=9, column=0, sticky='w', pady=4)
        payment_room_e = ctk.CTkEntry(frm)
        payment_room_e.grid(row=9, column=1, sticky='ew', pady=4)

        ctk.CTkLabel(frm, text='비고').grid(row=10, column=0, sticky='nw', pady=4)
        notes_t = ctk.CTkTextbox(frm, height=80)
        notes_t.grid(row=10, column=1, sticky='nsew', pady=4)

        btns = ctk.CTkFrame(frm, fg_color='transparent')
        btns.grid(row=11, column=0, columnspan=2, sticky='e', pady=(10,0))

        def save_run():
            session = db_manager.get_session()
            try:
                from database.models import ProductionRun
                try:
                    run_date = datetime.strptime(date_e.get().strip(), '%Y-%m-%d').date() if date_e.get().strip() else None
                except Exception:
                    run_date = None
                try:
                    qty_kg_val = float(qty_e.get().replace(',','')) if qty_e.get() else None
                except Exception:
                    qty_kg_val = None
                r = ProductionRun(
                    production_formulation_id=prod_id,
                    run_date=run_date,
                    lot_no=lot_e.get().strip() or None,
                    quantity_g=(qty_kg_val * 1000.0 if qty_kg_val is not None else None),
                    specific_gravity=sg_e.get().strip() or None,
                    viscosity_initial=visc_init_e.get().strip() or None,
                    viscosity_next_day=visc_next_e.get().strip() or None,
                    ph_initial=ph_init_e.get().strip() or None,
                    ph_next_day=ph_next_e.get().strip() or None,
                    payment_room=payment_room_e.get().strip() or None,
                    notes=notes_t.get('1.0','end').strip() or None,
                )
                session.add(r)
                session.commit()
                dlg.destroy()
                self.refresh_production_runs()
            except Exception as ex:
                session.rollback()
                messagebox.showerror('오류', f'저장 실패: {ex}', parent=dlg)
            finally:
                session.close()

        ctk.CTkButton(btns, text='저장', command=save_run).pack(side='right')
        ctk.CTkButton(btns, text='취소', fg_color='gray', command=dlg.destroy).pack(side='right', padx=(0,6))

        try:
            center_window_on_mouse_display(dlg)
        except Exception:
            pass

        self.wait_window(dlg)

    def edit_production_run(self):
        """선택된 생산 이력을 편집합니다."""
        if not hasattr(self, 'runs_tree'):
            return
        sel = self.runs_tree.selection()
        if not sel:
            messagebox.showwarning('선택 필요', '편집할 생산 이력을 선택하세요.', parent=self)
            return
        
        run_id = int(sel[0])
        session = db_manager.get_session()
        try:
            from database.models import ProductionRun
            run = session.query(ProductionRun).filter_by(id=run_id).first()
            if not run:
                messagebox.showerror('오류', '생산 이력을 찾을 수 없습니다.', parent=self)
                return
            
            dlg = ctk.CTkToplevel(self)
            dlg.title('생산 이력 편집')
            dlg.transient(self)
            dlg.grab_set()

            frm = ctk.CTkFrame(dlg)
            frm.pack(padx=20, pady=20, fill='both', expand=True)
            frm.grid_columnconfigure(1, weight=1)

            ctk.CTkLabel(frm, text='생산일자').grid(row=0, column=0, sticky='w', pady=4)
            date_e = ctk.CTkEntry(frm, width=140)
            date_e.grid(row=0, column=1, sticky='w', pady=4)
            date_e.insert(0, run.run_date.strftime('%Y-%m-%d') if run.run_date else '')

            ctk.CTkLabel(frm, text='제조번호').grid(row=1, column=0, sticky='w', pady=4)
            lot_e = ctk.CTkEntry(frm)
            lot_e.grid(row=1, column=1, sticky='ew', pady=4)
            lot_e.insert(0, run.lot_no or '')

            ctk.CTkLabel(frm, text='생산량(kg)').grid(row=2, column=0, sticky='w', pady=4)
            qty_e = ctk.CTkEntry(frm)
            qty_e.grid(row=2, column=1, sticky='ew', pady=4)
            if run.quantity_g:
                qty_e.insert(0, f"{run.quantity_g/1000:.1f}")

            # 물성치 섹션
            ctk.CTkLabel(frm, text='', font=ctk.CTkFont(size=11, weight='bold')).grid(row=3, column=0, columnspan=2, sticky='w', pady=(8,4))
            
            # 비중 (클릭 시 계산 기능)
            ctk.CTkLabel(frm, text='비중').grid(row=4, column=0, sticky='w', pady=4)
            sg_frame = ctk.CTkFrame(frm, fg_color='transparent')
            sg_frame.grid(row=4, column=1, sticky='ew', pady=4)
            sg_e = ctk.CTkEntry(sg_frame)
            sg_e.pack(side='left', fill='x', expand=True)
            sg_e.insert(0, run.specific_gravity or '')
            
            def calc_specific_gravity():
                calc_win = ctk.CTkToplevel(dlg)
                calc_win.title('비중 계산')
                calc_win.geometry('350x250')
                calc_win.transient(dlg)
                calc_win.grab_set()
                
                calc_frm = ctk.CTkFrame(calc_win)
                calc_frm.pack(padx=20, pady=20, fill='both', expand=True)
                calc_frm.grid_columnconfigure(1, weight=1)
                
                ctk.CTkLabel(calc_frm, text='총무게 (g)').grid(row=0, column=0, sticky='w', pady=4)
                total_e = ctk.CTkEntry(calc_frm)
                total_e.grid(row=0, column=1, sticky='ew', pady=4)
                
                ctk.CTkLabel(calc_frm, text='빈비중컵 무게 (g)').grid(row=1, column=0, sticky='w', pady=4)
                empty_e = ctk.CTkEntry(calc_frm)
                empty_e.grid(row=1, column=1, sticky='ew', pady=4)
                
                ctk.CTkLabel(calc_frm, text='비중컵 용량 (mL)').grid(row=2, column=0, sticky='w', pady=4)
                volume_e = ctk.CTkEntry(calc_frm)
                volume_e.grid(row=2, column=1, sticky='ew', pady=4)
                
                result_label = ctk.CTkLabel(calc_frm, text='', font=ctk.CTkFont(weight='bold'))
                result_label.grid(row=3, column=0, columnspan=2, pady=(10,0))
                
                def calculate():
                    try:
                        total_weight = float(total_e.get().replace(',',''))
                        empty_cup = float(empty_e.get().replace(',',''))
                        cup_volume = float(volume_e.get().replace(',',''))
                        sg = (total_weight - empty_cup) / cup_volume
                        sg_e.delete(0, 'end')
                        sg_e.insert(0, f'{sg:.4f}')
                        result_label.configure(text=f'비중: {sg:.4f}', text_color='green')
                    except Exception as ex:
                        result_label.configure(text=f'오류: {ex}', text_color='red')
                
                calc_btn_frm = ctk.CTkFrame(calc_frm, fg_color='transparent')
                calc_btn_frm.grid(row=4, column=0, columnspan=2, pady=(10,0))
                ctk.CTkButton(calc_btn_frm, text='계산', command=calculate).pack(side='left', padx=5)
                ctk.CTkButton(calc_btn_frm, text='닫기', fg_color='gray', command=calc_win.destroy).pack(side='left', padx=5)
            
            ctk.CTkButton(sg_frame, text='계산', width=60, command=calc_specific_gravity).pack(side='left', padx=(5,0))
            
            # 점도 (당일/익일)
            ctk.CTkLabel(frm, text='점도(당일)').grid(row=5, column=0, sticky='w', pady=4)
            visc_init_e = ctk.CTkEntry(frm)
            visc_init_e.grid(row=5, column=1, sticky='ew', pady=4)
            visc_init_e.insert(0, run.viscosity_initial or '')
            
            # pH (당일/익일)
            ctk.CTkLabel(frm, text='pH(당일)').grid(row=6, column=0, sticky='w', pady=4)
            ph_init_e = ctk.CTkEntry(frm)
            ph_init_e.grid(row=6, column=1, sticky='ew', pady=4)
            ph_init_e.insert(0, run.ph_initial or '')
            
            ctk.CTkLabel(frm, text='점도(익일)').grid(row=7, column=0, sticky='w', pady=4)
            visc_next_e = ctk.CTkEntry(frm)
            visc_next_e.grid(row=7, column=1, sticky='ew', pady=4)
            visc_next_e.insert(0, run.viscosity_next_day or '')
            
            ctk.CTkLabel(frm, text='pH(익일)').grid(row=8, column=0, sticky='w', pady=4)
            ph_next_e = ctk.CTkEntry(frm)
            ph_next_e.grid(row=8, column=1, sticky='ew', pady=4)
            ph_next_e.insert(0, run.ph_next_day or '')

            ctk.CTkLabel(frm, text='결제방').grid(row=9, column=0, sticky='w', pady=4)
            payment_room_e = ctk.CTkEntry(frm)
            payment_room_e.grid(row=9, column=1, sticky='ew', pady=4)
            payment_room_e.insert(0, run.payment_room or '')

            ctk.CTkLabel(frm, text='비고').grid(row=10, column=0, sticky='nw', pady=4)
            notes_t = ctk.CTkTextbox(frm, height=80)
            notes_t.grid(row=10, column=1, sticky='nsew', pady=4)
            notes_t.insert('1.0', run.notes or '')

            btns = ctk.CTkFrame(frm, fg_color='transparent')
            btns.grid(row=11, column=0, columnspan=2, sticky='e', pady=(10,0))

            def save_edit():
                try:
                    try:
                        run_date = datetime.strptime(date_e.get().strip(), '%Y-%m-%d').date() if date_e.get().strip() else None
                    except Exception:
                        run_date = None
                    try:
                        qty_kg_val = float(qty_e.get().replace(',','')) if qty_e.get() else None
                    except Exception:
                        qty_kg_val = None
                    
                    run.run_date = run_date
                    run.lot_no = lot_e.get().strip() or None
                    run.quantity_g = (qty_kg_val * 1000.0 if qty_kg_val is not None else None)
                    run.specific_gravity = sg_e.get().strip() or None
                    run.viscosity_initial = visc_init_e.get().strip() or None
                    run.viscosity_next_day = visc_next_e.get().strip() or None
                    run.ph_initial = ph_init_e.get().strip() or None
                    run.ph_next_day = ph_next_e.get().strip() or None
                    run.payment_room = payment_room_e.get().strip() or None
                    run.notes = notes_t.get('1.0','end').strip() or None
                    
                    session.commit()
                    dlg.destroy()
                    self.refresh_production_runs()
                except Exception as ex:
                    session.rollback()
                    messagebox.showerror('오류', f'저장 실패: {ex}', parent=dlg)

            ctk.CTkButton(btns, text='저장', command=save_edit).pack(side='right')
            ctk.CTkButton(btns, text='취소', fg_color='gray', command=dlg.destroy).pack(side='right', padx=(0,6))

            try:
                center_window_on_mouse_display(dlg)
            except Exception:
                pass

            self.wait_window(dlg)
        finally:
            session.close()

    def export_selected_run_to_excel(self):
        """선택된 생산 이력을 엑셀로 내보냅니다."""
        self._generate_run_report(mode="excel")

    def print_selected_run(self):
        """선택된 생산 이력을 인쇄(미리보기)합니다."""
        self._generate_run_report(mode="print")

    def _generate_run_report(self, mode="excel"):
        """공통 리포트 생성 로직 (엑셀/인쇄)"""
        sel = self.runs_tree.selection()
        if not sel:
            messagebox.showwarning("선택 필요", "내보낼 생산 이력을 선택하세요.", parent=self)
            return

        run_id = sel[0]
        session = db_manager.get_session()
        try:
            from database.models import ProductionRun, ProductionFormulation, ProductionStep, User, Client
            run = session.query(ProductionRun).get(run_id)
            if not run: return
            
            prod = run.production
            if not prod: return

            # 기본 정보 수집
            client_name = ""
            if prod.source_formulation and prod.source_formulation.oem_odm_client:
                client_name = prod.source_formulation.oem_odm_client.name
            
            approver_name = ""
            if prod.approved_by:
                approver_name = prod.approved_by.real_name or prod.approved_by.username

            # 레시피 데이터 (스냅샷 기반)
            items_snapshot = []
            if prod.items_snapshot:
                try:
                    items_snapshot = json.loads(prod.items_snapshot)
                except Exception:
                    pass

            # 공정/검사 데이터
            steps = session.query(ProductionStep).filter_by(production_formulation_id=prod.id).order_by(ProductionStep.step_no).all()
            
            # Phase별 공정/검사 매핑 (기존 로직 준용)
            phase_map = {}
            prefixes = ("시간", "온도", "HE/M", "H/M", "P/M", "HE/M:", "H/M:", "P/M:")
            for st in steps:
                ph = (st.phase or "").strip()
                if not ph: continue
                if ph not in phase_map: phase_map[ph] = {"proc": [], "insp": []}
                
                instr = (st.instruction or "").strip()
                for line in instr.splitlines():
                    lt = line.strip()
                    if not lt: continue
                    if lt.startswith(prefixes):
                        phase_map[ph]["insp"].append(lt)
                    else:
                        phase_map[ph]["proc"].append(lt)

            def _norm_phase(v):
                s = str(v).strip() if v is not None else ''
                return s.replace('Ph.', '').replace('PH', '').strip() if s else ''

            # 본문 행 생성 (선택된 Run의 생산량 기준 계산)
            run_qty_kg = (run.quantity_g / 1000.0) if run.quantity_g else 0
            rows = []
            current_phase = None
            phase_order_counter = 0
            
            for it in sorted(items_snapshot, key=lambda x: (x.get('order') or 0)):
                # ratio는 Decimal일 수 있으므로 안전하게 변환
                ratio_val = it.get('ratio')
                try:
                    ratio = float(ratio_val) if ratio_val is not None else 0.0
                except (ValueError, TypeError):
                    ratio = 0.0
                
                # Run 생산량 기준 계량량 계산 (kg)
                calc_kg = (run_qty_kg * ratio / 100.0) if run_qty_kg else 0.0

                phase_val = it.get('phase') or ""
                ph_key = _norm_phase(phase_val)
                pm = phase_map.get(ph_key) or {"proc": [], "insp": []}

                if phase_val != current_phase:
                    current_phase = phase_val
                    phase_order_counter = 1
                    phase_display = phase_val
                    process_text = "\n".join(pm.get('proc') or []).replace('"', '').replace("'", '')
                    inspection_text = "\n".join(pm.get('insp') or []).replace('"', '').replace("'", '')
                else:
                    phase_order_counter += 1
                    phase_display = ""
                    process_text = ""
                    inspection_text = ""

                rows.append({
                    "Ph.": phase_display,
                    "구분": str(phase_order_counter) if current_phase else "",
                    "코드": it.get('material_code') or "",
                    "원료명": it.get('material_name') or "",
                    "함량(%)": ratio,
                    "생산량(kg)": calc_kg,
                    "계량량(kg)": calc_kg,
                    "제조공정": process_text,
                    "공정검사": inspection_text,
                })

            # 단계/공정 행 (기존 로직 준용)
            step_rows = []
            for st in steps:
                proc_lines, insp_lines = [], []
                instr = (st.instruction or '').strip()
                for ln in instr.splitlines():
                    lt = ln.strip()
                    if not lt: continue
                    if lt.startswith(prefixes):
                        insp_lines.append(lt)
                    else:
                        proc_lines.append(lt)
                step_rows.append({
                    "단계": st.step_no,
                    "구분": (st.phase or '').strip(),
                    "제조공정": "\n".join(proc_lines),
                    "공정검사": "\n".join(insp_lines),
                    "온도": st.temperature or "",
                    "시간(분)": st.time_min if st.time_min is not None else "",
                    "RPM": st.rpm or "",
                    "장비": st.equipment or "",
                    "비고": st.notes or "",
                })

            # 상세 정보 (Run 정보 위주로 구성)
            details = {
                "제품명": prod.product_name or "",
                "생산코드": run.lot_no or prod.production_code or "", # Run의 Lot No 우선
                "LAB NO.": prod.lab_no or "",
                "차수": prod.revision or "",
                "거래처": client_name or "",
                "결제방": run.payment_room or prod.payment_room or "",
                "생산량(kg)": f"{run_qty_kg:,.1f} kg",
                "제조일": run.run_date.strftime('%Y-%m-%d') if run.run_date else "",
                "상태": prod.status or "",
                "승인자": approver_name or "",
                "비고": (run.notes or "").strip() or (prod.notes or "").strip(),
                "출력일시": datetime.now().strftime('%Y-%m-%d %H:%M'),
                "제조자": approver_name # 제조자 정보가 명시적으로 없으므로 승인자나 담당자 활용 가능
            }

            production_data = {"details": details, "items": rows, "steps": step_rows}
            
            if mode == "excel":
                excel_handler.export_production_formulation_revised_to_excel(
                    production_data, 
                    default_filename=f"생지_{prod.product_name}_{run.lot_no}.xlsx"
                )
            else:
                show_production_print_preview(production_data, parent=self)

        except Exception as e:
            messagebox.showerror("오류", f"데이터 생성 중 오류가 발생했습니다:\n{e}", parent=self)
        finally:
            session.close()

    def delete_selected_production_run(self):
        if not hasattr(self, 'runs_tree'):
            return
        sel = self.runs_tree.selection()
        if not sel:
            messagebox.showwarning('선택 필요', '삭제할 생산 이력을 선택하세요.', parent=self)
            return
        if not messagebox.askyesno('삭제 확인', '선택한 생산 이력을 삭제할까요?', parent=self):
            return
        run_id = int(sel[0])
        session = db_manager.get_session()
        try:
            from database.models import ProductionRun
            r = session.query(ProductionRun).filter_by(id=run_id).first()
            if r:
                session.delete(r)
                session.commit()
            self.refresh_production_runs()
        except Exception as ex:
            session.rollback()
            messagebox.showerror('오류', f'삭제 실패: {ex}', parent=self)
        finally:
            session.close()

    def edit_production_process(self, prod_id=None):
        """선택된 생산처방의 공정(제법) 단계를 편집하는 창을 엽니다."""
        # prod_id가 전달되지 않으면 현재 선택된 것을 사용
        if prod_id is None:
            prod_id = getattr(self, '_selected_production_id', None)
        
        if not prod_id:
            messagebox.showwarning("선택 필요", "공정을 편집할 생산처방을 선택하세요.", parent=self)
            return

        session = db_manager.get_session()
        try:
            prod = session.query(ProductionFormulation).filter_by(id=prod_id).first()
            if not prod:
                messagebox.showerror("오류", "생산처방을 찾을 수 없습니다.", parent=self)
                return
            # 사용 권한 확인 (상태 기반)
            try:
                if not self.can_use_production(prod):
                    messagebox.showwarning("권한 없음", f"현재 계정으로는 상태 '{prod.status or ''}' 문서를 사용할 수 없습니다.", parent=self)
                    return
            except Exception:
                pass

            win = ctk.CTkToplevel(self)
            win.title(f"생산처방 편집 - {prod.product_name or ''} ({prod.revision or ''})")
            win.geometry("1100x650")  # 창 크기를 키워서 모든 요소가 보이게 함
            win.resizable(True, True)
            win.minsize(950, 550)  # 최소 크기 키우기
            win.grab_set()

            # 상단 정보 + 버튼 (편집 가능)
            top = ctk.CTkFrame(win, fg_color="transparent")
            top.pack(fill="x", padx=15, pady=(12,8))
            
            # 왼쪽: 제품 정보 (편집 가능)
            info_left = ctk.CTkFrame(top, fg_color="transparent")
            info_left.pack(side="left", fill="x", expand=True)
            
            # 행 1: 제품명, 차수, 생산코드, 업체명
            row1 = ctk.CTkFrame(info_left, fg_color="transparent")
            row1.pack(anchor="w", fill="x", pady=2)
            
            ctk.CTkLabel(row1, text="제품명: ", font=ctk.CTkFont(size=11)).pack(side="left")
            product_name_entry = ctk.CTkEntry(row1, width=200)
            product_name_entry.insert(0, prod.product_name or "")
            product_name_entry.pack(side="left", padx=2)
            
            ctk.CTkLabel(row1, text=" 차수: ", font=ctk.CTkFont(size=11)).pack(side="left")
            revision_entry = ctk.CTkEntry(row1, width=80)
            revision_entry.insert(0, prod.revision or "")
            revision_entry.pack(side="left", padx=2)
            
            ctk.CTkLabel(row1, text=" 생산코드: ", font=ctk.CTkFont(size=11)).pack(side="left")
            production_code_entry = ctk.CTkEntry(row1, width=120)
            production_code_entry.insert(0, prod.production_code or "")
            production_code_entry.pack(side="left", padx=2)
            
            ctk.CTkLabel(row1, text=" 업체명: ", font=ctk.CTkFont(size=11)).pack(side="left")
            client_name_entry = ctk.CTkEntry(row1, width=150)
            client_name_entry.insert(0, prod.client_name or "")
            client_name_entry.pack(side="left", padx=2)
            
            # 행 2: 생산량, 제조일, 상태
            row2 = ctk.CTkFrame(info_left, fg_color="transparent")
            row2.pack(anchor="w", fill="x", pady=2)
            
            ctk.CTkLabel(row2, text="생산량(kg): ", font=ctk.CTkFont(size=11)).pack(side="left")
            base_weight_entry = ctk.CTkEntry(row2, width=80)
            base_weight_kg = ((prod.base_weight_g or 0)/1000)
            base_weight_entry.insert(0, f"{base_weight_kg:.1f}")
            base_weight_entry.pack(side="left", padx=2)
            
            ctk.CTkLabel(row2, text=" 제조일: ", font=ctk.CTkFont(size=11)).pack(side="left")
            effective_date_entry = DateEntry(row2, date_pattern='yyyy-mm-dd', state='normal', width=100)
            if prod.effective_date:
                effective_date_entry.set_date(prod.effective_date)
            effective_date_entry.pack(side="left", padx=2)

            # 행 3: 결제방 + 버튼들
            row3 = ctk.CTkFrame(info_left, fg_color="transparent")
            row3.pack(anchor="w", fill="x", pady=2)
            
            ctk.CTkLabel(row3, text="결제방: ", font=ctk.CTkFont(size=11)).pack(side="left")
            payment_room_entry = ctk.CTkEntry(row3, width=200)
            payment_room_entry.insert(0, prod.payment_room or "")
            payment_room_entry.pack(side="left", padx=2)
            
            # 버튼들
            def save_edits():
                session_save = db_manager.get_session()
                try:
                    p_update = session_save.query(ProductionFormulation).filter_by(id=prod.id).first()
                    if p_update:
                        p_update.product_name = product_name_entry.get().strip() or p_update.product_name
                        p_update.revision = revision_entry.get().strip() or p_update.revision
                        p_update.production_code = production_code_entry.get().strip() or p_update.production_code
                        p_update.client_name = client_name_entry.get().strip() or p_update.client_name
                        p_update.payment_room = payment_room_entry.get().strip() or p_update.payment_room
                        try:
                            new_kg = float(base_weight_entry.get().strip())
                            p_update.base_weight_g = new_kg * 1000.0
                        except Exception:
                            pass
                        try:
                            new_date = effective_date_entry.get_date()
                            p_update.effective_date = new_date
                        except Exception:
                            pass
                        session_save.commit()
                        prod.product_name = p_update.product_name
                        prod.revision = p_update.revision
                        prod.production_code = p_update.production_code
                        prod.client_name = p_update.client_name
                        prod.payment_room = p_update.payment_room
                        prod.base_weight_g = p_update.base_weight_g
                        prod.effective_date = p_update.effective_date
                        messagebox.showinfo("성공", "생산처방 정보가 저장되었습니다.", parent=win)
                        self.refresh_production_list()
                        populate_recipe_items()
                    else:
                        messagebox.showerror("오류", "데이터를 찾을 수 없습니다.", parent=win)
                except Exception as e:
                    session_save.rollback()
                    messagebox.showerror("오류", f"저장 실패: {e}", parent=win)
                finally:
                    session_save.close()
            
            ctk.CTkButton(row3, text="💾 저장", width=100, fg_color="blue",
                         command=save_edits).pack(side="left", padx=(15, 3))
            ctk.CTkButton(row3, text="🖨 인쇄 미리보기", width=120,
                         command=self.print_preview_selected_production).pack(side="left", padx=3)
            ctk.CTkButton(row3, text="닫기", width=80, fg_color="gray",
                         command=win.destroy).pack(side="left", padx=3)

            # Status ComboBox Logic
            try:
                # 1. Determine allowed status options based on role
                # Default flow: 초안 -> 검토중 -> 확정
                # RD (Level 1): Can set '초안'
                # RQ (Level 2): Can set '검토중' (if current is '초안' or '검토중')
                # RQD/Admin (Level 3): Can set '확정' (if current is '검토중' or '확정')
                
                current_lvl = self._role_level()
                current_status = prod.status or '초안'
                
                allowed_next = []
                # 현재 상태를 항상 포함 (변경 취소 등을 위해)
                allowed_next.append(current_status)
                
                if current_lvl >= 1: # RD+
                    if '초안' not in allowed_next: allowed_next.append('초안')
                
                if current_lvl >= 2: # RQ+
                    if '검토중' not in allowed_next: allowed_next.append('검토중')
                    
                if current_lvl >= 3: # RQD+
                    if '확정' not in allowed_next: allowed_next.append('확정')

                # Filter valid transitions (Optional strict workflow: Draft -> Under Review -> Approved)
                # For now, allow role-based selection as requested.
                
                # Deduplicate and Sort?
                # Keeping simple list: ['초안', '검토중', '확정'] filtered by level
                full_order = ['초안', '검토중', '확정']
                final_options = [s for s in full_order if s in allowed_next]
                
                if not final_options:
                    final_options = [current_status]

                ctk.CTkLabel(row2, text=" | 상태: ", font=ctk.CTkFont(size=11), text_color="gray").pack(side="left")
                
                def on_status_change(choice):
                    if choice == current_status:
                        return
                        
                    if not messagebox.askyesno("상태 변경", f"상태를 '{current_status}'에서 '{choice}'(으)로 변경하시겠습니까?\n변경 즉시 저장됩니다.", parent=win):
                        status_combo.set(current_status)
                        return
                    
                    session_update = db_manager.get_session()
                    try:
                        p_update = session_update.query(ProductionFormulation).filter_by(id=prod.id).first()
                        if p_update:
                            p_update.status = choice
                            # 승인자 처리: 확정 시 현재 사용자
                            if choice == '확정':
                                p_update.approved_by_id = self.current_user.id
                                p_update.approved_at = datetime.now()
                            elif choice == '초안':
                                # 상태가 내려가면 승인정보 초기화? 정책에 따라 다름. 일단 유지.
                                pass
                                
                            session_update.commit()
                            messagebox.showinfo("성공", f"상태가 '{choice}'(으)로 변경되었습니다.", parent=win)
                            # Update local object for display
                            prod.status = choice 
                            # Refresh list in main window
                            self.refresh_production_list()
                        else:
                            messagebox.showerror("오류", "데이터를 찾을 수 없습니다.", parent=win)
                    except Exception as e:
                        session_update.rollback()
                        messagebox.showerror("오류", f"상태 변경 실패: {e}", parent=win)
                        status_combo.set(current_status)
                    finally:
                        session_update.close()

                status_combo = ctk.CTkComboBox(row2, values=final_options, width=100, height=22, font=("", 11), command=on_status_change)
                status_combo.set(current_status)
                status_combo.pack(side="left", padx=(5,0))
                
            except Exception as e:
                print(f"Status Combo Error: {e}")
                ctk.CTkLabel(row2, text=f" | 상태: {prod.status or ''}", font=ctk.CTkFont(size=11), text_color="gray").pack(side="left")
            


            # 메인 컨테이너: 레시피만 표시 (통합 뷰)
            main_container = ctk.CTkFrame(win)
            main_container.pack(fill="both", expand=True, padx=15, pady=(0,12))
            main_container.grid_columnconfigure(0, weight=1)
            main_container.grid_rowconfigure(0, weight=1)

            # === 레시피 (처방내용 + 제조공정/공정검사 통합) ===
            recipe_frame = ctk.CTkFrame(main_container, corner_radius=8)
            recipe_frame.grid(row=0, column=0, sticky="nsew")
            recipe_frame.grid_columnconfigure(0, weight=1)
            recipe_frame.grid_rowconfigure(1, weight=1)
            
            # 헤더 + 안내 메시지
            header_frame = ctk.CTkFrame(recipe_frame, fg_color="transparent")
            header_frame.grid(row=0, column=0, sticky="ew", padx=12, pady=(10,8))
            header_frame.grid_columnconfigure(0, weight=1)
            
            ctk.CTkLabel(header_frame, text="📋 레시피 (처방내용 + 공정)", 
                        font=ctk.CTkFont(size=13, weight="bold")).pack(side="left")
            ctk.CTkLabel(header_frame, text="💡 제조공정/공정검사 셀을 더블클릭하여 Phase별 편집", 
                        font=ctk.CTkFont(size=11), text_color="gray").pack(side="right", padx=(10,0))
            recipe_list_wrap = ctk.CTkFrame(recipe_frame, fg_color="transparent")
            recipe_list_wrap.grid(row=1, column=0, sticky="nsew")
            recipe_list_wrap.grid_columnconfigure(0, weight=1)
            recipe_list_wrap.grid_rowconfigure(0, weight=1)
            
            # Treeview for recipe items (제조공정/공정검사 포함)
            rcols = ("phase","order","code","name","ratio","amount","calc_g","process","inspection")
            # 전역 Treeview 스타일을 오염시키지 않기 위해 전용 스타일 사용
            recipe_tree = ttk.Treeview(recipe_list_wrap, columns=rcols, show="headings", style="Recipe.Treeview")
            recipe_tree.heading("phase", text="Ph."); recipe_tree.column("phase", width=50, anchor="center")
            recipe_tree.heading("order", text="구분"); recipe_tree.column("order", width=50, anchor="center")
            recipe_tree.heading("code", text="코드"); recipe_tree.column("code", width=100)
            recipe_tree.heading("name", text="원료명"); recipe_tree.column("name", width=220, stretch=True)
            recipe_tree.heading("ratio", text="함량(%)"); recipe_tree.column("ratio", width=80, anchor="e")
            recipe_tree.heading("amount", text="중량(실험)"); recipe_tree.column("amount", width=80, anchor="e")
            recipe_tree.heading("calc_g", text="생산량(kg)"); recipe_tree.column("calc_g", width=100, anchor="e")
            recipe_tree.heading("process", text="제조공정"); recipe_tree.column("process", width=200, anchor="w")
            recipe_tree.heading("inspection", text="공정검사"); recipe_tree.column("inspection", width=150, anchor="w")
            recipe_tree.grid(row=0, column=0, sticky="nsew")
            
            # Phase별 시각적 그룹화를 위한 태그 스타일 설정
            style = ttk.Style()

            # 전용 스타일로 행 높이 '정상' 수준으로 설정
            style.configure("Recipe.Treeview", rowheight=30)

            # 테마별 가독성 보장: Light에서는 밝은 톤 배경 + 검은 글씨, Dark에서는 어두운 배경 + 흰 글씨
            try:
                appearance = ctk.get_appearance_mode().lower()
            except Exception:
                appearance = 'dark'

            if appearance == 'light':
                # 밝은 테마: 밝은 배경에 검정 텍스트
                recipe_tree.tag_configure("phase_first", background="#E8F0FE", foreground="black")   # 연한 파란색 톤
                recipe_tree.tag_configure("phase_rest", background="#F5F8FF", foreground="black")    # 더 연한 톤으로 대비
                recipe_tree.tag_configure("phase_border", background="#DDE7F3", foreground="black")  # 경계 강조
            else:
                # 어두운 테마: 기존 색 유지 + 흰 텍스트로 명암 확보
                recipe_tree.tag_configure("phase_first", background="#2b2b2b", foreground="white")
                recipe_tree.tag_configure("phase_rest", background="#1a1a1a", foreground="white")
                recipe_tree.tag_configure("phase_border", background="#3a3a3a", foreground="white")
            
            rscroll = ttk.Scrollbar(recipe_list_wrap, orient="vertical", command=recipe_tree.yview)
            recipe_tree.configure(yscrollcommand=rscroll.set)
            rscroll.grid(row=0, column=1, sticky="ns")

            # === 함수 정의를 먼저 해야 함 (populate_recipe_items에서 사용) ===
            def split_instruction(instr_text: str):
                """
                제조공정과 공정검사를 분리합니다.
                구분자: "---" 또는 "===", 없으면 전체를 제조공정으로 간주
                형식: "제조공정내용\n---\n공정검사내용" 또는 "제조공정내용\n===\n공정검사내용"
                """
                instr_text = (instr_text or "").strip()
                if not instr_text:
                    return ("", "")
                
                # 구분자로 분리
                if "\n---\n" in instr_text:
                    parts = instr_text.split("\n---\n", 1)
                    return (parts[0].strip(), parts[1].strip() if len(parts) > 1 else "")
                elif "\n===\n" in instr_text:
                    parts = instr_text.split("\n===\n", 1)
                    return (parts[0].strip(), parts[1].strip() if len(parts) > 1 else "")
                else:
                    # 구분자가 없으면 전체를 제조공정으로 간주
                    return (instr_text, "")

            def compose_instruction(process_text: str, inspection_text: str):
                """
                제조공정과 공정검사를 결합합니다.
                형식: "제조공정\n---\n공정검사"
                """
                p = (process_text or "").strip()
                q = (inspection_text or "").strip()
                if p and q:
                    return p + "\n---\n" + q
                elif p:
                    return p
                elif q:
                    return "---\n" + q  # 제조공정이 없으면 구분자만 붙임
                return ""

            def populate_recipe_items():
                # 아이템 스냅샷 표시 + 기준중량으로 환산값 계산 + Phase별 제조공정/공정검사 표시
                for i in recipe_tree.get_children():
                    recipe_tree.delete(i)
                
                try:
                    items = json.loads(prod.items_snapshot) if prod.items_snapshot else []
                except Exception:
                    items = []
                base_w = prod.base_weight_g or 0
                
                # Phase별 공정 정보 가져오기
                s_proc = db_manager.get_session()
                phase_processes = {}  # Phase별 공정 정보 {phase: (process_text, inspection_text)}
                try:
                    steps = s_proc.query(ProductionStep).filter_by(production_formulation_id=prod_id).order_by(ProductionStep.step_no.asc()).all()
                    for st in steps:
                        if st.phase:
                            if st.phase not in phase_processes:
                                phase_processes[st.phase] = []
                            # instruction을 제조공정과 공정검사로 분리
                            proc, insp = split_instruction(st.instruction or "")
                            phase_processes[st.phase].append((proc, insp))
                finally:
                    s_proc.close()
                
                # Phase별로 제조공정/공정검사를 하나의 문자열로 결합
                phase_merged_processes = {}
                for phase, proc_list in phase_processes.items():
                    all_proc = "\n".join([p[0] for p in proc_list if p[0]]).strip()
                    all_insp = "\n".join([p[1] for p in proc_list if p[1]]).strip()
                    phase_merged_processes[phase] = (all_proc, all_insp)
                
                # Phase 순서로 정렬 (A, B, C...) 및 병합 표시를 위한 Phase 추적
                current_phase = None
                order_counter = 0
                item_ids_by_phase = {}  # Phase별 아이템 ID 추적
                
                for idx, it in enumerate(sorted(items, key=lambda x: (x.get('order') or 0))):
                    ratio = it.get('ratio') or 0
                    calc_g = (base_w * float(ratio) / 100.0) if base_w and isinstance(ratio, (int, float)) else ""
                    calc_kg = (calc_g / 1000.0) if isinstance(calc_g, (int, float)) else ""
                    try:
                        calc_disp = f"{calc_kg:,.1f}" if isinstance(calc_kg, (int, float)) else ""
                    except Exception:
                        calc_disp = str(calc_kg) if calc_kg is not None else ""
                    
                    phase_val = it.get('phase') or ""
                    
                    # Phase 표시 로직
                    is_first_in_phase = False
                    if phase_val != current_phase:
                        # 새로운 Phase 시작
                        current_phase = phase_val
                        order_counter = 1  # Phase 내 순번 초기화
                        is_first_in_phase = True
                        if phase_val:
                            item_ids_by_phase[phase_val] = []
                        
                        # 첫 행에만 Phase와 제조공정/공정검사 표시
                        phase_display = phase_val if phase_val else ""
                        if phase_val and phase_val in phase_merged_processes:
                            process_text, inspection_text = phase_merged_processes[phase_val]
                        else:
                            process_text, inspection_text = "", ""
                    else:
                        # 같은 Phase 내 다음 행 - Ph., 제조공정, 공정검사 모두 빈 문자열
                        order_counter += 1
                        phase_display = ""  # Phase 병합 효과
                        process_text, inspection_text = "", ""  # 제조공정/공정검사 병합 효과
                    
                    # 구분 컬럼에는 Phase 내 순번 표시
                    order_display = str(order_counter) if current_phase else ""
                    
                    # 태그 설정: Phase 정보 + 시각적 그룹화
                    item_tags = [f"phase_{current_phase}"] if current_phase else []
                    if is_first_in_phase:
                        item_tags.append("phase_first")  # 첫 행 스타일
                    else:
                        item_tags.append("phase_rest")   # 나머지 행 스타일
                    
                    # 아이템 삽입
                    item_id = recipe_tree.insert("", "end", 
                        tags=tuple(item_tags),
                        values=(
                            phase_display,  # Ph. 컬럼: Phase (첫 행만 표시, 나머지는 빈 문자열)
                            order_display,  # 구분 컬럼: Phase 내 순번 (1, 2, 3...)
                            it.get('material_code') or "",
                            it.get('material_name') or "",
                            f"{(ratio or 0):.4f}" if isinstance(ratio, (int, float)) else (ratio or ""),
                            it.get('amount') or "",
                            calc_disp,
                            process_text,  # 제조공정 (첫 행만 표시, 나머지는 빈 문자열)
                            inspection_text,  # 공정검사 (첫 행만 표시, 나머지는 빈 문자열)
                        ))
                    
                    # Phase별 아이템 ID 저장
                    if current_phase and current_phase in item_ids_by_phase:
                        item_ids_by_phase[current_phase].append(item_id)



            populate_recipe_items()
            
            # UI 생성 후 메인 창 중앙 배치
            win.update_idletasks()
            parent = self
            parent_x = parent.winfo_rootx()
            parent_y = parent.winfo_rooty()
            parent_w = parent.winfo_width()
            parent_h = parent.winfo_height()
            win_w = win.winfo_width()
            win_h = win.winfo_height()
            x = parent_x + (parent_w - win_w) // 2
            y = parent_y + (parent_h - win_h) // 2
            win.geometry(f"+{x}+{y}")
            
            # 레시피에서 제조공정/공정검사 더블클릭 편집
            def on_recipe_double_click(event):
                item = recipe_tree.identify_row(event.y)
                col = recipe_tree.identify_column(event.x)
                if not item or not col:
                    return
                
                # 컬럼 인덱스 확인 (제조공정 또는 공정검사만 편집 가능)
                try:
                    col_idx = int(col.replace('#', '')) - 1
                except Exception:
                    return
                
                if col_idx < 0 or col_idx >= len(recipe_tree["columns"]):
                    return
                
                col_name = recipe_tree["columns"][col_idx]
                if col_name not in ("process", "inspection"):
                    return  # 제조공정/공정검사 컬럼만 편집 가능
                
                # 선택된 행의 Phase 추출
                tags = recipe_tree.item(item, 'tags')
                phase = None
                for tag in tags:
                    if tag.startswith('phase_'):
                        phase = tag.replace('phase_', '')
                        break
                
                if not phase:
                    messagebox.showwarning("편집 불가", "Phase가 없는 항목은 편집할 수 없습니다.", parent=win)
                    return
                
                # 해당 Phase의 모든 공정을 통합 편집
                open_phase_process_editor(phase, col_name)
            
            def open_phase_process_editor(phase, edit_type):
                """Phase별 제조공정 또는 공정검사 통합 편집"""
                # 현재 Phase의 모든 공정 가져오기
                s_edit = db_manager.get_session()
                try:
                    steps = s_edit.query(ProductionStep).filter_by(
                        production_formulation_id=prod_id, 
                        phase=phase
                    ).order_by(ProductionStep.step_no.asc()).all()
                    
                    # 현재 내용 추출
                    current_texts = []
                    for st in steps:
                        proc, insp = split_instruction(st.instruction or "")
                        if edit_type == "process":
                            current_texts.append(proc)
                        else:
                            current_texts.append(insp)
                    
                    current_text = "\n".join([t for t in current_texts if t]).strip()
                    
                finally:
                    s_edit.close()
                
                # 편집 다이얼로그
                edit_win = ctk.CTkToplevel(win)
                edit_win.title(f"Phase {phase} - {'제조공정' if edit_type == 'process' else '공정검사'} 편집")
                edit_win.geometry("525x600")  # 700 * 3/4 = 525
                edit_win.resizable(True, True)  # 크기 조절 및 최대화 버튼 활성화
                edit_win.minsize(400, 400)  # 최소 크기만 제한
                # edit_win.transient(win)  # 최대화 버튼을 활성화하기 위해 transient 제거
                edit_win.grab_set()
                edit_win.after(100, lambda: print(f"[WINDOW SIZE] 공정 편집 | geometry: {edit_win.winfo_width()}x{edit_win.winfo_height()} | requested: 525x600"))
                
                ctk.CTkLabel(edit_win, text=f"Phase {phase} {'제조공정' if edit_type == 'process' else '공정검사'}", 
                            font=ctk.CTkFont(size=14, weight="bold")).pack(pady=(15,10), padx=20)
                
                # 공정검사인 경우 체크박스 추가
                if edit_type == "inspection":
                    checkbox_frame = ctk.CTkFrame(edit_win, fg_color="transparent")
                    checkbox_frame.pack(fill="x", padx=20, pady=(0,10))
                    
                    ctk.CTkLabel(checkbox_frame, text="표준 검사 항목:", 
                                font=ctk.CTkFont(size=12, weight="bold")).pack(anchor="w", pady=(0,5))
                    
                    # 표준 검사 항목 템플릿
                    inspection_items = [
                        ("시간", "시간 :"),
                        ("온도", "온도 :              ℃"),
                        ("H/M", "H/M :              rpm"),
                        ("P/M", "P/M :              rpm"),
                        ("HE/M", "HE/M:              rpm"),
                        ("전체 템플릿", "시간 :\n온도 :              ℃\nH/M :              rpm\nP/M :              rpm\nHE/M:              rpm")
                    ]
                    
                    inspection_vars = {}
                    items_grid = ctk.CTkFrame(checkbox_frame, fg_color="transparent")
                    items_grid.pack(fill="x")
                    
                    for idx, (label, content) in enumerate(inspection_items):
                        var = ctk.BooleanVar()
                        inspection_vars[label] = content  # 라벨을 키로, 실제 내용을 값으로 저장
                        chk = ctk.CTkCheckBox(items_grid, text=label, variable=var, width=120)
                        # var를 체크박스 위젯에 저장
                        chk._var = var
                        chk._label = label
                        row = idx // 3  # 3열 배치
                        col = idx % 3
                        chk.grid(row=row, column=col, sticky="w", padx=5, pady=2)
                    
                    def add_selected_items():
                        selected_contents = []
                        for widget in items_grid.winfo_children():
                            if isinstance(widget, ctk.CTkCheckBox) and widget._var.get():
                                selected_contents.append(inspection_vars[widget._label])
                        
                        if selected_contents:
                            current = text_box.get("1.0", "end-1c").strip()
                            new_items = "\n".join(selected_contents)
                            if current:
                                text_box.insert("end", "\n" + new_items)
                            else:
                                text_box.insert("1.0", new_items)
                    
                    ctk.CTkButton(checkbox_frame, text="선택 항목 추가", 
                                 command=add_selected_items, width=120).pack(pady=(10,0))
                
                text_box = ctk.CTkTextbox(edit_win, wrap="word", fg_color="#404040", text_color="white")
                text_box.pack(fill="both", expand=True, padx=20, pady=(0,15))
                text_box.insert("1.0", current_text)
                
                def save_phase_process():
                    new_text = text_box.get("1.0", "end-1c").strip()
                    
                    s_save = db_manager.get_session()
                    try:
                        steps = s_save.query(ProductionStep).filter_by(
                            production_formulation_id=prod_id, 
                            phase=phase
                        ).order_by(ProductionStep.step_no.asc()).all()
                        
                        # 공정이 없으면 새로 생성
                        if not steps:
                            st = ProductionStep(
                                production_formulation_id=prod_id,
                                phase=phase,
                                step_no=1,
                                instruction=new_text if edit_type == "process" else f"\n{new_text}"
                            )
                            s_save.add(st)
                        else:
                            # 첫 번째 공정에만 저장 (나머지는 삭제하거나 하나로 통합)
                            for st in steps:
                                proc, insp = split_instruction(st.instruction or "")
                                if edit_type == "process":
                                    st.instruction = compose_instruction(new_text, insp)
                                else:
                                    st.instruction = compose_instruction(proc, new_text)
                        
                        s_save.commit()
                        messagebox.showinfo("저장 완료", f"Phase {phase}의 공정이 저장되었습니다.", parent=edit_win)
                        edit_win.destroy()
                        populate_recipe_items()  # 레시피 새로고침
                        
                    except Exception as ex:
                        s_save.rollback()
                        messagebox.showerror("오류", f"저장 실패: {ex}", parent=edit_win)
                    finally:
                        s_save.close()
                
                btn_frame = ctk.CTkFrame(edit_win, fg_color="transparent")
                btn_frame.pack(pady=(0,15))
                ctk.CTkButton(btn_frame, text="저장", width=100, command=save_phase_process).pack(side="left", padx=5)
                ctk.CTkButton(btn_frame, text="취소", width=100, fg_color="gray", command=edit_win.destroy).pack(side="left", padx=5)
                
                # 공정 편집 창을 부모(생산처방 편집) 창 중앙에 배치
                edit_win.update_idletasks()
                parent_x = win.winfo_rootx()
                parent_y = win.winfo_rooty()
                parent_w = win.winfo_width()
                parent_h = win.winfo_height()
                edit_w = edit_win.winfo_width()
                edit_h = edit_win.winfo_height()
                x = parent_x + (parent_w - edit_w) // 2
                y = parent_y + (parent_h - edit_h) // 2
                edit_win.geometry(f"+{x}+{y}")
            
            recipe_tree.bind("<Double-1>", on_recipe_double_click)

        finally:
            session.close()

    def create_production_formulation(self):
        # 생성 권한: RD+만 허용
        try:
            if self._role_level() < 1:
                messagebox.showwarning("권한 없음", "생산처방 생성 권한이 없습니다.", parent=self)
                return
        except Exception:
            pass
        # 선택된 처방 ID가 없다면 현재 트리뷰의 선택을 한 번 더 확인하여 보조적으로 설정합니다.
        if not getattr(self, '_selected_formulation_id', None):
            try:
                if hasattr(self, 'formulation_tree'):
                    sel = self.formulation_tree.selection()
                    if sel and len(sel) == 1:
                        try:
                            self._selected_formulation_id = int(sel[0])
                        except Exception:
                            self._selected_formulation_id = None
            except Exception:
                pass
        if not self._selected_formulation_id:
            messagebox.showwarning("선택 필요", "생산처방으로 확정할 처방을 먼저 선택하세요.\n(처방 목록 탭에서 단일 처방을 선택한 뒤 다시 시도하세요)", parent=self)
            return

        # DB에서 소스 처방 로드
        session = db_manager.get_session()
        try:
            src = session.query(Formulation).filter_by(id=self._selected_formulation_id).first()
            if not src:
                messagebox.showerror("오류", "선택된 처방을 찾을 수 없습니다.", parent=self)
                return
            # 다이얼로그 구성
            dlg = ctk.CTkToplevel(self)
            dlg.title("생산처방 생성")
            dlg.transient(self)
            dlg.grab_set()

            frm = ctk.CTkFrame(dlg)
            frm.pack(padx=20, pady=20, fill="both", expand=True)

            def add_row(r, label, w=260):
                ctk.CTkLabel(frm, text=label).grid(row=r, column=0, sticky="w", pady=4)
                e = ctk.CTkEntry(frm, width=w)
                e.grid(row=r, column=1, sticky="ew", pady=4)
                return e

            frm.grid_columnconfigure(1, weight=1)
            name_e = add_row(0, "제품명")
            name_e.insert(0, src.experiment_name or "")
            lab_e = add_row(1, "LAB NO.")
            lab_e.insert(0, src.lab_no or "")
            prodcode_e = add_row(2, "생산코드")
            rev_e = add_row(3, "차수")
            rev_e.insert(0, src.revision or "")
            # 업체명: 타겟 거래처 텍스트 우선, 없으면 OEM/ODM 거래처명
            client_e = add_row(4, "업체명")
            initial_client_name = (src.target_client_id or "").strip() or ((src.oem_odm_client.name or "") if src.oem_odm_client else "")
            client_e.insert(0, initial_client_name)
            base_e = add_row(5, "생산량(kg)")
            try:
                qv = float(self.quotation_weight_entry.get())
                base_e.insert(0, f"{qv/1000:.1f}")
            except Exception:
                base_e.insert(0, "1.0")

            # 날짜 유틸: 휴일 로드 + 다음 영업일 계산 (주말 + config.ini Holidays.dates)
            def _load_holidays():
                hol = set()
                try:
                    from modules.excel_handler import CONFIG_FILE_PATH
                except Exception:
                    CONFIG_FILE_PATH = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'config.ini')
                try:
                    cfg = configparser.ConfigParser(); cfg.read(CONFIG_FILE_PATH, encoding='utf-8')
                    dates_str = cfg.get('Holidays', 'dates', fallback='').strip()
                    if dates_str:
                        for s in dates_str.split(','):
                            s = s.strip()
                            try:
                                hol.add(datetime.strptime(s, '%Y-%m-%d').date())
                            except Exception:
                                pass
                except Exception:
                    pass
                return hol

            HOLIDAYS = _load_holidays()

            def _is_business_day(d: date) -> bool:
                # 월=0..일=6, 주말(토/일) 제외 + 설정된 휴일 제외
                if d.weekday() >= 5:
                    return False
                if d in HOLIDAYS:
                    return False
                return True

            def _next_business_day(start: date) -> date:
                # start 다음날부터 체크하여 영업일 반환
                cur = start + timedelta(days=1)
                while not _is_business_day(cur):
                    cur += timedelta(days=1)
                return cur

            # 지시일(달력) + 제조일(달력, 자동계산되나 수정 가능)
            ctk.CTkLabel(frm, text="지시일").grid(row=5, column=0, sticky="w", pady=4)
            directive_de = DateEntry(frm, date_pattern='yyyy-mm-dd', state='normal')
            directive_de.grid(row=5, column=1, sticky="w", pady=4)
            directive_de.set_date(datetime.now().date())

            ctk.CTkLabel(frm, text="제조일").grid(row=6, column=0, sticky="w", pady=4)
            mfg_de = DateEntry(frm, date_pattern='yyyy-mm-dd', state='normal')
            mfg_de.grid(row=6, column=1, sticky="w", pady=4)
            try:
                mfg_de.set_date(_next_business_day(datetime.now().date()))
            except Exception:
                mfg_de.set_date(datetime.now().date())

            def on_directive_changed(_evt=None):
                try:
                    d = directive_de.get_date()
                    mfg_de.set_date(_next_business_day(d))
                except Exception:
                    pass

            # 달력 선택 이벤트 + 수동 입력 포커스 아웃에도 동작
            try:
                directive_de.bind('<<DateEntrySelected>>', on_directive_changed)
            except Exception:
                pass
            try:
                directive_de.bind('<FocusOut>', on_directive_changed)
            except Exception:
                pass

            ctk.CTkLabel(frm, text="상태").grid(row=7, column=0, sticky="w", pady=4)
            allowed_statuses = self.allowed_status_values_for_create()
            # 허용 상태가 없으면 진입 자체가 차단되었겠지만 안전망
            if not allowed_statuses:
                allowed_statuses = ['초안']
            status_var = tk.StringVar(value=allowed_statuses[0])
            status_opt = ctk.CTkOptionMenu(frm, values=allowed_statuses, variable=status_var)
            status_opt.grid(row=7, column=1, sticky="w", pady=4)

            ctk.CTkLabel(frm, text="비고").grid(row=8, column=0, sticky="nw", pady=4)
            notes_t = ctk.CTkTextbox(frm, height=80)
            notes_t.grid(row=8, column=1, sticky="nsew", pady=4)

            btns = ctk.CTkFrame(frm, fg_color="transparent")
            btns.grid(row=9, column=0, columnspan=2, sticky="e", pady=(10,0))
            # 저장 중복 방지 플래그
            save_in_progress = {"flag": False}

            def on_save():
                # 재진입 방지
                if save_in_progress["flag"]:
                    return
                save_in_progress["flag"] = True
                try:
                    save_btn.configure(state="disabled")
                except Exception:
                    pass
                try:
                    base_w_kg = float(base_e.get().replace(',','')) if base_e.get() else 1.0
                except Exception:
                    base_w_kg = 1.0
                try:
                    try:
                        eff_date = mfg_de.get_date()
                    except Exception:
                        eff_date = None
                except Exception:
                    eff_date = None

                # 스냅샷 구성(처방 아이템) - 줄내림을 기준으로 Phase 자동 할당
                items = []
                try:
                    # 줄내림을 기준으로 Phase를 A, B, C... 순서로 할당
                    phase_letter = 'A'
                    phase_counter = 0
                    
                    for it in sorted(src.items, key=lambda x: x.order if x.order is not None else 999999):
                        material_code = it.material_code or ""
                        is_separator = material_code.strip() in ["---", "-", "--", "―", "ㅡ"]
                        
                        if is_separator:
                            # 줄내림은 스킵하고 다음 Phase로 넘어감
                            phase_counter += 1
                            phase_letter = chr(ord('A') + phase_counter) if phase_counter < 26 else f"Phase{phase_counter+1}"
                            continue
                        
                        # 일반 원료는 현재 Phase 할당
                        items.append({
                            'order': it.order,
                            'phase': phase_letter,
                            'material_code': it.material_code,
                            'material_name': it.material_name,
                            'ratio': it.ratio,
                            'amount': it.amount,
                        })
                except Exception:
                    pass

                try:
                    newp = ProductionFormulation(
                        source_formulation_id=src.id,
                        product_name=name_e.get().strip() or (src.experiment_name or ''),
                        production_code=prodcode_e.get().strip() or None,
                        lab_no=lab_e.get().strip() or src.lab_no,
                        revision=rev_e.get().strip() or src.revision,
                        client_name=client_e.get().strip() or None,
                        base_weight_g=base_w_kg * 1000.0,
                        status=status_var.get(),
                        effective_date=eff_date,
                        approved_by_user_id=getattr(self.current_user, 'id', None),
                        notes=notes_t.get('1.0','end').strip(),
                        items_snapshot=json.dumps(items, ensure_ascii=False),
                    )
                    session.add(newp)
                    session.commit()
                    messagebox.showinfo("완료", "생산처방이 생성되었습니다.", parent=dlg)
                    dlg.destroy()
                    # Reset production view to client level to ensure new formulation is visible
                    self.show_production_folder_view()
                    # Also ensure refresh is called
                    self.refresh_production_list()
                except Exception as ex:
                    session.rollback()
                    messagebox.showerror("오류", f"저장 실패: {ex}", parent=dlg)
                finally:
                    # 에러 시 버튼 복구, 정상 저장 시에는 창이 닫혀 버튼 접근 필요 없음
                    try:
                        save_in_progress["flag"] = False
                        save_btn.configure(state="normal")
                    except Exception:
                        pass

            save_btn = ctk.CTkButton(btns, text="저장", command=on_save)
            save_btn.pack(side="right")
            ctk.CTkButton(btns, text="취소", fg_color="gray", command=dlg.destroy).pack(side="right", padx=(0,6))

            try:
                center_window_on_mouse_display(dlg)
            except Exception:
                pass

            self.wait_window(dlg)
        finally:
            session.close()

    def export_selected_production(self):
        """[사용 중지 예정] JSON 내보내기 (호환용). Excel 전환 이후에는 사용하지 않습니다."""
        prod_id = getattr(self, '_selected_production_id', None)
        if not prod_id:
            messagebox.showwarning("선택 필요", "내보낼 생산처방을 선택하세요.", parent=self)
            return
        session = db_manager.get_session()
        try:
            prod = session.query(ProductionFormulation).filter_by(id=prod_id).first()
            if not prod:
                messagebox.showerror("오류", "생산처방을 찾을 수 없습니다.", parent=self)
                return
            # 저장 위치
            default_name = f"production_{prod.id}_{(prod.product_name or 'product')}.json"
            save_path = filedialog.asksaveasfilename(parent=self, title="생산처방 내보내기", defaultextension=".json",
                                                     initialfile=default_name,
                                                     filetypes=[("JSON Files", "*.json"), ("All Files", "*.*")])
            if not save_path:
                return
            # 데이터 구성
            steps = session.query(ProductionStep).filter_by(production_formulation_id=prod.id).order_by(ProductionStep.step_no.asc(), ProductionStep.id.asc()).all()
            out = {
                "production_formulation": {
                    "id": prod.id,
                    "source_formulation_id": prod.source_formulation_id,
                    "product_name": prod.product_name,
                    "production_code": prod.production_code,
                    "lab_no": prod.lab_no,
                    "revision": prod.revision,
                    "base_weight_g": prod.base_weight_g,
                    "status": prod.status,
                    "effective_date": prod.effective_date.strftime('%Y-%m-%d') if prod.effective_date else None,
                    "approved_by_user_id": prod.approved_by_user_id,
                    "notes": prod.notes,
                    "created_at": prod.created_at.strftime('%Y-%m-%d %H:%M') if prod.created_at else None,
                },
                "items_snapshot": json.loads(prod.items_snapshot) if prod.items_snapshot else None,
                "steps": [
                    {
                        "step_no": st.step_no,
                        "phase": st.phase,
                        "instruction": st.instruction,
                        "temperature": st.temperature,
                        "time_min": st.time_min,
                        "rpm": st.rpm,
                        "equipment": st.equipment,
                        "notes": st.notes,
                    } for st in steps
                ]
            }
            with open(save_path, 'w', encoding='utf-8') as f:
                json.dump(out, f, ensure_ascii=False, indent=2)
            messagebox.showinfo("완료", "생산처방 내보내기가 완료되었습니다.", parent=self)
        except Exception as ex:
            messagebox.showerror("오류", f"내보내기 실패: {ex}", parent=self)
        finally:
            session.close()

    def export_selected_production_to_excel(self):
        """선택된 생산처방을 엑셀 파일로 내보냅니다 (요구사항: 생산처방 모든 내보내기 = 엑셀)."""
        prod_id = getattr(self, '_selected_production_id', None)
        if not prod_id:
            messagebox.showwarning("선택 필요", "내보낼 생산처방을 선택하세요.", parent=self)
            return
        session = db_manager.get_session()
        try:
            prod = session.query(ProductionFormulation).filter_by(id=prod_id).first()
            if not prod:
                messagebox.showerror("오류", "생산처방을 찾을 수 없습니다.", parent=self)
                return
            # 사용 권한 확인 (상태 기반)
            try:
                if not self.can_use_production(prod):
                    messagebox.showwarning("권한 없음", f"현재 계정으로는 상태 '{prod.status or ''}' 문서를 사용할 수 없습니다.", parent=self)
                    return
            except Exception:
                pass
            # 승인자명 표시용
            approver_name = ""
            try:
                approver_name = (prod.approved_by.real_name or prod.approved_by.username) if prod.approved_by else ""
            except Exception:
                approver_name = ""

            # 거래처명 계산 (생산처방에 저장된 값 우선, 없으면 소스 처방에서 가져오기)
            client_name = ""
            try:
                client_name = (prod.client_name or "").strip()
                if not client_name:
                    sf = prod.source_formulation
                    if sf:
                        client_name = (sf.target_client_id or "").strip() or ((sf.oem_odm_client.name or "") if sf.oem_odm_client else "")
            except Exception:
                client_name = ""

            # 공정 단계 로드 및 phase별 제조공정/공정검사 맵 구성
            steps = (
                session.query(ProductionStep)
                .filter_by(production_formulation_id=prod.id)
                .order_by(ProductionStep.step_no.asc(), ProductionStep.id.asc())
                .all()
            )
            prefixes = ("시간", "온도", "HE/M", "H/M", "P/M", "HE/M:", "H/M:", "P/M:")
            phase_map = {}
            def _norm_phase(x):
                return (str(x or '').strip().upper())
            for st in steps:
                ph = _norm_phase(st.phase)
                entry = phase_map.get(ph) or {"proc": [], "insp": []}
                instr = (st.instruction or '').strip()
                for ln in instr.splitlines():
                    lt = ln.strip()
                    if not lt:
                        continue
                    if lt.startswith(prefixes):
                        entry["insp"].append(lt)
                    else:
                        entry["proc"].append(lt)
                phase_map[ph] = entry

            # 아이템 스냅샷 파싱 및 행 구성
            try:
                items_snapshot = json.loads(prod.items_snapshot) if prod.items_snapshot else []
            except Exception:
                items_snapshot = []

            def to_float_safe(v):
                try:
                    return float(v)
                except Exception:
                    return None

            base_w = prod.base_weight_g or 0
            rows = []
            # Phase별 그룹화를 위한 추적
            current_phase = None
            phase_order_counter = 0  # Phase 내 순번
            
            for it in sorted(items_snapshot, key=lambda x: (x.get('order') or 0)):
                ratio = to_float_safe(it.get('ratio'))
                calc_g = (base_w * ratio / 100.0) if (base_w and ratio is not None) else None
                calc_kg = (calc_g / 1000.0) if isinstance(calc_g, (int, float)) else None
                
                phase_val = it.get('phase') or ""
                ph_key = _norm_phase(phase_val)
                pm = phase_map.get(ph_key) or {"proc": [], "insp": []}
                
                # Phase 표시 및 제조공정/공정검사: 첫 번째 행에만 표시
                if phase_val != current_phase:
                    current_phase = phase_val
                    phase_order_counter = 1  # Phase 내 순번 초기화
                    phase_display = phase_val
                    # 첫 행에만 제조공정/공정검사 표시 (쌍따옴표 제거)
                    process_text = "\n".join(pm.get('proc') or []).replace('"', '').replace("'", '')
                    inspection_text = "\n".join(pm.get('insp') or []).replace('"', '').replace("'", '')
                else:
                    phase_order_counter += 1
                    phase_display = ""  # 같은 Phase 내에서는 빈 문자열
                    process_text = ""  # 같은 Phase 내에서는 빈 문자열
                    inspection_text = ""  # 같은 Phase 내에서는 빈 문자열
                
                rows.append({
                    "Ph.": phase_display,  # Phase (A, B, C...) - 첫 행에만 표시
                    "구분": str(phase_order_counter) if current_phase else "",  # Phase 내 순번 (1, 2, 3...)
                    "코드": it.get('material_code') or "",
                    "원료명": it.get('material_name') or "",
                    "함량(%)": ratio if ratio is not None else it.get('ratio') or "",
                    "생산량(kg)": calc_kg,
                    "제조공정": process_text,  # 첫 행에만 표시
                    "공정검사": inspection_text,  # 첫 행에만 표시
                })

            # 단계 상세(제조공정 시트용)
            step_rows = []
            for st in steps:
                # instruction에서 공정과 검사 텍스트 분리
                proc_lines, insp_lines = [], []
                instr = (st.instruction or '').strip()
                for ln in instr.splitlines():
                    lt = ln.strip()
                    if not lt:
                        continue
                    if lt.startswith(prefixes):
                        insp_lines.append(lt)
                    else:
                        proc_lines.append(lt)
                step_rows.append({
                    "단계": st.step_no,
                    "구분": (st.phase or '').strip(),
                    "제조공정": "\n".join(proc_lines),
                    "공정검사": "\n".join(insp_lines),
                    "온도": st.temperature or "",
                    "시간(분)": st.time_min if st.time_min is not None else "",
                    "RPM": st.rpm or "",
                    "장비": st.equipment or "",
                    "비고": st.notes or "",
                })

            details = {
                "제품명": prod.product_name or "",
                "생산코드": prod.production_code or "",
                "LAB NO.": prod.lab_no or "",
                "차수": prod.revision or "",
                "거래처": client_name or "",
                "결제방": prod.payment_room or "",
                "생산량(kg)": f"{(base_w/1000):,.1f} kg" if isinstance(base_w, (int, float)) else (base_w or ""),
                "제조일": prod.effective_date.strftime('%Y-%m-%d') if prod.effective_date else "",
                "상태": prod.status or "",
                "승인자": approver_name or "",
                "비고": (prod.notes or "").strip(),
                "출력일시": datetime.now().strftime('%Y-%m-%d %H:%M'),
            }

            production_data = {"details": details, "items": rows, "steps": step_rows}
            default_filename = f"생산처방_{(prod.product_name or '제품')}_{(prod.revision or '')}.xlsx"
            excel_handler.export_production_formulation_to_excel(
                production_data,
                default_filename=default_filename,
                mode="revised"
            )
        except Exception as ex:
            messagebox.showerror("오류", f"내보내기 실패: {ex}", parent=self)
        finally:
            session.close()

    def preview_production_formulation(self):
        """선택된 생산처방 미리보기: 좌 레시피 / 우 도식, 두 컬럼 완전 분할 레이아웃."""
        prod_id = getattr(self, '_selected_production_id', None)
        if not prod_id:
            messagebox.showwarning("선택 필요", "미리보기할 생산처방을 선택하세요.", parent=self)
            return
        session = db_manager.get_session()
        try:
            prod = session.query(ProductionFormulation).filter_by(id=prod_id).first()
            if not prod:
                messagebox.showerror("오류", "생산처방을 찾을 수 없습니다.", parent=self)
                return

            win = ctk.CTkToplevel(self)
            win.title(f"생산처방 미리보기 - {prod.product_name or ''} ({prod.revision or ''})")
            win.geometry("750x680")  # 1000 * 3/4 = 750
            win.resizable(True, True)  # 크기 조절 및 최대화 버튼 활성화
            win.minsize(600, 500)  # 최소 크기만 제한
            # win.transient(self)  # 최대화 버튼을 활성화하기 위해 transient 제거
            win.grab_set()
            win.after(100, lambda: print(f"[WINDOW SIZE] 생산처방 미리보기 | geometry: {win.winfo_width()}x{win.winfo_height()} | requested: 750x680"))

            # 상단 메타 정보
            top = ctk.CTkFrame(win)
            top.pack(fill="x", padx=10, pady=(10,5))
            meta = [
                f"제품명: {prod.product_name or ''}",
                f"차수: {prod.revision or ''}",
                f"LAB NO.: {prod.lab_no or ''}",
                f"생산코드: {prod.production_code or ''}",
                f"제조일: {prod.effective_date.strftime('%Y-%m-%d') if prod.effective_date else ''}",
                f"상태: {prod.status or ''}",
                f"생산량(kg): {((prod.base_weight_g or 0)/1000):.1f}",
            ]
            ctk.CTkLabel(top, text="   ".join(meta)).pack(anchor="w")

            # 데이터 로드 및 재사용 가능한 프리뷰 패널 구성
            steps = session.query(ProductionStep).filter_by(production_formulation_id=prod.id).order_by(ProductionStep.step_no.asc(), ProductionStep.id.asc()).all()
            container = ctk.CTkFrame(win)
            container.pack(fill="both", expand=True, padx=10, pady=(0,10))
            pane = ProductionPreviewPane(
                container,
                prod,
                steps,
                on_export_excel=lambda: self.export_selected_production_to_excel(),
                on_print_preview=lambda: self.print_preview_selected_production()
            )
            pane.pack(fill="both", expand=True)

            # 메인 창 중앙에 배치
            win.update_idletasks()
            parent = self
            parent_x = parent.winfo_rootx()
            parent_y = parent.winfo_rooty()
            parent_w = parent.winfo_width()
            parent_h = parent.winfo_height()
            win_w = win.winfo_width()
            win_h = win.winfo_height()
            x = parent_x + (parent_w - win_w) // 2
            y = parent_y + (parent_h - win_h) // 2
            win.geometry(f"+{x}+{y}")

            self.wait_window(win)
        finally:
            session.close()

    def print_preview_selected_production(self):
        """선택된 생산처방을 프로그램 내 A4 이미지 미리보기로 표시합니다.
        - 레이아웃은 엑셀 내보내기(수정본)과 동일하게 렌더링됩니다.
        """
        prod_id = getattr(self, '_selected_production_id', None)
        if not prod_id:
            messagebox.showwarning("선택 필요", "미리보기할 생산처방을 선택하세요.", parent=self)
            return
        session = db_manager.get_session()
        try:
            prod = session.query(ProductionFormulation).filter_by(id=prod_id).first()
            if not prod:
                messagebox.showerror("오류", "생산처방을 찾을 수 없습니다.", parent=self)
                return
            # 사용 권한 확인 (상태 기반)
            try:
                if not self.can_use_production(prod):
                    messagebox.showwarning("권한 없음", f"현재 계정으로는 상태 '{prod.status or ''}' 문서를 사용할 수 없습니다.", parent=self)
                    return
            except Exception:
                pass

            # 승인자명 표시용
            try:
                approver_name = (prod.approved_by.real_name or prod.approved_by.username) if prod.approved_by else ""
            except Exception:
                approver_name = ""

            # 거래처명 계산 (생산처방에 저장된 값 우선, 없으면 소스 처방에서 가져오기)
            client_name = ""
            try:
                client_name = (prod.client_name or "").strip()
                if not client_name:
                    sf = prod.source_formulation
                    if sf:
                        client_name = (sf.target_client_id or "").strip() or ((sf.oem_odm_client.name or "") if sf.oem_odm_client else "")
            except Exception:
                client_name = ""

            # 단계 로드 및 phase별 제조공정/공정검사 맵 구성
            steps = (
                session.query(ProductionStep)
                .filter_by(production_formulation_id=prod.id)
                .order_by(ProductionStep.step_no.asc(), ProductionStep.id.asc())
                .all()
            )
            prefixes = ("시간", "온도", "HE/M", "H/M", "P/M", "HE/M:", "H/M:", "P/M:")
            phase_map = {}
            def _norm_phase(x):
                return (str(x or '').strip().upper())
            for st in steps:
                ph = _norm_phase(st.phase)
                entry = phase_map.get(ph) or {"proc": [], "insp": []}
                instr = (st.instruction or '').strip()
                for ln in instr.splitlines():
                    lt = ln.strip()
                    if not lt:
                        continue
                    if lt.startswith(prefixes):
                        entry["insp"].append(lt)
                    else:
                        entry["proc"].append(lt)
                phase_map[ph] = entry

            # 아이템 스냅샷 파싱 및 행 구성
            try:
                items_snapshot = json.loads(prod.items_snapshot) if prod.items_snapshot else []
            except Exception:
                items_snapshot = []

            def to_float_safe(v):
                try:
                    return float(v)
                except Exception:
                    return None

            base_w = prod.base_weight_g or 0
            rows = []
            current_phase = None
            phase_order_counter = 0
            for it in sorted(items_snapshot, key=lambda x: (x.get('order') or 0)):
                ratio = to_float_safe(it.get('ratio'))
                calc_g = (base_w * ratio / 100.0) if (base_w and ratio is not None) else None
                calc_kg = (calc_g / 1000.0) if isinstance(calc_g, (int, float)) else None

                phase_val = it.get('phase') or ""
                ph_key = _norm_phase(phase_val)
                pm = phase_map.get(ph_key) or {"proc": [], "insp": []}

                if phase_val != current_phase:
                    current_phase = phase_val
                    phase_order_counter = 1
                    phase_display = phase_val
                    process_text = "\n".join(pm.get('proc') or []).replace('"', '').replace("'", '')
                    inspection_text = "\n".join(pm.get('insp') or []).replace('"', '').replace("'", '')
                else:
                    phase_order_counter += 1
                    phase_display = ""
                    process_text = ""
                    inspection_text = ""

                rows.append({
                    "Ph.": phase_display,
                    "구분": str(phase_order_counter) if current_phase else "",
                    "코드": it.get('material_code') or "",
                    "원료명": it.get('material_name') or "",
                    "함량(%)": ratio if ratio is not None else it.get('ratio') or "",
                    "생산량(kg)": calc_kg,
                    "제조공정": process_text,
                    "공정검사": inspection_text,
                })

            step_rows = []
            for st in steps:
                proc_lines, insp_lines = [], []
                instr = (st.instruction or '').strip()
                for ln in instr.splitlines():
                    lt = ln.strip()
                    if not lt:
                        continue
                    if lt.startswith(prefixes):
                        insp_lines.append(lt)
                    else:
                        proc_lines.append(lt)
                step_rows.append({
                    "단계": st.step_no,
                    "구분": (st.phase or '').strip(),
                    "제조공정": "\n".join(proc_lines),
                    "공정검사": "\n".join(insp_lines),
                    "온도": st.temperature or "",
                    "시간(분)": st.time_min if st.time_min is not None else "",
                    "RPM": st.rpm or "",
                    "장비": st.equipment or "",
                    "비고": st.notes or "",
                })

            details = {
                "제품명": prod.product_name or "",
                "생산코드": prod.production_code or "",
                "LAB NO.": prod.lab_no or "",
                "차수": prod.revision or "",
                "거래처": client_name or "",
                "결제방": prod.payment_room or "",
                "생산량(kg)": f"{(base_w/1000):,.1f} kg" if isinstance(base_w, (int, float)) else (base_w or ""),
                "제조일": prod.effective_date.strftime('%Y-%m-%d') if prod.effective_date else "",
                "상태": prod.status or "",
                "승인자": approver_name or "",
                "비고": (prod.notes or "").strip(),
                "출력일시": datetime.now().strftime('%Y-%m-%d %H:%M'),
            }

            production_data = {"details": details, "items": rows, "steps": step_rows}
            # 내장 A4 미리보기 실행 (엑셀 수정본과 동일 레이아웃)
            show_production_print_preview(production_data, parent=self)
        except Exception as ex:
            messagebox.showerror("오류", f"미리보기 실패: {ex}", parent=self)
        finally:
            session.close()

    def refresh_package_list(self):
        if not hasattr(self, 'package_tree'):
            return
        for item in self.package_tree.get_children():
            self.package_tree.delete(item)
        
        session = db_manager.get_session()
        try:
            if self._selected_formulation_id:
                # 실험처방이 선택된 경우: 해당 처방과 관련된 패키지만 표시
                # 1) 실험처방에 직접 연결된 패키지
                pkgs = session.query(DocumentPackage).filter_by(formulation_id=self._selected_formulation_id).order_by(DocumentPackage.created_at.desc()).all()
                # 2) 선택된 실험처방에서 파생된 생산처방에 연결된 패키지 포함
                try:
                    prod_ids = [pid for (pid,) in session.query(ProductionFormulation.id).filter_by(source_formulation_id=self._selected_formulation_id).all()]
                    if prod_ids:
                        more = (
                            session.query(DocumentPackage)
                            .filter(DocumentPackage.production_formulation_id.in_(prod_ids))
                            .order_by(DocumentPackage.created_at.desc())
                            .all()
                        )
                        existing_ids = {p.id for p in pkgs}
                        pkgs.extend([m for m in more if m.id not in existing_ids])
                except Exception:
                    pass
            else:
                # 실험처방이 선택되지 않은 경우: 모든 패키지 표시
                pkgs = session.query(DocumentPackage).order_by(DocumentPackage.created_at.desc()).all()
            
            for p in pkgs:
                creator = ""
                try:
                    creator = (p.created_by.real_name or p.created_by.username) if p.created_by else ""
                except Exception:
                    pass
                created_str = p.created_at.strftime("%Y-%m-%d %H:%M") if p.created_at else ""
                self.package_tree.insert("", "end", iid=p.id, values=(p.name or "", created_str, creator, p.revision or ""))
        finally:
            session.close()

    def on_package_tree_select(self, event):
        # 현재는 별도 처리 없이도 충분하지만, 추후 버튼 활성화/비활성화를 제어하려면 이곳에서 처리
        pass

    def _get_selected_package_id(self):
        if not hasattr(self, 'package_tree'):
            return None
        sel = self.package_tree.selection()
        if not sel:
            return None
        iid = sel[0]
        try:
            return int(iid)
        except Exception:
            return None

    def open_selected_package_detail(self):
        pkg_id = self._get_selected_package_id()
        if not pkg_id:
            messagebox.showwarning("선택 필요", "상세를 볼 패키지를 선택하세요.", parent=self)
            return
        self.open_package_detail_window(pkg_id)

    def open_package_detail_window(self, package_id: int):
        session = db_manager.get_session()
        try:
            pkg = session.query(DocumentPackage).filter_by(id=package_id).first()
            if not pkg:
                messagebox.showerror("오류", "패키지를 찾을 수 없습니다.", parent=self)
                return

            win = ctk.CTkToplevel(self)
            win.title(f"패키지 상세 - {pkg.name}")
            win.geometry("1000x700")
            win.resizable(True, True)
            win.minsize(900, 600)
            win.transient(self)  # 메인 창에 종속
            win.grab_set()
            
            # 메인 창 중앙에 배치
            win.update_idletasks()
            parent_x = self.winfo_rootx()
            parent_y = self.winfo_rooty()
            parent_w = self.winfo_width()
            parent_h = self.winfo_height()
            win_w = win.winfo_width()
            win_h = win.winfo_height()
            x = parent_x + (parent_w - win_w) // 2
            y = parent_y + (parent_h - win_h) // 2
            win.geometry(f"+{x}+{y}")

            # 상단: 패키지 기본 정보
            top = ctk.CTkFrame(win)
            top.pack(fill="x", padx=10, pady=(10,5))
            
            # 패키지 유형 표시
            pkg_type = "생산처방 패키지" if pkg.production_formulation_id else "실험처방 패키지"
            
            info_text = (
                f"[{pkg_type}] 제품: {pkg.product_name or ''}   차수: {pkg.revision or ''}   생성: "
                f"{pkg.created_at.strftime('%Y-%m-%d %H:%M') if pkg.created_at else ''}   작성자: "
            )
            try:
                creator = (pkg.created_by.real_name or pkg.created_by.username) if pkg.created_by else ""
            except Exception:
                creator = ""
            info = ctk.CTkLabel(top, text=info_text + creator, font=ctk.CTkFont(size=13, weight="bold"))
            info.pack(anchor="w", pady=5)

            # 탭뷰 생성
            tabview = ctk.CTkTabview(win)
            tabview.pack(fill="both", expand=True, padx=10, pady=(5,10))
            
            # 탭 추가
            tab_formulation = tabview.add("실험처방")
            tab_ingredients = tabview.add("전성분")
            tab_quotation = tabview.add("견적")
            tab_production = tabview.add("생산처방")
            tab_documents = tabview.add("문서 링크")
            tab_attachments = tabview.add("첨부파일")

            # 스냅샷 데이터 파싱
            try:
                full_snapshot = json.loads(pkg.quotation_snapshot) if pkg.quotation_snapshot else {}
            except Exception:
                full_snapshot = {}

            # === 탭 1: 실험처방 정보 ===
            formulation_frame = ctk.CTkScrollableFrame(tab_formulation)
            formulation_frame.pack(fill="both", expand=True, padx=10, pady=10)
            
            formulation_info = full_snapshot.get("formulation_info", {})
            if formulation_info:
                info_text = f"""실험품명: {formulation_info.get('실험품명', '')}
LAB NO: {formulation_info.get('LAB NO', '')}
차수: {formulation_info.get('차수', '')}
실험일: {formulation_info.get('실험일', '')}
담당자: {formulation_info.get('담당자', '')}
샘플발송횟수: {formulation_info.get('샘플발송횟수', 0)}
샘플발송일: {formulation_info.get('샘플발송일', '')}
비고: {formulation_info.get('비고', '')}
"""
                ctk.CTkLabel(formulation_frame, text="기본 정보", font=ctk.CTkFont(weight="bold", size=14)).pack(anchor="w", pady=(0,10))
                info_box = ctk.CTkTextbox(formulation_frame, height=150)
                info_box.pack(fill="x", pady=(0,15))
                info_box.insert("1.0", info_text)
                info_box.configure(state="disabled")
                
                # 원료 목록
                materials = full_snapshot.get("formulation_materials", [])
                if materials:
                    ctk.CTkLabel(formulation_frame, text="원료 목록", font=ctk.CTkFont(weight="bold", size=14)).pack(anchor="w", pady=(10,10))
                    
                    # Treeview로 원료 목록 표시
                    tree_frame = ctk.CTkFrame(formulation_frame)
                    tree_frame.pack(fill="x")
                    
                    # 행 수에 따라 높이 조정 (최소 8, 최대 15)
                    tree_height = min(max(len(materials), 8), 15)
                    
                    material_tree = ttk.Treeview(tree_frame, columns=("순번","원료코드","원료명","함량","제조사","공급사","원산지"), show="headings", height=tree_height)
                    material_tree.heading("순번", text="순번")
                    material_tree.heading("원료코드", text="원료코드")
                    material_tree.heading("원료명", text="원료명")
                    material_tree.heading("함량", text="함량(%)")
                    material_tree.heading("제조사", text="제조사")
                    material_tree.heading("공급사", text="공급사")
                    material_tree.heading("원산지", text="원산지")
                    
                    material_tree.column("순번", width=50)
                    material_tree.column("원료코드", width=100)
                    material_tree.column("원료명", width=220)
                    material_tree.column("함량", width=80)
                    material_tree.column("제조사", width=130)
                    material_tree.column("공급사", width=130)
                    material_tree.column("원산지", width=100)
                    
                    for mat in materials:
                        material_tree.insert("", "end", values=(
                            mat.get("순번", ""),
                            mat.get("원료코드", ""),
                            mat.get("원료명", ""),
                            mat.get("함량", ""),
                            mat.get("제조사", ""),
                            mat.get("공급사", ""),
                            mat.get("원산지", "")
                        ))
                    
                    scrollbar = ttk.Scrollbar(tree_frame, orient="vertical", command=material_tree.yview)
                    material_tree.configure(yscrollcommand=scrollbar.set)
                    
                    material_tree.pack(side="left", fill="x", expand=True)
                    scrollbar.pack(side="right", fill="y")
            else:
                ctk.CTkLabel(formulation_frame, text="실험처방 정보가 없습니다.").pack(pady=20)

            # === 탭 2: 전성분 ===
            ingredient_frame = ctk.CTkScrollableFrame(tab_ingredients)
            ingredient_frame.pack(fill="both", expand=True, padx=10, pady=10)
            
            ing_snapshot = full_snapshot.get("ingredients", {})
            if ing_snapshot:
                for sheet_name, content in ing_snapshot.items():
                    ctk.CTkLabel(ingredient_frame, text=sheet_name, font=ctk.CTkFont(weight="bold", size=13)).pack(anchor="w", pady=(10,5))
                    
                    if sheet_name == "디자인 전성분":
                        # 한글/영문 텍스트 표시
                        if isinstance(content, dict):
                            ko_text = content.get("ko", "")
                            en_text = content.get("en", "")
                            
                            if ko_text:
                                ctk.CTkLabel(ingredient_frame, text="한글:", font=ctk.CTkFont(weight="bold")).pack(anchor="w", pady=(5,0))
                                ko_box = ctk.CTkTextbox(ingredient_frame, height=80)
                                ko_box.pack(fill="x", pady=(0,10))
                                ko_box.insert("1.0", ko_text)
                                ko_box.configure(state="disabled")
                            
                            if en_text:
                                ctk.CTkLabel(ingredient_frame, text="영문:", font=ctk.CTkFont(weight="bold")).pack(anchor="w", pady=(5,0))
                                en_box = ctk.CTkTextbox(ingredient_frame, height=80)
                                en_box.pack(fill="x", pady=(0,10))
                                en_box.insert("1.0", en_text)
                                en_box.configure(state="disabled")
                    else:
                        # 테이블 형태 데이터 표시
                        if isinstance(content, dict):
                            headers = content.get("headers", [])
                            rows = content.get("rows", [])
                            
                            if headers and rows:
                                tree_frame = ctk.CTkFrame(ingredient_frame)
                                tree_frame.pack(fill="x", pady=(0,15))
                                
                                # 행 수에 따라 높이 조정 (최소 5, 최대 15)
                                tree_height = min(max(len(rows), 5), 15)
                                
                                tree = ttk.Treeview(tree_frame, columns=headers, show="headings", height=tree_height)
                                for h in headers:
                                    tree.heading(h, text=h)
                                    tree.column(h, width=100)
                                
                                for row in rows:
                                    tree.insert("", "end", values=row)
                                
                                scrollbar = ttk.Scrollbar(tree_frame, orient="vertical", command=tree.yview)
                                tree.configure(yscrollcommand=scrollbar.set)
                                
                                tree.pack(side="left", fill="x", expand=True)
                                scrollbar.pack(side="right", fill="y")
            else:
                ctk.CTkLabel(ingredient_frame, text="전성분 정보가 없습니다.").pack(pady=20)

            # === 탭 3: 견적 ===
            quotation_frame = ctk.CTkScrollableFrame(tab_quotation)
            quotation_frame.pack(fill="both", expand=True, padx=10, pady=10)
            
            quo_snapshot = full_snapshot.get("quotation", {})
            if quo_snapshot:
                # 기본 정보
                details = quo_snapshot.get("details", {})
                if details:
                    ctk.CTkLabel(quotation_frame, text="기본 정보", font=ctk.CTkFont(weight="bold", size=14)).pack(anchor="w", pady=(0,10))
                    details_text = f"""실험품명: {details.get('실험품명', '')}
담당자: {details.get('담당자', '')}
LAB NO.: {details.get('LAB NO.', '')}
기준 중량: {details.get('기준 중량', '')}"""
                    details_box = ctk.CTkTextbox(quotation_frame, height=100)
                    details_box.pack(fill="x", pady=(0,15))
                    details_box.insert("1.0", details_text)
                    details_box.configure(state="disabled")
                
                # 견적 항목
                items = quo_snapshot.get("items", [])
                if items:
                    ctk.CTkLabel(quotation_frame, text="견적 항목", font=ctk.CTkFont(weight="bold", size=14)).pack(anchor="w", pady=(10,10))
                    
                    tree_frame = ctk.CTkFrame(quotation_frame)
                    tree_frame.pack(fill="x", pady=(0,15))
                    
                    # 첫 번째 항목으로 컬럼 수 파악
                    if items:
                        col_count = len(items[0])
                        col_names = [f"컬럼{i+1}" for i in range(col_count)]
                        
                        # 행 수에 따라 높이 조정 (최소 8, 최대 15)
                        tree_height = min(max(len(items), 8), 15)
                        
                        tree = ttk.Treeview(tree_frame, columns=col_names, show="headings", height=tree_height)
                        for i, col in enumerate(col_names):
                            tree.heading(col, text=col)
                            tree.column(col, width=100)
                        
                        for item in items:
                            tree.insert("", "end", values=item)
                        
                        scrollbar = ttk.Scrollbar(tree_frame, orient="vertical", command=tree.yview)
                        tree.configure(yscrollcommand=scrollbar.set)
                        
                        tree.pack(side="left", fill="x", expand=True)
                        scrollbar.pack(side="right", fill="y")
                
                # 요약 정보
                summary = quo_snapshot.get("summary", {})
                if summary:
                    ctk.CTkLabel(quotation_frame, text="요약", font=ctk.CTkFont(weight="bold", size=14)).pack(anchor="w", pady=(10,10))
                    summary_text = f"""총 함량: {summary.get('총 함량', '')}
총 원료 원가: {summary.get('총 원료 원가', '')}
VAT(10%) 포함가: {summary.get('VAT(10%) 포함가', '')}
이윤(15%) 포함가: {summary.get('이윤(15%) 포함가', '')}"""
                    summary_box = ctk.CTkTextbox(quotation_frame, height=100)
                    summary_box.pack(fill="x")
                    summary_box.insert("1.0", summary_text)
                    summary_box.configure(state="disabled")
            else:
                ctk.CTkLabel(quotation_frame, text="견적 정보가 없습니다.").pack(pady=20)

            # === 탭 4: 생산처방 ===
            production_frame = ctk.CTkScrollableFrame(tab_production)
            production_frame.pack(fill="both", expand=True, padx=10, pady=10)
            
            prod_snapshot = full_snapshot.get("production_formulation")
            if prod_snapshot:
                # 기본 정보
                prod_text = f"""제품명: {prod_snapshot.get('제품명', '')}
생산코드: {prod_snapshot.get('생산코드', '')}
LAB NO: {prod_snapshot.get('LAB NO', '')}
차수: {prod_snapshot.get('차수', '')}
기준중량: {prod_snapshot.get('기준중량', '')} g
상태: {prod_snapshot.get('상태', '')}
시행일: {prod_snapshot.get('시행일', '')}
비고: {prod_snapshot.get('비고', '')}"""
                
                ctk.CTkLabel(production_frame, text="기본 정보", font=ctk.CTkFont(weight="bold", size=14)).pack(anchor="w", pady=(0,10))
                prod_box = ctk.CTkTextbox(production_frame, height=150)
                prod_box.pack(fill="x", pady=(0,15))
                prod_box.insert("1.0", prod_text)
                prod_box.configure(state="disabled")
                
                # 원료 목록
                prod_materials = prod_snapshot.get("원료목록", [])
                if prod_materials:
                    ctk.CTkLabel(production_frame, text="원료 목록", font=ctk.CTkFont(weight="bold", size=14)).pack(anchor="w", pady=(10,10))
                    
                    tree_frame = ctk.CTkFrame(production_frame)
                    tree_frame.pack(fill="x")
                    
                    # 행 수에 따라 높이 조정 (최소 8, 최대 15)
                    tree_height = min(max(len(prod_materials), 8), 15)
                    
                    prod_tree = ttk.Treeview(tree_frame, columns=("순번","구분","원료코드","원료명","함량","실제중량"), show="headings", height=tree_height)
                    prod_tree.heading("순번", text="순번")
                    prod_tree.heading("구분", text="구분")
                    prod_tree.heading("원료코드", text="원료코드")
                    prod_tree.heading("원료명", text="원료명")
                    prod_tree.heading("함량", text="함량(%)")
                    prod_tree.heading("실제중량", text="실제중량(g)")
                    
                    prod_tree.column("순번", width=50)
                    prod_tree.column("구분", width=80)
                    prod_tree.column("원료코드", width=120)
                    prod_tree.column("원료명", width=250)
                    prod_tree.column("함량", width=100)
                    prod_tree.column("실제중량", width=120)
                    
                    for mat in prod_materials:
                        prod_tree.insert("", "end", values=(
                            mat.get("순번", ""),
                            mat.get("구분", ""),
                            mat.get("원료코드", ""),
                            mat.get("원료명", ""),
                            mat.get("함량", ""),
                            mat.get("실제중량", "")
                        ))
                    
                    scrollbar = ttk.Scrollbar(tree_frame, orient="vertical", command=prod_tree.yview)
                    prod_tree.configure(yscrollcommand=scrollbar.set)
                    
                    prod_tree.pack(side="left", fill="x", expand=True)
                    scrollbar.pack(side="right", fill="y")
            else:
                ctk.CTkLabel(production_frame, text="생산처방 정보가 없습니다.").pack(pady=20)

            # === 탭 5: 문서 링크 ===
            doc_frame = ctk.CTkFrame(tab_documents)
            doc_frame.pack(fill="both", expand=True, padx=10, pady=10)
            
            link_tree = ttk.Treeview(doc_frame, columns=("type","ref"), show="headings", selectmode="browse")
            link_tree.heading("type", text="유형")
            link_tree.heading("ref", text="참조ID/제목")
            link_tree.column("type", width=200)
            link_tree.column("ref", width=600, stretch=True)
            link_tree.pack(side="left", fill="both", expand=True)
            
            link_scroll = ttk.Scrollbar(doc_frame, orient="vertical", command=link_tree.yview)
            link_scroll.pack(side="right", fill="y")
            link_tree.configure(yscrollcommand=link_scroll.set)
            
            # 문서 링크 및 품질 서류(제품표준서) 데이터 로딩
            try:
                prod_std = full_snapshot.get("product_standard")
                if prod_std:
                    p_name = prod_std.get("품명", "")
                    p_lab = prod_std.get("LAB NO", "")
                    link_tree.insert("", "end", values=("ProductStandard (제품표준서)", f"{p_name} [{p_lab}] - 성상 및 규격 스냅샷 완비"))

                for l in (pkg.links or []):
                    ref_label = str(l.ref_id)
                    if l.doc_type == 'IngredientReport':
                        try:
                            r = session.query(IngredientReport).filter_by(id=l.ref_id).first()
                            if r:
                                ref_label = f"{l.ref_id} - 전성분({r.product_name or ''})"
                        except Exception:
                            pass
                    elif l.doc_type == 'SemiFinishedCOA':
                        try:
                            r = session.query(SemiFinishedCOA).filter_by(id=l.ref_id).first()
                            if r:
                                ref_label = f"{l.ref_id} - 반제품 COA({r.product_name or ''})"
                        except Exception:
                            pass
                    elif l.doc_type == 'FinishedProductCOA':
                        try:
                            r = session.query(FinishedProductCOA).filter_by(id=l.ref_id).first()
                            if r:
                                ref_label = f"{l.ref_id} - 완제품 COA({r.product_name or ''})"
                        except Exception:
                            pass
                    link_tree.insert("", "end", values=(l.doc_type, ref_label))
            except Exception:
                pass

            # === 탭 6: 첨부파일 ===
            attach_frame = ctk.CTkFrame(tab_attachments)
            attach_frame.pack(fill="both", expand=True, padx=10, pady=10)
            
            attach_tree = ttk.Treeview(attach_frame, columns=("name","type","path"), show="headings", selectmode="browse")
            attach_tree.heading("name", text="파일명")
            attach_tree.heading("type", text="유형")
            attach_tree.heading("path", text="경로")
            attach_tree.column("name", width=300)
            attach_tree.column("type", width=150)
            attach_tree.column("path", width=450, stretch=True)
            attach_tree.pack(side="left", fill="both", expand=True)
            
            attach_scroll = ttk.Scrollbar(attach_frame, orient="vertical", command=attach_tree.yview)
            attach_scroll.pack(side="right", fill="y")
            attach_tree.configure(yscrollcommand=attach_scroll.set)
            
            # 첨부파일 데이터 로딩
            try:
                for a in (pkg.attachments or []):
                    attach_tree.insert("", "end", values=(a.file_name or '', a.attachment_type or '', a.file_path or ''))
            except Exception:
                pass

            # 창 중앙 배치
            win.update_idletasks()
            parent = self
            parent_x = parent.winfo_rootx()
            parent_y = parent.winfo_rooty()
            parent_w = parent.winfo_width()
            parent_h = parent.winfo_height()
            win_w = win.winfo_width()
            win_h = win.winfo_height()
            x = parent_x + (parent_w - win_w) // 2
            y = parent_y + (parent_h - win_h) // 2
            win.geometry(f"+{x}+{y}")

            self.wait_window(win)
        finally:
            session.close()

    def add_package_link(self):
        pkg_id = self._get_selected_package_id()
        if not pkg_id:
            messagebox.showwarning("선택 필요", "링크를 추가할 패키지를 선택하세요.", parent=self)
            return

        # 간단 선택 다이얼로그: 문서 유형 선택 후 해당 목록에서 선택
        dialog = ctk.CTkToplevel(self)
        dialog.title("문서 링크 추가")
        dialog.transient(self)
        dialog.grab_set()

        frame = ctk.CTkFrame(dialog)
        frame.pack(padx=20, pady=20, fill="both", expand=True)

        ctk.CTkLabel(frame, text="문서 유형").pack(anchor="w")
        type_var = tk.StringVar(value='IngredientReport')
        type_dropdown = ctk.CTkOptionMenu(frame, values=['IngredientReport', 'SemiFinishedCOA', 'FinishedProductCOA'], variable=type_var)
        type_dropdown.pack(fill="x", pady=(0,10))

        list_frame = ctk.CTkFrame(frame)
        list_frame.pack(fill="both", expand=True)
        list_frame.grid_columnconfigure(0, weight=1)
        list_frame.grid_rowconfigure(0, weight=1)

        list_tree = ttk.Treeview(list_frame, columns=("id","name"), show="headings", selectmode="browse")
        list_tree.heading("id", text="ID"); list_tree.column("id", width=80)
        list_tree.heading("name", text="제목/제품명"); list_tree.column("name", width=360, stretch=True)
        list_tree.grid(row=0, column=0, sticky="nsew")
        list_scroll = ttk.Scrollbar(list_frame, orient="vertical", command=list_tree.yview)
        list_scroll.grid(row=0, column=1, sticky="ns")
        list_tree.configure(yscrollcommand=list_scroll.set)

        # 로더
        def load_docs():
            for i in list_tree.get_children():
                list_tree.delete(i)
            session = db_manager.get_session()
            try:
                pkg = session.query(DocumentPackage).filter_by(id=pkg_id).first()
                if not pkg:
                    return
                keyword = (pkg.product_name or '').strip()
                docs = []
                if type_var.get() == 'IngredientReport':
                    q = session.query(IngredientReport)
                    if keyword:
                        q = q.filter(IngredientReport.product_name.like(f"%{keyword}%"))
                    docs = q.order_by(IngredientReport.id.desc()).limit(200).all()
                    for d in docs:
                        list_tree.insert("", "end", iid=d.id, values=(d.id, d.product_name or ''))
                elif type_var.get() == 'SemiFinishedCOA':
                    q = session.query(SemiFinishedCOA)
                    if keyword:
                        q = q.filter(SemiFinishedCOA.product_name.like(f"%{keyword}%"))
                    docs = q.order_by(SemiFinishedCOA.id.desc()).limit(200).all()
                    for d in docs:
                        list_tree.insert("", "end", iid=d.id, values=(d.id, d.product_name or ''))
                elif type_var.get() == 'FinishedProductCOA':
                    q = session.query(FinishedProductCOA)
                    if keyword:
                        q = q.filter(FinishedProductCOA.product_name.like(f"%{keyword}%"))
                    docs = q.order_by(FinishedProductCOA.id.desc()).limit(200).all()
                    for d in docs:
                        list_tree.insert("", "end", iid=d.id, values=(d.id, d.product_name or ''))
            finally:
                session.close()

        load_docs()
        type_dropdown.configure(command=lambda _: load_docs())

        def do_add():
            sel = list_tree.selection()
            if not sel:
                messagebox.showwarning("선택 필요", "연결할 문서를 선택하세요.", parent=dialog)
                return
            ref_id = int(sel[0])
            session2 = db_manager.get_session()
            try:
                link = DocumentPackageLink(package_id=pkg_id, doc_type=type_var.get(), ref_id=ref_id)
                session2.add(link)
                session2.commit()
                messagebox.showinfo("완료", "문서 링크가 추가되었습니다.", parent=dialog)
                dialog.destroy()
                # 상세창이 떠있다면 수동 새로고침 필요 (간단화를 위해 생략)
            except Exception as ex:
                session2.rollback()
                messagebox.showerror("오류", f"링크 추가 실패: {ex}", parent=dialog)
            finally:
                session2.close()

        btns = ctk.CTkFrame(frame, fg_color="transparent")
        btns.pack(fill="x", pady=(10,0))
        ctk.CTkButton(btns, text="추가", command=do_add).pack(side="left")
        ctk.CTkButton(btns, text="취소", fg_color="gray", command=dialog.destroy).pack(side="right")

        try:
            center_window_on_mouse_display(dialog)
        except Exception:
            pass

        self.wait_window(dialog)

    def add_package_attachment(self):
        pkg_id = self._get_selected_package_id()
        if not pkg_id:
            messagebox.showwarning("선택 필요", "첨부를 추가할 패키지를 선택하세요.", parent=self)
            return
        filepaths = filedialog.askopenfilenames(parent=self, title="첨부 파일 선택")
        if not filepaths:
            return
        session = db_manager.get_session()
        try:
            count = 0
            for fp in filepaths:
                try:
                    fname = os.path.basename(fp)
                    att = DocumentAttachment(package_id=pkg_id, file_name=fname, file_path=fp, attachment_type=None)
                    session.add(att)
                    count += 1
                except Exception:
                    continue
            session.commit()
            messagebox.showinfo("완료", f"{count}개 첨부가 추가되었습니다.", parent=self)
        except Exception as ex:
            session.rollback()
            messagebox.showerror("오류", f"첨부 추가 실패: {ex}", parent=self)
        finally:
            session.close()

    def export_selected_package(self):
        pkg_id = self._get_selected_package_id()
        if not pkg_id:
            messagebox.showwarning("선택 필요", "내보낼 패키지를 선택하세요.", parent=self)
            return
        out_dir = filedialog.askdirectory(parent=self, title="내보낼 폴더 선택")
        if not out_dir:
            return
        session = db_manager.get_session()
        try:
            pkg = session.query(DocumentPackage).filter_by(id=pkg_id).first()
            if not pkg:
                messagebox.showerror("오류", "패키지를 찾을 수 없습니다.", parent=self)
                return

            # package.json 생성
            export_obj = {
                "package": {
                    "id": pkg.id,
                    "name": pkg.name,
                    "product_name": pkg.product_name,
                    "revision": pkg.revision,
                    "created_at": pkg.created_at.strftime('%Y-%m-%d %H:%M') if pkg.created_at else None,
                    "notes": pkg.notes,
                },
                "ingredient_snapshot": json.loads(pkg.ingredient_snapshot) if pkg.ingredient_snapshot else None,
                "quotation_snapshot": json.loads(pkg.quotation_snapshot) if pkg.quotation_snapshot else None,
                "links": [{"doc_type": l.doc_type, "ref_id": l.ref_id} for l in (pkg.links or [])],
                "attachments": [{"file_name": a.file_name, "file_path": a.file_path, "attachment_type": a.attachment_type} for a in (pkg.attachments or [])]
            }

            # 생산처방 연결 시 공정 단계도 포함
            try:
                if pkg.production_formulation_id:
                    prod = session.query(ProductionFormulation).filter_by(id=pkg.production_formulation_id).first()
                    if prod:
                        steps = (
                            session.query(ProductionStep)
                            .filter_by(production_formulation_id=prod.id)
                            .order_by(ProductionStep.step_no.asc(), ProductionStep.id.asc())
                            .all()
                        )
                        export_obj["production_formulation"] = {
                            "id": prod.id,
                            "product_name": prod.product_name,
                            "production_code": prod.production_code,
                            "revision": prod.revision,
                            "lab_no": prod.lab_no,
                            "base_weight_g": prod.base_weight_g,
                            "status": prod.status,
                            "effective_date": prod.effective_date.strftime('%Y-%m-%d') if prod.effective_date else None,
                            "notes": prod.notes,
                        }
                        export_obj["production_steps"] = [
                            {
                                "step_no": st.step_no,
                                "phase": st.phase,
                                "instruction": st.instruction,
                                "temperature": st.temperature,
                                "time_min": st.time_min,
                                "rpm": st.rpm,
                                "equipment": st.equipment,
                                "notes": st.notes,
                            } for st in steps
                        ]
            except Exception:
                pass

            out_json = os.path.join(out_dir, f"package_{pkg.id}.json")
            with open(out_json, 'w', encoding='utf-8') as f:
                json.dump(export_obj, f, ensure_ascii=False, indent=2)

            # 첨부 복사
            if pkg.attachments:
                attach_dir = os.path.join(out_dir, "attachments")
                os.makedirs(attach_dir, exist_ok=True)
                for a in pkg.attachments:
                    try:
                        if a.file_path and os.path.exists(a.file_path):
                            shutil.copy2(a.file_path, os.path.join(attach_dir, a.file_name or os.path.basename(a.file_path)))
                    except Exception:
                        pass

            messagebox.showinfo("완료", "패키지 내보내기가 완료되었습니다.", parent=self)
        except Exception as ex:
            messagebox.showerror("오류", f"내보내기 실패: {ex}", parent=self)
        finally:
            session.close()

    def delete_selected_package(self):
        """관리자 전용: 선택된 패키지 삭제 (첨부 파일과 링크도 함께 삭제)."""
        pkg_id = self._get_selected_package_id()
        if not pkg_id:
            messagebox.showwarning('선택 필요', '삭제할 패키지를 선택하세요.', parent=self)
            return
        
        # 권한 확인
        try:
            if hasattr(self.current_user, 'can_delete'):
                allowed = self.current_user.can_delete()
            else:
                allowed = bool(getattr(self.current_user, 'is_admin', False))
        except Exception:
            allowed = bool(getattr(self.current_user, 'is_admin', False))
        
        if not allowed:
            messagebox.showwarning('권한 없음', '패키지 삭제 권한이 없습니다.', parent=self)
            return
        
        session = db_manager.get_session()
        try:
            from database.models import DocumentPackage, DocumentPackageLink, DocumentAttachment
            
            # 패키지 정보 조회
            pkg = session.query(DocumentPackage).filter_by(id=pkg_id).first()
            if not pkg:
                messagebox.showerror('오류', '패키지를 찾을 수 없습니다.', parent=self)
                return
            
            # 삭제 확인
            pkg_name = pkg.name or f"패키지 #{pkg.id}"
            if not messagebox.askyesno('삭제 확인', 
                                      f'"{pkg_name}"을(를) 삭제할까요?\n\n연결된 문서 링크와 첨부 파일도 함께 삭제됩니다.\n이 작업은 되돌릴 수 없습니다.', 
                                      parent=self):
                return
            
            # 첨부 파일 삭제 (선택적)
            if pkg.attachments:
                delete_files = messagebox.askyesno('첨부 파일 삭제', 
                                                   f'{len(pkg.attachments)}개의 첨부 파일이 있습니다.\n실제 파일도 함께 삭제할까요?', 
                                                   parent=self)
                if delete_files:
                    for attachment in pkg.attachments:
                        try:
                            if attachment.file_path and os.path.exists(attachment.file_path):
                                os.remove(attachment.file_path)
                                print(f"[패키지 삭제] 첨부 파일 삭제: {attachment.file_path}")
                        except Exception as e:
                            print(f"[경고] 첨부 파일 삭제 실패: {attachment.file_path} - {e}")
            
            # 문서 링크 삭제 (CASCADE로 자동 삭제되지만 명시적으로 처리)
            session.query(DocumentPackageLink).filter_by(package_id=pkg_id).delete()
            
            # 첨부 파일 레코드 삭제 (CASCADE로 자동 삭제되지만 명시적으로 처리)
            session.query(DocumentAttachment).filter_by(package_id=pkg_id).delete()
            
            # 패키지 삭제
            session.delete(pkg)
            session.commit()
            
            messagebox.showinfo('완료', f'패키지 "{pkg_name}"이(가) 삭제되었습니다.', parent=self)
            
            # 목록 갱신
            self.refresh_package_list()
            
        except Exception as ex:
            session.rollback()
            messagebox.showerror('오류', f'패키지 삭제 실패:\n{ex}', parent=self)
            import traceback
            traceback.print_exc()
        finally:
            session.close()

    def create_document_package(self):
        if not self._selected_formulation_id:
            messagebox.showwarning(self.texts['selection_error'], self.texts.get('select_formulation_first','처방을 먼저 선택하세요.'), parent=self)
            return

        # 전성분/견적 스냅샷 준비: UI에서 생성 후 추출
        try:
            self.generate_all_ingredient_lists(force=True)
        except Exception:
            pass
        try:
            # 견적이 비어 있으면 자동 로드 후 계산
            if not self.quotation_tree.get_children():
                self.load_formulation_for_quotation()
            else:
                self.recalculate_quotation()
        except Exception:
            pass

        # 패키지 스냅샷 전체 구조
        package_snapshot = {
            "formulation_info": {},          # 실험처방 기본 정보
            "formulation_materials": [],     # 실험처방 원료 목록
            "ingredients": {},               # 전성분 목록 (복합/단일/합산)
            "quotation": {},                 # 견적 정보
            "production_formulation": None,  # 생산처방 정보 (있는 경우)
        }

        # 1) 실험처방 정보 및 원료 목록 저장
        session = db_manager.get_session()
        try:
            formulation = session.query(Formulation).filter_by(id=self._selected_formulation_id).first()
            if not formulation:
                messagebox.showerror(self.texts['error'], self.texts.get('select_formulation_first','처방을 먼저 선택하세요.'), parent=self)
                return
            
            # 실험처방 기본 정보
            manager_display = self.get_manager_display_name(formulation.manager_name or "", session)
            package_snapshot["formulation_info"] = {
                "id": formulation.id,
                "실험품명": formulation.experiment_name,
                "LAB NO": formulation.lab_no,
                "차수": formulation.revision or "",
                "실험일": formulation.experiment_date or "",
                "담당자": manager_display,
                "샘플발송횟수": formulation.sample_sent_count or 0,
                "샘플발송일": formulation.sample_delivery_date.isoformat() if formulation.sample_delivery_date else "",
                "비고": formulation.experiment_comment or "",
            }
            
            # 실험처방 원료 목록
            for fm in formulation.items:
                material_info = {
                    "순번": fm.order,
                    "원료코드": fm.material_code,
                    "원료명": fm.material_name or (fm.material.name if fm.material else ""),
                    "함량": float(fm.ratio) if fm.ratio else 0,
                }
                if fm.material:
                    material_info.update({
                        "제조사": fm.material.manufacturer or "",
                        "공급사": fm.material.supplier or "",
                        "원산지": fm.material.origin or "",
                    })
                package_snapshot["formulation_materials"].append(material_info)
        except Exception as e:
            session.close()
            messagebox.showerror(self.texts['error'], f"처방 정보 로드 중 오류: {e}", parent=self)
            return

        # 2) 전성분 스냅샷 재사용: export_all_ingredient_lists의 로직과 동일하게 추출
        ingredient_snapshot = {}

        def extract_tree_for_snapshot(treeview, sheet_name):
            if not treeview.get_children():
                return
            all_cols = treeview["columns"]
            visible_cols = list(treeview["displaycolumns"]) if treeview["displaycolumns"] not in (None, ['#all']) else list(all_cols)
            headers = [treeview.heading(col)["text"] for col in visible_cols if col in all_cols]
            col_index = {col: i for i, col in enumerate(all_cols)}
            indices = [col_index[c] for c in visible_cols if c in col_index]
            data = []
            for item_id in treeview.get_children():
                vals = treeview.item(item_id, "values")
                if isinstance(vals, str):
                    continue
                row = [vals[i] if i < len(vals) else "" for i in indices]
                data.append(row)
            if data:
                ingredient_snapshot[sheet_name] = {"headers": headers, "rows": data}

        # 복합/단일 전성분 트리뷰들 추출 (이미 생성되어 있다고 가정)
        try:
            extract_tree_for_snapshot(self.raw_material_ingredient_tree, "복합 전성분(원료별)")
        except Exception:
            pass
        try:
            extract_tree_for_snapshot(self.summed_ingredient_tree, "성분 합산")
        except Exception:
            pass
        try:
            extract_tree_for_snapshot(self.single_ingredient_tree, "단일 전성분")
        except Exception:
            pass
        # 디자인 전성분 텍스트도 포함
        try:
            ingredient_snapshot["디자인 전성분"] = {
                "ko": self.design_ko_textbox.get("1.0", "end").strip(),
                "en": self.design_en_textbox.get("1.0", "end").strip(),
            }
        except Exception:
            pass
        
        package_snapshot["ingredients"] = ingredient_snapshot

        # 3) 견적 스냅샷
        quotation_snapshot = {
            "details": {},
            "items": [],
            "summary": {}
        }
        try:
            quotation_snapshot["details"] = {
                "실험품명": formulation.experiment_name,
                "담당자": manager_display,
                "LAB NO.": formulation.lab_no,
                "기준 중량": self.quotation_weight_entry.get() + "g",
            }
        except Exception:
            pass
        try:
            # Get profit margin
            try:
                profit_margin = float(self.quotation_profit_margin_entry.get().strip())
            except (ValueError, TypeError):
                profit_margin = 15.0
            
            quotation_snapshot["items"] = [self.quotation_tree.item(item, "values") for item in self.quotation_tree.get_children()]
            quotation_snapshot["summary"] = {
                "총 함량": self.quotation_total_ratio_label.cget("text"),
                "총 원료 원가": self.total_raw_cost_label.cget("text"),
                "VAT(10%) 포함가": self.price_with_vat_label.cget("text"),
                f"이윤({profit_margin:.0f}%) 포함가": self.price_with_profit_label.cget("text"),
            }
        except Exception:
            pass
        
        package_snapshot["quotation"] = quotation_snapshot

        # 4) 생산처방 정보 (있는 경우)
        try:
            production_id = getattr(self, '_selected_production_id', None)
            prod = None
            if production_id:
                prod = session.query(ProductionFormulation).filter_by(id=production_id).first()
            
            if prod:
                package_snapshot["production_formulation"] = {
                    "id": prod.id,
                    "제품명": prod.product_name,
                    "생산코드": prod.production_code or "",
                    "LAB NO": prod.lab_no or "",
                    "차수": prod.revision or "",
                    "기준중량": float(prod.base_weight_g) if prod.base_weight_g else 0,
                    "상태": prod.status or "",
                    "시행일": prod.effective_date.isoformat() if prod.effective_date else "",
                    "비고": prod.notes or "",
                    "원료목록": []
                }
                
                # 생산처방 원료 목록 (items_snapshot JSON 파싱)
                try:
                    if prod.items_snapshot:
                        items = json.loads(prod.items_snapshot)
                        for item in items:
                            material_info = {
                                "순번": item.get("order", ""),
                                "구분": item.get("phase", ""),
                                "원료코드": item.get("code", ""),
                                "원료명": item.get("name", ""),
                                "함량": float(item.get("ratio", 0)) if item.get("ratio") else 0,
                                "실제중량": float(item.get("amount", 0)) if item.get("amount") else 0,
                            }
                            package_snapshot["production_formulation"]["원료목록"].append(material_info)
                except Exception as e:
                    print(f"생산처방 원료 목록 파싱 실패: {e}")
        except Exception as e:
            print(f"생산처방 정보 로드 실패: {e}")
            package_snapshot["production_formulation"] = None

        # 5) 제품표준서 및 품질관리 서류 스냅샷 추가
        try:
            package_snapshot["product_standard"] = {
                "문서명": "제품표준서 (Product Standard)",
                "품명": (prod.product_name if prod else formulation.experiment_name),
                "LAB NO": (prod.lab_no if prod else formulation.lab_no) or "",
                "차수": (prod.revision if prod else formulation.revision) or "",
                "실험일": formulation.experiment_date or "",
                "성상_물성치": {
                    "초기 pH": formulation.experiment_ph_initial or "",
                    "익일 pH": formulation.experiment_ph_next_day or "",
                    "초기 점도": formulation.experiment_viscosity_initial or "",
                    "익일 점도": formulation.experiment_viscosity_next_day or "",
                    "제조기기": formulation.experiment_machine or "",
                },
                "특이사항_비고": formulation.experiment_comment or "",
                "생산처방연동": bool(prod)
            }
            package_snapshot["quality_documents"] = {
                "제품표준서": package_snapshot["product_standard"],
                "시험성적서_COA": {"연동처방ID": formulation.id},
                "MSDS": {"연동처방ID": formulation.id},
                "원료목록보고": {"연동처방ID": formulation.id}
            }
        except Exception as q_err:
            print(f"[Package] 제품표준서 스냅샷 생성 실패: {q_err}")

        # 6) 패키지 DB 저장
        try:
            pkg = DocumentPackage(
                name=f"{(prod.product_name if prod else formulation.experiment_name)} 패키지 {datetime.now().strftime('%Y%m%d_%H%M')}",
                formulation_id=(None if prod else formulation.id),
                production_formulation_id=(prod.id if prod else None),
                product_name=(prod.product_name if prod else formulation.experiment_name),
                revision=(prod.revision if prod else formulation.revision),
                created_by_user_id=getattr(self.current_user, 'id', None),
                ingredient_snapshot=json.dumps(package_snapshot["ingredients"], ensure_ascii=False),
                quotation_snapshot=json.dumps(package_snapshot, ensure_ascii=False),  # 전체 스냅샷을 quotation_snapshot에 저장
            )
            session.add(pkg)
            session.commit()
            messagebox.showinfo(self.texts['success'], "패키지가 저장되었습니다.", parent=self)
            self.refresh_package_list()
        except Exception as e:
            session.rollback()
            messagebox.showerror(self.texts['error'], f"패키지 저장 중 오류: {e}", parent=self)
        finally:
            session.close()

    def export_quotation(self):
        """현재 견적 내용을 엑셀 파일로 내보냅니다."""
        if not self._selected_formulation_id:
            messagebox.showwarning(self.texts['selection_error'], self.texts['select_formulation_and_create_quotation'], parent=self)
            return

        session = db_manager.get_session()
        try:
            formulation = session.query(Formulation).filter_by(id=self._selected_formulation_id).first()
            if not formulation: return

            try:
                profit_margin = float(self.quotation_profit_margin_entry.get().strip())
            except (ValueError, TypeError):
                profit_margin = 15.0

            quotation_data = {
                "details": {
                    "실험품명": formulation.experiment_name,
                    "담당자": self.get_manager_display_name(formulation.manager_name or "", session),
                    "LAB NO.": formulation.lab_no,
                    "기준 중량": self.quotation_weight_entry.get() + "g",
                    "개당 용량": (self.quotation_unit_capacity_entry.get() if hasattr(self, 'quotation_unit_capacity_entry') else "50") + "g",
                    "산출 수량": (self.quotation_unit_count_entry.get() + " EA") if hasattr(self, 'quotation_unit_count_entry') else "1 EA",
                },
                "extra_expenses": {
                    "인력비": (self.quotation_labor_entry.get() if hasattr(self, 'quotation_labor_entry') else "0") + " 원",
                    "제조비": (self.quotation_mfg_cost_entry.get() if hasattr(self, 'quotation_mfg_cost_entry') else "0") + " 원",
                    "운송비": (self.quotation_shipping_entry.get() if hasattr(self, 'quotation_shipping_entry') else "0") + " 원",
                    "용기": (self.quotation_container_entry.get() if hasattr(self, 'quotation_container_entry') else "0") + " 원",
                    "1kg당 총단가": self.quotation_cost_per_kg_label.cget("text") if hasattr(self, 'quotation_cost_per_kg_label') else "-",
                    "개당(EA) 총단가": self.quotation_cost_per_unit_label.cget("text") if hasattr(self, 'quotation_cost_per_unit_label') else "-",
                },
                "items": [self.quotation_tree.item(item, "values") for item in self.quotation_tree.get_children()],
                "summary": {
                    "총 함량": self.quotation_total_ratio_label.cget("text") if hasattr(self, 'quotation_total_ratio_label') else "100%",
                    "총 원료 원가": self.total_raw_cost_label.cget("text"),
                    "총 제조 원가": self.total_combined_cost_label.cget("text") if hasattr(self, 'total_combined_cost_label') else self.total_raw_cost_label.cget("text"),
                    f"이윤({profit_margin:.0f}%) 포함 공급가": self.price_with_profit_label.cget("text"),
                    "최종가 (VAT 10% 포함)": self.price_with_vat_label.cget("text"),
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
        
        # [수정] 뒤로가기 시 상위 폴더(업체 폴더) 상태 유지
        if client_id_to_load is not None:
            # 특정 업체로 이동 요청 시
            self.current_view_level = "item"
            self.current_client_id = client_id_to_load
            self.load_folders(is_initial_load=False)
        elif self.current_view_level == "item":
            # 이전에 아이템 목록(업체 내부 또는 미지정 폴더)을 보고 있었다면 그 상태 복원
            self.load_folders(is_initial_load=False)
        else:
            # 그 외(업체 목록 등)의 경우 초기화하며 로드
            self.load_folders(is_initial_load=True)



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

    def export_selected_formulation_to_excel(self):
        """선택된 처방을 엑셀(.xlsx)로 내보냅니다 (무조건 Excel)."""
        if not hasattr(self, '_selected_formulation_id') or not self._selected_formulation_id:
            messagebox.showwarning(self.texts.get('export_error', '내보내기 오류'), self.texts.get('select_formulation_first', '처방을 먼저 선택하세요.'), parent=self)
            return

        session = db_manager.get_session()
        try:
            f = session.query(Formulation).filter_by(id=self._selected_formulation_id).first()
            if not f:
                messagebox.showerror(self.texts.get('export_error', '내보내기 오류'), '선택된 처방을 찾을 수 없습니다.', parent=self)
                return

            # 상세 정보 구성
            manager_display = self.get_manager_display_name(f.manager_name or "", session)
            total_amount = 0.0
            items_rows = []
            # 아이템 정렬 및 집계
            for it in sorted(f.items or [], key=lambda x: (x.order or 0, x.id or 0)):
                # 합계 계산용
                try:
                    if it.amount is not None:
                        total_amount += float(it.amount)
                except Exception:
                    pass
                items_rows.append({
                    "구분": it.phase or "",
                    "코드": it.material_code or ("---" if getattr(it, 'material_id', None) is None else ""),
                    "원료명": it.material_name or "",
                    "함량(%)": it.ratio if it.ratio is not None else "",
                    "실험량(g)": it.amount if it.amount is not None else "",
                })

            details = {
                "실험품명": f.experiment_name or "",
                "실험년월일": f.experiment_date or "",
                "담당자": manager_display,
                "거래처": f.target_client_id or "",
                "LAB NO.": f.lab_no or "",
                "차수": f.revision or "",
                "담당번호": f.manager_code or "",
                "총 실험량": total_amount if total_amount else "",
                "pH (당일)": f.experiment_ph_initial or "",
                "pH (익일)": f.experiment_ph_next_day or "",
                "점도 (당일)": f.experiment_viscosity_initial or "",
                "점도 (익일)": f.experiment_viscosity_next_day or "",
                "사용핀 및 기계": f.experiment_machine or "",
                "품평결과 및 특이사항": f.experiment_comment or "",
            }

            formulation_data = {
                "details": details,
                "items": items_rows,
            }

            default_filename = f"{(f.experiment_name or '처방')}_처방.xlsx"
            excel_handler.export_formulation_template(formulation_data, default_filename)
        except Exception as e:
            messagebox.showerror(self.texts.get('export_error', '내보내기 오류'), f"처방 내보내기 중 오류: {e}", parent=self)
        finally:
            session.close()

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
            # 연구원 이상(RD, RQ, RQD, MSAD)이 삭제 버튼을 활성화할 수 있습니다.
            if self.current_user.can_delete_formulation():
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

    def create_folder_card(self, master, folder_name, count):
        """슬라이더 값에 따라 크기가 조절되는 폴더 카드 위젯을 생성합니다."""
        # 슬라이더 값에 따라 폰트 크기와 카드 크기 동적 계산
        icon_size = int(self.icon_size_slider.get())
        title_size = int(icon_size / 2.8)  # 아이콘 크기에 비례하여 조절
        count_size = int(icon_size / 3.6)  # 아이콘 크기에 비례하여 조절
        wraplength = int(icon_size * 3.75)
        
        # [수정] 카드 자체 크기도 슬라이더에 따라 조절
        card_width = int(icon_size * 4)   # 아이콘 크기의 4배
        card_height = int(icon_size * 3)  # 아이콘 크기의 3배
        padding_y = max(5, int(icon_size / 6))  # 패딩도 비례 조절
        
        card = ctk.CTkFrame(master, corner_radius=10, cursor="hand2", 
                           width=card_width, height=card_height)
        card.grid_columnconfigure(0, weight=1)
        card.pack_propagate(False)  # 카드 크기 고정 (내부 위젯에 의해 늘어나지 않음)

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

        # --- 서브 탭 뷰 생성 (상단 밀착) ---
        sub_tab_view = ctk.CTkTabview(
            tab_frame, border_width=0, border_color=("gray80", "gray30"),
            command=self.on_complex_ingredient_sub_tab_change # 복합 전성분 내 서브탭 변경 감지
        )
        self.complex_ingredient_sub_tab_view = sub_tab_view # 서브 탭뷰를 인스턴스 변수로 저장
        self.complex_ingredient_sub_tab_view.grid(row=0, column=0, padx=0, pady=0, sticky="nsew")

        raw_material_tab = sub_tab_view.add(self.texts['by_raw_material'])
        summed_list_tab = sub_tab_view.add(self.texts['summed_ingredients'])

        # --- 원료별 목록 탭 UI ---
        raw_material_tab.grid_columnconfigure(0, weight=1)
        raw_material_tab.grid_columnconfigure(1, weight=0)
        raw_material_tab.grid_rowconfigure(0, weight=1)  # Treeview가 차지할 공간
        raw_material_tab.grid_rowconfigure(1, weight=0)  # 가로 스크롤바
        raw_material_tab.grid_rowconfigure(2, weight=0)  # 합계 프레임
        
        # 열 정의는 여기에 유지합니다.
        self.complex_ing_cols = self.texts['complex_ingredient_tree_columns']
 
        self.raw_material_ingredient_tree = ttk.Treeview(raw_material_tab, columns=list(self.complex_ing_cols.keys()), show="headings")
        self._setup_treeview_columns(self.raw_material_ingredient_tree, self.complex_ing_cols)
        self.raw_material_ingredient_tree.grid(row=0, column=0, sticky="nsew", padx=(6, 0), pady=(0, 2))
        self.raw_material_ingredient_tree.tag_configure('material_row', font=('Malgun Gothic', 11, 'bold'))
 
        # 원료별 목록 스크롤바
        raw_v_scroll = ttk.Scrollbar(raw_material_tab, orient="vertical", command=self.raw_material_ingredient_tree.yview)
        self.raw_material_ingredient_tree.configure(yscrollcommand=raw_v_scroll.set)
        raw_v_scroll.grid(row=0, column=1, sticky='ns', pady=(0, 2))
        raw_h_scroll = ttk.Scrollbar(raw_material_tab, orient="horizontal", command=self.raw_material_ingredient_tree.xview)
        self.raw_material_ingredient_tree.configure(xscrollcommand=raw_h_scroll.set)
        raw_h_scroll.grid(row=1, column=0, sticky='ew', padx=(6, 0))
 
        # 원료별 목록 합계 프레임
        raw_material_summary_frame = ctk.CTkFrame(raw_material_tab, fg_color="transparent")
        raw_material_summary_frame.grid(row=2, column=0, columnspan=2, sticky="e", padx=10, pady=5)
        ctk.CTkLabel(raw_material_summary_frame, text=self.texts['total_rm_ratio_label'], font=ctk.CTkFont(weight="bold")).pack(side="left", padx=(0, 5))
        self.raw_material_rm_ratio_total_label = ctk.CTkLabel(raw_material_summary_frame, text="0.0000", font=ctk.CTkFont(weight="bold"))
        self.raw_material_rm_ratio_total_label.pack(side="left", padx=(0, 20))
        ctk.CTkLabel(raw_material_summary_frame, text=self.texts['total_actual_wt_label'], font=ctk.CTkFont(weight="bold")).pack(side="left", padx=(0, 5))
        self.raw_material_actual_wt_total_label = ctk.CTkLabel(raw_material_summary_frame, text="0.000000", font=ctk.CTkFont(weight="bold"))
        self.raw_material_actual_wt_total_label.pack(side="left")
 
        # --- 전성분 합계 탭 UI ---
        summed_list_tab.grid_columnconfigure(0, weight=1)
        summed_list_tab.grid_columnconfigure(1, weight=0)
        summed_list_tab.grid_rowconfigure(0, weight=1)  # Treeview가 차지할 공간
        summed_list_tab.grid_rowconfigure(1, weight=0)  # 가로 스크롤바
        summed_list_tab.grid_rowconfigure(2, weight=0)  # 합계 프레임
 
        summed_cols = self.texts['summed_ingredient_tree_columns']
        self.summed_ingredient_tree = ttk.Treeview(summed_list_tab, columns=list(summed_cols.keys()), show="headings") # noqa
        self.summed_ingredient_tree.heading("phase", text=summed_cols['phase']); self.summed_ingredient_tree.column("phase", width=80, anchor="center", stretch=True)
        self.summed_ingredient_tree.heading("name_en", text=summed_cols['name_en']); self.summed_ingredient_tree.column("name_en", width=200, stretch=True) # noqa
        self.summed_ingredient_tree.heading("name_ko", text=summed_cols['name_ko']); self.summed_ingredient_tree.column("name_ko", width=200, stretch=True) # noqa
        self.summed_ingredient_tree.heading("total_ratio", text=summed_cols['total_ratio']); self.summed_ingredient_tree.column("total_ratio", width=120, anchor="e", stretch=True) # noqa
        self.summed_ingredient_tree.heading("cas_no", text=summed_cols['cas_no']); self.summed_ingredient_tree.column("cas_no", width=120, stretch=True) # noqa
        self.summed_ingredient_tree.heading("function", text=summed_cols['function']); self.summed_ingredient_tree.column("function", width=150, stretch=True) # noqa
        self.summed_ingredient_tree.grid(row=0, column=0, sticky="nsew", padx=(10,0), pady=(0,5))
 
        # 전성분 합계 스크롤바
        sum_v_scroll = ttk.Scrollbar(summed_list_tab, orient="vertical", command=self.summed_ingredient_tree.yview)
        self.summed_ingredient_tree.configure(yscrollcommand=sum_v_scroll.set)
        sum_v_scroll.grid(row=0, column=1, sticky='ns', pady=(0,5))
        sum_h_scroll = ttk.Scrollbar(summed_list_tab, orient="horizontal", command=self.summed_ingredient_tree.xview)
        self.summed_ingredient_tree.configure(xscrollcommand=sum_h_scroll.set)
        sum_h_scroll.grid(row=1, column=0, sticky='ew', padx=(10,0))
 
        # 전성분 합계 요약 프레임
        summed_summary_frame = ctk.CTkFrame(summed_list_tab, fg_color="transparent")
        summed_summary_frame.grid(row=2, column=0, columnspan=2, sticky="e", padx=10, pady=5)
        ctk.CTkLabel(summed_summary_frame, text=self.texts['total_ratio_sum'], font=ctk.CTkFont(weight="bold")).pack(side="left", padx=(0, 5))
        self.summed_total_ratio_label = ctk.CTkLabel(summed_summary_frame, text="0.000000", font=ctk.CTkFont(weight="bold"))
        self.summed_total_ratio_label.pack(side="left")

    def generate_raw_material_ingredient_list(self):
        """선택된 처방을 기반으로 원료별 전성분 목록을 생성합니다. (동일 원료 합산)"""
        if not self._selected_formulation_id:
            messagebox.showwarning(self.texts['selection_error'], self.texts['select_formulation_first'], parent=self)
            return
        
        # Treeview 초기화
        for item in self.raw_material_ingredient_tree.get_children():
            self.raw_material_ingredient_tree.delete(item)

        session = db_manager.get_session()
        try:
            # 처방에 포함된 원료 아이템들을 가져옵니다.
            formulation_items = session.query(FormulationItem).filter_by(formulation_id=self._selected_formulation_id).order_by(FormulationItem.order).all()

            # 1. 원료별 합산 (Code와 Name이 같은 경우)
            aggregated_items = {}
            
            for item in formulation_items:
                # 구분선 등 제외
                if not item.material_code or item.material_code == "---": 
                    continue
                
                # 키 생성: (code, name)
                key = (item.material_code, item.material_name)
                
                if key not in aggregated_items:
                    aggregated_items[key] = {
                        'material_code': item.material_code,
                        'material_name': item.material_name,
                        'ratio': Decimal('0')
                    }
                
                aggregated_items[key]['ratio'] += to_decimal(item.ratio)

            # 2. 리스트로 변환 및 정렬 (함량 내림차순)
            sorted_items = sorted(
                aggregated_items.values(), 
                key=lambda x: x['ratio'], 
                reverse=True
            )

            # 3. Treeview 데이터 생성
            tree_data_to_process = []
            total_rm_ratio = Decimal('0')
            total_actual_wt = Decimal('0')
            material_no = 1

            for data in sorted_items:
                code = data['material_code']
                name = data['material_name']
                rm_ratio_dec = data['ratio']
                
                # 원료 정보 DB 조회
                material = session.query(Material).filter_by(code=code).first()
                
                group_tag = 'group_odd' if (material_no - 1) % 2 != 0 else 'group_even'
                
                total_rm_ratio += rm_ratio_dec

                # [수정] 중복 전성분 제거 로직 삭제: 원료 내 중복된 전성분도 모두 표시 (사용자 요청)
                unique_ingredients = []
                if material and material.ingredients:
                    # ID 순으로 정렬하여 그대로 사용
                    unique_ingredients = sorted(material.ingredients, key=lambda x: x.id)

                # 100% 단일 성분인지 확인 (unique_ingredients 사용)
                is_single_100 = False
                single_ing = None
                if unique_ingredients and len(unique_ingredients) == 1:
                    try:
                        single_ing = unique_ingredients[0]
                        if to_decimal(single_ing.composition_ratio) == Decimal('100'):
                            is_single_100 = True
                    except Exception:
                        pass

                if not material or not unique_ingredients or is_single_100:
                    # 전성분 없음 OR 단일성분 100% -> 100% 단일 성분 (Big Text)
                    ing_ratio_dec = Decimal('100')
                    actual_wt_dec = rm_ratio_dec
                    total_actual_wt += actual_wt_dec
                    
                    # 단일 성분인 경우 CAS No, Function, Name 가져오기
                    cas_no_val = ""
                    function_val = ""
                    inci_name_val = ""
                    name_ko_val = name # 기본값은 원료명

                    if is_single_100 and single_ing:
                        cas_no_val = single_ing.cas_no or ""
                        function_val = single_ing.function or ""
                        inci_name_val = single_ing.name_en or ""
                        name_ko_val = single_ing.name_ko or name

                    # 컬럼 순서: no, material_name, inci_name, name_ko, rm_ratio, ing_ratio, actual_wt, cas_no, function, hs_code, origin, material_name_en, nmpa_reg_num, supplier, supplier_en, remark
                    values = [
                        material_no, 
                        material.name if material else name, 
                        inci_name_val, 
                        name_ko_val,
                        rm_ratio_dec, 
                        ing_ratio_dec, 
                        actual_wt_dec, 
                        cas_no_val, # cas_no
                        function_val, # function
                        (material.hs_code or "") if material else "", # hs_code (원료)
                        (material.origin or "") if material else "", # origin (원료)
                        (material.name_en or "") if material else "", # material_name_en (원료)
                        (material.nmpa_reg_num or "") if material else "", # nmpa_reg_num (원료)
                        (material.supplier.name or "") if (material and material.supplier) else "", # supplier (원료)
                        (material.supplier.name_en or "") if (material and material.supplier) else "", # supplier_en (원료)
                        "" # remark
                    ]

                    tree_data_to_process.append({
                        "is_first": True, "is_separator": False, "group_tag": group_tag,
                        "values": values
                    })
                else:
                    # 전성분 있음 (unique_ingredients 사용)
                    for i, ing in enumerate(unique_ingredients):
                        ing_comp_ratio_dec = to_decimal(ing.composition_ratio)
                        actual_wt = rm_ratio_dec * (ing_comp_ratio_dec / Decimal('100'))
                        total_actual_wt += actual_wt
                        
                        is_first = (i == 0)
                        
                        # [수정] HS Code, Origin을 Material 테이블에서 가져오도록 변경 (첫 행에만 표시)
                        values = [
                            material_no if is_first else "",                    # no
                            material.name if is_first else "",                  # material_name
                            ing.name_en or "",                                  # inci_name
                            ing.name_ko,                                        # name_ko
                            rm_ratio_dec if is_first else None,                 # rm_ratio
                            ing_comp_ratio_dec,                                 # ing_ratio
                            actual_wt,                                          # actual_wt
                            ing.cas_no,                                         # cas_no
                            ing.function,                                       # function
                            (material.hs_code or "") if is_first else "",       # hs_code (Material)
                            (material.origin or "") if is_first else "",        # origin (Material)
                            (material.name_en or "") if is_first else "",       # material_name_en (Material)
                            (material.supplier.name or "") if (is_first and material and material.supplier) else "", # supplier (Material)
                            ing.remark or ""                                    # remark
                        ]
                        
                        tree_data_to_process.append({
                            "is_first": is_first, "is_separator": False, "group_tag": group_tag,
                            "values": values
                        })
                
                material_no += 1

            # 4. 최대 소수점 자릿수 계산 및 포맷팅
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

    def _show_column_selection_popup(self, treeview, columns_config, x, y):
        """커스텀 열 선택 팝업을 표시합니다."""
        # 이미 열려있는 팝업이 있다면 닫기 (선택사항)
        # 여기서는 단순하게 매번 생성
        ColumnSelectionPopup(self, treeview, columns_config, self._update_visible_columns, x, y)

    def _create_column_selection_menu(self, parent, treeview, columns_config, button_widget):
        """열 선택 팝업 버튼을 설정합니다."""
        # 기존 tk.Menu 대신 커스텀 팝업 사용
        button_widget.configure(command=lambda: self._show_column_selection_popup(
            treeview, 
            columns_config, 
            button_widget.winfo_rootx(), 
            button_widget.winfo_rooty() + button_widget.winfo_height()
        ))

    def _update_visible_columns(self, treeview, columns_config):
        """체크박스 상태에 따라 Treeview의 열을 업데이트합니다."""
        # 특정 Treeview(복합 전성분)의 경우, 일부 열은 다른 열과 함께 활성화되어야 합니다.
        # 예: 'hs_code'가 선택되면 'origin'도 함께 선택.
        try:
            # 안전하게 BooleanVar 접근
            if columns_config is getattr(self, 'complex_ing_cols', None):
                # HS CODE -> origin
                hs_cfg = columns_config.get('hs_code')
                origin_cfg = columns_config.get('origin')
                if hs_cfg and origin_cfg and hs_cfg.get('variable') and origin_cfg.get('variable'):
                    if hs_cfg['variable'].get():
                        origin_cfg['variable'].set(True)

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
            treeview.column(col_id, width=config["width"], anchor=config.get("anchor", "w"), stretch=True)
        
        visible_columns = [col_id for col_id, config in columns_config.items() if config.get("visible", True)]
        visible_columns = [col_id for col_id, config in columns_config.items() if config.get("visible", True)]
        treeview.configure(displaycolumns=visible_columns)

        # 우클릭 메뉴 바인딩 추가
        treeview.bind("<Button-3>", lambda event: self._show_column_selection_popup(
            treeview, columns_config, event.x_root, event.y_root
        ))

    def copy_complex_ingredients_to_clipboard(self):
        """복합 전성분 텍스트박스의 내용을 클립보드에 복사합니다."""
        # TODO: 현재 활성화된 Treeview의 내용을 복사하도록 수정 필요
        messagebox.showinfo(self.texts['notification'], self.texts['clipboard_copy_dev'], parent=self)

    def setup_single_ingredient_tab(self, tab_frame):
        """'단일 전성분 (함량순)' 탭의 UI를 설정합니다."""
        tab_frame.grid_columnconfigure(0, weight=1)
        tab_frame.grid_columnconfigure(1, weight=0)
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
        self.single_ingredient_tree.grid(row=0, column=0, padx=(10,0), pady=(10,5), sticky="nsew") # Treeview를 맨 위로 이동

        # 단일 전성분 스크롤바
        single_v_scroll = ttk.Scrollbar(tab_frame, orient="vertical", command=self.single_ingredient_tree.yview)
        self.single_ingredient_tree.configure(yscrollcommand=single_v_scroll.set)
        single_v_scroll.grid(row=0, column=1, padx=(0,10), pady=(10,5), sticky='ns')
        single_h_scroll = ttk.Scrollbar(tab_frame, orient="horizontal", command=self.single_ingredient_tree.xview)
        self.single_ingredient_tree.configure(xscrollcommand=single_h_scroll.set)
        single_h_scroll.grid(row=1, column=0, padx=(10,0), sticky='ew')
        
        # 단일 전성분 합계 프레임
        single_summary_frame = ctk.CTkFrame(tab_frame, fg_color="transparent")
        single_summary_frame.grid(row=2, column=0, columnspan=2, sticky="e", padx=10, pady=5)
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
                                'hs_code': ing.hs_code or "", 'remark': ing.remark or ""
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
                    data['remark']
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
        
        # --- 상단 컨트롤 프레임 (마진을 바짝 밀착시켜 높이 확보) ---
        top_control_frame = ctk.CTkFrame(tab_frame, fg_color="transparent")
        top_control_frame.grid(row=0, column=0, padx=10, pady=(2, 2), sticky="ew")

        # 생성 버튼은 강제 생성(force=True)으로 호출하여 탭 활성화 여부와 무관하게 생성되도록 함
        ctk.CTkButton(top_control_frame, text=self.texts['create_all_lists'], width=90, height=26, command=lambda: self.generate_all_ingredient_lists(force=True), font=("", 11)).pack(side="left")
        ctk.CTkButton(top_control_frame, text="📊 전성분 엑셀 (KO)", width=110, height=26, command=lambda: self.export_all_ingredient_lists(lang="ko"), font=("", 11)).pack(side="left", padx=(5, 0))
        ctk.CTkButton(top_control_frame, text="🌐 영문 전성분 (EN)", width=120, height=26, fg_color="#1565C0", hover_color="#0D47A1", command=lambda: self.export_all_ingredient_lists(lang="en"), font=("", 11)).pack(side="left", padx=(5, 0))

        # --- 열 선택 메뉴 버튼 (컨트롤 프레임에 추가) ---
        # 이 버튼은 나중에 생성될 Treeview를 참조해야 하므로, UI 구성 후 마지막에 command를 설정합니다.
        self.column_selection_button = ctk.CTkButton(top_control_frame, text=self.texts['select_columns_to_display'], width=100, height=26, font=("", 11))
        self.column_selection_button.pack(side="right", padx=(5, 0))

        # 전성분 탭 내부에 또 다른 탭 뷰를 생성합니다. (상단 여백 0으로 밀착)
        self.ingredient_tab_view = ctk.CTkTabview(
            tab_frame, border_width=0, border_color=("gray85", "gray28"),
            command=self.on_ingredient_tab_change # 탭 변경 시 호출될 함수 연결
        )
        self.ingredient_tab_view.grid(row=1, column=0, padx=10, pady=(0, 4), sticky="nsew")
        
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

    def _is_ingredient_main_tab_active(self) -> bool:
        """현재 '전성분' 메인 서브 탭이 활성화되어 있는지 확인합니다."""
        try:
            label_map = {"korean": "전성분", "english": "Ingredient List"}
            expected = label_map.get(getattr(self.app, 'language', 'korean'), "전성분")
            return hasattr(self, 'formulation_sub_tab_view') and self.formulation_sub_tab_view.get() == expected
        except Exception:
            return False

    def generate_all_ingredient_lists(self, force: bool = False):
        """모든 종류의 전성분 목록을 한 번에 생성합니다.
        - force=False일 때는 '전성분' 탭이 활성화된 경우에만 생성합니다.
        - 처방 선택이 해제된 경우에는 항상 모든 목록을 비웁니다.
        """
        # 선택 해제 시에는 언제나 정리
        if not self._selected_formulation_id:
            for tree in [self.raw_material_ingredient_tree, self.summed_ingredient_tree, self.single_ingredient_tree]:
                tree.delete(*tree.get_children())
            self.raw_material_rm_ratio_total_label.configure(text="0.0000")
            self.raw_material_actual_wt_total_label.configure(text="0")
            self.summed_total_ratio_label.configure(text="0")
            self.single_total_ratio_label.configure(text="0")
            self.design_ko_textbox.delete("1.0", "end")
            self.design_en_textbox.delete("1.0", "end")
            return

        # 전성분 탭이 비활성 상태이고 강제 생성이 아니면 조용히 종료 (다른 탭 조작 시 불필요한 생성 방지)
        if not force and not self._is_ingredient_main_tab_active():
            return

        # 생성 수행
        self.generate_raw_material_ingredient_list()
        self.generate_summed_ingredient_list()
        self.generate_single_ingredient_list()
        self.generate_design_ingredient_list()

    def export_all_ingredient_lists(self, lang="ko"):
        """생성된 모든 전성분 목록을 하나의 엑셀 파일에 여러 시트로 내보냅니다."""
        is_eng = (lang == "en")
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
            
            # 1. 원료별 합산 (Code와 Name이 같은 경우)
            aggregated_items = {}
            
            for item in formulation_items:
                # 구분선 등 제외
                if not item.material_code or item.material_code == "---": 
                    continue
                
                # 키 생성: (code, name)
                key = (item.material_code, item.material_name)
                
                if key not in aggregated_items:
                    aggregated_items[key] = {
                        'material_code': item.material_code,
                        'material_name': item.material_name,
                        'ratio': Decimal('0')
                    }
                
                aggregated_items[key]['ratio'] += to_decimal(item.ratio)

            # 2. 리스트로 변환 및 정렬 (함량 내림차순)
            sorted_items = sorted(
                aggregated_items.values(), 
                key=lambda x: x['ratio'], 
                reverse=True
            )
            
            # Build raw material data as dict rows keyed by complex_ing_cols keys.
            col_order = [
                'no', 'material_name', 'inci_name', 'name_ko', 'rm_ratio', 'ing_ratio', 'actual_wt',
                'cas_no', 'function', 'hs_code', 'origin', 'material_name_en', 'supplier', 'remark'
            ]

            raw_rows = []
            raw_rows_decimal = [] # Decimal 객체를 그대로 저장할 리스트
            material_no = 1
            
            for data in sorted_items:
                code = data['material_code']
                name = data['material_name']
                rm_ratio_dec = data['ratio']

                material = session.query(Material).filter_by(code=code).first()

                # [수정] 중복 전성분 제거 로직 삭제 (Export)
                unique_ingredients = []
                if material and material.ingredients:
                    unique_ingredients = sorted(material.ingredients, key=lambda x: x.id)

                # 100% 단일 성분인지 확인
                is_single_100 = False
                single_ing = None
                if unique_ingredients and len(unique_ingredients) == 1:
                    try:
                        single_ing = unique_ingredients[0]
                        if to_decimal(single_ing.composition_ratio) == Decimal('100'):
                            is_single_100 = True
                    except Exception:
                        pass

                if not material or not unique_ingredients or is_single_100:
                    actual_wt = rm_ratio_dec
                    # 단일 성분인 경우 CAS No, Function, Name 가져오기
                    cas_no_val = "-"
                    function_val = "-"
                    inci_name_val = ""
                    name_ko_val = item.material_name # 기본값

                    if is_single_100 and single_ing:
                        cas_no_val = single_ing.cas_no or "-"
                        function_val = single_ing.function or "-"
                        inci_name_val = single_ing.name_en or ""
                        name_ko_val = single_ing.name_ko or item.material_name

                    row = {
                        'no': material_no,
                        'material_name': material.name if material else item.material_name,
                        'inci_name': inci_name_val,
                        'name_ko': name_ko_val,
                        'rm_ratio': actual_wt,
                        'ing_ratio': Decimal('100'),
                        'actual_wt': actual_wt,
                        'cas_no': cas_no_val,
                        'function': function_val,
                        'hs_code': (material.hs_code or "") if material else "",
                        'origin': material.origin if material else "",
                        'material_name_en': material.name_en if material else "",
                        'supplier': (material.supplier.name or "") if (material and material.supplier) else "",
                        'remark': ""
                    }
                    raw_rows_decimal.append(row)
                    material_no += 1
                else:
                    for i, ing in enumerate(unique_ingredients):
                        ing_comp_ratio_dec = to_decimal(ing.composition_ratio)
                        actual_wt = rm_ratio_dec * (ing_comp_ratio_dec / Decimal('100'))
                        if i == 0:
                            row = {
                                'no': material_no,
                                'material_name': material.name,
                                'inci_name': ing.name_en or "",
                                'name_ko': ing.name_ko,
                                'rm_ratio': rm_ratio_dec,
                                'ing_ratio': ing_comp_ratio_dec,
                                'actual_wt': actual_wt,
                                'cas_no': ing.cas_no or "-",
                                'function': ing.function or "-",
                                'hs_code': (material.hs_code or "") if material else "",
                                'origin': material.origin if material else "",
                                'material_name_en': material.name_en if material else "",
                                'supplier': (material.supplier.name or "") if (material and material.supplier) else "",
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
                                'hs_code': (material.hs_code or "") if material else "",
                                'origin': material.origin if material else "",
                                'material_name_en': material.name_en if material else "",
                                'supplier': "",
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
                        'origin': '원산지', 'material_name_en': '영문원료명', 'supplier': '거래처명', 'remark': 'Remark'
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
                                'hs_code': ing.hs_code or "", 'nmpa_reg_num': (material.nmpa_reg_num or "") if material else "", 'remark': ing.remark or ""
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
        if (ko_text or en_text) and self.texts['press_button_placeholder'] not in ko_text:
            if is_eng:
                design_headers = ["Type", "INCI Ingredients"]
                design_data = [("INCI (English):", en_text)]
                sheets_data["Packaging INCI"] = {"type": "table", "content": {"headers": design_headers, "data": design_data}}
            else:
                design_headers = ["구분", "전성분 목록"]
                design_data = [
                    ("국문:", ko_text),
                    ("영문 (INCI):", en_text)
                ]
                sheets_data[self.texts['ingredients_for_design']] = {"type": "table", "content": {"headers": design_headers, "data": design_data}}

        if not sheets_data:
            messagebox.showwarning(self.texts['export_error'], self.texts['no_data_to_export_create_list'], parent=self)
            return

        session = db_manager.get_session()
        formulation = session.query(Formulation).filter_by(id=self._selected_formulation_id).first()
        session.close()
        
        f_name = (formulation.experiment_name_en or formulation.experiment_name) if (formulation and is_eng) else (formulation.experiment_name if formulation else "전성분목록")
        default_filename = f"{f_name}_Ingredients_EN.xlsx" if is_eng else f"{f_name}_전성분목록.xlsx"
        
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
        top_button_frame.grid(row=0, column=0, padx=10, pady=(0, 5), sticky="e")
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
        filter_frame.grid(row=0, column=0, padx=10, pady=(0, 5), sticky="ew")
        filter_frame.grid_columnconfigure(6, weight=1) # 오른쪽 정렬을 위한 빈 공간
        
        # DB에서 존재하는 연도 가져오기 (자동 추가)
        current_year = datetime.now().year
        db_years = set()
        session = db_manager.get_session()
        try:
            # experiment_date는 String(20)이므로 앞 4자리를 잘라서 연도로 인식
            # SQLite/MySQL 호환성을 위해 func.substr 사용
            existing_years = session.query(func.substr(Formulation.experiment_date, 1, 4)).distinct().all()
            for y in existing_years:
                if y[0] and y[0].isdigit() and len(y[0]) == 4:
                    db_years.add(int(y[0]))
        except Exception as e:
            print(f"연도 목록 조회 실패: {e}")
        finally:
            session.close()

        # 기본 범위: 현재 연도 기준 +/- 10년
        default_range = set(range(current_year - 10, current_year + 11))
        
        # DB 연도와 기본 범위 합치기
        all_years = sorted(default_range.union(db_years))
        years = [str(y) for y in all_years]
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

    def load_formulations(self, client_id=None, maintain_position=False):
        """DB에서 처방 목록을 불러와 현재 뷰에 맞게 표시합니다."""
        # [버그 수정] client_id가 None이면 현재 선택된 업체 사용
        effective_client_id = client_id if client_id is not None else self.current_client_id
        
        if self.current_view == "folders":
            # maintain_position이 True이면 초기화(is_initial_load)를 하지 않음
            self.load_folders(client_id=effective_client_id, is_initial_load=not maintain_position)
        elif self.current_view == "files":
            self.load_files_in_folder(self.current_folder_name, effective_client_id)

    def load_folders(self, client_id=None, is_initial_load=True):
        """폴더 카드를 표시합니다. (업체별 → 아이템별 2단계 구조)"""
        for widget in self.folder_view.winfo_children():
            widget.destroy()

        # [UI 버그 수정] 내용 변경 후 스크롤 프레임이 즉시 갱신되지 않는 현상(빈 화면) 해결을 위해 강제 업데이트
        self.folder_view.update_idletasks()
        # 스크롤 위치를 맨 위로 초기화 (선택 사항이지만 UI 경험상 좋음)
        if hasattr(self.folder_view, '_parent_canvas'):
             self.folder_view._parent_canvas.yview_moveto(0)

        if is_initial_load:
            try:
                icon_size_str = self.app.get_config_value('Appearance', 'folder_icon_size', '40')
                self.icon_size_slider.set(int(float(icon_size_str)))
            except Exception as e:
                print(f"폴더 아이콘 크기 로드 실패: {e}")
                self.icon_size_slider.set(40)
            # 초기 로드 시 업체 레벨로 시작
            self.current_view_level = "client"
            self.current_client_id = None
            self.current_client_name = None
        
        session = db_manager.get_session()
        try:
            search_term = ""
            if hasattr(self, 'list_search_entry'):
                search_term = self.list_search_entry.get().strip()
            
            if self.current_view_level == "client":
                # === 업체별 폴더 표시 ===
                self._load_client_folders(session, search_term)
            else:
                # === 아이템별 폴더 표시 (특정 업체 선택됨) ===
                self._load_item_folders(session, search_term)
        except Exception as db_err:
            # 동기화 직후 DB 연결 문제 등으로 오류 발생 시 안내 표시
            print(f"[처방폴더] load_folders DB 오류: {db_err}")
            try:
                # 폴더 뷰 초기화 후 안내 메시지 표시
                for widget in self.folder_view.winfo_children():
                    try:
                        widget.destroy()
                    except Exception:
                        pass
                import customtkinter as ctk
                ctk.CTkLabel(
                    self.folder_view,
                    text="⚠️ 데이터베이스 연결이 일시적으로 불안정합니다.\n잠시 후 다시 시도해주세요.",
                    font=ctk.CTkFont(size=14),
                    text_color="orange"
                ).pack(pady=50)
            except Exception:
                pass
        finally:
            try:
                session.close()
            except Exception:
                pass

    
    def _load_client_folders(self, session, search_term=""):
        """업체별 폴더 표시"""
        # 업체별로 그룹화: oem_odm_client_id가 있는 것들
        from sqlalchemy import func
        
        # 업체가 지정된 처방 카운트 - Client JOIN
        client_query = session.query(
            Client.id,
            Client.name,
            func.count(Formulation.id)
        ).join(
            Formulation, Formulation.oem_odm_client_id == Client.id
        )
        
        if search_term:
            client_query = client_query.filter(
                or_(
                    Client.name.like(f"%{search_term}%"),
                    Formulation.experiment_name.like(f"%{search_term}%")
                )
            )
        
        client_query = client_query.group_by(Client.id, Client.name).order_by(Client.name)
        client_data = client_query.all()
        
        # 업체가 미지정된 처방 카운트
        unassigned_query = session.query(func.count(Formulation.id)).filter(
            or_(
                Formulation.oem_odm_client_id == None,
                Formulation.oem_odm_client_id == 0
            )
        )
        if search_term:
            unassigned_query = unassigned_query.filter(Formulation.experiment_name.like(f"%{search_term}%"))
        unassigned_count = unassigned_query.scalar() or 0
        
        if not client_data and unassigned_count == 0:
            ctk.CTkLabel(self.folder_view, text=self.texts['no_formulation_data'], 
                        font=ctk.CTkFont(size=16)).pack(pady=50)
            return
        
        row, col = 0, 0
        
        # [수정] 카드 크기에 따라 열 수 동적 계산
        icon_size = int(self.icon_size_slider.get())
        card_width = int(icon_size * 4) + 20  # 카드 너비 + 패딩
        self.folder_view.update_idletasks()
        container_width = self.folder_view.winfo_width()
        if container_width < 100:  # 초기 로드 시 너비가 작을 수 있음
            container_width = 800  # 기본값
        max_cols = max(1, container_width // card_width)
        
        # 업체별 폴더 카드
        for client_id, client_name, count in client_data:
            card = self._create_client_folder_card(self.folder_view, client_id, client_name, count)
            card.grid(row=row, column=col, padx=10, pady=10, sticky="nsew")
            col += 1
            if col >= max_cols:
                col = 0
                row += 1
        
        # 미지정 폴더 (업체가 없는 처방들)
        if unassigned_count > 0:
            unassigned_name = self.texts.get("unassigned_client", "미지정")
            card = self._create_client_folder_card(self.folder_view, None, unassigned_name, unassigned_count)
            card.grid(row=row, column=col, padx=10, pady=10, sticky="nsew")
    
    def _load_item_folders(self, session, search_term=""):
        """특정 업체 내의 아이템별 폴더 표시 (실험명 기준 그룹화)"""
        from sqlalchemy import func
        
        # [수정] 사용자의 요청으로 다시 '실험명' 기준으로만 그룹화 (내부에서 리스트로 구분)
        query = session.query(Formulation.experiment_name, func.count(Formulation.id))
        
        # 업체 필터링
        if self.current_client_id is None:
            # 미지정 업체
            query = query.filter(
                or_(
                    Formulation.oem_odm_client_id == None,
                    Formulation.oem_odm_client_id == 0
                )
            )
        else:
            query = query.filter(Formulation.oem_odm_client_id == self.current_client_id)
        
        if search_term:
            query = query.filter(Formulation.experiment_name.like(f"%{search_term}%"))
        
        # 그룹화 기준: experiment_name Only
        grouped_data = query.group_by(Formulation.experiment_name).order_by(Formulation.experiment_name).all()
        
        if not grouped_data:
            ctk.CTkLabel(self.folder_view, text=self.texts['no_formulation_data'], 
                        font=ctk.CTkFont(size=16)).pack(pady=50)
            return
        
        # 상단에 뒤로가기 버튼 추가
        back_frame = ctk.CTkFrame(self.folder_view, fg_color="transparent")
        back_frame.grid(row=0, column=0, columnspan=5, sticky="w", padx=5, pady=(0, 10))
        
        back_btn = ctk.CTkButton(
            back_frame, 
            text=f"← {self.texts.get('back_to_clients', '업체 목록으로')}",
            width=120,
            fg_color="gray50",
            hover_color="gray40",
            command=self._go_back_to_client_view
        )
        back_btn.pack(side="left")
        
        # 현재 업체명 표시
        client_label = ctk.CTkLabel(
            back_frame,
            text=f"  📁 {self.current_client_name or self.texts.get('unassigned_client', '미지정')}",
            font=ctk.CTkFont(size=14, weight="bold")
        )
        client_label.pack(side="left", padx=10)
        
        # [수정] 카드 크기에 따라 열 수 동적 계산
        icon_size = int(self.icon_size_slider.get())
        card_width = int(icon_size * 4) + 20  # 카드 너비 + 패딩
        self.folder_view.update_idletasks()
        container_width = self.folder_view.winfo_width()
        if container_width < 100:  # 초기 로드 시 너비가 작을 수 있음
            container_width = 800  # 기본값
        max_cols = max(1, container_width // card_width)
        
        row, col = 1, 0  # 뒤로가기 버튼 아래부터 시작
        for name, count in grouped_data:
            # 카드에 표시할 이름: 제품명만 표시
            display_name = name or "(이름 없음)"
            
            card = self.create_folder_card(self.folder_view, display_name, count)
            card.grid(row=row, column=col, padx=10, pady=10, sticky="nsew")
            col += 1
            if col >= max_cols:
                col = 0
                row += 1
    
    def _create_client_folder_card(self, parent, client_id, client_name, item_count):
        """업체 폴더 카드 생성"""
        icon_size = int(self.icon_size_slider.get())
        
        # [수정] 카드 크기도 슬라이더에 따라 조절
        card_width = int(icon_size * 4)   # 아이콘 크기의 4배
        card_height = int(icon_size * 3)  # 아이콘 크기의 3배
        title_size = max(11, int(icon_size / 3))  # 제목 크기도 비례 조절
        count_size = max(9, int(icon_size / 4))   # 카운트 크기도 비례 조절
        wraplength = int(icon_size * 3)
        
        card = ctk.CTkFrame(parent, corner_radius=10, fg_color=("gray95", "gray20"),
                           border_width=1, border_color=("gray80", "gray40"),
                           width=card_width, height=card_height)
        card.pack_propagate(False)  # 카드 크기 고정
        card.bind("<Button-1>", lambda e, cid=client_id, cname=client_name: self._on_client_folder_click(cid, cname))
        card.bind("<Enter>", lambda e, c=card: c.configure(fg_color=("gray85", "gray30")))
        card.bind("<Leave>", lambda e, c=card: c.configure(fg_color=("gray95", "gray20")))
        
        # 업체 아이콘 (🏢)
        icon_label = ctk.CTkLabel(card, text="🏢", font=ctk.CTkFont(size=icon_size))
        icon_label.pack(pady=(max(5, int(icon_size/8)), 3))
        icon_label.bind("<Button-1>", lambda e, cid=client_id, cname=client_name: self._on_client_folder_click(cid, cname))
        
        # 업체명
        name_label = ctk.CTkLabel(card, text=client_name, font=ctk.CTkFont(size=title_size, weight="bold"),
                                 wraplength=wraplength)
        name_label.pack()
        name_label.bind("<Button-1>", lambda e, cid=client_id, cname=client_name: self._on_client_folder_click(cid, cname))
        
        # 아이템 수
        count_label = ctk.CTkLabel(card, text=f"({item_count}개 아이템)", font=ctk.CTkFont(size=count_size),
                                  text_color="gray50")
        count_label.pack(pady=(0, max(5, int(icon_size/8))))
        count_label.bind("<Button-1>", lambda e, cid=client_id, cname=client_name: self._on_client_folder_click(cid, cname))
        
        return card
    
    def _on_client_folder_click(self, client_id, client_name):
        """업체 폴더 클릭 시 해당 업체의 아이템 폴더 표시"""
        self.current_view_level = "item"
        self.current_client_id = client_id
        self.current_client_name = client_name
        self.load_folders(is_initial_load=False)
    
    def _go_back_to_client_view(self):
        """아이템 뷰에서 업체 뷰로 돌아가기"""
        self.current_view_level = "client"
        self.current_client_id = None
        self.current_client_name = None
        self.load_folders(is_initial_load=False)

    def load_files_in_folder(self, folder_name, client_id=None, is_unassigned=False):
        """특정 폴더(실험품명)에 속한 처방들을 파일 목록으로 표시합니다."""
        for item in self.formulation_tree.get_children():
            self.formulation_tree.delete(item)

        session = db_manager.get_session()
        try:
            # [수정] 다시 실험명으로만 검색 (폴더명이 곧 실험명)
            query = session.query(Formulation).filter_by(experiment_name=folder_name)
            
            # [버그 수정] 미지정 업체도 정확히 필터링
            if is_unassigned or (client_id is None and self.current_view_level == "item"):
                # 미지정 업체: client_id가 None 또는 0인 처방만 표시
                query = query.filter(
                    or_(
                        Formulation.oem_odm_client_id == None,
                        Formulation.oem_odm_client_id == 0
                    )
                )
            elif client_id:
                query = query.filter(Formulation.oem_odm_client_id == client_id)
            
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
            try:
                # Treeview iid는 정수로 설정해도 문자열로 반환될 수 있으므로 안전하게 변환
                self._selected_formulation_id = int(first_item_id)
            except (ValueError, TypeError):
                self._selected_formulation_id = None
        else:
            self._selected_formulation_id = None
        self.update_button_states()
        # 패키지 탭 리스트는 자동으로 갱신하지 않음 (사용자가 패키지 탭을 선택하거나 패키지 생성 후에만 갱신)
        # 생산 처방 리스트는 자동으로 불러오지 않고 비워둡니다.
        # 사용자가 '생산처방 생성'을 수행한 이후에만 목록이 생성되도록 요구사항 반영.
        if hasattr(self, 'production_tree'):
            try:
                for item in self.production_tree.get_children():
                    self.production_tree.delete(item)
            except Exception:
                pass

    def get_selected_formulation_ids(self):
        """Treeview에서 선택된 모든 처방의 ID 목록을 반환합니다."""
        selected_ids = []
        selected_items = self.formulation_tree.selection()
        for iid in selected_items:
            if str(iid).isdigit():
                selected_ids.append(int(iid))
        return selected_ids

    def change_formulation_client(self):
        """선택된 처방들의 업체를 일괄 변경합니다."""
        selected_ids = self.get_selected_formulation_ids()
        if not selected_ids:
            messagebox.showwarning("선택 필요", "업체를 변경할 처방을 하나 이상 선택해주세요.", parent=self)
            return
        
        # 업체 선택 팝업 생성
        popup = ctk.CTkToplevel(self)
        popup.title("업체 변경")
        popup.geometry("400x300")
        popup.transient(self)
        popup.grab_set()
        
        # 안내 라벨
        ctk.CTkLabel(popup, text=f"선택된 {len(selected_ids)}개 처방의 업체를 변경합니다.", 
                    font=ctk.CTkFont(size=14, weight="bold")).pack(pady=(20, 10))
        
        # 업체 유형 선택
        type_frame = ctk.CTkFrame(popup, fg_color="transparent")
        type_frame.pack(fill="x", padx=20, pady=5)
        ctk.CTkLabel(type_frame, text="업체 유형:").pack(side="left")
        # 데이터베이스에서 실제 업체 유형 가져오기
        client_types = db_manager.get_unique_client_types()
        if not client_types:
            client_types = ["OEM/ODM"]  # 기본값
        client_type_combo = ctk.CTkComboBox(type_frame, values=client_types, width=150)
        client_type_combo.pack(side="left", padx=10)
        client_type_combo.set(client_types[0])
        
        # 업체명 선택
        name_frame = ctk.CTkFrame(popup, fg_color="transparent")
        name_frame.pack(fill="x", padx=20, pady=5)
        ctk.CTkLabel(name_frame, text="업체명:").pack(side="left")
        client_name_combo = ctk.CTkComboBox(name_frame, values=["(로딩 중...)"], width=250)
        client_name_combo.pack(side="left", padx=10)
        
        # 미지정 옵션 체크박스
        unassigned_var = ctk.BooleanVar(value=False)
        unassigned_check = ctk.CTkCheckBox(popup, text="미지정으로 변경 (업체 해제)", variable=unassigned_var)
        unassigned_check.pack(pady=10)
        
        # 업체 목록 저장용
        client_map = {}
        
        def load_clients(client_type):
            """선택된 유형의 업체 목록을 로드합니다."""
            nonlocal client_map
            client_map.clear()
            session = db_manager.get_session()
            try:
                clients = session.query(Client).filter_by(client_type=client_type).order_by(Client.name).all()
                if clients:
                    names = [c.name for c in clients]
                    client_name_combo.configure(values=names)
                    client_name_combo.set(names[0])
                    for c in clients:
                        client_map[c.name] = c.id
                else:
                    client_name_combo.configure(values=["(업체 없음)"])
                    client_name_combo.set("(업체 없음)")
            finally:
                session.close()
        
        # 초기 로드
        load_clients(client_types[0])
        
        # 유형 변경 시 업체 목록 갱신
        def on_type_change(choice):
            load_clients(choice)
        client_type_combo.configure(command=on_type_change)
        
        # 미지정 체크 시 업체 콤보 비활성화
        def on_unassigned_toggle():
            if unassigned_var.get():
                client_type_combo.configure(state="disabled")
                client_name_combo.configure(state="disabled")
            else:
                client_type_combo.configure(state="normal")
                client_name_combo.configure(state="normal")
        unassigned_check.configure(command=on_unassigned_toggle)
        
        # 버튼 프레임
        btn_frame = ctk.CTkFrame(popup, fg_color="transparent")
        btn_frame.pack(pady=20)
        
        def apply_change():
            """선택된 처방들의 업체를 변경합니다."""
            if unassigned_var.get():
                target_client_id = None
            else:
                selected_name = client_name_combo.get()
                if selected_name in ["(로딩 중...)", "(업체 없음)"]:
                    messagebox.showwarning("업체 선택", "변경할 업체를 선택해주세요.", parent=popup)
                    return
                target_client_id = client_map.get(selected_name)
                if not target_client_id:
                    messagebox.showwarning("업체 오류", "선택한 업체를 찾을 수 없습니다.", parent=popup)
                    return
            
            # 확인 메시지
            target_name = "미지정" if target_client_id is None else client_name_combo.get()
            if not messagebox.askyesno("업체 변경 확인", 
                                       f"선택된 {len(selected_ids)}개 처방의 업체를\n'{target_name}'(으)로 변경하시겠습니까?", 
                                       parent=popup):
                return
            
            # DB 업데이트
            session = db_manager.get_session()
            try:
                updated_count = 0
                for form_id in selected_ids:
                    formulation = session.query(Formulation).filter_by(id=form_id).first()
                    if formulation:
                        formulation.oem_odm_client_id = target_client_id
                        updated_count += 1
                
                session.commit()
                messagebox.showinfo("변경 완료", f"{updated_count}개 처방의 업체가 변경되었습니다.", parent=popup)
                popup.destroy()
                
                # 폴더 뷰 새로고침
                self.load_formulations(maintain_position=True)
                
                # [추가] 폴더가 비어있으면 상위 폴더로 자동 이동
                if self.current_view == "files":
                    if not self.formulation_tree.get_children():
                        # 현재 폴더에 처방이 하나도 없으면 상위(폴더 뷰)로 이동
                        self.show_folder_view()
                
            except Exception as e:
                session.rollback()
                messagebox.showerror("오류", f"업체 변경 중 오류 발생:\n{e}", parent=popup)
            finally:
                session.close()
        
        ctk.CTkButton(btn_frame, text="변경", width=80, command=apply_change).pack(side="left", padx=10)
        ctk.CTkButton(btn_frame, text="취소", width=80, fg_color="gray50", command=popup.destroy).pack(side="left", padx=10)

    def delete_formulation(self):
        """선택된 처방을 삭제합니다. (연구원 이상 권한)"""
        # 권한 확인
        if not self.current_user.can_delete_formulation():
            messagebox.showwarning("권한 없음", "처방 삭제는 연구원 이상만 가능합니다.", parent=self)
            return
        
        selected_ids = self.get_selected_formulation_ids()
        if not selected_ids:
            messagebox.showwarning(self.texts['selection_error'], self.texts['select_formulation_to_delete'], parent=self)
            return

        session = db_manager.get_session()
        try:
            # 삭제 전 현재 상태 기록
            current_view = self.current_view
            current_folder_name = self.current_folder_name
            current_client_id = self.current_client_id
            current_view_level = self.current_view_level
            
            # 삭제 전 관련 데이터 확인
            related_data = []
            backup_data = []
            
            for form_id in selected_ids:
                formulation = session.query(Formulation).options(joinedload(Formulation.items)).filter_by(id=form_id).first()
                if not formulation:
                    continue
                
                # 생산처방 확인
                prod_forms = session.query(ProductionFormulation).filter_by(source_formulation_id=form_id).all()
                if prod_forms:
                    prod_names = [pf.product_name or pf.production_code or f"ID:{pf.id}" for pf in prod_forms]
                    related_data.append(f"• 처방 '{formulation.experiment_name}' (LAB NO: {formulation.lab_no or 'N/A'})\n  → 생산처방 {len(prod_forms)}개: {', '.join(prod_names[:3])}{'...' if len(prod_names) > 3 else ''}")
                
                # 문서패키지 링크 확인 (처방이 문서패키지에서 참조되는 경우)
                # DocumentPackageLink에서 doc_type='Formulation'으로 참조되는 경우 확인
                # 현재 구조상 처방은 직접 링크되지 않지만, 혹시 모를 경우를 대비
                
                # 백업 데이터 준비
                formulation_dict = {
                    'id': formulation.id,
                    'experiment_name': formulation.experiment_name,
                    'lab_no': formulation.lab_no,
                    'revision': formulation.revision,
                    'manager_name': formulation.manager_name,
                    'manager_code': formulation.manager_code,
                    'experiment_date': formulation.experiment_date,
                    'experiment_ph_initial': formulation.experiment_ph_initial,
                    'experiment_ph_next_day': formulation.experiment_ph_next_day,
                    'experiment_viscosity_initial': formulation.experiment_viscosity_initial,
                    'experiment_viscosity_next_day': formulation.experiment_viscosity_next_day,
                    'experiment_machine': formulation.experiment_machine,
                    'experiment_comment': formulation.experiment_comment,
                    'oem_odm_client_id': formulation.oem_odm_client_id,
                    'has_target_info': formulation.has_target_info,
                    'target_sample_name': formulation.target_sample_name,
                    'target_ph_initial': formulation.target_ph_initial,
                    'target_ph_next_day': formulation.target_ph_next_day,
                    'target_viscosity_initial': formulation.target_viscosity_initial,
                    'target_viscosity_next_day': formulation.target_viscosity_next_day,
                    'target_machine': formulation.target_machine,
                    'target_client_id': formulation.target_client_id,
                    'sample_sent_count': formulation.sample_sent_count,
                    'sample_delivery_date': str(formulation.sample_delivery_date) if formulation.sample_delivery_date else None,
                    'change_log': formulation.change_log,
                    'created_at': str(formulation.created_at) if formulation.created_at else None,
                    'items': []
                }
                
                for item in formulation.items:
                    formulation_dict['items'].append({
                        'order': item.order,
                        'phase': item.phase,
                        'material_code': item.material_code,
                        'material_name': item.material_name,
                        'ratio': item.ratio,
                        'amount': item.amount,
                        'material_id': item.material_id
                    })
                
                backup_data.append(formulation_dict)
            
            # 관련 데이터가 있으면 경고 메시지 표시
            if related_data:
                warning_msg = "다음 관련 데이터가 존재합니다:\n\n" + "\n\n".join(related_data)
                warning_msg += "\n\n계속하시겠습니까?"
                if not messagebox.askyesno("관련 데이터 경고", warning_msg, parent=self):
                    return
            
            # 최종 삭제 확인
            confirm_msg = self.texts['delete_formulation_confirm_msg'].format(count=len(selected_ids))
            if related_data:
                confirm_msg += "\n\n※ 관련 데이터는 자동으로 백업됩니다."
            
            if not messagebox.askyesno(self.texts['delete_confirm'], confirm_msg, parent=self):
                return
            
            # 삭제 전 현재 폴더/업체에 남아있을 처방 개수 예측
            # selected_ids 중에서 현재 폴더/업체에 속한 것만 세기
            if current_view == "files" and current_folder_name:
                # 현재 폴더/업체에 있는 모든 처방의 ID를 가져오기
                pre_delete_query = session.query(Formulation.id).filter_by(experiment_name=current_folder_name)
                if current_client_id:
                    pre_delete_query = pre_delete_query.filter_by(oem_odm_client_id=current_client_id)
                else:
                    pre_delete_query = pre_delete_query.filter(
                        or_(
                            Formulation.oem_odm_client_id == None,
                            Formulation.oem_odm_client_id == 0
                        )
                    )
                current_form_ids = [id for (id,) in pre_delete_query.all()]
                # 선택된 ID 중에서 현재 폴더에 속한 개수 세기
                delete_count_in_folder = sum(1 for id in selected_ids if id in current_form_ids)
                pre_delete_count = len(current_form_ids)
                expected_remaining = pre_delete_count - delete_count_in_folder
            
            # 백업 수행
            if backup_data:
                from modules.secure_vault import SecureVault
                
                # AppData 심층 시스템 은닉 볼트에 암호화 백업
                for f_data in backup_data:
                    SecureVault.encrypt_and_save(
                        category='formulations',
                        record_id=f"{f_data.get('experiment_name', 'form')}_{f_data.get('id')}",
                        data_dict=f_data,
                        username=self.current_user.username
                    )
                
                # 로컬 백업 폴더(보조) 저장
                backup_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'data', 'backups', 'formulations')
                os.makedirs(backup_dir, exist_ok=True)
                
                timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
                backup_filename = f"formulation_backup_{timestamp}.json"
                backup_filepath = os.path.join(backup_dir, backup_filename)
                
                backup_info = {
                    'backup_date': timestamp,
                    'deleted_by': self.current_user.username,
                    'deleted_by_name': self.current_user.real_name or self.current_user.username,
                    'formulations': backup_data
                }
                
                with open(backup_filepath, 'w', encoding='utf-8') as f:
                    json.dump(backup_info, f, ensure_ascii=False, indent=2)
            
            # 선택된 모든 ID에 대해 삭제를 수행합니다.
            query = session.query(Formulation).filter(Formulation.id.in_(selected_ids))
            deleted_count = query.delete(synchronize_session=False)
            
            session.commit()
            
            success_msg = self.texts['delete_formulation_success_msg'].format(count=deleted_count)
            if backup_data:
                success_msg += f"\n\n백업 파일: {backup_filename}"
            
            messagebox.showinfo(self.texts['success'], success_msg, parent=self)
            self._selected_formulation_id = None # ID 초기화
            self.update_button_states() # 버튼 상태 업데이트
            
            # 삭제 후 처리: 현재 뷰가 files 이고 해당 폴더에 더이상 처방이 없으면 상위 폴더로 돌아가기
            if current_view == "files" and current_folder_name:
                if expected_remaining <= 0:
                    # 남아있는 처방이 없으면 상위 뷰로 돌아가기
                    self.current_view = "folders"
                    self.show_folder_view()
                    
                    # 상위 뷰 로드
                    if current_view_level == "item":
                        self.load_folders(is_initial_load=False)
                    else:
                        self.load_folders(is_initial_load=False)
                else:
                    # 남아있는 처방이 있으면 그냥 리프레시
                    self.load_formulations(maintain_position=True)
            else:
                # 폴더 뷰일 경우 그냥 리프레시
                self.load_formulations(maintain_position=True)

        except Exception as e:
            session.rollback()
            messagebox.showerror(self.texts['db_error'], f"{self.texts['delete_error_msg']}: {e}", parent=self)
        finally:
            session.close()
    
    def copy_formulation(self):
        """선택된 처방을 복사하여 새로운 처방으로 생성합니다."""
        if not self._selected_formulation_id:
            messagebox.showwarning("선택 필요", "복사할 처방을 선택하세요.", parent=self)
            return
        
        session = db_manager.get_session()
        try:
            # 원본 처방 조회
            original = session.query(Formulation).options(joinedload(Formulation.items)).filter_by(id=self._selected_formulation_id).first()
            if not original:
                messagebox.showerror("오류", "선택된 처방을 찾을 수 없습니다.", parent=self)
                return
            
            # 새 LAB NO 입력 받기
            from tkinter import simpledialog
            new_lab_no = simpledialog.askstring("처방 복사", 
                                                f"새로운 LAB NO를 입력하세요:\n(원본: {original.lab_no or 'N/A'})",
                                                parent=self)
            if not new_lab_no:
                return  # 취소
            
            new_lab_no = new_lab_no.strip().upper()
            
            # 중복 확인
            existing = session.query(Formulation).filter_by(
                experiment_name=original.experiment_name,
                lab_no=new_lab_no
            ).first()
            if existing:
                messagebox.showerror("오류", f"동일한 실험품명과 LAB NO({new_lab_no})가 이미 존재합니다.", parent=self)
                return
            
            # 새 처방 생성
            new_form = Formulation(
                experiment_name=original.experiment_name,
                lab_no=new_lab_no,
                revision=original.revision,
                manager_name=original.manager_name,
                manager_code=original.manager_code,
                experiment_date=original.experiment_date,
                experiment_ph_initial=original.experiment_ph_initial,
                experiment_ph_next_day=original.experiment_ph_next_day,
                experiment_viscosity_initial=original.experiment_viscosity_initial,
                experiment_viscosity_next_day=original.experiment_viscosity_next_day,
                experiment_machine=original.experiment_machine,
                experiment_comment=original.experiment_comment,
                oem_odm_client_id=original.oem_odm_client_id,
                has_target_info=original.has_target_info,
                target_sample_name=original.target_sample_name,
                target_ph_initial=original.target_ph_initial,
                target_ph_next_day=original.target_ph_next_day,
                target_viscosity_initial=original.target_viscosity_initial,
                target_viscosity_next_day=original.target_viscosity_next_day,
                target_machine=original.target_machine,
                target_client_id=original.target_client_id,
                sample_sent_count=0,  # 샘플 발송 횟수는 0으로 초기화
                change_log=f"[{datetime.now().strftime('%Y-%m-%d %H:%M')}] {original.lab_no}에서 복사됨"
            )
            session.add(new_form)
            session.flush()  # ID 생성
            
            # 아이템 복사
            for item in original.items:
                new_item = FormulationItem(
                    formulation_id=new_form.id,
                    order=item.order,
                    phase=item.phase,
                    material_code=item.material_code,
                    material_name=item.material_name,
                    ratio=item.ratio,
                    amount=item.amount
                )
                session.add(new_item)
            
            session.commit()
            messagebox.showinfo("완료", f"처방이 복사되었습니다.\n새 LAB NO: {new_lab_no}", parent=self)
            self.load_formulations()
            
        except Exception as e:
            session.rollback()
            messagebox.showerror("오류", f"처방 복사 실패: {e}", parent=self)
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

            try:
                center_window_on_mouse_display(dialog)
            except Exception:
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
    def delete_all_formulations(self):
        """
        관리자 전용: 모든 처방 데이터를 삭제합니다.
        WARNING: 복구할 수 없는 작업입니다.
        """
        if not self.current_user.is_admin:
            messagebox.showwarning("권한 오류", "관리자만 사용할 수 있습니다.", parent=self)
            return

        if not messagebox.askyesno("경고", "정말로 모든 처방 데이터를 삭제하시겠습니까?\n이 작업은 되돌릴 수 없습니다.\n\n계속하시겠습니까?", icon='warning', parent=self):
            return
            
        # 한번 더 확인 (안전을 위해)
        if not messagebox.askyesno("최종 확인", "정말 삭제하시겠습니까? 모든 데이터가 사라집니다.", icon='warning', parent=self):
            return

        session = db_manager.get_session()
        try:
            # Formulation 삭제 시 Cascade 설정에 의해 FormulationItem 등도 삭제됨을 가정
            # 만약 Cascade가 없다면 FormulationItem 먼저 삭제 필요
            session.query(FormulationItem).delete()
            session.query(Formulation).delete()
            session.commit()
            messagebox.showinfo(self.texts['success'], "모든 처방 데이터가 삭제되었습니다.")
            
            # UI 갱신
            self.load_folders(is_initial_load=True)
            self.refresh_formulation_filters()
            
        except Exception as e:
            session.rollback()
            messagebox.showerror(self.texts['db_error'], f"삭제 실패: {e}", parent=self)
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

                # 표준 포맷을 찾지 못하면 기존 generic 동작 (Grouping 적용)
                added = 0
                updated = 0
                
                # --- Loose Header Matching Helper (Defined once) ---
                def get_val(r, keys):
                    for k in keys:
                        if k in r and r[k]: return r[k]
                    row_keys_norm = {str(rk).strip(): rk for rk in r.keys()}
                    for k in keys:
                        k_norm = str(k).strip()
                        if k_norm in row_keys_norm and r[row_keys_norm[k_norm]]:
                            return r[row_keys_norm[k_norm]]
                    return None

                for sheet_name, rows in imported.items():
                    # 1. 행들을 제품명/LabNo/차수 기준으로 그룹화
                    groups = {} 
                    last_exp_name = None
                    last_lab_no = None
                    last_revision = None # [추가] 차수 컨텍스트 유지
                    
                    for row in rows:
                        exp_name = get_val(row, ['제품명', '실험품명', 'Experiment Name'])
                        lab_no = get_val(row, ['LAB NO.', 'Lab No', 'LAB_NO'])
                        revision_val = get_val(row, ['차수', 'revision', 'Revision', 'rev']) # [추가]
                        
                        # --- Order (순번) Check for Group Break ---
                        order_val = get_val(row, ['순번', 'no', 'No', 'order', 'Order'])
                        is_new_start = False
                        if order_val:
                            try:
                                if int(float(order_val)) == 1:
                                    is_new_start = True
                            except:
                                pass
                        
                        # 만약 순번이 1이면, 이전 그룹 정보를 이어받지 않도록(Reset) 강제함
                        if is_new_start:
                            last_exp_name = None
                            last_lab_no = None
                            last_revision = None

                        # --- Grouping Logic ---
                        is_ingredient_row = any(get_val(row, [k]) for k in ('원료명', '원료코드', '함량(%)', 'name', 'code', 'ratio'))
                        
                        # 만약 제품명/LabNo가 없고, 순번이 1이 아니며, 원료 행으로 보이면 -> 이전 그룹 이어받기
                        if not exp_name and not lab_no and not revision_val and not is_new_start:
                            # 이름/LabNo/차수가 모두 없으면 이전 컨텍스트를 사용
                            if is_ingredient_row and (last_exp_name or last_lab_no):
                                exp_name = last_exp_name
                                lab_no = last_lab_no
                                revision_val = last_revision
                            else:
                                exp_name = sheet_name
                        
                        # Update Last context
                        if exp_name: last_exp_name = exp_name
                        if lab_no: last_lab_no = lab_no
                        if revision_val: last_revision = revision_val # 차수 업데이트
                        
                        # 중요: 순번 1번인데 이름이 없으면, 임의의 고유 키를 생성해야 섞이지 않음
                        if is_new_start and not exp_name and not lab_no:
                             import uuid
                             exp_name = f"Unknown_{uuid.uuid4().hex[:6]}"
                             last_exp_name = exp_name

                        # [수정] 그룹 키에 revision_val 추가
                        key = (exp_name or sheet_name, lab_no, revision_val)
                        if key not in groups:
                            groups[key] = []
                        groups[key].append(row)
                        
                    # 2. 그룹별로 처방 생성/업데이트 (키 unpacking 수정 필요)
                    for (g_exp_name, g_lab_no, g_revision), g_rows in groups.items():
                        # 그룹의 첫 번째 행에서 대표 정보 추출 (담당자, 날짜 등)
                        # 그룹의 첫 번째 행에서 대표 정보 추출 (담당자, 날짜, 차수 등)
                        first_row = g_rows[0]
                        date_str = get_val(first_row, ['실험일', 'Date'])
                        manager = get_val(first_row, ['담당자', 'manager'])
                        manager_code_val = get_val(first_row, ['담당번호', '담당 번호', 'manager_code', '문서 번호'])
                        comment = get_val(first_row, ['비고', 'remark'])
                        # [추가] 차수(revision)도 추출
                        revision_val = get_val(first_row, ['차수', 'revision', 'Revision', 'rev'])
                        
                        existing = None
                        if g_lab_no:
                            # [수정] Lab No + 제품명 + (차수) 까지 확인하여 엄격하게 분리
                            # 차수가 없으면 None으로 비교
                            query = session.query(Formulation).filter_by(lab_no=str(g_lab_no), experiment_name=g_exp_name)
                            if revision_val:
                                query = query.filter_by(revision=str(revision_val))
                            else:
                                # 차수가 없는 경우: DB에서도 revision이 None이거나 비어있는 것을 찾아야 함
                                # 하지만 기존 데이터에 revision이 없을 수도 있으므로, 이는 '없는 것' 끼리 매칭
                                query = query.filter(or_(Formulation.revision == None, Formulation.revision == ''))
                                
                            existing = query.first()
                            
                        target_f = None
                        if existing:
                            # 기존 처방 업데이트
                            existing.experiment_name = g_exp_name
                            existing.experiment_date = date_str
                            if manager: existing.manager_name = manager
                            if manager_code_val: existing.manager_code = str(manager_code_val).strip().upper()
                            if comment: existing.experiment_comment = comment
                            # 차수는 업데이트 하지 않음 (키로 사용되었으므로)
                            
                            # [수정] 중요: 업데이트 시 기존 원료 항목들은 중복될 수 있으므로 모두 제거 후 다시 추가
                            session.query(FormulationItem).filter_by(formulation_id=existing.id).delete()
                            
                            target_f = existing
                            updated += 1
                        else:
                            newf = Formulation(
                                experiment_name=g_exp_name,
                                experiment_date=date_str,
                                lab_no=str(g_lab_no) if g_lab_no else None,
                                manager_name=manager,
                                manager_code=str(manager_code_val).strip().upper() if manager_code_val is not None else None,
                                experiment_comment=comment,
                                revision=str(revision_val) if revision_val is not None else None
                            )
                            session.add(newf)
                            session.flush() # ID 생성
                            target_f = newf
                            added += 1
                        
                        current_order = 1
                        if existing and existing.items:
                             max_ord = max((i.order for i in existing.items if i.order), default=0)
                             current_order = max_ord + 1

                        for row in g_rows:
                            if not any(get_val(row, [k]) for k in ('원료코드', '원료명', '함량(%)', '코드', 'name', 'ratio')):
                                continue
                                
                            try:
                                fi = FormulationItem(
                                    formulation_id=target_f.id,
                                    material_code=get_val(row, ['원료코드', '코드']),
                                    material_name=get_val(row, ['원료명', 'name']),
                                    ratio=try_convert_to_float(get_val(row, ['함량(%)', '함량', '%', 'ratio']) or 0) or 0,
                                    amount=try_convert_to_float(get_val(row, ['실험량(g)', '중량', 'amount']) or 0) or 0,
                                    phase=get_val(row, ['구분', 'phase']),
                                    order=get_val(row, ['순번', 'order']) or current_order
                                )
                                session.add(fi)
                                current_order += 1
                            except Exception:
                                pass
                        lab_no = get_val(['LAB NO.', 'Lab No', 'LAB_NO'])
                        
                        # --- Order (순번) Check for Group Break ---
                        order_val = get_val(['순번', 'no', 'No', 'order', 'Order'])
                        is_new_start = False
                        if order_val:
                            try:
                                if int(float(order_val)) == 1:
                                    is_new_start = True
                            except:
                                pass
                        
                        # 만약 순번이 1이면, 이전 그룹 정보를 이어받지 않도록(Reset) 강제함
                        if is_new_start:
                            last_exp_name = None
                            last_lab_no = None

                        # --- Grouping Logic ---
                        # 엑셀 병합 셀 등으로 인해 제품명이 비어있고, 바로 윗 행과 연관된 내용(원료 등)인 경우
                        # 제품명을 이어받을지 결정해야 함.
                        
                        is_ingredient_row = any(get_val([k]) for k in ('원료명', '원료코드', '함량(%)', 'name', 'code', 'ratio'))
                        
                        # 만약 제품명/LabNo가 없고, 순번이 1이 아니며, 원료 행으로 보이면 -> 이전 그룹 이어받기
                        if not exp_name and not lab_no and not is_new_start:
                            if is_ingredient_row and (last_exp_name or last_lab_no):
                                exp_name = last_exp_name
                                lab_no = last_lab_no
                            else:
                                # 식별 불가 시 시트명 사용
                                exp_name = sheet_name
                        
                        # Update Last context
                        if exp_name: last_exp_name = exp_name
                        if lab_no: last_lab_no = lab_no
                        
                        # 키 생성 (None은 빈 문자열로 처리하여 통일)
                        # 중요: 순번 1번인데 이름이 없으면, 임의의 고유 키를 생성해야 섞이지 않음
                        if is_new_start and not exp_name and not lab_no:
                             # 임시 이름 생성 (충돌 방지)
                             import uuid
                             exp_name = f"Unknown_{uuid.uuid4().hex[:6]}"
                             last_exp_name = exp_name

                        key = (exp_name or sheet_name, lab_no)
                        if key not in groups:
                            groups[key] = []
                        groups[key].append(row)
                        
                    # 2. 그룹별로 처방 생성/업데이트
                    for (g_exp_name, g_lab_no), g_rows in groups.items():
                        # 그룹의 첫 번째 행에서 대표 정보 추출 (담당자, 날짜 등)
                        first_row = g_rows[0]
                        date_str = get_val(first_row, ['실험일', 'Date'])
                        manager = get_val(first_row, ['담당자', 'manager'])
                        manager_code_val = get_val(first_row, ['담당번호', '담당 번호', 'manager_code', '문서 번호'])
                        comment = get_val(first_row, ['비고', 'remark'])
                        
                        existing = None
                        if g_lab_no:
                            existing = session.query(Formulation).filter_by(lab_no=str(g_lab_no)).first()
                        
                        target_f = None
                        if existing:
                            existing.experiment_name = g_exp_name
                            existing.experiment_date = date_str
                            if manager: existing.manager_name = manager
                            if manager_code_val: existing.manager_code = str(manager_code_val).strip().upper()
                            if comment: existing.experiment_comment = comment
                            target_f = existing
                            updated += 1
                        else:
                            newf = Formulation(
                                experiment_name=g_exp_name,
                                experiment_date=date_str,
                                lab_no=str(g_lab_no) if g_lab_no else None,
                                manager_name=manager,
                                manager_code=str(manager_code_val).strip().upper() if manager_code_val is not None else None,
                                experiment_comment=comment
                            )
                            session.add(newf)
                            session.flush() # ID 생성
                            target_f = newf
                            added += 1
                        
                        current_order = 1
                        if existing and existing.items:
                             max_ord = max((i.order for i in existing.items if i.order), default=0)
                             current_order = max_ord + 1

                        for row in g_rows:
                            if not any(get_val(row, [k]) for k in ('원료코드', '원료명', '함량(%)', '코드', 'name', 'ratio')):
                                continue
                                
                            try:
                                fi = FormulationItem(
                                    formulation_id=target_f.id,
                                    material_code=get_val(row, ['원료코드', '코드']),
                                    material_name=get_val(row, ['원료명', 'name']),
                                    ratio=try_convert_to_float(get_val(row, ['함량(%)', '함량', '%', 'ratio']) or 0) or 0,
                                    amount=try_convert_to_float(get_val(row, ['실험량(g)', '중량', 'amount']) or 0) or 0,
                                    phase=get_val(row, ['구분', 'phase']),
                                    order=get_val(row, ['순번', 'order']) or current_order
                                )
                                session.add(fi)
                                current_order += 1
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
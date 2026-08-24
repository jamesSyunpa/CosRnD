# modules/formulation_popup.py
import customtkinter as ctk
from sqlalchemy.orm import joinedload
from tkinter import ttk, messagebox
from tkcalendar import DateEntry
from database.db_manager import db_manager
from database.models import Client, Formulation, FormulationItem, Material, User
from datetime import datetime
from modules.ui_components import CustomErrorDialog, CustomDropdown, AddMaterialDialog, ClientQuickSearchPopup

# Circular Import 방지: document_management 대신 ui_components에서 직접 import 했습니다.
from modules.ui_components import try_convert_to_float, HelpPopup
from modules.translation import get_texts
from decimal import Decimal, InvalidOperation, getcontext

# 충분히 큰 정밀도 설정 (필요시 더 증가 가능)
getcontext().prec = 80

def to_decimal(value):
    """안전하게 Decimal로 변환. 숫자/문자/None 모두 처리."""
    try:
        if value is None:
            return Decimal('0')
        if isinstance(value, Decimal):
            return value
        # float는 str로 감싸서 부동소수 오차 회피
        return Decimal(str(value))
    except (InvalidOperation, ValueError):
        return Decimal('0')

def decimal_to_str_full(d):
    """
    Decimal을 지수표기 없이 가능한 모든 유효 숫자(내부 digits 및 exponent 포함)로 변환.
    - Decimal.as_tuple()을 이용해 정확한 자릿수까지 출력 (작은 값도 0.000013 등으로 표시)
    - 연산 결과에 따라 trailing zeros가 필요하면 그대로 보여줌.
    """
    d = to_decimal(d)
    # 0 특별 처리
    if d == 0:
        return "0"
    sign, digits, exp = d.as_tuple()
    digits_str = ''.join(str(x) for x in digits) if digits else '0'
    if exp >= 0:
        # 정수(혹은 소수점 오른쪽으로 0 채움)
        s = digits_str + ('0' * exp)
        if sign:
            s = '-' + s
        return s
    # exp < 0: 소수점 위치 계산
    point_index = len(digits_str) + exp  # exp는 음수
    if point_index > 0:
        int_part = digits_str[:point_index]
        frac_part = digits_str[point_index:]
        s = int_part + '.' + frac_part
    else:
        s = '0.' + ('0' * (-point_index)) + digits_str
    if sign:
        s = '-' + s
    return s

def format_decimal_full_with_pct(d):
    """Decimal을 문자열로 변환하고 뒤에 % 붙임 (퍼센트 표현용 유틸)."""
    return decimal_to_str_full(d) + '%'

def compute_actual_wt(ingredient_pct, total_weight, rm_pct=None):
    """
    ingredient_pct: 성분 퍼센트 값(예: 0.001 을 '0.001%'로 취급하는 입력)
    rm_pct: 해당 성분 내 RM 퍼센트 값(없으면 None)
    total_weight: 전체 무게 (예: g)

    반환: (actual_pct_decimal, actual_wt_decimal)
      - actual_pct_decimal: 퍼센트 단위로 계산된 Decimal (사용자 요구대로 퍼센트끼리 곱하면 100으로 나누지 않음)
      - actual_wt_decimal: total_weight * (actual_pct / 100)
    예) ingredient_pct=Decimal('0.001'), rm_pct=Decimal('0.01') => actual_pct=0.00001 (퍼센트), actual_wt = total_weight * 0.00001 / 100
    """
    ing = to_decimal(ingredient_pct)
    tw = to_decimal(total_weight)
    if rm_pct is not None:
        rm = to_decimal(rm_pct)
        actual_pct = ing * rm  # 퍼센트 단위끼리의 곱
    else:
        actual_pct = ing

    # 실제 무게는 퍼센트를 분수로 바꿔 곱함
    actual_wt = tw * (actual_pct / Decimal('100'))
    return actual_pct, actual_wt

# --- 적용 예시 지시 ---
# 아래와 같은 기존 코드 조각들을 찾아 치환하세요.
# 기존 예시 (문제 원인):
# actual_wt = float(total_weight) * (float(ing_pct) / 100.0)
# display_pct = f"{actual_pct:.6f}%"
# display_wt = f"{actual_wt:.6f}"
#
# 변경 예시(치환):
# actual_pct, actual_wt = compute_actual_wt(row['ing_pct'], total_weight_value, row.get('rm_pct'))
# row['ACTUAL_PCT_DISPLAY'] = format_decimal_full_with_pct(actual_pct)    # 예: "0.000013%"
# row['ACTUAL_WT_DISPLAY'] = decimal_to_str_full(actual_wt)               # 예: "0.000013"
#
# 엑셀/CSV/Treeview에 쓸 때도 반드시 decimal_to_str_full 또는 format_decimal_full_with_pct 사용.
#
# 예: worksheet.write(row, col_pct, decimal_to_str_full(actual_pct) + '%')
#     treeview.set(item, 'ACTUAL_WT', decimal_to_str_full(actual_wt))
#
# 또한 기존에 "{:.6f}".format(...) 또는 f"{val:.6f}" 형태로 포맷한 모든 곳을 찾아 위 유틸로 대체해야 합니다.

class FormulationEditPopup(ctk.CTkToplevel):
    """처방 생성 및 수정 팝업 창"""
    def __init__(self, master, user, app, on_save_callback, formulation_id=None):
        super().__init__(master)
        self.master = master
        self.current_user = user
        self.app = app
        self.on_save_callback = on_save_callback
        self.on_save_callback = on_save_callback
        self.formulation_id = formulation_id
        self.is_loading = False # 로딩 중 이벤트 트리거 방지 플래그
        # self.target_client_map = {} # 타겟 거래처 맵 -> 텍스트 입력으로 변경되어 더 이상 필요 없음
        self.sample_sent_count = 0 # 샘플 발송 횟수 저장
        self.formulation_client_map = {} # 본 실험 거래처 맵
        self.edit_entry = None
        self.language = app.language
        self.texts = get_texts(self.language)

        self.title(self.texts['formulation_popup_title'])
        self.transient(master)
        self.resizable(True, True) # 크기 조절 활성화
        # [v64] 처방 생성/수정창 최적 뷰포트 (오른쪽 잘림 완벽 방지)
        self.minsize(1050, 680)
        # [수정] 메인 화면(원료/성분 조회 등)과 번갈아가며 동시 작업을 지원하기 위해 grab_set() 비활성화 (Non-modal)

        try:
            init_w, init_h = 1220, 760
            center_window_on_mouse_display(self, width=init_w, height=init_h)
        except Exception:
            try:
                sw, sh = self.winfo_screenwidth(), self.winfo_screenheight()
                w, h = 1220, 760
                x = max(0, (sw // 2) - (w // 2))
                y = max(0, (sh // 2) - (h // 2))
                self.geometry(f"{w}x{h}+{x}+{y}")
            except Exception:
                pass

        self.setup_ui()
        if formulation_id:
            self.load_formulation_details(formulation_id)
        else:
            self.clear_form()

    def setup_ui(self):
        """팝업 창의 UI를 구성합니다."""
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(0, weight=1)

        # 1. 메인 컨테이너 (상세정보 폼과 처방내용을 담음)
        main_container = ctk.CTkFrame(self, fg_color="transparent")
        main_container.grid(row=0, column=0, sticky="nsew", padx=10, pady=10)
        main_container.grid_columnconfigure(0, weight=5) # 좌측: 처방 상세 정보 (45%)
        main_container.grid_columnconfigure(1, weight=6) # 우측: 처방 내용 (55%로 넓게 확보)
        main_container.grid_rowconfigure(0, weight=1)

        # 2. 좌측: 처방 상세 정보 폼
        form_container_pane = ctk.CTkFrame(main_container, fg_color="transparent")
        form_container_pane.grid(row=0, column=0, sticky="nsew", padx=(0, 5))
        form_container_pane.grid_rowconfigure(0, weight=1)
        form_container_pane.grid_columnconfigure(0, weight=1)
        self.form_pane = ctk.CTkScrollableFrame(form_container_pane, label_text=self.texts['formulation_details'])
        self.form_pane.grid(row=0, column=0, sticky="nsew")

        # 3. 우측: 처방 내용(원료 목록)
        content_pane = ctk.CTkFrame(main_container, fg_color="transparent")
        content_pane.grid(row=0, column=1, sticky="nsew", padx=(5, 0))

        # --- form_pane 내부 UI 구성 ---
        self.form_pane.grid_columnconfigure((1, 3), weight=1)
        # --- 1. 타겟 정보 섹션 (form_pane에 추가) ---
        target_info_frame = ctk.CTkFrame(self.form_pane, fg_color="transparent")
        target_info_frame.grid(row=0, column=0, columnspan=4, padx=10, pady=10, sticky="ew")

        self.target_info_var = ctk.BooleanVar()
        target_info_check = ctk.CTkCheckBox(
            target_info_frame, text=self.texts['use_target_info'], variable=self.target_info_var,
            font=ctk.CTkFont(weight="bold"), command=self.toggle_target_info
        )
        target_info_check.pack(side="top", anchor="w", padx=10, pady=5)

        # 타겟 정보 입력 필드를 담을 프레임
        self.target_fields_frame = ctk.CTkFrame(target_info_frame, fg_color="transparent")
        self.target_fields_frame.pack(fill="x", expand=True, padx=10, pady=5)
        self.target_fields_frame.grid_columnconfigure((1, 3), weight=1)

        # 타겟 샘플명 행
        ctk.CTkLabel(self.target_fields_frame, text=self.texts['target_sample_name']).grid(row=0, column=0, padx=(0, 10), pady=5, sticky="w")
        self.target_sample_name_entry = ctk.CTkEntry(self.target_fields_frame)
        self.target_sample_name_entry.grid(row=0, column=1, columnspan=4, padx=0, pady=5, sticky="ew")

        # 타겟 pH 행
        ctk.CTkLabel(self.target_fields_frame, text=self.texts['target_ph']).grid(row=1, column=0, padx=(0, 10), pady=5, sticky="w")
        ctk.CTkLabel(self.target_fields_frame, text=self.texts['today']).grid(row=1, column=1, padx=(0, 5), pady=5, sticky="e")
        self.target_ph_initial_entry = ctk.CTkEntry(self.target_fields_frame, width=100)
        self.target_ph_initial_entry.grid(row=1, column=2, pady=5, sticky="w")
        ctk.CTkLabel(self.target_fields_frame, text=self.texts['next_day']).grid(row=1, column=3, padx=(10, 5), pady=5, sticky="e")
        self.target_ph_next_day_entry = ctk.CTkEntry(self.target_fields_frame, width=100)
        self.target_ph_next_day_entry.grid(row=1, column=4, pady=5, sticky="w")

        # 타겟 점도 행
        ctk.CTkLabel(self.target_fields_frame, text=self.texts['target_viscosity']).grid(row=2, column=0, padx=(0, 10), pady=5, sticky="w")
        ctk.CTkLabel(self.target_fields_frame, text=self.texts['today']).grid(row=2, column=1, padx=(0, 5), pady=5, sticky="e")
        self.target_viscosity_initial_entry = ctk.CTkEntry(self.target_fields_frame, width=100)
        self.target_viscosity_initial_entry.grid(row=2, column=2, pady=5, sticky="w")
        ctk.CTkLabel(self.target_fields_frame, text=self.texts['next_day']).grid(row=2, column=3, padx=(10, 5), pady=5, sticky="e")
        self.target_viscosity_next_day_entry = ctk.CTkEntry(self.target_fields_frame, width=100)
        self.target_viscosity_next_day_entry.grid(row=2, column=4, pady=5, sticky="w")

        # 사용핀 및 기계 행
        ctk.CTkLabel(self.target_fields_frame, text=self.texts['pin_and_machine']).grid(row=3, column=0, padx=(0, 10), pady=5, sticky="w")
        self.target_machine_entry = ctk.CTkEntry(self.target_fields_frame)
        self.target_machine_entry.grid(row=3, column=1, columnspan=4, padx=0, pady=5, sticky="ew")

        # 타겟 거래처 행
        ctk.CTkLabel(self.target_fields_frame, text=self.texts['target_client']).grid(row=4, column=0, padx=(0, 10), pady=5, sticky="w")
        self.target_client_entry = ctk.CTkEntry(self.target_fields_frame)
        self.target_client_entry.grid(row=4, column=1, columnspan=4, padx=0, pady=5, sticky="ew")

        # --- 구분선-
        separator = ttk.Separator(self.form_pane, orient='horizontal')
        separator.grid(row=1, column=0, columnspan=4, sticky='ew', padx=10, pady=15)


        # --- 2. 본 실험 처방 상세 정보 섹션 (form_pane에 추가) ---
        experiment_info_frame = ctk.CTkFrame(self.form_pane, fg_color="transparent")
        # pady를 조정하여 구분선과의 간격을 맞춥니다.
        experiment_info_frame.grid(row=2, column=0, columnspan=4, padx=10, pady=(0, 10), sticky="ew")
        experiment_info_frame.grid_columnconfigure(0, weight=0, minsize=65)
        experiment_info_frame.grid_columnconfigure(1, weight=1)
        experiment_info_frame.grid_columnconfigure(2, weight=0, minsize=55)
        experiment_info_frame.grid_columnconfigure(3, weight=1)

        # 0행: 실험품명
        ctk.CTkLabel(experiment_info_frame, text="실험품명", font=ctk.CTkFont(weight="bold")).grid(row=0, column=0, padx=(5, 5), pady=5, sticky="w")
        self.exp_name_entry = ctk.CTkEntry(experiment_info_frame)
        self.exp_name_entry.grid(row=0, column=1, columnspan=3, padx=5, pady=5, sticky="ew")
        
        # 1행: 실험일 / 담당자
        ctk.CTkLabel(experiment_info_frame, text="실험일").grid(row=1, column=0, padx=(5, 5), pady=5, sticky="w")
        self.exp_date_entry = DateEntry(experiment_info_frame, date_pattern='yyyy-mm-dd', width=12)
        self.exp_date_entry.grid(row=1, column=1, padx=5, pady=5, sticky="ew")
        self.exp_date_entry.bind("<<DateEntrySelected>>", self.update_lab_no)

        ctk.CTkLabel(experiment_info_frame, text="담당자").grid(row=1, column=2, padx=(10, 5), pady=5, sticky="w")
        self.exp_manager_entry = ctk.CTkEntry(experiment_info_frame)
        self.exp_manager_entry.grid(row=1, column=3, padx=5, pady=5, sticky="ew")
        self.exp_manager_entry.insert(0, self.current_user.username)

        # 2행: 담당번호 / 거래처
        ctk.CTkLabel(experiment_info_frame, text="담당번호").grid(row=2, column=0, padx=(5, 5), pady=5, sticky="w")
        self.exp_code_entry = ctk.CTkEntry(experiment_info_frame)
        self.exp_code_entry.grid(row=2, column=1, padx=5, pady=5, sticky="ew")
        self.exp_code_entry.bind("<KeyRelease>", self.update_lab_no)

        ctk.CTkLabel(experiment_info_frame, text="거래처").grid(row=2, column=2, padx=(10, 5), pady=5, sticky="w")
        
        client_selection_frame = ctk.CTkFrame(experiment_info_frame, fg_color="transparent")
        client_selection_frame.grid(row=2, column=3, padx=5, pady=5, sticky="ew")
        client_selection_frame.grid_columnconfigure(0, weight=1)
        client_selection_frame.grid_columnconfigure(1, weight=3)

        all_client_types = [self.texts['select_type']] + db_manager.get_unique_client_types()
        self.formulation_client_type_combo = CustomDropdown(client_selection_frame, values=all_client_types, width=80, command=self.update_formulation_client_combo)
        self.formulation_client_type_combo.grid(row=0, column=0, padx=(0, 3), sticky="ew")
        self.formulation_client_name_combo = CustomDropdown(client_selection_frame, values=[self.texts['select_client']], command=self.on_client_select, width=130)
        self.formulation_client_name_combo.grid(row=0, column=1, padx=(0, 3), sticky="ew")
        
        # [v65] 거래처 빠른 검색 팝업 버튼 (수천 개 거래처 초고속 검색 & 휠 가속 지원)
        self.client_quick_search_btn = ctk.CTkButton(
            client_selection_frame,
            text="🔍",
            width=28,
            height=28,
            font=ctk.CTkFont(size=12, weight="bold"),
            command=self._open_client_quick_search
        )
        self.client_quick_search_btn.grid(row=0, column=2, sticky="e")

        # 3행: LAB NO. / 차수
        ctk.CTkLabel(experiment_info_frame, text="LAB NO.").grid(row=3, column=0, padx=(5, 5), pady=5, sticky="w")
        self.lab_no_entry = ctk.CTkEntry(experiment_info_frame, state="disabled")
        self.lab_no_entry.grid(row=3, column=1, padx=5, pady=5, sticky="ew")

        ctk.CTkLabel(experiment_info_frame, text="차수").grid(row=3, column=2, padx=(10, 5), pady=5, sticky="w")
        self.revision_entry = ctk.CTkEntry(experiment_info_frame)
        self.revision_entry.grid(row=3, column=3, padx=5, pady=5, sticky="ew")
        self.revision_entry.bind("<KeyRelease>", self.update_lab_no)

        # 4행: 거래처 담당자 정보
        self.client_details_label = ctk.CTkLabel(
            experiment_info_frame, text="", justify="left",
            font=ctk.CTkFont(size=11), text_color="gray"
        )
        self.client_details_label.grid(row=4, column=1, columnspan=3, padx=5, pady=(0, 5), sticky="w")

        # --- 3. 실험 결과 섹션 (form_pane에 추가) ---
        exp_result_frame = ctk.CTkFrame(self.form_pane)
        exp_result_frame.grid(row=3, column=0, columnspan=4, padx=10, pady=(0, 10), sticky="ew")
        exp_result_frame.grid_columnconfigure((2, 4), weight=1)

        ctk.CTkLabel(exp_result_frame, text=self.texts['experiment_results'], font=ctk.CTkFont(weight="bold")).grid(row=0, column=0, columnspan=5, padx=10, pady=(5,10), sticky="w")

        ctk.CTkLabel(exp_result_frame, text=self.texts['ph']).grid(row=1, column=0, padx=10, pady=5, sticky="w")
        ctk.CTkLabel(exp_result_frame, text=self.texts['today']).grid(row=1, column=1, padx=(0, 5), pady=5, sticky="e")
        self.exp_ph_initial_entry = ctk.CTkEntry(exp_result_frame, width=100)
        self.exp_ph_initial_entry.grid(row=1, column=2, pady=5, sticky="w")
        ctk.CTkLabel(exp_result_frame, text=self.texts['next_day']).grid(row=1, column=3, padx=(10, 5), pady=5, sticky="e")
        self.exp_ph_next_day_entry = ctk.CTkEntry(exp_result_frame, width=100)
        self.exp_ph_next_day_entry.grid(row=1, column=4, pady=5, sticky="w")

        ctk.CTkLabel(exp_result_frame, text=self.texts['viscosity']).grid(row=2, column=0, padx=10, pady=5, sticky="w")
        ctk.CTkLabel(exp_result_frame, text=self.texts['today']).grid(row=2, column=1, padx=(0, 5), pady=5, sticky="e")
        self.exp_viscosity_initial_entry = ctk.CTkEntry(exp_result_frame, width=100)
        self.exp_viscosity_initial_entry.grid(row=2, column=2, pady=5, sticky="w")
        ctk.CTkLabel(exp_result_frame, text=self.texts['next_day']).grid(row=2, column=3, padx=(10, 5), pady=5, sticky="e")
        self.exp_viscosity_next_day_entry = ctk.CTkEntry(exp_result_frame, width=100)
        self.exp_viscosity_next_day_entry.grid(row=2, column=4, pady=5, sticky="w")

        ctk.CTkLabel(exp_result_frame, text=self.texts['pin_and_machine']).grid(row=3, column=0, padx=10, pady=5, sticky="w")
        self.exp_machine_entry = ctk.CTkEntry(exp_result_frame)
        self.exp_machine_entry.grid(row=3, column=1, columnspan=4, padx=10, pady=5, sticky="ew")

        # --- 4. 품평결과 및 특이사항 섹션 (form_pane에 추가) ---
        comment_frame = ctk.CTkFrame(self.form_pane)
        comment_frame.grid(row=4, column=0, columnspan=4, padx=10, pady=10, sticky="ew")
        comment_frame.grid_columnconfigure(1, weight=1)
        ctk.CTkLabel(comment_frame, text=self.texts['evaluation_and_notes']).grid(row=0, column=0, padx=10, pady=5, sticky="nw")
        self.exp_comment_textbox = ctk.CTkTextbox(comment_frame, height=100)
        self.exp_comment_textbox.grid(row=0, column=1, padx=10, pady=5, sticky="ew")
        
        # --- 5. 변경 이력 섹션 (form_pane에 추가) ---
        history_frame = ctk.CTkFrame(self.form_pane)
        history_frame.grid(row=5, column=0, columnspan=4, padx=10, pady=10, sticky="ew")
        history_frame.grid_columnconfigure(1, weight=1)
        ctk.CTkLabel(history_frame, text=self.texts['change_history']).grid(row=0, column=0, padx=10, pady=5, sticky="nw")
        self.change_log_textbox = ctk.CTkTextbox(history_frame, height=100, state="disabled", wrap="word")
        self.change_log_textbox.grid(row=0, column=1, padx=10, pady=5, sticky="ew")
        
        # --- content_pane 내부 UI 구성 ---
        content_pane.grid_columnconfigure(0, weight=1)
        content_pane.grid_columnconfigure(1, weight=0) # 스크롤바 전용 열
        content_pane.grid_rowconfigure(1, weight=1)

        # --- [v64] 처방 내용 헤더 툴바 (2단 콤팩트 배치) ---
        content_header = ctk.CTkFrame(content_pane, fg_color=("gray92", "gray18"), corner_radius=6)
        content_header.grid(row=0, column=0, columnspan=2, padx=5, pady=(0, 6), sticky="ew")

        # 1단: 처방 내용 타이틀 / 총 실험량 / 구분 입력
        h_row1 = ctk.CTkFrame(content_header, fg_color="transparent")
        h_row1.pack(fill="x", padx=8, pady=(4, 2))

        ctk.CTkLabel(h_row1, text=f"📋 {self.texts['formulation_content']}", font=ctk.CTkFont(size=13, weight="bold")).pack(side="left", padx=(0, 12))

        ctk.CTkLabel(h_row1, text=f"{self.texts['formulation_item_tree_columns']['phase']}:", font=ctk.CTkFont(size=11, weight="bold")).pack(side="left", padx=(0, 4))
        self.phase_entry = ctk.CTkEntry(h_row1, width=45, height=26, font=ctk.CTkFont(size=11, weight="bold"), justify="center")
        self.phase_entry.pack(side="left", padx=(0, 4))
        self.phase_entry.insert(0, "A")
        self.phase_entry.bind("<KeyRelease>", self.on_phase_entry_changed)
        self.phase_entry.bind("<FocusOut>", self.on_phase_entry_changed)

        self.apply_phase_button = ctk.CTkButton(
            h_row1, text="구분 적용", width=55, height=26,
            font=ctk.CTkFont(size=10), fg_color="gray45", hover_color="gray35",
            command=self.apply_phase_to_selected
        )
        self.apply_phase_button.pack(side="left", padx=(0, 12))

        ctk.CTkLabel(h_row1, text=self.texts['total_experiment_amount_g'], font=ctk.CTkFont(size=11, weight="bold")).pack(side="left", padx=(0, 4))
        self.main_total_amount_entry = ctk.CTkEntry(h_row1, width=80, height=26, justify='right', font=ctk.CTkFont(size=11))
        self.main_total_amount_entry.pack(side="left")
        self.main_total_amount_entry.bind("<Return>", self.calculate_item_amounts)
        self.main_total_amount_entry.bind("<FocusOut>", self.calculate_item_amounts)

        # 2단: 액션 버튼 툴바 (원료추가 / 구분선 / To100 / 위 / 아래 / 삭제)
        h_row2 = ctk.CTkFrame(content_header, fg_color="transparent")
        h_row2.pack(fill="x", padx=8, pady=(2, 4))

        self.add_material_button = ctk.CTkButton(
            h_row2, text=f"➕ {self.texts['add_material']}", width=75, height=26,
            font=ctk.CTkFont(size=11, weight="bold"),
            fg_color="#1565C0", hover_color="#0D47A1",
            command=self.open_add_material_dialog
        )
        self.add_material_button.pack(side="left", padx=2)

        self.add_separator_button = ctk.CTkButton(
            h_row2, text="➖ 구분선", width=65, height=26,
            font=ctk.CTkFont(size=11),
            fg_color="gray45", hover_color="gray35",
            command=self.add_line_break_to_formulation
        )
        self.add_separator_button.pack(side="left", padx=2)

        self.to_100_button = ctk.CTkButton(
            h_row2, text=self.texts['to_100'], width=55, height=26,
            font=ctk.CTkFont(size=11),
            fg_color="#0288D1", hover_color="#01579B",
            command=self.set_ratio_to_100
        )
        self.to_100_button.pack(side="left", padx=2)

        self.move_up_button = ctk.CTkButton(
            h_row2, text="▲ 위로", width=48, height=26,
            font=ctk.CTkFont(size=11),
            fg_color="gray40", hover_color="gray30",
            command=self.move_item_up
        )
        self.move_up_button.pack(side="left", padx=2)

        self.move_down_button = ctk.CTkButton(
            h_row2, text="▼ 아래로", width=52, height=26,
            font=ctk.CTkFont(size=11),
            fg_color="gray40", hover_color="gray30",
            command=self.move_item_down
        )
        self.move_down_button.pack(side="left", padx=2)

        self.delete_item_button = ctk.CTkButton(
            h_row2, text=f"🗑️ {self.texts['delete_selected']}", width=70, height=26,
            font=ctk.CTkFont(size=11),
            fg_color="#C62828", hover_color="#8E0000",
            command=self.delete_selected_item
        )
        self.delete_item_button.pack(side="right", padx=2)

        # --- 처방 내용 Treeview ---
        formulation_item_cols = self.texts['formulation_item_tree_columns']
        # columns 인자에는 딕셔너리의 키 리스트를 명시적으로 전달해야 합니다. (Shift 범위 다중 선택을 위해 extended 적용)
        self.formulation_item_tree = ttk.Treeview(content_pane, columns=list(formulation_item_cols.keys()), show="headings", selectmode="extended")
        self.formulation_item_tree.heading("phase", text=formulation_item_cols['phase']); self.formulation_item_tree.column("phase", width=50, minwidth=40, anchor="center")
        self.formulation_item_tree.heading("code", text=formulation_item_cols['code']); self.formulation_item_tree.column("code", width=85, minwidth=70)
        self.formulation_item_tree.heading("name", text=formulation_item_cols['name']); self.formulation_item_tree.column("name", width=160, minwidth=120, stretch=True)
        self.formulation_item_tree.heading("ratio", text=formulation_item_cols['ratio']); self.formulation_item_tree.column("ratio", width=75, minwidth=65, anchor="e")
        self.formulation_item_tree.heading("amount", text=formulation_item_cols['amount']); self.formulation_item_tree.column("amount", width=75, minwidth=65, anchor="e")
        self.formulation_item_tree.grid(row=1, column=0, padx=(5, 0), pady=(0, 5), sticky="nsew")
        self.formulation_item_tree.bind("<Double-1>", self.edit_item_ratio)
        self.formulation_item_tree.bind("<Button-3>", self.show_tree_context_menu)
        self.formulation_item_tree.bind("<<TreeviewSelect>>", self.on_treeview_selection_change)
        self.formulation_item_tree.bind("<Delete>", lambda e: self.delete_selected_item())
        self.formulation_item_tree.bind("<BackSpace>", lambda e: self.delete_selected_item())
        self.formulation_item_tree.bind("<Up>", self.move_item_up)
        self.formulation_item_tree.bind("<Down>", self.move_item_down)
        self.formulation_item_tree.bind("<Control-Up>", self.move_item_up)
        self.formulation_item_tree.bind("<Control-Down>", self.move_item_down)
        self.formulation_item_tree.bind("<Return>", self.edit_selected_item_ratio)
        self.formulation_item_tree.bind("<F2>", self.edit_selected_item_ratio)

        # --- 처방 내용 Treeview 스크롤바 ---
        tree_scrollbar = ttk.Scrollbar(content_pane, orient="vertical", command=self.formulation_item_tree.yview)
        self.formulation_item_tree.configure(yscrollcommand=tree_scrollbar.set)
        tree_scrollbar.grid(row=1, column=1, sticky="ns", padx=(0, 5), pady=(0, 5))

        self.apply_theme_to_trees()

        # --- 처방 내용 요약 ---
        summary_frame = ctk.CTkFrame(content_pane, fg_color="transparent")
        summary_frame.grid(row=2, column=0, padx=10, pady=5, sticky="e")

        ctk.CTkLabel(summary_frame, text=self.texts['total_ratio_label_short'], font=ctk.CTkFont(weight="bold")).pack(side="left", padx=(10, 2))
        self.total_ratio_label = ctk.CTkLabel(summary_frame, text="0.0000 %", font=ctk.CTkFont(weight="bold"))
        self.total_ratio_label.pack(side="left", padx=(0, 15))

        ctk.CTkLabel(summary_frame, text=self.texts['total_amount_label_short'], font=ctk.CTkFont(weight="bold")).pack(side="left", padx=(10, 2))
        self.total_amount_label = ctk.CTkLabel(summary_frame, text="0.0000 g", font=ctk.CTkFont(weight="bold"))
        self.total_amount_label.pack(side="left", padx=(0, 5))

    def apply_theme_to_trees(self):
        """현재 테마에 맞게 formulation_item_tree의 oddrow / evenrow 배경색을 적용합니다."""
        theme = ctk.get_appearance_mode().lower()
        if theme == 'light':
            odd_bg = "#F9FAFB"
            even_bg = "#FFFFFF"
            tree_fg = "#1F2937"
        else:
            odd_bg = "#282A2E"
            even_bg = "#202124"
            tree_fg = "#E8EAED"

        if hasattr(self, 'formulation_item_tree') and self.formulation_item_tree:
            try:
                self.formulation_item_tree.tag_configure("oddrow", background=odd_bg, foreground=tree_fg)
                self.formulation_item_tree.tag_configure("evenrow", background=even_bg, foreground=tree_fg)
                self.formulation_item_tree.tag_configure("group_odd", background=odd_bg, foreground=tree_fg)
                self.formulation_item_tree.tag_configure("group_even", background=even_bg, foreground=tree_fg)
            except Exception:
                pass

    def reapply_row_striping(self):
        """Treeview의 모든 행 순서에 맞춰 oddrow / evenrow 교차 줄무늬를 100% 재배열합니다."""
        self.apply_theme_to_trees()
        if hasattr(self, 'formulation_item_tree') and self.formulation_item_tree:
            for idx, item_id in enumerate(self.formulation_item_tree.get_children()):
                tag = 'oddrow' if idx % 2 == 0 else 'evenrow'
                try:
                    self.formulation_item_tree.item(item_id, tags=(tag,))
                except Exception:
                    pass

        # --- 하단 버튼 프레임 ---
        bottom_button_frame = ctk.CTkFrame(self, fg_color="transparent")
        bottom_button_frame.grid(row=1, column=0, padx=10, pady=(0, 10), sticky="e")
        
        self.import_button = ctk.CTkButton(bottom_button_frame, text=self.texts['import'], width=100, command=self.import_formulation_from_excel)
        self.import_button.pack(side="left", padx=5)
        self.export_button = ctk.CTkButton(bottom_button_frame, text=self.texts['export'], width=100, command=self.export_formulation_to_excel)
        self.export_button.pack(side="left", padx=5)

        self.save_button = ctk.CTkButton(bottom_button_frame, text=self.texts['save'], width=100, command=self.save_formulation)
        self.save_button.pack(side="left", padx=5)
        self.cancel_button = ctk.CTkButton(bottom_button_frame, text=self.texts['close'], width=100, fg_color="gray50", hover_color="gray35", command=self.destroy)
        self.cancel_button.pack(side="left", padx=5)

        # 초기 상태 설정
        self.toggle_target_info()

    def update_lab_no(self, event=None):
        """고유번호, 실험일, 차수가 모두 있을 때만 LAB NO.를 자동으로 생성합니다."""
        # 로딩 중이거나, 필수 위젯이 아직 생성되지 않았으면 중단
        if getattr(self, 'is_loading', False) or not hasattr(self, 'lab_no_entry'):
            return

        unique_code = self.exp_code_entry.get().strip().upper()
        revision = self.revision_entry.get().strip().upper()
        date_str = ""
        try:
            # DateEntry에서 날짜 객체를 가져옵니다.
            exp_date = self.exp_date_entry.get_date()
            # 'YYMMDD' 형식으로 포맷합니다.
            date_str = exp_date.strftime("%y%m%d")
        except Exception:
            pass # 날짜가 유효하지 않으면 date_str은 빈 문자열
        
        # 모든 필드에 값이 있을 때만 LAB NO. 생성
        if unique_code and date_str and revision:
            lab_no = f"{unique_code}{date_str}{revision}"
        else:
            lab_no = ""

        # LAB NO. 필드를 활성화하여 값을 넣고 다시 비활성화합니다.
        self.lab_no_entry.configure(state="normal")
        self.lab_no_entry.delete(0, "end")
        self.lab_no_entry.insert(0, lab_no)
        self.lab_no_entry.configure(state="disabled")

    def clear_form(self):
        """상세 정보 폼의 모든 입력 필드를 초기화합니다."""
        self.formulation_id = None

        # 타겟 정보
        self.sample_sent_count = 0
        self.target_info_var.set(False)
        self.toggle_target_info()
        self.target_sample_name_entry.delete(0, "end")
        self.target_ph_initial_entry.delete(0, "end")
        self.target_ph_next_day_entry.delete(0, "end")
        self.target_viscosity_initial_entry.delete(0, "end")
        self.target_viscosity_next_day_entry.delete(0, "end")
        self.target_machine_entry.delete(0, "end")
        self.target_client_entry.delete(0, "end")

        # 본 실험 정보
        self.exp_name_entry.delete(0, "end")
        self.exp_date_entry.set_date(datetime.now())
        self.exp_manager_entry.delete(0, "end")
        self.exp_manager_entry.insert(0, self.current_user.username)
        self.exp_code_entry.delete(0, "end")
        self.revision_entry.delete(0, "end")
        self.exp_code_entry.insert(0, self.current_user.manager_code or "") # 현재 사용자의 담당번호 자동 입력

        # 본 실험 결과 정보
        self.exp_ph_initial_entry.delete(0, "end")
        self.exp_ph_next_day_entry.delete(0, "end")
        self.exp_viscosity_initial_entry.delete(0, "end")
        self.exp_viscosity_next_day_entry.delete(0, "end")
        self.exp_machine_entry.delete(0, "end")
        self.exp_comment_textbox.delete("1.0", "end")

        # 변경 이력 초기화
        self.change_log_textbox.configure(state="normal")
        self.change_log_textbox.delete("1.0", "end")
        self.change_log_textbox.configure(state="disabled")
        # 거래처 정보
        self.formulation_client_type_combo.set(self.texts['select_type'])
        self.update_formulation_client_combo(self.texts['select_type'])
        self.client_details_label.configure(text="")

        # 처방 내용 초기화
        for item in self.formulation_item_tree.get_children():
            self.formulation_item_tree.delete(item)
        self.main_total_amount_entry.delete(0, "end")
        self.update_formulation_summary()
        self.update_lab_no() # 폼 초기화 후 LAB NO. 업데이트

    def load_formulation_details(self, formulation_id):
        """특정 처방의 상세 정보를 불러와 폼에 채웁니다."""
        self.is_loading = True # 로딩 시작 (이벤트 억제)
        self.formulation_id = formulation_id
        session = db_manager.get_session()
        try:
            form = session.query(Formulation).options(
                joinedload(Formulation.items)
            ).filter_by(id=formulation_id).first()
            if not form: return

            # 샘플 발송 횟수 로드
            self.sample_sent_count = form.sample_sent_count or 0

            # 타겟 정보
            self.target_info_var.set(form.has_target_info)
            self.toggle_target_info()            
            self.target_sample_name_entry.delete(0, "end"); self.target_sample_name_entry.insert(0, form.target_sample_name or "")
            self.target_ph_initial_entry.delete(0, "end"); self.target_ph_initial_entry.insert(0, form.target_ph_initial or "")
            self.target_ph_next_day_entry.delete(0, "end"); self.target_ph_next_day_entry.insert(0, form.target_ph_next_day or "")
            self.target_viscosity_initial_entry.delete(0, "end"); self.target_viscosity_initial_entry.insert(0, form.target_viscosity_initial or "")
            self.target_viscosity_next_day_entry.delete(0, "end"); self.target_viscosity_next_day_entry.insert(0, form.target_viscosity_next_day or "")
            self.target_machine_entry.delete(0, "end"); self.target_machine_entry.insert(0, form.target_machine or "")
            self.target_client_entry.delete(0, "end"); self.target_client_entry.insert(0, form.target_client_id or "")

            # 본 실험 정보
            self.exp_name_entry.delete(0, "end"); self.exp_name_entry.insert(0, form.experiment_name or "")            
            if form.experiment_date: self.exp_date_entry.set_date(form.experiment_date)
            # 담당자명/담당번호 표시
            self.exp_manager_entry.delete(0, "end"); self.exp_manager_entry.insert(0, form.manager_name or "")
            self.exp_code_entry.delete(0, "end")
            # 우선 DB에 저장된 manager_code를 표시
            if form.manager_code:
                self.exp_code_entry.insert(0, form.manager_code)
            else:
                # DB에 manager_code가 없으면 LAB NO.에서 접두부(영문) 추출 시도
                lab = (form.lab_no or "").strip()
                if lab:
                    import re
                    m = re.match(r'^([A-Za-z]+)', lab)
                    if m:
                        parsed_code = m.group(1).upper()
                        self.exp_code_entry.insert(0, parsed_code)
                        # 사용자 테이블에서 해당 담당번호가 등록되어 있으면 담당자명으로 채움
                        try:
                            user = session.query(User).filter_by(manager_code=parsed_code).first()
                            if user and not (form.manager_name):
                                self.exp_manager_entry.delete(0, "end")
                                # User에는 full name 필드가 없을 수 있어서 username을 기본으로 표시
                                self.exp_manager_entry.insert(0, user.username or "")
                        except Exception:
                            pass
            # 만약 form에는 manager_code가 있지만 manager_name이 비어있고, 등록된 사용자가 있다면 이름 보완
            if form.manager_code and not form.manager_name:
                try:
                    user = session.query(User).filter_by(manager_code=form.manager_code).first()
                    if user:
                        self.exp_manager_entry.delete(0, "end")
                        self.exp_manager_entry.insert(0, user.username or "")
                except Exception:
                    pass

            self.revision_entry.delete(0, "end"); self.revision_entry.insert(0, form.revision or "")

            # 본 실험 결과 정보
            self.exp_ph_initial_entry.delete(0, "end"); self.exp_ph_initial_entry.insert(0, form.experiment_ph_initial or "")            
            self.exp_ph_next_day_entry.delete(0, "end"); self.exp_ph_next_day_entry.insert(0, form.experiment_ph_next_day or "")
            self.exp_viscosity_initial_entry.delete(0, "end"); self.exp_viscosity_initial_entry.insert(0, form.experiment_viscosity_initial or "")
            self.exp_viscosity_next_day_entry.delete(0, "end"); self.exp_viscosity_next_day_entry.insert(0, form.experiment_viscosity_next_day or "")
            self.exp_machine_entry.delete(0, "end"); self.exp_machine_entry.insert(0, form.experiment_machine or "")
            self.exp_comment_textbox.delete("1.0", "end"); self.exp_comment_textbox.insert("1.0", form.experiment_comment or "")

            # 변경 이력 로드
            self.change_log_textbox.configure(state="normal")
            self.change_log_textbox.delete("1.0", "end")
            self.change_log_textbox.insert("1.0", form.change_log or "저장된 변경 이력이 없습니다.")
            self.change_log_textbox.configure(state="disabled")

            # 거래처 정보
            if form.oem_odm_client:
                client = form.oem_odm_client
                self.formulation_client_type_combo.set(client.client_type)
                self.update_formulation_client_combo(client.client_type)
                self.formulation_client_name_combo.set(client.name)
                self.on_client_select(client.name)
            else:
                self.formulation_client_type_combo.set(self.texts['select_type'])
                self.update_formulation_client_combo(self.texts['select_type'])

            # 처방 내용 로드
            for item in self.formulation_item_tree.get_children():
                self.formulation_item_tree.delete(item)
            
            total_amount = Decimal('0')
            # 정렬할 때 order가 None인 항목이 섞여 있어 TypeError가 발생할 수 있음
            # None은 마지막에 오도록 튜플 키로 안전하게 정렬합니다.
            for idx, item in enumerate(sorted(form.items, key=lambda x: (x.order is None, x.order if x.order is not None else 0))):
                tag = 'oddrow' if idx % 2 == 0 else 'evenrow'
                self.formulation_item_tree.insert("", "end", tags=(tag,), values=(
                    item.phase or "",
                    item.material_code or "---",
                    item.material_name or "---",
                    decimal_to_str_full(to_decimal(item.ratio)) if item.ratio is not None else "---",
                    decimal_to_str_full(to_decimal(item.amount)) if item.amount is not None else "---"
                ))
                if item.amount is not None:
                    total_amount += to_decimal(item.amount)
            
            # 총 실험량 필드 업데이트
            self.main_total_amount_entry.delete(0, "end")
            self.main_total_amount_entry.insert(0, decimal_to_str_full(total_amount))

            self.reapply_row_striping()
            self.update_formulation_summary()
            # DB에 저장된 lab_no가 있으면 그것을 우선 표시합니다.
            if form.lab_no:
                try:
                    self.lab_no_entry.configure(state="normal")
                    self.lab_no_entry.delete(0, "end")
                    self.lab_no_entry.insert(0, form.lab_no)
                    self.lab_no_entry.configure(state="disabled")
                except Exception:
                    # 실패 시 기존 동작(생성)으로 폴백
                    self.update_lab_no()
            else:
                # 저장된 값이 없으면 기존 로직대로 자동 생성
                self.is_loading = False # LAB NO 업데이트를 위해 로딩 해제
                self.update_lab_no()
        finally:
            self.is_loading = False # 로딩 종료
            session.close()

    def save_formulation(self):
        """폼 데이터를 DB에 저장 (신규/수정)"""
        # 저장 직전에 LAB NO.를 다시 한번 업데이트하여 최신 상태를 보장합니다.
        self.update_lab_no()

        exp_name = self.exp_name_entry.get().strip()
        if not exp_name:
            messagebox.showwarning(self.texts['input_error'], self.texts['experiment_name_required'], parent=self)
            return

        session = db_manager.get_session()
        try:
            is_new_revision = False
            old_form_items = {}
            if self.formulation_id: # 수정
                form = session.query(Formulation).options(joinedload(Formulation.items)).filter_by(id=self.formulation_id).first()
                # --- 'LAB NO.' 변경 감지 ---
                # DB의 LAB NO.와 현재 폼의 LAB NO.가 다르면 '새 버전으로 저장'으로 간주합니다.
                # 정규화: DB와 입력값을 모두 strip 및 대문자화하여 비교
                current_lab_no_input = self.lab_no_entry.get().strip().upper()
                stored_lab_no = (form.lab_no or "").strip().upper()
                if form and stored_lab_no != current_lab_no_input:
                    is_new_revision = True
                    old_form_items = {item.material_code: item.ratio for item in form.items}
                    self.formulation_id = None # ID를 None으로 만들어 신규 저장 모드로 전환
                    form = Formulation() # 새로운 처방 객체 생성
                    session.add(form)
                    # 디버깅을 위해 담당번호와 LAB NO.를 함께 출력
                    current_code = self.exp_code_entry.get().strip()
                    print(f"LAB NO. 변경 감지: '새 버전으로 저장'을 시작합니다. (담당번호: '{current_code}', LAB NO: '{current_lab_no_input}')")
            else: # 신규
                form = Formulation()
                session.add(form)

            # --- 변경 이력 생성 (새 버전으로 저장 시) ---
            change_log_text = ""
            if is_new_revision:
                new_form_items = {}
                for item_id in self.formulation_item_tree.get_children():
                    values = self.formulation_item_tree.item(item_id, "values")
                    code, ratio_str = values[1], values[3]
                    if code != "---":
                        try:
                            new_form_items[code] = float(ratio_str)
                        except (ValueError, TypeError):
                            continue
                
                log_entries = []
                all_codes = sorted(list(set(old_form_items.keys()) | set(new_form_items.keys())))
                for code in all_codes:
                    old_ratio = old_form_items.get(code)
                    new_ratio = new_form_items.get(code)
                    if old_ratio is None and new_ratio is not None:
                        log_entries.append(f"- {code}: {self.texts['log_added']} ({new_ratio:.4f}%)")
                    elif old_ratio is not None and new_ratio is None:
                        log_entries.append(f"- {code}: {self.texts['log_deleted']}")
                    elif old_ratio is not None and new_ratio is not None and abs(old_ratio - new_ratio) > 1e-9:
                        log_entries.append(f"- {code}: {self.texts['log_ratio_changed']} ({old_ratio:.4f}% -> {new_ratio:.4f}%)")
                if log_entries:
                    # 현재 변경사항만 생성 (누적하지 않음)
                    change_log_text = f"[{datetime.now().strftime('%Y-%m-%d %H:%M')}] {self.texts['log_changes_from_previous']}:\n" + "\n".join(log_entries)

            # --- 데이터 매핑 ---
            # 중복 검사 전에 객체에 데이터를 먼저 채워 autoflush 오류를 방지합니다.
            form.experiment_name = exp_name
            # .get()은 문자열을 반환하므로, 날짜 객체를 반환하는 .get_date()를 사용합니다.
            form.experiment_date = self.exp_date_entry.get_date()

            form.manager_name = self.exp_manager_entry.get().strip() or None
            form.manager_code = self.exp_code_entry.get().strip().upper() or None
            form.revision = self.revision_entry.get().strip().upper() or None
            form.experiment_ph_initial = self.exp_ph_initial_entry.get().strip() or None
            form.experiment_ph_next_day = self.exp_ph_next_day_entry.get().strip() or None
            form.experiment_viscosity_initial = self.exp_viscosity_initial_entry.get().strip() or None
            form.experiment_viscosity_next_day = self.exp_viscosity_next_day_entry.get().strip() or None
            form.experiment_machine = self.exp_machine_entry.get().strip() or None
            form.experiment_comment = self.exp_comment_textbox.get("1.0", "end-1c").strip() or None

            # OEM/ODM 거래처 저장
            client_name = self.formulation_client_name_combo.get()
            if client_name not in [self.texts['select_client'], self.texts['no_clients_found']]:
                form.oem_odm_client_id = self.formulation_client_map.get(client_name)
            else:
                form.oem_odm_client_id = None

            lab_no = self.lab_no_entry.get().strip().upper() or None

            # --- LAB NO. 중복 검사 (저장 전) ---
            # 신규 저장 또는 새 버전으로 저장 시에만 LAB NO. 중복 검사 수행
            if (self.formulation_id is None) and lab_no:
                # is_new_revision이 True일 때도 self.formulation_id가 None이 됨
                existing_form = session.query(Formulation).filter_by(
                    experiment_name=exp_name, 
                    lab_no=lab_no
                ).first()
                if existing_form:
                    messagebox.showerror(self.texts['save_error'], self.texts['lab_no_exists_error'].format(name=exp_name), parent=self)
                    # is_new_revision으로 인해 ID가 None으로 변경된 경우, 원래 ID로 복구하여 창이 닫히지 않게 함
                    if is_new_revision:
                        original_id = session.query(Formulation).filter_by(lab_no=lab_no).first().id
                        if original_id:
                           self.formulation_id = original_id
                    return

            # LAB NO.는 중복 검사 후 최종적으로 할당
            form.lab_no = lab_no

            # 타겟 정보 저장
            form.has_target_info = self.target_info_var.get()            
            if form.has_target_info:
                form.target_sample_name = self.target_sample_name_entry.get().strip() or None
                form.target_ph_initial = self.target_ph_initial_entry.get().strip() or None
                form.target_ph_next_day = self.target_ph_next_day_entry.get().strip() or None
                form.target_viscosity_initial = self.target_viscosity_initial_entry.get().strip() or None
                form.target_viscosity_next_day = self.target_viscosity_next_day_entry.get().strip() or None
                form.target_machine = self.target_machine_entry.get().strip() or None
                form.target_client_id = self.target_client_entry.get().strip() or None
            else:
                form.target_sample_name, form.target_ph_initial, form.target_ph_next_day = None, None, None
                form.target_viscosity_initial, form.target_viscosity_next_day, form.target_machine = None, None, None
                form.target_client_id = None

            # '새 버전으로 저장'이 아닐 경우, 기존의 변경 이력을 그대로 유지합니다.
            if not is_new_revision and self.formulation_id:
                change_log_text = form.change_log

            # 생성된 변경 이력 저장
            form.change_log = change_log_text if change_log_text else None

            # --- 처방 내용(FormulationItem) 저장 ---
            form.items.clear()
            session.flush()

            for i, item_id in enumerate(self.formulation_item_tree.get_children()):
                values = self.formulation_item_tree.item(item_id, "values")
                try:
                    ratio = float(values[3]) if values[3] != "---" else None
                    amount = float(values[4]) if values[4] != "---" else None
                except (ValueError, TypeError):
                    ratio, amount = None, None

                new_item = FormulationItem(
                    order=i, phase=values[0], material_code=values[1],
                    material_name=values[2], ratio=ratio, amount=amount
                )
                form.items.append(new_item)

            session.commit()
            messagebox.showinfo(self.texts['success'], self.texts['formulation_saved_success'], parent=self)
            
            self.on_save_callback() # 부모 창의 목록 새로고침 콜백 호출
            self.destroy() # 팝업 창 닫기

        except Exception as e:
            session.rollback()
            CustomErrorDialog(self, title="데이터베이스 오류", error_message=f"저장 중 오류 발생:\n\n{e}") # noqa
        finally:
            session.close()

    def open_add_material_dialog(self):
        """원료 추가 팝업창을 엽니다."""
        AddMaterialDialog(self, self.add_material_to_formulation, self.add_line_break_to_formulation)

    def add_material_to_formulation(self, material_id):
        """선택된 원료를 처방 내용 Treeview에 추가합니다."""
        session = db_manager.get_session()
        try:
            from database.models import Material
            material = session.query(Material).filter_by(id=material_id).first()
            if material:
                ratio = Decimal('0')
                amount = Decimal('0') # noqa
                phase = self.phase_entry.get().strip().upper() or "A"
                # 태그 추가
                tag = 'oddrow' if len(self.formulation_item_tree.get_children()) % 2 == 0 else 'evenrow'
                self.formulation_item_tree.insert("", "end", tags=(tag,), values=(
                    phase, material.code, material.name, decimal_to_str_full(ratio), decimal_to_str_full(amount)
                ))
        finally:
            session.close()

    def add_materials_from_lookup(self, materials_list):
        """[신규 기능] 원료/성분 조회 및 스마트 매칭에서 선택된 원료들을 신규 처방 개발창에 일괄 자동 추가합니다."""
        if not materials_list:
            return
        
        default_phase = self.phase_entry.get().strip().upper() or "A"
        for mat in materials_list:
            if not mat:
                continue
            ratio = Decimal('0')
            amount = Decimal('0')
            tag = 'oddrow' if len(self.formulation_item_tree.get_children()) % 2 == 0 else 'evenrow'
            self.formulation_item_tree.insert("", "end", tags=(tag,), values=(
                default_phase, mat.code or "-", mat.name or "-", decimal_to_str_full(ratio), decimal_to_str_full(amount)
            ))
        
        self.update_formulation_summary()

    def add_line_break_to_formulation(self):
        """처방 내용에 빈 줄(구분선)을 추가합니다."""
        # 태그 추가
        tag = 'oddrow' if len(self.formulation_item_tree.get_children()) % 2 == 0 else 'evenrow'
        # 구분선에는 phase 값을 비워둡니다.
        self.formulation_item_tree.insert("", "end", tags=(tag,), values=("", "---", "---", "---", "---")) # noqa
        self.update_formulation_summary()

    def delete_selected_item(self):
        """처방 내용 Treeview에서 선택된 모든 항목(Shift 범위 선택 / Ctrl 다중 선택)을 일괄 삭제합니다."""
        selected_items = self.formulation_item_tree.selection()
        if not selected_items:
            messagebox.showwarning(self.texts['selection_error'], self.texts['select_item_to_delete'], parent=self)
            return
        
        # 선택된 모든 항목 일괄 삭제
        for item_id in selected_items:
            try:
                self.formulation_item_tree.delete(item_id)
            except Exception:
                pass

        self.reapply_row_striping()
        self.update_formulation_summary()

    def edit_item_ratio(self, event):
        """Treeview의 셀(구분, 코드, 원료명, 함량)을 더블클릭하여 즉시 수정합니다."""
        if self.edit_entry: 
            try: self.edit_entry.destroy()
            except Exception: pass
            self.edit_entry = None
            
        region = self.formulation_item_tree.identify("region", event.x, event.y)
        column_id = self.formulation_item_tree.identify_column(event.x)
        selected_item = self.formulation_item_tree.focus()
        
        if region == "cell" and selected_item and column_id in ["#1", "#2", "#3", "#4"]:
            self.start_ratio_editing(selected_item, column_id)

    def edit_selected_item_ratio(self, event=None):
        selected_item = self.formulation_item_tree.focus()
        if selected_item: 
            self.start_ratio_editing(selected_item, "#4")

    def start_ratio_editing(self, selected_item, column_id="#4"):
        if not selected_item: return
        item_values = self.formulation_item_tree.item(selected_item, "values")
        if not item_values: return
        if item_values[1] == "---" and column_id not in ["#1"]: return

        bbox = self.formulation_item_tree.bbox(selected_item, column_id)
        if not bbox: return
        x, y, width, height = bbox
        
        # 어떤 컬럼을 편집하는지에 따라 값 가져오기
        col_index = int(column_id.replace('#', '')) - 1
        current_value = str(item_values[col_index]) if col_index < len(item_values) else ""

        justify_mode = 'right' if column_id in ["#4", "#5"] else ('center' if column_id in ["#1", "#2"] else 'left')
        self.edit_entry = ctk.CTkEntry(self.formulation_item_tree, width=width, height=height, justify=justify_mode)
        self.edit_entry.place(x=x, y=y)
        self.edit_entry.insert(0, current_value)
        self.edit_entry.select_range(0, 'end')
        safe_focus(self.edit_entry)
        self.edit_entry.bind("<Return>", lambda e, i=selected_item, c=column_id: self.on_edit_entry_commit(i, c))
        self.edit_entry.bind("<FocusOut>", lambda e, i=selected_item, c=column_id: self.on_edit_entry_commit(i, c))
    
    def on_edit_entry_commit(self, item_id, column_id):
        if not self.edit_entry: return
        try:
            val = self.edit_entry.get().strip()
            current_values = list(self.formulation_item_tree.item(item_id, "values"))
            
            if column_id == "#1": # 구분 (Phase)
                old_phase = str(current_values[0]).strip().upper()
                new_phase = val.upper()
                current_values[0] = new_phase
                self.formulation_item_tree.item(item_id, values=tuple(current_values))
                
                # [연쇄 변경 전파]: 변경된 행 이하에서 동일한 이전 구분을 가진 연속된 행들을 새 구분으로 함께 통일 변경
                all_children = list(self.formulation_item_tree.get_children())
                if item_id in all_children and old_phase:
                    start_idx = all_children.index(item_id)
                    for child_id in all_children[start_idx + 1:]:
                        child_vals = list(self.formulation_item_tree.item(child_id, "values"))
                        if not child_vals:
                            break
                        # 구분선(---)을 만나면 해당 블록 종료
                        if child_vals[1] == "---":
                            break
                        child_phase = str(child_vals[0]).strip().upper()
                        # 이전과 같은 구분을 가지던 하위 항목들만 연속으로 새 구분으로 변경
                        if child_phase == old_phase:
                            child_vals[0] = new_phase
                            self.formulation_item_tree.item(child_id, values=tuple(child_vals))
                        else:
                            # 다른 구분을 만나면 전파 중단
                            break
            elif column_id == "#2": # 원료코드
                current_values[1] = val
            elif column_id == "#3": # 원료명
                current_values[2] = val
            elif column_id == "#4": # 함량 (%)
                new_ratio_dec = to_decimal(val)
                current_values[3] = decimal_to_str_full(new_ratio_dec)
                # amount 재계산
                current_values[4] = self.calculate_single_amount(new_ratio_dec)
            
            if column_id != "#1":
                self.formulation_item_tree.item(item_id, values=tuple(current_values))
        except (InvalidOperation, ValueError, TypeError):
            pass
        finally:
            if self.edit_entry:
                try: self.edit_entry.destroy()
                except Exception: pass
                self.edit_entry = None
            self.update_formulation_summary()

    def on_treeview_selection_change(self, event=None):
        """Treeview에서 선택 항목이 바뀔 때 상단 구분(Phase) 입력창을 해당 항목의 구분값으로 표시"""
        selected_item = self.formulation_item_tree.focus()
        if not selected_item: return
        item_values = self.formulation_item_tree.item(selected_item, "values")
        if item_values and len(item_values) > 0 and item_values[1] != "---":
            current_phase = str(item_values[0]).strip()
            if current_phase:
                self.phase_entry.delete(0, "end")
                self.phase_entry.insert(0, current_phase)

    def on_phase_entry_changed(self, event=None):
        """상단 구분(Phase) 입력창 변경 이벤트 (엔터/구분적용 버튼으로 확정)"""
        pass

    def apply_phase_to_selected(self):
        """구분 적용 버튼 클릭 시: 선택된 항목의 구분을 변경하고, 그 이하의 동일 구분 연속 항목들도 다른 구분을 만나기 전까지 일괄 통일 변경"""
        new_phase = self.phase_entry.get().strip().upper()
        if not new_phase:
            return
            
        selected_item = self.formulation_item_tree.focus()
        if not selected_item:
            # 포커스가 없으면 첫 번째 선택 항목 사용
            sel = self.formulation_item_tree.selection()
            if sel:
                selected_item = sel[0]
            else:
                return

        item_values = list(self.formulation_item_tree.item(selected_item, "values"))
        if not item_values or item_values[1] == "---":
            return

        old_phase = str(item_values[0]).strip().upper()
        item_values[0] = new_phase
        self.formulation_item_tree.item(selected_item, values=tuple(item_values))

        # 변경된 위치 이하로 연속된 동일 구분 항목들(또는 다른 구분/구분선 전까지) 일괄 변경
        all_children = list(self.formulation_item_tree.get_children())
        if selected_item in all_children:
            start_idx = all_children.index(selected_item)
            for child_id in all_children[start_idx + 1:]:
                child_vals = list(self.formulation_item_tree.item(child_id, "values"))
                if not child_vals:
                    break
                # 구분선(---)을 만나면 종료
                if child_vals[1] == "---":
                    break
                child_phase = str(child_vals[0]).strip().upper()
                # 이전과 같은 구분을 가지던 하위 항목들만 연속으로 새 구분으로 변경
                if child_phase == old_phase or not child_phase:
                    child_vals[0] = new_phase
                    self.formulation_item_tree.item(child_id, values=tuple(child_vals))
                else:
                    # 다른 구분을 만나면 즉시 멈춤
                    break

    def show_tree_context_menu(self, event):
        """Treeview 우클릭 시 빠른 조작 팝업 메뉴 표시"""
        item_id = self.formulation_item_tree.identify_row(event.y)
        if item_id:
            self.formulation_item_tree.selection_set(item_id)
            self.formulation_item_tree.focus(item_id)
            self.on_treeview_selection_change()
            
        menu = tk.Menu(self, tearoff=0)
        menu.add_command(label="➕ 원료 추가...", command=self.open_add_material_dialog)
        menu.add_command(label="➖ 구분선 추가", command=self.add_line_break_to_formulation)
        menu.add_separator()
        menu.add_command(label="🏷️ 구분(Phase) 수정 (더블클릭)", command=lambda: self.start_ratio_editing(self.formulation_item_tree.focus(), "#1"))
        menu.add_command(label="✏️ 함량 수정 (F2 / Return)", command=self.edit_selected_item_ratio)
        menu.add_command(label="💯 To 100% 자동 채우기", command=self.set_ratio_to_100)
        menu.add_separator()
        menu.add_command(label="▲ 위로 이동 (Ctrl+Up)", command=self.move_item_up)
        menu.add_command(label="▼ 아래로 이동 (Ctrl+Down)", command=self.move_item_down)
        menu.add_separator()
        menu.add_command(label="🗑️ 선택 항목 삭제 (Delete)", command=self.delete_selected_item)
        try:
            menu.tk_popup(event.x_root, event.y_root)
        finally:
            menu.grab_release()

    def set_ratio_to_100(self):
        selected_item_id = self.formulation_item_tree.focus()
        if not selected_item_id:
            messagebox.showwarning(self.texts['selection_error'], self.texts['select_material_for_to100'], parent=self)
            return
        item_values = self.formulation_item_tree.item(selected_item_id, "values")
        if item_values and item_values[1] == "---":
            messagebox.showwarning(self.texts['selection_error'], self.texts['cannot_apply_to_separator'], parent=self)
            return

        other_ratios_sum = Decimal('0')
        for item_id in self.formulation_item_tree.get_children():
            if item_id == selected_item_id: continue
            values = self.formulation_item_tree.item(item_id, "values")
            if values and values[1] != "---":
                try: other_ratios_sum += to_decimal(values[3])
                except (ValueError, TypeError): continue
        
        new_ratio = Decimal('100.0') - other_ratios_sum
        if new_ratio < Decimal('0'):
            messagebox.showwarning(self.texts['calculation_error'], self.texts['ratio_exceeds_100_warning'], parent=self)
            new_ratio = Decimal('0.0')

        current_values = list(self.formulation_item_tree.item(selected_item_id, "values"))
        current_values[3] = f"{new_ratio:.4f}"
        current_values[4] = self.calculate_single_amount(new_ratio)
        self.formulation_item_tree.item(selected_item_id, values=tuple(current_values))
        self.update_formulation_summary()

    def move_item_up(self, event=None):
        selected_item = self.formulation_item_tree.focus()
        if not selected_item: return
        prev_item = self.formulation_item_tree.prev(selected_item)
        if prev_item:
            self.formulation_item_tree.move(selected_item, "", self.formulation_item_tree.index(prev_item))
            self.formulation_item_tree.focus(selected_item)
            self.formulation_item_tree.selection_set(selected_item) # noqa
            self.reapply_row_striping()
        return 'break'

    def move_item_down(self, event=None):
        selected_item = self.formulation_item_tree.focus()
        if not selected_item: return
        self.formulation_item_tree.move(selected_item, self.formulation_item_tree.parent(selected_item), self.formulation_item_tree.index(selected_item) + 1)
        self.reapply_row_striping()

    def calculate_single_amount(self, ratio) -> str:
        try:
            total_amount = to_decimal(self.main_total_amount_entry.get())
            ratio_dec = to_decimal(ratio)
            amount = (total_amount * ratio_dec) / Decimal('100')
            return decimal_to_str_full(amount)
        except Exception:
            return "0"

    def calculate_item_amounts(self, event=None):
        try:
            total_amount = to_decimal(self.main_total_amount_entry.get())
        except (InvalidOperation, ValueError, TypeError):
            total_amount = Decimal('0')
        for item_id in self.formulation_item_tree.get_children():
            values = list(self.formulation_item_tree.item(item_id, "values"))
            if values and values[1] != "---":
                try:
                    ratio_dec = to_decimal(values[3])
                    amount = (total_amount * ratio_dec) / Decimal('100')
                    values[4] = decimal_to_str_full(amount)
                    self.formulation_item_tree.item(item_id, values=tuple(values))
                except (InvalidOperation, ValueError, TypeError):
                    continue
        self.update_formulation_summary()

    def update_formulation_summary(self):
        total_ratio = Decimal('0')
        total_amount = Decimal('0')
        for item_id in self.formulation_item_tree.get_children():
            values = self.formulation_item_tree.item(item_id, "values")
            if values and values[1] != "---":
                try:
                    total_ratio += to_decimal(values[3])
                    total_amount += to_decimal(values[4])
                except (InvalidOperation, ValueError, TypeError):
                    continue
        self.total_ratio_label.configure(text=f"{decimal_to_str_full(total_ratio)} %")
        self.total_amount_label.configure(text=f"{decimal_to_str_full(total_amount)} g")
        self.reapply_row_striping()

    def toggle_target_info(self):
        if self.target_info_var.get():
            self.target_fields_frame.pack(fill="x", expand=True, padx=10, pady=5)
        else:
            self.target_fields_frame.pack_forget()

    # update_target_client_combo 메서드는 더 이상 필요 없으므로 삭제합니다.

    def update_formulation_client_combo(self, selected_type: str):
        self.formulation_client_name_combo.set(self.texts['select_client'])
        if selected_type == self.texts['select_type']:
            self.formulation_client_name_combo.configure(values=[self.texts['select_client']])
            return
        session = db_manager.get_session()
        try:
            clients = session.query(Client).filter_by(is_active=True, client_type=selected_type).order_by(Client.name).all()
            self.formulation_client_map = {client.name: client.id for client in clients}
            client_names = [client.name for client in clients]
            values = [self.texts['select_client']] + client_names if client_names else [self.texts['no_clients_found']]
            self.formulation_client_name_combo.configure(values=values)
        finally: session.close()

    def on_client_select(self, selected_name: str):
        if selected_name in [self.texts['select_client'], self.texts['no_clients_found']]:
            self.client_details_label.configure(text="")
            return
        client_id = self.formulation_client_map.get(selected_name)
        if not client_id:
            self.client_details_label.configure(text="")
            return
        session = db_manager.get_session()
        try:
            client = session.query(Client).filter_by(id=client_id).first()
            if client:
                details = self.texts['client_details_format'].format(manager=client.manager_name or '-', phone=client.phone or '-')
                self.client_details_label.configure(text=details)
        except Exception as e: print(f"거래처 상세 정보 로드 중 오류: {e}")
        finally: session.close()

    def _open_client_quick_search(self):
        """대량 거래처 고속 검색 및 즉각 선택 팝업 열기"""
        cur_type = self.formulation_client_type_combo.get()
        init_t = cur_type if cur_type != self.texts.get('select_type', '- 선택 -') else None
        ClientQuickSearchPopup(self, self._on_quick_client_selected, initial_type=init_t)

    def _on_quick_client_selected(self, client_name, client_type):
        """빠른 검색 팝업에서 거래처 선택 시 콤보박스 및 담당자 정보 즉시 자동 동기화"""
        if client_type and client_type != self.formulation_client_type_combo.get():
            self.formulation_client_type_combo.set(client_type)
            self.update_formulation_client_combo(client_type)
        
        self.formulation_client_name_combo.set(client_name)
        self.on_client_select(client_name)

    def export_formulation_to_excel(self): # noqa
        # 내보내기 직전에 LAB NO.를 다시 한번 업데이트하여 최신 상태를 보장합니다.
        self.update_lab_no()

        if not self.exp_name_entry.get().strip():
            messagebox.showwarning(self.texts['warning'], self.texts['export_formulation_name_empty'], parent=self)
            return
        formulation_data = {
            "details": {
                "실험품명": self.exp_name_entry.get(), "실험년월일": self.exp_date_entry.get(),
                "담당자": self.exp_manager_entry.get(), "담당번호": self.exp_code_entry.get().upper(),
                "LAB NO.": self.lab_no_entry.get().upper(), "차수": self.revision_entry.get().upper(),
                "거래처": self.formulation_client_name_combo.get(), "총 실험량": self.main_total_amount_entry.get(),
                "pH (당일)": self.exp_ph_initial_entry.get(), "pH (익일)": self.exp_ph_next_day_entry.get(),
                "점도 (당일)": self.exp_viscosity_initial_entry.get(), "점도 (익일)": self.exp_viscosity_next_day_entry.get(),
                "사용핀 및 기계": self.exp_machine_entry.get(),
                "품평결과 및 특이사항": self.exp_comment_textbox.get("1.0", "end-1c"),
            }, "items": []
        }

        # 타겟 정보 사용이 체크된 경우, 타겟 상세 정보 추가
        if self.target_info_var.get():
            formulation_data["target_details"] = {
                "타겟 샘플명": self.target_sample_name_entry.get(),
                "타겟 pH (당일)": self.target_ph_initial_entry.get(),
                "타겟 pH (익일)": self.target_ph_next_day_entry.get(),
                "타겟 점도 (당일)": self.target_viscosity_initial_entry.get(),
                "타겟 점도 (익일)": self.target_viscosity_next_day_entry.get(),
                "사용핀 및 기계": self.target_machine_entry.get(),
                "타겟 거래처": self.target_client_entry.get(), # 이 부분은 엑셀 핸들러와 관련되어 있으므로 유지합니다.
            }

        for item_id in self.formulation_item_tree.get_children():
            values = self.formulation_item_tree.item(item_id, "values")
            formulation_data["items"].append({
                "구분": values[0], "코드": values[1], "원료명": values[2],
                "함량(%)": values[3], "실험량(g)": values[4],
            })
        default_filename = f"lab_{formulation_data['details']['실험품명']}_처방.xlsx"
        
        # --- 파일명 생성 로직 수정 ---
        product_name = formulation_data['details']['실험품명']
        lab_no = formulation_data['details']['LAB NO.']
        
        if self.sample_sent_count > 0:
            default_filename = f"lab_{product_name}_{lab_no}_{self.sample_sent_count:02d}.xlsx"
        else:
            default_filename = f"lab_{product_name}_{lab_no}.xlsx"

        # 내보내기 전 데이터 확인 메시지 창 표시
        details_to_show = formulation_data.get("details", {})
        export_info = (
            f"엑셀 파일로 아래의 데이터를 내보냅니다.\n"
            f"모든 값은 대문자로 변환되어 저장됩니다.\n"
            f"----------------------------------\n"
            f"담당번호: {details_to_show.get('담당번호')}\n"
            f"차수: {details_to_show.get('차수')}\n"
            f"LAB NO.: {details_to_show.get('LAB NO.')}\n"
            f"----------------------------------"
        )
        messagebox.showinfo(self.texts['export_data_confirm_title'], export_info, parent=self)

        excel_handler.export_formulation_template(formulation_data, default_filename)

    def _apply_imported_data_to_ui(self, formulation_data):
        self.is_loading = True # 로딩 시작
        try:
            # '가져오기'는 항상 '신규' 처방으로 처리합니다.
            # 기존에 수정 중이던 ID가 있더라도 이를 무시하고 None으로 설정하여
            # 중복 저장 오류를 방지합니다.
            self.clear_form()
            self.formulation_id = None # ID를 None으로 설정하여 신규 저장 모드로 전환

            details = formulation_data.get("details", {})
            items = formulation_data.get("items", [])
            target_details = formulation_data.get("target_details", {})

            # 가져오기 후 데이터 확인 메시지 창 표시
            import_info = (
                f"엑셀 파일에서 아래의 데이터를 가져왔습니다.\n"
                f"UI에 적용 시 모든 값은 대문자로 변환됩니다.\n"
                f"----------------------------------\n"
                f"담당번호 (또는 문서 번호): {details.get('담당번호') or details.get('문서 번호')}\n"
                f"차수: {details.get('차수')}\n"
                f"LAB NO.: {details.get('LAB NO.')}\n"
                f"----------------------------------"
            )
            messagebox.showinfo(self.texts['import_data_confirm_title'], import_info, parent=self)

            # --- 타겟 정보 적용 ---
            if target_details:
                self.target_info_var.set(True)
                self.toggle_target_info()
                self.target_sample_name_entry.insert(0, target_details.get("타겟 샘플명") or "")
                self.target_ph_initial_entry.insert(0, target_details.get("타겟 pH (당일)") or "")
                self.target_ph_next_day_entry.insert(0, target_details.get("타겟 pH (익일)") or "")
                self.target_viscosity_initial_entry.insert(0, target_details.get("타겟 점도 (당일)") or "")
                self.target_viscosity_next_day_entry.insert(0, target_details.get("타겟 점도 (익일)") or "")
                self.target_machine_entry.insert(0, target_details.get("사용핀 및 기계") or "")
                self.target_client_entry.insert(0, target_details.get("타겟 거래처") or "") # 이 부분은 엑셀 핸들러와 관련되어 있으므로 유지합니다.

            # --- 본 실험 정보 적용 ---
            self.exp_name_entry.insert(0, details.get("실험품명") or "")
            date_str = str(details.get("실험년월일", "")).split(" ")[0]
            if date_str:
                try: self.exp_date_entry.set_date(datetime.strptime(date_str, '%Y-%m-%d'))
                except (ValueError, TypeError):
                    messagebox.showwarning(self.texts['date_format_error'], self.texts['invalid_date_format_warning'].format(date=date_str), parent=self)
                    self.exp_date_entry.set_date(datetime.now())
            else: self.exp_date_entry.set_date(datetime.now())
            self.exp_manager_entry.delete(0, "end")
            self.exp_manager_entry.insert(0, details.get("담당자", self.current_user.username) or self.current_user.username) # 담당자가 없으면 현재 사용자
            # '담당번호' 또는 이전 형식인 '문서 번호' 키를 모두 확인하여 값을 가져옵니다.
            manager_code = details.get("담당번호") or details.get("문서 번호") or ""
            # clear_form에 의해 자동 입력된 값을 지우고 엑셀의 값으로 덮어씁니다.
            self.exp_code_entry.delete(0, "end")
            self.exp_code_entry.insert(0, str(manager_code).upper())
            
            revision = details.get("차수") or ""
            self.revision_entry.insert(0, str(revision).upper())
            
            self.main_total_amount_entry.insert(0, details.get("총 실험량") or "")
            
            # LAB NO.는 자동 생성 로직보다 엑셀 값을 우선 적용
            lab_no = details.get("LAB NO.") or ""

            self.exp_ph_initial_entry.insert(0, details.get("pH (당일)") or "")
            self.exp_ph_next_day_entry.insert(0, details.get("pH (익일)") or "")
            self.exp_viscosity_initial_entry.insert(0, details.get("점도 (당일)") or "")
            self.exp_viscosity_next_day_entry.insert(0, details.get("점도 (익일)") or "")
            self.exp_machine_entry.insert(0, details.get("사용핀 및 기계") or "")
            self.exp_comment_textbox.insert("1.0", details.get("품평결과 및 특이사항") or "")
            
            client_name = details.get("거래처", self.texts['select_client'])
            if client_name and client_name != self.texts['select_client']:
                session = db_manager.get_session()
                client = session.query(Client).filter_by(name=client_name).first()
                session.close()
                if client:
                    self.formulation_client_type_combo.set(client.client_type)
                    self.update_formulation_client_combo(client.client_type)
                    self.formulation_client_name_combo.set(client.name)
                else:
                    messagebox.showwarning(self.texts['client_error'], self.texts['client_not_found_warning'].format(name=client_name), parent=self)
                    self.formulation_client_type_combo.set(self.texts['select_type'])
                    self.update_formulation_client_combo(self.texts['select_type'])

            # 총 실험량 값을 먼저 가져옵니다.
            try:
                total_amount = to_decimal(details.get("총 실험량", 0.0))
            except (ValueError, TypeError):
                total_amount = Decimal('0')

            for item in items:
                # 기존 try_convert_to_float 유지하되 Decimal로 변환하여 포맷
                ratio_val = try_convert_to_float(item.get("함량(%)", "0"))
                ratio_dec = to_decimal(ratio_val)
                ratio_str = decimal_to_str_full(ratio_dec)

                # 총 실험량과 함량을 기반으로 실험량을 다시 계산합니다.
                if total_amount > Decimal('0'):
                    amount_val = (total_amount * ratio_dec) / Decimal('100')
                    amount_str = decimal_to_str_full(amount_val)
                else:
                    amount_str = "0"

                self.formulation_item_tree.insert("", "end", values=(
                    item.get("구분") or "", item.get("코드") or "", item.get("원료명") or "",
                    ratio_str, amount_str
                ))
            
            self.update_formulation_summary()
            
            # LAB NO. 처리: 엑셀에 값이 있으면 그 값을 사용, 없으면 자동 생성
            # 단, 담당번호가 비어있으면 엑셀의 LAB NO.를 무시하고 자동 생성 로직을 다시 실행합니다.
            if lab_no and manager_code: # manager_code가 비어있지 않은 모든 경우를 참으로 처리
                self.lab_no_entry.configure(state="normal"); self.lab_no_entry.delete(0, "end"); self.lab_no_entry.insert(0, str(lab_no).upper()); self.lab_no_entry.configure(state="disabled")
            else:
                self.update_lab_no() # 엑셀에 LAB NO.가 없으면 자동 생성

            messagebox.showinfo(self.texts['success'], self.texts['formulation_import_success'], parent=self)
        except Exception as e:
            CustomErrorDialog(self, title="가져오기 오류", error_message=f"데이터를 적용하는 중 오류가 발생했습니다:\n\n{e}") # noqa
        finally:
            self.is_loading = False # 로딩 종료
            # 마지막으로 LAB NO 업데이트 (필요시)
            try: self.update_lab_no()
            except Exception: pass

    def import_formulation_from_excel(self):
        if not messagebox.askyesno(self.texts['import_confirm'], self.texts['import_formulation_confirm_msg'], parent=self):
            return
        formulation_data = excel_handler.import_formulation_template()
        if formulation_data:
            self._apply_imported_data_to_ui(formulation_data)

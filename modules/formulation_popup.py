# modules/formulation_popup.py
import customtkinter as ctk
from sqlalchemy.orm import joinedload
from tkinter import ttk, messagebox
from tkcalendar import DateEntry
from database.db_manager import db_manager
from database.models import Client, Formulation, FormulationItem, Material, User
from datetime import datetime
import time
from modules import excel_handler
from modules.ui_components import CustomErrorDialog

# document_management.py에서 클래스들을 가져옵니다.
from modules.ui_components import CustomDropdown, AddMaterialDialog
from modules.ui_components import try_convert_to_float, HelpPopup
from utils import center_window_on_mouse_display, safe_focus
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

# 안전한 DateEntry 래퍼: Babel locale-data 누락 시에도 크래시 없이 동작
class SafeDateEntry:
    """tkcalendar.DateEntry 사용 시 Babel locale-data 누락으로 인한 크래시를 방지하는 안전 래퍼.

    - 정상 환경: 내부적으로 tkcalendar.DateEntry 위젯을 생성하여 그대로 위임합니다.
    - 폴백 환경: CTkEntry로 대체하고 get_date/set_date 등의 최소 인터페이스를 제공합니다.
    """
    def __init__(self, master, **kwargs):
        self._is_fallback = False
        self._master = master
        # tkcalendar가 존재하더라도 Babel locale-data가 누락되면 생성 시점에 예외가 발생합니다.
        try:
            self._widget = DateEntry(master, **kwargs)
        except Exception:
            # 폴백: 일반 입력 상자 사용, 기본값은 오늘 날짜(YYYY-MM-DD)
            self._is_fallback = True
            width = kwargs.get('width', 120)
            self._widget = ctk.CTkEntry(master, width=width)
            try:
                self._widget.insert(0, datetime.now().strftime('%Y-%m-%d'))
            except Exception:
                pass

    # --- Tk geometry/event delegation ---
    def grid(self, *args, **kwargs):
        return self._widget.grid(*args, **kwargs)

    def pack(self, *args, **kwargs):
        return self._widget.pack(*args, **kwargs)

    def place(self, *args, **kwargs):
        return self._widget.place(*args, **kwargs)

    def bind(self, *args, **kwargs):
        # DateEntry 이벤트 바인딩을 최대한 그대로 위임
        if hasattr(self._widget, 'bind'):
            # DateEntry 전용 가상 이벤트를 폴백 위젯에서 근접 동작으로 매핑
            if self._is_fallback and args and isinstance(args[0], str) and args[0] == "<<DateEntrySelected>>":
                callback = args[1] if len(args) > 1 else kwargs.get('func')
                res1 = self._widget.bind('<FocusOut>', callback)
                res2 = self._widget.bind('<Return>', callback)
                return (res1, res2)
            return self._widget.bind(*args, **kwargs)
        return None

    def configure(self, *args, **kwargs):
        if hasattr(self._widget, 'configure'):
            return self._widget.configure(*args, **kwargs)
        return None

    # --- API compatibility ---
    def set_date(self, value):
        if self._is_fallback:
            try:
                # datetime 또는 문자열 모두 허용
                if hasattr(value, 'strftime'):
                    s = value.strftime('%Y-%m-%d')
                else:
                    s = str(value)
                self._widget.delete(0, 'end')
                self._widget.insert(0, s)
            except Exception:
                pass
            return None
        # 정상 DateEntry라면 원래 메서드 사용
        try:
            return self._widget.set_date(value)
        except Exception:
            return None

    def get_date(self):
        if self._is_fallback:
            try:
                s = self._widget.get()
                # 형식이 다를 수 있으니 유연하게 처리
                for fmt in ('%Y-%m-%d', '%Y/%m/%d', '%y-%m-%d', '%y/%m/%d'):
                    try:
                        return datetime.strptime(s, fmt)
                    except Exception:
                        continue
            except Exception:
                pass
            # 파싱 실패 시 오늘로 대체
            return datetime.now()
        try:
            return self._widget.get_date()
        except Exception:
            return datetime.now()

    def get(self):
        try:
            return self._widget.get()
        except Exception:
            return ''

    # 기타 속성/메서드는 내부 위젯에 위임
    def __getattr__(self, name):
        return getattr(self._widget, name)

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
        self.formulation_id = formulation_id
        # self.target_client_map = {} # 타겟 거래처 맵 -> 텍스트 입력으로 변경되어 더 이상 필요 없음
        self.sample_sent_count = 0 # 샘플 발송 횟수 저장
        self.formulation_client_map = {} # 본 실험 거래처 맵
        self.edit_entry = None
        self.language = app.language
        self.texts = get_texts(self.language)
        
        # 세션 만료 방지를 위한 새로고침 타이머
        self.refresh_timer = None
        self.last_activity_time = time.time()
        self.data_loading = False  # 데이터 로딩 중 플래그

        self.title(self.texts['formulation_popup_title'])
        # 창 크기: 적절한 크기로 축소 조정
        self.geometry("1280x760")
        # self.transient(master)  # 최대화 버튼을 활성화하기 위해 transient 제거
        self.resizable(True, True) # 크기 조절 및 최대화 버튼 활성화
        self.minsize(800, 600)
        
        # 메인 팝업 레이아웃 가중치 추가
        self.grid_rowconfigure(0, weight=1)
        self.grid_columnconfigure(0, weight=1)
        
        # 창 크기 정보 출력
        self.after(100, lambda: print(f"[WINDOW SIZE] {self.title()} | geometry: {self.winfo_width()}x{self.winfo_height()} | requested: 1280x760"))

        # UI 구성
        self.setup_ui()
        
        # UI 생성 후 창 크기 강제 설정
        self.update_idletasks()
        self.geometry("1280x760")
        self.update()
        
        # 데이터 로딩 (UI 구성 완료 후 지연 실행)
        if formulation_id:
            self.after(100, lambda: self.load_formulation_details(formulation_id))
        else:
            # 신규 처방 생성시 즉시 폼 초기화 (지연 없이)
            self.clear_form()
            
        # 주기적 데이터 새로고침 시작 (5분마다)
        self.start_refresh_timer()
        # 창 중앙 배치 (메인 창 기준)
        try:
            self.center_on_parent()
        except Exception:
            pass
            
        # 창이 열릴 때 맨 앞으로 띄우고 강제로 포커스를 설정합니다 (grab_set은 미사용하므로 다른 창과 전환 가능)
        self.lift()
        self.focus_force()
        self.after(100, lambda: (self.lift(), self.focus_force()))
    
    def center_on_parent(self):
        """팝업 창을 부모(메인) 창의 중앙에 배치합니다."""
        self.update_idletasks()
        parent = self.master
        if parent:
            # 부모 창의 화면상 절대 위치와 크기
            parent_x = parent.winfo_rootx()
            parent_y = parent.winfo_rooty()
            parent_w = parent.winfo_width()
            parent_h = parent.winfo_height()
            
            # 현재 창의 크기
            win_w = self.winfo_width()
            win_h = self.winfo_height()
            
            # 부모 창 중앙 계산
            x = parent_x + (parent_w - win_w) // 2
            y = parent_y + (parent_h - win_h) // 2
            
            self.geometry(f"+{x}+{y}")

    def setup_ui(self):
        """팝업 창의 UI를 구성합니다."""
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(0, weight=1)
        
        # 안전한 Entry 텍스트 입력 헬퍼 (index, text 두 인자 강제)
        # - None -> "" 처리
        # - 예외 발생 시 무시하고 기본값 유지
        def _safe_insert(entry_widget, value, index=0):
            try:
                text = "" if value is None else str(value)
                entry_widget.insert(index, text)
            except Exception as _e:
                # 디버깅을 돕기 위한 콘솔 로그만 남기고 동작은 계속
                print(f"Entry.safe_insert 오류: {entry_widget} -> {value} ({_e})")
        # 인스턴스 메서드로 노출
        self.safe_insert = _safe_insert

        # 1. 메인 컨테이너 (상세정보 폼과 처방내용을 담음)
        main_container = ctk.CTkFrame(self, fg_color="transparent")
        main_container.grid(row=0, column=0, sticky="nsew", padx=10, pady=(10, 0))
        
        # Column 0(상세정보)은 픽셀 기반 강제 제어를 위해 weight=0으로 두고 초기 너비는 약 61%인 768px로 설정
        # Column 2(처방내용)는 남은 화면 전체를 채우도록 weight=1로 설정
        main_container.grid_columnconfigure(0, weight=0, minsize=768) # 좌측: 처방 상세 정보
        main_container.grid_columnconfigure(1, weight=0)  # 중간: 스플리터 조절 바
        main_container.grid_columnconfigure(2, weight=1)  # 우측: 처방 내용
        main_container.grid_rowconfigure(0, weight=1)

        # 팝업 루트의 grid 가중치 설정: 0번 행(메인 컨테이너)은 크기가 늘어나며, 1번 행(하단 버튼 프레임)은 고정 높이
        self.grid_rowconfigure(0, weight=1)
        self.grid_rowconfigure(1, weight=0)
        self.grid_columnconfigure(0, weight=1)

        # 2. 좌측: 처방 상세 정보 폼
        form_container_pane = ctk.CTkFrame(main_container, fg_color="transparent")
        form_container_pane.grid(row=0, column=0, sticky="nsew", padx=(0, 2))
        form_container_pane.grid_rowconfigure(0, weight=1)
        form_container_pane.grid_columnconfigure(0, weight=1)
        self.form_pane = ctk.CTkScrollableFrame(form_container_pane, label_text=self.texts['formulation_details'])
        self.form_pane.grid(row=0, column=0, sticky="nsew")

        # 2.5 중간: 마우스 드래그로 폭을 조절하는 스플리터 바 추가
        drag_bar = ctk.CTkFrame(main_container, width=6, fg_color="#555555", corner_radius=0)
        drag_bar.grid(row=0, column=1, sticky="ns", padx=1)
        
        # 커서 변경
        drag_bar.bind("<Enter>", lambda e: drag_bar.configure(cursor="size_we"))
        drag_bar.bind("<Leave>", lambda e: drag_bar.configure(cursor=""))
        
        # 드래그 동작 정의 (마우스 포인터의 x좌표와 좌측 영역의 가로 픽셀을 1:1로 일치시킴)
        def on_splitter_drag(event):
            container_x = event.x_root - main_container.winfo_rootx()
            total_width = main_container.winfo_width()
            
            # 최소 너비 300px, 최대 너비는 (전체 너비 - 250px)로 제한하여 UI 깨짐 방지
            if total_width > 550:
                min_w = 300
                max_w = total_width - 250
                target_w = max(min_w, min(container_x, max_w))
                main_container.grid_columnconfigure(0, minsize=target_w)
                    
        drag_bar.bind("<B1-Motion>", on_splitter_drag)

        # 3. 우측: 처방 내용(원료 목록)
        content_pane = ctk.CTkFrame(main_container)
        content_pane.grid(row=0, column=2, sticky="nsew", padx=(2, 0))



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
        experiment_info_frame.grid_columnconfigure(1, weight=1)
        experiment_info_frame.grid_columnconfigure(3, weight=1)

        ctk.CTkLabel(experiment_info_frame, text=self.texts['experiment_name'], font=ctk.CTkFont(weight="bold")).grid(row=0, column=0, padx=10, pady=5, sticky="w")
        self.exp_name_entry = ctk.CTkEntry(experiment_info_frame)
        self.exp_name_entry.grid(row=0, column=1, columnspan=3, padx=10, pady=5, sticky="ew")
        
        ctk.CTkLabel(experiment_info_frame, text=self.texts['experiment_date']).grid(row=1, column=0, padx=10, pady=5, sticky="w")
        # tkcalendar의 Babel locale-data 누락 시에도 안전하게 동작하도록 래퍼 사용
        self.exp_date_entry = SafeDateEntry(experiment_info_frame, date_pattern='yyyy-mm-dd', width=15)
        self.exp_date_entry.grid(row=1, column=1, padx=10, pady=5, sticky="w")
        self.exp_date_entry.bind("<<DateEntrySelected>>", self.update_lab_no)

        ctk.CTkLabel(experiment_info_frame, text=self.texts['manager_name']).grid(row=1, column=2, padx=10, pady=5, sticky="w")
        self.exp_manager_entry = ctk.CTkEntry(experiment_info_frame, width=90)
        self.exp_manager_entry.grid(row=1, column=3, padx=10, pady=5, sticky="ew")
        # 기본값으로 현재 사용자 설정 (안전 래퍼 사용)
        self.safe_insert(self.exp_manager_entry, self.current_user.real_name or self.current_user.username)

        ctk.CTkLabel(experiment_info_frame, text=self.texts['manager_code']).grid(row=2, column=0, padx=10, pady=5, sticky="w")
        self.exp_code_entry = ctk.CTkEntry(experiment_info_frame, width=90, state="disabled")
        self.exp_code_entry.grid(row=2, column=1, padx=10, pady=5, sticky="ew")

        ctk.CTkLabel(experiment_info_frame, text=self.texts['lab_no']).grid(row=3, column=0, padx=10, pady=5, sticky="w")
        self.lab_no_entry = ctk.CTkEntry(experiment_info_frame, state="disabled") # 읽기 전용으로 설정
        self.lab_no_entry.grid(row=3, column=1, padx=10, pady=5, sticky="ew")

        ctk.CTkLabel(experiment_info_frame, text=self.texts['revision']).grid(row=3, column=2, padx=10, pady=5, sticky="w")
        self.revision_entry = ctk.CTkEntry(experiment_info_frame, width=90)
        self.revision_entry.grid(row=3, column=3, padx=10, pady=5, sticky="ew")
        self.revision_entry.bind("<KeyRelease>", self.update_lab_no)

        # --- OEM/ODM 거래처 선택 ---
        ctk.CTkLabel(experiment_info_frame, text=self.texts['client']).grid(row=2, column=2, padx=10, pady=5, sticky="w")
        
        client_selection_frame = ctk.CTkFrame(experiment_info_frame, fg_color="transparent")
        client_selection_frame.grid(row=2, column=3, padx=10, pady=5, sticky="ew")
        client_selection_frame.grid_columnconfigure(1, weight=1)

        all_client_types = [self.texts['select_type']] + db_manager.get_unique_client_types()
        self.formulation_client_type_combo = CustomDropdown(client_selection_frame, values=all_client_types, width=120, command=self.update_formulation_client_combo)
        self.formulation_client_type_combo.grid(row=0, column=0, padx=(0, 5), sticky="ew")
        self.formulation_client_name_combo = CustomDropdown(client_selection_frame, values=[self.texts['select_client']], command=self.on_client_select, width=180)
        self.formulation_client_name_combo.grid(row=0, column=1, sticky="ew")

        # 선택된 거래처의 상세 정보를 표시할 라벨
        self.client_details_label = ctk.CTkLabel(
            experiment_info_frame, text="", justify="left",
            font=ctk.CTkFont(size=11), text_color="gray"
        )
        self.client_details_label.grid(row=4, column=3, padx=10, pady=(0, 5), sticky="w")

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
        content_pane.grid_columnconfigure(1, weight=0) # scrollbar column
        content_pane.grid_rowconfigure(1, weight=1)

        # --- 처방 내용 헤더 (버튼 등) (content_pane에 추가) ---
        content_header = ctk.CTkFrame(content_pane, fg_color="transparent")
        content_header.grid(row=0, column=0, columnspan=2, padx=10, pady=10, sticky="ew")
        
        ctk.CTkLabel(content_header, text=self.texts['formulation_content'], font=ctk.CTkFont(size=14, weight="bold")).pack(side="left", padx=(0, 8))

        # 총 실험량 입력 필드를 헤더로 이동
        total_amount_header_frame = ctk.CTkFrame(content_header, fg_color="transparent")
        total_amount_header_frame.pack(side="left", padx=(5, 10))
        ctk.CTkLabel(total_amount_header_frame, text=self.texts['total_experiment_amount_g'], font=ctk.CTkFont(weight="bold")).pack(side="left", padx=(0, 5))
        self.main_total_amount_entry = ctk.CTkEntry(total_amount_header_frame, width=100, justify='right')
        self.main_total_amount_entry.pack(side="left")
        self.main_total_amount_entry.bind("<Return>", self.calculate_item_amounts)
        self.main_total_amount_entry.bind("<FocusOut>", self.calculate_item_amounts)

        content_buttons = ctk.CTkFrame(content_header, fg_color="transparent")
        content_buttons.pack(side="right")
        btn_font = ctk.CTkFont(size=11)
        self.add_material_button = ctk.CTkButton(content_buttons, text=self.texts['add_material'], width=75, font=btn_font, command=self.open_add_material_dialog)
        self.add_material_button.pack(side="left", padx=2)
        self.to_100_button = ctk.CTkButton(content_buttons, text=self.texts['to_100'], width=65, font=btn_font, command=self.set_ratio_to_100)
        self.to_100_button.pack(side="left", padx=2)
        self.move_up_button = ctk.CTkButton(content_buttons, text="▲", width=30, font=btn_font, command=self.move_item_up)
        self.move_up_button.pack(side="left", padx=(4, 1))
        self.move_down_button = ctk.CTkButton(content_buttons, text="▼", width=30, font=btn_font, command=self.move_item_down)
        self.move_down_button.pack(side="left", padx=(1, 4))
        self.sort_by_phase_button = ctk.CTkButton(content_buttons, text="구분순 정렬", width=75, font=btn_font, command=self.sort_items_by_phase)
        self.sort_by_phase_button.pack(side="left", padx=2)
        self.delete_item_button = ctk.CTkButton(content_buttons, text=self.texts['delete_selected'], width=75, font=btn_font, fg_color="#D32F2F", hover_color="#B71C1C", command=self.delete_selected_item)
        self.delete_item_button.pack(side="left", padx=2)

        # --- 처방 내용 Treeview ---
        formulation_item_cols = self.texts['formulation_item_tree_columns']
        # columns 인자에는 딕셔너리의 키 리스트를 명시적으로 전달해야 합니다.
        self.formulation_item_tree = ttk.Treeview(content_pane, columns=list(formulation_item_cols.keys()), show="headings", selectmode="browse")
        self.formulation_item_tree.heading("phase", text=formulation_item_cols['phase']); self.formulation_item_tree.column("phase", width=80, anchor="center")
        self.formulation_item_tree.heading("code", text=formulation_item_cols['code']); self.formulation_item_tree.column("code", width=100)
        self.formulation_item_tree.heading("name", text=formulation_item_cols['name']); self.formulation_item_tree.column("name", width=150, stretch=True)
        self.formulation_item_tree.heading("ratio", text=formulation_item_cols['ratio']); self.formulation_item_tree.column("ratio", width=80, anchor="e")
        self.formulation_item_tree.heading("amount", text=formulation_item_cols['amount']); self.formulation_item_tree.column("amount", width=80, anchor="e")
        self.formulation_item_tree.grid(row=1, column=0, padx=10, pady=(0, 5), sticky="nsew")
        self.formulation_item_tree.bind("<Double-1>", self.on_treeview_double_click)
        self.formulation_item_tree.bind("<Up>", self.move_item_up)
        self.formulation_item_tree.bind("<Down>", self.move_item_down)
        self.formulation_item_tree.bind("<Control-Up>", self.move_item_up)
        self.formulation_item_tree.bind("<Return>", self.edit_selected_item_ratio)
        self.formulation_item_tree.bind("<Control-Down>", self.move_item_down)
        
        # 드래그 앤 드롭 기능 추가
        self.drag_data = {"item": None, "index": None}
        self.formulation_item_tree.bind("<ButtonPress-1>", self.on_drag_start)
        self.formulation_item_tree.bind("<B1-Motion>", self.on_drag_motion)
        self.formulation_item_tree.bind("<ButtonRelease-1>", self.on_drag_release)

        # --- 처방 내용 Treeview 스크롤바 ---
        tree_scrollbar = ttk.Scrollbar(content_pane, orient="vertical", command=self.formulation_item_tree.yview) # content_pane을 부모로 사용
        self.formulation_item_tree.configure(yscrollcommand=tree_scrollbar.set)
        tree_scrollbar.grid(row=1, column=1, sticky="ns")
        
        # --- 처방 내용 안내 메시지 (Treeview가 비어있을 때 표시용) ---
        self.empty_message_label = ctk.CTkLabel(
            content_pane, 
            text="'원료 추가' 버튼을 클릭하여 처방에 원료를 추가하세요.",
            text_color="gray",
            font=ctk.CTkFont(size=12)
        )
        # 초기에는 숨김 (처방 로드 후에 결정)


        # --- 처방 내용 요약 ---
        summary_frame = ctk.CTkFrame(content_pane, fg_color="transparent")
        summary_frame.grid(row=2, column=0, columnspan=2, padx=10, pady=5, sticky="e")

        ctk.CTkLabel(summary_frame, text=self.texts['total_ratio_label_short'], font=ctk.CTkFont(weight="bold")).pack(side="left", padx=(10, 2))
        self.total_ratio_label = ctk.CTkLabel(summary_frame, text="0.0000 %", font=ctk.CTkFont(weight="bold"))
        self.total_ratio_label.pack(side="left", padx=(0, 15))

        ctk.CTkLabel(summary_frame, text=self.texts['total_amount_label_short'], font=ctk.CTkFont(weight="bold")).pack(side="left", padx=(10, 2))
        self.total_amount_label = ctk.CTkLabel(summary_frame, text="0.0000 g", font=ctk.CTkFont(weight="bold"))
        self.total_amount_label.pack(side="left", padx=(0, 5))

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
        
        # 사용자 활동 감지를 위한 이벤트 바인딩
        self.bind_activity_events()

    def bind_activity_events(self):
        """사용자 활동 감지를 위한 이벤트를 바인딩합니다"""
        try:
            # 마우스 및 키보드 활동 감지
            self.bind("<Button-1>", self.on_user_activity)
            self.bind("<Key>", self.on_user_activity)
            self.bind("<Motion>", self.on_user_activity)
            
            # 주요 입력 위젯들에 개별적으로 이벤트 바인딩
            widgets_to_bind = [
                self.exp_name_entry, self.exp_manager_entry, self.exp_code_entry,
                self.target_sample_name_entry, self.target_client_entry
            ]
            
            for widget in widgets_to_bind:
                if hasattr(widget, 'bind'):
                    widget.bind("<KeyPress>", self.on_user_activity)
                    widget.bind("<Button-1>", self.on_user_activity)
                    
        except Exception as e:
            print(f"이벤트 바인딩 중 오류: {e}")



    def update_lab_no(self, event=None):
        """고유번호, 실험일, 차수가 모두 있을 때만 LAB NO.를 자동으로 생성합니다."""
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
        self.safe_insert(self.exp_manager_entry, self.current_user.real_name or self.current_user.username)
        self.revision_entry.delete(0, "end")
        # 현재 사용자의 담당번호 자동 입력 (속성이 없을 수 있으므로 안전하게 접근)
        manager_code = getattr(self.current_user, 'manager_code', "")
        # Disable된 entry에 값을 넣으려면 잠시 enable 시켜야 함
        self.exp_code_entry.configure(state="normal")
        self.exp_code_entry.delete(0, "end")
        self.safe_insert(self.exp_code_entry, manager_code)
        self.exp_code_entry.configure(state="disabled")
        self.update_lab_no()

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
        
        # 안내 메시지 표시 (처방 내용이 비어있으므로)
        self.empty_message_label.grid(row=2, column=0, columnspan=2, padx=10, pady=10)
        self.update_lab_no() # 폼 초기화 후 LAB NO. 업데이트

    def load_formulation_details(self, formulation_id):
        """특정 처방의 상세 정보를 불러와 폼에 채웁니다."""
        if self.data_loading:
            print("이미 데이터 로딩 중입니다.")
            return
            
        self.data_loading = True
        self.formulation_id = formulation_id
        session = db_manager.get_session()
        
        try:
            form = session.query(Formulation).options(
                joinedload(Formulation.items),
                joinedload(Formulation.oem_odm_client)
            ).filter_by(id=formulation_id).first()
            
            if not form: 
                print(f"처방 ID {formulation_id}를 찾을 수 없습니다.")
                self.data_loading = False
                return

            print(f"처방 데이터 로딩 시작: {form.experiment_name}")

            # 먼저 모든 기본 필드들을 클리어
            self.clear_form_fields()
            
            # 샘플 발송 횟수 로드
            self.sample_sent_count = form.sample_sent_count or 0

            # 타겟 정보 로드
            has_target = form.has_target_info if form.has_target_info is not None else False
            self.target_info_var.set(has_target)
            self.toggle_target_info()
            
            # 타겟 정보 필드들 설정
            if form.target_sample_name:
                self.target_sample_name_entry.insert(0, str(form.target_sample_name))
            if form.target_ph_initial:
                self.target_ph_initial_entry.insert(0, str(form.target_ph_initial))
            if form.target_ph_next_day:
                self.target_ph_next_day_entry.insert(0, str(form.target_ph_next_day))
            if form.target_viscosity_initial:
                self.target_viscosity_initial_entry.insert(0, str(form.target_viscosity_initial))
            if form.target_viscosity_next_day:
                self.target_viscosity_next_day_entry.insert(0, str(form.target_viscosity_next_day))
            if form.target_machine:
                self.target_machine_entry.insert(0, str(form.target_machine))
            if form.target_client_id:
                self.target_client_entry.insert(0, str(form.target_client_id))

            # 본 실험 정보 로드
            if form.experiment_name:
                self.exp_name_entry.insert(0, str(form.experiment_name))
                
            if form.experiment_date:
                self.exp_date_entry.set_date(form.experiment_date)
                
            # 담당자명 로드
            if form.manager_name:
                self.exp_manager_entry.insert(0, str(form.manager_name))
            else:
                self.exp_manager_entry.insert(0, self.current_user.real_name or self.current_user.username)
                
            # 담당번호 로드 및 처리
            manager_code = self.get_manager_code_from_form(form, session)
            if manager_code:
                self.exp_code_entry.configure(state="normal")
                self.exp_code_entry.insert(0, str(manager_code))
                self.exp_code_entry.configure(state="disabled")
                
            # 차수 로드
            if form.revision:
                self.revision_entry.insert(0, str(form.revision))
                
            # LAB NO. 업데이트
            self.update_lab_no()

            # 본 실험 결과 정보 로드
            if form.experiment_ph_initial:
                self.exp_ph_initial_entry.insert(0, str(form.experiment_ph_initial))
            if form.experiment_ph_next_day:
                self.exp_ph_next_day_entry.insert(0, str(form.experiment_ph_next_day))
            if form.experiment_viscosity_initial:
                self.exp_viscosity_initial_entry.insert(0, str(form.experiment_viscosity_initial))
            if form.experiment_viscosity_next_day:
                self.exp_viscosity_next_day_entry.insert(0, str(form.experiment_viscosity_next_day))
            if form.experiment_machine:
                self.exp_machine_entry.insert(0, str(form.experiment_machine))
            if form.experiment_comment:
                self.exp_comment_textbox.insert("1.0", str(form.experiment_comment))

            # 변경 이력 로드
            self.load_change_log(form)

            # 거래처 정보 로드 (즉시 처리, 지연 없이)
            if form.oem_odm_client:
                self.load_client_info(form.oem_odm_client)
            else:
                self.formulation_client_type_combo.set(self.texts['select_type'])
                self.update_formulation_client_combo(self.texts['select_type'])

            # 처방 내용 로드
            self.load_formulation_items(form)

            # LAB NO. 설정
            self.set_lab_no(form)
                
            print("처방 데이터 로딩 완료")
            
        except Exception as e:
            print(f"처방 데이터 로딩 중 오류: {e}")
            import traceback
            traceback.print_exc()
        finally:
            session.close()
            self.data_loading = False
            # UI 업데이트 강제
            self.update_idletasks()
            
    def clear_form_fields(self):
        """폼의 모든 필드를 클리어합니다 (clear_form과 달리 기본값 설정 안함)"""
        # 타겟 정보 클리어
        self.target_sample_name_entry.delete(0, "end")
        self.target_ph_initial_entry.delete(0, "end")
        self.target_ph_next_day_entry.delete(0, "end")
        self.target_viscosity_initial_entry.delete(0, "end")
        self.target_viscosity_next_day_entry.delete(0, "end")
        self.target_machine_entry.delete(0, "end")
        self.target_client_entry.delete(0, "end")
        
        # 본 실험 정보 클리어
        self.exp_name_entry.delete(0, "end")
        self.exp_manager_entry.delete(0, "end")
        self.revision_entry.delete(0, "end")
        
        # 실험 결과 클리어
        self.exp_ph_initial_entry.delete(0, "end")
        self.exp_ph_next_day_entry.delete(0, "end")
        self.exp_viscosity_initial_entry.delete(0, "end")
        self.exp_viscosity_next_day_entry.delete(0, "end")
        self.exp_machine_entry.delete(0, "end")
        self.exp_comment_textbox.delete("1.0", "end")
        
        # 총 실험량 클리어
        self.main_total_amount_entry.delete(0, "end")
            
    def get_manager_code_from_form(self, form, session):
        """폼에서 담당번호를 추출합니다"""
        if form.manager_code:
            return form.manager_code
        else:
            # DB에 manager_code가 없으면 LAB NO.에서 접두부(영문) 추출 시도
            lab = (form.lab_no or "").strip()
            if lab:
                import re
                m = re.match(r'^([A-Za-z]+)', lab)
                if m:
                    parsed_code = m.group(1).upper()
                    # 사용자 테이블에서 해당 담당번호가 등록되어 있으면 담당자명도 업데이트
                    try:
                        user = session.query(User).filter_by(manager_code=parsed_code).first()
                        if user and not form.manager_name:
                            # 담당자명이 없으면 업데이트
                            self.exp_manager_entry.delete(0, "end")
                            self.exp_manager_entry.insert(0, user.username or "")
                    except Exception as e:
                        print(f"사용자 정보 조회 오류: {e}")
                    return parsed_code
            else:
                # LAB NO.도 없으면 현재 사용자의 manager_code 사용
                if hasattr(self.current_user, 'manager_code') and self.current_user.manager_code:
                    return self.current_user.manager_code
        return None
    
    def get_manager_display_name(self, manager_value):
        """담당자 필드의 값을 표시용 이름으로 변환합니다"""
        if not manager_value or not manager_value.strip():
            return self.current_user.real_name or self.current_user.username or ""
        
        manager_value = manager_value.strip()
        
        # 숫자로만 이루어진 경우 사용자 ID로 판단하여 이름으로 변환
        if manager_value.isdigit():
            session = db_manager.get_session()
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
            finally:
                session.close()
        
        # 이미 이름인 경우 그대로 반환
        return manager_value
        
    def load_change_log(self, form):
        """변경 이력을 로드합니다"""
        self.change_log_textbox.configure(state="normal")
        self.change_log_textbox.delete("1.0", "end")
        if form.change_log:
            self.change_log_textbox.insert("1.0", str(form.change_log))
        else:
            self.change_log_textbox.insert("1.0", "저장된 변경 이력이 없습니다.")
        self.change_log_textbox.configure(state="disabled")
        
    def load_client_info(self, client):
        """거래처 정보를 로드합니다"""
        try:
            # 거래처 타입 설정
            self.formulation_client_type_combo.set(client.client_type)
            # 거래처 목록 업데이트
            self.update_formulation_client_combo(client.client_type)
            # UI 업데이트 적용
            self.update_idletasks()
            # 거래처명 설정
            self.formulation_client_name_combo.set(client.name)
            self.on_client_select(client.name)
            print(f"거래처 정보 로드 완료: {client.name}")
        except Exception as e:
            print(f"거래처 정보 로드 오류: {e}")
            import traceback
            traceback.print_exc()
            
    def load_formulation_items(self, form):
        """처방 아이템들을 로드합니다"""
        # 기존 아이템들 삭제
        for item in self.formulation_item_tree.get_children():
            self.formulation_item_tree.delete(item)
        
        if form.items:
            print(f"처방 아이템 {len(form.items)}개 로딩 중...")
            total_amount = Decimal('0')
            
            # 정렬: order 필드로만 정렬 (저장 시 순서대로 order가 부여되므로)
            # phase로 정렬하면 줄내림(phase="")이 맨 뒤로 밀려나는 문제 발생
            def _to_int_safe(v, default=10**9):
                try:
                    if v is None:
                        return default
                    # "12", 12, "12.0" 등 처리
                    s = str(v).strip()
                    if s == "":
                        return default
                    # 소수로 들어오면 버림
                    return int(float(s))
                except Exception:
                    return default

            def sort_key(item):
                return _to_int_safe(getattr(item, 'order', None))
            
            sorted_items = sorted(form.items, key=sort_key)
            
            for item in sorted_items:
                phase = str(item.phase) if item.phase else ""
                material_code = str(item.material_code) if item.material_code else "---"
                material_name = str(item.material_name) if item.material_name else "---"
                
                # 줄내림 체크: material_code가 "---"이면 줄내림으로 처리
                is_separator = material_code.strip() in ["---", "-", "--", "―", "ㅡ"]
                
                if is_separator:
                    # 줄내림인 경우 비율과 양을 빈 문자열로
                    ratio_str = ""
                    amount_str = ""
                else:
                    # 일반 원료인 경우
                    if item.ratio is not None:
                        ratio_str = decimal_to_str_full(to_decimal(item.ratio))
                    else:
                        ratio_str = "0"
                        
                    if item.amount is not None:
                        amount_str = decimal_to_str_full(to_decimal(item.amount))
                        total_amount += to_decimal(item.amount)
                    else:
                        amount_str = "0"
                
                self.formulation_item_tree.insert("", "end", values=(
                    phase, material_code, material_name, ratio_str, amount_str
                ))
                
            print(f"처방 아이템 로딩 완료. 총량: {total_amount}")
            
            # 총 실험량 필드 업데이트
            if total_amount > 0:
                self.main_total_amount_entry.insert(0, decimal_to_str_full(total_amount))
                
            # 안내 메시지 숨기기 (아이템이 있으므로)
            self.empty_message_label.grid_remove()
        else:
            print("처방 아이템이 없습니다.")
            # 안내 메시지 표시 (아이템이 없으므로)
            self.empty_message_label.grid(row=2, column=0, columnspan=2, padx=10, pady=10)
            
        # 요약 정보 업데이트
        self.update_formulation_summary()
        
    def set_lab_no(self, form):
        """LAB NO.를 설정합니다"""
        if form.lab_no:
            try:
                self.lab_no_entry.configure(state="normal")
                self.lab_no_entry.delete(0, "end")
                self.lab_no_entry.insert(0, str(form.lab_no))
                self.lab_no_entry.configure(state="disabled")
                print(f"LAB NO. 설정 완료: {form.lab_no}")
            except Exception as e:
                print(f"LAB NO. 설정 오류: {e}")
                self.update_lab_no()
        else:
            # 저장된 값이 없으면 기존 로직대로 자동 생성
            self.update_lab_no()
            


    def save_formulation(self):
        """폼 데이터를 DB에 저장 (신규/수정)"""
        # 저장 직전에 LAB NO.를 다시 한번 업데이트하여 최신 상태를 보장합니다.
        self.update_lab_no()

        exp_name = self.exp_name_entry.get().strip()
        if not exp_name:
            messagebox.showwarning(self.texts['input_error'], self.texts['experiment_name_required'], parent=self)
            return

        manager_code = self.exp_code_entry.get().strip()
        if not manager_code:
            messagebox.showwarning(self.texts['input_error'], "담당번호는 필수 입력 항목입니다. 회원 정보에서 담당번호를 설정하거나 관리자에게 문의하세요.", parent=self)
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
                    # 이전 메타 스냅샷 저장 (변경 이력에 '변경된 항목만' 기록하기 위함)
                    try:
                        prev_meta = {
                            'manager_name': form.manager_name or "",
                            'experiment_date': form.experiment_date or "",
                            'experiment_ph_initial': form.experiment_ph_initial or "",
                            'experiment_ph_next_day': form.experiment_ph_next_day or "",
                            'experiment_viscosity_initial': form.experiment_viscosity_initial or "",
                            'experiment_viscosity_next_day': form.experiment_viscosity_next_day or "",
                            'experiment_machine': form.experiment_machine or "",
                            'sample_sent_count': int(form.sample_sent_count or 0),
                            'sample_delivery_date': form.sample_delivery_date.strftime('%Y-%m-%d') if getattr(form, 'sample_delivery_date', None) else "",
                            'oem_odm_client_name': (form.oem_odm_client.name if getattr(form, 'oem_odm_client', None) else ""),
                            'target_client_id': form.target_client_id or "",
                        }
                    except Exception:
                        prev_meta = None
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
                # 1) 메타 필드 변경 비교 (폴더 이력과 동일 철학: 변경된 항목만 기록)
                try:
                    # 현재 메타 스냅샷을 UI에서 수집
                    def _date_to_str(d):
                        try:
                            return d.strftime('%Y-%m-%d')
                        except Exception:
                            return str(d) if d else ""

                    current_client_name = self.formulation_client_name_combo.get()
                    if current_client_name in [self.texts['select_client'], self.texts['no_clients_found']]:
                        current_client_name = ""

                    curr_meta = {
                        'manager_name': (self.exp_manager_entry.get() or "").strip(),
                        'experiment_date': _date_to_str(self.exp_date_entry.get_date()),
                        'experiment_ph_initial': (self.exp_ph_initial_entry.get() or "").strip(),
                        'experiment_ph_next_day': (self.exp_ph_next_day_entry.get() or "").strip(),
                        'experiment_viscosity_initial': (self.exp_viscosity_initial_entry.get() or "").strip(),
                        'experiment_viscosity_next_day': (self.exp_viscosity_next_day_entry.get() or "").strip(),
                        'experiment_machine': (self.exp_machine_entry.get() or "").strip(),
                        'sample_sent_count': int(self.sample_sent_count or 0),
                        'sample_delivery_date': "",  # 입력 위젯 부재로 현재는 공란 유지
                        'oem_odm_client_name': current_client_name,
                        'target_client_id': (self.target_client_entry.get() or "").strip(),
                    }

                    def _add_change(label, old, new):
                        old_s = "" if old is None else str(old)
                        new_s = "" if new is None else str(new)
                        if old_s != new_s:
                            log_entries.append(f"- {label}: {old_s or '-'} → {new_s or '-'}")

                    if 'prev_meta' in locals() and prev_meta is not None:
                        _add_change('담당자', prev_meta.get('manager_name'), curr_meta.get('manager_name'))
                        _add_change('실험일', prev_meta.get('experiment_date'), curr_meta.get('experiment_date'))
                        _add_change('pH(초기)', prev_meta.get('experiment_ph_initial'), curr_meta.get('experiment_ph_initial'))
                        _add_change('pH(익일)', prev_meta.get('experiment_ph_next_day'), curr_meta.get('experiment_ph_next_day'))
                        _add_change('점도(초기)', prev_meta.get('experiment_viscosity_initial'), curr_meta.get('experiment_viscosity_initial'))
                        _add_change('점도(익일)', prev_meta.get('experiment_viscosity_next_day'), curr_meta.get('experiment_viscosity_next_day'))
                        _add_change('Pin', prev_meta.get('experiment_machine'), curr_meta.get('experiment_machine'))
                        _add_change('샘플발송 횟수', prev_meta.get('sample_sent_count'), curr_meta.get('sample_sent_count'))
                        _add_change('샘플발송일', prev_meta.get('sample_delivery_date'), curr_meta.get('sample_delivery_date'))
                        _add_change('OEM/ODM 거래처', prev_meta.get('oem_odm_client_name'), curr_meta.get('oem_odm_client_name'))
                        _add_change('타겟 거래처', prev_meta.get('target_client_id'), curr_meta.get('target_client_id'))
                except Exception:
                    pass
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

            # 샘플 발송 횟수 저장
            form.sample_sent_count = self.sample_sent_count

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
                    ratio = to_decimal(values[3]) if values[3] not in ("---", "") else None
                    amount = to_decimal(values[4]) if values[4] not in ("---", "") else None
                except (InvalidOperation, ValueError, TypeError):
                    ratio, amount = None, None

                new_item = FormulationItem(
                    order=i, phase=values[0], material_code=values[1],
                    material_name=values[2], ratio=ratio, amount=amount
                )
                form.items.append(new_item)

            session.commit()
            
            # 디버깅: 저장된 처방 정보 출력
            print(f"[처방 저장] 실험품명: {form.experiment_name}, LAB NO: {form.lab_no}, 차수: {form.revision}, ID: {form.id}, 생성일: {form.created_at}")
            
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
                amount = Decimal('0')
                # 태그 추가
                tag = 'oddrow' if len(self.formulation_item_tree.get_children()) % 2 == 0 else 'evenrow'
                
                # 선택된 아이템이 있으면 그 위에, 없으면 맨 끝에 추가
                selected_item = self.formulation_item_tree.focus()
                if selected_item:
                    # 선택된 아이템의 인덱스를 가져와서 그 위에 삽입
                    index = self.formulation_item_tree.index(selected_item)
                    self.formulation_item_tree.insert("", index, tags=(tag,), values=(
                        "", material.code, material.name, decimal_to_str_full(ratio), decimal_to_str_full(amount)
                    ))
                else:
                    # 선택된 항목이 없으면 맨 끝에 추가
                    self.formulation_item_tree.insert("", "end", tags=(tag,), values=(
                        "", material.code, material.name, decimal_to_str_full(ratio), decimal_to_str_full(amount)
                    ))
                
                self.update_phase_numbers()
                # 안내 메시지 숨기기 (아이템이 추가되었으므로)
                self.empty_message_label.grid_remove()
        finally:
            session.close()

    def add_line_break_to_formulation(self):
        """처방 내용에 빈 줄(구분선)을 추가합니다."""
        # 선택된 아이템이 있으면 그 위에, 없으면 맨 끝에 추가
        selected_item = self.formulation_item_tree.focus()
        tag = 'oddrow' if len(self.formulation_item_tree.get_children()) % 2 == 0 else 'evenrow'
        
        if selected_item:
            # 선택된 아이템의 인덱스를 가져와서 그 위에 삽입
            index = self.formulation_item_tree.index(selected_item)
            self.formulation_item_tree.insert("", index, tags=(tag,), values=("", "---", "---", "---", "---"))
        else:
            # 선택된 항목이 없으면 맨 끝에 추가
            self.formulation_item_tree.insert("", "end", tags=(tag,), values=("", "---", "---", "---", "---"))
        
        self.update_phase_numbers()
        # 안내 메시지 숨기기 (아이템이 추가되었으므로)
        self.empty_message_label.grid_remove()

    def delete_selected_item(self):
        """처방 내용 Treeview에서 선택된 항목을 삭제합니다."""
        selected_item = self.formulation_item_tree.selection()
        if not selected_item:
            messagebox.showwarning(self.texts['selection_error'], self.texts['select_item_to_delete'], parent=self)
            return
        self.formulation_item_tree.delete(selected_item)
        self.update_phase_numbers()
        
        # 모든 아이템이 삭제되었는지 확인하고 안내 메시지 표시
        if not self.formulation_item_tree.get_children():
            self.empty_message_label.grid(row=2, column=0, columnspan=2, padx=10, pady=10)

    def on_treeview_double_click(self, event):
        """Treeview 더블클릭 - Phase 또는 함량 셀 편집"""
        if self.edit_entry:
            self.edit_entry.destroy()
        
        region = self.formulation_item_tree.identify("region", event.x, event.y)
        if region != "cell":
            return
        
        column = self.formulation_item_tree.identify_column(event.x)
        selected_item = self.formulation_item_tree.focus()
        
        if not selected_item:
            return
        
        # Phase 컬럼 (#1) 편집
        if column == "#1":
            self.start_phase_editing(selected_item, column)
        # 함량 컬럼 (#4) 편집
        elif column == "#4":
            self.start_ratio_editing(selected_item, column)
    
    def start_phase_editing(self, selected_item, column_id):
        """Phase 셀 편집 시작"""
        if not selected_item:
            return
        
        item_values = self.formulation_item_tree.item(selected_item, "values")
        if item_values and item_values[1] == "---":  # 구분선은 편집 불가
            return
        
        if self.edit_entry:
            self.edit_entry.destroy()
        
        x, y, width, height = self.formulation_item_tree.bbox(selected_item, column_id)
        current_value = self.formulation_item_tree.item(selected_item, "values")[0]
        
        self.edit_entry = ctk.CTkEntry(self.formulation_item_tree, width=width, height=height, justify='center')
        self.edit_entry.place(x=x, y=y)
        self.edit_entry.insert(0, current_value)
        self.edit_entry.select_range(0, 'end')
        safe_focus(self.edit_entry)
        self.edit_entry.bind("<Return>", lambda e: self.on_phase_edit_commit(selected_item))
        self.edit_entry.bind("<FocusOut>", lambda e: self.on_phase_edit_commit(selected_item))
    
    def on_phase_edit_commit(self, item_id):
        """Phase 편집 완료 - 값 저장 및 재정렬"""
        if not self.edit_entry:
            return
        
        try:
            new_phase = self.edit_entry.get().strip()
            current_values = list(self.formulation_item_tree.item(item_id, "values"))
            old_phase = current_values[0]
            
            # Phase 값이 변경되었을 때만 처리
            if new_phase != old_phase:
                current_values[0] = new_phase
                self.formulation_item_tree.item(item_id, values=tuple(current_values))
                
                # Phase가 숫자인 경우 자동 재정렬 트리거
                try:
                    new_phase_num = int(new_phase) if new_phase else 0
                    # 다른 Phase들 확인 및 재정렬
                    self.reorder_phases_on_insert(new_phase_num)
                except ValueError:
                    # 숫자가 아닌 Phase는 재정렬 안 함
                    pass
        except Exception as e:
            print(f"Phase 편집 오류: {e}")
        finally:
            self.edit_entry.destroy()
            self.edit_entry = None
    
    def reorder_phases_on_insert(self, inserted_phase):
        """Phase 중간 삽입 시 이후 Phase들을 자동으로 밀어내기"""
        all_items = []
        
        # 모든 아이템 정보 수집
        for item_id in self.formulation_item_tree.get_children():
            values = list(self.formulation_item_tree.item(item_id, "values"))
            tags = self.formulation_item_tree.item(item_id, "tags")
            all_items.append((item_id, values, tags))
        
        # Phase 재정렬
        phase_map = {}  # {old_phase: new_phase}
        for item_id, values, tags in all_items:
            if values[1] == "---":  # 구분선은 스킵
                continue
            
            try:
                current_phase_str = values[0]
                if not current_phase_str:
                    continue
                
                current_phase = int(current_phase_str)
                
                # 삽입된 Phase보다 크거나 같은 Phase는 +1
                if current_phase >= inserted_phase and current_phase != inserted_phase:
                    new_phase = current_phase + 1
                    phase_map[current_phase] = new_phase
                    values[0] = str(new_phase)
                    self.formulation_item_tree.item(item_id, values=tuple(values))
            except (ValueError, TypeError):
                # 숫자가 아닌 Phase는 건너뜀
                continue
        
        if phase_map:
            print(f"Phase 자동 재정렬: Phase {inserted_phase} 삽입, {phase_map} 변경")
    
    def edit_item_ratio(self, event):
        """Treeview의 '함량' 셀을 더블클릭하여 수정합니다."""
        if self.edit_entry: self.edit_entry.destroy()
        region = self.formulation_item_tree.identify("region", event.x, event.y)
        if region != "cell" or self.formulation_item_tree.identify_column(event.x) != "#4":
            return
        selected_item = self.formulation_item_tree.focus()
        self.start_ratio_editing(selected_item, "#4")

    def edit_selected_item_ratio(self, event=None):
        selected_item = self.formulation_item_tree.focus()
        if selected_item: self.start_ratio_editing(selected_item, "#4")

    def start_ratio_editing(self, selected_item, column_id):
        if not selected_item: return
        item_values = self.formulation_item_tree.item(selected_item, "values")
        if item_values and item_values[1] == "---": return
        if self.edit_entry: self.edit_entry.destroy()

        x, y, width, height = self.formulation_item_tree.bbox(selected_item, column_id)
        current_value = self.formulation_item_tree.item(selected_item, "values")[3]
        self.edit_entry = ctk.CTkEntry(self.formulation_item_tree, width=width, height=height, justify='right')
        self.edit_entry.place(x=x, y=y)
        self.edit_entry.insert(0, current_value)
        self.edit_entry.select_range(0, 'end')
        safe_focus(self.edit_entry)
        self.edit_entry.bind("<Return>", lambda e: self.on_edit_entry_commit(selected_item))
        self.edit_entry.bind("<FocusOut>", lambda e: self.on_edit_entry_commit(selected_item))
    
    def on_edit_entry_commit(self, item_id):
        if not self.edit_entry: return
        try:
            # Decimal로 안전하게 변환
            new_ratio_dec = to_decimal(self.edit_entry.get())
            current_values = list(self.formulation_item_tree.item(item_id, "values"))
            current_values[3] = decimal_to_str_full(new_ratio_dec)
            # amount는 재계산하지 않고 그대로 유지
            # current_values[4] = self.calculate_single_amount(new_ratio_dec)
            self.formulation_item_tree.item(item_id, values=tuple(current_values))
        except (InvalidOperation, ValueError, TypeError):
            pass
        finally:
            self.edit_entry.destroy()
            self.edit_entry = None
            self.update_formulation_summary()

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
        # amount는 재계산하지 않고 그대로 유지
        # current_values[4] = self.calculate_single_amount(new_ratio)
        self.formulation_item_tree.item(selected_item_id, values=tuple(current_values))
        self.update_formulation_summary()

    def move_item_up(self, event=None):
        selected_item = self.formulation_item_tree.focus()
        if not selected_item: return
        prev_item = self.formulation_item_tree.prev(selected_item)
        if prev_item:
            self.formulation_item_tree.move(selected_item, "", self.formulation_item_tree.index(prev_item))
            self.formulation_item_tree.focus(selected_item)
            self.formulation_item_tree.selection_set(selected_item)
            self.update_phase_numbers()
        return 'break'

    def move_item_down(self, event=None):
        selected_item = self.formulation_item_tree.focus()
        if not selected_item: return
        next_item = self.formulation_item_tree.next(selected_item)
        if next_item:
            # next_item 다음 위치로 이동 (한 칸만 이동)
            next_next_item = self.formulation_item_tree.next(next_item)
            if next_next_item:
                self.formulation_item_tree.move(selected_item, "", self.formulation_item_tree.index(next_next_item))
            else:
                self.formulation_item_tree.move(selected_item, "", "end")
            self.formulation_item_tree.focus(selected_item)
            self.formulation_item_tree.selection_set(selected_item)
            self.update_phase_numbers()

    def on_drag_start(self, event):
        """드래그 시작 - 클릭한 아이템 저장"""
        item = self.formulation_item_tree.identify_row(event.y)
        if item:
            self.drag_data["item"] = item
            self.drag_data["index"] = self.formulation_item_tree.index(item)

    def on_drag_motion(self, event):
        """드래그 중 - 현재 위치 표시"""
        target_item = self.formulation_item_tree.identify_row(event.y)
        if target_item and self.drag_data["item"]:
            # 드래그 중인 아이템을 시각적으로 표시하기 위해 선택
            self.formulation_item_tree.selection_set(target_item)

    def on_drag_release(self, event):
        """드래그 종료 - 아이템 이동"""
        if not self.drag_data["item"]:
            return
        
        target_item = self.formulation_item_tree.identify_row(event.y)
        drag_item = self.drag_data["item"]
        
        if target_item and drag_item != target_item:
            # 타겟 아이템의 위치로 이동
            target_index = self.formulation_item_tree.index(target_item)
            self.formulation_item_tree.move(drag_item, "", target_index)
            self.formulation_item_tree.focus(drag_item)
            self.formulation_item_tree.selection_set(drag_item)
            self.update_phase_numbers()
        
        # 드래그 데이터 초기화
        self.drag_data = {"item": None, "index": None}

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

    def update_phase_numbers(self):
        i = 1
        for item_id in self.formulation_item_tree.get_children():
            current_values = list(self.formulation_item_tree.item(item_id, "values"))
            if current_values[1] == "---":
                current_values[0] = ""
            else:
                current_values[0] = str(i)
                i += 1
            self.formulation_item_tree.item(item_id, values=tuple(current_values))
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

    def sort_items_by_phase(self):
        """처방 내용 아이템들을 구분(phase) 순서로 정렬합니다."""
        # 현재 Treeview의 모든 아이템 정보를 수집
        items_data = []
        for item_id in self.formulation_item_tree.get_children():
            values = self.formulation_item_tree.item(item_id, "values")
            tags = self.formulation_item_tree.item(item_id, "tags")
            items_data.append((values, tags))
        
        # phase(구분) 순서로 정렬
        # 숫자가 있는 것은 숫자 순으로, 빈 문자열이나 "---"는 마지막에
        def sort_key(item):
            phase_value = item[0][0]  # phase는 첫 번째 컬럼
            if not phase_value or phase_value == "---" or phase_value == "":
                return (1, 999)  # 빈 값들은 마지막에
            try:
                return (0, int(phase_value))  # 숫자로 변환 가능하면 숫자 순으로
            except (ValueError, TypeError):
                return (1, str(phase_value))  # 문자열은 문자열 순으로
        
        sorted_items = sorted(items_data, key=sort_key)
        
        # 기존 아이템들 삭제
        for item_id in self.formulation_item_tree.get_children():
            self.formulation_item_tree.delete(item_id)
        
        # 정렬된 순서로 다시 삽입
        for values, tags in sorted_items:
            self.formulation_item_tree.insert("", "end", values=values, tags=tags)
        
        # phase 번호 업데이트
        self.update_phase_numbers()

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

    def export_formulation_to_excel(self): # noqa
        # 내보내기 직전에 LAB NO.를 다시 한번 업데이트하여 최신 상태를 보장합니다.
        self.update_lab_no()

        if not self.exp_name_entry.get().strip():
            messagebox.showwarning(self.texts['warning'], self.texts['export_formulation_name_empty'], parent=self)
            return
        
        # 담당자명 처리: ID가 아닌 이름으로 변환
        manager_name = self.get_manager_display_name(self.exp_manager_entry.get())
        
        formulation_data = {
            "details": {
                "실험품명": self.exp_name_entry.get(), "실험년월일": self.exp_date_entry.get(),
                "담당자": manager_name, "담당번호": self.exp_code_entry.get().upper(),
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
            self.exp_manager_entry.insert(0, details.get("담당자", self.current_user.real_name or self.current_user.username) or (self.current_user.real_name or self.current_user.username)) # 담당자가 없으면 현재 사용자
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
                
                # 줄내림 체크: 코드가 "---"이면 줄내림으로 처리
                code_val = item.get("코드", "")
                if isinstance(code_val, str) and code_val.strip() in ["---", "-", "--", "―", "ㅡ"]:
                    # 줄내림인 경우
                    ratio_str = ""
                    amount_str = ""
                else:
                    # 일반 원료인 경우
                    ratio_dec = to_decimal(ratio_val)
                    ratio_str = decimal_to_str_full(ratio_dec)

                    # 총 실험량과 함량을 기반으로 실험량을 다시 계산합니다.
                    if total_amount > Decimal('0'):
                        amount_val = (total_amount * ratio_dec) / Decimal('100')
                        amount_str = decimal_to_str_full(amount_val)
                    else:
                        amount_str = "0"

                self.formulation_item_tree.insert("", "end", values=(
                    item.get("구분") or "", code_val or "", item.get("원료명") or "",
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

    def import_formulation_from_excel(self):
        if not messagebox.askyesno(self.texts['import_confirm'], self.texts['import_formulation_confirm_msg'], parent=self):
            return
        formulation_data = excel_handler.import_formulation_template()
        if formulation_data:
            self._apply_imported_data_to_ui(formulation_data)
    
    def start_refresh_timer(self):
        """데이터 새로고침 타이머를 시작합니다 (5분마다)"""
        # 기존 타이머가 있으면 먼저 취소 (타이머 누적 방지)
        if self.refresh_timer:
            try:
                self.after_cancel(self.refresh_timer)
            except Exception:
                pass
            self.refresh_timer = None
        
        # 창이 아직 존재하는지 확인
        try:
            if not self.winfo_exists():
                return
        except Exception:
            return
            
        self.refresh_timer = self.after(300000, self.refresh_data_periodically)  # 5분 = 300,000ms
        
    def refresh_data_periodically(self):
        """주기적으로 데이터를 새로고침합니다"""
        # 창이 이미 파괴되었는지 확인
        try:
            if not self.winfo_exists():
                return
        except Exception:
            return
            
        try:
            # 데이터 로딩 중이거나 편집 중인 경우 새로고침 건너뛰기
            if self.data_loading:
                print("데이터 로딩 중이므로 새로고침을 건너뜁니다.")
                self.start_refresh_timer()
                return
                
            # 활동이 있었던 경우에만 새로고침 (마지막 활동 후 10분 이내)
            current_time = time.time()
            if current_time - self.last_activity_time < 600:  # 10분
                print("사용자 활동이 최근에 있었으므로 데이터 새로고침을 수행합니다.")
                self.refresh_formulation_data()
            else:
                print("사용자 활동이 없어 새로고침을 건너뜁니다.")
            
            # 다음 새로고침 스케줄
            self.start_refresh_timer()
            
        except Exception as e:
            print(f"데이터 새로고침 중 오류: {e}")
            # 오류가 발생해도 타이머는 계속 실행
            self.start_refresh_timer()
    
    def refresh_formulation_data(self):
        """처방 데이터를 새로고침합니다"""
        try:
            # 현재 편집 중인 경우에는 새로고침하지 않음
            if self.edit_entry and self.edit_entry.winfo_exists():
                print("편집 중이므로 새로고침을 건너뜁니다.")
                return
                
            print("처방 데이터 새로고침 중...")
            
            # 현재 처방 ID가 있는 경우에만 새로고침
            if self.formulation_id:
                # 현재 사용자 입력값들을 저장
                current_values = self.get_current_form_values()
                print(f"현재 입력값 저장: {current_values}")
                
                # 데이터베이스에서 최신 데이터 로드
                session = db_manager.get_session()
                try:
                    form = session.query(Formulation).filter_by(id=self.formulation_id).first()
                    if form:
                        # 기본 정보만 새로고침 (사용자 입력 필드는 유지)
                        self.load_essential_data_only(form)
                        print("필수 데이터만 새로고침 완료")
                    else:
                        print(f"처방 ID {self.formulation_id}를 찾을 수 없습니다.")
                finally:
                    session.close()
                    
                # 중요한 사용자 입력값들은 다시 복원
                self.restore_user_inputs(current_values)
                print("사용자 입력값 복원 완료")
            else:
                print("신규 처방이므로 새로고침을 건너뜁니다.")
                
        except Exception as e:
            print(f"처방 데이터 새로고침 중 오류: {e}")
            import traceback
            traceback.print_exc()
    
    def load_essential_data_only(self, form):
        """필수 데이터만 로드합니다 (사용자 입력 필드는 건드리지 않음)"""
        try:
            # 변경 이력만 업데이트 (사용자가 직접 수정하지 않는 필드)
            self.change_log_textbox.configure(state="normal")
            self.change_log_textbox.delete("1.0", "end")
            if form.change_log:
                self.change_log_textbox.insert("1.0", str(form.change_log))
            else:
                self.change_log_textbox.insert("1.0", "저장된 변경 이력이 없습니다.")
            self.change_log_textbox.configure(state="disabled")
            
            # 샘플 발송 횟수 업데이트
            self.sample_sent_count = form.sample_sent_count or 0
            
            print("필수 데이터 로드 완료")
            
        except Exception as e:
            print(f"필수 데이터 로드 중 오류: {e}")
    
    def get_current_form_values(self):
        """현재 폼의 입력값들을 저장합니다"""
        try:
            return {
                'exp_name': self.exp_name_entry.get(),
                'exp_manager': self.exp_manager_entry.get(),
                'exp_code': self.exp_code_entry.get(),
                'revision': self.revision_entry.get(),
                'target_info_checked': self.target_info_var.get(),
                'target_sample_name': self.target_sample_name_entry.get(),
                'target_client': self.target_client_entry.get(),
                'target_ph_initial': self.target_ph_initial_entry.get(),
                'target_ph_next_day': self.target_ph_next_day_entry.get(),
                'target_viscosity_initial': self.target_viscosity_initial_entry.get(),
                'target_viscosity_next_day': self.target_viscosity_next_day_entry.get(),
                'target_machine': self.target_machine_entry.get(),
                'exp_ph_initial': self.exp_ph_initial_entry.get(),
                'exp_ph_next_day': self.exp_ph_next_day_entry.get(),
                'exp_viscosity_initial': self.exp_viscosity_initial_entry.get(),
                'exp_viscosity_next_day': self.exp_viscosity_next_day_entry.get(),
                'exp_machine': self.exp_machine_entry.get(),
                'exp_comment': self.exp_comment_textbox.get("1.0", "end-1c"),
                'main_total_amount': self.main_total_amount_entry.get(),
                'client_type': self.formulation_client_type_combo.get(),
                'client_name': self.formulation_client_name_combo.get(),
            }
        except Exception as e:
            print(f"현재 폼 값 저장 중 오류: {e}")
            return {}
    
    def restore_user_inputs(self, values):
        """사용자 입력값들을 복원합니다"""
        try:
            if not values:
                return
                
            # 실험명이 사용자가 수정한 것이라면 복원
            if 'exp_name' in values and values['exp_name'].strip():
                current_name = self.exp_name_entry.get().strip()
                if current_name != values['exp_name']:
                    self.exp_name_entry.delete(0, "end")
                    self.exp_name_entry.insert(0, values['exp_name'])
            
            # 담당자명 복원
            if 'exp_manager' in values and values['exp_manager'].strip():
                current_manager = self.exp_manager_entry.get().strip()
                if current_manager != values['exp_manager']:
                    self.exp_manager_entry.delete(0, "end")
                    self.exp_manager_entry.insert(0, values['exp_manager'])
            
            # 담당번호 복원
            if 'exp_code' in values and values['exp_code'].strip():
                current_code = self.exp_code_entry.get().strip()
                if current_code != values['exp_code']:
                    self.exp_code_entry.delete(0, "end")
                    self.exp_code_entry.insert(0, values['exp_code'])
                    
            # 차수 복원
            if 'revision' in values and values['revision'].strip():
                current_revision = self.revision_entry.get().strip()
                if current_revision != values['revision']:
                    self.revision_entry.delete(0, "end")
                    self.revision_entry.insert(0, values['revision'])
            
            # 타겟 정보 체크박스 상태 복원
            if 'target_info_checked' in values:
                self.target_info_var.set(values['target_info_checked'])
                self.toggle_target_info()
            
            # 총 실험량 복원
            if 'main_total_amount' in values and values['main_total_amount'].strip():
                current_amount = self.main_total_amount_entry.get().strip()
                if current_amount != values['main_total_amount']:
                    self.main_total_amount_entry.delete(0, "end")
                    self.main_total_amount_entry.insert(0, values['main_total_amount'])
            
            # 거래처 정보 복원
            if 'client_type' in values and values['client_type'] != self.texts['select_type']:
                self.formulation_client_type_combo.set(values['client_type'])
                self.update_formulation_client_combo(values['client_type'])
                
                if 'client_name' in values and values['client_name'] != self.texts['select_client']:
                    # 잠깐 대기 후 거래처명 설정
                    self.after(50, lambda: self.formulation_client_name_combo.set(values['client_name']))
            
            print("사용자 입력값 복원 완료")
            
        except Exception as e:
            print(f"사용자 입력값 복원 중 오류: {e}")
    
    def on_user_activity(self, event=None):
        """사용자 활동 시간을 업데이트합니다"""
        self.last_activity_time = time.time()
        # print(f"사용자 활동 감지: {datetime.fromtimestamp(self.last_activity_time).strftime('%H:%M:%S')}")
        
    def destroy(self):
        """창 종료 시 타이머 정리"""
        if self.refresh_timer:
            self.after_cancel(self.refresh_timer)
            self.refresh_timer = None
        print("처방 편집 창이 종료되었습니다.")
        # 주의: 이 메서드는 동적으로 클래스에 바인딩되므로 super() 사용이 불가합니다.
        # 직접 부모 클래스 메서드를 호출합니다.
        try:
            ctk.CTkToplevel.destroy(self)
        except Exception:
            # 최후의 수단으로 Tk widget의 destroy 시도
            try:
                self.__class__.__mro__[1].destroy(self)
            except Exception:
                pass

# --- 메서드 바인딩 제거 (모든 함수가 이제 클래스 메서드로 제대로 정의됨) ---
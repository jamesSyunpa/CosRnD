# modules/formulation_popup.py
import customtkinter as ctk
from sqlalchemy.orm import joinedload
from tkinter import ttk, messagebox
from tkcalendar import DateEntry
from database.db_manager import db_manager
from database.models import Client, Formulation, FormulationItem, Material
from datetime import datetime
from modules import excel_handler
from modules.ui_components import CustomErrorDialog

# document_management.py에서 클래스들을 가져옵니다.
from modules.document_management import CustomDropdown, AddMaterialDialog
from modules.ui_components import try_convert_to_float, HelpPopup
from modules.translation import get_texts

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

        self.title(self.texts['formulation_popup_title'])
        # self.geometry("1200x800") # 크기 고정 해제
        self.transient(master)
        self.resizable(True, True) # 크기 조절 활성화
        self.minsize(1000, 700) # 최소 크기 설정
        self.grab_set()

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
        main_container.grid_columnconfigure(0, weight=1, uniform="group1") # 좌측: 처방 상세 정보
        main_container.grid_columnconfigure(1, weight=1, uniform="group1") # 우측: 처방 내용
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
        experiment_info_frame.grid_columnconfigure(1, weight=1)
        experiment_info_frame.grid_columnconfigure(3, weight=1)

        ctk.CTkLabel(experiment_info_frame, text=self.texts['experiment_name'], font=ctk.CTkFont(weight="bold")).grid(row=0, column=0, padx=10, pady=5, sticky="w")
        self.exp_name_entry = ctk.CTkEntry(experiment_info_frame)
        self.exp_name_entry.grid(row=0, column=1, columnspan=3, padx=10, pady=5, sticky="ew")
        
        ctk.CTkLabel(experiment_info_frame, text=self.texts['experiment_date']).grid(row=1, column=0, padx=10, pady=5, sticky="w")
        self.exp_date_entry = DateEntry(experiment_info_frame, date_pattern='yyyy-mm-dd', width=15)
        self.exp_date_entry.grid(row=1, column=1, padx=10, pady=5, sticky="w")
        self.exp_date_entry.bind("<<DateEntrySelected>>", self.update_lab_no)

        ctk.CTkLabel(experiment_info_frame, text=self.texts['manager_name']).grid(row=1, column=2, padx=10, pady=5, sticky="w")
        self.exp_manager_entry = ctk.CTkEntry(experiment_info_frame)
        self.exp_manager_entry.grid(row=1, column=3, padx=10, pady=5, sticky="ew")
        self.exp_manager_entry.insert(0, self.current_user.username) # 기본값으로 현재 사용자 설정

        ctk.CTkLabel(experiment_info_frame, text=self.texts['manager_code']).grid(row=2, column=0, padx=10, pady=5, sticky="w")
        self.exp_code_entry = ctk.CTkEntry(experiment_info_frame)
        self.exp_code_entry.grid(row=2, column=1, padx=10, pady=5, sticky="ew")
        self.exp_code_entry.bind("<KeyRelease>", self.update_lab_no)

        ctk.CTkLabel(experiment_info_frame, text=self.texts['lab_no']).grid(row=3, column=0, padx=10, pady=5, sticky="w")
        self.lab_no_entry = ctk.CTkEntry(experiment_info_frame, state="disabled") # 읽기 전용으로 설정
        self.lab_no_entry.grid(row=3, column=1, padx=10, pady=5, sticky="ew")

        ctk.CTkLabel(experiment_info_frame, text=self.texts['revision']).grid(row=3, column=2, padx=10, pady=5, sticky="w")
        self.revision_entry = ctk.CTkEntry(experiment_info_frame)
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
        self.formulation_client_name_combo = CustomDropdown(client_selection_frame, values=[self.texts['select_client']], command=self.on_client_select, width=250)
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
        content_pane.grid_rowconfigure(1, weight=1)

        # --- 처방 내용 헤더 (버튼 등) (content_pane에 추가) ---
        content_header = ctk.CTkFrame(content_pane, fg_color="transparent")
        content_header.grid(row=0, column=0, padx=10, pady=10, sticky="ew")
        
        ctk.CTkLabel(content_header, text=self.texts['formulation_content'], font=ctk.CTkFont(size=14, weight="bold")).pack(side="left", padx=(0, 20))

        # 총 실험량 입력 필드를 헤더로 이동
        total_amount_header_frame = ctk.CTkFrame(content_header, fg_color="transparent")
        total_amount_header_frame.pack(side="left", padx=(10, 20))
        ctk.CTkLabel(total_amount_header_frame, text=self.texts['total_experiment_amount_g'], font=ctk.CTkFont(weight="bold")).pack(side="left", padx=(0, 5))
        self.main_total_amount_entry = ctk.CTkEntry(total_amount_header_frame, width=100, justify='right')
        self.main_total_amount_entry.pack(side="left")
        self.main_total_amount_entry.bind("<Return>", self.calculate_item_amounts)
        self.main_total_amount_entry.bind("<FocusOut>", self.calculate_item_amounts)

        content_buttons = ctk.CTkFrame(content_header, fg_color="transparent")
        content_buttons.pack(side="right")
        self.add_material_button = ctk.CTkButton(content_buttons, text=self.texts['add_material'], width=80, command=self.open_add_material_dialog)
        self.add_material_button.pack(side="left", padx=5)
        self.to_100_button = ctk.CTkButton(content_buttons, text=self.texts['to_100'], width=80, command=self.set_ratio_to_100)
        self.to_100_button.pack(side="left", padx=5)
        self.move_up_button = ctk.CTkButton(content_buttons, text="▲", width=40, command=self.move_item_up)
        self.move_up_button.pack(side="left", padx=(10, 2))
        self.move_down_button = ctk.CTkButton(content_buttons, text="▼", width=40, command=self.move_item_down)
        self.move_down_button.pack(side="left", padx=(2, 10))
        self.delete_item_button = ctk.CTkButton(content_buttons, text=self.texts['delete_selected'], width=80, fg_color="#D32F2F", hover_color="#B71C1C", command=self.delete_selected_item)
        self.delete_item_button.pack(side="left", padx=5)

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
        self.formulation_item_tree.bind("<Double-1>", self.edit_item_ratio)
        self.formulation_item_tree.bind("<Up>", self.move_item_up)
        self.formulation_item_tree.bind("<Down>", self.move_item_down)
        self.formulation_item_tree.bind("<Control-Up>", self.move_item_up)
        self.formulation_item_tree.bind("<Return>", self.edit_selected_item_ratio)
        self.formulation_item_tree.bind("<Control-Down>", self.move_item_down)

        # --- 처방 내용 Treeview 스크롤바 ---
        tree_scrollbar = ttk.Scrollbar(content_pane, orient="vertical", command=self.formulation_item_tree.yview) # content_pane을 부모로 사용
        self.formulation_item_tree.configure(yscrollcommand=tree_scrollbar.set)
        tree_scrollbar.grid(row=1, column=1, sticky="ns")


        # --- 처방 내용 요약 ---
        summary_frame = ctk.CTkFrame(content_pane, fg_color="transparent")
        summary_frame.grid(row=2, column=0, padx=10, pady=5, sticky="e")

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
            self.exp_manager_entry.delete(0, "end"); self.exp_manager_entry.insert(0, form.manager_name or "")
            self.exp_code_entry.delete(0, "end"); self.exp_code_entry.insert(0, form.manager_code or "")

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
            
            total_amount = 0.0
            for item in sorted(form.items, key=lambda x: x.order):
                self.formulation_item_tree.insert("", "end", values=(
                    item.phase or "",
                    item.material_code or "---",
                    item.material_name or "---",
                    f"{item.ratio:.4f}" if item.ratio is not None else "---",
                    f"{item.amount:.4f}" if item.amount is not None else "---"
                ))
                if item.amount is not None:
                    total_amount += item.amount
            
            # 총 실험량 필드 업데이트
            self.main_total_amount_entry.delete(0, "end")
            self.main_total_amount_entry.insert(0, f"{total_amount:.4f}")

            self.update_formulation_summary()
            self.update_lab_no() # 데이터 로드 후 LAB NO. 업데이트
        finally:
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
                if form and form.lab_no != self.lab_no_entry.get().strip():
                    is_new_revision = True
                    old_form_items = {item.material_code: item.ratio for item in form.items}
                    self.formulation_id = None # ID를 None으로 만들어 신규 저장 모드로 전환
                    form = Formulation() # 새로운 처방 객체 생성
                    session.add(form)
                    # 디버깅을 위해 담당번호와 LAB NO.를 함께 출력
                    current_code = self.exp_code_entry.get().strip()
                    print(f"LAB NO. 변경 감지: '새 버전으로 저장'을 시작합니다. (담당번호: '{current_code}', LAB NO: '{self.lab_no_entry.get().strip()}')")
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
                ratio = 0.0
                amount = 0.0 
                # 태그 추가
                tag = 'oddrow' if len(self.formulation_item_tree.get_children()) % 2 == 0 else 'evenrow'
                self.formulation_item_tree.insert("", "end", tags=(tag,), values=(
                    "", material.code, material.name, f"{ratio:.4f}", f"{amount:.4f}"
                ))
                self.update_phase_numbers()
        finally:
            session.close()

    def add_line_break_to_formulation(self):
        """처방 내용에 빈 줄(구분선)을 추가합니다."""
        # 태그 추가
        tag = 'oddrow' if len(self.formulation_item_tree.get_children()) % 2 == 0 else 'evenrow'
        self.formulation_item_tree.insert("", "end", tags=(tag,), values=("", "---", "---", "---", "---"))
        self.update_phase_numbers()

    def delete_selected_item(self):
        """처방 내용 Treeview에서 선택된 항목을 삭제합니다."""
        selected_item = self.formulation_item_tree.selection()
        if not selected_item:
            messagebox.showwarning(self.texts['selection_error'], self.texts['select_item_to_delete'], parent=self)
            return
        self.formulation_item_tree.delete(selected_item)
        self.update_phase_numbers()

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
        self.edit_entry.focus_set()
        self.edit_entry.bind("<Return>", lambda e: self.on_edit_entry_commit(selected_item))
        self.edit_entry.bind("<FocusOut>", lambda e: self.on_edit_entry_commit(selected_item))
    
    def on_edit_entry_commit(self, item_id):
        if not self.edit_entry: return
        try:
            new_ratio = float(self.edit_entry.get())
            current_values = list(self.formulation_item_tree.item(item_id, "values"))
            current_values[3] = f"{new_ratio:.4f}"
            current_values[4] = self.calculate_single_amount(new_ratio)
            self.formulation_item_tree.item(item_id, values=tuple(current_values))
        except (ValueError, TypeError): pass
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

        other_ratios_sum = 0.0
        for item_id in self.formulation_item_tree.get_children():
            if item_id == selected_item_id: continue
            values = self.formulation_item_tree.item(item_id, "values")
            if values and values[1] != "---":
                try: other_ratios_sum += float(values[3])
                except (ValueError, TypeError): continue
        
        new_ratio = 100.0 - other_ratios_sum
        if new_ratio < 0:
            messagebox.showwarning(self.texts['calculation_error'], self.texts['ratio_exceeds_100_warning'], parent=self)
            new_ratio = 0.0

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
            self.formulation_item_tree.selection_set(selected_item)
            self.update_phase_numbers()
        return 'break'

    def move_item_down(self, event=None):
        selected_item = self.formulation_item_tree.focus()
        if not selected_item: return
        next_item = self.formulation_item_tree.next(selected_item)
        if next_item:
            self.formulation_item_tree.move(selected_item, "", self.formulation_item_tree.index(next_item) + 1)
            self.formulation_item_tree.focus(selected_item)
            self.formulation_item_tree.selection_set(selected_item)
            self.update_phase_numbers()
        else:
            self.formulation_item_tree.move(selected_item, "", "end")
            self.update_phase_numbers()

    def calculate_single_amount(self, ratio: float) -> str:
        try:
            total_amount = float(self.main_total_amount_entry.get())
            amount = (total_amount * ratio) / 100.0
            return f"{amount:.4f}"
        except (ValueError, TypeError): return "0.0000"

    def calculate_item_amounts(self, event=None):
        try: total_amount = float(self.main_total_amount_entry.get())
        except (ValueError, TypeError): total_amount = 0.0
        for item_id in self.formulation_item_tree.get_children():
            values = list(self.formulation_item_tree.item(item_id, "values"))
            if values and values[1] != "---":
                try:
                    ratio = float(values[3])
                    amount = (total_amount * ratio) / 100.0
                    values[4] = f"{amount:.4f}"
                    self.formulation_item_tree.item(item_id, values=tuple(values))
                except (ValueError, TypeError): continue
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
        total_ratio, total_amount = 0.0, 0.0
        for item_id in self.formulation_item_tree.get_children():
            values = self.formulation_item_tree.item(item_id, "values")
            if values and values[1] != "---":
                try:
                    total_ratio += float(values[3])
                    total_amount += float(values[4])
                except (ValueError, TypeError): continue
        self.total_ratio_label.configure(text=f"{total_ratio:.4f} %")
        self.total_amount_label.configure(text=f"{total_amount:.4f} g")

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
                total_amount = float(details.get("총 실험량", 0.0))
            except (ValueError, TypeError):
                total_amount = 0.0

            for item in items:
                ratio_val = try_convert_to_float(item.get("함량(%)", "0.0000"))
                ratio_str = f"{ratio_val:.4f}" if isinstance(ratio_val, float) else str(ratio_val)

                # 총 실험량과 함량을 기반으로 실험량을 다시 계산합니다.
                if isinstance(ratio_val, float) and total_amount > 0:
                    amount_val = (total_amount * ratio_val) / 100.0
                    amount_str = f"{amount_val:.4f}"
                else:
                    amount_str = "0.0000"

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

    def import_formulation_from_excel(self):
        if not messagebox.askyesno(self.texts['import_confirm'], self.texts['import_formulation_confirm_msg'], parent=self):
            return
        formulation_data = excel_handler.import_formulation_template()
        if formulation_data:
            self._apply_imported_data_to_ui(formulation_data)
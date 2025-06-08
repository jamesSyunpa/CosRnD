# modules/translation.py

TRANSLATIONS = {
    "korean": {
        "help": "도움말",
        "close": "닫기",
        "save": "저장",
        "new": "신규",
        "edit": "수정",
        "delete": "삭제",
        "reset": "초기화",
        "search": "검색",
        "import": "가져오기",
        "export": "내보내기",
        "notification": "알림",
        "warning": "경고",
        "error": "오류",
        "success": "성공",
        "db_error": "데이터베이스 오류",
        "input_error": "입력 오류",
        "selection_error": "선택 오류",
        "export_error": "내보내기 오류",
        "calculation_error": "계산 오류",
        "import_confirm": "가져오기 확인",
        "delete_confirm": "삭제 확인",
        "dev_in_progress": "기능 개발 예정입니다.",
        "dev_in_progress_short": "개발 예정",
        "select_type": "- 유형 선택 -",
        "select_client": "- 업체 선택 -",
        "no_clients_found": "- 해당 업체 없음 -",
        "id": "ID",
        "code": "코드",
        "material_name": "원료명",
        "all_ingredients": "전성분",
        "press_button_placeholder": "버튼을 눌러주세요",

        # Main UI
        "menu": "메뉴", "home": "메인 화면", "document": "연구소", "quality": "품질 관리", "data": "데이터 관리", "settings": "설정 관리", "logout": "로그아웃",
        "formulation_mgt": "처방 관리", "document_sub": "문서", "ingredient_mgt": "성분 관리", "client_mgt": "거래처 관리", "user_mgt": "회원 관리", "settings_sub": "설정",
        "coa": "COA", "msds": "MSDS", "prod_standard": "제품표준서", "mfg_record": "제조관리기록서",

        # Settings
        "settings_tab": "설정",
        "settings_help_title": "설정 관리 도움말",
        "settings_help_message": """
        [설정 관리 사용법]
        이 화면에서는 프로그램의 동작 환경을 설정합니다.
        
        1. 테마 설정: 프로그램의 전체적인 디자인 테마(Light/Dark/System)를 변경합니다.
        2. 언어 설정: 프로그램의 모든 UI 언어를 변경합니다. (재시작 필요 없음)
        3. 경로 설정: DB 파일과 엑셀 파일의 기본 저장/불러오기 위치를 지정합니다.
           - DB 저장 경로 변경 시, 기존 DB 파일을 새 경로로 이동하거나 새로 생성할 수 있습니다.
           - (관리자만 경로 수정 가능)
        """,
        "theme_settings": "테마 설정", "language_settings": "언어 설정", "db_path": "DB 저장 경로", "excel_path": "엑셀 기본 경로",
        "browse": "찾아보기...", "save_paths": "경로 저장", "db_path_warning": "* DB 저장 경로는 프로그램 재시작 시 적용됩니다.",
        "export_excel_forms": "엑셀 폼 내보내기", "export_ingredient_form": "성분 폼 내보내기", "export_client_form": "거래처 폼 내보내기", "export_user_form": "사용자 폼 내보내기",
        "data_reset_warning": "데이터 리셋 (주의: 되돌릴 수 없음)", "reset_ingredient_data": "성분 데이터 리셋", "reset_client_data": "거래처 데이터 리셋", "reset_user_data": "사용자 데이터 리셋", "reset_all_data": "전체 데이터 리셋",

        # Data Management
        "data_mgt_help_title": "데이터 관리 도움말",
        "data_mgt_help_message": """
        [데이터 관리 사용법]
        이 화면에서는 프로그램의 기본 데이터(성분, 거래처, 회원)를 관리합니다.
        
        1. 성분 관리 탭: 원료의 상세 정보와 그에 속한 전성분 목록을 관리합니다.
        2. 거래처 관리 탭: 원료, OEM/ODM, 부자재 등 모든 거래처 정보를 관리합니다. (관리자 전용)
        3. 회원 관리 탭: 프로그램 사용자 계정을 관리합니다. (관리자 전용)
        """,
        "user_info": "사용자 정보", "password_helper": "(새 비밀번호 또는 변경 시 입력)", "admin_privilege": "관리자 권한",
        "view_selected_history": "선택 항목 이력 보기", "user_list": "사용자 목록", "view_all_history": "전체 이력 조회",
        "export_data": "데이터 내보내기", "import_data": "데이터 가져오기",
        "user_labels": {"username": "사용자 ID", "password": "비밀번호", "manager_code": "담당번호", "position": "직책", "contact": "연락처", "zip_code": "우편번호", "address": "주소"},
        "user_tree_columns": {"id": "ID", "username": "사용자 ID", "manager_code": "담당번호", "position": "직책", "contact": "연락처", "is_admin": "관리자 여부"},
        "client_info": "거래처 정보", "client_search": "거래처 검색", "client_type": "거래처 유형", "is_active": "사용 여부", "client_list": "거래처 목록",
        "client_type_values": ["원료", "OEM/ODM", "부자재", "기타"],
        "client_type_filter_values": ["- 유형 선택 -", "원료", "OEM/ODM", "부자재", "기타"],
        "client_labels": {"code": "거래처코드(사업자번호)", "name": "거래처명", "ceo": "대표자명", "manager": "담당자명", "contact": "연락처", "fax": "팩스", "email": "이메일", "zip": "우편번호", "address": "주소"},
        "client_tree_columns": {"id": "ID", "type": "유형", "code": "거래처코드", "name": "거래처명", "ceo": "대표자명", "manager": "담당자명", "contact": "연락처", "fax": "팩스", "email": "이메일", "zip": "우편번호", "address": "주소", "active": "사용여부"},

        # Document Management
        "doc_mgt_help_title": "처방 관리 도움말",
        "doc_mgt_help_message": """
        [처방 관리 사용법]
        [처방 목록 탭]
        1. 폴더/파일 보기: 각 '실험품명'이 하나의 폴더입니다. 폴더를 클릭하면 해당 실험품명의 모든 차수(버전) 목록을 볼 수 있습니다.
        2. 처방 생성/수정: '신규' 버튼으로 새 처방을, 목록에서 처방 선택 후 '수정' 버튼(또는 더블클릭)으로 기존 처방을 수정합니다.
        
        [견적 탭]
        1. 견적 생성: '처방 목록' 탭에서 처방을 선택한 후, '견적' 탭으로 와서 '견적 생성' 버튼을 누르면 해당 처방의 원료 목록이 불러와집니다.
        
        [전성분 탭]
        1. 목록 생성: '처방 목록' 탭에서 처방을 선택한 후, '전성분' 탭으로 와서 '전체 목록 생성' 버튼을 누르면 모든 전성분 목록이 한 번에 생성됩니다.
        """,
        "formulation_folders": "처방 폴더", "icon_size": "아이콘 크기:", "client_filter": "거래처 필터:", "back_to_folders": "◀ 뒤로 가기",
        "compare_history": "이력 비교", "reset_selection": "선택 초기화", "edit_sample_count": "발송수정", "send_sample": "샘플발송", "folder": "폴더", "formulations": "개 처방",
        "select_formulation_to_edit": "수정할 처방을 목록에서 선택하세요.", "select_one_formulation_to_edit": "하나의 처방만 선택하여 수정할 수 있습니다.",
        "select_two_formulations_to_compare": "비교할 두 개의 처방을 선택해주세요.", "select_folder_first": "폴더를 먼저 선택해주세요.",
        "no_formulation_data": "처방 데이터가 없습니다.\n'신규' 버튼을 눌러 새 처방을 작성하세요.",
    "formulation_tree_columns": {"id": "ID", "revision": "차수", "manager_code": "담당번호", "date": "실험일", "experiment_name": "제품명", "lab_no": "LAB NO.", "sample_sent": "샘플발송", "sample_delivery_date": "샘플발송일"},
        "delete_formulation_confirm_msg": "정말로 선택한 {count}개의 처방을 삭제하시겠습니까?", "delete_formulation_success_msg": "{count}개의 처방이 삭제되었습니다.",
        "select_formulation_to_delete": "삭제할 처방을 목록에서 선택하세요.", "delete_error_msg": "삭제 중 오류 발생: {e}",
        "select_formulation_for_sample": "샘플 발송 처리할 처방을 목록에서 선택하세요.", "send_sample_confirm": "샘플 발송 확인", "send_sample_confirm_msg": "선택한 처방의 샘플 발송 횟수를 1 증가시키겠습니까?",
        "sample_count_updated_msg": "샘플 발송 횟수가 {count}로 업데이트되었습니다.", "formulation_not_found": "선택된 처방을 찾을 수 없습니다.", "sample_count_update_error": "샘플 발송 횟수 업데이트 중 오류 발생: {e}",
        "edit_sample_info_title": "샘플 발송 정보 수정", "sent_count": "발송 횟수:", "last_sent_date": "마지막 발송일 (YYYY-MM-DD):", "sample_info_updated_success": "샘플 발송 정보가 업데이트되었습니다.",
        "invalid_number_date_format": "올바른 숫자와 날짜 형식(YYYY-MM-DD)을 입력해주세요.", "update_error_msg": "업데이트 중 오류 발생: {ex}", "sample_count_edit_error": "샘플 발송 횟수 수정 중 오류 발생: {e}",
        "client_list_update_error": "거래처 목록 갱신 중 오류: {e}",
        "create_quotation": "견적 생성", "export_quotation": "견적서 내보내기", "delete_selected": "선택 삭제", "base_weight_g": "기준 중량(g):", "add_material": "원료 추가", "edit_ratio": "함량 수정",
        "quotation_tree_columns": {"phase": "구분", "code": "코드", "name": "원료명", "ratio": "함량(%)", "unit_price": "단가(원/kg)", "cost": "원가(원)"},
        "total_ratio": "총 함량:", "total_raw_cost": "총 원료 원가:", "price_with_vat": "VAT(10%) 포함가:", "price_with_profit": "이윤(15%) 포함가:",
        "select_formulation_first": "먼저 '처방 목록' 탭에서 처방을 선택해주세요.", "quotation_creation_error": "견적 생성 오류", "quotation_creation_error_msg": "견적을 생성하는 중 오류가 발생했습니다",
        "select_item_to_edit_ratio": "함량을 수정할 항목을 목록에서 선택하세요.", "select_item_to_delete": "삭제할 항목을 목록에서 선택하세요.", "no_quotation_to_export": "내보낼 견적 내용이 없습니다. '견적 생성'을 먼저 실행해주세요.",
        "select_formulation_and_create_quotation": "먼저 '처방 목록' 탭에서 처방을 선택하고 '견적 생성'을 실행해주세요.",
        "reset_formulation_ref_title": "처방 참조 초기화 확인", "reset_formulation_ref_confirm": "모든 처방의 원료 참조를 초기화하시겠습니까?\n\n이 작업은 처방전 자체를 삭제하지 않지만,\n각 처방에 연결된 모든 원료 정보를 '참조 없음' 상태로 변경합니다.\n이 작업은 되돌릴 수 없습니다.",
        "reset_complete": "초기화 완료", "reset_formulation_ref_success": "모든 처방의 원료 참조가 초기화되었습니다.\n(총 {count}개 항목)", "reset_formulation_ref_error": "처방 참조 초기화 중 오류 발생",
        "data_update_failed": "데이터 업데이트에 실패했습니다.", "comment_updated_success": "기타 사항이 업데이트되었습니다.", "edit_comment_title": "기타 사항 수정", "enter_comment_to_edit": "수정할 내용을 입력하세요:",
        "no_data_to_export": "내보낼 데이터가 없습니다.", "import_journal_confirm_msg": "엑셀 파일에서 실험일지 데이터를 가져옵니다.\n\n'실험번호'를 기준으로 기존 데이터를 찾아 업데이트하며, 일치하는 데이터가 없으면 새로 추가합니다.\n\n계속하시겠습니까?",
        "import_journal_success_msg": "실험일지 가져오기가 완료되었습니다.\n- 신규 추가: {added}개\n- 기존 업데이트: {updated}개", "import_error_msg": "가져오기 중 오류 발생: {e}",
        "use_date_filter": "조회 기간 사용", "year": "년", "month": "월", "detailed_search": "상세 검색:", "enter_search_term": "검색어 입력...",
        "journal_search_fields": ["전체", "품명", "pH", "점도", "Pin", "실험번호", "업체"], "journal_tree_columns": {"date": "실험 날짜", "name": "품명", "ph": "pH", "viscosity": "점도", "gravity": "비중", "pin": "Pin", "lab_no": "실험번호", "client": "업체", "sample_delivery": "샘플 전달", "comment": "기타"},
        "no_date": "날짜 없음",
        "create_all_lists": "전체 목록 생성", "export_to_excel": "엑셀로 내보내기", "select_columns_to_display": "표시할 열 선택",
        "complex_ingredients_for_docs": "복합 전성분 (서류용)", "single_ingredients_by_ratio": "단일 전성분 (함량순)", "ingredients_for_design": "디자인용 전성분",
        "by_raw_material": "원료별 목록", "summed_ingredients": "전성분 합계",
    "complex_ingredient_tree_columns": {"no": {"text": "NO", "width": 40, "anchor": "center", "visible": True}, "material_name": {"text": "원료명", "width": 200, "visible": True}, "inci_name": {"text": "INCI Name", "width": 200, "visible": True}, "name_ko": {"text": "성분의 한글명", "width": 200, "visible": True}, "rm_ratio": {"text": "RM 함량(%)", "width": 120, "anchor": "e", "visible": True}, "ing_ratio": {"text": "성분 함량(%)", "width": 120, "anchor": "e", "visible": True}, "actual_wt": {"text": "Actual Wt (%)", "width": 120, "anchor": "e", "visible": True}, "cas_no": {"text": "CAS No.", "width": 120, "visible": True}, "function": {"text": "Ingredient function", "width": 150, "visible": True}, "hs_code": {"text": "HS CODE", "width": 100, "visible": False}, "origin": {"text": "원산지", "width": 100, "visible": False}, "material_name_en": {"text": "영문원료명", "width": 150, "visible": False}, "nmpa_reg_num": {"text": "NMPA", "width": 120, "visible": False}, "remark": {"text": "Remark", "width": 100, "visible": True}},
        "total_rm_ratio_label": "RM or ingredient % in fla 합계:", "total_actual_wt_label": "Actual Wt (%) 합계:",
        "summed_ingredient_tree_columns": {"name_ko": "국문명", "name_en": "영문명", "cas_no": "CAS No.", "function": "기능", "total_ratio": "총 함량(%)"},
        "total_ratio_sum": "총 함량(%) 합계:", "clipboard_copy_dev": "클립보드 복사 기능은 개발 예정입니다.",
        "single_ingredient_tree_columns": {"no": {"text": "NO", "width": 40, "anchor": "center", "visible": True}, "name_en": {"text": "INGREDIENT", "width": 250, "visible": True}, "ci_no": {"text": "C.I NO", "width": 80, "visible": False}, "total_ratio": {"text": "% (W/W)", "width": 100, "anchor": "e", "visible": True}, "cas_no": {"text": "CAS. NO", "width": 120, "visible": True}, "function": {"text": "FUNCTION", "width": 150, "visible": True}, "hs_code": {"text": "HS CODE", "width": 100, "visible": False}, "nmpa_reg_num": {"text": "NMPA", "width": 120, "visible": False}, "remark": {"text": "비고", "width": 150, "visible": False}},
        "total_ratio_ww_sum": "총 함량(% (W/W)) 합계:",
        "korean_ingredients": "국문 전성분", "english_ingredients_inci": "영문 전성분 (INCI)",
        "select_formulation_and_create_list": "먼저 처방을 선택하고 '전체 목록 생성'을 실행해주세요.", "no_data_to_export_create_list": "내보낼 데이터가 없습니다. '전체 목록 생성'을 먼저 실행해주세요.",
        "single_ingredients_korean": "단일 전성분 (국문)", "single_ingredients_english": "단일 전성분 (영문)",
        "functional_report_title": "기능성화장품 심사제외품목 보고서 작성", "export_report": "보고서 내보내기",
        "usage_default": "본품 적당량을 취해 피부에 골고루 펴 바른다.", "precautions_default": "1. 화장품 사용 시 또는 사용 후 직사광선에 의하여 사용부위가 붉은 반점, 부어오름 또는 가려움증 등의 이상 증상이나 부작용이 있는 경우에는 전문의 등과 상담할 것\n\n2. 상처가 있는 부위 등에는 사용을 자제할 것\n\n3. 보관 및 취급시의 주의 사항\n가. 어린이의 손이 닿지 않는 곳에 보관할 것\n나. 직사광선을 피해서 보관할 것",
        "active_substance_default": "예시:\n총 에칠헥실트리아존으로서 4.00그램\n총 폴리실리콘-15으로서 3.00그램", "ingredients_ratio_default": "예시:\n나이아신아마이드: 2g\n아데노신: 0.04g",

        # Quality Management
        "quality_mgt_help_title": "품질 관리 도움말",
        "quality_mgt_help_message": """
        [품질 관리 사용법]
        - COA: 반제품/완제품의 시험성적서(COA)를 관리합니다.
        - MSDS: 물질안전보건자료(MSDS)를 관리합니다.
        - 제품표준서: 제품의 표준 정보를 관리합니다.
        - 제조관리기록서: 제품의 제조 이력을 관리합니다.
        (모든 기능은 현재 개발 예정입니다.)
        """,
        "semi_finished_product_report": "반제품 시험성적서",
        "semi_finished_product_report_title": "반제품 시험성적서 정보 입력",
        "semi_product_table_headers": ["구분", "시험항목", "시험기준", "시험결과", "비고"],
        "semi_product_coa_fields": {}, # 이 줄을 삭제하거나 빈 딕셔너리로 남겨둡니다.
        "create_excel_report": "엑셀 보고서 생성", "form_cleared": "입력 양식이 초기화되었습니다.", "required_fields_missing": "필수 항목(제품명, LOT, 종합판정)을 모두 입력해주세요.",
        "save_report_as": "보고서 다른 이름으로 저장", "report_saved_success": "보고서가 성공적으로 저장되었습니다", "report_generation_error": "보고서 생성 중 오류 발생",

        # Formulation Popup
        "formulation_popup_title": "처방 생성/수정", "formulation_details": "처방 상세 정보", "use_target_info": "타겟 정보 사용",
        "target_sample_name": "타겟 샘플명", "target_ph": "타겟 pH", "today": "당일:", "next_day": "익일:", "target_viscosity": "타겟 점도",
        "pin_and_machine": "사용핀 및 기계", "target_client": "타겟 거래처", "experiment_name": "실험품명", "experiment_date": "실험년월일",
        "manager_name": "담당자", "manager_code": "담당번호", "lab_no": "LAB NO.", "revision": "차수", "client": "거래처",
        "experiment_results": "실험 결과", "ph": "pH", "viscosity": "점도", "evaluation_and_notes": "품평결과 및 특이사항", "change_history": "변경 이력",
        "formulation_content": "처방 내용", "total_experiment_amount_g": "총 실험량(g):", "to_100": "To 100",
        "formulation_item_tree_columns": {"phase": "구분", "code": "코드", "name": "원료명", "ratio": "함량(%)", "amount": "실험량(g)"},
        "total_ratio_label_short": "총 함량:", "total_amount_label_short": "총 실험량:",
        "experiment_name_required": "실험품명은 필수 항목입니다.",
        "log_added": "추가됨", "log_deleted": "삭제됨", "log_ratio_changed": "함량 변경", "log_changes_from_previous": "이전 버전 대비 변경사항",
        "lab_no_exists_error": "'{name}' 제품에 이미 사용 중인 'LAB NO.'입니다.\n담당번호, 실험일, 차수를 확인해주세요.", "save_error": "저장 오류",
        "formulation_saved_success": "처방 정보가 저장되었습니다.",
        "select_material_to_add": "목록에서 추가할 원료를 선택하세요.", "line_break": "줄 내림",
        "select_item_to_delete": "삭제할 항목을 선택하세요.", "select_material_for_to100": "'To 100'을 적용할 원료를 목록에서 선택하세요.",
        "cannot_apply_to_separator": "구분선에는 함량을 적용할 수 없습니다.", "ratio_exceeds_100_warning": "다른 원료의 함량 합계가 이미 100%를 초과하여, 선택된 원료의 함량을 0으로 설정합니다.",
        "client_details_format": "담당: {manager} / 연락처: {phone}",
        "export_data_confirm_title": "내보내기 데이터 확인", "import_data_confirm_title": "가져오기 데이터 확인",
        "date_format_error": "날짜 형식 오류", "invalid_date_format_warning": "'{date}'는 올바른 날짜 형식이 아닙니다. 오늘 날짜로 설정됩니다.",
        "client_error": "거래처 오류", "client_not_found_warning": "엑셀의 거래처 '{name}'를 찾을 수 없습니다.\n거래처를 직접 선택해주세요.",
        "formulation_import_success": "처방 정보를 성공적으로 불러왔습니다.", "import_formulation_confirm_msg": "엑셀 파일에서 처방을 가져옵니다.\n현재 작성 중인 내용은 모두 사라집니다. 계속하시겠습니까?",

        # Add Material Dialog
        "add_material_title": "원료 추가", "material_search": "원료 검색:", "no_ingredients_registered": "등록된 전성분이 없습니다.",
    },
    "english": {
        # Generic
        "help": "Help", "close": "Close", "save": "Save", "new": "New", "edit": "Edit", "delete": "Delete", "reset": "Reset", "search": "Search", "import": "Import", "export": "Export",
        "notification": "Notification", "warning": "Warning", "error": "Error", "success": "Success", "db_error": "Database Error", "input_error": "Input Error", "selection_error": "Selection Error", "export_error": "Export Error", "calculation_error": "Calculation Error",
        "import_confirm": "Import Confirmation", "delete_confirm": "Delete Confirmation", "dev_in_progress": "This feature is under development.", "dev_in_progress_short": "In-dev",
        "select_type": "- Select Type -", "select_client": "- Select Client -", "no_clients_found": "- No clients found -",
        "id": "ID", "code": "Code", "material_name": "Material Name", "all_ingredients": "All Ingredients", "press_button_placeholder": "Please press the button",

        # Main UI
        "menu": "MENU", "home": "Home", "document": "R&D Center", "quality": "Quality Control", "data": "Data Mgt.", "settings": "Settings", "logout": "Logout",
        "formulation_mgt": "Formulation Mgt.", "document_sub": "Documents", "ingredient_mgt": "Ingredient Mgt.", "client_mgt": "Client Mgt.", "user_mgt": "User Mgt.", "settings_sub": "Settings",
        "coa": "COA", "msds": "MSDS", "prod_standard": "Product Standard", "mfg_record": "MFG Record",

        # Settings
        "settings_tab": "Settings",
        "settings_help_title": "Settings Help",
        "settings_help_message": """
        [How to use Settings]
        This screen configures the program's operating environment.
        
        1. Theme Settings: Change the overall design theme (Light/Dark/System) of the program.
        2. Language Settings: Change the UI language for the entire program (no restart needed).
        3. Path Settings: Specify the default save/load locations for DB and Excel files.
           - When changing the DB path, you can move the existing DB file or create a new one.
           - (Only administrators can modify paths)
        """,
        "theme_settings": "Theme Settings", "language_settings": "Language", "db_path": "DB Path", "excel_path": "Excel Path",
        "browse": "Browse...", "save_paths": "Save Paths", "db_path_warning": "* DB path change will be applied on program restart.",
        "export_excel_forms": "Export Excel Forms", "export_ingredient_form": "Export Ingredient Form", "export_client_form": "Export Client Form", "export_user_form": "Export User Form",
        "data_reset_warning": "Data Reset (Warning: Cannot be undone)", "reset_ingredient_data": "Reset Ingredient Data", "reset_client_data": "Reset Client Data", "reset_user_data": "Reset User Data", "reset_all_data": "Reset All Data",

        # Data Management
        "data_mgt_help_title": "Data Management Help",
        "data_mgt_help_message": """
        [How to use Data Management]
        This screen manages the program's basic data (ingredients, clients, users).
        
        1. Ingredient Mgt. Tab: Manage detailed information of raw materials and their ingredients.
        2. Client Mgt. Tab: Manage all client information such as raw materials, OEM/ODM, etc. (Admin only)
        3. User Mgt. Tab: Manage user accounts for the program. (Admin only)
        """,
        "user_info": "User Information", "password_helper": "(Enter for new password or change)", "admin_privilege": "Admin Privilege",
        "view_selected_history": "View Selected History", "user_list": "User List", "view_all_history": "View All History",
        "export_data": "Export Data", "import_data": "Import Data",
        "user_labels": {"username": "User ID", "password": "Password", "manager_code": "Mng. Code", "position": "Position", "contact": "Contact", "zip_code": "Zip Code", "address": "Address"},
        "user_tree_columns": {"id": "ID", "username": "User ID", "manager_code": "Mng. Code", "position": "Position", "contact": "Contact", "is_admin": "Is Admin"},
        "client_info": "Client Information", "client_search": "Client Search", "client_type": "Client Type", "is_active": "Is Active", "client_list": "Client List",
        "client_type_values": ["Raw Material", "OEM/ODM", "Packaging", "Other"],
        "client_type_filter_values": ["- Select Type -", "Raw Material", "OEM/ODM", "Packaging", "Other"],
        "client_labels": {"code": "Client Code(Biz No.)", "name": "Client Name", "ceo": "CEO Name", "manager": "Manager Name", "contact": "Contact", "fax": "Fax", "email": "Email", "zip": "Zip Code", "address": "Address"},
        "client_tree_columns": {"id": "ID", "type": "Type", "code": "Client Code", "name": "Client Name", "ceo": "CEO Name", "manager": "Manager Name", "contact": "Contact", "fax": "Fax", "email": "Email", "zip": "Zip Code", "address": "Address", "active": "Is Active"},

        # Document Management
        "doc_mgt_help_title": "Formulation Management Help",
        "doc_mgt_help_message": """
        [How to use Formulation Management]
        [Formulation List Tab]
        1. Folder/File View: Each 'Experiment Name' is a folder. Click a folder to see all revisions.
        2. Create/Edit: Use 'New' button for a new formulation, or select one and click 'Edit' (or double-click).
        
        [Quotation Tab]
        1. Create Quotation: Select a formulation in 'Formulation List' tab, then go to 'Quotation' tab and click 'Create Quotation'.
        
        [Ingredient List Tab]
        1. Create Lists: Select a formulation, go to 'Ingredient List' tab, and click 'Create All Lists'.
        """,
        "formulation_folders": "Formulation Folders", "icon_size": "Icon Size:", "client_filter": "Client Filter:", "back_to_folders": "◀ Back",
        "compare_history": "Compare History", "reset_selection": "Reset Selection", "edit_sample_count": "Edit Sent", "send_sample": "Send Sample", "folder": "Folder", "formulations": "formulations",
        "select_formulation_to_edit": "Please select a formulation to edit from the list.", "select_one_formulation_to_edit": "You can only edit one formulation at a time.",
        "select_two_formulations_to_compare": "Please select two formulations to compare.", "select_folder_first": "Please select a folder first.",
        "no_formulation_data": "No formulation data found.\nPress the 'New' button to create a new formulation.",
    "formulation_tree_columns": {"id": "ID", "revision": "Revision", "manager_code": "Mng. Code", "date": "Date", "experiment_name": "Product", "lab_no": "LAB NO.", "sample_sent": "Sample Sent", "sample_delivery_date": "Delivery Date"},
        "delete_formulation_confirm_msg": "Are you sure you want to delete the selected {count} formulation(s)?", "delete_formulation_success_msg": "{count} formulation(s) have been deleted.",
        "select_formulation_to_delete": "Please select formulation(s) to delete from the list.", "delete_error_msg": "Error during deletion: {e}",
        "select_formulation_for_sample": "Please select a formulation to process for sample sending.", "send_sample_confirm": "Confirm Sample Sending", "send_sample_confirm_msg": "Do you want to increment the sample sent count for the selected formulation by 1?",
        "sample_count_updated_msg": "Sample sent count updated to {count}.", "formulation_not_found": "Selected formulation not found.", "sample_count_update_error": "Error updating sample sent count: {e}",
        "edit_sample_info_title": "Edit Sample Sending Info", "sent_count": "Sent Count:", "last_sent_date": "Last Sent Date (YYYY-MM-DD):", "sample_info_updated_success": "Sample sending information has been updated.",
        "invalid_number_date_format": "Please enter a valid number and date format (YYYY-MM-DD).", "update_error_msg": "Error during update: {ex}", "sample_count_edit_error": "Error editing sample sent count: {e}",
        "client_list_update_error": "Error updating client list: {e}",
        "create_quotation": "Create Quotation", "export_quotation": "Export Quotation", "delete_selected": "Delete Selected", "base_weight_g": "Base Weight(g):", "add_material": "Add Material", "edit_ratio": "Edit Ratio",
        "quotation_tree_columns": {"phase": "Phase", "code": "Code", "name": "Material Name", "ratio": "Ratio(%)", "unit_price": "Unit Price(KRW/kg)", "cost": "Cost(KRW)"},
        "total_ratio": "Total Ratio:", "total_raw_cost": "Total Raw Cost:", "price_with_vat": "Price with VAT(10%):", "price_with_profit": "Price with Profit(15%):",
        "select_formulation_first": "Please select a formulation from the 'Formulation List' tab first.", "quotation_creation_error": "Quotation Creation Error", "quotation_creation_error_msg": "An error occurred while creating the quotation",
        "select_item_to_edit_ratio": "Please select an item from the list to edit its ratio.", "select_item_to_delete": "Please select an item to delete from the list.", "no_quotation_to_export": "No quotation content to export. Please run 'Create Quotation' first.",
        "select_formulation_and_create_quotation": "Please select a formulation from 'Formulation List' tab and run 'Create Quotation' first.",
        "reset_formulation_ref_title": "Confirm Formulation Reference Reset", "reset_formulation_ref_confirm": "Are you sure you want to reset the material references for all formulations?\n\nThis action does not delete the formulations themselves, but changes all linked material information to a 'No Reference' state.\nThis action cannot be undone.",
        "reset_complete": "Reset Complete", "reset_formulation_ref_success": "Material references for all formulations have been reset.\n({count} items affected)", "reset_formulation_ref_error": "Error during formulation reference reset",
        "data_update_failed": "Data update failed.", "comment_updated_success": "Comment has been updated.", "edit_comment_title": "Edit Comment", "enter_comment_to_edit": "Enter the content to modify:",
        "no_data_to_export": "No data to export.", "import_journal_confirm_msg": "Import lab journal data from an Excel file.\n\nThis will update existing data based on 'LAB NO.' and add new entries if no match is found.\n\nContinue?",
        "import_journal_success_msg": "Lab journal import complete.\n- New: {added}\n- Updated: {updated}", "import_error_msg": "Error during import: {e}", # noqa
        "use_date_filter": "Use Date Filter", "year": "Year", "month": "Month", "detailed_search": "Detailed Search:", "enter_search_term": "Enter search term...",
        "journal_search_fields": ["All", "Product Name", "pH", "Viscosity", "Pin", "Lab No.", "Client"], "journal_tree_columns": {"date": "Date", "name": "Product Name", "ph": "pH", "viscosity": "Viscosity", "gravity": "Gravity", "pin": "Pin", "lab_no": "Lab No.", "client": "Client", "sample_delivery": "Sample Delivery", "comment": "Comment"},
        "no_date": "No Date",
        "create_all_lists": "Create All Lists", "export_to_excel": "Export to Excel", "select_columns_to_display": "Select Columns",
        "complex_ingredients_for_docs": "Complex Ingredients (for Docs)", "single_ingredients_by_ratio": "Single Ingredients (by Ratio)", "ingredients_for_design": "Ingredients for Design",
        "by_raw_material": "By Raw Material", "summed_ingredients": "Summed Ingredients",
    "complex_ingredient_tree_columns": {"no": {"text": "NO", "width": 40, "anchor": "center", "visible": True}, "material_name": {"text": "Material Name", "width": 200, "visible": True}, "inci_name": {"text": "INCI Name", "width": 200, "visible": True}, "name_ko": {"text": "Ingredient Name (KO)", "width": 200, "visible": True}, "rm_ratio": {"text": "RM Ratio(%)", "width": 120, "anchor": "e", "visible": True}, "ing_ratio": {"text": "Ing. Ratio(%)", "width": 120, "anchor": "e", "visible": True}, "actual_wt": {"text": "Actual Wt (%)", "width": 120, "anchor": "e", "visible": True}, "cas_no": {"text": "CAS No.", "width": 120, "visible": True}, "function": {"text": "Ingredient function", "width": 150, "visible": True}, "hs_code": {"text": "HS CODE", "width": 100, "visible": False}, "origin": {"text": "Origin", "width": 100, "visible": False}, "material_name_en": {"text": "Material Name (EN)", "width": 150, "visible": False}, "nmpa_reg_num": {"text": "NMPA", "width": 120, "visible": False}, "remark": {"text": "Remark", "width": 100, "visible": True}},
        "total_rm_ratio_label": "Total RM or ingredient % in fla:", "total_actual_wt_label": "Total Actual Wt (%):",
        "summed_ingredient_tree_columns": {"name_ko": "Name (KO)", "name_en": "Name (EN)", "cas_no": "CAS No.", "function": "Function", "total_ratio": "Total Ratio(%)"},
        "total_ratio_sum": "Total Ratio(%) Sum:", "clipboard_copy_dev": "Clipboard copy feature is under development.",
        "single_ingredient_tree_columns": {"no": {"text": "NO", "width": 40, "anchor": "center", "visible": True}, "name_en": {"text": "INGREDIENT", "width": 250, "visible": True}, "ci_no": {"text": "C.I NO", "width": 80, "visible": False}, "total_ratio": {"text": "% (W/W)", "width": 100, "anchor": "e", "visible": True}, "cas_no": {"text": "CAS. NO", "width": 120, "visible": True}, "function": {"text": "FUNCTION", "width": 150, "visible": True}, "hs_code": {"text": "HS CODE", "width": 100, "visible": False}, "nmpa_reg_num": {"text": "NMPA", "width": 120, "visible": False}, "remark": {"text": "Remark", "width": 150, "visible": False}},
        "total_ratio_ww_sum": "Total Ratio (% (W/W)) Sum:",
        "korean_ingredients": "Korean Ingredients", "english_ingredients_inci": "English Ingredients (INCI)",
        "select_formulation_and_create_list": "Please select a formulation and run 'Create All Lists' first.", "no_data_to_export_create_list": "No data to export. Please run 'Create All Lists' first.",
        "single_ingredients_korean": "Single Ingredients (Korean)", "single_ingredients_english": "Single Ingredients (English)",
        "functional_report_title": "Functional Cosmetics Exemption Report Form", "export_report": "Export Report",
        "usage_default": "Apply a proper amount to the skin evenly.", "precautions_default": "1. If you experience any symptoms such as redness, swelling, or itchiness during usage or from exposure to direct sunlight after usage, suspend use and consult a physician.\n\n2. Do not use on wounds or other areas of skin irritation.\n\n3. Storage and handling\na. Keep out of reach of children.\nb. Keep away from direct sunlight.",
        "active_substance_default": "Example:\nTotal Ethylhexyl Triazone as 4.00g\nTotal Polysilicone-15 as 3.00g", "ingredients_ratio_default": "Example:\nNiacinamide: 2g\nAdenosine: 0.04g",

        # Quality Management
        "quality_mgt_help_title": "Quality Management Help",
        "quality_mgt_help_message": """
        [How to use Quality Management]
        - COA: Manage Certificate of Analysis for semi-finished/finished products.
        - MSDS: Manage Material Safety Data Sheets.
        - Product Standard: Manage standard information for products.
        - MFG Record: Manage manufacturing history for products.
        (All features are currently under development.)
        """,
        "semi_finished_product_report": "Semi-finished Product Report",
        "semi_finished_product_report_title": "Semi-finished Product Report Information",
        "semi_product_table_headers": ["No.", "Test Item", "Specification", "Result", "Remark"],
        "semi_product_coa_fields": {}, # 이 줄을 삭제하거나 빈 딕셔너리로 남겨둡니다.
        "create_excel_report": "Create Excel Report", "form_cleared": "The input form has been cleared.", "required_fields_missing": "Please fill in all required fields (Product Name, LOT, Overall Conclusion).",
        "save_report_as": "Save Report As", "report_saved_success": "Report saved successfully", "report_generation_error": "An error occurred while generating the report",

        # Formulation Popup
        "formulation_popup_title": "Create/Edit Formulation", "formulation_details": "Formulation Details", "use_target_info": "Use Target Info",
        "target_sample_name": "Target Sample Name", "target_ph": "Target pH", "today": "Today:", "next_day": "Next Day:", "target_viscosity": "Target Viscosity",
        "pin_and_machine": "Pin & Machine", "target_client": "Target Client", "experiment_name": "Experiment Name", "experiment_date": "Experiment Date",
        "manager_name": "Manager", "manager_code": "Mng. Code", "lab_no": "LAB NO.", "revision": "Revision", "client": "Client",
        "experiment_results": "Experiment Results", "ph": "pH", "viscosity": "Viscosity", "evaluation_and_notes": "Evaluation & Notes", "change_history": "Change History",
        "formulation_content": "Formulation Content", "total_experiment_amount_g": "Total Exp. Amount(g):", "to_100": "To 100",
        "formulation_item_tree_columns": {"phase": "Phase", "code": "Code", "name": "Material Name", "ratio": "Ratio(%)", "amount": "Amount(g)"},
        "total_ratio_label_short": "Total Ratio:", "total_amount_label_short": "Total Amount:",
        "experiment_name_required": "Experiment Name is a required field.",
        "log_added": "Added", "log_deleted": "Deleted", "log_ratio_changed": "Ratio changed", "log_changes_from_previous": "Changes from previous version",
        "lab_no_exists_error": "'LAB NO.' is already in use for product '{name}'.\nPlease check Manager Code, Date, and Revision.", "save_error": "Save Error",
        "formulation_saved_success": "Formulation information has been saved.",
        "select_material_to_add": "Please select a material to add from the list.", "line_break": "Line Break",
        "select_item_to_delete": "Please select an item to delete.", "select_material_for_to100": "Please select a material from the list to apply 'To 100'.",
        "cannot_apply_to_separator": "Cannot apply ratio to a separator line.", "ratio_exceeds_100_warning": "The sum of other material ratios already exceeds 100%. Setting the selected material's ratio to 0.",
        "client_details_format": "Manager: {manager} / Contact: {phone}",
        "export_data_confirm_title": "Confirm Export Data", "import_data_confirm_title": "Confirm Import Data",
        "date_format_error": "Date Format Error", "invalid_date_format_warning": "'{date}' is not a valid date format. Setting to today's date.",
        "client_error": "Client Error", "client_not_found_warning": "Client '{name}' from Excel not found.\nPlease select a client manually.",
        "formulation_import_success": "Successfully imported formulation information.", "import_formulation_confirm_msg": "Import formulation from an Excel file.\nAll current content will be lost. Continue?",

        # Add Material Dialog
        "add_material_title": "Add Material", "material_search": "Material Search:", "no_ingredients_registered": "No ingredients registered.",
    }
}

def get_texts(language):
    """지정된 언어에 대한 텍스트 딕셔너리를 반환합니다."""
    return TRANSLATIONS.get(language, TRANSLATIONS["korean"])
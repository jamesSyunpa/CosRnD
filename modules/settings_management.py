# modules/settings_management.py
import customtkinter as ctk
from tkinter import messagebox, filedialog
import configparser
import os
import shutil
import subprocess
from datetime import datetime
from database.db_manager import db_manager, SCHEMA_VERSION
from database.models import Base, Formulation, FormulationItem, Material, Client, User
from sqlalchemy import create_engine, text, inspect
from modules.ui_components import HelpPopup
from utils import center_window_on_mouse_display
from utils.update_manager import UpdateManager, UpdateDialog
from modules.translation import get_texts
from modules import excel_handler

class DBPathOptionsDialog(ctk.CTkToplevel):
    """DB 경로 설정 시 관리자에게 옵션을 제공하는 대화상자"""
    def __init__(self, master):
        super().__init__(master)
        self.title("DB 설정 옵션")
        self.geometry("450x250")
        self.transient(master)
        self.grab_set()
        self.resizable(False, False)

        self._choice = ""

        main_frame = ctk.CTkFrame(self, fg_color="transparent")
        main_frame.pack(padx=20, pady=20, fill="both", expand=True)

        label = ctk.CTkLabel(main_frame, text="새로운 공유 DB 경로에 대한 작업을 선택하세요:", font=ctk.CTkFont(size=14, weight="bold"))
        label.pack(pady=(0, 15), anchor="w")

        self.radio_var = ctk.StringVar(value="use")

        radio_1 = ctk.CTkRadioButton(main_frame, text="경로에 있는 기존 DB 사용하기", variable=self.radio_var, value="use")
        radio_1.pack(anchor="w", pady=5)

        radio_2 = ctk.CTkRadioButton(main_frame, text="새로운 DB 생성하기 (비어있음)", variable=self.radio_var, value="create")
        radio_2.pack(anchor="w", pady=5)

        radio_3 = ctk.CTkRadioButton(main_frame, text="현재 DB를 지정 경로로 이동하기", variable=self.radio_var, value="move")
        radio_3.pack(anchor="w", pady=5)

        button_frame = ctk.CTkFrame(self, fg_color="transparent")
        button_frame.pack(pady=(0, 20))

        confirm_button = ctk.CTkButton(button_frame, text="확인", command=self._on_confirm)
        confirm_button.pack(side="left", padx=10)

        cancel_button = ctk.CTkButton(button_frame, text="취소", command=self._on_cancel, fg_color="gray")
        cancel_button.pack(side="left", padx=10)
        try:
            center_window_on_mouse_display(self)
        except Exception:
            pass
        self.wait_window()

    def _on_confirm(self):
        self._choice = self.radio_var.get()
        self.destroy()

    def _on_cancel(self):
        self._choice = None
        self.destroy()

    def get_choice(self):
        return self._choice

class SettingsManagementFrame(ctk.CTkFrame):
    def __init__(self, master, current_user, app, config_path, application_path):
        super().__init__(master)
        self.current_user = current_user
        self.app = app
        self.config_path = config_path
        self.application_path = application_path
        self.texts = get_texts(self.app.language)

        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(0, weight=1)

        top_frame = ctk.CTkFrame(self, fg_color="transparent")
        top_frame.grid(row=0, column=0, sticky="nsew")
        top_frame.grid_columnconfigure(0, weight=1)
        top_frame.grid_rowconfigure(0, weight=1)
        self.tab_view = ctk.CTkTabview(top_frame, anchor="center", command=self.on_tab_change)
        self.tab_view.grid(row=0, column=0, sticky="nsew", padx=10, pady=10)

        self.help_button = ctk.CTkButton(top_frame, text="도움말", width=80, command=self.show_help)
        self.help_button.place(relx=0.98, y=10, anchor="ne")

        # Maintain a mapping between internal tab keys (stable identifiers)
        # and the displayed tab labels (localized). This allows other modules
        # to request a tab using a stable key like 'settings_sub'.
        self.tab_key_map = {}

        tab_key = 'settings_sub'
        tab_label = self.texts.get(tab_key, "설정")
        self.tab_key_map[tab_key] = tab_label
        self.tab_view.add(tab_label)
        self.setup_settings_tab(self.tab_view.tab(tab_label))

    def show_help(self):
        title = "설정 관리 도움말"
        message = self.texts.get('settings_help_message_admin' if self.current_user.is_admin else 'settings_help_message_user', "")
        HelpPopup(self, title, message)

    def on_tab_change(self):
        selected_tab = self.tab_view.get()
        # Try to find a stable action key for the selected (localized) tab label.
        found_key = None
        for k, v in getattr(self.app, 'ACTION_CONFIG', {}).items():
            if k.startswith('settings/'):
                title = v.get('title')
                if title == selected_tab:
                    found_key = k
                    break

        if found_key:
            self.app.record_action(found_key)
        else:
            # Fallback: record with the literal selected tab label
            self.app.record_action(f"settings/{selected_tab}")

    def switch_to_tab(self, tab_name):
        """Accept either a stable tab key (e.g. 'settings_sub') or the
        displayed localized tab label (e.g. '설정')."""
        try:
            # First, try to set using the provided name directly (may be the label)
            self.tab_view.set(tab_name)
            return
        except Exception:
            pass

        # If direct set failed, attempt to resolve as an internal key -> label
        resolved_label = None
        if tab_name in self.tab_key_map:
            resolved_label = self.tab_key_map[tab_name]
        else:
            # Maybe caller passed a full action like 'settings/settings_sub'
            if '/' in tab_name:
                _, maybe_key = tab_name.split('/', 1)
                resolved_label = self.tab_key_map.get(maybe_key)

        if resolved_label:
            try:
                self.tab_view.set(resolved_label)
                return
            except Exception:
                pass

        # As a last resort, try to set by looking for a matching title in ACTION_CONFIG
        for k, v in getattr(self.app, 'ACTION_CONFIG', {}).items():
            if k.startswith('settings/') and (v.get('title') == tab_name or v.get('title') == resolved_label):
                try:
                    self.tab_view.set(v.get('title'))
                    return
                except Exception:
                    break

        # If we reach here, no matching tab was found; log for debugging.
        print(f"[경고] SettingsManagementFrame: 탭을 찾을 수 없음: '{tab_name}'")

    def change_appearance_mode_event(self, new_appearance_mode: str):
        ctk.set_appearance_mode(new_appearance_mode)
        self.app.update_treeview_style()
        self._save_config('Appearance', 'theme', new_appearance_mode.lower())

    def change_language_event(self, new_language: str):
        lang_code = 'korean' if new_language.lower() == 'korean' else 'english'
        self.app.language = lang_code
        self._save_config('Appearance', 'language', lang_code)
        self.app.recreate_main_ui()

    def change_sync_mode_event(self, selected_mode: str):
        """동기화 알림 모드(배지 알림/끄기) 변경 시 config.ini에 저장합니다."""
        mode_code = "badge" if "배지" in selected_mode else "disabled"
        self._save_config('Sync', 'mode', mode_code)
        print(f"[Settings] 동기화 알림 모드 변경 저장됨: {mode_code}")

    def change_sync_interval_event(self, selected_interval: str):
        """동기화 확인 주기 변경 시 config.ini에 초 단위로 저장합니다."""
        if "1분" in selected_interval:
            sec = 60
        elif "3분" in selected_interval:
            sec = 180
        elif "5분" in selected_interval:
            sec = 300
        elif "10분" in selected_interval:
            sec = 600
        else:
            sec = 60
        self._save_config('Sync', 'check_interval_sec', str(sec))
        print(f"[Settings] 동기화 확인 주기 변경 저장됨: {sec}초")

    def sync_db_now_event(self):
        """연구원이 [지금 즉시 최신 데이터 불러오기] 클릭 시 즉시 실시간 동기화를 수행합니다."""
        try:
            self.sync_now_btn.configure(state="disabled", text="⏳ 동기화 중...")
            self.update_idletasks()

            config = configparser.ConfigParser(interpolation=None)
            config.read(self.config_path, encoding='utf-8')
            shared_db_path = config.get('Paths', 'shared_db_path', fallback=None)

            if not shared_db_path:
                messagebox.showwarning("동기화 안내", "공유 DB 경로가 설정되어 있지 않습니다.", parent=self)
                self.sync_now_btn.configure(state="normal", text="⚡ 지금 즉시 최신 데이터 불러오기")
                return

            if hasattr(self.app, 'sync_with_shared_db_safe'):
                success = self.app.sync_with_shared_db_safe(shared_db_path, show_success_popup=True)
            else:
                success = False

            self.sync_now_btn.configure(state="normal", text="⚡ 지금 즉시 최신 데이터 불러오기")
        except Exception as e:
            self.sync_now_btn.configure(state="normal", text="⚡ 지금 즉시 최신 데이터 불러오기")
            messagebox.showerror("동기화 오류", f"실시간 동기화 중 오류가 발생했습니다: {e}", parent=self)

    def change_update_mode_event(self, selected_mode: str):
        """업데이트 모드(자동/수동) 변경 시 config.ini에 저장합니다."""
        mode_code = "auto" if "자동" in selected_mode else "manual"
        UpdateManager.save_update_mode(mode_code)
        self._save_config('Update', 'mode', mode_code)
        print(f"[Settings] 업데이트 모드 변경 저장됨: {mode_code}")

    def check_update_now_event(self):
        """수동으로 최신 버전을 즉시 확인하고 결과를 팝업으로 안내합니다."""
        self.check_update_btn.configure(state="disabled", text="⏳ 확인 중...")

        def _worker():
            try:
                is_available, cur_ver, lat_ver, info = UpdateManager.check_for_remote_update()
            except Exception as e:
                is_available, cur_ver, lat_ver, info = False, UpdateManager.get_current_version(), UpdateManager.get_current_version(), {"summary": f"확인 중 오류: {e}"}

            def _show():
                try:
                    self.check_update_btn.configure(state="normal", text="🔍 지금 최신 버전 확인")
                    UpdateDialog(self.winfo_toplevel(), cur_ver, lat_ver, info, is_new=is_available)
                except Exception as ex:
                    print(f"[Settings] 업데이트 다이얼로그 팝업 오류: {ex}")

            self.after(0, _show)

        import threading
        threading.Thread(target=_worker, daemon=True).start()

    def setup_settings_tab(self, tab_frame):
        scrollable_frame = ctk.CTkScrollableFrame(tab_frame, fg_color="transparent")
        scrollable_frame.pack(fill="both", expand=True)
        scrollable_frame.grid_columnconfigure(0, weight=1)

        # --- UI 설정 ---
        ui_frame = ctk.CTkFrame(scrollable_frame)
        ui_frame.grid(row=0, column=0, padx=20, pady=20, sticky="ew")
        ui_frame.grid_columnconfigure(1, weight=1)

        ctk.CTkLabel(ui_frame, text="테마 설정").grid(row=0, column=0, padx=10, pady=10, sticky="w")
        self.theme_menu = ctk.CTkOptionMenu(ui_frame, values=["Light", "Dark", "System"], command=self.change_appearance_mode_event)
        self.theme_menu.grid(row=0, column=1, padx=10, pady=10, sticky="w")

        ctk.CTkLabel(ui_frame, text="언어 설정").grid(row=1, column=0, padx=10, pady=10, sticky="w")
        self.language_menu = ctk.CTkOptionMenu(ui_frame, values=["Korean", "English"], command=self.change_language_event)
        self.language_menu.grid(row=1, column=1, padx=10, pady=10, sticky="w")

        # --- 경로 설정 ---
        # --- 경로 설정 ---
        path_frame = ctk.CTkFrame(scrollable_frame)
        path_frame.grid(row=1, column=0, padx=20, pady=(0, 20), sticky="ew")
        path_frame.grid_columnconfigure(1, weight=1)

        ctk.CTkLabel(path_frame, text="공유 DB 경로", font=ctk.CTkFont(weight="bold")).grid(row=0, column=0, padx=10, pady=10, sticky="w")
        self.db_path_entry = ctk.CTkEntry(path_frame)
        self.db_path_entry.grid(row=0, column=1, padx=10, pady=10, sticky="ew")
        db_browse_button = ctk.CTkButton(path_frame, text="찾아보기", width=90, command=self.browse_db_path)
        db_browse_button.grid(row=0, column=2, padx=10, pady=10)

        ctk.CTkLabel(path_frame, text="엑셀 저장 경로", font=ctk.CTkFont(weight="bold")).grid(row=1, column=0, padx=10, pady=10, sticky="w")
        self.excel_path_entry = ctk.CTkEntry(path_frame)
        self.excel_path_entry.grid(row=1, column=1, padx=10, pady=10, sticky="ew")
        excel_browse_button = ctk.CTkButton(path_frame, text="찾아보기", width=90, command=self.browse_excel_path)
        excel_browse_button.grid(row=1, column=2, padx=10, pady=10)

        ctk.CTkLabel(path_frame, text="백업 저장 경로", font=ctk.CTkFont(weight="bold")).grid(row=2, column=0, padx=10, pady=10, sticky="w")
        self.backup_path_entry = ctk.CTkEntry(path_frame)
        self.backup_path_entry.grid(row=2, column=1, padx=10, pady=10, sticky="ew")
        backup_browse_button = ctk.CTkButton(path_frame, text="찾아보기", width=90, command=self.browse_backup_path)
        backup_browse_button.grid(row=2, column=2, padx=10, pady=10)

        # 경로 저장 버튼
        save_button = ctk.CTkButton(
            path_frame, 
            text="💾 경로 설정 저장 및 재시작", 
            fg_color="#0284C7",
            hover_color="#0369A1",
            font=ctk.CTkFont(weight="bold"),
            command=self.save_paths
        )
        save_button.grid(row=3, column=1, columnspan=2, pady=(5, 12), padx=10, sticky="e")

        # --- 공유 데이터베이스 동기화 설정 ---
        sync_cfg_frame = ctk.CTkFrame(scrollable_frame)
        sync_cfg_frame.grid(row=2, column=0, padx=20, pady=(0, 20), sticky="ew")
        sync_cfg_frame.grid_columnconfigure(1, weight=1)

        ctk.CTkLabel(sync_cfg_frame, text="🔄 공유 DB 실시간 동기화", font=ctk.CTkFont(size=14, weight="bold")).grid(row=0, column=0, columnspan=3, padx=10, pady=(10, 6), sticky="w")

        ctk.CTkLabel(sync_cfg_frame, text="알림 방식", font=ctk.CTkFont(weight="bold")).grid(row=1, column=0, padx=10, pady=6, sticky="w")
        self.sync_mode_segmented = ctk.CTkSegmentedButton(
            sync_cfg_frame,
            values=["조용한 배지 알림 (권장)", "알림 끄기 (수동)"],
            command=self.change_sync_mode_event,
            height=28
        )
        self.sync_mode_segmented.grid(row=1, column=1, padx=10, pady=6, sticky="w")

        ctk.CTkLabel(sync_cfg_frame, text="확인 주기", font=ctk.CTkFont(weight="bold")).grid(row=2, column=0, padx=10, pady=6, sticky="w")
        self.sync_interval_menu = ctk.CTkOptionMenu(
            sync_cfg_frame,
            values=["1분마다 (권장)", "3분마다", "5분마다", "10분마다"],
            command=self.change_sync_interval_event,
            width=160
        )
        self.sync_interval_menu.grid(row=2, column=1, padx=10, pady=6, sticky="w")

        self.sync_now_btn = ctk.CTkButton(
            sync_cfg_frame,
            text="⚡ 지금 즉시 최신 데이터 불러오기",
            fg_color="#059669",
            hover_color="#047857",
            font=ctk.CTkFont(weight="bold"),
            command=self.sync_db_now_event
        )
        self.sync_now_btn.grid(row=2, column=2, padx=10, pady=6, sticky="e")

        # --- 소프트웨어 업데이트 설정 ---
        update_cfg_frame = ctk.CTkFrame(scrollable_frame)
        update_cfg_frame.grid(row=3, column=0, padx=20, pady=(0, 20), sticky="ew")
        update_cfg_frame.grid_columnconfigure(1, weight=1)

        ctk.CTkLabel(update_cfg_frame, text="업데이트 방식", font=ctk.CTkFont(weight="bold")).grid(row=0, column=0, padx=10, pady=10, sticky="w")
        
        self.update_mode_segmented = ctk.CTkSegmentedButton(
            update_cfg_frame,
            values=["자동 업데이트 (권장)", "수동 업데이트"],
            command=self.change_update_mode_event,
            height=28
        )
        self.update_mode_segmented.grid(row=0, column=1, padx=10, pady=10, sticky="w")

        curr_ver = UpdateManager.get_current_version()
        self.update_ver_lbl = ctk.CTkLabel(
            update_cfg_frame, 
            text=f"현재 버전: {curr_ver} (럭포마 공식 배포판)", 
            font=ctk.CTkFont(size=12), 
            text_color=("gray30", "gray75")
        )
        self.update_ver_lbl.grid(row=1, column=0, padx=10, pady=(0, 10), sticky="w")

        btn_box = ctk.CTkFrame(update_cfg_frame, fg_color="transparent")
        btn_box.grid(row=1, column=1, padx=10, pady=(0, 10), sticky="w")

        self.check_update_btn = ctk.CTkButton(
            btn_box,
            text="🔍 지금 최신 버전 확인",
            width=150,
            height=26,
            fg_color="#2563eb",
            hover_color="#1d4ed8",
            command=self.check_update_now_event
        )
        self.check_update_btn.pack(side="left")

        # --- DB 백업 / 복원 & 데이터 관리 섹션 ---
        self.setup_db_backup_restore_section(scrollable_frame)

        # --- 관리자 전용 기능 ---
        if self.current_user.is_admin:
            self.setup_admin_only_features(scrollable_frame)

        self.load_settings()

    def setup_db_backup_restore_section(self, parent_frame):
        """데이터 백업, 전체 불러오기(복원), 검증 섹션을 설정합니다."""
        backup_section = ctk.CTkFrame(parent_frame)
        backup_section.grid(row=3, column=0, padx=20, pady=(0, 20), sticky="ew")
        backup_section.grid_columnconfigure((0, 1, 2), weight=1)
        
        header_box = ctk.CTkFrame(backup_section, fg_color="transparent")
        header_box.grid(row=0, column=0, columnspan=3, padx=15, pady=(12, 6), sticky="ew")
        
        ctk.CTkLabel(
            header_box, 
            text="🛡️ 데이터베이스 백업 및 복원 (전체 불러오기)", 
            font=ctk.CTkFont(size=14, weight="bold")
        ).pack(side="left")
        
        ctk.CTkLabel(
            backup_section,
            text="현재 모든 연구 데이터(처방, 원료, 거래처, 사용자 등)를 안전하게 백업하거나 백업 파일에서 복원합니다.",
            font=ctk.CTkFont(size=11),
            text_color=("gray40", "gray70")
        ).grid(row=1, column=0, columnspan=3, padx=15, pady=(0, 10), sticky="w")
        
        # 1. 지금 백업하기 버튼
        backup_now_btn = ctk.CTkButton(
            backup_section,
            text="💾 지금 데이터 백업하기",
            height=34,
            font=ctk.CTkFont(weight="bold"),
            fg_color="#059669",
            hover_color="#047857",
            command=self.backup_current_db_now
        )
        backup_now_btn.grid(row=2, column=0, padx=(15, 6), pady=(0, 12), sticky="ew")

        # 2. 백업 파일에서 데이터 모두 불러오기 (복원) 버튼
        restore_btn = ctk.CTkButton(
            backup_section,
            text="📥 백업 데이터 모두 불러오기",
            height=34,
            font=ctk.CTkFont(weight="bold"),
            fg_color="#D97706",
            hover_color="#B45309",
            command=self.restore_db_from_backup
        )
        restore_btn.grid(row=2, column=1, padx=6, pady=(0, 12), sticky="ew")

        # 3. 백업 폴더 열기 & DB 검증 버튼 박스
        sub_btn_box = ctk.CTkFrame(backup_section, fg_color="transparent")
        sub_btn_box.grid(row=2, column=2, padx=(6, 15), pady=(0, 12), sticky="ew")
        sub_btn_box.grid_columnconfigure((0, 1), weight=1)

        open_folder_btn = ctk.CTkButton(
            sub_btn_box,
            text="📂 백업 폴더 열기",
            height=34,
            fg_color="gray50",
            hover_color="gray40",
            command=self.open_backup_folder
        )
        open_folder_btn.grid(row=0, column=0, padx=(0, 4), sticky="ew")

        validate_button = ctk.CTkButton(
            sub_btn_box,
            text="🔍 DB 검증",
            height=34,
            fg_color="#1565C0",
            hover_color="#1976D2",
            command=self.validate_current_db_path
        )
        validate_button.grid(row=0, column=1, padx=(4, 0), sticky="ew")

    def setup_admin_only_features(self, parent_frame):
        # --- 엑셀 폼 내보내기 ---
        export_frame = ctk.CTkFrame(parent_frame)
        export_frame.grid(row=4, column=0, padx=20, pady=(20, 10), sticky="ew")
        export_frame.grid_columnconfigure((0, 1, 2, 3), weight=1)
        ctk.CTkLabel(export_frame, text="엑셀 폼 내보내기", font=ctk.CTkFont(weight="bold")).grid(row=0, column=0, columnspan=4, pady=(10, 5))
        ctk.CTkButton(export_frame, text="원료 템플릿", command=self.export_material_template).grid(row=1, column=0, padx=5, pady=10, sticky="ew")
        ctk.CTkButton(export_frame, text="거래처 템플릿", command=self.export_client_template).grid(row=1, column=1, padx=5, pady=10, sticky="ew")
        ctk.CTkButton(export_frame, text="사용자 템플릿", command=self.export_user_template).grid(row=1, column=2, padx=5, pady=10, sticky="ew")
        ctk.CTkButton(export_frame, text="처방 템플릿", command=self.export_formulation_template).grid(row=1, column=3, padx=5, pady=10, sticky="ew")

        # --- 마스터 보안 복구 센터 (오직 최고 마스터/대표 전용 - 일반 관리자 및 직원은 완전 은닉) ---
        is_master_owner = (getattr(self.current_user, 'role', '') == 'MSAD') or (getattr(self.current_user, 'username', '').lower() in ['admin', 'master', 'ceo'])
        
        if is_master_owner:
            recovery_frame = ctk.CTkFrame(parent_frame, fg_color="#1E293B")
            recovery_frame.grid(row=5, column=0, padx=20, pady=(20, 10), sticky="ew")
            recovery_frame.grid_columnconfigure(0, weight=1)
            ctk.CTkLabel(recovery_frame, text="🛡️ 마스터 보안 데이터 복구 센터 (대표 전용)", font=ctk.CTkFont(size=14, weight="bold"), text_color="#38BDF8").grid(row=0, column=0, pady=(10, 2))
            ctk.CTkLabel(recovery_frame, text="각 PC의 AppData 심층 은닉 볼트에 암호화 보관된 삭제 데이터(처방/원료/거래처/사용자/DB)를 대표 마스터키로 완벽 복구합니다.", font=ctk.CTkFont(size=11), text_color="#94A3B8").grid(row=1, column=0, pady=(0, 8))
            
            master_recovery_btn = ctk.CTkButton(
                recovery_frame,
                text="🔑 대표 마스터 인증 및 데이터 복구 센터 열기",
                command=self.open_master_recovery_vault,
                fg_color="#0284C7",
                hover_color="#0369A1",
                height=36,
                font=ctk.CTkFont(weight="bold")
            )
            master_recovery_btn.grid(row=2, column=0, padx=20, pady=(0, 12), sticky="ew")

        # --- 데이터 리셋 ---
        reset_frame = ctk.CTkFrame(parent_frame)
        reset_frame.grid(row=6, column=0, padx=20, pady=(40, 20), sticky="ew")
        reset_frame.grid_columnconfigure((0, 1, 2, 3), weight=1)
        ctk.CTkLabel(reset_frame, text="데이터 초기화", font=ctk.CTkFont(weight="bold")).grid(row=0, column=0, columnspan=4, pady=(10, 5))
        reset_button_style = {"fg_color": "#D32F2F", "hover_color": "#B71C1C"}
        ctk.CTkButton(reset_frame, text="원료 데이터", command=lambda: self.confirm_reset("materials"), **reset_button_style).grid(row=1, column=0, padx=5, pady=10, sticky="ew")
        ctk.CTkButton(reset_frame, text="거래처 데이터", command=lambda: self.confirm_reset("clients"), **reset_button_style).grid(row=1, column=1, padx=5, pady=10, sticky="ew")
        ctk.CTkButton(reset_frame, text="사용자 데이터", command=lambda: self.confirm_reset("users"), **reset_button_style).grid(row=1, column=2, padx=5, pady=10, sticky="ew")
        all_reset_style = {"fg_color": "#B71C1C", "hover_color": "#7f0000"}
        ctk.CTkButton(reset_frame, text="전체 데이터", command=lambda: self.confirm_reset("all"), **all_reset_style).grid(row=1, column=3, padx=5, pady=10, sticky="ew")

    def open_master_recovery_vault(self):
        """마스터키 인증 후 복구 센터 팝업 대화상자를 엽니다. (대표 권한 엄격 검증)"""
        # 1차 권한 검증: 오직 최고 마스터(MSAD / admin / master)만 실행 가능
        is_master_owner = (getattr(self.current_user, 'role', '') == 'MSAD') or (getattr(self.current_user, 'username', '').lower() in ['admin', 'master', 'ceo'])
        if not is_master_owner:
            messagebox.showerror("접근 거부", "이 기능은 최고 대표 관리자(MSAD) 전용 보안 기능입니다.\n접근 권한이 없습니다.", parent=self)
            return

        # 2차 마스터키 입력 다이얼로그
        key_dialog = ctk.CTkInputDialog(text="대표 마스터 보안 복구키 (Master Secret Key)를 입력하세요:\n(대표 본인 로그인 비밀번호 또는 마스터키)", title="대표 마스터 보안 인증")
        entered_key = key_dialog.get_input()
        
        if not entered_key:
            return

        # 마스터키 검증: 대표 본인의 로그인 비밀번호 또는 마스터키
        is_valid = False
        if entered_key.strip() in ["master777!", "luxforma2026!", "admin"]:
            is_valid = True
        elif hasattr(self.current_user, 'password'):
            import bcrypt
            try:
                if bcrypt.checkpw(entered_key.encode('utf-8'), self.current_user.password.encode('utf-8')):
                    is_valid = True
            except Exception:
                pass

        if not is_valid:
            messagebox.showerror("인증 실패", "대표 마스터 보안 복구키가 올바르지 않습니다.\n접근이 거부되었습니다.", parent=self)
            return

        # 마스터 복구 대화상자 열기
        try:
            from master_recovery_suite import MasterRecoveryDialog
            MasterRecoveryDialog(self, current_user=self.current_user, app=self.app)
        except Exception as e:
            messagebox.showerror("오류", f"복구 센터를 여는 중 오류 발생: {e}", parent=self)

    def load_settings(self):
        config = configparser.ConfigParser()
        config.read(self.config_path, encoding='utf-8')
        
        theme = config.get('Appearance', 'theme', fallback='system').capitalize()
        self.theme_menu.set(theme)

        language = config.get('Appearance', 'language', fallback='korean').capitalize()
        self.language_menu.set(language)

        appdata_root = os.getenv('APPDATA', os.path.join(os.path.expanduser('~'), 'AppData', 'Roaming'))
        default_db = os.path.join(appdata_root, 'CosRQD', 'Data').replace('\\', '/')
        default_excel = os.path.join(os.path.expanduser('~'), 'Documents', 'CosRQD', 'ExcelData').replace('\\', '/')
        default_backup = os.path.join(appdata_root, 'CosRQD', 'backup').replace('\\', '/')

        db_path = config.get('Paths', 'shared_db_path', fallback=default_db)
        excel_path = config.get('Paths', 'excel_dir', fallback=default_excel)
        backup_path = config.get('Paths', 'backup_dir', fallback=default_backup)
        
        # 만약 기존 설정이 CosRnD로 되어 있으면 표시 시 CosRQD로 기본 정돈
        if 'CosRnD' in db_path and not os.path.exists(db_path):
            db_path = db_path.replace('CosRnD', 'CosRQD')
        if 'CosRnD' in excel_path and not os.path.exists(excel_path):
            excel_path = excel_path.replace('CosRnD', 'CosRQD')

        self.db_path_entry.delete(0, 'end')
        self.db_path_entry.insert(0, db_path)
        
        self.excel_path_entry.delete(0, 'end')
        self.excel_path_entry.insert(0, excel_path)

        if hasattr(self, 'backup_path_entry'):
            self.backup_path_entry.delete(0, 'end')
            self.backup_path_entry.insert(0, backup_path)

        # 공유 DB 동기화 설정 불러오기
        try:
            sync_mode = config.get('Sync', 'mode', fallback='badge')
            if hasattr(self, 'sync_mode_segmented'):
                self.sync_mode_segmented.set("조용한 배지 알림 (권장)" if sync_mode != 'disabled' else "알림 끄기 (수동)")
            
            sync_interval_sec = config.getint('Sync', 'check_interval_sec', fallback=60)
            if hasattr(self, 'sync_interval_menu'):
                if sync_interval_sec <= 60:
                    self.sync_interval_menu.set("1분마다 (권장)")
                elif sync_interval_sec <= 180:
                    self.sync_interval_menu.set("3분마다")
                elif sync_interval_sec <= 300:
                    self.sync_interval_menu.set("5분마다")
                else:
                    self.sync_interval_menu.set("10분마다")
        except Exception as sync_err:
            print(f"[Settings] 동기화 설정 로딩 실패: {sync_err}")

        # 업데이트 모드 불러오기
        try:
            update_mode = UpdateManager.get_update_mode()
            if hasattr(self, 'update_mode_segmented'):
                self.update_mode_segmented.set("자동 업데이트 (권장)" if update_mode == 'auto' else "수동 업데이트")
            if hasattr(self, 'update_ver_lbl'):
                self.update_ver_lbl.configure(text=f"현재 버전: {UpdateManager.get_current_version()} (럭포마 공식 배포판)")
        except Exception as up_err:
            print(f"[Settings] 업데이트 모드 로딩 실패: {up_err}")

    def browse_db_path(self):
        path = filedialog.askdirectory(title="공유 DB 경로 선택")
        if path:
            self.db_path_entry.delete(0, 'end')
            self.db_path_entry.insert(0, path)

    def browse_excel_path(self):
        path = filedialog.askdirectory(title="엑셀 저장 기본 경로 선택")
        if path:
            self.excel_path_entry.delete(0, 'end')
            self.excel_path_entry.insert(0, path)

    def browse_backup_path(self):
        path = filedialog.askdirectory(title="백업 저장 폴더 선택")
        if path:
            self.backup_path_entry.delete(0, 'end')
            self.backup_path_entry.insert(0, path)

    def open_backup_folder(self):
        """백업 폴더를 탐색기에서 엽니다."""
        backup_dir = self.backup_path_entry.get().strip() if hasattr(self, 'backup_path_entry') else ""
        if not backup_dir or backup_dir == "미설정":
            appdata_root = os.getenv('APPDATA', os.path.join(os.path.expanduser('~'), 'AppData', 'Roaming'))
            backup_dir = os.path.join(appdata_root, 'CosRQD', 'backup')
        
        os.makedirs(backup_dir, exist_ok=True)
        try:
            if sys.platform.startswith('win'):
                os.startfile(os.path.normpath(backup_dir))
            else:
                subprocess.Popen(['open', backup_dir])
        except Exception as e:
            messagebox.showerror("오류", f"백업 폴더를 여는 중 오류 발생: {e}", parent=self)

    def backup_current_db_now(self):
        """현재 활성화된 DB 파일을 백업 폴더에 타임스탬프와 함께 즉시 백업합니다."""
        try:
            cur_db = getattr(db_manager, 'db_path', None)
            if not cur_db or not os.path.exists(cur_db):
                cur_db = db_manager.get_local_db_path()
                
            if not cur_db or not os.path.exists(cur_db):
                messagebox.showerror("백업 실패", "현재 활성화된 데이터베이스 파일을 찾을 수 없습니다.", parent=self)
                return

            backup_dir = self.backup_path_entry.get().strip() if hasattr(self, 'backup_path_entry') else ""
            if not backup_dir or backup_dir == "미설정":
                appdata_root = os.getenv('APPDATA', os.path.join(os.path.expanduser('~'), 'AppData', 'Roaming'))
                backup_dir = os.path.join(appdata_root, 'CosRQD', 'backup')
            
            os.makedirs(backup_dir, exist_ok=True)

            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            backup_filename = f"cosmetic_backup_{timestamp}.db"
            backup_filepath = os.path.join(backup_dir, backup_filename)

            # SQLite WAL 체크포인트 커밋 후 안전 복사
            try:
                if db_manager.engine:
                    with db_manager.engine.connect() as conn:
                        conn.execute(text("PRAGMA wal_checkpoint(TRUNCATE)"))
            except Exception:
                pass

            shutil.copy2(cur_db, backup_filepath)
            
            # config.ini에 backup_dir 갱신
            self._save_config('Paths', 'backup_dir', backup_dir)

            res = messagebox.askyesno(
                "데이터 백업 성공",
                f"데이터베이스 백업이 안전하게 완료되었습니다!\n\n"
                f"📁 백업 파일명: {backup_filename}\n"
                f"📂 저장 위치: {backup_dir}\n\n"
                f"지금 백업 폴더를 확인하시겠습니까?",
                parent=self
            )
            if res:
                self.open_backup_folder()
        except Exception as e:
            messagebox.showerror("백업 오류", f"데이터 백업 도중 오류가 발생했습니다:\n{e}", parent=self)

    def restore_db_from_backup(self):
        """백업 DB 파일을 선택하여 현재 데이터베이스로 전체 복원(모두 불러오기)합니다."""
        try:
            backup_dir = self.backup_path_entry.get().strip() if hasattr(self, 'backup_path_entry') else ""
            if not backup_dir or not os.path.exists(backup_dir):
                appdata_root = os.getenv('APPDATA', os.path.join(os.path.expanduser('~'), 'AppData', 'Roaming'))
                backup_dir = os.path.join(appdata_root, 'CosRQD', 'backup')
                os.makedirs(backup_dir, exist_ok=True)

            selected_file = filedialog.askopenfilename(
                title="불러올 백업 데이터베이스 파일(.db) 선택",
                initialdir=backup_dir,
                filetypes=[("SQLite DB 파일", "*.db;*.sqlite;*.bak"), ("모든 파일", "*.*")],
                parent=self
            )

            if not selected_file or not os.path.exists(selected_file):
                return

            # 복원 확인 경고창
            confirm = messagebox.askyesno(
                "데이터 복원 (전체 불러오기) 확인",
                f"선택한 백업 파일에서 모든 연구 데이터를 복원하시겠습니까?\n\n"
                f"선택된 파일: {os.path.basename(selected_file)}\n\n"
                f"⚠️ 주의: 현재 데이터는 복원 직전 세이프티 백업 파일로 자동 보존된 후 교체됩니다.\n"
                f"복원 완료 후 프로그램이 자동으로 재시작됩니다.",
                parent=self
            )
            if not confirm:
                return

            cur_db = getattr(db_manager, 'db_path', None)
            if not cur_db:
                cur_db = db_manager.get_local_db_path()

            # 1. 복원 전 현재 DB 세이프티 백업
            if os.path.exists(cur_db):
                safety_backup = f"{cur_db}.safety_backup_{int(datetime.now().timestamp())}.bak"
                try:
                    shutil.copy2(cur_db, safety_backup)
                    print(f"[복원] 복원 전 안전 백업 완료: {safety_backup}")
                except Exception as b_err:
                    print(f"[복원] 안전 백업 실패(계속 진행): {b_err}")

            # 2. DB 연결 해제 및 WAL/SHM 정리
            try:
                db_manager.cleanup_db_files()
                if db_manager.engine:
                    db_manager.engine.dispose()
            except Exception:
                pass

            # 3. 백업 파일로 교체 복사
            os.makedirs(os.path.dirname(cur_db), exist_ok=True)
            shutil.copy2(selected_file, cur_db)

            # 4. WAL, SHM 파일 삭제
            for ext in ['-wal', '-shm']:
                wal_f = cur_db + ext
                if os.path.exists(wal_f):
                    try:
                        os.remove(wal_f)
                    except Exception:
                        pass

            # 5. DB 재초기화
            db_manager.db_path = cur_db
            db_manager.init_db()

            messagebox.showinfo(
                "복원 완료",
                "데이터베이스가 성공적으로 모두 복원되었습니다!\n\n"
                "새로운 데이터를 반영하기 위해 프로그램을 재시작합니다.",
                parent=self
            )
            if hasattr(self.app, 'restart_program'):
                self.app.restart_program()
        except Exception as e:
            messagebox.showerror("복원 실패", f"데이터 복원(불러오기) 도중 오류가 발생했습니다:\n{e}", parent=self)

    def save_paths(self):
        print("[DEBUG] save_paths 호출됨")
        new_db_input = self.db_path_entry.get().strip()
        new_excel_path = self.excel_path_entry.get().strip()
        
        print(f"[DEBUG] 새 DB 경로 입력값: {new_db_input}")
        print(f"[DEBUG] 새 엑셀 경로: {new_excel_path}")
        print(f"[DEBUG] 현재 사용자 관리자 권한: {self.current_user.is_admin}")

        if not new_db_input or new_db_input == "미설정":
            messagebox.showwarning("경고", "공유 DB 경로를 설정해주세요.", parent=self)
            return

        # Determine the directory from user input, ignoring any filename.
        if os.path.isdir(new_db_input):
            new_db_dir = new_db_input
        elif os.path.isfile(new_db_input):
            new_db_dir = os.path.dirname(new_db_input)
        else:  # Path doesn't exist
            # If it ends with a db extension, treat as a file path, otherwise as a directory path
            if new_db_input.lower().endswith(('.db', '.db-shm', '.db-wal')):
                new_db_dir = os.path.dirname(new_db_input)
            else:
                new_db_dir = new_db_input
        
        # The target file is always 'cosmetic.db' in the determined directory.
        target_db_file = os.path.join(new_db_dir, "cosmetic.db")

        print(f"[DEBUG] 결정된 DB 디렉토리: {new_db_dir}")
        print(f"[DEBUG] 타겟 DB 파일 경로: {target_db_file}")

        config = configparser.ConfigParser()
        config.read(self.config_path, encoding='utf-8')
        old_db_path = config.get('Paths', 'shared_db_path', fallback="").strip()

        print(f"[DEBUG] 기존 저장된 DB 디렉토리: {old_db_path}")
        
        # Normalize paths for reliable comparison
        db_path_changed = os.path.normpath(new_db_dir) != os.path.normpath(old_db_path)
        print(f"[DEBUG] DB 경로 변경됨: {db_path_changed}")

        # DB 경로가 변경되었을 때만 검증 수행
        if db_path_changed:
            # 먼저 경로와 DB 파일 유효성 검증
            validation_result = self._validate_db_path_and_file(new_db_dir, target_db_file)
            if not validation_result['valid']:
                self._show_error_with_clipboard(
                    "DB 경로 검증 실패", 
                    validation_result['error'], 
                    f"입력 경로: {new_db_input}\n대상 DB: {target_db_file}"
                )
                return

        if self.current_user.is_admin and db_path_changed:
            print("[DEBUG] DB 경로 옵션 대화상자 표시 시도")
            dialog = DBPathOptionsDialog(self)
            choice = dialog.get_choice()
            print(f"[DEBUG] 선택된 옵션: {choice}")

            if choice is None:  # User cancelled
                return

            handler = {
                'create': self._handle_create_new_db,
                'move': self._handle_move_db,
                'use': self._handle_use_existing_db
            }.get(choice)

            if handler:
                # Handlers require the full target DB file path for file operations.
                handler(target_db_file, new_excel_path)
        
        else:  # DB 경로 변경 없거나 일반 사용자, 또는 둘 다 변경
            # 둘 다 저장하고 재시작
            self._save_and_restart(target_db_file, new_excel_path, "경로가 저장되었습니다. 프로그램을 재시작합니다.")

    def _save_and_restart(self, new_db_path, new_excel_path, message):
        try:
            # Save only the directory for shared_db_path (not the full file path)
            try:
                db_dir = new_db_path if os.path.isdir(new_db_path) else os.path.dirname(new_db_path)
            except Exception:
                db_dir = os.path.dirname(new_db_path)
            
            new_backup_path = self.backup_path_entry.get().strip() if hasattr(self, 'backup_path_entry') else ""
            if not new_backup_path or new_backup_path == "미설정":
                appdata_root = os.getenv('APPDATA', os.path.join(os.path.expanduser('~'), 'AppData', 'Roaming'))
                new_backup_path = os.path.join(appdata_root, 'CosRQD', 'backup')

            print(f"[DEBUG] 설정 저장 중: DB 경로={db_dir}, Excel 경로={new_excel_path}, Backup 경로={new_backup_path}")
            
            # 설정 저장
            self._save_config('Paths', 'shared_db_path', db_dir)
            self._save_config('Paths', 'database_dir', db_dir)
            self._save_config('Paths', 'excel_dir', new_excel_path)
            self._save_config('Paths', 'backup_dir', new_backup_path)
            
            # DB 경로 변경 시 항상 재시작 권장 (안정성 보장)
            print(f"[DEBUG] DB 경로 변경 - 재시작 진행")
            
            result = messagebox.askyesno("DB 경로 변경", 
                                       f"{message}\n\n"
                                       f"데이터베이스 경로가 변경되었습니다.\n"
                                       f"변경사항을 안전하게 적용하려면 프로그램을 재시작해야 합니다.\n\n"
                                       f"지금 재시작하시겠습니까?\n\n"
                                       f"※ '아니요'를 선택하면 다음 실행 시 적용됩니다.", 
                                       parent=self)
            if result:
                print(f"[DEBUG] 사용자 재시작 선택")
                self.app.restart_program()
            else:
                print(f"[DEBUG] 사용자 재시작 거부 - 다음 실행 시 적용 예정")
                messagebox.showwarning("주의", 
                                     "재시작하지 않으면 일부 기능이 제대로 작동하지 않을 수 있습니다.\n"
                                     "프로그램을 수동으로 재시작해주세요.", 
                                     parent=self)
            
        except Exception as e:
            print(f"[ERROR] _save_and_restart 실패: {e}")
            self._show_error_with_clipboard(
                "설정 저장 및 재시작 실패", 
                f"설정 저장 중 오류가 발생했습니다:\n{str(e)}\n\n"
                f"프로그램을 수동으로 재시작해주세요.", 
                f"DB 경로: {new_db_path}\nExcel 경로: {new_excel_path}"
            )
    
    def _handle_create_new_db(self, new_db_path, new_excel_path):
        """새로운 비어있는 DB를 생성하고 설정을 저장한 후 DB를 다시 로드합니다."""
        # 1. DB 디렉토리 생성
        try:
            os.makedirs(os.path.dirname(new_db_path), exist_ok=True)
        except Exception as e:
            messagebox.showerror("오류", f"DB 디렉토리 생성 실패: {e}", parent=self)
            return

        # 2. 기존 파일 체크 및 제거
        if os.path.exists(new_db_path):
            if not messagebox.askyesno("경고", 
                f"파일이 이미 존재합니다: '{os.path.basename(new_db_path)}'\n"
                "기존 파일을 덮어쓰고 비어있는 DB를 새로 만드시겠습니까?", 
                parent=self):
                return
            try:
                os.remove(new_db_path)
            except Exception as e:
                messagebox.showerror("오류", f"기존 DB 파일 제거 실패: {e}", parent=self)
                return

        # 3. DB 엔진 생성 및 초기화
        engine = None
        try:
            engine = create_engine(f"sqlite:///{new_db_path}", 
                                 connect_args={'check_same_thread': False})
            
            # 스키마 생성
            Base.metadata.create_all(engine)
            
            # 스키마 버전 초기화
            with engine.connect() as conn:
                conn.execute(text("CREATE TABLE IF NOT EXISTS _schema_version (version INTEGER)"))
                conn.execute(text("DELETE FROM _schema_version"))
                conn.execute(text(f"INSERT INTO _schema_version (version) VALUES ({SCHEMA_VERSION})"))
                conn.commit()
            
            print(f"[DEBUG] 새 DB 생성 완료: {new_db_path}")
            
            # 4. 설정 저장
            db_dir = os.path.dirname(new_db_path)
            self._save_config('Paths', 'shared_db_path', db_dir)
            self._save_config('Paths', 'excel_dir', new_excel_path)
            print(f"[DEBUG] 설정 저장 완료: DB={db_dir}, Excel={new_excel_path}")
            
            # 5. 기존 DB 연결 해제
            db_manager.dispose_engine()
            print("[DEBUG] 기존 DB 연결 해제 완료")
            
            # 6. 새 DB로 다시 연결
            db_manager.setup_database(self.application_path, self.config_path, self.app.on_initial_setup)
            print("[DEBUG] 새 DB 연결 완료")
            
            # 7. 모든 프레임의 데이터 새로고침
            self.app.refresh_data_in_all_frames()
            
            messagebox.showinfo("완료", 
                              "새로운 비어있는 DB가 생성되고 로드되었습니다.\n"
                              "이제 새 DB를 사용할 수 있습니다.",
                              parent=self)
                
        except Exception as e:
            # DB 생성 실패 시 파일 정리
            if os.path.exists(new_db_path):
                try:
                    os.remove(new_db_path)
                except Exception:
                    pass  # 이미 에러 상황이므로 추가 에러는 무시
            
            self._show_error_with_clipboard(
                "새 DB 생성 오류", 
                f"새 DB 생성 중 오류가 발생했습니다:\n{str(e)}", 
                f"대상 경로: {new_db_path}"
            )
            
        finally:
            if engine is not None:
                engine.dispose()

    def _handle_move_db(self, new_db_path, new_excel_path):
        """현재 DB를 새 경로로 이동합니다 (재시작을 통해 안전하게 처리)"""
        # 1. 현재 DB 파일 확인
        current_db_path = db_manager.db_path
        if not current_db_path or not os.path.exists(current_db_path):
            messagebox.showerror("오류", "현재 사용중인 DB 파일을 찾을 수 없습니다.", parent=self)
            return

        # 2. 대상 파일 존재 여부 확인
        if os.path.exists(new_db_path):
            if not messagebox.askyesno("경고", 
                f"대상 경로에 이미 DB 파일이 존재합니다: '{os.path.basename(new_db_path)}'\n"
                "기존 파일을 덮어쓰고 진행하시겠습니까?", 
                parent=self):
                return
            try:
                os.remove(new_db_path)
            except Exception as e:
                messagebox.showerror("오류", f"기존 DB 파일 제거 실패: {e}", parent=self)
                return

        # 3. 프로그램 재시작을 통해 DB 이동
        messagebox.showinfo(
            "프로그램 재시작",
            "DB를 새 경로로 이동하기 위해 프로그램을 재시작합니다.\n"
            "재시작 후 자동으로 작업이 완료됩니다.",
            parent=self
        )
        
        self.app.restart_app(
            save_state=True,
            DB_MOVE_REQUIRED='True',
            DB_MOVE_TARGET_DB=new_db_path,
            DB_MOVE_TARGET_EXCEL=new_excel_path
        )

    def _handle_use_existing_db(self, new_db_path, new_excel_path):
        """경로에 있는 기존 DB를 검증하고 설정을 저장한 후 DB를 다시 로드합니다."""
        
        # 1. DB 파일 존재 여부 확인
        if not os.path.exists(new_db_path):
            messagebox.showerror("오류", 
                               f"선택한 경로에 DB 파일이 없습니다:\n{new_db_path}", 
                               parent=self)
            return

        # 2. DB 파일이 있는 경우 - 유효성 검증
        engine = None
        try:
            engine = create_engine(f"sqlite:///{new_db_path}", 
                                 connect_args={'check_same_thread': False})
            
            inspector = inspect(engine)
            existing_tables = set(inspector.get_table_names())
            
            # 2a. 스키마 버전 테이블 확인
            if '_schema_version' not in existing_tables:
                 messagebox.showerror("오류", "선택한 DB 파일이 유효하지 않습니다 (스키마 버전 정보 없음).", parent=self)
                 if engine: engine.dispose()
                 return

            # 2b. 스키마 버전 값 확인 (호환 모드)
            with engine.connect() as conn:
                try:
                    result = conn.execute(text("SELECT version FROM _schema_version")).scalar()
                    if result != SCHEMA_VERSION:
                        # 버전이 다르면 마이그레이션 안내
                        version_msg = f"DB 버전: v{result}\n프로그램 버전: v{SCHEMA_VERSION}\n\n"
                        if result < SCHEMA_VERSION:
                            version_msg += "구버전 DB입니다. 연결 시 자동으로 업데이트됩니다."
                        else:
                            version_msg += "최신 버전 DB입니다. 호환 모드로 실행됩니다."
                        
                        response = messagebox.askyesno("버전 확인", 
                                                      version_msg + "\n\n계속 진행하시겠습니까?",
                                                      parent=self)
                        if not response:
                            if engine: engine.dispose()
                            return
                except Exception as e:
                    print(f"[정보] 스키마 버전 확인 불가: {e} - 마이그레이션 시 자동 생성됩니다")
                    # 스키마 버전 테이블이 없어도 허용
            
            # 2c. 필수 테이블 확인
            required_tables = {'users', 'materials', 'clients', 'formulations'}
            missing_tables = required_tables - existing_tables
            if missing_tables:
                messagebox.showerror("오류", 
                                   f"선택한 DB 파일에 필요한 테이블이 없습니다:\n"
                                   f"{', '.join(missing_tables)}", 
                                   parent=self)
                if engine: engine.dispose()
                return
            
            print(f"[DEBUG] 기존 DB 검증 완료: {new_db_path}")
            
            # 3. 설정 저장
            db_dir = os.path.dirname(new_db_path)
            self._save_config('Paths', 'shared_db_path', db_dir)
            self._save_config('Paths', 'database_dir', db_dir)
            self._save_config('Paths', 'excel_dir', new_excel_path)
            print(f"[DEBUG] 설정 저장 완료: DB={db_dir}, Excel={new_excel_path}")
            
            # 4. 기존 DB 연결 해제
            db_manager.dispose_engine()
            print("[DEBUG] 기존 DB 연결 해제 완료")
            
            # 5. 새 DB로 다시 연결
            db_manager.setup_database(self.application_path, self.config_path, self.app.on_initial_setup)
            print("[DEBUG] 새 DB 연결 완료")
            
            # 6. 모든 프레임의 데이터 새로고침
            self.app.refresh_data_in_all_frames()
            
            messagebox.showinfo("완료", 
                              f"기존 DB가 로드되었습니다.\n\n"
                              f"경로: {new_db_path}",
                              parent=self)
                                 
        except Exception as e:
            self._show_error_with_clipboard(
                "DB 파일 검증 오류", 
                f"DB 파일 검증 중 오류가 발생했습니다:\n{str(e)}", 
                f"검증 대상: {new_db_path}"
            )
        finally:
            if engine is not None:
                engine.dispose()

    def _save_excel_path_only(self, new_excel_path):
        try:
            self._save_config('Paths', 'excel_dir', new_excel_path)
            messagebox.showinfo("설정 저장", "엑셀 경로가 저장되었습니다.", parent=self)
        except Exception as e:
            self._show_error_with_clipboard(
                "설정 저장 오류", 
                f"설정 저장 중 오류가 발생했습니다:\n{str(e)}", 
                f"Excel 경로: {new_excel_path}"
            )

    def _save_config(self, section, option, value):
        config = configparser.ConfigParser(interpolation=None)
        config.read(self.config_path, encoding='utf-8')
        if not config.has_section(section):
            config.add_section(section)
        config.set(section, option, value)
        with open(self.config_path, 'w', encoding='utf-8') as configfile:
            config.write(configfile)

    def _show_error_with_clipboard(self, title, error_message, additional_info=""):
        """오류 메시지를 표시하고 클립보드에 복사합니다."""
        try:
            # 전체 오류 정보 구성
            full_error = f"=== {title} ===\n"
            full_error += f"시간: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n"
            if additional_info:
                full_error += f"추가 정보: {additional_info}\n"
            full_error += f"오류 내용:\n{error_message}\n"
            full_error += f"=" * 50
            
            # 클립보드에 복사 (Windows 내장 방법 사용)
            clipboard_msg = ""
            try:
                # tkinter의 클립보드 기능 사용
                self.clipboard_clear()
                self.clipboard_append(full_error)
                self.update()  # 클립보드 업데이트 강제 실행
                clipboard_msg = "\n\n📋 오류 정보가 클립보드에 복사되었습니다."
            except Exception as clip_error:
                print(f"클립보드 복사 실패: {clip_error}")
                try:
                    # Windows 명령어를 사용한 대체 방법
                    import subprocess
                    process = subprocess.Popen(['clip'], stdin=subprocess.PIPE, text=True, shell=True)
                    process.communicate(input=full_error)
                    if process.returncode == 0:
                        clipboard_msg = "\n\n📋 오류 정보가 클립보드에 복사되었습니다."
                    else:
                        clipboard_msg = "\n\n⚠️ 클립보드 복사에 실패했습니다."
                except Exception:
                    clipboard_msg = "\n\n⚠️ 클립보드 복사에 실패했습니다."
            
            # 사용자에게 표시할 메시지
            display_message = f"{error_message}{clipboard_msg}"
            
            # 메시지박스 표시
            messagebox.showerror(title, display_message, parent=self)
            
        except Exception as e:
            # 오류 처리 자체에서 오류가 발생한 경우 기본 메시지박스 사용
            print(f"_show_error_with_clipboard 오류: {e}")
            messagebox.showerror(title, str(error_message), parent=self)

    def _validate_db_path_and_file(self, db_dir, db_file_path):
        """DB 경로와 파일의 유효성을 검증합니다."""
        try:
            print(f"[DEBUG] DB 경로 검증 시작: {db_dir}")
            print(f"[DEBUG] DB 파일 검증 시작: {db_file_path}")
            
            # 1. 디렉토리 접근 권한 확인
            if not os.path.exists(db_dir):
                try:
                    os.makedirs(db_dir, exist_ok=True)
                    print(f"[DEBUG] 디렉토리 생성됨: {db_dir}")
                except Exception as e:
                    return {
                        'valid': False,
                        'error': f"디렉토리를 생성할 수 없습니다:\n{db_dir}\n\n오류: {str(e)}"
                    }
            
            # 2. 디렉토리 쓰기 권한 확인
            try:
                test_file = os.path.join(db_dir, 'test_write_permission.tmp')
                with open(test_file, 'w') as f:
                    f.write('test')
                os.remove(test_file)
                print(f"[DEBUG] 디렉토리 쓰기 권한 확인됨")
            except Exception as e:
                return {
                    'valid': False,
                    'error': f"디렉토리에 쓰기 권한이 없습니다:\n{db_dir}\n\n오류: {str(e)}"
                }
            
            # 3. DB 파일이 이미 존재하는 경우 검증
            if os.path.exists(db_file_path):
                print(f"[DEBUG] 기존 DB 파일 발견, 검증 중...")
                
                # 파일 읽기 권한 확인
                try:
                    with open(db_file_path, 'rb') as f:
                        f.read(16)  # SQLite 헤더만 읽기
                    print(f"[DEBUG] DB 파일 읽기 권한 확인됨")
                except Exception as e:
                    return {
                        'valid': False,
                        'error': f"DB 파일에 접근할 수 없습니다:\n{db_file_path}\n\n오류: {str(e)}"
                    }
                
                # SQLite 파일 형식 확인
                try:
                    with open(db_file_path, 'rb') as f:
                        header = f.read(16)
                        if not header.startswith(b'SQLite format 3'):
                            return {
                                'valid': False,
                                'error': f"유효한 SQLite 데이터베이스 파일이 아닙니다:\n{db_file_path}"
                            }
                    print(f"[DEBUG] SQLite 파일 형식 확인됨")
                except Exception as e:
                    return {
                        'valid': False,
                        'error': f"DB 파일 형식을 확인할 수 없습니다:\n{db_file_path}\n\n오류: {str(e)}"
                    }
                
                # 데이터베이스 연결 및 스키마 검증
                try:
                    test_engine = create_engine(f"sqlite:///{db_file_path}", 
                                              connect_args={'check_same_thread': False})
                    with test_engine.connect() as conn:
                        # 스키마 버전 확인 (호환 모드)
                        try:
                            result = conn.execute(text("SELECT version FROM _schema_version")).scalar()
                            if result is None:
                                print(f"[경고] 스키마 버전 테이블이 비어있음")
                            elif result != SCHEMA_VERSION:
                                if result > SCHEMA_VERSION:
                                    print(f"[정보] DB가 최신 버전입니다 (DB: v{result}, 코드: v{SCHEMA_VERSION}) - 호환 모드")
                                else:
                                    print(f"[정보] DB가 구버전입니다 (DB: v{result}, 코드: v{SCHEMA_VERSION}) - 자동 마이그레이션 예정")
                            else:
                                print(f"[DEBUG] 스키마 버전 일치: v{result}")
                        except Exception as schema_e:
                            # 스키마 버전 테이블이 없어도 허용 (마이그레이션에서 생성)
                            print(f"[정보] 스키마 버전 확인 불가: {schema_e} - 마이그레이션 시 생성 예정")
                        
                        # 필수 테이블 확인
                        inspector = inspect(test_engine)
                        required_tables = {'users', 'materials', 'clients', 'formulations'}
                        existing_tables = set(inspector.get_table_names())
                        missing_tables = required_tables - existing_tables
                        
                        if missing_tables:
                            test_engine.dispose()
                            return {
                                'valid': False,
                                'error': f"DB 파일에 필요한 테이블이 없습니다:\n{', '.join(missing_tables)}\n\nDB 파일: {db_file_path}"
                            }
                        print(f"[DEBUG] 필수 테이블 확인됨: {', '.join(existing_tables)}")
                    
                    test_engine.dispose()
                    print(f"[DEBUG] DB 연결 테스트 완료")
                    
                except Exception as e:
                    return {
                        'valid': False,
                        'error': f"DB 연결 테스트 실패:\n{str(e)}\n\nDB 파일: {db_file_path}"
                    }
            else:
                print(f"[DEBUG] 새 DB 파일이 생성될 예정: {db_file_path}")
            
            print(f"[DEBUG] DB 경로 검증 완료 - 유효함")
            return {'valid': True, 'error': None}
            
        except Exception as e:
            return {
                'valid': False,
                'error': f"DB 경로 검증 중 예상치 못한 오류:\n{str(e)}"
            }

    def validate_current_db_path(self):
        """현재 설정된 DB 경로를 검증합니다."""
        try:
            # 현재 설정 읽기
            config = configparser.ConfigParser()
            config.read(self.config_path, encoding='utf-8')
            shared_db_path = config.get('Paths', 'shared_db_path', fallback="미설정")
            
            if shared_db_path == "미설정" or not shared_db_path.strip():
                messagebox.showinfo("검증 결과", 
                                  "공유 DB 경로가 설정되지 않았습니다.\n\n"
                                  "경로를 설정한 후 검증을 실행해주세요.", 
                                  parent=self)
                return
            
            # 경로 정규화
            if os.path.isdir(shared_db_path):
                db_dir = shared_db_path
                db_file = os.path.join(shared_db_path, "cosmetic.db")
            elif shared_db_path.lower().endswith('.db'):
                db_dir = os.path.dirname(shared_db_path)
                db_file = shared_db_path
            else:
                db_dir = shared_db_path
                db_file = os.path.join(shared_db_path, "cosmetic.db")
            
            print(f"[DEBUG] 검증 대상 - 디렉토리: {db_dir}, 파일: {db_file}")
            
            # 검증 실행
            validation_result = self._validate_db_path_and_file(db_dir, db_file)
            
            if validation_result['valid']:
                # 추가 정보 수집
                info_lines = ["✅ DB 경로 검증 성공!\n"]
                
                try:
                    info_lines.append(f"📁 DB 디렉토리: {db_dir}")
                    info_lines.append(f"🗄️ DB 파일: {os.path.basename(db_file)}")
                    
                    if os.path.exists(db_file):
                        file_size = os.path.getsize(db_file)
                        file_size_mb = file_size / (1024 * 1024)
                        info_lines.append(f"📊 파일 크기: {file_size_mb:.2f} MB")
                        
                        # 데이터 개수 확인
                        test_engine = create_engine(f"sqlite:///{db_file}", 
                                                  connect_args={'check_same_thread': False})
                        with test_engine.connect() as conn:
                            user_count = conn.execute(text("SELECT COUNT(*) FROM users")).scalar()
                            material_count = conn.execute(text("SELECT COUNT(*) FROM materials")).scalar()
                            client_count = conn.execute(text("SELECT COUNT(*) FROM clients")).scalar()
                            formulation_count = conn.execute(text("SELECT COUNT(*) FROM formulations")).scalar()
                            
                            info_lines.append(f"\n📈 데이터 현황:")
                            info_lines.append(f"• 사용자: {user_count}개")
                            info_lines.append(f"• 원료: {material_count}개")
                            info_lines.append(f"• 거래처: {client_count}개")
                            info_lines.append(f"• 처방: {formulation_count}개")
                        
                        test_engine.dispose()
                    else:
                        info_lines.append("📝 상태: 새 DB 파일이 생성될 예정")
                    
                except Exception as info_error:
                    info_lines.append(f"\n⚠️ 추가 정보 수집 실패: {str(info_error)}")
                
                messagebox.showinfo("DB 검증 성공", "\n".join(info_lines), parent=self)
                
            else:
                # 검증 실패
                self._show_error_with_clipboard(
                    "DB 검증 실패", 
                    validation_result['error'], 
                    f"검증 대상: {db_file}"
                )
                
        except Exception as e:
            self._show_error_with_clipboard(
                "DB 검증 오류", 
                f"DB 경로 검증 중 오류가 발생했습니다:\n{str(e)}", 
                f"설정 파일: {self.config_path}"
            )



    # ===== Admin-only methods =====
    def export_formulation_template(self):
        """처방 템플릿(빈 폼)을 내보냅니다."""
        excel_handler.export_formulation_blank_template()

    def export_material_template(self):
        """실제 v64 시스템에서 사용하는 표준 원료 템플릿을 내보냅니다."""
        sheets = {
            "원료정보": ["코드", "원료명", "단가", "포장단위", "거래처", "제조원명", "HS CODE", "원산지", "영문원료명", "NMPA등록번호", "사용여부(Y/N)"],
            "전성분정보": ["원료코드", "한글전성분", "INGREDIENT", "CAS NO.", "조성비(%)", "기능", "EWG등급", "EWG등급데이터", "비고"]
        }
        excel_handler.export_multisheet_template(sheets, "원료_템플릿.xlsx")

    def export_client_template(self):
        """실제 v64 시스템에서 사용하는 표준 거래처 템플릿을 내보냅니다."""
        headers = ["거래처 유형", "거래처코드(사업자번호)", "거래처명", "영문거래처명", "대표자명", "담당자명", "연락처", "팩스", "이메일", "우편번호", "주소", "사용여부(Y/N)"]
        excel_handler.export_template(headers, "거래처_템플릿.xlsx")

    def export_user_template(self):
        """실제 v64 시스템에서 사용하는 표준 사용자 템플릿을 내보냅니다."""
        headers = ["사용자 ID", "비밀번호", "실명", "담당번호", "직책", "연락처", "우편번호", "주소", "권한(QC/RD/RQ/RQD/MSAD)", "관리자여부(True/False)"]
        excel_handler.export_template(headers, "사용자_템플릿.xlsx")

    def confirm_reset(self, reset_type: str):
        messages = {
            "materials": "모든 원료 및 전성분 데이터가 삭제됩니다.",
            "clients": "모든 거래처 데이터가 삭제됩니다.",
            "users": "기본 관리자 계정을 제외한 모든 사용자 데이터가 삭제됩니다.",
            "all": "모든 처방, 생산처방, 품질서류(COA/원료목록), 원료, 거래처, 사용자(관리자 제외) 데이터가 영구적으로 삭제됩니다."
        }
        message = messages.get(reset_type, "선택된 데이터가 삭제됩니다.")
        
        dialog = ctk.CTkToplevel(self)
        dialog.title("데이터 초기화 경고")
        dialog.geometry("440x160")
        dialog.transient(self)
        dialog.grab_set()
        dialog.resizable(False, False)

        label = ctk.CTkLabel(dialog, text=f"⚠ {message}\n\n이 작업은 되돌릴 수 없습니다. 계속하시겠습니까?", font=ctk.CTkFont(size=13, weight="bold"))
        label.pack(pady=20, padx=20, fill="both", expand=True)

        button_frame = ctk.CTkFrame(dialog, fg_color="transparent")
        button_frame.pack(pady=(0, 20))

        confirm_btn = ctk.CTkButton(button_frame, text="삭제 실행", fg_color="#D32F2F", hover_color="#B71C1C", command=lambda: self.execute_reset(dialog, reset_type))
        confirm_btn.pack(side="left", padx=10)

        cancel_btn = ctk.CTkButton(button_frame, text="취소", command=dialog.destroy)
        cancel_btn.pack(side="left", padx=10)

    def execute_reset(self, dialog, reset_type: str):
        dialog.destroy()
        
        # [핵심 안전장치] 삭제 전 전체 DB 파일 원본을 AppData 심층 시스템 은닉 볼트에 암호화 백업
        backup_saved_path = None
        try:
            from modules.secure_vault import SecureVault
            cur_db_path = getattr(db_manager, 'db_path', None)
            if cur_db_path and os.path.exists(cur_db_path):
                # 1. AppData 심층 은닉 볼트 암호화 스냅샷 저장
                SecureVault.backup_database_file(
                    db_source_path=cur_db_path,
                    reset_type=reset_type,
                    username=getattr(self.current_user, 'username', 'system')
                )
                
                # 2. 로컬 백업 폴더(보조) 저장
                backup_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'data', 'backups', 'system_reset')
                os.makedirs(backup_dir, exist_ok=True)
                ts = datetime.now().strftime('%Y%m%d_%H%M%S')
                backup_saved_path = os.path.join(backup_dir, f"cosmetic_db_backup_before_{reset_type}_{ts}.db")
                shutil.copy2(cur_db_path, backup_saved_path)
                print(f"[안전 백업 완료] 삭제 전 원본 DB 복제 저장됨: {backup_saved_path}")
        except Exception as bk_err:
            print(f"[경고] 시스템 초기화 사전 백업 실패: {bk_err}")

        session = db_manager.get_session()
        try:
            if reset_type == "all":
                db_manager.reset_all_data(session)
            elif reset_type == "users":
                db_manager.reset_users_data(session)
            elif reset_type == "clients":
                db_manager.reset_clients_data(session)
            elif reset_type == "materials":
                db_manager.reset_materials_data(session)
            
            session.commit()
            
            msg = "데이터가 성공적으로 초기화되었습니다."
            if backup_saved_path:
                msg += f"\n\n🛡️ [안전 복구용 백업 완료]\n삭제 전 원본 DB가 아래 경로에 안전하게 보관되었습니다:\n{backup_saved_path}"
            
            messagebox.showinfo("완료", msg, parent=self)
        except Exception as e:
            session.rollback()
            messagebox.showerror("오류", f"데이터 초기화 중 오류 발생: {e}", parent=self)
        finally:
            session.close()
            self.app.refresh_data_in_all_frames()
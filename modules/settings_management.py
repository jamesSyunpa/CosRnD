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
        path_frame = ctk.CTkFrame(scrollable_frame)
        path_frame.grid(row=1, column=0, padx=20, pady=(0, 20), sticky="ew")
        path_frame.grid_columnconfigure(1, weight=1)

        ctk.CTkLabel(path_frame, text="공유 DB 경로").grid(row=0, column=0, padx=10, pady=10, sticky="w")
        self.db_path_entry = ctk.CTkEntry(path_frame)
        self.db_path_entry.grid(row=0, column=1, padx=10, pady=10, sticky="ew")
        db_browse_button = ctk.CTkButton(path_frame, text="찾아보기", command=self.browse_db_path)
        db_browse_button.grid(row=0, column=2, padx=10, pady=10)

        ctk.CTkLabel(path_frame, text="엑셀 저장 경로").grid(row=1, column=0, padx=10, pady=10, sticky="w")
        self.excel_path_entry = ctk.CTkEntry(path_frame)
        self.excel_path_entry.grid(row=1, column=1, padx=10, pady=10, sticky="ew")
        excel_browse_button = ctk.CTkButton(path_frame, text="찾아보기", command=self.browse_excel_path)
        excel_browse_button.grid(row=1, column=2, padx=10, pady=10)

        # --- 저장 버튼 ---
        save_button = ctk.CTkButton(scrollable_frame, text="경로 저장 및 재시작", command=self.save_paths)
        save_button.grid(row=2, column=0, pady=20, padx=20, sticky="e")

        # --- DB 백업/복원 기능 ---
        if self.current_user.is_admin:
            self.setup_db_backup_restore_section(scrollable_frame)

        # --- 관리자 전용 기능 ---
        if self.current_user.is_admin:
            self.setup_admin_only_features(scrollable_frame)

        self.load_settings()

    def setup_db_backup_restore_section(self, parent_frame):
        """DB 경로 검증 기능 섹션을 설정합니다."""
        validation_frame = ctk.CTkFrame(parent_frame)
        validation_frame.grid(row=3, column=0, padx=20, pady=(20, 10), sticky="ew")
        validation_frame.grid_columnconfigure(0, weight=1)
        
        ctk.CTkLabel(validation_frame, text="데이터베이스 검증", font=ctk.CTkFont(weight="bold")).grid(row=0, column=0, pady=(10, 5))
        
        # 경로 검증 버튼
        validate_button = ctk.CTkButton(
            validation_frame, 
            text="🔍 DB 경로 및 파일 검증", 
            command=self.validate_current_db_path,
            fg_color="#1565C0",
            hover_color="#1976D2"
        )
        validate_button.grid(row=1, column=0, padx=5, pady=10, sticky="ew")

    def setup_admin_only_features(self, parent_frame):
        # --- 엑셀 폼 내보내기 ---
        export_frame = ctk.CTkFrame(parent_frame)
        export_frame.grid(row=4, column=0, padx=20, pady=(20, 10), sticky="ew")
        export_frame.grid_columnconfigure((0, 1, 2), weight=1)
        ctk.CTkLabel(export_frame, text="엑셀 폼 내보내기", font=ctk.CTkFont(weight="bold")).grid(row=0, column=0, columnspan=3, pady=(10, 5))
        ctk.CTkButton(export_frame, text="원료 템플릿", command=self.export_material_template).grid(row=1, column=0, padx=5, pady=10, sticky="ew")
        ctk.CTkButton(export_frame, text="거래처 템플릿", command=self.export_client_template).grid(row=1, column=1, padx=5, pady=10, sticky="ew")
        ctk.CTkButton(export_frame, text="사용자 템플릿", command=self.export_user_template).grid(row=1, column=2, padx=5, pady=10, sticky="ew")

        # --- 데이터 리셋 ---
        reset_frame = ctk.CTkFrame(parent_frame)
        reset_frame.grid(row=5, column=0, padx=20, pady=(50, 20), sticky="ew")
        reset_frame.grid_columnconfigure((0, 1, 2, 3), weight=1)
        ctk.CTkLabel(reset_frame, text="데이터 초기화 (주의: 복구 불가)", font=ctk.CTkFont(weight="bold")).grid(row=0, column=0, columnspan=4, pady=(10, 5))
        reset_button_style = {"fg_color": "#D32F2F", "hover_color": "#B71C1C"}
        ctk.CTkButton(reset_frame, text="원료 데이터", command=lambda: self.confirm_reset("materials"), **reset_button_style).grid(row=1, column=0, padx=5, pady=10, sticky="ew")
        ctk.CTkButton(reset_frame, text="거래처 데이터", command=lambda: self.confirm_reset("clients"), **reset_button_style).grid(row=1, column=1, padx=5, pady=10, sticky="ew")
        ctk.CTkButton(reset_frame, text="사용자 데이터", command=lambda: self.confirm_reset("users"), **reset_button_style).grid(row=1, column=2, padx=5, pady=10, sticky="ew")
        all_reset_style = {"fg_color": "#B71C1C", "hover_color": "#7f0000"}
        ctk.CTkButton(reset_frame, text="전체 데이터", command=lambda: self.confirm_reset("all"), **all_reset_style).grid(row=1, column=3, padx=5, pady=10, sticky="ew")

    def load_settings(self):
        config = configparser.ConfigParser()
        config.read(self.config_path, encoding='utf-8')
        
        theme = config.get('Appearance', 'theme', fallback='system').capitalize()
        self.theme_menu.set(theme)

        language = config.get('Appearance', 'language', fallback='korean').capitalize()
        self.language_menu.set(language)

        db_path = config.get('Paths', 'shared_db_path', fallback="미설정")
        excel_path = config.get('Paths', 'excel_dir', fallback="미설정")
        
        self.db_path_entry.delete(0, 'end')
        self.db_path_entry.insert(0, db_path)
        
        self.excel_path_entry.delete(0, 'end')
        self.excel_path_entry.insert(0, excel_path)

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
        
        elif db_path_changed:  # Non-admin user
            # For non-admins just save the directory (handled inside _save_and_restart)
            self._save_and_restart(target_db_file, new_excel_path, "DB 경로가 변경되었습니다. 프로그램을 재시작합니다.")
        
        else:  # Only excel path changed or no change
            self._save_excel_path_only(new_excel_path)

    def _save_and_restart(self, new_db_path, new_excel_path, message):
        try:
            # Save only the directory for shared_db_path (not the full file path)
            try:
                db_dir = new_db_path if os.path.isdir(new_db_path) else os.path.dirname(new_db_path)
            except Exception:
                db_dir = os.path.dirname(new_db_path)
            
            print(f"[DEBUG] 설정 저장 중: DB 경로={db_dir}, Excel 경로={new_excel_path}")
            
            # 설정 저장
            self._save_config('Paths', 'shared_db_path', db_dir)
            self._save_config('Paths', 'excel_dir', new_excel_path)
            
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
        """현재 DB를 새 경로로 이동하고 설정을 저장한 후 DB를 다시 로드합니다."""
        # 1. 현재 DB 파일 확인
        local_db_path = db_manager.get_local_db_path()
        if not local_db_path or not os.path.exists(local_db_path):
            messagebox.showerror("오류", "현재 사용중인 로컬 DB 파일을 찾을 수 없습니다.", parent=self)
            return

        # 2. 대상 디렉토리 생성
        try:
            os.makedirs(os.path.dirname(new_db_path), exist_ok=True)
        except Exception as e:
            messagebox.showerror("오류", f"대상 디렉토리 생성 실패: {e}", parent=self)
            return

        # 3. 대상 파일 존재 여부 확인
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

        # 4. DB 연결 해제 및 파일 이동
        db_backup_path = None
        try:
            # DB 연결 해제
            db_manager.dispose_engine()
            print(f"[DEBUG] DB 연결 해제 완료")
            
            # 백업 생성
            db_backup_path = f"{local_db_path}.backup"
            shutil.copy2(local_db_path, db_backup_path)
            print(f"[DEBUG] 백업 생성 완료: {db_backup_path}")
            
            # 대상 디렉토리가 없으면 생성
            os.makedirs(os.path.dirname(new_db_path), exist_ok=True)
            
            # 파일 이동 (copy + delete 방식으로 변경하여 크로스 드라이브 이동 지원)
            shutil.copy2(local_db_path, new_db_path)
            print(f"[DEBUG] DB 파일 복사 완료: {new_db_path}")
            
            # 원본 파일 삭제
            os.remove(local_db_path)
            print(f"[DEBUG] 원본 DB 파일 삭제 완료")
            
            # 5. 설정 저장
            db_dir = os.path.dirname(new_db_path)
            self._save_config('Paths', 'shared_db_path', db_dir)
            self._save_config('Paths', 'excel_dir', new_excel_path)
            print(f"[DEBUG] 설정 저장 완료: DB={db_dir}, Excel={new_excel_path}")
            
            # 6. 새 DB로 다시 연결
            db_manager.setup_database(self.application_path, self.config_path, self.app.on_initial_setup)
            print("[DEBUG] 새 DB 연결 완료")
            
            # 7. 모든 프레임의 데이터 새로고침
            self.app.refresh_data_in_all_frames()
            
            # 성공적으로 이동했다면 백업 삭제
            if os.path.exists(db_backup_path):
                try:
                    os.remove(db_backup_path)
                    print(f"[DEBUG] 백업 파일 삭제 완료")
                except Exception:
                    pass  # 백업 삭제 실패는 무시
            
            messagebox.showinfo("완료", 
                              f"DB가 새 경로로 이동되고 로드되었습니다.\n\n"
                              f"새 경로: {new_db_path}",
                              parent=self)
                    
        except Exception as e:
            # 이동 실패 시 복구 시도
            if db_backup_path and os.path.exists(db_backup_path):
                try:
                    shutil.copy2(db_backup_path, local_db_path)
                    os.remove(db_backup_path)
                    print(f"[DEBUG] DB 복구 완료")
                except Exception as restore_error:
                    self._show_error_with_clipboard(
                        "심각한 DB 이동 오류", 
                        f"DB 파일 이동 실패 및 복구 실패:\n"
                        f"원본 오류: {str(e)}\n"
                        f"복구 오류: {str(restore_error)}", 
                        f"소스: {local_db_path}\n대상: {new_db_path}\n백업: {db_backup_path}"
                    )
                    return
                    
            self._show_error_with_clipboard(
                "DB 이동 오류", 
                f"DB 파일 이동 중 오류가 발생했습니다:\n{str(e)}", 
                f"소스: {local_db_path}\n대상: {new_db_path}"
            )
            # 복구 후 다시 연결 시도
            self.app.after(100, lambda: db_manager.setup_database(
                self.application_path, self.config_path, self.app.on_initial_setup))

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
    def export_material_template(self):
        sheets = {
            "원료정보": ["코드", "원료명", "단가", "포장단위", "거래처", "제조원명", "HS CODE", "원산지", "영문원료명", "NMPA등록번호", "사용여부(Y/N)"],
            "전성분정보": ["원료코드", "한글전성분", "INGREDIENT", "CAS NO.", "조성비(%)", "기능", "EWG등급", "EWG등급데이터"]
        }
        excel_handler.export_multisheet_template(sheets, "원료_템플릿.xlsx")

    def export_client_template(self):
        headers = ["거래처 유형", "거래처코드(사업자번호)", "거래처명", "대표자명", "담당자명", "연락처", "팩스", "이메일", "우편번호", "주소", "사용여부(Y/N)"]
        excel_handler.export_template(headers, "거래처_템플릿.xlsx")

    def export_user_template(self):
        headers = ["사용자 ID", "비밀번호", "직책", "연락처", "우편번호", "주소", "관리자여부(True/False)"]
        excel_handler.export_template(headers, "사용자_템플릿.xlsx")

    def confirm_reset(self, reset_type: str):
        messages = {
            "materials": "모든 성분(원료) 데이터가 삭제됩니다.",
            "clients": "모든 거래처 데이터가 삭제됩니다.",
            "users": "기본 admin 계정을 제외한 모든 사용자 데이터가 삭제됩니다.",
            "all": "모든 처방, 성분, 거래처, 사용자(admin 제외) 데이터가 영구적으로 삭제됩니다."
        }
        message = messages.get(reset_type, "선택된 데이터가 삭제됩니다.")
        
        dialog = ctk.CTkToplevel(self)
        dialog.title("경고")
        dialog.geometry("420x150")
        dialog.transient(self)
        dialog.grab_set()
        dialog.resizable(False, False)

        label = ctk.CTkLabel(dialog, text=f"⚠ {message}\n\n이 작업은 되돌릴 수 없습니다. 계속하시겠습니까?", font=ctk.CTkFont(size=14))
        label.pack(pady=20, padx=20, fill="both", expand=True)

        button_frame = ctk.CTkFrame(dialog, fg_color="transparent")
        button_frame.pack(pady=(0, 20))

        confirm_btn = ctk.CTkButton(button_frame, text="삭제 실행", fg_color="red", hover_color="#aa0000", command=lambda: self.execute_reset(dialog, reset_type))
        confirm_btn.pack(side="left", padx=10)

        cancel_btn = ctk.CTkButton(button_frame, text="취소", command=dialog.destroy)
        cancel_btn.pack(side="left", padx=10)

    def execute_reset(self, dialog, reset_type: str):
        dialog.destroy()
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
            messagebox.showinfo("완료", "데이터가 성공적으로 리셋되었습니다.")
        except Exception as e:
            session.rollback()
            messagebox.showerror("오류", f"데이터 리셋 중 오류 발생: {e}")
        finally:
            session.close()
            self.app.refresh_data_in_all_frames()
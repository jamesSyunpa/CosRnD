# modules/settings_management.py
import customtkinter as ctk
from tkinter import messagebox, filedialog
import configparser
import os
import shutil
from database.db_manager import db_manager, SCHEMA_VERSION
from database.models import Base, Formulation, FormulationItem, Material, Client, User
from sqlalchemy import create_engine, text, inspect
from modules.ui_components import HelpPopup
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

        # --- 관리자 전용 기능 ---
        if self.current_user.is_admin:
            self.setup_admin_only_features(scrollable_frame)

        self.load_settings()

    def setup_admin_only_features(self, parent_frame):
        # --- 엑셀 폼 내보내기 ---
        export_frame = ctk.CTkFrame(parent_frame)
        export_frame.grid(row=3, column=0, padx=20, pady=(20, 10), sticky="ew")
        export_frame.grid_columnconfigure((0, 1, 2), weight=1)
        ctk.CTkLabel(export_frame, text="엑셀 폼 내보내기", font=ctk.CTkFont(weight="bold")).grid(row=0, column=0, columnspan=3, pady=(10, 5))
        ctk.CTkButton(export_frame, text="원료 템플릿", command=self.export_material_template).grid(row=1, column=0, padx=5, pady=10, sticky="ew")
        ctk.CTkButton(export_frame, text="거래처 템플릿", command=self.export_client_template).grid(row=1, column=1, padx=5, pady=10, sticky="ew")
        ctk.CTkButton(export_frame, text="사용자 템플릿", command=self.export_user_template).grid(row=1, column=2, padx=5, pady=10, sticky="ew")

        # --- 데이터 리셋 ---
        reset_frame = ctk.CTkFrame(parent_frame)
        reset_frame.grid(row=4, column=0, padx=20, pady=(50, 20), sticky="ew")
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
        path = filedialog.asksaveasfilename(
            title="DB 파일 선택 또는 저장",
            initialfile="cosmetic.db",
            defaultextension=".db",
            filetypes=[("Database files", "*.db"), ("All files", "*.*")]
        )
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
        new_db_path = self.db_path_entry.get().strip()
        new_excel_path = self.excel_path_entry.get().strip()
        
        print(f"[DEBUG] 새 DB 경로 입력값: {new_db_path}")
        print(f"[DEBUG] 새 엑셀 경로: {new_excel_path}")
        print(f"[DEBUG] 현재 사용자 관리자 권한: {self.current_user.is_admin}")

        # Normalize input: allow user to paste either a folder path or a full DB file path.
        # We will always operate on a full DB file path internally (target_db_file),
        # but store only the directory (folder) in config (shared_db_path).
        if not new_db_path or new_db_path == "미설정":
            messagebox.showwarning("경고", "공유 DB 경로를 설정해주세요.", parent=self)
            return

        # Determine target DB file path from input
        if os.path.isdir(new_db_path):
            target_db_file = os.path.join(new_db_path, "cosmetic.db")
        else:
            # If user typed/selected a file-like path (endswith .db or cosmetic.db), use it.
            # Otherwise treat it as a folder and append cosmetic.db
            base = os.path.basename(new_db_path)
            if base.lower().endswith('.db') or base.lower() == 'cosmetic.db':
                target_db_file = new_db_path
            else:
                target_db_file = os.path.join(new_db_path, "cosmetic.db")

        print(f"[DEBUG] 내부 사용 DB 파일 경로: {target_db_file}")

        config = configparser.ConfigParser()
        config.read(self.config_path, encoding='utf-8')
        old_db_path = config.get('Paths', 'shared_db_path', fallback="").strip()

        print(f"[DEBUG] 기존 저장된 DB 디렉토리: {old_db_path}")
        new_db_dir = os.path.dirname(target_db_file)
        db_path_changed = new_db_dir != old_db_path
        print(f"[DEBUG] 내부 사용 DB 디렉토리: {new_db_dir}")
        print(f"[DEBUG] DB 경로 변경됨: {db_path_changed}")

        if self.current_user.is_admin and db_path_changed:
            print("[DEBUG] DB 경로 옵션 대화상자 표시 시도")
            dialog = DBPathOptionsDialog(self)
            choice = dialog.get_choice()
            print(f"[DEBUG] 선택된 옵션: {choice}")

            if choice is None: # User cancelled
                return

            handler = {
                'create': self._handle_create_new_db,
                'move': self._handle_move_db,
                'use': self._handle_use_existing_db
            }.get(choice)

            if handler:
                # Handlers require a full target DB file path for file operations.
                handler(target_db_file, new_excel_path)
        
        elif db_path_changed: # Non-admin user
            # For non-admins just save the directory (handled inside _save_and_restart)
            self._save_and_restart(target_db_file, new_excel_path, "DB 경로가 변경되었습니다. 프로그램을 재시작합니다.")
        
        else: # Only excel path changed or no change
            self._save_excel_path_only(new_excel_path)

    def _save_and_restart(self, new_db_path, new_excel_path, message):
        # Save only the directory for shared_db_path (not the full file path)
        try:
            db_dir = new_db_path if os.path.isdir(new_db_path) else os.path.dirname(new_db_path)
        except Exception:
            db_dir = os.path.dirname(new_db_path)
        self._save_config('Paths', 'shared_db_path', db_dir)
        self._save_config('Paths', 'excel_dir', new_excel_path)
        messagebox.showinfo("설정 완료", message, parent=self)
        self.app.restart_program()

    def _handle_create_new_db(self, new_db_path, new_excel_path):
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
                
            self._save_and_restart(new_db_path, new_excel_path, 
                                 "비어있는 새 공유 DB 경로가 설정되었습니다. 프로그램을 재시작합니다.")
                
        except Exception as e:
            # DB 생성 실패 시 파일 정리
            if os.path.exists(new_db_path):
                try:
                    os.remove(new_db_path)
                except Exception:
                    pass  # 이미 에러 상황이므로 추가 에러는 무시
            messagebox.showerror("오류", f"새 DB 생성 중 오류가 발생했습니다: {e}", parent=self)
            
        finally:
            if engine is not None:
                engine.dispose()

    def _handle_move_db(self, new_db_path, new_excel_path):
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
            
            # 백업 생성
            db_backup_path = f"{local_db_path}.backup"
            shutil.copy2(local_db_path, db_backup_path)
            
            # 파일 이동
            shutil.move(local_db_path, new_db_path)
            
            # 설정 저장 및 재시작
            self._save_and_restart(new_db_path, new_excel_path, 
                                 "기존 DB를 새 공유 경로로 이동했습니다. 프로그램을 재시작합니다.")
            
            # 성공적으로 이동했다면 백업 삭제
            if os.path.exists(db_backup_path):
                try:
                    os.remove(db_backup_path)
                except Exception:
                    pass  # 백업 삭제 실패는 무시
                    
        except Exception as e:
            # 이동 실패 시 복구 시도
            if db_backup_path and os.path.exists(db_backup_path):
                try:
                    shutil.copy2(db_backup_path, local_db_path)
                    os.remove(db_backup_path)
                except Exception as restore_error:
                    messagebox.showerror("심각한 오류", 
                        f"DB 파일 이동 실패 및 복구 실패:\n"
                        f"원본 오류: {e}\n"
                        f"복구 오류: {restore_error}\n"
                        f"백업 파일 위치: {db_backup_path}", 
                        parent=self)
                    return
                    
            messagebox.showerror("오류", f"DB 파일 이동 중 오류가 발생했습니다: {e}", parent=self)
            self.app.after(100, lambda: db_manager.setup_database(
                self.application_path, self.config_path, self.app.on_initial_setup))

    def _handle_use_existing_db(self, new_db_path, new_excel_path):
        """공유 DB 경로 설정을 처리합니다."""
        # DB 파일이 없는 경우 - 경로만 저장
        if not os.path.exists(new_db_path):
            db_dir = os.path.dirname(new_db_path)
            if not os.path.exists(db_dir):
                try:
                    os.makedirs(db_dir)
                    print(f"  * 공유 DB 디렉토리 생성됨: {db_dir}")
                except Exception as e:
                    messagebox.showerror("오류", 
                                       f"공유 DB 디렉토리를 생성할 수 없습니다:\n{e}", 
                                       parent=self)
                    return
            
            # 경로(디렉토리)만 저장하고 재시작
            self._save_config('Paths', 'shared_db_path', db_dir)
            self._save_config('Paths', 'excel_dir', new_excel_path)
            messagebox.showinfo("설정 완료", 
                              "공유 DB 경로가 설정되었습니다.\n"
                              "다른 사용자가 공유 DB를 생성하면 자동으로 동기화됩니다.", 
                              parent=self)
            self.app.restart_program()
            return

        # DB 파일이 있는 경우 - 유효성 검증
        engine = None
        try:
            engine = create_engine(f"sqlite:///{new_db_path}", 
                                 connect_args={'check_same_thread': False})
            
            # 스키마 버전 확인
            with engine.connect() as conn:
                try:
                    result = conn.execute(text("SELECT version FROM _schema_version")).scalar()
                    if result != SCHEMA_VERSION:
                        messagebox.showerror("오류", 
                                           f"DB 스키마 버전이 일치하지 않습니다.\n"
                                           f"필요한 버전: {SCHEMA_VERSION}\n"
                                           f"발견된 버전: {result}", 
                                           parent=self)
                        return
                except Exception as e:
                    messagebox.showerror("오류", 
                                       f"DB 스키마 버전을 확인할 수 없습니다: {e}", 
                                       parent=self)
                    return
                
            # 기본 테이블 존재 여부 확인
            inspector = inspect(engine)
            required_tables = {'user', 'material', 'client', 'formulation'}
            existing_tables = set(inspector.get_table_names())
            
            missing_tables = required_tables - existing_tables
            if missing_tables:
                messagebox.showerror("오류", 
                                   f"선택한 DB 파일에 필요한 테이블이 없습니다:\n"
                                   f"{', '.join(missing_tables)}", 
                                   parent=self)
                return
                
            # 모든 검증을 통과하면 설정 저장
            self._save_and_restart(new_db_path, new_excel_path, 
                                 "새로운 공유 DB 경로가 설정되었습니다. 프로그램을 재시작합니다.")
                                 
        except Exception as e:
            messagebox.showerror("오류", 
                               f"DB 파일 검증 중 오류가 발생했습니다: {e}", 
                               parent=self)
            
        finally:
            if engine is not None:
                engine.dispose()

    def _save_excel_path_only(self, new_excel_path):
        try:
            self._save_config('Paths', 'excel_dir', new_excel_path)
            messagebox.showinfo("설정 저장", "엑셀 경로가 저장되었습니다.", parent=self)
        except Exception as e:
            messagebox.showerror("저장 오류", f"설정 저장 중 오류가 발생했습니다: {e}", parent=self)

    def _save_config(self, section, option, value):
        config = configparser.ConfigParser(interpolation=None)
        config.read(self.config_path, encoding='utf-8')
        if not config.has_section(section):
            config.add_section(section)
        config.set(section, option, value)
        with open(self.config_path, 'w', encoding='utf-8') as configfile:
            config.write(configfile)

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
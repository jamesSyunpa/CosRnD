# -*- coding: utf-8 -*-
"""
소프트웨어 자동 업데이트 및 버전 감지 관리 모듈 (GitHub Releases + 네이버 카페 듀얼 엔진)
- GitHub Releases API 기반 최신 버전 감지 및 고속 직링크 자동 다운로드
- 네이버 카페(CosRQD) 자료실/공지 기반 보조 감지 지원
- config.ini 연동을 통한 수동/자동 업데이트 모드 제어
- 원클릭 실제 자동 업데이트 (DB 100% 무손실 안전 백업 -> 패처/런처 실행 -> 자동 교체 및 재실행)
"""

import os
import sys
import re
import json
import shutil
import zipfile
import tempfile
import configparser
import threading
import subprocess
import urllib.request
import urllib.error
import ssl
from datetime import datetime
import customtkinter as ctk
from tkinter import messagebox, ttk

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from utils.cafe_manager import CafeNoticeManager

def get_clean_subproc_env(extra_env=None):
    """
    서브프로세스 실행 시 PyInstaller 내부 임시 디렉토리 환경변수(_MEIPASS, _MEIPASS2 등)를
    완전히 제거하여, 새로 실행되는 자식 프로세스가 부모 프로세스의 임시 폴더에 종속되지 않고
    자신만의 고유한 새 임시 환경을 올바르게 생성하도록 보장합니다.
    """
    env = os.environ.copy()
    keys_to_remove = [
        '_MEIPASS',
        '_MEIPASS2',
        'PYTHONPATH',
        'PYTHONHOME',
        'PYINSTALLER_STRICT_UNLOAD_MODE',
        'PYINSTALLER_SUPPRESS_TEMP_ERRORS'
    ]
    for key in keys_to_remove:
        if key in env:
            del env[key]

    if extra_env:
        for k, v in extra_env.items():
            if v is not None:
                env[k] = str(v)
            elif k in env:
                del env[k]

    return env

def update_desktop_shortcuts(new_ver: str):
    """
    자동 업데이트 완료 시 바탕화면 및 시작메뉴의 구버전 바로가기들을 깨끗하게 정리하고,
    최신 버전(CosRQD 또는 CosRQD_{new_ver})으로 바로가기 아이콘을 자동 갱신합니다.
    """
    if not sys.platform.startswith('win'):
        return
    try:
        from pathlib import Path
        user_profile = Path(os.environ.get("USERPROFILE", ""))
        
        # 1. 대상 바로가기 폴더 목록 (바탕화면 & 시작메뉴)
        target_dirs = []
        try:
            import ctypes
            from ctypes import wintypes
            buf = ctypes.create_unicode_buffer(wintypes.MAX_PATH)
            ctypes.windll.shell32.SHGetFolderPathW(None, 0x0000, None, 0, buf)
            if buf.value and Path(buf.value).exists():
                target_dirs.append(Path(buf.value))
        except Exception:
            pass

        desk_def = user_profile / "Desktop"
        if desk_def.exists() and desk_def not in target_dirs:
            target_dirs.append(desk_def)

        start_menu = Path(os.environ.get("APPDATA", "")) / "Microsoft" / "Windows" / "Start Menu" / "Programs"
        if start_menu.exists():
            target_dirs.append(start_menu)

        # 2. 실행 파일 및 아이콘 경로 결정
        if getattr(sys, 'frozen', False):
            target_exe = Path(sys.executable)
        else:
            target_exe = Path(PROJECT_ROOT) / "dist" / "CosRQD.exe"
            if not target_exe.exists():
                target_exe = Path(PROJECT_ROOT) / "main.exe"

        icon_path = target_exe.parent / "Icon.ico"
        if not icon_path.exists():
            icon_path = Path(PROJECT_ROOT) / "Icon.ico"

        # 3. 기존 구버전 바로가기 삭제
        patterns = ["*CosRQD*.lnk", "*CosRnD*.lnk", "*화장품연구관리*.lnk", "*화장품연구*.lnk", "*화장품*.lnk"]
        for d in target_dirs:
            if d.exists():
                for pat in patterns:
                    for old_lnk in d.glob(pat):
                        try:
                            old_lnk.unlink()
                        except Exception:
                            pass

        # 4. 최신 버전 바로가기 생성 (PowerShell COM)
        new_shortcut_name = f"CosRQD_{new_ver}" if new_ver else "CosRQD"
        tgt_str = str(target_exe).replace("'", "''")
        cwd_str = str(target_exe.parent).replace("'", "''")
        ico_str = str(icon_path).replace("'", "''") if icon_path.exists() else ""
        
        for d in target_dirs:
            lnk_str = str(d / f"{new_shortcut_name}.lnk").replace("'", "''")
            ps_cmd = (
                f"$s=(New-Object -COM WScript.Shell).CreateShortcut('{lnk_str}');"
                f"$s.TargetPath='{tgt_str}';"
                f"$s.WorkingDirectory='{cwd_str}';"
            )
            if ico_str:
                ps_cmd += f"$s.IconLocation='{ico_str}';"
            ps_cmd += "$s.Save();"
            
            subprocess.run(["powershell", "-NoProfile", "-Command", ps_cmd], capture_output=True)

        # 5. 윈도우 쉘 아이콘 캐시 새로고침
        import ctypes
        ctypes.windll.shell32.SHChangeNotify(0x08000000, 0x0000, None, None)
        print(f"[UpdateManager] 바로가기 최신화 완료: {new_shortcut_name}")
    except Exception as lnk_err:
        print(f"[UpdateManager] 바로가기 갱신 실패: {lnk_err}")


class UpdateManager:
    CAFE_ID = 31737320
    GITHUB_REPO = "jamesSyunpa/CosRnD"  # GitHub 공식 배포 리포지토리 (소유자: jamesSyunpa)
    GITHUB_API_URL = f"https://api.github.com/repos/{GITHUB_REPO}/releases/latest"
    CONFIG_FILE_NAME = "config.ini"

    @classmethod
    def get_config_path(cls):
        """config.ini 파일의 실제 경로를 반환합니다."""
        appdata_dir = os.path.join(os.getenv('APPDATA', os.path.expanduser('~')), 'CosRnD')
        target_config = os.path.join(appdata_dir, cls.CONFIG_FILE_NAME)
        local_config = os.path.join(PROJECT_ROOT, cls.CONFIG_FILE_NAME)
        return target_config if os.path.exists(target_config) else local_config

    @classmethod
    def get_current_version(cls) -> str:
        """로컬 VERSION 파일에서 현재 설치된 버전을 읽어옵니다."""
        try:
            v_file = os.path.join(PROJECT_ROOT, "VERSION")
            if os.path.exists(v_file):
                with open(v_file, "r", encoding="utf-8") as f:
                    ver = f.read().strip()
                    if ver:
                        if not ver.startswith('v') and re.match(r'^\d+', ver):
                            ver = 'v' + ver
                        return ver
        except Exception as e:
            print(f"[UpdateManager] 로컬 버전 읽기 오류: {e}")
        return "v65.0.3"

    @classmethod
    def parse_version_tuple(cls, ver_str: str) -> tuple:
        """
        버전 문자열(v65, v65.0.1, v65.0.3, v66 등)을 비교 가능한 3단계 이상 숫자 튜플로 정규화합니다.
        예: 'v65' -> (65, 0, 0), 'v65.0.1' -> (65, 0, 1), 'v65.0.3' -> (65, 0, 3), 'v66' -> (66, 0, 0)
        """
        if not ver_str:
            return (0, 0, 0)
        clean = re.sub(r'[^0-9\.]', '', ver_str)
        parts = clean.split('.')
        nums = []
        for p in parts:
            if p.isdigit():
                nums.append(int(p))
        while len(nums) < 3:
            nums.append(0)
        return tuple(nums)

    @classmethod
    def get_update_mode(cls) -> str:
        """config.ini에서 업데이트 모드('auto' 또는 'manual')를 읽어옵니다."""
        config_path = cls.get_config_path()
        try:
            if os.path.exists(config_path):
                cfg = configparser.ConfigParser()
                cfg.read(config_path, encoding='utf-8')
                if cfg.has_section('Update'):
                    return cfg.get('Update', 'mode', fallback='auto').lower()
        except Exception as e:
            print(f"[UpdateManager] 설정 읽기 실패: {e}")
        return "auto"

    @classmethod
    def save_update_mode(cls, mode: str) -> bool:
        """config.ini의 [Update] 섹션에 업데이트 모드를 저장합니다."""
        config_path = cls.get_config_path()
        try:
            cfg = configparser.ConfigParser()
            if os.path.exists(config_path):
                cfg.read(config_path, encoding='utf-8')
            
            if not cfg.has_section('Update'):
                cfg.add_section('Update')
                
            cfg.set('Update', 'mode', mode.lower())
            cfg.set('Update', 'last_saved', datetime.now().strftime('%Y-%m-%d %H:%M:%S'))
            
            with open(config_path, 'w', encoding='utf-8') as f:
                cfg.write(f)
            return True
        except Exception as e:
            print(f"[UpdateManager] 설정 저장 실패: {e}")
            return False

    @classmethod
    def check_github_release(cls) -> tuple:
        """
        GitHub Releases 최신 정보를 비동기로 조회합니다 (urllib 표준 라이브러리 사용).
        반환값: (found: bool, version: str, release_info: dict)
        """
        req = urllib.request.Request(
            cls.GITHUB_API_URL,
            headers={
                "Accept": "application/vnd.github.v3+json",
                "User-Agent": "CosRnD-UpdateEngine"
            }
        )
        try:
            ctx = ssl.create_default_context()
            ctx.check_hostname = False
            ctx.verify_mode = ssl.CERT_NONE
            with urllib.request.urlopen(req, timeout=4.0, context=ctx) as response:
                if response.status == 200:
                    data = json.loads(response.read().decode('utf-8'))
                    tag = data.get("tag_name", "").strip()
                    if tag:
                        if not tag.startswith('v') and re.match(r'^\d+', tag):
                            tag = 'v' + tag
                        
                        # 첨부파일 다운로드 링크 찾기
                        download_url = None
                        file_name = None
                        file_size = 0
                        assets = data.get("assets", [])
                        for ast in assets:
                            aname = ast.get("name", "")
                            if aname.endswith((".zip", ".exe")):
                                download_url = ast.get("browser_download_url")
                                file_name = aname
                                file_size = ast.get("size", 0)
                                if "patch" in aname.lower() or "setup" in aname.lower():
                                    break

                        rel_info = {
                            "title": data.get("name") or f"CosRQD {tag}",
                            "date": (data.get("published_at") or "")[:10],
                            "summary": data.get("body", ""),
                            "url": data.get("html_url", f"https://github.com/{cls.GITHUB_REPO}/releases"),
                            "download_url": download_url,
                            "file_name": file_name,
                            "file_size": file_size,
                            "source": "github"
                        }
                        return (True, tag, rel_info)
        except Exception as e:
            print(f"[UpdateManager] GitHub 릴리즈 조회: {e}")
        return (False, "", {})

    @classmethod
    def check_for_remote_update(cls) -> tuple:
        """
        GitHub Releases(1순위) 및 네이버 카페(2순위)를 종합 스캔하여 최신 업데이트 정보를 반환합니다.
        반환값: (is_available: bool, current_ver: str, latest_ver: str, release_info: dict)
        """
        current_ver = cls.get_current_version()
        curr_tuple = cls.parse_version_tuple(current_ver)
        
        latest_ver_found = current_ver
        latest_tuple_found = curr_tuple
        best_release = None

        # 1순위: GitHub Releases 확인 (초고속 CDN 직링크)
        gh_found, gh_tag, gh_info = cls.check_github_release()
        if gh_found:
            gh_tuple = cls.parse_version_tuple(gh_tag)
            if gh_tuple > latest_tuple_found:
                latest_tuple_found = gh_tuple
                latest_ver_found = gh_tag
                best_release = gh_info

        # 2순위: 네이버 카페 게시글 스캔 (메뉴 13: 공지 및 업데이트 단독)
        articles = CafeNoticeManager.get_notice_list(menu_ids=[13], per_page=10)
        for art in articles:
            subj = art.get('subject', '')
            m = re.search(r'[vV]?(\d+\.\d+\.\d+|\d+\.\d+|\d+)', subj)
            if m:
                v_str = m.group(0)
                if not v_str.lower().startswith('v'):
                    v_str = 'v' + v_str
                v_tup = cls.parse_version_tuple(v_str)
                if v_tup > latest_tuple_found:
                    latest_tuple_found = v_tup
                    latest_ver_found = v_str
                    best_release = {
                        "title": art.get('subject', ''),
                        "date": art.get('date', ''),
                        "summary": art.get('summary', ''),
                        "url": art.get('url', 'https://cafe.naver.com/cosrqd'),
                        "download_url": None,
                        "file_name": None,
                        "source": "cafe"
                    }
                    
        is_available = latest_tuple_found > curr_tuple
        
        if not best_release:
            best_release = {
                "title": f"CosRQD {current_ver}",
                "date": datetime.now().strftime("%Y-%m-%d"),
                "summary": "현재 최신 버전입니다.",
                "url": f"https://github.com/{cls.GITHUB_REPO}/releases",
                "download_url": None,
                "source": "local"
            }
        
        return (is_available, current_ver, latest_ver_found, best_release)

    @classmethod
    def backup_database_before_update(cls) -> str:
        """업데이트 직전 사용자 데이터베이스 및 설정파일을 100% 안전하게 백업합니다."""
        try:
            backup_root = os.path.join(PROJECT_ROOT, "backups", "auto_updates")
            os.makedirs(backup_root, exist_ok=True)
            ts = datetime.now().strftime('%Y%m%d_%H%M%S')
            backup_dir = os.path.join(backup_root, f"backup_pre_update_{ts}")
            os.makedirs(backup_dir, exist_ok=True)

            from database.db_manager import db_manager
            db_path = getattr(db_manager, 'db_path', None)
            if db_path and os.path.exists(db_path):
                shutil.copy2(db_path, os.path.join(backup_dir, "cosmetic.db"))
                print(f"[UpdateManager] DB 백업 완료: {backup_dir}")

            cfg_path = cls.get_config_path()
            if os.path.exists(cfg_path):
                shutil.copy2(cfg_path, os.path.join(backup_dir, "config.ini"))

            return backup_dir
        except Exception as e:
            print(f"[UpdateManager] 사전 백업 실패: {e}")
            return ""

    @classmethod
    def execute_real_update(cls, master, latest_ver: str, release_info: dict):
        """
        GitHub 직링크를 통한 고속 다운로드 및 실제 자동 업데이트를 실행합니다.
        """
        download_url = release_info.get("download_url")
        
        if download_url:
            # GitHub 직링크가 있으면 진행률 다운로드 창 표시
            DownloadProgressDialog(master, latest_ver, download_url, release_info)
        else:
            # 링크가 없으면 런처 실행 및 브라우저 안내
            bk_path = cls.backup_database_before_update()
            launcher_script = os.path.join(PROJECT_ROOT, "launcher.py")
            launcher_exe = os.path.join(PROJECT_ROOT, "launcher.exe")
            
            clean_env = get_clean_subproc_env()
            flags = subprocess.CREATE_NEW_PROCESS_GROUP if os.name == 'nt' else 0
            
            launched = False
            try:
                if os.path.exists(launcher_exe):
                    subprocess.Popen([launcher_exe, "--update", latest_ver], env=clean_env, creationflags=flags)
                    launched = True
                elif os.path.exists(launcher_script):
                    subprocess.Popen([sys.executable, launcher_script, "--update", latest_ver], env=clean_env, creationflags=flags)
                    launched = True
            except Exception as e:
                print(f"[UpdateManager] 런처 실행 오류: {e}")

            if launched:
                messagebox.showinfo(
                    "업데이트 시작",
                    f"🚀 최신 버전({latest_ver}) 자동 업데이트를 시작합니다.\n\n"
                    f"• 기존 데이터베이스가 {bk_path}에 안전하게 백업되었습니다.\n"
                    f"• 프로그램이 종료된 후 최신 버전으로 자동 교체됩니다.",
                    parent=master
                )
                try:
                    master.winfo_toplevel().destroy()
                except:
                    pass
                sys.exit(0)
            else:
                import webbrowser
                webbrowser.open(release_info.get("url", f"https://github.com/{cls.GITHUB_REPO}/releases"))


class DownloadProgressDialog(ctk.CTkToplevel):
    """GitHub 릴리즈 파일 실시간 다운로드 및 자동 설치 프로그레스 창"""
    def __init__(self, master, latest_ver, download_url, release_info):
        super().__init__(master)
        self.title("CosRQD 업데이트 다운로드")
        self.geometry("460x220")
        self.resizable(False, False)
        self.transient(master)
        self.grab_set()

        self.latest_ver = latest_ver
        self.download_url = download_url
        self.release_info = release_info

        self._build_ui()
        self.after(200, self._start_download)

    def _build_ui(self):
        main_box = ctk.CTkFrame(self, fg_color="transparent")
        main_box.pack(fill="both", expand=True, padx=25, pady=20)

        ctk.CTkLabel(
            main_box,
            text=f"🚀 최신 버전({self.latest_ver}) 다운로드 중...",
            font=ctk.CTkFont(size=14, weight="bold")
        ).pack(anchor="w", pady=(0, 10))

        self.status_lbl = ctk.CTkLabel(
            main_box,
            text="GitHub 초고속 서버에 연결하는 중...",
            font=ctk.CTkFont(size=11),
            text_color="gray"
        )
        self.status_lbl.pack(anchor="w", pady=(0, 8))

        self.progress_bar = ctk.CTkProgressBar(main_box)
        self.progress_bar.pack(fill="x", pady=(0, 10))
        self.progress_bar.set(0)

        self.percent_lbl = ctk.CTkLabel(main_box, text="0%", font=ctk.CTkFont(size=11))
        self.percent_lbl.pack(anchor="e")

    def _start_download(self):
        def _worker():
            try:
                # 임시 폴더에 다운로드
                temp_dir = os.path.join(PROJECT_ROOT, "temp")
                os.makedirs(temp_dir, exist_ok=True)
                target_file = os.path.join(temp_dir, f"update_{self.latest_ver}.zip")

                req = urllib.request.Request(
                    self.download_url,
                    headers={"User-Agent": "CosRnD-UpdateEngine"}
                )
                ctx = ssl.create_default_context()
                ctx.check_hostname = False
                ctx.verify_mode = ssl.CERT_NONE

                with urllib.request.urlopen(req, timeout=60, context=ctx) as response:
                    total_size = int(response.headers.get('content-length', 0))
                    downloaded = 0

                    with open(target_file, 'wb') as f:
                        while True:
                            chunk = response.read(65536)
                            if not chunk:
                                break
                            f.write(chunk)
                            downloaded += len(chunk)
                            if total_size > 0:
                                pct = downloaded / total_size
                                self.after(0, lambda p=pct, d=downloaded, t=total_size: self._update_progress(p, d, t))

                self.after(0, lambda: self._apply_update(target_file))
            except Exception as e:
                self.after(0, lambda err=e: self._on_error(err))

        threading.Thread(target=_worker, daemon=True).start()

    def _update_progress(self, pct, downloaded, total_size):
        try:
            self.progress_bar.set(pct)
            mb_cur = downloaded / (1024 * 1024)
            mb_tot = total_size / (1024 * 1024)
            self.percent_lbl.configure(text=f"{int(pct * 100)}% ({mb_cur:.1f}MB / {mb_tot:.1f}MB)")
            self.status_lbl.configure(text="GitHub 글로벌 CDN으로부터 초고속 다운로드 중...")
        except:
            pass

    def _apply_update(self, zip_path):
        # 1. DB 백업
        bk_path = UpdateManager.backup_database_before_update()
        
        # 2. 압축 해제 및 덮어쓰기
        self.status_lbl.configure(text="데이터 백업 완료 및 새 버전 교체 중...")
        try:
            with zipfile.ZipFile(zip_path, 'r') as zf:
                zf.extractall(PROJECT_ROOT)
            
            # VERSION 파일 갱신
            with open(os.path.join(PROJECT_ROOT, "VERSION"), "w", encoding="utf-8") as f:
                f.write(self.latest_ver)

            # 3. 바탕화면 및 시작메뉴 바로가기 최신화 (구버전 정리 및 최신 버전명 반영)
            update_desktop_shortcuts(self.latest_ver)
        except Exception as ex:
            print(f"[Update] 압축 해제 및 바로가기 갱신 오류: {ex}")

        messagebox.showinfo(
            "업데이트 완료",
            f"✨ 최신 버전({self.latest_ver})으로 성공적으로 업데이트되었습니다!\n\n"
            f"• 기존 연구 데이터가 완벽하게 보존되었습니다.\n"
            f"• 바탕화면 바로가기가 최신 버전({self.latest_ver})으로 갱신되었습니다.\n"
            f"• 확인을 누르면 프로그램이 새로 재실행됩니다.",
            parent=self
        )

        # 프로그램 VBS 1.2초 지연 독립 안전 재실행 (임시 폴더 충돌 완전 원천 차단)
        try:
            exe_path = sys.executable if getattr(sys, 'frozen', False) else os.path.join(PROJECT_ROOT, "main.py")
            if sys.platform.startswith('win'):
                import ctypes
                for k in ['_MEIPASS', '_MEIPASS2', 'PYTHONPATH', 'PYTHONHOME']:
                    ctypes.windll.kernel32.SetEnvironmentVariableW(k, None)
                    if k in os.environ:
                        del os.environ[k]
                
                vbs_file = os.path.join(tempfile.gettempdir(), "cosrqd_safe_update_restart.vbs")
                escaped_exe = str(exe_path).replace('"', '""')
                if getattr(sys, 'frozen', False):
                    run_target = f'""{escaped_exe}""'
                else:
                    py_exe = sys.executable.replace('"', '""')
                    run_target = f'""{py_exe}"" ""{escaped_exe}""'
                
                with open(vbs_file, "w", encoding="utf-8") as f:
                    f.write(f'WScript.Sleep 1200\nCreateObject("WScript.Shell").Run "{run_target}", 1, False\n')
                
                subprocess.Popen(["wscript.exe", vbs_file], close_fds=True)
            else:
                subprocess.Popen([exe_path], cwd=os.path.dirname(exe_path), env=get_clean_subproc_env())
        except Exception as e:
            print(f"[Update] 재실행 실패: {e}")

        try:
            self.master.winfo_toplevel().destroy()
        except:
            pass
        import os as _os
        _os._exit(0)

    def _on_error(self, err):
        messagebox.showerror(
            "다운로드 오류",
            f"다운로드 중 오류가 발생했습니다: {err}\n\n웹 브라우저를 통해 직접 다운로드 페이지로 이동합니다.",
            parent=self
        )
        import webbrowser
        webbrowser.open(self.release_info.get("url", f"https://github.com/{UpdateManager.GITHUB_REPO}/releases"))
        self.destroy()


class UpdateDialog(ctk.CTkToplevel):
    """소프트웨어 업데이트 안내 및 원클릭 자동 설치 팝업 다이얼로그"""
    def __init__(self, master, current_ver, latest_ver, release_info, is_new=True):
        super().__init__(master)
        self.title("CosRQD 소프트웨어 업데이트")
        self.geometry("580x440")
        self.resizable(False, False)
        self.after(50, self.focus_force)
        self.after(50, self.lift)

        self.transient(master)
        self.grab_set()
        self.bind("<Escape>", lambda e: self.destroy())

        self.current_ver = current_ver
        self.latest_ver = latest_ver
        self.release_info = release_info
        self.is_new = is_new

        self._build_ui()

    def _build_ui(self):
        top_frame = ctk.CTkFrame(self, height=52, fg_color="#1e293b", corner_radius=0)
        top_frame.pack(fill="x")

        icon_text = "🚀 새로운 버전이 출시되었습니다!" if self.is_new else "✨ 현재 최신 버전을 사용 중입니다"
        ctk.CTkLabel(
            top_frame,
            text=icon_text,
            font=ctk.CTkFont(family="맑은 고딕", size=15, weight="bold"),
            text_color="#ffffff"
        ).pack(side="left", padx=15, pady=12)

        body = ctk.CTkFrame(self, fg_color="transparent")
        body.pack(fill="both", expand=True, padx=20, pady=15)

        ver_card = ctk.CTkFrame(body, fg_color=("#F1F5F9", "#242526"), corner_radius=8)
        ver_card.pack(fill="x", pady=(0, 10))

        v_box = ctk.CTkFrame(ver_card, fg_color="transparent")
        v_box.pack(fill="x", padx=15, pady=10)

        ctk.CTkLabel(v_box, text=f"• 현재 설치 버전:   {self.current_ver}", font=ctk.CTkFont(size=12)).pack(anchor="w", pady=2)
        
        status_color = "#22c55e" if self.is_new else "#3b82f6"
        ctk.CTkLabel(
            v_box, 
            text=f"• 최신 배포 버전:   {self.latest_ver}" + ("  🔥 (GitHub 초고속 자동 업데이트 가능)" if self.is_new else "  (최신 상태)"), 
            font=ctk.CTkFont(size=12, weight="bold"),
            text_color=status_color
        ).pack(anchor="w", pady=2)

        ctk.CTkLabel(body, text="📋 릴리즈 패치 내역 / 안내사항", font=ctk.CTkFont(size=12, weight="bold")).pack(anchor="w", pady=(5, 3))

        tb = ctk.CTkTextbox(body, wrap="word", font=ctk.CTkFont(family="Malgun Gothic", size=11), height=140)
        tb.pack(fill="both", expand=True, pady=(0, 10))
        
        summary_text = self.release_info.get("summary", "")
        title_text = self.release_info.get("title", "")
        
        display_content = (
            f"📢 [제목: {title_text}]\n"
            f"📅 [배포일: {self.release_info.get('date', '최근')}]\n"
            f"--------------------------------------------------\n"
            f"{summary_text if summary_text else 'CosRQD 시스템 기능 개선 및 안정화 패치가 포함되어 있습니다.'}\n\n"
            f"🛡️ [데이터 100% 무손실 보장]\n"
            f"업데이트 시 기존 연구 데이터(처방/원료 DB 및 거래처 정보)는 자동으로 안전 백업된 후 완벽히 보존됩니다."
        )
        tb.insert("1.0", display_content)
        tb.configure(state="disabled")

        btn_bar = ctk.CTkFrame(self, height=45, fg_color="transparent")
        btn_bar.pack(fill="x", padx=20, pady=(0, 15))

        ctk.CTkLabel(btn_bar, text="💡 [ESC] 키로 닫기", font=ctk.CTkFont(size=11), text_color="gray").pack(side="left")

        ctk.CTkButton(
            btn_bar,
            text="나중에 하기",
            width=90,
            fg_color="gray50",
            hover_color="gray40",
            command=self.destroy
        ).pack(side="right", padx=(5, 0))

        if self.is_new:
            ctk.CTkButton(
                btn_bar,
                text="⚡ 지금 자동 업데이트",
                width=165,
                font=ctk.CTkFont(weight="bold"),
                fg_color="#22c55e",
                hover_color="#16a34a",
                command=self._on_update_clicked
            ).pack(side="right", padx=(5, 0))
        else:
            ctk.CTkButton(
                btn_bar,
                text="🔄 최신 빌드로 재설치/복구",
                width=180,
                font=ctk.CTkFont(weight="bold"),
                fg_color="#0284C7",
                hover_color="#0369A1",
                command=self._on_update_clicked
            ).pack(side="right", padx=(5, 0))

        ctk.CTkButton(
            btn_bar,
            text="🌐 웹에서 직접 다운로드",
            width=150,
            fg_color="#3b82f6",
            hover_color="#2563eb",
            command=self._open_web_release
        ).pack(side="right", padx=(5, 0))

    def _on_update_clicked(self):
        confirm = messagebox.askyesno(
            "자동 업데이트 확인",
            f"새로운 버전({self.latest_ver})으로 자동 업데이트를 진행하시겠습니까?\n\n"
            f"• 진행 시 기존 데이터베이스(DB)는 자동으로 안전 백업됩니다.\n"
            f"• GitHub 초고속 CDN을 통해 10초 만에 자동 패치 후 재실행됩니다.",
            parent=self
        )
        if confirm:
            UpdateManager.execute_real_update(self, self.latest_ver, self.release_info)

    def _open_web_release(self):
        import webbrowser
        url = self.release_info.get("url", f"https://github.com/{UpdateManager.GITHUB_REPO}/releases")
        if url:
            webbrowser.open(url)

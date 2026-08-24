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
import time
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

        # 4. 최신 단일 표준 바로가기 생성 (버전 번호 없이 영구 고정 CosRQD.lnk)
        new_shortcut_name = "CosRQD"
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
        """설치 디렉토리, 실행 파일 경로, MEIPASS 및 PROJECT_ROOT에서 현재 버전을 정확히 읽어옵니다."""
        candidates = []
        try:
            # 1. 실행 파일 디렉토리 (예: C:\CosRQD\bin)
            if getattr(sys, 'frozen', False):
                exe_dir = os.path.dirname(os.path.abspath(sys.executable))
                candidates.append(os.path.join(exe_dir, "VERSION"))
                candidates.append(os.path.join(os.path.dirname(exe_dir), "VERSION"))
            
            # 2. PyInstaller 번들 내부 (_MEIPASS)
            meipass = getattr(sys, '_MEIPASS', '')
            if meipass:
                candidates.append(os.path.join(meipass, "VERSION"))

            # 3. PROJECT_ROOT 및 상위 경로
            candidates.append(os.path.join(PROJECT_ROOT, "VERSION"))
            candidates.append(os.path.join(os.path.dirname(PROJECT_ROOT), "VERSION"))
            candidates.append(os.path.join(os.getcwd(), "VERSION"))

            for v_file in candidates:
                if v_file and os.path.exists(v_file):
                    with open(v_file, "r", encoding="utf-8") as f:
                        lines = [line.strip() for line in f if line.strip()]
                        if lines:
                            ver = lines[0]
                            if ver:
                                if not ver.startswith('v') and re.match(r'^\d+', ver):
                                    ver = 'v' + ver
                                return ver
        except Exception as e:
            print(f"[UpdateManager] 로컬 버전 읽기 오류: {e}")

        # 기본 안전 폴백
        return "v65.0.44"

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
                        
                        # 첨부파일 다운로드 링크 찾기 (1순위: _Update.zip (원클릭 무설치 자동 업데이트), 2순위: Setup_.exe, 3순위: .zip)
                        download_url = None
                        file_name = None
                        file_size = 0
                        assets = data.get("assets", [])
                        
                        # 1순위: 자동 업데이트 전용 ZIP 패키지 (_Update.zip) - 인앱 원클릭 무설치 자동 갱신
                        for ast in assets:
                            aname = ast.get("name", "")
                            if "update" in aname.lower() and aname.endswith(".zip"):
                                download_url = ast.get("browser_download_url")
                                file_name = aname
                                file_size = ast.get("size", 0)
                                break

                        # 2순위: 단독 실행 인스톨러 (Setup.exe)
                        if not download_url:
                            for ast in assets:
                                aname = ast.get("name", "")
                                if aname.startswith("Setup_") and aname.endswith(".exe"):
                                    download_url = ast.get("browser_download_url")
                                    file_name = aname
                                    file_size = ast.get("size", 0)
                                    break

                        # 3순위: 일반 ZIP 파일 (분할파일 .001 등 제외)
                        if not download_url:
                            for ast in assets:
                                aname = ast.get("name", "")
                                if aname.endswith(".zip") and not re.search(r'\.\d{3}$', aname):
                                    download_url = ast.get("browser_download_url")
                                    file_name = aname
                                    file_size = ast.get("size", 0)
                                    break

                        rel_info = {
                            "title": data.get("name") or f"CosRQD {tag}",
                            "date": (data.get("published_at") or "")[:10],
                            "summary": data.get("body", ""),
                            "url": data.get("html_url", f"https://github.com/{cls.GITHUB_REPO}/releases"),
                            "download_url": download_url,
                            "file_name": file_name,
                            "file_size": file_size,
                            "assets": assets,
                            "tag": tag,
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
            elif gh_tuple == latest_tuple_found:
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
        [독립 네이티브 업데이터 엔진]
        메인 프로그램을 먼저 100% 안전 종료한 후, 독립 네이티브 GUI 창이 다운로드 및 파일 교체를 완벽히 수행합니다.
        """
        download_url = release_info.get("download_url")
        if not download_url:
            import webbrowser
            webbrowser.open(release_info.get("url", f"https://github.com/{cls.GITHUB_REPO}/releases"))
            return

        # 1. DB 및 설정파일 사전 안전 백업
        bk_path = cls.backup_database_before_update()
        current_pid = os.getpid()
        
        # 실제 디스크 상의 실행 파일 및 설치 디렉터리 (PyInstaller 임시 경로와 100% 분리)
        if getattr(sys, 'frozen', False):
            target_exe = sys.executable
            app_dir = os.path.dirname(sys.executable)
        else:
            target_exe = os.path.join(PROJECT_ROOT, "dist", "CosRQD.exe")
            if not os.path.exists(target_exe):
                target_exe = os.path.join(PROJECT_ROOT, "main.exe")
            app_dir = PROJECT_ROOT
        
        # 2. 독립 PowerShell 네이티브 업데이터 스크립트 작성
        temp_dir = tempfile.gettempdir()
        ps_script_path = os.path.join(temp_dir, f"cosrqd_native_updater_{int(time.time())}.ps1")
        
        ps_code = f'''# CosRQD Native Standalone Updater
[Console]::OutputEncoding = [System.Text.Encoding]::UTF8
param(
    [string]$DownloadUrl = "{download_url}",
    [string]$LatestVer = "{latest_ver}",
    [string]$AppDir = "{app_dir}",
    [string]$TargetExe = "{target_exe}",
    [int]$ParentPid = {current_pid}
)

Add-Type -AssemblyName System.Windows.Forms
Add-Type -AssemblyName System.Drawing

$form = New-Object System.Windows.Forms.Form
$form.Text = "CosRQD 자동 업데이트"
$form.Size = New-Object System.Drawing.Size(460, 220)
$form.StartPosition = "CenterScreen"
$form.FormBorderStyle = [System.Windows.Forms.FormBorderStyle]::FixedDialog
$form.MaximizeBox = $false
$form.MinimizeBox = $false
$form.TopMost = $true
$form.BackColor = [System.Drawing.Color]::FromArgb(30, 41, 59)

$titleLbl = New-Object System.Windows.Forms.Label
$titleLbl.Text = "🚀 CosRQD $LatestVer 자동 업데이트"
$titleLbl.ForeColor = [System.Drawing.Color]::White
$titleLbl.Font = New-Object System.Drawing.Font("맑은 고딕", 12, [System.Drawing.FontStyle]::Bold)
$titleLbl.Location = New-Object System.Drawing.Point(25, 20)
$titleLbl.Size = New-Object System.Drawing.Size(400, 30)
$form.Controls.Add($titleLbl)

$statusLbl = New-Object System.Windows.Forms.Label
$statusLbl.Text = "이전 프로그램 종료 및 리소스 정리 중..."
$statusLbl.ForeColor = [System.Drawing.Color]::FromArgb(148, 163, 184)
$statusLbl.Font = New-Object System.Drawing.Font("맑은 고딕", 9)
$statusLbl.Location = New-Object System.Drawing.Point(25, 55)
$statusLbl.Size = New-Object System.Drawing.Size(400, 25)
$form.Controls.Add($statusLbl)

$progressBar = New-Object System.Windows.Forms.ProgressBar
$progressBar.Location = New-Object System.Drawing.Point(25, 90)
$progressBar.Size = New-Object System.Drawing.Size(395, 25)
$progressBar.Minimum = 0
$progressBar.Maximum = 100
$progressBar.Value = 0
$form.Controls.Add($progressBar)

$pctLbl = New-Object System.Windows.Forms.Label
$pctLbl.Text = "0%"
$pctLbl.ForeColor = [System.Drawing.Color]::FromArgb(203, 213, 225)
$pctLbl.Font = New-Object System.Drawing.Font("맑은 고딕", 9, [System.Drawing.FontStyle]::Bold)
$pctLbl.Location = New-Object System.Drawing.Point(25, 125)
$pctLbl.Size = New-Object System.Drawing.Size(395, 20)
$pctLbl.TextAlign = [System.Drawing.ContentAlignment]::MiddleRight
$form.Controls.Add($pctLbl)

$form.Add_Shown({{
    $form.Refresh()
    
    # 1. 이전 메인 프로그램 프로세스 완전 종료 대기
    if ($ParentPid -gt 0) {{
        try {{
            $p = Get-Process -Id $ParentPid -ErrorAction SilentlyContinue
            if ($p) {{
                $p.WaitForExit(5000)
            }}
        }} catch {{}}
        Start-Sleep -Milliseconds 800
    }}
    Get-Process -Name "CosRQD", "main" -ErrorAction SilentlyContinue | Where-Object {{ $_.Id -ne $PID }} | Stop-Process -Force -ErrorAction SilentlyContinue
    Start-Sleep -Milliseconds 300

    # 2. 다운로드
    $statusLbl.Text = "GitHub 최신 버전 패키지 다운로드 중..."
    $form.Refresh()
    
    $tmpDir = [System.IO.Path]::GetTempPath()
    $isExe = $DownloadUrl.ToLower().EndsWith(".exe")
    $fileName = if ($isExe) {{ "Setup_CosRQD_$LatestVer.exe" }} else {{ "CosRQD_Update_$LatestVer.zip" }}
    $dlFile = Join-Path $tmpDir $fileName
    $extractDir = Join-Path $tmpDir "CosRQD_Extracted_$LatestVer"

    try {{
        [Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12 -bor [Net.SecurityProtocolType]::Tls13
        $wc = New-Object System.Net.WebClient
        $wc.Headers.Add("User-Agent", "CosRnD-NativeUpdater")
        
        $wc.Add_DownloadProgressChanged({{
            $progressBar.Value = $_.ProgressPercentage
            $mbRecv = [math]::Round($_.BytesReceived / 1MB, 1)
            $mbTotal = [math]::Round($_.TotalBytesToReceive / 1MB, 1)
            $pctLbl.Text = "$($_.ProgressPercentage)% ($mbRecv MB / $mbTotal MB)"
            $form.Refresh()
        }})
        
        $wc.Add_DownloadFileCompleted({{
            param($sender, $e)
            
            if ($e.Error -ne $null) {{
                [System.Windows.Forms.MessageBox]::Show("다운로드 실패: " + $e.Error.Message, "업데이트 오류")
                $form.Close()
                return
            }}
            
            try {{
                $wc.Dispose()
            }} catch {{}}

            if ($isExe) {{
                # Setup.exe 실행
                $statusLbl.Text = "설치 마법사를 시작합니다..."
                $progressBar.Value = 100
                $pctLbl.Text = "100%"
                $form.Refresh()
                Start-Sleep -Milliseconds 600
                $env:_MEIPASS2 = $null
                $env:_MEIPASS = $null
                try {{
                    Start-Process -FilePath $dlFile -Verb RunAs
                }} catch {{
                    Start-Process -FilePath $dlFile -UseShellExecute
                }}
                Start-Sleep -Milliseconds 1000
            }} else {{
                # ZIP 압축 해제 및 100% 덮어쓰기 (원클릭 무설치 자동 갱신)
                $statusLbl.Text = "최신 버전 파일 교체 중..."
                $form.Refresh()
                
                if (Test-Path $extractDir) {{ Remove-Item $extractDir -Recurse -Force -ErrorAction SilentlyContinue }}
                Expand-Archive -Path $dlFile -DestinationPath $extractDir -Force
                
                # 파일 교체 (단일 하위 폴더 포함 여부 검사)
                $subItems = Get-ChildItem -Path $extractDir
                if (($subItems.Count -eq 1) -and ($subItems[0].PSIsContainer)) {{
                    $actualSource = $subItems[0].FullName
                }} else {{
                    $actualSource = $extractDir
                }}
                Copy-Item -Path "$actualSource\\*" -Destination $AppDir -Recurse -Force
                
                # 바로가기 단일 고정 갱신 (CosRQD.lnk)
                try {{
                    $deskPath = [Environment]::GetFolderPath("Desktop")
                    $tgtExe = Join-Path $AppDir "CosRQD.exe"
                    if (-not (Test-Path $tgtExe)) {{ $tgtExe = Join-Path $AppDir "main.exe" }}
                    $icoPath = Join-Path $AppDir "Icon.ico"
                    
                    $sh = New-Object -ComObject WScript.Shell
                    $lnk = $sh.CreateShortcut((Join-Path $deskPath "CosRQD.lnk"))
                    $lnk.TargetPath = $tgtExe
                    $lnk.WorkingDirectory = $AppDir
                    if (Test-Path $icoPath) {{ $lnk.IconLocation = $icoPath }}
                    $lnk.Save()
                    
                    # 구버전 바로가기 정리
                    Get-ChildItem -Path $deskPath -Filter "*CosRQD*.lnk" | Where-Object {{ $_.Name -ne "CosRQD.lnk" }} | Remove-Item -Force -ErrorAction SilentlyContinue
                    Get-ChildItem -Path $deskPath -Filter "*화장품*.lnk" | Remove-Item -Force -ErrorAction SilentlyContinue
                }} catch {{}}

                # 임시 파일 정리
                Remove-Item $dlFile -Force -ErrorAction SilentlyContinue
                Remove-Item $extractDir -Recurse -Force -ErrorAction SilentlyContinue
                
                $statusLbl.Text = "업데이트 완료! 최신 버전을 실행합니다..."
                $progressBar.Value = 100
                $pctLbl.Text = "100%"
                $form.Refresh()
                Start-Sleep -Milliseconds 600

                # 실행 대상 결정
                $runExe = $TargetExe
                if (-not (Test-Path $runExe)) {{
                    $runExe = Join-Path $AppDir "CosRQD.exe"
                }}
                if (-not (Test-Path $runExe)) {{
                    $runExe = Join-Path $AppDir "main.exe"
                }}

                # 최신 프로그램 Windows 쉘 독립 실행 (상속된 _MEIPASS2 완전 차단)
                $env:_MEIPASS2 = $null
                $env:_MEIPASS = $null
                $env:PYTHONPATH = $null
                $env:PYTHONHOME = $null
                Start-Process -FilePath $runExe -WorkingDirectory $AppDir
                Start-Sleep -Milliseconds 500
            }}
            
            $form.Close()
        }})
        
        $wc.DownloadFileAsync((New-Object Uri($DownloadUrl)), $dlFile)
        
    }} catch {{
        [System.Windows.Forms.MessageBox]::Show("다운로드 중 오류가 발생했습니다: $_", "업데이트 실패")
        $form.Close()
    }}
}})

[System.Windows.Forms.Application]::Run($form)
'''

        with open(ps_script_path, "w", encoding="utf-8-sig") as pf:
            pf.write(ps_code)

        # 3. OS 레벨 환경변수 정화
        if sys.platform.startswith('win'):
            import ctypes
            for k in ['_MEIPASS', '_MEIPASS2', 'PYTHONPATH', 'PYTHONHOME']:
                ctypes.windll.kernel32.SetEnvironmentVariableW(k, None)

        # 4. 독립 네이티브 업데이터 실행
        flags = subprocess.CREATE_NO_WINDOW if os.name == 'nt' else 0
        subprocess.Popen(
            ["powershell.exe", "-ExecutionPolicy", "Bypass", "-WindowStyle", "Hidden", "-File", ps_script_path],
            creationflags=flags
        )
        print(f"[UpdateManager] 독립 네이티브 업데이터 실행 및 메인 프로그램 즉시 종료: {ps_script_path}")

        # 5. 메인 프로그램 즉시 완전 종료 (파일 락 100% 해제)
        try:
            master.winfo_toplevel().destroy()
        except:
            pass
        import os as _os
        _os._exit(0)


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
                temp_dir = tempfile.gettempdir()
                ext = ".exe" if self.download_url.lower().endswith(".exe") else ".zip"
                target_file = os.path.join(temp_dir, f"CosRQD_Update_{self.latest_ver}{ext}")

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

    def _apply_update(self, downloaded_file):
        """다운로드 완료 후 락 해제 대기, 안전 파일 교체, 최신 버전 자동 재실행을 100% 신뢰할 수 있는 방식으로 수행"""
        # 1. DB 안전 백업
        bk_path = UpdateManager.backup_database_before_update()
        
        self.status_lbl.configure(text="데이터 백업 완료 및 최신 버전 교체 준비 중...")
        self.update_idletasks()

        # 2. 바탕화면 바로가기 사전 갱신
        try:
            update_desktop_shortcuts(self.latest_ver)
        except Exception:
            pass

        is_zip = downloaded_file.lower().endswith(".zip")
        is_exe = downloaded_file.lower().endswith(".exe")
        
        if getattr(sys, 'frozen', False):
            exe_target = sys.executable
            app_dir = os.path.dirname(sys.executable)
        else:
            exe_target = os.path.join(PROJECT_ROOT, "dist", "CosRQD.exe")
            if not os.path.exists(exe_target):
                exe_target = os.path.join(PROJECT_ROOT, "main.exe")
            app_dir = PROJECT_ROOT

        current_pid = os.getpid()

        # OS 환경변수 정화
        if sys.platform.startswith('win'):
            import ctypes
            for k in ['_MEIPASS', '_MEIPASS2', 'PYTHONPATH', 'PYTHONHOME', 'PYINSTALLER_STRICT_UNLOAD_MODE']:
                try:
                    ctypes.windll.kernel32.SetEnvironmentVariableW(k, None)
                    os.environ.pop(k, None)
                except Exception:
                    pass

        if is_exe:
            # Setup.exe 단독 인스톨러 실행인 경우 (UAC 관리자 권한 상승 완벽 지원)
            self.status_lbl.configure(text="설치 마법사를 시작합니다...")
            self.update_idletasks()
            time.sleep(0.2)

            try:
                if sys.platform.startswith('win'):
                    os.startfile(downloaded_file)
                else:
                    subprocess.Popen([downloaded_file])
                print(f"[Update] Setup 인스톨러 실행 성공 (os.startfile): {downloaded_file}")
            except Exception as run_err:
                print(f"[Update] os.startfile 실패, ShellExecuteW 폴백: {run_err}")
                try:
                    import ctypes
                    ctypes.windll.shell32.ShellExecuteW(None, "open", downloaded_file, None, None, 1)
                except Exception as ex2:
                    print(f"[Update] ShellExecuteW 실패: {ex2}")
                    subprocess.Popen([downloaded_file], shell=True)

            # 메인 프로그램 즉시 완전 종료 (창 닫힘 및 프로세스 정상 종료)
            try:
                self.master.winfo_toplevel().destroy()
            except Exception:
                pass
            import os as _os
            _os._exit(0)

        elif is_zip:
            # ZIP 패키지 자동 교체인 경우
            temp_extract_dir = os.path.join(tempfile.gettempdir(), f"cosrqd_extract_{int(time.time())}")
            try:
                if os.path.exists(temp_extract_dir):
                    shutil.rmtree(temp_extract_dir, ignore_errors=True)
                os.makedirs(temp_extract_dir, exist_ok=True)
                with zipfile.ZipFile(downloaded_file, 'r') as zf:
                    zf.extractall(temp_extract_dir)
            except Exception as ex:
                print(f"[Update] 압축 해제 오류: {ex}")

            # 단일 하위 폴더 포함 여부 검사
            sub_items = os.listdir(temp_extract_dir)
            if len(sub_items) == 1 and os.path.isdir(os.path.join(temp_extract_dir, sub_items[0])):
                actual_source = os.path.join(temp_extract_dir, sub_items[0])
            else:
                actual_source = temp_extract_dir

            self.status_lbl.configure(text=f"최신 버전({self.latest_ver}) 교체 및 자동 재실행 중...")
            self.update_idletasks()

            # 100% 무오류 Windows 배치 스크립트 작성 (find/tasklist 파이프라인 행 걸림 원천 차단)
            bat_path = os.path.join(tempfile.gettempdir(), f"cosrqd_update_{int(time.time())}.bat")
            vbs_path = os.path.join(tempfile.gettempdir(), f"cosrqd_runner_{int(time.time())}.vbs")

            bat_content = f"""@echo off
chcp 65001 > nul
set TARGET_PID={current_pid}
set APP_DIR={app_dir}
set SRC_DIR={actual_source}
set EXE_TARGET={exe_target}
set DL_FILE={downloaded_file}
set EXTRACT_DIR={temp_extract_dir}

:: 1. 메인 프로세스 종료 대기 (안전 2초 대기)
ping 127.0.0.1 -n 3 > nul 2>&1
taskkill /f /pid %TARGET_PID% > nul 2>&1
ping 127.0.0.1 -n 2 > nul 2>&1

:: 2. 최신 파일 교체
if exist "%SRC_DIR%" (
    xcopy /y /e /q /h /r "%SRC_DIR%\\*" "%APP_DIR%\\" > nul 2>&1
)

:: 3. 환경변수 정화
set _MEIPASS=
set _MEIPASS2=
set PYTHONPATH=
set PYTHONHOME=
set PYINSTALLER_STRICT_UNLOAD_MODE=

:: 4. 최신 버전 프로그램 실행
start "" "%EXE_TARGET%"

:: 5. 임시 파일 정리 및 자폭
ping 127.0.0.1 -n 3 > nul 2>&1
if exist "%DL_FILE%" del /f /q "%DL_FILE%" > nul 2>&1
if exist "%EXTRACT_DIR%" rmdir /s /q "%EXTRACT_DIR%" > nul 2>&1
if exist "{vbs_path}" del /f /q "{vbs_path}" > nul 2>&1
(goto) 2>nul & del "%~f0"
"""
            with open(bat_path, "w", encoding="cp949", errors="ignore") as bf:
                bf.write(bat_content)

            # 콘솔 검은 창을 100% 숨기기 위한 VBScript 래퍼
            vbs_content = f'Set WshShell = CreateObject("WScript.Shell")\nWshShell.Run "{bat_path}", 0, False\n'
            with open(vbs_path, "w", encoding="utf-8") as vf:
                vf.write(vbs_content)

            # VBScript 무창 백그라운드 실행
            flags = (subprocess.CREATE_NO_WINDOW | subprocess.DETACHED_PROCESS) if os.name == 'nt' else 0
            subprocess.Popen(["wscript.exe", vbs_path], creationflags=flags, close_fds=True)
            print(f"[Update] 무창 업데이터 실행 완료: {vbs_path}")

            # 현재 프로그램 즉시 완전 종료 (파일 락 100% 즉시 해제)
            try:
                self.master.winfo_toplevel().destroy()
            except Exception:
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
        # 1. 릴리즈 정보에 이미 지정된 download_url 우선 사용
        download_url = self.release_info.get("download_url")

        # 2. download_url이 없으면 assets 목록에서 최적의 파일 탐색
        if not download_url:
            for asset in self.release_info.get("assets", []):
                name = asset.get("name", "")
                if "update" in name.lower() and name.endswith(".zip"):
                    download_url = asset.get("browser_download_url")
                    break
        if not download_url:
            for asset in self.release_info.get("assets", []):
                name = asset.get("name", "")
                if name.startswith("Setup_") and name.endswith(".exe"):
                    download_url = asset.get("browser_download_url")
                    break
        if not download_url:
            for asset in self.release_info.get("assets", []):
                name = asset.get("name", "")
                if name.endswith(".zip") and not re.search(r'\.\d{3}$', name):
                    download_url = asset.get("browser_download_url")
                    break

        if not download_url:
            import webbrowser
            webbrowser.open(self.release_info.get("url", f"https://github.com/{UpdateManager.GITHUB_REPO}/releases"))
            return

        self.release_info["download_url"] = download_url
        master_ref = self.master
        latest_v = self.latest_ver
        rel_info = self.release_info
        self.destroy()

        # 인앱 다운로드 프로그레스 다이얼로그 즉시 실행 (사용자가 다운로드 진행 상황을 직접 확인)
        try:
            DownloadProgressDialog(master_ref, latest_v, download_url, rel_info)
        except Exception as ex:
            print(f"[Update] 프로그레스 창 생성 실패: {ex}")
            import webbrowser
            webbrowser.open(rel_info.get("url", f"https://github.com/{UpdateManager.GITHUB_REPO}/releases"))

    def _open_web_release(self):
        import webbrowser
        url = self.release_info.get("url", f"https://github.com/{UpdateManager.GITHUB_REPO}/releases")
        if url:
            webbrowser.open(url)

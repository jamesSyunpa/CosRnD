"""
CosRnD Launcher Main Entry Point

This is the main launcher application that handles:
- First-time installation
- Application updates
- Process management
"""

import sys
import logging
from pathlib import Path
import os

# PyInstaller 번들 및 로컬 환경 sys.path 안전 등록
base_dir = Path(getattr(sys, '_MEIPASS', os.path.dirname(os.path.abspath(__file__))))
if str(base_dir) not in sys.path:
    sys.path.insert(0, str(base_dir))

def is_admin() -> bool:
    """Windows 관리자 권한(UAC) 보유 여부 확인"""
    if not sys.platform.startswith('win'):
        return True
    try:
        import ctypes
        return ctypes.windll.shell32.IsUserAnAdmin() != 0
    except Exception:
        return False


def ensure_admin_elevation():
    """
    인스톨러/런처 실행 즉시 Windows UAC(관리자 권한) 승인 창을 띄워
    사용자가 직접 승인하고 시스템에 안전하게 설치/등록되도록 합니다.
    """
    if sys.platform.startswith('win') and getattr(sys, 'frozen', False):
        if not is_admin():
            try:
                import ctypes
                params = " ".join([f'"{arg}"' for arg in sys.argv[1:]])
                ret = ctypes.windll.shell32.ShellExecuteW(
                    None, "runas", sys.executable, params, None, 1
                )
                if int(ret) > 32:
                    sys.exit(0)
            except Exception as e:
                print(f"[UAC] 관리자 승격 요청 실패: {e}")


def register_defender_exclusion(target_paths=None):
    """
    Windows Defender의 '제어된 폴더 액세스(보호된 폴더)' 허용 앱 목록에
    CosRQD 실행 파일들을 공식 등록합니다.
    """
    if not sys.platform.startswith('win'):
        return
    try:
        import subprocess
        if not target_paths:
            target_paths = [
                r"C:\CosRQD\bin\CosRQD.exe",
                r"C:\CosRQD\bin\CosRnD.exe",
                r"C:\CosRQD\bin\main.exe",
                os.path.join(os.environ.get("LOCALAPPDATA", ""), "CosRQD", "bin", "CosRQD.exe")
            ]
        for p in target_paths:
            if p:
                ps_cmd = f"Add-MpPreference -ControlledFolderAccessAllowedApplications '{p}' -ErrorAction SilentlyContinue"
                subprocess.run(["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-Command", ps_cmd], capture_output=True)
        print("[보안] Windows Defender 보호 폴더 액세스 허용 앱 등록 완료")
    except Exception as e:
        print(f"[보안] Defender 예외 등록 실패: {e}")


def unblock_self():
    """
    최초 실행 시 인터넷에서 다운로드되어 발생하는 Windows 스마트스크린 차단(MotW)을
    프로그램 내부에서 스스로 감지하여 자동으로 해제(Unblock)합니다.
    """
    if sys.platform.startswith('win'):
        try:
            # 1. 메인 실행 파일 경로 확인
            if getattr(sys, 'frozen', False):
                exe_path = sys.executable
            else:
                exe_path = os.path.abspath(__file__)
            
            # 2. NTFS 대체 데이터 스트림(Zone.Identifier) 경로 확인 및 삭제
            ads_path = f"{exe_path}:Zone.Identifier"
            if os.path.exists(ads_path):
                os.remove(ads_path)
                print(f"[보안] 자가 차단 해제 완료: {exe_path}")
        except Exception as e:
            print(f"[보안] 자가 차단 해제 시도 실패 (권한 등의 원인): {e}")

# 1. 인스톨러 구동 즉시 UAC 관리자 승인 창 호출
ensure_admin_elevation()

# 2. 프로그램 구동 즉시 차단 해제 실행
unblock_self()

# 3. Defender 제어된 폴더 액세스 자동 등록
register_defender_exclusion()

from launcher.config_manager import ConfigManager
from launcher.launcher_gui import run_launcher_gui, run_uninstaller_gui


# Configure logging
LOG_FORMAT = '%(asctime)s - %(name)s - %(levelname)s - %(message)s'


def setup_logging():
    """Configure logging for the launcher (No local file logs, no terminal dumps)"""
    # 윈도우 프로그램 실행 시 불필요한 파일 로그(launcher.log)와 콘솔창 터미널 출력을 생성하지 않도록 NullHandler 사용
    logging.basicConfig(
        level=logging.ERROR,  # 치명적인 크래시 오류만 로깅 허용
        handlers=[
            logging.NullHandler()
        ]
    )



def read_version() -> str:
    """
    Read application version from folder name or VERSION file.
    
    Priority:
    1. Folder name pattern (_vXX)
    2. VERSION file
    3. Default v1.0.0
    
    Returns:
        Version string
    """
    try:
        import re
        import os
        
        # 1순위: 폴더 이름에서 버전 추출 (예: CosRnD_v57 -> v57)
        current_dir = Path(__file__).parent
        folder_name = current_dir.name
        version_match = re.search(r'_v(\d+)', folder_name)
        if version_match:
            return f"v{version_match.group(1)}"
        
        # 2순위: VERSION 파일
        version_file = current_dir / "VERSION"
        if version_file.exists():
            return version_file.read_text(encoding='utf-8').strip()
    except Exception:
        pass
    
    return "v65.0.3"


def main():
    """Main entry point for launcher"""
    # 윈도우 작업표시줄 아이콘 정합성을 위한 AppUserModelID 설정
    try:
        import ctypes
        myappid = 'Luckfortma.CosRQD.Launcher.v65.0.3'
        ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(myappid)
    except Exception as appid_err:
        print(f"[STARTUP] AppUserModelID 설정 실패: {appid_err}")

    setup_logging()
    logger = logging.getLogger(__name__)
    
    logger.info("=" * 60)
    logger.info("CosRQD Launcher Starting")
    logger.info("=" * 60)
    
    try:
        # Read version
        version = read_version()
        logger.info(f"Application version: {version}")
        
        # Initialize configuration manager
        config_manager = ConfigManager()
        
        # Check if uninstall mode is requested
        if any(arg.lower() in ['--uninstall', '/uninstall', '-uninstall', 'uninstall'] for arg in sys.argv[1:]):
            logger.info("Uninstall mode requested via command line argument")
            run_uninstaller_gui(config_manager, version)
            return 0
            
        # Check if this is first run or existing installation
        if config_manager.exists():
            logger.info("Existing installation detected")
            install_path = config_manager.get_install_path()
            logger.info(f"Installation path: {install_path}")
        else:
            logger.info("First run - installation required")
        
        # Run GUI
        run_launcher_gui(config_manager, version)
        
    except Exception as e:
        import traceback
        import webbrowser
        import urllib.parse
        
        err_msg = traceback.format_exc()
        copied = False
        try:
            import pyperclip
            pyperclip.copy(err_msg)
            copied = True
        except Exception:
            try:
                import tkinter as tk
                r = tk.Tk()
                r.withdraw()
                r.clipboard_clear()
                r.clipboard_append(err_msg)
                r.update()
                copied = True
            except Exception:
                pass
                
        import tkinter as tk
        from tkinter import messagebox
        root = tk.Tk()
        root.withdraw()
        
        info_msg = "런처 구동 중 치명적인 오류가 발생했습니다.\n\n"
        if copied:
            info_msg += "오류 정보가 자동으로 [클립보드]에 복사되었습니다.\n"
        info_msg += "이메일 전송 창이 나타나면 본문에 Ctrl+V를 눌러서 붙여넣어 주세요.\n\n"
        info_msg += f"오류 요약: {e}"
        messagebox.showerror("런처 구동 오류", info_msg)
        
        try:
            email_addr = "luckfortma@naver.com"
            subject = urllib.parse.quote("[오류 보고] 화장품 연구소 관리 런처 에러")
            body = urllib.parse.quote("아래 영역에 Ctrl+V를 눌러 에러 로그를 붙여넣어주세요:\n\n\n\n" + err_msg[:500])
            mail_url = f"mailto:{email_addr}?subject={subject}&body={body}"
            webbrowser.open(mail_url)
        except Exception:
            pass
            
        logger.exception(f"Fatal error in launcher: {e}")
        return 1
    
    return 0


if __name__ == "__main__":
    sys.exit(main())

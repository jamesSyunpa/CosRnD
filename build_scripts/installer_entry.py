import sys
import os
import shutil
import tempfile
from pathlib import Path
import traceback

try:
    from tkinter import messagebox, Tk
except Exception:
    Tk = None

# For non-admin installer: install into %LOCALAPPDATA% and create shortcuts via PowerShell
APP_NAME = "화장품연구관리"

def is_admin():
    try:
        import ctypes
        return ctypes.windll.shell32.IsUserAnAdmin() != 0
    except Exception:
        return False

def show_msg(title, msg):
    try:
        if Tk:
            root = Tk()
            root.withdraw()
            messagebox.showinfo(title, msg)
            root.destroy()
        else:
            print(title, msg)
    except Exception:
        print(title, msg)


def copy_embedded_app(dest_dir):
    # 내부 번들 위치 (PyInstaller onefile: sys._MEIPASS)
    base = getattr(sys, '_MEIPASS', os.path.abspath('.'))
    app_source = os.path.join(base, 'app')
    # 또는 app.zip 같은 단일 번들
    app_zip = os.path.join(base, 'app.zip')

    if os.path.isdir(app_source):
        print('Found embedded app folder, copying...')
        if os.path.exists(dest_dir):
            shutil.rmtree(dest_dir)
        shutil.copytree(app_source, dest_dir)
        return True
    elif os.path.isfile(app_zip):
        print('Found embedded app.zip, extracting...')
        import zipfile
        if os.path.exists(dest_dir):
            shutil.rmtree(dest_dir)
        os.makedirs(dest_dir, exist_ok=True)
        with zipfile.ZipFile(app_zip, 'r') as z:
            z.extractall(dest_dir)
        return True
    else:
        print('No embedded app found in bundle')
        return False


def create_shortcut(target_path, name):
    try:
        # Use PowerShell COM to create a .lnk shortcut (works without pywin32)
        desktop = os.path.join(os.path.join(os.environ['USERPROFILE']), 'Desktop')
        lnk = os.path.join(desktop, f"{name}.lnk")
        ps_cmd = (
            "$s=(New-Object -COM WScript.Shell).CreateShortcut('" + lnk.replace("'","''") + "');"
            "$s.TargetPath='" + target_path.replace("'","''") + "';"
            "$s.WorkingDirectory='" + os.path.dirname(target_path).replace("'","''") + "';"
            "$s.Save();"
        )
        import subprocess
        subprocess.run(["powershell", "-NoProfile", "-Command", ps_cmd], check=True)
        print('Created shortcut via PowerShell:', lnk)
        return True
    except Exception as e:
        print('Failed to create shortcut via PowerShell:', e)
        return False


def main():
    try:
        # 설치 대상 디렉터리
        program_files = os.environ.get('ProgramFiles', r'C:\Program Files')
        dest = os.path.join(program_files, APP_NAME)

        if not is_admin():
            show_msg('권한 필요', '관리자 권한이 필요합니다. 설치를 관리자 권한으로 실행하세요.')
            return 1

        ok = copy_embedded_app(dest)
        if not ok:
            show_msg('설치 실패', '설치할 파일을 찾을 수 없습니다.')
            return 2

        # 실행 파일 찾기
        exe_path = None
        for root, dirs, files in os.walk(dest):
            for f in files:
                if f.lower().endswith('.exe'):
                    exe_path = os.path.join(root, f)
                    break
            if exe_path:
                break

        if exe_path:
            create_shortcut(exe_path, APP_NAME)
            show_msg('설치 완료', f'{APP_NAME}이(가) {dest}에 설치되었습니다.')
            # 바로 실행
            try:
                os.startfile(exe_path)
            except Exception:
                pass
            return 0
        else:
            show_msg('설치 경고', '실행할 .exe 파일을 찾지 못했습니다만 파일은 복사되었습니다.')
            return 0
    except Exception as e:
        traceback.print_exc()
        show_msg('오류', str(e))
        return 3

if __name__ == '__main__':
    sys.exit(main())

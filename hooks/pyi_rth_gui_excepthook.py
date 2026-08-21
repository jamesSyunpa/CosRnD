# Runtime hook to show GUI error dialog instead of console traceback
# Runs early in a frozen app to install a global sys.excepthook

import sys
import os
import traceback
from datetime import datetime


def _show_error_dialog(title: str, message: str) -> bool:
    """Try to show a GUI error dialog. Prefer Tk messagebox; fallback to Win32 MessageBox."""
    # 1) Tkinter messagebox
    try:
        import tkinter as tk
        from tkinter import messagebox
        root = tk.Tk()
        root.withdraw()
        try:
            messagebox.showerror(title, message)
        finally:
            try:
                root.destroy()
            except Exception:
                pass
        return True
    except Exception:
        pass

    # 2) Win32 MessageBoxW (no Tk available)
    try:
        import ctypes
        MB_OK = 0x0
        MB_ICONERROR = 0x10
        ctypes.windll.user32.MessageBoxW(0, message, title, MB_OK | MB_ICONERROR)
        return True
    except Exception:
        return False


essential_app_name = 'RnD_플랫폼'

def _log_error(text: str) -> str | None:
    """Write traceback to a log file under LOCALAPPDATA, return path or None."""
    try:
        base_dir = os.getenv('LOCALAPPDATA') or os.path.expanduser('~')
        log_dir = os.path.join(base_dir, essential_app_name, 'logs')
        os.makedirs(log_dir, exist_ok=True)
        fname = f"error_{datetime.now().strftime('%Y%m%d_%H%M%S')}.log"
        path = os.path.join(log_dir, fname)
        with open(path, 'w', encoding='utf-8') as f:
            f.write(text)
        return path
    except Exception:
        return None


def _format_friendly_message(log_path: str | None) -> str:
    msg = (
        "프로그램 실행 중 예기치 않은 오류가 발생했습니다.\n"
        "작업이 중단되었으며, 프로그램을 다시 시작해 주세요."
    )
    if log_path:
        msg += f"\n\n오류 로그 위치:\n{log_path}"
    return msg


def _excepthook(exctype, value, tb):
    try:
        tb_text = ''.join(traceback.format_exception(exctype, value, tb))
        log_path = _log_error(tb_text)
        message = _format_friendly_message(log_path)
        _show_error_dialog('오류', message)
    except Exception:
        # As a last resort, try bare minimum MessageBox
        try:
            import ctypes
            ctypes.windll.user32.MessageBoxW(0, '치명적 오류가 발생했습니다. 프로그램을 종료합니다.', '오류', 0x10)
        except Exception:
            pass
    finally:
        # Ensure immediate termination to avoid undefined state
        os._exit(1)


# Install global excepthook early
sys.excepthook = _excepthook

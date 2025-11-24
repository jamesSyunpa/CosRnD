# PyInstaller runtime hook for Tkinter/Tcl/Tk
# 이 파일은 PyInstaller 실행 시점에 Tcl/Tk 환경을 설정합니다.

import sys
import os

def setup_tcl_tk():
    """Tcl/Tk 환경 변수를 설정합니다."""
    
    if hasattr(sys, '_MEIPASS'):
        meipass = sys._MEIPASS
        
        # Tcl/Tk 라이브러리 경로 설정
        tcl_data = os.path.join(meipass, '_tcl_data')
        tk_data = os.path.join(meipass, '_tk_data')
        
        # TCL_LIBRARY와 TK_LIBRARY 환경 변수 설정
        if os.path.exists(tcl_data):
            # tcl8.6 폴더 찾기
            tcl86_path = None
            for item in os.listdir(tcl_data):
                if item.startswith('tcl8'):
                    tcl86_path = os.path.join(tcl_data, item)
                    break
            
            if tcl86_path and os.path.exists(tcl86_path):
                os.environ['TCL_LIBRARY'] = tcl86_path
                print(f"[RUNTIME-HOOK-TK] TCL_LIBRARY 설정: {tcl86_path}")
            else:
                os.environ['TCL_LIBRARY'] = tcl_data
                print(f"[RUNTIME-HOOK-TK] TCL_LIBRARY 설정 (루트): {tcl_data}")
        
        if os.path.exists(tk_data):
            # tk8.6 폴더 찾기
            tk86_path = None
            for item in os.listdir(tk_data):
                if item.startswith('tk8'):
                    tk86_path = os.path.join(tk_data, item)
                    break
            
            if tk86_path and os.path.exists(tk86_path):
                os.environ['TK_LIBRARY'] = tk86_path
                print(f"[RUNTIME-HOOK-TK] TK_LIBRARY 설정: {tk86_path}")
            else:
                os.environ['TK_LIBRARY'] = tk_data
                print(f"[RUNTIME-HOOK-TK] TK_LIBRARY 설정 (루트): {tk_data}")
        
        # DLL 경로를 PATH에 추가
        dll_paths = [
            meipass,
            os.path.join(meipass, 'DLLs'),
            os.path.join(meipass, 'Library', 'bin'),
        ]
        
        for dll_path in dll_paths:
            if os.path.exists(dll_path):
                current_path = os.environ.get('PATH', '')
                if dll_path not in current_path:
                    os.environ['PATH'] = dll_path + os.pathsep + current_path
                    print(f"[RUNTIME-HOOK-TK] PATH에 추가: {dll_path}")
        
        # 디버깅: 실제로 존재하는 파일 확인
        try:
            if os.path.exists(tcl_data):
                tcl_contents = os.listdir(tcl_data)
                print(f"[RUNTIME-HOOK-TK] _tcl_data 내용: {tcl_contents[:5]}")
            
            if os.path.exists(tk_data):
                tk_contents = os.listdir(tk_data)
                print(f"[RUNTIME-HOOK-TK] _tk_data 내용: {tk_contents[:5]}")
        except Exception as e:
            print(f"[RUNTIME-HOOK-TK] 디렉토리 확인 오류: {e}")
    
    try:
        # tkinter 모듈 로드 테스트
        import tkinter
        print("[RUNTIME-HOOK-TK] tkinter 모듈 로드 성공")
        return True
    except Exception as e:
        print(f"[RUNTIME-HOOK-TK] tkinter 로드 실패: {e}")
        print(f"[RUNTIME-HOOK-TK] TCL_LIBRARY: {os.environ.get('TCL_LIBRARY', 'NOT SET')}")
        print(f"[RUNTIME-HOOK-TK] TK_LIBRARY: {os.environ.get('TK_LIBRARY', 'NOT SET')}")
        return False

# Hook 실행
if __name__ == "__main__":
    setup_tcl_tk()
else:
    setup_tcl_tk()

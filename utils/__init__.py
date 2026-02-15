# -*- coding: utf-8 -*-
import sys
import os

def center_window_on_mouse_display(win, width: int | None = None, height: int | None = None, use_work_area: bool = True):
    """
    현재 마우스가 위치한 모니터의 정중앙에 주어진 창(win)을 배치합니다.
    (사용자 요청: 다중 모니터 이동 시 크기 재설정으로 인한 딜레이 제거 -> 단순화된 로직 적용)
    """
    try:
        win.update_idletasks()

        # 창 크기 결정 (명시가 없으면 현재 실제/요청 크기를 사용)
        w = int(width) if width else int(max(win.winfo_width(), win.winfo_reqwidth()))
        h = int(height) if height else int(max(win.winfo_height(), win.winfo_reqheight()))
        if w <= 1: w = 800
        if h <= 1: h = 600

        # 복잡한 모니터 감지 로직 대신, 단순히 현재 화면 기준으로 중앙 배치 시도
        # (Tkinter가 OS 창 관리자에게 맡기도록 유도하거나 단순 중앙 배치)
        try:
            # 1. 단순히 화면 중앙 계산 (기본 모니터 기준일 수 있음)
            sw = win.winfo_screenwidth()
            sh = win.winfo_screenheight()
            x = max(0, (sw // 2) - (w // 2))
            y = max(0, (sh // 2) - (h // 2))
            
            # 2. 지오메트리 설정 (크기 고정, 위치만 지정)
            win.geometry(f"{w}x{h}+{x}+{y}")
            return (x, y)
            
        except Exception:
             # 실패 시 아무것도 하지 않음 (OS 기본 배치 따름)
             pass

    except Exception:
        pass
    return (0, 0)

# ==================== PyInstaller 경로 처리 ====================
def resource_path(relative_path):
    """ Get absolute path to resource, works for dev and for PyInstaller """
    try:
        # PyInstaller creates a temp folder and stores path in _MEIPASS
        base_path = sys._MEIPASS
        # 임시 폴더 접근 가능 여부 확인
        if not os.path.exists(base_path) or not os.access(base_path, os.R_OK):
            raise Exception(f"_MEIPASS 경로 접근 불가: {base_path}")
        # print(f"[RESOURCE] Using _MEIPASS: {base_path}") # 너무 빈번해서 주석 처리 가능
    except Exception as e:
        base_path = os.path.dirname(os.path.dirname(os.path.abspath(__file__))) # utils 상위가 프로젝트 루트
        # print(f"[RESOURCE] _MEIPASS 사용 불가 ({e}), 프로젝트 루트 사용: {base_path}")
    
    # 아이콘 파일 특별 처리 (더 포괄적)
    if relative_path.lower() in ['icon.ico', 'Icon.ico', 'app.ico', 'application.ico']:
        icon_variants = [
            'Icon.ico',           # 대문자 I
            'icon.ico',           # 소문자 i
            'ICON.ICO',           # 모두 대문자
            'Icon.ICO',           # 혼합
            'app.ico',            # 앱 아이콘
            'application.ico',    # 어플리케이션 아이콘
            'main.ico',           # 메인 아이콘
        ]
        
        # 기본 경로에서 검색
        for variant in icon_variants:
            icon_path = os.path.join(base_path, variant)
            if os.path.exists(icon_path):
                # print(f"[RESOURCE] Found icon at: {icon_path}")
                return icon_path
        
        # data 폴더에서 검색
        data_path = os.path.join(base_path, 'data')
        if os.path.exists(data_path):
            for variant in icon_variants:
                icon_path = os.path.join(data_path, variant)
                if os.path.exists(icon_path):
                    # print(f"[RESOURCE] Found icon in data folder: {icon_path}")
                    return icon_path
        
        # assets 폴더에서 검색
        assets_path = os.path.join(base_path, 'assets')
        if os.path.exists(assets_path):
            for variant in icon_variants:
                icon_path = os.path.join(assets_path, variant)
                if os.path.exists(icon_path):
                    # print(f"[RESOURCE] Found icon in assets folder: {icon_path}")
                    return icon_path
        
        # 아이콘을 찾지 못한 경우 디렉토리 내용 출력 (더 상세히)
        # try:
        #     base_files = [f for f in os.listdir(base_path) if f.lower().endswith(('.ico', '.png', '.jpg', '.jpeg'))]
        #     print(f"[RESOURCE] Available image files in {base_path}: {base_files}")
            
        #     # 하위 폴더들도 검사
        #     for subdir in ['data', 'assets', 'icons', 'images']:
        #         subdir_path = os.path.join(base_path, subdir)
        #         if os.path.exists(subdir_path):
        #             sub_files = [f for f in os.listdir(subdir_path) if f.lower().endswith(('.ico', '.png', '.jpg', '.jpeg'))]
        #             if sub_files:
        #                 print(f"[RESOURCE] Available image files in {subdir_path}: {sub_files}")
        # except Exception as e:
        #     print(f"[RESOURCE] Cannot list directory: {e}")
        
        # 기본 아이콘이 없는 경우 대체 아이콘 생성 (임시 해결책)
        print("[RESOURCE] Creating fallback icon path")
        return create_fallback_icon(base_path)
    
    # 일반 파일 처리
    possible_paths = [
        os.path.join(base_path, relative_path),  # 기본 경로
        os.path.join(base_path, 'data', relative_path),  # data 폴더
        os.path.join(base_path, 'assets', relative_path),  # assets 폴더
        os.path.join(base_path, relative_path.capitalize()),  # 첫 글자 대문자
        os.path.join(base_path, relative_path.upper()),  # 모두 대문자
        os.path.join(base_path, relative_path.lower()),  # 모두 소문자
    ]
    
    for path in possible_paths:
        if os.path.exists(path):
            # print(f"[RESOURCE] Found resource at: {path}")
            return path
    
    print(f"[RESOURCE] Resource not found: {relative_path}")
    print(f"[RESOURCE] Tried paths: {possible_paths}")
    return possible_paths[0]  # 기본 경로 반환

def create_fallback_icon(base_path):
    """아이콘 파일이 없는 경우 임시 아이콘을 생성합니다"""
    try:
        from PIL import Image, ImageDraw, ImageFont
        import os
        
        # base_path 내 data/temp 폴더 사용 (AppData 사용 금지)
        temp_dir = os.path.join(base_path, 'data', 'temp')
        os.makedirs(temp_dir, exist_ok=True)
        temp_icon_path = os.path.join(temp_dir, 'rnd_platform_temp_icon.ico')
        print(f"[RESOURCE] 프로젝트 폴더 사용: {temp_dir}")
        
        # 간단한 임시 아이콘 생성
        size = (64, 64)
        image = Image.new('RGBA', size, (70, 130, 180, 255))  # Steel Blue
        draw = ImageDraw.Draw(image)
        
        # 간단한 'R' 문자 그리기 (R&D를 의미)
        # 폰트 로드 시도 (없으면 기본값)
        try:
             # 윈도우 기본 폰트 시도
            font = ImageFont.truetype("arial.ttf", 40)
        except:
             font = None
             
        draw.text((20, 10), "R", fill=(255, 255, 255, 255), font=font)
        
        # 임시 파일로 저장
        image.save(temp_icon_path, format='ICO')
        
        print(f"[RESOURCE] Created fallback icon: {temp_icon_path}")
        return temp_icon_path
        
    except Exception as e:
        print(f"[RESOURCE] Failed to create fallback icon: {e}")
        # 최후의 수단: None 반환하여 기본 아이콘 사용
        return None


def safe_focus(widget):
    """Safely set focus to a widget if it still exists.

    Intended for use where callbacks may run after a widget is destroyed.
    """
    try:
        if widget and getattr(widget, 'winfo_exists', lambda: False)():
            try:
                widget.focus_set()
            except Exception:
                try:
                    # best-effort fallback to focus_force
                    widget.focus_force()
                except Exception:
                    pass
    except Exception:
        pass

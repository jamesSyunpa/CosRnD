import sys

def center_window_on_mouse_display(win, width: int | None = None, height: int | None = None, use_work_area: bool = True):
	"""
	현재 마우스가 위치한 모니터의 정중앙에 주어진 창(win)을 배치합니다.
	- Windows에서는 Win32 API(ctypes)로 정확한 모니터 영역을 가져옵니다.
	- 다른 OS이거나 실패 시 Tk의 화면 크기 정보로 폴백합니다.
	"""
	try:
		win.update_idletasks()

		# 창 크기 결정 (명시가 없으면 현재 실제/요청 크기를 사용)
		w = int(width) if width else int(max(win.winfo_width(), win.winfo_reqwidth()))
		h = int(height) if height else int(max(win.winfo_height(), win.winfo_reqheight()))
		if w <= 1: w = 800
		if h <= 1: h = 600

		if sys.platform.startswith('win'):
			import ctypes
			from ctypes import wintypes

			user32 = ctypes.windll.user32

			class POINT(ctypes.Structure):
				_fields_ = [("x", ctypes.c_long), ("y", ctypes.c_long)]

			class RECT(ctypes.Structure):
				_fields_ = [("left", ctypes.c_long), ("top", ctypes.c_long), ("right", ctypes.c_long), ("bottom", ctypes.c_long)]

			class MONITORINFO(ctypes.Structure):
				_fields_ = [("cbSize", ctypes.c_ulong), ("rcMonitor", RECT), ("rcWork", RECT), ("dwFlags", ctypes.c_ulong)]

			# 커서 위치 얻기
			pt = POINT()
			if not user32.GetCursorPos(ctypes.byref(pt)):
				raise RuntimeError("GetCursorPos failed")

			# 포인터가 위치한 모니터 핸들 얻기
			MONITOR_DEFAULTTONEAREST = 2
			hmon = user32.MonitorFromPoint(pt, MONITOR_DEFAULTTONEAREST)
			if not hmon:
				raise RuntimeError("MonitorFromPoint failed")

			# 모니터 정보 가져오기
			mi = MONITORINFO()
			mi.cbSize = ctypes.sizeof(MONITORINFO)
			if not user32.GetMonitorInfoW(hmon, ctypes.byref(mi)):
				raise RuntimeError("GetMonitorInfoW failed")

			rect = mi.rcWork if use_work_area else mi.rcMonitor
			mon_w = rect.right - rect.left
			mon_h = rect.bottom - rect.top

			x = rect.left + max(0, (mon_w - w) // 2)
			y = rect.top + max(0, (mon_h - h) // 2)

			win.geometry(f"{w}x{h}+{x}+{y}")
			return (x, y)
		else:
			# 폴백: Tk의 화면 크기 기반 (단일 모니터 기준)
			sw = win.winfo_screenwidth()
			sh = win.winfo_screenheight()
			x = max(0, (sw // 2) - (w // 2))
			y = max(0, (sh // 2) - (h // 2))
			win.geometry(f"{w}x{h}+{x}+{y}")
			return (x, y)
	except Exception:
		# 최후 폴백: 위치 지정 실패 시 기본 위치 유지
		try:
			sw = win.winfo_screenwidth()
			sh = win.winfo_screenheight()
			w = int(width) if width else int(max(win.winfo_width(), win.winfo_reqwidth(), 800))
			h = int(height) if height else int(max(win.winfo_height(), win.winfo_reqheight(), 600))
			x = max(0, (sw // 2) - (w // 2))
			y = max(0, (sh // 2) - (h // 2))
			win.geometry(f"{w}x{h}+{x}+{y}")
		except Exception:
			pass

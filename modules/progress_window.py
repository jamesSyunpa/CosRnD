import customtkinter as ctk
from tkinter import ttk
import time

class ProgressWindow(ctk.CTkToplevel):
    def __init__(self, parent, title="로딩 중...", icon_path=None):
        super().__init__(parent)
        
        # 윈도우 설정
        self.title(title)
        if icon_path:
            self.iconbitmap(icon_path)
        
        # 윈도우 크기와 위치 설정
        window_width = 300
        window_height = 100
        screen_width = self.winfo_screenwidth()
        screen_height = self.winfo_screenheight()
        x = (screen_width - window_width) // 2
        y = (screen_height - window_height) // 2
        self.geometry(f"{window_width}x{window_height}+{x}+{y}")
        
        # 진행 상태 레이블
        self.status_label = ctk.CTkLabel(self, text="시스템 초기화 중...")
        self.status_label.pack(pady=10)
        
        # 프로그레스바
        self.progress_bar = ttk.Progressbar(self, length=250, mode='determinate')
        self.progress_bar.pack(pady=10)
        
        # 항상 위에 표시
        self.lift()
        self.attributes('-topmost', True)
        
        # 창 닫기 버튼 비활성화
        self.protocol("WM_DELETE_WINDOW", lambda: None)
        
        self._animation_job = None
        
        # UI 업데이트
        self.update()
    
    def update_progress(self, value, text=None):
        """프로그레스바 값과 텍스트 업데이트 (수동)"""
        if self._animation_job: # 애니메이션 중이면 수동 업데이트 중지
            return
        if text:
            self.status_label.configure(text=text)
        self.progress_bar['value'] = value
        self.update()

    def start_animation(self, duration_ms=1500):
        """설정된 시간 동안 부드러운 로딩 애니메이션을 시작합니다."""
        self.progress_bar['value'] = 0
        self.status_label.configure(text="시스템을 불러오는 중입니다...")
        self.start_time = time.time()
        self.duration_sec = duration_ms / 1000.0
        
        if self._animation_job:
            self.after_cancel(self._animation_job)
            
        self._animate()

    def _animate(self):
        """애니메이션의 각 프레임을 처리합니다."""
        elapsed = time.time() - self.start_time
        progress = min(100, int((elapsed / self.duration_sec) * 100))
        self.progress_bar['value'] = progress
        
        if progress < 100:
            self._animation_job = self.after(20, self._animate) # 약 50 FPS
        else:
            self.status_label.configure(text="거의 다 됐습니다...")
            self._animation_job = None

    def finish(self):
        """프로그레스 윈도우를 즉시 100%로 채우고 닫습니다."""
        if self._animation_job:
            self.after_cancel(self._animation_job)
            self._animation_job = None
        
        self.progress_bar['value'] = 100
        self.status_label.configure(text="완료!")
        self.update()
        self.after(100, self.destroy) # 잠시 보여준 후 파괴
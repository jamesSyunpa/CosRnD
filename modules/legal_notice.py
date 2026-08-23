# -*- coding: utf-8 -*-
import customtkinter as ctk
from tkinter import messagebox
import os
import sys

class LegalNoticeDialog(ctk.CTkToplevel):
    def __init__(self, parent, version_str, on_agree, config_path, already_agreed=False):
        super().__init__(parent)
        self.withdraw()  # 초기 드로잉 깜빡임 및 크기 드드득 현상 제거
        self.title("일반사항 및 법적고지")
        
        # 1. 렌더링 전 모니터 해상도를 감지하여 크기와 정확한 중앙 배치 좌표를 geometry로 즉시 고정
        self.resizable(False, False)
        self.parent = parent
        self.on_agree_callback = on_agree
        self.version_str = version_str or "v64"
        self.config_path = config_path
        self.already_agreed = already_agreed
        
        try:
            screen_width = self.winfo_screenwidth()
            screen_height = self.winfo_screenheight()
            x = int((screen_width - 800) / 2)
            y = int((screen_height - 600) / 2)
            self.geometry(f"800x600+{x}+{y}")
        except Exception:
            self.geometry("800x600+100+100")

        self.attributes("-topmost", True)
        self.protocol("WM_DELETE_WINDOW", self.on_close)
        
        # Main Frame
        self.main_frame = ctk.CTkFrame(self)
        self.main_frame.pack(fill="both", expand=True, padx=20, pady=20)

        # Title
        self.title_label = ctk.CTkLabel(self.main_frame, text="일반사항 및 법적고지", font=ctk.CTkFont(size=20, weight="bold"))
        self.title_label.pack(pady=(0, 20))

        # Text Content (Textbox for better wrapping)
        self.textbox = ctk.CTkTextbox(self.main_frame, wrap="word", font=ctk.CTkFont(size=12))
        self.textbox.pack(fill="both", expand=True, pady=10)
        
        self.text_content = f"""[실무요약] 본 프로그램의 모든 저작권 및 독점 배포권은 럭포마(luckfortma)에게 있으며, 화장품 연구소의 내부 연구 및 관리 효율 향상을 위한 공식 정식 솔루션입니다.

0.1 프로그램 개요
    0.1.1 프로그램 명칭
        국문: 화장품 연구소 관리 시스템 (CosRQD)
        영문: Cosmetic Research & Quality Data System (CosRQD)
    0.1.2 개발 및 배포권자
        원저작권자: luckfortma (럭포마)
        공식 배포 채널: luckfortma 공식 깃허브 및 공식 네이버 카페 (https://cafe.naver.com/cosrqd)
        비즈니스 문의: luckfortma@gmail.com
    0.1.3 개발 목적
        본 프로그램은 화장품 연구소의 연구 데이터 관리, 성분 정보 관리, 처방 설계, 시험 및 품질 관리 이력을 효율적으로 수행하기 위해 개발된 연구 통합 소프트웨어입니다.

0.2 지식재산권 독점 귀속 및 배포 권한 제한 (중요)
    0.2.1 저작권 및 배포권 독점 고지
        - 본 프로그램의 소스코드, 데이터 구조, 화면 설계(UI), 알고리즘, 기능 로직 및 모든 브랜드 권리는 오직 원저작권자 'luckfortma(럭포마)'에게 단독 귀속됩니다.
        - 오직 'luckfortma(럭포마)'만이 본 프로그램을 제작, 빌드, 수정, 배포하고 라이선스를 부여할 수 있습니다.
    0.2.2 무단 변형 및 2차 배포 금지
        - 원저작권자의 사전 서면 동의 없이 제3자(개인, 기업, 단체 등)가 본 프로그램을 무단 복제, 디컴파일(Reverse Engineering), 수정, 변형하거나 제3자 명의로 재배포/판매하는 행위를 엄격히 금지합니다.
        - 본 프로그램의 지식재산권을 침해하는 행위는 대한민국 저작권법 제136조에 따라 민·형사상의 강력한 법적 처벌 및 손해배상 청구의 대상이 됩니다.

0.3 책임 범위 및 면책 조항 (Disclaimer)
    0.3.1 면책 조항
        본 프로그램은 연구 및 내부 관리 편의를 위해 제공되는 전문 도구입니다. 프로그램 내에서 계산되는 수치 결과(배합비, 단가, 규격 등)는 참고용 자료이며, 최종 제품의 품질, 안전성, 법적 규제 적합성은 사용자가 관련 법령(INCI, 식약처 고시 등)에 따라 최종 검증하여 판단해야 합니다.
    0.3.2 데이터 입력 및 관리 책임
        프로그램에 입력되는 모든 데이터(성분명, 배합비, 수치 등)의 정확성 및 데이터베이스 백업 관리에 대한 책임은 사용자에게 있습니다.

0.4 사용자 동의 및 고지
    - 본 프로그램은 사용자가 상기 저작권 규정 및 이용 약관을 완전히 숙지하고 동의한 경우에 한하여 공식적으로 사용할 수 있습니다.

0.5 저작권 정보
    Copyright © 2025-2026 luckfortma. All rights reserved.
    개발 및 공식 배포: luckfortma (럭포마)
    프로그램 버전: {self.version_str} (공식 정식 배포판)

0.6 오픈소스 사용 고지
    본 프로그램은 오픈소스 라이브러리(Python, CustomTkinter, pandas, openpyxl, SQLAlchemy, SQLite3 등)를 활용하여 빌드되었으며, 각 구성요소의 라이선스 정책을 준수합니다.
"""
        self.textbox.insert("0.0", self.text_content)
        self.textbox.configure(state="disabled") # 읽기 전용으로 설정

        # Checkbox Frame
        self.checkbox_val = ctk.BooleanVar(value=already_agreed)
        self.checkbox = ctk.CTkCheckBox(self.main_frame, text="위 내용을 확인하였으며, 이에 동의합니다.", variable=self.checkbox_val)
        self.checkbox.pack(pady=(20, 10))
        
        if already_agreed:
            self.checkbox.configure(state="disabled")

        # Buttons
        self.button_frame = ctk.CTkFrame(self.main_frame, fg_color="transparent")
        self.button_frame.pack(fill="x", pady=10)

        btn_text = "확인 (닫기)" if already_agreed else "동의 및 시작"
        self.agree_btn = ctk.CTkButton(self.button_frame, text=btn_text, command=self.on_agree_click, width=200, height=40, font=ctk.CTkFont(weight="bold"))
        self.agree_btn.pack(pady=5)
        
        self.agree_btn.pack(pady=5)
        
        # Win32 안정성을 위해 약간의 지연 후 포커스/그랩 설정
        try:
            self._focus_after_id = self.after(100, self._set_focus_and_grab)
        except Exception:
            self._focus_after_id = None

        # Install instance-level safe wrappers for focus/grab methods so
        # external scheduled callbacks calling widget.focus_set()/focus_force()
        # won't raise if the widget was destroyed.
        try:
            self._destroyed = False
            self._orig_focus_set = getattr(self, 'focus_set', None)
            self._orig_focus_force = getattr(self, 'focus_force', None)
            self._orig_grab_set = getattr(self, 'grab_set', None)

            def _safe_focus_set(*a, **kw):
                try:
                    if getattr(self, 'winfo_exists', lambda: False)():
                        if callable(self._orig_focus_set):
                            return self._orig_focus_set(*a, **kw)
                except Exception:
                    pass
                return None

            def _safe_focus_force(*a, **kw):
                try:
                    if getattr(self, 'winfo_exists', lambda: False)():
                        if callable(self._orig_focus_force):
                            return self._orig_focus_force(*a, **kw)
                except Exception:
                    pass
                return None

            def _safe_grab_set(*a, **kw):
                try:
                    if getattr(self, 'winfo_exists', lambda: False)():
                        if callable(self._orig_grab_set):
                            return self._orig_grab_set(*a, **kw)
                except Exception:
                    pass
                return None

            # Override instance methods
            try:
                self.focus_set = _safe_focus_set
            except Exception:
                pass
            try:
                self.focus_force = _safe_focus_force
            except Exception:
                pass
            try:
                self.grab_set = _safe_grab_set
            except Exception:
                pass
        except Exception:
            pass

        # Ensure we cancel scheduled callbacks if the widget is destroyed
        def _on_destroy(event=None):
            try:
                self._destroyed = True
            except Exception:
                pass
            try:
                if getattr(self, '_focus_after_id', None):
                    try:
                        self.after_cancel(self._focus_after_id)
                    except Exception:
                        pass
            except Exception:
                pass

        try:
            self.bind("<Destroy>", _on_destroy)
        except Exception:
            pass

        self.deiconify()  # 화면 배치 완료 후 표시

    def _set_focus_and_grab(self):
        # Guard against calling focus/grab on a destroyed widget (packaged exe timing differences)
        # Cancel further scheduled focus attempts if widget no longer exists.
        try:
            exists = False
            try:
                exists = bool(self.winfo_exists())
            except Exception:
                exists = False
            if not exists:
                return

            # Attempt to raise and focus the dialog; guard each call.
            try:
                self.lift()
            except Exception:
                pass
            try:
                self.focus_force()
            except Exception:
                pass
            try:
                self.grab_set()
            except Exception:
                pass
        except Exception as e:
            # Any unexpected error should not propagate to the mainloop
            try:
                print(f"Focus/Grab failed (ignored): {e}")
            except Exception:
                pass

    def on_agree_click(self):
        # 이미 동의했으면 그냥 닫기
        if self.already_agreed:
            try:
                if getattr(self, '_focus_after_id', None):
                    try:
                        self.after_cancel(self._focus_after_id)
                    except Exception:
                        pass
            except Exception:
                pass
            self.destroy()
            return

        if self.checkbox_val.get():
            # 기록되지 않았다면 config.ini에 동의 버전을 저장
            try:
                import configparser
                cfg = configparser.ConfigParser()

                # Determine config path: use provided path, else exe dir (if frozen) or project root
                if self.config_path:
                    cfg_path = self.config_path
                else:
                    exe_dir = os.path.dirname(sys.executable) if getattr(sys, 'frozen', False) else os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
                    cfg_path = os.path.join(exe_dir, 'config.ini')

                # Read existing, update Legal/agreed_version
                try:
                    if os.path.exists(cfg_path):
                        cfg.read(cfg_path, encoding='utf-8')
                except Exception:
                    pass

                if 'Legal' not in cfg:
                    cfg['Legal'] = {}
                # Normalize stored version to 'vX' form when possible
                agreed_to = str(self.version_str).strip() if self.version_str else 'agreed'
                if not agreed_to or '?' in agreed_to:
                    agreed_to = 'agreed'
                
                if agreed_to and agreed_to != 'agreed' and not agreed_to.startswith('v'):
                    import re as _re
                    if _re.match(r'^\d+(?:\.\d+)*$', agreed_to):
                        agreed_to = 'v' + agreed_to
                cfg['Legal']['agreed_version'] = agreed_to

                # Write back (create file if missing)
                try:
                    with open(cfg_path, 'w', encoding='utf-8') as f:
                        cfg.write(f)
                    print(f"[LEGAL] Agreed version saved: {cfg_path} -> {self.version_str}")
                except Exception as e:
                    print(f"[LEGAL] Failed to write agreed version to config: {e}")

            except Exception as _e:
                print(f"[LEGAL] Error while saving agreement: {_e}")

            if self.on_agree_callback:
                try:
                    self.on_agree_callback()
                except Exception:
                    pass
            try:
                if getattr(self, '_focus_after_id', None):
                    try:
                        self.after_cancel(self._focus_after_id)
                    except Exception:
                        pass
            except Exception:
                pass
            self.destroy()
        else:
            messagebox.showwarning("동의 필요", "프로그램을 시작하려면 위 내용에 동의(체크)해야 합니다.")

    def on_close(self):
        # 이미 동의했거나 체크된 상태면 그냥 종료
        if self.already_agreed or self.checkbox_val.get():
            try:
                if getattr(self, '_focus_after_id', None):
                    try:
                        self.after_cancel(self._focus_after_id)
                    except Exception:
                        pass
            except Exception:
                pass
            self.destroy()
        else:
            if messagebox.askyesno("종료", "동의하지 않으면 프로그램을 사용할 수 없습니다.\n종료하시겠습니까?"):
                try:
                    if getattr(self, '_focus_after_id', None):
                        try:
                            self.after_cancel(self._focus_after_id)
                        except Exception:
                            pass
                except Exception:
                    pass
                try:
                    self.parent.destroy()
                except Exception:
                    pass
                try:
                    sys.exit(0)
                except SystemExit:
                    raise
                except Exception:
                    pass

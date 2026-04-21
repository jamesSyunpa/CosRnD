# -*- coding: utf-8 -*-
import customtkinter as ctk
from tkinter import messagebox
import os
import sys

class LegalNoticeDialog(ctk.CTkToplevel):
    def __init__(self, parent, version_str, on_agree, config_path, already_agreed=False):
        super().__init__(parent)
        self.title("일반사항 및 법적고지")
        self.geometry("800x600")
        self.resizable(False, False)
        self.parent = parent
        self.on_agree_callback = on_agree
        self.version_str = version_str
        self.config_path = config_path
        self.already_agreed = already_agreed
        
        # Center the window
        try:
            from utils import center_window_on_mouse_display
            center_window_on_mouse_display(self, 800, 600)
        except:
            self.eval('tk::PlaceWindow . center')

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
        
        self.text_content = """[실무요약] 본 프로그램은 화장품 연구소의 내부 연구 및 관리 효율 향상을 위한 도구이며, 최종 품질 판단 및 법적 책임은 전적으로 사용자에게 있습니다.

0.1 프로그램 개요
    0.1.1 프로그램 명칭
        국문: 화장품 연구소 관리 시스템
        영문: Cosmetic Research & Quality Data System (CosRQD)
    0.1.2 개발 목적
        본 프로그램은 화장품 연구소의 연구 데이터 관리, 성분 정보 관리, 시험 및 연구 이력 관리를 효율적으로 수행하기 위해 개발된 내부 연구 지원용 소프트웨어입니다.
        연구 업무의 편의성과 관리 효율 향상을 주목적으로 하며, 최종 제품의 품질 판단이나 법적 적합성 판단을 대체하는 목적이 아님을 명시합니다.

0.2 사용 범위 및 제한 사항
    0.2.1 사용 범위
        본 프로그램은 다음의 목적에 한하여 사용해야 합니다.
        - 화장품 연구 개발(R&D) 데이터의 전산화 및 관리
        - 성분 정보 데이터베이스 구축 및 배합 이력 관리
        - 내부 연구 기록 정리 및 참고용 수치 계산
        - 기타 연구소 내부 관리 업무 지원

    0.2.2 사용 제한
        대외비 (Internal Use Only): 본 프로그램은 외부 배포, 판매, 재가공, 무단 복제를 엄격히 금지합니다.
        법적 효력 부존재: 본 프로그램은 화장품 제조 및 판매 허가에 대한 법적 판단 도구로 사용될 수 없습니다.
        참고용 자료: 프로그램의 모든 출력 결과는 참고 자료(Reference)이며, 최종 판단은 반드시 관련 법규 및 내부 절차(SOP)에 따라 수행되어야 합니다.

0.3 책임 범위 및 면책 조항 (중요)
    !! Warning 주의 (Disclaimer) !!
    3.1 면책 조항
    본 프로그램은 연구 및 내부 관리 편의를 위해 제공됩니다. 본 프로그램을 통해 생성된 계산 결과, 분석 정보, 관리 데이터는 최종 제품의 품질, 안전성, 법적 적합성을 보장하지 않습니다. 본 프로그램의 사용으로 인해 발생하는 모든 유형/무형의 결과에 대한 최종 책임은 사용자에게 있으며, 개발자 및 제공자는 이에 대한 어떠한 법적 책임도 지지 않습니다.

    ** 3.2 데이터 입력 책임 **
    본 프로그램에 입력되는 모든 데이터(성분명, 함량, 배합비, 수치 정보 등)의 정확성에 대한 책임은 사용자에게 있습니다. 사용자의 입력 오류 또는 관리 부주의로 인해 발생한 문제에 대해서는 개발자가 책임을 지지 않습니다.

    ** 3.3 기기 귀속 및 복제 금지 동의 (Node-Locking) **
    본 프로그램은 보안을 위해 최초 실행된 PC의 하드웨어 정보 및 사용자 계정 정보와 결합되어 해당 기기에 귀속(박제)됩니다.
    - 사용자는 프로그램이 설치된 PC 외의 다른 기기로 무단 복제하여 실행할 수 없음에 동의합니다.
    - 무단 복제, 배포, 또는 보안 로직 우회 시도 시 프로그램 실행이 영구적으로 차단될 수 있습니다.
    - 기기 변경이나 포맷 등으로 인해 재설치가 필요한 경우, 관리자에게 문의하여 적절한 절차를 밟아야 합니다.

0.4 사용자 동의 및 고지
    0.4.1 이용 고지
        본 프로그램은 최초 로그인 시 다음 사항에 대한 고지를 제공하며, 사용자는 이에 동의한 후 프로그램을 사용할 수 있습니다.
        - 프로그램의 사용 목적 인지
        - 책임 범위 및 면책 사항 동의
        - 내부 사용 제한 규정 준수
        ※ 사용자의 동의 기록은 시스템에 저장되며, 추후 프로그램 버전 변경 시 재동의를 요구할 수 있습니다.

0.5 저작권 및 지식재산권
    0.5.1 저작권 정보
        Copyright © 2025 luckfortma. All rights reserved.
        본 프로그램의 소스코드, UI 구성, 기능 설계 및 설명 문서는 대한민국 저작권법의 보호를 받습니다.
        사전 승인 없이 본 프로그램의 전부 또는 일부를 복제, 배포, 수정, 재사용하는 행위를 금지합니다.

    0.5.2 개발 정보
        개발자: luckfortma
        이메일: luckfortma@gmail.com
        개발 목적: 화장품 연구소 내부 관리 전용

0.6 버전 및 변경 이력 관리
    0.6.1 버전 정보
        프로그램 버전: v55
        최조 배포일: 2025.12.17
    0.6.2 변경 이력
        본 프로그램은 기능 개선 및 안정성 확보를 위해 지속적으로 업데이트될 수 있습니다. 주요 변경 사항은 본 설명서의 개정본 또는 별도의 Release Note를 통해 관리합니다.

0.7 오픈소스 사용 고지
    본 프로그램은 개발 과정에서 다음의 오픈소스 소프트웨어를 활용하였습니다. 각 라이브러리는 해당 라이선스 정책을 따릅니다.
    Python, PyQt (or Tkinter), pandas, Numpy 등

※ 본 고지 사항의 상세 내용은 제14장 '법적 고지 및 면책 조항'을 따른다.
"""
        self.textbox.insert("0.0", self.text_content)
        self.textbox.configure(state="disabled") # 읽기 전용으로 설정

        # Checkbox Frame
        self.checkbox_val = ctk.BooleanVar(value=already_agreed)
        self.checkbox = ctk.CTkCheckBox(self.main_frame, text="위 내용을 확인하였으며, 이에 동의합니다.", variable=self.checkbox_val)
        self.checkbox.pack(pady=(20, 10))
        
        if already_agreed:
            self.checkbox.select() # 이미 동의한 경우 체크 상태 강제 설정
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
                agreed_to = str(self.version_str).strip() if self.version_str else ''
                if agreed_to and not agreed_to.startswith('v'):
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

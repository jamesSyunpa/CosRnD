# modules/quality_management.py
import customtkinter as ctk
from modules.ui_components import HelpPopup

class QualityManagementFrame(ctk.CTkFrame):
    def __init__(self, master, user, app):
        super().__init__(master)
        self.current_user = user
        self.app = app
        
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(0, weight=1)

        # --- 상단 프레임 (탭 뷰 + 도움말 버튼) ---
        top_frame = ctk.CTkFrame(self, fg_color="transparent")
        top_frame.grid(row=0, column=0, sticky="nsew")
        top_frame.grid_columnconfigure(0, weight=1)
        top_frame.grid_rowconfigure(0, weight=1)

        self.tab_view = ctk.CTkTabview(
            self, command=self.on_tab_change, border_width=1,
            border_color=("gray80", "gray30"),
            segmented_button_selected_color=("#3B8ED0", "#1F6AA5"),
            segmented_button_unselected_color=("gray92", "gray20"),
            text_color=("black", "white"),
            segmented_button_selected_hover_color=("#3671A8", "#144870"),
            segmented_button_unselected_hover_color=("gray85", "gray28")
        )
        self.tab_view.grid(row=0, column=0, sticky="nsew", padx=10, pady=10)

        # 도움말 버튼
        self.help_button = ctk.CTkButton(top_frame, text="도움말", width=80, command=self.show_help)
        self.help_button.place(relx=0.98, y=10, anchor="ne")

        # 기존 document_management.py에 있던 탭들을 이곳으로 이동
        self.tab_view.add("시험/테스트 결과 관리")
        self.tab_view.add("원료/거래처 문서")
        self.tab_view.add("품질/제조 문서")
        self.tab_view.add("규제/인허가 문서")

        self.setup_placeholder_tab(self.tab_view.tab("시험/테스트 결과 관리"), "시험/테스트 결과 관리")
        self.setup_placeholder_tab(self.tab_view.tab("원료/거래처 문서"), "원료/거래처 문서")
        self.setup_placeholder_tab(self.tab_view.tab("품질/제조 문서"), "품질/제조 문서")
        self.setup_placeholder_tab(self.tab_view.tab("규제/인허가 문서"), "규제/인허가 문서")

    def show_help(self):
        HelpPopup(self, "품질 관리 도움말", "품질 관리 관련 기능은 현재 개발 예정입니다.")

    def on_tab_change(self):
        selected_tab = self.tab_view.get()
        self.app.record_action(f"quality/{selected_tab}")

    def setup_placeholder_tab(self, tab_frame, tab_name):
        tab_frame.grid_columnconfigure(0, weight=1)
        tab_frame.grid_rowconfigure(0, weight=1)
        label = ctk.CTkLabel(tab_frame, text=f"{tab_name}\n기능 개발 예정입니다.", font=ctk.CTkFont(size=20, weight="bold"))
        label.grid(row=0, column=0, padx=20, pady=20)
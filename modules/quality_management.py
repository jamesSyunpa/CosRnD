# modules/quality_management.py
import customtkinter as ctk
from modules.ui_components import HelpPopup
from modules.translation import get_texts

class QualityManagementFrame(ctk.CTkFrame):
    def __init__(self, master, user, app, language="korean"):
        super().__init__(master)
        self.current_user = user
        self.app = app
        self.language = language
        self.texts = get_texts(language)
        
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
        self.help_button = ctk.CTkButton(top_frame, text=self.texts['help'], width=80, command=self.show_help)
        self.help_button.place(relx=0.98, y=10, anchor="ne")

        # --- 언어별 텍스트 ---
        texts = {
            "korean": ["COA", "MSDS", "제품표준서", "제조관리기록서"],
            "english": ["COA", "MSDS", "Product Standard", "MFG Record"]
        }
        current_texts = texts[self.language]

        # 하위 탭 추가
        for tab_name in current_texts:
            self.tab_view.add(tab_name)

        # 각 탭의 UI 설정
        self.setup_coa_tab(self.tab_view.tab(current_texts[0]))
        self.setup_msds_tab(self.tab_view.tab(current_texts[1]))
        self.setup_product_standard_tab(self.tab_view.tab(current_texts[2]))
        self.setup_mfg_record_tab(self.tab_view.tab(current_texts[3]))

    def show_help(self):
        """품질 관리 도움말을 표시합니다."""
        title = self.texts['quality_mgt_help_title']
        message = self.texts['quality_mgt_help_message']
        HelpPopup(self, title, message)

    def on_tab_change(self):
        selected_tab = self.tab_view.get()
        self.app.record_action(f"quality/{selected_tab}")

    def setup_coa_tab(self, tab_frame):
        """COA 탭 내부에 '반제품'과 '완제품' 서브 탭을 설정합니다."""
        tab_frame.grid_columnconfigure(0, weight=1)
        tab_frame.grid_rowconfigure(0, weight=1)

        coa_sub_tab_view = ctk.CTkTabview(tab_frame, border_width=1, border_color=("gray80", "gray30"))
        coa_sub_tab_view.grid(row=0, column=0, padx=5, pady=5, sticky="nsew")

        # --- 언어별 텍스트 ---
        texts = {
            "korean": {"semi": "반제품", "final": "완제품"},
            "english": {"semi": "Semi-finished", "final": "Finished Product"}
        }
        current_texts = texts[self.language]

        # 반제품/완제품 탭 추가
        coa_sub_tab_view.add(current_texts["semi"])
        coa_sub_tab_view.add(current_texts["final"])

        self.setup_placeholder_tab(coa_sub_tab_view.tab(current_texts["semi"]), f"COA - {current_texts['semi']} ({self.texts['dev_in_progress_short']})")
        self.setup_placeholder_tab(coa_sub_tab_view.tab(current_texts["final"]), f"COA - {current_texts['final']} ({self.texts['dev_in_progress_short']})")

    def setup_msds_tab(self, tab_frame):
        self.setup_placeholder_tab(tab_frame, f"MSDS ({self.texts['dev_in_progress_short']})")

    def setup_product_standard_tab(self, tab_frame):
        self.setup_placeholder_tab(tab_frame, f"{self.texts['prod_standard']} ({self.texts['dev_in_progress_short']})")

    def setup_mfg_record_tab(self, tab_frame):
        self.setup_placeholder_tab(tab_frame, f"{self.texts['mfg_record']} ({self.texts['dev_in_progress_short']})")

    def setup_placeholder_tab(self, tab_frame, tab_name):
        tab_frame.grid_columnconfigure(0, weight=1)
        tab_frame.grid_rowconfigure(0, weight=1)
        label = ctk.CTkLabel(tab_frame, text=f"{tab_name}\n{self.texts['dev_in_progress']}", font=ctk.CTkFont(size=20, weight="bold"))
        label.grid(row=0, column=0, padx=20, pady=20)
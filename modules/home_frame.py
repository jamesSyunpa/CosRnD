# modules/home_frame.py
import customtkinter as ctk
from modules.ui_components import HelpPopup # HelpPopup 클래스를 ui_components에서 가져옵니다.

class HomeFrame(ctk.CTkFrame):
    def __init__(self, master, user, app, recent_actions, action_config):
        super().__init__(master, fg_color="transparent")
        self.current_user = user
        self.app = app  # 메인 App 인스턴스 저장
        self.recent_actions = recent_actions
        self.action_config = action_config

        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(1, weight=1) # 바로가기 영역이 확장되도록 설정
        
        # --- 상단 프레임 (환영 메시지 + 도움말 버튼) ---
        top_frame = ctk.CTkFrame(self, fg_color="transparent")
        top_frame.grid(row=0, column=0, padx=20, pady=(40, 20), sticky="ew")
        top_frame.grid_columnconfigure(0, weight=1)

        # 환영 메시지
        welcome_text = f"'{self.current_user.username}'님, 환영합니다."
        self.welcome_label = ctk.CTkLabel(top_frame, text=welcome_text, font=ctk.CTkFont(size=24, weight="bold"))
        self.welcome_label.grid(row=0, column=0, sticky="w")

        # 도움말 버튼
        self.help_button = ctk.CTkButton(top_frame, text="도움말", width=80, command=self.show_help)
        self.help_button.grid(row=0, column=1, sticky="e")

        # 바로가기 메뉴 컨테이너
        self.quick_access_frame = ctk.CTkFrame(self, fg_color="transparent")
        self.quick_access_frame.grid(row=1, column=0, padx=50, pady=20, sticky="nsew")
        
        self.refresh_cards()

    def show_help(self):
        """메인 화면 도움말을 표시합니다."""
        title = "메인 화면 도움말"
        message = """
        [메인 화면 사용법]
        
        이 화면은 프로그램의 시작점입니다.
        
        1. 환영 메시지
        - 로그인한 사용자 정보를 환영 메시지로 보여줍니다.
        
        2. 바로가기 카드
        - 최근에 사용한 메뉴 5가지가 카드로 표시됩니다.
        - 카드를 클릭하면 해당 기능 화면으로 바로 이동할 수 있습니다.
        - 최근 활동이 없으면 안내 메시지가 표시됩니다.
        """
        HelpPopup(self, title, message)

    def refresh_cards(self):
        """최근 활동 기록을 바탕으로 바로가기 카드를 다시 그립니다."""
        # 기존에 표시되던 카드 위젯들을 모두 삭제합니다.
        for widget in self.quick_access_frame.winfo_children():
            widget.destroy()

        if not self.recent_actions: # self.recent_actions를 직접 사용하도록 변경
            info_label = ctk.CTkLabel(self.quick_access_frame, text="최근 사용한 메뉴가 없습니다.\n좌측 메뉴를 사용하여 작업을 시작하세요.", font=ctk.CTkFont(size=16))
            info_label.pack(pady=50)
            return

        # 항상 5개의 열을 기준으로 그리드를 구성하여 카드 크기를 고정합니다.
        num_columns = 5
        self.quick_access_frame.grid_columnconfigure(tuple(range(num_columns)), weight=1)

        # 새 카드 생성
        for i, target in enumerate(self.recent_actions): # self.recent_actions를 직접 사용하도록 변경
            config = self.action_config.get(target)
            if not config: continue

            icon = config.get("icon", "❓") # 아이콘
            title = config.get("title", target) # 제목
            card = self.create_quick_access_card(self.quick_access_frame, icon, title, target)
            card.grid(row=0, column=i, padx=10, pady=20, sticky="nsew") # 카드 간 간격(padx) 조정

    def create_quick_access_card(self, master, icon, title, target):
        """클릭 가능한 바로가기 카드 위젯을 생성합니다."""
        card_frame = ctk.CTkFrame(master, corner_radius=15, cursor="hand2")
        card_frame.grid_rowconfigure(0, weight=1)
        card_frame.grid_columnconfigure(0, weight=1)

        icon_label = ctk.CTkLabel(card_frame, text=icon, font=ctk.CTkFont(size=40)) # 아이콘 크기 조정
        icon_label.grid(row=0, column=0, pady=(15, 5)) # 내부 여백 조정

        title_label = ctk.CTkLabel(card_frame, text=title, font=ctk.CTkFont(size=14, weight="bold")) # 폰트 크기 조정
        title_label.grid(row=1, column=0, pady=(5, 15)) # 내부 여백 조정

        # 프레임과 내부 라벨에 모두 클릭 이벤트를 바인딩하여 어디를 눌러도 동작하게 함
        for widget in [card_frame, icon_label, title_label]:
            widget.bind("<Button-1>", lambda e, t=target: self.navigate_to(t))

        return card_frame

    def navigate_to(self, target):
        """지정된 화면으로 이동합니다."""
        self.app.navigate_and_record(target)
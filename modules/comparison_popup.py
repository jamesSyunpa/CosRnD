import customtkinter as ctk
from tkinter import ttk, messagebox
import sys
import os

# 프로젝트 루트 경로를 sys.path에 추가 (상대 경로 import를 위함)
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if PROJECT_ROOT not in sys.path:
    sys.path.append(PROJECT_ROOT)

from database.db_manager import db_manager
from sqlalchemy.orm import joinedload
from database.models import Formulation
from decimal import Decimal
from utils import center_window_on_mouse_display

class FormulationComparisonPopup(ctk.CTkToplevel):
    """두 처방을 비교하여 차이점을 보여주는 팝업 창"""

    def __init__(self, master, formulation_id1, formulation_id2):
        super().__init__(master)
        self.title("처방 비교")
        self.geometry("1400x800")
        self.transient(master)
        self.grab_set()

        self.reason_entries = {} # 변경 사유 입력을 위한 Entry 위젯 저장
        self.formulation1 = None
        self.formulation2 = None

        self.setup_ui()
        self.load_and_compare(formulation_id1, formulation_id2)
        try:
            center_window_on_mouse_display(self)
        except Exception:
            pass

    def setup_ui(self):
        """UI 기본 구조를 설정합니다."""
        self.grid_columnconfigure((0, 1, 2), weight=1) # 3단 그리드로 변경
        self.grid_rowconfigure(1, weight=1)

        # --- 스타일 설정 ---
        style = ttk.Style(self)
        style.configure("Comparison.Treeview", rowheight=25, font=('Malgun Gothic', 10))
        style.configure("Comparison.Treeview.Heading", font=('Malgun Gothic', 11, 'bold'))
        style.configure("added.Treeview", foreground="#E65100") # 주황색
        style.configure("removed.Treeview", foreground="gray50")
        style.configure("increased.Treeview", foreground="red")
        style.configure("decreased.Treeview", foreground="blue")


        # --- 좌측 프레임 (처방 1) ---
        frame1 = ctk.CTkFrame(self, border_width=1)
        frame1.grid(row=0, column=0, rowspan=2, padx=10, pady=10, sticky="nsew")
        frame1.grid_columnconfigure(0, weight=1)
        frame1.grid_rowconfigure(1, weight=1)
        self.label1 = ctk.CTkLabel(frame1, text="처방 1", font=ctk.CTkFont(size=16, weight="bold"))
        self.label1.grid(row=0, column=0, padx=10, pady=10, sticky="w")
        self.tree1 = ttk.Treeview(frame1, columns=("phase", "code", "name", "ratio"), show="headings", style="Comparison.Treeview")
        self.tree1.grid(row=1, column=0, sticky="nsew")
        self._setup_treeview(self.tree1)

        # --- 우측 프레임 (처방 2) ---
        frame2 = ctk.CTkFrame(self, border_width=1)
        frame2.grid(row=0, column=1, rowspan=2, padx=10, pady=10, sticky="nsew")
        frame2.grid_columnconfigure(0, weight=1)
        frame2.grid_rowconfigure(1, weight=1)
        self.label2 = ctk.CTkLabel(frame2, text="처방 2", font=ctk.CTkFont(size=16, weight="bold"))
        self.label2.grid(row=0, column=0, padx=10, pady=10, sticky="w")
        self.tree2 = ttk.Treeview(frame2, columns=("phase", "code", "name", "ratio"), show="headings", style="Comparison.Treeview")
        self.tree2.grid(row=1, column=0, sticky="nsew")
        self._setup_treeview(self.tree2)

        # --- 우측+ 프레임 (변경 사유) ---
        frame3 = ctk.CTkFrame(self, border_width=1)
        frame3.grid(row=0, column=2, rowspan=2, padx=10, pady=10, sticky="nsew")
        frame3.grid_columnconfigure(0, weight=1)
        frame3.grid_rowconfigure(1, weight=1)
        ctk.CTkLabel(frame3, text="변경 사유", font=ctk.CTkFont(size=16, weight="bold")).grid(row=0, column=0, padx=10, pady=10, sticky="w")
        self.reason_frame = ctk.CTkScrollableFrame(frame3, label_text="")
        self.reason_frame.grid(row=1, column=0, sticky="nsew", padx=5, pady=5)
        self.reason_frame.grid_columnconfigure(0, weight=1)

        # --- 하단 버튼 프레임 ---
        bottom_frame = ctk.CTkFrame(self, fg_color="transparent")
        bottom_frame.grid(row=2, column=0, columnspan=3, pady=10)
        ctk.CTkButton(bottom_frame, text="변경 사유 저장", command=self.save_reasons).pack(side="left", padx=10)
        ctk.CTkButton(bottom_frame, text="닫기", command=self.destroy, fg_color="gray50").pack(side="left", padx=10)

    def _setup_treeview(self, tree):
        """Treeview의 컬럼과 헤더를 설정합니다."""
        tree.heading("phase", text="구분"); tree.column("phase", width=60, anchor="center")
        tree.heading("code", text="코드"); tree.column("code", width=100)
        tree.heading("name", text="원료명"); tree.column("name", width=200, stretch=True)
        tree.heading("ratio", text="함량(%)"); tree.column("ratio", width=80, anchor="e")

        # Treeview 인스턴스에 직접 태그 스타일을 설정합니다.
        tree.tag_configure("added", foreground="#E65100") # 주황색
        tree.tag_configure("removed", foreground="gray50")
        tree.tag_configure("increased", foreground="red")
        tree.tag_configure("decreased", foreground="blue")

    def load_and_compare(self, id1, id2):
        """두 처방 데이터를 로드하고 비교하여 UI에 표시합니다."""
        session = db_manager.get_session()
        try:
            # items 관계를 함께 로드하여 DetachedInstanceError 방지
            self.formulation1 = session.query(Formulation).options(
                joinedload(Formulation.items)
            ).filter_by(id=id1).first()
            self.formulation2 = session.query(Formulation).options(
                joinedload(Formulation.items)
            ).filter_by(id=id2).first()
        finally:
            session.close()

        if not self.formulation1 or not self.formulation2:
            self.destroy()
            return

        # 최신 처방을 우측에 표시하기 위해 날짜 비교
        if self.formulation1.created_at > self.formulation2.created_at:
            self.formulation1, self.formulation2 = self.formulation2, self.formulation1

        # 라벨 업데이트
        self.label1.configure(text=f"이전 버전: {self.formulation1.lab_no or self.formulation1.id}")
        self.label2.configure(text=f"최신 버전: {self.formulation2.lab_no or self.formulation2.id}")

        # --- 비교 로직 수정 ---
        # 원료 코드를 키로 하는 딕셔너리와, 순서 기반의 리스트를 함께 사용합니다.
        items1_by_code = {item.material_code: item for item in self.formulation1.items if item.material_code and item.material_code != "---"}
        items2_by_code = {item.material_code: item for item in self.formulation2.items if item.material_code and item.material_code != "---"}

        # 전체 원료 코드 목록 (중복 제거 및 정렬)
        all_codes = sorted(list(set(items1_by_code.keys()) | set(items2_by_code.keys())))

        # 변경된 항목만 수집할 리스트
        changed_items_for_reason = []

        # --- 코드 기반으로 비교 ---
        for code in all_codes:
            item1 = items1_by_code.get(code)
            item2 = items2_by_code.get(code)

            if item1 and not item2:  # 삭제됨
                changed_items_for_reason.append({'code': item1.material_code, 'type': '삭제됨', 'name': item1.material_name})
                self._insert_item(self.tree1, item1, "removed")
                self._insert_placeholder(self.tree2, "removed")
            elif not item1 and item2:  # 추가됨
                changed_items_for_reason.append({'code': item2.material_code, 'type': '추가됨', 'name': item2.material_name})
                self._insert_placeholder(self.tree1, "added")
                self._insert_item(self.tree2, item2, "added")
            elif item1 and item2:  # 둘 다 존재 -> 함량 비교
                ratio1 = item1.ratio or 0.0
                ratio2 = item2.ratio or 0.0
                diff = ratio2 - ratio1

                if abs(diff) > 1e-9:  # 함량 변경
                    changed_items_for_reason.append({'code': item2.material_code, 'type': '함량 변경', 'name': item2.material_name})
                    self._insert_item(self.tree1, item1, "decreased")
                    ratio_str = f"{Decimal(str(item2.ratio)):.4f} ({Decimal(str(diff)):+.4f})"
                    self._insert_item(self.tree2, item2, "increased", ratio_override=ratio_str)
                else:  # 변경 없음
                    self._insert_item(self.tree1, item1)
                    self._insert_item(self.tree2, item2)

        # --- 구분선(---) 처리 ---
        # 구분선은 순서가 중요하므로 별도로 처리하여 UI에 표시합니다.
        separators1 = {item.order: item for item in self.formulation1.items if item.material_code == "---"}
        separators2 = {item.order: item for item in self.formulation2.items if item.material_code == "---"}
        all_sep_orders = sorted(list(set(separators1.keys()) | set(separators2.keys())))

        if all_sep_orders:
            self._insert_placeholder(self.tree1)
            self._insert_placeholder(self.tree2)
            for order in all_sep_orders:
                if separators1.get(order): self._insert_item(self.tree1, separators1[order])
                if separators2.get(order): self._insert_item(self.tree2, separators2[order])

        # 변경된 항목에 대해서만 사유 입력 UI를 순서대로 생성
        for item in changed_items_for_reason:
            self._add_reason_entry(item['code'], item['type'], item['name'])

    def _insert_item(self, tree, item, tag="", ratio_override=None):
        """Treeview에 처방 아이템을 삽입합니다."""
        # 구분선 처리
        if item.material_code == "---":
            tree.insert("", "end", values=("", "---", "---", "---"), tags=('separator',))
            return

        if ratio_override:
            ratio_display = ratio_override
        else:
            ratio_display = f"{Decimal(str(item.ratio or 0)):.4f}"

        values = (
            item.phase or "",
            item.material_code,
            item.material_name,
            ratio_display
        )
        tree.insert("", "end", values=values, tags=(tag,) if tag else ())

    def _insert_placeholder(self, tree, tag=""):
        """차이점을 맞추기 위해 빈 줄을 삽입합니다."""
        tree.insert("", "end", values=("", "", "", ""), tags=(tag,) if tag else ())

    def _add_reason_entry(self, code, change_type, material_name, old_name=None):
        """변경 사유 입력 UI 요소를 생성합니다."""
        # 각 항목을 담을 프레임
        item_frame = ctk.CTkFrame(self.reason_frame, fg_color="transparent")
        item_frame.pack(fill="x", pady=2, padx=5)
        item_frame.grid_columnconfigure(0, weight=1)

        # 원료명과 변경 유형 표시 (원료 변경 시 이전/이후 원료명 함께 표시)
        if change_type == '함량/원료 변경' and old_name and old_name != material_name:
            label_text = f"원료 변경: {old_name} → {material_name}"
        else:
            label_text = f"[{code}] {material_name} ({change_type})"

        label = ctk.CTkLabel(item_frame, text=label_text, font=ctk.CTkFont(size=12), anchor="w")
        label.grid(row=0, column=0, sticky="ew")

        # 사유 입력 텍스트박스
        entry = ctk.CTkTextbox(item_frame, height=40, font=ctk.CTkFont(size=12), wrap="word")
        entry.grid(row=1, column=0, sticky="ew", pady=(2, 8))
        self.reason_entries[code] = entry

    def save_reasons(self):
        """입력된 변경 사유를 최신 버전 처방의 change_log에 저장합니다."""
        if not self.formulation2 or not self.formulation2.id:
            messagebox.showerror("오류", "변경 사유를 저장할 대상 처방을 찾을 수 없습니다.", parent=self)
            return

        reasons_text = []
        for code, entry in self.reason_entries.items():
            reason = entry.get("1.0", "end-1c").strip()
            if reason:
                # UI에 표시된 라벨 텍스트를 그대로 가져와서 사용합니다.
                label_widget = entry.master.winfo_children()[0] # ctk.CTkLabel
                label_text = label_widget.cget("text") # 예: "[2058] UVINUL T 150 (함량 변경)"
                reasons_text.append(f"{label_text}: {reason}")

        if not reasons_text:
            messagebox.showinfo("알림", "저장할 변경 사유가 없습니다.", parent=self)
            return

        # --- 기존 로그를 불러와서 추가하는 로직으로 변경 ---
        session = db_manager.get_session()
        try:
            # DB에서 현재 처방의 최신 change_log를 가져옵니다.
            target_formulation = session.query(Formulation).filter_by(id=self.formulation2.id).first()
            if not target_formulation:
                messagebox.showerror("오류", "DB에서 대상 처방을 찾을 수 없습니다.", parent=self)
                return

            existing_log = target_formulation.change_log or ""
            
            # 새로운 사유를 기존 로그에 추가합니다.
            new_reason_log = "\n\n[사용자 입력 사유]\n" + "\n".join(reasons_text)
            final_log = existing_log + new_reason_log

            db_manager.update_formulation_field(self.formulation2.id, 'change_log', final_log)
            messagebox.showinfo("성공", "변경 사유가 성공적으로 저장되었습니다.", parent=self)
            self.destroy()
        finally:
            session.close()
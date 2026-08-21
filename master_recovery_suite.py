# master_recovery_suite.py
"""
[마스터 복원 전용 도구 - Master Recovery Suite]
최고 관리자(MSAD) 전용 독립 복구 프로그램 및 팝업 대화상자
각 PC의 AppData 심층 은닉 볼트(.sys_archive)에 암호화 보관된 삭제 데이터(처방/원료/거래처/사용자/DB스냅샷)를
복호화하여 목록화하고, 안전하게 운영 시스템 DB로 원클릭 복원합니다.
"""

import os
import sys
import customtkinter as ctk
from tkinter import ttk, messagebox
import json
from datetime import datetime

# 프로젝트 루트 및 모듈 경로 설정
PROJECT_ROOT = os.path.dirname(os.path.abspath(__file__))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from modules.secure_vault import SecureVault
from database.db_manager import db_manager
from database.models import Formulation, FormulationItem, Material, Ingredient, Client, User
from utils import center_window_on_mouse_display

class MasterRecoveryDialog(ctk.CTkToplevel):
    """메인 시스템 내부에서 마스터키 인증 후 열리는 마스터 복구 대화상자"""
    def __init__(self, master, current_user=None, app=None):
        super().__init__(master)

        self.master = master
        self.current_user = current_user
        self.app = app

        self.title("🛡️ 럭포마 R&D 플랫폼 - 마스터 보안 복구 센터")
        self.geometry("1100x700")
        self.minsize(950, 600)
        self.transient(master)
        self.grab_set()

        self._records = []
        self._build_ui()
        try:
            center_window_on_mouse_display(self)
        except Exception:
            pass
        self.refresh_vault_records()

    def _build_ui(self):
        # 상단 타이틀 바
        header_frame = ctk.CTkFrame(self, fg_color="#1E293B", corner_radius=0, height=70)
        header_frame.pack(fill="x", side="top")
        header_frame.pack_propagate(False)

        title_label = ctk.CTkLabel(
            header_frame,
            text="🛡️ 마스터 보안 데이터 복구 센터 (Master Secure Vault)",
            font=ctk.CTkFont(family="맑은 고딕", size=17, weight="bold"),
            text_color="#38BDF8"
        )
        title_label.pack(side="left", padx=20, pady=10)

        vault_path_lbl = ctk.CTkLabel(
            header_frame,
            text=f"📁 은닉 볼트: {SecureVault.get_vault_path()}",
            font=ctk.CTkFont(family="맑은 고딕", size=11),
            text_color="#94A3B8"
        )
        vault_path_lbl.pack(side="right", padx=20, pady=10)

        # 메인 영역
        main_frame = ctk.CTkFrame(self, fg_color="transparent")
        main_frame.pack(fill="both", expand=True, padx=20, pady=15)

        # 필터 컨트롤 바
        ctrl_frame = ctk.CTkFrame(main_frame, fg_color="#1E293B", corner_radius=8, height=50)
        ctrl_frame.pack(fill="x", pady=(0, 10))
        
        ctk.CTkLabel(ctrl_frame, text="카테고리 필터:", font=ctk.CTkFont(family="맑은 고딕", size=13, weight="bold")).pack(side="left", padx=(15, 10), pady=10)
        
        self.category_var = ctk.StringVar(value="전체 (All)")
        self.cat_menu = ctk.CTkOptionMenu(
            ctrl_frame,
            values=["전체 (All)", "처방 (formulations)", "원료 (materials)", "거래처 (clients)", "사용자 (users)", "전체DB스냅샷 (database_snapshots)"],
            variable=self.category_var,
            command=lambda v: self.refresh_vault_records(),
            width=180
        )
        self.cat_menu.pack(side="left", padx=5, pady=10)

        refresh_btn = ctk.CTkButton(ctrl_frame, text="🔄 새로고침", width=100, command=self.refresh_vault_records)
        refresh_btn.pack(side="left", padx=10, pady=10)

        self.status_lbl = ctk.CTkLabel(ctrl_frame, text="기록 0건 발견", font=ctk.CTkFont(family="맑은 고딕", size=12), text_color="#38BDF8")
        self.status_lbl.pack(side="right", padx=15, pady=10)

        # 트리뷰 및 상세 패널 컨테이너
        paned_frame = ctk.CTkFrame(main_frame, fg_color="transparent")
        paned_frame.pack(fill="both", expand=True)
        paned_frame.grid_columnconfigure(0, weight=6)
        paned_frame.grid_columnconfigure(1, weight=4)
        paned_frame.grid_rowconfigure(0, weight=1)

        # 좌측: 트리뷰
        tree_frame = ctk.CTkFrame(paned_frame, fg_color="#0F172A", corner_radius=8)
        tree_frame.grid(row=0, column=0, sticky="nsew", padx=(0, 10))

        # 스타일
        style = ttk.Style()
        style.theme_use("clam")
        style.configure("Vault.Treeview", background="#0F172A", foreground="#F8FAFC", fieldbackground="#0F172A", rowheight=28, font=("맑은 고딕", 10))
        style.configure("Vault.Treeview.Heading", background="#1E293B", foreground="#38BDF8", font=("맑은 고딕", 11, "bold"))
        style.map("Vault.Treeview", background=[("selected", "#0284C7")], foreground=[("selected", "white")])

        cols = ("category", "record_id", "deleted_by", "timestamp", "summary")
        self.tree = ttk.Treeview(tree_frame, columns=cols, show="headings", style="Vault.Treeview", selectmode="browse")
        self.tree.heading("category", text="구분")
        self.tree.heading("record_id", text="데이터 식별자")
        self.tree.heading("deleted_by", text="삭제자")
        self.tree.heading("timestamp", text="삭제 일시")
        self.tree.heading("summary", text="요약 내용")

        self.tree.column("category", width=90, anchor="center")
        self.tree.column("record_id", width=140, anchor="w")
        self.tree.column("deleted_by", width=90, anchor="center")
        self.tree.column("timestamp", width=130, anchor="center")
        self.tree.column("summary", width=220, anchor="w")

        v_scroll = ttk.Scrollbar(tree_frame, orient="vertical", command=self.tree.yview)
        self.tree.configure(yscrollcommand=v_scroll.set)
        
        self.tree.pack(side="left", fill="both", expand=True, padx=(5, 0), pady=5)
        v_scroll.pack(side="right", fill="y", pady=5)

        self.tree.bind("<<TreeviewSelect>>", self.on_record_select)

        # 우측: 상세 정보 및 복원 실행 패널
        detail_frame = ctk.CTkFrame(paned_frame, fg_color="#1E293B", corner_radius=8)
        detail_frame.grid(row=0, column=1, sticky="nsew")
        
        ctk.CTkLabel(detail_frame, text="📄 복구 데이터 상세 정보", font=ctk.CTkFont(family="맑은 고딕", size=14, weight="bold"), text_color="#F8FAFC").pack(anchor="w", padx=15, pady=(15, 5))

        self.detail_textbox = ctk.CTkTextbox(detail_frame, fg_color="#0F172A", text_color="#E2E8F0", font=("Consolas", 11), wrap="word")
        self.detail_textbox.pack(fill="both", expand=True, padx=15, pady=10)

        action_frame = ctk.CTkFrame(detail_frame, fg_color="transparent")
        action_frame.pack(fill="x", padx=15, pady=(0, 15))

        self.restore_btn = ctk.CTkButton(
            action_frame,
            text="⚡ 선택 항목 DB로 복원하기 (Restore)",
            fg_color="#10B981",
            hover_color="#059669",
            font=ctk.CTkFont(family="맑은 고딕", size=13, weight="bold"),
            height=40,
            command=self.execute_restore
        )
        self.restore_btn.pack(fill="x")

    def refresh_vault_records(self):
        for item in self.tree.get_children():
            self.tree.delete(item)
            
        selected_cat = self.category_var.get()
        filter_cat = None
        if "formulations" in selected_cat: filter_cat = "formulations"
        elif "materials" in selected_cat: filter_cat = "materials"
        elif "clients" in selected_cat: filter_cat = "clients"
        elif "users" in selected_cat: filter_cat = "users"
        elif "database_snapshots" in selected_cat: filter_cat = "database_snapshots"

        records = SecureVault.list_archived_records(filter_cat)
        records.sort(key=lambda r: str(r.get('timestamp', '')), reverse=True)
        self._records = records

        cat_names = {
            "formulations": "처방",
            "materials": "원료",
            "clients": "거래처",
            "users": "사용자",
            "database_snapshots": "전체DB"
        }

        for idx, rec in enumerate(records):
            cat = rec.get('category', '')
            cat_display = cat_names.get(cat, cat)
            rec_id = rec.get('record_id', '')
            deleted_by = rec.get('deleted_by', 'system')
            ts = rec.get('timestamp', '')
            
            payload = rec.get('payload') or {}
            summary = ""
            if cat == "formulations":
                summary = f"처방명: {payload.get('experiment_name', '')} (원료 {len(payload.get('items', []))}개)"
            elif cat == "materials":
                summary = f"원료명: {payload.get('name', '')} (단가: {payload.get('unit_price', 0):,}원)"
            elif cat == "clients":
                summary = f"거래처명: {payload.get('name', '')} ({payload.get('client_type', '')})"
            elif cat == "users":
                summary = f"실명: {payload.get('real_name', '')} ({payload.get('role', '')})"
            elif cat == "database_snapshots":
                summary = f"전체 DB 복제 스냅샷 ({rec.get('file_size', 0) // 1024:,} KB)"

            self.tree.insert("", "end", iid=str(idx), values=(cat_display, rec_id, deleted_by, ts, summary))

        self.status_lbl.configure(text=f"기록 {len(records)}건 발견 (암호화 은닉 보호됨)")
        self.detail_textbox.delete("1.0", "end")
        self.detail_textbox.insert("1.0", "목록에서 복구할 항목을 선택하세요.")

    def on_record_select(self, event):
        selected = self.tree.selection()
        if not selected:
            return
        idx = int(selected[0])
        if idx >= len(self._records):
            return
            
        rec = self._records[idx]
        cat = rec.get('category', '')
        
        self.detail_textbox.delete("1.0", "end")
        if cat == "database_snapshots":
            info_text = f"=== 전체 데이터베이스 암호화 스냅샷 ===\n"
            info_text += f"• 백업 파일: {rec.get('record_id')}\n"
            info_text += f"• 보관 일시: {rec.get('timestamp')}\n"
            info_text += f"• 파일 크기: {rec.get('file_size', 0):,} Bytes\n\n"
            info_text += "※ [복원하기] 실행 시 현재 운영 DB를 본 스냅샷으로 원복합니다."
            self.detail_textbox.insert("1.0", info_text)
        else:
            payload = rec.get('payload', {})
            json_formatted = json.dumps(payload, ensure_ascii=False, indent=2)
            self.detail_textbox.insert("1.0", json_formatted)

    def execute_restore(self):
        selected = self.tree.selection()
        if not selected:
            messagebox.showwarning("선택 오류", "복원할 항목을 목록에서 선택해주세요.", parent=self)
            return
            
        idx = int(selected[0])
        rec = self._records[idx]
        file_path = rec.get('file_path')
        cat = rec.get('category')

        if not file_path or not os.path.exists(file_path):
            messagebox.showerror("오류", "선택한 은닉 백업 파일을 찾을 수 없습니다.", parent=self)
            return

        if not messagebox.askyesno("복원 확인", f"선택한 '{cat}' 데이터를 현재 운영 시스템 DB로 복원하시겠습니까?\n\n이 작업은 암호를 복호화하여 데이터를 재투입합니다.", parent=self):
            return

        try:
            category, restored_content = SecureVault.restore_record_data(file_path)
            
            if category == "database_snapshots":
                # 전체 DB 파일 복원
                cur_db_path = getattr(db_manager, 'db_path', None)
                if not cur_db_path:
                    messagebox.showerror("오류", "현재 운영 DB 경로를 확인할 수 없습니다.", parent=self)
                    return
                    
                db_manager.dispose_engine()
                with open(cur_db_path, 'wb') as f:
                    f.write(restored_content)
                messagebox.showinfo("복원 완료", f"전체 데이터베이스가 성공적으로 복원되었습니다!\n\n경로: {cur_db_path}", parent=self)
            else:
                payload = restored_content.get('payload', {})
                session = db_manager.get_session()
                try:
                    if category == "formulations":
                        # 처방 복원
                        form = Formulation(
                            experiment_name=payload.get('experiment_name'),
                            lab_no=payload.get('lab_no'),
                            revision=payload.get('revision'),
                            manager_name=payload.get('manager_name'),
                            manager_code=payload.get('manager_code'),
                            experiment_date=payload.get('experiment_date'),
                            experiment_ph_initial=payload.get('experiment_ph_initial'),
                            experiment_ph_next_day=payload.get('experiment_ph_next_day'),
                            experiment_viscosity_initial=payload.get('experiment_viscosity_initial'),
                            experiment_viscosity_next_day=payload.get('experiment_viscosity_next_day'),
                            experiment_machine=payload.get('experiment_machine'),
                            experiment_comment=payload.get('experiment_comment'),
                            oem_odm_client_id=payload.get('oem_odm_client_id'),
                            target_client_id=payload.get('target_client_id'),
                            change_log=f"[마스터 복원] {datetime.now().strftime('%Y-%m-%d %H:%M')} 복원됨"
                        )
                        session.add(form)
                        session.flush()

                        for item in payload.get('items', []):
                            f_item = FormulationItem(
                                formulation_id=form.id,
                                order=item.get('order', 1),
                                phase=item.get('phase', 'A'),
                                material_code=item.get('material_code'),
                                material_name=item.get('material_name'),
                                ratio=item.get('ratio', 0.0),
                                amount=item.get('amount', 0.0),
                                material_id=item.get('material_id')
                            )
                            session.add(f_item)
                            
                    elif category == "materials":
                        # 원료 복원
                        mat = session.query(Material).filter_by(code=payload.get('code')).first()
                        if not mat:
                            mat = Material(code=payload.get('code'))
                            session.add(mat)
                        mat.name = payload.get('name')
                        mat.name_en = payload.get('name_en')
                        mat.unit_price = payload.get('unit_price', 0.0)
                        mat.package_unit = payload.get('package_unit')
                        mat.manufacturer = payload.get('manufacturer')
                        mat.hs_code = payload.get('hs_code')
                        mat.origin = payload.get('origin')
                        mat.nmpa_reg_num = payload.get('nmpa_reg_num')
                        mat.is_active = payload.get('is_active', True)
                        mat.change_log = f"[마스터 복원] {datetime.now().strftime('%Y-%m-%d %H:%M')} 복원됨"
                        session.flush()

                        # 전성분 복원
                        session.query(Ingredient).filter_by(material_id=mat.id).delete()
                        for ing in payload.get('ingredients', []):
                            new_ing = Ingredient(
                                material_id=mat.id,
                                name_ko=ing.get('name_ko'),
                                name_en=ing.get('name_en'),
                                cas_no=ing.get('cas_no'),
                                composition_ratio=ing.get('composition_ratio', 0.0),
                                function=ing.get('function'),
                                ewg_grade=ing.get('ewg_grade'),
                                ewg_data=ing.get('ewg_data'),
                                remark=ing.get('remark')
                            )
                            session.add(new_ing)

                    elif category == "clients":
                        # 거래처 복원
                        client = Client(
                            name=payload.get('name'),
                            name_en=payload.get('name_en'),
                            business_number=payload.get('business_number'),
                            client_type=payload.get('client_type', '원료'),
                            ceo_name=payload.get('ceo_name'),
                            manager_name=payload.get('manager_name'),
                            phone=payload.get('phone'),
                            fax=payload.get('fax'),
                            email=payload.get('email'),
                            zip_code=payload.get('zip_code'),
                            address=payload.get('address'),
                            is_active=payload.get('is_active', True),
                            change_log=f"[마스터 복원] {datetime.now().strftime('%Y-%m-%d %H:%M')} 복원됨"
                        )
                        session.add(client)

                    elif category == "users":
                        # 사용자 복원
                        u = session.query(User).filter_by(username=payload.get('username')).first()
                        if not u:
                            u = User(
                                username=payload.get('username'),
                                password="RestoredPassword123!", # 기본 임시 비밀번호
                                real_name=payload.get('real_name'),
                                manager_code=payload.get('manager_code'),
                                position=payload.get('position'),
                                contact=payload.get('contact'),
                                zip_code=payload.get('zip_code'),
                                address=payload.get('address'),
                                role=payload.get('role', 'RD'),
                                is_admin=payload.get('is_admin', False),
                                change_log=f"[마스터 복원] {datetime.now().strftime('%Y-%m-%d %H:%M')} 복원됨"
                            )
                            session.add(u)

                    session.commit()
                    messagebox.showinfo("복원 완료", f"'{category}' 데이터가 운영 데이터베이스에 성공적으로 복원되었습니다!", parent=self)
                    
                    # 앱 프레임 전체 새로고침
                    if self.app and hasattr(self.app, 'refresh_data_in_all_frames'):
                        self.app.refresh_data_in_all_frames()
                        
                except Exception as db_err:
                    session.rollback()
                    messagebox.showerror("DB 오류", f"복원 데이터 삽입 실패: {db_err}", parent=self)
                finally:
                    session.close()

        except Exception as e:
            messagebox.showerror("복원 실패", f"복구 중 오류가 발생했습니다: {e}", parent=self)

class MasterRecoveryApp(ctk.CTk):
    """독립 실행형 마스터 복구 센터 앱"""
    def __init__(self):
        super().__init__()
        self.title("🛡️ 럭포마 R&D 플랫폼 - 마스터 복구 센터 (Master Recovery Suite)")
        self.geometry("1100x700")
        self.minsize(950, 600)
        ctk.set_appearance_mode("Dark")
        ctk.set_default_color_theme("blue")

        config_path = os.path.join(os.getenv('APPDATA', os.path.expanduser('~')), 'CosRnD', 'config.ini')
        try:
            db_manager.setup_database(PROJECT_ROOT, config_path, None)
        except Exception as e:
            print(f"[경고] DB 연결 초기화 실패: {e}")

        self.dialog = MasterRecoveryDialog(self)
        self.dialog.protocol("WM_DELETE_WINDOW", self.destroy)
        self.withdraw()

if __name__ == "__main__":
    app = MasterRecoveryApp()
    app.mainloop()

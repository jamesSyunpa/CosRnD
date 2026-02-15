import customtkinter as ctk
from tkinter import messagebox, ttk
from database.db_manager import db_manager
from database.models import DeletionRequest, User, Formulation, ProductionRun, ProductionFormulation
from modules.data_backup import backup_manager
from datetime import datetime
from utils import center_window_on_mouse_display

class RequestDeletionDialog(ctk.CTkToplevel):
    def __init__(self, master, current_user, target_table, target_id, target_summary):
        super().__init__(master)
        self.title("삭제 요청")
        self.geometry("400x300")
        self.current_user = current_user
        self.target_table = target_table
        self.target_id = target_id
        self.target_summary = target_summary
        
        self.transient(master)
        self.grab_set()
        
        self.setup_ui()
        try:
            center_window_on_mouse_display(self)
        except:
            pass
        
    def setup_ui(self):
        ctk.CTkLabel(self, text="삭제 요청 사유를 입력하세요", font=("Arial", 14, "bold")).pack(pady=10)
        
        ctk.CTkLabel(self, text=f"대상: {self.target_summary}").pack(pady=5)
        
        self.reason_text = ctk.CTkTextbox(self, height=100)
        self.reason_text.pack(fill="x", padx=20, pady=10)
        
        btn_frame = ctk.CTkFrame(self, fg_color="transparent")
        btn_frame.pack(fill="x", padx=20, pady=10)
        
        ctk.CTkButton(btn_frame, text="요청하기", command=self.submit_request).pack(side="right", padx=5)
        ctk.CTkButton(btn_frame, text="취소", fg_color="gray", command=self.destroy).pack(side="right", padx=5)
        
    def submit_request(self):
        reason = self.reason_text.get("1.0", "end").strip()
        if not reason:
            messagebox.showwarning("경고", "삭제 사유를 입력해주세요.", parent=self)
            return
            
        session = db_manager.get_session()
        try:
            req = DeletionRequest(
                requester_id=self.current_user.id,
                target_table=self.target_table,
                target_id=self.target_id,
                target_summary=self.target_summary,
                reason=reason,
                status='PENDING'
            )
            session.add(req)
            session.commit()
            messagebox.showinfo("성공", "삭제 요청이 등록되었습니다.\n관리자 승인 후 처리됩니다.", parent=self)
            self.destroy()
        except Exception as e:
            session.rollback()
            messagebox.showerror("오류", f"요청 실패: {e}", parent=self)
        finally:
            session.close()

class DeletionRequestManager(ctk.CTkToplevel):
    def __init__(self, master, current_user):
        super().__init__(master)
        self.title("삭제 요청 관리")
        self.geometry("900x600")
        self.current_user = current_user
        
        self.setup_ui()
        self.load_requests()
        try:
            center_window_on_mouse_display(self)
        except:
            pass
        
    def setup_ui(self):
        # Tabs: Pending Requests, Processed/Backups
        self.tab_view = ctk.CTkTabview(self)
        self.tab_view.pack(fill="both", expand=True, padx=10, pady=10)
        
        self.tab_view.add("대기중인 요청")
        self.tab_view.add("처리 내역 / 백업")
        
        self.setup_pending_tab(self.tab_view.tab("대기중인 요청"))
        self.setup_processed_tab(self.tab_view.tab("처리 내역 / 백업"))
        
    def setup_pending_tab(self, parent):
        # Treeview
        columns = ("id", "requester", "table", "summary", "reason", "date")
        self.pending_tree = ttk.Treeview(parent, columns=columns, show="headings")
        self.pending_tree.heading("id", text="ID")
        self.pending_tree.heading("requester", text="요청자")
        self.pending_tree.heading("table", text="유형")
        self.pending_tree.heading("summary", text="대상 정보")
        self.pending_tree.heading("reason", text="사유")
        self.pending_tree.heading("date", text="요청일시")
        
        self.pending_tree.column("id", width=50)
        self.pending_tree.column("requester", width=80)
        self.pending_tree.column("table", width=100)
        self.pending_tree.column("summary", width=250)
        self.pending_tree.column("reason", width=200)
        self.pending_tree.column("date", width=120)
        
        self.pending_tree.pack(fill="both", expand=True, padx=5, pady=5)
        
        btn_frame = ctk.CTkFrame(parent)
        btn_frame.pack(fill="x", padx=5, pady=5)
        
        ctk.CTkButton(btn_frame, text="승인 (백업 후 삭제)", command=lambda: self.process_request(True), fg_color="green").pack(side="left", padx=5)
        ctk.CTkButton(btn_frame, text="승인 (즉시 삭제)", command=lambda: self.process_request(False), fg_color="#D32F2F", hover_color="#B71C1C").pack(side="left", padx=5)
        ctk.CTkButton(btn_frame, text="반려", command=self.reject_request, fg_color="gray").pack(side="left", padx=5)
        ctk.CTkButton(btn_frame, text="새로고침", command=self.load_requests).pack(side="right", padx=5)
        
    def setup_processed_tab(self, parent):
        columns = ("id", "requester", "table", "summary", "status", "processed_by", "date")
        self.processed_tree = ttk.Treeview(parent, columns=columns, show="headings")
        self.processed_tree.heading("id", text="ID")
        self.processed_tree.heading("requester", text="요청자")
        self.processed_tree.heading("table", text="유형")
        self.processed_tree.heading("summary", text="대상 정보")
        self.processed_tree.heading("status", text="상태")
        self.processed_tree.heading("processed_by", text="처리자")
        self.processed_tree.heading("date", text="처리일시")
        
        self.processed_tree.pack(fill="both", expand=True, padx=5, pady=5)
        
        btn_frame = ctk.CTkFrame(parent)
        btn_frame.pack(fill="x", padx=5, pady=5)
        
        ctk.CTkButton(btn_frame, text="데이터 복구 (Restore)", command=self.restore_backup, fg_color="#1F6AA5").pack(side="left", padx=5)
        ctk.CTkButton(btn_frame, text="새로고침", command=self.load_requests).pack(side="right", padx=5)

    def load_requests(self):
        # Clear trees
        for i in self.pending_tree.get_children(): self.pending_tree.delete(i)
        for i in self.processed_tree.get_children(): self.processed_tree.delete(i)
        
        session = db_manager.get_session()
        try:
            reqs = session.query(DeletionRequest).order_by(DeletionRequest.created_at.desc()).all()
            for r in reqs:
                requester = r.requester.real_name if r.requester else "Unknown"
                if r.status == 'PENDING':
                    self.pending_tree.insert("", "end", values=(r.id, requester, r.target_table, r.target_summary, r.reason, r.created_at.strftime('%Y-%m-%d %H:%M')))
                else:
                    processor = r.processed_by.real_name if r.processed_by else ""
                    self.processed_tree.insert("", "end", values=(r.id, requester, r.target_table, r.target_summary, r.status, processor, r.updated_at.strftime('%Y-%m-%d %H:%M')))
        finally:
            session.close()

    def process_request(self, with_backup):
        sel = self.pending_tree.selection()
        if not sel: 
            messagebox.showwarning("선택", "처리할 요청을 선택하세요.", parent=self)
            return
        
        req_id = self.pending_tree.item(sel[0])['values'][0]
        
        session = db_manager.get_session()
        try:
            req = session.query(DeletionRequest).get(req_id)
            if not req: return
            
            # Backup logic
            if with_backup:
                json_data = None
                if req.target_table == 'formulations':
                    json_data = backup_manager.serialize_formulation(req.target_id)
                elif req.target_table == 'production_runs':
                    json_data = backup_manager.serialize_production_run(req.target_id)
                elif req.target_table == 'production_formulations':
                    json_data = backup_manager.serialize_production_formulation(req.target_id)
                
                if json_data:
                    req.backup_data = json_data
                    req.status = 'APPROVED_BACKUP'
                else:
                    messagebox.showerror("오류", "데이터를 찾을 수 없거나 백업에 실패했습니다. (이미 삭제되었을 수 있음)", parent=self)
                    # If data is gone, just reject or mark as error? 
                    # Let's assume user wants to cancel if backup fails.
                    return
            else:
                req.status = 'APPROVED_DELETE'
            
            # Delete Logic
            target_obj = None
            if req.target_table == 'formulations':
                target_obj = session.query(Formulation).get(req.target_id)
            elif req.target_table == 'production_runs':
                target_obj = session.query(ProductionRun).get(req.target_id)
            elif req.target_table == 'production_formulations':
                target_obj = session.query(ProductionFormulation).get(req.target_id)
                
            if target_obj:
                session.delete(target_obj)
            else:
                if not with_backup:
                    # If direct delete and object missing, just mark approved?
                    pass
                else:
                    messagebox.showwarning("경고", "대상 데이터가 이미 존재하지 않습니다.", parent=self)
            
            req.processed_by_id = self.current_user.id
            req.updated_at = datetime.utcnow()
            session.commit()
            
            messagebox.showinfo("성공", "처리되었습니다.", parent=self)
            self.load_requests()
            
        except Exception as e:
            session.rollback()
            messagebox.showerror("오류", f"처리 실패: {e}", parent=self)
        finally:
            session.close()

    def reject_request(self):
        sel = self.pending_tree.selection()
        if not sel: return
        req_id = self.pending_tree.item(sel[0])['values'][0]
        
        session = db_manager.get_session()
        try:
            req = session.query(DeletionRequest).get(req_id)
            req.status = 'REJECTED'
            req.processed_by_id = self.current_user.id
            req.updated_at = datetime.utcnow()
            session.commit()
            self.load_requests()
        finally:
            session.close()
            
    def restore_backup(self):
        sel = self.processed_tree.selection()
        if not sel: return
        req_id = self.processed_tree.item(sel[0])['values'][0]
        
        session = db_manager.get_session()
        try:
            req = session.query(DeletionRequest).get(req_id)
            if not req.backup_data:
                messagebox.showwarning("불가", "백업 데이터가 없습니다.", parent=self)
                return
            
            if messagebox.askyesno("복구 확인", "정말 복구하시겠습니까?\n이미 같은 ID의 데이터가 있다면 덮어씁니다.", parent=self):
                success, msg = backup_manager.restore_data(req.backup_data)
                if success:
                    messagebox.showinfo("성공", "복구되었습니다.", parent=self)
                else:
                    messagebox.showerror("오류", f"복구 실패: {msg}", parent=self)
        finally:
            session.close()

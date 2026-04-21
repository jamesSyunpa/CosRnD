import customtkinter as ctk
from tkinter import ttk, messagebox
import tkinter as tk
from database.db_manager import db_manager
from database.models import ProductCodeRule
from database.models import ProductCodeAssignment, Client
from datetime import datetime
import traceback
import json

class CodeManagementFrame(ctk.CTkFrame):
    def __init__(self, master, user, app):
        super().__init__(master, corner_radius=0, fg_color="transparent")
        self.current_user = user
        self.app = app
        
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(0, weight=1)
        
        self._selected_rule_id = None
        
        self.setup_ui()
        self.load_rules()
        
    def setup_ui(self):
        # Layout: Left (Form), Right (List)
        paned = ctk.CTkFrame(self, fg_color="transparent")
        paned.grid(row=0, column=0, sticky="nsew", padx=10, pady=10)
        paned.grid_columnconfigure(0, weight=0, minsize=400) # Form
        paned.grid_columnconfigure(1, weight=1) # List
        paned.grid_rowconfigure(0, weight=1)
        
        # --- Left: Form ---
        form_frame = ctk.CTkFrame(paned)
        form_frame.grid(row=0, column=0, sticky="nsew", padx=(0, 10))
        form_frame.grid_columnconfigure(1, weight=1)
        
        ctk.CTkLabel(form_frame, text="코드 규칙 정보", font=ctk.CTkFont(size=14, weight="bold")).grid(row=0, column=0, columnspan=2, pady=15)
        
        self.entries = {}
        row = 1
        
        # Rule Name
        ctk.CTkLabel(form_frame, text="규칙명").grid(row=row, column=0, sticky="w", padx=10, pady=5)
        self.entries['rule_name'] = ctk.CTkEntry(form_frame)
        self.entries['rule_name'].grid(row=row, column=1, sticky="ew", padx=10, pady=5)
        row += 1
        
        # Type (Combobox) - 사용자 친화적 표시
        ctk.CTkLabel(form_frame, text="구분").grid(row=row, column=0, sticky="w", padx=10, pady=5)
        self.type_var = ctk.StringVar(value="반제품")
        # 보여지는 값은 한국어(반제품/완제품), 내부 저장은 매핑으로 처리
        self.type_combo = ctk.CTkOptionMenu(form_frame, variable=self.type_var, values=["반제품", "완제품"]) 
        self.type_combo.grid(row=row, column=1, sticky="w", padx=10, pady=5)
        # Helper text (간단 안내)
        ctk.CTkLabel(form_frame, text="(반제품: 연구용 반제품, 완제품: 출하시제품)", font=("Arial", 10), text_color="gray").grid(row=row, column=1, sticky="e", padx=10)
        row += 1
        
        # Prefix (제품구분문자)
        ctk.CTkLabel(form_frame, text="제품구분문자(예: S, P)").grid(row=row, column=0, sticky="w", padx=10, pady=5)
        self.entries['prefix'] = ctk.CTkEntry(form_frame)
        self.entries['prefix'].grid(row=row, column=1, sticky="ew", padx=10, pady=5)
        row += 1
        
        # Year Format
        ctk.CTkLabel(form_frame, text="연도 포맷").grid(row=row, column=0, sticky="w", padx=10, pady=5)
        self.year_var = ctk.StringVar(value="YY")
        ctk.CTkOptionMenu(form_frame, variable=self.year_var, values=["YY", "YYYY", "NONE"]).grid(row=row, column=1, sticky="w", padx=10, pady=5)
        row += 1
        
        # Separator (구분)
        ctk.CTkLabel(form_frame, text="구분(예: -)").grid(row=row, column=0, sticky="w", padx=10, pady=5)
        self.entries['separator'] = ctk.CTkEntry(form_frame)
        self.entries['separator'].grid(row=row, column=1, sticky="ew", padx=10, pady=5)
        row += 1
        
        # Sequence Digits
        ctk.CTkLabel(form_frame, text="일련번호 자릿수").grid(row=row, column=0, sticky="w", padx=10, pady=5)
        self.entries['sequence_length'] = ctk.CTkEntry(form_frame)
        self.entries['sequence_length'].grid(row=row, column=1, sticky="ew", padx=10, pady=5)
        self.entries['sequence_length'].insert(0, "3")
        row += 1
        
        # Suffix
        ctk.CTkLabel(form_frame, text="접미사(Suffix)").grid(row=row, column=0, sticky="w", padx=10, pady=5)
        self.entries['suffix'] = ctk.CTkEntry(form_frame)
        self.entries['suffix'].grid(row=row, column=1, sticky="ew", padx=10, pady=5)
        row += 1

        # 관리 항목 정의 (간단)
        ctk.CTkLabel(form_frame, text="관리 항목 (예: 온도, 장비)").grid(row=row, column=0, sticky="nw", padx=10, pady=5)
        # CTkTextbox is available in newer customtkinter; fallback to simple Entry if missing
        try:
            self.attribute_text = ctk.CTkTextbox(form_frame, height=80)
        except Exception:
            self.attribute_text = ctk.CTkEntry(form_frame)
        self.attribute_text.grid(row=row, column=1, sticky="ew", padx=10, pady=5)
        # 관리 항목 편집 버튼
        ctk.CTkButton(form_frame, text="관리 항목 편집", command=self.open_attribute_editor, width=120).grid(row=row, column=2, sticky="w", padx=6)
        ctk.CTkLabel(form_frame, text="간단 설명: 발급 시 선택할 항목을 정의합니다. 예) 온도(실온/가열), 장비(디스퍼/호모)", font=("Arial", 9), text_color="gray").grid(row=row+1, column=1, sticky="w", padx=10)
        ctk.CTkLabel(form_frame, text="(고급: JSON 형식으로 직접 정의 가능)", font=("Arial", 9), text_color="gray").grid(row=row+2, column=1, sticky="w", padx=10)
        row += 2
        
        # Current Sequence (Editable)
        ctk.CTkLabel(form_frame, text="현재 번호").grid(row=row, column=0, sticky="w", padx=10, pady=5)
        self.entries['current_sequence'] = ctk.CTkEntry(form_frame)
        self.entries['current_sequence'].grid(row=row, column=1, sticky="ew", padx=10, pady=5)
        self.entries['current_sequence'].insert(0, "0")
        ctk.CTkLabel(form_frame, text="(다음 발급 시 +1)", font=("Arial", 10), text_color="gray").grid(row=row+1, column=1, sticky="w", padx=10)
        row += 2
        
        # Preview
        ctk.CTkFrame(form_frame, height=2, fg_color="gray").grid(row=row, column=0, columnspan=2, sticky="ew", padx=10, pady=10)
        row += 1
        ctk.CTkLabel(form_frame, text="미리보기 (다음 번호)").grid(row=row, column=0, sticky="w", padx=10, pady=5)
        self.preview_label = ctk.CTkLabel(form_frame, text="", font=ctk.CTkFont(size=16, weight="bold"), text_color="#1F6AA5")
        self.preview_label.grid(row=row, column=1, sticky="w", padx=10, pady=5)
        row += 1

        # Assigned clients for selected rule (display only)
        ctk.CTkLabel(form_frame, text="할당된 거래처").grid(row=row, column=0, sticky="w", padx=10, pady=5)
        self.assigned_clients_label = ctk.CTkLabel(form_frame, text="(선택된 규칙의 거래처가 표시됩니다)")
        self.assigned_clients_label.grid(row=row, column=1, sticky="w", padx=10, pady=5)
        row += 1
        
        ctk.CTkButton(form_frame, text="미리보기 갱신", command=self.update_preview, width=100, fg_color="gray").grid(row=row, column=1, sticky="e", padx=10, pady=5)
        row += 1
        # Attribute widgets area (show attributes as rows, editable)
        self.attribute_area = ctk.CTkFrame(form_frame, fg_color="transparent")
        self.attribute_area.grid(row=row, column=0, columnspan=2, sticky='nsew', padx=10, pady=6)
        self.attribute_area.grid_columnconfigure(0, weight=1)
        self.attribute_rows = []
        # Quick add button: place on the row below the attribute area to avoid overlap
        ctk.CTkButton(form_frame, text="항목 추가(빠른)", command=self.add_attribute_quick, width=120).grid(row=row+1, column=1, sticky='e', padx=10)
        row += 2
        
        # Buttons
        btn_frame = ctk.CTkFrame(form_frame, fg_color="transparent")
        btn_frame.grid(row=row, column=0, columnspan=2, pady=20)
        
        ctk.CTkButton(btn_frame, text="저장", command=self.save_rule).pack(side="left", padx=5)
        ctk.CTkButton(btn_frame, text="초기화", command=self.clear_form).pack(side="left", padx=5)
        ctk.CTkButton(btn_frame, text="삭제", command=self.delete_rule, fg_color="#D32F2F", hover_color="#B71C1C").pack(side="left", padx=5)
        ctk.CTkButton(btn_frame, text="발급", command=self.open_issue_dialog, fg_color="#1F6AA5").pack(side="left", padx=5)
        
        # Bind events for live preview (optional, maybe too heavy? let's stick to button or focus out)
        for entry in self.entries.values():
            entry.bind("<KeyRelease>", lambda e: self.update_preview())
        
        # --- Right: List ---
        list_frame = ctk.CTkFrame(paned)
        list_frame.grid(row=0, column=1, sticky="nsew")
        list_frame.grid_columnconfigure(0, weight=1)
        list_frame.grid_rowconfigure(1, weight=1)
        
        ctk.CTkLabel(list_frame, text="규칙 목록", font=ctk.CTkFont(size=14, weight="bold")).grid(row=0, column=0, sticky="w", padx=10, pady=10)
        
        columns = ("id", "name", "type", "prefix", "format", "next_code")
        self.tree = ttk.Treeview(list_frame, columns=columns, show="headings")
        self.tree.heading("id", text="ID")
        self.tree.heading("name", text="규칙명")
        self.tree.heading("type", text="구분")
        self.tree.heading("prefix", text="접두사")
        self.tree.heading("format", text="포맷")
        self.tree.heading("next_code", text="다음 발급 예시")
        
        self.tree.column("id", width=40, anchor="center")
        self.tree.column("name", width=150)
        self.tree.column("type", width=80, anchor="center")
        self.tree.column("prefix", width=60, anchor="center")
        self.tree.column("format", width=100, anchor="center")
        self.tree.column("next_code", width=120)
        
        self.tree.grid(row=1, column=0, sticky="nsew", padx=10, pady=5)
        
        scrollbar = ttk.Scrollbar(list_frame, orient="vertical", command=self.tree.yview)
        self.tree.configure(yscrollcommand=scrollbar.set)
        scrollbar.grid(row=1, column=1, sticky="ns", pady=5)
        
        self.tree.bind("<<TreeviewSelect>>", self.on_select)

        # --- Assigned Codes (아래) ---
        ctk.CTkLabel(list_frame, text="할당된 코드 목록", font=ctk.CTkFont(size=12, weight="bold")).grid(row=2, column=0, sticky="w", padx=10, pady=(10,0))
        self.assign_tree = ttk.Treeview(list_frame, columns=("id","client","rule","product","code","created"), show="headings")
        self.assign_tree.heading("id", text="ID"); self.assign_tree.column("id", width=40, anchor="center")
        self.assign_tree.heading("client", text="거래처"); self.assign_tree.column("client", width=140)
        self.assign_tree.heading("rule", text="규칙"); self.assign_tree.column("rule", width=140)
        self.assign_tree.heading("product", text="제품명"); self.assign_tree.column("product", width=160)
        self.assign_tree.heading("code", text="코드"); self.assign_tree.column("code", width=160)
        self.assign_tree.heading("created", text="등록일"); self.assign_tree.column("created", width=140)
        self.assign_tree.grid(row=3, column=0, sticky="nsew", padx=10, pady=6)

        assign_btns = ctk.CTkFrame(list_frame, fg_color="transparent")
        assign_btns.grid(row=4, column=0, sticky="e", pady=(4,0), padx=10)
        ctk.CTkButton(assign_btns, text="할당 추가", command=self.open_assignment_dialog, width=110).pack(side="left", padx=6)
        ctk.CTkButton(assign_btns, text="할당 삭제", command=self.delete_assignment, width=110, fg_color="#D32F2F").pack(side="left", padx=6)

        # load assignments
        self.load_assignments()

    def generate_preview_str(self, prefix, year_fmt, sep, seq_len, current_seq, suffix):
        try:
            code = prefix or ""
            
            if year_fmt == 'YY':
                code += datetime.now().strftime('%y')
            elif year_fmt == 'YYYY':
                code += datetime.now().strftime('%Y')
                
            if sep:
                code += sep
                
            next_seq = int(current_seq or 0) + 1
            code += str(next_seq).zfill(int(seq_len or 3))
            
            if suffix:
                code += suffix
            return code
        except:
            return "Error"

    def build_code_with_attributes(self, prefix, year_fmt, sep, seq_len, current_seq, suffix, attributes: dict):
        """attributes: dict mapping attribute key -> selected value. If token_map provided, use token."""
        try:
            code = prefix or ""
            if year_fmt == 'YY':
                code += datetime.now().strftime('%y')
            elif year_fmt == 'YYYY':
                code += datetime.now().strftime('%Y')

            # insert attribute tokens if provided (concatenate all in order of attributes dict)
            if attributes:
                for k, v in attributes.items():
                    # if value is a dict with token, expect tuple (value, token)
                    if isinstance(v, (list, tuple)):
                        token = v[1]
                    else:
                        token = v
                    code += str(token)

            if sep:
                code += sep

            next_seq = int(current_seq or 0) + 1
            code += str(next_seq).zfill(int(seq_len or 3))

            if suffix:
                code += suffix
            return code
        except Exception:
            traceback.print_exc()
            return "Error"

    def update_preview(self):
        code = self.generate_preview_str(
            self.entries['prefix'].get(),
            self.year_var.get(),
            self.entries['separator'].get(),
            self.entries['sequence_length'].get(),
            self.entries['current_sequence'].get(),
            self.entries['suffix'].get()
        )
        self.preview_label.configure(text=code)

    def generate_semi_code(self,
                            date=None,
                            kiln="K01",
                            temp="RT",
                            process="MIX",
                            batch_no=1,
                            prefix=None,
                            separator='-',
                            seq_length=3,
                            suffix=None):
        """
        반제품 코드 생성 함수
        date: 생산일자 (YYYYMMDD) 또는 datetime.date/datetime 객체, 기본값은 오늘 날짜
        kiln: 가마/탱크 번호 (예: K01, T02)
        temp: 온도 조건 (예: HOT, RT, COLD)
        process: 공정 단계 (예: MIX, FER, FIL)
        batch_no: 해당 날짜의 생산 순번 (정수)
        prefix: 제품구분문자(예: S). 미지정 시 폼의 제품구분문자 사용(있다면)
        separator: 구분자 문자
        seq_length: 배치번호 자리수 (zfill 적용)
        suffix: 접미사
        """
        try:
            # 날짜 처리
            if date is None:
                date_str = datetime.now().strftime('%Y%m%d')
            else:
                if isinstance(date, str):
                    date_str = date
                else:
                    try:
                        date_str = date.strftime('%Y%m%d')
                    except Exception:
                        date_str = datetime.now().strftime('%Y%m%d')

            # prefix fallback
            if prefix is None:
                try:
                    prefix = self.entries.get('prefix').get()
                except Exception:
                    prefix = ''

            parts = []
            if prefix:
                parts.append(str(prefix))

            parts.append(str(date_str))

            if kiln:
                parts.append(str(kiln))
            if temp:
                parts.append(str(temp))
            if process:
                parts.append(str(process))

            header = separator.join(parts) if separator is not None else ''.join(parts)

            seq = str(int(batch_no)).zfill(int(seq_length or 3))

            code = f"{header}{separator}{seq}" if separator is not None else f"{header}{seq}"
            if suffix:
                code = f"{code}{suffix}"

            return code
        except Exception as e:
            traceback.print_exc()
            return f"Error: {e}"

    def open_issue_dialog(self):
        """Open a dialog to select attribute values and issue a code (increment sequence).
        This dialog now supports auto-filled (editable) date, kiln, temp, process and batch_no.
        For rules with code_type 'SEMI' the specialized `generate_semi_code` is used.
        """
        if not self._selected_rule_id:
            messagebox.showwarning("선택 오류", "발급할 규칙을 선택하세요.")
            return

        session = db_manager.get_session()
        try:
            rule = session.query(ProductCodeRule).get(self._selected_rule_id)
            if not rule:
                messagebox.showerror("오류", "규칙을 찾을 수 없습니다.")
                return

            # parse attribute schema
            try:
                schema = json.loads(rule.attribute_schema or '[]')
            except Exception:
                schema = []

            dlg = ctk.CTkToplevel(self)
            dlg.title("코드 발급")
            dlg.geometry("560x520")

            # Header fields (auto but editable)
            header = ctk.CTkFrame(dlg)
            header.grid(row=0, column=0, columnspan=2, sticky='ew', padx=8, pady=6)
            header.grid_columnconfigure(1, weight=1)

            ctk.CTkLabel(header, text='생산일자 (YYYYMMDD)').grid(row=0, column=0, sticky='w', padx=6, pady=4)
            date_var = tk.StringVar(value=datetime.now().strftime('%Y%m%d'))
            date_ent = ctk.CTkEntry(header, textvariable=date_var)
            date_ent.grid(row=0, column=1, sticky='ew', padx=6, pady=4)
            ctk.CTkButton(header, text='오늘', width=60, command=lambda: date_var.set(datetime.now().strftime('%Y%m%d'))).grid(row=0, column=2, padx=6)

            ctk.CTkLabel(header, text='가마/탱크').grid(row=1, column=0, sticky='w', padx=6, pady=4)
            kiln_var = tk.StringVar(value='K01')
            kiln_ent = ctk.CTkEntry(header, textvariable=kiln_var)
            kiln_ent.grid(row=1, column=1, sticky='ew', padx=6, pady=4)

            ctk.CTkLabel(header, text='온도').grid(row=2, column=0, sticky='w', padx=6, pady=4)
            temp_var = tk.StringVar(value='RT')
            temp_ent = ctk.CTkEntry(header, textvariable=temp_var)
            temp_ent.grid(row=2, column=1, sticky='ew', padx=6, pady=4)

            ctk.CTkLabel(header, text='공정').grid(row=3, column=0, sticky='w', padx=6, pady=4)
            process_var = tk.StringVar(value='MIX')
            process_ent = ctk.CTkEntry(header, textvariable=process_var)
            process_ent.grid(row=3, column=1, sticky='ew', padx=6, pady=4)

            next_seq_default = int(rule.current_sequence or 0) + 1
            ctk.CTkLabel(header, text='배치번호 (숫자)').grid(row=4, column=0, sticky='w', padx=6, pady=4)
            batch_var = tk.StringVar(value=str(next_seq_default))
            batch_ent = ctk.CTkEntry(header, textvariable=batch_var)
            batch_ent.grid(row=4, column=1, sticky='ew', padx=6, pady=4)

            # Attribute controls (below header)
            controls = {}
            r = 5
            for attr in schema:
                key = attr.get('key')
                if not key:
                    continue
                # skip if this attribute is covered by header
                if str(key).lower() in ('date', 'kiln', 'temp', 'process', 'batch_no', 'batch'):
                    continue
                label = attr.get('label') or key
                desc = attr.get('description') or ''
                atype = attr.get('type') or 'text'
                label_text = label if not desc else f"{label} — {desc}"
                ctk.CTkLabel(dlg, text=label_text).grid(row=r, column=0, sticky='w', padx=8, pady=6)
                if atype == 'select':
                    values = attr.get('options') or []
                    var = ctk.StringVar(value=values[0] if values else '')
                    opt = ctk.CTkOptionMenu(dlg, variable=var, values=values)
                    opt.grid(row=r, column=1, sticky='w', padx=8, pady=6)
                    controls[key] = (attr, var)
                else:
                    ent = ctk.CTkEntry(dlg)
                    ent.grid(row=r, column=1, sticky='ew', padx=8, pady=6)
                    controls[key] = (attr, ent)
                r += 1

            def do_issue():
                # collect attribute values
                attributes = {}
                for k, (attr, widget) in controls.items():
                    if isinstance(widget, ctk.StringVar):
                        val = widget.get()
                    else:
                        try:
                            val = widget.get()
                        except Exception:
                            val = ''
                    token_map = attr.get('token_map') or {}
                    token = token_map.get(val, val)
                    attributes[k] = (val, token)

                # header values
                date_val = date_var.get().strip()
                kiln_val = kiln_var.get().strip()
                temp_val = temp_var.get().strip()
                process_val = process_var.get().strip()
                try:
                    batch_no_val = int(batch_var.get())
                except Exception:
                    batch_no_val = int(rule.current_sequence or 0) + 1

                # build code depending on type
                if rule.code_type == 'SEMI':
                    code = self.generate_semi_code(
                        date=date_val,
                        kiln=kiln_val,
                        temp=temp_val,
                        process=process_val,
                        batch_no=batch_no_val,
                        prefix=rule.prefix,
                        separator=rule.separator,
                        seq_length=rule.sequence_length,
                        suffix=rule.suffix
                    )
                else:
                    code = self.build_code_with_attributes(
                        rule.prefix, rule.year_format, rule.separator,
                        rule.sequence_length, rule.current_sequence, rule.suffix, attributes
                    )

                # synchronize and save sequence
                try:
                    if rule.code_type == 'SEMI':
                        rule.current_sequence = int(batch_no_val)
                    else:
                        rule.current_sequence = int(rule.current_sequence or 0) + 1
                    session.add(rule)
                    session.commit()
                except Exception as e:
                    session.rollback()
                    messagebox.showerror("오류", f"발급 실패: {e}")
                    return

                messagebox.showinfo("발급 완료", f"발급 코드: {code}")
                dlg.destroy()
                self.load_rules()

            ctk.CTkButton(dlg, text="발급", command=do_issue, fg_color="#1F6AA5").grid(row=r+1, column=0, columnspan=2, pady=12)

        finally:
            session.close()

    def open_attribute_editor(self):
        """Open a GUI editor to manage attribute schema in a user-friendly way.
        Edits are saved back to the attribute_text control as JSON.
        """
        # load current schema
        try:
            raw = None
            try:
                raw = self.attribute_text.get('1.0', 'end').strip()
            except Exception:
                raw = self.attribute_text.get().strip()
            schema = json.loads(raw or '[]')
        except Exception:
            schema = []

        dlg = ctk.CTkToplevel(self)
        dlg.title("관리 항목 편집")
        dlg.geometry("700x360")
        dlg.transient(self)
        dlg.grab_set()
        dlg.lift()
        try:
            dlg.focus_force()
        except Exception:
            pass
        try:
            dlg.attributes('-topmost', True)
            dlg.after(100, lambda: dlg.attributes('-topmost', False))
        except Exception:
            pass

        # Left: list of attributes
        left = ctk.CTkFrame(dlg)
        left.grid(row=0, column=0, sticky='nswe', padx=8, pady=8)
        left.grid_rowconfigure(0, weight=1)
        left.grid_columnconfigure(0, weight=1)

        lbl = ctk.CTkLabel(left, text="항목 목록")
        lbl.grid(row=0, column=0, sticky='w')

        listbox_frame = tk.Frame(left)
        listbox_frame.grid(row=1, column=0, sticky='nswe')
        listbox_frame.rowconfigure(0, weight=1)
        listbox_frame.columnconfigure(0, weight=1)

        lb = tk.Listbox(listbox_frame, exportselection=False)
        lb.grid(row=0, column=0, sticky='nswe')
        lb_scroll = tk.Scrollbar(listbox_frame, command=lb.yview)
        lb_scroll.grid(row=0, column=1, sticky='ns')
        lb.configure(yscrollcommand=lb_scroll.set)

        # Right: editor fields
        right = ctk.CTkFrame(dlg)
        right.grid(row=0, column=1, sticky='nswe', padx=8, pady=8)
        right.grid_columnconfigure(1, weight=1)

        ctk.CTkLabel(right, text="Key").grid(row=0, column=0, sticky='w', padx=6, pady=6)
        key_ent = ctk.CTkEntry(right)
        key_ent.grid(row=0, column=1, sticky='ew', padx=6, pady=6)

        ctk.CTkLabel(right, text="표시명").grid(row=1, column=0, sticky='w', padx=6, pady=6)
        label_ent = ctk.CTkEntry(right)
        label_ent.grid(row=1, column=1, sticky='ew', padx=6, pady=6)

        ctk.CTkLabel(right, text="설명(일반 사용자용)").grid(row=2, column=0, sticky='w', padx=6, pady=6)
        desc_ent = ctk.CTkEntry(right)
        desc_ent.grid(row=2, column=1, sticky='ew', padx=6, pady=6)
        ctk.CTkLabel(right, text="형식").grid(row=3, column=0, sticky='w', padx=6, pady=6)
        type_var = tk.StringVar(value='select')
        type_opt = ctk.CTkOptionMenu(right, variable=type_var, values=['select', 'text'])
        type_opt.grid(row=3, column=1, sticky='w', padx=6, pady=6)

        ctk.CTkLabel(right, text="옵션 (쉼표로 구분)").grid(row=4, column=0, sticky='w', padx=6, pady=6)
        options_ent = ctk.CTkEntry(right)
        options_ent.grid(row=4, column=1, sticky='ew', padx=6, pady=6)

        ctk.CTkLabel(right, text="토큰 매핑 (옵션:토큰, 쉼표구분)").grid(row=5, column=0, sticky='w', padx=6, pady=6)
        token_ent = ctk.CTkEntry(right)
        token_ent.grid(row=5, column=1, sticky='ew', padx=6, pady=6)

        # Buttons for attribute item actions
        btn_frame = ctk.CTkFrame(right, fg_color='transparent')
        btn_frame.grid(row=6, column=0, columnspan=2, pady=10)
        add_btn = ctk.CTkButton(btn_frame, text="추가", width=80)
        add_btn.pack(side='left', padx=6)
        update_btn = ctk.CTkButton(btn_frame, text="저장", width=80)
        update_btn.pack(side='left', padx=6)
        remove_btn = ctk.CTkButton(btn_frame, text="삭제", width=80)
        remove_btn.pack(side='left', padx=6)

        def refresh_listbox():
            lb.delete(0, 'end')
            for i, a in enumerate(schema):
                desc = a.get('description') or a.get('label') or ''
                display = f"{i+1}. {a.get('label') or a.get('key') or ''} — {desc} [{a.get('key')}]"
                lb.insert('end', display)

        def load_selected(evt=None):
            sel = lb.curselection()
            if not sel:
                return
            idx = sel[0]
            a = schema[idx]
            key_ent.delete(0, 'end'); key_ent.insert(0, a.get('key',''))
            label_ent.delete(0, 'end'); label_ent.insert(0, a.get('label',''))
            desc_ent.delete(0, 'end'); desc_ent.insert(0, a.get('description',''))
            t = a.get('type','text')
            type_var.set(t)
            opts = a.get('options') or []
            options_ent.delete(0, 'end'); options_ent.insert(0, ','.join(opts))
            tm = a.get('token_map') or {}
            token_ent.delete(0, 'end'); token_ent.insert(0, ','.join([f"{k}:{v}" for k,v in tm.items()]))

        def add_attr():
            k = key_ent.get().strip()
            if not k:
                messagebox.showwarning('입력 오류', 'Key를 입력하세요.')
                return
            new = {
                'key': k,
                'label': label_ent.get().strip() or k,
                'description': desc_ent.get().strip(),
                'type': type_var.get(),
            }
            if type_var.get() == 'select':
                opts = [o.strip() for o in options_ent.get().split(',') if o.strip()]
                new['options'] = opts
                tm = {}
                for pair in [p.strip() for p in token_ent.get().split(',') if p.strip()]:
                    if ':' in pair:
                        a,b = pair.split(':',1); tm[a.strip()] = b.strip()
                if tm:
                    new['token_map'] = tm
            schema.append(new)
            refresh_listbox()

        def update_attr():
            sel = lb.curselection()
            if not sel:
                messagebox.showwarning('선택 오류', '수정할 항목을 선택하세요.')
                return
            idx = sel[0]
            k = key_ent.get().strip()
            if not k:
                messagebox.showwarning('입력 오류', 'Key를 입력하세요.')
                return
            a = schema[idx]
            a['key'] = k
            a['label'] = label_ent.get().strip() or k
            a['description'] = desc_ent.get().strip()
            a['type'] = type_var.get()
            if type_var.get() == 'select':
                opts = [o.strip() for o in options_ent.get().split(',') if o.strip()]
                a['options'] = opts
                tm = {}
                for pair in [p.strip() for p in token_ent.get().split(',') if p.strip()]:
                    if ':' in pair:
                        aa,bb = pair.split(':',1); tm[aa.strip()] = bb.strip()
                a['token_map'] = tm
            else:
                a.pop('options', None); a.pop('token_map', None)
            refresh_listbox()

        def remove_attr():
            sel = lb.curselection()
            if not sel:
                return
            idx = sel[0]
            schema.pop(idx)
            refresh_listbox()

        def save_all_and_close():
            try:
                txt = json.dumps(schema, ensure_ascii=False)
                try:
                    self.attribute_text.delete('1.0', 'end')
                    self.attribute_text.insert('1.0', txt)
                except Exception:
                    self.attribute_text.delete(0, 'end')
                    self.attribute_text.insert(0, txt)
                dlg.destroy()
                # refresh main-form attribute widgets
                try:
                    self.render_attribute_widgets()
                except Exception:
                    pass
                # Load assigned clients for this rule
                try:
                    self.load_rule_assignments(rule.id)
                except Exception:
                    pass
            except Exception as e:
                messagebox.showerror('오류', f'저장 실패: {e}')

        # bind actions
        lb.bind('<<ListboxSelect>>', load_selected)
        add_btn.configure(command=add_attr)
        update_btn.configure(command=update_attr)
        remove_btn.configure(command=remove_attr)

        # Bottom save/close
        bottom = ctk.CTkFrame(dlg, fg_color='transparent')
        bottom.grid(row=1, column=0, columnspan=2, pady=6)
        ctk.CTkButton(bottom, text='모두 저장', command=save_all_and_close, fg_color='#1F6AA5').pack(side='left', padx=6)
        ctk.CTkButton(bottom, text='취소', command=dlg.destroy).pack(side='left', padx=6)

        # initialize list
        refresh_listbox()

    def load_rules(self):
        for item in self.tree.get_children():
            self.tree.delete(item)
            
        session = db_manager.get_session()
        try:
            rules = session.query(ProductCodeRule).all()
            for rule in rules:
                # Generate preview for list
                preview = self.generate_preview_str(
                    rule.prefix, rule.year_format, rule.separator, 
                    rule.sequence_length, rule.current_sequence, rule.suffix
                )
                fmt_str = f"{rule.year_format}+{rule.separator}+{rule.sequence_length}자리"
                
                type_map = {"SEMI": "반제품", "FINISHED": "완제품"}
                type_display = type_map.get(rule.code_type, rule.code_type)
                
                self.tree.insert("", "end", values=(
                    rule.id, rule.rule_name, type_display, 
                    rule.prefix, fmt_str, preview
                ))
        finally:
            session.close()

        # ensure assignments refreshed when rules loaded (outside DB session)
        try:
            self.load_assignments()
        except Exception:
            pass
        try:
            # clear assigned clients display initially
            self.assigned_clients_label.configure(text='')
        except Exception:
            pass

    def on_select(self, event):
        sel = self.tree.selection()
        if not sel: return
        
        item_vals = self.tree.item(sel[0])['values']
        rule_id = item_vals[0]
        
        session = db_manager.get_session()
        try:
            rule = session.query(ProductCodeRule).get(rule_id)
            if rule:
                self._selected_rule_id = rule.id
                self.entries['rule_name'].delete(0, "end"); self.entries['rule_name'].insert(0, rule.rule_name or "")
                # display friendly type (반제품/완제품)
                type_map = {"SEMI": "반제품", "FINISHED": "완제품"}
                self.type_var.set(type_map.get(rule.code_type, rule.code_type))
                self.entries['prefix'].delete(0, "end"); self.entries['prefix'].insert(0, rule.prefix or "")
                self.year_var.set(rule.year_format or "YY")
                self.entries['separator'].delete(0, "end"); self.entries['separator'].insert(0, rule.separator or "")
                self.entries['sequence_length'].delete(0, "end"); self.entries['sequence_length'].insert(0, str(rule.sequence_length))
                self.entries['current_sequence'].delete(0, "end"); self.entries['current_sequence'].insert(0, str(rule.current_sequence))
                self.entries['suffix'].delete(0, "end"); self.entries['suffix'].insert(0, rule.suffix or "")
                # load attribute schema JSON into textbox/entry
                try:
                    text = rule.attribute_schema or '[]'
                except Exception:
                    text = '[]'
                try:
                    # CTkTextbox
                    self.attribute_text.delete('1.0', 'end')
                    self.attribute_text.insert('1.0', text)
                except Exception:
                    # Entry fallback
                    self.attribute_text.delete(0, 'end')
                    self.attribute_text.insert(0, text)

                self.update_preview()
                # render attribute widgets on main form
                try:
                    self.render_attribute_widgets()
                except Exception:
                    pass
        finally:
            session.close()

    def save_rule(self):
        try:
            data = {k: v.get() for k, v in self.entries.items()}
            # map displayed Korean type back to internal code_type
            type_reverse = {"반제품": "SEMI", "완제품": "FINISHED"}
            code_type = type_reverse.get(self.type_var.get(), self.type_var.get())
            year_fmt = self.year_var.get()
            
            if not data['rule_name']:
                messagebox.showwarning("입력 오류", "규칙명을 입력하세요.")
                return
                
            session = db_manager.get_session()
            try:
                if self._selected_rule_id:
                    rule = session.query(ProductCodeRule).get(self._selected_rule_id)
                    # Check uniqueness if type changed
                    if rule.code_type != code_type:
                        exist = session.query(ProductCodeRule).filter_by(code_type=code_type).first()
                        if exist:
                            messagebox.showwarning("중복", f"'{code_type}' 타입의 규칙은 이미 존재합니다.")
                            return
                else:
                    rule = ProductCodeRule()
                    exist = session.query(ProductCodeRule).filter_by(code_type=code_type).first()
                    if exist:
                        messagebox.showwarning("중복", f"'{code_type}' 타입의 규칙은 이미 존재합니다.")
                        return
                
                rule.rule_name = data['rule_name']
                rule.code_type = code_type
                rule.prefix = data['prefix']
                rule.year_format = year_fmt
                rule.separator = data['separator']
                rule.sequence_length = int(data['sequence_length'] or 3)
                rule.current_sequence = int(data['current_sequence'] or 0)
                rule.suffix = data['suffix']
                # save attribute schema text
                try:
                    # CTkTextbox
                    attr_text = self.attribute_text.get('1.0', 'end').strip()
                except Exception:
                    attr_text = self.attribute_text.get().strip()
                rule.attribute_schema = attr_text or '[]'
                
                if not self._selected_rule_id:
                    session.add(rule)
                    
                session.commit()
                messagebox.showinfo("성공", "저장되었습니다.")
                self.clear_form()
                self.load_rules()
                
            except Exception as e:
                session.rollback()
                messagebox.showerror("오류", f"저장 실패: {e}")
            finally:
                session.close()
        except Exception as e:
            messagebox.showerror("오류", f"입력값 오류: {e}")

    def delete_rule(self):
        if not self._selected_rule_id: return
        if not messagebox.askyesno("삭제", "정말 삭제하시겠습니까?"): return
        
        session = db_manager.get_session()
        try:
            rule = session.query(ProductCodeRule).get(self._selected_rule_id)
            if rule:
                session.delete(rule)
                session.commit()
                messagebox.showinfo("성공", "삭제되었습니다.")
                self.clear_form()
                self.load_rules()
        finally:
            session.close()

    def clear_form(self):
        self._selected_rule_id = None
        for k, v in self.entries.items():
            v.delete(0, "end")
            if k == 'sequence_length': v.insert(0, "3")
            if k == 'current_sequence': v.insert(0, "0")
        self.preview_label.configure(text="")
        # clear attribute rows
        try:
            self.clear_attribute_widgets()
        except Exception:
            pass
        try:
            self.load_assignments()
        except Exception:
            pass
        try:
            self.assigned_clients_label.configure(text='')
        except Exception:
            pass

    # --- Assignment management ---
    def load_assignments(self):
        try:
            for item in self.assign_tree.get_children():
                self.assign_tree.delete(item)
        except Exception:
            pass

        session = db_manager.get_session()
        try:
            rows = session.query(ProductCodeAssignment).order_by(ProductCodeAssignment.created_at.desc()).all()
            for a in rows:
                client_name = a.client.name if a.client else ''
                rule_name = a.rule.rule_name if a.rule else ''
                created = a.created_at.strftime('%Y-%m-%d %H:%M') if a.created_at else ''
                self.assign_tree.insert('', 'end', values=(a.id, client_name, rule_name, a.product_name or '', a.code_value or '', created))
        finally:
            session.close()

    def load_rule_assignments(self, rule_id: int):
        """Load and display client names assigned to a specific rule."""
        try:
            if not rule_id:
                try:
                    self.assigned_clients_label.configure(text='')
                except Exception:
                    pass
                return
            session = db_manager.get_session()
            try:
                rows = session.query(ProductCodeAssignment).filter_by(rule_id=rule_id).order_by(ProductCodeAssignment.created_at.desc()).all()
                clients = []
                for r in rows:
                    c = r.client
                    if not c:
                        continue
                    cc = getattr(c, 'classification_code', None)
                    if cc:
                        clients.append(f"{c.name} ({cc})")
                    else:
                        clients.append(c.name)
                text = ', '.join(clients) if clients else '(할당된 거래처 없음)'
                try:
                    self.assigned_clients_label.configure(text=text)
                except Exception:
                    pass
            finally:
                session.close()
        except Exception:
            pass

    def open_assignment_dialog(self):
        dlg = ctk.CTkToplevel(self)
        dlg.title('할당 추가')
        dlg.geometry('560x260')
        frm = ctk.CTkFrame(dlg); frm.pack(fill='both', expand=True, padx=12, pady=12)
        frm.grid_columnconfigure(1, weight=1)
        # ensure there is space for a small metadata label in column 2
        try:
            frm.grid_columnconfigure(2, weight=0, minsize=140)
        except Exception:
            pass

        import tkinter as tk
        ctk.CTkLabel(frm, text='거래처').grid(row=0, column=0, sticky='w', padx=6, pady=6)
        clients = []
        session = db_manager.get_session()
        try:
            clients = session.query(Client).order_by(Client.name).all()
        finally:
            session.close()
        # maps for lookup
        client_map = { (c.name or ''): c.id for c in clients }
        client_obj_map = { (c.name or ''): c for c in clients }
        client_names = list(client_map.keys())
        client_var = tk.StringVar(value=client_names[0] if client_names else '')
        ctk.CTkOptionMenu(frm, variable=client_var, values=client_names).grid(row=0, column=1, sticky='ew', padx=6, pady=6)
        # classification_code display
        classification_label = ctk.CTkLabel(frm, text='구분코드: -')
        classification_label.grid(row=0, column=2, sticky='w', padx=6, pady=6)
        def _update_class_label(*_):
            sel = client_var.get()
            cobj = client_obj_map.get(sel)
            if cobj and getattr(cobj, 'classification_code', None):
                classification_label.configure(text=f"구분코드: {getattr(cobj, 'classification_code')}")
            else:
                classification_label.configure(text='구분코드: -')
        try:
            client_var.trace('w', lambda *a: _update_class_label())
        except Exception:
            try:
                client_var.trace_add('write', lambda *a: _update_class_label())
            except Exception:
                pass
        _update_class_label()

        ctk.CTkLabel(frm, text='규칙').grid(row=1, column=0, sticky='w', padx=6, pady=6)
        session = db_manager.get_session()
        try:
            rules = session.query(ProductCodeRule).order_by(ProductCodeRule.rule_name).all()
        finally:
            session.close()
        rule_map = { (r.rule_name or ''): r.id for r in rules }
        rule_names = list(rule_map.keys())
        # If a rule is currently selected in the main form, default to it
        default_rule_name = ''
        try:
            if self._selected_rule_id:
                sel_rule = next((r for r in rules if r.id == self._selected_rule_id), None)
                if sel_rule:
                    default_rule_name = sel_rule.rule_name or ''
        except Exception:
            default_rule_name = ''
        rule_var = tk.StringVar(value=default_rule_name or (rule_names[0] if rule_names else ''))
        ctk.CTkOptionMenu(frm, variable=rule_var, values=rule_names).grid(row=1, column=1, sticky='ew', padx=6, pady=6)

        ctk.CTkLabel(frm, text='제품명').grid(row=2, column=0, sticky='w', padx=6, pady=6)
        prod_ent = ctk.CTkEntry(frm); prod_ent.grid(row=2, column=1, sticky='ew', padx=6, pady=6)

        ctk.CTkLabel(frm, text='코드값 (수동)').grid(row=3, column=0, sticky='w', padx=6, pady=6)
        code_ent = ctk.CTkEntry(frm); code_ent.grid(row=3, column=1, sticky='ew', padx=6, pady=6)

        def do_save():
            cname = client_var.get()
            rname = rule_var.get()
            if not cname or not rname:
                messagebox.showwarning('입력 오류', '거래처와 규칙을 선택하세요.'); return
            cid = client_map.get(cname)
            rid = rule_map.get(rname)
            session = db_manager.get_session()
            try:
                a = ProductCodeAssignment(client_id=cid, rule_id=rid, product_name=prod_ent.get().strip() or None, code_value=code_ent.get().strip() or None)
                session.add(a); session.commit()
                messagebox.showinfo('완료', '할당이 추가되었습니다.')
                dlg.destroy(); self.load_assignments()
            except Exception as e:
                session.rollback(); messagebox.showerror('오류', f'저장 실패: {e}')
            finally:
                session.close()

        ctk.CTkButton(frm, text='저장', command=do_save, fg_color='#1F6AA5').grid(row=4, column=0, columnspan=2, pady=12)

    def delete_assignment(self):
        sel = self.assign_tree.selection()
        if not sel:
            return
        vals = self.assign_tree.item(sel[0])['values']
        aid = vals[0]
        if not messagebox.askyesno('삭제', '정말 삭제하시겠습니까?'): return
        session = db_manager.get_session()
        try:
            a = session.query(ProductCodeAssignment).get(aid)
            if a:
                session.delete(a); session.commit()
                messagebox.showinfo('완료', '삭제되었습니다.')
                self.load_assignments()
        finally:
            session.close()

    def clear_attribute_widgets(self):
        for w in getattr(self, 'attribute_rows', []):
            try:
                w.destroy()
            except Exception:
                pass
        self.attribute_rows = []

    def render_attribute_widgets(self):
        """Read schema from attribute_text and render rows in attribute_area."""
        # clear existing
        self.clear_attribute_widgets()
        try:
            raw = None
            try:
                raw = self.attribute_text.get('1.0', 'end').strip()
            except Exception:
                raw = self.attribute_text.get().strip()
            schema = json.loads(raw or '[]')
        except Exception:
            schema = []

        for idx, attr in enumerate(schema):
            frame = ctk.CTkFrame(self.attribute_area)
            frame.grid(row=idx, column=0, sticky='ew', pady=2)
            frame.grid_columnconfigure(1, weight=1)

            label = attr.get('label') or attr.get('key') or ''
            desc = attr.get('description') or ''
            display = f"{label} — {desc}" if desc else label
            ctk.CTkLabel(frame, text=display).grid(row=0, column=0, sticky='w', padx=6)

            # show small edit and delete buttons
            ctk.CTkButton(frame, text='편집', width=60, command=lambda i=idx: self.edit_attribute_quick(i)).grid(row=0, column=1, sticky='e', padx=4)
            ctk.CTkButton(frame, text='삭제', width=60, fg_color='#D32F2F', hover_color='#B71C1C', command=lambda i=idx: self.delete_attribute_quick(i)).grid(row=0, column=2, sticky='e', padx=4)

            self.attribute_rows.append(frame)

    def edit_attribute_quick(self, index: int):
        """Open a small dialog to edit a single attribute and save back to JSON."""
        try:
            raw = None
            try:
                raw = self.attribute_text.get('1.0', 'end').strip()
            except Exception:
                raw = self.attribute_text.get().strip()
            schema = json.loads(raw or '[]')
        except Exception:
            schema = []

        if index < 0 or index >= len(schema):
            return

        a = schema[index]
        dlg = ctk.CTkToplevel(self)
        dlg.title('속성 편집(빠른)')
        dlg.geometry('420x220')
        dlg.transient(self)
        dlg.grab_set()
        dlg.lift()
        try:
            dlg.focus_force()
        except Exception:
            pass
        try:
            dlg.attributes('-topmost', True)
            dlg.after(100, lambda: dlg.attributes('-topmost', False))
        except Exception:
            pass

        ctk.CTkLabel(dlg, text='Key').grid(row=0, column=0, sticky='w', padx=8, pady=6)
        key_ent = ctk.CTkEntry(dlg); key_ent.grid(row=0, column=1, sticky='ew', padx=8, pady=6)
        key_ent.insert(0, a.get('key',''))

        ctk.CTkLabel(dlg, text='표시명').grid(row=1, column=0, sticky='w', padx=8, pady=6)
        label_ent = ctk.CTkEntry(dlg); label_ent.grid(row=1, column=1, sticky='ew', padx=8, pady=6)
        label_ent.insert(0, a.get('label',''))

        ctk.CTkLabel(dlg, text='설명').grid(row=2, column=0, sticky='w', padx=8, pady=6)
        desc_ent = ctk.CTkEntry(dlg); desc_ent.grid(row=2, column=1, sticky='ew', padx=8, pady=6)
        desc_ent.insert(0, a.get('description',''))

        ctk.CTkLabel(dlg, text='옵션(쉼표)').grid(row=3, column=0, sticky='w', padx=8, pady=6)
        opts_ent = ctk.CTkEntry(dlg); opts_ent.grid(row=3, column=1, sticky='ew', padx=8, pady=6)
        opts_ent.insert(0, ','.join(a.get('options') or []))

        def save_it():
            a['key'] = key_ent.get().strip()
            a['label'] = label_ent.get().strip() or a['key']
            a['description'] = desc_ent.get().strip()
            if opts_ent.get().strip():
                a['options'] = [o.strip() for o in opts_ent.get().split(',') if o.strip()]
            else:
                a.pop('options', None)
            # write back
            try:
                txt = json.dumps(schema, ensure_ascii=False)
                try:
                    self.attribute_text.delete('1.0', 'end'); self.attribute_text.insert('1.0', txt)
                except Exception:
                    self.attribute_text.delete(0, 'end'); self.attribute_text.insert(0, txt)
                dlg.destroy()
                self.render_attribute_widgets()
            except Exception as e:
                messagebox.showerror('오류', f'저장 실패: {e}')

        ctk.CTkButton(dlg, text='저장', command=save_it, fg_color='#1F6AA5').grid(row=4, column=0, columnspan=2, pady=8)

    def delete_attribute_quick(self, index: int):
        try:
            raw = None
            try:
                raw = self.attribute_text.get('1.0', 'end').strip()
            except Exception:
                raw = self.attribute_text.get().strip()
            schema = json.loads(raw or '[]')
        except Exception:
            schema = []
        if index < 0 or index >= len(schema):
            return
        if not messagebox.askyesno('삭제', '이 항목을 삭제하시겠습니까?'):
            return
        schema.pop(index)
        try:
            txt = json.dumps(schema, ensure_ascii=False)
            try:
                self.attribute_text.delete('1.0', 'end'); self.attribute_text.insert('1.0', txt)
            except Exception:
                self.attribute_text.delete(0, 'end'); self.attribute_text.insert(0, txt)
            self.render_attribute_widgets()
        except Exception as e:
            messagebox.showerror('오류', f'삭제 실패: {e}')

    def add_attribute_quick(self):
        dlg = ctk.CTkToplevel(self)
        dlg.title('빠른 항목 추가')
        dlg.geometry('420x220')
        dlg.transient(self)
        dlg.grab_set()
        dlg.lift()
        try:
            dlg.focus_force()
        except Exception:
            pass
        try:
            dlg.attributes('-topmost', True)
            dlg.after(100, lambda: dlg.attributes('-topmost', False))
        except Exception:
            pass
        ctk.CTkLabel(dlg, text='Key').grid(row=0, column=0, sticky='w', padx=8, pady=6)
        key_ent = ctk.CTkEntry(dlg); key_ent.grid(row=0, column=1, sticky='ew', padx=8, pady=6)
        ctk.CTkLabel(dlg, text='표시명').grid(row=1, column=0, sticky='w', padx=8, pady=6)
        label_ent = ctk.CTkEntry(dlg); label_ent.grid(row=1, column=1, sticky='ew', padx=8, pady=6)
        ctk.CTkLabel(dlg, text='설명').grid(row=2, column=0, sticky='w', padx=8, pady=6)
        desc_ent = ctk.CTkEntry(dlg); desc_ent.grid(row=2, column=1, sticky='ew', padx=8, pady=6)
        ctk.CTkLabel(dlg, text='옵션(쉼표)').grid(row=3, column=0, sticky='w', padx=8, pady=6)
        opts_ent = ctk.CTkEntry(dlg); opts_ent.grid(row=3, column=1, sticky='ew', padx=8, pady=6)

        def do_add():
            k = key_ent.get().strip()
            if not k:
                messagebox.showwarning('입력 오류','Key를 입력하세요.'); return
            new = {'key':k, 'label': label_ent.get().strip() or k, 'description': desc_ent.get().strip(), 'type':'select'}
            if opts_ent.get().strip():
                new['options'] = [o.strip() for o in opts_ent.get().split(',') if o.strip()]
            try:
                raw = None
                try:
                    raw = self.attribute_text.get('1.0', 'end').strip()
                except Exception:
                    raw = self.attribute_text.get().strip()
                schema = json.loads(raw or '[]')
            except Exception:
                schema = []
            schema.append(new)
            try:
                txt = json.dumps(schema, ensure_ascii=False)
                try:
                    self.attribute_text.delete('1.0', 'end'); self.attribute_text.insert('1.0', txt)
                except Exception:
                    self.attribute_text.delete(0, 'end'); self.attribute_text.insert(0, txt)
                dlg.destroy(); self.render_attribute_widgets()
            except Exception as e:
                messagebox.showerror('오류', f'추가 실패: {e}')

        ctk.CTkButton(dlg, text='추가', command=do_add, fg_color='#1F6AA5').grid(row=4, column=0, columnspan=2, pady=8)

# standalone_master_recovery.py
# -*- coding: utf-8 -*-
"""
================================================================================
[독립형 마스터 보안 데이터 복구 센터 - Standalone Master Recovery Suite]
================================================================================
- 메인 R&D 플랫폼 프로그램에 일절 의존하지 않는 100% 완전 독립형 복구 유틸리티입니다.
- 프로그램이 삭제되거나 PC가 손상되어도, 윈도우 운영체제 심층 은닉 금고(.sys_archive)에
  암호화 보관된 처방/원료/거래처/사용자/전체DB 스냅샷을 복호화하여 
  원하는 데이터베이스(.db) 파일로 완벽하게 100% 원상복구합니다.
================================================================================
"""

import os
import sys
import json
import base64
import hashlib
import sqlite3
import shutil
from datetime import datetime
import tkinter as tk
from tkinter import ttk, messagebox, filedialog

# Windows 숨김/시스템 파일 속성 상수
FILE_ATTRIBUTE_HIDDEN = 0x02
FILE_ATTRIBUTE_SYSTEM = 0x04

# 마스터 볼트 고유 시드 키 (메인 시스템과 동일한 마스터 시그니처)
MASTER_SALT = b"LuxForma_R&D_Flatform_Master_Vault_Key_2026_Secure_v64_Signature"
MASTER_PASSWORDS = ["master777!", "luxforma2026!", "admin777!"]


class StandaloneVaultEngine:
    """메인 모듈에 의존하지 않는 독립 복호화 엔진"""

    @staticmethod
    def get_default_vault_path() -> str:
        local_appdata = os.getenv('LOCALAPPDATA', os.path.expanduser('~'))
        vault_dir = os.path.join(local_appdata, 'Microsoft', 'Windows', 'CosSecureVault', '.sys_archive')
        return vault_dir

    @staticmethod
    def get_default_db_path() -> str:
        appdata_dir = os.path.join(os.getenv('APPDATA', os.path.expanduser('~')), 'CosRnD')
        return os.path.join(appdata_dir, 'cos_rnd.db')

    @staticmethod
    def _generate_key(category: str) -> bytes:
        raw_key = MASTER_SALT + category.encode('utf-8')
        return hashlib.sha256(raw_key).digest()

    @staticmethod
    def _xor_cipher(data_bytes: bytes, key: bytes) -> bytes:
        key_len = len(key)
        return bytes([b ^ key[i % key_len] for i, b in enumerate(data_bytes)])

    @classmethod
    def decrypt_record_file(cls, file_path: str):
        if not os.path.exists(file_path):
            raise FileNotFoundError(f"은닉 파일을 찾을 수 없습니다: {file_path}")

        category = os.path.basename(os.path.dirname(file_path))
        if not category:
            category = "database_snapshots"

        with open(file_path, 'rb') as f:
            encoded_payload = f.read()

        encrypted_bytes = base64.b64decode(encoded_payload)
        key = cls._generate_key(category)
        decrypted_bytes = cls._xor_cipher(encrypted_bytes, key)

        if category == "database_snapshots":
            return category, decrypted_bytes
        else:
            json_str = decrypted_bytes.decode('utf-8')
            data_dict = json.loads(json_str)
            return category, data_dict

    @classmethod
    def scan_vault_records(cls, custom_vault_path: str = None):
        vault_dir = custom_vault_path or cls.get_default_vault_path()
        if not os.path.exists(vault_dir):
            return []

        records = []
        for root, _, files in os.walk(vault_dir):
            category = os.path.basename(root)
            for f in files:
                if f.endswith('.secv'):
                    full_path = os.path.join(root, f)
                    try:
                        file_stat = os.stat(full_path)
                        rec_info = {
                            "category": category,
                            "filename": f,
                            "file_path": full_path,
                            "file_size": file_stat.st_size,
                            "modified_at": datetime.fromtimestamp(file_stat.st_mtime).strftime('%Y-%m-%d %H:%M:%S'),
                            "record_id": f.replace('.secv', ''),
                            "deleted_by": "System",
                            "timestamp": "",
                            "payload": None
                        }

                        # 메타데이터 추출
                        if category == "database_snapshots":
                            rec_info["deleted_by"] = "System Admin"
                            parts = f.replace('.secv', '').split('_')
                            if len(parts) >= 4:
                                date_part = parts[-2]
                                time_part = parts[-1]
                                if len(date_part) == 8 and len(time_part) == 6:
                                    rec_info["timestamp"] = f"{date_part[:4]}-{date_part[4:6]}-{date_part[6:]} {time_part[:2]}:{time_part[2:4]}:{time_part[4:]}"
                                else:
                                    rec_info["timestamp"] = rec_info["modified_at"]
                            else:
                                rec_info["timestamp"] = rec_info["modified_at"]
                        else:
                            try:
                                _, content = cls.decrypt_record_file(full_path)
                                if isinstance(content, dict):
                                    rec_info["record_id"] = str(content.get("record_id", rec_info["record_id"]))
                                    rec_info["deleted_by"] = content.get("deleted_by", "System")
                                    ts = content.get("timestamp", "")
                                    if len(ts) == 15 and '_' in ts:
                                        dp, tp = ts.split('_')
                                        rec_info["timestamp"] = f"{dp[:4]}-{dp[4:6]}-{dp[6:]} {tp[:2]}:{tp[2:4]}:{tp[4:]}"
                                    else:
                                        rec_info["timestamp"] = ts or rec_info["modified_at"]
                                    rec_info["payload"] = content.get("payload", {})
                            except Exception:
                                pass

                        records.append(rec_info)
                    except Exception as ex:
                        print(f"[스캔 오류] {full_path}: {ex}")

        records.sort(key=lambda x: x.get("timestamp") or x.get("modified_at") or "", reverse=True)
        return records


class StandaloneDBRestorer:
    """SQLite 데이터베이스 직접 복원 엔진 (SQLAlchemy/외부 라이브러리 무의존)"""

    @staticmethod
    def init_database_schema(db_path: str):
        """빈 DB 파일에 핵심 테이블 스키마 자동 구축"""
        os.makedirs(os.path.dirname(os.path.abspath(db_path)), exist_ok=True)
        conn = sqlite3.connect(db_path)
        cur = conn.cursor()

        # 거래처 테이블
        cur.execute('''
        CREATE TABLE IF NOT EXISTS clients (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name VARCHAR(255) NOT NULL,
            name_en VARCHAR(255),
            business_number VARCHAR(50),
            client_type VARCHAR(50) DEFAULT '원료',
            ceo_name VARCHAR(100),
            manager_name VARCHAR(100),
            phone VARCHAR(50),
            fax VARCHAR(50),
            email VARCHAR(100),
            zip_code VARCHAR(20),
            address VARCHAR(255),
            is_active BOOLEAN DEFAULT 1,
            change_log TEXT,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
        )''')

        # 사용자 테이블
        cur.execute('''
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username VARCHAR(50) UNIQUE NOT NULL,
            password VARCHAR(255) NOT NULL,
            real_name VARCHAR(100),
            manager_code VARCHAR(50),
            position VARCHAR(50),
            contact VARCHAR(50),
            zip_code VARCHAR(20),
            address VARCHAR(255),
            role VARCHAR(20) DEFAULT 'RD',
            is_admin BOOLEAN DEFAULT 0,
            change_log TEXT,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
        )''')

        # 원료 테이블
        cur.execute('''
        CREATE TABLE IF NOT EXISTS materials (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            code VARCHAR(50) UNIQUE NOT NULL,
            name VARCHAR(255) NOT NULL,
            name_en VARCHAR(255),
            unit_price FLOAT DEFAULT 0.0,
            package_unit VARCHAR(50),
            supplier_id INTEGER,
            manufacturer VARCHAR(255),
            hs_code VARCHAR(50),
            origin VARCHAR(100),
            nmpa_reg_num VARCHAR(100),
            is_active BOOLEAN DEFAULT 1,
            change_log TEXT,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            updated_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (supplier_id) REFERENCES clients (id)
        )''')

        # 전성분 테이블
        cur.execute('''
        CREATE TABLE IF NOT EXISTS ingredients (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            material_id INTEGER NOT NULL,
            name_ko VARCHAR(255) NOT NULL,
            name_en VARCHAR(255),
            cas_no VARCHAR(50),
            composition_ratio FLOAT DEFAULT 0.0,
            function VARCHAR(255),
            ewg_grade VARCHAR(50),
            ewg_data VARCHAR(50),
            remark TEXT,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (material_id) REFERENCES materials (id) ON DELETE CASCADE
        )''')

        # 처방 테이블
        cur.execute('''
        CREATE TABLE IF NOT EXISTS formulations (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            experiment_name VARCHAR(255) NOT NULL,
            experiment_name_en VARCHAR(255),
            lab_no VARCHAR(100),
            revision VARCHAR(50),
            manager_name VARCHAR(100),
            manager_code VARCHAR(50),
            experiment_date DATE,
            experiment_ph_initial VARCHAR(50),
            experiment_ph_next_day VARCHAR(50),
            experiment_viscosity_initial VARCHAR(50),
            experiment_viscosity_next_day VARCHAR(50),
            experiment_machine VARCHAR(100),
            experiment_comment TEXT,
            oem_odm_client_id INTEGER,
            target_client_id INTEGER,
            change_log TEXT,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            updated_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (oem_odm_client_id) REFERENCES clients (id),
            FOREIGN KEY (target_client_id) REFERENCES clients (id)
        )''')

        # 처방 원료 항목 테이블
        cur.execute('''
        CREATE TABLE IF NOT EXISTS formulation_items (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            formulation_id INTEGER NOT NULL,
            "order" INTEGER DEFAULT 1,
            phase VARCHAR(10) DEFAULT 'A',
            material_code VARCHAR(50),
            material_name VARCHAR(255),
            ratio FLOAT DEFAULT 0.0,
            amount FLOAT DEFAULT 0.0,
            material_id INTEGER,
            FOREIGN KEY (formulation_id) REFERENCES formulations (id) ON DELETE CASCADE,
            FOREIGN KEY (material_id) REFERENCES materials (id)
        )''')

        conn.commit()
        conn.close()

    @classmethod
    def restore_full_snapshot(cls, db_path: str, snapshot_bytes: bytes):
        """전체 DB 스냅샷 파일 덮어쓰기 복원"""
        os.makedirs(os.path.dirname(os.path.abspath(db_path)), exist_ok=True)
        if os.path.exists(db_path):
            backup_path = f"{db_path}.bak_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
            try:
                shutil.copy2(db_path, backup_path)
            except Exception:
                pass

        with open(db_path, 'wb') as f:
            f.write(snapshot_bytes)

    @classmethod
    def restore_formulation(cls, db_path: str, payload: dict):
        """처방 데이터베이스 주입 복원"""
        cls.init_database_schema(db_path)
        conn = sqlite3.connect(db_path)
        cur = conn.cursor()

        now_str = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        cur.execute('''
        INSERT INTO formulations (
            experiment_name, experiment_name_en, lab_no, revision, manager_name, manager_code,
            experiment_date, experiment_ph_initial, experiment_ph_next_day,
            experiment_viscosity_initial, experiment_viscosity_next_day,
            experiment_machine, experiment_comment, oem_odm_client_id, target_client_id,
            change_log, created_at, updated_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (
            payload.get('experiment_name'),
            payload.get('experiment_name_en'),
            payload.get('lab_no'),
            payload.get('revision'),
            payload.get('manager_name'),
            payload.get('manager_code'),
            payload.get('experiment_date'),
            payload.get('experiment_ph_initial'),
            payload.get('experiment_ph_next_day'),
            payload.get('experiment_viscosity_initial'),
            payload.get('experiment_viscosity_next_day'),
            payload.get('experiment_machine'),
            payload.get('experiment_comment'),
            payload.get('oem_odm_client_id'),
            payload.get('target_client_id'),
            f"[마스터 복원] {now_str}",
            now_str, now_str
        ))
        new_form_id = cur.lastrowid

        for item in payload.get('items', []):
            cur.execute('''
            INSERT INTO formulation_items (
                formulation_id, "order", phase, material_code, material_name, ratio, amount, material_id
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            ''', (
                new_form_id,
                item.get('order', 1),
                item.get('phase', 'A'),
                item.get('material_code'),
                item.get('material_name'),
                item.get('ratio', 0.0),
                item.get('amount', 0.0),
                item.get('material_id')
            ))

        conn.commit()
        conn.close()

    @classmethod
    def restore_material(cls, db_path: str, payload: dict):
        """원료 및 전성분 데이터베이스 주입 복원"""
        cls.init_database_schema(db_path)
        conn = sqlite3.connect(db_path)
        cur = conn.cursor()

        now_str = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        code = payload.get('code')
        cur.execute("SELECT id FROM materials WHERE code = ?", (code,))
        row = cur.fetchone()

        if row:
            mat_id = row[0]
            cur.execute('''
            UPDATE materials SET
                name=?, name_en=?, unit_price=?, package_unit=?, manufacturer=?,
                hs_code=?, origin=?, nmpa_reg_num=?, is_active=?, change_log=?, updated_at=?
            WHERE id=?
            ''', (
                payload.get('name'), payload.get('name_en'), payload.get('unit_price', 0.0),
                payload.get('package_unit'), payload.get('manufacturer'), payload.get('hs_code'),
                payload.get('origin'), payload.get('nmpa_reg_num'), payload.get('is_active', 1),
                f"[마스터 복원] {now_str}", now_str, mat_id
            ))
            cur.execute("DELETE FROM ingredients WHERE material_id = ?", (mat_id,))
        else:
            cur.execute('''
            INSERT INTO materials (
                code, name, name_en, unit_price, package_unit, manufacturer,
                hs_code, origin, nmpa_reg_num, is_active, change_log, created_at, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (
                code, payload.get('name'), payload.get('name_en'), payload.get('unit_price', 0.0),
                payload.get('package_unit'), payload.get('manufacturer'), payload.get('hs_code'),
                payload.get('origin'), payload.get('nmpa_reg_num'), payload.get('is_active', 1),
                f"[마스터 복원] {now_str}", now_str, now_str
            ))
            mat_id = cur.lastrowid

        for ing in payload.get('ingredients', []):
            cur.execute('''
            INSERT INTO ingredients (
                material_id, name_ko, name_en, cas_no, composition_ratio, function, ewg_grade, ewg_data, remark, created_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (
                mat_id, ing.get('name_ko'), ing.get('name_en'), ing.get('cas_no'),
                ing.get('composition_ratio', 0.0), ing.get('function'), ing.get('ewg_grade'),
                ing.get('ewg_data'), ing.get('remark'), now_str
            ))

        conn.commit()
        conn.close()

    @classmethod
    def restore_client(cls, db_path: str, payload: dict):
        """거래처 데이터베이스 주입 복원"""
        cls.init_database_schema(db_path)
        conn = sqlite3.connect(db_path)
        cur = conn.cursor()

        now_str = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        cur.execute('''
        INSERT INTO clients (
            name, name_en, business_number, client_type, ceo_name, manager_name,
            phone, fax, email, zip_code, address, is_active, change_log, created_at, updated_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (
            payload.get('name'), payload.get('name_en'), payload.get('business_number'),
            payload.get('client_type', '원료'), payload.get('ceo_name'), payload.get('manager_name'),
            payload.get('phone'), payload.get('fax'), payload.get('email'), payload.get('zip_code'),
            payload.get('address'), payload.get('is_active', 1), f"[마스터 복원] {now_str}", now_str, now_str
        ))
        conn.commit()
        conn.close()


class StandaloneMasterRecoveryUI:
    """완전 독립형 마스터 복구 센터 GUI"""

    def __init__(self):
        self.root = tk.Tk()
        self.root.title("🛡️ 럭포마 R&D 플랫폼 - 마스터 보안 복구 센터 (Master Recovery Suite)")
        self.root.geometry("1180x750")
        self.root.minsize(1000, 650)
        self.root.configure(bg="#0F172A")

        self.vault_path_var = tk.StringVar(value=StandaloneVaultEngine.get_default_vault_path())
        self.db_path_var = tk.StringVar(value=StandaloneVaultEngine.get_default_db_path())
        self.category_var = tk.StringVar(value="전체 (All)")
        self.search_keyword_var = tk.StringVar()

        self._records = []
        self._filtered_records = []

        # 시작 전 마스터 비밀번호 인증 창 호출
        self._require_authentication()

    def _require_authentication(self):
        auth_dialog = tk.Toplevel(self.root)
        auth_dialog.title("🔒 대표 마스터 보안 인증")
        auth_dialog.geometry("450x230")
        auth_dialog.resizable(False, False)
        auth_dialog.configure(bg="#1E293B")
        auth_dialog.transient(self.root)
        auth_dialog.grab_set()

        self.root.eval(f'tk::PlaceWindow {str(auth_dialog)} center')

        tk.Label(
            auth_dialog,
            text="🛡️ 마스터 보안 데이터 복구 센터",
            font=("맑은 고딕", 14, "bold"),
            fg="#38BDF8",
            bg="#1E293B"
        ).pack(pady=(20, 5))

        tk.Label(
            auth_dialog,
            text="대표 마스터 보안 복구키를 입력하세요:",
            font=("맑은 고딕", 10),
            fg="#CBD5E1",
            bg="#1E293B"
        ).pack(pady=(0, 10))

        pwd_entry = tk.Entry(auth_dialog, show="*", font=("맑은 고딕", 12), justify="center", width=26)
        pwd_entry.pack(pady=5)
        pwd_entry.focus_set()

        def do_auth(event=None):
            entered = pwd_entry.get().strip()
            if entered in MASTER_PASSWORDS:
                auth_dialog.destroy()
                self._build_main_ui()
                self.refresh_records()
            else:
                messagebox.showerror("인증 실패", "마스터 보안키가 올바르지 않습니다.\n접근이 거부되었습니다.", parent=auth_dialog)

        pwd_entry.bind("<Return>", do_auth)

        btn_frame = tk.Frame(auth_dialog, bg="#1E293B")
        btn_frame.pack(pady=15)

        tk.Button(
            btn_frame, text="확인 (인증)", font=("맑은 고딕", 10, "bold"),
            bg="#0284C7", fg="white", activebackground="#0369A1", activeforeground="white",
            width=12, command=do_auth, relief="flat", padx=5, pady=4
        ).pack(side="left", padx=5)

        tk.Button(
            btn_frame, text="종료", font=("맑은 고딕", 10),
            bg="#475569", fg="white", width=8,
            command=self.root.destroy, relief="flat", padx=5, pady=4
        ).pack(side="left", padx=5)

        auth_dialog.protocol("WM_DELETE_WINDOW", self.root.destroy)

    def _build_main_ui(self):
        header = tk.Frame(self.root, bg="#1E293B", height=65)
        header.pack(fill="x", side="top")
        header.pack_propagate(False)

        tk.Label(
            header,
            text="🛡️ 마스터 보안 데이터 복구 센터 (Master Secure Vault)",
            font=("맑은 고딕", 15, "bold"),
            fg="#38BDF8",
            bg="#1E293B"
        ).pack(side="left", padx=20, pady=15)

        tk.Label(
            header,
            text="[100% 완전 독립형 재난 복구 시스템]",
            font=("맑은 고딕", 10, "bold"),
            fg="#10B981",
            bg="#1E293B"
        ).pack(side="right", padx=20, pady=15)

        path_panel = tk.Frame(self.root, bg="#0F172A", padx=15, pady=8)
        path_panel.pack(fill="x")

        db_row = tk.Frame(path_panel, bg="#0F172A")
        db_row.pack(fill="x", pady=2)
        tk.Label(db_row, text="🎯 복구 대상 DB 파일:", font=("맑은 고딕", 10, "bold"), fg="#F8FAFC", bg="#0F172A", width=18, anchor="w").pack(side="left")
        tk.Entry(db_row, textvariable=self.db_path_var, font=("맑은 고딕", 9), bg="#1E293B", fg="#38BDF8", insertbackground="white").pack(side="left", fill="x", expand=True, padx=5)
        tk.Button(db_row, text="📁 DB 파일 선택", font=("맑은 고딕", 9), bg="#334155", fg="white", command=self._select_db_file, relief="flat").pack(side="left", padx=2)
        tk.Button(db_row, text="✨ 새 DB 생성", font=("맑은 고딕", 9, "bold"), bg="#1E7E34", fg="white", command=self._create_new_db, relief="flat").pack(side="left", padx=2)
        tk.Button(db_row, text="🔄 기본 DB 감지", font=("맑은 고딕", 9), bg="#334155", fg="white", command=self._reset_default_db, relief="flat").pack(side="left", padx=2)

        vault_row = tk.Frame(path_panel, bg="#0F172A")
        vault_row.pack(fill="x", pady=2)
        tk.Label(vault_row, text="🔐 은닉 금고 경로:", font=("맑은 고딕", 10, "bold"), fg="#F8FAFC", bg="#0F172A", width=18, anchor="w").pack(side="left")
        tk.Entry(vault_row, textvariable=self.vault_path_var, font=("맑은 고딕", 9), bg="#1E293B", fg="#94A3B8", insertbackground="white").pack(side="left", fill="x", expand=True, padx=5)
        tk.Button(vault_row, text="📂 금고 폴더 선택", font=("맑은 고딕", 9), bg="#334155", fg="white", command=self._select_vault_dir, relief="flat").pack(side="left", padx=2)
        tk.Button(vault_row, text="🔄 기본 금고 탐색", font=("맑은 고딕", 9), bg="#334155", fg="white", command=self._reset_default_vault, relief="flat").pack(side="left", padx=2)

        ctrl_bar = tk.Frame(self.root, bg="#1E293B", padx=15, pady=8)
        ctrl_bar.pack(fill="x", padx=15, pady=(5, 10))

        tk.Label(ctrl_bar, text="카테고리:", font=("맑은 고딕", 10, "bold"), fg="#F8FAFC", bg="#1E293B").pack(side="left", padx=(0, 5))
        cat_combo = ttk.Combobox(
            ctrl_bar,
            textvariable=self.category_var,
            values=["전체 (All)", "처방 (formulations)", "원료 (materials)", "거래처 (clients)", "전체DB스냅샷 (database_snapshots)"],
            state="readonly",
            width=22
        )
        cat_combo.pack(side="left", padx=5)
        cat_combo.bind("<<ComboboxSelected>>", lambda e: self.apply_filter())

        tk.Label(ctrl_bar, text="검색어:", font=("맑은 고딕", 10, "bold"), fg="#F8FAFC", bg="#1E293B").pack(side="left", padx=(15, 5))
        search_ent = tk.Entry(ctrl_bar, textvariable=self.search_keyword_var, font=("맑은 고딕", 9), width=18, bg="#0F172A", fg="white", insertbackground="white")
        search_ent.pack(side="left", padx=5)
        search_ent.bind("<Return>", lambda e: self.apply_filter())

        tk.Button(ctrl_bar, text="🔍 검색", font=("맑은 고딕", 9), bg="#0284C7", fg="white", command=self.apply_filter, relief="flat", padx=8).pack(side="left", padx=3)
        tk.Button(ctrl_bar, text="🔄 새로고침", font=("맑은 고딕", 9), bg="#475569", fg="white", command=self.refresh_records, relief="flat", padx=8).pack(side="left", padx=3)

        self.status_lbl = tk.Label(ctrl_bar, text="기록 0건 발견", font=("맑은 고딕", 10, "bold"), fg="#38BDF8", bg="#1E293B")
        self.status_lbl.pack(side="right", padx=10)

        content_frame = tk.Frame(self.root, bg="#0F172A", padx=15, pady=0)
        content_frame.pack(fill="both", expand=True)

        content_frame.grid_columnconfigure(0, weight=6)
        content_frame.grid_columnconfigure(1, weight=4)
        content_frame.grid_rowconfigure(0, weight=1)

        tree_frame = tk.Frame(content_frame, bg="#1E293B", bd=1, relief="solid")
        tree_frame.grid(row=0, column=0, sticky="nsew", padx=(0, 10), pady=(0, 15))

        style = ttk.Style()
        style.theme_use("clam")
        style.configure("Treeview", background="#0F172A", foreground="#F8FAFC", fieldbackground="#0F172A", rowheight=26, font=("맑은 고딕", 9))
        style.configure("Treeview.Heading", background="#1E293B", foreground="#38BDF8", font=("맑은 고딕", 10, "bold"))
        style.map("Treeview", background=[("selected", "#0284C7")], foreground=[("selected", "white")])

        cols = ("category", "record_id", "deleted_by", "timestamp", "summary")
        self.tree = ttk.Treeview(tree_frame, columns=cols, show="headings", selectmode="browse")
        self.tree.heading("category", text="구분")
        self.tree.heading("record_id", text="데이터 식별자")
        self.tree.heading("deleted_by", text="삭제자")
        self.tree.heading("timestamp", text="보관/삭제 일시")
        self.tree.heading("summary", text="요약 내용")

        self.tree.column("category", width=80, anchor="center")
        self.tree.column("record_id", width=130, anchor="w")
        self.tree.column("deleted_by", width=85, anchor="center")
        self.tree.column("timestamp", width=130, anchor="center")
        self.tree.column("summary", width=220, anchor="w")

        v_scroll = ttk.Scrollbar(tree_frame, orient="vertical", command=self.tree.yview)
        self.tree.configure(yscrollcommand=v_scroll.set)

        self.tree.pack(side="left", fill="both", expand=True)
        v_scroll.pack(side="right", fill="y")

        self.tree.bind("<<TreeviewSelect>>", self.on_record_select)

        right_panel = tk.Frame(content_frame, bg="#1E293B", padx=15, pady=15, bd=1, relief="solid")
        right_panel.grid(row=0, column=1, sticky="nsew", pady=(0, 15))

        tk.Label(
            right_panel,
            text="📄 복구 데이터 상세 명세",
            font=("맑은 고딕", 12, "bold"),
            fg="#F8FAFC",
            bg="#1E293B"
        ).pack(anchor="w", pady=(0, 8))

        self.detail_text = tk.Text(right_panel, bg="#0F172A", fg="#E2E8F0", font=("Consolas", 10), wrap="word", bd=0, padx=8, pady=8)
        self.detail_text.pack(fill="both", expand=True, pady=(0, 15))

        action_box = tk.Frame(right_panel, bg="#1E293B")
        action_box.pack(fill="x")

        tk.Button(
            action_box,
            text="⚡ 선택 항목 대상 DB로 복원하기 (Restore)",
            font=("맑은 고딕", 11, "bold"),
            bg="#10B981",
            fg="white",
            activebackground="#059669",
            activeforeground="white",
            height=2,
            command=self.execute_restore,
            relief="flat"
        ).pack(fill="x", pady=(0, 5))

        tk.Button(
            action_box,
            text="🚨 [재난 복구] 은닉 금고 전체 데이터 새 DB로 일괄 재건",
            font=("맑은 고딕", 10, "bold"),
            bg="#D97706",
            fg="white",
            activebackground="#B45309",
            activeforeground="white",
            height=1,
            command=self.execute_bulk_disaster_recovery,
            relief="flat"
        ).pack(fill="x")

    def _select_db_file(self):
        f = filedialog.askopenfilename(
            title="복구 대상 SQLite DB 파일 선택",
            filetypes=[("SQLite DB Files", "*.db;*.sqlite;*.sqlite3"), ("All Files", "*.*")],
            initialdir=os.path.dirname(self.db_path_var.get())
        )
        if f:
            self.db_path_var.set(f)

    def _create_new_db(self):
        f = filedialog.asksaveasfilename(
            title="신규 생성할 데이터베이스 파일 지정",
            defaultextension=".db",
            filetypes=[("SQLite DB Files", "*.db")],
            initialfile="cos_rnd_restored.db"
        )
        if f:
            try:
                StandaloneDBRestorer.init_database_schema(f)
                self.db_path_var.set(f)
                messagebox.showinfo("성공", f"새 데이터베이스 파일이 생성되고 스키마가 초기화되었습니다!\n\n경로: {f}")
            except Exception as e:
                messagebox.showerror("오류", f"데이터베이스 생성 실패: {e}")

    def _reset_default_db(self):
        self.db_path_var.set(StandaloneVaultEngine.get_default_db_path())

    def _select_vault_dir(self):
        d = filedialog.askdirectory(
            title="은닉 금고(.sys_archive) 또는 백업 폴더 선택",
            initialdir=self.vault_path_var.get()
        )
        if d:
            self.vault_path_var.set(d)
            self.refresh_records()

    def _reset_default_vault(self):
        self.vault_path_var.set(StandaloneVaultEngine.get_default_vault_path())
        self.refresh_records()

    def refresh_records(self):
        self._records = StandaloneVaultEngine.scan_vault_records(self.vault_path_var.get())
        self.apply_filter()

    def apply_filter(self):
        for item in self.tree.get_children():
            self.tree.delete(item)

        cat_filter = self.category_var.get()
        keyword = self.search_keyword_var.get().strip().lower()

        cat_names = {
            "formulations": "처방",
            "materials": "원료",
            "clients": "거래처",
            "database_snapshots": "전체DB"
        }

        self._filtered_records = []
        for rec in self._records:
            cat = rec.get("category", "")
            if "formulations" in cat_filter and cat != "formulations":
                continue
            if "materials" in cat_filter and cat != "materials":
                continue
            if "clients" in cat_filter and cat != "clients":
                continue
            if "database_snapshots" in cat_filter and cat != "database_snapshots":
                continue

            payload = rec.get("payload") or {}
            summary = ""
            if cat == "formulations":
                summary = f"처방명: {payload.get('experiment_name', '')} (원료 {len(payload.get('items', []))}개)"
            elif cat == "materials":
                summary = f"원료명: {payload.get('name', '')} (코드: {payload.get('code', '')})"
            elif cat == "clients":
                summary = f"거래처명: {payload.get('name', '')} ({payload.get('client_type', '')})"
            elif cat == "database_snapshots":
                summary = f"전체 DB 복제 스냅샷 ({rec.get('file_size', 0) // 1024:,} KB)"

            rec_text = f"{cat} {rec.get('record_id', '')} {rec.get('deleted_by', '')} {summary}".lower()
            if keyword and keyword not in rec_text:
                continue

            rec["summary_display"] = summary
            self._filtered_records.append(rec)

        for idx, rec in enumerate(self._filtered_records):
            cat = rec.get("category", "")
            cat_display = cat_names.get(cat, cat)
            self.tree.insert("", "end", iid=str(idx), values=(
                cat_display,
                rec.get("record_id", ""),
                rec.get("deleted_by", "System"),
                rec.get("timestamp", ""),
                rec.get("summary_display", "")
            ))

        self.status_lbl.configure(text=f"기록 {len(self._filtered_records)}건 발견 (암호화 은닉 보호됨)")
        self.detail_text.delete("1.0", "end")
        self.detail_text.insert("1.0", "목록에서 복구할 항목을 선택하세요.")

    def on_record_select(self, event):
        sel = self.tree.selection()
        if not sel:
            return
        idx = int(sel[0])
        if idx >= len(self._filtered_records):
            return

        rec = self._filtered_records[idx]
        cat = rec.get("category", "")
        self.detail_text.delete("1.0", "end")

        if cat == "database_snapshots":
            info = f"=== 전체 데이터베이스 암호화 스냅샷 ===\n"
            info += f"• 백업 파일: {rec.get('filename')}\n"
            info += f"• 보관 일시: {rec.get('timestamp')}\n"
            info += f"• 파일 크기: {rec.get('file_size', 0):,} Bytes ({rec.get('file_size', 0)//1024:,} KB)\n"
            info += f"• 저장 경로: {rec.get('file_path')}\n\n"
            info += "※ [복원하기] 실행 시 현재 지정된 복구 대상 DB 파일로 즉시 덮어쓰기 복원됩니다."
            self.detail_text.insert("1.0", info)
        else:
            payload = rec.get("payload") or {}
            info = f"=== 은닉 복구 레코드 ({cat}) ===\n"
            info += f"• 식별자: {rec.get('record_id')}\n"
            info += f"• 삭제/보관자: {rec.get('deleted_by')}\n"
            info += f"• 일시: {rec.get('timestamp')}\n\n"
            info += json.dumps(payload, ensure_ascii=False, indent=2)
            self.detail_text.insert("1.0", info)

    def execute_restore(self):
        sel = self.tree.selection()
        if not sel:
            messagebox.showwarning("선택 오류", "복원할 항목을 목록에서 선택해주세요.")
            return

        idx = int(sel[0])
        rec = self._filtered_records[idx]
        file_path = rec.get("file_path")
        cat = rec.get("category")
        target_db = self.db_path_var.get().strip()

        if not target_db:
            messagebox.showerror("오류", "복구 대상 DB 파일 경로를 지정하세요.")
            return

        if not messagebox.askyesno(
            "복원 확인",
            f"선택한 '{cat}' 데이터를 아래 대상 DB로 복원하시겠습니까?\n\n"
            f"대상 DB: {target_db}\n\n"
            "암호를 복호화하여 데이터를 안전하게 재투입합니다."
        ):
            return

        try:
            category, content = StandaloneVaultEngine.decrypt_record_file(file_path)

            if category == "database_snapshots":
                StandaloneDBRestorer.restore_full_snapshot(target_db, content)
                messagebox.showinfo("복원 완료", f"전체 데이터베이스 스냅샷이 성공적으로 복원되었습니다!\n\n경로: {target_db}")
            elif category == "formulations":
                payload = content.get("payload", {})
                StandaloneDBRestorer.restore_formulation(target_db, payload)
                messagebox.showinfo("복원 완료", f"처방 데이터 '{payload.get('experiment_name')}'이(가) 성공적으로 복원되었습니다!")
            elif category == "materials":
                payload = content.get("payload", {})
                StandaloneDBRestorer.restore_material(target_db, payload)
                messagebox.showinfo("복원 완료", f"원료 데이터 '{payload.get('name')}'이(가) 성공적으로 복원되었습니다!")
            elif category == "clients":
                payload = content.get("payload", {})
                StandaloneDBRestorer.restore_client(target_db, payload)
                messagebox.showinfo("복원 완료", f"거래처 데이터 '{payload.get('name')}'이(가) 성공적으로 복원되었습니다!")
        except Exception as e:
            messagebox.showerror("복원 실패", f"복구 작업 중 오류가 발생했습니다: {e}")

    def execute_bulk_disaster_recovery(self):
        """재난 일괄 복구: 은닉 금고의 모든 개별 처방/원료/거래처를 대상 DB에 일괄 주입"""
        target_db = self.db_path_var.get().strip()
        if not target_db:
            messagebox.showerror("오류", "복구 대상 DB 파일 경로를 지정하세요.")
            return

        if not messagebox.askyesno(
            "🚨 재난 일괄 복구 확인",
            "은닉 금고에 보관된 모든 처방, 원료, 거래처 데이터를\n"
            f"대상 DB({target_db})로 일괄 복원 및 재구축하시겠습니까?\n\n"
            "※ 프로그램과 DB가 완전 소실되었을 때 사용하는 최종 재건 모드입니다."
        ):
            return

        success_count = 0
        fail_count = 0

        for rec in self._records:
            cat = rec.get("category")
            if cat == "database_snapshots":
                continue  # 스냅샷은 덮어쓰기이므로 일괄 주입에서 제외

            file_path = rec.get("file_path")
            try:
                category, content = StandaloneVaultEngine.decrypt_record_file(file_path)
                payload = content.get("payload", {})
                if category == "formulations":
                    StandaloneDBRestorer.restore_formulation(target_db, payload)
                    success_count += 1
                elif category == "materials":
                    StandaloneDBRestorer.restore_material(target_db, payload)
                    success_count += 1
                elif category == "clients":
                    StandaloneDBRestorer.restore_client(target_db, payload)
                    success_count += 1
            except Exception:
                fail_count += 1

        messagebox.showinfo(
            "재난 복구 완료",
            f"재난 일괄 복구 작업이 완료되었습니다!\n\n"
            f"• 성공 복구 항목: {success_count}건\n"
            f"• 실패 항목: {fail_count}건\n\n"
            f"대상 데이터베이스: {target_db}"
        )

    def run(self):
        self.root.mainloop()


if __name__ == "__main__":
    app = StandaloneMasterRecoveryUI()
    app.run()

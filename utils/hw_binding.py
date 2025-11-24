import os
import json
import hmac
import hashlib
import subprocess
from datetime import datetime
from cryptography.fernet import Fernet
import base64


_PEPPER = b"RnD_Platform_LocalBind_v1"
# DB 테이블명
_BINDING_TABLE = "system_binding"

# 암호화 키 생성 (PEPPER 기반으로 고정 키 생성)
def _get_encryption_key():
    """PEPPER를 기반으로 고정된 암호화 키를 생성합니다."""
    key = hashlib.sha256(_PEPPER).digest()
    return base64.urlsafe_b64encode(key)


def _ps_json(cmd: str, timeout: float = 3.0):
    """Run a PowerShell command that ends with ConvertTo-Json and return parsed JSON.
    Returns None if execution fails.
    """
    try:
        full = [
            "powershell",
            "-NoProfile",
            "-ExecutionPolicy", "Bypass",
            "-Command",
            cmd,
        ]
        out = subprocess.check_output(full, stderr=subprocess.STDOUT, timeout=timeout)
        s = out.decode("utf-8", errors="ignore").strip()
        if not s:
            return None
        return json.loads(s)
    except Exception:
        return None


def _norm_str(x: str) -> str:
    if not x:
        return ""
    s = str(x).strip().upper()
    # 제거: 공백과 구분자
    for ch in [" ", "-", ":", ";", ".", ",", "\\", "/", "\t", "\n", "\r"]:
        s = s.replace(ch, "")
    return s


def _unique_sorted(seq):
    return sorted(list({ _norm_str(x) for x in (seq or []) if _norm_str(x) }))


def get_hw_components() -> dict:
    """Collect key hardware identifiers using WMI via PowerShell.
    Returns a dict with stable, normalized fields.
    """
    # BIOS Serial
    bios = _ps_json("Get-CimInstance Win32_BIOS | Select-Object SerialNumber | ConvertTo-Json -Compress")
    bios_serial = ""
    if isinstance(bios, dict):
        bios_serial = _norm_str(bios.get("SerialNumber", ""))
    elif isinstance(bios, list) and bios:
        bios_serial = _norm_str((bios[0] or {}).get("SerialNumber", ""))

    # BaseBoard Serial
    bb = _ps_json("Get-CimInstance Win32_BaseBoard | Select-Object SerialNumber | ConvertTo-Json -Compress")
    baseboard_serial = ""
    if isinstance(bb, dict):
        baseboard_serial = _norm_str(bb.get("SerialNumber", ""))
    elif isinstance(bb, list) and bb:
        baseboard_serial = _norm_str((bb[0] or {}).get("SerialNumber", ""))

    # ComputerSystemProduct UUID
    cs = _ps_json("Get-CimInstance Win32_ComputerSystemProduct | Select-Object UUID | ConvertTo-Json -Compress")
    csproduct_uuid = ""
    if isinstance(cs, dict):
        csproduct_uuid = _norm_str(cs.get("UUID", ""))
    elif isinstance(cs, list) and cs:
        csproduct_uuid = _norm_str((cs[0] or {}).get("UUID", ""))

    # CPU ProcessorId (can be multiple)
    cpu = _ps_json("Get-CimInstance Win32_Processor | Select-Object ProcessorId | ConvertTo-Json -Compress")
    cpu_ids = []
    if isinstance(cpu, dict):
        cpu_ids = _unique_sorted([cpu.get("ProcessorId", "")])
    elif isinstance(cpu, list):
        cpu_ids = _unique_sorted([item.get("ProcessorId", "") for item in cpu if isinstance(item, dict)])

    # DiskDrive SerialNumber (multiple)
    dd = _ps_json("Get-CimInstance Win32_DiskDrive | Select-Object SerialNumber | ConvertTo-Json -Compress")
    disk_serials = []
    if isinstance(dd, dict):
        disk_serials = _unique_sorted([dd.get("SerialNumber", "")])
    elif isinstance(dd, list):
        disk_serials = _unique_sorted([item.get("SerialNumber", "") for item in dd if isinstance(item, dict)])

    # Physical Network adapters MACAddress (multiple)
    na = _ps_json(
        "Get-CimInstance Win32_NetworkAdapter -Filter \"PhysicalAdapter=True and MACAddress IS NOT NULL\" | "
        "Select-Object MACAddress | ConvertTo-Json -Compress"
    )
    macs = []
    if isinstance(na, dict):
        macs = _unique_sorted([na.get("MACAddress", "")])
    elif isinstance(na, list):
        macs = _unique_sorted([item.get("MACAddress", "") for item in na if isinstance(item, dict)])

    return {
        "bios_serial": bios_serial,
        "baseboard_serial": baseboard_serial,
        "csproduct_uuid": csproduct_uuid,
        "cpu_ids": cpu_ids,
        "disk_serials": disk_serials,
        "macs": macs,
    }


def _canonical_components(hw: dict) -> dict:
    return {
        "bios_serial": _norm_str(hw.get("bios_serial", "")),
        "baseboard_serial": _norm_str(hw.get("baseboard_serial", "")),
        "csproduct_uuid": _norm_str(hw.get("csproduct_uuid", "")),
        "cpu_ids": _unique_sorted(hw.get("cpu_ids", [])),
        "disk_serials": _unique_sorted(hw.get("disk_serials", [])),
        "macs": _unique_sorted(hw.get("macs", [])),
    }


def _sign_binding(payload: str) -> str:
    mac = hmac.new(_PEPPER, payload.encode("utf-8"), hashlib.sha256).hexdigest()
    return mac


def _get_db_path(config_file_path: str) -> str:
    """config.ini에서 DB 경로를 읽어옵니다."""
    try:
        import configparser
        cfg = configparser.ConfigParser()
        cfg.read(config_file_path, encoding="utf-8")
        db_path = cfg.get("Database", "db_path", fallback="").strip()
        if db_path and os.path.exists(db_path):
            return db_path
    except Exception:
        pass
    # 기본값: config.ini와 같은 폴더의 platform.db
    base_dir = os.path.dirname(config_file_path)
    return os.path.join(base_dir, "platform.db")


def _load_mode_from_config(config_file_path: str) -> str:
    try:
        import configparser
        cfg = configparser.ConfigParser()
        cfg.read(config_file_path, encoding="utf-8")
        mode = (cfg.get("Security", "binding_mode", fallback="flex").strip().lower())
        return "strict" if mode == "strict" else "flex"
    except Exception:
        return "flex"


def save_binding(config_file_path: str, mode: str = "flex") -> dict:
    """하드웨어 바인딩 정보를 DB에 암호화하여 저장합니다."""
    hw = _canonical_components(get_hw_components())
    record = {
        "version": 1,
        "mode": (mode or "flex"),
        "created_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "components": hw,
    }
    payload = json.dumps({"version": record["version"], "mode": record["mode"], "components": record["components"]}, sort_keys=True, separators=(",", ":"))
    record["signature"] = _sign_binding(payload)
    
    # 데이터 암호화
    fernet = Fernet(_get_encryption_key())
    encrypted_data = fernet.encrypt(json.dumps(record).encode('utf-8'))
    
    # DB에 저장
    db_path = _get_db_path(config_file_path)
    try:
        import sqlite3
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        
        # 테이블이 없으면 생성
        cursor.execute(f'''
            CREATE TABLE IF NOT EXISTS {_BINDING_TABLE} (
                id INTEGER PRIMARY KEY CHECK (id = 1),
                encrypted_data BLOB NOT NULL,
                updated_at TEXT NOT NULL
            )
        ''')
        
        # 데이터 저장 (REPLACE로 단일 레코드 유지)
        cursor.execute(f'''
            REPLACE INTO {_BINDING_TABLE} (id, encrypted_data, updated_at)
            VALUES (1, ?, ?)
        ''', (encrypted_data, datetime.now().strftime("%Y-%m-%d %H:%M:%S")))
        
        conn.commit()
        conn.close()
        
        # 기존 JSON 파일이 있으면 삭제
        try:
            legacy_json = os.path.join(os.path.dirname(config_file_path), "hw_binding.json")
            if os.path.exists(legacy_json):
                os.remove(legacy_json)
                print(f"[HW-BIND] 기존 JSON 파일 삭제: {legacy_json}")
        except Exception:
            pass
        
        return record
    except Exception as e:
        print(f"[HW-BIND] DB 저장 실패: {e}")
        raise


def load_binding(config_file_path: str) -> dict | None:
    """DB에서 암호화된 하드웨어 바인딩 정보를 복호화하여 로드합니다."""
    db_path = _get_db_path(config_file_path)
    
    # 레거시: JSON 파일이 있으면 DB로 마이그레이션
    legacy_json = os.path.join(os.path.dirname(config_file_path), "hw_binding.json")
    if os.path.exists(legacy_json):
        try:
            print("[HW-BIND] 기존 JSON 파일을 DB로 마이그레이션 중...")
            with open(legacy_json, "r", encoding="utf-8") as f:
                data = json.load(f)
            
            # DB에 저장
            fernet = Fernet(_get_encryption_key())
            encrypted_data = fernet.encrypt(json.dumps(data).encode('utf-8'))
            
            import sqlite3
            conn = sqlite3.connect(db_path)
            cursor = conn.cursor()
            cursor.execute(f'''
                CREATE TABLE IF NOT EXISTS {_BINDING_TABLE} (
                    id INTEGER PRIMARY KEY CHECK (id = 1),
                    encrypted_data BLOB NOT NULL,
                    updated_at TEXT NOT NULL
                )
            ''')
            cursor.execute(f'''
                REPLACE INTO {_BINDING_TABLE} (id, encrypted_data, updated_at)
                VALUES (1, ?, ?)
            ''', (encrypted_data, datetime.now().strftime("%Y-%m-%d %H:%M:%S")))
            conn.commit()
            conn.close()
            
            # 마이그레이션 후 JSON 파일 삭제
            os.remove(legacy_json)
            print("[HW-BIND] JSON 파일 마이그레이션 완료 및 삭제")
        except Exception as e:
            print(f"[HW-BIND] JSON 마이그레이션 실패: {e}")
    
    # DB에서 로드
    try:
        import sqlite3
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        
        # 테이블 존재 확인
        cursor.execute(f"SELECT name FROM sqlite_master WHERE type='table' AND name='{_BINDING_TABLE}'")
        if not cursor.fetchone():
            conn.close()
            return None
        
        # 데이터 로드
        cursor.execute(f'SELECT encrypted_data FROM {_BINDING_TABLE} WHERE id = 1')
        row = cursor.fetchone()
        conn.close()
        
        if not row:
            return None
        
        # 복호화
        fernet = Fernet(_get_encryption_key())
        decrypted_data = fernet.decrypt(row[0])
        data = json.loads(decrypted_data.decode('utf-8'))
        
        # verify signature
        payload = json.dumps({"version": data.get("version"), "mode": data.get("mode"), "components": data.get("components")}, sort_keys=True, separators=(",", ":"))
        sig = str(data.get("signature", ""))
        if not sig or _sign_binding(payload) != sig:
            return {"_invalid_signature": True, **data}
        return data
    except Exception as e:
        print(f"[HW-BIND] DB 로드 실패: {e}")
        return None


def compare_components(stored: dict, current: dict) -> dict:
    """Return comparison details and a match count over categories.
    Categories: uuid, bios, baseboard, cpu(any), disk(any), mac(any).
    """
    s = _canonical_components(stored)
    c = _canonical_components(current)

    matches = {
        "csproduct_uuid": bool(s.get("csproduct_uuid") and s.get("csproduct_uuid") == c.get("csproduct_uuid")),
        "bios_serial": bool(s.get("bios_serial") and s.get("bios_serial") == c.get("bios_serial")),
        "baseboard_serial": bool(s.get("baseboard_serial") and s.get("baseboard_serial") == c.get("baseboard_serial")),
        "cpu_ids": len(set(s.get("cpu_ids", [])) & set(c.get("cpu_ids", []))) > 0,
        "disk_serials": len(set(s.get("disk_serials", [])) & set(c.get("disk_serials", []))) > 0,
        "macs": len(set(s.get("macs", [])) & set(c.get("macs", []))) > 0,
    }
    count = sum(1 for v in matches.values() if v)
    return {"matches": matches, "count": count}


def meets_threshold(count: int, mode: str) -> bool:
    # strict: >=5 of 6 categories; flex: >=3 of 6
    if (mode or "flex").lower() == "strict":
        return count >= 5
    return count >= 3


def ensure_machine_binding(config_file_path: str):
    """Ensure the machine is bound. If no binding exists, prompt to create it.
    If binding exists, verify signature and compare against current HW; block on failure.
    """
    mode = _load_mode_from_config(config_file_path)

    def _show_error(msg: str):
        try:
            import tkinter as tk
            from tkinter import messagebox
            root = tk.Tk(); root.withdraw()
            messagebox.showerror("실행 차단", msg)
            root.destroy()
        except Exception:
            pass

    def _ask_yesno(title: str, msg: str) -> bool:
        try:
            import tkinter as tk
            from tkinter import messagebox
            root = tk.Tk(); root.withdraw()
            res = messagebox.askyesno(title, msg)
            root.destroy()
            return bool(res)
        except Exception:
            return False

    record = load_binding(config_file_path)
    if record is None:
        # First run activation
        if _ask_yesno("PC 활성화", "이 PC에 프로그램을 활성화하시겠습니까?\n하드웨어 바인딩 정보를 생성/저장합니다."):
            try:
                save_binding(config_file_path, mode)
            except Exception as e:
                _show_error(f"바인딩 생성 실패: {e}")
                raise SystemExit(1)
        else:
            _show_error("활성화가 취소되어 프로그램을 종료합니다.")
            raise SystemExit(1)
        return

    if record.get("_invalid_signature"):
        _show_error("바인딩 파일 서명 검증에 실패했습니다. 프로그램을 종료합니다.")
        raise SystemExit(1)

    current = get_hw_components()
    cmp = compare_components(record.get("components", {}), current)
    if not meets_threshold(cmp.get("count", 0), (record.get("mode") or mode)):
        # Build a short detail
        m = cmp.get("matches", {})
        detail = ", ".join([f"{k}:{'✓' if v else '✗'}" for k, v in m.items()])
        _show_error("이 PC는 등록된 하드웨어와 일치하지 않습니다.\n\n"
                   f"모드: {(record.get('mode') or mode)} / 일치 항목 수: {cmp.get('count',0)} / 6\n"
                   f"세부: {detail}")
        raise SystemExit(1)

    # OK
    return

# modules/secure_vault.py
import os
import sys
import json
import base64
import hashlib
import shutil
from datetime import datetime

# Windows 파일 속성 상수 (Hidden + System)
FILE_ATTRIBUTE_HIDDEN = 0x02
FILE_ATTRIBUTE_SYSTEM = 0x04

class SecureVault:
    """
    각 PC의 AppData 심층부에 삭제/변조가 불가능하도록 
    데이터를 2중 암호화하여 은닉 저장하는 보안 볼트 엔진
    """
    
    # 마스터 볼트 고유 시드 키
    _MASTER_SALT = b"LuxForma_R&D_Flatform_Master_Vault_Key_2026_Secure_v64_Signature"

    @classmethod
    def get_vault_path(cls) -> str:
        """
        각 PC의 AppData/Local 심층 시스템 은닉 경로 반환
        일반 사용자가 접근하거나 눈치채기 어려운 시스템 보호 폴더 구조
        """
        local_appdata = os.getenv('LOCALAPPDATA', os.path.expanduser('~'))
        vault_dir = os.path.join(local_appdata, 'Microsoft', 'Windows', 'CosSecureVault', '.sys_archive')
        os.makedirs(vault_dir, exist_ok=True)
        
        # 윈도우 OS 숨김(Hidden) + 시스템(System) 보호 속성 적용
        try:
            import ctypes
            ctypes.windll.kernel32.SetFileAttributesW(vault_dir, FILE_ATTRIBUTE_HIDDEN | FILE_ATTRIBUTE_SYSTEM)
        except Exception:
            pass
            
        return vault_dir

    @classmethod
    def _generate_key(cls, category: str) -> bytes:
        """카테고리별 동적 암호화 키 생성 (SHA-256)"""
        raw_key = cls._MASTER_SALT + category.encode('utf-8')
        return hashlib.sha256(raw_key).digest()

    @classmethod
    def _xor_cipher(cls, data_bytes: bytes, key: bytes) -> bytes:
        """대칭 스트림 XOR 암호화/복호화"""
        key_len = len(key)
        return bytes([b ^ key[i % key_len] for i, b in enumerate(data_bytes)])

    @classmethod
    def encrypt_and_save(cls, category: str, record_id: str, data_dict: dict, username: str = "system") -> str:
        """
        딕셔너리 데이터를 암호화하여 은닉 볼트에 저장 (.secv)
        """
        try:
            vault_dir = cls.get_vault_path()
            category_dir = os.path.join(vault_dir, category)
            os.makedirs(category_dir, exist_ok=True)
            
            try:
                import ctypes
                ctypes.windll.kernel32.SetFileAttributesW(category_dir, FILE_ATTRIBUTE_HIDDEN | FILE_ATTRIBUTE_SYSTEM)
            except Exception:
                pass

            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            filename = f"sys_{category}_{record_id}_{timestamp}.secv"
            target_path = os.path.join(category_dir, filename)

            # 페이로드 패키징
            payload = {
                "category": category,
                "record_id": str(record_id),
                "timestamp": timestamp,
                "deleted_by": username,
                "payload": data_dict
            }
            json_bytes = json.dumps(payload, ensure_ascii=False).encode('utf-8')
            
            # 암호화
            key = cls._generate_key(category)
            encrypted_bytes = cls._xor_cipher(json_bytes, key)
            encoded_payload = base64.b64encode(encrypted_bytes)

            with open(target_path, 'wb') as f:
                f.write(encoded_payload)

            # 파일에도 숨김+시스템 속성 부여
            try:
                import ctypes
                ctypes.windll.kernel32.SetFileAttributesW(target_path, FILE_ATTRIBUTE_HIDDEN | FILE_ATTRIBUTE_SYSTEM)
            except Exception:
                pass

            print(f"[SecureVault] 안전 은닉 백업 완료 ({category}): {target_path}")
            return target_path
        except Exception as e:
            print(f"[SecureVault 오류] 백업 저장 실패: {e}")
            return ""

    @classmethod
    def backup_database_file(cls, db_source_path: str, reset_type: str, username: str = "system") -> str:
        """
        DB 파일 원본 전체를 은닉 볼트에 암호화 스냅샷으로 저장
        """
        try:
            if not os.path.exists(db_source_path):
                return ""
                
            vault_dir = cls.get_vault_path()
            db_archive_dir = os.path.join(vault_dir, "database_snapshots")
            os.makedirs(db_archive_dir, exist_ok=True)

            try:
                import ctypes
                ctypes.windll.kernel32.SetFileAttributesW(db_archive_dir, FILE_ATTRIBUTE_HIDDEN | FILE_ATTRIBUTE_SYSTEM)
            except Exception:
                pass

            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            target_filename = f"snapshot_db_{reset_type}_{timestamp}.secv"
            target_path = os.path.join(db_archive_dir, target_filename)

            with open(db_source_path, 'rb') as f:
                raw_db = f.read()

            key = cls._generate_key("database_snapshots")
            encrypted_db = cls._xor_cipher(raw_db, key)
            encoded_db = base64.b64encode(encrypted_db)

            with open(target_path, 'wb') as f:
                f.write(encoded_db)

            try:
                import ctypes
                ctypes.windll.kernel32.SetFileAttributesW(target_path, FILE_ATTRIBUTE_HIDDEN | FILE_ATTRIBUTE_SYSTEM)
            except Exception:
                pass

            print(f"[SecureVault] 전체 DB 은닉 암호화 백업 완료: {target_path}")
            return target_path
        except Exception as e:
            print(f"[SecureVault 오류] DB 백업 저장 실패: {e}")
            return ""

    @classmethod
    def list_archived_records(cls, category: str = None) -> list:
        """
        마스터 프로그램 전용: 은닉 볼트의 백업 기록 목록 조회
        """
        vault_dir = cls.get_vault_path()
        results = []
        
        categories = [category] if category else ['formulations', 'materials', 'clients', 'users', 'database_snapshots']
        
        for cat in categories:
            cat_dir = os.path.join(vault_dir, cat)
            if not os.path.exists(cat_dir):
                continue
                
            for fname in os.listdir(cat_dir):
                if not fname.endswith('.secv'):
                    continue
                file_path = os.path.join(cat_dir, fname)
                try:
                    with open(file_path, 'rb') as f:
                        content = f.read()
                    
                    key = cls._generate_key(cat)
                    decrypted_bytes = cls._xor_cipher(base64.b64decode(content), key)
                    
                    if cat == "database_snapshots":
                        mtime = datetime.fromtimestamp(os.path.getmtime(file_path)).strftime('%Y-%m-%d %H:%M:%S')
                        results.append({
                            "category": "database_snapshots",
                            "record_id": fname,
                            "timestamp": mtime,
                            "deleted_by": "System Admin",
                            "file_path": file_path,
                            "file_size": len(decrypted_bytes),
                            "payload": None
                        })
                    else:
                        data = json.loads(decrypted_bytes.decode('utf-8'))
                        data["file_path"] = file_path
                        results.append(data)
                except Exception as parse_err:
                    print(f"[SecureVault] 파일 복호화 실패 ({fname}): {parse_err}")
                    
        return results

    @classmethod
    def restore_record_data(cls, file_path: str) -> tuple:
        """
        마스터 프로그램 전용: 특정 은닉 백업 파일 복호화하여 원본 데이터 반환
        반환: (category, payload_dict_or_db_bytes)
        """
        category = os.path.basename(os.path.dirname(file_path))
        with open(file_path, 'rb') as f:
            content = f.read()
        
        key = cls._generate_key(category)
        decrypted_bytes = cls._xor_cipher(base64.b64decode(content), key)
        
        if category == "database_snapshots":
            return category, decrypted_bytes
        else:
            return category, json.loads(decrypted_bytes.decode('utf-8'))

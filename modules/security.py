import os
import sys
import hashlib
import subprocess
import uuid
import ctypes # Windows API 사용을 위해 추가
from tkinter import messagebox
from datetime import datetime

class SecurityManager:
    """
    프로그램 실행 권한을 제어하는 보안 매니저
    - Node-Locking: 최초 실행된 PC에 귀속
    - Anti-Copy: 단순 복사 시 실행 차단
    """
    
    def __init__(self):
        # 실행 파일 위치 기준
        if getattr(sys, 'frozen', False):
            self.base_path = os.path.dirname(sys.executable)
        else:
            self.base_path = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
            
        # 2025-02-04: License 파일은 AppData/Roaming에 저장하여 업데이트 시에도 유지되도록 함
        # C:\Users\사용자명\AppData\Roaming\CosRnD_Platform
        try:
            self.app_data_path = os.path.join(os.environ['APPDATA'], 'CosRnD_Platform')
            os.makedirs(self.app_data_path, exist_ok=True)
        except Exception as e:
            # AppData 접근 실패 시 프로그램 폴더 사용 (폴백)
            print(f"[보안] AppData 폴더 생성 실패: {e}")
            self.app_data_path = os.path.join(self.base_path, 'config')
            try:
                os.makedirs(self.app_data_path, exist_ok=True)
            except Exception as e2:
                print(f"[보안] 폴백 폴더도 생성 실패: {e2}")
                self.app_data_path = self.base_path
        
        # license.dat는 숨김 폴더인 AppData 내에 위치하며, 파일 자체도 숨김 속성을 부여할 예정
        self.license_file = os.path.join(self.app_data_path, "license.dat")
        
        # 이전 버전과의 호환성 및 마이그레이션을 위한 구 경로
        self.old_license_file = os.path.join(self.base_path, "license.dat")
        
        # setup.key는 여전히 프로그램 실행 위치에서 찾음 (배포 시 여기에 포함되므로)
        self.setup_flag = os.path.join(self.base_path, "setup.key")
        
        # Salt for hashing (Hardcoded)
        self.salt = "CosRnD_Platform_V59_Secure_Salt_2024"

    def get_system_signature(self):
        """현재 시스템의 고유 식별자(HWID) 생성 (UUID + MAC + Username)"""
        try:
            # 1. Motherboard UUID (Windows)
            cmd = 'wmic csproduct get uuid'
            try:
                # creationflags=0x08000000 (CREATE_NO_WINDOW) to hide console window
                uuid_proc = subprocess.check_output(cmd, shell=True, creationflags=0x08000000, timeout=5)
                sys_uuid = uuid_proc.decode().split('\n')[1].strip()
                if not sys_uuid or len(sys_uuid) < 5:
                    raise ValueError("Invalid UUID from wmic")
            except Exception as e:
                print(f"[보안] WMIC UUID 조회 실패: {e} - 폴백 사용")
                # 폴백: Windows 환경 변수 기반 ID 생성
                sys_uuid = os.environ.get('COMPUTERNAME', 'UNKNOWN') + "_" + os.environ.get('PROCESSOR_IDENTIFIER', 'CPU_UNKNOWN')
        except Exception as e:
            print(f"[보안] 시스템 UUID 조회 실패: {e}")
            sys_uuid = "UNKNOWN_UUID"

        try:
            # 2. MAC Address
            mac = uuid.getnode()
        except Exception as e:
            print(f"[보안] MAC 주소 조회 실패: {e}")
            mac = 0
            
        try:
            # 3. Windows Username (추가 검증)
            # os.getlogin()이나 환경변수 사용
            username = os.environ.get('USERNAME', 'UNKNOWN_USER')
        except Exception as e:
            print(f"[보안] 사용자명 조회 실패: {e}")
            username = "UNKNOWN_USER"

        # Combine info
        raw_id = f"{sys_uuid}-{mac}-{username}-{self.salt}"
        
        # Hash it (SHA-256)
        hwid = hashlib.sha256(raw_id.encode()).hexdigest()
        print(f"[보안] HWID 생성 완료: {hwid[:16]}...")
        return hwid

    def verify_access(self):
        """
        접근 권한 검증 메인 로직
        Returns: True if allowed, False otherwise
        """
        current_hwid = self.get_system_signature()
        
        # 0. 마이그레이션: AppData에 라이선스가 없고, 기존 경로(실행위치)에 라이선스가 있다면 이동 처리
        if not os.path.exists(self.license_file) and os.path.exists(self.old_license_file):
            try:
                # 기존 파일 내용 읽기
                with open(self.old_license_file, 'r') as f:
                    content = f.read().strip()
                
                # 새 위치에 쓰기
                with open(self.license_file, 'w') as f:
                    f.write(content)
                
                # 파일 숨김 속성 적용
                try:
                    FILE_ATTRIBUTE_HIDDEN = 0x02
                    ctypes.windll.kernel32.SetFileAttributesW(self.license_file, FILE_ATTRIBUTE_HIDDEN)
                except Exception:
                    pass
                
                print(f"License migrated from {self.old_license_file} to {self.license_file}")
                # 기존 파일은 백업 차원에서 남겨두거나 삭제할 수 있음. 
                # 혼동 방지를 위해 삭제하는 것이 좋으나 안전을 위해 유지할 수도 있음.
                # 여기서는 삭제하지 않고 둠.
            except Exception as e:
                print(f"License migration failed: {e}")

        # 1. 라이선스 파일이 있는 경우 (이미 등록된 PC)
        # 업데이트 시나리오: 사용자가 실행파일만 교체해도 기존 license.dat가 있으면 통과
        # 우선순위: AppData > 폴백 경로 (프로그램 폴더)
        license_paths = [
            self.license_file,  # AppData\Roaming\CosRnD_Platform\license.dat
            os.path.join(self.base_path, 'config', 'license.dat')  # 폴백: 프로그램폴더\config\license.dat
        ]
        
        for license_path in license_paths:
            if os.path.exists(license_path):
                try:
                    with open(license_path, 'r') as f:
                        stored_hwid = f.read().strip()
                    
                    if current_hwid == stored_hwid:
                        # 유효한 라이선스 존재 시, setup.key가 있어도 무시(삭제하지 않음)하고 통과
                        # -> 실수로 setup.key를 같이 넣어도 기존 사용자는 영향 없음
                        print(f"[보안] 라이선스 검증 성공: {license_path}")
                        return True
                    else:
                        # 라이선스 파일은 있지만 HWID 불일치 (다른 PC에서 복사해온 경우 등)
                        # 이 경우 아래의 setup.key 로직으로 넘어가서 재등록을 시도할지, 아니면 차단할지 결정해야 함.
                        # 여기서는 '재등록 기회'를 주기 위해 setup.key 체크 로직으로 넘어감 (pass)
                        # 다만, 명확한 에러 메시지를 위해 로그만 남기고 일단 진행
                        print(f"[보안] HWID 불일치: {license_path}")
                        pass 
                except Exception as e:
                    # 라이선스 파일 읽기 실패 -> setup.key 확인으로 넘어감
                    print(f"[보안] 라이선스 읽기 실패: {license_path} - {e}")
                    pass

        # 2. 라이선스 파일이 없거나 유효하지 않은 경우 -> 초기 설정(setup.key) 확인
        if os.path.exists(self.setup_flag):
            try:
                # 최초 실행: 현재 PC 박제
                print(f"[보안] 기기 등록 시작: {self.license_file}")
                
                # 폴더 재확인 (쓰기 직전)
                license_dir = os.path.dirname(self.license_file)
                if not os.path.exists(license_dir):
                    try:
                        os.makedirs(license_dir, exist_ok=True)
                        print(f"[보안] 라이선스 폴더 생성: {license_dir}")
                    except Exception as e:
                        print(f"[보안] 라이선스 폴더 생성 실패: {e}")
                        raise
                
                # 기존 파일이 있으면 먼저 삭제 (권한 오류 방지)
                if os.path.exists(self.license_file):
                    try:
                        os.remove(self.license_file)
                        print(f"[보안] 기존 라이선스 파일 삭제: {self.license_file}")
                    except Exception as e:
                        print(f"[보안] 기존 파일 삭제 실패: {e}")
                
                # 현재 HWID 기록
                with open(self.license_file, 'w') as f:
                    f.write(current_hwid)
                print(f"[보안] 라이선스 파일 기록 완료: {self.license_file}")
                
                # 파일 숨김 속성 적용 (Windows)
                try:
                    FILE_ATTRIBUTE_HIDDEN = 0x02
                    ctypes.windll.kernel32.SetFileAttributesW(self.license_file, FILE_ATTRIBUTE_HIDDEN)
                    print(f"[보안] 파일 숨김 속성 적용 완료")
                except Exception as e:
                    print(f"[보안] 파일 숨김 속성 적용 실패 (무시): {e}")
                
                # setup.key 삭제 (재사용 방지)
                try:
                    os.remove(self.setup_flag)
                    print(f"[보안] setup.key 삭제 완료")
                except Exception as e:
                    print(f"[보안] setup.key 삭제 실패 (무시): {e}")
                
                messagebox.showinfo("등록 완료", "이 PC가 정상적으로 등록되었습니다.\n이제 프로그램을 사용하실 수 있습니다.")
                return True
            except PermissionError as pe:
                # 권한 오류: 폴백 경로 사용
                print(f"[보안] ⚠️ AppData 권한 오류 - 폴백 경로 사용: {pe}")
                try:
                    # 프로그램 폴더 내 config 폴더 사용
                    fallback_dir = os.path.join(self.base_path, 'config')
                    os.makedirs(fallback_dir, exist_ok=True)
                    fallback_license = os.path.join(fallback_dir, 'license.dat')
                    
                    # 기존 파일 삭제
                    if os.path.exists(fallback_license):
                        os.remove(fallback_license)
                    
                    # 파일 쓰기
                    with open(fallback_license, 'w') as f:
                        f.write(current_hwid)
                    
                    print(f"[보안] 포백 라이선스 저장: {fallback_license}")
                    
                    # setup.key 삭제
                    try:
                        os.remove(self.setup_flag)
                    except:
                        pass
                    
                    messagebox.showinfo("등록 완료", "이 PC가 정상적으로 등록되었습니다.\n(로컬 저장)\n이제 프로그램을 사용하실 수 있습니다.")
                    return True
                except Exception as fallback_error:
                    error_msg = f"기기 등록 중 오류가 발생했습니다.\n\n상세: {str(fallback_error)}\n\n프로그램 폴더 권한을 확인하거나 관리자로 실행해주세요."
                    print(f"[보안] 포백도 실패: {error_msg}")
                    self._show_error("등록 실패", error_msg)
                    return False
            except Exception as e:
                error_msg = f"기기 등록 중 오류가 발생했습니다.\n\n상세: {str(e)}\n\n폴더: {license_dir}\n권한을 확인하거나 관리자로 실행해주세요."
                print(f"[보안] 오류: {error_msg}")
                self._show_error("등록 실패", error_msg)
                return False

        # 3. 라이선스도 없고, 셋업 키도 없는 경우 (불법 복제 또는 파일 유실)
        else:
            self._show_error("실행 불가", "유효한 라이선스를 찾을 수 없습니다.\n관리자에게 문의하여 'setup.key'를 발급받으세요.")
            return False

    def _show_error(self, title, msg):
        # 메인 윈도우가 아직 없을 수 있으므로 임시 root 생성
        try:
            import tkinter as tk
            root = tk.Tk()
            root.withdraw()
            messagebox.showerror(title, msg)
            root.destroy()
        except:
            pass

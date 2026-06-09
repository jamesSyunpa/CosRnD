import os
import sys
import bcrypt
import shutil
from sqlalchemy import create_engine, text, event, inspect, or_
import configparser
from sqlalchemy.orm import sessionmaker, joinedload, subqueryload
from datetime import datetime
from types import SimpleNamespace

from database.models import Base, User, Client, Material, Ingredient, Formulation, FormulationItem, ProductionFormulation, ProductionStep, ProductionRun

SCHEMA_VERSION = 18

def file_exists_including_hidden(path: str) -> bool:
    """숨김 파일을 포함하여 파일 존재 여부를 확인합니다."""
    if not path:
        return False
    
    # 기본 존재 여부 확인
    if os.path.exists(path):
        return True
    
    # Windows에서 숨김 파일 명시적 확인
    try:
        import ctypes
        FILE_ATTRIBUTE_HIDDEN = 0x02
        attrs = ctypes.windll.kernel32.GetFileAttributesW(path)
        # INVALID_FILE_ATTRIBUTES = -1 (0xFFFFFFFF)
        if attrs == -1:
            return False
        return True
    except Exception:
        return False

def ensure_file_accessible(path: str):
    """파일의 읽기 전용, 숨김, 시스템 속성을 해제하여 SQLite가 정상적으로 열 수 있도록 합니다."""
    if not path:
        return
    try:
        if sys.platform.startswith('win'):
            import ctypes
            # 파일이 존재하는 경우 속성을 일반(Normal)으로 재설정
            if os.path.exists(path):
                FILE_ATTRIBUTE_NORMAL = 0x80
                ctypes.windll.kernel32.SetFileAttributesW(path, FILE_ATTRIBUTE_NORMAL)
                print(f"[자가치유] 파일 속성 일반화 완료 (숨김/읽기전용 해제): {path}")
            else:
                # 존재하진 않지만 숨김 파일 속성을 확인해 제거 시도
                attrs = ctypes.windll.kernel32.GetFileAttributesW(path)
                if attrs != -1:
                    FILE_ATTRIBUTE_NORMAL = 0x80
                    ctypes.windll.kernel32.SetFileAttributesW(path, FILE_ATTRIBUTE_NORMAL)
    except Exception as e:
        print(f"[경고] 파일 속성 변경 실패: {e}")

def discover_database_paths() -> list:
    """OneDrive, 네트워크 드라이브 등에서 cosmetic.db 파일이 존재하는 위치를 자동으로 스캔하여 검색합니다."""
    candidates = []
    
    # 1. OneDrive 환경 변수 확인 및 스캔
    onedrive_vars = ['OneDrive', 'OneDriveConsumer', 'OneDriveCommercial']
    for var in onedrive_vars:
        od_path = os.environ.get(var)
        if od_path and os.path.exists(od_path):
            candidates.append(os.path.normpath(os.path.join(od_path, 'CosRnD_data')))
            candidates.append(os.path.normpath(os.path.join(od_path, 'Documents', 'CosRnD_data')))
            candidates.append(os.path.normpath(os.path.join(od_path, 'CosRnD')))
            candidates.append(os.path.normpath(os.path.join(od_path, 'Data')))
            
    # 2. 내 문서(Documents) 경로 내 OneDrive 동기화 폴더 확인
    user_profile = os.path.expanduser('~')
    candidates.append(os.path.normpath(os.path.join(user_profile, 'OneDrive', 'Documents', 'CosRnD_data')))
    candidates.append(os.path.normpath(os.path.join(user_profile, 'OneDrive', 'CosRnD_data')))
    
    # 3. 네트워크 드라이브 및 로컬 드라이브 스캔 (D부터 Z까지)
    if sys.platform.startswith('win'):
        import ctypes
        try:
            for drive_letter in range(ord('D'), ord('Z') + 1):
                drive = f"{chr(drive_letter)}:\\"
                drive_type = ctypes.windll.kernel32.GetDriveTypeW(drive)
                if drive_type in (4, 3): # 네트워크 드라이브(4) 또는 기타 로컬 드라이브(3)
                    candidates.append(os.path.normpath(os.path.join(drive, 'CosRnD_data')))
                    candidates.append(os.path.normpath(os.path.join(drive, 'CosRnD', 'Data')))
        except Exception as e:
            print(f"[경로 검색] 드라이브 스캔 중 에러 (무시): {e}")

    # 실제 파일(cosmetic.db)이 존재하는 폴더만 필터링
    valid_dirs = []
    for directory in candidates:
        if not directory:
            continue
        directory = os.path.normpath(directory).replace('\\', '/')
        db_file = os.path.normpath(os.path.join(directory, 'cosmetic.db')).replace('\\', '/')
        if file_exists_including_hidden(db_file):
            print(f"[경로 검색] 유효한 DB 발견: {db_file}")
            valid_dirs.append(directory)
            
    return list(dict.fromkeys(valid_dirs))

class DBManager:
    _instance = None

    def __new__(cls, *args, **kwargs):
        if not cls._instance:
            cls._instance = super(DBManager, cls).__new__(cls)
        return cls._instance

    def _create_new_db_file(self, db_path: str) -> bool:
        """새로운 SQLite DB 파일을 생성합니다."""
        print("\n=== 새 DB 파일 생성 시작 ===")
        
        # 1. 기존 파일 삭제
        try:
            if file_exists_including_hidden(db_path):
                os.remove(db_path)
                print("  * 기존 DB 파일 삭제됨")
        except Exception as e:
            print(f"  * 기존 DB 파일 삭제 실패: {e}")
            return False

        # 2. DB 파일 생성
        try:
            # SQLite3 모듈 가져오기 (단계별 시도)
            sqlite3_module = None
            import_attempts = []
            
            # 시도 1: 기본 sqlite3 모듈
            try:
                import sqlite3
                # 기본 기능 테스트
                test_conn = sqlite3.connect(':memory:')
                test_conn.execute('SELECT 1')
                test_conn.close()
                sqlite3_module = sqlite3
                print("  * sqlite3 모듈 가져오기 성공 (기본)")
            except Exception as e:
                import_attempts.append(f"기본 sqlite3: {str(e)}")
            
            # 시도 2: _sqlite3 모듈 직접 import 후 sqlite3 재시도
            if not sqlite3_module:
                try:
                    import _sqlite3  # 강제로 _sqlite3 로드
                    import sqlite3   # sqlite3 재import
                    # 기본 기능 테스트
                    test_conn = sqlite3.connect(':memory:')
                    test_conn.execute('SELECT 1')
                    test_conn.close()
                    sqlite3_module = sqlite3
                    print("  * sqlite3 모듈 가져오기 성공 (_sqlite3 직접 로드 후)")
                except Exception as e:
                    import_attempts.append(f"_sqlite3 직접: {str(e)}")
            
            # 모든 시도 실패 시
            if not sqlite3_module:
                error_details = "\n".join([f"  - {attempt}" for attempt in import_attempts])
                error_msg = f"SQLite3 모듈을 가져올 수 없습니다:\n{error_details}"
                print(f"  * {error_msg}")
                return False
            
            # DB 파일 생성
            conn = sqlite3_module.connect(db_path)
            conn.close()
            
            if file_exists_including_hidden(db_path):
                file_size = os.path.getsize(db_path)
                print(f"  * 새 DB 파일 생성됨 ({file_size} bytes)")
                ensure_file_accessible(db_path)
                return True
            else:
                print("  * DB 파일이 생성되지 않았음")
                return False
                
        except Exception as e:
            print(f"  * DB 파일 생성 중 예상치 못한 오류: {str(e)}")
            return False

    def __init__(self):
        if not hasattr(self, 'initialized'):
            self.engine = None
            self.Session = None
            self.initialized = True
            self.application_path = None
            self.config_path = None

    def get_db_relative_path(self) -> str:
        # 기본 fallback 경로는 AppData/CosRnD/Data 로 지정 (OneDrive 동기화 잠금 회피)
        default_dir = os.path.join(os.getenv('APPDATA', os.path.join(os.path.expanduser('~'), 'AppData', 'Roaming')), 'CosRnD', 'Data')
        
        print("설정 파일 경로:", self.config_path)
        if not self.config_path or not os.path.exists(self.config_path):
            print(f"설정 파일이 없음, 기본값 {default_dir} 사용")
            return default_dir
            
        try:
            config = configparser.ConfigParser(interpolation=None)
            config.read(self.config_path, encoding='utf-8')
            db_dir = config.get('Paths', 'database_dir', fallback='')
            if not db_dir:
                db_dir = default_dir
            print(f"config.ini에서 읽은 database_dir: {db_dir}")
            return db_dir
        except Exception as e:
            print(f"설정 파일 읽기 실패: {e}, 기본값 {default_dir} 사용")
            return default_dir

    def get_local_db_path(self) -> str:
        db_dir = self.get_db_relative_path()
        target_path = os.path.join(db_dir, "cosmetic.db")
        
        # 이전 Documents 경로에서 AppData 경로로 자동 데이터베이스 이전(마이그레이션) 수행
        try:
            old_db_dir = os.path.join(os.path.expanduser('~'), 'Documents', 'CosRnD', 'Data')
            old_db_path = os.path.join(old_db_dir, "cosmetic.db")
            if os.path.exists(old_db_path) and not os.path.exists(target_path):
                os.makedirs(db_dir, exist_ok=True)
                shutil.copy2(old_db_path, target_path)
                print(f"[마이그레이션] 기존 Documents DB({old_db_path})를 AppData 경로({target_path})로 복사 완료")
        except Exception as mig_err:
            print(f"[경고] 기존 Documents DB 마이그레이션 실패: {mig_err}")
            
        return target_path

    def cleanup_db_files(self):
        """WAL, SHM, 백업 파일들을 정리합니다."""
        if not hasattr(self, 'db_path') or not self.db_path:
            print("[DEBUG] cleanup_db_files: db_path가 없음")
            return
            
        print(f"[DEBUG] DB 관련 파일 정리 시작: {self.db_path}")
        
        # 정리할 파일 확장자들
        cleanup_extensions = ['-wal', '-shm', '.tmp', '.bak', '.safety_backup']
        
        for ext in cleanup_extensions:
            file_path = f"{self.db_path}{ext}"
            if os.path.exists(file_path):
                try:
                    # 파일이 사용 중인지 확인하고 여러 번 시도
                    max_attempts = 3
                    for attempt in range(max_attempts):
                        try:
                            os.remove(file_path)
                            print(f"[DEBUG] 파일 정리됨: {os.path.basename(file_path)}")
                            break
                        except PermissionError as pe:
                            if attempt < max_attempts - 1:
                                print(f"[DEBUG] 파일 사용 중, 재시도 {attempt + 1}/{max_attempts}: {os.path.basename(file_path)}")
                                import time
                                time.sleep(0.1)
                            else:
                                print(f"[DEBUG] 파일 정리 실패 (사용 중): {os.path.basename(file_path)}")
                        except Exception as e:
                            print(f"[DEBUG] 파일 정리 실패: {os.path.basename(file_path)} - {e}")
                            break
                except Exception as e:
                    print(f"[DEBUG] 파일 정리 중 예상치 못한 오류: {os.path.basename(file_path)} - {e}")
        
        print(f"[DEBUG] DB 파일 정리 완료")

    def set_database_url(self, database_url: str):
        """런타임에 데이터베이스 URL을 변경합니다."""
        print(f"[DEBUG] DB URL 변경 요청: {database_url}")
        
        try:
            # 기존 연결 정리
            self.dispose_engine()
            
            # URL에서 DB 경로 추출
            if database_url.startswith('sqlite:///'):
                self.db_path = database_url[10:]  # 'sqlite:///' 제거
            else:
                raise ValueError(f"지원하지 않는 DB URL 형식: {database_url}")
            
            print(f"[DEBUG] 새 DB 경로 설정: {self.db_path}")
            return True
            
        except Exception as e:
            print(f"[ERROR] DB URL 변경 실패: {e}")
            return False

    def setup_database(self, application_path: str = None, config_path: str = None, on_initial_setup=None):
        """데이터베이스를 설정하고 초기화합니다."""
        print(f"\n{'='*50}\n[DB 설정 시작]")
        
        # 경로 설정 (이미 설정된 경우 유지)
        if application_path is not None:
            self.application_path = application_path
        if config_path is not None:
            self.config_path = config_path
            
        # 필수 경로가 없으면 오류
        if not self.application_path or not self.config_path:
            raise ValueError("application_path와 config_path가 필요합니다.")
        
        # 설정 파일 읽기
        config = configparser.ConfigParser(interpolation=None)
        config.read(self.config_path, encoding='utf-8')
        
        # 1. 기본 경로 설정 (Documents/CosRnD/Data/cosmetic.db)
        local_db_path = self.get_local_db_path()
        os.makedirs(os.path.dirname(local_db_path), exist_ok=True)
        shared_db_path = config.get('Paths', 'shared_db_path', fallback=None)

        # 만약 config.ini에 shared_db_path가 없거나 해당 경로가 존재하지 않는 경우, OneDrive 및 네트워크 드라이브 자동 스캔
        if not shared_db_path or not os.path.exists(shared_db_path):
            print("[INFO] 유효한 공유 DB 경로가 설정되지 않았습니다. OneDrive 및 네트워크 폴더 자동 스캔을 시도합니다...")
            discovered_paths = discover_database_paths()
            if discovered_paths:
                # 첫 번째 유효한 경로를 자동으로 책정
                auto_path = discovered_paths[0]
                shared_db_path = auto_path
                print(f"[INFO] 자동으로 감지된 DB 경로를 책정합니다: {auto_path}")
                
                # config.ini에 자동 감지된 경로 저장
                try:
                    if not config.has_section('Paths'):
                        config.add_section('Paths')
                    config.set('Paths', 'shared_db_path', auto_path)
                    with open(config_path, 'w', encoding='utf-8') as configfile:
                        config.write(configfile)
                except Exception as save_err:
                    print(f"[경고] 자동 감지된 경로 저장 실패 (무시): {save_err}")

        # Normalize shared_db_path: config stores only the folder. If a full file
        # path was stored, handle gracefully, but prefer folder paths.
        def resolve_shared_file(path):
            if not path:
                return None
            # 인라인 주석(#) 제거 및 공백 함수
            if '#' in path:
                path = path.split('#')[0]
            # 따옴표로 감싸진 값 방지 및 공백 제거
            path = path.strip().strip('"').strip("'")
            # if user or older code stored full file path, accept it
            if path.lower().endswith('.db') or os.path.basename(path).lower() == 'cosmetic.db':
                return path
            # otherwise treat stored value as a directory
            return os.path.join(path, 'cosmetic.db')

        shared_db_file = resolve_shared_file(shared_db_path)
        print(f"[INFO] 로컬 DB 경로: {local_db_path}")
        print(f"[INFO] 공유 DB (설정) 폴더/파일: {shared_db_path} -> {shared_db_file}")
        
        # 2. 공유 DB 경로 설정 (첫 실행시)
        # If nothing is configured and there's no local DB, set the default to the
        # local DB's directory (store folder only).
        if not shared_db_path and not file_exists_including_hidden(local_db_path):
            if not config.has_section('Paths'):
                config.add_section('Paths')
            try:
                config.set('Paths', 'shared_db_path', os.path.dirname(local_db_path))
                with open(config_path, 'w', encoding='utf-8') as configfile:
                    config.write(configfile)
                print(f"[INFO] 초기 DB 폴더 경로 설정: {os.path.dirname(local_db_path)}")
                shared_db_path = os.path.dirname(local_db_path)
                shared_db_file = local_db_path
            except Exception as e:
                print(f"[경고] 초기 DB 경로 저장 실패: {e}")
        
        # 3. 공유 DB 사용 시도
        # Try using shared DB file. If folder/file doesn't exist, create it automatically.
        try:
            if shared_db_file:
                db_dir = os.path.dirname(shared_db_file)
                if not os.path.exists(db_dir):
                    os.makedirs(db_dir, exist_ok=True)
                    print(f"[자가치유] 공유 DB 폴더가 존재하지 않아 새로 생성했습니다: {db_dir}")
                
                if not file_exists_including_hidden(shared_db_file):
                    print(f"[자가치유] 공유 DB 파일이 존재하지 않아 새로 생성합니다: {shared_db_file}")
                    if not self._create_new_db_file(shared_db_file):
                        raise RuntimeError("공유 DB 파일 자동 생성 실패")
                
                ensure_file_accessible(shared_db_file)
                print(f"[INFO] 공유 DB 파일 확인: {shared_db_file}")
                self.db_path = shared_db_file

                # 공유 DB 연결 엔진 생성
                test_engine = create_engine(
                    f'sqlite:///{shared_db_file}',
                    connect_args={
                        'check_same_thread': False,
                        'timeout': 60  # 원드라이브/네트워크 동기화 지연 시 잠금 타임아웃
                    }
                )
                db_version = None
                try:
                    with test_engine.connect() as conn:
                        try:
                            db_version = conn.execute(text("SELECT version FROM _schema_version")).scalar()
                            print(f"[INFO] 공유 DB 스키마 버전 감지: v{db_version}")
                        except Exception as schema_e:
                            print(f"[경고] 공유 DB 스키마 버전 확인 실패: {schema_e} (버전 테이블이 없을 수 있음)")
                except Exception as conn_e:
                    print(f"[경고] 공유 DB 연결 테스트 실패: {conn_e}")
                    test_engine.dispose()
                    raise

                # 엔진 채택 후 마이그레이션/트리거 보장 진행 (버전 불일치여도 시도)
                self.engine = test_engine
                try:
                    # 신규 DB이면 스키마 생성 및 기초 세팅
                    Base.metadata.create_all(self.engine)
                    # 스키마 버전 테이블이 없으면 설정
                    with self.engine.connect() as conn:
                        conn.execute(text("CREATE TABLE IF NOT EXISTS _schema_version (version INTEGER)"))
                        ver_check = conn.execute(text("SELECT version FROM _schema_version")).scalar()
                        if ver_check is None:
                            conn.execute(text(f"INSERT INTO _schema_version (version) VALUES ({SCHEMA_VERSION})"))
                            conn.commit()
                except Exception as base_e:
                    print(f"[경고] 기본 스키마 생성 실패(무시): {base_e}")

                try:
                    self._check_and_run_migrations()
                except Exception as mig_e:
                    print(f"[경고] 공유 DB 버전/마이그레이션 처리 실패(무시): {mig_e}")
                    try:
                        # 최소한 누락 컬럼 보수 시도
                        self._run_migrations()
                    except Exception as mig2:
                        print(f"[경고] 공유 DB 보수 마이그레이션 2차 실패(무시): {mig2}")
                try:
                    self.ensure_change_tracking()
                except Exception as trg_e:
                    print(f"[경고] 공유 DB 트리거 보장 실패(무시): {trg_e}")

                self.Session = sessionmaker(bind=self.engine)
                print(f"[INFO] 공유 DB 연결 성공 (마이그레이션/트리거 보장 완료)")
                self._save_init_state(True)
                return
        except Exception as e:
            print(f"[경고] 공유 DB 연결 및 생성 실패: {e}")
            if 'test_engine' in locals():
                try:
                    test_engine.dispose()
                except Exception:
                    pass
        
        # 4. 로컬 DB 사용
        print("\n=== 로컬 DB 설정 시작 ===")
        try:
            # 1. 초기화
            if self.engine:
                print("  * 기존 DB 엔진 정리")
                self.dispose_engine()
            
            self.db_path = local_db_path
            ensure_file_accessible(self.db_path)
            print(f"  * DB 경로: {self.db_path}")
            
            # 2. DB 파일 처리
            is_new_db = not file_exists_including_hidden(self.db_path)
            self.cleanup_db_files()
            
            # 3. DB 파일 생성 (없을 경우에만)
            if is_new_db:
                print(f"  * 새 DB 파일 생성 필요 (경로: {self.db_path})")
                if not self._create_new_db_file(self.db_path):
                    raise RuntimeError("DB 파일 생성 실패")
            else:
                print(f"  * 기존 DB 파일 유지 (경로: {self.db_path})")
            
            # 4. DB 엔진 초기화
            print("\n=== DB 엔진 초기화 ===")
            try:
                # SQLAlchemy 엔진 생성 시 SQLite 드라이버 명시적 지정
                db_url = f'sqlite:///{self.db_path}'
                print(f"  * DB URL: {db_url}")
                
                self.engine = create_engine(
                    db_url,
                    connect_args={
                        'check_same_thread': False,
                        'timeout': 60  # 연결 타임아웃 60초 설정 (원드라이브 잠금 대비)
                    },
                    pool_pre_ping=True,  # 연결 유효성 확인
                    echo=False  # SQL 로그 비활성화
                )
                
                @event.listens_for(self.engine, "connect")
                def set_sqlite_pragma(dbapi_connection, connection_record):
                    cursor = dbapi_connection.cursor()
                    cursor.execute("PRAGMA foreign_keys=ON")
                    cursor.execute("PRAGMA journal_mode=WAL")
                    cursor.close()
                
                # 연결 테스트
                with self.engine.connect() as conn:
                    conn.execute(text("SELECT sqlite_version()"))
                print("  * 엔진 생성 및 연결 테스트 완료")
                
            except Exception as e:
                if self.engine:
                    self.engine.dispose()
                    self.engine = None
                raise RuntimeError(f"DB 엔진 초기화 실패: {e}")
            
            # 5. 스키마 생성 및 검증
            print("\n=== 스키마 초기화 ===")
            try:
                # 마이그레이션 실행
                self._check_and_run_migrations()
                print("  * 마이그레이션 완료")
                
                # 테이블 생성
                Base.metadata.create_all(self.engine)
                inspector = inspect(self.engine)
                tables = inspector.get_table_names()
                print(f"  * 테이블 생성 완료: {', '.join(tables)}")
                # 변경 추적 보장 (트리거/로그)
                self.ensure_change_tracking()
                
                # 세션 팩토리 생성
                self.Session = sessionmaker(bind=self.engine)
                with self.Session() as test_session:
                    test_session.execute(text("SELECT 1"))
                print("  * 세션 팩토리 생성 및 테스트 완료")
                
            except Exception as e:
                if self.engine:
                    self.engine.dispose()
                    self.engine = None
                self.Session = None
                raise RuntimeError(f"스키마 초기화 실패: {e}")
            
            # 6. 초기 설정
            if is_new_db and on_initial_setup:
                print("\n=== 초기 설정 ===")
                try:
                    on_initial_setup()
                    print("  * 초기 설정 완료")
                except Exception as e:
                    print(f"  * [경고] 초기 설정 실패 (무시): {e}")
            
            self._save_init_state(True)
            print(f"\n[DB 설정 완료]\n{'='*50}\n")
            
        except Exception as e:
            print(f"\n[치명적 오류] DB 설정 실패:")
            print(f"  {str(e)}")
            print(f"  {repr(e)}")
            if self.engine:
                self.engine.dispose()
                self.engine = None
            self.Session = None
            raise RuntimeError(f"DB 설정 실패: {e}")

    def get_session(self):
        if not self.Session:
            raise RuntimeError("Database is not set up. Call setup_database() first.")
        return self.Session()

    def dispose_engine(self):
        """엔진을 정리하고 관련 파일들을 정리합니다."""
        print(f"[DEBUG] dispose_engine 호출됨")
        
        if self.engine:
            try:
                print(f"[DEBUG] DB 엔진 정리 시작...")
                
                # 1. 모든 활성 연결 종료
                try:
                    # Connection pool 정리
                    self.engine.dispose()
                    print(f"[DEBUG] Connection pool 정리 완료")
                except Exception as pool_error:
                    print(f"[DEBUG] Connection pool 정리 중 오류: {pool_error}")
                
                # 2. WAL 모드 비활성화 시도 (가능한 경우)
                try:
                    # 새로운 연결로 WAL 모드 해제 시도
                    temp_engine = create_engine(
                        f'sqlite:///{self.db_path}',
                        connect_args={'check_same_thread': False}
                    )
                    with temp_engine.connect() as conn:
                        conn.execute(text("PRAGMA journal_mode=DELETE"))
                        conn.commit()
                    temp_engine.dispose()
                    print(f"[DEBUG] WAL 모드 비활성화 완료")
                except Exception as wal_error:
                    print(f"[DEBUG] WAL 모드 비활성화 실패 (무시): {wal_error}")
                
                # 3. 엔진과 세션 객체 정리
                self.engine = None
                self.Session = None
                print(f"[DEBUG] 엔진 객체 정리 완료")
                
                # 4. 짧은 대기 시간 (파일 잠금 해제 대기)
                import time
                time.sleep(0.1)
                
                # 5. 관련 파일 정리
                try:
                    self.cleanup_db_files()
                    print(f"[DEBUG] DB 관련 파일 정리 완료")
                except Exception as cleanup_error:
                    print(f"[DEBUG] 파일 정리 중 오류: {cleanup_error}")
                
                print("[DEBUG] 데이터베이스 엔진 연결 해제 완료")
                
            except Exception as e:
                print(f"[ERROR] 엔진 정리 중 오류 발생: {e}")
                # 오류가 발생해도 객체는 정리
                self.engine = None
                self.Session = None
        else:
            print(f"[DEBUG] 정리할 엔진이 없음")

    def _run_migrations(self):
        print("데이터베이스 스키마 확인 및 업데이트 시작...")
        
        with self.engine.connect() as connection:
            inspector = inspect(self.engine)
            
            # 기존 DB의 모든 테이블 확인
            existing_tables = set(inspector.get_table_names())
            print(f"[정보] 기존 테이블: {', '.join(sorted(existing_tables)) if existing_tables else '없음'}")
            
            for table_name, table in Base.metadata.tables.items():
                try:
                    if table_name not in existing_tables:
                        # 테이블이 없으면 전체 생성
                        print(f"[정보] 테이블 '{table_name}' 생성 중...")
                        table.create(self.engine)
                        print(f"[완료] 테이블 '{table_name}' 생성 완료")
                        continue
                    
                    # 테이블이 있으면 컬럼 비교 - PRAGMA로 직접 확인
                    cursor = connection.execute(text(f"PRAGMA table_info({table_name})"))
                    existing_columns = {row[1] for row in cursor.fetchall()}
                    
                    print(f"[정보] {table_name} 테이블 기존 컬럼: {', '.join(sorted(existing_columns))}")
                    
                    # 필요한 컬럼 확인 및 추가
                    for column in table.c:
                        if column.name not in existing_columns:
                            try:
                                print(f"[정보] {table_name}.{column.name} 컬럼 추가 중...")
                                
                                # 트랜잭션 시작
                                trans = connection.begin()
                                
                                # 각 컬럼별로 직접 ALTER TABLE 실행
                                if table_name == 'clients':
                                    if column.name == 'name_en':
                                        connection.execute(text("ALTER TABLE clients ADD COLUMN name_en VARCHAR(100)"))
                                    elif column.name == 'change_log':
                                        connection.execute(text("ALTER TABLE clients ADD COLUMN change_log TEXT"))
                                elif table_name == 'materials':
                                    if column.name == 'name_en':
                                        connection.execute(text("ALTER TABLE materials ADD COLUMN name_en VARCHAR(255)"))
                                    elif column.name == 'origin':
                                        connection.execute(text("ALTER TABLE materials ADD COLUMN origin VARCHAR(100)"))
                                    elif column.name == 'supplier_id':
                                        connection.execute(text("ALTER TABLE materials ADD COLUMN supplier_id INTEGER"))
                                    elif column.name == 'change_log':
                                        connection.execute(text("ALTER TABLE materials ADD COLUMN change_log TEXT"))
                                    elif column.name == 'updated_at':
                                        connection.execute(text("ALTER TABLE materials ADD COLUMN updated_at DATETIME"))
                                else:
                                    # 기타 테이블은 기존 방식 사용
                                    from sqlalchemy.schema import CreateColumn
                                    column.default = None
                                    col_def = str(CreateColumn(column).compile(self.engine))
                                    col_def = col_def.replace('CREATE TABLE ', '').replace(f'{table_name} (', '').rstrip(')')
                                    alter_sql = f"ALTER TABLE {table_name} ADD COLUMN {col_def}"
                                    connection.execute(text(alter_sql))
                                
                                trans.commit()
                                print(f"[완료] 테이블 '{table_name}'에 컬럼 '{column.name}' 추가")
                                
                            except Exception as col_e:
                                # 컬럼 추가 실패는 경고만 출력 (이미 있거나 호환 불가)
                                print(f"[경고] 컬럼 '{table_name}.{column.name}' 추가 실패: {col_e}")
                                try:
                                    trans.rollback()
                                except:
                                    pass
                    
                    # materials 테이블의 경우 기존 client_id를 supplier_id로 복사
                    if table_name == 'materials':
                        try:
                            # supplier_id 컬럼이 있고, client_id 컬럼이 있으면 데이터 복사
                            cursor = connection.execute(text("PRAGMA table_info(materials)"))
                            mat_cols = {row[1] for row in cursor.fetchall()}
                            if 'supplier_id' in mat_cols and 'client_id' in mat_cols:
                                print(f"[정보] materials.client_id 데이터를 supplier_id로 복사 중...")
                                trans = connection.begin()
                                connection.execute(text("UPDATE materials SET supplier_id = client_id WHERE supplier_id IS NULL AND client_id IS NOT NULL"))
                                trans.commit()
                                print(f"[완료] 데이터 복사 완료")
                        except Exception as e:
                            print(f"[경고] 데이터 복사 실패: {e}")
                    
                    # DB에만 있고 코드에 없는 컬럼 확인 (정보성)
                    code_columns = {c.name for c in table.c}
                    extra_columns = existing_columns - code_columns
                    if extra_columns:
                        print(f"[정보] 테이블 '{table_name}'의 추가 컬럼 (백업 DB용): {', '.join(sorted(extra_columns))}")
                        
                except Exception as e:
                    print(f"[오류] 테이블 '{table_name}' 스키마 업데이트 실패: {e}")
        
        print("데이터베이스 스키마 확인 및 업데이트 완료.")

    def _check_and_run_migrations(self):
        with self.engine.connect() as connection:
            try:
                with connection.begin() as trans:
                    connection.execute(text("CREATE TABLE IF NOT EXISTS _schema_version (version INTEGER)"))
                    result = connection.execute(text("SELECT version FROM _schema_version")).scalar_one_or_none()
                    db_version = result if result is not None else 0

                    print(f"스키마 버전 확인: DB=v{db_version}, 코드=v{SCHEMA_VERSION}")
                    
                    # 항상 마이그레이션 실행 (누락된 컬럼 확인 및 추가)
                    self._run_migrations()
                    
                    # 버전 업데이트
                    if db_version != SCHEMA_VERSION:
                        connection.execute(text("DELETE FROM _schema_version"))
                        connection.execute(text(f"INSERT INTO _schema_version (version) VALUES ({SCHEMA_VERSION})"))
                        print(f"스키마 버전 업데이트: v{db_version} → v{SCHEMA_VERSION}")
            except Exception as e:
                print(f"스키마 버전 확인/업데이트 중 오류 발생: {e}")
                # 오류가 발생해도 계속 실행

    def ensure_change_tracking(self):
        """변경 추적용 change_log 테이블과 트리거를 생성합니다 (존재하지 않으면)."""
        try:
            with self.engine.connect() as conn:
                # change_log 테이블 생성 (확장 컬럼 포함)
                conn.execute(text(
                    """
                    CREATE TABLE IF NOT EXISTS change_log (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        table_name TEXT NOT NULL,
                        operation TEXT NOT NULL,
                        entity_id INTEGER,
                        entity_name TEXT,
                        changed_at TEXT NOT NULL DEFAULT (datetime('now'))
                    )
                    """
                ))

                # 확장 컬럼이 없으면 추가
                try:
                    res = conn.execute(text("PRAGMA table_info(change_log)")).fetchall()
                    cols = {r[1] for r in res}
                    if 'entity_id' not in cols:
                        conn.execute(text("ALTER TABLE change_log ADD COLUMN entity_id INTEGER"))
                    if 'entity_name' not in cols:
                        conn.execute(text("ALTER TABLE change_log ADD COLUMN entity_name TEXT"))
                except Exception as e:
                    print(f"[경고] change_log 확장 컬럼 추가 실패(무시): {e}")

                # 각 테이블별 이름 컬럼 매핑
                name_cols = {
                    'users': 'username',
                    'clients': 'name',
                    'materials': 'name',
                    'ingredients': 'name_ko',
                    'formulations': 'experiment_name',
                    'formulation_items': 'material_name',
                    # 생산 관련 테이블 변경 추적 추가
                    'production_formulations': 'product_name',
                    'production_steps': None,
                    'production_runs': None
                }
                tracked_tables = list(name_cols.keys())
                operations = [
                    ('ai', 'AFTER INSERT', 'INSERT'),
                    ('au', 'AFTER UPDATE', 'UPDATE'),
                    ('ad', 'AFTER DELETE', 'DELETE')
                ]

                for table in tracked_tables:
                    # 기존 트리거 제거 후 재생성 (이름/ID 기록을 위해)
                    for suffix, _, _ in operations:
                        trigger_name = f"trg_{table}_{suffix}"
                        try:
                            conn.execute(text(f"DROP TRIGGER IF EXISTS {trigger_name}"))
                        except Exception:
                            pass
                    name_col = name_cols.get(table, None)
                    for suffix, timing, op in operations:
                        trigger_name = f"trg_{table}_{suffix}"
                        # INSERT/UPDATE는 NEW, DELETE는 OLD 참조
                        ref = 'NEW' if op in ('INSERT', 'UPDATE') else 'OLD'
                        entity_id_expr = f"{ref}.id"
                        entity_name_expr = f"{ref}.{name_col}" if name_col else "NULL"
                        sql = f"""
                            CREATE TRIGGER {trigger_name}
                            {timing} ON {table}
                            BEGIN
                                INSERT INTO change_log(table_name, operation, entity_id, entity_name)
                                VALUES('{table}', '{op}', {entity_id_expr}, {entity_name_expr});
                            END;
                        """
                        conn.execute(text(sql))
        except Exception as e:
            print(f"[경고] 변경 추적 구성 실패(무시): {e}")

    def _save_init_state(self, state=True):
        """DB 초기화 상태를 config.ini에 저장"""
        if not self.config_path:
            return
            
        try:
            config = configparser.ConfigParser(interpolation=None)
            config.read(self.config_path, encoding='utf-8')
            
            if not config.has_section('Database'):
                config.add_section('Database')
            
            config.set('Database', 'initialized', str(state))
            
            with open(self.config_path, 'w', encoding='utf-8') as f:
                config.write(f)
                
            print(f"[DEBUG] DB 초기화 상태 저장: {state}")
        except Exception as e:
            print(f"[ERROR] 초기화 상태 저장 실패: {e}")

    def _check_init_state(self):
        """DB 초기화 상태 확인"""
        if not self.config_path:
            return False
            
        try:
            config = configparser.ConfigParser(interpolation=None)
            config.read(self.config_path, encoding='utf-8')
            return config.getboolean('Database', 'initialized', fallback=False)
        except Exception as e:
            print(f"[ERROR] 초기화 상태 확인 실패: {e}")
            return False

    def has_users(self) -> bool:
        # 초기화 상태와 관계없이 실제 사용자 수를 확인
        session = self.get_session()
        try:
            count = session.query(User).count()
            print(f"[DEBUG] 전체 사용자 수: {count}")
            if count > 0:
                self._save_init_state(True)
            return count > 0
        except Exception as e:
            print(f"[ERROR] has_users 확인 중 오류: {e}")
            return False
        finally:
            session.close()

    def create_default_admin(self):
        print("\n=== 기본 관리자 계정 생성 시작 ===")
        session = self.get_session()
        try:
            # 1. 기존 admin 계정 확인
            admin_user = session.query(User).filter_by(username='admin').first()
            print(f"  * 기존 admin 계정 존재 여부: {admin_user is not None}")
            
            if not admin_user:
                # 2. 새 admin 계정 생성
                try:
                    hashed_password = bcrypt.hashpw('admin1234!'.encode('utf-8'), bcrypt.gensalt())
                    new_admin = User(
                        username='admin',
                        password=hashed_password.decode('utf-8'),
                        is_admin=True,
                        position='시스템 관리자'
                    )
                    session.add(new_admin)
                    session.commit()
                    print("  * 기본 관리자 계정(admin) 생성 성공")
                    
                    # 3. 생성 확인
                    created_admin = session.query(User).filter_by(username='admin').first()
                    if created_admin:
                        print(f"  * 생성된 계정 확인: {created_admin.username} (관리자: {created_admin.is_admin})")
                    else:
                        print("  * [경고] 계정이 생성되었으나 확인할 수 없음")
                        
                except Exception as e:
                    print(f"  * [오류] 관리자 계정 생성 실패: {e}")
                    session.rollback()
                    raise
            else:
                print("  * 기존 admin 계정이 이미 존재함")
        except Exception as e:
            print(f"  * [치명적 오류] 관리자 계정 처리 실패: {e}")
            raise
        finally:
            session.close()
            print("=== 기본 관리자 계정 생성 완료 ===\n")

    def get_admin_user_count(self) -> int:
        session = self.get_session()
        try:
            count = session.query(User).filter_by(is_admin=True).count()
            print(f"[DEBUG] 관리자 사용자 수: {count}")
            return count
        except Exception as e:
            print(f"[ERROR] 관리자 수 확인 중 오류: {e}")
            return 0
        finally:
            session.close()

    def delete_user_by_username(self, username: str) -> bool:
        session = self.get_session()
        try:
            user = session.query(User).filter_by(username=username).first()
            if user:
                session.delete(user)
                session.commit()
                return True
            return False
        except Exception as e:
            session.rollback()
            print(f"사용자 '{username}' 삭제 중 오류: {e}")
            return False
        finally:
            session.close()

    def verify_user(self, username, password):
        session = self.get_session()
        try:
            user = session.query(User).filter_by(username=username).first()
            if user and bcrypt.checkpw(password.encode('utf-8'), user.password.encode('utf-8')):
                print(f"{datetime.now()}: 사용자 '{username}' 인증 성공")
                # User 객체를 그대로 반환 (권한 메서드 사용 가능)
                return user
            print(f"{datetime.now()}: 사용자 '{username}' 인증 실패")
            return None
        finally:
            # User 객체를 반환하므로 세션을 닫으면 안 됨
            # 대신 detached 상태로 만듦
            if user:
                session.expunge(user)  # 세션에서 분리
            session.close()

    def get_user_settings(self, username):
        session = self.get_session()
        try:
            user = session.query(User).filter_by(username=username).first()
            if user:
                return {"remember_id": user.remember_id, "auto_login": user.auto_login}
            return None
        finally:
            session.close()

    def update_user_settings(self, username, remember_id, auto_login):
        session = self.get_session()
        try:
            user = session.query(User).filter_by(username=username).first()
            if user:
                user.remember_id = remember_id
                user.auto_login = auto_login
                session.commit()
                print(f"{datetime.now()}: DB에 '{username}'의 설정 업데이트 성공")
                return True
            return False
        except Exception as e:
            session.rollback()
            print(f"{datetime.now()}: DB 설정 업데이트 실패: {e}")
            return False
        finally:
            session.close()

    def get_all_clients(self):
        session = self.get_session()
        try:
            clients = session.query(Client.name).order_by(Client.name).all()
            return clients
        finally:
            session.close()

    def get_unique_client_types(self):
        session = self.get_session()
        try:
            types = session.query(Client.client_type).filter(Client.client_type != None, Client.client_type != '').distinct().all()
            return sorted([t[0] for t in types])
        finally:
            session.close()

    def search_materials(self, search_term: str, load_ingredients: bool = False, search_ingredients: bool = False):
        session = self.get_session()
        try:
            query = session.query(Material).filter(Material.is_active == True)
            options = [joinedload(Material.supplier)]
            if load_ingredients:
                options.append(subqueryload(Material.ingredients))
            query = query.options(*options)

            if search_term:
                search_pattern = f"%{search_term}%"
                filters = [
                    Material.name.like(search_pattern),
                    Material.code.like(search_pattern),
                    Client.name.like(search_pattern),
                    Material.manufacturer.like(search_pattern),
                    Material.name_en.like(search_pattern),
                    Material.origin.like(search_pattern),
                    Material.hs_code.like(search_pattern),
                    Material.nmpa_reg_num.like(search_pattern)
                ]
                if search_ingredients:
                    query = query.outerjoin(Material.ingredients)
                    filters.extend([
                        Ingredient.name_ko.like(search_pattern),
                        Ingredient.name_en.like(search_pattern),
                        Ingredient.cas_no.like(search_pattern)
                    ])
                query = query.outerjoin(Material.supplier).filter(or_(*filters))
            
            results = query.distinct().order_by(Material.code).all()
            return results
        finally:
            session.close()

    def search_clients(self, search_term: str):
        session = self.get_session()
        try:
            query = session.query(Client)
            if search_term:
                search_pattern = f"%{search_term}%"
                query = query.filter(
                    or_(
                        Client.name.like(search_pattern),
                        Client.business_number.like(search_pattern),
                        Client.ceo_name.like(search_pattern),
                        Client.manager_name.like(search_pattern)
                    )
                )
            return query.order_by(Client.name).all()
        finally:
            session.close()

    def update_formulation_field(self, formulation_id, field_name, value):
        session = self.get_session()
        try:
            formulation = session.query(Formulation).filter_by(id=formulation_id).first()
            if formulation:
                setattr(formulation, field_name, value)
                session.commit()
                return True
            return False
        except Exception as e:
            session.rollback()
            return False
        finally:
            session.close()

    def execute_query(self, query, params=None):
        try:
            with self.Session() as session:
                result = session.execute(text(query), params or {})
                rows = result.fetchall()
                return [dict(row) for row in rows]
        except Exception as e:
            print(f"Query execution failed: {str(e)}")
            raise

    # --- Data Reset Methods ---
    def reset_all_data(self, session):
        session.query(FormulationItem).delete(synchronize_session=False)
        session.query(Formulation).delete(synchronize_session=False)
        session.query(Material).delete(synchronize_session=False)
        session.query(Client).delete(synchronize_session=False)
        session.query(User).filter(User.username != 'admin').delete(synchronize_session=False)
        print("모든 데이터가 리셋되었습니다 (admin 계정 제외).")

    def reset_users_data(self, session):
        session.query(User).filter(User.username != 'admin').delete(synchronize_session=False)
        print("사용자 데이터가 리셋되었습니다 (admin 계정 제외).")

    def reset_clients_data(self, session):
        session.query(Material).update({Material.supplier_id: None}, synchronize_session=False)
        session.query(Formulation).update({Formulation.target_client_id: None, Formulation.oem_odm_client_id: None}, synchronize_session=False)
        session.query(Client).delete(synchronize_session=False)
        print("거래처 데이터가 리셋되었습니다.")

    def reset_materials_data(self, session):
        session.query(FormulationItem).update({FormulationItem.material_id: None}, synchronize_session=False)
        session.query(Material).delete(synchronize_session=False)
        print("원료 데이터가 리셋되었습니다.")

    def has_admin_users(self):
        """시스템에 관리자 권한 사용자가 이미 존재하는지 확인합니다."""
        session = self.get_session()
        try:
            # is_admin=True이거나 role이 'MSAD' 또는 'RQD'인 사용자 확인 (정책: RQD=마스터)
            admin_count = session.query(User).filter(
                or_(User.is_admin == True, User.role.in_(['MSAD', 'RQD']))
            ).count()
            return admin_count > 0
        except Exception as e:
            print(f"관리자 존재 여부 확인 중 오류: {e}")
            return False
        finally:
            session.close()

db_manager = DBManager()
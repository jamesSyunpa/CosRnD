import os
import sys
import bcrypt
import shutil
from sqlalchemy import create_engine, text, event, inspect, or_
import configparser
from sqlalchemy.orm import sessionmaker, joinedload, subqueryload
from datetime import datetime
from types import SimpleNamespace

from database.models import Base, User, Client, Material, Ingredient, Formulation, FormulationItem

SCHEMA_VERSION = 11

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
            if os.path.exists(db_path):
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
            
            if os.path.exists(db_path):
                file_size = os.path.getsize(db_path)
                print(f"  * 새 DB 파일 생성됨 ({file_size} bytes)")
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
        print("설정 파일 경로:", self.config_path)
        if not self.config_path or not os.path.exists(self.config_path):
            print("설정 파일이 없음, 기본값 'data' 사용")
            return 'data'
            
        try:
            config = configparser.ConfigParser(interpolation=None)
            config.read(self.config_path, encoding='utf-8')
            db_dir = config.get('Paths', 'database_dir', fallback='data')
            print(f"config.ini에서 읽은 database_dir: {db_dir}")
            return db_dir
        except Exception as e:
            print(f"설정 파일 읽기 실패: {e}, 기본값 'data' 사용")
            return 'data'

    def get_local_db_path(self) -> str:
        if not self.application_path:
            return None
        db_dir = os.path.join(self.application_path, self.get_db_relative_path())
        return os.path.join(db_dir, "cosmetic.db")

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
        
        # 1. 기본 경로 설정
        local_db_path = os.path.join(application_path, self.get_db_relative_path(), "cosmetic.db")
        os.makedirs(os.path.dirname(local_db_path), exist_ok=True)
        shared_db_path = config.get('Paths', 'shared_db_path', fallback=None)

        # Normalize shared_db_path: config stores only the folder. If a full file
        # path was stored, handle gracefully, but prefer folder paths.
        def resolve_shared_file(path):
            if not path:
                return None
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
        if not shared_db_path and not os.path.exists(local_db_path):
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
        # Try using shared DB file if it exists (shared_db_file resolves folder->file)
        if shared_db_file and os.path.exists(shared_db_file):
            try:
                print(f"[INFO] 공유 DB 파일 확인: {shared_db_file}")
                self.db_path = shared_db_file

                # 공유 DB 연결 엔진 생성
                test_engine = create_engine(
                    f'sqlite:///{shared_db_file}',
                    connect_args={'check_same_thread': False}
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
                print(f"[경고] 공유 DB 연결 실패: {e}")
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
            print(f"  * DB 경로: {self.db_path}")
            
            # 2. DB 파일 처리
            is_new_db = not os.path.exists(self.db_path)
            self.cleanup_db_files()
            
            # 3. DB 파일 생성
            if not self._create_new_db_file(self.db_path):
                raise RuntimeError("DB 파일 생성 실패")
            
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
                        'timeout': 30  # 연결 타임아웃 설정
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
        inspector = inspect(self.engine)
        with self.engine.connect() as connection:
            for table_name, table in Base.metadata.tables.items():
                try:
                    existing_columns = {c['name'] for c in inspector.get_columns(table_name)}
                    for column in table.c:
                        if column.name not in existing_columns:
                            from sqlalchemy.schema import CreateColumn
                            column.default = None
                            # SQLite에서는 ALTER TABLE ... ADD COLUMN 구문이 필요
                            col_def = str(CreateColumn(column).compile(self.engine))
                            alter_sql = f"ALTER TABLE {table_name} ADD COLUMN {col_def}"
                            with connection.begin() as trans:
                                connection.execute(text(alter_sql))
                                print(f"테이블 '{table_name}'에 누락된 컬럼 '{column.name}' 추가 완료.")
                except Exception as e:
                    if "no such table" in str(e).lower():
                        print(f"테이블 '{table_name}'이(가) 아직 생성되지 않았습니다. create_all에서 생성됩니다.")
                    else:
                        print(f"테이블 '{table_name}' 스키마 업데이트 중 오류 발생: {e}")
        # 누락된 테이블 생성 보장 (공유 DB 경로에서도 동작하도록)
        try:
            Base.metadata.create_all(self.engine)
        except Exception as e:
            print(f"[경고] create_all 수행 중 오류(무시): {e}")
        print("데이터베이스 스키마 확인 및 업데이트 완료.")

    def _check_and_run_migrations(self):
        with self.engine.connect() as connection:
            try:
                with connection.begin() as trans:
                    connection.execute(text("CREATE TABLE IF NOT EXISTS _schema_version (version INTEGER)"))
                    result = connection.execute(text("SELECT version FROM _schema_version")).scalar_one_or_none()
                    db_version = result if result is not None else 0

                    if db_version < SCHEMA_VERSION:
                        print(f"스키마 버전 불일치 (DB: v{db_version}, 코드: v{SCHEMA_VERSION}). 마이그레이션 시작.")
                        self._run_migrations()
                        connection.execute(text("DELETE FROM _schema_version"))
                        connection.execute(text(f"INSERT INTO _schema_version (version) VALUES ({SCHEMA_VERSION})"))
            except Exception as e:
                print(f"스키마 버전 확인/업데이트 중 오류 발생: {e}")

    def ensure_change_tracking(self):
        """변경 추적용 change_log 테이블과 트리거를 생성합니다 (존재하지 않으면)."""
        try:
            with self.engine.connect() as conn:
                # change_log 테이블 생성
                conn.execute(text(
                    """
                    CREATE TABLE IF NOT EXISTS change_log (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        table_name TEXT NOT NULL,
                        operation TEXT NOT NULL,
                        changed_at TEXT NOT NULL DEFAULT (datetime('now'))
                    )
                    """
                ))

                tracked_tables = [
                    'users', 'clients', 'materials', 'ingredients', 'formulations', 'formulation_items'
                ]
                operations = [
                    ('ai', 'AFTER INSERT', 'INSERT'),
                    ('au', 'AFTER UPDATE', 'UPDATE'),
                    ('ad', 'AFTER DELETE', 'DELETE')
                ]

                for table in tracked_tables:
                    for suffix, timing, op in operations:
                        trigger_name = f"trg_{table}_{suffix}"
                        sql = f"""
                            CREATE TRIGGER IF NOT EXISTS {trigger_name}
                            {timing} ON {table}
                            BEGIN
                                INSERT INTO change_log(table_name, operation) VALUES('{table}', '{op}');
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
                    Client.name.like(search_pattern)
                ]
                if search_ingredients:
                    query = query.outerjoin(Material.ingredients)
                    filters.extend([
                        Ingredient.name_ko.like(search_pattern),
                        Ingredient.name_en.like(search_pattern)
                    ])
                query = query.outerjoin(Material.supplier).filter(or_(*filters))
            
            results = query.distinct().order_by(Material.code).all()
            return results
        finally:
            session.close()

    def search_clients(self, search_term: str):
        session = self.get_session()
        try:
            query = session.query(Client).filter(
                or_(Client.client_type != '원료', Client.client_type == None)
            )
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
        session.query(Material).update({Material.client_id: None}, synchronize_session=False)
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
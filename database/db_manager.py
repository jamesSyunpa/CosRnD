import os
import sys
import bcrypt
from sqlalchemy import create_engine, text, event, inspect
import configparser
from sqlalchemy.orm import sessionmaker, joinedload
from datetime import datetime

from database.models import Base, User, Client, Material, Ingredient, Formulation

# --- 스키마 버전 관리 ---
SCHEMA_VERSION = 10
class DBManager:
    _instance = None

    def __new__(cls, *args, **kwargs):
        if not cls._instance:
            cls._instance = super(DBManager, cls).__new__(cls)
        return cls._instance

    def __init__(self):
        if not hasattr(self, 'initialized'):  # 초기화가 한번만 되도록 보장
            self.engine = None
            self.Session = None
            self.initialized = True
            self.on_initial_setup_callback = None

    def setup_database(self, application_path: str, config_path: str, on_initial_setup=None):
        """설정 파일(config.ini)을 읽어 데이터베이스를 설정하고 초기화합니다."""
        config = configparser.ConfigParser()
        config.read(config_path, encoding='utf-8')
        db_dir_relative = config.get('Paths', 'database_dir', fallback='data')
        
        db_dir = os.path.join(application_path, db_dir_relative)
        db_filename = "cosmetic.db"
        db_path = os.path.join(db_dir, db_filename)

        print(f"\n{'='*50}\n[DB 설정 시작]")
        print(f"  - 실행 경로: {application_path}")
        print(f"  - 설정된 DB 상대 경로: {db_dir_relative}")
        print(f"  - DB 경로: {db_path}")

        # DB 파일이 위치할 디렉토리가 없으면 생성합니다.
        os.makedirs(db_dir, exist_ok=True)
        is_new_db = not os.path.exists(db_path)
        db_url = f'sqlite:///{db_path}'
        print(f"  - 연결 URL: {db_url}")
        self.engine = create_engine(db_url, connect_args={'check_same_thread': False})

        # 모든 연결 시 PRAGMA foreign_keys=ON 실행
        @event.listens_for(self.engine, "connect")
        def set_sqlite_pragma(dbapi_connection, connection_record):
            cursor = dbapi_connection.cursor()
            cursor.execute("PRAGMA foreign_keys=ON")
            cursor.close()

        # 스키마 마이그레이션 및 테이블 생성
        self._check_and_run_migrations()
        Base.metadata.create_all(self.engine)

        self.Session = sessionmaker(bind=self.engine)

        # DB가 새로 생성된 경우에만 초기 설정 콜백 호출
        if is_new_db and on_initial_setup:
            on_initial_setup()
        print(f"[DB 설정 완료]\n{'='*50}\n")

    def get_session(self):
        """새로운 데이터베이스 세션을 반환합니다."""
        if not self.Session:
            raise RuntimeError("Database is not set up. Call setup_database() first.")
        return self.Session()

    def dispose_engine(self):
        """데이터베이스 엔진의 모든 연결을 해제합니다."""
        if self.engine:
            self.engine.dispose()
            self.engine = None
            self.Session = None
            print("데이터베이스 엔진 연결이 해제되었습니다.")

    def _run_migrations(self):
        """
        데이터베이스 스키마를 확인하고 누락된 컬럼을 추가하는 간단한 마이그레이션 실행.
        """
        print("데이터베이스 스키마 확인 및 업데이트 시작...")
        inspector = inspect(self.engine)
        with self.engine.connect() as connection:
            # 모든 모델의 테이블에 대해 반복
            for table_name, table in Base.metadata.tables.items():
                try:
                    # Inspector를 사용하여 실제 DB의 컬럼 정보 가져오기
                    existing_columns = {c['name'] for c in inspector.get_columns(table_name)}
                    
                    # 모델에 정의된 컬럼과 비교
                    for column in table.c:
                        if column.name not in existing_columns:
                            # SQLAlchemy의 DDL 컴파일러를 사용하여 ADD COLUMN 구문 생성
                            from sqlalchemy.schema import CreateColumn
                            # 트랜잭션 내에서 DDL 실행
                            with connection.begin() as trans:
                                add_column_ddl = str(CreateColumn(column).compile(self.engine))
                                connection.execute(text(add_column_ddl))
                                print(f"테이블 '{table_name}'에 누락된 컬럼 '{column.name}' 추가 완료.")
                except Exception as e:
                    # 테이블이 아직 존재하지 않는 경우 등 예외 처리
                    if "no such table" in str(e):
                        print(f"테이블 '{table_name}'이(가) 아직 생성되지 않았습니다. create_all에서 생성됩니다.")
                    else:
                        print(f"테이블 '{table_name}' 스키마 업데이트 중 오류 발생: {e}")
        print("데이터베이스 스키마 확인 및 업데이트 완료.")

    def _check_and_run_migrations(self):
        """데이터베이스의 스키마 버전을 확인하고, 필요한 경우 마이그레이션을 실행합니다."""
        with self.engine.connect() as connection:
            try:
                # 트랜잭션 시작
                with connection.begin() as trans:
                    # _schema_version 테이블이 없으면 생성
                    connection.execute(text("CREATE TABLE IF NOT EXISTS _schema_version (version INTEGER)"))
                    
                    # 현재 DB 버전 확인
                    result = connection.execute(text("SELECT version FROM _schema_version")).scalar_one_or_none()
                    db_version = result if result is not None else 0

                    if db_version < SCHEMA_VERSION:
                        print(f"스키마 버전 불일치 (DB: v{db_version}, 코드: v{SCHEMA_VERSION}). 마이그레이션 시작.")
                        self._run_migrations()
                        # 새 버전으로 업데이트
                        connection.execute(text("DELETE FROM _schema_version"))
                        connection.execute(text(f"INSERT INTO _schema_version (version) VALUES ({SCHEMA_VERSION})"))
            except Exception as e:
                print(f"스키마 버전 확인/업데이트 중 오류 발생: {e}")

    def create_default_admin(self):
        """기본 관리자 계정(admin)이 없으면 생성합니다."""
        session = self.get_session()
        try:
            admin_user = session.query(User).filter_by(username='admin').first()
            if not admin_user:
                hashed_password = bcrypt.hashpw('admin1234!'.encode('utf-8'), bcrypt.gensalt())
                new_admin = User(
                    username='admin',
                    password=hashed_password.decode('utf-8'),
                    is_admin=True
                )
                session.add(new_admin)
                session.commit()
                print("기본 관리자 계정(admin)이 생성되었습니다.")
        finally:
            session.close()

    def has_users(self) -> bool:
        """데이터베이스에 사용자가 한 명이라도 있는지 확인합니다."""
        session = self.get_session()
        try:
            return session.query(User).count() > 0
        finally:
            session.close()

    def get_admin_user_count(self) -> int:
        """관리자 계정의 수를 반환합니다."""
        session = self.get_session()
        try:
            return session.query(User).filter_by(is_admin=True).count()
        finally:
            session.close()

    def delete_user_by_username(self, username: str) -> bool:
        """사용자 이름으로 사용자를 삭제합니다."""
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
        """
        사용자 이름과 비밀번호를 확인하고, 성공 시 사용자 객체(User Object)를 반환합니다.
        """
        session = self.get_session()
        try:
            user = session.query(User).filter_by(username=username).first()
            if user and bcrypt.checkpw(password.encode('utf-8'), user.password.encode('utf-8')):
                print(f"{datetime.now()}: 사용자 '{username}' 인증 성공")
                # 딕셔너리 대신 사용자 객체 자체를 반환하도록 수정
                return user
            print(f"{datetime.now()}: 사용자 '{username}' 인증 실패")
            return None
        finally:
            session.close()

    def get_user_settings(self, username):
        """
        특정 사용자의 설정 정보(remember_id, auto_login)를 딕셔너리로 가져옵니다.
        """
        session = self.get_session()
        try:
            user = session.query(User).filter_by(username=username).first()
            if user:
                return {"remember_id": user.remember_id, "auto_login": user.auto_login}
            return None
        finally:
            session.close()

    def update_user_settings(self, username, remember_id, auto_login):
        """
        사용자의 remember_id와 auto_login 설정을 업데이트합니다.
        """
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
        """거래처 전체 목록을 (이름,) 튜플 리스트로 반환"""
        session = self.get_session()
        try:
            clients = session.query(Client.name).order_by(Client.name).all()
            return clients
        finally:
            session.close()

    def get_unique_client_types(self):
        """데이터베이스에서 중복되지 않는 모든 거래처 유형을 가져옵니다."""
        session = self.get_session()
        try:
            # client_type이 null이 아니고 비어있지 않은 경우만 조회
            types = session.query(Client.client_type).filter(Client.client_type != None, Client.client_type != '').distinct().all()
            return sorted([t[0] for t in types])
        finally:
            session.close()

    def search_materials(self, search_term: str):
        """원료명, 코드, 한글/영문 전성분으로 원료를 검색합니다."""
        session = self.get_session()
        try:
            # is_active가 True인 원료만 검색하도록 기본 필터 설정
            query = session.query(Material).filter(Material.is_active == True)
            
            if search_term:
                search_pattern = f"%{search_term}%"
                # 거래처(Client) 테이블과 조인하고, 검색 조건에 거래처명 추가
                query = query.join(Material.client, isouter=True).filter(
                    (Material.name.like(search_pattern)) |
                    (Material.code.like(search_pattern)) |
                    (Client.name.like(search_pattern)) |
                    (Material.ingredients.any(Ingredient.name_ko.like(search_pattern))) |
                    (Material.ingredients.any(Ingredient.name_en.like(search_pattern))) |
                    (Material.ingredients.any(Ingredient.cas_no.like(search_pattern)))
                )
            
            return query.options(joinedload(Material.ingredients)).distinct().order_by(Material.code).all()
        finally:
            session.close()

    def update_formulation_field(self, formulation_id, field_name, value):
        """특정 처방의 단일 필드를 업데이트합니다."""
        session = self.get_session()
        try:
            formulation = session.query(Formulation).filter_by(id=formulation_id).first()
            if formulation:
                setattr(formulation, field_name, value)
                session.commit()
                print(f"Formulation ID {formulation_id}의 '{field_name}' 필드가 업데이트되었습니다.")
                return True
            return False
        except Exception as e:
            session.rollback()
            print(f"Formulation 필드 업데이트 중 오류 발생: {e}")
            return False
        finally:
            session.close()

# 전역 DBManager 인스턴스 생성
db_manager = DBManager()

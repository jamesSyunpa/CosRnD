import os
import sys
import bcrypt
import shutil
from sqlalchemy import create_engine, text, event, inspect, or_
import configparser
from sqlalchemy.orm import sessionmaker, joinedload, subqueryload
from datetime import datetime

from database.models import Base, User, Client, Material, Ingredient, Formulation, FormulationItem

SCHEMA_VERSION = 10

class DBManager:
    _instance = None

    def __new__(cls, *args, **kwargs):
        if not cls._instance:
            cls._instance = super(DBManager, cls).__new__(cls)
        return cls._instance

    def __init__(self):
        if not hasattr(self, 'initialized'):
            self.engine = None
            self.Session = None
            self.initialized = True
            self.application_path = None
            self.config_path = None

    def get_db_relative_path(self) -> str:
        if not self.config_path:
            return 'data'
        config = configparser.ConfigParser()
        config.read(self.config_path, encoding='utf-8')
        return config.get('Paths', 'database_dir', fallback='data')

    def get_local_db_path(self) -> str:
        if not self.application_path:
            return None
        db_dir = os.path.join(self.application_path, self.get_db_relative_path())
        return os.path.join(db_dir, "cosmetic.db")

    def setup_database(self, application_path: str, config_path: str, on_initial_setup=None):
        self.application_path = application_path
        self.config_path = config_path

        config = configparser.ConfigParser()
        config.read(config_path, encoding='utf-8')
        shared_db_path = config.get('Paths', 'shared_db_path', fallback=None)

        db_path = self.get_local_db_path()
        is_new_db = not os.path.exists(db_path)

        if shared_db_path and os.path.exists(shared_db_path) and is_new_db:
            print(f"Local DB not found. Copying from shared DB: {shared_db_path}")
            try:
                os.makedirs(os.path.dirname(db_path), exist_ok=True)
                shutil.copy(shared_db_path, db_path)
                is_new_db = False
            except Exception as e:
                print(f"Failed to copy shared DB: {e}")

        print(f"\n{'='*50}\n[DB 설정 시작]")
        print(f"  - DB 경로: {db_path}")

        os.makedirs(os.path.dirname(db_path), exist_ok=True)
        db_url = f'sqlite:///{db_path}'
        self.engine = create_engine(db_url, connect_args={'check_same_thread': False})

        @event.listens_for(self.engine, "connect")
        def set_sqlite_pragma(dbapi_connection, connection_record):
            cursor = dbapi_connection.cursor()
            cursor.execute("PRAGMA foreign_keys=ON")
            cursor.close()

        self._check_and_run_migrations()
        Base.metadata.create_all(self.engine)

        self.Session = sessionmaker(bind=self.engine)

        if is_new_db and on_initial_setup:
            on_initial_setup()
        print(f"[DB 설정 완료]\n{'='*50}\n")

    def get_session(self):
        if not self.Session:
            raise RuntimeError("Database is not set up. Call setup_database() first.")
        return self.Session()

    def dispose_engine(self):
        if self.engine:
            self.engine.dispose()
            self.engine = None
            self.Session = None
            print("데이터베이스 엔진 연결이 해제되었습니다.")

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
                            add_column_ddl = str(CreateColumn(column).compile(self.engine))
                            with connection.begin() as trans:
                                connection.execute(text(add_column_ddl))
                                print(f"테이블 '{table_name}'에 누락된 컬럼 '{column.name}' 추가 완료.")
                except Exception as e:
                    if "no such table" in str(e).lower():
                        print(f"테이블 '{table_name}'이(가) 아직 생성되지 않았습니다. create_all에서 생성됩니다.")
                    else:
                        print(f"테이블 '{table_name}' 스키마 업데이트 중 오류 발생: {e}")
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

    def create_default_admin(self):
        session = self.get_session()
        try:
            admin_user = session.query(User).filter_by(username='admin').first()
            if not admin_user:
                hashed_password = bcrypt.hashpw('admin1234!'.encode('utf-8'), bcrypt.gensalt())
                new_admin = User(username='admin', password=hashed_password.decode('utf-8'), is_admin=True)
                session.add(new_admin)
                session.commit()
                print("기본 관리자 계정(admin)이 생성되었습니다.")
        finally:
            session.close()

    def has_users(self) -> bool:
        session = self.get_session()
        try:
            return session.query(User).count() > 0
        finally:
            session.close()

    def get_admin_user_count(self) -> int:
        session = self.get_session()
        try:
            return session.query(User).filter_by(is_admin=True).count()
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
                return user
            print(f"{datetime.now()}: 사용자 '{username}' 인증 실패")
            return None
        finally:
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

db_manager = DBManager()

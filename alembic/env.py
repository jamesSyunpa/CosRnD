from logging.config import fileConfig

from sqlalchemy import engine_from_config
from sqlalchemy import pool

from alembic import context

# this is the Alembic Config object, which provides
# access to the values within the .ini file in use.
config = context.config

# Interpret the config file for Python logging.
# This line sets up loggers basically.
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

import os
import sys

# 프로젝트 루트 경로 추가
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from database.models import Base
from database.db_manager import DBManager

target_metadata = Base.metadata

def get_engine():
    # DBManager를 통해 현재 설정된 엔진 가져오기
    # 초기화 시 엔진이 없을 수 있으므로 로컬 DB로 강제 초기화
    db_manager = DBManager()
    if db_manager.engine is None:
        db_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "cosrnd_db.sqlite3")
        db_manager._create_new_db_file(db_path) # 파일이 없으면 생성
        # 직접 엔진 생성하여 할당
        from sqlalchemy import create_engine
        db_manager.engine = create_engine(f'sqlite:///{db_path}')
        
    return db_manager.engine

def run_migrations_online() -> None:
    """Run migrations in 'online' mode."""
    connectable = get_engine()

    with connectable.connect() as connection:
        context.configure(
            connection=connection, target_metadata=target_metadata
        )

        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()

import os
import sys
import logging
from sqlalchemy import inspect
from database.models import Base
from database.db_manager import DBManager

# 로깅 설정
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("SchemaVerifier")

def verify_schema_integrity():
    """
    SQLAlchemy 모델과 실제 데이터베이스 스키마 간의 불일치를 검증합니다.
    """
    logger.info("데이터베이스 스키마 검증 시작...")
    
    # 1. DB 연결
    db_manager = DBManager()
    
    # 엔진이 초기화되지 않은 경우 강제로 로컬 DB 로드
    if db_manager.engine is None:
        db_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "cosrnd_db.sqlite3")
        if not os.path.exists(db_path):
             db_manager._create_new_db_file(db_path)
        
        from sqlalchemy import create_engine
        db_manager.engine = create_engine(f'sqlite:///{db_path}')
        
    engine = db_manager.engine
    inspector = inspect(engine)
    
    # 2. 테이블 목록 조회
    db_tables = inspector.get_table_names()
    model_tables = Base.metadata.tables.keys()
    
    missing_tables = set(model_tables) - set(db_tables)
    if missing_tables:
        logger.error(f"❌ 누락된 테이블 발견: {missing_tables}")
    else:
        logger.info("✅ 모든 테이블이 존재합니다.")
        
    # 3. 컬럼 검증
    all_matched = True
    for table_name in model_tables:
        if table_name not in db_tables:
            continue
            
        logger.info(f"[{table_name}] 검증 중...")
        
        # DB 컬럼 조회
        db_columns = {col['name']: col for col in inspector.get_columns(table_name)}
        
        # 모델 컬럼 조회
        model_columns = Base.metadata.tables[table_name].columns
        
        for col_name, col_def in model_columns.items():
            if col_name not in db_columns:
                logger.error(f"  ❌ [{table_name}] 컬럼 누락: {col_name}")
                all_matched = False
            else:
                # 데이터 타입 검증 (옵션)
                pass
                
    if all_matched:
        logger.info("✨ 스키마 검증 완료: 모든 모델 필드가 데이터베이스에 존재합니다.")
        return True
    else:
        logger.error("🔥 스키마 불일치가 발견되었습니다. 마이그레이션이 필요합니다.")
        return False

if __name__ == "__main__":
    success = verify_schema_integrity()
    sys.exit(0 if success else 1)

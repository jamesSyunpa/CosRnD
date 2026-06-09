
import sqlite3
import os
import shutil

db_path = r"C:\Users\neon5\Documents\RnD_데이터관리\data\cosmetic.db"
backup_path = r"C:\Users\neon5\Documents\RnD_데이터관리\data\cosmetic_backup_prod.db"

print(f"DB: {db_path}")

# 백업
shutil.copy2(db_path, backup_path)
print(f"백업: {backup_path}")

conn = sqlite3.connect(db_path)
cursor = conn.cursor()

print("\n=== production_formulations 테이블 확인 ===")
cursor.execute("PRAGMA table_info(production_formulations)")
current_cols = [row[1] for row in cursor.fetchall()]
print(f"현재 컬럼: {current_cols}")

# 필요한 컬럼: id, source_formulation_id, product_name, production_code, lab_no, revision,
#               base_weight_g, status, effective_date, approved_by_user_id, notes,
#               created_at, client_name, items_snapshot

needed_cols = {
    'client_name': 'TEXT',
    'items_snapshot': 'TEXT'
}

for col_name, col_type in needed_cols.items():
    if col_name not in current_cols:
        try:
            cursor.execute(f"ALTER TABLE production_formulations ADD COLUMN {col_name} {col_type}")
            print(f"OK: {col_name} 추가")
        except Exception as e:
            print(f"INFO: {col_name} - {e}")
    else:
        print(f"OK: {col_name} 이미 존재")

# production_steps, production_runs, ingredient_reports, ingredient_report_items,
# semi_finished_coa, semi_finished_coa_items, finished_product_coa, finished_product_coa_items,
# document_packages, document_package_links, document_attachments, change_log 테이블 확인

other_tables = [
    'production_steps', 'production_runs', 
    'ingredient_reports', 'ingredient_report_items',
    'semi_finished_coa', 'semi_finished_coa_items',
    'finished_product_coa', 'finished_product_coa_items',
    'document_packages', 'document_package_links', 'document_attachments',
    'change_log'
]

print("\n=== 기타 테이블 확인 ===")

for table in other_tables:
    cursor.execute(f"SELECT name FROM sqlite_master WHERE type='table' AND name='{table}'")
    exists = cursor.fetchone()
    
    if not exists:
        print(f"{table}: 테이블 없어서 생성해야함")
        
        # 각 테이블 생성 SQL
        if table == 'production_steps':
            cursor.execute("""
                CREATE TABLE production_steps (
                    id INTEGER NOT NULL,
                    production_formulation_id INTEGER NOT NULL,
                    step_no INTEGER,
                    phase VARCHAR(50),
                    instruction TEXT,
                    temperature VARCHAR(50),
                    time_min FLOAT,
                    rpm VARCHAR(50),
                    equipment VARCHAR(255),
                    notes TEXT,
                    created_at DATETIME,
                    PRIMARY KEY (id),
                    FOREIGN KEY(production_formulation_id) REFERENCES production_formulations (id)
                )
            """)
            print(f"OK: {table} 생성")
        
        elif table == 'production_runs':
            cursor.execute("""
                CREATE TABLE production_runs (
                    id INTEGER NOT NULL,
                    production_formulation_id INTEGER NOT NULL,
                    run_date DATE,
                    lot_no VARCHAR(100),
                    quantity_g FLOAT,
                    notes TEXT,
                    specific_gravity VARCHAR(50),
                    viscosity_initial VARCHAR(50),
                    viscosity_next_day VARCHAR(50),
                    ph_initial VARCHAR(50),
                    ph_next_day VARCHAR(50),
                    created_at DATETIME,
                    PRIMARY KEY (id),
                    FOREIGN KEY(production_formulation_id) REFERENCES production_formulations (id)
                )
            """)
            print(f"OK: {table} 생성")
        
        elif table == 'ingredient_reports':
            cursor.execute("""
                CREATE TABLE ingredient_reports (
                    id INTEGER NOT NULL,
                    product_name VARCHAR(255) NOT NULL,
                    manufacturer VARCHAR(255),
                    type_code VARCHAR(100),
                    functional_type_code VARCHAR(100),
                    functional_code VARCHAR(100),
                    usage VARCHAR(255),
                    custom_content TEXT,
                    created_at DATETIME NOT NULL,
                    updated_at DATETIME NOT NULL,
                    PRIMARY KEY (id)
                )
            """)
            print(f"OK: {table} 생성")
        
        elif table == 'ingredient_report_items':
            cursor.execute("""
                CREATE TABLE ingredient_report_items (
                    id INTEGER NOT NULL,
                    report_id INTEGER NOT NULL,
                    row_no INTEGER,
                    ingredient_name VARCHAR(255) NOT NULL,
                    PRIMARY KEY (id),
                    FOREIGN KEY(report_id) REFERENCES ingredient_reports (id)
                )
            """)
            print(f"OK: {table} 생성")
        
        elif table == 'semi_finished_coa':
            cursor.execute("""
                CREATE TABLE semi_finished_coa (
                    id INTEGER NOT NULL,
                    product_name VARCHAR(255) NOT NULL,
                    lot_no VARCHAR(100),
                    manufacture_date DATE,
                    test_date DATE,
                    examiner VARCHAR(100),
                    overall_result VARCHAR(100),
                    notes TEXT,
                    created_at DATETIME NOT NULL,
                    updated_at DATETIME NOT NULL,
                    PRIMARY KEY (id)
                )
            """)
            print(f"OK: {table} 생성")
        
        elif table == 'semi_finished_coa_items':
            cursor.execute("""
                CREATE TABLE semi_finished_coa_items (
                    id INTEGER NOT NULL,
                    header_id INTEGER NOT NULL,
                    seq_no INTEGER,
                    item_name VARCHAR(255),
                    spec VARCHAR(255),
                    result VARCHAR(255),
                    remark VARCHAR(255),
                    PRIMARY KEY (id),
                    FOREIGN KEY(header_id) REFERENCES semi_finished_coa (id)
                )
            """)
            print(f"OK: {table} 생성")
        
        elif table == 'finished_product_coa':
            cursor.execute("""
                CREATE TABLE finished_product_coa (
                    id INTEGER NOT NULL,
                    product_name VARCHAR(255) NOT NULL,
                    semi_mfg_date DATE,
                    semi_lot_no VARCHAR(100),
                    pack_date DATE,
                    finished_lot_no VARCHAR(100),
                    expiry_date DATE,
                    unit_volume_ml FLOAT,
                    sampling_method VARCHAR(255),
                    test_date DATE,
                    examiner VARCHAR(100),
                    reviewer VARCHAR(100),
                    overall_result VARCHAR(100),
                    notes TEXT,
                    created_at DATETIME NOT NULL,
                    updated_at DATETIME NOT NULL,
                    PRIMARY KEY (id)
                )
            """)
            print(f"OK: {table} 생성")
        
        elif table == 'finished_product_coa_items':
            cursor.execute("""
                CREATE TABLE finished_product_coa_items (
                    id INTEGER NOT NULL,
                    header_id INTEGER NOT NULL,
                    item_id VARCHAR(50),
                    item_name VARCHAR(255),
                    spec VARCHAR(255),
                    result VARCHAR(255),
                    note VARCHAR(255),
                    PRIMARY KEY (id),
                    FOREIGN KEY(header_id) REFERENCES finished_product_coa (id)
                )
            """)
            print(f"OK: {table} 생성")
        
        elif table == 'document_packages':
            cursor.execute("""
                CREATE TABLE document_packages (
                    id INTEGER NOT NULL,
                    name VARCHAR(255) NOT NULL,
                    formulation_id INTEGER,
                    production_formulation_id INTEGER,
                    product_name VARCHAR(255),
                    revision VARCHAR(50),
                    created_by_user_id INTEGER,
                    created_at DATETIME NOT NULL,
                    notes TEXT,
                    ingredient_snapshot TEXT,
                    quotation_snapshot TEXT,
                    PRIMARY KEY (id),
                    FOREIGN KEY(formulation_id) REFERENCES formulations (id),
                    FOREIGN KEY(production_formulation_id) REFERENCES production_formulations (id),
                    FOREIGN KEY(created_by_user_id) REFERENCES users (id)
                )
            """)
            print(f"OK: {table} 생성")
        
        elif table == 'document_package_links':
            cursor.execute("""
                CREATE TABLE document_package_links (
                    id INTEGER NOT NULL,
                    package_id INTEGER NOT NULL,
                    doc_type VARCHAR(50) NOT NULL,
                    ref_id INTEGER NOT NULL,
                    PRIMARY KEY (id),
                    FOREIGN KEY(package_id) REFERENCES document_packages (id)
                )
            """)
            print(f"OK: {table} 생성")
        
        elif table == 'document_attachments':
            cursor.execute("""
                CREATE TABLE document_attachments (
                    id INTEGER NOT NULL,
                    package_id INTEGER NOT NULL,
                    file_name VARCHAR(255) NOT NULL,
                    file_path TEXT NOT NULL,
                    attachment_type VARCHAR(50),
                    created_at DATETIME NOT NULL,
                    PRIMARY KEY (id),
                    FOREIGN KEY(package_id) REFERENCES document_packages (id)
                )
            """)
            print(f"OK: {table} 생성")
        
        elif table == 'change_log':
            cursor.execute("""
                CREATE TABLE change_log (
                    id INTEGER NOT NULL,
                    table_name TEXT NOT NULL,
                    operation TEXT NOT NULL,
                    entity_id INTEGER,
                    entity_name TEXT,
                    changed_at TEXT NOT NULL,
                    PRIMARY KEY (id)
                )
            """)
            print(f"OK: {table} 생성")
    else:
        print(f"{table}: 이미 존재")

conn.commit()
conn.close()

print("\n=== 완료! 이제 프로그램을 실행하세요 ===")

"""
생산 이력(ProductionRun) 테이블에 물성치 컬럼 추가 마이그레이션
- specific_gravity: 비중
- viscosity_initial: 점도(당일)
- viscosity_next_day: 점도(익일)
- ph_initial: pH(당일)
- ph_next_day: pH(익일)
"""

import sqlite3
import os

def migrate():
    # 가능한 데이터베이스 경로들
    possible_paths = [
        'cosmetic.db',
        os.path.join('data', 'cosmetic.db'),
        os.path.join('database', 'app.db')
    ]
    
    db_path = None
    for path in possible_paths:
        if os.path.exists(path):
            db_path = path
            break
    
    if not db_path:
        print(f"데이터베이스 파일을 찾을 수 없습니다.")
        return
    
    print(f"데이터베이스 파일: {db_path}")

    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    # 추가할 컬럼 목록
    columns_to_add = [
        ('specific_gravity', 'TEXT'),
        ('viscosity_initial', 'TEXT'),
        ('viscosity_next_day', 'TEXT'),
        ('ph_initial', 'TEXT'),
        ('ph_next_day', 'TEXT'),
    ]

    for col_name, col_type in columns_to_add:
        try:
            cursor.execute(f"ALTER TABLE production_runs ADD COLUMN {col_name} {col_type}")
            print(f"✓ {col_name} 컬럼이 추가되었습니다.")
        except sqlite3.OperationalError as e:
            if 'duplicate column name' in str(e).lower():
                print(f"- {col_name} 컬럼이 이미 존재합니다.")
            else:
                print(f"✗ {col_name} 추가 중 오류: {e}")

    conn.commit()
    conn.close()
    print("\n마이그레이션이 완료되었습니다.")

if __name__ == '__main__':
    migrate()

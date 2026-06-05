import sys
import os
sys.path.append(os.getcwd())
from database.db_manager import db_manager
from database.models import Ingredient, Material
from sqlalchemy import func

def check_duplicates():
    # Initialize DB
    current_dir = os.getcwd()
    config_path = os.path.join(current_dir, 'config.ini')
    db_manager.setup_database(application_path=current_dir, config_path=config_path)

    session = db_manager.get_session()
    try:
        # Find duplicates based on material_id, name_ko, name_en, cas_no
        duplicates = session.query(
            Ingredient.material_id,
            Ingredient.name_ko,
            Ingredient.name_en,
            Ingredient.cas_no,
            func.count(Ingredient.id)
        ).group_by(
            Ingredient.material_id,
            Ingredient.name_ko,
            Ingredient.name_en,
            Ingredient.cas_no
        ).having(func.count(Ingredient.id) > 1).all()

        if duplicates:
            print(f"Found {len(duplicates)} sets of duplicate ingredients:")
            for dup in duplicates:
                print(f"Material ID: {dup[0]}, Name: {dup[1]}, Count: {dup[4]}")
                
                # Get the material code/name for context
                mat = session.query(Material).get(dup[0])
                if mat:
                    print(f"  -> Material: {mat.code} ({mat.name})")
        else:
            print("No duplicate ingredients found in the database.")

    finally:
        session.close()

if __name__ == "__main__":
    check_duplicates()

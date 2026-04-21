import sys
import os
sys.path.append(os.getcwd())
from database.db_manager import db_manager
from database.models import Ingredient
from sqlalchemy import func

def fix_duplicates():
    # Initialize DB
    current_dir = os.getcwd()
    config_path = os.path.join(current_dir, 'config.ini')
    db_manager.setup_database(application_path=current_dir, config_path=config_path)

    session = db_manager.get_session()
    try:
        print("Searching for duplicates...")
        # Find duplicates based on material_id, name_ko, name_en, cas_no
        # We want to find groups of duplicates
        duplicates_query = session.query(
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
        ).having(func.count(Ingredient.id) > 1)

        duplicate_groups = duplicates_query.all()
        
        if not duplicate_groups:
            print("No duplicates found.")
            return

        print(f"Found {len(duplicate_groups)} groups of duplicates. Starting cleanup...")
        
        total_deleted = 0
        
        for group in duplicate_groups:
            mat_id, name_ko, name_en, cas_no, count = group
            
            # Get all ingredients in this group
            query = session.query(Ingredient).filter(
                Ingredient.material_id == mat_id,
                Ingredient.name_ko == name_ko,
                Ingredient.name_en == name_en
            )
            
            # Handle NULL cas_no
            if cas_no is None:
                query = query.filter(Ingredient.cas_no.is_(None))
            else:
                query = query.filter(Ingredient.cas_no == cas_no)
                
            ingredients = query.order_by(Ingredient.id).all()
            
            # Keep the first one, delete the rest
            if len(ingredients) > 1:
                to_delete = ingredients[1:]
                for ing in to_delete:
                    session.delete(ing)
                total_deleted += len(to_delete)
                
        session.commit()
        print(f"Cleanup complete. Deleted {total_deleted} duplicate ingredients.")

    except Exception as e:
        session.rollback()
        print(f"Error during cleanup: {e}")
    finally:
        session.close()

if __name__ == "__main__":
    fix_duplicates()

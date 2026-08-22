import sys
import os

# Add the current directory to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from database.db_manager import db_manager
from sqlalchemy import inspect, text

# Set up config and application path
config_path = None
application_path = os.path.dirname(os.path.abspath(__file__))

# Find config.ini
config_candidates = [
    application_path,
    os.path.join(os.path.expanduser('~'), 'AppData', 'Roaming', 'CosRnD')
]
for candidate in config_candidates:
    test_path = os.path.join(candidate, 'config.ini')
    if os.path.exists(test_path):
        config_path = test_path
        break
 
print(f"Using config path: {config_path}")
print(f"Using application path: {application_path}")

# Setup database
db_manager.setup_database(application_path=application_path, config_path=config_path)

# Check and add columns
inspector = inspect(db_manager.engine)

# Check production_formulations for payment_room
print("\n=== Checking production_formulations table ===")
prod_cols = [c['name'] for c in inspector.get_columns('production_formulations')]
print(f"Columns found: {prod_cols}")
if 'payment_room' not in prod_cols:
    print("Adding payment_room column to production_formulations...")
    try:
        with db_manager.engine.connect() as conn:
            trans = conn.begin()
            conn.execute(text("ALTER TABLE production_formulations ADD COLUMN payment_room VARCHAR(255)"))
            trans.commit()
            print("Successfully added payment_room column to production_formulations!")
    except Exception as e:
        print(f"Error adding payment_room to production_formulations: {e}")
else:
    print("payment_room column already exists in production_formulations!")

# Check production_runs for payment_room
print("\n=== Checking production_runs table ===")
run_cols = [c['name'] for c in inspector.get_columns('production_runs')]
print(f"Columns found: {run_cols}")
if 'payment_room' not in run_cols:
    print("Adding payment_room column to production_runs...")
    try:
        with db_manager.engine.connect() as conn:
            trans = conn.begin()
            conn.execute(text("ALTER TABLE production_runs ADD COLUMN payment_room VARCHAR(255)"))
            trans.commit()
            print("Successfully added payment_room column to production_runs!")
    except Exception as e:
        print(f"Error adding payment_room to production_runs: {e}")
else:
    print("payment_room column already exists in production_runs!")

print("\n=== Done! ===")

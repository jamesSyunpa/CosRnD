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

# Check production_formulations for client_name
print("\n=== Checking production_formulations table ===")
prod_cols = [c['name'] for c in inspector.get_columns('production_formulations')]
print(f"Columns found: {prod_cols}")
if 'client_name' not in prod_cols:
    print("Adding client_name column...")
    try:
        with db_manager.engine.connect() as conn:
            trans = conn.begin()
            conn.execute(text("ALTER TABLE production_formulations ADD COLUMN client_name VARCHAR(255)"))
            trans.commit()
            print("Successfully added client_name column!")
    except Exception as e:
        print(f"Error adding client_name: {e}")
else:
    print("client_name column already exists!")

print("\n=== Done! ===")

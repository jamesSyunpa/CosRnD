import sqlite3
import os

DB_PATH = "data/cosmetic.db"

def add_columns():
    if not os.path.exists(DB_PATH):
        print(f"Database not found at {DB_PATH}")
        return

    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    # Add manufacturing_date to formulations (if not already done)
    try:
        cursor.execute("ALTER TABLE formulations ADD COLUMN manufacturing_date VARCHAR(20)")
        print("Successfully added column 'manufacturing_date' to 'formulations' table.")
    except sqlite3.OperationalError as e:
        if "duplicate column" in str(e):
            print("Column 'manufacturing_date' already exists in 'formulations'.")
        else:
            print(f"Error adding column to formulations: {e}")

    # Add production_date to production_runs
    try:
        cursor.execute("ALTER TABLE production_runs ADD COLUMN production_date DATE")
        print("Successfully added column 'production_date' to 'production_runs' table.")
    except sqlite3.OperationalError as e:
        if "duplicate column" in str(e):
            print("Column 'production_date' already exists in 'production_runs'.")
        else:
            print(f"Error adding column to production_runs: {e}")

    conn.commit()
    conn.close()

if __name__ == "__main__":
    add_columns()

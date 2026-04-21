import sys
import os
import bcrypt

# Add project root to sys.path
PROJECT_ROOT = os.path.dirname(os.path.abspath(__file__))
if PROJECT_ROOT not in sys.path:
    sys.path.append(PROJECT_ROOT)

from database.db_manager import db_manager
from database.models import User

CONFIG_FILE_PATH = os.path.join(PROJECT_ROOT, 'config.ini')

def reset_passwords():
    print("--- Password Reset Tool ---")
    # Setup DB connection
    # We pass PROJECT_ROOT as application_path
    try:
        db_manager.setup_database(PROJECT_ROOT, CONFIG_FILE_PATH, None)
    except Exception as e:
        print(f"Failed to setup database: {e}")
        return

    session = db_manager.get_session()
    try:
        users = session.query(User).all()
        if not users:
            print("No users found in the database.")
            return

        print(f"Found {len(users)} users.")
        
        # Reset all users to '1234'
        new_password = "1234"
        hashed_password = bcrypt.hashpw(new_password.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')
        
        for user in users:
            print(f"Resetting password for user: {user.username} ({user.real_name})")
            user.password = hashed_password
            
        session.commit()
        print("\nSUCCESS: All user passwords have been reset to '1234'.")
        print("You can now login with any existing username and password '1234'.")
        
    except Exception as e:
        print(f"Error during password reset: {e}")
        session.rollback()
    finally:
        session.close()

if __name__ == "__main__":
    reset_passwords()

import sys
import hashlib
import secrets
from PyQt5.QtWidgets import QApplication, QDialog
from src.ui.main_window import MainWindow
from src.ui.login_view import LoginView
from src.infrastructure.database import get_connection, init_db, seed_data

def ensure_database_and_users():
    """Initialize database and create default users if none exist"""
    
    # Initialize database tables
    try:
        # Check if tables exist by trying to query
        with get_connection() as conn:
            conn.execute("SELECT 1 FROM users LIMIT 1")
            has_users = True
    except:
        # Database doesn't exist or has no tables
        print("Initializing database...")
        init_db()
        seed_data()
        has_users = False
    
    with get_connection() as conn:
        cursor = conn.execute("SELECT COUNT(*) FROM users")
        user_count = cursor.fetchone()[0]
        
        if user_count == 0:
            print("Creating default users...")
            default_users = [
                ("admin", "admin123")
            ]
            
            for username, password in default_users:
                salt = secrets.token_hex(16)
                hashed = hashlib.sha256((salt + password).encode()).hexdigest()
                try:
                    conn.execute(
                        "INSERT INTO users (username, hashed_password, salt) VALUES (?, ?, ?)",
                        (username, hashed, salt)
                    )
                    print(f"  ✓ Created user: {username}")
                except:
                    pass
            conn.commit()
            print("Default users created successfully!")

def main() -> None:
    ensure_database_and_users()
    
    app = QApplication(sys.argv)
    app.setStyle("Fusion")
    
    login = LoginView()
    if login.exec_() == QDialog.Accepted:
        window = MainWindow()
        window.show()
        sys.exit(app.exec_())
    else:
        sys.exit(0)

if __name__ == "__main__":
    main()

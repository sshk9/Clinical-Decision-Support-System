import sys
from PyQt5.QtWidgets import QApplication, QDialog
from src.ui.main_window import MainWindow
from src.ui.login_view import LoginView
from src.infrastructure.database import init_db, seed_data, get_user_by_username

def main() -> None:
    app = QApplication(sys.argv)
    app.setStyle("Fusion")

    # Always safe — uses CREATE TABLE IF NOT EXISTS
    init_db()

    # Seed only on first run. Preserves the audit log and any logged
    # clinician decisions across application restarts.
    if get_user_by_username("admin") is None:
        seed_data()

    login = LoginView()
    if login.exec_() == QDialog.Accepted:
        window = MainWindow()
        window.show()
        sys.exit(app.exec_())
    else:
        sys.exit(0)

if __name__ == "__main__":
    main()
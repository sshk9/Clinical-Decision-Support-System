import sys
from PyQt5.QtWidgets import QApplication, QDialog
from src.ui.main_window import MainWindow
from src.ui.login_view import LoginView
from src.infrastructure.database import init_db, seed_data

def main() -> None:
    app = QApplication(sys.argv)
    app.setStyle("Fusion")
    
    init_db()
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

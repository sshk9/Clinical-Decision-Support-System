import sys
from PySide6.QtWidgets import QApplication, QMainWindow


def run_app():
    print("run_app() started")  # should print in terminal

    app = QApplication(sys.argv)

    window = QMainWindow()
    window.setWindowTitle("CDSS Prototype")
    window.resize(500, 300)
    window.show()

    print("window shown, entering event loop")  # should print
    exit_code = app.exec()  # IMPORTANT: must be exec() with parentheses
    print("event loop ended with:", exit_code)  # prints when you close window

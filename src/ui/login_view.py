from __future__ import annotations
from PyQt5.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout,
    QLabel, QLineEdit, QPushButton, QMessageBox
)
from PyQt5.QtCore import Qt
from ..infrastructure.auth_service import verify_credentials


class LoginView(QDialog):
    """Login dialog shown before the main window."""

    def __init__(self):
        super().__init__()
        self.setWindowTitle("CDSS Login")
        self.setFixedSize(340, 220)
        self._build()

    def _build(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(30, 30, 30, 30)
        layout.setSpacing(12)

        layout.addWidget(QLabel("Username:"))
        self._username = QLineEdit()
        self._username.setPlaceholderText("Enter username")
        layout.addWidget(self._username)

        layout.addWidget(QLabel("Password:"))
        self._password = QLineEdit()
        self._password.setPlaceholderText("Enter password")
        self._password.setEchoMode(QLineEdit.Password)
        layout.addWidget(self._password)

        btn_row = QHBoxLayout()
        login_btn = QPushButton("Login")
        cancel_btn = QPushButton("Cancel")
        login_btn.clicked.connect(self._on_login)
        cancel_btn.clicked.connect(self.reject)
        btn_row.addWidget(login_btn)
        btn_row.addWidget(cancel_btn)
        layout.addLayout(btn_row)

    def _on_login(self) -> None:
        username = self._username.text().strip()
        password = self._password.text()

        if not username or not password:
            QMessageBox.warning(self, "Error", "Please enter both username and password.")
            return

        if verify_credentials(username, password):
            self.accept()
        else:
            QMessageBox.warning(self, "Error", "Invalid username or password.")
            self._password.clear()
from __future__ import annotations
from PyQt5.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout,
    QLabel, QLineEdit, QPushButton, QMessageBox, QFrame, QGraphicsDropShadowEffect
)
from PyQt5.QtCore import Qt, QPoint
from PyQt5.QtGui import QColor, QFont
from ..infrastructure.auth_service import verify_credentials

class LoginView(QDialog):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("CDSS Portal")
        self.setFixedSize(400, 500)
        self.setWindowFlags(Qt.FramelessWindowHint | Qt.Window)
        self.setAttribute(Qt.WA_TranslucentBackground)
        self._build()

    def _build(self) -> None:
        self.main_layout = QVBoxLayout(self)
        
        self.container = QFrame()
        self.container.setObjectName("MainCard")
        self.container.setStyleSheet("""
            #MainCard {
                background-color: white;
                border-radius: 20px;
            }
            QLabel {
                font-family: 'Segoe UI', sans-serif;
            }
            #Title {
                font-size: 28px;
                font-weight: 800;
                color: #1a3a3a;
            }
            #SubTitle {
                font-size: 13px;
                color: #709090;
            }
            QLineEdit {
                border: 1px solid #e0eaea;
                border-radius: 10px;
                padding: 12px;
                background: #f8fbfb;
                font-size: 14px;
                color: #2d4f4f;
            }
            QLineEdit:focus {
                border: 2px solid #4db6ac;
                background: white;
            }
            QPushButton#LoginButton {
                background-color: #4db6ac;
                color: white;
                border: none;
                border-radius: 10px;
                font-size: 15px;
                font-weight: bold;
                padding: 12px;
            }
            QPushButton#LoginButton:hover {
                background-color: #3d968e;
            }
            QPushButton#CancelButton {
                background-color: transparent;
                color: #a0baba;
                border: none;
                font-size: 13px;
                font-weight: 600;
            }
            QPushButton#CancelButton:hover {
                color: #4db6ac;
            }
        """)
        
        shadow = QGraphicsDropShadowEffect(blurRadius=25, xOffset=0, yOffset=10)
        shadow.setColor(QColor(0, 0, 0, 40))
        self.container.setGraphicsEffect(shadow)

        card_layout = QVBoxLayout(self.container)
        card_layout.setContentsMargins(40, 50, 40, 50)
        card_layout.setSpacing(10)

        title = QLabel("Welcome")
        title.setObjectName("Title")
        title.setAlignment(Qt.AlignCenter)
        card_layout.addWidget(title)

        subtitle = QLabel("Authorized Personnel Only")
        subtitle.setObjectName("SubTitle")
        subtitle.setAlignment(Qt.AlignCenter)
        card_layout.addWidget(subtitle)
        card_layout.addSpacing(30)

        card_layout.addWidget(QLabel("USERNAME"))
        self._username = QLineEdit()
        self._username.setPlaceholderText("e.g. j.doe")
        card_layout.addWidget(self._username)
        
        card_layout.addSpacing(10)

        card_layout.addWidget(QLabel("PASSWORD"))
        self._password = QLineEdit()
        self._password.setPlaceholderText("••••••••")
        self._password.setEchoMode(QLineEdit.Password)
        card_layout.addWidget(self._password)

        card_layout.addSpacing(40)

        self.login_btn = QPushButton("Sign In")
        self.login_btn.setObjectName("LoginButton")
        self.login_btn.setCursor(Qt.PointingHandCursor)
        self.login_btn.clicked.connect(self._on_login)
        card_layout.addWidget(self.login_btn)

        cancel_btn = QPushButton("Go Back")
        cancel_btn.setObjectName("CancelButton")
        cancel_btn.setCursor(Qt.PointingHandCursor)
        cancel_btn.clicked.connect(self.reject)
        card_layout.addWidget(cancel_btn)

        self.main_layout.addWidget(self.container)
        self._username.setFocus()

    def _on_login(self) -> None:
        if verify_credentials(self._username.text(), self._password.text()):
            self.accept()
        else:
            QMessageBox.critical(self, "Error", "Invalid Credentials")
            self._password.clear()

    def mousePressEvent(self, event):
        self.oldPos = event.globalPos()

    def mouseMoveEvent(self, event):
        delta = QPoint(event.globalPos() - self.oldPos)
        self.move(self.x() + delta.x(), self.y() + delta.y())
        self.oldPos = event.globalPos()

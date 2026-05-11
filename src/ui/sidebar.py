from __future__ import annotations

from PyQt5.QtWidgets import QWidget, QVBoxLayout, QPushButton
from PyQt5.QtCore import pyqtSignal, Qt
from PyQt5.QtGui import QFont

from .ui_helpers import _label, ACCENT

# ---------------------------------------------------------------------------
# Sidebar
# ---------------------------------------------------------------------------
class Sidebar(QWidget):
    nav_changed = pyqtSignal(int)

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setFixedWidth(220)
        self.setStyleSheet(f"background: #ffffff; border-right: 1px solid #2A3F44;")
        self._buttons: list[QPushButton] = []
        self._build()

    def _build(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 24, 12, 24)
        layout.setSpacing(8)

        title = _label("  CDSS", 18, bold=True)
        title.setStyleSheet(f"color: {ACCENT}; background: transparent; border: none; padding: 8px 16px;")
        layout.addWidget(title)
        layout.addSpacing(16)

        nav_items = ["Dashboard", "Patient Management", "Analytics", "Trends", "Audit Log"]

        for i, name in enumerate(nav_items):
            btn = QPushButton(name)
            btn.setCheckable(True)
            btn.setFixedHeight(45)
            btn.setCursor(Qt.PointingHandCursor)
            btn.setFont(QFont("Segoe UI Variable", 10))

            btn.setStyleSheet(f"""
                QPushButton {{
                    background: transparent;
                    color: #94A3B8;
                    border: none;
                    text-align: left;
                    padding-left: 15px;
                    border-radius: 8px;
                    margin: 0px 5px;
                }}
                QPushButton:hover {{
                    background: #1E293B;
                    color: #F8FAFC;
                }}
                QPushButton:checked {{
                    background: #1E293B;
                    color:#F8FAFC;
                }}
            """)

            btn.clicked.connect(lambda _, idx=i: self._on_nav(idx))
            layout.addWidget(btn)
            self._buttons.append(btn)

        layout.addStretch()
        user_label = _label("  GP User", muted=False)
        user_label.setStyleSheet(f"color: #A8C4C4; background: transparent; border: none; padding: 8px 16px;")
        layout.addWidget(user_label)

        self._buttons[0].setChecked(True)

    def _on_nav(self, idx: int) -> None:
        for i, btn in enumerate(self._buttons):
            btn.blockSignals(True)
            btn.setChecked(i == idx)
            btn.blockSignals(False)
        self.nav_changed.emit(idx)

    def set_active(self, idx: int) -> None:
        """Public method to set the active navigation item."""
        self._on_nav(idx)
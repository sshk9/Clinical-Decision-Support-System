from __future__ import annotations

from PyQt5.QtWidgets import QWidget, QFrame, QLabel
from PyQt5.QtCore import Qt
from PyQt5.QtGui import QFont

# ---------------------------------------------------------------------------
# Colour Palette - matches Figma teal/mint theme
# ---------------------------------------------------------------------------
SIDEBAR_BG    = "#1B2A2F"
CONTENT_BG    = "#F4F7F7"
ACCENT        = "#2ABFBF"
ACCENT_DARK   = "#1FA8A8"
CARD_BG       = "#FFFFFF"
TEXT_PRIMARY  = "#111D1D"
TEXT_MUTED    = "#6B8A8A"
BORDER        = "#DDE8E8"
HOVER_ROW     = "#F0FAFA"
DANGER        = "#C0392B"
SUCCESS       = "#0D7A5A"
WARNING       = "#B45309"

RISK_LOW      = ("#E6F7F2", "#0D7A5A")
RISK_MEDIUM   = ("#FFF8E6", "#B45309")
RISK_HIGH     = ("#FEF0EF", "#C0392B")

SEV_COLORS    = {
    1: "#0D7A5A",
    2: "#56A87A",
    3: "#B45309",
    4: "#D9642A",
    5: "#C0392B",
}


RISK_COL_W  = 120
BADGE_W     = 80
BADGE_H     = 26

def _card(parent: QWidget | None = None) -> QFrame:
    frame = QFrame(parent)
    frame.setStyleSheet(f"""
        QFrame {{
            background: {CARD_BG};
            border-radius: 8px;
            border: 1px solid {BORDER};
        }}
    """)
    return frame


def _label(text: str, size: int = 13, bold: bool = False, muted: bool = False,
           color: str | None = None) -> QLabel:
    lbl = QLabel(text)
    font = QFont("Segoe UI", size)
    font.setBold(bold)
    lbl.setFont(font)
    c = color if color else (TEXT_MUTED if muted else TEXT_PRIMARY)
    lbl.setStyleSheet(f"color: {c}; background: transparent; border: none;")
    return lbl


class _Badge(QLabel):
    """Pill-shaped risk badge. Width is set via setFixedWidth, NOT CSS min-width."""

    _PRESETS = {
        "Low":    RISK_LOW,
        "Medium": RISK_MEDIUM,
        "High":   RISK_HIGH,
    }

    def __init__(self, text: str, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.set_risk(text)

    def set_risk(self, text: str) -> None:
        bg, fg = self._PRESETS.get(text, ("#ECECEC", "#555"))
        self.setText(text)
        self.setAlignment(Qt.AlignCenter)
        font = QFont("Segoe UI", 11)
        font.setBold(True)
        self.setFont(font)
        self.setFixedWidth(BADGE_W)
        self.setFixedHeight(BADGE_H)
        self.setStyleSheet(f"""
            QLabel {{
                background: {bg};
                color: {fg};
                border-radius: 12px;
                border: none;
            }}
        """)
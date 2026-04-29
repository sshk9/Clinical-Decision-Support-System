from __future__ import annotations
from PyQt5.QtWidgets import QWidget, QVBoxLayout, QHBoxLayout, QLabel, QSlider, QSpinBox, QFrame
from PyQt5.QtCore import Qt
from PyQt5.QtGui import QFont
from ..decision_engine.engine import ActionScore

# colour palette
ACCENT = "#2ABFBF"
TEXT_PRIMARY = "#1B2A2F"
TEXT_MUTED = "#6B8A8A"
CARD_BG = "#FFFFFF"
DIVIDER = "#EEF3F3"


class SensitivityAnalysisPanel(QWidget):
    def __init__(self, parent: QWidget | None = None):
        super().__init__(parent)
        self._current_score: ActionScore | None = None
        self._build()
        self.setVisible(False)

    def _build(self):
        # Base layout
        base_layout = QVBoxLayout(self)
        base_layout.setContentsMargins(0, 0, 0, 0)
        base_layout.setSpacing(10)

        # Header
        self.header_label = QLabel("Sensitivity Analysis")
        self.header_label.setFont(QFont("Segoe UI", 14, QFont.Bold))
        self.header_label.setStyleSheet(f"color: {TEXT_PRIMARY}; background: transparent; border: none;")
        base_layout.addWidget(self.header_label)

        # The main card
        self.card_frame = QFrame()
        self.card_frame.setObjectName("MainCard")
        self.card_frame.setStyleSheet(f"""
            QFrame#MainCard {{
                background-color: {CARD_BG};
                border: 1px solid {DIVIDER};
                border-radius: 12px;
            }}
            QLabel {{
                background-color: transparent;
                border: none;
            }}
            QSlider {{
                background-color: transparent;
            }}
            QSpinBox {{
                background-color: white;
                border: 1px solid {DIVIDER};
                border-radius: 4px;
                padding: 4px;
            }}
        """)

        card_layout = QVBoxLayout(self.card_frame)
        card_layout.setContentsMargins(24, 24, 24, 24)
        card_layout.setSpacing(0)

        # --- Future Value Weight (γ) ---
        gamma_label = QLabel("FUTURE VALUE WEIGHT (γ)")
        gamma_label.setStyleSheet(f"color: {TEXT_MUTED}; font-size: 10px; font-weight: 800; letter-spacing: 1px;")
        card_layout.addWidget(gamma_label)
        card_layout.addSpacing(8)

        gamma_row = QHBoxLayout()
        self.gamma_slider = QSlider(Qt.Horizontal)
        self.gamma_slider.setRange(50, 99)
        self.gamma_slider.setValue(90)
        self.gamma_slider.setFixedWidth(280)
        self.gamma_slider.setCursor(Qt.PointingHandCursor)

        self.gamma_value = QLabel("0.90")
        self.gamma_value.setStyleSheet(f"color: {ACCENT}; font-weight: bold; font-size: 13px; margin-left: 10px;")

        gamma_row.addWidget(self.gamma_slider)
        gamma_row.addWidget(self.gamma_value)
        gamma_row.addStretch()
        card_layout.addLayout(gamma_row)

        card_layout.addSpacing(20)

        # --- Risk Tolerance (±) ---
        risk_label = QLabel("RISK TOLERANCE +/-")
        risk_label.setStyleSheet(f"color: {TEXT_MUTED}; font-size: 10px; font-weight: 800; letter-spacing: 1px;")
        card_layout.addWidget(risk_label)
        card_layout.addSpacing(8)

        self.risk_spin = QSpinBox()
        self.risk_spin.setRange(-5, 5)
        self.risk_spin.setFixedWidth(65)
        card_layout.addWidget(self.risk_spin)

        # --- Divider & Results ---
        card_layout.addSpacing(30)
        line = QFrame()
        line.setFixedHeight(1)
        line.setStyleSheet(f"background-color: {DIVIDER}; border: none;")
        card_layout.addWidget(line)
        card_layout.addSpacing(20)

        # Projected score (large)
        self.result_label = QLabel("Projected Score: --")
        self.result_label.setFont(QFont("Segoe UI", 14, QFont.Bold))
        self.result_label.setStyleSheet(f"color: {TEXT_PRIMARY};")
        card_layout.addWidget(self.result_label)

        card_layout.addSpacing(12)

        base_layout.addWidget(self.card_frame)

        # Connect signals
        self.gamma_slider.valueChanged.connect(self._update_results)
        self.risk_spin.valueChanged.connect(self._update_results)

    def set_score(self, score: ActionScore):
        self._current_score = score
        self._update_results()
        self.setVisible(True)

    def _update_results(self):
        if not self._current_score:
            return

        gamma = self.gamma_slider.value() / 100.0
        self.gamma_value.setText(f"{gamma:.2f}")

        # Risk tolerance multiplier: each step ±10%
        risk_factor = 1.0 + (self.risk_spin.value() * 0.1)
        new_immediate = self._current_score.immediate_utility * risk_factor

        # Future value: only gamma changes (risk tolerance does not affect transitions)
        future_sum = sum(prob * val for _, prob, val in self._current_score.future_outcomes)
        new_total = new_immediate + (gamma * future_sum)

        diff = new_total - self._current_score.total_score

        # Colour and sign
        if diff > 0.001:
            color = "#28A745"   # green
            symbol = "+"
        elif diff < -0.001:
            color = "#DC3545"   # red
            symbol = ""
        else:
            color = TEXT_PRIMARY
            symbol = ""

        self.result_label.setText(f"Projected Score: {new_total:.3f} ({symbol}{diff:.3f})")
        self.result_label.setStyleSheet(f"color: {color}; background: transparent;")

    def clear(self):
        self.setVisible(False)
        self._current_score = None

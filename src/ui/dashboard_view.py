from __future__ import annotations

from PyQt5.QtWidgets import QWidget, QVBoxLayout, QHBoxLayout, QLabel
from PyQt5.QtCore import Qt
from PyQt5.QtGui import QFont

from .ui_helpers import (
    ACCENT, BORDER, DANGER, WARNING,
    _card, _label
)
from ..infrastructure.database import get_connection, get_state_distribution
from ..analytics.analytics import state_success_rate

# ---------------------------------------------------------------------------
# Dashboard view
# ---------------------------------------------------------------------------
class DashboardView(QWidget):
    """
    Overview panel — shows real stats from the DB on load.
    """

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.cards: dict[str, QLabel] = {}
        self._build()
        self._load_stats()

    def _build(self) -> None:
        root = QVBoxLayout(self)
        root.setContentsMargins(32, 32, 32, 32)
        root.setSpacing(20)

        root.addWidget(_label("Clinical Decision Dashboard", 20, bold=True))
        root.addWidget(_label("Active patients, risk alerts, and system health", muted=True))

        # ── ROW 1: Core Stats ──────────────────────────────────────────
        stats_row = QHBoxLayout()
        stats_row.setSpacing(16)

        for key, title in [
            ("active",    "Active Patients"),
            ("high_risk", "High-Risk Cases"),
            ("critical",  "Critical Cases"),
        ]:
            card = _card()
            layout = QVBoxLayout(card)
            layout.setContentsMargins(20, 16, 20, 16)
            layout.setSpacing(8)
            layout.addWidget(_label(title, muted=True))
            value_label = _label("—", 24, bold=True)
            layout.addWidget(value_label)
            layout.addWidget(_label("patients", 10, muted=True))
            stats_row.addWidget(card)
            self.cards[key] = value_label

        root.addLayout(stats_row)

        # ── ROW 2: Disease Breakdown ───────────────────────────────────
        disease_row = QHBoxLayout()
        disease_row.setSpacing(16)

        for key, title in [
            ("disease_1", "Type 2 Diabetes"),
            ("disease_2", "Chronic Kidney Disease"),
        ]:
            card = _card()
            layout = QVBoxLayout(card)
            layout.setContentsMargins(20, 16, 20, 16)
            layout.setSpacing(8)
            layout.addWidget(_label(title, muted=True))
            value_label = _label("—", 20, bold=True)
            layout.addWidget(value_label)
            layout.addWidget(_label("patients enrolled", 10, muted=True))
            disease_row.addWidget(card)
            self.cards[key] = value_label

        root.addLayout(disease_row)

        # ── Population Health Status Banner ───────────────────────────
        self.health_status_label = QLabel("")
        self.health_status_label.setWordWrap(True)
        self.health_status_label.setFont(QFont("Segoe UI", 11))
        self.health_status_label.setMinimumHeight(60)
        self.health_status_label.setAlignment(Qt.AlignVCenter | Qt.AlignLeft)
        root.addWidget(self.health_status_label)

        root.addStretch()

    def _load_stats(self) -> None:
        try:
            conn = get_connection()
            cursor = conn.cursor()

            cursor.execute("SELECT COUNT(*) FROM patient")
            active = cursor.fetchone()[0] or 0

            cursor.execute("""
                SELECT COUNT(*)
                FROM patient_status ps
                JOIN disease_state ds ON ps.current_state_id = ds.id
                WHERE ds.severity_level >= 4
            """)
            high_risk = cursor.fetchone()[0] or 0

            cursor.execute("""
                SELECT COUNT(*)
                FROM patient_status ps
                JOIN disease_state ds ON ps.current_state_id = ds.id
                WHERE ds.severity_level = 5
            """)
            critical = cursor.fetchone()[0] or 0

            cursor.execute("""
                SELECT d.name, COUNT(ps.patient_id)
                FROM patient_status ps
                JOIN disease d ON ps.disease_id = d.id
                GROUP BY d.id, d.name
            """)
            d1 = d2 = 0
            for disease_name, count in cursor.fetchall():
                if "Diabetes" in disease_name:
                    d1 = count
                elif "Kidney" in disease_name:
                    d2 = count

            conn.close()

            distribution = get_state_distribution()
            stats_data = state_success_rate(distribution)
            overall = stats_data.get(
                "overall",
                {"success_rate": 0, "total_patients": 0, "success_count": 0},
            )
            rate  = overall.get("success_rate", 0)
            count = overall.get("success_count", 0)
            total = overall.get("total_patients", 0)

            # Update stat cards
            self.cards["active"].setText(str(active))
            self.cards["high_risk"].setText(str(high_risk))
            self.cards["critical"].setText(str(critical))
            self.cards["disease_1"].setText(str(d1))
            self.cards["disease_2"].setText(str(d2))

            # Colour high-risk/critical values red if non-zero
            if high_risk > 0:
                self.cards["high_risk"].setStyleSheet(
                    f"color: {DANGER}; background: transparent; border: none; font-weight: bold;"
                )
            if critical > 0:
                self.cards["critical"].setStyleSheet(
                    f"color: {DANGER}; background: transparent; border: none; font-weight: bold;"
                )

            # Health status banner
            if rate >= 80:
                status, bg, fg = "Excellent", "#E8F5E9", "#28A745"
            elif rate >= 60:
                status, bg, fg = "Good",      "#E0F7FA", ACCENT
            elif rate >= 40:
                status, bg, fg = "Moderate",  "#FFF8E1", "#F9A825"
            elif rate >= 20:
                status, bg, fg = "Poor",      "#FFF3E0", WARNING
            else:
                status, bg, fg = "Critical",  "#FFEBEE", DANGER

            self.health_status_label.setText(
                f"Population Health Status: {status}\n"
                f"Success rate (severity ≤2): {rate:.1f}%  ({count}/{total} patients)"
            )
            self.health_status_label.setStyleSheet(f"""
                QLabel {{
                    padding: 14px 18px;
                    border-radius: 10px;
                    background-color: {bg};
                    color: {fg};
                    font-weight: 600;
                    border: 1px solid {BORDER};
                }}
            """)

        except Exception as e:
            print("Dashboard load error:", e)
            for key in ("active", "high_risk", "critical", "disease_1", "disease_2"):
                self.cards[key].setText("0")
            self.health_status_label.setText("Population Health Status: Data unavailable")
            self.health_status_label.setStyleSheet("""
                QLabel {
                    padding: 14px 18px;
                    border-radius: 10px;
                    background-color: #FFEBEE;
                    color: #C62828;
                    font-weight: 600;
                    border: 1px solid #DDE8E8;
                }
            """)

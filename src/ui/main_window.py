from __future__ import annotations
from PyQt5.QtWidgets import (
    QMainWindow, QWidget, QHBoxLayout, QVBoxLayout,
    QPushButton, QLabel, QListWidget, QListWidgetItem,
    QStackedWidget, QFrame, QSizePolicy, QTableWidget,
    QTableWidgetItem, QHeaderView, QComboBox, QProgressBar,
    QTreeWidget, QTreeWidgetItem, QScrollArea, QLineEdit,
    QFileDialog, QMessageBox
)
from PyQt5.QtCore import Qt, pyqtSignal, QTimer
from PyQt5.QtGui import QFont, QColor

from ..domain.patient import Patient
from ..domain.action import Action
from ..decision_engine.engine import DecisionEngine, ActionScore
from ..domain.patient_record import PatientRecord
from .comparison_widget import ComparisonWidget
from .trend_widget import TrendWidget
from .sensitivity_panel import SensitivityAnalysisPanel
from .risk_benefit_plot import RiskBenefitPlot
from ..infrastructure.database import get_connection, get_state_distribution, log_recommendation, get_all_patients_detailed
from ..analytics.analytics import state_success_rate
from ..ui.audit_widget import AuditWidget


# ---------------------------------------------------------------------------
# Colour Paletter - matches Figma teal/mint theme
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

STATE_COLORS = {
    1: SUCCESS,
    2: "#8BC34A",
    3: WARNING,
    4: DANGER,
    5: "#7B1FA2",
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


# ---------------------------------------------------------------------------
# Patient view
# ---------------------------------------------------------------------------
class PatientView(QWidget):
    """
    Clinical overview for a single patient.
    Displays current state, ranked actions with scores, decision trace,
    sensitivity analysis, risk-benefit visualization, and action history.
    """

    def __init__(self, engine: DecisionEngine, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._patient: Patient | None = None
        self._actions: list[Action] = []
        self._engine = engine
        self._current_scores: list[ActionScore] = []
        self._build()

    def _build(self) -> None:
        outer_layout = QVBoxLayout(self)
        outer_layout.setContentsMargins(0, 0, 0, 0)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.NoFrame)
        scroll.setStyleSheet(f"background-color: {CONTENT_BG};")

        container = QWidget()
        root = QVBoxLayout(container)
        root.setContentsMargins(32, 32, 32, 32)
        root.setSpacing(20)

        # Header
        self._header = _label("Patient Clinical Overview", 20, bold=True)
        root.addWidget(self._header)
        self._subheader = _label("No patient loaded.", muted=True)
        root.addWidget(self._subheader)
        self._risk_label = _label("Risk Score: —", 13, bold=True)
        root.addWidget(self._risk_label)

        self._risk_bar = QProgressBar()
        self._risk_bar.setRange(0, 100)
        self._risk_bar.setValue(0)
        self._risk_bar.setFormat("%p%")
        self._risk_bar.setMaximumHeight(18)
        root.addWidget(self._risk_bar)

        # State card
        state_card = _card()
        state_layout = QHBoxLayout(state_card)
        state_layout.setContentsMargins(20, 16, 20, 16)
        state_layout.setSpacing(40)
        self._state_label = _label("—", 20, bold=True)
        self._disease_label = _label("—", muted=True)
        self._model_label = _label("—", muted=True)
        state_layout.addWidget(_label("Current State:", bold=True))
        state_layout.addWidget(self._state_label)
        state_layout.addWidget(_label("Disease:", bold=True))
        state_layout.addWidget(self._disease_label)
        state_layout.addWidget(_label("Model:", bold=True))
        state_layout.addWidget(self._model_label)
        state_layout.addStretch()
        root.addWidget(state_card)

        # Action selector + run button
        action_row = QHBoxLayout()
        self._action_combo = QComboBox()
        self._action_combo.setFixedHeight(36)
        self._action_combo.setStyleSheet(f"""
            QComboBox {{
                background: {CARD_BG};
                border: 1px solid {BORDER};
                border-radius: 6px;
                padding: 4px 12px;
                font-size: 13px;
                color: {TEXT_PRIMARY};
            }}
        """)
        apply_btn = QPushButton("Apply Action")
        apply_btn.setFixedHeight(36)
        apply_btn.setStyleSheet(f"""
            QPushButton {{
                background: {ACCENT};
                color: white;
                border-radius: 6px;
                padding: 0 20px;
                font-size: 13px;
                font-weight: bold;
            }}
            QPushButton:hover {{ background: {ACCENT_DARK}; }}
        """)
        apply_btn.clicked.connect(self._on_apply_action)

        simulate_btn = QPushButton("Simulate Progression")
        simulate_btn.setFixedHeight(36)
        simulate_btn.setStyleSheet(f"""
            QPushButton {{
                background: {SIDEBAR_BG};
                color: white;
                border-radius: 6px;
                padding: 0 20px;
                font-size: 13px;
                font-weight: bold;
            }}
            QPushButton:hover {{ background: #2E3F45; }}
        """)
        simulate_btn.clicked.connect(self._on_simulate_progression)

        action_row.addWidget(self._action_combo)
        action_row.addWidget(apply_btn)
        action_row.addWidget(simulate_btn)
        action_row.addStretch()
        root.addLayout(action_row)

        # ── Decision Buttons Row 
        decision_layout = QHBoxLayout()
        decision_layout.setSpacing(12)

        self.accept_btn = QPushButton("✓ Accept")
        self.accept_btn.setFixedHeight(36)
        self.accept_btn.setStyleSheet(f"""
            QPushButton {{
                background-color: #28A745;
                color: white;
                border-radius: 6px;
                font-weight: bold;
                padding: 0 16px;
            }}
            QPushButton:hover {{ background-color: #218838; }}
            QPushButton:disabled {{ background-color: #6C757D; }}
        """)
        self.accept_btn.clicked.connect(self._on_accept)

        self.reject_btn = QPushButton("✗ Reject")
        self.reject_btn.setFixedHeight(36)
        self.reject_btn.setStyleSheet(f"""
            QPushButton {{
                background-color: #DC3545;
                color: white;
                border-radius: 6px;
                font-weight: bold;
                padding: 0 16px;
            }}
            QPushButton:hover {{ background-color: #C82333; }}
            QPushButton:disabled {{ background-color: #6C757D; }}
        """)
        self.reject_btn.clicked.connect(self._on_reject)

        self.override_btn = QPushButton("↩ Override")
        self.override_btn.setFixedHeight(36)
        self.override_btn.setStyleSheet(f"""
            QPushButton {{
                background-color: #FD7E14;
                color: white;
                border-radius: 6px;
                font-weight: bold;
                padding: 0 16px;
            }}
            QPushButton:hover {{ background-color: #E06600; }}
            QPushButton:disabled {{ background-color: #6C757D; }}
        """)
        self.override_btn.clicked.connect(self._on_override)

        decision_layout.addWidget(self.accept_btn)
        decision_layout.addWidget(self.reject_btn)
        decision_layout.addWidget(self.override_btn)
        decision_layout.addStretch()
        root.addLayout(decision_layout)

        # Confirmation label
        self.confirmation_label = _label("", size=11, muted=True)
        self.confirmation_label.setVisible(False)
        root.addWidget(self.confirmation_label)

        # Ranked actions table
        root.addWidget(_label("Ranked Actions", 15, bold=True))
        self._table = QTableWidget(0, 4)
        self._table.setHorizontalHeaderLabels(
            ["Action", "Immediate Utility", "Long-Term Value", "Total Score"]
        )
        self._table.horizontalHeader().setSectionResizeMode(0, QHeaderView.Stretch)
        self._table.setEditTriggers(QTableWidget.NoEditTriggers)
        self._table.setSelectionBehavior(QTableWidget.SelectRows)
        self._table.setAlternatingRowColors(True)
        self._table.setMinimumHeight(150)
        self._table.setStyleSheet(f"""
            QTableWidget {{
                background: {CARD_BG};
                border: 1px solid {BORDER};
                border-radius: 8px;
                gridline-color: #EEF3F3;
                font-size: 13px;
            }}
            QHeaderView::section {{
                background: #EEF3F3;
                color: {TEXT_MUTED};
                font-size: 12px;
                padding: 6px;
                border: none;
            }}
            QTableWidget::item:selected {{
                background: #D6F0F0;
                color: {TEXT_PRIMARY};
            }}
        """)
        root.addWidget(self._table)

        # Decision trace (Why-Panel)
        root.addWidget(_label("Decision Trace", 15, bold=True))
        self.trace_tree = QTreeWidget()
        self.trace_tree.setHeaderLabel("Component")
        self.trace_tree.setMinimumHeight(180)
        self.trace_tree.setStyleSheet(f"""
            QTreeWidget {{
                background: {CARD_BG};
                border: 1px solid {BORDER};
                border-radius: 8px;
                font-size: 12px;
            }}
        """)
        root.addWidget(self.trace_tree)

        # Sensitivity analysis panel
        self.sensitivity_panel = SensitivityAnalysisPanel()
        self.sensitivity_panel.setMinimumHeight(280)
        root.addWidget(self.sensitivity_panel)

        # Risk-Benefit Plot
        self.risk_benefit_plot = RiskBenefitPlot()
        root.addWidget(self.risk_benefit_plot)

        # Action history
        root.addWidget(_label("Action History", 15, bold=True))
        self._history_list = QListWidget()
        self._history_list.setMinimumHeight(120)
        self._history_list.setStyleSheet(f"""
            QListWidget {{
                background: {CARD_BG};
                border: 1px solid {BORDER};
                border-radius: 8px;
                font-size: 13px;
                color: {TEXT_PRIMARY};
            }}
        """)
        root.addWidget(self._history_list)

        root.addWidget(_label("Transition Impact — Last Action", 15, bold=True))
        self._transition_card = _card()
        self._transition_layout = QVBoxLayout(self._transition_card)
        self._transition_layout.setContentsMargins(16, 12, 16, 12)
        self._transition_layout.setSpacing(4)
        self._transition_placeholder = _label("No action applied yet.", muted=True)
        self._transition_layout.addWidget(self._transition_placeholder)
        root.addWidget(self._transition_card)

        root.addStretch(1)

        self._table.itemSelectionChanged.connect(self._update_trace)

        scroll.setWidget(container)
        outer_layout.addWidget(scroll)

    def load_patient(self, patient: Patient, actions: list[Action]) -> None:
        """Load a patient and compute ranked actions."""
        self._patient = patient
        self._actions = actions
        self.risk_benefit_plot.update_for_patient(patient.patient_id)
        self.confirmation_label.setVisible(False)
        self._refresh()

    def _refresh(self) -> None:
        if self._patient is None:
            return

        self._header.setText(f"Patient — {self._patient.name or self._patient.patient_id}")
        self._subheader.setText(f"ID: {self._patient.patient_id}")
        self._state_label.setText(self._patient.current_state_label())
        self._disease_label.setText(self._patient.disease_name or "Unknown")
        self._model_label.setText(self._patient.model_size_label())

        self._action_combo.clear()
        for action in self._actions:
            self._action_combo.addItem(action.name)

        self._current_scores = self._engine.rank_actions(self._patient.macro_state, self._actions)

        has_scores = len(self._current_scores) > 0
        self.accept_btn.setEnabled(has_scores)
        self.reject_btn.setEnabled(has_scores)
        self.override_btn.setEnabled(has_scores)
        if not has_scores:
            self.confirmation_label.setVisible(False)

        if self._current_scores:
            best = self._current_scores[0]
            self._risk_label.setText(f"Risk Score: {best.risk_score:.1f} ({best.risk_level})")
            self._risk_bar.setValue(int(best.risk_score))

            if best.risk_level == "Low":
                self._risk_label.setStyleSheet("color: #228B22; font-weight: bold;")
            elif best.risk_level == "Medium":
                self._risk_label.setStyleSheet("color: #D48806; font-weight: bold;")
            else:
                self._risk_label.setStyleSheet("color: #C62828; font-weight: bold;")
        else:
            self._risk_label.setText("Risk Score: —")
            self._risk_bar.setValue(0)
            self._risk_label.setStyleSheet("font-weight: bold;")

        self._table.setRowCount(len(self._current_scores))
        for row, score in enumerate(self._current_scores):
            self._table.setItem(row, 0, QTableWidgetItem(score.action.name))
            self._table.setItem(row, 1, QTableWidgetItem(f"{score.immediate_utility:.3f}"))
            self._table.setItem(row, 2, QTableWidgetItem(f"{score.long_term_value:.3f}"))
            total_item = QTableWidgetItem(f"{score.total_score:.3f}")
            if row == 0:
                total_item.setForeground(QColor(ACCENT))
                font = QFont("Segoe UI", 13)
                font.setBold(True)
                total_item.setFont(font)
            self._table.setItem(row, 3, total_item)

        if self._current_scores:
            self._table.selectRow(0)
        else:
            self.trace_tree.clear()
            self.sensitivity_panel.clear()
            self.risk_benefit_plot.clear()

        # History
        self._history_list.clear()
        for line in self._patient.macro_state.summary():
            self._history_list.addItem(line)

        # Transition impact panel
        self._update_transition_panel()

    def _update_trace(self) -> None:
        """Update the decision trace and sensitivity panel for the selected action."""
        selected = self._table.selectedItems()
        if not selected or not self._current_scores:
            self.trace_tree.clear()
            self.sensitivity_panel.clear()
            return

        row = selected[0].row()
        if row >= len(self._current_scores):
            self.sensitivity_panel.clear()
            return

        score = self._current_scores[row]
        self.trace_tree.clear()

        root_item = QTreeWidgetItem([f"Decision Trace: {score.action.name}"])
        self.trace_tree.addTopLevelItem(root_item)

        imm = QTreeWidgetItem([f"Immediate Benefit: +{score.immediate_utility:.2f}"])
        imm.setToolTip(0, score.action.description)
        root_item.addChild(imm)

        fut_item = QTreeWidgetItem([f"Future Outcomes (Long-term weight: {score.gamma*100:.0f}%)"])
        root_item.addChild(fut_item)
        for state, prob, val in score.future_outcomes:
            if prob <= 0.001:
                continue
            percent = prob * 100
            p_str = f"{percent:.2f}%" if percent < 1.0 else f"{percent:.1f}%"
            child = QTreeWidgetItem([f"{state}: {p_str} → value={val:.2f}"])
            if "Severe" in state or "Diabetic" in state or "Critical" in state:
                child.setForeground(0, QColor(DANGER))
            fut_item.addChild(child)

        calc = QTreeWidgetItem([f"Discounted Future: {score.gamma} * Σ(prob×value) = {score.long_term_value:.2f}"])
        root_item.addChild(calc)

        net = QTreeWidgetItem([f"Net Utility: {score.total_score:.2f}"])
        net.setForeground(0, QColor(ACCENT))
        root_item.addChild(net)

        self.trace_tree.expandAll()
        self.sensitivity_panel.set_score(score)

    def _update_transition_panel(self) -> None:
        """Show before/after transition probabilities from the last history step."""
        while self._transition_layout.count():
            item = self._transition_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

        summary = self._patient.macro_state.transition_impact_summary() if self._patient else None
        if not self._patient or summary is None:
            self._transition_placeholder = _label("No action applied yet.", muted=True)
            self._transition_layout.addWidget(self._transition_placeholder)
            return

        before = summary["before"]
        after = summary["after"]
        states = summary["states"]

        self._transition_layout.addWidget(
            _label(f"Action: {summary['action_name']}  |  State at time: {summary['state']}", bold=True)
        )

        changed = False
        for from_state in states:
            for to_state in states:
                p_before = before[from_state][to_state]
                p_after = after[from_state][to_state]
                if abs(p_after - p_before) > 1e-9:
                    changed = True
                    diff = p_after - p_before
                    arrow = "↑" if diff > 0 else "↓"
                    color = SUCCESS if diff > 0 else DANGER
                    row_text = (
                        f"{from_state} → {to_state}:   "
                        f"{p_before:.3f}  →  {p_after:.3f}  {arrow}"
                    )
                    lbl = _label(row_text)
                    lbl.setStyleSheet(
                        f"color: {color}; background: transparent; border: none; font-size: 13px;"
                    )
                    self._transition_layout.addWidget(lbl)

        if not changed:
            self._transition_layout.addWidget(
                _label("No transition probabilities changed.", muted=True)
            )

    def _on_apply_action(self) -> None:
        if self._patient is None or not self._actions:
            return
        idx = self._action_combo.currentIndex()
        if idx < 0:
            return
        self._patient = self._patient.apply_action(self._actions[idx])
        self._refresh()

    def _on_simulate_progression(self) -> None:
        """Simulate one disease progression step."""
        if self._patient is None:
            return
        new_macro = self._patient.macro_state.simulate_step()
        self._patient = Patient(
            patient_id=self._patient.patient_id,
            name=self._patient.name,
            disease_name=self._patient.disease_name,
            macro_state=new_macro,
        )
        self._refresh()

    # -----------------------------------------------------------------------
    # Clinician decision tracking handlers
    # -----------------------------------------------------------------------
    def _on_accept(self) -> None:
        """Log that the clinician accepted the top recommendation."""
        if not self._current_scores or self._patient is None:
            return
        top_score = self._current_scores[0]
        log_recommendation(
            patient_id=self._patient.patient_id,
            recommended_action=top_score.action.name,
            recommended_score=top_score.total_score,
            clinician_decision='accept'
        )
        self._show_confirmation(f"✓ Decision recorded: Accepted — {top_score.action.name}")

    def _on_reject(self) -> None:
        """Log that the clinician rejected the recommendation (no action taken)."""
        if not self._current_scores or self._patient is None:
            return
        top_score = self._current_scores[0]
        log_recommendation(
            patient_id=self._patient.patient_id,
            recommended_action=top_score.action.name,
            recommended_score=top_score.total_score,
            clinician_decision='reject'
        )
        self._show_confirmation("✗ Decision recorded: Rejected — No action taken")

    def _on_override(self) -> None:
        """Log that the clinician chose a different action (selected row)."""
        selected = self._table.selectedItems()
        if not selected or not self._current_scores or self._patient is None:
            self._show_confirmation("⚠ Please select an action to override with.", is_error=True)
            return
        row = selected[0].row()
        if row >= len(self._current_scores):
            return
        
        # Prevent overriding with the same action (that's just Accept)
        if row == 0:
            top_score = self._current_scores[0]
            self._show_confirmation(
                f"That is the top recommendation — use Accept instead (Accepted — {top_score.action.name})",
                is_error=True
            )
            return
        
        selected_score = self._current_scores[row]
        top_score = self._current_scores[0]

        log_recommendation(
            patient_id=self._patient.patient_id,
            recommended_action=top_score.action.name,
            recommended_score=top_score.total_score,
            clinician_decision='override',
            override_action=selected_score.action.name
        )
        self._show_confirmation(f"↩ Decision recorded: Override — {selected_score.action.name}")

    def _show_confirmation(self, message: str, is_error: bool = False, duration_seconds: int = 3):
        """Show a temporary confirmation label."""
        self.confirmation_label.setText(message)
        if is_error:
            self.confirmation_label.setStyleSheet("color: #DC3545; background: transparent;")
        else:
            self.confirmation_label.setStyleSheet("color: #28A745; background: transparent;")
        self.confirmation_label.setVisible(True)

        # Hide after duration
        QTimer.singleShot(duration_seconds * 1000, lambda: self.confirmation_label.setVisible(False))


# ---------------------------------------------------------------------------
# Patient management view
# ---------------------------------------------------------------------------
class PatientManagementView(QWidget):
    """
    Patient list panel — browse and select patients using a table.
    """

    patient_selected = pyqtSignal(object, object)

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._patients: list = []
        self._filtered_patients: list = []
        self._build()

    def _build(self) -> None:
        self.setStyleSheet(f"background: {CONTENT_BG};")

        root = QVBoxLayout(self)
        root.setContentsMargins(36, 32, 36, 32)
        root.setSpacing(0)

        # Header
        header = QWidget()
        header.setStyleSheet("background: transparent;")
        hl = QVBoxLayout(header)
        hl.setContentsMargins(0, 0, 0, 20)
        hl.setSpacing(4)
        hl.addWidget(_label("Patient Management", 22, bold=True))
        hl.addWidget(_label("Manage and monitor enrolled patients", 13, muted=True))
        root.addWidget(header)

        # Action bar
        action_bar = QHBoxLayout()
        action_bar.setSpacing(10)

        self.add_btn = QPushButton("+ Add Patient")
        self.add_btn.setFixedHeight(34)
        self.add_btn.setCursor(Qt.PointingHandCursor)
        self.add_btn.setStyleSheet(f"""
            QPushButton {{
                background: {ACCENT};
                color: #ffffff;
                border: none;
                border-radius: 6px;
                font-family: 'Segoe UI';
                font-size: 13px;
                font-weight: 600;
                padding: 0 18px;
            }}
            QPushButton:hover  {{ background: {ACCENT_DARK}; }}
            QPushButton:pressed {{ background: #198f8f; }}
        """)
        self.add_btn.clicked.connect(self._on_add_patient)
        action_bar.addWidget(self.add_btn)

        self.export_btn = QPushButton("↑  Export CSV")
        self.export_btn.setFixedHeight(34)
        self.export_btn.setCursor(Qt.PointingHandCursor)
        self.export_btn.setStyleSheet(f"""
            QPushButton {{
                background: {CARD_BG};
                color: {TEXT_PRIMARY};
                border: 1px solid {BORDER};
                border-radius: 6px;
                font-family: 'Segoe UI';
                font-size: 13px;
                font-weight: 500;
                padding: 0 18px;
            }}
            QPushButton:hover  {{ background: #EEF6F6; border-color: #BACED0; }}
            QPushButton:pressed {{ background: #E4EEEE; }}
        """)
        self.export_btn.clicked.connect(self._export_to_csv)
        action_bar.addWidget(self.export_btn)

        action_bar.addStretch()

        # Search
        search_wrap = QFrame()
        search_wrap.setFixedHeight(34)
        search_wrap.setStyleSheet(f"""
            QFrame {{ background: {CARD_BG}; border: 1px solid {BORDER}; border-radius: 6px; }}
            QFrame:focus-within {{ border: 1px solid {ACCENT}; }}
        """)
        sw_layout = QHBoxLayout(search_wrap)
        sw_layout.setContentsMargins(10, 0, 10, 0)
        sw_layout.setSpacing(6)
        search_icon = QLabel("⌕")
        search_icon.setStyleSheet(
            f"color: {TEXT_MUTED}; background: transparent; border: none; font-size: 15px;"
        )
        sw_layout.addWidget(search_icon)
        self._search = QLineEdit()
        self._search.setPlaceholderText("Search by name, ID, or disease…")
        self._search.setStyleSheet(f"""
            QLineEdit {{
                background: transparent;
                border: none;
                font-family: 'Segoe UI';
                font-size: 13px;
                color: {TEXT_PRIMARY};
            }}
        """)
        self._search.textChanged.connect(self._on_search)
        sw_layout.addWidget(self._search)
        search_wrap.setFixedWidth(280)
        action_bar.addWidget(search_wrap)

        root.addLayout(action_bar)
        root.addSpacing(16)

        self._summary_label = _label("", 12, muted=True)
        self._summary_label.setContentsMargins(2, 0, 0, 6)
        root.addWidget(self._summary_label)

        # Table
        self._table = QTableWidget()
        self._table.setColumnCount(7)
        self._table.setHorizontalHeaderLabels([
            "#", "Patient ID", "Name", "Disease", "Current State", "Severity", "Risk"
        ])

        hdr = self._table.horizontalHeader()
        hdr.setSectionResizeMode(0, QHeaderView.Fixed);       self._table.setColumnWidth(0, 36)
        hdr.setSectionResizeMode(1, QHeaderView.Fixed);       self._table.setColumnWidth(1, 80)
        hdr.setSectionResizeMode(2, QHeaderView.ResizeToContents)
        hdr.setSectionResizeMode(3, QHeaderView.ResizeToContents)
        hdr.setSectionResizeMode(4, QHeaderView.Stretch)
        hdr.setSectionResizeMode(5, QHeaderView.Fixed);       self._table.setColumnWidth(5, 80)
        hdr.setSectionResizeMode(6, QHeaderView.Fixed);       self._table.setColumnWidth(6, RISK_COL_W)

        self._table.verticalHeader().setVisible(False)
        self._table.setEditTriggers(QTableWidget.NoEditTriggers)
        self._table.setSelectionBehavior(QTableWidget.SelectRows)
        self._table.setSelectionMode(QTableWidget.SingleSelection)
        self._table.setShowGrid(False)
        self._table.setFocusPolicy(Qt.StrongFocus)
        self._table.setStyleSheet(f"""
            QTableWidget {{
                background: {CARD_BG};
                border: 1px solid {BORDER};
                border-radius: 10px;
                outline: none;
                font-family: 'Segoe UI';
                font-size: 13px;
                color: {TEXT_PRIMARY};
                gridline-color: transparent;
            }}
            QHeaderView::section {{
                background: #F4F8F8;
                color: {TEXT_MUTED};
                font-family: 'Segoe UI';
                font-size: 11px;
                font-weight: 600;
                text-transform: uppercase;
                letter-spacing: 0.5px;
                padding: 10px 12px;
                border: none;
                border-bottom: 1px solid {BORDER};
            }}
            QHeaderView::section:first {{ border-top-left-radius: 10px; }}
            QHeaderView::section:last  {{ border-top-right-radius: 10px; }}
            QTableWidget::item {{
                padding: 0 12px;
                border-bottom: 1px solid #F0F5F5;
                color: {TEXT_PRIMARY};
            }}
            QTableWidget::item:selected {{ background: #E4F5F5; color: {TEXT_PRIMARY}; }}
            QTableWidget::item:hover    {{ background: {HOVER_ROW}; }}
            QScrollBar:vertical {{ background: transparent; width: 6px; margin: 0; }}
            QScrollBar::handle:vertical {{
                background: #BACED0;
                border-radius: 3px;
                min-height: 30px;
            }}
            QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{ height: 0; }}
        """)
        self._table.itemDoubleClicked.connect(self._on_row_double_clicked)
        root.addWidget(self._table, 1)

    def set_patients(self, patients) -> None:
        self._patients = patients
        self._refresh_table()

    def _refresh_table(self, filter_text: str = "") -> None:
        detailed_patients = get_all_patients_detailed()
        patient_details: dict = {d["patient_id"]: d for d in detailed_patients}

        self._table.setRowCount(0)
        self._filtered_patients = []
        filter_lower = filter_text.lower().strip()

        for record in self._patients:
            if filter_lower:
                haystack = " ".join([
                    record.patient.name or "",
                    record.patient.patient_id or "",
                    record.patient.disease_name or "",
                ]).lower()
                if filter_lower not in haystack:
                    continue
            self._filtered_patients.append(record)

        self._table.setRowCount(len(self._filtered_patients))
        ROW_H = 44

        for row, record in enumerate(self._filtered_patients):
            self._table.setRowHeight(row, ROW_H)
            detail   = patient_details.get(record.patient.patient_id, {})
            severity = detail.get("severity_level", 3)
            risk     = self._get_risk_level(severity)

            # Col 0 — row number
            num_item = QTableWidgetItem(str(row + 1))
            num_item.setTextAlignment(Qt.AlignCenter)
            num_item.setForeground(QColor(TEXT_MUTED))
            self._table.setItem(row, 0, num_item)

            # Col 1 — Patient ID
            pid_item = QTableWidgetItem(record.patient.patient_id)
            pid_item.setFont(QFont("Consolas", 12))
            pid_item.setForeground(QColor(ACCENT_DARK))
            self._table.setItem(row, 1, pid_item)

            # Col 2 — Name
            self._table.setItem(row, 2, QTableWidgetItem(record.patient.name or "Unnamed"))

            # Col 3 — Disease
            dis_item = QTableWidgetItem(record.patient.disease_name or "Unknown")
            dis_item.setForeground(QColor(TEXT_MUTED))
            self._table.setItem(row, 3, dis_item)

            # Col 4 — Current State
            state = getattr(record.patient, "current_state", "—")
            self._table.setItem(row, 4, QTableWidgetItem(state))

            # Col 5 — Severity dot + number
            sev_item = QTableWidgetItem(f"  \u25cf {severity}")
            sev_item.setTextAlignment(Qt.AlignVCenter | Qt.AlignLeft)
            sev_item.setForeground(QColor(SEV_COLORS.get(severity, TEXT_MUTED)))
            font_sev = QFont("Segoe UI", 13)
            font_sev.setBold(True)
            sev_item.setFont(font_sev)
            self._table.setItem(row, 5, sev_item)

            # Col 6 — Risk badge
            badge = _Badge(risk)
            cell_widget = QWidget()
            cell_widget.setStyleSheet("background: transparent;")
            cl = QHBoxLayout(cell_widget)
            cl.setContentsMargins(0, 0, 0, 0)
            cl.setSpacing(0)
            cl.setAlignment(Qt.AlignCenter)
            cl.addWidget(badge)
            self._table.setCellWidget(row, 6, cell_widget)

        n = len(self._filtered_patients)
        self._summary_label.setText(f"{n} patient{'s' if n != 1 else ''} displayed")

    def _get_risk_level(self, severity: int) -> str:
        if severity <= 2:
            return "Low"
        elif severity <= 4:
            return "Medium"
        return "High"

    def _on_search(self, text: str) -> None:
        self._refresh_table(text)

    def _on_row_double_clicked(self, item) -> None:
        row = item.row()
        if 0 <= row < len(self._filtered_patients):
            record = self._filtered_patients[row]
            self.patient_selected.emit(record.patient, record.actions)

    def _on_add_patient(self) -> None:
        from .add_patient_dialog import AddPatientDialog
        dialog = AddPatientDialog(self)
        if dialog.exec_():
            self._load_and_refresh()

    def _export_to_csv(self) -> None:
        from ..infrastructure.database import get_patient_summary_export
        import csv
        from datetime import datetime

        patients = get_patient_summary_export()
        if not patients:
            QMessageBox.warning(self, "Export Error", "No patient data to export.")
            return

        filename, _ = QFileDialog.getSaveFileName(
            self, "Save Patient List",
            f"patients_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv",
            "CSV Files (*.csv)"
        )
        if not filename:
            return

        try:
            with open(filename, "w", newline="", encoding="utf-8") as f:
                writer = csv.writer(f)
                writer.writerow(["Patient ID", "First Name", "Last Name", "Disease",
                                 "Current State", "Severity Level", "Model Version"])
                for p in patients:
                    writer.writerow([
                        p["patient_id"], p["first_name"], p["last_name"],
                        p["disease_name"], p["current_state"],
                        p["severity_level"], p["model_version"],
                    ])
            QMessageBox.information(self, "Export Successful",
                                    f"Patient list exported to:\n{filename}")
        except Exception as e:
            QMessageBox.critical(self, "Export Failed",
                                 f"An error occurred while exporting:\n{str(e)}")

    def _load_and_refresh(self) -> None:
        from ..infrastructure.patient_service import load_patients_with_actions
        self.set_patients(load_patients_with_actions())


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

        nav_items = ["Dashboard", "Patients", "Patient Management", "Analytics", "Trends", "Audit Log"]

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


# ---------------------------------------------------------------------------
# Main window
# ---------------------------------------------------------------------------
class MainWindow(QMainWindow):
    """
    Application shell — sidebar navigation + stacked content views.

    Views:
        0 — Dashboard
        1 — Patient view (loaded from patient management)
        2 — Patient Management
        3 — Analytics / Patient Comparison
        4 — Population Trends
        5 — Audit Log
    """

    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle("Clinical Decision Support System")
        self.setMinimumSize(1100, 700)
        self._build()
        self._load_demo_data()

    def _build(self) -> None:
        central = QWidget()
        self.setCentralWidget(central)
        central.setStyleSheet(f"background: {CONTENT_BG};")

        root = QHBoxLayout(central)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        self._sidebar = Sidebar()
        self._sidebar.nav_changed.connect(self._on_nav_changed)
        root.addWidget(self._sidebar)

        self._stack = QStackedWidget()
        self._engine = DecisionEngine()
        self._dashboard_view = DashboardView()
        self._patient_view = PatientView(engine=self._engine)
        self._management_view = PatientManagementView()
        self._management_view.patient_selected.connect(self._on_patient_selected)
        self._analytics_view = ComparisonWidget()
        self._trend_view = TrendWidget()
        self._audit_view = AuditWidget()

        self._stack.addWidget(self._dashboard_view)   # index 0
        self._stack.addWidget(self._patient_view)     # index 1
        self._stack.addWidget(self._management_view)  # index 2
        self._stack.addWidget(self._analytics_view)   # index 3
        self._stack.addWidget(self._trend_view)       # index 4
        self._stack.addWidget(self._audit_view)       # index 5
        root.addWidget(self._stack)

    def _on_nav_changed(self, idx: int) -> None:
        self._stack.setCurrentIndex(idx)

    def _on_patient_selected(self, patient: Patient, actions: list[Action]) -> None:
        """Load selected patient into patient view and navigate to it."""
        self._patient_view.load_patient(patient, actions)
        self._sidebar.set_active(1)
        self._stack.setCurrentIndex(1)

    def _load_demo_data(self) -> None:
        """Load patients from the database via the patient service."""
        from ..infrastructure.patient_service import load_patients_with_actions
        self._management_view.set_patients(load_patients_with_actions())

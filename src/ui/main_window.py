from __future__ import annotations
from PyQt5.QtWidgets import (
    QMainWindow, QWidget, QHBoxLayout, QVBoxLayout,
    QPushButton, QLabel, QListWidget,
    QStackedWidget, QFrame, QTableWidget,
    QTableWidgetItem, QHeaderView, QComboBox, QProgressBar,
    QTreeWidget, QTreeWidgetItem, QScrollArea, QLineEdit,
    QFileDialog, QMessageBox
)
from PyQt5.QtCore import Qt, pyqtSignal, QTimer
from PyQt5.QtGui import QFont, QColor

from ..domain.patient import Patient
from ..domain.action import Action
from ..decision_engine.engine import DecisionEngine, ActionScore
from .comparison_widget import ComparisonWidget
from .trend_widget import TrendWidget
from .sensitivity_panel import SensitivityAnalysisPanel
from .risk_benefit_plot import RiskBenefitPlot
from ..infrastructure.database import get_connection, get_state_distribution, log_recommendation, get_all_patients_detailed
from ..analytics.analytics import state_success_rate
from ..ui.audit_widget import AuditWidget
from .sidebar import Sidebar
from .dashboard_view import DashboardView
from .patient_management_view import PatientManagementView

from .ui_helpers import (
    SIDEBAR_BG, CONTENT_BG, ACCENT, ACCENT_DARK, CARD_BG, TEXT_PRIMARY, TEXT_MUTED,
    BORDER, HOVER_ROW, DANGER, SUCCESS, WARNING, SEV_COLORS,
    RISK_COL_W, _card, _label, _Badge
)


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

        # ── Decision Buttons Row 
        decision_layout = QHBoxLayout()
        decision_layout.setSpacing(12)

        self.accept_btn = QPushButton("✓ Accept Top Recommendation")
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

        self.reject_btn = QPushButton("✗ Reject Recommendation")
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

        self.override_btn = QPushButton("↩ Override with Selected Action")
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

        decision_hint = _label(
            "Click to select an action from the ranking, then record the clinician decision below. "
            "Accept records the top recommendation. Override records the selected lower-ranked action.",
            size=11,
            muted=True
        )
        decision_hint.setWordWrap(True)
        root.addWidget(decision_hint)

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

        trace_hint = _label(
            "This section explains the currently selected action from the ranked list above. "
            "Click a different action row to update the Decision Trace and Sensitivity Analysis.",
            size=11,
            muted=True
        )
        trace_hint.setWordWrap(True)
        root.addWidget(trace_hint)

        # Sensitivity analysis panel
        root.addWidget(_label("Sensitivity Analysis", 15, bold=True))

        self.sensitivity_panel = SensitivityAnalysisPanel()
        self.sensitivity_panel.setMinimumHeight(280)
        root.addWidget(self.sensitivity_panel)

        sensitivity_hint = _label(
            "This panel shows a what-if projected score for the selected action. "
            "Future value weight adjusts the importance of future outcomes, while risk penalty reduces the score based on clinical risk. "
            "Unlike the ranked table's Total Score, this Projected Score includes the risk penalty.",
            size=11,
            muted=True
        )
        sensitivity_hint.setWordWrap(True)
        root.addWidget(sensitivity_hint)


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

        # Transition Impact
        root.addWidget(_label("Transition Impact — Last Action", 15, bold=True))
        self._transition_card = _card()
        self._transition_layout = QVBoxLayout(self._transition_card)
        self._transition_layout.setContentsMargins(16, 12, 16, 12)
        self._transition_layout.setSpacing(4)
        self._transition_placeholder = _label("No action applied yet.", muted=True)
        self._transition_layout.addWidget(self._transition_placeholder)
        root.addWidget(self._transition_card)

        transition_hint = _label(
            "Shows how the last applied action changed transition probabilities from the patient state at the time of action.",
            size=11,
            muted=True
        )
        transition_hint.setWordWrap(True)
        root.addWidget(transition_hint)

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
        from_state = summary["state"]

        for to_state in states:
            p_before = before[from_state][to_state]
            p_after = after[from_state][to_state]

            if abs(p_after - p_before) > 1e-9:
                changed = True
                diff = p_after - p_before
                arrow = "↑" if diff > 0 else "↓"

                color = TEXT_PRIMARY

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
                 f"That is already the top recommendation — use Accept Top Recommendation for {top_score.action.name}.",
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
# Main window
# ---------------------------------------------------------------------------
class MainWindow(QMainWindow):
    """
    Application shell — sidebar navigation + stacked content views.

    Views:
        0 — Dashboard
        1 — Patient Management
        2 — Analytics / Patient Comparison
        3 — Population Trends
        4 — Audit Log
        5 — Patient view (loaded from Patient Management; not navigable directly)
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
        self._stack.addWidget(self._management_view)  # index 1
        self._stack.addWidget(self._analytics_view)   # index 2
        self._stack.addWidget(self._trend_view)       # index 3
        self._stack.addWidget(self._audit_view)       # index 4
        self._stack.addWidget(self._patient_view)     # index 5 — only reached via patient selection
        root.addWidget(self._stack)

    def _on_nav_changed(self, idx: int) -> None:
        if idx == 0:
            self._dashboard_view._load_stats()
        elif idx == 4:
            self._audit_view._refresh()
        self._stack.setCurrentIndex(idx)

    def _on_patient_selected(self, patient: Patient, actions: list[Action]) -> None:
        """Load selected patient into patient view and navigate to it."""
        self._patient_view.load_patient(patient, actions)
        self._sidebar.set_active(1)
        self._stack.setCurrentIndex(5)

    def _load_demo_data(self) -> None:
        """Load patients from the database via the patient service."""
        from ..infrastructure.patient_service import load_patients_with_actions
        self._management_view.set_patients(load_patients_with_actions())



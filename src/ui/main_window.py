from __future__ import annotations
from PyQt5.QtWidgets import (
    QMainWindow, QWidget, QHBoxLayout, QVBoxLayout,
    QPushButton, QLabel, QListWidget, QListWidgetItem,
    QStackedWidget, QFrame, QSizePolicy, QTableWidget,
    QTableWidgetItem, QHeaderView, QComboBox, QProgressBar
)
from PyQt5.QtCore import Qt
from PyQt5.QtGui import QFont, QColor

from ..domain.patient import Patient
from ..domain.action import Action
from ..decision_engine.engine import DecisionEngine, ActionScore
from ..domain.patient_record import PatientRecord
from .comparison_widget import ComparisonWidget


# ---------------------------------------------------------------------------
# Colour palette — matches Figma teal/mint theme
# ---------------------------------------------------------------------------
SIDEBAR_BG   = "#1B2A2F"
CONTENT_BG   = "#F0F7F7"
ACCENT       = "#2ABFBF"
CARD_BG      = "#FFFFFF"
TEXT_PRIMARY = "#1B2A2F"
TEXT_MUTED   = "#6B8A8A"
DANGER       = "#E05C5C"
SUCCESS      = "#4CAF82"


def _card(parent: QWidget | None = None) -> QFrame:
    """Return a styled white card frame."""
    frame = QFrame(parent)
    frame.setStyleSheet(f"""
        QFrame {{
            background: {CARD_BG};
            border-radius: 8px;
            border: 1px solid #DDE8E8;
        }}
    """)
    return frame


def _label(text: str, size: int = 13, bold: bool = False, muted: bool = False) -> QLabel:
    """Return a styled QLabel."""
    lbl = QLabel(text)
    font = QFont("Segoe UI", size)
    font.setBold(bold)
    lbl.setFont(font)
    color = TEXT_MUTED if muted else TEXT_PRIMARY
    lbl.setStyleSheet(f"color: {color}; background: transparent; border: none;")
    return lbl


# ---------------------------------------------------------------------------
# Dashboard view
# ---------------------------------------------------------------------------

class DashboardView(QWidget):
    """
    Overview panel — shows summary stats and high-level system status.
    """

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._build()

    def _build(self) -> None:
        root = QVBoxLayout(self)
        root.setContentsMargins(32, 32, 32, 32)
        root.setSpacing(20)

        root.addWidget(_label("Clinical Decision Dashboard", 20, bold=True))
        root.addWidget(_label("Active patients, risk alerts, and model status", muted=True))

        stats_row = QHBoxLayout()
        stats_row.setSpacing(16)
        for title, value in [
            ("Active Patients", "—"),
            ("High-Risk Cases", "—"),
            ("Pending Follow-Ups", "—"),
        ]:
            card = _card()
            layout = QVBoxLayout(card)
            layout.setContentsMargins(20, 16, 20, 16)
            layout.addWidget(_label(title, muted=True))
            layout.addWidget(_label(value, 24, bold=True))
            stats_row.addWidget(card)
        root.addLayout(stats_row)

        note = _label(
            "Charts and live statistics will be available once the persistence layer is added (week 6).",
            muted=True,
        )
        note.setWordWrap(True)
        root.addWidget(note)
        root.addStretch()


# ---------------------------------------------------------------------------
# Patient view — ranked actions + history
# ---------------------------------------------------------------------------

class PatientView(QWidget):
    """
    Clinical overview for a single patient.
    Displays current state, ranked actions with scores, and action history.
    """

    def __init__(self, engine: DecisionEngine, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._patient: Patient | None = None
        self._actions: list[Action] = []
        self._engine = engine
        self._build()

    def _build(self) -> None:
        root = QVBoxLayout(self)
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
        self._state_label = _label("—", 22, bold=True)
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
                border: 1px solid #DDE8E8;
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
            QPushButton:hover {{ background: #23A8A8; }}
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
        self._table.setStyleSheet(f"""
            QTableWidget {{
                background: {CARD_BG};
                border: 1px solid #DDE8E8;
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

        root.addWidget(_label("Recommendation Explanation", 15, bold=True))

        self._explanation_box = QLabel("No recommendation available.")
        self._explanation_box.setWordWrap(True)
        self._explanation_box.setStyleSheet(f"""
            QLabel {{
                background: {CARD_BG};
                border: 1px solid #D9E4E8;
                border-radius: 10px;
                padding: 12px;
                color: {TEXT_PRIMARY};
            }}
        """)
        root.addWidget(self._explanation_box)

        # History
        root.addWidget(_label("Action History", 15, bold=True))
        self._history_table = QTableWidget(0, 3)
        self._history_table.setHorizontalHeaderLabels(["Step", "State", "Action"])
        self._history_table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self._history_table.setEditTriggers(QTableWidget.NoEditTriggers)
        self._history_table.setSelectionBehavior(QTableWidget.SelectRows)
        self._history_table.setMaximumHeight(150)

        self._history_table.setStyleSheet(f"""
            QTableWidget {{
                background: {CARD_BG};
                border: 1px solid #DDE8E8;
                border-radius: 8px;
                gridline-color: #EEF3F3;
                font-size: 13px;
            }}
        """)

        root.addWidget(self._history_table)

        # Transition impact panel
        root.addWidget(_label("Transition Impact — Last Action", 15, bold=True))
        self._transition_card = _card()
        self._transition_layout = QVBoxLayout(self._transition_card)
        self._transition_layout.setContentsMargins(16, 12, 16, 12)
        self._transition_layout.setSpacing(4)
        self._transition_placeholder = _label("No action applied yet.", muted=True)
        self._transition_layout.addWidget(self._transition_placeholder)
        root.addWidget(self._transition_card)

    def load_patient(self, patient: Patient, actions: list[Action]) -> None:
        """Load a patient and compute ranked actions."""
        self._patient = patient
        self._actions = actions
        self._refresh()

    def _refresh(self) -> None:
        if self._patient is None:
            return

        self._header.setText(f"Patient — {self._patient.name or self._patient.patient_id}")
        self._subheader.setText(f"ID: {self._patient.patient_id}")
        self._state_label.setText(self._patient.current_state_label())
        self._disease_label.setText(self._patient.disease_name or "Unknown")
        self._model_label.setText(self._patient.model_size_label())

        # Populate action dropdown
        self._action_combo.clear()
        for action in self._actions:
            self._action_combo.addItem(action.name)

        # Ranked actions table
        scores = self._engine.rank_actions(self._patient.macro_state, self._actions)
        
        if scores:
            best = scores[0]
            print("DEBUG RISK:", best.risk_score, best.risk_level)
            self._risk_label.setText(f"Risk Score: {best.risk_score:.1f} ({best.risk_level})")
            self._risk_bar.setValue(int(best.risk_score))
            self._explanation_box.setText(best.explanation)

            if best.risk_level == "Low":
                self._risk_label.setStyleSheet("color: #228B22; font-weight: bold;")
            elif best.risk_level == "Medium":
                self._risk_label.setStyleSheet("color: #D48806; font-weight: bold;")
            else:
                self._risk_label.setStyleSheet("color: #C62828; font-weight: bold;")
        else:
            self._risk_label.setText("Risk Score: —")
            self._risk_bar.setValue(0)
            self._explanation_box.setText("No recommendation available.")
            self._risk_label.setStyleSheet("font-weight: bold;")

        self._table.setRowCount(len(scores))
        for row, score in enumerate(scores):
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

        # History
        history = self._patient.macro_state.history
        self._history_table.setRowCount(len(history))

        for i, step in enumerate(history):
            self._history_table.setItem(i, 0, QTableWidgetItem(f"Step {i+1}"))
            self._history_table.setItem(i, 1, QTableWidgetItem(step.state))
            self._history_table.setItem(i, 2, QTableWidgetItem(step.action.name))

        # Transition impact panel
        self._update_transition_panel()

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
        after  = summary["after"]
        states = summary["states"]

        self._transition_layout.addWidget(
            _label(f"Action: {summary['action_name']}  |  State at time: {summary['state']}", bold=True)
        )

        changed = False
        for from_state in states:
            for to_state in states:
                p_before = before[from_state][to_state]
                p_after  = after[from_state][to_state]
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
        """Simulate one disease progression step — advances the current micro-state s."""
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


# ---------------------------------------------------------------------------
# Patient management view
# ---------------------------------------------------------------------------

class PatientManagementView(QWidget):
    """
    Patient list panel — browse and select patients.
    """

    from PyQt5.QtCore import pyqtSignal
    patient_selected = pyqtSignal(object, object)

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._patients: list[PatientRecord] = []
        self._build()

    def _build(self) -> None:
        root = QVBoxLayout(self)
        root.setContentsMargins(32, 32, 32, 32)
        root.setSpacing(16)

        root.addWidget(_label("Patient Management", 20, bold=True))
        root.addWidget(_label("Select a patient to view their clinical overview.", muted=True))

        self._list = QListWidget()
        self._list.setStyleSheet(f"""
            QListWidget {{
                background: {CARD_BG};
                border: 1px solid #DDE8E8;
                border-radius: 8px;
                font-size: 14px;
                color: {TEXT_PRIMARY};
            }}
            QListWidget::item:selected {{
                background: #D6F0F0;
                color: {TEXT_PRIMARY};
            }}
            QListWidget::item {{ padding: 10px; }}
        """)
        self._list.itemClicked.connect(self._on_patient_clicked)
        root.addWidget(self._list)

    def set_patients(self, patients: list[PatientRecord]) -> None:
        """Populate the list with PatientRecord objects."""
        self._patients = patients
        self._list.clear()
        for record in patients:
            label = f"{record.patient.name or 'Unnamed'}  —  ID: {record.patient.patient_id}  —  {record.patient.disease_name}  —  State: {record.patient.current_state}"
            self._list.addItem(label)

    def _on_patient_clicked(self, item: QListWidgetItem) -> None:
        idx = self._list.row(item)
        if 0 <= idx < len(self._patients):
            record = self._patients[idx]
            self.patient_selected.emit(record.patient, record.actions)


# ---------------------------------------------------------------------------
# Sidebar
# ---------------------------------------------------------------------------

class Sidebar(QWidget):
    from PyQt5.QtCore import pyqtSignal
    nav_changed = pyqtSignal(int)

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setFixedWidth(200)
        self.setStyleSheet(f"background: {SIDEBAR_BG};")
        self._buttons: list[QPushButton] = []
        self._build()

    def _build(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 24, 0, 24)
        layout.setSpacing(4)

        title = _label("  CDSS", 16, bold=True)
        title.setStyleSheet(f"color: {ACCENT}; background: transparent; border: none; padding: 8px 16px;")
        layout.addWidget(title)
        layout.addSpacing(16)

        for i, name in enumerate(["Dashboard", "Patients", "Patient Management", "Analytics"]):
            btn = QPushButton(f"  {name}")
            btn.setCheckable(True)
            btn.setFixedHeight(42)
            btn.setFont(QFont("Segoe UI", 12))
            btn.setStyleSheet(f"""
                QPushButton {{
                    background: transparent;
                    color: #A8C4C4;
                    border: none;
                    text-align: left;
                    padding-left: 20px;
                    border-radius: 0;
                }}
                QPushButton:checked {{
                    background: {ACCENT};
                    color: white;
                }}
                QPushButton:hover:!checked {{
                    background: #243438;
                    color: white;
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
            btn.setChecked(i == idx)
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
        self._comparison_view = ComparisonWidget()

        self._stack.addWidget(self._dashboard_view)     # index 0
        self._stack.addWidget(self._patient_view)       # index 1
        self._stack.addWidget(self._management_view)    # index 2
        self._stack.addWidget(self._comparison_view)    # index 3
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
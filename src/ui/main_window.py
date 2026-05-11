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
from .patient_view import PatientView

from .ui_helpers import (
    SIDEBAR_BG, CONTENT_BG, ACCENT, ACCENT_DARK, CARD_BG, TEXT_PRIMARY, TEXT_MUTED,
    BORDER, HOVER_ROW, DANGER, SUCCESS, WARNING, SEV_COLORS,
    RISK_COL_W, _card, _label, _Badge
)

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



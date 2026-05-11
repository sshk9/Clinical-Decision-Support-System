from __future__ import annotations

from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QPushButton, QLabel,
    QFrame, QLineEdit, QTableWidget, QTableWidgetItem,
    QHeaderView, QFileDialog, QMessageBox
)
from PyQt5.QtCore import Qt, pyqtSignal
from PyQt5.QtGui import QFont, QColor

from ..ui_helpers import (
    CONTENT_BG, ACCENT, ACCENT_DARK, CARD_BG, TEXT_PRIMARY,
    TEXT_MUTED, BORDER, HOVER_ROW, SEV_COLORS, RISK_COL_W,
    _label, _Badge
)
from ...application.patient_management_service import (
    get_detailed_patients,
    get_patient_export_rows,
    reload_patients_with_actions,
)

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
        detailed_patients = get_detailed_patients()
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
        from ..dialogs.add_patient_dialog import AddPatientDialog
        dialog = AddPatientDialog(self)
        if dialog.exec_():
            self._load_and_refresh()

    def _export_to_csv(self) -> None:
        import csv
        from datetime import datetime

        patients = get_patient_export_rows()
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
        self.set_patients(reload_patients_with_actions())
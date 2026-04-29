from __future__ import annotations
from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QComboBox,
    QTableWidget, QTableWidgetItem, QHeaderView, QPushButton,
    QFileDialog, QMessageBox
)
from PyQt5.QtCore import Qt
from PyQt5.QtGui import QFont, QColor
import csv
from datetime import datetime

from ..infrastructure.database import get_audit_log, get_all_patients

# Colour palette
ACCENT = "#2ABFBF"
TEXT_PRIMARY = "#1B2A2F"
TEXT_MUTED = "#6B8A8A"
CARD_BG = "#FFFFFF"
CONTENT_BG = "#F0F7F7"


class AuditWidget(QWidget):
    """
    Audit log viewer – shows all clinician decisions with filtering and export.
    """

    def __init__(self, parent=None):
        super().__init__(parent)
        self._build()
        self._load_patients()
        self._refresh()

    def _build(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(32, 32, 32, 32)
        root.setSpacing(20)

        # Header
        title = QLabel("Clinical Decision Audit Log")
        title.setFont(QFont("Segoe UI", 22, QFont.Bold))
        title.setStyleSheet(f"color: {TEXT_PRIMARY};")
        root.addWidget(title)

        subtitle = QLabel("Complete history of clinician decisions and recommendations")
        subtitle.setStyleSheet(f"color: {TEXT_MUTED};")
        root.addWidget(subtitle)

        # Filter row
        filter_layout = QHBoxLayout()
        filter_layout.setSpacing(15)

        filter_label = QLabel("Filter by Patient:")
        filter_label.setStyleSheet(f"color: {TEXT_PRIMARY}; font-weight: bold;")
        filter_layout.addWidget(filter_label)

        self.patient_filter = QComboBox()
        self.patient_filter.setMinimumWidth(250)
        self.patient_filter.setFixedHeight(35)
        self.patient_filter.setStyleSheet(f"""
            QComboBox {{
                background: {CARD_BG};
                border: 1px solid #DDE8E8;
                border-radius: 6px;
                padding: 6px 12px;
                font-size: 13px;
            }}
            QComboBox:focus {{
                border-color: {ACCENT};
            }}
        """)
        self.patient_filter.currentTextChanged.connect(self._refresh)
        filter_layout.addWidget(self.patient_filter)

        filter_layout.addStretch()

        # Export button
        self.export_btn = QPushButton("Export to CSV")
        self.export_btn.setFixedHeight(35)
        self.export_btn.setStyleSheet(f"""
            QPushButton {{
                background-color: {ACCENT};
                color: white;
                border-radius: 6px;
                font-weight: bold;
                padding: 0 16px;
            }}
            QPushButton:hover {{ background-color: #23A8A8; }}
        """)
        self.export_btn.clicked.connect(self._export_to_csv)
        filter_layout.addWidget(self.export_btn)

        root.addLayout(filter_layout)

        self.table = QTableWidget()
        self.table.setColumnCount(6)
        self.table.setHorizontalHeaderLabels([
            "Timestamp", "Patient", "Recommended Action", "Score", "Decision", "Override Action"
        ])
        self.table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeToContents)
        self.table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeToContents)
        self.table.horizontalHeader().setSectionResizeMode(2, QHeaderView.Stretch)
        self.table.horizontalHeader().setSectionResizeMode(3, QHeaderView.ResizeToContents)
        self.table.horizontalHeader().setSectionResizeMode(4, QHeaderView.ResizeToContents)
        self.table.horizontalHeader().setSectionResizeMode(5, QHeaderView.Stretch)
        self.table.setEditTriggers(QTableWidget.NoEditTriggers)
        self.table.setAlternatingRowColors(True)
        self.table.setStyleSheet(f"""
            QTableWidget {{
                background: {CARD_BG};
                border: 1px solid #DDE8E8;
                border-radius: 8px;
                gridline-color: #EEF3F3;
                font-size: 12px;
            }}
            QHeaderView::section {{
                background: #EEF3F3;
                color: {TEXT_MUTED};
                font-size: 11px;
                padding: 8px;
                font-weight: bold;
            }}
        """)
        root.addWidget(self.table)

        # Empty state label
        self.empty_label = QLabel("No audit records found")
        self.empty_label.setAlignment(Qt.AlignCenter)
        self.empty_label.setStyleSheet(f"color: {TEXT_MUTED}; font-size: 14px; padding: 40px;")
        self.empty_label.setVisible(False)
        root.addWidget(self.empty_label)

    def _load_patients(self):
        """Load patients from database into the filter dropdown."""
        patients = get_all_patients()
        self.patient_filter.addItem("All Patients", None)
        for pid, name, state, disease in patients:
            display = f"{name} ({pid}) – {disease}"
            self.patient_filter.addItem(display, pid)

    def _refresh(self):
        """Refresh the table based on the selected filter."""
        patient_id = self.patient_filter.currentData()
        records = get_audit_log(patient_id)

        if not records:
            self.table.setVisible(False)
            self.empty_label.setVisible(True)
            return

        self.table.setVisible(True)
        self.empty_label.setVisible(False)

        self.table.setRowCount(len(records))
        for row, rec in enumerate(records):
            (pid, patient_name, recommended_action, score, decision, override_action, timestamp) = rec

            # Format timestamp
            if timestamp:
                try:
                    ts = timestamp.replace("T", " ").split(".")[0]
                except:
                    ts = str(timestamp)
            else:
                ts = ""

            self.table.setItem(row, 0, QTableWidgetItem(ts))
            self.table.setItem(row, 1, QTableWidgetItem(patient_name))
            self.table.setItem(row, 2, QTableWidgetItem(recommended_action or ""))
            self.table.setItem(row, 3, QTableWidgetItem(f"{score:.3f}" if score else ""))

            # Decision cell with colour coding
            decision_item = QTableWidgetItem(decision.upper() if decision else "")
            if decision == "accept":
                decision_item.setForeground(QColor("#28A745"))  # green
            elif decision == "reject":
                decision_item.setForeground(QColor("#DC3545"))  # red
            elif decision == "override":
                decision_item.setForeground(QColor("#FD7E14"))  # amber
            self.table.setItem(row, 4, decision_item)

            self.table.setItem(row, 5, QTableWidgetItem(override_action or ""))

        # Resize rows to contents
        self.table.resizeRowsToContents()

    def _export_to_csv(self):
        """Export the current table contents to a CSV file."""
        if self.table.rowCount() == 0:
            QMessageBox.warning(self, "Export Error", "No data to export.")
            return

        # Ask user for save location
        filename, _ = QFileDialog.getSaveFileName(
            self,
            "Save Audit Log",
            f"audit_log_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv",
            "CSV Files (*.csv)"
        )
        if not filename:
            return

        try:
            with open(filename, 'w', newline='', encoding='utf-8') as f:
                writer = csv.writer(f)
                # Write header
                headers = ["Timestamp", "Patient", "Recommended Action", "Score", "Decision", "Override Action"]
                writer.writerow(headers)
                # Write data rows
                for row in range(self.table.rowCount()):
                    row_data = []
                    for col in range(self.table.columnCount()):
                        item = self.table.item(row, col)
                        row_data.append(item.text() if item else "")
                    writer.writerow(row_data)

            QMessageBox.information(
                self,
                "Export Successful",
                f"Audit log exported to:\n{filename}"
            )
        except Exception as e:
            QMessageBox.critical(
                self,
                "Export Failed",
                f"An error occurred while exporting:\n{str(e)}"
            )

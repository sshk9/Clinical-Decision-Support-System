from __future__ import annotations
from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QComboBox,
    QTableWidget, QTableWidgetItem, QHeaderView, QPushButton,
    QFileDialog, QMessageBox, QFrame
)
from PyQt5.QtCore import Qt
from PyQt5.QtGui import QFont, QColor
import csv
from datetime import datetime
from ..infrastructure.database import get_audit_log, get_all_patients

ACCENT = "#2ABFBF"
TEXT_PRIMARY = "#1B2A2F"
TEXT_MUTED = "#6B8A8A"
CARD_BG = "#FFFFFF"
CONTENT_BG = "#F0F7F7"


class AuditWidget(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self._build()
        self._load_patients()
        self._refresh()

    def _build(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(28, 24, 28, 24)  # tighter margins
        root.setSpacing(0)  # control spacing manually per section

        # ── Header block ─────────────────────────────────────────────
        header_layout = QHBoxLayout()
        header_layout.setSpacing(0)

        title_block = QVBoxLayout()
        title_block.setSpacing(2)  # tight title/subtitle gap

        title = QLabel("Clinical Decision Audit Log")
        title.setFont(QFont("Segoe UI", 18, QFont.Bold))
        title.setStyleSheet(f"color: {TEXT_PRIMARY};")
        title_block.addWidget(title)

        subtitle = QLabel("Complete history of clinician decisions and recommendations")
        subtitle.setStyleSheet(f"color: {TEXT_MUTED}; font-size: 12px;")
        title_block.addWidget(subtitle)

        header_layout.addLayout(title_block)
        header_layout.addStretch()

        # Export button lives in the header row, top-right
        self.export_btn = QPushButton("Export to CSV")
        self.export_btn.setFixedHeight(32)
        self.export_btn.setStyleSheet(f"""
            QPushButton {{
                background-color: {ACCENT};
                color: white;
                border-radius: 6px;
                font-weight: bold;
                font-size: 12px;
                padding: 0 14px;
                border: none;
            }}
            QPushButton:hover {{ background-color: #23A8A8; }}
        """)
        self.export_btn.clicked.connect(self._export_to_csv)
        header_layout.addWidget(self.export_btn, alignment=Qt.AlignVCenter)

        root.addLayout(header_layout)
        root.addSpacing(16)  # gap between header and toolbar

        # ── Toolbar (filter row) ──────────────────────────────────────
        toolbar = QHBoxLayout()
        toolbar.setSpacing(8)

        filter_label = QLabel("Filter by Patient:")
        filter_label.setStyleSheet(f"color: {TEXT_PRIMARY}; font-size: 12px; font-weight: bold;")
        filter_label.setFixedHeight(32)
        toolbar.addWidget(filter_label)

        self.patient_filter = QComboBox()
        self.patient_filter.setFixedHeight(32)
        self.patient_filter.setMinimumWidth(220)
        self.patient_filter.setMaximumWidth(320)
        self.patient_filter.setStyleSheet(f"""
            QComboBox {{
                background: {CARD_BG};
                border: 1px solid #DDE8E8;
                border-radius: 6px;
                padding: 4px 10px;
                font-size: 12px;
                color: {TEXT_PRIMARY};
            }}
            QComboBox:focus {{ border-color: {ACCENT}; }}
            QComboBox::drop-down {{ border: none; width: 20px; }}
        """)
        self.patient_filter.currentTextChanged.connect(self._refresh)
        toolbar.addWidget(self.patient_filter)
        toolbar.addStretch()  # pushes filter left, nothing right (export moved to header)

        root.addLayout(toolbar)
        root.addSpacing(12)  # gap before table

        # ── Divider ───────────────────────────────────────────────────
        line = QFrame()
        line.setFrameShape(QFrame.HLine)
        line.setStyleSheet("color: #DDE8E8;")
        root.addWidget(line)
        root.addSpacing(0)

        # ── Table ─────────────────────────────────────────────────────
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
        self.table.verticalHeader().setVisible(False)
        self.table.setShowGrid(False)
        self.table.setStyleSheet(f"""
            QTableWidget {{
                background: {CARD_BG};
                border: 1px solid #DDE8E8;
                border-radius: 8px;
                font-size: 12px;
                color: {TEXT_PRIMARY};
                outline: none;
            }}
            QTableWidget::item {{
                padding: 6px 10px;
                border-bottom: 1px solid #F0F7F7;
            }}
            QTableWidget::item:selected {{
                background: #E8F9F9;
                color: {TEXT_PRIMARY};
            }}
            QHeaderView::section {{
                background: #F5FAFA;
                color: {TEXT_MUTED};
                font-size: 11px;
                font-weight: bold;
                padding: 6px 10px;
                border: none;
                border-bottom: 1px solid #DDE8E8;
            }}
            QTableWidget::item:alternate {{
                background: #FAFEFE;
            }}
        """)
        root.addWidget(self.table)

        # ── Empty state ───────────────────────────────────────────────
        self.empty_label = QLabel("No audit records found")
        self.empty_label.setAlignment(Qt.AlignCenter)
        self.empty_label.setStyleSheet(
            f"color: {TEXT_MUTED}; font-size: 13px; padding: 32px;"
            f" border: 1px solid #DDE8E8; border-radius: 8px; background: {CARD_BG};"
        )
        self.empty_label.setVisible(False)
        root.addWidget(self.empty_label)

    def _load_patients(self):
        patients = get_all_patients()
        self.patient_filter.addItem("All Patients", None)
        for pid, name, state, disease in patients:
            self.patient_filter.addItem(f"{name} ({pid}) – {disease}", pid)

    def _refresh(self):
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

            if timestamp:
                try:
                    ts = timestamp.replace("T", " ").split(".")[0]
                except Exception:
                    ts = str(timestamp)
            else:
                ts = ""

            self.table.setItem(row, 0, QTableWidgetItem(ts))
            self.table.setItem(row, 1, QTableWidgetItem(patient_name))
            self.table.setItem(row, 2, QTableWidgetItem(recommended_action or ""))
            self.table.setItem(row, 3, QTableWidgetItem(f"{score:.3f}" if score else ""))

            decision_item = QTableWidgetItem(decision.upper() if decision else "")
            if decision == "accept":
                decision_item.setForeground(QColor("#28A745"))
            elif decision == "reject":
                decision_item.setForeground(QColor("#DC3545"))
            elif decision == "override":
                decision_item.setForeground(QColor("#FD7E14"))
            self.table.setItem(row, 4, decision_item)
            self.table.setItem(row, 5, QTableWidgetItem(override_action or ""))

        self.table.resizeRowsToContents()

    def _export_to_csv(self):
        if self.table.rowCount() == 0:
            QMessageBox.warning(self, "Export Error", "No data to export.")
            return

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
                writer.writerow(["Timestamp", "Patient", "Recommended Action", "Score", "Decision", "Override Action"])
                for row in range(self.table.rowCount()):
                    writer.writerow([
                        self.table.item(row, col).text() if self.table.item(row, col) else ""
                        for col in range(self.table.columnCount())
                    ])
            QMessageBox.information(self, "Export Successful", f"Audit log exported to:\n{filename}")
        except Exception as e:
            QMessageBox.critical(self, "Export Failed", f"An error occurred:\n{str(e)}")

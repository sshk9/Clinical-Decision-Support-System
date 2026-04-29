from __future__ import annotations
from PyQt5.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit,
    QComboBox, QPushButton, QMessageBox, QFormLayout
)
from PyQt5.QtCore import Qt
from PyQt5.QtGui import QFont

from ..infrastructure.database import get_diseases_with_states, add_patient

ACCENT = "#2ABFBF"
TEXT_PRIMARY = "#1B2A2F"
TEXT_MUTED = "#6B8A8A"
CARD_BG = "#FFFFFF"
DANGER = "#E05C5C"


class AddPatientDialog(QDialog):
    """Dialog for adding a new patient to the system."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Add New Patient")
        self.setMinimumWidth(500)
        self.setModal(True)
        self._diseases_data = []
        self._build()
        self._load_diseases()

    def _build(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 24, 24, 24)
        layout.setSpacing(20)

        # Title
        title = QLabel("Register New Patient")
        title.setFont(QFont("Segoe UI", 18, QFont.Bold))
        title.setStyleSheet(f"color: {TEXT_PRIMARY};")
        layout.addWidget(title)

        subtitle = QLabel("Enter patient details and initial clinical status")
        subtitle.setStyleSheet(f"color: {TEXT_MUTED};")
        layout.addWidget(subtitle)

        # Form layout
        form = QFormLayout()
        form.setSpacing(12)
        form.setLabelAlignment(Qt.AlignRight)

        # Patient ID
        self.patient_id_input = QLineEdit()
        self.patient_id_input.setPlaceholderText("e.g., P007")
        self.patient_id_input.setStyleSheet(self._input_style())
        form.addRow("Patient ID:*", self.patient_id_input)

        # First Name
        self.first_name_input = QLineEdit()
        self.first_name_input.setPlaceholderText("First name")
        self.first_name_input.setStyleSheet(self._input_style())
        form.addRow("First Name:*", self.first_name_input)

        # Last Name
        self.last_name_input = QLineEdit()
        self.last_name_input.setPlaceholderText("Last name")
        self.last_name_input.setStyleSheet(self._input_style())
        form.addRow("Last Name:*", self.last_name_input)

        # Disease dropdown
        self.disease_combo = QComboBox()
        self.disease_combo.setStyleSheet(self._combo_style())
        self.disease_combo.currentIndexChanged.connect(self._on_disease_changed)
        form.addRow("Disease:*", self.disease_combo)

        # Initial State dropdown
        self.state_combo = QComboBox()
        self.state_combo.setStyleSheet(self._combo_style())
        form.addRow("Initial State:*", self.state_combo)

        layout.addLayout(form)

        # Info note
        note = QLabel("* Required fields")
        note.setStyleSheet(f"color: {TEXT_MUTED}; font-size: 11px;")
        layout.addWidget(note)

        # Buttons
        button_layout = QHBoxLayout()
        button_layout.addStretch()

        self.cancel_btn = QPushButton("Cancel")
        self.cancel_btn.setFixedHeight(36)
        self.cancel_btn.setStyleSheet(self._button_style("#6C757D"))
        self.cancel_btn.clicked.connect(self.reject)
        button_layout.addWidget(self.cancel_btn)

        self.ok_btn = QPushButton("Add Patient")
        self.ok_btn.setFixedHeight(36)
        self.ok_btn.setStyleSheet(self._button_style(ACCENT))
        self.ok_btn.clicked.connect(self._on_accept)
        button_layout.addWidget(self.ok_btn)

        layout.addLayout(button_layout)

    def _input_style(self):
        return f"""
            QLineEdit {{
                background: {CARD_BG};
                border: 1px solid #DDE8E8;
                border-radius: 6px;
                padding: 8px 12px;
                font-size: 13px;
            }}
            QLineEdit:focus {{
                border-color: {ACCENT};
            }}
        """

    def _combo_style(self):
        return f"""
            QComboBox {{
                background: {CARD_BG};
                border: 1px solid #DDE8E8;
                border-radius: 6px;
                padding: 8px 12px;
                font-size: 13px;
            }}
            QComboBox:focus {{
                border-color: {ACCENT};
            }}
        """

    def _button_style(self, color):
        return f"""
            QPushButton {{
                background: {color};
                color: white;
                border-radius: 6px;
                font-weight: bold;
                padding: 0 20px;
            }}
            QPushButton:hover {{
                background: {color if color == "#6C757D" else "#23A8A8"};
            }}
        """

    def _load_diseases(self):
        """Load diseases and their states from database."""
        self._diseases_data = get_diseases_with_states()
        
        diseases_dict = {}
        for item in self._diseases_data:
            disease_id = item["disease_id"]
            if disease_id not in diseases_dict:
                diseases_dict[disease_id] = {
                    "name": item["disease_name"],
                    "states": [],
                    "model_id": item["model_id"]
                }
            diseases_dict[disease_id]["states"].append({
                "state_id": item["state_id"],
                "state_name": item["state_name"],
                "severity": item["severity_level"]
            })
        
        self.disease_combo.clear()
        for disease_id, data in diseases_dict.items():
            self.disease_combo.addItem(data["name"], {
                "disease_id": disease_id,
                "states": data["states"],
                "model_id": data["model_id"]
            })

    def _on_disease_changed(self):
        """Update state dropdown based on selected disease."""
        current_data = self.disease_combo.currentData()
        if current_data:
            states = current_data["states"]
            self.state_combo.clear()
            for state in states:
                self.state_combo.addItem(state["state_name"], state)
        else:
            self.state_combo.clear()

    def _on_accept(self):
        """Validate input and add patient."""
        patient_id = self.patient_id_input.text().strip()
        first_name = self.first_name_input.text().strip()
        last_name = self.last_name_input.text().strip()
        
        if not patient_id:
            QMessageBox.warning(self, "Validation Error", "Patient ID is required.")
            return
        if not first_name:
            QMessageBox.warning(self, "Validation Error", "First name is required.")
            return
        if not last_name:
            QMessageBox.warning(self, "Validation Error", "Last name is required.")
            return
        disease_data = self.disease_combo.currentData()
        if not disease_data:
            QMessageBox.warning(self, "Validation Error", "Please select a disease.")
            return
        
        state_data = self.state_combo.currentData()
        if not state_data:
            QMessageBox.warning(self, "Validation Error", "Please select an initial state.")
            return
        
        success = add_patient(
            patient_id=patient_id,
            first_name=first_name,
            last_name=last_name,
            disease_id=disease_data["disease_id"],
            state_id=state_data["state_id"],
            model_id=disease_data["model_id"]
        )
        
        if success:
            QMessageBox.information(self, "Success", f"Patient {patient_id} added successfully.")
            self.accept()
        else:
            QMessageBox.warning(self, "Error", f"Patient ID {patient_id} already exists.")

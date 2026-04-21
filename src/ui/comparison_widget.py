from __future__ import annotations
from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QComboBox,
    QTableWidget, QTableWidgetItem, QHeaderView, QFrame, QPushButton, QMessageBox
)
from PyQt5.QtCore import Qt
from PyQt5.QtGui import QFont, QColor

import matplotlib
matplotlib.use('Qt5Agg')
from matplotlib.backends.backend_qt5agg import FigureCanvasQTAgg
from matplotlib.figure import Figure

from ..infrastructure.database import (
    get_all_patients,
    get_actions_for_patient
)
from ..analytics.analytics import compare_actions


SIDEBAR_BG = "#1B2A2F"
CONTENT_BG = "#F0F7F7"
ACCENT = "#2ABFBF"
CARD_BG = "#FFFFFF"
TEXT_PRIMARY = "#1B2A2F"
TEXT_MUTED = "#6B8A8A"


class ComparisonWidget(QWidget):
    """
    Patient comparison widget for analytics view.
    Allows comparing two patients side-by-side.
    """
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.patients_data = []
        self.patient_disease_map = {}  # Store disease per patient
        self._first_compare = True
        self._build()
        self._load_patients()
    
    def _build(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(32, 32, 32, 32)
        layout.setSpacing(20)
        
        # Header
        title = QLabel("Patient Comparison & Analytics")
        title.setFont(QFont("Inter", 20, QFont.Bold))
        title.setStyleSheet(f"color: {TEXT_PRIMARY};")
        layout.addWidget(title)
        
        # Selection row
        selection_layout = QHBoxLayout()
        selection_layout.setSpacing(20)
        
        self.patient_a_combo = QComboBox()
        self.patient_a_combo.setMinimumWidth(200)
        self.patient_a_combo.setStyleSheet(self._combo_style())
        
        self.patient_b_combo = QComboBox()
        self.patient_b_combo.setMinimumWidth(200)
        self.patient_b_combo.setStyleSheet(self._combo_style())
        
        compare_btn = QPushButton("Compare")
        compare_btn.setStyleSheet(self._button_style())
        compare_btn.clicked.connect(self._on_compare)
        
        selection_layout.addWidget(QLabel("Patient A:"))
        selection_layout.addWidget(self.patient_a_combo)
        selection_layout.addWidget(QLabel("Patient B:"))
        selection_layout.addWidget(self.patient_b_combo)
        selection_layout.addWidget(compare_btn)
        selection_layout.addStretch()
        
        layout.addLayout(selection_layout)
        
        # Main content area - VERTICAL layout (tables on top, insights below)
        self.content_layout = QVBoxLayout()
        layout.addLayout(self.content_layout, stretch=1)
        
        # Initial placeholder
        self.placeholder = QLabel("Select two patients and click 'Compare' to see side-by-side analysis")
        self.placeholder.setAlignment(Qt.AlignCenter)
        self.placeholder.setStyleSheet(f"color: {TEXT_MUTED}; font-size: 14px;")
        self.content_layout.addWidget(self.placeholder)
    
    def _combo_style(self):
        return f"""
            QComboBox {{
                background: {CARD_BG};
                border: 1px solid #DDE8E8;
                border-radius: 6px;
                padding: 8px 12px;
                font-size: 13px;
                color: {TEXT_PRIMARY};
            }}
            QComboBox:hover {{
                border-color: {ACCENT};
            }}
        """
    
    def _button_style(self):
        return f"""
            QPushButton {{
                background: {ACCENT};
                color: white;
                border: none;
                border-radius: 6px;
                padding: 8px 20px;
                font-size: 13px;
                font-weight: bold;
            }}
            QPushButton:hover {{
                background: #23A8A8;
            }}
        """
    
    def _load_patients(self):
        """Load patients from database"""
        self.patients_data = get_all_patients()
        
        for pid, name, state, disease in self.patients_data:
            display = f"{name} ({pid}) - {disease} - {state}"
            self.patient_a_combo.addItem(display, pid)
            self.patient_b_combo.addItem(display, pid)
            self.patient_disease_map[pid] = disease
        
        # Select defaults
        if len(self.patients_data) >= 2:
            self.patient_a_combo.setCurrentIndex(0)
            self.patient_b_combo.setCurrentIndex(1)
    
    def _get_patient_disease(self, patient_id: str) -> str:
        """Get disease name for a patient"""
        return self.patient_disease_map.get(patient_id, "")
    
    def _on_compare(self):
        """Compare selected patients with validation"""
        patient_a_id = self.patient_a_combo.currentData()
        patient_b_id = self.patient_b_combo.currentData()
        
        if not patient_a_id or not patient_b_id:
            return
        
        # VALIDATION: Same disease check
        disease_a = self._get_patient_disease(patient_a_id)
        disease_b = self._get_patient_disease(patient_b_id)
        
        if disease_a != disease_b:
            QMessageBox.warning(
                self,
                "Incompatible Comparison",
                f"Cannot compare patients with different diseases.\n\n"
                f"Patient A: {disease_a}\n"
                f"Patient B: {disease_b}\n\n"
                f"Please select two patients with the same disease for meaningful comparison."
            )
            return
        
        # Clear previous content (including placeholder)
        self._clear_content()
        
        # Get actions for both patients
        actions_a = get_actions_for_patient(patient_a_id)
        actions_b = get_actions_for_patient(patient_b_id)
        
        # TABLES ROW (horizontal)
        tables_row = QWidget()
        tables_layout = QHBoxLayout(tables_row)
        tables_layout.setSpacing(20)
        
        # Patient A table
        table_a = self._create_comparison_table(actions_a, f"Patient A: {self._get_patient_name(patient_a_id)}")
        # Patient B table
        table_b = self._create_comparison_table(actions_b, f"Patient B: {self._get_patient_name(patient_b_id)}")
        
        tables_layout.addWidget(table_a)
        tables_layout.addWidget(table_b)
        
        self.content_layout.addWidget(tables_row)
        
        # INSIGHTS PANEL (below)
        insights = self._create_insights_panel(patient_a_id, patient_b_id, disease_a)
        self.content_layout.addWidget(insights)
    
    def _get_patient_name(self, patient_id: str) -> str:
        """Get patient display name"""
        for pid, name, state, disease in self.patients_data:
            if pid == patient_id:
                return name
        return patient_id
    
    def _create_comparison_table(self, actions_data, title):
        """Create a table widget for action comparison"""
        table_widget = QWidget()
        layout = QVBoxLayout(table_widget)
        layout.setSpacing(10)
        
        title_label = QLabel(title)
        title_label.setFont(QFont("Inter", 14, QFont.Bold))
        title_label.setStyleSheet(f"color: {ACCENT};")
        layout.addWidget(title_label)
        
        table = QTableWidget()
        table.setColumnCount(4)
        table.setHorizontalHeaderLabels(["Action", "Benefit", "Risk", "Net Utility"])
        table.horizontalHeader().setSectionResizeMode(0, QHeaderView.Stretch)
        table.setEditTriggers(QTableWidget.NoEditTriggers)
        table.setAlternatingRowColors(True)
        table.setStyleSheet(f"""
            QTableWidget {{
                background: {CARD_BG};
                border: 1px solid #DDE8E8;
                border-radius: 8px;
                font-size: 12px;
            }}
            QHeaderView::section {{
                background: #EEF3F3;
                color: {TEXT_MUTED};
                padding: 8px;
                font-weight: bold;
            }}
        """)
        
        # Process data
        comparison_data = []
        for name, desc, benefit, risk, cost, improve, worsen, delta in actions_data:
            net = benefit - risk - cost
            comparison_data.append((name, benefit, risk, net))
        
        # Sort by net utility
        comparison_data.sort(key=lambda x: x[3], reverse=True)
        
        table.setRowCount(len(comparison_data))
        for row, (name, benefit, risk, net) in enumerate(comparison_data):
            table.setItem(row, 0, QTableWidgetItem(name))
            table.setItem(row, 1, QTableWidgetItem(f"{benefit:.2f}"))
            table.setItem(row, 2, QTableWidgetItem(f"{risk:.2f}"))
            net_item = QTableWidgetItem(f"{net:.2f}")
            if row == 0:
                net_item.setForeground(QColor(ACCENT))
                font = QFont("Inter", 12, QFont.Bold)
                net_item.setFont(font)
            table.setItem(row, 3, net_item)
        
        table.setMinimumHeight(250)
        layout.addWidget(table)
        
        return table_widget
    
    def _create_insights_panel(self, patient_a_id, patient_b_id, disease_name):
        """Create insights panel with analytics for the specific disease"""
        panel = QFrame()
        panel.setStyleSheet(f"""
            QFrame {{
                background: {CARD_BG};
                border: 1px solid #DDE8E8;
                border-radius: 8px;
                padding: 15px;
            }}
        """)
        
        layout = QVBoxLayout(panel)
        layout.setSpacing(15)
        
        # Insights title with disease context
        insights_title = QLabel(f"Clinical Insights - {disease_name}")
        insights_title.setFont(QFont("Inter", 16, QFont.Bold))
        insights_title.setStyleSheet(f"color: {TEXT_PRIMARY};")
        layout.addWidget(insights_title)
        
        # Get disease ID for analytics
        disease_id = self._get_disease_id_by_name(disease_name)
        if disease_id:
            actions_global = get_actions_for_patient(patient_a_id)
            comparisons = compare_actions(actions_global)
            
            # Top actions for this disease
            top_actions_text = "Most Effective Strategies:\n"
            for i, action in enumerate(comparisons[:3], 1):
                top_actions_text += f"  {i}. {action.action_name} (net: {action.net_utility:.2f})\n"
            
            top_label = QLabel(top_actions_text)
            top_label.setStyleSheet(f"color: {TEXT_PRIMARY}; font-size: 12px;")
            top_label.setWordWrap(True)
            layout.addWidget(top_label)
            
            # Success rate for this specific disease
        summary_text = (
            f"Population Health:\n"
            f"  Detailed state-distribution analytics are not yet connected to this view.\n"
            f"  Current comparison focuses on action ranking and patient-specific recommendations."
        )

        summary_label = QLabel(summary_text)
        summary_label.setStyleSheet(f"color: {TEXT_PRIMARY}; font-size: 12px;")
        summary_label.setWordWrap(True)
        layout.addWidget(summary_label) 
        
        # Recommendation based on comparison
        rec_label = QLabel("Recommendation:")
        rec_label.setFont(QFont("Inter", 12, QFont.Bold))
        rec_label.setStyleSheet(f"color: {ACCENT};")
        layout.addWidget(rec_label)
        
        rec_text = QLabel("Consider the highest-ranked action for each patient based on their current clinical state.")
        rec_text.setStyleSheet(f"color: {TEXT_MUTED}; font-size: 12px;")
        rec_text.setWordWrap(True)
        layout.addWidget(rec_text)
        
        return panel
    
    def _get_disease_id_by_name(self, disease_name: str) -> int:
        """Get disease ID by name"""
        from ..infrastructure.database import get_connection
        with get_connection() as conn:
            cursor = conn.execute("SELECT id FROM disease WHERE name = ?", (disease_name,))
            result = cursor.fetchone()
            if result:
                return result[0]
        return None
    
    def _get_disease_id_for_patient(self, patient_id: str) -> int:
        """Get disease ID for a patient"""
        from ..infrastructure.database import get_connection
        with get_connection() as conn:
            cursor = conn.execute("SELECT disease_id FROM patient_status WHERE patient_id = ?", (patient_id,))
            result = cursor.fetchone()
            if result:
                return result[0]
        return None
    
    def _clear_content(self):
        """Clear the content layout completely"""
        while self.content_layout.count():
            item = self.content_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
        self._first_compare = False
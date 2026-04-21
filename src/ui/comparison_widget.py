from __future__ import annotations
from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QComboBox,
    QTableWidget, QTableWidgetItem, QHeaderView, QFrame, QPushButton,
    QMessageBox, QScrollArea
)
from PyQt5.QtCore import Qt
from PyQt5.QtGui import QFont, QColor

import matplotlib
matplotlib.use('Qt5Agg')
from matplotlib.backends.backend_qt5agg import FigureCanvasQTAgg
from matplotlib.figure import Figure

from ..infrastructure.database import (
    get_all_patients, get_actions_for_patient,
    get_action_utility_comparison, get_state_distribution
)
from ..analytics.analytics import compare_actions, state_success_rate


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
        self.patient_disease_map = {}
        self._first_compare = True
        self._build()
        self._load_patients()

    def _build(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(32, 32, 32, 32)
        layout.setSpacing(20)

        # Header
        title = QLabel("Patient Comparison & Analytics")
        title.setFont(QFont("Segoe UI", 20, QFont.Bold))
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
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setStyleSheet("QScrollArea { border: none; background: transparent; }")

        scroll_content = QWidget()
        self.content_layout = QVBoxLayout(scroll_content)
        self.content_layout.setSpacing(20)
        scroll.setWidget(scroll_content)

        layout.addWidget(scroll, stretch=1)

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

        if len(self.patients_data) >= 2:
            self.patient_a_combo.setCurrentIndex(0)
            self.patient_b_combo.setCurrentIndex(1)

    def _get_patient_disease(self, patient_id: str) -> str:
        return self.patient_disease_map.get(patient_id, "")

    def _get_disease_id_by_name(self, disease_name: str) -> int:
        from ..infrastructure.database import get_connection
        with get_connection() as conn:
            cursor = conn.execute("SELECT id FROM disease WHERE name = ?", (disease_name,))
            result = cursor.fetchone()
            if result:
                return result[0]
        return None

    def _get_patient_name(self, patient_id: str) -> str:
        for pid, name, state, disease in self.patients_data:
            if pid == patient_id:
                return name
        return patient_id

    def _create_effectiveness_chart(self, disease_name: str) -> QWidget:
        """
        Create a horizontal bar chart showing average net utility per action for the given disease.
        """
        disease_id = self._get_disease_id_by_name(disease_name)
        if not disease_id:
            placeholder = QLabel(f"No data available for {disease_name}")
            placeholder.setAlignment(Qt.AlignCenter)
            placeholder.setStyleSheet(f"color: {TEXT_MUTED};")
            return placeholder

        actions_data = get_action_utility_comparison(disease_id)
        comparisons = compare_actions(actions_data)

        if not comparisons:
            placeholder = QLabel(f"No action data available for {disease_name}")
            placeholder.setAlignment(Qt.AlignCenter)
            placeholder.setStyleSheet(f"color: {TEXT_MUTED};")
            return placeholder

        action_names = [c.action_name for c in comparisons]
        net_utilities = [c.net_utility for c in comparisons]

        fig = Figure(figsize=(8, 4), dpi=100)
        canvas = FigureCanvasQTAgg(fig)
        ax = fig.add_subplot(111)

        bars = ax.barh(action_names, net_utilities, color=TEXT_MUTED, height=0.6)

        if bars:
            bars[0].set_color(ACCENT)

        ax.set_xlabel("Net Utility (Benefit - Risk - Cost)", fontsize=11)
        ax.set_title(f"Action Effectiveness Ranking – {disease_name}", fontsize=13, fontweight='bold')
        ax.axvline(x=0, color='gray', linestyle='--', linewidth=0.8)
        ax.set_facecolor(CARD_BG)
        fig.tight_layout(pad=2.0)

        container = QFrame()
        container.setStyleSheet(f"""
            QFrame {{
                background: {CARD_BG};
                border: 1px solid #DDE8E8;
                border-radius: 8px;
                padding: 10px;
            }}
        """)
        container.setMinimumHeight(300)
        layout = QVBoxLayout(container)
        layout.addWidget(canvas)

        return container

    def _on_compare(self):
        patient_a_id = self.patient_a_combo.currentData()
        patient_b_id = self.patient_b_combo.currentData()

        if not patient_a_id or not patient_b_id:
            return

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

        self._clear_content()

        actions_a = get_actions_for_patient(patient_a_id)
        actions_b = get_actions_for_patient(patient_b_id)

        tables_row = QWidget()
        tables_row.setMinimumHeight(320)
        tables_layout = QHBoxLayout(tables_row)
        tables_layout.setSpacing(20)

        table_a = self._create_comparison_table(actions_a, f"Patient A: {self._get_patient_name(patient_a_id)}")
        table_b = self._create_comparison_table(actions_b, f"Patient B: {self._get_patient_name(patient_b_id)}")

        tables_layout.addWidget(table_a)
        tables_layout.addWidget(table_b)

        self.content_layout.addWidget(tables_row)

        chart = self._create_effectiveness_chart(disease_a)
        self.content_layout.addWidget(chart)

        insights = self._create_insights_panel(patient_a_id, patient_b_id, disease_a)
        insights.setMinimumHeight(200)
        self.content_layout.addWidget(insights)

    def _create_comparison_table(self, actions_data, title):
        """Create a table widget for action comparison"""
        table_widget = QWidget()
        layout = QVBoxLayout(table_widget)
        layout.setSpacing(10)

        title_label = QLabel(title)
        title_label.setFont(QFont("Segoe UI", 14, QFont.Bold))
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

        comparison_data = []
        for name, desc, benefit, risk, cost, improve, worsen, delta in actions_data:
            net = benefit - risk - cost
            comparison_data.append((name, benefit, risk, net))

        comparison_data.sort(key=lambda x: x[3], reverse=True)

        table.setRowCount(len(comparison_data))
        for row, (name, benefit, risk, net) in enumerate(comparison_data):
            table.setItem(row, 0, QTableWidgetItem(name))
            table.setItem(row, 1, QTableWidgetItem(f"{benefit:.2f}"))
            table.setItem(row, 2, QTableWidgetItem(f"{risk:.2f}"))
            net_item = QTableWidgetItem(f"{net:.2f}")
            if row == 0:
                net_item.setForeground(QColor(ACCENT))
                font = QFont("Segoe UI", 12, QFont.Bold)
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

        insights_title = QLabel(f"Clinical Insights – {disease_name}")
        insights_title.setFont(QFont("Segoe UI", 16, QFont.Bold))
        insights_title.setStyleSheet(f"color: {TEXT_PRIMARY};")
        layout.addWidget(insights_title)

        disease_id = self._get_disease_id_by_name(disease_name)
        if disease_id:
            actions_global = get_action_utility_comparison(disease_id)
            comparisons = compare_actions(actions_global)
            distribution = get_state_distribution()
            success_rates = state_success_rate(distribution)

            top_actions_text = "Most Effective Strategies:\n"
            for i, action in enumerate(comparisons[:3], 1):
                top_actions_text += f"  {i}. {action.action_name} (net: {action.net_utility:.2f})\n"

            top_label = QLabel(top_actions_text)
            top_label.setStyleSheet(f"color: {TEXT_PRIMARY}; font-size: 12px;")
            top_label.setWordWrap(True)
            layout.addWidget(top_label)

            disease_success = success_rates["by_disease"].get(disease_name, {})
            success_text = f"Population Health:\n"
            success_text += f"  {disease_name} success rate: {disease_success.get('success_rate', 0)}%"
            success_text += f" ({disease_success.get('success_count', 0)}/{disease_success.get('total_patients', 0)} patients)"

            success_label = QLabel(success_text)
            success_label.setStyleSheet(f"color: {TEXT_PRIMARY}; font-size: 12px;")
            success_label.setWordWrap(True)
            layout.addWidget(success_label)

        rec_label = QLabel("Recommendation:")
        rec_label.setFont(QFont("Segoe UI", 12, QFont.Bold))
        rec_label.setStyleSheet(f"color: {ACCENT};")
        layout.addWidget(rec_label)

        rec_text = QLabel("Consider the highest-ranked action for each patient based on their current clinical state.")
        rec_text.setStyleSheet(f"color: {TEXT_MUTED}; font-size: 12px;")
        rec_text.setWordWrap(True)
        layout.addWidget(rec_text)

        return panel

    def _clear_content(self):
        """Clear the content layout completely"""
        while self.content_layout.count():
            item = self.content_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
        self._first_compare = False
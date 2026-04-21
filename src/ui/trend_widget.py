from __future__ import annotations
from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QFrame,
    QTableWidget, QTableWidgetItem, QHeaderView, QComboBox, QScrollArea
)
from PyQt5.QtCore import Qt
from PyQt5.QtGui import QFont, QColor

import matplotlib
matplotlib.use('Qt5Agg')
from matplotlib.backends.backend_qt5agg import FigureCanvasQTAgg
from matplotlib.figure import Figure

from ..infrastructure.database import get_state_distribution, get_action_utility_comparison, get_connection
from ..analytics.analytics import compare_actions


SIDEBAR_BG = "#1B2A2F"
CONTENT_BG = "#F0F7F7"
ACCENT = "#2ABFBF"
CARD_BG = "#FFFFFF"
TEXT_PRIMARY = "#1B2A2F"
TEXT_MUTED = "#6B8A8A"
DANGER = "#E05C5C"
WARNING = "#FF9800"
SUCCESS = "#4CAF82"


class TrendWidget(QWidget):
    """
    Population health trends and analytics.
    Uses existing data to show severity distribution, action effectiveness, and population health metrics.
    No schema changes required.
    """

    def __init__(self, parent=None):
        super().__init__(parent)
        self._build()
        self._load_data()

    def _build(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(32, 32, 32, 32)
        layout.setSpacing(20)

        # Header
        title = QLabel("Population Health Trends")
        title.setFont(QFont("Inter", 20, QFont.Bold))
        title.setStyleSheet(f"color: {TEXT_PRIMARY};")
        layout.addWidget(title)

        subtitle = QLabel("Aggregate analytics across all patients. Data reflects current population state.")
        subtitle.setFont(QFont("Inter", 11))
        subtitle.setStyleSheet(f"color: {TEXT_MUTED};")
        layout.addWidget(subtitle)

        # Disease filter
        filter_layout = QHBoxLayout()
        filter_layout.addWidget(QLabel("Filter by Disease:"))
        self.disease_filter = QComboBox()
        self.disease_filter.addItem("All Diseases")
        self.disease_filter.currentTextChanged.connect(self._on_filter_changed)
        filter_layout.addWidget(self.disease_filter)
        filter_layout.addStretch()
        layout.addLayout(filter_layout)

        # Main content area (scrollable)
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setStyleSheet("QScrollArea { border: none; background: transparent; }")

        scroll_content = QWidget()
        self.content_layout = QVBoxLayout(scroll_content)
        self.content_layout.setSpacing(20)
        scroll.setWidget(scroll_content)

        layout.addWidget(scroll, stretch=1)

    def _load_data(self):
        """Load available diseases for filter"""
        with get_connection() as conn:
            cursor = conn.execute("SELECT DISTINCT name FROM disease ORDER BY name")
            for row in cursor.fetchall():
                self.disease_filter.addItem(row[0])
        
        self._refresh()

    def _on_filter_changed(self):
        self._refresh()

    def _refresh(self):
        """Refresh all charts and tables based on selected filter"""
        # Clear existing content
        while self.content_layout.count():
            item = self.content_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

        selected_disease = self.disease_filter.currentText()
        
        # Get distribution data
        distribution = get_state_distribution()
        
        # Filter by disease if needed
        if selected_disease != "All Diseases":
            distribution = [d for d in distribution if d["disease_name"] == selected_disease]
        
        # Row 1: Severity Distribution Chart and Key Metrics (wrapped in a QWidget)
        row1_widget = QWidget()
        row1_layout = QHBoxLayout(row1_widget)
        row1_layout.setSpacing(20)
        
        # Severity distribution chart
        severity_chart = self._create_severity_chart(distribution, selected_disease)
        row1_layout.addWidget(severity_chart, stretch=2)
        
        # Key metrics panel
        metrics_panel = self._create_metrics_panel(distribution, selected_disease)
        row1_layout.addWidget(metrics_panel, stretch=1)
        
        self.content_layout.addWidget(row1_widget)
        
        # Row 2: Action Effectiveness Chart (if disease selected)
        if selected_disease != "All Diseases":
            action_chart = self._create_action_effectiveness_chart(selected_disease)
            if action_chart:
                self.content_layout.addWidget(action_chart)
        
        # Row 3: State Distribution Table
        state_table = self._create_state_table(distribution, selected_disease)
        self.content_layout.addWidget(state_table)

    def _create_severity_chart(self, distribution, disease_name):
        """Create a pie chart of severity distribution"""
        # Count patients by severity level
        severity_counts = {1: 0, 2: 0, 3: 0, 4: 0, 5: 0}
        severity_labels = {
            1: "Normal (Level 1)",
            2: "Mild (Level 2)",
            3: "Moderate (Level 3)",
            4: "Severe (Level 4)",
            5: "Critical (Level 5)"
        }
        
        for item in distribution:
            severity = item["severity_level"]
            severity_counts[severity] = severity_counts.get(severity, 0) + item["patient_count"]
        
        # Filter out zero counts
        labels = []
        sizes = []
        colors = []
        
        color_map = {
            1: SUCCESS,
            2: "#8BC34A",
            3: WARNING,
            4: DANGER,
            5: "#7B1FA2"
        }
        
        for severity in [1, 2, 3, 4, 5]:
            if severity_counts[severity] > 0:
                labels.append(severity_labels[severity])
                sizes.append(severity_counts[severity])
                colors.append(color_map[severity])
        
        # Create figure
        fig = Figure(figsize=(5, 4), dpi=100)
        canvas = FigureCanvasQTAgg(fig)
        ax = fig.add_subplot(111)
        
        if sizes:
            wedges, texts, autotexts = ax.pie(sizes, labels=labels, colors=colors,
                                              autopct='%1.1f%%', startangle=90)
            for text in texts:
                text.set_fontsize(9)
            for autotext in autotexts:
                autotext.set_color('white')
                autotext.set_fontweight('bold')
        else:
            ax.text(0.5, 0.5, 'No data available', ha='center', va='center')
        
        ax.set_title(f"Severity Distribution - {disease_name if disease_name != 'All Diseases' else 'All Patients'}", 
                     fontsize=12, fontweight='bold')
        fig.tight_layout()
        
        container = QFrame()
        container.setStyleSheet(f"""
            QFrame {{
                background: {CARD_BG};
                border: 1px solid #DDE8E8;
                border-radius: 8px;
                padding: 10px;
            }}
        """)
        container_layout = QVBoxLayout(container)
        container_layout.addWidget(canvas)
        
        return container

    def _create_metrics_panel(self, distribution, disease_name):
        """Create a panel with key population health metrics"""
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
        
        # Title
        title = QLabel("Key Metrics")
        title.setFont(QFont("Inter", 14, QFont.Bold))
        title.setStyleSheet(f"color: {TEXT_PRIMARY};")
        layout.addWidget(title)
        
        # Calculate metrics
        total_patients = sum(item["patient_count"] for item in distribution)
        
        # Success rate (severity <= 2)
        success_count = sum(item["patient_count"] for item in distribution if item["severity_level"] <= 2)
        success_rate = (success_count / total_patients * 100) if total_patients > 0 else 0
        
        # Critical patients (severity >= 4)
        critical_count = sum(item["patient_count"] for item in distribution if item["severity_level"] >= 4)
        critical_rate = (critical_count / total_patients * 100) if total_patients > 0 else 0
        
        # Average severity
        total_severity = sum(item["severity_level"] * item["patient_count"] for item in distribution)
        avg_severity = total_severity / total_patients if total_patients > 0 else 0
        
        # Display metrics
        metrics = [
            ("Total Patients", str(total_patients), TEXT_PRIMARY),
            ("Success Rate", f"{success_rate:.1f}%", SUCCESS if success_rate >= 70 else WARNING),
            ("Critical Cases", f"{critical_count} ({critical_rate:.1f}%)", DANGER if critical_count > 0 else TEXT_MUTED),
            ("Avg Severity", f"{avg_severity:.1f}/5", self._get_severity_color(avg_severity))
        ]
        
        for label, value, color in metrics:
            row = QHBoxLayout()
            row.addWidget(QLabel(label))
            row.addStretch()
            value_label = QLabel(value)
            value_label.setStyleSheet(f"color: {color}; font-weight: bold; font-size: 14px;")
            row.addWidget(value_label)
            layout.addLayout(row)
        
        # Health indicator
        layout.addSpacing(10)
        health_status = self._get_health_status(success_rate, critical_rate)
        status_label = QLabel(f"Population Health: {health_status}")
        status_label.setAlignment(Qt.AlignCenter)
        status_label.setStyleSheet(f"""
            background-color: {self._get_status_color(success_rate)};
            color: white;
            padding: 8px;
            border-radius: 5px;
            font-weight: bold;
        """)
        layout.addWidget(status_label)
        
        return panel

    def _create_action_effectiveness_chart(self, disease_name):
        """Create a bar chart of action effectiveness for the selected disease"""
        with get_connection() as conn:
            cursor = conn.execute("SELECT id FROM disease WHERE name = ?", (disease_name,))
            result = cursor.fetchone()
            if not result:
                return None
            disease_id = result[0]
        
        actions_data = get_action_utility_comparison(disease_id)
        comparisons = compare_actions(actions_data)
        
        if not comparisons:
            return None
        
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
        container_layout = QVBoxLayout(container)
        container_layout.addWidget(canvas)
        
        return container

    def _create_state_table(self, distribution, disease_name):
        """Create a table showing state distribution by disease"""
        # Group by disease
        disease_groups = {}
        for item in distribution:
            disease = item["disease_name"]
            if disease not in disease_groups:
                disease_groups[disease] = []
            disease_groups[disease].append(item)
        
        # Filter by selected disease
        if disease_name != "All Diseases":
            disease_groups = {disease_name: disease_groups.get(disease_name, [])}
        
        table_widget = QWidget()
        layout = QVBoxLayout(table_widget)
        layout.setSpacing(10)
        
        title = QLabel("State Distribution by Disease")
        title.setFont(QFont("Inter", 14, QFont.Bold))
        title.setStyleSheet(f"color: {TEXT_PRIMARY};")
        layout.addWidget(title)
        
        table = QTableWidget()
        table.setColumnCount(4)
        table.setHorizontalHeaderLabels(["Disease", "State", "Severity", "Patient Count"])
        table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeToContents)
        table.horizontalHeader().setSectionResizeMode(1, QHeaderView.Stretch)
        table.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeToContents)
        table.horizontalHeader().setSectionResizeMode(3, QHeaderView.ResizeToContents)
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
        
        row_count = sum(len(items) for items in disease_groups.values())
        table.setRowCount(row_count)
        
        row = 0
        for disease, items in disease_groups.items():
            for item in items:
                table.setItem(row, 0, QTableWidgetItem(disease))
                table.setItem(row, 1, QTableWidgetItem(item["state_name"]))
                
                severity_item = QTableWidgetItem(str(item["severity_level"]))
                severity_item.setBackground(QColor(self._get_severity_color(item["severity_level"])))
                severity_item.setForeground(QColor("white"))
                table.setItem(row, 2, severity_item)
                
                table.setItem(row, 3, QTableWidgetItem(str(item["patient_count"])))
                row += 1
        
        table.setMinimumHeight(200)
        layout.addWidget(table)
        
        return table_widget

    def _get_severity_color(self, severity):
        """Get color for severity level"""
        if severity <= 2:
            return SUCCESS
        elif severity == 3:
            return WARNING
        else:
            return DANGER

    def _get_health_status(self, success_rate, critical_rate):
        """Get health status description"""
        if critical_rate > 20:
            return "Critical - Immediate Attention Required"
        elif success_rate < 50:
            return "Poor - High Risk Population"
        elif success_rate < 70:
            return "Moderate - Improvement Needed"
        elif success_rate < 85:
            return "Good - Stable Population"
        else:
            return "Excellent - Healthy Population"

    def _get_status_color(self, success_rate):
        """Get color for health status"""
        if success_rate < 50:
            return DANGER
        elif success_rate < 70:
            return WARNING
        elif success_rate < 85:
            return "#FFC107"
        else:
            return SUCCESS
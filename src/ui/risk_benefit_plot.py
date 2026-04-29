from __future__ import annotations
from PyQt5.QtWidgets import QWidget, QVBoxLayout, QHBoxLayout, QLabel, QFrame, QGridLayout
from PyQt5.QtCore import Qt
from PyQt5.QtGui import QFont
import matplotlib
matplotlib.use('Qt5Agg')
from matplotlib.backends.backend_qt5agg import FigureCanvasQTAgg
from matplotlib.figure import Figure
import matplotlib.cm as cm
import matplotlib.colors as mcolors

from ..infrastructure.database import get_benefit_risk_for_patient

# colour palette
TEXT_PRIMARY = "#1B2A2F"
TEXT_MUTED = "#6B8A8A"
CARD_BG = "#FFFFFF"
DIVIDER = "#EEF3F3"

class RiskBenefitPlot(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.current_patient_id = None
        self._build()
        self.setVisible(False)

    def _build(self):
        # 1. Base Layout
        base_layout = QVBoxLayout(self)
        base_layout.setContentsMargins(0, 0, 0, 0)
        base_layout.setSpacing(10)

        # 2. Header
        self.title_label = QLabel("Risk‑Benefit Landscape")
        self.title_label.setFont(QFont("Segoe UI", 14, QFont.Bold))
        self.title_label.setStyleSheet(f"color: {TEXT_PRIMARY}; margin-bottom: 2px;")
        base_layout.addWidget(self.title_label)

        # 3. The Card Container (The Box)
        self.card_frame = QFrame()
        self.card_frame.setObjectName("PlotCard")
        self.card_frame.setStyleSheet(f"""
            QFrame#PlotCard {{
                background-color: {CARD_BG};
                border: 1px solid {DIVIDER};
                border-radius: 12px;
            }}
            QLabel {{ background: transparent; border: none; }}
        """)
        
        self.card_layout = QVBoxLayout(self.card_frame)
        self.card_layout.setContentsMargins(24, 24, 24, 24)
        self.card_layout.setSpacing(0)

        # Matplotlib Canvas
        self.figure = Figure(figsize=(6, 3), dpi=100, facecolor='none')
        self.canvas = FigureCanvasQTAgg(self.figure)
        self.canvas.setMinimumHeight(300)
        self.card_layout.addWidget(self.canvas)

        # Custom Legend Area
        self.legend_container = QWidget()
        self.legend_layout = QGridLayout(self.legend_container)
        self.legend_layout.setContentsMargins(0, 20, 0, 10)
        self.legend_layout.setHorizontalSpacing(30)
        self.legend_layout.setVerticalSpacing(12)
        self.card_layout.addWidget(self.legend_container)


        # Add the card to the base layout
        base_layout.addWidget(self.card_frame)

    def update_for_patient(self, patient_id: str):
        self.current_patient_id = patient_id
        data = get_benefit_risk_for_patient(patient_id)
        
        if not data:
            self.setVisible(False)
            return

        action_names, benefits, risks, net_utilities = [], [], [], []
        for row in data:
            if len(row) >= 4:
                name, benefit, risk, cost = row
                action_names.append(name)
                benefits.append(benefit)
                risks.append(risk)
                net_utilities.append(benefit - risk - cost)

        if not action_names:
            self.setVisible(False)
            return

        self.setVisible(True)
        self._draw_plot(benefits, risks, net_utilities)
        self._update_legend(action_names, net_utilities)

    def _draw_plot(self, benefits, risks, net_utilities):
        self.figure.clear()
        ax = self.figure.add_subplot(111, facecolor='#FDFDFD')

        scatter = ax.scatter(benefits, risks, c=net_utilities, cmap='RdYlGn',
                             s=150, alpha=0.9, edgecolors=TEXT_PRIMARY, linewidth=1)

        max_val = max(max(benefits), max(risks)) + 0.1
        ax.plot([0, max_val], [0, max_val], color=TEXT_MUTED, linestyle='--', alpha=0.3)
        
        ax.set_xlabel("Expected Benefit", fontsize=9, color=TEXT_PRIMARY, fontweight='bold')
        ax.set_ylabel("Complication Risk", fontsize=9, color=TEXT_PRIMARY, fontweight='bold')
        
        ax.spines['top'].set_visible(False)
        ax.spines['right'].set_visible(False)
        ax.set_xlim(0, max_val)
        ax.set_ylim(0, max_val)
        ax.grid(True, linestyle=':', alpha=0.4)

        cbar = self.figure.colorbar(scatter, ax=ax, fraction=0.03, pad=0.04)
        cbar.outline.set_visible(False)
        cbar.set_label('Net Utility', size=8, color=TEXT_MUTED)

        self.figure.tight_layout()
        self.canvas.draw()

    def _update_legend(self, names, values):
        for i in reversed(range(self.legend_layout.count())): 
            self.legend_layout.itemAt(i).widget().setParent(None)

        norm = mcolors.Normalize(vmin=min(values), vmax=max(values))
        cmap = cm.get_cmap('RdYlGn')

        for i, name in enumerate(names):
            row, col = i // 2, i % 2
            
            color_hex = mcolors.to_hex(cmap(norm(values[i])))
            icon = QLabel("●")
            icon.setStyleSheet(f"color: {color_hex}; font-size: 16px; padding-right: 5px;")
            
            label = QLabel(name)
            label.setFont(QFont("Segoe UI", 10))
            label.setStyleSheet(f"color: {TEXT_PRIMARY};")

            item_layout = QHBoxLayout()
            item_layout.addWidget(icon)
            item_layout.addWidget(label)
            item_layout.addStretch()
            
            container = QWidget()
            container.setLayout(item_layout)
            self.legend_layout.addWidget(container, row, col)

    def clear(self):
        self.setVisible(False)
        self.figure.clear()
        self.canvas.draw()

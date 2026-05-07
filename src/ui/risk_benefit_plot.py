from __future__ import annotations
from PyQt5.QtWidgets import QWidget, QVBoxLayout, QHBoxLayout, QLabel, QFrame, QGridLayout
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

        # Explanation Note
        self.note_label = QLabel(
            "Note: This plot shows the short-term net benefit for each action, calculated from benefit, risk, and cost. "
            "The ranked recommendation table above is based on the decision engine's total score, "
            "which combines immediate utility with long-term value from value iteration."
        )
        self.note_label.setWordWrap(True)
        self.note_label.setFont(QFont("Segoe UI", 9))
        self.note_label.setStyleSheet(f"""
            color: {TEXT_MUTED};
            background: transparent;
            border: none;
            margin-top: 8px;
        """)
        self.card_layout.addWidget(self.note_label)


        # Add the card to the base layout
        base_layout.addWidget(self.card_frame)

    def update_for_patient(self, patient_id: str):
        self.current_patient_id = patient_id
        data = get_benefit_risk_for_patient(patient_id)
        
        if not data:
            self.setVisible(False)
            return

        action_names, benefits, risks, short_term_net_benefits = [], [], [], []
        for row in data:
            if len(row) >= 4:
                name, benefit, risk, cost = row
                action_names.append(name)
                benefits.append(benefit)
                risks.append(risk)
                short_term_net_benefits.append(benefit - risk - cost)

        if not action_names:
            self.setVisible(False)
            return

        self.setVisible(True)
        self._draw_plot(benefits, risks, short_term_net_benefits)
        self._update_legend(action_names, short_term_net_benefits)

    def _draw_plot(self, benefits, risks, short_term_net_benefits):
        self.figure.clear()
        ax = self.figure.add_subplot(111, facecolor='#FDFDFD')

        scatter = ax.scatter(benefits, risks, c=short_term_net_benefits, cmap='RdYlGn',
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
        cbar.set_label('Short-Term Net Benefit', size=8, color=TEXT_MUTED)

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
            icon.setStyleSheet(f"color: {color_hex}; font-size: 30px; padding-right: 3px;")
            
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

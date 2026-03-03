from PySide6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QLabel,
    QLineEdit, QPushButton, QListWidget, QMessageBox
)

from decision_engine.engine import rank_actions
from database.db import init_db, save_recommendation_run


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("CDSS Prototype (Standalone)")

        init_db()

        root = QWidget()
        layout = QVBoxLayout()

        layout.addWidget(QLabel("Patient ID:"))
        self.patient_id = QLineEdit()
        self.patient_id.setPlaceholderText("e.g., 10293")
        layout.addWidget(self.patient_id)

        layout.addWidget(QLabel("Disease State (S1/S2/S3):"))
        self.state = QLineEdit()
        self.state.setPlaceholderText("e.g., S3")
        layout.addWidget(self.state)

        self.btn = QPushButton("Run Recommendation")
        self.btn.clicked.connect(self.run_reco)
        layout.addWidget(self.btn)

        layout.addWidget(QLabel("Ranked Treatment Options:"))
        self.list = QListWidget()
        layout.addWidget(self.list)

        root.setLayout(layout)
        self.setCentralWidget(root)

    def run_reco(self):
        pid = self.patient_id.text().strip()
        st = self.state.text().strip().upper()

        if not pid or not st:
            QMessageBox.warning(self, "Missing input", "Please enter Patient ID and Disease State.")
            return

        try:
            recs = rank_actions(st)
        except Exception as e:
            QMessageBox.critical(self, "Error", str(e))
            return

        self.list.clear()
        for i, r in enumerate(recs, start=1):
            self.list.addItem(f"{i}. {r['action']} — score={r['score']:.2f} (conf={r['confidence']:.2f})")

        save_recommendation_run(pid, st, recs)


def run_app():
    app = QApplication([])
    w = MainWindow()
    w.resize(520, 360)
    w.show()
    app.exec()

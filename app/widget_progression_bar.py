import os

from PySide6.QtWidgets import (
    QVBoxLayout, QLabel, QProgressBar, QDialog
)
from PySide6.QtCore import Qt, QTimer


class ProgressionBar(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Help")
        self.setGeometry(550, 275, 350, 75)

        self.setWindowFlags(Qt.Window | Qt.WindowStaysOnTopHint)
        self.setModal(True)

        layout = QVBoxLayout()

        text_label = QLabel()
        text_label.setText("Please wait. Download in progress")
        text_label.setAlignment(Qt.AlignLeft | Qt.AlignTop)
        layout.addWidget(text_label)

        self.progress_bar = QProgressBar()
        self.progress_bar.setValue(0)
        layout.addWidget(self.progress_bar)

        self.setLayout(layout)

    def set_progress(self, value):
        if value < 100:
            self.progress_bar.setValue(int(round(value)))
        else:
            self.close()


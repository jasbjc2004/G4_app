import os

from PySide6.QtWidgets import (
    QVBoxLayout, QLabel, QDialog
)
from PySide6.QtGui import QPixmap
from PySide6.QtCore import Qt


class Help(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Help")
        self.setGeometry(400, 200, 400, 400)

        self.setWindowFlags(Qt.Window | Qt.WindowStaysOnTopHint)
        self.setModal(True)

        layout = QVBoxLayout()

        image_label = QLabel()
        file_directory = (os.path.dirname(os.path.abspath(__file__)))
        image_path = (os.path.join(file_directory, "NEEDED/PICTURES/help.png"))
        pixmap = QPixmap(image_path)
        scaled_pixmap = pixmap.scaled(500, 500, Qt.KeepAspectRatio, Qt.SmoothTransformation)
        image_label.setPixmap(scaled_pixmap)
        layout.addWidget(image_label)

        text_label = QLabel()
        text_label.setText(
            "Introduction: \n "
            " The front of the source has to point to the child. If done correctly, \n"
            " the x-axis on the source face to the child. \n"
            "For the data on the plot: \n"
            " The x-axis lays horizontal on the table. \n"
            " The y-axis is pointing to the source on the table.\n"
            " The z-axis is pointing to the roof.\n"
            " The center of this axis is in the middle of both hands")
        text_label.setWordWrap(True)  # Enable text wrapping
        text_label.setAlignment(Qt.AlignLeft | Qt.AlignTop)
        layout.addWidget(text_label)

        self.setLayout(layout)

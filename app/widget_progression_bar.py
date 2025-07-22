import os

from PySide6.QtGui import QIcon
from PySide6.QtWidgets import (
    QVBoxLayout, QLabel, QProgressBar, QDialog
)
from PySide6.QtCore import Qt, QTimer


class ProgressionBar(QDialog):
    """
    Show a progress bar when downloading a file
    """
    def __init__(self, parent=None):
        super().__init__(parent)
        file_directory = (os.path.dirname(os.path.abspath(__file__)))
        dir_icon = os.path.join(file_directory, 'NEEDED/PICTURES/hands.ico')
        self.setWindowTitle('Progress')
        self.setWindowIcon(QIcon(dir_icon))
        self.setGeometry(550, 275, 350, 75)

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
        """
        Set the progress displayed on the bar
        :param value: value to set the progress bar to
        """
        if value < 100:
            self.progress_bar.setValue(int(round(value)))
        else:
            self.close()


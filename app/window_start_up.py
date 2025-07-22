import os

from PySide6.QtGui import QIcon
from PySide6.QtWidgets import (
    QVBoxLayout, QWidget, QPushButton, QFileDialog, QApplication, QDialog
)

from window_set_up import SetUp


class StartUp(QDialog):
    """
    Window at the beginning of the program, to load existing project or start a new one
    """
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Startup")
        file_directory = (os.path.dirname(os.path.abspath(__file__)))
        dir_icon = os.path.join(file_directory, 'NEEDED/PICTURES/hands.ico')
        self.setWindowIcon(QIcon(dir_icon))

        layout = QVBoxLayout()

        self.button_new = QPushButton("New Project")
        self.button_new.clicked.connect(self.open_setup)
        self.button_old = QPushButton("Open existing Project")
        self.button_old.clicked.connect(self.reopen_setup)
        self.compare_patients = QPushButton("Compare participants")

        layout.addWidget(self.button_new)
        layout.addWidget(self.button_old)
        layout.addWidget(self.compare_patients)

        self.setLayout(layout)

    # go to setup window
    def open_setup(self):
        self.setup = SetUp()
        self.setup.show()
        self.close()

    def reopen_setup(self):
        folder = QFileDialog.getExistingDirectory(self, "Select Trial Directory", os.path.expanduser("~/Documents"))
        if folder:
            self.setup = SetUp(folder)
            self.setup.show()
            self.close()
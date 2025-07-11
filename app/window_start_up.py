import os

from PySide6.QtGui import QIcon
from PySide6.QtWidgets import (
    QVBoxLayout, QWidget, QPushButton, QFileDialog, QApplication
)

from window_set_up import SetUp


class StartUp(QWidget):
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

        layout.addWidget(self.button_new)
        layout.addWidget(self.button_old)

        self.setLayout(layout)

        screen = QApplication.primaryScreen()
        screen_geometry = screen.availableGeometry()

        # Get actual window size (now accurate after full setup)
        window_rect = self.frameGeometry()

        # Calculate center position
        x = (screen_geometry.width() - window_rect.width()) // 2
        y = (screen_geometry.height() - window_rect.height()) // 2

        self.move(x, y)

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
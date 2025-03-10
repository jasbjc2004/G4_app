from PySide6.QtWidgets import (
    QVBoxLayout, QWidget, QPushButton
)

from window_set_up import SetUp


class StartUp(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Startup")

        layout = QVBoxLayout()

        self.button_new = QPushButton("New Project")
        self.button_new.clicked.connect(self.open_setup)
        self.button_old = QPushButton("Open existing Project")

        layout.addWidget(self.button_new)
        layout.addWidget(self.button_old)

        self.setLayout(layout)

    # go to setup window
    def open_setup(self):
        self.setup = SetUp()
        self.setup.show()
        self.close()
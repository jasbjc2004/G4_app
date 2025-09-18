import os

from PySide6.QtGui import QIcon
from PySide6.QtPdf import QPdfDocument
from PySide6.QtPdfWidgets import QPdfView
from PySide6.QtWidgets import (
    QVBoxLayout, QLabel, QDialog, QGraphicsView, QGraphicsScene
)
from PySide6.QtCore import Qt


class Manual(QDialog):
    def __init__(self, parent=None):
        """
        creates a window to check the use manual inside the program
        """
        super().__init__(parent)
        self.setWindowTitle("Manual")
        file_directory = (os.path.dirname(os.path.abspath(__file__)))
        dir_icon = os.path.join(file_directory, 'NEEDED/PICTURES/hands.ico')
        self.setWindowIcon(QIcon(dir_icon))
        self.setGeometry(200, 100, 800, 700)

        self.setWindowFlags(Qt.Window)
        self.setModal(True)

        layout = QVBoxLayout()

        self.pdf_document = QPdfDocument(self)
        self.pdf_view = QPdfView()
        self.pdf_view.setDocument(self.pdf_document)

        self.scene = QGraphicsScene()
        self.overlay_view = QGraphicsView(self.scene)
        self.overlay_view.setStyleSheet("background: transparent")

        self.pdf_view.setPageMode(QPdfView.PageMode.MultiPage)

        file_directory = (os.path.dirname(os.path.abspath(__file__)))
        dir_manual = os.path.join(file_directory, 'NEEDED/FILES/user_manual.pdf')
        pdf_path = os.path.abspath(dir_manual)
        self.pdf_document.load(pdf_path)

        layout.addWidget(self.pdf_view)
        self.setLayout(layout)



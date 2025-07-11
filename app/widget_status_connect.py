from PySide6.QtWidgets import (
    QWidget, QLabel, QHBoxLayout
)
from PySide6.QtGui import QPainter, QColor
from PySide6.QtCore import Qt, QSize, Property


class StatusDot(QWidget):
    """
    Needed for the circle at the button of the window
    """
    def __init__(self, parent=None):
        super().__init__(parent)
        self._status = "disconnected"
        self._status_colors = {
            "connected": QColor("#2ecc71"),  # Green
            "disconnected": QColor("#e74c3c"),  # Red
            "connecting": QColor("#f1c40f"),  # Yellow
            "no sensor": QColor("#A020F0")  # Purple
        }
        self.setFixedSize(12, 12)

    def sizeHint(self):
        return QSize(12, 12)

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)

        # Draw the outer circle (border)
        painter.setPen(Qt.black)
        painter.setBrush(self._status_colors.get(self._status, QColor("#e74c3c")))
        painter.drawEllipse(1, 1, 10, 10)

    @Property(str)
    def status(self):
        return self._status

    @status.setter
    def status(self, value):
        if value in self._status_colors:
            self._status = value
            self.update()


class StatusWidget(QWidget):
    """
    Needed for the widget in the status bar to check the connection
    """
    def __init__(self, parent=None):
        super().__init__(parent)
        self.layout = QHBoxLayout(self)
        self.layout.setContentsMargins(0, 0, 0, 0)
        self.layout.setSpacing(5)

        # Create status dot
        self.status_dot = StatusDot()

        # Create status label
        self.status_label = QLabel("Disconnected")

        # Add widgets to layout
        self.layout.addWidget(self.status_dot)
        self.layout.addWidget(self.status_label)

    def set_status(self, status):
        self.status_dot.status = status
        status_texts = {
            "connected": "Connected",
            "disconnected": "Disconnected",
            "connecting": "Connecting...",
            "no sensor": "No sensor needed"
        }
        self.status_label.setText(status_texts.get(status, "Unknown"))
import os

import serial
import serial.tools.list_ports
from PySide6.QtGui import QIcon

from PySide6.QtWidgets import (
    QVBoxLayout, QLabel, QDialog, QPushButton, QSizePolicy, QMessageBox
)
from PySide6.QtCore import Qt, QTimer


class ButtonTester(QDialog):
    """
    Check the connection with the button
    """
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Button tester")
        file_directory = (os.path.dirname(os.path.abspath(__file__)))
        dir_icon = os.path.join(file_directory, 'NEEDED/PICTURES/hands.ico')
        self.setWindowIcon(QIcon(dir_icon))
        self.setGeometry(550, 275, 400, 400)

        self.main_window = parent

        self.button_connect = None

        self.setWindowFlags(Qt.Window | Qt.WindowStaysOnTopHint)
        self.setModal(True)

        layout = QVBoxLayout()

        text_label = QLabel()
        text_label.setText(
            "This window helps you to connect the button and check if the button works. \n If the screen doesn't turn "
            "yellow when pressing the button, please check the connection from the button to the micro-processor")
        text_label.setWordWrap(True)
        text_label.setAlignment(Qt.AlignLeft | Qt.AlignTop)

        text_label.setFixedHeight(80)
        layout.addWidget(text_label)

        self.button = QPushButton("Button ", self)
        self.button.setGeometry(200, 300, 200, 400)
        self.button.setStyleSheet("background-color : grey")

        self.button.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        layout.addWidget(self.button)

        layout.setStretchFactor(self.button, 3)
        layout.setStretchFactor(text_label, 1)

        self.timer = QTimer(self)

        self.setLayout(layout)

        self.timer.timeout.connect(self.read_button)
        self.timer.setInterval(20)

        QTimer.singleShot(0, self.connect_button)

    def connect_button(self):
        """
        Go through all ports and check for the right serial input
        :return: the connection of the serial input
        """
        from window_main_plot import MainWindow

        available_ports = serial.tools.list_ports.comports()
        found_port = False

        for port in available_ports:
            if not found_port:
                try:
                    ser_temp = serial.Serial(port.device, 9600, timeout=1)
                    print(f"Trying {port.device}...")

                    ser_temp.flushInput()

                    data = ser_temp.readline().decode().strip()
                    if data:
                        print(f"Found device on {port.device}")
                        self.button_connect = ser_temp

                    line = ser_temp.readline().decode('utf-8').strip()
                    print(line)

                    if line == '1':
                        self.timer.start()
                        if isinstance(self.main_window, MainWindow):
                            self.main_window.button_trigger = ser_temp
                            self.main_window.connection_button_action.setEnabled(False)
                            self.main_window.disconnect_button_action.setEnabled(True)

                        return ser_temp

                except serial.SerialException as e:
                    print(f"Failed to connect to {port}: {e}")

        if not found_port:
            QMessageBox.critical(self, "Warning", "No button found! "
                                                  "If this keeps happening, unplug the USB and try again")

    def read_button(self):
        """
        check if the connection was successful and change the color of the button accordingly
        """
        if self.button_connect is not None:
            try:
                while self.button_connect.in_waiting > 0:
                    data = self.button_connect.readline().decode().strip()
                    if data:
                        print(f"Button state: {data}")  # Modify based on what your device sends

                    if data == '1':
                        self.button.setStyleSheet("background-color : grey")
                    elif data == '0':
                        self.button.setStyleSheet("background-color : yellow")

            except KeyboardInterrupt:
                print("Stopped by user.")

    def closeEvent(self, event):
        self.timer.stop()
        event.accept()
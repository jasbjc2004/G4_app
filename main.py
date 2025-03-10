import sys

from PySide6.QtWidgets import QApplication

from window_start_up import StartUp

if __name__ == "__main__":
    app = QApplication(sys.argv)
    startup = StartUp()
    startup.show()

    sys.exit(app.exec())
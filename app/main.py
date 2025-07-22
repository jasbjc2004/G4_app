import os
import sys
import time

from PySide6.QtCore import Qt
from PySide6.QtGui import QPixmap
from PySide6.QtWidgets import QApplication, QSplashScreen

if __name__ == "__main__":
    app = QApplication(sys.argv)

    pixmap = QPixmap(os.path.join(os.path.abspath("."), "NEEDED/PICTURES/hands.ico"))
    splash = QSplashScreen(pixmap)
    splash.show()

    app.processEvents()

    from window_start_up import StartUp

    startup = StartUp()

    splash.finish(startup)
    startup.show()

    sys.exit(app.exec())

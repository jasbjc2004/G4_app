import sys
import time

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QApplication, QSplashScreen

if __name__ == "__main__":
    app = QApplication(sys.argv)

    #pixmap = QPixmap("splash_logo.png")  # of een neutrale afbeelding
    #splash = QSplashScreen(pixmap)
    splash = QSplashScreen()
    splash.showMessage("Loading application ...", Qt.AlignBottom | Qt.AlignCenter, color=Qt.GlobalColor.white)
    splash.show()

    app.processEvents()

    from window_start_up import StartUp

    startup = StartUp()

    splash.finish(startup)
    startup.show()

    sys.exit(app.exec())

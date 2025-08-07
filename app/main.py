import asyncio
import os
import sys

from qasync import QEventLoop
from PySide6.QtGui import QPixmap
from PySide6.QtWidgets import QApplication, QSplashScreen

if __name__ == "__main__":
    app = QApplication(sys.argv)

    # Usage of async for the gopro
    loop = QEventLoop(app)
    asyncio.set_event_loop(loop)

    pixmap = QPixmap(os.path.join((os.path.dirname(os.path.abspath(__file__))), "NEEDED/PICTURES/hands.ico"))
    splash = QSplashScreen(pixmap)
    splash.show()

    app.processEvents()

    from window_start_up import StartUp

    startup = StartUp()

    splash.finish(startup)
    startup.show()

    with loop:
        sys.exit(app.exec())

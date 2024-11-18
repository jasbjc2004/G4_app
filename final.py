import sys
import random
from PySide6.QtWidgets import (
    QApplication, QVBoxLayout, QMainWindow, QWidget, QPushButton,
    QLineEdit, QLabel, QHBoxLayout, QDateEdit, QTextEdit, QMessageBox,
    QComboBox, QToolBar, QStatusBar, QTabWidget
)
from PySide6.QtGui import QAction
from PySide6.QtCore import Qt, QDate, QSize
from matplotlib.figure import Figure
from matplotlib.backends.backend_qt5agg import FigureCanvasQTAgg as FigureCanvas

# StartUp window
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

# SetUp window
class SetUp(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Project Setup")

        main_layout = QVBoxLayout()

        form_layout = QVBoxLayout()

        # patient name -> change to participant code ?
        name_layout = QHBoxLayout()
        name_label = QLabel("Participant code:")
        self.name_input = QLineEdit()
        name_layout.addWidget(name_label)
        name_layout.addWidget(self.name_input)

        # Number of trials
        trial_layout = QHBoxLayout()
        self.combo_box = QComboBox()
        for i in range(1, 21):
            self.combo_box.addItem(str(i), i)

        self.label = QLabel("Number of trials: ")
        self.combo_box.setCurrentIndex(9)
        self.combo_box.currentIndexChanged.connect(self.update_label)

        trial_layout.addWidget(self.label)
        trial_layout.addWidget(self.combo_box)

        # Date Picker
        date_layout = QHBoxLayout()
        date_label = QLabel("Date:")
        self.date_input = QDateEdit()
        self.date_input.setCalendarPopup(True)
        self.date_input.setDate(QDate.currentDate())
        date_layout.addWidget(date_label)
        date_layout.addWidget(self.date_input)

        # Additional Notes
        notes_layout = QVBoxLayout()
        notes_label = QLabel("Additional Notes:")
        self.notes_input = QTextEdit()
        notes_layout.addWidget(notes_label)
        notes_layout.addWidget(self.notes_input)

        # Add widgets to the form layout
        form_layout.addLayout(name_layout)
        form_layout.addLayout(date_layout)
        form_layout.addLayout(trial_layout)
        form_layout.addLayout(notes_layout)

        # Add Start button
        button_layout = QHBoxLayout()
        self.save_button = QPushButton("Save")
        self.save_button.clicked.connect(self.save_button_pressed)

        self.back_button = QPushButton("Back")
        self.back_button.clicked.connect(self.back_button_pressed)
        button_layout.addStretch()
        button_layout.addWidget(self.back_button)
        button_layout.addWidget(self.save_button)

        # Add form and button layouts to main layout
        main_layout.addLayout(form_layout)
        main_layout.addLayout(button_layout)

        self.setLayout(main_layout)

    def update_label(self):
        selected_number = self.combo_box.currentData()

    # go to next window + save data
    def save_button_pressed(self):
        if self.name_input.text().strip() == "":
            ret = QMessageBox.warning(self, "Warning", "One of the input fields seems to be empty, do you wish to continue anyway?", QMessageBox.Yes | QMessageBox.Cancel)
            if ret == QMessageBox.Yes:
                num_trials = self.combo_box.currentData()
                self.mainwindow = MainWindow(num_trials)
                self.mainwindow.show()
                self.close()
        else:
            num_trials = self.combo_box.currentData()
            self.mainwindow = MainWindow(num_trials)
            self.mainwindow.show()
            self.close()
    # go back to startup window
    def back_button_pressed(self):
        self.startup = StartUp()
        self.startup.show()
        self.close()

# MainWindow
class MainWindow(QMainWindow):
    def __init__(self, num_trials):
        super().__init__()
        self.setWindowTitle("Sensors")

        # Menu bar
        menu_bar = self.menuBar()
        file_menu = menu_bar.addMenu("&File")
        quit_action = file_menu.addAction("Quit")
        quit_action.triggered.connect(self.close)

        # test buttons
        edit_menu = menu_bar.addMenu("Edit")
        edit_menu.addAction("Copy")
        edit_menu.addAction("Cut")
        edit_menu.addAction("Paste")
        edit_menu.addAction("Undo")
        edit_menu.addAction("Redo")

        menu_bar.addMenu("Window")
        menu_bar.addMenu("Settings")
        menu_bar.addMenu("&Help")

        menu_bar.setNativeMenuBar(False)

        # Toolbar
        toolbar = QToolBar("My main toolbar")
        toolbar.setIconSize(QSize(16, 16))
        self.addToolBar(toolbar)

        toolbar.addAction(quit_action)
        # test buttons
        action1 = QAction("Some action", self)
        action1.setStatusTip("Status message for some action")
        action1.triggered.connect(self.toolbar_button_click)
        toolbar.addAction(action1)

        toolbar.addSeparator()
        toolbar.addWidget(QPushButton("Click here"))

        # Tabs = number of trials
        tab_widget = QTabWidget(self)

        for i in range(1, num_trials + 1):
            tab = QWidget()
            layout = QVBoxLayout()

            # Graph Area
            figure = Figure()
            canvas = FigureCanvas(figure)
            ax = figure.add_subplot(111)
            x = [i for i in range(10)]
            y = [random.randint(0, 10) for _ in range(10)]
            ax.plot(x, y, label="Sample Data")
            ax.set_title(f"Graph {i}")
            ax.set_xlabel("X-axis")
            ax.set_ylabel("Y-axis")
            ax.legend()

            # Buttons
            button_layout = QHBoxLayout()
            start_button = QPushButton("Start")
            stop_button = QPushButton("Stop")
            overwrite_button = QPushButton("Overwrite")

            # Connect buttons to their respective functions
            start_button.clicked.connect(lambda: self.start_trial(i))
            stop_button.clicked.connect(lambda: self.stop_trial(i))
            overwrite_button.clicked.connect(lambda: self.overwrite_trial(i))

            button_layout.addWidget(start_button)
            button_layout.addWidget(stop_button)
            button_layout.addWidget(overwrite_button)

            layout.addWidget(canvas)
            layout.addLayout(button_layout)

            tab.setLayout(layout)
            tab_widget.addTab(tab, f"Trial {i}")

        self.setCentralWidget(tab_widget)

        # Status bar
        self.setStatusBar(QStatusBar(self))

    # test functions
    def start_trial(self, trial_number):
        print(f"Starting trial {trial_number}...")

    def stop_trial(self, trial_number):
        print(f"Stopping trial {trial_number}...")

    def overwrite_trial(self, trial_number):
        print(f"Overwriting trial {trial_number}...")

    def toolbar_button_click(self):
        self.statusBar().showMessage("Message from my app", 3000)


app = QApplication(sys.argv)
startup = StartUp()
startup.show()

app.exec()

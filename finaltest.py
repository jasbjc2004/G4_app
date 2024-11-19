import os
import sys
import numpy as np
import time
from PySide6.QtWidgets import (
    QApplication, QVBoxLayout, QMainWindow, QWidget, QPushButton,
    QLineEdit, QLabel, QHBoxLayout, QDateEdit, QTextEdit, QMessageBox,
    QComboBox, QToolBar, QStatusBar, QTabWidget
)
from PySide6.QtGui import QAction
from PySide6.QtCore import Qt, QDate, QSize, QTimer
from matplotlib.figure import Figure
from matplotlib.backends.backend_qt5agg import FigureCanvasQTAgg as FigureCanvas

from G4Track import get_frame_data, initialize_system
from data_processing import calibration_to_center


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
            ret = QMessageBox.warning(self, "Warning",
                                      "One of the input fields seems to be empty, do you wish to continue anyway?",
                                      QMessageBox.Yes | QMessageBox.Cancel)
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
        self.first_time = True
        self.is_connected = False
        self.dongle_id = None
        self.hub_id = None
        self.lindex = None
        self.rindex = None
        self.reading_active = False

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
        tab = QWidget()
        layout_tab = QVBoxLayout()

        self.figure = Figure()
        self.canvas = FigureCanvas(self.figure)
        layout_tab.addWidget(self.canvas)
        self.ax = self.figure.add_subplot(111)

        self.sensor_values = []
        self.ax.set_title('Sensor Data Simulation')
        self.ax.set_xlabel('Time (s)')
        self.ax.set_ylabel('Values')
        self.reading = False

        self.xs = []
        self.y1s = []
        self.y2s = []
        self.start_time = time.time()

        self.line1, = self.ax.plot([], [], lw=2, label='left', color='blue')
        self.line2, = self.ax.plot([], [], lw=2, label='right', color='orange')
        self.ax.legend()

        self.timer = QTimer(self)
        self.timer.timeout.connect(self.update_plot)
        self.timer.start(20)

        # Buttons
        button_layout = QHBoxLayout()
        start_button = QPushButton("Start")
        stop_button = QPushButton("Stop")
        overwrite_button = QPushButton("Overwrite")

        button_layout.addWidget(start_button)
        button_layout.addWidget(stop_button)
        button_layout.addWidget(overwrite_button)

        layout_tab.addWidget(self.canvas)
        layout_tab.addLayout(button_layout)

        tab.setLayout(layout_tab)
        tab_widget.addTab(tab, f"Trial {1}")

        self.setCentralWidget(tab_widget)

        # Modified toolbar actions with better labels
        self.connect_action = QAction("Connect", self)
        self.connect_action.setStatusTip("Connect to sensors")
        self.connect_action.triggered.connect(self.connecting)
        toolbar.addAction(self.connect_action)

        read = QAction("Start Reading", self)
        read.setStatusTip("Start reading sensor data")
        read.triggered.connect(self.start_reading)
        toolbar.addAction(read)

        stop = QAction("Stop Reading", self)
        stop.setStatusTip("Stop reading sensor data")
        stop.triggered.connect(self.stop_reading)
        toolbar.addAction(stop)

        # Status bar
        self.setStatusBar(QStatusBar(self))

    def toolbar_button_click(self):
        self.statusBar().showMessage("Message from my app", 3000)

    def read_sensor_data(self):
        if not self.is_connected:
            return 0, 0, 0

        elapsed_time = time.time() - self.start_time
        frame_data, active_count, data_hubs = get_frame_data(self.dongle_id, [self.hub_id])

        y1 = frame_data.G4_sensor_per_hub[self.lindex].pos[1]
        y2 = frame_data.G4_sensor_per_hub[self.rindex].pos[1]
        return elapsed_time, abs(y1), abs(y2)

    def update_plot(self):
        if self.reading_active and self.is_connected:
            # Read simulated data
            time_val, y1, y2 = self.read_sensor_data()

            # Update data lists
            self.xs.append(time_val)
            self.y1s.append(y1)
            self.y2s.append(y2)

            # Keep only last 200 points
            self.xs = self.xs[-200:]
            self.y1s = self.y1s[-200:]
            self.y2s = self.y2s[-200:]

            # Update plot
            self.line1.set_xdata(self.xs)
            self.line1.set_ydata(self.y1s)
            self.line2.set_xdata(self.xs)
            self.line2.set_ydata(self.y2s)

            # Adjust axes
            if self.xs:  # Only adjust if there's data
                self.ax.set_xlim(min(self.xs), max(self.xs) + 1)
                self.ax.set_ylim(0, max(max(self.y1s, default=1), max(self.y2s, default=1)) * 1.1)

            # Redraw canvas
            self.canvas.draw()
            self.canvas.flush_events()

    def start_reading(self):
        if not self.is_connected:
            QMessageBox.warning(self, "Warning", "Please connect to sensors first!")
            return
        self.reading_active = True
        self.start_time = time.time()  # Reset start time when starting to read
        self.statusBar().showMessage("Reading sensor data...")

    def stop_reading(self):
        self.reading_active = False
        self.statusBar().showMessage("Sensor reading stopped")

    def connecting(self):
        if self.is_connected:
            QMessageBox.information(self, "Info", "Already connected to sensors!")
            return

        try:
            file_directory = os.path.dirname(os.path.abspath(__file__))
            src_cfg_file = os.path.join(file_directory, "first_calibration.g4c")

            connected = False
            self.dongle_id = None

            # Add timeout to prevent infinite loop
            max_attempts = 3
            attempt = 0

            while self.dongle_id is None and attempt < max_attempts:
                connected, self.dongle_id = initialize_system(src_cfg_file)
                attempt += 1

            if not connected or self.dongle_id is None:
                QMessageBox.critical(self, "Error", "Failed to connect to sensors after multiple attempts!")
                return

            self.hub_id, self.lindex, self.rindex = calibration_to_center(self.dongle_id)
            self.is_connected = True
            self.connect_action.setEnabled(False)  # Disable connect button after successful connection
            self.statusBar().showMessage("Successfully connected to sensors")
            QMessageBox.information(self, "Success", "Successfully connected to sensors!")

        except Exception as e:
            QMessageBox.critical(self, "Error", f"Error connecting to sensors: {str(e)}")
            self.is_connected = False


app = QApplication(sys.argv)
startup = StartUp()
startup.show()

app.exec()

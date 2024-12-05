import os
import random
import sys
import time
from math import sqrt

import pandas as pd
from fpdf import FPDF
from enum import Enum

from PySide6.QtWidgets import (
    QApplication, QVBoxLayout, QMainWindow, QWidget, QPushButton,
    QLineEdit, QLabel, QHBoxLayout, QDateEdit, QTextEdit, QMessageBox,
    QComboBox, QToolBar, QStatusBar, QTabWidget, QSizePolicy, QInputDialog,
    QFileDialog, QDialog, QProgressDialog, QCheckBox, QDialogButtonBox
)
from PySide6.QtGui import QAction, QPainter, QColor
from PySide6.QtCore import Qt, QDate, QSize, QTimer, Property, QSettings
from matplotlib import pyplot as plt
from matplotlib.figure import Figure
from matplotlib.backends.backend_qt5agg import FigureCanvasQTAgg as FigureCanvas

from G4Track import get_frame_data, initialize_system, set_units, get_active_hubs
from data_processing import calibration_to_center

MAX_TRAILS = 21
READ_SAMPLE = False
BEAUTY_SPEED = False
MAX_ATTEMPTS = 10

"""
# https://stackoverflow.com/questions/31836104/pyinstaller-and-onefile-how-to-include-an-image-in-the-exe-file
def resource_path(relative_path):
    # Get absolute path to resource, works for dev and for PyInstaller
    try:
        # PyInstaller creates a temp folder and stores path in _MEIPASS
        base_path = sys._MEIPASS
    except Exception:
        base_path = os.path.abspath(".")

    return os.path.join(base_path, relative_path)
"""

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
class SetUp(QDialog):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Project Settings")

        self.settings = QSettings("PNO", "GUIsensor")

        self.settings.value("additional notes", "")


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

        #assessor
        assessor_layout = QHBoxLayout()
        assessor_label = QLabel("Assessor:            ")
        self.assessor_input = QLineEdit()
        assessor_layout.addWidget(assessor_label)
        assessor_layout.addWidget(self.assessor_input)

        # Add widgets to the form layout
        form_layout.addLayout(name_layout)
        form_layout.addLayout(assessor_layout)
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


class StatusDot(QWidget):
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


class TrialState(Enum):
    not_started = 0
    running = 1
    completed = 2


# Tab window
class TrailTab(QWidget):
    def __init__(self, trail_number, parent=None):
        super().__init__(parent)
        self.trial_number = trail_number
        self.reading_active = False
        self.start_time = None
        self.trial_state = TrialState.not_started

        self.pos_left = [0, 0, 0]
        self.pos_right = [0, 0, 0]
        self.xs = []
        self.log_left_plot = []
        self.log_right_plot = []

        self.plot_left_data = []
        self.plot_right_data = []

        self.setup()

    def setup(self):
        self.layout_tab = QHBoxLayout()
        self.setLayout(self.layout_tab)

        self.animation_widget = QWidget()
        self.animation_layout = QVBoxLayout(self.animation_widget)
        self.animation_widget.setLayout(self.animation_layout)
        self.layout_tab.addWidget(self.animation_widget)
        self.layout_tab.setStretch(2, 1)

        self.setup_plot()

        self.notes_widget = QWidget()
        self.notes_layout = QVBoxLayout(self.notes_widget)
        self.notes_label = QLabel("Notes:")
        self.notes_input = QTextEdit()
        self.notes_layout.addWidget(self.notes_label)
        self.notes_layout.addWidget(self.notes_input)
        self.layout_tab.addWidget(self.notes_widget)
        self.layout_tab.setStretch(1, 1)

        self.animation_widget.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)

        self.canvas.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)

        self.timer = QTimer(self)
        self.timer.timeout.connect(self.update_plot)
        self.timer.setInterval(20)

    def setup_plot(self):
        self.figure = Figure(constrained_layout=True)
        self.canvas = FigureCanvas(self.figure)
        # gaat mss aangepast moeten worden afhankelijk van hoe de notepad eruit zit
        self.canvas.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self.ax = self.figure.add_subplot(111)

        self.ax.set_title(f'Trial {self.trial_number + 1} - velocity plot')
        self.ax.set_xlabel('Time (s)')
        self.ax.set_ylabel('Velocity (cm/s)')
        self.ax.grid(True)

        self.ax.set_ylim(0, 10)
        self.ax.set_xlim(0, 10)

        self.line1, = self.ax.plot([], [], lw=2, label='Left', color='blue')
        self.line2, = self.ax.plot([], [], lw=2, label='Right', color='orange')
        self.ax.legend()

        self.layout_tab.addWidget(self.canvas)
        self.figure.tight_layout()

    def start_reading(self):
        if self.trial_state == TrialState.not_started:
            if not self.start_time:
                self.start_time = time.time()

            self.reading_active = True
            self.trial_state = TrialState.running
            self.timer.start()
            main_window = self.window()
            if isinstance(main_window, MainWindow):
                main_window.update_toolbar()

    def stop_reading(self):
        if self.trial_state == TrialState.running:
            self.reading_active = False
            self.timer.stop()
            self.trial_state = TrialState.completed
            main_window = self.window()
            if isinstance(main_window, MainWindow):
                main_window.update_toolbar()

    def reset_reading(self):
        if self.trial_state == TrialState.completed:
            self.ax.set_ylim(0, 10)
            self.ax.set_xlim(0, 10)

            self.pos_left = [0, 0, 0]
            self.pos_right = [0, 0, 0]
            self.xs = []
            self.log_left_plot = []
            self.log_right_plot = []

            self.plot_left_data = []
            self.plot_right_data = []

            self.line1.set_data([], [])
            self.line2.set_data([], [])

            self.canvas.draw()

            self.trial_state = TrialState.not_started
            main_window = self.window()
            if isinstance(main_window, MainWindow):
                main_window.update_toolbar()

            self.start_time = None

    def read_sensor_data(self):
        elapsed_time = time.time() - self.start_time

        if not READ_SAMPLE:
            main_window = self.window()

            if isinstance(main_window, MainWindow):
                if not main_window.is_connected:
                    return 0, 0, 0

            frame_data, active_count, data_hubs = get_frame_data(main_window.dongle_id, [main_window.hub_id])

            pos1 = frame_data.G4_sensor_per_hub[main_window.lindex].pos
            pos2 = frame_data.G4_sensor_per_hub[main_window.rindex].pos

            if tuple(pos1) == (0, 0, 0) or tuple(pos2) == (0, 0, 0):
                return elapsed_time, [x for x in self.pos_left], [x for x in self.pos_right]

            self.pos_left = pos1
            self.pos_right = pos2

            return elapsed_time, pos1, pos2
        elif BEAUTY_SPEED:
            if elapsed_time < 5:
                return elapsed_time, [0, 0, -elapsed_time], [0, elapsed_time, 0]
            elif elapsed_time < 10:
                return elapsed_time, [0, 0, -5 + (elapsed_time - 5)], [0, 5 - (elapsed_time - 5), 0]
            elif (elapsed_time < 15):
                return elapsed_time, [0, 0, -5 * (elapsed_time - 10)], [0, 5 * (elapsed_time - 10), 0]
            elif (elapsed_time < 20):
                return elapsed_time, [0, 0, -25+5 * (elapsed_time - 15)], [0, 25-5 * (elapsed_time - 15), 0]
            return elapsed_time, [0] * 3, [0] * 3
        else:
            return elapsed_time, [random.randint(-20, 20), random.randint(0, 20), random.randint(-20, 0)], \
                                 [random.randint(0, 20), random.randint(0, 20), random.randint(-20, 0)]

    def update_axis(self):
        main_window = self.window()

        if isinstance(main_window, MainWindow):
            if main_window.xt:
                self.ax.set_title(f'Trial {self.trial_number + 1} - x-coordinates')
                self.ax.set_ylabel('X-coordinates (cm)')

                self.plot_left_data = [abs(pos[0]) if main_window.set_abs_value else pos[0] for pos in self.log_left_plot]
                self.plot_right_data = [pos[0] for pos in self.log_right_plot]
            elif main_window.yt:
                self.ax.set_title(f'Trial {self.trial_number + 1} - y-coordinates')
                self.ax.set_ylabel('Y-coordinates (cm)')

                self.plot_left_data = [pos[1] for pos in self.log_left_plot]
                self.plot_right_data = [pos[1] for pos in self.log_right_plot]
            elif main_window.zt:
                self.ax.set_title(f'Trial {self.trial_number + 1} - z-coordinates')
                self.ax.set_ylabel('Z-coordinates (cm)')

                self.plot_left_data = [-pos[2] for pos in self.log_left_plot]
                self.plot_right_data = [-pos[2] for pos in self.log_right_plot]
            else:
                self.ax.set_title(f'Trial {self.trial_number + 1} - velocity plot')
                self.ax.set_ylabel('Velocity (cm/s)')

                self.plot_left_data = [pos[3] for pos in self.log_left_plot]
                self.plot_right_data = [pos[3] for pos in self.log_right_plot]

        self.line1.set_xdata(self.xs)
        self.line1.set_ydata(self.plot_left_data)
        self.line2.set_xdata(self.xs)
        self.line2.set_ydata(self.plot_right_data)

        self.ax.set_xlim(0, 10)
        self.ax.set_ylim(0, 10)
        if self.xs:  # Only adjust if there's data
            self.ax.set_xlim(0, self.xs[-1] + 1)

            max_y = max(max(self.plot_left_data[-200:], default=1),
                        max(self.plot_right_data[-200:], default=1)) * 1.1
            min_y = min(min(self.plot_left_data[-200:], default=1),
                        min(self.plot_right_data[-200:], default=1)) * 1.1
            if max_y < 10:
                max_y = 10
            if min_y > 0 or main_window.set_abs_value:
                min_y = 0

            self.ax.set_ylim(min_y, max_y)

        # Redraw canvas
        self.canvas.draw()

    def update_plot(self):
        if self.reading_active and self.trial_state == TrialState.running:
            # Read simulated data
            time_val, lpos, rpos = self.read_sensor_data()
            lpos, rpos = list(lpos), list(rpos)

            if len(self.log_left_plot) > 0:
                vl, vr = sqrt(((lpos[0] - self.log_left_plot[-1][0]) / (time_val - self.xs[- 1])) ** 2 +
                              ((lpos[1] - self.log_left_plot[-1][1]) / (time_val - self.xs[-1])) ** 2 +
                              ((lpos[2] - self.log_left_plot[-1][2]) / (time_val - self.xs[-1])) ** 2), \
                         sqrt(((rpos[0] - self.log_right_plot[-1][0]) / (time_val - self.xs[-1])) ** 2 +
                              ((rpos[1] - self.log_right_plot[-1][1]) / (time_val - self.xs[-1])) ** 2 +
                              ((rpos[2] - self.log_right_plot[-1][2]) / (time_val - self.xs[-1])) ** 2)
            else:
                vl, vr = 0, 0

            y1, y2 = 0, 0
            main_window = self.window()
            if isinstance(main_window, MainWindow):
                if main_window.xt:
                    if main_window.set_abs_value:
                        y1, y2 = -lpos[0], rpos[0]
                    else:
                        y1, y2 = lpos[0], rpos[0]
                elif main_window.yt:
                    y1, y2 = lpos[1], rpos[1]
                elif main_window.zt:
                    y1, y2 = -lpos[2], -rpos[2]
                else:
                    y1, y2 = vl, vr

            # Update data lists
            self.xs.append(time_val)
            lpos.append(vl)
            rpos.append(vr)
            self.log_left_plot.append(list(lpos))
            self.log_right_plot.append(list(rpos))

            self.plot_left_data.append(y1)
            self.plot_right_data.append(y2)

            # Update plot
            self.line1.set_xdata(self.xs)
            self.line1.set_ydata(self.plot_left_data)
            self.line2.set_xdata(self.xs)
            self.line2.set_ydata(self.plot_right_data)

            # Adjust axes
            if self.xs:  # Only adjust if there's data
                self.ax.set_xlim(0, self.xs[-1] + 1)

                max_y = max(max(self.plot_left_data[-200:], default=1),
                            max(self.plot_right_data[-200:], default=1)) * 1.1
                min_y = min(min(self.plot_left_data[-200:], default=1),
                            min(self.plot_right_data[-200:], default=1)) * 1.1
                if max_y < 10:
                    max_y = 10
                if min_y > 0 or main_window.set_abs_value:
                    min_y = 0

                self.ax.set_ylim(min_y, max_y)

            # Redraw canvas
            self.canvas.draw()


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
        self.set_abs_value = False

        self.xt = False
        self.yt = False
        self.zt = False
        self.vt = True

        self.resize(800, 600)
        self.setup(num_trials)
        self.num_trials = num_trials

    def setup(self, num_trials):
        self.central_widget = QWidget()
        self.setCentralWidget(self.central_widget)
        self.main_layout = QVBoxLayout()
        self.central_widget.setLayout(self.main_layout)

        self.setup_menubar()
        self.setup_toolbar()
        self.setup_statusbar()

        self.tab_widget = QTabWidget()
        self.tab_widget.currentChanged.connect(self.tab_change_handler)
        for i in range(0, num_trials):
            tab = TrailTab(i, self.tab_widget)
            self.tab_widget.addTab(tab, f"Trial {i + 1}")

        self.main_layout.addWidget(self.tab_widget)
        self.update_toolbar()

    def tab_change_handler(self, index):
        self.update_toolbar()

    def setup_menubar(self):
        menu_bar = self.menuBar()
        file_menu = menu_bar.addMenu("&File")
        excel_action = file_menu.addAction("Export to Excel and PDF")
        excel_action.triggered.connect(self.download_excel)
        tab_extra = file_menu.addAction("Add extra tab")
        tab_extra.triggered.connect(self.add_another_tab)
        file_menu.addSeparator()
        quit_action = file_menu.addAction("Quit")
        quit_action.triggered.connect(self.close)

        edit_menu = menu_bar.addMenu("Plot")
        xt_action = edit_menu.addAction("x(t)-plot")
        xt_action.triggered.connect(self.xt_plot)
        yt_action = edit_menu.addAction("y(t)-plot")
        yt_action.triggered.connect(self.yt_plot)
        zt_action = edit_menu.addAction("z(t)-plot")
        zt_action.triggered.connect(self.zt_plot)
        vt_action = edit_menu.addAction("v(t)-plot")
        vt_action.triggered.connect(self.vt_plot)

        menu_bar.addMenu("Window")
        settings_menu = menu_bar.addMenu("Settings")
        absx_action = settings_menu.addAction("Set absolute values to x-axis")
        absx_action.setCheckable(True)
        absx_action.triggered.connect(lambda: self.plot_absolute_x(absx_action))
        menu_bar.addMenu("&Help")

        menu_bar.setNativeMenuBar(False)

    def setup_toolbar(self):
        toolbar = QToolBar("My main toolbar")
        toolbar.setIconSize(QSize(16, 16))
        self.addToolBar(toolbar)
        toolbar.setMovable(False)

        self.connection_action = QAction("Connect", self)
        if READ_SAMPLE:
            self.connection_action.setEnabled(False)
        self.connection_action.setStatusTip("Connect and calibrate the sensor")
        self.connection_action.triggered.connect(lambda: self.connecting())
        toolbar.addAction(self.connection_action)

        self.calibrate_action = QAction("Calibrate", self)
        self.calibrate_action.setEnabled(False)
        self.calibrate_action.setStatusTip("Calibrate the sensor")
        self.calibrate_action.triggered.connect(lambda: self.calibration())
        toolbar.addAction(self.calibrate_action)

        toolbar.addSeparator()

        self.start_action = QAction("Start trial", self)
        self.start_action.setStatusTip("Start the current trial")
        self.start_action.triggered.connect(lambda: self.start_current_reading())

        self.stop_action = QAction("Stop trial", self)
        self.stop_action.setStatusTip("Stop the current trial")
        self.stop_action.setEnabled(False)
        self.stop_action.triggered.connect(lambda: self.stop_current_reading())

        self.reset_action = QAction("Overwrite trial", self)
        self.reset_action.setStatusTip("Overwrite the current trial")
        self.reset_action.setEnabled(False)
        self.reset_action.triggered.connect(lambda: self.reset_current_reading())

        toolbar.addActions([self.start_action, self.stop_action, self.reset_action])

        toolbar.addSeparator()

        quit_action = QAction("Quit", self)
        quit_action.triggered.connect(self.close)
        toolbar.addAction(quit_action)

    def setup_statusbar(self):
        self.statusbar = QStatusBar(self)
        self.setStatusBar(self.statusbar)

        self.status_widget = StatusWidget()
        self.statusbar.addPermanentWidget(self.status_widget)
        if READ_SAMPLE:
            self.status_widget.set_status("no sensor")
        else:
            self.status_widget.set_status("disconnected")

    def calibrate_message(self):
        self.statusBar().showMessage("Calibrating the sensors...", 5000)

    def get_tab(self):
        tab = self.tab_widget.currentWidget()
        if isinstance(tab, TrailTab):
            return tab
        return None

    def add_another_tab(self):
        tab = TrailTab(self.num_trials, self.tab_widget)
        self.tab_widget.addTab(tab, f"Trial {self.num_trials + 1}")
        self.num_trials += 1

    def update_toolbar(self):
        tab = self.get_tab()

        if tab is None or (not self.is_connected and not READ_SAMPLE):
            self.start_action.setEnabled(False)
            self.stop_action.setEnabled(False)
            self.reset_action.setEnabled(False)
            return

        if tab.trial_state == TrialState.not_started:
            self.start_action.setEnabled(True)
            self.stop_action.setEnabled(False)
            self.reset_action.setEnabled(False)
        elif tab.trial_state == TrialState.running:
            self.start_action.setEnabled(False)
            self.stop_action.setEnabled(True)
            self.reset_action.setEnabled(False)
        elif tab.trial_state == TrialState.completed:
            self.start_action.setEnabled(False)
            self.stop_action.setEnabled(False)
            self.reset_action.setEnabled(True)

    def start_current_reading(self):
        tab = self.get_tab()

        if tab is not None:
            tab.start_reading()
            self.tab_widget.tabBar().setEnabled(False)

    def stop_current_reading(self):
        tab = self.get_tab()

        if tab is not None:
            tab.stop_reading()
            self.tab_widget.tabBar().setEnabled(True)

    def reset_current_reading(self):
        tab = self.get_tab()

        if tab is not None:
            tab.reset_reading()
            self.update_toolbar()

    def connecting(self):
        if self.is_connected:
            QMessageBox.information(self, "Info", "Already connected to sensors!")
            return

        self.status_widget.set_status("connecting")
        self.repaint()
        file_directory = (os.path.dirname(os.path.abspath(__file__)))
        src_cfg_file = (os.path.join(file_directory, "first_calibration.g4c"))

        connected = False
        self.dongle_id = None

        # Add timeout to prevent infinite loop
        attempt = 0

        while self.dongle_id is None and attempt < MAX_ATTEMPTS:
            connected, self.dongle_id = initialize_system(src_cfg_file)
            attempt += 1

        if not connected or self.dongle_id is None:
            QMessageBox.critical(self, "Error", "Failed to connect to sensors after multiple attempts!")
            self.status_widget.set_status("disconnected")
            return

        try:
            get_active_hubs(self.dongle_id, True)[0]
        except:
            QMessageBox.critical(self, "Error", "Failed to connect to hubs! Please check if they are online")
            self.status_widget.set_status("disconnected")
            self.dongle_id = None
            return

        set_units(self.dongle_id)
        self.hub_id, self.lindex, self.rindex, self.calibration_status = calibration_to_center(self.dongle_id)

        if not self.calibration_status:
            QMessageBox.critical(self, "Warning", "Calibration did not succeed!")

        self.is_connected = True
        self.connection_action.setEnabled(False)  # Disable connect button after successful connection
        self.calibrate_action.setEnabled(True)
        self.statusBar().showMessage("Successfully connected to sensors")
        QMessageBox.information(self, "Success", "Successfully connected to sensors!")
        self.status_widget.set_status("connected")
        self.update_toolbar()

    def calibration(self):
        self.hub_id, self.lindex, self.rindex, self.calibration_status = calibration_to_center(self.dongle_id)

    def xt_plot(self):
        self.xt = True
        self.yt = False
        self.zt = False
        self.vt = False

        self.get_tab().update_axis()

    def yt_plot(self):
        self.xt = False
        self.yt = True
        self.zt = False
        self.vt = False

        self.get_tab().update_axis()

    def zt_plot(self):
        self.xt = False
        self.yt = False
        self.zt = True
        self.vt = False

        self.get_tab().update_axis()

    def vt_plot(self):
        self.xt = False
        self.yt = False
        self.zt = False
        self.vt = True

        self.get_tab().update_axis()

    def plot_absolute_x(self, button):
        if button.isChecked():
            self.set_abs_value = True
        else:
            self.set_abs_value = False
        self.get_tab().update_axis()

    def download_excel(self):
        while True:
            selection_plot = QDialog(self)
            selection_plot.setWindowTitle("Select graph to save")
            layout = QVBoxLayout()

            # Participant code input
            name_layout = QHBoxLayout()
            name_label = QLabel("Participant code:")
            participant_code = QLineEdit()
            name_layout.addWidget(name_label)
            name_layout.addWidget(participant_code)
            layout.addLayout(name_layout)

            # Plot selection checkboxes
            checkboxes = [
                QCheckBox("The x-position"),
                QCheckBox("The y-position"),
                QCheckBox("The z-position"),
                QCheckBox("The speed")
            ]
            for checkbox in checkboxes:
                checkbox.setChecked(True)
                layout.addWidget(checkbox)

            # Dialog buttons
            button_box = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
            button_box.accepted.connect(selection_plot.accept)
            button_box.rejected.connect(selection_plot.reject)
            layout.addWidget(button_box)

            selection_plot.setLayout(layout)
            result = selection_plot.exec()

            # Handle user input
            if result == QDialog.Rejected:
                return

            if not participant_code.text().strip():
                QMessageBox.warning(self, "Warning", "Participant code is required!")
                continue

            # File and folder selection
            folder = QFileDialog.getExistingDirectory(self, "Select Save Directory", os.path.expanduser("~/Documents"))
            if not folder:
                QMessageBox.warning(self, "Warning", "No directory selected! Please try again.")
                return

            # Disable main window during export
            self.setEnabled(False)

            # Create participant folder
            participant_folder = os.path.join(folder, participant_code.text())
            os.makedirs(participant_folder, exist_ok=True)

            # PDF and export setup
            pdf = FPDF()
            pdf.set_auto_page_break(auto=True, margin=15)
            pdf.add_page()
            pdf.set_font("Arial", size=12)

            def export_tab(index):
                QApplication.processEvents()
                tab = self.tab_widget.widget(index)

                if isinstance(tab, TrailTab):
                    # Data export logic (same as your original code)
                    data = {
                        "Time (s)": tab.xs if tab.xs else [],
                        "Left Sensor x (cm)": [pos[0] for pos in tab.log_left_plot] if tab.xs else [],
                        "Left Sensor y (cm)": [pos[1] for pos in tab.log_left_plot] if tab.xs else [],
                        "Left Sensor z (cm)": [-pos[2] for pos in tab.log_left_plot] if tab.xs else [],
                        "Left Sensor v (m/s)": [pos[3] for pos in tab.log_left_plot] if tab.xs else [],
                        "Right Sensor x (cm)": [pos[0] for pos in tab.log_right_plot] if tab.xs else [],
                        "Right Sensor y (cm)": [pos[1] for pos in tab.log_right_plot] if tab.xs else [],
                        "Right Sensor z (cm)": [-pos[2] for pos in tab.log_right_plot] if tab.xs else [],
                        "Right Sensor v (m/s)": [pos[3] for pos in tab.log_right_plot] if tab.xs else [],
                    }
                    max_length = max(len(v) for v in data.values())
                    for key in data:
                        data[key].extend([None] * (max_length - len(data[key])))

                    df = pd.DataFrame(data)
                    trial_file = os.path.join(participant_folder, f"trial_{index + 1}.xlsx")
                    df.to_excel(trial_file, index=False)

                    # PDF generation logic (same as your original code)
                    pdf.set_font("Arial", style="B", size=14)
                    pdf.cell(0, 10, f"Trial {index + 1}", ln=True)
                    pdf.set_font("Arial", size=12)
                    notes = tab.notes_input.toPlainText().strip()
                    pdf.multi_cell(0, 10, notes if notes else "No Notes")
                    pdf.ln(5)

                    # Plot export logic (same as your original code)
                    if tab.xs:
                        if True in [checker.isChecked() for checker in checkboxes]:
                            for pos_index in range(4):
                                if checkboxes[pos_index].isChecked():
                                    plt.figure(figsize=(10, 6))
                                    left_data = [data["Left Sensor x (cm)"] if pos_index == 0 else
                                                 data["Left Sensor y (cm)"] if pos_index == 1 else
                                                 data["Left Sensor z (cm)"] if pos_index == 2 else
                                                 data["Left Sensor v (m/s)"]][0]
                                    right_data = [data["Right Sensor x (cm)"] if pos_index == 0 else
                                                 data["Right Sensor y (cm)"] if pos_index == 1 else
                                                 data["Right Sensor z (cm)"] if pos_index == 2 else
                                                 data["Right Sensor v (m/s)"]][0]

                                    plt.plot(tab.xs, left_data, label='Left Sensor')
                                    plt.plot(tab.xs, right_data, label='Right Sensor')

                                    plt.title(
                                        f"{'X' if pos_index == 0 else 'Y' if pos_index == 1 else 'Z' if pos_index == 2 else 'Velocity'} Plot")
                                    plt.xlabel("Time (s)")
                                    ylabel = ["X Position (cm)" if pos_index == 0 else
                                              "Y Position (cm)" if pos_index == 0 else
                                              "Z Position (cm)" if pos_index == 0 else
                                              "Speed (cm)"][0]
                                    plt.ylabel(ylabel)
                                    plt.legend()
                                    plt.grid(True)

                                    plot_filename = os.path.join(participant_folder,
                                                    f"trial_{index + 1}_plot_{['x', 'y', 'z', 'v'][pos_index]}.png")
                                    plt.savefig(plot_filename, dpi=300, bbox_inches='tight')
                                    plt.close()
                                    pdf.image(plot_filename, x=None, y=None, w=100)
                                    pdf.ln(5)

            def process_tabs():
                try:
                    for i in range(self.tab_widget.count()):
                        export_tab(i)

                    # Finalize export
                    pdf_file = os.path.join(participant_folder, f"{participant_code.text()}.pdf")
                    pdf.output(pdf_file)

                    self.setEnabled(True)
                    QMessageBox.information(self, "Success", f"Data saved in folder: {participant_folder}")
                except Exception as e:
                    QMessageBox.critical(self, "Export Error", f"An error occurred during export: {str(e)}")
                    self.setEnabled(True)

            # Process tabs and complete export
            process_tabs()
            break


app = QApplication(sys.argv)
startup = StartUp()
startup.show()

app.exec()

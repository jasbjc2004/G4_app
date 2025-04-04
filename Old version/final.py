import os
import random
import sys
import time
from math import sqrt
import pandas as pd
from fpdf import FPDF
from enum import Enum
import serial

from PySide6.QtWidgets import (
    QApplication, QVBoxLayout, QMainWindow, QWidget, QPushButton,
    QLineEdit, QLabel, QHBoxLayout, QDateEdit, QTextEdit, QMessageBox,
    QComboBox, QToolBar, QStatusBar, QTabWidget, QSizePolicy,
    QFileDialog, QDialog, QProgressDialog, QCheckBox, QDialogButtonBox,
)
from PySide6.QtGui import QAction, QPainter, QColor, QPixmap
from PySide6.QtCore import Qt, QDate, QSize, QTimer, Property, QObject, QThread, Signal
from matplotlib import pyplot as plt
from matplotlib.figure import Figure
from matplotlib.backends.backend_qt5agg import FigureCanvasQTAgg as FigureCanvas

from G4Track import get_frame_data, initialize_system, set_units, get_active_hubs, increment, close_sensor
from data_processing import calibration_to_center

from scipy import signal

MAX_TRAILS = 21

READ_SAMPLE = False
BEAUTY_SPEED = True
SERIAL_BUTTON = True

MAX_ATTEMPTS = 10

MAX_HEIGHT_NEEDED = 2 #cm

fs = 120
fc = 10

ORDER_FILTER = 2 #4
SPEED_FILTER = True


# thread setup
class Worker(QObject):
    progress = Signal(int)
    finished = Signal()

    def run(self):
        for i in range(101):
            time.sleep(0.05)
            self.progress.emit(i)
        self.finished.emit()


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
                self.mainwindow = MainWindow(self.name_input.text(), self.assessor_input.text(),
                                             self.date_input.text(), num_trials, self.notes_input.toPlainText().strip())
                self.mainwindow.show()
                self.close()
        else:
            num_trials = self.combo_box.currentData()
            self.mainwindow = MainWindow(self.name_input.text(), self.assessor_input.text(),
                                         self.date_input.text(), num_trials, self.notes_input.toPlainText().strip())
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

        self.xt = False
        self.yt = False
        self.zt = False
        self.vt = True

        self.pos_left = [0, 0, 0]
        self.pos_right = [0, 0, 0]
        self.xs = []
        self.log_left_plot = []
        self.log_right_plot = []

        self.event_log = [0]*8
        #self.event_log[-1] = 4
        self.event_8 = None

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
        self.ax.set_ylabel('Speed (m/s)')
        self.ax.grid(True)

        self.ax.set_ylim(0, 10)
        self.ax.set_xlim(0, 10)

        self.line1, = self.ax.plot([], [], lw=2, label='Left', color='green')
        self.line2, = self.ax.plot([], [], lw=2, label='Right', color='red')
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

        main_window = self.window()
        button_pressed = False
        if (isinstance(main_window, MainWindow)) and SERIAL_BUTTON and (main_window.button is not None):
            try:
                line = '1'
                while main_window.button.in_waiting > 0:
                    line = main_window.button.readline().decode('utf-8').rstrip()

                #print(f"Received from Arduino: {line}")
                if line == '0':
                    self.stop_reading()
                    main_window.tab_widget.tabBar().setEnabled(True)
                    main_window.switch_to_next_tab()
                    button_pressed = True
            except serial.SerialException as e:
                print(f"Failed to connect to COM3: {e}")

        if not READ_SAMPLE:
            main_window = self.window()

            if isinstance(main_window, MainWindow):
                if not main_window.is_connected:
                    return 0, 0, 0, button_pressed

            frame_data, active_count, data_hubs = get_frame_data(main_window.dongle_id, [main_window.hub_id])

            pos1 = frame_data.G4_sensor_per_hub[main_window.lindex].pos
            pos2 = frame_data.G4_sensor_per_hub[main_window.rindex].pos

            if tuple(pos1) == (0, 0, 0) or tuple(pos2) == (0, 0, 0):
                return elapsed_time, [x for x in self.pos_left], [x for x in self.pos_right], button_pressed

            self.pos_left = pos1
            self.pos_right = pos2

            return elapsed_time, pos1, pos2, button_pressed
        elif BEAUTY_SPEED:
            if elapsed_time < 5:
                return elapsed_time, [0, 0, -elapsed_time], [0, elapsed_time, 0], button_pressed
            elif elapsed_time < 10:
                return elapsed_time, [0, 0, -5 + (elapsed_time - 5)], [0, 5 - (elapsed_time - 5), 0], button_pressed
            elif elapsed_time < 15:
                return elapsed_time, [0, 0, -5 * (elapsed_time - 10)], [0, 5 * (elapsed_time - 10), 0], button_pressed
            elif elapsed_time < 20:
                return elapsed_time, [0, 0, -25+5 * (elapsed_time - 15)], \
                    [0, 25-5 * (elapsed_time - 15), 0], button_pressed

            return elapsed_time, [0] * 3, [0] * 3, button_pressed
        else:
            return elapsed_time, [random.randint(-20, 20), random.randint(0, 20), random.randint(-20, 0)], \
                                 [random.randint(0, 20), random.randint(0, 20), random.randint(-20, 0)], button_pressed

    def xt_plot(self):
        self.xt = True
        self.yt = False
        self.zt = False
        self.vt = False

        self.update_axis()

    def yt_plot(self):
        self.xt = False
        self.yt = True
        self.zt = False
        self.vt = False

        self.update_axis()

    def zt_plot(self):
        self.xt = False
        self.yt = False
        self.zt = True
        self.vt = False

        self.update_axis()

    def vt_plot(self):
        self.xt = False
        self.yt = False
        self.zt = False
        self.vt = True

        self.update_axis()

    def process(self, b, a):
        if SPEED_FILTER:
            output_left_speed = signal.filtfilt(b, a, [pos[3] for pos in self.log_left_plot])
            output_right_speed = signal.filtfilt(b, a, [pos[3] for pos in self.log_right_plot])
            for index in range(len(self.log_left_plot)):
                self.log_left_plot[index][3] = output_left_speed[index]
                self.log_right_plot[index][3] = output_right_speed[index]

        else:
            output_left_x = signal.filtfilt(b, a, [pos[0] for pos in self.log_left_plot])
            output_left_y = signal.filtfilt(b, a, [pos[1] for pos in self.log_left_plot])
            output_left_z = signal.filtfilt(b, a, [pos[2] for pos in self.log_left_plot])
            output_right_x = signal.filtfilt(b, a, [pos[0] for pos in self.log_right_plot])
            output_right_y = signal.filtfilt(b, a, [pos[1] for pos in self.log_right_plot])
            output_right_z = signal.filtfilt(b, a, [pos[2] for pos in self.log_right_plot])

            for index in range(len(self.log_left_plot)):
                self.log_left_plot[index][0] = output_left_x[index]
                self.log_right_plot[index][0] = output_right_x[index]
                self.log_left_plot[index][1] = output_left_y[index]
                self.log_right_plot[index][1] = output_right_y[index]
                self.log_left_plot[index][2] = output_left_z[index]
                self.log_right_plot[index][2] = output_right_z[index]

                if index > 0:
                    lpos = (self.log_left_plot[index][0], self.log_left_plot[index][1], self.log_left_plot[index][2])
                    rpos = (self.log_right_plot[index][0], self.log_right_plot[index][1], self.log_right_plot[index][2])
                    self.log_left_plot[index][3] = self.speed_calculation(lpos, self.xs[index], index, True)
                    self.log_right_plot[index][3] = self.speed_calculation(rpos, self.xs[index], index, False)

        self.update_axis()
        QMessageBox.information(self, "Info", "Finished with the processing of the data")
        main_window = self.window()
        if isinstance(main_window, MainWindow):
            main_window.process_action.setEnabled(False)

    def update_axis(self):
        main_window = self.window()

        if isinstance(main_window, MainWindow):
            if self.xt:
                self.ax.set_title(f'Trial {self.trial_number + 1} - x-coordinates')
                self.ax.set_ylabel('X-coordinates (cm)')

                self.plot_left_data = [abs(pos[0]) if main_window.set_abs_value else pos[0] for pos in self.log_left_plot]
                self.plot_right_data = [pos[0] for pos in self.log_right_plot]
            elif self.yt:
                self.ax.set_title(f'Trial {self.trial_number + 1} - y-coordinates')
                self.ax.set_ylabel('Y-coordinates (cm)')

                self.plot_left_data = [pos[1] for pos in self.log_left_plot]
                self.plot_right_data = [pos[1] for pos in self.log_right_plot]
            elif self.zt:
                self.ax.set_title(f'Trial {self.trial_number + 1} - z-coordinates')
                self.ax.set_ylabel('Z-coordinates (cm)')

                self.plot_left_data = [-pos[2] for pos in self.log_left_plot]
                self.plot_right_data = [-pos[2] for pos in self.log_right_plot]
            else:
                self.ax.set_title(f'Trial {self.trial_number + 1} - velocity plot')
                self.ax.set_ylabel('Speed (m/s)')

                self.plot_left_data = [pos[3] for pos in self.log_left_plot]
                self.plot_right_data = [pos[3] for pos in self.log_right_plot]

        self.line1.set_xdata(self.xs)
        self.line1.set_ydata(self.plot_left_data)
        self.line2.set_xdata(self.xs)
        self.line2.set_ydata(self.plot_right_data)

        if self.event_8:
            self.event_8.remove()


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

        if self.event_log[-1] != 0:
            if ((-self.log_left_plot[-1][2] < -self.log_right_plot[-1][2]) and (-self.log_left_plot[-1][2] > MAX_HEIGHT_NEEDED)) \
                    or (-self.log_right_plot[-1][2] < MAX_HEIGHT_NEEDED):
                self.event_8 = self.ax.annotate("", xy=(self.event_log[-1], self.plot_left_data[-1]), xytext=(self.event_log[-1], 0),
                                 arrowprops=dict(arrowstyle="->", color="green", lw=2))
            else:
                self.event_8 = self.ax.annotate("", xy=(self.event_log[-1], self.plot_right_data[-1]), xytext=(self.event_log[-1], 0),
                                 arrowprops=dict(arrowstyle="->", color="red", lw=2))

        # Redraw canvas
        self.canvas.draw()

    def speed_calculation(self, vector, time_val, index, left):
        if left:
            return (sqrt(((vector[0] - self.log_left_plot[index-1][0]) / (time_val - self.xs[index- 1])) ** 2 +
                 ((vector[1] - self.log_left_plot[index-1][1]) / (time_val - self.xs[index-1])) ** 2 +
                 ((vector[2] - self.log_left_plot[index-1][2]) / (time_val - self.xs[index-1])) ** 2)/100)

        return (sqrt(((vector[0] - self.log_right_plot[index-1][0]) / (time_val - self.xs[index-1])) ** 2 +
             ((vector[1] - self.log_right_plot[index-1][1]) / (time_val - self.xs[index-1])) ** 2 +
             ((vector[2] - self.log_right_plot[index-1][2]) / (time_val - self.xs[index-1])) ** 2)/100)

    def update_plot(self):
        if self.reading_active and self.trial_state == TrialState.running:
            # Read simulated data
            time_val, lpos, rpos, button_pressed = self.read_sensor_data()
            lpos, rpos = list(lpos), list(rpos)

            if len(self.log_left_plot) > 0:
                vl, vr = self.speed_calculation(lpos, time_val, len(self.log_left_plot), True), \
                    self.speed_calculation(rpos, time_val, len(self.log_left_plot), False)
            else:
                vl, vr = 0, 0

            y1, y2 = 0, 0
            main_window = self.window()
            if isinstance(main_window, MainWindow):
                if self.xt:
                    if main_window.set_abs_value:
                        y1, y2 = -lpos[0], rpos[0]
                    else:
                        y1, y2 = lpos[0], rpos[0]
                elif self.yt:
                    y1, y2 = lpos[1], rpos[1]
                elif self.zt:
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

            if button_pressed:
                self.event_log[-1] = time_val
                if ((-lpos[2] < -rpos[2]) and (-lpos[2] > MAX_HEIGHT_NEEDED)) or (-rpos[2] < MAX_HEIGHT_NEEDED):
                    self.event_8 = self.ax.annotate("", xy=(time_val, y1), xytext=(time_val, 0),
                                     arrowprops=dict(arrowstyle="->", color="green", lw=2))
                else:
                    self.event_8 = self.ax.annotate("", xy=(time_val, y2), xytext=(time_val, 0),
                                     arrowprops=dict(arrowstyle="->", color="red", lw=2))

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


class Help(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Help")
        self.setGeometry(200, 200, 400, 400)

        self.setWindowFlags(Qt.Window | Qt.WindowStaysOnTopHint)
        self.setModal(True)

        layout = QVBoxLayout()

        image_label = QLabel()
        file_directory = (os.path.dirname(os.path.abspath(__file__)))
        image_path = (os.path.join(file_directory, "help.png"))
        pixmap = QPixmap(image_path)
        scaled_pixmap = pixmap.scaled(500, 500, Qt.KeepAspectRatio, Qt.SmoothTransformation)
        image_label.setPixmap(scaled_pixmap)
        layout.addWidget(image_label)

        text_label = QLabel()
        text_label.setText(
            "Introduction: \n "
            " The front of the source has to point to the child. If done correctly, \n"
            " the x-axis on the source face to the child. \n"
            "For the data on the plot: \n"
            " The x-axis lays horizontal on the table. \n"
            " The y-axis is pointing to the source on the table.\n"
            " The z-axis is pointing to the roof.\n"
            " The center of this axis is in the middle of both hands")
        text_label.setWordWrap(True)  # Enable text wrapping
        text_label.setAlignment(Qt.AlignLeft | Qt.AlignTop)
        layout.addWidget(text_label)

        self.setLayout(layout)


# MainWindow
class MainWindow(QMainWindow):
    def __init__(self, id, asses, date, num_trials, notes):
        super().__init__()

        self.button = None
        if SERIAL_BUTTON:
            available_ports = ['COM%s' % (i + 1) for i in range(12)]
            found_port = False

            for port in available_ports:
                try:
                    if not found_port:
                        ser_temp = serial.Serial(port, 9600, timeout=1)

                        line = ''
                        while self.button.in_waiting > 0:
                            line = self.button.readline().decode('utf-8').rstrip()

                        # print(f"Received from Arduino: {line}")
                        if line == '1':
                            self.button = ser_temp
                            found_port = True

                except serial.SerialException as e:
                    print(f"Failed to connect to {port}: {e}")

        self.setWindowTitle("Sensors")

        self.first_time = True
        self.is_connected = False
        self.dongle_id = None
        self.hub_id = None
        self.lindex = None
        self.rindex = None
        self.reading_active = False
        self.set_abs_value = False
        self.set_automatic = False
        self.progress_dialog = None

        self.resize(800, 600)
        self.setup(num_trials)
        self.id_part = id
        self.assessor = asses
        self.date = date
        self.num_trials = num_trials
        self.notes = notes

        w = fc / (fs / 2)
        self.b, self.a = signal.butter(ORDER_FILTER, w, 'low')

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

        settings_menu = menu_bar.addMenu("Settings")
        absx_action = settings_menu.addAction("Set absolute values to x-axis")
        absx_action.setCheckable(True)
        absx_action.triggered.connect(lambda: self.plot_absolute_x(absx_action))
        self.disconnect_action = settings_menu.addAction("Disconnect")
        self.disconnect_action.setEnabled(False)
        self.disconnect_action.triggered.connect(lambda: self.disconnecting() )

        switch_action = settings_menu.addAction("Switch tab automatically")
        switch_action.setCheckable(True)
        switch_action.triggered.connect(lambda: self.set_automatic_tab(switch_action))

        help_menu = menu_bar.addMenu("&Help")
        expl_action = help_menu.addAction("Introduction")
        expl_action.triggered.connect(lambda: self.create_help())

        menu_bar.setNativeMenuBar(False)

    def create_help(self):
        popup = Help(self)
        popup.show()

    def setup_toolbar(self):
        toolbar = QToolBar("My main toolbar")
        toolbar.setIconSize(QSize(16, 16))
        self.addToolBar(toolbar)
        toolbar.setMovable(False)

        self.connection_action = QAction("Connect", self)
        if READ_SAMPLE:
            self.connection_action.setEnabled(False)
        self.connection_action.setStatusTip("Connect and calibrate the sensor")
        #self.connection_action.triggered.connect(lambda: self.show_progress_dialog("Connecting...", 100))
        self.connection_action.triggered.connect(lambda: self.connecting())
        toolbar.addAction(self.connection_action)

        self.calibrate_action = QAction("Calibrate", self)
        self.calibrate_action.setEnabled(False)
        self.calibrate_action.setStatusTip("Calibrate the sensor")
        self.calibrate_action.triggered.connect(lambda: self.calibration())
        #self.calibrate_action.triggered.connect(lambda: self.show_progress_dialog("Calibrating...", 100))
        toolbar.addAction(self.calibrate_action)

        toolbar.addSeparator()

        self.start_action = QAction("Start trial", self)
        self.start_action.setStatusTip("Start the current trial")
        self.start_action.triggered.connect(lambda: self.start_current_reading())

        self.stop_action = QAction("Stop trial", self)
        self.stop_action.setStatusTip("Stop the current trial")
        self.stop_action.setEnabled(False)
        self.stop_action.triggered.connect(lambda: self.stop_current_reading())
        self.stop_action.triggered.connect(lambda: self.switch_to_next_tab())

        self.reset_action = QAction("Overwrite trial", self)
        self.reset_action.setStatusTip("Overwrite the current trial")
        self.reset_action.setEnabled(False)
        self.reset_action.triggered.connect(lambda: self.reset_current_reading())

        toolbar.addActions([self.start_action, self.stop_action, self.reset_action])

        toolbar.addSeparator()

        self.process_action = QAction("Process trial", self)
        self.process_action.setStatusTip("Process the current trial")
        self.process_action.setEnabled(False)
        self.process_action.triggered.connect(lambda: self.process_tab())
        toolbar.addAction(self.process_action)

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
            self.process_action.setEnabled(False)
            return
        if tab.trial_state == TrialState.not_started:
            self.start_action.setEnabled(True)
            self.stop_action.setEnabled(False)
            self.reset_action.setEnabled(False)
            self.process_action.setEnabled(False)
        elif tab.trial_state == TrialState.running:
            self.start_action.setEnabled(False)
            self.stop_action.setEnabled(True)
            self.reset_action.setEnabled(False)
            self.process_action.setEnabled(False)
        elif tab.trial_state == TrialState.completed:
            self.start_action.setEnabled(False)
            self.stop_action.setEnabled(False)
            self.reset_action.setEnabled(True)
            self.process_action.setEnabled(True)

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
            ret = QMessageBox.warning(self, "Warning",
                                      f"Do you really want to reset the data for trial {self.tab_widget.currentIndex()+1}?",
                                      QMessageBox.Yes | QMessageBox.Cancel)
            if ret == QMessageBox.Yes:
                tab.reset_reading()
                self.update_toolbar()

    def switch_to_next_tab(self,):
        if self.set_automatic:
            current_index = self.tab_widget.currentIndex()
            total_tabs = self.tab_widget.count()

            if current_index < total_tabs:
                next_index = (current_index + 1)
                self.tab_widget.setCurrentIndex(next_index)

    def connecting(self):
        QMessageBox.information(self, "Info", "Started to connect. Please wait a bit.")

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
        #increment(self.dongle_id, self.hub_id, (self.lindex, self.rindex), (0.1, 0.1))

        if not self.calibration_status:
            QMessageBox.critical(self, "Warning", "Calibration did not succeed!")

        self.is_connected = True
        self.connection_action.setEnabled(False)  # Disable connect button after successful connection
        self.calibrate_action.setEnabled(True)
        self.disconnect_action.setEnabled(True)
        self.statusBar().showMessage("Successfully connected to sensors")
        QMessageBox.information(self, "Success", "Successfully connected to sensors!")
        self.status_widget.set_status("connected")
        self.update_toolbar()

    def disconnecting(self):
        self.is_connected = False
        close_sensor()
        self.connection_action.setEnabled(True)
        self.calibrate_action.setEnabled(False)
        self.disconnect_action.setEnabled(False)
        self.statusBar().showMessage("Successfully disconnected to sensors")
        self.status_widget.set_status("disconnected")
        self.update_toolbar()

    def calibration(self):
        ret = QMessageBox.warning(self, "Warning",
                                  "Do you really want to calibrate again?",
                                  QMessageBox.Yes | QMessageBox.Cancel)
        if ret == QMessageBox.Yes:
            QMessageBox.information(self, "Info", "Started to calibrate. "
                                                  "Please wait a bit and keep the sensors at a fixed position.")
            self.hub_id, self.lindex, self.rindex, self.calibration_status = calibration_to_center(self.dongle_id)

    def show_progress_dialog(self, task_name, duration=100):

        progress_dialog = QProgressDialog(task_name, "Cancel", 0, duration, self)
        progress_dialog.setWindowModality(Qt.WindowModality.WindowModal)
        progress_dialog.setAutoClose(False)
        progress_dialog.setValue(0)

        worker = Worker()
        worker.progress.connect(progress_dialog.setValue)
        worker.finished.connect(progress_dialog.accept)

        worker_thread = QThread()
        worker.moveToThread(worker_thread)
        worker_thread.started.connect(worker.run)
        worker_thread.start()

        progress_dialog.exec()

        worker_thread.quit()
        worker_thread.wait()

    def xt_plot(self):
        self.get_tab().xt_plot()

    def yt_plot(self):
        self.get_tab().yt_plot()

    def zt_plot(self):
        self.get_tab().zt_plot()

    def vt_plot(self):
        self.get_tab().vt_plot()

    def process_tab(self):
        self.get_tab().process(self.b, self.a)

    def plot_absolute_x(self, button):
        if button.isChecked():
            self.set_abs_value = True
        else:
            self.set_abs_value = False
        self.get_tab().update_axis()

    def set_automatic_tab(self,button):
        if button.isChecked():
            self.set_automatic = True
        else:
            self.set_automatic = False

    def closeEvent(self, event):
        ret = QMessageBox.warning(self, "Warning",
                                  "Are you sure you want to quit the application?",
                                  QMessageBox.Yes | QMessageBox.Cancel)
        if ret == QMessageBox.Yes:
            close_sensor()
            event.accept()
        else:
            event.ignore()

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
                QCheckBox("The x-plot"),
                QCheckBox("The y-plot"),
                QCheckBox("The z-plot"),
                QCheckBox("The v-plot")
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

            pdf.set_font("Arial", style="BU", size=16)
            pdf.cell(0, 10, f"Participant {self.id_part} by assessor {self.assessor} "
                            f"on {self.date}" if self.id_part and self.assessor else
                            f"Participant {self.id_part} on {self.date}" if self.id_part else
                            f"Participant Unknown on {self.date}", ln=True)
            pdf.set_font("Arial", size=12)
            pdf.cell(0, 8, f"Total trials: {self.num_trials}", ln=True)
            pdf.multi_cell(0, 8, self.notes if self.notes else "No Additional Notes")

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

                    pdf.set_font("Arial", style="B", size=14)
                    pdf.cell(0, 10, f"Trial {index + 1}", ln=True)
                    pdf.set_font("Arial", size=12)
                    notes = tab.notes_input.toPlainText().strip()
                    pdf.multi_cell(0, 10, notes if notes else "No Notes")
                    pdf.ln(5)

                    if tab.xs:
                        for pos_index in [index for index in range(len(checkboxes)) if checkboxes[index].isChecked()]:
                            plt.figure(figsize=(10, 6))
                            left_data = [data["Left Sensor x (cm)"] if pos_index == 0 else
                                         data["Left Sensor y (cm)"] if pos_index == 1 else
                                         data["Left Sensor z (cm)"] if pos_index == 2 else
                                         data["Left Sensor v (m/s)"]][0]
                            right_data = [data["Right Sensor x (cm)"] if pos_index == 0 else
                                         data["Right Sensor y (cm)"] if pos_index == 1 else
                                         data["Right Sensor z (cm)"] if pos_index == 2 else
                                         data["Right Sensor v (m/s)"]][0]

                            plt.plot(tab.xs, left_data, label='Left Sensor', color='green')
                            plt.plot(tab.xs, right_data, label='Right Sensor', color='red')

                            plt.title(
                                f"{'X' if pos_index == 0 else 'Y' if pos_index == 1 else 'Z' if pos_index == 2 else 'Velocity'} Plot")
                            plt.xlabel("Time (s)")
                            ylabel = ["X Position (cm)", "Y Position (cm)", "Z Position (cm)", "Speed (m/s)"][pos_index]
                            plt.ylabel(ylabel)
                            plt.legend()
                            plt.grid(True)

                            plot_filename = os.path.join(participant_folder,
                                            f"trial_{index + 1}_plot_{['x', 'y', 'z', 'v'][pos_index]}.png")
                            plt.savefig(plot_filename, dpi=300, bbox_inches='tight')
                            plt.close()
                            pdf.image(plot_filename, x=None, y=None, w=100)
                            pdf.ln(5)

            #self.show_progress_dialog("Exporting to Excel...", 300)

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

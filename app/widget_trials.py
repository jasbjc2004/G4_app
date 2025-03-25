import random
import time
from math import sqrt
import pygame
from enum import Enum
import serial
import serial.tools.list_ports
import threading

from PySide6.QtGui import QColor, QTextCursor
from PySide6.QtWidgets import (
    QVBoxLayout, QWidget, QLabel, QHBoxLayout,
    QTextEdit, QMessageBox, QSizePolicy, QComboBox
)
from PySide6.QtCore import QTimer, QThread, Qt

from matplotlib.figure import Figure
from matplotlib.backends.backend_qt5agg import FigureCanvasQTAgg as FigureCanvas

from data_processing import calculate_boxhand
from sensor_G4Track import get_frame_data

from scipy import signal

from window_main_plot import MainWindow
from constants import READ_SAMPLE, BEAUTY_SPEED, SERIAL_BUTTON, MAX_HEIGHT_NEEDED, SPEED_FILTER, SENSORS_USED, fs


class TrialState(Enum):
    not_started = 0
    running = 1
    completed = 2


class TrailTab(QWidget):
    def __init__(self, trail_number, parent=None):
        super().__init__(parent)
        self.trial_number = trail_number
        self.reading_active = False
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
        self.button_pressed = False

        self.event_log = [0] * 6

        self.plot_left_data = []
        self.plot_right_data = []

        self.sound = None

        self.data_thread = ReadThread(self)

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

        self.notes_score_widget = QWidget()
        self.notes_score_layout = QVBoxLayout(self.notes_score_widget)

        self.score_widget = QWidget()
        self.score_layout = QHBoxLayout(self.score_widget)

        self.score = QComboBox()
        self.score.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        self.score.setMinimumWidth(100)
        score_label = QLabel("Trial score: ")
        self.score.addItems([str(i) for i in range(0,4)])

        self.score_layout.addWidget(score_label)
        self.score_layout.addWidget(self.score)
        self.score_layout.addStretch(1)

        self.notes_score_layout.addWidget(self.score_widget)

        self.notes_widget = QWidget()
        self.notes_layout = QVBoxLayout(self.notes_widget)

        self.notes_label = QLabel("Notes:")
        self.notes_input = QTextEdit()
        self.notes_layout.addWidget(self.notes_label)
        self.notes_layout.addWidget(self.notes_input)

        self.notes_score_layout.addWidget(self.notes_widget)

        self.layout_tab.addWidget(self.notes_score_widget)
        self.layout_tab.setStretch(1, 1)

        self.animation_widget.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)

        self.canvas.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)

        self.timer_plot = QTimer(self)
        self.timer_plot.timeout.connect(self.update_plot)
        self.timer_plot.setInterval(20)

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

        if self.vt:
            self.ax.set_ylim(0, 2)
        else:
            self.ax.set_ylim(0, 10)
        self.ax.set_xlim(0, 10)

        self.line1, = self.ax.plot([], [], lw=2, label='Left', color='green')
        self.line2, = self.ax.plot([], [], lw=2, label='Right', color='red')
        self.ax.legend()

        self.layout_tab.addWidget(self.canvas)
        self.figure.tight_layout()

    def start_reading(self):
        if self.trial_state == TrialState.not_started:
            self.reading_active = True
            self.trial_state = TrialState.running
            self.data_thread.start()
            self.timer_plot.start()
            main_window = self.window()
            if isinstance(main_window, MainWindow):
                main_window.update_toolbar()

    def stop_reading(self):
        if self.trial_state == TrialState.running:
            self.reading_active = False
            self.data_thread.stop()
            self.timer_plot.stop()
            self.trial_state = TrialState.completed
            main_window = self.window()
            if isinstance(main_window, MainWindow):
                main_window.update_toolbar()

            self.update_plot()

    def reset_reading(self):
        if self.trial_state == TrialState.completed:
            if self.vt:
                self.ax.set_ylim(0, 2)
            else:
                self.ax.set_ylim(0, 10)
            self.ax.set_xlim(0, 10)

            self.pos_left = (0, 0, 0)
            self.pos_right = (0, 0, 0)
            self.xs = []
            self.log_left_plot = []
            self.log_right_plot = []

            self.plot_left_data = []
            self.plot_right_data = []

            self.line1.set_data([], [])
            self.line2.set_data([], [])

            self.event_log = [0] * 6
            self.button_pressed = False

            self.canvas.draw()

            self.remove_added_text()

            self.trial_state = TrialState.not_started
            main_window = self.window()
            if isinstance(main_window, MainWindow):
                main_window.update_toolbar()

    def remove_added_text(self):
        cursor = self.notes_input.textCursor()
        cursor.beginEditBlock()

        cursor.movePosition(QTextCursor.Start)

        while not cursor.atEnd():
            cursor.movePosition(QTextCursor.Right, QTextCursor.KeepAnchor)

            char_color = cursor.charFormat()
            if char_color.foreground().color() == QColor(Qt.red):
                cursor.removeSelectedText()
            else:
                cursor.movePosition(QTextCursor.Right)

        cursor.endEditBlock()
        self.notes_input.setTextCursor(cursor)

    def xt_plot(self):
        self.xt = True
        self.yt = False
        self.zt = False
        self.vt = False

        self.update_plot()

    def yt_plot(self):
        self.xt = False
        self.yt = True
        self.zt = False
        self.vt = False

        self.update_plot()

    def zt_plot(self):
        self.xt = False
        self.yt = False
        self.zt = True
        self.vt = False

        self.update_plot()

    def vt_plot(self):
        self.xt = False
        self.yt = False
        self.zt = False
        self.vt = True

        self.update_plot()

    def process(self, b, a):
        if SPEED_FILTER:
            output_left_speed = signal.filtfilt(b, a, [pos[3] for pos in self.log_left_plot])
            output_right_speed = signal.filtfilt(b, a, [pos[3] for pos in self.log_right_plot])
            for index in range(len(self.log_left_plot)):
                self.log_left_plot[index] = tuple(self.log_left_plot[index][0:3]) + (output_left_speed[index],)
                self.log_right_plot[index] = tuple(self.log_right_plot[index][0:3]) + (output_right_speed[index],)

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

        self.update_plot()
        QMessageBox.information(self, "Info", "Finished with the processing of the data")
        main_window = self.window()
        if isinstance(main_window, MainWindow):
            main_window.process_action.setEnabled(False)

    def update_plot(self):
        main_window = self.window()

        if isinstance(main_window, MainWindow):
            if self.xt:
                self.ax.set_title(f'Trial {self.trial_number + 1} - x-coordinates')
                self.ax.set_ylabel('X-coordinates (cm)')

                self.plot_left_data = [abs(pos[0]) if main_window.set_abs_value else pos[0] for pos in
                                       self.log_left_plot]
                self.plot_right_data = [pos[0] for pos in self.log_right_plot]
            elif self.yt:
                self.ax.set_title(f'Trial {self.trial_number + 1} - y-coordinates')
                self.ax.set_ylabel('Y-coordinates (cm)')

                self.plot_left_data = [pos[1] for pos in self.log_left_plot]
                self.plot_right_data = [pos[1] for pos in self.log_right_plot]
            elif self.zt:
                self.ax.set_title(f'Trial {self.trial_number + 1} - z-coordinates')
                self.ax.set_ylabel('Z-coordinates (cm)')

                self.plot_left_data = [pos[2] for pos in self.log_left_plot]
                self.plot_right_data = [pos[2] for pos in self.log_right_plot]
            else:
                self.ax.set_title(f'Trial {self.trial_number + 1} - velocity plot')
                self.ax.set_ylabel('Speed (m/s)')

                self.plot_left_data = [pos[3] for pos in self.log_left_plot]
                self.plot_right_data = [pos[3] for pos in self.log_right_plot]

        self.line1.set_xdata(self.xs)
        self.line1.set_ydata(self.plot_left_data)
        self.line2.set_xdata(self.xs)
        self.line2.set_ydata(self.plot_right_data)

        self.ax.set_xlim(0, 10)
        if self.vt:
            self.ax.set_ylim(0, 2)
        else:
            self.ax.set_ylim(0, 10)

        if self.xs:
            self.ax.set_xlim(0, self.xs[-1] + 1)

            max_y = max(max(self.plot_left_data[-200:], default=1),
                        max(self.plot_right_data[-200:], default=1)) * 1.1
            min_y = min(min(self.plot_left_data[-200:], default=1),
                        min(self.plot_right_data[-200:], default=1)) * 1.1
            if max_y < 10:
                if self.vt:
                    max_y = 2
                else:
                    max_y = 10
            if min_y > 0 or main_window.set_abs_value:
                min_y = 0

            self.ax.set_ylim(min_y, max_y)

        if self.event_log[-1] == 0 and self.button_pressed:
            self.event_log[-1] = self.xs[-1]
            boxhand = calculate_boxhand(self.log_left_plot, self.log_right_plot)
            self.notes_input.setTextColor(QColor(Qt.red))
            if boxhand == 0:
                self.notes_input.append('Left hand is boxhand', )
            elif boxhand == 1:
                self.notes_input.append('Reft hand is boxhand')
            elif boxhand == 2 or boxhand == 3:
                self.notes_input.append('Both hands as boxhand')
            elif boxhand == 4:
                self.notes_input.append('Left hand is not used')
            elif boxhand == 5:
                self.notes_input.append('Right hand is not used')
            self.notes_input.setTextColor(QColor(Qt.black))

        self.canvas.draw()

        if self.button_pressed:
            self.stop_reading()
            main_window.tab_widget.tabBar().setEnabled(True)
            main_window.switch_to_next_tab()

    def speed_calculation(self, vector, time_val, index, left):
        if len(self.xs) <= 1 or len(self.log_right_plot) <= 1 or len(self.log_left_plot) <= 1:
            return 0

        if left:
            return (sqrt(((vector[0] - self.log_left_plot[index - 1][0]) * fs) ** 2 +
                         ((vector[1] - self.log_left_plot[index - 1][1]) * fs) ** 2 +
                         ((vector[2] - self.log_left_plot[index - 1][2]) * fs) ** 2) / 100)

        return (sqrt(((vector[0] - self.log_right_plot[index - 1][0]) * fs) ** 2 +
                     ((vector[1] - self.log_right_plot[index - 1][1]) * fs) ** 2 +
                     ((vector[2] - self.log_right_plot[index - 1][2]) * fs) ** 2) / 100)

    """
    def update_plot(self):
        if self.reading_active and self.trial_state == TrialState.running:
            lpos, rpos = self.log_left_plot

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
                    if self.vt:
                        max_y = 2
                    else:
                        max_y = 10
                if min_y > 0 or main_window.set_abs_value:
                    min_y = 0

                self.ax.set_ylim(min_y, max_y)

            # Redraw canvas
            self.canvas.draw()

            if button_pressed:
                self.play_music()
    """

    def play_music(self):
        main_window = self.window()
        if isinstance(main_window, MainWindow) and self.sound is None:
            num_sound = len(main_window.sound)
            random_sound = random.randint(0, num_sound - 1)

            self.sound = main_window.sound[random_sound]

        self.sound.play()
        timer = threading.Timer(2.0, self.stop_music)
        timer.start()

    def stop_music(self):
        pygame.mixer.stop()


class ReadThread(QThread):
    def __init__(self, parent):
        super().__init__(parent)

        self.start_time = None

    def run(self):
        self.stop_read = False
        if not self.start_time:
            self.start_time = time.time()

        while not self.stop_read:
            try:
                self.read_sensor_data()
            except Exception as e:
                print(f"Error in read_sensor_data: {e}")
                time.sleep(0.5)

            time.sleep(0.002)

    def stop(self):
        self.stop_read = True
        self.start_time = None

    def read_sensor_data(self):
        tab = self.parent()
        if tab and isinstance(tab, TrailTab):
            elapsed_time = time.time() - self.start_time

            main_window = tab.window()
            if (isinstance(main_window, MainWindow)) and SERIAL_BUTTON and (
                    main_window.button_trigger is not None):
                try:
                    line = '1'
                    while main_window.button_trigger.in_waiting > 0:
                        line = main_window.button_trigger.readline().decode('utf-8').rstrip()

                    # print(f"Received from Arduino: {line}")
                    if line == '0':
                        self.stop()
                        tab.button_pressed = True
                except serial.SerialException as e:
                    print(f"Failed to connect to COM3: {e}")

            if not READ_SAMPLE:
                main_window = tab.window()

                if isinstance(main_window, MainWindow):
                    if not main_window.is_connected:
                        tab.xs.append(len(tab.xs) / fs)
                        tab.log_left_plot.append((0, 0, 0, 0))
                        tab.log_right_plot.append((0, 0, 0, 0))

                frame_data, active_count, data_hubs = get_frame_data(main_window.dongle_id,
                                                                     [main_window.hub_id])

                if (active_count, data_hubs) == (1, 1):
                    time_now = len(tab.xs) / fs
                    pos1 = tuple(frame_data.G4_sensor_per_hub[main_window.lindex].pos)
                    pos1 = tuple([pos1[i] if i != 2 else -pos1[i] for i in range(3)])
                    pos1 += (tab.speed_calculation(pos1, time_now, len(tab.xs) - 1, True),)

                    pos2 = tuple(frame_data.G4_sensor_per_hub[main_window.rindex].pos)
                    pos2 = tuple([pos2[i] if i != 2 else -pos2[i] for i in range(3)])
                    pos2 += (tab.speed_calculation(pos2, time_now, len(tab.xs) - 1, False),)

                    tab.xs.append(len(tab.xs) / fs)
                    tab.log_left_plot.append(pos1)
                    tab.log_right_plot.append(pos2)

            elif BEAUTY_SPEED:
                elapsed_time = len(tab.xs) * 0.002
                tab.xs.append(elapsed_time)

                if elapsed_time < 5:
                    pos1 = (0, 0, -elapsed_time,)
                    pos2 = (0, elapsed_time, 0,)

                elif elapsed_time < 10:
                    pos1 = (0, 0, -5 + (elapsed_time - 5),)
                    pos2 = (0, 5 - (elapsed_time - 5), 0,)

                elif elapsed_time < 15:
                    pos1 = (0, 0, -5 * (elapsed_time - 10),)
                    pos2 = (0, 5 * (elapsed_time - 10), 0,)

                elif elapsed_time < 20:
                    pos1 = (0, 0, -25 + 5 * (elapsed_time - 15),)
                    pos2 = (0, 25 - 5 * (elapsed_time - 15), 0,)

                else:
                    pos1 = (0, 0, 0,)
                    pos2 = (0, 0, 0,)

                tab.log_left_plot.append(
                    pos1 + (tab.speed_calculation(pos1, tab.xs[-1], len(tab.xs) - 1, True),))
                tab.log_right_plot.append(
                    pos2 + (tab.speed_calculation(pos2, tab.xs[-1], len(tab.xs) - 1, False),))

            else:
                pos1 = (random.randint(-20, 20), random.randint(0, 20), random.randint(-20, 0))
                pos2 = (random.randint(-20, 20), random.randint(0, 20), random.randint(-20, 0))

                tab.xs.append(elapsed_time)
                tab.log_left_plot.append(
                    pos1 + (tab.speed_calculation(pos1, tab.xs[-1], len(tab.xs) - 1, True),))
                tab.log_right_plot.append(
                    pos2 + (tab.speed_calculation(pos2, tab.xs[-1], len(tab.xs) - 1, False),))

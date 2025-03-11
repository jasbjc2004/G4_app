import random
import time
from math import sqrt
import pygame
from enum import Enum
import serial
import serial.tools.list_ports


from PySide6.QtWidgets import (
    QVBoxLayout, QWidget,  QLabel, QHBoxLayout,
    QTextEdit, QMessageBox, QSizePolicy
)
from PySide6.QtCore import QTimer

from matplotlib.figure import Figure
from matplotlib.backends.backend_qt5agg import FigureCanvasQTAgg as FigureCanvas

from sensor_G4Track import get_frame_data

from scipy import signal

from window_main_plot import MainWindow

READ_SAMPLE = True
BEAUTY_SPEED = True
SERIAL_BUTTON = True

MAX_HEIGHT_NEEDED = 2  # cm

SPEED_FILTER = True

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

        self.event_log = [0] * 8
        # self.event_log[-1] = 4
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
            if self.vt:
                self.ax.set_ylim(0, 2)
            else:
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
        if (isinstance(main_window, MainWindow)) and SERIAL_BUTTON and (main_window.button_trigger is not None):
            try:
                line = '1'
                while main_window.button_trigger.in_waiting > 0:
                    line = main_window.button_trigger.readline().decode('utf-8').rstrip()

                # print(f"Received from Arduino: {line}")
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
                return elapsed_time, [0, 0, -25 + 5 * (elapsed_time - 15)], \
                    [0, 25 - 5 * (elapsed_time - 15), 0], button_pressed

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
        if self.vt:
            self.ax.set_ylim(0, 2)
        else:
            self.ax.set_ylim(0, 10)
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

        if self.event_log[-1] != 0:
            if ((-self.log_left_plot[-1][2] < -self.log_right_plot[-1][2]) and (
                    -self.log_left_plot[-1][2] > MAX_HEIGHT_NEEDED)) \
                    or (-self.log_right_plot[-1][2] < MAX_HEIGHT_NEEDED):
                self.event_8 = self.ax.annotate("", xy=(self.event_log[-1], self.plot_left_data[-1]),
                                                xytext=(self.event_log[-1], 0),
                                                arrowprops=dict(arrowstyle="->", color="green", lw=2))
            else:
                self.event_8 = self.ax.annotate("", xy=(self.event_log[-1], self.plot_right_data[-1]),
                                                xytext=(self.event_log[-1], 0),
                                                arrowprops=dict(arrowstyle="->", color="red", lw=2))

        # Redraw canvas
        self.canvas.draw()

    def speed_calculation(self, vector, time_val, index, left):
        if left:
            return (sqrt(((vector[0] - self.log_left_plot[index - 1][0]) / (time_val - self.xs[index - 1])) ** 2 +
                         ((vector[1] - self.log_left_plot[index - 1][1]) / (time_val - self.xs[index - 1])) ** 2 +
                         ((vector[2] - self.log_left_plot[index - 1][2]) / (time_val - self.xs[index - 1])) ** 2) / 100)

        return (sqrt(((vector[0] - self.log_right_plot[index - 1][0]) / (time_val - self.xs[index - 1])) ** 2 +
                     ((vector[1] - self.log_right_plot[index - 1][1]) / (time_val - self.xs[index - 1])) ** 2 +
                     ((vector[2] - self.log_right_plot[index - 1][2]) / (time_val - self.xs[index - 1])) ** 2) / 100)

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

                pygame.mixer.init()
                if self.trial_number < 5:
                    sound = pygame.mixer.Sound('NEEDED/MUSIC/Bumba.mp3')
                else:
                    sound = pygame.mixer.Sound('NEEDED/MUSIC/applause.mp3')
                sound.play()
                time.sleep(1.5)
                pygame.mixer.quit()

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


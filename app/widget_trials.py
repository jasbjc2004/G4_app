import random
from math import sqrt

import matplotlib.collections
import pygame
from enum import Enum
import threading

from PySide6.QtGui import QColor, QTextCursor
from PySide6.QtWidgets import (
    QVBoxLayout, QWidget, QLabel, QHBoxLayout,
    QTextEdit, QMessageBox, QSizePolicy, QComboBox
)
from PySide6.QtCore import QTimer, Qt

from matplotlib.figure import Figure
from matplotlib.lines import Line2D
from matplotlib.backends.backend_qt5agg import FigureCanvasQTAgg as FigureCanvas

from data_processing import calculate_boxhand, calculate_e6, calculate_events, calculate_extra_parameters, \
    calculate_position_events, predict_score

from scipy import signal

from thread_reading import ReadThread
from window_main_plot import MainWindow
from widget_settings import manage_settings
from constants import READ_SAMPLE, BEAUTY_SPEED, COLORS


class TrialState(Enum):
    """
    All the possibles states the trial can be in
    """
    not_started = 0
    running = 1
    completed = 2


def colors_to_hex(colors):
    hex_colors = []
    for color in colors:
        for (hex_c, name) in COLORS:
            if name == color: hex_colors.append(hex_c)
    return hex_colors


class TrailTab(QWidget):
    """
    Needed to show the plot and all the information related to a trial
    """
    def __init__(self, trail_number, parent: MainWindow):
        NUMBER_EVENTS = manage_settings.get("Events", "NUMBER_EVENTS")

        super().__init__(parent)
        self.case_status = -1
        self.scatter = []
        self.trial_number = trail_number
        self.reading_active = False
        self.trial_state = TrialState.not_started

        self.xt = False
        self.yt = False
        self.zt = False
        self.vt = True

        self.change_starting_point = False
        self.change_end_point = False
        self.change_events = False

        self.original_data_file = False

        self.pos_left = [0, 0, 0]
        self.pos_right = [0, 0, 0]
        self.xs = []
        self.log_left = []
        self.log_right = []
        self.button_pressed = False

        self.first_event_guess = True
        self.first_process = True

        self.event_log = [0] * NUMBER_EVENTS
        self.event_old_log = [0] * NUMBER_EVENTS
        self.event_position = [None] * NUMBER_EVENTS
        self.extra_parameters_bim = []
        self.extra_parameters_uni = []

        self.plot_left_data = []
        self.plot_right_data = []

        self.sound = None

        self.data_thread = ReadThread(self)

        self.setup()

    def setup(self):
        self.layout_tab = QHBoxLayout()
        self.setLayout(self.layout_tab)

        self.setup_plot()

        self.notes_score_widget = QWidget()
        self.notes_score_layout = QVBoxLayout(self.notes_score_widget)

        self.score_widget = QWidget()
        self.score_widget.setMaximumWidth(300)
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
        self.notes_input.textChanged.connect(self.signal_text_changed)
        self.notes_layout.addWidget(self.notes_label)
        self.notes_layout.addWidget(self.notes_input)

        self.notes_score_layout.addWidget(self.notes_widget)

        self.layout_tab.addWidget(self.notes_score_widget, 1)
        self.layout_tab.setStretch(1, 1)

        self.canvas.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)

        self.timer_plot = QTimer(self)
        self.timer_plot.timeout.connect(self.update_plot)
        self.timer_plot.setInterval(20)

    def signal_text_changed(self):
        main_window = self.window()
        if isinstance(main_window, MainWindow):
            main_window.signal_text_changed()

    def setup_plot(self):
        COLORS_EVENT = manage_settings.get("Events", "COLORS_EVENT")
        colors_hex = colors_to_hex(COLORS_EVENT)
        LABEL_EVENT = manage_settings.get("Events", "LABEL_EVENT")
        NUMBER_EVENTS = manage_settings.get("Events", "NUMBER_EVENTS")

        self.figure = Figure(constrained_layout=True)
        self.canvas = FigureCanvas(self.figure)

        self.canvas.mpl_connect('pick_event', self.pick_a_point)
        self.canvas.mpl_connect('motion_notify_event', self.track_mouse)
        self.canvas.mpl_connect('button_release_event', self.releasing_event)

        self.move_event = None
        self.moving_event_index = None

        self.canvas.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self.ax = self.figure.add_subplot(111)

        self.ax.set_title(f'Trial {self.trial_number + 1} - velocity plot')
        self.ax.set_xlabel('Time (s)')
        self.ax.set_ylabel('Speed (m/s)')
        self.ax.grid(True)

        if self.vt:
            self.ax.set_ylim(0, 3)
        else:
            self.ax.set_ylim(0, 10)
        self.ax.set_xlim(0, 10)

        self.line1, = self.ax.plot([], [], lw=2, label='Left', color='green', zorder=5, picker=5)
        self.line2, = self.ax.plot([], [], lw=2, label='Right', color='red', zorder=5, picker=5)
        legend_hands = self.ax.legend(handles=[self.line1, self.line2])

        self.ax.add_artist(legend_hands)

        self.mouse_marker = Line2D([0], [0], color='black', marker='x', markersize=8, visible=False)
        self.ax.add_line(self.mouse_marker)

        legend_elements = [None]*NUMBER_EVENTS
        for i in range(NUMBER_EVENTS):
            legend_elements[i] = Line2D([0], [0], marker='o', color='w', markerfacecolor=colors_hex[i],
                                        markersize=10, label=LABEL_EVENT[i])

        # Place legend below the plot
        self.ax.legend(handles=legend_elements, loc='upper center',
                  bbox_to_anchor=(0.5, -0.12), ncol=6)

        self.layout_tab.addWidget(self.canvas, 2)
        self.figure.tight_layout()

    def pick_a_point(self, event):
        """
        Take the coordinates of the selected point or move the scatter-events if selected
        :param event: not the same as the events from the scatter, python-event
        """
        if self.change_events and isinstance(event.artist, matplotlib.collections.PathCollection):
            for i, point in enumerate(self.scatter):
                if event.artist == point:
                    self.move_event = point
                    self.moving_event_index = i

                    main_window = self.window()
                    if isinstance(main_window, MainWindow):
                        main_window.saved_data = False
                    break
            return

        if isinstance(event.artist, matplotlib.collections.PathCollection):
            return

        ind = event.ind[0]
        x = event.artist.get_xdata()[ind]
        y = event.artist.get_ydata()[ind]
        if event.artist == self.line1 or abs(self.plot_left_data[ind] - self.plot_right_data[ind]) > 0.02:
            if self.change_starting_point:
                ret = QMessageBox.warning(self, "Warning",
                                          f"Do you really wanna make a new start at {self.xs[ind]} seconds?",
                                          QMessageBox.Yes | QMessageBox.Cancel)
                if ret == QMessageBox.Yes:
                    self.new_starting_point(ind, x)
                    self.change_starting_point = False
                    main_window = self.window()
                    if isinstance(main_window, MainWindow):
                        main_window.saved_data = False

            if self.change_end_point:
                ret = QMessageBox.warning(self, "Warning",
                                          f"Do you really wanna make a new end at {self.xs[ind]} seconds?",
                                          QMessageBox.Yes | QMessageBox.Cancel)
                if ret == QMessageBox.Yes:
                    self.new_end_point(ind, x)
                    self.change_end_point = False
                    main_window = self.window()
                    if isinstance(main_window, MainWindow):
                        main_window.saved_data = False

            self.window().statusBar().showMessage(f"Coordinates: x = {round(x, 2)} & y = {round(y, 2)}", 2000)

    def track_mouse(self, event):
        """
        Needed for the markings on the data of the plot
        :param event: not the same as the events from the scatter, python-event
        """
        fs = manage_settings.get("Sensors", "fs")
        if event.inaxes != self.ax:
            self.mouse_marker.set_visible(False)
            self.canvas.draw_idle()
            return

        x, y = event.xdata, event.ydata
        index_search = round(x * fs)

        if self.change_events and self.move_event is not None and x is not None and y is not None:
            if 0 < index_search < len(self.plot_left_data) and \
                    abs(y - self.plot_left_data[index_search]) < abs(y - self.plot_right_data[index_search]):
                y_position = self.plot_left_data[index_search]
            elif 0 < index_search < len(self.plot_left_data) and \
                    abs(y - self.plot_right_data[index_search]) < abs(y - self.plot_left_data[index_search]):
                y_position = self.plot_right_data[index_search]
            else:
                y_position = 0

            self.move_event.set_offsets([x, y_position])
            self.canvas.draw_idle()
            return

        if x is None or y is None:
            return

        index_search = round(x*fs)

        if 0 < index_search < len(self.xs) and abs(self.plot_left_data[index_search] - y) < 0.1:
            self.mouse_marker.set_data([self.xs[index_search]], [self.plot_left_data[index_search]])
            self.mouse_marker.set_visible(True)
        elif 0 < index_search < len(self.xs) and abs(self.plot_right_data[index_search] - y) < 0.1:
            self.mouse_marker.set_data([self.xs[index_search]], [self.plot_right_data[index_search]])
            self.mouse_marker.set_visible(True)
        else:
            self.mouse_marker.set_visible(False)

        self.canvas.draw_idle()

    def releasing_event(self, event):
        """
        Change the scatter-events from position when released
        :param event: not the same as the events from the scatter, python-event
        """
        fs = manage_settings.get("Sensors", "fs")
        if not self.change_events or self.move_event is None:
            return

        x, y = event.xdata, event.ydata
        index_search = round(x * fs)

        if 0 < index_search < len(self.plot_left_data):
            if self.event_old_log[self.moving_event_index] == 0:
                self.event_old_log[self.moving_event_index] = self.event_log[self.moving_event_index]
            self.event_log[self.moving_event_index] = index_search
            if abs(y - self.plot_left_data[index_search]) < abs(y - self.plot_right_data[index_search]):
                self.event_position[self.moving_event_index] = 'Left'
            else:
                self.event_position[self.moving_event_index] = 'Right'

            self.notes_input.setTextColor(QColor(Qt.red))
            self.notes_input.append('')
            self.notes_input.append(f'--> Alternated e{self.moving_event_index+1}: {index_search}, to a time: {round(x, 2)}')
            self.notes_input.setTextColor(QColor(Qt.black))

            self.move_event = None
            self.moving_event_index = None

    def new_starting_point(self, ind, x):
        if self.xs[ind] != x:
            return

        self.window().setEnabled(False)

        temp = self.xs
        self.xs = [time-temp[ind] for time in self.xs[ind:]]

        temp = self.log_left
        self.log_left = [temp[i] for i in range(ind, len(self.log_left))]

        temp = self.log_right
        self.log_right = [temp[i] for i in range(ind, len(self.log_right))]

        if self.event_log[-1] != 0:
            try:
                self.first_event_guess = True
                self.calculate_events(False, True)
            except:
                NUMBER_EVENTS = manage_settings.get("Events", "NUMBER_EVENTS")
                QMessageBox.critical(self, "Error", f"Failed to get new events!")
                self.event_log = [0] * NUMBER_EVENTS
                self.event_old_log = [0] * NUMBER_EVENTS
                self.event_position = [None] * NUMBER_EVENTS

                if self.scatter:
                    for point in self.scatter:
                        point.remove()
                    self.scatter = []

        self.update_plot(True)
        self.window().setEnabled(True)

    def new_end_point(self, ind, x):
        if self.xs[ind] != x:
            return

        self.window().setEnabled(False)

        self.xs = [time for time in self.xs[:ind]]

        temp = self.log_left
        self.log_left = [temp[i] for i in range(0, ind)]

        temp = self.log_right
        self.log_right = [temp[i] for i in range(0, ind)]

        if self.event_log[-1] != 0:
            try:
                self.first_event_guess = True
                self.calculate_events(False, True)
            except:
                NUMBER_EVENTS = manage_settings.get("Events", "NUMBER_EVENTS")
                QMessageBox.critical(self, "Error", f"Failed to get new events!")
                self.event_log = [0] * NUMBER_EVENTS
                self.event_old_log = [0] * NUMBER_EVENTS
                self.event_position = [None] * NUMBER_EVENTS

                if self.scatter:
                    for point in self.scatter:
                        point.remove()
                    self.scatter = []

        self.update_plot(True)
        self.window().setEnabled(True)

    def start_reading(self):
        if self.trial_state == TrialState.not_started:
            self.timer_plot.start()
            self.reading_active = True
            self.trial_state = TrialState.running
            main_window = self.window()
            if isinstance(main_window, MainWindow):
                main_window.update_toolbar()

    def stop_reading(self):
        if self.trial_state == TrialState.running:
            self.reading_active = False
            self.timer_plot.stop()
            self.trial_state = TrialState.completed
            main_window = self.window()
            if isinstance(main_window, MainWindow):
                main_window.update_toolbar()

            self.update_plot(True)
            main_window.save_excel(self.trial_number)

    def reset_reading(self):
        if self.trial_state == TrialState.completed:
            NUMBER_EVENTS = manage_settings.get("Events", "NUMBER_EVENTS")

            if self.vt:
                self.ax.set_ylim(0, 3)
            else:
                self.ax.set_ylim(0, 10)
            self.ax.set_xlim(0, 10)

            self.pos_left = (0, 0, 0)
            self.pos_right = (0, 0, 0)
            self.xs = []
            self.log_left = []
            self.log_right = []

            self.plot_left_data = []
            self.plot_right_data = []

            self.line1.set_data([], [])
            self.line2.set_data([], [])

            self.event_log = [0] * NUMBER_EVENTS
            self.event_old_log = [0] * NUMBER_EVENTS
            self.event_position = [None] * NUMBER_EVENTS

            self.button_pressed = False
            self.first_event_guess = True
            self.original_data_file = False

            self.score.setCurrentIndex(0)

            if self.scatter:
                for point in self.scatter:
                    point.remove()
                self.scatter = []

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

        self.update_plot(True)

    def yt_plot(self):
        self.xt = False
        self.yt = True
        self.zt = False
        self.vt = False

        self.update_plot(True)

    def zt_plot(self):
        self.xt = False
        self.yt = False
        self.zt = True
        self.vt = False

        self.update_plot(True)

    def vt_plot(self):
        self.xt = False
        self.yt = False
        self.zt = False
        self.vt = True

        self.update_plot(True)

    def process(self, b, a):
        """
        Implement the Butterworth filter on the speed
        """
        SPEED_FILTER = manage_settings.get("Data-processing", "SPEED_FILTER")
        if SPEED_FILTER:
            output_left_speed = signal.filtfilt(b, a, [pos[3] for pos in self.log_left])
            output_right_speed = signal.filtfilt(b, a, [pos[3] for pos in self.log_right])
            for index in range(len(self.log_left)):
                self.log_left[index] = tuple(self.log_left[index][0:3]) + (output_left_speed[index],)
                self.log_right[index] = tuple(self.log_right[index][0:3]) + (output_right_speed[index],)

        else:
            output_left_x = signal.filtfilt(b, a, [pos[0] for pos in self.log_left])
            output_left_y = signal.filtfilt(b, a, [pos[1] for pos in self.log_left])
            output_left_z = signal.filtfilt(b, a, [pos[2] for pos in self.log_left])
            output_right_x = signal.filtfilt(b, a, [pos[0] for pos in self.log_right])
            output_right_y = signal.filtfilt(b, a, [pos[1] for pos in self.log_right])
            output_right_z = signal.filtfilt(b, a, [pos[2] for pos in self.log_right])

            for index in range(len(self.log_left)):
                self.log_left[index][0] = output_left_x[index]
                self.log_right[index][0] = output_right_x[index]
                self.log_left[index][1] = output_left_y[index]
                self.log_right[index][1] = output_right_y[index]
                self.log_left[index][2] = output_left_z[index]
                self.log_right[index][2] = output_right_z[index]

                if index > 0:
                    lpos = (self.log_left[index][0], self.log_left[index][1], self.log_left[index][2])
                    rpos = (self.log_right[index][0], self.log_right[index][1], self.log_right[index][2])
                    self.log_left[index][3] = self.speed_calculation(lpos, self.xs[index], index, True)
                    self.log_right[index][3] = self.speed_calculation(rpos, self.xs[index], index, False)

        self.update_plot(True)

    def update_plot(self, redraw=False, parent=None):
        if redraw or (self.reading_active and self.trial_state == TrialState.running):
            if parent:
                main_window = parent
            else:
                main_window = self.window()

            if isinstance(main_window, MainWindow):
                COLORS_EVENT = manage_settings.get("Events", "COLORS_EVENT")
                colors_hex = colors_to_hex(COLORS_EVENT)
                LABEL_EVENT = manage_settings.get("Events", "LABEL_EVENT")
                NUMBER_EVENTS = manage_settings.get("Events", "NUMBER_EVENTS")

                if self.xt:
                    self.ax.set_title(f'Trial {self.trial_number + 1} - x-coordinates')
                    self.ax.set_ylabel('X-coordinates (cm)')

                    self.plot_left_data = [abs(pos[0]) if main_window.set_abs_value else pos[0] for pos in
                                           self.log_left]
                    self.plot_right_data = [pos[0] for pos in self.log_right]
                elif self.yt:
                    self.ax.set_title(f'Trial {self.trial_number + 1} - y-coordinates')
                    self.ax.set_ylabel('Y-coordinates (cm)')

                    self.plot_left_data = [pos[1] for pos in self.log_left]
                    self.plot_right_data = [pos[1] for pos in self.log_right]
                elif self.zt:
                    self.ax.set_title(f'Trial {self.trial_number + 1} - z-coordinates')
                    self.ax.set_ylabel('Z-coordinates (cm)')

                    self.plot_left_data = [pos[2] for pos in self.log_left]
                    self.plot_right_data = [pos[2] for pos in self.log_right]
                else:
                    self.ax.set_title(f'Trial {self.trial_number + 1} - velocity plot')
                    self.ax.set_ylabel('Speed (m/s)')

                    self.plot_left_data = [pos[3] for pos in self.log_left]
                    self.plot_right_data = [pos[3] for pos in self.log_right]

                self.line1.set_xdata(self.xs)
                self.line1.set_ydata(self.plot_left_data)
                self.line2.set_xdata(self.xs)
                self.line2.set_ydata(self.plot_right_data)

                self.ax.set_xlim(0, 10)
                if self.vt:
                    self.ax.set_ylim(0, 3)
                else:
                    self.ax.set_ylim(0, 10)

                if self.xs:
                    self.ax.set_xlim(0, self.xs[-1] + 1)

                    max_y = max(max(self.plot_left_data, default=1),
                                max(self.plot_right_data, default=1)) * 1.1
                    min_y = min(min(self.plot_left_data, default=1),
                                min(self.plot_right_data, default=1)) * 1.1
                    if max_y < 10:
                        if self.vt:
                            max_y = 3
                        else:
                            max_y = 10
                    if min_y > 0:
                        if self.vt:
                            min_y = -0.05
                        else:
                            min_y = -1

                    self.ax.set_ylim(min_y, max_y)

                if self.scatter is not None:
                    if self.scatter:
                        for i in range(len(self.scatter)):
                            self.scatter[i].remove()
                        self.scatter = []
                    if len(self.xs) > 0: self.draw_events()

                legend_elements = [None] * NUMBER_EVENTS
                for i in range(NUMBER_EVENTS):
                    legend_elements[i] = Line2D([0], [0], marker='o', color='w', markerfacecolor=colors_hex[i],
                                                markersize=10, label=LABEL_EVENT[i])

                # Place legend below the plot
                self.ax.legend(handles=legend_elements, loc='upper center',
                               bbox_to_anchor=(0.5, -0.12), ncol=6)

                self.canvas.draw()

                if self.button_pressed and not redraw:
                    self.stop_reading()
                    main_window.tab_widget.tabBar().setEnabled(True)
                    main_window.switch_to_next_tab()
                    self.play_music()

    def calculate_events(self, got_folder=False, go=False):
        if go or (self.event_log[-1] == 0 and (self.button_pressed or READ_SAMPLE or got_folder)):
            NUMBER_EVENTS = manage_settings.get("Events", "NUMBER_EVENTS")
            if go: self.remove_added_text()

            predict_score(self.log_left, self.log_right)
            
            self.event_log[-1] = calculate_e6(self.xs)

            self.case_status = calculate_boxhand(self.log_left, self.log_right)
            if self.first_event_guess:
                if (self.button_pressed or self.original_data_file) and not \
                        (self.original_data_file and self.get_score() == 0):
                    self.score.setCurrentIndex(self.get_estimated_score())

                self.first_event_guess = False

            if self.get_score() == 0:
                self.event_log = [0]*NUMBER_EVENTS
                self.score.setCurrentIndex(0)

            self.notes_input.append(" ")

            self.notes_input.setTextColor(QColor(Qt.red))
            notes = ('Left hand is boxhand', 'Right hand is boxhand', 'Both hands as boxhand',
                     'Both hands as boxhand', 'Left hand is not used', 'Right hand is not used',
                     'Hands switched, but right pressed', 'Hands switched, but left pressed', )
            self.notes_input.append(notes[self.case_status] if self.button_pressed or (self.original_data_file and self.get_score() != 0) else 'Button not pressed')

            self.notes_input.append( f"Estimated score: {self.get_estimated_score() if self.button_pressed or (self.original_data_file and self.get_score() != 0) else 0}" )

            if self.get_score() != 0:
                e1, e2, e3, e4, e5 = calculate_events(self.log_left, self.log_right, self.case_status, self.get_score())
                self.event_log[0], self.event_log[1], self.event_log[2], self.event_log[3], self.event_log[4] = \
                    e1, e2, e3, e4, e5

            self.event_position = calculate_position_events(self.case_status)

            if self.get_score() == 3:
                if self.case_status == 0:
                    self.extra_parameters_bim, self.extra_parameters_uni = calculate_extra_parameters(self.event_log,
                                                                                                      self.log_right,
                                                                                                      self.log_left)
                else:
                    self.extra_parameters_bim, self.extra_parameters_uni = calculate_extra_parameters(self.event_log,
                                                                                                      self.log_left,
                                                                                                      self.log_right)
            else:
                self.extra_parameters_bim, self.extra_parameters_uni = [], []

            if self.get_score() != 0:
                text = self.text_events(self.event_log)
                for line in text:
                    self.notes_input.append(line)

            self.notes_input.setTextColor(QColor(Qt.black))

            self.update_plot(True)
            self.window().update_toolbar()

    def text_events(self, events):
        if len(events) < 6:
            return

        e1, e2, e3, e4, e5, e6 = events

        text_events_notes = []
        text_events_notes.append(f'The measured data is e1: {e1} and e2: {e2}')
        text_events_notes.append(f'The time is then for e1: {round(self.xs[e1], 2)} and e2: {round(self.xs[e2], 2)}')
        text_events_notes.append(f'The measured data is e3: {e3}')
        text_events_notes.append(f'The time is then for e3: {round(self.xs[e3], 2)}')
        text_events_notes.append('')
        text_events_notes.append(f'The measured data is e4: {e4} and e5: {e5}')
        text_events_notes.append(f'The time is then for e4: {round(self.xs[e4], 2)} and e5: {round(self.xs[e5], 2)}')
        return text_events_notes

    def draw_events(self):
        COLORS_EVENT = manage_settings.get("Events", "COLORS_EVENT")
        colors_hex = colors_to_hex(COLORS_EVENT)
        LABEL_EVENT = manage_settings.get("Events", "LABEL_EVENT")
        NUMBER_EVENTS = manage_settings.get("Events", "NUMBER_EVENTS")

        x_positions = [self.xs[ei] for ei in self.event_log]

        y_positions = [self.plot_left_data[ei] if self.event_position[index] == 'Left' else
                      self.plot_right_data[ei] for index, ei in enumerate(self.event_log)]

        self.scatter = []
        for i in range(NUMBER_EVENTS):
            self.scatter.append(self.ax.scatter(x_positions[i], y_positions[i],
                                    c=colors_hex[i], label=LABEL_EVENT[i], s=32, zorder=15-i, picker=True))

    def speed_calculation(self, vector, time_val, index, left):
        fs = manage_settings.get("Sensors", "fs")

        if len(self.xs) <= 1 or len(self.log_right) <= 1 or len(self.log_left) <= 1:
            return 0

        if left:
            return (sqrt(((vector[0] - self.log_left[index - 1][0]) * fs) ** 2 +
                         ((vector[1] - self.log_left[index - 1][1]) * fs) ** 2 +
                         ((vector[2] - self.log_left[index - 1][2]) * fs) ** 2) / 100)

        return (sqrt(((vector[0] - self.log_right[index - 1][0]) * fs) ** 2 +
                     ((vector[1] - self.log_right[index - 1][1]) * fs) ** 2 +
                     ((vector[2] - self.log_right[index - 1][2]) * fs) ** 2) / 100)

    def get_score(self):
        return self.score.currentIndex()

    def get_estimated_score(self):
        if self.case_status <= 1:
            return 3
        elif self.case_status <= 3:
            return 2
        elif self.case_status <= 5:
            return 1
        elif self.case_status <= 7:
            return 2
        else:
            return 0

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
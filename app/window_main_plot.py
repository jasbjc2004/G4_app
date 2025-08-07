import io
import os

import pandas as pd
import pikepdf
import pygame
import threading

import fpdf

from PySide6.QtWidgets import (
    QVBoxLayout, QMainWindow, QWidget,
    QMessageBox,
    QToolBar, QStatusBar, QTabWidget,
    QDialog, QCheckBox, QDialogButtonBox, QApplication,
)
from PySide6.QtGui import QAction, QIcon, QColor, QTextCursor, QTextCharFormat
from PySide6.QtCore import QSize, Signal, QThread, QMutex, QWaitCondition, Qt
from matplotlib import pyplot as plt
from matplotlib.lines import Line2D
from qasync import asyncSlot

from logger import get_logbook
from recording_gopro import GoPro
from sensor_G4Track import initialize_system, set_units, get_active_hubs, close_sensor
from data_processing import calculate_boxhand, calculate_position_events, \
    predict_score, Calibration

from scipy import signal

from thread_download import DownloadThread
from thread_reading import ReadThread
from widget_settings import manage_settings
from constants import READ_SAMPLE


class MainWindow(QMainWindow):
    def __init__(self, id, asses, date, num_trials, notes, sound=None, folder=None, neg_z=False, manual=False,
                 save=None):
        super().__init__()

        self.is_recording = False
        self.thread_recording = None
        self.gopro = None
        self.cali = None
        self.button_trigger = None
        self.logger = get_logbook('window_main_plot')

        self.setWindowTitle(id)
        file_directory = (os.path.dirname(os.path.abspath(__file__)))
        dir_icon = os.path.join(file_directory, 'NEEDED/PICTURES/hands.ico')
        self.setWindowIcon(QIcon(dir_icon))

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
        self.events_present = False

        self.first_calibration = True

        self.resize(1000, 600)

        self.folder = folder
        self.neg_z = neg_z
        self.manual_events = manual

        self.setup(num_trials)
        self.id_part = id
        self.assessor = asses
        self.date = date
        self.num_trials = num_trials
        self.notes = notes

        self.thread_download = None
        self.worker_download = None
        self.data_thread = ReadThread(self)
        self.data_thread.lost_connection.connect(self.data_loss)
        self.interference = False
        self.data_thread.interference.connect(self.data_loss)
        self.data_thread.done_reading.connect(self.interference_message)

        self.sound = sound
        self.participant_folder = None

        self.progression = None

        fs = manage_settings.get("Sensors", "fs")
        fc = manage_settings.get("Sensors", "fc")
        ORDER_FILTER = manage_settings.get("Data-processing", "ORDER_FILTER")

        nyq = 0.5 * fs
        w = fc / nyq
        self.b, self.a = signal.butter(ORDER_FILTER, w, 'low', analog=False)

        self.pdf = None
        thread_pdf = threading.Thread(target=self.make_pdf())
        thread_pdf.daemon = True
        thread_pdf.start()

        self.save_dir = save
        self.save_all = False

        self.saved_data = True

    def data_loss(self):
        QMessageBox.critical(self, "Error", "Sensor is down, please check the connections")

    def interference_detected(self):
        self.interference = True

    def interference_message(self):
        if self.interference:
            QMessageBox.information(self, "Warning", "There was a small interference, please check the result")
            self.interference = False

    def setup(self, num_trials):
        from widget_trials import TrailTab

        self.central_widget = QWidget()
        self.setCentralWidget(self.central_widget)
        self.main_layout = QVBoxLayout()
        self.central_widget.setLayout(self.main_layout)

        self.setup_menubar()
        self.setup_toolbar()
        self.setup_statusbar()

        if not pygame.mixer.get_init():
            pygame.mixer.init()

        self.tab_widget = QTabWidget()
        self.tab_widget.currentChanged.connect(self.tab_change_handler)
        for i in range(0, num_trials):
            tab = TrailTab(i, self.tab_widget)
            self.tab_widget.addTab(tab, f"Trial {i + 1}")

        if self.folder:
            self.collect_data(num_trials)

        self.main_layout.addWidget(self.tab_widget)
        self.update_toolbar()

    def tab_change_handler(self, index):
        """
        Not sure what this does anymore (only 1 rule)
        """
        self.update_toolbar()

    def setup_menubar(self):
        menu_bar = self.menuBar()
        file_menu = menu_bar.addMenu("&File")
        pdf_action = file_menu.addAction("Export to PDF")
        pdf_action.triggered.connect(self.download_pdf)
        tab_extra = file_menu.addAction("Add extra tab")
        tab_extra.triggered.connect(self.add_another_tab)
        file_menu.addSeparator()
        self.validate_action = file_menu.addAction("Validate calibration")
        self.validate_action.triggered.connect(self.validate_cali)
        self.validate_action.setEnabled(False)
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

        switch_action = settings_menu.addAction("Switch tab automatically")
        switch_action.setCheckable(True)
        switch_action.triggered.connect(lambda: self.set_automatic_tab(switch_action))

        settings_menu.addSeparator()

        absx_action = settings_menu.addAction("Set absolute values to x-axis")
        absx_action.setCheckable(True)
        absx_action.triggered.connect(lambda: self.plot_absolute_x(absx_action))

        negz_action = settings_menu.addAction("Set the negative value of the z-axis")
        negz_action.triggered.connect(self.set_negz)

        switch_hand_action = settings_menu.addAction("Switch the hand placement")
        switch_hand_action.triggered.connect(self.switch_hands)

        self.new_start_action = settings_menu.addAction("New starting point")
        self.new_start_action.setEnabled(False)
        self.new_start_action.triggered.connect(lambda: self.new_startpoint())

        self.new_end_action = settings_menu.addAction("New end point")
        self.new_end_action.setEnabled(False)
        self.new_end_action.triggered.connect(lambda: self.new_endpoint())

        self.process_action = settings_menu.addAction("Filter data")
        self.process_action.setEnabled(False)
        self.process_action.triggered.connect(lambda: self.process_tab())

        self.move_events_action = settings_menu.addAction("Move events")
        self.move_events_action.setEnabled(False)
        self.move_events_action.triggered.connect(lambda: self.move_events())

        settings_menu.addSeparator()

        self.disconnect_sensor_action = settings_menu.addAction("Disconnect sensors")
        self.disconnect_sensor_action.setEnabled(False)
        self.disconnect_sensor_action.triggered.connect(lambda: self.disconnecting_sensors())

        self.disconnect_button_action = settings_menu.addAction("Disconnect button")
        self.disconnect_button_action.setEnabled(False)
        self.disconnect_button_action.triggered.connect(lambda: self.disconnecting_button())

        settings_menu.addSeparator()
        tab_setting = settings_menu.addAction("More settings")
        tab_setting.triggered.connect(self.open_settings)

        help_menu = menu_bar.addMenu("&Help")
        expl_action = help_menu.addAction("Introduction")
        expl_action.triggered.connect(lambda: self.create_help())
        help_doc_action = help_menu.addAction("Manual")
        help_doc_action.triggered.connect(lambda: self.show_user_manual())

        menu_bar.setNativeMenuBar(False)

    def create_help(self):
        """
        Create the help pop-up
        """
        from widget_help import Help

        popup = Help(self)
        popup.show()

    def open_settings(self):
        from widget_settings import Settings
        popup = Settings(parent=self)
        popup.show()

    def update_plot(self):
        self.get_tab().update_plot(True)

    def new_startpoint(self):
        QMessageBox.information(self, "Information", f"Select a new point on the graph ([ESC] to cancel)")
        self.setFocusPolicy(Qt.StrongFocus)
        self.get_tab().change_starting_point = True

    def new_endpoint(self):
        QMessageBox.information(self, "Information", f"Select a new point on the graph ([ESC] to cancel)")
        self.setFocusPolicy(Qt.StrongFocus)
        self.get_tab().change_end_point = True

    def move_events(self):
        QMessageBox.information(self, "Information",
                                f"You can move the events freely now on the graph ([ESC] to cancel)")
        self.setFocusPolicy(Qt.StrongFocus)
        self.get_tab().change_events = True

    def keyPressEvent(self, event):
        """
        Needed to stop all the processing for the altering of the data
        """
        if (
                self.get_tab().change_starting_point or self.get_tab().change_end_point or self.get_tab().change_events) and event.key() == Qt.Key.Key_Escape:
            if self.get_tab().change_starting_point:
                QMessageBox.information(self, "Success", f"Terminated process to select new start")
            elif self.get_tab().change_end_point:
                QMessageBox.information(self, "Success", f"Terminated process to select new end")
            else:
                QMessageBox.information(self, "Success", f"Terminated process to move events")

            self.get_tab().change_starting_point = False
            self.get_tab().change_end_point = False
            self.get_tab().change_events = False
            self.setFocusPolicy(Qt.NoFocus)

    def show_user_manual(self):
        """
        Create the manual pop-up
        """
        from widget_manual import Manual

        popup = Manual(self)
        popup.show()

    def setup_toolbar(self):
        SERIAL_BUTTON = manage_settings.get("General", "SERIAL_BUTTON")

        toolbar = QToolBar("My main toolbar")
        toolbar.setIconSize(QSize(16, 16))
        self.addToolBar(toolbar)
        toolbar.setMovable(False)

        self.connection_action = QAction("Connect sensor", self)
        if READ_SAMPLE:
            self.connection_action.setEnabled(False)
        self.connection_action.setStatusTip("Connect and calibrate the sensor")
        self.connection_action.triggered.connect(lambda: self.connecting())
        toolbar.addAction(self.connection_action)

        self.calibrate_action = QAction("Calibrate", self)
        if READ_SAMPLE:
            self.calibrate_action.setEnabled(True)
        else:
            self.calibrate_action.setEnabled(False)
        self.calibrate_action.setStatusTip("Calibrate the sensor")
        self.calibrate_action.triggered.connect(lambda: self.calibration())
        toolbar.addAction(self.calibrate_action)

        toolbar.addSeparator()

        self.connection_button_action = QAction("Connect button", self)
        if not SERIAL_BUTTON:
            self.connection_button_action.setEnabled(False)
        self.connection_button_action.setStatusTip("Connect button and check if this is working correctly")
        self.connection_button_action.triggered.connect(lambda: self.button_connect())
        toolbar.addAction(self.connection_button_action)

        toolbar.addSeparator()

        self.camera_button_action = QAction("Record", self)
        self.camera_button_action.setStatusTip("Connect camera to check the time")
        self.camera_button_action.triggered.connect(self.camera_recording)
        toolbar.addAction(self.camera_button_action)

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

        self.event_action = QAction("Events", self)
        self.event_action.setStatusTip("Calculate the events for all trials")
        self.event_action.setEnabled(False)
        self.event_action.triggered.connect(self.process_events)
        toolbar.addAction(self.event_action)

        toolbar.addSeparator()

        quit_action = QAction("Quit", self)
        quit_action.triggered.connect(self.close)
        toolbar.addAction(quit_action)

    def setup_statusbar(self):
        from widget_status_connect import StatusWidget

        self.statusbar = QStatusBar(self)
        self.setStatusBar(self.statusbar)

        self.status_widget = StatusWidget()
        self.statusbar.addPermanentWidget(self.status_widget)
        if READ_SAMPLE:
            self.status_widget.set_status("no sensor")
        else:
            self.status_widget.set_status("disconnected")

    def collect_data(self, number_trials):
        """
        Extract all the data from the corresponding folder from the start-up
        """
        all_zeros = True

        for filename in os.listdir(self.folder):
            file_path = os.path.join(self.folder, filename)

            if os.path.isdir(file_path):
                continue

            elif filename.endswith(('.xlsx', '.xls', '.xlsm')):
                try:
                    if os.path.splitext(filename)[0] not in os.path.basename(self.folder):
                        self.extract_excel(file_path)
                except:
                    QMessageBox.critical(self, "Error", f"Failed to get info from: {file_path}!")
                    continue

            elif filename.endswith('.pdf'):
                try:
                    all_zeros = self.add_notes(file_path)
                except:
                    QMessageBox.critical(self, "Error", f"Failed to get info from: {file_path}!")
                    continue

        if all_zeros:
            print("all scores are zero")
            for i in range(number_trials):
                tab = self.tab_widget.widget(i)
                tab.button_pressed = True
                tab.original_data_file = False

    def extract_excel(self, file):
        """
        Extract all the data from the corresponding excel from collect_data
        """
        NUMBER_EVENTS = manage_settings.get("Events", "NUMBER_EVENTS")

        from widget_trials import TrailTab, TrialState

        trial_data = pd.read_excel(file)
        trial_number = file.split('.')[-2].split('_')[-1]

        tab = self.tab_widget.widget(int(trial_number) - 1)

        if trial_data.shape[1] < 1:
            tab.event_log = [0] * NUMBER_EVENTS
            return

        first_col = trial_data.iloc[:, 0]

        if first_col.isnull().all() or first_col.astype(str).str.strip().eq("").all():
            return

        xs = trial_data.iloc[:, 0].values
        if not (isinstance(tab, TrailTab) and len(xs) > 2):
            tab.event_log = [0] * NUMBER_EVENTS
            return
        tab.trial_state = TrialState.completed

        self.update_toolbar()

        tab.xs.clear()
        tab.log_left.clear()
        tab.log_right.clear()

        tab.xs = list(xs)
        x1 = trial_data.iloc[:, 1].values
        y1 = trial_data.iloc[:, 2].values
        if not self.neg_z:
            z1 = trial_data.iloc[:, 3].values
        else:
            z1 = -trial_data.iloc[:, 3].values
        v1 = trial_data.iloc[:, 4].values

        x2 = trial_data.iloc[:, 5].values
        y2 = trial_data.iloc[:, 6].values
        if not self.neg_z:
            z2 = trial_data.iloc[:, 7].values
        else:
            z2 = -trial_data.iloc[:, 7].values
        v2 = trial_data.iloc[:, 8].values

        for i in range(len(x1)):
            tab.log_left.append((x1[i], y1[i], z1[i], v1[i],))
            tab.log_right.append((x2[i], y2[i], z2[i], v2[i],))

        try:
            if trial_data.shape[1] <= 8:
                tab.original_data_file = False
            else:
                tab.original_data_file = True

            # add manual sign
            if trial_data.shape[1] < 11:
                tab.event_log = [0] * NUMBER_EVENTS
            elif self.manual_events:
                tab.event_log = trial_data.iloc[:, 12].values[0:NUMBER_EVENTS].tolist()
                if all(x == 0 for x in tab.event_log):
                    tab.event_log = trial_data.iloc[:, 11].values[0:NUMBER_EVENTS].tolist()
            else:
                tab.event_log = trial_data.iloc[:, 11].values[0:NUMBER_EVENTS].tolist()

            self.events_present = not all(x == 0 for x in tab.event_log)
            if self.events_present:
                tab.first_process = False

            if trial_data.shape[1] < 13 or not self.manual_events:
                USE_NEURAL_NET = manage_settings.get("General", "USE_NEURAL_NET")

                if USE_NEURAL_NET:
                    score = predict_score(tab.log_left, tab.log_right)
                else:
                    score = -1
                tab.case_status = calculate_boxhand(tab.log_left, tab.log_right, score)
                tab.event_position = calculate_position_events(tab.case_status)
            else:
                tab.event_position = trial_data.iloc[:, 13].values[0:NUMBER_EVENTS].tolist()
        finally:
            if tab.event_log is None or len(tab.event_log) == 0:
                tab.event_log = [0] * NUMBER_EVENTS
            else:
                tab.event_log = [int(x) if x != 0 else 0 for x in tab.event_log]

        tab.update_plot(True, self)

    def add_notes(self, file):
        """
        Extract all the notes from the corresponding PDF from collect_data
        """
        from widget_trials import TrailTab

        pdf = pikepdf.Pdf.open(file)

        trial_number = 0
        in_table = False
        all_zeros = True
        for page in pdf.pages:
            pdf_content = page.get('/Contents').read_bytes().decode('utf-8')
            text = pdf_content.split('\n')

            for line in text:
                if '(' in line:
                    rule_text = line.split('(', 1)[1]
                    rule_text = rule_text[::-1].split(')', 1)[1][::-1]

                    if 'Trial 1' in rule_text and trial_number == 0:
                        trial_number = 1
                        tab = self.tab_widget.widget(int(trial_number) - 1)
                        if isinstance(tab, TrailTab) and 'score' in rule_text:
                            score = int(rule_text.split()[3])

                            tab.score.setCurrentIndex(score)
                            if score != 0: all_zeros = False

                    elif 'Trial' in rule_text and int(rule_text.split()[1][:-1]) == trial_number + 1:
                        in_table = False
                        trial_number += 1

                        tab = self.tab_widget.widget(int(trial_number) - 1)
                        if isinstance(tab, TrailTab) and 'score' in rule_text:
                            score = int(rule_text.split()[3])

                            tab.score.setCurrentIndex(score)
                            if score != 0: all_zeros = False

                    elif trial_number == 0:
                        continue

                    elif rule_text == 'Table' or rule_text == 'Parameters' or rule_text == 'Events':
                        in_table = True

                    elif rule_text == 'Average over all trials with score 3':
                        break

                    else:
                        cursor = tab.notes_input.textCursor()
                        fmt = QTextCharFormat()
                        fmt.setForeground(QColor(Qt.black))
                        cursor.setCharFormat(fmt)
                        if not in_table and rule_text != 'No Notes':
                            cursor.insertText(rule_text)
                            cursor.insertText('\n')

        return all_zeros

    def get_tab(self):
        from widget_trials import TrailTab

        tab = self.tab_widget.currentWidget()
        if isinstance(tab, TrailTab):
            return tab
        return None

    def get_tab_score(self):
        from widget_trials import TrailTab

        scores = []

        for index in range(self.tab_widget.count()):
            tab = self.tab_widget.widget(index)

            if isinstance(tab, TrailTab):
                scores.append(tab.get_score())

        return scores

    def add_another_tab(self):
        """
        Add another tab to the window
        """
        from widget_trials import TrailTab

        tab = TrailTab(self.num_trials, self.tab_widget)
        self.tab_widget.addTab(tab, f"Trial {self.num_trials + 1}")
        self.num_trials += 1

    def update_toolbar(self):
        """
        Update all the buttons in the toolbar
        """
        from widget_trials import TrialState
        SERIAL_BUTTON = manage_settings.get("General", "SERIAL_BUTTON")

        tab = self.get_tab()

        if tab is None or (not self.is_connected and self.first_calibration and not READ_SAMPLE):
            self.start_action.setEnabled(False)
            self.stop_action.setEnabled(False)
            self.reset_action.setEnabled(False)

        elif tab.trial_state == TrialState.not_started and (not self.first_calibration or READ_SAMPLE):
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

        if tab.trial_state == TrialState.completed:
            self.new_start_action.setEnabled(True)
            self.new_end_action.setEnabled(True)
            self.process_action.setEnabled(True)
            self.event_action.setEnabled(True)
            if tab.event_log[-1] != 0:
                self.move_events_action.setEnabled(True)
        else:
            self.new_start_action.setEnabled(False)
            self.new_end_action.setEnabled(False)
            self.process_action.setEnabled(False)
            self.event_action.setEnabled(False)
            self.move_events_action.setEnabled(False)

        if SERIAL_BUTTON and self.button_trigger is None:
            self.connection_button_action.setEnabled(True)
        elif not SERIAL_BUTTON:
            self.disconnecting_button()
            self.connection_button_action.setEnabled(False)

    def start_current_reading(self):
        tab = self.get_tab()
        self.saved_data = False

        if tab is not None:
            self.data_thread.start_tab_reading(tab)
            tab.start_reading()
            self.tab_widget.tabBar().setEnabled(False)

    def stop_current_reading(self):
        tab = self.get_tab()
        self.saved_data = False

        if tab is not None:
            self.data_thread.pause()
            self.data_thread.wait_until_paused()
            self.data_thread.stop_current_reading()
            tab.stop_reading()
            self.data_thread.resume()
            self.tab_widget.tabBar().setEnabled(True)

    def reset_current_reading(self):
        tab = self.get_tab()

        if tab is not None:
            ret = QMessageBox.warning(self, "Warning",
                                      f"Do you really want to reset the data for trial {self.tab_widget.currentIndex() + 1}?",
                                      QMessageBox.Yes | QMessageBox.Cancel)
            if ret == QMessageBox.Yes:
                tab.reset_reading()
                self.update_toolbar()

    def signal_text_changed(self):
        self.saved_data = False

    def switch_to_next_tab(self):
        """
        Makes it possible to skip the trial if it's finished to speed up the recording of data
        :return:
        """
        if self.set_automatic:
            current_index = self.tab_widget.currentIndex()
            total_tabs = self.tab_widget.count()

            if current_index < total_tabs:
                next_index = (current_index + 1)
                self.tab_widget.setCurrentIndex(next_index)

    def connecting(self):
        """
        Connect the sensor
        """
        MAX_ATTEMPTS_CONNECT = manage_settings.get("Sensors", "MAX_ATTEMPTS_CONNECT")

        QMessageBox.information(self, "Info", "Started to connect. Please wait a bit.")

        if self.is_connected:
            QMessageBox.information(self, "Info", "Already connected to sensors!")
            return

        self.status_widget.set_status("connecting")
        self.repaint()
        file_directory = (os.path.dirname(os.path.abspath(__file__)))
        src_cfg_file = (os.path.join(file_directory, "NEEDED/FILES/first_calibration.g4c"))

        connected = False
        self.dongle_id = None

        attempt = 0

        while self.dongle_id is None and attempt < MAX_ATTEMPTS_CONNECT:
            connected, self.dongle_id = initialize_system(src_cfg_file)
            attempt += 1

        if not connected or self.dongle_id is None:
            QMessageBox.critical(self, "Error", "Failed to connect to sensors after multiple attempts!")
            close_sensor()
            self.status_widget.set_status("disconnected")
            return

        try:
            get_active_hubs(self.dongle_id, True)[0]
        except:
            QMessageBox.critical(self, "Error", "Failed to connect to hubs! Please check if they are online")
            self.status_widget.set_status("disconnected")
            close_sensor()
            self.dongle_id = None
            return

        set_units(self.dongle_id)

        self.is_connected = True
        self.connection_action.setEnabled(False)  # Disable connect button after successful connection
        self.calibrate_action.setEnabled(True)
        self.disconnect_sensor_action.setEnabled(True)
        self.statusBar().showMessage("Successfully connected to sensors")
        QMessageBox.information(self, "Success", "Successfully connected to sensors!")
        self.status_widget.set_status("connected")
        self.update_toolbar()

    def button_connect(self):
        """
        Creates the pop-up for the connection with the button
        :return:
        """
        from widget_button_tester import ButtonTester

        popup = ButtonTester(self)
        popup.show()

    def camera_recording(self):
        if self.gopro is None:
            if self.participant_folder is None:
                self.make_dir()
            print(self.participant_folder)
            self.gopro = GoPro(self, self.participant_folder, self.id_part)
            self.is_recording = True
            # Connect the signals - these will be called in the main thread
            self.gopro.started.connect(self._on_recording_started)
            self.gopro.stopped.connect(self._on_recording_stopped)
            self.gopro.error.connect(self._on_error)
            self.gopro.download_progress.connect(self._on_download_progress)
        else:
            self.is_recording = False
        self.toggle_recording()

    def toggle_recording(self):
        if not self.is_recording:
            print('Stop recording')
            self.gopro.stop_recording()
            self.gopro = None
        else:
            if self.gopro is None:
                self.gopro = GoPro(self)
                # Connect the signals - these will be called in the main thread
                self.gopro.started.connect(self._on_recording_started)
                self.gopro.stopped.connect(self._on_recording_stopped)
                self.gopro.error.connect(self._on_error)
                self.gopro.download_progress.connect(self._on_download_progress)

            QMessageBox.information(self, "Succes", "Please make sure the gopro is in pairing mode!")
            print('Start recording')
            self.gopro.start_recording()

    def _on_recording_started(self):
        """Handle when recording actually starts - runs in main thread"""
        print("Recording started signal received")
        QMessageBox.information(self, "Success", "Recording started!")
        self.is_recording = True

    def _on_recording_stopped(self):
        """Handle when recording stops - runs in main thread"""
        print("Recording stopped signal received")
        QMessageBox.information(self, "Success", "Recording stopped and video downloaded!")
        self.is_recording = False
        self.gopro = None  # Clean up

    def _on_error(self, error_msg):
        """Handle GoPro errors - runs in main thread"""
        print(f"GoPro error: {error_msg}")
        QMessageBox.critical(self, "Error", f"GoPro Error: {error_msg}")
        self.is_recording = False
        self.gopro = None  # Clean up

    def _on_download_progress(self, message):
        """Handle download progress messages - runs in main thread"""
        print(f"Download progress: {message}")
        # You could update a progress bar or status label here

    def disconnecting_sensors(self):
        self.is_connected = False
        close_sensor()
        self.connection_action.setEnabled(True)
        self.calibrate_action.setEnabled(False)
        self.validate_action.setEnabled(False)
        self.disconnect_sensor_action.setEnabled(False)
        self.statusBar().showMessage("Successfully disconnected to sensors")
        self.status_widget.set_status("disconnected")
        self.update_toolbar()

    def disconnecting_button(self):
        print('disconnecting')
        self.button_trigger.close()
        self.button_trigger = None
        self.connection_button_action.setEnabled(True)
        self.disconnect_button_action.setEnabled(False)
        self.statusBar().showMessage("Successfully disconnected to button")

    def calibration(self):
        """
        Calibrate the sensor with calibration_to_center(sys_id) of data_processing
        """
        if self.dongle_id and not READ_SAMPLE:
            print('here')
            self.cali = Calibration(self.dongle_id)
        else:
            self.cali = None

        if self.data_thread.isRunning():
            self.data_thread.requestInterruption()
            self.data_thread.quit()
            self.data_thread.wait()

        ret = QMessageBox.Cancel
        if not self.first_calibration:
            ret = QMessageBox.warning(self, "Warning",
                                      "Do you really want to calibrate again?",
                                      QMessageBox.Yes | QMessageBox.Cancel)

        if self.first_calibration or ret == QMessageBox.Yes:
            QMessageBox.information(self, "Info", "Started to calibrate. "
                                                  "Please wait a bit and keep the sensors at a fixed position.")
            try:
                if not READ_SAMPLE:
                    self.hub_id, self.lindex, self.rindex, calibration_status = self.cali.calibration_to_center()
                else:
                    calibration_status = True
            except:
                calibration_status = False
            finally:
                if READ_SAMPLE:
                    calibration_status = True

            if not calibration_status:
                if self.hub_id == 0 and self.lindex == 0 and self.rindex == 0:
                    QMessageBox.critical(self, "Warning", "Abnormal activity! Check if the hub is charged "
                                                          "(no red light) and the blue light is on and the source is on")
                else:
                    QMessageBox.critical(self, "Warning", "Calibration did not succeed!")
            else:
                self.first_calibration = False

                LONG_CALIBRATION = manage_settings.get("Calibration", "LONG_CALIBRATION")
                if not READ_SAMPLE and LONG_CALIBRATION:
                    # start with orientation transformation
                    QMessageBox.information(self, "Info", "Put one of the sensors on the button. "
                                                          "Keep the other one still")
                    self.cali.precise_rotation(0)
                    QMessageBox.information(self, "Info", "Put one of the sensors in the outer left corner of the box. "
                                                          "Keep the other one still")
                    self.cali.precise_rotation(1)
                    QMessageBox.information(self, "Info", "Put same sensor in the outer right corner of the box. "
                                                          "Keep the other one still")
                    self.cali.precise_rotation(2)

                    QMessageBox.information(self, "Info", "Universal rotation set")

                    # start with translation transformation
                    QMessageBox.information(self, "Info", "Put one of the sensors on the button. "
                                                          "Keep the other one still")
                    # first phase to connect to button
                    calibration_status = self.cali.calibration_to_button_first_phase()
                    if not calibration_status:
                        QMessageBox.critical(self, "Warning", "Calibration to button did not succeed! "
                                                              "The program will use a less accurate calibration "
                                                              "or try again")
                    else:
                        # second phase to check if it worked
                        QMessageBox.information(self, "Info", "Put the other sensors on the button. "
                                                              "Keep the other one still")
                        calibration_status = self.cali.calibration_to_button_second_phase()
                        if not calibration_status:
                            QMessageBox.critical(self, "Warning", "Calibration to button did not succeed! "
                                                                  "The program will use a less accurate calibration "
                                                                  "or try again")
                        else:
                            QMessageBox.information(self, "Success", "Successfully calibrated to "
                                                                     "sensors according to button!")
                else:
                    QMessageBox.information(self, "Success", "Successfully calibrated to sensors!")

                self.validate_action.setEnabled(True)
                self.update_toolbar()

                self.data_thread.start()

    def validate_cali(self):
        QMessageBox.information(self, "Info", "Put one of the sensors on the button. "
                                              "Keep the other one still")
        calibration_status = self.cali.calibration_to_button_second_phase()
        if not calibration_status:
            QMessageBox.critical(self, "Warning", "There was a slight change in the position. Please be aware of this")
        else:
            QMessageBox.information(self, "Success", "Successfully validated the position")

    def xt_plot(self):
        self.get_tab().xt_plot()

    def yt_plot(self):
        self.get_tab().yt_plot()

    def zt_plot(self):
        self.get_tab().zt_plot()

    def vt_plot(self):
        self.get_tab().vt_plot()

    def process_tab(self):
        """
        Filter the data of the tab
        """
        self.get_tab().process(self.b, self.a)
        self.saved_data = False

    def process_events(self):
        """
        Calculate all the events of each trial
        """
        from widget_trials import TrailTab

        self.switch_hands(True)

        go = False
        if self.events_present:
            ret = QMessageBox.warning(self, "Warning",
                                      "Do you really want to calculate the events again?",
                                      QMessageBox.Yes | QMessageBox.Cancel)
            go = (ret == QMessageBox.Yes)

        if not self.events_present or go:
            for index in range(self.tab_widget.count()):
                tab = self.tab_widget.widget(index)

                if isinstance(tab, TrailTab) and len(tab.xs) > 0:
                    if tab.first_process:
                        tab.process(self.b, self.a)
                        tab.first_process = False
                    tab.calculate_events((self.folder is not None), go)

            self.events_present = True
        self.saved_data = False

    def plot_absolute_x(self, button):
        if button.isChecked():
            self.set_abs_value = True
        else:
            self.set_abs_value = False
        self.get_tab().update_plot(True)

    def set_negz(self):
        from widget_trials import TrailTab

        for i in range(self.tab_widget.count()):
            tab = self.tab_widget.widget(i)

            if isinstance(tab, TrailTab):
                for index in range(len(tab.log_left)):
                    temp = list(tab.log_left[index])
                    temp[2] = -temp[2]
                    tab.log_left[index] = tuple(temp)

                    temp = list(tab.log_right[index])
                    temp[2] = -temp[2]
                    tab.log_right[index] = tuple(temp)

            tab.update_plot(True)

    def switch_hands(self, show_no_error=False):
        """
        Check if hands are inverted in the proces after calibration
        :param show_no_error:
        :return:
        """
        from widget_trials import TrailTab

        self.lindex, self.rindex = self.rindex, self.lindex

        change_tabs = []
        active_tabs = 0
        for i in range(self.tab_widget.count()):
            tab = self.tab_widget.widget(i)

            if isinstance(tab, TrailTab):
                if len(tab.xs) > 0:
                    active_tabs += 1
                    if tab.log_left[0][0] > tab.log_right[0][0]:
                        tab.log_left, tab.log_right = tab.log_right, tab.log_left
                        change_tabs.append(i)

            tab.update_plot(True)

        if len(change_tabs) == 0:
            text = 'No trials are changed'
            if show_no_error: return
        elif len(change_tabs) == active_tabs:
            text = f"All trials changed"
        elif len(change_tabs) == 1:
            text = f'Trial {change_tabs[0]} changed'
        elif len(change_tabs) <= active_tabs / 2:
            missing = [i for i in range(10) if i not in change_tabs]
            if len(missing) == 1:
                text = f"All trials changed except for trial {missing[0]} changed"
            else:
                text = f"All trials changed except for trial {', '.join(str(n) for n in change_tabs)} changed"
        else:
            text = f"Trials {', '.join(str(n) for n in change_tabs)} changed"

        QMessageBox.warning(self, "Warning", text)

    def set_automatic_tab(self, button):
        if button.isChecked():
            self.set_automatic = True
        else:
            self.set_automatic = False

    def closeEvent(self, event):
        if not self.saved_data:
            ret = QMessageBox.warning(self, "Warning",
                                      "Are you sure you want to quit the application? There is still unsaved data!",
                                      QMessageBox.Yes | QMessageBox.Cancel)
            if ret == QMessageBox.Yes:
                self.full_close_app(event)
            else:
                event.ignore()
        else:
            self.full_close_app(event)

    def full_close_app(self, event):
        if self.thread_download and self.thread_download.isRunning():
            self.thread_download.quit()
            self.thread_download.wait()

        if hasattr(self, 'gopro') and self.gopro is not None:
            self.gopro.cleanup()

        if self.data_thread and self.data_thread.isRunning():
            self.data_thread.requestInterruption()
            self.data_thread.quit()
            self.data_thread.wait()

        close_sensor()

        if not pygame.mixer.get_init():
            pygame.mixer.quit()

        event.accept()
        QApplication.quit()

    def make_pdf(self):
        """
        Make the preparation of the PDF to speed up the proces
        """
        self.pdf = fpdf.FPDF()
        self.pdf.set_auto_page_break(auto=True, margin=15)
        self.pdf.add_page()
        self.pdf.set_font("Arial", size=12)

        self.pdf.set_font("Arial", style="BU", size=16)
        self.pdf.cell(0, 10, f"Participant {self.id_part} by assessor {self.assessor} "
                             f"on {self.date}" if self.id_part and self.assessor else
        f"Participant {self.id_part} on {self.date}" if self.id_part else
        f"Participant Unknown on {self.date}", ln=True)
        self.pdf.set_font("Arial", size=12)
        self.pdf.multi_cell(0, 8, self.notes if self.notes else "No Additional Notes")
        self.pdf.cell(0, 10, f"", ln=True)

    def save_excel(self, index):
        if self.thread_download and self.thread_download.isRunning():
            self.thread_download.quit()
            self.thread_download.wait()

        self.save_all = False
        if self.participant_folder is None:
            self.make_dir()

        self.thread_download = QThread()
        self.worker_download = DownloadThread(self, self.participant_folder, index)
        self.worker_download.moveToThread(self.thread_download)

        self.worker_download.pdf_ready_image.connect(self.add_plots_data)
        self.worker_download.progress.connect(self.set_progress)
        self.worker_download.finished_file.connect(self.finish_export)
        self.worker_download.error_occurred.connect(self.show_error)

        self.thread_download.started.connect(self.worker_download.run)
        self.thread_download.start()

    def make_dir(self):
        self.participant_folder = os.path.join(self.save_dir, self.id_part)

        counter = 0
        while os.path.exists(self.participant_folder):
            counter += 1
            self.participant_folder = os.path.join(self.save_dir, self.id_part + f'({counter})')
        os.makedirs(self.participant_folder, exist_ok=True)

    def download_pdf(self):
        """
        Start the download of the files
        """
        while True:
            selection_plot = QDialog(self)
            selection_plot.setWindowTitle("Select graph to save")
            layout = QVBoxLayout()

            # Plot selection checkboxes
            checkboxes = [
                QCheckBox("The x-plot"),
                QCheckBox("The y-plot"),
                QCheckBox("The z-plot"),
                QCheckBox("The v-plot")
            ]
            for checkbox in checkboxes:
                checkbox.setChecked(False)
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

            self.name_pdf = self.id_part

            if self.thread_download and self.thread_download.isRunning():
                self.thread_download.quit()
                self.thread_download.wait()

            self.save_all = True

            if self.participant_folder is None or not os.path.exists(self.participant_folder):
                self.make_dir()

            self.make_progress()
            self.thread_download = QThread()
            self.worker_download = DownloadThread(self, self.participant_folder, -1, self.id_part, self.pdf,
                                         [index for index in range(len(checkboxes)) if
                                             checkboxes[index].isChecked()])
            self.worker_download.moveToThread(self.thread_download)

            self.worker_download.pdf_ready_image.connect(self.add_plots_data)
            self.worker_download.progress.connect(self.set_progress)
            self.worker_download.finished_file.connect(self.finish_export)
            self.worker_download.error_occurred.connect(self.show_error)

            self.thread_download.started.connect(self.worker_download.run)
            self.thread_download.start()

            break

    def add_plots_data(self, plot_index, xs, left_data, right_data, events, event_position, pos_plot):
        """
        Plot the data in the PDF (needed to stay in MainThread)
        :param plot_index: which plot has to be made (x,y,z,v) as index
        :type plot_index: int
        :param xs: the timestamps
        :param left_data: the coordinates of the left hand
        :param right_data: the coordinates of the right hand
        :param events: the indexes of each event
        :param event_position: the position of each event
        :param pos_plot: a tuple containing the current index of the plot and the total selected plots
        """
        COLORS_EVENT = manage_settings.get("Events", "COLORS_EVENT")
        LABEL_EVENT = manage_settings.get("Events", "LABEL_EVENT")
        NUMBER_EVENTS = manage_settings.get("Events", "NUMBER_EVENTS")

        buf = io.BytesIO()
        try:
            fig, ax = plt.subplots()

            ax.plot(xs, left_data, label='Left Sensor', color='green')
            ax.plot(xs, right_data, label='Right Sensor', color='red')

            legend_hands = ax.legend()
            ax.add_artist(legend_hands)

            x_positions = [xs[ei] for ei in events]
            y_positions = [left_data[ei] if event_position[index] == 'Left' else
                           right_data[ei] for index, ei in enumerate(events)]

            for i in range(NUMBER_EVENTS):
                ax.scatter(x_positions[i], y_positions[i], c=COLORS_EVENT[i], label=LABEL_EVENT[i], s=32,
                           zorder=15 - i)

            ax.set_title(
                f"{'X' if plot_index == 0 else 'Y' if plot_index == 1 else 'Z' if plot_index == 2 else 'Velocity'} Plot")
            ax.set_xlabel("Time (s)")
            ylabel = ["X Position (cm)", "Y Position (cm)", "Z Position (cm)", "Speed (m/s)"][plot_index]
            ax.set_ylabel(ylabel)

            if events[-1] != 0:
                legend_elements = [None] * NUMBER_EVENTS
                for i in range(NUMBER_EVENTS):
                    legend_elements[i] = Line2D([0], [0], marker='o', color='w', markerfacecolor=COLORS_EVENT[i],
                                                markersize=10, label=LABEL_EVENT[i])

                # Place legend below the plot
                ax.legend(handles=legend_elements, loc='upper center',
                          bbox_to_anchor=(0.5, -0.12), ncol=6)

            ax.grid(True)

            fig_width_inch, fig_height_inch = fig.get_size_inches()
            aspect_ratio = fig_height_inch / fig_width_inch

            plt.savefig(buf, format='png', dpi=150, bbox_inches='tight')
            plt.close(fig)

            x_start = 15
            width = 80
            spacing_x = 5
            spacing_y = 15

            if pos_plot[0] not in [1, 3]:
                self.y_image = self.pdf.get_y()
            if pos_plot[0] == 2:
                self.pdf.ln(5)

            image_height = width * aspect_ratio

            x_image = x_start + pos_plot[0] % 2 * (width + spacing_x)

            current_y = self.pdf.get_y()
            page_height = self.pdf.h - 20  # margin
            available_space = page_height - current_y

            if available_space < image_height:
                self.pdf.add_page()
                self.y_image = self.pdf.get_y()

            buf.seek(0)
            self.pdf.image(buf, x=x_image, y=self.y_image, w=width, type='PNG')

            if pos_plot[0] in [1, 3] or pos_plot[0] == pos_plot[1] - 1:
                total_height = image_height + spacing_y
                self.pdf.set_y(self.y_image + total_height)

        except Exception as e:
            self.logger.error(e, exc_info=True)
            print(str(e))
        finally:
            buf.close()
            self.worker_download.condition.wakeAll()

    def make_progress(self):
        """
        Make the progress bar pop-up
        """
        from widget_progression_bar import ProgressionBar

        self.progression = ProgressionBar()
        self.progression.show()

    def show_error(self, e):
        self.logger.error(e, exc_info=True)
        if self.progression:
            self.progression.close()
            self.progression = None
        QMessageBox.critical(self, "Export Error", f"An error occurred during export: {str(e)}")

    def finish_export(self):
        """
        Upload the PDF to the right directory
        """

        if self.save_all:
            pdf_file = os.path.join(self.participant_folder, f"{self.name_pdf}.pdf")
            try:
                self.pdf.output(pdf_file)
            except PermissionError:
                print("PDF is waarschijnlijk nog open. Sluit het bestand en probeer opnieuw.")
                counter = 1
                while os.path.exists(pdf_file):
                    pdf_file = os.path.join(self.participant_folder, f"{self.name_pdf}({counter}).pdf")
                    counter += 1

                self.pdf.output(pdf_file)

            self.pdf = None
            thread_pdf = threading.Thread(target=self.make_pdf())
            thread_pdf.daemon = True
            thread_pdf.start()

            if self.progression:
                self.progression.set_progress(100)
                self.progression = None

            QMessageBox.information(self, "Success", f"Data saved in folder: {self.participant_folder}")
            self.saved_data = True

    def set_progress(self, value: int):
        self.progression.set_progress(value)

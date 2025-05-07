import io
import os
import time

import pandas as pd
import pikepdf
import pygame
import threading

import fpdf

from PySide6.QtWidgets import (
    QApplication, QVBoxLayout, QMainWindow, QWidget,
    QLineEdit, QLabel, QHBoxLayout, QMessageBox,
    QToolBar, QStatusBar, QTabWidget,
    QFileDialog, QDialog, QCheckBox, QDialogButtonBox,
)
from PySide6.QtGui import QAction
from PySide6.QtCore import QSize, QObject, Signal, QThread, QEventLoop, QMutex, QWaitCondition, Qt
from matplotlib import pyplot as plt
from matplotlib.lines import Line2D

from sensor_G4Track import initialize_system, set_units, get_active_hubs, close_sensor
from data_processing import calibration_to_center

from scipy import signal

from constants import MAX_ATTEMPTS, READ_SAMPLE, SERIAL_BUTTON, fs, fc, ORDER_FILTER, NUMBER_EVENTS, COLORS_EVENT, \
    LABEL_EVENT


class MainWindow(QMainWindow):
    def __init__(self, id, asses, date, num_trials, notes, sound=None, folder=None, neg_z=False):
        super().__init__()

        self.button_trigger = None

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
        self.events_present = False

        self.first_calibration = True

        self.resize(1000, 600)

        self.folder = folder
        self.neg_z = neg_z

        self.setup(num_trials)
        self.id_part = id
        self.assessor = asses
        self.date = date
        self.num_trials = num_trials
        self.notes = notes

        self.thread = None
        self.worker = None

        self.sound = sound

        nyq = 0.5 * fs
        w = fc / nyq
        self.b, self.a = signal.butter(ORDER_FILTER, w, 'low', analog=False)

        self.pdf = None
        thread_pdf = threading.Thread(target=self.make_pdf())
        thread_pdf.daemon = True
        thread_pdf.start()

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
            self.collect_data()

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

        switch_action = settings_menu.addAction("Switch tab automatically")
        switch_action.setCheckable(True)
        switch_action.triggered.connect(lambda: self.set_automatic_tab(switch_action))

        settings_menu.addSeparator()

        absx_action = settings_menu.addAction("Set absolute values to x-axis")
        absx_action.setCheckable(True)
        absx_action.triggered.connect(lambda: self.plot_absolute_x(absx_action))

        negz_action = settings_menu.addAction("Set the negative value of the z-axis")
        negz_action.triggered.connect(self.set_negz)

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

        help_menu = menu_bar.addMenu("&Help")
        expl_action = help_menu.addAction("Introduction")
        expl_action.triggered.connect(lambda: self.create_help())
        help_doc_action = help_menu.addAction("Manual")
        help_doc_action.triggered.connect(lambda: self.show_user_manual())

        menu_bar.setNativeMenuBar(False)

    def create_help(self):
        from widget_help import Help

        popup = Help(self)
        popup.show()

    def new_startpoint(self):
        QMessageBox.information(self, "Information", f"Select a new point on the graph ([ESC] to cancel)")
        self.setFocusPolicy(Qt.StrongFocus)
        self.get_tab().change_starting_point = True

    def new_endpoint(self):
        QMessageBox.information(self, "Information", f"Select a new point on the graph ([ESC] to cancel)")
        self.setFocusPolicy(Qt.StrongFocus)
        self.get_tab().change_end_point = True

    def move_events(self):
        QMessageBox.information(self, "Information", f"You can move the events freely now on the graph ([ESC] to cancel)")
        self.setFocusPolicy(Qt.StrongFocus)
        self.get_tab().change_events = True

    def keyPressEvent(self, event):
        if (self.get_tab().change_starting_point or self.get_tab().change_end_point or self.get_tab().change_events) and event.key() == Qt.Key.Key_Escape:
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
            print('Selectie uitgeschakeld')

    def show_user_manual(self):
        from widget_manual import Manual

        popup = Manual(self)
        popup.show()

    def setup_toolbar(self):
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

    def collect_data(self):
        for filename in os.listdir(self.folder):
            file_path = os.path.join(self.folder, filename)

            if os.path.isdir(file_path):
                continue

            elif filename.endswith(('.xlsx', '.xls', '.xlsm')):
                try:
                    self.extract_excel(file_path)
                except:
                    QMessageBox.critical(self, "Error", f"Failed to get info from: {file_path}!")
                    continue

            elif filename.endswith('.pdf'):
                try:
                    self.add_notes(file_path)
                except:
                    QMessageBox.critical(self, "Error", f"Failed to get info from: {file_path}!")
                    continue

    def extract_excel(self, file):
        from widget_trials import TrailTab, TrialState

        trial_data = pd.read_excel(file)
        trial_number = file.split('.')[-2].split('_')[-1]

        tab = self.tab_widget.widget(int(trial_number) - 1)

        xs = trial_data.iloc[:, 0].values
        if isinstance(tab, TrailTab) and len(xs) > 1:
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

            tab.update_plot(True, self)

    def add_notes(self, file):
        from widget_trials import TrailTab

        pdf = pikepdf.Pdf.open(file)

        trial_number = 0
        in_table = False
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

                    elif 'Trial' in rule_text and int(rule_text.split()[1][:-1]) == trial_number + 1:
                        in_table = False
                        trial_number += 1

                        tab = self.tab_widget.widget(int(trial_number) - 1)
                        if isinstance(tab, TrailTab) and 'score' in rule_text:
                            score = int(rule_text.split()[3])

                            tab.score.setCurrentIndex(score)

                    elif trial_number == 0:
                        continue

                    elif rule_text == 'Table':
                        in_table = True

                    elif rule_text == 'Average over all trials with score 3':
                        break

                    else:
                        if not in_table and rule_text != 'No Notes':
                            tab.notes_input.append(rule_text)

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
        from widget_trials import TrailTab

        tab = TrailTab(self.num_trials, self.tab_widget)
        self.tab_widget.addTab(tab, f"Trial {self.num_trials + 1}")
        self.num_trials += 1

    def update_toolbar(self):
        from widget_trials import TrialState

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
                                      f"Do you really want to reset the data for trial {self.tab_widget.currentIndex() + 1}?",
                                      QMessageBox.Yes | QMessageBox.Cancel)
            if ret == QMessageBox.Yes:
                tab.reset_reading()
                self.update_toolbar()

    def switch_to_next_tab(self):
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
        src_cfg_file = (os.path.join(file_directory, "NEEDED/FILES/first_calibration.g4c"))

        connected = False
        self.dongle_id = None

        attempt = 0

        while self.dongle_id is None and attempt < MAX_ATTEMPTS:
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
        from widget_button_tester import ButtonTester

        popup = ButtonTester(self)
        popup.show()

    def disconnecting_sensors(self):
        self.is_connected = False
        close_sensor()
        self.connection_action.setEnabled(True)
        self.calibrate_action.setEnabled(False)
        self.disconnect_sensor_action.setEnabled(False)
        self.button_trigger = None
        self.connection_button_action.setEnabled(True)
        self.statusBar().showMessage("Successfully disconnected to sensors")
        self.status_widget.set_status("disconnected")
        self.update_toolbar()

    def disconnecting_button(self):
        self.button_trigger = None
        self.connection_button_action.setEnabled(True)
        self.disconnect_button_action.setEnabled(False)
        self.statusBar().showMessage("Successfully disconnected to button")
        self.update_toolbar()

    def calibration(self):
        ret = QMessageBox.Cancel
        if not self.first_calibration:
            ret = QMessageBox.warning(self, "Warning",
                                      "Do you really want to calibrate again?",
                                      QMessageBox.Yes | QMessageBox.Cancel)

        if self.first_calibration or ret == QMessageBox.Yes:
            QMessageBox.information(self, "Info", "Started to calibrate. "
                                                  "Please wait a bit and keep the sensors at a fixed position.")
            try:
                self.hub_id, self.lindex, self.rindex, self.calibration_status = calibration_to_center(self.dongle_id)
            except:
                self.calibration_status = False
            # self.calibration_status = True

            if not self.calibration_status:
                QMessageBox.critical(self, "Warning", "Calibration did not succeed!")
            else:
                self.first_calibration = False
                self.update_toolbar()
                QMessageBox.information(self, "Success", "Successfully callibrated to sensors!")

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

    def process_events(self):
        from widget_trials import TrailTab

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
                print('done')

            tab.update_plot(True)

    def set_automatic_tab(self, button):
        if button.isChecked():
            self.set_automatic = True
        else:
            self.set_automatic = False

    def closeEvent(self, event):
        ret = QMessageBox.warning(self, "Warning",
                                  "Are you sure you want to quit the application?",
                                  QMessageBox.Yes | QMessageBox.Cancel)
        if ret == QMessageBox.Yes:
            if self.thread and self.thread.isRunning():
                self.thread.quit()
                self.thread.wait()

            close_sensor()

            if not pygame.mixer.get_init():
                pygame.mixer.quit()

            event.accept()
        else:
            event.ignore()

    def make_pdf(self):
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

    def download_excel(self):
        while True:
            selection_plot = QDialog(self)
            selection_plot.setWindowTitle("Select graph to save")
            layout = QVBoxLayout()

            # Participant code input
            name_layout = QHBoxLayout()
            name_label = QLabel("Participant code:")
            self.participant_code = QLineEdit()
            self.participant_code.setText(self.id_part)
            name_layout.addWidget(name_label)
            name_layout.addWidget(self.participant_code)
            layout.addLayout(name_layout)

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

            if not self.participant_code.text().strip():
                QMessageBox.warning(self, "Warning", "Participant code is required!")
                continue

            # File and folder selection
            folder = QFileDialog.getExistingDirectory(self, "Select Save Directory", os.path.expanduser("~/Documents"))
            if not folder:
                QMessageBox.warning(self, "Warning", "No directory selected! Please try again.")
                return

            # Create participant folder
            self.participant_folder = os.path.join(folder, self.participant_code.text())

            counter = 0
            while os.path.exists(self.participant_folder):
                counter += 1
                self.participant_folder = os.path.join(folder, self.participant_code.text() + f'({counter})')
            os.makedirs(self.participant_folder, exist_ok=True)
            self.name_pdf = self.participant_code.text()

            if self.thread and self.thread.isRunning():
                self.thread.quit()
                self.thread.wait()

            self.make_progress()
            self.thread = QThread()
            self.worker = ProgressionThread(self, self.pdf, self.participant_folder,
                                            [index for index in range(len(checkboxes)) if
                                             checkboxes[index].isChecked()])
            self.worker.moveToThread(self.thread)

            self.worker.pdf_ready_image.connect(self.add_plots_data)
            self.worker.progress.connect(self.set_progress)
            self.worker.finished_file.connect(self.finish_export)
            self.worker.error_occurred.connect(self.show_error)

            self.thread.started.connect(self.worker.run)
            self.thread.start()

            break

    def add_plots_data(self, plot_index, case, xs, left_data, right_data, events):
        buf = io.BytesIO()

        fig, ax = plt.subplots()

        ax.plot(xs, left_data, label='Left Sensor', color='green')
        ax.plot(xs, right_data, label='Right Sensor', color='red')

        legend_hands = ax.legend()
        ax.add_artist(legend_hands)

        if events[-1] != 0:
            x_positions = [xs[ei] for ei in events]
            if case in [0, 2, 5, 7]:
                y_positions = [left_data[ei] for ei in events[:3]]
                y_positions += [right_data[ei] for ei in events[3:]]
            elif case in [1, 3, 4, 6]:
                y_positions = [right_data[ei] for ei in events[:3]]
                y_positions += [left_data[ei] for ei in events[3:]]
            else:
                return

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

        plt.savefig(buf, format='png', dpi=150, bbox_inches='tight')
        plt.close(fig)

        buf.seek(0)

        self.pdf.image(buf, x=None, y=None, w=100)
        self.pdf.ln(5)

        buf.close()
        self.worker.condition.wakeAll()

    def make_progress(self):
        from widget_progression_bar import ProgressionBar

        self.progression = ProgressionBar()
        self.progression.show()

    def show_error(self, e):
        QMessageBox.critical(self, "Export Error", f"An error occurred during export: {str(e)}")

    def finish_export(self):
        print('finish')
        pdf_file = os.path.join(self.participant_folder, f"{self.name_pdf}.pdf")
        self.pdf.output(pdf_file)

        self.pdf = None
        thread_pdf = threading.Thread(target=self.make_pdf())
        thread_pdf.daemon = True
        thread_pdf.start()

        QMessageBox.information(self, "Success", f"Data saved in folder: {self.participant_folder}")

    def set_progress(self, value: int):
        print(f"Progress: {value}")
        self.progression.set_progress(value)


class ProgressionThread(QThread):
    progress = Signal(int)
    pdf_ready_image = Signal(int, int, list, list, list, list)
    finished_file = Signal()
    error_occurred = Signal(str)

    def __init__(self, parent: MainWindow, pdf, part_folder, check):
        super().__init__()

        self.pdf = pdf
        self.participant_folder = part_folder
        self.checkboxes = check

        self.num_trials = parent.num_trials
        self.main = parent
        self.counter_progress = 0

        active_tabs = self.count_active_tabs()
        if active_tabs == 0: active_tabs = 100
        if len(self.checkboxes) == 0:
            self.step_progress = 1 / active_tabs * 100
        else:
            self.step_progress = 1 / (active_tabs * len(self.checkboxes)) * 100

        self.mutex = QMutex()
        self.condition = QWaitCondition()

    def count_active_tabs(self):
        from widget_trials import TrailTab

        counter_active = 0
        for i in range(self.num_trials):
            tab = self.main.tab_widget.widget(i)

            if isinstance(tab, TrailTab) and len(tab.xs) > 0:
                counter_active += 1
        return counter_active

    def run(self):
        try:
            self.pdf.cell(0, 8, f"Total trials: {self.num_trials}", ln=True)

            for i in range(self.num_trials):
                self.export_tab(i)
                print(f'here {i}')

            self.pdf.add_page()
            self.pdf.set_font("Arial", style="B", size=14)
            self.pdf.cell(0, 10, f"Average over all trials with score 3", ln=True)
            self.pdf.set_font("Arial", size=12)
            print(f'here {self.num_trials + 1}')

            self.average_events_info()
            print(f'here {self.num_trials + 2}')

            self.finished_file.emit()

        except Exception as e:
            self.error_occurred.emit(str(e))

    def export_tab(self, index):
        from widget_trials import TrailTab

        tab = self.main.tab_widget.widget(index)

        if isinstance(tab, TrailTab):
            data = {
                "Time (s)": tab.xs if tab.xs else [],
                "Left Sensor x (cm)": [pos[0] for pos in tab.log_left] if tab.xs else [],
                "Left Sensor y (cm)": [pos[1] for pos in tab.log_left] if tab.xs else [],
                "Left Sensor z (cm)": [pos[2] for pos in tab.log_left] if tab.xs else [],
                "Left Sensor v (m/s)": [pos[3] for pos in tab.log_left] if tab.xs else [],
                "Right Sensor x (cm)": [pos[0] for pos in tab.log_right] if tab.xs else [],
                "Right Sensor y (cm)": [pos[1] for pos in tab.log_right] if tab.xs else [],
                "Right Sensor z (cm)": [pos[2] for pos in tab.log_right] if tab.xs else [],
                "Right Sensor v (m/s)": [pos[3] for pos in tab.log_right] if tab.xs else [],
                "Score: ": [tab.get_score()]
            }
            max_length = max(len(v) for v in data.values())
            for key in data:
                data[key].extend([None] * (max_length - len(data[key])))

            df = pd.DataFrame(data)
            trial_file = os.path.join(self.participant_folder, f"trial_{index + 1}.xlsx")
            df.to_excel(trial_file, index=False)

            self.pdf.set_font("Arial", style="B", size=14)
            self.pdf.cell(0, 10, f"Trial {index + 1}:{f' score {tab.get_score()}' if tab.xs else ''}", ln=True)
            self.pdf.set_font("Arial", size=12)
            notes = tab.notes_input.toPlainText().strip()
            self.pdf.multi_cell(0, 10, notes if notes else "No Notes")
            self.pdf.ln(5)

            if tab.xs:
                for pos_index in self.checkboxes:
                    left_data = [data["Left Sensor x (cm)"] if pos_index == 0 else
                                 data["Left Sensor y (cm)"] if pos_index == 1 else
                                 data["Left Sensor z (cm)"] if pos_index == 2 else
                                 data["Left Sensor v (m/s)"]][0]
                    right_data = [data["Right Sensor x (cm)"] if pos_index == 0 else
                                  data["Right Sensor y (cm)"] if pos_index == 1 else
                                  data["Right Sensor z (cm)"] if pos_index == 2 else
                                  data["Right Sensor v (m/s)"]][0]

                    self.mutex.lock()
                    self.pdf_ready_image.emit(pos_index, tab.case_status, tab.xs, left_data, right_data, tab.event_log)
                    self.condition.wait(self.mutex)
                    self.mutex.unlock()

                    self.counter_progress += self.step_progress
                    self.progress.emit(round(self.counter_progress))

            if self.counter_progress < (index + 1) * self.step_progress:
                self.counter_progress += self.step_progress
                self.progress.emit(round(self.counter_progress))

            if tab.extra_parameters_bim and tab.get_score() == 3:
                self.pdf.set_font("Arial", style="B", size=12)
                self.pdf.cell(0, 10, 'Table', ln=True)

                col_widths = [45, 60, 40]
                self.pdf.set_font('Arial', '', 12)

                data = [
                    ['', 'Parameter', 'Value'],
                    ['Bimanual', 'Total time', str(round(tab.extra_parameters_bim[0], 2))],
                    ['', 'Temporal coupling', str(round(tab.extra_parameters_bim[1], 2))],
                    ['', 'Movement overlap', str(round(tab.extra_parameters_bim[2], 2))],
                    ['', 'Goal synchronization', str(round(tab.extra_parameters_bim[3], 2))],

                    ['Unimanual', 'Time box hand', str(round(tab.extra_parameters_uni[0], 2))],
                    ['', 'Time 1e phase BH', str(round(tab.extra_parameters_uni[1], 2))],
                    ['', 'Time 2e phase BH', str(round(tab.extra_parameters_uni[2], 2))],
                    ['', 'Time trigger hand', str(round(tab.extra_parameters_uni[3], 2))],
                    ['', 'Smoothness BH', str(round(tab.extra_parameters_uni[4], 2))],
                    ['', 'Smoothness TH', str(round(tab.extra_parameters_uni[5], 2))],
                    ['', 'Path length BH', str(round(tab.extra_parameters_uni[6], 2))],
                    ['', 'Path 1e phase BH', str(round(tab.extra_parameters_uni[7], 2))],
                    ['', 'Path 2e phase BH', str(round(tab.extra_parameters_uni[8], 2))],
                    ['', 'Path length TH', str(round(tab.extra_parameters_uni[9], 2))],
                ]

                line_height = 10
                self.pdf.set_fill_color(235, 235, 235)  # lichtgrijs
                self.pdf.set_text_color(0, 0, 0)

                for row_ind, row in enumerate(data):
                    self.pdf.set_x(20)
                    first_row = (row_ind == 0)

                    for col_ind, datum in enumerate(row):
                        fill = first_row or col_ind == 0
                        align = 'L' if col_ind in [0, 1] and row_ind != 0 else 'C'
                        style = 'B' if first_row or col_ind == 0 else ''
                        self.pdf.set_font("Arial", style, size=12)
                        self.pdf.cell(col_widths[col_ind], line_height, datum, border=1, align=align, fill=fill)

                    self.pdf.ln(line_height)

    def average_events_info(self):
        from widget_trials import TrailTab

        average_bim_left = [0] * 4
        average_uni_left = [0] * 10
        left_counter = 0
        average_bim_right = [0] * 4
        average_uni_right = [0] * 10
        right_counter = 0

        for i in range(self.main.tab_widget.count()):
            tab = self.main.tab_widget.widget(i)

            if isinstance(tab, TrailTab) and len(tab.extra_parameters_bim) > 0:
                if tab.case_status == 0 and average_bim_left[0] == 0:
                    average_bim_left = tab.extra_parameters_bim
                    average_uni_left = tab.extra_parameters_uni
                    left_counter = 1
                elif tab.case_status == 1 and average_bim_right[0] == 0:
                    average_bim_right = tab.extra_parameters_bim
                    average_uni_right = tab.extra_parameters_uni
                    right_counter = 1
                elif tab.case_status == 0:
                    average_bim_left = tuple(
                        [a + b for a, b in zip(average_bim_left, tab.extra_parameters_bim)])
                    average_uni_left = tuple(
                        [a + b for a, b in zip(average_uni_left, tab.extra_parameters_uni)])
                    left_counter += 1
                elif tab.case_status == 1:
                    average_bim_right = tuple(
                        [a + b for a, b in zip(average_bim_right, tab.extra_parameters_bim)])
                    average_uni_right = tuple(
                        [a + b for a, b in zip(average_uni_right, tab.extra_parameters_uni)])
                    right_counter += 1

        average_bim_left = tuple([temp / left_counter if left_counter != 0 else 0 for temp in average_bim_left])
        average_uni_left = tuple([temp / left_counter if left_counter != 0 else 0 for temp in average_uni_left])
        average_bim_right = tuple([temp / right_counter if right_counter != 0 else 0 for temp in average_bim_right])
        average_uni_right = tuple([temp / right_counter if right_counter != 0 else 0 for temp in average_uni_right])

        col_widths = [45, 60, 40, 40]
        self.pdf.set_font('Arial', '', 12)

        data = [
            ['', 'Parameter', 'Average left', 'Average right'],
            ['Bimanual', 'Total time', str(round(average_bim_left[0], 2)), str(round(average_bim_right[0], 2))],
            ['', 'Temporal coupling', str(round(average_bim_left[1], 2)), str(round(average_bim_right[1], 2))],
            ['', 'Movement overlap', str(round(average_bim_left[2], 2)), str(round(average_bim_right[2], 2))],
            ['', 'Goal synchronization', str(round(average_bim_left[3], 2)), str(round(average_bim_right[3], 2))],

            ['Unimanual', 'Time box hand', str(round(average_uni_left[0], 2)), str(round(average_uni_right[0], 2))],
            ['', 'Time 1e phase BH', str(round(average_uni_left[1], 2)), str(round(average_uni_right[1], 2))],
            ['', 'Time 2e phase BH', str(round(average_uni_left[2], 2)), str(round(average_uni_right[2], 2))],
            ['', 'Time trigger hand', str(round(average_uni_left[3], 2)), str(round(average_uni_right[3], 2))],
            ['', 'Smoothness BH', str(round(average_uni_left[4], 2)), str(round(average_uni_right[4], 2))],
            ['', 'Smoothness TH', str(round(average_uni_left[5], 2)), str(round(average_uni_right[5], 2))],
            ['', 'Path length BH', str(round(average_uni_left[6], 2)), str(round(average_uni_right[6], 2))],
            ['', 'Path 1e phase BH', str(round(average_uni_left[7], 2)), str(round(average_uni_right[7], 2))],
            ['', 'Path 2e phase BH', str(round(average_uni_left[8], 2)), str(round(average_uni_right[8], 2))],
            ['', 'Path length TH', str(round(average_uni_left[9], 2)), str(round(average_uni_right[9], 2))],
        ]

        line_height = 10
        self.pdf.set_fill_color(235, 235, 235)
        self.pdf.set_text_color(0, 0, 0)

        for row_ind, row in enumerate(data):
            self.pdf.set_x(15)
            first_row = (row_ind == 0)

            for col_ind, datum in enumerate(row):
                fill = first_row or col_ind == 0
                align = 'L' if col_ind in [0, 1] and row_ind != 0 else 'C'
                style = 'B' if first_row or col_ind == 0 else ''
                self.pdf.set_font("Arial", style, size=12)
                self.pdf.cell(col_widths[col_ind], line_height, datum, border=1, align=align, fill=fill)

            self.pdf.ln(line_height)

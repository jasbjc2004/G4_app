import os

import pandas as pd
import pikepdf
import pygame
import threading

from fpdf import FPDF

from PySide6.QtWidgets import (
    QApplication, QVBoxLayout, QMainWindow, QWidget,
    QLineEdit, QLabel, QHBoxLayout, QMessageBox,
    QToolBar, QStatusBar, QTabWidget,
    QFileDialog, QDialog, QCheckBox, QDialogButtonBox,
)
from PySide6.QtGui import QAction
from PySide6.QtCore import QSize
from matplotlib import pyplot as plt

from sensor_G4Track import initialize_system, set_units, get_active_hubs, close_sensor
from data_processing import calibration_to_center

from scipy import signal

from constants import MAX_ATTEMPTS, READ_SAMPLE, SERIAL_BUTTON, fs, fc, ORDER_FILTER


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

        self.resize(1000, 600)

        self.folder = folder
        self.neg_z = neg_z

        self.setup(num_trials)
        self.id_part = id
        self.assessor = asses
        self.date = date
        self.num_trials = num_trials
        self.notes = notes

        self.sound = sound

        nyq = 0.5 * fs
        w = fc / nyq
        self.b, self.a = signal.butter(ORDER_FILTER, w, 'low', analog=False)

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
        absx_action = settings_menu.addAction("Set absolute values to x-axis")
        absx_action.setCheckable(True)
        absx_action.triggered.connect(lambda: self.plot_absolute_x(absx_action))

        negz_action = settings_menu.addAction("Set the negative value of the z-axis")
        negz_action.triggered.connect(self.set_negz)

        self.disconnect_action = settings_menu.addAction("Disconnect")
        self.disconnect_action.setEnabled(False)
        self.disconnect_action.triggered.connect(lambda: self.disconnecting())

        switch_action = settings_menu.addAction("Switch tab automatically")
        switch_action.setCheckable(True)
        switch_action.triggered.connect(lambda: self.set_automatic_tab(switch_action))

        help_menu = menu_bar.addMenu("&Help")
        expl_action = help_menu.addAction("Introduction")
        expl_action.triggered.connect(lambda: self.create_help())

        menu_bar.setNativeMenuBar(False)

    def create_help(self):
        from widget_help import Help

        popup = Help(self)
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
        # self.connection_action.triggered.connect(lambda: self.show_progress_dialog("Connecting...", 100))
        self.connection_action.triggered.connect(lambda: self.connecting())
        toolbar.addAction(self.connection_action)

        self.calibrate_action = QAction("Calibrate", self)
        self.calibrate_action.setEnabled(False)
        self.calibrate_action.setStatusTip("Calibrate the sensor")
        self.calibrate_action.triggered.connect(lambda: self.calibration())
        # self.calibrate_action.triggered.connect(lambda: self.show_progress_dialog("Calibrating...", 100))
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

        self.process_action = QAction("Process trial", self)
        self.process_action.setStatusTip("Process the current trial")
        self.process_action.setEnabled(False)
        self.process_action.triggered.connect(lambda: self.process_tab())
        toolbar.addAction(self.process_action)

        self.event_action = QAction("Events", self)
        self.event_action.setStatusTip("Calculate the events for all trials")
        self.event_action.setEnabled(False)
        self.event_action.triggered.connect(self.process_events)
        self.event_action.setEnabled(True)
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

    def calibrate_message(self):
        self.statusBar().showMessage("Calibrating the sensors...", 5000)

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

        tab = self.tab_widget.widget(int(trial_number)-1)

        xs = trial_data.iloc[:, 0].values
        if isinstance(tab, TrailTab) and len(xs) > 1:
            tab.trial_state = TrialState.completed
            self.update_toolbar()

            tab.xs.clear()
            tab.log_left_plot.clear()
            tab.log_right_plot.clear()

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
                tab.log_left_plot.append( (x1[i], y1[i], z1[i], v1[i], ) )
                tab.log_right_plot.append( (x2[i], y2[i], z2[i], v2[i],) )

            tab.update_plot(True, self)

    def add_notes(self, file):
        from widget_trials import TrailTab

        pdf = pikepdf.Pdf.open(file)

        trial_number = 0
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

                    elif 'Trial' in rule_text and int(rule_text.split()[1][:-1]) == trial_number+1:
                        trial_number += 1

                        tab = self.tab_widget.widget(int(trial_number) - 1)
                        if isinstance(tab, TrailTab) and 'score' in rule_text:
                            score = int(rule_text.split()[3])

                            tab.score.setCurrentIndex(score)

                    elif trial_number == 0:
                        continue

                    else:
                        if rule_text != 'No Notes':
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

        if tab is None or (not self.is_connected and not READ_SAMPLE):
            self.start_action.setEnabled(False)
            self.stop_action.setEnabled(False)
            self.reset_action.setEnabled(False)
            self.process_action.setEnabled(False)
        elif tab.trial_state == TrialState.not_started:
            self.start_action.setEnabled(True)
            self.stop_action.setEnabled(False)
            self.reset_action.setEnabled(False)
            self.process_action.setEnabled(False)
        elif tab.trial_state == TrialState.running:
            self.start_action.setEnabled(False)
            self.stop_action.setEnabled(True)
            self.reset_action.setEnabled(False)
        elif tab.trial_state == TrialState.completed:
            self.start_action.setEnabled(False)
            self.stop_action.setEnabled(False)
            self.reset_action.setEnabled(True)
            self.process_action.setEnabled(True)
        if self.folder and tab.xs:
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

        # Add timeout to prevent infinite loop
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
        self.hub_id, self.lindex, self.rindex, self.calibration_status = calibration_to_center(self.dongle_id)
        # increment(self.dongle_id, self.hub_id, (self.lindex, self.rindex), (0.1, 0.1))

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

    def button_connect(self):
        from widget_button_tester import ButtonTester

        popup = ButtonTester(self)
        popup.show()

    def disconnecting(self):
        self.is_connected = False
        close_sensor()
        self.connection_action.setEnabled(True)
        self.calibrate_action.setEnabled(False)
        self.disconnect_action.setEnabled(False)
        self.button_trigger = None
        self.connection_button_action.setEnabled(True)
        self.statusBar().showMessage("Successfully disconnected to sensors and button")
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
                for index in range(len(tab.log_left_plot)):
                    temp = list(tab.log_left_plot[index])
                    temp[2] = -temp[2]
                    tab.log_left_plot[index] = tuple(temp)

                    temp = list(tab.log_right_plot[index])
                    temp[2] = -temp[2]
                    tab.log_right_plot[index] = tuple(temp)
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
            close_sensor()

            if not pygame.mixer.get_init():
                pygame.mixer.quit()

            event.accept()
        else:
            event.ignore()

    def make_pdf(self):
        self.pdf = FPDF()
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
        from widget_trials import TrailTab

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

            counter = 0
            while os.path.exists(participant_folder):
                counter += 1
                participant_folder = os.path.join(folder, participant_code.text()+f'({counter})')
            os.makedirs(participant_folder, exist_ok=True)

            def export_tab(index):
                QApplication.processEvents()
                tab = self.tab_widget.widget(index)

                if isinstance(tab, TrailTab):
                    # Data export logic (same as your original code)
                    data = {
                        "Time (s)": tab.xs if tab.xs else [],
                        "Left Sensor x (cm)": [pos[0] for pos in tab.log_left_plot] if tab.xs else [],
                        "Left Sensor y (cm)": [pos[1] for pos in tab.log_left_plot] if tab.xs else [],
                        "Left Sensor z (cm)": [pos[2] for pos in tab.log_left_plot] if tab.xs else [],
                        "Left Sensor v (m/s)": [pos[3] for pos in tab.log_left_plot] if tab.xs else [],
                        "Right Sensor x (cm)": [pos[0] for pos in tab.log_right_plot] if tab.xs else [],
                        "Right Sensor y (cm)": [pos[1] for pos in tab.log_right_plot] if tab.xs else [],
                        "Right Sensor z (cm)": [pos[2] for pos in tab.log_right_plot] if tab.xs else [],
                        "Right Sensor v (m/s)": [pos[3] for pos in tab.log_right_plot] if tab.xs else [],
                        "Score: ": [tab.get_score()]
                    }
                    max_length = max(len(v) for v in data.values())
                    for key in data:
                        data[key].extend([None] * (max_length - len(data[key])))

                    df = pd.DataFrame(data)
                    trial_file = os.path.join(participant_folder, f"trial_{index + 1}.xlsx")
                    df.to_excel(trial_file, index=False)

                    self.pdf.set_font("Arial", style="B", size=14)
                    self.pdf.cell(0, 10, f"Trial {index + 1}:{f' score {tab.get_score()}' if tab.xs else ''}", ln=True)
                    self.pdf.set_font("Arial", size=12)
                    notes = tab.notes_input.toPlainText().strip()
                    self.pdf.multi_cell(0, 10, notes if notes else "No Notes")
                    self.pdf.ln(5)

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
                            plt.savefig(plot_filename, dpi=150, bbox_inches='tight')
                            plt.close()
                            self.pdf.image(plot_filename, x=None, y=None, w=100)
                            self.pdf.ln(5)

            def process_tabs():
                try:
                    self.pdf.cell(0, 8, f"Total trials: {self.num_trials}", ln=True)

                    for i in range(self.tab_widget.count()):
                        export_tab(i)

                    # Finalize export
                    pdf_file = os.path.join(participant_folder, f"{participant_code.text()}.pdf")
                    self.pdf.output(pdf_file)

                    self.setEnabled(True)
                    QMessageBox.information(self, "Success", f"Data saved in folder: {participant_folder}")
                except Exception as e:
                    QMessageBox.critical(self, "Export Error", f"An error occurred during export: {str(e)}")
                    self.setEnabled(True)

            # Process tabs and complete export
            process_tabs()
            break

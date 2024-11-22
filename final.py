import math
import sys
import random
import time
from enum import Enum

from PySide6.QtWidgets import (
    QApplication, QVBoxLayout, QMainWindow, QWidget, QPushButton,
    QLineEdit, QLabel, QHBoxLayout, QDateEdit, QTextEdit, QMessageBox,
    QComboBox, QToolBar, QStatusBar, QTabWidget, QProgressDialog
)
from PySide6.QtGui import QAction
from PySide6.QtCore import Qt, QDate, QSize, QTimer
from matplotlib.figure import Figure
from matplotlib.backends.backend_qt5agg import FigureCanvasQTAgg as FigureCanvas

from G4Track import *
from data_processing import calibration_to_center

MAX_TRAILS = 21
READ_MANUEL = True


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
        for i in range(1, MAX_TRAILS):
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
        self.label.setText(f"Number of trials: {selected_number}")

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


class TrialState(Enum):
    NOT_STARTED = "Not Started"
    RUNNING = "Running"
    COMPLETED = "Completed"
    PAUSED = "Paused"


class TrialTab(QWidget):
    def __init__(self, trial_number, parent=None):
        super().__init__(parent)
        self.trial_number = trial_number
        self.trial_state = TrialState.NOT_STARTED
        self.reading_active = False
        self.start_time = None

        self.xs = []
        self.y1s = []
        self.y2s = []

        self.setup_ui()
        self.setup_plot()
        self.setup_timer()

    def setup_ui(self):
        self.layout_tab = QVBoxLayout()

        # Status indicator with better visibility
        self.status_layout = QHBoxLayout()
        self.status_label = QLabel(f"Status: {self.trial_state.value}")
        self.status_label.setStyleSheet("font-weight: bold;")
        self.status_layout.addWidget(self.status_label)
        self.status_layout.addStretch()

        self.layout_tab.addLayout(self.status_layout)
        self.setLayout(self.layout_tab)

    def setup_plot(self):
        # Create figure with specific size and DPI
        self.figure = Figure(figsize=(8, 6), dpi=100)
        self.canvas = FigureCanvas(self.figure)
        self.ax = self.figure.add_subplot(111)

        # Configure plot
        self.ax.set_title(f'Trial {self.trial_number + 1} - Sensor Data')
        self.ax.set_xlabel('Time (s)')
        self.ax.set_ylabel('Coordinates (cm)')
        self.ax.grid(True)

        # Set initial plot ranges
        self.ax.set_ylim(0, 20)
        self.ax.set_xlim(0, 10)

        # Create empty lines
        self.line1, = self.ax.plot([], [], lw=2, label='Left Sensor', color='blue')
        self.line2, = self.ax.plot([], [], lw=2, label='Right Sensor', color='orange')
        self.ax.legend()

        # Add to layout
        self.layout_tab.addWidget(self.canvas)

        # Ensure tight layout
        self.figure.tight_layout()

    def setup_timer(self):
        self.timer = QTimer(self)
        self.timer.timeout.connect(self.update_plot)
        self.timer.setInterval(20)

    def update_status(self):
        self.status_label.setText(f"Status: {self.trial_state.value}")
        main_window = self.window()
        if isinstance(main_window, MainWindow):
            main_window.update_toolbar_buttons()

    def start_trial(self):
        try:
            # Check if other trials are running
            main_window = self.window()
            if not READ_MANUEL and not main_window.is_connected:
                QMessageBox.warning(self, "Warning", "Please connect to sensors first.")
                return

            if self.trial_state in [TrialState.NOT_STARTED, TrialState.PAUSED]:
                if not self.start_time:
                    self.start_time = time.time()

                self.reading_active = True
                self.trial_state = TrialState.RUNNING
                self.timer.start()  # Start the timer for plot updates
                self.update_status()

                msg = "Trial resumed" if self.xs else "Trial started"
                if isinstance(main_window, MainWindow):
                    main_window.statusBar().showMessage(f"Trial {self.trial_number + 1}: {msg}")

        except Exception as e:
            QMessageBox.critical(self, "Error", f"Failed to start trial: {str(e)}")
            self.reading_active = False
            self.timer.stop()

    def stop_trial(self):
        try:
            if self.trial_state == TrialState.RUNNING:
                self.reading_active = False
                self.timer.stop()
                self.trial_state = TrialState.COMPLETED
                self.update_status()

                main_window = self.window()
                if isinstance(main_window, MainWindow):
                    main_window.statusBar().showMessage(f"Trial {self.trial_number + 1} completed")

        except Exception as e:
            QMessageBox.critical(self, "Error", f"Failed to stop trial: {str(e)}")

    def reset_trial(self):
        try:
            if self.trial_state in [TrialState.COMPLETED, TrialState.PAUSED]:
                # Clear all data
                self.xs = []
                self.y1s = []
                self.y2s = []

                # Reset plot lines
                self.line1.set_data([], [])
                self.line2.set_data([], [])

                # Reset time
                self.start_time = None

                # Reset plot limits
                self.ax.set_xlim(0, 10)
                self.ax.set_ylim(0, 20)

                # Redraw
                self.canvas.draw()

                # Reset state
                self.trial_state = TrialState.NOT_STARTED
                self.update_status()

                main_window = self.window()
                if isinstance(main_window, MainWindow):
                    main_window.statusBar().showMessage(f"Trial {self.trial_number + 1} reset")

        except Exception as e:
            QMessageBox.critical(self, "Error", f"Failed to reset trial: {str(e)}")

    def read_sensor_data(self):
        try:
            if not self.start_time:
                return 0, 0, 0

            if READ_MANUEL:
                elapsed_time = time.time() - self.start_time
                # Simulated sensor data with smoother variations
                # Using sine waves for more realistic-looking data
                y1 = 50 + 10 * math.sin(elapsed_time) + random.gauss(0, 2)
                y2 = 50 + 10 * math.cos(elapsed_time) + random.gauss(0, 2)
                return elapsed_time, y1, y2
            else:
                main_window = self.window()
                if isinstance(main_window, MainWindow):
                    if not main_window.is_connected:
                        return 0, 0, 0

                elapsed_time = time.time() - self.start_time
                frame_data, active_count, data_hubs = get_frame_data(main_window.dongle_id, [main_window.hub_id])

                y1 = frame_data.G4_sensor_per_hub[main_window.lindex].pos[1]
                y2 = frame_data.G4_sensor_per_hub[main_window.rindex].pos[1]
                return elapsed_time, abs(y1), abs(y2)

        except Exception as e:
            print(f"Error reading sensor data: {str(e)}")
            return 0, 0, 0

    def update_plot(self):
        try:
            if self.reading_active and self.trial_state == TrialState.RUNNING:
                # Read simulated data
                time_val, y1, y2 = self.read_sensor_data()

                # Update data lists
                self.xs.append(time_val)
                self.y1s.append(y1)
                self.y2s.append(y2)

                max_points = 1000
                if len(self.xs) > max_points:
                    self.xs = self.xs[-max_points:]
                    self.y1s = self.y1s[-max_points:]
                    self.y2s = self.y2s[-max_points:]

                # Update plot data
                self.line1.set_data(self.xs, self.y1s)
                self.line2.set_data(self.xs, self.y2s)

                # Adjust x-axis limit
                if self.xs:
                    current_xlim = self.ax.get_xlim()
                    if self.xs[-1] >= current_xlim[1]:
                        self.ax.set_xlim(self.xs[-1] - 10, self.xs[-1] + 1)

                # Adjust y-axis limits if needed
                if self.y1s or self.y2s:
                    ymax = max(max(self.y1s), max(self.y2s)) + 5
                    self.ax.set_ylim(0, ymax)

                # Redraw canvas
                self.canvas.draw()

        except Exception as e:
            print(f"Error updating plot: {str(e)}")
            self.timer.stop()
            self.reading_active = False


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

        self.resize(800, 600)
        self.setup_ui(num_trials)

    def setup_ui(self, num_trials):
        # Create central widget and main layout
        self.central_widget = QWidget()
        self.setCentralWidget(self.central_widget)
        self.main_layout = QVBoxLayout()
        self.central_widget.setLayout(self.main_layout)

        # Menu bar
        menu_bar = self.menuBar()
        file_menu = menu_bar.addMenu("&File")
        save_action = file_menu.addAction("Save")
        file_menu.addSeparator()
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
        self.setup_toolbar()

        # Create tab widget
        self.tab_widget = QTabWidget()
        # Connect tab change signal to our custom handler
        self.tab_widget.currentChanged.connect(self.handle_tab_change)
        # Store the current tab index
        self.last_tab_index = 0

        for i in range(0, num_trials):
            trial_tab = TrialTab(i, self.tab_widget)
            self.tab_widget.addTab(trial_tab, f"Trial {i + 1}")

        self.main_layout.addWidget(self.tab_widget)

        # Status bar
        self.setStatusBar(QStatusBar(self))
        # Initial toolbar button update
        self.update_toolbar_buttons()

    def handle_tab_change(self, index):
        # Get the previous tab
        previous_tab = self.tab_widget.widget(self.last_tab_index)

        # If previous tab is running a trial, prevent the tab change
        if (previous_tab and
                isinstance(previous_tab, TrialTab) and
                previous_tab.trial_state == TrialState.RUNNING):

            # Block the signal temporarily to avoid recursive calls
            self.tab_widget.blockSignals(True)
            # Revert to the previous tab
            self.tab_widget.setCurrentIndex(self.last_tab_index)
            self.tab_widget.blockSignals(False)

            # Show warning message
            QMessageBox.warning(
                self,
                "Tab Switch Prevented",
                "Cannot switch tabs while a trial is running.\nPlease stop the current trial first."
            )
        else:
            # If no trial is running, update the last tab index
            self.last_tab_index = index

            # Update toolbar buttons for the new tab
            self.update_toolbar_buttons()

    # test functions
    def setup_toolbar(self):
        self.toolbar = QToolBar("My main toolbar")
        self.toolbar.setIconSize(QSize(32, 32))  # Make buttons more visible
        self.addToolBar(Qt.TopToolBarArea, self.toolbar)  # Specify toolbar area

        self.connect_action = QAction("Connect", self)
        self.connect_action.setStatusTip("Connect to sensors")
        self.connect_action.triggered.connect(self.connecting)
        if READ_MANUEL:
            self.connect_action.setEnabled(False)
        self.toolbar.addAction(self.connect_action)

        self.calibrate = QAction("Calibrate", self)
        self.calibrate.setStatusTip("Calibrate if it didn't work previously")
        self.calibrate.triggered.connect(self.calibrating)
        if READ_MANUEL | (not self.is_connected):
            self.calibrate.setEnabled(False)
        self.toolbar.addAction(self.calibrate)

        self.toolbar.addSeparator()

        # Create actions with better visual feedback
        self.start_action = QAction("Start Trial", self)
        self.start_action.setStatusTip("Start the current trial")
        self.toolbar.addAction(self.start_action)
        self.start_action.triggered.connect(self.start_current_trial)

        self.stop_action = QAction("Stop Trial", self)
        self.stop_action.setStatusTip("Stop the current trial")
        self.toolbar.addAction(self.stop_action)
        self.stop_action.triggered.connect(self.stop_current_trial)

        self.reset_action = QAction("Reset Trial", self)
        self.reset_action.setStatusTip("Reset the current trial")
        self.toolbar.addAction(self.reset_action)
        self.reset_action.triggered.connect(self.reset_current_trial)

        self.toolbar.addSeparator()

        self.quit_action = QAction("Quit", self)
        self.quit_action.setStatusTip("Exit the application")
        self.toolbar.addAction(self.quit_action)
        self.quit_action.triggered.connect(self.close)

    def get_current_tab(self):
        current_tab = self.tab_widget.currentWidget()
        if isinstance(current_tab, TrialTab):
            return current_tab
        return None

    def update_toolbar_buttons(self):
        current_tab = self.get_current_tab()
        if not current_tab:
            # Disable all buttons if no valid tab is selected
            self.start_action.setEnabled(False)
            self.stop_action.setEnabled(False)
            self.reset_action.setEnabled(False)
            return

        can_start = READ_MANUEL or self.is_connected

        # Update button states based on current trial state
        if current_tab.trial_state == TrialState.NOT_STARTED:
            self.start_action.setEnabled(True)
            self.stop_action.setEnabled(False)
            self.reset_action.setEnabled(False)
        elif current_tab.trial_state == TrialState.RUNNING:
            self.start_action.setEnabled(False)
            self.stop_action.setEnabled(True)
            self.reset_action.setEnabled(False)
        elif current_tab.trial_state == TrialState.COMPLETED:
            self.start_action.setEnabled(False)
            self.stop_action.setEnabled(False)
            self.reset_action.setEnabled(True)
        elif current_tab.trial_state == TrialState.PAUSED:
            self.start_action.setEnabled(can_start)
            self.stop_action.setEnabled(False)
            self.reset_action.setEnabled(True)

    def start_current_trial(self):
        current_tab = self.get_current_tab()
        if current_tab:
            try:
                current_tab.start_trial()
                # Disable tab bar when trial starts
                self.tab_widget.tabBar().setEnabled(False)
            except Exception as e:
                QMessageBox.critical(self, "Error", f"Failed to start trial: {str(e)}")
                self.statusBar().showMessage("Error starting trial")

    def stop_current_trial(self):
        current_tab = self.get_current_tab()
        if current_tab:
            try:
                current_tab.stop_trial()
                # Re-enable tab bar when trial stops
                self.tab_widget.tabBar().setEnabled(True)
            except Exception as e:
                QMessageBox.critical(self, "Error", f"Failed to stop trial: {str(e)}")
                self.statusBar().showMessage("Error stopping trial")

    def reset_current_trial(self):
        current_tab = self.get_current_tab()
        if current_tab:
            try:
                # Check if the trial is in a state that can be reset
                if current_tab.trial_state not in [TrialState.COMPLETED, TrialState.PAUSED]:
                    QMessageBox.warning(
                        self,
                        "Reset Failed",
                        "Can only reset trials that are completed or paused."
                    )
                    return

                # Ask for confirmation before resetting
                reply = QMessageBox.question(
                    self,
                    'Confirm Reset',
                    'Are you sure you want to reset this trial? All data will be lost.',
                    QMessageBox.Yes | QMessageBox.No,
                    QMessageBox.No
                )

                if reply == QMessageBox.Yes:
                    # Reset the trial
                    current_tab.reset_trial()

                    # Re-enable the tab bar if it was disabled
                    self.tab_widget.tabBar().setEnabled(True)

                    # Update status
                    self.statusBar().showMessage(f"Trial {current_tab.trial_number + 1} has been reset")

                    # Update toolbar buttons to reflect new state
                    self.update_toolbar_buttons()

            except Exception as e:
                QMessageBox.critical(
                    self,
                    "Error",
                    f"Failed to reset trial: {str(e)}"
                )
                self.statusBar().showMessage("Error resetting trial")

    def connecting(self):
        if self.is_connected:
            QMessageBox.information(self, "Info", "Already connected to sensors!")
            return

        try:
            # Create and configure progress dialog
            progress = QProgressDialog("Connecting to sensors...", "Cancel", 0, 100, self)
            progress.setWindowTitle("Connecting")
            progress.setWindowModality(Qt.WindowModal)
            progress.setAutoClose(True)
            progress.setAutoReset(True)
            progress.setValue(0)
            progress.show()

            # Initialize variables
            max_attempts = 10
            attempt = 0
            file_directory = os.path.dirname(os.path.abspath(__file__))
            src_cfg_file = os.path.join(file_directory, "first_calibration.g4c")

            while attempt < max_attempts and not progress.wasCanceled():
                # Update progress
                current_progress = (attempt * 100) // max_attempts
                progress.setValue(current_progress)

                # Attempt connection
                connected, self.dongle_id = initialize_system(src_cfg_file)

                if connected and self.dongle_id is not None:
                    progress.setValue(100)
                    self.hub_id, self.lindex, self.rindex = calibration_to_center(self.dongle_id)
                    self.is_connected = True
                    self.connect_action.setEnabled(False)
                    self.statusBar().showMessage("Successfully connected to sensors")
                    progress.close()
                    QMessageBox.information(self, "Success", "Successfully connected to sensors!")
                    return

                attempt += 1
                QApplication.processEvents()  # Keep UI responsive

            # If we get here, connection failed
            progress.close()
            if progress.wasCanceled():
                QMessageBox.warning(self, "Connection Canceled", "Connection attempt was canceled.")
            else:
                QMessageBox.critical(self, "Error", "Failed to connect to sensors after multiple attempts!")

        except Exception as e:
            QMessageBox.critical(self, "Error", f"Error connecting to sensors: {str(e)}")
            self.is_connected = False

    def calibrating(self):
        if self.is_connected:
            self.hub_id, self.lindex, self.rindex = calibration_to_center(self.dongle_id)

    def closeEvent(self, event):
        # Add confirmation dialog before closing
        reply = QMessageBox.question(
            self, 'Confirm Exit',
            'Are you sure you want to exit? Any unsaved data will be lost.',
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No
        )

        if reply == QMessageBox.Yes:
            event.accept()
        else:
            event.ignore()


if __name__ == "__main__":
    app = QApplication(sys.argv)
    startup = StartUp()
    startup.show()
    app.exec()


import logging
import random
import time

import serial
from PySide6.QtCore import QThread, Signal

from sensor_G4Track import get_frame_data
from constants import READ_SAMPLE, BEAUTY_SPEED
from widget_settings import manage_settings

fs = manage_settings.get("Sensors", "fs")
SERIAL_BUTTON = manage_settings.get("General", "SERIAL_BUTTON")

logging.basicConfig(
    filename='logboek.txt',
    level=logging.ERROR,
    format='%(asctime)s - %(levelname)s - %(message)s'
)


class ReadThread(QThread):
    """
    Thread to read the data when plotting the data --> possible to get 120 Hz without letting the program wait
    """
    lost_connection = Signal()

    def __init__(self, parent):
        super().__init__(parent)

        self.start_time = None
        self.stop_read = False
        self.tab = None
        self.sensor_died = 10

    def start_tab_reading(self, tab):
        self.tab = tab
        global fs, SERIAL_BUTTON
        fs = manage_settings.get("Sensors", "fs")
        SERIAL_BUTTON = manage_settings.get("General", "SERIAL_BUTTON")
        self.sensor_died = 10

    def stop_current_reading(self):
        self.tab = None
        self.start_time = None
        self.sensor_died = 10

    def run(self):
        self.stop_read = False

        while not self.stop_read:
            try:
                if self.tab is not None and not self.start_time:
                    self.start_time = time.time()

                if self.tab is not None:
                    self.read_sensor_data()
                else:
                    self.keep_sensor_alive()
            except Exception as e:
                logging.error(e, exc_info=True)
                print(f"Error in read_sensor_data: {e}")
                time.sleep(0.5)

            time.sleep(1/fs)

    def stop(self):
        self.stop_read = True
        self.start_time = None

    def keep_sensor_alive(self):
        """
        Needed to lower the delay when starting a reading
        """
        main_window = self.parent()

        if not READ_SAMPLE:
            get_frame_data(main_window.dongle_id, [main_window.hub_id])
            print('here')

    def read_sensor_data(self):
        """
        Read the sensor data (and also some test cases) & adds it to the log
        """
        from window_main_plot import MainWindow
        from widget_trials import TrailTab

        if self.tab is None:
            print("Warning: read_sensor_data called with None tab")
            return

        main_window = self.parent()
        if not (self.tab and main_window and isinstance(self.tab, TrailTab) and isinstance(main_window, MainWindow)):
            return

        elapsed_time = time.time() - self.start_time

        try:
            if SERIAL_BUTTON and main_window.button_trigger is not None:
                try:
                    line = '1'
                    while main_window.button_trigger.in_waiting > 0:
                        line = main_window.button_trigger.readline().decode('utf-8').rstrip()

                    if line == '0':
                        self.tab.button_pressed = True
                except serial.SerialException as e:
                    print(f"Failed to connect to COM3: {e}")

            if not READ_SAMPLE:
                if isinstance(main_window, MainWindow):
                    if not main_window.is_connected:
                        self.tab.xs.append(len(self.tab.xs) / fs)
                        self.tab.log_left.append((0, 0, 0, 0))
                        self.tab.log_right.append((0, 0, 0, 0))

                frame_data, active_count, data_hubs = get_frame_data(main_window.dongle_id,
                                                                     [main_window.hub_id])

                if (active_count, data_hubs) == (1, 1):
                    time_now = len(self.tab.xs) / fs
                    pos1 = tuple(frame_data.G4_sensor_per_hub[main_window.lindex].pos)
                    pos1 = tuple([pos1[i] if i != 2 else -pos1[i] for i in range(3)])
                    pos1 += (self.tab.speed_calculation(pos1, time_now, len(self.tab.xs) - 1, True),)

                    pos2 = tuple(frame_data.G4_sensor_per_hub[main_window.rindex].pos)
                    pos2 = tuple([pos2[i] if i != 2 else -pos2[i] for i in range(3)])
                    pos2 += (self.tab.speed_calculation(pos2, time_now, len(self.tab.xs) - 1, False),)

                    self.tab.xs.append(len(self.tab.xs) / fs)
                    self.tab.log_left.append(pos1)
                    self.tab.log_right.append(pos2)

            elif BEAUTY_SPEED:
                elapsed_time = len(self.tab.xs) / fs
                self.tab.xs.append(elapsed_time)

                if elapsed_time < 5:
                    pos1 = (0, 0, elapsed_time,)
                    pos2 = (0, elapsed_time, 0,)

                elif elapsed_time < 10:
                    pos1 = (0, 0, 5 - (elapsed_time - 5),)
                    pos2 = (0, 5 - (elapsed_time - 5), 0,)

                elif elapsed_time < 15:
                    pos1 = (0, 0, 5 * (elapsed_time - 10),)
                    pos2 = (0, 5 * (elapsed_time - 10), 0,)

                elif elapsed_time < 20:
                    pos1 = (0, 0, 25 - 5 * (elapsed_time - 15),)
                    pos2 = (0, 25 - 5 * (elapsed_time - 15), 0,)

                else:
                    pos1 = (0, 0, 0,)
                    pos2 = (0, 0, 0,)

                self.tab.log_left.append(
                    pos1 + (self.tab.speed_calculation(pos1, self.tab.xs[-1], len(self.tab.xs) - 1, True),))
                self.tab.log_right.append(
                    pos2 + (self.tab.speed_calculation(pos2, self.tab.xs[-1], len(self.tab.xs) - 1, False),))

            else:
                pos1 = (random.randint(-20, 20), random.randint(0, 20), random.randint(-20, 0))
                pos2 = (random.randint(-20, 20), random.randint(0, 20), random.randint(-20, 0))

                self.tab.xs.append(elapsed_time)
                self.tab.log_left.append(
                    pos1 + (self.tab.speed_calculation(pos1, self.tab.xs[-1], len(self.tab.xs) - 1, True),))
                self.tab.log_right.append(
                    pos2 + (self.tab.speed_calculation(pos2, self.tab.xs[-1], len(self.tab.xs) - 1, False),))

            if self.tab and self.tab.button_pressed:
                self.stop_current_reading()

            if self.tab and self.tab.log_left[3] == 0:
                print('here')
                self.lost_connection.emit()
        except:
            return

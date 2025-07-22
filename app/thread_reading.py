#import logging
import random
import time

import numpy as np
import serial
from PySide6.QtCore import QThread, Signal

from sensor_G4Track import get_frame_data
from constants import READ_SAMPLE, BEAUTY_SPEED
from widget_settings import manage_settings

fs = manage_settings.get("Sensors", "fs")
SERIAL_BUTTON = manage_settings.get("General", "SERIAL_BUTTON")
MAX_INTERFERENCE_SPEED = manage_settings.get("General", "MAX_INTERFERENCE_SPEED")
TIME_INTERFERENCE_SPEED = manage_settings.get("General", "TIME_INTERFERENCE_SPEED")

"""
logging.basicConfig(
    filename='logboek.txt',
    level=logging.ERROR,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
"""


class ReadThread(QThread):
    """
    Thread to read the data when plotting the data --> possible to get 120 Hz without letting the program wait
    """
    lost_connection = Signal()
    interference = Signal()
    done_reading = Signal()

    def __init__(self, parent):
        super().__init__(parent)

        self.start_time = None
        self.stop_read = False
        self.tab = None
        self.sensor_died = 10
        self.send_interference = False
        self.speed1 = []
        self.speed2 = []

    def start_tab_reading(self, tab):
        self.tab = tab
        global fs, SERIAL_BUTTON, MAX_INTERFERENCE_SPEED, TIME_INTERFERENCE_SPEED
        fs = manage_settings.get("Sensors", "fs")
        MAX_INTERFERENCE_SPEED = manage_settings.get("General", "MAX_INTERFERENCE_SPEED")
        TIME_INTERFERENCE_SPEED = manage_settings.get("General", "TIME_INTERFERENCE_SPEED")
        self.sensor_died = 10
        self.send_interference = False
        self.speed1 = []
        self.speed2 = []

    def stop_current_reading(self):
        print(len(self.tab.xs))
        self.tab = None
        self.start_time = None
        self.sensor_died = 10
        self.send_interference = False
        self.speed1 = []
        self.speed2 = []
        self.done_reading.emit()

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
                #logging.error(e, exc_info=True)
                print(f"Error in read_sensor_data: {e}")
                time.sleep(0.5)

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
                        print(len(self.tab.xs))
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
                    v1 = self.tab.speed_calculation(pos1, time_now, len(self.tab.xs) - 1, True)
                    pos1 += (v1,)

                    pos2 = tuple(frame_data.G4_sensor_per_hub[main_window.rindex].pos)
                    pos2 = tuple([pos2[i] if i != 2 else -pos2[i] for i in range(3)])
                    v2 = self.tab.speed_calculation(pos2, time_now, len(self.tab.xs) - 1, False)
                    pos2 += (v2,)

                    self.tab.xs.append(len(self.tab.xs) / fs)
                    self.tab.log_left.append(pos1)
                    self.tab.log_right.append(pos2)

                    self.speed1.append(v1)
                    self.speed1 = self.speed1[-fs*TIME_INTERFERENCE_SPEED:]
                    self.speed2.append(v2)
                    self.speed2 = self.speed2[-fs * TIME_INTERFERENCE_SPEED:]

                    if not self.send_interference and max(self.speed1) - min(self.speed1) > MAX_INTERFERENCE_SPEED and \
                            max(self.speed2) - min(self.speed2) > MAX_INTERFERENCE_SPEED:
                        print('here')
                        self.send_interference = True
                        self.interference.emit()

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
                self.lost_connection.emit()
        except:
            return

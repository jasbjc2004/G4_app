#import logging
import random
import time

import serial
from PySide6.QtCore import QThread, Signal

from logger import get_logbook
from sensor_G4Track import get_frame_data, get_frame_data_with_c_list
from constants import READ_SAMPLE, BEAUTY_SPEED
from widget_settings import manage_settings

import ctypes as ct

fs = manage_settings.get("Sensors", "fs")
HUBS = 1
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

        self.dongle = None
        self.tab = None
        self.sensor_died = 10
        self.send_interference = False
        self.speed1 = []
        self.speed2 = []
        self.logger = get_logbook('thread_reading')
        self.HUB_ID_ARRAY = (ct.c_int * HUBS)()

        self.interval = 1 / fs

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

        self.interval = 1 / fs

    def stop_current_reading(self):
        print(len(self.tab.xs))
        self.tab = None
        self.sensor_died = 10
        self.send_interference = False
        self.speed1 = []
        self.speed2 = []
        self.done_reading.emit()

        self.interval = 1 / fs

    def run(self):
        ct.windll.winmm.timeBeginPeriod(1)

        main_window = self.parent()
        from window_main_plot import MainWindow
        if isinstance(main_window, MainWindow):
            self.HUB_ID_ARRAY[0] = main_window.hub_id
            self.dongle = main_window.dongle_id

        next_time = time.perf_counter()

        while not self.isInterruptionRequested():
            try:
                if self.tab is not None:
                    self.read_sensor_data()
                else:
                    self.keep_sensor_alive()

            except Exception as e:
                self.logger.critical(f"Problem with reading the sensor data: {e}", exc_info=True)
                QThread.msleep(int(0.5*1000))
                next_time = time.perf_counter() + self.interval

            next_time += self.interval
            sleep_time = next_time - time.perf_counter()
            if sleep_time > 0:
                time.sleep(sleep_time)

    def keep_sensor_alive(self):
        """
        Needed to lower the delay when starting a reading
        """

        if not READ_SAMPLE and self.dongle:
            get_frame_data_with_c_list(self.dongle, self.HUB_ID_ARRAY)

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

        try:
            if not READ_SAMPLE:
                if isinstance(main_window, MainWindow):
                    if not main_window.is_connected:
                        self.tab.xs.append(len(self.tab.xs) / fs)
                        self.tab.log_left.append((0, 0, 0, 0))
                        self.tab.log_right.append((0, 0, 0, 0))

                frame_data, active_count, data_hubs = get_frame_data_with_c_list(main_window.dongle_id, self.HUB_ID_ARRAY)

                if (active_count, data_hubs) != (1, 1):
                    return

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
                """
                self.speed1.append(v1)
                self.speed1 = self.speed1[-fs*TIME_INTERFERENCE_SPEED:]
                self.speed2.append(v2)
                self.speed2 = self.speed2[-fs * TIME_INTERFERENCE_SPEED:]

                if not self.send_interference and max(self.speed1) - min(self.speed1) > MAX_INTERFERENCE_SPEED and \
                        max(self.speed2) - min(self.speed2) > MAX_INTERFERENCE_SPEED:
                    print('here')
                    self.send_interference = True
                    self.interference.emit()
                """
            elif BEAUTY_SPEED:
                QThread.msleep(int(1/fs * 1000))
                time_now = len(self.tab.xs) / fs

                if time_now < 5:
                    pos1 = (0, 0, -5*time_now,)
                    pos2 = (0, 5*time_now, 0,)

                elif time_now < 10:
                    pos1 = (0, 0, -25+5*(time_now-5),)
                    pos2 = (0, 25-5*(time_now-5), 0,)

                elif time_now < 15:
                    pos1 = (0, 0, -20 * (time_now - 10),)
                    pos2 = (0, 20 * (time_now - 10), 0,)

                elif time_now < 20:
                    pos1 = (0, 0, -100 + 20 * (time_now - 15),)
                    pos2 = (0, 100 - 20 * (time_now - 15), 0,)

                else:
                    pos1 = (0, 0, 0,)
                    pos2 = (0, 0, 0,)

                pos1 = tuple([pos1[i] if i != 2 else -pos1[i] for i in range(3)])
                v1 = self.tab.speed_calculation(pos1, time_now, len(self.tab.xs) - 1, True)
                pos1 += (v1,)

                pos2 = tuple([pos2[i] if i != 2 else -pos2[i] for i in range(3)])
                v2 = self.tab.speed_calculation(pos2, time_now, len(self.tab.xs) - 1, False)
                pos2 += (v2,)

                self.tab.xs.append(len(self.tab.xs) / fs)
                self.tab.log_left.append(pos1)
                self.tab.log_right.append(pos2)

            else:
                #QThread.msleep(int(1/fs * 1000))
                time_now = len(self.tab.xs) / fs

                pos1 = (random.randint(-20, 20), random.randint(0, 20), random.randint(-20, 0))
                pos2 = (random.randint(-20, 20), random.randint(0, 20), random.randint(-20, 0))

                pos1 = tuple([pos1[i] if i != 2 else -pos1[i] for i in range(3)])
                v1 = self.tab.speed_calculation(pos1, time_now, len(self.tab.xs) - 1, True)
                pos1 += (v1,)

                pos2 = tuple([pos2[i] if i != 2 else -pos2[i] for i in range(3)])
                v2 = self.tab.speed_calculation(pos2, time_now, len(self.tab.xs) - 1, False)
                pos2 += (v2,)

                self.tab.xs.append(len(self.tab.xs) / fs)
                self.tab.log_left.append(pos1)
                self.tab.log_right.append(pos2)

            if SERIAL_BUTTON and main_window.button_trigger is not None:
                try:
                    line = '1'
                    while main_window.button_trigger.in_waiting > 0:
                        line = main_window.button_trigger.readline().decode('utf-8').rstrip()

                    if line == '0':
                        self.tab.button_pressed = True
                        print(len(self.tab.xs))
                except serial.SerialException as e:
                    self.logger.warning(f"Failed to connect to button: {e}", exc_info=True)
                    print(f"Failed to connect to button: {e}")

            if self.tab and self.tab.button_pressed:
                self.stop_current_reading()

            if self.tab and self.tab.log_left[3] == 0:
                self.lost_connection.emit()
        except:
            return

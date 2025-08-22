import math
import random
import time

import serial
from PySide6.QtCore import QThread, Signal, QMutex, QWaitCondition

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

ADD_DATA = False
SLEEP_NEEDED = True


class ReadThread(QThread):
    """
    Thread to read the data when plotting the data --> possible to get 120 Hz without letting the program wait
    """
    lost_connection = Signal()
    interference = Signal()
    done_reading = Signal()

    def __init__(self, parent):
        super().__init__(parent)

        self.first_frame = 0
        self.timer_beauty = None
        self.dongle = None
        self.tab = None
        self.sensor_died = 10
        self.send_interference = False
        self.speed1 = []
        self.speed2 = []
        self.logger = get_logbook('thread_reading')
        self.HUB_ID_ARRAY = (ct.c_int * HUBS)()

        self._pause_mutex = QMutex()
        self._pause_condition = QWaitCondition()
        self._paused = False
        self._paused_flag = False

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
        self.timer_beauty = time.perf_counter()

    def stop_current_reading(self):
        print(len(self.tab.xs))
        self.tab = None
        self.sensor_died = 10
        self.send_interference = False
        self.speed1 = []
        self.speed2 = []
        self.done_reading.emit()

        self.interval = 1 / fs
        self.timer_beauty = None

    def pause(self):
        self._pause_mutex.lock()
        self._paused = True
        self._pause_mutex.unlock()

    def resume(self):
        self._pause_mutex.lock()
        self._paused = False
        self._pause_condition.wakeAll()
        self._pause_mutex.unlock()

    def wait_until_paused(self):
        while not self._paused_flag:
            QThread.msleep(10)

    def run(self):
        ct.windll.winmm.timeBeginPeriod(1)

        main_window = self.parent()
        from window_main_plot import MainWindow
        if isinstance(main_window, MainWindow) and main_window.dongle_id and main_window.hub_id:
            self.HUB_ID_ARRAY[0] = main_window.hub_id
            self.dongle = main_window.dongle_id

        next_time = -1

        while not self.isInterruptionRequested():
            self._pause_mutex.lock()
            if self._paused:
                self._paused_flag = True
                self._pause_condition.wait(self._pause_mutex)
                self._paused_flag = False
            self._pause_mutex.unlock()

            try:
                if self.tab is not None:
                    self.read_sensor_data()
                    if next_time == -1:
                        next_time = time.perf_counter()
                        timer_samples = time.perf_counter()
                else:
                    self.keep_sensor_alive()
                    next_time = -1

            except Exception as e:
                self.logger.critical(f"Problem with reading the sensor data: {e}", exc_info=True)
                QThread.msleep(int(0.5 * 1000))
                next_time = time.perf_counter() + self.interval

            if next_time != -1:
                next_time += self.interval
                sleep_time = next_time - time.perf_counter()
            else:
                sleep_time = self.interval

            if sleep_time > 0 and SLEEP_NEEDED:
                time.sleep(sleep_time)
            elif ADD_DATA and (BEAUTY_SPEED or READ_SAMPLE) and self.tab is not None and len(self.tab.xs) > 1:
                extra_time = abs(sleep_time)
                samples_missed = math.ceil(extra_time / self.interval)
                if extra_time > self.interval:
                    last_data = [self.tab.log_left[-1], self.tab.log_right[-1]]
                    snd_last_data = [self.tab.log_left[-2], self.tab.log_right[-2]]

                    diff_left = [(last - prev) / (samples_missed + 1)
                                 for last, prev in zip(last_data[0][:3], snd_last_data[0][:3])]
                    diff_right = [(last - prev) / (samples_missed + 1)
                                  for last, prev in zip(last_data[1][:3], snd_last_data[1][:3])]

                    base_time = self.tab.xs[-2]
                    for i in range(0, samples_missed):
                        interpolated_time = base_time + (i + 1) / fs

                        left_data = tuple([pos_i + (i + 1) * diff_i
                                           for pos_i, diff_i in zip(snd_last_data[0][0:3], diff_left)])
                        left_data += (
                        self.tab.speed_calculation(left_data, interpolated_time, len(self.tab.xs) - 2, True),)
                        right_data = tuple([pos_i + (i + 1) * diff_i
                                            for pos_i, diff_i in zip(snd_last_data[1][0:3], diff_right)])
                        right_data += (
                        self.tab.speed_calculation(right_data, interpolated_time, len(self.tab.xs) - 2, False),)

                        self.tab.log_left.insert(-1, left_data)
                        self.tab.log_right.insert(-1, right_data)
                        self.tab.xs.insert(-1, interpolated_time)
                        next_time += self.interval

                    time_now = (len(self.tab.xs) - 1) / fs
                    left_data = self.tab.log_left[-1][:3]
                    left_data += (self.tab.speed_calculation(left_data, time_now, len(self.tab.xs) - 2, True),)
                    right_data = self.tab.log_right[-1][:3]
                    right_data += (self.tab.speed_calculation(right_data, time_now, len(self.tab.xs) - 2, False),)

                    self.tab.xs[-1] = time_now
                    self.tab.log_left[-1] = left_data
                    self.tab.log_right[-1] = right_data

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

                frame_data, active_count, data_hubs = get_frame_data_with_c_list(main_window.dongle_id,
                                                                                 self.HUB_ID_ARRAY)

                if (active_count, data_hubs) != (1, 1):
                    return

                if len(self.tab.xs) == 0:
                    self.first_frame = frame_data.frame

                time_now = (frame_data.frame - self.first_frame) / fs

                if len(self.tab.xs) > 1:
                    last_frame = round(self.tab.xs[-1] * fs)
                    samples_missed = round(time_now * fs) - (last_frame + 1)
                    if samples_missed > 0: print(samples_missed)
                else:
                    samples_missed = 1

                if samples_missed < 0:
                    return

                pos1 = tuple(frame_data.G4_sensor_per_hub[main_window.lindex].pos)
                pos1 = tuple([pos1[i] if i != 2 else -pos1[i] for i in range(3)])

                pos2 = tuple(frame_data.G4_sensor_per_hub[main_window.rindex].pos)
                pos2 = tuple([pos2[i] if i != 2 else -pos2[i] for i in range(3)])

                if ADD_DATA and len(self.tab.xs) > 1 and samples_missed > 0:
                    print(samples_missed)
                    last_data = [self.tab.log_left[-1], self.tab.log_right[-1]]
                    snd_last_data = [self.tab.log_left[-2], self.tab.log_right[-2]]

                    diff_left = [(last - prev) / (samples_missed + 1)
                                 for last, prev in zip(last_data[0][:3], snd_last_data[0][:3])]
                    diff_right = [(last - prev) / (samples_missed + 1)
                                  for last, prev in zip(last_data[1][:3], snd_last_data[1][:3])]

                    base_time = self.tab.xs[-2]
                    for i in range(0, samples_missed):
                        interpolated_time = base_time + (i + 1) / fs

                        left_data = tuple([pos_i + (i + 1) * diff_i
                                           for pos_i, diff_i in zip(snd_last_data[0][0:3], diff_left)])
                        left_data += (
                            self.tab.speed_calculation(left_data, interpolated_time, len(self.tab.xs) - 2, True),)
                        right_data = tuple([pos_i + (i + 1) * diff_i
                                            for pos_i, diff_i in zip(snd_last_data[1][0:3], diff_right)])
                        right_data += (
                            self.tab.speed_calculation(right_data, interpolated_time, len(self.tab.xs) - 2, False),)

                        self.tab.log_left.append(left_data)
                        self.tab.log_right.append(right_data)
                        self.tab.xs.append(interpolated_time)

                v1 = self.tab.speed_calculation(pos1, time_now, len(self.tab.xs) - 1, True)
                v2 = self.tab.speed_calculation(pos2, time_now, len(self.tab.xs) - 1, False)

                pos1 += (v1,)
                pos2 += (v2,)

                self.tab.xs.append(time_now)
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
                if len(self.tab.xs) == 0:
                    self.timer_beauty = time.perf_counter()
                else:
                    jitter = random.uniform(-self.interval, +2 * self.interval)
                    time.sleep(max(0, self.interval + jitter))
                time_now = len(self.tab.xs) / fs

                exp_time = round((time.perf_counter() - self.timer_beauty) * fs) / fs
                if exp_time < time_now:
                    return
                if exp_time < 5:
                    pos1 = (0, 0, -5 * exp_time,)
                    pos2 = (0, 5 * exp_time, 0,)

                elif exp_time < 10:
                    pos1 = (0, 0, -25 + 5 * (exp_time - 5),)
                    pos2 = (0, 25 - 5 * (exp_time - 5), 0,)

                elif exp_time < 15:
                    pos1 = (0, 0, -20 * (exp_time - 10),)
                    pos2 = (0, 20 * (exp_time - 10), 0,)

                elif exp_time < 20:
                    pos1 = (0, 0, -100 + 20 * (exp_time - 15),)
                    pos2 = (0, 100 - 20 * (exp_time - 15), 0,)

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
                # QThread.msleep(int(1/fs * 1000))
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

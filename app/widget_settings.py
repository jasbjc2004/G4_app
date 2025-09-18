import json
import os
import shutil
import sys
import threading

import pygame
from PySide6.QtCore import Qt, QRegularExpression
from PySide6.QtGui import QIcon, QDoubleValidator, QValidator, QPixmap, \
    QColor, QPainter, QPainterPath
from PySide6.QtWidgets import QDialog, QVBoxLayout, QLabel, QPushButton, QHBoxLayout, QListWidget, \
    QStackedWidget, QListWidgetItem, QWidget, QFrame, QLineEdit, QCheckBox, QMessageBox, QComboBox, \
    QGraphicsOpacityEffect, QSizePolicy, QFileDialog

from constants import COLORS, NAME_APP
from logger import get_logbook

# Styles for the buttons in settings
invisible_style = """
                    QPushButton {
                        background-color: transparent;
                        border: none;
                        padding-left: 2px;
                        font-size: 20px;
                    }
                """
invisible_style_reset = """
                            QPushButton {
                                background-color: transparent;
                                border: none;
                            }
                        """
invisible_style_check = """
                            QPushButton {
                                background-color: transparent;
                                color: transparent;
                                font-size: 14px;
                                font-weight: bold;
                                padding: 0px 0px 2px 0px;
                                margin: 0px;
                                spacing: 0px;
                                text-align: center;
                            }
                            QPushButton:hover {
                                color: rgba(255, 255, 255, 0.5);
                                background-color: rgba(255, 0, 0, 0.2);
                            }
                            QPushButton:checked {
                                background-color: red;
                                color: white;
                            }
                        """


class SettingsManager:
    def __init__(self, config_file='constants.json'):
        """Class to manage all the settings: loading at the beginning, applying changes and resetting to default"""
        if getattr(sys, 'frozen', False):
            # Running as packaged executable
            appdata_dir = os.path.join(os.path.expanduser('~'), 'AppData', 'Roaming', NAME_APP)
            os.makedirs(appdata_dir, exist_ok=True)
            self.config_file = os.path.join(appdata_dir, config_file)
        else:
            # Running from source (PyCharm/development)
            file_directory = os.path.dirname(os.path.abspath(__file__))
            self.config_file = os.path.join(file_directory, config_file)

        self.settings = {}
        self.logger = get_logbook('widget_settings')

        # Create default settings if needed (only for packaged version)
        if getattr(sys, 'frozen', False) and not os.path.exists(self.config_file):
            self.create_default_settings()

        self.load_settings()

    def load_settings(self):
        try:
            if os.path.exists(self.config_file):
                with open(self.config_file, 'r') as set:
                    self.settings = json.load(set)
            else:
                self.create_default_settings()
        except:
            self.create_default_settings()

    def create_default_settings(self):
        self.settings = {
            "General": {
                "MAX_TRIALS": 20,
                "SERIAL_BUTTON": True,
                "USE_NEURAL_NET": True,
                "MAX_INTERFERENCE_SPEED": 20,
                "TIME_INTERFERENCE_SPEED": 0.3
            },
            "Calibration": {
                "LONG_CALIBRATION": True,
                "POSITION_BUTTON": [0, 15.2, 2.3],
                "SIZE_BASE_BOX": [12.9, 9.7],
                "THRESHOLD_CALIBRATION": 0.01,
                "MAX_ATTEMPTS_CALIBRATION": 5
            },
            "Sensors": {
                "fs": 120,
                "fc": 10,
                "SENSORS_USED": 2,
                "MAX_ATTEMPTS_CONNECT": 10,
            },
            "Data-processing": {
                "ORDER_FILTER": 2,
                "ORDER_EXTREMA": 10,
                "SPEED_FILTER": True,
                "MAX_HEIGHT_NEEDED": 2,
                "MAX_LENGTH_NEEDED": 2,
                "MIN_HEIGHT_NEEDED": 3,
                "MIN_LENGTH_NEEDED": 3,
                "THRESHOLD_BOTH_HANDS": 20,
                "THRESHOLD_CHANGED_HANDS_MEAS": 20,
                "SPEED_THRESHOLD": 0.05,
                "HEIGHT_BOX": 15,
            },
            "Events": {
                "NUMBER_EVENTS": 6,
                "COLORS_EVENT": ["Blue", "Purple", "Orange", "Yellow", "Pink", "Black"],
                "LABEL_EVENT": ["e1", "e2", "e3", "e4", "e5", "e6"]
            }
        }
        self.save_settings()

    def save_settings(self):
        """Save current settings to JSON file"""
        try:
            with open(self.config_file, 'w') as f:
                json.dump(self.settings, f, indent=4)
            print(f"Settings saved to {self.config_file}")
            return True
        except Exception as e:
            self.logger.error(e, exc_info=True)
            print(f"Error saving settings: {e}")
            return False

    def get(self, category, key):
        """Get a specific setting value"""
        return self.settings.get(category, {}).get(key)

    def get_category(self, category):
        """Get all specific setting value of a category"""
        return self.settings.get(category, {})

    def set(self, category, key, value):
        """Set a specific setting value"""
        self.settings[category][key] = value

    def reload_settings(self):
        """Reload settings from file"""
        self.load_settings()


manage_settings = SettingsManager()


class Settings(QDialog):
    def __init__(self, parent=None):
        """
        Settings to change the constant values
        """
        super().__init__(parent)
        self.setWindowTitle("Settings")
        file_directory = (os.path.dirname(os.path.abspath(__file__)))
        dir_icon = os.path.join(file_directory, 'NEEDED/PICTURES/hands.ico')
        self.setWindowIcon(QIcon(dir_icon))
        self.setGeometry(400, 100, 800, 500)

        self.setWindowFlags(Qt.Window)
        self.setModal(True)

        self.current_music = None
        self.current_timer = None
        self.del_music_button = []

        file_directory = (os.path.dirname(os.path.abspath(__file__)))
        if getattr(sys, 'frozen', False):
            # Running as packaged executable
            user_music_folder = os.path.join(os.path.expanduser('~'), 'AppData', 'Roaming', NAME_APP, 'MUSIC')
            if not os.path.exists(user_music_folder) or not os.listdir(user_music_folder):
                self.music_folder = os.path.join(file_directory, 'NEEDED/MUSIC')
            else:
                self.music_folder = user_music_folder
        else:
            # Running from source (PyCharm/development)
            self.music_folder = os.path.join(file_directory, 'NEEDED/MUSIC')
        self.basic_music_folder = os.path.join(file_directory, 'NEEDED/BASIC_MUSIC')

        layout = QVBoxLayout()
        page_main_layout = QHBoxLayout()

        self.list_widget = QListWidget()
        self.list_widget.setFixedWidth(150)

        menu = ['General', "Calibration", 'Sensors', 'Data-processing', 'Events', 'Music']
        for tab in menu:
            QListWidgetItem(tab, self.list_widget)

        self.stack = QStackedWidget()

        self.pages = []
        self.var_widget = {}
        for tab in menu:
            page = QWidget()
            page_layout = QVBoxLayout(page)

            # add heading
            label = QLabel(f"{tab}")
            label.setStyleSheet("font-weight: bold; font-size: 14px;")
            page_layout.addWidget(label)

            # add line
            line = QFrame()
            line.setFrameShape(QFrame.HLine)
            line.setFrameShadow(QFrame.Sunken)
            page_layout.addWidget(line)

            # fill values
            variabels_tab = manage_settings.get_category(tab)
            for variabel, value in variabels_tab.items():
                var_layout = QHBoxLayout()

                var_box = QLabel(variabel.replace("_", " ").capitalize())
                var_box.setFixedWidth(250)
                var_box.setAlignment(Qt.AlignLeft | Qt.AlignVCenter)
                var_layout.addWidget(var_box)

                var_layout.addStretch()
                if isinstance(value, bool):
                    value_box = QCheckBox()
                    value_box.setChecked(value)
                    value_box.setFixedWidth(100)
                    var_layout.addWidget(value_box)
                    page_layout.addLayout(var_layout)
                    self.var_widget[(tab, variabel)] = value_box
                elif isinstance(value, list):
                    item_list = []
                    for index in range(len(value)):
                        if variabel == "COLORS_EVENT":
                            item_edit = DistinctColorComboBox()
                            item_edit.set_selected_color(str(value[index]))
                        else:
                            item_edit = QLineEdit()
                            item_edit.setText(str(value[index]))
                        item_edit.setFixedWidth(100)
                        var_layout.addWidget(item_edit, alignment=Qt.AlignRight)
                        page_layout.addLayout(var_layout)
                        var_layout = QHBoxLayout()
                        item_list.append(item_edit)
                        if tab == 'Calibration':
                            validator = SinglePointDoubleValidator(0.01, 1000.0, 2)
                            item_edit.setValidator(validator)
                    self.var_widget[(tab, variabel)] = item_list
                else:
                    value_box = QLineEdit()
                    value_box.setText(str(value))
                    value_box.setFixedWidth(100)
                    if variabel == "NUMBER_EVENTS" or variabel == "SENSORS_USED":
                        value_box.setReadOnly(True)
                        value_box.setCursor(Qt.ArrowCursor)  # standaard muispijl
                        value_box.setStyleSheet("""
                            QLineEdit {
                                color: gray;
                                background-color: #f0f0f0;
                            }
                        """)
                        value_box.setFocusPolicy(Qt.NoFocus)
                    var_layout.addWidget(value_box)
                    page_layout.addLayout(var_layout)
                    self.var_widget[(tab, variabel)] = value_box
                    if variabel in ['MAX_TRIALS', "SENSORS_USED", "MAX_ATTEMPTS_CONNECT",
                                    "MAX_ATTEMPTS_CALIBRATION", "ORDER_FILTER", "ORDER_EXTREMA"]:
                        validator = IntPointlessValidator(r'^[0-9]*$', 1, 1000)
                        value_box.setValidator(validator)
                    else:
                        if variabel == "THRESHOLD_CALIBRATION":
                            validator = SinglePointDoubleValidator(0.0001, 1000.0, 4)
                        else:
                            validator = SinglePointDoubleValidator(0.01, 1000.0, 2)
                        value_box.setValidator(validator)

            if tab == 'Music':
                self.music_page_layout = page_layout
                music_layout = QHBoxLayout()
                music_layout.setSpacing(2)
                music_layout.setContentsMargins(0, 0, 0, 0)
                music_layout.addStretch()

                fixed_height = 24

                plus_button = QPushButton("+")
                plus_button.setStyleSheet(invisible_style)
                plus_button.clicked.connect(lambda: self.add_music())
                plus_button.setFixedWidth(25)
                plus_button.setFixedHeight(fixed_height)
                plus_button.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Fixed)
                music_layout.addWidget(plus_button)

                min_button = QPushButton("-")
                min_button.setStyleSheet(invisible_style)
                min_button.clicked.connect(lambda: self.delete_music())
                min_button.setFixedWidth(25)
                min_button.setFixedHeight(fixed_height)
                min_button.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Fixed)
                music_layout.addWidget(min_button)

                music_layout.addSpacing(8)

                reset_button = QPushButton("Reset")
                reset_button.setStyleSheet(invisible_style_reset)
                reset_button.clicked.connect(lambda: self.reset_music())
                reset_button.setFixedHeight(fixed_height)
                reset_button.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Fixed)
                music_layout.addWidget(reset_button)

                page_layout.addLayout(music_layout)

                for music_dir, sound in self.parent().sound:
                    self.add_music_widget(music_dir, sound)
            else:
                page_layout.addStretch()
            self.stack.addWidget(page)
            self.pages.append(page)

        self.list_widget.currentRowChanged.connect(self.stack.setCurrentIndex)

        page_main_layout.addWidget(self.list_widget)
        page_main_layout.addWidget(self.stack)

        layout.addLayout(page_main_layout)

        button_layout = QHBoxLayout()
        self.apply_button = QPushButton("Apply")
        self.apply_button.clicked.connect(self.apply)
        self.apply_button.setDefault(True)

        self.cancel_button = QPushButton("Cancel")
        self.cancel_button.clicked.connect(self.close)

        self.reset_button = QPushButton("Reset")
        self.reset_button.clicked.connect(self.reset)

        button_layout.addStretch()

        button_layout.addWidget(self.apply_button)
        button_layout.addWidget(self.cancel_button)
        button_layout.addWidget(self.reset_button)

        layout.addLayout(button_layout)

        self.list_widget.setCurrentRow(0)
        self.setLayout(layout)

    def add_music_widget(self, music_dir, sound):
        """
        Add the widget so every one has the same lay-out
        :param music_dir: the dir of the music file
        :param sound: the sound made with pygame
        """
        item = self.music_page_layout.itemAt(self.music_page_layout.count() - 1)
        if item.spacerItem() is not None:
            self.music_page_layout.takeAt(self.music_page_layout.count() - 1)

        music_layout = QHBoxLayout()
        music_layout.setContentsMargins(5, 5, 2, 2)
        music_layout.setSpacing(20)

        var_button = QPushButton("x")
        var_button.setStyleSheet(invisible_style_check)
        var_button.setCheckable(True)
        var_button.setFixedSize(20, 20)
        music_layout.addWidget(var_button)
        self.del_music_button.append((var_button, music_dir, sound))

        var_box = QLabel(os.path.basename(music_dir))
        var_box.setFixedWidth(300)
        music_layout.addWidget(var_box)

        music_layout.addStretch()

        var_button = QPushButton("▶")
        var_button.setStyleSheet(invisible_style)
        var_button.clicked.connect(lambda checked=False, s=sound: self.play_music(s))
        var_button.setFixedWidth(40)
        music_layout.addWidget(var_button)
        self.music_page_layout.addLayout(music_layout)

        self.music_page_layout.addStretch()

    def add_music(self):
        """
        Add music to the list, so this one is played with the press of the button
        """
        music_file, _ = QFileDialog.getOpenFileName(
            self,
            "Select a Music File",
            os.path.expanduser("~/Documents"),
            "Audio Files (*.mp3 *.wav *.ogg *.flac)"
        )

        if not music_file:
            return

        if not pygame.mixer.get_init():
            pygame.mixer.init()

        sound = pygame.mixer.Sound(music_file)
        self.parent().sound.append((music_file, sound))
        shutil.copy2(music_file, self.music_folder)

        self.add_music_widget(music_file, sound)

    def delete_music(self):
        """
        Delete the selected music out of the list, so this one isn't playes anymore. This is using the checkboxes in
        front of the text/ music
        """
        number_selected = 0
        for item in self.del_music_button:
            button, music_dir, sound = item
            if button.isChecked():
                number_selected += 1

        if number_selected == 0:
            return

        if number_selected == len(self.parent().sound):
            QMessageBox.warning(self, "Warning", "It is not possible to remove all the music-files. Reset first")
            return

        ret = QMessageBox.warning(self, "Warning",
                                  "Do you really want to delete these music-files?",
                                  QMessageBox.Yes | QMessageBox.Cancel)
        if ret == QMessageBox.Cancel:
            return

        print(len(self.parent().sound))

        for item in self.del_music_button:
            button, music_dir, sound = item
            if button.isChecked():
                self.del_music_button.remove(item)

                if os.path.isfile(music_dir):
                    os.remove(music_dir)

        self.reset_music(False)
        print(self.parent().sound)
        print(len(self.parent().sound))

    def reset_music(self, full=True):
        """
        if full is True: Delete all the music and upload the basic ones again. Else: reset the lay-out
        of the settings-menu
        :param full: a parameter to delete all (True) or just update the lay-out (False)
        """
        if full:
            ret = QMessageBox.warning(self, "Warning",
                                      "Do you really want to reset the music-files?",
                                      QMessageBox.Yes | QMessageBox.Cancel)
            if ret == QMessageBox.Cancel:
                return

        for i in reversed(range(self.music_page_layout.count())):
            item = self.music_page_layout.itemAt(i)

            if item.layout():
                sub_layout = item.layout()
                count = sub_layout.count()

                if count == 0:
                    self.music_page_layout.takeAt(i)
                    continue

                last_item = sub_layout.itemAt(count - 1)
                widget = last_item.widget()

                if isinstance(widget, QPushButton) and widget.text() == 'Reset':
                    break

                self.music_page_layout.takeAt(i)

                while sub_layout.count():
                    inner_item = sub_layout.takeAt(0)
                    if inner_item.widget():
                        inner_item.widget().setParent(None)
                    elif inner_item.layout():
                        print('found some layout extra')

            elif item.spacerItem() is not None:
                self.music_page_layout.takeAt(i)

        self.parent().sound = []
        if full:
            for filename in os.listdir(self.music_folder):
                file_path = os.path.join(self.music_folder, filename)
                if os.path.isfile(file_path):
                    os.remove(file_path)

        if full:
            music_folder = self.basic_music_folder
        else:
            music_folder = self.music_folder

        for music_file in os.listdir(music_folder):
            file_path = os.path.join(music_folder, music_file)
            if full:
                shutil.copy2(file_path, self.music_folder)
                file_path = os.path.join(self.music_folder, music_file)

            if not pygame.mixer.get_init():
                pygame.mixer.init()

            sound = pygame.mixer.Sound(file_path)
            self.parent().sound.append((file_path, sound))

            self.add_music_widget(file_path, sound)

    def apply(self):
        """Save the changes to the json-file"""
        changes_made = False
        never_save = False
        empty_widgets = []

        for (category, variabel), widget in self.var_widget.items():
            old_value = manage_settings.get(category, variabel)

            if isinstance(widget, QCheckBox):
                value = widget.isChecked()
            elif isinstance(widget, list):
                value = []
                for sub_widget in widget:
                    if isinstance(sub_widget, QComboBox):
                        value.append(sub_widget.currentText())
                    else:
                        text = sub_widget.text()
                        if not text or text == "":
                            never_save = True
                            empty_widgets.append(sub_widget)
                        elif text:
                            try:
                                if '.' in text:
                                    value.append(float(text))
                                    if float(text) == 0 and not variabel == 'POSITION_BUTTON':
                                        never_save = True
                                        empty_widgets.append(sub_widget)
                                else:
                                    value.append(int(text))
                                    if int(text) == 0 and not variabel == 'POSITION_BUTTON':
                                        never_save = True
                                        empty_widgets.append(sub_widget)
                            except ValueError:
                                value.append(text)
                        sub_widget.setStyleSheet("")
            else:
                text = widget.text()
                if not text or text == "":
                    never_save = True
                    empty_widgets.append(widget)
                elif text:
                    try:
                        if '.' in text:
                            value = float(text)
                            if value == 0:
                                never_save = True
                                empty_widgets.append(widget)
                        else:
                            value = int(text)
                            if value == 0:
                                never_save = True
                                empty_widgets.append(widget)
                    except ValueError:
                        value = text

                if not variabel == "NUMBER_EVENTS" and not variabel == "SENSORS_USED":
                    widget.setStyleSheet("")

            if not never_save and old_value != value:
                manage_settings.set(category, variabel, value)
                changes_made = True

        if never_save:
            for widget in empty_widgets:
                widget.setStyleSheet("background-color: #ffe5e5;")
            QMessageBox.warning(self, "Error", "One or more fields are empty or zero!")
        elif changes_made:
            if manage_settings.save_settings():
                self.parent().update_plot()
                self.parent().update_toolbar()
                QMessageBox.information(self, "Success", "Settings saved successfully!")
            else:
                QMessageBox.warning(self, "Error", "Failed to save settings!")

    def reset(self):
        """Reset all settings to default values or to the default music according to selected page"""
        current_tab = self.list_widget.currentRow()

        if current_tab == 5:
            self.reset_music(True)
            return

        reply = QMessageBox.warning(self, "Warning", "Are you sure you want to reset all settings to default values?",
                                    QMessageBox.Yes | QMessageBox.No, QMessageBox.No)

        if reply == QMessageBox.Yes:
            manage_settings.create_default_settings()
            self.refresh_ui()
            QMessageBox.information(self, "Info", "All settings are back to their default values")

    def refresh_ui(self):
        """Refresh the UI to reflect current settings"""
        for (category, variabel), widget in self.var_widget.items():
            value = manage_settings.get(category, variabel)

            if isinstance(widget, QCheckBox):
                widget.setChecked(value)
            elif isinstance(widget, list):
                for i, sub_widget in enumerate(widget):
                    if isinstance(sub_widget, DistinctColorComboBox):
                        sub_widget.set_selected_color(str(value[i]))
                    else:
                        if i < len(value):
                            sub_widget.setText(str(value[i]))
                        else:
                            sub_widget.setText("")
                        sub_widget.setStyleSheet("")
            else:
                widget.setText(str(value))
                if not variabel == "NUMBER_EVENTS" and not variabel == "SENSORS_USED":
                    widget.setStyleSheet("")

        self.parent().update_plot()
        self.parent().update_toolbar()

    def play_music(self, sound):
        """
        Play the music of the sound, as a sample
        :param sound: the sound of pygame
        """
        if self.current_timer is not None:
            self.current_timer.cancel()
        if self.current_music is not None:
            self.current_music.stop()

        self.current_music = sound.play()
        self.current_timer = threading.Timer(2.0, self.stop_music)
        self.current_timer.start()

    def stop_music(self):
        if self.current_music is not None:
            self.current_music.stop()


# Extra validators to ensure the right values are set in the settings
class IntPointlessValidator(QValidator):
    def __init__(self, pattern, min_val, max_val):
        """
        Make sure the user doesn't add a point to the int-value
        :param pattern: the tokens that can be used
        :param min_val: minimum value
        :param max_val: maximum value
        """
        super().__init__()
        self.regex = QRegularExpression(pattern)
        self.min_val = min_val
        self.max_val = max_val

    def validate(self, input_str: str, pos: int) -> object:
        """
        Check if the string in correct or not
        """
        if input_str == "":
            return QValidator.Intermediate, input_str, pos

        if not self.regex.match(input_str).hasMatch():
            return QValidator.Invalid, input_str, pos

        try:
            value = int(input_str)

            if self.min_val is not None and value < self.min_val:
                return QValidator.Invalid, input_str, pos

            if self.max_val is not None and value > self.max_val:
                return QValidator.Invalid, input_str, pos

        except ValueError:
            pass

        return QValidator.Acceptable, input_str, pos


class SinglePointDoubleValidator(QDoubleValidator):
    def __init__(self, min_val, max_val, decimals):
        """
        Make sure there is only one point and the value can also start with a point
        :param min_val: minimum value
        :param max_val: maximum value
        :param decimals: numbers of decimals permitted
        """
        super().__init__(min_val, max_val, decimals)
        self.min_val = min_val
        self.max_val = max_val
        self.decimals = decimals

    def validate(self, input_str, pos):
        """
        Check if the string in correct or not
        """
        if input_str == "":
            return QValidator.Intermediate, input_str, pos

        if input_str.count('.') > 1:
            return QValidator.Invalid, input_str, pos

        if '.' in input_str:
            decimal_part = input_str.split('.')[1]
            if len(decimal_part) > self.decimals:
                return QValidator.Invalid, input_str, pos

        try:
            if input_str == '.':
                return QValidator.Intermediate, input_str, pos
            elif input_str.endswith('.'):
                value = float(input_str[:-1]) if input_str[:-1] else 0.0
            elif input_str.startswith('.'):
                value = float('0' + input_str)
            else:
                value = float(input_str)

            is_potentially_incomplete = False

            # Single digit could be start of larger number
            if len(input_str) == 1 and input_str.isdigit():
                is_potentially_incomplete = True
            # Ends with decimal point - clearly incomplete
            elif input_str.endswith('.') and not input_str.startswith('.'):
                is_potentially_incomplete = True

            if is_potentially_incomplete:
                return QValidator.Intermediate, input_str, pos

            # Only enforce range on complete numbers
            """
            if value < self.min_val:
                min_str = f"{self.min_val}"
                return QValidator.Acceptable, min_str, len(min_str)
            """
            if value > self.max_val:
                return QValidator.Invalid, input_str, pos

        except ValueError:
            return QValidator.Invalid, input_str, pos

        # Use the parent's validation for everything else
        return super().validate(input_str, pos)


class DistinctColorComboBox(QComboBox):
    def __init__(self):
        """
        Make a color box with colors inside of them, so it gives a better visual effect
        """
        super().__init__()

        colors = COLORS

        for hex_color, name in colors:
            # Create larger preview for better visibility
            pixmap = QPixmap(20, 20)
            pixmap.fill(Qt.transparent)

            painter = QPainter(pixmap)
            painter.setRenderHint(QPainter.Antialiasing)
            painter.setBrush(QColor(hex_color))
            painter.setPen(Qt.NoPen)

            circle = QPainterPath()
            circle.addEllipse(2, 2, 16, 16)
            painter.drawPath(circle)
            painter.end()

            # Add border for white color visibility
            if hex_color == "#FFFFFF":
                painter = QPainter(pixmap)
                painter.setPen(QColor("#000000"))
                painter.drawRect(0, 0, 19, 15)
                painter.end()

            self.addItem(pixmap, name, hex_color)

    def get_selected_color(self):
        return self.currentData()

    def set_selected_color(self, color):
        for i in range(self.count()):
            if self.itemText(i).lower() == color.lower():
                self.setCurrentIndex(i)
                return True
        return False

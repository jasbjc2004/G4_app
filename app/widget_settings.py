import json
import os

from PySide6.QtCore import Qt, QRegularExpression
from PySide6.QtGui import QIcon, QDoubleValidator, QValidator, QPixmap, \
    QColor, QPainter, QPainterPath
from PySide6.QtWidgets import QDialog, QVBoxLayout, QLabel, QPushButton, QHBoxLayout, QListWidget, \
    QStackedWidget, QListWidgetItem, QWidget, QFrame, QLineEdit, QCheckBox, QMessageBox, QComboBox, \
    QGraphicsOpacityEffect

from constants import COLORS


class SettingsManager:
    """Class to manage all the settings: loading at the beginning, applying changes and resetting to default"""
    def __init__(self, config_file='constants.json'):
        file_directory = (os.path.dirname(os.path.abspath(__file__)))
        self.config_file = os.path.join(file_directory, config_file)
        self.settings = {}
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
              "General":  {
                "MAX_TRIALS": 20,
                "SERIAL_BUTTON": True,
                "USE_NEURAL_NET": True
              },
              "Sensors":  {
                "fs": 120,
                "fc": 10,
                "SENSORS_USED": 2,
                "MAX_ATTEMPTS_CONNECT": 10
              },
              "Data-processing": {
                "ORDER_FILTER": 2,
                "SPEED_FILTER": True,
                "MAX_HEIGHT_NEEDED": 2,
                "MAX_LENGTH_NEEDED": 2,
                "MIN_HEIGHT_NEEDED": 3,
                "MIN_LENGTH_NEEDED": 3,
                "POSITION_BUTTON": [0,15,1.5],
                "THRESHOLD_BOTH_HANDS": 20,
                "THRESHOLD_CHANGED_HANDS_MEAS": 20,
                "SPEED_THRESHOLD": 0.05,
                "HEIGHT_BOX": 15,
                "THRESHOLD_CALIBRATION": 0.01,
                "MAX_ATTEMPTS_CALIBRATION": 5
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
    """
    Settings to change the constant values
    """
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Settings")
        file_directory = (os.path.dirname(os.path.abspath(__file__)))
        dir_icon = os.path.join(file_directory, 'NEEDED/PICTURES/hands.ico')
        self.setWindowIcon(QIcon(dir_icon))
        self.setGeometry(400, 100, 800, 500)

        self.setWindowFlags(Qt.Window)
        self.setModal(True)

        layout = QVBoxLayout()
        page_main_layout = QHBoxLayout()

        self.list_widget = QListWidget()
        self.list_widget.setFixedWidth(150)

        menu = ['General', 'Sensors', 'Data-processing', 'Events']
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
                var_box.setFixedWidth(150)
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
                    if tab == 'General' or variabel == "SENSORS_USED" or variabel == "MAX_ATTEMPTS_CONNECT":
                        validator = IntPointlessValidator(r'^[0-9]*$', 1, 1000)
                        value_box.setValidator(validator)
                    else:
                        validator = SinglePointDoubleValidator(0.001, 1000.0, 2)
                        value_box.setValidator(validator)

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
                                else:
                                    value.append(int(text))
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
                        else:
                            value = int(text)
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
            QMessageBox.warning(self, "Error", "One or more fields are empty!")
        elif changes_made:
            if manage_settings.save_settings():
                self.parent().update_plot()
                QMessageBox.information(self, "Success", "Settings saved successfully!")
            else:
                QMessageBox.warning(self, "Error", "Failed to save settings!")

    def reset(self):
        """Reset all settings to default values"""
        reply = QMessageBox.question(self, "Reset Settings",
                                     "Are you sure you want to reset all settings to default values?",
                                     QMessageBox.Yes | QMessageBox.No,
                                     QMessageBox.No)

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


class IntPointlessValidator(QValidator):
    def __init__(self, pattern, min_val, max_val):
        super().__init__()
        self.regex = QRegularExpression(pattern)
        self.min_val = min_val
        self.max_val = max_val

    def validate(self, input_str: str, pos: int) -> object:
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
        super().__init__(min_val, max_val, decimals)
        self.min_val = min_val
        self.max_val = max_val
        self.decimals = decimals

    def validate(self, input_str, pos):
        if input_str == "":
            return QValidator.Intermediate, input_str, pos

        if input_str.count('.') > 1:
            return QValidator.Invalid, input_str, pos

        if '.' in input_str:
            decimal_part = input_str.split('.')[1]
            if len(decimal_part) > self.decimals:
                return QValidator.Invalid, input_str, pos

        try:
            # Handle partial input like "123." or ".5"
            if input_str == '.':
                return QValidator.Intermediate, input_str, pos
            elif input_str.endswith('.'):
                value = float(input_str[:-1]) if input_str[:-1] else 0.0
            elif input_str.startswith('.'):
                value = float('0' + input_str)
            else:
                value = float(input_str)

            # Enforce min/max range
            if value < self.min_val or value > self.max_val:
                return QValidator.Invalid, input_str, pos

        except ValueError:
            return QValidator.Invalid, input_str, pos

        # Use the parent's validation for everything else
        return super().validate(input_str, pos)


class DistinctColorComboBox(QComboBox):
    def __init__(self):
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

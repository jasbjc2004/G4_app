import os
import sys
import threading

import pygame
from PySide6.QtGui import QIcon
from PySide6.QtWidgets import (
    QVBoxLayout, QPushButton, QLineEdit, QLabel, QHBoxLayout,
    QDateEdit, QTextEdit, QMessageBox, QComboBox, QDialog, QCheckBox, QFileDialog, QApplication,
)
from PySide6.QtCore import QDate, QSize

from constants import NAME_APP
from widget_settings import manage_settings

import pikepdf

from window_main_plot import MainWindow

MAX_TRIALS = manage_settings.get("General", "MAX_TRIALS")


class SetUp(QDialog):
    def __init__(self, folder=None):
        """
        Window to add all the important data and load all the music in advance when user is filling in data
        :param folder: the folder where the old data is located
        """
        super().__init__()

        self.setWindowTitle("Setup")
        file_directory = (os.path.dirname(os.path.abspath(__file__)))
        dir_icon = os.path.join(file_directory, 'NEEDED/PICTURES/hands.ico')
        self.setWindowIcon(QIcon(dir_icon))

        file_directory = (os.path.dirname(os.path.abspath(__file__)))

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
        for i in range(1, MAX_TRIALS + 1):
            self.combo_box.addItem(str(i), i)

        self.label = QLabel("Number of trials: ")
        print(MAX_TRIALS)
        if MAX_TRIALS >= 10:
            self.combo_box.setCurrentIndex(9)
        else:
            self.combo_box.setCurrentIndex(MAX_TRIALS - 1)

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

        dir_layout = QHBoxLayout()
        map_button = QPushButton()
        map_button.clicked.connect(self.browse_dir)
        map_icon = QIcon(os.path.join(file_directory, 'NEEDED/PICTURES/map.png'))
        map_button.setIcon(map_icon)
        map_button.setIconSize(QSize(15, 15))
        dir_layout.addWidget(map_button)
        self.path = QLineEdit()
        self.full_path = ""
        if folder:
            self.set_dir(folder)
        else:
            self.set_dir(os.path.expanduser("~/Documents"))
        self.path.setReadOnly(True)
        dir_layout.addWidget(self.path)

        # Additional Notes
        notes_layout = QVBoxLayout()
        notes_label = QLabel("Additional Notes:")
        self.notes_input = QTextEdit()
        notes_layout.addWidget(notes_label)
        notes_layout.addWidget(self.notes_input)

        # assessor
        assessor_layout = QHBoxLayout()
        assessor_label = QLabel("Assessor:            ")
        self.assessor_input = QLineEdit()
        assessor_layout.addWidget(assessor_label)
        assessor_layout.addWidget(self.assessor_input)

        self.negative_z = QCheckBox(text="Negative z in the data")
        self.manual_events = QCheckBox(text="Use manual events")
        self.folder = folder
        if folder:
            notes_layout.addWidget(self.negative_z)
            notes_layout.addWidget(self.manual_events)
            self.load_pdf()

        # Add widgets to the form layout
        form_layout.addLayout(name_layout)
        form_layout.addLayout(assessor_layout)
        form_layout.addLayout(date_layout)
        form_layout.addLayout(dir_layout)
        form_layout.addLayout(trial_layout)
        form_layout.addLayout(notes_layout)

        # Add Start button
        button_layout = QHBoxLayout()
        self.save_button = QPushButton("Save")
        self.save_button.clicked.connect(self.save_button_pressed)
        self.save_button.setDefault(True)

        self.back_button = QPushButton("Back")
        self.back_button.clicked.connect(self.back_button_pressed)
        button_layout.addStretch()
        button_layout.addWidget(self.save_button)
        button_layout.addWidget(self.back_button)

        # Add form and button layouts to main layout
        main_layout.addLayout(form_layout)
        main_layout.addLayout(button_layout)

        self.setLayout(main_layout)

        screen = QApplication.primaryScreen()
        screen_rect = screen.geometry()

        window_rect = self.frameGeometry()
        center_point = screen_rect.center()
        window_rect.moveCenter(center_point)

        self.move(window_rect.topLeft())

        print(f"Screen rect: {screen_rect}")
        print(f"Screen center: {center_point}")
        print(f"Window size: {window_rect.size()}")
        print(f"Final position: {window_rect.topLeft()}")

        # Verify final position
        final_pos = self.pos()
        print(f"Final window position: {final_pos}")

        self.sound = list()
        pygame.mixer.init()

        if getattr(sys, 'frozen', False):
            # Running as packaged executable
            user_music_folder = os.path.join(os.path.expanduser('~'), 'AppData', 'Roaming', NAME_APP, 'MUSIC')
            if not os.path.exists(user_music_folder) or not os.listdir(user_music_folder):
                music_folder = os.path.join(file_directory, 'NEEDED/MUSIC')
            else:
                music_folder = user_music_folder
        else:
            # Running from source (PyCharm/development)
            music_folder = os.path.join(file_directory, 'NEEDED/MUSIC')
        dir_sound = []
        for filename in os.listdir(music_folder):
            file_path = os.path.join(music_folder, filename)

            if filename.endswith('.mp3'):
                dir_sound.append(file_path)

        threads_sound = [threading.Thread(target=self.load_sound, args=(dir_sound[i],)) for i in range(len(dir_sound))]
        for i in range(len(threads_sound)):
            threads_sound[i].daemon = True
            threads_sound[i].start()

        for t in threads_sound:
            t.join()

    def browse_dir(self):
        """
        Search for a new dir with the file explorer
        :return:
        """
        path_text = self.path.text()

        folder = QFileDialog.getExistingDirectory(
            self,
            "Select Save Directory",
            path_text,
            QFileDialog.ShowDirsOnly | QFileDialog.DontResolveSymlinks
        )
        if folder:
            self.set_dir(folder)

    def set_dir(self, folder):
        self.full_path = folder

        self.path.setText(folder)

    def save_button_pressed(self):
        if self.name_input.text().strip() == "":
            ret = QMessageBox.warning(self, "Warning",
                                      "One of the input fields seems to be empty, do you wish to continue anyway?",
                                      QMessageBox.Yes | QMessageBox.Cancel)
            if ret == QMessageBox.Yes:
                num_trials = self.combo_box.currentData()
                self.mainwindow = MainWindow(self.name_input.text(), self.assessor_input.text(),
                                             self.date_input.text(), num_trials, self.notes_input.toPlainText().strip(),
                                             self.sound, self.folder, self.negative_z.isChecked(),
                                             self.manual_events.isChecked(), self.full_path
                                             )
                self.mainwindow.show()
                self.close()
        else:
            num_trials = self.combo_box.currentData()
            self.mainwindow = MainWindow(self.name_input.text(), self.assessor_input.text(),
                                         self.date_input.text(), num_trials, self.notes_input.toPlainText().strip(),
                                         self.sound, self.folder, self.negative_z.isChecked(),
                                         self.manual_events.isChecked(), self.full_path
                                         )
            self.mainwindow.show()
            self.close()

    def back_button_pressed(self):
        from window_start_up import StartUp

        self.startup = StartUp()
        self.startup.show()
        self.close()

    def load_sound(self, dir_sound):
        if not pygame.mixer.get_init():
            pygame.mixer.init()

        self.sound.append((dir_sound, pygame.mixer.Sound(dir_sound)))

    def load_pdf(self):
        """
        Load the information from the PDF and fill the corresponding boxes in the window (add_data)
        """
        for filename in os.listdir(self.folder):
            file_path = os.path.join(self.folder, filename)

            if os.path.isdir(file_path):
                continue

            elif filename.endswith('.pdf'):
                self.add_data(file_path)

    def add_data(self, file):
        """
        Adds the data from the file to the boxes
        """
        pdf = pikepdf.Pdf.open(file)

        intro = pdf.pages[0]

        pdf_content = intro.get('/Contents').read_bytes().decode('utf-8')
        text = pdf_content.split('\n')

        set_values = [0 for i in range(4)]
        for line in text:
            if '(' in line:
                rule_text = line.split('(', 1)[1]
                rule_text = rule_text[::-1].split(')', 1)[1][::-1]

                if 'Trial 1' in rule_text or 'Trial 1:' in rule_text:
                    break

                rule_list = rule_text.split()
                if 'Participant' in rule_list and set_values[0] == 0:
                    index_part = rule_list.index('Participant')
                    self.name_input.setText(rule_list[index_part + 1])
                    set_values[0] = 1

                if 'assessor' in rule_list and set_values[1] == 0:
                    index_ass = rule_list.index('assessor')
                    self.assessor_input.setText(rule_list[index_ass + 1])
                    set_values[1] = 1

                if 'on' in rule_list and set_values[2] == 0:
                    index_date = rule_list.index('on')
                    print(rule_list[index_date + 1])
                    date = QDate.fromString(rule_list[index_date + 1], 'd/MM/yyyy')
                    print(date.currentDate())
                    self.date_input.setDate(date)
                    set_values[2] = 1

                elif 'Total' in rule_list and 'trials:' in rule_list and set_values[3] == 0 and 'used' not in rule_list:
                    index_num_trials = rule_list.index('trials:')
                    self.combo_box.setCurrentIndex(int(rule_list[index_num_trials + 1]) - 1)
                    set_values[3] = 1

                elif 'Total' in rule_list and 'trials:' in rule_list and 'used' in rule_list:
                    index_num_trials = rule_list.index('trials:')
                    if int(rule_list[index_num_trials + 1]) - 1 > self.combo_box.currentIndex():
                        self.combo_box.setCurrentIndex(int(rule_list[index_num_trials + 1]) - 1)
                    set_values[3] = 1

                else:
                    if rule_text != 'No Additional Notes':
                        self.notes_input.append(rule_text)

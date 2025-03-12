import threading

import pygame
from PySide6.QtWidgets import (
    QVBoxLayout, QPushButton, QLineEdit, QLabel, QHBoxLayout,
    QDateEdit, QTextEdit, QMessageBox, QComboBox, QDialog,
)
from PySide6.QtCore import QDate

from window_main_plot import MainWindow


class SetUp(QDialog):
    def __init__(self):
        super().__init__()

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
        for i in range(1, 21):
            self.combo_box.addItem(str(i), i)

        self.label = QLabel("Number of trials: ")
        self.combo_box.setCurrentIndex(9)

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

        # assessor
        assessor_layout = QHBoxLayout()
        assessor_label = QLabel("Assessor:            ")
        self.assessor_input = QLineEdit()
        assessor_layout.addWidget(assessor_label)
        assessor_layout.addWidget(self.assessor_input)

        # Add widgets to the form layout
        form_layout.addLayout(name_layout)
        form_layout.addLayout(assessor_layout)
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

        self.sound = list()
        pygame.mixer.init()
        dir_sound = ('NEEDED/MUSIC/Bumba.mp3',
                     'NEEDED/MUSIC/applause.mp3',
                     'NEEDED/MUSIC/Bluey.mp3',
                     'NEEDED/MUSIC/cheering.mp3',
                     'NEEDED/MUSIC/bong.mp3')

        threads_sound = [threading.Thread(target=self.load_sound, args=(dir_sound[i],)) for i in range(len(dir_sound))]
        for i in range(len(threads_sound)):
            threads_sound[i].daemon = True
            threads_sound[i].start()

        for t in threads_sound:
            t.join()

    def save_button_pressed(self):
        if self.name_input.text().strip() == "":
            ret = QMessageBox.warning(self, "Warning",
                                      "One of the input fields seems to be empty, do you wish to continue anyway?",
                                      QMessageBox.Yes | QMessageBox.Cancel)
            if ret == QMessageBox.Yes:
                num_trials = self.combo_box.currentData()
                self.mainwindow = MainWindow(self.name_input.text(), self.assessor_input.text(),
                                             self.date_input.text(), num_trials, self.notes_input.toPlainText().strip(),
                                             self.sound)
                self.mainwindow.show()
                self.close()
        else:
            num_trials = self.combo_box.currentData()
            self.mainwindow = MainWindow(self.name_input.text(), self.assessor_input.text(),
                                         self.date_input.text(), num_trials, self.notes_input.toPlainText().strip(),
                                         self.sound)
            self.mainwindow.show()
            self.close()

    def back_button_pressed(self):
        from window_start_up import StartUp

        self.startup = StartUp()
        self.startup.show()
        self.close()

    def load_sound(self, dir_sound):
        if pygame.mixer.get_init():
            pygame.mixer.init()

        self.sound.append(pygame.mixer.Sound(dir_sound))

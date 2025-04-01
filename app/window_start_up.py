import os

from PySide6.QtWidgets import (
    QVBoxLayout, QWidget, QPushButton, QFileDialog, QMessageBox
)

from window_set_up import SetUp


class StartUp(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Startup")

        layout = QVBoxLayout()

        self.button_new = QPushButton("New Project")
        self.button_new.clicked.connect(self.open_setup)
        self.button_old = QPushButton("Open existing Project")
        self.button_old.clicked.connect(self.reopen_setup)

        layout.addWidget(self.button_new)
        layout.addWidget(self.button_old)

        self.setLayout(layout)

    # go to setup window
    def open_setup(self):
        self.setup = SetUp()
        self.setup.show()
        self.close()

    def reopen_setup(self):
        folder = QFileDialog.getExistingDirectory(self, "Select Trial Directory", os.path.expanduser("~/Documents"))
        if folder:
            self.setup = SetUp(folder)
            self.setup.show()
            self.close()


        """import tkinter as tk
from tkinter import filedialog, Tk
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
from scipy.signal import butter, filtfilt

# Function to select file
def select_file():
    root = tk.Tk()
    root.withdraw()  # Hide the main window
    file_path = filedialog.askopenfilename(filetypes=[("Excel files", "*.xlsx")])
    return file_path

# Select file
file_path = select_file()

if file_path:
    # Load Excel data
    df = pd.read_excel(file_path)

    # Extract time and x data 
    t = df.iloc[:, 0].values
    f = df.iloc[:, 1].values 
   
else:
    print("No file selected.")"""

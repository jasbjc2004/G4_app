# Bimanual Hand Movement
With this program it is possible to connect to the Polhemus sensor, plot the data (real-time after a small delay) and data-processing. This program is intended for the data analyses of a bimanual hand movement and is part of a project of KULeuven. It is made in Python with the help of the library from Polhemus (converted from C to Python)

## 1. NEEDED
This map contains all files needed to let the program work. 

## 2. Old version
This map contains all the files from a previous version of the app. So these files are all extra for information and possible ideas for an extention in the main software. Not needed to let the program work.

## 3. Test Files
All files needed to test all different parts of the project. Not needed to let the program work.

## 4. app
All files related to the software, all are needed to let it work. In this map is also a code to make the .exe from all the other files, so the next person doesn't need to type all of it. The software can be made using 'Inno Setup Compiler'.


## To-do
* Make a fast start or a timer to start the reading of data (some delay in this version) -> change "_class ReadThread(QThread)_" or "_start_reading(self)_" in "_widget_trials.py_"
* Make possible to change the constant value -> work with .txt-file or .json-file
* Let the program search for artifacts -> maybe check how fast the speed or any other coordinate changes & check if it's usefull and the behavior of it
* Compare between patients -> maybe add a new class like "_widget_trials.py_" to add the comparision, also possible with seperate pop-up
* Make a summary of 1 patient (average of events) & plot on the rest of the trials -> seperate python-file for calculations + changes in "_update_plot(self, redraw=False, parent=None)_" of "_widget_trials.py_"
* Use a neural network to calculate the events -> more data needed with manual events (or correct automatic events) & score (maybe also the case of movement) to train the NN => changes in "_data_processing.py_"
* Add more sound -> changes in "_class SetUp(QDialog)_"
* Make a back-up of the data -> save after every reading in a .cvs or .xsl (both very fast) or **better**: a server
* Log possible errors to .txt to check what went wrong -> add global error handler + logger
* Change sensor to fit in a glove

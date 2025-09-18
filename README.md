# Bimanual Hand Movement
With this program it is possible to connect to the Polhemus sensor, plot the data (real-time after a small delay) and data-processing. This program is intended for the data analyses of a bimanual hand movement and is part of a project of KULeuven. It is made in Python with the help of the library from Polhemus (converted from C to Python)

## Content
### 1. Old version
This map contains all the files from a previous version of the app. So these files are all extra for information and possible ideas for an extention in the main software. Not needed to let the program work.

### 2. Test Files
All files needed to test all different parts of the project. Not needed to let the program work.

### 3. app
All files related to the software, all are needed to let it work. In this map is also a code to make the .exe from all the other files, so the next person doesn't need to type all of it. The software can be made using 'Inno Setup Compiler'.

## Make a new version of the app:
1. Use the software_installer.py to make an .exe in the dist-directory of your project
2. Open the info_installer.iss in Inno Setup Compiler. !!!You need to update the user and possibly the directories if needed !!!

## Update the neural network
1. Delete the scoring_model.keras
2. Make a new directory "TRAINING_DATA" with all the training data
3. Run training_nn_score.py
4. Make a new version of the app

## To-do
* Let the program search for artifacts -> maybe check how fast the speed or any other coordinate changes & check if it's usefull and the behavior of it
* Compare between patients -> maybe add a new class like "_widget_trials.py_" to add the comparision, also possible with seperate pop-up
* Make a summary of 1 patient (average of events) & plot on the rest of the trials -> seperate python-file for calculations + changes in "_update_plot(self, redraw=False, parent=None)_" of "_widget_trials.py_"
* Use a neural network to calculate the events -> more data needed with manual events (or correct automatic events) & score (maybe also the case of movement) to train the NN => changes in "_data_processing.py_"
* Change sensor to fit in a glove
* Make a better connection with the GoPro (maybe use a wired connection)
* Create a better lay-out for the output-files in thread_download.py
* Create a validation for the calibration data_processing.py
* Check the parameter smoothness & path length of the unimanual parameter in data_processing.py

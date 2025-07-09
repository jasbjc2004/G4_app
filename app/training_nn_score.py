import os

import numpy as np
import pandas as pd

import openpyxl
from tensorflow import keras
from keras.models import Sequential
from keras.layers import Masking, LSTM, Dense, Dropout
from keras.callbacks import EarlyStopping


def extract_excel_for_nn(file):
    """
    Extract all the data (coordinates and score) for training the neural network
    """
    trial_data = pd.read_excel(file)

    if trial_data.shape[0] < 1 or trial_data.shape[1] < 10:
        return None, -1

    coor = trial_data.iloc[:, 1:9].values
    score = trial_data.iloc[0, 9]

    return coor, score


def padding_input(samples_in, length):
    NUMBER_DOF = 8          # 3 coordinates and speed of each hand
    number_samples = len(length)

    max_len = max(length)

    padded_in = np.full((number_samples, max_len, NUMBER_DOF), 0.0, dtype=np.float32)
    for i, sample in enumerate(samples_in):
        length = sample.shape[0]
        padded_in[i, :length, :] = sample

    return padded_in


def main():
    folder = "TRAINING_DATA"

    x = []
    length_x = []
    y = []

    for filename in os.listdir(folder):
        file_path = os.path.join(folder, filename)

        if os.path.isdir(file_path):
            continue

        elif filename.endswith(('.xlsx', '.xls', '.xlsm')):
            coor_i, score_i = extract_excel_for_nn(file_path)

            if coor_i is not None and score_i != -1:
                x.append(coor_i)
                length_x.append(len(coor_i))
                y.append(score_i)

    x_padded = padding_input(x, length_x)
    y = np.array(y)

    print('Start training')

    model = Sequential([
        Masking(mask_value=0.0, input_shape=(None, 8)),
        LSTM(64, return_sequences=False),
        Dropout(0.2),
        Dense(32, activation='relu'),
        Dense(1, activation='sigmoid')  # Keep output from [0,3], Output [0,1], scale to [0,3]
    ])

    model.compile(optimizer='adam', loss='mse', metrics=['mae'])

    # Scale targets to [0,1]
    y_scaled = y / 3.0

    early_stop = EarlyStopping(patience=10, restore_best_weights=True)
    history = model.fit(x_padded, y_scaled, epochs=100, batch_size=8,
              validation_split=0.25, callbacks=[early_stop])

    model.save('scoring_model.keras')

    print(f"Final training loss: {history.history['loss'][-1]:.4f}")
    print(f"Final validation loss: {history.history['val_loss'][-1]:.4f}")
    print(f"Final training MAE: {history.history['mae'][-1]:.4f}")
    print(f"Final validation MAE: {history.history['val_mae'][-1]:.4f}")

main()

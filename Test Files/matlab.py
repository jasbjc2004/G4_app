
import os
import numpy as np
import pandas as pd
from scipy.signal import butter, filtfilt
from tkinter import filedialog, Tk, simpledialog, messagebox
import matplotlib.pyplot as plt
from scipy.signal import savgol_filter

# Constants
VEL_THRESHOLD = 0.01
SAMPLING_RATE = 120  # Hz
DT = 1 / SAMPLING_RATE

# Hide Tk window
Tk().withdraw()

# 1. Load master file
master_file_path = filedialog.askopenfilename(title="Select master file", filetypes=[("Excel files", "*.xlsx")])
M = pd.read_excel(master_file_path)

# 2. Select main data folder
main_data_folder = filedialog.askdirectory(title="Select main data folder with subfolders for every subject")

# 3. Choose full dataset or subject
set_option = messagebox.askquestion("Dataset", "Do you want to do the analysis for the full masterfile dataset, or for one specific subject (and trial)?")

# Initialize j and k
if set_option == 'yes':  # yes = hele dataset
    subfolders = [f.name for f in os.scandir(main_data_folder) if f.is_dir()][2:]
    for sub in subfolders:
        os.makedirs(os.path.join(main_data_folder, sub, 'figures'), exist_ok=True)
    j, k = 0, len(M) - 1

else:  # 'subject'
    sub_code = simpledialog.askstring("Input", "Enter subject code")
    trial_input = simpledialog.askstring("Input", "Enter trial number (leave blank if all trials need to be analysed)")
    os.makedirs(os.path.join(main_data_folder, sub_code, 'figures'), exist_ok=True)
    index = M[M.Participant_ID == sub_code].index[0]

    if trial_input and trial_input.isdigit():
        trial_num = int(trial_input)
        j = index + (trial_num - 1)
        k = j
    else:
        j = index
        k = index + 9

# initaliseer table
results = []

for i in range(j, k + 1):
    if M.loc[i, "Valid"] == 1:
        filename = os.path.join(main_data_folder, str(M.loc[i, "Participant_ID"]), f"Trial{int(M.loc[i, 'Trial_Number'])}.csv")
        D = pd.read_csv(filename, header=None).values

        # Filtering
        sf = 120
        cf = 10
        order = 2
        b, a = butter(order, cf / (sf / 2))
        D[:, 0:12] = filtfilt(b, a, D[:, 0:12], axis=0)

        # Determine hands
        box_hand = M.loc[i, "Box_hand"]
        if box_hand == 1:
            B_hand = -D[:, 6:9]
            T_hand = -D[:, 0:3]
        else:
            B_hand = -D[:, 0:3]
            T_hand = -D[:, 6:9]

        bx, by, bz = B_hand.T
        tx, ty, tz = T_hand.T

        # Velocity
        v_bx = np.diff(bx) * sf
        v_by = np.diff(by) * sf
        v_bz = np.diff(bz) * sf
        v_bh = np.sqrt(v_bx**2 + v_by**2 + v_bz**2)

        v_tx = np.diff(tx) * sf
        v_ty = np.diff(ty) * sf
        v_tz = np.diff(tz) * sf
        v_th = np.sqrt(v_tx**2 + v_ty**2 + v_tz**2)

        # Acceleration
        a_bh = np.diff(v_bh) * sf
        a_th = np.diff(v_th) * sf

        # Event detection
        e8 = np.argmax(D_nonrot[:, 14] > 0)

        e1 = np.argmax(v_bh > 0.05)
        while e1 > 0 and a_bh[e1 - 1] >= 0:
            e1 -= 1

        e2 = e1 + np.argmax(v_bh[e1:e1+50])
        e4 = e2 + 50 + np.argmax(v_bh[e2+50:e2+150])
        e3 = e2 + np.argmin(v_bh[e2:e4])

        e5 = np.argmax(bz[:e8])

        e6 = np.argmax(v_th > 0.05)
        while e6 > 0 and a_th[e6 - 1] >= 0:
            e6 -= 1

        e7 = e6 + np.argmax(v_th[e6:e8])

        # Plotting
        fig, axs = plt.subplots(3, 1, figsize=(10, 12))
        time_bz = np.arange(len(bz)) / sf
        time_v = np.arange(len(v_bh)) / sf
        time_a = np.arange(len(a_bh)) / sf

        axs[0].plot(time_bz, bz, label='Box hand Z')
        axs[0].plot(time_bz, tz, label='Trigger hand Z')
        axs[0].set_title('Position')
        axs[0].legend()

        axs[1].plot(time_v, v_bh, label='Box hand')
        axs[1].plot(time_v, v_th, label='Trigger hand')
        for idx, ev in enumerate([e1, e2, e3, e4, e5]):
            axs[1].plot(time_v[ev], v_bh[ev], '*r')
        for idx, ev in enumerate([e6, e7]):
            axs[1].plot(time_v[ev], v_th[ev], 'vr')
        axs[1].plot(time_v[e8], v_th[e8], 'vg')
        axs[1].set_title('Velocity')
        axs[1].legend()

        axs[2].plot(time_a, a_bh, label='Box hand')
        axs[2].plot(time_a, a_th, label='Trigger hand')
        axs[2].set_title('Acceleration')
        axs[2].legend()

        fig_title = f"{M.loc[i, 'Participant_ID']} - Test {M.loc[i, 'Test_retest']} - Trial {M.loc[i, 'Trial_Number']}"
        plt.suptitle(fig_title)
        plt.tight_layout()
        plt.pause(0.1)

        # Ask trial quality
        quality = messagebox.askquestion("Trial quality", "Indicate if quality of trial is good or bad")

        fig_path = os.path.join(main_data_folder, str(M.loc[i, "Participant_ID"]), "figures", f"{fig_title}.png")
        fig.savefig(fig_path)
        plt.close(fig)

        # Path lengths
        def path_length(x, y, z):
            return np.sum(np.sqrt(np.diff(x)**2 + np.diff(y)**2 + np.diff(z)**2))

        d_bh = path_length(bx[e1:e5], by[e1:e5], bz[e1:e5])
        d_bh_p1 = path_length(bx[e1:e3], by[e1:e3], bz[e1:e3])
        d_bh_p2 = path_length(bx[e3:e5], by[e3:e5], bz[e3:e5])
        d_th = path_length(tx[e6:e8], ty[e6:e8], tz[e6:e8])

        # Time calculations
        tt = (e8 - min(e1, e6)) / sf
        t_bh = (e5 - e1) / sf
        t_bh_p1 = (e3 - e1) / sf
        t_bh_p2 = (e5 - e3) / sf
        t_th = (e8 - e6) / sf
        temp_coupling = (e5 - e6) / sf
        mov_overlap = ((e6 - e5) / sf) / tt * 100
        goal_sync = (e5 - e8) / sf

        # Smoothness
        smooth_bh = np.sum(np.r_[False, np.diff(np.sign(np.diff(v_bh[e1:e5]))) != 0])
        smooth_th = np.sum(np.r_[False, np.diff(np.sign(np.diff(v_th[e6:e8]))) != 0])

        results.append([
            i, M.loc[i, "Participant_ID"], M.loc[i, "Test_retest"], M.loc[i, "Trial_Number"], tt,
            e1/sf, e2/sf, e3/sf, e4/sf, e5/sf, e6/sf, e7/sf, e8/sf,
            d_bh, d_bh_p1, d_bh_p2, d_th,
            t_bh, t_bh_p1, t_bh_p2, t_th,
            temp_coupling, mov_overlap, goal_sync,
            smooth_bh, smooth_th, quality
        ])

# Convert results to DataFrame
columns = [
    'number', 'Participant', 'Test', 'Trial', 'Total_Movement_Time', 'e1', 'e2', 'e3', 'e4', 'e5', 'e6', 'e7', 'e8',
    'path_length_box_hand', 'path_length_box_hand_phase1', 'path_length_box_hand_phase2',
    'path_length_trigger_hand', 'Movement_time_box_hand', 'Movement_time_box_hand_phase1',
    'Movement_time_box_hand_phase2', 'Movement_time_trigger_hand', 'Temporal_coupling',
    'Movement_overlap', 'Goal_synchronization', 'Smoothness_box_hand', 'Smoothness_trigger_hand',
    'Trial_quality'
]
results_df = pd.DataFrame(results, columns=columns)



# nog aanpassen uploaden van excel zie andere file
df =

# Ensure column names are correct
df.columns = [col.strip() for col in df.columns]

# Time vector
time = np.arange(len(df)) * DT

# Compute velocity
x = df["Position X"].to_numpy()
y = df["Position Y"].to_numpy()
vx = np.gradient(x, DT)
vy = np.gradient(y, DT)
v = np.sqrt(vx**2 + vy**2)
v_smooth = savgol_filter(v, 11, 3)

# Plot for inspection
plt.plot(time, v_smooth)
plt.axhline(VEL_THRESHOLD, color='r', linestyle='--')
plt.title("Velocity Profile")
plt.xlabel("Time (s)")
plt.ylabel("Velocity (m/s)")
plt.grid()
plt.show()

# Identify movement onset and offset
above_thresh = v_smooth > VEL_THRESHOLD
transitions = np.diff(above_thresh.astype(int))

onsets = np.where(transitions == 1)[0]
offsets = np.where(transitions == -1)[0]

# Handle edge cases
if offsets[0] < onsets[0]:
    offsets = offsets[1:]
if len(onsets) > len(offsets):
    onsets = onsets[:len(offsets)]

# Initialize list for metrics
metrics = []

for i, (start, end) in enumerate(zip(onsets, offsets)):
    segment = slice(start, end + 1)
    t = time[segment]
    v_segment = v_smooth[segment]

    if len(v_segment) < 5:
        continue

    peak_idx = np.argmax(v_segment)
    peak_velocity = v_segment[peak_idx]
    min_after_peak = np.min(v_segment[peak_idx:])

    movement_time = t[-1] - t[0]
    time_to_peak = t[peak_idx] - t[0]
    time_after_peak = t[-1] - t[peak_idx]

    metrics.append({
        "Trial": i + 1,
        "Movement Time (s)": movement_time,
        "Peak Velocity (m/s)": peak_velocity,
        "Time to Peak (s)": time_to_peak,
        "Time After Peak (s)": time_after_peak,
        "Min Velocity After Peak (m/s)": min_after_peak
    })

# Convert to DataFrame
metrics_df = pd.DataFrame(metrics)

# Compute averages
average_metrics = metrics_df.mean(numeric_only=True)
average_metrics.name = "Average"

# Append average as new row
metrics_df = pd.concat([metrics_df, pd.DataFrame([average_metrics])], ignore_index=True)

# Export to Excel
metrics_df.to_excel("movement_metrics.xlsx", index=False)

print("Analysis complete. Metrics saved to 'movement_metrics.xlsx'.")

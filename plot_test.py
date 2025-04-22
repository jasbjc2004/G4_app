import tkinter as tk
from tkinter import filedialog
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
from scipy.signal import butter, filtfilt, argrelextrema

BUTTON_PRESSED = True
sf = 120

def calculate_boxhand(pos_left, pos_right):
    """

    :param pos_left:
    :param pos_right:
    :returns:
        0 if the left hand is the box hand,
        1 if the right hand is the box hand
        2 if both hands are used simultaneous, but right pressed
        3 if both hands are used simultaneous, but left pressed
        4 if the left hand is not used
        5 if the right hand is not used
    """
    start_left = pos_left[0]
    start_right = pos_right[0]

    counter_left = 7*len(pos_left)/8
    counter_right = 7*len(pos_right)/8
    for i in range(-1,-len(pos_left),-1):
        if pos_left[i][2] < MAX_HEIGHT_NEEDED + start_left[2] and pos_left[i][1] < MAX_LENGTH_NEEDED + start_left[1]:
            counter_left -= 1
        if pos_right[i][2] < MAX_HEIGHT_NEEDED + start_right[2] and pos_right[i][1] < MAX_LENGTH_NEEDED + start_right[1]:
            counter_right -= 1

        if pos_left[i][2] > MIN_HEIGHT_NEEDED + start_left[2] and pos_left[i][1] > MIN_LENGTH_NEEDED + start_left[1]:
            counter_left += 5
        if pos_right[i][2] > MIN_HEIGHT_NEEDED + start_right[2] and pos_right[i][1] > MIN_LENGTH_NEEDED + start_right[1]:
            counter_right += 5

    if counter_left <= 0:
        return 4
    if counter_right <= 0:
        return 5

    THRESHOLD = 10
    mse_both_hands = 0
    for time in range(-1,-len(pos_left),-1):
        for pos in range(1,3):
            mse_both_hands += (pos_left[time][pos] - pos_right[time][pos]) ** 2 / (3*len(pos_left))

    print(mse_both_hands)

    mse_left = 0
    mse_right = 0
    for i in range(3):
        if i == 0:
            mse_left += (-pos_left[-1][i] - POSITION_BUTTON[i])**2 / 3
            mse_right += (pos_right[-1][i] - POSITION_BUTTON[i])**2 / 3
        else:
            mse_left += (pos_left[-1][i] - POSITION_BUTTON[i]) ** 2 / 3
            mse_right += (pos_right[-1][i] - POSITION_BUTTON[i]) ** 2 / 3

    if mse_left >= mse_right:
        if mse_both_hands < THRESHOLD:
            return 2
        return 0
    else:
        if mse_both_hands < THRESHOLD:
            return 3
        return 1

    
def select_file():
    root = tk.Tk()
    root.withdraw()
    return filedialog.askopenfilename(filetypes=[("Excel files", "*.xlsx")])

# is nu zo omdat ik de functie nog niet heb geimplemteerd
def box_hand():
    return 1

def butter_lowpass_filter(data, cutoff=5, fs=120, order=2):
    nyq = 0.5 * fs
    normal_cutoff = cutoff / nyq
    b, a = butter(order, normal_cutoff, btype='low', analog=False)
    return filtfilt(b, a, data)

file_path = select_file()
box_hand = box_hand()

if file_path:
    df = pd.read_excel(file_path)
    e6 = len(df.iloc[:,1])
    print(e6)
    if box_hand == 0:
        B_hand = np.array([df.iloc[:, 1], df.iloc[:, 2], df.iloc[:, 3], df.iloc[:, 4]])  # Boxhand is linkerhand
        T_hand = np.array([df.iloc[:, 5], df.iloc[:, 6], df.iloc[:, 7], df.iloc[:, 8]])  # Triggerhand is rechterhand
    else:
        B_hand = np.array([df.iloc[:, 5], df.iloc[:, 6], df.iloc[:, 7], df.iloc[:, 8]])  # Boxhand is rechterhand
        T_hand = np.array([df.iloc[:, 1], df.iloc[:, 2], df.iloc[:, 3], df.iloc[:, 4]])  # Triggerhand is linkerhand
else:
    print("No file selected.")
    exit()

B_hand = B_hand.T
T_hand = T_hand.T

# Coordinates + velocity per hand
bx = B_hand[:, 0]
by = B_hand[:, 1]
bz = B_hand[:, 2]
bv = B_hand[:, 3]

tx = T_hand[:, 0]
ty = T_hand[:, 1]
tz = T_hand[:, 2]
tv = T_hand[:, 3]

# Apply Butterworth filter to velocity data
bv = butter_lowpass_filter(B_hand[:, 3])
tv = butter_lowpass_filter(T_hand[:, 3])

a_bh = np.diff(bv) * sf
a_th = np.diff(tv) * sf

# Event calculations
e1 = np.argmax(bv > 0.05)
while e1 > 1 and a_bh[e1] >= 0:
    e1 -= 1
print("e1",e1)

piek_1 = np.argmax(bv[e1:e1+51]) + e1 - 1
print("piek_1",piek_1)
piek_2 = np.argmax(bv[piek_1 + 51:piek_1 + 1001]) + piek_1 + 50 - 1
print("piek_2",piek_2)
e2 = np.argmax(bv[piek_1:piek_2]) + piek_1 - 1
print("e2",e2)
e3 = np.argmax(bz[1:e6])
print("e3",e3)
e5 = np.argmax(tv > 0.05)
while e5 > 1 and a_th[e5] >= 0:
    e5 -= 1
print("e5",e5)

# Convert frames to seconds
time = np.arange(len(bv)) / sf


# berekenen van andere nodige parameters
# path-length of box hand (d=distance)
dbx = bx[e1:e3]
dby = by[e1:e3]
dbz = bz[e1:e3]


dbx = np.diff(dbx)
dby = np.diff(dby)
dbz = np.diff(dbz)


d_bh = np.sqrt((dbx ** 2) + (dby ** 2) + (dbz ** 2))
d_bh = np.sum(d_bh)

# path-length of box hand - eerste fase tot aan de doos
dbx_p1 = bx[e1:e2]
dby_p1 = by[e1:e2]
dbz_p1 = bz[e1:e2]


dbx_p1 = np.diff(dbx_p1)
dby_p1 = np.diff(dby_p1)
dbz_p1 = np.diff(dbz_p1)

d_bh_p1 = np.sqrt((dbx_p1 ** 2) + (dby_p1 ** 2) + (dbz_p1 ** 2))
d_bh_p1 = np.sum(d_bh_p1)



# path-length of box hand - tweede fase deksel van de doos op hoogste punt
dbx_p2 = bx[e2:e3]
dby_p2 = by[e2:e3]
dbz_p2 = bz[e2:e3]

dbx_p2 = np.diff(dbx_p2)
dby_p2 = np.diff(dby_p2)
dbz_p2 = np.diff(dbz_p2)

d_bh_p2 = np.sqrt((dbx_p2 ** 2) + (dby_p2 ** 2) + (dbz_p2 ** 2))
d_bh_p2 = sum(d_bh_p2)

# path-length of trigger hand of triggerhand, not yet activated as e5 still needs to be calculated ??? -> check na wat dit betekent
# hier nog aanpassen met e4 of hier nog andere fase ingevoegd moet worden
dtx = tx[e5:e6]
dty = ty[e5:e6]
dtz = tz[e5:e6]

dtx = np.diff(dtx)
dty = np.diff(dty)
dtz = np.diff(dtz)
d_th = np.sqrt((dtx ** 2) + (dty ** 2) + (dtz ** 2))
d_th = np.sum(d_th)

# total time = trigger press - start first movement
# e5 kan hier gelijk zijn aan e5 dus zoek dat uit
tt = (e6 - min(e1,e5)) / sf

# time box hand = end lid opening - start box hand
t_bh = (e3 - e1) / sf

# time 1st phase of box hand = start opening box - start of box hand
t_bh_p1 = (e2 - e1) / sf

# time 2nd phase of box hand = end of box hand - start opening box
t_bh_p2 = (e3 - e2) / sf

# time trigger hand = trigger press - start trigger hand
# rekening houden met e4 en e5
t_th = (e6 - e5) / sf

# temp coupling = end box hand - start trigger hand
temp_coupling = (e3 - e5) / sf

# movement overlap = end lid opening - start trigger hand
mov_overlap = ((e5 - e3) / sf ) / tt * 100

# goal synchronization = trigger press - end lid opening
goal_sync = (e3 - e6) / sf

# if start / endpoint is also a max => not taken into account. if need => first local max of b then sum in range e1: e3
subset = bv[e1:e3]

max_bh = argrelextrema(subset, np.greater)[0]
min_bh = argrelextrema(subset, np.less)[0]

# Count the number of local extrema
smooth_bh = len(max_bh) + len(min_bh)

subset_t = tv[e1:e3]

max_th = argrelextrema(subset_t, np.greater)[0]
min_th = argrelextrema(subset_t, np.less)[0]

# Count the number of local extrema
smooth_th = len(max_th) + len(min_th)
# dit moet nog uitgewerkt worden over meerdere trials en dan krijg je een table die alle info heeft waarover je dan een average neemt ....
"""

Table.columns = [
    'number', 'Participant', 'Test', 'Trial', 'Total_Movement_Time',
    'e1', 'e2', 'e3', 'e4', 'e5', 'e6', 'e7', 'e8',
    'path_length_box_hand', 'path_length_box_hand_phase1', 'path_length_box_hand_phase2',
    'path_length_trigger_hand', 'Movement_time_box_hand', 'Movement_time_box_hand_phase1',
    'Movement_time_box_hand_phase2', 'Movement_time_trigger_hand', 'Temporal_coupling',
    'Movement_overlap', 'Goal_synchronization', 'Smoothness_box_hand', 'Smoothness_trigger_hand',
    'Trial_quality'
]

# Timestamp: niet 100% zeker wat dit doet
time = datetime.now().strftime("%Y%m%d %H%M%S")

# Initialize output table
Table_avg = []


k = len(Table) # moet de lengte zijn nog aan te passen
j = 0  # Assuming this is defined elsewhere
Folder = './output'  # Define your desired output folder
os.makedirs(Folder, exist_ok=True)

for i in range(10, k+1, 10):
    idx_DHC = [i-9, i-8, i-7, i-3, i-2]
    idx_NDHC = [i-6, i-5, i-4, i-1, i]

    def mean_col(col, indices):
        return np.mean(Table.iloc[indices][col])

    def var_col(col, indices):
        return np.var(Table.iloc[indices][col])

    tt_DHC = mean_col('Total_Movement_Time', idx_DHC)
    tt_NDHC = mean_col('Total_Movement_Time', idx_NDHC)

    d_bh_DHC = mean_col('path_length_box_hand', idx_DHC)
    d_bh_NDHC = mean_col('path_length_box_hand', idx_NDHC)

    d_bh_phase1_DHC = mean_col('path_length_box_hand_phase1', idx_DHC)
    d_bh_phase1_NDHC = mean_col('path_length_box_hand_phase1', idx_NDHC)

    d_bh_phase2_DHC = mean_col('path_length_box_hand_phase2', idx_DHC)
    d_bh_phase2_NDHC = mean_col('path_length_box_hand_phase2', idx_NDHC)

    d_th_DHC = mean_col('path_length_trigger_hand', idx_DHC)
    d_th_NDHC = mean_col('path_length_trigger_hand', idx_NDHC)

    SA_th_DHC = var_col('path_length_trigger_hand', idx_DHC)
    SA_th_NDHC = var_col('path_length_trigger_hand', idx_NDHC)

    t_bh_DHC = mean_col('Movement_time_box_hand', idx_DHC)
    t_bh_NDHC = mean_col('Movement_time_box_hand', idx_NDHC)

    t_bh_phase1_DHC = mean_col('Movement_time_box_hand_phase1', idx_DHC)
    t_bh_phase1_NDHC = mean_col('Movement_time_box_hand_phase1', idx_NDHC)

    t_bh_phase2_DHC = mean_col('Movement_time_box_hand_phase2', idx_DHC)
    t_bh_phase2_NDHC = mean_col('Movement_time_box_hand_phase2', idx_NDHC)

    t_th_DHC = mean_col('Movement_time_trigger_hand', idx_DHC)
    t_th_NDHC = mean_col('Movement_time_trigger_hand', idx_NDHC)

    temp_coupling_DHC = mean_col('Temporal_coupling', idx_DHC)
    temp_coupling_NDHC = mean_col('Temporal_coupling', idx_NDHC)

    mov_overlap_DHC = mean_col('Movement_overlap', idx_DHC)
    mov_overlap_NDHC = mean_col('Movement_overlap', idx_NDHC)

    goal_sync_DHC = mean_col('Goal_synchronization', idx_DHC)
    goal_sync_NDHC = mean_col('Goal_synchronization', idx_NDHC)

    smooth_bh_DHC = mean_col('Smoothness_box_hand', idx_DHC)
    smooth_bh_NDHC = mean_col('Smoothness_box_hand', idx_NDHC)

    smooth_th_DHC = mean_col('Smoothness_trigger_hand', idx_DHC)
    smooth_th_NDHC = mean_col('Smoothness_trigger_hand', idx_NDHC)

    participant_id = M['Participant_ID'].iloc[j+i-10]
    test_retest = M['Test_retest'].iloc[j+i-10]

    Table_avg.append([
        participant_id, test_retest, 'DHC', tt_DHC, d_bh_DHC, d_bh_phase1_DHC,
        d_bh_phase2_DHC, d_th_DHC, SA_th_DHC, t_bh_DHC, t_bh_phase1_DHC,
        t_bh_phase2_DHC, t_th_DHC, temp_coupling_DHC, mov_overlap_DHC,
        goal_sync_DHC, smooth_bh_DHC, smooth_th_DHC
        ])

    Table_avg.append([
        participant_id, test_retest, 'NDHC', tt_NDHC, d_bh_NDHC, d_bh_phase1_NDHC,
        d_bh_phase2_NDHC, d_th_NDHC, SA_th_NDHC, t_bh_NDHC, t_bh_phase1_NDHC,
        t_bh_phase2_NDHC, t_th_NDHC, temp_coupling_NDHC, mov_overlap_NDHC,
        goal_sync_NDHC, smooth_bh_NDHC, smooth_th_NDHC
        ])

columns_avg = [
    'Participant', 'Test', 'Condition', 'Total_Movement_Time_avg',
    'path_length_box_hand_avg', 'path_length_box_hand_phase1_avg',
    'path_length_box_hand_phase2_avg', 'path_length_trigger_hand_avg',
    'path_length_trigger_hand_var', 'Movement_time_box_hand_avg',
    'Movement_time_box_hand_phase1_avg', 'Movement_time_box_hand_phase2_avg',
    'Movement_time_trigger_hand_avg', 'Temporal_coupling_avg',
    'Movement_overlap_avg', 'Goal_synchronization_avg',
    'Smoothness_box_hand_avg', 'Smoothness_trigger_hand_avg'
]

Table_avg_df = pd.DataFrame(Table_avg, columns=columns_avg)


output_path = os.path.join(Folder, f"output_study Box opening task {time}.xlsx")
with pd.ExcelWriter(output_path) as writer:
    Table.to_excel(writer, sheet_name='Trials', index=False)
    Table_avg_df.to_excel(writer, sheet_name='Average', index=False)


print(table_array)
"""

# Plot velocity and mark events
plt.figure(figsize=(10, 5))
plt.plot(time, bv, label='Box Hand Velocity (Filtered)', color='blue')
plt.plot(time, tv, label='Trigger Hand Velocity (Filtered)', color='red')
plt.axvline(x=e1/sf, color='green', linestyle='--', label='e1')
plt.axvline(x=e2/sf, color='purple', linestyle='--', label='e2')
plt.axvline(x=e3/sf, color='orange', linestyle='--', label='e3')
plt.axvline(x=e5/sf, color='brown', linestyle='--', label='e5')
plt.axvline(x=e6/sf, color='black', linestyle='--', label='e6')
plt.xlabel('Time (seconds)')
plt.ylabel('Velocity (m/s)')
plt.legend()
plt.title('Filtered Velocity Plot with Events')
plt.show(block=True)
plt.show()


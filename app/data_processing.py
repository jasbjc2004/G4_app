import numpy as np
from scipy.signal import argrelextrema

from constants import MAX_HEIGHT_NEEDED, POSITION_BUTTON, MAX_LENGTH_NEEDED, MIN_HEIGHT_NEEDED, MIN_LENGTH_NEEDED, \
    THRESHOLD_BOTH_HANDS, SPEED_THRESHOLD, HEIGHT_BOX, THRESHOLD_CHANGED_HANDS_MEAS, fs
from sensor_G4Track import *
import time


def calibration_to_center(sys_id):
    """
    Calibrate the system (facing the source), so the x-axis points to the right of the user, the y-axis to the front
    and the z-axis to the floor. Keep in mind that the hemisphere of the source is dynamic and needs time to adapt.
    :param sys_id: system id
    :type sys_id: int
    :return: the sensor who is on the left and right hand
    :rtype: int, int, int, bool
    """
    TRESHOLD = 0.01
    MAX_ATTEMPTS = 5
    attempt = 0

    while attempt < MAX_ATTEMPTS:
        frame_reference_orientation_reset(sys_id)
        frame_reference_translation_reset(sys_id)

        # set_units(sys_id)
        time.sleep(2)  # wait for the hemisphere to adapt
        hub_id = get_active_hubs(sys_id, True)[0]
        station_map = get_station_map(sys_id, hub_id)

        pos0 = None
        while pos0 is None:
            pos0, active_count, data_hubs = get_frame_data(sys_id, [hub_id])
            if active_count == 0 or data_hubs == 0:
                time.sleep(0.1)
                continue

        pos_ports = [i for i in range(0, len(station_map)) if station_map[i]]
        sen1 = pos0.G4_sensor_per_hub[pos_ports[0]]
        sen2 = pos0.G4_sensor_per_hub[pos_ports[1]]

        # Find reference using the axis on the source
        frame_reference_translation(sys_id, (max(sen1.pos[0], sen2.pos[0]),
                                             (sen1.pos[1] + sen2.pos[1]) / 2,
                                             min(sen1.pos[2], sen2.pos[2])))

        frame_reference_orientation(sys_id, (90, 180, 0))

        if sen1.pos[1] < sen2.pos[1]:
            lsen, rsen = pos_ports[0], pos_ports[1]
        else:
            lsen, rsen = pos_ports[1], pos_ports[0]

        time.sleep(2)

        pos0, active_count, data_hubs = None, 0, 0
        while active_count == 0 & data_hubs == 0:
            pos0, active_count, data_hubs = get_frame_data(sys_id, [hub_id])

        pos_left = list(pos0.G4_sensor_per_hub[lsen].pos)
        pos_right = list(pos0.G4_sensor_per_hub[rsen].pos)

        print(abs(abs(pos_left[0]) - pos_right[0]))

        print(f"sensor: {pos_left, pos_right}")

        time.sleep(2)
        if abs(abs(pos_left[0]) - pos_right[0]) < TRESHOLD:
            return hub_id, lsen, rsen, True

        attempt += 1

    return None, None, None, False


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
        6 if the hands switched, but right pressed
        7 if the hands switched, but left pressed
    """
    start_left = pos_left[0]
    start_right = pos_right[0]

    counter_left = 7 * len(pos_left) / 8
    counter_right = 7 * len(pos_right) / 8
    for i in range(-1, -len(pos_left), -1):
        if pos_left[i][2] < MAX_HEIGHT_NEEDED + start_left[2] and pos_left[i][1] < MAX_LENGTH_NEEDED + start_left[1]:
            counter_left -= 1
        if pos_right[i][2] < MAX_HEIGHT_NEEDED + start_right[2] and pos_right[i][1] < MAX_LENGTH_NEEDED + start_right[
            1]:
            counter_right -= 1

        if pos_left[i][2] > MIN_HEIGHT_NEEDED + start_left[2] and pos_left[i][1] > MIN_LENGTH_NEEDED + start_left[1]:
            counter_left += 1 * len(pos_left) / 6
        if pos_right[i][2] > MIN_HEIGHT_NEEDED + start_right[2] and pos_right[i][1] > MIN_LENGTH_NEEDED + start_right[
            1]:
            counter_right += 1 * len(pos_left) / 6

    if counter_left <= 0:
        return 4
    if counter_right <= 0:
        return 5

    mse_both_hands = 0
    counter_change = 0
    for time in range(-1, -len(pos_left), -1):
        for pos in range(1, 3):
            mse_both_hands += (pos_left[time][pos] - pos_right[time][pos]) ** 2 / (2 * len(pos_left))

        if pos_left[time][2] >= HEIGHT_BOX and pos_right[time][2] >= HEIGHT_BOX and \
                pos_left[time][1] > MIN_LENGTH_NEEDED + start_left[1] and \
                pos_right[time][1] > MIN_LENGTH_NEEDED + start_right[1]:
            counter_change += 1

    print(mse_both_hands)

    mse_left = 0
    mse_right = 0
    for i in range(3):
        if i == 0:
            mse_left += (-pos_left[-1][i] - POSITION_BUTTON[i]) ** 2 / 3
            mse_right += (pos_right[-1][i] - POSITION_BUTTON[i]) ** 2 / 3
        else:
            mse_left += (pos_left[-1][i] - POSITION_BUTTON[i]) ** 2 / 3
            mse_right += (pos_right[-1][i] - POSITION_BUTTON[i]) ** 2 / 3

    if mse_left >= mse_right:
        if mse_both_hands < THRESHOLD_BOTH_HANDS:
            return 2
        elif counter_change > THRESHOLD_CHANGED_HANDS_MEAS:
            return 6
        return 0
    else:
        if mse_both_hands < THRESHOLD_BOTH_HANDS:
            return 3
        elif counter_change > THRESHOLD_CHANGED_HANDS_MEAS:
            return 7
        return 1


def calculate_events(pos_left, pos_right, case, score):
    if (case == 0 and score == 3) or ((case == 2 or case == 6) and score == 2) or (case == 5 and score == 1):
        trigger_hand, box_hand = pos_right, pos_left
    elif (case == 1 and score == 3) or ((case == 3 or case == 7) and score == 2) or (case == 4 and score == 1):
        trigger_hand, box_hand = pos_left, pos_right
    else:
        return 0, 0, 0, 0, 0

    e6 = len(pos_left) - 1

    try:
        v_th = np.array([pos[3] for pos in trigger_hand])
        v_bh = np.array([pos[3] for pos in box_hand])

        a_bh = np.array(np.diff(v_bh) * fs)

        # calculating e1
        e1 = np.argmax(v_bh > SPEED_THRESHOLD)
        while e1 > 1 and a_bh[e1] >= 0:
            e1 -= 1
        print("e1", e1)

        if score != 3:
            return e1, 0, 0, 0, 0

        # calculating e2
        piek_1 = np.argmax(v_bh[e1:e1 + 51]) + e1 - 1
        print("piek_1 ", piek_1)
        piek_2 = np.argmax(v_bh[piek_1 + 51:piek_1 + 1001]) + piek_1 + 50 - 1
        print("piek_2 ", piek_2)
        e2 = np.argmin(v_bh[piek_1:piek_2]) + piek_1 - 1
        print("e2 ", e2)

        # calculating e3
        z_bh = np.array([pos[2] for pos in box_hand])
        e3 = np.argmax(z_bh[1:e6])
        print("e3", e3)

        # calculating e4 and e5
        start_trigger = pos_left[0]

        e4 = 0
        for i in range(len(pos_left)):
            if trigger_hand[i][2] < MAX_HEIGHT_NEEDED + start_trigger[2] and \
                    trigger_hand[i][1] < MAX_LENGTH_NEEDED + start_trigger[1]:
                e4 = i

        while e4 > 1 and v_th[e4-1] >= SPEED_THRESHOLD:
            e4 -= 1

        e5 = len(pos_left) - 1
        while e5 > 1 and v_th[e5-1] >= SPEED_THRESHOLD:
            e5 -= 1

        if abs(e5 - e1) < 60:
            e5 = e4

        return e1, e2, e3, e4, e5
    except:
        return 0,0,0,0,0


def calculate_e6(xs):
    return len(xs) - 1


def calculate_extra_parameters(events, trigger_hand, box_hand):
    e1, e2, e3, e4, e5, e6 = events
    bx = np.array([pos[0] for pos in box_hand])
    by = np.array([pos[1] for pos in box_hand])
    bz = np.array([pos[2] for pos in box_hand])
    bv = np.array([pos[3] for pos in box_hand])

    tx = np.array([pos[0] for pos in trigger_hand])
    ty = np.array([pos[1] for pos in trigger_hand])
    tz = np.array([pos[2] for pos in trigger_hand])
    tv = np.array([pos[3] for pos in trigger_hand])

    # we berekenen 4 bimanuele parameters en 10 unimanuele parameters

    # total time = trigger press - start first movement
    # e5 kan hier gelijk zijn aan e5 dus zoek dat uit
    tt = (e6 - min(e1, e4)) / fs

    # temp coupling = start trigger hand - start second phase of box opening hand ??
    temp_coupling = (e4 - e2) / fs

    # movement overlap = end lid opening - start trigger hand
    mov_overlap = ((e3 - e4) / fs)

    # goal synchronization = trigger press - end lid opening
    goal_sync = (e6 - e3) / fs

    # unimanuele parameters
    # time box hand = end lid opening - start box hand
    t_bh = (e3 - e1) / fs

    # time 1st phase of box hand = start opening box - start of box hand
    t_bh_p1 = (e2 - e1) / fs

    # time 2nd phase of box hand = end of box hand - start opening box
    t_bh_p2 = (e3 - e2) / fs

    # time trigger hand = trigger press - start trigger hand
    # rekening houden met e4 en e5
    t_th = (e6 - e4) / fs

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
    dtx = tx[e4:e6]
    dty = ty[e4:e6]
    dtz = tz[e4:e6]

    dtx = np.diff(dtx)
    dty = np.diff(dty)
    dtz = np.diff(dtz)
    d_th = np.sqrt((dtx ** 2) + (dty ** 2) + (dtz ** 2))
    d_th = np.sum(d_th)

    return [tt, temp_coupling, mov_overlap, goal_sync], \
        [t_bh, t_bh_p1, t_bh_p2, t_th, smooth_bh, smooth_th, d_bh, d_bh_p1, d_bh_p2, d_th]

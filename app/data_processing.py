from constants import MAX_HEIGHT_NEEDED, POSITION_BUTTON, MAX_LENGTH_NEEDED, MIN_HEIGHT_NEEDED, MIN_LENGTH_NEEDED, \
    THRESHOLD_BOTH_HANDS, SPEED_THRESHOLD, HEIGHT_BOX, THRESHOLD_CHANGED_HANDS_MEAS
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
                                             (sen1.pos[1] + sen2.pos[1])/2,
                                             0))

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

    counter_left = 7*len(pos_left)/8
    counter_right = 7*len(pos_right)/8
    for i in range(-1,-len(pos_left),-1):
        if pos_left[i][2] < MAX_HEIGHT_NEEDED + start_left[2] and pos_left[i][1] < MAX_LENGTH_NEEDED + start_left[1]:
            counter_left -= 1
        if pos_right[i][2] < MAX_HEIGHT_NEEDED + start_right[2] and pos_right[i][1] < MAX_LENGTH_NEEDED + start_right[1]:
            counter_right -= 1

        if pos_left[i][2] > MIN_HEIGHT_NEEDED + start_left[2] and pos_left[i][1] > MIN_LENGTH_NEEDED + start_left[1]:
            counter_left += 1*len(pos_left)/4
        if pos_right[i][2] > MIN_HEIGHT_NEEDED + start_right[2] and pos_right[i][1] > MIN_LENGTH_NEEDED + start_right[1]:
            counter_right += 1*len(pos_left)/4

    if counter_left <= 0:
        return 4
    if counter_right <= 0:
        return 5

    mse_both_hands = 0
    counter_change = 0
    for time in range(-1,-len(pos_left),-1):
        for pos in range(1,3):
            mse_both_hands += (pos_left[time][pos] - pos_right[time][pos]) ** 2 / (3*len(pos_left))

        if pos_left[time][2] >= HEIGHT_BOX and pos_right[time][2] >= HEIGHT_BOX:
            counter_change += 1


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


def calculate_e4_e5(pos_left, pos_right, case, score):
    if case == 0 and score == 3:
        trigger_hand, box_hand = pos_right, pos_left
    elif case == 1 and score == 3:
        trigger_hand, box_hand = pos_left, pos_right
    else:
        return 0, 0

    start_trigger = pos_left[0]
    start_box = pos_right[0]
    anticipation = False
    e4 = 0

    mse_both_hands = 0

    for i in range(len(pos_left)):
        if trigger_hand[i][2] < MAX_HEIGHT_NEEDED + start_trigger[2] and trigger_hand[i][1] < MAX_LENGTH_NEEDED + start_trigger[1] \
                and not ( box_hand[i][2] < MAX_HEIGHT_NEEDED + start_box[2] and box_hand[i][1] < MAX_LENGTH_NEEDED + start_box[1] ):
            e4 = i

        for pos in range(1, 3):
            mse_both_hands += (pos_left[i][pos] - pos_right[i][pos]) ** 2 / (3 * len(pos_left))

    if mse_both_hands <= THRESHOLD_BOTH_HANDS*2:
        anticipation = True
        print('anticipation happening')

    v_tr = [pos[3] for pos in trigger_hand]

    while v_tr[e4] >= SPEED_THRESHOLD:
        e4 -= 1

    if not anticipation:
        return e4, e4

    speed_5 = min(v_tr[e4:e4+100])
    e5 = v_tr[e4:e4+100].index(speed_5)

    return e4, e5

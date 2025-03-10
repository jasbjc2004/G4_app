import numpy as np

from G4Track import *
import time
import matplotlib.pyplot as plt
from matplotlib.animation import FuncAnimation

file_directory = os.path.dirname(os.path.abspath(__file__))
src_cfg_file = os.path.join(file_directory, "first_calibration.g4c")


def calibration_to_center(sys_id):
    """
    Calibrate the system (facing the source), so the x-axis points to the right of the user, the y-axis to the front
    and the z-axis to the ceiling. Keep in mind that the hemisphere of the source is dynamic and needs time to adapt.
    :param sys_id: system id
    :type sys_id: int
    :return: the sensor who is on the left and right hand
    :rtype: bool
    """
    time.sleep(2)  # wait for the hemisphere to adapt
    hub_id = get_active_hubs(sys_id, True)[0]
    map = get_station_map(sys_id,hub_id)

    pos0, active_count, data_hubs = None, 0, 0
    while active_count == 0 & data_hubs == 0:
        pos0, active_count, data_hubs = get_frame_data(sys_id, [hub_id])

    frame_reference_orientation(sys_id, (90,180,0))
    #print(frame_reference_orientation(sys_id))

    sen1 = pos0.G4_sensor_per_hub[0]
    sen2 = pos0.G4_sensor_per_hub[1]
    frame_reference_translation(sys_id, ((sen1.pos[0] + sen2.pos[0])/2,
                                         min(sen1.pos[1], sen2.pos[1]),
                                         min(sen1.pos[2], sen2.pos[2])))

    time.sleep(2)
    return hub_id


connected, dongle_id = initialize_system(src_cfg_file)
print(f"Dongle id: {dongle_id}")

start_time = time.time()
elapsed_time = time.time() - start_time
if connected:
    print(set_units(dongle_id))
    hub_id = calibration_to_center(dongle_id)

    while elapsed_time < 1:
        frame_data, active_count, data_hubs = get_frame_data(dongle_id, [hub_id])
        elapsed_time = time.time() - start_time

        if (active_count, data_hubs) == (1, 1):
            sensor2 = frame_data.G4_sensor_per_hub[1]
            sensor1 = frame_data.G4_sensor_per_hub[0]
            # print(f"Sensor {1}:")
            print(f"  Position sensor 1: (x: {sensor1.pos[0]}, y: {sensor1.pos[1]}, z: {sensor1.pos[2]})              "
                  f"Position sensor 2: (x: {sensor2.pos[0]}, y: {sensor2.pos[1]}, z: {sensor2.pos[2]})")
            #print(f"  Orientation: (qx: {sensor1.ori[0]}, qy: {sensor1.or

else:
    print("Failed to connect.")

close_sensor()

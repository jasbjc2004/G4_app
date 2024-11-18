from G4Track import *
import time


def calibration_to_center(sys_id):
    """
    Calibrate the system (facing the source), so the x-axis points to the right of the user, the y-axis to the front
    and the z-axis to the floor. Keep in mind that the hemisphere of the source is dynamic and needs time to adapt.
    :param sys_id: system id
    :type sys_id: int
    :return: the sensor who is on the left and right hand
    :rtype: bool
    """
    time.sleep(2)  # wait for the hemisphere to adapt
    hub_id = get_active_hubs(sys_id, True)[0]
    station_map = get_station_map(sys_id, hub_id)

    pos0, active_count, data_hubs = None, 0, 0
    while active_count == 0 & data_hubs == 0:
        pos0, active_count, data_hubs = get_frame_data(sys_id, [hub_id])

    frame_reference_orientation(sys_id, (90, 180, 0))

    pos_ports = [i for i in range(0, len(station_map)) if station_map[i]]
    sen1 = pos0.G4_sensor_per_hub[pos_ports[0]]
    sen2 = pos0.G4_sensor_per_hub[pos_ports[1]]
    frame_reference_translation(sys_id, ((sen1.pos[0] + sen2.pos[0]) / 2,
                                         min(sen1.pos[1], sen2.pos[1]),
                                         min(sen1.pos[2], sen2.pos[2])))
    if sen1.pos[0] < sen2.pos[0]:
        lsen, rsen = pos_ports[0], pos_ports[1]
    else:
        lsen, rsen = pos_ports[1], pos_ports[0]

    time.sleep(2)
    return hub_id, lsen, rsen

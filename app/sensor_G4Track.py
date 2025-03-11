import ctypes as ct
import os
from enum import Enum

file_directory = os.path.dirname(os.path.abspath(__file__))
G4Track = ct.CDLL(os.path.join(file_directory, "NEEDED/FILES/G4Track.dll"))
G4_sensors_per_hub = 3


class G4SensorFrameData(ct.Structure):
    """
    Structure to receive position & orientation from each sensor with fields:

    :Attributes:
    - id:     zero-based sensor number
    - pos:    position [x, y, z] in inch or cm, according to g4_set_query
    - ori:    orientation in Euler (azimuth, elevation, roll) or in quaternions according to configuration
    """
    _fields_ = [("id", ct.c_uint32),
                ("pos", ct.c_float * 3),
                ("ori", ct.c_float * 4)]


class G4FrameData(ct.Structure):
    """
    Structure used by '`g4_get_frame_data`' to retrieve most recent frame's tracker data with fields:

    :Attributes:
    - hub:                hub id as reported by system
    - frame:              frame number which position & orientation corresponds
    - stationMap:         bit-map to indicate which sensor is active, 1 if its active
    - dig_io:             8-bit map that corresponds to the digital I/O-ports
    - G4_sensor_per_hub:  array of G4SensorFrameData that holds info of each sensor
    """
    _fields_ = [("hub", ct.c_uint32),
                ("frame", ct.c_uint32),
                ("stationMap", ct.c_uint32),
                ("dig_io", ct.c_uint32),
                ("G4_sensor_per_hub", G4SensorFrameData * G4_sensors_per_hub)]


class G4SRCMap(ct.Structure):
    """
    Structure used to retrieve position & orientation of each source with fields:

    :Attributes:
    - id:           zero-based if of the source (between 0 and 7)
    - freq:         zero-based frequency value (between 0 and 7: 0->A, 1->B, ...)
    - flr_cmp:      filter components of the source
    - start_hem:    start of the hemisphere?
    - pos:          position [x,y,z] of the source, in inch or cm according to the configuration
    - att:          orientation Euler [azimuth, elevation, pitch] or in quaternions (4 elements)
    """
    _fields_ = [("id", ct.c_uint),
                ("freq", ct.c_uint),
                ('flr_cmp', ct.c_uint),
                ('start_hem', ct.c_uint),
                ("pos", ct.c_float * 3),
                ("att", ct.c_float * 4)]


class G4CMDDataStruct(ct.Structure):
    """
    Structure used for specification of the sensor or extra parameters needed for the command with fields:

    :Attributes:
    - id:       result of G4_CREATE_ID
    - action:   specifies the action: set, get, reset (from the enum Action)
    - iParam:   command-specific integer
    - pParam:   command-specific object
    """
    _fields_ = [("id", ct.c_int32),
                ("action", ct.c_uint32),
                ("iParam", ct.c_uint32),
                ("pParam", ct.c_void_p)]


class G4CMDStruct(ct.Structure):
    """
    Structure used for the 'g4_set_query' to set/ read many configurations at once

    :Attributes:
    - cmd:    command to perform from COMMANDS
    - cds:    specification of the sensor or extra parameters needed for the command
    """
    _fields_ = [("cmd", ct.c_uint),
                ("cds", G4CMDDataStruct)]


class G4CMDBlockStruct(ct.Structure):
    """
    Structure used for the 'g4_set_query' to set/ read many configurations at once

    :Attributes:
    - units:            array with the units for the position and orientation from enum UNITS
    - version_info:     system version
    - filter_params:    takes the filter values (get and set possible)
    - increment:        array with an element for the position and the orientation (per sensor)
    - rot_angles:       the frame-of-reference of orientation (return or set)
    - tranlate_xyz:     the frame-of-reference of translation (return or set)
    - tip_offset:       position [x,y,z] of the offset (for each sensor)
    """
    _fields_ = [("units", ct.c_uint * 2),
                ("version_info", ct.c_int8 * 50),
                ("filter_params", (ct.c_float * 4) * 2),
                ("increment", (ct.c_float * 2) * G4_sensors_per_hub),
                ("rot_angles", ct.c_float * 3),
                ("translate_xyz", ct.c_float * 3),
                ("tip_offset", (ct.c_float * 3) * G4_sensors_per_hub)]


class G4SystemInfo(ct.Structure):
    """
    Structure used for the 'g4_set_query' to set/ read many configurations at once

    :Attributes:
    - G4TrackVer:       Version of the G4Track.dll
    - hw_ser_n:         serial number of the hub
    - rf_fw_pn:         Radio Frequency Firmware Part Number?
    - dsp_bt_fw_pn:     Digital Signal Processor Bluetooth Firmware Part Number?
    - dsp_app_fw_pn:    Digital Signal Processor Application Firmware Part Number?
    """
    _fields_ = [("G4TrackVer", ct.c_char * 64),
                ("hw_ser_no", ct.c_char * 16),
                ("rf_fw_pn", ct.c_char * 16),
                ("dsp_bt_fw_pn", ct.c_char * 16),
                ("dsp_app_fw_pn", ct.c_char * 16)]


class ERROR(Enum):
    """
    Errors as specified by Polhemus
    """
    G4_ERROR_NONE = 0
    G4_ERROR_NO_FRAME_DATA_AVAIL = -100
    G4_ERROR_UNSUPPORTED_ACTION = -99
    G4_ERROR_UNSUPPORTED_TYPE = -98
    G4_ERROR_UNSUPPORTED_COMMAND = -97
    G4_ERROR_INVALID_STATION = -96
    G4_ERROR_NO_CONNECTION = -95
    G4_ERROR_NO_HUBS = -94
    G4_ERROR_FRAMERATE_SET = -93
    G4_ERROR_MEMORY_ALLOCATION = -92
    G4_ERROR_INVALID_SYSTEM_ID = -91
    G4_ERROR_SRC_CFG_FILE_OPEN = -90
    G4_ERROR_INVALID_SRC_CFG_FILE = -89
    G4_ERROR_UNABLE_TO_START_TIMER = -88
    G4_ERROR_HUB_NOT_ACTIVE = -87
    G4_ERROR_SYS_RESET_FAIL = -86
    G4_ERROR_DONGLE_CONNECTION = -85
    G4_ERROR_DONGLE_USB_CONFIGURATION = -84
    G4_ERROR_DONGLE_USB_INTERFACE_0 = -83
    G4_ERROR_DUPLICATE_SYS_IDS = -82
    G4_ERROR_INVALID_WILDCARD_USE = -81
    G4_ERROR_TOTAL = -80


class COMMANDS(Enum):
    """
    Commands as specified by Polhemus
    """
    G4_CMD_WHOAMI = 0
    G4_CMD_GETMAXSRC = 1
    G4_CMD_BORESIGHT = 2
    G4_CMD_FILTER = 3
    G4_CMD_INCREMENT = 4
    G4_CMD_FOR_ROTATE = 5
    G4_CMD_FOR_TRANSLATE = 6
    G4_CMD_TIP_OFFSET = 7
    G4_CMD_UNITS = 8
    G4_CMD_GET_ACTIVE_HUBS = 9
    G4_CMD_GET_STATION_MAP = 10
    G4_CMD_GET_SOURCE_MAP = 11
    G4_CMD_FRAMERATE = 12
    G4_CMD_RESTORE_DEF_CFG = 13
    G4_CMD_BLOCK_CFG = 14
    G4_TOTAL_COMMANDS = 15


class ACTION(Enum):
    """
    Actions as specified by Polhemus
    """
    G4_ACTION_SET = 0
    G4_ACTION_GET = 1
    G4_ACTION_RESET = 2


class DATATYPE(Enum):
    """
    Datatypes as specified by Polhemus
    """
    G4_DATA_POS = 0
    G4_DATA_ORI = 1


class UNITS(Enum):
    """
    Type of translation and orientation as specified by Polhemus
    """
    G4_TYPE_EULER_DEGREE = 0
    G4_TYPE_EULER_RADIAN = 1
    G4_TYPE_QUATERNION = 2
    G4_TYPE_INCH = 3
    G4_TYPE_FOOT = 4
    G4_TYPE_CM = 5
    G4_TYPE_METER = 6


# uint32_t g4_init_sys(int* pDongleId,const char* src_cfg_file,void* reserved)
g4_init_sys = G4Track.g4_init_sys
g4_init_sys.argtypes = [ct.POINTER(ct.c_int), ct.c_char_p, ct.c_void_p]
g4_init_sys.restype = ct.c_uint32

# void g4_close_tracker(void)
g4_close_tracker = G4Track.g4_close_tracker
g4_close_tracker.argtypes = ()
g4_close_tracker.restype = None

# uint32_t g4_get_frame_data(G4_FRAMEDATA* fd_array, int sysId, const int* hub_id_list, int num_hubs)
g4_get_frame_data = G4Track.g4_get_frame_data
g4_get_frame_data.argtypes = [ct.POINTER(G4FrameData), ct.c_int,
                                      ct.POINTER(ct.c_int), ct.c_int]
g4_get_frame_data.restype = ct.c_uint32

# uint32_t g4_set_query(LPG4_CMD_STRUCT pcs)
g4_set_query = G4Track.g4_set_query
g4_set_query.argtypes = [ct.POINTER(G4CMDStruct)]
g4_set_query.restype = ct.c_uint32


def initialize_system(src_cfg_file):
    """
    Initialize the G4Track Libray. It must be called before any interaction using this library.
    :param src_cfg_file: source configuration file (.g4c)
    :type src_cfg_file: str
    :returns: a boolean which is True if the system is initialized (otherwise False) and the sytem id (if
        there is a connection available, otherwise None)
    :rtype: (bool, int)
    """
    dongle_id_c = ct.c_int()
    status = g4_init_sys(ct.byref(dongle_id_c), src_cfg_file.encode('utf-8'), ct.c_void_p(None))

    # numbers are still unsigned --> convert to signed by substracting 2^32 or 0x100000000
    if status > 0:
        status = status - 0x100000000

    if status == ERROR.G4_ERROR_NONE.value:
        return True, dongle_id_c.value
    elif status == ERROR.G4_ERROR_NO_CONNECTION.value:
        print(f"Error: No connection possible (status code: {status}).")
        return False, None
    else:
        print(f"Error: Unexpected status code {ERROR(status).name}.")
        return False, None


def close_sensor():
    """
    Delete connection with the sensor
    """
    G4Track = ct.CDLL(os.path.join(file_directory, "NEEDED/FILES/G4Track.dll"))
    g4_close_tracker()
    del G4Track


def get_frame_data(system_id, hub_id_list):
    """
    Enables the program to retrieve position & orientation from the hub (single frame, watch out with 120 Hz)
    :param system_id: source configuration file (.g4c)
    :type system_id: int
    :param hub_id_list: array of hub ids the user is requesting data from
    :type hub_id_list: list[int]
    :return: a struct with the position and orientation, a number of active hubs
     and a number of hubs worth of data returned in the fd (default set to 1)
    :rtype: (G4FrameData, int, int)
    """
    fd = G4FrameData()
    hub_id_c = (ct.c_int * len(hub_id_list))(*hub_id_list)
    res = g4_get_frame_data(ct.byref(fd), ct.c_int(system_id), hub_id_c, 1)

    res = res & 0xFFFFFFFF
    active_hubs = (res >> 16) & 0xFFFF
    hub_count = res & 0xFFFF

    return fd, active_hubs, hub_count


def create_id(sys=-1, hub=0, sensor=0):
    """
    Create an id of the given input, needed for the Commands ('set_query'), no parameters needed
    (id for all sensors and systems that are available)
    :param sys: id of the system, given with the funtion initialize_system (start with 1)
    :param hub: id of the hub
    :param sensor: id of the sensor
    :return: -1 if no parameters where given, otherwise a combination of the given parameters
    :rtype: int
    """
    if sys == -1:
        return -1

    return ((sys << 24) & 0xff000000) | ((hub << 8) & 0x0fff00) | (sensor & 0x7f)


def create_id_sensormap(sys, hub, sensormap):
    """
    Create an id of the given input, needed for the Commands ('set_query') using a sensor map
    :param sys: id of the system
    :type sys: int
    :param hub: id of the hub
    :type hub: int
    :param sensormap: sensor map from the command get_sensor_map or function get_frame_data
    :type sensormap: int
    :return: a combination of the given parameters
    :rtype: int
    """
    return create_id(sys, hub, sensormap) | 0x80


def id_to_sensormap(sens_id):
    """
    Convert a tuple of all sensor ids to a sensormap
    :param sens_id: a tuple containing all sensor ids
    :type sens_id: tuple[int]
    :return: sensormap
    :rtype: int
    """
    map = 0
    if 0 in sens_id:
        map += 1 << 2
    if 1 in sens_id:
        map += 1 << 2
    if 2 in sens_id:
        map += 1
    return map


def who_am_i(sys_id, hub_id=0, sensor_id=0):
    """
    Function to get the system information for a specific sensor of a hub
    :param sys_id: id of the system (result of the function initialize_system)
    :param hub_id: id of the hub
    :param sensor_id: id of the sensor
    :return: a struct of G4SystemInfo with the information of the system
    :rtype: G4SystemInfo
    """
    cmd_struct = G4CMDStruct()
    cmd_struct.cmd = COMMANDS.G4_CMD_WHOAMI.value
    cmd_struct.cds.id = create_id(sys_id, hub_id, sensor_id)
    cmd_struct.cds.action = ACTION.G4_ACTION_GET.value
    version_info = G4SystemInfo()
    cmd_struct.cds.pParam = ct.cast(ct.byref(version_info), ct.c_void_p)

    status = g4_set_query(ct.byref(cmd_struct))

    if status > 1:
        status = status - 0x100000000

    if status == ERROR.G4_ERROR_NONE.value:
        return version_info
    else:
        print(f"Error: Unexpected status code {ERROR(status).name}.")
        return None


def get_max_sources():
    """
    Function to know the maximum number of sources that can be connected to a single dongle
    :return: number of sources that can be connected
    :rtype: int
    """
    cmd_struct = G4CMDStruct()
    cmd_struct.cmd = COMMANDS.G4_CMD_GETMAXSRC.value

    status = g4_set_query(ct.byref(cmd_struct))

    if status > 0:
        status = status - 0x100000000

    if status == ERROR.G4_ERROR_NONE.value:
        return cmd_struct.cds.iParam
    else:
        print(f"Error: Unexpected status code {status}.")
        return None


def boresight(sys_id, hub_id, sen_id, pos_init=None):
    """
    Set or get the boresight of all sensors (sys_id = -1, only set) or a particular one
    :param sys_id: system id (-1 if all sensors are intended, only to set)
    :type sys_id: int
    :param hub_id: hub id (0 if all sensors are intended, only to set)
    :type hub_id: int
    :param sen_id: sensor id ((0,) if all sensors are intended, only to set)
    :type sen_id: tuple[int]
    :param pos_init: the position to set the boresight to (None to get the position)
    :type pos_init: tuple[float, float, float]
    :return: the position if there was no position given, otherwise the status
    """
    cmd_struct = G4CMDStruct()
    cmd_struct.cmd = COMMANDS.G4_CMD_BORESIGHT.value

    if len(sen_id) == 1:
        sen_id = sen_id[0]
        cmd_struct.cds.id = create_id(sys_id, hub_id, sen_id)
    else:
        cmd_struct.cds.id = create_id_sensormap(sys_id, hub_id, id_to_sensormap(sen_id))
    cmd_struct.cds.iParam = UNITS.G4_TYPE_EULER_DEGREE.value

    if pos_init is None:
        pos = (ct.c_int * 3)()
        cmd_struct.cds.action = ACTION.G4_ACTION_GET.value
    else:
        pos = (ct.c_int * 3)(*pos_init)
        cmd_struct.cds.action = ACTION.G4_ACTION_SET.value

    cmd_struct.cds.pParam = ct.cast(ct.byref(pos), ct.c_void_p)

    status = g4_set_query(ct.byref(cmd_struct))

    if status > 0:
        status = status - 0x100000000

    if status == ERROR.G4_ERROR_NONE.value:
        if pos_init is None:
            return list(pos)
        else:
            return True
    else:
        print(f"Error: Unexpected status code {ERROR(status).name}.")
        return False


def boresight_reset(sys_id=-1, hub_id=0, sen_id=(0,)):
    """
    Unboresight all sensors (no attributes given) or a particular one
    :param sys_id: system id (-1 if all sensors are intended)
    :type sys_id: int
    :param hub_id: hub id (0 if all sensors are intended)
    :type hub_id: int
    :param sen_id: sensor id ((0,) if all sensors are intended)
    :type sen_id: tuple[int]
    :return: status if it worked
    :rtype: bool
    """
    cmd_struct = G4CMDStruct()
    cmd_struct.cmd = COMMANDS.G4_CMD_BORESIGHT.value

    if len(sen_id) == 1:
        sen_id = sen_id[0]
        cmd_struct.cds.id = create_id(sys_id, hub_id, sen_id)
    else:
        cmd_struct.cds.id = create_id_sensormap(sys_id, hub_id, id_to_sensormap(sen_id))

    cmd_struct.cds.action = ACTION.G4_ACTION_RESET.value
    cmd_struct.cds.iParam = UNITS.G4_TYPE_EULER_DEGREE.value

    status = g4_set_query(ct.byref(cmd_struct))

    if status > 0:
        status = status - 0x100000000

    if status == ERROR.G4_ERROR_NONE.value:
        return True
    else:
        print(f"Error: Unexpected status code {ERROR(status).name}.")
        return False


def filter(sys_id, hub_id, return_pos=True, filter_coef_init=None):
    """
    Set or get the filter of a particular hub or all hubs (sys_id = -1, only set)
    :param sys_id: system id (-1 if all sensors are intended, only to set)
    :type sys_id: int
    :param hub_id: hub id (0 if all sensors are intended, only to set)
    :type hub_id: int
    :param return_pos: true if the function needs to set/ get a position, otherwise the orientation
    :type return_pos: bool
    :param filter_coef_init: the filter coefficients to set the filter to (None to get the position)
    :type filter_coef_init: tuple[float, float, float, float]
    :return: the position if there was no position given, otherwise the status
    """
    cmd_struct = G4CMDStruct()
    cmd_struct.cmd = COMMANDS.G4_CMD_FILTER.value

    cmd_struct.cds.id = create_id(sys_id, hub_id, 0)

    if return_pos:
        cmd_struct.cds.iParam = DATATYPE.G4_DATA_POS.value
    else:
        cmd_struct.cds.iParam = DATATYPE.G4_DATA_ORI.value

    if filter_coef_init is None:
        filter_coef = (ct.c_float * 4)()
        cmd_struct.cds.action = ACTION.G4_ACTION_GET.value
    else:
        filter_coef = (ct.c_float * 4)(*filter_coef_init)
        cmd_struct.cds.action = ACTION.G4_ACTION_SET.value

    cmd_struct.cds.pParam = ct.cast(ct.byref(filter_coef), ct.c_void_p)

    status = g4_set_query(ct.byref(cmd_struct))

    if status > 0:
        status = status - 0x100000000

    if status == ERROR.G4_ERROR_NONE.value:
        if filter_coef_init is None:
            return list(filter_coef)
        else:
            return True
    else:
        print(f"Error: Unexpected status code {ERROR(status).name}.")
        return False


def filter_reset(sys_id, hub_id, return_pos=True):
    """
    Reset the filter of a particular hub
    :param sys_id: system id (-1 if all sensors are intended)
    :type sys_id: int
    :param hub_id: hub id (0 if all sensors are intended)
    :type hub_id: int
    :param return_pos: true if the function needs to set/ get a position, otherwise the orientation
    :type return_pos: bool
    :return: the status
    """
    cmd_struct = G4CMDStruct()
    cmd_struct.cmd = COMMANDS.G4_CMD_FILTER.value

    cmd_struct.cds.id = create_id(sys_id, hub_id, 0)

    if return_pos:
        cmd_struct.cds.iParam = DATATYPE.G4_DATA_POS.value
    else:
        cmd_struct.cds.iParam = DATATYPE.G4_DATA_ORI.value

    cmd_struct.cds.action = ACTION.G4_ACTION_RESET.value
    status = g4_set_query(ct.byref(cmd_struct))

    if status > 0:
        status = status - 0x100000000

    if status == ERROR.G4_ERROR_NONE.value:
        return True
    else:
        print(f"Error: Unexpected status code {ERROR(status).name}.")
        return False


def increment(sys_id, hub_id, sen_id, posori_init=None):
    """
    Set or get the position and orientation increment of all sensors (sys_id = -1, only set) or a particular one
    :param sys_id: system id (-1 if all sensors are intended, only to set)
    :type sys_id: int
    :param hub_id: hub id (0 if all sensors are intended, only to set)
    :type hub_id: int
    :param sen_id: sensor id ((0,) if all sensors are intended, only to set)
    :type sen_id: tuple[int]
    :param posori_init: the increment to set the increment to (None to get), a negative value turns auto-increment on
    :type posori_init: tuple[float, float]
    :return: the position if there was no position given, otherwise the status
    """
    cmd_struct = G4CMDStruct()
    cmd_struct.cmd = COMMANDS.G4_CMD_INCREMENT.value

    if len(sen_id) == 1:
        sen_id = sen_id[0]
        cmd_struct.cds.id = create_id(sys_id, hub_id, sen_id)
    else:
        cmd_struct.cds.id = create_id_sensormap(sys_id, hub_id, id_to_sensormap(sen_id))
    cmd_struct.cds.iParam = UNITS.G4_TYPE_CM.value << 16 | UNITS.G4_TYPE_EULER_DEGREE.value

    if posori_init is None:
        posori = (ct.c_float * 2)()
        cmd_struct.cds.action = ACTION.G4_ACTION_GET.value
    else:
        posori = (ct.c_float * 2)(*posori_init)
        cmd_struct.cds.action = ACTION.G4_ACTION_SET.value

    cmd_struct.cds.pParam = ct.cast(ct.byref(posori), ct.c_void_p)

    status = g4_set_query(ct.byref(cmd_struct))

    if status > 0:
        status = status - 0x100000000

    if status == ERROR.G4_ERROR_NONE.value:
        if posori_init is None:
            return list(posori)
        else:
            return True
    else:
        print(f"Error: Unexpected status code {ERROR(status).name}.")
        return False


def increment_reset(sys_id=-1, hub_id=0, sen_id=(0,)):
    """
    Reset the position and orientation increment of all sensors (sys_id = -1, only set) or a particular one
    :param sys_id: system id (-1 if all sensors are intended, only to set)
    :type sys_id: int
    :param hub_id: hub id (0 if all sensors are intended, only to set)
    :type hub_id: int
    :param sen_id: sensor id ((0,) if all sensors are intended, only to set)
    :type sen_id: tuple[int]
    :return: the position if there was no position given, otherwise the status
    """
    cmd_struct = G4CMDStruct()
    cmd_struct.cmd = COMMANDS.G4_CMD_BORESIGHT.value

    if len(sen_id) == 1:
        sen_id = sen_id[0]
        cmd_struct.cds.id = create_id(sys_id, hub_id, sen_id)
    else:
        cmd_struct.cds.id = create_id_sensormap(sys_id, hub_id, id_to_sensormap(sen_id))
    cmd_struct.cds.iParam = UNITS.G4_TYPE_CM.value << 16 | UNITS.G4_TYPE_EULER_DEGREE.value
    cmd_struct.cds.action = ACTION.G4_ACTION_RESET.value
    status = g4_set_query(ct.byref(cmd_struct))

    if status > 0:
        status = status - 0x100000000

    if status == ERROR.G4_ERROR_NONE.value:
        return True
    else:
        print(f"Error: Unexpected status code {ERROR(status).name}.")
        return False


def frame_reference_orientation(sys_id, degree_init=None):
    """
    Set or get the frame of reference of rotation for all sensors (of a given system)
    :param sys_id: system id
    :type sys_id: int
    :param degree_init: the orientation to set the frame of reference to (None to get the position)
    :type degree_init: tuple[float, float, float]
    :return: the orientation of reference if there was no orientation given, otherwise the status
    """
    cmd_struct = G4CMDStruct()
    cmd_struct.cmd = COMMANDS.G4_CMD_FOR_ROTATE.value
    cmd_struct.cds.id = create_id(sys_id)
    cmd_struct.cds.iParam = UNITS.G4_TYPE_EULER_DEGREE.value

    if degree_init is None:
        degree = (ct.c_float * 3)()
        cmd_struct.cds.action = ACTION.G4_ACTION_GET.value
    else:
        degree = (ct.c_float * 3)(*degree_init)
        cmd_struct.cds.action = ACTION.G4_ACTION_SET.value

    cmd_struct.cds.pParam = ct.cast(ct.byref(degree), ct.c_void_p)
    status = g4_set_query(ct.byref(cmd_struct))

    if status > 0:
        status = status - 0x100000000

    if status == ERROR.G4_ERROR_NONE.value:
        if degree_init is None:
            return list(degree)
        else:
            return True
    else:
        print(f"Error: Unexpected status code {ERROR(status).name}.")
        return False


def frame_reference_orientation_reset(sys_id):
    """
    Set or get the frame of reference of rotation for all sensors (of a given system)
    :param sys_id: system id
    :type sys_id: int
    :return: the position if there was no position given, otherwise the status
    """
    cmd_struct = G4CMDStruct()
    cmd_struct.cmd = COMMANDS.G4_CMD_FOR_ROTATE.value
    cmd_struct.cds.id = create_id(sys_id)
    cmd_struct.cds.iParam = UNITS.G4_TYPE_EULER_DEGREE.value
    cmd_struct.cds.action = ACTION.G4_ACTION_RESET.value
    status = g4_set_query(ct.byref(cmd_struct))

    if status > 0:
        status = status - 0x100000000

    if status == ERROR.G4_ERROR_NONE.value:
        return True
    else:
        print(f"Error: Unexpected status code {ERROR(status).name}.")
        return False


def frame_reference_translation(sys_id, pos_init=None):
    """
    Set or get the frame of reference of translation for all sensors (of a given system)
    :param sys_id: system id
    :type sys_id: int
    :param pos_init: the position to set the frame of reference to (None to get the position)
    :type pos_init: tuple[float, float, float]
    :return: the position of reference if there was no position given, otherwise the status
    """
    cmd_struct = G4CMDStruct()
    cmd_struct.cmd = COMMANDS.G4_CMD_FOR_TRANSLATE.value
    cmd_struct.cds.id = create_id(sys_id)
    cmd_struct.cds.iParam = UNITS.G4_TYPE_CM.value

    if pos_init is None:
        pos = (ct.c_float * 3)()
        cmd_struct.cds.action = ACTION.G4_ACTION_GET.value
    else:
        pos = (ct.c_float * 3)(*pos_init)
        cmd_struct.cds.action = ACTION.G4_ACTION_SET.value

    cmd_struct.cds.pParam = ct.cast(ct.byref(pos), ct.c_void_p)
    status = g4_set_query(ct.byref(cmd_struct))

    if status > 0:
        status = status - 0x100000000

    if status == ERROR.G4_ERROR_NONE.value:
        if pos_init is None:
            return list(pos)
        else:
            return True
    else:
        print(f"Error: Unexpected status code {ERROR(status).name}.")
        return False


def frame_reference_translation_reset(sys_id):
    """
    Set or get the frame of reference of rotation for all sensors (of a given system)
    :param sys_id: system id
    :type sys_id: int
    :return: the position if there was no position given, otherwise the status
    """
    cmd_struct = G4CMDStruct()
    cmd_struct.cmd = COMMANDS.G4_CMD_FOR_TRANSLATE.value
    cmd_struct.cds.id = create_id(sys_id)
    cmd_struct.cds.iParam = UNITS.G4_TYPE_CM.value
    cmd_struct.cds.action = ACTION.G4_ACTION_RESET.value
    status = g4_set_query(ct.byref(cmd_struct))

    if status > 0:
        status = status - 0x100000000

    if status == ERROR.G4_ERROR_NONE.value:
        return True
    else:
        print(f"Error: Unexpected status code {ERROR(status).name}.")
        return False


def tip_offsets(sys_id, hub_id, sen_id, tof_init=None):
    """
    Extend or ofsset the center of a particular sensor (or sensormap)
    :param sys_id: system id (-1 if all sensors are intended, only to set)
    :type sys_id: int
    :param hub_id: hub id (0 if all sensors are intended, only to set)
    :type hub_id: int
    :param sen_id: sensor id ((0,) if all sensors are intended, only to set)
    :type sen_id: tuple[int]
    :param tof_init: the position to set the boresight to (None to get the position)
    :type tof_init: tuple[float, float, float]
    :return: the position if there was no position given, otherwise the status
    """
    cmd_struct = G4CMDStruct()
    cmd_struct.cmd = COMMANDS.G4_CMD_TIP_OFFSET.value

    if len(sen_id) == 1:
        sen_id = sen_id[0]
        cmd_struct.cds.id = create_id(sys_id, hub_id, sen_id)
    else:
        cmd_struct.cds.id = create_id_sensormap(sys_id, hub_id, id_to_sensormap(sen_id))
    cmd_struct.cds.iParam = UNITS.G4_TYPE_CM.value

    if tof_init is None:
        tof = (ct.c_float * 3)()
        cmd_struct.cds.action = ACTION.G4_ACTION_GET.value
    else:
        tof = (ct.c_float * 3)(*tof_init)
        cmd_struct.cds.action = ACTION.G4_ACTION_SET.value

    cmd_struct.cds.pParam = ct.cast(ct.byref(tof), ct.c_void_p)
    status = g4_set_query(ct.byref(cmd_struct))

    if status > 0x7FFFFFFF:
        status = status - 0x100000000

    if status == ERROR.G4_ERROR_NONE.value:
        if tof_init is None:
            return list(tof)
        else:
            return True
    else:
        print(f"Error: Unexpected status code {ERROR(status).name}.")
        return False


def tip_offsets_reset(sys_id, hub_id, sen_id):
    """
    Reset the center of a particular sensor (or sensormap)
    :param sys_id: system id (-1 if all sensors are intended, only to set)
    :type sys_id: int
    :param hub_id: hub id (0 if all sensors are intended, only to set)
    :type hub_id: int
    :param sen_id: sensor id ((0,) if all sensors are intended, only to set)
    :type sen_id: tuple[int]
    :return: the status
    :rtype: bool
    """
    cmd_struct = G4CMDStruct()
    cmd_struct.cmd = COMMANDS.G4_CMD_TIP_OFFSET.value

    if len(sen_id) == 1:
        sen_id = sen_id[0]
        cmd_struct.cds.id = create_id(sys_id, hub_id, sen_id)
    else:
        cmd_struct.cds.id = create_id_sensormap(sys_id, hub_id, id_to_sensormap(sen_id))
    cmd_struct.cds.iParam = UNITS.G4_TYPE_CM.value
    cmd_struct.cds.action = ACTION.G4_ACTION_RESET.value
    status = g4_set_query(ct.byref(cmd_struct))

    if status > 0:
        status = status - 0x100000000

    if status == ERROR.G4_ERROR_NONE.value:
        return True
    else:
        print(f"Error: Unexpected status code {ERROR(status).name}.")
        return False


def set_units(sys_id):
    """
    Set the units to cm and degree (possible to make a reset too)
    :param sys_id: system id
    :type sys_id: int
    :return: the status
    :rtype: bool
    """
    cmd_struct = G4CMDStruct()
    cmd_struct.cmd = COMMANDS.G4_CMD_UNITS.value
    cmd_struct.cds.id = create_id(sys_id, 0, 0)
    cmd_struct.cds.action = ACTION.G4_ACTION_SET.value
    cmd_struct.cds.iParam = DATATYPE.G4_DATA_ORI.value
    cmd_struct.cds.pParam = ct.cast(ct.pointer(ct.c_int(UNITS.G4_TYPE_EULER_DEGREE.value)), ct.c_void_p)
    status = g4_set_query(ct.byref(cmd_struct))

    if status > 0:
        status = status - 0x100000000

    if status != ERROR.G4_ERROR_NONE.value:
        print(f"Error: Unexpected status code {ERROR(status).name}.")
        return False

    cmd_struct.cds.iParam = DATATYPE.G4_DATA_POS.value
    cmd_struct.cds.pParam = ct.cast(ct.pointer(ct.c_int(UNITS.G4_TYPE_CM.value)), ct.c_void_p)
    status = g4_set_query(ct.byref(cmd_struct))

    if status > 0:
        status = status - 0x100000000

    if status == ERROR.G4_ERROR_NONE.value:
        return True
    else:
        print(f"Error: Unexpected status code {ERROR(status).name}.")
        return None


def get_units(sys_id, hub_id):
    """
    Get the units of the given system-id (orientation & translation)
    :param sys_id: system id
    :type sys_id: int
    :param hub_id: hub id
    :type hub_id: int
    :return: a tuple with the units of the orientation and translation
    :rtype: tuple[DATATYPE, DATATYPE]
    """
    res_ori = 0
    res_pos = 0

    cmd_struct = G4CMDStruct()
    cmd_struct.cmd = COMMANDS.G4_CMD_UNITS.value
    cmd_struct.cds.id = create_id(sys_id, hub_id, 0)
    cmd_struct.cds.action = ACTION.G4_ACTION_GET.value
    cmd_struct.cds.iParam = DATATYPE.G4_DATA_ORI.value
    res_ori_value = ct.c_uint(res_ori)
    cmd_struct.cds.pParam = ct.cast(ct.byref(res_ori_value), ct.c_void_p)
    status = g4_set_query(ct.byref(cmd_struct))
    res_ori = res_ori_value.value

    if status > 0:
        status = status - 0x100000000

    if status != ERROR.G4_ERROR_NONE.value:
        print(f"Error: Unexpected status code {ERROR(status).name}.")
        return None

    cmd_struct.cds.iParam = DATATYPE.G4_DATA_POS.value
    res_pos_value = ct.c_uint(res_pos)
    cmd_struct.cds.pParam = ct.cast(ct.byref(res_pos_value), ct.c_void_p)
    status = g4_set_query(ct.byref(cmd_struct))
    res_pos = res_pos_value.value

    if status == ERROR.G4_ERROR_NONE.value:
        return UNITS(res_ori).name, UNITS(res_pos).name
    else:
        print(f"Error: Unexpected status code {ERROR(status).name}.")
        return None


def get_active_hubs(sys_id, id_needed=False):
    """
    Get a number or all IDs of the active hubs (of a given system)
    :param sys_id: system ID
    :type sys_id: int
    :param id_needed: True if the function needs to give the hub ID
    :type id_needed: bool
    :return: the number of active hubs or the ID of these hubs (id_needed = True)
    :rtype: int | tuple[int]
    """
    cmd_struct = G4CMDStruct()
    cmd_struct.cmd = COMMANDS.G4_CMD_GET_ACTIVE_HUBS.value
    cmd_struct.cds.id = create_id(sys_id, 0, 0)
    cmd_struct.cds.action = ACTION.G4_ACTION_GET.value

    status = g4_set_query(ct.byref(cmd_struct))

    if status > 0:
        status = status - 0x100000000

    if status != ERROR.G4_ERROR_NONE.value:
        print(f"Error: Unexpected status code {ERROR(status).name}.")
        return None

    if id_needed:
        hub_ids = (ct.c_int * cmd_struct.cds.iParam)()
        cmd_struct.cds.pParam = ct.cast(ct.byref(hub_ids), ct.c_void_p)

        status = g4_set_query(ct.byref(cmd_struct))

        if status > 0:
            status = status - 0x100000000

        if status == ERROR.G4_ERROR_NONE.value:
            for i in range(cmd_struct.cds.iParam):
                hub_ids[i] = i

            return list(hub_ids)
        else:
            print(f"Error: Unexpected status code {ERROR(status).name}.")
            return None

    return cmd_struct.cds.iParam


def get_station_map(sys_id, hub_id):
    """
    Find the active sensor of a given hub, also possible with the function 'get_frame_data'
    :param sys_id: system id
    :type sys_id: int
    :param hub_id: hub id
    :type hub_id: int
    :return: a tuple with boolean to show which sensor is active
    :rtype: tuple[bool, bool, bool]
    """
    cmd_struct = G4CMDStruct()
    cmd_struct.cmd = COMMANDS.G4_CMD_GET_STATION_MAP.value
    cmd_struct.cds.id = create_id(sys_id, hub_id, 0)

    status = g4_set_query(ct.byref(cmd_struct))

    if status > 0:
        status = status - 0x100000000

    if status == ERROR.G4_ERROR_NONE.value:
        bits = format(cmd_struct.cds.iParam, f'{3}b')
        return tuple(bit == '1' for bit in bits)[::-1]
    else:
        print(f"Error: Unexpected status code {ERROR(status).name}.")
        return None


def get_source_map(sys_id):
    """
    Get the location of all sources (of a given system)
    :param sys_id: system id
    :type sys_id: int
    :return: an array with the information of all connected sources
    :rtype: list[G4SRCMap]
    """
    cmd_struct = G4CMDStruct()
    cmd_struct.cmd = COMMANDS.G4_CMD_GET_SOURCE_MAP.value
    cmd_struct.cds.id = create_id(sys_id, 0, 0)

    status = g4_set_query(ct.byref(cmd_struct))

    if status > 0:
        status = status - 0x100000000
    if status != ERROR.G4_ERROR_NONE.value:
        print(f"Error: Unexpected status code {ERROR(status).name}.")
        return False

    source_map = (G4SRCMap * cmd_struct.cds.iParam)()

    cmd_struct.cds.pParam = ct.cast(ct.byref(source_map), ct.c_void_p)
    cmd_struct.cds.iParam = ((UNITS.G4_TYPE_INCH.value << 16) | UNITS.G4_TYPE_EULER_DEGREE.value)

    status = g4_set_query(ct.byref(cmd_struct))

    if status > 0:
        status = status - 0x100000000

    if status == ERROR.G4_ERROR_NONE.value:
        return list(source_map)
    else:
        print(f"Error: Unexpected status code {ERROR(status).name}.")
        return False


def restore_default(sys_id=-1):
    """
    Restore the system to its default configuration
    :param sys_id: system id (default set to all systems)
    :type sys_id: int
    :return: the status
    :rtype: bool
    """
    cmd_struct = G4CMDStruct()
    cmd_struct.cmd = COMMANDS.G4_CMD_RESTORE_DEF_CFG.value
    cmd_struct.cds.id = create_id(sys_id, 0, 0)

    status = g4_set_query(ct.byref(cmd_struct))

    if status > 0:
        status = status - 0x100000000

    if status == ERROR.G4_ERROR_NONE.value:
        return True
    else:
        print(f"Error: Unexpected status code {ERROR(status).name}.")
        return False


def block_read_write(sys_id, hub_id, action):
    """
    (Not finished) Read, write or reset multiple configuration of a given hub
    :param sys_id: system id
    :type sys_id: int
    :param hub_id: hub id
    :type hub_id: int
    :param action: a string to specify the task of this function ('GET', 'SET', 'RESET')
    :type action: str
    :return: a G4CMDBlockStruct with the information of the given hub or a status
    :rtype: G4CMDBlockStruct | bool
    """
    cmd_struct = G4CMDStruct()
    cmd_struct.cmd = COMMANDS.G4_CMD_BLOCK_CFG.value
    cmd_struct.cds.id = create_id(sys_id, hub_id, 0)

    res = G4CMDBlockStruct()
    if action.lower() == 'set':
        cmd_struct.action = ACTION.G4_ACTION_SET.value
        res.units = (ct.c_uint * 2)(*[UNITS.G4_TYPE_CM.value, UNITS.G4_TYPE_EULER_DEGREE.value])
        # set all parameters here, still need to experiment with all
        cmd_struct.cds.pParam = ct.cast(ct.byref(res), ct.c_void_p)
    elif action.lower() == 'get':
        cmd_struct.action = ACTION.G4_ACTION_GET.value
        cmd_struct.cds.pParam = ct.cast(ct.byref(res), ct.c_void_p)
    else:
        cmd_struct.action = ACTION.G4_ACTION_RESET.value

    cmd_struct.cds.iParam = (UNITS.G4_TYPE_CM.value << 16 | UNITS.G4_TYPE_EULER_DEGREE.value)
    status = g4_set_query(ct.byref(cmd_struct))

    if status > 0:
        status = status - 0x100000000

    if status == ERROR.G4_ERROR_NONE.value:
        if action.lower() == 'get':
            return res
        else:
            return True
    else:
        print(f"Error: Unexpected status code {ERROR(status).name}.")
        return None


"Function and struct for stylus mode possible, but not needed"

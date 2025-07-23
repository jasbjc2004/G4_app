import logging
import os
import sys
from datetime import datetime

from constants import NAME_APP


def get_logbook(name='Unknown'):
    """
    Define a logger and log the error (or other info) with the name
    Usage:
    from logger import get_logger
    logger = get_logger(py-file)
    logger.debug("Loading main window")
    """

    logger = logging.getLogger(name)
    if logger.handlers:
        return logger

    # Determine log directory
    if getattr(sys, 'frozen', False):
        # Running as packaged executable
        log_dir = os.path.join(os.path.expanduser('~'), 'AppData', 'Roaming', NAME_APP, 'logs')
    else:
        # Running from source (PyCharm/development)
        log_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'logs')

    os.makedirs(log_dir, exist_ok=True)

    # Set minimum level of logger (DEBUG, INFO, WARNING, ERROR, CRITICAL)
    logger.setLevel(logging.WARNING)

    log_file = os.path.join(log_dir, f"app_{datetime.now().strftime('%Y%m%d')}.log")
    file_handler = logging.FileHandler(log_file)
    file_handler.setLevel(logging.WARNING)
    console_handler = logging.StreamHandler()
    console_handler.setLevel(logging.INFO)

    formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
    file_handler.setFormatter(formatter)
    console_handler.setFormatter(formatter)

    logger.addHandler(file_handler)
    logger.addHandler(console_handler)

    return logger

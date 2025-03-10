import serial
import serial.tools.list_ports


def find_serial_port(baudrate=9600, timeout=1):
    """Automatically find the correct serial port for the button."""
    ports = serial.tools.list_ports.comports()

    for port in ports:
        try:
            ser = serial.Serial(port.device, baudrate, timeout=timeout)
            print(f"Trying {port.device}...")

            # Read a small amount to check if it's the correct device
            ser.flushInput()
            data = ser.readline().decode().strip()
            if data:  # If we receive data, it's likely the correct port
                print(f"Found device on {port.device}")
                return ser  # Return the open serial connection
            ser.close()
        except (serial.SerialException, UnicodeDecodeError):
            continue

    print("No valid device found.")
    return None


def read_button(ser):
    """Continuously read button state from serial port."""
    if ser is None:
        print("No serial device found. Exiting.")
        return

    print(f"Listening on {ser.port}...")
    try:
        while True:
            if ser.in_waiting > 0:
                data = ser.readline().decode().strip()
                if data:
                    print(f"Button state: {data}")  # Modify based on what your device sends
    except KeyboardInterrupt:
        print("Stopped by user.")
    finally:
        ser.close()


# Usage
serial_conn = find_serial_port()
read_button(serial_conn)


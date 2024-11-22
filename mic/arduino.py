import serial
import glob
import time

BAUD_RATE = 115200
arduino_serial = None


def find_arduino_port():
    """
    Automatically detect the Arduino port on macOS.
    """
    # List all potential Arduino ports
    ports = glob.glob('/dev/cu.usbmodem*') + glob.glob('/dev/tty.usbmodem*')

    if not ports:
        print("No Arduino ports found.")
        return None

    for port in ports:
        try:
            # Attempt to open the port
            ser = serial.Serial(port, BAUD_RATE, timeout=1)
            ser.close()
            print(f"Arduino found on port: {port}")
            return port
        except (OSError, serial.SerialException):
            pass

    print("No responsive Arduino port found.")
    return None


def initialize_serial():
    """Initialize serial connection with Arduino."""
    global arduino_serial
    port = find_arduino_port()
    if not port:
        print("Failed to find Arduino port.")
        return False

    try:
        arduino_serial = serial.Serial(port, BAUD_RATE, timeout=1)
        time.sleep(2)  # Wait for Arduino to reset
        print(f"Serial connection established on {port}")
        return True
    except serial.SerialException as e:
        print(f"Failed to establish serial connection: {e}")
        arduino_serial = None
        return False


def send_message_to_arduino(message, max_retries=3):
    """Send a message to Arduino with retry mechanism."""
    global arduino_serial
    for _ in range(max_retries):
        print(f"Attempting to send message to Arduino: {message}")
        if arduino_serial:
            try:
                arduino_serial.write(message.encode('utf-8'))
                arduino_serial.flush()
                print(f"Sent to Arduino: {message}")
                return True
            except serial.SerialException as e:
                print(f"Error sending message to Arduino: {e}")
                reset_arduino()
            except Exception as e:
                print(f"Unexpected error sending message to Arduino: {e}")
        else:
            print("Arduino not connected. Attempting to connect...")
            initialize_serial()
        time.sleep(1)

    print(f"Failed to send message to Arduino after {max_retries} attempts")
    return False


def reset_arduino():
    """Reset the Arduino connection."""
    global arduino_serial
    print("Resetting Arduino connection...")
    if arduino_serial:
        arduino_serial.close()
    time.sleep(1)
    initialize_serial()


def check_arduino_connection():
    """Check and attempt to reconnect to Arduino if necessary."""
    global arduino_serial
    if arduino_serial is None or not arduino_serial.is_open:
        print("Arduino connection lost. Attempting to reconnect...")
        initialize_serial()
    return arduino_serial is not None and arduino_serial.is_open


def wait_for_arduino_message(expected_message="H", timeout=10):
    """Wait for a specific message from Arduino."""
    global arduino_serial
    start_time = time.time()
    while time.time() - start_time < timeout:
        if arduino_serial.in_waiting > 0:
            message = arduino_serial.readline().decode('utf-8').strip()
            print(f"Received from Arduino: {message}")
            if message == expected_message:
                return True
        time.sleep(0.1)
    print(f"Timeout waiting for message: {expected_message}")
    return False


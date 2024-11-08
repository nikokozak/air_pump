import pyaudio
import numpy as np
import wave
import serial
import time
import threading
import os
import librosa
import soundfile as sf
import glob
import serial.tools.list_ports

# Constants
CHUNK = 1024
FORMAT = pyaudio.paInt16
CHANNELS = 1 # This needs to be figured out in config.
RATE = 48000
RECORD_SECONDS = 300
WAVE_OUTPUT_FILENAME = "output.wav"
DECIBEL_THRESHOLD = -25
PLAYBACK_DECIBEL_THRESHOLD = -30  # Adjust this value as needed - make interactive system to do so.
DEFAULT_ARDUINO_PORT = "/dev/cu.usbmodem1101"
DEFAULT_INPUT_DEVICE = 0
DEFAULT_OUTPUT_DEVICE = 1
BAUD_RATE = 115200
PLAYBACK_SPEED = 0.8

# Global variables
arduino_serial = None
p = pyaudio.PyAudio()

############## Config Menu #######################

def list_devices():
    """List all available audio devices."""
    print("Available audio devices:")
    for i in range(p.get_device_count()):
        info = p.get_device_info_by_index(i)
        device_type = []
        if info['maxInputChannels'] > 0:
            device_type.append("Input")
        if info['maxOutputChannels'] > 0:
            device_type.append("Output")
        print(f"Device {i}: {info['name']} ({', '.join(device_type)})")

############### ARDUINO ######################

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

########################## AUDIO ###############################

def calculate_db(audio_data):
    """Calculate decibel level from audio data."""
    audio_data_float = audio_data.astype(np.float32)
    rms = np.sqrt(np.mean(audio_data_float**2))
    ref = 32768.0
    return 20 * np.log10(rms / ref) if rms > 0 else -96


def record_audio(input_device_index=None):
    """Record audio and send messages to Arduino based on volume."""
    if not check_arduino_connection():
        print("Cannot record audio without Arduino connection.")
        return

    print("Starting record_audio function")
    try:
        stream = p.open(format=FORMAT, channels=CHANNELS, rate=RATE,
                        input=True, input_device_index=input_device_index,
                        frames_per_buffer=CHUNK)
    except Exception as e:
        print(f"Error opening audio stream: {e}")
        return

    print(f"Recording... Format: {FORMAT}, Channels: {CHANNELS}, Rate: {RATE}")

    frames = []
    threshold_exceeded = False

    stop_recording_event = threading.Event()  # Use an Event object

    def listen_for_arduino_stop():
        global arduino_serial
        while not stop_recording_event.is_set():
            if arduino_serial.in_waiting > 0:
                message = arduino_serial.readline().decode('utf-8').strip()
                print(message)
                if message == "H":
                    print("Received stop signal from Arduino. Ending recording.")
                    stop_recording_event.set()  # Set the event
                    return
            time.sleep(0.1)

    arduino_thread = threading.Thread(target=listen_for_arduino_stop)
    arduino_thread.daemon = True
    arduino_thread.start()

    try:
        for _ in range(0, int(RATE / CHUNK * RECORD_SECONDS)):
            if stop_recording_event.is_set():  # Check the event
                print("Stopping recording due to Arduino signal")
                break

            data = stream.read(CHUNK, exception_on_overflow=False)
            frames.append(data)
            audio_data = np.frombuffer(data, dtype=np.int16)

            db = calculate_db(audio_data)
            print(f"Decibel Level: {db:.2f} dB")

            if db > DECIBEL_THRESHOLD and not threshold_exceeded:
                threshold_exceeded = True
                send_message_to_arduino("2")
            elif db <= DECIBEL_THRESHOLD and threshold_exceeded:
                threshold_exceeded = False
                send_message_to_arduino("b")

            time.sleep(0.001)

    except Exception as e:
        print(f"Error during recording loop: {e}")

    print("Finished recording loop")

    stream.stop_stream()
    stream.close()

    save_wave_file(frames)
    send_message_to_arduino("b")
    print("Sent final stop message to Arduino")


def save_wave_file(frames):
    """Save recorded audio to a wave file."""
    try:
        wf = wave.open(WAVE_OUTPUT_FILENAME, 'wb')
        wf.setnchannels(CHANNELS)
        wf.setsampwidth(p.get_sample_size(FORMAT))
        wf.setframerate(RATE)
        wf.writeframes(b''.join(frames))
        wf.close()
        print(f"Saved audio file: {WAVE_OUTPUT_FILENAME}")
    except Exception as e:
        print(f"Error saving WAV file: {e}")


def play_audio(file_name, output_device_index=None, playback_speed=PLAYBACK_SPEED):
    """Play audio file in reverse with adjustable speed and send messages to Arduino based on volume."""
    if not check_arduino_connection():
        print("Cannot play audio without Arduino connection.")
        return

    print("Starting play_audio function")
    try:
        y, sr = librosa.load(file_name, sr=None)
        y_reversed = y[::-1]  # Reverse the audio data
        y_slow = librosa.effects.time_stretch(y_reversed, rate=playback_speed)

        num_channels = 2 if y.ndim > 1 and y.shape[1] > 1 else 1
        device_info = p.get_device_info_by_index(
            output_device_index or p.get_default_output_device_info()['index'])
        supported_channels = device_info['maxOutputChannels']

        print(f"Audio channels: {num_channels}, Device supported channels: {supported_channels}")

        if num_channels > supported_channels:
            print(f"Converting {num_channels} channels to {supported_channels} channels")
            y_slow = librosa.to_mono(y_slow)
            num_channels = 1

        sf.write('temp_reversed.wav', y_slow, sr, subtype='PCM_16')
        wf = wave.open('temp_reversed.wav', 'rb')
        print(f"Opened wave file successfully. Channels: {wf.getnchannels()}, Sample width: {wf.getsampwidth()}, Frame rate: {wf.getframerate()}")
    except Exception as e:
        print(f"Error opening or processing wave file: {e}")
        return

    try:
        stream = p.open(format=p.get_format_from_width(wf.getsampwidth()),
                        channels=num_channels,
                        rate=wf.getframerate(),
                        output=True,
                        output_device_index=output_device_index)
        print("Opened audio stream successfully")
    except Exception as e:
        print(f"Error opening audio stream: {e}")
        wf.close()
        return

    play_audio_stream(wf, stream)

    stream.stop_stream()
    stream.close()
    wf.close()
    os.remove('temp_reversed.wav')

    print("play_audio function completed")


def play_audio_stream(wf, stream):
    """Play audio stream and handle Arduino messaging."""
    state = "OFF"
    on_count = off_count = 0
    ON_THRESHOLD = PLAYBACK_DECIBEL_THRESHOLD
    OFF_THRESHOLD = PLAYBACK_DECIBEL_THRESHOLD  # - 3
    STABILITY_COUNT = 3

    print("Playing...")

    try:
        data = wf.readframes(CHUNK)
        while data:
            stream.write(data)
            audio_data = np.frombuffer(data, dtype=np.int16)

            db = calculate_db(audio_data)
            print(f"Playback Decibel Level: {db:.2f} dB")

            if state == "OFF":
                if db > ON_THRESHOLD:
                    on_count += 1
                    off_count = 0
                    if on_count >= STABILITY_COUNT:
                        state = "ON"
                        send_message_to_arduino("1")
                        print(f"Threshold exceeded ({ON_THRESHOLD} dB), turning ON")
                else:
                    on_count = 0
            elif state == "ON":
                if db < OFF_THRESHOLD:
                    off_count += 1
                    on_count = 0
                    if off_count >= STABILITY_COUNT:
                        state = "OFF"
                        send_message_to_arduino("a")
                        print(
                            f"Below threshold ({OFF_THRESHOLD} dB), turning OFF")
                else:
                    off_count = 0

            data = wf.readframes(CHUNK)

        print("Finished playback.")
    except KeyboardInterrupt:
        print("\nPlayback interrupted by user.")
    except Exception as e:
        print(f"Error during playback: {e}")
    finally:
        send_message_to_arduino("a")
        print("Sent final stop message to Arduino")


######################## ARDUINO ################################

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

######################### CONFIG MENU ##############################

def menu():
    """Main menu for user interaction."""
    global arduino_serial
    input_device_index = DEFAULT_INPUT_DEVICE
    output_device_index = DEFAULT_OUTPUT_DEVICE

    if not arduino_serial:
        initialize_serial()

    while True:
        print("\nMenu:")
        print("1. Start system")
        print("2. List devices and change input/output")
        # print("1. Record Audio")
        # print("2. Play Audio")
        # print("3. List devices and change input/output")
        print("3. Exit")
        choice = input("Enter your choice: ")

        print(f"You chose option: {choice}")

        if choice == '1':
            print("System ready")
            while True:
                if wait_for_arduino_message("H"):
                    print("Arduino is ready, preparing to record audio...")
                    record_audio(input_device_index)
                    if wait_for_arduino_message("H"):
                        print("Preparing to play audio...")
                        if not os.path.exists(WAVE_OUTPUT_FILENAME):
                            print(f"Error: Audio file {WAVE_OUTPUT_FILENAME} does not exist. Please record audio first.")
                            continue
                        play_audio(WAVE_OUTPUT_FILENAME, output_device_index)
                    else:
                        print("Failed to receive ready signal from Arduino.")
                else:
                    print("Failed to receive ready signal from Arduino.")
        elif choice == '2':
            list_devices()
            input_device_index = int(input(
                "Enter the input device index for recording (or press Enter for default): ") or DEFAULT_INPUT_DEVICE)
            output_device_index = int(input(
                "Enter the output device index for playback (or press Enter for default): ") or DEFAULT_OUTPUT_DEVICE)
        elif choice == '3':
            break
        else:
            print("Invalid choice. Please try again.")

    if arduino_serial:
        arduino_serial.close()


if __name__ == "__main__":
    if initialize_serial():
        menu()
    else:
        print("Unable to connect to Arduino. Exiting.")
    p.terminate()

import pyaudio
import numpy as np
import wave
import serial
import time

# Constants
CHUNK = 1024  # Number of audio samples per buffer
FORMAT = pyaudio.paInt16  # Audio format (16-bit PCM)
CHANNELS = 2  # Number of audio channels
RATE = 48000  # Sampling rate (samples per second)
RECORD_SECONDS = 5  # Duration of recording
WAVE_OUTPUT_FILENAME = "output.wav"  # Output file name
DECIBEL_THRESHOLD = -20  # Add this line

# Global variables
arduino_serial = None
p = pyaudio.PyAudio()  # Initialize PyAudio
DEFAULT_ARDUINO_PORT = "/dev/cu.usbmodem1101"
DEFAULT_INPUT_DEVICE = 0
DEFAULT_OUTPUT_DEVICE = 1

def list_devices():
    print("Available audio devices:")
    for i in range(p.get_device_count()):
        info = p.get_device_info_by_index(i)
        device_type = []
        if info['maxInputChannels'] > 0:
            device_type.append("Input")
        if info['maxOutputChannels'] > 0:
            device_type.append("Output")
        print(f"Device {i}: {info['name']} ({', '.join(device_type)})")

def record_audio(input_device_index=None):
    # Open stream
    stream = p.open(format=FORMAT,
                    channels=CHANNELS,
                    rate=RATE,
                    input=True,
                    input_device_index=input_device_index,
                    frames_per_buffer=CHUNK)

    print("Recording...")

    frames = []
    threshold_exceeded = False

    # Record and process audio
    for _ in range(0, int(RATE / CHUNK * RECORD_SECONDS)):
        data = stream.read(CHUNK)
        frames.append(data)
        audio_data = np.frombuffer(data, dtype=np.int16)
        
        # Improved decibel calculation
        audio_data_float = audio_data.astype(np.float32)
        rms = np.sqrt(np.mean(audio_data_float**2))
        
        # Reference value for 16-bit audio
        ref = 32768.0
        
        if rms > 0:
            db = 20 * np.log10(rms / ref)
        else:
            db = -96  # Approximate lowest possible dB for 16-bit audio
        
        print(f"Decibel Level: {db:.2f} dB")

        # Check if the threshold is exceeded
        if db > DECIBEL_THRESHOLD and not threshold_exceeded:
            threshold_exceeded = True
            send_message_to_arduino("1")  # Send '1' when threshold is exceeded
        elif db <= DECIBEL_THRESHOLD and threshold_exceeded:
            threshold_exceeded = False
            send_message_to_arduino("a")  # Send 'a' when it returns to a lower value

    print("Finished recording.")

    # Stop and close the stream
    stream.stop_stream()
    stream.close()

    # Save the recorded data as a WAV file
    wf = wave.open(WAVE_OUTPUT_FILENAME, 'wb')
    wf.setnchannels(CHANNELS)
    wf.setsampwidth(p.get_sample_size(FORMAT))
    wf.setframerate(RATE)
    wf.writeframes(b''.join(frames))
    wf.close()

def play_audio(file_name, output_device_index=None):
    wf = wave.open(file_name, 'rb')
    stream = p.open(format=p.get_format_from_width(wf.getsampwidth()),
                    channels=wf.getnchannels(),
                    rate=wf.getframerate(),
                    output=True,
                    output_device_index=output_device_index)

    threshold_exceeded = False
    print("Playing...")

    data = wf.readframes(CHUNK)
    while data:
        stream.write(data)
        audio_data = np.frombuffer(data, dtype=np.int16)
        
        # Decibel calculation
        audio_data_float = audio_data.astype(np.float32)
        rms = np.sqrt(np.mean(audio_data_float**2))
        
        # Reference value for 16-bit audio
        ref = 32768.0
        
        if rms > 0:
            db = 20 * np.log10(rms / ref)
        else:
            db = -96  # Approximate lowest possible dB for 16-bit audio
        
        print(f"Playback Decibel Level: {db:.2f} dB")

        # Check if the threshold is exceeded
        if db > DECIBEL_THRESHOLD and not threshold_exceeded:
            threshold_exceeded = True
            send_message_to_arduino("2")  # Send '2' when threshold is exceeded
        elif db <= DECIBEL_THRESHOLD and threshold_exceeded:
            threshold_exceeded = False
            send_message_to_arduino("b")  # Send 'b' when it returns to a lower value

        data = wf.readframes(CHUNK)

    print("Finished playback.")
    stream.stop_stream()
    stream.close()

def initialize_serial(port, baud_rate):
    global arduino_serial
    try:
        arduino_serial = serial.Serial(port, baud_rate, timeout=1)
        time.sleep(2)  # Allow time for Arduino to reset
        print(f"Serial connection established on {port}")
    except serial.SerialException as e:
        print(f"Failed to establish serial connection: {e}")

def read_from_arduino():
    if arduino_serial and arduino_serial.in_waiting:
        return arduino_serial.readline().decode('utf-8').strip()
    return None

def write_to_arduino(data):
    if arduino_serial:
        arduino_serial.write(data.encode('utf-8'))
        arduino_serial.flush()

def send_message_to_arduino(message):
    if arduino_serial:
        arduino_serial.write(message.encode('utf-8'))
        arduino_serial.flush()
        print(f"Sent to Arduino: {message}")
    else:
        print("Arduino not connected. Message not sent.")

def menu():
    input_device_index = DEFAULT_INPUT_DEVICE
    output_device_index = DEFAULT_OUTPUT_DEVICE

    while True:
        print("\nMenu:")
        print("1. Record Audio")
        print("2. Play Audio")
        print("3. Re-list devices and change input/output")
        print("4. Read from Arduino")
        print("5. Write to Arduino")
        print("6. Exit")
        choice = input("Enter your choice: ")

        if choice == '1':
            record_audio(input_device_index)
        elif choice == '2':
            play_audio(WAVE_OUTPUT_FILENAME, output_device_index)
        elif choice == '3':
            list_devices()
            input_device_index = int(input("Enter the input device index for recording (or press Enter for default): ") or DEFAULT_INPUT_DEVICE)
            output_device_index = int(input("Enter the output device index for playback (or press Enter for default): ") or DEFAULT_OUTPUT_DEVICE)
        elif choice == '4':
            data = read_from_arduino()
            if data:
                print(f"Received from Arduino: {data}")
            else:
                print("No data received from Arduino")
        elif choice == '5':
            message = input("Enter message to send to Arduino: ")
            write_to_arduino(message)
        elif choice == '6':
            break
        else:
            print("Invalid choice. Please try again.")

    if arduino_serial:
        arduino_serial.close()

if __name__ == "__main__":
    port = input(f"Enter the Arduino serial port (or press Enter for default {DEFAULT_ARDUINO_PORT}): ") or DEFAULT_ARDUINO_PORT
    baud_rate = 9600  # Make sure this matches the baud rate in your Arduino sketch
    initialize_serial(port, baud_rate)
    menu()
    p.terminate()  # Terminate PyAudio when done

import pyaudio
import numpy as np
import wave
import serial
import time
import threading
import os
import librosa
import soundfile as sf

# Constants
CHUNK = 1024
FORMAT = pyaudio.paInt16
CHANNELS = 2
RATE = 48000
RECORD_SECONDS = 5
WAVE_OUTPUT_FILENAME = "output.wav"
DECIBEL_THRESHOLD = -20

# Global variables
arduino_serial = None
p = pyaudio.PyAudio()
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

def initialize_serial(port, baud_rate):
    global arduino_serial
    try:
        arduino_serial = serial.Serial(port, baud_rate, timeout=1)
        time.sleep(2)
        print(f"Serial connection established on {port}")
    except serial.SerialException as e:
        print(f"Failed to establish serial connection: {e}")
        arduino_serial = None

def send_message_to_arduino(message, max_retries=3):
    global arduino_serial
    retries = 0
    while retries < max_retries:
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
            initialize_serial(port, baud_rate)
        
        retries += 1
        time.sleep(1)
    
    print(f"Failed to send message to Arduino after {max_retries} attempts")
    return False

def reset_arduino():
    global arduino_serial
    print("Resetting Arduino connection...")
    if arduino_serial:
        arduino_serial.close()
    time.sleep(1)
    initialize_serial(port, baud_rate)

def check_arduino_connection():
    global arduino_serial
    if arduino_serial is None or not arduino_serial.is_open:
        print("Arduino connection lost. Attempting to reconnect...")
        initialize_serial(port, baud_rate)
    return arduino_serial is not None and arduino_serial.is_open

def record_audio(input_device_index=None):
    if not check_arduino_connection():
        print("Cannot record audio without Arduino connection.")
        return

    print("Starting record_audio function")
    try:
        device_info = p.get_device_info_by_index(input_device_index if input_device_index is not None else p.get_default_input_device_info()['index'])
        print(f"Input device info: {device_info}")
        
        stream = p.open(format=FORMAT,
                        channels=CHANNELS,
                        rate=RATE,
                        input=True,
                        input_device_index=input_device_index,
                        frames_per_buffer=CHUNK)
    except Exception as e:
        print(f"Error opening audio stream: {e}")
        return

    print(f"Recording... Format: {FORMAT}, Channels: {CHANNELS}, Rate: {RATE}")

    frames = []
    threshold_exceeded = False

    try:
        for i in range(0, int(RATE / CHUNK * RECORD_SECONDS)):
            print(f"Recording frame {i}")
            try:
                data = stream.read(CHUNK, exception_on_overflow=False)
            except Exception as e:
                print(f"Error reading audio data: {e}")
                continue

            frames.append(data)
            audio_data = np.frombuffer(data, dtype=np.int16)
            
            audio_data_float = audio_data.astype(np.float32)
            rms = np.sqrt(np.mean(audio_data_float**2))
            
            ref = 32768.0
            
            if rms > 0:
                db = 20 * np.log10(rms / ref)
            else:
                db = -96
            
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

    try:
        stream.stop_stream()
        stream.close()
    except Exception as e:
        print(f"Error closing audio stream: {e}")

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

    send_message_to_arduino("b")
    print("Sent final stop message to Arduino")

def play_audio(file_name, output_device_index=None, playback_speed=0.5):
    if not check_arduino_connection():
        print("Cannot play audio without Arduino connection.")
        return

    print("Starting play_audio function")
    try:
        # Load the audio file
        y, sr = librosa.load(file_name, sr=None)
        
        # Time-stretch the audio without changing pitch
        y_slow = librosa.effects.time_stretch(y, rate=playback_speed)
        
        # Get the number of channels in the original audio
        num_channels = 2 if y.ndim > 1 and y.shape[1] > 1 else 1
        
        # Get the supported channels for the output device
        device_info = p.get_device_info_by_index(output_device_index if output_device_index is not None else p.get_default_output_device_info()['index'])
        supported_channels = device_info['maxOutputChannels']
        
        print(f"Audio channels: {num_channels}, Device supported channels: {supported_channels}")
        
        # Convert to mono if necessary
        if num_channels > supported_channels:
            print(f"Converting {num_channels} channels to {supported_channels} channels")
            y_slow = librosa.to_mono(y_slow)
            num_channels = 1
        
        # Write the time-stretched audio to a temporary file
        sf.write('temp_slow.wav', y_slow, sr, subtype='PCM_16')
        wf = wave.open('temp_slow.wav', 'rb')
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

    state = "OFF"
    on_count = 0
    off_count = 0
    ON_THRESHOLD = DECIBEL_THRESHOLD
    OFF_THRESHOLD = DECIBEL_THRESHOLD - 3
    STABILITY_COUNT = 5

    print("Playing...")

    try:
        data = wf.readframes(CHUNK)
        while data:
            stream.write(data)
            audio_data = np.frombuffer(data, dtype=np.int16)
            
            audio_data_float = audio_data.astype(np.float32)
            rms = np.sqrt(np.mean(audio_data_float**2))
            
            ref = 32768.0
            
            if rms > 0:
                db = 20 * np.log10(rms / ref)
            else:
                db = -96
            
            print(f"Playback Decibel Level: {db:.2f} dB")

            if state == "OFF":
                if db > ON_THRESHOLD:
                    on_count += 1
                    off_count = 0
                    if on_count >= STABILITY_COUNT:
                        state = "ON"
                        send_message_to_arduino("1")
                        print("Threshold exceeded, turning ON")
                else:
                    on_count = 0
            elif state == "ON":
                if db < OFF_THRESHOLD:
                    off_count += 1
                    on_count = 0
                    if off_count >= STABILITY_COUNT:
                        state = "OFF"
                        send_message_to_arduino("a")
                        print("Below threshold, turning OFF")
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
        stream.stop_stream()
        stream.close()
        wf.close()
        os.remove('temp_slow.wav')

    print("play_audio function completed")

def menu():
    global arduino_serial
    input_device_index = DEFAULT_INPUT_DEVICE
    output_device_index = DEFAULT_OUTPUT_DEVICE

    if not arduino_serial:
        initialize_serial(port, baud_rate)

    while True:
        print("\nMenu:")
        print("1. Record Audio")
        print("2. Play Audio")
        print("3. Re-list devices and change input/output")
        print("4. Read from Arduino")
        print("5. Write to Arduino")
        print("6. Exit")
        choice = input("Enter your choice: ")

        print(f"You chose option: {choice}")

        if choice == '1':
            print("Preparing to record audio...")
            record_audio(input_device_index)
        elif choice == '2':
            print("Preparing to play audio...")
            if not os.path.exists(WAVE_OUTPUT_FILENAME):
                print(f"Error: Audio file {WAVE_OUTPUT_FILENAME} does not exist. Please record audio first.")
                continue
            playback_speed = float(input("Enter playback speed (e.g., 0.5 for half speed): ") or 1.0)
            play_audio(WAVE_OUTPUT_FILENAME, output_device_index, playback_speed)
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
    baud_rate = 115200
    initialize_serial(port, baud_rate)
    menu()
    p.terminate()

import pyaudio
import numpy as np
import wave
import librosa
import soundfile as sf
import os
import threading
import time
from mic.arduino import send_message_to_arduino, check_arduino_connection

CHUNK = 1024
FORMAT = pyaudio.paInt16
CHANNELS = 1
RATE = 48000
RECORD_SECONDS = 300
WAVE_OUTPUT_FILENAME = "output.wav"
DECIBEL_THRESHOLD = -25
PLAYBACK_DECIBEL_THRESHOLD = -30
PLAYBACK_SPEED = 0.8

p = pyaudio.PyAudio()

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
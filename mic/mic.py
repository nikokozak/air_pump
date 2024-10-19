import pyaudio
import numpy as np
import wave

# Constants
CHUNK = 1024  # Number of audio samples per buffer
FORMAT = pyaudio.paInt16  # Audio format (16-bit PCM)
CHANNELS = 2  # Number of audio channels
RATE = 48000  # Sampling rate (samples per second)
RECORD_SECONDS = 5  # Duration of recording
WAVE_OUTPUT_FILENAME = "output.wav"  # Output file name

# Initialize PyAudio
p = pyaudio.PyAudio()

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

    data = wf.readframes(CHUNK)
    while data:
        stream.write(data)
        data = wf.readframes(CHUNK)

    stream.stop_stream()
    stream.close()

def menu():
    input_device_index = None
    output_device_index = None

    while True:
        if input_device_index is None or output_device_index is None:
            list_devices()
            input_device_index = int(input("Enter the input device index for recording: "))
            output_device_index = int(input("Enter the output device index for playback: "))

        print("\nMenu:")
        print("1. Record Audio")
        print("2. Play Audio")
        print("3. Re-list devices and change input/output")
        print("4. Exit")
        choice = input("Enter your choice: ")

        if choice == '1':
            record_audio(input_device_index)
        elif choice == '2':
            play_audio(WAVE_OUTPUT_FILENAME, output_device_index)
        elif choice == '3':
            input_device_index = None
            output_device_index = None
        elif choice == '4':
            break
        else:
            print("Invalid choice. Please try again.")

menu()

# Terminate PyAudio
p.terminate()

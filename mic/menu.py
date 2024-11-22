from .arduino import initialize_serial, wait_for_arduino_message
from .sound import record_audio, play_audio, WAVE_OUTPUT_FILENAME
import os
import pyaudio

p = pyaudio.PyAudio()

DEFAULT_INPUT_DEVICE = 0
DEFAULT_OUTPUT_DEVICE = 1


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
                            print(f"Error: Audio file {
                                  WAVE_OUTPUT_FILENAME} does not exist. Please record audio first.")
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

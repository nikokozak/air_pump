from mic.arduino import initialize_serial
from mic.menu import menu
import pyaudio

p = pyaudio.PyAudio()

if __name__ == "__main__":
    if initialize_serial():
        menu()
    else:
        print("Unable to connect to Arduino. Exiting.")
    p.terminate()

from mic.arduino import initialize_serial
from mic.menu import menu
import pyaudio

p = pyaudio.PyAudio()

def run_system(config):
    pass
    # breathe cycle on repeat.
        # within breathe cycle, IF on inhale, check for peaks in DB.
        # IF peak, trigger inflation MAX, until time of inhale cycle ends.
        # IF on exhale, previous inhale recorded audio, play back exhale.

if __name__ == "__main__":
    if initialize_serial():
        # The following is pseudo-code until we implement it.

        menu() # configuration menu, should return a configuration object
        # run_system(config) # main loop
    else:
        print("Unable to connect to Arduino. Exiting.")
    p.terminate()

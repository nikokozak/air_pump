import processing.sound.*;
import processing.serial.*;

// Constants
final int CHUNK = 1024;
final int CHANNELS = 2;
final int RATE = 44100;
final int RECORD_SECONDS = 5;
final String WAVE_OUTPUT_FILENAME = "output.wav";
final float DECIBEL_THRESHOLD = -20;

// Global variables
Serial arduino;
AudioIn input;
Amplitude amp;
AudioRecorder recorder;
SoundFile soundFile;
FFT fft;

String DEFAULT_ARDUINO_PORT = "/dev/cu.usbmodem1101";
int DEFAULT_INPUT_DEVICE = 0;
int DEFAULT_OUTPUT_DEVICE = 1;
int inputDeviceIndex = DEFAULT_INPUT_DEVICE;
int outputDeviceIndex = DEFAULT_OUTPUT_DEVICE;
boolean isRecording = false;
boolean isPlaying = false;
float playbackSpeed = 1.0;

void setup() {
  size(600, 400);
  textAlign(LEFT, TOP);
  
  // Initialize audio
  Sound.list();
  input = new AudioIn(this, inputDeviceIndex);
  amp = new Amplitude(this);
  recorder = new AudioRecorder(this);
  fft = new FFT(this, CHUNK);
  
  // Initialize serial
  printArray(Serial.list());
  String port = DEFAULT_ARDUINO_PORT;
  try {
    arduino = new Serial(this, port, 115200);
    println("Serial connection established on " + port);
  } catch (Exception e) {
    println("Failed to establish serial connection: " + e.getMessage());
  }
  
  showMenu();
}

void draw() {
  background(200);
  if (isRecording) {
    recordAudio();
  }
  if (isPlaying) {
    monitorPlayback();
  }
}

void keyPressed() {
  switch(key) {
    case '1':
      startRecording();
      break;
    case '2':
      startPlayback();
      break;
    case '3':
      listDevices();
      break;
    case '4':
      readFromArduino();
      break;
    case '5':
      writeToArduino();
      break;
    case '6':
      exit();
      break;
    default:
      println("Invalid choice. Please try again.");
  }
}

void showMenu() {
  background(200);
  text("Menu:", 10, 10);
  text("1. Record Audio", 10, 30);
  text("2. Play Audio", 10, 50);
  text("3. Re-list devices and change input/output", 10, 70);
  text("4. Read from Arduino", 10, 90);
  text("5. Write to Arduino", 10, 110);
  text("6. Exit", 10, 130);
  text("Press a number key to select an option", 10, 170);
}

void listDevices() {
  println("Available audio devices:");
  Sound.list();
  inputDeviceIndex = int(inputDeviceIndex);
  outputDeviceIndex = int(outputDeviceIndex);
  println("Input device set to: " + inputDeviceIndex);
  println("Output device set to: " + outputDeviceIndex);
  input = new AudioIn(this, inputDeviceIndex);
}

void startRecording() {
  if (!isRecording) {
    println("Preparing to record audio...");
    input.start();
    recorder.beginRecord();
    isRecording = true;
    println("Recording started...");
  }
}

void recordAudio() {
  if (isRecording) {
    float level = input.analyze();
    float db = 20 * log10(level);
    println("Recording Decibel Level: " + db + " dB");
    
    if (db > DECIBEL_THRESHOLD) {
      sendMessageToArduino("2");
    } else {
      sendMessageToArduino("b");
    }
    
    if (frameCount % (RATE * RECORD_SECONDS) == 0) {
      stopRecording();
    }
  }
}

void stopRecording() {
  if (isRecording) {
    recorder.endRecord();
    recorder.save(WAVE_OUTPUT_FILENAME);
    input.stop();
    isRecording = false;
    println("Recording stopped and saved.");
    sendMessageToArduino("b");
  }
}

void startPlayback() {
  if (!isPlaying) {
    println("Preparing to play audio...");
    soundFile = new SoundFile(this, WAVE_OUTPUT_FILENAME);
    if (soundFile != null) {
      soundFile.rate(playbackSpeed);
      soundFile.play();
      fft.input(soundFile);
      isPlaying = true;
      println("Playing audio...");
    } else {
      println("Error: Audio file not found. Please record audio first.");
    }
  }
}

void monitorPlayback() {
  if (isPlaying) {
    fft.analyze();
    float sum = 0;
    for (int i = 0; i < fft.spectrum.length; i++) {
      sum += fft.spectrum[i] * fft.spectrum[i];
    }
    float rms = sqrt(sum / fft.spectrum.length);
    float db = 20 * log10(rms);
    println("Playback Decibel Level: " + db + " dB");
    
    if (db > DECIBEL_THRESHOLD) {
      sendMessageToArduino("1");
    } else {
      sendMessageToArduino("a");
    }
    
    if (!soundFile.isPlaying()) {
      isPlaying = false;
      println("Playback finished.");
      sendMessageToArduino("a");
    }
  }
}

void sendMessageToArduino(String message) {
  if (arduino != null) {
    try {
      arduino.write(message);
      println("Sent to Arduino: " + message);
    } catch (Exception e) {
      println("Error sending message to Arduino: " + e.getMessage());
    }
  } else {
    println("Arduino not connected. Message not sent.");
  }
}

void readFromArduino() {
  if (arduino != null && arduino.available() > 0) {
    String data = arduino.readStringUntil('\n');
    if (data != null) {
      println("Received from Arduino: " + data.trim());
    }
  } else {
    println("No data received from Arduino");
  }
}

void writeToArduino() {
  String message = "Test message";  // You can modify this to get user input
  sendMessageToArduino(message);
}

void exit() {
  if (arduino != null) {
    arduino.stop();
  }
  super.exit();
}

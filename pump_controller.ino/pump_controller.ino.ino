#include <RotaryEncoder.h>

#define MOTOR1_PIN 10
#define MOTOR2_PIN 11

// Rotary Encoder 1 pins
#define ENCODER1_CLK 5
#define ENCODER1_DT 6
#define ENCODER1_SW 9

// Rotary Encoder 2 pins
#define ENCODER2_CLK 12
#define ENCODER2_DT 13
#define ENCODER2_SW A0

RotaryEncoder encoder1(ENCODER1_DT, ENCODER1_CLK, RotaryEncoder::LatchMode::TWO03);
RotaryEncoder encoder2(ENCODER2_DT, ENCODER2_CLK, RotaryEncoder::LatchMode::TWO03);

void checkPosition() {
  encoder1.tick();
  encoder2.tick();
}

void setup() {
  pinMode(MOTOR1_PIN, OUTPUT);
  pinMode(MOTOR2_PIN, OUTPUT);
  
  pinMode(ENCODER1_SW, INPUT_PULLUP);
  pinMode(ENCODER2_SW, INPUT_PULLUP);
  
  attachInterrupt(digitalPinToInterrupt(ENCODER1_CLK), checkPosition, CHANGE);
  attachInterrupt(digitalPinToInterrupt(ENCODER2_CLK), checkPosition, CHANGE);
  
  Serial.begin(9600);
  while (!Serial) {
    ; // Wait for serial port to connect
  }
  
  Serial.println("Pump Controller Ready");
}

void loop() {
  static unsigned long lastSerialCheck = 0;
  static unsigned long lastEncoderCheck = 0;
  unsigned long currentMillis = millis();

  // Check for serial input every 10ms
  if (currentMillis - lastSerialCheck >= 10) {
    lastSerialCheck = currentMillis;
    if (Serial.available() > 0) {
      char command = Serial.read();
      handleCommand(command);
    }
  }

  // Check encoder values and switches every 50ms
  if (currentMillis - lastEncoderCheck >= 50) {
    lastEncoderCheck = currentMillis;
    checkEncoders();
    checkEncoderSwitches();
  }
}

void handleCommand(char command) {
  switch (command) {
    case '1':
      pumpMotor(1);
      break;
    case '2':
      pumpMotor(2);
      break;
    case 'a':
      stopMotor(1);
      break;
    case 'b':
      stopMotor(2);
      break;
    default:
      Serial.println("Invalid command");
  }
}

void checkEncoders() {
  static int lastPos1 = 0;
  static int lastPos2 = 0;

  int newPos1 = encoder1.getPosition();
  if (newPos1 != lastPos1) {
    Serial.print("E1:");
    Serial.println(newPos1);
    lastPos1 = newPos1;
  }

  int newPos2 = encoder2.getPosition();
  if (newPos2 != lastPos2) {
    Serial.print("E2:");
    Serial.println(newPos2);
    lastPos2 = newPos2;
  }
}

void checkEncoderSwitches() {
  if (digitalRead(ENCODER1_SW) == LOW) {
    Serial.println("S1");
  }

  if (digitalRead(ENCODER2_SW) == LOW) {
    Serial.println("S2");
  }
}

void pumpMotor(int motorNumber) {
  int motorPin = (motorNumber == 1) ? MOTOR1_PIN : MOTOR2_PIN;
  digitalWrite(motorPin, HIGH);
  Serial.print("Motor ");
  Serial.print(motorNumber);
  Serial.println(" pumping");
}

void stopMotor(int motorNumber) {
  int motorPin = (motorNumber == 1) ? MOTOR1_PIN : MOTOR2_PIN;
  digitalWrite(motorPin, LOW);
  Serial.print("Motor ");
  Serial.print(motorNumber);
  Serial.println(" stopped");
}

#include <RotaryEncoder.h>

#define MOTOR1_PIN 10
#define MOTOR2_PIN 11

// Rotary Encoder 1 pins
#define ENCODER1_CLK 5
#define ENCODER1_DT 6
#define ENCODER1_SW 9

// Unit Pins
#define USER_BUTTON 12
#define USER_LED 13

RotaryEncoder encoder1(ENCODER1_DT, ENCODER1_CLK, RotaryEncoder::LatchMode::TWO03);
int buttonState = HIGH; // Default button state
int prevButtonState = HIGH;
int ledState = LOW;

void checkPosition() {
  encoder1.tick();
}

void setup() {
  pinMode(MOTOR1_PIN, OUTPUT);
  pinMode(MOTOR2_PIN, OUTPUT);
  
  pinMode(ENCODER1_SW, INPUT_PULLUP);

  pinMode(USER_BUTTON, INPUT_PULLUP);
  pinMode(USER_LED, OUTPUT);
  
  attachInterrupt(digitalPinToInterrupt(ENCODER1_CLK), checkPosition, CHANGE);
  
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

  digitalWrite(USER_LED, HIGH);

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

  buttonState = digitalRead(USER_BUTTON);

  if (buttonState == LOW && prevButtonState != LOW) { // Switch is pressed!
      Serial.println("H");
      prevButtonState = buttonState;
  } else if (buttonState == HIGH && prevButtonState == LOW) { // Switch is not pressed!
      prevButtonState = HIGH;
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
    case 'c':
      userLED(500);
    case 'd':
      userLED(1000);
    case 'e':
      digitalWrite(USER_LED, HIGH);
    case 'f':
      digitalWrite(USER_LED, LOW);
    // H writes button HIGH;
    default:
      Serial.println("Invalid command");
  }
}

void checkEncoders() {
  static int lastPos1 = 0;

  int newPos1 = encoder1.getPosition();
  if (newPos1 != lastPos1) {
    Serial.print("E1:");
    Serial.println(newPos1);
    lastPos1 = newPos1;
  }
}

void checkEncoderSwitches() {
  if (digitalRead(ENCODER1_SW) == LOW) {
    Serial.println("S1");
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

void userLED(int speed) {
  int isTime = speed % millis();
  if (isTime == 0) {
    if (ledState == 0) {
      digitalWrite(USER_LED, HIGH);
      ledState == 1;
    } else {
      digitalWrite(USER_LED, LOW);
      ledState == 0;
    }
  } 
}

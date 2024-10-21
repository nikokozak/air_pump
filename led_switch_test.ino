const int LED_PIN = 12;
const int SWITCH_PIN = 13;

void setup() {
  pinMode(LED_PIN, OUTPUT);
  pinMode(SWITCH_PIN, INPUT_PULLUP);
  Serial.begin(9600);
}

void loop() {
  // Read the switch state
  int switchState = digitalRead(SWITCH_PIN);

  // If switch is pressed (LOW due to pullup), turn on LED
  if (switchState == LOW) {
    digitalWrite(LED_PIN, HIGH);
    Serial.println("Switch pressed, LED ON");
  } else {
    digitalWrite(LED_PIN, LOW);
    Serial.println("Switch released, LED OFF");
  }

  delay(100);  // Small delay to debounce and limit serial output
}


#include <Wire.h>
#include "Adafruit_SHT31.h"

Adafruit_SHT31 sht31 = Adafruit_SHT31();

const int SOIL1 = A0;
const int SOIL2 = A1;
const int SOIL3 = A2;

void setup() {
  Serial.begin(115200);
  if (!sht31.begin(0x44)) {
    Serial.println("SHT31_ERROR");
  }
}

void loop() {
  // Como el USB se enciende y apaga por fuera, aquí leemos directo
  int soil1 = analogRead(SOIL1);
  int soil2 = analogRead(SOIL2);
  int soil3 = analogRead(SOIL3);

  float temp = sht31.readTemperature();
  float hum = sht31.readHumidity();

  Serial.print("SOIL1:"); Serial.print(soil1);
  Serial.print(",SOIL2:"); Serial.print(soil2);
  Serial.print(",SOIL3:"); Serial.print(soil3);
  Serial.print(",TEMP:"); Serial.print(temp);
  Serial.print(",HUM:"); Serial.println(hum);

  delay(2000); // Envía datos cada 2 segundos mientras esté vivo
}
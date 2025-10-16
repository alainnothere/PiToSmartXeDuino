#ifndef SrxeSerialHelper_h
#define SrxeSerialHelper_h
#include <Arduino.h>

class SrxeSerialHelper {
public:
  uint8_t readUint8() {
    while (!Serial.available());
    return Serial.read();
  }
  
  uint16_t readUint16() {
    while (!Serial.available());
    uint16_t high = Serial.read();
    while (!Serial.available());
    uint16_t low = Serial.read();
    return (high << 8) | low;
  }
};

#endif

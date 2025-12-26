#include "SoftClockSerial.h"

// Pin definitions
const int softSerialRx = RX_PIN;    // TMS
const int softSerialTx = 31;    // TCK
const int softSerialClock = 32; // TDO

// Create the ONE instance here
SoftClockSerial softSerial(softSerialTx, softSerialRx, softSerialClock);

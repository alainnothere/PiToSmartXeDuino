#include "SerialHelpers.h"
#include "SmartResponseXEmt.h"



uint8_t lastCommandReceived = -1;
uint8_t lastKeyPressed = -1;
bool shiftPressed = false;
bool symPressed = false;
static uint32_t lastUpdate = 0;
static uint8_t spinnerIndex = 0;
uint16_t pixelsScrolled = 0;
unsigned long lastMillis = 0;
unsigned long avgOfExecutions = 17;

bool enableShowStatusBar = true;
bool enableDebugThroughSerial = true;
bool enableDebugToScreen = true;

extern int __heap_start, *__brkval;

int freeMemory() {
    int v;
    return (int) &v - (__brkval == 0 ? (int) &__heap_start : (int) __brkval);
}


void showStatusBar () {

	if (!enableShowStatusBar) {
		return;
	}

	uint8_t status[] = {'/', '-', '\\', '|'};

	avgOfExecutions = (avgOfExecutions * 3 + (millis() - lastMillis)) >> 2;



#ifdef USING_SOFTWARE_SERIAL
	//               0           1           2         3         4
	//               1234 56 78901 23 45 67 89012345 67 89 01 23456789012
	sprintf(buffer, "CMD:%02X KEY:%02X S%02X R%04X C%02X %c %c          %c",
			lastCommandReceived,
			lastKeyPressed,
			Serial.framingErrors(),
			freeMemory(),
			(unsigned int)(avgOfExecutions & 0xFF),
			enableDebugThroughSerial ? 'Z' : '_',
			enableDebugToScreen ? 'D' : '_',
			status[spinnerIndex]);

#else
	//               0           1           2         3         4
	//               1234 56 78901 23 45678901 23 45 67 890123456789012
	sprintf(buffer, "CMD:%02X KEY:%02X R%04X C%02X %c %c              %c", lastCommandReceived, lastKeyPressed, freeMemory(), (unsigned int)(avgOfExecutions & 0xFF),
			enableDebugThroughSerial ? 'Z' : '_',
			enableDebugToScreen ? 'D' : '_',
			status[spinnerIndex]);
#endif

	if (millis() - lastUpdate > 250) {   // change every 100 ms
	    lastUpdate = millis();
	    spinnerIndex++;
	    spinnerIndex = spinnerIndex % sizeof(status);
	    //sendDebugPacket(buffer);
	}

	SRXEWriteString(0, 0 + pixelsScrolled, buffer, FONT_NORMAL, 3, 0);
	SRXEHorizontalLine(0,9+ pixelsScrolled,128,3,1);

	lastMillis = millis();
}

void sendReadyForNextCommandPacket() {
    Serial.write(CMD_PADDING_MARKER);
    Serial.write(CMD_PADDING_MARKER);
    Serial.write(READY_FOR_NEXT_COMMAND);
#ifdef USING_SOFTWARE_SERIAL
    Serial.update();
#endif
}

void sendDebugPacket(char* message) {
	sendDebugPacket(message, 10);
}

void sendDebugPacket(char* message, uint8_t line) {

	if (enableDebugToScreen)
	{
		SRXEWriteString(0, line + pixelsScrolled, message, FONT_NORMAL, 3, 0);
	}
	if (enableDebugThroughSerial)
	{
		Serial.write(DEBUG_START_MARKER);

		for (int i = 0; i < strlen(message); i++) {
			Serial.write(message[i]);
		}

		Serial.write(DEBUG_END_MARKER);
	}

}

void sendKeyPacket(byte key) {
  /**
   * Send a single keyboard packet:
   * [0xFD] [KEY] [CHECKSUM] [0xFE]
   * where CHECKSUM = 0xFD XOR KEY
   */
  Serial.write(KEY_START_MARKER);
  Serial.write(key);
  Serial.write(KEY_START_MARKER ^ key);
  Serial.write(KEY_END_MARKER);

}

uint8_t serialReadUint8() {
    while (!Serial.available()) {
        // Waiting - available() runs the clock
    }
    return Serial.read();
}

uint16_t serialReadUint16() {
    uint8_t high = serialReadUint8();
    uint8_t low = serialReadUint8();
    return (high << 8) | low;
}

const uint8_t bufferSize = 64;
const uint8_t numberOfCharsToPossiblyReceive = bufferSize - 1;
char buffer[bufferSize];

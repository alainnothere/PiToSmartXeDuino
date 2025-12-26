#ifndef SERIAL_HELPERS_H
#define SERIAL_HELPERS_H

#include "SerialConfig.h"
#include <Arduino.h>

// Protocol markers
#ifdef USING_SOFTWARE_SERIAL
	#define BAUD_RATE			   115200
#endif

// Debug packet markers
#define DEBUG_START_MARKER       0xFA
#define DEBUG_END_MARKER         0xFB

// Single key packet markers (legacy, still used for special keys like Sym+0/1/2/3)
#define KEY_START_MARKER         0xFD
#define KEY_END_MARKER           0xFE

// Line input packet markers (new buffered input)
// Format: [LINE_START_MARKER][LENGTH][...data...][CHECKSUM][LINE_END_MARKER]
// CHECKSUM = LINE_START_MARKER ^ LENGTH ^ (XOR of all data bytes)
#define LINE_START_MARKER        0xF8
#define LINE_END_MARKER          0xF9

// Ready signal
#define READY_FOR_NEXT_COMMAND   0xFC

// Padding/invalid command marker
#define CMD_PADDING_MARKER       0xFF

// Command codes (sent from Pi to Arduino)
#define CMD_WRITE_TEXT           0x02
#define CMD_SCROLL_UP            0x03
#define CMD_PRINT_BLOCK_RLE      0x04
#define CMD_PRINT_BLOCK          0x05
#define CMD_CLEAR_SCREEN         0x06
#define CMD_PRINT_PROMPT         0x07
#define CMD_PRINT_BATCH_TO_SCREEN 0x08

// Key modifier codes (for special key handling)
#define KEY_MODIFIER_SHIFT       0x10
#define KEY_MODIFIER_SYM         0x11

// Declare functions (defined in .cpp)
void sendReadyForNextCommandPacket();
void sendDebugPacket(char* message);
void sendDebugPacket(char* message, uint8_t line);
uint8_t serialReadUint8();
uint16_t serialReadUint16();
void sendKeyPacket(byte key);
void showStatusBar();

// Shared buffer and state variables
extern const uint8_t bufferSize;
extern const uint8_t numberOfCharsToPossiblyReceive;
extern char buffer[];
extern uint16_t pixelsScrolled;

extern uint8_t lastCommandReceived;
extern uint8_t lastKeyPressed;
extern bool shiftPressed;
extern bool symPressed;

extern bool enableShowStatusBar;
extern bool enableDebugThroughSerial;
extern bool enableDebugToScreen;

#endif

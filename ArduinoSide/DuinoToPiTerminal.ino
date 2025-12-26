/*
 * Smart Response XE Terminal Controller
 *
 * This Arduino acts as a hardware terminal for a Raspberry Pi, providing
 * keyboard input and display output over serial communication.
 *
 * DISPLAY ARCHITECTURE:
 * - The Arduino supports 4 font sizes with different dimensions:
 *   Font 0 (NORMAL): 52 cols × 17 rows, 8 pixels per row
 *   Font 1 (SMALL):  64 cols × 17 rows, 8 pixels per row
 *   Font 2 (MEDIUM): 42 cols × 8 rows,  16 pixels per row
 *   Font 3 (LARGE):  35 cols × 8 rows,  16 pixels per row
 *
 * - The Arduino displays exactly what the Pi tells it to display at
 *   specified pixel coordinates. No buffering or state management.
 *
 * KEYBOARD PROTOCOL:
 * - Regular key presses send a 4-byte packet:
 *   [0xFD] [KEY] [CHECKSUM] [0xFE]
 *   where CHECKSUM = 0xFD XOR KEY
 *
 * - Modifier keys (Shift/Sym) with undefined mappings send TWO packets:
 *   Packet 1: [0xFD] [MODIFIER] [CHECKSUM] [0xFE]
 *             where MODIFIER = 0x10 (Shift) or 0x11 (Sym)
 *   Packet 2: [0xFD] [KEY] [CHECKSUM] [0xFE]
 *             where KEY is the base key code
 *
 * - Special keys use their mapped codes (DEL=0x08, arrows, screen keys, etc)
 *
 * COMMAND PROTOCOL:
 * - Pi sends commands, Arduino executes and responds
 * - After processing each command, Arduino sends:
 *   [0xFF] [0xFF] [0xFC]
 *   (two completion markers, then ready signal)
 *
 * COMMANDS:
 * - 0x01: Clear screen
 * - 0x02: Write text at position with font/colors
 *   Format: [CMD] [X_high] [X_low] [Y_high] [Y_low] [FONT] [FG] [BG] [LEN_high] [LEN_low] [TEXT...]
 *
 * SCREEN LAYOUT:
 * - The screen is oriented with row 0 at the TOP, increasing downward
 * - Row numbering: 0 (top) → 16 or 7 (bottom), depending on font
 *
 * For a 17-row font (Font 0 or 1):
 *   Row 0:  Oldest visible output
 *   Row 1:
 *   ...
 *   Row 15: Newest output (most recent command result)
 *   Row 16: Command prompt (where user types) ← BOTTOM
 *
 * For an 8-row font (Font 2 or 3):
 *   Row 9:  Oldest visible output (rows 0-8 are off-screen but in buffer)
 *   Row 10:
 *   ...
 *   Row 15: Newest output (most recent command result)
 *   Row 16: Command prompt (where user types) ← BOTTOM
 *
 * Output scrolls UP: new lines appear at row 15, old lines move toward row 0
 * and eventually scroll off the top (but remain in the Pi's buffer).
 */

#include "SmartResponseXEmt.h"
#include "SerialHelpers.h"
#include "SrxeCommandHandler.h"
#include "SerialConfig.h"


// Create instances
SrxeCommandHandler commandHandler;

void setup() {

	Serial.begin(BAUD_RATE);
	SRXEInit(0xe7, 0xd6, 0xa2);
	SRXEScrollReset();  // Reset scroll to 0
	SRXEScrollArea(0, 136, 24);
	SRXEFill(0);
	SRXEWriteString(0, 100, "Terminal Ready", FONT_LARGE, 3, 0);
	SRXEWriteString(0, 120, "Waiting for Pi...", FONT_LARGE, 3, 0);
	sendReadyForNextCommandPacket();
}

void loop() {
	commandHandler.handleReadKeyboard();
	showStatusBar();

	Serial.update();
	if (Serial.available()) {
		lastCommandReceived = Serial.read();

		switch (lastCommandReceived) {
		case CMD_CLEAR_SCREEN:
			commandHandler.handleClearScreen();
			break;

		case CMD_PRINT_PROMPT:
			commandHandler.handleWritePromptText();
			break;

		case CMD_WRITE_TEXT:
			commandHandler.handleWriteText();
			break;

		case CMD_SCROLL_UP:
			commandHandler.handleScrollUp();
			showStatusBar();
			break;

		case CMD_PRINT_BLOCK_RLE:
			commandHandler.printBlockRle();
			break;

		case CMD_PRINT_BLOCK:
			commandHandler.printBlock();
			break;

		default:
			// in case it's not a command I'm expecting and discard
			// the rest of the communication
			while (Serial.available()) {
				Serial.read();
			}
			sprintf(buffer, "Invalid CMD:%02X", lastCommandReceived);
			sendDebugPacket(buffer,32);
		}

		sendReadyForNextCommandPacket();
	}
}

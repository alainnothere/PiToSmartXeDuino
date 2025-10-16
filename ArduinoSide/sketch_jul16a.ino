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
#include "SrxeKeyboard.h"
#include "SrxeSerialHelper.h"
#include "SrxeCommandHandler.h"

#define BAUD_RATE 115200


#define CMD_CLEAR_SCREEN            0x01
#define CMD_WRITE_TEXT              0x02
#define CMD_SCROLL_UP               0x03

#define CMD_READY_FOR_NEXT_COMMAND  0xFC
#define CMD_COMPLETITION_MARKER     0xFF

// Create instances
SrxeKeyboard keyboard;
SrxeSerialHelper serialHelper;
SrxeCommandHandler commandHandler(&serialHelper);

void setup() {
  Serial.begin(BAUD_RATE);
  SRXEInit(0xe7, 0xd6, 0xa2);
  SRXEScrollArea(0,136,24);
  SRXEFill(0);
  SRXEWriteString(0, 20, "Terminal Ready", FONT_LARGE, 3, 0);
  SRXEWriteString(0, 40, "Waiting for Pi...", FONT_LARGE, 2, 0);
  
  // Send initial ready signal
  Serial.write(0xFC);  // Ready marker
}

void loop() {
  keyboard.readKeyboard();
  
  // ===== SERIAL INPUT -> PROCESS COMMANDS =====
  if (Serial.available()) {
    uint8_t cmd = Serial.read();
       
    switch(cmd) {
      case CMD_CLEAR_SCREEN:
        commandHandler.handleClearScreen();
        break;
        
      case CMD_WRITE_TEXT:
        commandHandler.handleWriteText();
        break;

      case CMD_SCROLL_UP:
        commandHandler.handleScrollUp();
        break;
         
      default:
        // Unknown command - flush and respond
        while(Serial.available()) {
          Serial.read();
        }
        Serial.write(0xFF);
        return;  // Exit early, don't send ready signal for unknown commands
    }
    
    // Flush any leftover bytes
    while(Serial.available()) {
      Serial.read();
    }
    
    // Send completion markers
    Serial.write(CMD_COMPLETITION_MARKER);
    Serial.write(CMD_COMPLETITION_MARKER);
    
    // IMPORTANT: Send ready signal AFTER display is done
    Serial.write(CMD_READY_FOR_NEXT_COMMAND);  // Ready for next command
  }
}

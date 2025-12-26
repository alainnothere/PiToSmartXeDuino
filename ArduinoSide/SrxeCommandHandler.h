#ifndef SrxeCommandHandler_h
#define SrxeCommandHandler_h
#include <Arduino.h>
#include "SmartResponseXEmt.h"
#include "SerialHelpers.h"
#include "SrxeKeyboard.h"
#include "SerialConfig.h"

SrxeKeyboard keyboard;

class SrxeCommandHandler {
private:
  uint16_t screenVerticalSize = 136;
  byte lastKey = 0;

  static const uint16_t arraySize = 544;
  byte arr[arraySize];
  
public:
  SrxeCommandHandler() {}

  void handleClearScreen() {
    SRXEScrollReset(); 
    SRXEScrollArea(0,136,24); 
    pixelsScrolled = 0;
    SRXEFill(0);
  }

  void handleReadKeyboard() {
    keyboard.readKeyboard();
  } 


  /*
   * printBlock() - Draw pre-encoded pixel data to screen
   * 
   * Parameters:
   *   data: Pre-encoded pixel data in "3 pixels in 2 bytes" format
   *   width: Width in pixels
   *   height: Height in pixels
   *   x: X position on screen in pixels
   *   y: Y position on screen in pixels
   * 
   * The data buffer size should be: (width ÷ 3 × 2) × height bytes
   */
   /* For the 30x30 black block, we need 30x30 pixels, then we need 2 bytes for 3 points, so we need
    * 30x30*(2/3), that means 600 bytes...
    * I'm sending from python
    * >H 60
    * >H 60
    * >B 30
    * >B 30
    * >B 0xFF <- data to print
    * >H 600  <- how many times
    * 
   */
  void printBlockRle() {
    uint16_t x = serialReadUint16();
    uint16_t y = serialReadUint16();

    sprintf(buffer, "printBlockRle x: %d, y: %d", x, y);
    sendDebugPacket(buffer);
    
    // Decompress RLE data
    uint16_t arrayPosition = 0;
    while (arrayPosition < arraySize) {
      uint8_t dataToPrint = serialReadUint8();      // Read the value
      uint16_t timesToPrintIt = serialReadUint16(); // Read the count

      // Check that we're not going to exceed the array size
      if (arrayPosition + timesToPrintIt > arraySize) {
        // If the count exceeds remaining space, trim it
        timesToPrintIt = arraySize - arrayPosition;
      }
      
      memset(arr + arrayPosition, dataToPrint, timesToPrintIt);
      arrayPosition += timesToPrintIt;
    }
   
    SRXESetPosition(x, y, 48, 34);
    SRXEWriteDataBlock(arr, arraySize);
  }   

  void printBlock() {
    uint16_t x = serialReadUint16();
    uint16_t y = serialReadUint16();

    sprintf(buffer, "printBlock x: %d, y: %d", x, y);
    sendDebugPacket(buffer);
    
    // Decompress RLE data
    uint16_t arrayPosition = 0;
    while (arrayPosition < arraySize) {
      uint8_t dataToPrint = serialReadUint8();      // Read the value
      //arr[arrayPosition] = dataToPrint;
      memset(arr + arrayPosition, dataToPrint, 1);
      arrayPosition += 1;
    }

    y = (y + pixelsScrolled) % screenVerticalSize;
    
    // Send to display (no header, just data)
    SRXESetPosition(x, y, 48, 34);
    SRXEWriteDataBlock(arr, arraySize);
  }   
  
  void handleWritePromptText() {
    uint8_t y = serialReadUint8();
    uint8_t font_size = serialReadUint8();
    uint8_t fg_color = serialReadUint8();
    uint8_t bg_color = serialReadUint8();
    uint8_t length = serialReadUint8();

    sprintf(buffer, "prompt y: %d,  fs: %d, fc: %d, bc: %d, l: %d,", y, font_size, fg_color, bg_color, length);
    sendDebugPacket(buffer,24);

	uint8_t number_of_prompt_chars_at_the_beginning = 5;
	buffer[0] = 'C';
	buffer[1] = 'M';
	buffer[2] = 'D';
	buffer[3] = '>';
	buffer[4] = ' ';

	for (uint8_t i = 0; i < length; i++) {
		char c = serialReadUint8();
		if (i < numberOfCharsToPossiblyReceive - 1 - number_of_prompt_chars_at_the_beginning) {
			buffer[i + number_of_prompt_chars_at_the_beginning] = c;
		}
	}

	// now I need to fill the rest until I fill all the remaining space with spaces
	for (uint8_t i = length + number_of_prompt_chars_at_the_beginning; i < numberOfCharsToPossiblyReceive; i++) {
		buffer[i] = ' ';
	}

	buffer[numberOfCharsToPossiblyReceive] = '\0';
	y = (y + pixelsScrolled) % screenVerticalSize;

    SRXEWriteString(0, y, buffer, font_size, fg_color, bg_color);

    keyboard.setFont(font_size);
    keyboard.clearInput();
  }

  void handleWriteText() {
    uint8_t y = serialReadUint8();
    uint8_t font_size = serialReadUint8();
    uint8_t fg_color = serialReadUint8();
    uint8_t bg_color = serialReadUint8();
    uint8_t length = serialReadUint8();

    sprintf(buffer, "write y: %d,  fs: %d, fc: %d, bc: %d, l: %d,", y, font_size, fg_color, bg_color, length);
    sendDebugPacket(buffer,24);

    // These are the constraints for the fonts.
    // the number of rows and the number of columns you can have with each one
    // as well as +number of pixels to be in the next row assuming you want the
    // rows one after another
    // 64, 17, 8 small
    // 52, 17, 8 normal
    // 42, 8, 16 medium
    // 35, 8, 16 large
    // Read all text characters
	for (uint16_t i = 0; i < length; i++) {
      while (!Serial.available());
      char c = Serial.read();
      if (i < numberOfCharsToPossiblyReceive - 1) {
    	  buffer[i] = c;
      }
    }

	// now I need to fill the rest until I fill all the remaining space with spaces
	for (uint8_t i = length; i < numberOfCharsToPossiblyReceive; i++) {
		buffer[i] = ' ';
	}

	buffer[numberOfCharsToPossiblyReceive] = '\0';

    y = (y + pixelsScrolled) % screenVerticalSize;
    SRXEWriteString(0, y, buffer, font_size, fg_color, bg_color);
    keyboard.setFont(font_size);
    keyboard.clearInput();
  }

  void handleScrollUp() {
    uint8_t pixels = serialReadUint8();

    pixelsScrolled = (pixelsScrolled + pixels) % screenVerticalSize;

    sprintf(buffer, "Ask to scroll %d pixels, scroll offset: %d", pixels, pixelsScrolled);
	sendDebugPacket(buffer);

    // Scroll the display up by the specified number of pixels
    SRXEScroll(pixels);
  }
};

#endif

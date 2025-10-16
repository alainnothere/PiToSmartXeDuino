#ifndef SrxeCommandHandler_h
#define SrxeCommandHandler_h
#include <Arduino.h>
#include "SmartResponseXEmt.h"
#include "SrxeSerialHelper.h"


#define DEBUG_START_MARKER   0xFA
#define DEBUG_END_MARKER     0xFB
#define DEBUG_MAX_CHUNK_SIZE 63

class SrxeCommandHandler {
private:
  uint16_t screenVerticalSize = 136;
  uint16_t pixelsScrolled = 0;

  // this maximum number of chars comes from writing all the chars
  // for one line using the smallest of the fonts + 1 for the end char
  static const uint8_t numberOfCharsToPossiblyReceive = 65;
  char textBuffer[numberOfCharsToPossiblyReceive];
  SrxeSerialHelper* serialHelper;
  
public:
  SrxeCommandHandler(SrxeSerialHelper* helper) : serialHelper(helper) {}

  void handleClearScreen() {
    pixelsScrolled = 0;
    SRXEScrollReset(); 
    SRXEScrollArea(0,136,24); 
    SRXEFill(0);
  }

  void sendDebugPacket(const char* message) {
    int len = strlen(message);
    int offset = 0;
    
    while (offset < len) {
      // Calculate how many bytes to send in this chunk
      int chunkSize = min(DEBUG_MAX_CHUNK_SIZE, len - offset);
      
      // Send start marker
      Serial.write(DEBUG_START_MARKER);
      
      // Send the chunk
      for (int i = 0; i < chunkSize; i++) {
        Serial.write(message[offset + i]);
      }
      
      // Send end marker
      Serial.write(DEBUG_END_MARKER);
      
      offset += chunkSize;
    }
  }

 
  void handleWriteText() {
    uint16_t x = serialHelper->readUint16();
    uint16_t y = serialHelper->readUint16();
    uint8_t font_size = serialHelper->readUint8();
    uint8_t fg_color = serialHelper->readUint8();
    uint8_t bg_color = serialHelper->readUint8();
    uint16_t length = serialHelper->readUint16();
    
    if (font_size > 3) font_size = 3;

    // These are the constraints for the fonts.
    // the number of rows and the number of columns you can have with each one
    // as well as +number of pixels to be in the next row assumming you want the
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
        textBuffer[i] = c;
      }
    }
    textBuffer[length] = '\0';
    
    // Small delay to let any straggler bytes arrive
    delay(10);
    
    // Flush any extra bytes
    while(Serial.available()) {
      Serial.read();
    }

    y = (y + pixelsScrolled) % screenVerticalSize;
    
    // Write to display - THIS IS THE SLOW PART
    SRXEWriteString(x, y, textBuffer, font_size, fg_color, bg_color);    

    sprintf(textBuffer, "x position: %d", x);
    sendDebugPacket(textBuffer);
    sprintf(textBuffer, "y position: %d", y);
    sendDebugPacket(textBuffer);
    sprintf(textBuffer, "pixelsScrolled position: %d", pixelsScrolled);
    sendDebugPacket(textBuffer);        
    Serial.write(0xFF);
  }

  void handleScrollUp() {
    
    uint16_t pixels = serialHelper->readUint16();
    sprintf(textBuffer, "Before pixelsScrolled: %d", pixelsScrolled);
    sendDebugPacket(textBuffer);        
    sprintf(textBuffer, "Before pixelsScrolled + scroll: %d", pixelsScrolled + pixels);
    sendDebugPacket(textBuffer); 
    
    if (pixelsScrolled + pixels >= screenVerticalSize) { 
      pixelsScrolled = (pixelsScrolled + pixels) % screenVerticalSize;
    }
    else {
      pixelsScrolled = pixelsScrolled + pixels;
    }

    sprintf(textBuffer, "After pixelsScrolled: %d", pixelsScrolled);
    sendDebugPacket(textBuffer);        
    sprintf(textBuffer, "After pixelsScrolled + scroll: %d", pixelsScrolled + pixels);
    sendDebugPacket(textBuffer);        
    Serial.write(0xFF);
    
    // Scroll the display up by the specified number of pixels
    SRXEScroll(pixels);
  }
};



#endif

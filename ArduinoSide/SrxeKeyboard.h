#ifndef SrxeKeyboard_h
#define SrxeKeyboard_h
#include <Arduino.h>
#include "SmartResponseXEmt.h"

#define KEY_START_MARKER     0xFD
#define KEY_END_MARKER       0xFE
#define KEY_MODIFIER_SHIFT   0x10
#define KEY_MODIFIER_SYM     0x11

// Keyboard maps from library (declare outside class)
extern byte OriginalKeys[];
extern byte ShiftedKeys[];
extern byte SymKeys[];

class SrxeKeyboard {
private:
  byte lastKey = 0;
  unsigned long lastKeyTime = 0;
  
  #define KEY_DEBOUNCE_MS 25  // 25ms debounce
  
  // ===== BAD KEYBOARD CONFIGURATION =====
  #define BAD_KEYBOARD true  // Set to false for hardware v2
  
  // List of keys that are broken/noisy on this keyboard
  static const byte badKeys[];
  static const int numBadKeys;
  
  bool isValidKey(byte key) {
    // Check if it's a bad key first
    if (isBadKey(key)) return false;
    
    // Only accept printable ASCII and known special keys
    if (key >= 32 && key <= 126) return true;  // Printable ASCII
    if (key == 0x09) return true;  // TAB
    if (key == 0x1B) return true;  // ESC
    if (key == 0x0A) return true;  // Enter/Line Feed
    if (key == 0x08) return true;  // Backspace/DEL
    if (key >= 0xE0 && key <= 0xE3) return true;  // Arrow keys
    if (key >= 0xF0 && key <= 0xF8) return true;  // Screen keys
    return false;
  }
 
  bool isBadKey(byte key) {
    if (!BAD_KEYBOARD) return false;
    
    for (int i = 0; i < numBadKeys; i++) {
      if (key == badKeys[i]) {
        return true;
      }
    }
    return false;
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
  
  bool shouldSendModifier(byte keyPosition, bool isShift, bool isSym) {
    /**
     * Determine if we should send a modifier packet before the key.
     * Returns true if the shift/sym mapping is "undefined" (same as original)
     */
    if (isShift) {
      // Check if ShiftedKeys differs from OriginalKeys
      byte originalKey = OriginalKeys[keyPosition];
      byte shiftedKey = ShiftedKeys[keyPosition];
      
      // If they're the same, shift is undefined for this key
      if (originalKey == shiftedKey && originalKey != 0) {
        return true;
      }
    }
    
    if (isSym) {
      // Check if SymKeys has a useful mapping
      byte originalKey = OriginalKeys[keyPosition];
      byte symKey = SymKeys[keyPosition];
      
      // If sym key is the same as original or is null, sym is undefined
      if ((symKey == originalKey || symKey == 0) && originalKey != 0) {
        return true;
      }
    }
    
    return false;
  }
  
public:
  void readKeyboard() {
    byte key = SRXEGetKey();
  
    if (key != 0 && isValidKey(key)) {
      // Check if this is a new key or enough time has passed
      if (key != lastKey || (millis() - lastKeyTime > KEY_DEBOUNCE_MS)) {
        
        // Get shift and sym state from keyboard scan
        byte *keyMap = SRXEGetKeyMap();
        bool shiftPressed = keyMap[0] & 0x08;
        bool symPressed = keyMap[0] & 0x10;
        
        // Find the key position in the keyboard map
        // Reverse-lookup which position generated this key
        int keyPosition = -1;
        for (int i = 0; i < 60; i++) {  // 6 rows × 10 cols = 60 positions
          if (OriginalKeys[i] == key ||
              (shiftPressed && ShiftedKeys[i] == key) ||
              (symPressed && SymKeys[i] == key)) {
            keyPosition = i;
            break;
          }
        }
        
        // Check if we should send modifier packet
        if (keyPosition >= 0) {
          if (shiftPressed && shouldSendModifier(keyPosition, true, false)) {
            // Send shift modifier packet first
            sendKeyPacket(KEY_MODIFIER_SHIFT);
            delay(5);  // Small delay between packets
          }
          else if (symPressed && shouldSendModifier(keyPosition, false, true)) {
            // Send sym modifier packet first
            sendKeyPacket(KEY_MODIFIER_SYM);
            delay(5);  // Small delay between packets
          }
        }
        
        // Send the actual key packet
        sendKeyPacket(key);
        
        lastKey = key;
        lastKeyTime = millis();
      }
    } else if (key == 0) {
      // No key pressed - allow next key press
      lastKey = 0;
    }
  }
};

// Define static members outside the class
const byte SrxeKeyboard::badKeys[] = {
  0x0A,  // Line Feed noise
  0xAA,  // Noise
  0xF8,  // Noise
  0xF7,  // Noise  
  0x98,  // Noise
  0x97,  // Noise
  0x96,  // Noise
  0xF6,  // Noise
  0xF3,  // Noise
  0xF0,  // Noise
  0xF1,  // Noise
};

const int SrxeKeyboard::numBadKeys = sizeof(badKeys) / sizeof(badKeys[0]);

#endif

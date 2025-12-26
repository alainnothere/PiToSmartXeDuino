/**
 * SrxeKeyboard.h - Keyboard handler with buffered input
 *
 * This class handles keyboard scanning and routes keys to the input buffer.
 * Instead of sending each keypress immediately, it buffers input locally
 * and only sends complete lines when Enter is pressed.
 *
 * The readKeyboard() method should be called frequently from the main loop.
 * It will:
 *   1. Scan for key presses
 *   2. Debounce keys
 *   3. Route keys to the input buffer
 *   4. Render the prompt line (with blinking cursor)
 *   5. When Enter is pressed, send the line and signal ready
 *
 * Special keys that are still sent immediately (not buffered):
 *   - Sym+0/1/2/3 (font change) - handled by Pi
 *   - Any other special keys defined in the future
 */

#ifndef SrxeKeyboard_h
#define SrxeKeyboard_h

#include <Arduino.h>
#include "SmartResponseXEmt.h"
#include "SerialConfig.h"
#include "SerialHelpers.h"
#include "SrxeInputBuffer.h"

// Keyboard maps from library (declare outside class)
extern byte OriginalKeys[];
extern byte ShiftedKeys[];
extern byte SymKeys[];

class SrxeKeyboard {
private:
    SrxeInputBuffer _inputBuffer;

    byte _lastKey = 0;
    unsigned long _lastKeyTime = 0;

    static const uint8_t KEY_DEBOUNCE_MS = 25;

    // ===== BAD KEYBOARD CONFIGURATION =====
    static const bool BAD_KEYBOARD = true;  // Set to false for hardware v2
    
    // List of keys that are broken/noisy on this keyboard
    static const byte badKeys[];
    static const int numBadKeys;
    
    bool isValidKey(byte key) {
        return true;  // Currently accepting all keys

        // Original validation (commented out for reference):
        // if (isBadKey(key)) return false;
        // if (key >= 32 && key <= 126) return true;  // Printable ASCII
        // if (key == 0x09) return true;  // TAB
        // if (key == 0x1B) return true;  // ESC
        // if (key == 0x0A) return true;  // Enter/Line Feed
        // if (key == 0x08) return true;  // Backspace/DEL
        // if (key >= 0xE0 && key <= 0xE3) return true;  // Arrow keys
        // if (key >= 0xF0 && key <= 0xA0) return true;  // Screen keys
        // return false;
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

    /**
     * Check if this key should be sent immediately (not buffered)
     * Returns true for special keys like Sym+0/1/2/3
     */
    bool shouldSendImmediately(byte key, bool symPressed, bool shiftPressed) {
        // Shift + 0/1/2/3 for font change - send immediately
        if (shiftPressed && (key == 0x30  || key == 0x31 || key == 0x32 || key == 0x33)) {
            return true;
        }

        // Sym + c for clear screen
        if (symPressed && (key == 0x63)) {
            return true;
        }

        // Add other special keys here as needed

        return false;
    }
    
    /**
     * Check if this key/combo represents something we handle on the arduino side
     * and should not be sent or used as input for the buffer, for example F0
     * shows the "status bar"
     */
    bool isSpecialFunctionOnArduinoSide(byte key, bool symPressed, bool shiftPressed) {

        // Add other special keys here as needed
        if (key == 0xF0 && !symPressed && !shiftPressed)
        {
        	enableShowStatusBar = !enableShowStatusBar;
            sprintf(buffer, "Status bar enabled: %d", enableShowStatusBar);
        	sendDebugPacket(buffer);
        	return true;
        }
        if (key == 0xF0 && symPressed && !shiftPressed)
        {
        	enableDebugToScreen = !enableDebugToScreen;
            sprintf(buffer, "Debug to screen enabled: %d", enableDebugToScreen);
        	sendDebugPacket(buffer);
        	return true;
        }
        if (key == 0xF0 && !symPressed && shiftPressed)
        {
        	enableDebugThroughSerial = !enableDebugThroughSerial;
            sprintf(buffer, "Debug to serial enabled: %d", enableDebugThroughSerial);
        	sendDebugPacket(buffer);
        	return true;
        }

        return false;
    }

    bool shouldSendModifier(byte keyPosition, bool isShift, bool isSym) {
        /**
         * Determine if we should send a modifier packet before the key.
         * Returns true if the shift/sym mapping is "undefined" (same as original)
         */
        if (isShift) {
            byte originalKey = OriginalKeys[keyPosition];
            byte shiftedKey = ShiftedKeys[keyPosition];

            if (originalKey == shiftedKey && originalKey != 0) {
                return true;
            }
        }

        if (isSym) {
            byte originalKey = OriginalKeys[keyPosition];
            byte symKey = SymKeys[keyPosition];

            if ((symKey == originalKey || symKey == 0) && originalKey != 0) {
                return true;
            }
        }

        return false;
    }
    
    /**
     * Find key position in keyboard map (for modifier detection)
     */
    int findKeyPosition(byte key, bool shiftPressed, bool symPressed) {
        for (int i = 0; i < 60; i++) {
            if (OriginalKeys[i] == key ||
                (shiftPressed && ShiftedKeys[i] == key) ||
                (symPressed && SymKeys[i] == key)) {
                return i;
            }
        }
        return -1;
    }

public:
    SrxeKeyboard() {}

    /**
     * Initialize with a specific font
     */
    void init(uint8_t fontId) {
        _inputBuffer.init(fontId);
    }

    /**
     * Set the current font for the input buffer
     */
    void setFont(uint8_t fontId) {
        _inputBuffer.setFont(fontId);
    }

    /**
     * Main keyboard reading function
     * Call this frequently from the main loop
     *
     * Returns true if a complete line was sent (Enter pressed)
     */
    bool readKeyboard() {
        // Always render the prompt (handles cursor blinking)
        _inputBuffer.render();

        byte key = SRXEGetKey();
        
        if (key != 0 && isValidKey(key)) {
            // Check debounce
            if (key != _lastKey || (millis() - _lastKeyTime > KEY_DEBOUNCE_MS)) {

                // Get modifier state
                byte *keyMap = SRXEGetKeyMap();
                bool shiftPressed = keyMap[0] & 0x08;
                bool symPressed = keyMap[0] & 0x10;

                // Debug output
                sprintf(buffer, "Key:0x%02X Sh:%d Sym:%d", key, shiftPressed, symPressed);
                sendDebugPacket(buffer);

                // Update status bar variable
                lastKeyPressed = key;

                // Check if this key should bypass the buffer
                if (shouldSendImmediately(key, symPressed, shiftPressed)) {
//                    // Find key position for modifier check
//                    int keyPosition = findKeyPosition(key, shiftPressed, symPressed);
//
//                    if (keyPosition >= 0) {
//                        if (shiftPressed && shouldSendModifier(keyPosition, true, false)) {
//                            sendKeyPacket(KEY_MODIFIER_SHIFT);
//                        }
//                        else if (symPressed && shouldSendModifier(keyPosition, false, true)) {
//                            sendKeyPacket(KEY_MODIFIER_SYM);
//                        }
//                    }
					if (shiftPressed) {
						sendKeyPacket(KEY_MODIFIER_SHIFT);
					}
					else if (symPressed) {
						sendKeyPacket(KEY_MODIFIER_SYM);
					}

                    sendKeyPacket(key);
                }
                else if (isSpecialFunctionOnArduinoSide(key, symPressed, shiftPressed))
                {

                }
                else {
                    // Route to input buffer
                	bool enterPressed = _inputBuffer.handleKey(key, shiftPressed);

                    if (enterPressed) {
                        // Send the complete line
                        _inputBuffer.sendLine();

                        // Clear buffer for next input
                        //_inputBuffer.clear();

                        // Update tracking
                        _lastKey = key;
                        _lastKeyTime = millis();

                        return true;  // Signal that line was sent
                    }
                }

                _lastKey = key;
                _lastKeyTime = millis();
            }
        } else {
            _lastKey = 0;
        }
        
        return false;
    }

    /**
     * Get access to the input buffer (for external control if needed)
     */
    SrxeInputBuffer& getInputBuffer() {
        return _inputBuffer;
    }

    /**
     * Clear the input buffer
     */
    void clearInput() {
        _inputBuffer.clear();
    }
};

// Define static members outside the class
// THIS IS NEEDED IF YOU ARE USING THE HARDWARE SERIAL ON THE ARDUINO AND THE
// KEYBOARD IS STILL TIED TO THE SERIAL PORT WITH THE RESISTORS, IN THAT CASE
// YOU HAVE TO USE THE TDO AND TDI FOR READING TRICK
const byte SrxeKeyboard::badKeys[] = {
    0x0A,  // Line Feed noise
    0xAA,  // Noise
    0x98,  // Noise
    0x97,  // Noise
    0x96,  // Noise
    0x04,  // Noise
    0x1E,  // Noise
};

const int SrxeKeyboard::numBadKeys = sizeof(badKeys) / sizeof(badKeys[0]);

#endif

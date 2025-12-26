/**
 * "please document what you do with all this info so in the future some
 *  poor soul that decides to work on this have this info"
 *
 * SrxeInputBuffer.h - Buffered keyboard input with local echo
 *
 * This class handles keyboard input buffering for the SmartXE terminal.
 * Instead of sending each keypress immediately to the Pi, it buffers
 * up to 128 characters locally, displays them with a blinking cursor,
 * and only sends the complete line when Enter is pressed.
 *
 * This reduces round-trips significantly:
 * - Old: Each keypress = 1 round trip (type "hello" = 5 round trips)
 * - New: Entire line = 1 round trip (type "hello" + Enter = 1 round trip)
 *
 * ============================================================================
 * FONT CONFIGURATION (from Pi side python code):
 * ============================================================================
 *
 * # Font configuration: [font_id, cols, rows_visible, pixels_per_row, padding to add to be in the last line]
 * fontConfiguration = [
 *     # font id
 *     #   cols   pixel per row
 *     #       rows   padding
 *     #
 *     [0, 52, 17, 8, 0],  # FONT_NORMAL
 *     [1, 64, 17, 8, 0],  # FONT_SMALL
 *     [2, 32, 8, 17, 0],  # FONT_MEDIUM
 *     [3, 25, 8, 17, 0]   # FONT_LARGE
 * ]
 *
 * Prompt Y position formula (from Pi):
 *   y = rows_visible * pixels_per_row + padding - pixels_per_row
 *
 *
 * ============================================================================
 * KEY MAPPINGS:
 * ============================================================================
 * 0x08 = Enter (Del key repurposed) - sends buffer to Pi
 * 0x7F = Backspace (Shift+Del) - deletes char before cursor
 * 0xE3 = Left arrow - move cursor left
 * 0xE2 = Right arrow - move cursor right
 * 0x20-0x7E = Printable ASCII - inserted at cursor position
 *
 * ============================================================================
 * DISPLAY LOGIC:
 * ============================================================================
 * The prompt line shows "CMD> " followed by user input and a blinking cursor.
 *
 * When input is short (fits on screen):
 *   │CMD> hello world█                    │
 *
 * When input extends LEFT of visible area (user scrolled right):
 *   │CMD><< more text here█               │
 *
 * When input extends RIGHT of visible area (cursor not at end):
 *   │CMD> start of long text>>            │
 *
 * When input extends BOTH directions:
 *   │CMD><< middle of text>>              │
 *
 * ============================================================================
 * PROTOCOL:
 * ============================================================================
 * When Enter is pressed, sends:
 *   [LINE_START_MARKER][LENGTH][...data...][CHECKSUM][LINE_END_MARKER]
 *
 * Where CHECKSUM = LINE_START_MARKER ^ LENGTH ^ (XOR of all data bytes)
 *
 */

#ifndef SrxeInputBuffer_h
#define SrxeInputBuffer_h

#include <Arduino.h>
#include "SmartResponseXEmt.h"
#include "SerialConfig.h"
#include "SerialHelpers.h"

// Protocol markers for line input (different from single key markers)
#define LINE_START_MARKER    0xF8
#define LINE_END_MARKER      0xF9

// Key codes
#define KEY_ENTER       0x08  // Del key repurposed as Enter
#define KEY_BACKSPACE   0x7F  // Shift+Del
#define KEY_LEFT        0xE3
#define KEY_RIGHT       0xE2

// Font configuration table
// Index: font_id, Values: {cols, rows_visible, pixels_per_row, padding}
// This mirrors the Python fontConfiguration array
static const uint8_t fontConfig[4][4] = {
    {52, 17, 8, 0},   // FONT_NORMAL (id 0)
    {64, 17, 8, 0},   // FONT_SMALL (id 1)
    {32, 8, 17, 0},   // FONT_MEDIUM (id 2)
    {25, 8, 17, 0}    // FONT_LARGE (id 3)
};

class SrxeInputBuffer {
private:
    static const uint8_t MAX_INPUT = 128;
    static const uint8_t PROMPT_WIDTH = 5;  // "CMD> "
    static const uint16_t BLINK_INTERVAL_MS = 500;

    char _buffer[MAX_INPUT + 1];  // +1 for null terminator
    uint8_t _length;              // Number of chars in buffer
    uint8_t _cursorPos;           // Cursor position (0 to _length)
    uint8_t _viewOffset;          // First visible char index (for scrolling)
    uint8_t _fontId;              // Current font (0-3)

    // Cursor blinking state
    bool _cursorVisible;
    unsigned long _lastBlinkTime;

    /**
     * Get number of columns for current font
     */
    uint8_t getCols() {
        if (_fontId > 3) _fontId = 0;
        return fontConfig[_fontId][0];
    }

    /**
     * Get Y position for prompt line (last visible line)
     * Formula: y = rows_visible * pixels_per_row + padding - pixels_per_row
     * Then adjust for scroll offset
     */
    uint8_t getYPosition() {
        if (_fontId > 3) _fontId = 0;
        uint8_t rows = fontConfig[_fontId][1];
        uint8_t pixelsPerRow = fontConfig[_fontId][2];
        uint8_t padding = fontConfig[_fontId][3];

        uint8_t y = (rows * pixelsPerRow) + padding - pixelsPerRow;

        // Adjust for scroll (same as other handlers)
        y = (y + pixelsScrolled) % 136;  // 136 = screen vertical size

        return y;
    }

    /**
     * Calculate usable character width (accounting for prompt and indicators)
     */
    uint8_t getUsableWidth() {
        uint8_t cols = getCols();
        // Always reserve space for prompt
        // May also need space for << or >> indicators
        return cols - PROMPT_WIDTH;
    }

    /**
     * Adjust view offset to keep cursor visible
     */
    void adjustViewOffset() {
        uint8_t usable = getUsableWidth();

        // Account for << indicator taking 2 chars if we're scrolled
        uint8_t visibleChars = usable;
        if (_viewOffset > 0) {
            visibleChars -= 2;  // << takes 2 chars
        }

        // If cursor is before view, scroll left
        if (_cursorPos < _viewOffset) {
            _viewOffset = _cursorPos;
        }

        // If cursor is after visible area, scroll right
        if (_cursorPos > _viewOffset + visibleChars) {
            _viewOffset = _cursorPos - visibleChars;
        }
    }

    /**
     * Calculate checksum for the buffer
     * CHECKSUM = LINE_START_MARKER ^ LENGTH ^ (XOR of all data bytes)
     */
    uint8_t calculateChecksum() {
        uint8_t checksum = LINE_START_MARKER ^ _length;
        for (uint8_t i = 0; i < _length; i++) {
            checksum ^= _buffer[i];
        }
        return checksum;
    }

public:
    SrxeInputBuffer() {
        clear();
        _fontId = 0;  // Default to FONT_NORMAL
    }

    /**
     * Initialize with a specific font
     */
    void init(uint8_t fontId) {
        _fontId = fontId;
        clear();
    }

    /**
     * Set the current font
     */
    void setFont(uint8_t fontId) {
        if (fontId <= 3) {
            _fontId = fontId;
            adjustViewOffset();  // Recalculate view since width changed
        }
    }

    /**
     * Get current font ID
     */
    uint8_t getFont() {
        return _fontId;
    }

    /**
     * Clear the buffer and reset state
     */
    void clear() {
        _length = 0;
        _cursorPos = 0;
        _viewOffset = 0;
        _buffer[0] = '\0';
        _cursorVisible = true;
        _lastBlinkTime = millis();
    }

    /**
     * Handle a key press
     * Returns true if Enter was pressed (line ready to send)
     */
    bool handleKey(byte key, bool shiftPressed) {
        // Reset cursor blink on any keypress
        _cursorVisible = true;
        _lastBlinkTime = millis();

        if (key == KEY_ENTER && !shiftPressed) {
            return true;  // Signal that line is ready
        }
        else if (key == KEY_ENTER && shiftPressed) {
            // Shift+Del = Backspace
            if (_cursorPos > 0) {
                for (uint8_t i = _cursorPos - 1; i < _length - 1; i++) {
                    _buffer[i] = _buffer[i + 1];
                }
                _length--;
                _cursorPos--;
                _buffer[_length] = '\0';
                adjustViewOffset();
            }
        }
        else if (key == KEY_BACKSPACE) {
            // Keep this for 0x7F if it ever gets used
            // ... existing backspace code ...
        }
        else if (key == KEY_LEFT) {
            if (_cursorPos > 0) {
                _cursorPos--;
                adjustViewOffset();
            }
        }
        else if (key == KEY_RIGHT) {
            if (_cursorPos < _length) {
                _cursorPos++;
                adjustViewOffset();
            }
        }
        else if (key >= 0x20 && key <= 0x7E) {
            // Printable ASCII
            if (_length < MAX_INPUT) {
                // Shift everything after cursor right by one
                for (uint8_t i = _length; i > _cursorPos; i--) {
                    _buffer[i] = _buffer[i - 1];
                }
                _buffer[_cursorPos] = (char)key;
                _length++;
                _cursorPos++;
                _buffer[_length] = '\0';
                adjustViewOffset();
            }
        }

        return false;
    }

    /**
     * Render the prompt line to screen
     * Call this regularly to update cursor blink
     */
    void render() {
        // Update cursor blink
        if (millis() - _lastBlinkTime >= BLINK_INTERVAL_MS) {
            _cursorVisible = !_cursorVisible;
            _lastBlinkTime = millis();
        }

        uint8_t cols = getCols();
        uint8_t y = getYPosition();

        // Build the display line
        char displayLine[65];  // Max 64 chars + null (FONT_SMALL is widest at 64)
        memset(displayLine, ' ', cols);
        displayLine[cols] = '\0';

        // Start with prompt
        displayLine[0] = 'C';
        displayLine[1] = 'M';
        displayLine[2] = 'D';
        displayLine[3] = '>';
        displayLine[4] = ' ';

        uint8_t writePos = PROMPT_WIDTH;
        uint8_t charsAvailable = cols - PROMPT_WIDTH;

        // Check if we need << indicator (content to the left)
        bool hasLeftOverflow = (_viewOffset > 0);
        bool hasRightOverflow = false;

        if (hasLeftOverflow) {
            displayLine[writePos++] = '<';
            displayLine[writePos++] = '<';
            charsAvailable -= 2;
        }

        // Calculate how many chars we can show
        uint8_t charsToShow = _length - _viewOffset;
        if (charsToShow > charsAvailable - 2) {  // -2 for potential >> or cursor
            charsToShow = charsAvailable - 2;
            hasRightOverflow = (_viewOffset + charsToShow < _length);
        }

        // Copy visible portion of buffer
        for (uint8_t i = 0; i < charsToShow && (writePos < cols - 2); i++) {
            uint8_t bufIdx = _viewOffset + i;
            if (bufIdx < _length) {
                // Check if this is cursor position
                if (bufIdx == _cursorPos && _cursorVisible) {
                    // Show cursor as block (inverse would be better but using █ char)
                    displayLine[writePos++] = 0xDB;  // Block character, or use '_'
                } else {
                    displayLine[writePos++] = _buffer[bufIdx];
                }
            }
        }

        // If cursor is at end of buffer
        if (_cursorPos == _length && _cursorVisible) {
            if (writePos < cols - (hasRightOverflow ? 2 : 0)) {
                displayLine[writePos++] = '_';  // Cursor at end
            }
        }

        // Add >> indicator if content extends right
        if (hasRightOverflow) {
            // Place >> at end
            displayLine[cols - 2] = '>';
            displayLine[cols - 1] = '>';
        }

        // Ensure null termination
        displayLine[cols] = '\0';

        // Write to screen
        SRXEWriteString(0, y, displayLine, _fontId, 3, 0);
    }

    /**
     * Send the buffered line to Pi
     * Format: [LINE_START_MARKER][LENGTH][...data...][CHECKSUM][LINE_END_MARKER]
     */
    void sendLine() {
        Serial.write(LINE_START_MARKER);
        Serial.write(_length);

        for (uint8_t i = 0; i < _length; i++) {
            Serial.write(_buffer[i]);
        }

        Serial.write(calculateChecksum());
        Serial.write(LINE_END_MARKER);

#ifdef USING_SOFTWARE_SERIAL
        Serial.update();
#endif
    }

    /**
     * Get the current buffer contents (null-terminated)
     */
    const char* getBuffer() {
        return _buffer;
    }

    /**
     * Get the current buffer length
     */
    uint8_t getLength() {
        return _length;
    }
};

#endif

# Communication Protocol Specification

## Overview

The PiToSmartXeDuino protocol is a bidirectional packet-based serial communication system running at 19,200 baud. The protocol uses simple packet structures with checksums for reliability.

**Communication Medium:**
- Software serial (bit-banged) on JTAG pins on the arduino side to avoid opening the case, on the pi the hardware UART is used.
- Baud rate: 19,200
- Format: 8N1 (8 data bits, no parity, 1 stop bit)
- TDO it's used to let the pi know that it can send data as the arduino needs to disable interruptions and focus on just that to keep the speed as high as possible

---

## Physical Layer

### Pin Configuration

| Function | XE Pin | Pi BCM GPIO | Direction |
|----------|--------|---------|-----------|
| Serial TX (Pi → XE) | TMS | GPIO 14 | Pi → XE |
| Serial RX (Pi ← XE) | TCK | GPIO 15 | Pi ← XE |
| Signal/Ready | TDO | GPIO 27 | Pi ← XE |

### Soft/Hard Serial Implementation

**Pi Side: hardware UART**
```python
# Using hardware UART mapped to GPIO 14/15
serial_port = "/dev/ttyAMA0"

# Signal pin for the pi to send data
SIGNAL_PIN_NUMBER_ON_GPIO_NUMBERING = 27
```

**Arduino Side: software, bit bang**
```cpp
// Timer-based bit-banging
#define BAUD_RATE 19200
#define BIT_TICKS ((F_CPU / 8) / BAUD_RATE)  // Timer1 ticks per bit

// Signal pin goes LOW when Arduino ready to receive
SIG_LOW();   // Ready
SIG_HIGH();  // Busy
```

### Handshaking Protocol

**Purpose:** Prevent buffer overruns in soft serial implementation.

**Flow:**
```
Arduino:                    Pi:
───────                     ───

[Ready to receive]
SIG_LOW() ───────────────→ [Detects LOW signal]
                           [Writes data to serial]
[Receiving byte...]        
                           [Waits for completion]
[Byte received]
SIG_HIGH() ──────────────→ [Ready signal released]

[Processing command...]
[Sends READY packet]
0xFC ─────────────────────→ [Receives READY]
                           [Can send next command]
```

**Timing:**
```python
# Pi waits up to 100ms for signal pin to go LOW
TIMEOUT_WAITING_FOR_SIGNAL_TO_TRANSFER = 100 / 1000  # 100ms

# Pi waits up to 1000ms for READY packet
timeout = 1.0  # seconds
```

---

## Protocol Markers

### Command Markers (Pi → Arduino)

```python
CMD_WRITE_TEXT = 0x02      # Write text to screen
CMD_SCROLL_UP = 0x03       # Scroll screen up by N pixels
CMD_PRINT_BLOCK_RLE = 0x04 # Print RLE-encoded block (future/unused)
CMD_PRINT_BLOCK = 0x05     # Print raw block (future/unused)
CMD_CLEAR_SCREEN = 0x06    # Clear the screen
CMD_PRINT_PROMPT = 0x07    # Print the command prompt line
CMD_PRINT_BATCH = 0x08     # Batch screen update (future/unused)

CMD_PADDING_MARKER = 0xFF  # Padding/no-op byte
```

### Response Markers (Arduino → Pi)

```python
CMD_READY_FOR_NEXT_COMMAND = 0xFC  # Arduino ready for next command
```

### Debug Packet Markers (Arduino → Pi)

```python
DEBUG_START_MARKER = 0xFA  # Start of debug message
DEBUG_END_MARKER = 0xFB    # End of debug message
```

### Keyboard Packet Markers (Arduino → Pi)

```python
# Single key packet
KEY_START_MARKER = 0xFD
KEY_END_MARKER = 0xFE

# Key modifiers (sent before key in separate packet)
KEY_MODIFIER_SHIFT = 0x10
KEY_MODIFIER_SYM = 0x11

# Line input packet (buffered input)
LINE_START_MARKER = 0xF8
LINE_END_MARKER = 0xF9
```

---

## Packet Formats

### 1. READY Signal (Arduino → Pi)

**Format:**
```
[0xFC]
```

**Purpose:** Signals that Arduino has completed processing the previous command and is ready for the next one.

**When Sent:**
- After completing CMD_WRITE_TEXT
- After completing CMD_SCROLL_UP
- After completing CMD_CLEAR_SCREEN
- After completing CMD_PRINT_PROMPT
- After any other screen operation

**Example:**
```
Hex:  FC
```

**Python Reception:**
```python
packet = self.read_packet()
if packet['type'] == 'ready':
    # Can send next command
```

---

### 2. Single Key Packet (Arduino → Pi)

**Format:**
```
[KEY_START] [KEY] [CHECKSUM] [KEY_END]
 0xFD       byte   byte       0xFE
```

**Checksum Calculation:**
```
CHECKSUM = KEY_START ^ KEY
         = 0xFD ^ KEY
```

**Purpose:** Send individual keypresses (used for special keys and modifier combinations).

**When Sent:**
- Special key combinations (Shift+0/1/2/3, Sym+C, etc.)
- Any key that should bypass line buffering

**Example - Shift+1 (font change):**
```
Packet 1 (Modifier):
  Hex:  FD 10 ED FE
        │  │  │  └─ KEY_END
        │  │  └──── CHECKSUM (0xFD ^ 0x10 = 0xED)
        │  └─────── KEY_MODIFIER_SHIFT
        └────────── KEY_START

Packet 2 (Key):
  Hex:  FD 31 CC FE
        │  │  │  └─ KEY_END
        │  │  └──── CHECKSUM (0xFD ^ 0x31 = 0xCC)
        │  └─────── '1' (0x31)
        └────────── KEY_START
```

**Python Reception:**
```python
packet1 = {'type': 'key', 'key': 0x10}  # Shift modifier
packet2 = {'type': 'key', 'key': 0x31}  # '1' key
# KeyboardHandler combines these → {'action': 'font_change', 'font': 1}
```

---

### 3. Line Input Packet (Arduino → Pi)

**Format:**
```
[LINE_START] [LENGTH] [DATA...] [CHECKSUM] [LINE_END]
 0xF8        byte     N bytes    byte       0xF9
```

**Checksum Calculation:**
```
CHECKSUM = LINE_START ^ LENGTH ^ (XOR of all DATA bytes)

Example:
  LINE_START = 0xF8
  LENGTH = 5
  DATA = "hello" = 0x68 0x65 0x6C 0x6C 0x6F
  
  CHECKSUM = 0xF8 ^ 0x05 ^ 0x68 ^ 0x65 ^ 0x6C ^ 0x6C ^ 0x6F
           = 0x1A
```

**Purpose:** Send a complete command line after user presses Enter.

**When Sent:**
- User presses Enter (0x08 key, repurposed from Del)
- After local buffering and editing on Arduino

**Example - User types "ls" and presses Enter:**
```
Hex:  F8 02 6C 73 8A F9
      │  │  │  │  │  └─ LINE_END
      │  │  │  │  └──── CHECKSUM (0xF8 ^ 0x02 ^ 0x6C ^ 0x73 = 0x8A)
      │  │  │  └─────── 's' (0x73)
      │  │  └────────── 'l' (0x6C)
      │  └───────────── LENGTH = 2
      └──────────────── LINE_START

Packet as bytes: [248, 2, 108, 115, 138, 249]
```

**Python Reception:**
```python
packet = {'type': 'line', 'data': 'ls'}
# Main loop receives: {'type': 'command', 'value': 'ls'}
```

**Advantages over single-key packets:**
- Reduces serial traffic (1 packet vs N packets for N characters)
- Allows local editing (cursor movement, backspace)
- Shows immediate feedback on XE screen
- Faster command entry

---

### 4. Debug Packet (Arduino → Pi)

**Format:**
```
[DEBUG_START] [DATA...] [DEBUG_END]
 0xFA         N bytes    0xFB
```

**No Checksum:** Debug packets are informational only.

**Purpose:** Send debug messages from Arduino for development/troubleshooting.

**When Sent:**
- After processing commands (if debug enabled)
- On errors
- On state changes

**Example:**
```
Message: "Ask to scroll 16 pixels, scroll offset: 24"

Hex:  FA 41 73 6B 20 74 6F ... 32 34 FB
      │  └─────────────────────────┘  │
      │  ASCII string                 │
      DEBUG_START                 DEBUG_END
```

**Python Reception:**
```python
packet = {'type': 'debug', 'message': 'Ask to scroll 16 pixels, scroll offset: 24'}
# Logged to console or screen depending on settings
```

**Arduino Configuration:**
```cpp
bool enableDebugThroughSerial = true;  // Send to serial
bool enableDebugToScreen = true;       // Also show on screen
```

---

### 5. Clear Screen Command (Pi → Arduino)

**Format:**
```
[CMD_CLEAR_SCREEN]
 0x06
```

**Purpose:** Clear the screen and reset scroll offset.

**Arduino Action:**
```cpp
void handleClearScreen() {
    SRXEScrollReset();       // Reset scroll register to 0
    SRXEScrollArea(0,136,24); // Set scroll area
    pixelsScrolled = 0;       // Reset offset tracker
    SRXEFill(0);             // Fill screen with black (0x00)
}
```

**Sends READY when complete.**

**Example:**
```
Pi sends:
  Hex:  06

Arduino:
  [Clears screen]
  [Sends READY]
  Hex:  FC
```

---

### 6. Scroll Up Command (Pi → Arduino)

**Format:**
```
[CMD_SCROLL_UP] [PIXELS]
 0x03           byte (0-255)
```

**Purpose:** Scroll screen content up by N pixels using hardware scroll register.

**Arduino Action:**
```cpp
void handleScrollUp() {
    uint8_t pixels = serialReadUint8();
    
    // Accumulate scroll offset (wraps at 136)
    pixelsScrolled = (pixelsScrolled + pixels) % screenVerticalSize;
    
    // Update hardware scroll register
    SRXEScroll(pixels);
}
```

**Sends READY when complete.**

**Example - Scroll up 16 pixels (2 rows in font 0):**
```
Pi sends:
  Hex:  03 10
        │  └─ 16 pixels
        └──── CMD_SCROLL_UP

Arduino:
  [Updates scroll register]
  pixelsScrolled: 24 → 40
  [Sends READY]
  Hex:  FC
```

**Visual Effect:**
```
Before (pixelsScrolled = 24):
┌────────────┐
│ Line 1     │ ← Physical row 0 shows buffer row 3
│ Line 2     │
│ Line 3     │
│ ...        │
│ CMD>       │
└────────────┘

After (pixelsScrolled = 40, scrolled +16):
┌────────────┐
│ Line 3     │ ← Physical row 0 now shows buffer row 5
│ Line 4     │
│ Line 5     │
│ ...        │
│ CMD>       │
└────────────┘
```

---

### 7. Write Text Command (Pi → Arduino)

**Format:**
```
[CMD_WRITE_TEXT] [Y] [FONT] [FG] [BG] [LENGTH] [TEXT...]
 0x02            byte byte   byte byte byte     N bytes
```

**Fields:**
- **Y:** Y position in pixels (0-135)
- **FONT:** Font ID (0-3)
- **FG:** Foreground color (0-3 for grayscale)
- **BG:** Background color (0-3 for grayscale)
- **LENGTH:** Number of text bytes to follow
- **TEXT:** ASCII characters (up to LENGTH bytes)

**Arduino Action:**
```cpp
void handleWriteText() {
    uint8_t y = serialReadUint8();
    uint8_t font_size = serialReadUint8();
    uint8_t fg_color = serialReadUint8();
    uint8_t bg_color = serialReadUint8();
    uint8_t length = serialReadUint8();
    
    // Read text characters
    for (uint16_t i = 0; i < length; i++) {
        buffer[i] = Serial.read();
    }
    
    // Pad to full width with spaces
    for (uint8_t i = length; i < numberOfCharsToPossiblyReceive; i++) {
        buffer[i] = ' ';
    }
    buffer[numberOfCharsToPossiblyReceive] = '\0';
    
    // Adjust Y for scroll offset
    y = (y + pixelsScrolled) % screenVerticalSize;
    
    // Render to screen
    SRXEWriteString(0, y, buffer, font_size, fg_color, bg_color);
}
```

**Sends READY when complete.**

**Example - Write "/bin/bash: line 1: a: command not found" at y=120:**
```
Pi sends:
  Hex:  02 78 00 03 00 27 2F 62 69 6E 2F 62 61 73 68 ...
        │  │  │  │  │  │  └──────────────────────────────
        │  │  │  │  │  │  Text: "/bin/bash: line 1: a..."
        │  │  │  │  │  └───── LENGTH = 39 (0x27)
        │  │  │  │  └──────── BG = 0 (black)
        │  │  │  └─────────── FG = 3 (white)
        │  │  └────────────── FONT = 0 (normal)
        │  └───────────────── Y = 120 (0x78)
        └──────────────────── CMD_WRITE_TEXT

Arduino:
  [Renders text to screen]
  Actual Y = (120 + 24) % 136 = 144 % 136 = 8
  [Sends READY]
  Hex:  FC
```

**Color Values:**
```cpp
0x00 = BLACK       (0b00 for 2-bit pixel)
0x49 = DARK_GRAY   (0b01 for 2-bit pixel)
0x92 = LIGHT_GRAY  (0b10 for 2-bit pixel)
0xFF = WHITE       (0b11 for 2-bit pixel)
```

---

### 8. Print Prompt Command (Pi → Arduino)

**Format:**
```
[CMD_PRINT_PROMPT] [Y] [FONT] [FG] [BG] [LENGTH] [TEXT...]
 0x07              byte byte   byte byte byte     N bytes
```

**Same format as CMD_WRITE_TEXT, but:**
- Arduino automatically prepends "CMD> " to the text
- Used specifically for the prompt line

**Arduino Action:**
```cpp
void handleWritePromptText() {
    uint8_t y = serialReadUint8();
    uint8_t font_size = serialReadUint8();
    uint8_t fg_color = serialReadUint8();
    uint8_t bg_color = serialReadUint8();
    uint8_t length = serialReadUint8();
    
    // Prepend "CMD> "
    buffer[0] = 'C';
    buffer[1] = 'M';
    buffer[2] = 'D';
    buffer[3] = '>';
    buffer[4] = ' ';
    
    // Read user input after prompt
    for (uint8_t i = 0; i < length; i++) {
        buffer[i + 5] = serialReadUint8();
    }
    
    // Pad rest with spaces
    for (uint8_t i = length + 5; i < numberOfCharsToPossiblyReceive; i++) {
        buffer[i] = ' ';
    }
    
    y = (y + pixelsScrolled) % screenVerticalSize;
    SRXEWriteString(0, y, buffer, font_size, fg_color, bg_color);
    
    // Clear input buffer (ready for next command)
    keyboard.clearInput();
}
```

**Sends READY when complete.**

**Example - Update prompt with empty text (user hasn't typed yet):**
```
Pi sends:
  Hex:  07 80 00 03 00 00
        │  │  │  │  │  └─ LENGTH = 0 (no user input yet)
        │  │  │  │  └──── BG = 0
        │  │  │  └─────── FG = 3
        │  │  └────────── FONT = 0
        │  └───────────── Y = 128 (0x80)
        └──────────────── CMD_PRINT_PROMPT

Arduino:
  Renders: "CMD>  " (with spaces to clear old input)
  [Sends READY]
  Hex:  FC
```

---

## Screen Encoding (Future/Advanced)

### The "3 Pixels in 2 Bytes" Format

The SMART Response XE display uses 2-bit grayscale (4 colors: black, dark gray, light gray, white). The encoding packs pixels in a special way:

**Encoding Layout:**

```
BYTE 0:  [PPP][PPP][PP]
         |1st||2nd||3rd(partial)|

BYTE 1:  [XXXXXX][XX]
         |unused||3rd(rest)|
```

**Example - Three WHITE pixels:**

WHITE = 0b11 (binary) = 3 (decimal)

```
Pixel 0 (first):  Uses bits 7-5 of byte 0  → 0xE0 = 0b11100000
Pixel 1 (second): Uses bits 4-2 of byte 0  → 0x1C = 0b00011100
Pixel 2 (third):  Uses bits 1-0 of byte 0  → 0x03 = 0b00000011
                  AND entire byte 1         → 0xFF = 0b11111111

Result: [0xFF, 0xFF] → 3 white pixels
```

**Example - [BLACK][WHITE][BLACK]:**

```
Pixel 0 (BLACK): 0x00 (bits 7-5 stay 0)
Pixel 1 (WHITE): 0x1C (bits 4-2 set)
Pixel 2 (BLACK): 0x00 (bits 1-0 of byte 0 stay 0, byte 1 stays 0)

Result: [0x1C, 0x00] → [BLACK][WHITE][BLACK]
```

**Color Values:**
```
0x00 = BLACK
0x49 = DARK GRAY
0x92 = LIGHT GRAY
0xFF = WHITE
```

**Note:** This encoding is handled by the SmartResponseXE library. Direct pixel manipulation commands (CMD_PRINT_BLOCK, CMD_PRINT_BLOCK_RLE) exist in the protocol but are currently unused.

---

## Command Sequences

### Typical Command Execution Flow

**User types "ls" and presses Enter:**

```
Step 1: User Input (locally buffered on Arduino)
────────────────────────────────────────────────
User: 'l' → Arduino buffer: "l"
User: 's' → Arduino buffer: "ls"
User: Enter → Send LINE packet to Pi

Arduino→Pi:
  [0xF8][0x02]['l']['s'][CHECKSUM][0xF9]


Step 2: Command Execution (on Pi)
────────────────────────────────────────────────
Pi receives: {'type': 'line', 'data': 'ls'}
Pi executes: subprocess.run(['/bin/bash', '-c', 'ls'])
Pi captures output:
  "CMD>  ls                "
  "file1.txt               "
  "file2.txt               "
  "folder/                 "


Step 3: Screen Update (Pi → Arduino)
────────────────────────────────────────────────
Pi determines: 4 new lines, need to scroll

Pi→Arduino: Scroll up 32 pixels (4 lines × 8 px)
  [0x03][0x20]

Arduino→Pi: READY
  [0xFC]

Pi→Arduino: Write "file1.txt" at y=104
  [0x02][0x68][0x00][0x03][0x00][0x09]['f']['i']['l']['e']['1']['.']['t']['x']['t']

Arduino→Pi: READY
  [0xFC]

Pi→Arduino: Write "file2.txt" at y=112
  [0x02][0x70][0x00][0x03][0x00][0x09]['f']['i']['l']['e']['2']['.']['t']['x']['t']

Arduino→Pi: READY
  [0xFC]

Pi→Arduino: Write "folder/" at y=120
  [0x02][0x78][0x00][0x03][0x00][0x07]['f']['o']['l']['d']['e']['r']['/']

Arduino→Pi: READY
  [0xFC]

Pi→Arduino: Update prompt (empty)
  [0x07][0x80][0x00][0x03][0x00][0x00]

Arduino→Pi: READY
  [0xFC]


Step 4: Next Command Input
────────────────────────────────────────────────
User types next command...
Arduino buffers locally, shows cursor
```

### Font Change Sequence

**User presses Shift+1 (switch to Font 1):**

```
Step 1: Arduino sends modifier + key
────────────────────────────────────────────────
Arduino→Pi: KEY packet (Shift modifier)
  [0xFD][0x10][0xED][0xFE]

Arduino→Pi: KEY packet ('1')
  [0xFD][0x31][0xCC][0xFE]


Step 2: Pi processes action
────────────────────────────────────────────────
Pi: KeyboardHandler returns {'action': 'font_change', 'font': 1}
Pi: terminal.switch_font(1)  # Updates cols/rows
Pi: Stores new font ID


Step 3: Clear and redraw screen
────────────────────────────────────────────────
Pi→Arduino: Clear screen
  [0x06]

Arduino→Pi: READY
  [0xFC]

Pi→Arduino: Write line 1 with font 1
  [0x02][y][0x01][0x03][0x00][len][text...]

Arduino→Pi: READY
  [0xFC]

Pi→Arduino: Write line 2 with font 1
  [0x02][y][0x01][0x03][0x00][len][text...]

... (repeat for all visible lines)

Pi→Arduino: Update prompt with font 1
  [0x07][y][0x01][0x03][0x00][0x00]

Arduino→Pi: READY
  [0xFC]
```

---

## Timing and Performance

### Serial Throughput

**Baud Rate:** 19,200 bits/second
**Effective Data Rate:** ~1,920 bytes/second (accounting for start/stop bits)

**Typical Packet Sizes:**
- READY signal: 1 byte
- KEY packet: 4 bytes
- LINE packet: 5 + N bytes (N = command length)
- SCROLL command: 2 bytes
- WRITE_TEXT command: 6 + N bytes (N = text length)

**Example Calculation - Write 50-char line:**
```
Packet size: 6 + 50 = 56 bytes
Transmission time: 56 / 1920 = 0.029 seconds (~29ms)
Plus READY response: 1 byte = 0.0005 seconds
Plus Arduino processing: ~50-100ms
Total: ~80-130ms per line
```

### Command Latency

From logs:
- Scroll: ~50ms
- Write line: ~100-120ms
- Update prompt: ~50-80ms

**Bottlenecks:**
1. Serial baud rate (19,200)
2. Screen rendering on Arduino
3. Handshaking overhead

### Optimization Strategies

**1. Line Buffering:**
- Old: Send each keypress individually (N packets for N-char command)
- New: Buffer locally, send one LINE packet
- Savings: For "ls -la" (6 chars): 6 packets → 1 packet

**2. Differential Updates:**
- Only send lines that changed
- Skip identical lines
- Reduces screen update packets

**3. Scrolling:**
- Use hardware scroll instead of redrawing entire screen
- 1 scroll command vs multiple write commands

**4. Font-aware Wrapping:**
- Wrap text on Pi side to match font width
- Prevents mid-word breaks on Arduino

---

## Error Handling

### Checksum Validation

**Single Key Packet:**
```cpp
expected_checksum = KEY_START_MARKER ^ key_byte;
if (checksum_byte != expected_checksum) {
    // Ignore packet, return error
    return {'type': 'error', 'reason': 'key_checksum_fail'};
}
```

**Line Packet:**
```cpp
expected_checksum = LINE_START_MARKER ^ length;
for (each data_byte) {
    expected_checksum ^= data_byte;
}
if (checksum_byte != expected_checksum) {
    // Ignore packet, return error
    return {'type': 'error', 'reason': 'line_checksum_fail'};
}
```

### Timeout Handling

**Pi Side:**
```python
def wait_for_ready(self, timeout=1.0):
    start_time = time.time()
    
    while time.time() - start_time < timeout:
        packet = self.read_packet()
        if packet and packet['type'] == 'ready':
            return True
    
    # Timeout - log warning but continue
    print("[WARNING]: timeout waiting for ready signal!")
    return False
```

**Arduino Side:**
```cpp
// Timeout waiting for signal pin
unsigned long startTime = millis();
while (millis() - startTime < _timeoutTimeToWaitForSignalOnMs) {
    if (signal_detected) {
        // Process byte
    }
}
// Timeout - return to main loop
```

### Framing Errors

**Soft Serial:**
```cpp
// Arduino tracks framing errors
uint16_t _framingErrorCount = 0;

// If stop bit is not HIGH, increment counter
if (!RX_READ()) {
    _framingErrorCount++;
}
```

**Status Display:**
```cpp
// Shown on status bar (F0 key toggles)
sprintf(buffer, "CMD:%02X KEY:%02X S%02X R%04X ...",
        lastCommand, lastKey, Serial.framingErrors(), freeMemory());
```

### Recovery Mechanisms

**Bad Packet:**
- Ignore and wait for next packet
- Parser state machine resets to IDLE

**Timeout:**
- Log warning
- Continue operation (don't block indefinitely)

**Serial Disconnect:**
- Currently: No automatic recovery
- Future: Could implement reconnection logic

---

## Protocol Extensions (Future)

### Cursor Control

**Proposed commands:**
```python
CMD_SET_CURSOR = 0x09     # Set cursor position
CMD_CURSOR_MOVE = 0x0A    # Relative cursor movement
```

**Format:**
```
[CMD_SET_CURSOR] [X] [Y]
 0x09            byte byte
```

**Use Case:** Full-screen terminal emulation (nano, vim)

### Color/Grayscale

**Current:** Protocol supports FG/BG color bytes, but always uses white-on-black
**Future:** Implement 4-level grayscale for:
- Syntax highlighting
- Status indicators
- Visual feedback

### Graphics/Bitmap

**Existing (unused):**
```python
CMD_PRINT_BLOCK_RLE = 0x04
CMD_PRINT_BLOCK = 0x05
```

**Use Case:**
- QR codes
- Simple graphics
- Progress bars
- Custom characters

### Batch Operations

**Proposed:**
```python
CMD_PRINT_BATCH = 0x08
```

**Format:**
```
[CMD_PRINT_BATCH] [COUNT] [CMD1] [PARAMS1...] [CMD2] [PARAMS2...] ...
```

**Use Case:** Send multiple commands in one packet, reduce handshaking overhead

---

## Debugging

### Debug Output

**Enable/Disable:**
```cpp
bool enableDebugThroughSerial = true;  // Send to Pi via serial
bool enableDebugToScreen = true;        // Show on status bar
```

**Toggle:**
- Shift+F0: Toggle debug to serial
- Sym+F0: Toggle debug to screen
- F0: Toggle status bar

**Debug Packet Example:**
```cpp
sendDebugPacket("Ask to scroll 16 pixels, scroll offset: 24");

// Sends:
// [0xFA]['A']['s']['k'][' ']['t']['o']...[0xFB]
```

### Status Bar

**Display Format:**
```
CMD:02 KEY:31 S00 R1234 C17 Z D          |
│      │      │   │     │   │ │         └─ Spinner
│      │      │   │     │   │ └────────── D=Debug to screen
│      │      │   │     │   └──────────── Z=Debug to serial
│      │      │   │     └──────────────── C=Cycle time (ms)
│      │      │   └────────────────────── R=Free RAM (bytes)
│      │      └────────────────────────── S=Serial framing errors
│      └───────────────────────────────── Last key pressed
└──────────────────────────────────────── Last command received
```

**Toggle:** Press F0 key

---

## Summary

The protocol is designed for:
- **Simplicity:** Easy to implement and debug
- **Reliability:** Checksums and handshaking
- **Efficiency:** Buffering and differential updates
- **Extensibility:** Room for future enhancements

**Key Features:**
- 19,200 baud soft serial
- Packet-based with checksums
- Out-of-band handshaking via signal pin
- Line buffering reduces round-trips
- READY signal prevents buffer overruns
- Debug packets for development

The protocol successfully balances simplicity with functionality, enabling responsive terminal operation while keeping both sides manageable.

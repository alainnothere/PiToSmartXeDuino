# System Architecture

## Overview

PiToSmartXeDuino implements a terminal emulator where the Raspberry Pi Zero 2W acts as the "brain" and the SMART Response XE acts as a "dumb terminal" providing only keyboard input and screen output.

**Division of Responsibilities:**
- **Pi (Intelligence):** Command execution, terminal buffer management, line tracking, output formatting
- **XE (I/O Device):** Keyboard scanning, screen rendering, local input buffering

This architecture keeps the resource-constrained ATmega128RFA1 focused on real-time I/O operations while the Pi handles all computational tasks.

---

## System Components

### Raspberry Pi Side

**Main Components:**

1. **Terminal Backend** (`SubprocessTerminal.py` or `PyteAndPtyProcessTerminal.py`)
    - Executes shell commands
    - Captures stdout/stderr
    - Wraps output to current font width
    - Currently using `SubprocessTerminal` (faster)
    - `PyteAndPtyProcessTerminal` reserved for future full terminal emulation (nano, top, etc.)

2. **Serial Communication** (`serialCommunicationsToArduino.py`)
    - High-level API wrapping lower-level modules
    - Maintains backward compatibility with original interface

3. **Screen Controller** (`screen_controller.py`)
    - Manages screen buffer (history of terminal output)
    - Tracks what's currently displayed
    - Implements differential updates (only sends changed lines)
    - Handles scrolling and prompt line separately

4. **Protocol Parser** (`protocol.py`)
    - Non-blocking state machine for parsing incoming packets
    - Handles: READY signals, KEY packets, LINE packets, DEBUG packets

5. **Serial Connection** (`serial_connection.py`)
    - Low-level serial I/O with handshaking
    - Uses pigpio for GPIO timing
    - Implements soft serial signal pin protocol

6. **Keyboard Handler** (`keyboard_handler.py`)
    - Processes key codes and modifier combinations
    - Translates special key sequences (Shift+0/1/2/3) into actions

### Arduino Side

**Main Components:**

1. **Main Loop** (`DuinoToPiTerminal.ino`)
    - Keyboard scanning
    - Packet reception and command dispatch
    - Screen update coordination

2. **Soft Serial** (`SoftClockSerial.cpp/h`)
    - Timer-based bit-banging serial implementation
    - 19,200 baud on JTAG pins (TMS/TCK/TDO)
    - Signal pin handshaking

3. **Input Buffer** (`SrxeInputBuffer.h`)
    - Local line buffering (up to 128 characters)
    - Cursor positioning and editing
    - Renders prompt line with blinking cursor
    - Only sends complete lines to Pi (on Enter)

4. **Keyboard Handler (using bitbank2's library)** (`SrxeKeyboard.h`)
    - Scans keyboard matrix
    - Debouncing
    - Routes keys to input buffer or sends immediately (special keys)

5. **Command Handler** (`SrxeCommandHandler.h`)
    - Processes commands from Pi
    - Executes screen updates
    - Manages scroll offset

6. **Screen Library (using bitbank2's library)** (`SmartResponseXEmt.cpp/h`)
    - Low-level LCD control
    - Text rendering in 4 font sizes
    - Scrolling primitives

---

## Data Flow

### User Input Flow

```
┌──────────────────────────────────────────────────────────────────┐
│ 1. User types on XE keyboard                                     │
└────────────────────────┬─────────────────────────────────────────┘
                         │
                         ▼
┌──────────────────────────────────────────────────────────────────┐
│ 2. SrxeKeyboard scans matrix, debounces                          │
└────────────────────────┬─────────────────────────────────────────┘
                         │
                         ▼
                    Decision Point:
                         │
         ┌───────────────┼───────────────┐
         │                               │
         ▼                               ▼
┌─────────────────┐            ┌──────────────────────┐
│ Special Key?    │            │ Regular Character?   │
│ (Shift+0/1/2/3, │            │ (a-z, 0-9, etc.)    │
│  Sym+C, etc.)   │            │                      │
└────────┬────────┘            └──────────┬───────────┘
         │                                │
         ▼                                ▼
┌─────────────────┐            ┌──────────────────────┐
│ Send KEY packet │            │ Add to local buffer  │
│ immediately     │            │ Show on prompt line  │
│ to Pi           │            │ with cursor          │
└────────┬────────┘            └──────────┬───────────┘
         │                                │
         │                                ▼
         │                     ┌──────────────────────┐
         │                     │ User presses Enter?  │
         │                     └──────────┬───────────┘
         │                                │
         │                                ▼
         │                     ┌──────────────────────┐
         │                     │ Send LINE packet     │
         │                     │ [0xF8][LEN][DATA]    │
         │                     │ [CHECKSUM][0xF9]     │
         │                     └──────────┬───────────┘
         │                                │
         └────────────────┬───────────────┘
                          │
                          ▼
┌──────────────────────────────────────────────────────────────────┐
│ 3. Pi receives packet via serial_connection.py                   │
└────────────────────────┬─────────────────────────────────────────┘
                         │
                         ▼
┌──────────────────────────────────────────────────────────────────┐
│ 4. PacketParser parses and returns:                              │
│    - {'type': 'key', 'key': 0x33} for special keys              │
│    - {'type': 'line', 'data': 'ls -la'} for buffered input      │
└────────────────────────┬─────────────────────────────────────────┘
                         │
                         ▼
┌──────────────────────────────────────────────────────────────────┐
│ 5. KeyboardHandler processes:                                    │
│    - Special keys → {'action': 'font_change', 'font': 1}        │
│    - Commands → {'type': 'command', 'value': 'ls -la'}          │
└────────────────────────┬─────────────────────────────────────────┘
                         │
                         ▼
                    Decision Point
                         │
         ┌───────────────┼───────────────┐
         │                               │
         ▼                               ▼
┌─────────────────┐            ┌──────────────────────┐
│ Action?         │            │ Command?             │
│ (font_change,   │            │                      │
│  clear_buffer)  │            │                      │
└────────┬────────┘            └──────────┬───────────┘
         │                                │
         ▼                                ▼
   See Font Switch                ┌──────────────────────┐
   Flow below                      │ 6. Execute command   │
                                   │    via Terminal      │
                                   │    Backend           │
                                   └──────────┬───────────┘
                                              │
                                              ▼
                                   ┌──────────────────────┐
                                   │ 7. Capture output    │
                                   │    Wrap to font cols │
                                   └──────────┬───────────┘
                                              │
                                              ▼
                                        See Output
                                        Flow below
```

### Command Output Flow

```
┌──────────────────────────────────────────────────────────────────┐
│ Terminal Backend captures command output                         │
│ Example: "ls -la" produces 10 lines of output                   │
└────────────────────────┬─────────────────────────────────────────┘
                         │
                         ▼
┌──────────────────────────────────────────────────────────────────┐
│ Wrap lines to current font column width                          │
│ Font 0: 52 cols, Font 1: 64 cols, etc.                          │
└────────────────────────┬─────────────────────────────────────────┘
                         │
                         ▼
┌──────────────────────────────────────────────────────────────────┐
│ ScreenController.send_new_lines() compares:                      │
│ - OLD: What's currently in screen buffer                         │
│ - NEW: Lines to display                                          │
└────────────────────────┬─────────────────────────────────────────┘
                         │
                         ▼
                    Decision Point:
                    Few lines or many?
                         │
         ┌───────────────┼───────────────┐
         │                               │
         ▼                               ▼
┌─────────────────────┐        ┌──────────────────────┐
│ Fewer new lines     │        │ Many new lines       │
│ than screen rows?   │        │ (>= screen rows)?    │
└────────┬────────────┘        └──────────┬───────────┘
         │                                │
         ▼                                ▼
┌─────────────────────┐        ┌──────────────────────┐
│ SCROLL UP:          │        │ COMPARE & UPDATE:    │
│ 1. Calculate pixels │        │ 1. Compare old vs    │
│    = lines × px/row │        │    new line by line  │
│ 2. Send CMD_SCROLL  │        │ 2. Only send lines   │
│ 3. Send only new    │        │    that changed      │
│    bottom lines     │        │ 3. Skip identical    │
└────────┬────────────┘        └──────────┬───────────┘
         │                                │
         └────────────────┬───────────────┘
                          │
                          ▼
┌──────────────────────────────────────────────────────────────────┐
│ For each line to send:                                           │
│ - Send CMD_WRITE_TEXT (0x02)                                     │
│ - Include: y_position, font_id, colors, length, text            │
│ - WAIT for READY (0xFC) from Arduino                            │
└────────────────────────┬─────────────────────────────────────────┘
                         │
                         ▼
┌──────────────────────────────────────────────────────────────────┐
│ Update prompt line:                                              │
│ - Send CMD_PRINT_PROMPT (0x07) with empty text                  │
│ - Arduino prepends "CMD> " automatically                         │
│ - WAIT for READY (0xFC)                                          │
└────────────────────────┬─────────────────────────────────────────┘
                         │
                         ▼
                   Command complete
```

### Font Switch Flow

```
┌──────────────────────────────────────────────────────────────────┐
│ User presses Shift+1 (switch to Font 1)                         │
└────────────────────────┬─────────────────────────────────────────┘
                         │
                         ▼
┌──────────────────────────────────────────────────────────────────┐
│ Arduino sends: [KEY_MODIFIER_SHIFT][0x31]                       │
└────────────────────────┬─────────────────────────────────────────┘
                         │
                         ▼
┌──────────────────────────────────────────────────────────────────┐
│ Pi KeyboardHandler returns:                                      │
│ {'action': 'font_change', 'font': 1}                            │
└────────────────────────┬─────────────────────────────────────────┘
                         │
                         ▼
┌──────────────────────────────────────────────────────────────────┐
│ Pi Main Loop:                                                    │
│ 1. terminal.switch_font(1) - Updates terminal dimensions        │
│ 2. Send CMD_CLEAR_SCREEN (0x06)                                 │
│ 3. WAIT for READY                                                │
└────────────────────────┬─────────────────────────────────────────┘
                         │
                         ▼
┌──────────────────────────────────────────────────────────────────┐
│ Arduino clears screen, resets scroll offset to 0                │
│ Sends READY (0xFC)                                               │
└────────────────────────┬─────────────────────────────────────────┘
                         │
                         ▼
┌──────────────────────────────────────────────────────────────────┐
│ Pi re_send_screen_lines_to_arduino(font_id):                    │
│ - Sends all visible lines from buffer using new font            │
│ - Each line: CMD_WRITE_TEXT with new font_id                    │
│ - WAIT for READY after each line                                │
└────────────────────────┬─────────────────────────────────────────┘
                         │
                         ▼
                   Screen redrawn
```

---

## Screen Buffer Management

### Buffer Structure

The Pi maintains a scrolling buffer of terminal output:

```python
# From screen_controller.py
self._lines: list[str]  # Buffer of lines sent to screen

# From config.py
TERMINAL_HISTORY_ROWS = 100  # Maximum rows in buffer
```

**Key Characteristics:**
- Buffer stores up to 100 rows of history
- Only the last N rows are visible (depends on font)
- Oldest lines scroll out of view but remain in buffer
- Prompt line (row 16 for fonts 0/1, row 7 for fonts 2/3) is handled separately

### Font Configurations

From `config.py`:

```python
# [font_id, cols, rows_visible, pixels_per_row, padding]
FONT_CONFIGURATION = [
    [0, 52, 17, 8, 0],  # FONT_NORMAL: 52 chars × 17 rows × 8px
    [1, 64, 17, 8, 0],  # FONT_SMALL:  64 chars × 17 rows × 8px
    [2, 32, 8, 17, 0],  # FONT_MEDIUM: 32 chars × 8 rows × 17px
    [3, 25, 8, 17, 0],  # FONT_LARGE:  25 chars × 8 rows × 17px
]
```

**Screen Layout:**
- Total height: 136 pixels
- Fonts 0/1: 17 visible rows (16 for output + 1 for prompt)
- Fonts 2/3: 8 visible rows (7 for output + 1 for prompt)

### Scrolling Mechanism

**Physical Scrolling (on XE) (using bitbank2's library):**

The XE's LCD controller has a built-in scroll register. Instead of redrawing the entire screen when scrolling, we update the scroll offset:

```python
# From screen_controller.py
def scroll_screen_up(self, pixels: int):
    # Send CMD_SCROLL_UP with pixel count
    cmd = struct.pack('>B', CMD_SCROLL_UP)
    cmd += struct.pack('>B', pixels)
    self._serial.send(cmd)
```

**Arduino tracks scroll offset:**

```cpp
// From SrxeCommandHandler.h
uint16_t pixelsScrolled = 0;

void handleScrollUp() {
    uint8_t pixels = serialReadUint8();
    
    // Accumulate scroll offset (wraps at screen height)
    pixelsScrolled = (pixelsScrolled + pixels) % screenVerticalSize;
    
    // Update hardware scroll register
    SRXEScroll(pixels);
}
```

**Scroll Offset Behavior:**
- Accumulates as content scrolls up
- Wraps at 136 pixels (screen height)
- All Y coordinates sent from Pi are adjusted: `y = (y + pixelsScrolled) % 136`
- Lines that scroll off the top physically reappear at bottom (but are overwritten with new content)

**Example Scroll Calculation:**

```
Font 0 (8 pixels per row):
- 2 new lines appear
- Scroll pixels = 2 × 8 = 16
- pixelsScrolled += 16

Before scroll:  pixelsScrolled = 24
After scroll:   pixelsScrolled = 40
```

### Prompt Line Handling

The prompt line is always on the last visible row and is handled separately:

**Y Position Calculation:**
```python
# From screen_controller.py
def update_prompt(self, text: str, font_id: int):
    font_config = FONT_CONFIGURATION[font_id]
    
    # y = rows_visible * pixels_per_row + padding - pixels_per_row
    y = font_config[2] * font_config[3] + font_config[4] - font_config[3]
    
    self._send_line_raw(y, font_id, text, CMD_PRINT_PROMPT)
```

**For Font 0:**
```
y = 17 * 8 + 0 - 8 = 128
```

**Special Prompt Command:**
- Uses `CMD_PRINT_PROMPT` (0x07) instead of `CMD_WRITE_TEXT` (0x02)
- Arduino automatically prepends "CMD> " to the text
- Allows Pi to send just the user input portion

### Differential Screen Updates

The ScreenController tracks what's been sent and only sends changes:

```python
# From screen_controller.py
def send_new_lines(self, lines_to_print: list[str], font_id: int, 
                   force_redraw: bool = False):
    
    if not force_redraw:
        # Compare new lines with buffer
        for i in range(0, rows_in_screen):
            new_line = lines_to_print[len(lines_to_print) - 1 - i]
            old_line = self._lines[len(self._lines) - 1 - i] if exists else ""
            
            # Only send if different
            if new_line.strip() != old_line.strip():
                self.send_line(new_line, rows_in_screen - i - 1, font_id)
```

**Optimization Strategy:**

1. **Few new lines** (< screen rows):
    - Scroll screen up by (new_lines × pixels_per_row)
    - Send only the new bottom lines

2. **Many new lines** (>= screen rows):
    - Compare each line with what's in buffer
    - Send only lines that changed
    - Skip identical lines

3. **Font change:**
    - Force full redraw (different layout)
    - Clear screen first
    - Send all visible lines

---

## Command Flow with Handshaking

### READY Signal Protocol

**Critical Rule:** The Pi must wait for READY (0xFC) from Arduino before sending the next command.

**Why?** The Arduino processes commands sequentially and may take time for:
- Screen rendering (text drawing, scrolling)
- Serial buffer management
- Keyboard scanning

**Example from logs:**

```
[send command CMD_SCROLL_UP]
    [wait for READY...]
        [Arduino DEBUG: "Ask to scroll 16 pixels, scroll offset: 24"]
        [Receive READY, took: 0.0528 seconds]
[send command CMD_WRITE_TEXT]
    [wait for READY...]
        [Arduino DEBUG: "write y: 120, fs: 0, fc: 3, bc: 0, l: 39"]
        [Receive READY, took: 0.1161 seconds]
```

**Implementation:**

```python
# From serial_connection.py
def wait_for_ready(self, timeout: float = 1.0) -> bool:
    start_time = time.time()
    
    while True:
        if time.time() - start_time > timeout:
            return False  # Timeout
        
        packet = self.read_packet()
        
        if packet and packet['type'] == 'ready':
            return True  # Got READY signal
        
        # Continue waiting...
```

**Every screen operation waits:**
```python
# From screen_controller.py
def send_line(self, line: str, display_row: int, font_id: int):
    # ... build command packet ...
    self._serial.send(cmd)
    self._serial.wait_for_ready(timeout=1.0)  # WAIT!
```

---

## Terminal Backend Comparison

### SubprocessTerminal (Current Default)

**Implementation:**
```python
# From SubprocessTerminal.py
def run_command(self, command, timeout=10.0):
    process = subprocess.Popen(
        ['/bin/bash', '-c', command],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        env=my_env  # Sets COLUMNS and LINES
    )
    
    stdout, stderr = process.communicate(timeout=timeout)
    output = f"\n{PROMPT} {command}\n" + stdout
    self.last_output_lines = self.wrap_lines(output.splitlines())
```

**Characteristics:**
- Executes each command independently (no persistent shell)
- Fast execution
- Simple output capture
- No VT100 escape sequence support
- Cannot run interactive programs (nano, vim, top)

**When to use:**
- Basic command execution
- Speed is important
- Don't need full terminal features

### PyteAndPtyProcessTerminal (Future/Advanced)

**Implementation:**
```python
# From PyteAndPtyProcessTerminal.py
def run_command(self, command, timeout=10.0):
    self.process = PtyProcess.spawn(
        ['/bin/bash', '-c', command],
        dimensions=(self.rows, self.cols)
    )
    
    # Read PTY output with VT100 sequences
    while self.process.isalive():
        output = self.process.read()
        self.stream.feed(output)  # Feed to pyte terminal emulator
```

**Characteristics:**
- Uses pseudo-terminal (PTY)
- Supports VT100/ANSI escape sequences
- Can run full-screen programs
- Slower due to VT100 parsing
- More complex state management

**When to use:**
- Need to run nano, vim, top, htop
- Need cursor positioning
- Need colors (if added to protocol)

**Status:** Code present but not active. Requires:
- Full VT100 escape sequence parsing
- Cursor position tracking
- Potentially extended protocol for cursor commands

---

## Performance Characteristics

### Timing Analysis (from logs)

**Typical command execution:**
```
Command "a" (invalid):
- Total time: 0.238 seconds
  - Command execution: ~0.030s
  - Screen update: ~0.208s
    - Scroll: 0.053s
    - Write line: 0.116s
    - Update prompt: 0.055s
```

**Screen operation times:**
- Scroll: ~50ms
- Write line: ~100-120ms
- Update prompt: ~50-80ms

**Key Bottlenecks:**
1. Serial communication at 19,200 baud
2. Screen rendering on Arduino
3. Waiting for READY signals

**Optimization Strategies:**
1. Differential updates (only send changed lines)
2. Local line buffering (reduces round-trips)
3. Scroll instead of full redraws when possible
4. Font-specific column wrapping

---

## Memory Management

### Pi Side

**Screen Buffer:**
```python
self._lines: list[str]  # Up to 100 rows @ ~64 chars = ~6.4KB
```

**Packet Buffers:**
```python
RX_BUFFER_SIZE = 128  # Serial receive buffer
```

### Arduino Side

**Input Buffer:**
```cpp
static const uint8_t MAX_INPUT = 128;  // Command line buffer
char _buffer[MAX_INPUT + 1];
```

**Screen Buffer:**
```cpp
char buffer[64];  # Reused for command building
```

**Serial Buffers:**
```cpp
static const uint8_t RX_BUFFER_SIZE = 128;
uint8_t _rxBuffer[RX_BUFFER_SIZE];  // Receive
uint8_t _txBuffer[RX_BUFFER_SIZE];  // Transmit
```

**Total RAM Usage:** ~500-600 bytes for buffers (ATmega128RFA1 has 16KB RAM)

---

## State Management

### Pi State

**Global State:**
- Current font ID
- Screen buffer (list of lines)
- Terminal backend instance
- Keyboard handler state

**Per-Command State:**
- Command being executed
- Output capture in progress
- Lines to send

### Arduino State

**Global State:**
- Current font ID
- Scroll offset (pixelsScrolled)
- Input buffer contents
- Cursor position
- Last key pressed

**No Persistent State Between Commands:**
- Each command is stateless
- Screen content persists but Pi doesn't track it pixel-perfect
- Rely on differential updates for efficiency

---

## Error Handling

### Protocol Level

**Checksums:**
- LINE packets: XOR checksum of all bytes
- KEY packets: XOR of start marker and key

**Timeouts:**
- Waiting for READY: 1 second default
- Command execution: 10 seconds default
- Serial signal: 100ms

**Error Recovery:**
- Bad checksum: Ignore packet
- Timeout: Log warning, continue
- Framing errors: Tracked but not critical

### Application Level

**Invalid Commands:**
- Captured by bash, shown as error output
- Terminal continues normally

**Serial Disconnection:**
- Not currently handled

---

## Future Enhancements

### Planned Features

1. **Full Terminal Emulation:**
    - Switch to PyteAndPtyProcessTerminal
    - Support nano, vim, top
    - Cursor positioning commands

2. **Battery Power:**
    - Board revision with 5V boost converter
    - True portable operation

3. **Extended Protocol:**
    - Cursor positioning commands
    - Color support (4-level grayscale)
    - Graphics/bitmap commands

4. **Wireless Module:**
    - CC1101 integration
    - Remote terminal access
    - Mesh networking

### Known Limitations

1. **No full-screen apps:** Requires VT100 support
2. **Fixed baud rate:** 19,200 is limit of soft serial reliability
3. **No cursor keys:** Arrow keys not yet mapped to terminal control

---

## Summary

The architecture prioritizes:
- **Simplicity:** Clear separation between Pi (brain) and XE (I/O)
- **Reliability:** Handshaking ensures commands complete
- **Efficiency:** Differential updates minimize serial traffic
- **Maintainability:** Modular design, single-responsibility components

The system works well for basic shell interaction and can be extended for more advanced terminal features.

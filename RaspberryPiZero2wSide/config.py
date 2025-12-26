"""
Configuration constants for Smart Response XE Terminal

This file contains all protocol markers, font configuration, timing constants,
and hardware pin definitions used by both the Pi and conceptually mirrors
what's on the Arduino side.

FONT CONFIGURATION:
==================
The screen is 136 pixels tall. Different fonts divide this differently:
- Small fonts (8px): 136/8 = 17 rows (divides evenly)
- Large fonts (17px): 136/17 = 8 rows (divides evenly)

Font configuration: [font_id, cols, rows_visible, pixels_per_row, padding]

The padding field was added because some font/row combinations don't
divide evenly into 136 pixels, causing the last row to be offset.

"please document what you do with all this info so in the future some
poor soul that decides to work on this have this info"
"""

# =============================================================================
# SERIAL CONFIGURATION
# =============================================================================

BAUD_RATE_SOFT_SERIAL = 19200
BAUD_RATE_HARDWARE_SERIAL = 115200
USING_SOFT_SERIAL = True

# Timeout waiting for Arduino signal pin to go LOW (ready to receive)
TIMEOUT_WAITING_FOR_SIGNAL_TO_TRANSFER = 100 / 1000  # 100ms

# GPIO pin number (BCM numbering) for the Arduino ready signal
SIGNAL_PIN_NUMBER_ON_GPIO_NUMBERING = 27

# Configuration
VERTICAL_SCREEN_SIZE = 136

# =============================================================================
# PROTOCOL MARKERS - COMMANDS (Pi → Arduino)
# =============================================================================

CMD_WRITE_TEXT = 0x02  # Write text to screen
CMD_SCROLL_UP = 0x03  # Scroll screen up by N pixels
CMD_PRINT_BLOCK_RLE = 0x04  # Print RLE-encoded block
CMD_PRINT_BLOCK = 0x05  # Print raw block
CMD_CLEAR_SCREEN = 0x06  # Clear the screen
CMD_PRINT_PROMPT = 0x07  # Print the command prompt line
CMD_PRINT_BATCH = 0x08  # Batch screen update (future)

CMD_PADDING_MARKER = 0xFF  # Padding/no-op byte

# =============================================================================
# PROTOCOL MARKERS - RESPONSES (Arduino → Pi)
# =============================================================================

CMD_READY_FOR_NEXT_COMMAND = 0xFC  # Arduino is ready for next command

# =============================================================================
# PROTOCOL MARKERS - DEBUG PACKETS (Arduino → Pi)
# =============================================================================

DEBUG_START_MARKER = 0xFA
DEBUG_END_MARKER = 0xFB

# =============================================================================
# PROTOCOL MARKERS - KEYBOARD PACKETS (Arduino → Pi)
# =============================================================================

# Single key packet: [KEY_START] [KEY] [CHECKSUM] [KEY_END]
# CHECKSUM = KEY_START ^ KEY
KEY_START_MARKER = 0xFD
KEY_END_MARKER = 0xFE

# Key modifier codes (sent before the key when modifier is active)
KEY_MODIFIER_SHIFT = 0x10
KEY_MODIFIER_SYM = 0x11

# =============================================================================
# PROTOCOL MARKERS - LINE INPUT PACKETS (Arduino → Pi)
# =============================================================================

# Line input packet: [LINE_START] [LENGTH] [DATA...] [CHECKSUM] [LINE_END]
# CHECKSUM = LINE_START ^ LENGTH ^ (XOR of all data bytes)
LINE_START_MARKER = 0xF8
LINE_END_MARKER = 0xF9

# =============================================================================
# FONT CONFIGURATION
# =============================================================================

# Font configuration: [font_id, cols, rows_visible, pixels_per_row, padding]
#
# - font_id: Matches Arduino FONT_* constants
# - cols: Characters per line
# - rows_visible: Number of text rows visible on screen
# - pixels_per_row: Height of each character in pixels
# - padding: Extra pixels to add for proper alignment
#
# Y position formula for a row:
#   y = row * pixels_per_row + padding
#
# Last line (prompt) Y position:
#   y = rows_visible * pixels_per_row + padding - pixels_per_row

FONT_NORMAL = 0
FONT_SMALL = 1
FONT_MEDIUM = 2
FONT_LARGE = 3

FONT_CONFIGURATION = [
    # [font_id, cols, rows_visible, pixels_per_row, padding]
    [FONT_NORMAL, 52, 17, 8, 0],  # Normal: 52 chars × 17 rows × 8px
    [FONT_SMALL, 64, 17, 8, 0],  # Small: 64 chars × 17 rows × 8px
    [FONT_MEDIUM, 32, 8, 17, 0],  # Medium: 32 chars × 8 rows × 17px
    [FONT_LARGE, 25, 8, 17, 0],  # Large: 25 chars × 8 rows × 17px
]


# Helper to get font config by ID
def get_font_config(font_id):
    """Get font configuration tuple by font ID"""
    if 0 <= font_id < len(FONT_CONFIGURATION):
        return FONT_CONFIGURATION[font_id]
    return FONT_CONFIGURATION[FONT_NORMAL]


# =============================================================================
# SCREEN CONFIGURATION
# =============================================================================

SCREEN_WIDTH_PIXELS = 128
SCREEN_HEIGHT_PIXELS = 136

# The prompt prefix shown on the input line
PROMPT = "CMD> "

# =============================================================================
# TERMINAL BUFFER CONFIGURATION
# =============================================================================

# Maximum number of rows to keep in history buffer
TERMINAL_HISTORY_ROWS = 100

# =============================================================================
# LOG CONFIGURATION
# =============================================================================

# 5 = only if nuclear bombs go off let me know
# 4 = error
# 3 = info
# 2 = debug
# 1 = I love to see infinite number of letters appear on screen
LOG_LEVEL_TO_SEE = 3

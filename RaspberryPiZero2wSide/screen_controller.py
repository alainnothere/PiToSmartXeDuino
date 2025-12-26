"""
Screen controller for Smart Response XE Terminal

This module manages the screen buffer and sends display commands to the Arduino.
It tracks what's currently displayed to optimize updates (only sending changed lines).
"""

import struct

from config import (
    FONT_CONFIGURATION,
    CMD_WRITE_TEXT,
    CMD_SCROLL_UP,
    CMD_CLEAR_SCREEN,
    CMD_PRINT_PROMPT,
    PROMPT,
    TERMINAL_HISTORY_ROWS,
)
from serial_connection import ArduinoSerial
from utilities import Utilities


class ScreenController:
    """
    Manages screen content and sends display commands to Arduino.

    Tracks what's been sent to the screen to optimize updates:
    - Only sends lines that have changed
    - Handles scrolling efficiently
    - Manages the command prompt separately from output
    """

    def __init__(self, serial: ArduinoSerial):
        """
        Initialize screen controller.

        Args:
            serial: ArduinoSerial instance for communication
        """
        self._serial = serial
        self._lines: list[str] = []  # Buffer of lines sent to screen

    @property
    def lines(self) -> list[str]:
        """Get current line buffer (for testing)"""
        return self._lines

    @lines.setter
    def lines(self, value: list[str]):
        """Set line buffer (for testing)"""
        self._lines = value

    def clear_screen(self, clear_buffer: bool = True):
        """
        Clear the Arduino screen.

        Args:
            clear_buffer: If True, also clear the local line buffer
        """
        if clear_buffer:
            self._lines.clear()

        cmd = struct.pack('>B', CMD_CLEAR_SCREEN)
        self._serial.send(cmd)
        self._serial.wait_for_ready(timeout=1.0)

    def scroll_screen_up(self, pixels: int):
        """
        Scroll the screen up by a number of pixels.

        Args:
            pixels: Number of pixels to scroll
        """
        Utilities.print_with_indent(f"Scrolling up: {pixels} pixels")

        cmd = struct.pack('>B', CMD_SCROLL_UP)
        cmd += struct.pack('>B', pixels)

        self._serial.send(cmd)
        self._serial.wait_for_ready(timeout=1.0)

    def update_prompt(self, text: str, font_id: int):
        """
        Update the command prompt line.

        The prompt is always on the last visible row.

        Args:
            text: Text to display after "CMD> "
            font_id: Current font ID
        """
        font_config = FONT_CONFIGURATION[font_id]

        # Calculate Y position for last line
        # y = rows_visible * pixels_per_row + padding - pixels_per_row
        y = font_config[2] * font_config[3] + font_config[4] - font_config[3]

        self._send_line_raw(y, font_id, text, CMD_PRINT_PROMPT)

    def send_line(self, line: str, display_row: int, font_id: int, force_pad: bool = True):
        """
        Send a single line to a specific display row.

        Args:
            line: Text to display
            display_row: Row number on display (0 = top)
            font_id: Current font ID
            force_pad: If True, pad line to full width
        """
        if display_row < 0:
            Utilities.print_with_indent(f"invalid display_row: {display_row}")
            return

        # Handle empty lines
        if len(line) == 0:
            line = "_"

        # Workaround for screen corruption at certain lengths
        if len(line) == 24:
            line = line + "_"

        font_config = FONT_CONFIGURATION[font_id]
        font_cols = font_config[1]

        # Pad or truncate line to font width
        if force_pad:
            line = line[:font_cols].ljust(font_cols)

        # Calculate Y position
        y = display_row * font_config[3] + font_config[4]

        Utilities.print_with_indent_and_log_level(f"display_row: {display_row}, Y: {y}", 1)
        self._send_line_raw(y, font_id, line, CMD_WRITE_TEXT)

    def _send_line_raw(self, y_position: int, font_id: int, line: str,
                       command: int = CMD_WRITE_TEXT):
        """
        Send a line at a specific Y pixel position.

        Args:
            y_position: Y position in pixels
            font_id: Font ID
            line: Text to display
            command: Command byte (CMD_WRITE_TEXT or CMD_PRINT_PROMPT)
        """
        text_bytes = line.rstrip().encode('ascii', errors='replace')
        length = len(text_bytes)

        fore_color = 3  # White
        back_color = 0  # Black

        cmd = struct.pack('>B', command)
        cmd += struct.pack('>B', y_position)
        cmd += struct.pack('>B', font_id)
        cmd += struct.pack('>B', fore_color)
        cmd += struct.pack('>B', back_color)
        cmd += struct.pack('>B', length)
        cmd += text_bytes

        Utilities.print_with_indent(
            f"command: 0x{command:02X}, y: {y_position}, font: {font_id}, "
            f"len: {length}, text: {line[:20]}...")

        self._serial.send(cmd)
        self._serial.wait_for_ready(timeout=1.0)

    def send_new_lines(self, lines_to_print: list[str], font_id: int,
                       force_redraw: bool = False):
        """
        Send new lines to the screen, optimizing for minimal updates.

        This method:
        - Compares new lines with what's already on screen
        - Scrolls if needed
        - Only sends lines that have changed

        Args:
            lines_to_print: New lines to display
            font_id: Current font ID
            force_redraw: If True, redraw all lines without comparison
        """
        scrolled_lines = len(lines_to_print)

        # Nothing to do if no new lines
        if scrolled_lines == 0:
            return

        font_config = FONT_CONFIGURATION[font_id]
        visible_rows = font_config[2]
        rows_in_screen = visible_rows - 1  # -1 for prompt line

        Utilities.print_lines(self._lines, lines_to_print,
                              f"old_lines vs lines_to_print; visible_rows: {visible_rows}, "
                              f"rows_in_screen: {rows_in_screen}")

        Utilities.trim_trailing_empty(lines_to_print)
        Utilities.trim_trailing_empty(self._lines)

        if not force_redraw:
            scrolled_lines = len(lines_to_print)

            # Case 1: Fewer new lines than screen rows - scroll and add
            if rows_in_screen > scrolled_lines:
                scroll_pixels = scrolled_lines * font_config[3]
                self.scroll_screen_up(scroll_pixels)

                # Print new lines from bottom up
                for i in range(0, scrolled_lines):
                    new_line = lines_to_print[len(lines_to_print) - i - 1]

                    # Skip prompt lines
                    if not new_line.startswith(PROMPT):
                        self.send_line(new_line, rows_in_screen - i - 1, font_id)

            # Case 2: More or equal new lines - compare and update only differences
            else:
                for i in range(0, rows_in_screen):
                    new_line = lines_to_print[len(lines_to_print) - 1 - i]

                    # Get old line if it exists
                    old_line = ""
                    old_line_position = len(self._lines) - 1 - i
                    if (len(self._lines) > old_line_position >= 0 and
                            len(self._lines) > 0):
                        old_line = self._lines[old_line_position]

                    # Skip prompt lines
                    if not new_line.startswith(PROMPT):
                        # Only send if different
                        if new_line.strip() != old_line.strip():
                            self.send_line(new_line, rows_in_screen - i - 1, font_id)

        # Update local buffer
        self._lines.extend(lines_to_print)
        self._lines = self._lines[-TERMINAL_HISTORY_ROWS:]

        Utilities.print_lines(self._lines, lines_to_print, "rows after printing")

    def resend_screen(self, font_id: int):
        """
        Resend all visible lines to the screen.

        Used after font change when the entire screen needs redrawing.

        Args:
            font_id: Current font ID
        """
        Utilities.print_with_indent("Resending screen")

        font_config = FONT_CONFIGURATION[font_id]
        visible_rows = font_config[2]
        rows_in_screen = visible_rows - 1

        # Send lines from bottom up
        line_index = 1
        for row in range(rows_in_screen, 0, -1):
            if len(self._lines) > 0:
                buffer_index = len(self._lines) - line_index
                if buffer_index >= 0:
                    line = self._lines[buffer_index]
                    self.send_line(line, row - 1, font_id)

            line_index += 1

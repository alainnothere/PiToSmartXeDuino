"""
Serial communication wrapper for Smart Response XE Terminal

This module provides the high-level API for communicating with the Arduino.
It wraps the lower-level modules (serial_connection, screen_controller, protocol)
into a single interface that matches the original API for backward compatibility.
"""

import time

from config import (
    FONT_CONFIGURATION,
    PROMPT,
    LINE_START_MARKER,
    TERMINAL_HISTORY_ROWS,
)
from serial_connection import ArduinoSerial
from screen_controller import ScreenController
from keyboard_handler import KeyboardHandler
from utilities import Utilities

# Re-export for backward compatibility
fontConfiguration = FONT_CONFIGURATION


class SerialCommunicationToArduino:
    """
    High-level interface for Arduino communication.

    This class provides the same API as the original implementation
    but uses the new modular structure internally.
    """

    def __init__(self, ser=None, serial_port: str = None, baud_rate: int = None):
        """
        Initialize communication with Arduino.

        Args:
            ser: Unused, kept for backward compatibility
            serial_port: Serial port path (e.g., '/dev/ttyAMA0')
            baud_rate: Unused, baud rate is set in config.py
        """
        if serial_port is None:
            print("Serial port not specified")
            exit(1)

        self._arduino = ArduinoSerial(serial_port)
        self._screen = ScreenController(self._arduino)

    @property
    def lines(self) -> list[str]:
        """Get current line buffer"""
        return self._screen.lines

    @lines.setter
    def lines(self, value: list[str]):
        """Set line buffer (for testing)"""
        self._screen.lines = value

    @property
    def ser(self):
        """Get underlying serial object (for backward compatibility)"""
        return self._arduino._ser

    def clear_screen(self, clear_buffer: bool = True):
        """Clear the screen"""
        start_time = time.time()
        self._screen.clear_screen(clear_buffer)
        Utilities.print_with_indent(f"Operation completed in {time.time() - start_time} secs")

    def scroll_screen_up(self, scroll_pixels: int):
        """Scroll screen up by pixels"""
        start_time = time.time()
        self._screen.scroll_screen_up(scroll_pixels)
        Utilities.print_with_indent(f"Operation completed in {time.time() - start_time} secs")

    def update_prompt(self, prompt: str, font_id: int):
        """Update the command prompt"""
        start_time = time.time()
        Utilities.print_with_indent(f"prompt: {prompt}")
        self._screen.update_prompt(prompt, font_id)
        Utilities.print_with_indent(f"Operation completed in {time.time() - start_time} secs")

    def send_line_to_arduino(self, line: str, display_row: int, font_id: int,
                             force_pad: bool = True):
        """Send a single line to the screen"""
        self._screen.send_line(line, display_row, font_id, force_pad)

    def send_line_to_arduino2(self, y_position: int, font_id: int, line: str,
                              command_to_send: int = None):
        """Send a line at a specific Y position"""
        from config import CMD_WRITE_TEXT
        if command_to_send is None:
            command_to_send = CMD_WRITE_TEXT
        self._screen._send_line_raw(y_position, font_id, line, command_to_send)

    def send_new_screen_lines_to_arduino(self, lines_to_print: list[str],
                                         font_id: int, force_redraw: bool = False):
        """Send new lines to screen with optimization"""
        self._screen.send_new_lines(lines_to_print, font_id, force_redraw)

    def re_send_screen_lines_to_arduino(self, font_id: int):
        """Resend all visible lines"""
        self._screen.resend_screen(font_id)

    def send_using_serial_to_duino(self, cmd: bytes):
        """Send raw bytes to Arduino"""
        self._arduino.send(cmd)

    def wait_for_screen_update_ready(self, caller: str, timeout: float = 1.0) -> bool:
        """Wait for Arduino ready signal"""
        return self._arduino.wait_for_ready(timeout)

    def get_command_from_keyboard(self, font_id: int, keyboard_handler: KeyboardHandler):
        """
        Wait for user to type command, return command string or action.

        Args:
            font_id: Current font ID
            keyboard_handler: KeyboardHandler instance

        Returns:
            dict with either:
            - {"type": "command", "value": str}
            - {"action": str, ...}
        """
        command = ""

        while True:
            Utilities.delay_to_not_bog_cpu()

            # Read all available packets
            packets = self._arduino.read_all_packets()

            if (len(packets) > 0):
                Utilities.print_with_indent_and_log_level(f"Packets: {packets}", 1)

            for packet in packets:

                Utilities.print_with_indent_and_log_level(f"Received packet: {packet}", 2)
                ptype = packet.get('type')

                if ptype == 'line':
                    # Complete line from buffered input
                    return {"type": "command", "value": packet['data']}

                elif ptype == 'key':
                    key = packet['key']
                    Utilities.print_with_indent(f"Key received: 0x{key:02X}")

                    # Process key through handler
                    result = keyboard_handler.process_key(key)

                    if result is None:
                        # Modifier key, ignore
                        continue

                    elif isinstance(result, dict):
                        # Action to execute
                        if result.get("action") == "enter":
                            return {"type": "command", "value": command}

                        elif result.get("action") == "backspace":
                            if len(command) > 0:
                                command = command[:-1]
                                self.update_prompt(command + " ", font_id)

                        else:
                            # Return action (font change, clear, etc)
                            return result

                    elif isinstance(result, str):
                        # Regular character
                        command += result
                        self.update_prompt(command + " ", font_id)

                elif ptype == 'debug':
                    Utilities.print_with_indent(f"[DUINO DEBUG] {packet['message']}")

                elif ptype == 'ready':
                    Utilities.print_with_indent_and_log_level("Received READY", 3)

                elif ptype == 'error':
                    Utilities.print_with_indent(f"[PROTOCOL ERROR] {packet}")

                elif ptype == 'unknown':
                    Utilities.print_with_indent(
                        f"Unknown byte: 0x{packet['byte']:02X} ({packet['ascii']})")

    def process_pending_serial(self, key_buffer: list = None) -> bool:
        """
        Process pending serial data (backward compatibility).

        Args:
            key_buffer: Optional list to append received keys to

        Returns:
            True if ready signal was received
        """
        if key_buffer is None:
            key_buffer = []

        found_ready = False

        packets = self._arduino.read_all_packets()

        for packet in packets:
            ptype = packet.get('type')

            if ptype == 'ready':
                Utilities.print_with_indent_and_log_level(
                    "Received CMD_READY_FOR_NEXT_COMMAND", 2)
                found_ready = True

            elif ptype == 'key':
                key_buffer.append(packet['key'])

            elif ptype == 'line':
                key_buffer.append(LINE_START_MARKER)
                key_buffer.append(packet['data'])

            elif ptype == 'debug':
                Utilities.print_with_indent(f"[DUINO SENT] {packet['message']}")

            elif ptype == 'error':
                Utilities.print_with_indent(f"[ERROR] {packet}")

        return found_ready

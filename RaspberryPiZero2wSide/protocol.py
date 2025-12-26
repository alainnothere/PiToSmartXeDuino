"""
Protocol packet parser for Smart Response XE Terminal

This module provides a non-blocking state machine parser for incoming
serial data from the Arduino. Instead of blocking reads, bytes are fed
one at a time and complete packets are returned when ready.

PACKET TYPES:
=============

1. Ready Signal:
   [0xFC]
   Arduino signals it's ready for the next command.

2. Single Key Packet:
   [0xFD] [KEY] [CHECKSUM] [0xFE]
   CHECKSUM = 0xFD ^ KEY
   Used for special keys and when line buffering is disabled.

3. Line Input Packet:
   [0xF8] [LENGTH] [DATA...] [CHECKSUM] [0xF9]
   CHECKSUM = 0xF8 ^ LENGTH ^ (XOR of all data bytes)
   Used for buffered line input (user typed a complete line).

4. Debug Packet:
   [0xFA] [DATA...] [0xFB]
   Debug messages from Arduino for development.

5. Padding:
   [0xFF]
   No-op byte, ignored.
"""
import utilities
from config import (
    CMD_READY_FOR_NEXT_COMMAND,
    CMD_PADDING_MARKER,
    KEY_START_MARKER,
    KEY_END_MARKER,
    LINE_START_MARKER,
    LINE_END_MARKER,
    DEBUG_START_MARKER,
    DEBUG_END_MARKER,
)


class PacketParser:
    """
    Non-blocking state machine parser for Arduino packets.

    Usage:
        parser = PacketParser()

        while serial.in_waiting > 0:
            byte = serial.read(1)[0]
            packet = parser.feed(byte)
            if packet:
                handle_packet(packet)
    """

    # Parser states
    STATE_IDLE = 'IDLE'
    STATE_KEY_WAIT_DATA = 'KEY_WAIT_DATA'
    STATE_KEY_WAIT_CHECKSUM = 'KEY_WAIT_CHECKSUM'
    STATE_KEY_WAIT_END = 'KEY_WAIT_END'
    STATE_LINE_WAIT_LENGTH = 'LINE_WAIT_LENGTH'
    STATE_LINE_WAIT_DATA = 'LINE_WAIT_DATA'
    STATE_LINE_WAIT_CHECKSUM = 'LINE_WAIT_CHECKSUM'
    STATE_LINE_WAIT_END = 'LINE_WAIT_END'
    STATE_DEBUG_WAIT_DATA = 'DEBUG_WAIT_DATA'

    def __init__(self):
        self.state = self.STATE_IDLE
        self.buffer = bytearray()
        self.expected_length = 0
        self.key_byte = 0
        self.checksum_byte = 0

    def reset(self):
        """Reset parser to idle state"""
        self.state = self.STATE_IDLE
        self.buffer.clear()
        self.expected_length = 0
        self.key_byte = 0
        self.checksum_byte = 0

    def feed(self, byte):
        """
        Feed a single byte to the parser.

        Args:
            byte: Integer 0-255

        Returns:
            dict with packet info if a complete packet was parsed, None otherwise.

            Packet types returned:
            - {'type': 'ready'}
            - {'type': 'key', 'key': int}
            - {'type': 'line', 'data': str}
            - {'type': 'debug', 'message': str}
            - {'type': 'error', 'reason': str}
        """

        utilities.Utilities.print_with_indent_and_log_level(f"Received 0x{byte:02x} while state is {self.state}", 1)

        # IDLE state - waiting for start of packet
        if self.state == self.STATE_IDLE:
            return self._handle_idle(byte)

        # KEY packet states
        elif self.state == self.STATE_KEY_WAIT_DATA:
            self.key_byte = byte
            self.state = self.STATE_KEY_WAIT_CHECKSUM
            return None

        elif self.state == self.STATE_KEY_WAIT_CHECKSUM:
            self.checksum_byte = byte
            self.state = self.STATE_KEY_WAIT_END
            return None

        elif self.state == self.STATE_KEY_WAIT_END:
            self.state = self.STATE_IDLE
            if byte == KEY_END_MARKER:
                expected_checksum = KEY_START_MARKER ^ self.key_byte
                if self.checksum_byte == expected_checksum:
                    return {'type': 'key', 'key': self.key_byte}
                else:
                    return {'type': 'error', 'reason': 'key_checksum_fail', 'key': self.key_byte}
            else:
                return {'type': 'error', 'reason': 'key_end_marker_missing'}

        # LINE packet states
        elif self.state == self.STATE_LINE_WAIT_LENGTH:
            self.expected_length = byte
            self.buffer.clear()
            if self.expected_length == 0:
                self.state = self.STATE_LINE_WAIT_CHECKSUM
            else:
                self.state = self.STATE_LINE_WAIT_DATA
            return None

        elif self.state == self.STATE_LINE_WAIT_DATA:
            self.buffer.append(byte)
            if len(self.buffer) >= self.expected_length:
                self.state = self.STATE_LINE_WAIT_CHECKSUM
            return None

        elif self.state == self.STATE_LINE_WAIT_CHECKSUM:
            self.checksum_byte = byte
            self.state = self.STATE_LINE_WAIT_END
            return None

        elif self.state == self.STATE_LINE_WAIT_END:
            self.state = self.STATE_IDLE
            if byte == LINE_END_MARKER:
                # Calculate expected checksum
                expected_checksum = LINE_START_MARKER ^ self.expected_length
                for b in self.buffer:
                    expected_checksum ^= b

                if self.checksum_byte == expected_checksum:
                    try:
                        data = self.buffer.decode('ascii')
                        return {'type': 'line', 'data': data}
                    except UnicodeDecodeError:
                        return {'type': 'error', 'reason': 'line_decode_fail'}
                else:
                    return {'type': 'error', 'reason': 'line_checksum_fail'}
            else:
                return {'type': 'error', 'reason': 'line_end_marker_missing'}

        # DEBUG packet state
        elif self.state == self.STATE_DEBUG_WAIT_DATA:
            if byte == DEBUG_END_MARKER:
                self.state = self.STATE_IDLE
                try:
                    message = self.buffer.decode('utf-8')
                    self.buffer.clear()
                    return {'type': 'debug', 'message': message}
                except UnicodeDecodeError:
                    response = self.buffer.hex()
                    self.buffer.clear()
                    return {'type': 'debug', 'message': f'[decode error] {response}'}
            else:
                self.buffer.append(byte)
                return None

        # Unknown state - reset
        else:
            self.reset()
            return {'type': 'error', 'reason': 'unknown_state'}

    def _handle_idle(self, byte):
        """Handle byte in IDLE state"""

        if byte == CMD_READY_FOR_NEXT_COMMAND:
            return {'type': 'ready'}

        elif byte == KEY_START_MARKER:
            self.state = self.STATE_KEY_WAIT_DATA
            return None

        elif byte == LINE_START_MARKER:
            self.state = self.STATE_LINE_WAIT_LENGTH
            return None

        elif byte == DEBUG_START_MARKER:
            self.state = self.STATE_DEBUG_WAIT_DATA
            if len(self.buffer) > 0:
                try:
                    message = self.buffer.decode('utf-8')
                    self.buffer.clear()
                    return {'type': 'debug', 'message': message}
                except UnicodeDecodeError:
                    response = self.buffer.hex()
                    self.buffer.clear()
                    return {'type': 'debug', 'message': f'[decode error] {response}'}

            self.buffer.clear()
            return None

        elif byte == CMD_PADDING_MARKER:
            # Padding byte, ignore
            return None

        else:
            # Unknown byte in idle state
            ascii_char = chr(byte) if 32 <= byte <= 126 else '.'
            return {'type': 'unknown', 'byte': byte, 'ascii': ascii_char}

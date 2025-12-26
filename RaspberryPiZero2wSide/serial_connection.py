"""
Low-level serial connection to Arduino

This module handles the raw serial communication with the Arduino,
including the signal pin handshaking for soft serial mode.
"""

import time
import serial
import pigpio

from config import (
    BAUD_RATE_SOFT_SERIAL,
    BAUD_RATE_HARDWARE_SERIAL,
    USING_SOFT_SERIAL,
    TIMEOUT_WAITING_FOR_SIGNAL_TO_TRANSFER,
    SIGNAL_PIN_NUMBER_ON_GPIO_NUMBERING,
)
from protocol import PacketParser
from utilities import Utilities


class ArduinoSerial:
    """
    Low-level serial connection to Arduino with signal pin handshaking.

    In soft serial mode, the Arduino uses a signal pin to indicate when
    it's ready to receive data. This class handles waiting for that signal
    before sending.
    """

    def __init__(self, serial_port: str):
        """
        Initialize serial connection.

        Args:
            serial_port: Serial port path (e.g., '/dev/ttyAMA0')
        """
        self._pi = pigpio.pi()

        if USING_SOFT_SERIAL:
            self._ser = serial.Serial(serial_port, baudrate=BAUD_RATE_SOFT_SERIAL)
        else:
            self._ser = serial.Serial(serial_port, baudrate=BAUD_RATE_HARDWARE_SERIAL)

        self._parser = PacketParser()

    def close(self):
        """Close serial connection and GPIO"""
        if self._ser:
            self._ser.close()
        if self._pi:
            self._pi.stop()

    @property
    def in_waiting(self) -> int:
        """Number of bytes waiting to be read"""
        return self._ser.in_waiting

    def send(self, data: bytes) -> bool:
        """
        Send data to Arduino.

        In soft serial mode, waits for the signal pin to go LOW before sending.

        Args:
            data: Bytes to send

        Returns:
            True if sent successfully, False if timeout waiting for signal
        """
        if USING_SOFT_SERIAL:
            start_time = time.time()

            while True:
                elapsed = time.time() - start_time

                if elapsed >= TIMEOUT_WAITING_FOR_SIGNAL_TO_TRANSFER:
                    Utilities.print_with_indent_and_log_level(
                        "TIMEOUT waiting to send message to duino", 2)
                    return False

                signal_line = self._pi.read(SIGNAL_PIN_NUMBER_ON_GPIO_NUMBERING)
                if signal_line == 0:
                    self._ser.write(data)
                    Utilities.print_with_indent_and_log_level("SENT message to duino using soft serial", 2)
                    return True

                # Small delay to avoid busy-waiting
                time.sleep(0.0001)
        else:
            self._ser.write(data)
            return True

    def read_packet(self):
        """
        Read and parse a single packet if data is available.

        Returns:
            Parsed packet dict, or None if no complete packet available.

            Packet types:
            - {'type': 'ready'}
            - {'type': 'key', 'key': int}
            - {'type': 'line', 'data': str}
            - {'type': 'debug', 'message': str}
            - {'type': 'error', 'reason': str}
            - {'type': 'unknown', 'byte': int}
        """
        while self._ser.in_waiting > 0:
            byte = self._ser.read(1)[0]
            packet = self._parser.feed(byte)
            if packet:
                return packet
        return None

    def read_all_packets(self) -> list:
        """
        Read and parse all available packets.

        Returns:
            List of parsed packet dicts
        """
        packets = []
        while True:
            packet = self.read_packet()
            if packet is None:
                break
            packets.append(packet)
        return packets

    def wait_for_ready(self, timeout: float = 1.0, process_callback=None) -> bool:
        """
        Wait for Arduino ready signal.

        Args:
            timeout: Maximum time to wait in seconds
            process_callback: Optional callback(packet) for non-ready packets

        Returns:
            True if ready signal received, False if timeout
        """
        start_time = time.time()

        while True:
            if time.time() - start_time > timeout:
                Utilities.print_with_indent_and_log_level(
                    "[WARNING]: timeout waiting for ready signal!", 4)
                return False

            packet = self.read_packet()

            if packet:
                if packet['type'] == 'ready':
                    elapsed = time.time() - start_time
                    Utilities.print_with_indent_and_log_level(
                        f"Receive READY, took: {elapsed:.4f} seconds", 4)
                    return True
                if packet['type'] == 'debug':
                    Utilities.print_with_indent(f"[DUINO DEBUG] {packet['message']}")
                elif process_callback:
                    process_callback(packet)

            Utilities.delay_to_not_bog_cpu()

    def flush_input(self):
        """Flush any pending input data"""
        self._ser.reset_input_buffer()

    def flush_output(self):
        """Flush any pending output data"""
        self._ser.reset_output_buffer()

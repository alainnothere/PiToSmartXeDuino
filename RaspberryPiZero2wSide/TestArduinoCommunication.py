"""
Unit tests for Smart Response XE Terminal communication

Tests the screen update logic, scroll optimization, and line comparison.
"""

import unittest
from unittest.mock import MagicMock, patch, call
import sys

# Mock hardware dependencies before importing
sys.modules['pigpio'] = MagicMock()
sys.modules['serial'] = MagicMock()

from config import FONT_CONFIGURATION, PROMPT, TERMINAL_HISTORY_ROWS
from protocol import PacketParser


class MockArduinoSerial:
    """Mock for ArduinoSerial to avoid hardware dependencies"""

    def __init__(self, port):
        self._ser = MagicMock()

    def send(self, data):
        return True

    def wait_for_ready(self, timeout=1.0, process_callback=None):
        return True

    def read_all_packets(self):
        return []


class TestScreenController(unittest.TestCase):
    """Test the screen controller logic"""

    def setUp(self):
        # Patch ArduinoSerial before importing ScreenController
        with patch('serial_connection.ArduinoSerial', MockArduinoSerial):
            from screen_controller import ScreenController
            self.mock_serial = MockArduinoSerial("/dev/fake")
            self.screen = ScreenController(self.mock_serial)

        # Mock the methods we want to track
        self.screen.scroll_screen_up = MagicMock()
        self.screen.send_line = MagicMock()
        self.screen._lines = []

    def test_scroll_logic_with_new_lines(self):
        """Test that scrolling works correctly with fewer new lines than screen rows"""
        # Font 2 (MEDIUM): 32 cols, 8 rows visible, 17px per row
        font_id = 2
        font_config = FONT_CONFIGURATION[font_id]

        self.screen._lines = ["Old Line 1"]
        new_lines = ["New Line A", "New Line B"]

        self.screen.send_new_lines(new_lines, font_id=font_id)

        # 2 new lines * 17px height = 34px
        expected_scroll = font_config[3] * 2
        self.screen.scroll_screen_up.assert_called_once_with(expected_scroll)

        # Verify 2 lines were sent (Line A and Line B)
        self.assertEqual(self.screen.send_line.call_count, 2)

    def test_send_just_one_different_line(self):
        """Test that only changed lines are sent when screen is full"""
        font_id = 2

        self.screen._lines = [
            'sddET39uU8237088',
            'z2345678901234567890123456789012',
            '34567890123456789012345678901234',
            'CMD> a',
            '/bin/bash: line 1: a: command no',
            't found',
            'CMD> ls',
            'a.out',
            'backupOriginalProgram',
            'bla.py',
            'clockDetection.py',
            'communicationTestUsing3Wires.py',
            'e-Paper',
            'oldFilesBackup',
            'piToDuino',
            'pythonblabla.py',
            'pythonblabla.py.bak.working',
            'pythonblabla.py.bakWorks',
            'pythonblabla.py.bak.worksButIThi',
            'nkItsCountingNoise',
            'python-cc1101',
            'raspiGpioLogs',
            'runcProgram.sh',
            '0d-s82j-sjdk7.ino.hex',
            'sync_serial',
            'sync_serial_gpio_slave.c',
            'sddETBin',
            'sddET39uU8237088',
            'z2345678901234567890123456789012',
            '34567890123456789012345678901234'
        ]

        new_lines = [
            'CMD> ls',
            'a.out',
            'backupOriginalProgram',
            'bla.py',
            'clockDetection.py',
            'communicationTestUsing3Wires.py',
            'e-Paper',
            'oldFilesBackup',
            'piToDuino',
            'pythonblabla.py',
            'pythonblabla.py.bak.working',
            'pythonblabla.py.bakWorks',
            'pythonblabla.py.bak.worksButIThi',
            'nkItsCountingNoise',
            'python-cc1101',
            'raspiGpioLogs',
            'runcProgram.sh',
            '0d-s82j-sjdk7.ino.hex',
            'sync_serial',
            'sync_serial_gpio_slave.c',
            'sddETBin',
            'sddET39uU8237088',
            'I am a different line',  # This line is different
            '34567890123456789012345678901234'
        ]

        self.screen.send_new_lines(new_lines, font_id=font_id)

        # Should only call send_line for the different line
        self.screen.send_line.assert_called_once_with(
            'I am a different line', 5, font_id)

    def test_no_line_is_sent_when_they_are_the_same(self):
        """Test that no lines are sent when content is identical"""
        font_id = 2

        self.screen._lines = [
            'sddET39uU8237088',
            'z2345678901234567890123456789012',
            '34567890123456789012345678901234',
            'CMD> a',
            '/bin/bash: line 1: a: command no',
            't found',
            'CMD> ls',
            'a.out',
            'backupOriginalProgram',
            'bla.py',
            'clockDetection.py',
            'communicationTestUsing3Wires.py',
            'e-Paper',
            'oldFilesBackup',
            'piToDuino',
            'pythonblabla.py',
            'pythonblabla.py.bak.working',
            'pythonblabla.py.bakWorks',
            'pythonblabla.py.bak.worksButIThi',
            'nkItsCountingNoise',
            'python-cc1101',
            'raspiGpioLogs',
            'runcProgram.sh',
            '0d-s82j-sjdk7.ino.hex',
            'sync_serial',
            'sync_serial_gpio_slave.c',
            'sddETBin',
            'sddET39uU8237088',
            'z2345678901234567890123456789012',
            '34567890123456789012345678901234'
        ]

        new_lines = [
            'CMD> ls',
            'a.out',
            'backupOriginalProgram',
            'bla.py',
            'clockDetection.py',
            'communicationTestUsing3Wires.py',
            'e-Paper',
            'oldFilesBackup',
            'piToDuino',
            'pythonblabla.py',
            'pythonblabla.py.bak.working',
            'pythonblabla.py.bakWorks',
            'pythonblabla.py.bak.worksButIThi',
            'nkItsCountingNoise',
            'python-cc1101',
            'raspiGpioLogs',
            'runcProgram.sh',
            '0d-s82j-sjdk7.ino.hex',
            'sync_serial',
            'sync_serial_gpio_slave.c',
            'sddETBin',
            'sddET39uU8237088',
            'z2345678901234567890123456789012',
            '34567890123456789012345678901234'
        ]

        self.screen.send_new_lines(new_lines, font_id=font_id)

        self.screen.send_line.assert_not_called()

    def test_scroll_and_print_all_lines(self):
        """Test scrolling with a few new lines"""
        font_id = 2
        font_config = FONT_CONFIGURATION[font_id]

        self.screen._lines = []

        new_lines = [
            'CMD> a',
            '/bin/bash: line 1: a: command no',
            't found',
        ]

        self.screen.send_new_lines(new_lines, font_id=font_id)

        # CMD> a starts with PROMPT so it's skipped
        # Should print 2 lines
        expected_calls = [
            call('t found', 6, font_id),
            call('/bin/bash: line 1: a: command no', 5, font_id),
        ]
        self.screen.send_line.assert_has_calls(expected_calls, any_order=False)
        self.assertEqual(self.screen.send_line.call_count, 2)

        # Should scroll by 3 lines * 17px = 51px
        expected_scroll = font_config[3] * 3
        self.screen.scroll_screen_up.assert_called_once_with(expected_scroll)

    def test_scroll_and_print_all_lines_more_than_screen(self):
        """Test when more lines than screen rows - no scroll, just overwrite"""
        font_id = 2
        font_config = FONT_CONFIGURATION[font_id]
        rows_in_screen = font_config[2] - 1  # 8 - 1 = 7

        self.screen._lines = []

        new_lines = [
            'CMD> a',
            '/bin/bash: line 1: a: command no',
            't found',
            'CMD> a',
            '/bin/bash: line 1: a: command no',
            't found',
            '/bin/bash: line 1: a: command no',
            't found',
            '/bin/bash: line 1: a: command no',
            't found',
            '/bin/bash: line 1: a: command no',
            't found',
            '/bin/bash: line 1: a: command no',
            't found',
        ]

        self.screen.send_new_lines(new_lines, font_id=font_id)

        # Should print 7 lines (rows_in_screen)
        expected_calls = [
            call('t found', 6, font_id),
            call('/bin/bash: line 1: a: command no', 5, font_id),
            call('t found', 4, font_id),
            call('/bin/bash: line 1: a: command no', 3, font_id),
            call('t found', 2, font_id),
            call('/bin/bash: line 1: a: command no', 1, font_id),
            call('t found', 0, font_id),
        ]
        self.screen.send_line.assert_has_calls(expected_calls, any_order=False)
        self.assertEqual(self.screen.send_line.call_count, 7)

        # Should NOT scroll when replacing entire screen
        self.screen.scroll_screen_up.assert_not_called()

    def test_scroll_and_print_with_existing_lines(self):
        """Test full screen replacement when buffer already has content"""
        font_id = 2

        self.screen._lines = [
            'bla',
            'more bla',
            'even more bla',
        ]

        new_lines = [
            'CMD> a',
            '/bin/bash: line 1: a: command no',
            't found',
            'CMD> a',
            '/bin/bash: line 1: a: command no',
            't found',
            '/bin/bash: line 1: a: command no',
            't found',
            '/bin/bash: line 1: a: command no',
            't found',
            '/bin/bash: line 1: a: command no',
            't found',
            '/bin/bash: line 1: a: command no',
            't found',
        ]

        self.screen.send_new_lines(new_lines, font_id=font_id)

        # Should print 7 lines
        expected_calls = [
            call('t found', 6, font_id),
            call('/bin/bash: line 1: a: command no', 5, font_id),
            call('t found', 4, font_id),
            call('/bin/bash: line 1: a: command no', 3, font_id),
            call('t found', 2, font_id),
            call('/bin/bash: line 1: a: command no', 1, font_id),
            call('t found', 0, font_id),
        ]
        self.screen.send_line.assert_has_calls(expected_calls, any_order=False)
        self.assertEqual(self.screen.send_line.call_count, 7)

        # Should NOT scroll when replacing entire screen
        self.screen.scroll_screen_up.assert_not_called()


class TestPacketParser(unittest.TestCase):
    """Test the protocol packet parser"""

    def setUp(self):
        self.parser = PacketParser()

    def test_ready_signal(self):
        """Test parsing ready signal"""
        packet = self.parser.feed(0xFC)
        self.assertEqual(packet, {'type': 'ready'})

    def test_padding_ignored(self):
        """Test that padding bytes are ignored"""
        packet = self.parser.feed(0xFF)
        self.assertIsNone(packet)

    def test_key_packet(self):
        """Test parsing key packet"""
        # Send start marker
        self.assertIsNone(self.parser.feed(0xFD))
        # Send key
        self.assertIsNone(self.parser.feed(0x41))  # 'A'
        # Send checksum (0xFD ^ 0x41 = 0xBC)
        self.assertIsNone(self.parser.feed(0xBC))
        # Send end marker
        packet = self.parser.feed(0xFE)

        self.assertEqual(packet, {'type': 'key', 'key': 0x41})

    def test_key_packet_bad_checksum(self):
        """Test key packet with bad checksum"""
        self.parser.feed(0xFD)  # Start
        self.parser.feed(0x41)  # Key
        self.parser.feed(0x00)  # Bad checksum
        packet = self.parser.feed(0xFE)  # End

        self.assertEqual(packet['type'], 'error')
        self.assertEqual(packet['reason'], 'key_checksum_fail')

    def test_line_packet(self):
        """Test parsing line input packet"""
        # Start marker
        self.assertIsNone(self.parser.feed(0xF8))
        # Length = 5
        self.assertIsNone(self.parser.feed(5))
        # Data: "hello"
        for c in b'hello':
            self.assertIsNone(self.parser.feed(c))
        # Checksum: 0xF8 ^ 5 ^ ord('h') ^ ord('e') ^ ord('l') ^ ord('l') ^ ord('o')
        checksum = 0xF8 ^ 5
        for c in b'hello':
            checksum ^= c
        self.assertIsNone(self.parser.feed(checksum))
        # End marker
        packet = self.parser.feed(0xF9)

        self.assertEqual(packet, {'type': 'line', 'data': 'hello'})

    def test_line_packet_empty(self):
        """Test parsing empty line packet"""
        self.parser.feed(0xF8)  # Start
        self.parser.feed(0)  # Length = 0
        checksum = 0xF8 ^ 0  # Checksum for empty data
        self.parser.feed(checksum)
        packet = self.parser.feed(0xF9)  # End

        self.assertEqual(packet, {'type': 'line', 'data': ''})

    def test_debug_packet(self):
        """Test parsing debug packet"""
        self.parser.feed(0xFA)  # Start
        for c in b'debug msg':
            self.parser.feed(c)
        packet = self.parser.feed(0xFB)  # End

        self.assertEqual(packet, {'type': 'debug', 'message': 'debug msg'})

    def test_unknown_byte(self):
        """Test unknown byte in idle state"""
        packet = self.parser.feed(0x42)  # Random byte

        self.assertEqual(packet['type'], 'unknown')
        self.assertEqual(packet['byte'], 0x42)

    def test_parser_reset(self):
        """Test that parser can be reset mid-packet"""
        self.parser.feed(0xFD)  # Start key packet
        self.parser.feed(0x41)  # Key
        # Don't finish packet, reset instead
        self.parser.reset()

        # Should be back in IDLE state
        packet = self.parser.feed(0xFC)  # Ready signal
        self.assertEqual(packet, {'type': 'ready'})

    def test_multiple_packets_in_sequence(self):
        """Test parsing multiple packets in sequence"""
        # First packet: ready
        p1 = self.parser.feed(0xFC)
        self.assertEqual(p1['type'], 'ready')

        # Second packet: key
        self.parser.feed(0xFD)
        self.parser.feed(0x41)
        self.parser.feed(0xBC)  # 0xFD ^ 0x41
        p2 = self.parser.feed(0xFE)
        self.assertEqual(p2['type'], 'key')

        # Third packet: ready again
        p3 = self.parser.feed(0xFC)
        self.assertEqual(p3['type'], 'ready')


class TestKeyboardHandler(unittest.TestCase):
    """Test the keyboard handler"""

    def setUp(self):
        from keyboard_handler import KeyboardHandler
        self.handler = KeyboardHandler()

    def test_regular_character(self):
        """Test regular printable character"""
        result = self.handler.process_key(ord('a'))
        self.assertEqual(result, 'a')

    def test_enter_key(self):
        """Test DEL as Enter"""
        result = self.handler.process_key(0x08)
        self.assertEqual(result, {"action": "enter"})

    def test_backspace_key(self):
        """Test 0x7F as backspace"""
        result = self.handler.process_key(0x7F)
        self.assertEqual(result, {"action": "backspace"})

    def test_shift_backspace(self):
        """Test Shift + DEL as backspace"""
        # First send shift modifier
        result1 = self.handler.process_key(0x10)  # KEY_MODIFIER_SHIFT
        self.assertIsNone(result1)

        # Then send DEL
        result2 = self.handler.process_key(0x08)
        self.assertEqual(result2, {"action": "backspace"})

    def test_shift_font_change(self):
        """Test Shift + number for font change"""
        # Shift + 0
        self.handler.process_key(0x10)
        result = self.handler.process_key(ord('0'))
        self.assertEqual(result, {"action": "font_change", "font": 0})

        # Shift + 2
        self.handler.process_key(0x10)
        result = self.handler.process_key(ord('2'))
        self.assertEqual(result, {"action": "font_change", "font": 2})

    def test_sym_clear(self):
        """Test Sym + C for clear buffer"""
        self.handler.process_key(0x11)  # KEY_MODIFIER_SYM
        result = self.handler.process_key(ord('c'))
        self.assertEqual(result, {"action": "clear_buffer"})

    def test_modifier_resets_after_use(self):
        """Test that modifier state resets after one key"""
        # Activate shift
        self.handler.process_key(0x10)
        # Use it with a key
        self.handler.process_key(ord('a'))

        # Next key should be normal (not shifted)
        result = self.handler.process_key(0x08)  # DEL
        self.assertEqual(result, {"action": "enter"})  # Not backspace


if __name__ == '__main__':
    unittest.main()

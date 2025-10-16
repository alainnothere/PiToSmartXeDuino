#!/usr/bin/env python3
"""
Smart Response XE Terminal Client

This Python program runs on a Raspberry Pi and uses an Arduino with a
Smart Response XE as a hardware terminal (keyboard + display).

ARCHITECTURE OVERVIEW:

1. PTY (Pseudo-Terminal):
   - Creates a virtual terminal where commands run
   - Dimensions match the current font size
   - Captures terminal output including VT100 escape sequences

2. Screen Buffer (17 rows × 64 cols max):
   - Maintains a scrolling buffer of terminal output
   - Always 17 rows tall (expandable to 100+ for history in future)
   - Width = 64 cols (largest font), filled based on current font's PTY width
   - Row 16 (bottom): Always the command prompt
   - Rows 0-15: Scrolling output (newest at bottom, oldest at top)

3. Font System:
   Font 0 (NORMAL): 52 cols × 17 rows visible
   Font 1 (SMALL):  64 cols × 17 rows visible
   Font 2 (MEDIUM): 42 cols × 8 rows visible (shows buffer rows 9-16)
   Font 3 (LARGE):  35 cols × 8 rows visible (shows buffer rows 9-16)

   Buffer behavior:
   - PTY runs at font's column width (52, 64, 42, or 35 cols)
   - Output fills leftmost N columns of buffer (rest empty)
   - Arduino receives only what the font can display:
     * Fonts 0,1: All 17 rows, leftmost N columns
     * Fonts 2,3: Last 8 rows (9-16), leftmost N columns

   When switching fonts:
   - Font 3→Font 1: Previously hidden rows 0-8 become visible
   - Font 1→Font 3: Rows 0-8 stay in buffer but go off-screen
   - PTY is recreated with new dimensions
   - Screen is redrawn

KEYBOARD HANDLING:

Regular keys: Added to command buffer
Modifier sequences (Shift/Sym + key): Trigger actions
- Shift+0/1/2/3: Switch fonts
- Shift+DEL: Backspace
- Sym+C: Clear screen
- DEL alone: Enter (execute command)

Actions return:
- None: Modifier key (ignore)
- str: Regular character (add to command)
- dict: Action to execute (font change, clear, etc)

COMMUNICATION PROTOCOL:

Arduino → Pi:
- Keyboard packet: [0xFD] [KEY] [CHECKSUM] [0xFE]
- Modifier packet: Two packets sent in sequence
- Ready signal: [0xFC] (ready for next command)
- Completion: [0xFF] [0xFF] (command processed)

Pi → Arduino:
- Clear screen: [0x01]
- Write text: [0x02] [X] [Y] [FONT] [FG] [BG] [LENGTH] [TEXT...]

SCREEN LAYOUT:

Physical display orientation (row numbers increase top to bottom):
Row 0  ← TOP (oldest visible content)
Row 1
Row 2
...
Row 15 ← Most recent command output appears here
Row 16 ← BOTTOM (command prompt, where user types)

Scrolling behavior:
- When new output arrives, it appears at row 15
- Existing content scrolls UP (toward row 0)
- Content that scrolls above row 0 stays in buffer but becomes invisible
- Larger fonts (2,3) only show rows 9-16 (8 rows total)
- Smaller fonts (0,1) show all rows 0-16 (17 rows total)

Example command flow:
1. User types at row 16: "pwd"
2. User presses DEL (enter)
3. Command executes, output "> pwd" appears at row 15
4. Command result "/home/user" appears at row 14
5. Prompt returns to row 16
6. Next command output scrolls everything up:
   - "/home/user" moves to row 15
   - "> pwd" moves to row 14
   - New output appears at row 15
"""

import serial
import struct
import time
import pyte

from keyboardHandler import KeyboardHandler
from screenBuffer import ScreenBuffer, fontConfiguration
from terminalBuffer import TerminalBuffer

from serialCommunicationsToArduino import SerialCommunicationToArduino, CMD_CLEAR_SCREEN, CMD_WRITE_CHAR, CMD_SCROLL_UP
from utilities import Utilities

# Configuration
SERIAL_PORT = '/dev/ttyAMA0'
BAUD_RATE = 115200
VERTICAL_SCREEN_SIZE = 136


def send_line_to_arduino(ser, line, physical_row, display_row, font_id, force_trim=False):
    """
    Send a single line to Arduino
    physical_row: Row number in buffer (0-16)
    display_row: Row number on display (0-7 or 0-16 depending on font)
    """
    font_config = fontConfiguration[font_id]
    font_cols = font_config[1]

    # Ensure line is exactly font_cols wide
    if force_trim:
        line = line[:font_cols].ljust(font_cols).strip()
    else:
        line = line[:font_cols].ljust(font_cols)

    text_bytes = line.encode('ascii', errors='replace')

    # check the comment on the fontConfiguration to understand why we need to pad for the location
    y = display_row * font_config[3] + font_config[4]

    length = len(text_bytes)

    cmd = struct.pack('>B', CMD_WRITE_CHAR)
    cmd += struct.pack('>H', 0)  # X = 0
    cmd += struct.pack('>H', y)  # Y = display_row * pixels_per_row
    cmd += struct.pack('>B', font_id)
    cmd += struct.pack('>B', 3)  # FG white
    cmd += struct.pack('>B', 0)  # BG black
    cmd += struct.pack('>H', length)
    cmd += text_bytes

    print(f"To Arduino: Y: {y}, length: {length}, text: {line}\n")

    ser.write(cmd)
    SerialCommunicationToArduino.wait_for_ready(ser)


def send_screen_to_arduino(ser, screen_buffer, font_id, num_new_lines=0, force_full_redraw=False):
    """
    Send screen to Arduino, using scroll optimization when possible

    Returns:
        new_scroll_pixels: Updated scroll position after this operation
    """

    # there is always at least one line to update, and that's the prompt, so num_new_lines will always be at least 2
    # because as this is configured there is at least one response for every command
    num_new_lines = num_new_lines + 1

    # this will get the lines we will print to the screen as well as the "starting position" or the
    # row where we start for this particular font
    start_row, lines = screen_buffer.get_lines_for_font(font_id)

    pixels_per_row = fontConfiguration[font_id][3]
    visible_rows = fontConfiguration[font_id][2]

    if force_full_redraw:
        print(f"Force Full Redraw: clearing screen, start_row: {start_row}")
        clear_screen(ser)

        for display_row, line in enumerate(lines):
            physical_row = start_row + display_row
            send_line_to_arduino(ser, line, physical_row, display_row, font_id, force_trim=True)
    else:
        if num_new_lines >= visible_rows - 1:
            print(f"Force Full Redraw: clearing screen, start_row: {start_row}")
            clear_screen(ser)

            for display_row, line in enumerate(lines):
                physical_row = start_row + display_row
                send_line_to_arduino(ser, line, physical_row, display_row, font_id, force_trim=True)

        else:
            # Scroll and send new lines
            scroll_pixels_needed = num_new_lines * pixels_per_row
            scroll_screen_up(ser, scroll_pixels_needed)
            print(
                f"Scrolling up: start_row: {start_row}, font_id: {font_id}, scroll_pixels_needed: {scroll_pixels_needed}, num_new_lines: {num_new_lines}, pixels_per_row: {pixels_per_row}")

            # Send new lines at bottom
            for display_row, line in enumerate(lines):
                physical_row = start_row + display_row
                if physical_row > visible_rows - num_new_lines - 1 - 1:
                    send_line_to_arduino(ser, line, physical_row, display_row, font_id)


def scroll_screen_up(ser, scroll_pixels):
    """
    Scroll the Arduino screen up by specified number of rows

    Args:
        num_rows: Number of rows to scroll
        font_id: Current font (to calculate pixels per row)

    Returns:
        True if successful, False on timeout
    """
    # Send scroll command: [CMD] [PIXELS_high] [PIXELS_low]
    cmd = struct.pack('>B', CMD_SCROLL_UP)
    cmd += struct.pack('>H', scroll_pixels)

    ser.write(cmd)
    return SerialCommunicationToArduino.wait_for_ready(ser)


def switch_font(ser, screen_buffer, new_font, terminal):
    """Switch to new font, recreate PTY, redraw screen"""
    print(f"\nSwitching to font {new_font}...")

    # Get new font dimensions
    font_config = fontConfiguration[new_font]
    new_cols = font_config[1]

    # Recreate terminal with new dimensions
    terminal.cols = new_cols
    terminal.rows = 17
    terminal.screen = pyte.Screen(new_cols, 17)
    terminal.stream = pyte.Stream(terminal.screen)

    # Clear Arduino screen (also resets scroll)
    clear_screen(ser)

    print(f"Font {new_font} active ({new_cols} cols × {font_config[2]} rows visible)")
    return new_font


def get_command_from_keyboard(ser, screen_buffer, font_id, keyboard_handler, serial_to_duino):
    """Wait for user to type command, return command string or action"""
    command = ""
    key_buffer = []

    while True:
        time.sleep(0.01)
        serial_to_duino.process_pending_serial(ser, key_buffer)

        while len(key_buffer) > 0:
            key = key_buffer.pop(0)

            # Process key through handler
            result = keyboard_handler.process_key(key)

            if result is None:
                # Modifier key, ignore
                continue

            elif isinstance(result, dict):
                # Action to execute
                if result["action"] == "enter":
                    return {"type": "command", "value": command}

                elif result["action"] == "backspace":
                    if len(command) > 0:
                        command = command[:-1]
                        screen_buffer.update_prompt("CMD> " + command + " ")
                        # Update prompt line
                        start_row, lines = screen_buffer.get_lines_for_font(font_id)
                        prompt_line = lines[-1]

                        # For fonts with 17 rows, prompt is at display row 16
                        # For fonts with 8 rows, prompt is at display row 7
                        font_config = fontConfiguration[font_id]
                        visible_rows = font_config[2]
                        display_row = visible_rows - 1  # Last visible row
                        send_line_to_arduino(ser, prompt_line, 16, display_row, font_id)

                else:
                    # Return action (font change, clear, etc)
                    return result

            elif isinstance(result, str):
                # Regular character
                command += result
                screen_buffer.update_prompt("CMD> " + command)
                # Update prompt line
                start_row, lines = screen_buffer.get_lines_for_font(font_id)
                prompt_line = lines[-1]

                send_line_to_arduino(ser, prompt_line, 16, fontConfiguration[font_id][2] - 1, font_id)


def clear_screen(ser):
    ser.write(bytes([CMD_CLEAR_SCREEN]))
    SerialCommunicationToArduino.wait_for_ready(ser)


def main():
    serial_to_duino = SerialCommunicationToArduino

    ser = serial.Serial(SERIAL_PORT, BAUD_RATE, timeout=0)

    print("Starting terminal communication...")
    print("Waiting for Arduino...")
    SerialCommunicationToArduino.wait_for_ready(ser, timeout=10.0)
    print("Arduino ready!\n")

    # Initialize with Font 1 (64×17)
    current_font = 1
    font_config = fontConfiguration[current_font]

    terminal = TerminalBuffer(pyte, cols=font_config[1], rows=17)
    screen_buffer = ScreenBuffer(max_cols=64, rows=17, prompt="CMD> ")
    keyboard_handler = KeyboardHandler()

    # Initial screen display
    clear_screen(ser)
    send_screen_to_arduino(
        ser, screen_buffer, current_font,
        # this is the default, in this case this is the initial drawn of the
        # screen so no need to send anything new as there is nothing "old"
        # this is equivalent to say
        # num_new_lines=0,
        force_full_redraw=True)

    print(f"Font {current_font} active ({font_config[1]} cols × {font_config[2]} rows visible)")
    print("Shift+0/1/2/3 = Change font, Sym+C = Clear buffer\n")

    try:
        while True:
            # Get input from keyboard
            result = get_command_from_keyboard(ser, screen_buffer, current_font, keyboard_handler, serial_to_duino)

            # Handle result based on type
            if "action" in result:
                # It's an action
                if result["action"] == "font_change":
                    new_font = result["font"]
                    current_font = switch_font(ser, screen_buffer, new_font, terminal)
                    # Full redraw after font change, reset scroll
                    send_screen_to_arduino(
                        ser,
                        screen_buffer,
                        current_font,
                        # this is the default, in this case, we are switching fonts and we want to redraw anything,
                        # as there is nothing "old" that can help us as the font is different
                        # this is equivalent to say
                        # num_new_lines=0,
                        force_full_redraw=True)

                elif result["action"] == "clear_buffer":
                    # Clear buffer and screen
                    screen_buffer.lines = ["" for _ in range(17)]
                    screen_buffer.update_prompt("CMD> ")
                    clear_screen(ser)
                    send_screen_to_arduino(
                        ser,
                        screen_buffer,
                        current_font,
                        # this is the default, in this case we want to clear the screen, so nothing to scroll
                        # this is equivalent to say
                        # num_new_lines=0,
                        force_full_redraw=True)
                    print("Buffer cleared")

            elif "type" in result:
                # It's a command
                if result["type"] == "command":
                    cmd = result["value"]

                    if not cmd.strip():
                        continue

                    print(f"Executing: {cmd}")

                    # Add command to buffer
                    terminal.run_command(f"echo '{Utilities.start_marker}'", timeout=10.0)
                    screen_buffer.add_output_lines(["> " + cmd])
                    if terminal.run_command(cmd, timeout=10.0):
                        # Get and trim output
                        raw_output = terminal.get_screen()
                        print(f"Command response: {raw_output}")
                        trimmed_output = Utilities.trim_empty_lines(raw_output)
                        print(f"trimmed_output: {trimmed_output}")
                        screen_buffer.log_buffer()
                        screen_buffer.add_reversed_output_lines(trimmed_output)
                        screen_buffer.log_buffer()
                        number_of_new_lines = len(trimmed_output)

                        # Reset prompt
                        screen_buffer.update_prompt("CMD> ")

                        # Redraw screen with optimization
                        send_screen_to_arduino(
                            ser,
                            screen_buffer,
                            current_font,
                            number_of_new_lines,
                            force_full_redraw=False)

                    else:
                        screen_buffer.add_output_lines(["<timeout>"])
                        screen_buffer.update_prompt("CMD> ")
                        send_screen_to_arduino(ser, screen_buffer, current_font,
                                               force_full_redraw=False)

    except KeyboardInterrupt:
        print("\n\nExiting...")
    finally:
        ser.close()


if __name__ == '__main__':
    main()

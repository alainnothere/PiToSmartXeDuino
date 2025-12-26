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

import sys

from keyboard_handler import KeyboardHandler
from PyteAndPtyProcessTerminal import PyteAndPtyProcessTerminal
from SubprocessTerminal import SubprocessTerminal

from serialCommunicationsToArduino import SerialCommunicationToArduino, PROMPT
from utilities import Utilities
import time


def main():
    Utilities.print_with_indent(f"All arguments: {sys.argv}")
    serial_port = sys.argv[1] if len(sys.argv) > 1 and sys.argv[1] else "/dev/ttyAMA0"
    Utilities.print_with_indent(f"using port {serial_port}")

    # Utilities.print_all_font_chars(Utilities.uc_font)
    # serial_port = '/dev/ttyAMA0'
    serial_to_duino = SerialCommunicationToArduino(None, serial_port)

    if False:
        terminal = PyteAndPtyProcessTerminal()
    else:
        terminal = SubprocessTerminal()

    Utilities.print_with_indent_and_log_level("Starting terminal communication...", 2)
    Utilities.print_with_indent_and_log_level("Waiting for Arduino...", 2)

    serial_to_duino.clear_screen()

    Utilities.print_with_indent("Arduino ready!")

    keyboard_handler = KeyboardHandler()

    # Initial screen display
    serial_to_duino.clear_screen()
    serial_to_duino.send_new_screen_lines_to_arduino(
        terminal.get_screen_new_lines(), terminal.get_current_font())
    # this is the default, in this case this is the initial drawn of the
    # screen so no need to send anything new as there is nothing "old"
    # this is equivalent to say
    # num_new_lines=0,
    # force_full_redraw=True)

    Utilities.print_with_indent("Shift+0/1/2/3 = Change font, Sym+C = Clear buffer")

    try:
        while True:
            Utilities.delay_to_not_bog_cpu()

            current_font = terminal.get_current_font()
            serial_to_duino.update_prompt("", current_font)

            # Get input from keyboard
            result = serial_to_duino.get_command_from_keyboard(
                terminal.get_current_font(),
                keyboard_handler)

            # Handle result based on type
            Utilities.print_with_indent(f"\n\n\nget command from keyboard result: {result}")
            if "action" in result:
                # It's an action
                if result["action"] == "font_change":
                    current_font = result["font"]
                    Utilities.print_with_indent(f"switching font to font size: {current_font}")
                    terminal.switch_font(current_font)
                    serial_to_duino.clear_screen(clear_buffer=False)
                    serial_to_duino.re_send_screen_lines_to_arduino(current_font)
                    # this is the default, in this case, we are switching fonts and we want to redraw anything,
                    # as there is nothing "old" that can help us as the font is different
                    # this is equivalent to say
                    # num_new_lines=0,
                    # force_full_redraw=True)

                elif result["action"] == "clear_buffer":
                    terminal.clear()
                    serial_to_duino.clear_screen()
                    # this is the default, in this case we want to clear the screen, so nothing to scroll
                    # this is equivalent to say
                    # num_new_lines=0,
                    # force_full_redraw=True)
                    Utilities.print_with_indent("Buffer cleared")

            elif "type" in result:
                # It's a command
                start_time = time.time()
                if result["type"] == "command":
                    cmd = result["value"].strip()

                    if not cmd:
                        continue

                    cmd = Utilities.apply_user_substitutions(cmd)

                    if Utilities.is_internal_command(cmd):
                        serial_to_duino.send_new_screen_lines_to_arduino(
                            Utilities.execute_internal_command(cmd),
                            current_font)
                    else:
                        Utilities.print_with_indent(f"Executing: {cmd}")

                        terminal.run_command("echo '========================='", timeout=10.0)
                        terminal.run_command(f"echo '{PROMPT}" + cmd + "   '", timeout=10.0)

                        # I need to force the IF to force the command to be executed by the time
                        # I grab the screen
                        if terminal.run_command(cmd, timeout=10.0):
                            serial_to_duino.send_new_screen_lines_to_arduino(
                                terminal.get_screen_new_lines(),
                                current_font)
                        else:
                            serial_to_duino.send_new_screen_lines_to_arduino(
                                terminal.get_screen_new_lines(),
                                current_font)

                Utilities.print_with_indent(f"Operation completed in {time.time() - start_time} secs")

    except KeyboardInterrupt:
        Utilities.print_with_indent("\n\nExiting...")


if __name__ == '__main__':
    main()

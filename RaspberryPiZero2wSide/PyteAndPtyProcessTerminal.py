import select
import time
import pyte
from ptyprocess import PtyProcess

from config import get_font_config
from utilities import Utilities

number_of_rows = 30


class PyteAndPtyProcessTerminal:

    def __init__(self, font_size=2):
        # set variables, most of them will be set below on the switch_font command
        self.stream: pyte.Stream = None
        self.screen: pyte.Screen = None
        self.rows: int
        self.cols: int
        self.process: PtyProcess = None
        self.pyte = pyte
        self.font_size = font_size
        self.switch_font(font_size)

    def run_command(self, command, timeout=10.0):
        """
        Run a command in the PTY and wait for it to complete
        Returns True if successful, False if timeout
        """
        self.clear

        self.process = PtyProcess.spawn(
            ['/bin/bash', '-c', command],
            dimensions=(self.rows, self.cols)
        )

        start_time = time.time()

        try:
            while self.process.isalive():
                if time.time() - start_time > timeout:
                    Utilities.print_with_indent_and_log_level(f"Command timeout after {timeout}s", 2)
                    self.process.terminate(force=True)
                    return False

                if self.process.fd in select.select([self.process.fd], [], [], 0.1)[0]:
                    try:
                        output = self.process.read()
                        if isinstance(output, bytes):
                            output = output.decode('utf-8', errors='replace')
                        self.stream.feed(output)
                    except EOFError:
                        break

            # Read remaining output
            try:
                while True:
                    output = self.process.read()
                    if isinstance(output, bytes):
                        output = output.decode('utf-8', errors='replace')
                    self.stream.feed(output)
            except EOFError:
                pass

            return True

        except Exception as e:
            Utilities.print_with_indent_and_log_level(f"Error running command: {e}", 2)
            if self.process and self.process.isalive():
                self.process.terminate(force=True)
            return False

    def switch_font(self, new_font_size):
        """Switch to new font, recreate PTY, redraw screen"""
        Utilities.print_with_indent(f"Switching to font {new_font_size}...")
        self.font_size = new_font_size
        # Get new font dimensions
        font_config = get_font_config().fontConfiguration[new_font_size]
        new_cols = font_config[1]
        new_rows = font_config[2]

        # Recreate terminal with new dimensions
        self.cols = new_cols
        self.rows = new_rows

        if self.screen is not None:
            self.screen.resize(number_of_rows, new_cols)
        else:
            self.screen = self.pyte.Screen(new_cols, number_of_rows)
            self.stream = self.pyte.Stream(self.screen)

        Utilities.print_with_indent_and_log_level(
            f"Font {new_font_size} active ({new_cols} cols × {font_config[2]} rows visible)", 2)

    def get_screen_new_lines(self):
        lines = []
        for row in range(self.screen.lines):
            line = ""
            for col in range(self.screen.columns):
                char = self.screen.buffer[row][col].data
                line += char
            stripped = line.rstrip()
            if stripped:
                lines.append(stripped)

        Utilities.print_with_indent_and_log_level(f"Screen contents: {lines}", 2)

        try:
            index = len(lines) - 1 - lines[::-1].index("=========================")
            new_lines = lines[index + 1:]
        except ValueError:
            new_lines = lines

        Utilities.print_with_indent_and_log_level(f"New contents: {new_lines}", 2)

        return new_lines

    def clear(self):
        """Clear the terminal screen"""
        self.screen.reset()

    def get_current_font(self):
        return self.font_size

# # Example usage:
# if __name__ == "__main__":
#     import pyte
#
#     # Create a test screen
#     screen = pyte.Screen(80, 24)
#     stream = pyte.Stream(screen)
#
#     # Write some test content
#     stream.feed("Hello, World!\n")
#     stream.feed("This is a test of grayscale rendering.\n")
#     stream.feed("█▓▒░ Testing different characters ░▒▓█\n")
#
#     # Render to grayscale bitmap
#     grayscale_map = render_screen_to_grayscale(screen, font_size=14)
#
#     print(f"Output shape: {grayscale_map.shape}")
#     print(f"Value range: {grayscale_map.min()} to {grayscale_map.max()}")
#
#     # Optionally save as image
#     output_img = Image.fromarray((grayscale_map * 17).astype(np.uint8))  # Scale back to 0-255
#     output_img.save("screen_render.png")
#     print("Saved to screen_render.png")
#
#     # Or render to specific size
#     custom_map = render_screen_to_grayscale_custom_size(screen, 640, 480, font_size=14)
#     print(f"Custom size output: {custom_map.shape}")
#
#     def clear(self):
#         """Clear the terminal screen"""
#         self.screen.reset()
#
#     def get_current_font(self):
#         return self.font_size

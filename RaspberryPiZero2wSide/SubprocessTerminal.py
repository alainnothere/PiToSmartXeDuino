import subprocess
import os
import time
from config import get_font_config, PROMPT
from utilities import Utilities

number_of_rows = 30


class SubprocessTerminal:

    def __init__(self, font_size=2):
        self.font_size = font_size
        self.rows: int = 0
        self.cols: int = 0
        self.last_output_lines = []
        self.switch_font(font_size)

    def run_command(self, command, timeout=10.0, override_log_level=2):
        """
        Run a command using subprocess and capture output
        Returns True if successful, False if timeout or error
        """
        self.clear()

        # Create environment with terminal dimensions
        my_env = os.environ.copy()
        my_env["COLUMNS"] = str(self.cols)
        my_env["LINES"] = str(self.rows)
        my_env["TERM"] = "xterm"  # Ensure programs know we're in a terminal

        try:
            process = subprocess.Popen(
                ['/bin/bash', '-c', command],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                env=my_env
            )

            try:
                stdout, stderr = process.communicate(timeout=timeout)

                # Combine stdout and stderr
                output = f"\n{PROMPT} {command}\n" + stdout
                if stderr:
                    output += stderr

                # Split into lines and store
                self.last_output_lines = self.wrap_lines(output.splitlines())

                # now let's break lines into multiple lines IF the line is longer than the self.cols value

                return process.returncode == 0

            except subprocess.TimeoutExpired:
                Utilities.print_with_indent_and_log_level(
                    f"Command timeout after {timeout}s", override_log_level
                )
                process.kill()
                process.communicate()  # Clean up
                return False

        except Exception as e:
            Utilities.print_with_indent_and_log_level(
                f"Error running command: {e}", 3
            )
            return False

    def wrap_lines(self, lines):
        new_list = []
        for line in lines:
            if len(line) <= self.cols:
                new_list.append(line)
            else:
                # Chop the string into chunks of length x
                for i in range(0, len(line), self.cols):
                    new_list.append(line[i: i + self.cols])
        return new_list

    def switch_font(self, new_font_size):
        """Switch to new font, update dimensions"""
        Utilities.print_with_indent(f"Switching to font {new_font_size}...")
        self.font_size = new_font_size

        # Get new font dimensions
        font_config = get_font_config(new_font_size)
        new_cols = font_config[1]
        new_rows = font_config[2]

        self.cols = new_cols
        self.rows = new_rows

        Utilities.print_with_indent_and_log_level(
            f"Font {new_font_size} active ({new_cols} cols × {new_rows} rows visible)", 2
        )

    def get_screen_new_lines(self):
        """
        Return the output lines, attempting to find content after separator
        """
        lines = [line.rstrip() for line in self.last_output_lines if line.rstrip()]

        Utilities.print_with_indent_and_log_level(f"Screen contents: {lines}", 2)

        try:
            index = len(lines) - 1 - lines[::-1].index("=========================")
            new_lines = lines[index + 1:]
        except ValueError:
            new_lines = lines

        Utilities.print_with_indent_and_log_level(f"New contents: {new_lines}", 2)

        return new_lines

    def clear(self):
        """Clear the stored output"""
        self.last_output_lines = []

    def get_current_font(self):
        return self.font_size

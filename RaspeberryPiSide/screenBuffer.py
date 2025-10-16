# now there is this situation, the screen is 136 lines, the small font is 8 lines and the big is 16
# and the small font will divide nicely the screen 136/8 = 17, but for the case of the big font
# the result contains decimals 136/16 = 8.5, so if we use this method to calculate where the row should
# be for the bigger fonts the last line will be 8 pixels above the last possible printable line
# for that reason I need to pad it
# philosophical issue, now the first line is not the first line... but I'm printing from the bottom up
# so that will be future developer problem....
# so here, without more talk, I proceed to add a new column to the font configuration, the padding to be in the last
# line
# Font configuration: [font_id, cols, rows_visible, pixels_per_row, padding to add to be in the last line]
fontConfiguration = [
    [0, 52, 17, 8, 0],  # FONT_NORMAL
    [1, 64, 17, 8, 0],  # FONT_SMALL
    [2, 32, 8, 16, 8],  # FONT_MEDIUM
    [3, 25, 8, 16, 8]  # FONT_LARGE
]


class ScreenBuffer:
    def __init__(self, max_cols=64, rows=17, prompt="CMD> "):
        """Initialize screen buffer - always 17 rows, max 64 cols"""
        self.max_cols = max_cols
        self.rows = rows
        self.prompt = prompt
        self.lines = ["" for _ in range(rows)]
        self.lines[rows - 1] = prompt

    def log_buffer(self):
        print(f"console buffer: {self.lines}")

    def add_reversed_output_lines(self, new_lines):
        self.add_output_lines(list(reversed(new_lines)))

    def add_output_lines(self, new_lines):
        """
        Add new output lines to buffer, scrolling up as needed.
        Ensures new lines overwrite previous ones completely.
        Rows 0-15 are scrollable content, row 16 is always prompt.
        """
        num_new = len(new_lines)
        if num_new == 0:
            return

        content_rows = self.rows - 1  # 16 rows for content

        # Helper: pad a new line to match or exceed old line's length
        def pad_line(new_line, old_line):
            new_line = new_line.rstrip("\n")  # remove accidental trailing newline
            if len(new_line) < len(old_line):
                return new_line + " " * (len(old_line) - len(new_line))
            else:
                return new_line

        if num_new >= content_rows:
            # Only take the last lines, and pad them against blanks (or nothing)
            new_display_lines = [
                pad_line(new, "") for new in new_lines[-content_rows:]
            ]
        else:
            # Scroll up old content, and add new lines
            old_lines = self.lines[num_new:content_rows]
            new_display_lines = []

            for i in range(num_new):
                old_line = self.lines[content_rows - num_new + i]
                new_line = pad_line(new_lines[i], old_line)
                new_display_lines.append(new_line)

            new_display_lines = old_lines + new_display_lines

        # Set content rows
        self.lines[0:content_rows] = new_display_lines

        # Keep prompt in place
        self.lines[self.rows - 1] = self.prompt

    def get_lines_for_font(self, font_id):
        """
        Get lines to display for given font
        Returns: (start_row, lines_to_send)
        """
        font_config = fontConfiguration[font_id]
        visible_rows = font_config[2]
        font_cols = font_config[1]

        if visible_rows >= 17:
            # Show all rows (fonts 0, 1)
            start_row = 0
            lines = self.lines[0:17]
        else:
            # Show last N rows (fonts 2, 3)
            start_row = 17 - visible_rows
            lines = self.lines[start_row:17]

        # Truncate each line to font's column width
        lines = [line[:font_cols].ljust(font_cols) for line in lines]

        return start_row, lines

    def update_prompt(self, new_prompt):
        """Update the prompt text"""
        self.prompt = new_prompt
        self.lines[self.rows - 1] = new_prompt

"""
Keyboard handler for Smart Response XE Terminal

Processes keyboard input from the Arduino and handles modifier key combinations.
"""

from config import KEY_MODIFIER_SHIFT, KEY_MODIFIER_SYM


class KeyboardHandler:
    """
    Process keyboard input and detect modifier key combinations.

    The Arduino sends modifier keys (Shift, Sym) as separate packets
    before the actual key. This class tracks the modifier state and
    returns appropriate actions.
    """

    def __init__(self):
        self.modifier_active = None

    def process_key(self, key: int):
        """
        Process keyboard input and return action or character.

        Args:
            key: Key code from Arduino

        Returns:
            - None: Modifier key (ignore, wait for next key)
            - str: Regular character to add to command
            - dict: Action to execute:
                - {"action": "enter"}
                - {"action": "backspace"}
                - {"action": "font_change", "font": 0-3}
                - {"action": "clear_buffer"}
        """
        # Check for modifier keys
        if key == KEY_MODIFIER_SHIFT:
            self.modifier_active = 'shift'
            return None

        if key == KEY_MODIFIER_SYM:
            self.modifier_active = 'sym'
            return None

        # Process with active modifier
        if self.modifier_active == 'shift':
            result = self._handle_shift_key(key)
            self.modifier_active = None
            return result

        if self.modifier_active == 'sym':
            result = self._handle_sym_key(key)
            self.modifier_active = None
            return result

        # No modifier - regular key
        return self._handle_regular_key(key)

    def _handle_shift_key(self, key: int):
        """Handle Shift + key combinations"""

        # Shift + 0-3: Font switching
        if key == 0x30:
            return {"action": "font_change", "font": 0}
        if key == 0x31:
            return {"action": "font_change", "font": 1}
        if key == 0x32:
            return {"action": "font_change", "font": 2}
        if key == 0x33:
            return {"action": "font_change", "font": 3}

        # Shift + DEL (0x08): Backspace
        if key == 0x08:
            return {"action": "backspace"}

        # Default: treat as regular character
        return chr(key) if 32 <= key <= 126 else None

    def _handle_sym_key(self, key: int):
        """Handle Sym + key combinations"""

        # Sym + C: Clear screen
        if key == 0x63:
            return {"action": "clear_buffer"}

        # Default: treat as regular character
        return chr(key) if 32 <= key <= 126 else None

    def _handle_regular_key(self, key: int):
        """Handle regular key presses"""

        # DEL (0x08) = Enter
        if key == 0x08:
            return {"action": "enter"}

        # Backspace (0x7F)
        if key == 0x7F:
            return {"action": "backspace"}

        # Printable character
        if 32 <= key <= 126:
            return chr(key)

        # Ignore other special keys
        return None

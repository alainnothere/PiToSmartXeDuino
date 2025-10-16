# Keyboard definitions
KEY_START_MARKER = 0xFD
KEY_END_MARKER = 0xFE
KEY_MODIFIER_SHIFT = 0x10
KEY_MODIFIER_SYM = 0x11

class KeyboardHandler:
    def __init__(self):
        self.modifier_active = None

    def process_key(self, key):
        """
        Process keyboard input and return action or character

        Returns:
        - None: Ignore (modifier keys)
        - str: Regular character to add to command
        - dict: Action to execute
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

    def _handle_shift_key(self, key):
        """Handle Shift + key combinations"""
        # Shift + 0-3: Font switching
        if key == ord('0'):
            return {"action": "font_change", "font": 0}
        if key == ord('1'):
            return {"action": "font_change", "font": 1}
        if key == ord('2'):
            return {"action": "font_change", "font": 2}
        if key == ord('3'):
            return {"action": "font_change", "font": 3}

        # Shift + DEL: Backspace
        if key == 0x08:
            return {"action": "backspace"}

        # Default: treat as regular character
        return chr(key) if 32 <= key <= 126 else None

    def _handle_sym_key(self, key):
        """Handle Sym + key combinations"""
        # Sym + C: Clear screen
        if key == ord('c') or key == ord('C'):
            return {"action": "clear_buffer"}

        # Default: treat as regular character
        return chr(key) if 32 <= key <= 126 else None

    def _handle_regular_key(self, key):
        """Handle regular key presses"""
        # DEL = Enter
        if key == 0x08:
            return {"action": "enter"}

        # Backspace
        if key == 0x7F:
            return {"action": "backspace"}

        # Printable character
        if 32 <= key <= 126:
            return chr(key)

        # Ignore other special keys
        return None

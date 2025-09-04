"""Keyboard input handling using curtsies-style tokens."""

from typing import Optional
from dataclasses import dataclass
from enum import Enum


class KeyType(Enum):
    """Types of key events."""
    REGULAR = "regular"
    ALT = "alt"
    CTRL = "ctrl"
    SPECIAL = "special"
    SHIFT_SPECIAL = "shift_special"  # Shift + arrow keys, etc.


@dataclass
class KeyEvent:
    """Represents a parsed keyboard event."""
    key_type: KeyType
    value: str  # The base key (e.g., 'a', 'left', 'backspace')
    raw: str  # The raw key string from blessed
    is_alt: bool = False
    is_ctrl: bool = False
    is_shift: bool = False
    is_sequence: bool = False
    code: Optional[int] = None


class KeyboardHandler:
    """Handles keyboard input using curtsies-style key names."""
    
    # Control key mappings
    CTRL_KEYS = {
        '\x01': 'a',  # Ctrl+A
        '\x02': 'b',  # Ctrl+B  
        '\x03': 'c',  # Ctrl+C
        '\x04': 'd',  # Ctrl+D
        '\x05': 'e',  # Ctrl+E
        '\x06': 'f',  # Ctrl+F
        '\x07': 'g',  # Ctrl+G
        '\x08': 'h',  # Ctrl+H (backspace)
        '\x09': 'i',  # Ctrl+I (tab)
        '\x0a': 'j',  # Ctrl+J (newline)
        '\x0b': 'k',  # Ctrl+K
        '\x0c': 'l',  # Ctrl+L
        '\x0d': 'm',  # Ctrl+M (return)
        '\x0e': 'n',  # Ctrl+N
        '\x0f': 'o',  # Ctrl+O
        '\x10': 'p',  # Ctrl+P
        '\x11': 'q',  # Ctrl+Q
        '\x12': 'r',  # Ctrl+R
        '\x13': 's',  # Ctrl+S
        '\x14': 't',  # Ctrl+T
        '\x15': 'u',  # Ctrl+U
        '\x16': 'v',  # Ctrl+V
        '\x17': 'w',  # Ctrl+W
        '\x18': 'x',  # Ctrl+X
        '\x19': 'y',  # Ctrl+Y
        '\x1a': 'z',  # Ctrl+Z
        '\x1e': '^',  # Ctrl+^ (RS - Record Separator)
    }
    
    def __init__(self, terminal_interface):
        """Initialize with a terminal interface."""
        self.terminal = terminal_interface
        
    def get_key_event(self, timeout: Optional[float] = None) -> Optional[KeyEvent]:
        """Get next key event and map curtsies-style names to KeyEvent."""
        key = self.terminal.get_key(timeout)
        if not key:
            return None
        return self.parse_key(key)
    
    def parse_raw_key(self, key_str: str) -> KeyEvent:
        """Parse a raw key string into a KeyEvent.
        
        Args:
            key_str: Raw key string
            
        Returns:
            Parsed KeyEvent
        """
        # Check for ESC
        if key_str == '\x1b':
            return KeyEvent(
                key_type=KeyType.SPECIAL,
                value='escape',
                raw=key_str,
                is_sequence=False
            )
        
        # Check for Ctrl keys
        if key_str in self.CTRL_KEYS:
            return KeyEvent(
                key_type=KeyType.CTRL,
                value=self.CTRL_KEYS[key_str],
                raw=key_str,
                is_ctrl=True,
                is_sequence=False
            )
        
        # Regular character
        return KeyEvent(
            key_type=KeyType.REGULAR,
            value=key_str,
            raw=key_str,
            is_sequence=False
        )
    
    def parse_key(self, key) -> KeyEvent:
        """Parse a blessed key into a KeyEvent.
        
        Args:
            key: blessed.keyboard.Keystroke object
            
        Returns:
            Parsed KeyEvent
        """
        key_str = str(key)

        # Fast-path: curtsies-style key names like '<LEFT>', '<Ctrl-x>', '<Alt-left>'
        if key_str.startswith('<') and key_str.endswith('>'):
            name = key_str[1:-1]
            lower = name.lower()
            # Support both '-' and '+' as modifier separators (e.g., '<Esc+u>')
            lower = lower.replace('+', '-')
            # Split modifiers and base
            parts = lower.split('-') if '-' in lower else [lower]
            mods = set()
            base = parts[-1]
            if len(parts) > 1:
                mods = set(parts[:-1])
            # Normalize meta->alt
            if 'meta' in mods:
                mods.add('alt')
            # Treat 'esc' as alt modifier when combined with another key
            if 'esc' in mods:
                mods.add('alt')
            specials = {'left','right','up','down','home','end','enter','backspace','delete'}
            # Heuristic: if base is not a known special but the token contains
            # a known direction name, infer it (some terminals/curtsies builds
            # can produce unusual casing/orderings)
            if base not in specials:
                if 'left' in lower:
                    base = 'left'
                elif 'right' in lower:
                    base = 'right'
                elif 'up' in lower:
                    base = 'up'
                elif 'down' in lower:
                    base = 'down'
            # Control modified letters
            if 'ctrl' in mods and len(base) == 1:
                # Map Ctrl-J / Ctrl-M to enter
                if base in ('j','m'):
                    return KeyEvent(key_type=KeyType.SPECIAL, value='enter', raw=key_str, is_sequence=True)
                return KeyEvent(key_type=KeyType.CTRL, value=base, raw=key_str, is_ctrl=True)
            # Alt/meta modified arrows or letters
            if 'alt' in mods:
                if base in specials or len(base) == 1:
                    return KeyEvent(key_type=KeyType.ALT, value=base, raw=key_str, is_alt=True)
            # Shift-modified arrows for selection
            if 'shift' in mods and base in specials:
                return KeyEvent(key_type=KeyType.SHIFT_SPECIAL, value=base, raw=key_str, is_shift=True, is_sequence=True)
            # Plain specials
            if base in specials:
                return KeyEvent(key_type=KeyType.SPECIAL, value=base, raw=key_str, is_sequence=True)
            # Escape
            if base in ('esc','escape'):
                return KeyEvent(key_type=KeyType.SPECIAL, value='escape', raw='\x1b')
            # Fallback: treat unknown token as special
            return KeyEvent(key_type=KeyType.SPECIAL, value=base, raw=key_str, is_sequence=True)

        # Raw newline or carriage return should be treated as enter
        if key_str in ('\n', '\r'):
            return KeyEvent(key_type=KeyType.SPECIAL, value='enter', raw=key_str)
        
        # Bare ESC
        if key_str == '\x1b':
            return KeyEvent(key_type=KeyType.SPECIAL, value='escape', raw='\x1b')
        
        # Check for Ctrl keys
        if key_str in self.CTRL_KEYS:
            return KeyEvent(
                key_type=KeyType.CTRL,
                value=self.CTRL_KEYS[key_str],
                raw=key_str,
                is_ctrl=True,
                is_sequence=False
            )
        
        # Regular character
        return KeyEvent(
            key_type=KeyType.REGULAR,
            value=key_str,
            raw=key_str,
            is_sequence=False
        )
    
    # Legacy escape-sequence helpers removed; curtsies tokens are parsed directly above.


def create_keyboard_handler(terminal_interface):
    """Factory function to create a keyboard handler.
    
    Args:
        terminal_interface: TerminalInterface instance
        
    Returns:
        KeyboardHandler instance
    """
    return KeyboardHandler(terminal_interface)

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
    
    # No raw control mapping; curtsies tokens are used exclusively
    
    def __init__(self, terminal_interface):
        """Initialize with a terminal interface."""
        self.terminal = terminal_interface
        
    def get_key_event(self, timeout: Optional[float] = None) -> Optional[KeyEvent]:
        """Get next key event and map curtsies-style names to KeyEvent."""
        key = self.terminal.get_key(timeout)
        if not key:
            return None
        return self.parse_key(key)
    
    # No parse_raw_key: raw sequences are not supported; curtsies tokens only
    
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
            # Normalize page keys first
            if base in ('pageup', 'page_up'):
                base = 'page_up'
            elif base in ('pagedown', 'page_down'):
                base = 'page_down'

            specials = {
                'left','right','up','down','home','end','enter','backspace','delete',
                'page_up','page_down','insert'
            }
            # Map named whitespace tokens to regular characters
            if base in ('space', 'spacebar', 'spc') and not mods:
                return KeyEvent(key_type=KeyType.REGULAR, value=' ', raw=' ')
            if base in ('tab',) and not mods:
                return KeyEvent(key_type=KeyType.REGULAR, value='\t', raw='\t')
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

        # Single-byte ASCII control chars (Ctrl-<letter>)
        if len(key_str) == 1:
            o = ord(key_str)
            if 1 <= o <= 26:  # Ctrl-A .. Ctrl-Z (exclude ESC=27)
                ch = chr(ord('a') + o - 1)
                # Map Ctrl-J/Ctrl-M to enter, consistent with terminals
                if ch in ('j', 'm'):
                    return KeyEvent(key_type=KeyType.SPECIAL, value='enter', raw=key_str)
                return KeyEvent(key_type=KeyType.CTRL, value=ch, raw=key_str, is_ctrl=True)

        # Bare ESC
        if key_str == '\x1b':
            return KeyEvent(key_type=KeyType.SPECIAL, value='escape', raw='\x1b')
        
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

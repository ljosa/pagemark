"""Keyboard input handling with proper Alt key support."""

from typing import Optional, Tuple
from dataclasses import dataclass
from enum import Enum
import blessed
from .constants import EditorConstants


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
    """Handles keyboard input with proper Alt key detection."""
    
    # Known Alt key sequences from various terminals
    ALT_SEQUENCES = {
        # Alt + arrow keys (various terminal encodings)
        '\x1b[1;3D': ('left', True),   # xterm-style Alt+Left
        '\x1b[1;3C': ('right', True),  # xterm-style Alt+Right
        # Note: \x1b[D and \x1b[C are regular arrow keys, not Alt-modified
        # Note: \x1bOD and \x1bOC are regular arrow keys in application mode, not Alt-modified
        
        # Alt + letters (ESC + letter)
        '\x1bb': ('b', True),           # Alt+B (backward word)
        '\x1bf': ('f', True),           # Alt+F (forward word)
        '\x1bc': ('c', True),           # Alt+C (capitalize word)
        '\x1bd': ('d', True),           # Alt+D (delete word)
        '\x1bl': ('l', True),           # Alt+L (downcase word)
        '\x1bt': ('t', True),           # Alt+T (transpose words)
        '\x1bu': ('u', True),           # Alt+U (upcase word)
        
        # Alt + backspace
        '\x1b\x7f': ('backspace', True),  # Alt+Backspace (delete word)
        '\x1b\x08': ('backspace', True),  # Alt+Backspace (alternate)
    }
    
    # Shift + arrow key sequences
    SHIFT_SEQUENCES = {
        '\x1b[1;2D': 'left',   # Shift+Left
        '\x1b[1;2C': 'right',  # Shift+Right  
        '\x1b[1;2A': 'up',     # Shift+Up
        '\x1b[1;2B': 'down',   # Shift+Down
        '\x1b[1;2H': 'home',   # Shift+Home
        '\x1b[1;2F': 'end',    # Shift+End
    }
    
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
        """Get next key event with consolidated Alt/Shift handling."""
        key = self.terminal.get_key(timeout)
        if not key:
            return None
        key_str = str(key)

        # Combine ESC with the immediate next keystroke (non-blocking)
        if key_str == '\x1b':
            next_key = self.terminal.get_key(timeout=0)
            if next_key:
                combined = key_str + str(next_key)
                if combined in self.SHIFT_SEQUENCES:
                    return KeyEvent(
                        key_type=KeyType.SHIFT_SPECIAL,
                        value=self.SHIFT_SEQUENCES[combined],
                        raw=combined,
                        is_shift=True,
                        is_sequence=True
                    )
                if combined in self.ALT_SEQUENCES:
                    base_key, is_alt = self.ALT_SEQUENCES[combined]
                    return KeyEvent(
                        key_type=KeyType.ALT,
                        value=base_key,
                        raw=combined,
                        is_alt=is_alt,
                        is_sequence=False
                    )
                nstr = str(next_key)
                if len(nstr) == 1 and nstr.isalpha():
                    return KeyEvent(
                        key_type=KeyType.ALT,
                        value=nstr.lower(),
                        raw=combined,
                        is_alt=True,
                        is_sequence=False
                    )
                # Fallback: handle next_key normally
                return self.parse_key(next_key)
            # Bare ESC
            return KeyEvent(
                key_type=KeyType.SPECIAL,
                value='escape',
                raw='\x1b',
                is_sequence=False
            )

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
        
        # Check for known Shift/Alt sequences by raw string first
        if key_str in self.SHIFT_SEQUENCES:
            return KeyEvent(
                key_type=KeyType.SHIFT_SPECIAL,
                value=self.SHIFT_SEQUENCES[key_str],
                raw=key_str,
                is_shift=True,
                is_sequence=hasattr(key, 'is_sequence') and key.is_sequence,
                code=key.code if hasattr(key, 'code') else None
            )
        if key_str in self.ALT_SEQUENCES:
            base_key, is_alt = self.ALT_SEQUENCES[key_str]
            return KeyEvent(
                key_type=KeyType.ALT,
                value=base_key,
                raw=key_str,
                is_alt=is_alt,
                is_sequence=hasattr(key, 'is_sequence') and key.is_sequence,
                code=key.code if hasattr(key, 'code') else None
            )

        # Check for Shift-modified special sequences by raw string
        if key_str in self.SHIFT_SEQUENCES:
            return KeyEvent(
                key_type=KeyType.SHIFT_SPECIAL,
                value=self.SHIFT_SEQUENCES[key_str],
                raw=key_str,
                is_shift=True,
                is_sequence=hasattr(key, 'is_sequence') and key.is_sequence,
                code=key.code if hasattr(key, 'code') else None
            )
        
        # Bare ESC is handled in get_key_event
        if key_str == '\x1b':
            return KeyEvent(
                key_type=KeyType.SPECIAL,
                value='escape',
                raw=key_str,
                is_sequence=False
            )
        
        # Handle special keys from blessed first (before checking Ctrl keys)
        # This ensures that special sequences are properly identified
        if hasattr(key, 'is_sequence') and key.is_sequence:
            # Map blessed key codes to readable names
            if hasattr(key, 'code'):
                key_name = self._get_key_name(key)
                return KeyEvent(
                    key_type=KeyType.SPECIAL,
                    value=key_name,
                    raw=key_str,
                    is_sequence=True,
                    code=key.code
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
    
    def _handle_escape_sequence(self, next_key) -> KeyEvent:
        """Handle ESC followed by another key (Alt pattern).
        
        Args:
            next_key: The key that followed ESC
            
        Returns:
            KeyEvent with Alt modifier if applicable
        """
        next_str = str(next_key)
        
        # Check for Alt+letter patterns
        if len(next_str) == 1 and next_str.isalpha():
            return KeyEvent(
                key_type=KeyType.ALT,
                value=next_str.lower(),
                raw='\x1b' + next_str,
                is_alt=True,
                is_sequence=False
            )
        
        # Check for Alt+arrow keys (when sent as ESC + arrow sequence)
        if hasattr(next_key, 'is_sequence') and next_key.is_sequence:
            key_name = self._get_key_name(next_key)
            if key_name in ('left', 'right', 'up', 'down', 'backspace'):
                return KeyEvent(
                    key_type=KeyType.ALT,
                    value=key_name,
                    raw='\x1b' + str(next_key),
                    is_alt=True,
                    is_sequence=True,
                    code=next_key.code if hasattr(next_key, 'code') else None
                )
        
        # Check for Alt+backspace special cases
        if next_str in ('\x7f', '\x08'):
            return KeyEvent(
                key_type=KeyType.ALT,
                value='backspace',
                raw='\x1b' + next_str,
                is_alt=True,
                is_sequence=False
            )
        
        # Not an Alt combination - return as separate ESC + key
        # This shouldn't normally happen with our timeout
        return KeyEvent(
            key_type=KeyType.REGULAR,
            value=next_str,
            raw=next_str,
            is_sequence=hasattr(next_key, 'is_sequence') and next_key.is_sequence
        )
    
    def _get_key_name(self, key) -> str:
        """Get a readable name for a blessed special key.
        
        Args:
            key: blessed.keyboard.Keystroke object
            
        Returns:
            Readable key name
        """
        if not hasattr(key, 'code'):
            return str(key)
        
        # Map common blessed key codes
        term = self.terminal.term
        key_mapping = {
            term.KEY_LEFT: 'left',
            term.KEY_RIGHT: 'right',
            term.KEY_UP: 'up',
            term.KEY_DOWN: 'down',
            term.KEY_BACKSPACE: 'backspace',
            term.KEY_ENTER: 'enter',
            term.KEY_DELETE: 'delete',
            term.KEY_HOME: 'home',
            term.KEY_END: 'end',
            term.KEY_PGUP: 'page_up',
            term.KEY_PGDOWN: 'page_down',
            263: 'backspace',  # Common backspace code
        }
        
        # Add function keys if they exist
        if hasattr(term, 'KEY_F1'):
            key_mapping[term.KEY_F1] = 'f1'
        
        return key_mapping.get(key.code, f'key_{key.code}')


def create_keyboard_handler(terminal_interface):
    """Factory function to create a keyboard handler.
    
    Args:
        terminal_interface: TerminalInterface instance
        
    Returns:
        KeyboardHandler instance
    """
    return KeyboardHandler(terminal_interface)

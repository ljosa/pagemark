"""Test keyboard input handling."""

import pytest
from unittest.mock import Mock, MagicMock
from pagemark.keyboard import KeyboardHandler, KeyEvent, KeyType


class MockTerminal:
    """Mock terminal interface for testing."""
    
    def __init__(self):
        self.term = MagicMock()
        self.term.KEY_LEFT = 260
        self.term.KEY_RIGHT = 261
        self.term.KEY_UP = 259
        self.term.KEY_DOWN = 258
        self.term.KEY_BACKSPACE = 263
        self.term.KEY_ENTER = 343
        self.term.KEY_DELETE = 330
        self.term.KEY_HOME = 262
        self.term.KEY_END = 360
        self.term.KEY_PGUP = 339
        self.term.KEY_PGDOWN = 338
        self._key_queue = []
        
    def get_key(self, timeout=None):
        """Mock get_key that returns from queue."""
        if self._key_queue:
            return self._key_queue.pop(0)
        return None
    
    def add_key(self, key_str, is_sequence=False, code=None):
        """Add a key to the queue."""
        key = Mock()
        key.__str__ = lambda self: key_str
        key.is_sequence = is_sequence
        if code is not None:
            key.code = code
        self._key_queue.append(key)


def test_alt_left_sequences():
    """Test various Alt+Left arrow sequences."""
    terminal = MockTerminal()
    handler = KeyboardHandler(terminal)
    
    # Test xterm-style Alt+Left
    terminal.add_key('\x1b[1;3D')
    event = handler.get_key_event()
    assert event is not None
    assert event.key_type == KeyType.ALT
    assert event.value == 'left'
    assert event.is_alt == True
    
    # Test Alt-b (backward word)
    terminal.add_key('\x1bb')
    event = handler.get_key_event()
    assert event.key_type == KeyType.ALT
    assert event.value == 'b'
    assert event.is_alt == True


def test_alt_right_sequences():
    """Test various Alt+Right arrow sequences."""
    terminal = MockTerminal()
    handler = KeyboardHandler(terminal)
    
    # Test xterm-style Alt+Right
    terminal.add_key('\x1b[1;3C')
    event = handler.get_key_event()
    assert event.key_type == KeyType.ALT
    assert event.value == 'right'
    assert event.is_alt == True
    
    # Test Alt-f (forward word)
    terminal.add_key('\x1bf')
    event = handler.get_key_event()
    assert event.key_type == KeyType.ALT
    assert event.value == 'f'


def test_alt_backspace():
    """Test Alt+Backspace sequences."""
    terminal = MockTerminal()
    handler = KeyboardHandler(terminal)
    
    # Test Alt+Backspace variant 1
    terminal.add_key('\x1b\x7f')
    event = handler.get_key_event()
    assert event.key_type == KeyType.ALT
    assert event.value == 'backspace'
    assert event.is_alt == True
    
    # Test Alt+Backspace variant 2
    terminal.add_key('\x1b\x08')
    event = handler.get_key_event()
    assert event.key_type == KeyType.ALT
    assert event.value == 'backspace'


def test_esc_followed_by_key():
    """Test ESC followed by another key (two-part Alt sequence)."""
    terminal = MockTerminal()
    handler = KeyboardHandler(terminal)
    
    # Test ESC + b (Alt-b)
    terminal.add_key('\x1b')
    terminal.add_key('b')
    event = handler.get_key_event()
    assert event.key_type == KeyType.ALT
    assert event.value == 'b'
    assert event.is_alt == True
    
    # Test ESC + f (Alt-f)
    terminal.add_key('\x1b')
    terminal.add_key('f')
    event = handler.get_key_event()
    assert event.key_type == KeyType.ALT
    assert event.value == 'f'
    assert event.is_alt == True


def test_esc_alone():
    """Test ESC key by itself (no following key)."""
    terminal = MockTerminal()
    handler = KeyboardHandler(terminal)
    
    # ESC with no following key
    terminal.add_key('\x1b')
    event = handler.get_key_event()
    assert event.key_type == KeyType.SPECIAL
    assert event.value == 'escape'
    assert event.is_alt == False


def test_ctrl_keys():
    """Test Ctrl key combinations."""
    terminal = MockTerminal()
    handler = KeyboardHandler(terminal)
    
    # Ctrl-A
    terminal.add_key('\x01')
    event = handler.get_key_event()
    assert event.key_type == KeyType.CTRL
    assert event.value == 'a'
    assert event.is_ctrl == True
    
    # Ctrl-E
    terminal.add_key('\x05')
    event = handler.get_key_event()
    assert event.key_type == KeyType.CTRL
    assert event.value == 'e'
    
    # Ctrl-K
    terminal.add_key('\x0b')
    event = handler.get_key_event()
    assert event.key_type == KeyType.CTRL
    assert event.value == 'k'
    
    # Ctrl-Q
    terminal.add_key('\x11')
    event = handler.get_key_event()
    assert event.key_type == KeyType.CTRL
    assert event.value == 'q'
    
    # Ctrl-S
    terminal.add_key('\x13')
    event = handler.get_key_event()
    assert event.key_type == KeyType.CTRL
    assert event.value == 's'


def test_regular_arrow_sequences():
    """Test that regular arrow sequences are NOT treated as Alt."""
    terminal = MockTerminal()
    handler = KeyboardHandler(terminal)
    
    # These should NOT be treated as Alt sequences
    regular_sequences = [
        '\x1b[D',   # Regular left arrow in many terminals
        '\x1b[C',   # Regular right arrow in many terminals  
        '\x1bOD',   # Application mode left arrow
        '\x1bOC',   # Application mode right arrow
    ]
    
    for seq in regular_sequences:
        terminal.add_key(seq)
        event = handler.get_key_event()
        # These will be buffered and returned as regular keys since blessed
        # should handle them as special sequences
        assert event is not None
        assert event.key_type != KeyType.ALT, f"{repr(seq)} should not be Alt"
        

def test_special_keys():
    """Test special keys like arrows, enter, backspace."""
    terminal = MockTerminal()
    handler = KeyboardHandler(terminal)
    
    # Left arrow
    terminal.add_key('[D', is_sequence=True, code=terminal.term.KEY_LEFT)
    event = handler.get_key_event()
    assert event.key_type == KeyType.SPECIAL
    assert event.value == 'left'
    assert event.is_sequence == True
    
    # Right arrow
    terminal.add_key('[C', is_sequence=True, code=terminal.term.KEY_RIGHT)
    event = handler.get_key_event()
    assert event.key_type == KeyType.SPECIAL
    assert event.value == 'right'
    
    # Enter
    terminal.add_key('\r', is_sequence=True, code=terminal.term.KEY_ENTER)
    event = handler.get_key_event()
    assert event.key_type == KeyType.SPECIAL
    assert event.value == 'enter'
    
    # Backspace
    terminal.add_key('\x7f', is_sequence=True, code=terminal.term.KEY_BACKSPACE)
    event = handler.get_key_event()
    assert event.key_type == KeyType.SPECIAL
    assert event.value == 'backspace'


def test_regular_keys():
    """Test regular character input."""
    terminal = MockTerminal()
    handler = KeyboardHandler(terminal)
    
    # Regular letters
    for char in 'abcdefg':
        terminal.add_key(char)
        event = handler.get_key_event()
        assert event.key_type == KeyType.REGULAR
        assert event.value == char
        assert event.is_alt == False
        assert event.is_ctrl == False
    
    # Numbers
    for char in '0123456789':
        terminal.add_key(char)
        event = handler.get_key_event()
        assert event.key_type == KeyType.REGULAR
        assert event.value == char
    
    # Special characters
    for char in '!@#$%^&*()':
        terminal.add_key(char)
        event = handler.get_key_event()
        assert event.key_type == KeyType.REGULAR
        assert event.value == char


def test_no_key_available():
    """Test when no key is available."""
    terminal = MockTerminal()
    handler = KeyboardHandler(terminal)
    
    # No keys in queue
    event = handler.get_key_event(timeout=0)
    assert event is None
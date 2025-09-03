"""Terminal interface using Blessed for the word processor."""

import blessed
from typing import Optional


class TerminalInterface:
    """Handles terminal I/O using Blessed."""
    
    def __init__(self, terminal: Optional[blessed.Terminal] = None):
        """Initialize with a terminal instance (or create one)."""
        self.term = terminal or blessed.Terminal()
        self.is_fullscreen = False
        
    def setup(self):
        """Enter fullscreen mode and prepare terminal."""
        print(self.term.enter_fullscreen)
        print(self.term.hide_cursor)
        print(self.term.clear)
        self.is_fullscreen = True
        
    def cleanup(self):
        """Exit fullscreen mode and restore terminal."""
        if self.is_fullscreen:
            print(self.term.exit_fullscreen)
            print(self.term.normal_cursor)
            self.is_fullscreen = False
            
    def clear_screen(self):
        """Clear the entire screen."""
        print(self.term.clear)
        
    def draw_lines(self, lines: list[str], cursor_y: int, cursor_x: int):
        """Draw text lines and position cursor.
        
        Args:
            lines: List of strings to display
            cursor_y: Cursor row position (0-based)
            cursor_x: Cursor column position (0-based)
        """
        # Clear screen first
        print(self.term.home + self.term.clear, end='')
        
        # Draw each line
        for y, line in enumerate(lines):
            # Move to position and draw line
            print(self.term.move(y, 0) + line[:self.term.width], end='')
            
        # Draw status line at bottom
        status = f" Line {cursor_y + 1}, Col {cursor_x + 1} | Ctrl-Q to quit "
        print(self.term.move(self.term.height - 1, 0), end='')
        print(self.term.reverse + status.ljust(self.term.width) + self.term.normal, end='')
        
        # Position cursor
        print(self.term.move(cursor_y, cursor_x) + self.term.normal_cursor, end='', flush=True)
        
    def get_key(self):
        """Get a single keypress from the user.
        
        Returns:
            blessed.keyboard.Keystroke object
        """
        return self.term.inkey()
        
    @property
    def width(self):
        """Terminal width in columns."""
        return self.term.width
        
    @property  
    def height(self):
        """Terminal height in rows (excluding status line)."""
        return self.term.height - 1  # Reserve one line for status
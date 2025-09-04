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
        
    def draw_lines(self, lines: list[str], cursor_y: int, cursor_x: int, 
                   left_margin: int = 0, view_width: int = 65, status_override: str = None,
                   selection_ranges: list = None):
        """Draw text lines and position cursor with optional left margin.
        
        Args:
            lines: List of strings to display
            cursor_y: Cursor row position (0-based)
            cursor_x: Cursor column position (0-based)
            left_margin: Number of spaces to indent from left
            view_width: Width of the view area
            status_override: Custom status message to display instead of default
        """
        # Clear screen first
        print(self.term.home + self.term.clear, end='')
        
        # Draw each line with left margin
        for y, line in enumerate(lines):
            # Move to position and draw line with margin
            print(self.term.move(y, left_margin), end='')
            # Ensure line is exactly view_width characters (pad or truncate)
            display_line = line[:view_width].ljust(view_width)
            
            # Check if this line has any selection
            if selection_ranges and y < len(selection_ranges) and selection_ranges[y]:
                start_col, end_col = selection_ranges[y]
                # Draw line with selection highlighting
                if start_col > 0:
                    print(display_line[:start_col], end='')
                print(self.term.reverse + display_line[start_col:end_col] + self.term.normal, end='')
                if end_col < len(display_line):
                    print(display_line[end_col:], end='')
            else:
                print(display_line, end='')
            
        # Draw status line at bottom
        if status_override:
            # When there's a message or interaction, show it without F1 help
            status = status_override
            print(self.term.move(self.term.height - 1, 0), end='')
            print(status.ljust(self.term.width), end='')
        else:
            # At rest, show "F1 for help" right-justified
            help_text = "F1 for help"
            print(self.term.move(self.term.height - 1, 0), end='')
            # Clear the line first
            print(' ' * self.term.width, end='')
            # Position at right side for help text
            print(self.term.move(self.term.height - 1, self.term.width - len(help_text) - 1), end='')
            print(help_text, end='')
        
        # Position cursor (adjust for margin or for prompt input)
        if status_override and (": " in status_override):
            # Position cursor at end of current input
            cursor_pos = len(status_override)
            print(self.term.move(self.term.height - 1, cursor_pos) + self.term.normal_cursor, end='', flush=True)
        else:
            # Normal cursor positioning in text
            print(self.term.move(cursor_y, cursor_x + left_margin) + self.term.normal_cursor, end='', flush=True)
    
    def draw_error_message(self, message1: str, message2: str = ""):
        """Draw an error message in the center of the screen.
        
        Args:
            message1: Primary error message
            message2: Secondary information
        """
        # Clear screen first
        print(self.term.home + self.term.clear, end='')
        
        # Calculate center position
        center_y = self.term.height // 2
        
        # Draw error box
        box_width = max(len(message1), len(message2)) + 4
        left_margin = (self.term.width - box_width) // 2
        
        # Draw box
        print(self.term.move(center_y - 2, left_margin) + "╔" + "═" * (box_width - 2) + "╗", end='')
        print(self.term.move(center_y - 1, left_margin) + "║ " + message1.center(box_width - 4) + " ║", end='')
        if message2:
            print(self.term.move(center_y, left_margin) + "║ " + message2.center(box_width - 4) + " ║", end='')
            print(self.term.move(center_y + 1, left_margin) + "╚" + "═" * (box_width - 2) + "╝", end='')
        else:
            print(self.term.move(center_y, left_margin) + "╚" + "═" * (box_width - 2) + "╝", end='')
        
        # Draw help text at bottom
        help_text = "Ctrl-Q to quit | Resize terminal to continue"
        help_pos = (self.term.width - len(help_text)) // 2
        print(self.term.move(self.term.height - 1, help_pos), end='')
        print(help_text, end='', flush=True)
        
    def get_key(self, timeout=None):
        """Get a single keypress from the user.
        
        Args:
            timeout: Timeout in seconds (None for blocking, 0 for non-blocking)
            
        Returns:
            blessed.keyboard.Keystroke object
        """
        if timeout is None:
            return self.term.inkey()
        else:
            return self.term.inkey(timeout=timeout)
    
    @property
    def width(self):
        """Terminal width in columns."""
        return self.term.width
        
    @property  
    def height(self):
        """Terminal height in rows (excluding status line)."""
        return self.term.height - 1  # Reserve one line for status
"""Terminal interface using Blessed for display and Curtsies for input."""

import blessed
from typing import Optional
import sys
import select


class TerminalInterface:
    """Handles terminal I/O using Blessed."""
    
    def __init__(self, terminal: Optional[blessed.Terminal] = None):
        """Initialize with a terminal instance (or create one)."""
        self.term = terminal or blessed.Terminal()
        self.is_fullscreen = False
        self._curtsies_input: Optional[object] = None
        self._curtsies_active: bool = False
        # Virtual screen state for minimal updates
        self._last_lines: list[str] | None = None
        self._last_status: str | None = None
        self._last_left_margin: int | None = None
        self._last_view_width: int | None = None
        
    def setup(self):
        """Enter fullscreen mode and prepare terminal."""
        print(self.term.enter_fullscreen)
        print(self.term.hide_cursor)
        print(self.term.clear)
        self.is_fullscreen = True
        # Initialize curtsies input
        if self._curtsies_input is None:
            try:
                from curtsies import Input  # type: ignore
                # Enter raw mode immediately so reads work
                self._curtsies_input = Input(keynames='curtsies')  # type: ignore
                self._curtsies_input.__enter__()
                self._curtsies_active = True
            except Exception:
                # Justification: curtsies may be absent or fail to initialize
                # in some environments (CI, limited terminals). Fall back to
                # a no-input mode gracefully without crashing.
                self._curtsies_input = None
                self._curtsies_active = False
        
    def cleanup(self):
        """Exit fullscreen mode and restore terminal."""
        if self.is_fullscreen:
            print(self.term.exit_fullscreen)
            print(self.term.normal_cursor)
            self.is_fullscreen = False
        # Close curtsies input if in use
        if self._curtsies_input is not None:
            try:
                if self._curtsies_active:
                    # Exit raw mode context
                    self._curtsies_input.__exit__(None, None, None)  # type: ignore
            except Exception:
                # Justification: teardown should never crash the app. Any
                # failure to exit raw mode is non-fatal at this point.
                pass
            finally:
                self._curtsies_input = None
                self._curtsies_active = False
            
    def clear_screen(self):
        """Clear the entire screen."""
        print(self.term.clear)

    def invalidate_frame(self) -> None:
        """Invalidate cached frame so next update does a full clear.

        Use this when a modal UI (e.g., print dialog) has drawn arbitrary
        content to the screen and we need the editor to repaint from
        a clean slate on the next draw.
        """
        self._last_lines = None
        self._last_status = None
        self._last_left_margin = None
        self._last_view_width = None
    
    def move_cursor(self, y: int, x: int, left_margin: int = 0):
        """Move the cursor to a position without redrawing the screen."""
        print(self.term.move(y, x + left_margin) + self.term.normal_cursor, end='', flush=True)
    
    def draw_line(self, y: int, text: str, left_margin: int = 0, view_width: int = 65):
        """Redraw a single line at row y without clearing the screen."""
        display_line = (text[:view_width]).ljust(view_width)
        print(self.term.move(y, left_margin) + display_line, end='', flush=True)
        
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

    def _compose_display_line(self, line: str, view_width: int, selection: Optional[tuple[int, int]] | None,
                               styles: Optional[list[int]] = None) -> str:
        """Compose a display line with bold/underline and optional selection, padded to width.

        Styles is a per-column bitmask list with 1=bold, 2=underline.
        """
        text = line[:view_width].ljust(view_width)
        styles = (styles or [])[:view_width] + [0]*max(0, view_width - len(styles or []))

        out = []
        active_bold = False
        active_under = False
        active_rev = False

        def set_attrs(bold: bool, under: bool, rev: bool):
            nonlocal active_bold, active_under, active_rev
            if not (bold or under or rev):
                out.append(self.term.normal)
                active_bold = active_under = active_rev = False
                return
            # Reset then enable desired to avoid sticky state issues
            out.append(self.term.normal)
            if bold:
                out.append(self.term.bold)
            if under:
                out.append(self.term.underline)
            if rev:
                out.append(self.term.reverse)
            active_bold, active_under, active_rev = bold, under, rev

        for i, ch in enumerate(text):
            sel = False
            if selection and selection[0] <= i < selection[1]:
                sel = True
            bold = bool(styles[i] & 1)
            under = bool(styles[i] & 2)
            if (bold != active_bold) or (under != active_under) or (sel != active_rev):
                set_attrs(bold, under, sel)
            out.append(ch)
        # Reset at end
        if active_bold or active_under or active_rev:
            out.append(self.term.normal)
        return ''.join(out)

    def update_frame(
        self,
        lines: list[str],
        cursor_y: int,
        cursor_x: int,
        left_margin: int,
        view_width: int,
        status_override: Optional[str] = None,
        selection_ranges: Optional[list] = None,
        styles_by_line: Optional[list[list[int]]] = None,
    ) -> None:
        """Diff against last frame and write only changes.

        Falls back to a full clear on first paint or when geometry changes.
        """
        # Determine if we need a full clear (first paint, resize, margin/width change)
        need_full_clear = (
            self._last_lines is None
            or self._last_left_margin != left_margin
            or self._last_view_width != view_width
            or len(self._last_lines or []) != len(lines)
        )

        if need_full_clear:
            print(self.term.home + self.term.clear, end='')
            self._last_lines = ["" for _ in range(len(lines))]
            self._last_status = None
            self._last_left_margin = left_margin
            self._last_view_width = view_width

        # Draw each line if changed
        for y, line in enumerate(lines):
            sel = selection_ranges[y] if selection_ranges and y < len(selection_ranges) else None
            style_line = styles_by_line[y] if styles_by_line and y < len(styles_by_line) else None
            new_disp = self._compose_display_line(line, view_width, sel, styles=style_line)
            old_disp = "" if self._last_lines is None else (self._last_lines[y] if y < len(self._last_lines) else "")
            if new_disp != old_disp:
                print(self.term.move(y, left_margin) + new_disp, end='')
                if self._last_lines is not None and y < len(self._last_lines):
                    self._last_lines[y] = new_disp

        # Status line at bottom
        if status_override:
            status_text = status_override.ljust(self.term.width)
        else:
            help_text = "F1 for help"
            status_text = (" " * (self.term.width - len(help_text) - 1)) + help_text
        if status_text != (self._last_status or ""):
            print(self.term.move(self.term.height - 1, 0) + status_text, end='')
            self._last_status = status_text

        # Finally position cursor
        if status_override and (": " in status_override):
            cursor_pos = len(status_override)
            print(self.term.move(self.term.height - 1, cursor_pos) + self.term.normal_cursor, end='', flush=True)
        else:
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

        Uses curtsies Input if available for normalized events; falls back to
        blessed if curtsies is unavailable.

        Args:
            timeout: Timeout in seconds (None for blocking, 0 for non-blocking)
            
        Returns:
            A key event object; for curtsies, a small shim with __str__.
        """
        if self._curtsies_input is not None:
            # Use select on stdin to implement timeouts
            if timeout is None:
                evt = next(self._curtsies_input)  # blocks
                return str(evt)
            else:
                t = 0.0 if timeout == 0 else float(timeout)
                r, _, _ = select.select([sys.stdin], [], [], t)
                if not r:
                    return None
                evt = next(self._curtsies_input)
                return str(evt)
        # Curtsies is required; if not initialized, return None
        return None
    
    @property
    def width(self):
        """Terminal width in columns."""
        return self.term.width
        
    @property  
    def height(self):
        """Terminal height in rows (excluding status line)."""
        return self.term.height - 1  # Reserve one line for status

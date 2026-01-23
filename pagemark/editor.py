"""Main editor controller for the word processor."""

import os
import sys
import select
import signal
import termios
import tempfile
import errno
import time
from typing import Optional
from .terminal import TerminalInterface
from .model import TextModel
from .view import TerminalTextView
from .print_dialog import PrintDialog, PrintAction
from .print_output import PrintOutput
from .print_formatter import PrintFormatter
from .keyboard import KeyboardHandler, KeyEvent, KeyType
from .constants import EditorConstants
from .commands import CommandRegistry
from .undo import UndoManager, ModelSnapshot, UndoEntry
from .session import get_session, SessionKeys
from .font_config import get_font_config
from .autosave import write_swap_file, delete_swap_file


class Editor:
    """Main word processor application controller."""

    def __init__(self):
        """Initialize the editor components."""
        self.terminal = TerminalInterface()
        self.keyboard = KeyboardHandler(self.terminal)
        self.view = TerminalTextView()
        # Session manager
        self.session = get_session()
        
        # Session settings
        self.spacing_double = self.session.get(SessionKeys.DOUBLE_SPACING, False)
        self.view.set_double_spacing(self.spacing_double)
        
        # Line length from session or default
        # This is the text area width (65 for 10-pitch, 72 for 12-pitch)
        self.VIEW_WIDTH = self.session.get(SessionKeys.LINE_LENGTH, EditorConstants.DOCUMENT_WIDTH)
        # Initialize view dimensions early
        self.view.num_rows = self.terminal.height
        self.view.num_columns = self.VIEW_WIDTH
        self.model = TextModel(self.view, paragraphs=[""])
        self.command_registry = CommandRegistry()  # Command pattern for key handling
        self.running = False
        self.error_mode = False  # True when terminal is too narrow
        # Create pipe for resize signaling
        self._resize_pipe_r, self._resize_pipe_w = os.pipe()
        # File handling
        self.filename = None
        self.modified = False
        self.status_message = None
        self.prompt_mode = None  # None, 'save_filename', 'save_filename_quit', 'quit_confirm', or 'help'
        self.prompt_input = ""
        self.help_visible = False  # Track if help screen is visible
        # Undo/redo
        self.undo = UndoManager()
        # Incremental search state
        self._isearch_origin = None  # tuple[int,int] of original cursor
        self._isearch_last_match = None  # tuple[int,int] of last match start
        # Autosave state
        self._last_edit_time: float | None = None
        self._last_autosave_time: float | None = None

    def _handle_resize(self, signum, frame):
        """Handle terminal resize signal."""
        del signum, frame # Unused
        # Write to pipe to wake up select()
        os.write(self._resize_pipe_w, EditorConstants.RESIZE_PIPE_MARKER)

    def _handle_sigint(self, signum, frame):
        """Handle SIGINT (Ctrl-C) - treat as copy command."""
        del signum, frame # Unused
        # Set a flag to process copy command
        self._ctrl_c_pressed = True
        # Write to pipe to wake up select()
        os.write(self._resize_pipe_w, b'C')

    def _calculate_autosave_timeout(self) -> float | None:
        """Calculate timeout for select() based on autosave timing.

        Returns:
            Timeout in seconds for select(), or None if no timeout needed.
        """
        # No autosave needed if document isn't modified or has no filename
        if not self.modified or not self.filename:
            return None

        now = time.monotonic()

        # Debounce: wait until 10s after last edit
        if self._last_edit_time is not None:
            debounce_remaining = (
                self._last_edit_time + EditorConstants.AUTOSAVE_DEBOUNCE_SECONDS
            ) - now
            if debounce_remaining > 0:
                return debounce_remaining

        # Backstop: if we've never autosaved, or 5 min since last autosave
        if self._last_autosave_time is not None:
            backstop_remaining = (
                self._last_autosave_time + EditorConstants.AUTOSAVE_BACKSTOP_SECONDS
            ) - now
            if backstop_remaining > 0:
                return backstop_remaining

        # Time to save - small timeout to trigger save soon
        return 0.1

    def _maybe_autosave(self) -> None:
        """Perform autosave if conditions are met."""
        # No autosave if document isn't modified or has no filename
        if not self.modified or not self.filename:
            return

        now = time.monotonic()

        # Check debounce condition: 10s since last edit
        debounce_met = (
            self._last_edit_time is not None
            and now - self._last_edit_time >= EditorConstants.AUTOSAVE_DEBOUNCE_SECONDS
        )

        # Check backstop condition: 5 min since last autosave (or never autosaved)
        backstop_met = (
            self._last_autosave_time is None
            or now - self._last_autosave_time >= EditorConstants.AUTOSAVE_BACKSTOP_SECONDS
        )

        if debounce_met or backstop_met:
            content = self.model.to_overstrike_text()
            if write_swap_file(self.filename, content):
                self._last_autosave_time = now

    def run(self):
        """Run the main editor loop."""
        self.terminal.setup()
        self.running = True
        # Set up signal handlers
        original_winch_handler = signal.signal(signal.SIGWINCH, self._handle_resize)
        # Preserve existing SIGINT handler; Ctrl-C is delivered as keystroke (ISIG disabled)
        original_int_handler = signal.getsignal(signal.SIGINT)

        try:
            # Main event loop
            with self.terminal.term.cbreak():
                # Disable flow control and special processing AFTER entering cbreak mode
                old_settings = None
                try:
                    old_settings = termios.tcgetattr(sys.stdin)
                    new_settings = list(old_settings)  # Make it mutable
                    # Disable IXON/IXOFF in input flags (index 0) to allow Ctrl-S and Ctrl-Q
                    new_settings[0] &= ~(termios.IXON | termios.IXOFF)
                    # Disable IEXTEN so Ctrl-V (VLNEXT) is not intercepted by the tty
                    # Disable ISIG so Ctrl-C arrives as a keystroke (handled by KeyboardHandler)
                    try:
                        new_settings[3] &= ~(termios.IEXTEN | termios.ISIG)
                    except AttributeError:
                        pass
                    termios.tcsetattr(sys.stdin, termios.TCSANOW, new_settings)
                except (termios.error, AttributeError, OSError):
                    pass

                # Initial draw
                need_draw = True

                while self.running:
                    # Only draw when needed
                    if need_draw:
                        # Check terminal width and update view dimensions
                        self.view.num_rows = self.terminal.height

                        # Check if terminal is wide enough
                        if self.terminal.width < EditorConstants.MIN_TERMINAL_WIDTH:
                            self.error_mode = True
                            self._draw_error()
                        else:
                            was_error = self.error_mode
                            self.error_mode = False
                            # Render when transitioning out of error mode, first time, or after resize
                            if was_error or not hasattr(self, '_rendered_once'):
                                self.view.render()
                                self._rendered_once = True
                            # Draw current state
                            self._draw()

                        need_draw = False

                    # Calculate select timeout based on autosave timing
                    timeout = self._calculate_autosave_timeout()

                    # Wait for input on stdin or resize pipe
                    # Use file descriptor 0 for stdin to work in all environments
                    ready, _, _ = select.select([0, self._resize_pipe_r], [], [], timeout)

                    if not ready:
                        # Timeout - check autosave
                        self._maybe_autosave()
                        # No UI change needed from autosave
                    elif self._resize_pipe_r in ready:
                        # Clear the pipe (resize wake)
                        os.read(self._resize_pipe_r, 1024)
                        if self.running:
                            # Force re-render on resize
                            if hasattr(self, '_rendered_once'):
                                delattr(self, '_rendered_once')
                            need_draw = True
                    elif 0 in ready:
                        # Handle input (non-blocking since select says it's ready)
                        key_event = self.keyboard.get_key_event(timeout=0)
                        if key_event:
                            # Process key and schedule a draw; diff'ing will minimize output
                            was_modified = self._handle_key_event(key_event)
                            need_draw = True
                            # Track edit time for autosave debounce
                            if was_modified:
                                self._last_edit_time = time.monotonic()

                # Restore terminal settings before exiting cbreak
                if old_settings:
                    try:
                        termios.tcsetattr(sys.stdin, termios.TCSANOW, old_settings)
                    except (termios.error, OSError):
                        # Best-effort restore on exit; failing to restore shouldn't crash the app
                        pass

        except KeyboardInterrupt:
            # With ISIG disabled, this should not be raised; keep for safety
            pass
        finally:
            # Restore original signal handlers
            signal.signal(signal.SIGWINCH, original_winch_handler)
            signal.signal(signal.SIGINT, original_int_handler)
            # Close pipes
            os.close(self._resize_pipe_r)
            os.close(self._resize_pipe_w)
            self.terminal.cleanup()

    def _draw(self):
        """Draw the current editor state to terminal."""
        # Show help screen if active
        if self.help_visible:
            self._draw_help()
            return

        # Calculate left margin for centering
        left_margin = (self.terminal.width - self.VIEW_WIDTH) // 2

        # Prepare status override if in prompt mode or showing a message
        status_override = None
        cursor_in_status = False  # Flag to indicate if cursor should be in status line
        
        if self.prompt_mode in ('save_filename', 'save_filename_quit'):
            status_override = f" File to save in: {self.prompt_input}"
            cursor_in_status = True
        elif self.prompt_mode == 'quit_confirm':
            status_override = " Save file? (y, n) "
            cursor_in_status = True
        elif self.prompt_mode == 'pdf_filename':
            status_override = f" Save PDF as: {self.prompt_input}"
            cursor_in_status = True
        elif self.prompt_mode == 'isearch':
            not_found = ''
            if self.prompt_input:
                # Indicate not found if we have a query but no last match
                if self._isearch_last_match is None:
                    not_found = ' (no match)'
            status_override = f" I-search: {self.prompt_input}{not_found}"
            cursor_in_status = False  # Cursor stays in text during search
        elif self.status_message:
            status_override = f" {self.status_message}"
            cursor_in_status = False

        # Get selection ranges for highlighting and diff-paint frame
        selection_ranges = self.view.get_selection_ranges()

        self.terminal.update_frame(
            self.view.lines,
            self.view.visual_cursor_y,
            self.view.visual_cursor_x,
            left_margin,
            self.VIEW_WIDTH,
            status_override,
            selection_ranges,
            getattr(self.view, 'line_styles', None),
            cursor_in_status=cursor_in_status
        )

    def _snapshot_state(self) -> ModelSnapshot:
        # Copy paragraphs and styles (deep copy masks)
        paragraphs_copy = list(self.model.paragraphs)
        styles_copy = [list(row) for row in getattr(self.model, 'styles', [])]
        cp = self.model.cursor_position
        sel_start = self.model.selection_start
        sel_end = self.model.selection_end
        start_tuple = None if sel_start is None else (sel_start.paragraph_index, sel_start.character_index)
        end_tuple = None if sel_end is None else (sel_end.paragraph_index, sel_end.character_index)
        caret_style = getattr(self.model, 'caret_style', 0)
        return ModelSnapshot(
            paragraphs=paragraphs_copy,
            styles=styles_copy,
            caret_style=caret_style,
            cursor_paragraph_index=cp.paragraph_index,
            cursor_character_index=cp.character_index,
            selection_start=start_tuple,
            selection_end=end_tuple,
        )

    def _apply_snapshot(self, snap: ModelSnapshot):
        # Restore model state and redraw
        self.model.paragraphs = list(snap.paragraphs)
        if hasattr(snap, 'styles') and snap.styles is not None:
            self.model.styles = [list(row) for row in snap.styles]
        if hasattr(snap, 'caret_style'):
            self.model.caret_style = snap.caret_style
        self.model.cursor_position.paragraph_index = snap.cursor_paragraph_index
        self.model.cursor_position.character_index = snap.cursor_character_index
        if snap.selection_start is None:
            self.model.selection_start = None
        else:
            from .model import CursorPosition
            self.model.selection_start = CursorPosition(*snap.selection_start)
        if snap.selection_end is None:
            self.model.selection_end = None
        else:
            from .model import CursorPosition
            self.model.selection_end = CursorPosition(*snap.selection_end)
        # Modified flag reflects that buffer differs from last saved content
        self.modified = True
        self.view.render()

    def _draw_error(self):
        """Draw error message when terminal is too narrow."""
        self.terminal.draw_error_message(
            EditorConstants.TERMINAL_TOO_NARROW_MESSAGE.format(EditorConstants.MIN_TERMINAL_WIDTH),
            EditorConstants.CURRENT_WIDTH_MESSAGE.format(self.terminal.width)
        )

    def _draw_help(self):
        """Draw the help screen."""
        term = self.terminal.term

        # Clear screen
        print(term.clear(), end='')

        # Draw centered, bold title at top
        title = "Help"
        # Be defensive: tests may mock term without setting width
        try:
            width = int(getattr(term, 'width', 80))
        except (TypeError, ValueError):
            width = 80
        title_pos = (width - len(title)) // 2
        # Use string coercion to avoid MagicMock arithmetic swallowing content in tests
        print(f"{term.move(1, title_pos)}{term.bold}{title}{term.normal}", end='')

        # Help content
        help_lines = [
            "",
            "FILE                         NAVIGATION",
            "  Ctrl-S    Save              Alt-←/→    Word left/right",
            "  Ctrl-Q    Quit              Alt-B/F    Word left/right",
            "  Ctrl-F    Search            Alt-↑/↓    Paragraph back/forward",
            "  Ctrl-P    Print             Ctrl-A     Beginning of line",
            "  Ctrl-W    Word count        Ctrl-E     End of line",
            "                              Home       Beginning of document",
            "                              End        End of document",
            "",
            "EDITING",
            "  Tab       Indent (5 spaces)  Shift-←/→  Extend selection",
            "  Ctrl-D    Delete char        Shift-↑/↓  Extend selection",
            "  Ctrl-K    Kill line          Ctrl-X     Cut line",
            "  Alt-M     Center line        Ctrl-C     Copy line",
            "  Ctrl-T    Transpose chars    Ctrl-V     Paste",
            "  Alt-Bksp  Delete word        Ctrl-U     Underline toggle",
            "  Ctrl-B    Bold toggle",
            "",
            "UNDO",
            "  Ctrl-Z    Undo              Ctrl-Y     Redo",
        ]

        # Center the help content vertically (accounting for title)
        try:
            height = int(getattr(term, 'height', 24))
        except (TypeError, ValueError):
            height = 24
        content_start_y = max(3, (height - len(help_lines)) // 2)

        # Calculate horizontal centering
        max_line_length = max(len(line) for line in help_lines)
        left_margin = max(0, (width - max_line_length) // 2)

        # Draw help content
        for i, line in enumerate(help_lines):
            print(f"{term.move(content_start_y + i, left_margin)}{line}", end='')

        # Draw status line at bottom
        status_text = " Press any key to continue"
        print(f"{term.move(term.height - 1, 0)}{status_text}", end='')

        # Hide cursor
        print(term.hide_cursor, end='', flush=True)

    def show_help(self):
        """Show the help screen."""
        self.help_visible = True

    def hide_help(self):
        """Hide the help screen and return to editor."""
        self.help_visible = False
        # Force re-render
        if hasattr(self, '_rendered_once'):
            delattr(self, '_rendered_once')
        # Invalidate terminal frame since help drew directly to screen
        self.terminal.invalidate_frame()

    def _handle_key_event(self, key_event: KeyEvent) -> bool:
        """Handle a keyboard event and update model/view state.

        Editor always schedules a draw after handling; terminal diffing ensures
        minimal updates are written to the screen.

        Returns:
            True if the document was modified by this key event.
        """
        # If help is visible, any key dismisses it
        if self.help_visible:
            self.hide_help()
            return False

        # Clear status message on any keypress (except in prompt mode)
        if self.status_message and not self.prompt_mode:
            self.status_message = None

        # Handle prompt modes first
        if self._handle_prompt_mode(key_event):
            return False

        # Don't process other keys if in error mode
        if self.error_mode:
            return False

        # Handle ESC key by itself
        if key_event.key_type == KeyType.SPECIAL and key_event.value == 'escape':
            # Just ESC - could be used for canceling operations
            return False

        # Execute command
        was_modified = self.command_registry.execute(self, key_event)
        if was_modified:
            self.modified = True
        return was_modified

    def _handle_prompt_mode(self, key_event: KeyEvent) -> bool:
        """Handle input in prompt mode.

        Returns:
            True if in prompt mode and event was handled
        """
        if self.prompt_mode in ('save_filename', 'save_filename_quit'):
            self._handle_filename_prompt(key_event)
            return True
        elif self.prompt_mode == 'quit_confirm':
            self._handle_quit_confirm(key_event)
            return True
        elif self.prompt_mode == 'pdf_filename':
            self._handle_pdf_filename_prompt(key_event)
            return True
        elif self.prompt_mode == 'isearch':
            self._handle_isearch_prompt(key_event)
            return True
        return False

    # --- Incremental search (Ctrl-F) ---
    def start_incremental_search(self) -> None:
        """Enter incremental search mode starting at current cursor."""
        # Check for empty document
        if not self.model.paragraphs:
            self.status_message = "No text to search"
            return
            
        cp = self.model.cursor_position
        self._isearch_origin = (cp.paragraph_index, cp.character_index)
        self._isearch_last_match = None
        self.prompt_mode = 'isearch'
        self.prompt_input = ""
        # Show immediate prompt
        self.status_message = None

    # ASCII printable character threshold
    _MIN_PRINTABLE_ORD = 32
    
    def _handle_isearch_prompt(self, key_event: KeyEvent) -> None:
        """Handle key events during incremental search."""
        # Cancel on ESC or Ctrl-G
        if (key_event.key_type == KeyType.SPECIAL and key_event.value == 'escape') or \
           (key_event.key_type == KeyType.CTRL and key_event.value == 'g'):
            # Restore original cursor position
            if self._isearch_origin is not None:
                pi, ci = self._isearch_origin
                self.model.cursor_position.paragraph_index = pi
                self.model.cursor_position.character_index = ci
                self.model._update_caret_style_from_position()
                self.view.render()
            self.prompt_mode = None
            self.prompt_input = ""
            self._isearch_origin = None
            self._isearch_last_match = None
            return

        # Accept with Enter: keep current location, exit
        if key_event.key_type == KeyType.SPECIAL and key_event.value == 'enter':
            self.prompt_mode = None
            self._isearch_origin = None
            self._isearch_last_match = None
            return

        # Next match on Ctrl-F while in isearch and have a query
        if key_event.key_type == KeyType.CTRL and key_event.value == 'f':
            if self.prompt_input:
                self._isearch_find_next(from_current=True)
            return

        # Backspace edits query
        if key_event.key_type == KeyType.SPECIAL and key_event.value == 'backspace':
            if self.prompt_input:
                self.prompt_input = self.prompt_input[:-1]
                self._isearch_update()
            else:
                # Nothing to delete; keep origin
                pass
            return

        # Regular character appends to query
        if key_event.key_type == KeyType.REGULAR:
            ch = key_event.value
            # Accept any Unicode character that's printable
            if ch and (ch.isprintable() or ch == ' '):
                self.prompt_input += ch
                self._isearch_update()
            return

        # Ignore other keys in isearch
        return

    def _isearch_update(self) -> None:
        """Update search position after query change."""
        if not self.prompt_input:
            # No query: reset to origin
            if self._isearch_origin is not None:
                pi, ci = self._isearch_origin
                self.model.cursor_position.paragraph_index = pi
                self.model.cursor_position.character_index = ci
                self.model._update_caret_style_from_position()
                self.view.render()
                self._isearch_last_match = None
            return
        # Find first match at/after origin
        if self._isearch_origin is None:
            # Safety: use current pos if origin lost
            cp = self.model.cursor_position
            start = (cp.paragraph_index, cp.character_index)
        else:
            start = self._isearch_origin
        match = self._find_forward(self.prompt_input, start)
        if match is not None:
            self._move_cursor_to(match)
            self._isearch_last_match = match
        else:
            # No match found - stay at current position
            self._isearch_last_match = None

    def _isearch_find_next(self, from_current: bool = False) -> None:
        """Find next match after last match (or origin if none)."""
        if not self.prompt_input:
            return
        if from_current and self._isearch_last_match is not None:
            pi, ci = self._isearch_last_match
            start = (pi, ci + 1)
        elif self._isearch_last_match is not None:
            start = (self._isearch_last_match[0], self._isearch_last_match[1] + 1)
        else:
            start = self._isearch_origin or (self.model.cursor_position.paragraph_index, self.model.cursor_position.character_index)
        match = self._find_forward(self.prompt_input, start)
        if match is not None:
            self._move_cursor_to(match)
            self._isearch_last_match = match

    def _move_cursor_to(self, pos: tuple[int, int]) -> None:
        pi, ci = pos
        self.model.cursor_position.paragraph_index = pi
        self.model.cursor_position.character_index = ci
        self.model._update_caret_style_from_position()
        self.view.render()

    def _find_forward(self, query: str, start: tuple[int, int]) -> Optional[tuple[int, int]]:
        """Find query at/after start. Case-insensitive search.

        Returns start position of match or None.
        """
        q = query.lower()
        paras = self.model.paragraphs
        start_pi, start_ci = start
        # Current paragraph from start_ci
        if 0 <= start_pi < len(paras):
            idx = paras[start_pi].lower().find(q, max(0, start_ci))
            if idx != -1:
                return (start_pi, idx)
        # Subsequent paragraphs
        for pi in range(start_pi + 1, len(paras)):
            idx = paras[pi].lower().find(q)
            if idx != -1:
                return (pi, idx)
        return None

    def _handle_backspace(self):
        """Handle backspace key - delete character before cursor."""
        self.model.backspace()

    def load_file(self, filename: str):
        """Load a file into the editor.

        Args:
            filename: Path to file to load
        """
        self.filename = filename
        try:
            with open(filename, 'r', encoding='utf-8') as f:
                content = f.read()
                # Parse as overstrike to support styled documents; plain text is handled too
                self.model = TextModel.from_overstrike_text(self.view, content)
                self.view.render()
                self.modified = False
        except FileNotFoundError:
            # New file - start with empty document
            self.modified = False
        except Exception as e:
            print(f"Error loading file: {e}")
            sys.exit(1)
        
        # Load persisted settings for this document
        self.session.load_document_settings(self.filename)

    def load_from_content(self, filename: str, content: str):
        """Load content directly into the editor (for recovery).

        Args:
            filename: Path to associate with this document
            content: Content to load (typically from swap file)
        """
        self.filename = filename
        # Parse as overstrike to support styled documents; plain text is handled too
        self.model = TextModel.from_overstrike_text(self.view, content)
        self.view.render()
        # Mark as modified since content came from swap, not the actual file
        self.modified = True
        
        # Load persisted settings for this document
        self.session.load_document_settings(self.filename)

    def save_file(self, filename: str):
        """Save the current document to a file atomically.

        Args:
            filename: Path to save file to

        Returns:
            True if save succeeded, False otherwise
        """
        try:
            # Serialize with overstrike to preserve bold/underline
            try:
                content = self.model.to_overstrike_text()
            except (AttributeError, IndexError, KeyError):
                # Fall back to plain text if styles are corrupted or missing
                content = '\n'.join(self.model.paragraphs)

            # Write to a temporary file in the same directory for atomic save
            # This ensures we're on the same filesystem for the rename operation
            dir_name = os.path.dirname(filename) or '.'

            # Create temp file with same suffix as target
            suffix = os.path.splitext(filename)[1]
            with tempfile.NamedTemporaryFile(mode='w', encoding='utf-8',
                                           dir=dir_name, suffix=suffix,
                                           delete=False) as temp_file:
                temp_filename = temp_file.name
                temp_file.write(content)
                temp_file.flush()
                os.fsync(temp_file.fileno())  # Ensure data is written to disk

            # Atomic rename - this is atomic on POSIX systems
            # On Windows, it will overwrite existing file atomically
            os.replace(temp_filename, filename)

            self.filename = filename
            self.modified = False
            # Clean up swap file after successful save
            delete_swap_file(filename)
            self._last_autosave_time = None
            return True

        except PermissionError:
            self.status_message = f"Error: Permission denied saving {filename}"
            # Clean up temp file if it exists
            if 'temp_filename' in locals() and os.path.exists(temp_filename):
                try:
                    os.remove(temp_filename)
                except OSError:
                    # If cleanup fails (e.g., file already removed), ignore
                    pass
            return False
        except OSError as e:
            if e.errno == errno.ENOSPC:  # No space left on device
                self.status_message = f"Error: No space left on device"
            else:
                self.status_message = f"Error: Cannot save to {filename}"
            # Clean up temp file if it exists
            if 'temp_filename' in locals() and os.path.exists(temp_filename):
                try:
                    os.remove(temp_filename)
                except OSError:
                    # Ignore cleanup errors; saving already failed and user is notified
                    pass
            return False
        except Exception as e:
            self.status_message = f"Error: Cannot save to {filename}"
            # Clean up temp file if it exists
            if 'temp_filename' in locals() and os.path.exists(temp_filename):
                try:
                    os.remove(temp_filename)
                except OSError:
                    # Ignore cleanup errors; saving already failed and user is notified
                    pass
            return False

    def _handle_save(self):
        """Handle Ctrl-S save command."""
        if self.filename:
            # Save to existing file
            if self.save_file(self.filename):
                self.status_message = f"Saved to {self.filename}"
        else:
            # Need to prompt for filename
            self.prompt_mode = 'save_filename'
            self.prompt_input = ""

    def _handle_filename_prompt(self, key_event):
        """Handle keypress during filename prompt."""
        if (key_event.key_type == KeyType.SPECIAL and key_event.value == 'escape') or \
           (key_event.key_type == KeyType.CTRL and key_event.value == 'g'):  # ESC or Ctrl-G
            # Cancel prompt
            self.prompt_mode = None
            self.prompt_input = ""
        elif key_event.key_type == KeyType.SPECIAL and key_event.value == 'enter':
            # Save with entered filename
            if self.prompt_input:
                if self.save_file(self.prompt_input):
                    self.status_message = f"Saved to {self.prompt_input}"
                    # If we were saving before quit, quit now
                    if self.prompt_mode == 'save_filename_quit':
                        self.running = False
                self.prompt_mode = None
                self.prompt_input = ""
        elif key_event.key_type == KeyType.SPECIAL and key_event.value == 'backspace':
            # Delete character from prompt
            if self.prompt_input:
                self.prompt_input = self.prompt_input[:-1]
        elif key_event.key_type == KeyType.REGULAR:
            # Add character to prompt
            char = key_event.value
            if ord(char) >= 32:
                self.prompt_input += char

    def _handle_pdf_filename_prompt(self, key_event):
        """Handle keypress during PDF filename prompt."""
        if (key_event.key_type == KeyType.SPECIAL and key_event.value == 'escape') or \
           (key_event.key_type == KeyType.CTRL and key_event.value == 'g'):  # ESC or Ctrl-G
            # Cancel prompt
            self.prompt_mode = None
            self.prompt_input = ""
            self._pending_print_pages = None
            self.status_message = "PDF save cancelled"
        elif key_event.key_type == KeyType.SPECIAL and key_event.value == 'enter':
            # Save with entered filename
            if self.prompt_input and hasattr(self, '_pending_print_pages'):
                font_name = getattr(self, '_pending_print_font', 'Courier')
                page_runs = getattr(self, '_pending_print_page_runs', None)
                self._save_to_pdf(self._pending_print_pages, self.prompt_input, font_name, page_runs)
                # Save PDF filename to session
                self.session.set(SessionKeys.PDF_FILENAME, self.prompt_input)
                self._pending_print_pages = None
                self._pending_print_font = None
                if hasattr(self, '_pending_print_page_runs'):
                    self._pending_print_page_runs = None
            self.prompt_mode = None
            self.prompt_input = ""
        elif key_event.key_type == KeyType.SPECIAL and key_event.value == 'backspace':
            # Delete character from prompt
            if self.prompt_input:
                self.prompt_input = self.prompt_input[:-1]
        elif key_event.key_type == KeyType.REGULAR:
            # Add character to prompt
            char = key_event.value
            if ord(char) >= 32:
                self.prompt_input += char

    def _handle_quit_confirm(self, key_event):
        """Handle keypress during quit confirmation."""
        if key_event.key_type == KeyType.REGULAR:
            char = key_event.value.lower()
            if char == 'y':
                # Save and quit
                if self.filename:
                    self.save_file(self.filename)
                    self.running = False
                else:
                    # Need filename first
                    self.prompt_mode = 'save_filename_quit'
                    self.prompt_input = ""
            elif char == 'n':
                # Quit without saving
                self.running = False
            else:
                # Cancel quit
                self.prompt_mode = None

    def _handle_print(self):
        """Handle Ctrl-P print command."""
        # Clear screen for dialog
        self.terminal.clear_screen()

        # Show print dialog
        dialog = PrintDialog(self.model, self.terminal)
        # Initialize dialog spacing from session and refresh pages/preview
        # Pass spacing to dialog; actual page/preview rebuild handled in dialog.show()
        try:
            dialog.double_spacing = self.spacing_double
        except AttributeError:
            # Dialog may not have double_spacing attribute in older versions
            pass
        result = dialog.show()

        # Process the result
        if result.action == PrintAction.CANCEL:
            # User cancelled, just return to editor
            self.status_message = "Print cancelled"
        elif result.action == PrintAction.PRINT:
            # Print to printer
            font_config = dialog.get_font_config()
            pf = PrintFormatter(
                self.model.paragraphs, 
                double_spacing=dialog.double_spacing, 
                styles=getattr(self.model, 'styles', None),
                font_config=font_config
            )
            pf.format_pages()
            page_runs = pf.get_page_runs()
            pages_for_print = pf.pages
            self._print_to_printer(pages_for_print, result.printer_name, result.double_sided, page_runs, result.font_name)
        elif result.action == PrintAction.SAVE_PDF:
            # Save to PDF file - prompt for filename
            self.prompt_mode = 'pdf_filename'
            # Try to use saved PDF filename from session, otherwise use default
            saved_pdf_filename = self.session.get(SessionKeys.PDF_FILENAME)
            self.prompt_input = saved_pdf_filename if saved_pdf_filename else result.pdf_filename
            # Store pages and font for later use
            # Re-format with correct font configuration
            font_config = dialog.get_font_config()
            pf = PrintFormatter(
                self.model.paragraphs, 
                double_spacing=dialog.double_spacing, 
                styles=getattr(self.model, 'styles', None),
                font_config=font_config
            )
            pf.format_pages()
            self._pending_print_pages = pf.pages
            self._pending_print_font = result.font_name
            self._pending_print_page_runs = pf.get_page_runs()

        # Persist spacing choice in session and update view
        self.spacing_double = dialog.double_spacing
        self.view.set_double_spacing(self.spacing_double)
        self.session.set(SessionKeys.DOUBLE_SPACING, self.spacing_double)
        
        # Persist line length in session and update view if changed
        line_length = dialog.get_line_length()
        self.session.set(SessionKeys.LINE_LENGTH, line_length)
        
        # Update view width if changed
        if line_length != self.VIEW_WIDTH:
            self.VIEW_WIDTH = line_length
            self.view.num_columns = self.VIEW_WIDTH
            # Force model to recalculate visual positions
            if hasattr(self.model, 'notify_cursor_moved'):
                self.model.notify_cursor_moved()

        # Force full-screen redraw after returning from dialog
        # The dialog draws outside the editor's managed frame, so invalidate
        # the cached frame and force a re-render on the next loop iteration.
        self.terminal.invalidate_frame()
        if hasattr(self, '_rendered_once'):
            delattr(self, '_rendered_once')

    def _print_to_printer(self, pages, printer_name, double_sided, page_runs=None, font_name="Courier"):
        """Submit print job to printer.

        Args:
            pages: Formatted pages to print.
            printer_name: Name of the printer.
            double_sided: Whether to print double-sided.
            page_runs: Optional style runs for the pages.
            font_name: Font to use for PDF generation.
        """
        # Show progress message
        self.status_message = f"Printing to {printer_name}..."
        self._draw()

        # Perform the print operation
        try:
            output = PrintOutput(font_name)
        except Exception as e:
            # Use the specific error message
            self.status_message = f"✗ Font error: {e}"
            return
            
        # Set runs on output if there are any styled runs
        if page_runs:
            # Check if there are any non-empty run lines
            has_styled_content = any(any(line_runs for line_runs in page if line_runs) for page in page_runs)
            if has_styled_content:
                output.page_runs = page_runs
        success, error = output.print_to_printer(pages, printer_name, double_sided)

        if success:
            self.status_message = f"✓ Successfully printed to {printer_name}"
        else:
            self.status_message = f"✗ Print failed: {error}"

    def _save_to_pdf(self, pages, filename, font_name="Courier", page_runs=None):
        """Save pages to PDF file.

        Args:
            pages: Formatted pages to save.
            filename: Output PDF filename.
            font_name: Font to use for PDF generation.
            page_runs: Optional style runs for the pages.
        """
        # Show progress message
        self.status_message = f"Saving PDF to {filename}..."
        self._draw()

        # Validate path first
        try:
            output = PrintOutput(font_name)
        except Exception as e:
            # Use the specific error message
            self.status_message = f"✗ Font error: {e}"
            return
        valid, error = output.validate_output_path(filename)
        if not valid:
            self.status_message = f"✗ {error}"
            return

        # Set runs on output if there are any styled runs
        if page_runs:
            # Check if there are any non-empty run lines
            has_styled_content = any(any(line_runs for line_runs in page if line_runs) for page in page_runs)
            if has_styled_content:
                output.page_runs = page_runs
        
        # Use the provided pages (already formatted with correct line length)
        success, message = output.save_to_file(pages, filename)

        if success:
            if message:  # If there's a message
                self.status_message = f"✓ {message}"
            else:
                self.status_message = f"✓ Successfully saved PDF to {filename}"
        else:
            self.status_message = f"✗ {message}"

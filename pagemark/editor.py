"""Main editor controller for the word processor."""

import os
import sys
import select
import signal
import termios
import tempfile
import errno
from .terminal import TerminalInterface
from .model import TextModel
from .view import TerminalTextView
from .print_dialog import PrintDialog, PrintAction
from .print_output import PrintOutput
from .keyboard import KeyboardHandler, KeyEvent, KeyType
from .constants import EditorConstants
from .commands import CommandRegistry


class Editor:
    """Main word processor application controller."""

    def __init__(self):
        """Initialize the editor components."""
        self.terminal = TerminalInterface()
        self.keyboard = KeyboardHandler(self.terminal)
        self.view = TerminalTextView()
        # Fixed width for the view from constants
        self.VIEW_WIDTH = EditorConstants.DOCUMENT_WIDTH
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

    def run(self):
        """Run the main editor loop."""
        self.terminal.setup()
        self.running = True
        self._ctrl_c_pressed = False  # Flag for Ctrl-C detection

        # Set up signal handlers
        original_winch_handler = signal.signal(signal.SIGWINCH, self._handle_resize)
        original_int_handler = signal.signal(signal.SIGINT, self._handle_sigint)  # Custom handler for Ctrl-C

        try:
            # Main event loop
            with self.terminal.term.cbreak():
                # Disable flow control AFTER entering cbreak mode
                old_settings = None
                try:
                    old_settings = termios.tcgetattr(sys.stdin)
                    new_settings = list(old_settings)  # Make it mutable
                    # Disable IXON/IXOFF in input flags (index 0) to allow Ctrl-S and Ctrl-Q
                    new_settings[0] &= ~(termios.IXON | termios.IXOFF)
                    # Also disable IEXTEN in local flags so Ctrl-V (VLNEXT) is not intercepted by tty
                    try:
                        new_settings[3] &= ~termios.IEXTEN
                    except AttributeError:
                        pass
                    # Note: We DON'T disable ISIG here; KeyboardInterrupt is handled explicitly
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

                    # Wait for input on stdin or resize pipe
                    # Use file descriptor 0 for stdin to work in all environments
                    ready, _, _ = select.select([0, self._resize_pipe_r], [], [])
                    
                    if self._resize_pipe_r in ready:
                        # Clear the pipe
                        data = os.read(self._resize_pipe_r, 1024)
                        
                        # Check if this is a Ctrl-C signal
                        if self._ctrl_c_pressed:
                            self._ctrl_c_pressed = False
                            # Create synthetic Ctrl-C event for copy
                            from .keyboard import KeyEvent
                            ctrl_c_event = KeyEvent(
                                key_type=KeyType.CTRL,
                                value='c',
                                raw='\x03',
                                is_ctrl=True
                            )
                            self._handle_key_event(ctrl_c_event)
                            need_draw = True
                        elif self.running:
                            # Normal resize event
                            # Force re-render on resize
                            if hasattr(self, '_rendered_once'):
                                delattr(self, '_rendered_once')
                            need_draw = True
                    elif 0 in ready:
                        # Handle input (non-blocking since select says it's ready)
                        key_event = self.keyboard.get_key_event(timeout=0)
                        if key_event:
                            # Process all keys normally
                            self._handle_key_event(key_event)
                            need_draw = True
                
                # Restore terminal settings before exiting cbreak
                if old_settings:
                    try:
                        termios.tcsetattr(sys.stdin, termios.TCSANOW, old_settings)
                    except:
                        pass

        except KeyboardInterrupt:
            # Handle Ctrl-C gracefully
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
        if self.prompt_mode in ('save_filename', 'save_filename_quit'):
            status_override = f" File to save in: {self.prompt_input}"
        elif self.prompt_mode == 'quit_confirm':
            status_override = " Save file? (y, n) "
        elif self.prompt_mode == 'ps_filename':
            status_override = f" Save PS as: {self.prompt_input}"
        elif self.status_message:
            status_override = f" {self.status_message}"

        # Get selection ranges for highlighting
        selection_ranges = self.view.get_selection_ranges()
        
        self.terminal.draw_lines(
            self.view.lines,
            self.view.visual_cursor_y,
            self.view.visual_cursor_x,
            left_margin=left_margin,
            view_width=self.VIEW_WIDTH,
            status_override=status_override,
            selection_ranges=selection_ranges
        )

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
        title = "PAGEMARK HELP"
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
            "  Ctrl-P    Print             Ctrl-A     Beginning of line",
            "  Ctrl-W    Word count         Ctrl-E     End of line",
            "  F1        Help",
            "",
            "EDITING",
            "  Ctrl-D    Delete char",
            "  Ctrl-K    Kill line",
            "  Ctrl-^    Center line",
            "  Ctrl-T    Transpose chars",
            "  Ctrl-X    Cut line",
            "  Ctrl-C    Copy line",
            "  Ctrl-V    Paste",
            "  Alt-Bksp  Delete word"
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

    def _handle_key_event(self, key_event: KeyEvent):
        """Handle a keyboard event.

        Args:
            key_event: KeyEvent object with parsed key information
        """
        # If help is visible, any key dismisses it
        if self.help_visible:
            self.hide_help()
            return
            
        # Clear status message on any keypress (except in prompt mode)
        if self.status_message and not self.prompt_mode:
            self.status_message = None

        # Handle prompt modes first
        if self._handle_prompt_mode(key_event):
            return

        # Don't process other keys if in error mode
        if self.error_mode:
            return

        # Handle ESC key by itself
        if key_event.key_type == KeyType.SPECIAL and key_event.value == 'escape':
            # Just ESC - could be used for canceling operations
            return

        # Try to execute command from registry
        was_modified = self.command_registry.execute(self, key_event)
        if was_modified:
            self.modified = True
    
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
        elif self.prompt_mode == 'ps_filename':
            self._handle_ps_filename_prompt(key_event)
            return True
        return False

    def _handle_backspace(self):
        """Handle backspace key - delete character before cursor."""
        if self.model.cursor_position.character_index > 0:
            # Delete within paragraph
            para_idx = self.model.cursor_position.paragraph_index
            char_idx = self.model.cursor_position.character_index
            para = self.model.paragraphs[para_idx]
            self.model.paragraphs[para_idx] = para[:char_idx-1] + para[char_idx:]
            self.model.cursor_position.character_index -= 1
            self.view.render()
        elif self.model.cursor_position.paragraph_index > 0:
            # Join with previous paragraph
            self.model._join_with_previous_paragraph()
            self.view.render()

    def load_file(self, filename: str):
        """Load a file into the editor.

        Args:
            filename: Path to file to load
        """
        self.filename = filename
        try:
            with open(filename, 'r', encoding='utf-8') as f:
                content = f.read()
                paragraphs = content.split('\n') if content else [""]
                self.model = TextModel(self.view, paragraphs=paragraphs)
                self.view.render()
                self.modified = False
        except FileNotFoundError:
            # New file - start with empty document
            self.modified = False
        except Exception as e:
            print(f"Error loading file: {e}")
            sys.exit(1)

    def save_file(self, filename: str):
        """Save the current document to a file atomically.

        Args:
            filename: Path to save file to
        
        Returns:
            True if save succeeded, False otherwise
        """
        try:
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
            return True
            
        except PermissionError:
            self.status_message = f"Error: Permission denied saving {filename}"
            # Clean up temp file if it exists
            if 'temp_filename' in locals() and os.path.exists(temp_filename):
                try:
                    os.remove(temp_filename)
                except:
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
                except:
                    pass
            return False
        except Exception as e:
            self.status_message = f"Error: Cannot save to {filename}"
            # Clean up temp file if it exists
            if 'temp_filename' in locals() and os.path.exists(temp_filename):
                try:
                    os.remove(temp_filename)
                except:
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
    
    def _handle_ps_filename_prompt(self, key_event):
        """Handle keypress during PS filename prompt."""
        if (key_event.key_type == KeyType.SPECIAL and key_event.value == 'escape') or \
           (key_event.key_type == KeyType.CTRL and key_event.value == 'g'):  # ESC or Ctrl-G
            # Cancel prompt
            self.prompt_mode = None
            self.prompt_input = ""
            self._pending_print_pages = None
            self.status_message = "PS save cancelled"
        elif key_event.key_type == KeyType.SPECIAL and key_event.value == 'enter':
            # Save with entered filename
            if self.prompt_input and hasattr(self, '_pending_print_pages'):
                self._save_to_ps(self._pending_print_pages, self.prompt_input)
                self._pending_print_pages = None
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
        result = dialog.show()
        
        # Process the result
        if result.action == PrintAction.CANCEL:
            # User cancelled, just return to editor
            self.status_message = "Print cancelled"
        elif result.action == PrintAction.PRINT:
            # Print to printer
            self._print_to_printer(dialog.pages, result.printer_name, result.double_sided)
        elif result.action == PrintAction.SAVE_PS:
            # Save to PS file - prompt for filename
            self.prompt_mode = 'ps_filename'
            self.prompt_input = result.ps_filename
            # Store pages for later use
            self._pending_print_pages = dialog.pages
        
        # Force redraw after returning from dialog
        if hasattr(self, '_rendered_once'):
            delattr(self, '_rendered_once')
    
    def _print_to_printer(self, pages, printer_name, double_sided):
        """Submit print job to printer.
        
        Args:
            pages: Formatted pages to print.
            printer_name: Name of the printer.
            double_sided: Whether to print double-sided.
        """
        # Show progress message
        self.status_message = f"Printing to {printer_name}..."
        self._draw()
        
        # Perform the print operation
        output = PrintOutput()
        success, error = output.print_to_printer(pages, printer_name, double_sided)
        
        if success:
            self.status_message = f"✓ Successfully printed to {printer_name}"
        else:
            self.status_message = f"✗ Print failed: {error}"
    
    def _save_to_ps(self, pages, filename):
        """Save pages to PostScript file.
        
        Args:
            pages: Formatted pages to save.
            filename: Output PS filename.
        """
        # Show progress message
        self.status_message = f"Saving PS to {filename}..."
        self._draw()
        
        # Validate path first
        output = PrintOutput()
        valid, error = output.validate_output_path(filename)
        if not valid:
            self.status_message = f"✗ {error}"
            return
        
        # Perform the save operation
        success, message = output.save_to_file(pages, filename)
        
        if success:
            if message:  # If there's a message
                self.status_message = f"✓ {message}"
            else:
                self.status_message = f"✓ Successfully saved PS to {filename}"
        else:
            self.status_message = f"✗ {message}"

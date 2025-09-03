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


class Editor:
    """Main word processor application controller."""

    def __init__(self):
        """Initialize the editor components."""
        self.terminal = TerminalInterface()
        self.view = TerminalTextView()
        # Fixed width of 65 characters for the view
        self.VIEW_WIDTH = 65
        # Initialize view dimensions early
        self.view.num_rows = self.terminal.height
        self.view.num_columns = self.VIEW_WIDTH
        self.model = TextModel(self.view, paragraphs=[""])
        self.running = False
        self.error_mode = False  # True when terminal is too narrow
        # Create pipe for resize signaling
        self._resize_pipe_r, self._resize_pipe_w = os.pipe()
        # File handling
        self.filename = None
        self.modified = False
        self.status_message = None
        self.prompt_mode = None  # None, 'save_filename', 'save_filename_quit', or 'quit_confirm'
        self.prompt_input = ""
        # Buffer for building escape sequences
        self.escape_buffer = ""

    def _handle_resize(self, signum, frame):
        """Handle terminal resize signal."""
        del signum, frame # Unused
        # Write to pipe to wake up select()
        os.write(self._resize_pipe_w, b'R')

    def run(self):
        """Run the main editor loop."""
        self.terminal.setup()
        self.running = True

        # Set up signal handler for terminal resize
        original_handler = signal.signal(signal.SIGWINCH, self._handle_resize)

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
                        if self.terminal.width < self.VIEW_WIDTH:
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
                        os.read(self._resize_pipe_r, 1024)
                        # Check if we should continue (pipe can be used to wake for quit too)
                        if self.running:
                            # Force re-render on resize
                            if hasattr(self, '_rendered_once'):
                                delattr(self, '_rendered_once')
                            need_draw = True
                    elif 0 in ready:
                        # Handle input (non-blocking since select says it's ready)
                        key = self.terminal.get_key(timeout=0)
                        if key:
                            # Process keys
                            self._handle_key(key)
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
            # Restore original signal handler
            signal.signal(signal.SIGWINCH, original_handler)
            # Close pipes
            os.close(self._resize_pipe_r)
            os.close(self._resize_pipe_w)
            self.terminal.cleanup()

    def _draw(self):
        """Draw the current editor state to terminal."""
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

        self.terminal.draw_lines(
            self.view.lines,
            self.view.visual_cursor_y,
            self.view.visual_cursor_x,
            left_margin=left_margin,
            view_width=self.VIEW_WIDTH,
            status_override=status_override
        )

    def _draw_error(self):
        """Draw error message when terminal is too narrow."""
        self.terminal.draw_error_message(
            f"Terminal too narrow! Need at least {self.VIEW_WIDTH} columns.",
            f"Current width: {self.terminal.width} columns."
        )

    def _handle_key(self, key):
        """Handle a keypress event.

        Args:
            key: blessed.keyboard.Keystroke object
        """
        # Clear status message on any keypress (except in prompt mode)
        if self.status_message and not self.prompt_mode:
            self.status_message = None

        # Handle prompt modes first
        if self.prompt_mode in ('save_filename', 'save_filename_quit'):
            self._handle_filename_prompt(key)
            return
        elif self.prompt_mode == 'quit_confirm':
            self._handle_quit_confirm(key)
            return
        elif self.prompt_mode == 'ps_filename':
            self._handle_ps_filename_prompt(key)
            return

        # Check for quit command (Ctrl-Q)
        if (hasattr(key, 'is_sequence') and not key.is_sequence and str(key) == '\x11') or key == '\x11':  # Ctrl-Q
            if self.modified:
                self.prompt_mode = 'quit_confirm'
            else:
                self.running = False
            return

        # Check for save command (Ctrl-S)
        if (hasattr(key, 'is_sequence') and not key.is_sequence and str(key) == '\x13') or key == '\x13':  # Ctrl-S
            self._handle_save()
            return
        
        # Check for print command (Ctrl-P)
        if (hasattr(key, 'is_sequence') and not key.is_sequence and str(key) == '\x10') or key == '\x10':  # Ctrl-P
            self._handle_print()
            return

        # Don't process other keys if in error mode
        if self.error_mode:
            return

        key_str = str(key)
        
        # Build escape sequences
        if self.escape_buffer or key_str == '\x1b':
            # Start or continue building escape sequence
            self.escape_buffer += key_str
            
            # Check if we have a complete Alt sequence
            if self.escape_buffer in ('\x1b[1;3D', '\x1bb', '\x1b[D', '\x1bOD'):
                # Alt-left
                self.model.left_word()
                self.view.update_desired_x()
                self.escape_buffer = ""
                return
            elif self.escape_buffer in ('\x1b[1;3C', '\x1bf', '\x1b[C', '\x1bOC'):
                # Alt-right  
                self.model.right_word()
                self.view.update_desired_x()
                self.escape_buffer = ""
                return
            elif self.escape_buffer in ('\x1b\x7f', '\x1b\x08'):
                # Alt-backspace
                self.model.backward_kill_word()
                self.modified = True
                self.view.update_desired_x()
                self.escape_buffer = ""
                return
            
            # Check if this could still become a valid sequence
            potential_sequences = [
                '\x1b[1;3D', '\x1bb', '\x1b[D', '\x1bOD',  # Alt-left
                '\x1b[1;3C', '\x1bf', '\x1b[C', '\x1bOC',  # Alt-right
                '\x1b\x7f', '\x1b\x08'  # Alt-backspace
            ]
            
            # If buffer could be start of a valid sequence, keep accumulating
            for seq in potential_sequences:
                if seq.startswith(self.escape_buffer):
                    return  # Keep accumulating
                    
            # Not a valid sequence - clear buffer and handle as regular ESC
            if self.escape_buffer == '\x1b':
                # Just ESC by itself - clear and continue processing
                self.escape_buffer = ""
                return
            else:
                # Invalid escape sequence - clear buffer
                self.escape_buffer = ""
                return
        
        # Handle Ctrl shortcuts first (not sequences)
        if str(key) == '\x04':  # Ctrl-D (delete-char)
            self.model.delete_char()
            self.modified = True
            self.view.update_desired_x()
            return
        elif str(key) == '\x01':  # Ctrl-A (move-beginning-of-line)
            self.model.move_beginning_of_line()
            self.view.update_desired_x()
            return
        elif str(key) == '\x05':  # Ctrl-E (move-end-of-line)
            self.model.move_end_of_line()
            self.view.update_desired_x()
            return
        elif str(key) == '\x0b':  # Ctrl-K (kill-line)
            self.model.kill_line()
            self.modified = True
            self.view.update_desired_x()
            return
        
        
        # Handle special keys
        if key.is_sequence:
            if key.code == self.terminal.term.KEY_LEFT:
                self.model.left_char()
                self.view.update_desired_x()  # Reset desired X on horizontal movement
            elif key.code == self.terminal.term.KEY_RIGHT:
                self.model.right_char()
                self.view.update_desired_x()  # Reset desired X on horizontal movement
            elif key.code == self.terminal.term.KEY_UP:
                self.view.move_cursor_up()
            elif key.code == self.terminal.term.KEY_DOWN:
                self.view.move_cursor_down()
            elif key.code == self.terminal.term.KEY_BACKSPACE or key.code == 263:
                self._handle_backspace()
                self.modified = True
                self.view.update_desired_x()  # Reset desired X after editing
            elif key.code == self.terminal.term.KEY_ENTER:
                self.model.insert_text('\n')
                self.modified = True
                self.view.update_desired_x()  # Reset desired X after editing
            # Ignore any other sequences to prevent partial ESC sequences from being inserted
        else:
            # Regular character - insert it
            char = str(key)
            # Filter out control characters and escape sequences
            if not char.startswith('\x1b') and (ord(char[0]) >= 32 or char == '\t'):
                self.model.insert_text(char)
                self.modified = True
                self.view.update_desired_x()  # Reset desired X after typing

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
            prev_idx = self.model.cursor_position.paragraph_index - 1
            prev_para = self.model.paragraphs[prev_idx]
            curr_para = self.model.paragraphs[self.model.cursor_position.paragraph_index]

            # Combine paragraphs
            self.model.paragraphs[prev_idx] = prev_para + curr_para
            del self.model.paragraphs[self.model.cursor_position.paragraph_index]

            # Move cursor to join point
            self.model.cursor_position.paragraph_index = prev_idx
            self.model.cursor_position.character_index = len(prev_para)
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
    
    def _handle_filename_prompt(self, key):
        """Handle keypress during filename prompt."""
        if key == '\x1b' or key == '\x07':  # ESC or Ctrl-G
            # Cancel prompt
            self.prompt_mode = None
            self.prompt_input = ""
    
    def _handle_ps_filename_prompt(self, key):
        """Handle keypress during PS filename prompt."""
        if key == '\x1b' or key == '\x07':  # ESC or Ctrl-G
            # Cancel prompt
            self.prompt_mode = None
            self.prompt_input = ""
            self._pending_print_pages = None
            self.status_message = "PS save cancelled"
        elif key.code == self.terminal.term.KEY_ENTER:
            # Save with entered filename
            if self.prompt_input and hasattr(self, '_pending_print_pages'):
                self._save_to_ps(self._pending_print_pages, self.prompt_input)
                self._pending_print_pages = None
            self.prompt_mode = None
            self.prompt_input = ""
        elif key.code == self.terminal.term.KEY_BACKSPACE or key.code == 263:
            # Delete character from prompt
            if self.prompt_input:
                self.prompt_input = self.prompt_input[:-1]
        elif not key.is_sequence:
            # Add character to prompt
            char = str(key)
            if ord(char) >= 32:
                self.prompt_input += char
        elif key.code == self.terminal.term.KEY_ENTER:
            # Save with entered filename
            if self.prompt_input:
                if self.save_file(self.prompt_input):
                    self.status_message = f"Saved to {self.prompt_input}"
                    # If we were saving before quit, quit now
                    if self.prompt_mode == 'save_filename_quit':
                        self.running = False
                self.prompt_mode = None
                self.prompt_input = ""
        elif key.code == self.terminal.term.KEY_BACKSPACE or key.code == 263:
            # Delete character from prompt
            if self.prompt_input:
                self.prompt_input = self.prompt_input[:-1]
        elif not key.is_sequence:
            # Add character to prompt
            char = str(key)
            if ord(char) >= 32:
                self.prompt_input += char
    
    def _handle_quit_confirm(self, key):
        """Handle keypress during quit confirmation."""
        char = str(key).lower()
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

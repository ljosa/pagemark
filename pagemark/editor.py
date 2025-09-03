"""Main editor controller for the word processor."""

import os
import sys
import select
import signal
from .terminal import TerminalInterface
from .model import TextModel
from .view import TerminalTextView


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

        self.terminal.draw_lines(
            self.view.lines,
            self.view.visual_cursor_y,
            self.view.visual_cursor_x,
            left_margin=left_margin,
            view_width=self.VIEW_WIDTH
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
        # Check for quit command (Ctrl-Q)
        if key == '\x11':  # Ctrl-Q
            self.running = False
            return

        # Don't process other keys if in error mode
        if self.error_mode:
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
                self.view.update_desired_x()  # Reset desired X after editing
            elif key.code == self.terminal.term.KEY_ENTER:
                self.model.insert_text('\n')
                self.view.update_desired_x()  # Reset desired X after editing
        else:
            # Regular character - insert it
            char = str(key)
            # Filter out control characters except tab
            if ord(char) >= 32 or char == '\t':
                self.model.insert_text(char)
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
        try:
            with open(filename, 'r') as f:
                content = f.read()
                paragraphs = content.split('\n') if content else [""]
                self.model = TextModel(self.view, paragraphs=paragraphs)
                self.view.render()
        except FileNotFoundError:
            # New file - start with empty document
            pass
        except Exception as e:
            print(f"Error loading file: {e}")
            sys.exit(1)

    def save_file(self, filename: str):
        """Save the current document to a file.

        Args:
            filename: Path to save file to
        """
        try:
            content = '\n'.join(self.model.paragraphs)
            with open(filename, 'w') as f:
                f.write(content)
        except Exception:
            # In a real app, show error in status line
            pass

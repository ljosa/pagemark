"""Main editor controller for the word processor."""

import sys
from .terminal import TerminalInterface
from .model import TextModel
from .view import TerminalTextView


class Editor:
    """Main word processor application controller."""
    
    def __init__(self):
        """Initialize the editor components."""
        self.terminal = TerminalInterface()
        self.view = TerminalTextView()
        # Initialize view dimensions early
        self.view.num_rows = self.terminal.height
        self.view.num_columns = self.terminal.width
        self.model = TextModel(self.view, paragraphs=[""])
        self.running = False
        
    def run(self):
        """Run the main editor loop."""
        self.terminal.setup()
        self.running = True
        
        try:
            # Initialize view dimensions
            self.view.num_rows = self.terminal.height
            self.view.num_columns = self.terminal.width
            
            # Initial render
            self.view.render()
            
            # Main event loop
            with self.terminal.term.cbreak():
                while self.running:
                    # Draw current state
                    self._draw()
                    
                    # Handle input
                    key = self.terminal.get_key()
                    if key:
                        self._handle_key(key)
                        
        except KeyboardInterrupt:
            # Handle Ctrl-C gracefully
            pass
        finally:
            self.terminal.cleanup()
            
    def _draw(self):
        """Draw the current editor state to terminal."""
        self.terminal.draw_lines(
            self.view.lines,
            self.view.visual_cursor_y,
            self.view.visual_cursor_x
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
            
        # Handle special keys
        if key.is_sequence:
            if key.code == self.terminal.term.KEY_LEFT:
                self.model.left_char()
            elif key.code == self.terminal.term.KEY_RIGHT:
                self.model.right_char()
            elif key.code == self.terminal.term.KEY_BACKSPACE or key.code == 263:
                self._handle_backspace()
            elif key.code == self.terminal.term.KEY_ENTER:
                self.model.insert_text('\n')
        else:
            # Regular character - insert it
            char = str(key)
            # Filter out control characters except tab
            if ord(char) >= 32 or char == '\t':
                self.model.insert_text(char)
                
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
        except Exception as e:
            # In a real app, show error in status line
            pass
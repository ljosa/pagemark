"""Wrapper to run the existing editor with Textual terminal interface."""

from textual.app import App, ComposeResult
from textual.widgets import Static
from textual.reactive import var
from textual import work
import threading
import queue
import time

from .model import TextModel
from .view import TerminalTextView


class EditorDisplay(Static):
    """Widget to display the editor content."""
    pass


class TextualEditor(App):
    """Textual wrapper for the existing editor logic."""
    
    CSS = """
    EditorDisplay {
        background: $surface;
        color: $text;
        width: 100%;
        height: 100%;
        padding: 0;
        border: none;
    }
    """
    
    display_text = var("")
    
    def __init__(self, filename=None):
        super().__init__()
        self.filename = filename
        self.model = None
        self.view = None
        self.key_queue = queue.Queue()
        self.running = True
        self.modified = False
        self.status_message = None
        
    def compose(self) -> ComposeResult:
        yield EditorDisplay()
        
    def on_mount(self):
        """Initialize the editor when mounted."""
        # Create the model and view
        self.view = TerminalTextView()
        self.view.num_columns = 65
        self.view.num_rows = self.size.height
        
        self.model = TextModel(self.view, paragraphs=[""])
        
        # Load file if provided
        if self.filename:
            self.load_file(self.filename)
        
        # Start the render loop
        self.set_interval(0.1, self.update_display)
        
    def on_key(self, event):
        """Handle keyboard input."""
        key = event.key
        
        # Clear status message on any keypress (except when showing it)
        if self.status_message and key != "ctrl+s":
            self.status_message = None
        
        # Handle special keys
        if key == "ctrl+q":
            self.exit()
        elif key == "ctrl+s":
            self.save_file()
        elif key == "ctrl+a":
            self.model.move_beginning_of_line()
        elif key == "ctrl+e":
            self.model.move_end_of_line()
        elif key == "ctrl+d":
            self.model.delete_char()
        elif key == "ctrl+k":
            self.model.kill_line()
        elif key == "escape+b" or key == "alt+left":
            self.model.left_word()
        elif key == "escape+f" or key == "alt+right":
            self.model.right_word()
        elif key == "escape+backspace" or key == "alt+backspace":
            self.model.backward_kill_word()
            self.modified = True
        elif key == "up":
            self.view.move_cursor_up()
        elif key == "down":
            self.view.move_cursor_down()
        elif key == "left":
            self.model.left_char()
        elif key == "right":
            self.model.right_char()
        elif key == "backspace":
            self.handle_backspace()
            self.modified = True
        elif key == "enter":
            self.model.insert_text('\n')
            self.modified = True
        elif len(key) == 1:
            # Regular character
            self.model.insert_text(key)
            self.modified = True
        
        # Update display
        self.update_display()
    
    def handle_backspace(self):
        """Handle backspace key."""
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
            
            self.model.paragraphs[prev_idx] = prev_para + curr_para
            del self.model.paragraphs[self.model.cursor_position.paragraph_index]
            
            self.model.cursor_position.paragraph_index = prev_idx
            self.model.cursor_position.character_index = len(prev_para)
            self.view.render()
    
    def update_display(self):
        """Update the display with current editor state."""
        if not self.view or not self.model:
            return
            
        # Update view dimensions
        self.view.num_rows = self.size.height - 1  # Leave room for status line
        
        # Render the view
        self.view.render()
        
        # Calculate left margin to center the 65-character view
        terminal_width = self.size.width
        left_margin = max(0, (terminal_width - self.view.num_columns) // 2)
        margin_str = ' ' * left_margin
        
        # Get the display lines from the view and add margins
        display_lines = []
        for y in range(self.view.num_rows):
            if y < len(self.view.lines):
                line = self.view.lines[y]
                # Pad to width
                line = line.ljust(self.view.num_columns)
            else:
                line = ' ' * self.view.num_columns
            # Add left margin for centering
            display_lines.append(margin_str + line)
        
        # Add status line (full terminal width)
        if self.modified:
            mod_indicator = " [Modified]"
        else:
            mod_indicator = ""
        
        if self.filename:
            status = f" {self.filename}{mod_indicator}"
        else:
            status = f" [No file]{mod_indicator}"
        
        if self.status_message:
            status = f" {self.status_message}"
            
        # Status line spans full terminal width
        status = status.ljust(terminal_width)
        display_lines.append(status)
        
        # Add cursor visualization with margin offset
        cursor_y = self.view.visual_cursor_y
        cursor_x = self.view.visual_cursor_x + left_margin  # Adjust for margin
        if 0 <= cursor_y < len(display_lines) - 1:  # Don't put cursor on status line
            line = display_lines[cursor_y]
            if cursor_x < len(line):
                # Show cursor as inverse video or special char
                line = line[:cursor_x] + '█' + line[cursor_x+1:]
                display_lines[cursor_y] = line
        
        # Update the display widget
        display_text = '\n'.join(display_lines)
        widget = self.query_one(EditorDisplay)
        widget.update(display_text)
    
    def load_file(self, filename):
        """Load a file into the editor."""
        try:
            with open(filename, 'r') as f:
                content = f.read()
                # Split into paragraphs
                paragraphs = content.split('\n')
                self.model.paragraphs = paragraphs if paragraphs else ['']
                self.model.cursor_position.paragraph_index = 0
                self.model.cursor_position.character_index = 0
                self.filename = filename
                self.modified = False
                self.status_message = f"Loaded {filename}"
        except Exception as e:
            self.status_message = f"Error loading file: {e}"
    
    def save_file(self):
        """Save the current document."""
        if not self.filename:
            self.status_message = "No filename set"
            return
            
        try:
            content = '\n'.join(self.model.paragraphs)
            with open(self.filename, 'w') as f:
                f.write(content)
            self.modified = False
            self.status_message = f"Saved {self.filename}"
        except Exception as e:
            self.status_message = f"Error saving: {e}"


def main():
    """Run the editor with Textual interface."""
    import sys
    filename = sys.argv[1] if len(sys.argv) > 1 else None
    app = TextualEditor(filename=filename)
    app.run()


if __name__ == "__main__":
    main()
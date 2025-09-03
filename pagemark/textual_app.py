"""Clean Textual implementation using the existing model."""

from textual.app import App, ComposeResult
from textual.widgets import TextArea, Footer, Header
from textual.binding import Binding
from pathlib import Path

from .model import TextModel, CursorPosition
from .view import TerminalTextView


class PagemarkApp(App):
    """Textual app using existing TextModel."""
    
    CSS = """
    TextArea {
        background: $surface;
        border: none;
        scrollbar-size: 1 1;
    }
    """
    
    BINDINGS = [
        Binding("ctrl+q", "quit", "Quit"),
        Binding("ctrl+s", "save", "Save"),
        # Emacs bindings will be handled in the TextArea directly
    ]
    
    def __init__(self, filename=None):
        super().__init__()
        self.filename = filename
        self.text_area = None
        self.model = None
        self.view = None
        
    def compose(self) -> ComposeResult:
        """Create widgets."""
        yield Header()
        self.text_area = TextArea()
        
        # Disable line numbers and gutter
        self.text_area.show_line_numbers = False
        
        # Add custom key bindings to TextArea
        self._setup_keybindings()
        
        yield self.text_area
        yield Footer()
        
    def _setup_keybindings(self):
        """Set up Emacs-style keybindings on the TextArea."""
        # The TextArea widget handles most text editing already
        # We just need to add our custom Emacs bindings
        pass
        
    async def on_mount(self) -> None:
        """Load file when app starts."""
        # Create model and view for our logic
        self.view = TerminalTextView()
        self.view.num_columns = 65
        self.view.num_rows = self.size.height - 2  # Account for header/footer
        self.model = TextModel(self.view, paragraphs=[""])
        
        if self.filename:
            try:
                with open(self.filename, 'r') as f:
                    content = f.read()
                    self.text_area.load_text(content)
                    # Also load into our model
                    self.model.paragraphs = content.split('\n') if content else ['']
                self.sub_title = f"Editing: {self.filename}"
            except Exception as e:
                self.notify(f"Error loading file: {e}", severity="error")
        
        # Focus the text area
        self.text_area.focus()
        
    def action_quit(self) -> None:
        """Quit the application."""
        # Check if modified
        if self.text_area.text != self._get_original_text():
            # TODO: Add save prompt
            pass
        self.exit()
        
    def action_save(self) -> None:
        """Save the file."""
        if not self.filename:
            self.notify("No filename set", severity="warning")
            return
            
        try:
            content = self.text_area.text
            with open(self.filename, 'w') as f:
                f.write(content)
            self.notify(f"Saved to {self.filename}")
        except Exception as e:
            self.notify(f"Error saving: {e}", severity="error")
    
    def _get_original_text(self) -> str:
        """Get the original text for comparison."""
        if self.filename and Path(self.filename).exists():
            try:
                with open(self.filename, 'r') as f:
                    return f.read()
            except:
                pass
        return ""


def main():
    """Run the Textual app."""
    import sys
    filename = sys.argv[1] if len(sys.argv) > 1 else None
    app = PagemarkApp(filename=filename)
    app.run()


if __name__ == "__main__":
    main()
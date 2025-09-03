"""Print dialog UI for document printing."""

from typing import List, Optional, Tuple, NamedTuple
from enum import Enum
import blessed

from .print_formatter import PrintFormatter
from .print_preview import PrintPreview
from .printer_utils import PrinterManager
from .model import TextModel
from .terminal import TerminalInterface


class PrintAction(Enum):
    """Actions that can be taken from the print dialog."""
    CANCEL = "cancel"
    PRINT = "print"
    SAVE_PDF = "save_pdf"


class PrintOptions(NamedTuple):
    """Options selected in the print dialog."""
    action: PrintAction
    printer_name: Optional[str] = None
    double_sided: bool = False
    pdf_filename: Optional[str] = None


class PrintDialog:
    """Interactive print dialog for document printing."""
    
    def __init__(self, model: TextModel, terminal: TerminalInterface):
        """Initialize print dialog.
        
        Args:
            model: The text model containing the document.
            terminal: The terminal interface for display.
        """
        self.model = model
        self.terminal = terminal
        self.printer_manager = PrinterManager()
        
        # Format document into pages
        self.formatter = PrintFormatter(model.paragraphs)
        self.pages = self.formatter.format_pages()
        
        # Create preview generator
        self.preview = PrintPreview(self.pages)
        
        # Dialog state
        self.current_page = 0
        self.selected_output = 0  # Index in output options list
        self.double_sided = True
        
        # Build output options list (printers + PDF)
        self.output_options = self._build_output_list()
        
    def _build_output_list(self) -> List[str]:
        """Build list of output options (printers + PDF).
        
        Returns:
            List of output option names.
        """
        options = []
        
        # Add available printers
        printers = self.printer_manager.get_available_printers()
        options.extend(printers)
        
        # Add PDF option
        options.append("PDF File")
        
        # If no printers available, ensure PDF is an option
        if not options:
            options = ["PDF File"]
        
        # Try to select default printer
        default = self.printer_manager.get_default_printer()
        if default and default in options:
            self.selected_output = options.index(default)
        
        return options
    
    def show(self) -> PrintOptions:
        """Display the print dialog and handle user interaction.
        
        Returns:
            PrintOptions with the user's selections, or action=CANCEL if cancelled.
        """
        # Save terminal state
        original_cursor = self.terminal.term.hidden_cursor
        
        try:
            # Hide cursor during dialog
            print(self.terminal.term.hide_cursor, end='', flush=True)
            
            while True:
                self._render()
                
                # Get user input
                key = self.terminal.get_key()
                
                if key in (blessed.keyboard.Keystroke('\x1b'), 'c', 'C'):
                    # Escape or C - cancel
                    return PrintOptions(action=PrintAction.CANCEL)
                
                elif key in ('p', 'P'):
                    # Print/Save
                    return self._get_print_options()
                
                elif key in ('o', 'O'):
                    # Cycle through output options
                    self.selected_output = (self.selected_output + 1) % len(self.output_options)
                
                elif key in ('d', 'D'):
                    # Toggle double-sided
                    self.double_sided = not self.double_sided
                
                elif key.name == 'KEY_PGUP':
                    # Previous page
                    if self.current_page > 0:
                        self.current_page -= 1
                
                elif key.name == 'KEY_PGDOWN':
                    # Next page
                    if self.current_page < len(self.pages) - 1:
                        self.current_page += 1
                        
        finally:
            # Restore cursor visibility
            if not original_cursor:
                print(self.terminal.term.normal_cursor, end='', flush=True)
    
    def _render(self):
        """Render the print dialog."""
        term = self.terminal.term
        
        # Clear screen
        print(term.home + term.clear, end='')
        
        # Calculate layout
        dialog_width = 68
        dialog_height = 40
        left_margin = (term.width - dialog_width) // 2
        top_margin = (term.height - dialog_height) // 2
        
        # Draw dialog border and title
        self._draw_border(left_margin, top_margin, dialog_width, dialog_height)
        
        # Draw page preview on the left
        preview_left = left_margin + 2
        preview_top = top_margin + 3
        self._draw_preview(preview_left, preview_top)
        
        # Draw options on the right
        options_left = preview_left + 47  # 43 chars + 4 spacing
        options_top = top_margin + 3
        self._draw_options(options_left, options_top)
        
        # Draw navigation help
        help_top = top_margin + dialog_height - 2
        help_text = "PgUp/PgDn: Navigate pages"
        print(term.move(help_top, left_margin + 2) + help_text, end='', flush=True)
    
    def _draw_border(self, left: int, top: int, width: int, height: int):
        """Draw the dialog border and title."""
        term = self.terminal.term
        
        # Top border
        print(term.move(top, left) + "┌" + "─" * (width - 2) + "┐", end='')
        
        # Title
        title = "Print Document"
        title_pos = left + (width - len(title)) // 2
        print(term.move(top + 1, left) + "│" + " " * (width - 2) + "│", end='')
        print(term.move(top + 1, title_pos) + title, end='')
        
        # Separator after title
        print(term.move(top + 2, left) + "├" + "─" * (width - 2) + "┤", end='')
        
        # Side borders
        for y in range(3, height - 1):
            print(term.move(top + y, left) + "│", end='')
            print(term.move(top + y, left + width - 1) + "│", end='')
        
        # Bottom border
        print(term.move(top + height - 1, left) + "└" + "─" * (width - 2) + "┘", end='')
    
    def _draw_preview(self, left: int, top: int):
        """Draw the page preview."""
        term = self.terminal.term
        
        # Page indicator
        page_text = f"Page Preview ({self.current_page + 1}/{len(self.pages)})"
        print(term.move(top - 1, left) + page_text, end='')
        
        # Get preview with border
        preview_lines = self.preview.generate_preview_with_border(self.current_page)
        
        # Draw preview
        for i, line in enumerate(preview_lines):
            print(term.move(top + i, left) + line, end='')
    
    def _draw_options(self, left: int, top: int):
        """Draw the print options."""
        term = self.terminal.term
        y = top
        
        # Output selection
        print(term.move(y, left) + "[O]utput:", end='')
        y += 1
        
        for i, option in enumerate(self.output_options):
            if i == self.selected_output:
                marker = "[x] "
            else:
                marker = "[ ] "
            print(term.move(y, left) + marker + option, end='')
            y += 1
        
        y += 1
        
        # Double-sided option (only if printing to printer)
        if self.selected_output < len(self.output_options) - 1:  # Not PDF
            double_text = "YES" if self.double_sided else "NO"
            print(term.move(y, left) + f"[D]ouble-sided: {double_text}", end='')
            y += 2
        else:
            y += 2
        
        # Separator
        print(term.move(y, left) + "─" * 15, end='')
        y += 2
        
        # Action buttons
        print(term.move(y, left) + "[P]rint  [C]ancel", end='')
    
    def _get_print_options(self) -> PrintOptions:
        """Get the final print options based on current selections.
        
        Returns:
            PrintOptions with the current selections.
        """
        selected_option = self.output_options[self.selected_output]
        
        if selected_option == "PDF File":
            # PDF output
            return PrintOptions(
                action=PrintAction.SAVE_PDF,
                pdf_filename="output.pdf"  # Default, will be prompted later
            )
        else:
            # Printer output
            return PrintOptions(
                action=PrintAction.PRINT,
                printer_name=selected_option,
                double_sided=self.double_sided
            )
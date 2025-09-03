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
    SAVE_PS = "save_ps"


class PrintOptions(NamedTuple):
    """Options selected in the print dialog."""
    action: PrintAction
    printer_name: Optional[str] = None
    double_sided: bool = False
    ps_filename: Optional[str] = None


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
        
        # Build output options list (printers + PS File)
        self.output_options = self._build_output_list()
        
    def _build_output_list(self) -> List[str]:
        """Build list of output options (printers + PS File).
        
        Returns:
            List of output option names.
        """
        options = []
        
        # Add available printers
        printers = self.printer_manager.get_available_printers()
        options.extend(printers)
        
        # Add PS File option
        options.append("PS File")
        
        # If no printers available, ensure PS File is an option
        if not options:
            options = ["PS File"]
        
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
        
        # Calculate layout (wider to accommodate long printer names)
        dialog_width = min(100, term.width - 4)  # Use more width if available
        dialog_height = 38  # Slightly less height without borders
        left_margin = max(2, (term.width - dialog_width) // 2)
        top_margin = max(1, (term.height - dialog_height) // 2)
        
        # Draw title (no border)
        self._draw_title(left_margin, top_margin, dialog_width)
        
        # Draw page preview on the left
        preview_left = left_margin
        preview_top = top_margin + 2  # After title
        self._draw_preview(preview_left, preview_top)
        
        # Draw options on the right with more space
        options_left = preview_left + 48  # 45 chars for preview + 3 spacing
        options_top = top_margin + 2
        options_max_width = dialog_width - 48  # Remaining width for options
        self._draw_options(options_left, options_top, options_max_width)
        
        # Flush output
        print('', end='', flush=True)
    
    def _draw_title(self, left: int, top: int, width: int):
        """Draw the dialog title without borders."""
        term = self.terminal.term
        
        # Center the title
        title = "Print Document"
        title_pos = left + (width - len(title)) // 2
        print(term.move(top, title_pos) + term.bold + title + term.normal, end='')
    
    def _draw_preview(self, left: int, top: int):
        """Draw the page preview."""
        term = self.terminal.term
        
        # Get preview with border
        preview_lines = self.preview.generate_preview_with_border(self.current_page)
        
        # Draw preview
        for i, line in enumerate(preview_lines):
            print(term.move(top + i, left) + line, end='')
        
        # Draw page info and navigation help at bottom right of preview
        page_text = f"Page {self.current_page + 1}/{len(self.pages)}"
        nav_text = "PgUp/PgDn: Navigate"
        
        # Position at bottom right of preview box
        info_y = top + len(preview_lines)
        print(term.move(info_y, left) + page_text, end='')
        print(term.move(info_y, left + 45 - len(nav_text)) + nav_text, end='')
    
    def _draw_options(self, left: int, top: int, max_width: int):
        """Draw the print options.
        
        Args:
            left: Left position
            top: Top position
            max_width: Maximum width available for options
        """
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
            # Truncate option if it's too long
            display_option = option[:max_width - 4] if len(option) > max_width - 4 else option
            print(term.move(y, left) + marker + display_option, end='')
            y += 1
        
        y += 1
        
        # Double-sided option (only if printing to printer)
        if self.selected_output < len(self.output_options) - 1:  # Not PS File
            double_text = "YES" if self.double_sided else "NO"
            print(term.move(y, left) + f"[D]ouble-sided: {double_text}", end='')
            y += 2
        else:
            y += 2
        
        # Separator
        sep_width = min(25, max_width)
        print(term.move(y, left) + "─" * sep_width, end='')
        y += 2
        
        # Action buttons
        print(term.move(y, left) + "[P]rint  [C]ancel", end='')
    
    def _get_print_options(self) -> PrintOptions:
        """Get the final print options based on current selections.
        
        Returns:
            PrintOptions with the current selections.
        """
        selected_option = self.output_options[self.selected_output]
        
        if selected_option == "PS File":
            # PS File output
            return PrintOptions(
                action=PrintAction.SAVE_PS,
                ps_filename="output.ps"  # Default, will be prompted later
            )
        else:
            # Printer output
            return PrintOptions(
                action=PrintAction.PRINT,
                printer_name=selected_option,
                double_sided=self.double_sided
            )
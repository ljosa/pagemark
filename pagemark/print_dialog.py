"""Print dialog UI for document printing."""

from typing import List, Optional, Tuple, NamedTuple
from enum import Enum
import blessed
import os
import logging

from .print_formatter import PrintFormatter
from .print_preview import PrintPreview
from .printer_utils import PrinterManager
from .model import TextModel
from .terminal import TerminalInterface
from .keyboard import KeyboardHandler, KeyType
from .font_config import FontConfig, get_font_config
from .session import get_session, SessionKeys

logger = logging.getLogger(__name__)


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
    font_name: str = "Courier"  # Default to Courier


class PrintDialog:
    """Interactive print dialog for document printing."""
    
    def __init__(self, model: TextModel, terminal: Optional[TerminalInterface], double_spacing: bool = False):
        """Initialize print dialog.
        
        Args:
            model: The text model containing the document.
            terminal: The terminal interface for display (optional for testing).
            double_spacing: Initial double spacing setting.
        """
        self.model = model
        self.terminal = terminal
        self.printer_manager = PrinterManager()
        self.session = get_session()
        
        # Dialog state
        self.current_page = 0
        self.selected_output = 0  # Index in output options list
        
        # Restore double-sided setting from session
        self.double_sided = self.session.get(SessionKeys.DUPLEX_PRINTING, True)
        
        # Restore or initialize spacing
        self.double_spacing = self.session.get(SessionKeys.DOUBLE_SPACING, double_spacing)
        
        # Font selection state
        self.available_fonts = self._detect_available_fonts()
        
        # Restore font selection from session with bounds checking
        saved_font = self.session.get(SessionKeys.FONT_NAME)
        if saved_font and saved_font in self.available_fonts:
            self.selected_font_index = self.available_fonts.index(saved_font)
        else:
            self.selected_font_index = 0  # Default to Courier
            self.session.set(SessionKeys.FONT_NAME, self.available_fonts[0])
        
        # Get font configuration
        self.font_config = self._get_current_font_config()
        self.line_length = self.font_config.text_width
        self.session.set(SessionKeys.LINE_LENGTH, self.line_length)
        
        # Format document into pages with appropriate line length
        styles = getattr(model, 'styles', None)
        self.formatter = PrintFormatter(
            model.paragraphs, 
            double_spacing=self.double_spacing, 
            styles=styles, 
            line_length=self.line_length,
            font_config=self.font_config
        )
        self.pages = self.formatter.format_pages()
        
        # Create preview generator
        self._create_preview()
        
        # Build output options list (printers + PDF File)
        self.output_options = self._build_output_list()
        
    def _build_output_list(self) -> List[str]:
        """Build list of output options (printers + PDF File).
        
        Returns:
            List of output option names.
        """
        options = []
        
        # Add available printers
        printers = self.printer_manager.get_available_printers()
        options.extend(printers)
        
        # Add PDF File option
        options.append("PDF File")
        
        # If no printers available, ensure PDF File is an option
        if not options:
            options = ["PDF File"]
        
        # Try to restore saved printer/output from session
        saved_printer = self.session.get(SessionKeys.PRINTER_NAME)
        if saved_printer and saved_printer in options:
            self.selected_output = options.index(saved_printer)
        else:
            # Try to select default printer
            default = self.printer_manager.get_default_printer()
            if default and default in options:
                self.selected_output = options.index(default)
        
        return options
    
    def _detect_available_fonts(self) -> List[str]:
        """Detect available fonts for PDF generation.
        
        Returns:
            List of available font names. Courier is always first.
        """
        from .pdf_generator import PDFGenerator, FontLoadError
        
        fonts = ["Courier"]  # Always available (built-in PDF font)
        
        # Test if Prestige Elite Std can actually be loaded
        try:
            # Try to create a generator with the font
            test_gen = PDFGenerator("Prestige Elite Std")
            # If we get here without exception, the font works
            fonts.append("Prestige Elite Std")
        except FontLoadError as e:
            # Font can't be loaded, don't include it
            logger.debug(f"Font 'Prestige Elite Std' not available: {e}")
        except Exception as e:
            # Unexpected error, log it but don't crash
            logger.warning(f"Unexpected error detecting 'Prestige Elite Std': {e}")
        
        return fonts
    
    def _get_current_font_config(self) -> FontConfig:
        """Get the font configuration for the currently selected font.
        
        Returns:
            FontConfig for the selected font.
            
        Raises:
            ValueError: If font configuration not found.
        """
        font_name = self.available_fonts[self.selected_font_index]
        config = get_font_config(font_name)
        if not config:
            raise ValueError(f"No configuration found for font: {font_name}")
        return config
    
    def _get_preview_width(self) -> int:
        """Calculate the preview width based on current font configuration.
        
        Returns:
            Width of the preview in characters.
        """
        return self.font_config.full_page_width
    
    def _create_preview(self) -> None:
        """Create or recreate the print preview with current settings."""
        page_width = self._get_preview_width()
        self.preview = PrintPreview(self.pages, page_width)
    
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
            
            # Use the same input stack as the editor
            handler = KeyboardHandler(self.terminal)

            # Apply initial spacing from session if provided
            # Apply initial spacing from session if provided
            try:
                self._reformat_pages()
            except (AttributeError, IndexError, ValueError) as e:
                # Reformatting may raise on malformed model in rare tests;
                # the dialog should still open and allow cancel.
                logger.debug(f"Failed to reformat pages on dialog open: {e}")

            while True:
                self._render()
                
                # Get user input (parsed)
                ev = handler.get_key_event(timeout=None)
                if not ev:
                    continue

                # Cancel: ESC or 'C'
                if (ev.key_type == KeyType.SPECIAL and ev.value == 'escape') or (
                    ev.key_type == KeyType.REGULAR and ev.value in ('c', 'C')
                ):
                    return PrintOptions(action=PrintAction.CANCEL)

                # Print/Save: 'P'
                if ev.key_type == KeyType.REGULAR and ev.value in ('p', 'P'):
                    return self._get_print_options()

                # Cycle output: 'O'
                if ev.key_type == KeyType.REGULAR and ev.value in ('o', 'O'):
                    self.selected_output = (self.selected_output + 1) % len(self.output_options)
                    # Save selected output to session
                    selected_option = self.output_options[self.selected_output]
                    self.session.set(SessionKeys.PRINTER_NAME, selected_option)
                    continue

                # Toggle double-sided: 'D'
                if ev.key_type == KeyType.REGULAR and ev.value in ('d', 'D'):
                    self.double_sided = not self.double_sided
                    # Save duplex setting to session
                    self.session.set(SessionKeys.DUPLEX_PRINTING, self.double_sided)
                    continue

                # Toggle spacing: 'S'
                if ev.key_type == KeyType.REGULAR and ev.value in ('s', 'S'):
                    self.double_spacing = not self.double_spacing
                    self.session.set(SessionKeys.DOUBLE_SPACING, self.double_spacing)
                    self._reformat_pages()
                    continue

                # Cycle font: 'F'
                if ev.key_type == KeyType.REGULAR and ev.value in ('f', 'F'):
                    if len(self.available_fonts) > 1:
                        self.selected_font_index = (self.selected_font_index + 1) % len(self.available_fonts)
                        # Update font configuration
                        self.font_config = self._get_current_font_config()
                        self.line_length = self.font_config.text_width
                        # Save to session
                        self.session.set(SessionKeys.FONT_NAME, self.available_fonts[self.selected_font_index])
                        self.session.set(SessionKeys.LINE_LENGTH, self.line_length)
                        # Reformat with new font
                        self._reformat_pages()
                    continue

                # Page navigation: PageUp/PageDown
                if ev.key_type == KeyType.SPECIAL and ev.value in ('page_up', 'pageup'):
                    if self.current_page > 0:
                        self.current_page -= 1
                    continue
                if ev.key_type == KeyType.SPECIAL and ev.value in ('page_down', 'pagedown'):
                    if self.current_page < len(self.pages) - 1:
                        self.current_page += 1
                    continue
                        
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
        dialog_width = min(110, term.width - 4)  # Increased for wider preview
        dialog_height = 38  # Slightly less height without borders
        left_margin = max(2, (term.width - dialog_width) // 2)
        top_margin = max(1, (term.height - dialog_height) // 2)
        
        # Draw title (no border)
        self._draw_title(left_margin, top_margin, dialog_width)
        
        # Draw page preview on the left
        preview_left = left_margin
        preview_top = top_margin + 2  # After title
        preview_width = self._draw_preview(preview_left, preview_top)
        
        # Draw options on the right with dynamic spacing based on preview width
        # Preview width + 2 for border + 3 for spacing
        options_left = preview_left + preview_width + 5
        options_top = top_margin + 2
        options_max_width = dialog_width - (preview_width + 5)  # Remaining width for options
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
    
    def _draw_preview(self, left: int, top: int) -> int:
        """Draw the page preview.
        
        Returns:
            Width of the preview including border.
        """
        term = self.terminal.term
        
        # Get preview with border
        preview_lines = self.preview.generate_preview_with_border(self.current_page)
        
        # Calculate preview width (including borders)
        preview_width = len(preview_lines[0]) if preview_lines else 45
        
        # Draw preview
        for i, line in enumerate(preview_lines):
            print(term.move(top + i, left) + line, end='')
        
        # Draw page info and navigation help at bottom of preview
        page_text = f"Page {self.current_page + 1}/{len(self.pages)}"
        nav_text = "PgUp/PgDn: Navigate"
        
        # Position at bottom of preview box
        info_y = top + len(preview_lines)
        print(term.move(info_y, left) + page_text, end='')
        # Position nav text at right edge of preview
        print(term.move(info_y, left + preview_width - len(nav_text) - 2) + nav_text, end='')
        
        return preview_width
    
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
        if self.selected_output < len(self.output_options) - 1:  # Not PDF File
            double_text = "YES" if self.double_sided else "NO"
            print(term.move(y, left) + f"[D]ouble-sided: {double_text}", end='')
            y += 2
        else:
            y += 2
        # Spacing option
        spacing_text = "DOUBLE" if self.double_spacing else "SINGLE"
        print(term.move(y, left) + f"[S]pacing: {spacing_text}", end='')
        y += 2
        
        # Font option (if multiple fonts available)
        if len(self.available_fonts) > 1:
            print(term.move(y, left) + "[F]ont:", end='')
            y += 1
            for i, font in enumerate(self.available_fonts):
                if i == self.selected_font_index:
                    marker = "[x] "
                else:
                    marker = "[ ] "
                print(term.move(y, left) + marker + font, end='')
                y += 1
            y += 1
        
        # Separator
        sep_width = min(25, max_width)
        print(term.move(y, left) + "─" * sep_width, end='')
        y += 2
        
        # Action buttons
        print(term.move(y, left) + "[P]rint  [C]ancel", end='')
    
    def _reformat_pages(self) -> None:
        """Reformat pages with current settings.
        
        This method is called when font or spacing changes.
        """
        styles = getattr(self.model, 'styles', None)
        self.formatter = PrintFormatter(
            self.model.paragraphs,
            double_spacing=self.double_spacing,
            styles=styles,
            line_length=self.line_length,
            font_config=self.font_config
        )
        self.pages = self.formatter.format_pages()
        self._create_preview()
        
        # Clamp current page if needed
        if self.current_page >= len(self.pages):
            self.current_page = max(0, len(self.pages) - 1)
    
    def get_line_length(self) -> int:
        """Get the current line length based on selected font.
        
        Returns:
            Current line length (text width in characters).
        """
        return self.line_length
    
    def get_font_config(self) -> FontConfig:
        """Get the current font configuration.
        
        Returns:
            Current FontConfig object.
        """
        return self.font_config
    
    def _get_print_options(self) -> PrintOptions:
        """Get the final print options based on current selections.
        
        Returns:
            PrintOptions with the current selections.
        """
        selected_option = self.output_options[self.selected_output]
        selected_font = self.available_fonts[self.selected_font_index]
        
        if selected_option == "PDF File":
            # PDF File output
            return PrintOptions(
                action=PrintAction.SAVE_PDF,
                pdf_filename="output.pdf",  # Default, will be prompted later
                font_name=selected_font
            )
        else:
            # Printer output
            return PrintOptions(
                action=PrintAction.PRINT,
                printer_name=selected_option,
                double_sided=self.double_sided,
                font_name=selected_font
            )

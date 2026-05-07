"""Print dialog UI for document printing."""

from typing import List, Optional, NamedTuple, Tuple
from enum import Enum
import blessed
import os
import logging
import textwrap

from .booklet import imposition_order, pad_to_multiple_of_4
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
    booklet: bool = False  # Saddle-stitched booklet imposition


class PrintDialog:
    """Interactive print dialog for document printing."""

    # Layout constants
    DEFAULT_DIALOG_WIDTH = 110  # cap for the single-page layout
    DIALOG_HEIGHT = 38
    PREVIEW_BORDERED_HEIGHT = 35  # 33 quadrant rows + 2 border rows
    OPTIONS_COLUMN_WIDTH = 30  # reserved for the right-side options column
    PREVIEW_OPTIONS_GAP = 5  # blank columns between preview and options

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

        # Restore booklet setting from session
        self.booklet = bool(self.session.get(SessionKeys.BOOKLET, False))

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

        # Booklet imposition order: list of (left_idx, right_idx) per sheet side.
        # Empty in single-page mode; recomputed when booklet toggles or pages change.
        self.imposed_sides: List[Tuple[int, int]] = []
        self._compute_imposed_sides()

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

    def _compute_imposed_sides(self) -> None:
        """Update ``self.imposed_sides`` based on booklet state and page count.

        Empty when booklet is off or there are no pages.
        """
        if not self.booklet or not self.pages:
            self.imposed_sides = []
            return
        padded_n = pad_to_multiple_of_4(len(self.pages))
        self.imposed_sides = imposition_order(padded_n)

    def _navigation_count(self) -> int:
        """Number of items the user can navigate via PgUp/PgDn."""
        return len(self.imposed_sides) if self.booklet else len(self.pages)

    def _required_dialog_width(self) -> int:
        """Minimum dialog width needed to render preview + options column."""
        if self.booklet:
            half_preview = (self.font_config.full_page_width + 1) // 2
            preview_width = 1 + half_preview + 1 + half_preview + 1  # borders + fold
        else:
            preview_width = ((self.font_config.full_page_width + 1) // 2) + 2
        return preview_width + self.PREVIEW_OPTIONS_GAP + self.OPTIONS_COLUMN_WIDTH
    
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

                # Toggle double-sided: 'D' (no-op when booklet on -- duplex is implicit)
                if ev.key_type == KeyType.REGULAR and ev.value in ('d', 'D'):
                    if self.booklet:
                        continue
                    self.double_sided = not self.double_sided
                    # Save duplex setting to session
                    self.session.set(SessionKeys.DUPLEX_PRINTING, self.double_sided)
                    continue

                # Toggle booklet: 'B'
                if ev.key_type == KeyType.REGULAR and ev.value in ('b', 'B'):
                    self.booklet = not self.booklet
                    self.session.set(SessionKeys.BOOKLET, self.booklet)
                    self._compute_imposed_sides()
                    # Reset navigation when switching modes (item indices differ)
                    self.current_page = 0
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

                # Page (or sheet-side, in booklet mode) navigation
                if ev.key_type == KeyType.SPECIAL and ev.value in ('page_up', 'pageup'):
                    if self.current_page > 0:
                        self.current_page -= 1
                    continue
                if ev.key_type == KeyType.SPECIAL and ev.value in ('page_down', 'pagedown'):
                    if self.current_page < self._navigation_count() - 1:
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

        # Dialog width: in booklet mode the preview is twice as wide, so
        # let the dialog grow beyond the single-page cap when the terminal
        # has room. When it doesn't, fall back to a width that fits.
        needed = self._required_dialog_width()
        cap = max(self.DEFAULT_DIALOG_WIDTH, needed) if self.booklet else self.DEFAULT_DIALOG_WIDTH
        dialog_width = min(cap, term.width - 4)
        left_margin = max(2, (term.width - dialog_width) // 2)
        top_margin = max(1, (term.height - self.DIALOG_HEIGHT) // 2)

        # Draw title (no border)
        self._draw_title(left_margin, top_margin, dialog_width)

        # Reserve space for the options column on the right; whatever remains
        # is the preview area (which may shrink for the narrow-terminal fallback).
        preview_top = top_margin + 2
        preview_left = left_margin
        max_preview_width = max(
            10,
            dialog_width - self.OPTIONS_COLUMN_WIDTH - self.PREVIEW_OPTIONS_GAP,
        )

        if self.booklet and term.width < needed:
            preview_width = self._draw_preview_too_narrow(
                preview_left, preview_top, needed, max_preview_width
            )
        else:
            preview_width = self._draw_preview(preview_left, preview_top)

        # Position options just right of the actual preview.
        options_left = preview_left + preview_width + self.PREVIEW_OPTIONS_GAP
        options_top = top_margin + 2
        options_max_width = max(
            self.OPTIONS_COLUMN_WIDTH,
            left_margin + dialog_width - options_left,
        )
        self._draw_options(options_left, options_top, options_max_width)

        # Flush output
        print('', end='', flush=True)

    def _draw_preview_too_narrow(
        self, left: int, top: int, needed: int, max_width: int
    ) -> int:
        """Render a placeholder when the terminal is too narrow for booklet preview.

        Wraps the message into the available width so the rest of the dialog
        (including the [B]ooklet toggle) remains on-screen and operable.

        Returns the width occupied (border + content + border).
        """
        term = self.terminal.term
        # Inner width: leave room for the two side borders. Cap so the box
        # never overwhelms the dialog -- the user only needs enough text to
        # know what to do.
        inner = max(10, min(max_width - 2, 30))
        width = inner + 2  # plus left/right border columns

        msg = (
            f"Booklet preview needs {needed}+ cols. "
            "Press B to disable booklet."
        )
        msg_lines = textwrap.wrap(msg, width=inner - 2) or [msg[: inner - 2]]

        # Match the height of a real bordered preview so the layout below
        # (page-info row, options) lines up identically in both modes.
        height = self.PREVIEW_BORDERED_HEIGHT

        print(term.move(top, left) + "┌" + "─" * inner + "┐", end='')
        for r in range(1, height - 1):
            msg_idx = r - 1
            if 0 <= msg_idx < len(msg_lines):
                content = " " + msg_lines[msg_idx].ljust(inner - 1)
            else:
                content = " " * inner
            print(term.move(top + r, left) + "│" + content + "│", end='')
        print(term.move(top + height - 1, left) + "└" + "─" * inner + "┘", end='')
        return width
    
    def _draw_title(self, left: int, top: int, width: int):
        """Draw the dialog title without borders."""
        term = self.terminal.term
        
        # Center the title
        title = "Print Document"
        title_pos = left + (width - len(title)) // 2
        print(term.move(top, title_pos) + term.bold + title + term.normal, end='')
    
    def _draw_preview(self, left: int, top: int) -> int:
        """Draw the page (or booklet sheet) preview.

        Returns:
            Width of the preview including border.
        """
        term = self.terminal.term

        if not self.pages:
            preview_lines = []
            page_text = "No content"
        elif self.booklet and self.imposed_sides:
            sheet_idx = min(self.current_page, len(self.imposed_sides) - 1)
            left_idx, right_idx = self.imposed_sides[sheet_idx]
            preview_lines = self.preview.generate_sheet_preview_with_border(left_idx, right_idx)
            page_text = self._sheet_label(sheet_idx, left_idx, right_idx)
        else:
            preview_lines = self.preview.generate_preview_with_border(self.current_page)
            page_text = f"Page {self.current_page + 1}/{len(self.pages)}"

        preview_width = len(preview_lines[0]) if preview_lines else 45

        for i, line in enumerate(preview_lines):
            print(term.move(top + i, left) + line, end='')

        nav_text = "PgUp/PgDn: Navigate"
        info_y = top + len(preview_lines)
        print(term.move(info_y, left) + page_text, end='')
        print(term.move(info_y, left + preview_width - len(nav_text) - 2) + nav_text, end='')

        return preview_width

    def _sheet_label(self, sheet_idx: int, left_page_idx: int, right_page_idx: int) -> str:
        """Format the bottom-of-preview label in booklet mode.

        Sheet sides are ordered front_1, back_1, front_2, back_2, ...
        """
        n_real = len(self.pages)
        sheet_num = sheet_idx // 2 + 1
        side = "front" if sheet_idx % 2 == 0 else "back"
        n_sheets = max(1, len(self.imposed_sides) // 2)

        def page_label(idx: int) -> str:
            return str(idx + 1) if idx < n_real else "blank"

        return (
            f"Sheet {sheet_num}/{n_sheets} {side}: pp. "
            f"{page_label(left_page_idx)}, {page_label(right_page_idx)}"
        )
    
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

        # Double-sided option: only when printing to a printer AND booklet is off
        # (booklet implies short-edge duplex, so the toggle doesn't apply).
        # Reserve the row in either case so toggling the option doesn't shift
        # the items below it.
        if (self.selected_output < len(self.output_options) - 1
                and not self.booklet):
            double_text = "YES" if self.double_sided else "NO"
            print(term.move(y, left) + f"[D]ouble-sided: {double_text}", end='')
        y += 2

        # Booklet option
        booklet_text = "ON" if self.booklet else "OFF"
        print(term.move(y, left) + f"[B]ooklet: {booklet_text}", end='')
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
        self._compute_imposed_sides()
        self._create_preview()

        # Clamp current navigation index to whatever's now valid
        nav_count = self._navigation_count()
        if self.current_page >= nav_count:
            self.current_page = max(0, nav_count - 1)
    
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
            return PrintOptions(
                action=PrintAction.SAVE_PDF,
                pdf_filename="output.pdf",  # Default, will be prompted later
                font_name=selected_font,
                booklet=self.booklet,
            )
        else:
            # Booklet implies duplex (short-edge) at the printer level;
            # surface that as double_sided=True so downstream sees it.
            double_sided = True if self.booklet else self.double_sided
            return PrintOptions(
                action=PrintAction.PRINT,
                printer_name=selected_option,
                double_sided=double_sided,
                font_name=selected_font,
                booklet=self.booklet,
            )

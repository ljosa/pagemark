"""Document formatter for printing - formats text into 85x66 character pages."""

from typing import List, Tuple, Optional
from .view import render_paragraph


class PrintFormatter:
    """Formats document into printable pages with proper margins and page numbers."""
    
    # Full page dimensions (8.5" x 11" at 10 cpi x 6 lpi)
    FULL_PAGE_WIDTH = 85   # Total characters per line
    FULL_PAGE_HEIGHT = 66  # Total lines per page
    
    # Text area dimensions (with 1" margins)
    TEXT_WIDTH = 65   # Characters in text area
    TEXT_HEIGHT = 54  # Lines in text area
    
    # Margin sizes
    TOP_MARGIN = 6    # Lines before text starts (1")
    BOTTOM_MARGIN = 6  # Lines after text ends (1")
    LEFT_MARGIN = 10   # Characters before text starts (1")
    RIGHT_MARGIN = 10  # Characters after text ends (1")
    
    # Page number position (1/2" from top = line 3, 0-indexed)
    PAGE_NUMBER_LINE = 3  # Line 4 in 1-indexed terms
    
    def __init__(self, paragraphs: List[str], double_spacing: bool = False, styles: Optional[List[List[int]]] = None):
        """Initialize formatter with document paragraphs."""
        self.paragraphs = paragraphs
        self.pages: List[List[str]] = []
        self.double_spacing = bool(double_spacing)
        self.styles: Optional[List[List[int]]] = styles
        # Parallel to pages: per line list of (start_x, text, flags) runs; None for non-text lines
        self.page_runs: List[List[Optional[List[Tuple[int, str, int]]]]] = []
    
    def format_pages(self) -> List[List[str]]:
        """Format paragraphs into full 85x66 pages with margins.
        
        Returns:
            List of pages, where each page is a list of 66 lines, 
            each line is 85 characters wide.
        """
        # First, format text content into 65-char wide lines; also build flat style runs
        text_lines: List[str] = []
        flat_runs: List[Optional[List[Tuple[int, str, int]]]] = []
        for idx, paragraph in enumerate(self.paragraphs):
            # Use the same render_paragraph function as view.py for consistency
            lines, counts = render_paragraph(paragraph, self.TEXT_WIDTH)
            text_lines.extend(lines)
            if self.styles is not None:
                st = self.styles[idx] if idx < len(self.styles) else [0] * len(paragraph)
                start = 0
                for li, line in enumerate(lines):
                    end = counts[li]
                    slice_styles = st[start:end]
                    # Build contiguous runs for this 65-char line
                    runs: List[Tuple[int, str, int]] = []
                    if line:
                        x = 0
                        while x < len(line):
                            flags = slice_styles[x] if x < len(slice_styles) else 0
                            j = x
                            while j < len(line):
                                f2 = slice_styles[j] if j < len(slice_styles) else 0
                                if f2 != flags:
                                    break
                                j += 1
                            if flags != 0:
                                seg_text = line[x:j]
                                # Convert to absolute x with left margin
                                runs.append((self.LEFT_MARGIN + x, seg_text, flags))
                            x = j
                    flat_runs.append(runs if runs else [])
                    start = end
            else:
                for _ in lines:
                    flat_runs.append([])
        
        # Now create full pages with margins
        self.pages = []
        self.page_runs = []
        text_line_index = 0
        page_num = 1
        
        while text_line_index < len(text_lines):
            # Create a new page (85x66)
            page: List[str] = []
            page_run_lines: List[Optional[List[Tuple[int, str, int]]]] = []
            
            # Top margin (lines 0-5)
            for i in range(self.TOP_MARGIN):
                if i == self.PAGE_NUMBER_LINE and page_num > 1:
                    # Add page number on line 4 for pages 2+
                    page.append(self._create_page_number_line(page_num))
                else:
                    # Empty margin line
                    page.append(" " * self.FULL_PAGE_WIDTH)
                page_run_lines.append(None)
            
            # Text area (lines 6-59)
            if not self.double_spacing:
                for i in range(self.TEXT_HEIGHT):
                    if text_line_index < len(text_lines):
                        text_line = text_lines[text_line_index].ljust(self.TEXT_WIDTH)
                        full_line = " " * self.LEFT_MARGIN + text_line + " " * self.RIGHT_MARGIN
                        page.append(full_line)
                        runs = flat_runs[text_line_index] if text_line_index < len(flat_runs) else []
                        page_run_lines.append(runs if runs else [])
                        text_line_index += 1
                    else:
                        page.append(" " * self.FULL_PAGE_WIDTH)
                        page_run_lines.append(None)
            else:
                # Double spacing: place text on every other line in text area
                placed = 0
                slots = self.TEXT_HEIGHT // 2
                for i in range(self.TEXT_HEIGHT):
                    if i % 2 == 0 and text_line_index < len(text_lines) and placed < slots:
                        text_line = text_lines[text_line_index].ljust(self.TEXT_WIDTH)
                        full_line = " " * self.LEFT_MARGIN + text_line + " " * self.RIGHT_MARGIN
                        page.append(full_line)
                        runs = flat_runs[text_line_index] if text_line_index < len(flat_runs) else []
                        page_run_lines.append(runs if runs else [])
                        text_line_index += 1
                        placed += 1
                    else:
                        page.append(" " * self.FULL_PAGE_WIDTH)
                        page_run_lines.append(None)
            
            # Bottom margin (lines 60-65)
            for i in range(self.BOTTOM_MARGIN):
                page.append(" " * self.FULL_PAGE_WIDTH)
                page_run_lines.append(None)
            
            self.pages.append(page)
            self.page_runs.append(page_run_lines)
            page_num += 1
        
        # If no content, create no pages (not even a blank one)
        if not text_lines:
            self.pages = []
            self.page_runs = []
        
        return self.pages

    def get_page_runs(self) -> List[List[Optional[List[Tuple[int, str, int]]]]]:
        """Return per-line style runs aligned to pages; None where no runs."""
        return self.page_runs
    
    def _create_page_number_line(self, page_num: int) -> str:
        """Create a page number line centered on the page."""
        page_number_str = str(page_num)
        # Center the page number in the full width
        padding_left = (self.FULL_PAGE_WIDTH - len(page_number_str)) // 2
        padding_right = self.FULL_PAGE_WIDTH - padding_left - len(page_number_str)
        return " " * padding_left + page_number_str + " " * padding_right
    
    def get_page_count(self) -> int:
        """Return the total number of pages."""
        return len(self.pages)
    
    def get_page(self, page_num: int) -> List[str]:
        """Get a specific page (0-indexed).
        
        Args:
            page_num: The page number to retrieve (0-indexed).
            
        Returns:
            List of lines for the requested page, or empty list if page doesn't exist.
        """
        if 0 <= page_num < len(self.pages):
            return self.pages[page_num]
        return []
    
    def format_for_print(self) -> str:
        """Format all pages as a single string for printing.
        
        Returns:
            String with all pages formatted for printing, with form feeds between pages.
        """
        output = []
        for i, page in enumerate(self.pages):
            # Pages are already full-sized (85x66)
            output.extend(page)
            
            # Add form feed between pages (but not after last page)
            if i < len(self.pages) - 1:
                output.append("\f")  # Form feed character
        
        return "\n".join(output)

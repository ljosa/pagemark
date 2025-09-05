"""Document formatter for printing - formats text into 85x66 character pages."""

from typing import List, Tuple
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
    
    def __init__(self, paragraphs: List[str], double_spacing: bool = False):
        """Initialize formatter with document paragraphs."""
        self.paragraphs = paragraphs
        self.pages: List[List[str]] = []
        self.double_spacing = bool(double_spacing)
    
    def format_pages(self) -> List[List[str]]:
        """Format paragraphs into full 85x66 pages with margins.
        
        Returns:
            List of pages, where each page is a list of 66 lines, 
            each line is 85 characters wide.
        """
        # First, format text content into 65-char wide lines
        text_lines = []
        for paragraph in self.paragraphs:
            # Use the same render_paragraph function as view.py for consistency
            lines, _ = render_paragraph(paragraph, self.TEXT_WIDTH)
            text_lines.extend(lines)
        
        # Now create full pages with margins
        self.pages = []
        text_line_index = 0
        page_num = 1
        
        while text_line_index < len(text_lines):
            # Create a new page (85x66)
            page = []
            
            # Top margin (lines 0-5)
            for i in range(self.TOP_MARGIN):
                if i == self.PAGE_NUMBER_LINE and page_num > 1:
                    # Add page number on line 4 for pages 2+
                    page.append(self._create_page_number_line(page_num))
                else:
                    # Empty margin line
                    page.append(" " * self.FULL_PAGE_WIDTH)
            
            # Text area (lines 6-59)
            if not self.double_spacing:
                for i in range(self.TEXT_HEIGHT):
                    if text_line_index < len(text_lines):
                        text_line = text_lines[text_line_index].ljust(self.TEXT_WIDTH)
                        full_line = " " * self.LEFT_MARGIN + text_line + " " * self.RIGHT_MARGIN
                        page.append(full_line)
                        text_line_index += 1
                    else:
                        page.append(" " * self.FULL_PAGE_WIDTH)
            else:
                # Double spacing: place text on every other line in text area
                placed = 0
                slots = self.TEXT_HEIGHT // 2
                for i in range(self.TEXT_HEIGHT):
                    if i % 2 == 0 and text_line_index < len(text_lines) and placed < slots:
                        text_line = text_lines[text_line_index].ljust(self.TEXT_WIDTH)
                        full_line = " " * self.LEFT_MARGIN + text_line + " " * self.RIGHT_MARGIN
                        page.append(full_line)
                        text_line_index += 1
                        placed += 1
                    else:
                        page.append(" " * self.FULL_PAGE_WIDTH)
            
            # Bottom margin (lines 60-65)
            for i in range(self.BOTTOM_MARGIN):
                page.append(" " * self.FULL_PAGE_WIDTH)
            
            self.pages.append(page)
            page_num += 1
        
        # If no content, create no pages (not even a blank one)
        if not text_lines:
            self.pages = []
        
        return self.pages
    
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

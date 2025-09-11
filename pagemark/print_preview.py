"""Generate quarter block preview of print pages."""

from typing import List


class PrintPreview:
    """Generates quarter block preview of pages for the print dialog."""
    
    # Unicode quadrant block characters
    EMPTY = " "
    TOP_LEFT = "\u2598"      # ▘
    TOP_RIGHT = "\u259D"     # ▝
    BOTTOM_LEFT = "\u2596"   # ▖
    BOTTOM_RIGHT = "\u2597"  # ▗
    TOP_HALF = "\u2580"      # ▀
    BOTTOM_HALF = "\u2584"   # ▄
    LEFT_HALF = "\u258C"     # ▌
    RIGHT_HALF = "\u2590"    # ▐
    DIAGONAL_1 = "\u259A"    # ▚ (top-left and bottom-right)
    DIAGONAL_2 = "\u259E"    # ▞ (top-right and bottom-left)
    THREE_QUARTERS_1 = "\u259B"  # ▛ (missing bottom-right)
    THREE_QUARTERS_2 = "\u259C"  # ▜ (missing bottom-left)
    THREE_QUARTERS_3 = "\u2599"  # ▙ (missing top-right)
    THREE_QUARTERS_4 = "\u259F"  # ▟ (missing top-left)
    FULL = "\u2588"          # █
    
    # Mapping from 4-bit pattern to character
    # Bits: top-left, top-right, bottom-left, bottom-right
    QUADRANT_MAP = {
        0b0000: EMPTY,
        0b1000: TOP_LEFT,
        0b0100: TOP_RIGHT,
        0b0010: BOTTOM_LEFT,
        0b0001: BOTTOM_RIGHT,
        0b1100: TOP_HALF,
        0b0011: BOTTOM_HALF,
        0b1010: LEFT_HALF,
        0b0101: RIGHT_HALF,
        0b1001: DIAGONAL_1,
        0b0110: DIAGONAL_2,
        0b1110: THREE_QUARTERS_1,
        0b1101: THREE_QUARTERS_2,
        0b1011: THREE_QUARTERS_3,
        0b0111: THREE_QUARTERS_4,
        0b1111: FULL
    }
    
    def __init__(self, pages: List[List[str]], page_width: int = 85):
        """Initialize preview with formatted pages.
        
        Args:
            pages: List of pages from PrintFormatter.
            page_width: Width of pages in characters (85 for standard, 102 for 12-pitch with wider margins).
        """
        self.pages = pages
        self.page_width = page_width
    
    def generate_preview(self, page_num: int) -> List[str]:
        """Generate quarter block preview of a page.
        
        Maps a page to a terminal display where each terminal
        character represents a 2x2 area of the document using quadrant blocks.
        
        Args:
            page_num: The page number to preview (0-indexed).
            
        Returns:
            List of 33 strings representing the preview.
        """
        if page_num >= len(self.pages):
            return []
        
        page = self.pages[page_num]
        preview_lines = []
        
        # Calculate preview width based on page width
        # Round up to ensure we capture all characters
        preview_width = (self.page_width + 1) // 2
        
        # Process page in 2x2 blocks
        for row in range(0, 66, 2):  # 33 preview rows
            preview_line = []
            
            for col in range(0, self.page_width + 1, 2):  # Ensure we cover full width
                # Get the 2x2 block of characters
                top_left = self._get_char(page, row, col)
                top_right = self._get_char(page, row, col + 1)
                bottom_left = self._get_char(page, row + 1, col)
                bottom_right = self._get_char(page, row + 1, col + 1)
                
                # Convert to quadrant block
                quadrant = self._chars_to_quadrant(
                    top_left, top_right, bottom_left, bottom_right
                )
                preview_line.append(quadrant)
            
            # Ensure consistent width
            line = "".join(preview_line)
            if len(line) < preview_width:
                line += " " * (preview_width - len(line))
            elif len(line) > preview_width:
                line = line[:preview_width]
            preview_lines.append(line)
        
        return preview_lines
    
    def _get_char(self, page: List[str], row: int, col: int) -> str:
        """Get a character from the page, returning space if out of bounds.
        
        Args:
            page: The page data (list of strings).
            row: The row index (0-based).
            col: The column index (0-based).
            
        Returns:
            The character at the position, or space if out of bounds.
        """
        if row >= len(page):
            return " "
        line = page[row]
        if col >= len(line):
            return " "
        return line[col]
    
    def _chars_to_quadrant(self, tl: str, tr: str, bl: str, br: str) -> str:
        """Convert a 2x2 block of characters to a quadrant block character.
        
        Args:
            tl: Top-left character
            tr: Top-right character
            bl: Bottom-left character
            br: Bottom-right character
            
        Returns:
            The appropriate Unicode quadrant block character.
        """
        # Build bit pattern based on non-space characters
        pattern = 0
        if tl and tl.strip():  # Non-empty and not just whitespace
            pattern |= 0b1000
        if tr and tr.strip():
            pattern |= 0b0100
        if bl and bl.strip():
            pattern |= 0b0010
        if br and br.strip():
            pattern |= 0b0001
        
        return self.QUADRANT_MAP[pattern]
    
    def generate_preview_with_border(self, page_num: int) -> List[str]:
        """Generate preview with a border around it.
        
        Args:
            page_num: The page number to preview (0-indexed).
            
        Returns:
            List of strings representing the bordered preview.
        """
        preview = self.generate_preview(page_num)
        if not preview:
            return []
        
        # Calculate preview width
        preview_width = (self.page_width + 1) // 2
        
        # Add border
        bordered = []
        bordered.append("┌" + "─" * preview_width + "┐")
        for line in preview:
            bordered.append("│" + line + "│")
        bordered.append("└" + "─" * preview_width + "┘")
        
        return bordered
"""Generate PDF directly in Python for printing."""

from typing import List
from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import letter


class PDFGenerator:
    """Generate PDF files for printing text documents."""
    
    def __init__(self):
        """Initialize PDF generator."""
        # Page dimensions for US Letter (8.5 x 11 inches)
        self.page_width = 612  # 8.5 * 72
        self.page_height = 792  # 11 * 72
        
        # Margins to match PostScript layout
        # PostScript starts at 0 horizontal, 11 inches - 1/6 inch vertical
        self.left_margin = 0
        # PostScript: "0 11 1 6 div sub inch moveto" = 11*72 - 72/6 = 792 - 12 = 780
        self.starting_y = 780  # 11 inches - 1/6 inch from bottom
        
        # Font settings to match PostScript
        # 12 point Courier for 6 lpi (lines per inch)
        self.font_size = 12
        self.line_height = 12  # 72/6 = 12 points per line
        
        # Track unprintable characters for warning
        self.unprintable_chars = set()
        self.has_unprintable = False
        
    def generate_pdf(self, pages: List[List[str]], page_styles: list[list[object]] | None = None) -> bytes:
        """Generate PDF from formatted pages.

        Args:
            pages: List of pages, each containing 66 lines of 85 chars.
            page_styles: Optional per-line style masks for the 65-col text area.
            
        Returns:
            Complete PDF document as bytes.
        """
        # Reset unprintable tracking for this generation
        self.unprintable_chars = set()
        self.has_unprintable = False
        import io
        pdf_buffer = io.BytesIO()
        
        # Create PDF canvas
        c = canvas.Canvas(pdf_buffer, pagesize=letter)
        
        # Process each page
        for page_num, page in enumerate(pages, 1):
            # Starting Y position matches PostScript exactly
            # PostScript uses: "0 11 1 6 div sub inch moveto" then "showline" moves down
            y_position = self.starting_y
            
            # Process each line on the page
            for li, line in enumerate(page):
                runs = None
                # page_styles parameter represents styled runs
                if page_styles and page_num-1 < len(page_styles) and li < len(page_styles[page_num-1]):
                    runs = page_styles[page_num-1][li]
                
                if not runs:
                    # Simple unstyled line
                    c.setFont("Courier", self.font_size)
                    # Convert line to handle encoding
                    safe_line = self._make_pdf_safe(line)
                    c.drawString(self.left_margin, y_position, safe_line)
                    # Move down for next line (like PostScript's showline)
                    y_position -= self.line_height
                else:
                    # Styled drawing: interleave unstyled text with styled runs
                    x_position = self.left_margin
                    current_col = 0
                    
                    # Calculate character width for Courier at this size
                    # Courier is monospace, all chars same width
                    c.setFont("Courier", self.font_size)
                    char_width = c.stringWidth("X", "Courier", self.font_size)
                    
                    # Ensure runs are sorted by start position
                    runs_sorted = sorted(runs, key=lambda r: r[0])
                    
                    for (start_x, seg_text, flags) in runs_sorted:
                        bold = bool(flags & 1)
                        underline = bool(flags & 2)
                        
                        # Draw any unstyled gap text before this run
                        if start_x > current_col:
                            gap_text = line[current_col:start_x]
                            if gap_text:
                                c.setFont("Courier", self.font_size)
                                safe_gap = self._make_pdf_safe(gap_text)
                                c.drawString(x_position, y_position, safe_gap)
                                x_position += len(gap_text) * char_width
                            current_col = start_x
                        
                        # Set font for styled segment
                        if bold:
                            c.setFont("Courier-Bold", self.font_size)
                        else:
                            c.setFont("Courier", self.font_size)
                        
                        # Draw the styled text
                        safe_seg = self._make_pdf_safe(seg_text)
                        text_start_x = x_position
                        c.drawString(x_position, y_position, safe_seg)
                        text_width = len(seg_text) * char_width
                        
                        # Draw underline if needed
                        if underline:
                            c.line(text_start_x, y_position - 2, 
                                  text_start_x + text_width, y_position - 2)
                        
                        x_position += text_width
                        current_col = start_x + len(seg_text)
                    
                    # Draw any trailing unstyled text
                    if current_col < len(line):
                        tail_text = line[current_col:]
                        if tail_text:
                            c.setFont("Courier", self.font_size)
                            safe_tail = self._make_pdf_safe(tail_text)
                            c.drawString(x_position, y_position, safe_tail)
                    
                    # Move down for next line (like PostScript's showline)
                    y_position -= self.line_height
            
            # End the page
            c.showPage()
        
        # Save the PDF
        c.save()
        
        # Get PDF bytes
        pdf_buffer.seek(0)
        return pdf_buffer.read()
    
    def _make_pdf_safe(self, text: str) -> str:
        """Convert text to be safe for PDF output with Courier font.
        
        The built-in Courier font supports Windows-1252 encoding which
        includes Latin-1 plus additional characters in the 0x80-0x9F range.
        
        Characters not in Windows-1252 are replaced with '?' and tracked
        for warning messages.
        
        Args:
            text: Text to make safe.
            
        Returns:
            Text safe for PDF output.
        """
        result = []
        for char in text:
            try:
                # Test if character can be encoded in Windows-1252
                char.encode('cp1252')
                result.append(char)
            except UnicodeEncodeError:
                # Track unprintable character for warning
                self.unprintable_chars.add(char)
                self.has_unprintable = True
                # Replace with question mark
                result.append('?')
        return ''.join(result)
    
    def get_unprintable_warning(self) -> str | None:
        """Get warning message about unprintable characters.
        
        Returns:
            Warning message if unprintable chars were found, None otherwise.
        """
        if not self.has_unprintable:
            return None
        
        # Create a sorted list of unique unprintable characters for display
        char_list = sorted(self.unprintable_chars)
        
        # Format characters for display (show unicode code point for non-displayable)
        formatted_chars = []
        for char in char_list[:10]:  # Limit to first 10 for readability
            if ord(char) < 32 or ord(char) == 127:  # Control characters
                formatted_chars.append(f"U+{ord(char):04X}")
            else:
                formatted_chars.append(f"'{char}' (U+{ord(char):04X})")
        
        if len(char_list) > 10:
            formatted_chars.append(f"... and {len(char_list) - 10} more")
        
        return (f"Warning: {len(self.unprintable_chars)} unique unprintable character(s) "
                f"were replaced with '?' in the PDF output: {', '.join(formatted_chars)}")
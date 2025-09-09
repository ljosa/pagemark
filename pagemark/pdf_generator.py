"""Generate PDF directly in Python for printing."""

from typing import List
from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import letter
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont


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
        
    def generate_pdf(self, pages: List[List[str]], page_styles: list[list[object]] | None = None) -> bytes:
        """Generate PDF from formatted pages.

        Args:
            pages: List of pages, each containing 66 lines of 85 chars.
            page_styles: Optional per-line style masks for the 65-col text area.
            
        Returns:
            Complete PDF document as bytes.
        """
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
        """Convert text to be safe for PDF output.
        
        ReportLab handles most encoding automatically, but we need to
        handle any characters that might cause issues.
        
        Args:
            text: Text to make safe.
            
        Returns:
            Text safe for PDF.
        """
        # ReportLab handles Latin-1 well, but replace any chars outside that range
        result = []
        for char in text:
            try:
                # Test if character can be encoded in Latin-1
                char.encode('latin-1')
                result.append(char)
            except UnicodeEncodeError:
                # Replace with question mark if can't encode
                result.append('?')
        
        return ''.join(result)
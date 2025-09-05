"""Generate PostScript directly in Python for printing."""

from typing import List


class PostScriptGenerator:
    """Generate PostScript files for printing text documents."""
    
    # PostScript header for text documents
    PS_HEADER = """%!PS-Adobe-3.0
%%DocumentData: Clean7Bit
%%Pages: {num_pages}
%%PageOrder: Ascend
%%BoundingBox: 0 0 612 792
%%DocumentNeededResources: font Courier
%%DocumentNeededResources: font Courier-ISOLatin1
%%DocumentNeededResources: font Courier-Bold
%%DocumentNeededResources: font Courier-Bold-ISOLatin1
%%EndComments

%%BeginProlog
%%BeginResource: procset
/inch {{72 mul}} def
/showline {{
  show
  0 currentpoint exch pop 12 sub moveto
}} def
% Set up ISOLatin1 encoding for Courier font
/Courier-ISOLatin1 /Courier findfont
dup length dict begin
  {{1 index /FID ne {{def}} {{pop pop}} ifelse}} forall
  /Encoding ISOLatin1Encoding def
  currentdict
end
definefont pop
% Bold variant with ISOLatin1
/Courier-Bold-ISOLatin1 /Courier-Bold findfont
dup length dict begin
  {{1 index /FID ne {{def}} {{pop pop}} ifelse}} forall
  /Encoding ISOLatin1Encoding def
  currentdict
end
definefont pop
%%EndResource
%%EndProlog

%%BeginSetup
%%IncludeResource: font Courier
%%EndSetup
"""

    # Page setup template
    # Font size: 10 cpi = 7.2 points wide, 12 points high for 6 lpi
    # Start at 11 inches minus 1/6 inch for baseline positioning
    PAGE_SETUP = """%%Page: {page_num} {page_num}
%%BeginPageSetup
/Courier-ISOLatin1 findfont 12 scalefont setfont
0 setgray
%%EndPageSetup
gsave
0 11 1 6 div sub inch moveto
"""

    # Page trailer
    PAGE_TRAILER = """grestore
showpage
"""

    # Document trailer
    DOC_TRAILER = """%%Trailer
%%EOF
"""

    def __init__(self):
        """Initialize PostScript generator."""
        pass
    
    def generate_postscript(self, pages: List[List[str]], page_styles: list[list[object]] | None = None) -> str:
        """Generate PostScript from formatted pages.

        Args:
            pages: List of pages, each containing 66 lines of 85 chars.
            page_styles: Optional per-line style masks for the 65-col text area.
            
        Returns:
            Complete PostScript document as a string.
        """
        ps_content = []
        
        # Add header
        ps_content.append(self.PS_HEADER.format(num_pages=len(pages)))
        
        # Process each page
        for page_num, page in enumerate(pages, 1):
            # Add page setup
            ps_content.append(self.PAGE_SETUP.format(page_num=page_num))
            # Tag page if styled runs are present
            has_runs = False
            if page_styles and page_num-1 < len(page_styles):
                try:
                    for line_runs in page_styles[page_num-1]:
                        if line_runs:
                            has_runs = True
                            break
                except Exception:
                    has_runs = False
            if has_runs:
                ps_content.append("% StyledRuns: yes\n")
            
            # Add page content
            # Start from top of page (10 inches from bottom)
            # Each line moves down 12 points (1/6 inch for 6 lpi)
            for li, line in enumerate(page):
                runs = None
                # page_styles parameter now represents runs for backward compatibility of variable name
                if page_styles and page_num-1 < len(page_styles) and li < len(page_styles[page_num-1]):
                    runs = page_styles[page_num-1][li]
                if not runs:
                    # Escape special PostScript characters and print simple line
                    escaped_line = self._escape_postscript(line)
                    ps_content.append(f"({escaped_line}) showline\n")
                else:
                    # Styled drawing: interleave unstyled text from the source line with styled runs.
                    # Track current x column in full 85-col line
                    current_x = 0
                    # Ensure runs are sorted by start_x
                    runs_sorted = sorted(runs, key=lambda r: r[0])
                    for (start_x, seg_text, flags) in runs_sorted:
                        b = bool(flags & 1)
                        u = bool(flags & 2)
                        # Emit any unstyled content between current_x and start_x from the original line
                        if start_x > current_x:
                            gap_text = line[current_x:start_x]
                            if gap_text:
                                ps_content.append("/Courier-ISOLatin1 findfont 12 scalefont setfont\n")
                                ps_content.append(f"({self._escape_postscript(gap_text)}) show\n")
                            current_x = start_x
                        # Set font for this styled segment
                        if b:
                            ps_content.append("/Courier-Bold-ISOLatin1 findfont 12 scalefont setfont\n")
                        else:
                            ps_content.append("/Courier-ISOLatin1 findfont 12 scalefont setfont\n")
                        # Show the text segment (track underline start/end)
                        if u:
                            ps_content.append("currentpoint /uy exch def /ux exch def\n")
                        ps_content.append(f"({self._escape_postscript(seg_text)}) show\n")
                        if u:
                            ps_content.append("currentpoint /uy2 exch def /ux2 exch def\n")
                            ps_content.append("gsave\n")
                            ps_content.append("newpath ux uy 2 sub moveto ux2 uy 2 sub lineto stroke\n")
                            ps_content.append("grestore\n")
                            ps_content.append("ux2 uy2 moveto\n")
                        current_x = start_x + len(seg_text)
                    # Emit any trailing unstyled content to end of line
                    if current_x < len(line):
                        tail_text = line[current_x:]
                        if tail_text:
                            ps_content.append("/Courier-ISOLatin1 findfont 12 scalefont setfont\n")
                            ps_content.append(f"({self._escape_postscript(tail_text)}) show\n")
                    # Move to next line (equivalent to showline's move)
                    ps_content.append("0 currentpoint exch pop 12 sub moveto\n")
            
            # Add page trailer
            ps_content.append(self.PAGE_TRAILER)
        
        # Add document trailer
        ps_content.append(self.DOC_TRAILER)
        
        return ''.join(ps_content)
    
    def _escape_postscript(self, text: str) -> str:
        """Escape special characters for PostScript strings.
        
        Handles both PostScript special characters and Unicode/Latin-1 encoding.
        
        Args:
            text: Text to escape.
            
        Returns:
            Escaped text safe for PostScript.
        """
        result = []
        
        for char in text:
            # Handle PostScript special characters
            if char == '\\':
                result.append('\\\\')
            elif char == '(':
                result.append('\\(')
            elif char == ')':
                result.append('\\)')
            elif char == '\n':
                result.append('\\n')
            elif char == '\r':
                result.append('\\r')
            elif char == '\t':
                result.append('\\t')
            elif char == '\f':
                result.append('\\f')
            elif char == '\b':
                result.append('\\b')
            # Handle ASCII characters
            elif ord(char) < 128:
                result.append(char)
            # Handle Latin-1 characters (128-255)
            elif ord(char) < 256:
                # Use octal escape for Latin-1 characters
                result.append(f'\\{ord(char):03o}')
            else:
                # For characters outside Latin-1, try to encode to Latin-1
                try:
                    # Try to encode as Latin-1
                    char.encode('latin-1')
                    result.append(f'\\{ord(char):03o}')
                except UnicodeEncodeError:
                    # Replace with question mark if can't encode
                    result.append('?')
        
        return ''.join(result)

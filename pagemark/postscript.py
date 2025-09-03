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
    
    def generate_postscript(self, pages: List[List[str]]) -> str:
        """Generate PostScript from formatted pages.
        
        Args:
            pages: List of pages, each containing 66 lines of 85 chars.
            
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
            
            # Add page content
            # Start from top of page (10 inches from bottom)
            # Each line moves down 12 points (1/6 inch for 6 lpi)
            for line in page:
                # Escape special PostScript characters
                escaped_line = self._escape_postscript(line)
                ps_content.append(f"({escaped_line}) showline\n")
            
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
"""RTF parsing utilities for clipboard integration."""

from typing import Tuple, Optional, List
import re

# Maximum RTF size to parse (10MB) to prevent DoS attacks
MAX_RTF_SIZE = 10 * 1024 * 1024  # 10MB


def parse_rtf(rtf_text: str) -> Tuple[str, Optional[List[List[int]]]]:
    """Parse RTF format to extract text and styles.
    
    Args:
        rtf_text: RTF formatted text
        
    Returns:
        Tuple of (plain_text, styles) where styles is a list of style masks
        Returns empty string if RTF exceeds size limit
    """
    if not rtf_text or not rtf_text.startswith('{\\rtf'):
        return rtf_text, None
    
    # Check size limit to prevent DoS
    if len(rtf_text) > MAX_RTF_SIZE:
        return "", None  # Return empty string for oversized RTF
    
    # Track text and styles
    text_chars = []
    style_chars = []
    
    # State tracking
    bold = False
    underline = False
    group_stack = []  # Stack of (bold, underline) states
    i = 0
    
    # Skip past header to find content
    # Content typically starts after \pard or similar paragraph commands
    content_markers = [r'\pard', r'\pardeftab']
    content_start = 0
    for marker in content_markers:
        pos = rtf_text.find(marker)
        if pos > content_start:
            content_start = pos
    
    if content_start > 0:
        # Skip to after the paragraph command and any following commands
        i = content_start
        while i < len(rtf_text) and rtf_text[i] != ' ' and rtf_text[i] != '\n':
            i += 1
        # Skip past any additional formatting commands
        while i < len(rtf_text):
            if rtf_text[i] == '\\':
                # Skip control word
                i += 1
                while i < len(rtf_text) and (rtf_text[i].isalpha() or rtf_text[i].isdigit() or rtf_text[i] == '-'):
                    i += 1
                if i < len(rtf_text) and rtf_text[i] == ' ':
                    i += 1
            elif rtf_text[i] in ' \n':
                i += 1
            else:
                break
    
    # Parse content
    while i < len(rtf_text):
        if rtf_text[i] == '\\':
            if i + 1 < len(rtf_text):
                # Handle control sequences
                if rtf_text[i:i+2] == '\\b':
                    # Check if it's \b0 (bold off) or \b (bold on)
                    if i + 2 < len(rtf_text) and rtf_text[i+2] == '0':
                        bold = False
                        i += 3
                    else:
                        bold = True
                        i += 2
                    # Skip optional space
                    if i < len(rtf_text) and rtf_text[i] == ' ':
                        i += 1
                    continue
                
                elif rtf_text[i:i+3] == '\\ul':
                    # Check for \ul0 or \ulnone (underline off)
                    if i + 3 < len(rtf_text):
                        if rtf_text[i+3] == '0':
                            underline = False
                            i += 4
                        elif rtf_text[i+3:i+7] == 'none':
                            underline = False
                            i += 7
                        else:
                            underline = True
                            i += 3
                    else:
                        underline = True
                        i += 3
                    # Skip optional space
                    if i < len(rtf_text) and rtf_text[i] == ' ':
                        i += 1
                    continue
                
                elif rtf_text[i:i+4] == '\\par':
                    # Paragraph break - add newline
                    text_chars.append('\n')
                    style_chars.append(0)
                    i += 4
                    # Skip optional space and newline
                    while i < len(rtf_text) and rtf_text[i] in ' \n':
                        i += 1
                    continue
                
                elif rtf_text[i:i+2] == '\\\\':
                    # Escaped backslash
                    text_chars.append('\\')
                    style = _get_style(bold, underline)
                    style_chars.append(style)
                    i += 2
                    continue
                
                elif rtf_text[i:i+2] == '\\{':
                    # Escaped brace
                    text_chars.append('{')
                    style = _get_style(bold, underline)
                    style_chars.append(style)
                    i += 2
                    continue
                
                elif rtf_text[i:i+2] == '\\}':
                    # Escaped brace
                    text_chars.append('}')
                    style = _get_style(bold, underline)
                    style_chars.append(style)
                    i += 2
                    continue
                
                elif rtf_text[i:i+2] == '\\\n' or rtf_text[i:i+2] == '\\\r':
                    # Line continuation in RTF source (ignore)
                    i += 2
                    continue
                
                elif rtf_text[i:i+2] == "\\'": 
                    # Hex escape sequence (e.g., \'f8 for ø)
                    i += 2
                    if i + 1 < len(rtf_text):
                        hex_chars = rtf_text[i:i+2]
                        try:
                            char_code = int(hex_chars, 16)
                            text_chars.append(chr(char_code))
                            style = _get_style(bold, underline)
                            style_chars.append(style)
                            i += 2
                        except ValueError:
                            # Invalid hex, keep the literal characters
                            text_chars.append(hex_chars[0] if hex_chars else '')
                            if len(hex_chars) > 1:
                                text_chars.append(hex_chars[1])
                            style = _get_style(bold, underline)
                            style_chars.append(style)
                            if len(hex_chars) > 1:
                                style_chars.append(style)
                            i += len(hex_chars)
                    continue
                
                elif rtf_text[i:i+2] == "\\u":
                    # Unicode character (e.g., \u248? for ø)
                    i += 2
                    num_str = ''
                    # Handle negative numbers for characters > 32767
                    if i < len(rtf_text) and rtf_text[i] == '-':
                        num_str += rtf_text[i]
                        i += 1
                    # Read digits
                    while i < len(rtf_text) and rtf_text[i].isdigit():
                        num_str += rtf_text[i]
                        i += 1
                    
                    if num_str:
                        try:
                            char_code = int(num_str)
                            # Handle negative values (two's complement for values > 32767)
                            if char_code < 0:
                                char_code = 65536 + char_code
                            if 0 <= char_code <= 0x10FFFF:  # Valid Unicode range
                                text_chars.append(chr(char_code))
                                style = _get_style(bold, underline)
                                style_chars.append(style)
                        except (ValueError, OverflowError):
                            pass
                    
                    # Skip the replacement character (usually ?)
                    if i < len(rtf_text) and rtf_text[i] == '?':
                        i += 1
                    continue
                
                else:
                    # Skip other control sequences
                    i += 1
                    # Skip control word
                    while i < len(rtf_text) and (rtf_text[i].isalpha() or rtf_text[i] == '*'):
                        i += 1
                    # Skip optional numeric parameter
                    if i < len(rtf_text) and (rtf_text[i] == '-' or rtf_text[i].isdigit()):
                        if rtf_text[i] == '-':
                            i += 1
                        while i < len(rtf_text) and rtf_text[i].isdigit():
                            i += 1
                    # Skip optional space
                    if i < len(rtf_text) and rtf_text[i] == ' ':
                        i += 1
                    continue
            else:
                i += 1
        
        elif rtf_text[i] == '{':
            # Start of group - save current state
            group_stack.append((bold, underline))
            i += 1
        
        elif rtf_text[i] == '}':
            # End of group - restore previous state
            if group_stack:
                bold, underline = group_stack.pop()
            else:
                # End of document
                break
            i += 1
        
        elif rtf_text[i] in '\r\n':
            # RTF source line breaks (not content)
            i += 1
        
        else:
            # Regular character
            text_chars.append(rtf_text[i])
            style = _get_style(bold, underline)
            style_chars.append(style)
            i += 1
    
    # Convert to result format
    if not text_chars:
        return "", None
    
    text = ''.join(text_chars)
    
    # Convert flat style list to paragraph-based format
    paragraphs = text.split('\n')
    styles_list = []
    
    char_index = 0
    for para in paragraphs:
        para_len = len(para)
        if para_len > 0:
            para_styles = style_chars[char_index:char_index + para_len]
            styles_list.append(para_styles)
            char_index += para_len
        else:
            styles_list.append([])
        char_index += 1  # Skip the newline
    
    # Return with styles only if there are actual styles
    if styles_list and any(any(s != 0 for s in para) for para in styles_list):
        return text, styles_list
    else:
        return text, None


def _get_style(bold: bool, underline: bool) -> int:
    """Convert bold/underline flags to style mask value."""
    style = 0
    if bold and underline:
        style = 3
    elif bold:
        style = 1
    elif underline:
        style = 2
    return style
"""RTF serialization without access to a system clipboard."""
from typing import List


def generate_rtf(text: str, styles: List[List[int]]) -> str:
    """Generate RTF format from text and styles.

    Args:
        text: Plain text with newlines separating paragraphs
        styles: List of style masks for each paragraph

    Returns:
        RTF formatted string
    """
    # RTF header - using Helvetica which is standard on macOS
    rtf = r'{\rtf1\ansi\ansicpg1252\cocoartf2639' + '\n'
    rtf += r'\cocoatextscaling0\cocoaplatform0{\fonttbl\f0\fswiss\fcharset0 Helvetica;}' + '\n'
    rtf += r'{\colortbl;\red255\green255\blue255;}' + '\n'
    rtf += r'{\*\expandedcolortbl;;}' + '\n'
    rtf += r'\pard\tx560\tx1120\tx1680\tx2240\tx2800\tx3360\tx3920\tx4480\tx5040\tx5600\tx6160\tx6720\pardirnatural\partightenfactor0' + '\n\n'
    rtf += r'\f0\fs24 \cf0 '

    paragraphs = text.split('\n')

    for para_idx, para in enumerate(paragraphs):
        if para_idx > 0:
            rtf += r'\par' + '\n'  # Paragraph break

        if para_idx >= len(styles) or not styles[para_idx]:
            # No styling for this paragraph
            rtf += escape_rtf(para)
            continue

        style_mask = styles[para_idx]
        i = 0

        while i < len(para):
            if i >= len(style_mask):
                # No style info for rest of paragraph
                rtf += escape_rtf(para[i:])
                break

            # Find run of same style
            current_style = style_mask[i]
            run_end = i + 1
            while run_end < len(para) and run_end < len(style_mask) and style_mask[run_end] == current_style:
                run_end += 1

            run_text = escape_rtf(para[i:run_end])

            if current_style == 0:
                rtf += run_text
            elif current_style == 1:  # Bold
                rtf += r'{\b ' + run_text + '}'
            elif current_style == 2:  # Underline
                rtf += r'{\ul ' + run_text + '}'
            elif current_style == 3:  # Bold + Underline
                rtf += r'{\b\ul ' + run_text + '}'
            else:
                rtf += run_text

            i = run_end

    rtf += '}'
    return rtf


def escape_rtf(text: str) -> str:
    """Escape special characters for RTF."""
    text = text.replace('\\', '\\\\')
    text = text.replace('{', '\\{')
    text = text.replace('}', '\\}')
    # Handle Unicode characters
    result = []
    for char in text:
        if ord(char) <= 127:
            result.append(char)
        else:
            # RTF \uN takes signed 16-bit UTF-16 code units; astral
            # characters become a surrogate pair (two \uN words). The
            # UTF-16 codec produces exactly those units.
            units = char.encode('utf-16-be')
            for k in range(0, len(units), 2):
                n = int.from_bytes(units[k:k + 2], 'big', signed=True)
                result.append(f'\\u{n}?')
    return ''.join(result)

"""RTF parsing utilities for clipboard integration."""

from typing import Tuple, Optional, List

# Maximum RTF size to parse (10MB) to prevent DoS attacks
MAX_RTF_SIZE = 10 * 1024 * 1024  # 10MB

# Destination groups whose text content is not document text.
# Any group starting with \* is likewise skipped. Note that \field is NOT
# skipped: its \*\fldinst instruction part is starred (skipped anyway) while
# its {\fldrslt ...} part holds the visible text of hyperlinks etc.
_SKIP_DESTINATIONS = frozenset({
    'fonttbl', 'colortbl', 'expandedcolortbl', 'stylesheet', 'info',
    'pict', 'themedata', 'colorschememapping', 'listtable',
    'listoverridetable', 'header', 'footer', 'headerl', 'headerr',
    'headerf', 'footerl', 'footerr', 'footerf', 'xmlnstbl',
    'footnote', 'annotation',
})

# Control words that produce a character.
_SYMBOL_WORDS = {
    'par': '\n',
    'line': '\n',
    'tab': ' ',  # the editor has no tab stops; nearest equivalent
    'emdash': '—',
    'endash': '–',
    'lquote': '‘',
    'rquote': '’',
    'ldblquote': '“',
    'rdblquote': '”',
    'bullet': '•',
}


def _get_style(bold: bool, underline: bool) -> int:
    """Convert bold/underline flags to style mask value."""
    style = 0
    if bold:
        style |= 1
    if underline:
        style |= 2
    return style


def _decode_hex_byte(code: int, codepage: int) -> str:
    """Decode a \\'xx hex escape byte using the document's declared code page
    (\\ansicpgN; Windows-1252 by default, where 0x80-0x9F are printable
    smart quotes, dashes, ...)."""
    for encoding in (f'cp{codepage}', 'cp1252'):
        try:
            return bytes([code]).decode(encoding)
        except (UnicodeDecodeError, LookupError):
            continue
    return chr(code)


def _merge_surrogate_pairs(chars: List[str], styles: List[int]) -> None:
    """Merge UTF-16 surrogate pairs written as two \\uN words (in place)."""
    i = 0
    while i + 1 < len(chars):
        hi, lo = ord(chars[i]), ord(chars[i + 1])
        if 0xD800 <= hi <= 0xDBFF and 0xDC00 <= lo <= 0xDFFF:
            merged = 0x10000 + ((hi - 0xD800) << 10) + (lo - 0xDC00)
            chars[i] = chr(merged)
            del chars[i + 1]
            del styles[i + 1]
        i += 1


def parse_rtf(rtf_text: str) -> Tuple[str, Optional[List[List[int]]]]:
    """Parse RTF format to extract text and styles.

    Tokenizes RTF properly (control words are matched exactly, never by
    prefix) and skips destination groups such as the font table, so no
    header text leaks into the result.

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

    text_chars: List[str] = []
    style_chars: List[int] = []

    bold = False
    underline = False
    uc_skip = 1  # characters following \uN that are a fallback (RTF default)
    skip_group = False  # inside a destination group (fonttbl, \*..., ...)
    pending_uc = 0  # fallback characters still to consume after \uN
    codepage = 1252  # \ansicpgN; Windows-1252 unless declared otherwise
    # Stack of (bold, underline, uc_skip, skip_group) saved at each '{'
    group_stack: List[Tuple[bool, bool, int, bool]] = []

    def emit(ch: str) -> None:
        if skip_group:
            return
        text_chars.append(ch)
        style_chars.append(_get_style(bold, underline))

    def consume_uc_fallback() -> bool:
        """Whether the next literal char / hex escape is a \\uN fallback.

        Only ordinary characters and \\'xx escapes count as fallback text;
        control words like \\par must not be swallowed."""
        nonlocal pending_uc
        if pending_uc > 0:
            pending_uc -= 1
            return True
        return False

    i = 0
    n = len(rtf_text)
    while i < n:
        ch = rtf_text[i]

        if ch == '{':
            group_stack.append((bold, underline, uc_skip, skip_group))
            pending_uc = 0
            i += 1
            # Destination groups: {\*\word ...} or {\fonttbl ...}; source
            # line breaks may separate the brace from the control word
            j0 = i
            while j0 < n and rtf_text[j0] in '\r\n':
                j0 += 1
            if j0 < n and rtf_text[j0] == '\\':
                if j0 + 1 < n and rtf_text[j0 + 1] == '*':
                    skip_group = True
                else:
                    j = j0 + 1
                    while j < n and rtf_text[j].isalpha():
                        j += 1
                    if rtf_text[j0 + 1:j] in _SKIP_DESTINATIONS:
                        skip_group = True
            continue

        if ch == '}':
            if group_stack:
                bold, underline, uc_skip, skip_group = group_stack.pop()
            pending_uc = 0
            i += 1
            if not group_stack:
                break  # closed the root group: end of document
            continue

        if ch in '\r\n':
            # Line breaks in the RTF source are not content
            i += 1
            continue

        if ch != '\\':
            if not consume_uc_fallback():
                emit(ch)
            i += 1
            continue

        # Backslash: control word, control symbol, or escape
        if i + 1 >= n:
            break
        c = rtf_text[i + 1]

        if c == "'":
            # Hex escape, e.g. \'f8
            hex_chars = rtf_text[i + 2:i + 4]
            try:
                code = int(hex_chars, 16)
            except ValueError:
                code = None
            if len(hex_chars) == 2 and code is not None:
                if not consume_uc_fallback():
                    emit(_decode_hex_byte(code, codepage))
                i += 4
            else:
                # Invalid hex: preserve the characters as literal text
                if not consume_uc_fallback():
                    for hc in hex_chars:
                        emit(hc)
                i += 2 + len(hex_chars)
            continue

        if c in '\\{}':
            if not consume_uc_fallback():
                emit(c)
            i += 2
            continue
        if c == '~':
            if not consume_uc_fallback():
                emit('\xa0')  # non-breaking space
            i += 2
            continue
        if c == '_':
            if not consume_uc_fallback():
                emit('-')  # non-breaking hyphen
            i += 2
            continue
        if not c.isalpha():
            # \- (optional hyphen), \* (handled at group start), \<newline>
            # (line continuation), and any other control symbol: no content
            i += 2
            continue

        # Control word: letters, optional signed integer, optional one
        # space delimiter (the space belongs to the control word)
        j = i + 1
        while j < n and rtf_text[j].isalpha():
            j += 1
        word = rtf_text[i + 1:j]
        param: Optional[int] = None
        k = j
        if k < n and (rtf_text[k] == '-' or rtf_text[k].isdigit()):
            num_start = k
            if rtf_text[k] == '-':
                k += 1
            while k < n and rtf_text[k].isdigit():
                k += 1
            try:
                param = int(rtf_text[num_start:k])
            except ValueError:
                param = None
        if k < n and rtf_text[k] == ' ':
            k += 1
        i = k

        if word != 'u':
            # A \uN fallback is the character(s) immediately following the
            # \uN word; any other control word closes the fallback window
            # (otherwise e.g. the text after a \par would be swallowed)
            pending_uc = 0

        if word == 'b':
            bold = param != 0
        elif word == 'ul':
            underline = param != 0
        elif word == 'ulnone':
            underline = False
        elif word == 'plain':
            bold = False
            underline = False
        elif word in _SYMBOL_WORDS:
            emit(_SYMBOL_WORDS[word])
        elif word == 'uc':
            uc_skip = param if param is not None else 1
        elif word == 'u':
            code = param
            if code is not None:
                if code < 0:
                    code += 65536  # \uN is a signed 16-bit value
                if 0 <= code <= 0x10FFFF:
                    emit(chr(code))
            pending_uc = uc_skip
        elif word == 'ansicpg':
            if param is not None:
                codepage = param
        # All other control words carry no document text; ignore them.

    if not text_chars:
        return "", None

    _merge_surrogate_pairs(text_chars, style_chars)
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

"""Regression tests for RTF parser and generator bugs (BUG-4, BUG-14, BUG-21)."""

from pagemark.clipboard import ClipboardManager
from pagemark.rtf_parser import parse_rtf


# --- BUG-4: control words must be matched exactly, not by prefix ---

def test_blue_is_not_bold():
    text, styles = parse_rtf(r"{\rtf1\ansi\pard\plain the \blue4 sky\par}")
    assert text == "the sky\n"
    assert styles is None


def test_ulc_is_not_underline():
    text, styles = parse_rtf(r"{\rtf1\ansi\pard\plain a \ulc2 b\par}")
    assert text == "a b\n"
    assert styles is None


def test_pard_is_not_a_paragraph_break():
    # \pard must not be read as \par + "d". (The space after \pard is its
    # delimiter and is consumed, so no separator appears either.)
    text, _ = parse_rtf(r"{\rtf1\ansi\pard hello\pard world}")
    assert text == "helloworld"


# --- BUG-14.1: hex escapes are Windows-1252, not raw codepoints ---

def test_hex_escape_smart_quotes_cp1252():
    text, _ = parse_rtf(r"{\rtf1\ansi\pard\plain he said \'93hi\'94\par}")
    assert text == "he said “hi”\n"  # curly quotes, not C1 controls


def test_hex_escape_endash_cp1252():
    text, _ = parse_rtf(r"{\rtf1\ansi\pard\plain 1\'962\par}")
    assert text == "1–2\n"


# --- BUG-14.2: \uN fallback skipping must honor hex escapes and \ucN ---

def test_unicode_fallback_written_as_hex_escape():
    text, _ = parse_rtf(r"{\rtf1\ansi\pard\plain lambda: \u955\'3f end\par}")
    assert text == "lambda: λ end\n"


def test_uc0_means_no_fallback():
    # The space after \u955 is the control word's delimiter (consumed);
    # with \uc0 there is no fallback character to skip.
    text, _ = parse_rtf(r"{\rtf1\ansi\pard\plain \uc0\u955 end\par}")
    assert text == "λend\n"


def test_uc2_skips_two_fallback_chars():
    text, _ = parse_rtf(r"{\rtf1\ansi\pard\plain \uc2\u955 AB end\par}")
    assert text == "λ end\n"


# --- BUG-14.3: paragraph starting with an escaped character ---

def test_hex_escape_at_content_start():
    text, _ = parse_rtf(r"{\rtf1\ansi\pard\f0\fs24 \'e9tude\par}")
    assert text == "étude\n"


def test_unicode_escape_at_content_start():
    text, _ = parse_rtf(r"{\rtf1\ansi\pard\f0\fs24 \u233?tude\par}")
    assert text == "étude\n"


# --- BUG-14.4: destination groups must be skipped even without \pard ---

def test_font_table_does_not_leak_without_pard():
    text, _ = parse_rtf(r"{\rtf1\ansi{\fonttbl{\f0\fswiss Arial;}}Hello world}")
    assert text == "Hello world"


def test_starred_destination_groups_skipped():
    text, _ = parse_rtf(r"{\rtf1\ansi{\*\generator LibreOffice}Hello}")
    assert text == "Hello"


# --- BUG-14.5: \tab, \line, and symbol words produce characters ---

def test_tab_becomes_space():
    text, _ = parse_rtf(r"{\rtf1\ansi\pard\plain a\tab b\par}")
    assert text == "a b\n"


def test_line_becomes_newline():
    text, _ = parse_rtf(r"{\rtf1\ansi\pard\plain a\line b\par}")
    assert text == "a\nb\n"


def test_symbol_words():
    text, _ = parse_rtf(r"{\rtf1\ansi\pard\plain a\emdash b \lquote c\rquote\par}")
    assert text == "a—b ‘c’\n"


# --- Review findings on the tokenizer rewrite ---

def test_destination_group_after_source_newline_is_skipped():
    # Pretty-printed RTF may put a line break between '{' and the
    # destination word; header text must still not leak into the paste.
    text, _ = parse_rtf("{\\rtf1\\ansi{\n\\fonttbl{\\f0 Helvetica;}}Hello world}")
    assert text == "Hello world"


def test_unicode_without_fallback_does_not_swallow_par():
    # Minimal generators omit the \uN fallback character; the following
    # \par must not be consumed as the fallback.
    text, _ = parse_rtf(r"{\rtf1\ansi\pard a\u246\par b\par}")
    assert text == "aö\nb\n"


def test_field_result_text_is_kept():
    # Hyperlinks arrive as \field groups; the \fldrslt part is the visible
    # text and must survive (the \*\fldinst instruction is skipped).
    rtf = (r'{\rtf1\ansi before {\field{\*\fldinst HYPERLINK "http://x.com"}'
           r'{\fldrslt Click here}} after}')
    text, _ = parse_rtf(rtf)
    assert text == "before Click here after"


def test_footnote_body_is_skipped():
    rtf = r"{\rtf1\ansi One.\chftn {\footnote body text.} Two.}"
    text, _ = parse_rtf(rtf)
    assert text == "One. Two."


def test_hex_escapes_use_declared_codepage():
    # \ansicpg1251 (Cyrillic): 0xE0-0xE2 are а, б, в — not à, á, â
    text, _ = parse_rtf(r"{\rtf1\ansi\ansicpg1251\pard \'e0\'e1\'e2\par}")
    assert text == "абв\n"


# --- BUG-21: RTF generation for characters above U+7FFF ---

def test_escape_rtf_uses_signed_16_bit_values():
    # U+8000 and above must be written as negative numbers
    rtf = ClipboardManager._escape_rtf("者")
    assert rtf == f"\\u{0x8005 - 0x10000}?"


def test_escape_rtf_emoji_surrogate_pair():
    rtf = ClipboardManager._escape_rtf("😀")  # U+1F600
    assert rtf == "\\u-10179?\\u-8704?"


def test_emoji_round_trip():
    text = "hi 😀 there"
    styles = [[1] * len(text)]  # bold, to force the RTF path
    rtf = ClipboardManager._generate_rtf(text, styles)
    parsed_text, parsed_styles = parse_rtf(rtf)
    assert parsed_text == text
    assert parsed_styles is not None
    assert parsed_styles[0] == [1] * len(text)


def test_bmp_high_char_round_trip():
    text = "圀"  # U+5700, above 0x7FFF but in the BMP
    rtf = ClipboardManager._generate_rtf(text, [[2]])
    parsed_text, parsed_styles = parse_rtf(rtf)
    assert parsed_text == text
    assert parsed_styles == [[2]]

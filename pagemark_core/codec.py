"""Pagemark overstrikes, with explicit rejection of unrepresentable new styling.

The decoder matches terminal Pagemark. The original bytes are retained so an
unchanged document, including its newline convention, can be saved unchanged.
"""
from __future__ import annotations

from dataclasses import dataclass

BOLD = 1
UNDERLINE = 2
MAX_DOCUMENT_BYTES = 16 * 1024 * 1024


@dataclass(frozen=True)
class StyledText:
    text: str
    styles: tuple[int, ...]

    def __post_init__(self):
        if len(self.text) != len(self.styles):
            raise ValueError("Text and style lengths differ")
        if any(flag not in (0, BOLD, UNDERLINE, BOLD | UNDERLINE) for flag in self.styles):
            raise ValueError("Unsupported text style")

    def parts(self) -> tuple[list[str], list[list[int]]]:
        paragraphs = self.text.split("\n")
        styles = []
        offset = 0
        for paragraph in paragraphs:
            styles.append(list(self.styles[offset:offset + len(paragraph)]))
            offset += len(paragraph) + 1
        return paragraphs, styles


def parse_overstrike_paragraph(text: str) -> tuple[str, list[int]]:
    output, styles = [], []
    i = 0
    while i < len(text):
        char = text[i]
        if char == "_" and i + 2 < len(text) and text[i + 1] == "\b":
            char = text[i + 2]
            flag = UNDERLINE
            if i + 4 < len(text) and text[i + 3:i + 5] == "\b" + char:
                flag |= BOLD
                i += 5
            else:
                i += 3
        elif i + 2 < len(text) and text[i + 1:i + 3] == "\b" + char:
            flag = BOLD
            i += 3
        else:
            flag = 0
            i += 1
        output.append(char)
        styles.append(flag)
    return "".join(output), styles


def encode_overstrike_paragraph(text: str, styles: list[int]) -> str:
    """Legacy representation; callers decide whether to reject ambiguous styles."""
    output = []
    for i, char in enumerate(text):
        flag = styles[i] if i < len(styles) else 0
        output.append(("_\b" if flag & UNDERLINE else "") + char
                      + ("\b" + char if flag & BOLD else ""))
    return "".join(output)


def decode(data: bytes) -> StyledText:
    if len(data) > MAX_DOCUMENT_BYTES:
        raise ValueError("This prototype opens documents up to 16 MiB")
    source = data.decode("utf-8").replace("\r\n", "\n").replace("\r", "\n")
    text, styles = [], []
    for paragraph_index, paragraph in enumerate(source.split("\n")):
        if paragraph_index:
            text.append("\n")
            styles.append(0)
        plain, flags = parse_overstrike_paragraph(paragraph)
        text.append(plain)
        styles.extend(flags)
    return StyledText("".join(text), tuple(styles))


def encode(value: StyledText, original: bytes | None = None) -> bytes:
    if original is not None and decode(original) == value:
        return original
    paragraphs, styles = value.parts()
    data = "\n".join(encode_overstrike_paragraph(text, flags)
                     for text, flags in zip(paragraphs, styles)).encode("utf-8")
    if decode(data) != value:
        raise ValueError("This formatting cannot round-trip through Pagemark's legacy format. "
                         "For example, a bold underscore is ambiguous. Your edits are retained.")
    if original and b"\r\n" in original and b"\n" not in original.replace(b"\r\n", b""):
        data = data.replace(b"\n", b"\r\n")
    return data


def utf16_offsets(text: str) -> list[int]:
    offsets = [0]
    for char in text:
        offsets.append(offsets[-1] + (2 if ord(char) > 0xFFFF else 1))
    return offsets

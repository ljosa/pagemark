"""Terminal cell measurements for document text (em dashes display as ``--``)."""

from collections.abc import Iterator

from wcwidth import wcwidth, wcswidth


def display_width(text: str) -> int:
    """Measure terminal cells after applying the document's dash convention."""
    if text.isascii() and text.isprintable():
        return len(text)
    return max(0, wcswidth(text.replace("—", "--")))


def display_spans(text: str) -> Iterator[tuple[int, int, int]]:
    """Yield source start/end indices and cell widths of display units.

    Keep zero-width marks with their base so wrapping and terminal attribute
    changes do not separate a combining sequence. Also retain joined sequences
    in loaded text; typed/pasted input normally filters joiner controls.
    """
    if text.isascii() and text.isprintable():
        for index in range(len(text)):
            yield index, index + 1, 1
        return
    start = 0
    while start < len(text):
        end = start + 1
        while end < len(text) and (
            wcwidth(text[end]) == 0 or text[end - 1] == "\u200d"
        ):
            end += 1
        yield start, end, display_width(text[start:end])
        start = end


def display_prefix(text: str, width: int, *, force_progress: bool = False) -> str:
    """Return a prefix fitting in cells, optionally consuming an oversized unit."""
    if text.isascii() and text.isprintable():
        return text[: max(1 if force_progress else 0, width)]
    column = 0
    end = 0
    for start, stop, unit_width in display_spans(text):
        if column + unit_width > width:
            if force_progress and start == 0:
                end = stop
            break
        column += unit_width
        end = stop
    return text[:end]

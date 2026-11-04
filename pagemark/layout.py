"""Pure, immutable paragraph and document layout.

Source offsets count Python codepoints; columns count terminal cells. A consumed
wrap separator belongs to the preceding line, including at its right margin.
Hard-wrap boundaries and full-width paragraph ends belong to the continuation.
Only this module defines these mappings; painters must not wrap the cursor again.
"""

from __future__ import annotations

from bisect import bisect_right
from dataclasses import dataclass
from functools import lru_cache
import re
from typing import Optional, Sequence

from .coordinates import CellColumn, ContentLineIndex, DocumentPosition, SourceOffset
from .text_layout import display_prefix, display_spans, display_width


@dataclass(frozen=True)
class LayoutLine:
    text: str
    start: SourceOffset
    end: SourceOffset
    indent: CellColumn
    # One source index per rendered codepoint, not per terminal cell.
    # Synthetic indentation has no source; an em dash has two entries.
    sources: tuple[Optional[SourceOffset], ...]
    caret_stops: tuple[tuple[SourceOffset, CellColumn], ...]

    def styles(self, mask: Sequence[int]) -> list[int]:
        return [mask[i] if i is not None and i < len(mask) else 0 for i in self.sources]

    def selection(self, start: int, end: int) -> Optional[tuple[int, int]]:
        selected = [
            i
            for i, source in enumerate(self.sources)
            if source is not None and start <= source < end
        ]
        if not selected:
            return None
        return (
            display_width(self.text[: selected[0]]),
            display_width(self.text[: selected[-1] + 1]),
        )


@dataclass(frozen=True)
class ParagraphLayout:
    paragraph: str
    num_columns: int
    hanging_width: int
    rows: tuple[LayoutLine, ...]
    boundaries: tuple[int, ...]

    @property
    def lines(self) -> list[str]:
        """Compatibility copy; callers cannot mutate cached layout."""
        return [row.text for row in self.rows]

    @property
    def cumulative_counts(self) -> list[int]:
        return list(self.boundaries)

    @property
    def line_count(self) -> int:
        return len(self.rows)

    def line_start(self, line_index: int) -> int:
        if line_index <= 0:
            return 0
        return self.boundaries[min(line_index, self.line_count) - 1]

    def line_end(self, line_index: int) -> int:
        if line_index < 0:
            return 0
        return self.boundaries[min(line_index, self.line_count - 1)]

    def line_for_char_index(self, char_index: int) -> int:
        return min(bisect_right(self.boundaries, char_index), self.line_count - 1)

    def char_to_line_and_column(self, char_index: int) -> tuple[int, int]:
        line = self.line_for_char_index(char_index)
        return line, char_index - self.line_start(line)

    def line_and_column_to_char(self, line_index: int, column: int) -> int:
        return self.line_start(line_index) + column

    def visual_column(self, char_index: int) -> int:
        line = self.rows[self.line_for_char_index(char_index)]
        return line.indent + display_width(self.paragraph[line.start : char_index])

    def character_at_column(self, line_index: int, column: int) -> int:
        stops = self.rows[line_index].caret_stops
        for offset, cell in stops:
            if cell >= column:
                return offset
        return stops[-1][0]

    def content_column_from_visual(self, line_index: int, visual_column: int) -> int:
        return self.character_at_column(line_index, visual_column) - self.line_start(
            line_index
        )

    def line_content_length(self, line_index: int) -> int:
        if not 0 <= line_index < self.line_count:
            return 0
        return self.line_end(line_index) - self.line_start(line_index)

    def has_hanging_indent(self, line_index: int) -> bool:
        return line_index > 0 and self.hanging_width > 0

    def visual_line_width(self, line_index: int) -> int:
        return (
            display_width(self.rows[line_index].text)
            if 0 <= line_index < self.line_count
            else 0
        )

    def is_extended(self, line_index: int) -> bool:
        return self.visual_line_width(line_index) > self.num_columns


def _get_hanging_indent_width(paragraph: str) -> int:
    """Return hanging indent width for bullet/numbered paragraphs.

    Detects optional leading spaces, then one of:
    - '-', '*', or non-breaking space (U+00A0) followed by exactly one space
    - one or more digits followed by '.' or ')' and exactly one space

    Returns total columns before first text char (base indent + marker + one space),
    or 0 if not a bullet/numbered paragraph.
    """
    # Leading spaces
    # Require exactly one space after the marker by asserting the next
    # character is non-space. This prevents triggering on multiple spaces.
    m = re.match(r"^(\s*)(?:([-*\xa0]) (?=\S)|((?:\d+)(?:[\.)]) (?=\S)))", paragraph)
    if not m:
        return 0
    leading = m.group(1) or ""
    marker = m.group(2)
    numbered = m.group(3)
    if marker is not None:
        # '-', '*', or non-breaking space with exactly one trailing space matched
        return len(leading) + len(marker) + 1
    if numbered is not None:
        # '\d+.' or '\d+)' with exactly one trailing space matched
        return len(leading) + len(numbered)
    return 0


def get_hanging_indent_width(paragraph: str, num_columns: Optional[int] = None) -> int:
    """Public helper: return hanging indent width for bullets/numbers.

    This wraps the internal implementation to provide a stable API for
    other modules (e.g., printing/formatting) without importing a private
    function.
    """
    width = _get_hanging_indent_width(paragraph)
    # Reserve room for a two-column character (including displayed em dashes).
    # Use the same effective indent in rendering, navigation, and styling.
    if num_columns is not None:
        width = min(width, max(0, num_columns - 2))
    return width


def _wrap_paragraph(paragraph: str, num_columns: int) -> tuple[list[str], list[int]]:
    """Render into a list of lines, with word wrap and hanging indents.

    Returns (lines, cumulative_counts) where cumulative_counts are character
    counts in the original paragraph at the end of each visual line. Visual
    indent spaces for wrapped bullet/numbered paragraphs are not counted in
    cumulative_counts.

    Double-space handling: When two consecutive spaces would cause the second
    space to wrap to the next line, both spaces are kept on the current line
    by extending it into the right margin (up to num_columns + 1).
    """
    if num_columns < 1:
        raise ValueError("num_columns must be positive")
    if not paragraph:
        return ([""], [0])

    visual_width = display_width

    def slice_to_visual_width(text: str, max_visual_width: int) -> str:
        return display_prefix(text, max_visual_width, force_progress=True)

    hanging_width = get_hanging_indent_width(paragraph, num_columns)
    indent_prefix = " " * hanging_width if hanging_width > 0 else ""

    lines: list[str] = []
    cumulative_counts: list[int] = []
    char_count = 0
    words = paragraph.split(" ")
    current_line: Optional[str] = None
    line_index = 0
    skip_next_space = False  # Set when double-space extended into margin

    def available_width_for_line(idx: int) -> int:
        if idx == 0:
            return num_columns
        return num_columns - hanging_width if hanging_width > 0 else num_columns

    def get_line_prefix(idx: int) -> str:
        """Get the visual prefix for a line (hanging indent spaces for wrapped lines)."""
        return indent_prefix if (idx > 0 and hanging_width > 0) else ""

    for i, word in enumerate(words):
        width = available_width_for_line(line_index)
        is_empty_word = len(word) == 0
        is_not_last_word = i < len(words) - 1

        if current_line is None:
            # First word on the line
            if is_empty_word:
                # Empty word at line start means a space should start this line
                # (happens with 3+ consecutive spaces where third wraps)
                current_line = ""
            elif visual_width(word) >= width:
                # Break long word across as many lines as needed
                while visual_width(word) >= width:
                    slice_text = slice_to_visual_width(word, width)
                    lines.append(get_line_prefix(line_index) + slice_text)
                    char_count += len(slice_text)
                    cumulative_counts.append(char_count)
                    word = word[len(slice_text) :]
                    line_index += 1
                    width = available_width_for_line(line_index)
                current_line = word
            else:
                current_line = word
        elif skip_next_space:
            # Previous iteration added double-space into margin; don't add separator
            skip_next_space = False
            if is_empty_word:
                # Third+ consecutive space - wrap it to new line
                lines.append(get_line_prefix(line_index) + current_line)
                char_count += len(current_line)
                cumulative_counts.append(char_count)
                line_index += 1
                current_line = (
                    ""  # Start new line (space will be added by next iteration)
                )
            elif visual_width(current_line) + visual_width(word) <= width:
                current_line += word
            else:
                # Word doesn't fit - commit current line and start new
                lines.append(get_line_prefix(line_index) + current_line)
                char_count += len(current_line)
                cumulative_counts.append(char_count)
                line_index += 1
                width = available_width_for_line(line_index)
                # Handle long word
                if visual_width(word) >= width:
                    while visual_width(word) >= width:
                        slice_text = slice_to_visual_width(word, width)
                        lines.append(get_line_prefix(line_index) + slice_text)
                        char_count += len(slice_text)
                        cumulative_counts.append(char_count)
                        word = word[len(slice_text) :]
                        line_index += 1
                        width = available_width_for_line(line_index)
                    current_line = word
                else:
                    current_line = word
        elif is_empty_word:
            # Empty word = second space of consecutive spaces
            # Only extend into margin when adding space EXACTLY fills the line
            if visual_width(current_line) + 1 == width and is_not_last_word:
                # Extend into margin: add both spaces (keeps double-space together)
                current_line += "  "
                skip_next_space = True
            else:
                # Normal case - just add the separator space
                current_line += " "
        else:
            # Normal word - check if it fits
            if visual_width(current_line) + 1 + visual_width(word) <= width:
                current_line += " " + word
            else:
                # Commit current line
                lines.append(get_line_prefix(line_index) + current_line)
                char_count += len(current_line) + 1  # +1 for the space before next word
                cumulative_counts.append(char_count)
                line_index += 1
                width = available_width_for_line(line_index)
                # Place the word on the new line, breaking if needed
                if visual_width(word) >= width:
                    while visual_width(word) >= width:
                        slice_text = slice_to_visual_width(word, width)
                        lines.append(get_line_prefix(line_index) + slice_text)
                        char_count += len(slice_text)
                        cumulative_counts.append(char_count)
                        word = word[len(slice_text) :]
                        line_index += 1
                        width = available_width_for_line(line_index)
                    current_line = word
                else:
                    current_line = word

    assert current_line is not None
    # Append the final line
    lines.append(get_line_prefix(line_index) + current_line)
    char_count += len(current_line)
    cumulative_counts.append(char_count)
    # A completely full final line needs a continuation position for the
    # cursor, just like a long word split exactly at the wrapping boundary.
    if visual_width(current_line) == available_width_for_line(line_index):
        lines.append(get_line_prefix(line_index + 1))
        cumulative_counts.append(char_count)

    # Replace em-dashes with double hyphens for display
    lines = [line.replace("—", "--") for line in lines]

    return (lines, cumulative_counts)


def expand_styles_for_display(content: str, styles: list[int]) -> list[int]:
    """Expand a per-character style slice to per-display-column styles.

    Em-dashes occupy one content character but two display columns (rendered
    as "--"), so their style flag is duplicated. Without this, every style
    run to the right of an em-dash is shifted left by one column per dash.
    """
    if "—" not in content:
        # Hot path: render() calls this per line per keystroke; a C-level
        # scan beats the per-character loop for the overwhelmingly common
        # dash-free line. (Callers pad short slices themselves.)
        return styles
    out: list[int] = []
    for idx, ch in enumerate(content):
        flag = styles[idx] if idx < len(styles) else 0
        out.append(flag)
        if ch == "—":
            out.append(flag)
    return out


@lru_cache(maxsize=256)
def layout_paragraph(paragraph: str, width: int) -> ParagraphLayout:
    lines, counts = _wrap_paragraph(paragraph, width)
    indent = get_hanging_indent_width(paragraph, width)
    rows = []
    start = 0
    for index, (text, end) in enumerate(zip(lines, counts)):
        prefix = indent if index else 0
        sources: list[Optional[SourceOffset]] = [None] * prefix
        for offset in range(start, end):
            sources.extend(
                [SourceOffset(offset)] * (2 if paragraph[offset] == "—" else 1)
            )
        sources = sources[: len(text)]
        stops = [(SourceOffset(start), CellColumn(prefix))]
        column = prefix
        for _, stop, cells in display_spans(paragraph[start:end]):
            column += cells
            offset = start + stop
            if offset < end or index == len(lines) - 1:
                stops.append((SourceOffset(offset), CellColumn(column)))
        rows.append(
            LayoutLine(
                text,
                SourceOffset(start),
                SourceOffset(end),
                CellColumn(prefix),
                tuple(sources),
                tuple(stops),
            )
        )
        start = end
    return ParagraphLayout(paragraph, width, indent, tuple(rows), tuple(counts))


def render_paragraph(paragraph: str, num_columns: int) -> tuple[list[str], list[int]]:
    layout = layout_paragraph(paragraph, num_columns)
    return layout.lines, layout.cumulative_counts


# Historical public names; both use the authoritative layout implementation.
VisualLineMapper = ParagraphLayout
get_line_mapper = layout_paragraph


@dataclass(frozen=True)
class DocumentLayout:
    paragraphs: tuple[ParagraphLayout, ...]
    starts: tuple[int, ...]
    line_count: int

    @classmethod
    def build(cls, paragraphs: Sequence[str], width: int) -> DocumentLayout:
        layouts = tuple(layout_paragraph(text, width) for text in paragraphs) or (
            layout_paragraph("", width),
        )
        starts = []
        count = 0
        for layout in layouts:
            starts.append(count)
            count += layout.line_count
        return cls(layouts, tuple(starts), count)

    def locate_line(self, line: int) -> tuple[int, int]:
        line = min(max(0, line), self.line_count - 1)
        paragraph = bisect_right(self.starts, line) - 1
        return paragraph, line - self.starts[paragraph]

    def line_at(self, line: int) -> LayoutLine:
        pi, li = self.locate_line(line)
        return self.paragraphs[pi].rows[li]

    def line_for_position(self, position: DocumentPosition) -> ContentLineIndex:
        pi = min(max(0, position.paragraph_index), len(self.paragraphs) - 1)
        return ContentLineIndex(
            self.starts[pi]
            + self.paragraphs[pi].line_for_char_index(position.character_index)
        )

    def position_at(self, line: int, column: int) -> DocumentPosition:
        pi, li = self.locate_line(line)
        return DocumentPosition(pi, self.paragraphs[pi].character_at_column(li, column))

    def column_for_position(self, position: DocumentPosition) -> CellColumn:
        return CellColumn(
            self.paragraphs[position.paragraph_index].visual_column(
                position.character_index
            )
        )

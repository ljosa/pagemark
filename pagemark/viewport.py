"""Pure viewport geometry. Page markers are rows, never document content.

The top is anchored to a content line. A marker preceding that line is outside
this viewport. All visibility and paging decisions use the same row sequence.
"""
from dataclasses import dataclass, replace

from .coordinates import ContentLineIndex, ScreenRowIndex


@dataclass(frozen=True)
class TextRow:
    line: ContentLineIndex


@dataclass(frozen=True)
class PageBreakRow:
    page: int


@dataclass(frozen=True)
class Viewport:
    top: ContentLineIndex
    height: int
    lines_per_page: int

    def __post_init__(self) -> None:
        if self.height < 1 or self.lines_per_page < 1:
            raise ValueError("Viewport height and page length must be positive")

    def normalized(self, total: int) -> "Viewport":
        if total < 1:
            raise ValueError("A document must have at least one content line")
        return replace(self, top=ContentLineIndex(min(max(0, self.top), total - 1)))

    def _physical_row(self, line: int) -> int:
        return line + line // self.lines_per_page

    def _content_line(self, row: int, *, round_up: bool) -> ContentLineIndex:
        page, offset = divmod(max(0, row), self.lines_per_page + 1)
        if offset == self.lines_per_page and not round_up:
            offset -= 1
        return ContentLineIndex(page * self.lines_per_page + offset)

    def row_for_line(self, line: int) -> ScreenRowIndex:
        return ScreenRowIndex(self._physical_row(line) - self._physical_row(self.top))

    def rows(self, total: int) -> tuple[TextRow | PageBreakRow, ...]:
        viewport = self.normalized(total)
        result: list[TextRow | PageBreakRow] = []
        line = viewport.top
        while len(result) < self.height and line < total:
            result.append(TextRow(ContentLineIndex(line)))
            line += 1
            if (line < total and line % self.lines_per_page == 0
                    and len(result) < self.height):
                result.append(PageBreakRow(line // self.lines_per_page + 1))
        return tuple(result)

    def centered(self, cursor: int, total: int) -> "Viewport":
        cursor = min(max(0, cursor), total - 1)
        top = self._content_line(self._physical_row(cursor) - self.height // 2,
                                 round_up=True)
        return replace(self, top=top).normalized(total)

    def ensure_visible(self, cursor: int, total: int) -> "Viewport":
        viewport = self.normalized(total)
        if 0 <= viewport.row_for_line(cursor) < self.height:
            return viewport
        return viewport.centered(cursor, total)

    def scroll_page(self, direction: int, total: int, overlap: int = 2) -> "Viewport":
        if direction not in (-1, 1):
            raise ValueError("Page direction must be -1 or 1")
        viewport = self.normalized(total)
        row = viewport._physical_row(viewport.top) + direction * max(1, self.height - overlap)
        top = viewport._content_line(row, round_up=direction < 0)
        # A one-row step can land on a marker; still make content progress.
        if top == viewport.top:
            top = ContentLineIndex(top + direction)
        return replace(viewport, top=top).normalized(total)

    def clamp_line(self, line: int, total: int) -> ContentLineIndex:
        content = [row.line for row in self.rows(total) if isinstance(row, TextRow)]
        return ContentLineIndex(min(max(line, content[0]), content[-1]))

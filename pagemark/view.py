"""Terminal presentation adapter for the pure layout and viewport modules."""
from .coordinates import ContentLineIndex, DocumentPosition
from .constants import EditorConstants
from .model import TextView
from .layout import DocumentLayout
# Preserve the public imports used by existing clients.
from .layout import (  # noqa: F401
    VisualLineMapper, get_line_mapper, render_paragraph,
    get_hanging_indent_width, expand_styles_for_display,
)
from .viewport import PageBreakRow, TextRow, Viewport


class TerminalTextView(TextView):
    num_rows: int
    num_columns: int
    LINES_PER_PAGE = EditorConstants.LINES_PER_PAGE
    CONTEXT_LINES = 2

    def __init__(self) -> None:
        self.start_paragraph_index = 0
        self.end_paragraph_index = 1
        self.first_paragraph_line_offset = 0
        self.visual_cursor_y = 0
        self.visual_cursor_x = 0
        self._desired_x = 0
        self._double_spacing = False
        self.lines: list[str] = []
        self.line_styles: list[list[int]] = []
        self._frame_rows: tuple[TextRow | PageBreakRow, ...] = ()
        self._layout_key = None

    @property
    def desired_x(self) -> int:
        return self.model.desired_column if self._model is not None else self._desired_x

    @desired_x.setter
    def desired_x(self, value: int) -> None:
        self._desired_x = value
        if self._model is not None:
            self.model.desired_column = value

    def set_double_spacing(self, enabled: bool) -> None:
        self._double_spacing = bool(enabled)

    def _effective_lines_per_page(self) -> int:
        return max(1, self.LINES_PER_PAGE // (2 if self._double_spacing else 1))

    def _create_page_break_line(self, page_num: int) -> str:
        text = f" Page {page_num} "
        padding = max(0, (self.num_columns - len(text)) // 2)
        return ("─" * padding + text).ljust(self.num_columns, "─")[:self.num_columns]

    def _document_layout(self) -> DocumentLayout:
        key = (tuple(self.model.paragraphs), self.num_columns)
        if key != self._layout_key:
            self._layout = DocumentLayout.build(key[0], key[1])
            self._layout_key = key
        return self._layout

    def _position(self) -> DocumentPosition:
        cursor = self.model.cursor_position
        return DocumentPosition(cursor.paragraph_index, cursor.character_index)

    def _viewport(self, layout: DocumentLayout) -> Viewport:
        # Document edits can remove the old top paragraph or wrapped line.
        pi = min(max(0, self.start_paragraph_index), len(layout.paragraphs) - 1)
        li = min(max(0, self.first_paragraph_line_offset), layout.paragraphs[pi].line_count - 1)
        return Viewport(ContentLineIndex(layout.starts[pi] + li),
                        max(1, self.num_rows), self._effective_lines_per_page())

    def _set_viewport(self, viewport: Viewport, layout: DocumentLayout) -> None:
        self.start_paragraph_index, self.first_paragraph_line_offset = layout.locate_line(viewport.top)

    def render(self) -> None:
        layout = self._document_layout()
        cursor_line = layout.line_for_position(self._position())
        viewport = self._viewport(layout).ensure_visible(cursor_line, layout.line_count)
        self._set_viewport(viewport, layout)
        self._layout = layout
        self._frame_rows = viewport.rows(layout.line_count)
        self.lines = []
        self.line_styles = []
        for row in self._frame_rows:
            if isinstance(row, PageBreakRow):
                text = self._create_page_break_line(row.page)
                self.lines.append(text)
                self.line_styles.append([0] * len(text))
            else:
                pi, li = layout.locate_line(row.line)
                line = layout.paragraphs[pi].rows[li]
                self.lines.append(line.text)
                self.line_styles.append(line.styles(self.model.styles[pi]))
                self.end_paragraph_index = pi + 1
        self.visual_cursor_y = viewport.row_for_line(cursor_line)
        self.visual_cursor_x = layout.column_for_position(self._position())

    def get_selection_ranges(self):
        start, end = self.model.selection_start, self.model.selection_end
        if start is None or end is None:
            return None
        if end < start:
            start, end = end, start
        ranges = []
        for row in self._frame_rows:
            if isinstance(row, PageBreakRow):
                ranges.append(None)
                continue
            pi, li = self._layout.locate_line(row.line)
            if not start.paragraph_index <= pi <= end.paragraph_index:
                ranges.append(None)
                continue
            paragraph = self._layout.paragraphs[pi]
            first = start.character_index if pi == start.paragraph_index else 0
            last = end.character_index if pi == end.paragraph_index else len(paragraph.paragraph)
            ranges.append(paragraph.rows[li].selection(first, last))
        return ranges

    def _get_paragraph_line_count(self, paragraph_index: int) -> int:
        return get_line_mapper(self.model.paragraphs[paragraph_index], self.num_columns).line_count

    def center_view_on_cursor(self) -> None:
        layout = self._document_layout()
        viewport = self._viewport(layout).centered(layout.line_for_position(self._position()), layout.line_count)
        self._set_viewport(viewport, layout)

    def _move_to_line(self, layout: DocumentLayout, line: int, column: int) -> None:
        position = layout.position_at(line, column)
        self.model.relocate_cursor(position, preserve_column=True, render=False)

    def _move_vertical(self, direction: int) -> None:
        layout = self._document_layout()
        target = layout.line_for_position(self._position()) + direction
        if 0 <= target < layout.line_count:
            self._move_to_line(layout, target, self.desired_x)
        self.render()

    def move_cursor_up(self) -> None:
        self._move_vertical(-1)

    def move_cursor_down(self) -> None:
        self._move_vertical(1)

    def _move_cursor_to_visual_line(self, visual_y: int, desired_x: int) -> None:
        if 0 <= visual_y < len(self._frame_rows):
            row = self._frame_rows[visual_y]
            if isinstance(row, TextRow):
                self._move_to_line(self._layout, row.line, desired_x)
                self.render()

    def update_desired_x(self) -> None:
        self.model.desired_column = self.model.cursor_column()

    def _scroll_page(self, direction: int) -> None:
        layout = self._document_layout()
        viewport = self._viewport(layout).scroll_page(direction, layout.line_count, self.CONTEXT_LINES)
        cursor_line = layout.line_for_position(self._position())
        target = viewport.clamp_line(cursor_line, layout.line_count)
        self._set_viewport(viewport, layout)
        if target != cursor_line:
            self._move_to_line(layout, target, self.desired_x)
        self.render()

    def scroll_page_down(self) -> None:
        self._scroll_page(1)

    def scroll_page_up(self) -> None:
        self._scroll_page(-1)

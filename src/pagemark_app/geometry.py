"""Pixel geometry over shared content lines; paper gaps never enter the model."""
from dataclasses import dataclass
from math import ceil


@dataclass(frozen=True)
class CellMetrics:
    width: float
    height: float
    baseline: float


@dataclass(frozen=True)
class EditorGeometry:
    line_count: int
    viewport_width: float
    pages: bool = False
    double_spacing: bool = False
    zoom: float = 1.25
    columns: int = 65
    draft_metrics: CellMetrics | None = None

    @property
    def rows_per_page(self):
        return 27 if self.double_spacing else 54

    @property
    def page_count(self):
        return max(1, ceil(self.line_count / self.rows_per_page))

    @property
    def cell_width(self):
        if self.draft_metrics:
            return self.draft_metrics.width
        return (7.2 if self.columns == 65 else 6.0) * self.zoom

    @property
    def line_height(self):
        if self.draft_metrics:
            return self.draft_metrics.height * (2 if self.double_spacing else 1)
        return (24 if self.double_spacing else 12) * self.zoom

    @property
    def ink_top(self):
        return 0 if self.draft_metrics else 3 * self.zoom

    @property
    def ink_height(self):
        return self.draft_metrics.height if self.draft_metrics else 12 * self.zoom

    @property
    def baseline(self):
        return self.draft_metrics.baseline if self.draft_metrics else 12 * self.zoom

    @property
    def horizontal_padding(self):
        return 80 if self.draft_metrics else 40

    @property
    def content_width(self):
        return self.columns * self.cell_width if self.draft_metrics else 612 * self.zoom

    @property
    def natural_width(self):
        return self.content_width + self.horizontal_padding

    @property
    def width(self):
        return max(self.viewport_width, self.natural_width)

    @property
    def paper_x(self):
        return (self.width - 612 * self.zoom) / 2

    @property
    def text_x(self):
        if self.draft_metrics:
            return (self.width - self.columns * self.cell_width) / 2
        return self.paper_x + (72 if self.columns == 65 else 90) * self.zoom

    @property
    def page_stride(self):
        return 792 * self.zoom + 24 if self.pages else self.rows_per_page * self.line_height + 28

    @property
    def text_top(self):
        return 20 + 72 * self.zoom if self.pages else 40

    @property
    def height(self):
        if self.pages:
            return 20 + self.page_count * self.page_stride
        return self.line_y(max(0, self.line_count - 1)) + self.line_height + 60

    def line_y(self, line):
        page, row = divmod(line, self.rows_per_page)
        return self.text_top + page * self.page_stride + row * self.line_height

    def line_at_y(self, y):
        page = max(0, min(int((y - 20) // self.page_stride), self.page_count - 1))
        # Clamp a click in a margin/gap to the nearest actual line, including
        # the preceding page's final row and following page's first row.
        candidates = set()
        for near in range(max(0, page - 1), min(self.page_count, page + 2)):
            row = round((y - self.text_top - near * self.page_stride) / self.line_height)
            row = max(0, min(row, self.rows_per_page - 1))
            candidates.add(min(self.line_count - 1, near * self.rows_per_page + row))
        return min(candidates, key=lambda line: abs(y - self.line_y(line)))

    def point(self, line, column):
        return self.text_x + column * self.cell_width, self.line_y(line)

    def hit(self, layout, x, y):
        line = self.line_at_y(y - self.line_height / 2)
        row = layout.line_at(line)
        column = (x - self.text_x) / self.cell_width
        offset, _ = min(row.caret_stops, key=lambda stop: abs(stop[1] - column))
        paragraph, _ = layout.locate_line(line)
        from pagemark_core.coordinates import DocumentPosition
        return DocumentPosition(paragraph, offset)

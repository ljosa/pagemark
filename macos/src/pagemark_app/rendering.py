"""Pure drawing runs over shared layout; this module never wraps text.

ASCII cells of the same appearance can be drawn as one fixed-pitch string.
Other display clusters retain their explicit cell positions, including font
fallback, combining characters and wide glyphs. Selection is presentation data.
"""
from dataclasses import dataclass

from pagemark_core.text_layout import display_spans


@dataclass(frozen=True)
class TextRun:
    text: str
    column: int
    style: int
    selected: bool


def text_runs(row, styles, start=0, end=0, *, batch_ascii=True):
    """Group drawable cells without changing source/style/selection mappings."""
    runs = []
    text = []
    column = 0
    run_column = 0
    appearance = None

    def flush():
        if text:
            runs.append(TextRun("".join(text), run_column, *appearance))
            text.clear()

    for begin, stop, cells in display_spans(row.text):
        source = row.sources[begin] if begin < len(row.sources) else None
        style = styles[source] if source is not None and source < len(styles) else 0
        selected = source is not None and start <= source < end
        cluster = row.text[begin:stop]
        current = (style, selected)
        if batch_ascii and cluster.isascii() and cluster.isprintable():
            if appearance != current:
                flush()
            if not text:
                run_column, appearance = column, current
            text.append(cluster)
        else:
            flush()
            runs.append(TextRun(cluster, column, *current))
        column += cells
    flush()
    return tuple(runs)

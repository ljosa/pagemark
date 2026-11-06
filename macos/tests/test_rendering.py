"""Batching must preserve fixed cells, source styles and selection boundaries."""
import pytest


from pagemark_core.layout import layout_paragraph  # noqa: E402
from pagemark_core.text_layout import display_spans  # noqa: E402
from pagemark_app.rendering import TextRun, text_runs  # noqa: E402


def test_plain_line_is_one_draw_run_and_selection_and_styles_split_it():
    row = layout_paragraph("one two", 65).rows[0]
    assert text_runs(row, [0] * 7) == (TextRun("one two", 0, 0, False),)
    assert text_runs(row, [0, 0, 0, 0, 1, 1, 1], 1, 6) == (
        TextRun("o", 0, 0, False), TextRun("ne ", 1, 0, True),
        TextRun("tw", 4, 1, True), TextRun("o", 6, 1, False))


@pytest.mark.parametrize("text", [
    "ffi fi fl -- abc", "aé é字😀👩‍💻z", "- " + "one—two three " * 10,
    "  spaces  and  more   ", "", "a" * 130,
])
@pytest.mark.parametrize("batch", [False, True])
def test_runs_preserve_each_display_clusters_cell_style_and_source_selection(text, batch):
    flags = [index % 4 for index in range(len(text))]
    start, end = 2, max(2, len(text) - 3)
    for row in layout_paragraph(text, 65).rows:
        expected = []
        column = 0
        for begin, stop, cells in display_spans(row.text):
            source = row.sources[begin]
            expected.append((row.text[begin:stop], column,
                             flags[source] if source is not None else 0,
                             source is not None and start <= source < end))
            column += cells
        actual = []
        for run in text_runs(row, flags, start, end, batch_ascii=batch):
            column = run.column
            for begin, stop, cells in display_spans(run.text):
                actual.append((run.text[begin:stop], column, run.style, run.selected))
                column += cells
        assert actual == expected


def test_unicode_clusters_keep_explicit_positions_between_batched_ascii():
    row = layout_paragraph("abc é字 def", 65).rows[0]
    runs = text_runs(row, [0] * len(row.text))
    assert [(run.text, run.column) for run in runs] == [
        ("abc ", 0), ("é", 4), ("字", 5), (" def", 7)]

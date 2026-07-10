"""Regression tests for em-dash style alignment (BUG-15).

An em-dash is one content character but is displayed as two columns ("--"),
so per-column style data must duplicate its flag or every run to its right
is shifted left by one column per dash.
"""

from pagemark.model import TextModel
from pagemark.print_formatter import PrintFormatter
from pagemark.view import TerminalTextView, expand_styles_for_display


def test_expand_styles_for_display():
    #          a  —  b        display: a - - b
    assert expand_styles_for_display("a—b", [0, 2, 1]) == [0, 2, 2, 1]
    assert expand_styles_for_display("ab", [1, 0]) == [1, 0]
    assert expand_styles_for_display("——", [1, 3]) == [1, 1, 3, 3]


def test_view_styles_aligned_after_emdash():
    view = TerminalTextView()
    view.num_rows = 5
    view.num_columns = 20
    model = TextModel(view, paragraphs=["a—bold"])
    model.styles = [[0, 0, 1, 1, 1, 1]]  # "bold" is bold
    view.render()

    assert view.lines[0] == "a--bold"
    # Columns: a, -, -, b, o, l, d — "bold" occupies columns 3-6
    assert view.line_styles[0] == [0, 0, 0, 1, 1, 1, 1]


def test_view_styled_emdash_covers_both_columns():
    view = TerminalTextView()
    view.num_rows = 5
    view.num_columns = 20
    model = TextModel(view, paragraphs=["x—y"])
    model.styles = [[0, 1, 0]]  # the em-dash itself is bold
    view.render()

    assert view.lines[0] == "x--y"
    assert view.line_styles[0] == [0, 1, 1, 0]


def test_selection_highlight_aligned_after_emdash():
    """The selection highlight must use display columns, like the styles."""
    view = TerminalTextView()
    view.num_rows = 5
    view.num_columns = 20
    model = TextModel(view, paragraphs=["a—bold"])
    view.render()

    # Select "bold" (content chars 2-5)
    from pagemark.model import CursorPosition
    model.selection_start = CursorPosition(0, 2)
    model.selection_end = CursorPosition(0, 6)
    ranges = view.get_selection_ranges()

    # Display line is 'a--bold'; "bold" occupies columns 3-6
    assert ranges[0] == (3, 7)


def test_print_runs_aligned_after_emdash():
    styles = [[0, 0, 1, 1, 1, 1]]
    pf = PrintFormatter(["a—bold"], styles=styles)
    pf.format_pages()

    # First text line of the first page (after the 6-line top margin)
    runs = pf.page_runs[0][PrintFormatter.TOP_MARGIN]
    assert runs is not None and len(runs) == 1
    x, text, flags = runs[0]
    assert text == "bold"
    assert flags == 1
    # 'bold' starts at display column 3 ('a--'), plus the left margin
    assert x == pf.LEFT_MARGIN + 3

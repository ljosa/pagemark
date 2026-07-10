"""Regression tests for cursor movement across wrap boundaries (BUG-8/BUG-9).

A character index that exactly equals a visual line boundary
(cumulative_counts[i]) belongs to the START of the next line. Two families
of bugs followed from code that didn't respect this:

- BUG-8: moving up/down onto a shorter wrapped line clamped desired_x to a
  length that included the wrap separator space, landing the cursor exactly
  on the boundary — so Up got permanently stuck and Down skipped a line.
- BUG-9: render() treated a cursor at the boundary after the view's last
  line as "in view", drawing it on the wrong row and making the next Down
  press a no-op.
"""

from pagemark.model import TextModel
from pagemark.view import TerminalTextView, get_line_mapper


def make_view(paragraphs, num_rows=24, num_columns=20):
    view = TerminalTextView()
    view.num_rows = num_rows
    view.num_columns = num_columns
    model = TextModel(view, paragraphs=paragraphs)
    view.render()
    return view, model


def doc_line_of(view, model):
    """The visual document line the cursor is logically on."""
    pi = model.cursor_position.paragraph_index
    dl = sum(view._get_paragraph_line_count(i) for i in range(pi))
    mapper = get_line_mapper(model.paragraphs[pi], view.num_columns)
    return dl + mapper.line_for_char_index(model.cursor_position.character_index)


def total_doc_lines(view, model):
    return sum(view._get_paragraph_line_count(i) for i in range(len(model.paragraphs)))


def test_up_arrow_not_stuck_on_shorter_wrapped_line():
    """BUG-8: Up from a long line onto a shorter wrapped line must move up."""
    # visual lines: ['aaa bbb', 'cccccccccccccccccc', 'ddd']
    para = "aaa bbb cccccccccccccccccc ddd"
    view, model = make_view([para])
    mapper = get_line_mapper(para, view.num_columns)
    # Cursor at end of the long middle line; desired_x follows.
    model.cursor_position.character_index = mapper.line_end(1) - 1
    view.render()
    view.update_desired_x()

    view.move_cursor_up()
    assert doc_line_of(view, model) == 0

    # Repeated presses must not re-stick either.
    view.move_cursor_up()
    assert doc_line_of(view, model) == 0  # already at first line


def test_down_arrow_does_not_skip_a_line():
    """BUG-8: Down from a long line onto a shorter wrapped line moves 1 line."""
    # visual lines: ['cccccccccccccccccc', 'aaa bbb', 'ddddddddddddddddd e']
    para = "cccccccccccccccccc aaa bbb ddddddddddddddddd e"
    view, model = make_view([para])
    mapper = get_line_mapper(para, view.num_columns)
    model.cursor_position.character_index = mapper.line_end(0) - 1
    view.render()
    view.update_desired_x()

    view.move_cursor_down()
    assert doc_line_of(view, model) == 1

    view.move_cursor_down()
    assert doc_line_of(view, model) == 2


def test_down_and_up_visit_every_visual_line():
    """Down (Up) must advance exactly one visual line per press, for any
    desired_x, over documents with bullets, double spaces, and long words."""
    docs = [
        ["aaa bbb cccccccccccccccccc ddd eeeeeeeeeeeeeeeee f ghij"],
        [" - alpha beta gamma delta epsilon zeta eta theta", "", "tail"],
        ["one  two  three  four  five  six  seven  eight", "x" * 45, "end"],
    ]
    for paragraphs in docs:
        for desired_x in (0, 7, 19, 25):
            view, model = make_view(paragraphs)
            model.cursor_position.paragraph_index = 0
            model.cursor_position.character_index = 0
            view.render()
            view.desired_x = desired_x
            total = total_doc_lines(view, model)
            for expected in range(1, total):
                view.move_cursor_down()
                assert doc_line_of(view, model) == expected, (
                    f"Down stalled/skipped at line {expected} "
                    f"(desired_x={desired_x}, doc={paragraphs!r})")
            for expected in range(total - 2, -1, -1):
                view.move_cursor_up()
                assert doc_line_of(view, model) == expected, (
                    f"Up stalled/skipped at line {expected} "
                    f"(desired_x={desired_x}, doc={paragraphs!r})")


def test_right_across_boundary_at_view_bottom_then_down():
    """BUG-9: Right across a wrap boundary on the bottom screen row must show
    the cursor on the (newly scrolled-in) next line, and Down must work."""
    para = ("aaaa bbbb cccc dddd eeee ffff gggg hhhh iiii jjjj kkkk llll "
            "mmmm nnnn oooo pppp qqqq rrrr ssss tttt uuuu vvvv wwww xxxx")
    view, model = make_view([para, "another paragraph"], num_rows=4)
    mapper = get_line_mapper(para, view.num_columns)
    # Last character of the bottom row of the initial view (line 3 of 6).
    model.cursor_position.character_index = mapper.line_end(3) - 2
    view.render()
    view.update_desired_x()
    assert view.visual_cursor_y == 3

    model.right_char()
    view.update_desired_x()
    model.right_char()
    view.update_desired_x()

    # Cursor is now at the boundary index: logically on line 4. The view must
    # have recentered so that line is actually on screen, at column 0.
    assert doc_line_of(view, model) == 4
    assert view.visual_cursor_x == 0
    assert 0 <= view.visual_cursor_y < len(view.lines)
    assert view.lines[view.visual_cursor_y].startswith("qqqq")

    # The very next Down press must move down one line (this was a dead press).
    view.move_cursor_down()
    assert doc_line_of(view, model) == 5


def test_cursor_row_correct_when_view_top_is_on_page_boundary():
    """A page break belongs before every 54th document line, but the one
    preceding the view's own top line is never rendered; the cursor row must
    not be shifted down to account for it."""
    paragraphs = [f"para {i}" for i in range(60)]
    view, model = make_view(paragraphs, num_rows=6, num_columns=65)
    view.start_paragraph_index = 54  # view top exactly on the page boundary
    view.first_paragraph_line_offset = 0
    model.cursor_position.paragraph_index = 56
    model.cursor_position.character_index = 2
    view.render()
    assert view.lines[view.visual_cursor_y] == "para 56"

    view.move_cursor_down()
    assert model.cursor_position.paragraph_index == 57


def test_cursor_below_page_break_displaced_view_bottom():
    """A page-break row consumes view space; a cursor on the content line it
    displaced is below the view and must trigger recentering, after which
    Down advances normally."""
    word = "x" * 19
    para = " ".join([word] * 60)  # one visual line per word at width 20
    view, model = make_view([para], num_rows=4)
    mapper = get_line_mapper(para, view.num_columns)
    assert mapper.line_count == 60
    # View shows lines 51-53 plus the page break after line 53; line 54 is out.
    view.first_paragraph_line_offset = 51
    model.cursor_position.character_index = mapper.line_start(54) + 3
    view.render()
    view.update_desired_x()
    assert view.lines[view.visual_cursor_y] == word

    before = doc_line_of(view, model)
    assert before == 54
    view.move_cursor_down()
    assert doc_line_of(view, model) == 55


def test_cursor_at_boundary_on_first_view_line_stays_in_view():
    """A cursor exactly at the boundary that starts the first visible line is
    inside the view; render must not scroll away from it."""
    para = "aaaa bbbb cccc dddd eeee ffff gggg hhhh iiii jjjj kkkk llll"
    view, model = make_view([para], num_rows=2)
    mapper = get_line_mapper(para, view.num_columns)
    # Scroll so line 1 is the first visible line; cursor at its boundary index.
    view.first_paragraph_line_offset = 1
    model.cursor_position.character_index = mapper.line_start(1)
    view.render()
    assert view.first_paragraph_line_offset == 1
    assert view.visual_cursor_y == 0
    assert view.visual_cursor_x == 0

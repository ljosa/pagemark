"""Tests for hanging indents on bullet and numbered paragraphs."""

from pagemark.view import render_paragraph, TerminalTextView
from pagemark.model import TextModel, CursorPosition


def test_bullet_wrapping_applies_hanging_indent():
    text = "- This is a bullet item that will wrap across lines"
    lines, _ = render_paragraph(text, 20)
    assert len(lines) > 1
    # Wrapped lines should start with two spaces ("- ") as hanging indent
    for i in range(1, len(lines)):
        assert lines[i].startswith("  ")


def test_numbered_wrapping_applies_hanging_indent():
    text = "12. This numbered item will wrap across lines to the next"
    lines, _ = render_paragraph(text, 20)
    assert len(lines) > 1
    # Hanging indent equals length of "12. " which is 4 spaces
    for i in range(1, len(lines)):
        assert lines[i].startswith(" " * 4)


def test_multiple_spaces_after_marker_does_not_indent():
    text = "-  two spaces after bullet should not trigger hanging indent"
    lines, _ = render_paragraph(text, 20)
    assert len(lines) > 1
    # Wrapped lines should NOT start with two spaces solely due to hanging indent
    # The second line should begin with content text, not synthetic spaces
    assert not lines[1].startswith("  ")


def test_ctrl_a_visual_x_on_wrapped_bullet():
    view = TerminalTextView()
    view.num_columns = 20
    view.num_rows = 10

    paragraph = "- This bullet will definitely wrap to another line"
    model = TextModel(view, paragraphs=[paragraph])

    # Compute a position in the second visual line
    _, counts = render_paragraph(paragraph, view.num_columns)
    assert len(counts) > 1  # ensure wraps
    # Place cursor a few chars into the second visual line
    model.cursor_position = CursorPosition(0, counts[0] + 3)

    # Move to beginning of visual line (Ctrl-A)
    model.move_beginning_of_line()

    # Character index should jump to start of second visual line in model space
    assert model.cursor_position.character_index == counts[0]

    # Visual X should be the hanging indent width (2 for "- ")
    assert view.visual_cursor_x == 2


def test_move_cursor_to_visual_line_snaps_in_indent():
    view = TerminalTextView()
    view.num_columns = 20
    view.num_rows = 10

    paragraph = "- This bullet will definitely wrap to another line"
    model = TextModel(view, paragraphs=[paragraph])
    view.render()

    # Move caret to second visual line with desired_x inside the indent
    # visual_y = 1 should be second line; desired_x = 1 is inside the 2-space indent
    view._move_cursor_to_visual_line(1, 1)

    # Verify caret snapped to first text column after indent
    _, counts = render_paragraph(paragraph, view.num_columns)
    assert model.cursor_position.character_index == counts[0]
    assert view.visual_cursor_x == 2


def test_selection_ranges_account_for_hanging_indent():
    view = TerminalTextView()
    view.num_columns = 20
    view.num_rows = 10

    paragraph = "- This bullet will definitely wrap to another line"
    model = TextModel(view, paragraphs=[paragraph])
    view.render()

    # Compute counts to pick positions spanning into second line
    _, counts = render_paragraph(paragraph, view.num_columns)
    assert len(counts) > 1

    # Select from middle of first line to a few chars into second line
    start = CursorPosition(0, 5)
    end = CursorPosition(0, counts[0] + 4)
    model.selection_start = start
    model.selection_end = end

    ranges = view.get_selection_ranges()

    # First visible line selection starts at column 5
    assert ranges[0] is not None
    s0, e0 = ranges[0]
    assert s0 == 5
    assert e0 == len(view.lines[0])

    # Second visible line selection should include the two-space indent offset
    assert ranges[1] is not None
    s1, e1 = ranges[1]
    assert s1 == 2  # hanging indent width
    assert e1 == 2 + 4  # indent + 4 characters into the second line


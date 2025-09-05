"""Tests for preserving desired column on vertical navigation."""

from pagemark.model import TextModel, CursorPosition
from pagemark.view import TerminalTextView


def test_preserve_column_simple_up_down():
    view = TerminalTextView()
    view.num_columns = 20
    view.num_rows = 10

    # Two lines with different lengths when wrapped
    text = "Short line"  # length 10
    long_text = "This is a very long line that wraps"
    model = TextModel(view, paragraphs=[long_text, text, long_text])

    # Place cursor at character index 15 and set desired column accordingly
    model.cursor_position = CursorPosition(0, 15)
    view.render()
    desired = view.visual_cursor_x
    view.desired_x = desired

    # Move down into a short line; cursor clamps but desired column should be preserved
    view.move_cursor_down()
    clamped_x = view.visual_cursor_x
    assert clamped_x <= desired

    # Move back up; cursor should attempt to return to desired column
    view.move_cursor_up()
    assert view.visual_cursor_x == desired


def test_preserve_column_with_paging():
    view = TerminalTextView()
    view.num_columns = 20
    view.num_rows = 5  # small viewport to force paging

    para = "This is a very long line that will wrap across several visual lines in the viewport"
    model = TextModel(view, paragraphs=[para, para, para])
    view.render()

    # Move cursor somewhere mid-screen and record desired column
    model.cursor_position = CursorPosition(0, 15)
    view.render()
    desired = view.visual_cursor_x
    view.desired_x = desired

    # Page down and ensure the cursor on new top/bottom honors desired column visually (clamped)
    view.scroll_page_down()
    after_x = view.visual_cursor_x
    assert after_x <= desired

    # Page up and ensure we restore desired column on the entry line
    view.scroll_page_up()
    assert view.visual_cursor_x == desired

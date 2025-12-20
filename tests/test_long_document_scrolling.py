"""Test scrolling in long documents (20+ pages) to prevent recursion."""

import pytest
from pagemark.model import TextModel
from pagemark.view import TerminalTextView


def create_long_document_view(num_paragraphs: int = 1100, num_rows: int = 24, num_columns: int = 65, multiline: bool = False):
    """Create a view with a long document for testing."""
    view = TerminalTextView()
    view.num_rows = num_rows
    view.num_columns = num_columns
    view.start_paragraph_index = 0
    view.first_paragraph_line_offset = 0

    model = TextModel(view)
    if multiline:
        # Longer text that wraps to multiple lines - needed to trigger the bug
        long_text = 'This is a much longer line that will definitely wrap to multiple visual lines in the editor'
        model.paragraphs = [f'{i}: {long_text}' for i in range(num_paragraphs)]
    else:
        model.paragraphs = [f'This is line {i} of the document' for i in range(num_paragraphs)]
    model.styles = [[] for _ in range(num_paragraphs)]
    model.cursor_position.paragraph_index = 0
    model.cursor_position.character_index = 0

    view.render()
    return view, model


def test_page_down_then_up_no_recursion():
    """Test that PgDn followed by PgUp doesn't cause infinite recursion.

    This is a regression test for a bug where center_view_on_cursor() used
    the total page breaks from document start instead of page breaks within
    the view, causing the cursor to remain outside the view after centering.
    """
    view, model = create_long_document_view()

    # Scroll down 25 times (should be on page 10+)
    for _ in range(25):
        view.scroll_page_down()

    # This should not raise RecursionError
    for _ in range(5):
        view.scroll_page_up()

    # Verify we scrolled successfully
    assert view.start_paragraph_index < 540  # Should have moved up


def test_arrow_navigation_after_page_down():
    """Test that arrow key navigation works after scrolling down in long document."""
    view, model = create_long_document_view()

    # Scroll down
    for _ in range(25):
        view.scroll_page_down()

    initial_para = model.cursor_position.paragraph_index

    # Arrow up should not cause recursion
    for _ in range(50):
        view.move_cursor_up()

    assert model.cursor_position.paragraph_index < initial_para

    # Arrow down should also work
    for _ in range(25):
        view.move_cursor_down()

    assert model.cursor_position.paragraph_index > initial_para - 50


def test_render_recursion_guard():
    """Test that the recursion guard in render() prevents infinite loops."""
    view, model = create_long_document_view()

    # Move cursor to middle of document
    model.cursor_position.paragraph_index = 550
    model.cursor_position.character_index = 0
    view.start_paragraph_index = 0  # View is at start, cursor is far away

    # This render should center the view on cursor without infinite recursion
    view.render()

    # View should have moved to include cursor
    assert view.start_paragraph_index > 0


def test_long_document_page_break_centering():
    """Test that centering works correctly with many page breaks."""
    view, model = create_long_document_view()

    # Scroll to the end of document
    for _ in range(50):
        view.scroll_page_down()

    # Center on cursor explicitly
    view.center_view_on_cursor()
    view.render()

    # The cursor should be visible (within the rendered range)
    cursor_para = model.cursor_position.paragraph_index
    assert view.start_paragraph_index <= cursor_para


def test_multiline_paragraphs_deep_cursor_no_recursion():
    """Test render with multiline paragraphs and cursor deep in document.

    This is the key regression test. The bug occurred when:
    1. Paragraphs wrap to multiple lines
    2. Cursor is positioned deep in document (high page_breaks_before)
    3. half_rows becomes very negative: (num_rows - page_breaks_before) // 2
    4. This causes first_paragraph_line_offset to be set incorrectly
    5. Cursor ends up outside the view after centering
    6. render() calls center_view_on_cursor() and render() recursively forever
    """
    view, model = create_long_document_view(num_paragraphs=1500, multiline=True)

    # Position cursor deep in document where page_breaks_before > num_rows
    model.cursor_position.paragraph_index = 1400
    model.cursor_position.character_index = 0
    view.start_paragraph_index = 0  # View at start, cursor far away

    # This should NOT raise RecursionError
    view.render()

    # Verify cursor is now visible
    assert view.start_paragraph_index <= model.cursor_position.paragraph_index

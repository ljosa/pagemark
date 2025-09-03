import pytest
from pagemark import TextModel, TerminalTextView


def test_render_two_paragraphs_overflow():
    """Test rendering two paragraphs that exceed view rows."""
    v = TerminalTextView()
    v.num_rows = 5  # Small view height
    v.num_columns = 30

    # Two paragraphs that will need more than 5 lines total
    para1 = "This is the first paragraph that will wrap into multiple lines due to width"
    para2 = "This is the second paragraph that also wraps into multiple lines"
    m = TextModel(v, paragraphs=[para1, para2])

    v.render()

    # Should fill exactly the number of rows available
    assert len(v.lines) == v.num_rows

    # All lines should respect column width
    for line in v.lines:
        assert len(line) <= v.num_columns

    # First line should be from first paragraph
    assert v.lines[0].startswith("This is the first")

    # Cursor at beginning of first paragraph
    assert m.cursor_position.paragraph_index == 0
    assert m.cursor_position.character_index == 0
    assert v.visual_cursor_x == 0
    assert v.visual_cursor_y == 0

    # View should start at first paragraph
    assert v.start_paragraph_index == 0
    # View should end at or after second paragraph (since we have 2 paragraphs)
    assert v.end_paragraph_index == 2


def test_render_many_short_paragraphs_overflow():
    """Test rendering many single-line paragraphs exceeding view rows."""
    v = TerminalTextView()
    v.num_rows = 4
    v.num_columns = 40

    # Create 10 short paragraphs (each fits on one line)
    paragraphs = [f"Paragraph {i+1}" for i in range(10)]
    m = TextModel(v, paragraphs=paragraphs)

    v.render()

    # Should show exactly 4 lines (the view height)
    assert len(v.lines) == v.num_rows

    # Should show first 4 paragraphs
    assert v.lines[0] == "Paragraph 1"
    assert v.lines[1] == "Paragraph 2"
    assert v.lines[2] == "Paragraph 3"
    assert v.lines[3] == "Paragraph 4"

    # Cursor at beginning
    assert m.cursor_position.paragraph_index == 0
    assert m.cursor_position.character_index == 0

    # View boundaries
    assert v.start_paragraph_index == 0
    assert v.end_paragraph_index == 4  # Paragraphs 0-3 are shown


def test_render_long_first_paragraph_overflow():
    """Test when first paragraph alone exceeds view rows."""
    v = TerminalTextView()
    v.num_rows = 3
    v.num_columns = 20

    # First paragraph needs more than 3 lines
    para1 = "This is a very long first paragraph that will definitely need more than three lines to display completely"
    para2 = "Second paragraph that won't be visible"
    m = TextModel(v, paragraphs=[para1, para2])

    v.render()

    # Should fill all available rows with first paragraph
    assert len(v.lines) == v.num_rows

    # All lines should be from the first paragraph (no room for second)
    for line in v.lines:
        assert len(line) <= v.num_columns

    # View should only show first paragraph
    assert v.start_paragraph_index == 0
    assert v.end_paragraph_index == 1  # Only first paragraph visible

    # Cursor position
    assert m.cursor_position.paragraph_index == 0
    assert m.cursor_position.character_index == 0
    assert v.visual_cursor_x == 0
    assert v.visual_cursor_y == 0


def test_render_mixed_paragraph_lengths_overflow():
    """Test rendering mix of short and long paragraphs exceeding view."""
    v = TerminalTextView()
    v.num_rows = 6
    v.num_columns = 25

    # Mix of paragraph lengths
    para1 = "Short first"
    para2 = "This is a much longer second paragraph that will wrap across multiple lines"
    para3 = "Short third"
    para4 = "Another long paragraph here that wraps"
    m = TextModel(v, paragraphs=[para1, para2, para3, para4])

    v.render()

    # Should use all available rows
    assert len(v.lines) == v.num_rows

    # First line should be the short first paragraph
    assert v.lines[0] == "Short first"

    # All lines respect column limit
    for line in v.lines:
        assert len(line) <= v.num_columns

    # Cursor at start
    assert m.cursor_position.paragraph_index == 0
    assert m.cursor_position.character_index == 0

    # View starts at beginning
    assert v.start_paragraph_index == 0
    # End depends on how much fits, but should be at least 2
    assert v.end_paragraph_index >= 2

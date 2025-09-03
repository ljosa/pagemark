import pytest
from pagemark import TextModel, TerminalView


def test_render_two_line_paragraph():
    """Test rendering a paragraph that wraps to exactly two lines."""
    v = TerminalView()
    v.num_rows = 10
    v.num_columns = 35  # Width adjusted to get exactly 2 lines
    
    # Text that should wrap to two lines with 35 columns
    text = "This is a paragraph that will wrap nicely into exactly two lines"
    m = TextModel(v, paragraphs=[text])
    
    v.render()
    
    # Should render to exactly 2 lines with the given column width
    assert len(v.lines) == 2
    
    # First line should start with "This"
    assert v.lines[0].startswith("This")
    
    # Check line lengths don't exceed column limit
    assert len(v.lines[0]) <= v.num_columns
    assert len(v.lines[1]) <= v.num_columns
    
    # Cursor at beginning
    assert m.cursor_position.paragraph_index == 0
    assert m.cursor_position.character_index == 0
    assert v.visual_cursor_x == 0
    assert v.visual_cursor_y == 0
    
    # View boundaries
    assert v.start_paragraph_index == 0
    assert v.end_paragraph_index == 1


def test_render_paragraph_with_mid_word_break():
    """Test rendering when a word must be broken mid-word."""
    v = TerminalView()
    v.num_rows = 10
    v.num_columns = 15  # Very narrow
    
    # Has a very long word that must be broken
    text = "This has a verylongwordthatmustbebroken here"
    m = TextModel(v, paragraphs=[text])
    
    v.render()
    
    # Should have multiple lines due to word breaking
    assert len(v.lines) >= 3
    
    # Check all lines respect column limit
    for line in v.lines:
        assert len(line) <= v.num_columns
    
    # First line should be "This has a"
    assert v.lines[0] == "This has a"
    
    # Second line should be part of the long word
    assert v.lines[1] == "verylongwordtha"
    
    # Cursor position checks
    assert m.cursor_position.paragraph_index == 0
    assert m.cursor_position.character_index == 0
    assert v.visual_cursor_x == 0
    assert v.visual_cursor_y == 0


def test_render_paragraph_exact_width():
    """Test rendering when text exactly fits the column width."""
    v = TerminalView()
    v.num_rows = 10
    v.num_columns = 10
    
    # Each word is exactly 10 characters
    text = "1234567890 abcdefghij"
    m = TextModel(v, paragraphs=[text])
    
    v.render()
    
    # Should be on two lines - each word on its own line
    assert len(v.lines) == 2
    assert v.lines[0] == "1234567890"
    assert v.lines[1] == "abcdefghij"
    
    # Cursor checks
    assert m.cursor_position.paragraph_index == 0
    assert m.cursor_position.character_index == 0
    assert v.visual_cursor_x == 0
    assert v.visual_cursor_y == 0


def test_render_two_line_with_trailing_spaces():
    """Test rendering handles trailing spaces correctly."""
    v = TerminalView()
    v.num_rows = 10
    v.num_columns = 20
    
    # Text with multiple spaces between words
    text = "First    line   and   second    line"
    m = TextModel(v, paragraphs=[text])
    
    v.render()
    
    # Should wrap into at least 2 lines
    assert len(v.lines) >= 2
    
    # All lines should respect column width
    for line in v.lines:
        assert len(line) <= v.num_columns
    
    # Cursor at start
    assert m.cursor_position.paragraph_index == 0
    assert m.cursor_position.character_index == 0
    assert v.visual_cursor_x == 0
    assert v.visual_cursor_y == 0
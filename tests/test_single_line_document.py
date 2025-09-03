import pytest
from pagemark import TextModel, TerminalView


def test_render_single_line_document():
    """Test rendering a document with a single line of text."""
    v = TerminalView()
    v.num_rows = 10
    v.num_columns = 80
    
    text = "This is a single line of text in the document."
    m = TextModel(v, paragraphs=[text])
    
    v.render()
    
    # Verify the document renders correctly
    assert len(v.lines) == 1
    assert v.lines[0] == text
    
    # Cursor should be at the beginning of the document
    assert m.cursor_position.paragraph_index == 0
    assert m.cursor_position.character_index == 0
    assert v.visual_cursor_x == 0
    assert v.visual_cursor_y == 0
    
    # View boundaries
    assert v.start_paragraph_index == 0
    assert v.end_paragraph_index == 1


def test_render_single_line_document_with_word_wrap():
    """Test rendering a single line that needs word wrapping."""
    v = TerminalView()
    v.num_rows = 10
    v.num_columns = 20  # Small width to force wrapping
    
    text = "This is a longer line that will need to be wrapped across multiple lines"
    m = TextModel(v, paragraphs=[text])
    
    v.render()
    
    # Verify word wrapping occurred
    assert len(v.lines) > 1
    assert len(v.lines) <= v.num_rows
    
    # Check that no line exceeds the column limit
    for line in v.lines:
        assert len(line) <= v.num_columns
    
    # First line should start with "This"
    assert v.lines[0].startswith("This")
    
    # Cursor position
    assert m.cursor_position.paragraph_index == 0
    assert m.cursor_position.character_index == 0
    assert v.visual_cursor_x == 0
    assert v.visual_cursor_y == 0
    
    # View boundaries
    assert v.start_paragraph_index == 0
    assert v.end_paragraph_index == 1


def test_render_single_line_very_long_word():
    """Test rendering a single line with a word longer than column width."""
    v = TerminalView()
    v.num_rows = 5
    v.num_columns = 10
    
    # Word longer than column width should be broken
    text = "supercalifragilisticexpialidocious"
    m = TextModel(v, paragraphs=[text])
    
    v.render()
    
    # Word should be broken across multiple lines
    assert len(v.lines) > 1
    
    # Each line should be exactly 10 chars (except possibly the last)
    for i, line in enumerate(v.lines[:-1]):
        assert len(line) == v.num_columns
    
    # Last line should have the remainder
    assert len(v.lines[-1]) <= v.num_columns
    
    # Reconstructing should give us the original (up to what fits in view)
    reconstructed = "".join(v.lines)
    assert text.startswith(reconstructed)
    
    # Cursor position
    assert m.cursor_position.paragraph_index == 0
    assert m.cursor_position.character_index == 0
    assert v.visual_cursor_x == 0
    assert v.visual_cursor_y == 0
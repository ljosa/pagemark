from pagemark import TextModel, TerminalTextView


def test_up_arrow_maintains_desired_x():
    """Test that up arrow maintains desired X position across lines."""
    v = TerminalTextView()
    v.num_rows = 20
    v.num_columns = 65
    
    # Create lines with different lengths
    paragraphs = [
        "This is a long line with many characters that we can navigate",
        "Short line",
        "Another long line with many characters for testing navigation"
    ]
    m = TextModel(v, paragraphs=paragraphs)
    
    # Position cursor at column 50 on the third line
    m.cursor_position.paragraph_index = 2
    m.cursor_position.character_index = 50
    
    v.render()
    v.update_desired_x()  # Set desired X to 50
    
    # Move up to the short line
    v.move_cursor_up()
    
    # Cursor should be at end of short line (column 10)
    assert m.cursor_position.paragraph_index == 1
    assert m.cursor_position.character_index == 10  # Length of "Short line"
    
    # Move up again to the first line
    v.move_cursor_up()
    
    # Cursor should return to column 50
    assert m.cursor_position.paragraph_index == 0
    assert m.cursor_position.character_index == 50


def test_down_arrow_maintains_desired_x():
    """Test that down arrow maintains desired X position across lines."""
    v = TerminalTextView()
    v.num_rows = 20
    v.num_columns = 65
    
    # Create lines with different lengths
    paragraphs = [
        "This is a long line with many characters that we can navigate",
        "Short line",
        "Another long line with many characters for testing navigation"
    ]
    m = TextModel(v, paragraphs=paragraphs)
    
    # Position cursor at column 50 on the first line
    m.cursor_position.paragraph_index = 0
    m.cursor_position.character_index = 50
    
    v.render()
    v.update_desired_x()  # Set desired X to 50
    
    # Move down to the short line
    v.move_cursor_down()
    
    # Cursor should be at end of short line (column 10)
    assert m.cursor_position.paragraph_index == 1
    assert m.cursor_position.character_index == 10  # Length of "Short line"
    
    # Move down again to the third line
    v.move_cursor_down()
    
    # Cursor should return to column 50
    assert m.cursor_position.paragraph_index == 2
    assert m.cursor_position.character_index == 50


def test_arrow_navigation_with_word_wrap():
    """Test up/down navigation with word-wrapped lines."""
    v = TerminalTextView()
    v.num_rows = 20
    v.num_columns = 20  # Narrow to force word wrap
    
    # Create a long paragraph that will wrap
    paragraphs = [
        "This is a very long paragraph that will definitely wrap across multiple visual lines when displayed"
    ]
    m = TextModel(v, paragraphs=paragraphs)
    
    # Position cursor on the second visual line
    m.cursor_position.paragraph_index = 0
    m.cursor_position.character_index = 25  # Somewhere in the middle
    
    v.render()
    initial_y = v.visual_cursor_y
    
    # Move up to the first visual line
    v.move_cursor_up()
    assert v.visual_cursor_y < initial_y
    assert m.cursor_position.paragraph_index == 0  # Still in same paragraph
    
    # Move back down
    v.move_cursor_down()
    assert v.visual_cursor_y == initial_y


def test_arrow_navigation_skips_page_breaks():
    """Test that up/down arrows skip over page break lines."""
    v = TerminalTextView()
    v.num_rows = 60
    v.num_columns = 65
    
    # Create enough lines to trigger a page break after line 54
    paragraphs = [f"Line {i}" for i in range(1, 56)]
    m = TextModel(v, paragraphs=paragraphs)
    
    # Position cursor on line 55 (after the page break)
    m.cursor_position.paragraph_index = 54
    m.cursor_position.character_index = 0
    
    v.render()
    
    # Move up - should skip the page break and go to line 54
    v.move_cursor_up()
    assert m.cursor_position.paragraph_index == 53  # Line 54 (0-indexed)
    
    # Move down - should skip the page break and go back to line 55
    v.move_cursor_down()
    assert m.cursor_position.paragraph_index == 54  # Line 55 (0-indexed)


def test_up_arrow_at_document_start():
    """Test that up arrow does nothing at document start."""
    v = TerminalTextView()
    v.num_rows = 10
    v.num_columns = 65
    
    paragraphs = ["First line", "Second line"]
    m = TextModel(v, paragraphs=paragraphs)
    
    # Position cursor at start of document
    m.cursor_position.paragraph_index = 0
    m.cursor_position.character_index = 0
    
    v.render()
    
    # Try to move up - should do nothing
    v.move_cursor_up()
    assert m.cursor_position.paragraph_index == 0
    assert m.cursor_position.character_index == 0


def test_down_arrow_at_document_end():
    """Test that down arrow does nothing at document end."""
    v = TerminalTextView()
    v.num_rows = 10
    v.num_columns = 65
    
    paragraphs = ["First line", "Second line"]
    m = TextModel(v, paragraphs=paragraphs)
    
    # Position cursor at end of document
    m.cursor_position.paragraph_index = 1
    m.cursor_position.character_index = len("Second line")
    
    v.render()
    
    # Try to move down - should do nothing
    v.move_cursor_down()
    assert m.cursor_position.paragraph_index == 1
    assert m.cursor_position.character_index == len("Second line")


def test_arrow_navigation_with_empty_lines():
    """Test up/down navigation with empty lines."""
    v = TerminalTextView()
    v.num_rows = 20
    v.num_columns = 65
    
    paragraphs = [
        "First line",
        "",  # Empty line
        "Third line"
    ]
    m = TextModel(v, paragraphs=paragraphs)
    
    # Position cursor on third line
    m.cursor_position.paragraph_index = 2
    m.cursor_position.character_index = 5
    
    v.render()
    v.update_desired_x()  # Set desired X to 5
    
    # Move up to empty line
    v.move_cursor_up()
    assert m.cursor_position.paragraph_index == 1
    assert m.cursor_position.character_index == 0  # Empty line
    
    # Move up to first line
    v.move_cursor_up()
    assert m.cursor_position.paragraph_index == 0
    assert m.cursor_position.character_index == 5  # Maintains desired X
    
    # Move back down through empty line
    v.move_cursor_down()
    assert m.cursor_position.paragraph_index == 1
    assert m.cursor_position.character_index == 0
    
    v.move_cursor_down()
    assert m.cursor_position.paragraph_index == 2
    assert m.cursor_position.character_index == 5  # Back to desired X


def test_horizontal_movement_resets_desired_x():
    """Test that horizontal movement resets the desired X position."""
    v = TerminalTextView()
    v.num_rows = 20
    v.num_columns = 65
    
    paragraphs = [
        "This is a long line with many characters",
        "Short",
        "Another long line with many characters"
    ]
    m = TextModel(v, paragraphs=paragraphs)
    
    # Start at column 30 on first line
    m.cursor_position.paragraph_index = 0
    m.cursor_position.character_index = 30
    
    v.render()
    v.update_desired_x()
    assert v.desired_x == 30
    
    # Move left - should reset desired X
    m.cursor_position.character_index = 29
    v.render()
    v.update_desired_x()
    assert v.desired_x == 29
    
    # Move right - should reset desired X
    m.cursor_position.character_index = 31
    v.render() 
    v.update_desired_x()
    assert v.desired_x == 31
from pagemark import TextModel, TerminalTextView


def test_down_arrow_centers_on_scroll():
    """Test that down arrow centers cursor when scrolling out of view."""
    v = TerminalTextView()
    v.num_rows = 5  # Small view to test scrolling
    v.num_columns = 65
    
    # Create more lines than can fit in view
    paragraphs = [f"Line {i}" for i in range(1, 11)]  # 10 lines
    m = TextModel(v, paragraphs=paragraphs)
    
    # Start at top of document
    m.cursor_position.paragraph_index = 0
    m.cursor_position.character_index = 0
    
    v.render()
    
    # Move down to last visible line (line 5, index 4)
    for _ in range(4):
        v.move_cursor_down()
    
    # Check we're at line 5
    assert m.cursor_position.paragraph_index == 4
    
    # Move down once more - should center view on cursor
    v.move_cursor_down()
    
    # Cursor should be at line 6 (index 5)
    assert m.cursor_position.paragraph_index == 5
    
    # Visual cursor should be centered (middle of 5-line view is line 3, index 2)
    assert v.visual_cursor_y == 2
    
    # View should be centered on line 6
    assert v.lines[2] == "Line 6"  # Cursor line in middle


def test_up_arrow_centers_on_scroll():
    """Test that up arrow centers cursor when scrolling out of view."""
    v = TerminalTextView()
    v.num_rows = 5  # Small view to test scrolling
    v.num_columns = 65
    
    # Create more lines than can fit in view
    paragraphs = [f"Line {i}" for i in range(1, 11)]  # 10 lines
    m = TextModel(v, paragraphs=paragraphs)
    
    # Start at line 6
    m.cursor_position.paragraph_index = 5
    m.cursor_position.character_index = 0
    
    v.render()
    
    # View should show lines 4-8 (cursor is on line 6, centered)
    # Move up to first visible line
    while v.visual_cursor_y > 0:
        v.move_cursor_up()
    
    # Now move up once more - should center view
    v.move_cursor_up()
    
    # Visual cursor should be centered (middle of view)
    assert v.visual_cursor_y == 2
    
    # Check cursor moved up correctly
    assert m.cursor_position.paragraph_index == 2


def test_continuous_down_scrolling():
    """Test scrolling down centers when going out of view."""
    v = TerminalTextView()
    v.num_rows = 5
    v.num_columns = 65
    
    # Create 20 lines
    paragraphs = [f"Line {i}" for i in range(1, 21)]
    m = TextModel(v, paragraphs=paragraphs)
    
    # Start at top
    m.cursor_position.paragraph_index = 0
    m.cursor_position.character_index = 0
    
    v.render()
    
    # Move down to bottom of view
    for _ in range(4):
        v.move_cursor_down()
    assert v.visual_cursor_y == 4  # At bottom
    
    # Move down once more - should center
    v.move_cursor_down()
    assert v.visual_cursor_y == 2  # Centered
    assert m.cursor_position.paragraph_index == 5
    
    # Continue moving down within view
    for _ in range(2):
        v.move_cursor_down()
    assert v.visual_cursor_y == 4  # At bottom again
    
    # Move down once more - should center again
    v.move_cursor_down()
    assert v.visual_cursor_y == 2  # Centered again
    assert m.cursor_position.paragraph_index == 8


def test_continuous_up_scrolling():
    """Test scrolling up centers when going out of view."""
    v = TerminalTextView()
    v.num_rows = 5
    v.num_columns = 65
    
    # Create 20 lines
    paragraphs = [f"Line {i}" for i in range(1, 21)]
    m = TextModel(v, paragraphs=paragraphs)
    
    # Start at line 15
    m.cursor_position.paragraph_index = 14
    m.cursor_position.character_index = 0
    
    v.render()
    
    # Move cursor to top of current view
    while v.visual_cursor_y > 0:
        v.move_cursor_up()
    assert v.visual_cursor_y == 0  # At top
    
    # Move up once more - should center
    v.move_cursor_up()
    assert v.visual_cursor_y == 2  # Centered
    
    # Continue moving up within view
    for _ in range(2):
        v.move_cursor_up()
    assert v.visual_cursor_y == 0  # At top again
    
    # Move up once more - should center again
    v.move_cursor_up()
    assert v.visual_cursor_y == 2  # Centered again


def test_scrolling_with_page_breaks():
    """Test scrolling behavior with page breaks."""
    v = TerminalTextView()
    v.num_rows = 10  # Small view
    v.num_columns = 65
    
    # Create 56 lines (will have page break after line 54)
    paragraphs = [f"Line {i}" for i in range(1, 57)]
    m = TextModel(v, paragraphs=paragraphs)
    
    # Start at line 52
    m.cursor_position.paragraph_index = 51
    m.cursor_position.character_index = 0
    
    v.render()
    
    # Move down a few times to cross the page break
    for _ in range(4):
        v.move_cursor_down()
    
    # Should be at line 56 (index 55), skipping the page break
    # Note: started at line 52 (index 51), moved down 4 times
    assert m.cursor_position.paragraph_index == 55
    
    # There should be a page break in the visible lines
    page_break_found = False
    for line in v.lines:
        if "Page 2" in line:
            page_break_found = True
            break
    assert page_break_found, "Page break should be visible"
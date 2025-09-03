from pagemark import TextModel, TerminalTextView


def test_page_break_at_54_lines():
    """Test that a page break line appears every 54 lines."""
    v = TerminalTextView()
    v.num_rows = 60  # Enough to show a page break
    v.num_columns = 65
    
    # Create 55 lines of text (should have a page break after line 54)
    paragraphs = ["Line " + str(i) for i in range(1, 56)]
    m = TextModel(v, paragraphs=paragraphs)
    
    v.render()
    
    # Check that line 54 (index 53) is followed by a page break
    # The page break should be at index 54 in the lines list
    assert len(v.lines) > 55  # Should have at least 55 lines plus page break
    assert v.lines[54] == "─" * 65  # Page break line
    assert v.lines[53] == "Line 54"  # Line before page break
    assert v.lines[55] == "Line 55"  # Line after page break


def test_page_break_visual_separation():
    """Test that page breaks are horizontal lines."""
    v = TerminalTextView()
    v.num_rows = 60
    v.num_columns = 65
    
    # Create exactly 54 lines
    paragraphs = ["Line " + str(i) for i in range(1, 55)]
    m = TextModel(v, paragraphs=paragraphs)
    
    v.render()
    
    # The 55th visual line (index 54) should be a page break
    assert v.lines[54] == "─" * 65


def test_cursor_skips_page_break():
    """Test that cursor positioning accounts for page break lines."""
    v = TerminalTextView()
    v.num_rows = 60
    v.num_columns = 65
    
    # Create 55 lines and position cursor on line 55
    paragraphs = ["Line " + str(i) for i in range(1, 56)]
    m = TextModel(v, paragraphs=paragraphs)
    
    # Move cursor to line 55 (after the page break)
    m.cursor_position.paragraph_index = 54  # 55th paragraph (0-indexed)
    m.cursor_position.character_index = 0
    
    v.render()
    
    # Visual cursor should be on line 56 (index 55) because of the page break
    # Line 54 is at index 53, page break at index 54, line 55 at index 55
    assert v.visual_cursor_y == 55  # Cursor on line after page break


def test_multiple_page_breaks():
    """Test that multiple page breaks appear at correct intervals."""
    v = TerminalTextView()
    v.num_rows = 120  # Enough to show multiple page breaks
    v.num_columns = 65
    
    # Create 110 lines (should have page breaks after lines 54 and 108)
    paragraphs = ["Line " + str(i) for i in range(1, 111)]
    m = TextModel(v, paragraphs=paragraphs)
    
    v.render()
    
    # First page break after line 54 (index 53)
    assert v.lines[54] == "─" * 65
    
    # Second page break after line 108 (but accounting for first page break)
    # Line 108 would be at index 108 + 1 (for first page break) = 109
    assert v.lines[109] == "─" * 65


def test_page_break_with_scrolling():
    """Test that page breaks work correctly when view is scrolled."""
    v = TerminalTextView()
    v.num_rows = 30  # Smaller view
    v.num_columns = 65
    
    # Create 100 lines
    paragraphs = ["Line " + str(i) for i in range(1, 101)]
    m = TextModel(v, paragraphs=paragraphs)
    
    # Move cursor to line 60 to scroll the view
    m.cursor_position.paragraph_index = 59
    m.cursor_position.character_index = 0
    
    v.render()
    
    # The view should show the page break that occurs after line 54
    # but the exact position depends on centering logic
    page_break_found = False
    for line in v.lines:
        if line == "─" * 65:
            page_break_found = True
            break
    
    # We should see at least one page break in the view
    assert page_break_found, "Page break should be visible in scrolled view"


def test_no_page_break_at_line_zero():
    """Test that no page break appears before the first line."""
    v = TerminalTextView()
    v.num_rows = 10
    v.num_columns = 65
    
    paragraphs = ["First line", "Second line"]
    m = TextModel(v, paragraphs=paragraphs)
    
    v.render()
    
    # First line should not be a page break
    assert v.lines[0] != "─" * 65
    assert v.lines[0] == "First line"
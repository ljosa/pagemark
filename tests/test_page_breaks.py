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
    assert "Page 2" in v.lines[54]  # Page break line with page number
    assert "─" in v.lines[54]  # Should have horizontal lines
    assert v.lines[53] == "Line 54"  # Line before page break
    assert v.lines[55] == "Line 55"  # Line after page break


def test_page_break_visual_separation():
    """Test that page breaks show page numbers with horizontal lines."""
    v = TerminalTextView()
    v.num_rows = 60
    v.num_columns = 65
    
    # Create 55 lines to trigger page break after line 54
    paragraphs = ["Line " + str(i) for i in range(1, 56)]
    m = TextModel(v, paragraphs=paragraphs)
    
    v.render()
    
    # The 55th visual line (index 54) should be a page break with "Page 2"
    assert "Page 2" in v.lines[54]
    assert "─" in v.lines[54]
    # Check it's centered
    assert v.lines[54].index("Page 2") > 20  # Should be roughly centered


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
    assert "Page 2" in v.lines[54]
    assert "─" in v.lines[54]
    
    # Second page break after line 108 (but accounting for first page break)
    # Line 108 would be at index 108 + 1 (for first page break) = 109
    assert "Page 3" in v.lines[109]
    assert "─" in v.lines[109]


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
    page_number = None
    for line in v.lines:
        if "─" in line and "Page" in line:
            page_break_found = True
            # Extract page number
            if "Page 2" in line:
                page_number = 2
            elif "Page 3" in line:
                page_number = 3
            break
    
    # We should see at least one page break in the view
    assert page_break_found, "Page break should be visible in scrolled view"
    assert page_number in [2, 3], f"Expected Page 2 or 3, got {page_number}"


def test_page_number_centering():
    """Test that page numbers are properly centered in the page break line."""
    v = TerminalTextView()
    v.num_rows = 60
    v.num_columns = 65
    
    # Create exactly 54 lines to get a page break
    paragraphs = ["Line " + str(i) for i in range(1, 56)]
    m = TextModel(v, paragraphs=paragraphs)
    
    v.render()
    
    # Get the page break line
    page_break_line = v.lines[54]
    
    # Check that it contains Page 2
    assert "Page 2" in page_break_line
    
    # Check centering - "Page 2" should be roughly in the middle
    page_text = " Page 2 "
    start_pos = page_break_line.index(page_text)
    # With 65 columns and " Page 2 " being 8 chars, it should start around position 28-29
    assert 27 <= start_pos <= 30, f"Page text not centered, starts at position {start_pos}"
    
    # Check that the rest is filled with dashes
    before_text = page_break_line[:start_pos]
    after_text = page_break_line[start_pos + len(page_text):]
    assert all(c == "─" for c in before_text), "Before text should be all dashes"
    assert all(c == "─" for c in after_text), "After text should be all dashes"


def test_no_page_break_at_line_zero():
    """Test that no page break appears before the first line."""
    v = TerminalTextView()
    v.num_rows = 10
    v.num_columns = 65
    
    paragraphs = ["First line", "Second line"]
    m = TextModel(v, paragraphs=paragraphs)
    
    v.render()
    
    # First line should not be a page break
    assert "Page" not in v.lines[0]
    assert v.lines[0] == "First line"
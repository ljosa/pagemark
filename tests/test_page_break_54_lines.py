from pagemark import TextModel, TerminalTextView


def test_no_page_break_after_exactly_54_lines():
    """Test that no page break appears after exactly 54 lines."""
    v = TerminalTextView()
    v.num_rows = 60  # Enough to show all lines plus potential page break
    v.num_columns = 65
    
    # Create exactly 54 lines
    paragraphs = [f"Line {i}" for i in range(1, 55)]  # Lines 1-54
    m = TextModel(v, paragraphs=paragraphs)
    
    v.render()
    
    # Should have exactly 54 lines, no page break
    assert len(v.lines) == 54, f"Expected 54 lines, got {len(v.lines)}"
    
    # Last line should be "Line 54", not a page break
    assert v.lines[-1] == "Line 54"
    
    # No line should contain "Page 2"
    for line in v.lines:
        assert "Page 2" not in line, f"Found unexpected page break: {line}"


def test_page_break_after_55_lines():
    """Test that page break DOES appear after 55 lines (on page 2)."""
    v = TerminalTextView()
    v.num_rows = 60  # Enough to show all lines plus page break
    v.num_columns = 65
    
    # Create 55 lines
    paragraphs = [f"Line {i}" for i in range(1, 56)]  # Lines 1-55
    m = TextModel(v, paragraphs=paragraphs)
    
    v.render()
    
    # Should have 56 lines (55 content + 1 page break)
    assert len(v.lines) == 56, f"Expected 56 lines, got {len(v.lines)}"
    
    # Line at index 54 should be the page break
    assert "Page 2" in v.lines[54]
    assert "─" in v.lines[54]
    
    # Line 55 should be after the page break
    assert v.lines[55] == "Line 55"


def test_no_page_break_for_short_document():
    """Test that no page break appears for documents shorter than 54 lines."""
    v = TerminalTextView()
    v.num_rows = 60
    v.num_columns = 65
    
    # Create 30 lines (well under 54)
    paragraphs = [f"Line {i}" for i in range(1, 31)]
    m = TextModel(v, paragraphs=paragraphs)
    
    v.render()
    
    # Should have exactly 30 lines, no page break
    assert len(v.lines) == 30
    
    # No line should contain "Page"
    for line in v.lines:
        assert "Page" not in line


def test_page_break_at_108_lines():
    """Test that page breaks appear at lines 54 and 108."""
    v = TerminalTextView()
    v.num_rows = 115  # Enough to show 108 lines plus 2 page breaks
    v.num_columns = 65
    
    # Create exactly 108 lines
    paragraphs = [f"Line {i}" for i in range(1, 109)]  # Lines 1-108
    m = TextModel(v, paragraphs=paragraphs)
    
    v.render()
    
    # Should have 109 lines (108 content + 1 page break after line 54)
    # No page break after 108 since that would start page 3
    assert len(v.lines) == 109, f"Expected 109 lines, got {len(v.lines)}"
    
    # Page break after line 54
    assert "Page 2" in v.lines[54]
    
    # No page break after line 108 (would be at index 109 but we only have 109 total)
    assert v.lines[-1] == "Line 108"  # Last line should be content, not page break
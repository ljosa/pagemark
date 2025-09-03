"""Tests for the print formatter."""

from pagemark.print_formatter import PrintFormatter


def test_single_page_document():
    """Test formatting a document that fits on a single page."""
    paragraphs = ["This is a short document.", "It has two paragraphs."]
    formatter = PrintFormatter(paragraphs)
    pages = formatter.format_pages()
    
    assert len(pages) == 1
    # Check page dimensions
    assert len(pages[0]) == 66  # Full page height
    assert all(len(line) == 85 for line in pages[0])  # Full page width
    
    # Check text content appears in the right place (line 6, with left margin)
    assert pages[0][6].strip() == "This is a short document."
    assert pages[0][7].strip() == "It has two paragraphs."
    
    # First page should not have a page number on line 4 (index 3)
    assert pages[0][3].strip() == ""  # Should be blank


def test_multi_page_document():
    """Test formatting a document that spans multiple pages."""
    # Create enough content for multiple pages
    paragraphs = ["Line " + str(i) for i in range(60)]  # More than 54 lines
    formatter = PrintFormatter(paragraphs)
    pages = formatter.format_pages()
    
    assert len(pages) == 2
    # Both pages should be full size
    assert len(pages[0]) == 66
    assert len(pages[1]) == 66
    
    # First page should not have a page number on line 4
    assert pages[0][3].strip() == ""
    
    # Second page should have page number "2" on line 4 (index 3)
    assert "2" in pages[1][3]
    # Check it's centered
    page_num_line = pages[1][3]
    stripped = page_num_line.strip()
    assert stripped == "2"
    # Should be roughly centered
    left_spaces = len(page_num_line) - len(page_num_line.lstrip())
    right_spaces = len(page_num_line.rstrip()) - len(page_num_line.strip())
    assert abs(left_spaces - right_spaces) <= 1  # Allow for odd-width centering


def test_word_wrapping():
    """Test that long lines are properly wrapped at 65 characters."""
    long_line = "This is a very long line that definitely exceeds the 65 character limit and should be wrapped to the next line appropriately"
    paragraphs = [long_line]
    formatter = PrintFormatter(paragraphs)
    pages = formatter.format_pages()
    
    assert len(pages) == 1
    assert len(pages[0]) == 66  # Full page
    
    # Check that text is wrapped (should appear on multiple lines)
    # Text starts at line 6
    text_line_1 = pages[0][6].strip()
    text_line_2 = pages[0][7].strip()
    assert text_line_1 != ""  # First part of text
    assert text_line_2 != ""  # Wrapped part
    
    # Check that text content doesn't exceed 65 characters
    for i in range(6, 60):  # Text area
        content = pages[0][i][10:75]  # Extract text area (columns 11-75)
        assert len(content) == 65


def test_exact_page_boundary():
    """Test document that ends exactly at a page boundary."""
    # Create exactly 54 lines
    paragraphs = ["Line " + str(i) for i in range(54)]
    formatter = PrintFormatter(paragraphs)
    pages = formatter.format_pages()
    
    assert len(pages) == 1
    assert len(pages[0]) == 66  # Full page with margins


def test_page_numbering_position():
    """Test that page numbers appear in the correct position."""
    # Create content for 3 pages
    paragraphs = ["Line " + str(i) for i in range(150)]
    formatter = PrintFormatter(paragraphs)
    pages = formatter.format_pages()
    
    assert len(pages) == 3
    
    # Page 1: no page number on line 4 (index 3)
    assert pages[0][3].strip() == ""
    
    # Page 2: page number "2" on line 4
    assert "2" in pages[1][3]
    assert pages[1][3].strip() == "2"
    
    # Page 3: page number "3" on line 4
    assert "3" in pages[2][3]
    assert pages[2][3].strip() == "3"


def test_empty_document():
    """Test handling of empty document."""
    formatter = PrintFormatter([])
    pages = formatter.format_pages()
    
    # Empty document should produce no pages
    assert len(pages) == 0


def test_single_empty_paragraph():
    """Test handling of a single empty paragraph."""
    formatter = PrintFormatter([""])
    pages = formatter.format_pages()
    
    assert len(pages) == 1
    assert len(pages[0]) == 66
    # Text area should have an empty line
    assert pages[0][6].strip() == ""


def test_format_for_print():
    """Test formatting pages for print output with form feeds."""
    paragraphs = ["Page 1 content"] + [""] * 53 + ["Page 2 content"]
    formatter = PrintFormatter(paragraphs)
    formatter.format_pages()
    
    output = formatter.format_for_print()
    
    # Should contain a form feed character between pages
    assert "\f" in output
    # Should have exactly one form feed (between 2 pages)
    assert output.count("\f") == 1
    # Form feed should come after 66 lines (full page)
    lines = output.split("\n")
    form_feed_index = next(i for i, line in enumerate(lines) if "\f" in line)
    assert form_feed_index == 66


def test_get_page():
    """Test retrieving individual pages."""
    paragraphs = ["Line " + str(i) for i in range(60)]
    formatter = PrintFormatter(paragraphs)
    formatter.format_pages()
    
    # Get first page
    page1 = formatter.get_page(0)
    assert len(page1) == 66
    assert "Line 0" in page1[6]  # First text line at line 6
    
    # Get second page
    page2 = formatter.get_page(1)
    assert len(page2) == 66
    assert "2" in page2[3]  # Has page number at line 4
    
    # Get non-existent page
    page3 = formatter.get_page(2)
    assert page3 == []


def test_get_page_count():
    """Test getting the total page count."""
    # Single page
    formatter1 = PrintFormatter(["Short text"])
    formatter1.format_pages()
    assert formatter1.get_page_count() == 1
    
    # Multiple pages
    formatter2 = PrintFormatter(["Line " + str(i) for i in range(100)])
    formatter2.format_pages()
    assert formatter2.get_page_count() == 2
    
    # Empty document
    formatter3 = PrintFormatter([])
    formatter3.format_pages()
    assert formatter3.get_page_count() == 0
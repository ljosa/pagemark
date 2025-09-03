"""Tests for the print preview generator."""

from pagemark.print_preview import PrintPreview
from pagemark.print_formatter import PrintFormatter


def test_preview_dimensions():
    """Test that preview has correct dimensions."""
    # Create a simple page
    formatter = PrintFormatter(["Test text"])
    pages = formatter.format_pages()
    
    preview = PrintPreview(pages)
    preview_lines = preview.generate_preview(0)
    
    # Should be 33 lines tall (66/2)
    assert len(preview_lines) == 33
    
    # Each line should be 43 characters wide (86/2, rounding up from 85)
    for line in preview_lines:
        assert len(line) == 43


def test_empty_page_preview():
    """Test preview of an empty page."""
    # Create empty page (85x66 of spaces)
    page = [" " * 85 for _ in range(66)]
    
    preview = PrintPreview([page])
    preview_lines = preview.generate_preview(0)
    
    # All should be empty (spaces)
    for line in preview_lines:
        assert all(c == " " for c in line)


def test_full_page_preview():
    """Test preview of a page full of text."""
    # Create page full of X's (but only 85 wide, so last column will be half)
    page = ["X" * 85 for _ in range(66)]
    
    preview = PrintPreview([page])
    preview_lines = preview.generate_preview(0)
    
    # All except the last column should be full blocks
    # Last column will be left-half blocks (▌) since column 86 is empty
    for line in preview_lines:
        # First 42 columns should be full blocks
        assert all(c == "█" for c in line[:42])
        # Last column should be left-half block (columns 84-85 filled, 86 empty)
        assert line[42] == "▌"


def test_quadrant_mapping():
    """Test that quadrant blocks are correctly mapped."""
    preview = PrintPreview([])
    
    # Test all patterns
    assert preview._chars_to_quadrant(" ", " ", " ", " ") == " "
    assert preview._chars_to_quadrant("A", " ", " ", " ") == "▘"
    assert preview._chars_to_quadrant(" ", "A", " ", " ") == "▝"
    assert preview._chars_to_quadrant(" ", " ", "A", " ") == "▖"
    assert preview._chars_to_quadrant(" ", " ", " ", "A") == "▗"
    assert preview._chars_to_quadrant("A", "A", " ", " ") == "▀"
    assert preview._chars_to_quadrant(" ", " ", "A", "A") == "▄"
    assert preview._chars_to_quadrant("A", " ", "A", " ") == "▌"
    assert preview._chars_to_quadrant(" ", "A", " ", "A") == "▐"
    assert preview._chars_to_quadrant("A", "A", "A", "A") == "█"


def test_text_area_visibility():
    """Test that text in the text area is visible in preview."""
    # Create a document with text
    formatter = PrintFormatter(["This is test text that should appear in the preview."])
    pages = formatter.format_pages()
    
    preview = PrintPreview(pages)
    preview_lines = preview.generate_preview(0)
    
    # Text starts at line 6 (row 3 in preview)
    # and column 10 (column 5 in preview)
    # So the text area in preview is roughly rows 3-29, columns 5-37
    
    # Check that there's content in the text area
    has_content = False
    for row in range(3, 30):
        for col in range(5, 38):
            if row < len(preview_lines) and col < len(preview_lines[row]):
                if preview_lines[row][col] != " ":
                    has_content = True
                    break
    
    assert has_content


def test_page_number_visibility():
    """Test that page numbers are visible in preview."""
    # Create a multi-page document
    long_text = ["Line " + str(i) for i in range(100)]
    formatter = PrintFormatter(long_text)
    pages = formatter.format_pages()
    
    preview = PrintPreview(pages)
    
    # Check page 2 (which should have page number)
    preview_lines = preview.generate_preview(1)
    
    # Page number is on line 4 (row 2 in preview), centered
    # Should see some non-space characters around the center
    page_num_row = preview_lines[1]  # Line 4 maps to preview row 2 (lines 2-3)
    center_area = page_num_row[20:23]  # Center area of the line
    
    # Should have some content (the page number)
    assert any(c != " " for c in center_area)


def test_margin_areas():
    """Test that margin areas are mostly empty."""
    # Create a page with text only in the text area
    formatter = PrintFormatter(["Test content in the text area."])
    pages = formatter.format_pages()
    
    preview = PrintPreview(pages)
    preview_lines = preview.generate_preview(0)
    
    # Top margin (rows 0-2) should be mostly empty
    for row in range(3):
        line = preview_lines[row]
        # Most of the line should be spaces
        non_spaces = sum(1 for c in line if c != " ")
        assert non_spaces < len(line) // 4  # Less than 25% non-space
    
    # Bottom margin (rows 30-32) should be mostly empty
    for row in range(30, 33):
        line = preview_lines[row]
        non_spaces = sum(1 for c in line if c != " ")
        assert non_spaces < len(line) // 4
    
    # Left margin (columns 0-4) should be mostly empty
    for row in range(len(preview_lines)):
        for col in range(5):
            assert preview_lines[row][col] == " " or preview_lines[row][col] in "▗▖"  # Allow bottom-right/left quarters
    
    # Right margin (columns 38-42) should be mostly empty
    for row in range(len(preview_lines)):
        for col in range(38, 43):
            if col < len(preview_lines[row]):
                assert preview_lines[row][col] == " " or preview_lines[row][col] in "▘▝"  # Allow top-left/right quarters


def test_preview_with_border():
    """Test preview with border generation."""
    formatter = PrintFormatter(["Test text"])
    pages = formatter.format_pages()
    
    preview = PrintPreview(pages)
    bordered = preview.generate_preview_with_border(0)
    
    # Should have border lines
    assert len(bordered) == 35  # 33 + 2 border lines
    assert bordered[0].startswith("┌")
    assert bordered[0].endswith("┐")
    assert bordered[-1].startswith("└")
    assert bordered[-1].endswith("┘")
    
    # Content lines should be bordered
    for i in range(1, len(bordered) - 1):
        assert bordered[i].startswith("│")
        assert bordered[i].endswith("│")


def test_out_of_bounds_page():
    """Test requesting preview of non-existent page."""
    formatter = PrintFormatter(["Test"])
    pages = formatter.format_pages()
    
    preview = PrintPreview(pages)
    # Try to get page 5 when only 1 exists
    preview_lines = preview.generate_preview(5)
    
    assert preview_lines == []
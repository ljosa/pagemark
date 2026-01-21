"""Test that bold and underline styles are rendered correctly in bulleted lists."""

import pytest
from pagemark.model import TextModel, CursorPosition, StyleFlags
from pagemark.view import TerminalTextView, render_paragraph


def test_bold_in_wrapped_bullet_line():
    """Test that bold styles appear at correct positions in wrapped bullet lines.
    
    The bug: When a bullet point wraps to a second line, and bold is applied to 
    text on the wrapped line, the bold appears a few characters too early (shifted 
    left by the hanging indent width).
    """
    # Create a bullet point that will wrap
    text = "- This is a bullet item that will wrap across multiple lines to demonstrate the issue"
    
    view = TerminalTextView()
    view.num_rows = 10
    view.num_columns = 40  # Force wrapping
    model = TextModel(view, paragraphs=[text])
    
    # Render the paragraph to see how it wraps
    para_lines, para_counts = render_paragraph(text, view.num_columns)
    
    # Verify it wraps to multiple lines
    assert len(para_lines) > 1, "Bullet should wrap to multiple lines"
    
    # Apply bold to characters on the second wrapped line
    # The second line starts at para_counts[0]
    second_line_start = para_counts[0]
    bold_start = second_line_start + 5  # Bold starts 5 chars into second line
    bold_end = second_line_start + 15   # Bold ends 15 chars into second line
    
    # Apply bold to model.styles
    model._sync_styles_length()
    for i in range(bold_start, bold_end):
        model.styles[0][i] |= StyleFlags.BOLD
    
    # Set cursor position within the rendered view
    model.cursor_position = CursorPosition(0, bold_start)
    
    # Render the view
    view.render()
    
    # The second visual line should have bold starting at position 7
    # (2 spaces for hanging indent "- " + 5 characters into the line)
    # not at position 5 (which would be the bug)
    assert len(view.line_styles) >= 2, "Should have at least 2 visual lines"
    
    second_line_styles = view.line_styles[1]
    
    # Check that position 5 is NOT bold (this would indicate the bug)
    assert not (second_line_styles[5] & StyleFlags.BOLD), \
        "Position 5 should NOT be bold (hanging indent width is 2)"
    
    # Check that position 7 IS bold (5 + 2 for hanging indent)
    assert second_line_styles[7] & StyleFlags.BOLD, \
        "Position 7 should be bold (5 chars into line + 2 for hanging indent)"
    
    # Check that the bold extends correctly
    for i in range(7, min(17, len(second_line_styles))):  # 7 to 17 (15 + 2 indent)
        assert second_line_styles[i] & StyleFlags.BOLD, \
            f"Position {i} should be bold"


def test_underline_in_wrapped_numbered_list():
    """Test that underline styles appear at correct positions in wrapped numbered lists."""
    # Create a numbered list that will wrap
    text = "1. This is a numbered item that will wrap across multiple lines to demonstrate"
    
    view = TerminalTextView()
    view.num_rows = 10
    view.num_columns = 40  # Force wrapping
    model = TextModel(view, paragraphs=[text])
    
    # Render the paragraph to see how it wraps
    para_lines, para_counts = render_paragraph(text, view.num_columns)
    
    # Verify it wraps to multiple lines
    assert len(para_lines) > 1, "Numbered item should wrap to multiple lines"
    
    # Apply underline to characters on the second wrapped line
    second_line_start = para_counts[0]
    underline_start = second_line_start + 3
    underline_end = second_line_start + 10
    
    # Apply underline to model.styles
    model._sync_styles_length()
    for i in range(underline_start, underline_end):
        model.styles[0][i] |= StyleFlags.UNDERLINE
    
    # Set cursor position within the rendered view
    model.cursor_position = CursorPosition(0, underline_start)
    
    # Render the view
    view.render()
    
    # The numbered list "1. " has hanging indent of 3
    # So the second visual line should have underline starting at position 6
    # (3 spaces for hanging indent + 3 characters into the line)
    assert len(view.line_styles) >= 2, "Should have at least 2 visual lines"
    
    second_line_styles = view.line_styles[1]
    
    # Check that position 3 is NOT underlined (this would indicate the bug)
    assert not (second_line_styles[3] & StyleFlags.UNDERLINE), \
        "Position 3 should NOT be underlined (hanging indent width is 3)"
    
    # Check that position 6 IS underlined (3 + 3 for hanging indent)
    assert second_line_styles[6] & StyleFlags.UNDERLINE, \
        "Position 6 should be underlined (3 chars into line + 3 for hanging indent)"


def test_bold_on_first_line_of_bullet():
    """Test that bold on the first line of a bullet (no hanging indent) works correctly."""
    text = "- This is a bullet with bold on first line only"
    
    view = TerminalTextView()
    view.num_rows = 10
    view.num_columns = 40
    model = TextModel(view, paragraphs=[text])
    
    # Apply bold to characters on the first line
    bold_start = 5  # After "- Th"
    bold_end = 15
    
    model._sync_styles_length()
    for i in range(bold_start, bold_end):
        model.styles[0][i] |= StyleFlags.BOLD
    
    model.cursor_position = CursorPosition(0, bold_start)
    view.render()
    
    # First line should have bold at the exact positions (no offset needed)
    first_line_styles = view.line_styles[0]
    
    assert first_line_styles[5] & StyleFlags.BOLD, "Position 5 should be bold"
    assert first_line_styles[14] & StyleFlags.BOLD, "Position 14 should be bold"
    assert not (first_line_styles[15] & StyleFlags.BOLD), "Position 15 should NOT be bold"

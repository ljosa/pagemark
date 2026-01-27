"""Test em-dash rendering and cursor handling."""

import pytest
from pagemark.model import TextModel, CursorPosition
from pagemark.view import render_paragraph, get_line_mapper
from pagemark.print_formatter import PrintFormatter
from unittest.mock import Mock


def create_test_model(paragraphs):
    """Create a test model with given paragraphs."""
    view = Mock()
    view.render = Mock()
    return TextModel(view, paragraphs=paragraphs)


def test_render_paragraph_with_emdash():
    """Test that em-dash is rendered as double hyphen in terminal."""
    paragraph = "This is an em—dash test"
    lines, counts = render_paragraph(paragraph, 65)
    
    # The visual line should have -- instead of —
    assert lines[0] == "This is an em--dash test"
    # The character count should still be based on original text
    assert counts[0] == len(paragraph)


def test_render_paragraph_multiple_emdashes():
    """Test rendering with multiple em-dashes."""
    paragraph = "First—second—third em—dashes"
    lines, counts = render_paragraph(paragraph, 65)
    
    # All em-dashes should be replaced with --
    assert lines[0] == "First--second--third em--dashes"
    # Character count based on original
    assert counts[0] == len(paragraph)


def test_emdash_cursor_position():
    """Test cursor positioning with em-dashes."""
    paragraph = "Before—after"
    mapper = get_line_mapper(paragraph, 65)
    
    # Cursor before em-dash (at position 6, which is the —)
    # Visual column should account for em-dash being 2 chars wide
    # Position 0-5: "Before" = 6 visual cols
    # Position 6: "—" starts here
    visual_col = mapper.visual_column(6)
    assert visual_col == 6
    
    # Cursor after em-dash (at position 7)
    # "Before" (6) + "—" displayed as "--" (2) = 8 visual cols
    visual_col = mapper.visual_column(7)
    assert visual_col == 8


def test_emdash_cursor_movement_right():
    """Test that cursor movement treats em-dash as single character."""
    model = create_test_model(["Test—text"])
    model.cursor_position = CursorPosition(0, 4)  # Before em-dash
    
    # Move right should go over the em-dash in one step
    model.right_char()
    assert model.cursor_position.character_index == 5  # After em-dash
    
    
def test_emdash_cursor_movement_left():
    """Test that cursor movement left treats em-dash as single character."""
    model = create_test_model(["Test—text"])
    model.cursor_position = CursorPosition(0, 5)  # After em-dash
    
    # Move left should go over the em-dash in one step
    model.left_char()
    assert model.cursor_position.character_index == 4  # Before em-dash


def test_emdash_deletion():
    """Test that deleting an em-dash removes it as a single unit."""
    model = create_test_model(["Test—text"])
    model.cursor_position = CursorPosition(0, 4)  # Before em-dash
    
    # Delete should remove the em-dash
    model.delete_char()
    assert model.paragraphs[0] == "Testtext"
    assert model.cursor_position.character_index == 4


def test_emdash_backspace():
    """Test that backspace over em-dash removes it as a single unit."""
    model = create_test_model(["Test—text"])
    model.cursor_position = CursorPosition(0, 5)  # After em-dash
    
    # Backspace should remove the em-dash
    model.backspace()
    assert model.paragraphs[0] == "Testtext"
    assert model.cursor_position.character_index == 4


def test_emdash_at_line_wrap():
    """Test em-dash behavior when it causes line wrap."""
    # Create a paragraph where em-dash is near the wrap point
    # With 20 columns, this should wrap
    paragraph = "Short line with—em"
    lines, counts = render_paragraph(paragraph, 20)
    
    # Check that em-dash is rendered as -- in output
    full_text = ''.join(lines)
    assert '—' not in full_text
    assert '--' in full_text


def test_multiple_emdashes_visual_column():
    """Test visual column calculation with multiple em-dashes."""
    paragraph = "A—B—C—D"
    mapper = get_line_mapper(paragraph, 65)
    
    # Position 0: 'A' -> visual col 0
    assert mapper.visual_column(0) == 0
    
    # Position 1: first '—' -> visual col 1
    assert mapper.visual_column(1) == 1
    
    # Position 2: 'B' -> visual col 3 (A + -- from first em-dash)
    assert mapper.visual_column(2) == 3
    
    # Position 3: second '—' -> visual col 4 (A + -- + B)
    assert mapper.visual_column(3) == 4
    
    # Position 4: 'C' -> visual col 6 (A + -- + B + --)
    assert mapper.visual_column(4) == 6


def test_emdash_content_column_from_visual():
    """Test reverse mapping from visual column to content column."""
    paragraph = "Test—word"
    mapper = get_line_mapper(paragraph, 65)
    
    # Visual column 0-3: "Test" -> content 0-3
    assert mapper.content_column_from_visual(0, 0) == 0
    assert mapper.content_column_from_visual(0, 3) == 3
    
    # Visual column 4: first hyphen of em-dash -> content 4
    assert mapper.content_column_from_visual(0, 4) == 4
    
    # Visual column 5: second hyphen of em-dash -> still content 4 (within em-dash)
    assert mapper.content_column_from_visual(0, 5) == 5
    
    # Visual column 6: 'w' of "word" -> content 5
    assert mapper.content_column_from_visual(0, 6) == 5


def test_emdash_with_hanging_indent():
    """Test em-dash rendering with hanging indent (bullets)."""
    paragraph = "- Item with—emdash text"
    lines, counts = render_paragraph(paragraph, 65)
    
    # First line should have em-dash as --
    assert '--' in lines[0]
    assert '—' not in lines[0]


def test_emdash_insertion():
    """Test that inserting an em-dash works correctly."""
    model = create_test_model(["Before after"])
    # Set up mock view properties needed by insert_text
    model.view.start_paragraph_index = 0
    model.view.end_paragraph_index = 1
    model.cursor_position = CursorPosition(0, 7)  # After "Before "
    
    # Insert an em-dash
    model.insert_text("—")
    assert model.paragraphs[0] == "Before —after"
    assert model.cursor_position.character_index == 8


def test_empty_paragraph_with_emdash():
    """Test edge case of paragraph containing only em-dash."""
    paragraph = "—"
    lines, counts = render_paragraph(paragraph, 65)
    
    assert lines[0] == "--"
    assert counts[0] == 1  # Still just 1 character in model


def test_emdash_at_paragraph_start():
    """Test em-dash at the beginning of a paragraph."""
    paragraph = "—Start with emdash"
    lines, counts = render_paragraph(paragraph, 65)
    
    assert lines[0] == "--Start with emdash"


def test_emdash_at_paragraph_end():
    """Test em-dash at the end of a paragraph."""
    paragraph = "End with emdash—"
    lines, counts = render_paragraph(paragraph, 65)
    
    assert lines[0] == "End with emdash--"


def test_emdash_in_print_formatter():
    """Test that em-dashes are rendered as -- in print output."""
    paragraphs = ["This has an em—dash in it"]
    formatter = PrintFormatter(paragraphs)
    pages = formatter.format_pages()
    
    # Get the text content from the first page
    page_text = ''.join(pages[0])
    
    # Em-dash should be rendered as -- in print output
    assert '--' in page_text
    assert '—' not in page_text


def test_emdash_in_print_formatter_multiple():
    """Test multiple em-dashes in print formatter."""
    paragraphs = ["First—second—third paragraph with—em-dashes"]
    formatter = PrintFormatter(paragraphs)
    pages = formatter.format_pages()
    
    # Get the text content from the first page
    page_text = ''.join(pages[0])
    
    # All em-dashes should be rendered as -- in print output
    assert page_text.count('--') >= 3
    assert '—' not in page_text


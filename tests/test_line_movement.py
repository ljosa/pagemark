"""Test line movement (Ctrl-A/E) functionality."""

import pytest
from pagemark.model import TextModel, CursorPosition
from unittest.mock import Mock


def create_test_model(paragraphs):
    """Create a test model with given paragraphs."""
    view = Mock()
    view.render = Mock()
    view.num_columns = 65  # Default editor width
    return TextModel(view, paragraphs=paragraphs)


def test_move_beginning_of_line_basic():
    """Test basic move to beginning of line."""
    model = create_test_model(["hello world"])
    model.cursor_position = CursorPosition(0, 5)  # Middle of line
    
    model.move_beginning_of_line()
    assert model.cursor_position.character_index == 0
    assert model.cursor_position.paragraph_index == 0


def test_move_beginning_of_line_already_at_start():
    """Test move when already at beginning."""
    model = create_test_model(["hello world"])
    model.cursor_position = CursorPosition(0, 0)  # Already at start
    
    model.move_beginning_of_line()
    assert model.cursor_position.character_index == 0


def test_move_end_of_line_basic():
    """Test basic move to end of line."""
    model = create_test_model(["hello world"])
    model.cursor_position = CursorPosition(0, 5)  # Middle of line
    
    model.move_end_of_line()
    assert model.cursor_position.character_index == 11  # Length of "hello world"
    assert model.cursor_position.paragraph_index == 0


def test_move_end_of_line_already_at_end():
    """Test move when already at end."""
    model = create_test_model(["hello world"])
    model.cursor_position = CursorPosition(0, 11)  # Already at end
    
    model.move_end_of_line()
    assert model.cursor_position.character_index == 11


def test_move_beginning_of_line_empty_paragraph():
    """Test move in empty paragraph."""
    model = create_test_model([""])
    model.cursor_position = CursorPosition(0, 0)
    
    model.move_beginning_of_line()
    assert model.cursor_position.character_index == 0


def test_move_end_of_line_empty_paragraph():
    """Test move in empty paragraph."""
    model = create_test_model([""])
    model.cursor_position = CursorPosition(0, 0)
    
    model.move_end_of_line()
    assert model.cursor_position.character_index == 0


def test_line_movement_multiple_paragraphs():
    """Test line movement respects paragraph boundaries."""
    model = create_test_model(["first paragraph", "second paragraph", "third"])
    
    # Test beginning of middle paragraph
    model.cursor_position = CursorPosition(1, 7)  # Middle of "second"
    model.move_beginning_of_line()
    assert model.cursor_position.paragraph_index == 1
    assert model.cursor_position.character_index == 0
    
    # Test end of same paragraph
    model.move_end_of_line()
    assert model.cursor_position.paragraph_index == 1
    assert model.cursor_position.character_index == 16  # Length of "second paragraph"


def test_line_movement_with_long_line():
    """Test line movement with long text that wraps."""
    long_text = "a" * 100
    model = create_test_model([long_text])
    model.cursor_position = CursorPosition(0, 50)  # Middle of first visual line
    
    # Move to end of visual line (should be at position 64, not 65 or 100)
    # Position 64 is the last 'a' on the first visual line
    # Position 65 would be the first 'a' of the second visual line
    model.move_end_of_line()
    assert model.cursor_position.character_index == 64  # Last char of first visual line
    
    # Move to beginning of visual line
    model.move_beginning_of_line()
    assert model.cursor_position.character_index == 0
    
    # Test on second visual line (past the boundary)
    model.cursor_position = CursorPosition(0, 66)  # Definitely on second visual line
    
    # Move to end of second visual line first
    model.move_end_of_line()
    assert model.cursor_position.character_index == 100  # End of paragraph
    
    # Move to beginning of second visual line
    model.move_beginning_of_line()
    assert model.cursor_position.character_index == 65  # Start of second visual line
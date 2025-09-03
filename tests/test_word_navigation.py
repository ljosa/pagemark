"""Test word navigation (Alt-left/right) functionality."""

import pytest
from pagemark.model import TextModel, CursorPosition
from unittest.mock import Mock


def create_test_model(paragraphs):
    """Create a test model with given paragraphs."""
    view = Mock()
    view.render = Mock()
    return TextModel(view, paragraphs=paragraphs)


def test_right_word_basic():
    """Test basic forward word movement."""
    model = create_test_model(["hello world test"])
    model.cursor_position = CursorPosition(0, 0)
    
    # Move to "world"
    model.right_word()
    assert model.cursor_position.character_index == 6
    
    # Move to "test"
    model.right_word()
    assert model.cursor_position.character_index == 12
    
    # At end of line
    model.right_word()
    assert model.cursor_position.character_index == 16


def test_right_word_multiple_spaces():
    """Test forward word movement with multiple spaces."""
    model = create_test_model(["hello    world"])
    model.cursor_position = CursorPosition(0, 0)
    
    model.right_word()
    assert model.cursor_position.character_index == 9  # Start of "world"


def test_right_word_across_paragraphs():
    """Test forward word movement across paragraph boundaries."""
    model = create_test_model(["first paragraph", "second paragraph"])
    model.cursor_position = CursorPosition(0, 5)  # End of "first"
    
    model.right_word()
    assert model.cursor_position.character_index == 6  # Start of "paragraph"
    assert model.cursor_position.paragraph_index == 0
    
    model.right_word()  
    # Should move to next paragraph since we're at the end
    assert model.cursor_position.paragraph_index == 1
    assert model.cursor_position.character_index == 0  # Start of next para


def test_left_word_basic():
    """Test basic backward word movement."""
    model = create_test_model(["hello world test"])
    model.cursor_position = CursorPosition(0, 16)  # End of line
    
    # Move to "test"
    model.left_word()
    assert model.cursor_position.character_index == 12
    
    # Move to "world"
    model.left_word()
    assert model.cursor_position.character_index == 6
    
    # Move to "hello"
    model.left_word()
    assert model.cursor_position.character_index == 0


def test_left_word_multiple_spaces():
    """Test backward word movement with multiple spaces."""
    model = create_test_model(["hello    world"])
    model.cursor_position = CursorPosition(0, 14)  # End of "world"
    
    model.left_word()
    assert model.cursor_position.character_index == 9  # Start of "world"
    
    model.left_word()
    assert model.cursor_position.character_index == 0  # Start of "hello"


def test_left_word_across_paragraphs():
    """Test backward word movement across paragraph boundaries."""
    model = create_test_model(["first paragraph", "second paragraph"])
    model.cursor_position = CursorPosition(1, 0)  # Start of second para
    
    model.left_word()
    assert model.cursor_position.paragraph_index == 0
    assert model.cursor_position.character_index == 15  # End of first para


def test_word_navigation_empty_paragraph():
    """Test word navigation with empty paragraphs."""
    model = create_test_model(["first", "", "third"])
    
    # Forward from first to third
    model.cursor_position = CursorPosition(0, 5)
    model.right_word()
    assert model.cursor_position.paragraph_index == 1
    assert model.cursor_position.character_index == 0
    
    model.right_word()
    assert model.cursor_position.paragraph_index == 2
    assert model.cursor_position.character_index == 0
    
    # Backward from third to first
    model.left_word()
    assert model.cursor_position.paragraph_index == 1
    assert model.cursor_position.character_index == 0
    
    model.left_word()
    assert model.cursor_position.paragraph_index == 0
    assert model.cursor_position.character_index == 5


def test_word_navigation_punctuation():
    """Test word navigation stops at word boundaries, not punctuation."""
    model = create_test_model(["hello, world! test."])
    model.cursor_position = CursorPosition(0, 0)
    
    # Should skip punctuation attached to words
    model.right_word()
    assert model.cursor_position.character_index == 7  # Start of "world"
    
    model.right_word()
    assert model.cursor_position.character_index == 14  # Start of "test"
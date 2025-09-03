"""Test delete-char (Ctrl-D) functionality."""

import pytest
from pagemark.model import TextModel, CursorPosition
from unittest.mock import Mock


def create_test_model(paragraphs):
    """Create a test model with given paragraphs."""
    view = Mock()
    view.render = Mock()
    return TextModel(view, paragraphs=paragraphs)


def test_delete_char_basic():
    """Test basic character deletion."""
    model = create_test_model(["hello world"])
    model.cursor_position = CursorPosition(0, 5)  # At space between words
    
    model.delete_char()
    assert model.paragraphs[0] == "helloworld"
    assert model.cursor_position.character_index == 5  # Cursor doesn't move


def test_delete_char_at_line_end():
    """Test delete at end of line joins with next paragraph."""
    model = create_test_model(["first", "second"])
    model.cursor_position = CursorPosition(0, 5)  # End of "first"
    
    model.delete_char()
    assert len(model.paragraphs) == 1
    assert model.paragraphs[0] == "firstsecond"
    assert model.cursor_position.paragraph_index == 0
    assert model.cursor_position.character_index == 5  # Cursor doesn't move


def test_delete_char_at_document_end():
    """Test delete at end of document does nothing."""
    model = create_test_model(["hello"])
    model.cursor_position = CursorPosition(0, 5)  # End of document
    
    model.delete_char()
    assert model.paragraphs[0] == "hello"  # No change
    assert model.cursor_position.character_index == 5


def test_delete_char_empty_paragraph():
    """Test delete with empty paragraph."""
    model = create_test_model(["first", "", "third"])
    model.cursor_position = CursorPosition(1, 0)  # In empty paragraph
    
    model.delete_char()
    assert len(model.paragraphs) == 2
    assert model.paragraphs == ["first", "third"]
    assert model.cursor_position.paragraph_index == 1
    assert model.cursor_position.character_index == 0


def test_delete_char_beginning_of_line():
    """Test delete at beginning of line."""
    model = create_test_model(["hello world"])
    model.cursor_position = CursorPosition(0, 0)
    
    model.delete_char()
    assert model.paragraphs[0] == "ello world"
    assert model.cursor_position.character_index == 0


def test_delete_char_middle_of_word():
    """Test delete in middle of word."""
    model = create_test_model(["hello world"])
    model.cursor_position = CursorPosition(0, 3)  # At second 'l' in "hello"
    
    model.delete_char()
    assert model.paragraphs[0] == "helo world"
    assert model.cursor_position.character_index == 3


def test_delete_char_with_spaces():
    """Test delete with multiple spaces."""
    model = create_test_model(["hello    world"])
    model.cursor_position = CursorPosition(0, 5)  # At first space
    
    model.delete_char()
    assert model.paragraphs[0] == "hello   world"  # One space deleted
    assert model.cursor_position.character_index == 5


def test_delete_char_multiple_paragraphs():
    """Test delete across multiple paragraphs."""
    model = create_test_model(["first", "second", "third"])
    model.cursor_position = CursorPosition(1, 6)  # End of "second"
    
    model.delete_char()
    assert len(model.paragraphs) == 2
    assert model.paragraphs == ["first", "secondthird"]
    assert model.cursor_position.paragraph_index == 1
    assert model.cursor_position.character_index == 6
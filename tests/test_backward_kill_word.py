"""Test backward-kill-word (Alt-backspace) functionality."""

import pytest
from pagemark.model import TextModel, CursorPosition
from unittest.mock import Mock


def create_test_model(paragraphs):
    """Create a test model with given paragraphs."""
    view = Mock()
    view.render = Mock()
    return TextModel(view, paragraphs=paragraphs)


def test_backward_kill_word_basic():
    """Test basic backward word deletion."""
    model = create_test_model(["hello world test"])
    model.cursor_position = CursorPosition(0, 11)  # After "world"
    
    model.backward_kill_word()
    assert model.paragraphs[0] == "hello  test"  # Space preserved
    assert model.cursor_position.character_index == 6  # After "hello "


def test_backward_kill_word_at_word_start():
    """Test backward word deletion at start of a word."""
    model = create_test_model(["hello world test"])
    model.cursor_position = CursorPosition(0, 6)  # Start of "world"
    
    model.backward_kill_word()
    assert model.paragraphs[0] == "world test"
    assert model.cursor_position.character_index == 0


def test_backward_kill_word_multiple_spaces():
    """Test backward word deletion with multiple spaces."""
    model = create_test_model(["hello    world"])
    model.cursor_position = CursorPosition(0, 14)  # End of "world"
    
    model.backward_kill_word()
    assert model.paragraphs[0] == "hello    "
    assert model.cursor_position.character_index == 9


def test_backward_kill_word_across_paragraphs():
    """Test backward word deletion across paragraph boundary."""
    model = create_test_model(["first paragraph", "second"])
    model.cursor_position = CursorPosition(1, 0)  # Start of second paragraph
    
    model.backward_kill_word()
    assert len(model.paragraphs) == 1
    assert model.paragraphs[0] == "first paragraphsecond"
    assert model.cursor_position.paragraph_index == 0
    assert model.cursor_position.character_index == 15


def test_backward_kill_word_empty_paragraph():
    """Test backward word deletion with empty paragraphs."""
    model = create_test_model(["first", "", "third"])
    model.cursor_position = CursorPosition(1, 0)  # Empty paragraph
    
    model.backward_kill_word()
    assert len(model.paragraphs) == 2
    assert model.paragraphs == ["first", "third"]  # Joins the paragraphs
    assert model.cursor_position.paragraph_index == 0
    assert model.cursor_position.character_index == 5  # End of "first"
    

def test_backward_kill_word_at_document_start():
    """Test backward word deletion at start of document (no-op)."""
    model = create_test_model(["hello world"])
    model.cursor_position = CursorPosition(0, 0)
    
    model.backward_kill_word()
    assert model.paragraphs[0] == "hello world"  # No change
    assert model.cursor_position.character_index == 0


def test_backward_kill_word_with_punctuation():
    """Test backward word deletion with punctuation."""
    model = create_test_model(["hello, world!"])
    model.cursor_position = CursorPosition(0, 13)  # After "!"
    
    model.backward_kill_word()
    assert model.paragraphs[0] == "hello, "
    assert model.cursor_position.character_index == 7


def test_backward_kill_word_middle_of_word():
    """Test backward word deletion from middle of a word."""
    model = create_test_model(["hello wonderful world"])
    model.cursor_position = CursorPosition(0, 11)  # At 'r' in "wonderful"
    
    model.backward_kill_word()
    assert model.paragraphs[0] == "hello rful world"
    assert model.cursor_position.character_index == 6  # After "hello "
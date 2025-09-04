"""Test kill-line (Ctrl-K) functionality."""

import pytest
from pagemark.model import TextModel, CursorPosition
from unittest.mock import Mock


def create_test_model(paragraphs):
    """Create a test model with given paragraphs."""
    view = Mock()
    view.render = Mock()
    view.num_columns = 65  # Default editor width
    return TextModel(view, paragraphs=paragraphs)


def test_kill_line_basic():
    """Test basic kill to end of line."""
    model = create_test_model(["hello world test"])
    model.cursor_position = CursorPosition(0, 5)  # At space before "world"
    
    model.kill_line()
    assert model.paragraphs[0] == "hello"
    assert model.cursor_position.character_index == 5


def test_kill_line_at_beginning():
    """Test kill entire line from beginning."""
    model = create_test_model(["hello world"])
    model.cursor_position = CursorPosition(0, 0)
    
    model.kill_line()
    assert model.paragraphs[0] == ""
    assert model.cursor_position.character_index == 0


def test_kill_line_at_end():
    """Test kill at end of line joins with next paragraph."""
    model = create_test_model(["first", "second"])
    model.cursor_position = CursorPosition(0, 5)  # End of "first"
    
    model.kill_line()
    assert len(model.paragraphs) == 1
    assert model.paragraphs[0] == "firstsecond"
    assert model.cursor_position.character_index == 5


def test_kill_line_empty_paragraph():
    """Test kill on empty paragraph."""
    model = create_test_model(["", "second"])
    model.cursor_position = CursorPosition(0, 0)
    
    model.kill_line()
    assert len(model.paragraphs) == 1
    assert model.paragraphs[0] == "second"
    assert model.cursor_position.character_index == 0


def test_kill_line_at_document_end():
    """Test kill at end of document does nothing."""
    model = create_test_model(["hello"])
    model.cursor_position = CursorPosition(0, 5)
    
    model.kill_line()
    assert model.paragraphs[0] == "hello"
    assert model.cursor_position.character_index == 5


def test_kill_line_middle_of_word():
    """Test kill from middle of a word."""
    model = create_test_model(["hello wonderful world"])
    model.cursor_position = CursorPosition(0, 8)  # At 'd' in "wonderful"
    
    model.kill_line()
    assert model.paragraphs[0] == "hello wo"
    assert model.cursor_position.character_index == 8


def test_kill_line_multiple_paragraphs():
    """Test kill line behavior with multiple paragraphs."""
    model = create_test_model(["first line", "second line", "third line"])
    
    # Kill from middle of first line
    model.cursor_position = CursorPosition(0, 6)  # After "first "
    model.kill_line()
    assert model.paragraphs[0] == "first "
    assert len(model.paragraphs) == 3
    
    # Kill at end of first line (joins with second)
    model.kill_line()
    assert model.paragraphs[0] == "first second line"
    assert len(model.paragraphs) == 2


def test_kill_line_consecutive():
    """Test consecutive kill-line operations."""
    model = create_test_model(["hello world", "second line"])
    model.cursor_position = CursorPosition(0, 6)  # After "hello "
    
    # First kill removes "world"
    model.kill_line()
    assert model.paragraphs[0] == "hello "
    
    # Second kill joins with next line
    model.kill_line()
    assert model.paragraphs[0] == "hello second line"
    assert len(model.paragraphs) == 1
"""Tests for the Textual-based editor."""

import pytest
from pagemark.textual_editor import PagemarkEditor
from pagemark.model import TextModel, CursorPosition
from unittest.mock import Mock, patch


def test_editor_creation():
    """Test that the editor can be created."""
    app = PagemarkEditor()
    assert app is not None
    assert app.filename is None


def test_editor_with_filename():
    """Test creating editor with a filename."""
    app = PagemarkEditor(filename="test.txt")
    assert app.filename == "test.txt"


def test_model_functions_exist():
    """Test that the model functions we implemented exist."""
    model = TextModel(Mock())
    
    # Check that all our Emacs functions exist
    assert hasattr(model, 'left_word')
    assert hasattr(model, 'right_word')
    assert hasattr(model, 'backward_kill_word')
    assert hasattr(model, 'delete_char')
    assert hasattr(model, 'move_beginning_of_line')
    assert hasattr(model, 'move_end_of_line')
    assert hasattr(model, 'kill_line')


def test_cursor_position():
    """Test CursorPosition class."""
    pos1 = CursorPosition(0, 0)
    pos2 = CursorPosition(1, 0)
    
    assert pos1 < pos2
    assert pos2 >= pos1
    assert pos1.paragraph_index == 0
    assert pos1.character_index == 0
"""Test center line functionality."""

import pytest
from unittest.mock import Mock
from pagemark.model import TextModel, CursorPosition
from pagemark.editor import Editor
from pagemark.keyboard import KeyEvent, KeyType
from pagemark.commands import CenterLineCommand
from pagemark.constants import EditorConstants


def create_mock_view():
    """Create a mock view for testing."""
    view = Mock()
    view.render = Mock()
    view.num_columns = EditorConstants.DOCUMENT_WIDTH
    return view


def test_center_single_line():
    """Test centering a single line paragraph."""
    view = create_mock_view()
    model = TextModel(view, paragraphs=["Hello World"])
    model.cursor_position = CursorPosition(0, 0)
    
    result = model.center_line()
    
    assert result == True
    # Should be centered within 65 character width
    expected_spaces = (65 - len("Hello World")) // 2
    expected = ' ' * expected_spaces + "Hello World"
    assert model.paragraphs[0] == expected
    # Cursor should be at the start of the centered text
    assert model.cursor_position.character_index == expected_spaces


def test_center_line_with_existing_spaces():
    """Test centering a line that already has leading/trailing spaces."""
    view = create_mock_view()
    model = TextModel(view, paragraphs=["    Hello World    "])
    model.cursor_position = CursorPosition(0, 5)  # After first 'H'
    
    result = model.center_line()
    
    assert result == True
    # Should strip and re-center
    expected_spaces = (65 - len("Hello World")) // 2
    expected = ' ' * expected_spaces + "Hello World"
    assert model.paragraphs[0] == expected
    # Cursor should maintain relative position in the text
    assert model.cursor_position.character_index == expected_spaces + 1


def test_center_multi_line_paragraph_fails():
    """Test that centering fails for multi-line paragraphs."""
    view = create_mock_view()
    # Create a paragraph that's too long to fit on one line
    long_text = "a" * 70  # Longer than DOCUMENT_WIDTH (65)
    model = TextModel(view, paragraphs=[long_text])
    model.cursor_position = CursorPosition(0, 0)
    
    result = model.center_line()
    
    assert result == False
    # Paragraph should remain unchanged
    assert model.paragraphs[0] == long_text


def test_center_empty_line():
    """Test centering an empty line."""
    view = create_mock_view()
    model = TextModel(view, paragraphs=[""])
    model.cursor_position = CursorPosition(0, 0)
    
    result = model.center_line()
    
    assert result == True
    # Empty line should remain empty
    assert model.paragraphs[0] == ""


def test_center_line_at_max_width():
    """Test centering a line that's exactly at document width."""
    view = create_mock_view()
    # Create text exactly 65 characters
    text = "x" * EditorConstants.DOCUMENT_WIDTH
    model = TextModel(view, paragraphs=[text])
    model.cursor_position = CursorPosition(0, 0)
    
    result = model.center_line()
    
    assert result == False
    # Line at max width cannot be centered
    assert model.paragraphs[0] == text


def test_center_line_command_success():
    """Test CenterLineCommand when centering succeeds."""
    editor = Editor()
    editor.model.paragraphs = ["Short text"]
    editor.model.cursor_position = CursorPosition(0, 0)
    
    command = CenterLineCommand()
    key_event = KeyEvent(
        key_type=KeyType.CTRL,
        value='^',
        raw='\x1e',
        is_ctrl=True,
        is_alt=False,
        is_sequence=False,
        code=None
    )
    
    modified = command.execute(editor, key_event)
    
    assert modified == True  # Document was modified
    assert editor.status_message is None  # No error message


def test_center_line_command_multi_line_error():
    """Test CenterLineCommand shows error for multi-line paragraph."""
    editor = Editor()
    editor.model.paragraphs = ["a" * 70]  # Too long to fit on one line
    editor.model.cursor_position = CursorPosition(0, 0)
    
    command = CenterLineCommand()
    key_event = KeyEvent(
        key_type=KeyType.CTRL,
        value='^',
        raw='\x1e',
        is_ctrl=True,
        is_alt=False,
        is_sequence=False,
        code=None
    )
    
    modified = command.execute(editor, key_event)
    
    assert modified == True  # EditCommand always returns True
    assert editor.status_message == "Cannot center multi-line paragraph"


def test_center_line_command_through_registry():
    """Test center line command through command registry."""
    from pagemark.commands import CommandRegistry
    
    registry = CommandRegistry()
    
    # Check that Alt-m is registered
    command = registry.get_command(KeyType.ALT, 'm')
    assert command is not None
    assert isinstance(command, CenterLineCommand)
"""Tests for incremental search functionality."""

import pytest
from unittest.mock import MagicMock, Mock, PropertyMock
from pagemark.editor import Editor
from pagemark.keyboard import KeyEvent, KeyType


@pytest.fixture
def editor_with_text():
    """Create an editor with sample text for searching."""
    editor = MagicMock(spec=Editor)
    
    # Set up model with test paragraphs
    editor.model = MagicMock()
    editor.model.paragraphs = [
        "The quick brown fox jumps over the lazy dog.",
        "This is a test file for incremental search functionality.",
        "We need to find words like search, test, and fox.",
        "The word search appears multiple times in this document.",
    ]
    
    # Set up cursor position
    cursor_pos = MagicMock()
    cursor_pos.paragraph_index = 0
    cursor_pos.character_index = 0
    editor.model.cursor_position = cursor_pos
    
    # Set up view
    editor.view = MagicMock()
    editor.view.render = Mock()
    
    # Initialize search-related attributes
    editor._isearch_origin = None
    editor._isearch_last_match = None
    editor.prompt_mode = None
    editor.prompt_input = ""
    editor.status_message = None
    
    # Add real methods from Editor
    editor.start_incremental_search = Editor.start_incremental_search.__get__(editor)
    editor._find_forward = Editor._find_forward.__get__(editor)
    editor._move_cursor_to = Editor._move_cursor_to.__get__(editor)
    editor._isearch_update = Editor._isearch_update.__get__(editor)
    editor._isearch_find_next = Editor._isearch_find_next.__get__(editor)
    editor._handle_isearch_prompt = Editor._handle_isearch_prompt.__get__(editor)
    
    return editor


def test_start_incremental_search(editor_with_text):
    """Test starting incremental search mode."""
    editor = editor_with_text
    
    editor.start_incremental_search()
    
    assert editor.prompt_mode == 'isearch'
    assert editor.prompt_input == ""
    assert editor._isearch_origin == (0, 0)
    assert editor._isearch_last_match is None


def test_search_empty_document():
    """Test searching in an empty document."""
    editor = MagicMock(spec=Editor)
    editor.model = MagicMock()
    editor.model.paragraphs = []
    editor.status_message = None
    editor.prompt_mode = None  # Initialize prompt_mode
    
    # Add real method
    editor.start_incremental_search = Editor.start_incremental_search.__get__(editor)
    
    editor.start_incremental_search()
    
    assert editor.status_message == "No text to search"
    assert editor.prompt_mode != 'isearch'


def test_find_forward_basic(editor_with_text):
    """Test basic forward search functionality."""
    editor = editor_with_text
    
    # Search for 'fox' from beginning
    match = editor._find_forward('fox', (0, 0))
    assert match == (0, 16)  # First 'fox' in first paragraph
    
    # Search for 'search' from beginning
    match = editor._find_forward('search', (0, 0))
    assert match == (1, 36)  # First 'search' in second paragraph
    
    # Search for non-existent text
    match = editor._find_forward('xyz', (0, 0))
    assert match is None


def test_find_forward_case_insensitive(editor_with_text):
    """Test that search is case-insensitive."""
    editor = editor_with_text
    
    # Search for 'FOX' should find 'fox'
    match = editor._find_forward('FOX', (0, 0))
    assert match == (0, 16)
    
    # Search for 'SEARCH' should find 'search'
    match = editor._find_forward('SEARCH', (0, 0))
    assert match == (1, 36)


def test_find_forward_from_middle(editor_with_text):
    """Test searching from middle of document."""
    editor = editor_with_text
    
    # Search for 'fox' starting from paragraph 2
    match = editor._find_forward('fox', (2, 0))
    assert match == (2, 45)  # 'fox' in third paragraph
    
    # Search for 'search' starting after first occurrence
    match = editor._find_forward('search', (1, 37))
    assert match == (2, 27)  # Next 'search' in third paragraph


def test_incremental_search_character_input(editor_with_text):
    """Test typing characters during incremental search."""
    editor = editor_with_text
    editor.start_incremental_search()
    
    # Type 'f'
    key_event = Mock()
    key_event.key_type = KeyType.REGULAR
    key_event.value = 'f'
    editor._handle_isearch_prompt(key_event)
    
    assert editor.prompt_input == 'f'
    # Should have moved to first 'f' in 'fox'
    assert editor.model.cursor_position.paragraph_index == 0
    assert editor.model.cursor_position.character_index == 16
    
    # Type 'o' to make 'fo'
    key_event.value = 'o'
    editor._handle_isearch_prompt(key_event)
    
    assert editor.prompt_input == 'fo'
    # Should still be at 'fox'
    assert editor.model.cursor_position.paragraph_index == 0
    assert editor.model.cursor_position.character_index == 16


def test_incremental_search_backspace(editor_with_text):
    """Test backspace during incremental search."""
    editor = editor_with_text
    editor.start_incremental_search()
    editor.prompt_input = "fox"
    editor._isearch_update()
    
    # Backspace to remove 'x'
    key_event = Mock()
    key_event.key_type = KeyType.SPECIAL
    key_event.value = 'backspace'
    editor._handle_isearch_prompt(key_event)
    
    assert editor.prompt_input == "fo"


def test_incremental_search_cancel(editor_with_text):
    """Test canceling incremental search with ESC."""
    editor = editor_with_text
    editor.start_incremental_search()
    
    # Move cursor by searching
    editor.prompt_input = "fox"
    editor._isearch_update()
    
    # Cancel with ESC
    key_event = Mock()
    key_event.key_type = KeyType.SPECIAL
    key_event.value = 'escape'
    editor._handle_isearch_prompt(key_event)
    
    # Should restore original position
    assert editor.model.cursor_position.paragraph_index == 0
    assert editor.model.cursor_position.character_index == 0
    assert editor.prompt_mode is None
    assert editor._isearch_origin is None


def test_incremental_search_accept(editor_with_text):
    """Test accepting search position with Enter."""
    editor = editor_with_text
    editor.start_incremental_search()
    
    # Search for something
    editor.prompt_input = "fox"
    editor._isearch_update()
    
    # Accept with Enter
    key_event = Mock()
    key_event.key_type = KeyType.SPECIAL
    key_event.value = 'enter'
    editor._handle_isearch_prompt(key_event)
    
    # Should keep current position
    assert editor.model.cursor_position.paragraph_index == 0
    assert editor.model.cursor_position.character_index == 16
    assert editor.prompt_mode is None
    assert editor._isearch_origin is None


def test_incremental_search_find_next(editor_with_text):
    """Test finding next match with Ctrl-F during search."""
    editor = editor_with_text
    editor.start_incremental_search()
    
    # Search for 'search'
    editor.prompt_input = "search"
    editor._isearch_update()
    
    # Should be at first 'search' in paragraph 1
    assert editor.model.cursor_position.paragraph_index == 1
    assert editor.model.cursor_position.character_index == 36
    
    # Press Ctrl-F for next match
    key_event = Mock()
    key_event.key_type = KeyType.CTRL
    key_event.value = 'f'
    editor._handle_isearch_prompt(key_event)
    
    # Should be at second 'search' in paragraph 2
    assert editor.model.cursor_position.paragraph_index == 2
    assert editor.model.cursor_position.character_index == 27


def test_incremental_search_no_match(editor_with_text):
    """Test searching for non-existent text."""
    editor = editor_with_text
    editor.start_incremental_search()
    
    # Search for non-existent text
    editor.prompt_input = "xyz"
    editor._isearch_update()
    
    # Should indicate no match
    assert editor._isearch_last_match is None
    # Cursor should stay at original position
    assert editor.model.cursor_position.paragraph_index == 0
    assert editor.model.cursor_position.character_index == 0


def test_unicode_character_input(editor_with_text):
    """Test that Unicode characters are handled correctly."""
    editor = editor_with_text
    editor.start_incremental_search()
    
    # Type Unicode character
    key_event = Mock()
    key_event.key_type = KeyType.REGULAR
    key_event.value = '€'
    editor._handle_isearch_prompt(key_event)
    
    assert editor.prompt_input == '€'
    
    # Test emoji
    key_event.value = '😊'
    editor._handle_isearch_prompt(key_event)
    
    assert editor.prompt_input == '€😊'


def test_control_characters_ignored(editor_with_text):
    """Test that control characters are ignored during search."""
    editor = editor_with_text
    editor.start_incremental_search()
    
    # Try to input control character
    key_event = Mock()
    key_event.key_type = KeyType.REGULAR
    key_event.value = '\x01'  # Ctrl-A
    editor._handle_isearch_prompt(key_event)
    
    # Should be ignored
    assert editor.prompt_input == ""
    
    # Tab and newline should also be ignored
    key_event.value = '\t'
    editor._handle_isearch_prompt(key_event)
    assert editor.prompt_input == ""
    
    key_event.value = '\n'
    editor._handle_isearch_prompt(key_event)
    assert editor.prompt_input == ""
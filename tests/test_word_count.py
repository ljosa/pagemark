"""Test word count functionality."""

import pytest
from pagemark.model import DocumentModel
from pagemark.editor import Editor
from pagemark.keyboard import KeyEvent, KeyType
from pagemark.commands import WordCountCommand


def test_count_words_empty_document():
    """Test word count on empty document."""
    model = DocumentModel()
    model.paragraphs = [""]
    assert model.count_words() == 0


def test_count_words_single_paragraph():
    """Test word count on single paragraph."""
    model = DocumentModel()
    model.paragraphs = ["This is a test paragraph with six words."]
    assert model.count_words() == 8


def test_count_words_multiple_paragraphs():
    """Test word count across multiple paragraphs."""
    model = DocumentModel()
    model.paragraphs = [
        "First paragraph has four words.",
        "Second paragraph also has five words.",
        "Third one."
    ]
    assert model.count_words() == 13


def test_count_words_with_extra_spaces():
    """Test word count handles extra spaces correctly."""
    model = DocumentModel()
    model.paragraphs = [
        "  Multiple   spaces   between   words  ",
        "    Leading and trailing spaces    "
    ]
    assert model.count_words() == 8


def test_count_words_with_empty_paragraphs():
    """Test word count with empty paragraphs."""
    model = DocumentModel()
    model.paragraphs = [
        "First paragraph.",
        "",
        "Second paragraph after empty.",
        "",
        ""
    ]
    assert model.count_words() == 6


def test_word_count_command_sets_status_message():
    """Test that WordCountCommand sets the status message."""
    editor = Editor()
    editor.model.paragraphs = ["This document has exactly five words."]
    
    # Execute word count command
    command = WordCountCommand()
    key_event = KeyEvent(
        key_type=KeyType.CTRL,
        value='w',
        raw='\x17',
        is_ctrl=True,
        is_alt=False,
        is_sequence=False,
        code=None
    )
    
    command.execute(editor, key_event)
    
    # Check status message
    assert editor.status_message == "6 words"


def test_word_count_command_through_registry():
    """Test word count command through command registry."""
    from pagemark.commands import CommandRegistry
    
    registry = CommandRegistry()
    
    # Check that Ctrl-W is registered
    command = registry.get_command(KeyType.CTRL, 'w')
    assert command is not None
    assert isinstance(command, WordCountCommand)

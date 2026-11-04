"""Regression tests for editor-level bugs (BUG-13, BUG-17)."""

import time
from unittest.mock import patch

import pytest

from pagemark.constants import EditorConstants
from pagemark.editor import Editor
from pagemark.keyboard import KeyEvent, KeyType
from pagemark.session import get_session


@pytest.fixture
def clean_session():
    get_session().clear()
    yield
    get_session().clear()


def press(editor, char):
    editor._handle_quit_confirm(
        KeyEvent(key_type=KeyType.REGULAR, value=char, raw=char))


# --- BUG-13: answering "y" to "Save file?" must not quit on a failed save ---

def test_quit_confirm_failed_save_does_not_quit(clean_session):
    editor = Editor()
    editor.filename = "test.txt"
    editor.modified = True
    editor.running = True
    editor.prompt_mode = 'quit_confirm'

    with patch.object(editor, 'save_file', return_value=False) as mock_save:
        press(editor, 'y')

    mock_save.assert_called_once_with("test.txt")
    assert editor.running is True
    # Back in the editor so the save error message is visible.
    assert editor.prompt_mode is None


def test_quit_confirm_successful_save_quits(clean_session):
    editor = Editor()
    editor.filename = "test.txt"
    editor.modified = True
    editor.running = True
    editor.prompt_mode = 'quit_confirm'

    with patch.object(editor, 'save_file', return_value=True):
        press(editor, 'y')

    assert editor.running is False


# --- BUG-17: the autosave backstop must fire despite continuous typing ---

def test_backstop_fires_during_continuous_typing(clean_session):
    editor = Editor()
    editor.filename = "test.txt"
    editor.modified = True
    now = time.monotonic()
    # User has been typing for > backstop without pause and never autosaved.
    editor._last_edit_time = now - 1
    editor._last_autosave_time = None
    editor._pending_edit_since = now - EditorConstants.AUTOSAVE_BACKSTOP_SECONDS - 1

    with patch('pagemark.editor.write_swap_file', return_value=True) as mock_write:
        editor._maybe_autosave()

    mock_write.assert_called_once()
    # A successful autosave rearms the backstop.
    assert editor._pending_edit_since is None
    assert editor._last_autosave_time is not None


def test_undo_counts_as_an_edit_for_autosave(clean_session):
    """Undo/redo modify the buffer without a key event; autosave must still
    see the restored state as new (review finding on the BUG-17 fix)."""
    editor = Editor()
    editor.filename = "test.txt"
    editor.modified = True
    now = time.monotonic()
    editor._last_edit_time = now - 100
    editor._last_autosave_time = now - 50  # autosave is current...

    editor.model.insert_text("unsaved text")
    snapshot = editor._snapshot_state()
    editor._apply_snapshot(snapshot)  # ...then the user presses Ctrl-Z

    assert editor._autosave_is_current() is False
    assert editor._calculate_autosave_timeout() is not None


def test_no_repeat_autosave_without_new_edits(clean_session):
    """_maybe_autosave now runs on every loop wakeup; it must not rewrite the
    swap file when nothing changed since the last autosave."""
    editor = Editor()
    editor.filename = "test.txt"
    editor.modified = True
    now = time.monotonic()
    editor._last_edit_time = now - 100          # debounce long since met
    editor._last_autosave_time = now - 50       # ...but already autosaved

    with patch('pagemark.editor.write_swap_file', return_value=True) as mock_write:
        editor._maybe_autosave()

    mock_write.assert_not_called()

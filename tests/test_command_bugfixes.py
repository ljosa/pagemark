"""Regression tests for command-layer bugs (BUG-16, BUG-19)."""

import pytest

from pagemark.editor import Editor
from pagemark.keyboard import KeyEvent, KeyType
from pagemark.model import CursorPosition
from pagemark.session import get_session


@pytest.fixture
def editor():
    get_session().clear()
    ed = Editor()
    ed.view.num_rows = 10
    ed.view.num_columns = 65
    yield ed
    get_session().clear()


def key(key_type, value):
    return KeyEvent(key_type=key_type, value=value, raw=value)


# --- BUG-16: Ctrl-B/Ctrl-U on a selection must re-render immediately ---

def test_style_toggle_updates_rendered_styles(editor):
    editor.model.paragraphs = ["hello world"]
    editor.model.styles = [[0] * 11]
    editor.view.render()

    # Select "hello"
    editor.model.cursor_position = CursorPosition(0, 0)
    editor.model.start_selection()
    editor.model.cursor_position = CursorPosition(0, 5)
    editor.model.update_selection_end()

    editor.command_registry.execute(editor, key(KeyType.CTRL, 'b'))

    # The frame the editor draws from must already show the bold run.
    assert editor.view.line_styles[0][:5] == [1, 1, 1, 1, 1]
    assert editor.view.line_styles[0][5:] == [0] * 6


# --- BUG-19: no-op edits must not mark modified or pollute the undo stack ---

def test_cut_without_selection_is_not_a_modification(editor):
    editor.model.paragraphs = ["hello"]
    editor.view.render()
    assert editor.modified is False

    editor._handle_key_event(key(KeyType.CTRL, 'x'))

    assert editor.modified is False
    assert not editor.undo.can_undo()


def test_caret_style_toggle_without_selection_is_not_a_modification(editor):
    editor.model.paragraphs = ["hello"]
    editor.view.render()

    editor._handle_key_event(key(KeyType.CTRL, 'b'))

    assert editor.modified is False
    assert not editor.undo.can_undo()
    # The caret style itself must still toggle.
    assert editor.model.caret_style == 1


def test_real_edit_still_marks_modified_and_undoable(editor):
    editor.model.paragraphs = [""]
    editor.view.render()

    editor._handle_key_event(key(KeyType.REGULAR, 'a'))

    assert editor.modified is True
    assert editor.undo.can_undo()
    assert editor.model.paragraphs == ["a"]

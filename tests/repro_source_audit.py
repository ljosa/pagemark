"""Opt-in bug reproductions; assertions describe the intended behavior.

Run: .venv/bin/python -m pytest tests/repro_source_audit.py -q --tb=short
These currently fail. The filename excludes them from default test discovery.
All filesystem changes use pytest's temporary directory; no real clipboard,
terminal session, printer, or user settings are accessed.
"""

import os
from pathlib import Path
import stat
import subprocess
import sys
from types import SimpleNamespace

import pytest
from wcwidth import wcswidth

from pagemark.clipboard import ClipboardManager
from pagemark.editor import Editor
from pagemark.keyboard import KeyEvent, KeyType
from pagemark.model import CursorPosition, TextModel
from pagemark.session import SessionKeys, SessionManager
from pagemark.settings_persistence import SettingsPersistence
from pagemark.view import render_paragraph


@pytest.fixture
def editor(monkeypatch, tmp_path):
    monkeypatch.setattr(SessionManager, "_instance", None)
    persistence = SettingsPersistence()
    persistence._config_dir = tmp_path / "config"
    persistence._settings_file = persistence._config_dir / "settings.json"
    monkeypatch.setattr("pagemark.settings_persistence._persistence", persistence)
    monkeypatch.setattr(
        "pagemark.editor.TerminalInterface",
        lambda: SimpleNamespace(height=24, width=80),
    )
    instance = Editor()
    instance.view.render()
    try:
        yield instance
    finally:
        os.close(instance._resize_pipe_r)
        os.close(instance._resize_pipe_w)


def press(editor, key_type, value):
    return editor._handle_key_event(KeyEvent(key_type=key_type, value=value, raw=value))


def set_text(editor, text):
    editor.model = TextModel(editor.view, [text])
    editor.view.render()


def select_all(editor):
    editor.model.move_end_of_document()
    editor.model.selection_start = CursorPosition(0, 0)
    editor.model.selection_end = CursorPosition(0, len(editor.model.paragraphs[0]))


@pytest.mark.parametrize("indent,word", [(63, "x"), (62, "—")])
def test_bug22_indented_bullet_render_terminates(indent, word):
    # A separate process bounds the non-terminating renderer and is killed and
    # reaped by subprocess.run on timeout. No editor process is left behind.
    source = (
        "from pagemark.view import render_paragraph\n"
        "print('renderer-ready', flush=True)\n"
        f"print(render_paragraph({' ' * indent + '- ' + word!r}, 65))\n"
    )
    try:
        result = subprocess.run(
            [sys.executable, "-c", source],
            cwd=Path(__file__).resolve().parents[1],
            capture_output=True,
            text=True,
            timeout=1,
            check=True,
        )
    except subprocess.TimeoutExpired as exc:
        assert b"renderer-ready" in (exc.stdout or b""), "Python startup timed out"
        pytest.fail("render_paragraph did not finish within 1 second after import")
    assert "renderer-ready" in result.stdout


def test_bug23_save_preserves_symlink_and_updates_target(editor, tmp_path):
    target = tmp_path / "original.txt"
    target.write_text("old", encoding="utf-8")
    link = tmp_path / "link.txt"
    link.symlink_to(target)
    editor.load_file(str(link))
    press(editor, KeyType.REGULAR, "new ")
    assert editor.save_file(str(link))
    assert (link.is_symlink(), target.read_text(encoding="utf-8")) == (True, "new old")


def test_bug24_save_preserves_existing_permissions(editor, tmp_path):
    path = tmp_path / "shared.txt"
    path.write_text("old", encoding="utf-8")
    path.chmod(0o640)
    editor.load_file(str(path))
    press(editor, KeyType.REGULAR, "new ")
    assert editor.save_file(str(path))
    assert stat.S_IMODE(path.stat().st_mode) == 0o640


@pytest.mark.parametrize(
    "key,text,expected",
    [("u", "ß X", "SS X"), ("l", "İ X", "i̇ X"), ("c", "ß X", "SS X")],
)
def test_bug25_case_expansion_preserves_styles_and_cursor(editor, key, text, expected):
    set_text(editor, text)
    editor.model.styles = [[1, 0, 2]]
    press(editor, KeyType.ALT, key)
    assert editor.model.paragraphs == [expected]
    assert (editor.model.styles, editor.model.cursor_position.character_index) == (
        [[1, 1, 0, 2]],
        2,
    )


def test_bug26_unicode_search_returns_original_character_index(editor):
    set_text(editor, "İx")
    press(editor, KeyType.CTRL, "f")
    press(editor, KeyType.REGULAR, "x")
    assert editor.model.cursor_position == CursorPosition(0, 1)


@pytest.mark.parametrize("clipboard_text", ["", "\x00"])
def test_bug27_empty_paste_preserves_selection(editor, monkeypatch, clipboard_text):
    set_text(editor, "keep me")
    select_all(editor)
    monkeypatch.setattr(ClipboardManager, "paste_text", lambda: (clipboard_text, None))
    press(editor, KeyType.CTRL, "v")
    assert editor.model.paragraphs == ["keep me"]
    assert not editor.undo.can_undo()


@pytest.mark.parametrize(
    "key_type,key,expected",
    [
        (KeyType.SPECIAL, "enter", ["", ""]),
        (KeyType.SPECIAL, "backspace", [""]),
        (KeyType.CTRL, "d", [""]),
    ],
)
def test_bug28_editing_replaces_selected_range(editor, key_type, key, expected):
    set_text(editor, "abc")
    select_all(editor)
    press(editor, key_type, key)
    assert editor.model.paragraphs == expected
    assert editor.model.selection_start is None


def test_bug29_first_save_associates_settings_with_document(editor, tmp_path):
    path = tmp_path / "new.txt"
    press(editor, KeyType.REGULAR, "text")
    press(editor, KeyType.CTRL, "s")
    assert editor.prompt_mode == "save_filename"
    # Filename input normally arrives one character at a time.
    for char in str(path):
        press(editor, KeyType.REGULAR, char)
    press(editor, KeyType.SPECIAL, "enter")
    assert path.read_text(encoding="utf-8") == "text"
    editor.session.set(SessionKeys.DOUBLE_SPACING, True)
    editor.session.clear()
    editor.load_file(str(path))
    assert editor.spacing_double is True


@pytest.mark.parametrize("text", ["界x", "e\u0301x"])
def test_bug30_cursor_uses_terminal_cell_width(editor, text):
    press(editor, KeyType.REGULAR, text)
    assert editor.view.visual_cursor_x == wcswidth(text)


def test_existing_bug5_undo_to_saved_content_clears_modified(editor, tmp_path):
    path = tmp_path / "saved.txt"
    set_text(editor, "saved")
    assert editor.save_file(str(path))
    press(editor, KeyType.REGULAR, "x")
    press(editor, KeyType.CTRL, "z")
    assert editor.model.to_overstrike_text() == path.read_text(encoding="utf-8")
    assert editor.modified is False


def test_existing_bug6_word_fitting_exactly_does_not_wrap():
    text = "a " + "b" * 63
    assert len(text) == 65
    lines, _ = render_paragraph(text, 65)
    assert lines == [text]

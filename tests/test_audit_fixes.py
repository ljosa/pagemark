"""Regression tests for bugs documented in BUG_AUDIT.md."""

import os
import stat
from pathlib import Path
import subprocess
import sys
from types import SimpleNamespace

import pytest

from pagemark.keyboard import KeyType
from pagemark.editor import Editor
from pagemark.keyboard import KeyEvent
from pagemark.model import CursorPosition, TextModel
from pagemark.session import SessionManager
from pagemark.settings_persistence import SettingsPersistence


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


@pytest.mark.parametrize("width", [1, 2, 65])
def test_bug22_wrapping_preserves_content_and_mapping(width):
    from pagemark.view import get_line_mapper

    paragraph = " " * 63 + "- —abc"
    mapper = get_line_mapper(paragraph, width)
    assert mapper.cumulative_counts[-1] == len(paragraph)
    assert all(
        a <= b for a, b in zip(mapper.cumulative_counts, mapper.cumulative_counts[1:])
    )
    for index, line in enumerate(mapper.lines):
        start, end = mapper.line_start(index), mapper.line_end(index)
        content = paragraph[start:end].replace("—", "--")
        prefix = " " * mapper.hanging_width if index else ""
        assert line == prefix + content or line == prefix + content[:-1]


def test_bug23_save_preserves_symlink_and_updates_target(editor, tmp_path):
    target = tmp_path / "original.txt"
    target.write_text("old", encoding="utf-8")
    link = tmp_path / "link.txt"
    link.symlink_to(target)
    editor.load_file(str(link))
    press(editor, KeyType.REGULAR, "new ")
    assert editor.save_file(str(link))
    assert (link.is_symlink(), target.read_text(encoding="utf-8")) == (True, "new old")


@pytest.mark.parametrize("target_exists", [True, False])
def test_bug23_relative_link_chain_across_directories(editor, tmp_path, target_exists):
    directory = tmp_path / "documents"
    directory.mkdir()
    target = directory / "target.txt"
    if target_exists:
        target.write_text("old", encoding="utf-8")
    intermediate = tmp_path / "intermediate.txt"
    intermediate.symlink_to("documents/target.txt")
    link = tmp_path / "alias.txt"
    link.symlink_to("intermediate.txt")
    editor.load_file(str(link))
    set_text(editor, "new")
    assert editor.save_file(str(link))
    assert link.is_symlink() and intermediate.is_symlink()
    assert target.read_text(encoding="utf-8") == "new"
    assert editor.filename == str(link)


def test_bug23_failed_save_preserves_symlink(editor, tmp_path, monkeypatch):
    target = tmp_path / "target.txt"
    target.write_text("old", encoding="utf-8")
    link = tmp_path / "alias.txt"
    link.symlink_to(target)
    editor.load_file(str(link))
    set_text(editor, "new")

    def fail_replace(*args):
        raise OSError("simulated replacement failure")

    monkeypatch.setattr("pagemark.editor.os.replace", fail_replace)
    assert not editor.save_file(str(link))
    assert link.is_symlink()
    assert target.read_text(encoding="utf-8") == "old"
    assert sorted(p.name for p in tmp_path.iterdir()) == ["alias.txt", "target.txt"]


def test_bug24_save_preserves_existing_permissions(editor, tmp_path):
    path = tmp_path / "shared.txt"
    path.write_text("old", encoding="utf-8")
    path.chmod(0o640)
    editor.load_file(str(path))
    press(editor, KeyType.REGULAR, "new ")
    assert editor.save_file(str(path))
    assert stat.S_IMODE(path.stat().st_mode) == 0o640


@pytest.mark.parametrize("mode", [0o600, 0o644, 0o755])
def test_bug24_save_preserves_symlink_target_mode(editor, tmp_path, mode):
    target = tmp_path / "target.txt"
    target.write_text("old", encoding="utf-8")
    target.chmod(mode)
    link = tmp_path / "alias.txt"
    link.symlink_to(target)
    set_text(editor, "new")
    assert editor.save_file(str(link))
    assert stat.S_IMODE(target.stat().st_mode) == mode
    assert link.is_symlink()


def test_bug24_new_file_has_private_permissions(editor, tmp_path):
    target = tmp_path / "new.txt"
    assert editor.save_file(str(target))
    assert stat.S_IMODE(target.stat().st_mode) == 0o600


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


@pytest.mark.parametrize(
    "key,text,expected", [("l", "ΟΣ X", "ος X"), ("c", "aΣ X", "Aσ X")]
)
def test_bug25_case_conversion_keeps_context(editor, key, text, expected):
    set_text(editor, text)
    editor.model.styles = [[1, 2, 0, 3]]
    press(editor, KeyType.ALT, key)
    assert editor.model.paragraphs == [expected]
    assert editor.model.styles == [[1, 2, 0, 3]]


def test_bug25_expansion_with_prefix_suffix_and_undo(editor):
    set_text(editor, "a ß X")
    editor.model.styles = [[0, 0, 1, 0, 2]]
    editor.model.cursor_position = CursorPosition(0, 1)
    press(editor, KeyType.ALT, "u")
    assert editor.model.paragraphs == ["a SS X"]
    assert editor.model.styles == [[0, 0, 1, 1, 0, 2]]
    assert editor.model.cursor_position == CursorPosition(0, 4)
    press(editor, KeyType.CTRL, "z")
    assert editor.model.paragraphs == ["a ß X"]
    assert editor.model.styles == [[0, 0, 1, 0, 2]]
    press(editor, KeyType.CTRL, "y")
    assert editor.model.styles == [[0, 0, 1, 1, 0, 2]]


def test_bug26_unicode_search_returns_original_character_index(editor):
    set_text(editor, "İx")
    press(editor, KeyType.CTRL, "f")
    press(editor, KeyType.REGULAR, "x")
    assert editor.model.cursor_position == CursorPosition(0, 1)


def test_bug26_repeated_search_advances_in_original_coordinates(editor):
    set_text(editor, "İx İx")
    press(editor, KeyType.CTRL, "f")
    press(editor, KeyType.REGULAR, "x")
    assert editor.model.cursor_position == CursorPosition(0, 1)
    press(editor, KeyType.CTRL, "f")
    assert editor.model.cursor_position == CursorPosition(0, 4)
    press(editor, KeyType.CTRL, "f")
    assert editor.model.cursor_position == CursorPosition(0, 4)
    press(editor, KeyType.CTRL, "g")
    assert editor.model.cursor_position == CursorPosition(0, 0)


def test_bug26_search_skips_expansion_before_start_and_finds_next_paragraph(editor):
    set_text(editor, "İx")
    assert editor._find_forward("x", (0, 2)) is None
    editor.model.insert_text("\nİİx")
    assert editor._find_forward("x", (1, 0)) == (1, 2)

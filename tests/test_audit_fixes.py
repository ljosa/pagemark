"""Regression tests for bugs documented in BUG_AUDIT.md."""

import os
from pathlib import Path
import subprocess
import sys
from types import SimpleNamespace

import pytest

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

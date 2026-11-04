"""Regression tests for bugs documented in BUG_AUDIT.md."""

import os
import stat
from pathlib import Path
import subprocess
import sys
from types import SimpleNamespace

import pytest
from wcwidth import wcswidth

from pagemark.keyboard import KeyType
from pagemark.editor import Editor
from pagemark.keyboard import KeyEvent
from pagemark.model import CursorPosition, TextModel
from pagemark.view import render_paragraph
from pagemark.session import SessionKeys, SessionManager
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


@pytest.mark.parametrize("reverse", [False, True])
@pytest.mark.parametrize(
    "key_type,key,expected",
    [
        (KeyType.SPECIAL, "enter", ["a", "f"]),
        (KeyType.SPECIAL, "backspace", ["af"]),
        (KeyType.CTRL, "d", ["af"]),
    ],
)
def test_bug28_multiline_selection_and_undo(editor, reverse, key_type, key, expected):
    editor.model = TextModel(editor.view, ["abc", "def"])
    editor.model.styles = [[1, 1, 1], [2, 2, 2]]
    start, end = CursorPosition(0, 1), CursorPosition(1, 2)
    editor.model.selection_start, editor.model.selection_end = (
        (end, start) if reverse else (start, end)
    )
    cp = editor.model.selection_end
    editor.model.cursor_position = CursorPosition(
        cp.paragraph_index, cp.character_index
    )
    editor.view.render()
    press(editor, key_type, key)
    assert editor.model.paragraphs == expected
    assert editor.model.styles == ([[1], [2]] if key == "enter" else [[1, 2]])
    assert editor.model.selection_start is None
    press(editor, KeyType.CTRL, "z")
    assert editor.model.paragraphs == ["abc", "def"]
    assert editor.model.styles == [[1, 1, 1], [2, 2, 2]]


@pytest.mark.parametrize(
    "key_type,key,expected",
    [
        (KeyType.SPECIAL, "enter", ["a", "bc"]),
        (KeyType.SPECIAL, "backspace", ["bc"]),
        (KeyType.CTRL, "d", ["ac"]),
    ],
)
def test_bug28_empty_selection_uses_normal_edit(editor, key_type, key, expected):
    set_text(editor, "abc")
    editor.model.cursor_position = CursorPosition(0, 1)
    editor.model.start_selection()
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


def test_bug29_first_save_persists_existing_preferences(editor, tmp_path):
    from pagemark.settings_persistence import get_persistence

    path = str(tmp_path / "new.txt")
    editor.session.set(SessionKeys.DOUBLE_SPACING, True)
    assert editor.save_file(path)
    assert get_persistence().load_settings(path)[SessionKeys.DOUBLE_SPACING] is True


def test_bug29_save_as_moves_settings_association(editor, tmp_path):
    from pagemark.settings_persistence import get_persistence

    old = str(tmp_path / "old.txt")
    new = str(tmp_path / "new.txt")
    editor.session.set(SessionKeys.DOUBLE_SPACING, True)
    assert editor.save_file(old)
    assert editor.save_file(new)
    editor.session.set(SessionKeys.DOUBLE_SPACING, False)
    persistence = get_persistence()
    assert persistence.load_settings(old)[SessionKeys.DOUBLE_SPACING] is True
    assert persistence.load_settings(new)[SessionKeys.DOUBLE_SPACING] is False


def test_bug29_failed_save_keeps_settings_association(editor, tmp_path):
    old = str(tmp_path / "old.txt")
    assert editor.save_file(old)
    assert not editor.save_file(str(tmp_path / "missing" / "new.txt"))
    assert editor.session._document_path == old


@pytest.mark.parametrize("text", ["界x", "e\u0301x"])
def test_bug30_cursor_uses_terminal_cell_width(editor, text):
    press(editor, KeyType.REGULAR, text)
    assert editor.view.visual_cursor_x == wcswidth(text)


@pytest.mark.parametrize("text", ["界" * 40, "e\u0301" * 80, "—" * 40, "✈\ufe0f" * 40])
def test_bug30_wrap_preserves_display_units(text):
    from pagemark.view import get_line_mapper

    mapper = get_line_mapper(text, 65)
    assert all(wcswidth(line) <= 65 for line in mapper.lines)
    assert "".join(mapper.lines) == text.replace("—", "--")
    assert mapper.cumulative_counts[-1] == len(text)
    for line in mapper.lines:
        assert not line.startswith(("\u0301", "\ufe0f"))


def test_bug30_vertical_navigation_preserves_cell_column(editor):
    editor.model = TextModel(editor.view, ["界X", "abc", "e\u0301XY"])
    editor.model.cursor_position = CursorPosition(0, 2)
    editor.view.render()
    editor.view.update_desired_x()
    press(editor, KeyType.SPECIAL, "down")
    assert editor.model.cursor_position == CursorPosition(1, 3)
    press(editor, KeyType.SPECIAL, "down")
    assert editor.model.cursor_position == CursorPosition(2, 4)
    assert editor.view.visual_cursor_x == 3


@pytest.mark.parametrize("text,column", [("界X", 2), ("e\u0301X", 1), ("✈\ufe0fX", 2)])
def test_bug30_terminal_styles_and_selection_use_matching_coordinates(
    editor, text, column
):
    import blessed
    import pyte
    from pagemark.terminal import TerminalInterface

    set_text(editor, text)
    editor.model.styles = [[0] * (len(text) - 1) + [1]]
    editor.model.selection_start = CursorPosition(0, len(text) - 1)
    editor.model.selection_end = CursorPosition(0, len(text))
    editor.view.render()
    selection = editor.view.get_selection_ranges()[0]
    assert selection == (column, column + 1)
    terminal = TerminalInterface(
        blessed.Terminal(kind="xterm-256color", force_styling=True)
    )
    output = terminal._compose_display_line(
        editor.view.lines[0], 10, selection, editor.view.line_styles[0]
    )
    assert wcswidth(terminal.term.strip_seqs(output)) == 10
    screen = pyte.Screen(20, 2)
    pyte.Stream(screen).feed(output)
    # pyte 0.8 does not implement variation-selector width changes.
    if "\ufe0f" not in text:
        char = screen.buffer[0][column]
        assert char.data == "X" and char.bold and char.reverse


def test_bug30_terminal_clipping_keeps_combining_marks():
    import blessed
    from pagemark.terminal import TerminalInterface

    terminal = TerminalInterface(
        blessed.Terminal(kind="xterm-256color", force_styling=True)
    )
    assert terminal._compose_display_line("e\u0301X", 1, None) == "e\u0301"
    assert terminal._compose_display_line("界X", 1, None) == " "


def test_existing_bug5_undo_to_saved_content_clears_modified(editor, tmp_path):
    path = tmp_path / "saved.txt"
    set_text(editor, "saved")
    assert editor.save_file(str(path))
    press(editor, KeyType.REGULAR, "x")
    press(editor, KeyType.CTRL, "z")
    assert editor.model.to_overstrike_text() == path.read_text(encoding="utf-8")
    assert editor.modified is False


def test_bug5_style_undo_redo_and_save_baseline(editor, tmp_path):
    path = str(tmp_path / "styled.txt")
    set_text(editor, "saved")
    assert editor.save_file(path)
    select_all(editor)
    press(editor, KeyType.CTRL, "b")
    assert editor.modified
    press(editor, KeyType.CTRL, "z")
    assert not editor.modified
    press(editor, KeyType.CTRL, "y")
    assert editor.modified
    assert editor.save_file(path)
    press(editor, KeyType.CTRL, "z")
    assert editor.modified
    press(editor, KeyType.CTRL, "y")
    assert not editor.modified


def test_bug5_editing_back_to_saved_state_removes_stale_swap(editor, tmp_path):
    from pagemark.autosave import get_swap_path, write_swap_file

    path = str(tmp_path / "saved.txt")
    assert editor.save_file(path)
    press(editor, KeyType.REGULAR, "x")
    assert write_swap_file(path, "x")
    press(editor, KeyType.SPECIAL, "backspace")
    assert not editor.modified
    assert not Path(get_swap_path(path)).exists()
    press(editor, KeyType.CTRL, "z")
    assert editor.modified


def test_bug5_recovery_is_dirty_until_saved(editor, tmp_path):
    path = str(tmp_path / "recovered.txt")
    editor.load_from_content(path, "recovered")
    press(editor, KeyType.REGULAR, "x")
    press(editor, KeyType.CTRL, "z")
    assert editor.modified
    assert editor.save_file(path)
    press(editor, KeyType.CTRL, "y")
    assert editor.modified
    press(editor, KeyType.CTRL, "z")
    assert not editor.modified


def test_bug5_failed_save_does_not_move_clean_baseline(editor, tmp_path):
    set_text(editor, "saved")
    assert editor.save_file(str(tmp_path / "saved.txt"))
    press(editor, KeyType.REGULAR, "x")
    assert not editor.save_file(str(tmp_path / "missing" / "file.txt"))
    assert editor.modified
    press(editor, KeyType.CTRL, "z")
    assert not editor.modified


def test_existing_bug6_word_fitting_exactly_does_not_wrap():
    text = "a " + "b" * 63
    assert len(text) == 65
    lines, _ = render_paragraph(text, 65)
    assert lines == [text, ""]  # Empty continuation is for the cursor.


def test_bug6_full_line_cursor_navigation_and_following_paragraph(editor):
    text = "a " + "b" * 63
    editor.model = TextModel(editor.view, [text, "next"])
    editor.model.cursor_position = CursorPosition(0, len(text))
    editor.view.render()
    editor.view.update_desired_x()
    assert editor.view.lines[:3] == [text, "", "next"]
    assert (editor.view.visual_cursor_y, editor.view.visual_cursor_x) == (1, 0)
    press(editor, KeyType.SPECIAL, "left")
    assert (editor.view.visual_cursor_y, editor.view.visual_cursor_x) == (0, 64)
    press(editor, KeyType.SPECIAL, "down")
    assert editor.model.cursor_position == CursorPosition(0, 65)
    assert editor.view.visual_cursor_y == 1
    press(editor, KeyType.SPECIAL, "down")
    assert editor.model.cursor_position.paragraph_index == 1


def test_bug6_exact_fit_before_more_words_does_not_add_blank_line():
    text = "a " + "b" * 63 + " next"
    lines, counts = render_paragraph(text, 65)
    assert lines == [text[:65], "next"]
    assert counts == [66, len(text)]

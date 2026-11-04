"""Editor and terminal regressions for BUG-31 through BUG-39.

Core behavior is real; only terminal dimensions, settings persistence, and
clipboard I/O are isolated. Terminal tests run on temporary documents.
"""

import os
from types import SimpleNamespace

import pytest

from pagemark.clipboard import ClipboardManager
from pagemark.editor import Editor
from pagemark.model import CursorPosition, TextModel
from pagemark.session import SessionManager
from pagemark.text_layout import display_width
from pagemark.view import get_line_mapper


@pytest.fixture
def editor(monkeypatch):
    monkeypatch.setattr(SessionManager, "_instance", None)
    monkeypatch.setattr(
        "pagemark.editor.TerminalInterface",
        lambda: SimpleNamespace(height=24, width=80),
    )
    instance = Editor()
    instance.session.set_persistence_enabled(False)
    instance.view.render()
    try:
        yield instance
    finally:
        os.close(instance._resize_pipe_r)
        os.close(instance._resize_pipe_w)


def document(editor, paragraphs):
    editor.model = TextModel(editor.view, paragraphs)
    editor.view.render()
    editor.view.update_desired_x()


def press(editor, token, count=1):
    for _ in range(count):
        editor._handle_key_event(editor.keyboard.parse_key(token))


@pytest.mark.parametrize("action", ["<BACKSPACE>", "X", "<ENTER>", "<Ctrl-x>"])
def test_bug31_delete_scrolled_selection_does_not_crash(editor, monkeypatch, action):
    document(editor, ["abc"] * 40)
    monkeypatch.setattr(ClipboardManager, "copy_text", lambda *args: None)
    press(editor, "<Shift-DOWN>", 39)
    assert editor.view.start_paragraph_index > 0
    assert editor.model.selection_start == CursorPosition(0, 0)
    assert editor.model.selection_end == CursorPosition(39, 0)
    press(editor, action)
    assert len(editor.model.paragraphs) == (2 if action == "<ENTER>" else 1)
    assert editor.undo.can_undo()


def test_bug31_undo_scrolled_multiline_paste_does_not_crash(editor, monkeypatch):
    document(editor, [""])
    monkeypatch.setattr(
        ClipboardManager, "paste_text", lambda: ("\n".join(["abc"] * 40), None)
    )
    press(editor, "<Ctrl-v>")
    assert editor.view.start_paragraph_index > 0
    press(editor, "<Ctrl-z>")
    assert editor.model.paragraphs == [""]
    assert editor.view.start_paragraph_index == 0


def test_bug32_exact_fit_cursor_row_matches_its_document_line(editor):
    text = "a " + "b" * 63 + " next"
    document(editor, [text, "last"])
    press(editor, "<RIGHT>", 65)
    mapper = get_line_mapper(text, 65)
    assert mapper.lines == [text[:65], "next"]
    assert editor.model.cursor_position == CursorPosition(0, 65)
    assert editor.view.visual_cursor_y == mapper.line_for_char_index(65)


def test_bug32_right_across_separator_changes_visible_position(editor):
    document(editor, ["a " + "b" * 63 + " next", "last"])
    press(editor, "<RIGHT>", 65)
    before = (editor.view.visual_cursor_y, editor.view.visual_cursor_x)
    press(editor, "<RIGHT>")
    assert editor.model.cursor_position == CursorPosition(0, 66)
    assert (editor.view.visual_cursor_y, editor.view.visual_cursor_x) != before


def test_bug32_down_visits_the_next_wrapped_line(editor):
    document(editor, ["a " + "b" * 63 + " next", "last"])
    press(editor, "<RIGHT>", 65)
    press(editor, "<DOWN>")
    assert editor.model.cursor_position.paragraph_index == 0
    assert editor.model.cursor_position.character_index >= 66


@pytest.mark.parametrize(
    "rows,top,cursor,expected_top", [(4, 54, 57, 53), (24, 54, 77, 33)]
)
def test_bug33_page_up_accounts_for_page_marker_rows(
    editor, rows, top, cursor, expected_top
):
    editor.view.num_rows = rows
    document(editor, [f"row{i:03}" for i in range(100)])
    # Reproduce a viewport with its cursor at the last visible row. This is
    # also reachable by normal Down presses; the PTY test below does so.
    editor.view.start_paragraph_index = top
    editor.model.cursor_position = CursorPosition(cursor, 0)
    editor.view.render()
    press(editor, "<PAGEUP>")
    assert editor.view.start_paragraph_index == expected_top


@pytest.mark.parametrize("shift", [True, False])
def test_bug34_vertical_selection_preserves_desired_column(editor, shift):
    document(editor, ["abcdefghij", "x", "abcdefghij"])
    press(editor, "<RIGHT>", 8)
    press(editor, "<Shift-DOWN>" if shift else "<DOWN>", 2)
    assert editor.model.cursor_position == CursorPosition(2, 8)


@pytest.mark.parametrize(
    "action,expected_column", [("search", 7), ("undo", 3), ("redo", 4)]
)
def test_bug35_vertical_move_uses_column_restored_by_search_or_history(
    editor, action, expected_column
):
    document(editor, ["abcdefghij", "0123456789"])
    if action == "search":
        press(editor, "<Ctrl-f>")
        press(editor, "h")
        press(editor, "<ENTER>")
    else:
        press(editor, "<RIGHT>", 3)
        press(editor, "X")
        if action == "undo":
            press(editor, "<Ctrl-z>")
        else:
            press(editor, "<Ctrl-z>")
            press(editor, "<HOME>")
            press(editor, "<Ctrl-y>")
    assert editor.view.visual_cursor_x == expected_column
    press(editor, "<DOWN>")
    assert editor.model.cursor_position == CursorPosition(1, expected_column)


@pytest.mark.parametrize("source_style,target_style", [(1, 0), (0, 2)])
@pytest.mark.parametrize(
    "movement,target_paragraph", [("<DOWN>", 1), ("<PAGEDOWN>", 2)]
)
def test_bug36_vertical_movement_inherits_target_text_style(
    editor, source_style, target_style, movement, target_paragraph
):
    editor.view.num_rows = 4
    document(editor, ["abcd"] * 6)
    editor.model.styles = [[source_style] * 4] + [[target_style] * 4 for _ in range(5)]
    # Moving right establishes the source paragraph's insertion style.
    press(editor, "<RIGHT>")
    press(editor, movement)
    assert editor.model.cursor_position == CursorPosition(target_paragraph, 1)
    press(editor, "Q")
    assert editor.model.paragraphs[target_paragraph] == "aQbcd"
    assert editor.model.styles[target_paragraph][1] == target_style


def test_bug37_literal_page_text_is_an_editable_content_row(editor):
    document(editor, ["abc", "─ Page 2 ─", "xyz"])
    press(editor, "<DOWN>")
    assert editor.model.cursor_position == CursorPosition(1, 0)
    assert editor.view.visual_cursor_y == 1


def test_bug37_literal_page_text_does_not_shift_selection(editor):
    document(editor, ["abc", "─ Page 2 ─", "xyz"])
    press(editor, "<END>")
    press(editor, "<Shift-LEFT>", 3)
    assert editor.model.get_selected_text() == "xyz"
    assert editor.view.get_selection_ranges() == [None, None, (0, 3)]


@pytest.mark.parametrize("text", ["—" * 40, "界" * 40, "e\u0301" * 40])
def test_bug38_centering_uses_display_width(editor, text):
    document(editor, [text])
    width = display_width(text)
    before = editor._snapshot_state()
    result = editor.model.center_line()
    if width >= editor.view.num_columns:
        assert result is False
        assert editor._snapshot_state() == before
    else:
        assert result is True
        assert editor.model.paragraphs == [" " * ((65 - width) // 2) + text]


@pytest.mark.parametrize("reverse", [True, False])
def test_bug39_tab_replaces_selection_using_insertion_column(editor, reverse):
    document(editor, ["abcdef"])
    if reverse:
        press(editor, "<RIGHT>", 3)
    press(editor, "<Shift-LEFT>" if reverse else "<Shift-RIGHT>", 3)
    assert editor.model.get_selected_text() == "abc"
    press(editor, "<TAB>")
    assert editor.model.paragraphs == ["     def"]
    assert editor.view.visual_cursor_x == 5


def test_bug31_real_terminal_selection_deletion_stays_running(tmp_path):
    from terminal_harness import TerminalHarness

    path = tmp_path / "selection.txt"
    path.write_text("\n".join(["abc"] * 40), encoding="utf-8")
    with TerminalHarness(rows=24, cols=80) as terminal:
        terminal.start(str(path))
        assert terminal.wait_ready()
        terminal.press("shift-down", count=39)
        assert terminal.wait_stable()
        terminal.press("backspace")
        assert terminal.wait_stable()
        assert terminal._process.poll() is None, terminal.screen_text()


def test_bug33_real_terminal_page_up_changes_viewport(tmp_path):
    from terminal_harness import TerminalHarness

    path = tmp_path / "pages.txt"
    path.write_text("\n".join(f"row{i:03}" for i in range(100)), encoding="utf-8")
    # Five physical rows leave four editor rows and one status row.
    with TerminalHarness(rows=5, cols=80) as terminal:
        terminal.start(str(path))
        assert terminal.wait_ready()
        terminal.press("down", count=57)
        assert terminal.wait_stable()
        before = terminal.get_line(0).strip()
        assert before == "row054"
        terminal.press("page_up")
        assert terminal.wait_stable()
        assert terminal.get_line(0).strip() != before


def test_edit_and_history_publish_only_complete_frames(editor, monkeypatch):
    document(editor, ["abc"] * 40)
    press(editor, "<Shift-DOWN>", 39)
    frames = []
    render = editor.view.render

    def observe():
        frames.append(
            (
                tuple(editor.model.paragraphs),
                editor.undo.can_undo(),
                editor.undo.can_redo(),
            )
        )
        render()

    monkeypatch.setattr(editor.view, "render", observe)
    press(editor, "X")
    assert frames == [(("Xabc",), True, False)]
    assert editor.modified
    frames.clear()
    press(editor, "<Ctrl-z>")
    assert frames == [(("abc",) * 40, False, True)]
    frames.clear()
    press(editor, "<Ctrl-y>")
    assert frames == [(("Xabc",), True, False)]


def test_clipboard_read_failure_preserves_selection_and_document(editor, monkeypatch):
    document(editor, ["abc"])
    press(editor, "<Shift-RIGHT>", 2)
    before = editor._snapshot_state()

    def fail():
        raise RuntimeError("Clipboard unavailable")

    monkeypatch.setattr(ClipboardManager, "paste_text", fail)
    with pytest.raises(RuntimeError, match="Clipboard unavailable"):
        press(editor, "<Ctrl-v>")
    assert editor._snapshot_state() == before
    assert not editor.undo.can_undo()


@pytest.mark.parametrize("reverse", [False, True])
def test_tab_replacement_across_wrapped_and_styled_paragraphs(editor, reverse):
    document(editor, ["a" * 80, "end"])
    editor.model.styles = [[1] * 80, [2] * 3]
    editor.model.selection_start = CursorPosition(0, 68)
    editor.model.selection_end = CursorPosition(1, 1)
    if reverse:
        editor.model.selection_start, editor.model.selection_end = (
            editor.model.selection_end,
            editor.model.selection_start,
        )
    editor.model.cursor_position = editor.model.selection_end
    editor.view.render()
    editor.model.caret_style = 3
    press(editor, "<TAB>")
    assert editor.model.paragraphs == ["a" * 68 + "  nd"]
    assert editor.model.styles == [[1] * 68 + [3, 3, 2, 2]]
    assert editor.model.cursor_position == CursorPosition(0, 70)

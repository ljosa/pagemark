"""Native clipboard actions use the platform backend without touching the pasteboard."""
from types import SimpleNamespace

import pytest

F = pytest.importorskip("Foundation")
pytest.importorskip("AppKit")

from pagemark_app import native_editor  # noqa: E402
from pagemark_app.codec import StyledText  # noqa: E402
from pagemark_app.display_preferences import DisplayPreferences  # noqa: E402
from pagemark_app.session import EditorSession  # noqa: E402
from test_display_preferences import MemoryDefaults  # noqa: E402


@pytest.fixture
def editor(monkeypatch):
    preferences = DisplayPreferences(MemoryDefaults())
    monkeypatch.setattr(native_editor, "display_preferences", lambda: preferences)
    changes, errors, copied = [], [], []
    session = EditorSession(StyledText("ab\ncd", (1, 2, 0, 3, 0)),
                            on_change=lambda before, after: changes.append((before, after)))
    document = SimpleNamespace(session=session, report_error=errors.append)
    view = native_editor.PagemarkEditorView.alloc().initWithFrame_(F.NSMakeRect(0, 0, 800, 600))
    view.configure(document)
    session.select(1, 4)
    monkeypatch.setattr(native_editor.ClipboardManager, "copy_text",
                        staticmethod(lambda text, styles: copied.append((text, styles))))
    yield view, changes, errors, copied
    view.teardown()


@pytest.mark.parametrize("command", ["copy", "cut"])
@pytest.mark.parametrize("route", ["menu", "shortcut"])
def test_copy_and_cut_preserve_selected_styles(editor, command, route):
    view, changes, errors, copied = editor
    before = view.session.snapshot()
    if route == "menu":
        getattr(view, command + "_")(None)
    else:
        view.execute(command)
    assert not errors
    assert copied == [("b\nc", [[2], [3]])]
    if command == "copy":
        assert view.session.snapshot() == before
        assert not changes
    else:
        assert view.session.value == StyledText("ad", (1, 0))
        assert len(changes) == 1
        assert changes[0] == (before, view.session.snapshot())


@pytest.mark.parametrize("command", ["copy", "cut"])
def test_empty_selection_does_not_write_clipboard(editor, command):
    view, changes, errors, copied = editor
    view.session.select(1, 1)
    before = view.session.snapshot()
    view.execute(command)
    assert view.session.snapshot() == before
    assert not copied and not changes and not errors


def test_failed_cut_keeps_text_selection_and_history(editor, monkeypatch):
    view, changes, errors, copied = editor
    before = view.session.snapshot()
    failure = RuntimeError("Clipboard unavailable")

    def fail(text, styles):
        raise failure

    monkeypatch.setattr(native_editor.ClipboardManager, "copy_text", staticmethod(fail))
    view.execute("cut")
    assert errors == [failure]
    assert view.session.snapshot() == before
    assert not changes and not copied

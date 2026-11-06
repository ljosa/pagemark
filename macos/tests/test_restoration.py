"""Real secure Cocoa archives and editor state restoration, without user state files."""
from dataclasses import replace
from types import SimpleNamespace

import pytest

A = pytest.importorskip("AppKit")
F = pytest.importorskip("Foundation")

from pagemark_app import application, native_editor  # noqa: E402
from pagemark_app.codec import StyledText  # noqa: E402
from pagemark_app.display_preferences import DisplayPreferences, ViewMode  # noqa: E402
from pagemark_app.restoration import EditorRestorationState, PREFIX  # noqa: E402
from pagemark_app.session import EditorSession  # noqa: E402
from test_display_preferences import MemoryDefaults  # noqa: E402


def archive(write):
    coder = F.NSKeyedArchiver.alloc().initRequiringSecureCoding_(True)
    write(coder)
    coder.finishEncoding()
    reader, error = F.NSKeyedUnarchiver.alloc().initForReadingFromData_error_(coder.encodedData(), None)
    assert error is None
    reader.setRequiresSecureCoding_(True)
    return reader


@pytest.fixture
def editor(monkeypatch, tmp_path):
    preferences = DisplayPreferences(MemoryDefaults())
    monkeypatch.setattr(native_editor, "display_preferences", lambda: preferences)
    document = application.PagemarkDocument.alloc().init()
    path = tmp_path / "restoration.txt"
    path.write_text("hello 😀\n" * 100)
    document.setFileURL_(F.NSURL.fileURLWithPath_(str(path)))
    document.setFileType_("public.plain-text")
    text = "hello 😀\n" * 100
    document.session = EditorSession(StyledText(text, (0,) * len(text)))
    view = native_editor.PagemarkEditorView.alloc().initWithFrame_(F.NSMakeRect(0, 0, 800, 600))
    view.configure(document)
    document.editor = view
    yield document, view, preferences
    F.NSObject.cancelPreviousPerformRequestsWithTarget_(document)
    view.teardown()
    document.editor = None


def test_document_hooks_roundtrip_secure_editor_state(editor):
    document, view, preferences = editor
    view.session.select(18, 2)  # Preserve selection direction as well as extent.
    view.session.model.caret_style = 3
    view.view_mode = ViewMode.DRAFT
    view._zoom_levels = {False: 1.5, True: 2.0}
    view.double_spacing = True
    expected = EditorRestorationState.capture(view)
    before = view.session.snapshot()
    def encode_background(coder):
        queue = F.NSOperationQueue.alloc().init()
        document.encodeRestorableStateWithCoder_backgroundQueue_(coder, queue)
        queue.waitUntilAllOperationsAreFinished()
    reader = archive(encode_background)
    assert EditorRestorationState.decode(reader) == expected
    view.session.select(0, 0)
    view.view_mode = ViewMode.CONTINUOUS
    document.restoreStateWithCoder_(reader)
    document.restoreEditorState_(None)
    assert EditorRestorationState.capture(view) == expected
    assert view.session.snapshot() == before
    assert preferences.defaults.values == {}
    assert not document.isDocumentEdited()
    assert not document.undoManager().canUndo()
    assert not type(document).autosavesInPlace()
    assert not type(document).autosavesDrafts()
    reader.finishDecoding()


def test_corrupt_or_stale_ui_values_are_bounded_without_editing_text(editor):
    document, view, preferences = editor
    before = view.session.value
    state = EditorRestorationState(-100, 10**9, 255, 999, float("nan"), float("inf"), False,
                                   float("nan"), float("inf"))
    state.apply(view)
    assert view.session.selection == (0, len(before.text))
    assert view.session.value == before
    assert view.view_mode == ViewMode.CONTINUOUS
    assert view._zoom_levels == {False: 1.25, True: 1.25}
    assert view.session.model.caret_style == 3
    assert not document.isDocumentEdited()


@pytest.mark.parametrize("version", [None, 0, 2])
def test_unknown_state_versions_are_ignored(version):
    reader = archive(lambda coder: coder.encodeInteger_forKey_(version, PREFIX + "version")
                     if version is not None else None)
    assert EditorRestorationState.decode(reader) is None
    reader.finishDecoding()


def test_scroll_restoration_waits_for_layout_and_clamps_to_clip_bounds(editor, monkeypatch):
    document, view, preferences = editor
    events = []
    clip = SimpleNamespace(
        bounds=lambda: F.NSMakeRect(0, 0, 800, 600),
        constrainBoundsRect_=lambda rect: F.NSMakeRect(min(rect.origin.x, 100),
                                                       min(rect.origin.y, 500), 800, 600),
        scrollToPoint_=lambda point: events.append(tuple(point)))
    scroll = SimpleNamespace(contentView=lambda: clip,
                             reflectScrolledClipView_=lambda clip: events.append("reflected"))
    monkeypatch.setattr(view, "enclosingScrollView", lambda: scroll)
    monkeypatch.setattr(view, "refresh", lambda reveal: events.append(("layout", reveal)))
    state = replace(EditorRestorationState.capture(view), scroll_x=1000, scroll_y=1000)
    state.apply(view)
    assert events == [("layout", False), (100.0, 500.0), "reflected"]


def test_secure_restoration_opt_in_and_scroll_invalidation(editor, monkeypatch):
    document, view, preferences = editor
    delegate = application.PagemarkDelegate.alloc().init()
    assert delegate.applicationSupportsSecureRestorableState_(None)
    assert delegate.application_shouldSaveApplicationState_(None, None)
    assert delegate.application_shouldRestoreApplicationState_(None, None)
    calls = []
    monkeypatch.setattr(document, "invalidateRestorableState", lambda: calls.append(True))
    view.viewportScrolled_(None)
    view.refresh(reveal=False)
    assert calls == [True, True]

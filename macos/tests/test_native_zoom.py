"""Native zoom dispatch preserves editing, composition, output and preferences."""
from types import SimpleNamespace

import pytest

A = pytest.importorskip("AppKit")
F = pytest.importorskip("Foundation")

from pagemark_app import application, native_editor  # noqa: E402
from pagemark_app.display_preferences import DisplayPreferences, ViewMode  # noqa: E402
from pagemark_app.native_editor import PagemarkEditorView  # noqa: E402
from pagemark_app.zoom import MAX_ZOOM, MIN_ZOOM  # noqa: E402
from test_display_preferences import MemoryDefaults  # noqa: E402
from test_key_bindings import ShortcutMenuApplication  # noqa: E402


@pytest.fixture
def document_view(monkeypatch):
    preferences = DisplayPreferences(MemoryDefaults())
    monkeypatch.setattr(native_editor, "display_preferences", lambda: preferences)
    document = application.PagemarkDocument.alloc().init()
    manager = document.undoManager()
    manager.setGroupsByEvent_(False)
    manager.beginUndoGrouping()
    document.session.insert("first line\n" + "body " * 1000)
    manager.endUndoGrouping()
    document.session.select(2, 20)
    view = PagemarkEditorView.alloc().initWithFrame_(F.NSMakeRect(0, 0, 840, 692))
    view.configure(document)
    document.editor = view
    yield document, view, preferences
    document.clear_recovery()
    view.teardown()
    document.editor = None


def pdf_size(document):
    view = application.PDFPrintView.alloc().initWithFrame_(F.NSMakeRect(0, 0, 1, 1))
    view.configure(document.output_pdf())
    return tuple(view.page_size), view.pdf_rep.pageCount()


def test_zoom_across_views_preserves_layout_save_bytes_undo_and_print_size(document_view):
    document, view, preferences = document_view
    before = document.session.snapshot()
    layout = document.session.layout
    saved = bytes(document.dataOfType_error_("public.plain-text", None)[0])
    output = pdf_size(document)
    for mode in ViewMode:
        view.view_mode = mode
        view.refresh(reveal=False)
        for scale in (.5, .8, 1, 1.33, 2, 4, 5):
            view.set_zoom(scale)
            assert view.zoom == scale
            assert preferences.zoom_for(mode) == scale
            assert document.session.layout is layout
            assert document.session.snapshot() == before
            assert bytes(document.dataOfType_error_("public.plain-text", None)[0]) == saved
            assert document.isDocumentEdited()
            assert document.undoManager().canUndo() and not document.undoManager().canRedo()
        assert pdf_size(document) == output
    view.view_mode = ViewMode.DRAFT
    view.set_zoom(1.75)
    view.view_mode = ViewMode.PAGES
    view.set_zoom(1.1)
    view.view_mode = ViewMode.CONTINUOUS
    assert view.zoom == 1.1
    view.view_mode = ViewMode.DRAFT
    assert view.zoom == 1.75
    document.undoManager().undo()
    assert document.session.value.text == ""
    document.undoManager().redo()
    assert document.session.value == before.value


@pytest.mark.parametrize("end_phase", [A.NSEventPhaseEnded, A.NSEventPhaseCancelled])
def test_pinch_and_keyboard_zoom_preserve_marked_text_and_defer_pinch_preference_writes(document_view, end_phase):
    document, view, preferences = document_view
    missing = F.NSMakeRange(F.NSNotFound, 0)
    view.setMarkedText_selectedRange_replacementRange_("é", F.NSMakeRange(2, 0), missing)
    before = document.session.snapshot()
    marked, composition = view.marked, view.composition_before
    view.execute("zoom_reset")
    assert view.zoom == 1
    view.execute("zoom_in")
    assert view.zoom == 1.1
    view.execute("zoom_out")
    assert view.zoom == 1

    def pinch(delta, phase):
        view.magnifyWithEvent_(SimpleNamespace(magnification=lambda: delta, phase=lambda: phase,
                                              locationInWindow=lambda: F.NSMakePoint(200, 200)))

    pinch(.2, A.NSEventPhaseBegan)
    pinch(.25, A.NSEventPhaseChanged)
    assert view.zoom == 1.5
    assert preferences.zoom_for(view.view_mode) == 1
    pinch(0, end_phase)
    assert preferences.zoom_for(view.view_mode) == 1.5
    assert (view.marked, view.composition_before) == (marked, composition)
    assert document.session.snapshot() == before
    manager = document.undoManager()
    manager.beginUndoGrouping()
    view.unmarkText()
    manager.endUndoGrouping()
    manager.undo()
    assert document.session.snapshot() == composition


def test_zoom_menu_routes_to_document_and_disables_unavailable_actions(document_view, monkeypatch):
    document, view, _ = document_view
    app = ShortcutMenuApplication.alloc().init()
    delegate = application.PagemarkDelegate.alloc().init()
    application.configure_menu(app, delegate)
    menu = app.menu.itemWithTitle_("View").submenu()
    current, key_window = [document], [None]
    monkeypatch.setattr(A, "NSDocumentController", SimpleNamespace(sharedDocumentController=lambda:
        SimpleNamespace(currentDocument=lambda: current[0])))
    monkeypatch.setattr(A, "NSApp", SimpleNamespace(keyWindow=lambda: key_window[0]))
    for title, key, expected in (("Zoom In", "+", 1.5), ("Zoom Out", "-", 1.25),
                                  ("Actual Size", "0", 1)):
        item = menu.itemWithTitle_(title)
        assert item.keyEquivalent() == key
        assert item.keyEquivalentModifierMask() == A.NSEventModifierFlagCommand
        assert delegate.validateMenuItem_(item)
        delegate.performSelector_withObject_("zoomView:", item)
        assert view.zoom == expected
    for level, disabled_title in ((MAX_ZOOM, "Zoom In"), (MIN_ZOOM, "Zoom Out"), (1, "Actual Size")):
        view.set_zoom(level)
        assert not delegate.validateMenuItem_(menu.itemWithTitle_(disabled_title))
    key_window[0] = object()
    assert not delegate.validateMenuItem_(menu.itemWithTitle_("Zoom In"))
    current[0] = None
    assert not delegate.validateMenuItem_(menu.itemWithTitle_("Zoom In"))

"""Native fit adapters keep frame changes and zoom changes independent."""
from types import SimpleNamespace

import pytest

A = pytest.importorskip("AppKit")
F = pytest.importorskip("Foundation")

from pagemark_app import application  # noqa: E402
from pagemark_app.display_preferences import ViewMode  # noqa: E402
from pagemark_app.geometry import EditorGeometry  # noqa: E402
from pagemark_app.native_fitting import fit_width, rect_values, resize_window_to_fit  # noqa: E402
from test_key_bindings import ShortcutMenuApplication  # noqa: E402
from test_native_zoom import document_view as shared_document_view, pdf_size  # noqa: E402

document_view = shared_document_view


@pytest.mark.parametrize("mode", list(ViewMode))
def test_fit_width_with_real_font_metrics_preserves_document_composition_and_print(document_view, mode):
    document, editor, preferences = document_view
    editor.view_mode = mode
    editor.zoom = 2
    editor.setFrameSize_((840, 692))
    editor.refresh(reveal=False)
    output = pdf_size(document)
    missing = F.NSMakeRange(F.NSNotFound, 0)
    editor.setMarkedText_selectedRange_replacementRange_("é", F.NSMakeRange(2, 0), missing)
    # Marked-text refresh has no clip view in this headless fixture. Supply the
    # intended viewport again; the production app obtains it from NSScrollView.
    editor.setFrameSize_((840, 692))
    editor.refresh(reveal=False)
    before = document.session.snapshot()
    marked, composition, layout = editor.marked, editor.composition_before, document.session.layout
    fit_width(editor)
    assert 0 <= 840 - editor.geometry.natural_width <= 2
    assert preferences.zoom_for(mode) == editor.zoom
    assert document.session.snapshot() == before
    assert (editor.marked, editor.composition_before) == (marked, composition)
    assert document.session.layout is layout
    manager = document.undoManager()
    manager.beginUndoGrouping()
    editor.unmarkText()
    manager.endUndoGrouping()
    manager.undo()
    assert document.session.snapshot() == composition
    assert pdf_size(document) == output


class FitWindow:
    """Only the WindowServer boundary is replaced; sizing uses production code."""
    def __init__(self, chrome_changes=False):
        self.rect = F.NSMakeRect(1000, 60, 600, 720)
        self.style = A.NSWindowStyleMaskResizable | A.NSWindowStyleMaskTitled
        self.frames = []
        self.chrome_changes = chrome_changes

    def frame(self):
        return self.rect

    def styleMask(self):
        return self.style

    def screen(self):
        return SimpleNamespace(visibleFrame=lambda: F.NSMakeRect(0, 0, 1600, 1000))

    def minSize(self):
        return F.NSMakeSize(480, 320)

    def maxSize(self):
        return F.NSMakeSize(3000, 3000)

    def setFrame_display_(self, rect, display):
        self.rect = rect
        self.frames.append(rect_values(rect))

    def content_width(self):
        # Simulate an autohiding scroller disappearing after the first resize.
        chrome = 4 if self.chrome_changes and self.frames else 19
        return self.rect.size.width - chrome


class FitEditor:
    def __init__(self, window, zoom=1.25):
        self.host = window
        self.scroll = SimpleNamespace(contentSize=lambda: F.NSMakeSize(window.content_width(), 692),
                                      tile=lambda: None)
        self.zoom = zoom
        self.saved_zoom = None
        self.refresh(reveal=False)

    def window(self):
        return self.host

    def enclosingScrollView(self):
        return self.scroll

    def refresh(self, *, reveal):
        assert not reveal
        self.geometry = EditorGeometry(150, self.scroll.contentSize().width, pages=True, zoom=self.zoom)

    def set_zoom(self, value, *, persist):
        self.zoom = value
        self.refresh(reveal=False)

    def remember_zoom(self):
        self.saved_zoom = self.zoom


@pytest.mark.parametrize("zoom,expected_width", [(.5, 480), (1.25, 824), (5, 1600)])
def test_resize_window_accounts_for_chrome_and_limits_without_changing_zoom(zoom, expected_width):
    window = FitWindow()
    editor = FitEditor(window, zoom)
    resize_window_to_fit(editor)
    assert window.frame().size.width == expected_width
    assert window.frame().size.height == 720
    assert window.frame().origin.y == 60
    assert 0 <= window.frame().origin.x <= 1600 - expected_width
    assert editor.zoom == zoom and editor.saved_zoom is None
    before = list(window.frames)
    resize_window_to_fit(editor)
    assert window.frames == before


def test_resize_window_reconciles_autohiding_scrollbars():
    window = FitWindow(chrome_changes=True)
    editor = FitEditor(window)
    resize_window_to_fit(editor)
    assert window.frame().size.width == 809
    assert window.frame().origin.x == 1600 - 809
    assert editor.scroll.contentSize().width == editor.geometry.natural_width
    assert len(window.frames) == 2


def test_fit_menu_routes_actions_and_respects_fullscreen_and_active_window(monkeypatch):
    app = ShortcutMenuApplication.alloc().init()
    delegate = application.PagemarkDelegate.alloc().init()
    application.configure_menu(app, delegate)
    menu = app.menu.itemWithTitle_("View").submenu()
    fit = menu.itemWithTitle_("Fit Width")
    resize = menu.itemWithTitle_("Resize Window to Fit")
    window = FitWindow()
    editor = FitEditor(window)
    current, key_window = [SimpleNamespace(editor=editor)], [window]
    monkeypatch.setattr(A, "NSDocumentController", SimpleNamespace(sharedDocumentController=lambda:
        SimpleNamespace(currentDocument=lambda: current[0])))
    monkeypatch.setattr(A, "NSApp", SimpleNamespace(keyWindow=lambda: key_window[0]))
    assert fit.target() == resize.target() == delegate
    assert delegate.validateMenuItem_(fit) and delegate.validateMenuItem_(resize)
    delegate.performSelector_withObject_("fitWidth:", fit)
    assert not window.frames and editor.zoom != 1.25
    editor.set_zoom(1.5, persist=False)
    delegate.performSelector_withObject_("resizeWindowToFit:", resize)
    assert window.frames and editor.zoom == 1.5
    window.frames.clear()
    window.style |= A.NSWindowStyleMaskFullScreen
    assert delegate.validateMenuItem_(fit) and not delegate.validateMenuItem_(resize)
    delegate.performSelector_withObject_("resizeWindowToFit:", resize)
    assert not window.frames
    key_window[0] = object()
    assert not delegate.validateMenuItem_(fit) and not delegate.validateMenuItem_(resize)
    current[0] = None
    assert not delegate.validateMenuItem_(fit) and not delegate.validateMenuItem_(resize)

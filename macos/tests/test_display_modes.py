"""Exercise native screen fonts, selection geometry, menus and preference controls."""
from types import SimpleNamespace

import pytest

A = pytest.importorskip("AppKit")
F = pytest.importorskip("Foundation")
objc = pytest.importorskip("objc")

from pagemark_app import application, native_editor, native_preferences  # noqa: E402
from pagemark_app.codec import StyledText  # noqa: E402
from pagemark_app.display_preferences import Appearance, DisplayPreferences, DraftFont, ViewMode  # noqa: E402
from pagemark_app.native_editor import PagemarkEditorView  # noqa: E402
from pagemark_app.native_preferences import PreferencesController, apply_appearance  # noqa: E402
from pagemark_app.screen_fonts import draft_font  # noqa: E402
from pagemark_app.session import EditorSession  # noqa: E402
from test_display_preferences import MemoryDefaults  # noqa: E402


@pytest.fixture
def preferences(monkeypatch):
    preferences = DisplayPreferences(MemoryDefaults())
    for module in (application, native_editor, native_preferences):
        monkeypatch.setattr(module, "display_preferences", lambda: preferences)
    return preferences


@pytest.mark.parametrize("zoom,double", [(0.75, False), (1.5, False), (3, True)])
def test_draft_geometry_matches_font_for_clicks_caret_and_accessibility(preferences, zoom, double):
    preferences.view_mode = ViewMode.DRAFT
    preferences.draft_font = DraftFont("Menlo-Regular")
    preferences.set_zoom(ViewMode.DRAFT, zoom)
    text = "\n".join(["abc é 字 😀 end"] * 125)
    session = EditorSession(StyledText(text, (0,) * len(text)))
    view = PagemarkEditorView.alloc().initWithFrame_(F.NSMakeRect(0, 0, 840, 692))
    view.double_spacing = double
    view.configure(SimpleNamespace(session=session))
    try:
        geometry = view.geometry
        font = view.painter.fonts[0]
        assert font.fontName() == "Menlo-Regular"
        assert font.pointSize() == DraftFont.size * zoom
        assert geometry.cell_width == pytest.approx(F.NSString.stringWithString_("M").sizeWithAttributes_(
            {A.NSFontAttributeName: font}).width)
        for line in range(session.layout.line_count):
            row = session.layout.line_at(line)
            for offset, column in row.caret_stops:
                x, y = geometry.point(line, column)
                position = geometry.hit(session.layout, x, y + geometry.line_height / 2)
                assert (position.paragraph_index, position.character_index) == (line, offset)
        session.select(0, 0)
        caret = view.caret_rect()
        assert caret.size.height == geometry.ink_height
        frame = view.accessibilityFrameForRange_(F.NSMakeRange(0, 3))
        assert frame.origin == view.convertRect_toView_(caret, None).origin
        assert frame.size.width == pytest.approx(3 * geometry.cell_width)
        assert frame.size.height == caret.size.height
        assert geometry.page_count == (125 + geometry.rows_per_page - 1) // geometry.rows_per_page
    finally:
        view.teardown()


def test_modes_and_font_changes_preserve_document_layout_selection_undo_and_print(preferences):
    document = application.PagemarkDocument.alloc().init()
    view = PagemarkEditorView.alloc().initWithFrame_(F.NSMakeRect(0, 0, 840, 692))
    manager = document.undoManager()
    manager.setGroupsByEvent_(False)
    manager.beginUndoGrouping()
    document.session.insert("bold words\n" + "body " * 200)
    manager.endUndoGrouping()
    document.session.select(0, 4)
    view.configure(document)
    document.editor = view
    before = document.session.snapshot()
    layout = document.session.layout
    saved, error = document.dataOfType_error_("public.plain-text", None)
    assert error is None
    try:
        for mode in (ViewMode.PAGES, ViewMode.DRAFT, ViewMode.CONTINUOUS, ViewMode.DRAFT):
            view.view_mode = mode
            view.draft_font = DraftFont("Menlo-Regular", 24)
            view.refresh()
            assert document.session.snapshot() == before
            assert document.session.layout is layout
            assert manager.canUndo() and not manager.canRedo()
            assert document.isDocumentEdited()
            assert bytes(document.dataOfType_error_("public.plain-text", None)[0]) == bytes(saved)
            pdf = application.PDFPrintView.alloc().initWithFrame_(F.NSMakeRect(0, 0, 1, 1))
            pdf.configure(document.output_pdf())
            assert pdf.page_size == (612, 792)
            assert pdf.pdf_rep.pageCount() == view.geometry.page_count
            assert view.painter.fonts[0].fontName() == (
                "Menlo-Regular" if mode == ViewMode.DRAFT else "Courier")
        manager.undo()
        assert document.session.value.text == ""
        assert not document.isDocumentEdited()
        manager.redo()
        assert document.session.value == before.value
    finally:
        document.clear_recovery()
        view.teardown()
        document.editor = None


@pytest.mark.parametrize("name", ["Missing-Pagemark-Test-Font", "Helvetica"])
def test_draft_unavailable_or_proportional_font_uses_fixed_width_fallback(name):
    font = draft_font(DraftFont(name, 16))
    assert font.isFixedPitch()
    assert font.pointSize() == 16
    assert font.fontName() == "Menlo-Regular"


class DisplayMenuApplication(F.NSObject):
    def setWindowsMenu_(self, menu):
        self.windows = menu

    def setMainMenu_(self, menu):
        self.menu = menu

    def setAppearance_(self, appearance):
        self.appearance_override = appearance


class ValidationItem:
    """Capture checkmarks without AppKit loading menu images via WindowServer."""
    def __init__(self, item):
        self.item = item
        self.state = None

    def __getattr__(self, name):
        return getattr(self.item, name)

    def setState_(self, state):
        self.state = state


class PreferenceActionTestController(PreferencesController):
    @objc.python_method
    def make_window(self):
        # Exercise controller initialization without connecting to WindowServer.
        self.window_creation_requested = True
        return None


def test_view_menu_order_actions_checkmarks_persistence_and_system_appearance(preferences, monkeypatch):
    app = DisplayMenuApplication.alloc().init()
    delegate = application.PagemarkDelegate.alloc().init()
    application.configure_menu(app, delegate)
    menu = app.menu.itemWithTitle_("View").submenu()
    assert ["separator" if item.isSeparatorItem() else str(item.title())
            for item in menu.itemArray() if not item.isHidden()] == [
        "Continuous", "Pages", "Draft", "separator", "Light Mode", "Dark Mode", "System Default",
        "separator", "Zoom In", "Zoom Out", "Actual Size", "Fit Width", "Resize Window to Fit",
        "separator", "Enter Full Screen"]
    fullscreen = menu.itemWithTitle_("Enter Full Screen")
    assert fullscreen.target() is None and fullscreen.action() == "toggleFullScreen:"
    assert fullscreen.keyEquivalent() == "f"
    assert fullscreen.keyEquivalentModifierMask() == (
        A.NSEventModifierFlagCommand | A.NSEventModifierFlagControl)
    pref_item = app.menu.itemWithTitle_("Pagemark").submenu().itemWithTitle_("Preferences…")
    assert pref_item.keyEquivalent() == "," and pref_item.action() == "showPreferences:"
    current = [None]
    monkeypatch.setattr(A, "NSDocumentController", SimpleNamespace(
        sharedDocumentController=lambda: SimpleNamespace(currentDocument=lambda: current[0])))
    monkeypatch.setattr(A, "NSApp", app)
    assert not delegate.validateMenuItem_(menu.itemWithTitle_("Draft"))
    for title, name in (("Light Mode", A.NSAppearanceNameAqua),
                        ("Dark Mode", A.NSAppearanceNameDarkAqua), ("System Default", None)):
        item = menu.itemWithTitle_(title)
        delegate.performSelector_withObject_("changeAppearance:", item)
        assert (app.appearance_override.name() if app.appearance_override else None) == name
        for other in menu.itemArray()[4:7]:
            validation = ValidationItem(other)
            assert delegate.validateMenuItem_(validation)  # Works without a document.
            assert validation.state == int(other == item)
        # Apply the persisted choice as a newly launched app does.
        apply_appearance(app, preferences.appearance)
        assert (app.appearance_override.name() if app.appearance_override else None) == name
    current[0] = SimpleNamespace(editor=SimpleNamespace(view_mode=ViewMode.CONTINUOUS,
                                                       refresh=lambda: None))
    for selected in menu.itemArray()[:3]:
        delegate.performSelector_withObject_("changeView:", selected)
        assert preferences.view_mode == ViewMode(selected.tag())
        for item in menu.itemArray()[:3]:
            validation = ValidationItem(item)
            assert delegate.validateMenuItem_(validation)
            assert validation.state == int(item == selected)


def test_font_action_updates_existing_draft_views_without_changing_other_modes(preferences, monkeypatch):
    refreshed = []
    editors = [SimpleNamespace(view_mode=mode, draft_font=DraftFont(),
                               refresh=lambda mode=mode: refreshed.append(mode)) for mode in ViewMode]
    monkeypatch.setattr(A, "NSDocumentController", SimpleNamespace(sharedDocumentController=lambda:
        SimpleNamespace(documents=lambda: [SimpleNamespace(editor=e) for e in editors])))
    controller = PreferenceActionTestController.alloc().init()
    assert controller.window_creation_requested
    # Native popup controls need WindowServer and are covered by the signed
    # editor probe. Here the real Objective-C action receives their selections.
    family = A.NSMenuItem.alloc().initWithTitle_action_keyEquivalent_("Menlo", None, "")
    family.setRepresentedObject_("Menlo-Regular")
    controller.family = SimpleNamespace(selectedItem=lambda: family)
    controller.performSelector_withObject_("changeDraftFont:", None)
    assert preferences.draft_font == DraftFont("Menlo-Regular")
    assert all(editor.draft_font == preferences.draft_font for editor in editors)
    assert refreshed == [ViewMode.DRAFT]
    assert preferences.appearance == Appearance.SYSTEM

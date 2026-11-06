"""Open events from Finder and the system Recent menu share this delegate path."""
from types import SimpleNamespace
import sys
import time
import unicodedata

import pytest

if sys.platform != "darwin":
    pytest.skip("Requires macOS AppKit", allow_module_level=True)
pytest.importorskip("pagemark_core", reason="Build the app and include Resources/python on PYTHONPATH")
F = pytest.importorskip("Foundation")
objc = pytest.importorskip("objc")

from pagemark_app import application  # noqa: E402
from pagemark_app.probe import check_recent_menu  # noqa: E402


class MenuTestApplication(F.NSObject):
    def setWindowsMenu_(self, menu):
        self.window_menu = menu

    def setMainMenu_(self, menu):
        self.main_menu = menu


def test_recent_menu_registers_its_native_role_before_application_launch():
    app = MenuTestApplication.alloc().init()
    delegate = application.PagemarkDelegate.alloc().init()
    application.configure_menu(app, delegate)
    files = app.main_menu.itemWithTitle_("File").submenu()
    item = files.itemWithTitle_("Open Recent")
    assert item is not None, "Open Recent must exist before AppKit finishes launching"
    recent = item.submenu()
    # Read AppKit's actual registration, not an app-maintained identifier or
    # the visible title. This distinguishes a system menu from a lookalike.
    assert recent._menuName() == "NSRecentDocumentsMenu"
    assert recent.delegate() is None
    clear = recent.itemWithTitle_("Clear Menu")
    assert clear.action() == "clearRecentDocuments:"
    assert clear.target() == application.A.NSDocumentController.sharedDocumentController()
    assert not delegate.respondsToSelector_("openRecent:")


class NonNativeClearTarget(F.NSObject):
    def clearRecentDocuments_(self, sender):
        raise AssertionError("The diagnostic must never clear the Recent list")


@pytest.mark.parametrize("handler", ["document", "native_recent", "application", "unresolved"])
def test_recent_probe_resolves_appkits_own_clear_item(handler):
    controller = application.A.NSDocumentController.sharedDocumentController()
    controller.recentDocumentURLs()
    native_recent = objc.getInstanceVariable(controller, "_recentItemsController")
    # Use a menu made by AppKit itself: its Clear Menu item intentionally has
    # no explicit target. Reading this template never opens or clears history.
    recent_item = native_recent._createOpenRecentMenuItem()
    clear = recent_item.submenu().itemAtIndex_(0)
    assert clear.action() == "clearRecentDocuments:"
    assert clear.target() is None
    main = application.A.NSMenu.alloc().initWithTitle_("Main")
    files = application.A.NSMenu.alloc().initWithTitle_("File")
    application.add_item(main, "File", None).setSubmenu_(files)
    files.addItem_(recent_item)
    resolved = {"document": controller, "native_recent": native_recent,
                "application": NonNativeClearTarget.alloc().init(), "unresolved": None}[handler]
    routes = []

    def resolve(action, target, sender):
        routes.append((action, target, sender))
        return resolved

    # Only the NSApplication responder-chain lookup is stubbed; the menu,
    # item, registration, and both native handlers are real AppKit objects.
    app = SimpleNamespace(mainMenu=lambda: main, targetForAction_to_from_=resolve)
    delegate = application.PagemarkDelegate.alloc().init()
    assert check_recent_menu(app, delegate) is (handler in ("document", "native_recent"))
    assert routes == [("clearRecentDocuments:", None, clear)]


class RecordingOpenApplication(F.NSObject):
    def init(self):
        self = objc.super(RecordingOpenApplication, self).init()
        self.errors = []
        self.replies = []
        return self

    def presentError_(self, error):
        self.errors.append(error)
        return True

    def replyToOpenOrPrint_(self, reply):
        self.replies.append(reply)


class CallbackTestDocumentController(application.A.NSDocumentController):
    def noteNewRecentDocument_(self, document):
        pass  # Never add test fixtures to the user's recent-document history.

    def noteNewRecentDocumentURL_(self, url):
        pass


@pytest.mark.parametrize("already_open", [False, True])
def test_native_open_callback_delivers_document_bool_and_error(tmp_path, already_open):
    # Keep this independent controller from becoming the app's shared one.
    application.A.NSDocumentController.sharedDocumentController()
    controller = CallbackTestDocumentController.alloc().init()
    url = F.NSURL.fileURLWithPath_(str(tmp_path / "callback-fixture.txt"))
    document = None
    if already_open:
        document = application.A.NSDocument.alloc().init()
        document.setFileURL_(url)
        controller.addDocument_(document)
    results = []

    def completed(opened, was_already_open, error):
        results.append((opened, was_already_open, error))

    try:
        # This must cross the real Cocoa bridge. Mocking this method misses
        # PyObjC 12.1's incorrect one-argument completion-block signature.
        controller.openDocumentWithContentsOfURL_display_completionHandler_(url, False, completed)
        deadline = time.monotonic() + 3
        while not results and time.monotonic() < deadline:
            F.NSRunLoop.mainRunLoop().runUntilDate_(F.NSDate.dateWithTimeIntervalSinceNow_(0.01))
        assert len(results) == 1
        opened, was_already_open, error = results[0]
        assert isinstance(was_already_open, bool)
        assert was_already_open is already_open
        if already_open:
            assert opened == document and error is None
        else:
            assert opened is None and error is not None
    finally:
        if document is not None:
            controller.removeDocument_(document)


@pytest.mark.parametrize("error_codes", [
    (None, None),
    (F.NSFileReadNoPermissionError, None),
    (F.NSFileReadNoSuchFileError, F.NSFileReadNoPermissionError),
])
def test_system_open_events_show_errors_and_reply_after_all_opens(monkeypatch, error_codes):
    requests = []

    def open_document(url, display, completion):
        requests.append((url, display, completion))

    controller = SimpleNamespace(
        openDocumentWithContentsOfURL_display_completionHandler_=open_document)
    monkeypatch.setattr(application.A, "NSDocumentController", SimpleNamespace(
        sharedDocumentController=lambda: controller))
    app = RecordingOpenApplication.alloc().init()
    delegate = application.PagemarkDelegate.alloc().init()
    # Exercise Objective-C dispatch and filename-to-NSURL conversion. No real
    # document is opened and neither the user's Recent list nor grants change.
    paths = ["/unopened-test-fixtures/é 100%.txt", "/unopened-test-fixtures/second.txt"]
    delegate.performSelector_withObject_withObject_("application:openFiles:", app, paths)
    # Cocoa may decompose filesystem names; preserve their Unicode meaning.
    assert [unicodedata.normalize("NFC", str(url.path())) for url, _, _ in requests] == paths
    assert all(display for _, display, _ in requests)
    assert app.replies == []

    errors = []
    # Native document opens can complete asynchronously and out of order.
    for index in (1, 0):
        code = error_codes[index]
        error = None if code is None else F.NSError.errorWithDomain_code_userInfo_(
            F.NSCocoaErrorDomain, code, {F.NSLocalizedDescriptionKey: "Test open failure"})
        if error is not None:
            errors.append(error)
        requests[index][2](None, index == 1, error)
        if index == 1:
            assert app.replies == []

    assert app.errors == errors
    expected = (application.A.NSApplicationDelegateReplyFailure if errors
                else application.A.NSApplicationDelegateReplySuccess)
    assert app.replies == [expected]

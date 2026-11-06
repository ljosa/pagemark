"""Checks executed in the signed app, not a development Python process.

Only inspect the disposable path explicitly supplied by the test harness.
Network probes address loopback, never an external host or real user data.
"""
from __future__ import annotations

import errno
import json
from pathlib import Path
import socket
import sys
import tempfile
import time


def attempt(operation):
    try:
        operation()
    except OSError as exc:
        return {"denied": exc.errno in (errno.EPERM, errno.EACCES),
                "errno": exc.errno, "error": str(exc)}
    return {"denied": False, "error": None}


def checkpoint(message):
    print("probe: " + message, file=sys.stderr, flush=True)


def check_recent_menu(app, delegate):
    """Check registration; AppKit populates the menu when tracking begins."""
    import Foundation as F

    menus = []
    for top in app.mainMenu().itemArray():
        if top.submenu() is None:
            continue
        for item in top.submenu().itemArray():
            menu = item.submenu()
            if menu is not None and any(
                    child.action() == "clearRecentDocuments:" for child in menu.itemArray()):
                menus.append(menu)
    status = {"menu_count": len(menus), "registered": False, "native_clear_target": False}
    if len(menus) == 1:
        menu = menus[0]
        status["registered"] = bool(menu.respondsToSelector_("_menuName")
                                    and menu._menuName() == "NSRecentDocumentsMenu"
                                    and menu.delegate() != delegate)
        clear_items = [item for item in menu.itemArray()
                       if item.action() == "clearRecentDocuments:"]
        status["clear_item_count"] = len(clear_items)
        if len(clear_items) == 1:
            item = clear_items[0]
            # AppKit's own Clear Menu item has a nil target. Resolve it through
            # the same public API used for action routing, without sending the
            # action or clearing history. The handler may be NSDocumentController
            # or AppKit's internal recent-items controller.
            target = item.target()
            resolved = app.targetForAction_to_from_(item.action(), target, item)
            status["declared_clear_target"] = type(target).__name__ if target is not None else None
            status["resolved_clear_target"] = type(resolved).__name__ if resolved is not None else None
            bundle = F.NSBundle.bundleForClass_(type(resolved)) if resolved is not None else None
            status["clear_target_bundle"] = str(bundle.bundleIdentifier()) if bundle else None
            status["native_clear_target"] = bool(
                resolved is not None and resolved.respondsToSelector_(item.action())
                and status["clear_target_bundle"] == "com.apple.AppKit")
    checkpoint("Recent menu registration: " + json.dumps(status))
    return status["registered"] and status["native_clear_target"]


def check_document_open_callback():
    """Exercise Cocoa's real asynchronous callback using a missing private fixture."""
    import AppKit as A
    import Foundation as F

    private = Path(F.NSHomeDirectory()) / "Library/Caches/Pagemark"
    private.mkdir(parents=True, exist_ok=True)
    results = []
    with tempfile.TemporaryDirectory(prefix="open-probe-", dir=private) as directory:
        url = F.NSURL.fileURLWithPath_(str(Path(directory) / "missing.txt"))

        def completed(document, already_open, error):
            results.append((document, already_open, error))

        try:
            A.NSDocumentController.sharedDocumentController().openDocumentWithContentsOfURL_display_completionHandler_(
                url, False, completed)
        except Exception as error:
            checkpoint("document open callback failed: " + type(error).__name__ + ": " + str(error))
            return False
        deadline = time.monotonic() + 3
        while not results and time.monotonic() < deadline:
            F.NSRunLoop.mainRunLoop().runUntilDate_(F.NSDate.dateWithTimeIntervalSinceNow_(0.01))
    # Failure is intentional: no existing document is opened or added to Recent.
    return (len(results) == 1 and results[0][0] is None
            and results[0][1] is False and results[0][2] is not None)


def check_editor():
    """Exercise real Cocoa objects and events in a hidden, disposable window."""
    import AppKit as A
    from .application import PagemarkDocument, PagemarkDelegate, configure_menu
    from .codec import StyledText
    from .display_preferences import ViewMode
    from .session import Snapshot

    class PagemarkEditorProbeDelegate(PagemarkDelegate):
        def applicationDidFinishLaunching_(self, notification):
            # Complete AppKit's real launch sequence without opening a default
            # document or presenting the user's recovery dialog during a probe.
            pass

    checkpoint("getting native application")
    app = A.NSApplication.sharedApplication()
    delegate = PagemarkEditorProbeDelegate.alloc().init()
    app.setDelegate_(delegate)
    checkpoint("configuring menus")
    configure_menu(app, delegate)
    checkpoint("finishing native launch; checking system Recent menu")
    app.finishLaunching()
    recent = check_recent_menu(app, delegate)
    checkpoint("checking native document-open callback")
    open_callback = check_document_open_callback()
    checkpoint("creating document")
    document = PagemarkDocument.alloc().init()
    document.session.restore(Snapshot(StyledText("one two", (0,) * 7), 0, None, 0))
    manager = document.undoManager()
    manager.setGroupsByEvent_(False)
    try:
        checkpoint("creating hidden editor window")
        document.makeWindowControllers()
        checkpoint("editor window created; checking Command navigation and shortcuts")
        editor = document.editor

        def key(character, modifiers):
            event = A.NSEvent.keyEventWithType_location_modifierFlags_timestamp_windowNumber_context_characters_charactersIgnoringModifiers_isARepeat_keyCode_(
                A.NSEventTypeKeyDown, (0, 0), modifiers, 0, editor.window().windowNumber(),
                None, character, character, False, 0)
            manager.beginUndoGrouping()
            try:
                return bool(editor.performKeyEquivalent_(event))
            finally:
                manager.endUndoGrouping()

        navigation = key(A.NSRightArrowFunctionKey, A.NSEventModifierFlagCommand)
        navigation = navigation and document.session.cursor > 0
        document.session.select(0, 3)
        shortcuts = key("b", A.NSEventModifierFlagCommand)
        shortcuts = shortcuts and key("u", A.NSEventModifierFlagCommand)
        shortcuts = shortcuts and document.session.value.styles[:3] == (3, 3, 3)
        checkpoint("checking undo and redo")
        manager.undo()
        undo = document.session.value.styles[:3] == (1, 1, 1)
        manager.redo()
        undo = undo and document.session.value.styles[:3] == (3, 3, 3)
        checkpoint("checking Control aliases and Command-F search")
        formatting = key("\x02", A.NSEventModifierFlagControl)
        formatting = formatting and key("\x15", A.NSEventModifierFlagControl)
        formatting = formatting and document.session.value.styles[:3] == (0, 0, 0)
        shortcuts = shortcuts and key("f", A.NSEventModifierFlagCommand)
        shortcuts = shortcuts and not document.find_bar.view.isHidden()
        checkpoint("checking transient Find controls and full-height editor")
        find_bar = check_find_bar(document)
        checkpoint("checking Center Line and word transformation shortcuts")
        transforms = check_transform_shortcuts(editor, key)
        before = document.session.snapshot()
        checkpoint("checking view switching")
        for mode in (ViewMode.PAGES, ViewMode.DRAFT, ViewMode.CONTINUOUS):
            editor.view_mode = mode
            editor.refresh()
        views = document.session.snapshot() == before
        views = views and bool(editor.window().collectionBehavior() & A.NSWindowCollectionBehaviorFullScreenPrimary)
        checkpoint("checking display preferences and native appearance")
        display = check_display_preferences(app, delegate)
        checkpoint("checking zoom keys, synthetic pinch and scroll anchoring")
        from .zoom_probe import check_fit_actions, check_zoom
        zoom = check_zoom(editor)
        checkpoint("checking Fit Width and Resize Window to Fit")
        fit_actions = check_fit_actions(editor)
        checkpoint("checking reusable Help window and independent menu validation")
        help_window = check_help_window(app, delegate)
        return {"native_editor_window_created": True, "command_navigation": navigation,
                "command_shortcuts": shortcuts,
                "control_formatting": formatting, "native_undo_redo": undo,
                "view_switch_preserves_state": views, "native_recent_menu": recent,
                "native_document_open_callback": open_callback,
                "native_display_preferences": display, "native_zoom_controls": zoom,
                "native_fit_actions": fit_actions, "native_find_bar": find_bar,
                "native_transform_shortcuts": transforms, "native_help_window": help_window}
    finally:
        checkpoint("closing disposable editor document")
        document.close()
        app.setDelegate_(None)


def check_transform_shortcuts(editor, key):
    import AppKit as A
    from .codec import StyledText
    from .session import Snapshot

    before = editor.session.snapshot()
    try:
        for letter, shift, expected in (("e", False, " " * 30 + "mIXed"),
                                         ("C", True, "Mixed"), ("U", True, "MIXED"),
                                         ("L", True, "mixed")):
            editor.session.restore(Snapshot(StyledText("mIXed", (0,) * 5), 0, None, 0))
            editor.refresh()
            modifiers = A.NSEventModifierFlagCommand | (A.NSEventModifierFlagShift if shift else 0)
            if not key(letter, modifiers) or editor.session.value.text != expected:
                return False
            editor.document.undoManager().undo()
            if editor.session.value.text != "mIXed":
                return False
        return True
    finally:
        editor.session.restore(before)
        editor.refresh()


def check_help_window(app, delegate):
    from .native_help import HelpController

    item = app.mainMenu().itemWithTitle_("Help").submenu().itemWithTitle_("Pagemark Help")
    controller = HelpController.alloc().init()
    try:
        window = controller.window()
        text = controller.text_view
        valid = not text.isEditable() and text.isSelectable()
        valid = valid and "Center line\t⌘E" in str(text.string())
        text.layoutManager().ensureLayoutForTextContainer_(text.textContainer())
        valid = valid and text.frame().size.height > window.contentView().bounds().size.height
        for _ in range(2):
            controller.close()
            valid = valid and controller.window() == window and delegate.validateMenuItem_(item)
        return valid
    finally:
        controller.close()


def check_find_bar(document):
    import Foundation as F

    editor, bar = document.editor, document.find_bar
    scroll = editor.enclosingScrollView()
    content = scroll.superview()
    before = document.session.snapshot()
    original_frame = editor.window().frame()
    try:
        # The Command-F shortcut has already opened Find. Reopening must not
        # subtract another row from the viewport.
        bar.show()
        frame = scroll.frame()
        valid = frame.origin.y == bar.HEIGHT and F.NSMaxY(frame) == content.bounds().size.height
        bar.field.setStringValue_("no such text")
        document.controlTextDidChange_(None)
        valid = valid and bar.feedback.stringValue() == "No matches"
        bar.field.setStringValue_("two")
        document.controlTextDidChange_(None)
        valid = valid and bar.feedback.stringValue() == "" and document.session.selection == (4, 7)
        bar.field.setStringValue_("")
        document.controlTextDidChange_(None)
        valid = valid and bar.feedback.stringValue() == ""
        frame = editor.window().frame()
        frame.size.width -= 80
        editor.window().setFrame_display_(frame, True)
        valid = valid and F.NSMaxX(bar.field.frame()) < F.NSMinX(bar.feedback.frame())
        valid = valid and F.NSMaxX(bar.feedback.frame()) <= content.bounds().size.width
        for _ in range(2):
            document.control_textView_doCommandBySelector_(bar.field, None, "cancelOperation:")
            valid = valid and bar.view.isHidden() and scroll.frame() == content.bounds()
        return valid and document.session.value == before.value
    finally:
        document.session.restore(before)
        editor.window().setFrame_display_(original_frame, True)
        bar.set_visible(False)


def check_display_preferences(app, delegate):
    import AppKit as A
    from .display_preferences import Appearance
    from .native_preferences import PreferencesController, apply_appearance, display_preferences

    # Exercise real controls in a hidden preferences window. No user defaults
    # are written, and the original appearance is restored even on failure.
    controller = PreferencesController.alloc().init()
    original = app.appearance()
    try:
        window = controller.window()
        valid = bool(window and controller.family.numberOfItems())
        valid = valid and bool(controller.family.selectedItem().representedObject())
        valid = valid and not hasattr(controller, "size")
        for choice, name in ((Appearance.LIGHT, A.NSAppearanceNameAqua),
                             (Appearance.DARK, A.NSAppearanceNameDarkAqua), (Appearance.SYSTEM, None)):
            apply_appearance(app, choice)
            valid = valid and (app.appearance().name() if app.appearance() else None) == name
        menu = app.mainMenu().itemWithTitle_("View").submenu()
        for item in menu.itemArray():
            if item.action() == "changeAppearance:":
                valid = valid and delegate.validateMenuItem_(item)
                expected = int(str(item.representedObject()) == display_preferences().appearance)
                valid = valid and item.state() == expected
        return valid
    finally:
        app.setAppearance_(original)
        controller.close()


def run_editor() -> int:
    import Foundation
    result = {"app_version": Foundation.NSBundle.mainBundle().objectForInfoDictionaryKey_(
        "CFBundleShortVersionString")}
    checks = check_editor()
    result.update(checks)
    print(json.dumps(result, indent=2), flush=True)
    return 0 if all(checks.values()) else 1


def run(denied_file: str | None, *, include_editor=True) -> int:
    checkpoint("importing Cocoa and shared PDF modules")
    import AppKit
    import Foundation
    import objc
    from .application import PDFPrintView
    from pagemark_core.print_formatter import PrintFormatter
    from pagemark_core.pdf_generator import PDFGenerator

    # Creating/invoking a Python-backed Cocoa class exercises PyObjC's call stubs.
    class PagemarkProbeObject(Foundation.NSObject):
        def answer(self):
            return 42

    checkpoint("checking Cocoa callback, PDF, and native print adapter")
    bridge = PagemarkProbeObject.alloc().init()
    page = PrintFormatter(["Pagemark sandbox probe"])
    pdf = PDFGenerator().generate_pdf(page.format_pages(), page.get_page_runs())
    data = Foundation.NSData.dataWithBytes_length_(pdf, len(pdf))
    rep = AppKit.NSPDFImageRep.imageRepWithData_(data)
    print_view = PDFPrintView.alloc().initWithFrame_(Foundation.NSMakeRect(0, 0, 612, 792))
    print_view.configure(pdf)
    operation = AppKit.NSPrintOperation.printOperationWithView_printInfo_(
        print_view, AppKit.NSPrintInfo.sharedPrintInfo().copy())
    # Construct the platform adapter without opening a panel or submitting a job.
    result = {
        "app_version": Foundation.NSBundle.mainBundle().objectForInfoDictionaryKey_("CFBundleShortVersionString"),
        "python_isolated": bool(sys.flags.isolated),
        "site_import_disabled": "site" not in sys.modules,
        "python_paths": sys.path,
        "python_executable": sys.executable,
        "pyobjc_version": objc.__version__,
        "cocoa_callback": bridge.performSelector_("answer") == 42,
        "pdf_generated": pdf.startswith(b"%PDF-"),
        "native_pdf_pages": int(rep.pageCount()) if rep else None,
        "native_print_operation_created": operation is not None,
    }
    checkpoint("checking app-private storage")
    recovery = Path(Foundation.NSHomeDirectory()) / "Library/Application Support/Pagemark"
    recovery.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryFile(dir=recovery) as stream:
        stream.write(b"pagemark-private-storage-probe")
        stream.seek(0)
        result["private_storage_read_write"] = stream.read() == b"pagemark-private-storage-probe"

    def connect():
        with socket.socket() as connection:
            connection.settimeout(1)
            connection.connect(("127.0.0.1", 9))

    def listen():
        with socket.socket() as server:
            server.bind(("127.0.0.1", 0))
            server.listen(1)

    checkpoint("checking direct network and unselected-file denials")
    result["loopback_connect"] = attempt(connect)
    result["loopback_listen"] = attempt(listen)
    if denied_file:
        result["unselected_file"] = attempt(lambda: Path(denied_file).read_bytes())
    editor_result = {}
    if include_editor:
        # Preserve completed results even if native GUI initialization aborts.
        checkpoint("runtime checks completed: " + json.dumps(result))
        editor_result = check_editor()
        result.update(editor_result)
    print(json.dumps(result, indent=2), flush=True)
    valid = (result["python_isolated"] and result["site_import_disabled"]
             and result["cocoa_callback"] and result["pdf_generated"]
             and result["native_pdf_pages"] == 1
             and result["native_print_operation_created"]
             and result["private_storage_read_write"]
             and all(editor_result.values())
             and result["loopback_connect"]["denied"]
             and result["loopback_listen"]["denied"])
    if denied_file:
        valid = valid and result["unselected_file"]["denied"]
    return 0 if valid else 1


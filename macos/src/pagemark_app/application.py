"""Native document lifecycle, menus, recovery and shared PDF printing."""
from __future__ import annotations

import objc
import AppKit as A
import Foundation as F
from pathlib import Path
import uuid

from .codec import BOLD, UNDERLINE, StyledText, decode, encode, utf16_offsets
from .cocoa_compat import configure_document_open_callback
from .display_preferences import Appearance, ViewMode
from .native_editor import PagemarkEditorView
from .native_find import FindBar
from .native_help import HelpController
from .native_fitting import can_resize_window, fit_width, resize_window_to_fit
from .native_preferences import PreferencesController, apply_appearance, display_preferences
from .recovery import RecoveryStore
from .session import EditorSession, Snapshot
from .zoom import command_zoom

configure_document_open_callback()


def cocoa_error(error: Exception):
    return F.NSError.errorWithDomain_code_userInfo_(
        "org.pagemark.mac", 1, {F.NSLocalizedDescriptionKey: str(error)})


def font(bold=False):
    return A.NSFont.fontWithName_size_("Courier-Bold" if bold else "Courier", 16)


def attributed(value: StyledText):
    result = F.NSMutableAttributedString.alloc().initWithString_attributes_(
        value.text, {A.NSFontAttributeName: font(),
                     A.NSForegroundColorAttributeName: A.NSColor.textColor()})
    offsets = utf16_offsets(value.text)
    start = 0
    while start < len(value.styles):
        flag = value.styles[start]
        end = start + 1
        while end < len(value.styles) and value.styles[end] == flag:
            end += 1
        attrs = {A.NSFontAttributeName: font(bool(flag & BOLD)),
                 A.NSUnderlineStyleAttributeName: 1 if flag & UNDERLINE else 0}
        result.addAttributes_range_(attrs, (offsets[start], offsets[end] - offsets[start]))
        start = end
    return result


def styled(storage) -> StyledText:
    text = str(storage.string())
    if "\ufffc" in text:
        raise ValueError("Pagemark documents cannot contain attachments")
    offsets = utf16_offsets(text)
    flags = []
    manager = A.NSFontManager.sharedFontManager()
    for index, char in enumerate(text):
        if char == "\n":
            flags.append(0)
            continue
        attrs, _ = storage.attributesAtIndex_effectiveRange_(offsets[index], None)
        current_font = attrs.get(A.NSFontAttributeName)
        flag = BOLD if current_font and manager.traitsOfFont_(current_font) & A.NSBoldFontMask else 0
        if attrs.get(A.NSUnderlineStyleAttributeName, 0):
            flag |= UNDERLINE
        flags.append(flag)
    return StyledText(text, tuple(flags))


def render_pdf(value: StyledText, double_spacing=False, booklet=False):
    from pagemark_core.print_formatter import PrintFormatter
    from pagemark_core.pdf_generator import PDFGenerator
    paragraphs, styles = value.parts()
    formatter = PrintFormatter(paragraphs, styles=styles, double_spacing=double_spacing)
    pages = formatter.format_pages()
    generator = PDFGenerator()
    pdf = generator.generate_pdf(pages, formatter.get_page_runs(), booklet=booklet)
    return pdf, generator.get_unprintable_warning()


def pdf_for(value: StyledText, double_spacing=False, booklet=False) -> bytes:
    return render_pdf(value, double_spacing, booklet)[0]


class PDFPrintView(A.NSView):
    @objc.python_method
    def configure(self, pdf):
        data = F.NSData.dataWithBytes_length_(pdf, len(pdf))
        self.pdf_rep = A.NSPDFImageRep.imageRepWithData_(data)
        if self.pdf_rep is None:
            raise ValueError("macOS could not read the generated PDF")
        self.page_size = self.pdf_rep.size()
        self.setFrameSize_((self.page_size.width,
                            self.page_size.height * self.pdf_rep.pageCount()))

    def knowsPageRange_(self, ignored):
        return True, F.NSMakeRange(1, self.pdf_rep.pageCount())

    def rectForPage_(self, page):
        return F.NSMakeRect(0, (page - 1) * self.page_size.height,
                            self.page_size.width, self.page_size.height)

    def drawRect_(self, rect):
        operation = A.NSPrintOperation.currentOperation()
        page = operation.currentPage() if operation else 1
        if 1 <= page <= self.pdf_rep.pageCount():
            self.pdf_rep.setCurrentPage_(page - 1)
            self.pdf_rep.drawInRect_(self.rectForPage_(page))


def recovery_store():
    return RecoveryStore(Path(F.NSHomeDirectory()) / "Library/Application Support/Pagemark/Recovery")


class PagemarkDocument(A.NSDocument):
    def init(self):
        self = objc.super(PagemarkDocument, self).init()
        if self is not None:
            self.content = StyledText("", ())
            self.original_bytes = None
            self.session = EditorSession(on_change=self.editor_changed)
            self.editor = self.find_bar = None
            self.recovery_id = str(uuid.uuid4())
            self.recovery_timer = None
            self.recovery_error = None
        return self

    @classmethod
    def autosavesInPlace(cls):
        return False

    @classmethod
    def preservesVersions(cls):
        return False

    @classmethod
    def autosavesDrafts(cls):
        return False

    def readFromData_ofType_error_(self, data, type_name, ignored):
        try:
            original = bytes(data)
            content = decode(original)
            self.session.restore(Snapshot(content, 0, None, 0))
            self.original_bytes, self.content = original, content
            if self.editor:
                self.editor.refresh()
            return True, None
        except (ValueError, UnicodeError) as error:
            return False, cocoa_error(error)

    def dataOfType_error_(self, type_name, ignored):
        try:
            if self.editor:
                self.editor.unmarkText()
            value = self.session.value
            data = encode(value, self.original_bytes)
            return F.NSData.dataWithBytes_length_(data, len(data)), None
        except (ValueError, UnicodeError) as error:
            return None, cocoa_error(error)

    def writeSafelyToURL_ofType_forSaveOperation_error_(self, url, type_name, operation, ignored):
        value = self.session.value
        ok, error = objc.super(PagemarkDocument, self).writeSafelyToURL_ofType_forSaveOperation_error_(
            url, type_name, operation, None)
        if ok and operation in (A.NSSaveOperation, A.NSSaveAsOperation):
            self.original_bytes = encode(value, self.original_bytes)
            self.content = value
            if self.session.value == value:
                self.clear_recovery()
        return ok, error

    @objc.python_method
    def editor_changed(self, before, after):
        manager = self.undoManager()
        manager.registerUndoWithTarget_handler_(self, lambda target: target.restore_snapshot(before))
        manager.setActionName_("Edit")
        self.schedule_recovery()

    @objc.python_method
    def restore_snapshot(self, snapshot):
        before = self.session.snapshot()
        self.session.restore(snapshot)
        self.editor_changed(before, snapshot)
        if self.editor:
            self.editor.refresh()

    @objc.python_method
    def schedule_recovery(self):
        if self.recovery_timer:
            return
        self.recovery_timer = F.NSTimer.scheduledTimerWithTimeInterval_target_selector_userInfo_repeats_(
            0.75, self, "writeRecovery:", None, False)

    def writeRecovery_(self, timer):
        self.recovery_timer = None
        try:
            recovery_store().write(self.recovery_id, self.session.snapshot(),
                                   self.displayName(), self.original_bytes)
            self.recovery_error = None
        except (OSError, ValueError) as error:
            self.report_recovery_error("Recovery unavailable: " + str(error))

    @objc.python_method
    def clear_recovery(self):
        if self.recovery_timer:
            self.recovery_timer.invalidate()
            self.recovery_timer = None
        try:
            recovery_store().remove(self.recovery_id)
            self.recovery_error = None
        except OSError as error:
            self.report_recovery_error("Could not remove recovery copy: " + str(error))

    @objc.python_method
    def report_recovery_error(self, message):
        # A failed timer must not interrupt every subsequent keystroke with
        # the same dialog. A successful recovery operation resets this state.
        if message != self.recovery_error:
            self.recovery_error = message
            self.report_error(RuntimeError(message))

    def close(self):
        # NSDocument calls close only after its Save/Discard/Cancel decision.
        # Cancelling never reaches this method, so the recovery remains intact.
        self.clear_recovery()
        if self.editor:
            self.editor.teardown()
        objc.super(PagemarkDocument, self).close()

    def makeWindowControllers(self):
        window = A.NSWindow.alloc().initWithContentRect_styleMask_backing_defer_(
            F.NSMakeRect(0, 0, 840, 720),
            A.NSWindowStyleMaskTitled | A.NSWindowStyleMaskClosable |
            A.NSWindowStyleMaskMiniaturizable | A.NSWindowStyleMaskResizable,
            A.NSBackingStoreBuffered, False)
        window.setSubtitle_("Pagemark — editor preview")
        window.setRestorable_(False)
        window.setCollectionBehavior_(A.NSWindowCollectionBehaviorFullScreenPrimary)
        window.setMinSize_((480, 320))
        window.center()
        content = window.contentView()
        scroll = A.NSScrollView.alloc().initWithFrame_(content.bounds())
        scroll.setAutoresizingMask_(A.NSViewWidthSizable | A.NSViewHeightSizable)
        scroll.setHasVerticalScroller_(True)
        scroll.setHasHorizontalScroller_(True)
        scroll.setAutohidesScrollers_(True)
        editor = PagemarkEditorView.alloc().initWithFrame_(content.bounds())
        scroll.setDocumentView_(editor)
        content.addSubview_(scroll)
        self.editor = editor
        editor.configure(self)
        self.find_bar = FindBar(editor, self)
        clip = scroll.contentView()
        clip.setPostsFrameChangedNotifications_(True)
        F.NSNotificationCenter.defaultCenter().addObserver_selector_name_object_(
            editor, "viewportChanged:", A.NSViewFrameDidChangeNotification, clip)
        window.makeFirstResponder_(editor)
        controller = A.NSWindowController.alloc().initWithWindow_(window)
        self.addWindowController_(controller)

    @objc.python_method
    def report_error(self, error):
        self.presentError_(cocoa_error(error))

    @objc.python_method
    def editor_action(self, action):
        if action == "save":
            self.saveDocument_(None)
        elif action == "print":
            self.printDocument_(None)
        elif action == "find":
            self.find_bar.show()
        elif action == "help":
            A.NSApp.delegate().showHelp_(None)
        elif action == "word_count":
            alert = A.NSAlert.alloc().init()
            alert.setMessageText_(f"{self.session.model.count_words()} words")
            alert.runModal()

    def controlTextDidChange_(self, notification):
        self.find_bar.text_changed()

    def control_textView_doCommandBySelector_(self, control, view, selector):
        return self.find_bar.command(selector)

    def printDocument_(self, sender):
        self.print_output(booklet=False)

    def printBooklet_(self, sender):
        self.print_output(booklet=True)

    @objc.python_method
    def print_output(self, *, booklet):
        try:
            self.editor.unmarkText()
            pdf = self.output_pdf(booklet=booklet)
            if pdf is None:
                return
            view = PDFPrintView.alloc().initWithFrame_(F.NSMakeRect(0, 0, 612, 792))
            view.configure(pdf)
            info = self.printInfo().copy()
            info.setPaperSize_(view.page_size)
            for name in ("Top", "Bottom", "Left", "Right"):
                getattr(info, "set" + name + "Margin_")(0)
            operation = A.NSPrintOperation.printOperationWithView_printInfo_(view, info)
            operation.setJobTitle_(self.displayName())
            operation.runOperation()
        except Exception as error:
            self.report_error(error)

    def exportPDF_(self, sender):
        try:
            self.editor.unmarkText()
            pdf = self.output_pdf()
            if pdf is None:
                return
            panel = A.NSSavePanel.savePanel()
            panel.setAllowedFileTypes_(["pdf"])
            panel.setNameFieldStringValue_(self.displayName().removesuffix(".txt") + ".pdf")
            if panel.runModal() == A.NSModalResponseOK:
                data = F.NSData.dataWithBytes_length_(pdf, len(pdf))
                ok, error = data.writeToURL_options_error_(panel.URL(), F.NSDataWritingAtomic, None)
                if not ok:
                    self.presentError_(error)
        except Exception as error:
            self.report_error(error)

    @objc.python_method
    def output_pdf(self, *, booklet=False):
        pdf, warning = render_pdf(self.session.value, self.editor.double_spacing, booklet)
        if warning:
            alert = A.NSAlert.alloc().init()
            alert.setMessageText_("Some characters cannot be printed in Courier")
            alert.setInformativeText_(warning + "\nThe document itself is unchanged.")
            alert.addButtonWithTitle_("Cancel")
            alert.addButtonWithTitle_("Continue")
            if alert.runModal() != A.NSAlertSecondButtonReturn:
                return None
        return pdf


class PagemarkDelegate(F.NSObject):
    def application_shouldSaveApplicationState_(self, app, coder):
        return False

    def application_shouldRestoreApplicationState_(self, app, coder):
        return False

    def applicationShouldOpenUntitledFile_(self, app):
        return False

    def applicationDidFinishLaunching_(self, notification):
        controller = A.NSDocumentController.sharedDocumentController()
        if not controller.documents():
            controller.newDocument_(None)
        A.NSApp.activateIgnoringOtherApps_(True)
        self.recoverDocuments_(None)

    def application_openFiles_(self, app, filenames):
        controller = A.NSDocumentController.sharedDocumentController()
        remaining = [len(filenames)]
        failed = [False]

        def completed(document, already_open, error):
            if error is not None:
                failed[0] = True
                app.presentError_(error)
            remaining[0] -= 1
            if remaining[0] == 0:
                app.replyToOpenOrPrint_(A.NSApplicationDelegateReplyFailure if failed[0]
                                       else A.NSApplicationDelegateReplySuccess)

        for path in filenames:
            controller.openDocumentWithContentsOfURL_display_completionHandler_(
                F.NSURL.fileURLWithPath_(path), True, completed)

    def exportPDF_(self, sender):
        document = A.NSDocumentController.sharedDocumentController().currentDocument()
        if document:
            document.exportPDF_(sender)

    def printDocument_(self, sender):
        document = A.NSDocumentController.sharedDocumentController().currentDocument()
        if document:
            document.printDocument_(sender)

    def printBooklet_(self, sender):
        document = A.NSDocumentController.sharedDocumentController().currentDocument()
        if document:
            document.printBooklet_(sender)

    def editorCommand_(self, sender):
        document = A.NSDocumentController.sharedDocumentController().currentDocument()
        if document and document.editor:
            document.editor.execute(str(sender.representedObject()))

    def changeView_(self, sender):
        document = A.NSDocumentController.sharedDocumentController().currentDocument()
        if document and document.editor:
            editor = document.editor
            editor.view_mode = ViewMode(sender.tag())
            display_preferences().view_mode = editor.view_mode
            editor.refresh()

    def changeAppearance_(self, sender):
        appearance = Appearance(str(sender.representedObject()))
        display_preferences().appearance = appearance
        apply_appearance(A.NSApp, appearance)

    def zoomView_(self, sender):
        document = A.NSDocumentController.sharedDocumentController().currentDocument()
        if document and document.editor:
            editor = document.editor
            editor.set_zoom(command_zoom(editor.zoom, str(sender.representedObject())))

    def fitWidth_(self, sender):
        document = A.NSDocumentController.sharedDocumentController().currentDocument()
        if document and document.editor:
            fit_width(document.editor)

    def resizeWindowToFit_(self, sender):
        document = A.NSDocumentController.sharedDocumentController().currentDocument()
        if document and document.editor:
            resize_window_to_fit(document.editor)

    def showPreferences_(self, sender):
        if not getattr(self, "preferences_controller", None):
            self.preferences_controller = PreferencesController.alloc().init()
        self.preferences_controller.showWindow_(sender)

    def showHelp_(self, sender):
        if not getattr(self, "help_controller", None):
            self.help_controller = HelpController.alloc().init()
        self.help_controller.showWindow_(sender)

    def changeSpacing_(self, sender):
        document = A.NSDocumentController.sharedDocumentController().currentDocument()
        if document and document.editor:
            document.editor.double_spacing = sender.tag() == 2
            document.editor.refresh()

    def validateMenuItem_(self, item):
        action = item.action()
        if action == "showHelp:":
            return True
        if action == "changeAppearance:":
            item.setState_(int(display_preferences().appearance == str(item.representedObject())))
            return True
        document = A.NSDocumentController.sharedDocumentController().currentDocument()
        if action in ("zoomView:", "fitWidth:", "resizeWindowToFit:"):
            if not document or not document.editor or A.NSApp.keyWindow() != document.editor.window():
                return False
            if action == "fitWidth:":
                return True
            if action == "resizeWindowToFit:":
                return can_resize_window(document.editor.window())
            return command_zoom(document.editor.zoom, str(item.representedObject())) != document.editor.zoom
        if action in ("changeView:", "changeSpacing:", "editorCommand:",
                      "printDocument:", "printBooklet:", "exportPDF:"):
            if not document or not document.editor:
                return False
            if action == "editorCommand:" and (
                    A.NSApp.keyWindow() != document.editor.window()
                    or document.editor.window().firstResponder() != document.editor):
                return False
            if action == "changeView:":
                item.setState_(int(document.editor.view_mode == ViewMode(item.tag())))
            elif action == "changeSpacing:":
                item.setState_(int(document.editor.double_spacing == (item.tag() == 2)))
            elif action == "editorCommand:" and str(item.representedObject()) in ("bold", "underline"):
                flag = BOLD if str(item.representedObject()) == "bold" else UNDERLINE
                item.setState_(int(bool(document.session.model.caret_style & flag)))
        return True

    def recoverDocuments_(self, sender):
        controller = A.NSDocumentController.sharedDocumentController()
        active = {document.recovery_id for document in controller.documents()}
        store = recovery_store()
        identifiers = [identifier for identifier in store.identifiers() if identifier not in active]
        if not identifiers:
            return
        alert = A.NSAlert.alloc().init()
        alert.setMessageText_(f"Recover {len(identifiers)} unsaved document(s)?")
        alert.setInformativeText_("Recovery opens private copies. Use Save As to choose their destination.")
        alert.addButtonWithTitle_("Recover")
        alert.addButtonWithTitle_("Keep for Later")
        alert.addButtonWithTitle_("Discard Copies")
        result = alert.runModal()
        if result == A.NSAlertSecondButtonReturn:
            return
        for identifier in identifiers:
            try:
                if result == A.NSAlertThirdButtonReturn:
                    store.remove(identifier)
                    continue
                snapshot, title, original = store.read(identifier)
                document = PagemarkDocument.alloc().init()
                document.recovery_id = identifier
                document.original_bytes = original
                document.session.restore(snapshot)
                document.setFileType_("public.plain-text")
                document.setDisplayName_("Recovered — " + title)
                document.updateChangeCount_(A.NSChangeDone)
                controller.addDocument_(document)
                document.makeWindowControllers()
                document.showWindows()
            except (OSError, ValueError, KeyError, TypeError) as error:
                A.NSApp.presentError_(cocoa_error(error))


def add_item(menu, title, action, key="", target=None, control=False):
    item = A.NSMenuItem.alloc().initWithTitle_action_keyEquivalent_(title, action, key)
    if target is not None:
        item.setTarget_(target)
    if control:
        item.setKeyEquivalentModifierMask_(A.NSEventModifierFlagControl)
    menu.addItem_(item)
    return item


def make_recent_menu(controller):
    recent = A.NSMenu.alloc().initWithTitle_("Open Recent")
    # Programmatic menus need the same internal name as an Interface Builder
    # Recent menu. AppKit will not infer this role from a title or Open action.
    # This private selector is isolated here and checked on the target OS.
    # Replace it with a compiled menu nib when the build has Interface Builder.
    if not recent.respondsToSelector_("_setMenuName:"):
        raise RuntimeError("This macOS version cannot register Pagemark's Open Recent menu")
    recent._setMenuName_("NSRecentDocumentsMenu")
    add_item(recent, "Clear Menu", "clearRecentDocuments:", target=controller)
    return recent


def configure_menu(app, delegate):
    main = A.NSMenu.alloc().initWithTitle_("Main")
    application = A.NSMenu.alloc().initWithTitle_("Pagemark")
    add_item(main, "Pagemark", None).setSubmenu_(application)
    add_item(application, "About Pagemark", "orderFrontStandardAboutPanel:", target=app)
    application.addItem_(A.NSMenuItem.separatorItem())
    add_item(application, "Preferences…", "showPreferences:", ",", delegate)
    application.addItem_(A.NSMenuItem.separatorItem())
    add_item(application, "Quit Pagemark", "terminate:", "q", app)
    files = A.NSMenu.alloc().initWithTitle_("File")
    add_item(main, "File", None).setSubmenu_(files)
    controller = A.NSDocumentController.sharedDocumentController()
    add_item(files, "New", "newDocument:", "n", controller)
    add_item(files, "Open…", "openDocument:", "o", controller)
    # Register before finishLaunching so AppKit owns population and selection.
    add_item(files, "Open Recent", None).setSubmenu_(make_recent_menu(controller))
    add_item(files, "Close", "performClose:", "w")
    add_item(files, "Save", "saveDocument:", "s")
    add_item(files, "Save As…", "saveDocumentAs:", "s").setKeyEquivalentModifierMask_(
        A.NSEventModifierFlagCommand | A.NSEventModifierFlagShift)
    add_item(files, "Recover Unsaved Documents…", "recoverDocuments:", target=delegate)
    files.addItem_(A.NSMenuItem.separatorItem())
    add_item(files, "Export PDF…", "exportPDF:", target=delegate)
    add_item(files, "Print…", "printDocument:", "p", delegate)
    add_item(files, "Print Booklet…", "printBooklet:", target=delegate)
    edit = A.NSMenu.alloc().initWithTitle_("Edit")
    add_item(main, "Edit", None).setSubmenu_(edit)
    for title, action, key in (("Undo", "undo:", "z"), ("Redo", "redo:", "y"),
                               ("Cut", "cut:", "x"), ("Copy", "copy:", "c"),
                               ("Paste", "paste:", "v")):
        add_item(edit, title, action, key)
    # Native dialog fields also get the conventional Shift-Command-Z alias.
    redo = add_item(edit, "Redo", "redo:", "z")
    redo.setKeyEquivalentModifierMask_(A.NSEventModifierFlagCommand | A.NSEventModifierFlagShift)
    redo.setHidden_(True)
    redo.setAllowsKeyEquivalentWhenHidden_(True)
    add_item(edit, "Select All", "selectAll:", "a")
    add_item(edit, "Find…", "editorCommand:", "f", delegate).setRepresentedObject_("find")
    add_item(edit, "Word Count", "editorCommand:", "w", delegate, control=True).setRepresentedObject_("word_count")
    transform = A.NSMenu.alloc().initWithTitle_("Transform")
    add_item(edit, "Transform", None).setSubmenu_(transform)
    for title, command, key in (("Capitalize Word", "capitalize_word", "c"),
                                ("Uppercase Word", "upcase_word", "u"),
                                ("Lowercase Word", "downcase_word", "l")):
        item = add_item(transform, title, "editorCommand:", key, delegate)
        item.setRepresentedObject_(command)
        item.setKeyEquivalentModifierMask_(A.NSEventModifierFlagCommand | A.NSEventModifierFlagShift)
    format_menu = A.NSMenu.alloc().initWithTitle_("Format")
    add_item(main, "Format", None).setSubmenu_(format_menu)
    for title, command, key in (("Bold", "bold", "b"), ("Underline", "underline", "u")):
        add_item(format_menu, title, "editorCommand:", key, delegate).setRepresentedObject_(command)
    add_item(format_menu, "Center Line", "editorCommand:", "e", delegate).setRepresentedObject_("center_line")
    format_menu.addItem_(A.NSMenuItem.separatorItem())
    add_item(format_menu, "Single Spacing", "changeSpacing:", target=delegate).setTag_(1)
    add_item(format_menu, "Double Spacing", "changeSpacing:", target=delegate).setTag_(2)
    view = A.NSMenu.alloc().initWithTitle_("View")
    add_item(main, "View", None).setSubmenu_(view)
    add_item(view, "Continuous", "changeView:", target=delegate).setTag_(0)
    add_item(view, "Pages", "changeView:", target=delegate).setTag_(1)
    add_item(view, "Draft", "changeView:", target=delegate).setTag_(2)
    view.addItem_(A.NSMenuItem.separatorItem())
    for title, appearance in (("Light Mode", Appearance.LIGHT), ("Dark Mode", Appearance.DARK),
                              ("System Default", Appearance.SYSTEM)):
        add_item(view, title, "changeAppearance:", target=delegate).setRepresentedObject_(str(appearance))
    view.addItem_(A.NSMenuItem.separatorItem())
    for title, command, key in (("Zoom In", "zoom_in", "+"), ("Zoom Out", "zoom_out", "-"),
                                ("Actual Size", "zoom_reset", "0")):
        add_item(view, title, "zoomView:", key, delegate).setRepresentedObject_(command)
    alias = add_item(view, "Zoom In", "zoomView:", "=", delegate)
    alias.setRepresentedObject_("zoom_in")
    alias.setHidden_(True)
    alias.setAllowsKeyEquivalentWhenHidden_(True)
    add_item(view, "Fit Width", "fitWidth:", target=delegate)
    add_item(view, "Resize Window to Fit", "resizeWindowToFit:", target=delegate)
    view.addItem_(A.NSMenuItem.separatorItem())
    add_item(view, "Enter Full Screen", "toggleFullScreen:", "f").setKeyEquivalentModifierMask_(
        A.NSEventModifierFlagCommand | A.NSEventModifierFlagControl)
    window = A.NSMenu.alloc().initWithTitle_("Window")
    add_item(main, "Window", None).setSubmenu_(window)
    add_item(window, "Minimize", "performMiniaturize:", "m")
    add_item(window, "Zoom", "performZoom:")
    help_menu = A.NSMenu.alloc().initWithTitle_("Help")
    add_item(main, "Help", None).setSubmenu_(help_menu)
    add_item(help_menu, "Pagemark Help", "showHelp:", target=delegate)
    app.setWindowsMenu_(window)
    app.setMainMenu_(main)


def run():
    app = A.NSApplication.sharedApplication()
    app.setActivationPolicy_(A.NSApplicationActivationPolicyRegular)
    apply_appearance(app, display_preferences().appearance)
    delegate = PagemarkDelegate.alloc().init()
    app.setDelegate_(delegate)
    configure_menu(app, delegate)
    app.run()


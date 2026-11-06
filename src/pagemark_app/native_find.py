"""Transient Find controls and feedback, separate from document lifecycle."""
import AppKit as A
import Foundation as F


class FindBar:
    HEIGHT = 36

    def __init__(self, editor, delegate):
        self.editor = editor
        self.origin = 0
        content = editor.enclosingScrollView().superview()
        width = content.bounds().size.width
        self.view = A.NSView.alloc().initWithFrame_(F.NSMakeRect(0, 0, width, self.HEIGHT))
        self.view.setAutoresizingMask_(A.NSViewWidthSizable)
        self.field = A.NSSearchField.alloc().initWithFrame_(F.NSMakeRect(12, 6, width - 132, 24))
        self.field.setAutoresizingMask_(A.NSViewWidthSizable)
        self.field.setPlaceholderString_("Find — Return for next, Escape to finish")
        self.field.setAccessibilityLabel_("Find")
        self.field.setDelegate_(delegate)
        self.view.addSubview_(self.field)
        self.feedback = A.NSTextField.labelWithString_("")
        self.feedback.setFrame_(F.NSMakeRect(width - 108, 8, 96, 20))
        self.feedback.setAutoresizingMask_(A.NSViewMinXMargin)
        self.feedback.setTextColor_(A.NSColor.secondaryLabelColor())
        self.view.addSubview_(self.feedback)
        self.view.setHidden_(True)
        content.addSubview_(self.view)

    def set_visible(self, visible):
        scroll = self.editor.enclosingScrollView()
        frame = scroll.superview().bounds()
        if visible:
            frame.origin.y += self.HEIGHT
            frame.size.height -= self.HEIGHT
        self.view.setHidden_(not visible)
        scroll.setFrame_(frame)
        self.editor.refresh()

    def show(self):
        self.editor.unmarkText()
        self.origin = self.editor.session.selection[0]
        self.feedback.setStringValue_("")
        self.set_visible(True)
        self.editor.window().makeFirstResponder_(self.field)

    def find(self, start, backwards=False):
        query = str(self.field.stringValue())
        found = bool(query) and self.editor.session.find(query, start, backwards)
        self.feedback.setStringValue_("No matches" if query and not found else "")
        if found or not query:
            self.editor.refresh()
        return found

    def text_changed(self):
        self.find(self.origin)

    def command(self, selector):
        name = selector.decode() if isinstance(selector, bytes) else str(selector)
        if name == "cancelOperation:":
            self.set_visible(False)
            self.editor.window().makeFirstResponder_(self.editor)
            return True
        if name in ("insertNewline:", "insertBacktab:"):
            backwards = name == "insertBacktab:"
            start, end = self.editor.session.selection
            if not self.find(start if backwards else end, backwards) and self.field.stringValue():
                A.NSBeep()
            return True
        return False

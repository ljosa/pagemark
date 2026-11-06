"""Reusable, nonmodal keyboard reference window."""
import AppKit as A
import Foundation as F
import objc

from .help_content import HELP_NOTE, HELP_SECTIONS


def help_text():
    result = F.NSMutableAttributedString.alloc().initWithString_("")
    color = A.NSColor.textColor()

    def append(text, size=13, *, heading=False, before=0, after=5, secondary=False):
        paragraph = A.NSMutableParagraphStyle.alloc().init()
        paragraph.setParagraphSpacingBefore_(before)
        paragraph.setParagraphSpacing_(after)
        paragraph.setTabStops_([A.NSTextTab.alloc().initWithTextAlignment_location_options_(
            A.NSTextAlignmentRight, 540, {})])
        font = A.NSFont.boldSystemFontOfSize_(size) if heading else A.NSFont.systemFontOfSize_(size)
        attrs = {A.NSFontAttributeName: font, A.NSParagraphStyleAttributeName: paragraph,
                 A.NSForegroundColorAttributeName: A.NSColor.secondaryLabelColor() if secondary else color}
        result.appendAttributedString_(F.NSAttributedString.alloc().initWithString_attributes_(text, attrs))

    append("Keyboard Shortcuts\n", 24, heading=True, after=8)
    append("Pagemark for macOS\n", secondary=True, after=4)
    for heading, rows in HELP_SECTIONS:
        append(heading + "\n", 14, heading=True, before=18, after=8)
        for action, shortcut in rows:
            append(action + "\t" + shortcut + "\n")
    append("\n" + HELP_NOTE, 12, secondary=True)
    return result


class HelpController(A.NSWindowController):
    def init(self):
        self = objc.super(HelpController, self).initWithWindow_(None)
        if self is not None:
            self.setWindow_(self.make_window())
        return self

    @objc.python_method
    def make_window(self):
        window = A.NSWindow.alloc().initWithContentRect_styleMask_backing_defer_(
            F.NSMakeRect(0, 0, 620, 620), A.NSWindowStyleMaskTitled | A.NSWindowStyleMaskClosable |
            A.NSWindowStyleMaskMiniaturizable | A.NSWindowStyleMaskResizable,
            A.NSBackingStoreBuffered, False)
        window.setTitle_("Pagemark Help")
        window.setMinSize_((620, 360))
        window.setReleasedWhenClosed_(False)
        window.setRestorable_(False)
        scroll = A.NSScrollView.alloc().initWithFrame_(window.contentView().bounds())
        scroll.setAutoresizingMask_(A.NSViewWidthSizable | A.NSViewHeightSizable)
        scroll.setHasVerticalScroller_(True)
        scroll.setAutohidesScrollers_(True)
        self.text_view = A.NSTextView.alloc().initWithFrame_(scroll.contentView().bounds())
        self.text_view.setEditable_(False)
        self.text_view.setSelectable_(True)
        self.text_view.setDrawsBackground_(False)
        self.text_view.setTextContainerInset_((24, 20))
        self.text_view.setMinSize_((0, scroll.contentSize().height))
        self.text_view.setMaxSize_((1e7, 1e7))
        self.text_view.setVerticallyResizable_(True)
        self.text_view.setHorizontallyResizable_(False)
        self.text_view.setAutoresizingMask_(A.NSViewWidthSizable)
        self.text_view.textContainer().setContainerSize_((scroll.contentSize().width, 1e7))
        self.text_view.textContainer().setWidthTracksTextView_(True)
        self.text_view.textStorage().setAttributedString_(help_text())
        scroll.setDocumentView_(self.text_view)
        self.text_view.sizeToFit()
        window.contentView().addSubview_(scroll)
        window.center()
        return window

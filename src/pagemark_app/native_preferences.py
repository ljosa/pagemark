"""Native presentation of app-wide display preferences."""
import AppKit as A
import Foundation as F
import objc

from .display_preferences import Appearance, DisplayPreferences, DraftFont, ViewMode
from .screen_fonts import draft_font, draft_font_choices


def display_preferences():
    return DisplayPreferences(F.NSUserDefaults.standardUserDefaults())


def apply_appearance(app, appearance):
    name = {Appearance.LIGHT: A.NSAppearanceNameAqua,
            Appearance.DARK: A.NSAppearanceNameDarkAqua}.get(Appearance(appearance))
    # A nil override follows subsequent system appearance changes as well.
    app.setAppearance_(A.NSAppearance.appearanceNamed_(name) if name else None)


def refresh_draft_editors():
    spec = display_preferences().draft_font
    for document in A.NSDocumentController.sharedDocumentController().documents():
        editor = getattr(document, "editor", None)
        if editor is not None:
            editor.draft_font = spec
            if editor.view_mode == ViewMode.DRAFT:
                editor.refresh()


class PreferencesController(A.NSWindowController):
    def init(self):
        self = objc.super(PreferencesController, self).initWithWindow_(None)
        if self is not None:
            self.preferences = display_preferences()
            # A controller initialized with no window or nib does not invoke
            # loadWindow on first access. Create the programmatic window here;
            # the app creates this controller lazily on the Preferences action.
            self.setWindow_(self.make_window())
        return self

    @objc.python_method
    def make_window(self):
        window = A.NSWindow.alloc().initWithContentRect_styleMask_backing_defer_(
            F.NSMakeRect(0, 0, 480, 140), A.NSWindowStyleMaskTitled | A.NSWindowStyleMaskClosable,
            A.NSBackingStoreBuffered, False)
        window.setTitle_("Preferences")
        window.setReleasedWhenClosed_(False)
        window.setRestorable_(False)
        window.setContentView_(self.make_content())
        window.center()
        return window

    @objc.python_method
    def make_content(self):
        content = A.NSView.alloc().initWithFrame_(F.NSMakeRect(0, 0, 480, 140))
        label = A.NSTextField.labelWithString_("Draft font:")
        label.setFrame_(F.NSMakeRect(20, 87, 100, 22))
        label.setAlignment_(A.NSTextAlignmentRight)
        content.addSubview_(label)
        self.family = A.NSPopUpButton.alloc().initWithFrame_pullsDown_(
            F.NSMakeRect(132, 85, 324, 26), False)
        self.family.setAccessibilityLabel_("Draft font")
        spec = self.preferences.draft_font
        current = draft_font(spec)
        choices = dict(draft_font_choices())
        choices[str(current.familyName())] = str(current.fontName())
        for family, name in sorted(choices.items(), key=lambda choice: choice[0].casefold()):
            self.family.addItemWithTitle_(family)
            self.family.lastItem().setRepresentedObject_(name)
        self.family.selectItemWithTitle_(current.familyName())
        self.family.setTarget_(self)
        self.family.setAction_("changeDraftFont:")
        content.addSubview_(self.family)
        note = A.NSTextField.wrappingLabelWithString_(
            "Pinch or use ⌘+ / ⌘− to change the reading size.\n⌘0 resets zoom to 100%. Zoom does not affect printing.")
        note.setFont_(A.NSFont.systemFontOfSize_(12))
        note.setTextColor_(A.NSColor.secondaryLabelColor())
        note.setFrame_(F.NSMakeRect(24, 20, 432, 40))
        content.addSubview_(note)
        return content

    def changeDraftFont_(self, sender):
        self.preferences.draft_font = DraftFont(str(self.family.selectedItem().representedObject()))
        refresh_draft_editors()

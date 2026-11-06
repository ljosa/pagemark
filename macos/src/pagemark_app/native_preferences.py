"""Native presentation of app-wide display preferences."""
import AppKit as A
import Foundation as F
import objc

from .display_preferences import (
    Appearance, DisplayPreferences, DraftFont, ViewMode, DRAFT_LINE_SPACINGS,
)
from .screen_fonts import draft_font, draft_font_choices


def display_preferences():
    return DisplayPreferences(F.NSUserDefaults.standardUserDefaults())


def apply_appearance(app, appearance):
    name = {Appearance.LIGHT: A.NSAppearanceNameAqua,
            Appearance.DARK: A.NSAppearanceNameDarkAqua}.get(Appearance(appearance))
    # A nil override follows subsequent system appearance changes as well.
    app.setAppearance_(A.NSAppearance.appearanceNamed_(name) if name else None)


def refresh_draft_editors():
    preferences = display_preferences()
    for document in A.NSDocumentController.sharedDocumentController().documents():
        editor = getattr(document, "editor", None)
        if editor is not None:
            editor.draft_font = preferences.draft_font
            editor.draft_line_spacing = preferences.draft_line_spacing
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
            F.NSMakeRect(0, 0, 480, 180), A.NSWindowStyleMaskTitled | A.NSWindowStyleMaskClosable,
            A.NSBackingStoreBuffered, False)
        window.setTitle_("Preferences")
        window.setReleasedWhenClosed_(False)
        window.setRestorable_(False)
        window.setContentView_(self.make_content())
        window.center()
        return window

    @objc.python_method
    def make_content(self):
        content = A.NSView.alloc().initWithFrame_(F.NSMakeRect(0, 0, 480, 180))
        label = A.NSTextField.labelWithString_("Draft font:")
        label.setFrame_(F.NSMakeRect(20, 127, 100, 22))
        label.setAlignment_(A.NSTextAlignmentRight)
        content.addSubview_(label)
        self.family = A.NSPopUpButton.alloc().initWithFrame_pullsDown_(
            F.NSMakeRect(132, 125, 324, 26), False)
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
        spacing_label = A.NSTextField.labelWithString_("Draft spacing:")
        spacing_label.setFrame_(F.NSMakeRect(20, 87, 100, 22))
        spacing_label.setAlignment_(A.NSTextAlignmentRight)
        content.addSubview_(spacing_label)
        self.spacing = A.NSPopUpButton.alloc().initWithFrame_pullsDown_(
            F.NSMakeRect(132, 85, 324, 26), False)
        self.spacing.setAccessibilityLabel_("Draft line spacing")
        for value, title in zip(DRAFT_LINE_SPACINGS, ("Single", "1.25", "1.5", "Double")):
            self.spacing.addItemWithTitle_(title)
            self.spacing.lastItem().setRepresentedObject_(value)
        self.spacing.selectItemAtIndex_(DRAFT_LINE_SPACINGS.index(self.preferences.draft_line_spacing))
        self.spacing.setTarget_(self)
        self.spacing.setAction_("changeDraftLineSpacing:")
        content.addSubview_(self.spacing)
        note = A.NSTextField.wrappingLabelWithString_(
            "Draft font and spacing do not affect printing.\nPinch or use ⌘+ / ⌘− to zoom; ⌘0 resets to 100%.")
        note.setFont_(A.NSFont.systemFontOfSize_(12))
        note.setTextColor_(A.NSColor.secondaryLabelColor())
        note.setFrame_(F.NSMakeRect(24, 20, 432, 40))
        content.addSubview_(note)
        return content

    def changeDraftFont_(self, sender):
        self.preferences.draft_font = DraftFont(str(self.family.selectedItem().representedObject()))
        refresh_draft_editors()

    def changeDraftLineSpacing_(self, sender):
        self.preferences.draft_line_spacing = float(self.spacing.selectedItem().representedObject())
        refresh_draft_editors()

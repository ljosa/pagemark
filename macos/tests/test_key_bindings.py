"""Exercise native key events without opening dialogs or changing the clipboard."""
import pytest

pytest.importorskip("pagemark_core")
A = pytest.importorskip("AppKit")
F = pytest.importorskip("Foundation")
objc = pytest.importorskip("objc")

from pagemark_app.application import PagemarkDelegate, configure_menu  # noqa: E402
from pagemark_app.native_editor import PagemarkEditorView  # noqa: E402


class ShortcutTestWindow(F.NSObject):
    def firstResponder(self):
        return self.responder


class ShortcutTestView(PagemarkEditorView):
    def window(self):
        return getattr(self, "test_window", None)

    @objc.python_method
    def execute(self, command, extend=False):
        self.commands.append((command, extend))


class ShortcutMenuApplication(F.NSObject):
    def setWindowsMenu_(self, menu):
        self.windows = menu

    def setMainMenu_(self, menu):
        self.menu = menu


@pytest.fixture
def editor():
    view = ShortcutTestView.alloc().initWithFrame_(F.NSMakeRect(0, 0, 800, 600))
    window = ShortcutTestWindow.alloc().init()
    window.responder = view
    view.test_window = window
    view.commands = []
    yield view
    window.responder = None
    view.test_window = None


def event(character, modifiers):
    return A.NSEvent.keyEventWithType_location_modifierFlags_timestamp_windowNumber_context_characters_charactersIgnoringModifiers_isARepeat_keyCode_(
        A.NSEventTypeKeyDown, (0, 0), modifiers, 0, 0, None,
        character, character, False, 0)


@pytest.mark.parametrize("letter,action", [
    ("s", "save"), ("q", "quit"), ("f", "find"), ("p", "print"),
    ("x", "cut"), ("c", "copy"), ("v", "paste"), ("b", "bold"),
    ("u", "underline"), ("z", "undo"), ("y", "redo"),
])
@pytest.mark.parametrize("modifier", [A.NSEventModifierFlagCommand, A.NSEventModifierFlagControl])
def test_requested_command_shortcuts_and_control_aliases(editor, letter, action, modifier):
    character = chr(ord(letter) - 96) if modifier == A.NSEventModifierFlagControl else letter
    assert editor.performKeyEquivalent_(event(character, modifier))
    assert editor.commands == [(action, False)]


def test_command_arrows_extend_selection_and_shift_command_z_redoes(editor):
    modifiers = A.NSEventModifierFlagCommand | A.NSEventModifierFlagShift
    assert editor.performKeyEquivalent_(event(A.NSRightArrowFunctionKey, modifiers))
    assert editor.performKeyEquivalent_(event("Z", modifiers))
    assert editor.commands == [("word_right", True), ("redo", True)]


@pytest.mark.parametrize("character,shift,command", [
    ("+", False, "zoom_in"), ("+", True, "zoom_in"), ("=", False, "zoom_in"),
    ("=", True, "zoom_in"), ("-", False, "zoom_out"), ("0", False, "zoom_reset"),
])
def test_zoom_shortcuts_accept_plus_and_unshifted_equals(editor, character, shift, command):
    modifiers = A.NSEventModifierFlagCommand | (A.NSEventModifierFlagShift if shift else 0)
    assert editor.performKeyEquivalent_(event(character, modifiers))
    assert editor.commands == [(command, shift)]


@pytest.mark.parametrize("character,command", [
    (A.NSLeftArrowFunctionKey, "left"), (A.NSRightArrowFunctionKey, "right"),
    (A.NSUpArrowFunctionKey, "up"), (A.NSDownArrowFunctionKey, "down"),
    (A.NSHomeFunctionKey, "home"), (A.NSEndFunctionKey, "end"),
    (A.NSPageUpFunctionKey, "page_up"), (A.NSPageDownFunctionKey, "page_down"),
    (A.NSDeleteFunctionKey, "delete"),
])
def test_native_function_characters_dispatch_to_editor_commands(editor, character, command):
    editor.keyDown_(event(character, 0))
    assert editor.commands == [(command, False)]


@pytest.mark.parametrize("letter,modifiers", [
    ("b", A.NSEventModifierFlagOption),
    ("b", A.NSEventModifierFlagCommand | A.NSEventModifierFlagOption),
    ("b", A.NSEventModifierFlagCommand | A.NSEventModifierFlagControl),
    ("S", A.NSEventModifierFlagCommand | A.NSEventModifierFlagShift),
])
def test_native_input_and_other_menu_equivalents_are_not_intercepted(editor, letter, modifiers):
    assert not editor.performKeyEquivalent_(event(letter, modifiers))
    assert not editor.commands


def test_editor_shortcuts_do_not_intercept_a_native_field_editors_keys(editor):
    editor.test_window.responder = None
    assert not editor.performKeyEquivalent_(event("c", A.NSEventModifierFlagCommand))
    assert not editor.commands


def test_visible_menus_show_command_shortcuts_and_preserve_native_responder_routing():
    app = ShortcutMenuApplication.alloc().init()
    delegate = PagemarkDelegate.alloc().init()
    configure_menu(app, delegate)
    expected = {"Pagemark": {"Quit Pagemark": "q"},
                "File": {"Save": "s", "Print…": "p"},
                "Edit": {"Find…": "f", "Cut": "x", "Copy": "c", "Paste": "v",
                         "Undo": "z", "Redo": "y"},
                "Format": {"Bold": "b", "Underline": "u"}}
    for name, commands in expected.items():
        menu = app.menu.itemWithTitle_(name).submenu()
        for title, key in commands.items():
            item = menu.itemWithTitle_(title)
            assert not item.isHidden()
            assert item.keyEquivalent() == key
            assert item.keyEquivalentModifierMask() == A.NSEventModifierFlagCommand
    edit = app.menu.itemWithTitle_("Edit").submenu()
    for title in ("Cut", "Copy", "Paste", "Undo", "Redo"):
        assert edit.itemWithTitle_(title).target() is None
    transform = edit.itemWithTitle_("Transform").submenu()
    assert [item.representedObject() for item in transform.itemArray()] == [
        "capitalize_word", "upcase_word", "downcase_word"]

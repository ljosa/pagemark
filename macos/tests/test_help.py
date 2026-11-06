"""Help remains available independently of document and field-editor focus."""
from types import SimpleNamespace

import pytest

A = pytest.importorskip("AppKit")

from pagemark_app import application  # noqa: E402
from pagemark_app.native_help import help_text  # noqa: E402
from test_key_bindings import ShortcutMenuApplication  # noqa: E402


def test_help_menu_stays_enabled_after_closing_help_and_without_a_document(monkeypatch):
    app = ShortcutMenuApplication.alloc().init()
    delegate = application.PagemarkDelegate.alloc().init()
    application.configure_menu(app, delegate)
    item = app.menu.itemWithTitle_("Help").submenu().itemWithTitle_("Pagemark Help")
    current = [None]
    monkeypatch.setattr(A, "NSDocumentController", SimpleNamespace(sharedDocumentController=lambda:
        SimpleNamespace(currentDocument=lambda: current[0])))
    monkeypatch.setattr(A, "NSApp", SimpleNamespace(keyWindow=lambda: object()))
    shown, created = [], []

    def allocate():
        controller = SimpleNamespace(showWindow_=lambda sender: shown.append(sender))
        controller.init = lambda: controller
        controller.close = lambda: shown.append("closed")
        created.append(controller)
        return controller

    monkeypatch.setattr(application, "HelpController", SimpleNamespace(alloc=allocate))
    assert item.action() == "showHelp:"
    for document in (None, SimpleNamespace(editor=object()), None):
        current[0] = document
        assert delegate.validateMenuItem_(item)
        delegate.performSelector_withObject_(item.action(), item)
        delegate.help_controller.close()
        assert delegate.validateMenuItem_(item)
    assert len(created) == 1
    assert shown == [item, "closed"] * 3


def test_editor_help_command_uses_the_same_application_action(monkeypatch):
    calls = []
    monkeypatch.setattr(A, "NSApp", SimpleNamespace(delegate=lambda:
        SimpleNamespace(showHelp_=lambda sender: calls.append(sender))))
    document = application.PagemarkDocument.alloc().init()
    document.editor_action("help")
    assert calls == [None]


def test_help_content_formats_all_groups_and_new_shortcuts_as_native_text():
    value = help_text()
    text = str(value.string())
    assert text.startswith("Keyboard Shortcuts\n")
    for row in ("Center line\t⌘E", "Capitalize word\t⇧⌘C", "Uppercase word\t⇧⌘U",
                "Lowercase word\t⇧⌘L", "Close Find\tEscape"):
        assert row in text
    assert "⌘M" not in text and "⌘L:" not in text

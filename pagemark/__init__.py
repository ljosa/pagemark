"""Pagemark terminal application and compatible public imports."""
from .model import TextModel, TextView, CursorPosition

__all__ = ['TextModel', 'TextView', 'CursorPosition', 'TerminalTextView', 'render_paragraph']


def __getattr__(name):
    # Importing document/layout modules must not initialize a terminal UI.
    if name in ('TerminalTextView', 'render_paragraph'):
        from . import view
        value = getattr(view, name)
        globals()[name] = value
        return value
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")

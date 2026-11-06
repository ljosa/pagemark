"""Terminal model adapter; document editing lives in pagemark_core."""
from pagemark_core.model import (  # noqa: F401
    CursorPosition, DocumentModel, StyleFlags, StyleMask, StyleMasks, TextView,
)
from pagemark_core.model import TextModel as CoreTextModel
from .clipboard import ClipboardManager


class TextModel(CoreTextModel):
    def __init__(self, view, paragraphs=None, *, clipboard=None):
        super().__init__(view, paragraphs, clipboard=ClipboardManager if clipboard is None else clipboard)

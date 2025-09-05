from dataclasses import dataclass
from typing import Optional


@dataclass
class ModelSnapshot:
    paragraphs: list[str]
    styles: Optional[list[list[int]]] = None
    caret_style: int = 0
    cursor_paragraph_index: int = 0
    cursor_character_index: int = 0
    selection_start: Optional[tuple[int, int]] = None
    selection_end: Optional[tuple[int, int]] = None


@dataclass
class UndoEntry:
    before: ModelSnapshot
    after: ModelSnapshot


class UndoManager:
    def __init__(self, max_entries: int = 500):
        self._undo_stack: list[UndoEntry] = []
        self._redo_stack: list[UndoEntry] = []
        self._max_entries = max_entries

    def clear(self):
        self._undo_stack.clear()
        self._redo_stack.clear()

    def push(self, entry: UndoEntry):
        self._undo_stack.append(entry)
        # Cap history
        if len(self._undo_stack) > self._max_entries:
            self._undo_stack.pop(0)
        # Any new edit invalidates redo history
        self._redo_stack.clear()

    def can_undo(self) -> bool:
        return bool(self._undo_stack)

    def can_redo(self) -> bool:
        return bool(self._redo_stack)

    def undo(self, editor) -> bool:
        if not self._undo_stack:
            return False
        entry = self._undo_stack.pop()
        # Apply before snapshot
        editor._apply_snapshot(entry.before)
        # Move to redo stack
        self._redo_stack.append(entry)
        return True

    def redo(self, editor) -> bool:
        if not self._redo_stack:
            return False
        entry = self._redo_stack.pop()
        # Apply after snapshot
        editor._apply_snapshot(entry.after)
        # Return entry to undo stack
        self._undo_stack.append(entry)
        return True

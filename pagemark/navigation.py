"""Cursor state transitions without model, terminal, or command dependencies.

Vertical movement preserves the preferred cell column. Other relocations set
it to the destination column. Selection keeps its first anchor. Moving inherits
style from the character on the left (or the first character at paragraph start);
history can explicitly restore the insertion style instead.
"""
from dataclasses import dataclass
from typing import Sequence

from .coordinates import CellColumn, DocumentPosition


def inherited_style(position: DocumentPosition, styles: Sequence[Sequence[int]]) -> int:
    if not 0 <= position.paragraph_index < len(styles):
        return 0
    row = styles[position.paragraph_index]
    index = max(0, position.character_index - 1)
    return row[index] if index < len(row) else 0


@dataclass(frozen=True)
class NavigationState:
    cursor: DocumentPosition = DocumentPosition()
    anchor: DocumentPosition | None = None
    desired_column: CellColumn = CellColumn(0)
    caret_style: int = 0

    def relocate(self, target: DocumentPosition, column: int,
                 styles: Sequence[Sequence[int]], *, preserve_column: bool = False,
                 extend_selection: bool = False,
                 caret_style: int | None = None) -> "NavigationState":
        return NavigationState(
            cursor=target,
            anchor=(self.anchor or self.cursor) if extend_selection else None,
            desired_column=self.desired_column if preserve_column else CellColumn(column),
            caret_style=inherited_style(target, styles) if caret_style is None else caret_style,
        )

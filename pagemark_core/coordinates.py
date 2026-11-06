"""Coordinate types shared by the pure editor components."""

from dataclasses import dataclass
from typing import NewType

SourceOffset = NewType("SourceOffset", int)
CellColumn = NewType("CellColumn", int)
ContentLineIndex = NewType("ContentLineIndex", int)
ScreenRowIndex = NewType("ScreenRowIndex", int)


@dataclass(frozen=True, order=True)
class DocumentPosition:
    paragraph_index: int = 0
    character_index: int = 0

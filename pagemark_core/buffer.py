"""Immutable styled text with validated, atomic range replacement.

Offsets count codepoints; paragraph separators carry no style. A document always
contains at least one paragraph. Range endpoints may be reversed, but must be
valid. Invalid input raises before any state can change. No presentation or
cursor-navigation policy belongs in this module.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Sequence

from .coordinates import DocumentPosition


@dataclass(frozen=True)
class StyledParagraph:
    text: str
    styles: tuple[int, ...]

    def __post_init__(self) -> None:
        object.__setattr__(self, "styles", tuple(self.styles))
        if "\n" in self.text or len(self.text) != len(self.styles):
            raise ValueError("A paragraph needs one style per codepoint and no newline")

    def slice(self, start: int, end: int | None = None) -> StyledParagraph:
        return StyledParagraph(self.text[start:end], self.styles[start:end])

    def concat(self, other: StyledParagraph) -> StyledParagraph:
        return StyledParagraph(self.text + other.text, self.styles + other.styles)


@dataclass(frozen=True)
class StyledDocument:
    paragraphs: tuple[StyledParagraph, ...]

    def __post_init__(self) -> None:
        object.__setattr__(self, "paragraphs", tuple(self.paragraphs))
        if not self.paragraphs:
            raise ValueError("A document must contain at least one paragraph")

    @classmethod
    def from_parts(
        cls, paragraphs: Sequence[str], styles: Sequence[Sequence[int]]
    ) -> StyledDocument:
        if len(paragraphs) != len(styles):
            raise ValueError("Paragraph and style counts must match")
        return cls(
            tuple(
                StyledParagraph(text, tuple(mask))
                for text, mask in zip(paragraphs, styles)
            )
        )

    @classmethod
    def plain(cls, text: str, style: int = 0) -> StyledDocument:
        return cls(
            tuple(
                StyledParagraph(part, (style,) * len(part)) for part in text.split("\n")
            )
        )

    def bounds(
        self, start: DocumentPosition, end: DocumentPosition
    ) -> tuple[DocumentPosition, DocumentPosition]:
        for position in (start, end):
            pi, ci = position.paragraph_index, position.character_index
            if not 0 <= pi < len(self.paragraphs) or not 0 <= ci <= len(
                self.paragraphs[pi].text
            ):
                raise ValueError(f"Invalid document position: {position}")
        return (start, end) if start <= end else (end, start)

    def slice(self, start: DocumentPosition, end: DocumentPosition) -> StyledDocument:
        start, end = self.bounds(start, end)
        result = []
        for pi in range(start.paragraph_index, end.paragraph_index + 1):
            first = start.character_index if pi == start.paragraph_index else 0
            last = end.character_index if pi == end.paragraph_index else None
            result.append(self.paragraphs[pi].slice(first, last))
        return StyledDocument(tuple(result))

    def replace(
        self, start: DocumentPosition, end: DocumentPosition, inserted: StyledDocument
    ) -> tuple[StyledDocument, DocumentPosition]:
        start, end = self.bounds(start, end)
        first, last = start.paragraph_index, end.paragraph_index
        parts = list(inserted.paragraphs)
        cursor = DocumentPosition(
            first + len(parts) - 1,
            len(parts[-1].text) + (start.character_index if len(parts) == 1 else 0),
        )
        parts[0] = (
            self.paragraphs[first].slice(0, start.character_index).concat(parts[0])
        )
        parts[-1] = parts[-1].concat(self.paragraphs[last].slice(end.character_index))
        result = self.paragraphs[:first] + tuple(parts) + self.paragraphs[last + 1 :]
        return StyledDocument(result), cursor

    def toggle_style(
        self, start: DocumentPosition, end: DocumentPosition, flag: int
    ) -> StyledDocument:
        selected = self.slice(start, end)
        clear = all(
            mask & flag
            for paragraph in selected.paragraphs
            for mask in paragraph.styles
        )
        replacement = StyledDocument(
            tuple(
                StyledParagraph(
                    paragraph.text,
                    tuple(
                        mask & ~flag if clear else mask | flag
                        for mask in paragraph.styles
                    ),
                )
                for paragraph in selected.paragraphs
            )
        )
        return self.replace(start, end, replacement)[0]

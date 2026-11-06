"""Paragraph-local Unicode indices and document prefix offsets, without Cocoa.

Text changes create a new index while retaining unchanged paragraph records.
Grapheme segmentation is supplied by the platform and computed only on demand.
The index owns no mutable document data and cannot change selection or text.
"""
from bisect import bisect_left, bisect_right
from functools import cached_property

from pagemark_core.coordinates import DocumentPosition

from .codec import utf16_offsets


class _ParagraphIndex:
    def __init__(self, text, boundaries):
        self.text = text
        self._boundaries = boundaries
        self.native_length = len(text) + sum(ord(char) > 0xFFFF for char in text)
        self.word_count = len(text.split())

    @cached_property
    def native_offsets(self):
        return range(len(self.text) + 1) if self.text.isascii() else utf16_offsets(self.text)

    @cached_property
    def stops(self):
        return self._boundaries(self.text)


class TextIndex:
    def __init__(self, paragraphs, boundaries, previous=None):
        retained = {item.text: item for item in previous.paragraphs} if (
            previous is not None and previous.boundaries is boundaries) else {}
        self.boundaries = boundaries
        self.paragraphs = tuple(retained[text] if text in retained else _ParagraphIndex(text, boundaries)
                                for text in paragraphs)
        if not self.paragraphs:
            raise ValueError("A document must contain at least one paragraph")
        source, native = [], []
        source_count = native_count = 0
        for item in self.paragraphs:
            source.append(source_count)
            native.append(native_count)
            source_count += len(item.text) + 1
            native_count += item.native_length + 1
        self.source_starts, self.native_starts = tuple(source), tuple(native)
        self.length, self.native_length = source_count - 1, native_count - 1
        self.word_count = sum(item.word_count for item in self.paragraphs)

    def position(self, offset):
        offset = max(0, min(offset, self.length))
        paragraph = bisect_right(self.source_starts, offset) - 1
        return DocumentPosition(paragraph, offset - self.source_starts[paragraph])

    def offset(self, position):
        return self.source_starts[position.paragraph_index] + position.character_index

    def native_offset(self, offset):
        point = self.position(offset)
        return (self.native_starts[point.paragraph_index]
                + self.paragraphs[point.paragraph_index].native_offsets[point.character_index])

    def source_offset(self, native_offset, *, round_up=False):
        native_offset = max(0, min(native_offset, self.native_length))
        paragraph = bisect_right(self.native_starts, native_offset) - 1
        offsets = self.paragraphs[paragraph].native_offsets
        local = native_offset - self.native_starts[paragraph]
        character = bisect_left(offsets, local) if round_up else bisect_right(offsets, local) - 1
        return self.source_starts[paragraph] + character

    def snap(self, offset, bias="nearest"):
        point = self.position(offset)
        stops = self.paragraphs[point.paragraph_index].stops
        index = bisect_left(stops, point.character_index)
        upper = stops[min(index, len(stops) - 1)]
        lower = upper if upper == point.character_index else stops[max(0, index - 1)]
        local = {"floor": lower, "ceil": upper}.get(bias)
        if local is None:
            local = min((lower, upper), key=lambda value: abs(value - point.character_index))
        return self.source_starts[point.paragraph_index] + local

    def previous_boundary(self, offset):
        point = self.position(offset)
        if point.character_index == 0:
            return max(0, self.offset(point) - 1)
        stops = self.paragraphs[point.paragraph_index].stops
        return (self.source_starts[point.paragraph_index]
                + stops[max(0, bisect_left(stops, point.character_index) - 1)])

    def next_boundary(self, offset):
        point = self.position(offset)
        paragraph = self.paragraphs[point.paragraph_index]
        if point.character_index == len(paragraph.text):
            return min(self.length, self.offset(point) + 1)
        stops = paragraph.stops
        return (self.source_starts[point.paragraph_index]
                + stops[min(len(stops) - 1, bisect_right(stops, point.character_index))])

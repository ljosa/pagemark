"""Document-scoped bridge to the unmodified Pagemark editing model.

AppKit owns undo, input composition, and clipboard access. This module owns
source positions and publishes one complete change per editing transaction.
It never opens a file or imports the terminal view.
"""
from __future__ import annotations

from bisect import bisect_right
from dataclasses import dataclass

from pagemark_core.coordinates import DocumentPosition
from pagemark_core.layout import DocumentLayout, layout_paragraph
from pagemark_core.model import CursorPosition, TextModel
from pagemark_core.text_layout import display_spans

from .codec import StyledText
from .text_index import TextIndex


class MacTextModel(TextModel):
    def _get_visual_line_info(self):
        point = self.navigation_state.cursor
        layout = layout_paragraph(self.paragraphs[point.paragraph_index], self.view.num_columns)
        return layout.line_for_char_index(point.character_index), layout


@dataclass(frozen=True)
class Snapshot:
    value: StyledText
    cursor: int
    anchor: int | None
    caret_style: int
    desired_column: int | None = None


class EditorSession:
    def __init__(self, value=StyledText("", ()), on_change=None, boundaries=None):
        self.num_columns = 65
        self.model = MacTextModel(self)
        self.on_change = on_change
        self.boundaries = boundaries or self._display_boundaries
        self._layout_key = None
        self._layout = None
        self._index_key = None
        self._index = None
        self.restore(Snapshot(value, 0, None, 0))

    def render(self):
        # Model render requests are deliberately deferred to the native event
        # boundary; intermediate mutations must never publish half a selection.
        pass

    @staticmethod
    def _display_boundaries(text):
        return [0] + [end for _, end, _ in display_spans(text)]

    @property
    def value(self):
        text = "\n".join(self.model.paragraphs)
        flags = []
        for index, row in enumerate(self.model.styles):
            if index:
                flags.append(0)
            flags.extend(row)
        return StyledText(text, tuple(flags))

    @property
    def layout(self):
        key = (tuple(self.model.paragraphs), self.num_columns)
        if key != self._layout_key:
            self._layout = DocumentLayout.build(key[0], key[1], previous=self._layout)
            self._layout_key = key
        return self._layout

    def offset(self, position):
        return self.index.offset(position)

    def position(self, offset):
        return self.index.position(offset)

    @property
    def index(self):
        key = (tuple(self.model.paragraphs), self.boundaries)
        if key != self._index_key:
            self._index = TextIndex(key[0], self.boundaries, self._index)
            self._index_key = key
        return self._index

    @property
    def anchor(self):
        point = self.model.navigation_state.anchor
        return self.offset(point) if point is not None else None

    @property
    def cursor(self):
        return self.offset(self.model.navigation_state.cursor)

    @property
    def selection(self):
        state = self.model.navigation_state
        cursor = self.offset(state.cursor)
        anchor = self.offset(state.anchor) if state.anchor else cursor
        return min(anchor, cursor), max(anchor, cursor)

    def snapshot(self):
        state = self.model.navigation_state
        return Snapshot(self.value, self.cursor,
                        self.offset(state.anchor) if state.anchor else None, state.caret_style,
                        self.model.desired_column)

    def restore(self, state):
        self.model.paragraphs, self.model.styles = state.value.parts()
        self.select(state.anchor if state.anchor is not None else state.cursor, state.cursor)
        self.model.caret_style = state.caret_style
        if state.desired_column is not None:
            self.model.desired_column = state.desired_column

    def select(self, anchor, cursor):
        self.model.clear_selection()
        if anchor != cursor:
            self.model.selection_start = CursorPosition(*self._tuple(self.position(anchor)))
        self.model.relocate_cursor(self.position(cursor), render=False)

    @staticmethod
    def _tuple(position):
        return position.paragraph_index, position.character_index

    def notify_change(self, before):
        after = self.snapshot()
        if before.value != after.value and self.on_change:
            self.on_change(before, after)
        return before.value != after.value

    def edit(self, operation):
        before = self.snapshot()
        try:
            with self.model.defer_render():
                operation()
                self.model.desired_column = self.model.cursor_column()
        except Exception:
            self.restore(before)
            raise
        return self.notify_change(before)

    def insert(self, text, styles=None, *, notify=True):
        text, styles = self.model._sanitize_clipboard_content(text, styles)
        if notify:
            return self.edit(lambda: self.model.replace_selection(text, styles))
        self.model.replace_selection(text, styles)
        self.model.desired_column = self.model.cursor_column()

    def move_to(self, target, extend=False, preserve_column=False):
        offset = self.offset(target)
        target = self.position(self.index.snap(offset))
        if extend:
            if self.model.selection_start is None:
                self.model.start_selection()
        else:
            self.model.clear_selection()
        self.model.relocate_cursor(target, preserve_column=preserve_column, render=False)

    def move(self, command, extend=False, page_lines=20):
        model = self.model
        point = model.navigation_state.cursor
        line = self.layout.line_for_position(point)
        if command in ("left", "right"):
            start, end = self.selection
            if not extend and start != end:
                target = start if command == "left" else end
            else:
                if command == "left":
                    target = self.index.previous_boundary(self.cursor)
                else:
                    target = self.index.next_boundary(self.cursor)
            self.move_to(self.position(target), extend)
        elif command in ("up", "down", "page_up", "page_down"):
            delta = {"up": -1, "down": 1, "page_up": -page_lines, "page_down": page_lines}
            target = self.layout.position_at(line + delta[command], model.desired_column)
            self.move_to(target, extend, preserve_column=True)
        else:
            if extend:
                if model.selection_start is None:
                    model.start_selection()
            else:
                model.clear_selection()
            method = {
                "word_left": "left_word", "word_right": "right_word",
                "paragraph_up": "backward_paragraph", "paragraph_down": "forward_paragraph",
                "home": "move_beginning_of_document", "end": "move_end_of_document",
                "line_home": "move_beginning_of_line", "line_end": "move_end_of_line",
            }[command]
            getattr(model, method)()
            model.update_selection_end()
            offset = self.offset(model.navigation_state.cursor)
            # Shared word operations count codepoints. Round in the travel
            # direction so word movement cannot get stuck before a combining mark.
            offset = self.index.snap(offset, "floor" if offset < self.offset(point) else "ceil")
            self.move_to(self.position(offset), extend)

    def delete(self, backward=False):
        def operation():
            if self.selection[0] == self.selection[1]:
                self.move("left" if backward else "right", extend=True)
            self.model.delete_selection()
        return self.edit(operation)

    def tab(self):
        start, _ = self.selection
        column = self.layout.column_for_position(self.position(start))
        return self.insert(" " * (5 - column % 5))

    def toggle_style(self, flag):
        def operation():
            if self.selection[0] != self.selection[1]:
                self.model.toggle_selection_style(flag)
            else:
                self.model.caret_style ^= flag
        return self.edit(operation)

    def transpose_characters(self):
        # Cocoa supplies extended grapheme boundaries, including emoji flags and
        # ZWJ sequences, without changing the shared core's source-offset model.
        def operation():
            point = self.model.navigation_state.cursor
            paragraph = self.model.paragraphs[point.paragraph_index]
            stops = self.boundaries(paragraph)
            right = min(bisect_right(stops, point.character_index), len(stops) - 1)
            if right < 2:
                return
            start, middle, end = stops[right - 2:right + 1]
            flags = self.model.styles[point.paragraph_index]
            text = paragraph[middle:end] + paragraph[start:middle]
            styles = flags[middle:end] + flags[start:middle]
            base = self.offset(DocumentPosition(point.paragraph_index, 0))
            self.select(base + start, base + end)
            self.model.replace_selection(text, [styles])
        return self.edit(operation)

    def find(self, query, start=0, backwards=False):
        # Searching the original string avoids casefold expansion corrupting
        # source ranges (for example ß -> ss). re.IGNORECASE keeps offsets exact.
        import re
        matches = list(re.finditer(re.escape(query), self.value.text, re.IGNORECASE)) if query else []
        if not matches:
            return False
        if backwards:
            match = next((m for m in reversed(matches) if m.start() < start), matches[-1])
        else:
            match = next((m for m in matches if m.start() >= start), matches[0])
        self.select(match.start(), match.end())
        return True

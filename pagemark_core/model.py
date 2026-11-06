from __future__ import annotations

import unicodedata
from abc import ABC, abstractmethod
from contextlib import contextmanager
from dataclasses import dataclass
from enum import IntFlag
from typing import Callable, Optional, List
from .clipboard import Clipboard
from .codec import encode_overstrike_paragraph, parse_overstrike_paragraph
from .buffer import StyledDocument
from .text_layout import display_width
from .coordinates import CellColumn, DocumentPosition
from .layout import layout_paragraph
from .navigation import NavigationState, inherited_style

# Type alias for style masks
StyleMask = List[int]
StyleMasks = List[StyleMask]


class StyleFlags(IntFlag):
    """Text style flags for bold and underline formatting.

    Uses bit flags to support combining styles (e.g., bold + underline).
    """
    NONE = 0
    BOLD = 1
    UNDERLINE = 2
    BOLD_UNDERLINE = BOLD | UNDERLINE


@dataclass
class CursorPosition:
    paragraph_index: int = 0
    character_index: int = 0

    def __lt__(self, other):
        if self.paragraph_index != other.paragraph_index:
            return self.paragraph_index < other.paragraph_index
        return self.character_index < other.character_index

    def __ge__(self, other):
        return not self < other


class TextView(ABC):
    _model: "Optional[TextModel]" = None
    start_paragraph_index: int = 0
    end_paragraph_index: int = 1

    @property
    def model(self):
        assert self._model
        return self._model

    @abstractmethod
    def render(self):
        """Render the view from start_paragraph_index.

        Assume that end_paragraph_index is out of date, so update it.
        If the cursor turns out to be outside the view, center the
        view on the cursor and update both start_pargraph_index and
        end_paragraph_index.

        """


class TextModel:
    """Text model with support for styled text using overstrike encoding.

    The overstrike format represents bold and underline using backspace sequences:
    - Bold: character + backspace + same character (e.g., "X\bX")
    - Underline: underscore + backspace + character (e.g., "_\bX")
    - Bold+Underline: underscore + backspace + character + backspace + same character

    Internally, styles are stored as parallel arrays of bit flags alongside the text.
    """
    paragraphs: List[str]
    cursor_position: CursorPosition
    view: TextView
    styles: StyleMasks
    caret_style: int

    def __init__(self, view: TextView, paragraphs: Optional[List[str]] = None, *,
                 clipboard: Clipboard | None = None):
        self.clipboard = clipboard
        self.view = view
        self.view._model = self
        self.paragraphs = paragraphs if paragraphs is not None else [""]
        self.cursor_position = CursorPosition()
        self.selection_start: Optional[CursorPosition] = None  # CursorPosition when selection started
        self.selection_end: Optional[CursorPosition] = None    # Current end of selection
        # Styling: per-paragraph parallel mask arrays with bit flags
        self.STYLE_BOLD = StyleFlags.BOLD  # Keep for backward compatibility
        self.STYLE_UNDER = StyleFlags.UNDERLINE  # Keep for backward compatibility
        self.styles = [[0]*len(p) for p in self.paragraphs]
        # Caret style used when inserting text; updated on cursor moves
        self.caret_style = 0
        self.desired_column = 0
        self._render_depth = 0
        self._render_pending = False

    def request_render(self) -> None:
        if self._render_depth:
            self._render_pending = True
        else:
            self.view.render()

    @contextmanager
    def defer_render(self):
        """Publish a frame only after the caller finishes its state transition."""
        self._render_depth += 1
        try:
            yield
        finally:
            self._render_depth -= 1
            if self._render_depth == 0 and self._render_pending:
                self._render_pending = False
                self.view.render()

    def _document_buffer(self) -> StyledDocument:
        self._sync_styles_length()
        return StyledDocument.from_parts(self.paragraphs, self.styles)

    def _set_buffer(self, document: StyledDocument) -> None:
        paragraphs = [paragraph.text for paragraph in document.paragraphs]
        styles = [list(paragraph.styles) for paragraph in document.paragraphs]
        self.paragraphs, self.styles = paragraphs, styles

    def _replace_range(self, start: DocumentPosition, end: DocumentPosition,
                       inserted: StyledDocument | None = None) -> None:
        document, cursor = self._document_buffer().replace(
            start, end, inserted if inserted is not None else StyledDocument.plain(""),
        )
        self._set_buffer(document)
        self.cursor_position = CursorPosition(cursor.paragraph_index, cursor.character_index)

    def replace_selection(self, text: str, styles: list[list[int]] | None = None) -> None:
        """Replace selection (or insert at point) as one document operation."""
        start, end = self._selection_bounds() or (self.navigation_state.cursor,) * 2
        inserted = (StyledDocument.from_parts(text.split("\n"), styles) if styles is not None
                    else StyledDocument.plain(text, self.caret_style))
        self._replace_range(start, end, inserted)
        self.clear_selection()
        self.request_render()

    def _selection_bounds(self) -> tuple[DocumentPosition, DocumentPosition] | None:
        if self.selection_start is None or self.selection_end is None:
            return None
        start = DocumentPosition(self.selection_start.paragraph_index, self.selection_start.character_index)
        end = DocumentPosition(self.selection_end.paragraph_index, self.selection_end.character_index)
        return (start, end) if start <= end else (end, start)

    def toggle_selection_style(self, flag: int) -> None:
        bounds = self._selection_bounds()
        if bounds is not None:
            self._set_buffer(self._document_buffer().toggle_style(*bounds, flag))
            self.request_render()

    def _sync_styles_length(self):
        """Ensure styles list mirrors paragraphs lengths (internal safety).

        Optimized to only resize when necessary and preserve existing styles.
        """
        # Fast path: check if sync is needed at all
        if len(self.styles) == len(self.paragraphs):
            # Only check and fix individual paragraph lengths that differ
            for i, para in enumerate(self.paragraphs):
                para_len = len(para)
                style_len = len(self.styles[i])
                if style_len != para_len:
                    # Resize only this specific style array
                    if style_len < para_len:
                        # Extend with zeros
                        self.styles[i].extend([0] * (para_len - style_len))
                    else:
                        # Truncate
                        self.styles[i] = self.styles[i][:para_len]
        else:
            # Full rebuild required - paragraph count changed
            self.styles = [[0]*len(p) for p in self.paragraphs]

    @property
    def navigation_state(self) -> NavigationState:
        cursor = self.cursor_position
        anchor = self.selection_start
        return NavigationState(
            DocumentPosition(cursor.paragraph_index, cursor.character_index),
            DocumentPosition(anchor.paragraph_index, anchor.character_index) if anchor else None,
            CellColumn(self.desired_column), self.caret_style,
        )

    def cursor_column(self, position: DocumentPosition | None = None) -> int:
        position = position or self.navigation_state.cursor
        width = getattr(self.view, "num_columns", 65)
        # TextModel also supports non-terminal views without layout dimensions.
        if not isinstance(width, int):
            width = 65
        return layout_paragraph(self.paragraphs[position.paragraph_index], width).visual_column(position.character_index)

    def relocate_cursor(self, position: DocumentPosition, *, preserve_column: bool = False,
                        caret_style: int | None = None, render: bool = True) -> None:
        state = self.navigation_state.relocate(
            position, self.cursor_column(position), self.styles,
            preserve_column=preserve_column,
            extend_selection=self.selection_start is not None,
            caret_style=caret_style,
        )
        self.cursor_position = CursorPosition(state.cursor.paragraph_index, state.cursor.character_index)
        self.desired_column = state.desired_column
        self.caret_style = state.caret_style
        self.selection_start = (CursorPosition(state.anchor.paragraph_index, state.anchor.character_index)
                                if state.anchor else None)
        self.update_selection_end()
        if render:
            self.request_render()

    def _finish_cursor_move(self) -> None:
        self.relocate_cursor(self.navigation_state.cursor)

    def _update_caret_style_from_position(self):
        self.caret_style = inherited_style(self.navigation_state.cursor, self.styles)

    # --- Serialization with overstrike for bold/underline ---
    def to_overstrike_text(self) -> str:
        """Serialize document to text using overstrike for bold/underline.

        For each character c with style flags:
        - bold: c + '\b' + c
        - underline: '_' + '\b' + c
        - both: '_' + '\b' + c + '\b' + c
        """
        return "\n".join(encode_overstrike_paragraph(
            text, self.styles[i] if i < len(self.styles) else [])
            for i, text in enumerate(self.paragraphs))

    _parse_overstrike_paragraph = staticmethod(parse_overstrike_paragraph)

    @classmethod
    def from_overstrike_text(cls, view: TextView, text: str, *,
                            clipboard: Clipboard | None = None) -> "TextModel":
        paras_raw = text.split('\n') if text else [""]
        paras: List[str] = []
        styles: StyleMasks = []
        for p in paras_raw:
            plain, style_mask = cls._parse_overstrike_paragraph(p)
            paras.append(plain)
            styles.append(style_mask)
        m = cls(view, paragraphs=paras, clipboard=clipboard)
        m.styles = styles
        m._update_caret_style_from_position()
        return m

    def insert_text(self, text: str, position: Optional[CursorPosition] = None):
        position = position or self.cursor_position
        point = DocumentPosition(position.paragraph_index, position.character_index)
        self._replace_range(point, point, StyledDocument.plain(text, self.caret_style))
        self.request_render()

    def backspace(self) -> None:
        point = self.navigation_state.cursor
        if point.character_index > 0:
            self._replace_range(DocumentPosition(point.paragraph_index, point.character_index - 1), point)
        elif point.paragraph_index > 0:
            self._join_with_previous_paragraph()
        self.request_render()

    def _insert_text_with_styles(self, parts: list[str], parts_styles: list[list[int]]):
        point = self.navigation_state.cursor
        self._replace_range(point, point, StyledDocument.from_parts(parts, parts_styles))
        self.request_render()

    def right_char(self):
        if self.cursor_position.character_index < len(self.paragraphs[self.cursor_position.paragraph_index]):
            self.cursor_position.character_index += 1
        elif self.cursor_position.paragraph_index + 1 < len(self.paragraphs):
            self.cursor_position.paragraph_index += 1
            self.cursor_position.character_index = 0
        self._finish_cursor_move()

    def left_char(self):
        if self.cursor_position.character_index > 0:
            self.cursor_position.character_index -= 1
        elif self.cursor_position.paragraph_index > 0:
            self.cursor_position.paragraph_index -= 1
            self.cursor_position.character_index = len(self.paragraphs[self.cursor_position.paragraph_index])
        self._finish_cursor_move()

    def move_beginning_of_document(self) -> None:
        """Move cursor to the beginning of the document (Home)."""
        self.cursor_position.paragraph_index = 0
        self.cursor_position.character_index = 0
        self._finish_cursor_move()

    def move_end_of_document(self) -> None:
        """Move cursor to the end of the document (End)."""
        if self.paragraphs:
            last_idx = len(self.paragraphs) - 1
            self.cursor_position.paragraph_index = last_idx
            self.cursor_position.character_index = len(self.paragraphs[last_idx])
        else:
            self.cursor_position.paragraph_index = 0
            self.cursor_position.character_index = 0
        self._finish_cursor_move()

    def backward_paragraph(self) -> None:
        """Move to beginning of previous non-empty paragraph (M-up).

        Definition: The "previous non-empty paragraph" is the closest paragraph
        at or before the current position that contains text (inclusive). If the
        current paragraph is non-empty and the cursor is not at its beginning,
        move to the beginning of the current paragraph. If already at the
        beginning of a non-empty paragraph, move to the beginning of the
        previous non-empty paragraph, if any. Empty paragraphs are skipped.
        """
        pi = self.cursor_position.paragraph_index

        # If current paragraph is non-empty
        if 0 <= pi < len(self.paragraphs) and len(self.paragraphs[pi]) > 0:
            if self.cursor_position.character_index > 0:
                # Move to beginning of current non-empty paragraph
                self.cursor_position.character_index = 0
            else:
                # At beginning: find previous non-empty paragraph strictly before
                j = pi - 1
                while j >= 0 and len(self.paragraphs[j]) == 0:
                    j -= 1
                if j >= 0:
                    self.cursor_position.paragraph_index = j
                    self.cursor_position.character_index = 0
                # else: already at first non-empty; no movement
        else:
            # Current is empty; go to nearest previous non-empty paragraph
            j = pi - 1
            while j >= 0 and len(self.paragraphs[j]) == 0:
                j -= 1
            if j >= 0:
                self.cursor_position.paragraph_index = j
                self.cursor_position.character_index = 0
            # else: nothing before; no movement

        self._finish_cursor_move()

    def forward_paragraph(self) -> None:
        """Move to beginning of paragraph after the next non-empty (M-down).

        Definition: The "next non-empty paragraph" is the closest paragraph at
        or after the current position that contains text. Move to the beginning
        of the non-empty paragraph following that, if it exists.
        """
        pi = self.cursor_position.paragraph_index

        # Find next non-empty paragraph at or after current
        j = pi
        while j < len(self.paragraphs) and len(self.paragraphs[j]) == 0:
            j += 1

        if j < len(self.paragraphs):
            # Find the next non-empty AFTER j
            k = j + 1
            while k < len(self.paragraphs) and len(self.paragraphs[k]) == 0:
                k += 1
            if k < len(self.paragraphs):
                self.cursor_position.paragraph_index = k
                self.cursor_position.character_index = 0
            # else: no subsequent non-empty paragraph; no movement

        self._finish_cursor_move()

    def count_words(self) -> int:
        """Count the total number of words in the document.

        Returns:
            Total word count
        """
        word_count = 0
        for paragraph in self.paragraphs:
            # Split by whitespace and count non-empty strings
            words = paragraph.split()
            word_count += len(words)
        return word_count

    def transpose_words(self):
        """Transpose word before cursor with word after cursor.

        Emacs behavior: Transpose the words around point, moving forward.
        """
        para_idx = self.cursor_position.paragraph_index
        paragraph = self.paragraphs[para_idx]
        char_idx = self.cursor_position.character_index

        # Find word boundaries
        import re
        words = list(re.finditer(r'\b\w+\b', paragraph))

        if len(words) < 2:
            return

        # Find which words to transpose
        current_word_idx = None
        for i, match in enumerate(words):
            if match.start() <= char_idx <= match.end():
                current_word_idx = i
                break
            elif char_idx < match.start():
                current_word_idx = i - 1 if i > 0 else 0
                break

        if current_word_idx is None:
            # Cursor is after all words
            if len(words) >= 2:
                current_word_idx = len(words) - 2
            else:
                return

        # Ensure we have two words to transpose
        if current_word_idx < 0 or current_word_idx >= len(words) - 1:
            if len(words) >= 2:
                # At end, transpose last two words
                current_word_idx = len(words) - 2
            else:
                return

        # Get the two words to transpose
        word1 = words[current_word_idx]
        word2 = words[current_word_idx + 1]

        # Build the new paragraph
        new_paragraph = (
            paragraph[:word1.start()] +
            word2.group() +
            paragraph[word1.end():word2.start()] +
            word1.group() +
            paragraph[word2.end():]
        )

        # Update paragraph and styles (styles remain with their characters)
        old_styles = self.styles[para_idx]
        new_styles = (
            old_styles[:word1.start()] +
            old_styles[word2.start():word2.end()] +
            old_styles[word1.end():word2.start()] +
            old_styles[word1.start():word1.end()] +
            old_styles[word2.end():]
        )
        self._replace_range(DocumentPosition(para_idx, 0), DocumentPosition(para_idx, len(paragraph)),
                            StyledDocument.from_parts([new_paragraph], [new_styles]))

        # Move cursor to end of transposed region (total length is unchanged)
        self.cursor_position.character_index = word2.end()
        self.request_render()

    def transpose_chars(self):
        """Swap adjacent codepoints and their styles, moving past the pair."""
        pi, ci = self.cursor_position.paragraph_index, self.cursor_position.character_index
        paragraph = self.paragraphs[pi]
        if len(paragraph) < 2:
            return
        first = min(max(0, ci - 1), len(paragraph) - 2)
        self._sync_styles_length()
        text = paragraph[first:first + 2][::-1]
        styles = self.styles[pi][first:first + 2][::-1]
        self._replace_range(DocumentPosition(pi, first), DocumentPosition(pi, first + 2),
                            StyledDocument.from_parts([text], [styles]))
        self.request_render()

    def center_line(self) -> bool:
        """Center the current paragraph if it fits on one line.

        Returns:
            True if centering was successful, False if paragraph is multi-line
        """
        width = self.view.num_columns

        para_idx = self.cursor_position.paragraph_index
        paragraph = self.paragraphs[para_idx]

        # Strip existing leading/trailing spaces to get true content
        stripped = paragraph.strip()

        # Don't center empty lines
        if not stripped:
            self._replace_range(DocumentPosition(para_idx, 0), DocumentPosition(para_idx, len(paragraph)))
            self.request_render()
            return True

        # Check if paragraph would wrap (multi-line) or is at max width
        if display_width(stripped) >= width:
            return False

        # Calculate centering
        spaces_needed = (width - display_width(stripped)) // 2
        centered = ' ' * spaces_needed + stripped

        # Update the paragraph, moving the style mask with its characters
        self._sync_styles_length()
        old_leading = len(paragraph) - len(paragraph.lstrip())
        content_styles = self.styles[para_idx][old_leading:old_leading + len(stripped)]
        original_column = self.cursor_position.character_index
        self._replace_range(DocumentPosition(para_idx, 0), DocumentPosition(para_idx, len(paragraph)),
                            StyledDocument.from_parts([centered], [[0] * spaces_needed + content_styles]))
        self.cursor_position.character_index = original_column

        # Adjust cursor position to account for added spaces
        # If cursor was at the beginning, keep it at the beginning of the centered text
        if self.cursor_position.character_index <= old_leading:
            self.cursor_position.character_index = spaces_needed
        else:
            # Adjust by the difference in leading spaces, clamped to the new
            # length (strip() may also have removed trailing spaces the
            # cursor was sitting in)
            self.cursor_position.character_index = min(
                self.cursor_position.character_index - old_leading + spaces_needed,
                len(centered))

        self.request_render()
        return True


    def _join_with_previous_paragraph(self):
        pi = self.cursor_position.paragraph_index
        if pi == 0:
            return False
        self._replace_range(DocumentPosition(pi - 1, len(self.paragraphs[pi - 1])), DocumentPosition(pi, 0))
        return True

    def _join_with_next_paragraph(self):
        point = self.navigation_state.cursor
        pi = point.paragraph_index
        if pi + 1 >= len(self.paragraphs):
            return False
        self._replace_range(DocumentPosition(pi, len(self.paragraphs[pi])), DocumentPosition(pi + 1, 0))
        self.cursor_position = CursorPosition(pi, point.character_index)
        return True

    def right_word(self):
        """Move cursor forward by one word (Emacs-style)."""
        para = self.paragraphs[self.cursor_position.paragraph_index]
        start = self.cursor_position.character_index
        pos = start
        para_len = len(para)
        # Skip current word characters
        while pos < para_len and not para[pos].isspace():
            pos += 1

        # Skip whitespace
        while pos < para_len and para[pos].isspace():
            pos += 1

        if pos < para_len:
            # Found next word in same paragraph
            self.cursor_position.character_index = pos
        else:
            # Reached end of paragraph while scanning
            if start >= para_len and self.cursor_position.paragraph_index + 1 < len(self.paragraphs):
                # Started at end of paragraph: move to next paragraph start
                self.cursor_position.paragraph_index += 1
                self.cursor_position.character_index = 0
            else:
                # Otherwise stop at end of current paragraph (including when starting
                # at the first letter of the last word)
                self.cursor_position.character_index = para_len

        self._finish_cursor_move()

    def left_word(self):
        """Move cursor backward by one word (Emacs-style)."""
        para = self.paragraphs[self.cursor_position.paragraph_index]
        pos = self.cursor_position.character_index

        if pos > 0:
            # Move back one position to start
            pos -= 1

            # Skip whitespace backwards
            while pos > 0 and para[pos].isspace():
                pos -= 1

            # Skip word characters backwards
            while pos > 0 and not para[pos - 1].isspace():
                pos -= 1

            self.cursor_position.character_index = pos
        elif self.cursor_position.paragraph_index > 0:
            # Move to end of previous paragraph
            self.cursor_position.paragraph_index -= 1
            self.cursor_position.character_index = len(self.paragraphs[self.cursor_position.paragraph_index])

        self._finish_cursor_move()

    def downcase_word(self):
        """Lowercase from the cursor to the end of the current/next word."""
        self._change_word_case(str.lower)

    def upcase_word(self):
        """Uppercase from the cursor to the end of the current/next word."""
        self._change_word_case(str.upper)

    def capitalize_word(self):
        """Uppercase the first character and lowercase the rest of the word."""
        self._change_word_case(str.lower, capitalize=True)

    def _change_word_case(self, convert: Callable[[str], str], *, capitalize: bool = False) -> None:
        para_idx = self.cursor_position.paragraph_index
        paragraph = self.paragraphs[para_idx]
        start = self.cursor_position.character_index
        while start < len(paragraph) and paragraph[start].isspace():
            start += 1
        end = start
        while end < len(paragraph) and not paragraph[end].isspace():
            end += 1
        if start == end:
            return

        word = paragraph[start:end]
        # Convert the complete string to preserve context-sensitive casing,
        # such as Greek final sigma. Individual conversions determine only
        # how many codepoints inherit each source character's style.
        replacement = (word[0].upper() + word[1:].lower()
                       if capitalize else convert(word))
        self._sync_styles_length()
        mask = self.styles[para_idx]
        replacement_styles = []
        for index, char in enumerate(word):
            converted = char.upper() if capitalize and index == 0 else convert(char)
            replacement_styles.extend([mask[start + index]] * len(converted))
        self._replace_range(DocumentPosition(para_idx, start), DocumentPosition(para_idx, end),
                            StyledDocument.from_parts([replacement], [replacement_styles]))
        self._update_caret_style_from_position()
        self.request_render()

    def kill_word(self):
        """Delete from cursor to end of current/next word (Emacs M-d)."""
        para = self.paragraphs[self.cursor_position.paragraph_index]
        pos = self.cursor_position.character_index
        para_len = len(para)

        if pos < para_len:
            end_pos = pos

            # Skip current word if we're in one
            while end_pos < para_len and not para[end_pos].isspace():
                end_pos += 1

            # Skip whitespace after word
            while end_pos < para_len and para[end_pos].isspace():
                end_pos += 1

            # Delete from cursor to end_pos
            pi = self.cursor_position.paragraph_index
            self._replace_range(DocumentPosition(pi, pos), DocumentPosition(pi, end_pos))
        elif self.cursor_position.paragraph_index < len(self.paragraphs) - 1:
            # At end of paragraph, join with next paragraph
            self._join_with_next_paragraph()

        self.request_render()

    def backward_kill_word(self):
        """Delete from cursor back to beginning of previous word (Emacs-style)."""
        para = self.paragraphs[self.cursor_position.paragraph_index]
        pos = self.cursor_position.character_index

        if pos > 0:
            original_pos = pos
            # Move back one position to start
            pos -= 1

            # Skip whitespace backwards
            while pos > 0 and para[pos].isspace():
                pos -= 1

            # Skip word characters backwards
            while pos > 0 and not para[pos - 1].isspace():
                pos -= 1

            # Delete from pos to original position
            pi = self.cursor_position.paragraph_index
            self._replace_range(DocumentPosition(pi, pos), DocumentPosition(pi, original_pos))
        elif self.cursor_position.paragraph_index > 0:
            # At start of paragraph, join with previous paragraph
            self._join_with_previous_paragraph()

        self.request_render()

    def delete_char(self):
        point = self.navigation_state.cursor
        pi, ci = point.paragraph_index, point.character_index
        if ci < len(self.paragraphs[pi]):
            self._replace_range(point, DocumentPosition(pi, ci + 1))
        else:
            self._join_with_next_paragraph()
        self.request_render()

    def _get_visual_line_info(self):
        """Get information about the current visual line.

        Returns:
            Tuple of (line_index, mapper) where mapper is a VisualLineMapper.
        """
        from .layout import get_line_mapper

        para_idx = self.cursor_position.paragraph_index
        char_idx = self.cursor_position.character_index
        para = self.paragraphs[para_idx]

        mapper = get_line_mapper(para, self.view.num_columns)
        line_index = mapper.line_for_char_index(char_idx)

        return line_index, mapper

    def move_beginning_of_line(self):
        """Move cursor to beginning of visual line (Emacs-style Ctrl-A)."""
        line_index, mapper = self._get_visual_line_info()

        # Calculate the start position of this visual line
        self.cursor_position.character_index = mapper.line_start(line_index)

        self._finish_cursor_move()

    def move_end_of_line(self):
        """Move cursor to end of visual line (Emacs-style Ctrl-E)."""
        line_index, mapper = self._get_visual_line_info()

        para_idx = self.cursor_position.paragraph_index
        para = self.paragraphs[para_idx]

        # Move to the end of this visual line
        if line_index == mapper.line_count - 1:
            # Last visual line - go to actual end of paragraph
            self.cursor_position.character_index = len(para)
        else:
            # Not the last line - go to last char of this visual line
            # line_end is the first char of the NEXT line, so subtract 1
            self.cursor_position.character_index = mapper.line_end(line_index) - 1

        self._finish_cursor_move()

    def start_selection(self):
        """Start a new selection at current cursor position."""
        self.selection_start = CursorPosition(
            self.cursor_position.paragraph_index,
            self.cursor_position.character_index
        )
        self.selection_end = CursorPosition(
            self.cursor_position.paragraph_index,
            self.cursor_position.character_index
        )

    def clear_selection(self):
        """Clear the current selection."""
        self.selection_start = None
        self.selection_end = None

    def update_selection_end(self):
        """Update the end of selection to current cursor position."""
        if self.selection_start is not None:
            self.selection_end = CursorPosition(
                self.cursor_position.paragraph_index,
                self.cursor_position.character_index
            )

    def get_selected_text(self) -> str:
        bounds = self._selection_bounds()
        if bounds is None:
            return ""
        return "\n".join(paragraph.text for paragraph in self._document_buffer().slice(*bounds).paragraphs)

    def _get_selected_styles(self):
        bounds = self._selection_bounds()
        if bounds is None:
            return None
        return [list(paragraph.styles) for paragraph in self._document_buffer().slice(*bounds).paragraphs]

    def delete_selection(self) -> bool:
        bounds = self._selection_bounds()
        if bounds is None or bounds[0] == bounds[1]:
            self.clear_selection()
            return False
        self._replace_range(*bounds)
        self.clear_selection()
        self.request_render()
        return True

    def copy_selection(self):
        """Copy selected text to system clipboard."""
        selected = self.get_selected_text()
        if selected:
            # Get styles for selected text
            styles = self._get_selected_styles() if self.selection_start else None
            if self.clipboard is None:
                raise RuntimeError("The front end must provide clipboard access")
            self.clipboard.copy_text(selected, styles)
            return True
        return False

    def cut_selection(self):
        """Cut selected text to clipboard."""
        if self.copy_selection():
            self.delete_selection()
            return True
        return False

    def paste(self):
        """Read and sanitize external content before changing the document."""
        if self.clipboard is None:
            raise RuntimeError("The front end must provide clipboard access")
        text, styles = self.clipboard.paste_text()
        text, styles = self._sanitize_clipboard_content(text, styles)
        # Preserve the existing empty-paste selection replacement policy.
        if text or self.selection_start is not None:
            self.replace_selection(text, styles)

    @staticmethod
    def _keep_insertable_char(ch: str) -> Optional[str]:
        """Map a character to what may enter the document, or None to drop.

        Shared policy for typed and pasted input: characters that break
        fixed-width rendering are excluded. Tabs and non-ASCII space
        separators (em space, narrow NBSP, ...) become a plain space; other
        control characters are dropped. NBSP is kept because bullet
        paragraphs use it as a marker.
        """
        if ch == ' ' or ch == '\xa0':
            return ch
        if ch == '\t' or unicodedata.category(ch) in ('Zs', 'Zl', 'Zp'):
            return ' '
        if ch.isprintable():
            return ch
        return None

    @classmethod
    def _sanitize_clipboard_content(cls, text: str,
                                    styles: Optional[StyleMasks]) -> tuple[str, Optional[StyleMasks]]:
        """Normalize pasted text (line endings, tabs, control characters).

        CR and CRLF become LF; other control characters are dropped. When
        per-paragraph style masks are present they are kept aligned with the
        surviving characters. (Styled text arrives pre-split by the RTF
        parser, which never emits CR, so CR normalization only applies to
        the plain-text path where it cannot desync the masks.)
        """
        if styles is None:
            text = text.replace('\r\n', '\n').replace('\r', '\n')

        parts = text.split('\n')
        out_parts: list[str] = []
        out_styles: StyleMasks = []
        for i, part in enumerate(parts):
            mask = (styles[i] if i < len(styles) else []) if styles is not None else []
            chars: list[str] = []
            flags: StyleMask = []
            for j, ch in enumerate(part):
                kept = cls._keep_insertable_char(ch)
                if kept is not None:
                    chars.append(kept)
                    flags.append(mask[j] if j < len(mask) else 0)
            out_parts.append(''.join(chars))
            out_styles.append(flags)
        return '\n'.join(out_parts), (out_styles if styles is not None else None)

    def kill_line(self):
        """Delete from cursor to end of visual line (Emacs-style Ctrl-K)."""
        line_index, mapper = self._get_visual_line_info()

        para_idx = self.cursor_position.paragraph_index
        char_idx = self.cursor_position.character_index
        para = self.paragraphs[para_idx]

        # End-of-paragraph behavior: join with next paragraph if exists
        if char_idx == len(para):
            if para_idx + 1 < len(self.paragraphs):
                self._join_with_next_paragraph()
            # else: at end of document, nothing to do
            self.request_render()
            return

        # Delete to the end of the current visual line
        visual_line_end = mapper.line_end(line_index)
        if char_idx < visual_line_end:
            self._replace_range(DocumentPosition(para_idx, char_idx), DocumentPosition(para_idx, visual_line_end))

            # After deleting the last visual line of a multi-line paragraph, if we're now
            # at the end of the paragraph and there's a next paragraph,
            # move the cursor to the beginning of the next paragraph
            is_last_visual_line = (line_index == mapper.line_count - 1)
            is_multiline_para = (mapper.line_count > 1)
            at_end_of_para = (char_idx == len(self.paragraphs[para_idx]))
            if is_last_visual_line and is_multiline_para and at_end_of_para and para_idx + 1 < len(self.paragraphs):
                self.cursor_position = CursorPosition(para_idx + 1, 0)
        # else: no change

        self.request_render()


class DocumentModel:
    """Lightweight model for document-level operations.

    This shim exists to support tests that import `DocumentModel` directly
    without requiring a view. It provides a `paragraphs` list and the
    `count_words` method consistent with `TextModel`.
    """

    def __init__(self, paragraphs: Optional[list[str]] = None):
        self.paragraphs = paragraphs if paragraphs is not None else [""]

    def count_words(self) -> int:
        word_count = 0
        for paragraph in self.paragraphs:
            words = paragraph.split()
            word_count += len(words)
        return word_count

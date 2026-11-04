from __future__ import annotations

from typing import Optional
from .model import TextView, CursorPosition
from .constants import EditorConstants
from .layout import (VisualLineMapper, get_line_mapper, render_paragraph,
                     get_hanging_indent_width, expand_styles_for_display)
from .text_layout import display_spans, display_width
try:
    from typing import override
except ImportError:
    def override(func):
        return func


class TerminalTextView(TextView):
    num_rows: int
    num_columns: int
    first_paragraph_line_offset: int = 0
    visual_cursor_y: int = 0
    visual_cursor_x: int = 0  # Store visual horizontal position
    desired_x: int = 0  # Desired X position for up/down navigation
    LINES_PER_PAGE: int = EditorConstants.LINES_PER_PAGE  # Base lines per printed page
    CONTEXT_LINES: int = 2  # Overlap context lines when paging
    _double_spacing: bool = False

    def __init__(self) -> None:
        # Per-instance mutable state (not shared across instances)
        self.lines: list[str] = []
        self.line_styles: list[list[int]] = []
    
    def _adjust_style_slice_for_hanging_indent(self, style_slice: list[int], 
                                                is_wrapped_line: bool, 
                                                paragraph: str) -> list[int]:
        """Adjust style slice to account for hanging indent padding.
        
        When a bullet or numbered paragraph wraps to multiple lines, wrapped lines
        have hanging indent spaces prepended. This method adds corresponding zero
        style flags to the beginning of the style slice to align with the visual
        line positions.
        
        Args:
            style_slice: The style flags from the model for this line's content
            is_wrapped_line: True if this is a wrapped line (not the first line)
            paragraph: The paragraph text to check for hanging indent
            
        Returns:
            Adjusted style slice with hanging indent padding if applicable
        """
        if is_wrapped_line:
            hanging_width = get_hanging_indent_width(paragraph, self.num_columns)
            if hanging_width > 0:
                # Prepend padding for the hanging indent spaces
                return [0] * hanging_width + style_slice
        return style_slice

    def set_double_spacing(self, enabled: bool) -> None:
        self._double_spacing = bool(enabled)

    def _effective_lines_per_page(self) -> int:
        return self.LINES_PER_PAGE // 2 if self._double_spacing else self.LINES_PER_PAGE

    def _create_page_break_line(self, page_num: int) -> str:
        """Create a centered page break line with page number."""
        page_text = f" Page {page_num} "
        padding = (self.num_columns - len(page_text)) // 2
        return "─" * padding + page_text + "─" * (self.num_columns - padding - len(page_text))
    
    def _is_page_break_line(self, line: str) -> bool:
        """Check if a line is a page break line."""
        return "─" in line and "Page" in line
    
    def _should_add_page_break(self, doc_line: int) -> bool:
        """Check if a page break should be added after the given document line."""
        lines_per_page = self._effective_lines_per_page()
        # First check is for lines at the end of first paragraph
        if (doc_line + 1) % lines_per_page == 0 and doc_line > 0:
            return True
        # Second check is for lines in remaining paragraphs
        if doc_line % lines_per_page == (lines_per_page - 1) and doc_line >= (lines_per_page - 1):
            return True
        return False
    
    def _calculate_page_number(self, doc_line: int) -> int:
        """Calculate the page number for a page break after the given line."""
        lpp = self._effective_lines_per_page()
        if (doc_line + 1) % lpp == 0:
            return (doc_line + 1) // lpp + 1
        else:
            return (doc_line // lpp) + 2

    def _get_paragraph_line_count(self, paragraph_index: int) -> int:
        """Get the number of lines in a rendered paragraph."""
        para_lines, _ = render_paragraph(self.model.paragraphs[paragraph_index], self.num_columns)
        return len(para_lines)
    
    def _get_document_line_number(self, paragraph_index: int, line_within_para: int) -> int:
        """Calculate the absolute document line number for a given paragraph and line within it."""
        doc_line = 0
        for i in range(paragraph_index):
            doc_line += self._get_paragraph_line_count(i)
        doc_line += line_within_para
        return doc_line

    @override
    def get_selection_ranges(self):
        """Calculate selection ranges for visible lines.

        Returns:
            List of tuples (start_col, end_col) for each visible line, or None if no selection.
        """
        if self.model.selection_start is None or self.model.selection_end is None:
            return None

        # Get normalized selection bounds
        start = self.model.selection_start
        end = self.model.selection_end
        if (start.paragraph_index > end.paragraph_index or
            (start.paragraph_index == end.paragraph_index and
             start.character_index > end.character_index)):
            start, end = end, start

        selection_ranges = []
        current_para_idx = self.start_paragraph_index
        current_line_offset = self.first_paragraph_line_offset
        current_mapper: Optional[VisualLineMapper] = None

        for line_idx, line in enumerate(self.lines):
            # Skip page break lines consistently
            if self._is_page_break_line(line):
                selection_ranges.append(None)
                continue

            # Check if this line is within selection
            if current_para_idx < start.paragraph_index or current_para_idx > end.paragraph_index:
                selection_ranges.append(None)
            else:
                # This paragraph is at least partially selected
                para = self.model.paragraphs[current_para_idx]
                # Get or refresh mapper for current paragraph
                if current_mapper is None or current_line_offset == 0:
                    current_mapper = get_line_mapper(para, self.num_columns)

                # Get character range for this visual line using mapper
                line_start_char = current_mapper.line_start(current_line_offset)
                line_end_char = current_mapper.line_end(current_line_offset)

                # Get visual offset for hanging indent
                visual_offset = current_mapper.hanging_width if current_mapper.has_hanging_indent(current_line_offset) else 0

                def to_display_col(char_index: int) -> int:
                    return display_width(para[line_start_char:char_index]) + visual_offset

                # Selection endpoints clamped to this line, in char space
                sel_from = line_start_char
                sel_to = line_end_char
                if current_para_idx == start.paragraph_index:
                    sel_from = max(start.character_index, line_start_char)
                if current_para_idx == end.paragraph_index:
                    sel_to = min(end.character_index, line_end_char)

                if sel_from < sel_to:
                    sel_start = to_display_col(sel_from)
                    sel_end = min(display_width(line), to_display_col(sel_to))
                    if sel_to >= line_end_char:
                        # Line fully selected to its end: cover the visible
                        # remainder (wrap separator isn't displayed)
                        sel_end = display_width(line)
                    selection_ranges.append((sel_start, sel_end) if sel_start < sel_end else None)
                else:
                    selection_ranges.append(None)

            # Move to next line
            current_line_offset += 1
            if current_mapper is None:
                current_mapper = get_line_mapper(self.model.paragraphs[current_para_idx], self.num_columns)
            if current_line_offset >= current_mapper.line_count:
                current_para_idx += 1
                current_line_offset = 0
                current_mapper = None  # Will be refreshed for next paragraph

        return selection_ranges
    
    def _display_style_slice(self, para: str, st: list[int], mapper: VisualLineMapper,
                             line_index: int, line_text: str) -> list[int]:
        """Build per-character style flags for the rendered (dash-expanded) text."""
        return mapper.rows[line_index].styles(st)

    @staticmethod
    def _end_char_for_line(mapper: VisualLineMapper, line_index: int) -> int:
        """First character index past a visual line, for "cursor < end" checks.

        A character index exactly at line_end() of a non-final line is a wrap
        boundary, which line_for_char_index places at the start of the NEXT
        visual line — outside a view that ends with this line. For the final
        line of a paragraph, the index equal to the paragraph length is on the
        line itself, so it must be included.
        """
        if line_index >= mapper.line_count - 1:
            return mapper.line_end(line_index) + 1
        return mapper.line_end(line_index)

    def render(self):
        paragraph_index = self.start_paragraph_index
        # First paragraph
        para = self.model.paragraphs[paragraph_index]
        mapper = get_line_mapper(para, self.num_columns)

        # Clamp first_paragraph_line_offset to valid range
        # This handles cases where the paragraph has shrunk after deletion
        if self.first_paragraph_line_offset >= mapper.line_count:
            self.first_paragraph_line_offset = max(0, mapper.line_count - 1)

        # A character index exactly at line_start(offset) is a wrap boundary,
        # which line_for_char_index places at the start of the first visible
        # line, so it is inside the view ("cursor >= start" comparisons).
        start_position = CursorPosition(paragraph_index, mapper.line_start(self.first_paragraph_line_offset))

        # Build lines with page breaks
        self.lines = []
        self.line_styles = []
        doc_line_start = self._get_document_line_number(paragraph_index, self.first_paragraph_line_offset)

        # Add lines from first paragraph. Page-break rows also consume view
        # space, so fewer than lines_wanted content lines may actually fit;
        # track the real count for end_position and doc_lines_added.
        lines_wanted = min(mapper.line_count - self.first_paragraph_line_offset, self.num_rows)
        content_lines_added = 0
        for i in range(lines_wanted):
            if len(self.lines) >= self.num_rows:
                break
            content_lines_added += 1
            doc_line = doc_line_start + i
            line_index = self.first_paragraph_line_offset + i
            # Add the actual content line
            line_text = mapper.lines[line_index]
            self.lines.append(line_text)
            # Build style line from model.styles and paragraph boundaries
            st = self.model.styles[paragraph_index] if hasattr(self.model, 'styles') else []
            self.line_styles.append(
                self._display_style_slice(para, st, mapper, line_index, line_text))
            # Check if there's more content after this line
            has_more_content = (i < lines_wanted - 1) or (paragraph_index + 1 < len(self.model.paragraphs))
            # Add page break if needed and there's more content
            if self._should_add_page_break(doc_line) and has_more_content and len(self.lines) < self.num_rows:
                page_num = self._calculate_page_number(doc_line)
                self.lines.append(self._create_page_break_line(page_num))
                # Add empty style array for page break line to keep indices aligned
                self.line_styles.append([0] * self.num_columns)

        # Set end_position only if we have lines to display
        if content_lines_added > 0:
            last_line_index = self.first_paragraph_line_offset + content_lines_added - 1
            end_position = CursorPosition(paragraph_index, self._end_char_for_line(mapper, last_line_index))
        else:
            # If no lines from this paragraph, set end to start
            end_position = start_position

        # Track total document lines processed
        doc_lines_added = content_lines_added

        # Remaining paragraphs
        while len(self.lines) < self.num_rows and paragraph_index + 1 < len(self.model.paragraphs):
            paragraph_index += 1
            para = self.model.paragraphs[paragraph_index]
            mapper = get_line_mapper(para, self.num_columns)

            for i in range(mapper.line_count):
                if len(self.lines) >= self.num_rows:
                    break
                doc_line = doc_line_start + doc_lines_added
                # Add the actual content line
                line_text = mapper.lines[i]
                self.lines.append(line_text)
                st = self.model.styles[paragraph_index] if hasattr(self.model, 'styles') else []
                self.line_styles.append(
                    self._display_style_slice(para, st, mapper, i, line_text))
                doc_lines_added += 1
                end_position = CursorPosition(paragraph_index, self._end_char_for_line(mapper, i))
                # Check if there's more content after this line
                has_more_content = (i < mapper.line_count - 1) or (paragraph_index + 1 < len(self.model.paragraphs))
                # Add page break if needed and there's more content
                if self._should_add_page_break(doc_line) and has_more_content and len(self.lines) < self.num_rows:
                    page_num = self._calculate_page_number(doc_line)
                    self.lines.append(self._create_page_break_line(page_num))
                    # Add empty style array for page break line to keep indices aligned
                    self.line_styles.append([0] * self.num_columns)

        self.end_paragraph_index = paragraph_index + 1

        # If the cursor is outside the view, center the view on the cursor
        if self.model.cursor_position < start_position or self.model.cursor_position >= end_position:
            self._recenter_and_rerender()
            return

        self._set_visual_cursor_position()

        # The cursor can still wrap visually past the last row (e.g. at the
        # end of a line that exactly fills the width, on the bottom row).
        # Recenter so the cursor row is actually on screen.
        if self.visual_cursor_y >= self.num_rows:
            if not self._recenter_and_rerender():
                self.visual_cursor_y = self.num_rows - 1
            return

        # Add empty line if cursor is at the start of a new visual line
        # This happens when text exactly fills a line and cursor is after it
        if self.visual_cursor_y == len(self.lines) and len(self.lines) < self.num_rows:
            self.lines.append("")
            self.line_styles.append([])

    def _recenter_and_rerender(self) -> bool:
        """Center the view on the cursor and re-render, guarding against
        recursion (render calls this, and this calls render).

        Returns:
            False when already inside a recentering render, in which case
            nothing was done and the caller must cope with the cursor
            position as-is.
        """
        if getattr(self, '_rendering', False):
            return False
        self._rendering = True
        try:
            self.center_view_on_cursor()
            self.render()
        finally:
            self._rendering = False
        return True

    def _set_visual_cursor_position(self):
        # Set visual cursor position accounting for page break lines
        cursor_para_idx = self.model.cursor_position.paragraph_index
        char_idx = self.model.cursor_position.character_index

        # Get document line number at start of view
        doc_line_start = self._get_document_line_number(self.start_paragraph_index, self.first_paragraph_line_offset)

        # Calculate the cursor's document line number
        cursor_doc_line = 0
        for i in range(cursor_para_idx):
            cursor_doc_line += self._get_paragraph_line_count(i)

        # Use VisualLineMapper to find line index and column
        mapper = get_line_mapper(self.model.paragraphs[cursor_para_idx], self.num_columns)
        line_index = mapper.line_for_char_index(char_idx)

        cursor_doc_line += line_index

        # Calculate number of page breaks between start of view and cursor.
        # A page break precedes each line_num that is a multiple of lpp, but
        # the one preceding the view's own top line is above the view and is
        # never rendered, so start counting at doc_line_start + 1.
        page_breaks_before = 0
        lpp = self._effective_lines_per_page()
        for line_num in range(doc_line_start + 1, cursor_doc_line):
            if line_num % lpp == 0:
                page_breaks_before += 1

        # Calculate visual Y position
        self.visual_cursor_y = cursor_doc_line - doc_line_start + page_breaks_before

        # Clamp to visible screen area
        if self.visual_cursor_y < 0:
            self.visual_cursor_y = 0
        elif self.visual_cursor_y >= len(self.lines):
            self.visual_cursor_y = len(self.lines) - 1

        # Skip over page break lines
        while (self.visual_cursor_y < len(self.lines) and
               self._is_page_break_line(self.lines[self.visual_cursor_y])):
            self.visual_cursor_y += 1

        # Calculate visual cursor X position (includes hanging indent offset)
        self.visual_cursor_x = mapper.visual_column(char_idx)

    def center_view_on_cursor(self):
        mapper = get_line_mapper(self.model.paragraphs[self.model.cursor_position.paragraph_index], self.num_columns)
        line_index = mapper.line_for_char_index(self.model.cursor_position.character_index)

        # Center with half the screen above the cursor
        # Note: We don't subtract total page breaks from document start, as that's
        # irrelevant - only page breaks within the view matter, and those will be
        # handled naturally by the render loop
        half_rows = self.num_rows // 2
        self.first_paragraph_line_offset = line_index - half_rows  # Could be negative

        self.start_paragraph_index = self.model.cursor_position.paragraph_index
        while self.first_paragraph_line_offset < 0 and self.start_paragraph_index > 0:
            self.start_paragraph_index -= 1
            prev_mapper = get_line_mapper(self.model.paragraphs[self.start_paragraph_index], self.num_columns)
            self.first_paragraph_line_offset += prev_mapper.line_count
        if self.first_paragraph_line_offset < 0:
            self.first_paragraph_line_offset = 0
    
    def move_cursor_up(self):
        """Move cursor up one visual line, maintaining desired X position."""
        # Find current visual line (skip page breaks going up)
        target_y = self.visual_cursor_y - 1
        while target_y >= 0 and target_y < len(self.lines) and self._is_page_break_line(self.lines[target_y]):
            target_y -= 1
        
        if target_y < 0:
            # Need to move up beyond current view
            if self.start_paragraph_index == 0 and self.first_paragraph_line_offset == 0:
                # At document start, do nothing
                return
            # Move cursor up one line in the document
            self._move_cursor_up_in_document()
            return
        
        # Move cursor to the target line at desired X position
        self._move_cursor_to_visual_line(target_y, self.desired_x)
    
    def move_cursor_down(self):
        """Move cursor down one visual line, maintaining desired X position."""
        # Find next visual line (skip page breaks going down)
        target_y = self.visual_cursor_y + 1
        while target_y < len(self.lines) and self._is_page_break_line(self.lines[target_y]):
            target_y += 1

        if target_y >= len(self.lines):
            # Need to move down beyond current view
            if self._is_at_last_document_line():
                # Cursor is on the very last visual line — nothing below
                return
            # Move cursor down one line in the document
            self._move_cursor_down_in_document()
            return

        # Move cursor to the target line at desired X position
        self._move_cursor_to_visual_line(target_y, self.desired_x)

    def _is_at_last_document_line(self) -> bool:
        """Check if the cursor is on the last visual line of the document."""
        cp = self.model.cursor_position
        if cp.paragraph_index < len(self.model.paragraphs) - 1:
            return False  # Not in the last paragraph
        # In the last paragraph — check if on its last visual line
        para = self.model.paragraphs[cp.paragraph_index]
        mapper = get_line_mapper(para, self.num_columns)
        line_index = mapper.line_for_char_index(cp.character_index)
        return line_index >= mapper.line_count - 1
    
    def _move_cursor_to_visual_line(self, visual_y: int, desired_x: int):
        """Move cursor to a specific visual line at the desired X position."""
        # Map visual Y to document position
        doc_line = self._visual_y_to_document_line(visual_y)
        if doc_line is None:
            return

        # Find which paragraph this line belongs to
        paragraph_index, line_within_para = self._document_line_to_paragraph(doc_line)
        if paragraph_index >= len(self.model.paragraphs):
            return

        # Use VisualLineMapper for coordinate conversion
        mapper = get_line_mapper(self.model.paragraphs[paragraph_index], self.num_columns)

        if line_within_para >= mapper.line_count:
            return

        char_index = self._char_index_for_desired_x(mapper, line_within_para, desired_x)

        # Update cursor position
        self.model.cursor_position.paragraph_index = paragraph_index
        self.model.cursor_position.character_index = char_index

        # Re-render to update visual cursor position
        self.render()
    
    def _visual_y_to_document_line(self, visual_y: int) -> Optional[int]:
        """Convert visual Y position to document line number."""
        if visual_y < 0 or visual_y >= len(self.lines):
            return None
        
        # Count non-page-break lines from start of view
        doc_line_start = self._get_document_line_number(self.start_paragraph_index, self.first_paragraph_line_offset)
        doc_line = doc_line_start
        
        for i in range(visual_y + 1):
            if i < len(self.lines) and not self._is_page_break_line(self.lines[i]):
                if i < visual_y:
                    doc_line += 1
        
        return doc_line
    
    def _document_line_to_paragraph(self, doc_line: int) -> tuple[int, int]:
        """Convert document line number to paragraph index and line within paragraph."""
        current_line = 0
        for para_idx in range(len(self.model.paragraphs)):
            para_line_count = self._get_paragraph_line_count(para_idx)
            if current_line + para_line_count > doc_line:
                return (para_idx, doc_line - current_line)
            current_line += para_line_count
        # Line is beyond document
        return (len(self.model.paragraphs) - 1, 0)
    
    def _move_cursor_up_in_document(self):
        """Move cursor up one line in the document and center view."""
        # Get current document line
        doc_line = self._visual_y_to_document_line(0) - 1  # Line above current view
        if doc_line < 0:
            return

        # Convert to paragraph and line within paragraph
        paragraph_index, line_within_para = self._document_line_to_paragraph(doc_line)

        # Use VisualLineMapper for coordinate conversion
        mapper = get_line_mapper(self.model.paragraphs[paragraph_index], self.num_columns)

        if line_within_para >= mapper.line_count:
            return

        # Calculate character index using the mapper
        char_index = self._char_index_for_desired_x(mapper, line_within_para)

        # Update cursor position
        self.model.cursor_position.paragraph_index = paragraph_index
        self.model.cursor_position.character_index = char_index

        # Center view on the cursor
        self.center_view_on_cursor()
        self.render()
    
    def _char_index_for_desired_x(self, mapper: VisualLineMapper, line_within_para: int,
                                  desired_x: Optional[int] = None) -> int:
        """Calculate the character index for a visual X position on a given line.

        This helper centralizes the logic for mapping a visual X position
        (self.desired_x unless given explicitly) to a character index,
        accounting for hanging indents. The result always stays on the
        requested visual line: line_content_length() includes the separator
        space consumed by word wrap, and landing exactly on that boundary
        index would put the cursor on the NEXT visual line (see
        line_for_char_index), which made vertical movement skip or stall.
        """
        if desired_x is None:
            desired_x = self.desired_x
        return mapper.character_at_column(line_within_para, desired_x)

    def _move_cursor_down_in_document(self):
        """Move cursor down one line in the document and center view."""
        # Get current document line
        last_visual_y = len(self.lines) - 1
        while last_visual_y >= 0 and self._is_page_break_line(self.lines[last_visual_y]):
            last_visual_y -= 1
        doc_line = self._visual_y_to_document_line(last_visual_y) + 1  # Line below current view

        # Convert to paragraph and line within paragraph
        paragraph_index, line_within_para = self._document_line_to_paragraph(doc_line)
        if paragraph_index >= len(self.model.paragraphs):
            return

        # Use VisualLineMapper for coordinate conversion
        mapper = get_line_mapper(self.model.paragraphs[paragraph_index], self.num_columns)

        if line_within_para >= mapper.line_count:
            return

        # Calculate character index using the mapper
        char_index = self._char_index_for_desired_x(mapper, line_within_para)

        # Update cursor position
        self.model.cursor_position.paragraph_index = paragraph_index
        self.model.cursor_position.character_index = char_index
        
        # Center view on the cursor
        self.center_view_on_cursor()
        self.render()
    
    def update_desired_x(self):
        """Update the desired X position based on current cursor position."""
        self.desired_x = self.visual_cursor_x

    # --- Paging (Emacs-style C-v / M-v) ---
    def _total_document_lines(self) -> int:
        total = 0
        for i in range(len(self.model.paragraphs)):
            total += self._get_paragraph_line_count(i)
        return total

    def _page_breaks_between(self, start_doc_line: int, end_doc_line_exclusive: int) -> int:
        """Count page break lines that would be inserted between start (inclusive)
        and end (exclusive) document lines.

        Page break lines are virtual lines inserted after certain document
        lines; reuse the same condition used in render.
        """
        count = 0
        for ln in range(max(0, start_doc_line), max(0, end_doc_line_exclusive)):
            if self._should_add_page_break(ln):
                count += 1
        return count

    def _doc_top_line(self) -> int:
        return self._get_document_line_number(self.start_paragraph_index, self.first_paragraph_line_offset)

    def _set_view_top_to_doc_line(self, doc_line: int) -> None:
        para_idx, line_in_para = self._document_line_to_paragraph(doc_line)
        self.start_paragraph_index = para_idx
        self.first_paragraph_line_offset = line_in_para

    def _cursor_doc_line(self) -> int:
        """Compute the document line where the cursor is (counting content lines only)."""
        cursor_para_idx = self.model.cursor_position.paragraph_index
        doc_line = 0
        for i in range(cursor_para_idx):
            doc_line += self._get_paragraph_line_count(i)
        # Which wrapped line contains the cursor
        mapper = get_line_mapper(self.model.paragraphs[cursor_para_idx], self.num_columns)
        line_idx = mapper.line_for_char_index(self.model.cursor_position.character_index)
        return doc_line + line_idx

    def _set_cursor_to_doc_line_start(self, doc_line: int) -> None:
        """Set cursor to the start of a document line."""
        para_idx, line_in_para = self._document_line_to_paragraph(doc_line)
        mapper = get_line_mapper(self.model.paragraphs[para_idx], self.num_columns)
        char_index = mapper.line_start(line_in_para)
        self.model.cursor_position.paragraph_index = para_idx
        self.model.cursor_position.character_index = char_index

    def _set_cursor_to_doc_line_desired_x(self, doc_line: int) -> None:
        """Position cursor on a document line using desired_x, clamped visually.

        Keeps the internal desired_x intact while placing the cursor at the
        nearest valid position on the target visual line (respecting hanging
        indent on wrapped lines).
        """
        para_idx, line_in_para = self._document_line_to_paragraph(doc_line)
        if para_idx >= len(self.model.paragraphs):
            return

        mapper = get_line_mapper(self.model.paragraphs[para_idx], self.num_columns)
        if line_in_para >= mapper.line_count:
            return

        char_index = self._char_index_for_desired_x(mapper, line_in_para)
        self.model.cursor_position.paragraph_index = para_idx
        self.model.cursor_position.character_index = char_index

    def scroll_page_down(self) -> None:
        # Scroll forward: one screenful minus context
        target_visual = max(1, self.num_rows - self.CONTEXT_LINES)
        top = self._doc_top_line()
        total = self._total_document_lines()
        # Adjust for page-break lines so we move by target visual lines
        d = min(target_visual, max(0, total - 1 - top))
        # Iterate to account for page breaks introduced in range
        for _ in range(5):
            breaks = self._page_breaks_between(top, top + d)
            eff = d + breaks
            if eff == target_visual:
                break
            if eff > target_visual and d > 0:
                d -= min(eff - target_visual, d)
            elif eff < target_visual:
                room = max(0, total - 1 - (top + d))
                inc = min(target_visual - eff, room)
                if inc == 0:
                    break
                d += inc
            else:
                break
        new_top = min(max(0, total - 1), top + d)

        # Adjust view
        self._set_view_top_to_doc_line(new_top)

        # Cursor behavior: if cursor above new_top, move to top line at desired_x
        cursor_line = self._cursor_doc_line()
        if cursor_line < new_top:
            self._set_cursor_to_doc_line_desired_x(new_top)
        # Re-render
        self.render()

    def scroll_page_up(self) -> None:
        # Scroll backward: one screenful minus context
        target_visual = max(1, self.num_rows - self.CONTEXT_LINES)
        top = self._doc_top_line()
        # Determine backward doc-line movement accounting for page breaks
        d = min(target_visual, top)
        for _ in range(5):
            breaks = self._page_breaks_between(top - d, top)
            eff = d + breaks
            if eff == target_visual:
                break
            if eff > target_visual and d > 0:
                d -= min(eff - target_visual, d)
            elif eff < target_visual:
                inc = min(target_visual - eff, top - d)
                if inc == 0:
                    break
                d += inc
            else:
                break
        new_top = max(0, top - d)

        # Adjust view
        self._set_view_top_to_doc_line(new_top)

        # Cursor behavior: if cursor below bottom, move to bottom line of view
        cursor_line = self._cursor_doc_line()
        approx_bottom = new_top + max(0, self.num_rows - 1)
        total = self._total_document_lines()
        if cursor_line > approx_bottom:
            bottom_line = min(total - 1, approx_bottom)
            self._set_cursor_to_doc_line_desired_x(bottom_line)
        # Re-render
        self.render()

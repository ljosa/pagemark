from typing import Optional
from dataclasses import dataclass
import re
# Provide a no-op override decorator on Python < 3.12
try:
    from typing import override  # type: ignore
except ImportError:  # pragma: no cover - compatibility shim
    def override(func):
        return func
from .model import TextView, CursorPosition
from .constants import EditorConstants


@dataclass
class VisualLineMapper:
    """Maps between character indices and visual line positions.

    This class centralizes the logic for converting between:
    - Character indices in the paragraph text
    - Visual line indices (which wrapped line)
    - Column positions within a visual line

    The cumulative_counts array contains character counts at the END of each
    visual line. So cumulative_counts[i] is the character index of the first
    character of line i+1 (or paragraph length for the last line).

    Key semantic: A character index that exactly equals cumulative_counts[i]
    is considered to be at the START of line i+1, not at the END of line i.
    """
    lines: list[str]
    cumulative_counts: list[int]
    hanging_width: int = 0

    @property
    def line_count(self) -> int:
        """Number of visual lines."""
        return len(self.lines)

    def line_start(self, line_index: int) -> int:
        """Return the character index where a visual line starts."""
        if line_index <= 0:
            return 0
        if line_index >= len(self.cumulative_counts):
            return self.cumulative_counts[-1] if self.cumulative_counts else 0
        return self.cumulative_counts[line_index - 1]

    def line_end(self, line_index: int) -> int:
        """Return the character index where a visual line ends (exclusive).

        This is the index of the first character of the NEXT line,
        or the paragraph length for the last line.
        """
        if line_index < 0:
            return 0
        if line_index >= len(self.cumulative_counts):
            return self.cumulative_counts[-1] if self.cumulative_counts else 0
        return self.cumulative_counts[line_index]

    def line_for_char_index(self, char_index: int) -> int:
        """Find which visual line contains a character index.

        If char_index exactly equals a line boundary (cumulative_counts[i]),
        it is considered to be at the START of the next line (i+1).
        """
        # Handle boundary case: exactly at a line end means start of next line
        for i in range(len(self.cumulative_counts) - 1):
            if char_index == self.cumulative_counts[i]:
                return i + 1
        # Normal case: find first line whose end is past char_index
        for i, count in enumerate(self.cumulative_counts):
            if char_index < count:
                return i
        return len(self.cumulative_counts) - 1

    def char_to_line_and_column(self, char_index: int) -> tuple[int, int]:
        """Convert a character index to (line_index, column).

        The column is the position within the line's content (not counting
        visual hanging indent padding).
        """
        line_index = self.line_for_char_index(char_index)
        start = self.line_start(line_index)
        column = char_index - start
        return (line_index, column)

    def line_and_column_to_char(self, line_index: int, column: int) -> int:
        """Convert (line_index, column) to a character index.

        The column should be the content position (not counting visual
        hanging indent padding).
        """
        start = self.line_start(line_index)
        return start + column

    def visual_column(self, char_index: int) -> int:
        """Get the visual column for a character index.

        This accounts for hanging indent on wrapped lines.
        """
        line_index, column = self.char_to_line_and_column(char_index)
        if line_index > 0 and self.hanging_width > 0:
            return column + self.hanging_width
        return column

    def content_column_from_visual(self, line_index: int, visual_column: int) -> int:
        """Convert a visual column to content column for a specific line.

        Accounts for hanging indent on wrapped lines.
        """
        if line_index > 0 and self.hanging_width > 0:
            # Clamp clicks in the indent area to the first content position
            if visual_column <= self.hanging_width:
                return 0
            return visual_column - self.hanging_width
        return visual_column

def _get_hanging_indent_width(paragraph: str) -> int:
    """Return hanging indent width for bullet/numbered paragraphs.

    Detects optional leading spaces, then one of:
    - '-' or '*' followed by exactly one space
    - one or more digits followed by '.' or ')' and exactly one space

    Returns total columns before first text char (base indent + marker + one space),
    or 0 if not a bullet/numbered paragraph.
    """
    # Leading spaces
    # Require exactly one space after the marker by asserting the next
    # character is non-space. This prevents triggering on multiple spaces.
    m = re.match(r"^(\s*)(?:([-*]) (?=\S)|((?:\d+)(?:[\.)]) (?=\S)))", paragraph)
    if not m:
        return 0
    leading = m.group(1) or ""
    marker = m.group(2)
    numbered = m.group(3)
    if marker is not None:
        # '-' or '*' with exactly one trailing space matched
        return len(leading) + len(marker) + 1
    if numbered is not None:
        # '\d+.' or '\d+)' with exactly one trailing space matched
        return len(leading) + len(numbered)
    return 0


def get_hanging_indent_width(paragraph: str) -> int:
    """Public helper: return hanging indent width for bullets/numbers.

    This wraps the internal implementation to provide a stable API for
    other modules (e.g., printing/formatting) without importing a private
    function.
    """
    return _get_hanging_indent_width(paragraph)


def render_paragraph(paragraph: str, num_columns: int) -> tuple[list[str], list[int]]:
    """Render into a list of lines, with word wrap and hanging indents.

    Returns (lines, cumulative_counts) where cumulative_counts are character
    counts in the original paragraph at the end of each visual line. Visual
    indent spaces for wrapped bullet/numbered paragraphs are not counted in
    cumulative_counts.
    """
    if not paragraph:
        return ([""], [0])

    hanging_width = _get_hanging_indent_width(paragraph)
    indent_prefix = " " * hanging_width if hanging_width > 0 else ""

    lines: list[str] = []
    cumulative_counts: list[int] = []
    char_count = 0
    words = paragraph.split(" ")
    current_line: Optional[str] = None
    line_index = 0

    def available_width_for_line(idx: int) -> int:
        if idx == 0:
            return num_columns
        return num_columns - hanging_width if hanging_width > 0 else num_columns

    for word in words:
        width = available_width_for_line(line_index)
        if current_line is None:
            # First word on the line
            if len(word) >= width:
                # Break long word across as many lines as needed
                while len(word) >= width:
                    prefix = indent_prefix if (line_index > 0 and hanging_width > 0) else ""
                    lines.append(prefix + word[:width])
                    char_count += width
                    cumulative_counts.append(char_count)
                    word = word[width:]
                    line_index += 1
                    width = available_width_for_line(line_index)
                current_line = word
            else:
                current_line = word
        else:
            # Check if word fits on current line (plus a space)
            if len(current_line) + 1 + len(word) < width:
                current_line += " " + word
            else:
                # Commit current line
                prefix = indent_prefix if (line_index > 0 and hanging_width > 0) else ""
                lines.append(prefix + current_line)
                char_count += len(current_line) + 1  # +1 for the space that would have been added
                cumulative_counts.append(char_count)
                line_index += 1
                width = available_width_for_line(line_index)
                # Place the word on the new line, breaking if needed
                if len(word) >= width:
                    while len(word) >= width:
                        prefix = indent_prefix if (line_index > 0 and hanging_width > 0) else ""
                        lines.append(prefix + word[:width])
                        char_count += width
                        cumulative_counts.append(char_count)
                        word = word[width:]
                        line_index += 1
                        width = available_width_for_line(line_index)
                    current_line = word
                else:
                    current_line = word

    assert current_line is not None
    # Append the final line
    prefix = indent_prefix if (line_index > 0 and hanging_width > 0) else ""
    lines.append(prefix + current_line)
    char_count += len(current_line)
    cumulative_counts.append(char_count)

    return (lines, cumulative_counts)


def get_line_mapper(paragraph: str, num_columns: int) -> VisualLineMapper:
    """Create a VisualLineMapper for a paragraph.

    This is the preferred way to work with visual line mappings.
    It provides methods to convert between character indices and
    line/column positions.
    """
    lines, cumulative_counts = render_paragraph(paragraph, num_columns)
    hanging_width = _get_hanging_indent_width(paragraph)
    return VisualLineMapper(
        lines=lines,
        cumulative_counts=cumulative_counts,
        hanging_width=hanging_width
    )


class TerminalTextView(TextView):
    num_rows: int
    num_columns: int
    first_paragraph_line_offset: int = 0
    lines: list[str] = []
    line_styles: list[list[int]] = []  # per-line style flags per column (bold/underline)
    visual_cursor_y: int = 0
    visual_cursor_x: int = 0  # Store visual horizontal position
    desired_x: int = 0  # Desired X position for up/down navigation
    LINES_PER_PAGE: int = EditorConstants.LINES_PER_PAGE  # Base lines per printed page
    CONTEXT_LINES: int = 2  # Overlap context lines when paging
    _double_spacing: bool = False
    
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
            hanging_width = _get_hanging_indent_width(paragraph)
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
                _, para_counts = render_paragraph(para, self.num_columns)
                
                # Calculate character range for this visual line
                if current_line_offset == 0:
                    line_start_char = 0
                else:
                    line_start_char = para_counts[current_line_offset - 1]

                if current_line_offset < len(para_counts):
                    line_end_char = para_counts[current_line_offset]
                else:
                    line_end_char = len(para)
                
                # Calculate selection within this line
                sel_start = 0
                sel_end = len(line)
                # Hanging indent offset for wrapped lines
                hanging_width = _get_hanging_indent_width(para)
                visual_offset = hanging_width if (current_line_offset > 0 and hanging_width > 0) else 0
                
                if current_para_idx == start.paragraph_index:
                    if start.character_index > line_start_char:
                        sel_start = max(0, start.character_index - line_start_char) + visual_offset
                    else:
                        sel_start = 0 + visual_offset
                
                if current_para_idx == end.paragraph_index:
                    if end.character_index < line_end_char:
                        sel_end = min(len(line), (end.character_index - line_start_char) + visual_offset)
                    else:
                        sel_end = min(len(line), len(line))
                
                if sel_start < sel_end:
                    selection_ranges.append((sel_start, sel_end))
                else:
                    selection_ranges.append(None)
            
            # Move to next line
            current_line_offset += 1
            para_line_count = self._get_paragraph_line_count(current_para_idx)
            if current_line_offset >= para_line_count:
                current_para_idx += 1
                current_line_offset = 0
        
        return selection_ranges
    
    def render(self):
        paragraph_index = self.start_paragraph_index
        # First paragraph
        para = self.model.paragraphs[paragraph_index]
        para_lines, para_counts = render_paragraph(para, self.num_columns)
        
        # Clamp first_paragraph_line_offset to valid range
        # This handles cases where the paragraph has shrunk after deletion
        if self.first_paragraph_line_offset >= len(para_lines):
            self.first_paragraph_line_offset = max(0, len(para_lines) - 1)
        
        if self.first_paragraph_line_offset == 0:
            start_position = CursorPosition(paragraph_index, 0)
        else:
            start_position = CursorPosition(paragraph_index, para_counts[self.first_paragraph_line_offset - 1] + 1)
        
        # Build lines with page breaks
        self.lines = []
        self.line_styles = []
        doc_line_start = self._get_document_line_number(paragraph_index, self.first_paragraph_line_offset)
        
        # Add lines from first paragraph
        lines_wanted = min(len(para_lines) - self.first_paragraph_line_offset, self.num_rows)
        for i in range(lines_wanted):
            if len(self.lines) >= self.num_rows:
                break
            doc_line = doc_line_start + i
            # Add the actual content line
            line_text = para_lines[self.first_paragraph_line_offset + i]
            self.lines.append(line_text)
            # Build style line from model.styles and paragraph boundaries
            start_ci = 0 if (self.first_paragraph_line_offset + i) == 0 else para_counts[self.first_paragraph_line_offset + i - 1]
            end_ci = para_counts[self.first_paragraph_line_offset + i]
            st = self.model.styles[paragraph_index] if hasattr(self.model, 'styles') else []
            style_slice = st[start_ci:end_ci] if st else [0]*len(line_text)
            # Account for hanging indent padding on wrapped lines
            line_index = self.first_paragraph_line_offset + i
            style_slice = self._adjust_style_slice_for_hanging_indent(style_slice, line_index > 0, para)
            style_slice = (style_slice + [0]*max(0, len(line_text)-len(style_slice)))[:len(line_text)]
            self.line_styles.append(style_slice)
            # Check if there's more content after this line
            has_more_content = (i < lines_wanted - 1) or (paragraph_index + 1 < len(self.model.paragraphs))
            # Add page break if needed and there's more content
            if self._should_add_page_break(doc_line) and has_more_content and len(self.lines) < self.num_rows:
                page_num = self._calculate_page_number(doc_line)
                self.lines.append(self._create_page_break_line(page_num))
                # Add empty style array for page break line to keep indices aligned
                self.line_styles.append([0] * self.num_columns)
        
        # Set end_position only if we have lines to display
        if lines_wanted > 0:
            end_position = CursorPosition(paragraph_index, para_counts[self.first_paragraph_line_offset + lines_wanted - 1] + 1)
        else:
            # If no lines from this paragraph, set end to start
            end_position = start_position
        
        # Track total document lines processed
        doc_lines_added = lines_wanted
        
        # Remaining paragraphs
        while len(self.lines) < self.num_rows and paragraph_index + 1 < len(self.model.paragraphs):
            paragraph_index += 1
            para = self.model.paragraphs[paragraph_index]
            para_lines, para_counts = render_paragraph(para, self.num_columns)
            
            for i in range(len(para_lines)):
                if len(self.lines) >= self.num_rows:
                    break
                doc_line = doc_line_start + doc_lines_added
                # Add the actual content line
                line_text = para_lines[i]
                self.lines.append(line_text)
                st = self.model.styles[paragraph_index] if hasattr(self.model, 'styles') else []
                start_ci = 0 if i == 0 else para_counts[i-1]
                end_ci = para_counts[i]
                style_slice = st[start_ci:end_ci] if st else [0]*len(line_text)
                # Account for hanging indent padding on wrapped lines
                style_slice = self._adjust_style_slice_for_hanging_indent(style_slice, i > 0, para)
                style_slice = (style_slice + [0]*max(0, len(line_text)-len(style_slice)))[:len(line_text)]
                self.line_styles.append(style_slice)
                doc_lines_added += 1
                end_position = CursorPosition(paragraph_index, para_counts[i] + 1)
                # Check if there's more content after this line
                has_more_content = (i < len(para_lines) - 1) or (paragraph_index + 1 < len(self.model.paragraphs))
                # Add page break if needed and there's more content
                if self._should_add_page_break(doc_line) and has_more_content and len(self.lines) < self.num_rows:
                    page_num = self._calculate_page_number(doc_line)
                    self.lines.append(self._create_page_break_line(page_num))
                    # Add empty style array for page break line to keep indices aligned
                    self.line_styles.append([0] * self.num_columns)
        
        self.end_paragraph_index = paragraph_index + 1

        # If the cursor is outside the view, center the view on the cursor
        if self.model.cursor_position < start_position or self.model.cursor_position >= end_position:
            if not getattr(self, '_rendering', False):
                self._rendering = True
                try:
                    self.center_view_on_cursor()
                    # Re-render after centering (recursive call)
                    self.render()
                finally:
                    self._rendering = False
            return

        self._set_visual_cursor_position()

        # Add empty line if cursor is at the start of a new visual line
        # This happens when text exactly fills a line and cursor is after it
        if self.visual_cursor_y == len(self.lines) and len(self.lines) < self.num_rows:
            self.lines.append("")
            self.line_styles.append([])

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

        # Calculate number of page breaks between start of view and cursor
        page_breaks_before = 0
        lpp = self._effective_lines_per_page()
        for line_num in range(doc_line_start, cursor_doc_line):
            if line_num > 0 and line_num % lpp == 0:
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

        # Handle cursor at end of line that exactly fills width
        if self.visual_cursor_x == self.num_columns:
            # Cursor wraps to start of next line
            self.visual_cursor_y += 1
            # Skip page break if present
            while (self.visual_cursor_y < len(self.lines) and 
                   self._is_page_break_line(self.lines[self.visual_cursor_y])):
                self.visual_cursor_y += 1
            self.visual_cursor_x = 0
        elif self.visual_cursor_x < 0:
            self.visual_cursor_x = 0
        elif self.visual_cursor_x > self.num_columns:
            # This shouldn't happen with proper wrapping
            self.visual_cursor_x = self.num_columns - 1

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
            if self.end_paragraph_index >= len(self.model.paragraphs):
                # At document end, do nothing
                return
            # Move cursor down one line in the document
            self._move_cursor_down_in_document()
            return
        
        # Move cursor to the target line at desired X position
        self._move_cursor_to_visual_line(target_y, self.desired_x)
    
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

        line_text = mapper.lines[line_within_para]
        # Convert visual X to content column, clamped to line length
        content_x = mapper.content_column_from_visual(line_within_para, desired_x)
        # Get actual line content length (excluding hanging indent prefix)
        line_content_len = len(line_text) - (mapper.hanging_width if line_within_para > 0 else 0)
        content_x = min(content_x, line_content_len)

        # Convert to character index
        char_index = mapper.line_and_column_to_char(line_within_para, content_x)

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
    
    def _char_index_for_desired_x(self, mapper: VisualLineMapper, line_within_para: int) -> int:
        """Calculate the character index for desired_x on a given line.

        This helper centralizes the logic for mapping a visual X position
        (desired_x) to a character index, accounting for hanging indents.
        """
        line_text = mapper.lines[line_within_para]
        # Get actual line content length (excluding hanging indent prefix)
        line_content_len = len(line_text) - (mapper.hanging_width if line_within_para > 0 else 0)

        # Convert visual X to content column
        content_x = mapper.content_column_from_visual(line_within_para, self.desired_x)
        content_x = min(content_x, line_content_len)

        return mapper.line_and_column_to_char(line_within_para, content_x)

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
        # Compute the document line where the cursor is (counting content lines only)
        cursor_para_idx = self.model.cursor_position.paragraph_index
        doc_line = 0
        for i in range(cursor_para_idx):
            doc_line += self._get_paragraph_line_count(i)
        # Which wrapped line contains the cursor
        _, para_counts = render_paragraph(self.model.paragraphs[cursor_para_idx], self.num_columns)
        line_idx = 0
        char_idx = self.model.cursor_position.character_index
        for i, count in enumerate(para_counts):
            if char_idx < count:
                line_idx = i
                break
        else:
            line_idx = len(para_counts) - 1
        return doc_line + line_idx

    def _set_cursor_to_doc_line_start(self, doc_line: int) -> None:
        para_idx, line_in_para = self._document_line_to_paragraph(doc_line)
        para = self.model.paragraphs[para_idx]
        _, counts = render_paragraph(para, self.num_columns)
        if line_in_para == 0:
            char_index = 0
        else:
            char_index = counts[line_in_para - 1]
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

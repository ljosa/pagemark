from typing import override
from .model import TextView, CursorPosition
from .constants import EditorConstants

def _break_long_word(word: str, num_columns: int, lines: list[str], 
                     cumulative_counts: list[int], char_count: int) -> tuple[str, int]:
    """Break a word that's too long to fit on one line.
    
    Returns the remaining part of the word and updated char_count.
    """
    while len(word) >= num_columns:
        lines.append(word[:num_columns])
        char_count += num_columns
        cumulative_counts.append(char_count)
        word = word[num_columns:]
    return word, char_count


def render_paragraph(paragraph: str, num_columns: int) -> tuple[list[str], list[int]]:
    """Render into a list of lines, at most num_columns long, with word wrap.

    As a second return value, return the cumulative character
    counts at the end of each line.

    """
    if not paragraph:
        return ([""], [0])

    lines = []
    cumulative_counts = []
    char_count = 0
    words = paragraph.split(" ")
    current_line = None

    for word in words:
        if current_line is None:
            # First word on the line
            if len(word) >= num_columns:
                # Word is too long, break it
                word, char_count = _break_long_word(word, num_columns, lines, 
                                                   cumulative_counts, char_count)
            current_line = word
        else:
            # Check if word fits on current line
            if len(current_line) + 1 + len(word) < num_columns:
                current_line += " " + word
            else:
                # Start new line
                lines.append(current_line)
                char_count += len(current_line) + 1  # +1 for the space that would have been added
                cumulative_counts.append(char_count)
                if len(word) >= num_columns:
                    # Word is too long, break it
                    word, char_count = _break_long_word(word, num_columns, lines,
                                                       cumulative_counts, char_count)
                current_line = word

    assert current_line is not None
    lines.append(current_line)
    char_count += len(current_line)
    cumulative_counts.append(char_count)

    return (lines, cumulative_counts)


class TerminalTextView(TextView):
    num_rows: int
    num_columns: int
    first_paragraph_line_offset: int = 0
    lines: list[str] = []
    visual_cursor_y: int = 0
    visual_cursor_x: int = 0  # Store visual horizontal position
    desired_x: int = 0  # Desired X position for up/down navigation
    LINES_PER_PAGE: int = EditorConstants.LINES_PER_PAGE  # Standard lines per printed page

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
        # First check is for lines at the end of first paragraph
        if (doc_line + 1) % self.LINES_PER_PAGE == 0 and doc_line > 0:
            return True
        # Second check is for lines in remaining paragraphs
        if doc_line % self.LINES_PER_PAGE == (self.LINES_PER_PAGE - 1) and doc_line >= (self.LINES_PER_PAGE - 1):
            return True
        return False
    
    def _calculate_page_number(self, doc_line: int) -> int:
        """Calculate the page number for a page break after the given line."""
        if (doc_line + 1) % self.LINES_PER_PAGE == 0:
            return (doc_line + 1) // self.LINES_PER_PAGE + 1
        else:
            return (doc_line // self.LINES_PER_PAGE) + 2

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
                
                if current_line_offset < len(para_counts) - 1:
                    line_end_char = para_counts[current_line_offset]
                else:
                    line_end_char = len(para)
                
                # Calculate selection within this line
                sel_start = 0
                sel_end = len(line)
                
                if current_para_idx == start.paragraph_index:
                    if start.character_index > line_start_char:
                        sel_start = max(0, start.character_index - line_start_char)
                
                if current_para_idx == end.paragraph_index:
                    if end.character_index < line_end_char:
                        sel_end = min(len(line), end.character_index - line_start_char)
                
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
        para_lines, para_counts = render_paragraph(self.model.paragraphs[paragraph_index], self.num_columns)
        if self.first_paragraph_line_offset == 0:
            start_position = CursorPosition(paragraph_index, 0)
        else:
            start_position = CursorPosition(paragraph_index, para_counts[self.first_paragraph_line_offset - 1] + 1)
        
        # Build lines with page breaks
        self.lines = []
        doc_line_start = self._get_document_line_number(paragraph_index, self.first_paragraph_line_offset)
        
        # Add lines from first paragraph
        lines_wanted = min(len(para_lines) - self.first_paragraph_line_offset, self.num_rows)
        for i in range(lines_wanted):
            if len(self.lines) >= self.num_rows:
                break
            doc_line = doc_line_start + i
            # Add the actual content line
            self.lines.append(para_lines[self.first_paragraph_line_offset + i])
            # Check if there's more content after this line
            has_more_content = (i < lines_wanted - 1) or (paragraph_index + 1 < len(self.model.paragraphs))
            # Add page break if needed and there's more content
            if self._should_add_page_break(doc_line) and has_more_content and len(self.lines) < self.num_rows:
                page_num = self._calculate_page_number(doc_line)
                self.lines.append(self._create_page_break_line(page_num))
        
        end_position = CursorPosition(paragraph_index, para_counts[self.first_paragraph_line_offset + lines_wanted - 1] + 1)
        
        # Track total document lines processed
        doc_lines_added = lines_wanted
        
        # Remaining paragraphs
        while len(self.lines) < self.num_rows and paragraph_index + 1 < len(self.model.paragraphs):
            paragraph_index += 1
            para_lines, para_counts = render_paragraph(self.model.paragraphs[paragraph_index], self.num_columns)
            
            for i in range(len(para_lines)):
                if len(self.lines) >= self.num_rows:
                    break
                doc_line = doc_line_start + doc_lines_added
                # Add the actual content line
                self.lines.append(para_lines[i])
                doc_lines_added += 1
                end_position = CursorPosition(paragraph_index, para_counts[i] + 1)
                # Check if there's more content after this line
                has_more_content = (i < len(para_lines) - 1) or (paragraph_index + 1 < len(self.model.paragraphs))
                # Add page break if needed and there's more content
                if self._should_add_page_break(doc_line) and has_more_content and len(self.lines) < self.num_rows:
                    page_num = self._calculate_page_number(doc_line)
                    self.lines.append(self._create_page_break_line(page_num))
        
        self.end_paragraph_index = paragraph_index + 1

        # If the cursor is outside the view, center the view on the cursor
        if self.model.cursor_position < start_position or self.model.cursor_position >= end_position:
            self.center_view_on_cursor()
            # Re-render after centering (recursive call)
            self.render()
            return

        self._set_visual_cursor_position()

        # Add empty line if cursor is at the start of a new visual line
        # This happens when text exactly fills a line and cursor is after it
        if self.visual_cursor_y == len(self.lines) and len(self.lines) < self.num_rows:
            self.lines.append("")

    def _set_visual_cursor_position(self):
        # Set visual cursor position accounting for page break lines
        cursor_para_idx = self.model.cursor_position.paragraph_index
        
        # Get document line number at start of view
        doc_line_start = self._get_document_line_number(self.start_paragraph_index, self.first_paragraph_line_offset)
        
        # Calculate the cursor's document line number
        cursor_doc_line = 0
        for i in range(cursor_para_idx):
            cursor_doc_line += self._get_paragraph_line_count(i)
        
        # Find which line within the cursor paragraph the cursor is on
        _, para_counts = render_paragraph(self.model.paragraphs[cursor_para_idx], self.num_columns)
        line_index = 0
        char_idx = self.model.cursor_position.character_index
        
        # Special case: if cursor is exactly at a line boundary (para_counts value),
        # it should be on the next line (start of next line, not end of current)
        for i in range(len(para_counts) - 1):
            if char_idx == para_counts[i]:
                line_index = i + 1
                break
        else:
            # Normal case: find which line contains this character
            while (line_index < len(para_counts) and
                   para_counts[line_index] < char_idx):
                line_index += 1
        
        cursor_doc_line += line_index
        
        # Calculate number of page breaks between start of view and cursor
        page_breaks_before = 0
        for line_num in range(doc_line_start, cursor_doc_line):
            if line_num > 0 and line_num % self.LINES_PER_PAGE == 0:
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
        
        # Calculate visual cursor X position within the line
        if line_index == 0:
            self.visual_cursor_x = self.model.cursor_position.character_index
        else:
            # Calculate position within the current line
            self.visual_cursor_x = self.model.cursor_position.character_index - para_counts[line_index - 1]

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
        _, para_counts = render_paragraph(self.model.paragraphs[self.model.cursor_position.paragraph_index], self.num_columns)
        line_index = self._find_line_index(para_counts, self.model.cursor_position.character_index)
        
        # Account for page breaks when centering
        cursor_doc_line = self._get_document_line_number(self.model.cursor_position.paragraph_index, line_index)
        page_breaks_before = cursor_doc_line // self.LINES_PER_PAGE
        
        half_rows = (self.num_rows - page_breaks_before) // 2  # Adjust for page breaks
        self.first_paragraph_line_offset = line_index - half_rows  # Could be negative
        
        self.start_paragraph_index = self.model.cursor_position.paragraph_index
        while self.first_paragraph_line_offset < 0 and self.start_paragraph_index > 0:
            self.start_paragraph_index -= 1
            _, para_counts = render_paragraph(self.model.paragraphs[self.start_paragraph_index], self.num_columns)
            self.first_paragraph_line_offset += len(para_counts)
        if self.first_paragraph_line_offset < 0:
            self.first_paragraph_line_offset = 0

    def _find_line_index(self, cumulative_counts: list[int], char_index: int) -> int:
        """Find the line index in cumulative_counts that contains char_index."""
        for i, count in enumerate(cumulative_counts):
            if char_index < count:
                return i
        return len(cumulative_counts) - 1
    
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
        
        # Get the rendered lines for this paragraph
        para_lines, para_counts = render_paragraph(self.model.paragraphs[paragraph_index], self.num_columns)
        
        # Calculate character index for the desired X position on this line
        if line_within_para >= len(para_lines):
            return
        
        line_text = para_lines[line_within_para]
        actual_x = min(desired_x, len(line_text))
        
        # Calculate character index in the paragraph
        if line_within_para == 0:
            char_index = actual_x
        else:
            char_index = para_counts[line_within_para - 1] + actual_x
        
        # Update cursor position
        self.model.cursor_position.paragraph_index = paragraph_index
        self.model.cursor_position.character_index = char_index
        
        # Re-render to update visual cursor position
        self.render()
    
    def _visual_y_to_document_line(self, visual_y: int) -> int | None:
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
        
        # Get the rendered lines for this paragraph
        para_lines, para_counts = render_paragraph(self.model.paragraphs[paragraph_index], self.num_columns)
        
        # Calculate character index for the desired X position on this line
        if line_within_para >= len(para_lines):
            return
        
        line_text = para_lines[line_within_para]
        actual_x = min(self.desired_x, len(line_text))
        
        # Calculate character index in the paragraph
        if line_within_para == 0:
            char_index = actual_x
        else:
            char_index = para_counts[line_within_para - 1] + actual_x
        
        # Update cursor position
        self.model.cursor_position.paragraph_index = paragraph_index
        self.model.cursor_position.character_index = char_index
        
        # Center view on the cursor
        self.center_view_on_cursor()
        self.render()
    
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
        
        # Get the rendered lines for this paragraph
        para_lines, para_counts = render_paragraph(self.model.paragraphs[paragraph_index], self.num_columns)
        
        # Calculate character index for the desired X position on this line
        if line_within_para >= len(para_lines):
            return
        
        line_text = para_lines[line_within_para]
        actual_x = min(self.desired_x, len(line_text))
        
        # Calculate character index in the paragraph
        if line_within_para == 0:
            char_index = actual_x
        else:
            char_index = para_counts[line_within_para - 1] + actual_x
        
        # Update cursor position
        self.model.cursor_position.paragraph_index = paragraph_index
        self.model.cursor_position.character_index = char_index
        
        # Center view on the cursor
        self.center_view_on_cursor()
        self.render()
    
    def update_desired_x(self):
        """Update the desired X position based on current cursor position."""
        self.desired_x = self.visual_cursor_x

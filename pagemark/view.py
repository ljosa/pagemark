from typing import override
from .model import TextView, CursorPosition

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

    current_line = ""
    for word in words:
        if not current_line:
            # First word on the line
            if len(word) < num_columns:
                current_line = word
            else:
                # Word is too long, break it
                while len(word) >= num_columns:
                    lines.append(word[:num_columns])
                    char_count += num_columns
                    cumulative_counts.append(char_count)
                    word = word[num_columns:]
                if word:
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
                if len(word) < num_columns:
                    current_line = word
                else:
                    # Word is too long, break it
                    while len(word) >= num_columns:
                        lines.append(word[:num_columns])
                        char_count += num_columns
                        cumulative_counts.append(char_count)
                        word = word[num_columns:]
                    if word:
                        current_line = word
                    else:
                        current_line = ""

    if current_line:
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

    @override
    def render(self):
        paragraph_index = self.start_paragraph_index
        # First paragraph
        para_lines, para_counts = render_paragraph(self.model.paragraphs[paragraph_index], self.num_columns)
        if self.first_paragraph_line_offset == 0:
            start_position = CursorPosition(paragraph_index, 0)
        else:
            start_position = CursorPosition(paragraph_index, para_counts[self.first_paragraph_line_offset - 1] + 1)
        lines_wanted = min(len(para_lines) - self.first_paragraph_line_offset, self.num_rows)
        self.lines = para_lines[self.first_paragraph_line_offset:self.first_paragraph_line_offset + lines_wanted]
        end_position = CursorPosition(paragraph_index, para_counts[self.first_paragraph_line_offset + lines_wanted - 1] + 1)
        # Remaining paragraphs
        while len(self.lines) < self.num_rows and paragraph_index + 1 < len(self.model.paragraphs):
            paragraph_index += 1
            para_lines, para_counts = render_paragraph(self.model.paragraphs[paragraph_index], self.num_columns)
            lines_wanted = min(len(para_lines), self.num_rows - len(self.lines))
            self.lines += para_lines[:lines_wanted]
            end_position = CursorPosition(paragraph_index, para_counts[lines_wanted - 1] + 1)
        self.end_paragraph_index = paragraph_index + 1

        # If the cursor is outside the view, center the view on the cursor
        if self.model.cursor_position < start_position or self.model.cursor_position >= end_position:
            print(f"Centering view on cursor because cursor {self.model.cursor_position} is outside view {start_position} to {end_position}")
            self.center_view_on_cursor()

        self._set_visual_cursor_position()
        
        # Add empty line if cursor is at the start of a new visual line
        # This happens when text exactly fills a line and cursor is after it
        if self.visual_cursor_y == len(self.lines) and len(self.lines) < self.num_rows:
            self.lines.append("")

    def _set_visual_cursor_position(self):
        # Set visual cursor position
        _, para_counts = render_paragraph(self.model.paragraphs[self.model.cursor_position.paragraph_index], self.num_columns)
        if self.model.cursor_position.paragraph_index == self.start_paragraph_index:
            line_index = 0
            while (line_index < len(para_counts) and
                   para_counts[line_index] < self.model.cursor_position.character_index):
                line_index += 1
            self.visual_cursor_y = line_index - self.first_paragraph_line_offset
            if self.visual_cursor_y < 0:
                self.visual_cursor_y = 0
            elif self.visual_cursor_y >= self.num_rows:
                self.visual_cursor_y = self.num_rows - 1
            if line_index == 0:
                self.visual_cursor_x = self.model.cursor_position.character_index
            else:
                # Calculate position within the current line
                # No -1 needed here, as the space is already counted in para_counts
                self.visual_cursor_x = self.model.cursor_position.character_index - para_counts[line_index - 1]

            # Handle cursor at end of line that exactly fills width
            if self.visual_cursor_x == self.num_columns:
                # Cursor wraps to start of next line
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
        half_rows = self.num_rows // 2
        self.first_paragraph_line_offset = line_index - half_rows  # Could be negative
        while self.first_paragraph_line_offset < 0 and self.start_paragraph_index > 0:
            self.start_paragraph_index -= 1
            _, para_counts = render_paragraph(self.model.paragraphs[self.start_paragraph_index], self.num_columns)
            self.first_paragraph_line_offset += len(para_counts)
        if self.first_paragraph_line_offset < 0:
            self.first_paragraph_line_offset = 0
        self.render()  # Re-render with updated start_paragraph_index and offset

    def _find_line_index(self, cumulative_counts: list[int], char_index: int) -> int:
        """Find the line index in cumulative_counts that contains char_index."""
        for i, count in enumerate(cumulative_counts):
            if char_index < count:
                return i
        return len(cumulative_counts) - 1

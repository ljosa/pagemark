from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Optional

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
    _model: "TextModel | None" = None
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
    paragraphs: list[str]
    cursor_position: CursorPosition
    view: TextView

    def __init__(self, view: TextView, paragraphs=[""]):
        self.view = view
        self.view._model = self
        self.paragraphs = paragraphs
        self.cursor_position = CursorPosition()
        self.selection_start = None  # CursorPosition when selection started
        self.selection_end = None    # Current end of selection
        self.clipboard = ""          # Internal clipboard for cut/copy/paste

    def insert_text(self, text: str, position: CursorPosition | None = None):
        if position is None:
            position = self.cursor_position

        before_view = position.paragraph_index < self.view.start_paragraph_index
        in_view = self.view.start_paragraph_index <= position.paragraph_index < self.view.end_paragraph_index

        paragraphs = text.split("\n")
        current_paragraph = self.paragraphs[self.cursor_position.paragraph_index]
        before_cursor = current_paragraph[:self.cursor_position.character_index]
        after_cursor = current_paragraph[self.cursor_position.character_index:]
        paragraphs[0] = before_cursor + paragraphs[0]
        paragraphs[-1] += after_cursor
        self.paragraphs = (
            self.paragraphs[: self.cursor_position.paragraph_index]
            + paragraphs
            + self.paragraphs[self.cursor_position.paragraph_index + 1 :]
        )
        self.cursor_position.paragraph_index += len(paragraphs) - 1
        self.cursor_position.character_index = len(paragraphs[-1]) - len(after_cursor)

        if before_view:
            self.view.start_paragraph_index += len(paragraphs) - 1
            self.view.end_paragraph_index += len(paragraphs) - 1
        elif in_view:
            self.view.render()

    def right_char(self):
        if self.cursor_position.character_index < len(self.paragraphs[self.cursor_position.paragraph_index]):
            self.cursor_position.character_index += 1
        elif self.cursor_position.paragraph_index + 1 < len(self.paragraphs):
            self.cursor_position.paragraph_index += 1
            self.cursor_position.character_index = 0
        self.view.render()

    def left_char(self):
        if self.cursor_position.character_index > 0:
            self.cursor_position.character_index -= 1
        elif self.cursor_position.paragraph_index > 0:
            self.cursor_position.paragraph_index -= 1
            self.cursor_position.character_index = len(self.paragraphs[self.cursor_position.paragraph_index])
        self.view.render()
    
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
        
        self.paragraphs[para_idx] = new_paragraph
        
        # Move cursor to end of transposed region
        self.cursor_position.character_index = word2.start() + len(word1.group())
        self.view.render()
    
    def transpose_chars(self):
        """Transpose character before cursor with character after cursor.
        
        Emacs behavior: If at end of line, transpose the two chars before cursor.
        If at beginning of line, transpose first two chars.
        """
        para_idx = self.cursor_position.paragraph_index
        paragraph = self.paragraphs[para_idx]
        char_idx = self.cursor_position.character_index
        para_len = len(paragraph)
        
        if para_len < 2:
            # Need at least 2 characters to transpose
            return
        
        if char_idx == 0:
            # At beginning, transpose first two chars
            self.paragraphs[para_idx] = paragraph[1] + paragraph[0] + paragraph[2:]
            self.cursor_position.character_index = 2
        elif char_idx >= para_len:
            # At end, transpose last two chars
            self.paragraphs[para_idx] = paragraph[:-2] + paragraph[-1] + paragraph[-2]
            # Cursor stays at end
        else:
            # In middle, transpose char before and after cursor
            if char_idx == 1:
                # Special case when cursor is at position 1
                self.paragraphs[para_idx] = paragraph[1] + paragraph[0] + paragraph[2:]
            else:
                self.paragraphs[para_idx] = (
                    paragraph[:char_idx-1] + 
                    paragraph[char_idx] + 
                    paragraph[char_idx-1] + 
                    paragraph[char_idx+1:]
                )
            self.cursor_position.character_index = min(char_idx + 1, para_len)
        
        self.view.render()
    
    def center_line(self) -> bool:
        """Center the current paragraph if it fits on one line.
        
        Returns:
            True if centering was successful, False if paragraph is multi-line
        """
        from .constants import EditorConstants
        
        para_idx = self.cursor_position.paragraph_index
        paragraph = self.paragraphs[para_idx]
        
        # Strip existing leading/trailing spaces to get true content
        stripped = paragraph.strip()
        
        # Don't center empty lines
        if not stripped:
            self.paragraphs[para_idx] = ""
            self.cursor_position.character_index = 0
            self.view.render()
            return True
        
        # Check if paragraph would wrap (multi-line) or is at max width
        if len(stripped) >= EditorConstants.DOCUMENT_WIDTH:
            return False
        
        # Calculate centering
        spaces_needed = (EditorConstants.DOCUMENT_WIDTH - len(stripped)) // 2
        centered = ' ' * spaces_needed + stripped
        
        # Update the paragraph
        self.paragraphs[para_idx] = centered
        
        # Adjust cursor position to account for added spaces
        # If cursor was at the beginning, keep it at the beginning of the centered text
        if self.cursor_position.character_index <= len(paragraph) - len(paragraph.lstrip()):
            self.cursor_position.character_index = spaces_needed
        else:
            # Adjust cursor position by the difference in leading spaces
            old_leading = len(paragraph) - len(paragraph.lstrip())
            self.cursor_position.character_index = self.cursor_position.character_index - old_leading + spaces_needed
        
        self.view.render()
        return True

 
    
    def _join_with_previous_paragraph(self):
        """Join current paragraph with previous one, positioning cursor at join point.
        
        Returns:
            True if join was performed, False if at document start
        """
        if self.cursor_position.paragraph_index == 0:
            return False
            
        prev_idx = self.cursor_position.paragraph_index - 1
        prev_para = self.paragraphs[prev_idx]
        curr_para = self.paragraphs[self.cursor_position.paragraph_index]
        
        # Combine paragraphs
        self.paragraphs[prev_idx] = prev_para + curr_para
        del self.paragraphs[self.cursor_position.paragraph_index]
        
        # Move cursor to join point
        self.cursor_position.paragraph_index = prev_idx
        self.cursor_position.character_index = len(prev_para)
        
        return True
    
    def _join_with_next_paragraph(self):
        """Join current paragraph with next one, keeping cursor position.
        
        Returns:
            True if join was performed, False if at document end
        """
        if self.cursor_position.paragraph_index + 1 >= len(self.paragraphs):
            return False
            
        para_idx = self.cursor_position.paragraph_index
        curr_para = self.paragraphs[para_idx]
        next_para = self.paragraphs[para_idx + 1]
        
        # Combine paragraphs
        self.paragraphs[para_idx] = curr_para + next_para
        del self.paragraphs[para_idx + 1]
        
        return True
    
    def right_word(self):
        """Move cursor forward by one word (Emacs-style)."""
        para = self.paragraphs[self.cursor_position.paragraph_index]
        pos = self.cursor_position.character_index
        
        # Skip current word characters
        while pos < len(para) and not para[pos].isspace():
            pos += 1
        
        # Skip whitespace
        while pos < len(para) and para[pos].isspace():
            pos += 1
        
        if pos < len(para):
            # Found next word in same paragraph
            self.cursor_position.character_index = pos
        elif self.cursor_position.paragraph_index + 1 < len(self.paragraphs):
            # Move to start of next paragraph
            self.cursor_position.paragraph_index += 1
            self.cursor_position.character_index = 0
        else:
            # At end of document
            self.cursor_position.character_index = len(para)
        
        self.view.render()
    
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
        
        self.view.render()
    
    def downcase_word(self):
        """Convert from cursor to end of word to lowercase (Emacs M-l).
        
        If in middle of word, convert from cursor to end of word.
        If in whitespace, skip to next word and convert it.
        """
        para = self.paragraphs[self.cursor_position.paragraph_index]
        start_pos = self.cursor_position.character_index
        pos = start_pos
        para_len = len(para)
        
        if pos >= para_len:
            return
        
        # If we're in whitespace, skip to next word
        if pos < para_len and para[pos].isspace():
            while pos < para_len and para[pos].isspace():
                pos += 1
            start_pos = pos
        
        if pos >= para_len:
            return
        
        # Find end of current word
        while pos < para_len and not para[pos].isspace():
            pos += 1
        
        # Convert to lowercase from start_pos to end of word
        if pos > start_pos:
            self.paragraphs[self.cursor_position.paragraph_index] = (
                para[:start_pos] + para[start_pos:pos].lower() + para[pos:]
            )
            self.cursor_position.character_index = pos
        
        self.view.render()
    
    def upcase_word(self):
        """Convert from cursor to end of word to uppercase (Emacs M-u).
        
        If in middle of word, convert from cursor to end of word.
        If in whitespace, skip to next word and convert it.
        """
        para = self.paragraphs[self.cursor_position.paragraph_index]
        start_pos = self.cursor_position.character_index
        pos = start_pos
        para_len = len(para)
        
        if pos >= para_len:
            return
        
        # If we're in whitespace, skip to next word
        if pos < para_len and para[pos].isspace():
            while pos < para_len and para[pos].isspace():
                pos += 1
            start_pos = pos
        
        if pos >= para_len:
            return
        
        # Find end of current word
        while pos < para_len and not para[pos].isspace():
            pos += 1
        
        # Convert to uppercase from start_pos to end of word
        if pos > start_pos:
            self.paragraphs[self.cursor_position.paragraph_index] = (
                para[:start_pos] + para[start_pos:pos].upper() + para[pos:]
            )
            self.cursor_position.character_index = pos
        
        self.view.render()
    
    def capitalize_word(self):
        """Capitalize the word at or after cursor position (Emacs M-c).
        
        Move forward to beginning of word if not at one, capitalize first letter,
        lowercase rest, and move cursor to end of word.
        """
        para = self.paragraphs[self.cursor_position.paragraph_index]
        pos = self.cursor_position.character_index
        para_len = len(para)
        
        # Skip to start of word if not at one
        while pos < para_len and para[pos].isspace():
            pos += 1
        
        if pos >= para_len:
            return
        
        # Find end of word
        word_start = pos
        while pos < para_len and not para[pos].isspace():
            pos += 1
        word_end = pos
        
        # Capitalize first letter, lowercase rest
        word = para[word_start:word_end]
        if word:
            capitalized = word[0].upper() + word[1:].lower()
            self.paragraphs[self.cursor_position.paragraph_index] = (
                para[:word_start] + capitalized + para[word_end:]
            )
            self.cursor_position.character_index = word_end
        
        self.view.render()
    
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
            self.paragraphs[self.cursor_position.paragraph_index] = para[:pos] + para[end_pos:]
        elif self.cursor_position.paragraph_index < len(self.paragraphs) - 1:
            # At end of paragraph, join with next paragraph
            self._join_with_next_paragraph()
        
        self.view.render()
    
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
            self.paragraphs[self.cursor_position.paragraph_index] = para[:pos] + para[original_pos:]
            self.cursor_position.character_index = pos
        elif self.cursor_position.paragraph_index > 0:
            # At start of paragraph, join with previous paragraph
            self._join_with_previous_paragraph()
        
        self.view.render()
    
    def delete_char(self):
        """Delete character at cursor position (Emacs-style Ctrl-D)."""
        para = self.paragraphs[self.cursor_position.paragraph_index]
        pos = self.cursor_position.character_index
        
        if pos < len(para):
            # Delete character at cursor
            self.paragraphs[self.cursor_position.paragraph_index] = para[:pos] + para[pos+1:]
        elif self.cursor_position.paragraph_index + 1 < len(self.paragraphs):
            # At end of paragraph, join with next paragraph
            self._join_with_next_paragraph()
        # else: at end of document, do nothing
        
        self.view.render()
    
    def _get_visual_line_info(self):
        """Get information about the current visual line.
        
        Returns:
            Tuple of (line_index, para_lines, para_counts)
        """
        from .view import render_paragraph
        
        para_idx = self.cursor_position.paragraph_index
        char_idx = self.cursor_position.character_index
        para = self.paragraphs[para_idx]
        
        # Get wrapped lines for current paragraph
        para_lines, para_counts = render_paragraph(para, self.view.num_columns)
        
        # Find which visual line we're on within the paragraph
        # Use simple rule: we're on the line whose cumulative count we haven't exceeded
        line_index = len(para_counts) - 1  # Default to last line
        if para_counts:
            for i, count in enumerate(para_counts):
                if char_idx <= count:
                    line_index = i
                    break
                
        return line_index, para_lines, para_counts
    
    def move_beginning_of_line(self):
        """Move cursor to beginning of visual line (Emacs-style Ctrl-A)."""
        line_index, _, para_counts = self._get_visual_line_info()
        
        # Calculate the start position of this visual line
        if line_index == 0:
            self.cursor_position.character_index = 0
        else:
            self.cursor_position.character_index = para_counts[line_index - 1]
        
        self.view.render()
    
    def move_end_of_line(self):
        """Move cursor to end of visual line (Emacs-style Ctrl-E)."""
        line_index, _, para_counts = self._get_visual_line_info()
        
        para_idx = self.cursor_position.paragraph_index
        para = self.paragraphs[para_idx]
        
        # Move to the end of this visual line
        if para_counts:
            if line_index == len(para_counts) - 1:
                # Last visual line - go to actual end of paragraph
                self.cursor_position.character_index = len(para)
            else:
                # Not the last line - go to last char of this visual line
                # para_counts[line_index] is the first char of the NEXT line
                # So para_counts[line_index] - 1 is the last char of THIS line
                self.cursor_position.character_index = para_counts[line_index] - 1
        else:
            # Empty paragraph
            self.cursor_position.character_index = 0
        
        self.view.render()
    
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
        """Get the currently selected text."""
        if self.selection_start is None or self.selection_end is None:
            return ""
        
        # Ensure start comes before end
        start = self.selection_start
        end = self.selection_end
        if (start.paragraph_index > end.paragraph_index or 
            (start.paragraph_index == end.paragraph_index and 
             start.character_index > end.character_index)):
            start, end = end, start
        
        # Single paragraph selection
        if start.paragraph_index == end.paragraph_index:
            para = self.paragraphs[start.paragraph_index]
            return para[start.character_index:end.character_index]
        
        # Multi-paragraph selection
        result = []
        for i in range(start.paragraph_index, end.paragraph_index + 1):
            para = self.paragraphs[i]
            if i == start.paragraph_index:
                result.append(para[start.character_index:])
            elif i == end.paragraph_index:
                result.append(para[:end.character_index])
            else:
                result.append(para)
        return '\n'.join(result)
    
    def delete_selection(self):
        """Delete the currently selected text."""
        if self.selection_start is None or self.selection_end is None:
            return
        
        # Ensure start comes before end
        start = self.selection_start
        end = self.selection_end
        if (start.paragraph_index > end.paragraph_index or 
            (start.paragraph_index == end.paragraph_index and 
             start.character_index > end.character_index)):
            start, end = end, start
        
        # Single paragraph deletion
        if start.paragraph_index == end.paragraph_index:
            para = self.paragraphs[start.paragraph_index]
            self.paragraphs[start.paragraph_index] = (
                para[:start.character_index] + para[end.character_index:]
            )
            self.cursor_position = CursorPosition(start.paragraph_index, start.character_index)
        else:
            # Multi-paragraph deletion
            first_para = self.paragraphs[start.paragraph_index][:start.character_index]
            last_para = self.paragraphs[end.paragraph_index][end.character_index:]
            
            # Combine first and last parts
            self.paragraphs[start.paragraph_index] = first_para + last_para
            
            # Delete intermediate paragraphs
            for _ in range(end.paragraph_index - start.paragraph_index):
                del self.paragraphs[start.paragraph_index + 1]
            
            self.cursor_position = CursorPosition(start.paragraph_index, start.character_index)
        
        self.clear_selection()
        self.view.render()
    
    def copy_selection(self):
        """Copy selected text to clipboard."""
        selected = self.get_selected_text()
        if selected:
            self.clipboard = selected
            return True
        return False
    
    def cut_selection(self):
        """Cut selected text to clipboard."""
        if self.copy_selection():
            self.delete_selection()
            return True
        return False
    
    def paste(self):
        """Paste clipboard at cursor position, replacing any selection."""
        if self.selection_start is not None:
            self.delete_selection()
        if self.clipboard:
            self.insert_text(self.clipboard)
    
    def kill_line(self):
        """Delete from cursor to end of visual line (Emacs-style Ctrl-K)."""
        line_index, _, para_counts = self._get_visual_line_info()
        
        para_idx = self.cursor_position.paragraph_index
        char_idx = self.cursor_position.character_index
        para = self.paragraphs[para_idx]
        
        # Find the end position of this visual line
        if para_counts:
            visual_line_end = para_counts[line_index]
        else:
            visual_line_end = 0
        
        # Kill from current position to end of visual line
        if char_idx < visual_line_end:
            # Delete from cursor to end of visual line
            self.paragraphs[para_idx] = para[:char_idx] + para[visual_line_end:]
        elif char_idx == len(para) and para_idx + 1 < len(self.paragraphs):
            # At end of paragraph - join with next paragraph
            self._join_with_next_paragraph()
        # else: cursor at end of visual line but not end of paragraph, or at end of document - do nothing
        
        self.view.render()


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

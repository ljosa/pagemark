from abc import ABC, abstractmethod
from dataclasses import dataclass

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
            prev_idx = self.cursor_position.paragraph_index - 1
            prev_para = self.paragraphs[prev_idx]
            curr_para = self.paragraphs[self.cursor_position.paragraph_index]
            
            # Combine paragraphs
            self.paragraphs[prev_idx] = prev_para + curr_para
            del self.paragraphs[self.cursor_position.paragraph_index]
            
            # Move cursor to join point
            self.cursor_position.paragraph_index = prev_idx
            self.cursor_position.character_index = len(prev_para)
        
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
            next_para = self.paragraphs[self.cursor_position.paragraph_index + 1]
            self.paragraphs[self.cursor_position.paragraph_index] = para + next_para
            del self.paragraphs[self.cursor_position.paragraph_index + 1]
        # else: at end of document, do nothing
        
        self.view.render()

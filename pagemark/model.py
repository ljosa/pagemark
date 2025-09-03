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
    cursor_position: CursorPosition = CursorPosition()
    view: TextView

    def __init__(self, view: TextView, paragraphs=[""]):
        self.view = view
        self.view._model = self
        self.paragraphs = paragraphs

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

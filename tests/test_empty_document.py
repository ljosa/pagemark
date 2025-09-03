import pytest
from pagemark import TextModel, TerminalTextView


def test_render_empty_document():
    """Test rendering an empty document."""
    v = TerminalTextView()
    v.num_rows = 10
    v.num_columns = 80

    m = TextModel(v, paragraphs=[""])

    v.render()

    # These assertions verify the render works correctly for an empty document
    assert len(v.lines) == 1
    assert v.lines[0] == ""
    assert v.visual_cursor_x == 0
    assert v.visual_cursor_y == 0
    assert v.start_paragraph_index == 0
    assert v.end_paragraph_index == 1
    assert m.cursor_position.paragraph_index == 0
    assert m.cursor_position.character_index == 0

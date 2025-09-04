"""Test cursor positioning at line boundaries when text wraps."""

from pagemark.model import TextModel
from pagemark.view import TerminalTextView


def test_cursor_at_wrapped_line_boundary():
    """Test that cursor appears at start of next line when at boundary character.
    
    This was a bug where a character at the exact boundary between wrapped lines
    (when char_index equals para_counts[i]) would show the cursor at the END 
    of the current line instead of START of the next line.
    """
    view = TerminalTextView()
    view.num_rows = 10
    view.num_columns = 65
    
    # Use the exact text that exposed the bug
    text = "The author's central thesis is that sedentary farming was not an unavoidable consequence of learning to plant cereal crops and raise animals."
    model = TextModel(view, paragraphs=[text])
    view.render()
    
    # Position cursor at character 127 (the 'r' in "raise animals")
    # This is exactly at para_counts[1] = 127, the boundary between lines 1 and 2
    model.cursor_position.paragraph_index = 0
    model.cursor_position.character_index = 127
    view.render()
    
    # Cursor should be at visual line 2, column 0 (start of "raise animals")
    # Bug would place it at line 1, column 62 (end of "...crops and")
    assert view.visual_cursor_y == 2, f"Cursor Y should be 2, got {view.visual_cursor_y}"
    assert view.visual_cursor_x == 0, f"Cursor X should be 0, got {view.visual_cursor_x}"


def test_cursor_down_reaches_last_wrapped_line():
    """Test that down arrow can reach the last line of wrapped text.
    
    This was the reported bug where pressing down couldn't reach
    the last visual line of a wrapped paragraph.
    """
    view = TerminalTextView()
    view.num_rows = 5
    view.num_columns = 10  # Force wrapping
    
    # Text that wraps to exactly 2 lines
    model = TextModel(view, paragraphs=["First line second line"])
    view.render()
    
    # Start at line 0
    assert view.visual_cursor_y == 0
    
    # Press down arrow
    view.move_cursor_down()
    
    # Should move to line 1
    assert view.visual_cursor_y == 1, f"After down arrow, should be at line 1, got {view.visual_cursor_y}"
    assert view.visual_cursor_x == 0, f"Should be at column 0, got {view.visual_cursor_x}"
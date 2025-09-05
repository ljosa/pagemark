"""Test Ctrl-A/E work with visual lines (wrapped text)."""

from pagemark.model import TextModel, CursorPosition
from pagemark.view import TerminalTextView


def test_move_beginning_of_visual_line():
    """Test Ctrl-A moves to beginning of visual line, not paragraph."""
    view = TerminalTextView()
    view.num_columns = 20  # Force wrapping
    view.num_rows = 10
    
    # Create a long paragraph that will wrap
    long_text = "This is a very long line that will definitely wrap around"
    model = TextModel(view, paragraphs=[long_text])
    
    # Position cursor in the middle of the second visual line
    # "This is a very long " (20 chars) is first line
    # "line that will " would be second line
    model.cursor_position = CursorPosition(0, 25)  # Middle of "line that"
    
    # Move to beginning of visual line
    model.move_beginning_of_line()
    
    # Should be at position 20 (start of second visual line)
    assert model.cursor_position.character_index == 20
    assert model.cursor_position.paragraph_index == 0


def test_move_end_of_visual_line():
    """Test Ctrl-E moves to end of visual line, not paragraph."""
    view = TerminalTextView()
    view.num_columns = 20  # Force wrapping
    view.num_rows = 10
    
    # Create a long paragraph that will wrap
    long_text = "This is a very long line that will definitely wrap around"
    model = TextModel(view, paragraphs=[long_text])
    
    # Position cursor at beginning of first visual line
    model.cursor_position = CursorPosition(0, 0)
    
    # Move to end of visual line
    model.move_end_of_line()
    
    # Should be at position 19 (last character of first visual line)
    # Position 20 would be the first character of the next line
    assert model.cursor_position.character_index == 19
    assert model.cursor_position.paragraph_index == 0


def test_move_beginning_of_line_first_visual_line():
    """Test Ctrl-A on first visual line goes to start of paragraph."""
    view = TerminalTextView()
    view.num_columns = 20  # Force wrapping
    view.num_rows = 10
    
    long_text = "This is a very long line that will definitely wrap around"
    model = TextModel(view, paragraphs=[long_text])
    
    # Position cursor in middle of first visual line
    model.cursor_position = CursorPosition(0, 10)
    
    # Move to beginning
    model.move_beginning_of_line()
    
    # Should be at position 0
    assert model.cursor_position.character_index == 0
    assert model.cursor_position.paragraph_index == 0


def test_move_end_of_line_middle_visual_line():
    """Test Ctrl-E on middle visual line moves to end of that visual line."""
    view = TerminalTextView()
    view.num_columns = 20  # Force wrapping
    view.num_rows = 10
    
    long_text = "This is a very long line that will definitely wrap around"
    model = TextModel(view, paragraphs=[long_text])
    
    # Position cursor on the third visual line (chars 35-51, "definitely wrap ")
    model.cursor_position = CursorPosition(0, 40)  # In "definitely"
    
    # Move to end of visual line
    model.move_end_of_line()
    
    # Check what the actual visual lines are for this text
    from pagemark.view import render_paragraph
    para_lines, para_counts = render_paragraph(long_text, 20)
    
    # Find which line position 40 is on
    line_index = 0
    for i, count in enumerate(para_counts):
        if 40 < count:
            line_index = i
            break
    
    # Should be at the last character of that visual line
    if line_index == len(para_counts) - 1:
        # Last line - go to end of paragraph
        assert model.cursor_position.character_index == len(long_text)
    else:
        # Not last line - go to last char of this visual line
        assert model.cursor_position.character_index == para_counts[line_index] - 1
    assert model.cursor_position.paragraph_index == 0


def test_move_end_of_line_at_visual_boundary_stays_on_next_line():
    """Ctrl-E at start of a visual line should act on that line, not the previous one.

    Regression: when cursor is exactly at a wrap boundary (start of next visual line),
    move_end_of_line should move to the end of that current line, not jump to the
    end of the previous visual line.
    """
    view = TerminalTextView()
    view.num_columns = 20  # Force wrapping
    view.num_rows = 10

    long_text = "This is a very long line that will definitely wrap around"
    model = TextModel(view, paragraphs=[long_text])

    from pagemark.view import render_paragraph
    para_lines, para_counts = render_paragraph(long_text, 20)
    assert len(para_counts) >= 2  # ensure wrapping happened

    # Place cursor exactly at the start of the second visual line
    boundary = para_counts[0]
    model.cursor_position = CursorPosition(0, boundary)

    # Invoke Ctrl-E behavior
    model.move_end_of_line()

    # Expect to be at the end of the second visual line (not the first)
    if len(para_counts) > 1:
        expected_end = para_counts[1] - 1 if len(para_counts) > 1 else len(long_text)
    else:
        expected_end = len(long_text)
    assert model.cursor_position.character_index == expected_end
    assert model.cursor_position.paragraph_index == 0


def test_move_end_of_line_last_visual_line():
    """Test Ctrl-E on last visual line goes to end of paragraph."""
    view = TerminalTextView()
    view.num_columns = 20  # Force wrapping
    view.num_rows = 10
    
    long_text = "This is a very long line that will definitely wrap around"
    model = TextModel(view, paragraphs=[long_text])
    
    # Position cursor on the last visual line (which starts at char 51)
    model.cursor_position = CursorPosition(0, 52)  # In "around"
    
    # Move to end
    model.move_end_of_line()
    
    # Should be at end of paragraph (since we're on the last visual line)
    assert model.cursor_position.character_index == len(long_text)
    assert model.cursor_position.paragraph_index == 0


def test_kill_visual_line():
    """Test Ctrl-K kills to end of visual line, not paragraph."""
    view = TerminalTextView()
    view.num_columns = 20  # Force wrapping
    view.num_rows = 10
    
    # Create a long paragraph that will wrap
    long_text = "This is a very long line that will definitely wrap around"
    model = TextModel(view, paragraphs=[long_text])
    
    # Position cursor at position 10 in first visual line
    model.cursor_position = CursorPosition(0, 10)
    
    # Kill to end of visual line
    model.kill_line()
    
    # Should have deleted from position 10 to 20 (the visual line boundary)
    # Result: "This is a line that will definitely wrap around"
    expected = "This is a line that will definitely wrap around"
    assert model.paragraphs[0] == expected
    assert model.cursor_position.character_index == 10


def test_kill_at_end_of_visual_line():
    """Test Ctrl-K at end of visual line deletes nothing from current line."""
    view = TerminalTextView()
    view.num_columns = 20  # Force wrapping
    view.num_rows = 10
    
    long_text = "This is a very long line that will definitely wrap around"
    model = TextModel(view, paragraphs=[long_text])
    
    # Position cursor at end of first visual line (position 20)
    # Note: position 20 is considered the end of the first line
    model.cursor_position = CursorPosition(0, 20)
    
    # Kill - at position 20, we're at the end of the first visual line
    # So this should do nothing (no text to delete on this line)
    model.kill_line()
    
    # Text should be unchanged
    assert model.paragraphs[0] == long_text
    assert model.cursor_position.character_index == 20


def test_move_in_short_line():
    """Test Ctrl-A/E work normally in lines that don't wrap."""
    view = TerminalTextView()
    view.num_columns = 65  # Default width
    view.num_rows = 10
    
    short_text = "Short line"
    model = TextModel(view, paragraphs=[short_text])
    
    # Position in middle
    model.cursor_position = CursorPosition(0, 5)
    
    # Move to beginning
    model.move_beginning_of_line()
    assert model.cursor_position.character_index == 0
    
    # Move to end
    model.move_end_of_line()
    assert model.cursor_position.character_index == len(short_text)

from pagemark import TextModel, TerminalTextView


def test_insert_full_width_line():
    """Test inserting exactly terminal width characters."""
    v = TerminalTextView()
    v.num_rows = 10
    v.num_columns = 20

    m = TextModel(v, paragraphs=[""])

    # Insert exactly 20 characters (the width)
    text = "a" * 20
    m.insert_text(text)

    v.render()

    # Should be two lines (the last empty)
    assert len(v.lines) == 2
    assert v.lines[0] == text
    assert v.lines[1] == ""
    assert len(v.lines[0]) == v.num_columns

    # Cursor should be at the end of the paragraph
    assert m.cursor_position.paragraph_index == 0
    assert m.cursor_position.character_index == 20

    # Visual cursor should be at the beginning of the second visual line.
    assert v.visual_cursor_y == 1
    assert v.visual_cursor_x == 0


def test_insert_one_char_over_width():
    """Test inserting one character more than terminal width."""
    v = TerminalTextView()
    v.num_rows = 10
    v.num_columns = 20

    m = TextModel(v, paragraphs=[""])

    # Insert 21 characters (one more than width)
    text = "b" * 21
    m.insert_text(text)

    # Render the view
    v.render()

    # Should wrap to two lines
    assert len(v.lines) == 2
    assert v.lines[0] == "b" * 20  # First line full
    assert v.lines[1] == "b"        # One character on second line

    # Cursor should be after the 21st character of the paragraph
    assert m.cursor_position.paragraph_index == 0
    assert m.cursor_position.character_index == 21

    # Visual cursor should be on second line, after the single 'b'
    assert v.visual_cursor_y == 1  # Second line
    assert v.visual_cursor_x == 1


def test_insert_exact_width_then_navigate():
    """Test cursor navigation after inserting full width line."""
    v = TerminalTextView()
    v.num_rows = 10
    v.num_columns = 30

    m = TextModel(v, paragraphs=[""])

    # Insert exactly 30 characters
    text = "x" * 30
    m.insert_text(text)
    v.render()

    # Verify initial position
    assert m.cursor_position.character_index == 30
    assert v.visual_cursor_y == 1
    assert v.visual_cursor_x == 0

    # Navigate left
    m.left_char()
    assert m.cursor_position.character_index == 29
    assert v.visual_cursor_y == 0
    assert v.visual_cursor_x == 29

    # Navigate right (back to end)
    m.right_char()
    assert m.cursor_position.character_index == 30
    assert v.visual_cursor_y == 1
    assert v.visual_cursor_x == 0


def test_insert_width_with_spaces():
    """Test inserting line with spaces that equals terminal width."""
    v = TerminalTextView()
    v.num_rows = 10
    v.num_columns = 25

    m = TextModel(v, paragraphs=[""])

    # Insert text with spaces totaling 25 chars
    text = "Hello World Test Line 123"  # Exactly 25 characters
    assert len(text) == 25
    m.insert_text(text)

    v.render()

    # The last word should wrap
    assert len(v.lines) == 2
    assert v.lines[0] == "Hello World Test Line"
    assert v.lines[1] == "123"

    # Cursor at end
    assert m.cursor_position.character_index == 25

    assert v.visual_cursor_y == 1
    assert v.visual_cursor_x == 3


def test_word_at_exact_boundary():
    """Test when a word ends exactly at the terminal width."""
    v = TerminalTextView()
    v.num_rows = 10
    v.num_columns = 15

    m = TextModel(v, paragraphs=[""])

    # Insert text where a word ends exactly at column 15
    text = "Hello beautiful"  # "Hello " = 6 chars, "beautiful" = 9 chars, total = 15
    assert len(text) == 15
    m.insert_text(text)

    v.render()

    # Should wrap
    assert len(v.lines) == 2
    assert v.lines[0] == "Hello"
    assert v.lines[1] == "beautiful"

    # Cursor position after "beautiful"
    assert m.cursor_position.character_index == 15  # 15 + 1 space + 5 chars
    assert v.visual_cursor_y == 1
    assert v.visual_cursor_x == 9


def test_multiple_full_width_lines():
    """Test inserting multiple lines that each fill the terminal width."""
    v = TerminalTextView()
    v.num_rows = 5
    v.num_columns = 10

    m = TextModel(v, paragraphs=[""])

    # Insert 3 lines worth of characters (30 chars total)
    text = "A" * 30
    m.insert_text(text)

    v.render()

    # Should wrap to exactly 3 lines
    assert len(v.lines) == 4
    assert v.lines[0] == "A" * 10
    assert v.lines[1] == "A" * 10
    assert v.lines[2] == "A" * 10
    assert v.lines[3] == ""

    # Cursor at the end
    assert m.cursor_position.character_index == 30

    assert v.visual_cursor_y == 3
    assert v.visual_cursor_x == 0

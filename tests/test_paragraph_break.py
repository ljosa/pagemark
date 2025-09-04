from pagemark import TextModel, TerminalTextView


def test_insert_paragraph_break_empty():
    """Test inserting a paragraph break in an empty document."""
    v = TerminalTextView()
    v.num_rows = 10
    v.num_columns = 20

    m = TextModel(v, paragraphs=[""])

    # Insert a newline (paragraph break)
    m.insert_text("\n")

    # Should create two empty paragraphs
    assert len(m.paragraphs) == 2
    assert m.paragraphs[0] == ""
    assert m.paragraphs[1] == ""

    # Cursor should be at start of second paragraph
    assert m.cursor_position.paragraph_index == 1
    assert m.cursor_position.character_index == 0

    # Render and check view
    v.render()
    assert len(v.lines) == 2
    assert v.lines[0] == ""
    assert v.lines[1] == ""

    # Visual cursor should be on second line
    assert v.visual_cursor_y == 1
    assert v.visual_cursor_x == 0


def test_insert_paragraph_break_middle():
    """Test inserting a paragraph break in the middle of text."""
    v = TerminalTextView()
    v.num_rows = 10
    v.num_columns = 30

    m = TextModel(v, paragraphs=["Hello world"])

    # Move cursor to after "Hello"
    m.cursor_position.character_index = 5

    # Insert a newline
    m.insert_text("\n")

    # Should split the paragraph
    assert len(m.paragraphs) == 2
    assert m.paragraphs[0] == "Hello"
    assert m.paragraphs[1] == " world"

    # Cursor should be at start of second paragraph
    assert m.cursor_position.paragraph_index == 1
    assert m.cursor_position.character_index == 0

    # Render and check view
    v.render()
    assert len(v.lines) == 2
    assert v.lines[0] == "Hello"
    assert v.lines[1] == " world"

    # Visual cursor should be at start of second line
    assert v.visual_cursor_y == 1
    assert v.visual_cursor_x == 0


def test_insert_paragraph_break_end():
    """Test inserting a paragraph break at the end of a line."""
    v = TerminalTextView()
    v.num_rows = 10
    v.num_columns = 30

    m = TextModel(v, paragraphs=["First line"])

    # Move cursor to end
    m.cursor_position.character_index = 10

    # Insert a newline
    m.insert_text("\n")

    # Should create a new empty paragraph
    assert len(m.paragraphs) == 2
    assert m.paragraphs[0] == "First line"
    assert m.paragraphs[1] == ""

    # Cursor should be at start of second paragraph
    assert m.cursor_position.paragraph_index == 1
    assert m.cursor_position.character_index == 0

    # Render and check view
    v.render()
    assert len(v.lines) == 2
    assert v.lines[0] == "First line"
    assert v.lines[1] == ""

    # Visual cursor should be on second line
    assert v.visual_cursor_y == 1
    assert v.visual_cursor_x == 0


def test_multiple_paragraph_breaks():
    """Test inserting multiple consecutive paragraph breaks."""
    v = TerminalTextView()
    v.num_rows = 10
    v.num_columns = 20

    m = TextModel(v, paragraphs=[""])

    # Insert three newlines
    m.insert_text("\n\n\n")

    # Should create four paragraphs (original + 3 new)
    assert len(m.paragraphs) == 4
    assert all(para == "" for para in m.paragraphs)

    # Cursor should be at start of fourth paragraph
    assert m.cursor_position.paragraph_index == 3
    assert m.cursor_position.character_index == 0

    # Render and check view
    v.render()
    assert len(v.lines) == 4
    assert all(line == "" for line in v.lines)

    # Visual cursor should be on fourth line
    assert v.visual_cursor_y == 3
    assert v.visual_cursor_x == 0


def test_paragraph_break_with_wrapped_text():
    """Test paragraph break in text that wraps across lines."""
    v = TerminalTextView()
    v.num_rows = 10
    v.num_columns = 15

    # Text that will wrap
    text = "This is a long line that will wrap"
    m = TextModel(v, paragraphs=[text])

    # Move cursor to middle of wrapped portion
    m.cursor_position.character_index = 20  # After "line "

    # Insert a newline
    m.insert_text("\n")

    # Should split the paragraph
    assert len(m.paragraphs) == 2
    assert m.paragraphs[0] == "This is a long line "  # Space at position 19 stays with first part
    assert m.paragraphs[1] == "that will wrap"  # No leading space

    # Cursor should be at start of second paragraph
    assert m.cursor_position.paragraph_index == 1
    assert m.cursor_position.character_index == 0

    # Render and check view
    v.render()

    # First paragraph wraps to two lines, second to one
    assert v.lines[0] == "This is a long"
    assert v.lines[1] == "line "  # Trailing space on wrapped line
    assert v.lines[2] == "that will wrap"  # No leading space

    # Visual cursor should be at start of third visual line
    assert v.visual_cursor_y == 2
    assert v.visual_cursor_x == 0


def test_navigate_across_paragraphs():
    """Test cursor navigation across paragraph boundaries."""
    v = TerminalTextView()
    v.num_rows = 10
    v.num_columns = 20

    m = TextModel(v, paragraphs=["First", "Second", "Third"])

    # Start at beginning of second paragraph
    m.cursor_position.paragraph_index = 1
    m.cursor_position.character_index = 0
    v.render()

    # Navigate left should go to end of first paragraph
    m.left_char()
    assert m.cursor_position.paragraph_index == 0
    assert m.cursor_position.character_index == 5
    assert v.visual_cursor_y == 0
    assert v.visual_cursor_x == 5

    # Navigate right should go back to start of second paragraph
    m.right_char()
    assert m.cursor_position.paragraph_index == 1
    assert m.cursor_position.character_index == 0
    assert v.visual_cursor_y == 1
    assert v.visual_cursor_x == 0

    # Navigate to end of second paragraph
    m.cursor_position.character_index = 6
    v.render()

    # Navigate right should go to start of third paragraph
    m.right_char()
    assert m.cursor_position.paragraph_index == 2
    assert m.cursor_position.character_index == 0
    assert v.visual_cursor_y == 2
    assert v.visual_cursor_x == 0


def test_insert_text_after_paragraph_break():
    """Test inserting text after creating a new paragraph."""
    v = TerminalTextView()
    v.num_rows = 10
    v.num_columns = 30

    m = TextModel(v, paragraphs=["First paragraph"])

    # Go to end and insert paragraph break
    m.cursor_position.character_index = 15
    m.insert_text("\n")

    # Now insert text in the new paragraph
    m.insert_text("Second paragraph")

    # Verify model state
    assert len(m.paragraphs) == 2
    assert m.paragraphs[0] == "First paragraph"
    assert m.paragraphs[1] == "Second paragraph"

    # Cursor should be at end of second paragraph
    assert m.cursor_position.paragraph_index == 1
    assert m.cursor_position.character_index == 16

    # Render and verify view
    v.render()
    assert v.lines[0] == "First paragraph"
    assert v.lines[1] == "Second paragraph"

    # Visual cursor at end of second line
    assert v.visual_cursor_y == 1
    assert v.visual_cursor_x == 16

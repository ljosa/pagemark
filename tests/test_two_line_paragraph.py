from pagemark import TextModel, TerminalTextView


def test_render_two_line_paragraph():
    """Test rendering a paragraph that wraps to exactly two lines."""
    v = TerminalTextView()
    v.num_rows = 10
    v.num_columns = 35  # Width adjusted to get exactly 2 lines

    # Text that should wrap to two lines with 35 columns
    text = "This is a paragraph that will wrap nicely into exactly two lines"
    m = TextModel(v, paragraphs=[text])

    v.render()

    # Should render to exactly 2 lines with the given column width
    assert len(v.lines) == 2

    # First line should start with "This"
    assert v.lines[0].startswith("This")

    # Check line lengths don't exceed column limit
    assert len(v.lines[0]) <= v.num_columns
    assert len(v.lines[1]) <= v.num_columns

    # Cursor at beginning
    assert m.cursor_position.paragraph_index == 0
    assert m.cursor_position.character_index == 0
    assert v.visual_cursor_x == 0
    assert v.visual_cursor_y == 0

    # View boundaries
    assert v.start_paragraph_index == 0
    assert v.end_paragraph_index == 1


def test_render_paragraph_with_mid_word_break():
    """Test rendering when a word must be broken mid-word."""
    v = TerminalTextView()
    v.num_rows = 10
    v.num_columns = 15  # Very narrow

    # Has a very long word that must be broken
    text = "This has a verylongwordthatmustbebroken here"
    m = TextModel(v, paragraphs=[text])

    v.render()

    # Should have multiple lines due to word breaking
    assert len(v.lines) >= 3

    # Check all lines respect column limit
    for line in v.lines:
        assert len(line) <= v.num_columns

    # First line should be "This has a"
    assert v.lines[0] == "This has a"

    # Second line should be part of the long word
    assert v.lines[1] == "verylongwordtha"

    # Cursor position checks
    assert m.cursor_position.paragraph_index == 0
    assert m.cursor_position.character_index == 0
    assert v.visual_cursor_x == 0
    assert v.visual_cursor_y == 0


def test_render_paragraph_exact_width():
    """Test rendering when text exactly fits the column width."""
    v = TerminalTextView()
    v.num_rows = 10
    v.num_columns = 10

    # Each word is exactly 10 characters
    text = "1234567890 abcdefghij"
    m = TextModel(v, paragraphs=[text])

    v.render()

    # Should be on four lines due to exact fits
    assert len(v.lines) == 4
    assert v.lines[0] == "1234567890"
    assert v.lines[1] == ""
    assert v.lines[2] == "abcdefghij"
    assert v.lines[3] == ""

    # Cursor checks
    assert m.cursor_position.paragraph_index == 0
    assert m.cursor_position.character_index == 0
    assert v.visual_cursor_x == 0
    assert v.visual_cursor_y == 0


def test_render_two_line_with_trailing_spaces():
    """Test rendering handles trailing spaces correctly."""
    v = TerminalTextView()
    v.num_rows = 10
    v.num_columns = 20

    # Text with multiple spaces between words
    text = "First    line   and   second    line"
    m = TextModel(v, paragraphs=[text])

    v.render()

    # Should wrap into at least 2 lines
    assert len(v.lines) >= 2

    # Lines should respect column width, with up to +1 for double-space margin extension
    for line in v.lines:
        assert len(line) <= v.num_columns + 1

    # Cursor at start
    assert m.cursor_position.paragraph_index == 0
    assert m.cursor_position.character_index == 0
    assert v.visual_cursor_x == 0
    assert v.visual_cursor_y == 0


def test_double_space_margin_extension():
    """Test that double-spaces are kept together by extending into margin.

    When two consecutive spaces would cause the second space to wrap to the
    next line, both spaces should be kept on the current line by extending
    it into the right margin (num_columns + 1).
    """
    v = TerminalTextView()
    v.num_rows = 10
    v.num_columns = 6  # Small width to easily trigger wrapping

    # "Hello  world" - the double-space should stay together
    # Without margin extension: "Hello " on line 1, " world" on line 2 (bad)
    # With margin extension: "Hello  " on line 1 (7 chars), "world" on line 2 (good)
    text = "Hello  world"
    m = TextModel(v, paragraphs=[text])

    v.render()

    # Should render to 2 lines
    assert len(v.lines) == 2

    # First line should have both spaces (extended to 7 chars)
    assert v.lines[0] == "Hello  "
    assert len(v.lines[0]) == 7  # Extended into margin

    # Second line should be just "world" without leading space
    assert v.lines[1] == "world"


def test_double_space_cursor_in_margin():
    """Test cursor positioning when in the margin area of an extended line."""
    v = TerminalTextView()
    v.num_rows = 10
    v.num_columns = 6

    text = "Hello  world"
    m = TextModel(v, paragraphs=[text])

    # Move cursor to position 6 (the second space, in the margin)
    m.cursor_position.character_index = 6
    v.render()

    # Cursor should be on line 0 at column 6 (in the margin)
    assert v.visual_cursor_y == 0
    assert v.visual_cursor_x == 6


def test_triple_space_only_two_in_margin():
    """Test that only two spaces extend into margin, third wraps.

    For three or more consecutive spaces, only the first two stay together
    via margin extension. The third space wraps to the next line.
    """
    v = TerminalTextView()
    v.num_rows = 10
    v.num_columns = 6

    # "Hello   x" - triple space
    text = "Hello   x"
    m = TextModel(v, paragraphs=[text])

    v.render()

    # First line: "Hello  " (7 chars, two spaces in margin)
    # Second line: starts with remaining content
    assert v.lines[0] == "Hello  "
    assert len(v.lines[0]) == 7

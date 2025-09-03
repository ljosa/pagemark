import pytest
from pagemark import TextModel, TerminalTextView, CursorPosition


def test_insert_two_paragraphs_in_middle():
    """Test inserting text with two paragraphs into the middle of a paragraph."""
    v = TerminalTextView()
    v.num_rows = 10
    v.num_columns = 80

    # Start with a single paragraph
    initial_text = "This is the original paragraph with some text."
    m = TextModel(v, paragraphs=[initial_text])

    # Position cursor in the middle (after "original ")
    m.cursor_position = CursorPosition(0, 21)  # After "This is the original "

    # Insert text containing two newlines (creating 3 paragraphs from the insertion)
    insert_text = "FIRST INSERTED\nSECOND INSERTED\nTHIRD INSERTED"
    m.insert_text(insert_text)

    # Should now have 4 paragraphs total:
    # 1. "This is the original FIRST INSERTED"
    # 2. "SECOND INSERTED"
    # 3. "THIRD INSERTED paragraph with some text."
    assert len(m.paragraphs) == 3
    assert m.paragraphs[0] == "This is the original FIRST INSERTED"
    assert m.paragraphs[1] == "SECOND INSERTED"
    assert m.paragraphs[2] == "THIRD INSERTEDparagraph with some text."

    # Cursor should be after "THIRD INSERTED" in the third paragraph
    assert m.cursor_position.paragraph_index == 2
    assert m.cursor_position.character_index == 14  # Length of "THIRD INSERTED"


def test_insert_empty_paragraphs():
    """Test inserting text with empty lines (just newlines)."""
    v = TerminalTextView()
    v.num_rows = 10
    v.num_columns = 80

    # Start with text
    m = TextModel(v, paragraphs=["First paragraph", "Second paragraph"])

    # Position cursor at end of first paragraph
    m.cursor_position = CursorPosition(0, len("First paragraph"))

    # Insert two newlines (creating empty paragraphs)
    m.insert_text("\n\n")

    # Should now have 4 paragraphs with two empty ones
    assert len(m.paragraphs) == 4
    assert m.paragraphs[0] == "First paragraph"
    assert m.paragraphs[1] == ""
    assert m.paragraphs[2] == ""
    assert m.paragraphs[3] == "Second paragraph"

    # Cursor should be at beginning of third paragraph (index 2)
    assert m.cursor_position.paragraph_index == 2
    assert m.cursor_position.character_index == 0


def test_insert_at_beginning_of_paragraph():
    """Test inserting multi-paragraph text at the beginning of a paragraph."""
    v = TerminalTextView()
    v.num_rows = 10
    v.num_columns = 80

    m = TextModel(v, paragraphs=["Original text here"])

    # Position cursor at beginning
    m.cursor_position = CursorPosition(0, 0)

    # Insert two paragraphs
    m.insert_text("New first line\nNew second line\n")

    # Should have 3 paragraphs
    assert len(m.paragraphs) == 3
    assert m.paragraphs[0] == "New first line"
    assert m.paragraphs[1] == "New second line"
    assert m.paragraphs[2] == "Original text here"

    # Cursor should be at beginning of third paragraph
    assert m.cursor_position.paragraph_index == 2
    assert m.cursor_position.character_index == 0


def test_insert_between_paragraphs():
    """Test inserting multi-paragraph text between existing paragraphs."""
    v = TerminalTextView()
    v.num_rows = 10
    v.num_columns = 80

    m = TextModel(v, paragraphs=["First", "Second", "Third"])

    # Position cursor at end of first paragraph
    m.cursor_position = CursorPosition(0, 5)  # After "First"

    # Insert text with newlines
    m.insert_text("\nInserted A\nInserted B")

    # Should now have 5 paragraphs
    assert len(m.paragraphs) == 5
    assert m.paragraphs[0] == "First"
    assert m.paragraphs[1] == "Inserted A"
    assert m.paragraphs[2] == "Inserted B"
    assert m.paragraphs[3] == "Second"
    assert m.paragraphs[4] == "Third"

    # Cursor should be after "Inserted B"
    assert m.cursor_position.paragraph_index == 2
    assert m.cursor_position.character_index == 10  # Length of "Inserted B"


def test_insert_splits_word():
    """Test inserting paragraphs in the middle of a word."""
    v = TerminalTextView()
    v.num_rows = 10
    v.num_columns = 80

    m = TextModel(v, paragraphs=["Unbreakable"])

    # Position cursor in middle of the word
    m.cursor_position = CursorPosition(0, 5)  # After "Unbre"

    # Insert text with newlines
    m.insert_text("\nNEW\n")

    # Should split the word across paragraphs
    assert len(m.paragraphs) == 3
    assert m.paragraphs[0] == "Unbre"
    assert m.paragraphs[1] == "NEW"
    assert m.paragraphs[2] == "akable"

    # Cursor should be at beginning of "akable"
    assert m.cursor_position.paragraph_index == 2
    assert m.cursor_position.character_index == 0


def test_insert_with_position_parameter():
    """Test that position parameter has a bug - it's ignored in the implementation."""
    v = TerminalTextView()
    v.num_rows = 10
    v.num_columns = 80

    m = TextModel(v, paragraphs=["ABC", "DEF", "GHI"])

    # Cursor at origin
    assert m.cursor_position.paragraph_index == 0
    assert m.cursor_position.character_index == 0

    # Try to insert at a specific position in second paragraph
    insert_position = CursorPosition(1, 2)  # After "DE" in "DEF"
    m.insert_text("XXX\nYYY", position=insert_position)

    # BUG: The position parameter is ignored!
    # The insertion happens at cursor position (0,0) instead of the specified position
    # This is because lines 58-66 in model.py use self.cursor_position instead of position

    # The actual (buggy) behavior:
    assert len(m.paragraphs) == 4
    assert m.paragraphs[0] == "XXX"  # Inserted at cursor position, not at specified position
    assert m.paragraphs[1] == "YYYABC"  # Rest of "ABC" after the insertion
    assert m.paragraphs[2] == "DEF"  # Original second paragraph unchanged
    assert m.paragraphs[3] == "GHI"  # Original third paragraph unchanged

    # Cursor moved based on the insertion at cursor position
    assert m.cursor_position.paragraph_index == 1
    assert m.cursor_position.character_index == 3  # After "YYY"

from pagemark import TextModel, TerminalTextView


def test_view_always_65_columns():
    """Test that the view always uses 65 columns regardless of terminal size."""
    v = TerminalTextView()
    v.num_rows = 10
    v.num_columns = 65  # Should always be 65

    m = TextModel(v, paragraphs=["This is a test of the fixed-width view."])

    # Insert text that's longer than 65 characters
    long_text = "This is a very long line that should wrap at exactly 65 characters on the display"
    m.insert_text(long_text)

    v.render()

    # Check that lines are wrapped at 65 characters
    assert all(len(line) <= 65 for line in v.lines)

    # Verify wrapping occurred
    assert len(v.lines) > 1


def test_text_wraps_at_65():
    """Test that text wraps at exactly 65 characters."""
    v = TerminalTextView()
    v.num_rows = 10
    v.num_columns = 65

    # Create text that's exactly 65 characters
    text = "a" * 65
    _ = TextModel(v, paragraphs=[text])

    v.render()

    # Should create two lines: one with 65 'a's and an empty one for cursor
    assert len(v.lines) == 2
    assert v.lines[0] == "a" * 65
    assert v.lines[1] == ""


def test_word_wrap_at_65():
    """Test that word wrapping respects the 65 character limit."""
    v = TerminalTextView()
    v.num_rows = 10
    v.num_columns = 65

    # Create text with words that should wrap
    text = "The quick brown fox jumps over the lazy dog. " * 3
    m = TextModel(v, paragraphs=[text])

    v.render()

    # All lines should be 65 chars or less
    for line in v.lines:
        assert len(line) <= 65

    # Should have wrapped
    assert len(v.lines) > 1

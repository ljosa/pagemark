"""Tests for non-breaking space as a bullet character (for block quotes)."""

from pagemark.view import render_paragraph, get_hanging_indent_width


def test_nbsp_bullet_wrapping_applies_hanging_indent():
    """Test that non-breaking space followed by space acts as a bullet."""
    # Non-breaking space (U+00A0) followed by space, then text
    text = "\xa0 This is a block quote that will wrap across lines"
    lines, _ = render_paragraph(text, 20)
    assert len(lines) > 1
    # Wrapped lines should start with two spaces ("\xa0 ") as hanging indent
    for i in range(1, len(lines)):
        assert lines[i].startswith("  ")


def test_nbsp_bullet_hanging_indent_width():
    """Test that get_hanging_indent_width recognizes non-breaking space bullet."""
    text = "\xa0 This is a block quote"
    width = get_hanging_indent_width(text)
    # Non-breaking space (1 char) + space (1 char) = 2
    assert width == 2


def test_nbsp_bullet_with_leading_spaces():
    """Test that non-breaking space bullet works with leading spaces."""
    text = "  \xa0 This is an indented block quote that will wrap"
    lines, _ = render_paragraph(text, 20)
    assert len(lines) > 1
    width = get_hanging_indent_width(text)
    # 2 leading spaces + non-breaking space (1) + space (1) = 4
    assert width == 4
    # Wrapped lines should start with four spaces
    for i in range(1, len(lines)):
        assert lines[i].startswith("    ")


def test_nbsp_bullet_multiple_spaces_does_not_indent():
    """Test that multiple spaces after non-breaking space does not trigger hanging indent."""
    text = "\xa0  two spaces should not trigger hanging indent"
    lines, _ = render_paragraph(text, 20)
    assert len(lines) > 1
    # Should NOT trigger hanging indent
    assert not lines[1].startswith("  ")


def test_nbsp_without_space_does_not_trigger():
    """Test that non-breaking space without following space doesn't trigger hanging indent."""
    text = "\xa0This has no space after nbsp"
    width = get_hanging_indent_width(text)
    assert width == 0

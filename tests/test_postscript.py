"""Tests for PostScript generation."""

from pagemark.postscript import PostScriptGenerator


def test_postscript_generator_basic():
    """Test basic PostScript generation."""
    generator = PostScriptGenerator()
    
    # Create simple test pages
    pages = [
        ["Line 1", "Line 2", "Line 3"] + [""] * 63,  # Page 1 with 3 lines
        ["Page 2 Line 1", ""] * 33  # Page 2
    ]
    
    ps_content = generator.generate_postscript(pages)
    
    # Check PostScript header
    assert ps_content.startswith("%!PS-Adobe-3.0")
    assert "%%Pages: 2" in ps_content
    assert "%%BoundingBox: 0 0 612 792" in ps_content
    assert "/Courier" in ps_content
    
    # Check page markers
    assert "%%Page: 1 1" in ps_content
    assert "%%Page: 2 2" in ps_content
    
    # Check content
    assert "(Line 1) showline" in ps_content
    assert "(Line 2) showline" in ps_content
    assert "(Page 2 Line 1) showline" in ps_content
    
    # Check document structure
    assert "%%Trailer" in ps_content
    assert "%%EOF" in ps_content


def test_postscript_escape_special_chars():
    """Test escaping of special PostScript characters."""
    generator = PostScriptGenerator()
    
    # Test escaping
    test_cases = [
        ("Hello (world)", "Hello \\(world\\)"),
        ("Test ) bracket", "Test \\) bracket"),
        ("Back\\slash", "Back\\\\slash"),
        ("()()", "\\(\\)\\(\\)"),
        ("Normal text", "Normal text")
    ]
    
    for input_text, expected in test_cases:
        escaped = generator._escape_postscript(input_text)
        assert escaped == expected


def test_postscript_escape_unicode():
    """Test escaping of Unicode/Latin-1 characters."""
    generator = PostScriptGenerator()
    
    # Test Latin-1 characters
    test_cases = [
        ("Vebjørn Ljoså", "Vebj\\370rn Ljos\\345"),  # Norwegian
        ("café", "caf\\351"),  # French é
        ("über", "\\374ber"),  # German ü
        ("æøå", "\\346\\370\\345"),  # Norwegian letters
        ("ÆØÅ", "\\306\\330\\305"),  # Norwegian capitals
    ]
    
    for input_text, expected in test_cases:
        escaped = generator._escape_postscript(input_text)
        assert escaped == expected


def test_postscript_with_special_content():
    """Test PostScript generation with special characters in content."""
    generator = PostScriptGenerator()
    
    # Page with special characters
    pages = [[
        "Text with (parentheses)",
        "Text with backslash\\here",
        "Combined (test) with \\ both"
    ] + [""] * 63]
    
    ps_content = generator.generate_postscript(pages)
    
    # Check escaped content
    assert "(Text with \\(parentheses\\)) showline" in ps_content
    assert "(Text with backslash\\\\here) showline" in ps_content
    assert "(Combined \\(test\\) with \\\\ both) showline" in ps_content


def test_postscript_empty_pages():
    """Test PostScript generation with empty pages."""
    generator = PostScriptGenerator()
    
    # Empty page (66 empty lines)
    pages = [[""] * 66]
    
    ps_content = generator.generate_postscript(pages)
    
    # Should still have structure
    assert "%!PS-Adobe-3.0" in ps_content
    assert "%%Pages: 1" in ps_content
    assert "%%Page: 1 1" in ps_content
    assert "showline" in ps_content  # Empty lines still get showline
    assert "%%EOF" in ps_content


def test_postscript_page_structure():
    """Test that PostScript has correct page structure."""
    generator = PostScriptGenerator()
    
    # Create 3 pages
    pages = [["Page " + str(i+1)] + [""] * 65 for i in range(3)]
    
    ps_content = generator.generate_postscript(pages)
    
    # Check page count
    assert "%%Pages: 3" in ps_content
    
    # Check each page has proper structure
    for i in range(3):
        page_num = i + 1
        assert f"%%Page: {page_num} {page_num}" in ps_content
        assert f"(Page {page_num}) showline" in ps_content
    
    # Check showpage commands (one per page)
    assert ps_content.count("showpage") == 3
    assert ps_content.count("gsave") == 3
    assert ps_content.count("grestore") == 3


def test_postscript_styled_uses_bold_and_underline():
    """Styled PS generation switches fonts and draws underlines for styled runs."""
    generator = PostScriptGenerator()

    # One page with a single text area line containing mixed styles
    # Build an 85-char line with 10-char left margin + 65-char text + 10 right margin
    left_margin = " " * 10
    right_margin = " " * 10
    text = "Hello World".ljust(65)
    pages = [[left_margin + text + right_margin] + [""] * 65]
    # Build runs: bold on "Hello" (start_x=10), underline on "World" (start_x=16)
    STYLE_BOLD = 1
    STYLE_UNDER = 2
    runs_line = [
        (10, "Hello", STYLE_BOLD),
        (16, "World", STYLE_UNDER),
    ]
    page_runs = [[runs_line] + [None] * 65]
    ps_content = generator.generate_postscript(pages, page_runs)

    # Expect bold font switches present
    assert "/Courier-Bold-ISOLatin1" in ps_content
    # Expect underline drawing annotations present
    assert "underline segment" in ps_content or "lineto stroke" in ps_content

"""Tests for the two-page booklet sheet preview."""

from pagemark.print_preview import PrintPreview
from pagemark.print_formatter import PrintFormatter


def _format(paragraphs):
    formatter = PrintFormatter(paragraphs)
    return formatter.format_pages()


def test_sheet_preview_dimensions_courier():
    pages = _format(["Test"])
    preview = PrintPreview(pages)  # default 85-wide page
    sheet = preview.generate_sheet_preview(0, 0)

    # 33 rows tall (same as single page)
    assert len(sheet) == 33
    # Width is 2x the single-page preview width
    half = (85 + 1) // 2  # 43
    for line in sheet:
        assert len(line) == 2 * half


def test_sheet_preview_blank_padding_half():
    pages = _format(["Hello world"])
    preview = PrintPreview(pages)
    # Right side is out of range -> blank
    sheet = preview.generate_sheet_preview(0, 99)
    half = (85 + 1) // 2
    assert len(sheet) == 33
    for line in sheet:
        # Right half should be entirely spaces
        assert line[half:] == " " * half


def test_sheet_preview_blank_padding_left():
    pages = _format(["Hello world"])
    preview = PrintPreview(pages)
    sheet = preview.generate_sheet_preview(99, 0)
    half = (85 + 1) // 2
    for line in sheet:
        # Left half should be entirely spaces
        assert line[:half] == " " * half


def test_sheet_preview_with_border_dimensions():
    pages = _format(["Hello"])
    preview = PrintPreview(pages)
    bordered = preview.generate_sheet_preview_with_border(0, 0)
    half = (85 + 1) // 2
    # 33 content rows + 2 border rows
    assert len(bordered) == 35
    expected_width = 1 + half + 1 + half + 1  # left | mid | right borders
    for line in bordered:
        assert len(line) == expected_width
    # Top has T-down at fold; bottom T-up
    assert bordered[0][1 + half] == "┬"
    assert bordered[-1][1 + half] == "┴"
    # Middle vertical fold line
    for line in bordered[1:-1]:
        assert line[1 + half] == "│"


def test_sheet_preview_with_border_dimensions_elite():
    """Verify the wider 12-pitch (Prestige Elite) preview width."""
    from pagemark.font_config import get_font_config

    config = get_font_config("Prestige Elite Std")
    assert config is not None
    pages = PrintFormatter(["Test"], font_config=config).format_pages()
    preview = PrintPreview(pages, page_width=config.full_page_width)
    bordered = preview.generate_sheet_preview_with_border(0, 0)
    half = (config.full_page_width + 1) // 2  # 51 for 102-wide
    expected_width = 1 + half + 1 + half + 1
    for line in bordered:
        assert len(line) == expected_width


def test_sheet_preview_includes_content_from_both_pages():
    """Content from each of two distinct pages should appear in its half."""
    # Make a multi-page document so we have at least two distinct pages
    paragraphs = [f"Line {i}" for i in range(120)]
    pages = _format(paragraphs)
    assert len(pages) >= 2

    preview = PrintPreview(pages)
    half = (85 + 1) // 2

    # Render sheet with page 0 on left and page 1 on right
    sheet_01 = preview.generate_sheet_preview(0, 1)
    # Render swapped to confirm differences come from per-page content
    sheet_10 = preview.generate_sheet_preview(1, 0)

    # The two sheets are not identical (page contents differ)
    assert sheet_01 != sheet_10

    # Each half of sheet_01 should match the corresponding single-page preview
    p0 = preview.generate_preview(0)
    p1 = preview.generate_preview(1)
    for row, line in enumerate(sheet_01):
        assert line[:half] == p0[row]
        assert line[half:] == p1[row]

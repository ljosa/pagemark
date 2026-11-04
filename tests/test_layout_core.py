"""Exhaustive small-input contracts for layout, independent of the UI."""

from itertools import product

from pagemark.coordinates import DocumentPosition
from pagemark.layout import DocumentLayout, layout_paragraph


def test_exhaustive_source_mapping_and_caret_contract():
    alphabet = ["a", " ", "—", "界", "e\u0301"]
    for length in range(5):
        for tokens in product(alphabet, repeat=length):
            text = "".join(tokens)
            for width in range(1, 8):
                layout = layout_paragraph(text, width)
                assert layout.boundaries[-1] == len(text), (text, width)
                assert list(layout.boundaries) == sorted(layout.boundaries)
                for index, row in enumerate(layout.rows):
                    assert len(row.sources) == len(row.text), (text, width, row)
                    # Independent reconstruction from source indices; no width
                    # or cursor helper participates in the expected text.
                    expected = "".join(
                        " " if i is None else "-" if text[i] == "—" else text[i]
                        for i in row.sources
                    )
                    assert row.text == expected, (text, width, row)
                    for offset, column in row.caret_stops:
                        assert layout.line_for_char_index(offset) == index, (
                            text,
                            width,
                            row,
                        )
                        assert layout.visual_column(offset) == column
                        # Combining sequences can share a column: canonicalize
                        # to the first valid stop rather than assert a bijection.
                        canonical = layout.character_at_column(index, column)
                        assert layout.visual_column(canonical) == column
                        assert layout.line_for_char_index(canonical) == index


def test_unbroken_ascii_layout_matches_independent_division():
    for width in range(1, 12):
        for length in range(50):
            text = "x" * length
            layout = layout_paragraph(text, width)
            for offset in range(length + 1):
                assert layout.char_to_line_and_column(offset) == divmod(offset, width)
                assert layout.visual_column(offset) == offset % width


def test_cached_layout_is_not_mutable_through_compatibility_lists():
    layout = layout_paragraph("abc def", 5)
    layout.lines.clear()
    layout.cumulative_counts.clear()
    assert layout_paragraph("abc def", 5).lines == ["abc", "def"]


def test_document_layout_maps_positions_without_terminal_state():
    layout = DocumentLayout.build(["abc", "defgh", ""], 3)
    for line in range(layout.line_count):
        position = layout.position_at(line, 0)
        assert isinstance(position, DocumentPosition)
        assert layout.line_for_position(position) == line

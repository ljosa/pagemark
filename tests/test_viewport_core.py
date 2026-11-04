"""Compare viewport geometry with an independent, materialized row stream."""
from pagemark.viewport import PageBreakRow, TextRow, Viewport


def stream(total, page_length):
    result = []
    for line in range(total):
        if line and line % page_length == 0:
            result.append(PageBreakRow(line // page_length + 1))
        result.append(TextRow(line))
    return result


def test_viewport_matches_reference_rows_and_visibility():
    for total in range(1, 22):
        for page_length in (1, 2, 3, 7, 54):
            reference = stream(total, page_length)
            for height in (1, 2, 4, 10):
                for top in range(total):
                    viewport = Viewport(top, height, page_length)
                    offset = reference.index(TextRow(top))
                    expected = reference[offset:offset + height]
                    assert list(viewport.rows(total)) == expected
                    for index, row in enumerate(expected):
                        if isinstance(row, TextRow):
                            assert viewport.row_for_line(row.line) == index
                    for cursor in (0, top, total - 1):
                        visible = viewport.ensure_visible(cursor, total)
                        assert TextRow(cursor) in visible.rows(total)
                        assert visible.ensure_visible(cursor, total) == visible
                    for direction in (-1, 1):
                        moved = viewport.scroll_page(direction, total)
                        assert (moved.top - top) * direction >= 0
                        if 0 <= top + direction < total:
                            assert moved.top != top
                        clamped = moved.clamp_line(top, total)
                        assert TextRow(clamped) in moved.rows(total)


def test_stale_top_is_clamped_after_document_shrinks():
    viewport = Viewport(100, 24, 54)
    assert viewport.normalized(1).top == 0
    assert viewport.ensure_visible(0, 1).rows(1) == (TextRow(0),)

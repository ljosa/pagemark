"""Reproduce: down-arrow cursor gets stuck before end of document.

Bug report
----------
Open a long document in pagemark.  Press the down arrow repeatedly.
The cursor stops partway through the document even though there are
additional contents below.

Root cause
----------
In ``view.py``, ``move_cursor_down()`` checked
``end_paragraph_index >= len(self.model.paragraphs)`` to decide
whether the cursor had reached the bottom of the document.  But
``end_paragraph_index`` tracks *paragraph* boundaries, not visual
lines within the last paragraph.  When the last paragraph shown on
screen has wrapped lines that extend past the bottom of the view,
the check falsely concludes "end of document" and refuses to scroll.

Expected behaviour: pressing down-arrow should traverse every line of
the document, scrolling as needed, until the cursor reaches the very
last visual line.
"""

from __future__ import annotations

import pytest

pyte = pytest.importorskip("pyte")


@pytest.fixture
def small_term():
    """Provide a 12x80 TerminalHarness (small screen) for focused tests."""
    from terminal_harness import TerminalHarness

    harness = TerminalHarness(rows=12, cols=80)
    yield harness
    harness.stop()


def test_down_arrow_single_long_paragraph(small_term, tmp_path):
    """Simplest trigger: one paragraph that wraps past the screen.

    A 12-row terminal has 11 content rows (1 for status).  A single
    paragraph of ~150 words wraps to ~18 visual lines at 65 columns.
    The cursor must be able to reach the last word ("word149").
    """
    content = " ".join(f"word{i}" for i in range(150))
    test_file = tmp_path / "long.txt"
    test_file.write_text(content)

    small_term.start(str(test_file))
    assert small_term.wait_ready(timeout=5), "Editor did not start"

    marker = "word149"
    max_presses = 30  # 18 lines - 11 visible = 7 scrolls, plus margin
    presses = 0

    for presses in range(1, max_presses + 1):
        small_term.press("down")
        small_term.wait_stable(timeout=0.5, settle_time=0.05)
        if marker in small_term.screen_text():
            return  # PASS — reached the end

    screen = small_term.screen_text()
    assert marker in screen, (
        f"After {presses} down-arrow presses the last word ('{marker}') "
        f"is not visible.  Cursor at {small_term.get_cursor_position()}.\n"
        f"Screen:\n{screen}"
    )


def test_down_arrow_short_lines_then_long_paragraph(small_term, tmp_path):
    """Several short paragraphs followed by one long paragraph.

    The short paragraphs fill most of the 11 content rows, so only
    a few lines of the trailing long paragraph are visible.  The
    cursor must still be able to scroll through the remainder.
    """
    short = "\n".join(f"Line {i}" for i in range(1, 8))  # 7 lines
    # ~80 words -> ~5 visual lines at 65 cols.  7 + 5 = 12, > 11 rows.
    long_para = " ".join(f"end{i}" for i in range(80))
    content = short + "\n" + long_para
    test_file = tmp_path / "mixed.txt"
    test_file.write_text(content)

    small_term.start(str(test_file))
    assert small_term.wait_ready(timeout=5), "Editor did not start"

    marker = "end79"
    max_presses = 25

    for presses in range(1, max_presses + 1):
        small_term.press("down")
        small_term.wait_stable(timeout=0.5, settle_time=0.05)
        if marker in small_term.screen_text():
            return  # PASS

    screen = small_term.screen_text()
    assert marker in screen, (
        f"After {presses} down-arrow presses the last word ('{marker}') "
        f"is not visible.  Cursor at {small_term.get_cursor_position()}.\n"
        f"Screen:\n{screen}"
    )

"""Saddle-stitch booklet imposition.

A saddle-stitch booklet is printed on landscape sheets, two source pages per
side, then folded along the vertical center and stapled. For the folded
result to read in natural page order, source pages must be re-ordered
("imposed") and the page count padded to a multiple of four with blanks.

For an N-page document (padded to a multiple of 4), printed onto S = N/4
landscape sheets, the imposition is, for sheet i (1-indexed):

    front: (left=N - 2i + 2, right=2i - 1)
    back:  (left=2i,         right=N - 2i + 1)

so the duplex stack of sheets, folded along the vertical center, reads
1, 2, 3, ..., N. Page numbers are 1-based here; the API returns 0-based
indices into the padded source page list.
"""

from typing import List, Tuple


def pad_to_multiple_of_4(n: int) -> int:
    """Round ``n`` up to the nearest multiple of 4 (0 stays 0)."""
    if n <= 0:
        return 0
    return ((n + 3) // 4) * 4


def imposition_order(n_pages: int) -> List[Tuple[int, int]]:
    """Return saddle-stitch imposition for ``n_pages`` (must be a multiple of 4).

    The result is a list of ``(left_idx, right_idx)`` tuples — one entry per
    landscape sheet *side*, in print order: sheet 1 front, sheet 1 back,
    sheet 2 front, sheet 2 back, ... Indices are 0-based into the padded
    source-page list.
    """
    if n_pages == 0:
        return []
    if n_pages % 4 != 0:
        raise ValueError(f"n_pages must be a multiple of 4, got {n_pages}")

    sides: List[Tuple[int, int]] = []
    n_sheets = n_pages // 4
    for i in range(1, n_sheets + 1):
        front_left = n_pages - 2 * i + 2  # 1-based
        front_right = 2 * i - 1
        back_left = 2 * i
        back_right = n_pages - 2 * i + 1
        sides.append((front_left - 1, front_right - 1))
        sides.append((back_left - 1, back_right - 1))
    return sides

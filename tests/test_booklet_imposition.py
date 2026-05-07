"""Tests for booklet imposition logic."""

import pytest

from pagemark.booklet import pad_to_multiple_of_4, imposition_order


def test_pad_zero():
    assert pad_to_multiple_of_4(0) == 0


def test_pad_negative():
    assert pad_to_multiple_of_4(-3) == 0


def test_pad_one_to_four():
    assert pad_to_multiple_of_4(1) == 4
    assert pad_to_multiple_of_4(2) == 4
    assert pad_to_multiple_of_4(3) == 4
    assert pad_to_multiple_of_4(4) == 4


def test_pad_five_to_eight():
    assert pad_to_multiple_of_4(5) == 8
    assert pad_to_multiple_of_4(6) == 8
    assert pad_to_multiple_of_4(7) == 8
    assert pad_to_multiple_of_4(8) == 8


def test_pad_nine_to_twelve():
    assert pad_to_multiple_of_4(9) == 12


def test_imposition_zero():
    assert imposition_order(0) == []


def test_imposition_invalid_raises():
    with pytest.raises(ValueError):
        imposition_order(5)
    with pytest.raises(ValueError):
        imposition_order(2)


def test_imposition_4_pages():
    # Single sheet, 4 pages: front (4,1), back (2,3) -- 0-indexed
    assert imposition_order(4) == [(3, 0), (1, 2)]


def test_imposition_8_pages():
    # Two sheets:
    #   sheet 1 front (8,1), back (2,7)
    #   sheet 2 front (6,3), back (4,5)
    assert imposition_order(8) == [(7, 0), (1, 6), (5, 2), (3, 4)]


def test_imposition_12_pages():
    # Three sheets:
    #   sheet 1: front (12,1), back (2,11)
    #   sheet 2: front (10,3), back (4,9)
    #   sheet 3: front (8,5),  back (6,7)
    assert imposition_order(12) == [
        (11, 0), (1, 10),
        (9, 2),  (3, 8),
        (7, 4),  (5, 6),
    ]


def test_imposition_covers_all_pages_exactly_once():
    """Every padded page index appears exactly once across all sheet sides."""
    for n in (4, 8, 12, 16, 20, 100):
        sides = imposition_order(n)
        assert len(sides) == n // 2
        flat = [idx for pair in sides for idx in pair]
        assert sorted(flat) == list(range(n))


def test_imposition_natural_reading_order():
    """When folded as described in module docstring, pages read in 1..N order.

    Folding sheet i (1-indexed) places, in reading order:
      - sheet i front-right (page 2i-1)
      - sheet i back-left   (page 2i)
    on opening to that sheet from the front, and at the back of the booklet:
      - sheet i back-right  (page N - 2i + 1)
      - sheet i front-left  (page N - 2i + 2)
    """
    n = 8
    sides = imposition_order(n)
    # Sheet 1 front: (left, right) -> after folding the right is page 1
    assert sides[0][1] == 0  # page 1
    # Sheet 1 back: left is page 2
    assert sides[1][0] == 1  # page 2
    # Sheet 2 front-right is page 3, back-left is page 4
    assert sides[2][1] == 2
    assert sides[3][0] == 3
    # Sheet 2 back-right is page N-3 = 5; front-left is page N-2 = 6
    assert sides[3][1] == 4
    assert sides[2][0] == 5
    # Sheet 1 back-right is page N-1 = 7; front-left is page N = 8
    assert sides[1][1] == 6
    assert sides[0][0] == 7

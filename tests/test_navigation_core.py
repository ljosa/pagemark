from itertools import product

from pagemark.coordinates import DocumentPosition
from pagemark.navigation import NavigationState


def test_navigation_transition_matrix():
    styles = ((1, 2, 3), (), (2, 0, 1))
    for paragraph, column, preserve, extend in product(range(3), range(4), (False, True), (False, True)):
        if column > len(styles[paragraph]):
            continue
        target = DocumentPosition(paragraph, column)
        original = NavigationState(DocumentPosition(0, 2), desired_column=8, caret_style=3)
        moved = original.relocate(target, column, styles, preserve_column=preserve, extend_selection=extend)
        assert moved.cursor == target
        assert moved.desired_column == (8 if preserve else column)
        assert moved.anchor == (original.cursor if extend else None)
        assert moved.caret_style == (styles[paragraph][max(0, column - 1)] if styles[paragraph] else 0)
        again = moved.relocate(DocumentPosition(2, 2), 2, styles, preserve_column=True, extend_selection=extend)
        assert again.anchor == moved.anchor
        assert again.desired_column == moved.desired_column
        assert original == NavigationState(DocumentPosition(0, 2), desired_column=8, caret_style=3)


def test_history_restores_explicit_insertion_style_and_column():
    original = NavigationState(desired_column=9, caret_style=1)
    restored = original.relocate(DocumentPosition(0, 1), 1, ((0, 0),), caret_style=3)
    assert restored.caret_style == 3
    assert restored.desired_column == 1

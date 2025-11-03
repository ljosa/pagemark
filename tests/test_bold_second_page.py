"""Test bold formatting on second page."""

import unittest
from unittest.mock import Mock
from pagemark.model import TextModel, CursorPosition, StyleFlags
from pagemark.view import TerminalTextView


class TestBoldSecondPage(unittest.TestCase):
    """Test that bold formatting works correctly on the second page."""

    def test_selection_ranges_on_second_page(self):
        """Test that selection ranges are calculated correctly on the second page.

        Bug: When on page 2 (first_paragraph_line_offset > 0), the selection
        range calculation uses current_line_offset as an index into para_counts,
        but current_line_offset starts at first_paragraph_line_offset, not 0.
        This causes incorrect character range calculations.
        """
        # Create a long paragraph that spans multiple pages (54 lines per page)
        # Each line is about 70 characters
        lines = []
        for i in range(1, 120):
            lines.append(f'This is line {i:03d} of the test document for reproducing the bold selection bug.')
        text = ' '.join(lines)

        # Create view and model
        view = TerminalTextView()
        view.num_rows = 54
        view.num_columns = 80
        model = TextModel(view, paragraphs=[text])

        # Now let's look at the rendered paragraph to understand character positions
        from pagemark.view import render_paragraph
        _, para_counts = render_paragraph(text, 80)

        # Select a word on the second visual line of page 2 (visual line index 1)
        # The first visual line of page 2 is para line 54
        # The second visual line of page 2 is para line 55
        # Character range for line 55 is para_counts[54] to para_counts[55]
        line_55_start = para_counts[54]
        line_55_end = para_counts[55]

        # Select characters in the middle of line 55 (e.g., 5 chars in)
        select_start = line_55_start + 5
        select_end = line_55_start + 15

        # IMPORTANT: Set cursor position BEFORE rendering
        # Otherwise render() will center on cursor (0,0) and reset our offset
        model.cursor_position = CursorPosition(0, select_start)
        model.selection_start = CursorPosition(0, select_start)
        model.selection_end = CursorPosition(0, select_end)

        # Now render with the offset to simulate scrolling to second page
        view.start_paragraph_index = 0
        view.first_paragraph_line_offset = 54
        view.render()

        # Get selection ranges
        selection_ranges = view.get_selection_ranges()

        # The selection should appear on visual line 1 (second line on screen)
        # because line 0 is the first line of page 2 (para line 54)
        # and line 1 is the second line of page 2 (para line 55)
        self.assertIsNotNone(selection_ranges, "Selection ranges should not be None")
        self.assertIsNotNone(selection_ranges[1], "Line 1 should have a selection")

        # The selection should be at columns 5-15 of the visual line
        expected_start = 5
        expected_end = 15
        actual_start, actual_end = selection_ranges[1]

        self.assertEqual(actual_start, expected_start,
                        f"Selection should start at column {expected_start}, got {actual_start}")
        self.assertEqual(actual_end, expected_end,
                        f"Selection should end at column {expected_end}, got {actual_end}")

        # Line 0 should NOT have a selection
        self.assertIsNone(selection_ranges[0], "Line 0 should not have a selection")


if __name__ == '__main__':
    unittest.main()

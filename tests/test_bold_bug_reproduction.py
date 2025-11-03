"""Reproduce the bold formatting bug on second page."""

import unittest
from pagemark.model import TextModel, CursorPosition, StyleFlags
from pagemark.view import TerminalTextView
from pagemark.commands import ToggleBoldCommand
from pagemark.keyboard import KeyEvent, KeyType


class TestBoldBugReproduction(unittest.TestCase):
    """Reproduce the actual bug: bold applied to wrong line."""

    def test_bold_applied_to_correct_line_on_page_2(self):
        """Test that bold is applied to the correct characters on page 2.

        Bug reproduction:
        1. Open a two-page document
        2. Navigate to second visual line on second page
        3. Select a word
        4. Press Cmd-B (or Ctrl-B)
        5. BUG: Bold appears on first line of second page instead
        """
        # Create a long paragraph that spans multiple pages (54 lines per page)
        lines = []
        for i in range(1, 120):
            lines.append(f'This is line {i:03d} of the test document for reproducing the bold selection bug.')
        text = ' '.join(lines)

        # Create model and view
        view = TerminalTextView()
        view.num_rows = 54
        view.num_columns = 80
        model = TextModel(view, paragraphs=[text])

        # Get paragraph rendering info
        from pagemark.view import render_paragraph
        para_lines, para_counts = render_paragraph(text, 80)

        print(f"Total visual lines in paragraph: {len(para_lines)}")
        print(f"Lines per page: 54")
        print(f"Page 2 starts at visual line: 54")
        print(f"Page 2, line 0 char range: 0 to {para_counts[54]}")
        print(f"Page 2, line 1 char range: {para_counts[54]} to {para_counts[55]}")

        # Navigate to page 2
        view.start_paragraph_index = 0
        view.first_paragraph_line_offset = 54

        # Select a word on the SECOND visual line of page 2 (para line 55)
        # This should be characters at para_counts[54] to para_counts[55]
        line_55_start = para_counts[54]
        line_55_end = para_counts[55]

        # Select 10 characters starting at position 5 of line 55
        select_start = line_55_start + 5
        select_end = line_55_start + 15

        print(f"\nSelecting characters {select_start} to {select_end}")
        print(f"This should be on visual line 55 (second line of page 2)")

        # Set selection
        model.cursor_position = CursorPosition(0, select_start)
        model.selection_start = CursorPosition(0, select_start)
        model.selection_end = CursorPosition(0, select_end)

        # Render the view
        view.render()

        # Apply bold directly using the toggle style logic from commands.py
        # This simulates what happens when the user presses Ctrl-B
        from pagemark.commands import ToggleStyleCommand
        toggle_cmd = ToggleStyleCommand(StyleFlags.BOLD)
        toggle_cmd._toggle_selection_style(model, StyleFlags.BOLD)

        # Check that the CORRECT characters are bold
        # The selected characters (select_start to select_end) should be bold
        print(f"\nChecking styles from {select_start} to {select_end}")
        for i in range(select_start, select_end):
            self.assertTrue(
                model.styles[0][i] & StyleFlags.BOLD,
                f"Character {i} should be bold (in selected range {select_start}-{select_end})"
            )

        # Check that characters on the FIRST line of page 2 are NOT bold
        # First line is para line 54, char range 0 to para_counts[54]
        line_54_start = 0 if 54 == 0 else para_counts[53]
        line_54_end = para_counts[54]

        print(f"\nChecking that first line of page 2 is NOT bold")
        print(f"First line char range: {line_54_start} to {line_54_end}")

        # Check characters at the same visual position on line 54
        check_start = line_54_start + 5
        check_end = line_54_start + 15
        print(f"Checking characters {check_start} to {check_end} are NOT bold")

        for i in range(check_start, check_end):
            self.assertFalse(
                model.styles[0][i] & StyleFlags.BOLD,
                f"Character {i} should NOT be bold (not in selected range)"
            )


if __name__ == '__main__':
    unittest.main()

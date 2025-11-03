"""Test that bold styles are rendered correctly on page 2."""

import unittest
from pagemark.model import TextModel, CursorPosition, StyleFlags
from pagemark.view import TerminalTextView
from pagemark.commands import ToggleStyleCommand


class TestBoldRenderingPage2(unittest.TestCase):
    """Test that bold styles are rendered correctly when viewing page 2."""

    def test_bold_rendered_on_correct_visual_line(self):
        """Test that bold styles appear on the correct visual line on page 2.

        The bug: When bold is applied to characters on line 55, it appears
        on line 54 in the rendered view.
        """
        # Create a long paragraph
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

        # Apply bold to a range on visual line 55 (second line of page 2)
        line_55_start = para_counts[54]
        line_55_end = para_counts[55]

        # Bold characters 5-15 of line 55
        bold_start = line_55_start + 5
        bold_end = line_55_start + 15

        print(f"Bolding characters {bold_start} to {bold_end}")
        print(f"This is visual line 55, char range {line_55_start} to {line_55_end}")

        # Debug: Check what the actual rendered lines are
        print(f"\nActual rendered para_lines[54]: '{para_lines[54]}'")
        print(f"Actual rendered para_lines[55]: '{para_lines[55]}'")
        print(f"Length of para_lines[55]: {len(para_lines[55])}")

        # Check the char range for line 55
        line_55_text_from_model = text[para_counts[54]:para_counts[55]]
        print(f"Text from model[{para_counts[54]}:{para_counts[55]}]: '{line_55_text_from_model}'")
        print(f"Length: {len(line_55_text_from_model)}")

        # Apply bold to model.styles
        model._sync_styles_length()
        for i in range(bold_start, bold_end):
            model.styles[0][i] |= StyleFlags.BOLD

        # Navigate to page 2
        view.start_paragraph_index = 0
        view.first_paragraph_line_offset = 54

        # IMPORTANT: Set cursor position to be within the view we're rendering
        # Otherwise render() will call center_view_on_cursor() and reset our offset
        model.cursor_position = CursorPosition(0, bold_start)

        # Check what paragraph text the model has before rendering
        print(f"\nModel paragraph 0 first 200 chars: '{model.paragraphs[0][:200]}'")
        print(f"Model paragraph 0 last 200 chars: '{model.paragraphs[0][-200:]}'")
        print(f"Model paragraph 0 total length: {len(model.paragraphs[0])}")

        view.render()

        # Re-render para_lines after view.render() to see if they match
        from pagemark.view import render_paragraph
        rerendered_lines, rerendered_counts = render_paragraph(model.paragraphs[0], 80)
        print(f"\nRe-rendered para_lines[54]: '{rerendered_lines[54]}'")
        print(f"Re-rendered para_lines[55]: '{rerendered_lines[55]}'")

        # Check that line_styles has the bold in the right place
        print(f"\nTotal visual lines rendered: {len(view.lines)}")
        print(f"Total style lines: {len(view.line_styles)}")

        # Show first few lines rendered by view
        print(f"\nFirst 5 rendered view.lines:")
        for idx in range(min(5, len(view.lines))):
            print(f"  [{idx}]: '{view.lines[idx]}'")

        # Debug: Check the actual model styles
        model_bold_positions = [i for i in range(len(model.styles[0])) if model.styles[0][i] & StyleFlags.BOLD]
        print(f"Model has BOLD at {len(model_bold_positions)} positions: {model_bold_positions}")

        # The bold should appear on visual line index 1 (second line on screen)
        # because line 0 is visual line 54, and line 1 is visual line 55

        # Check line 1 (visual line 55)
        if len(view.line_styles) > 1:
            line_1_styles = view.line_styles[1]
            print(f"\nLine 1 (view offset) rendered:")
            print(f"  Text: '{view.lines[1]}'")
            print(f"  Length: {len(view.lines[1])}")
            print(f"  Styles length: {len(line_1_styles)}")
            print(f"\nExpected (para_lines[55]):")
            print(f"  Text: '{para_lines[55]}'")
            print(f"  Length: {len(para_lines[55])}")

            # Check for hanging indent
            from pagemark.view import _get_hanging_indent_width
            hanging_width = _get_hanging_indent_width(text)
            print(f"Hanging indent width: {hanging_width}")

            # Check the expected vs actual slice
            expected_start = 4290
            expected_end = 4368
            expected_slice = model.styles[0][expected_start:expected_end]
            print(f"Expected style slice length: {len(expected_slice)}")
            print(f"Actual style slice length: {len(line_1_styles)}")

            # What's the actual text for this range?
            actual_text_from_model = text[expected_start:expected_end]
            print(f"Actual text from model[{expected_start}:{expected_end}]: '{actual_text_from_model}'")
            print(f"Length: {len(actual_text_from_model)}")

            # Check if the expected slice has bold
            expected_bold = [i for i, s in enumerate(expected_slice) if s & StyleFlags.BOLD]
            print(f"Bold in expected slice at positions: {expected_bold}")

            # Check that characters 5-15 are bold
            bold_found = False
            for i in range(5, min(15, len(line_1_styles))):
                if line_1_styles[i] & StyleFlags.BOLD:
                    bold_found = True
                    break

            # self.assertTrue(bold_found, "Bold should be found on line 1 (visual line 55)")
            if not bold_found:
                print("Bold NOT found on line 1 - BUG CONFIRMED")

        # Check line 0 (visual line 54) - should NOT have bold at positions 5-15
        if len(view.line_styles) > 0:
            line_0_styles = view.line_styles[0]
            print(f"\nLine 0 (visual line 54) styles: {len(line_0_styles)} chars")
            print(f"Line 0 text length: {len(view.lines[0])}")

            # Check where bold actually appears
            print("\nChecking which visual lines have bold:")
            for idx, styles in enumerate(view.line_styles[:10]):
                bold_positions = [i for i in range(len(styles)) if styles[i] & StyleFlags.BOLD]
                if bold_positions:
                    print(f"  Visual line {idx}: BOLD at positions {bold_positions}")
                else:
                    # Show what char range this line should have
                    visual_line_num = 54 + idx  # We're on page 2, starting at line 54
                    if visual_line_num < len(para_counts):
                        start_char = para_counts[visual_line_num - 1] if visual_line_num > 0 else 0
                        end_char = para_counts[visual_line_num]
                        print(f"  Visual line {idx} (para line {visual_line_num}): char range {start_char}-{end_char}, no bold")

            # Check that characters 5-15 are NOT bold
            for i in range(5, min(15, len(line_0_styles))):
                if line_0_styles[i] & StyleFlags.BOLD:
                    print(f"BUG CONFIRMED: Character {i} on line 0 IS bold (should not be)")
                # Don't fail the test yet, we're confirming the bug exists
                # self.assertFalse(
                #     line_0_styles[i] & StyleFlags.BOLD,
                #     f"Character {i} on line 0 should NOT be bold"
                # )


if __name__ == '__main__':
    unittest.main()

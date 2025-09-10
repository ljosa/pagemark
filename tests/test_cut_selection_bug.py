"""Regression test for IndexError bug when cutting selected text.

This test reproduces the bug reported in bug-report.txt where cutting
selected text causes an IndexError in view.py line 278 when
first_paragraph_line_offset becomes invalid after the paragraph shrinks.
"""

import unittest
from unittest.mock import Mock
from pagemark.model import TextModel, CursorPosition
from pagemark.view import render_paragraph


class TestCutSelectionBug(unittest.TestCase):
    """Test for IndexError bug when cutting text that shrinks paragraph lines."""
    
    def setUp(self):
        """Set up test environment with mock view."""
        # Create a mock view that simulates the problematic state
        self.mock_view = Mock()
        self.mock_view.num_rows = 20
        self.mock_view.num_columns = 80
        self.mock_view.start_paragraph_index = 0
        self.mock_view.first_paragraph_line_offset = 0
        self.mock_view.end_paragraph_index = 10
        
        # Store original render for later restoration
        self.original_render = self.mock_view.render
        
    def test_cut_selection_with_invalid_line_offset(self):
        """Test that cutting text doesn't cause IndexError when line offset becomes invalid.
        
        This is a regression test for the bug where:
        1. A paragraph has multiple lines when wrapped
        2. The view's first_paragraph_line_offset is set to line 2 or higher
        3. After cutting text, the paragraph shrinks to fewer lines
        4. render() crashes trying to access para_counts[first_paragraph_line_offset - 1]
        
        This test should FAIL when the bug is present and PASS when it's fixed.
        """
        # Create model with very long text that wraps to 3+ lines
        # Make sure it's long enough to have at least 3 lines
        long_text = "This is a long paragraph with lots of text that will definitely wrap to multiple lines. " * 4
        self.model = TextModel(self.mock_view, paragraphs=[
            "First paragraph",
            long_text,  # This will wrap to 3+ lines at 80 columns
            "Third paragraph"
        ])
        
        # Verify the second paragraph wraps to multiple lines
        para_lines, para_counts = render_paragraph(long_text, 80)
        initial_line_count = len(para_lines)
        self.assertGreaterEqual(initial_line_count, 3, 
                               f"Test setup: paragraph should wrap to at least 3 lines, got {initial_line_count}")
        
        # Position view at the second paragraph with line offset of 2
        # This simulates being scrolled to the 3rd line of the paragraph
        self.mock_view.start_paragraph_index = 1
        self.mock_view.first_paragraph_line_offset = 2  # Force offset to 2 (3rd line)
        
        # Use the actual TerminalTextView render method to catch the real bug
        from pagemark.view import TerminalTextView
        
        # Create a real view instance using the TextView protocol
        real_view = TerminalTextView()
        real_view._model = self.model
        real_view.num_rows = 20
        real_view.num_columns = 80
        real_view.start_paragraph_index = 1
        real_view.first_paragraph_line_offset = 2
        
        # Replace model's view with the real one temporarily
        original_view = self.model.view
        self.model.view = real_view
        
        try:
            # Select a very large portion of text in the second paragraph
            # This will cause the paragraph to shrink from 5 lines to 1 line when cut
            self.model.selection_start = CursorPosition(1, 20)
            self.model.selection_end = CursorPosition(1, 300)  # Cut 280 chars to go from 352 to 72
            
            # Verify selection is set
            selected_text = self.model.get_selected_text()
            self.assertGreater(len(selected_text), 50, 
                              "Should have selected substantial text")
            
            # The bug occurs when cut_selection calls delete_selection which calls render
            # This should NOT raise an IndexError when the bug is fixed
            result = self.model.cut_selection()
            
            # If we get here without an IndexError, the bug is fixed (or not present)
            self.assertTrue(result, "Cut operation should succeed")
            
            # Verify the text was actually cut
            self.assertLess(len(self.model.paragraphs[1]), 100, 
                           "Paragraph should be much shorter after cut")
            
        finally:
            # Restore original view
            self.model.view = original_view
        
    def test_cut_selection_empty_paragraph(self):
        """Test cutting all text from a paragraph doesn't cause IndexError.
        
        This tests the edge case where cutting leaves an empty paragraph.
        """
        self.model = TextModel(self.mock_view, paragraphs=[
            "First paragraph",
            "Second paragraph to be deleted",
            "Third paragraph"
        ])
        
        # No special render needed for this test since offset is 0
        # Select entire second paragraph
        self.model.selection_start = CursorPosition(1, 0)
        self.model.selection_end = CursorPosition(1, len(self.model.paragraphs[1]))
        
        # Cut the selection - this should work without IndexError
        # even though it leaves an empty paragraph
        result = self.model.cut_selection()
        self.assertTrue(result, "Cut should succeed")
        self.assertEqual(self.model.paragraphs[1], "", "Paragraph should be empty after cut")
        
    def test_cut_selection_cross_paragraph(self):
        """Test cutting text across paragraphs doesn't cause IndexError.
        
        This tests cutting from middle of one paragraph to middle of next.
        """
        self.model = TextModel(self.mock_view, paragraphs=[
            "First paragraph with some text",
            "Second paragraph with more text that might wrap to multiple lines when displayed",
            "Third paragraph with text"
        ])
        
        # Select from middle of paragraph 1 to middle of paragraph 2
        self.model.selection_start = CursorPosition(1, 15)
        self.model.selection_end = CursorPosition(2, 10)
        
        # This should work without IndexError
        result = self.model.cut_selection()
        self.assertTrue(result, "Cross-paragraph cut should succeed")
        
        # Verify paragraphs were merged
        self.assertEqual(len(self.model.paragraphs), 2, "Should have 2 paragraphs after merge")
        # After cutting from char 15 of para 1 to char 10 of para 2, we get:
        # "Second paragrap" + "graph with text"
        self.assertIn("Second paragrap", self.model.paragraphs[1])
        self.assertIn("graph with text", self.model.paragraphs[1])


if __name__ == '__main__':
    unittest.main()
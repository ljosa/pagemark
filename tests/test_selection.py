"""Test selection functionality."""

import unittest
from unittest.mock import Mock, MagicMock
from pagemark.model import TextModel, CursorPosition
from pagemark.keyboard import KeyboardHandler, KeyEvent, KeyType


class TestSelection(unittest.TestCase):
    """Test selection operations."""
    
    def setUp(self):
        """Set up test environment."""
        self.mock_view = Mock()
        self.mock_view.render = Mock()
        self.mock_view.start_paragraph_index = 0
        self.mock_view.end_paragraph_index = 10
        self.model = TextModel(self.mock_view, paragraphs=[
            "The quick brown fox",
            "jumps over the lazy dog"
        ])
        
    def test_selection_start(self):
        """Test starting a selection."""
        self.model.cursor_position = CursorPosition(0, 4)  # At "quick"
        self.model.start_selection()
        
        self.assertIsNotNone(self.model.selection_start)
        self.assertEqual(self.model.selection_start.paragraph_index, 0)
        self.assertEqual(self.model.selection_start.character_index, 4)
        
    def test_selection_end_update(self):
        """Test updating selection end."""
        self.model.cursor_position = CursorPosition(0, 4)
        self.model.start_selection()
        
        # Move cursor to select "quick"
        self.model.cursor_position = CursorPosition(0, 9)
        self.model.update_selection_end()
        
        self.assertIsNotNone(self.model.selection_end)
        self.assertEqual(self.model.selection_end.paragraph_index, 0)
        self.assertEqual(self.model.selection_end.character_index, 9)
        
    def test_get_selected_text(self):
        """Test getting selected text."""
        # Select "quick"
        self.model.cursor_position = CursorPosition(0, 4)
        self.model.start_selection()
        self.model.cursor_position = CursorPosition(0, 9)
        self.model.update_selection_end()
        
        selected = self.model.get_selected_text()
        self.assertEqual(selected, "quick")
        
    def test_multi_line_selection(self):
        """Test selection across multiple paragraphs."""
        # Start at "fox"
        self.model.cursor_position = CursorPosition(0, 16)
        self.model.start_selection()
        
        # End at "jumps"
        self.model.cursor_position = CursorPosition(1, 5)
        self.model.update_selection_end()
        
        selected = self.model.get_selected_text()
        self.assertEqual(selected, "fox\njumps")
        
    def test_copy_selection(self):
        """Test copying selected text."""
        # Select "quick"
        self.model.cursor_position = CursorPosition(0, 4)
        self.model.start_selection()
        self.model.cursor_position = CursorPosition(0, 9)
        self.model.update_selection_end()
        
        result = self.model.copy_selection()
        self.assertTrue(result)
        self.assertEqual(self.model.clipboard, "quick")
        
        # Selection should remain
        self.assertIsNotNone(self.model.selection_start)
        
    def test_cut_selection(self):
        """Test cutting selected text."""
        # Select "quick"
        self.model.cursor_position = CursorPosition(0, 4)
        self.model.start_selection()
        self.model.cursor_position = CursorPosition(0, 9)
        self.model.update_selection_end()
        
        result = self.model.cut_selection()
        self.assertTrue(result)
        self.assertEqual(self.model.clipboard, "quick")
        self.assertEqual(self.model.paragraphs[0], "The  brown fox")
        
        # Selection should be cleared
        self.assertIsNone(self.model.selection_start)
        
    def test_paste(self):
        """Test pasting text."""
        self.model.clipboard = "fast"
        self.model.cursor_position = CursorPosition(0, 4)
        
        self.model.paste()
        self.assertEqual(self.model.paragraphs[0], "The fastquick brown fox")
        self.assertEqual(self.model.cursor_position.character_index, 8)
        
    def test_delete_selection(self):
        """Test deleting selected text."""
        # Select "quick brown"
        self.model.cursor_position = CursorPosition(0, 4)
        self.model.start_selection()
        self.model.cursor_position = CursorPosition(0, 15)
        self.model.update_selection_end()
        
        self.model.delete_selection()
        self.assertEqual(self.model.paragraphs[0], "The  fox")
        self.assertIsNone(self.model.selection_start)
        
    def test_clear_selection(self):
        """Test clearing selection."""
        self.model.cursor_position = CursorPosition(0, 4)
        self.model.start_selection()
        self.model.cursor_position = CursorPosition(0, 9)
        self.model.update_selection_end()
        
        self.model.clear_selection()
        self.assertIsNone(self.model.selection_start)
        self.assertIsNone(self.model.selection_end)




if __name__ == '__main__':
    unittest.main()
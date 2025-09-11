"""Unit tests for print dialog font selection functionality."""

import unittest
from unittest.mock import Mock, patch, MagicMock
from pagemark.print_dialog import PrintDialog, PrintOptions, PrintAction
from pagemark.model import TextModel
from pagemark.view import TerminalTextView
from pagemark.session import get_session, SessionKeys
from pagemark.font_config import get_font_config


class TestPrintDialogFontSelection(unittest.TestCase):
    """Test print dialog font selection features."""
    
    def setUp(self):
        """Set up test fixtures."""
        # Clear session
        get_session().clear()
        
        # Create mock view and model
        self.view = TerminalTextView()
        self.view.num_columns = 65
        self.model = TextModel(self.view, paragraphs=["Test paragraph"])
        
    def test_default_font_selection(self):
        """Test that Courier is selected by default."""
        dialog = PrintDialog(self.model, None)
        
        self.assertEqual(dialog.selected_font_index, 0)
        self.assertEqual(dialog.available_fonts[0], "Courier")
        self.assertEqual(dialog.line_length, 65)
        
    def test_font_detection(self):
        """Test font detection includes Courier at minimum."""
        dialog = PrintDialog(self.model, None)
        
        self.assertIn("Courier", dialog.available_fonts)
        self.assertEqual(dialog.available_fonts[0], "Courier")
        
    @patch('pagemark.pdf_generator.PDFGenerator')
    def test_font_detection_with_prestige_elite(self, mock_pdf_gen):
        """Test font detection when Prestige Elite is available."""
        # Mock successful font load
        mock_pdf_gen.return_value = Mock()
        
        dialog = PrintDialog(self.model, None)
        
        self.assertEqual(len(dialog.available_fonts), 2)
        self.assertIn("Prestige Elite Std", dialog.available_fonts)
        
    @patch('pagemark.pdf_generator.PDFGenerator')
    def test_font_detection_with_missing_font(self, mock_pdf_gen):
        """Test font detection when Prestige Elite is not available."""
        from pagemark.pdf_generator import FontLoadError
        
        # Mock font load failure
        mock_pdf_gen.side_effect = FontLoadError("Font not found")
        
        dialog = PrintDialog(self.model, None)
        
        # Should only have Courier
        self.assertEqual(len(dialog.available_fonts), 1)
        self.assertEqual(dialog.available_fonts[0], "Courier")
        
    def test_session_persistence_font_name(self):
        """Test font selection persists in session."""
        session = get_session()
        
        # Set font in session
        session.set(SessionKeys.FONT_NAME, "Courier")
        
        dialog = PrintDialog(self.model, None)
        
        self.assertEqual(dialog.available_fonts[dialog.selected_font_index], "Courier")
        
    def test_session_persistence_invalid_font(self):
        """Test handling of invalid font in session."""
        session = get_session()
        
        # Set non-existent font
        session.set(SessionKeys.FONT_NAME, "NonExistent Font")
        
        dialog = PrintDialog(self.model, None)
        
        # Should default to Courier
        self.assertEqual(dialog.selected_font_index, 0)
        self.assertEqual(dialog.available_fonts[0], "Courier")
        
    def test_line_length_for_courier(self):
        """Test line length for Courier (10-pitch)."""
        dialog = PrintDialog(self.model, None)
        dialog.selected_font_index = 0  # Courier
        
        config = dialog._get_current_font_config()
        
        self.assertEqual(config.text_width, 65)
        self.assertEqual(config.pitch, 10)
        
    @patch('pagemark.pdf_generator.PDFGenerator')
    def test_line_length_for_prestige_elite(self, mock_pdf_gen):
        """Test line length for Prestige Elite (12-pitch)."""
        # Mock successful font load
        mock_pdf_gen.return_value = Mock()
        
        dialog = PrintDialog(self.model, None)
        
        if "Prestige Elite Std" in dialog.available_fonts:
            dialog.selected_font_index = dialog.available_fonts.index("Prestige Elite Std")
            config = dialog._get_current_font_config()
            
            self.assertEqual(config.text_width, 72)
            self.assertEqual(config.pitch, 12)
            
    def test_preview_width_calculation(self):
        """Test preview width calculation for different fonts."""
        dialog = PrintDialog(self.model, None)
        
        # Courier (10-pitch)
        dialog.selected_font_index = 0
        dialog.font_config = dialog._get_current_font_config()
        preview_width = dialog._get_preview_width()
        self.assertEqual(preview_width, 85)
        
    def test_double_spacing_session(self):
        """Test double spacing persistence."""
        session = get_session()
        session.set(SessionKeys.DOUBLE_SPACING, True)
        
        dialog = PrintDialog(self.model, None)
        
        self.assertTrue(dialog.double_spacing)
        
    def test_get_print_options_printer(self):
        """Test getting print options for printer output."""
        dialog = PrintDialog(self.model, None)
        dialog.selected_output = 0  # Assume first is a printer
        dialog.output_options = ["Test Printer", "PDF File"]
        
        options = dialog._get_print_options()
        
        self.assertEqual(options.action, PrintAction.PRINT)
        self.assertEqual(options.printer_name, "Test Printer")
        self.assertEqual(options.font_name, "Courier")
        
    def test_get_print_options_pdf(self):
        """Test getting print options for PDF output."""
        dialog = PrintDialog(self.model, None)
        dialog.output_options = ["PDF File"]
        dialog.selected_output = 0
        
        options = dialog._get_print_options()
        
        self.assertEqual(options.action, PrintAction.SAVE_PDF)
        self.assertEqual(options.pdf_filename, "output.pdf")
        self.assertEqual(options.font_name, "Courier")
        
    def test_reformat_pages(self):
        """Test page reformatting when settings change."""
        dialog = PrintDialog(self.model, None)
        
        # Store initial page count
        initial_pages = len(dialog.pages)
        
        # Change spacing
        dialog.double_spacing = True
        dialog._reformat_pages()
        
        # Pages should exist (even if count changes)
        self.assertIsNotNone(dialog.pages)
        self.assertIsNotNone(dialog.preview)
        
    def test_font_config_error_handling(self):
        """Test error handling for missing font configuration."""
        dialog = PrintDialog(self.model, None)
        dialog.available_fonts = ["Unknown Font"]
        dialog.selected_font_index = 0
        
        with self.assertRaises(ValueError) as ctx:
            dialog._get_current_font_config()
            
        self.assertIn("No configuration found", str(ctx.exception))


if __name__ == '__main__':
    unittest.main()
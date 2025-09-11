"""Unit tests for font configuration module."""

import unittest
from pagemark.font_config import (
    FontConfig, 
    get_font_config, 
    FONT_CONFIGS,
    LETTER_WIDTH_INCHES,
    STANDARD_MARGIN_INCHES,
    NARROW_MARGIN_INCHES
)


class TestFontConfig(unittest.TestCase):
    """Test font configuration functionality."""
    
    def test_courier_config(self):
        """Test Courier font configuration (10-pitch)."""
        config = get_font_config("Courier")
        self.assertIsNotNone(config)
        self.assertEqual(config.name, "Courier")
        self.assertEqual(config.pitch, 10)
        self.assertEqual(config.point_size, 12)
        self.assertEqual(config.text_width, 65)
        self.assertEqual(config.left_margin_chars, 10)
        self.assertEqual(config.right_margin_chars, 10)
        self.assertEqual(config.full_page_width, 85)
        self.assertFalse(config.is_embedded)
        
    def test_prestige_elite_config(self):
        """Test Prestige Elite font configuration (12-pitch)."""
        config = get_font_config("Prestige Elite Std")
        self.assertIsNotNone(config)
        self.assertEqual(config.name, "Prestige Elite Std")
        self.assertEqual(config.pitch, 12)
        self.assertEqual(config.point_size, 10)
        self.assertEqual(config.text_width, 72)
        self.assertEqual(config.left_margin_chars, 15)
        self.assertEqual(config.right_margin_chars, 15)
        self.assertEqual(config.full_page_width, 102)
        self.assertTrue(config.is_embedded)
        
    def test_unknown_font(self):
        """Test that unknown font returns None."""
        config = get_font_config("Unknown Font")
        self.assertIsNone(config)
        
    def test_line_height_constant(self):
        """Test that line height is always 12 points (6 lpi)."""
        for font_name in FONT_CONFIGS:
            config = get_font_config(font_name)
            self.assertEqual(config.line_height, 12)
            
    def test_10_pitch_calculations(self):
        """Test 10-pitch dimension calculations."""
        config = FontConfig.create_10_pitch(
            name="Test10",
            pdf_name="Test10",
            pdf_bold_name="Test10-Bold"
        )
        # 8.5" * 10 cpi = 85 chars total
        self.assertEqual(config.full_page_width, 85)
        # 1" margins * 10 cpi = 10 chars each
        self.assertEqual(config.left_margin_chars, 10)
        self.assertEqual(config.right_margin_chars, 10)
        # 85 - 20 = 65 chars text
        self.assertEqual(config.text_width, 65)
        
    def test_12_pitch_calculations(self):
        """Test 12-pitch dimension calculations."""
        config = FontConfig.create_12_pitch(
            name="Test12",
            pdf_name="Test12",
            pdf_bold_name="Test12-Bold"
        )
        # 8.5" * 12 cpi = 102 chars total
        self.assertEqual(config.full_page_width, 102)
        # 1.25" margins * 12 cpi = 15 chars each
        self.assertEqual(config.left_margin_chars, 15)
        self.assertEqual(config.right_margin_chars, 15)
        # 102 - 30 = 72 chars text
        self.assertEqual(config.text_width, 72)
        
    def test_font_config_immutable(self):
        """Test that FontConfig is immutable (frozen dataclass)."""
        config = get_font_config("Courier")
        with self.assertRaises(AttributeError):
            config.text_width = 100
            
    def test_pdf_names(self):
        """Test PDF font names are set correctly."""
        courier = get_font_config("Courier")
        self.assertEqual(courier.pdf_name, "Courier")
        self.assertEqual(courier.pdf_bold_name, "Courier-Bold")
        
        elite = get_font_config("Prestige Elite Std")
        self.assertEqual(elite.pdf_name, "PrestigeEliteStd")
        self.assertEqual(elite.pdf_bold_name, "PrestigeEliteStd-Bold")


if __name__ == '__main__':
    unittest.main()
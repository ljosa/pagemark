"""Test Unicode support in PDF generation."""

import unittest
from pagemark.pdf_generator import PDFGenerator


class TestPDFUnicode(unittest.TestCase):
    """Test that PDF generation properly handles Unicode characters."""
    
    def setUp(self):
        """Set up test environment."""
        self.generator = PDFGenerator()
    
    def test_unicode_characters_in_pdf(self):
        """Test that various Unicode characters render correctly in PDF."""
        # Test page with various Unicode characters
        test_lines = [
            "Basic ASCII: Hello World!",
            "Extended Latin: café, naïve, résumé",
            "Currency symbols: € £ ¥ ₹ ₽ ¢",
            "Math symbols: ∑ ∏ √ ∞ ≈ ≠ ≤ ≥ ± ÷",
            "Greek letters: α β γ δ ε λ μ π σ φ ω Ω",
            "Arrows: → ← ↑ ↓ ↔ ⇒ ⇐ ⇑ ⇓ ⇔",
            "Box drawing: ─ │ ┌ ┐ └ ┘ ├ ┤ ┬ ┴ ┼",
            "Emoji: 😀 👍 ❤️ ✓ ✗ ⚡ ★ ☆",
            "Chinese: 你好世界",
            "Japanese: こんにちは世界",
            "Korean: 안녕하세요",
            "Arabic: مرحبا بالعالم",
            "Hebrew: שלום עולם",
            "Russian: Привет мир",
            "Special chars: — " " ' ' … •",
        ]
        
        # Pad with empty lines to make a full page (66 lines)
        while len(test_lines) < 66:
            test_lines.append("")
        
        pages = [test_lines]
        
        # Generate PDF
        pdf_bytes = self.generator.generate_pdf(pages)
        
        # Basic validation
        self.assertIsNotNone(pdf_bytes)
        self.assertGreater(len(pdf_bytes), 0)
        
        # Check that PDF header is present
        self.assertTrue(pdf_bytes.startswith(b'%PDF'))
        
        # For debugging: write PDF to file to inspect manually
        # with open('test_unicode.pdf', 'wb') as f:
        #     f.write(pdf_bytes)
    
    def test_make_pdf_safe_no_substitutions(self):
        """Test that _make_pdf_safe only preserves Windows-1252 chars and replaces others with '?'."""
        test_strings = [
            ("café", "café"),  # Windows-1252 supported, preserved
            ("€100", "€100"),  # Euro is in Windows-1252, preserved  
            ("Hello 世界", "Hello ??"),  # Chinese replaced with ?
            ("α + β = γ", "? + ? = ?"),  # Greek letters replaced with ?
            ("😀", "?"),  # Emoji replaced with ?
            ("→ ← ↑ ↓", "? ? ? ?"),  # Arrows replaced with ?
            ("≈ ≠ ≤ ≥", "? ? ? ?"),  # Math symbols replaced with ?
            ("—", "—"),  # Em dash is in Windows-1252, preserved
            ('"Hello"', '"Hello"'),  # Smart quotes are in Windows-1252, preserved
            ("∑ = π × 2", "? = ? × 2"),  # Greek/math replaced, × preserved (in cp1252)
            ("√16 = 4", "?16 = 4"),  # Square root replaced with ?
            ("∞", "?"),  # Infinity replaced with ?
            ("✓ ✗", "? ?"),  # Check marks replaced with ?
            ("• Bullet", "• Bullet"),  # Bullet is in Windows-1252, preserved
        ]
        
        for input_str, expected in test_strings:
            result = self.generator._make_pdf_safe(input_str)
            self.assertEqual(result, expected, 
                           f"Unicode string '{input_str}' should become '{expected}', got '{result}'")
    
    def test_unprintable_warning_system(self):
        """Test that warning system correctly tracks unprintable characters."""
        # Test with no unprintable characters
        self.generator._make_pdf_safe("Hello World")
        self.assertFalse(self.generator.has_unprintable)
        self.assertIsNone(self.generator.get_unprintable_warning())
        
        # Test with Windows-1252 characters (no warning)
        self.generator.unprintable_chars = set()
        self.generator.has_unprintable = False
        self.generator._make_pdf_safe("café €100 • —")
        self.assertFalse(self.generator.has_unprintable)
        self.assertIsNone(self.generator.get_unprintable_warning())
        
        # Test with unprintable characters
        self.generator.unprintable_chars = set()
        self.generator.has_unprintable = False
        self.generator._make_pdf_safe("Hello 世界 😀 α β γ")
        self.assertTrue(self.generator.has_unprintable)
        warning = self.generator.get_unprintable_warning()
        self.assertIsNotNone(warning)
        self.assertIn("unprintable character(s)", warning)
        self.assertIn("replaced with '?'", warning)
        
        # Test that specific characters are tracked
        self.generator.unprintable_chars = set()
        self.generator.has_unprintable = False
        self.generator._make_pdf_safe("→←↑↓")
        self.assertEqual(len(self.generator.unprintable_chars), 4)
        self.assertIn('→', self.generator.unprintable_chars)
        self.assertIn('←', self.generator.unprintable_chars)
        self.assertIn('↑', self.generator.unprintable_chars)
        self.assertIn('↓', self.generator.unprintable_chars)


if __name__ == '__main__':
    unittest.main()
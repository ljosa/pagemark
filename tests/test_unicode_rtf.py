"""Test Unicode character handling in RTF clipboard."""

import unittest
from pagemark.rtf_parser import parse_rtf
from pagemark.clipboard import ClipboardManager


class TestUnicodeRTF(unittest.TestCase):
    """Test Unicode character handling in RTF format."""
    
    def test_parse_hex_escape_o_with_stroke(self):
        """Test parsing ø (U+00F8) from TextEdit hex escape format."""
        # This is what TextEdit generates for ø
        rtf = r'''{\rtf1\ansi\ansicpg1252\cocoartf2639
\cocoatextscaling0\cocoaplatform0{\fonttbl\f0\fswiss\fcharset0 Helvetica;}
{\colortbl;\red255\green255\blue255;}
{\*\expandedcolortbl;;}
\pard\tx560\tx1120\tx1680\tx2240\tx2800\tx3360\tx3920\tx4480\tx5040\tx5600\tx6160\tx6720\pardirnatural\partightenfactor0

\f0\fs24 \cf0 Test \'f8 character}'''
        
        text, styles = parse_rtf(rtf)
        self.assertEqual(text, 'Test ø character')
    
    def test_generate_rtf_with_o_with_stroke(self):
        """Test generating RTF with ø character."""
        text = "Test ø character"
        styles = [[0] * len(text)]
        
        rtf = ClipboardManager._generate_rtf(text, styles)
        
        # Should generate \u248? format
        self.assertIn(r'\u248?', rtf)
        
        # Should round-trip correctly
        parsed_text, _ = parse_rtf(rtf)
        self.assertEqual(parsed_text, text)
    
    def test_parse_various_hex_escapes(self):
        """Test parsing various Unicode characters via hex escapes."""
        test_cases = [
            (r"\'e9", "é"),  # Latin Small Letter E with Acute (U+00E9)
            (r"\'e5", "å"),  # Latin Small Letter A with Ring Above (U+00E5)
            (r"\'f1", "ñ"),  # Latin Small Letter N with Tilde (U+00F1)
            (r"\'fc", "ü"),  # Latin Small Letter U with Diaeresis (U+00FC)
            (r"\'e6", "æ"),  # Latin Small Letter AE (U+00E6)
        ]
        
        for escape, expected in test_cases:
            rtf = r'{\rtf1\ansi\deff0 Test ' + escape + '}'
            text, _ = parse_rtf(rtf)
            self.assertEqual(text, f'Test {expected}', 
                           f"Failed to parse {escape} as {expected}")
    
    def test_mixed_unicode_and_formatting(self):
        """Test Unicode characters with bold/underline formatting."""
        rtf = r'''{\rtf1\ansi\deff0 Normal {\b Bold \'f8} {\ul Underline \'e9}}'''
        
        text, styles = parse_rtf(rtf)
        self.assertEqual(text, 'Normal Bold ø Underline é')
        
        # Check that formatting is preserved
        if styles:
            # Find position of ø
            o_pos = text.index('ø')
            self.assertEqual(styles[0][o_pos], 1, "ø should be bold")
            
            # Find position of é
            e_pos = text.index('é')
            self.assertEqual(styles[0][e_pos], 2, "é should be underlined")
    
    def test_invalid_hex_escape(self):
        """Test handling of invalid hex escape sequences."""
        rtf = r'''{\rtf1\ansi\deff0 Test \'zz invalid}'''
        
        text, _ = parse_rtf(rtf)
        # Invalid hex escape should be preserved as literal text
        self.assertEqual(text, 'Test zz invalid')
    
    def test_clipboard_round_trip_with_unicode(self):
        """Test full clipboard round-trip with Unicode characters."""
        text = "Café naïve résumé Zürich ñoño"
        styles = [[0] * len(text)]
        
        # Generate RTF
        rtf = ClipboardManager._generate_rtf(text, styles)
        
        # Parse it back
        parsed_text, parsed_styles = parse_rtf(rtf)
        
        self.assertEqual(parsed_text, text)
    
    def test_unicode_at_rtf_boundaries(self):
        """Test Unicode characters at RTF group boundaries."""
        rtf = r'''{\rtf1\ansi\deff0 {\'f8}\'e9}'''
        
        text, _ = parse_rtf(rtf)
        self.assertEqual(text, 'øé')


if __name__ == '__main__':
    unittest.main()
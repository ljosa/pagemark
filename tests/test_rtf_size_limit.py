"""Test RTF size limit protection."""

import unittest
from unittest.mock import Mock, patch
from pagemark.rtf_parser import parse_rtf, MAX_RTF_SIZE
from pagemark.clipboard import ClipboardManager


class TestRTFSizeLimit(unittest.TestCase):
    """Test RTF size limit to prevent DoS attacks."""
    
    def test_parse_rtf_within_limit(self):
        """Test parsing RTF within size limit."""
        rtf = r'{\rtf1\ansi\deff0 Normal {\b Bold} Text}'
        text, styles = parse_rtf(rtf)
        self.assertEqual(text, 'Normal Bold Text')
        self.assertIsNotNone(styles)
    
    def test_parse_rtf_exceeds_limit(self):
        """Test parsing RTF that exceeds size limit."""
        # Create RTF larger than 10MB
        huge_rtf = r'{\rtf1\ansi\deff0 ' + 'A' * (MAX_RTF_SIZE + 1) + '}'
        text, styles = parse_rtf(huge_rtf)
        self.assertEqual(text, "")  # Should return empty string
        self.assertIsNone(styles)
    
    def test_parse_rtf_at_limit(self):
        """Test parsing RTF exactly at size limit."""
        # Create RTF exactly at 10MB
        prefix = r'{\rtf1\ansi\deff0 '
        suffix = '}'
        content_size = MAX_RTF_SIZE - len(prefix) - len(suffix)
        rtf_content = 'A' * content_size
        rtf = prefix + rtf_content + suffix
        self.assertEqual(len(rtf), MAX_RTF_SIZE)
        text, styles = parse_rtf(rtf)
        # Should parse successfully
        self.assertIsNotNone(text)
    
    @patch('pagemark.clipboard.sys.platform', 'darwin')
    def test_clipboard_paste_size_limit(self):
        """Test clipboard paste with size limit."""
        # Mock AppKit module
        mock_appkit = Mock()
        mock_pb_class = Mock()
        mock_pb = Mock()
        
        mock_appkit.NSPasteboard = mock_pb_class
        mock_appkit.NSPasteboardTypeRTF = 'rtf'
        mock_appkit.NSPasteboardTypeString = 'string'
        mock_pb_class.generalPasteboard.return_value = mock_pb
        
        # Create mock RTF data larger than limit
        huge_rtf = r'{\rtf1\ansi\deff0 ' + 'A' * (MAX_RTF_SIZE + 1) + '}'
        mock_rtf_data = Mock()
        mock_rtf_data.__len__ = Mock(return_value=MAX_RTF_SIZE + 1)
        
        mock_pb.dataForType_.return_value = mock_rtf_data
        mock_pb.stringForType_.return_value = "Fallback plain text"
        
        # Patch the import
        with patch.dict('sys.modules', {'AppKit': mock_appkit}):
            text, styles = ClipboardManager.paste_text()
            
            # Should fall back to plain text
            self.assertEqual(text, "Fallback plain text")
            self.assertIsNone(styles)
    
    def test_size_limit_value(self):
        """Test that size limit is reasonable (10MB)."""
        self.assertEqual(MAX_RTF_SIZE, 10 * 1024 * 1024)
        self.assertEqual(MAX_RTF_SIZE, 10485760)  # 10MB in bytes


if __name__ == '__main__':
    unittest.main()
"""System clipboard integration with RTF format support."""

import sys
from typing import Optional, List, Tuple
from .rtf_parser import parse_rtf, MAX_RTF_SIZE


class ClipboardManager:
    """Manages system clipboard operations with RTF format support.
    
    On macOS, uses native APIs via PyObjC for rich text interchange.
    Supports bold and underline formatting.
    
    Internal format uses style masks:
    - 0: Plain text
    - 1: Bold
    - 2: Underline  
    - 3: Bold + Underline
    """
    
    @staticmethod
    def copy_text(text: str, styles: Optional[List[List[int]]] = None) -> None:
        """Copy text to system clipboard.
        
        Args:
            text: Plain text to copy (may contain newlines for multiple paragraphs)
            styles: Optional list of style masks for each paragraph
        """
        if sys.platform == 'darwin':
            ClipboardManager._copy_macos(text, styles)
        else:
            ClipboardManager._copy_linux(text, styles)
    
    @staticmethod
    def paste_text() -> Tuple[str, Optional[List[List[int]]]]:
        """Paste text from system clipboard.
        
        Returns:
            Tuple of (text, styles) where styles is None if no formatting detected
        """
        if sys.platform == 'darwin':
            return ClipboardManager._paste_macos()
        else:
            return ClipboardManager._paste_linux()
    
    @staticmethod
    def _copy_macos(text: str, styles: Optional[List[List[int]]]) -> None:
        """Copy to macOS clipboard with RTF format if styles present."""
        try:
            from AppKit import NSPasteboard, NSPasteboardTypeRTF, NSPasteboardTypeString
            import Foundation
            
            # Get the general pasteboard
            pb = NSPasteboard.generalPasteboard()
            pb.clearContents()
            
            if not styles or not any(any(s != 0 for s in para) for para in styles):
                # Plain text only
                pb.setString_forType_(text, NSPasteboardTypeString)
            else:
                # Generate RTF and set both formats
                rtf = ClipboardManager._generate_rtf(text, styles)
                
                # Convert RTF string to NSData
                rtf_data = Foundation.NSData.dataWithBytes_length_(
                    rtf.encode('utf-8'), len(rtf.encode('utf-8'))
                )
                
                # Set both RTF and plain text
                pb.setData_forType_(rtf_data, NSPasteboardTypeRTF)
                pb.setString_forType_(text, NSPasteboardTypeString)
                
        except ImportError:
            # Fallback to pyperclip for plain text only
            import pyperclip
            pyperclip.copy(text)
    
    @staticmethod
    def _paste_macos() -> Tuple[str, Optional[List[List[int]]]]:
        """Paste from macOS clipboard, trying RTF format first."""
        try:
            from AppKit import NSPasteboard, NSPasteboardTypeRTF, NSPasteboardTypeString
            
            pb = NSPasteboard.generalPasteboard()
            
            # Try to get RTF data first
            rtf_data = pb.dataForType_(NSPasteboardTypeRTF)
            if rtf_data:
                # Check size before processing
                if len(rtf_data) > MAX_RTF_SIZE:
                    # RTF too large, fall back to plain text
                    pass
                else:
                    # Convert NSData to string
                    rtf_bytes = bytes(rtf_data)
                    rtf_text = rtf_bytes.decode('utf-8', errors='ignore')
                    
                    if rtf_text.startswith('{\\rtf'):
                        # Parse RTF to extract text and styles
                        text, styles = parse_rtf(rtf_text)
                        if text:
                            return text, styles
            
            # Fall back to plain text
            plain_text = pb.stringForType_(NSPasteboardTypeString)
            if plain_text:
                return str(plain_text), None
            
            return "", None
            
        except ImportError:
            # Fallback to pyperclip
            import pyperclip
            content = pyperclip.paste()
            return content, None
    
    @staticmethod
    def _copy_linux(text: str, styles: Optional[List[List[int]]]) -> None:
        """Copy to Linux clipboard (plain text only for now)."""
        import pyperclip
        pyperclip.copy(text)
    
    @staticmethod  
    def _paste_linux() -> Tuple[str, Optional[List[List[int]]]]:
        """Paste from Linux clipboard."""
        import pyperclip
        content = pyperclip.paste()
        return content, None
    
    @staticmethod
    def _generate_rtf(text: str, styles: List[List[int]]) -> str:
        """Generate RTF format from text and styles.
        
        Args:
            text: Plain text with newlines separating paragraphs
            styles: List of style masks for each paragraph
            
        Returns:
            RTF formatted string
        """
        # RTF header - using Helvetica which is standard on macOS
        rtf = r'{\rtf1\ansi\ansicpg1252\cocoartf2639' + '\n'
        rtf += r'\cocoatextscaling0\cocoaplatform0{\fonttbl\f0\fswiss\fcharset0 Helvetica;}' + '\n'
        rtf += r'{\colortbl;\red255\green255\blue255;}' + '\n'
        rtf += r'{\*\expandedcolortbl;;}' + '\n'
        rtf += r'\pard\tx560\tx1120\tx1680\tx2240\tx2800\tx3360\tx3920\tx4480\tx5040\tx5600\tx6160\tx6720\pardirnatural\partightenfactor0' + '\n\n'
        rtf += r'\f0\fs24 \cf0 '
        
        paragraphs = text.split('\n')
        
        for para_idx, para in enumerate(paragraphs):
            if para_idx > 0:
                rtf += r'\par' + '\n'  # Paragraph break
                
            if para_idx >= len(styles) or not styles[para_idx]:
                # No styling for this paragraph
                rtf += ClipboardManager._escape_rtf(para)
                continue
            
            style_mask = styles[para_idx]
            i = 0
            
            while i < len(para):
                if i >= len(style_mask):
                    # No style info for rest of paragraph
                    rtf += ClipboardManager._escape_rtf(para[i:])
                    break
                
                # Find run of same style
                current_style = style_mask[i]
                run_end = i + 1
                while run_end < len(para) and run_end < len(style_mask) and style_mask[run_end] == current_style:
                    run_end += 1
                
                run_text = ClipboardManager._escape_rtf(para[i:run_end])
                
                if current_style == 0:
                    rtf += run_text
                elif current_style == 1:  # Bold
                    rtf += r'{\b ' + run_text + '}'
                elif current_style == 2:  # Underline
                    rtf += r'{\ul ' + run_text + '}'
                elif current_style == 3:  # Bold + Underline
                    rtf += r'{\b\ul ' + run_text + '}'
                else:
                    rtf += run_text
                
                i = run_end
        
        rtf += '}'
        return rtf
    
    @staticmethod
    def _escape_rtf(text: str) -> str:
        """Escape special characters for RTF."""
        text = text.replace('\\', '\\\\')
        text = text.replace('{', '\\{')
        text = text.replace('}', '\\}')
        # Handle Unicode characters
        result = []
        for char in text:
            if ord(char) > 127:
                # Use Unicode escape
                result.append(f'\\u{ord(char)}?')
            else:
                result.append(char)
        return ''.join(result)
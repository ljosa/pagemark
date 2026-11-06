"""System clipboard integration with RTF format support."""

import sys
from typing import Optional, List, Tuple
from pagemark_core.rtf import generate_rtf, escape_rtf
from pagemark_core.rtf_parser import parse_rtf, MAX_RTF_SIZE


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

    _generate_rtf = staticmethod(generate_rtf)
    _escape_rtf = staticmethod(escape_rtf)

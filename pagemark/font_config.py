"""Font configuration and constants for the pagemark editor.

This module defines font configurations for different typewriter fonts,
including their pitch, dimensions, and PDF generation settings.
"""

from dataclasses import dataclass
from typing import Dict, Optional


# Physical page constants (US Letter)
LETTER_WIDTH_INCHES = 8.5
LETTER_HEIGHT_INCHES = 11.0
POINTS_PER_INCH = 72

# Line spacing
LINES_PER_INCH = 6  # Standard typewriter line spacing
LINE_HEIGHT_POINTS = POINTS_PER_INCH / LINES_PER_INCH  # 12 points

# Margins in inches
STANDARD_MARGIN_INCHES = 1.0  # Standard 1" margins for 10-pitch
NARROW_MARGIN_INCHES = 1.25  # 1.25" margins for 12-pitch


@dataclass(frozen=True)
class FontConfig:
    """Configuration for a typewriter font.
    
    Attributes:
        name: Display name of the font
        pdf_name: Name used in PDF generation
        pdf_bold_name: Bold variant name for PDF
        pitch: Characters per inch (10 for pica, 12 for elite)
        point_size: Font size in points
        text_width: Number of characters in the text area
        left_margin_chars: Left margin in characters
        right_margin_chars: Right margin in characters
        full_page_width: Total page width in characters
        is_embedded: Whether font is embedded in PDF (vs referenced)
    """
    name: str
    pdf_name: str
    pdf_bold_name: str
    pitch: int
    point_size: int
    text_width: int
    left_margin_chars: int
    right_margin_chars: int
    full_page_width: int
    is_embedded: bool
    
    @property
    def line_height(self) -> int:
        """Line height in points (always 12 for 6 lpi)."""
        return LINE_HEIGHT_POINTS
    
    @classmethod
    def create_10_pitch(cls, name: str, pdf_name: str, pdf_bold_name: str, 
                        is_embedded: bool = False) -> 'FontConfig':
        """Create a 10-pitch (pica) font configuration.
        
        10-pitch means 10 characters per inch:
        - 8.5" width = 85 characters total
        - 1" margins each side = 10 chars each
        - Text area = 65 characters
        """
        pitch = 10
        full_width = int(LETTER_WIDTH_INCHES * pitch)  # 85
        margin_chars = int(STANDARD_MARGIN_INCHES * pitch)  # 10
        text_width = full_width - (2 * margin_chars)  # 65
        
        return cls(
            name=name,
            pdf_name=pdf_name,
            pdf_bold_name=pdf_bold_name,
            pitch=pitch,
            point_size=12,  # 10-pitch fonts use 12pt
            text_width=text_width,
            left_margin_chars=margin_chars,
            right_margin_chars=margin_chars,
            full_page_width=full_width,
            is_embedded=is_embedded
        )
    
    @classmethod
    def create_12_pitch(cls, name: str, pdf_name: str, pdf_bold_name: str,
                        is_embedded: bool = True) -> 'FontConfig':
        """Create a 12-pitch (elite) font configuration.
        
        12-pitch means 12 characters per inch:
        - 8.5" width = 102 characters total
        - 1.25" margins each side = 15 chars each
        - Text area = 72 characters
        """
        pitch = 12
        full_width = int(LETTER_WIDTH_INCHES * pitch)  # 102
        margin_chars = int(NARROW_MARGIN_INCHES * pitch)  # 15
        text_width = full_width - (2 * margin_chars)  # 72
        
        return cls(
            name=name,
            pdf_name=pdf_name,
            pdf_bold_name=pdf_bold_name,
            pitch=pitch,
            point_size=10,  # 12-pitch fonts use 10pt
            text_width=text_width,
            left_margin_chars=margin_chars,
            right_margin_chars=margin_chars,
            full_page_width=full_width,
            is_embedded=is_embedded
        )


# Pre-defined font configurations
FONT_CONFIGS: Dict[str, FontConfig] = {
    "Courier": FontConfig.create_10_pitch(
        name="Courier",
        pdf_name="Courier",
        pdf_bold_name="Courier-Bold",
        is_embedded=False  # Built-in PDF font, referenced not embedded
    ),
    "Prestige Elite Std": FontConfig.create_12_pitch(
        name="Prestige Elite Std",
        pdf_name="PrestigeEliteStd",
        pdf_bold_name="PrestigeEliteStd-Bold",
        is_embedded=True  # Custom font, must be embedded
    )
}


def get_font_config(font_name: str) -> Optional[FontConfig]:
    """Get font configuration by name.
    
    Args:
        font_name: Name of the font
        
    Returns:
        FontConfig if found, None otherwise
    """
    return FONT_CONFIGS.get(font_name)
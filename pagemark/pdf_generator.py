"""Terminal PDF adapter with the existing system-font discovery policy."""
from pagemark_core.pdf_generator import FontLoadError  # noqa: F401
from pagemark_core.pdf_generator import PDFGenerator as CorePDFGenerator
from pagemark_platform.fonts import prestige_font_paths


class PDFGenerator(CorePDFGenerator):
    def __init__(self, font_name="Courier", *, font_paths=None):
        if font_name == "Prestige Elite Std" and font_paths is None:
            font_paths = prestige_font_paths()
        super().__init__(font_name, font_paths=font_paths)

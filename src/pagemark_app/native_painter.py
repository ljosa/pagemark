"""Bounded, view-owned Cocoa resources for painting already-laid-out text."""
from collections import OrderedDict

import AppKit as A
import Foundation as F

from .rendering import text_runs
from .screen_fonts import cell_metrics, draft_font


class TextPainter:
    def __init__(self, capacity=256):
        self.capacity = capacity
        self._lines = OrderedDict()
        self._configuration = None

    def configure(self, zoom, font_spec=None):
        configuration = (zoom, font_spec)
        if configuration == self._configuration:
            return
        self._configuration = configuration
        self._lines.clear()
        if font_spec is None:
            fonts = (A.NSFont.fontWithName_size_("Courier", 12 * zoom),
                     A.NSFont.fontWithName_size_("Courier-Bold", 12 * zoom))
        else:
            normal = draft_font(font_spec, zoom)
            bold = A.NSFontManager.sharedFontManager().convertFont_toHaveTrait_(normal, A.NSBoldFontMask)
            fonts = (normal, bold)
        self.metrics = cell_metrics(fonts)
        # Some families change advance for bold; those need explicit cell placement.
        self.uniform_advance = abs(cell_metrics((fonts[1],)).width - self.metrics.width) < 0.001
        manager = A.NSLayoutManager.alloc().init()
        self.baselines = tuple(manager.defaultBaselineOffsetForFont_(font) for font in fonts)
        self.fonts = fonts
        synthetic_bold = font_spec is not None and fonts[0].fontName() == fonts[1].fontName()
        self.attributes = {}
        for flag in range(4):
            for selected in (False, True):
                self.attributes[flag, selected] = {
                    A.NSFontAttributeName: fonts[bool(flag & 1)],
                    A.NSForegroundColorAttributeName: (A.NSColor.selectedTextColor()
                                                      if selected else A.NSColor.textColor()),
                    A.NSUnderlineStyleAttributeName: 1 if flag & 2 else 0,
                    # Preserve terminal cell advances when batching ASCII.
                    A.NSLigatureAttributeName: 0,
                    A.NSKernAttributeName: 0,
                }
                if synthetic_bold and flag & 1:
                    # Families such as Monaco have no bold face. Fill and
                    # stroke their glyphs so the document's bold stays visible.
                    self.attributes[flag, selected][A.NSStrokeWidthAttributeName] = -3

    def draw(self, row, styles, start, end, focused, x, y, geometry, font_spec=None):
        self.configure(geometry.zoom, font_spec)
        # The current Courier renderer has a 7.2-point advance. Preserve
        # explicit cell positioning if a different grid is requested.
        batch_ascii = (self.uniform_advance if font_spec else geometry.columns == 65)
        runs = text_runs(row, styles, start, end, batch_ascii=batch_ascii)
        key = (runs, bool(focused))
        prepared = self._lines.get(key)
        if prepared is None:
            prepared = tuple((F.NSString.stringWithString_(run.text), run.column,
                              self.attributes[run.style, run.selected and bool(focused)],
                              self.baselines[bool(run.style & 1)]) for run in runs)
            self._lines[key] = prepared
            if len(self._lines) > self.capacity:
                self._lines.popitem(last=False)
        else:
            self._lines.move_to_end(key)
        for string, column, attributes, baseline in prepared:
            string.drawAtPoint_withAttributes_(
                (x + column * geometry.cell_width, y + geometry.baseline - baseline), attributes)

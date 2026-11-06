"""Resolve installed monospaced fonts for Draft without changing print fonts."""
import AppKit as A
import Foundation as F

from .geometry import CellMetrics


def draft_font(spec, zoom=1):
    for name in (spec.name, "Menlo-Regular", "Courier"):
        font = A.NSFont.fontWithName_size_(name, spec.size * zoom)
        if font is not None and font.isFixedPitch():
            return font
    return A.NSFont.monospacedSystemFontOfSize_weight_(spec.size * zoom, A.NSFontWeightRegular)


def draft_font_choices():
    manager = A.NSFontManager.sharedFontManager()
    choices = {}
    for family in manager.availableFontFamilies():
        font = manager.fontWithFamily_traits_weight_size_(family, 0, 5, 14)
        if font is not None and font.isFixedPitch():
            choices[str(family)] = str(font.fontName())
    # Some system families are resolvable but absent from availableFontFamilies.
    for name in ("JetBrainsMonoNL-Regular", "Menlo-Regular", "Courier"):
        font = A.NSFont.fontWithName_size_(name, 14)
        if font is not None and font.isFixedPitch():
            choices[str(font.familyName())] = str(font.fontName())
    return sorted(choices.items(), key=lambda choice: choice[0].casefold())


def cell_metrics(fonts):
    manager = A.NSLayoutManager.alloc().init()
    width = F.NSString.stringWithString_("M").sizeWithAttributes_({
        A.NSFontAttributeName: fonts[0], A.NSLigatureAttributeName: 0,
        A.NSKernAttributeName: 0}).width
    return CellMetrics(width, max(manager.defaultLineHeightForFont_(f) for f in fonts),
                       max(manager.defaultBaselineOffsetForFont_(f) for f in fonts))

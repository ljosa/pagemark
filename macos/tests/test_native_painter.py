"""Compare batched Cocoa output with the original per-cluster grid painter."""
from math import ceil

import pytest

pytest.importorskip("pagemark_core")
A = pytest.importorskip("AppKit")
F = pytest.importorskip("Foundation")
objc = pytest.importorskip("objc")

from pagemark_core.layout import layout_paragraph  # noqa: E402
from pagemark_core.text_layout import display_spans  # noqa: E402
from pagemark_app.geometry import EditorGeometry  # noqa: E402
from pagemark_app.display_preferences import DraftFont  # noqa: E402
from pagemark_app.native_painter import TextPainter  # noqa: E402


def bitmap_draw(operation):
    bitmap = A.NSBitmapImageRep.alloc().initWithBitmapDataPlanes_pixelsWide_pixelsHigh_bitsPerSample_samplesPerPixel_hasAlpha_isPlanar_colorSpaceName_bytesPerRow_bitsPerPixel_(
        None, 1000, 80, 8, 4, True, False, A.NSDeviceRGBColorSpace, 0, 0)
    context = A.NSGraphicsContext.graphicsContextWithBitmapImageRep_(bitmap)
    A.NSGraphicsContext.saveGraphicsState()
    A.NSGraphicsContext.setCurrentContext_(context)
    try:
        A.NSColor.whiteColor().set()
        A.NSRectFill(F.NSMakeRect(0, 0, 1000, 80))
        operation()
        data = bytes(bitmap.bitmapData())
        stride = bitmap.bytesPerRow()
        return b"".join(data[y * stride:y * stride + 4000] for y in range(80))
    finally:
        A.NSGraphicsContext.restoreGraphicsState()


def reference_draw(row, flags, start, end, focused, geometry, fonts=None):
    fonts = fonts or (A.NSFont.fontWithName_size_("Courier", 12 * geometry.zoom),
                      A.NSFont.fontWithName_size_("Courier-Bold", 12 * geometry.zoom))
    manager = A.NSLayoutManager.alloc().init()
    baselines = [manager.defaultBaselineOffsetForFont_(font) for font in fonts]
    column = 0
    for begin, stop, cells in display_spans(row.text):
        source = row.sources[begin]
        flag = flags[source] if source is not None else 0
        selected = source is not None and start <= source < end
        attributes = {
            A.NSFontAttributeName: fonts[bool(flag & 1)],
            A.NSForegroundColorAttributeName: (A.NSColor.selectedTextColor()
                                              if selected and focused else A.NSColor.textColor()),
            A.NSUnderlineStyleAttributeName: 1 if flag & 2 else 0,
        }
        F.NSString.stringWithString_(row.text[begin:stop]).drawAtPoint_withAttributes_(
            (10 + column * geometry.cell_width,
             20 + geometry.baseline - baselines[bool(flag & 1)]), attributes)
        column += cells


def assert_same_pixels(actual, expected, flags, geometry):
    if actual == expected:
        return
    # At fractional cell advances, drawing an underline as a single run
    # changes antialiasing at a few joins between cells. Text positions and
    # the underline bounds stay fixed. Integer advances must match exactly.
    assert geometry.cell_width % 1 and any(flag & 2 for flag in flags)
    pixels = {index // 4 for index, (a, b) in enumerate(zip(actual, expected)) if a != b}
    assert len(pixels) <= 2 * ceil(geometry.zoom) * sum(bool(flag & 2) for flag in flags)
    for pixel in pixels:
        column = (pixel % 1000 - 10) / geometry.cell_width
        assert abs(column - round(column)) * geometry.cell_width <= 1
    rows = {pixel // 1000 for pixel in pixels}
    assert max(rows) - min(rows) <= 2 * ceil(geometry.zoom)


@pytest.mark.parametrize("zoom,columns", [(1, 65), (1.25, 65), (2, 65), (1.25, 72)])
@pytest.mark.parametrize("text,flags,selection,focused", [
    ("office ffi fi fl  spaced  --", None, (0, 0), False),
    ("bold under both plain", [1] * 5 + [2] * 6 + [3] * 5 + [0] * 5, (3, 14), True),
    ("abc é é 字 😀 end", None, (0, 12), False),
])
def test_native_runs_match_original_painting(zoom, columns, text, flags, selection, focused):
    with objc.autorelease_pool():
        row = layout_paragraph(text, columns).rows[0]
        flags = flags or [0] * len(text)
        geometry = EditorGeometry(1, 840, zoom=zoom, columns=columns)
        painter = TextPainter()
        expected = bitmap_draw(lambda: reference_draw(row, flags, *selection, focused, geometry))
        actual = bitmap_draw(lambda: painter.draw(row, flags, *selection, focused, 10, 20, geometry))
        assert_same_pixels(actual, expected, flags, geometry)
        # A cached draw and a selection change must not retain stale attributes.
        cached = bitmap_draw(lambda: painter.draw(row, flags, *selection, focused, 10, 20, geometry))
        assert cached == actual
        selection = (0, len(text))
        changed = bitmap_draw(lambda: painter.draw(row, flags, *selection, True, 10, 20, geometry))
        expected = bitmap_draw(lambda: reference_draw(row, flags, *selection, True, geometry))
        assert_same_pixels(changed, expected, flags, geometry)


def test_native_line_cache_is_bounded_and_font_changes_invalidate_it():
    painter = TextPainter(capacity=3)
    geometry = EditorGeometry(1, 840)
    for index in range(8):
        text = f"line {index}"
        row = layout_paragraph(text, 65).rows[0]
        bitmap_draw(lambda: painter.draw(row, [0] * len(text), 0, 0, False, 10, 20, geometry))
    assert len(painter._lines) == 3
    painter.configure(2)
    assert not painter._lines
    assert painter.fonts[0].pointSize() == 24


@pytest.mark.parametrize("text,styles", [
    ("office -> != ffi", [0] * 16),
    ("bold under both plain", [1] * 5 + [2] * 6 + [3] * 5 + [0] * 5),
    ("abc é é 字 😀 end", [0] * 16),
])
def test_draft_font_runs_match_cell_positions_and_caches_follow_font_changes(text, styles):
    row = layout_paragraph(text, 65).rows[0]
    painter = TextPainter()
    for spec in (DraftFont("Menlo-Regular", 12), DraftFont("Courier", 18)):
        painter.configure(1.25, spec)
        assert not painter._lines
        geometry = EditorGeometry(1, 840, draft_metrics=painter.metrics)
        actual = bitmap_draw(lambda: painter.draw(row, styles, 3, 12, True, 10, 20, geometry, spec))
        expected = bitmap_draw(lambda: reference_draw(row, styles, 3, 12, True, geometry, painter.fonts))
        assert_same_pixels(actual, expected, styles, geometry)


def test_cached_text_colors_follow_appearance_changes():
    painter = TextPainter()
    row = layout_paragraph("Screen colors", 65).rows[0]
    geometry = EditorGeometry(1, 840)
    results = []
    for name in (A.NSAppearanceNameAqua, A.NSAppearanceNameDarkAqua, A.NSAppearanceNameAqua):
        appearance = A.NSAppearance.appearanceNamed_(name)
        appearance.performAsCurrentDrawingAppearance_(lambda: results.append(bitmap_draw(
            lambda: painter.draw(row, [0] * 13, 0, 0, False, 10, 20, geometry))))
    assert len(painter._lines) == 1
    assert results[0] != results[1]
    assert results[0] == results[2]


def test_draft_family_without_bold_face_still_displays_bold():
    spec = DraftFont("Monaco", 14)
    painter = TextPainter()
    painter.configure(1.25, spec)
    assert painter.fonts[0].fontName() == painter.fonts[1].fontName() == "Monaco"
    geometry = EditorGeometry(1, 840, draft_metrics=painter.metrics)
    row = layout_paragraph("Bold", 65).rows[0]
    normal = bitmap_draw(lambda: painter.draw(row, [0] * 4, 0, 0, False, 10, 20, geometry, spec))
    bold = bitmap_draw(lambda: painter.draw(row, [1] * 4, 0, 0, False, 10, 20, geometry, spec))
    assert normal != bold

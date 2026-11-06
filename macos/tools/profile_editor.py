#!/usr/bin/env python3
"""Measure synthetic edit, layout, navigation and offscreen drawing costs.

Run with src and the repository root on PYTHONPATH, using the build
interpreter. This never launches NSApplication, opens a user document, writes
recovery data or submits a print job. It does not measure key-to-screen latency.
"""
import argparse
import json
from pathlib import Path
import statistics
import time

import AppKit as A
import Foundation as F
import objc

from pagemark_core.layout import layout_paragraph
from pagemark_app.codec import StyledText
from pagemark_app.display_preferences import ViewMode
from pagemark_app.native_editor import PagemarkEditorView, composed_boundaries
from pagemark_app.session import EditorSession


def median_ms(operation, samples):
    durations = []
    for _ in range(samples):
        with objc.autorelease_pool():
            start = time.perf_counter()
            operation()
            durations.append((time.perf_counter() - start) * 1000)
    return round(statistics.median(durations), 3)


def measure(paragraphs, samples):
    text = "\n".join(f"Paragraph {index:05d}. " + "The quick brown fox jumps over the lazy dog. " * 6
                     for index in range(paragraphs))
    layout_paragraph.cache_clear()
    session = EditorSession(StyledText(text, (0,) * len(text)), boundaries=composed_boundaries)
    session.select(len(text), len(text))
    _ = session.layout
    misses = []

    def edit():
        before = layout_paragraph.cache_info().misses
        session.insert("x")
        _ = session.layout
        misses.append(layout_paragraph.cache_info().misses - before)

    def navigate():
        session.move("left")
        session.move("right")

    result = {"paragraphs": paragraphs, "characters": len(text),
              "insert_and_layout_ms": median_ms(edit, samples),
              "paragraph_layout_misses_per_edit": misses}
    navigate()
    result["left_right_pair_ms"] = median_ms(navigate, samples)
    view = PagemarkEditorView.alloc().initWithFrame_(F.NSMakeRect(0, 0, 840, 692))
    view.session = session
    bitmap = A.NSBitmapImageRep.alloc().initWithBitmapDataPlanes_pixelsWide_pixelsHigh_bitsPerSample_samplesPerPixel_hasAlpha_isPlanar_colorSpaceName_bytesPerRow_bitsPerPixel_(
        None, 840, 692, 8, 4, True, False, A.NSDeviceRGBColorSpace, 0, 0)
    A.NSGraphicsContext.saveGraphicsState()
    A.NSGraphicsContext.setCurrentContext_(A.NSGraphicsContext.graphicsContextWithBitmapImageRep_(bitmap))
    try:
        for pages in (False, True):
            view.view_mode = ViewMode.PAGES if pages else ViewMode.CONTINUOUS
            view.refresh(reveal=False)
            dirty = F.NSMakeRect(0, 0, 840, 692)
            view.drawRect_(dirty)
            result["pages_draw_ms" if pages else "continuous_draw_ms"] = median_ms(
                lambda: view.drawRect_(dirty), samples)
    finally:
        A.NSGraphicsContext.restoreGraphicsState()
        view.teardown()
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--paragraphs", type=int, nargs="+", default=[25, 100, 260, 500])
    parser.add_argument("--samples", type=int, default=7)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    if args.samples < 1 or any(count < 1 for count in args.paragraphs):
        parser.error("Samples and paragraph counts must be positive")
    report = {"measurement": "Synthetic CPU/offscreen timings; not key-to-screen latency",
              "samples": args.samples, "cases": []}
    for count in args.paragraphs:
        with objc.autorelease_pool():
            report["cases"].append(measure(count, args.samples))
    output = json.dumps(report, indent=2) + "\n"
    if args.output:
        args.output.write_text(output)
    print(output, end="")


if __name__ == "__main__":
    main()

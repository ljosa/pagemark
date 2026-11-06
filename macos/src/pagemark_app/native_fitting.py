"""Explicit fit actions over the existing editor geometry and native window."""
from math import ceil

import AppKit as A
import Foundation as F

from .fitting import fit_width_zoom, fitted_window_frame


def fit_width(editor):
    scroll = editor.enclosingScrollView()
    viewport_width = editor.geometry.viewport_width
    # Scrollbar visibility and measured Draft advances can change after a fit.
    # Resolve those small changes without installing a persistent auto-fit mode.
    for _ in range(3):
        if scroll is not None:
            scroll.tile()
            viewport_width = scroll.contentSize().width
        level = fit_width_zoom(editor.geometry, viewport_width)
        if abs(level - editor.zoom) < 1e-7:
            break
        editor.set_zoom(level, persist=False)
        if scroll is not None:
            scroll.tile()
            viewport_width = scroll.contentSize().width
        if 0 <= viewport_width - editor.geometry.natural_width <= 2:
            break
    editor.remember_zoom()


def can_resize_window(window):
    return bool(window is not None and window.styleMask() & A.NSWindowStyleMaskResizable
                and not window.styleMask() & A.NSWindowStyleMaskFullScreen)


def rect_values(rect):
    return rect.origin.x, rect.origin.y, rect.size.width, rect.size.height


def resize_window_to_fit(editor):
    window, scroll = editor.window(), editor.enclosingScrollView()
    if not can_resize_window(window) or scroll is None:
        return
    screen = window.screen() or A.NSScreen.mainScreen()
    if screen is None:
        return
    original = rect_values(window.frame())
    for _ in range(3):
        scroll.tile()
        editor.refresh(reveal=False)
        frame = rect_values(window.frame())
        # Include borders and a non-overlay vertical scroller in the frame width.
        chrome = frame[2] - scroll.contentSize().width
        desired = ceil(editor.geometry.natural_width + chrome)
        target = fitted_window_frame(original, rect_values(screen.visibleFrame()), desired,
                                     window.minSize().width, window.maxSize().width)
        if target == frame:
            break
        window.setFrame_display_(F.NSMakeRect(*target), True)
    scroll.tile()
    editor.refresh(reveal=False)

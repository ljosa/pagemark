"""Signed-app zoom checks using native keys, clip views and synthetic pinch deltas."""
import AppKit as A
import Foundation as F
import objc

from .codec import StyledText
from .display_preferences import ViewMode
from .native_fitting import fit_width, rect_values, resize_window_to_fit
from .session import Snapshot
from .zoom import MAX_ZOOM, ZoomAnchor


class PagemarkProbeMagnifyEvent(F.NSObject):
    @objc.signature(b"d@:")
    def magnification(self):
        return self.delta

    @objc.signature(F.NSPoint.__typestr__ + b"@:")
    def locationInWindow(self):
        return self.point

    @objc.signature(b"Q@:")
    def phase(self):
        return A.NSEventPhaseEnded


def check_zoom(editor):
    before = editor.session.snapshot()
    mode, levels, preferences = editor.view_mode, dict(editor._zoom_levels), editor.preferences
    editor.preferences = None  # The probe must not write the user's saved zoom.
    try:
        text = "\n".join("Zoom probe line " + str(i) for i in range(150))
        editor.session.restore(Snapshot(StyledText(text, (0,) * len(text)), 0, None, 0))
        snapshot = editor.session.snapshot()
        layout = editor.session.layout
        scroll = editor.enclosingScrollView()
        clip = scroll.contentView()

        def key(character, modifiers=A.NSEventModifierFlagCommand):
            event = A.NSEvent.keyEventWithType_location_modifierFlags_timestamp_windowNumber_context_characters_charactersIgnoringModifiers_isARepeat_keyCode_(
                A.NSEventTypeKeyDown, (0, 0), modifiers, 0, editor.window().windowNumber(),
                None, character, character, False, 0)
            return bool(editor.performKeyEquivalent_(event))

        def anchor():
            rect = editor.visibleRect()
            point = F.NSMakePoint(F.NSMidX(rect), F.NSMidY(rect))
            return ZoomAnchor.capture(editor.geometry, point.x, point.y), point, (
                point.x - rect.origin.x, point.y - rect.origin.y)

        def stayed_put(content, relative):
            rect = editor.visibleRect()
            x, y = content.point(editor.geometry)
            return abs(x - rect.origin.x - relative[0]) < 1.1 and abs(y - rect.origin.y - relative[1]) < 1.1

        for view_mode in ViewMode:
            editor.view_mode = view_mode
            editor.zoom = 1.25
            editor.refresh(reveal=False)
            clip.scrollToPoint_((0, editor.geometry.line_y(60) - clip.bounds().size.height / 2))
            scroll.reflectScrolledClipView_(clip)
            content, _, relative = anchor()
            if not key("+", A.NSEventModifierFlagCommand | A.NSEventModifierFlagShift):
                return False
            if editor.zoom != 1.5 or not stayed_put(content, relative):
                return False
            if not key("-") or editor.zoom != 1.25 or not key("0") or editor.zoom != 1:
                return False
            if not key("=") or editor.zoom != 1.1:
                return False
            content, point, relative = anchor()
            event = PagemarkProbeMagnifyEvent.alloc().init()
            event.delta = .25
            event.point = editor.convertPoint_toView_(point, None)
            editor.performSelector_withObject_("magnifyWithEvent:", event)
            if abs(editor.zoom - 1.375) > 1e-6 or not stayed_put(content, relative):
                return False
            if editor.session.snapshot() != snapshot or editor.session.layout is not layout:
                return False
        return True
    finally:
        editor.session.restore(before)
        editor.view_mode, editor._zoom_levels, editor.preferences = mode, levels, preferences
        editor.refresh(reveal=False)


def check_fit_actions(editor):
    before = editor.session.snapshot()
    mode, levels, preferences = editor.view_mode, dict(editor._zoom_levels), editor.preferences
    window, scroll = editor.window(), editor.enclosingScrollView()
    original_frame = window.frame()
    editor.preferences = None
    try:
        text = "Fit action probe\n" * 150
        editor.session.restore(Snapshot(StyledText(text, (0,) * len(text)), 0, None, 0))
        snapshot, layout = editor.session.snapshot(), editor.session.layout
        for view_mode in ViewMode:
            window.setFrame_display_(original_frame, True)
            editor.view_mode, editor.zoom = view_mode, 2
            editor.refresh(reveal=False)
            frame = rect_values(window.frame())
            fit_width(editor)
            slack = scroll.contentSize().width - editor.geometry.natural_width
            if rect_values(window.frame()) != frame or not -.1 <= slack <= 2:
                return False
            for scale in (1.25, MAX_ZOOM):
                editor.zoom = scale
                editor.refresh(reveal=False)
                resize_window_to_fit(editor)
                x, y, width, height = rect_values(window.frame())
                screen = window.screen() or A.NSScreen.mainScreen()
                visible = screen.visibleFrame()
                if editor.zoom != scale or y != frame[1] or height != frame[3]:
                    return False
                if x < F.NSMinX(visible) - .1 or x + width > F.NSMaxX(visible) + .1:
                    return False
                chrome = width - scroll.contentSize().width
                desired = editor.geometry.natural_width + chrome
                expected = min(visible.size.width, max(window.minSize().width,
                                                       min(desired, window.maxSize().width)))
                if abs(width - expected) > 1.1:
                    return False
                if editor.session.snapshot() != snapshot or editor.session.layout is not layout:
                    return False
        return True
    finally:
        editor.session.restore(before)
        editor.view_mode, editor._zoom_levels, editor.preferences = mode, levels, preferences
        window.setFrame_display_(original_frame, True)
        editor.refresh(reveal=False)

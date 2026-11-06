"""Secure, versioned editor UI state; AppKit owns document URLs and window frames."""
from dataclasses import dataclass
from math import isfinite

from .display_preferences import ViewMode
from .zoom import bounded_zoom

PREFIX = "org.pagemark.editor."


@dataclass(frozen=True)
class EditorRestorationState:
    cursor: int
    anchor: int
    caret_style: int
    mode: int
    layout_zoom: float
    draft_zoom: float
    double_spacing: bool
    scroll_x: float
    scroll_y: float

    @classmethod
    def capture(cls, editor):
        session = editor.session
        scroll = editor.enclosingScrollView()
        origin = scroll.contentView().bounds().origin if scroll else None
        return cls(session.cursor, session.anchor if session.anchor is not None else session.cursor,
                   session.model.caret_style, int(editor.view_mode), editor._zoom_levels[False],
                   editor._zoom_levels[True], editor.double_spacing,
                   origin.x if origin else 0, origin.y if origin else 0)

    def encode(self, coder):
        coder.encodeInteger_forKey_(1, PREFIX + "version")
        for name in ("cursor", "anchor", "caret_style", "mode"):
            coder.encodeInteger_forKey_(getattr(self, name), PREFIX + name)
        for name in ("layout_zoom", "draft_zoom", "scroll_x", "scroll_y"):
            coder.encodeDouble_forKey_(getattr(self, name), PREFIX + name)
        coder.encodeBool_forKey_(self.double_spacing, PREFIX + "double_spacing")

    @classmethod
    def decode(cls, coder):
        if not coder.containsValueForKey_(PREFIX + "version"):
            return None
        if coder.decodeIntegerForKey_(PREFIX + "version") != 1:
            return None
        integers = [int(coder.decodeIntegerForKey_(PREFIX + name))
                    for name in ("cursor", "anchor", "caret_style", "mode")]
        floats = [float(coder.decodeDoubleForKey_(PREFIX + name))
                  for name in ("layout_zoom", "draft_zoom", "scroll_x", "scroll_y")]
        return cls(*integers, *floats[:2], bool(coder.decodeBoolForKey_(PREFIX + "double_spacing")),
                   *floats[2:])

    def apply(self, editor):
        session = editor.session
        limit = session.index.length
        cursor = session.index.snap(max(0, min(self.cursor, limit)))
        anchor = session.index.snap(max(0, min(self.anchor, limit)))
        session.select(anchor, cursor)
        session.model.caret_style = self.caret_style & 3
        try:
            editor.view_mode = ViewMode(self.mode)
        except ValueError:
            pass  # Keep the current preference if a newer version added a mode.
        editor._zoom_levels = {False: bounded_zoom(self.layout_zoom),
                               True: bounded_zoom(self.draft_zoom)}
        editor.double_spacing = self.double_spacing
        editor.refresh(reveal=False)
        scroll = editor.enclosingScrollView()
        if scroll:
            clip = scroll.contentView()
            bounds = clip.bounds()
            bounds.origin.x = max(0, self.scroll_x) if isfinite(self.scroll_x) else 0
            bounds.origin.y = max(0, self.scroll_y) if isfinite(self.scroll_y) else 0
            clip.scrollToPoint_(clip.constrainBoundsRect_(bounds).origin)
            scroll.reflectScrolledClipView_(clip)

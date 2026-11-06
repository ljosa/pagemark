"""Screen-only preferences, independent of document state and print settings."""
from dataclasses import dataclass
from enum import IntEnum, StrEnum
from math import isfinite

from .zoom import DEFAULT_ZOOM, bounded_zoom

DRAFT_LINE_SPACINGS = (1.0, 1.25, 1.5, 2.0)


class ViewMode(IntEnum):
    CONTINUOUS = 0
    PAGES = 1
    DRAFT = 2


class Appearance(StrEnum):
    LIGHT = "light"
    DARK = "dark"
    SYSTEM = "system"


@dataclass(frozen=True)
class DraftFont:
    name: str = "JetBrainsMonoNL-Regular"
    size: float = 14


class DisplayPreferences:
    """NSUserDefaults adapter; an injected store keeps tests out of user defaults."""

    def __init__(self, defaults):
        self.defaults = defaults

    @property
    def view_mode(self):
        value = self.defaults.objectForKey_("ViewMode")
        if value is None:
            return ViewMode.PAGES if self.defaults.boolForKey_("PagesView") else ViewMode.CONTINUOUS
        try:
            return ViewMode(value)
        except (ValueError, TypeError):
            return ViewMode.CONTINUOUS

    @view_mode.setter
    def view_mode(self, mode):
        self.defaults.setInteger_forKey_(int(ViewMode(mode)), "ViewMode")

    @property
    def appearance(self):
        try:
            return Appearance(self.defaults.objectForKey_("Appearance"))
        except (ValueError, TypeError):
            return Appearance.SYSTEM

    @appearance.setter
    def appearance(self, value):
        self.defaults.setObject_forKey_(str(Appearance(value)), "Appearance")

    @property
    def draft_font(self):
        name = self.defaults.objectForKey_("DraftFontName")
        return DraftFont(str(name) if isinstance(name, str) and name else DraftFont.name)

    @draft_font.setter
    def draft_font(self, font):
        if not font.name:
            raise ValueError("Choose a draft font")
        self.defaults.setObject_forKey_(font.name, "DraftFontName")

    def zoom_for(self, mode):
        draft = ViewMode(mode) == ViewMode.DRAFT
        value = self.defaults.objectForKey_("DraftZoom" if draft else "LayoutZoom")
        if value is not None:
            return bounded_zoom(value)
        if not draft:
            return DEFAULT_ZOOM
        # 0.2.8 rendered DraftFontSize at 125%. Preserve that reading size
        # until an explicit zoom choice takes precedence over the old setting.
        try:
            size = float(self.defaults.objectForKey_("DraftFontSize"))
        except (TypeError, ValueError):
            return DEFAULT_ZOOM
        if not isfinite(size) or not 8 <= size <= 48:
            return DEFAULT_ZOOM
        return bounded_zoom(DEFAULT_ZOOM * size / DraftFont.size)

    @property
    def draft_line_spacing(self):
        value = self.defaults.objectForKey_("DraftLineSpacing")
        return float(value) if value in DRAFT_LINE_SPACINGS else 1.0

    @draft_line_spacing.setter
    def draft_line_spacing(self, value):
        if value not in DRAFT_LINE_SPACINGS:
            raise ValueError("Choose a supported draft line spacing")
        self.defaults.setDouble_forKey_(float(value), "DraftLineSpacing")

    def set_zoom(self, mode, value):
        key = "DraftZoom" if ViewMode(mode) == ViewMode.DRAFT else "LayoutZoom"
        self.defaults.setDouble_forKey_(bounded_zoom(value), key)

"""Screen zoom policy and content anchoring, independent of Cocoa and editing."""
from dataclasses import dataclass
from math import isfinite

DEFAULT_ZOOM = 1.25
MIN_ZOOM = 0.5
MAX_ZOOM = 5.0
ZOOM_STEPS = (0.5, 0.67, 0.8, 0.9, 1.0, 1.1, 1.25, 1.5, 1.75, 2.0, 2.5, 3.0, 4.0, 5.0)
ZOOM_COMMANDS = {"zoom_in", "zoom_out", "zoom_reset"}


def bounded_zoom(value, fallback=DEFAULT_ZOOM):
    try:
        value = float(value)
    except (ValueError, TypeError):
        return fallback
    return max(MIN_ZOOM, min(MAX_ZOOM, value)) if isfinite(value) else fallback


def command_zoom(current, command):
    if command == "zoom_reset":
        return 1.0
    if command == "zoom_in":
        return next((level for level in ZOOM_STEPS if level > current + 1e-6), MAX_ZOOM)
    if command == "zoom_out":
        return next((level for level in reversed(ZOOM_STEPS) if level < current - 1e-6), MIN_ZOOM)
    raise ValueError(f"Unknown zoom command: {command}")


def pinch_zoom(current, delta):
    # Each Cocoa magnify event supplies a relative change since the last event.
    return bounded_zoom(current * (1 + delta), fallback=current)


@dataclass(frozen=True)
class ZoomAnchor:
    line: int
    column: float
    row_fraction: float

    @classmethod
    def capture(cls, geometry, x, y):
        line = geometry.line_at_y(y)
        return cls(line, (x - geometry.text_x) / geometry.cell_width,
                   (y - geometry.line_y(line)) / geometry.line_height)

    def point(self, geometry):
        x, y = geometry.point(self.line, self.column)
        return x, y + self.row_fraction * geometry.line_height

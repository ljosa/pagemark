"""Pure sizing policy for fitting content to a view or a window to content."""
from .zoom import bounded_zoom


def fit_width_zoom(geometry, viewport_width):
    # Leave a point of slack for native font and backing-pixel rounding.
    available = max(0, viewport_width - geometry.horizontal_padding - 1)
    return bounded_zoom(geometry.zoom * available / geometry.content_width)


def fitted_window_frame(frame, screen, desired_width, minimum, maximum):
    """Return (x, y, width, height), preserving height and the left edge if possible."""
    x, y, _, height = frame
    left, _, screen_width, _ = screen
    width = min(screen_width, max(minimum, min(desired_width, maximum)))
    # Screen limits take precedence when a display is narrower than minimum.
    x = max(left, min(x, left + screen_width - width))
    return x, y, width, height

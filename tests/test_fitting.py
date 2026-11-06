"""Fit commands keep content magnification separate from window sizing."""
import pytest

from pagemark_app.fitting import fit_width_zoom, fitted_window_frame
from pagemark_app.geometry import CellMetrics, EditorGeometry
from pagemark_app.zoom import MAX_ZOOM, MIN_ZOOM


@pytest.mark.parametrize("mode", ["continuous", "pages", "draft"])
@pytest.mark.parametrize("width", [420, 840, 1600])
def test_fit_width_uses_the_whole_page_or_draft_column_and_its_padding(mode, width):
    def geometry(zoom):
        metrics = CellMetrics(8.4 * zoom, 17 * zoom, 13 * zoom) if mode == "draft" else None
        return EditorGeometry(150, width, mode == "pages", zoom=zoom, draft_metrics=metrics)

    fitted = geometry(fit_width_zoom(geometry(2), width))
    assert fitted.natural_width == pytest.approx(width - 1)
    assert fitted.width == width
    assert fit_width_zoom(geometry(2), 100) == MIN_ZOOM
    assert fit_width_zoom(geometry(2), 10000) == MAX_ZOOM


@pytest.mark.parametrize("frame,screen,desired,minimum,maximum,expected", [
    ((200, 50, 900, 720), (0, 0, 1600, 1000), 800, 480, 3000, (200, 50, 800, 720)),
    ((1000, 50, 600, 720), (0, 0, 1600, 1000), 1000, 480, 3000, (600, 50, 1000, 720)),
    ((200, 50, 900, 720), (0, 0, 1600, 1000), 3000, 480, 4000, (0, 50, 1600, 720)),
    ((-1200, -50, 900, 720), (-1600, 0, 1600, 1000), 1100, 480, 3000, (-1200, -50, 1100, 720)),
    ((-600, 50, 600, 720), (-1600, 0, 1600, 1000), 1100, 480, 3000, (-1100, 50, 1100, 720)),
    ((200, 50, 900, 720), (0, 0, 1600, 1000), 300, 480, 3000, (200, 50, 480, 720)),
    ((200, 50, 900, 720), (0, 0, 1600, 1000), 1300, 480, 1000, (200, 50, 1000, 720)),
    ((200, 50, 900, 720), (0, 0, 400, 1000), 900, 480, 3000, (0, 50, 400, 720)),
])
def test_window_fit_changes_only_width_and_the_minimum_horizontal_position(
        frame, screen, desired, minimum, maximum, expected):
    assert fitted_window_frame(frame, screen, desired, minimum, maximum) == expected

"""Zoom policy preserves content coordinates across different screen geometries."""
import pytest

from pagemark_app.geometry import CellMetrics, EditorGeometry
from pagemark_app.zoom import MAX_ZOOM, MIN_ZOOM, ZoomAnchor, command_zoom, pinch_zoom


def test_keyboard_zoom_steps_from_arbitrary_pinch_scales_and_stops_at_limits():
    assert command_zoom(1.33, "zoom_in") == 1.5
    assert command_zoom(1.33, "zoom_out") == 1.25
    assert command_zoom(1.25, "zoom_in") == 1.5
    assert command_zoom(1.25, "zoom_out") == 1.1
    assert command_zoom(MAX_ZOOM, "zoom_in") == MAX_ZOOM
    assert command_zoom(MIN_ZOOM, "zoom_out") == MIN_ZOOM
    assert command_zoom(3.14, "zoom_reset") == 1


def test_pinch_uses_incremental_factors_and_rejects_invalid_scales():
    zoom = pinch_zoom(1, .2)
    assert zoom == 1.2
    assert pinch_zoom(zoom, -.25) == pytest.approx(.9)
    assert pinch_zoom(2, 100) == MAX_ZOOM
    assert pinch_zoom(2, -2) == MIN_ZOOM
    assert pinch_zoom(2, float("nan")) == 2
    assert pinch_zoom(2, float("inf")) == 2


@pytest.mark.parametrize("mode", ["continuous", "pages", "draft"])
@pytest.mark.parametrize("double", [False, True])
def test_content_anchor_tracks_text_including_page_boundaries_at_any_scale(mode, double):
    def geometry(zoom):
        metrics = CellMetrics(8 * zoom, 17 * zoom, 13 * zoom) if mode == "draft" else None
        return EditorGeometry(150, 840, mode == "pages", double, zoom, draft_metrics=metrics)

    before = geometry(1.25)
    for line in (0, 1, 26, 27, 53, 54, 80, 149):
        x, y = before.point(line, 17.3)
        y += before.line_height * .2
        anchor = ZoomAnchor.capture(before, x, y)
        for zoom in (.5, .67, 1, 2.33, 4):
            after = geometry(zoom)
            new_x, new_y = anchor.point(after)
            assert (new_x - after.text_x) / after.cell_width == pytest.approx(17.3)
            assert new_y == pytest.approx(after.line_y(line) + after.line_height * .2)
        assert anchor.point(before) == pytest.approx((x, y))

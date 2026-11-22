"""The boundary polygon, its area, and where a flight leaves the park."""

from __future__ import annotations

import pytest

from pyrio import Stadium
from pyrio.geometry import area, boundary, boundary_crossing


def test_every_boundary_is_closed():
    for stadium in Stadium:
        points = boundary(stadium)
        assert len(points) > 30, stadium
        assert points[0] == points[-1]


def test_area_is_the_shoelace_area_not_the_perimeter():
    # The old ConvexHull.area was the hull's perimeter, about 340 to 385 here.
    areas = {stadium: area(stadium) for stadium in Stadium}
    assert areas[Stadium.MARIO_STADIUM] == pytest.approx(10065.76, abs=0.01)
    assert areas[Stadium.TOY_FIELD] == pytest.approx(11121.39, abs=0.01)
    assert all(8000 < a < 11200 for a in areas.values())


def test_area_ignores_the_winding_direction():
    # Some outlines run clockwise, some counter-clockwise; the area is positive.
    assert area(Stadium.BOWSER_CASTLE) > 0
    assert area(Stadium.DK_JUNGLE) > 0


def test_boundary_crossing():
    out = boundary_crossing(Stadium.MARIO_STADIUM, [(0.0, 10.0, 90.0), (0.0, 8.0, 130.0)])
    assert out is not None
    assert 90.0 < out[2] < 130.0
    assert boundary_crossing(Stadium.MARIO_STADIUM, [(0.0, 1.0, 10.0), (0.0, 1.0, 20.0)]) is None

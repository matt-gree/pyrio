"""Regression tests for the stadium drawing helpers.

calculate_stadium_area() referenced ConvexHull, which was imported only inside
the module's ``__main__`` block, so every library call raised NameError.
"""
import pytest

from pyrio.draw import draw_stadium


STADIUM_STEMS = [
    "mario_stadium",
    "bowser_castle",
    "wario_palace",
    "yoshi_park",
    "peach_garden",
    "dk_jungle",
    "toy_field",
]


@pytest.mark.parametrize("stem", STADIUM_STEMS)
def test_calculate_stadium_area_is_callable(stem):
    area = draw_stadium.calculate_stadium_area(stem)
    assert isinstance(area, float)
    assert area > 0

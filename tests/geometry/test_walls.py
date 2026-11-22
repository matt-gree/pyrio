"""The outfield-wall table and the questions it answers."""

from __future__ import annotations

import itertools

import pytest

from pyrio import Stadium
from pyrio.geometry import clears_wall, wall_at, wall_crossing, walls


def test_every_stadium_has_a_wall():
    for stadium in Stadium:
        assert walls(stadium), stadium


def test_mario_stadium_centre_wall_is_four_high():
    # The hand-typed table pyrio once had said 3; all eight panels measure 4.00.
    segment = wall_at(Stadium.MARIO_STADIUM, 0.0)
    assert segment is not None
    assert segment.z_at(0.0) == pytest.approx(100.04, abs=0.01)
    assert segment.height == 4.0


def test_peach_garden_centre_is_stepped():
    heights = {x: wall_at(Stadium.PEACH_GARDEN, x) for x in (0.0, -6.0, -8.0, -50.0)}
    assert [s.height for s in heights.values() if s] == [23.0, 20.99, 18.0, 7.0]


def test_toy_field_has_a_uniform_ten_and_a_half_wall():
    segment = wall_at(Stadium.TOY_FIELD, 0.0)
    assert segment is not None
    assert segment.z_at(0.0) == pytest.approx(100.97, abs=0.01)
    assert {s.height for s in walls(Stadium.TOY_FIELD)} == {10.5}


def test_no_wall_past_the_foul_poles():
    assert wall_at(Stadium.MARIO_STADIUM, 500.0) is None
    assert wall_at(Stadium.MARIO_STADIUM, -500.0) is None


def test_the_table_is_contiguous_and_ordered():
    # wall_at matches start <= x < end and takes the first, so a gap is a dead x
    # and an overlap hides a segment.
    for stadium in Stadium:
        segments = walls(stadium)
        for a, b in itertools.pairwise(segments):
            assert a.end_x > a.start_x
            assert b.start_x == pytest.approx(a.end_x, abs=1e-6), stadium


def test_clears_wall():
    assert clears_wall(Stadium.MARIO_STADIUM, [(0.0, 30.0, 150.0)])
    assert not clears_wall(Stadium.MARIO_STADIUM, [(0.0, 1.0, 50.0)])
    assert not clears_wall(Stadium.MARIO_STADIUM, [(0.0, 3.9, 101.0)])  # into the wall
    assert clears_wall(Stadium.TOY_FIELD, [(0.0, 30.0, 150.0)])


def test_wall_crossing_interpolates_the_wall_plane():
    point = wall_crossing(Stadium.MARIO_STADIUM, [(0.0, 10.0, 90.0), (0.0, 8.0, 110.0)])
    assert point is not None
    assert point[2] == pytest.approx(100.0445)
    assert point[1] == pytest.approx(10.0 - 2.0 * (100.0445 - 90.0) / 20.0)
    assert wall_crossing(Stadium.MARIO_STADIUM, [(0.0, 1.0, 10.0), (0.0, 1.0, 20.0)]) is None
    assert wall_crossing(Stadium.MARIO_STADIUM, []) is None


# --- transitional: pinned to the pre-1.0 module until step 7 deletes it ----------


def test_the_table_is_the_old_modules():
    from pyrio.stadiums import STADIUM_WALLS

    for stadium in Stadium:
        old = STADIUM_WALLS[stadium.label]
        segments = walls(stadium)
        assert [s.start_x for s in segments] == old["starting_x"]
        assert [s.end_x for s in segments] == old["ending_x"]
        assert [s.height for s in segments] == old["wall_height"]
        assert [s.slope for s in segments] == old["m"]
        assert [s.intercept for s in segments] == old["c"]


def test_answers_match_the_old_module():
    import random

    from pyrio import stadiums

    rng = random.Random(3)
    for _ in range(300):
        stadium = rng.choice(list(Stadium))
        path = [(rng.uniform(-70, 70), rng.uniform(0, 30), rng.uniform(60, 130)) for _ in range(6)]
        path.sort(key=lambda p: p[2])
        assert clears_wall(stadium, path) == stadiums.is_home_run(path, stadium.label)
        assert wall_crossing(stadium, path) == stadiums.wall_collision_point(path, stadium.label)

"""Outfield-wall queries, including the stadium pyrio has no wall data for.

Toy Field is a valid StadiumID with no entry in STADIUM_WALLS (inherited from
the JS `stadiums` constant). wall_at used to raise KeyError for it, which no
caller expected.
"""
import pytest

from pyrio import stadiums


def test_known_stadiums_have_wall_data():
    assert stadiums.has_wall_data("Mario Stadium")
    assert stadiums.has_wall_data("Peach Garden")
    assert len(stadiums.STADIUM_NAMES) == 6


def test_toy_field_has_no_wall_data():
    assert not stadiums.has_wall_data("Toy Field")


def test_wall_at_returns_none_for_a_stadium_without_walls():
    # Was KeyError. None matches how wall_collision_point already treats it.
    assert stadiums.wall_at("Toy Field", 0.0) is None
    assert stadiums.wall_at("Toy Field", -30.0) is None


def test_wall_at_still_answers_for_a_known_stadium():
    wall = stadiums.wall_at("Mario Stadium", 0.0)
    assert wall is not None
    wall_z, height = wall
    assert wall_z == pytest.approx(100.0)
    assert height == 3


def test_wall_at_returns_none_past_the_foul_poles():
    assert stadiums.wall_at("Mario Stadium", 500.0) is None


def test_is_home_run_refuses_rather_than_guessing():
    # Toy Field's collision model does have a fence, so False would be a claim
    # this module cannot support: it lacks the height, not the fence.
    traj = [(0.0, 30.0, 150.0)]
    with pytest.raises(ValueError, match="no outfield wall data"):
        stadiums.is_home_run(traj, "Toy Field")


def test_is_home_run_still_works_for_a_known_stadium():
    over = [(0.0, 30.0, 150.0)]     # way out, well above a 3-high wall
    assert stadiums.is_home_run(over, "Mario Stadium") is True
    short = [(0.0, 1.0, 50.0)]      # in the park
    assert stadiums.is_home_run(short, "Mario Stadium") is False


def test_wall_collision_point_still_returns_none_for_toy_field():
    # Unchanged, and documented in its own docstring.
    assert stadiums.wall_collision_point([(0.0, 30.0, 150.0)], "Toy Field") is None


def test_home_run_stadiums_skips_the_wall_less_stadium():
    # It iterates STADIUM_NAMES, so it must not hit the new ValueError.
    names = stadiums.home_run_stadiums([(0.0, 30.0, 150.0)])
    assert "Toy Field" not in names
    assert "Mario Stadium" in names


def test_game_highlights_survives_a_stadium_without_walls():
    # robbed_home_runs refuses for Toy Field; the package should drop that one
    # highlight rather than fail entirely.
    from pyrio import hit_analysis
    pkg = hit_analysis.game_highlights([], stadium="Toy Field")
    assert pkg["robbed_home_runs"] == []
    assert set(pkg) == {"hardest_hit", "longest_flight", "highest_apex",
                        "deepest_robbery", "robbed_home_runs"}

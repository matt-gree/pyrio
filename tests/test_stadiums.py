"""Outfield-wall queries over the derived STADIUM_WALLS table.

The table is generated from the game's collision models by
tools/derive_stadium_walls.py. These tests pin the behaviour callers rely on
and the two heights where the generated table corrected the old hand-typed
one, so a regeneration that quietly changes them fails here.
"""
import pytest

from pyrio import stadiums


def test_every_stadium_has_wall_data():
    # Toy Field used to be missing, so is_home_run raised for a real
    # StadiumID. All seven are covered now.
    assert len(stadiums.STADIUM_NAMES) == 7
    for name in ("Mario Stadium", "Peach Garden", "Wario Palace", "Yoshi Park",
                 "DK Jungle", "Bowser Castle", "Toy Field"):
        assert stadiums.has_wall_data(name), name


def test_has_wall_data_is_false_for_an_unknown_name():
    assert not stadiums.has_wall_data("Delfino Plaza")
    assert not stadiums.has_wall_data("")


def test_wall_at_returns_none_for_an_unknown_stadium():
    # Was KeyError. None matches how wall_collision_point already treats it.
    assert stadiums.wall_at("Delfino Plaza", 0.0) is None


def test_mario_stadium_centre_wall_is_four_high():
    # The hand-typed table said 3. All eight of the model's wall panels
    # measure 4.00, and the distance it recorded as 100 is 100.04, so the
    # distance was transcribed correctly and the height was not.
    wall = stadiums.wall_at("Mario Stadium", 0.0)
    assert wall is not None
    wall_z, height = wall
    assert wall_z == pytest.approx(100.04, abs=0.01)
    assert height == 4.0


def test_peach_garden_centre_is_stepped():
    # Three heights across the middle, which the old reading flattened to 18
    # by measuring one course's thickness instead of the wall's top.
    assert stadiums.wall_at("Peach Garden", 0.0)[1] == 23.0
    assert stadiums.wall_at("Peach Garden", -6.0)[1] == 20.99
    assert stadiums.wall_at("Peach Garden", -8.0)[1] == 18.0


def test_peach_garden_corner_wall_is_seven_high():
    # The hand-typed table said 8; all nine corner triangles measure 7.000.
    assert stadiums.wall_at("Peach Garden", -50.0)[1] == 7.0


def test_toy_field_has_a_uniform_ten_and_a_half_wall():
    # Its height looked unrecoverable because every wall triangle reports
    # max(y) == 0 -- which is the point: mesh y is inverted world height, so
    # the wall top IS y = 0.
    wall = stadiums.wall_at("Toy Field", 0.0)
    assert wall is not None
    wall_z, height = wall
    assert wall_z == pytest.approx(100.97, abs=0.01)
    assert height == 10.5


def test_wall_at_returns_none_past_the_foul_poles():
    assert stadiums.wall_at("Mario Stadium", 500.0) is None
    assert stadiums.wall_at("Mario Stadium", -500.0) is None


def test_the_table_is_contiguous_and_ordered():
    # wall_at matches `sx <= x < ex` and returns the first hit, so a gap is a
    # dead x and an overlap silently shadows a segment.
    for name in stadiums.STADIUM_NAMES:
        w = stadiums.STADIUM_WALLS[name]
        starts, ends = w["starting_x"], w["ending_x"]
        assert len(starts) == len(ends) == len(w["wall_height"]) \
            == len(w["m"]) == len(w["c"]), name
        for i, (sx, ex) in enumerate(zip(starts, ends)):
            assert ex > sx, (name, i)
            if i + 1 < len(starts):
                assert starts[i + 1] == pytest.approx(ex, abs=1e-6), (name, i)


def test_is_home_run_refuses_only_for_an_unknown_stadium():
    traj = [(0.0, 30.0, 150.0)]
    with pytest.raises(ValueError, match="no outfield wall data"):
        stadiums.is_home_run(traj, "Delfino Plaza")


def test_is_home_run_uses_the_corrected_mario_height():
    over = [(0.0, 30.0, 150.0)]      # way out, well above the wall
    assert stadiums.is_home_run(over, "Mario Stadium") is True
    short = [(0.0, 1.0, 50.0)]       # in the park
    assert stadiums.is_home_run(short, "Mario Stadium") is False


def test_is_home_run_now_answers_for_toy_field():
    # Used to raise ValueError.
    assert stadiums.is_home_run([(0.0, 30.0, 150.0)], "Toy Field") is True
    assert stadiums.is_home_run([(0.0, 1.0, 50.0)], "Toy Field") is False


def test_home_run_stadiums_can_include_toy_field():
    names = stadiums.home_run_stadiums([(0.0, 40.0, 200.0)])
    assert "Mario Stadium" in names
    assert "Toy Field" in names


def test_game_highlights_computes_robberies_for_every_stadium():
    from pyrio import hit_analysis
    for name in stadiums.STADIUM_NAMES:
        pkg = hit_analysis.game_highlights([], stadium=name)
        assert pkg["robbed_home_runs"] == []
        assert set(pkg) == {"hardest_hit", "longest_flight", "highest_apex",
                            "deepest_robbery", "robbed_home_runs"}


def test_game_highlights_still_survives_an_unknown_stadium():
    from pyrio import hit_analysis
    pkg = hit_analysis.game_highlights([], stadium="Delfino Plaza")
    assert pkg["robbed_home_runs"] == []

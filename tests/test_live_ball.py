"""Live-ball physics: the loader, determinism, and where it beats the table.

live_ball is a port of RioVisualizer's physics.py, and the port is verified
against it by tools/check_live_ball_parity.py (560/560 runs identical, every
outcome and event type reached). That check needs a RioVisualizer checkout, so
it is not part of this suite. What is here instead: the parts of the interface
pyrio owns, and the behaviour that justified the port.
"""
import gzip
import hashlib
import json
import math

import pytest

from pyrio import live_ball, stadiums


def flight_over(x_at_wall, z_at_wall, height_at_wall, frames=200):
    """A flight crossing (x, z) at a given height, still descending.

    Deliberately simple: the point is a repeatable ball at a chosen spot on
    the wall, not a realistic hit.
    """
    n = 60
    vx, vz = x_at_wall / n, z_at_wall / n
    points = []
    for f in range(frames + 1):
        t = f / n
        y = height_at_wall * (1 - 0.35 * (t - 1.0) ** 2) if t <= 1.6 \
            else height_at_wall * (1 - 0.35 * 0.36)
        points.append((vx * f, max(0.15, y), vz * f))
    return points


# ------------------------------------------------------------------- loading

def test_every_stadium_has_a_bundled_mesh():
    assert live_ball.list_stadiums() == sorted(stadiums.STADIUM_NAMES)


def test_load_stadium_gives_triangles_and_a_park():
    stadium = live_ball.load_stadium("Mario Stadium")
    assert stadium["Triangle Collections"]
    assert stadium["Park"]["physics"]["groundY"] == 0.15


def test_load_stadium_refuses_an_unknown_name():
    with pytest.raises(ValueError, match="no collision mesh"):
        live_ball.load_stadium("Delfino Plaza")


def test_the_bundled_meshes_match_their_manifest():
    # The meshes are copied from RioVisualizer's extraction; the manifest is
    # how we know a mesh has not been edited or truncated in transit.
    manifest = json.loads((live_ball.COLLISION_DIR / "MANIFEST.json").read_text())
    assert len(manifest) == 7
    for filename, want in manifest.items():
        path = live_ball.COLLISION_DIR / f"{filename}.gz"
        raw = gzip.decompress(path.read_bytes())
        assert len(raw) == want["bytes"], filename
        assert hashlib.sha256(raw).hexdigest() == want["sha256"], filename


def test_stadium_triangles_are_shared_not_copied_per_call():
    # load_stadium caches, so playing out many hits in a park does not reparse
    # 5.6MB of JSON each time.
    assert live_ball.load_stadium("Toy Field")["Triangle Collections"] is \
        live_ball.load_stadium("Toy Field")["Triangle Collections"]


# ------------------------------------------------------------------ the loop

def test_a_ball_well_over_the_fence_is_a_home_run():
    assert live_ball.is_home_run(flight_over(0.0, 100.0, 30.0), "Mario Stadium")


def test_a_weak_grounder_stays_in_the_park():
    dribble = [(0.0, 1.0, 0.0)] + [(0.0, 0.15, z * 0.4) for z in range(1, 40)]
    result = live_ball.play_out(dribble, "Mario Stadium")
    assert result["outcome"] in ("stopped", "in_play", "fielded")


def test_outcomes_are_always_from_the_documented_set():
    for name in live_ball.list_stadiums():
        result = live_ball.play_out(flight_over(10.0, 95.0, 12.0), name, seed=3)
        assert result["outcome"] in live_ball.OUTCOMES, name


def test_the_same_seed_replays_identically():
    path = flight_over(-20.0, 90.0, 9.0)
    a = live_ball.play_out(path, "Yoshi Park", seed=11)
    b = live_ball.play_out(path, "Yoshi Park", seed=11)
    assert a["points"] == b["points"]
    assert a["events"] == b["events"]
    assert a["outcome"] == b["outcome"]


def test_an_empty_trajectory_is_rejected():
    with pytest.raises(ValueError, match="trajectory is empty"):
        live_ball.play_out([], "Mario Stadium")


def test_every_frame_is_reported_once():
    result = live_ball.play_out(flight_over(0.0, 100.0, 30.0), "Mario Stadium")
    # points[0] is the contact point, then one per frame.
    assert len(result["points"]) == result["events"][-1]["frame"] + 1


def test_hazards_can_be_switched_off():
    # Bowser Castle's Thwomps and star pads are hazards; with them removed the
    # park is bare geometry. Both runs have to stay self-consistent.
    path = flight_over(0.0, 88.0, 14.0)
    with_hz = live_ball.play_out(path, "Bowser Castle", seed=1)
    without = live_ball.play_out(path, "Bowser Castle", seed=1, hazards=False)
    assert with_hz["outcome"] in live_ball.OUTCOMES
    assert without["outcome"] in live_ball.OUTCOMES
    assert not [e for e in without["events"] if e["type"] == "hazard"]


# --------------------------------------------------- what the table cannot do

def test_yoshi_parks_fence_posts_stop_a_ball_the_table_clears():
    """The reason this module exists.

    stadiums.STADIUM_WALLS gives Yoshi Park a flat 3.2 wall. The park also has
    UNCLIMBABLE_WALL posts standing in the fence line at 3.5-4.2, which the
    game bounces balls off exactly as it does the fence
    (ball_physics.c:2783) but which the one-dimensional table cannot hold.

    Both x below are 3.2 in the table. The mesh clears one and not the other,
    at the same height -- which is the post. Comparing two x at one height
    also controls for the mesh modelling the ball's own radius, an offset of
    about 0.15 that a bare table/mesh comparison would confuse for this.
    """
    assert stadiums.wall_at("Yoshi Park", 0.0)[1] == 3.2
    assert stadiums.wall_at("Yoshi Park", -2.0)[1] == 3.2

    clear_gap = flight_over(0.0, 93.34, 3.4)
    into_post = flight_over(-2.0, 93.34, 3.4)

    # The table cannot tell them apart.
    assert stadiums.is_home_run(clear_gap, "Yoshi Park") is True
    assert stadiums.is_home_run(into_post, "Yoshi Park") is True

    # The mesh can.
    assert live_ball.is_home_run(clear_gap, "Yoshi Park", hazards=False) is True
    assert live_ball.is_home_run(into_post, "Yoshi Park", hazards=False) is False


def test_the_post_is_cleared_by_a_high_enough_ball():
    # Confirms the case above is a wall of finite height, not a dead spot.
    assert live_ball.is_home_run(
        flight_over(-2.0, 93.34, 6.0), "Yoshi Park", hazards=False) is True


def test_the_table_and_the_mesh_agree_on_clear_cases():
    # The table is a cheap approximation, not a wrong one: it should only
    # diverge in the margins the mesh resolves.
    for name in live_ball.list_stadiums():
        obvious = flight_over(0.0, 120.0, 40.0)
        assert live_ball.is_home_run(obvious, name, hazards=False) is True, name
        assert stadiums.is_home_run(obvious, name) is True, name

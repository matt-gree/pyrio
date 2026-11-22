"""The live ball's interface, and the plays the wall table can't call."""

from __future__ import annotations

from typing import Any

import pytest

from pyrio import Character, Hand, PitchType, Stadium, SwingType
from pyrio.geometry import clears_wall, wall_at
from pyrio.sim import (
    HitInputs,
    LiveBallEventKind,
    LiveBallOutcome,
    play_out,
    simulate_hit,
)


def flight_over(x_at_wall: float, z_at_wall: float, height_at_wall: float, frames: int = 200):
    """A repeatable flight crossing (x, z) at a given height, still descending."""
    n = 60
    vx, vz = x_at_wall / n, z_at_wall / n
    points: list[tuple[float, float, float]] = []
    for f in range(frames + 1):
        t = f / n
        y = (
            height_at_wall * (1 - 0.35 * (t - 1.0) ** 2)
            if t <= 1.6
            else height_at_wall * (1 - 0.35 * 0.36)
        )
        points.append((vx * f, max(0.15, y), vz * f))
    return points


def test_every_frame_is_reported_once():
    result = play_out(Stadium.MARIO_STADIUM, flight_over(0.0, 100.0, 30.0))
    assert result.outcome is LiveBallOutcome.HOME_RUN
    assert len(result.trajectory) == result.events[-1].frame + 1
    assert result.events[-1].kind is LiveBallEventKind.OUTCOME
    assert result.events[-1].outcome is LiveBallOutcome.HOME_RUN


def test_a_dribbler_stops():
    dribble = [(0.0, 0.15, 0.0), (0.0, 0.15, 0.05), (0.0, 0.15, 0.1)]
    result = play_out(Stadium.MARIO_STADIUM, dribble)
    assert result.outcome is LiveBallOutcome.STOPPED


def test_the_same_seed_plays_the_same_way():
    path = flight_over(-20.0, 60.0, 9.0)
    assert play_out(Stadium.YOSHI_PARK, path, seed=11) == play_out(
        Stadium.YOSHI_PARK, path, seed=11
    )


def test_an_empty_trajectory_is_refused():
    with pytest.raises(ValueError, match="trajectory is empty"):
        play_out(Stadium.MARIO_STADIUM, [])


def test_a_misspelt_option_is_refused():
    # The old continue_ball(..., hazard=False) quietly played with hazards on.
    options: dict[str, Any] = {"hazard": False}
    with pytest.raises(TypeError):
        play_out(Stadium.BOWSER_CASTLE, flight_over(0.0, 88.0, 14.0), **options)


def test_hazards_can_be_switched_off():
    path = flight_over(0.0, 88.0, 14.0)
    without = play_out(Stadium.BOWSER_CASTLE, path, seed=1, hazards=False)
    assert not [e for e in without.events if e.hazard is not None]


def test_a_simulated_hit_plays_out():
    hit = simulate_hit(
        HitInputs(
            batter=Character.MARIO,
            pitcher=Character.MARIO,
            pitch=PitchType.CURVE,
            swing=SwingType.CHARGE,
            hand=Hand.RIGHT,
            batter_x=0.0,
            ball_x=0.0,
            charge_up=1.0,
            charge_down=1.0,
        )
    )
    result = play_out(
        Stadium.MARIO_STADIUM, hit.trajectory, acceleration=hit.acceleration_per_frame
    )
    assert result.land_frame is not None
    assert result.trajectory[0] == hit.trajectory[0]


# --- what the wall table cannot do -------------------------------------------------


def test_a_ball_off_the_foul_pole_is_a_home_run():
    # Yoshi Park's poles (x +/-57.4..58.9, z 58.3..59.9) are FOUL_POLE surfaces.
    for x in (57.9, -57.9):
        result = play_out(Stadium.YOSHI_PARK, flight_over(x, 59.1, 8.0), hazards=False)
        assert result.outcome is LiveBallOutcome.HOME_RUN, x


def test_yoshi_parks_fence_posts_stop_a_ball_the_table_clears():
    """The table gives Yoshi Park a flat 3.2 wall; the mesh has posts in it at 3.5-3.6."""
    for x in (0.0, -2.0):
        segment = wall_at(Stadium.YOSHI_PARK, x)
        assert segment is not None
        assert segment.height == 3.2
    clear_gap = flight_over(0.0, 93.34, 3.4)
    into_post = flight_over(-2.0, 93.34, 3.4)
    assert clears_wall(Stadium.YOSHI_PARK, clear_gap)
    assert clears_wall(Stadium.YOSHI_PARK, into_post)

    gap = play_out(Stadium.YOSHI_PARK, clear_gap, hazards=False)
    assert gap.outcome is LiveBallOutcome.HOME_RUN
    post = play_out(Stadium.YOSHI_PARK, into_post, hazards=False)
    assert post.outcome is not LiveBallOutcome.HOME_RUN
    assert post.events[0].surface == "back wall"


def test_the_table_and_the_mesh_agree_on_clear_cases():
    obvious = flight_over(0.0, 120.0, 40.0)
    for stadium in Stadium:
        assert play_out(stadium, obvious, hazards=False).outcome is LiveBallOutcome.HOME_RUN
        assert clears_wall(stadium, obvious), stadium

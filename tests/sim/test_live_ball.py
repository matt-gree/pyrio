"""The live ball's interface, and the plays the wall table can't call."""

from __future__ import annotations

from dataclasses import replace
from typing import Any

import pytest

from pyrio import Character, Hand, PitchType, Stadium, SwingType
from pyrio.geometry import clears_wall, wall_at
from pyrio.sim import (
    HitInputs,
    HitResult,
    LiveBallEventKind,
    LiveBallOutcome,
    hazard_seed,
    play_out,
    play_out_flight,
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
    result = play_out_flight(Stadium.MARIO_STADIUM, flight_over(0.0, 100.0, 30.0))
    assert result.outcome is LiveBallOutcome.HOME_RUN
    assert len(result.trajectory) == result.events[-1].frame + 1
    assert result.events[-1].kind is LiveBallEventKind.OUTCOME
    assert result.events[-1].outcome is LiveBallOutcome.HOME_RUN


def test_a_dribbler_stops():
    dribble = [(0.0, 0.15, 0.0), (0.0, 0.15, 0.05), (0.0, 0.15, 0.1)]
    result = play_out_flight(Stadium.MARIO_STADIUM, dribble)
    assert result.outcome is LiveBallOutcome.STOPPED


def test_the_same_seed_plays_the_same_way():
    path = flight_over(-20.0, 60.0, 9.0)
    assert play_out_flight(Stadium.YOSHI_PARK, path, seed=11) == play_out_flight(
        Stadium.YOSHI_PARK, path, seed=11
    )


def test_an_empty_trajectory_is_refused():
    with pytest.raises(ValueError, match="trajectory is empty"):
        play_out_flight(Stadium.MARIO_STADIUM, [])


def test_a_misspelt_option_is_refused():
    # The old continue_ball(..., hazard=False) quietly played with hazards on.
    options: dict[str, Any] = {"hazard": False}
    with pytest.raises(TypeError):
        play_out_flight(Stadium.BOWSER_CASTLE, flight_over(0.0, 88.0, 14.0), **options)


def test_hazards_can_be_switched_off():
    path = flight_over(0.0, 88.0, 14.0)
    without = play_out_flight(Stadium.BOWSER_CASTLE, path, seed=1, hazards=False)
    assert not [e for e in without.events if e.hazard is not None]


def _hover(lead_in: list[tuple[float, float, float]], frames: int = 300):
    """A ball held low in left field near thwomp-0, creeping away from home,
    after ``lead_in``: in reach of thwomp-0 (and thwomp-1) the whole time."""
    x, y, z = -40.0, 15.0, 58.0
    return [*lead_in, *((x, y, z + 1e-4 * f) for f in range(frames))]


def _slams(path: list[tuple[float, float, float]]) -> dict[str, list[int]]:
    played = play_out_flight(Stadium.BOWSER_CASTLE, path, seed=1)
    slams: dict[str, list[int]] = {}
    for e in played.events:
        if e.result == "slam" and e.hazard is not None:
            slams.setdefault(e.hazard, []).append(e.frame)
    return slams


def test_a_thwomp_back_on_its_perch_slams_again():
    # thwomp_slamControl: a slam doesn't disarm it; climbing back, it perches again.
    slams = _slams(_hover([]))
    first, second = slams["thwomp-0"][:2]
    # rise 11 frames, fall, sit 42, climb 13 units at 0.2 a frame
    assert 11 + 42 + 65 <= second - first <= 11 + 16 + 42 + 66 + 2


@pytest.mark.parametrize(
    "lead_in",
    [
        # moving back toward home (velocity.z < 0)
        [(-40.0, 15.0, 58.0 + 0.2 * (5 - f)) for f in range(5)],
        # heading far wide of every Thwomp, carried to its depth
        [(-40.0 - 3.0 * (5 - f), 15.0, 58.0 - 0.01 * (5 - f)) for f in range(5)],
    ],
    ids=["toward-home", "wide"],
)
def test_a_thwomp_the_ball_fails_once_stays_disarmed(lead_in: list[tuple[float, float, float]]):
    assert _slams(_hover([]))  # the same ball, without the lead-in, sets them off
    assert _slams(_hover(lead_in)) == {}


@pytest.mark.parametrize("step", [0.4, 0.8, 1.5])
def test_a_klaptrap_knocks_a_rolling_ball_once(step: float):
    # DK Jungle sweeps its hazards from pastCoordinates[4] to the ball (checkCollision
    # asm; the C decompile has the ends swapped). Swept the other way, the
    # one-sided faces catch the ball a frame late and again on every frame after.
    path = [(2.4, 0.3, 40.0 + step * f) for f in range(80)]
    played = play_out_flight(Stadium.DK_JUNGLE, path, seed=1)
    hits = [e.frame for e in played.events if e.hazard == "klaptrap-1"]
    reaches_front = next(f for f, (_, _, z) in enumerate(path) if z >= 56.4)
    assert hits == [reaches_front]


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
    result = play_out_flight(Stadium.MARIO_STADIUM, hit.trajectory, acceleration=hit.acceleration)
    assert result.land_frame is not None
    assert result.trajectory[0] == hit.trajectory[0]


# --- what the wall table cannot do -------------------------------------------------


def test_a_ball_off_the_foul_pole_is_a_home_run():
    # Yoshi Park's poles (x +/-57.4..58.9, z 58.3..59.9) are FOUL_POLE surfaces.
    for x in (57.9, -57.9):
        result = play_out_flight(Stadium.YOSHI_PARK, flight_over(x, 59.1, 8.0), hazards=False)
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

    gap = play_out_flight(Stadium.YOSHI_PARK, clear_gap, hazards=False)
    assert gap.outcome is LiveBallOutcome.HOME_RUN
    post = play_out_flight(Stadium.YOSHI_PARK, into_post, hazards=False)
    assert post.outcome is not LiveBallOutcome.HOME_RUN
    assert post.events[0].surface == "back wall"


def test_the_table_and_the_mesh_agree_on_clear_cases():
    obvious = flight_over(0.0, 120.0, 40.0)
    for stadium in Stadium:
        assert play_out_flight(stadium, obvious, hazards=False).outcome is LiveBallOutcome.HOME_RUN
        assert clears_wall(stadium, obvious), stadium


def _hit(**changes: object) -> HitResult:
    inputs = HitInputs(
        batter=Character.MARIO,
        pitcher=Character.LUIGI,
        pitch=PitchType.CURVE,
        swing=SwingType.CHARGE,
        hand=Hand.RIGHT,
        batter_x=0.0,
        ball_x=0.0,
        charge_up=1.0,
        charge_down=1.0,
        seeds=(1565, 20008, 1628),
    )
    return simulate_hit(replace(inputs, **changes))


def test_play_out_takes_a_hit_and_plays_it_at_its_stadium():
    hit = _hit(stadium=Stadium.BOWSER_CASTLE)
    played = play_out(hit)
    assert played == play_out_flight(
        Stadium.BOWSER_CASTLE,
        hit.trajectory,
        acceleration=hit.acceleration,
        seed=hazard_seed(hit.inputs.seeds),
    )
    assert play_out(hit, seed=5, hazards=False) == play_out_flight(
        Stadium.BOWSER_CASTLE,
        hit.trajectory,
        acceleration=hit.acceleration,
        seed=5,
        hazards=False,
    )


def test_hazard_seed_mixes_the_three_rng_values():
    assert hazard_seed((1, 2, 3)) == (1 * 31 + 2) * 31 + 3


def test_garlic_halves_play_out_without_the_hits_push():
    hit = _hit(
        batter=Character.WARIO, swing=SwingType.STAR, stars=5, is_captain=True, charge_up=0.0
    )
    if hit.garlic_trajectory is None:
        pytest.skip("this swing didn't split")
    assert play_out(hit) == play_out_flight(
        hit.inputs.stadium, hit.trajectory, seed=hazard_seed(hit.inputs.seeds)
    )


def test_a_catch_cuts_the_flight_at_the_glove():
    hit = _hit()
    glove = hit.trajectory[40]
    played = play_out(hit, caught_at=glove)
    assert played.outcome is LiveBallOutcome.CAUGHT
    assert played.trajectory == hit.trajectory[:41]
    assert played.land_frame is None
    assert [e.kind for e in played.events] == [LiveBallEventKind.OUTCOME]

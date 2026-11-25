"""The simulation against a frozen record of its own results.

``pyrio.sim`` was ported from the pre-1.0 ``hit_simulation`` and ``live_ball``
modules and held to them number for number until they were deleted. This file
keeps that hold: ``tests/fixtures/sim_goldens.json.gz`` records the results
over the same spread of inputs the parity tests used, written while the port
and the originals still agreed exactly.

A change that moves any of these numbers changes the simulation. If that's
intended, regenerate the record and review the diff::

    python tests/sim/test_goldens.py

Floats are compared to 1e-9, not exactly, so a different platform's maths
library can't fail the test by a last-place rounding difference.
"""

from __future__ import annotations

import gzip
import json
import math
import pathlib
import random
from typing import Any

import pytest

from pyrio import (
    Character,
    ChargeType,
    Hand,
    InputDirection,
    PitchType,
    Stadium,
    SwingType,
)
from pyrio.sim import (
    HitInputs,
    HitOverrides,
    HitResult,
    LiveBallResult,
    Mod,
    play_out_flight,
    simulate_all_zones,
    simulate_hit,
    simulate_trajectory,
)

GOLDENS = pathlib.Path(__file__).parent.parent / "fixtures" / "sim_goldens.json.gz"

_PITCHES = [
    (PitchType.CURVE, None),
    (PitchType.CHARGE, ChargeType.SLIDER),
    (PitchType.CHARGE, ChargeType.PERFECT),
    (PitchType.CHANGE_UP, None),
    (PitchType.CHARGE, ChargeType.CAPTAIN_STAR),
]
# The mods that change a hit, in the order the recorded draws used. A new mod
# goes here only if it changes simulate_hit, and then the goldens move.
_HIT_MODS = (Mod.FIX_NON_RED_TOAD_REACH, Mod.REMOVE_SLICE)


# --- the inputs -----------------------------------------------------------------


def random_inputs(rng: random.Random) -> HitInputs:
    pitch, charge = rng.choice(_PITCHES)
    batter_x = rng.uniform(-1.2, 1.2)
    overrides = HitOverrides()
    if rng.random() < 0.15:
        overrides = HitOverrides(
            vertical_zone=rng.choice([None, 0, 1, 2, 3, 4]),
            horizontal_angle_raw=rng.choice([None, rng.randrange(0x200, 0x600)]),
            vertical_angle_raw=rng.choice([None, rng.randrange(-200, 900)]),
            power=rng.choice([None, rng.randrange(50, 250)]),
            banana_start_frame=rng.choice([None, rng.randrange(0, 40)]),
            banana_end_frame=rng.choice([None, rng.randrange(40, 200)]),
            banana_hand=rng.choice([None, Hand.RIGHT, Hand.LEFT]),
            garlic_spread_rad=rng.choice([None, rng.uniform(0.1, 0.4)]),
            garlic_real_ball_to_left=rng.choice([None, True, False]),
        )
    return HitInputs(
        batter=rng.choice(list(Character)),
        pitcher=rng.choice(list(Character)),
        pitch=pitch,
        charge=charge,
        swing=rng.choice([SwingType.SLAP, SwingType.CHARGE, SwingType.STAR, SwingType.STAR]),
        hand=rng.choice(list(Hand)),
        stick=InputDirection(rng.randrange(16)),
        batter_x=batter_x,
        ball_x=batter_x + rng.uniform(-0.95, 0.45),
        ball_z=rng.uniform(-1.0, 1.0),
        charge_up=rng.choice([0.0, 0.0, 0.35, 0.8, 1.0, 1.0]),
        charge_down=rng.choice([0.0, 0.5, 1.0, rng.random()]),
        contact_frame=rng.choice([*range(2, 11), *range(15)]),
        chem_links_on_base=rng.randrange(4),
        stars=rng.randrange(6),
        is_captain=rng.random() < 0.5,
        batter_is_superstar=rng.random() < 0.3,
        pitcher_is_superstar=rng.random() < 0.3,
        is_easy_batting=rng.random() < 0.2,
        stadium=rng.choice(list(Stadium)),
        mods=frozenset(m for m in _HIT_MODS if rng.random() < 0.3),
        seeds=(rng.randrange(32768), rng.randrange(32768), rng.randrange(32768)),
        overrides=overrides,
    )


def star_inputs() -> list[HitInputs]:
    return [
        HitInputs(
            batter=batter,
            pitcher=Character.MARIO,
            pitch=PitchType.CURVE,
            swing=SwingType.STAR,
            hand=Hand.RIGHT,
            batter_x=0.0,
            ball_x=0.0,
            stars=stars,
            is_captain=is_captain,
            charge_up=charge_up,
        )
        for batter in Character
        for stars, is_captain, charge_up in ((5, True, 0.0), (5, False, 1.0), (1, False, 0.0))
    ]


def flight(rng: random.Random, frames: int = 90) -> list[tuple[float, float, float]]:
    """A synthetic batted ball over the azimuths and launch angles the game produces."""
    speed = 1.4 + rng.random() * 1.6
    azimuth = -50 + rng.random() * 100
    elevation = 8 + rng.random() * 45
    return aimed(speed, elevation, azimuth, frames)


def aimed(
    speed: float, elevation_deg: float, azimuth_deg: float, frames: int = 150
) -> list[tuple[float, float, float]]:
    a, e = math.radians(azimuth_deg), math.radians(elevation_deg)
    vx, vy, vz = (
        speed * math.sin(a) * math.cos(e),
        speed * math.sin(e),
        speed * math.cos(a) * math.cos(e),
    )
    x, y, z = 0.0, 1.0, 0.0
    points = [(x, y, z)]
    for _ in range(frames):
        vy -= 0.00275
        vx, vy, vz = vx * 0.996, vy * 0.996, vz * 0.996
        x, y, z = x + vx, y + vy, z + vz
        y = max(y, 0.15)
        points.append((x, y, z))
    return points


# --- what's recorded --------------------------------------------------------------


def hit_record(result: HitResult) -> dict[str, Any]:
    trajectory = result.trajectory
    return {
        "contact_type": result.contact_type.label,
        "contact_absolute": result.contact_absolute,
        "contact_quality": result.contact_quality,
        "angles": [result.horizontal_angle_raw, result.vertical_angle_raw],
        "power": result.power,
        "velocity": list(result.velocity_per_frame),
        "acceleration": list(result.acceleration_per_frame),
        "ball_energy": result.ball_energy,
        "hang_frames": result.hang_frames,
        "landing": list(result.landing),
        "trajectory": [len(trajectory), max(p[1] for p in trajectory), list(trajectory[-1])],
        "garlic": None
        if result.garlic_trajectory is None
        else [len(result.garlic_trajectory), list(result.garlic_trajectory[-1])],
    }


def live_ball_record(result: LiveBallResult) -> dict[str, Any]:
    return {
        "outcome": result.outcome.value,
        "land_frame": result.land_frame,
        "points": len(result.trajectory),
        "end": list(result.trajectory[-1]),
        "events": [[e.frame, e.kind.value, list(e.location)] for e in result.events],
    }


def compute() -> dict[str, Any]:
    rng = random.Random(20261121)
    hits: list[dict[str, Any] | None] = []
    for _ in range(1000):
        try:
            hits.append(hit_record(simulate_hit(random_inputs(rng))))
        except ValueError:
            hits.append(None)  # the bat can't reach the ball
    rng = random.Random(7)
    trajectories: list[list[Any]] = []
    while len(trajectories) < 100:
        inputs, frames = random_inputs(rng), rng.randrange(1, 400)
        try:
            path = simulate_trajectory(inputs, frames)
        except ValueError:
            continue
        trajectories.append([len(path), list(path[-1])])
    rng = random.Random(11)
    zones: list[list[dict[str, Any]]] = []
    while len(zones) < 30:
        try:
            zones.append([hit_record(r) for r in simulate_all_zones(random_inputs(rng))])
        except ValueError:
            continue
    live: list[dict[str, Any]] = []
    for stadium in Stadium:
        rng = random.Random(stadium.id)
        for seed in range(40):
            path = flight(rng)
            for hazards in (True, False):
                played = play_out_flight(stadium, path, seed=seed, hazards=hazards)
                live.append(live_ball_record(played))
        for speed in (0.6, 1.0, 1.4):
            for azimuth in (-30.0, 0.0, 25.0):
                live.append(live_ball_record(play_out_flight(stadium, aimed(speed, 25.0, azimuth))))
    return {
        "hits": hits,
        "stars": [hit_record(simulate_hit(i)) for i in star_inputs()],
        "trajectories": trajectories,
        "zones": zones,
        "live_ball": live,
    }


# --- the tests -------------------------------------------------------------------


def assert_close(new: Any, old: Any, where: str) -> None:
    if isinstance(old, float):
        assert isinstance(new, int | float), where
        assert math.isclose(new, old, rel_tol=1e-9, abs_tol=1e-9), f"{where}: {new} != {old}"
    elif isinstance(old, list):
        assert isinstance(new, list), where
        assert len(new) == len(old), f"{where}: length {len(new)} != {len(old)}"
        for i, (a, b) in enumerate(zip(new, old, strict=True)):
            assert_close(a, b, f"{where}[{i}]")
    elif isinstance(old, dict):
        assert isinstance(new, dict), where
        assert new.keys() == old.keys(), where
        for key in old:
            assert_close(new[key], old[key], f"{where}.{key}")
    else:
        assert new == old, f"{where}: {new!r} != {old!r}"


@pytest.fixture(scope="module")
def results() -> tuple[dict[str, Any], dict[str, Any]]:
    with gzip.open(GOLDENS, "rt", encoding="utf-8") as f:
        recorded = json.load(f)
    # Through JSON, so tuples compare as the lists they were saved as.
    return json.loads(json.dumps(compute())), recorded


@pytest.mark.parametrize("section", ["hits", "stars", "trajectories", "zones", "live_ball"])
def test_matches_the_record(section: str, results: tuple[dict[str, Any], dict[str, Any]]):
    new, recorded = results
    assert len(recorded[section]) > 0
    assert_close(new[section], recorded[section], section)


def test_the_record_is_not_vacuous(results: tuple[dict[str, Any], dict[str, Any]]):
    _, recorded = results
    assert sum(h is not None for h in recorded["hits"]) > 600
    kinds = {e[1] for r in recorded["live_ball"] for e in r["events"]}
    assert len(kinds) >= 6


if __name__ == "__main__":
    with gzip.open(GOLDENS, "wt", encoding="utf-8") as f:
        json.dump(compute(), f, separators=(",", ":"))
    print(f"wrote {GOLDENS}")

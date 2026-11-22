"""The ported live ball against the pre-1.0 one, frame for frame.

Transitional, like ``test_hit_parity.py``: step 7 deletes ``pyrio.live_ball``
and this file. The bar is exact: same outcome, land frame, trajectory and
events. ``tools/check_live_ball_parity.py`` holds the port to RioVisualizer,
the original, the same way.
"""

from __future__ import annotations

import collections
import math
import random
from typing import Any

import pytest

from pyrio import Stadium
from pyrio import live_ball as legacy
from pyrio.sim import LiveBallEvent, LiveBallEventKind, LiveBallResult, play_out

_FIELDS = {
    "surface": "surface",
    "hazard": "hazard",
    "result": "result",
    "block": "variant",
    "label": "label",
    "fall_speed": "fall",
    "heading_deg": "heading",
    "spin": "spin",
    "is_star_plant": "star",
}


def event_as_dict(event: LiveBallEvent) -> dict[str, Any]:
    """An event in the old module's dict form, ``assumed: False`` left out."""
    kind = event.outcome.value if event.outcome else event.kind.value
    out: dict[str, Any] = {"frame": event.frame, "type": kind, "pos": list(event.location)}
    for name, key in _FIELDS.items():
        value = getattr(event, name)
        if value is not None:
            out[key] = value
    if event.hazard_kind is not None:
        out["what"] = event.hazard_kind.value
    if event.is_assumed:
        out["assumed"] = True
    if event.is_approximate:
        out["approx"] = True
    return out


def normalise(old_event: dict[str, Any]) -> dict[str, Any]:
    return {k: v for k, v in old_event.items() if not (k == "assumed" and v is False)}


def assert_same(new: LiveBallResult, old: dict[str, Any]) -> None:
    assert new.outcome.value == old["outcome"]
    assert new.land_frame == old["land_frame"]
    assert [list(p) for p in new.trajectory] == old["points"]
    assert [event_as_dict(e) for e in new.events] == [normalise(e) for e in old["events"]]


def flight(seed: int, frames: int = 90) -> list[tuple[float, float, float]]:
    """A synthetic batted ball over the azimuths and launch angles the game produces."""
    rng = random.Random(seed)
    speed = 1.4 + rng.random() * 1.6
    azimuth = math.radians(-50 + rng.random() * 100)
    elevation = math.radians(8 + rng.random() * 45)
    vx = speed * math.sin(azimuth) * math.cos(elevation)
    vy = speed * math.sin(elevation)
    vz = speed * math.cos(azimuth) * math.cos(elevation)
    x, y, z = 0.0, 1.0, 0.0
    points = [(x, y, z)]
    for _ in range(frames):
        vy -= 0.00275
        vx, vy, vz = vx * 0.996, vy * 0.996, vz * 0.996
        x, y, z = x + vx, y + vy, z + vz
        y = max(y, 0.15)
        points.append((x, y, z))
    return points


@pytest.fixture(scope="module")
def legacy_stadiums() -> dict[Stadium, Any]:
    return {s: legacy.load_stadium(s.label) for s in Stadium}


SEEDS = 40  # the fewest that reach every event type, star and release included


def test_play_out_matches_the_old_module(legacy_stadiums: dict[Stadium, Any]):
    kinds: collections.Counter[LiveBallEventKind] = collections.Counter()
    for stadium in Stadium:
        for seed in range(SEEDS):
            path = flight(seed)
            for hazards in (True, False):
                old = legacy.continue_ball(
                    legacy_stadiums[stadium], path, seed=seed, hazards=hazards
                )
                new = play_out(stadium, path, seed=seed, hazards=hazards)
                assert_same(new, old)
                kinds.update(e.kind for e in new.events)
    # Not vacuous: the runs reach the hazards, not just the ground and walls.
    for kind in set(LiveBallEventKind) - {LiveBallEventKind.PANEL}:  # see the next test
        assert kinds[kind] > 0, kind


def test_options_match_the_old_module(legacy_stadiums: dict[Stadium, Any]):
    path = flight(3, frames=120)
    cases: list[dict[str, Any]] = [
        {"acceleration": (0.001, 0.0, -0.002)},
        {"mystery_blocks": "note"},
        {"mystery_blocks": "brick"},
        {"star_plants": True},
        {"star_plants": False},
        {"max_frames": 40},
        {"roll_frames": 30},
        {"stop_at": (path[-1][0], path[-1][2])},
    ]
    for stadium in Stadium:
        for options in cases:
            old_options = dict(options)
            acceleration = old_options.pop("acceleration", (0.0, 0.0, 0.0))
            old = legacy.continue_ball(
                legacy_stadiums[stadium], path, acceleration, seed=5, **old_options
            )
            assert_same(play_out(stadium, path, seed=5, **options), old)


def aimed(speed: float, elevation_deg: float, azimuth_deg: float, frames: int = 150):
    """A flight launched from the plate at a given speed and angle."""
    a, e = math.radians(azimuth_deg), math.radians(elevation_deg)
    vx = speed * math.sin(a) * math.cos(e)
    vy = speed * math.sin(e)
    vz = speed * math.cos(a) * math.cos(e)
    x, y, z = 0.0, 1.0, 0.0
    points = [(x, y, z)]
    for _ in range(frames):
        vy -= 0.00275
        vx, vy, vz = vx * 0.996, vy * 0.996, vz * 0.996
        x, y, z = x + vx, y + vy, z + vz
        y = max(y, 0.15)
        points.append((x, y, z))
    return points


def test_toy_field_panels_match(legacy_stadiums: dict[Stadium, Any]):
    # The flights above never land on a Toy Field panel; these are aimed at them.
    panels = 0
    for speed in (0.6, 0.8, 1.0, 1.2, 1.4, 1.6):
        for azimuth in (-30.0, 0.0, 25.0):
            path = aimed(speed, 25.0, azimuth)
            old = legacy.continue_ball(legacy_stadiums[Stadium.TOY_FIELD], path)
            new = play_out(Stadium.TOY_FIELD, path)
            assert_same(new, old)
            panels += sum(e.kind is LiveBallEventKind.PANEL for e in new.events)
    assert panels > 0

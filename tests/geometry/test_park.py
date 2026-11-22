"""Hazards, surface physics and fielders."""

from __future__ import annotations

import pytest

from pyrio import Position, Stadium
from pyrio.geometry import (
    FIELDER_LOCKOUT_FRAMES,
    FIELDER_START_LOCATIONS,
    HazardKind,
    hazards,
    physics,
)


def test_every_stadium_has_hazards_of_known_kinds():
    seen: set[HazardKind] = set()
    for stadium in Stadium:
        found = hazards(stadium)
        assert found, stadium
        assert len({h.id for h in found}) == len(found), stadium
        seen.update(h.kind for h in found)
    assert seen == set(HazardKind)


def test_hazards_by_stadium():
    kinds = {s: {h.kind for h in hazards(s)} for s in Stadium}
    assert HazardKind.THWOMP in kinds[Stadium.BOWSER_CASTLE]
    assert HazardKind.CHOMP in kinds[Stadium.WARIO_PALACE]
    assert HazardKind.PIRANHA in kinds[Stadium.YOSHI_PARK]
    assert HazardKind.BLOCK in kinds[Stadium.PEACH_GARDEN]
    assert HazardKind.KLAPTRAP in kinds[Stadium.DK_JUNGLE]
    assert HazardKind.PANEL in kinds[Stadium.TOY_FIELD]


def test_peach_gardens_blocks():
    blocks = [h for h in hazards(Stadium.PEACH_GARDEN) if h.kind is HazardKind.BLOCK]
    assert len(blocks) == 16
    note = next(h for h in blocks if h.id == "note-0")
    assert note.location == (-51.0, 9.0, 65.0)
    assert note.yaw_deg == 315.0
    assert note.parameters["type"] == "note"


def test_a_lava_pool_has_no_single_location():
    pools = [h for h in hazards(Stadium.BOWSER_CASTLE) if h.kind is HazardKind.LAVA_POOL]
    assert pools
    assert all(p.location is None for p in pools)


def test_hazard_parameters_are_read_only():
    hazard = hazards(Stadium.BOWSER_CASTLE)[0]
    with pytest.raises(TypeError):
        hazard.parameters["id"] = "x"  # type: ignore[index]


def test_physics():
    assert physics(Stadium.MARIO_STADIUM).ground_height == 0.15
    assert physics(Stadium.TOY_FIELD).ground_height == 0.35
    flat = {s for s in Stadium if physics(s).has_flat_floor}
    assert flat == set(Stadium) - {Stadium.BOWSER_CASTLE, Stadium.TOY_FIELD}
    mario = physics(Stadium.MARIO_STADIUM)
    assert (mario.first_bounce_vertical_keep, mario.wall_keep) == (0.44, 0.3)


def test_fielders():
    assert set(FIELDER_START_LOCATIONS) == set(Position)
    assert set(FIELDER_LOCKOUT_FRAMES) == set(Position)
    assert FIELDER_START_LOCATIONS[Position.CENTER_FIELD] == (0.0, 0.0, 76.0)
    assert FIELDER_LOCKOUT_FRAMES[Position.CATCHER] == 40

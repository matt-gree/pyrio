"""HitInputs.from_event: recorded contacts, rebuilt from the game model and simulated again."""

from __future__ import annotations

import pathlib
from typing import Any

import pytest

import pyrio
from pyrio import Game, MoonshotStatus, Stadium, SwingType
from pyrio.sim import HitInputs, simulate_hit

FIXTURES = pathlib.Path(__file__).parent.parent / "fixtures"
GAME_FILE = FIXTURES / "20260618T191655_SpiceOrange-Vs-MattGree_3896251267.json"
DECODED_FILE = FIXTURES / "decoded.20260618T191655_SpiceOrange-Vs-MattGree_3896251267.json"
# Every era recent enough to record the swing's RNG.
SIMULATABLE = [
    GAME_FILE,
    DECODED_FILE,
    *sorted((FIXTURES / "stat_files").glob("2.*/*.json")),
]


def simulatable(game: Game) -> list[tuple[pyrio.Event, HitInputs]]:
    out = []
    for event in game.events:
        if event.contact is None or event.pitch is None:
            continue
        if event.pitch.swing not in (SwingType.SLAP, SwingType.CHARGE, SwingType.STAR):
            continue
        out.append((event, HitInputs.from_event(event, stadium=game.stadium)))
    return out


@pytest.mark.parametrize("path", SIMULATABLE, ids=lambda p: f"{p.parent.name}/{p.name[:24]}")
def test_recorded_contacts_simulate_to_what_was_recorded(path: pathlib.Path):
    """Contact type and launch angles, against what the client wrote.

    Power is left out: in some games it comes out 1-2 low on most contacts, the
    same through the pre-1.0 bridge (tools/hit_sim_validation.py), which points
    at something the simulator doesn't model rather than at from_event.
    """
    game = pyrio.read_game(path)
    pairs = simulatable(game)
    assert len(pairs) > 10
    exact = 0
    for event, inputs in pairs:
        contact = event.contact
        assert contact is not None
        result = simulate_hit(inputs)
        if (
            result.contact_type is contact.type
            and result.horizontal_angle_raw == contact.horizontal_angle
            and result.vertical_angle_raw == contact.vertical_angle
        ):
            exact += 1
    assert exact / len(pairs) >= 0.9, f"{exact}/{len(pairs)} contacts reproduced exactly"


def test_encoded_and_decoded_files_give_the_same_inputs():
    encoded = [i for _, i in simulatable(pyrio.read_game(GAME_FILE))]
    decoded = [i for _, i in simulatable(pyrio.read_game(DECODED_FILE))]
    assert encoded == decoded


def test_matches_the_pre_1_0_bridge(recorded_legacy_inputs: list[Any]):
    """Transitional: the old stat-file bridge and from_event drive identical hits."""
    from pyrio import hit_simulation as legacy

    from .test_hit_parity import assert_same

    new = [i for _, i in simulatable(pyrio.read_game(DECODED_FILE))]
    assert len(new) == len(recorded_legacy_inputs)
    for inputs, old in zip(new, recorded_legacy_inputs, strict=True):
        assert_same(simulate_hit(inputs), legacy.simulate_hit(old))


def test_a_five_star_swing_is_rebuilt_fully_charged():
    game = pyrio.read_game(GAME_FILE)
    for event, inputs in simulatable(game):
        assert event.contact is not None
        if event.contact.moonshot is MoonshotStatus.MOONSHOT:
            assert inputs.charge_up == 1.0
            assert inputs.swing is SwingType.STAR


def test_events_without_contact_are_refused():
    game = pyrio.read_game(GAME_FILE)
    no_contact = next(e for e in game.events if e.contact is None)
    with pytest.raises(ValueError, match="no contact"):
        HitInputs.from_event(no_contact, stadium=Stadium.MARIO_STADIUM)


def test_files_without_rng_are_refused():
    game = pyrio.read_game(next((FIXTURES / "stat_files" / "0.1.7a").glob("*.json")))
    contact = next(e for e in game.events if e.contact is not None)
    with pytest.raises(ValueError, match="too old"):
        HitInputs.from_event(contact, stadium=game.stadium)

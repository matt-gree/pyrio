"""HitInputs.from_event: recorded contacts, rebuilt from the game model and simulated again."""

from __future__ import annotations

import json
import math
import pathlib
from typing import TYPE_CHECKING, Any

import pytest

import pyrio
from pyrio import ChargeType, Game, MoonshotStatus, PitchType, Stadium, SwingType
from pyrio.sim import HitInputs, simulate_contacts, simulate_hit

if TYPE_CHECKING:
    from collections.abc import Callable

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
    """Contact type, quality, launch angles and power, against what the client wrote."""
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
            and contact.power in (None, result.power)
            and (
                contact.quality is None
                or math.isclose(contact.quality, result.contact_quality, abs_tol=1e-3)
            )
        ):
            exact += 1
    assert exact / len(pairs) >= 0.9, f"{exact}/{len(pairs)} contacts reproduced exactly"


def test_superstar_batters_get_superstar_contact_size():
    """Superstar boosts contact size as well as power, so it shows in contact quality."""
    game = pyrio.read_game(
        FIXTURES / "stat_files/2.0.2/decoded.20240127T163640_Clutch1908-Vs-Baltor33_1908774040.json"
    )
    pairs = [(e, i) for e, i in simulatable(game) if i.batter_is_superstar]
    assert len(pairs) > 10
    for event, inputs in pairs:
        assert event.contact is not None
        assert event.contact.quality is not None
        assert math.isclose(
            event.contact.quality, simulate_hit(inputs).contact_quality, abs_tol=1e-3
        )


def test_encoded_and_decoded_files_give_the_same_inputs():
    encoded = [i for _, i in simulatable(pyrio.read_game(GAME_FILE))]
    decoded = [i for _, i in simulatable(pyrio.read_game(DECODED_FILE))]
    assert encoded == decoded


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


def _edited(edit: Callable[[dict[str, Any]], None]) -> Game:
    data = json.loads(GAME_FILE.read_text())
    for event in data["Events"]:
        edit(event)
    return pyrio.read_game(data)


def test_unrecorded_stars_are_none_and_star_swings_still_simulate():
    def no_stars(event: dict[str, Any]) -> None:
        event["Away Stars"] = event["Home Stars"] = 255

    game = _edited(no_stars)
    assert all(e.state.away_stars is None and e.state.home_stars is None for e in game.events)
    stars = [
        e
        for e in game.events
        if e.pitch is not None and e.pitch.swing is SwingType.STAR and e.contact is not None
    ]
    assert stars
    for event in stars:
        inputs = HitInputs.from_event(event, stadium=game.stadium)
        assert inputs.swing is SwingType.STAR
        assert inputs.stars >= 1
    assert len(simulate_contacts(game)) == len(simulate_contacts(pyrio.read_game(GAME_FILE)))


def test_a_curve_with_a_stray_charge_type_simulates_as_a_curve():
    def stray(event: dict[str, Any]) -> None:
        pitch = event.get("Pitch")
        if pitch and pitch["Pitch Type"] == 0:
            pitch["Charge Type"] = 2

    game = _edited(stray)
    swings = (SwingType.SLAP, SwingType.CHARGE, SwingType.STAR)
    curves = [
        e
        for e in game.events
        if e.pitch and e.pitch.type is PitchType.CURVE and e.contact and e.pitch.swing in swings
    ]
    assert curves
    assert all(e.pitch is not None and e.pitch.charge_type is ChargeType.SLIDER for e in curves)
    assert {HitInputs.from_event(e, stadium=game.stadium).charge for e in curves} == {None}


def test_simulate_contacts_leaves_out_a_contact_it_cannot_reproduce():
    full = simulate_contacts(pyrio.read_game(GAME_FILE))
    first = full[0].event_number

    def contradict(event: dict[str, Any]) -> None:
        if event["Event Num"] == first:
            event["Pitch"]["Pitch Type"] = 1  # a charge pitch with no charge type
            event["Pitch"]["Charge Type"] = 0

    assert [c.event_number for c in simulate_contacts(_edited(contradict))] == [
        c.event_number for c in full[1:]
    ]

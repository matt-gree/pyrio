"""Contact records and highlights."""

from __future__ import annotations

import functools
import math
import pathlib
from dataclasses import replace

import pyrio
from pyrio import (
    AtBatResult,
    Character,
    Hand,
    PitchType,
    PrimaryContactResult,
    SecondaryContactResult,
    Side,
    Stadium,
    SwingType,
)
from pyrio.sim import (
    ContactRecord,
    HitInputs,
    HitOverrides,
    LiveBallOutcome,
    best,
    find_highlights,
    format_highlights,
    simulate_contacts,
    simulate_hit,
)

INPUTS = HitInputs(
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


FIXTURES = pathlib.Path(__file__).parent.parent / "fixtures"
GAME_FILE = FIXTURES / "20260618T191655_SpiceOrange-Vs-MattGree_3896251267.json"


@functools.cache
def game() -> pyrio.Game:
    return pyrio.read_game(GAME_FILE)


def record(
    power: int,
    *,
    result: AtBatResult = AtBatResult.SINGLE,
    primary_result: PrimaryContactResult = PrimaryContactResult.FAIR,
    secondary_result: SecondaryContactResult = SecondaryContactResult.SINGLE,
) -> ContactRecord:
    """A contact with a chosen power and outcome, on a real event's bones."""
    event = simulate_contacts(game())[0].event
    assert event.contact is not None
    event = replace(
        event,
        number=power,
        result=result,
        batter_spot=replace(event.batter_spot, character=Character.MARIO),
        contact=replace(
            event.contact, primary_result=primary_result, secondary_result=secondary_result
        ),
    )
    hit = simulate_hit(replace(INPUTS, overrides=HitOverrides(power=power)))
    return ContactRecord(event=event, player="Player", hit=hit)


def test_record_properties():
    r = record(150)
    assert r.power == 150
    assert r.distance == r.hit.distance
    assert r.landing == r.trajectory[-1]
    assert r.is_fair
    assert not r.caught
    assert r.is_hit
    assert r.batter is Character.MARIO
    foul = record(150, primary_result=PrimaryContactResult.FOUL)
    assert foul.is_foul
    assert not foul.is_fair


def test_best():
    contacts = [record(120), record(200), record(160)]
    assert best(contacts, key=lambda c: c.power) is contacts[1]
    assert best([], key=lambda c: c.power) is None


def test_highlights_count_fair_balls_only():
    foul = record(300, primary_result=PrimaryContactResult.FOUL)
    fair = record(150)
    found = find_highlights([foul, fair])
    assert found.hardest_hit is fair
    assert found.longest_flight is fair
    assert found.highest_apex is fair
    assert found.deepest_robbery is None
    assert found.robbed_home_runs == ()


def test_robbed_home_runs_need_a_stadium():
    caught = record(
        400,
        result=AtBatResult.CAUGHT,
        secondary_result=SecondaryContactResult.OUT_CAUGHT,
    )
    assert caught.caught
    assert find_highlights([caught]).deepest_robbery is caught
    assert find_highlights([caught]).robbed_home_runs == ()
    robbed = find_highlights([caught], stadium=Stadium.MARIO_STADIUM).robbed_home_runs
    assert robbed == (caught,)


def test_format_highlights():
    caught = record(
        400, result=AtBatResult.CAUGHT, secondary_result=SecondaryContactResult.OUT_CAUGHT
    )
    lines = format_highlights(find_highlights([record(150), caught], stadium=Stadium.MARIO_STADIUM))
    assert lines[0].startswith("HARDEST HIT: Mario (Player) - 400 power Caught")
    assert any(line.startswith("ROBBED HOME RUN") for line in lines)
    assert format_highlights(find_highlights([])) == []


def test_simulate_contacts_covers_every_swing_that_connected():
    game = pyrio.read_game(GAME_FILE)
    records = simulate_contacts(game)
    swings = (SwingType.SLAP, SwingType.CHARGE, SwingType.STAR)
    expected = [
        e
        for e in game.events
        if e.contact is not None and e.pitch is not None and e.pitch.swing in swings
    ]
    assert [r.event_number for r in records] == [e.number for e in expected]
    for record, event in zip(records, expected, strict=True):
        assert event.contact is not None
        assert record.batter is event.batter_spot.character
        assert record.batting_side is event.state.batting_side
        assert record.result is event.result
        assert record.contact is event.contact
        assert record.event is event
        side = game.away if record.batting_side is Side.AWAY else game.home
        assert record.player == side.player


def test_simulate_contacts_reproduces_the_recorded_contact():
    records = simulate_contacts(pyrio.read_game(GAME_FILE))
    game = pyrio.read_game(GAME_FILE)
    by_number = {e.number: e for e in game.events}
    exact = 0
    for r in records:
        contact = by_number[r.event_number].contact
        assert contact is not None
        exact += r.hit.contact_type is contact.type
    assert exact / len(records) >= 0.9


def test_simulate_contacts_is_empty_for_files_without_rng():
    old = pyrio.read_game(next((FIXTURES / "stat_files" / "0.1.7a").glob("*.json")))
    assert simulate_contacts(old) == ()


def test_a_caught_ball_plays_out_to_the_glove():
    caught = next(r for r in simulate_contacts(game()) if r.caught)
    played = caught.play_out()
    assert played.outcome is LiveBallOutcome.CAUGHT
    assert played.land_frame is None
    glove = caught.contact.landing_location
    end = played.trajectory[-1]
    assert math.dist(end, glove) == min(math.dist(p, glove) for p in caught.trajectory)
    assert played.events[-1].outcome is LiveBallOutcome.CAUGHT


def test_a_ball_in_play_stops_with_the_first_fielder():
    grounders = [
        r
        for r in simulate_contacts(game())
        if not r.caught and r.is_fair and not r.result.is_hit and r.event.fielding is not None
    ]
    assert grounders
    outcomes = {r.play_out().outcome for r in grounders}
    assert LiveBallOutcome.FIELDED in outcomes

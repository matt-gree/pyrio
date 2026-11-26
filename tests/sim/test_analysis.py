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
    TAG_TO_MOD,
    ContactRecord,
    HitInputs,
    HitOverrides,
    LiveBallOutcome,
    Mod,
    find_highlights,
    format_highlights,
    hazard_seed,
    play_out,
    simulate_contacts,
    simulate_hit,
)

INPUTS = HitInputs(
    batter=Character.MARIO,
    pitcher=Character.MARIO,
    pitch_type=PitchType.CURVE,
    swing=SwingType.CHARGE,
    batting_hand=Hand.RIGHT,
    batter_x=0.0,
    ball_x=0.0,
    charge_power_up=1.0,
    charge_power_down=1.0,
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
    assert r.landing_location == r.trajectory[-1]
    assert r.is_fair
    assert not r.caught
    assert r.is_hit
    assert r.batter is Character.MARIO
    foul = record(150, primary_result=PrimaryContactResult.FOUL)
    assert foul.is_foul
    assert not foul.is_fair


def test_highlights_count_fair_balls_only():
    foul = record(300, primary_result=PrimaryContactResult.FOUL)
    fair = record(150)
    found = find_highlights([foul, fair])
    assert found.hardest_hit is fair
    assert found.longest_flight is fair
    assert found.highest_flight is fair
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


def test_simulate_contacts_covers_every_ball_in_play():
    game = pyrio.read_game(GAME_FILE)
    records = simulate_contacts(game)
    swings = (SwingType.SLAP, SwingType.CHARGE, SwingType.STAR, SwingType.BUNT)
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


def test_hazards_off_games_play_the_bare_park():
    # Tag set 198 ("S13 Superstars Off") was played with the "Hazards Off" code. A
    # stat file can't say so; with hazards on, a Thwomp stands in both balls' way.
    mods = frozenset({TAG_TO_MOD["Hazards Off"]})
    assert mods == {Mod.HAZARDS_OFF}
    on = {r.event_number: r for r in simulate_contacts(game())}
    off = {r.event_number: r for r in simulate_contacts(game(), mods=mods)}
    for number in (153, 190):
        assert on[number].result is AtBatResult.HOME_RUN
        assert on[number].play_out().outcome is not LiveBallOutcome.HOME_RUN
        assert off[number].play_out().outcome is LiveBallOutcome.HOME_RUN
        assert play_out(off[number].hit).outcome is LiveBallOutcome.HOME_RUN
        # An explicit choice wins over the mods.
        assert off[number].play_out(hazards=True) == on[number].play_out()
        assert on[number].play_out(hazards=False) == off[number].play_out()


def test_play_out_picks_hazard_dice_that_agree_with_the_record():
    path = (
        FIXTURES / "stat_files" / "2.1.1" / "20260219T212721_MattGree-Vs-Baltor33_1189820580.json"
    )
    record = next(r for r in simulate_contacts(pyrio.read_game(path)) if r.event_number == 7)
    assert record.is_foul
    fielding = record.event.fielding
    stop_at = None if fielding is None else (fielding.location[0], fielding.location[2])
    assert play_out(record.hit, stop_at=stop_at).outcome is not LiveBallOutcome.FOUL
    assert record.play_out().outcome is LiveBallOutcome.FOUL
    # A seed given is a seed kept.
    assert record.play_out(seed=hazard_seed(record.hit.inputs.rng)) == play_out(
        record.hit, stop_at=stop_at
    )

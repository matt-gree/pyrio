"""Contact records and highlights."""

from __future__ import annotations

from dataclasses import replace

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
    best,
    find_highlights,
    format_highlights,
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


def record(power: int, **fields: object) -> ContactRecord:
    hit = simulate_hit(replace(INPUTS, overrides=HitOverrides(power=power)))
    base = ContactRecord(
        event_number=power,
        inning=1,
        batting_side=Side.AWAY,
        player="Player",
        batter=Character.MARIO,
        swing=SwingType.CHARGE,
        result=AtBatResult.SINGLE,
        primary_result=PrimaryContactResult.FAIR,
        secondary_result=SecondaryContactResult.SINGLE,
        rbi=0,
        simulation=hit,
    )
    return replace(base, **fields)


def test_record_properties():
    r = record(150)
    assert r.power == 150
    assert r.distance == r.simulation.distance
    assert r.landing == r.trajectory[-1]
    assert r.is_fair
    assert not r.caught
    assert r.is_hit
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

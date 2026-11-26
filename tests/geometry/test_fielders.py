"""The bases, fielder starts and fielder reach."""

from __future__ import annotations

from pathlib import Path

import pytest

from pyrio import Ability, AtBatResult, Character, Position, read_game
from pyrio.geometry import (
    BASE_LOCATIONS,
    FIELDER_LOCKOUT_FRAMES,
    FIELDER_START_LOCATIONS,
    MOUND_LOCATION,
    fielder_reach,
)

STAT_FILES = Path(__file__).parent.parent / "fixtures" / "stat_files"


def test_the_bases_are_the_games():
    home, first, second, third = BASE_LOCATIONS
    assert (first[0], first[2]) == (18.95, 19.4)
    assert (third[0], third[2]) == (-first[0], first[2])  # third mirrors first
    assert second[2] == 39.0
    assert home[2] < 1.0
    assert MOUND_LOCATION[2] == 18.5


def test_a_fielder_goes_nowhere_during_the_lockout():
    lockout = FIELDER_LOCKOUT_FRAMES[Position.CENTER_FIELD]
    reach = fielder_reach(Character.MARIO, Position.CENTER_FIELD, lockout)
    assert (reach.running, reach.diving) == (0.0, 0.0)
    assert reach.start == FIELDER_START_LOCATIONS[Position.CENTER_FIELD]
    assert reach.reaches(reach.start)


def test_a_fielder_accelerates_to_jogging_speed_without_sprinting():
    lockout = FIELDER_LOCKOUT_FRAMES[Position.LEFT_FIELD]
    jogging = Character.MARIO.attributes.jogging_speed
    ramp = fielder_reach(Character.MARIO, Position.LEFT_FIELD, lockout + 15, sprint=False)
    assert ramp.running == pytest.approx(jogging * sum(range(1, 16)) / 15)
    later = fielder_reach(Character.MARIO, Position.LEFT_FIELD, lockout + 25, sprint=False)
    assert later.running - ramp.running == pytest.approx(10 * jogging)


def test_a_full_sprint_runs_at_1_4_times_jogging_speed():
    lockout = FIELDER_LOCKOUT_FRAMES[Position.RIGHT_FIELD]
    jogging = Character.MARIO.attributes.jogging_speed
    a = fielder_reach(Character.MARIO, Position.RIGHT_FIELD, lockout + 40)
    b = fielder_reach(Character.MARIO, Position.RIGHT_FIELD, lockout + 50)
    assert b.running - a.running == pytest.approx(10 * 1.4 * jogging)
    jog = fielder_reach(Character.MARIO, Position.RIGHT_FIELD, lockout + 50, sprint=False)
    assert b.running > jog.running


def test_reach_grows_with_time_speed_and_superstar():
    frames = range(0, 200, 7)
    reaches = [fielder_reach(Character.YOSHI, Position.CENTER_FIELD, f).diving for f in frames]
    assert reaches == sorted(reaches)
    slow = fielder_reach(Character.BOWSER, Position.CENTER_FIELD, 120).running
    fast = fielder_reach(Character.YOSHI, Position.CENTER_FIELD, 120).running
    assert fast > slow
    starred = fielder_reach(Character.BOWSER, Position.CENTER_FIELD, 120, is_superstar=True)
    assert starred.running > slow


def _has_sliding_catch(character: Character) -> bool:
    return Ability.SLIDING_CATCH in character.attributes.abilities


def test_a_dive_adds_the_dive_range_and_sliding_catch_reaches_further():
    lockout = FIELDER_LOCKOUT_FRAMES[Position.CENTER_FIELD]
    plain = next(c for c in Character if not _has_sliding_catch(c))
    reach = fielder_reach(plain, Position.CENTER_FIELD, lockout + 100)
    # The dive is decided the frame before the ball lands: one frame's run short.
    last_frame = 1.4 * plain.attributes.jogging_speed
    expected = reach.running - last_frame + plain.attributes.dive_range
    assert reach.diving == pytest.approx(expected)
    early = fielder_reach(plain, Position.CENTER_FIELD, lockout + 5)
    assert early.diving == early.running  # too little time after the lockout to dive
    slider = next(c for c in Character if _has_sliding_catch(c))
    sliding = fielder_reach(slider, Position.CENTER_FIELD, lockout + 100)
    assert sliding.diving > sliding.running + slider.attributes.dive_range


def test_negative_frames_are_a_bug():
    with pytest.raises(ValueError, match="frames"):
        fielder_reach(Character.MARIO, Position.PITCHER, -1)


def test_recorded_outfield_catches_are_within_reach():
    # Across ~15,700 local fly-ball catches, 99.4% were inside the reach.
    checked = 0
    for path in sorted(STAT_FILES.rglob("*.json")):
        game = read_game(path)
        for event in game.events:
            fielding, contact = event.fielding, event.contact
            if event.result not in (AtBatResult.CAUGHT, AtBatResult.CAUGHT_LINE_DRIVE):
                continue
            if fielding is None or contact is None or contact.hang_frames is None:
                continue
            if fielding.position not in (
                Position.LEFT_FIELD,
                Position.CENTER_FIELD,
                Position.RIGHT_FIELD,
            ):
                continue
            if contact.max_height < 5:
                continue
            reach = fielder_reach(
                fielding.spot.character,
                fielding.position,
                contact.hang_frames,
                is_superstar=fielding.spot.is_superstar,
            )
            assert reach.reaches(fielding.location), (path.name, event.number)
            checked += 1
    assert checked > 10

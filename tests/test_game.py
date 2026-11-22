"""The game model's own behaviour: versions, derived properties, hashing."""

from __future__ import annotations

import dataclasses
from collections import Counter
from pathlib import Path

import pytest

from pyrio import (
    AtBatResult,
    Bases,
    BattingLine,
    Character,
    Game,
    OutType,
    PitchingLine,
    Side,
    StealType,
    Version,
    read_game,
)

FIXTURES = Path(__file__).parent / "fixtures"
GAME_PATH = FIXTURES / "20260618T191655_SpiceOrange-Vs-MattGree_3896251267.json"


@pytest.fixture(scope="module")
def game() -> Game:
    return read_game(GAME_PATH)


# --- Version ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("text", "version"),
    [
        ("2.2.0", Version(2, 2, 0)),
        ("2.0", Version(2, 0, 0)),
        ("0.1.7.a", Version(0, 1, 7, "a")),
        ("0.1.7a", Version(0, 1, 7, "a")),
        (" 1.9.6 ", Version(1, 9, 6)),
    ],
)
def test_version_parse(text: str, version: Version):
    assert Version.parse(text) == version


@pytest.mark.parametrize("text", ["", "Pre 0.1.7", "2", "v2.2.0", "2.2.0-beta1"])
def test_version_parse_rejects(text: str):
    with pytest.raises(ValueError, match="not a Project Rio version"):
        Version.parse(text)


def test_version_order_and_str():
    assert Version(0, 1, 7) < Version(0, 1, 7, "a") < Version(0, 1, 8) < Version(1, 9, 1)
    assert Version(2, 3, 0) > Version(2, 2, 9)
    assert sorted([Version(2, 0, 0), Version(0, 1, 9), Version(1, 9, 6)])[0] == Version(0, 1, 9)
    assert str(Version(0, 1, 7, "a")) == "0.1.7.a"
    assert str(Version(2, 2, 0)) == "2.2.0"


# --- Game and teams ------------------------------------------------------------------------


def test_game_header(game: Game):
    assert game.id == 3896251267
    assert game.version == Version(2, 2, 0)
    assert game.away.player == "SpiceOrange"
    assert game.home.player == "MattGree"
    assert (game.away.score, game.home.score) == (9, 12)
    assert game.team(Side.AWAY) is game.away
    assert game.team(Side.HOME) is game.home
    assert game.result.winner is Side.HOME
    assert game.is_netplay
    assert not game.loaded_from_hud
    assert game.average_ping_ms == 19
    assert game.lag_spikes == 18


def test_team_lines_sum_the_roster(game: Game):
    team = game.home
    assert team.batting == sum((s.batting for s in team.roster), BattingLine())
    assert team.pitching == sum((s.pitching for s in team.roster), PitchingLine())
    assert team.batting.rbi == 12
    assert team.pitching.outs_pitched == 27
    assert team.captain.character is Character.MARIO


def test_captain_needs_one(game: Game):
    roster = tuple(dataclasses.replace(s, is_captain=False) for s in game.away.roster)
    team = dataclasses.replace(game.away, roster=roster)
    with pytest.raises(ValueError, match="no captain"):
        _ = team.captain


def test_roster_spots_are_hashable_dict_keys(game: Game):
    at_bats = Counter(event.batter_spot for event in game.events if event.is_last_pitch)
    assert set(at_bats) <= set(game.away.roster) | set(game.home.roster)
    assert sum(at_bats.values()) == sum(1 for e in game.events if e.is_last_pitch)
    leadoff = game.away.roster[0]
    assert hash(leadoff) == hash(dataclasses.replace(leadoff, outs_per_position={}))


# --- Events and states ------------------------------------------------------------------------


def test_event_shortcuts(game: Game):
    first = game.events[0]
    assert first.batter is first.batter_spot.character is Character.DK
    assert first.pitcher is Character.WALUIGI
    assert first.catcher is first.catcher_spot.character
    assert first.is_first_pitch
    assert first.is_last_pitch
    assert first.is_hit
    assert first.result is AtBatResult.SINGLE
    second = game.events[1]
    assert second.state.bases == Bases.FIRST
    assert not second.is_last_pitch
    assert not second.is_hit


def test_game_state(game: Game):
    state = game.events[-1].state
    assert state.score(Side.AWAY) == state.away_score
    assert state.stars(Side.HOME) == state.home_stars
    assert state.leader is Side.HOME
    assert game.events[0].state.leader is None


def test_runner(game: Game):
    runner = game.events[1].runners[1]
    assert runner.spot is game.away.roster[0]
    assert runner.start_base == 1
    assert runner.end_base == 1
    assert runner.bases_advanced == 0
    assert not runner.scored
    assert not runner.is_out
    assert runner.out_base is None
    assert runner.steal is StealType.NONE
    assert runner.out_type is OutType.NONE


def test_half_innings(game: Game):
    halves = game.half_innings
    assert [(h.inning, h.batting_side) for h in halves[:3]] == [
        (1, Side.AWAY),
        (1, Side.HOME),
        (2, Side.AWAY),
    ]
    assert halves[0].is_top
    assert not halves[1].is_top
    assert halves[2].runs == 6
    assert sum(len(h.events) for h in halves) == len(game.events)
    assert [e for h in halves for e in h.events] == list(game.events)


def test_lead_changes(game: Game):
    changes = game.lead_changes
    assert [e.state.batting_side for e in changes] == [Side.AWAY, Side.HOME]
    for event in changes:
        assert event.is_lead_change
        side = event.state.batting_side
        assert event.state.score(side) <= event.state.score(side.other)
        assert event.state.score(side) + event.runs > event.state.score(side.other)

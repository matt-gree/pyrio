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
    MoonshotStatus,
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


def test_inning_runs_is_the_line_score(game: Game):
    away, home = game.inning_runs(Side.AWAY), game.inning_runs(Side.HOME)
    assert len(away) == len(home) == game.innings_played
    assert sum(r or 0 for r in away) == game.away.score
    assert sum(r or 0 for r in home) == game.home.score


# --- At-bats ----------------------------------------------------------------------------

STAT_FILES = sorted((FIXTURES / "stat_files").rglob("*.json"))


def test_at_bats(game: Game):
    at_bats = game.at_bats
    assert len(at_bats) == 90
    first, second = at_bats[0], at_bats[1]
    assert first.events == (game.events[0],)
    assert first.final is game.events[0]
    assert first.batter is Character.DK
    assert first.batter_spot is game.away.roster[first.batter_spot.index]
    assert (first.inning, first.batting_side) == (1, Side.AWAY)
    assert first.result is AtBatResult.SINGLE
    assert first.is_complete
    assert second.events == game.events[1:3]
    assert second.state is game.events[1].state
    assert second.state.bases == Bases.FIRST
    assert second.pitches == 2
    assert second.result is AtBatResult.CAUGHT
    assert sum(ab.runs for ab in at_bats) == game.away.score + game.home.score
    assert sum(ab.rbi for ab in at_bats) == sum(e.rbi for e in game.events)


def test_at_bat_pitches_leave_out_pitchless_events(game: Game):
    (at_bat,) = [ab for ab in game.at_bats if game.events[47] in ab.events]
    assert game.events[47].pitch is None
    assert at_bat.pitches == len(at_bat.events) - 1


def test_star_chance_at_bats(game: Game):
    star_chances = [ab for ab in game.at_bats if ab.is_star_chance]
    assert len(star_chances) == 12
    assert star_chances[0].batter is Character.PETEY
    assert star_chances[0].pitches == 4


def test_half_inning_at_bats_make_up_the_game(game: Game):
    assert [ab for h in game.half_innings for ab in h.at_bats] == list(game.at_bats)


def test_outs_on_the_bases_can_leave_an_at_bat_unfinished():
    game = read_game(
        FIXTURES / "stat_files/2.0.2/decoded.20231114T143512_Flatbread-Vs-MattGree_153176676.json"
    )
    unfinished = [ab for ab in game.at_bats if not ab.is_complete]
    assert len(unfinished) == 1
    (at_bat,) = unfinished
    assert at_bat.result is AtBatResult.NONE
    assert (at_bat.inning, at_bat.batting_side, at_bat.pitches) == (1, Side.AWAY, 5)
    # Both runners were caught stealing with one out, ending the half mid-count.
    assert at_bat.final.state.outs == 1
    assert [r.start_base for r in at_bat.final.runners if r.out_type is OutType.TAG] == [1, 3]
    following = game.at_bats[game.at_bats.index(at_bat) + 1]
    assert (following.inning, following.batting_side) == (1, Side.HOME)


def test_at_bats_partition_every_fixture():
    assert STAT_FILES
    for path in STAT_FILES:
        game = read_game(path)
        at_bats = game.at_bats
        assert [e for ab in at_bats for e in ab.events] == list(game.events), path
        for ab in at_bats:
            assert ab.events, path
            assert all(e.result is AtBatResult.NONE for e in ab.events[:-1]), path
            assert {(e.batter_spot, e.state.inning, e.state.batting_side) for e in ab.events} == {
                (ab.batter_spot, ab.inning, ab.batting_side)
            }, path
            # The game sets a star chance as the at-bat begins and holds it.
            assert {e.state.is_star_chance for e in ab.events} == {ab.is_star_chance}, path


# --- Event predicates -------------------------------------------------------------------


def test_event_predicates(game: Game):
    assert sum(e.is_star_swing for e in game.events) == 20
    assert not any(e.is_star_pitch for e in game.events)
    assert [e.number for e in game.events if e.has_bobble] == [154, 201, 205]
    assert [e.number for e in game.events if e.has_wall_jump] == [176]
    pitchless = game.events[47]
    assert not any(
        (
            pitchless.is_star_pitch,
            pitchless.is_star_swing,
            pitchless.is_moonshot,
            pitchless.has_bobble,
            pitchless.has_wall_jump,
        )
    )


def test_star_pitches_match_the_box_score():
    found = 0
    for path in STAT_FILES:
        game = read_game(path)
        for team in (game.away, game.home):
            thrown = sum(e.is_star_pitch for e in game.events if e.pitcher_spot.side is team.side)
            assert thrown == team.pitching.star_pitches_thrown, path
            found += thrown
    assert found


def test_is_moonshot(game: Game):
    event = next(e for e in game.events if e.contact is not None)
    assert event.contact is not None
    assert not event.is_moonshot
    for status, expected in (
        (MoonshotStatus.MOONSHOT, True),
        (MoonshotStatus.FAILED, False),
        (MoonshotStatus.NONE, False),
    ):
        contact = dataclasses.replace(event.contact, moonshot=status)
        assert dataclasses.replace(event, contact=contact).is_moonshot is expected

"""Responses decode into models: each endpoint against its contract fixture."""

from __future__ import annotations

import dataclasses
import math
from datetime import UTC, datetime
from typing import TYPE_CHECKING

import pytest
import respx

from pyrio import (
    AtBatResult,
    Bases,
    BattingLine,
    Character,
    ContactType,
    Hand,
    InputDirection,
    ManualSelect,
    OutType,
    PitchingLine,
    Position,
    Side,
    Stadium,
    StealType,
    SwingType,
    TeamName,
)
from pyrio.sim import simulate_hit
from pyrio.web import (
    APIResponseError,
    CommunityKind,
    ContactLine,
    RioClient,
    TagKind,
    TagSetKind,
)

if TYPE_CHECKING:
    from collections.abc import Iterator

BASE = "https://api.projectrio.app"


@pytest.fixture
def mock() -> Iterator[respx.MockRouter]:
    with respx.mock(base_url=BASE, assert_all_called=False) as router:
        yield router


@pytest.fixture
def rio() -> Iterator[RioClient]:
    with RioClient(api_key="test-key") as client:
        yield client


# --- games --------------------------------------------------------------------


def test_games_decode_fully(mock, rio, contract):
    mock.get("/games/").respond(json=contract("games.json"))
    first, second = rio.games(include_linescore=True, include_scoring_plays=True)

    assert first.game_id == 3896251267
    assert first.stadium is Stadium.BOWSER_CASTLE
    assert first.start_time == datetime(2026, 6, 18, 18, 16, 55, tzinfo=UTC)
    assert first.end_time.tzinfo is UTC
    assert first.away.player == "SpiceOrange"
    assert first.away.captain is Character.BOWSER_JR
    assert first.home.captain is Character.MARIO
    assert first.home.roster[0] is Character.MARIO
    assert len(first.home.roster) == 9
    assert all(isinstance(c, Character) for c in first.away.roster)
    assert (first.away.score, first.home.score) == (9, 12)
    assert first.winner is Side.HOME
    assert first.team(Side.AWAY) is first.away
    assert first.tag_set_id == 198
    assert first.ratings is not None
    assert (first.ratings.winner_before, first.ratings.winner_after) == (1612, 1621)

    assert first.linescore is not None
    assert first.linescore.away == (0, 2, 0, 1, 0, 3, 0, 3, 0)
    assert first.linescore.home[-1] is None  # the box score's "X"
    assert first.scoring_plays is not None
    play = first.scoring_plays[0]
    assert play.batting_side is Side.HOME
    assert play.result is AtBatResult.HOME_RUN
    assert play.batter is Character.MARIO
    assert play.runs == 1
    batter = play.runners[0]
    assert batter is not None
    assert batter.out_type is OutType.NONE
    assert batter.steal is StealType.NONE
    assert play.runners[1:] == (None, None, None)

    # No game history: no tag set, no ratings.
    assert second.tag_set_id is None
    assert second.ratings is None
    assert second.scoring_plays == ()


def test_optional_game_sections_are_none_when_not_requested(mock, rio, contract):
    mock.get("/games/").respond(json=contract("games_plain.json"))
    (game,) = rio.games()
    assert game.linescore is None
    assert game.scoring_plays is None


def test_empty_games(mock, rio):
    mock.get("/games/").respond(json={"games": []})
    assert rio.games() == []


def test_missing_required_key_names_endpoint_and_present_keys(mock, rio, contract):
    body = contract("games_plain.json")
    del body["games"][0]["stadium"]
    mock.get("/games/").respond(json=body)
    with pytest.raises(APIResponseError, match=r"/games/.*'stadium'.*present: \[") as info:
        rio.games()
    assert "home_captain" in str(info.value)


def test_unknown_extra_keys_are_ignored(mock, rio, contract):
    body = contract("games_plain.json")
    body["games"][0]["brand_new_field"] = {"anything": 1}
    body["server_version"] = "2.0"
    mock.get("/games/").respond(json=body)
    assert rio.games()[0].game_id == 3896251267


def test_wrong_type_is_a_response_error(mock, rio, contract):
    body = contract("games_plain.json")
    body["games"][0]["home_score"] = "12"
    mock.get("/games/").respond(json=body)
    with pytest.raises(APIResponseError, match="home_score"):
        rio.games()


def test_unknown_code_is_a_response_error(mock, rio, contract):
    body = contract("games_plain.json")
    body["games"][0]["stadium"] = 99
    mock.get("/games/").respond(json=body)
    with pytest.raises(APIResponseError, match="Stadium"):
        rio.games()


def test_missing_roster_slot_is_a_response_error(mock, rio, contract):
    body = contract("games_plain.json")
    body["games"][0]["away_roster"][4] = None
    mock.get("/games/").respond(json=body)
    with pytest.raises(APIResponseError, match=r"away_roster\[4\]"):
        rio.games()


# --- stats --------------------------------------------------------------------


def test_stats_without_grouping(mock, rio, contract):
    mock.get("/stats/").respond(json=contract("stats.json"))
    (row,) = rio.stats()
    assert (row.game_id, row.user, row.roster_spot, row.character) == (None, None, None, None)
    assert row.batting == BattingLine(
        at_bats=20,
        hits=7,
        singles=4,
        doubles=2,
        triples=0,
        home_runs=1,
        walks=2,
        hit_by_pitch=1,
        strikeouts=3,
        sac_flies=1,
        rbi=5,
        stolen_bases=0,
        star_hits=1,
    )
    assert row.batting.avg == pytest.approx(7 / 20)
    assert row.pitching == PitchingLine(
        batters_faced=30,
        outs_pitched=21,
        hits_allowed=8,
        runs_allowed=4,
        walks=2,
        hit_by_pitch=1,
        strikeouts=6,
        pitches_thrown=95,
        star_pitches_thrown=2,
    )
    assert (row.balls_thrown, row.strikes_thrown) == (30, 50)
    assert row.contact is not None
    assert row.contact.foul_contacts == 6
    assert row.contact.double_plays == 1
    assert row.contact.hits == 7
    assert row.contact_by_swing is None
    assert row.runs_scored is None
    assert row.pitcher_wins is None
    assert row.fielding is not None
    assert row.fielding.pitches_at[Position.CENTER_FIELD] == 10
    assert row.fielding.outs_at[Position.PITCHER] == 0
    assert row.fielding.sliding_catches == 1
    assert row.record is not None
    assert (row.record.wins, row.record.losses, row.record.games) == (4, 2, 6)


def test_stats_by_character(mock, rio, contract):
    mock.get("/stats/").respond(json=contract("stats_by_character.json"))
    rows = {row.character: row for row in rio.stats(by_character=True)}
    assert set(rows) == {Character.MARIO, Character.BABY_MARIO, Character.BOO}
    assert rows[Character.BABY_MARIO].batting is not None
    assert rows[Character.BABY_MARIO].batting.at_bats == 40
    # Queries that write no row for a group leave their keys out; that's zero.
    boo = rows[Character.BOO]
    assert boo.contact == ContactLine()
    assert (boo.balls_thrown, boo.strikes_thrown) == (0, 0)
    assert boo.fielding is not None
    assert boo.fielding.bobbles == 0


def test_stats_by_user_and_swing(mock, rio, contract):
    mock.get("/stats/").respond(json=contract("stats_by_user_swing.json"))
    rows = rio.stats(
        by_user=True,
        by_swing=True,
        include_runs_scored=True,
        include_pitcher_wins=True,
        exclude_fielding=True,
        exclude_record=True,
    )
    by_user = {row.user: row for row in rows}
    matt = by_user["MattGree"]
    assert matt.character is None
    assert matt.contact_by_swing is not None
    assert set(matt.contact_by_swing) == {
        SwingType.NONE,
        SwingType.SLAP,
        SwingType.CHARGE,
        SwingType.STAR,
    }
    assert matt.contact_by_swing[SwingType.STAR].home_runs == 1
    assert matt.contact is not None
    assert matt.contact == sum(matt.contact_by_swing.values(), ContactLine())
    assert matt.runs_scored == 3
    assert matt.pitcher_wins == 4
    assert matt.batting is not None
    assert matt.batting.at_bats == 20
    assert matt.fielding is None
    assert matt.record is None


def test_stats_hand_splits_become_rows(mock, rio, contract):
    mock.get("/stats/").respond(json=contract("stats_by_game_spot_hand.json"))
    rows = rio.stats(by_game=True, by_roster_spot=True, by_batting_hand=True, by_fielding_hand=True)
    assert {row.game_id for row in rows} == {3896251267}
    spot0 = [row for row in rows if row.roster_spot == 0]
    batting = [row for row in spot0 if row.batting_hand is not None]
    pitching = [row for row in spot0 if row.fielding_hand is not None]
    rest = [row for row in spot0 if row.batting_hand is None and row.fielding_hand is None]
    assert [row.batting_hand for row in batting] == [Hand.RIGHT]
    assert batting[0].batting is not None
    assert batting[0].pitching is None
    assert [row.fielding_hand for row in pitching] == [Hand.LEFT]
    assert pitching[0].batting is None
    assert len(rest) == 1
    assert rest[0].fielding is not None
    assert rest[0].record is not None
    assert rest[0].batting is None


def test_stats_with_flags_the_response_lacks_fails_clearly(mock, rio, contract):
    # A response nested by character, read as if ungrouped: the decoder says so
    # rather than returning empty rows.
    mock.get("/stats/").respond(json=contract("stats_by_character.json"))
    with pytest.raises(APIResponseError, match="by_\\* flags"):
        rio.stats()


def test_stats_era_is_zero_until_the_server_sends_earned_runs(mock, rio, contract):
    mock.get("/stats/").respond(json=contract("stats.json"))
    (row,) = rio.stats()
    assert row.pitching is not None
    assert row.pitching.earned_runs == 0
    assert row.pitching.era == 0
    assert not math.isnan(row.pitching.whip)


def test_stats_read_earned_runs_once_the_server_sends_them(mock, rio, contract):
    data = contract("stats.json")
    data["Stats"]["Pitching"] |= {"earned_runs": 3, "homeruns_allowed": 1}
    data["Stats"]["Batting"]["successful_bunts"] = 2
    mock.get("/stats/").respond(json=data)
    (row,) = rio.stats()
    assert row.pitching is not None
    assert row.batting is not None
    assert (row.pitching.earned_runs, row.pitching.home_runs_allowed) == (3, 1)
    assert row.pitching.era == row.pitching.era_over(9) > 0
    assert row.batting.bunts == 2


# --- events, star chances, landing data (section 4a) --------------------------


def test_event_ids_read_the_bare_game_keyed_object(mock, rio, contract):
    # /events/ returns {game_id: {event_num: event_id}}, with no "events" key.
    # pyrio <1.0 looked for "Events"/"events" and always returned nothing.
    mock.get("/events/").respond(json=contract("events.json"))
    refs = rio.event_ids(tags=["S13 Superstars Off"])
    assert len(refs) == 4
    assert [(r.game_id, r.event_number) for r in refs] == [
        (1189820580, 0),
        (3896251267, 0),
        (3896251267, 1),
        (3896251267, 10),
    ]
    assert refs[-1].event_id == 5550011


def test_event_ids_empty(mock, rio):
    mock.get("/events/").respond(json={})
    assert rio.event_ids() == []


def test_star_chances_read_the_data_key(mock, rio, contract):
    # /star_chances/ returns {"Data": [...]}. pyrio <1.0 looked for
    # "Star Chances"/"star_chances" and always returned nothing.
    mock.get("/star_chances/").respond(json=contract("star_chances.json"))
    (row,) = rio.star_chances()
    assert row.star_chances == 18
    assert row.plate_appearances == 140
    assert (row.pitcher_wins, row.batter_wins) == (11, 7)
    assert row.inning is None
    assert row.batting_side is None


def test_star_chances_by_inning(mock, rio, contract):
    mock.get("/star_chances/").respond(json=contract("star_chances_by_inning.json"))
    top, bottom = rio.star_chances(by_inning=True)
    assert (top.inning, top.batting_side) == (1, Side.AWAY)
    assert (bottom.batting_side, bottom.star_chances) == (Side.HOME, 3)


def test_star_chances_and_landing_data_empty_object_is_no_rows(mock, rio):
    # Both routes return a bare {} when no event matched.
    mock.get("/star_chances/").respond(json={})
    mock.get("/landing_data/").respond(json={})
    assert rio.star_chances() == []
    assert rio.landing_data() == []


def test_star_chances_missing_data_key_raises(mock, rio):
    mock.get("/star_chances/").respond(json={"Star Chances": []})
    with pytest.raises(APIResponseError, match=r"'Data'.*present: \['Star Chances'\]"):
        rio.star_chances()


def test_landing_data(mock, rio, contract):
    mock.get("/landing_data/").respond(json=contract("landing_data.json"))
    homer, caught = rio.landing_data()
    assert homer.result is AtBatResult.HOME_RUN
    assert homer.batter is Character.MARIO
    assert homer.fielder is None
    assert homer.batting_hand is Hand.RIGHT  # a boolean column: false is right
    assert homer.pitching_hand is Hand.LEFT
    assert homer.swing is SwingType.SLAP
    assert homer.contact_type is ContactType.PERFECT
    assert homer.input_direction == InputDirection.LEFT | InputDirection.UP
    assert homer.fielder_position is None
    assert homer.manual_select is None
    # Rio web stores the angles in each other's columns; the decoder swaps back.
    assert (homer.vertical_angle, homer.horizontal_angle) == (412, 1093)
    assert caught.fielder is Character.DIDDY
    assert caught.fielder_position is Position.CENTER_FIELD
    assert caught.manual_select is ManualSelect.CLOSEST_TO_BALL
    assert caught.contact_type is ContactType.SOUR_RIGHT
    assert caught.fielder_location is not None


def test_a_landing_row_rebuilds_its_swing(mock, rio, contract):
    mock.get("/landing_data/").respond(json=contract("landing_data.json"))
    homer, _ = rio.landing_data()
    inputs = homer.hit_inputs(stadium=Stadium.PEACH_GARDEN)
    assert (inputs.batter, inputs.swing, inputs.rng) == (
        Character.MARIO,
        SwingType.SLAP,
        homer.rng,
    )
    assert (inputs.batter_x, inputs.ball_x) == (homer.bat_location[0], homer.location[0])
    simulate_hit(inputs)  # the row has everything the simulation needs
    star = dataclasses.replace(homer, swing=SwingType.STAR)
    with pytest.raises(ValueError, match="star swing"):
        star.hit_inputs(stadium=Stadium.PEACH_GARDEN)
    bunt = dataclasses.replace(homer, swing=SwingType.BUNT)
    simulate_hit(bunt.hit_inputs(stadium=Stadium.PEACH_GARDEN))
    unrecorded = dataclasses.replace(homer, swing=SwingType.NONE)
    with pytest.raises(ValueError, match="no swing type"):
        unrecorded.hit_inputs(stadium=Stadium.PEACH_GARDEN)


# --- live games and reference data ----------------------------------------------


def test_live_games(mock, rio, contract):
    mock.get("/populate_db/ongoing_game/").respond(json=contract("ongoing_games.json"))
    (game,) = rio.live_games()
    assert game.stadium is Stadium.BOWSER_CASTLE
    assert game.batting_side is Side.HOME
    assert game.bases == Bases.FIRST | Bases.THIRD
    assert game.home.roster[0] is Character.MARIO
    assert game.away.inning_runs == (0, 2, 0, 1)
    assert game.is_star_chance is False
    assert game.away.captain_spot == 0
    assert game.home.captain is Character.MARIO
    assert game.away.logo is TeamName.BOWSER_BLUE_SHELLS
    assert game.home.positions[2] is Position.FIRST_BASE
    assert game.home.fielder(Position.PITCHER) == 0
    assert game.away.is_superstar == (False,) * 9
    assert game.runner_spots == (1, None, 0)
    assert game.batting_hand is Hand.RIGHT
    assert game.batter is game.home.roster[2]
    assert game.pitcher is game.away.roster[0]
    assert game.chemistry_links_on_base == 1
    assert game.batter_line is None
    assert game.pitcher_line is None


def test_live_game_stat_lines(mock, rio, contract):
    body = contract("ongoing_games.json")
    (raw,) = body["ongoing_games"]
    raw["batter_stats"] = {"At Bats": 3, "Hits": 2, "Homeruns": 1, "RBI": 2}
    raw["pitcher_stats"] = {"Batters Faced": 12, "Outs Pitched": 9, "Strikeouts": 3}
    raw["away_fielding_positions"][4] = 255
    mock.get("/populate_db/ongoing_game/").respond(json=body)
    (game,) = rio.live_games()
    assert game.batter_line == BattingLine(at_bats=3, hits=2, home_runs=1, rbi=2)
    assert game.pitcher_line == PitchingLine(batters_faced=12, outs_pitched=9, strikeouts=3)
    assert game.away.positions[4] is None


def test_tag_sets(mock, rio, contract):
    mock.post("/tag_set/list").respond(json=contract("tag_sets.json"))
    mock.get("/tag_set/198").respond(json=contract("tag_set.json"))
    (listed,) = rio.tag_sets.list()
    assert listed.kind is TagSetKind.SEASON
    assert listed.community_kind is CommunityKind.OFFICIAL
    assert listed.start_time.tzinfo is UTC
    assert listed.tag_ids == (1, 2, 3, 4)
    gecko = listed.tags[3]
    assert gecko.kind is TagKind.GECKO_CODE
    assert gecko.gecko_code == "04000000 00000000\n"
    single = rio.tag_sets.get(198)
    assert single.community_kind is None
    assert single.name == listed.name


def test_tags_users_ladder(mock, rio, contract):
    mock.post("/tag/list").respond(json=contract("tags.json"))
    mock.get("/user/all/").respond(json=contract("users.json"))
    mock.post("/tag_set/ladder/").respond(json=contract("ladder.json"))
    tags = rio.tags.list()
    assert [t.kind for t in tags][:2] == [TagKind.COMMUNITY, TagKind.COMPONENT]
    assert tags[0].gecko_code is None
    users = rio.users.list()
    assert {u.id: u.name for u in users} == {1: "MattGree", 2: "SpiceOrange", 17: "Zed"}
    ladder = rio.tag_sets.ladder("S13 Superstars Off")
    assert [row.user for row in ladder] == ["Zed", "MattGree", "SpiceOrange"]
    assert ladder[2].ties == 1


def test_ladder_games(mock, rio, contract):
    mock.get("/ladder/games/").respond(json=contract("ladder_games.json"))
    played, manual = rio.tag_sets.ladder_games(["S13 Superstars Off"])
    assert played.away_captain is Character.BOWSER_JR
    assert played.ratings.winner_after == 1621
    assert manual.game_id is None
    assert manual.stadium is None
    assert manual.ratings.winner_after is None


def test_communities_and_members(mock, rio, contract):
    mock.post("/community/list").respond(json=contract("communities.json"))
    mock.post("/community/members").respond(json=contract("members.json"))
    mock.post("/community/key").respond(json=contract("community_key.json"))
    official, nnl = rio.communities.list()
    assert official.kind is CommunityKind.OFFICIAL
    assert nnl.is_private is True
    assert nnl.url is None
    admin, member = rio.communities.members("Project Rio")
    assert admin.is_admin
    assert not admin.is_banned  # banned: null is false
    assert member.key is None
    keyed = rio.communities.generate_key("Project Rio")
    assert keyed.key == "AbCd"
    assert keyed.key_created_at is not None

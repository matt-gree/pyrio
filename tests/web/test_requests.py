"""Requests go out the way Rio web's route code reads them (ProjectRio-web d4bf233).

Each section 4a request bug in pyrio <1.0 has a test here that fails if it
comes back: flags as ``'1'``, the parameter names the server reads, list types
where it expects lists, and one HTTP call per method.
"""

from __future__ import annotations

import inspect
import json
import re
from datetime import UTC, datetime, timedelta, timezone
from pathlib import Path
from typing import TYPE_CHECKING, Any

import httpx
import pytest
import respx

from pyrio import AtBatResult, Character, ContactType, Hand, Position, Side, Stadium, SwingType
from pyrio.web import RioClient, TagKind, TagSetKind, _encode

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


def query(route: respx.Route) -> list[tuple[str, str]]:
    return list(route.calls.last.request.url.params.multi_items())


def body(route: respx.Route) -> Any:
    return json.loads(route.calls.last.request.content)


# --- flags (section 4a: "Flags never reach the server") ---------------------------


def test_stats_flags_are_sent_as_1_with_the_servers_names(mock, rio):
    route = mock.get("/stats/").respond(json={"Stats": {}})
    rio.stats(
        by_game=True,
        by_user=True,
        by_roster_spot=True,
        by_character=True,
        by_batting_hand=True,
        by_fielding_hand=True,
        by_swing=True,
        exclude_fouls=True,
        exclude_batting=True,
        exclude_pitching=True,
        exclude_fielding=True,
        exclude_record=True,
        include_pitcher_wins=True,
        include_runs_scored=True,
    )
    sent = dict(query(route))
    flags = {
        "by_game",
        "by_user",
        "by_roster_order",
        "by_char",
        "by_batting_hand",
        "by_fielding_hand",
        "by_swing",
        "exclude_nonfair",
        "exclude_batting",
        "exclude_pitching",
        "exclude_fielding",
        "exclude_misc",
        "include_pitcher_wins",
        "include_runs_scored",
    }
    assert {name: sent[name] for name in flags} == dict.fromkeys(flags, "1")


def test_flags_that_are_off_are_not_sent(mock, rio):
    route = mock.get("/stats/").respond(json={"Stats": {}})
    rio.stats()
    assert [name for name, _ in query(route) if name.startswith(("by_", "exclude_"))] == []
    assert "True" not in str(route.calls.last.request.url)


def test_games_include_flags_are_1_and_include_teams_is_gone(mock, rio):
    route = mock.get("/games/").respond(json={"games": []})
    rio.games(include_linescore=True, include_scoring_plays=True)
    sent = dict(query(route))
    assert sent["include_linescore"] == "1"
    assert sent["include_scoring_plays"] == "1"  # pyrio <1.0 couldn't send it
    assert "include_teams" not in sent  # the server never read it


def test_event_flags(mock, rio):
    route = mock.get("/events/").respond(json={})
    rio.event_ids(only_star_chances=True, users_as_batter=True, users_as_pitcher=True)
    sent = dict(query(route))
    assert (sent["star_chance"], sent["users_as_batter"], sent["users_as_pitcher"]) == (
        "1",
        "1",
        "1",
    )


def test_star_chances_by_inning_uses_its_own_truthy_spelling(mock, rio):
    route = mock.get("/star_chances/").respond(json={})
    rio.star_chances(by_inning=True)
    assert dict(query(route))["by_inning"] == "true"


def test_limit_games(mock, rio):
    route = mock.get("/games/").respond(json={"games": []})
    rio.games()
    assert dict(query(route))["limit_games"] == "50"
    rio.games(limit_games=None)
    assert dict(query(route))["limit_games"] == "False"  # pyrio <1.0 got a 400 for True
    rio.games(limit_games=7)
    assert dict(query(route))["limit_games"] == "7"
    with pytest.raises(ValueError, match="limit"):
        rio.games(limit_games=-1)


# --- parameter names (section 4a: "Parameter names the server never reads") -------


def test_landing_data_sends_events_and_games(mock, rio):
    route = mock.get("/landing_data/").respond(json={})
    rio.landing_data(event_ids=[11, 12], game_ids=[3])
    sent = query(route)
    assert ("events", "11") in sent
    assert ("events", "12") in sent
    assert ("games", "3") in sent
    names = {name for name, _ in sent}
    assert "event_list" not in names
    assert "game_list" not in names


def test_tag_list_sends_communities_and_a_types_list(mock, rio):
    route = mock.post("/tag/list").respond(json={"Tags": []})
    rio.tags.list(kinds=[TagKind.GECKO_CODE, TagKind.COMPONENT], community_ids=[1, 7])
    assert body(route) == {"Types": ["Gecko Code", "Component"], "Communities": [1, 7]}


def test_tag_set_dates_are_ints(mock, rio, contract):
    route = mock.post("/tag_set/create").respond(json=contract("tag_set.json")["Tag Set"][0])
    start = datetime(2026, 1, 1, tzinfo=UTC)
    rio.tag_sets.create(
        "S14",
        description="Season 14",
        kind=TagSetKind.SEASON,
        community="Project Rio",
        start_time=start,
        end_time=start + timedelta(days=90),
        tag_ids=[2],
    )
    sent = body(route)
    assert sent["start_date"] == 1767225600
    assert isinstance(sent["end_date"], int)
    assert sent["add_tag_ids"] == [2]
    assert sent["type"] == "Season"


def test_manual_submit_sends_no_recalc_or_rio_key(mock, rio):
    route = mock.post("/manual_submit_game/").respond(json={"game_history_id": 99})
    history_id = rio.submit_game(
        winner="MattGree",
        loser="SpiceOrange",
        winner_score=5,
        loser_score=3,
        tag_set="S13 Superstars Off",
        played_at=datetime(2026, 6, 18, tzinfo=UTC),
    )
    assert history_id == 99
    sent = body(route)
    assert "recalc" not in sent
    assert "submitter_rio_key" not in sent
    assert sent["date"] == 1781740800


def test_stats_offers_no_event_filters():
    # pyrio <1.0's StatsParameterList inherited pitcher_char, contact, inning, ...,
    # none of which /stats/ reads. Unknown arguments are now a TypeError.
    with RioClient() as rio, pytest.raises(TypeError):
        rio.stats(innings=[1])  # type: ignore[call-arg]


def test_event_filters_encode_enums_as_the_servers_ids(mock, rio):
    route = mock.get("/events/").respond(json={})
    rio.event_ids(
        pitchers=[Character.BOWSER_JR],
        batters=[Character.MARIO, Character.TOAD_B],
        fielder_positions=[Position.SHORTSTOP],
        contacts=[ContactType.PERFECT, ContactType.MISS],
        swings=[SwingType.STAR],
        batter_hands=[Hand.LEFT],
        batting_sides=[Side.HOME],
        results=[AtBatResult.HOME_RUN],
        away_scores=[0],
        home_scores=[3],
        limit_events=10,
    )
    sent = query(route)
    assert ("pitcher_char", "19") in sent
    assert ("batter_char", "0") in sent
    assert ("batter_char", "29") in sent
    assert ("fielder_pos", "5") in sent
    assert ("contact", "2") in sent
    assert ("contact", "5") in sent  # 5 is "no contact"
    assert ("swing", "3") in sent
    assert ("batter_hand", "1") in sent
    assert ("half_inning", "1") in sent
    assert ("final_result", "10") in sent
    assert ("away_score", "0") in sent
    assert ("home_score", "3") in sent
    assert ("limit_events", "10") in sent


def test_game_filters(mock, rio):
    route = mock.get("/games/").respond(json={"games": []})
    rio.games(
        tags=["S13 Superstars Off", "Stars Off"],
        users=["MattGree"],
        vs_users=["SpiceOrange"],
        captains=[Character.BABY_MARIO],
        stadiums=[Stadium.TOY_FIELD],
        start_time=datetime(2026, 1, 1, tzinfo=UTC),
        end_time=datetime(2026, 1, 1, 5, tzinfo=timezone(timedelta(hours=5))),
    )
    sent = query(route)
    assert [v for k, v in sent if k == "tag"] == ["S13 Superstars Off", "Stars Off"]
    assert ("username", "MattGree") in sent
    assert ("vs_username", "SpiceOrange") in sent
    # Names go out as typed: the whitespace stripping pyrio <1.0 did is gone,
    # since the server normalizes names itself (lower_and_remove_nonalphanumeric).
    assert ("captain", "Baby Mario") in sent
    assert ("stadium", "6") in sent
    assert ("start_time", "1767225600") in sent
    assert ("end_time", "1767225600") in sent


def test_a_bare_string_for_a_list_is_refused(rio):
    # pyrio <1.0: get_games("tag") silently returned unfiltered data.
    with pytest.raises(TypeError, match=r"tags takes a list"):
        rio.games(tags="Stars Off")  # a str is a Sequence[str], so only a runtime check catches it


def test_naive_datetimes_are_refused(rio):
    with pytest.raises(ValueError, match="timezone-aware"):
        rio.games(start_time=datetime(2026, 1, 1))


def test_raw_ids_are_refused_where_enums_are_expected(rio):
    with pytest.raises(TypeError, match="Character"):
        rio.games(captains=[7])


# --- one call per request (section 4a: "get_games() makes four HTTP calls") --------


def test_games_makes_one_call_and_writes_nothing(mock, rio, contract, tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    mock.get("/games/").respond(json=contract("games.json"))
    rio.games(include_linescore=True, include_scoring_plays=True)
    assert len(mock.calls) == 1
    assert list(Path(tmp_path).iterdir()) == []


def test_every_method_makes_exactly_one_call(mock, rio, contract):
    mock.get("/stats/").respond(json=contract("stats.json"))
    mock.get("/events/").respond(json=contract("events.json"))
    mock.get("/landing_data/").respond(json=contract("landing_data.json"))
    mock.get("/star_chances/").respond(json=contract("star_chances.json"))
    for read in (rio.stats, rio.event_ids, rio.landing_data, rio.star_chances):
        before = len(mock.calls)
        read()
        assert len(mock.calls) == before + 1, read.__name__


# --- paths, as the server spells them -------------------------------------------

# Every route this client calls, with the server's own trailing slash. A path
# without its slash costs a 308 (with the credential re-sent) or a 404.
SERVER_ROUTES = {
    "/games/",
    "/stats/",
    "/events/",
    "/landing_data/",
    "/star_chances/",
    "/ladder/games/",
    "/populate_db/ongoing_game/",
    "/delete_game/",
    "/manual_submit_game/",
    "/login/",
    "/api_key/register/",
    "/api_key/reset/",
    "/user/all/",
    "/user/community/",
    "/user/community/sponsor/",
    "/user_group/add_user",
    "/user_group/remove_user",
    "/user_group/check_for_member",
    "/user_group/members",
    "/community/create",
    "/community/list",
    "/community/join",
    "/community/leave",
    "/community/invite",
    "/community/members",
    "/community/tags",
    "/community/manage",
    "/community/sponsor",
    "/community/key",
    "/community/update",
    "/tag/create",
    "/tag/update",
    "/tag/list",
    "/tag_set/create",
    "/tag_set/update",
    "/tag_set/delete",
    "/tag_set/list",
    "/tag_set/ladder/",
}


def test_every_encoded_path_is_a_server_route():
    source = inspect.getsource(_encode)
    paths = set(re.findall(r'"(/[a-z_/]+)"', source)) - {"/"}
    assert paths, "found no paths: the scan is broken"
    assert sorted(paths - SERVER_ROUTES) == []
    assert sorted(SERVER_ROUTES - paths) == []


# --- credentials ------------------------------------------------------------------


def test_api_key_goes_in_the_authorization_header(mock):
    route = mock.get("/games/").respond(json={"games": []})
    with RioClient(api_key="secret") as rio:
        rio.games()
    request = route.calls.last.request
    assert request.headers["Authorization"] == "ApiKey secret"
    assert "secret" not in str(request.url)


def test_management_bodies(mock, rio):
    create = mock.post("/community/create").respond(
        json={"community_name": "NNL", "private": True, "active_url": None}
    )
    manage = mock.post("/community/manage").respond(json={"members": []})
    assert rio.communities.create("NNL", description="d", private=True) is None
    assert body(create) == {
        "community_name": "NNL",
        "type": "Unofficial",
        "private": 1,  # the server compares `== 1`
        "global_link": 0,
        "desc": "d",
    }
    rio.communities.ban_members("NNL", ["Zed"])
    assert body(manage) == {
        "community_name": "NNL",
        "user_list": [{"username": "Zed", "ban": True}],
    }


def test_tag_set_list_body(mock, rio, contract):
    route = mock.post("/tag_set/list").respond(json=contract("tag_sets.json"))
    rio.tag_sets.list(active_only=True, community_ids=[])
    assert body(route) == {"Active": "true"}  # an empty Communities list is a 409


def test_delete_game_accepts_a_plain_text_answer(mock, rio):
    route = mock.post("/delete_game/").respond(text="Game deleted")
    assert rio.delete_game(3896251267) is None
    assert body(route) == {"game_id": 3896251267}


def test_request_json_is_the_escape_hatch(mock, rio):
    route = mock.get("/characters/").respond(json={"characters": []})
    assert rio.request_json("GET", "/characters/", params={"name": ["Baby Mario", "Mario"]}) == {
        "characters": []
    }
    assert query(route) == [("name", "Baby Mario"), ("name", "Mario")]
    with pytest.raises(TypeError, match="flags"):
        rio.request_json("GET", "/stats/", params={"by_char": True})


def test_request_bodies_are_json(mock, rio):
    route = mock.post("/tag_set/ladder/").respond(json={})
    rio.tag_sets.ladder("S13 Superstars Off")
    request = route.calls.last.request
    assert request.headers["content-type"] == "application/json"
    assert body(route) == {"TagSet": "S13 Superstars Off"}
    assert isinstance(request, httpx.Request)

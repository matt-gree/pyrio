"""Requests to Rio web: its parameter names and encodings, and one builder per endpoint.

This is the only module that knows Rio web's request names. Each builder takes
typed Python values and returns a :class:`Call`: the path, the query or body,
the credential it needs and the decoder for its response. The clients only
send calls, so the sync and async clients can't disagree about a request.

The server's conventions, from ProjectRio-web ``d4bf233``:

- A flag is on only when its value is exactly ``'1'`` (``== '1'``), so a flag
  is sent as ``'1'`` and left out when off. Python's ``True`` would go out as
  ``"True"``, which the server reads as off. Two routes differ: ``by_inning``
  on ``/star_chances/`` accepts ``true``/``t``, and ``Active`` on
  ``/tag_set/list`` reads ``yes``/``y``/``true``/``t``.
- List parameters repeat the key (``tag=a&tag=b``); the server reads them with
  ``getlist``.
- Names (tags, users, captains, tag sets, communities, groups) go out as typed.
  The server lowercases them and drops everything but letters and digits.
- Times are Unix seconds.
- ``limit_games`` is an integer, or ``'False'`` for no limit.

Arguments are checked at runtime as well as typed, since many callers (bots,
notebooks) run no type checker; a wrong type would otherwise reach the server
as a filter that silently matches nothing.
"""

# pyright: reportUnnecessaryIsInstance=false

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import TYPE_CHECKING, Any, Generic, Literal, TypeAlias, TypeVar

from .._characters import Character
from .._codes import AtBatResult, ContactType, Hand, Position, Side, Stadium, SwingType
from .._enum import CodeEnum
from . import _decode as decode
from ._models import (
    Community,
    CommunityKind,
    CommunityMember,
    EventRef,
    GameSummary,
    IssuedKey,
    LadderGame,
    LadderRow,
    LandingRow,
    LiveGame,
    StarChanceRow,
    StatRow,
    Tag,
    TagKind,
    TagSet,
    TagSetKind,
    User,
)

if TYPE_CHECKING:
    from collections.abc import Callable, Mapping, Sequence

T = TypeVar("T")
V = TypeVar("V")

Params: TypeAlias = list[tuple[str, str]]
JSON: TypeAlias = dict[str, Any]


def _no_params() -> Params:
    return []


class Auth(Enum):
    """What credential a call needs."""

    PUBLIC = "public"
    """None. Any credential the client has is still sent, since some public
    routes show more to a caller they can identify (a private community's tags)."""
    CREDENTIAL = "credential"
    """An API key or a session."""
    SESSION = "session"
    """A session from ``login()``: Rio web refuses keys for these, because a
    credential may not be used to increase its own authority."""


@dataclass(frozen=True, slots=True)
class Call(Generic[T]):
    """One HTTP request to Rio web and how to decode its answer."""

    method: Literal["GET", "POST"]
    path: str
    decode: Callable[[object], T]
    params: Params = field(default_factory=lambda: _no_params())
    body: JSON | None = None
    auth: Auth = Auth.PUBLIC
    cacheable: bool = False
    """Reference data a ``DiskCache`` may serve."""
    json_response: bool = True
    """False for routes that answer plain text, which is then ignored."""


# --- the encoding table -------------------------------------------------------


def _flag(params: Params, name: str, on: bool) -> None:
    if on:
        params.append((name, "1"))


def _values(name: str, values: Sequence[V] | None) -> Sequence[V]:
    """A list argument's items. A bare string is refused: it would iterate letter by letter."""
    if values is None:
        return ()
    if isinstance(values, str | bytes):
        raise TypeError(f"{name} takes a list, not a single string: {name}=[{values!r}]")
    return values


def _strs(params: Params, name: str, arg: str, values: Sequence[str] | None) -> None:
    for value in _values(arg, values):
        if not isinstance(value, str):
            raise TypeError(f"{arg} takes strings, got {value!r}")
        params.append((name, value))


def _ints(params: Params, name: str, arg: str, values: Sequence[int] | None) -> None:
    for value in _values(arg, values):
        if isinstance(value, bool) or not isinstance(value, int):
            raise TypeError(f"{arg} takes integers, got {value!r}")
        params.append((name, str(value)))


def _codes(params: Params, name: str, arg: str, values: Sequence[CodeEnum] | None) -> None:
    for value in _values(arg, values):
        if not isinstance(value, CodeEnum):
            raise TypeError(f"{arg} takes enum members, got {value!r}")
        params.append((name, str(value.id)))


def _labels(params: Params, name: str, arg: str, values: Sequence[Character] | None) -> None:
    """Characters by name, which is how the game filters identify a captain."""
    for value in _values(arg, values):
        if not isinstance(value, Character):
            raise TypeError(f"{arg} takes Character members, got {value!r}")
        params.append((name, value.label))


def epoch(arg: str, value: datetime) -> int:
    """A timezone-aware ``datetime`` as Unix seconds."""
    if not isinstance(value, datetime):
        raise TypeError(f"{arg} takes a datetime, got {value!r}")
    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError(f"{arg} must be timezone-aware, such as datetime(..., tzinfo=UTC)")
    return int(value.timestamp())


def _time(params: Params, name: str, arg: str, value: datetime | None) -> None:
    if value is not None:
        params.append((name, str(epoch(arg, value))))


def _limit_games(params: Params, arg: str, value: int | None) -> None:
    if value is None:
        params.append(("limit_games", "False"))
        return
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        raise ValueError(f"{arg} must be a non-negative integer or None, got {value!r}")
    params.append(("limit_games", str(value)))


# `contact=5` is Rio web's "no contact" (a miss), stored as NULL.
_CONTACT_IDS = {ContactType.MISS: 5}
_HALF_INNING = {Side.AWAY: "0", Side.HOME: "1"}


@dataclass(frozen=True, slots=True, kw_only=True)
class GameFilter:
    """The ``/games/`` filters, which every read endpoint also accepts."""

    tags: Sequence[str] | None = None
    exclude_tags: Sequence[str] | None = None
    users: Sequence[str] | None = None
    vs_users: Sequence[str] | None = None
    exclude_users: Sequence[str] | None = None
    captains: Sequence[Character] | None = None
    vs_captains: Sequence[Character] | None = None
    exclude_captains: Sequence[Character] | None = None
    stadiums: Sequence[Stadium] | None = None
    start_time: datetime | None = None
    end_time: datetime | None = None

    def encode(self, params: Params) -> None:
        # views/games.py, get_game_ids()
        _strs(params, "tag", "tags", self.tags)
        _strs(params, "exclude_tag", "exclude_tags", self.exclude_tags)
        _strs(params, "username", "users", self.users)
        _strs(params, "vs_username", "vs_users", self.vs_users)
        _strs(params, "exclude_username", "exclude_users", self.exclude_users)
        _labels(params, "captain", "captains", self.captains)
        _labels(params, "vs_captain", "vs_captains", self.vs_captains)
        _labels(params, "exclude_captain", "exclude_captains", self.exclude_captains)
        _codes(params, "stadium", "stadiums", self.stadiums)
        _time(params, "start_time", "start_time", self.start_time)
        _time(params, "end_time", "end_time", self.end_time)


@dataclass(frozen=True, slots=True, kw_only=True)
class EventFilter:
    """The per-event filters of ``/events/``, ``/landing_data/`` and ``/star_chances/``."""

    game_ids: Sequence[int] | None = None
    pitchers: Sequence[Character] | None = None
    batters: Sequence[Character] | None = None
    fielders: Sequence[Character] | None = None
    fielder_positions: Sequence[Position] | None = None
    contacts: Sequence[ContactType] | None = None
    swings: Sequence[SwingType] | None = None
    chem_links: Sequence[int] | None = None
    batter_hands: Sequence[Hand] | None = None
    pitcher_hands: Sequence[Hand] | None = None
    innings: Sequence[int] | None = None
    batting_sides: Sequence[Side] | None = None
    balls: Sequence[int] | None = None
    strikes: Sequence[int] | None = None
    outs: Sequence[int] | None = None
    away_scores: Sequence[int] | None = None
    home_scores: Sequence[int] | None = None
    results: Sequence[AtBatResult] | None = None
    only_star_chances: bool = False
    users_as_batter: bool = False
    users_as_pitcher: bool = False

    def encode(self, params: Params) -> None:
        # stat_retrieval.py, _parse_event_args(). `pitch` is accepted there but
        # filters nothing (its predicate is commented out), so it isn't offered.
        _ints(params, "games", "game_ids", self.game_ids)
        _codes(params, "pitcher_char", "pitchers", self.pitchers)
        _codes(params, "batter_char", "batters", self.batters)
        _codes(params, "fielder_char", "fielders", self.fielders)
        _codes(params, "fielder_pos", "fielder_positions", self.fielder_positions)
        for contact in _values("contacts", self.contacts):
            if not isinstance(contact, ContactType):
                raise TypeError(f"contacts takes ContactType members, got {contact!r}")
            params.append(("contact", str(_CONTACT_IDS.get(contact, contact.id))))
        _codes(params, "swing", "swings", self.swings)
        _ints(params, "chem_link", "chem_links", self.chem_links)
        _codes(params, "batter_hand", "batter_hands", self.batter_hands)
        _codes(params, "pitcher_hand", "pitcher_hands", self.pitcher_hands)
        _ints(params, "inning", "innings", self.innings)
        for side in _values("batting_sides", self.batting_sides):
            if not isinstance(side, Side):
                raise TypeError(f"batting_sides takes Side members, got {side!r}")
            params.append(("half_inning", _HALF_INNING[side]))
        _ints(params, "balls", "balls", self.balls)
        _ints(params, "strikes", "strikes", self.strikes)
        _ints(params, "outs", "outs", self.outs)
        _ints(params, "away_score", "away_scores", self.away_scores)
        _ints(params, "home_score", "home_scores", self.home_scores)
        _codes(params, "final_result", "results", self.results)
        _flag(params, "star_chance", self.only_star_chances)
        _flag(params, "users_as_batter", self.users_as_batter)
        _flag(params, "users_as_pitcher", self.users_as_pitcher)


# --- reads --------------------------------------------------------------------


def games(
    games: GameFilter, *, limit: int | None, linescore: bool, scoring_plays: bool
) -> Call[list[GameSummary]]:
    params: Params = []
    games.encode(params)
    _limit_games(params, "limit", limit)
    _flag(params, "include_linescore", linescore)
    _flag(params, "include_scoring_plays", scoring_plays)
    return Call("GET", "/games/", decode.games, params)


def stats(
    games: GameFilter,
    *,
    game_ids: Sequence[int] | None,
    limit_games: int | None,
    characters: Sequence[Character] | None,
    shape: decode.StatsShape,
    exclude_fouls: bool,
    exclude_batting: bool,
    exclude_pitching: bool,
    exclude_fielding: bool,
    exclude_record: bool,
) -> Call[list[StatRow]]:
    # stat_retrieval.py, endpoint_detailed_stats()
    params: Params = []
    games.encode(params)
    _limit_games(params, "limit_games", limit_games)
    _ints(params, "games", "game_ids", game_ids)
    _codes(params, "char_id", "characters", characters)
    _flag(params, "by_game", shape.by_game)
    _flag(params, "by_user", shape.by_user)
    _flag(params, "by_roster_order", shape.by_roster_spot)
    _flag(params, "by_char", shape.by_character)
    _flag(params, "by_batting_hand", shape.by_batting_hand)
    _flag(params, "by_fielding_hand", shape.by_pitching_hand)
    _flag(params, "by_swing", shape.by_swing)
    _flag(params, "exclude_nonfair", exclude_fouls)
    _flag(params, "exclude_batting", exclude_batting)
    _flag(params, "exclude_pitching", exclude_pitching)
    _flag(params, "exclude_fielding", exclude_fielding)
    _flag(params, "exclude_misc", exclude_record)
    _flag(params, "include_pitcher_wins", shape.include_pitcher_wins)
    _flag(params, "include_runs_scored", shape.include_runs_scored)

    def decode_stats(data: object) -> list[StatRow]:
        return decode.stats(data, shape)

    return Call("GET", "/stats/", decode_stats, params)


def event_ids(
    games: GameFilter, events: EventFilter, *, limit_games: int | None, limit: int
) -> Call[list[EventRef]]:
    params: Params = []
    games.encode(params)
    events.encode(params)
    _limit_games(params, "limit_games", limit_games)
    if isinstance(limit, bool) or not isinstance(limit, int) or limit < 0:
        raise ValueError(f"limit must be a non-negative integer, got {limit!r}")
    params.append(("limit_events", str(limit)))
    return Call("GET", "/events/", decode.event_ids, params)


def landing_data(
    games: GameFilter,
    events: EventFilter,
    *,
    event_ids: Sequence[int] | None,
    limit_games: int | None,
) -> Call[list[LandingRow]]:
    params: Params = []
    games.encode(params)
    events.encode(params)
    _ints(params, "events", "event_ids", event_ids)
    _limit_games(params, "limit_games", limit_games)
    return Call("GET", "/landing_data/", decode.landing_data, params)


def star_chances(
    games: GameFilter,
    events: EventFilter,
    *,
    event_ids: Sequence[int] | None,
    limit_games: int | None,
    by_inning: bool,
) -> Call[list[StarChanceRow]]:
    params: Params = []
    games.encode(params)
    events.encode(params)
    _ints(params, "events", "event_ids", event_ids)
    _limit_games(params, "limit_games", limit_games)
    if by_inning:
        # This route reads `in ["true", "True", "T", "t"]`, not `== '1'`.
        params.append(("by_inning", "true"))

    def decode_star_chances(data: object) -> list[StarChanceRow]:
        return decode.star_chances(data, by_inning=by_inning)

    return Call("GET", "/star_chances/", decode_star_chances, params)


def live_games() -> Call[list[LiveGame]]:
    return Call("GET", "/populate_db/ongoing_game/", decode.live_games)


# --- games, sessions, keys ----------------------------------------------------


def delete_game(game_id: int) -> Call[None]:
    return Call(
        "POST",
        "/delete_game/",
        decode.ignore,
        body={"game_id": game_id},
        auth=Auth.CREDENTIAL,
        json_response=False,
    )


def submit_game(
    *,
    winner: str,
    loser: str,
    winner_score: int,
    loser_score: int,
    tag_set: str,
    played_at: datetime,
    game_id: int | None,
) -> Call[int]:
    # populate_db.py, submit_game_history(). The submitter is the credential;
    # `submitter_rio_key` and `recalc` aren't read.
    body: JSON = {
        "winner_username": winner,
        "loser_username": loser,
        "winner_score": winner_score,
        "loser_score": loser_score,
        "tag_set": tag_set,
        "date": epoch("played_at", played_at),
    }
    if game_id is not None:
        body["game_id_dec"] = game_id
    return Call(
        "POST", "/manual_submit_game/", decode.game_history_id, body=body, auth=Auth.CREDENTIAL
    )


def login(email: str, password: str) -> Call[tuple[str, str]]:
    return Call("POST", "/login/", decode.login, body={"Email": email, "Password": password})


def create_api_key() -> Call[IssuedKey]:
    path = "/api_key/register/"
    return Call("POST", path, decode.issued_key(path), body={}, auth=Auth.SESSION)


def reset_api_key() -> Call[IssuedKey]:
    path = "/api_key/reset/"
    return Call("POST", path, decode.issued_key(path), body={}, auth=Auth.SESSION)


def query(params: Mapping[str, str | int | Sequence[str | int]] | None) -> Params:
    """The escape hatch's query: a list value repeats its key, as the server's ``getlist`` reads."""
    pairs: Params = []
    for name, value in (params or {}).items():
        values = [value] if isinstance(value, str | int) else value
        for item in values:
            if isinstance(item, bool):
                raise TypeError(f"{name}: send flags as '1', not {item!r}")
            pairs.append((name, str(item)))
    return pairs


def body(json: Mapping[str, Any] | None) -> JSON | None:
    return None if json is None else dict(json)


def raw(
    method: Literal["GET", "POST"], path: str, params: Params, body: JSON | None
) -> Call[object]:
    if not path.startswith("/"):
        raise ValueError(f"path must start with '/', got {path!r}")
    return Call(method, path, decode.as_is, params, body)


# --- users and groups ---------------------------------------------------------


def users(*, include_unverified: bool) -> Call[list[User]]:
    params: Params = [("verified", "false")] if include_unverified else []
    return Call("GET", "/user/all/", decode.users, params, cacheable=True)


def user_communities(user: str) -> Call[list[Community]]:
    path = "/user/community/"
    return Call("GET", path, decode.communities(path, "communities"), [("username", user)])


def user_sponsored_communities(user: str) -> Call[list[Community]]:
    path = "/user/community/sponsor/"
    decoder = decode.communities(path, "sponsored_communities")
    return Call("GET", path, decoder, [("username", user)])


def add_to_group(user: str, group: str) -> Call[None]:
    body: JSON = {"username": user, "group_name": group}
    return Call("POST", "/user_group/add_user", decode.ignore, body=body, auth=Auth.SESSION)


def remove_from_group(user: str, group: str) -> Call[None]:
    body: JSON = {"username": user, "group_name": group}
    return Call("POST", "/user_group/remove_user", decode.ignore, body=body, auth=Auth.SESSION)


def is_in_group(user: str, group: str) -> Call[bool]:
    params: Params = [("username", user), ("group_name", group)]
    return Call(
        "GET",
        "/user_group/check_for_member",
        decode.is_group_member,
        params,
        auth=Auth.CREDENTIAL,
    )


def group_members(group: str) -> Call[list[str]]:
    params: Params = [("group_name", group)]
    return Call("GET", "/user_group/members", decode.group_members, params, auth=Auth.CREDENTIAL)


# --- tags ---------------------------------------------------------------------


def _optional(body: JSON, name: str, value: object) -> None:
    if value is not None:
        body[name] = value


def _kind_value(arg: str, value: Enum | None, kind: type[Enum]) -> str | None:
    if value is None:
        return None
    if not isinstance(value, kind):
        raise TypeError(f"{arg} takes a {kind.__name__}, got {value!r}")
    return str(value.value)


def list_tags(
    *, kinds: Sequence[TagKind] | None, community_ids: Sequence[int] | None
) -> Call[list[Tag]]:
    # tag.py, tag_list(): POST reads `Types` (a list) and `Communities` (ids).
    body: JSON = {}
    if kinds is not None:
        body["Types"] = [_kind_value("kinds", k, TagKind) for k in _values("kinds", kinds)]
    if community_ids is not None:
        body["Communities"] = [int(i) for i in _values("community_ids", community_ids)]
    return Call("POST", "/tag/list", decode.tags("/tag/list", "Tags"), body=body, cacheable=True)


def create_tag(
    *,
    name: str,
    description: str,
    kind: TagKind,
    community: str,
    gecko_code: str | None,
    gecko_code_description: str | None,
) -> Call[Tag]:
    body: JSON = {
        "name": name,
        "desc": description,
        "community_name": community,
        "type": _kind_value("kind", kind, TagKind),
    }
    _optional(body, "gecko_code", gecko_code)
    _optional(body, "gecko_code_desc", gecko_code_description)
    return Call("POST", "/tag/create", decode.tag, body=body, auth=Auth.CREDENTIAL)


def update_tag(
    tag_id: int,
    *,
    name: str | None,
    description: str | None,
    kind: TagKind | None,
    gecko_code: str | None,
    gecko_code_description: str | None,
) -> Call[None]:
    body: JSON = {"tag_id": tag_id}
    _optional(body, "name", name)
    _optional(body, "desc", description)
    _optional(body, "type", _kind_value("kind", kind, TagKind))
    _optional(body, "gecko_code", gecko_code)
    _optional(body, "gecko_code_desc", gecko_code_description)
    return Call("POST", "/tag/update", decode.ignore, body=body, auth=Auth.CREDENTIAL)


# --- tag sets -----------------------------------------------------------------


def list_tag_sets(*, active_only: bool, community_ids: Sequence[int] | None) -> Call[list[TagSet]]:
    # tag.py, tagset_list(). `Active` reads yes/y/true/t. An empty
    # `Communities` list is a 409, so it's sent only when non-empty.
    body: JSON = {}
    if active_only:
        body["Active"] = "true"
    ids = [int(i) for i in _values("community_ids", community_ids)]
    if ids:
        body["Communities"] = ids
    return Call("POST", "/tag_set/list", decode.tag_sets, body=body, cacheable=True)


def get_tag_set(tag_set_id: int) -> Call[TagSet]:
    if isinstance(tag_set_id, bool) or not isinstance(tag_set_id, int):
        raise TypeError(f"tag_set_id takes an integer, got {tag_set_id!r}")
    return Call("GET", f"/tag_set/{tag_set_id}", decode.tag_set, cacheable=True)


def create_tag_set(
    *,
    name: str,
    description: str,
    kind: TagSetKind,
    community: str,
    start_time: datetime,
    end_time: datetime,
    tag_ids: Sequence[int] | None,
    copy_tags_from: int | None,
) -> Call[TagSet]:
    body: JSON = {
        "name": name,
        "desc": description,
        "type": _kind_value("kind", kind, TagSetKind),
        "community_name": community,
        "start_date": epoch("start_time", start_time),
        "end_date": epoch("end_time", end_time),
    }
    if tag_ids is not None:
        body["add_tag_ids"] = [int(i) for i in _values("tag_ids", tag_ids)]
    _optional(body, "tag_set_id", copy_tags_from)
    return Call("POST", "/tag_set/create", decode.created_tag_set, body=body, auth=Auth.CREDENTIAL)


def update_tag_set(
    tag_set_id: int,
    *,
    name: str | None,
    kind: TagSetKind | None,
    start_time: datetime | None,
    end_time: datetime | None,
    add_tag_ids: Sequence[int] | None,
    remove_tag_ids: Sequence[int] | None,
) -> Call[None]:
    # `desc` is accepted but TagSet has no such column, so it isn't offered.
    body: JSON = {"tag_set_id": tag_set_id}
    _optional(body, "name", name)
    _optional(body, "type", _kind_value("kind", kind, TagSetKind))
    if start_time is not None:
        body["start_date"] = epoch("start_time", start_time)
    if end_time is not None:
        body["end_date"] = epoch("end_time", end_time)
    if add_tag_ids is not None:
        body["add_tag_ids"] = [int(i) for i in _values("add_tag_ids", add_tag_ids)]
    if remove_tag_ids is not None:
        body["remove_tag_ids"] = [int(i) for i in _values("remove_tag_ids", remove_tag_ids)]
    return Call("POST", "/tag_set/update", decode.ignore, body=body, auth=Auth.CREDENTIAL)


def delete_tag_set(name: str) -> Call[None]:
    return Call("POST", "/tag_set/delete", decode.ignore, body={"name": name}, auth=Auth.CREDENTIAL)


def ladder(tag_set: str) -> Call[list[LadderRow]]:
    # The trailing slash is the server's spelling; without it, a 308.
    return Call("POST", "/tag_set/ladder/", decode.ladder, body={"TagSet": tag_set})


def ladder_games(
    tag_sets: Sequence[str], *, start_time: datetime | None, end_time: datetime | None
) -> Call[list[LadderGame]]:
    params: Params = []
    _strs(params, "tag_set", "tag_sets", tag_sets)
    _time(params, "start_time", "start_time", start_time)
    _time(params, "end_time", "end_time", end_time)
    return Call("GET", "/ladder/games/", decode.ladder_games, params)


# --- communities --------------------------------------------------------------


def create_community(
    *, name: str, kind: CommunityKind, private: bool, global_link: bool, description: str
) -> Call[str | None]:
    # community.py, community_create(): `private` and `global_link` are
    # compared `== 1`.
    body: JSON = {
        "community_name": name,
        "type": _kind_value("kind", kind, CommunityKind),
        "private": 1 if private else 0,
        "global_link": 1 if global_link else 0,
        "desc": description,
    }
    return Call(
        "POST", "/community/create", decode.created_community, body=body, auth=Auth.CREDENTIAL
    )


def list_communities() -> Call[list[Community]]:
    # The route's `type` filter compares against integer keys and can never
    # match a stored type, so it isn't offered.
    path = "/community/list"
    return Call(
        "POST", path, decode.communities(path, "Communities"), body={}, auth=Auth.CREDENTIAL
    )


def join_community(name: str, *, url: str | None) -> Call[bool]:
    body: JSON = {"community_name": name}
    _optional(body, "URL", url)
    return Call("POST", "/community/join", decode.joined_community, body=body, auth=Auth.CREDENTIAL)


def leave_community(name: str) -> Call[CommunityMember]:
    body: JSON = {"community_name": name}
    return Call("POST", "/community/leave", decode.left_community, body=body, auth=Auth.CREDENTIAL)


def invite(name: str, users: Sequence[str]) -> Call[list[str]]:
    body: JSON = {"community_name": name, "invite_list": list(_values("users", users))}
    return Call("POST", "/community/invite", decode.invited, body=body, auth=Auth.CREDENTIAL)


def community_members(name: str) -> Call[list[CommunityMember]]:
    path = "/community/members"
    return Call("POST", path, decode.members(path, "Members"), body={"community_name": name})


def community_tags(name: str) -> Call[list[Tag]]:
    path = "/community/tags"
    return Call("POST", path, decode.tags(path, "Tags"), body={"community_name": name})


def manage_members(
    name: str, users: Sequence[str], action: dict[str, bool]
) -> Call[list[CommunityMember]]:
    # community.py, community_manage(): one {"username", <action>: bool} per user.
    path = "/community/manage"
    body: JSON = {
        "community_name": name,
        "user_list": [{"username": user, **action} for user in _values("users", users)],
    }
    return Call("POST", path, decode.members(path, "members"), body=body, auth=Auth.CREDENTIAL)


def sponsor(name: str, action: Literal["get", "add", "remove"]) -> Call[str | None]:
    body: JSON = {"community_name": name, "action": action}
    auth = Auth.PUBLIC if action == "get" else Auth.CREDENTIAL
    return Call("POST", "/community/sponsor", decode.sponsor, body=body, auth=auth)


def community_key(name: str, action: Literal["generate", "revoke"]) -> Call[CommunityMember]:
    body: JSON = {"community_name": name, "action": action}
    return Call("POST", "/community/key", decode.community_key, body=body, auth=Auth.CREDENTIAL)


def all_community_keys(name: str) -> Call[dict[str, str]]:
    body: JSON = {"community_name": name, "action": "generate_all"}
    return Call(
        "POST", "/community/key", decode.all_community_keys, body=body, auth=Auth.CREDENTIAL
    )


def update_community(
    community_id: int,
    *,
    name: str | None,
    description: str | None,
    private: bool | None,
    global_link: bool | None,
    active_tag_set_limit: int | None,
) -> Call[None]:
    # community.py, community_update(). Its `type` assigns an attribute that
    # isn't the column, so changing the kind isn't offered.
    body: JSON = {"community_id": community_id}
    _optional(body, "name", name)
    _optional(body, "desc", description)
    _optional(body, "private", private)
    _optional(body, "link", global_link)
    _optional(body, "active_tag_set_limit", active_tag_set_limit)
    return Call("POST", "/community/update", decode.ignore, body=body, auth=Auth.CREDENTIAL)

"""Reading stat files and HUD files: the version-aware decoder.

This is the only module that knows client versions differ. Every per-version
rule lives in ``_rules`` below, named for what it does, with the range it
applies to and why; ``tests/test_decode.py`` pins each one. Past this module
nothing sees a raw dict, a raw id, a raw label or a version number.

Encoded files (ids) are the source of truth. Decoded files (labels) parse too:
every coded field accepts an id or a label, with the label corrections below.
"""

from __future__ import annotations

import json
import os
import re
from collections.abc import Callable, Mapping
from dataclasses import dataclass, replace
from datetime import UTC, datetime
from pathlib import Path
from typing import IO, Any, TypeVar, cast

from ._characters import Character
from ._codes import (
    AtBatResult,
    Bases,
    ChargeType,
    ContactType,
    DeadBallReason,
    FielderAction,
    FielderBobble,
    Hand,
    InputDirection,
    ManualSelect,
    MoonshotStatus,
    OutType,
    PitchType,
    Position,
    PrimaryContactResult,
    PushPull,
    SecondaryContactResult,
    Side,
    Stadium,
    StealType,
    SwingType,
)
from ._enum import CodeEnum
from ._errors import StatFileError, UnknownCodeError
from ._game import (
    HOME_PLATE,
    MERCY_LEAD,
    Contact,
    Event,
    Fielding,
    Game,
    GameResult,
    GameState,
    HUDSnapshot,
    Pitch,
    RosterSpot,
    Runner,
    Team,
    Version,
    leader,
)
from ._stats import rio_batting_line, rio_pitching_line
from ._team_names import TeamName

__all__ = ["read_game", "read_hud"]

_E = TypeVar("_E", bound=CodeEnum)

Source = str | os.PathLike[str] | IO[str] | IO[bytes] | Mapping[str, Any]

# --- Version rules -------------------------------------------------------------
# Kinds, after docs/version-decoding-proposal.md: (a) the same value under another
# key, (b) a wrong value that can be corrected, (c) a value the file can't give.

# (c) Clients before 0.1.7 wrote no "Version" key, and 0.1.0-0.1.5 a different
# layout altogether ("Away/Home Team Roster" arrays and "Player Stats").
_FIRST_SUPPORTED = Version(0, 1, 7)
# (b) Team numbers meant 0 = home, 1 = away before 1.9.2, and the reverse since.
_TEAM_0_IS_AWAY = Version(1, 9, 2)
# (b) 1.9.2-1.9.4 flipped the team numbers but not the captain lookup, so each
# team's "Captain" flag marks the roster index of the other team's captain.
_CAPTAINS_FIXED = Version(1, 9, 5)
# (a) Renamed keys are read by whichever name the file has, newest first, not
# by version: some test builds labelled 1.9.5 still wrote the 1.9.4 layout.
#  - Roster keys: "Team 1 Roster 3" up to 1.9.4, "Away Roster 3" from 1.9.5.
#  - 1.9.2 renamed "Pitches Per Position" to "Batters Per Position" and changed
#    the count from pitches to batters (ProjectRio ee757054f4), so the two are
#    kept apart: RosterSpot.pitches_per_position and .batters_per_position.
# (b) "GameID" is hex up to 0.1.8 (std::hex), decimal from 0.1.9, and hex again
# from 2.3.0 (a random 64-bit id, StatTracker::gameIDToHex).
_DECIMAL_GAME_ID = Version(0, 1, 9)
_HEX_GAME_ID = Version(2, 3, 0)
# (c) Before 0.1.9 the fielder's action and jump weren't initialised, so a
# fielder who didn't collect the ball got whatever was in memory. The same fix
# (ProjectRio 339c6c5797) set the position of a fielder logged from a bobble,
# which until then was also whatever was in memory (values up to 255).
_FIELDER_ACTION = Version(0, 1, 9)
# (c) Before 0.1.9 a pitch that hit the batter, or was still in the air when a
# crash file was written, has no "Type of Swing": no swing was logged.
_SWING_ALWAYS_WRITTEN = Version(0, 1, 9)
# (b) Before 0.1.8 "Star Pitch" was the game's raw star-pitch byte, which can be
# 2 or 3, not a 0/1 flag (ProjectRio 75ff1381ac). Any nonzero is a star pitch.
_STAR_PITCH_FLAG = Version(0, 1, 8)
# (c) Before 1.9.2 "Fielder Manual Selected" held the manual-select lock, a
# different value from today's selection, under the same key.
_MANUAL_SELECT = Version(1, 9, 2)
# (b) Before 2.3.0 the at-bat result table had the labels for ids 5 and 6 the
# wrong way round, so a decoded "Caught" means id 5. Encoded ids were always right.
_CAUGHT_LABELS_FIXED = Version(2, 3, 0)
# (b) Before 2.3.0 the contact results were logged wrongly in three ways that
# can be put right (see _correct_legacy_contact).
_CONTACT_RESULTS_FIXED = Version(2, 3, 0)
# (b) Before 2.3.0 every bunt was logged with no swing type: the game's swing
# flag only covers slaps, charges and star swings (ProjectRio db01a9438e). A
# pitch with no swing that was hit can only have been bunted. A missed bunt
# still can't be told from a take.
_BUNT_SWING_RECORDED = Version(2, 3, 0)

_SWAPPED_CAUGHT_LABELS = {
    "caught": AtBatResult.CAUGHT_LINE_DRIVE,
    "caught line-drive": AtBatResult.CAUGHT,
}

# (b), every version: a decoded file writes an id its client's table lacked as
# "Unable to Decode. Invalid Value (N).", so N is the id (a charged captain star
# before 2.3.0, an unresolved play's secondary result 255).
_UNDECODED = re.compile(r"Unable to Decode\. Invalid Value \((\d+)\)\.")

_UNFINISHED_PLAY = 255  # "Num Outs During Play" when the game ended mid-play
_NO_BASE = 255  # "Runner Result Base" for a runner put out
_NO_POSITION = 0xFF  # "Inv" in cPosition
# Some games (seen from 2.0.1 to 2.1.1, all with no tag set) write 255 for both
# teams' stars at every event while star swings and pitches still happen: the
# count wasn't recorded.
_UNRECORDED_STARS = 255
# (b), every version: "Event Num" is a byte, so a game past 255 events wraps to
# 0. The decoder counts the wraps, so Event.number is unique within a game.
_EVENT_NUMBER_WRAP = 256


@dataclass(frozen=True, slots=True)
class _Rules:
    """How one client version's files are read. Each field is one rule above."""

    version: Version
    home_is_team_0: bool
    captains_crossed: bool
    decimal_game_id: bool
    fielder_action: bool
    swing_always_written: bool
    star_pitch_flag: bool
    manual_select: bool
    caught_labels_swapped: bool
    legacy_contact_results: bool
    bunts_unrecorded: bool


def _rules(version: Version) -> _Rules:
    return _Rules(
        version=version,
        home_is_team_0=version < _TEAM_0_IS_AWAY,
        captains_crossed=_TEAM_0_IS_AWAY <= version < _CAPTAINS_FIXED,
        decimal_game_id=_DECIMAL_GAME_ID <= version < _HEX_GAME_ID,
        fielder_action=version >= _FIELDER_ACTION,
        swing_always_written=version >= _SWING_ALWAYS_WRITTEN,
        star_pitch_flag=version >= _STAR_PITCH_FLAG,
        manual_select=version >= _MANUAL_SELECT,
        caught_labels_swapped=version < _CAUGHT_LABELS_FIXED,
        legacy_contact_results=version < _CONTACT_RESULTS_FIXED,
        bunts_unrecorded=version < _BUNT_SWING_RECORDED,
    )


# --- Reading values --------------------------------------------------------------


class _Node:
    """One JSON object from the file, and where it sits, for error messages."""

    __slots__ = ("_data", "_path", "_where")

    def __init__(self, data: Mapping[str, Any], where: str, path: str | None) -> None:
        self._data = data
        self._where = where
        self._path = path

    def error(self, message: str, key: str | None = None) -> StatFileError:
        where = f"{self._where}.{key}" if self._where and key else (key or self._where)
        return StatFileError(message, path=self._path, key=where or None)

    def has(self, key: str) -> bool:
        return key in self._data

    def value(self, key: str) -> object:
        try:
            return self._data[key]
        except KeyError:
            raise self.error("missing", key) from None

    def integer(self, key: str) -> int:
        return self.as_integer(self.value(key), key)

    def maybe_integer(self, key: str) -> int | None:
        return self.integer(key) if key in self._data else None

    def number(self, key: str) -> float:
        value = self.value(key)
        if isinstance(value, bool) or not isinstance(value, int | float | str):
            raise self.error(f"expected a number, got {value!r}", key)
        try:
            return float(value.replace(",", "")) if isinstance(value, str) else float(value)
        except ValueError:
            raise self.error(f"expected a number, got {value!r}", key) from None

    def maybe_number(self, key: str) -> float | None:
        return self.number(key) if key in self._data else None

    def flag(self, key: str) -> bool:
        value = self.integer(key)
        if value not in (0, 1):
            raise self.error(f"expected 0 or 1, got {value!r}", key)
        return value == 1

    def maybe_flag(self, key: str) -> bool | None:
        return self.flag(key) if key in self._data else None

    def text(self, key: str) -> str:
        value = self.value(key)
        if not isinstance(value, str):
            raise self.error(f"expected a string, got {value!r}", key)
        return value

    def node(self, key: str) -> _Node:
        value = self.value(key)
        if not isinstance(value, Mapping):
            raise self.error(f"expected an object, got {type(value).__name__}", key)
        where = f"{self._where}.{key}" if self._where else key
        return _Node(cast("Mapping[str, Any]", value), where, self._path)

    def maybe_node(self, key: str) -> _Node | None:
        return self.node(key) if key in self._data else None

    def nodes(self, key: str) -> list[_Node]:
        value = self.value(key)
        if not isinstance(value, list):
            raise self.error(f"expected a list, got {type(value).__name__}", key)
        items: list[_Node] = []
        for index, item in enumerate(cast("list[object]", value)):
            where = f"{self._where}.{key}[{index}]" if self._where else f"{key}[{index}]"
            if not isinstance(item, Mapping):
                raise StatFileError("expected an object", path=self._path, key=where)
            items.append(_Node(cast("Mapping[str, Any]", item), where, self._path))
        return items

    def coded(self, key: str, kind: type[_E]) -> _E:
        return self._coded(self.value(key), key, kind)

    def maybe_coded(self, key: str, kind: type[_E]) -> _E | None:
        return self.coded(key, kind) if key in self._data else None

    def position(self, key: str) -> Position | None:
        value = self.value(key)
        if value == _NO_POSITION or value == "Inv":
            return None
        return self._coded(value, key, Position)

    def spot(self, key: str, team: Team) -> RosterSpot:
        index = self.integer(key)
        if not 0 <= index < len(team.roster):
            raise self.error(f"roster spot {index} is out of range", key)
        return team.roster[index]

    def per_position(self, key: str) -> dict[Position, int]:
        # Written as an empty list, or a list holding one {position label: count}.
        value = self.value(key)
        if not isinstance(value, list):
            raise self.error(f"expected a list, got {type(value).__name__}", key)
        counts: dict[Position, int] = {}
        for entry in cast("list[object]", value):
            if not isinstance(entry, Mapping):
                raise self.error("expected a list of objects", key)
            for label, count in cast("Mapping[object, object]", entry).items():
                counts[self._coded(label, key, Position)] = self.as_integer(count, key)
        return counts

    def as_integer(self, value: object, key: str) -> int:
        # Integers often arrive quoted, and the client's locale can group the
        # digits ("10,257"), so strip commas from strings.
        if isinstance(value, bool):
            raise self.error(f"expected an integer, got {value!r}", key)
        if isinstance(value, int):
            return value
        if isinstance(value, float) and value.is_integer():
            return int(value)
        if isinstance(value, str):
            try:
                return int(value.replace(",", ""))
            except ValueError:
                pass
        raise self.error(f"expected an integer, got {value!r}", key)

    def _coded(self, value: object, key: str, kind: type[_E]) -> _E:
        if isinstance(value, str) and (match := _UNDECODED.fullmatch(value)):
            value = int(match.group(1))
        if isinstance(value, bool) or not isinstance(value, int | str):
            raise self.error(f"expected a {kind.__name__} id or label, got {value!r}", key)
        try:
            return kind(value)
        except UnknownCodeError as err:
            raise self.error(str(err), key) from err


def _load(source: Source) -> tuple[Mapping[str, Any], str | None]:
    if isinstance(source, Mapping):
        return source, None
    if isinstance(source, str | os.PathLike):
        path: str | None = os.fspath(source)
        raw: str | bytes = Path(path).read_bytes()
    else:
        path = getattr(source, "name", None)
        path = path if isinstance(path, str) else None
        raw = source.read()
    text = raw.decode("utf-8", errors="replace") if isinstance(raw, bytes) else raw
    try:
        data = _parse_json(text)
    except json.JSONDecodeError as err:
        raise StatFileError(f"not valid JSON: {err}", path=path) from err
    if not isinstance(data, Mapping):
        raise StatFileError("expected a JSON object at the top level", path=path)
    return cast("Mapping[str, Any]", data), path


def _parse_json(text: str) -> object:
    # strict=False: 0.1.7 wrote the quitting team as a raw control character.
    try:
        return json.loads(text, strict=False)
    except json.JSONDecodeError:
        # (b) 1.9.5 wrote a game without a tag set as `"TagSetID": ,`.
        repaired = re.sub(r'("TagSetID":\s*),', r"\1null,", text)
        # (b) 0.1.7-0.1.8 left a comma before a closing bracket: crash and quit
        # files after the last event, and 0.1.8 after a pitch with no swing.
        repaired = re.sub(r",(\s*[}\]])", r"\1", repaired)
        if repaired == text:
            raise
        return json.loads(repaired, strict=False)


# --- Stat files ------------------------------------------------------------------


def read_game(source: Source) -> Game:
    """Decode a stat file into a :class:`~pyrio.Game`.

    ``source`` is a path (a ``str`` is always a path, never JSON text), an open
    file in text or binary mode, or the already-parsed JSON object. Encoded
    and decoded files both work, from any client from 0.1.7 on. Raises
    :class:`~pyrio.StatFileError` for a file it can't read, saying where.
    """
    data, path = _load(source)
    root = _Node(data, "", path)
    rules = _rules(_file_version(root))
    away_roster, home_roster = _rosters(root, rules)
    away = Team(
        side=Side.AWAY,
        player=root.text("Away Player"),
        score=root.integer("Away Score"),
        roster=away_roster,
    )
    home = Team(
        side=Side.HOME,
        player=root.text("Home Player"),
        score=root.integer("Home Score"),
        roster=home_roster,
    )
    game_id = _game_id(root, rules)
    events = _events(root, rules, game_id, away, home)
    innings_selected = root.integer("Innings Selected")
    innings_played = root.integer("Innings Played")
    return Game(
        id=game_id,
        version=rules.version,
        start_time=_time(root, "Date - Start"),
        end_time=_time(root, "Date - End"),
        stadium=root.coded("StadiumID", Stadium),
        tag_set_id=_tag_set_id(root),
        is_netplay=root.flag("Netplay"),
        loaded_from_hud=bool(root.maybe_flag("Loaded from HUD")),
        innings_selected=innings_selected,
        innings_played=innings_played,
        average_ping_ms=root.integer("Average Ping"),
        lag_spikes=root.integer("Lag Spikes"),
        away=away,
        home=home,
        events=events,
        result=_result(root, away.score, home.score, innings_selected, innings_played, events),
    )


def _file_version(root: _Node) -> Version:
    if not root.has("Version"):
        raise root.error(
            "no Version key: this file is from Rio 0.1.6 or earlier, which pyrio doesn't read"
        )
    text = root.text("Version")
    try:
        version = Version.parse(text)
    except ValueError as err:
        raise root.error(str(err), "Version") from err
    if version < _FIRST_SUPPORTED:
        raise root.error(f"pyrio reads files from Rio {_FIRST_SUPPORTED} on", "Version")
    return version


def _game_id(root: _Node, rules: _Rules) -> int:
    raw = str(root.value("GameID")).replace(",", "")
    try:
        return int(raw, 10 if rules.decimal_game_id else 16)
    except ValueError:
        raise root.error(f"{raw!r} is not a game id", "GameID") from None


def _time(root: _Node, key: str) -> datetime:
    # Encoded files write Unix time; decoded files the writer's local time, in
    # asctime form ("Thu Jun 18 18:50:37 2026"), with no zone.
    text = str(root.value(key))
    if text.isdigit():
        return datetime.fromtimestamp(int(text), tz=UTC)
    try:
        return datetime.strptime(text, "%a %b %d %H:%M:%S %Y")
    except ValueError:
        raise root.error(f"{text!r} is not a date", key) from None


def _tag_set_id(root: _Node) -> int | None:
    # Absent before 1.9.5; -1 means none since 2.3.0, "" or null before.
    value = root.value("TagSetID") if root.has("TagSetID") else None
    if value is None or value == "":
        return None
    tag_set_id = root.integer("TagSetID")
    return None if tag_set_id < 0 else tag_set_id


def _result(
    root: _Node,
    away_score: int,
    home_score: int,
    innings_selected: int,
    innings_played: int,
    events: tuple[Event, ...],
) -> GameResult:
    quit_by, crashed = _quitter(root)
    winner = leader(away_score, home_score)
    # The mercy rule ends a game on a lead of 10 or more, but a home team that
    # trails always gets its half of the inning to answer: an away mercy win
    # ends on the home side batting.
    is_mercy = (
        quit_by is None
        and not crashed
        and innings_played < innings_selected
        and abs(away_score - home_score) >= MERCY_LEAD
        and (winner is Side.HOME or (bool(events) and events[-1].state.batting_side is Side.HOME))
    )
    return GameResult(winner=winner, is_mercy=is_mercy, quit_by=quit_by, crashed=crashed)


def _quitter(root: _Node) -> tuple[Side | None, bool]:
    # 0 is the home side quitting, 1 the away side, 2 a crash, 255 nobody. Decoded
    # files spell those "Home", "Away", "Crash", "None". 0.1.7 wrote a string: ""
    # for nobody, "Crash", or the 0/1 as a raw character.
    value = root.value("Quitter Team")
    match value:
        case 255 | "None" | "":
            return None, False
        case 0 | "Home" | "\x00":
            return Side.HOME, False
        case 1 | "Away" | "\x01":
            return Side.AWAY, False
        case 2 | "Crash":
            return None, True
        case _:
            raise root.error(f"unknown quitter {value!r}", "Quitter Team")


def _rosters(root: _Node, rules: _Rules) -> tuple[tuple[RosterSpot, ...], tuple[RosterSpot, ...]]:
    stats = root.node("Character Game Stats")
    return _build_rosters(_roster_nodes(stats, rules), rules)


def _roster_nodes(parent: _Node, rules: _Rules) -> dict[Side, list[_Node]]:
    nodes: dict[Side, list[_Node]] = {}
    for side in Side:
        team = int((side is Side.HOME) != rules.home_is_team_0)
        keys = (f"{side.value} Roster {{}}", f"Team {team} Roster {{}}")
        key = next((key for key in keys if parent.has(key.format(0))), keys[0])
        nodes[side] = [parent.node(key.format(index)) for index in range(9)]
    return nodes


def _build_rosters(
    nodes: dict[Side, list[_Node]], rules: _Rules
) -> tuple[tuple[RosterSpot, ...], tuple[RosterSpot, ...]]:
    captains = {side: [node.flag("Captain") for node in nodes[side]] for side in Side}
    if rules.captains_crossed:
        captains = {Side.AWAY: captains[Side.HOME], Side.HOME: captains[Side.AWAY]}
    for side in Side:
        if sum(captains[side]) != 1:
            raise nodes[side][0].error(f"the {side} team has {sum(captains[side])} captains, not 1")
    away, home = (
        tuple(
            _spot(node, side, index, captains[side][index], rules)
            for index, node in enumerate(nodes[side])
        )
        for side in (Side.AWAY, Side.HOME)
    )
    return away, home


def _spot(node: _Node, side: Side, index: int, is_captain: bool, rules: _Rules) -> RosterSpot:
    defense = node.node("Defensive Stats")
    offense = node.node("Offensive Stats")
    batting = rio_batting_line(offense.integer)
    pitching = rio_pitching_line(defense.integer)
    if defense.has("Batters Per Position") or not defense.has("Pitches Per Position"):
        batters, pitches = defense.per_position("Batters Per Position"), None
    else:
        batters, pitches = None, defense.per_position("Pitches Per Position")
    return RosterSpot(
        side=side,
        index=index,
        character=node.coded("CharID", Character),
        is_superstar=node.flag("Superstar"),
        is_captain=is_captain,
        fielding_hand=node.coded("Fielding Hand", Hand),
        batting_hand=node.coded("Batting Hand", Hand),
        batting=batting,
        pitching=pitching,
        was_pitcher=defense.flag("Was Pitcher"),
        stamina=defense.integer("Stamina"),
        big_plays=defense.integer("Big Plays"),
        batters_per_position=batters,
        pitches_per_position=pitches,
        batter_outs_per_position=defense.per_position("Batter Outs Per Position"),
        outs_per_position=defense.per_position("Outs Per Position"),
    )


def _events(root: _Node, rules: _Rules, game_id: int, away: Team, home: Team) -> tuple[Event, ...]:
    nodes = root.nodes("Events")
    scores = [(node.integer("Away Score"), node.integer("Home Score")) for node in nodes]
    scores.append((away.score, home.score))
    events: list[Event] = []
    wraps, previous = 0, -1
    for i, node in enumerate(nodes):
        raw_number = node.integer("Event Num")
        if raw_number < previous:
            wraps += 1
        previous = raw_number
        number = raw_number + wraps * _EVENT_NUMBER_WRAP
        state = _state(node)
        batting_index = 0 if state.batting_side is Side.AWAY else 1
        runs = scores[i + 1][batting_index] - scores[i][batting_index]
        following = nodes[i + 1] if i + 1 < len(nodes) else None
        event = _event(node, following, rules, game_id, state, runs, away, home)
        events.append(replace(event, number=number) if wraps else event)
    return tuple(events)


def _state(node: _Node) -> GameState:
    half = node.integer("Half Inning")
    if half not in (0, 1):
        raise node.error(f"expected 0 or 1, got {half}", "Half Inning")
    bases = Bases(0)
    for key, base in (
        ("Runner 1B", Bases.FIRST),
        ("Runner 2B", Bases.SECOND),
        ("Runner 3B", Bases.THIRD),
    ):
        if node.has(key):
            bases |= base
    return GameState(
        inning=node.integer("Inning"),
        batting_side=Side.AWAY if half == 0 else Side.HOME,
        balls=node.integer("Balls"),
        strikes=node.integer("Strikes"),
        outs=node.integer("Outs"),
        away_score=node.integer("Away Score"),
        home_score=node.integer("Home Score"),
        away_stars=_stars(node, "Away Stars"),
        home_stars=_stars(node, "Home Stars"),
        is_star_chance=node.flag("Star Chance"),
        pitcher_stamina=node.integer("Pitcher Stamina"),
        chemistry_links_on_base=node.integer("Chemistry Links on Base"),
        bases=bases,
    )


def _stars(node: _Node, key: str) -> int | None:
    stars = node.integer(key)
    return None if stars == _UNRECORDED_STARS else stars


def _event(
    node: _Node,
    following: _Node | None,
    rules: _Rules,
    game_id: int,
    state: GameState,
    runs: int,
    away: Team,
    home: Team,
) -> Event:
    batting, fielding = (away, home) if state.batting_side is Side.AWAY else (home, away)
    result = _at_bat_result(node, rules)
    outs_during_play = node.maybe_integer("Num Outs During Play")
    runners = _runners(node, batting, result)
    pitch_node = node.maybe_node("Pitch")
    pitch = contact = fielder = None
    if pitch_node is not None:
        pitch = _pitch(pitch_node, rules)
        contact_node = pitch_node.maybe_node("Contact")
        if contact_node is not None:
            contact = _contact(contact_node)
            if rules.bunts_unrecorded and pitch.swing is SwingType.NONE:
                pitch = replace(pitch, swing=SwingType.BUNT)
            if rules.legacy_contact_results:
                contact = _correct_legacy_contact(
                    contact,
                    result,
                    runners,
                    outs_during_play,
                    lambda: _continues_at_bat(node, following),
                )
            fielder_node = contact_node.maybe_node("First Fielder")
            if fielder_node is not None:
                fielder = _fielding(fielder_node, fielding, rules)
    return Event(
        game_id=game_id,
        number=node.integer("Event Num"),
        state=state,
        batter_spot=node.spot("Batter Roster Loc", batting),
        pitcher_spot=node.spot("Pitcher Roster Loc", fielding),
        catcher_spot=node.spot("Catcher Roster Loc", fielding),
        result=result,
        rbi=node.integer("RBI"),
        runs=runs,
        outs_during_play=None if outs_during_play == _UNFINISHED_PLAY else outs_during_play,
        dead_ball_reason=node.maybe_coded("Dead Ball Reason", DeadBallReason),
        runners=runners,
        pitch=pitch,
        contact=contact,
        fielding=fielder,
    )


def _at_bat_result(node: _Node, rules: _Rules) -> AtBatResult:
    value = node.value("Result of AB")
    if rules.caught_labels_swapped and isinstance(value, str):
        swapped = _SWAPPED_CAUGHT_LABELS.get(value.casefold())
        if swapped is not None:
            return swapped
    return node.coded("Result of AB", AtBatResult)


def _runners(node: _Node, batting: Team, result: AtBatResult) -> tuple[Runner, ...]:
    runners: list[Runner] = []
    for key in ("Runner Batter", "Runner 1B", "Runner 2B", "Runner 3B"):
        runner = node.maybe_node(key)
        if runner is None:
            continue
        out_type = runner.coded("Out Type", OutType)
        is_out = out_type is not OutType.NONE
        result_base: int | None = runner.integer("Runner Result Base")
        if is_out or result_base == _NO_BASE:
            result_base = None
        elif result is AtBatResult.HOME_RUN:
            # Every runner scores on a home run. Before 2.2.0 Rio usually left
            # the end base at the start base, because the result came first.
            result_base = HOME_PLATE
        runners.append(
            Runner(
                spot=runner.spot("Runner Roster Loc", batting),
                initial_base=runner.integer("Runner Initial Base"),
                result_base=result_base,
                out_type=out_type,
                out_base=runner.integer("Out Location") if is_out else None,
                steal=runner.coded("Steal", StealType),
            )
        )
    if result.is_walk:
        return _walk_runners(runners)
    return tuple(runners)


def _walk_runners(runners: list[Runner]) -> tuple[Runner, ...]:
    # (b), every version: on a walk or hit by pitch Rio logs the result before
    # anyone moves, so the batter's end base reads 0 and the forced runners
    # haven't advanced. Each is put on the next base, as the game does; a
    # runner already moved (a steal on the pitch) is left alone.
    occupied = {r.initial_base for r in runners if r.initial_base}
    forced = 0  # bases from first that are filled in a row, so forced to move
    while forced + 1 in occupied:
        forced += 1
    corrected: list[Runner] = []
    for runner in runners:
        moves = runner.initial_base == 0 or runner.initial_base <= forced
        if moves and not runner.is_out and runner.result_base in (0, runner.initial_base):
            runner = replace(runner, result_base=runner.initial_base + 1)
        corrected.append(runner)
    return tuple(corrected)


def _pitch(node: _Node, rules: _Rules) -> Pitch:
    bat_location = None
    if node.has("Bat Contact Pos - X"):
        bat_location = (node.number("Bat Contact Pos - X"), node.number("Bat Contact Pos - Z"))
    swing = SwingType.NONE
    if rules.swing_always_written or node.has("Type of Swing"):
        swing = node.coded("Type of Swing", SwingType)
    return Pitch(
        type=node.coded("Pitch Type", PitchType),
        charge_type=node.coded("Charge Type", ChargeType),
        is_star=node.flag("Star Pitch")
        if rules.star_pitch_flag
        else node.integer("Star Pitch") != 0,
        is_meatball=node.flag("DB"),
        speed=node.integer("Pitch Speed"),
        swing=swing,
        strike_zone_location=node.maybe_number("Ball Position - Strikezone"),
        is_in_strike_zone=node.maybe_flag("In Strikezone"),
        bat_location=bat_location,
    )


def _contact(node: _Node) -> Contact:
    rng = location = None
    if node.has("RNG1"):
        rng = (node.integer("RNG1"), node.integer("RNG2"), node.integer("RNG3"))
    if node.has("Ball Contact Pos - X"):
        location = (node.number("Ball Contact Pos - X"), node.number("Ball Contact Pos - Z"))
    stick = node.value("Input Direction - Stick")
    try:
        input_direction = InputDirection(stick)
    except (UnknownCodeError, ValueError) as err:
        raise node.error(str(err), "Input Direction - Stick") from err
    return Contact(
        type=node.coded("Type of Contact", ContactType),
        swing_frame=node.integer("Frame of Swing Upon Contact"),
        charge_power_up=node.number("Charge Power Up"),
        charge_power_down=node.number("Charge Power Down"),
        moonshot=node.coded("Star Swing Five-Star", MoonshotStatus),
        push_pull=node.coded("Input Direction - Push/Pull", PushPull),
        input_direction=input_direction,
        power=node.maybe_integer("Ball Power"),
        vertical_angle=node.maybe_integer("Vert Angle"),
        horizontal_angle=node.maybe_integer("Horiz Angle"),
        absolute=node.maybe_number("Contact Absolute"),
        quality=node.maybe_number("Contact Quality"),
        rng=rng,
        velocity=(
            node.number("Ball Velocity - X"),
            node.number("Ball Velocity - Y"),
            node.number("Ball Velocity - Z"),
        ),
        location=location,
        landing_location=(
            node.number("Ball Landing Position - X"),
            node.number("Ball Landing Position - Y"),
            node.number("Ball Landing Position - Z"),
        ),
        max_height=node.number("Ball Max Height"),
        hang_frames=node.maybe_integer("Ball Hang Time"),
        primary_result=node.coded("Contact Result - Primary", PrimaryContactResult),
        secondary_result=node.coded("Contact Result - Secondary", SecondaryContactResult),
    )


_BALL_IN_PLAY_RESULTS = frozenset(
    result for result in AtBatResult if AtBatResult.SINGLE <= result <= AtBatResult.DOUBLE_PLAY
)
_LEGACY_OUT_SECONDARY = {
    # Rio wrote the batter's out type as the secondary result: force (2) read
    # as "Out-tag" and tag (3) as "Foul".
    OutType.FORCE: SecondaryContactResult.OUT_FORCE,
    OutType.TAG: SecondaryContactResult.OUT_TAG,
}


def _correct_legacy_contact(
    contact: Contact,
    result: AtBatResult,
    runners: tuple[Runner, ...],
    outs_during_play: int | None,
    continues_at_bat: Callable[[], bool],
) -> Contact:
    """Put right the contact results clients before 2.3.0 logged wrongly.

    1. A batter forced or tagged out got their out type as the secondary result.
    2. Every result from single to double play was logged primary ``FAIR``; a
       sacrifice fly is always caught, so it's ``OUT``. The other results stay,
       since the file can't say which balls were fielded before landing.
    3. A foul that landed before the game called it was logged as fair and
       caught. It's a strikeout (a foul bunt), or a result of none followed by
       the same at-bat with one more strike.
    """
    primary, secondary = contact.primary_result, contact.secondary_result
    batter = next((runner for runner in runners if runner.initial_base == 0), None)
    if (
        primary in (PrimaryContactResult.FAIR, PrimaryContactResult.FIELDED)
        and secondary is SecondaryContactResult.OUT_CAUGHT
        and outs_during_play != _UNFINISHED_PLAY
        and (result is AtBatResult.STRIKEOUT or (result is AtBatResult.NONE and continues_at_bat()))
    ):
        primary = PrimaryContactResult.FOUL
        secondary = SecondaryContactResult.FOUL
    elif result not in _BALL_IN_PLAY_RESULTS and batter is not None:
        corrected = _LEGACY_OUT_SECONDARY.get(batter.out_type)
        if corrected is not None and secondary.id == batter.out_type.id:
            secondary = corrected
    if result is AtBatResult.SACRIFICE_FLY and primary is PrimaryContactResult.FAIR:
        primary = PrimaryContactResult.OUT
    if (primary, secondary) == (contact.primary_result, contact.secondary_result):
        return contact
    return replace(contact, primary_result=primary, secondary_result=secondary)


def _continues_at_bat(node: _Node, following: _Node | None) -> bool:
    # A foul keeps the batter up with the same outs and balls, and adds a strike
    # unless there are already two. The last event in a file can't be confirmed.
    if following is None:
        return False
    for key in ("Inning", "Half Inning", "Batter Roster Loc", "Outs", "Balls"):
        if following.integer(key) != node.integer(key):
            return False
    return following.integer("Strikes") == min(node.integer("Strikes") + 1, 2)


def _fielding(node: _Node, team: Team, rules: _Rules) -> Fielding:
    bobble = node.coded("Fielder Bobble", FielderBobble)
    position = None
    if rules.fielder_action or bobble is FielderBobble.NONE:
        position = node.position("Fielder Position")
    return Fielding(
        spot=node.spot("Fielder Roster Location", team),
        position=position,
        action=node.coded("Fielder Action", FielderAction) if rules.fielder_action else None,
        jumped=node.flag("Fielder Jump") if rules.fielder_action else None,
        manual_select=(
            node.coded("Fielder Manual Selected", ManualSelect) if rules.manual_select else None
        ),
        location=(
            node.number("Fielder Position - X"),
            node.number("Fielder Position - Y"),
            node.number("Fielder Position - Z"),
        ),
        bobble=bobble,
    )


# --- HUD files -------------------------------------------------------------------

_HUD_EVENT = re.compile(r"(\d+)([ab]?)")


def read_hud(source: Source, *, version: Version | str) -> HUDSnapshot:
    """Decode a HUD file (``hud.json`` or ``decoded.hud.json``) into a :class:`~pyrio.HUDSnapshot`.

    HUD files don't say which client wrote them, and the same label means
    different things in different versions (2.3.0 even writes the game id in
    hex where 2.2.0 wrote decimal), so the caller passes ``version``: a
    :class:`~pyrio.Version` or a string such as ``"2.3.0"``. The client that
    writes a HUD file also writes the stat files beside it, and they say.
    """
    if isinstance(version, str):
        try:
            version = Version.parse(version)
        except ValueError as err:
            raise StatFileError(str(err)) from err
    data, path = _load(source)
    root = _Node(data, "", path)
    rules = _rules(version)
    nodes = _roster_nodes(root, rules)
    away_roster, home_roster = _build_rosters(nodes, rules)
    state = _state(root)
    positions: dict[RosterSpot, Position] = {}
    for roster, side in ((away_roster, Side.AWAY), (home_roster, Side.HOME)):
        for spot, node in zip(roster, nodes[side], strict=True):
            if node.has("Fielding Position"):
                position = node.position("Fielding Position")
                if position is not None:
                    positions[spot] = position
    event_text = str(root.value("Event Num"))
    match = _HUD_EVENT.fullmatch(event_text)
    if match is None:
        raise root.error(f"{event_text!r} is not an event number", "Event Num")
    event_number, is_play_over = int(match.group(1)), match.group(2) == "b"
    game_id = _game_id(root, rules) if root.has("GameID") else None
    # The roster stats are written after the play and the event's own fields
    # before it, so on a play-over file the fielding side's runs allowed say
    # how many runs the play scored.
    runs = 0
    if is_play_over:
        fielding_roster = home_roster if state.batting_side is Side.AWAY else away_roster
        runs = _play_runs(root, state, fielding_roster)
    away_runs = runs if state.batting_side is Side.AWAY else 0
    home_runs = runs - away_runs
    away = Team(
        side=Side.AWAY,
        player=root.text("Away Player"),
        score=root.integer("Away Score") + away_runs,
        roster=away_roster,
    )
    home = Team(
        side=Side.HOME,
        player=root.text("Home Player"),
        score=root.integer("Home Score") + home_runs,
        roster=home_roster,
    )
    batting, fielding = (away, home) if state.batting_side is Side.AWAY else (home, away)
    play = None
    if is_play_over and game_id is not None and root.has("Previous Event"):
        play = _hud_play(
            root, rules, game_id, event_number, state, runs, batting, fielding, positions
        )
    return HUDSnapshot(
        version=version,
        game_id=game_id,
        tag_set_id=_tag_set_id(root),
        stadium=root.maybe_coded("StadiumID", Stadium),
        innings_selected=root.maybe_integer("Innings Selected"),
        away_logo=root.maybe_coded("Away Logo", TeamName),
        home_logo=root.maybe_coded("Home Logo", TeamName),
        away_port=root.maybe_integer("Away Port"),
        home_port=root.maybe_integer("Home Port"),
        star_skills=root.maybe_flag("Star Skills On"),
        mercy_rule=root.maybe_flag("Mercy On"),
        event_number=event_number,
        is_play_over=is_play_over,
        away=away,
        home=home,
        away_inning_runs=_inning_runs(root, "Away Inning Scores", state.inning, away_runs),
        home_inning_runs=_inning_runs(root, "Home Inning Scores", state.inning, home_runs),
        state=state,
        batter_spot=root.spot("Batter Roster Loc", batting),
        pitcher_spot=root.spot("Pitcher Roster Loc", fielding),
        runners=_runners(root, batting, play.result if play is not None else AtBatResult.NONE),
        play=play,
        fielding_positions=positions,
    )


_MOST_RUNS_ON_A_PLAY = 4


def _play_runs(root: _Node, state: GameState, fielding_roster: tuple[RosterSpot, ...]) -> int:
    allowed = sum(spot.pitching.runs_allowed for spot in fielding_roster)
    runs = allowed - state.score(state.batting_side)
    if 0 <= runs <= _MOST_RUNS_ON_A_PLAY:
        return runs
    # Stats that don't add up to the score (as in a game resumed from a HUD
    # file): count the runners home, unless the play ended the half, in which
    # case the game counted none of them in every file seen.
    if state.outs + (root.maybe_integer("Num Outs During Play") or 0) >= 3:
        return 0
    return sum(
        1
        for key in ("Runner Batter", "Runner 1B", "Runner 2B", "Runner 3B")
        if (runner := root.maybe_node(key)) is not None
        and runner.integer("Runner Result Base") == HOME_PLATE
    )


def _hud_play(
    root: _Node,
    rules: _Rules,
    game_id: int,
    event_number: int,
    state: GameState,
    runs: int,
    batting: Team,
    fielding: Team,
    positions: dict[RosterSpot, Position],
) -> Event:
    # A play-over file holds one whole event, split in two: the state, the
    # batter, pitcher and runners at the top level, and what the play did
    # under "Previous Event". The catcher comes from the fielding positions.
    played = root.node("Previous Event")
    catcher = next(
        (s for s, at in positions.items() if at is Position.CATCHER and s.side is fielding.side),
        None,
    )
    if catcher is None:
        raise root.error("the fielding side has no catcher", "Fielding Position")
    result = _at_bat_result(played, rules)
    outs_during_play = root.maybe_integer("Num Outs During Play")
    runners = _runners(root, batting, result)
    pitch = contact = fielder = None
    pitch_node = played.maybe_node("Pitch")
    if pitch_node is not None:
        pitch = _pitch(pitch_node, rules)
        contact_node = pitch_node.maybe_node("Contact")
        if contact_node is not None:
            contact = _contact(contact_node)
            if rules.bunts_unrecorded and pitch.swing is SwingType.NONE:
                pitch = replace(pitch, swing=SwingType.BUNT)
            if rules.legacy_contact_results:
                contact = _correct_legacy_contact(
                    contact, result, runners, outs_during_play, lambda: False
                )
            fielder_node = contact_node.maybe_node("First Fielder")
            if fielder_node is not None:
                fielder = _fielding(fielder_node, fielding, rules)
    return Event(
        game_id=game_id,
        number=event_number,
        state=state,
        batter_spot=root.spot("Batter Roster Loc", batting),
        pitcher_spot=root.spot("Pitcher Roster Loc", fielding),
        catcher_spot=catcher,
        result=result,
        rbi=played.integer("RBI"),
        runs=runs,
        outs_during_play=None if outs_during_play == _UNFINISHED_PLAY else outs_during_play,
        dead_ball_reason=played.maybe_coded("Dead Ball Reason", DeadBallReason),
        runners=runners,
        pitch=pitch,
        contact=contact,
        fielding=fielder,
    )


def _inning_runs(root: _Node, key: str, inning: int, runs: int) -> tuple[int, ...] | None:
    if not root.has(key):
        return None
    value = root.value(key)
    if not isinstance(value, list):
        raise root.error("expected a list", key)
    innings = [root.as_integer(item, key) for item in cast("list[object]", value)]
    if runs and 0 < inning <= len(innings):
        innings[inning - 1] += runs
    return tuple(innings)

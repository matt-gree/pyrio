"""Rio web's responses into models: one function per endpoint.

This is the only module that knows Rio web's response keys. The shapes are
ProjectRio-web's route code at ``d4bf233`` (``app/views/*.py``). A missing key
the route always writes raises :class:`APIResponseError` naming the endpoint
and the keys that were there; keys this module doesn't read are ignored, so
the server can add fields without breaking clients.
"""

from __future__ import annotations

from dataclasses import dataclass, replace
from datetime import UTC, datetime
from typing import TYPE_CHECKING, TypeVar, cast

from .._characters import Character
from .._codes import (
    AtBatResult,
    Bases,
    ChargeType,
    ContactType,
    Hand,
    InputDirection,
    ManualSelect,
    OutType,
    PitchType,
    Position,
    Side,
    Stadium,
    StealType,
    SwingType,
)
from .._enum import CodeEnum
from .._errors import UnknownCodeError
from .._stats import BattingLine, PitchingLine
from ._errors import APIResponseError
from ._models import (
    Community,
    CommunityKind,
    CommunityMember,
    ContactLine,
    EventRef,
    FieldingLine,
    GameSummary,
    IssuedKey,
    LadderGame,
    LadderRow,
    LandingRow,
    Linescore,
    LiveGame,
    LiveTeam,
    PlayRunner,
    RatingUpdate,
    RecordLine,
    ScoringPlay,
    StarChanceRow,
    StatRow,
    Tag,
    TagKind,
    TagSet,
    TagSetKind,
    TeamSummary,
    User,
)

if TYPE_CHECKING:
    from collections.abc import Callable, Iterator

E = TypeVar("E", bound=CodeEnum)
L = TypeVar("L", TagKind, TagSetKind, CommunityKind)


# --- a typed view over one JSON object ---------------------------------------


class _Obj:
    """One JSON object from ``endpoint``, read key by key with types checked."""

    __slots__ = ("_data", "endpoint", "where")

    def __init__(self, endpoint: str, data: object, where: str = "response") -> None:
        if not isinstance(data, dict):
            raise APIResponseError(
                f"{endpoint}: expected a JSON object at {where}, got {_kind(data)}"
            )
        self._data = cast(dict[str, object], data)
        self.endpoint = endpoint
        self.where = where

    def __contains__(self, key: str) -> bool:
        return key in self._data

    def items(self) -> Iterator[tuple[str, object]]:
        return iter(self._data.items())

    def raw(self, key: str) -> object:
        try:
            return self._data[key]
        except KeyError:
            raise APIResponseError(
                f"{self.endpoint}: {self.where} has no {key!r} key; present: {sorted(self._data)}"
            ) from None

    def fail(self, key: str, expected: str, value: object) -> APIResponseError:
        return APIResponseError(
            f"{self.endpoint}: expected {expected} at {self.where}[{key!r}], got {_kind(value)}"
        )

    def int(self, key: str) -> int:
        value = self.raw(key)
        if isinstance(value, bool) or not isinstance(value, int):
            raise self.fail(key, "an integer", value)
        return value

    def opt_int(self, key: str) -> int | None:
        return None if self.raw(key) is None else self.int(key)

    def count(self, key: str) -> int:
        """A SQL ``SUM``/``COUNT``: an integer, where ``null`` (a sum over nothing) is 0."""
        return 0 if self.raw(key) is None else self.int(key)

    def count_or_zero(self, key: str) -> int:
        """A count from a query that writes no row when nothing matched: absent means 0."""
        return self.count(key) if key in self._data else 0

    def float(self, key: str) -> float:
        value = self.raw(key)
        if isinstance(value, bool) or not isinstance(value, int | float):
            raise self.fail(key, "a number", value)
        return float(value)

    def opt_float(self, key: str) -> float | None:
        return None if self.raw(key) is None else self.float(key)

    def str(self, key: str) -> str:
        value = self.raw(key)
        if not isinstance(value, str):
            raise self.fail(key, "a string", value)
        return value

    def opt_str(self, key: str) -> str | None:
        return None if self.raw(key) is None else self.str(key)

    def bool(self, key: str) -> bool:
        value = self.raw(key)
        if not isinstance(value, bool):
            raise self.fail(key, "true or false", value)
        return value

    def flag(self, key: str) -> bool:
        """A nullable boolean column, where ``null`` means false."""
        return False if self.raw(key) is None else self.bool(key)

    def obj(self, key: str) -> _Obj:
        return _Obj(self.endpoint, self.raw(key), f"{self.where}[{key!r}]")

    def list(self, key: str) -> list[object]:
        value = self.raw(key)
        if not isinstance(value, list):
            raise self.fail(key, "a list", value)
        return cast(list[object], value)

    def objs(self, key: str) -> list[_Obj]:
        return [
            _Obj(self.endpoint, item, f"{self.where}[{key!r}][{i}]")
            for i, item in enumerate(self.list(key))
        ]

    def code(self, key: str, kind: type[E]) -> E:
        value = self.int(key)
        try:
            return kind(value)
        except UnknownCodeError:
            raise self.fail(key, f"a {kind.__name__} id", value) from None

    def opt_code(self, key: str, kind: type[E]) -> E | None:
        return None if self.raw(key) is None else self.code(key, kind)

    def label(self, key: str, kind: type[L]) -> L:
        value = self.str(key)
        try:
            return kind(value)
        except ValueError:
            raise self.fail(key, f"a {kind.__name__}", value) from None

    def character(self, key: str) -> Character:
        """A character by its canonical name, as Rio web writes it."""
        value = self.str(key)
        try:
            return Character(value)
        except UnknownCodeError:
            raise self.fail(key, "a character name", value) from None

    def opt_character(self, key: str) -> Character | None:
        return None if self.raw(key) is None else self.character(key)

    def hand(self, key: str) -> Hand:
        """A handedness stored as a boolean column: false is right, true is left."""
        value = self.raw(key)
        if isinstance(value, bool):
            return Hand.LEFT if value else Hand.RIGHT
        return self.code(key, Hand)

    def time(self, key: str) -> datetime:
        return datetime.fromtimestamp(self.int(key), UTC)

    def opt_time(self, key: str) -> datetime | None:
        return None if self.raw(key) is None else self.time(key)


def _kind(value: object) -> str:
    return "null" if value is None else type(value).__name__


def _int_key(endpoint: str, key: str, where: str) -> int:
    """A JSON object key that the server wrote from an integer."""
    try:
        return int(key)
    except ValueError:
        raise APIResponseError(
            f"{endpoint}: expected an integer key at {where}, got {key!r}"
        ) from None


def _list(endpoint: str, data: object, where: str = "response") -> list[object]:
    if not isinstance(data, list):
        raise APIResponseError(f"{endpoint}: expected a JSON list at {where}, got {_kind(data)}")
    return cast(list[object], data)


def _code_from(endpoint: str, value: object, kind: type[E], where: str) -> E:
    if isinstance(value, bool) or not isinstance(value, int):
        raise APIResponseError(f"{endpoint}: expected a {kind.__name__} id at {where}")
    try:
        return kind(value)
    except UnknownCodeError:
        raise APIResponseError(
            f"{endpoint}: {value!r} at {where} is not a {kind.__name__} id"
        ) from None


# --- /games/ ----------------------------------------------------------------


def games(data: object) -> list[GameSummary]:
    """``GET /games/``: ``{"games": [...]}`` (``views/games.py``, ``endpoint_games``)."""
    body = _Obj("/games/", data)
    return [_game(game) for game in body.objs("games")]


def _game(game: _Obj) -> GameSummary:
    linescore = _linescore(game) if "linescore" in game else None
    scoring_plays = (
        tuple(_scoring_play(play) for play in game.objs("scoring_plays"))
        if "scoring_plays" in game
        else None
    )
    return GameSummary(
        game_id=game.int("game_id"),
        stadium=game.code("stadium", Stadium),
        start_time=game.time("date_time_start"),
        end_time=game.time("date_time_end"),
        away=_team(game, "away"),
        home=_team(game, "home"),
        innings_played=game.int("innings_played"),
        innings_selected=game.int("innings_selected"),
        tag_set_id=game.opt_int("game_mode"),
        ratings=_ratings(game),
        linescore=linescore,
        scoring_plays=scoring_plays,
    )


def _team(game: _Obj, side: str) -> TeamSummary:
    roster_key = f"{side}_roster"
    roster = game.list(roster_key)
    characters: list[Character] = []
    for spot, value in enumerate(roster):
        if value is None:
            raise APIResponseError(
                f"{game.endpoint}: game {game.raw('game_id')} has no character "
                f"at {roster_key}[{spot}]"
            )
        characters.append(_code_from(game.endpoint, value, Character, f"{roster_key}[{spot}]"))
    return TeamSummary(
        player=game.str(f"{side}_user"),
        captain=game.character(f"{side}_captain"),
        roster=tuple(characters),
        score=game.int(f"{side}_score"),
    )


def _ratings(row: _Obj) -> RatingUpdate | None:
    winner_before = row.opt_int("winner_incoming_elo")
    loser_before = row.opt_int("loser_incoming_elo")
    if winner_before is None or loser_before is None:
        return None
    return RatingUpdate(
        winner_before=winner_before,
        loser_before=loser_before,
        winner_after=row.opt_int("winner_result_elo"),
        loser_after=row.opt_int("loser_result_elo"),
    )


def _linescore(game: _Obj) -> Linescore:
    halves = game.list("linescore")
    if len(halves) != 2:
        raise game.fail("linescore", "[away, home]", halves)
    away = _list(game.endpoint, halves[0], "linescore[0]")
    home = _list(game.endpoint, halves[1], "linescore[1]")
    if not all(isinstance(r, int) and not isinstance(r, bool) for r in away):
        raise game.fail("linescore", "run counts", away)
    home_runs: list[int | None] = []
    for runs in home:
        if runs == "X":
            home_runs.append(None)
        elif isinstance(runs, int) and not isinstance(runs, bool):
            home_runs.append(runs)
        else:
            raise game.fail("linescore", "run counts or 'X'", home)
    return Linescore(away=tuple(cast(list[int], away)), home=tuple(home_runs))


def _scoring_play(play: _Obj) -> ScoringPlay:
    runners: list[PlayRunner | None] = []
    for i, value in enumerate(play.list("runners")):
        if value is None:
            runners.append(None)
            continue
        runner = _Obj(play.endpoint, value, f"{play.where}['runners'][{i}]")
        runners.append(
            PlayRunner(
                character=runner.code("char_id", Character),
                initial_base=runner.int("initial_base"),
                result_base=runner.int("result_base"),
                out_type=runner.code("out_type", OutType),
                out_location=runner.int("out_location"),
                steal=runner.code("steal", StealType),
            )
        )
    return ScoringPlay(
        inning=play.int("inning"),
        batting_side=_half_inning(play, "half_inning"),
        event_num=play.int("event_num"),
        runs=play.int("result_rbi"),
        result=play.code("result_of_ab", AtBatResult),
        batter=play.code("batter", Character),
        pitcher=play.code("pitcher", Character),
        away_score=play.int("away_score"),
        home_score=play.int("home_score"),
        outs=play.int("outs"),
        runners=tuple(runners),
    )


def _half_inning(row: _Obj, key: str) -> Side:
    """Rio web's ``half_inning``: 0 is the top (away batting), 1 the bottom."""
    value = row.int(key)
    if value not in (0, 1):
        raise row.fail(key, "0 or 1", value)
    return Side.AWAY if value == 0 else Side.HOME


# --- /ladder/games/ ---------------------------------------------------------


def ladder_games(data: object) -> list[LadderGame]:
    """``GET /ladder/games/``: ``{"games": [...]}`` (``stat_retrieval.endpoint_ladder_games``).

    Every game column comes from a LEFT JOIN, so each may be ``null``.
    """
    body = _Obj("/ladder/games/", data)
    rows: list[LadderGame] = []
    for row in body.objs("games"):
        ratings = _ratings(row)
        if ratings is None:
            raise row.fail("winner_incoming_elo", "an integer", None)
        rows.append(
            LadderGame(
                tag_set_id=row.int("tag_set"),
                winner=row.opt_str("winner_player"),
                loser=row.opt_str("loser_player"),
                ratings=ratings,
                game_id=row.opt_int("game_id"),
                stadium=row.opt_code("stadium", Stadium),
                start_time=row.opt_time("date_time_start"),
                end_time=row.opt_time("date_time_end"),
                away_player=row.opt_str("away_player"),
                home_player=row.opt_str("home_player"),
                away_captain=row.opt_character("away_captain"),
                home_captain=row.opt_character("home_captain"),
                away_score=row.opt_int("away_score"),
                home_score=row.opt_int("home_score"),
                innings_played=row.opt_int("innings_played"),
                innings_selected=row.opt_int("innings_selected"),
            )
        )
    return rows


# --- /populate_db/ongoing_game/ ---------------------------------------------


def live_games(data: object) -> list[LiveGame]:
    """``GET /populate_db/ongoing_game/``: ``{"ongoing_games": [OngoingGame.to_dict()]}``."""
    body = _Obj("/populate_db/ongoing_game/", data)
    return [_live_game(game) for game in body.objs("ongoing_games")]


def _live_game(game: _Obj) -> LiveGame:
    bases = Bases(0)
    for key, base in (
        ("runner_on_first", Bases.FIRST),
        ("runner_on_second", Bases.SECOND),
        ("runner_on_third", Bases.THIRD),
    ):
        if game.flag(key):
            bases |= base
    return LiveGame(
        away=_live_team(game, "away"),
        home=_live_team(game, "home"),
        tag_set_id=game.int("tag_set"),
        stadium=game.code("stadium_id", Stadium),
        start_time=game.time("start_time"),
        innings_selected=game.int("innings_selected"),
        inning=game.int("inning"),
        batting_side=_half_inning(game, "half_inning"),
        outs=game.int("outs"),
        bases=bases,
        is_star_chance=game.flag("star_chance"),
        batter_spot=game.int("batter"),
        pitcher_spot=game.int("pitcher"),
    )


def _live_team(game: _Obj, side: str) -> LiveTeam:
    roster = tuple(game.code(f"{side}_roster_{spot}_char", Character) for spot in range(9))
    runs = game.raw(f"{side}_inning_scores")
    inning_runs = (
        ()
        if runs is None
        else tuple(
            _int_value(game, f"{side}_inning_scores", r)
            for r in _list(game.endpoint, runs, f"{side}_inning_scores")
        )
    )
    return LiveTeam(
        player=game.str(f"{side}_player"),
        roster=roster,
        score=game.int(f"{side}_score"),
        stars=game.int(f"{side}_stars"),
        inning_runs=inning_runs,
    )


def _int_value(row: _Obj, key: str, value: object) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        raise row.fail(key, "integers", value)
    return value


# --- /events/ ---------------------------------------------------------------


def event_ids(data: object) -> list[EventRef]:
    """``GET /events/``: ``{game_id: {event_num: event_id}}`` (``endpoint_event``).

    A bare object keyed by game id; there is no ``"events"`` key. Returned in
    game and event order.
    """
    body = _Obj("/events/", data)
    refs: list[EventRef] = []
    for game_key, _ in body.items():
        game_id = _int_key(body.endpoint, game_key, "the top level")
        events = body.obj(game_key)
        for event_key, _ in events.items():
            refs.append(
                EventRef(
                    game_id=game_id,
                    event_num=_int_key(body.endpoint, event_key, events.where),
                    event_id=events.int(event_key),
                )
            )
    refs.sort(key=lambda ref: (ref.game_id, ref.event_num))
    return refs


# --- /star_chances/ ---------------------------------------------------------


def star_chances(data: object, *, by_inning: bool) -> list[StarChanceRow]:
    """``GET /star_chances/``: ``{"Data": [...]}``, or ``{}`` when no event matched."""
    body = _Obj("/star_chances/", data)
    if not any(True for _ in body.items()):
        return []
    rows: list[StarChanceRow] = []
    for row in body.objs("Data"):
        rows.append(
            StarChanceRow(
                inning=row.int("inning") if by_inning else None,
                batting_side=_half_inning(row, "half_inning") if by_inning else None,
                eligible_events=row.count("eligible_event"),
                star_chances=row.count("star_chances"),
                plate_appearances=row.count("total_events"),
                pitcher_wins=row.count("pitcher_win"),
                batter_wins=row.count("batter_win"),
                games=row.count("games"),
            )
        )
    return rows


# --- /landing_data/ ---------------------------------------------------------


def landing_data(data: object) -> list[LandingRow]:
    """``GET /landing_data/``: ``{"Data": [...]}``, or ``{}`` when no event matched."""
    body = _Obj("/landing_data/", data)
    if not any(True for _ in body.items()):
        return []
    return [_landing_row(row) for row in body.objs("Data")]


def _landing_row(row: _Obj) -> LandingRow:
    position = row.opt_int("fielder_position")
    return LandingRow(
        game_id=row.int("game_id"),
        event_num=row.int("event_num"),
        result=row.code("final_result", AtBatResult),
        chem_links=row.int("chem_links_ob"),
        batter=row.code("batter_char_id", Character),
        pitcher=row.code("pitcher_char_id", Character),
        fielder=row.opt_code("fielder_char_id", Character),
        batter_player=row.str("batter_username"),
        pitcher_player=row.str("pitcher_username"),
        batting_hand=row.hand("batting_hand"),
        pitching_hand=row.hand("fielding_hand"),
        pitch_type=row.code("pitch_type", PitchType),
        charge_type=row.code("charge_pitch_type", ChargeType),
        swing=row.code("type_of_swing", SwingType),
        contact=row.opt_code("type_of_contact", ContactType),
        power=row.int("ball_power"),
        # Rio web stores the stat file's "Vert Angle" in ball_horiz_angle and
        # "Horiz Angle" in ball_vert_angle (populate_db.py:701-702), so each is
        # read from the other's column.
        vertical_angle=row.int("ball_horiz_angle"),
        horizontal_angle=row.int("ball_vert_angle"),
        contact_absolute=row.float("contact_absolute"),
        contact_quality=row.float("contact_quality"),
        rng1=row.float("rng1"),
        rng2=row.float("rng2"),
        rng3=row.float("rng3"),
        ball_velocity_x=row.float("ball_x_velocity"),
        ball_velocity_y=row.float("ball_y_velocity"),
        ball_velocity_z=row.float("ball_z_velocity"),
        contact_location_x=row.float("ball_x_contact_pos"),
        contact_location_z=row.float("ball_z_contact_pos"),
        landing_location_x=row.float("ball_x_landing_pos"),
        landing_location_y=row.float("ball_y_landing_pos"),
        landing_location_z=row.float("ball_z_landing_pos"),
        max_height=row.float("ball_max_height"),
        hang_time=row.float("ball_hang_time"),
        stick=_stick(row),
        charge_power_up=row.float("charge_power_up"),
        charge_power_down=row.float("charge_power_down"),
        swing_frame=row.int("frame_of_swing"),
        bat_contact_location_x=row.float("bat_x_contact_pos"),
        bat_contact_location_z=row.float("bat_z_contact_pos"),
        # The game writes 0xFF for "no position".
        fielder_position=None
        if position in (None, 0xFF)
        else row.code("fielder_position", Position),
        fielder_location_x=row.opt_float("fielder_x_pos"),
        fielder_location_y=row.opt_float("fielder_y_pos"),
        fielder_location_z=row.opt_float("fielder_z_pos"),
        fielder_jump=row.opt_int("fielder_jump"),
        manual_select=row.opt_code("manual_select_state", ManualSelect),
    )


def _stick(row: _Obj) -> InputDirection:
    value = row.int("stick_input")
    try:
        return InputDirection(value)
    except UnknownCodeError:
        raise row.fail("stick_input", "a stick bitmask", value) from None


# --- /stats/ ----------------------------------------------------------------


@dataclass(frozen=True, slots=True, kw_only=True)
class StatsShape:
    """The ``by_*`` and ``include_*`` flags a ``/stats/`` request sent.

    The response nests one level per grouping flag, so walking it needs them.
    """

    by_game: bool = False
    by_user: bool = False
    by_roster_spot: bool = False
    by_character: bool = False
    by_batting_hand: bool = False
    by_pitching_hand: bool = False
    by_swing: bool = False
    include_pitcher_wins: bool = False
    include_runs_scored: bool = False


@dataclass(frozen=True, slots=True, kw_only=True)
class _Key:
    game_id: int | None = None
    user: str | None = None
    roster_spot: int | None = None
    character: Character | None = None


# The server's names for batting's summary columns, mapped once to BattingLine's.
_BATTING = {
    "at_bats": "summary_at_bats",
    "hits": "summary_hits",
    "singles": "summary_singles",
    "doubles": "summary_doubles",
    "triples": "summary_triples",
    "home_runs": "summary_homeruns",
    "walks": "summary_walks_bb",
    "hit_by_pitch": "summary_walks_hbp",
    "strikeouts": "summary_strikeouts",
    "sac_flies": "summary_sac_flys",
    "rbi": "summary_rbi",
    "stolen_bases": "summary_bases_stolen",
    "star_hits": "star_hits",
}
# Batting's per-pitch counts. The query writes them only for groups with a pitch.
_CONTACT = {
    "plate_appearances": "plate_appearances",
    "strikeouts": "strikeouts",
    "outs": "outs",
    "foul_contacts": "foul_hits",
    "fair_contacts": "fair_hits",
    "sour_contacts": "sour_hits",
    "nice_contacts": "nice_hits",
    "perfect_contacts": "perfect_hits",
    "singles": "singles",
    "doubles": "doubles",
    "triples": "triples",
    "home_runs": "homeruns",
    "sac_flies": "sacflys",
    "double_plays": "gidps",
    "rbi": "rbi",
}
_PITCHING = {
    "batters_faced": "batters_faced",
    "outs_pitched": "outs_pitched",
    "hits_allowed": "hits_allowed",
    "runs_allowed": "runs_allowed",
    "walks": "walks_bb",
    "hit_by_pitch": "walks_hbp",
    "strikeouts": "strikeouts_pitched",
    "pitches_thrown": "total_pitches",
    "star_pitches_thrown": "star_pitches_thrown",
}
_RECORD = {
    "away_wins": "away_wins",
    "away_losses": "away_loses",
    "home_wins": "home_wins",
    "home_losses": "home_loses",
    "games": "game_appearances",
}
_POSITIONS = {
    Position.PITCHER: "p",
    Position.CATCHER: "c",
    Position.FIRST_BASE: "1b",
    Position.SECOND_BASE: "2b",
    Position.THIRD_BASE: "3b",
    Position.SHORTSTOP: "ss",
    Position.LEFT_FIELD: "lf",
    Position.CENTER_FIELD: "cf",
    Position.RIGHT_FIELD: "rf",
}
# Fielding's per-play counts. The query writes them only for groups that fielded a ball.
_FIELDING_PLAYS = {
    "jump_catches": "jump_catches",
    "sliding_catches": "diving_catches",
    "wall_jumps": "wall_jumps",
    "swaps": "swap_successes",
    "bobbles": "bobbles",
}
_CATEGORIES = ("Batting", "Pitching", "Fielding", "Misc")


def stats(data: object, shape: StatsShape) -> list[StatRow]:
    """``GET /stats/``: ``{"Stats": ...}`` nested by the request's flags.

    The nesting is ``[game_id] → [username] → [roster_loc] → [char_name] →``
    section, each level present only when its ``by_*`` flag was sent
    (``stat_retrieval.update_detailed_stats_dict``). Under ``Batting`` come the
    batting-hand names, then the swing names; under ``Pitching``, the pitching
    hand names.
    """
    body = _Obj("/stats/", data)
    levels = [
        level
        for level, on in (
            ("game", shape.by_game),
            ("user", shape.by_user),
            ("spot", shape.by_roster_spot),
            ("character", shape.by_character),
        )
        if on
    ]
    rows: list[StatRow] = []
    for key, sections in _descend(body.obj("Stats"), levels, _Key()):
        rows.extend(_stat_rows(key, sections, shape))
    return rows


def _descend(node: _Obj, levels: list[str], key: _Key) -> Iterator[tuple[_Key, _Obj]]:
    """Each group's sections, with the grouping keys collected on the way down."""
    if not levels:
        yield key, node
        return
    level, rest = levels[0], levels[1:]
    for name, _ in node.items():
        if level == "game":
            child = replace(key, game_id=_int_key(node.endpoint, name, node.where))
        elif level == "user":
            child = replace(key, user=name)
        elif level == "spot":
            child = replace(key, roster_spot=_int_key(node.endpoint, name, node.where))
        else:
            child = replace(key, character=_char_key(node, name))
        yield from _descend(node.obj(name), rest, child)


def _char_key(node: _Obj, name: str) -> Character:
    try:
        return Character(name)
    except UnknownCodeError:
        raise APIResponseError(
            f"{node.endpoint}: {name!r} at {node.where} is not a character name"
        ) from None


def _labelled(node: _Obj, kind: type[E]) -> Iterator[tuple[E, _Obj]]:
    """The sub-objects of ``node`` keyed by a coded value's label, such as ``"Slap"``."""
    for name, value in node.items():
        if not isinstance(value, dict):
            continue
        try:
            member = kind(name)
        except UnknownCodeError:
            raise APIResponseError(
                f"{node.endpoint}: {name!r} at {node.where} is not a {kind.__name__}"
            ) from None
        yield member, node.obj(name)


def _stat_rows(key: _Key, sections: _Obj, shape: StatsShape) -> Iterator[StatRow]:
    unknown = [name for name, _ in sections.items() if name not in _CATEGORIES]
    if unknown:
        raise APIResponseError(
            f"{sections.endpoint}: expected sections {list(_CATEGORIES)} at "
            f"{sections.where}, got {unknown}; check the request's by_* flags"
        )
    common = {
        "game_id": key.game_id,
        "user": key.user,
        "roster_spot": key.roster_spot,
        "character": key.character,
    }
    group: dict[str, object] = {}

    if "Batting" in sections:
        batting = sections.obj("Batting")
        if shape.by_batting_hand:
            for hand, split in _labelled(batting, Hand):
                yield StatRow(**common, batting_hand=hand, **_batting(split, shape))  # type: ignore[arg-type]
        else:
            group.update(_batting(batting, shape))

    if "Pitching" in sections:
        pitching = sections.obj("Pitching")
        if shape.by_pitching_hand:
            for hand, split in _labelled(pitching, Hand):
                yield StatRow(**common, pitching_hand=hand, **_pitching(split, shape))  # type: ignore[arg-type]
        else:
            group.update(_pitching(pitching, shape))

    if "Fielding" in sections:
        group["fielding"] = _fielding(sections.obj("Fielding"))
    if "Misc" in sections:
        misc = sections.obj("Misc")
        group["record"] = RecordLine(**{field: misc.count(name) for field, name in _RECORD.items()})

    if group:
        yield StatRow(**common, **group)  # type: ignore[arg-type]


def _contact(node: _Obj) -> ContactLine:
    return ContactLine(**{field: node.count_or_zero(name) for field, name in _CONTACT.items()})


def _batting(node: _Obj, shape: StatsShape) -> dict[str, object]:
    line = BattingLine(**{field: node.count(name) for field, name in _BATTING.items()})
    by_swing: dict[SwingType, ContactLine] | None = None
    if shape.by_swing:
        by_swing = {swing: _contact(split) for swing, split in _labelled(node, SwingType)}
        contact = sum(by_swing.values(), ContactLine())
    else:
        contact = _contact(node)
    return {
        "batting": line,
        "contact": contact,
        "contact_by_swing": by_swing,
        "runs_scored": node.count("runs_scored") if shape.include_runs_scored else None,
    }


def _pitching(node: _Obj, shape: StatsShape) -> dict[str, object]:
    return {
        "pitching": PitchingLine(**{field: node.count(name) for field, name in _PITCHING.items()}),
        "balls_thrown": node.count_or_zero("balls"),
        "strikes_thrown": node.count_or_zero("strikes"),
        "pitcher_wins": node.count("pitcher_wins") if shape.include_pitcher_wins else None,
    }


def _fielding(node: _Obj) -> FieldingLine:
    return FieldingLine(
        pitches_at={pos: node.count(f"pitches_per_{name}") for pos, name in _POSITIONS.items()},
        outs_at={pos: node.count(f"outs_per_{name}") for pos, name in _POSITIONS.items()},
        big_plays=node.count("big_plays"),
        **{field: node.count_or_zero(name) for field, name in _FIELDING_PLAYS.items()},
    )


# --- reference data ---------------------------------------------------------


def users(data: object) -> list[User]:
    """``GET /user/all/``: ``{"users": {id: username}}``."""
    body = _Obj("/user/all/", data)
    listing = body.obj("users")
    return [
        User(id=_int_key(body.endpoint, key, listing.where), name=listing.str(key))
        for key, _ in listing.items()
    ]


def _tag(tag: _Obj) -> Tag:
    return Tag(
        id=tag.int("id"),
        name=tag.str("name"),
        kind=tag.label("type", TagKind),
        description=tag.opt_str("desc"),
        community_id=tag.opt_int("comm_id"),
        is_active=tag.flag("active"),
        created_at=tag.opt_time("date_created"),
        gecko_code=(tag.opt_str("gecko_code") or None) if "gecko_code" in tag else None,
        gecko_code_description=(
            (tag.opt_str("gecko_code_desc") or None) if "gecko_code_desc" in tag else None
        ),
    )


def tags(endpoint: str, key: str) -> Callable[[object], list[Tag]]:
    """A decoder for ``{key: [tag, ...]}``, the shape of ``/tag/list`` and ``/community/tags``."""

    def decode(data: object) -> list[Tag]:
        return [_tag(tag) for tag in _Obj(endpoint, data).objs(key)]

    return decode


def tag(data: object) -> Tag:
    """``POST /tag/create``: the new tag's ``Tag.to_dict()``."""
    return _tag(_Obj("/tag/create", data))


def _tag_set(row: _Obj) -> TagSet:
    return TagSet(
        id=row.int("id"),
        name=row.str("name"),
        kind=row.label("type", TagSetKind),
        community_id=row.opt_int("comm_id"),
        start_time=row.time("start_date"),
        end_time=row.time("end_date"),
        tags=tuple(_tag(tag) for tag in row.objs("tags")),
        community_kind=row.label("comm_type", CommunityKind) if "comm_type" in row else None,
    )


def tag_sets(data: object) -> list[TagSet]:
    """``POST /tag_set/list``: ``{"Tag Sets": [...]}``."""
    return [_tag_set(row) for row in _Obj("/tag_set/list", data).objs("Tag Sets")]


def tag_set(data: object) -> TagSet:
    """``GET /tag_set/<id>``: ``{"Tag Set": [tag_set]}``, a one-item list."""
    body = _Obj("/tag_set/<id>", data)
    rows = body.objs("Tag Set")
    if len(rows) != 1:
        raise body.fail("Tag Set", "a one-item list", rows)
    return _tag_set(rows[0])


def created_tag_set(data: object) -> TagSet:
    """``POST /tag_set/create``: the new tag set's ``TagSet.to_dict()``."""
    return _tag_set(_Obj("/tag_set/create", data))


def ladder(data: object) -> list[LadderRow]:
    """``POST /tag_set/ladder/``: ``{username: {...}}``, ordered here by rating, highest first."""
    body = _Obj("/tag_set/ladder/", data)
    rows = [
        LadderRow(
            user=row.str("username"),
            rating=row.int("rating"),
            wins=row.count("num_wins"),
            losses=row.count("num_losses"),
            ties=row.count("num_ties"),
        )
        for row in (body.obj(name) for name, _ in body.items())
    ]
    rows.sort(key=lambda row: (-row.rating, row.user.casefold()))
    return rows


def _community(row: _Obj) -> Community:
    return Community(
        id=row.int("id"),
        name=row.str("name"),
        kind=row.label("type", CommunityKind),
        is_private=row.flag("private"),
        url=row.opt_str("url"),
        description=row.opt_str("desc"),
        tag_set_limit=row.opt_int("tag_set_limit"),
        created_at=row.opt_time("date_created"),
    )


def communities(endpoint: str, key: str) -> Callable[[object], list[Community]]:
    """A decoder for ``{key: [community, ...]}`` (``Community.to_dict()``)."""

    def decode(data: object) -> list[Community]:
        return [_community(row) for row in _Obj(endpoint, data).objs(key)]

    return decode


def _member(row: _Obj) -> CommunityMember:
    return CommunityMember(
        id=row.int("id"),
        user_id=row.int("user_id"),
        is_admin=row.flag("admin"),
        is_active=row.flag("active"),
        was_invited=row.flag("invited"),
        is_banned=row.flag("banned"),
        joined_at=row.opt_time("date_joined"),
        key=row.opt_str("community_key") if "community_key" in row else None,
        key_created_at=row.opt_time("date_key_created") if "date_key_created" in row else None,
    )


def members(endpoint: str, key: str) -> Callable[[object], list[CommunityMember]]:
    """A decoder for ``{key: [member, ...]}`` (``CommunityUser.to_dict()``)."""

    def decode(data: object) -> list[CommunityMember]:
        return [_member(row) for row in _Obj(endpoint, data).objs(key)]

    return decode


def community_key(data: object) -> CommunityMember:
    """``POST /community/key`` for the caller: a bare one-item list holding their row."""
    endpoint = "/community/key"
    rows = _list(endpoint, data)
    if len(rows) != 1:
        raise APIResponseError(f"{endpoint}: expected a one-item list, got {len(rows)} items")
    return _member(_Obj(endpoint, rows[0], "response[0]"))


def all_community_keys(data: object) -> dict[str, str]:
    """``POST /community/key`` with ``generate_all``: ``[{"user", "comm_key"}, ...]``."""
    endpoint = "/community/key"
    keys: dict[str, str] = {}
    for i, value in enumerate(_list(endpoint, data)):
        row = _Obj(endpoint, value, f"response[{i}]")
        keys[row.str("user")] = row.str("comm_key")
    return keys


def left_community(data: object) -> CommunityMember:
    """``POST /community/leave``: ``{"community name", "member"}``."""
    return _member(_Obj("/community/leave", data).obj("member"))


def joined_community(data: object) -> bool:
    """``POST /community/join``: ``{"community name", "active"}``; whether membership is active."""
    return _Obj("/community/join", data).flag("active")


def created_community(data: object) -> str | None:
    """``POST /community/create``: ``{"community_name", "private", "active_url"}``."""
    return _Obj("/community/create", data).opt_str("active_url")


def invited(data: object) -> list[str]:
    """``POST /community/invite``: ``{"Invited Users": [username, ...]}``."""
    return _strings(_Obj("/community/invite", data), "Invited Users")


def sponsor(data: object) -> str | None:
    """``POST /community/sponsor``: ``{"sponsor": username or null}``."""
    return _Obj("/community/sponsor", data).opt_str("sponsor")


def group_members(data: object) -> list[str]:
    """``GET /user_group/members``: ``{"users": [username, ...]}``."""
    return _strings(_Obj("/user_group/members", data), "users")


def is_group_member(data: object) -> bool:
    """``GET /user_group/check_for_member``: ``{"is_member": bool}``."""
    return _Obj("/user_group/check_for_member", data).bool("is_member")


def _strings(body: _Obj, key: str) -> list[str]:
    values = body.list(key)
    if not all(isinstance(v, str) for v in values):
        raise body.fail(key, "a list of strings", values)
    return cast(list[str], values)


def login(data: object) -> tuple[str, str]:
    """``POST /login/``: ``{"msg", "username", "access_token"}`` as (username, token)."""
    body = _Obj("/login/", data)
    return body.str("username"), body.str("access_token")


def issued_key(endpoint: str) -> Callable[[object], IssuedKey]:
    """A decoder for ``/api_key/register/`` and ``/api_key/reset/``.

    Both answer ``{"api_key", "email_sent"}``.
    """

    def decode(data: object) -> IssuedKey:
        body = _Obj(endpoint, data)
        return IssuedKey(key=body.str("api_key"), was_emailed=body.bool("email_sent"))

    return decode


def game_history_id(data: object) -> int:
    """``POST /manual_submit_game/``: ``{"game_history_id": id}``."""
    return _Obj("/manual_submit_game/", data).int("game_history_id")


def ignore(data: object) -> None:
    """For routes that answer a bare ``'Success'`` string or a message nobody needs."""
    del data


def as_is(data: object) -> object:
    """The escape hatch's decoder: the JSON, untouched."""
    return data

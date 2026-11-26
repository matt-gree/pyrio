"""What Rio web's responses decode into: frozen records reusing the core enums.

Every timestamp is a UTC-aware ``datetime``; convert it with ``.astimezone()``
for display. Grouping keys and optional sections are ``None`` when absent.
"""

from __future__ import annotations

from collections.abc import Mapping  # noqa: TC003 -- dataclass fields are resolved at runtime
from dataclasses import dataclass
from datetime import datetime  # noqa: TC003 -- dataclass fields are resolved at runtime
from enum import Enum

from .._characters import Character  # noqa: TC001
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
from .._game import leader
from .._stats import BattingLine, Line, PitchingLine
from .._team_names import TeamName  # noqa: TC001
from ..sim import HitInputs, Mod

__all__ = [
    "Community",
    "CommunityKind",
    "CommunityMember",
    "ContactLine",
    "EventRef",
    "FieldingLine",
    "GameSummary",
    "IssuedKey",
    "LadderGame",
    "LadderRow",
    "LandingRow",
    "Linescore",
    "LiveGame",
    "LiveTeam",
    "PlayRunner",
    "RatingUpdate",
    "RecordLine",
    "ScoringPlay",
    "StarChanceRow",
    "StatRow",
    "Tag",
    "TagKind",
    "TagSet",
    "TagSetKind",
    "TeamSummary",
    "User",
]


# --- kinds ------------------------------------------------------------------


class _Label(Enum):
    """A Rio web category, valued by the exact string the API uses."""

    value: str  # pyright: ignore[reportIncompatibleMethodOverride]

    def __str__(self) -> str:
        return self.value


class TagKind(_Label):
    """What a tag is for (Rio web's ``cTAG_TYPES``)."""

    COMPONENT = "Component"
    COMPETITION = "Competition"
    """Made by Rio web for each tag set; it can't be created directly."""
    COMMUNITY = "Community"
    """Made by Rio web for each community; it can't be created directly."""
    CLIENT_CODE = "Client Code"
    GECKO_CODE = "Gecko Code"
    TEST = "Test"


class TagSetKind(_Label):
    """What a tag set is (Rio web's ``cTAG_SET_TYPES``)."""

    SEASON = "Season"
    LEAGUE = "League"
    TOURNAMENT = "Tournament"
    CUSTOM = "Custom"
    TEST = "Test"


class CommunityKind(_Label):
    """Whether a community is run by Project Rio (Rio web's ``cCOMM_TYPES``)."""

    OFFICIAL = "Official"
    UNOFFICIAL = "Unofficial"


# --- lines -----------------------------------------------------------------


@dataclass(frozen=True, slots=True, kw_only=True)
class ContactLine(Line):
    """Batted-ball counts from Rio web's ``/stats/``, which stat files don't summarize.

    Counted per pitch the batter saw, so ``plate_appearances`` and
    ``strikeouts`` come from the same rows as the contact counts. With
    ``exclude_fouls``, foul contacts are left out of every count here.
    """

    plate_appearances: int = 0
    strikeouts: int = 0
    outs: int = 0
    """Batted balls that were outs."""
    foul_contacts: int = 0
    fair_contacts: int = 0
    """Batted balls that landed fair or were fielded."""
    sour_contacts: int = 0
    nice_contacts: int = 0
    perfect_contacts: int = 0
    singles: int = 0
    doubles: int = 0
    triples: int = 0
    home_runs: int = 0
    sac_flies: int = 0
    double_plays: int = 0
    """Ground-ball double plays."""
    rbi: int = 0

    @property
    def hits(self) -> int:
        """Singles, doubles, triples and home runs."""
        return self.singles + self.doubles + self.triples + self.home_runs


@dataclass(frozen=True, slots=True, kw_only=True)
class FieldingLine(Line):
    """Fielding counts from Rio web's ``/stats/``."""

    pitches_at: Mapping[Position, int]
    """Pitches spent at each position."""
    outs_at: Mapping[Position, int]
    """Outs made while at each position."""
    big_plays: int = 0
    jump_catches: int = 0
    sliding_catches: int = 0
    wall_jumps: int = 0
    swaps: int = 0
    """Successful swaps."""
    bobbles: int = 0


@dataclass(frozen=True, slots=True, kw_only=True)
class RecordLine(Line):
    """Wins and losses from Rio web's ``/stats/`` (its "Misc" section).

    Rio web counts one row per character in a game. Grouped by character or
    roster spot, or filtered to characters, each row counts; otherwise the
    server divides by nine so the numbers are games.
    """

    away_wins: int = 0
    away_losses: int = 0
    home_wins: int = 0
    home_losses: int = 0
    games: int = 0

    @property
    def wins(self) -> int:
        return self.away_wins + self.home_wins

    @property
    def losses(self) -> int:
        return self.away_losses + self.home_losses


@dataclass(frozen=True, slots=True, kw_only=True)
class StatRow:
    """One group of results from :meth:`RioClient.stats`.

    The grouping keys (``game_id``, ``user``, ``roster_spot``, ``character``)
    are set when the matching ``by_*`` flag was passed and ``None`` otherwise.

    A hand split is a grouping key too, but only for the section it splits:
    with ``by_batting_hand``, a group's batting arrives in one row per hand
    (``batting_hand`` set, the other sections ``None``) and its other sections
    in the row where ``batting_hand`` is ``None``. ``by_fielding_hand`` does the
    same for pitching.

    Rio web's ``/stats/`` doesn't report earned runs, home runs allowed or
    bunts yet, so until the server adds them ``pitching.earned_runs``,
    ``pitching.home_runs_allowed`` and ``batting.bunts`` are 0, and so is
    ``pitching.era``. They're read as soon as the server sends them
    (``earned_runs``, ``homeruns_allowed``, ``successful_bunts``).
    """

    game_id: int | None = None
    user: str | None = None
    roster_spot: int | None = None
    character: Character | None = None
    batting_hand: Hand | None = None
    fielding_hand: Hand | None = None

    batting: BattingLine | None = None
    contact: ContactLine | None = None
    """Batted-ball counts; with ``by_swing``, the sum over swings."""
    contact_by_swing: Mapping[SwingType, ContactLine] | None = None
    """Set only with ``by_swing``."""
    runs_scored: int | None = None
    """Set only with ``include_runs_scored``."""

    pitching: PitchingLine | None = None
    balls_thrown: int | None = None
    """Pitches outside the zone that the batter took."""
    strikes_thrown: int | None = None
    """Pitches in the zone that weren't hit, plus swings at pitches outside it."""
    pitcher_wins: int | None = None
    """Set only with ``include_pitcher_wins``."""

    fielding: FieldingLine | None = None
    record: RecordLine | None = None


# --- games ------------------------------------------------------------------


@dataclass(frozen=True, slots=True, kw_only=True)
class TeamSummary:
    """One side of a :class:`GameSummary`."""

    player: str
    captain: Character
    roster: tuple[Character, ...]
    """Indexed by roster spot, 0 to 8."""
    score: int


@dataclass(frozen=True, slots=True, kw_only=True)
class RatingUpdate:
    """The two players' ratings before and after a game counted toward a ladder.

    The ``*_after`` values are ``None`` until the result is accepted.
    """

    winner_before: int
    loser_before: int
    winner_after: int | None
    loser_after: int | None


@dataclass(frozen=True, slots=True, kw_only=True)
class Linescore:
    """Runs per inning for each side.

    ``home`` has ``None`` for a final half-inning the home side didn't need to
    bat (the box score's ``X``).
    """

    away: tuple[int, ...]
    home: tuple[int | None, ...]


@dataclass(frozen=True, slots=True, kw_only=True)
class PlayRunner:
    """A batter or runner on a :class:`ScoringPlay`."""

    character: Character
    initial_base: int
    """0 for the batter, 1 to 3 for a runner."""
    result_base: int
    """Where the play left them; 4 means they scored."""
    out_type: OutType
    out_base: int
    steal: StealType


@dataclass(frozen=True, slots=True, kw_only=True)
class ScoringPlay:
    """A play on which at least one run scored."""

    inning: int
    batting_side: Side
    event_number: int
    runs: int
    result: AtBatResult
    batter: Character
    pitcher: Character
    away_score: int
    """The away score when the play began."""
    home_score: int
    """The home score when the play began."""
    outs: int
    """Outs when the play began."""
    runners: tuple[PlayRunner | None, ...]
    """The batter, then the runners on first, second and third; ``None`` for an empty base."""


@dataclass(frozen=True, slots=True, kw_only=True)
class GameSummary:
    """A finished game, from :meth:`RioClient.games`."""

    game_id: int
    stadium: Stadium
    start_time: datetime
    end_time: datetime
    away: TeamSummary
    home: TeamSummary
    innings_played: int
    innings_selected: int
    tag_set_id: int | None
    """The tag set the game was played under (what the client calls its game mode);
    ``None`` when the game counted toward none. Name it with ``rio.tag_sets.get``."""
    ratings: RatingUpdate | None
    """``None`` when the game counted toward no ladder."""
    linescore: Linescore | None = None
    """Set only with ``include_linescore``."""
    scoring_plays: tuple[ScoringPlay, ...] | None = None
    """Set only with ``include_scoring_plays``."""

    @property
    def winner(self) -> Side | None:
        """The side with more runs, or ``None`` for a tie.

        Not a core ``GameResult``: ``/games/`` doesn't return who quit, so mercy,
        quits and crashes can't be told apart here.
        """
        return leader(self.away.score, self.home.score)

    def team(self, side: Side) -> TeamSummary:
        """The team on ``side``."""
        return self.home if side is Side.HOME else self.away


@dataclass(frozen=True, slots=True, kw_only=True)
class LadderGame:
    """A result counted toward a tag set's ladder, from ``rio.tag_sets.ladder_games``.

    A manually submitted result has no game behind it, so every game field is
    ``None`` for one.
    """

    tag_set_id: int
    winner: str | None
    loser: str | None
    ratings: RatingUpdate
    game_id: int | None
    stadium: Stadium | None
    start_time: datetime | None
    end_time: datetime | None
    away_player: str | None
    home_player: str | None
    away_captain: Character | None
    home_captain: Character | None
    away_score: int | None
    home_score: int | None
    innings_played: int | None
    innings_selected: int | None


@dataclass(frozen=True, slots=True, kw_only=True)
class LiveTeam:
    """One side of a :class:`LiveGame`."""

    player: str
    roster: tuple[Character, ...]
    captain_spot: int | None
    """The captain's roster spot (index into ``roster``)."""
    is_superstar: tuple[bool, ...]
    """Per roster spot; empty when the client didn't report it."""
    positions: tuple[Position | None, ...]
    """Where each roster spot is fielding; empty when the client didn't report it."""
    logo: TeamName | None
    score: int
    stars: int
    inning_runs: tuple[int, ...]

    @property
    def captain(self) -> Character | None:
        return None if self.captain_spot is None else self.roster[self.captain_spot]

    def fielder(self, position: Position) -> int | None:
        """The roster spot fielding ``position``, or ``None`` if none is reported."""
        for spot, at in enumerate(self.positions):
            if at is position:
                return spot
        return None


@dataclass(frozen=True, slots=True, kw_only=True)
class LiveGame:
    """A game in progress, from :meth:`RioClient.live_games`.

    Rio web gives a live game no id; the players and ``start_time`` identify it.
    """

    away: LiveTeam
    home: LiveTeam
    tag_set_id: int
    stadium: Stadium
    start_time: datetime
    innings_selected: int
    inning: int
    batting_side: Side
    outs: int
    bases: Bases
    """Occupied bases."""
    runner_spots: tuple[int | None, int | None, int | None]
    """The batting side's roster spot on first, second and third."""
    is_star_chance: bool
    chemistry_links_on_base: int | None
    batter_spot: int
    batting_hand: Hand | None
    pitcher_spot: int
    batter_line: BattingLine | None
    """The batter's game so far, when the client reported it."""
    pitcher_line: PitchingLine | None
    """The pitcher's game so far, when the client reported it."""
    loaded_from_hud: bool

    def team(self, side: Side) -> LiveTeam:
        return self.away if side is Side.AWAY else self.home

    @property
    def batter(self) -> Character:
        return self.team(self.batting_side).roster[self.batter_spot]

    @property
    def pitcher(self) -> Character:
        return self.team(self.batting_side.other).roster[self.pitcher_spot]


# --- events -----------------------------------------------------------------


@dataclass(frozen=True, slots=True, kw_only=True)
class EventRef:
    """Where an event lives: its game, its number in that game and its Rio web id."""

    game_id: int
    event_number: int
    event_id: int


@dataclass(frozen=True, slots=True, kw_only=True)
class StarChanceRow:
    """Star-chance counts, for all matching events or for one half-inning.

    ``inning`` and ``batting_side`` are set with ``by_inning`` and ``None``
    otherwise.
    """

    inning: int | None
    batting_side: Side | None
    eligible_events: int
    """Events with the bases empty, not the first of the game, and a side under five stars."""
    star_chances: int
    plate_appearances: int
    pitcher_wins: int
    """Star chances the pitcher won (the at-bat ended in an out or a walk)."""
    batter_wins: int
    """Star chances the batter won (a hit)."""
    games: int


@dataclass(frozen=True, slots=True, kw_only=True)
class LandingRow:
    """One batted ball, from :meth:`RioClient.landing_data`.

    Named as the stat-file model names the same values (``Contact``,
    ``Pitch``, ``Fielding``): world units, velocities per frame, raw angles.
    :meth:`hit_inputs` rebuilds the swing for :func:`pyrio.sim.simulate_hit`.
    """

    game_id: int
    event_number: int
    result: AtBatResult
    chemistry_links_on_base: int
    batter: Character
    pitcher: Character
    fielder: Character | None
    batter_player: str
    pitcher_player: str
    batting_hand: Hand
    pitching_hand: Hand
    pitch_type: PitchType
    charge_type: ChargeType
    swing: SwingType
    contact_type: ContactType | None
    power: int
    vertical_angle: int
    horizontal_angle: int
    contact_absolute: float
    contact_quality: float
    rng: tuple[int, int, int]
    """The three random numbers the game drew for the hit (``Contact.rng``)."""
    velocity: tuple[float, float, float]
    location: tuple[float, float]
    """Where the ball was when it met the bat, ``(x, z)`` (``Contact.location``)."""
    landing_location: tuple[float, float, float]
    max_height: float
    hang_frames: int
    input_direction: InputDirection
    charge_power_up: float
    charge_power_down: float
    swing_frame: int
    """The frame of the swing on which contact was made."""
    bat_location: tuple[float, float]
    """Where the batter held the bat, ``(x, z)`` (``Pitch.bat_location``)."""
    fielder_position: Position | None
    fielder_location: tuple[float, float, float] | None
    fielder_jumped: bool | None
    manual_select: ManualSelect | None

    def hit_inputs(
        self,
        *,
        stadium: Stadium,
        superstars: bool = False,
        mods: frozenset[Mod] = frozenset(),
    ) -> HitInputs:
        """The inputs that produced this batted ball, to simulate it again.

        Rio web serves neither the stadium, whether superstars were on, nor the
        gecko mods, so they're the caller's (from the game or its tag set).
        Raises ``ValueError`` for a star swing: the row has neither the team's
        stars nor the moonshot flag that decide which swing the game gave. Also
        for a row with no swing type: before Rio 2.3.0 that was a bunt, but from
        1.9.2 to 1.9.4 it was often any swing, and a row doesn't say which
        client wrote it. Use ``HitInputs.from_event`` on the stat file for both.
        """
        if self.swing is SwingType.NONE:
            raise ValueError(
                f"event {self.event_number} of game {self.game_id} has no swing type, which a "
                "landing row can't resolve: a bunt before Rio 2.3.0, or a 1.9.2-1.9.4 swing"
            )
        if self.swing is SwingType.STAR:
            raise ValueError(
                f"event {self.event_number} of game {self.game_id} is a star swing, which a "
                "landing row can't rebuild: it has no star count or moonshot flag"
            )
        return HitInputs(
            batter=self.batter,
            pitcher=self.pitcher,
            pitch_type=self.pitch_type,
            charge_type=self.charge_type if self.pitch_type is PitchType.CHARGE else None,
            swing=self.swing,
            batting_hand=self.batting_hand,
            input_direction=self.input_direction,
            batter_x=self.bat_location[0],
            ball_x=self.location[0],
            ball_z=self.location[1],
            charge_power_up=self.charge_power_up,
            charge_power_down=self.charge_power_down,
            swing_frame=self.swing_frame,
            chemistry_links_on_base=self.chemistry_links_on_base,
            batter_is_superstar=superstars,
            pitcher_is_superstar=superstars,
            stadium=stadium,
            mods=mods,
            rng=self.rng,
        )


# --- reference data ---------------------------------------------------------


@dataclass(frozen=True, slots=True, kw_only=True)
class User:
    """A Rio web account."""

    id: int
    name: str


@dataclass(frozen=True, slots=True, kw_only=True)
class Tag:
    """A tag: a label games are filtered by."""

    id: int
    name: str
    kind: TagKind
    description: str | None
    community_id: int | None
    is_active: bool
    created_at: datetime | None
    gecko_code: str | None = None
    """Set only for a ``GECKO_CODE`` tag."""
    gecko_code_description: str | None = None


@dataclass(frozen=True, slots=True, kw_only=True)
class TagSet:
    """A tag set: what the client and site currently call a game mode.

    Games are recorded against one, and each has its own ladder.
    """

    id: int
    name: str
    kind: TagSetKind
    community_id: int | None
    start_time: datetime
    end_time: datetime
    tags: tuple[Tag, ...]
    community_kind: CommunityKind | None = None
    """Set by ``rio.tag_sets.list``, which reports it; ``None`` elsewhere."""

    @property
    def tag_ids(self) -> tuple[int, ...]:
        return tuple(tag.id for tag in self.tags)


@dataclass(frozen=True, slots=True, kw_only=True)
class LadderRow:
    """One player's standing on a tag set's ladder."""

    user: str
    rating: int
    wins: int
    losses: int
    ties: int


@dataclass(frozen=True, slots=True, kw_only=True)
class Community:
    """A community: a group of players with its own tags and tag sets."""

    id: int
    name: str
    kind: CommunityKind
    is_private: bool
    url: str | None
    """The join link, when the community has one."""
    description: str | None
    tag_set_limit: int | None
    """How many tag sets may be active at once."""
    created_at: datetime | None


@dataclass(frozen=True, slots=True, kw_only=True)
class CommunityMember:
    """A user's membership row in a community."""

    id: int
    user_id: int
    is_admin: bool
    is_active: bool
    was_invited: bool
    is_banned: bool
    joined_at: datetime | None
    key: str | None = None
    """The member's community key, when the endpoint reports it."""
    key_created_at: datetime | None = None


@dataclass(frozen=True, slots=True, kw_only=True)
class IssuedKey:
    """An API key Rio web just issued. It's shown once; store it now."""

    key: str
    was_emailed: bool

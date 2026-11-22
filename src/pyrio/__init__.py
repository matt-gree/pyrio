"""Project Rio for Python: Mario Superstar Baseball's data, typed.

Install with ``pip install projectrio``; import as ``pyrio``.
"""

from importlib.metadata import version as _version

from ._characters import (
    Ability,
    CaptainStar,
    Character,
    CharacterAttributes,
    CharacterClass,
    CharacterFamily,
    HorizontalHitTrajectory,
    StarPitch,
    StarSwing,
    VerticalHitTrajectory,
)
from ._stats import BattingLine, PitchingLine, format_batting_line, format_pitching_line
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
    PitchResult,
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
from ._decode import read_game, read_hud
from ._enum import CodeEnum
from ._errors import RioError, StatFileError, UnknownCodeError, UnknownNameError
from ._game import (
    Contact,
    Event,
    Fielding,
    Game,
    GameResult,
    GameState,
    HalfInning,
    HUDSnapshot,
    Pitch,
    RosterSpot,
    Runner,
    Team,
    Version,
)
from ._serialize import to_jsonable
from ._team_names import CAPTAIN_TEAMS, CaptainTeams, SignatureTeam, TeamName, team_name

__version__ = _version("projectrio")

__all__ = [
    "Ability",
    "AtBatResult",
    "Bases",
    "BattingLine",
    "CAPTAIN_TEAMS",
    "CaptainStar",
    "CaptainTeams",
    "Character",
    "CharacterAttributes",
    "CharacterClass",
    "CharacterFamily",
    "ChargeType",
    "CodeEnum",
    "Contact",
    "ContactType",
    "DeadBallReason",
    "Event",
    "FielderAction",
    "FielderBobble",
    "Fielding",
    "Game",
    "GameResult",
    "GameState",
    "HUDSnapshot",
    "HalfInning",
    "Hand",
    "HorizontalHitTrajectory",
    "InputDirection",
    "ManualSelect",
    "MoonshotStatus",
    "OutType",
    "Pitch",
    "PitchResult",
    "PitchType",
    "PitchingLine",
    "Position",
    "PrimaryContactResult",
    "PushPull",
    "RioError",
    "RosterSpot",
    "Runner",
    "SecondaryContactResult",
    "Side",
    "SignatureTeam",
    "Stadium",
    "StarPitch",
    "StarSwing",
    "StatFileError",
    "StealType",
    "SwingType",
    "Team",
    "TeamName",
    "UnknownCodeError",
    "UnknownNameError",
    "Version",
    "VerticalHitTrajectory",
    "format_batting_line",
    "format_pitching_line",
    "read_game",
    "read_hud",
    "team_name",
    "to_jsonable",
]

# --- Pre-1.0 -----------------------------------------------------------------
# Not in __all__. The 1.0 rebuild replaces these step by step and deletes them
# in step 7 (docs/v1.0.0-audit.md, section 9). Their coded values are the old
# pyrio.rio_value classes, imported from there, not the enums above.

# Stat file parsing
from .stat_file_parser import (
    StatObj,
    EventSearch,
    EventObj,
    HudObj,
    RunnerObj,
    load_stat_file,
    iter_stat_files,
)

# API parameter lists and endpoint constants
from .api import (
    Endpoint,
    ParameterList,
    GamesParameterList,
    EventsParameterList,
    LandingDataParameterList,
    StarChancesParameterList,
    StatsParameterList,
    LandingData,
)

# Web API client
from .rio_web import RioWeb

# Custom exceptions
from .exceptions import (
    RioAPIError,
    RioAuthError,
    RioNotFoundError,
    UnknownRioValueError,
)

# Stat formatters and derived stat calculators
from .stat_formatters import (
    batting_avg,
    slugging_pct,
    on_base_pct,
    ops,
    so_pct,
    derive_batting,
    era,
    innings_pitched,
    k_pct,
    opp_avg,
    derive_pitching,
)

# Glicko-2 rating
from .glicko2 import Player as GlickoPlayer
from .glicko_calculator import glicko2_win_probability

# Hit simulator (deterministic port of the MSSB batting calculator)
from .hit_simulation import (
    simulate_hit,
    simulate_hit_from_event,
    hit_inputs_from_event,
    HitInputs,
    HitResult,
)
from . import hit_analysis, stadiums

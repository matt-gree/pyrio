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
from ._enum import CodeEnum
from ._errors import RioError, UnknownCodeError, UnknownNameError
from ._team_names import TeamName

__version__ = _version("projectrio")

__all__ = [
    "Ability",
    "AtBatResult",
    "Bases",
    "BattingLine",
    "CaptainStar",
    "Character",
    "CharacterAttributes",
    "CharacterClass",
    "CharacterFamily",
    "ChargeType",
    "CodeEnum",
    "ContactType",
    "DeadBallReason",
    "FielderAction",
    "FielderBobble",
    "Hand",
    "HorizontalHitTrajectory",
    "InputDirection",
    "ManualSelect",
    "MoonshotStatus",
    "OutType",
    "PitchResult",
    "PitchType",
    "PitchingLine",
    "Position",
    "PrimaryContactResult",
    "PushPull",
    "RioError",
    "SecondaryContactResult",
    "Side",
    "Stadium",
    "StarPitch",
    "StarSwing",
    "StealType",
    "SwingType",
    "TeamName",
    "UnknownCodeError",
    "UnknownNameError",
    "VerticalHitTrajectory",
    "format_batting_line",
    "format_pitching_line",
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

# Team name resolution: the algorithm plus the captain-teams data itself
from .team_name_algo import team_name, CaptainTeams, Signature, CAPTAIN_TEAMS

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
from .hit_sim_validation import validate_statobj
from . import hit_analysis, stadiums

"""Project Rio for Python: Mario Superstar Baseball's data, typed.

Install with ``pip install projectrio``; import as ``pyrio``.
"""

from importlib.metadata import PackageNotFoundError as _PackageNotFoundError
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
    AtBat,
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
from ._stats import BattingLine, PitchingLine, format_batting_line, format_pitching_line
from ._team_names import CAPTAIN_TEAMS, CaptainTeams, SignatureTeam, TeamName, team_name

try:
    __version__ = _version("projectrio")
except _PackageNotFoundError:  # imported from a source tree on the path, e.g. a git submodule
    __version__ = "0+unknown"

__all__ = [
    "CAPTAIN_TEAMS",
    "Ability",
    "AtBat",
    "AtBatResult",
    "Bases",
    "BattingLine",
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

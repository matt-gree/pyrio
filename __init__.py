# Stat file parsing
from .stat_file_parser import (
    StatObj, EventSearch, EventObj, HudObj, RunnerObj,
    load_stat_file, iter_stat_files,
)

# Lookup tables and translation
from .lookup import (
    Lookup, LookupDicts, CAPTAINS,
    lookup, list_dicts, simplified_name_groups,
    userInputToCharacter, is_captain,
    LookupValue, Character, Stadium,
    PitchType, ChargeType, SwingType, ContactType,
    FinalResult, PrimaryContactResult, SecondaryContactResult,
    OutType, StealType, PitchResult,
    Hand, Position, FielderAction, FielderBobble, ManualSelect, TeamName,
    DeadBallReason,
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
from .exceptions import RioAPIError, RioAuthError, RioNotFoundError

# Team name resolution
from .team_name_algo import team_name

# Stat formatters and derived stat calculators
from .stat_formatters import (
    batting_avg, slugging_pct, on_base_pct, ops, so_pct, derive_batting,
    era, innings_pitched, k_pct, opp_avg, derive_pitching,
    format_batting_line, format_pitching_line,
)

# Glicko-2 rating
from .glicko2 import Player as GlickoPlayer
from .glicko_calculator import glicko2_win_probability

# Hit simulator (deterministic port of the MSSB batting calculator)
from .hit_simulation import simulate_hit, simulate_hit_from_event, HitInputs, HitResult
from .hit_sim_validation import validate_statobj
from . import hit_analysis, stadiums

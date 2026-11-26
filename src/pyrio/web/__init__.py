"""The Project Rio web API (``api.projectrio.app``): ``RioClient`` and ``AsyncRioClient``.

Install with ``pip install 'projectrio[web]'``, which adds httpx::

    from pyrio.web import RioClient

    with RioClient.from_env() as rio:
        games = rio.games(tags=["S13 Superstars Off"], limit_games=50)
        games[0].home.captain          # Character.MARIO
        rio.stats(users=["MattGree"], by_character=True)[0].batting.ops

Responses decode into frozen models that reuse pyrio's enums and stat lines.
Errors are :class:`APIError` subclasses, all :class:`pyrio.RioError`.

**Provisional.** Rio web 2.0 reworks tag sets, communities and game modes,
so this module may change in a minor release until that API settles. The
core (``import pyrio``) is not affected.
"""

try:
    import httpx as _httpx
except ImportError as error:  # pragma: no cover - exercised in a subprocess test
    raise ImportError("pyrio.web needs httpx: pip install 'projectrio[web]'") from error

del _httpx

# The httpx check above has to run before these imports, which need httpx.
from ._async_client import AsyncRioClient  # noqa: E402
from ._cache import DiskCache  # noqa: E402
from ._client import RioClient  # noqa: E402
from ._errors import (  # noqa: E402
    APIConnectionError,
    APIError,
    APIResponseError,
    APITimeoutError,
    AuthenticationError,
    NotFoundError,
)
from ._models import (  # noqa: E402
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

__all__ = [
    "APIConnectionError",
    "APIError",
    "APIResponseError",
    "APITimeoutError",
    "AsyncRioClient",
    "AuthenticationError",
    "Community",
    "CommunityKind",
    "CommunityMember",
    "ContactLine",
    "DiskCache",
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
    "NotFoundError",
    "PlayRunner",
    "RatingUpdate",
    "RecordLine",
    "RioClient",
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

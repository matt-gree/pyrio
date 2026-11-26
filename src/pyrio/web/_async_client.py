"""``AsyncRioClient``: the asyncio client for Rio web, with ``RioClient``'s methods."""

from __future__ import annotations

import asyncio
import os

# The types in public signatures are imported at runtime, not under
# TYPE_CHECKING, so typing.get_type_hints() works on every method (RioWebCLI
# derives its prompts from them).
from collections.abc import Mapping, Sequence  # noqa: TC003
from datetime import datetime  # noqa: TC003
from types import TracebackType  # noqa: TC003
from typing import Any, Literal, Self, TypeVar

import httpx

from .._characters import Character  # noqa: TC001
from .._codes import (  # noqa: TC001
    AtBatResult,
    ContactType,
    Hand,
    Position,
    Side,
    Stadium,
    SwingType,
)
from . import _base
from . import _decode as decode
from . import _encode as encode
from ._cache import DiskCache  # noqa: TC001
from ._models import (  # noqa: TC001
    EventRef,
    GameSummary,
    LandingRow,
    LiveGame,
    StarChanceRow,
    StatRow,
)
from ._resources import AsyncCommunities, AsyncKeys, AsyncTags, AsyncTagSets, AsyncUsers

__all__ = ["AsyncRioClient"]

T = TypeVar("T")


class AsyncRioClient(_base.ClientBase):
    """An asyncio client for Rio web's API, with the same methods as :class:`RioClient`.

    For code inside an event loop, such as a Discord bot::

        async with AsyncRioClient.from_env() as rio:
            games = await rio.games(tags=["S13 Superstars Off"], limit_games=100)

    It reads nothing implicitly: pass ``api_key`` or use :meth:`from_env`. Public
    reads need no key; calling an endpoint that does without one raises
    :class:`AuthenticationError` before any request is made.

    Each method makes exactly one HTTP request. GETs that fail to connect or
    get a 429/502/503/504 are retried up to ``max_retries`` times with
    backoff; POSTs never are. ``timeout`` (seconds, or an ``httpx.Timeout``)
    bounds every request. With ``cache``, reference data (tag sets, tags,
    users) is served from a :class:`DiskCache`.

    Pass ``http_client`` to configure httpx yourself (proxies, certificates);
    the client then doesn't close it. The default client ignores proxy and
    certificate environment variables.
    """

    def __init__(
        self,
        *,
        api_key: str | None = None,
        base_url: str = _base.BASE_URL,
        timeout: float | httpx.Timeout = _base.DEFAULT_TIMEOUT,
        max_retries: int = _base.DEFAULT_MAX_RETRIES,
        cache: DiskCache | None = None,
        http_client: httpx.AsyncClient | None = None,
    ) -> None:
        super().__init__(
            api_key=api_key,
            base_url=base_url,
            timeout=timeout,
            max_retries=max_retries,
            cache=cache,
        )
        self._owns_http = http_client is None
        self._http = http_client or httpx.AsyncClient(timeout=timeout, trust_env=False)
        self.communities = AsyncCommunities(self._send)
        self.tags = AsyncTags(self._send)
        self.tag_sets = AsyncTagSets(self._send)
        self.users = AsyncUsers(self._send)
        self.keys = AsyncKeys(self._send)

    @classmethod
    def from_env(
        cls,
        *,
        base_url: str = _base.BASE_URL,
        timeout: float | httpx.Timeout = _base.DEFAULT_TIMEOUT,
        max_retries: int = _base.DEFAULT_MAX_RETRIES,
        cache: DiskCache | None = None,
        http_client: httpx.AsyncClient | None = None,
    ) -> Self:
        """A client using the API key in ``PYRIO_API_KEY``, if it's set.

        The only place pyrio reads the environment.
        """
        return cls(
            api_key=os.environ.get(_base.API_KEY_ENV),
            base_url=base_url,
            timeout=timeout,
            max_retries=max_retries,
            cache=cache,
            http_client=http_client,
        )

    async def __aenter__(self) -> Self:
        return self

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        tb: TracebackType | None,
    ) -> None:
        await self.aclose()

    async def aclose(self) -> None:
        """Close the connection pool (unless it was passed in as ``http_client``)."""
        if self._owns_http:
            await self._http.aclose()

    async def _send(self, call: encode.Call[T]) -> T:
        prepared = self._prepare(call)
        hit, value = self._cached(call, prepared)
        if hit:
            return value  # type: ignore[return-value]
        attempt = 0
        while True:
            attempt += 1
            try:
                response = await self._http.request(
                    prepared.method,
                    prepared.url,
                    params=tuple(prepared.params),
                    json=prepared.body,
                    headers=prepared.headers,
                    timeout=self.timeout,
                )
            except httpx.TransportError as error:
                if self._should_retry(prepared, attempt, None):
                    await asyncio.sleep(_base.retry_delay(attempt))
                    continue
                raise _base.transport_error(prepared, error) from error
            if response.is_error and self._should_retry(prepared, attempt, response.status_code):
                await response.aclose()
                await asyncio.sleep(_base.retry_delay(attempt))
                continue
            return self._finish(call, prepared, response)

    # --- reads ----------------------------------------------------------------

    async def games(
        self,
        *,
        tags: Sequence[str] | None = None,
        exclude_tags: Sequence[str] | None = None,
        users: Sequence[str] | None = None,
        vs_users: Sequence[str] | None = None,
        exclude_users: Sequence[str] | None = None,
        captains: Sequence[Character] | None = None,
        vs_captains: Sequence[Character] | None = None,
        exclude_captains: Sequence[Character] | None = None,
        stadiums: Sequence[Stadium] | None = None,
        start_time: datetime | None = None,
        end_time: datetime | None = None,
        limit_games: int | None = 50,
        include_linescore: bool = False,
        include_scoring_plays: bool = False,
    ) -> list[GameSummary]:
        """Finished games, newest first.

        ``limit_games`` caps how many (``None`` for every match). Games match every
        filter given; within one filter, any listed value matches. Times are
        compared against when a game ended and must be timezone-aware.

        Rio web can't currently filter by a captain whose name has a space or
        parenthesis (``BABY_MARIO``, ``KING_BOO``, ...): it answers 400.
        """
        return await self._send(
            encode.games(
                encode.GameFilter(
                    tags=tags,
                    exclude_tags=exclude_tags,
                    users=users,
                    vs_users=vs_users,
                    exclude_users=exclude_users,
                    captains=captains,
                    vs_captains=vs_captains,
                    exclude_captains=exclude_captains,
                    stadiums=stadiums,
                    start_time=start_time,
                    end_time=end_time,
                ),
                limit_games=limit_games,
                linescore=include_linescore,
                scoring_plays=include_scoring_plays,
            )
        )

    async def stats(
        self,
        *,
        game_ids: Sequence[int] | None = None,
        tags: Sequence[str] | None = None,
        exclude_tags: Sequence[str] | None = None,
        users: Sequence[str] | None = None,
        vs_users: Sequence[str] | None = None,
        exclude_users: Sequence[str] | None = None,
        captains: Sequence[Character] | None = None,
        vs_captains: Sequence[Character] | None = None,
        exclude_captains: Sequence[Character] | None = None,
        stadiums: Sequence[Stadium] | None = None,
        start_time: datetime | None = None,
        end_time: datetime | None = None,
        limit_games: int | None = None,
        characters: Sequence[Character] | None = None,
        by_game: bool = False,
        by_user: bool = False,
        by_roster_spot: bool = False,
        by_character: bool = False,
        by_batting_hand: bool = False,
        by_fielding_hand: bool = False,
        by_swing: bool = False,
        exclude_fouls: bool = False,
        exclude_batting: bool = False,
        exclude_pitching: bool = False,
        exclude_fielding: bool = False,
        exclude_record: bool = False,
        include_pitcher_wins: bool = False,
        include_runs_scored: bool = False,
    ) -> list[StatRow]:
        """Batting, pitching, fielding and win-loss totals, one :class:`StatRow` per group.

        Games come from ``game_ids``, or else from the game filters (all
        matching games unless ``limit_games``). ``users`` and ``characters``
        also restrict whose stats count. Each ``by_*`` flag splits the rows by
        that key; see :class:`StatRow` for the hand splits. ``exclude_fouls``
        leaves foul contacts out of the contact counts.
        """
        shape = decode.StatsShape(
            by_game=by_game,
            by_user=by_user,
            by_roster_spot=by_roster_spot,
            by_character=by_character,
            by_batting_hand=by_batting_hand,
            by_fielding_hand=by_fielding_hand,
            by_swing=by_swing,
            include_pitcher_wins=include_pitcher_wins,
            include_runs_scored=include_runs_scored,
        )
        return await self._send(
            encode.stats(
                encode.GameFilter(
                    tags=tags,
                    exclude_tags=exclude_tags,
                    users=users,
                    vs_users=vs_users,
                    exclude_users=exclude_users,
                    captains=captains,
                    vs_captains=vs_captains,
                    exclude_captains=exclude_captains,
                    stadiums=stadiums,
                    start_time=start_time,
                    end_time=end_time,
                ),
                game_ids=game_ids,
                limit_games=limit_games,
                characters=characters,
                shape=shape,
                exclude_fouls=exclude_fouls,
                exclude_batting=exclude_batting,
                exclude_pitching=exclude_pitching,
                exclude_fielding=exclude_fielding,
                exclude_record=exclude_record,
            )
        )

    async def event_ids(
        self,
        *,
        game_ids: Sequence[int] | None = None,
        tags: Sequence[str] | None = None,
        exclude_tags: Sequence[str] | None = None,
        users: Sequence[str] | None = None,
        vs_users: Sequence[str] | None = None,
        exclude_users: Sequence[str] | None = None,
        captains: Sequence[Character] | None = None,
        vs_captains: Sequence[Character] | None = None,
        exclude_captains: Sequence[Character] | None = None,
        stadiums: Sequence[Stadium] | None = None,
        start_time: datetime | None = None,
        end_time: datetime | None = None,
        limit_games: int | None = None,
        pitchers: Sequence[Character] | None = None,
        batters: Sequence[Character] | None = None,
        fielders: Sequence[Character] | None = None,
        fielder_positions: Sequence[Position] | None = None,
        contacts: Sequence[ContactType] | None = None,
        swings: Sequence[SwingType] | None = None,
        chemistry_links: Sequence[int] | None = None,
        batter_hands: Sequence[Hand] | None = None,
        pitcher_hands: Sequence[Hand] | None = None,
        innings: Sequence[int] | None = None,
        batting_sides: Sequence[Side] | None = None,
        balls: Sequence[int] | None = None,
        strikes: Sequence[int] | None = None,
        outs: Sequence[int] | None = None,
        away_scores: Sequence[int] | None = None,
        home_scores: Sequence[int] | None = None,
        results: Sequence[AtBatResult] | None = None,
        only_star_chances: bool = False,
        users_as_batter: bool = False,
        users_as_pitcher: bool = False,
        limit_events: int = 1000,
    ) -> list[EventRef]:
        """The events matching every filter, as references, in game and event order.

        ``limit_events`` caps the events (Rio web allows at most 150,000).
        ``users_as_batter``/``users_as_pitcher`` keep only events where one of
        ``users`` or ``vs_users`` was batting/pitching. ``contacts`` may
        include ``ContactType.MISS``.
        """
        return await self._send(
            encode.event_ids(
                encode.GameFilter(
                    tags=tags,
                    exclude_tags=exclude_tags,
                    users=users,
                    vs_users=vs_users,
                    exclude_users=exclude_users,
                    captains=captains,
                    vs_captains=vs_captains,
                    exclude_captains=exclude_captains,
                    stadiums=stadiums,
                    start_time=start_time,
                    end_time=end_time,
                ),
                encode.EventFilter(
                    game_ids=game_ids,
                    pitchers=pitchers,
                    batters=batters,
                    fielders=fielders,
                    fielder_positions=fielder_positions,
                    contacts=contacts,
                    swings=swings,
                    chemistry_links=chemistry_links,
                    batter_hands=batter_hands,
                    pitcher_hands=pitcher_hands,
                    innings=innings,
                    batting_sides=batting_sides,
                    balls=balls,
                    strikes=strikes,
                    outs=outs,
                    away_scores=away_scores,
                    home_scores=home_scores,
                    results=results,
                    only_star_chances=only_star_chances,
                    users_as_batter=users_as_batter,
                    users_as_pitcher=users_as_pitcher,
                ),
                limit_games=limit_games,
                limit_events=limit_events,
            )
        )

    async def landing_data(
        self,
        *,
        event_ids: Sequence[int] | None = None,
        game_ids: Sequence[int] | None = None,
        tags: Sequence[str] | None = None,
        exclude_tags: Sequence[str] | None = None,
        users: Sequence[str] | None = None,
        vs_users: Sequence[str] | None = None,
        exclude_users: Sequence[str] | None = None,
        captains: Sequence[Character] | None = None,
        vs_captains: Sequence[Character] | None = None,
        exclude_captains: Sequence[Character] | None = None,
        stadiums: Sequence[Stadium] | None = None,
        start_time: datetime | None = None,
        end_time: datetime | None = None,
        limit_games: int | None = 50,
        pitchers: Sequence[Character] | None = None,
        batters: Sequence[Character] | None = None,
        fielders: Sequence[Character] | None = None,
        fielder_positions: Sequence[Position] | None = None,
        contacts: Sequence[ContactType] | None = None,
        swings: Sequence[SwingType] | None = None,
        chemistry_links: Sequence[int] | None = None,
        batter_hands: Sequence[Hand] | None = None,
        pitcher_hands: Sequence[Hand] | None = None,
        innings: Sequence[int] | None = None,
        batting_sides: Sequence[Side] | None = None,
        balls: Sequence[int] | None = None,
        strikes: Sequence[int] | None = None,
        outs: Sequence[int] | None = None,
        away_scores: Sequence[int] | None = None,
        home_scores: Sequence[int] | None = None,
        results: Sequence[AtBatResult] | None = None,
        only_star_chances: bool = False,
        users_as_batter: bool = False,
        users_as_pitcher: bool = False,
    ) -> list[LandingRow]:
        """Every batted ball in the matching events: contact, flight and fielding.

        ``event_ids``, if given, replaces every other filter. Otherwise the
        newest ``limit_games`` matching games are searched (``None`` for all).
        """
        return await self._send(
            encode.landing_data(
                encode.GameFilter(
                    tags=tags,
                    exclude_tags=exclude_tags,
                    users=users,
                    vs_users=vs_users,
                    exclude_users=exclude_users,
                    captains=captains,
                    vs_captains=vs_captains,
                    exclude_captains=exclude_captains,
                    stadiums=stadiums,
                    start_time=start_time,
                    end_time=end_time,
                ),
                encode.EventFilter(
                    game_ids=game_ids,
                    pitchers=pitchers,
                    batters=batters,
                    fielders=fielders,
                    fielder_positions=fielder_positions,
                    contacts=contacts,
                    swings=swings,
                    chemistry_links=chemistry_links,
                    batter_hands=batter_hands,
                    pitcher_hands=pitcher_hands,
                    innings=innings,
                    batting_sides=batting_sides,
                    balls=balls,
                    strikes=strikes,
                    outs=outs,
                    away_scores=away_scores,
                    home_scores=home_scores,
                    results=results,
                    only_star_chances=only_star_chances,
                    users_as_batter=users_as_batter,
                    users_as_pitcher=users_as_pitcher,
                ),
                event_ids=event_ids,
                limit_games=limit_games,
            )
        )

    async def star_chances(
        self,
        *,
        event_ids: Sequence[int] | None = None,
        game_ids: Sequence[int] | None = None,
        tags: Sequence[str] | None = None,
        exclude_tags: Sequence[str] | None = None,
        users: Sequence[str] | None = None,
        vs_users: Sequence[str] | None = None,
        exclude_users: Sequence[str] | None = None,
        captains: Sequence[Character] | None = None,
        vs_captains: Sequence[Character] | None = None,
        exclude_captains: Sequence[Character] | None = None,
        stadiums: Sequence[Stadium] | None = None,
        start_time: datetime | None = None,
        end_time: datetime | None = None,
        limit_games: int | None = None,
        pitchers: Sequence[Character] | None = None,
        batters: Sequence[Character] | None = None,
        fielders: Sequence[Character] | None = None,
        fielder_positions: Sequence[Position] | None = None,
        contacts: Sequence[ContactType] | None = None,
        swings: Sequence[SwingType] | None = None,
        chemistry_links: Sequence[int] | None = None,
        batter_hands: Sequence[Hand] | None = None,
        pitcher_hands: Sequence[Hand] | None = None,
        innings: Sequence[int] | None = None,
        batting_sides: Sequence[Side] | None = None,
        balls: Sequence[int] | None = None,
        strikes: Sequence[int] | None = None,
        outs: Sequence[int] | None = None,
        away_scores: Sequence[int] | None = None,
        home_scores: Sequence[int] | None = None,
        results: Sequence[AtBatResult] | None = None,
        only_star_chances: bool = False,
        users_as_batter: bool = False,
        users_as_pitcher: bool = False,
        by_inning: bool = False,
    ) -> list[StarChanceRow]:
        """Star-chance counts over the matching events, or per half-inning with ``by_inning``.

        ``event_ids``, if given, replaces every other filter.
        """
        return await self._send(
            encode.star_chances(
                encode.GameFilter(
                    tags=tags,
                    exclude_tags=exclude_tags,
                    users=users,
                    vs_users=vs_users,
                    exclude_users=exclude_users,
                    captains=captains,
                    vs_captains=vs_captains,
                    exclude_captains=exclude_captains,
                    stadiums=stadiums,
                    start_time=start_time,
                    end_time=end_time,
                ),
                encode.EventFilter(
                    game_ids=game_ids,
                    pitchers=pitchers,
                    batters=batters,
                    fielders=fielders,
                    fielder_positions=fielder_positions,
                    contacts=contacts,
                    swings=swings,
                    chemistry_links=chemistry_links,
                    batter_hands=batter_hands,
                    pitcher_hands=pitcher_hands,
                    innings=innings,
                    batting_sides=batting_sides,
                    balls=balls,
                    strikes=strikes,
                    outs=outs,
                    away_scores=away_scores,
                    home_scores=home_scores,
                    results=results,
                    only_star_chances=only_star_chances,
                    users_as_batter=users_as_batter,
                    users_as_pitcher=users_as_pitcher,
                ),
                event_ids=event_ids,
                limit_games=limit_games,
                by_inning=by_inning,
            )
        )

    async def live_games(self) -> list[LiveGame]:
        """Games in progress, newest first."""
        return await self._send(encode.live_games())

    # --- writes and sessions ----------------------------------------------------

    async def submit_game(
        self,
        *,
        winner: str,
        loser: str,
        winner_score: int,
        loser_score: int,
        tag_set: str,
        played_at: datetime,
        game_id: int | None = None,
    ) -> int:
        """Record a result by hand toward a tag set's ladder; returns its id.

        Needs an API key held by one of the players, a community admin or site
        staff. A player's submission waits for the opponent to accept it.
        """
        return await self._send(
            encode.submit_game(
                winner=winner,
                loser=loser,
                winner_score=winner_score,
                loser_score=loser_score,
                tag_set=tag_set,
                played_at=played_at,
                game_id=game_id,
            )
        )

    async def delete_game(self, game_id: int) -> None:
        """Delete a game and everything recorded with it. Site staff only."""
        await self._send(encode.delete_game(game_id))

    async def login(self, *, email: str, password: str) -> str:
        """Start a session for this client; returns the account's user name.

        A few calls need one because Rio web refuses keys for them:
        ``rio.keys.create()``/``reset()`` and changing group membership. While
        the session lasts, it's sent instead of the API key.
        """
        return self._start_session(await self._send(encode.login(email, password)))

    async def request_json(
        self,
        method: Literal["GET", "POST"],
        path: str,
        *,
        params: Mapping[str, str | int | Sequence[str | int]] | None = None,
        json: Mapping[str, Any] | None = None,
    ) -> object:
        """Call an endpoint pyrio doesn't model, and return its JSON undecoded.

        ``path`` includes the server's trailing slash, if it has one
        (``"/characters/"``). The credential, timeout and retries apply as for
        any call.
        """
        return await self._send(encode.raw(method, path, encode.query(params), encode.body(json)))

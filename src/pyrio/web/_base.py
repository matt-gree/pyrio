"""What the sync and async clients share: credentials, retries, errors and caching.

Each client only moves bytes; everything that decides what a request looks
like, whether it may be retried and what its answer means lives here, so the
two can't drift apart.
"""

from __future__ import annotations

import html
import json
import logging
import random
import re
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any, TypeVar

import httpx

from ._encode import Auth, Call
from ._errors import (
    APIConnectionError,
    APIError,
    APIResponseError,
    APITimeoutError,
    AuthenticationError,
    NotFoundError,
)

if TYPE_CHECKING:
    from ._cache import DiskCache

T = TypeVar("T")

logger = logging.getLogger("pyrio.web")

BASE_URL = "https://api.projectrio.app"
DEFAULT_TIMEOUT = 30.0
DEFAULT_MAX_RETRIES = 2
API_KEY_ENV = "PYRIO_API_KEY"

# Statuses worth another try: rate limiting and a proxy or server that's
# briefly unavailable. Rio web's 500s come from bugs and repeat, so they don't.
_RETRY_STATUSES = frozenset({429, 502, 503, 504})


def retry_delay(attempt: int) -> float:
    """Seconds to wait before retry ``attempt`` (1, 2, ...): exponential with jitter, at most 8."""
    return min(8.0, 0.5 * 2 ** (attempt - 1)) * (0.75 + random.random() / 2)


@dataclass(frozen=True, slots=True)
class Prepared:
    """A call turned into what httpx sends."""

    method: str
    url: str
    params: list[tuple[str, str]]
    body: dict[str, Any] | None
    headers: dict[str, str]
    retries: int
    cache_key: str | None


class ClientBase:
    """Configuration and request logic shared by ``RioClient`` and ``AsyncRioClient``."""

    def __init__(
        self,
        *,
        api_key: str | None,
        base_url: str,
        timeout: float | httpx.Timeout,
        max_retries: int,
        cache: DiskCache | None,
    ) -> None:
        if max_retries < 0:
            raise ValueError(f"max_retries must be 0 or more, got {max_retries!r}")
        self.api_key = api_key or None
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout
        self.max_retries = max_retries
        self.cache = cache
        self._session: str | None = None
        self._user: str | None = None

    def __repr__(self) -> str:
        credential = "session" if self._session else ("api_key" if self.api_key else "none")
        return f"{type(self).__name__}(base_url={self.base_url!r}, credential={credential})"

    @property
    def user(self) -> str | None:
        """The account ``login()`` signed in as, or ``None`` without a session."""
        return self._user

    def logout(self) -> None:
        """Drop the session from ``login()``; later calls use the API key, if any."""
        self._session = None
        self._user = None

    def _start_session(self, result: tuple[str, str]) -> str:
        self._user, self._session = result
        return self._user

    def _prepare(self, call: Call[Any]) -> Prepared:
        url = self.base_url + call.path
        headers = {"Accept": "application/json"}
        # One Authorization header carries either credential. The session wins,
        # since the routes that need one refuse a key.
        if self._session:
            headers["Authorization"] = f"Bearer {self._session}"
        elif self.api_key and call.auth is not Auth.SESSION:
            headers["Authorization"] = f"ApiKey {self.api_key}"
        if call.auth is Auth.SESSION and not self._session:
            raise AuthenticationError(
                f"{call.method} {call.path} needs a session: call login(email=..., password=...) "
                "first. Rio web refuses API keys here.",
                method=call.method,
                url=url,
            )
        if call.auth is Auth.CREDENTIAL and "Authorization" not in headers:
            raise AuthenticationError(
                f"{call.method} {call.path} needs an API key: pass RioClient(api_key=...), "
                f"set {API_KEY_ENV} and use RioClient.from_env(), or login() first.",
                method=call.method,
                url=url,
            )
        cache_key = None
        if call.cacheable and self.cache is not None:
            cache_key = json.dumps(
                [call.method, url, call.params, call.body], sort_keys=True, default=str
            )
        return Prepared(
            method=call.method,
            url=url,
            params=call.params,
            body=call.body,
            headers=headers,
            # Only GETs are retried: a repeated POST could act twice.
            retries=self.max_retries if call.method == "GET" else 0,
            cache_key=cache_key,
        )

    def _cached(self, call: Call[T], prepared: Prepared) -> tuple[bool, T | None]:
        if prepared.cache_key is None or self.cache is None:
            return False, None
        body = self.cache.get(prepared.cache_key)
        if body is None:
            return False, None
        logger.debug("cache hit: %s %s", prepared.method, prepared.url)
        return True, call.decode(body)

    def _should_retry(self, prepared: Prepared, attempt: int, status: int | None) -> bool:
        """Whether to try again after ``attempt`` tries (``status`` None: a transport error)."""
        if attempt > prepared.retries:
            return False
        return status is None or status in _RETRY_STATUSES

    def _finish(self, call: Call[T], prepared: Prepared, response: httpx.Response) -> T:
        if response.is_error:
            raise _status_error(prepared, response)
        if not call.json_response:
            return call.decode(None)
        try:
            body: object = response.json()
        except ValueError:
            content_type = response.headers.get("content-type", "no content type")
            raise APIResponseError(
                f"{prepared.method} {call.path}: expected JSON, got {content_type}: "
                f"{_snippet(response.text)}",
                method=prepared.method,
                url=prepared.url,
                status_code=response.status_code,
                body=_snippet(response.text),
            ) from None
        result = call.decode(body)
        if prepared.cache_key is not None and self.cache is not None:
            self.cache.set(prepared.cache_key, body)
        return result


def transport_error(prepared: Prepared, error: httpx.TransportError) -> APIConnectionError:
    """httpx's transport failure as pyrio's, so callers never import httpx to catch it."""
    kind = APITimeoutError if isinstance(error, httpx.TimeoutException) else APIConnectionError
    return kind(
        f"{prepared.method} {prepared.url} failed: {type(error).__name__}: {error}",
        method=prepared.method,
        url=prepared.url,
    )


def _status_error(prepared: Prepared, response: httpx.Response) -> APIError:
    status = response.status_code
    reason = _reason(response.text) or response.reason_phrase
    kind = (
        AuthenticationError
        if status in (401, 403)
        else NotFoundError
        if status == 404
        else APIError
    )
    return kind(
        f"{prepared.method} {prepared.url} returned {status}: {reason}",
        method=prepared.method,
        url=prepared.url,
        status_code=status,
        body=_snippet(response.text),
    )


_PARAGRAPH = re.compile(r"<p>(.*?)</p>", re.DOTALL | re.IGNORECASE)


def _reason(text: str) -> str:
    """The reason in a Werkzeug error page (``<p>...</p>``), or the start of plain text."""
    match = _PARAGRAPH.search(text)
    if match:
        return html.unescape(re.sub(r"<[^>]+>", "", match.group(1))).strip()
    if text.lstrip().startswith("<"):
        return ""
    return _snippet(text)


def _snippet(text: str, limit: int = 300) -> str:
    text = " ".join(text.split())
    return text if len(text) <= limit else text[: limit - 3] + "..."

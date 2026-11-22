"""The web client's exceptions, all under :class:`APIError` (a :class:`pyrio.RioError`).

httpx's own transport errors are wrapped, so a caller never imports httpx just
to catch a failure.
"""

from __future__ import annotations

from .._errors import RioError

__all__ = [
    "APIConnectionError",
    "APIError",
    "APIResponseError",
    "APITimeoutError",
    "AuthenticationError",
    "NotFoundError",
]


class APIError(RioError):
    """A request to Rio web failed.

    ``status_code`` is the HTTP status when the server answered, else ``None``.
    ``body`` is the start of the response text, which for Rio web's errors is
    usually a Werkzeug HTML page carrying the reason.
    """

    def __init__(
        self,
        message: str,
        *,
        method: str | None = None,
        url: str | None = None,
        status_code: int | None = None,
        body: str | None = None,
    ) -> None:
        super().__init__(message)
        self.message = message
        self.method = method
        self.url = url
        self.status_code = status_code
        self.body = body


class AuthenticationError(APIError):
    """The request needs a credential it didn't have, or the one it had was refused.

    Raised before any HTTP call when an endpoint that needs an API key or a
    session is called without one, and for a 401 or 403 from the server.
    """


class NotFoundError(APIError):
    """The server answered 404.

    Rio web reuses 409 for many "not found" cases too; those arrive as a plain
    :class:`APIError` with ``status_code == 409``.
    """


class APIResponseError(APIError):
    """The server answered, but not in the shape this version of pyrio decodes.

    The message names the endpoint and, for a missing key, the keys that were
    present. Seeing this usually means Rio web changed a response.
    """


class APIConnectionError(APIError):
    """No usable response: the connection failed or broke off."""


class APITimeoutError(APIConnectionError, TimeoutError):
    """The request timed out."""

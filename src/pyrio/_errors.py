"""The core's exceptions. Everything pyrio raises on purpose is a :class:`RioError`."""

from __future__ import annotations

__all__ = ["RioError", "StatFileError", "UnknownCodeError", "UnknownNameError"]


class RioError(Exception):
    """Base class for every error pyrio raises on purpose."""


class UnknownCodeError(RioError, ValueError):
    """A value that names no member of a coded type, such as ``Stadium(99)``."""

    def __init__(self, kind: type, value: object) -> None:
        self.kind = kind
        self.value = value
        super().__init__(f"{value!r} is not a valid {kind.__name__}")


class UnknownNameError(UnknownCodeError):
    """Human input that matches no known name. ``suggestions`` holds close matches."""

    def __init__(self, kind: type, value: str, suggestions: tuple[str, ...] = ()) -> None:
        super().__init__(kind, value)
        self.suggestions = suggestions
        message = f"{value!r} is not a known {kind.__name__} name"
        if suggestions:
            message += f" -- did you mean {' or '.join(suggestions)}?"
        self.args = (message,)


class StatFileError(RioError, ValueError):
    """A stat file or HUD file pyrio can't read: malformed, or from a client it doesn't support.

    ``path`` is the file (``None`` when decoding an in-memory dict) and ``key``
    the place in it, such as ``"Events[12].Pitch.Type of Swing"``.
    """

    def __init__(self, message: str, *, path: str | None = None, key: str | None = None) -> None:
        self.path = path
        self.key = key
        where = ": ".join(part for part in (path, key) if part)
        super().__init__(f"{where}: {message}" if where else message)

"""Resolving what people type: nicknames, shorthand, spacing, punctuation and case.

Machine input (stat files, API rows) goes through the strict enum constructors.
This module backs the lenient ``parse`` classmethods, which are for people.
"""

from __future__ import annotations

import difflib
import tomllib
import unicodedata
from functools import cache
from importlib.resources import files
from typing import Any, Generic, TypeVar

from ._errors import UnknownNameError

__all__ = ["NameIndex", "nicknames", "normalize"]

T = TypeVar("T")


def normalize(text: str) -> str:
    """Fold ``text`` to the form names are matched in.

    NFKC, then casefold, then drop everything that isn't a letter or digit, so
    ``"Bowser Jr."``, ``"bowser-jr"`` and ``"BOWSER JR"`` all become ``"bowserjr"``.
    """
    return "".join(ch for ch in unicodedata.normalize("NFKC", text).casefold() if ch.isalnum())


class NameIndex(Generic[T]):
    """Normalized names mapped to the values they mean.

    ``kind`` is the type named in errors. Adding a name that already means
    something else raises ``ValueError``, so a conflict in the data fails on
    first use rather than resolving one way at random.
    """

    def __init__(self, kind: type) -> None:
        self._kind = kind
        self._names: dict[str, T] = {}

    def add(self, name: str, value: T) -> None:
        """Make ``name`` resolve to ``value``."""
        key = normalize(name)
        if not key:
            raise ValueError(f"{name!r} has no letters or digits")
        existing = self._names.setdefault(key, value)
        if existing != value:
            raise ValueError(f"{name!r} would mean both {existing} and {value}")

    def resolve(self, text: str) -> T:
        """The value ``text`` names. Raises :class:`~pyrio.UnknownNameError`."""
        key = normalize(text)
        try:
            return self._names[key]
        except KeyError:
            close = difflib.get_close_matches(key, self._names, n=5, cutoff=0.75)
            suggestions = tuple(dict.fromkeys(str(self._names[name]) for name in close))[:3]
            raise UnknownNameError(self._kind, text, suggestions) from None


@cache
def nicknames() -> dict[str, Any]:
    """The curated names in ``_data/nicknames.toml``, read once on first use."""
    with files("pyrio").joinpath("_data/nicknames.toml").open("rb") as handle:
        return tomllib.load(handle)

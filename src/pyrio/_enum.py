"""``CodeEnum``: the base for every Project Rio coded value (an id paired with a label)."""

from __future__ import annotations

from enum import Enum
from functools import cache
from typing import Self, cast

from ._errors import UnknownCodeError

__all__ = ["CodeEnum"]


class CodeEnum(Enum):
    """A coded value: Project Rio's integer id paired with its canonical label.

    Members are declared as ``NAME = id, "Label", *aliases``. An alias is either
    another label (an older spelling that decoded stat files may still carry) or
    another id that means the same thing (Rio writes both ``0`` and ``0xFF`` for
    "no bobble").

    Look a member up by id, by a digit string, or by label or alias, ignoring
    case: ``Stadium(1)``, ``Stadium("1")``, ``Stadium("bowser's castle")``. A value
    that names no member raises :class:`~pyrio.UnknownCodeError`, a
    ``ValueError``. Members never compare equal to a raw ``int`` or ``str``; use
    ``.id`` and ``.label``, or ``int()`` and ``str()``. Members of one type sort
    by id.
    """

    _value_: int
    _label: str
    _aliases: tuple[int | str, ...]

    def __new__(cls, code: int, label: str, *aliases: int | str) -> Self:
        member = object.__new__(cls)
        member._value_ = code
        member._label = label
        member._aliases = aliases
        return member

    @property
    def id(self) -> int:
        """Project Rio's integer id for this value."""
        return self._value_

    @property
    def label(self) -> str:
        """Project Rio's canonical label for this value."""
        return self._label

    def __str__(self) -> str:
        return self._label

    def __int__(self) -> int:
        return self._value_

    def __lt__(self, other: object) -> bool:
        if type(other) is not type(self):
            return NotImplemented
        return self._value_ < cast(Self, other)._value_

    def __le__(self, other: object) -> bool:
        if type(other) is not type(self):
            return NotImplemented
        return self._value_ <= cast(Self, other)._value_

    def __gt__(self, other: object) -> bool:
        if type(other) is not type(self):
            return NotImplemented
        return self._value_ > cast(Self, other)._value_

    def __ge__(self, other: object) -> bool:
        if type(other) is not type(self):
            return NotImplemented
        return self._value_ >= cast(Self, other)._value_

    @classmethod
    def _missing_(cls, value: object) -> Self:
        labels, ids = _index(cls)
        found: CodeEnum | None = None
        if isinstance(value, str):
            if value.isascii() and value.isdigit():
                code = int(value)
                if code in cls._value2member_map_:
                    return cls(code)
                found = ids.get(code)
            else:
                found = labels.get(value.casefold())
        elif isinstance(value, int) and not isinstance(value, bool):
            found = ids.get(value)
        if found is None:
            raise UnknownCodeError(cls, value)
        return cast(Self, found)


@cache
def _index(cls: type[CodeEnum]) -> tuple[dict[str, CodeEnum], dict[int, CodeEnum]]:
    """Case-folded labels and aliases, and alias ids, for one ``CodeEnum`` type.

    Raises ``TypeError`` if two members share a label or an id, so a mistake in a
    hand-written table fails on first use (and in the test that uses them all).
    """
    labels: dict[str, CodeEnum] = {}
    ids: dict[int, CodeEnum] = {}
    for member in cls:
        for alias in (member.label, *member._aliases):  # pyright: ignore[reportPrivateUsage]
            if isinstance(alias, str):
                clash = labels.setdefault(alias.casefold(), member) is not member
            else:
                taken = alias in cls._value2member_map_
                clash = taken or ids.setdefault(alias, member) is not member
            if clash:
                raise TypeError(f"{cls.__name__}: {alias!r} names two members")
    return labels, ids

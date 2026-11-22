"""``to_jsonable``: any model object as plain dicts and lists, for JSON and web front ends."""

from __future__ import annotations

import dataclasses
from collections.abc import Mapping
from datetime import datetime
from enum import Enum, Flag
from typing import Any, cast

from ._enum import CodeEnum
from ._game import RosterSpot, Team, Version

__all__ = ["to_jsonable"]


def to_jsonable(obj: object) -> Any:
    """``obj`` as plain dicts, lists, strings, numbers, booleans and ``None``.

    Dataclasses become dicts of their fields (properties are left out), enums
    their labels (``"Bowser Castle"``, ``"1-3"`` for bases), datetimes ISO 8601
    strings, a :class:`~pyrio.Version` its string, and tuples lists. A roster
    spot is written out in full only in its team's ``roster``; everywhere else
    (an event's batter, a runner) it's a reference, ``{"side": "Away",
    "index": 3}``, so a game doesn't repeat each spot hundreds of times.
    ``json.dumps(to_jsonable(game))`` always works.
    """
    return _convert(obj, full_spots=True)


def _convert(obj: object, *, full_spots: bool) -> Any:
    if obj is None or isinstance(obj, bool | int | float | str):
        return obj
    if isinstance(obj, CodeEnum):
        return obj.label
    if isinstance(obj, Flag):
        return str(obj)
    if isinstance(obj, Enum):
        return str(obj.value)
    if isinstance(obj, datetime):
        return obj.isoformat()
    if isinstance(obj, Version):
        return str(obj)
    if isinstance(obj, RosterSpot) and not full_spots:
        return {"side": obj.side.value, "index": obj.index}
    if isinstance(obj, Team):
        return {
            field.name: _convert(getattr(obj, field.name), full_spots=field.name == "roster")
            for field in dataclasses.fields(obj)
        }
    if dataclasses.is_dataclass(obj) and not isinstance(obj, type):
        return {
            field.name: _convert(getattr(obj, field.name), full_spots=False)
            for field in dataclasses.fields(obj)
        }
    if isinstance(obj, Mapping):
        items = cast("Mapping[object, object]", obj).items()
        return {_key(key): _convert(value, full_spots=False) for key, value in items}
    if isinstance(obj, list | tuple):
        return [_convert(item, full_spots=full_spots) for item in cast("list[object]", obj)]
    raise TypeError(f"to_jsonable can't convert {type(obj).__name__}")


def _key(key: object) -> str:
    # JSON keys are strings: a position's label, a roster spot as "Away 3".
    if isinstance(key, RosterSpot):
        return f"{key.side.value} {key.index}"
    converted = _convert(key, full_spots=False)
    return converted if isinstance(converted, str) else str(converted)

"""DataFrames from pyrio's models, with the ``pandas`` extra.

One function, :func:`frame`, flattens a sequence of any one model type
(``Event``, ``RosterSpot``, ``Game``, ``pyrio.web.GameSummary``,
``pyrio.web.LandingRow``, ``pyrio.sim.ContactRecord``, ...) into one row each::

    >>> import pyrio, pyrio.pandas
    >>> games = [pyrio.read_game(p) for p in paths]                # doctest: +SKIP
    >>> events = pyrio.pandas.frame(e for g in games for e in g.events)  # doctest: +SKIP
    >>> events.groupby("batter_spot_character", observed=True)["rbi"].sum()  # doctest: +SKIP

Install it with ``pip install 'projectrio[pandas]'``. ``import pyrio`` never
loads this module, so pandas stays optional.
"""

from __future__ import annotations

import dataclasses
import functools
from enum import Enum, Flag
from typing import TYPE_CHECKING, Any

import pandas as pd

from ._enum import CodeEnum
from ._game import RosterSpot, Version

if TYPE_CHECKING:
    from collections.abc import Iterable

__all__ = ["frame"]


def frame(items: Iterable[Any]) -> pd.DataFrame:
    """One row per item, one column per field, for items of one dataclass type.

    How fields become columns:

    - A nested model is flattened, its columns prefixed with the field's name:
      ``Event.pitch.type`` is ``pitch_type``. When the nested model is ``None``
      its columns are missing values.
    - A ``RosterSpot`` inside another model is reduced to which player it is
      (``batter_spot_character``, ``batter_spot_side``, ``batter_spot_index``);
      frame a roster directly for every field of each spot.
    - A location ``(x, y, z)`` is three columns, ``..._x``, ``..._y``, ``..._z``.
    - An enum is a categorical column of its labels, in the enum's own order.
    - Collections of models, mappings and other tuples are left out (frame
      ``game.events`` or ``team.roster`` separately); so are properties, which
      can be recomputed from the columns.

    Raises ``TypeError`` if the items aren't all dataclasses of the same type.
    """
    rows: list[dict[str, Any]] = []
    containers: set[str] = set()
    enums: dict[str, type[Enum]] = {}
    kind: type | None = None
    for item in items:
        if not dataclasses.is_dataclass(item) or isinstance(item, type):
            raise TypeError(f"frame() takes dataclass instances, not {type(item).__name__}")
        if kind is None:
            kind = type(item)
        elif type(item) is not kind:
            raise TypeError(
                f"frame() takes items of one type, got {kind.__name__} and {type(item).__name__}"
            )
        row: dict[str, Any] = {}
        _flatten(item, "", row, containers, enums)
        rows.append(row)

    df = pd.DataFrame.from_records(rows)
    # A nested model that was None in some rows left a column of its own name.
    df = df.drop(columns=[c for c in containers if c in df.columns and df[c].isna().all()])
    for column, enum in enums.items():
        if column in df.columns and not issubclass(enum, Flag):
            labels = [_label(member) for member in enum]
            df[column] = pd.Categorical(df[column], categories=labels)
    return df


def _flatten(
    obj: Any,
    prefix: str,
    row: dict[str, Any],
    containers: set[str],
    enums: dict[str, type[Enum]],
) -> None:
    for f in dataclasses.fields(obj):
        name = f"{prefix}{f.name}"
        shape = _shape(f.type)
        value = getattr(obj, f.name)
        if shape == "skip":
            continue
        if shape == "xyz":
            for axis, v in zip("xyz", (None, None, None) if value is None else value, strict=True):
                row[f"{name}_{axis}"] = v
        elif isinstance(value, RosterSpot):
            containers.add(name)
            row[f"{name}_character"] = _label(value.character)
            enums[f"{name}_character"] = type(value.character)
            row[f"{name}_side"] = _label(value.side)
            enums[f"{name}_side"] = type(value.side)
            row[f"{name}_index"] = value.index
        elif isinstance(value, Version):
            row[name] = str(value)
        elif dataclasses.is_dataclass(value) and not isinstance(value, type):
            containers.add(name)
            _flatten(value, f"{name}_", row, containers, enums)
        elif isinstance(value, Enum):
            row[name] = _label(value)
            enums[name] = type(value)
        else:
            row[name] = value


_POINT = {"Point", "tuple[float, float, float]"}
_LEFT_OUT = ("tuple[", "dict[", "Mapping[", "list[", "set[", "frozenset[", "Sequence[")


@functools.cache
def _shape(annotation: object) -> str:
    """How a field's annotation is framed: "xyz", "skip" or "value"."""
    text = annotation if isinstance(annotation, str) else repr(annotation)
    text = text.removesuffix(" | None")
    if text in _POINT:
        return "xyz"
    if text.startswith(_LEFT_OUT):
        return "skip"
    return "value"


def _label(member: Enum) -> str:
    if isinstance(member, CodeEnum):
        return member.label
    if type(member).__str__ not in (Enum.__str__, Flag.__str__):
        return str(member)
    return member.name

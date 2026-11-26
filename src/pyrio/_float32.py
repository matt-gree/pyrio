"""Single-precision rounding, for the ports of the game's float math."""

from __future__ import annotations

import struct

__all__ = ["f32"]

_FLOAT = struct.Struct("f")


def f32(x: float) -> float:
    """``x`` rounded to a single-precision float, as the game stores it."""
    value: float = _FLOAT.unpack(_FLOAT.pack(x))[0]
    return value

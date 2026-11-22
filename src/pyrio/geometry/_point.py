"""The coordinate type every geometry and simulation function speaks."""

from __future__ import annotations

from typing import TypeAlias

__all__ = ["Point"]

Point: TypeAlias = tuple[float, float, float]
"""A location ``(x, y, z)`` in field units, with home plate at the origin.

``x`` is positive toward first base (right field), ``y`` is height above the
field, and ``z`` runs out toward centre field.
"""

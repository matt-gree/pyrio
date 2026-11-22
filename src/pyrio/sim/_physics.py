"""The ball's flight constants, shared by the hit simulation and the live ball."""

from __future__ import annotations

from typing import Final

GRAVITY_PER_FRAME_SQUARED: Final = 0.00275
"""Fall in vertical speed each frame, in field units per frame (``lbl_3_data_45FC``)."""

VELOCITY_KEPT_PER_FRAME: Final = 0.996
"""Fraction of its velocity the ball keeps each frame, after drag.

``1 - lbl_3_data_4600 / 10000`` in the decomp.
"""

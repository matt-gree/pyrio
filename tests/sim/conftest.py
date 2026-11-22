"""Shared fixtures for the simulation tests."""

from __future__ import annotations

import pathlib
from typing import Any

import pytest

FIXTURES = pathlib.Path(__file__).parent.parent / "fixtures"
DECODED = FIXTURES / "decoded.20260618T191655_SpiceOrange-Vs-MattGree_3896251267.json"


@pytest.fixture(scope="session")
def recorded_legacy_inputs() -> list[Any]:
    """The pre-1.0 module's inputs for every simulated contact in the fixture game.

    Transitional, like the parity tests that use it: built with the pre-1.0
    stat-file reader until ``HitInputs.from_event`` exists.
    """
    import pyrio
    from pyrio.hit_simulation import hit_inputs_from_event
    from pyrio.stat_file_parser import EventObj

    stat = pyrio.load_stat_file(DECODED)
    out: list[Any] = []
    for i in range(len(stat.events())):
        event = EventObj(stat, i)
        try:
            out.append(hit_inputs_from_event(event))
        except ValueError:
            continue  # no contact, or a bunt
    return out

"""RunnerObj: read-only view over a base-runner sub-dict."""
from __future__ import annotations

from typing import Optional

from ..lookup import Lookup, Character, OutType, StealType


class RunnerObj:
    """A base runner within an event (read-only view over a runner sub-dict)."""

    def __init__(self, runner_json: dict):
        self.runner_json = runner_json

    def roster_location(self) -> int:
        return self.runner_json['Runner Roster Loc']

    def character(self) -> Optional[Character]:
        return Lookup.character(self.runner_json.get('Runner Char Id'))

    def initial_base(self) -> int:
        return self.runner_json['Runner Initial Base']

    def result_base(self) -> int:
        return self.runner_json['Runner Result Base']

    def total_bases(self) -> int:
        return self.result_base() - self.initial_base()

    def out_type(self) -> Optional[OutType]:
        return Lookup.out_type(self.runner_json.get('Out Type'))

    def steal(self) -> Optional[StealType]:
        return Lookup.steal_type(self.runner_json.get('Steal'))

    def is_out(self) -> bool:
        ot = self.out_type()
        return ot is not None and ot.name != "None"


# ---------------------------------------------------------------------------
# Stat-file loaders
#
# Entry points for reading decoded stat files off disk into StatObj instances.
# When this module is split into a `stat_file/` subpackage, these belong in
# `stat_file/loaders.py` -- the view classes above stay pure / I/O-free.
# ---------------------------------------------------------------------------

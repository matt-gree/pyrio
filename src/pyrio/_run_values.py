"""Run expectancy and linear weights from stat-file events, and wOBA and wRC on top.

The run-expectancy table (RE24) is the average number of runs a side scores from a
base and out state to the end of its half inning. A result's linear weight is the
average change in run expectancy across it, plus the runs it scored.

Both are measured only over half innings that ran their course: three outs made,
and no walk-off possible. Two kinds of half inning are left out:

- **The game's last half, if it was cut short.** That's a quit or a crash, or the
  batting side winning during it (a walk-off, or a home mercy win). The runs that
  side would have gone on to score are unknown.
- **Every bottom half from the last scheduled inning on.** Those can end on a
  walk-off, so the only ones that reach three outs are the ones where the home
  side didn't score enough. Keeping them would bias the table down. This is the
  usual practice (Tango et al., *The Book*).

Since every half kept ends on its third out, every result in it has a known next
state: the next event's, or the end of the half (worth nothing).
"""

from __future__ import annotations

import math
from collections import Counter, defaultdict
from dataclasses import dataclass, field
from typing import TYPE_CHECKING

from ._codes import AtBatResult, Bases, Side
from ._stats import BattingLine, ratio

if TYPE_CHECKING:
    from collections.abc import Iterable, Iterator

    from ._game import AtBat, Game, HalfInning

__all__ = ["LinearWeights", "RunExpectancy", "linear_weights", "run_expectancy"]

_BASE_ORDER = (
    Bases(0),
    Bases.FIRST,
    Bases.SECOND,
    Bases.THIRD,
    Bases.FIRST | Bases.SECOND,
    Bases.FIRST | Bases.THIRD,
    Bases.SECOND | Bases.THIRD,
    Bases.FIRST | Bases.SECOND | Bases.THIRD,
)

# The results wOBA credits. Every other result in a plate appearance counts as an out.
_WOBA_RESULTS = (
    AtBatResult.WALK,
    AtBatResult.HIT_BY_PITCH,
    AtBatResult.SINGLE,
    AtBatResult.DOUBLE,
    AtBatResult.TRIPLE,
    AtBatResult.HOME_RUN,
)


@dataclass(frozen=True, slots=True, kw_only=True)
class RunExpectancy:
    """The RE24 table: average runs from each base and out state to the end of the half.

    Index it with the bases and outs: ``expectancy[Bases.FIRST, 1]``. A state
    that never occurred gives ``math.nan``. ``str()`` prints the 8-by-3 grid.
    """

    runs: dict[tuple[Bases, int], int] = field(default_factory=dict[tuple[Bases, int], int])
    """Runs scored from each state to the end of the half inning, summed over every
    at-bat that began in it."""
    occurrences: dict[tuple[Bases, int], int] = field(default_factory=dict[tuple[Bases, int], int])
    """At-bats that began in each state. Only states that occurred are present."""

    def __getitem__(self, state: tuple[Bases, int]) -> float:
        count = self.occurrences.get(state, 0)
        return self.runs.get(state, 0) / count if count else math.nan

    def __str__(self) -> str:
        lines = ["Bases  0 outs  1 out  2 outs"]
        for bases in _BASE_ORDER:
            cells = (f"{self[bases, outs]:6.3f}" for outs in range(3))
            lines.append(f"{bases!s:<5}  " + " ".join(cells))
        return "\n".join(lines)


@dataclass(frozen=True, slots=True, kw_only=True)
class LinearWeights:
    """The average run value of each at-bat result, and the wOBA family built on them.

    ``weights[AtBatResult.SINGLE]`` is the average change in run expectancy across
    a single, plus the runs it scored. A result never seen gives ``math.nan``.

    wOBA here is unscaled. Each credited result is worth its run value above an
    out, so wOBA reads as runs per plate appearance above a team of outs. The
    credited results are walks, hit by pitch, and singles through home runs.
    """

    values: dict[AtBatResult, float] = field(default_factory=dict[AtBatResult, float])
    """Each result's average run value."""
    counts: dict[AtBatResult, int] = field(default_factory=dict[AtBatResult, int])
    """How many of each result the values were measured over."""
    runs: int = 0
    """Runs scored in the half innings measured, for the league's runs per plate appearance."""

    def __getitem__(self, result: AtBatResult) -> float:
        return self.values.get(result, math.nan)

    @property
    def out_value(self) -> float:
        """The average run value of an out: every ``AtBatResult.is_out`` result, pooled."""
        outs = [result for result in self.counts if result.is_out]
        total = sum(self.counts[result] for result in outs)
        if not total:
            return math.nan
        return sum(self.values[result] * self.counts[result] for result in outs) / total

    @property
    def plate_appearances(self) -> int:
        """The league's plate appearances: every result measured but bunts."""
        return sum(n for result, n in self.counts.items() if result is not AtBatResult.BUNT)

    @property
    def league_woba(self) -> float:
        """The wOBA of every plate appearance measured."""
        credit = sum(
            self._credit(result) * self.counts[result]
            for result in _WOBA_RESULTS
            if self.counts.get(result)
        )
        return ratio(credit, self.plate_appearances)

    @property
    def league_runs_per_pa(self) -> float:
        """Runs per plate appearance over the half innings measured."""
        return ratio(self.runs, self.plate_appearances)

    def woba(self, batting: Iterable[AtBat] | BattingLine) -> float:
        """Weighted on-base average: credited run value per plate appearance.

        Takes at-bats or a box-score line. Only complete at-bats are read, and bunts
        are left out (Rio's box score counts neither as a plate appearance).
        Errors and fielder's choices count as plate appearances with no credit.

        The variant that leaves walks out of numerator and denominator (wOBA "on
        contact") is this, given at-bats with the walks filtered out.
        """
        credit, plate_appearances = self._tally(batting)
        return ratio(credit, plate_appearances)

    def wraa(self, batting: Iterable[AtBat] | BattingLine) -> float:
        """Weighted runs above average: ``(wOBA - league wOBA) * PA``."""
        credit, plate_appearances = self._tally(batting)
        if not plate_appearances:
            return 0.0
        return credit - self.league_woba * plate_appearances

    def wrc(self, batting: Iterable[AtBat] | BattingLine) -> float:
        """Weighted runs created: wRAA plus the league's runs per PA times PA."""
        credit, plate_appearances = self._tally(batting)
        if not plate_appearances:
            return 0.0
        return credit + (self.league_runs_per_pa - self.league_woba) * plate_appearances

    def _credit(self, result: AtBatResult) -> float:
        return self[result] - self.out_value

    def _tally(self, batting: Iterable[AtBat] | BattingLine) -> tuple[float, int]:
        if isinstance(batting, BattingLine):
            counts = {
                AtBatResult.WALK: batting.walks,
                AtBatResult.HIT_BY_PITCH: batting.hit_by_pitch,
                AtBatResult.SINGLE: batting.singles,
                AtBatResult.DOUBLE: batting.doubles,
                AtBatResult.TRIPLE: batting.triples,
                AtBatResult.HOME_RUN: batting.home_runs,
            }
            plate_appearances = batting.plate_appearances
        else:
            results = Counter(at_bat.result for at_bat in batting)
            del results[AtBatResult.NONE], results[AtBatResult.BUNT]
            counts = results
            plate_appearances = results.total()
        # A result the batter never had adds nothing, even if its weight is unknown.
        credit = sum(self._credit(r) * counts[r] for r in _WOBA_RESULTS if counts.get(r))
        return credit, plate_appearances


def run_expectancy(games: Iterable[Game]) -> RunExpectancy:
    """The RE24 table from the at-bats of many games.

    Every at-bat in a half inning that ran its course counts, finished or not,
    from the state it began in. Its runs are those scored from its first event to
    the end of the half, runs on the third-out play included.
    """
    runs: Counter[tuple[Bases, int]] = Counter()
    occurrences: Counter[tuple[Bases, int]] = Counter()
    for game in games:
        for half in _complete_halves(game):
            to_come = _runs_to_come(half)
            position = {id(event): i for i, event in enumerate(half.events)}
            for at_bat in half.at_bats:
                state = (at_bat.state.bases, at_bat.state.outs)
                runs[state] += to_come[position[id(at_bat.events[0])]]
                occurrences[state] += 1
    return RunExpectancy(runs=_ordered(runs), occurrences=_ordered(occurrences))


def linear_weights(
    games: Iterable[Game], *, expectancy: RunExpectancy | None = None
) -> LinearWeights:
    """Each at-bat result's average run value, over many games.

    For every event with a result in a half inning that ran its course: run
    expectancy after it (the next event's state, or zero if the half ended) minus
    run expectancy before it, plus the runs scored on it. The state before is the
    result event's own, so a steal or pickoff earlier in the at-bat isn't
    credited to the batter.

    ``expectancy`` defaults to the table from the same games. A result whose state
    before or after is missing from the table is skipped. That can happen only when
    ``expectancy`` was measured on other games, or on very few.
    """
    games = list(games)
    if expectancy is None:
        expectancy = run_expectancy(games)
    totals: defaultdict[AtBatResult, float] = defaultdict(float)
    counts: Counter[AtBatResult] = Counter()
    runs = 0
    for game in games:
        for half in _complete_halves(game):
            runs += half.runs
            events = half.events
            for i, event in enumerate(events):
                if event.result is AtBatResult.NONE:
                    continue
                before = expectancy[event.state.bases, event.state.outs]
                if i + 1 < len(events):
                    following = events[i + 1].state
                    after = expectancy[following.bases, following.outs]
                else:
                    after = 0.0
                if math.isnan(before) or math.isnan(after):
                    continue
                totals[event.result] += after - before + event.runs
                counts[event.result] += 1
    ordered = sorted(counts, key=lambda result: result.id)
    return LinearWeights(
        values={result: totals[result] / counts[result] for result in ordered},
        counts={result: counts[result] for result in ordered},
        runs=runs,
    )


def _complete_halves(game: Game) -> Iterator[HalfInning]:
    halves = game.half_innings
    for i, half in enumerate(halves):
        if half.batting_side is Side.HOME and half.inning >= game.innings_selected:
            continue  # a walk-off could have cut it short
        if i == len(halves) - 1 and not _last_half_finished(game, half):
            continue
        yield half


def _last_half_finished(game: Game, half: HalfInning) -> bool:
    # A game that ends normally ends on a third out, unless the batting side won
    # during the half (a walk-off, or a home mercy win).
    result = game.result
    if result.quit_by is not None or result.crashed:
        return False
    return result.winner is not half.batting_side


def _runs_to_come(half: HalfInning) -> list[int]:
    # Runs from each event (inclusive) to the end of the half.
    to_come = [0] * (len(half.events) + 1)
    for i in range(len(half.events) - 1, -1, -1):
        to_come[i] = to_come[i + 1] + half.events[i].runs
    return to_come


def _ordered(counter: Counter[tuple[Bases, int]]) -> dict[tuple[Bases, int], int]:
    order = {bases: i for i, bases in enumerate(_BASE_ORDER)}
    return {state: counter[state] for state in sorted(counter, key=lambda s: (order[s[0]], s[1]))}

"""Batting and pitching lines, and the one formula for each derived stat.

A line is a frozen record of counting stats. Lines add (``a + b``), so a team's
line is the sum of its roster's and a career is the sum of its games. Rate stats
are properties computed from the counts: unrounded floats, ``math.nan`` when the
denominator is zero. Rounding and display belong to the ``format_*`` functions.

The same classes come out of stat files and the web API, so both give the same
fields and the same numbers.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, fields
from typing import TYPE_CHECKING, Self

if TYPE_CHECKING:
    from collections.abc import Callable

__all__ = ["BattingLine", "PitchingLine", "format_batting_line", "format_pitching_line"]


def _ratio(numerator: float, denominator: float) -> float:
    return numerator / denominator if denominator else math.nan


class _Line:
    """Field-wise addition for the line dataclasses."""

    __slots__ = ()

    def __add__(self, other: object) -> Self:
        if type(other) is not type(self):
            return NotImplemented
        return type(self)(
            **{f.name: getattr(self, f.name) + getattr(other, f.name) for f in fields(self)}  # type: ignore[arg-type]
        )

    def __radd__(self, other: object) -> Self:
        # Lets sum(lines) work: sum() starts from 0.
        if other == 0:
            return self
        return NotImplemented


@dataclass(frozen=True, slots=True, kw_only=True)
class BattingLine(_Line):
    """A batter's counting stats, for one game or summed over many.

    ``walks`` are four-ball walks only; ``hit_by_pitch`` is counted separately.
    """

    at_bats: int = 0
    hits: int = 0
    singles: int = 0
    doubles: int = 0
    triples: int = 0
    home_runs: int = 0
    walks: int = 0
    hit_by_pitch: int = 0
    strikeouts: int = 0
    sac_flies: int = 0
    bunts: int = 0
    """Successful bunts."""
    rbi: int = 0
    stolen_bases: int = 0
    star_hits: int = 0

    @property
    def plate_appearances(self) -> int:
        """At bats, walks, hit by pitch and sacrifice flies."""
        return self.at_bats + self.walks + self.hit_by_pitch + self.sac_flies

    @property
    def total_bases(self) -> int:
        return self.singles + 2 * self.doubles + 3 * self.triples + 4 * self.home_runs

    @property
    def avg(self) -> float:
        """Batting average: hits per at bat."""
        return _ratio(self.hits, self.at_bats)

    @property
    def obp(self) -> float:
        """On-base percentage: times on base per plate appearance."""
        return _ratio(self.hits + self.walks + self.hit_by_pitch, self.plate_appearances)

    @property
    def slg(self) -> float:
        """Slugging: total bases per at bat."""
        return _ratio(self.total_bases, self.at_bats)

    @property
    def ops(self) -> float:
        """On-base plus slugging."""
        return self.obp + self.slg

    @property
    def iso(self) -> float:
        """Isolated power: slugging minus average."""
        return self.slg - self.avg

    @property
    def k_pct(self) -> float:
        """Strikeouts per plate appearance, as a fraction (0.25, not 25)."""
        return _ratio(self.strikeouts, self.plate_appearances)


@dataclass(frozen=True, slots=True, kw_only=True)
class PitchingLine(_Line):
    """A pitcher's counting stats, for one game or summed over many.

    ``walks`` are four-ball walks only; ``hit_by_pitch`` is counted separately.
    """

    batters_faced: int = 0
    outs_pitched: int = 0
    hits_allowed: int = 0
    home_runs_allowed: int = 0
    runs_allowed: int = 0
    earned_runs: int = 0
    walks: int = 0
    hit_by_pitch: int = 0
    strikeouts: int = 0
    pitches_thrown: int = 0
    star_pitches_thrown: int = 0

    @property
    def innings_pitched(self) -> float:
        """Outs divided by three, so 19 outs is 6.333... (``format_pitching_line`` shows 6.1)."""
        return self.outs_pitched / 3

    @property
    def era(self) -> float:
        """Earned runs per nine innings. ``era_over`` scales to another game length."""
        return self.era_over(9)

    def era_over(self, innings: int) -> float:
        """Earned runs per ``innings`` innings, for leagues that play shorter games."""
        return _ratio(self.earned_runs * innings * 3, self.outs_pitched)

    @property
    def whip(self) -> float:
        """Walks plus hits per inning pitched."""
        return _ratio(self.walks + self.hits_allowed, self.innings_pitched)

    @property
    def k_pct(self) -> float:
        """Strikeouts per batter faced, as a fraction (0.25, not 25)."""
        return _ratio(self.strikeouts, self.batters_faced)

    @property
    def k_per_bb(self) -> float:
        """Strikeouts per walk."""
        return _ratio(self.strikeouts, self.walks)

    @property
    def avg_against(self) -> float:
        """Hits per at bat against: batters faced, less walks and hit batters."""
        return _ratio(self.hits_allowed, self.batters_faced - self.walks - self.hit_by_pitch)

    @property
    def pitches_per_inning(self) -> float:
        return _ratio(self.pitches_thrown, self.innings_pitched)


def format_batting_line(line: BattingLine) -> str:
    """One game's batting line: ``"2-for-4, HR, 2B, RBI"``.

    Hits for at bats, then each nonzero stat in the order HR, 3B, 2B, BB, HBP,
    RBI, SB, with a count when it's more than one (``"2 2B"``). Singles are implied.
    """
    parts = [f"{line.hits}-for-{line.at_bats}"]
    for count, label in (
        (line.home_runs, "HR"),
        (line.triples, "3B"),
        (line.doubles, "2B"),
        (line.walks, "BB"),
        (line.hit_by_pitch, "HBP"),
        (line.rbi, "RBI"),
        (line.stolen_bases, "SB"),
    ):
        if count == 1:
            parts.append(label)
        elif count > 1:
            parts.append(f"{count} {label}")
    return ", ".join(parts)


def format_pitching_line(line: PitchingLine) -> str:
    """One game's pitching line: ``"6.1 IP, 3 H, 1 R, 1 ER, 2 BB, 1 HBP, 4 K, 0 HR, 87 P"``.

    Every field is shown, zeros included, since leaving one out is ambiguous.
    Innings are in the box-score form, where ``.1`` and ``.2`` are thirds.
    """
    innings = f"{line.outs_pitched // 3}.{line.outs_pitched % 3}"
    return (
        f"{innings} IP, {line.hits_allowed} H, {line.runs_allowed} R, "
        f"{line.earned_runs} ER, {line.walks} BB, {line.hit_by_pitch} HBP, "
        f"{line.strikeouts} K, {line.home_runs_allowed} HR, {line.pitches_thrown} P"
    )


# Rio writes a character's game so far under the same keys everywhere: the stat
# file's and HUD file's rosters, and the live feed's batter and pitcher. Each
# reader takes a function that reads one key as an integer.


def rio_batting_line(count: Callable[[str], int]) -> BattingLine:
    """A batting line from Rio's ``"Offensive Stats"`` keys."""
    return BattingLine(
        at_bats=count("At Bats"),
        hits=count("Hits"),
        singles=count("Singles"),
        doubles=count("Doubles"),
        triples=count("Triples"),
        home_runs=count("Homeruns"),
        walks=count("Walks (4 Balls)"),
        hit_by_pitch=count("Walks (Hit)"),
        strikeouts=count("Strikeouts"),
        sac_flies=count("Sac Flys"),
        bunts=count("Successful Bunts"),
        rbi=count("RBI"),
        stolen_bases=count("Bases Stolen"),
        star_hits=count("Star Hits"),
    )


def rio_pitching_line(count: Callable[[str], int]) -> PitchingLine:
    """A pitching line from Rio's ``"Defensive Stats"`` keys."""
    return PitchingLine(
        batters_faced=count("Batters Faced"),
        outs_pitched=count("Outs Pitched"),
        hits_allowed=count("Hits Allowed"),
        home_runs_allowed=count("HRs Allowed"),
        runs_allowed=count("Runs Allowed"),
        earned_runs=count("Earned Runs"),
        walks=count("Batters Walked"),
        hit_by_pitch=count("Batters Hit"),
        strikeouts=count("Strikeouts"),
        pitches_thrown=count("Pitches Thrown"),
        star_pitches_thrown=count("Star Pitches Thrown"),
    )

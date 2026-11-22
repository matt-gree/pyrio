"""Batting by character across a folder of stat files, as a pandas table.

    python examples/character_batting.py STAT_FILE_FOLDER

Needs ``pip install 'projectrio[pandas]'``.
"""

from __future__ import annotations

import argparse
import pathlib

import pyrio
import pyrio.pandas


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument("folder", help="a folder of stat files (searched recursively)")
    args = parser.parse_args(argv)

    games = [pyrio.read_game(p) for p in sorted(pathlib.Path(args.folder).rglob("*.json"))]
    # One row per roster spot per game, with every batting count as a column.
    spots = pyrio.pandas.frame(
        spot for g in games for team in (g.away, g.home) for spot in team.roster
    )
    totals = spots.groupby("character", observed=True)[
        ["batting_at_bats", "batting_hits", "batting_home_runs", "batting_rbi"]
    ].sum()
    totals["avg"] = totals["batting_hits"] / totals["batting_at_bats"]
    totals = totals[totals["batting_at_bats"] >= 5].sort_values("avg", ascending=False)
    print(f"{len(games)} games")
    print(totals.round(3).to_string())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

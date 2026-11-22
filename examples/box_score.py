"""Print a stat file's box score: the line score, then each side's batting and pitching.

    python examples/box_score.py GAME.json

Needs only ``pip install projectrio``.
"""

from __future__ import annotations

import argparse

import pyrio
from pyrio import Side, format_batting_line, format_pitching_line


def line_score(game: pyrio.Game) -> list[str]:
    innings = max(game.innings_played, 1)
    runs = {Side.AWAY: [0] * innings, Side.HOME: [0] * innings}
    for half in game.half_innings:
        runs[half.batting_side][half.inning - 1] += sum(e.runs for e in half.events)
    header = " " * 14 + " ".join(f"{i:>2}" for i in range(1, innings + 1)) + "    R   H"
    rows = [header]
    for side in Side:
        team = game.team(side)
        cells = " ".join(f"{r:>2}" for r in runs[side])
        rows.append(f"{team.player[:12]:<14}{cells}  {team.score:>3} {team.batting.hits:>3}")
    return rows


def box_score(game: pyrio.Game) -> list[str]:
    lines = [f"{game.stadium.label}, {game.start_time:%Y-%m-%d}, Rio {game.version}", ""]
    lines += line_score(game)
    for side in Side:
        team = game.team(side)
        lines += ["", f"{team.player} ({side})"]
        for spot in team.roster:
            captain = " (C)" if spot.is_captain else ""
            lines.append(
                f"  {spot.character.label + captain:<20} {format_batting_line(spot.batting)}"
            )
        for spot in team.roster:
            if spot.was_pitcher:
                lines.append(
                    f"  P {spot.character.label:<18} {format_pitching_line(spot.pitching)}"
                )
    return lines


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument("path", help="a stat file, encoded or decoded")
    args = parser.parse_args(argv)
    print("\n".join(box_score(pyrio.read_game(args.path))))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

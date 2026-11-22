"""Write a stat file's spray chart as an SVG.

    python examples/spray_chart.py GAME.json -o spray.svg

Needs only ``pip install projectrio``: pyrio.svg has no dependencies.
"""

from __future__ import annotations

import argparse
import pathlib

import pyrio
import pyrio.svg


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument("path", help="a stat file, encoded or decoded")
    parser.add_argument("-o", "--out", default="spray.svg", help="where to write the SVG")
    parser.add_argument("--fouls", action="store_true", help="mark foul balls too")
    args = parser.parse_args(argv)

    game = pyrio.read_game(args.path)
    title = f"{game.away.player} {game.away.score} - {game.home.score} {game.home.player}"
    svg = pyrio.svg.spray_chart(
        game.events, stadium=game.stadium, fouls=args.fouls, size=600, title=title
    )
    pathlib.Path(args.out).write_text(svg, encoding="utf-8")
    print(f"wrote {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

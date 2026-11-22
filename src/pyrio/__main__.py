"""The ``pyrio`` command: ``pyrio decode FILE`` prints a stat file in readable form.

Also runs as ``python -m pyrio``.
"""

from __future__ import annotations

import argparse
import json
import sys
from typing import TYPE_CHECKING

from . import __version__
from ._decode import read_game, read_hud
from ._errors import StatFileError
from ._serialize import to_jsonable
from ._stats import format_batting_line, format_pitching_line

if TYPE_CHECKING:
    from collections.abc import Sequence

    from ._game import Event, Game, Team

__all__ = ["main"]


def main(argv: Sequence[str] | None = None) -> int:
    """Run the command line; returns the exit status."""
    parser = argparse.ArgumentParser(prog="pyrio", description="Project Rio stat-file tools.")
    parser.add_argument("--version", action="version", version=f"pyrio {__version__}")
    commands = parser.add_subparsers(dest="command", required=True)
    decode = commands.add_parser(
        "decode", help="print a stat file (encoded or decoded) in readable form"
    )
    decode.add_argument("file", help="a stat file, or a HUD file with --hud")
    decode.add_argument("--events", action="store_true", help="also list every event")
    decode.add_argument("--json", action="store_true", help="print the decoded model as JSON")
    decode.add_argument(
        "--hud", metavar="VERSION", help="read FILE as a HUD file written by client VERSION"
    )
    args = parser.parse_args(argv)

    try:
        if args.hud is not None:
            model: object = read_hud(args.file, version=args.hud)
            text = json.dumps(to_jsonable(model), indent=2)
        else:
            game = read_game(args.file)
            if args.json:
                text = json.dumps(to_jsonable(game), indent=2)
            else:
                text = _describe(game, events=args.events)
    except (OSError, StatFileError) as err:
        print(f"pyrio: {err}", file=sys.stderr)
        return 1
    print(text)
    return 0


def _describe(game: Game, *, events: bool) -> str:
    result = game.result
    if result.quit_by is not None:
        ending = f"{game.team(result.quit_by).player} quit"
    elif result.crashed:
        ending = "crashed"
    elif result.is_mercy:
        ending = "mercy rule"
    else:
        ending = "final"
    lines = [
        f"Game {game.id}  (Rio {game.version})",
        f"{game.start_time:%Y-%m-%d %H:%M}  {game.stadium}",
        f"{game.away.player} {game.away.score}, {game.home.player} {game.home.score}"
        f"  ({ending}, {game.innings_played} of {game.innings_selected} innings)",
        "",
        *_line_score(game),
    ]
    for team in (game.away, game.home):
        lines += ["", *_box(team)]
    if events:
        lines += ["", "Events", *(_event_line(event) for event in game.events)]
    return "\n".join(lines)


def _line_score(game: Game) -> list[str]:
    innings = max(game.innings_played, max((e.state.inning for e in game.events), default=0))
    runs = {(half.inning, half.batting_side): half.runs for half in game.half_innings}
    header = "".join(f"{i:>3}" for i in range(1, innings + 1))
    width = max(len(game.away.player), len(game.home.player))
    rows = [f"{'':<{width}} {header}    R"]
    for team in (game.away, game.home):
        cells = "".join(
            f"{runs[(i, team.side)]:>3}" if (i, team.side) in runs else "  -"
            for i in range(1, innings + 1)
        )
        rows.append(f"{team.player:<{width}} {cells}  {team.score:>3}")
    return rows


def _box(team: Team) -> list[str]:
    rows = [f"{team.player} ({team.side})"]
    for spot in team.roster:
        name = spot.character.label + " (C)" * spot.is_captain + "*" * spot.is_superstar
        rows.append(f"  {spot.index + 1}. {name:<18} {format_batting_line(spot.batting)}")
    for spot in team.roster:
        if spot.was_pitcher:
            rows.append(f"  P  {spot.character.label:<18} {format_pitching_line(spot.pitching)}")
    return rows


def _event_line(event: Event) -> str:
    state = event.state
    half = "T" if state.batting_side.value == "Away" else "B"
    count = f"{state.balls}-{state.strikes}, {state.outs} out"
    action = event.result.label if event.result.id else ""
    if event.pitch is not None:
        pitch = f"{event.pitch.type} {event.pitch.swing}"
        if event.contact is not None:
            pitch += f", {event.contact.type}"
    else:
        pitch = "no pitch"
    return (
        f"{event.number:>4} {half}{state.inning:<2} {state.away_score}-{state.home_score}"
        f" [{state.bases}] {count:<12} {event.batter.label} vs {event.pitcher.label}:"
        f" {pitch}{'  -> ' + action if action else ''}"
    )


if __name__ == "__main__":
    sys.exit(main())

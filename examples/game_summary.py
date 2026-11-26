"""A broadcast-style game summary graphic, built on the hit simulator.

    python examples/game_summary.py GAME.json -o summary.png

Three panels: every ball in play's simulated flight over the stadium (a
caught ball shows where it would have come down), the hardest-hit balls, and
each fair ball's carry against its apex. The game's highlights run along the
bottom. Needs ``pip install 'projectrio[plot]'``.
"""

from __future__ import annotations

import argparse

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.lines import Line2D

import pyrio
import pyrio.plot
from pyrio import AtBatResult, Side
from pyrio.sim import ContactRecord, find_highlights, format_highlights, simulate_contacts

SIDE_COLOR = {Side.AWAY: "#c0392b", Side.HOME: "#2a62b8"}
HIT_STYLE = {
    AtBatResult.SINGLE: ("#2e8b3a", "o", 60),
    AtBatResult.DOUBLE: ("#2a62b8", "D", 80),
    AtBatResult.TRIPLE: ("#7b4bb3", "^", 100),
    AtBatResult.HOME_RUN: ("#e08a00", "*", 300),
}


def draw_flights(ax, game: pyrio.Game, contacts: tuple[ContactRecord, ...]) -> None:
    pyrio.plot.stadium(game.stadium, ax=ax, fielders=True)
    for c in contacts:
        xs = [p[0] for p in c.trajectory]
        zs = [p[2] for p in c.trajectory]
        color = "#aaaaaa" if c.is_foul else SIDE_COLOR[c.batting_side]
        ax.plot(xs, zs, color=color, alpha=0.2 if c.is_foul else 0.5, linewidth=1, zorder=2)
        x, _, z = c.landing_location
        if c.result in HIT_STYLE:
            hit_color, marker, size = HIT_STYLE[c.result]
            ax.scatter(x, z, color=hit_color, marker=marker, s=size, edgecolors="black", zorder=5)
        elif not c.is_foul:
            ax.scatter(x, z, color=color, marker="x" if c.caught else "P", s=40, zorder=4)
    ax.legend(
        handles=[
            Line2D([], [], color=SIDE_COLOR[Side.AWAY], label=f"{game.away.player} (away)"),
            Line2D([], [], color=SIDE_COLOR[Side.HOME], label=f"{game.home.player} (home)"),
            Line2D([], [], color="#555555", marker="x", lw=0, label="Caught (simulated landing)"),
            Line2D([], [], color="#e08a00", marker="*", lw=0, markersize=12, label="Home run"),
        ],
        loc="upper left",
        fontsize=8,
    )
    ax.set_title("Simulated ball flight")


def draw_hardest_hit(ax, contacts: tuple[ContactRecord, ...], top: int = 8) -> None:
    fair = sorted((c for c in contacts if c.is_fair), key=lambda c: c.power, reverse=True)[:top]
    rows = list(range(len(fair)))[::-1]
    ax.barh(rows, [c.power for c in fair], color=[SIDE_COLOR[c.batting_side] for c in fair])
    ax.set_yticks(rows, [f"{c.batter.label} - {c.result.label}" for c in fair], fontsize=8)
    if fair:
        ax.set_xlim(min(c.power for c in fair) - 8, max(c.power for c in fair) + 8)
    ax.set_xlabel("Exit power")
    ax.set_title("Hardest-hit balls")


def draw_hit_profile(ax, contacts: tuple[ContactRecord, ...]) -> None:
    fair = [c for c in contacts if c.is_fair]
    ax.scatter(
        [c.distance for c in fair],
        [c.max_height for c in fair],
        s=[20 + c.hang_frames * 0.8 for c in fair],
        c=[
            "#e08a00" if c.result is AtBatResult.HOME_RUN else "#2e8b3a" if c.is_hit else "#999999"
            for c in fair
        ],
        edgecolors="black",
        linewidths=0.4,
        alpha=0.8,
    )
    ax.set_xlabel("Carry (simulated)")
    ax.set_ylabel("Apex height (simulated)")
    ax.set_title("Hit profile (size = hang time)")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument("path", help="a stat file, encoded or decoded")
    parser.add_argument("-o", "--out", default="summary.png", help="where to write the PNG")
    args = parser.parse_args(argv)

    game = pyrio.read_game(args.path)
    contacts = simulate_contacts(game)
    highlights = format_highlights(find_highlights(contacts, stadium=game.stadium))

    fig = plt.figure(figsize=(16, 9))
    grid = fig.add_gridspec(
        2,
        2,
        width_ratios=[1.5, 1],
        hspace=0.35,
        wspace=0.25,
        left=0.05,
        right=0.98,
        top=0.88,
        bottom=0.16,
    )
    draw_flights(fig.add_subplot(grid[:, 0]), game, contacts)
    draw_hardest_hit(fig.add_subplot(grid[0, 1]), contacts)
    draw_hit_profile(fig.add_subplot(grid[1, 1]), contacts)
    fig.suptitle(
        f"{game.away.player} {game.away.score} - {game.home.score} {game.home.player}"
        f"  |  {game.stadium.label}  |  {game.innings_played} innings",
        fontsize=16,
        fontweight="bold",
    )
    fig.text(0.05, 0.02, "\n".join(highlights), fontsize=9, family="monospace", va="bottom")
    fig.savefig(args.out, dpi=120)
    print(f"wrote {args.out}")
    print("\n".join(highlights))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

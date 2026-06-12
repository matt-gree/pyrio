"""Broadcast-style game summary graphic built on the hit simulator.

Demo/reference renderer for the reusable pieces in this repo:
  - ``hit_analysis``  : per-contact simulation records + highlight metrics
  - ``stadiums``      : outfield wall geometry (robbed-HR detection)
  - ``draw.draw_stadium`` : stadium outlines / fielder positions

Panels: a spray chart with real simulated flight paths over the stadium
outline (caught balls show their would-be landing), an exit-power
leaderboard, and a hit-profile scatter, plus a highlight ticker.

Usage:
    python -m pyrio.game_summary <decoded stat file> [-o out.png]

    from pyrio import game_summary
    game_summary.render_game_summary("decoded.json", "out.png")
"""
from __future__ import annotations

import json
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

from . import hit_analysis as ha
from .stat_file_parser import StatObj
from .draw import draw_stadium

_DRAW_DIR = Path(__file__).parent / "draw"
_STADIUM_FILES = {
    "Mario Stadium": "mario_stadium",
    "Peach Garden": "peach_garden",
    "Wario Palace": "wario_palace",
    "Yoshi Park": "yoshi_park",
    "DK Jungle": "dk_jungle",
    "Bowser Castle": "bowser_castle",
}

# result -> (color, marker, size)
_RESULT_STYLE = {
    "Single": ("#2ca02c", "o", 70),
    "Double": ("#1f77b4", "D", 90),
    "Triple": ("#9467bd", "^", 110),
    "HR": ("#ff9500", "*", 320),
}
_AWAY_COLOR = "#d62728"
_HOME_COLOR = "#1f77b4"


# ---------------------------------------------------------------- panels

def _draw_field(ax, stat: StatObj, contacts: list[ha.ContactRecord]):
    stadium_file = _STADIUM_FILES.get(stat.stadium())
    if stadium_file:
        draw_stadium.draw_stad(str(_DRAW_DIR / stadium_file), ax=ax)
    draw_stadium.draw_45_degree_lines(ax=ax, color="#bbbbbb")
    draw_stadium.draw_fielder_positions(ax=ax, color="#888888", marker="s")

    for c in contacts:
        team_color = _AWAY_COLOR if c.half_inning == 0 else _HOME_COLOR
        traj = np.array(c.trajectory)

        # flight path
        ax.plot(traj[:, 0], traj[:, 2],
                color="#aaaaaa" if c.foul else team_color,
                alpha=0.18 if c.foul else 0.45,
                linewidth=0.8 if c.foul else 1.3, zorder=2)

        # landing marker
        x, _, z = c.landing
        if c.foul:
            ax.scatter(x, z, color="#aaaaaa", marker=".", s=35, zorder=3)
        elif c.result in _RESULT_STYLE:
            color, marker, size = _RESULT_STYLE[c.result]
            ax.scatter(x, z, color=color, marker=marker, s=size,
                       edgecolors="black", linewidths=0.6, zorder=5)
            if c.result == "HR":
                ax.annotate(f"{c.batter} HR", (x, z), textcoords="offset points",
                            xytext=(6, 6), fontsize=9, fontweight="bold", color="#b36b00")
        elif c.caught:
            ax.scatter(x, z, color=team_color, marker="x", s=55, alpha=0.8, zorder=4)
        else:
            ax.scatter(x, z, color=team_color, marker="P", s=45, alpha=0.8, zorder=4)

    # robbery callout: deepest caught ball
    robbery = ha.deepest_robbery(contacts)
    if robbery:
        x, _, z = robbery.landing
        ax.annotate(f"ROBBED: {robbery.batter}", (x, z), textcoords="offset points",
                    xytext=(-70, 18), fontsize=9, fontweight="bold", color="#7a1fa2",
                    arrowprops=dict(arrowstyle="->", color="#7a1fa2", lw=1.2))

    away_name, home_name = stat.player(0), stat.player(1)
    handles = [
        plt.Line2D([], [], color=_AWAY_COLOR, lw=2, label=f"{away_name} (away)"),
        plt.Line2D([], [], color=_HOME_COLOR, lw=2, label=f"{home_name} (home)"),
        plt.Line2D([], [], color="#2ca02c", marker="o", lw=0, label="Single"),
        plt.Line2D([], [], color="#1f77b4", marker="D", lw=0, label="Double"),
        plt.Line2D([], [], color="#ff9500", marker="*", lw=0, markersize=14, label="Home Run"),
        plt.Line2D([], [], color="#555555", marker="x", lw=0, label="Caught (sim landing)"),
        plt.Line2D([], [], color="#aaaaaa", marker=".", lw=0, label="Foul"),
    ]
    ax.legend(handles=handles, loc="upper left", fontsize=8, framealpha=0.9)
    ax.set_title("Spray chart - simulated ball flight (caught balls show would-be landing)")
    ax.set_aspect("equal")


def _draw_power_leaderboard(ax, contacts: list[ha.ContactRecord], top_n: int = 8):
    fair = sorted((c for c in contacts if c.fair), key=lambda c: c.power, reverse=True)[:top_n]
    labels = [f"{c.batter} ({'A' if c.half_inning == 0 else 'H'}) - {c.result}" for c in fair]
    powers = [c.power for c in fair]
    colors = [_AWAY_COLOR if c.half_inning == 0 else _HOME_COLOR for c in fair]

    y = np.arange(len(fair))[::-1]
    ax.barh(y, powers, color=colors, alpha=0.85, edgecolor="black", linewidth=0.4)
    ax.set_yticks(y)
    ax.set_yticklabels(labels, fontsize=8)
    for yi, p in zip(y, powers):
        ax.text(p + 0.5, yi, str(p), va="center", fontsize=8)
    ax.set_xlim(min(powers) - 8, max(powers) + 8)
    ax.set_xlabel("Exit power", fontsize=9)
    ax.set_title("Hardest hit balls")


def _draw_hit_profile(ax, contacts: list[ha.ContactRecord]):
    fair = [c for c in contacts if c.fair]
    xs = [c.distance for c in fair]
    ys = [c.apex for c in fair]
    sizes = [20 + c.hang_frames * 0.8 for c in fair]
    colors = ["#ff9500" if c.result == "HR"
              else "#2ca02c" if c.is_hit
              else "#999999" for c in fair]
    ax.scatter(xs, ys, s=sizes, c=colors, alpha=0.75, edgecolors="black", linewidths=0.4)
    ax.set_xlabel("Carry distance (sim)", fontsize=9)
    ax.set_ylabel("Apex height (sim)", fontsize=9)
    ax.set_title("Hit profile - size = hang time")
    handles = [
        plt.Line2D([], [], color="#2ca02c", marker="o", lw=0, label="Hit"),
        plt.Line2D([], [], color="#ff9500", marker="o", lw=0, label="HR"),
        plt.Line2D([], [], color="#999999", marker="o", lw=0, label="Out"),
    ]
    ax.legend(handles=handles, fontsize=8, loc="upper left")


# ---------------------------------------------------------------- driver

def render_game_summary(stat_path, out_path=None) -> Path:
    with open(stat_path) as f:
        stat = StatObj(json.load(f))
    contacts = ha.simulate_contacts(stat)
    highlight_lines = ha.format_highlights(
        ha.game_highlights(contacts, stadium=stat.stadium()))

    away, home = stat.player(0), stat.player(1)
    score = f"{away} {stat.score(0)} - {stat.score(1)} {home}"

    fig = plt.figure(figsize=(16, 9))
    gs = fig.add_gridspec(2, 2, width_ratios=[1.55, 1], hspace=0.32, wspace=0.18,
                          left=0.05, right=0.98, top=0.88, bottom=0.12)
    ax_field = fig.add_subplot(gs[:, 0])
    ax_power = fig.add_subplot(gs[0, 1])
    ax_profile = fig.add_subplot(gs[1, 1])

    _draw_field(ax_field, stat, contacts)
    _draw_power_leaderboard(ax_power, contacts)
    _draw_hit_profile(ax_profile, contacts)

    fig.suptitle(f"{score}  |  {stat.stadium()}  |  {stat.inningsPlayed()} innings",
                 fontsize=16, fontweight="bold")
    fig.text(0.05, 0.02, "\n".join(highlight_lines), fontsize=9, family="monospace", va="bottom")

    if out_path is None:
        out_path = Path.cwd() / f"game_summary_{stat.gameID()}.png"
    out_path = Path(out_path)
    fig.savefig(out_path, dpi=130)
    plt.close(fig)
    return out_path


def main(argv=None):
    import argparse
    parser = argparse.ArgumentParser(description="Render a game summary graphic from a stat file")
    parser.add_argument("path", help="decoded stat file")
    parser.add_argument("-o", "--out", default=None, help="output PNG path")
    args = parser.parse_args(argv)
    out = render_game_summary(args.path, args.out)
    print(f"saved {out}")
    with open(args.path) as f:
        stat = StatObj(json.load(f))
    contacts = ha.simulate_contacts(stat)
    for line in ha.format_highlights(ha.game_highlights(contacts, stadium=stat.stadium())):
        print(line)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
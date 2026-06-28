"""Dev-only visualizer for hit-simulator trajectories vs. recorded stat files.

NOT part of the shipped package -- add to .gitignore. Draws a top-down (X vs Z)
view of one or more stadiums and overlays, for every contact event in the given
stat files, the simulated flight path against the recorded landing.

Color key (per event), with the failing (red) events highlighted and the rest
faded:
  * green  -- clean natural landing within the threshold of the recording
  * red    -- clean natural landing but OFF by more than the threshold
  * gray   -- IGNORED: the recorded landing was determined by a fielder
              (caught for an out / reached via a fielder action), so the
              air-only sim is not expected to match it.
  * orange -- IGNORED: the flight path passes through a Peach Garden note block,
              which deflects the ball in a way the air-only sim can't model.
Landing is compared in 3D and matches hit_sim_validation (field-boundary crossing
for balls that leave the park, bounce-to-hang-time for in-park grounders).
Garlic (Wario/Waluigi) second-ball paths are drawn as dotted lines.

Usage:
    python -m pyrio.hit_sim_visualizer                       # all data/starHitExamples/*.json
    python -m pyrio.hit_sim_visualizer file1.json file2.json
    python -m pyrio.hit_sim_visualizer --threshold 1.0 --out viz.png
    python -m pyrio.hit_sim_visualizer --no-show            # just save the PNG(s)
"""
from __future__ import annotations

import argparse
import json
import math
import sys
from collections import namedtuple
from pathlib import Path

import matplotlib.pyplot as plt

# Work both as a module (`python -m pyrio.hit_sim_visualizer`) and as a plain
# script / IDE "Run" (`python pyrio/hit_sim_visualizer.py`), where there is no
# parent package for relative imports.
if __package__:
    from .. import hit_simulation as hs
    from .. import hit_sim_validation as v
    from .. import hit_sim_api_validation as av
    from .. import hit_sim_report as hr
    from .. import rio_tags
    from .. import stadiums
    from ..constants import game_constants as G
    from ..stat_file_parser import StatObj, EventObj
else:
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
    import hit_simulation as hs
    import hit_sim_validation as v
    import hit_sim_api_validation as av
    import hit_sim_report as hr
    import rio_tags
    import stadiums
    from ..constants import game_constants as G
    from ..stat_file_parser import StatObj, EventObj

_HERE = Path(__file__).resolve().parent
_STADIUMS_DIR = _HERE / "constants" / "stadiums"
_DEFAULT_DIR = _HERE / "data" / "starHitExamples"

# Encoded StadiumID (G.STADIUM_ID_TO_NAME) -> stadium boundary file stem.
_STADIUM_FILE = {
    0x0: "mario_stadium",
    0x1: "bowser_castle",
    0x2: "wario_palace",
    0x3: "yoshi_park",
    0x4: "peach_garden",
    0x5: "dk_jungle",
    0x6: "toy_field",
}

_OK, _MISS, _IGNORED, _NOTEBLOCK = "ok", "miss", "ignored", "noteblock"
_COLOR = {_OK: "tab:green", _MISS: "tab:red", _IGNORED: "0.55", _NOTEBLOCK: "tab:orange"}
_LABEL = {
    _OK: "within threshold",
    _MISS: "off by > threshold",
    _IGNORED: "ignored (fielder-determined)",
    _NOTEBLOCK: "ignored (note-block deflected)",
}
# Per-category drawing emphasis: fade the passing (green), ignored (gray) and
# note-block-deflected (orange) events so the failing (red) ones stand out.
_STYLE = {
    _OK:        {"alpha": 0.12, "lw": 1.0, "zorder": 2, "ms": 4, "annotate": False},
    _IGNORED:   {"alpha": 0.10, "lw": 1.0, "zorder": 2, "ms": 4, "annotate": False},
    _NOTEBLOCK: {"alpha": 0.35, "lw": 1.2, "zorder": 3, "ms": 5, "annotate": False},
    _MISS:      {"alpha": 0.95, "lw": 2.3, "zorder": 6, "ms": 7, "annotate": True},
}

# One drawable event, decoupled from its source (stat file or API row):
#   traj         -- list of (x, y, z) flight points
#   garlic       -- garlic 2nd-ball (x, y, z) points, or None
#   sim_landing  -- simulated landing (x, y, z) to compare
#   rec_landing  -- recorded landing (x, y, z), or None
#   label        -- annotation text (e.g. "ev12 Boo")
#   cat, err     -- category (_OK/_MISS/_IGNORED/_NOTEBLOCK) and 3D error (or None)
_Row = namedtuple("_Row", "traj garlic sim_landing rec_landing label cat err")


def _stadium_boundary(file_stem):
    """(xs, zs) of the stadium outline, or None if there's no boundary file."""
    path = _STADIUMS_DIR / f"{file_stem}.txt"
    if not path.exists():
        return None
    xs, zs = [], []
    with open(path) as f:
        for line in f:
            line = line.split()
            if len(line) != 2:
                continue
            xs.append(float(line[0]))
            zs.append(float(line[1]))
    return xs, zs


def _draw_foul_lines(ax, length=110.0):
    e = length * math.cos(math.pi / 4)
    ax.plot([0, e], [0, e], color="0.8", lw=1, zorder=0)
    ax.plot([0, -e], [0, e], color="0.8", lw=1, zorder=0)


def _collect_events(paths):
    """Yield (event, contact, stadium_code, stadium_name, active_tags) per contact."""
    for path in paths:
        with open(path) as f:
            stat = StatObj(json.load(f))
        stadium_name = stat.stadium()
        try:
            stadium_code = G.to_encoded(G.STADIUM_ID_TO_NAME, stadium_name)
        except (KeyError, TypeError):
            stadium_code = None
        try:
            tags = rio_tags.active_tags_for_stat(stat)
        except Exception:
            tags = frozenset()
        for i in range(len(list(stat.events()))):
            event = EventObj(stat, i)
            contact = event.contact_dict()
            if contact and "Ball Landing Position - X" in contact:
                yield event, contact, stadium_code, stadium_name, tags


def _recorded_landing(contact):
    """Recorded (x, y, z) landing, or None if unavailable."""
    try:
        return (float(contact["Ball Landing Position - X"]),
                float(contact["Ball Landing Position - Y"]),
                float(contact["Ball Landing Position - Z"]))
    except (KeyError, TypeError, ValueError):
        return None


def _effective_landing(event, contact, result, stadium_name, tags):
    """The simulated landing to compare, matching hit_sim_validation: the
    field-boundary crossing's nearest trajectory point for balls that left the
    park, else the bounce trajectory walked to the recorded hang time, else the
    aerial landing."""
    if stadiums.boundary_crossing(result.trajectory, stadium_name) is not None:
        rec = _recorded_landing(contact)
        near = stadiums.nearest_trajectory_point(result.trajectory, rec) if rec else None
        return near[2] if near else tuple(result.landing)
    try:
        hang = int(str(contact.get("Ball Hang Time")).replace(",", ""))
    except (TypeError, ValueError):
        hang = None
    if hang and hang > 0:
        try:
            return hs.simulate_hit_trajectory_from_event(event, hang, tags)[-1]
        except Exception:
            pass
    return tuple(result.landing)


def _classify(contact, result, landing, stadium_name, threshold):
    """(category, error) for one event. error is None when ignored. 3D distance."""
    if not v._is_natural_landing(contact):
        return _IGNORED, None
    rec = _recorded_landing(contact)
    if rec is None:
        return _IGNORED, None
    # Peach Garden note blocks deflect balls the air-sim flies straight through.
    if stadiums.note_block_hit(result.trajectory, stadium_name) is not None:
        return _NOTEBLOCK, math.dist(rec, landing)
    err = math.dist(rec, landing)
    return (_OK if err <= threshold else _MISS), err


def _plot_stadium(ax, stadium_code, rows):
    """Draw one stadium panel; rows is a list of _Row."""
    file_stem = _STADIUM_FILE.get(stadium_code)
    boundary = _stadium_boundary(file_stem) if file_stem is not None else None
    if boundary:
        ax.plot(boundary[0], boundary[1], color="0.3", lw=1.2, zorder=1)
    _draw_foul_lines(ax)
    ax.plot(0, 0, marker="H", color="black", ms=8, zorder=5)  # home plate

    # Draw misses last so they sit on top of the faded passing/ignored events.
    rows = sorted(rows, key=lambda r: _STYLE[r.cat]["zorder"])
    for row in rows:
        color = _COLOR[row.cat]
        st = _STYLE[row.cat]
        a, lw, z = st["alpha"], st["lw"], st["zorder"]
        traj = row.traj
        ax.plot([p[0] for p in traj], [p[2] for p in traj],
                color=color, lw=lw, alpha=a, zorder=z)
        # garlic second ball, if any
        if row.garlic:
            g = row.garlic
            ax.plot([p[0] for p in g], [p[2] for p in g],
                    color=color, lw=lw * 0.8, ls=":", alpha=a, zorder=z)
            ax.plot(g[-1][0], g[-1][2], marker="^", color=color, ms=st["ms"], mfc="none",
                    alpha=a, zorder=z)
        # simulated landing + recorded landing + the error connector
        sx, sz = row.sim_landing[0], row.sim_landing[2]
        ax.plot(sx, sz, marker="o", color=color, ms=st["ms"], alpha=a, zorder=z)
        if row.rec_landing is not None:
            rx, rz = row.rec_landing[0], row.rec_landing[2]
            ax.plot(rx, rz, marker="x", color=color, ms=st["ms"] + 1, mew=1.6, alpha=a, zorder=z)
            ax.plot([sx, rx], [sz, rz], color=color, lw=0.8, ls="--", alpha=a, zorder=z)
        if st["annotate"]:
            tag = row.label
            if row.err is not None:
                tag += f" ({row.err:.2f})"
            ax.annotate(tag, (sx, sz), textcoords="offset points", xytext=(4, 4),
                        fontsize=7, color=color, zorder=z + 1)

    name = G.STADIUM_ID_TO_NAME.get(stadium_code, "Unknown stadium")
    ax.set_title(name)
    ax.set_xlabel("X")
    ax.set_ylabel("Z")
    ax.set_aspect("equal", adjustable="datalim")
    ax.grid(True, color="0.92")


def _render(by_stadium, n_ok, n_total, threshold, out, show, suptitle=None):
    """Build one figure per stadium from {stadium_code: [_Row, ...]}, optionally
    save to `out` (stadium suffix added when >1), and print the clean-rate."""
    if not by_stadium:
        print("No drawable contact events found.")
        return

    figs = []
    for stadium_code, rows in sorted(by_stadium.items(), key=lambda kv: (kv[0] is None, kv[0])):
        fig, ax = plt.subplots(figsize=(9, 8))
        _plot_stadium(ax, stadium_code, rows)
        if suptitle:
            fig.suptitle(suptitle, fontsize=10)
        # legend from category handles
        handles = [plt.Line2D([], [], color=c, lw=2) for c in _COLOR.values()]
        labels = list(_LABEL.values())
        handles += [
            plt.Line2D([], [], color="0.4", marker="o", ls="", label="sim landing"),
            plt.Line2D([], [], color="0.4", marker="x", ls="", label="recorded landing"),
            plt.Line2D([], [], color="0.4", lw=1.2, ls=":", label="garlic 2nd ball"),
        ]
        labels += ["sim landing", "recorded landing", "garlic 2nd ball"]
        ax.legend(handles, labels, fontsize=8, loc="upper right")
        fig.tight_layout()
        figs.append((stadium_code, fig))

    if out:
        out = Path(out)
        for stadium_code, fig in figs:
            if len(figs) == 1:
                target = out
            else:
                stem = _STADIUM_FILE.get(stadium_code, str(stadium_code))
                target = out.with_name(f"{out.stem}_{stem}{out.suffix}")
            fig.savefig(target, dpi=130)
            print(f"saved {target}")

    print(f"{n_ok}/{n_total} clean events within {threshold:g} unit(s) "
          f"(ignored fielder-determined events excluded).")
    if show:
        plt.show()


def visualize(paths, threshold=1.0, out=None, show=True):
    """Build one figure per stadium found across `paths` (stat files)."""
    by_stadium: dict = {}
    n_ok = n_total = 0
    for event, contact, stadium_code, stadium_name, tags in _collect_events(paths):
        try:
            result = hs.simulate_hit_from_event(event, tags)
        except Exception as exc:  # bunts, no-contact, etc. -- skip in a dev tool
            print(f"  skip ev{event.event_num()} {event.batter()}: {exc}")
            continue
        landing = _effective_landing(event, contact, result, stadium_name, tags)
        cat, err = _classify(contact, result, landing, stadium_name, threshold)
        by_stadium.setdefault(stadium_code, []).append(
            _Row(result.trajectory, result.garlic_trajectory, tuple(landing),
                 _recorded_landing(contact), f"ev{event.event_num()} {event.batter()}",
                 cat, err))
        if cat in (_OK, _MISS):
            n_total += 1
            n_ok += cat == _OK

    _render(by_stadium, n_ok, n_total, threshold, out, show)


def _char_name(char_id):
    """Decode an encoded char id to its character name (for annotations)."""
    try:
        return hs._load_attr_rows()[int(char_id)]["Character"]
    except (KeyError, ValueError, TypeError):
        return str(char_id)


def visualize_api(tag=None, games=None, limit_games=None, threshold=1.0,
                  out=None, show=True):
    """Build one figure per stadium for games pulled from ProjectRio's
    /landing_data/ endpoint (the API counterpart to `visualize`). Selection
    mirrors hit_sim_api_validation: `tag`, specific `games`, and/or `limit_games`.
    """
    from ..api_manager import APIManager
    api = APIManager()
    params = av._filter_params(tag, games, None, limit_games)
    games_resp = api.send_request(av.Endpoints.GAMES, "GET", params) or {}
    ctx = av._game_context(games_resp.get("games", []))
    landing_resp = api.send_request(av.Endpoints.LANDING_DATA, "GET", params) or {}
    # The /games/ metadata lookup (which carries stadium + game_mode) doesn't honor
    # the `games` filter, so narrow to the requested game ids client-side too.
    wanted = set(games) if games else None
    rows = [r for r in landing_resp.get("Data", [])
            if r["game_id"] in ctx and (wanted is None or r["game_id"] in wanted)]

    by_stadium: dict = {}
    n_ok = n_total = 0
    for r in rows:
        stadium_id, tags, stars_on = ctx[r["game_id"]]
        stadium_name = G.STADIUM_ID_TO_NAME[stadium_id]
        if int(r["type_of_swing"]) not in av._SUPPORTED_SWING_CODES:
            continue
        try:
            inputs = hs._inputs_from_landing_row(r, stadium_id, tags, stars_on, stars_on)
            result = hs.simulate_hit(inputs)
        except Exception as exc:  # bunts, no-contact, etc. -- skip in a dev tool
            print(f"  skip ev{r.get('event_num')}: {exc}")
            continue

        rec = (float(r["ball_x_landing_pos"]), float(r["ball_y_landing_pos"]),
               float(r["ball_z_landing_pos"]))
        hang = int(r["ball_hang_time"]) if r.get("ball_hang_time") else None
        hr.resolve_landing(result, stadium_name, rec, bounces=True, hang_time=hang,
                           walk_to_hang=lambda f, _in=inputs: hs.simulate_hit_trajectory(_in, f))
        landing = tuple(result.landing)

        if not av._is_natural_landing(r):
            cat, err = _IGNORED, None
        elif hr.note_block_deflected(result, stadium_name):
            cat, err = _NOTEBLOCK, math.dist(rec, landing)
        else:
            err = math.dist(rec, landing)
            cat = _OK if err <= threshold else _MISS
        label = f"ev{r.get('event_num')} {_char_name(r['batter_char_id'])}"
        by_stadium.setdefault(stadium_id, []).append(
            _Row(result.trajectory, result.garlic_trajectory, landing, rec, label, cat, err))
        if cat in (_OK, _MISS):
            n_total += 1
            n_ok += cat == _OK

    suptitle = None
    if games and len(games) == 1:
        suptitle = f"game {games[0]}"
    _render(by_stadium, n_ok, n_total, threshold, out, show, suptitle=suptitle)


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("paths", nargs="*", help="stat-file JSONs (default: data/starHitExamples/*.json)")
    ap.add_argument("--threshold", type=float, default=1.0, help="match threshold in units (default 1.0)")
    ap.add_argument("--out", help="save figure(s) to this PNG path (stadium suffix added if >1)")
    ap.add_argument("--no-show", dest="show", action="store_false", help="don't open a window")
    # API mode: pull games from ProjectRio's /landing_data/ instead of local files.
    ap.add_argument("--api", action="store_true",
                    help="pull events from the /landing_data/ endpoint instead of stat files")
    ap.add_argument("--game", type=int, action="append", dest="games",
                    help="(API mode) a specific game id (repeatable)")
    ap.add_argument("--tag", action="append",
                    help="(API mode) only games carrying this gecko tag (repeatable)")
    ap.add_argument("--limit-games", type=int, default=None,
                    help="(API mode) cap to the newest N matching games")
    args = ap.parse_args(argv)

    if args.api or args.games or args.tag:
        visualize_api(tag=args.tag, games=args.games, limit_games=args.limit_games,
                      threshold=args.threshold, out=args.out, show=args.show)
        return

    paths = [Path(p) for p in args.paths] or sorted(_DEFAULT_DIR.glob("*.json"))
    if not paths:
        ap.error(f"no input files (looked in {_DEFAULT_DIR})")
    visualize(paths, threshold=args.threshold, out=args.out, show=args.show)


if __name__ == "__main__":
    main()

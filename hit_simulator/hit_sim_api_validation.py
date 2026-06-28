"""Validate the hit simulator against ProjectRio's /landing_data/ endpoint.

The API counterpart to hit_sim_validation (which reads local decoded stat files):
instead of parsing files, this pulls recorded contact + landing data straight
from the server and reproduces each event with the simulator. The comparison
machinery -- FieldSpec / ValidationReport / summary and the landing post-
processing -- is shared via hit_sim_report; only the record source and the
per-game input resolution are different here.

A /landing_data/ row carries almost every simulator input already encoded, so
events come through hit_simulation.simulate_hit_from_landing_row. The three
game-level facts the row omits are resolved from the API per game:

  - stadium    -- from /games/ (drives the ground plane / bounce).
  - active mods-- a game's ``game_mode`` IS its tag-set id, so its tags come from
                  rio_tags; TAG_TO_FLAG picks out the ones the simulator models
                  (e.g. Remove slice, the Toad bat-reach fix).
  - superstars -- on unless the tag set carries "Disable Superstars".

Quirk: the endpoint's ``ball_horiz_angle`` and ``ball_vert_angle`` columns are
swapped relative to the simulator's convention, so the contact field specs read
them crosswise. Walu tech can't be detected from a row (no team star count), so
under-starred star swings won't be corrected -- the same caveat as
simulate_hit_from_landing_row.

Usage:
    from pyrio import hit_sim_api_validation as v
    report = v.validate_api(tag="Enable Hazardless", limit_games=5, include_landing=True)
    print(report.summary())

CLI:
    python -m pyrio.hit_sim_api_validation --tag "Enable Hazardless" --limit-games 5 --landing
    python -m pyrio.hit_sim_api_validation --game 229094479689 --game 281593399191 --landing
"""
from __future__ import annotations

from typing import Optional

from .. import hit_simulation as hs
from .. import rio_tags
from ..api_manager import APIManager
from ..constants import game_constants as G
from ..lookup import LookupDicts
from .hit_sim_report import (FieldSpec, ValidationReport, note_block_deflected,
                             resolve_landing)

class Endpoints:
    GAMES = "/games/"
    LANDING_DATA = "/landing_data/"


# Type of Swing codes the simulator supports: 1 Slap, 2 Charge, 3 Star.
_SUPPORTED_SWING_CODES = (1, 2, 3)
# final_result codes where the ball came down on its own (singles..home run), so
# the recorded landing is a natural landing rather than a fielder-catch point.
_NATURAL_RESULT_CODES = frozenset({7, 8, 9, 10})
# A tag set carrying this has superstars (stat buffs) turned off for the game.
_DISABLE_SUPERSTARS_TAG = "Disable Superstars"


# ---------------------------------------------------------------- field specs
# API flavor: recorded values come straight off a /landing_data/ row.

def _contact_field_specs(vel_tol: float, float_tol: float) -> list[FieldSpec]:
    return [
        FieldSpec("contact_type",
                  lambda r: int(r["type_of_contact"]),
                  lambda res: res.contact_type),
        FieldSpec("contact_absolute",
                  lambda r: float(r["contact_absolute"]),
                  lambda res: res.contact_absolute, tol=float_tol),
        FieldSpec("contact_quality",
                  lambda r: float(r["contact_quality"]),
                  lambda res: res.contact_quality, tol=float_tol),
        # NOTE: ball_horiz_angle / ball_vert_angle are swapped in the endpoint, so
        # read them crosswise against the simulator's horizontal/vertical angle.
        FieldSpec("horizontal_angle",
                  lambda r: int(r["ball_vert_angle"]),
                  lambda res: res.horizontal_angle),
        FieldSpec("vertical_angle",
                  lambda r: int(r["ball_horiz_angle"]),
                  lambda res: res.vertical_angle),
        FieldSpec("power",
                  lambda r: int(r["ball_power"]),
                  lambda res: res.power),
        FieldSpec("velocity_x",
                  lambda r: r["ball_x_velocity"],
                  lambda res: res.velocity[0], tol=vel_tol),
        FieldSpec("velocity_y",
                  lambda r: r["ball_y_velocity"],
                  lambda res: res.velocity[1], tol=vel_tol),
        FieldSpec("velocity_z",
                  lambda r: r["ball_z_velocity"],
                  lambda res: res.velocity[2], tol=vel_tol),
    ]


def _landing_field_spec(landing_tol: float) -> FieldSpec:
    return FieldSpec("landing",
                     lambda r: (float(r["ball_x_landing_pos"]),
                                float(r["ball_y_landing_pos"]),
                                float(r["ball_z_landing_pos"])),
                     lambda res: tuple(res.landing), tol=landing_tol)


def _is_natural_landing(row: dict) -> bool:
    """True if the row's landing is where the ball naturally came down (a hit),
    not a fielder-catch point (an out). The row lacks the fielder-action detail
    the stat-file path uses, so the at-bat result is the proxy."""
    try:
        return int(row["final_result"]) in _NATURAL_RESULT_CODES
    except (KeyError, TypeError, ValueError):
        return False


# ---------------------------------------------------------------- fetch / resolve

def _filter_params(tag, games, username, limit_games) -> dict:
    params: dict = {}
    if tag:
        params["tag"] = tag
    if games:
        params["games"] = games          # repeatable; filters to specific game ids
    if username:
        params["username"] = username
    if limit_games is not None:
        params["limit_games"] = limit_games
    return params


def _game_context(games_rows) -> dict:
    """game_id -> (stadium_id, active_tags, stars_on), all resolved from the API.

    A game's ``game_mode`` is its tag-set id, so the active gecko tags (and thus
    the simulator mod flags and whether superstars are on) come from rio_tags.
    """
    ctx = {}
    for g in games_rows:
        tags = rio_tags.tags_for_tag_set(g["game_mode"])
        stars_on = _DISABLE_SUPERSTARS_TAG not in tags
        ctx[g["game_id"]] = (g["stadium"], tags, stars_on)
    return ctx


# ---------------------------------------------------------------- driver

def validate_api(*, tag=None, games=None, username=None, limit_games=None,
                 include_landing: bool = False, landing_exclude_caught: bool = True,
                 bounces: bool = True, vel_tol: float = 1e-4, float_tol: float = 1e-3,
                 landing_tol: float = 1.0, api: Optional[APIManager] = None,
                 report: Optional[ValidationReport] = None) -> ValidationReport:
    """Fetch landing data for the selected games and compare each event to the sim.

    Selection mirrors the endpoint's filters: ``tag`` (gecko tag name),
    ``games`` (specific game ids), ``username``, and/or ``limit_games`` (newest N).
    Contact-stage fields are the real validation; ``include_landing`` adds the 3D
    landing comparison (informational -- fence balls use the boundary nearest-
    point, in-park balls the bounce/skid at hang time, and caught/note-block
    landings are excluded), matching the stat-file validator.
    """
    api = api or APIManager()
    report = report or ValidationReport()

    params = _filter_params(tag, games, username, limit_games)
    games_resp = api.send_request(Endpoints.GAMES, "GET", params) or {}
    ctx = _game_context(games_resp.get("games", []))
    report.files += len(ctx)

    landing_resp = api.send_request(Endpoints.LANDING_DATA, "GET", params) or {}
    rows = [r for r in landing_resp.get("Data", []) if r["game_id"] in ctx]

    specs = _contact_field_specs(vel_tol, float_tol)
    landing_spec = _landing_field_spec(landing_tol) if include_landing else None

    for r in rows:
        report.total_events += 1
        report.contact_events += 1          # a landing row always carries contact
        gid, ev = r["game_id"], r.get("event_num")
        stadium_id, active_tags, stars_on = ctx[gid]
        stadium_name = LookupDicts.STADIUM[stadium_id]

        swing_code = int(r["type_of_swing"])
        if swing_code not in _SUPPORTED_SWING_CODES:
            report.skipped.append((gid, ev, f"unsupported swing: {swing_code}"))
            continue

        inputs = hs._inputs_from_landing_row(r, stadium_id, active_tags, stars_on, stars_on)
        try:
            result = hs.simulate_hit(inputs)
        except ValueError as ex:
            report.skipped.append((gid, ev, f"value error: {ex}"))
            continue
        except Exception as ex:  # noqa: BLE001 - surface unexpected failures
            report.errors.append((gid, ev, f"{type(ex).__name__}: {ex}"))
            continue
        report.simulated += 1

        for spec in specs:
            try:
                ok, rec, com = spec.matches(r, result)
            except (KeyError, TypeError, ValueError):
                continue
            st = report._stat(spec.name)
            st.total += 1
            if ok:
                st.matches += 1
            else:
                st.mismatches.append((gid, ev, rec, com))

        if not include_landing:
            continue
        rec_pt = (float(r["ball_x_landing_pos"]), float(r["ball_y_landing_pos"]),
                  float(r["ball_z_landing_pos"]))
        hang = int(r["ball_hang_time"]) if r.get("ball_hang_time") else None
        resolve_landing(result, stadium_name, rec_pt, bounces=bounces, hang_time=hang,
                        walk_to_hang=lambda f, _in=inputs: hs.simulate_hit_trajectory(_in, f))
        skip = landing_exclude_caught and not _is_natural_landing(r)
        if not skip and note_block_deflected(result, stadium_name):
            skip = True
        if skip:
            continue
        ok, rec, com = landing_spec.matches(r, result)
        st = report._stat("landing")
        st.total += 1
        if ok:
            st.matches += 1
        else:
            st.mismatches.append((gid, ev, rec, com))

    return report


def main(argv=None):
    import argparse
    parser = argparse.ArgumentParser(
        description="Validate the hit simulator against ProjectRio's /landing_data/ endpoint")
    parser.add_argument("--tag", action="append",
                        help="only games carrying this gecko tag (repeatable), "
                             'e.g. --tag "Enable Hazardless"')
    parser.add_argument("--game", type=int, action="append", dest="games",
                        help="a specific game id (repeatable)")
    parser.add_argument("--username", action="append",
                        help="only games involving this user (repeatable)")
    parser.add_argument("--limit-games", type=int, default=None,
                        help="cap to the newest N matching games (the endpoint "
                             "defaults to 50 when omitted)")
    parser.add_argument("--landing", action="store_true",
                        help="also compare the 3D landing (informational; fence "
                             "balls use the field-boundary crossing, caught and "
                             "note-block landings are excluded)")
    parser.add_argument("--include-caught-landing", action="store_true",
                        help="include fielder-determined (out) landings in the "
                             "landing comparison")
    args = parser.parse_args(argv)
    report = validate_api(tag=args.tag, games=args.games, username=args.username,
                          limit_games=args.limit_games, include_landing=args.landing,
                          landing_exclude_caught=not args.include_caught_landing)
    print(report.summary())
    # Exit status reflects the deterministic fields only; landing is informational.
    return 0 if report.contact_fields_perfect() and not report.errors else 1


if __name__ == "__main__":
    raise SystemExit(main())

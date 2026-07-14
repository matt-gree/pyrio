"""Stat formatters and derived stat calculators for Mario Superstar Baseball.

Individual stat functions accept **kwargs so callers can pass a full stat dict
(e.g. ``derive_batting(**hud_batting)``) without pre-filtering keys.

Batting derived stats (derive_batting):
    avg      — batting average (H / AB)
    slg      — slugging percentage
    obp      — on-base percentage
    ops      — on-base plus slugging
    so_pct   — strikeout percentage (SO / AB × 100)

Pitching derived stats (derive_pitching):
    era      — earned run average (27-out scale for 9-inning game)
    ip       — innings pitched as "X.Y" string (e.g. "6.1")
    k_pct    — strikeout percentage (K / BF × 100)
    opp_avg  — opponent batting average (H / BF)
"""


# ── Batting ───────────────────────────────────────────────────────────────────

def batting_avg(*, at_bats=0, hits=0, **_) -> float:
    """Batting average: H / AB, rounded to 3 decimal places."""
    return round(hits / at_bats, 3) if at_bats else 0.0


def slugging_pct(*, at_bats=0, singles=0, doubles=0, triples=0, homeruns=0, **_) -> float:
    """Slugging percentage: (1B + 2×2B + 3×3B + 4×HR) / AB."""
    return round((singles + 2 * doubles + 3 * triples + 4 * homeruns) / at_bats, 3) if at_bats else 0.0


def on_base_pct(*, at_bats=0, hits=0, walks_bb=0, walks_hbp=0, sac_flys=0, **_) -> float:
    """On-base percentage: (H + BB + HBP) / (AB + BB + HBP + SF)."""
    denom = at_bats + walks_bb + walks_hbp + sac_flys
    return round((hits + walks_bb + walks_hbp) / denom, 3) if denom else 0.0


def ops(*, at_bats=0, hits=0, singles=0, doubles=0, triples=0, homeruns=0,
        walks_bb=0, walks_hbp=0, sac_flys=0, **_) -> float:
    """On-base plus slugging (OBP + SLG)."""
    obp = on_base_pct(at_bats=at_bats, hits=hits, walks_bb=walks_bb,
                      walks_hbp=walks_hbp, sac_flys=sac_flys)
    slg = slugging_pct(at_bats=at_bats, singles=singles, doubles=doubles,
                       triples=triples, homeruns=homeruns)
    return round(obp + slg, 3)


def so_pct(*, at_bats=0, strikeouts=0, **_) -> float:
    """Strikeout percentage: SO / AB × 100, rounded to 1 decimal place."""
    return round((strikeouts / at_bats) * 100, 1) if at_bats else 0.0


def derive_batting(**kwargs) -> dict:
    """Compute all derived batting stats from a raw batting stat dict.

    Returns a dict with keys: avg, slg, obp, ops, so_pct.
    Intended to be merged into the batting stat dict before pushing to state.
    """
    return {
        "avg":    batting_avg(**kwargs),
        "slg":    slugging_pct(**kwargs),
        "obp":    on_base_pct(**kwargs),
        "ops":    ops(**kwargs),
        "so_pct": so_pct(**kwargs),
    }


# ── Pitching ──────────────────────────────────────────────────────────────────

def era(*, outs_pitched=0, earned_runs=0, **_) -> float:
    """Earned run average on a 27-out (9-inning) scale, rounded to 1 decimal."""
    return round(27 * (earned_runs / outs_pitched), 1) if outs_pitched else 0.0


def innings_pitched(*, outs_pitched=0, **_) -> str:
    """Innings pitched formatted as 'X.Y' (e.g. '6.1' for 19 outs)."""
    return f"{outs_pitched // 3}.{outs_pitched % 3}"


def k_pct(*, batters_faced=0, strikeouts_pitched=0, **_) -> float:
    """Strikeout percentage: K / BF × 100, rounded to 1 decimal place."""
    return round((strikeouts_pitched / batters_faced) * 100, 1) if batters_faced else 0.0


def opp_avg(*, batters_faced=0, hits_allowed=0, **_) -> float:
    """Opponent batting average: H / BF, rounded to 3 decimal places."""
    return round(hits_allowed / batters_faced, 3) if batters_faced else 0.0


def derive_pitching(**kwargs) -> dict:
    """Compute all derived pitching stats from a raw pitching stat dict.

    Returns a dict with keys: era, ip, k_pct, opp_avg.
    Intended to be merged into the pitching stat dict before pushing to state.
    """
    return {
        "era":     era(**kwargs),
        "ip":      innings_pitched(**kwargs),
        "k_pct":   k_pct(**kwargs),
        "opp_avg": opp_avg(**kwargs),
    }


# ── Line score formatters ─────────────────────────────────────────────────────

def format_batting_line(*, at_bats=0, hits=0, homeruns=0, triples=0, doubles=0,
                        walks_bb=0, walks_hbp=0, rbi=0, stolen_bases=0, **_) -> str:
    """Format a single-game batting line.

    Convention: H-for-AB[, count stat]...
    Stat order (nonzero only): HR → 3B → 2B → BB → HBP → RBI → SB
    Singles are implied. Count prefix only when value > 1 (e.g. "2 HR").

    Examples:
        4 AB, 2 H, 1 HR, 1 2B  → "2-for-4, HR, 2B"
        5 AB, 4 H, 0 HR, 2 2B  → "4-for-5, 2 2B"
        3 AB, 0 H               → "0-for-3"
    """
    line = f"{hits}-for-{at_bats}"
    for val, label in [
        (homeruns,     "HR"),
        (triples,      "3B"),
        (doubles,      "2B"),
        (walks_bb,     "BB"),
        (walks_hbp,    "HBP"),
        (rbi,          "RBI"),
        (stolen_bases, "SB"),
    ]:
        if val > 0:
            line += f", {label}" if val == 1 else f", {val} {label}"
    return line


def format_pitching_line(*, outs_pitched=0, hits_allowed=0, runs_allowed=0,
                         earned_runs=0, walks_bb=0, walks_hbp=0,
                         strikeouts_pitched=0, hrs_allowed=0, total_pitches=0, **_) -> str:
    """Format a single-game pitching line.

    All fields are always shown even if zero (omission is ambiguous in a pitcher line).
    Order: IP, H, R, ER, BB, K, HR, P

    Example: "6.0, 3 H, 1 R, 1 ER, 2 BB, 4 K, 0 HR, 87 P"
    """
    ip = innings_pitched(outs_pitched=outs_pitched)
    bb = walks_bb + walks_hbp
    return (
        f"{ip}, {hits_allowed} H, {runs_allowed} R, {earned_runs} ER, "
        f"{bb} BB, {strikeouts_pitched} K, {hrs_allowed} HR, {total_pitches} P"
    )

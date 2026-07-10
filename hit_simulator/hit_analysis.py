"""Game-level hit analysis built on the hit simulator.

Turns a decoded stat file into structured per-contact records (each contact
re-simulated exactly via its recorded RNG seeds) and provides metrics that the
raw stat file cannot: full flight paths, would-be landing spots for caught
balls, robbery detection, and cross-stadium HR checks.

Typical use:
    from pyrio.hit_analysis import simulate_contacts, game_highlights
    contacts = simulate_contacts(stat_obj)
    hl = game_highlights(contacts, stadium=stat_obj.stadium())
    df = contacts_to_dataframe(contacts)

Caveat: contact-stage outputs (power, angles, velocity) reproduce the game
exactly; the flight path itself uses the calculator's unverified trajectory
model, so landing/HR numbers are good approximations rather than ground truth.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from . import hit_simulation as hs
from .. import stadiums
from .hit_simulation import HitResult
from ..stat_file_parser import StatObj, EventObj

_SUPPORTED_SWINGS = ("Slap", "Charge", "Star")


# ---------------------------------------------------------------- records

@dataclass
class ContactRecord:
    """One simulated ball in play, with its event context."""
    event_num: int
    inning: int
    half_inning: int            # 0 = away batting, 1 = home batting
    player_name: str            # human controlling the batting team
    batter: str
    swing: str                  # Slap / Charge / Star
    result: str                 # event "Result of AB" (e.g. Single, HR, ...)
    primary_result: str         # contact "Contact Result - Primary" (Fair/Foul/Out)
    secondary_result: str       # contact "Contact Result - Secondary"
    rbi: int
    sim: HitResult

    # -- convenience passthroughs to the simulation --
    @property
    def power(self) -> int:
        return self.sim.power

    @property
    def distance(self) -> float:
        return self.sim.distance

    @property
    def hang_frames(self) -> int:
        return self.sim.hang_frames

    @property
    def landing(self) -> tuple:
        return self.sim.landing

    @property
    def trajectory(self) -> list:
        return self.sim.trajectory

    @property
    def apex(self) -> float:
        return max(p[1] for p in self.sim.trajectory)

    @property
    def foul(self) -> bool:
        return self.primary_result == "Foul"

    @property
    def fair(self) -> bool:
        return not self.foul

    @property
    def caught(self) -> bool:
        return self.secondary_result == "Out-caught"

    @property
    def is_hit(self) -> bool:
        return self.result in ("Single", "Double", "Triple", "HR")

    def home_run_stadiums(self) -> list[str]:
        """Stadiums where this trajectory would clear the wall."""
        return stadiums.home_run_stadiums(self.trajectory)


def simulate_contacts(stat: StatObj) -> list[ContactRecord]:
    """Simulate every supported contact event in a game.

    Bunts and other unsupported swings are skipped silently (mirroring
    hit_sim_validation's skip behavior).
    """
    records = []
    for i in range(len(stat.events())):
        event = EventObj(stat, i)
        contact = event.contact_dict()
        if not contact:
            continue
        swing = event.pitch_dict().get("Type of Swing")
        if swing not in _SUPPORTED_SWINGS:
            continue
        try:
            sim = hs.simulate_hit_from_event(event)
        except ValueError:
            continue
        records.append(ContactRecord(
            event_num=i,
            inning=event.inning(),
            half_inning=event.half_inning(),
            player_name=stat.player(event.half_inning()),
            batter=event.batter(),
            swing=swing,
            result=event.result_of_AB(),
            primary_result=contact.get("Contact Result - Primary"),
            secondary_result=contact.get("Contact Result - Secondary"),
            rbi=event.rbi(),
            sim=sim,
        ))
    return records


def contacts_to_dataframe(contacts: list[ContactRecord]):
    """Flatten contact records into a pandas DataFrame (no trajectories)."""
    import pandas as pd

    rows = []
    for c in contacts:
        lx, ly, lz = c.landing
        rows.append({
            "event_num": c.event_num,
            "inning": c.inning,
            "half_inning": c.half_inning,
            "player": c.player_name,
            "batter": c.batter,
            "swing": c.swing,
            "result": c.result,
            "primary_result": c.primary_result,
            "secondary_result": c.secondary_result,
            "rbi": c.rbi,
            "foul": c.foul,
            "caught": c.caught,
            "is_hit": c.is_hit,
            "contact_type": c.sim.contact_type_name,
            "contact_quality": c.sim.contact_quality,
            "power": c.power,
            "horiz_angle": c.sim.horizontal_angle,
            "vert_angle": c.sim.vertical_angle,
            "landing_x": lx,
            "landing_z": lz,
            "distance": c.distance,
            "apex": c.apex,
            "hang_frames": c.hang_frames,
        })
    return pd.DataFrame(rows)


# ---------------------------------------------------------------- metrics

def _fair(contacts):
    return [c for c in contacts if c.fair]


def hardest_hit(contacts: list[ContactRecord]) -> Optional[ContactRecord]:
    fair = _fair(contacts)
    return max(fair, key=lambda c: c.power) if fair else None


def longest_flight(contacts: list[ContactRecord]) -> Optional[ContactRecord]:
    fair = _fair(contacts)
    return max(fair, key=lambda c: c.distance) if fair else None


def highest_apex(contacts: list[ContactRecord]) -> Optional[ContactRecord]:
    fair = _fair(contacts)
    return max(fair, key=lambda c: c.apex) if fair else None


def deepest_robbery(contacts: list[ContactRecord]) -> Optional[ContactRecord]:
    """The caught ball whose simulated landing was deepest."""
    robbed = [c for c in _fair(contacts) if c.caught]
    return max(robbed, key=lambda c: c.distance) if robbed else None


def robbed_home_runs(contacts: list[ContactRecord], stadium: str) -> list[ContactRecord]:
    """Caught balls whose simulated trajectory clears this stadium's wall --
    i.e. plays where the batter was robbed of a home run."""
    return [c for c in _fair(contacts)
            if c.caught and stadiums.is_home_run(c.trajectory, stadium)]


def game_highlights(contacts: list[ContactRecord],
                    stadium: Optional[str] = None) -> dict:
    """Structured highlight package for a game.

    Returns a dict with keys: hardest_hit, longest_flight, highest_apex,
    deepest_robbery (ContactRecord or None) and robbed_home_runs (list;
    empty when no stadium given).
    """
    return {
        "hardest_hit": hardest_hit(contacts),
        "longest_flight": longest_flight(contacts),
        "highest_apex": highest_apex(contacts),
        "deepest_robbery": deepest_robbery(contacts),
        "robbed_home_runs": robbed_home_runs(contacts, stadium) if stadium else [],
    }


def format_highlights(highlights: dict) -> list[str]:
    """Render a highlight package as human-readable lines."""
    lines = []
    c = highlights.get("hardest_hit")
    if c:
        lines.append(f"HARDEST HIT: {c.batter} ({c.player_name}) - "
                     f"{c.power} power {c.result}, inning {c.inning}")
    c = highlights.get("longest_flight")
    if c:
        lines.append(f"LONGEST FLIGHT: {c.batter} ({c.player_name}) - "
                     f"{c.distance:.1f} units, {c.result}, inning {c.inning}")
    c = highlights.get("highest_apex")
    if c:
        lines.append(f"MOONBALL: {c.batter} ({c.player_name}) - "
                     f"apex {c.apex:.1f}, {c.hang_frames} frame hang time")
    c = highlights.get("deepest_robbery")
    if c:
        lines.append(f"ROBBERY OF THE GAME: {c.batter} ({c.player_name}) - "
                     f"caught ball would have landed {c.distance:.1f} units deep "
                     f"(inning {c.inning})")
    for c in highlights.get("robbed_home_runs", []):
        lines.append(f"ROBBED HOME RUN: {c.batter} ({c.player_name}) - "
                     f"inning {c.inning}, trajectory cleared the wall")
    return lines

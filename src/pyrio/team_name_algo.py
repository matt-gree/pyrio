"""Resolve the in-game team name for a custom roster.

Each captain has four team logos (see ``Tables.TEAM_NAME``): two **signature**
rosters (named when every one of their characters is on the roster), one
**captain-class** team (chosen when the captain's character class is the roster's
strict plurality), and a **default**. ``CAPTAIN_TEAMS`` models those roles with
value objects: keyed by the captain :class:`Character`, holding :class:`TeamName`
logos and :class:`BaseCharacter` signature sets.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from .rio_value import BaseCharacter, Character, Tables, TeamName

CLASSES = ('Balance', 'Technique', 'Speed', 'Power')

# All in-game team logos, from the canonical logo table.
in_game_team_names_list = [TeamName.from_raw(logo_id) for logo_id in Tables.TEAM_NAME]


def _signature(name: str, *members: str) -> tuple[TeamName, frozenset]:
    """A signature: its team logo plus the base characters that must all appear."""
    return TeamName.from_raw(name), frozenset(map(BaseCharacter.from_raw, members))


@dataclass(frozen=True)
class CaptainTeams:
    """The four team logos a captain can field, by role."""

    default: TeamName
    class_team: TeamName                                          # captain's-class plurality
    signatures: tuple[tuple[TeamName, frozenset[BaseCharacter]], ...]


# captain Character -> CaptainTeams, built straight from value objects. Names
# resolve through TeamName.from_raw / BaseCharacter.from_raw, so a typo'd logo or
# character raises here at import (e.g. it would have caught 'Bry Bones').
CAPTAIN_TEAMS: dict[Character, CaptainTeams] = {
    Character.from_raw("Mario"): CaptainTeams(
        TeamName.from_raw("Mario Heroes"), TeamName.from_raw("Mario Fireballs"),
        (_signature("Mario Sunshines", "Luigi", "Monty", "Pianta", "Noki"),
         _signature("Mario All Stars", "Peach", "Yoshi", "DK", "Bowser"))),
    Character.from_raw("Luigi"): CaptainTeams(
        TeamName.from_raw("Luigi Gentlemen"), TeamName.from_raw("Luigi Vacuums"),
        (_signature("Luigi Mansioneers", "Bowser", "Toad", "Boo", "King Boo"),
         _signature("Luigi Leapers", "Waluigi", "Diddy", "Daisy", "Baby Luigi"))),
    Character.from_raw("Peach"): CaptainTeams(
        TeamName.from_raw("Peach Roses"), TeamName.from_raw("Peach Dynasties"),
        (_signature("Peach Monarchs", "Daisy", "Toad", "Toadsworth", "Toadette"),
         _signature("Peach Princesses", "Mario", "Bowser", "Baby Mario", "Bowser Jr"))),
    Character.from_raw("Daisy"): CaptainTeams(
        TeamName.from_raw("Daisy Lillies"), TeamName.from_raw("Daisy Cupids"),
        (_signature("Daisy Queen Bees", "Peach", "Dixie", "Toadette", "Noki"),
         _signature("Daisy Petals", "Birdo", "Dixie", "Wario", "Petey"))),
    Character.from_raw("Yoshi"): CaptainTeams(
        TeamName.from_raw("Yoshi Eggs"), TeamName.from_raw("Yoshi Speed Stars"),
        (_signature("Yoshi Islanders", "Birdo", "Baby Mario", "Baby Luigi", "Shy Guy"),
         _signature("Yoshi Flutters", "Boo", "King Boo", "Paratroopa", "Paragoomba"))),
    Character.from_raw("Birdo"): CaptainTeams(
        TeamName.from_raw("Birdo Beauties"), TeamName.from_raw("Birdo Models"),
        (_signature("Birdo Bows", "Mario", "Luigi", "Peach", "Toad"),
         _signature("Birdo Fans", "Yoshi", "Shy Guy", "Goomba", "Koopa"))),
    Character.from_raw("Wario"): CaptainTeams(
        TeamName.from_raw("Wario Garlics"), TeamName.from_raw("Wario Steakheads"),
        (_signature("Wario Greats", "Waluigi", "King Boo", "Magikoopa", "Petey"),
         _signature("Wario Beasts", "DK", "Bowser", "Bowser Jr", "Bro"))),
    Character.from_raw("Waluigi"): CaptainTeams(
        TeamName.from_raw("Waluigi Mystiques"), TeamName.from_raw("Waluigi Smart Alecks"),
        (_signature("Waluigi Flankers", "King Boo", "Wario", "Magikoopa", "Dry Bones"),
         _signature("Waluigi Mashers", "Mario", "Luigi", "Toadsworth", "Wario"))),
    Character.from_raw("DK"): CaptainTeams(
        TeamName.from_raw("DK Explorers"), TeamName.from_raw("DK Wild Ones"),
        (_signature("DK Kongs", "Diddy", "Dixie", "Goomba", "Koopa"),
         _signature("DK Animals", "Yoshi", "Bowser", "Monty", "Petey"))),
    Character.from_raw("Diddy"): CaptainTeams(
        TeamName.from_raw("Diddy Survivors"), TeamName.from_raw("Diddy Ninjas"),
        (_signature("Diddy Tails", "Yoshi", "Birdo", "Dixie", "Boo"),
         _signature("Diddy Red Caps", "Mario", "Birdo", "Baby Mario", "Toadette"))),
    Character.from_raw("Bowser"): CaptainTeams(
        TeamName.from_raw("Bowser Flames"), TeamName.from_raw("Bowser Blue Shells"),
        # 'Bowser Monsters' is a 3-character signature: those three are all it needs.
        (_signature("Bowser Monsters", "Bowser Jr", "Dry Bones", "Bro"),
         _signature("Bowser Black Stars", "Waluigi", "Wario", "Petey", "Bro"))),
    Character.from_raw("Bowser Jr"): CaptainTeams(
        TeamName.from_raw("Jr Fangs"), TeamName.from_raw("Jr Bombers"),
        (_signature("Jr Pixies", "Diddy", "Boo", "Shy Guy", "Goomba"),
         _signature("Jr Rookies", "Diddy", "Dixie", "Baby Mario", "Baby Luigi"))),
}


def team_name(roster: list[str], captain: str) -> Optional[TeamName]:
    """Resolve the in-game team name for a roster led by ``captain``.

    Returns None for an incomplete roster or a non-captain. ``roster`` and
    ``captain`` accept any name/alias/id the Character resolver understands.
    """
    if '' in roster:
        return None

    cap = Character.from_raw(captain)
    if not cap.attributes.is_captain:
        return None
    teams = CAPTAIN_TEAMS[cap]

    chars = [Character.from_raw(name) for name in roster]
    roster_bases = {c.base for c in chars}

    # Signature rosters: a named team if all of its characters are present.
    for name, signature in teams.signatures:
        if signature <= roster_bases:
            return name

    # Otherwise: the captain's-class team if that class is the strict plurality.
    classes = [c.attributes.char_class for c in chars]
    captain_class = cap.attributes.char_class
    if all(classes.count(captain_class) > classes.count(other)
           for other in CLASSES if other != captain_class):
        return teams.class_team

    return teams.default

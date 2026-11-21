"""Resolve the in-game team name for a custom roster.

Each captain has four team logos (see ``Tables.TEAM_NAME``): two **signature**
rosters (named when every one of their characters is on the roster), one
**captain-class** team (chosen when the captain's character class is the roster's
strict plurality), and a **default**. ``CAPTAIN_TEAMS`` models those roles with
value objects: keyed by the captain :class:`Character`, each :class:`CaptainTeams`
record holds :class:`TeamName` logos and :class:`Signature` rosters.
"""
from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from typing import Optional

from .constants.character_data import CHARACTER_CLASS
from .rio_value import BaseCharacter, Character, Tables, TeamName

ROSTER_SIZE = 9

# Character classes, derived from the canonical attribute decode table.
CLASSES = tuple(CHARACTER_CLASS.values())

# All in-game team logos, from the canonical logo table.
IN_GAME_TEAM_NAMES = tuple(TeamName.from_raw(logo_id) for logo_id in Tables.TEAM_NAME)


@dataclass(frozen=True)
class Signature:
    """A signature roster: a team logo and the base characters that unlock it."""

    team: TeamName
    members: frozenset[BaseCharacter]


def _signature(name: str, *members: str) -> Signature:
    return Signature(TeamName.from_raw(name), frozenset(map(BaseCharacter.from_raw, members)))


@dataclass(frozen=True)
class CaptainTeams:
    """The four team logos a captain can field, by role."""

    default: TeamName
    class_team: TeamName                                          # captain's-class plurality
    signatures: tuple[Signature, ...]


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


def _is_blank(slot: object) -> bool:
    """A not-yet-filled roster/captain slot: '' or None."""
    return slot is None or (isinstance(slot, str) and slot == '')


def team_name(
    roster: Sequence[int | str | Character],
    captain: int | str | Character | None,
) -> Optional[TeamName]:
    """Resolve the in-game team name for a roster led by ``captain``.

    Slots accept any id, name, or alias the Character resolver understands, or
    a :class:`Character` itself. Returns None while the input is incomplete (a
    roster slot or the captain is ``''``/``None``) or when ``captain`` cannot
    lead a team. Raises ValueError for a roster that is not 9 slots, or for a
    filled slot that resolves to no character.
    """
    if len(roster) != ROSTER_SIZE:
        raise ValueError(f"roster must have {ROSTER_SIZE} slots, got {len(roster)}")
    if _is_blank(captain) or any(_is_blank(slot) for slot in roster):
        return None

    cap = Character.from_raw(captain)
    if not cap.attributes.is_captain:
        return None
    teams = CAPTAIN_TEAMS[cap]

    chars = [Character.from_raw(slot) for slot in roster]
    roster_bases = {c.base for c in chars}

    # Signature rosters: a named team if all of its characters are present.
    for signature in teams.signatures:
        if signature.members <= roster_bases:
            return signature.team

    # Otherwise: the captain's-class team if that class is the strict plurality.
    classes = [c.attributes.char_class for c in chars]
    captain_class = cap.attributes.char_class
    if all(classes.count(captain_class) > classes.count(other)
           for other in CLASSES if other != captain_class):
        return teams.class_team

    return teams.default

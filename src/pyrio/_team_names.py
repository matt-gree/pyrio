"""Team names: the game's logo names, and the rule that names a team from its roster.

Each captain has four logos: two **signature** teams, named when every family in
the signature is on the roster; a **class team**, named when the captain's class
is the roster's strict plurality; and a **default**. ``CAPTAIN_TEAMS`` holds that
data, and :func:`team_name` applies the rule.
"""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass
from types import MappingProxyType
from typing import TYPE_CHECKING, Final, Literal

from ._characters import Character, CharacterFamily
from ._enum import CodeEnum

if TYPE_CHECKING:
    from collections.abc import Mapping, Sequence

__all__ = ["CAPTAIN_TEAMS", "CaptainTeams", "SignatureTeam", "TeamName", "team_name"]


class TeamName(CodeEnum):
    """A team name, one per logo (``cLogoIdToTeamName``).

    Logos come in fours per captain: two signature teams, a class team and the
    captain's default team, in that order.
    """

    MARIO_SUNSHINES = 0, "Mario Sunshines"
    MARIO_ALL_STARS = 1, "Mario All Stars"
    MARIO_FIREBALLS = 2, "Mario Fireballs"
    MARIO_HEROES = 3, "Mario Heroes"
    LUIGI_MANSIONEERS = 4, "Luigi Mansioneers"
    LUIGI_LEAPERS = 5, "Luigi Leapers"
    LUIGI_VACUUMS = 6, "Luigi Vacuums"
    LUIGI_GENTLEMEN = 7, "Luigi Gentlemen"
    PEACH_MONARCHS = 8, "Peach Monarchs"
    PEACH_PRINCESSES = 9, "Peach Princesses"
    PEACH_DYNASTIES = 10, "Peach Dynasties"
    PEACH_ROSES = 11, "Peach Roses"
    DAISY_QUEEN_BEES = 12, "Daisy Queen Bees"
    DAISY_PETALS = 13, "Daisy Petals"
    DAISY_CUPIDS = 14, "Daisy Cupids"
    DAISY_LILLIES = 15, "Daisy Lillies"
    YOSHI_ISLANDERS = 16, "Yoshi Islanders"
    YOSHI_FLUTTERS = 17, "Yoshi Flutters"
    YOSHI_SPEED_STARS = 18, "Yoshi Speed Stars"
    YOSHI_EGGS = 19, "Yoshi Eggs"
    BIRDO_BOWS = 20, "Birdo Bows"
    BIRDO_FANS = 21, "Birdo Fans"
    BIRDO_MODELS = 22, "Birdo Models"
    BIRDO_BEAUTIES = 23, "Birdo Beauties"
    WARIO_GREATS = 24, "Wario Greats"
    WARIO_BEASTS = 25, "Wario Beasts"
    WARIO_STEAKHEADS = 26, "Wario Steakheads"
    WARIO_GARLICS = 27, "Wario Garlics"
    WALUIGI_FLANKERS = 28, "Waluigi Flankers"
    WALUIGI_MASHERS = 29, "Waluigi Mashers"
    WALUIGI_SMART_ALECKS = 30, "Waluigi Smart Alecks"
    WALUIGI_MYSTIQUES = 31, "Waluigi Mystiques"
    DK_KONGS = 32, "DK Kongs"
    DK_ANIMALS = 33, "DK Animals"
    DK_WILD_ONES = 34, "DK Wild Ones"
    DK_EXPLORERS = 35, "DK Explorers"
    DIDDY_TAILS = 36, "Diddy Tails"
    DIDDY_RED_CAPS = 37, "Diddy Red Caps"
    DIDDY_NINJAS = 38, "Diddy Ninjas"
    DIDDY_SURVIVORS = 39, "Diddy Survivors"
    BOWSER_MONSTERS = 40, "Bowser Monsters"
    BOWSER_BLACK_STARS = 41, "Bowser Black Stars"
    BOWSER_BLUE_SHELLS = 42, "Bowser Blue Shells"
    BOWSER_FLAMES = 43, "Bowser Flames"
    JR_PIXIES = 44, "Jr Pixies"
    JR_ROOKIES = 45, "Jr Rookies"
    JR_BOMBERS = 46, "Jr Bombers"
    JR_FANGS = 47, "Jr Fangs"

    @property
    def captain(self) -> Character:
        """The captain whose logo this is."""
        return _LOGO_CAPTAINS[self.id // 4]

    @property
    def role(self) -> Literal["signature", "class_team", "default"]:
        """This logo's role for its captain."""
        return _LOGO_ROLES[self.id % 4]


# The captains in logo order, which matches no other canonical ordering.
_LOGO_CAPTAINS = (
    Character.MARIO,
    Character.LUIGI,
    Character.PEACH,
    Character.DAISY,
    Character.YOSHI,
    Character.BIRDO,
    Character.WARIO,
    Character.WALUIGI,
    Character.DK,
    Character.DIDDY,
    Character.BOWSER,
    Character.BOWSER_JR,
)
_LOGO_ROLES: tuple[Literal["signature", "class_team", "default"], ...] = (
    "signature",
    "signature",
    "class_team",
    "default",
)


@dataclass(frozen=True, slots=True)
class SignatureTeam:
    """A signature team: the logo, and the families that name it when all are on the roster."""

    team: TeamName
    members: frozenset[CharacterFamily]


@dataclass(frozen=True, slots=True)
class CaptainTeams:
    """A captain's four logos, by role."""

    default: TeamName
    class_team: TeamName
    signatures: tuple[SignatureTeam, SignatureTeam]


def _signature(team: TeamName, *members: CharacterFamily) -> SignatureTeam:
    return SignatureTeam(team, frozenset(members))


_F = CharacterFamily
_T = TeamName

CAPTAIN_TEAMS: Final[Mapping[Character, CaptainTeams]] = MappingProxyType(
    {
        Character.MARIO: CaptainTeams(
            _T.MARIO_HEROES,
            _T.MARIO_FIREBALLS,
            (
                _signature(_T.MARIO_SUNSHINES, _F.LUIGI, _F.MONTY, _F.PIANTA, _F.NOKI),
                _signature(_T.MARIO_ALL_STARS, _F.PEACH, _F.YOSHI, _F.DK, _F.BOWSER),
            ),
        ),
        Character.LUIGI: CaptainTeams(
            _T.LUIGI_GENTLEMEN,
            _T.LUIGI_VACUUMS,
            (
                _signature(_T.LUIGI_MANSIONEERS, _F.BOWSER, _F.TOAD, _F.BOO, _F.KING_BOO),
                _signature(_T.LUIGI_LEAPERS, _F.WALUIGI, _F.DIDDY, _F.DAISY, _F.BABY_LUIGI),
            ),
        ),
        Character.PEACH: CaptainTeams(
            _T.PEACH_ROSES,
            _T.PEACH_DYNASTIES,
            (
                _signature(_T.PEACH_MONARCHS, _F.DAISY, _F.TOAD, _F.TOADSWORTH, _F.TOADETTE),
                _signature(_T.PEACH_PRINCESSES, _F.MARIO, _F.BOWSER, _F.BABY_MARIO, _F.BOWSER_JR),
            ),
        ),
        Character.DAISY: CaptainTeams(
            _T.DAISY_LILLIES,
            _T.DAISY_CUPIDS,
            (
                _signature(_T.DAISY_QUEEN_BEES, _F.PEACH, _F.DIXIE, _F.TOADETTE, _F.NOKI),
                _signature(_T.DAISY_PETALS, _F.BIRDO, _F.DIXIE, _F.WARIO, _F.PETEY),
            ),
        ),
        Character.YOSHI: CaptainTeams(
            _T.YOSHI_EGGS,
            _T.YOSHI_SPEED_STARS,
            (
                _signature(_T.YOSHI_ISLANDERS, _F.BIRDO, _F.BABY_MARIO, _F.BABY_LUIGI, _F.SHY_GUY),
                _signature(_T.YOSHI_FLUTTERS, _F.BOO, _F.KING_BOO, _F.PARATROOPA, _F.PARAGOOMBA),
            ),
        ),
        Character.BIRDO: CaptainTeams(
            _T.BIRDO_BEAUTIES,
            _T.BIRDO_MODELS,
            (
                _signature(_T.BIRDO_BOWS, _F.MARIO, _F.LUIGI, _F.PEACH, _F.TOAD),
                _signature(_T.BIRDO_FANS, _F.YOSHI, _F.SHY_GUY, _F.GOOMBA, _F.KOOPA),
            ),
        ),
        Character.WARIO: CaptainTeams(
            _T.WARIO_GARLICS,
            _T.WARIO_STEAKHEADS,
            (
                _signature(_T.WARIO_GREATS, _F.WALUIGI, _F.KING_BOO, _F.MAGIKOOPA, _F.PETEY),
                _signature(_T.WARIO_BEASTS, _F.DK, _F.BOWSER, _F.BOWSER_JR, _F.BRO),
            ),
        ),
        Character.WALUIGI: CaptainTeams(
            _T.WALUIGI_MYSTIQUES,
            _T.WALUIGI_SMART_ALECKS,
            (
                _signature(_T.WALUIGI_FLANKERS, _F.KING_BOO, _F.WARIO, _F.MAGIKOOPA, _F.DRY_BONES),
                _signature(_T.WALUIGI_MASHERS, _F.MARIO, _F.LUIGI, _F.TOADSWORTH, _F.WARIO),
            ),
        ),
        Character.DK: CaptainTeams(
            _T.DK_EXPLORERS,
            _T.DK_WILD_ONES,
            (
                _signature(_T.DK_KONGS, _F.DIDDY, _F.DIXIE, _F.GOOMBA, _F.KOOPA),
                _signature(_T.DK_ANIMALS, _F.YOSHI, _F.BOWSER, _F.MONTY, _F.PETEY),
            ),
        ),
        Character.DIDDY: CaptainTeams(
            _T.DIDDY_SURVIVORS,
            _T.DIDDY_NINJAS,
            (
                _signature(_T.DIDDY_TAILS, _F.YOSHI, _F.BIRDO, _F.DIXIE, _F.BOO),
                _signature(_T.DIDDY_RED_CAPS, _F.MARIO, _F.BIRDO, _F.BABY_MARIO, _F.TOADETTE),
            ),
        ),
        Character.BOWSER: CaptainTeams(
            _T.BOWSER_FLAMES,
            _T.BOWSER_BLUE_SHELLS,
            (
                # Three families, not four: these three are all it needs.
                _signature(_T.BOWSER_MONSTERS, _F.BOWSER_JR, _F.DRY_BONES, _F.BRO),
                _signature(_T.BOWSER_BLACK_STARS, _F.WALUIGI, _F.WARIO, _F.PETEY, _F.BRO),
            ),
        ),
        Character.BOWSER_JR: CaptainTeams(
            _T.JR_FANGS,
            _T.JR_BOMBERS,
            (
                _signature(_T.JR_PIXIES, _F.DIDDY, _F.BOO, _F.SHY_GUY, _F.GOOMBA),
                _signature(_T.JR_ROOKIES, _F.DIDDY, _F.DIXIE, _F.BABY_MARIO, _F.BABY_LUIGI),
            ),
        ),
    }
)
"""Each captain's logos and signature teams: the data :func:`team_name` reads."""

_ROSTER_SIZE = 9


def team_name(roster: Sequence[Character | None], captain: Character | None) -> TeamName | None:
    """The team name the game gives ``roster`` when ``captain`` leads it.

    A signature team wins if all its families are on the roster (any variant
    counts). Otherwise it is the class team if the captain's class is the
    roster's strict plurality, and the default if not.

    ``None`` in a slot or as the captain means not chosen yet, and the answer is
    ``None`` until the team is complete. It is also ``None`` for a captain who
    can't lead a team. A roster that isn't nine slots raises ``ValueError``.
    """
    if len(roster) != _ROSTER_SIZE:
        raise ValueError(f"a roster has {_ROSTER_SIZE} slots, got {len(roster)}")
    if captain is None or any(slot is None for slot in roster):
        return None
    if not captain.is_captain:
        return None
    teams = CAPTAIN_TEAMS[captain]
    characters = [slot for slot in roster if slot is not None]

    families = {character.family for character in characters}
    for signature in teams.signatures:
        if signature.members <= families:
            return signature.team

    classes = Counter(character.attributes.character_class for character in characters)
    captain_class = captain.attributes.character_class
    if all(classes[captain_class] > n for c, n in classes.items() if c is not captain_class):
        return teams.class_team
    return teams.default

"""Team names: the game's logo names, and (from step 4) naming a team from its roster."""

from __future__ import annotations

from typing import Literal

from ._characters import Character
from ._enum import CodeEnum

__all__ = ["TeamName"]


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

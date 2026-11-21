"""Characters, character families and per-character attributes."""

from __future__ import annotations

import csv
import io
from dataclasses import dataclass, replace
from enum import Enum
from functools import cache
from importlib.resources import files
from typing import Self, cast

from ._codes import Hand
from ._enum import CodeEnum
from ._errors import UnknownCodeError
from ._names import NameIndex, nicknames

__all__ = [
    "Ability",
    "CaptainStar",
    "Character",
    "CharacterAttributes",
    "CharacterClass",
    "CharacterFamily",
    "HorizontalHitTrajectory",
    "StarPitch",
    "StarSwing",
    "VerticalHitTrajectory",
]


class Character(CodeEnum):
    """A playable character (``cCharIdToCharName``).

    ``Character(29)`` and ``Character("Toad(B)")`` are strict, for machine input.
    ``Character.parse("teardrop")`` is lenient, for people.
    """

    MARIO = 0, "Mario"
    LUIGI = 1, "Luigi"
    DK = 2, "DK"
    DIDDY = 3, "Diddy"
    PEACH = 4, "Peach"
    DAISY = 5, "Daisy"
    YOSHI = 6, "Yoshi"
    BABY_MARIO = 7, "Baby Mario"
    BABY_LUIGI = 8, "Baby Luigi"
    BOWSER = 9, "Bowser"
    WARIO = 10, "Wario"
    WALUIGI = 11, "Waluigi"
    KOOPA_G = 12, "Koopa(G)"
    TOAD_R = 13, "Toad(R)"
    BOO = 14, "Boo"
    TOADETTE = 15, "Toadette"
    SHY_GUY_R = 16, "Shy Guy(R)"
    BIRDO = 17, "Birdo"
    MONTY = 18, "Monty"
    BOWSER_JR = 19, "Bowser Jr"
    PARATROOPA_R = 20, "Paratroopa(R)"
    PIANTA_B = 21, "Pianta(B)"
    PIANTA_R = 22, "Pianta(R)"
    PIANTA_Y = 23, "Pianta(Y)"
    NOKI_B = 24, "Noki(B)"
    NOKI_R = 25, "Noki(R)"
    NOKI_G = 26, "Noki(G)"
    BRO_H = 27, "Bro(H)"
    TOADSWORTH = 28, "Toadsworth"
    TOAD_B = 29, "Toad(B)"
    TOAD_Y = 30, "Toad(Y)"
    TOAD_G = 31, "Toad(G)"
    TOAD_P = 32, "Toad(P)"
    MAGIKOOPA_B = 33, "Magikoopa(B)"
    MAGIKOOPA_R = 34, "Magikoopa(R)"
    MAGIKOOPA_G = 35, "Magikoopa(G)"
    MAGIKOOPA_Y = 36, "Magikoopa(Y)"
    KING_BOO = 37, "King Boo"
    PETEY = 38, "Petey"
    DIXIE = 39, "Dixie"
    GOOMBA = 40, "Goomba"
    PARAGOOMBA = 41, "Paragoomba"
    KOOPA_R = 42, "Koopa(R)"
    PARATROOPA_G = 43, "Paratroopa(G)"
    SHY_GUY_B = 44, "Shy Guy(B)"
    SHY_GUY_Y = 45, "Shy Guy(Y)"
    SHY_GUY_G = 46, "Shy Guy(G)"
    SHY_GUY_BK = 47, "Shy Guy(Bk)"
    DRY_BONES_GY = 48, "Dry Bones(Gy)"
    DRY_BONES_G = 49, "Dry Bones(G)"
    DRY_BONES_R = 50, "Dry Bones(R)"
    DRY_BONES_B = 51, "Dry Bones(B)"
    BRO_F = 52, "Bro(F)"
    BRO_B = 53, "Bro(B)"

    @property
    def family(self) -> CharacterFamily:
        """The family this character is a variant of: ``Character.TOAD_B.family``."""
        return CharacterFamily(self.label.partition("(")[0])

    @property
    def attributes(self) -> CharacterAttributes:
        """This character's attributes with superstar off; ``.with_superstar()`` for on."""
        return _attributes()[self]

    @property
    def is_captain(self) -> bool:
        """Whether this character can captain a team."""
        return self.attributes.is_captain

    @classmethod
    def parse(cls, text: str) -> Character:
        """The character a person means.

        Accepts labels and nicknames with any spacing, punctuation or case
        (``"Bowser Jr."``, ``"bj"``, ``"teardrop"``), variant forms built from
        the family name (``"toad blue"``, ``"r!toad"``), and a bare family name,
        which means that family's default variant (``"koopa"`` is
        ``KOOPA_R``). Raises :class:`~pyrio.UnknownNameError` with suggestions
        on a miss.
        """
        return _character_names().resolve(text)


class CharacterFamily(Enum):
    """A character with its variants together: the five Toads are one family.

    Rio gives families no id, so the value is the label. Families sort in the
    order of their first variant's id. A family exposes only what all its
    variants share; reach per-variant numbers through a variant.
    """

    MARIO = "Mario"
    LUIGI = "Luigi"
    DK = "DK"
    DIDDY = "Diddy"
    PEACH = "Peach"
    DAISY = "Daisy"
    YOSHI = "Yoshi"
    BABY_MARIO = "Baby Mario"
    BABY_LUIGI = "Baby Luigi"
    BOWSER = "Bowser"
    WARIO = "Wario"
    WALUIGI = "Waluigi"
    KOOPA = "Koopa"
    TOAD = "Toad"
    BOO = "Boo"
    TOADETTE = "Toadette"
    SHY_GUY = "Shy Guy"
    BIRDO = "Birdo"
    MONTY = "Monty"
    BOWSER_JR = "Bowser Jr"
    PARATROOPA = "Paratroopa"
    PIANTA = "Pianta"
    NOKI = "Noki"
    BRO = "Bro"
    TOADSWORTH = "Toadsworth"
    MAGIKOOPA = "Magikoopa"
    KING_BOO = "King Boo"
    PETEY = "Petey"
    DIXIE = "Dixie"
    GOOMBA = "Goomba"
    PARAGOOMBA = "Paragoomba"
    DRY_BONES = "Dry Bones"

    value: str  # pyright: ignore[reportIncompatibleMethodOverride]

    @property
    def label(self) -> str:
        """The family's name, such as ``"Shy Guy"``."""
        return self.value

    @property
    def variants(self) -> tuple[Character, ...]:
        """The family's characters in id order: ``(Character.MARIO,)`` for Mario."""
        return _variants()[self]

    @property
    def has_variants(self) -> bool:
        """Whether the family has more than one character."""
        return len(self.variants) > 1

    @property
    def default(self) -> Character:
        """The variant a bare family name means, such as ``Character.KOOPA_R`` for Koopa."""
        if not self.has_variants:
            return self.variants[0]
        return Character(nicknames()["families"][self.label]["default"])

    @property
    def char_class(self) -> CharacterClass:
        """The class every variant shares."""
        return self.variants[0].attributes.char_class

    @property
    def is_captain(self) -> bool:
        """Whether the family's characters can captain a team."""
        return self.variants[0].is_captain

    @property
    def abilities(self) -> frozenset[Ability]:
        """The fielding abilities every variant shares."""
        return self.variants[0].attributes.abilities

    @classmethod
    def parse(cls, text: str) -> CharacterFamily:
        """The family a person means: ``CharacterFamily.parse("bones")``.

        Accepts everything :meth:`Character.parse` does and returns that
        character's family.
        """
        return Character.parse(text).family

    def __str__(self) -> str:
        return self.value

    def __lt__(self, other: object) -> bool:
        if not isinstance(other, CharacterFamily):
            return NotImplemented
        return _order()[self] < _order()[other]

    def __le__(self, other: object) -> bool:
        if not isinstance(other, CharacterFamily):
            return NotImplemented
        return _order()[self] <= _order()[other]

    def __gt__(self, other: object) -> bool:
        if not isinstance(other, CharacterFamily):
            return NotImplemented
        return _order()[self] > _order()[other]

    def __ge__(self, other: object) -> bool:
        if not isinstance(other, CharacterFamily):
            return NotImplemented
        return _order()[self] >= _order()[other]

    @classmethod
    def _missing_(cls, value: object) -> Self:
        if isinstance(value, str):
            for member in cls:
                if member.value.casefold() == value.casefold():
                    return member
        raise UnknownCodeError(cls, value)


@cache
def _order() -> dict[CharacterFamily, int]:
    return {family: index for index, family in enumerate(CharacterFamily)}


@cache
def _variants() -> dict[CharacterFamily, tuple[Character, ...]]:
    groups: dict[CharacterFamily, list[Character]] = {family: [] for family in CharacterFamily}
    for character in Character:
        groups[character.family].append(character)
    return {family: tuple(members) for family, members in groups.items()}


@cache
def _character_names() -> NameIndex[Character]:
    index = NameIndex[Character](Character)
    for character in Character:
        index.add(character.label, character)
    for name, character in _variant_forms().items():
        index.add(name, character)
    for family in CharacterFamily:
        for stem in _stems(family):
            index.add(stem, family.default)
    for label, names in nicknames()["characters"].items():
        character = Character(label)
        for name in names:
            index.add(name, character)
    return index


def _stems(family: CharacterFamily) -> tuple[str, ...]:
    """The family's name and its nicknames, which variant forms are built on."""
    entry = nicknames()["families"].get(family.label, {})
    return (family.label, *entry.get("nicknames", ()))


def _variant_forms() -> dict[str, Character]:
    """Names generated for each variant, such as ``redtoad``, ``toadred``, ``rtoad`` and ``toadr``.

    A variant's suffix (the ``R`` in ``Toad(R)``) and its words (``red``) go
    before or after each of the family's stems. The words come from
    ``[variant_words]`` in ``nicknames.toml``, unless the family names its own.
    """
    data = nicknames()
    forms: dict[str, Character] = {}
    for family in CharacterFamily:
        if not family.has_variants:
            continue
        words = data["families"][family.label].get("variant_words", data["variant_words"])
        for character in family.variants:
            suffix = character.label.partition("(")[2].rstrip(")")
            for prefix in (suffix, *words[suffix]):
                for stem in _stems(family):
                    forms[prefix + stem] = character
                    forms[stem + prefix] = character
    return forms


# --- attributes -------------------------------------------------------------


class CharacterClass(CodeEnum):
    """A character's class, from the attribute sheet's ``Character Class``."""

    BALANCE = 0, "Balance"
    POWER = 1, "Power"
    SPEED = 2, "Speed"
    TECHNIQUE = 3, "Technique"


class HorizontalHitTrajectory(CodeEnum):
    """Which way a character's hits tend to go."""

    MID = 0, "Mid"
    PULL = 1, "Pull"
    PUSH = 2, "Push"


class VerticalHitTrajectory(CodeEnum):
    """How high a character's hits tend to go."""

    MID = 0, "Mid"
    HIGH = 1, "High"
    LOW = 2, "Low"


class CaptainStar(CodeEnum):
    """A captain's star ball, which is both their star pitch and their star swing.

    The ids index the captain-star tables in the hit simulation.
    """

    FIREBALL = 1, "Fireball"
    GREEN_FIREBALL = 2, "Green Fireball"
    PHONY_BALL = 3, "Phony Ball"
    LIAR_BALL = 4, "Liar Ball"
    BANANA_BALL = 5, "Banana Ball"
    BOOMERANG_BALL = 6, "Boomerang Ball"
    KILLER_BALL = 7, "Killer Ball"
    KILLER_JR_BALL = 8, "Killer Jr. Ball"
    EGG_BALL = 9, "Egg Ball"
    WEIRD_BALL = 10, "Weird Ball"
    HEART_BALL = 11, "Heart Ball"
    FLOWER_BALL = 12, "Flower Ball"


class StarPitch(CodeEnum):
    """The star pitch a character throws when not captain."""

    CURVE = 1, "Curve", "Breaking Ball"
    FASTBALL = 2, "Fastball"
    CHANGE_UP = 3, "Change-Up"


class StarSwing(CodeEnum):
    """The star swing a character hits when not captain."""

    POP_FLY = 1, "Pop Fly"
    GROUNDER = 2, "Grounder"
    LINE_DRIVE = 3, "Line Drive"


class Ability(Enum):
    """A fielding ability."""

    BALL_DASH = "Ball Dash"
    BODY_CHECK = "Body Check"
    CLAMBER = "Clamber"
    LASER_BEAM = "Laser Beam"
    MAGICAL_CATCH = "Magical Catch"
    QUICK_THROW = "Quick Throw"
    SLIDING_CATCH = "Sliding Catch"
    SUCTION = "Suction"
    SUPER_CATCH = "Super Catch"
    SUPER_JUMP = "Super Jump"
    TONGUE_CATCH = "Tongue Catch"
    WALL_JUMP = "Wall Jump"

    value: str  # pyright: ignore[reportIncompatibleMethodOverride]

    @property
    def label(self) -> str:
        """The ability's name, such as ``"Wall Jump"``."""
        return self.value

    def __str__(self) -> str:
        return self.value


@dataclass(frozen=True, slots=True)
class CharacterAttributes:
    """One character's attributes, from the game's attribute sheet.

    ``Character.attributes`` gives the record with superstar off, and
    :meth:`with_superstar` the record with it on.
    """

    char_class: CharacterClass
    is_captain: bool
    abilities: frozenset[Ability]
    # pitching
    weight: int
    curve_ball_speed: int
    fast_ball_speed: int
    curve: int
    cursed_ball: int
    curve_control: int
    pitching_height: float
    has_super_curve: bool
    # fielding
    fielding_arm: Hand
    throwing_power: int
    speed: int
    # batting
    batting_stance: Hand
    slap_hit_power: int
    charge_hit_power: int
    bunting: int
    horizontal_hit_trajectory: HorizontalHitTrajectory
    vertical_hit_trajectory: VerticalHitTrajectory
    slap_contact_size_multiplier: int
    charge_contact_size_multiplier: int
    horizontal_range_near: float
    horizontal_range_far: float
    has_trimmed_bat: bool
    has_wall_splat: bool
    # star moves
    captain_star: CaptainStar | None
    star_pitch: StarPitch
    star_swing: StarSwing
    # where the character sits on the character select screen, from 1
    select_screen_order: int
    is_superstar: bool = False

    def with_superstar(self) -> CharacterAttributes:
        """The record with superstar on: each boosted stat goes up, to its ceiling if it has one."""
        if self.is_superstar:
            return self
        boosted = {
            name: _boost(cast(int, getattr(self, name)), increase, ceiling)
            for name, (increase, ceiling) in _SUPERSTAR_BOOSTS.items()
        }
        return replace(self, is_superstar=True, **boosted)


_SUPERSTAR_BOOSTS: dict[str, tuple[int, int | None]] = {
    "curve_ball_speed": (20, None),
    "fast_ball_speed": (20, None),
    "curve": (50, 100),
    "cursed_ball": (50, 100),
    "curve_control": (50, None),
    "throwing_power": (50, 100),
    "speed": (50, None),
    "slap_hit_power": (50, 100),
    "charge_hit_power": (50, 100),
    "bunting": (50, 100),
    "slap_contact_size_multiplier": (50, 100),
    "charge_contact_size_multiplier": (50, 100),
}
# What superstar adds to each boosted stat, and the ceiling it can't pass (None: none).


def _boost(value: int, increase: int, ceiling: int | None) -> int:
    return value + increase if ceiling is None else min(value + increase, ceiling)


@cache
def _attributes() -> dict[Character, CharacterAttributes]:
    text = files("pyrio").joinpath("_data/character_attributes.csv").read_text(encoding="utf-8")
    return {
        Character(int(row["CharId"])): _from_row(row) for row in csv.DictReader(io.StringIO(text))
    }


def _from_row(row: dict[str, str]) -> CharacterAttributes:
    def number(column: str) -> int:
        return int(float(row[column]))  # some integer columns are written "1.0"

    def flag(column: str) -> bool:
        return number(column) == 1

    if row["Captain Star Pitch"] != row["Captain Star Hit"]:
        raise ValueError(f"{row['Character']}: captain star pitch and swing differ")
    captain_star = number("Captain Star Pitch")
    return CharacterAttributes(
        char_class=CharacterClass(number("Character Class")),
        is_captain=flag("Captain Character"),
        abilities=frozenset(ability for ability in Ability if flag(ability.value)),
        weight=number("Weight"),
        curve_ball_speed=number("Curve Ball Speed"),
        fast_ball_speed=number("Fast Ball Speed"),
        curve=number("Curve"),
        cursed_ball=number("Cursed Ball"),
        curve_control=number("Curve Control"),
        pitching_height=float(row["Pitching Height"]),
        has_super_curve=flag("Super Curve"),
        fielding_arm=Hand(number("Fielding Arm")),
        throwing_power=number("Throwing Power"),
        speed=number("Speed"),
        batting_stance=Hand(number("Batting Stance")),
        slap_hit_power=number("Slap Hit Power"),
        charge_hit_power=number("Charge Hit Power"),
        bunting=number("Bunting"),
        horizontal_hit_trajectory=HorizontalHitTrajectory(number("Horizontal Hit Trajectory")),
        vertical_hit_trajectory=VerticalHitTrajectory(number("Vertical Hit Trajectory")),
        slap_contact_size_multiplier=number("Slap Contact Size Multiplier"),
        charge_contact_size_multiplier=number("Charge Contact Size Multiplier"),
        horizontal_range_near=float(row["Horizontal Range Near"]),
        horizontal_range_far=float(row["Horizontal Range Far"]),
        has_trimmed_bat=flag("Trimmed Bat"),
        has_wall_splat=flag("Wall Splat"),
        captain_star=CaptainStar(captain_star) if captain_star else None,
        star_pitch=StarPitch(number("Non-Captain Star Pitch")),
        star_swing=StarSwing(number("Non-Captain Star Hit")),
        select_screen_order=number("CSS Sort"),
    )

"""Project Rio coded values: ID/name tables and the typed value objects on them.

Typed resolution (preferred):

    Character.from_raw(0)        -> Character(0, "Mario")
    Stadium.from_raw("1")        -> Stadium(1, "Bowser Castle")

Raw bidirectional translation:

    lookup("char_name", 0)       -> "Mario"
    lookup("char_name", "Mario") -> 0
    lookup(Tables.CHAR_NAME, 0)  -> "Mario"   # also works
    list_dicts()                 # prints all available table names

pandas is an optional, lazily-imported dependency: only the Series/DataFrame
helpers (lookup on a Series/DataFrame, create_translated_columns) use it, so
importing this module does not require pandas.
"""
from __future__ import annotations

import csv
import os
import sys
from dataclasses import dataclass
from typing import ClassVar, TYPE_CHECKING, TypeVar, overload

from .exceptions import UnknownRioValueError

if TYPE_CHECKING:
    from .constants.character_data import CharacterAttributes


class Tables:
    CHAR_NAME = {
        0: "Mario",
        1: "Luigi",
        2: "DK",
        3: "Diddy",
        4: "Peach",
        5: "Daisy",
        6: "Yoshi",
        7: "Baby Mario",
        8: "Baby Luigi",
        9: "Bowser",
        10: "Wario",
        11: "Waluigi",
        12: "Koopa(G)",
        13: "Toad(R)",
        14: "Boo",
        15: "Toadette",
        16: "Shy Guy(R)",
        17: "Birdo",
        18: "Monty",
        19: "Bowser Jr",
        20: "Paratroopa(R)",
        21: "Pianta(B)",
        22: "Pianta(R)",
        23: "Pianta(Y)",
        24: "Noki(B)",
        25: "Noki(R)",
        26: "Noki(G)",
        27: "Bro(H)",
        28: "Toadsworth",
        29: "Toad(B)",
        30: "Toad(Y)",
        31: "Toad(G)",
        32: "Toad(P)",
        33: "Magikoopa(B)",
        34: "Magikoopa(R)",
        35: "Magikoopa(G)",
        36: "Magikoopa(Y)",
        37: "King Boo",
        38: "Petey",
        39: "Dixie",
        40: "Goomba",
        41: "Paragoomba",
        42: "Koopa(R)",
        43: "Paratroopa(G)",
        44: "Shy Guy(B)",
        45: "Shy Guy(Y)",
        46: "Shy Guy(G)",
        47: "Shy Guy(Bk)",
        48: "Dry Bones(Gy)",
        49: "Dry Bones(G)",
        50: "Dry Bones(R)",
        51: "Dry Bones(B)",
        52: "Bro(F)",
        53: "Bro(B)",
    }

    STADIUM = {
        0: "Mario Stadium",
        1: "Bowser Castle",
        2: "Wario Palace",
        3: "Yoshi Park",
        4: "Peach Garden",
        5: "DK Jungle",
        6: "Toy Field"
    }

    CONTACT_TYPE = {
        255: "Miss",
        0: "Sour - Left",
        1: "Nice - Left",
        2: "Perfect",
        3: "Nice - Right",
        4: "Sour - Right"
    }

    HAND = {
        0: "Right",
        1: "Left"
    }

    HAND_BOOL = {
        True: "Left",
        False: "Right"
    }

    INPUT_DIRECTION = {
        0: "",
        1: "Left",
        2: "Right",
        3: "Left+Right",
        4: "Down",
        5: "Left+Down",
        6: "Right+Down",
        7: "Left+Right+Down",
        8: "Up",
        9: "Left+Up",
        10: "Right+Up",
        11: "Left+Right+Up",
        12: "Down+Up",
        13: "Left+Down+Up",
        14: "Right+Down+Up",
        15: "Left+Right+Down+Up"
    }

    PITCH_TYPE = {
        0: "Curve",
        1: "Charge",
        2: "ChangeUp"
    }

    CHARGE_TYPE = {
        0: "N/A",
        2: "Slider",
        3: "Perfect"
    }

    TYPE_OF_SWING = {
        0: "None",
        1: "Slap",
        2: "Charge",
        3: "Star",
        4: "Bunt"
    }

    POSITION = {
        0: "P",
        1: "C",
        2: "1B",
        3: "2B",
        4: "3B",
        5: "SS",
        6: "LF",
        7: "CF",
        8: "RF",
        255: "Inv",
        None: "None"
    }

    FIELDER_ACTIONS = {
        0: "None",
        2: "Sliding",
        3: "Walljump",
    }

    FIELDER_BOBBLES = {
        0: "None",
        1: "Slide/stun lock",
        2: "Fumble",
        3: "Bobble",
        4: "Fireball",
        16: "Garlic knockout",
        255: "None"
    }

    STEAL_TYPE = {
        0: "None",
        1: "Ready",
        2: "Normal",
        3: "Perfect",
        255: "None"
    }

    OUT_TYPE = {
        0: "None",
        1: "Caught",
        2: "Force",
        3: "Tag",
        4: "Force Back",
        16: "Strike-out",
    }

    PITCH_RESULT = {
        0: "HBP",
        1: "BB",
        2: "Ball",
        3: "Strike-looking",
        4: "Strike-swing",
        5: "Strike-bunting",
        6: "Contact",
        7: "Unknown"
    }

    PRIMARY_CONTACT_RESULT = {
        0: "Out",
        1: "Foul",
        2: "Fair",
        3: "Fielded",
        4: "Unknown"
    }

    SECONDARY_CONTACT_RESULT = {
        0: "Out-caught",
        1: "Out-force",
        2: "Out-tag",
        3: "Foul",
        4: "Batter safe, runner out",
        7: "Single",
        8: "Double",
        9: "Triple",
        10: "HR",
        11: "Error - Input",
        12: "Error - Chem",
        13: "Bunt",
        14: "SacFly",
        15: "Ground ball double Play",
        16: "Foul catch",
    }

    FINAL_RESULT = {
        0: "None",
        1: "Strikeout",
        2: "Walk (BB)",
        3: "Walk (HBP)",
        4: "Out",
        5: "Caught",
        6: "Caught line-drive",
        7: "Single",
        8: "Double",
        9: "Triple",
        10: "HR",
        11: "Error - Input",
        12: "Error - Chem",
        13: "Bunt",
        14: "SacFly",
        15: "Ground ball double Play",
        16: "Foul catch"
    }

    MANUAL_SELECT = {
        0: "No Selected Char",
        1: "Pitcher",
        2: "Catcher",
        3: "Closest to Ball",
        4: "Closest to Drop",
    }

    DEAD_BALL_REASON = {
        0: "N/A",
        1: "Home Run",
        2: "Foul Ball",
        3: "Ground Rule Double",
        4: "Ball Dead",
    }

    SIMPLIFIED_NAME = {
        'Mario': 'Mario',
        'Luigi': 'Luigi',
        'DK': 'DK',
        'Diddy': 'Diddy',
        'Peach': 'Peach',
        'Daisy': 'Daisy',
        'Yoshi': 'Yoshi',
        'Baby Mario': 'Baby Mario',
        'Baby Luigi': 'Baby Luigi',
        'Bowser': 'Bowser',
        'Wario': 'Wario',
        'Waluigi': 'Waluigi',
        'Koopa(G)': 'Koopa',
        'Toad(R)': 'Toad',
        'Boo': 'Boo',
        'Toadette': 'Toadette',
        'Shy Guy(R)': 'Shy Guy',
        'Birdo': 'Birdo',
        'Monty': 'Monty',
        'Bowser Jr': 'Bowser Jr',
        'Paratroopa(R)': 'Paratroopa',
        'Pianta(B)': 'Pianta',
        'Pianta(R)': 'Pianta',
        'Pianta(Y)': 'Pianta',
        'Noki(B)': 'Noki',
        'Noki(R)': 'Noki',
        'Noki(G)': 'Noki',
        'Bro(H)': 'Bro',
        'Toadsworth': 'Toadsworth',
        'Toad(B)': 'Toad',
        'Toad(Y)': 'Toad',
        'Toad(G)': 'Toad',
        'Toad(P)': 'Toad',
        'Magikoopa(B)': 'Magikoopa',
        'Magikoopa(R)': 'Magikoopa',
        'Magikoopa(G)': 'Magikoopa',
        'Magikoopa(Y)': 'Magikoopa',
        'King Boo': 'King Boo',
        'Petey': 'Petey',
        'Dixie': 'Dixie',
        'Goomba': 'Goomba',
        'Paragoomba': 'Paragoomba',
        'Koopa(R)': 'Koopa',
        'Paratroopa(G)': 'Paratroopa',
        'Shy Guy(B)': 'Shy Guy',
        'Shy Guy(Y)': 'Shy Guy',
        'Shy Guy(G)': 'Shy Guy',
        'Shy Guy(Bk)': 'Shy Guy',
        'Dry Bones(Gy)': 'Dry Bones',
        'Dry Bones(G)': 'Dry Bones',
        'Dry Bones(R)': 'Dry Bones',
        'Dry Bones(B)': 'Dry Bones',
        'Bro(F)': 'Bro',
        'Bro(B)': 'Bro',
    }

    # Logo id -> team name (canonical cLogoIdToTeamName).
    TEAM_NAME = {
        0: "Mario Sunshines",
        1: "Mario All Stars",
        2: "Mario Fireballs",
        3: "Mario Heroes",
        4: "Luigi Mansioneers",
        5: "Luigi Leapers",
        6: "Luigi Vacuums",
        7: "Luigi Gentlemen",
        8: "Peach Monarchs",
        9: "Peach Princesses",
        10: "Peach Dynasties",
        11: "Peach Roses",
        12: "Daisy Queen Bees",
        13: "Daisy Petals",
        14: "Daisy Cupids",
        15: "Daisy Lillies",
        16: "Yoshi Islanders",
        17: "Yoshi Flutters",
        18: "Yoshi Speed Stars",
        19: "Yoshi Eggs",
        20: "Birdo Bows",
        21: "Birdo Fans",
        22: "Birdo Models",
        23: "Birdo Beauties",
        24: "Wario Greats",
        25: "Wario Beasts",
        26: "Wario Steakheads",
        27: "Wario Garlics",
        28: "Waluigi Flankers",
        29: "Waluigi Mashers",
        30: "Waluigi Smart Alecks",
        31: "Waluigi Mystiques",
        32: "DK Kongs",
        33: "DK Animals",
        34: "DK Wild Ones",
        35: "DK Explorers",
        36: "Diddy Tails",
        37: "Diddy Red Caps",
        38: "Diddy Ninjas",
        39: "Diddy Survivors",
        40: "Bowser Monsters",
        41: "Bowser Black Stars",
        42: "Bowser Blue Shells",
        43: "Bowser Flames",
        44: "Jr Pixies",
        45: "Jr Rookies",
        46: "Jr Bombers",
        47: "Jr Fangs",
    }


# -------------------------------------------------------------------------
# String-name registry: maps friendly names -> Tables attributes
# -------------------------------------------------------------------------

_DICT_REGISTRY: dict[str, dict] = {}


def _build_registry():
    """Build the string-name -> dict mapping from Tables attributes."""
    for attr_name in dir(Tables):
        if attr_name.startswith('_'):
            continue
        val = getattr(Tables, attr_name)
        if isinstance(val, dict):
            _DICT_REGISTRY[attr_name.lower()] = val


_build_registry()


def _resolve_dict(dictionary) -> dict:
    """Accept a dict directly or a string name like 'char_name'."""
    if isinstance(dictionary, dict):
        return dictionary
    if isinstance(dictionary, str):
        key = dictionary.lower()
        if key in _DICT_REGISTRY:
            return _DICT_REGISTRY[key]
        raise UnknownRioValueError(
            f"Unknown dictionary name: '{dictionary}'. "
            f"Use list_dicts() to see available names."
        )
    raise TypeError(f"Expected a dict or string name, got {type(dictionary).__name__}")


def list_dicts():
    """Print all available lookup dictionary names and a sample of their contents."""
    for name, d in sorted(_DICT_REGISTRY.items()):
        items = list(d.items())
        sample = items[:3]
        sample_str = ", ".join(f"{k} -> {v}" for k, v in sample)
        if len(items) > 3:
            sample_str += f", ... ({len(items)} total)"
        print(f"  {name:<30} {sample_str}")


def simplified_name_groups() -> dict[str, list[str]]:
    """Return a dict mapping simplified names to lists of character variant names.
    e.g., {'Toad': ['Toad(R)', 'Toad(B)', 'Toad(Y)', 'Toad(G)', 'Toad(P)'], ...}
    """
    groups = {}
    for char, sn in Tables.SIMPLIFIED_NAME.items():
        groups.setdefault(sn, []).append(char)
    return groups


def _single_lookup(dictionary: dict, term):
    """Bidirectional single-term translation: id -> name or name -> id.

    Returns the matching value, or an ``"Invalid ID or Name: ..."`` string
    sentinel when the term is in neither the keys nor the values.
    """
    original_term = term
    if isinstance(term, str) and term.isdigit():
        term = int(term)
    if isinstance(term, float) and term.is_integer():
        term = int(term)

    str_term = str(term).lower()
    # Lowercased indexes onto the *real* keys, so a case-insensitive match
    # resolves to the actual table entry in either direction. Matching a key
    # (id -> name) wins over matching a value (name -> id); on a collision the
    # first spelling in the table wins.
    key_by_lower_key: dict[str, object] = {}
    key_by_lower_value: dict[str, object] = {}
    for k, v in dictionary.items():
        key_by_lower_key.setdefault(str(k).lower(), k)
        key_by_lower_value.setdefault(str(v).lower(), k)

    if str_term in key_by_lower_key:
        return dictionary[key_by_lower_key[str_term]]
    if str_term in key_by_lower_value:
        return key_by_lower_value[str_term]
    return f"Invalid ID or Name: {original_term}"


# -------------------------------------------------------------------------
# Value objects
# -------------------------------------------------------------------------

_RV = TypeVar("_RV", bound="RioValue")

# Distinguishes "id absent from the table" from "id maps to None".
_MISSING = object()


@dataclass(frozen=True, eq=False, repr=False)
class RioValue:
    """A Project Rio coded value: an id paired with its canonical name.

    Subclasses set ``_lookup`` to their :class:`Tables` mapping and inherit
    :meth:`from_raw`, which resolves a raw id or name (the encoded-vs-decoded
    difference) into a value object.

    Equality is value-to-value only: a value object equals another of the same
    type with the same id, and is never equal to a raw int or str. Compare
    ``.id`` / ``.name`` (or another value object) instead. ``int()`` yields the
    id and ``str()`` yields the name as explicit, unambiguous conversions.
    """
    id: int
    name: str

    # Subclasses point this at their Tables mapping.
    _lookup: ClassVar[dict] = {}

    def __post_init__(self) -> None:
        """Reject an id/name pair that does not agree with this type's table.

        Equality and hashing use the id alone, so an inconsistent pair would
        otherwise compare equal to the correctly-named value and silently
        misreport its name. The bare ``RioValue`` has no table and stays
        unvalidated, so it can still stand in for an unmapped value type.
        """
        if not self._lookup:
            return
        expected = self._lookup.get(self.id, _MISSING)
        if expected is _MISSING:
            raise UnknownRioValueError(
                f"Unknown {type(self).__name__} id: {self.id!r}"
            )
        if self.name != expected:
            raise UnknownRioValueError(
                f"{type(self).__name__} id {self.id!r} is {expected!r}, "
                f"not {self.name!r}"
            )

    def __int__(self) -> int:
        return self.id

    def __str__(self) -> str:
        return self.name

    def __repr__(self) -> str:
        return f"{type(self).__name__}({self.id!r}, {self.name!r})"

    def __eq__(self, other: object) -> bool:
        if isinstance(other, RioValue):
            return type(self) is type(other) and self.id == other.id
        return NotImplemented

    def __hash__(self) -> int:
        return hash((type(self).__name__, self.id))

    @classmethod
    @overload
    def from_raw(cls: "type[_RV]", search_term: "int | str | _RV") -> "_RV": ...
    @classmethod
    @overload
    def from_raw(cls: "type[_RV]", search_term: None) -> None: ...
    @classmethod
    def from_raw(cls: "type[_RV]", search_term: "int | str | _RV | None") -> "_RV | None":
        """Resolve a raw id or name to a value object (``None`` -> ``None``).

        Accepts the canonical int id, a digit string, the name string, or an
        already-resolved value object of the same type (returned as-is), so it
        absorbs the encoded-vs-decoded difference. Raises
        ``UnknownRioValueError`` (a ``ValueError``) for an id/name that is not
        in this type's mapping, or a value object of a different type.
        """
        if search_term is None:
            return None
        if isinstance(search_term, (RioValue, BaseCharacter)):
            if isinstance(search_term, cls):
                return search_term
            raise UnknownRioValueError(f"Cannot resolve {search_term!r} as a {cls.__name__}")
        if isinstance(search_term, bool):
            raise UnknownRioValueError(f"Unknown {cls.__name__}: {search_term!r}")
        d = cls._lookup
        if isinstance(search_term, int):
            id_ = search_term
        elif isinstance(search_term, str) and search_term.isdigit():
            id_ = int(search_term)
        else:
            id_ = _single_lookup(d, search_term)
            if not isinstance(id_, int):
                raise UnknownRioValueError(f"Unknown {cls.__name__}: {search_term!r}")
        name = _single_lookup(d, id_)
        if not isinstance(name, str) or name.startswith("Invalid"):
            raise UnknownRioValueError(f"Unknown {cls.__name__} id: {search_term!r}")
        return cls(id_, name)


class Character(RioValue):
    """A Mario Superstar Baseball character: char id plus canonical name."""

    _lookup = Tables.CHAR_NAME

    @classmethod
    @overload
    def from_raw(cls, search_term: "int | str | Character") -> "Character": ...
    @classmethod
    @overload
    def from_raw(cls, search_term: None) -> None: ...
    @classmethod
    def from_raw(cls, search_term: "int | str | Character | None") -> "Character | None":
        """Resolve a char id or name (any alias) to a Character (None -> None)."""
        if search_term is None:
            return None
        if isinstance(search_term, str) and not search_term.isdigit():
            name = userInputToCharacter(search_term)  # raises UnknownRioValueError if unknown
            return cls(_single_lookup(Tables.CHAR_NAME, name), name)
        return super().from_raw(search_term)

    @property
    def name_no_variant(self) -> str:
        """Name without the colour/variant suffix, e.g. 'Pianta(R)' -> 'Pianta'."""
        return Tables.SIMPLIFIED_NAME.get(self.name, self.name)

    @property
    def base(self) -> "BaseCharacter":
        """The variant-less identity of this character (e.g. 'Pianta(R)' -> Pianta)."""
        return BaseCharacter(self.name_no_variant)

    @property
    def hex(self) -> str:
        """Char id as a hex string, e.g. '0x15'."""
        return hex(self.id)

    @property
    def attributes(self) -> "CharacterAttributes":
        """Base (star-OFF) attributes for this character, incl. ``char_class``
        and ``is_captain``.

        Use ``.attributes.with_superstar()`` for star-ON values -- a bare
        Character has no game context to know whether it is starred.
        """
        from .constants.character_data import character_attributes
        return character_attributes(self.id)


# Simplified (variant-less) character names, and a representative variant id per
# name for base-level attribute lookups.
_SIMPLIFIED_NAMES = set(Tables.SIMPLIFIED_NAME.values())
_BASE_REPRESENTATIVE_ID: dict[str, int] = {}
for _cid, _full in Tables.CHAR_NAME.items():
    _BASE_REPRESENTATIVE_ID.setdefault(Tables.SIMPLIFIED_NAME.get(_full, _full), _cid)


@dataclass(frozen=True, eq=False, repr=False)
class BaseCharacter:
    """A character identity without its colour/variant suffix (e.g. 'Pianta').

    Distinct from :class:`Character`, which is a single variant (id 0-53): all
    Pianta variants share one ``BaseCharacter``. Equality and hashing are by
    name, and never equal to a raw string. Class/captain are variant-invariant,
    so they live here too.
    """
    name: str

    def __str__(self) -> str:
        return self.name

    def __repr__(self) -> str:
        return f"BaseCharacter({self.name!r})"

    def __eq__(self, other: object) -> bool:
        if isinstance(other, BaseCharacter):
            return self.name == other.name
        return NotImplemented

    def __hash__(self) -> int:
        return hash(("BaseCharacter", self.name))

    @classmethod
    @overload
    def from_raw(cls, value: "int | str | Character | BaseCharacter") -> "BaseCharacter": ...
    @classmethod
    @overload
    def from_raw(cls, value: None) -> None: ...
    @classmethod
    def from_raw(cls, value: "int | str | Character | BaseCharacter | None") -> "BaseCharacter | None":
        """Resolve a simplified name, variant name, alias, char id, or Character
        to a base character (None -> None)."""
        if value is None:
            return None
        if isinstance(value, BaseCharacter):
            return value
        if isinstance(value, str) and value in _SIMPLIFIED_NAMES:
            return cls(value)
        return Character.from_raw(value).base

    @property
    def attributes(self) -> "CharacterAttributes":
        """Attributes of a representative variant (class/captain are shared)."""
        from .constants.character_data import character_attributes
        return character_attributes(_BASE_REPRESENTATIVE_ID[self.name])

    @property
    def char_class(self) -> str:
        return self.attributes.char_class

    @property
    def is_captain(self) -> bool:
        return self.attributes.is_captain


# Legacy decoded stadium names -> canonical names.
_OLD_STADIUM_NAMES = {
    "Bowser's Castle": "Bowser Castle",
    "Wario's Palace": "Wario Palace",
    "Yoshi's Island": "Yoshi Park",
    "Peach's Garden": "Peach Garden",
    "DK's Jungle": "DK Jungle",
}


class Stadium(RioValue):
    """A Mario Superstar Baseball stadium."""

    _lookup = Tables.STADIUM

    @classmethod
    @overload
    def from_raw(cls, search_term: "int | str | Stadium") -> "Stadium": ...
    @classmethod
    @overload
    def from_raw(cls, search_term: None) -> None: ...
    @classmethod
    def from_raw(cls, search_term: "int | str | Stadium | None") -> "Stadium | None":
        """Resolve a stadium id or name (incl. legacy names) to a Stadium."""
        if isinstance(search_term, str):
            search_term = _OLD_STADIUM_NAMES.get(search_term, search_term)
        return super().from_raw(search_term)


class PitchType(RioValue):
    """A pitch type: Curve / Charge / ChangeUp."""

    _lookup = Tables.PITCH_TYPE


class ChargeType(RioValue):
    """A charge pitch type."""

    _lookup = Tables.CHARGE_TYPE


class SwingType(RioValue):
    """A type of swing: None / Slap / Charge / Star / Bunt."""

    _lookup = Tables.TYPE_OF_SWING


class ContactType(RioValue):
    """A type of bat contact: Sour/Nice/Perfect/Miss."""

    _lookup = Tables.CONTACT_TYPE


class FinalResult(RioValue):
    """The final result of an at-bat (cAtBatResult)."""

    _lookup = Tables.FINAL_RESULT


class PrimaryContactResult(RioValue):
    """Primary contact result: Out / Foul / Fair / Fielded."""

    _lookup = Tables.PRIMARY_CONTACT_RESULT


class SecondaryContactResult(RioValue):
    """Secondary contact result: the detailed hit/out outcome."""

    _lookup = Tables.SECONDARY_CONTACT_RESULT


class OutType(RioValue):
    """How an out was made: Caught / Force / Tag / ..."""

    _lookup = Tables.OUT_TYPE


class StealType(RioValue):
    """A steal type: None / Ready / Normal / Perfect."""

    _lookup = Tables.STEAL_TYPE


class PitchResult(RioValue):
    """The result of a pitch: HBP / BB / Ball / Strike / Contact."""

    _lookup = Tables.PITCH_RESULT


class Hand(RioValue):
    """Handedness: Right / Left."""

    _lookup = Tables.HAND


class Position(RioValue):
    """A fielding position: P/C/1B/.../RF, or Inv."""

    _lookup = Tables.POSITION


class FielderAction(RioValue):
    """A fielder action: None / Sliding / Walljump / ..."""

    _lookup = Tables.FIELDER_ACTIONS


class FielderBobble(RioValue):
    """A fielder bobble: None / Bobble / Fireball / Fumble / ..."""

    _lookup = Tables.FIELDER_BOBBLES


class ManualSelect(RioValue):
    """Manual fielder selection: No Selected Char / Pitcher / Catcher / ..."""

    _lookup = Tables.MANUAL_SELECT


# The canonical logo table groups ids in fours per captain: id // 4 gives the
# captain (in this order, which matches no other canonical sort) and id % 4
# gives the role. team_name_algo's CAPTAIN_TEAMS is validated against this.
_TEAM_LOGO_CAPTAINS = (
    "Mario", "Luigi", "Peach", "Daisy", "Yoshi", "Birdo",
    "Wario", "Waluigi", "DK", "Diddy", "Bowser", "Bowser Jr",
)
_TEAM_LOGO_ROLES = ("signature", "signature", "class_team", "default")


class TeamName(RioValue):
    """A team (logo) name, e.g. 'Mario Fireballs'."""

    _lookup = Tables.TEAM_NAME

    @property
    def captain(self) -> "Character":
        """The captain whose logo this is."""
        return Character.from_raw(_TEAM_LOGO_CAPTAINS[self.id // 4])

    @property
    def role(self) -> str:
        """This logo's role for its captain: 'signature', 'class_team', or 'default'."""
        return _TEAM_LOGO_ROLES[self.id % 4]


class DeadBallReason(RioValue):
    """Why a ball was dead: N/A / Home Run / Foul Ball / Ground Rule Double / Ball Dead."""

    _lookup = Tables.DEAD_BALL_REASON


# -------------------------------------------------------------------------
# Generic bulk / string-name translation
# -------------------------------------------------------------------------
# For typed value objects (Character, Stadium, PitchType, ...) use the value
# class constructors, e.g. ``Character.from_raw(2)``. These functions are for
# raw dict translation and the pandas helpers.

def lookup(dictionary, search_term, auto_print: bool = False):
    """Look up a value in a table bidirectionally.

    dictionary: a dict, or a string name like 'char_name', 'stadium', etc.
    search_term: int ID, string name, list, pd.Series, or pd.DataFrame.
    """
    d = _resolve_dict(dictionary)

    if isinstance(search_term, list):
        result = [_single_lookup(d, term) for term in search_term]
    elif type(search_term).__module__.split('.')[0] == 'pandas':
        # Only import pandas when we were actually handed a pandas object.
        import pandas as pd
        if isinstance(search_term, pd.Series):
            result = search_term.apply(lambda t: _single_lookup(d, t))
        elif isinstance(search_term, pd.DataFrame):
            result = search_term.map(lambda t: _single_lookup(d, t))
        else:
            result = _single_lookup(d, search_term)
    else:
        result = _single_lookup(d, search_term)

    if auto_print:
        print(result)
    return result


def create_translated_columns(df: "pd.DataFrame") -> "pd.DataFrame":
    """Add _str columns with human-readable translations for known columns."""
    column_to_dict_map = {
        'batter_char_id': Tables.CHAR_NAME,
        'pitcher_char_id': Tables.CHAR_NAME,
        'fielder_char_id': Tables.CHAR_NAME,
        'batting_hand': Tables.HAND_BOOL,
        'fielder_jump': Tables.FIELDER_ACTIONS,
        'fielder_position': Tables.POSITION,
        'fielding_hand': Tables.HAND_BOOL,
        'final_result': Tables.FINAL_RESULT,
        'manual_select_state': Tables.MANUAL_SELECT,
        'stick_input': Tables.INPUT_DIRECTION,
        'type_of_contact': Tables.CONTACT_TYPE,
        'type_of_swing': Tables.TYPE_OF_SWING,
        'stadium': Tables.STADIUM,
    }

    for column, dict_name in column_to_dict_map.items():
        if column in df.columns:
            translated_values = lookup(dict_name, df[column])
            df[f'{column}_str'] = translated_values.astype('category')

    return df


# -------------------------------------------------------------------------
# Character name resolution (merged from characters.py)
# -------------------------------------------------------------------------

def _resource_path(relative_path: str) -> str:
    """Get absolute path to resource, works for dev and for PyInstaller bundle."""
    if hasattr(sys, '_MEIPASS'):
        return os.path.join(sys._MEIPASS, relative_path)
    return os.path.join(os.path.abspath("."), relative_path)


def _load_char_aliases() -> dict[str, int]:
    """Load CharNames.csv and build a mapping of all aliases -> char ID."""
    aliases = {}
    csv_path = _resource_path(os.path.join(os.path.dirname(__file__), "CharNames.csv"))
    with open(csv_path, "r") as f:
        for char_id, row in enumerate(csv.reader(f)):
            for name in row:
                aliases[name] = char_id
    return aliases


_CHAR_ALIASES = _load_char_aliases()


def userInputToCharacter(user_input: str) -> str:
    """Convert user input (nickname, abbreviation, etc.) to canonical character name.

    Case-insensitive, space-insensitive.
    Raises UnknownRioValueError for unrecognized input.
    """
    cleaned = user_input.replace(' ', '').lower()
    if cleaned not in _CHAR_ALIASES:
        raise UnknownRioValueError(f'{user_input} is an invalid character name')
    return lookup(Tables.CHAR_NAME, _CHAR_ALIASES[cleaned])


def is_captain(character: str) -> bool:
    """Check if a character (by any name/alias) is a captain."""
    from .constants.character_data import character_attributes
    return character_attributes(userInputToCharacter(character)).is_captain



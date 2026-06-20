"""Bidirectional lookup for Project Rio ID/name mappings.

    lookup("char_name", 0)          -> "Mario"
    lookup("char_name", "Mario")    -> 0
    lookup(LookupDicts.CHAR_NAME, 0) -> "Mario"   # also works

    list_dicts()  # prints all available dictionary names
"""
import csv
import os
import sys
from dataclasses import dataclass

import pandas as pd

CAPTAINS = [
    'Mario',
    'Luigi',
    'DK',
    'Diddy',
    'Peach',
    'Daisy',
    'Yoshi',
    'Bowser',
    'Wario',
    'Waluigi',
    'Birdo',
    'Bowser Jr'
]


class LookupDicts:
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
        0: "Left",
        1: "Right"
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
        55: "None"
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
        3: "foul",
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
        1: "Selected Other Char",
        2: "Selected This Char",
        None: "None"
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

    CHAR_CLASS = {
        'Mario': 'Balance',
        'Luigi': 'Balance',
        'DK': 'Power',
        'Diddy': 'Speed',
        'Peach': 'Technique',
        'Daisy': 'Balance',
        'Yoshi': 'Speed',
        'Baby Mario': 'Speed',
        'Baby Luigi': 'Speed',
        'Bowser': 'Power',
        'Wario': 'Power',
        'Waluigi': 'Technique',
        'Koopa': 'Balance',
        'Toad': 'Balance',
        'Boo': 'Technique',
        'Toadette': 'Speed',
        'Shy Guy': 'Balance',
        'Birdo': 'Balance',
        'Monty': 'Speed',
        'Bowser Jr': 'Power',
        'Paratroopa': 'Technique',
        'Pianta': 'Power',
        'Noki': 'Speed',
        'Bro': 'Power',
        'Toadsworth': 'Technique',
        'Magikoopa': 'Technique',
        'King Boo': 'Power',
        'Petey': 'Power',
        'Dixie': 'Technique',
        'Goomba': 'Balance',
        'Paragoomba': 'Speed',
        'Dry Bones': 'Technique',
    }


# -------------------------------------------------------------------------
# String-name registry: maps friendly names -> LookupDicts attributes
# -------------------------------------------------------------------------

_DICT_REGISTRY: dict[str, dict] = {}


def _build_registry():
    """Build the string-name -> dict mapping from LookupDicts attributes."""
    for attr_name in dir(LookupDicts):
        if attr_name.startswith('_'):
            continue
        val = getattr(LookupDicts, attr_name)
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
        raise ValueError(
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
    for char, sn in LookupDicts.SIMPLIFIED_NAME.items():
        groups.setdefault(sn, []).append(char)
    return groups


# -------------------------------------------------------------------------
# Value objects
# -------------------------------------------------------------------------

@dataclass(frozen=True, eq=False, repr=False)
class LookupValue:
    """An id paired with its canonical name.

    Equality is value-to-value only: a value object equals another of the same
    type with the same id, and is never equal to a raw int or str. Compare
    ``.id`` / ``.name`` (or another value object) instead. ``int()`` yields the
    id and ``str()`` yields the name as explicit, unambiguous conversions.
    """
    id: int
    name: str

    def __int__(self) -> int:
        return self.id

    def __str__(self) -> str:
        return self.name

    def __repr__(self) -> str:
        return f"{type(self).__name__}({self.id!r}, {self.name!r})"

    def __eq__(self, other: object) -> bool:
        if isinstance(other, LookupValue):
            return type(self) is type(other) and self.id == other.id
        return NotImplemented

    def __hash__(self) -> int:
        return hash((type(self).__name__, self.id))


class Character(LookupValue):
    """A Mario Superstar Baseball character: char id plus canonical name."""

    @property
    def name_no_variant(self) -> str:
        """Name without the colour/variant suffix, e.g. 'Pianta(R)' -> 'Pianta'."""
        return LookupDicts.SIMPLIFIED_NAME.get(self.name, self.name)

    @property
    def hex(self) -> str:
        """Char id as a hex string, e.g. '0x15'."""
        return hex(self.id)

    @property
    def char_class(self) -> str | None:
        """Class ('Balance', 'Power', 'Speed', 'Technique'), or None if unknown."""
        return LookupDicts.CHAR_CLASS.get(self.name_no_variant)

    @property
    def is_captain(self) -> bool:
        """Whether this character can captain a team."""
        return self.name_no_variant in CAPTAINS


class Stadium(LookupValue):
    """A Mario Superstar Baseball stadium."""


# Legacy decoded stadium names -> canonical names.
_OLD_STADIUM_NAMES = {
    "Bowser's Castle": "Bowser Castle",
    "Wario's Palace": "Wario Palace",
    "Yoshi's Island": "Yoshi Park",
    "Peach's Garden": "Peach Garden",
    "DK's Jungle": "DK Jungle",
}


# -------------------------------------------------------------------------
# Lookup class and module-level function
# -------------------------------------------------------------------------

class Lookup:
    """Bidirectional lookup between IDs and names. All methods are static."""

    @staticmethod
    def _single_lookup(dictionary: dict, term):
        original_term = term
        if isinstance(term, str) and term.isdigit():
            term = int(term)
        if isinstance(term, float) and term.is_integer():
            term = int(term)

        str_term = str(term).lower()
        adjusted_dict = {str(k).lower(): str(v).lower() for k, v in dictionary.items()}

        if str_term in adjusted_dict:
            return dictionary.get(term, f"Invalid ID or Name: {original_term}")
        elif str_term in adjusted_dict.values():
            return [key for key, value in dictionary.items() if value.lower() == str_term][0]
        else:
            return f"Invalid ID or Name: {original_term}"

    @staticmethod
    def lookup(dictionary, search_term, auto_print: bool = False):
        """Look up a value in a dictionary bidirectionally.

        dictionary: a dict, or a string name like 'char_name', 'stadium', etc.
        search_term: int ID, string name, list, pd.Series, or pd.DataFrame.
        """
        d = _resolve_dict(dictionary)
        sl = Lookup._single_lookup

        if isinstance(search_term, pd.Series):
            result = search_term.apply(lambda t: sl(d, t))
        elif isinstance(search_term, pd.DataFrame):
            result = search_term.map(lambda t: sl(d, t))
        elif isinstance(search_term, list):
            result = [sl(d, term) for term in search_term]
        else:
            result = sl(d, search_term)

        if auto_print:
            print(result)
        return result

    @staticmethod
    def translate_values(dictionary, values):
        return Lookup.lookup(dictionary, values)

    @staticmethod
    def character(search_term: int | str) -> "Character":
        """Resolve a char id or name (any alias) to a Character value object."""
        if isinstance(search_term, str) and not search_term.isdigit():
            name = userInputToCharacter(search_term)  # raises ValueError if unknown
            char_id = Lookup.lookup(LookupDicts.CHAR_NAME, name)
        else:
            char_id = int(search_term)
            name = Lookup.lookup(LookupDicts.CHAR_NAME, char_id)
            if not isinstance(name, str) or name.startswith("Invalid"):
                raise ValueError(f"Unknown character id: {search_term!r}")
        return Character(char_id, name)

    @staticmethod
    def _value(dictionary, search_term, value_cls):
        """Resolve an id or name to a value_cls value object.

        Accepts the canonical int id or the name string (so it absorbs the
        encoded-vs-decoded difference). None passes through as None.
        """
        if search_term is None:
            return None
        if isinstance(search_term, bool):
            raise ValueError(f"Unknown {value_cls.__name__}: {search_term!r}")
        d = _resolve_dict(dictionary)
        if isinstance(search_term, int):
            id_ = search_term
        elif isinstance(search_term, str) and search_term.isdigit():
            id_ = int(search_term)
        else:
            id_ = Lookup._single_lookup(d, search_term)
            if not isinstance(id_, int):
                raise ValueError(f"Unknown {value_cls.__name__}: {search_term!r}")
        name = Lookup._single_lookup(d, id_)
        if not isinstance(name, str) or name.startswith("Invalid"):
            raise ValueError(f"Unknown {value_cls.__name__} id: {search_term!r}")
        return value_cls(id_, name)

    @staticmethod
    def stadium(search_term: int | str) -> "Stadium":
        """Resolve a stadium id or name (incl. legacy names) to a Stadium."""
        if isinstance(search_term, str):
            search_term = _OLD_STADIUM_NAMES.get(search_term, search_term)
        return Lookup._value(LookupDicts.STADIUM, search_term, Stadium)

    @staticmethod
    def create_translated_columns(df: pd.DataFrame) -> pd.DataFrame:
        """Add _str columns with human-readable translations for known columns."""
        column_to_dict_map = {
            'batter_char_id': LookupDicts.CHAR_NAME,
            'pitcher_char_id': LookupDicts.CHAR_NAME,
            'fielder_char_id': LookupDicts.CHAR_NAME,
            'batting_hand': LookupDicts.HAND_BOOL,
            'fielder_jump': LookupDicts.FIELDER_ACTIONS,
            'fielder_position': LookupDicts.POSITION,
            'fielding_hand': LookupDicts.HAND_BOOL,
            'final_result': LookupDicts.FINAL_RESULT,
            'manual_select_state': LookupDicts.MANUAL_SELECT,
            'stick_input': LookupDicts.INPUT_DIRECTION,
            'type_of_contact': LookupDicts.CONTACT_TYPE,
            'type_of_swing': LookupDicts.TYPE_OF_SWING,
            'stadium': LookupDicts.STADIUM,
        }

        for column, dict_name in column_to_dict_map.items():
            if column in df.columns:
                translated_values = Lookup.lookup(dict_name, df[column])
                df[f'{column}_str'] = translated_values.astype('category')

        return df


# Module-level convenience alias
lookup = Lookup.lookup


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
    Raises ValueError for unrecognized input.
    """
    cleaned = user_input.replace(' ', '').lower()
    if cleaned not in _CHAR_ALIASES:
        raise ValueError(f'{user_input} is an invalid character name')
    return lookup(LookupDicts.CHAR_NAME, _CHAR_ALIASES[cleaned])


def is_captain(character: str) -> bool:
    """Check if a character (by any name/alias) is a captain."""
    return userInputToCharacter(character) in CAPTAINS



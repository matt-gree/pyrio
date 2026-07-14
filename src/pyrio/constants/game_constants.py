"""General game constants for the hit simulator.

Decode tables that mirror the stat-file format (handedness, pitch/swing types)
are sourced from the canonical lookup layer (``pyrio.rio_value``) so there is a
single, parity-tested source of truth -- they are NOT duplicated here. This
module keeps only the hit-sim-specific data: stadium coordinate files,
character-attribute column encodings, the superstar conversion, and the
field-coercion helpers.
"""
from ..rio_value import Tables

# Stat-file decode tables, re-exported from the canonical lookup layer (single
# source of truth, guarded by tests/test_canonical_parity.py). The hit-sim
# pipeline works in ENCODED ints and touches these only via to_encoded(), so it
# accepts either encoded or decoded stat files.
HAND = Tables.HAND
PITCH_TYPE = Tables.PITCH_TYPE
CHARGE_PITCH_TYPE = Tables.CHARGE_TYPE
TYPE_OF_SWING = Tables.TYPE_OF_SWING
TYPE_OF_CONTACT = Tables.CONTACT_TYPE
SECONDARY_CONTACT_RESULT = Tables.SECONDARY_CONTACT_RESULT

# Encoded stadium id -> boundary-coordinate file in constants/stadiums/.
# Toy Field has no boundary file (open field), so it is intentionally absent.
STADIUM_ID_TO_COORD_FILE = {
    0x0: "mario_stadium.txt",
    0x1: "bowser_castle.txt",
    0x2: "wario_palace.txt",
    0x3: "yoshi_park.txt",
    0x4: "peach_garden.txt",
    0x5: "dk_jungle.txt",
}


# --------------------------------------------------------------------------
# Character-attribute column encodings, the superstar conversion (per-stat
# delta/cap), and the ability list now live in constants/character_data.py, where
# the AttributeSpec registry (ATTRIBUTES) is the single source of truth for
# per-character attributes. Star-ON values: CharacterAttributes.with_superstar(),
# or AttributeSpec.to_star_on() for a single stat.


# --------------------------------------------------------------------------
# Field coercion (encoded <-> decoded stat files)
# --------------------------------------------------------------------------
# Stat files come in two flavors: "decoded" (categorical fields as strings) and
# "encoded" (the raw ints). These helpers accept either so consumers can work in
# encoded values regardless of which file flavor they were handed.

def to_encoded(table, value):
    """Return the encoded int for a field value.

    ``value`` may already be an encoded int (returned as-is) or a decoded string
    that appears as a value in ``table`` (an encoded->decoded map), which is
    reverse-looked-up. Raises KeyError if a string is not found.
    """
    if isinstance(value, int):
        return value
    for code, label in table.items():
        if label == value:
            return code
    raise KeyError(f"{value!r} not found in {table}")


# Batting stick input is a bitmask (decoded as a '+'-joined string, e.g.
# "Left+Down"). Bits:
STICK_LEFT = 0x1
STICK_RIGHT = 0x2
STICK_DOWN = 0x4
STICK_UP = 0x8


def stick_directions(value):
    """Return (up, down, left, right) bools from a stick input value.

    Accepts either an encoded bitmask int or a decoded '+'-joined string.
    """
    if isinstance(value, int):
        return (bool(value & STICK_UP), bool(value & STICK_DOWN),
                bool(value & STICK_LEFT), bool(value & STICK_RIGHT))
    s = value or ""
    return ("Up" in s, "Down" in s, "Left" in s, "Right" in s)

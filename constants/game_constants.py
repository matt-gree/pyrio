"""General game constants for the hit simulator.

Decode tables that mirror the stat-file format (handedness, pitch/swing types)
are sourced from the canonical lookup layer (``pyrio.lookup``) so there is a
single, parity-tested source of truth -- they are NOT duplicated here. This
module keeps only the hit-sim-specific data: stadium coordinate files,
character-attribute column encodings, the superstar conversion, and the
field-coercion helpers.
"""
from ..lookup import LookupDicts

# Stat-file decode tables, re-exported from the canonical lookup layer (single
# source of truth, guarded by tests/test_canonical_parity.py). The hit-sim
# pipeline works in ENCODED ints and touches these only via to_encoded(), so it
# accepts either encoded or decoded stat files.
HAND = LookupDicts.HAND
PITCH_TYPE = LookupDicts.PITCH_TYPE
CHARGE_PITCH_TYPE = LookupDicts.CHARGE_TYPE
TYPE_OF_SWING = LookupDicts.TYPE_OF_SWING

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
# Character-attribute column encodings
# --------------------------------------------------------------------------
# Encoded->decoded maps for the categorical columns of character_attributes.csv.
# Right/Left columns (Fielding Arm, Batting Stance) reuse HAND above; the
# Captain Character column is a plain 1/0 boolean.

HORIZONTAL_HIT_TRAJECTORY = {
    0: "Mid",
    1: "Pull",
    2: "Push",
}

VERTICAL_HIT_TRAJECTORY = {
    0: "Mid",
    1: "High",
    2: "Low",
}

# Captain star ball (used by both the Captain Star Pitch and Captain Star Hit
# columns -- a captain's star pitch and star hit are the same ball). 0 = none
# (non-captain rows). Codes 1-12 index the captain-star tables in the hit sim.
CAPTAIN_STAR_BALL = {
    0: "",
    1: "Fireball",
    2: "Green Fireball",
    3: "Phony Ball",
    4: "Liar Ball",
    5: "Banana Ball",
    6: "Boomerang Ball",
    7: "Killer Ball",
    8: "Killer Jr. Ball",
    9: "Egg Ball",
    10: "Weird Ball",
    11: "Heart Ball",
    12: "Flower Ball",
}

# Non-captain star hit trajectory (the "Non-Captain Star Hit" column). Codes 1-3
# index the non-captain-star tables in the hit sim.
NON_CAPTAIN_STAR_HIT = {
    1: "Pop Fly",
    2: "Grounder",
    3: "Line Drive",
}

CHARACTER_CLASS = {
    0: "Balance",
    1: "Power",
    2: "Speed",
    3: "Technique",
}

# Non-captain star pitch type (the "Non-Captain Star Pitch" column). Note the
# attribute data labels the curve pitch "Breaking Ball"; both map to code 1.
NON_CAPTAIN_STAR_PITCH_TYPE = {
    1: "Curve",      # data spelling: "Breaking Ball"
    2: "Fastball",
    3: "Change-Up",
}

# Abilities. In-game these are a bitmask; in character_attributes.csv they are
# flattened to one 0/1 flag column per ability (column name == ability name),
# replacing the old Ability 1 / Ability 2 columns.
ABILITIES = [
    "Ball Dash",
    "Body Check",
    "Clamber",
    "Laser Beam",
    "Magical Catch",
    "Quick Throw",
    "Sliding Catch",
    "Suction",
    "Super Catch",
    "Super Jump",
    "Tongue Catch",
    "Wall Jump",
]

# --------------------------------------------------------------------------
# Superstar ("star on") conversion
# --------------------------------------------------------------------------

# The character attribute table stores star-OFF (base) values. Turning a
# character superstar applies a flat per-stat buff, clamped to an optional cap.
# Verified against the legacy ston/stoff CSVs: every cell equals
# min(base + delta, cap) with zero exceptions.
#
# Keys are character-attribute column names; value is (delta, cap) where cap is
# None for stats that may exceed 100 (Speed, Curve Control, and the two pitch
# speeds, observed up to 140/195 respectively).
SUPERSTAR_STAT_MODIFIERS = {
    "Curve Ball Speed": (20, None),
    "Fast Ball Speed": (20, None),
    "Curve": (50, 100),
    "Cursed Ball": (50, 100),
    "Curve Control": (50, None),
    "Throwing Power": (50, 100),
    "Speed": (50, None),
    "Slap Hit Power": (50, 100),
    "Charge Hit Power": (50, 100),
    "Bunting": (50, 100),
    "Slap Contact Size Multiplier": (50, 100),
    "Charge Contact Size Multiplier": (50, 100),
}


def apply_superstar(stat_name, base_value):
    """Convert a star-OFF stat value to its star-ON value.

    Returns ``base_value`` unchanged for stats that have no superstar modifier.
    """
    mod = SUPERSTAR_STAT_MODIFIERS.get(stat_name)
    if mod is None:
        return base_value
    delta, cap = mod
    boosted = base_value + delta
    return min(boosted, cap) if cap is not None else boosted


def apply_superstar_row(row):
    """Return a copy of a character-attribute row with star-ON stat values.

    Only the SUPERSTAR_STAT_MODIFIERS columns are converted; every other column
    (name, class, abilities, etc.) passes through unchanged.
    """
    out = dict(row)
    for col in SUPERSTAR_STAT_MODIFIERS:
        if col in out:
            out[col] = apply_superstar(col, int(out[col]))
    return out


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

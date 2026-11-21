"""General game constants and encoded->decoded lookup tables.

The pipeline works in ENCODED values (the raw bytes the game stores, e.g. char
id 0x0, contact type 2). These dictionaries decode those encoded values into
human-readable strings only when needed (display, the "decoded" stat file). Keep
data in encoded form; decode at the edges.

The decode tables are ported from the stat-file creator's C++ header
(MSB_StatTracker.h, the ``c*`` maps). Memory addresses / struct layouts from that
header are emulator-side only and intentionally not ported here.
"""

DEAD_BALL_REASON = {
    0x0: "N/A",
    0x1: "Home Run",
    0x2: "Foul Ball",
    0x3: "Ground Rule Double",
    0x4: "Ball Dead",
}

GAME_CONTROL_STATE = {
    0x0: "default",
    0x1: "AtBat",
    0x2: "LiveBall",
    0x3: "InningTransition",
    0x4: "LoadGame",
    0x5: "GameStartMovie",
    0x6: "TransitionToMinigameStart",
    0x7: "TransitionPrepareNextGame",
    0x8: "TransitionMainFunction",
    0x9: "EndOfGame?",
    0xb: "Paused",
    0xd: "HowToPlayScreen",
    0xe: "MVP/EndGameScreen",
    0xf: "MinigamePostGameTransition",
    0x13: "HomeRunEnd",
    0x14: "HomeRunLap",
    0x15: "PostReplayBatterCelebration",
    0x16: "StarChanceVsScreen",
    0x17: "ChampionshipScreen",
    0x19: "MinigameNewRound?",
    0x1a: "MinigameTransitionToBatting1",
    0x1c: "MinigameSelectScreen",
    0x1d: "ToyFieldStadiumLoadScreen",
    0x1e: "CharacterSelectMinigameToyField",
    0x21: "ReadyMinigameScreen",
    0x22: "PostMinigameMenu",
}

# --------------------------------------------------------------------------
# Character-attribute column encodings
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
    "Bunt Contact Size Multiplier": (50, None),
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
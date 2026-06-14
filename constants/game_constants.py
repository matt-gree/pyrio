"""General game constants and encoded->decoded lookup tables.

The pipeline works in ENCODED values (the raw bytes the game stores, e.g. char
id 0x0, contact type 2). These dictionaries decode those encoded values into
human-readable strings only when needed (display, the "decoded" stat file). Keep
data in encoded form; decode at the edges.

The decode tables are ported from the stat-file creator's C++ header
(MSB_StatTracker.h, the ``c*`` maps). Memory addresses / struct layouts from that
header are emulator-side only and intentionally not ported here.
"""

# --------------------------------------------------------------------------
# Characters
# --------------------------------------------------------------------------

# Encoded char id -> character name. The id IS the in-game id (matches the game,
# unlike the JS batting-calculator char ids), so this is the canonical join key.
CHAR_ID_TO_NAME = {
    0x0: "Mario",
    0x1: "Luigi",
    0x2: "DK",
    0x3: "Diddy",
    0x4: "Peach",
    0x5: "Daisy",
    0x6: "Yoshi",
    0x7: "Baby Mario",
    0x8: "Baby Luigi",
    0x9: "Bowser",
    0xa: "Wario",
    0xb: "Waluigi",
    0xc: "Koopa(G)",
    0xd: "Toad(R)",
    0xe: "Boo",
    0xf: "Toadette",
    0x10: "Shy Guy(R)",
    0x11: "Birdo",
    0x12: "Monty",
    0x13: "Bowser Jr",
    0x14: "Paratroopa(R)",
    0x15: "Pianta(B)",
    0x16: "Pianta(R)",
    0x17: "Pianta(Y)",
    0x18: "Noki(B)",
    0x19: "Noki(R)",
    0x1a: "Noki(G)",
    0x1b: "Bro(H)",
    0x1c: "Toadsworth",
    0x1d: "Toad(B)",
    0x1e: "Toad(Y)",
    0x1f: "Toad(G)",
    0x20: "Toad(P)",
    0x21: "Magikoopa(B)",
    0x22: "Magikoopa(R)",
    0x23: "Magikoopa(G)",
    0x24: "Magikoopa(Y)",
    0x25: "King Boo",
    0x26: "Petey",
    0x27: "Dixie",
    0x28: "Goomba",
    0x29: "Paragoomba",
    0x2a: "Koopa(R)",
    0x2b: "Paratroopa(G)",
    0x2c: "Shy Guy(B)",
    0x2d: "Shy Guy(Y)",
    0x2e: "Shy Guy(G)",
    0x2f: "Shy Guy(Bk)",
    0x30: "Dry Bones(Gy)",
    0x31: "Dry Bones(G)",
    0x32: "Dry Bones(R)",
    0x33: "Dry Bones(B)",
    0x34: "Bro(F)",
    0x35: "Bro(B)",
}

# Reverse: character name -> encoded char id (for encoding human-readable input).
NAME_TO_CHAR_ID = {name: cid for cid, name in CHAR_ID_TO_NAME.items()}

# Encoded char ids that are captain-type characters.
CAPTAIN_CHAR_IDS = frozenset({
    0x0,   # Mario
    0x1,   # Luigi
    0x2,   # DK
    0x3,   # Diddy
    0x4,   # Peach
    0x5,   # Daisy
    0x6,   # Yoshi
    0x9,   # Bowser
    0xa,   # Wario
    0xb,   # Waluigi
    0x11,  # Birdo
    0x13,  # Bowser Jr
})

# --------------------------------------------------------------------------
# Stadiums / teams
# --------------------------------------------------------------------------

STADIUM_ID_TO_NAME = {
    0x0: "Mario Stadium",
    0x1: "Bowser Castle",
    0x2: "Wario Palace",
    0x3: "Yoshi Park",
    0x4: "Peach Garden",
    0x5: "DK Jungle",
    0x6: "Toy Field",
}

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

LOGO_ID_TO_TEAM_NAME = {
    0x0: "Mario Sunshines",
    0x1: "Mario All Stars",
    0x2: "Mario Fireballs",
    0x3: "Mario Heroes",
    0x4: "Luigi Mansioneers",
    0x5: "Luigi Leapers",
    0x6: "Luigi Vacuums",
    0x7: "Luigi Gentlemen",
    0x8: "Peach Monarchs",
    0x9: "Peach Princesses",
    0xA: "Peach Dynasties",
    0xB: "Peach Roses",
    0xC: "Daisy Queen Bees",
    0xD: "Daisy Petals",
    0xE: "Daisy Cupids",
    0xF: "Daisy Lillies",
    0x10: "Yoshi Islanders",
    0x11: "Yoshi Flutters",
    0x12: "Yoshi Speed Stars",
    0x13: "Yoshi Eggs",
    0x14: "Birdo Bows",
    0x15: "Birdo Fans",
    0x16: "Birdo Models",
    0x17: "Birdo Beauties",
    0x18: "Wario Greats",
    0x19: "Wario Beasts",
    0x1A: "Wario Steakheads",
    0x1B: "Wario Garlics",
    0x1C: "Waluigi Flankers",
    0x1D: "Waluigi Mashers",
    0x1E: "Waluigi Smart Alecks",
    0x1F: "Waluigi Mystiques",
    0x20: "DK Kongs",
    0x21: "DK Animals",
    0x22: "DK Wild Ones",
    0x23: "DK Explorers",
    0x24: "Diddy Tails",
    0x25: "Diddy Red Caps",
    0x26: "Diddy Ninjas",
    0x27: "Diddy Survivors",
    0x28: "Bowser Monsters",
    0x29: "Bowser Black Stars",
    0x2A: "Bowser Blue Shells",
    0x2B: "Bowser Flames",
    0x2C: "Jr Pixies",
    0x2D: "Jr Rookies",
    0x2E: "Jr Bombers",
    0x2F: "Jr Fangs",
}

# --------------------------------------------------------------------------
# At-bat / contact
# --------------------------------------------------------------------------

TYPE_OF_CONTACT = {
    0xFF: "Miss",
    0: "Sour - Left",
    1: "Nice - Left",
    2: "Perfect",
    3: "Nice - Right",
    4: "Sour - Right",
}

HAND = {
    0: "Right",
    1: "Left",
}

INPUT_DIRECTION = {
    0: "None",
    1: "Towards Batter",
    2: "Away From Batter",
}

PITCH_TYPE = {
    0: "Curve",
    1: "Charge",
    2: "ChangeUp",
}

CHARGE_PITCH_TYPE = {
    0: "N/A",
    2: "Slider",
    3: "Perfect",
}

TYPE_OF_SWING = {
    0: "None",
    1: "Slap",
    2: "Charge",
    3: "Star",
    4: "Bunt",
}

# --------------------------------------------------------------------------
# Fielding
# --------------------------------------------------------------------------

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
    0xFF: "Inv",
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
    0x10: "Garlic knockout",
    0xFF: "None",
}

STEAL_TYPE = {
    0: "None",
    1: "Ready",
    2: "Normal",
    3: "Perfect",
    0xFF: "None",
}

OUT_TYPE = {
    0: "None",
    1: "Caught",
    2: "Force",
    3: "Tag",
    4: "Force Back",
    0x10: "Strike-out",
}

# --------------------------------------------------------------------------
# Results
# --------------------------------------------------------------------------

PITCH_RESULT = {
    0: "HBP",
    1: "BB",
    2: "Ball",
    3: "Strike-looking",
    4: "Strike-swing",
    5: "Strike-bunting",
    6: "Contact",
    7: "Unknown",
}

PRIMARY_CONTACT_RESULT = {
    0: "Out",
    1: "Foul",
    2: "Fair",
    3: "Fielded",
    4: "Unknown",
}

SECONDARY_CONTACT_RESULT = {
    0x0: "Out-caught",
    0x1: "Out-force",
    0x2: "Out-tag",
    0x3: "Foul",
    0x4: "Batter safe, runner out",
    0x7: "Single",
    0x8: "Double",
    0x9: "Triple",
    0xA: "HR",
    0xB: "Error - Input",
    0xC: "Error - Chem",
    0xD: "Bunt",
    0xE: "SacFly",
    0xF: "Ground ball double Play",
    0x10: "Foul catch",
}

AT_BAT_RESULT = {
    0x0: "None",
    0x1: "Strikeout",
    0x2: "Walk (BB)",
    0x3: "Walk (HBP)",
    0x4: "Out",
    0x5: "Caught",
    0x6: "Caught line-drive",
    0x7: "Single",
    0x8: "Double",
    0x9: "Triple",
    0xA: "HR",
    0xB: "Error - Input",
    0xC: "Error - Chem",
    0xD: "Bunt",
    0xE: "SacFly",
    0xF: "Ground ball double Play",
    0x10: "Foul catch",
}

DEAD_BALL_REASON = {
    0x0: "N/A",
    0x1: "Home Run",
    0x2: "Foul Ball",
    0x3: "Ground Rule Double",
    0x4: "Ball Dead",
}

MANUAL_SELECT = {
    0x0: "No Selected Char",
    0x1: "Pitcher",
    0x2: "Catcher",
    0x3: "Closest to Ball",
    0x4: "Closest to Drop",
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
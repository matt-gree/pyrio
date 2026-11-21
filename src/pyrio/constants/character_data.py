"""Per-character attribute data, loaded from ``character_attributes.csv``.

The ``ATTRIBUTES`` registry of :class:`AttributeSpec` descriptors is the single
source of truth for every character attribute: it drives CSV parsing, the
superstar conversion, and categorical decoding. ``CharacterAttributes`` is the
typed star-OFF (base) record; ``.with_superstar()`` returns the star-ON values.

Superstar model: starring a character adds a flat per-stat ``+delta``, with no
clamp. The decomp settles this -- the starring routine applies the bonus as a
bare ``+=`` to each of the twelve fields of ``SuperstarStatBonus``
(mssb-dtk ``src/Unknown/orderchange.c``, and the same twelve in
``src/game/minigame/minigame_framework.c``); only the four StatBar *display*
values are clamped, at 10. Every stat is a ``u8``, so 100 + 50 = 150 stores
fine (``StatTable`` in ``include/game/character_stats.h``).

The game does clamp these stats elsewhere, but under different systems that are
not the superstar bonus and are not modelled here:
  - challenge-mode mission buffs scale and clamp at 100, and the two pitch
    speeds at 200 (``scaleStat`` / ``capApplicationFunction`` in
    ``src/Unknown/File_0x8004207c.c``)
  - challenge shop items multiply, also unclamped (``roster_init.c``)

``cap`` is kept on AttributeSpec for those cases; the superstar specs leave it
None. Stats with ``superstar_delta == 0`` are unaffected by stars.
"""
from __future__ import annotations

import csv
from dataclasses import dataclass, fields, replace
from functools import lru_cache
from pathlib import Path
from typing import Callable, ClassVar, Optional

from ..rio_value import Tables

_CSV = Path(__file__).parent / "character_attributes.csv"


# --------------------------------------------------------------------------
# Categorical decode maps (encoded int -> decoded label) for attribute columns.
# Fielding Arm / Batting Stance reuse the canonical Tables.HAND.
# --------------------------------------------------------------------------

CHARACTER_CLASS = {0: "Balance", 1: "Power", 2: "Speed", 3: "Technique"}

HORIZONTAL_HIT_TRAJECTORY = {0: "Mid", 1: "Pull", 2: "Push"}

VERTICAL_HIT_TRAJECTORY = {0: "Mid", 1: "High", 2: "Low"}

# A captain's star pitch and star hit are the same ball; codes 1-12 index the
# captain-star tables in the hit sim. 0 = none (non-captain rows).
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

NON_CAPTAIN_STAR_HIT = {1: "Pop Fly", 2: "Grounder", 3: "Line Drive"}

# Data labels the curve pitch "Breaking Ball"; both map to code 1.
NON_CAPTAIN_STAR_PITCH_TYPE = {1: "Curve", 2: "Fastball", 3: "Change-Up"}


# --------------------------------------------------------------------------
# AttributeSpec: one descriptor per character-attribute column
# --------------------------------------------------------------------------

def _int(raw) -> int:
    # Tolerant: the CSV stores some integer flags as "1.0".
    return int(float(raw))


def _bool(raw) -> bool:
    return bool(int(raw))


@dataclass(frozen=True)
class AttributeSpec:
    """Describes one character attribute: how to parse it, its superstar
    behaviour, and (reserved) its in-memory address."""

    key: str                          # CharacterAttributes field name
    column: str                       # CSV header
    category: str                     # identity | pitching | fielding | batting | ability | star
    cast: Callable = _int             # raw str -> typed value (ignored when decode set)
    decode: Optional[dict] = None     # encoded int -> decoded label
    cap: Optional[int] = None         # superstar cap (None = uncapped)
    superstar_delta: int = 0          # 0 = not boosted by stars
    memory_address: Optional[int] = None  # reserved: live-memory reads

    def parse(self, raw):
        """Parse a raw CSV cell to its typed (decoded) value."""
        if self.decode is not None:
            return self.decode[int(raw)]
        return self.cast(raw)

    def encode(self, value):
        """Reverse of categorical decoding: decoded label -> encoded int.

        Returns ``value`` unchanged for non-categorical (numeric) attributes.
        """
        if self.decode is None:
            return value
        for code, label in self.decode.items():
            if label == value:
                return code
        raise KeyError(f"{value!r} is not a valid {self.column}")

    def to_star_on(self, base):
        """Star-ON value for a numeric base (no-op for unboosted stats).

        A bare add: the game does not clamp the superstar bonus (see this
        module's docstring). ``cap`` is honoured if one is ever set, but no
        superstar spec sets one.
        """
        if not self.superstar_delta:
            return base
        boosted = base + self.superstar_delta
        return min(boosted, self.cap) if self.cap is not None else boosted


_ABILITY_COLUMNS = [
    "Ball Dash", "Body Check", "Clamber", "Laser Beam", "Magical Catch",
    "Quick Throw", "Sliding Catch", "Suction", "Super Catch", "Super Jump",
    "Tongue Catch", "Wall Jump",
]


def _ability_specs() -> list[AttributeSpec]:
    return [
        AttributeSpec(col.lower().replace(" ", "_"), col, "ability", cast=_bool)
        for col in _ABILITY_COLUMNS
    ]


ATTRIBUTES: list[AttributeSpec] = [
    # identity
    AttributeSpec("char_id", "CharId", "identity"),
    AttributeSpec("name", "Character", "identity", cast=str),
    AttributeSpec("char_class", "Character Class", "identity", decode=CHARACTER_CLASS),
    AttributeSpec("is_captain", "Captain Character", "identity", cast=_bool),
    # abilities
    *_ability_specs(),
    # pitching
    AttributeSpec("weight", "Weight", "pitching"),
    AttributeSpec("curve_ball_speed", "Curve Ball Speed", "pitching", superstar_delta=20),
    AttributeSpec("fast_ball_speed", "Fast Ball Speed", "pitching", superstar_delta=20),
    AttributeSpec("curve", "Curve", "pitching", superstar_delta=50),
    AttributeSpec("cursed_ball", "Cursed Ball", "pitching", superstar_delta=50),
    AttributeSpec("curve_control", "Curve Control", "pitching", superstar_delta=50),
    AttributeSpec("pitching_height", "Pitching Height", "pitching", cast=float),
    AttributeSpec("super_curve", "Super Curve", "pitching", cast=_bool),
    # fielding
    AttributeSpec("fielding_arm", "Fielding Arm", "fielding", decode=Tables.HAND),
    AttributeSpec("throwing_power", "Throwing Power", "fielding", superstar_delta=50),
    AttributeSpec("speed", "Speed", "fielding", superstar_delta=50),
    # batting
    AttributeSpec("batting_stance", "Batting Stance", "batting", decode=Tables.HAND),
    AttributeSpec("slap_hit_power", "Slap Hit Power", "batting", superstar_delta=50),
    AttributeSpec("charge_hit_power", "Charge Hit Power", "batting", superstar_delta=50),
    AttributeSpec("bunt_contact_size", "Bunt Contact Size Multiplier", "batting",
                  superstar_delta=50),
    AttributeSpec("horizontal_hit_trajectory", "Horizontal Hit Trajectory", "batting", decode=HORIZONTAL_HIT_TRAJECTORY),
    AttributeSpec("vertical_hit_trajectory", "Vertical Hit Trajectory", "batting", decode=VERTICAL_HIT_TRAJECTORY),
    AttributeSpec("slap_contact_size_multiplier", "Slap Contact Size Multiplier", "batting", superstar_delta=50),
    AttributeSpec("charge_contact_size_multiplier", "Charge Contact Size Multiplier", "batting", superstar_delta=50),
    AttributeSpec("horizontal_range_near", "Horizontal Range Near", "batting", cast=float),
    AttributeSpec("horizontal_range_far", "Horizontal Range Far", "batting", cast=float),
    AttributeSpec("trimmed_bat", "Trimmed Bat", "batting"),
    AttributeSpec("wall_splat", "Wall Splat", "batting", cast=_bool),
    # sort keys
    AttributeSpec("css_sort", "CSS Sort", "identity"),
    AttributeSpec("char_id_sort", "Char Id Sort", "identity"),
    # star moves
    AttributeSpec("captain_star_pitch", "Captain Star Pitch", "star", decode=CAPTAIN_STAR_BALL),
    AttributeSpec("non_captain_star_pitch", "Non-Captain Star Pitch", "star", decode=NON_CAPTAIN_STAR_PITCH_TYPE),
    AttributeSpec("captain_star_hit", "Captain Star Hit", "star", decode=CAPTAIN_STAR_BALL),
    AttributeSpec("non_captain_star_hit", "Non-Captain Star Hit", "star", decode=NON_CAPTAIN_STAR_HIT),
]

ATTRIBUTES_BY_KEY = {spec.key: spec for spec in ATTRIBUTES}


# --------------------------------------------------------------------------
# CharacterAttributes: the typed per-character record
# --------------------------------------------------------------------------

@dataclass(frozen=True)
class CharacterAttributes:
    """Star-OFF (base) attributes for one character. ``with_superstar()`` returns
    the star-ON record. Fields mirror ``ATTRIBUTES`` (guarded by a test)."""

    # identity
    char_id: int
    name: str
    char_class: str
    is_captain: bool
    css_sort: int
    char_id_sort: int
    # abilities
    ball_dash: bool
    body_check: bool
    clamber: bool
    laser_beam: bool
    magical_catch: bool
    quick_throw: bool
    sliding_catch: bool
    suction: bool
    super_catch: bool
    super_jump: bool
    tongue_catch: bool
    wall_jump: bool
    # pitching
    weight: int
    curve_ball_speed: int
    fast_ball_speed: int
    curve: int
    cursed_ball: int
    curve_control: int
    pitching_height: float
    super_curve: bool
    # fielding
    fielding_arm: str
    throwing_power: int
    speed: int
    # batting
    batting_stance: str
    slap_hit_power: int
    charge_hit_power: int
    bunt_contact_size: int
    horizontal_hit_trajectory: str
    vertical_hit_trajectory: str
    slap_contact_size_multiplier: int
    charge_contact_size_multiplier: int
    horizontal_range_near: float
    horizontal_range_far: float
    trimmed_bat: int
    wall_splat: bool
    # star moves
    captain_star_pitch: str
    non_captain_star_pitch: str
    captain_star_hit: str
    non_captain_star_hit: str

    _ABILITY_KEYS: ClassVar[tuple] = tuple(
        c.lower().replace(" ", "_") for c in _ABILITY_COLUMNS
    )

    @property
    def abilities(self) -> frozenset[str]:
        """The display names of the abilities this character has."""
        return frozenset(
            col for col, key in zip(_ABILITY_COLUMNS, self._ABILITY_KEYS)
            if getattr(self, key)
        )

    def raw(self, key: str):
        """The encoded value for an attribute (reverses categorical decoding).

        e.g. ``attrs.raw("char_class")`` -> the encoded int. Numeric attributes
        are returned unchanged.
        """
        return ATTRIBUTES_BY_KEY[key].encode(getattr(self, key))

    def with_superstar(self) -> "CharacterAttributes":
        """Return the star-ON record (per-stat +delta clamped to cap)."""
        updates = {
            spec.key: spec.to_star_on(getattr(self, spec.key))
            for spec in ATTRIBUTES if spec.superstar_delta
        }
        return replace(self, **updates)


def _build(row: dict) -> CharacterAttributes:
    return CharacterAttributes(**{spec.key: spec.parse(row[spec.column]) for spec in ATTRIBUTES})


@lru_cache(maxsize=1)
def _rows() -> dict:
    """Records indexed by BOTH char id (encoded files) and name (decoded files)."""
    by_key: dict = {}
    with open(_CSV, newline="") as f:
        for row in csv.DictReader(f):
            attrs = _build(row)
            by_key[attrs.char_id] = attrs
            by_key[attrs.name] = attrs
    return by_key


def character_attributes(char) -> CharacterAttributes:
    """Base attributes for a character by encoded char id or canonical name."""
    rows = _rows()
    try:
        return rows[char]
    except KeyError:
        raise KeyError(f"No character attributes for {char!r}") from None

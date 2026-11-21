"""The game's coded values, as enums.

Every ``CodeEnum`` here mirrors one table in Project Rio's ``MSB_StatTracker.h``
(named in its docstring), and ``tests/test_canonical_parity.py`` checks each
against the header. Member names and aliases are decisions, made here; ids and
labels are upstream's. When upstream adds or renames a value, the parity test
prints the line to paste.
"""

from __future__ import annotations

from enum import Enum, Flag
from functools import cache

from ._enum import CodeEnum
from ._errors import UnknownCodeError
from ._names import NameIndex, nicknames

__all__ = [
    "AtBatResult",
    "Bases",
    "ChargeType",
    "ContactType",
    "DeadBallReason",
    "FielderAction",
    "FielderBobble",
    "Hand",
    "InputDirection",
    "ManualSelect",
    "MoonshotStatus",
    "OutType",
    "PitchResult",
    "PitchType",
    "Position",
    "PrimaryContactResult",
    "PushPull",
    "SecondaryContactResult",
    "Side",
    "Stadium",
    "StealType",
    "SwingType",
]


class Stadium(CodeEnum):
    """A stadium (``cStadiumIdToStadiumName``).

    The aliases are the names decoded stat files used before Rio settled on
    today's labels.
    """

    MARIO_STADIUM = 0, "Mario Stadium"
    BOWSER_CASTLE = 1, "Bowser Castle", "Bowser's Castle"
    WARIO_PALACE = 2, "Wario Palace", "Wario's Palace"
    YOSHI_PARK = 3, "Yoshi Park", "Yoshi's Island"
    PEACH_GARDEN = 4, "Peach Garden", "Peach's Garden"
    DK_JUNGLE = 5, "DK Jungle", "DK's Jungle"
    TOY_FIELD = 6, "Toy Field"

    @classmethod
    def parse(cls, text: str) -> Stadium:
        """The stadium a person means: ``Stadium.parse("bc")``, ``Stadium.parse("toy")``.

        Accepts labels and aliases with any spacing, punctuation or case, plus
        the shorthand in ``nicknames.toml``. Raises
        :class:`~pyrio.UnknownNameError` with suggestions on a miss.
        """
        return _stadium_names().resolve(text)


@cache
def _stadium_names() -> NameIndex[Stadium]:
    index = NameIndex[Stadium](Stadium)
    for stadium in Stadium:
        for name in (stadium.label, *stadium._aliases):  # pyright: ignore[reportPrivateUsage]
            if isinstance(name, str):
                index.add(name, stadium)
    for label, names in nicknames()["stadiums"].items():
        for name in names:
            index.add(name, Stadium(label))
    return index


class Side(Enum):
    """Which team: away (batting in the top half) or home.

    Stat files say this with a team number whose meaning flipped in Rio 1.9.2;
    the decoder applies that once, so code that holds a ``Side`` never needs to
    know which era a file came from.
    """

    AWAY = "Away"
    HOME = "Home"

    @property
    def other(self) -> Side:
        """The opposing side."""
        return Side.HOME if self is Side.AWAY else Side.AWAY

    def __str__(self) -> str:
        return self.value


class Hand(CodeEnum):
    """Handedness for batting and throwing (``cHandToHR``)."""

    RIGHT = 0, "Right"
    LEFT = 1, "Left"


class PitchType(CodeEnum):
    """The kind of pitch thrown (``cPitchTypeToHR``)."""

    CURVE = 0, "Curve"
    CHARGE = 1, "Charge"
    CHANGE_UP = 2, "ChangeUp"


class ChargeType(CodeEnum):
    """What a charge pitch turned into (``cChargePitchTypeToHR``)."""

    NONE = 0, "N/A"
    CAPTAIN_STAR = 1, "Charged Captain Star"
    SLIDER = 2, "Slider"
    PERFECT = 3, "Perfect"


class SwingType(CodeEnum):
    """The kind of swing (``cTypeOfSwing``)."""

    NONE = 0, "None"
    SLAP = 1, "Slap"
    CHARGE = 2, "Charge"
    STAR = 3, "Star"
    BUNT = 4, "Bunt"


class ContactType(CodeEnum):
    """Where the ball met the bat (``cTypeOfContactToHR``)."""

    SOUR_LEFT = 0, "Sour - Left"
    NICE_LEFT = 1, "Nice - Left"
    PERFECT = 2, "Perfect"
    NICE_RIGHT = 3, "Nice - Right"
    SOUR_RIGHT = 4, "Sour - Right"
    MISS = 0xFF, "Miss"

    @property
    def is_sour(self) -> bool:
        """A sour contact, on either side."""
        return self in (ContactType.SOUR_LEFT, ContactType.SOUR_RIGHT)

    @property
    def is_nice(self) -> bool:
        """A nice contact, on either side."""
        return self in (ContactType.NICE_LEFT, ContactType.NICE_RIGHT)


class PushPull(CodeEnum):
    """Whether the batter pushed the stick toward or away from themselves at contact.

    Upstream's ``cInputDirectionToHR``, written as ``"Input Direction - Push/Pull"``.
    """

    NONE = 0, "None"
    TOWARDS_BATTER = 1, "Towards Batter"
    AWAY_FROM_BATTER = 2, "Away From Batter"


class MoonshotStatus(CodeEnum):
    """Whether a swing was a moonshot (``cMoonShotStatus``).

    ``FAILED`` is a moonshot attempt without perfect contact. The game never
    records it; the stat tracker infers it from the attempt's conditions.
    """

    NONE = 0, "None"
    MOONSHOT = 1, "Moonshot"
    FAILED = 2, "Failed Moonshot"


class Position(CodeEnum):
    """A fielding position (``cPosition``).

    Upstream's ``0xFF`` ("Inv") means no position, which pyrio reads as
    ``None``, so there's no member for it.
    """

    PITCHER = 0, "P"
    CATCHER = 1, "C"
    FIRST_BASE = 2, "1B"
    SECOND_BASE = 3, "2B"
    THIRD_BASE = 4, "3B"
    SHORTSTOP = 5, "SS"
    LEFT_FIELD = 6, "LF"
    CENTER_FIELD = 7, "CF"
    RIGHT_FIELD = 8, "RF"


class FielderAction(CodeEnum):
    """A move the fielder made going for the ball (``cFielderActions``)."""

    NONE = 0, "None"
    SLIDING = 2, "Sliding"
    WALL_JUMP = 3, "Walljump"


class FielderBobble(CodeEnum):
    """How a fielder failed to hold the ball (``cFielderBobbles``)."""

    NONE = 0, "None", 0xFF
    SLIDE_STUN_LOCK = 1, "Slide/stun lock"
    FUMBLE = 2, "Fumble"
    BOBBLE = 3, "Bobble"
    FIREBALL = 4, "Fireball"
    GARLIC_KNOCKOUT = 0x10, "Garlic knockout"


class StealType(CodeEnum):
    """How a runner left the base (``cStealType``)."""

    NONE = 0, "None", 0xFF
    READY = 1, "Ready"
    NORMAL = 2, "Normal"
    PERFECT = 3, "Perfect"


class OutType(CodeEnum):
    """How an out was made (``cOutType``)."""

    NONE = 0, "None"
    CAUGHT = 1, "Caught"
    FORCE = 2, "Force"
    TAG = 3, "Tag"
    FORCE_BACK = 4, "Force Back"
    STRIKEOUT = 0x10, "Strike-out"


class PitchResult(CodeEnum):
    """What a single pitch came to (``cPitchResult``)."""

    HIT_BY_PITCH = 0, "HBP"
    WALK = 1, "BB"
    BALL = 2, "Ball"
    STRIKE_LOOKING = 3, "Strike-looking"
    STRIKE_SWINGING = 4, "Strike-swing"
    STRIKE_BUNTING = 5, "Strike-bunting"
    CONTACT = 6, "Contact"
    UNKNOWN = 7, "Unknown"


class PrimaryContactResult(CodeEnum):
    """The broad result of a batted ball (``cPrimaryContactResult``)."""

    OUT = 0, "Out"
    FOUL = 1, "Foul"
    FAIR = 2, "Fair"
    FIELDED = 3, "Fielded"
    UNKNOWN = 4, "Unknown"


class SecondaryContactResult(CodeEnum):
    """The detailed result of a batted ball (``cSecondaryContactResult``).

    ``BATTER_SAFE_THROW_ELSEWHERE`` (0xC) is pyrio's label pending upstream
    (ProjectRio/ProjectRio#170): it's set when a throw could have retired a
    runner but none was put out. Rio 2.2.0 called it "Error - Chem" and 2.3.0
    "Fielders Choice", and both still resolve to it. There's no 0x10: the
    secondary result is only copied up to the double play, so "Foul catch"
    can't occur here (it does in :class:`AtBatResult`).
    """

    OUT_CAUGHT = 0, "Out-caught"
    OUT_FORCE = 1, "Out-force"
    OUT_TAG = 2, "Out-tag"
    FOUL = 3, "Foul"
    BATTER_SAFE_RUNNER_OUT = 4, "Batter safe, runner out"
    SINGLE = 7, "Single"
    DOUBLE = 8, "Double"
    TRIPLE = 9, "Triple"
    HOME_RUN = 0xA, "HR"
    ERROR = 0xB, "Error", "Error - Input"
    BATTER_SAFE_THROW_ELSEWHERE = (
        0xC,
        "Batter safe, throw elsewhere",
        "Error - Chem",
        "Fielders Choice",
    )
    BUNT = 0xD, "Bunt"
    SACRIFICE_FLY = 0xE, "SacFly"
    DOUBLE_PLAY = 0xF, "Ground ball double Play"
    NONE = 0xFF, "None"


class AtBatResult(CodeEnum):
    """How an at-bat ended (``cAtBatResult``).

    ``CAUGHT_LINE_DRIVE`` (5) and ``CAUGHT`` (6) are not interchangeable: the
    game assigns 5 to a flat, low-apex catch (vertical angle at most 160) and 6
    above it. Decoded files from Rio 2.2.0 and earlier carry these two labels
    the other way round, which the decoder corrects using the file's version.
    For 0xC see :class:`SecondaryContactResult`.
    """

    NONE = 0, "None"
    STRIKEOUT = 1, "Strikeout"
    WALK = 2, "Walk (BB)"
    HIT_BY_PITCH = 3, "Walk (HBP)"
    OUT = 4, "Out"
    CAUGHT_LINE_DRIVE = 5, "Caught line-drive"
    CAUGHT = 6, "Caught"
    SINGLE = 7, "Single"
    DOUBLE = 8, "Double"
    TRIPLE = 9, "Triple"
    HOME_RUN = 0xA, "HR"
    ERROR = 0xB, "Error", "Error - Input"
    BATTER_SAFE_THROW_ELSEWHERE = (
        0xC,
        "Batter safe, throw elsewhere",
        "Error - Chem",
        "Fielders Choice",
    )
    BUNT = 0xD, "Bunt"
    SACRIFICE_FLY = 0xE, "SacFly"
    DOUBLE_PLAY = 0xF, "Ground ball double Play"
    FOUL_CATCH = 0x10, "Foul catch"

    @property
    def is_hit(self) -> bool:
        """A single, double, triple or home run."""
        return self.bases > 0

    @property
    def bases(self) -> int:
        """Bases the hit was worth: 1 for a single up to 4 for a home run, else 0."""
        return _HIT_BASES.get(self, 0)

    @property
    def is_walk(self) -> bool:
        """A walk, either on balls or hit by pitch."""
        return self in (AtBatResult.WALK, AtBatResult.HIT_BY_PITCH)

    @property
    def is_out(self) -> bool:
        """The batter was put out: strikeout, out, a catch, sacrifice fly or double play."""
        return self in _OUTS


_HIT_BASES = {
    AtBatResult.SINGLE: 1,
    AtBatResult.DOUBLE: 2,
    AtBatResult.TRIPLE: 3,
    AtBatResult.HOME_RUN: 4,
}
_OUTS = frozenset(
    {
        AtBatResult.STRIKEOUT,
        AtBatResult.OUT,
        AtBatResult.CAUGHT_LINE_DRIVE,
        AtBatResult.CAUGHT,
        AtBatResult.SACRIFICE_FLY,
        AtBatResult.DOUBLE_PLAY,
        AtBatResult.FOUL_CATCH,
    }
)


class ManualSelect(CodeEnum):
    """Which fielder the player took manual control of (``cManualSelectDecode``)."""

    NONE = 0, "No Selected Char"
    PITCHER = 1, "Pitcher"
    CATCHER = 2, "Catcher"
    CLOSEST_TO_BALL = 3, "Closest to Ball"
    CLOSEST_TO_DROP = 4, "Closest to Drop"


class DeadBallReason(CodeEnum):
    """Why the ball was dead (``cDeadBallReason``)."""

    NONE = 0, "N/A"
    HOME_RUN = 1, "Home Run"
    FOUL_BALL = 2, "Foul Ball"
    GROUND_RULE_DOUBLE = 3, "Ground Rule Double"
    BALL_DEAD = 4, "Ball Dead"


class Bases(Flag):
    """Which bases are occupied: ``Bases.FIRST | Bases.THIRD``.

    ``str()`` gives the positional form, ``"1-3"``, or ``"---"`` when empty.
    """

    FIRST = 1
    SECOND = 2
    THIRD = 4

    def __str__(self) -> str:
        return "".join(
            digit if base in self else "-"
            for digit, base in (("1", Bases.FIRST), ("2", Bases.SECOND), ("3", Bases.THIRD))
        )


class InputDirection(Flag):
    """The stick directions held at contact, a bitmask: ``InputDirection.LEFT | InputDirection.UP``.

    Decoded stat files spell it ``"Left+Up"``, with ``""`` for none. Both forms
    look up: ``InputDirection(9)`` and ``InputDirection("Left+Up")``.
    """

    LEFT = 1
    RIGHT = 2
    DOWN = 4
    UP = 8

    @property
    def label(self) -> str:
        """The decoded stat-file spelling, such as ``"Left+Up"``."""
        return "+".join(member.name.capitalize() for member in self if member.name)

    def __str__(self) -> str:
        return self.label

    @classmethod
    def _missing_(cls, value: object) -> InputDirection:
        if isinstance(value, str):
            result = cls(0)
            for word in filter(None, value.split("+")):
                member = cls.__members__.get(word.strip().upper())
                if member is None:
                    raise UnknownCodeError(cls, value)
                result |= member
            return result
        if isinstance(value, int) and not isinstance(value, bool) and 0 <= value <= 0xF:
            return super()._missing_(value)
        raise UnknownCodeError(cls, value)

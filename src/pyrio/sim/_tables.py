"""The batting tables the hit simulation reads, from the game's data.

Ported from the batting calculator's ``index.js``, which took them from the
game. Each table is named for what it holds; the game's address or symbol is in
the comment above it, for cross-reference with the decomp. Indices noted as
``[a][b]`` are the order to index in.

Index names used below:

* swing: 0 slap, 1 charge, 2 star, 3 bunt (the game's general swing type)
* contact: 0 left sour, 1 left nice, 2 perfect, 3 right nice, 4 right sour
  (``ContactType`` ids)
* easy: 0 normal batting, 1 easy batting
* stick: 0 none, 1 pull (toward the batter), 2 push (``PushPull`` ids)
* hit type: 0-17, sour/nice/perfect for each of slap, charge, change-up slap,
  change-up charge, perfect-pitch slap and perfect-pitch charge
"""

from __future__ import annotations

from typing import Final

DEFAULT_SEEDS: Final = (7769, 5359, 1828)
"""The calculator's RNG values when none are given (StaticRandomInt1/2, 0x8089269c)."""

MOONSHOT_POWER_MULTIPLIER: Final = 1.5
"""Power multiplier for a connected moonshot (``g_hitFloats.moonshotMult``)."""

# Chemistry with runners on base, indexed by links (0-3).
CHEM_CONTACT_SIZE_MULTIPLIERS: Final = (1.0, 1.05, 1.1, 1.2)  # contact_ChemLinkMultipliers
CHEM_POWER_MULTIPLIERS: Final = (1.0, 1.1, 1.25, 1.5)  # RandomBattingFactors_ChemLinkMult0

HIT_TYPE_UNSET_ROW: Final = (0x3F828F5C, 0x3F866666, 0x3F800000, 0x3F733333, 0x3F59999A)
"""What the game reads as the hit-type row of a star swing.

A star swing leaves the hit type unset at -1, and the game then reads the 20
bytes before ``HIT_TYPE_EFFECTS`` (0x807b7120): the tail of a float table
reinterpreted as integers. Only the vertical-zone mask matters (0x3f733333): its
0x3000000 bits force the pop-fly zone, the Texas Leaguer of a failed moonshot.
Modelled explicitly, since Python's ``table[-1]`` would wrap to the last row.
"""

REMOVE_SLICE_ANGLES: Final[dict[tuple[int, int, int], tuple[int, int]]] = {
    (0, 1, 2): (-600, -600),
    (0, 1, 10): (600, 600),
    (1, 1, 2): (-600, -600),
    (1, 1, 10): (700, 700),
    (2, 1, 2): (-550, -550),
    (2, 1, 10): (650, 650),
    (2, 0, 10): (700, 700),
}
"""The "Remove slice" mod's horizontal angle ranges, ``[(stick, is_charge, frame)]``.

The game leaves these cells of ``HORIZONTAL_ANGLE_RANGES`` as (0, 0), which sends
an early or late contact dead up the middle (the "slice"). The mod gives them
the extreme pull and push ranges, so the ball goes foul. Each range has zero
span, so no random draw changes it.
"""

# Captain star swings (``CaptainStar`` ids) with an effect on the flight.
BANANA_CAPTAIN_STARS: Final = frozenset({5, 6})  # DK, Diddy
BULLET_CAPTAIN_STARS: Final = frozenset({7, 8})  # Bowser, Bowser Jr
GARLIC_CAPTAIN_STARS: Final = frozenset({3, 4})  # Wario, Waluigi

BANANA_TURN_RAD_PER_FRAME: Final = 0.008
"""How far the banana ball's heading turns each frame (``DKStarAngleDelta``)."""

BANANA_START_FRACTION: Final = 0.25
BANANA_END_FRACTION: Final = 0.95
"""The banana curve runs from this fraction of the straight flight's hang time to that."""

BULLET_ENERGY_MULTIPLIER: Final = 4.0
"""Ball energy of a bullet star swing, as a multiple of its power."""

GARLIC_SPLIT_FRAMES_BEFORE_GROUND: Final = 120
"""The garlic ball splits this many frames before the straight flight would land."""

GARLIC_SPREAD_RAD: Final = (0.2, 0.3)
"""Each garlic ball's heading turns by a random amount in this range."""

# Contact thresholds, [bat][swing][easy] -> four base values, then the four
# values a full contact size moves them to: left nice, left perfect, right
# perfect, right nice. ``bat`` is 0, or 1 for a trimmed bat.
# BallContactArray_807b6294
CONTACT_THRESHOLDS: Final[tuple[tuple[tuple[tuple[int, ...], ...], ...], ...]] = (
    (
        ((50, 98, 106, 150, 30, 95, 109, 170), (40, 98, 106, 160, 20, 95, 109, 180)),
        ((60, 99, 101, 150, 40, 97, 103, 170), (55, 99, 101, 160, 35, 97, 103, 180)),
        ((50, 99, 101, 140, 40, 97, 103, 160), (45, 99, 101, 145, 35, 97, 103, 165)),
        ((80, 98, 102, 120, 35, 95, 105, 165), (80, 98, 102, 110, 35, 95, 105, 165)),
        ((0, 0, 0, 0, 0, 0, 0, 0), (0, 0, 0, 0, 0, 0, 0, 0)),
    ),
    (
        ((40, 96, 104, 150, 30, 93, 107, 170), (30, 96, 104, 170, 20, 93, 107, 180)),
        ((60, 96, 104, 140, 35, 93, 107, 170), (50, 96, 104, 150, 25, 93, 107, 180)),
        ((60, 99, 101, 140, 40, 97, 103, 160), (40, 99, 101, 160, 30, 97, 103, 170)),
        ((90, 98, 102, 110, 75, 95, 105, 125), (90, 98, 102, 110, 75, 95, 105, 125)),
        ((0, 0, 0, 0, 0, 0, 0, 0), (0, 0, 0, 0, 0, 0, 0, 0)),
    ),
)

# Per hit type: power percent (easy, normal), vertical-zone masks (easy,
# normal), and the zone a forced hit takes. UINT_ARRAY_ARRAY_807b7134
HIT_TYPE_EFFECTS: Final[tuple[tuple[int, ...], ...]] = (
    (100, 100, 0x00111110, 0x00111110, 0),
    (100, 100, 0x00111110, 0x00111110, 2),
    (101, 102, 0x00111110, 0x00111110, 1),
    (90, 90, 0x00111110, 0x00111110, 0),
    (94, 95, 0x00111110, 0x00111110, 0),
    (102, 103, 0x00111110, 0x00111110, 1),
    (90, 90, 0x00111110, 0x01100000, 0),
    (85, 90, 0x00111110, 0x00111110, 0),
    (102, 103, 0x00111110, 0x00111110, 1),
    (100, 100, 0x00111110, 0x00111110, 0),
    (95, 100, 0x00111110, 0x00111110, 2),
    (104, 105, 0x00111110, 0x00111110, 1),
    (60, 60, 0x00111110, 0x00111110, 0),
    (70, 75, 0x00111110, 0x00111110, 0),
    (87, 90, 0x00111110, 0x00111110, 1),
    (70, 70, 0x00111110, 0x00111110, 0),
    (80, 85, 0x00111110, 0x00111110, 0),
    (105, 110, 0x00111110, 0x00111110, 1),
    (50, 50, 0x00110110, 0x00110110, 0),
)

# Horizontal angle range, [stick][is_charge][contact frame] -> (low, high), raw
# angle units offset from straight ahead. BattingAngleRanges
HORIZONTAL_ANGLE_RANGES: Final[tuple[tuple[tuple[tuple[int, ...], ...], ...], ...]] = (
    (
        (
            (0, 0),
            (0, 0),
            (-700, -500),
            (-500, -350),
            (-400, -250),
            (-350, -100),
            (-150, 250),
            (200, 300),
            (250, 400),
            (350, 550),
            (550, 700),
            (0, 0),
            (0, 0),
            (0, 0),
            (0, 0),
        ),
        (
            (0, 0),
            (0, 0),
            (0, 0),
            (-600, -400),
            (-400, -200),
            (-300, -100),
            (-200, 200),
            (100, 400),
            (300, 450),
            (350, 600),
            (0, 0),
            (0, 0),
            (0, 0),
            (0, 0),
            (0, 0),
        ),
    ),
    (
        (
            (0, 0),
            (0, 0),
            (-750, -500),
            (-500, -300),
            (-300, -150),
            (-150, 200),
            (200, 400),
            (300, 450),
            (400, 600),
            (500, 600),
            (600, 700),
            (0, 0),
            (0, 0),
            (0, 0),
            (0, 0),
        ),
        (
            (0, 0),
            (0, 0),
            (0, 0),
            (-600, -400),
            (-400, -200),
            (-300, 100),
            (100, 400),
            (100, 400),
            (200, 500),
            (500, 700),
            (0, 0),
            (0, 0),
            (0, 0),
            (0, 0),
            (0, 0),
        ),
    ),
    (
        (
            (0, 0),
            (0, 0),
            (-700, -600),
            (-600, -400),
            (-450, -350),
            (-400, -300),
            (-350, -200),
            (-200, 150),
            (150, 300),
            (300, 700),
            (0, 0),
            (0, 0),
            (0, 0),
            (0, 0),
            (0, 0),
        ),
        (
            (0, 0),
            (0, 0),
            (0, 0),
            (-550, -300),
            (-400, -200),
            (-300, -100),
            (-300, -100),
            (-100, 200),
            (200, 450),
            (450, 650),
            (0, 0),
            (0, 0),
            (0, 0),
            (0, 0),
            (0, 0),
        ),
    ),
)

# Weights of the five vertical zones, [vertical trajectory][is_charge][easy]
# [contact]. The trajectory is ``VerticalHitTrajectory``'s id.
# BattingVerticalAngleWeights
VERTICAL_ZONE_WEIGHTS: Final[tuple[tuple[tuple[tuple[tuple[int, ...], ...], ...], ...], ...]] = (
    (
        (
            (
                (0, 10, 20, 30, 40),
                (20, 20, 20, 20, 20),
                (10, 25, 30, 25, 10),
                (20, 20, 20, 20, 20),
                (40, 30, 20, 10, 0),
            ),
            (
                (0, 10, 20, 30, 40),
                (20, 20, 20, 20, 20),
                (10, 25, 30, 25, 10),
                (20, 20, 20, 20, 20),
                (40, 30, 20, 10, 0),
            ),
        ),
        (
            (
                (10, 0, 20, 30, 40),
                (20, 22, 22, 28, 8),
                (20, 25, 25, 25, 5),
                (20, 22, 22, 28, 8),
                (10, 0, 20, 30, 40),
            ),
            (
                (10, 0, 20, 30, 40),
                (20, 22, 22, 28, 8),
                (20, 25, 25, 25, 5),
                (20, 22, 22, 28, 8),
                (10, 0, 20, 30, 40),
            ),
        ),
    ),
    (
        (
            (
                (0, 10, 20, 30, 40),
                (5, 5, 15, 40, 35),
                (5, 5, 20, 40, 35),
                (5, 5, 15, 40, 35),
                (40, 30, 20, 10, 0),
            ),
            (
                (0, 10, 20, 30, 40),
                (5, 5, 15, 40, 35),
                (5, 5, 20, 40, 35),
                (5, 5, 15, 40, 35),
                (40, 30, 20, 10, 0),
            ),
        ),
        (
            (
                (5, 0, 10, 40, 45),
                (5, 21, 12, 29, 33),
                (5, 23, 15, 27, 30),
                (5, 21, 12, 29, 33),
                (5, 0, 10, 40, 45),
            ),
            (
                (5, 0, 10, 40, 45),
                (5, 21, 12, 29, 33),
                (5, 23, 15, 27, 30),
                (5, 21, 12, 29, 33),
                (5, 0, 10, 40, 45),
            ),
        ),
    ),
    (
        (
            (
                (10, 20, 20, 20, 30),
                (35, 40, 15, 5, 5),
                (30, 40, 20, 5, 5),
                (35, 40, 15, 5, 5),
                (40, 30, 20, 5, 5),
            ),
            (
                (10, 20, 20, 20, 30),
                (35, 40, 15, 5, 5),
                (30, 40, 20, 5, 5),
                (35, 40, 15, 5, 5),
                (40, 30, 20, 5, 5),
            ),
        ),
        (
            (
                (10, 0, 20, 30, 40),
                (35, 30, 22, 10, 3),
                (30, 30, 25, 15, 0),
                (35, 30, 22, 10, 3),
                (10, 0, 20, 30, 40),
            ),
            (
                (10, 0, 20, 30, 40),
                (35, 30, 22, 10, 3),
                (30, 30, 25, 15, 0),
                (35, 30, 22, 10, 3),
                (10, 0, 20, 30, 40),
            ),
        ),
    ),
)

# Vertical angle range of each zone, [is_charge][contact][zone] -> (low, high).
# SHORT_ARRAY_ARRAY_ARRAY_ARRAY_807b67cc
VERTICAL_ZONE_ANGLES: Final[tuple[tuple[tuple[tuple[int, ...], ...], ...], ...]] = (
    (
        ((-50, 50), (50, 100), (100, 300), (300, 400), (400, 500)),
        ((50, 150), (150, 200), (200, 250), (250, 300), (300, 350)),
        ((50, 150), (150, 200), (150, 200), (200, 300), (300, 350)),
        ((50, 150), (150, 200), (200, 250), (250, 300), (300, 350)),
        ((-50, 50), (50, 100), (100, 300), (300, 400), (400, 500)),
    ),
    (
        ((400, 450), (450, 500), (500, 550), (550, 600), (550, 600)),
        ((50, 100), (100, 150), (300, 400), (350, 450), (400, 500)),
        ((100, 200), (350, 400), (450, 500), (500, 550), (530, 580)),
        ((50, 100), (100, 150), (300, 400), (350, 450), (400, 500)),
        ((400, 450), (450, 500), (500, 550), (550, 600), (550, 600)),
    ),
)

# Vertical angle range of a hit type that forces its zone, [forced zone].
# SHORT_ARRAY_ARRAY_807b6af4
FORCED_VERTICAL_ANGLES: Final[tuple[tuple[int, ...], ...]] = ((0, 0), (500, 550), (500, 550))

# Vertical angle range of a non-captain star swing, [StarSwing id - 1][contact].
# NonCaptainStarSwingBattingVerticalAngleRanges
STAR_SWING_VERTICAL_ANGLES: Final[tuple[tuple[tuple[int, ...], ...], ...]] = (
    ((250, 300), (300, 350), (350, 400), (400, 450), (450, 500)),
    ((50, 100), (50, 100), (50, 100), (50, 100), (50, 100)),
    ((120, 160), (160, 200), (160, 200), (160, 200), (120, 160)),
)

# Vertical angle range of a captain star swing, [CaptainStar id - 1][contact].
# CaptainStarSwingBattingVerticalAngleRanges
CAPTAIN_STAR_VERTICAL_ANGLES: Final[tuple[tuple[tuple[int, ...], ...], ...]] = (
    ((59, 61), (59, 61), (59, 61), (59, 61), (59, 61)),
    ((-101, -99), (-101, -99), (-101, -99), (-101, -99), (-101, -99)),
    ((350, 400), (350, 400), (350, 400), (350, 400), (350, 400)),
    ((450, 500), (450, 500), (450, 500), (450, 500), (450, 500)),
    ((120, 160), (160, 200), (160, 200), (160, 200), (120, 160)),
    ((250, 300), (250, 300), (250, 300), (250, 300), (250, 300)),
    ((64, 80), (64, 80), (64, 80), (64, 80), (64, 80)),
    ((64, 80), (64, 80), (64, 80), (64, 80), (64, 80)),
    ((350, 400), (350, 400), (350, 400), (350, 400), (350, 400)),
    ((200, 250), (200, 250), (200, 250), (200, 250), (200, 250)),
    ((350, 600), (350, 600), (350, 600), (350, 600), (350, 600)),
    ((350, 600), (350, 600), (350, 600), (350, 600), (350, 600)),
)

# Exit speed range and added gravity, [swing][contact] -> (low, high, gravity
# in 1e-5 units). Rows 4 and 5 are unused by slap, charge and star. BallHitArray
EXIT_VELOCITIES: Final[tuple[tuple[tuple[int, ...], ...], ...]] = (
    ((100, 130, -110), (140, 145, -100), (145, 150, -110), (140, 145, -100), (100, 130, -110)),
    ((140, 150, -120), (162, 177, -160), (160, 170, 0), (162, 177, -160), (140, 150, -120)),
    ((120, 130, -200), (140, 150, -200), (160, 170, -200), (140, 150, -200), (120, 130, -200)),
    ((150, 160, -300), (170, 190, -300), (190, 200, -300), (170, 190, -300), (150, 160, -300)),
    ((130, 140, -200), (145, 155, -300), (160, 170, -300), (145, 155, -300), (130, 140, -200)),
    ((140, 150, -150), (190, 200, -200), (200, 210, -180), (190, 200, -200), (140, 150, -150)),
)

# The same for a non-captain star swing, [StarSwing id - 1][contact].
# StarSwingExitVelocityArray
STAR_SWING_EXIT_VELOCITIES: Final[tuple[tuple[tuple[int, ...], ...], ...]] = (
    ((150, 160, -150), (160, 170, -150), (170, 180, -100), (160, 170, -150), (150, 160, -150)),
    ((150, 160, -250), (160, 170, -250), (170, 180, -250), (160, 170, -250), (150, 160, -250)),
    ((170, 180, -300), (170, 180, -300), (190, 200, -300), (170, 180, -300), (170, 180, -300)),
)

# The same for a captain star swing, [CaptainStar id - 1][contact].
# CaptainStarSwingExitVelocityArray
CAPTAIN_STAR_EXIT_VELOCITIES: Final[tuple[tuple[tuple[int, ...], ...], ...]] = (
    ((140, 150, 0), (150, 160, 150), (160, 170, 150), (150, 160, 150), (140, 150, 0)),
    ((120, 130, 0), (130, 150, 50), (160, 170, 100), (130, 150, 50), (120, 130, 0)),
    ((90, 100, 80), (100, 110, 80), (110, 120, 80), (100, 110, 80), (90, 100, 80)),
    ((60, 70, 80), (70, 80, 80), (70, 80, 80), (70, 80, 80), (60, 70, 80)),
    ((170, 180, -120), (170, 180, -130), (190, 200, -125), (170, 180, -135), (170, 180, -125)),
    ((150, 160, -140), (150, 160, -150), (160, 170, -150), (150, 160, -150), (150, 160, -140)),
    ((170, 180, 0), (170, 180, 0), (190, 200, 0), (170, 180, 0), (170, 180, 0)),
    ((160, 170, 0), (160, 170, 0), (180, 190, 0), (160, 170, 0), (160, 170, 0)),
    ((90, 130, -650), (90, 130, -650), (90, 130, -650), (90, 130, -650), (90, 130, -650)),
    ((140, 160, -400), (140, 160, -400), (140, 160, -400), (140, 160, -400), (140, 160, -400)),
    ((130, 140, -100), (140, 150, -100), (150, 160, -100), (140, 150, -100), (130, 140, -100)),
    ((130, 140, -100), (140, 150, -100), (150, 160, -100), (140, 150, -100), (130, 140, -100)),
)

# How far the pitcher's cursed ball scales power down, [perfect/nice/sour] ->
# (at 0 cursed ball, at 100). FLOAT_ARRAY_ARRAY_807b7480
CURSED_BALL_POWER_SCALE: Final[tuple[tuple[float, ...], ...]] = ((1.0, 1.0), (1.0, 0.8), (1.0, 0.5))

# The pitcher's cursed ball as the pitch uses it (adjustPitchCurveSpeedCursedBall,
# lbl_3_data_5EDC[3] and [8] read as s16): a pitcher below this stamina is
# tired, and a tired pitcher's cursed ball loses this percentage, all of it.
# A captain star pitch's cursed ball is 100. A charge pitch or change-up
# scales it by lbl_3_data_5F08[8], which is 1.0, so not at all.
TIRED_PITCHER_STAMINA: Final = 4
TIRED_CURSED_BALL_LOSS_PERCENT: Final = 100
STAR_PITCH_CURSED_BALL: Final = 100

# Power bonus across the field, [HorizontalHitTrajectory id][segment], five
# points interpolated across four segments. FieldTrajectories
FIELD_POWER_BONUS: Final[tuple[tuple[float, ...], ...]] = (
    (1.0, 1.0, 1.0, 1.0, 1.0),
    (0.85, 0.95, 1.0, 1.05, 1.02),
    (1.02, 1.05, 1.0, 0.95, 0.85),
)

# Sideways curve on a hit, [has super curve] -> (base, x acceleration,
# z acceleration). FLOAT_ARRAY_ARRAY_807b72bc
CURVE_FACTORS: Final[tuple[tuple[float, ...], ...]] = ((0.5, 0.001, 0.003), (0.25, 0.006, 0.008))

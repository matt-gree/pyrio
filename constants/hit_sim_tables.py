"""Character-independent lookup tables and enums for the hit simulator.

These are ported verbatim from the batting calculator's index.js. Identifiers
(including the raw-memory-address names like ``BallContactArray_807b6294``) are
kept exactly as in the JS so the pipeline in ``hit_simulation.py`` reads 1:1
against the source and stays easy to diff/verify. If the JS tables ever change,
update them here in lockstep.

This module holds only constants -- no logic. Per-character data
(hit power, contact size, trajectories, horizontal range, trimmed bat, pitching
height) lives in ``constants/character_attributes.csv`` and is joined by
character NAME, never by the JS numeric char id (which does not match the real
game -- e.g. Koopa(R)/(G) are swapped).
"""

# --- Contact type enum (Batter_ContactType) ---
LeftSour = 0
LeftNice = 1
Perfect = 2
RightNice = 3
RightSour = 4

# --- Batter handedness (AtBat_BatterHand) ---
Righty = 0
Lefty = 1

# --- Swing kind (Batter_Contact_SlapChargeBuntStar) ---
Slap = 0
Charge = 1
Star = 2
Bunt = 3

# --- Hit type (Batter_HitType) ---
SourSlap = 0x0
NiceSlap = 0x1
PerfectSlap = 0x2
SourCharge = 0x3
NiceCharge = 0x4
PerfectCharge = 0x5
SourChangeUpSlap = 0x6
NiceChangeUpSlap = 0x7
PerfectChangeUpSlap = 0x8
SourChangeUpCharge = 0x9
NiceChangeUpCharge = 0xA
PerfectChangeUpCharge = 0xB
PerfectPitchSourSlap = 0xC
PerfectPitchNiceSlap = 0xD
PerfectPitchPerfectSlap = 0xE
PerfectPitchSourCharge = 0xF
PerfectPitchNiceCharge = 0x10
PerfectPitchPerfectCharge = 0x11

# --- Pitch type (Pitcher_TypeOfPitch) ---
PitchCurve = 0
PitchCharge = 1
PitchChangeUp = 2

# --- Charge pitch type (ChargePitchType) ---
PitchChargeType_None = 0
PitchChargeType_ChargedStar = 1   # a charged star pitch that never resolved to Slider/Perfect
PitchChargeType_Charge = 2        # Slider
PitchChargeType_Perfect = 3

# --- Stick input direction (AtBat_InputDirection) ---
PushPullNone = 0
PullStickTowardsHitting = 1
PushStickAway = 2

# Default RNG seeds used by the JS when none are supplied (each <= 32767).
# Real simulations should pass the event's RNG1/RNG2/RNG3 instead.
DEFAULT_STATIC_RANDOM_INT1 = 7769
DEFAULT_STATIC_RANDOM_INT2 = 5359
DEFAULT_USHORT_8089269c = 1828

# Trajectory integration constants (calculateHitGround).
AIR_RESISTANCE = 0.996
GRAVITY = 0.00275

# Ground-plane Y used for landing/bounce detection in liveBallHitPhysics
# (const_0.15(/0.35ToyField)GroundYForBounces). The ball is treated as having
# reached the ground when its Y drops below this; Toy Field sits higher.
GROUND_Y_DEFAULT = 0.15
GROUND_Y_TOY_FIELD = 0.35

# Stadiums where liveBallHitPhysics applies the blanket flat-ground bounce
# (clamp Y to the ground plane, reverse a downward Y velocity). Bowser Castle
# (0x1) and Toy Field (0x6) are excluded because their ground plane has HOLES, so
# a uniform "clamp + bounce up everywhere" would be wrong -- their real,
# geometry-aware ground/wall collisions are resolved by ballCollisionLogic (not
# ported here). Keyed by encoded StadiumID. Decoded from the JS gating
# `StadiumID == Mario || (byte)(StadiumID + ~BowserCastle) < 3 || StadiumID == DKJungle`.
BOUNCING_STADIUM_IDS = frozenset({0x0, 0x2, 0x3, 0x4, 0x5})  # Mario, Wario, Yoshi, Peach, DK

# --- Contact threshold base values, indexed [trimmedBat][slapChargeStarBunt][easyBatting] ---
# Each leaf is [b0, b1, b2, b3, leftNice, leftPerfect, rightPerfect, rightNice].
BallContactArray_807b6294 = [[[[50, 98, 106, 150, 30, 95, 109, 170], [40, 98, 106, 160, 20, 95, 109, 180]], [[60, 99, 101, 150, 40, 97, 103, 170], [55, 99, 101, 160, 35, 97, 103, 180]], [[50, 99, 101, 140, 40, 97, 103, 160], [45, 99, 101, 145, 35, 97, 103, 165]], [[80, 98, 102, 120, 35, 95, 105, 165], [80, 98, 102, 110, 35, 95, 105, 165]], [[0, 0, 0, 0, 0, 0, 0, 0], [0, 0, 0, 0, 0, 0, 0, 0]]], [[[40, 96, 104, 150, 30, 93, 107, 170], [30, 96, 104, 170, 20, 93, 107, 180]], [[60, 96, 104, 140, 35, 93, 107, 170], [50, 96, 104, 150, 25, 93, 107, 180]], [[60, 99, 101, 140, 40, 97, 103, 160], [40, 99, 101, 160, 30, 97, 103, 170]], [[90, 98, 102, 110, 75, 95, 105, 125], [90, 98, 102, 110, 75, 95, 105, 125]], [[0, 0, 0, 0, 0, 0, 0, 0], [0, 0, 0, 0, 0, 0, 0, 0]]]]

# Per hit-type flags, indexed [Batter_HitType]: [v0, v1, mask3, mask4, idx5].
UINT_ARRAY_ARRAY_807b7134 = [[100, 100, 0x00111110, 0x00111110, 0], [100, 100, 0x00111110, 0x00111110, 2], [101, 102, 0x00111110, 0x00111110, 1], [90, 90, 0x00111110, 0x00111110, 0], [94, 95, 0x00111110, 0x00111110, 0], [102, 103, 0x00111110, 0x00111110, 1], [90, 90, 0x00111110, 0x01100000, 0], [85, 90, 0x00111110, 0x00111110, 0], [102, 103, 0x00111110, 0x00111110, 1], [100, 100, 0x00111110, 0x00111110, 0], [95, 100, 0x00111110, 0x00111110, 2], [104, 105, 0x00111110, 0x00111110, 1], [60, 60, 0x00111110, 0x00111110, 0], [70, 75, 0x00111110, 0x00111110, 0], [87, 90, 0x00111110, 0x00111110, 1], [70, 70, 0x00111110, 0x00111110, 0], [80, 85, 0x00111110, 0x00111110, 0], [105, 110, 0x00111110, 0x00111110, 1], [50, 50, 0x00110110, 0x00110110, 0]]

# A Star swing leaves Batter_HitType unset at -1 (0xff) -- the contact code only
# assigns it for Slap/Charge. The game then reads UINT_ARRAY_ARRAY_807b7134[-1],
# which is out of bounds: it picks up the 20 bytes *before* the table (0x807b7120),
# the tail of a float table ([1.02, 1.05, 1.0, 0.95, 0.85]) reinterpreted as a uint
# row. Only mask3 (u4 = 0x3f733333) matters downstream -- its 0x3000000 bits force
# i_var5 = 1 (the pop-fly vertical zone -> the Texas Leaguer of a failed Moonshot).
# Modeled explicitly because Python's table[-1] would wrap to the last valid row.
UINT_ARRAY_807b7120_HITTYPE_UNSET = [0x3f828f5c, 0x3f866666, 0x3f800000, 0x3f733333, 0x3f59999a]

# "Most perfect" contact window per swing kind: [lowerBound, upperBound, _].
ContactPerfectThresholds = [[99.1, 100.9, 100.5], [99.7, 100.3, 1.1], [99.7, 100.3, 1.0]]

# Contact-size multiplier by chem links on base (slap, non-charge).
contact_ChemLinkMultipliers = [1.0, 1.05, 1.1, 1.2]

# Power multiplier by chem links on base (charge).
RandomBattingFactors_ChemLinkMult0 = [1.0, 1.1, 1.25, 1.5]

# Horizontal angle ranges, indexed [inputDirection][isCharge][frameOfContact] -> [low, high].
BattingAngleRanges = [[[[0, 0], [0, 0], [-700, -500], [-500, -350], [-400, -250], [-350, -100], [-150, 250], [200, 300], [250, 400], [350, 550], [550, 700], [0, 0], [0, 0], [0, 0], [0, 0]], [[0, 0], [0, 0], [0, 0], [-600, -400], [-400, -200], [-300, -100], [-200, 200], [100, 400], [300, 450], [350, 600], [0, 0], [0, 0], [0, 0], [0, 0], [0, 0]]], [[[0, 0], [0, 0], [-750, -500], [-500, -300], [-300, -150], [-150, 200], [200, 400], [300, 450], [400, 600], [500, 600], [600, 700], [0, 0], [0, 0], [0, 0], [0, 0]], [[0, 0], [0, 0], [0, 0], [-600, -400], [-400, -200], [-300, 100], [100, 400], [100, 400], [200, 500], [500, 700], [0, 0], [0, 0], [0, 0], [0, 0], [0, 0]]], [[[0, 0], [0, 0], [-700, -600], [-600, -400], [-450, -350], [-400, -300], [-350, -200], [-200, 150], [150, 300], [300, 700], [0, 0], [0, 0], [0, 0], [0, 0], [0, 0]], [[0, 0], [0, 0], [0, 0], [-550, -300], [-400, -200], [-300, -100], [-300, -100], [-100, 200], [200, 450], [450, 650], [0, 0], [0, 0], [0, 0], [0, 0], [0, 0]]]]

# "Remove slice" gecko mod: vanilla leaves these [inputDirection][isCharge][frame]
# cells as [0,0], which forces the hit dead up the middle (raw angle 0x400 -- the
# unrealistic "slice") whenever contact lands on the earliest/latest valid frame.
# The mod replaces them with the proper extreme pull (frame 2) / push (frame 10)
# ranges so the ball goes foul instead. Values are zero-span (low == high), so the
# angle is deterministic and no RNG index is drawn. See hit_simulation.remove_slice.
REMOVE_SLICE_ANGLE_OVERRIDES = {
    (PushPullNone, 1, 2): [-600, -600],
    (PushPullNone, 1, 10): [600, 600],
    (PullStickTowardsHitting, 1, 2): [-600, -600],
    (PullStickTowardsHitting, 1, 10): [700, 700],
    (PushStickAway, 1, 2): [-550, -550],
    (PushStickAway, 1, 10): [650, 650],
    (PushStickAway, 0, 10): [700, 700],
}

# Vertical zone weights, indexed [hitTrajectoryLow][slapOrCharge][easyBatting][contactType] -> 5 weights.
BattingVerticalAngleWeights = [[[[[0, 10, 20, 30, 40], [20, 20, 20, 20, 20], [10, 25, 30, 25, 10], [20, 20, 20, 20, 20], [40, 30, 20, 10, 0]], [[0, 10, 20, 30, 40], [20, 20, 20, 20, 20], [10, 25, 30, 25, 10], [20, 20, 20, 20, 20], [40, 30, 20, 10, 0]]], [[[10, 0, 20, 30, 40], [20, 22, 22, 28, 8], [20, 25, 25, 25, 5], [20, 22, 22, 28, 8], [10, 0, 20, 30, 40]], [[10, 0, 20, 30, 40], [20, 22, 22, 28, 8], [20, 25, 25, 25, 5], [20, 22, 22, 28, 8], [10, 0, 20, 30, 40]]]], [[[[0, 10, 20, 30, 40], [5, 5, 15, 40, 35], [5, 5, 20, 40, 35], [5, 5, 15, 40, 35], [40, 30, 20, 10, 0]], [[0, 10, 20, 30, 40], [5, 5, 15, 40, 35], [5, 5, 20, 40, 35], [5, 5, 15, 40, 35], [40, 30, 20, 10, 0]]], [[[5, 0, 10, 40, 45], [5, 21, 12, 29, 33], [5, 23, 15, 27, 30], [5, 21, 12, 29, 33], [5, 0, 10, 40, 45]], [[5, 0, 10, 40, 45], [5, 21, 12, 29, 33], [5, 23, 15, 27, 30], [5, 21, 12, 29, 33], [5, 0, 10, 40, 45]]]], [[[[10, 20, 20, 20, 30], [35, 40, 15, 5, 5], [30, 40, 20, 5, 5], [35, 40, 15, 5, 5], [40, 30, 20, 5, 5]], [[10, 20, 20, 20, 30], [35, 40, 15, 5, 5], [30, 40, 20, 5, 5], [35, 40, 15, 5, 5], [40, 30, 20, 5, 5]]], [[[10, 0, 20, 30, 40], [35, 30, 22, 10, 3], [30, 30, 25, 15, 0], [35, 30, 22, 10, 3], [10, 0, 20, 30, 40]], [[10, 0, 20, 30, 40], [35, 30, 22, 10, 3], [30, 30, 25, 15, 0], [35, 30, 22, 10, 3], [10, 0, 20, 30, 40]]]]]

# Vertical angle zones, indexed [slapOrCharge][contactType][zoneIndex] -> [low, high].
SHORT_ARRAY_ARRAY_ARRAY_ARRAY_807b67cc = [[[[-50, 50], [50, 100], [100, 300], [300, 400], [400, 500]], [[50, 150], [150, 200], [200, 250], [250, 300], [300, 350]], [[50, 150], [150, 200], [150, 200], [200, 300], [300, 350]], [[50, 150], [150, 200], [200, 250], [250, 300], [300, 350]], [[-50, 50], [50, 100], [100, 300], [300, 400], [400, 500]]], [[[400, 450], [450, 500], [500, 550], [550, 600], [550, 600]], [[50, 100], [100, 150], [300, 400], [350, 450], [400, 500]], [[100, 200], [350, 400], [450, 500], [500, 550], [530, 580]], [[50, 100], [100, 150], [300, 400], [350, 450], [400, 500]], [[400, 450], [450, 500], [500, 550], [550, 600], [550, 600]]]]

# Vertical angle override by iVar5 zone -> [low, high].
SHORT_ARRAY_ARRAY_807b6af4 = [[0, 0], [500, 550], [500, 550]]

# Non-captain star swing vertical ranges, indexed [swing-1][contactType] -> [low, high].
NonCaptainStarSwingBattingVerticalAngleRanges = [[[250, 300], [300, 350], [350, 400], [400, 450], [450, 500]], [[50, 100], [50, 100], [50, 100], [50, 100], [50, 100]], [[120, 160], [160, 200], [160, 200], [160, 200], [120, 160]]]

# Captain star swing vertical ranges, indexed [captainStar-1][contactType] -> [low, high].
CaptainStarSwingBattingVerticalAngleRanges = [[[59, 61], [59, 61], [59, 61], [59, 61], [59, 61]], [[-101, -99], [-101, -99], [-101, -99], [-101, -99], [-101, -99]], [[350, 400], [350, 400], [350, 400], [350, 400], [350, 400]], [[450, 500], [450, 500], [450, 500], [450, 500], [450, 500]], [[120, 160], [160, 200], [160, 200], [160, 200], [120, 160]], [[250, 300], [250, 300], [250, 300], [250, 300], [250, 300]], [[64, 80], [64, 80], [64, 80], [64, 80], [64, 80]], [[64, 80], [64, 80], [64, 80], [64, 80], [64, 80]], [[350, 400], [350, 400], [350, 400], [350, 400], [350, 400]], [[200, 250], [200, 250], [200, 250], [200, 250], [200, 250]], [[350, 600], [350, 600], [350, 600], [350, 600], [350, 600]], [[350, 600], [350, 600], [350, 600], [350, 600], [350, 600]]]

# Exit-velocity ranges (regular), indexed [slapChargeStarBunt][contactType] -> [low, high, gravity].
BallHitArray = [[[100, 130, -110], [140, 145, -100], [145, 150, -110], [140, 145, -100], [100, 130, -110]], [[140, 150, -120], [162, 177, -160], [160, 170, 0], [162, 177, -160], [140, 150, -120]], [[120, 130, -200], [140, 150, -200], [160, 170, -200], [140, 150, -200], [120, 130, -200]], [[150, 160, -300], [170, 190, -300], [190, 200, -300], [170, 190, -300], [150, 160, -300]], [[130, 140, -200], [145, 155, -300], [160, 170, -300], [145, 155, -300], [130, 140, -200]], [[140, 150, -150], [190, 200, -200], [200, 210, -180], [190, 200, -200], [140, 150, -150]]]

# Exit-velocity ranges (non-captain star), indexed [swing-1][contactType] -> [low, high, gravity].
StarSwingExitVelocityArray = [[[150, 160, -150], [160, 170, -150], [170, 180, -100], [160, 170, -150], [150, 160, -150]], [[150, 160, -250], [160, 170, -250], [170, 180, -250], [160, 170, -250], [150, 160, -250]], [[170, 180, -300], [170, 180, -300], [190, 200, -300], [170, 180, -300], [170, 180, -300]]]

# Exit-velocity ranges (captain star), indexed [captainStar-1][contactType] -> [low, high, gravity].
CaptainStarSwingExitVelocityArray = [[[140, 150, 0], [150, 160, 150], [160, 170, 150], [150, 160, 150], [140, 150, 0]], [[120, 130, 0], [130, 150, 50], [160, 170, 100], [130, 150, 50], [120, 130, 0]], [[90, 100, 80], [100, 110, 80], [110, 120, 80], [100, 110, 80], [90, 100, 80]], [[60, 70, 80], [70, 80, 80], [70, 80, 80], [70, 80, 80], [60, 70, 80]], [[170, 180, -120], [170, 180, -130], [190, 200, -125], [170, 180, -135], [170, 180, -125]], [[150, 160, -140], [150, 160, -150], [160, 170, -150], [150, 160, -150], [150, 160, -140]], [[170, 180, 0], [170, 180, 0], [190, 200, 0], [170, 180, 0], [170, 180, 0]], [[160, 170, 0], [160, 170, 0], [180, 190, 0], [160, 170, 0], [160, 170, 0]], [[90, 130, -650], [90, 130, -650], [90, 130, -650], [90, 130, -650], [90, 130, -650]], [[140, 160, -400], [140, 160, -400], [140, 160, -400], [140, 160, -400], [140, 160, -400]], [[130, 140, -100], [140, 150, -100], [150, 160, -100], [140, 150, -100], [130, 140, -100]], [[130, 140, -100], [140, 150, -100], [150, 160, -100], [140, 150, -100], [130, 140, -100]]]

# Cursed-ball power scaling per perfect/nice/sour -> [min, max].
FLOAT_ARRAY_ARRAY_807b7480 = [[1.0, 1.0], [1.0, 0.8], [1.0, 0.5]]

# Field-area power bonus, indexed [trajectoryNearFar][segment].
FieldTrajectories = [[1.0, 1.0, 1.0, 1.0, 1.0], [0.85, 0.95, 1.0, 1.05, 1.02], [1.02, 1.05, 1.0, 0.95, 0.85]]

# Allowed bat-extension reach (ballX - posX), indexed [trimmedBat] -> [near, far].
BattingExtensions = [[-0.85, 0.15], [-0.35, 0.35]]

# Super-curve factors, indexed [hasSuperCurve] -> [base, xAccel, zAccel].
FLOAT_ARRAY_ARRAY_807b72bc = [[0.5, 0.001, 0.003], [0.25, 0.006, 0.008]]

# Star-swing codes (captain_star_hit_pitch 1-12 / 0, non_captain_star_swing 1-3)
# now live pre-encoded in the "Captain Star Hit" / "Non-Captain Star Hit" columns
# of constants/character_attributes.csv; their name<->code maps are
# LookupDicts.CAPTAIN_STAR_BALL / NON_CAPTAIN_STAR_HIT.

# --- DK / Diddy "banana" captain star hit ---
# The "Captain Star Hit" column encodes a per-captain code (1 Mario .. 12 Daisy),
# stored at contact in AtBat_Mystery_CaptainStarSwing. DK (5) and Diddy (6) both
# throw the banana star hit: while it is active, liveBallHitPhysics rotates the
# ball's HORIZONTAL velocity by a fixed angle each frame (the horizontal speed is
# preserved -- only the direction turns), producing the wide banana arc.
CaptainStar_DK = 5
CaptainStar_Diddy = 6
BANANA_CAPTAIN_STARS = frozenset({CaptainStar_DK, CaptainStar_Diddy})

# Per-frame horizontal turn applied during the banana hit, in radians
# (const_hitFloats.0.008_DKStarAngleDelta).
DK_DIDDY_STAR_ANGLE_DELTA = 0.008

# The banana curve is active over the middle of the flight: CalculateHitVariables
# sets bananaHitStartFrame = trunc(hangtimeOfHit * 0.25) and bananaHitEndFrame =
# trunc(hangtimeOfHit * 0.95), where hangtimeOfHit is the straight-flight hang
# time (the curve turns on after a quarter of the flight and off near the end).
DK_DIDDY_STAR_HANGTIME_START = 0.25
DK_DIDDY_STAR_HANGTIME_END = 0.95

# --- Other captain star hit codes ("Captain Star Hit" column) ---
CaptainStar_Wario = 3
CaptainStar_Waluigi = 4
CaptainStar_Bowser = 7
CaptainStar_BowserJr = 8

# Bowser / Bowser Jr "bullet" star: BallEnergy = 4x the hit power
# (const_hitFloats.4.0_bulletStarEnergyMultiplier). Energy drives how hard the
# ball plows through fielders, NOT the aerial flight, so it is exposed as
# HitResult metadata only -- the bullet's flat trajectory already comes from the
# captain-star exit-velocity table.
BULLET_CAPTAIN_STARS = frozenset({CaptainStar_Bowser, CaptainStar_BowserJr})
BULLET_STAR_ENERGY_MULT = 4.0

# Wario / Waluigi "garlic" star (warioWaluStarHit): the hit flies normally until
# GARLIC_SPLIT_FRAMES_BEFORE_GROUND frames before it would reach the ground
# (hitShortConst.120_framesBeforeGroundWhenGarlicSplits), then SPLITS into two
# balls -- one "real", one garlic -- that start at the split point keeping the
# pre-split horizontal speed and Y velocity, but with headings offset to either
# side of the pre-split heading. warioWaluStarHitDirection (RandomInt_Game(2),
# set in CalculateHitVariables) picks which side is the real ball.
GARLIC_CAPTAIN_STARS = frozenset({CaptainStar_Wario, CaptainStar_Waluigi})
GARLIC_SPLIT_FRAMES_BEFORE_GROUND = 120
# Per-side heading offset (radians) from the pre-split heading: the game rolls an
# independent randomInRange(0.2, 0.3) for each ball (ported in _random_in_range).
GARLIC_SPREAD_LOWER = 0.2
GARLIC_SPREAD_UPPER = 0.3

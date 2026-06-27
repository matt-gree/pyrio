"""Port of the MSSB batting calculator (index.js) -> hit info + trajectory.

Pipeline (per the JS): parse -> calculateContact -> calculateHorizontalAngle ->
calculateVerticalAngle -> calculateHitPower -> convertPowerToVelocity ->
calculateHitGround. Given the three RNG seeds it is fully deterministic, so a
recorded event's RNG1/RNG2/RNG3 reproduces that event's contact exactly.

Public API:
    simulate_hit(HitInputs) -> HitResult            # pure core
    simulate_hit_from_event(EventObj) -> HitResult  # stat-file adapter

Character attributes are loaded by NAME from constants/character_attributes.csv
(the encoded star-OFF table == the JS `stats` base values). When stars_on, the
superstar conversion (constants.game_constants.apply_superstar, a capped +50/+20
per stat) is applied to slap/charge power (batter) and cursed ball (pitcher) --
the same stats the JS calculator buffed, now clamped to the in-game caps.

Notes / known JS quirks carried over:
  - Moonshot (`AtBat_MoonShot`) is unreachable here: the JS hardcodes
    starsForBatter = 4, so the moonshot branch (needs >= 5) never runs. Its
    undefined `AtBat_MoonShotMultiplier` therefore never matters.
  - Super curve is read from the "Super Curve" column of the character attribute
    CSV (derived from the "Curved Hits" Extra tag) instead of the JS's hardcoded
    char ids.

calculateHitGround / liveBallHitPhysics notes:
  - Integration is semi-implicit (symplectic) Euler: each frame velocity is
    decayed (air resistance + gravity) and acceleration added BEFORE the
    position is stepped, matching the game's per-frame order.
  - The trajectory starts at the world contact position. The recorded contact X
    is batter-relative (mirrored about the plate for lefties) while velocity and
    landing are world-frame, so the X start is mirrored for lefties.
  - The ground plane is GROUND_Y (0.15, or 0.35 on Toy Field), not 0. Most
    stadiums (BOUNCING_STADIUM_IDS) get a blanket flat-ground bounce: clamp Y and
    reverse a downward Y velocity. Bowser Castle / Toy Field are excluded because
    their ground has holes, so the game resolves them in ballCollisionLogic (not
    ported); we approximate that with a ground-pinning skid.
  - The aerial `landing` is recorded one frame after first ground contact (the
    sim advances one extra frame). HitResult.trajectory stays wall-free and
    stops at that aerial landing.

Testing helpers (not used by the core sim):
  - simulate_hit_trajectory / simulate_hit_trajectory_from_event continue the
    ball through ground contacts (bounce/skid) for a fixed number of frames --
    e.g. walking a grounder/liner to its recorded hang time.
  - stadiums.wall_collision_point clips a trajectory to the outfield wall.
  - hit_sim_validation.py exposes --walls and --bounces to compare landings.

Testing status (via hit_sim_validation.py):
    - Hit inputs, such as horizontal/vertical angle thresholds and hit power, have been spot-checked with 2 stars off stat files and they achieved 100% convergence.
    - Landing spots (fair, in-play, contact-correct) match the recorded landing
      within ~1 unit ~97% of the time with --walls --bounces enabled.
"""
from __future__ import annotations

import csv
import math
import struct
from dataclasses import dataclass, field
from typing import Optional

from .constants import hit_sim_tables as T
from .constants import CHARACTER_ATTRIBUTES_CSV
from .constants import game_constants as G
from .stat_file_parser import EventObj

# JS leaves AtBat_MoonShotMultiplier undefined; the branch is unreachable here
# (starsForBatter is hardcoded 4), so this value is never actually used.
_MOONSHOT_MULTIPLIER = 1.0

_CONTACT_TYPE_NAMES = ["Left Sour", "Left Nice", "Perfect", "Right Nice", "Right Sour"]


# ---------------------------------------------------------------- JS helpers

def _jfloor(x: float) -> int:
    """The JS `floor` is Math.trunc (toward zero), not Math.floor."""
    return math.trunc(x)


def _to_int32(x: int) -> int:
    x &= 0xFFFFFFFF
    return x - 0x100000000 if x & 0x80000000 else x


def _f32(x: float) -> float:
    """Narrow a Python double to 32-bit float, as the game's single-precision
    arithmetic does (needed where an intermediate (float) cast changes a result)."""
    return struct.unpack("f", struct.pack("f", x))[0]


def _adjust_ball_angle(a: int) -> int:
    """JS AdjustBallAngle: wrap into [0, 0xfff]."""
    return a % 0x1000


def _mssb_to_radians(p: int) -> float:
    if p < 0:
        p += 0x1000
    if 0xFFF < p:
        p += -0x1000
    d = (math.pi * (p << 1)) / 4096
    if math.pi < d:
        d = -(2 * math.pi - d)
    return d


def _linear_interpolate(value, prev_min, prev_max, next_min, next_max):
    """JS LinearInterpolateToNewRange (clamps the fraction to [0, 1])."""
    if (prev_max - prev_min) == 0:
        frac = 1.0
    else:
        frac = 1.0
        calced = (value - prev_min) / (prev_max - prev_min)
        if calced <= frac:
            frac = calced
            if calced < 0.0:
                frac = 0.0
    return (next_max - next_min) * frac + next_min


# ---------------------------------------------------------------- attributes

_attr_rows: Optional[dict] = None


def _load_attr_rows() -> dict:
    """Character-attribute rows indexed by BOTH name (decoded files) and encoded
    char id (encoded files), so a row resolves whichever identity a stat file uses.
    """
    global _attr_rows
    if _attr_rows is None:
        rows = {}
        with open(CHARACTER_ATTRIBUTES_CSV, newline="") as f:
            for row in csv.DictReader(f):
                rows[row["Character"]] = row     # by name ("Boo")
                rows[int(row["CharId"])] = row   # by encoded char id (0xe)
        _attr_rows = rows
    return _attr_rows


# Non-red Toad color variants. The "Fix Non-red Toad Hitboxes and Bat Reach" mod
# gives these Red Toad's bat reach (Horizontal Range Near/Far); see HitInputs.
_NON_RED_TOADS = frozenset({"Toad(B)", "Toad(Y)", "Toad(G)", "Toad(P)"})


def _red_toad_reach() -> tuple:
    """Red Toad's (Horizontal Range Near, Far), read from the attribute CSV."""
    row = _load_attr_rows()["Toad(R)"]
    return float(row["Horizontal Range Near"]), float(row["Horizontal Range Far"])


def _stat(row, col, stars_on):
    """Read an integer stat, applying the superstar conversion when stars_on."""
    value = int(row[col])
    return G.apply_superstar(col, value) if stars_on else value


@dataclass
class BatterAttributes:
    name: str
    slap_hit_power: int
    charge_power: int
    slap_contact_size: int
    charge_contact_size: int
    bunting: int
    horizontal_trajectory: int       # BatterAtPlate_TrajectoryNearFar (0 Mid/1 Pull/2 Push)
    vertical_trajectory: int         # AtBat_HitTrajectoryLow (0 Mid/1 High/2 Low)
    captain_star_hit_pitch: int      # 1-12 captains, 0 otherwise
    non_captain_star_swing: int      # 1-3
    horizontal_range_near: float
    horizontal_range_far: float
    trimmed_bat: int
    pitching_height: float
    has_super_curve: bool

    @classmethod
    def from_name(cls, name, stars_on: bool = False) -> "BatterAttributes":
        # `name` may be a character name (decoded files) or an encoded char id.
        row = _load_attr_rows()[name]
        return cls(
            name=row["Character"],
            slap_hit_power=_stat(row, "Slap Hit Power", stars_on),
            charge_power=_stat(row, "Charge Hit Power", stars_on),
            slap_contact_size=_stat(row, "Slap Contact Size Multiplier", stars_on),
            charge_contact_size=_stat(row, "Charge Contact Size Multiplier", stars_on),
            bunting=_stat(row, "Bunting", stars_on),
            horizontal_trajectory=int(row["Horizontal Hit Trajectory"]),
            vertical_trajectory=int(row["Vertical Hit Trajectory"]),
            captain_star_hit_pitch=int(row["Captain Star Hit"]),
            non_captain_star_swing=int(row["Non-Captain Star Hit"]),
            horizontal_range_near=float(row["Horizontal Range Near"]),
            horizontal_range_far=float(row["Horizontal Range Far"]),
            trimmed_bat=int(float(row["Trimmed Bat"])),
            pitching_height=float(row["Pitching Height"]),
            has_super_curve=bool(int(row["Super Curve"])),
        )


@dataclass
class PitcherAttributes:
    name: str
    cursed_ball: int

    @classmethod
    def from_name(cls, name, stars_on: bool = False) -> "PitcherAttributes":
        # `name` may be a character name (decoded files) or an encoded char id.
        row = _load_attr_rows()[name]
        return cls(name=row["Character"], cursed_ball=_stat(row, "Cursed Ball", stars_on))


# ---------------------------------------------------------------- I/O structs

@dataclass
class HitInputs:
    batter_name: str
    pitcher_name: str
    # pitch: 0 Curve, 1 Charge(Slider), 2 Perfect Charge, 3 ChangeUp
    pitch_type_val: int
    pos_x: float                 # batter X at contact
    ball_x: float                # ball X at contact (world X start of trajectory)
    # ball_z (world Z start of trajectory) is in the defaulted block below.
    batter_hand: int             # 0 Righty, 1 Lefty
    swing: int                   # 0 Slap, 1 Charge (Star handled via is_star)
    is_star: bool = False
    charge_up: float = 0.0
    charge_down: float = 0.0
    chem_links: int = 0          # 0-3
    frame: int = 5               # frame of contact (2-10)
    input_up: bool = False
    input_down: bool = False
    input_left: bool = False
    input_right: bool = False
    easy_batting: bool = False
    batter_stars_on: bool = False
    pitcher_stars_on: bool = False
    ball_z: float = 0.0                     # ball Z at contact (world Z start of trajectory)
    ground_y: float = T.GROUND_Y_DEFAULT   # landing/bounce plane (0.35 on Toy Field)
    bounce: bool = True                     # ground bounces elastically (False = skid; Bowser Castle / Toy Field)
    # Gecko-mod toggles (off = vanilla). The validator turns these on from a
    # match's active tags; see TAG_TO_FLAG and _inputs_from_event.
    # "Fix Non-red Toad Hitboxes and Bat Reach": give the non-red Toad color
    # variants Red Toad's bat reach (Horizontal Range Near/Far). No other effect.
    fix_non_red_toad_reach: bool = False
    # "Remove slice": patch the [0,0] holes in BattingAngleRanges (an early/late
    # contact otherwise goes dead up the middle) so frame-2/10 hits go foul; see
    # T.REMOVE_SLICE_ANGLE_OVERRIDES.
    remove_slice: bool = False
    # DK/Diddy "banana" captain star hit (auto-applied when the captain star is
    # DK or Diddy): while active, the horizontal velocity is rotated
    # T.DK_DIDDY_STAR_ANGLE_DELTA rad/frame (speed preserved), making the wide
    # horizontal arc. CalculateHitVariables derives all three from the hit, so
    # None means "use the game's rule": the window is 0.25x..0.95x of the
    # straight-flight hang time, and the direction is the batter's hand. Set
    # explicit values only to override.
    banana_hit_start_frame: Optional[int] = None   # active while start < framesSinceLiveBall < end
    banana_hit_end_frame: Optional[int] = None
    banana_direction: Optional[int] = None         # 0 (Righty) subtracts, 1 (Lefty) adds the delta
    # Wario/Waluigi "garlic" captain star hit (auto-applied for Wario/Waluigi). The
    # ball splits in two near the ground; each ball's heading is offset from the
    # pre-split heading by a per-side spread. None -> the game's RNG
    # (randomInRange(0.2, 0.3) per side); a float forces one symmetric spread (rad).
    # The game rolls warioWaluStarHitDirection via RandomInt_Game(2); None
    # reproduces that, 0/1 forces which side the real ball takes.
    garlic_spread: Optional[float] = None
    garlic_direction: Optional[int] = None
    rng1: int = T.DEFAULT_STATIC_RANDOM_INT1
    rng2: int = T.DEFAULT_STATIC_RANDOM_INT2
    rng3: int = T.DEFAULT_USHORT_8089269c


@dataclass
class HitResult:
    contact_absolute: float                  # CalculatedBallPos (0-200)
    contact_type: int
    contact_type_name: str
    contact_quality: float
    hit_type: int
    horizontal_angle: int                    # raw 0-4096
    vertical_angle: int                      # raw 0-4096
    horizontal_angle_deg: float
    vertical_angle_deg: float
    power: int
    velocity: tuple                          # (x, y, z)
    acceleration: tuple                      # (x, y, z)
    landing: tuple                           # (x, y, z) last airborne point
    distance: float                          # sqrt(x^2 + z^2) of landing
    hang_frames: int
    ball_energy: float                       # BallEnergy (Bowser/BJ bullet = 4x power; else charge energy)
    trajectory: list = field(repr=False)     # list of (x, y, z) per frame -- the real ball
    # Wario/Waluigi garlic ball's (x, y, z) per frame from the split onward; None
    # for non-garlic hits. The main `trajectory` follows the real ball.
    garlic_trajectory: Optional[list] = field(default=None, repr=False)


# ---------------------------------------------------------------- simulator

class _HitSim:
    """Faithful port of the JS pipeline; attribute names mirror inMemBatter/etc."""

    def __init__(self, batter: BatterAttributes, pitcher: PitcherAttributes, inp: HitInputs):
        self.b = batter
        self.p = pitcher
        self.inp = inp

        # RNG state (mutated by weighted_random_index)
        self.s1 = inp.rng1
        self.s2 = inp.rng2
        self.ushort = inp.rng3

        # pitcher pitch typing (parseValues)
        pv = inp.pitch_type_val
        if pv == 0:
            self.Pitcher_TypeOfPitch = T.PitchCurve
            self.ChargePitchType = T.PitchChargeType_None
        elif pv == 1:
            self.Pitcher_TypeOfPitch = T.PitchCharge
            self.ChargePitchType = T.PitchChargeType_Charge
        elif pv == 2:
            self.Pitcher_TypeOfPitch = T.PitchCharge
            self.ChargePitchType = T.PitchChargeType_Perfect
        else:
            self.Pitcher_TypeOfPitch = T.PitchChangeUp
            self.ChargePitchType = T.PitchChargeType_None
        self.cursed_ball = pitcher.cursed_ball

        # batter setup (parseValues)
        self.AtBat_Mystery_BatDirection = 0
        self.AtBat_TrimmedBat = batter.trimmed_bat
        self.posX = inp.pos_x
        self.ballContact_X = inp.ball_x
        self.interstitialBallContact_X = inp.ball_x
        self.AtBat_BatterHand = inp.batter_hand
        self.Batter_Contact_SlapChargeBuntStar = inp.swing
        self.Batter_IsBunting = inp.swing == T.Bunt
        self.BatterAtPlate_BatterCharge_Up = inp.charge_up
        self.BatterAtPlate_BatterCharge_Down = inp.charge_down
        self.AtBat_IsFullyCharged = inp.charge_up == 1.0
        self.Batter_SlapHitPower = batter.slap_hit_power
        self.BatterAtPlate_ChargePower = batter.charge_power
        self.Batter_SlapContactSize = batter.slap_contact_size
        self.Batter_ChargeContactSize = batter.charge_contact_size
        self.Batter_Bunting = batter.bunting
        self.BatterAtPlate_TrajectoryNearFar = batter.horizontal_trajectory
        self.AtBat_HitTrajectoryLow = batter.vertical_trajectory

        # Bat reach (Horizontal Range Near/Far). "Fix Non-red Toad Hitboxes and
        # Bat Reach" gives the non-red Toads Red Toad's reach.
        self.horizontalRangeNear = batter.horizontal_range_near
        self.horizontalRangeFar = batter.horizontal_range_far
        if inp.fix_non_red_toad_reach and batter.name in _NON_RED_TOADS:
            self.horizontalRangeNear, self.horizontalRangeFar = _red_toad_reach()
        self.removeSlice = inp.remove_slice
        self.RandomBattingFactors_ChemLinksOnBase = inp.chem_links
        self.Frame_SwingContact1 = int(inp.frame)
        self.EasyBatting = 1 if inp.easy_batting else 0
        self.isStar = inp.is_star
        self.AtBat_MoonShot = False
        self.input_up = inp.input_up
        self.input_down = inp.input_down
        self.input_left = inp.input_left
        self.input_right = inp.input_right
        self.AtBat_CaptainStarHitPitch = batter.captain_star_hit_pitch
        self.AtBat_NonCaptainStarSwing = batter.non_captain_star_swing
        self.nonCaptainStarSwingContact = 0
        self.AtBat_Mystery_CaptainStarSwing = 0
        self.AtBat_Mystery_DidPopFlyOrGrounderConnect = False

        # DK/Diddy banana star hit window/direction (see HitInputs).
        self.bananaHitStartFrame = inp.banana_hit_start_frame
        self.bananaHitEndFrame = inp.banana_hit_end_frame
        self.directionOfBananaHit = inp.banana_direction

        # Wario/Waluigi garlic star hit spread/direction (see HitInputs).
        self.garlicSpread = inp.garlic_spread
        self.warioWaluStarHitDirection = inp.garlic_direction

        self._resolve_star_swing()

        # outputs filled during the pipeline
        self.CalculatedBallPos = 0.0
        self.Batter_ContactType = T.LeftSour
        self.ContactQuality = 0.0
        self.Batter_HitType = -1
        self.LeftNiceThreshold = 0.0
        self.LeftPerfectThreshold = 0.0
        self.RightPerfectThreshold = 0.0
        self.RightNiceThreshold = 0.0
        self.Hit_HorizontalAngle = 0
        self.Hit_VerticalAngle = 0
        self.Hit_HorizontalPower = 0
        self.AddedContactGravity = 0.0
        self.ballVelocity = [0.0, 0.0, 0.0]
        self.ballAcceleration = [0.0, 0.0, 0.0]
        self.BallEnergy = 0.0
        self.trajectory: list = []
        self._garlic_trajectory: Optional[list] = None

    # -- parseValues star resolution (starsForBatter hardcoded 4) --
    def _resolve_star_swing(self):
        stars_for_batter = 4
        if not self.isStar:
            return
        if self.Batter_IsBunting:
            self.Batter_Contact_SlapChargeBuntStar = T.Bunt
            self.AtBat_MoonShot = False
            return
        # starsForBatter != 0  -> True
        # (not fullyCharged) or (starsForBatter < 5) -> always True here
        if self.AtBat_CaptainStarHitPitch == 0:
            if self.AtBat_NonCaptainStarSwing == 0:
                self.isStar = False
            else:
                self.nonCaptainStarSwingContact = self.AtBat_NonCaptainStarSwing
                if self.AtBat_NonCaptainStarSwing == 2:
                    self.Batter_Contact_SlapChargeBuntStar = T.Charge
                    self.AtBat_Mystery_DidPopFlyOrGrounderConnect = True
                    self.BatterAtPlate_BatterCharge_Up = 1.0
                elif self.AtBat_NonCaptainStarSwing < 2:  # == 1
                    self.Batter_Contact_SlapChargeBuntStar = T.Charge
                    self.AtBat_Mystery_DidPopFlyOrGrounderConnect = True
                    self.BatterAtPlate_BatterCharge_Up = 1.0
                elif self.AtBat_NonCaptainStarSwing < 4:  # == 3
                    self.Batter_Contact_SlapChargeBuntStar = T.Slap
        else:
            # JS captain-at-roster-loc branch is `else if (false)`; falls through
            # to: else if (starsForBatter < 2) -> False, else -> Star
            self.Batter_Contact_SlapChargeBuntStar = T.Star

        if (self.Batter_Contact_SlapChargeBuntStar == T.Star
                or self.AtBat_Mystery_DidPopFlyOrGrounderConnect):
            self.AtBat_Mystery_CaptainStarSwing = self.AtBat_CaptainStarHitPitch

    # -- RNG --
    def _weighted_random_index(self, vals, count):
        loop_sum = sum(vals)
        fin_sum = -loop_sum if loop_sum < 0 else loop_sum
        if fin_sum < 2:
            random_sum = 0
        else:
            self.s1 = (self.s1 - (self.s2 & 0xFF)) + _jfloor(self.s2 / fin_sum) + self.ushort
            random_range = self.s1 - _jfloor(self.s1 / fin_sum) * fin_sum
            rr = _to_int32(random_range)
            random_sum = ((rr >> 31) ^ rr) - (rr >> 31)  # abs(int32)
            if loop_sum < 0:
                random_sum = -random_sum
        new_index = 0
        c = count
        i = 0
        while c > 0:
            if random_sum < vals[i]:
                return new_index
            random_sum -= vals[i]
            new_index += 1
            c -= 1
            i += 1
        return 0

    def _random_int_game(self, max_num: int) -> int:
        """Port of RandomInt_Game: a uniform int in [0, |max_num|) drawn from the
        same StaticRandomInt1/2 + TotalframesAtPlay RNG as _weighted_random_index
        (and mutating s1 the same way)."""
        n = -max_num if max_num < 0 else max_num
        if n < 2:
            return 0
        self.s1 = (self.s1 - (self.s2 & 0xFF)) + _jfloor(self.s2 / n) + self.ushort
        rr = _to_int32(self.s1 - _jfloor(self.s1 / n) * n)
        result = ((rr >> 31) ^ rr) - (rr >> 31)  # abs(int32)
        return -result if max_num < 0 else result

    def _random_in_range(self, lower: float, upper: float) -> float:
        """Port of randomInRange: a uniform float in [lower, upper] quantized to
        0.001, drawn from the same RNG as _random_int_game. The (float) casts on
        the step count are reproduced so the quantization matches the game."""
        steps = _jfloor(_f32(1000.0 * _f32(upper - lower))) + 1
        return _f32(0.001 * self._random_int_game(steps) + lower)

    # -- hitBall: is contact even possible? --
    def hit_ball(self) -> bool:
        ext = T.BattingExtensions[self.AtBat_TrimmedBat]
        diff = self.ballContact_X - self.posX
        if ext[0] <= diff <= ext[1]:
            self.interstitialBallContact_X = self.ballContact_X
            return True
        return False

    # -- calculateContact --
    def calculate_contact(self):
        charge_up = self.BatterAtPlate_BatterCharge_Up
        contact_size = self.Batter_SlapContactSize
        if self.AtBat_Mystery_CaptainStarSwing != 0:
            charge_up = 0.0
            contact_size = 100.0
        if not self.Batter_IsBunting:
            if charge_up <= 0.0:
                if self.RandomBattingFactors_ChemLinksOnBase != 0:
                    contact_size *= T.contact_ChemLinkMultipliers[self.RandomBattingFactors_ChemLinksOnBase]
            else:
                contact_size = self.Batter_ChargeContactSize
        else:
            contact_size = self.Batter_Bunting

        diff = self.interstitialBallContact_X - self.posX
        if self.AtBat_BatterHand == T.Lefty:
            diff = -diff
        if diff >= 0.0:
            cbp = 100.0 * (diff / self.horizontalRangeFar) + 100.0
        else:
            cbp = -(100.0 * (diff / self.horizontalRangeNear) - 100.0)
        cbp = max(0.0, min(200.0, cbp))
        self.CalculatedBallPos = cbp

        contact_size = contact_size / 100.0
        big = T.BallContactArray_807b6294[self.AtBat_TrimmedBat][self.Batter_Contact_SlapChargeBuntStar][self.EasyBatting]
        b0, b1, b2, b3 = big[0], big[1], big[2], big[3]
        self.LeftNiceThreshold = contact_size * (big[4] - b0) + b0
        self.LeftPerfectThreshold = contact_size * (big[5] - b1) + b1
        self.RightPerfectThreshold = contact_size * (big[6] - b2) + b2
        self.RightNiceThreshold = contact_size * (big[7] - b3) + b3

        ct = T.LeftSour
        if self.LeftNiceThreshold <= cbp:
            ct = T.LeftNice
            if self.LeftPerfectThreshold <= cbp:
                ct = T.Perfect
                if self.RightPerfectThreshold <= cbp:
                    ct = T.RightNice
                    if self.RightNiceThreshold <= cbp:
                        ct = T.RightSour
        self.Batter_ContactType = ct

        if ct == T.Perfect:
            span = self.RightPerfectThreshold - self.LeftPerfectThreshold
            if cbp >= 100.0:
                self.ContactQuality = 1.0 - (cbp - self.LeftPerfectThreshold) / span
            else:
                self.ContactQuality = (cbp - self.LeftPerfectThreshold) / span
        elif ct < T.Perfect:
            if ct == T.LeftSour:
                self.ContactQuality = cbp / self.LeftNiceThreshold
            else:
                self.ContactQuality = (cbp - self.LeftNiceThreshold) / (self.LeftPerfectThreshold - self.LeftNiceThreshold)
        elif ct < T.RightSour:
            self.ContactQuality = 1.0 - (cbp - self.RightPerfectThreshold) / (self.RightNiceThreshold - self.RightPerfectThreshold)
        else:
            self.ContactQuality = 1.0 - (cbp - self.RightNiceThreshold) / (200.0 - self.RightNiceThreshold)

        # (AtBat_MoonShot is always False here, so its block is skipped.)

        swing = self.Batter_Contact_SlapChargeBuntStar
        if swing in (T.Slap, T.Charge):
            self.Batter_HitType = T.SourSlap
            if self.Batter_ContactType == T.Perfect:
                self.Batter_HitType = T.PerfectSlap
            elif self.Batter_ContactType in (T.LeftNice, T.RightNice):
                self.Batter_HitType = T.NiceSlap
            if self.ChargePitchType == T.PitchChargeType_Perfect:
                self.Batter_HitType += T.PerfectPitchSourSlap if swing == T.Slap else T.PerfectPitchSourCharge
            else:
                if self.Pitcher_TypeOfPitch == T.PitchCurve:
                    if swing != T.Slap:
                        self.Batter_HitType += T.SourCharge
                else:
                    self.Batter_HitType += T.SourChangeUpSlap if swing == T.Slap else T.SourChangeUpCharge

    # -- calculateHorizontalAngle --
    def calculate_horizontal_angle(self):
        is_charge = 0 if self.Batter_Contact_SlapChargeBuntStar == T.Slap else 1
        input_direction = T.PushPullNone
        if self.AtBat_Mystery_BatDirection == 0:
            if not self.input_right:
                if self.input_left:
                    input_direction = T.PullStickTowardsHitting if self.AtBat_BatterHand == T.Righty else T.PushStickAway
            elif self.AtBat_BatterHand == T.Righty:
                input_direction = T.PushStickAway
            else:
                input_direction = T.PullStickTowardsHitting

        frame = self.Frame_SwingContact1
        rng = T.BattingAngleRanges[input_direction][is_charge][frame]
        if self.removeSlice:
            rng = T.REMOVE_SLICE_ANGLE_OVERRIDES.get((input_direction, is_charge, frame), rng)
        i_low = rng[0]
        i_span = rng[1] - rng[0]
        if i_span < 0:
            i_low += self.s1 - _jfloor(self.s1 / -i_span) * -i_span
        elif i_span > 0:
            i_low += self.s1 - _jfloor(self.s1 / i_span) * i_span
        i_low += 0x400
        if self.AtBat_BatterHand != T.Righty:
            i_low = (0x800 - i_low) if i_low < 0x801 else (0x1800 - i_low)
        self.Hit_HorizontalAngle = _adjust_ball_angle(i_low)

    # -- calculateVerticalAngle --
    def calculate_vertical_angle(self):
        i_var5 = 0
        up_down = 0
        slap_or_charge = 0 if self.Batter_Contact_SlapChargeBuntStar == 0 else 1
        handled_zones = False
        lower = higher = 0

        captain_star = self.AtBat_Mystery_CaptainStarSwing
        if captain_star == 0:
            if not self.AtBat_MoonShot:
                noncap = self.nonCaptainStarSwingContact
                if noncap == 0:
                    if self.AtBat_Mystery_BatDirection == 0:
                        if not self.input_up:
                            if self.input_down:
                                up_down = 2
                        else:
                            up_down = 1

                    weights = T.BattingVerticalAngleWeights[self.AtBat_HitTrajectoryLow][slap_or_charge][self.EasyBatting][self.Batter_ContactType]
                    w0, w1, w2, w3, w4 = weights

                    u4 = T.UINT_ARRAY_ARRAY_807b7134[self.Batter_HitType][3 - self.EasyBatting]
                    u6 = T.UINT_ARRAY_ARRAY_807b7134[self.Batter_HitType][4]
                    u5 = u4 & 0xF000000
                    if u5 == 0:
                        u16 = u4 & 0xF
                        if u16 != 0:
                            i_var5 = 2
                            if u16 == 2:
                                if up_down == 2:
                                    i_var5 = 0
                                    u6 = 2
                            elif u16 == 3 and up_down == 1:
                                i_var5 = 0
                                u6 = 2
                    else:
                        i_var5 = 1
                        if u5 == 0x2000000:
                            if up_down == 2:
                                i_var5 = 0
                                u6 = 2
                        elif u5 == 0x3000000 and up_down == 1:
                            i_var5 = 0
                            u6 = 2

                    if i_var5 == 0:
                        if (u4 & 0x1E0) == 0:
                            w0 = 0
                        if (u4 & 0xF0) == 0:
                            w1 = 0
                        if (u4 & 0x78) == 0:
                            w2 = 0
                        if (u4 & 0x3C) == 0:
                            w3 = 0
                        if (u4 & 0x1E) == 0:
                            w4 = 0
                        if up_down == 2:
                            w4 += w0
                            w0 = 0
                        elif up_down == 1:
                            tmp = w4 + w0
                            w4 = 0
                            w0 = w3 + tmp
                            w3 = 0

                    if i_var5 == 0:
                        idx = self._weighted_random_index([w0, w1, w2, w3, w4], 5)
                        zone = T.SHORT_ARRAY_ARRAY_ARRAY_ARRAY_807b67cc[slap_or_charge][self.Batter_ContactType][idx]
                        lower, higher = zone[0], zone[1]
                        handled_zones = True
                    else:
                        lower, higher = T.SHORT_ARRAY_ARRAY_807b6af4[i_var5]
                else:
                    rng = T.NonCaptainStarSwingBattingVerticalAngleRanges[noncap - 1][self.Batter_ContactType]
                    lower, higher = rng[0], rng[1]
            else:
                zone = T.SHORT_ARRAY_ARRAY_ARRAY_ARRAY_807b67cc[1][self.Batter_ContactType][2]
                lower, higher = zone[0], zone[1]
        else:
            rng = T.CaptainStarSwingBattingVerticalAngleRanges[captain_star - 1][self.Batter_ContactType]
            lower, higher = rng[0], rng[1]

        span = higher - lower
        if span == 0:
            s_var3 = lower
        else:
            s_var3 = lower + (self.s1 - _jfloor(self.s1 / span) * span)
        self.Hit_VerticalAngle = s_var3

        if self.Hit_VerticalAngle < 0x401:
            if self.Hit_VerticalAngle < -0x400:
                self.Hit_VerticalAngle += 0x1000
                self.Hit_HorizontalAngle = _adjust_ball_angle(self.Hit_HorizontalAngle + 0x800)
            elif self.Hit_VerticalAngle < 0:
                self.Hit_VerticalAngle += 0x1000
        else:
            self.Hit_VerticalAngle = 0x800 - self.Hit_VerticalAngle
            self.Hit_HorizontalAngle = _adjust_ball_angle(self.Hit_HorizontalAngle + 0x800)

    # -- calculateHitPower --
    def calculate_hit_power(self):
        nice_sour = self.Batter_ContactType
        charged = self.BatterAtPlate_BatterCharge_Up
        contact_array = T.BallHitArray[self.Batter_Contact_SlapChargeBuntStar][nice_sour]

        if self.AtBat_Mystery_CaptainStarSwing == 0:
            if self.nonCaptainStarSwingContact != 0:
                charged = 0.0
                contact_array = T.StarSwingExitVelocityArray[self.nonCaptainStarSwingContact - 1][nice_sour]
        else:
            charged = 0.0
            contact_array = T.CaptainStarSwingExitVelocityArray[self.AtBat_Mystery_CaptainStarSwing - 1][nice_sour]

        if self.AtBat_Mystery_DidPopFlyOrGrounderConnect:
            self.BatterAtPlate_BatterCharge_Down = 1.0

        if self.AtBat_MoonShot:
            contact_array = T.BallHitArray[1][self.Batter_ContactType]

        v1, v2 = contact_array[0], contact_array[1]
        calced_distance = self.ContactQuality * (v2 - v1) + v1

        if self.AtBat_Mystery_CaptainStarSwing == 0:
            if charged <= 0.0:
                power = self.Batter_SlapHitPower
            else:
                power = (self.BatterAtPlate_ChargePower
                         - (self.BatterAtPlate_ChargePower - self.Batter_SlapHitPower)
                         * 0.5 * (1.0 - self.BatterAtPlate_BatterCharge_Down))
        else:
            power = 100.0

        if self.AtBat_Mystery_CaptainStarSwing == 0 and self.nonCaptainStarSwingContact == 0:
            if self.Batter_ContactType in (T.LeftNice, T.RightNice):
                pns = 1
            elif self.Batter_ContactType == T.Perfect:
                pns = 0
            else:
                pns = 2
            d = _linear_interpolate(self.cursed_ball, 0.0, 100.0,
                                    T.FLOAT_ARRAY_ARRAY_807b7480[pns][0],
                                    T.FLOAT_ARRAY_ARRAY_807b7480[pns][1])
            power = power * d

        if self.RandomBattingFactors_ChemLinksOnBase != 0 and 0.0 < charged:
            power = power * T.RandomBattingFactors_ChemLinkMult0[self.RandomBattingFactors_ChemLinksOnBase]

        if -1 < self.Batter_HitType:
            power = (power * T.UINT_ARRAY_ARRAY_807b7134[self.Batter_HitType][1 - self.EasyBatting]) / 100.0

        f = calced_distance * ((power / 100.0) * (1.0 - 0.8) + 0.8)
        self.AddedContactGravity = 0.00001 * contact_array[2]

        if self.AtBat_Mystery_CaptainStarSwing == 0:
            ball_angle = self.Hit_HorizontalAngle
            if ball_angle < 0x200:
                ns = 0
            elif ball_angle < 0x601:
                ns = ball_angle - 0x200
            else:
                ns = 0x400
            if self.AtBat_BatterHand != T.Righty:
                ns = 0x400 - ns
            if ns < 0x100:
                seg = 0
            elif ns < 0x200:
                seg = 1
                ns -= 0x100
            elif ns < 0x300:
                seg = 2
                ns -= 0x200
            else:
                seg = 3
                ns -= 0x300
            traj = T.FieldTrajectories[self.BatterAtPlate_TrajectoryNearFar]
            field_bonus = _linear_interpolate(ns / 256, 0.0, 1.0, traj[seg], traj[seg + 1])
            f = f * field_bonus

        if self.AtBat_MoonShot:
            f = f * _MOONSHOT_MULTIPLIER

        self.Hit_HorizontalPower = _jfloor(f)

    # -- convertPowerToVelocity --
    def convert_power_to_velocity(self):
        half_power = self.Hit_HorizontalPower * 0.5
        h_angle = _mssb_to_radians(self.Hit_HorizontalAngle)
        v_angle = _mssb_to_radians(self.Hit_VerticalAngle)

        s_vert = math.sin(v_angle)
        c_vert = math.cos(v_angle)
        half_power_x_cos = half_power * c_vert
        c_horiz = math.cos(h_angle)
        s_horiz = math.sin(h_angle)

        x_ground = c_horiz * half_power_x_cos
        z_ground = s_horiz * half_power_x_cos

        self.ballVelocity = [x_ground / 100.0, (half_power * s_vert) / 100.0, z_ground / 100.0]
        self.ballAcceleration = [0.0, self.AddedContactGravity, 0.0]

        if not self.Batter_IsBunting and (self.Hit_HorizontalAngle < 0x901 or 0xEFF < self.Hit_HorizontalAngle):
            has_super_curve = 1 if self.b.has_super_curve else 0
            if self.nonCaptainStarSwingContact == 3:
                has_super_curve = 1

            contact = self.CalculatedBallPos
            if 100.0 < self.CalculatedBallPos:
                contact = 200.0 - self.CalculatedBallPos

            v_ang = self.Hit_VerticalAngle
            f = 1.0 - (1.0 - contact * 0.01) * T.FLOAT_ARRAY_ARRAY_807b72bc[has_super_curve][0]
            if 0x180 < v_ang < 0x401:
                u = v_ang - 0x180
                contact = min(u, 512.0)
                f = f * (1.0 - contact * 1.0 / 512.0)

            h_ang = self.Hit_HorizontalAngle
            if h_ang < 0xC01 and 0xFF < h_ang:
                if 0x700 < h_ang:
                    h_ang = 0x700
            else:
                h_ang = 0x100
            if self.AtBat_BatterHand != T.Righty:
                h_ang = 0x800 - h_ang
            if h_ang < 0x460:
                contact = (0x460 - h_ang) / 864.0
            else:
                contact = (0x460 - h_ang) / 672.0

            contact = f * contact
            if contact >= 0.0:
                if contact > 0.0:
                    z_ground = -c_horiz
                    x_ground = s_horiz
            else:
                contact = -contact
                z_ground = c_horiz
                x_ground = -s_horiz

            self.ballAcceleration[2] = (z_ground * contact) * T.FLOAT_ARRAY_ARRAY_807b72bc[has_super_curve][2]
            self.ballAcceleration[0] = (x_ground * contact) * T.FLOAT_ARRAY_ARRAY_807b72bc[has_super_curve][1]
            if self.ballAcceleration[2] > 0.0:
                self.ballAcceleration[2] = -self.ballAcceleration[2]
            if self.AtBat_BatterHand != T.Righty:
                self.ballAcceleration[0] = -self.ballAcceleration[0]

    # -- CalculateHitVariables tail (runs after CalculateBallVelocityAcceleration) --
    def _calculate_star_state(self):
        """Derive BallEnergy and the Wario/Waluigi garlic direction, mirroring the
        captain-star tail of CalculateHitVariables. Called after
        convert_power_to_velocity so any RNG draw lands in the game's order."""
        cap = self.AtBat_Mystery_CaptainStarSwing
        # Regular charge energy: a fully-charged, non-captain-star, non-sour
        # contact arms the ball (BallEnergy = hit power). The Ghidra sour test
        # rendered oddly; "not sour" (Nice/Perfect) is the intent.
        if (cap == 0
                and self.Batter_ContactType not in (T.LeftSour, T.RightSour)
                and self.BatterAtPlate_BatterCharge_Up >= 1.0):
            self.BallEnergy = float(self.Hit_HorizontalPower)
        # Bowser / Bowser Jr bullet star: 4x energy (metadata only -- the flat
        # flight already comes from the captain-star exit-velocity table).
        if cap in T.BULLET_CAPTAIN_STARS:
            self.BallEnergy = self.Hit_HorizontalPower * T.BULLET_STAR_ENERGY_MULT
        # Wario / Waluigi: warioWaluStarHitDirection = RandomInt_Game(2) unless the
        # caller forced it (drawn here to match the game's RNG consumption order).
        if cap in T.GARLIC_CAPTAIN_STARS and self.warioWaluStarHitDirection is None:
            self.warioWaluStarHitDirection = self._random_int_game(2)

    # -- calculateHitGround (per-frame loop of liveBallHitPhysics) --
    def _straight_hangtime(self) -> int:
        """Frames to first ground contact with no star modifiers applied -- the
        game's hangtimeOfHit / framesUntilBallHitsGround, which both the banana
        window and the garlic split are scheduled against (they are computed from
        the un-curved flight)."""
        self._build_trajectory(_apply_specials=False)
        return self._landed_at if self._landed_at is not None else 0

    def _banana_active(self) -> bool:
        return self.AtBat_Mystery_CaptainStarSwing in T.BANANA_CAPTAIN_STARS

    def _banana_window(self):
        """Resolve (start_frame, end_frame, direction) for the DK/Diddy banana
        hit, applying the game's rules (CalculateHitVariables) for any field left
        as None: the window is 0.25x..0.95x of the straight-flight hang time and
        the direction is the batter's hand."""
        direction = self.directionOfBananaHit
        if direction is None:
            direction = self.AtBat_BatterHand
        start = self.bananaHitStartFrame
        end = self.bananaHitEndFrame
        if start is None or end is None:
            hangtime = self._straight_hangtime()
            if start is None:
                start = math.trunc(hangtime * T.DK_DIDDY_STAR_HANGTIME_START)
            if end is None:
                end = math.trunc(hangtime * T.DK_DIDDY_STAR_HANGTIME_END)
        return start, end, direction

    def _garlic_active(self) -> bool:
        return self.AtBat_Mystery_CaptainStarSwing in T.GARLIC_CAPTAIN_STARS

    def _garlic_params(self):
        """Resolve (split_frame, spread_plus, spread_minus, direction) for the
        Wario/Waluigi garlic hit. The ball splits GARLIC_SPLIT_FRAMES_BEFORE_GROUND
        frames before it would land (warioWaluStarHit fires on
        framesUntilBallHitsGround == that), i.e. at straight_hangtime - 120. Each
        side's heading offset is an independent randomInRange(0.2, 0.3) draw (the
        +side first, matching warioWaluStarHit's RNG order); a forced garlic_spread
        overrides both with one symmetric value."""
        direction = self.warioWaluStarHitDirection
        if direction is None:
            direction = 0
        if self.garlicSpread is None:
            spread_plus = self._random_in_range(T.GARLIC_SPREAD_LOWER, T.GARLIC_SPREAD_UPPER)
            spread_minus = self._random_in_range(T.GARLIC_SPREAD_LOWER, T.GARLIC_SPREAD_UPPER)
        else:
            spread_plus = spread_minus = self.garlicSpread
        split_frame = self._straight_hangtime() - T.GARLIC_SPLIT_FRAMES_BEFORE_GROUND
        return split_frame, spread_plus, spread_minus, direction

    def _build_trajectory(self, max_frames=None, _apply_specials=True):
        """Integrate the flight, semi-implicit Euler as in liveBallHitPhysics.

        Aerial mode (``max_frames`` None): fly until the first ground contact,
        then one extra frame -- the stat file records the landing one frame after
        contact -- and stop. This is the wall-free aerial landing.

        Fixed mode (``max_frames`` = N): integrate exactly N frames, continuing
        through ground contacts. On stadiums with the blanket flat-ground bounce
        (``HitInputs.bounce``) a downward Y velocity is reversed; on Bowser Castle
        / Toy Field (holes in the ground, so no blanket bounce) we approximate
        their unported ballCollisionLogic by pinning the ball to the ground plane
        and killing its downward Y velocity (a skid). Used to walk a
        grounder/liner along the ground for testing.
        """
        # Start at the ball's world contact position (the game integrates from
        # AtBat_Contact_BallPos, which is offset from home plate, not the origin).
        # The recorded contact X is batter-relative (mirrored about the plate for
        # lefties), whereas velocity and landing are world-frame, so mirror the X
        # start for lefties -- the same handedness flip the curve applies to
        # ballAcceleration[0]. Z (depth) is not handed.
        start_x = -self.ballContact_X if self.AtBat_BatterHand != T.Righty else self.ballContact_X
        px, py, pz = start_x, self.b.pitching_height, self.inp.ball_z
        vx, vy, vz = self.ballVelocity
        ax, ay, az = self.ballAcceleration
        air = T.AIR_RESISTANCE
        grav = T.GRAVITY
        ground_y = self.inp.ground_y
        bounce = self.inp.bounce

        points = [(px, py, pz)]
        landed_at = None
        f = 0
        # Star modifiers resolve their timing from the straight flight, so they
        # are skipped on the internal straight pass (_apply_specials=False).
        # DK (5) / Diddy (6) banana: curve the horizontal velocity below.
        banana = _apply_specials and self._banana_active()
        if banana:
            banana_start, banana_end, banana_dir = self._banana_window()
        # Wario (3) / Waluigi (4) garlic: split into two balls near the ground.
        garlic = _apply_specials and self._garlic_active()
        if garlic:
            garlic_split_frame, garlic_spread_plus, garlic_spread_minus, garlic_dir = self._garlic_params()
            garlic_split_done = False
            garlic_pts = None
            gx = gy = gz = gvx = gvy = gvz = 0.0
        while True:
            # framesSinceLiveBall for this tick (the game increments it at the top
            # of liveBallHitPhysics, before the physics).
            f += 1
            # Decay velocity and add acceleration FIRST, then step the position
            # (and only then resolve the ground).
            vx = vx * air + ax
            vy = (vy - grav) * air + ay
            vz = vz * air + az
            # DK/Diddy banana star hit: while the window is open, rotate the
            # horizontal velocity by a fixed angle each frame (horizontal speed
            # preserved) -> the wide banana arc. Mirrors the DK/Diddy branch of
            # liveBallHitPhysics, inserted between the acceleration and position
            # steps. radianAngleToPoint(vx, vz) == atan2(vz, vx) so that
            # vx == cos(angle)*speed and vz == sin(angle)*speed.
            if banana and banana_start < f < banana_end:
                ground_speed = math.hypot(vx, vz)
                angle = math.atan2(vz, vx)
                if banana_dir == 0:   # Righty
                    angle -= T.DK_DIDDY_STAR_ANGLE_DELTA
                else:                 # Lefty
                    angle += T.DK_DIDDY_STAR_ANGLE_DELTA
                vx = math.cos(angle) * ground_speed
                vz = math.sin(angle) * ground_speed
            px += vx
            py += vy
            pz += vz
            # Wario/Waluigi garlic star hit. At the split frame the ball forks
            # into the real ball (kept as the main px/py/pz) and a garlic ball,
            # both starting here with the pre-split horizontal speed and vy but
            # headings offset +/- garlic_spread from the pre-split heading; which
            # side is real is warioWaluStarHitDirection. After the split both fly
            # under plain air+gravity (acceleration zeroed), per warioWaluStarHit.
            if garlic and not garlic_split_done and f == garlic_split_frame:
                speed = math.hypot(vx, vz)
                heading = math.atan2(vz, vx)
                plus_a = heading + garlic_spread_plus
                minus_a = heading - garlic_spread_minus
                if garlic_dir == 0:
                    real_a, garlic_a = minus_a, plus_a
                else:
                    real_a, garlic_a = plus_a, minus_a
                vx, vz = math.cos(real_a) * speed, math.sin(real_a) * speed
                ax = ay = az = 0.0
                gx, gy, gz = px, py, pz
                gvx, gvy, gvz = math.cos(garlic_a) * speed, vy, math.sin(garlic_a) * speed
                garlic_pts = [(gx, gy, gz)]
                garlic_split_done = True
            elif garlic and garlic_split_done:
                gvx = gvx * air
                gvy = (gvy - grav) * air
                gvz = gvz * air
                gx += gvx
                gy += gvy
                gz += gvz
                if gy < ground_y:
                    gy = ground_y
                    if gvy < 0.0:
                        gvy = -gvy if bounce else 0.0
                garlic_pts.append((gx, gy, gz))
            if py < ground_y:
                py = ground_y
                if vy < 0.0:
                    # bounce: blanket flat-ground reversal. skid: approximation of
                    # the unported ballCollisionLogic on hole stadiums (Bowser
                    # Castle / Toy Field), which have no blanket ground bounce.
                    vy = -vy if bounce else 0.0
                if landed_at is None:
                    landed_at = f
            points.append((px, py, pz))
            if max_frames is None:
                if landed_at is not None and f >= landed_at + 1:
                    break
            elif f >= max_frames:
                break
        self._landed_at = landed_at
        if garlic:
            self._garlic_trajectory = garlic_pts
        return points

    def calculate_hit_ground(self):
        self.trajectory = self._build_trajectory()

    # -- pipeline up to (but not including) the ground integration --
    def _pipeline(self):
        if not self.hit_ball():
            raise ValueError("These inputs would not make contact with the ball")
        self.calculate_contact()
        self.calculate_horizontal_angle()
        self.calculate_vertical_angle()
        self.calculate_hit_power()
        self.convert_power_to_velocity()
        self._calculate_star_state()

    # -- run the whole pipeline --
    def run(self) -> HitResult:
        self._pipeline()
        self.calculate_hit_ground()

        landing = self.trajectory[-1] if self.trajectory else (0.0, self.b.pitching_height, 0.0)
        return HitResult(
            contact_absolute=self.CalculatedBallPos,
            contact_type=self.Batter_ContactType,
            contact_type_name=_CONTACT_TYPE_NAMES[self.Batter_ContactType],
            contact_quality=self.ContactQuality,
            hit_type=self.Batter_HitType,
            horizontal_angle=self.Hit_HorizontalAngle,
            vertical_angle=self.Hit_VerticalAngle,
            horizontal_angle_deg=(self.Hit_HorizontalAngle - 0x400) * 360 / 4096,
            vertical_angle_deg=self.Hit_VerticalAngle * 360 / 4096,
            power=self.Hit_HorizontalPower,
            velocity=tuple(self.ballVelocity),
            acceleration=tuple(self.ballAcceleration),
            landing=landing,
            distance=math.sqrt(landing[0] ** 2 + landing[2] ** 2),
            hang_frames=len(self.trajectory),
            ball_energy=self.BallEnergy,
            trajectory=self.trajectory,
            garlic_trajectory=self._garlic_trajectory,
        )


# ---------------------------------------------------------------- public API

def simulate_hit(inputs: HitInputs) -> HitResult:
    """Run the full pipeline for an explicit set of inputs."""
    batter = BatterAttributes.from_name(inputs.batter_name, inputs.batter_stars_on)
    pitcher = PitcherAttributes.from_name(inputs.pitcher_name, inputs.pitcher_stars_on)
    return _HitSim(batter, pitcher, inputs).run()


def _int_no_commas(value) -> int:
    return int(str(value).replace(",", "")) if value is not None else 0


# Maps a ProjectRio gecko tag name to the HitInputs flag that models it, so the
# simulator reproduces a modded match's behavior rather than diverging from it.
TAG_TO_FLAG = {
    "Fix Non-red Toad Hitboxes and Bat Reach": "fix_non_red_toad_reach",
    "Remove slice": "remove_slice",
}


def _mod_flags_from_tags(active_tags) -> dict:
    """HitInputs mod-flag kwargs for the gecko tags active in a match."""
    return {flag: (tag in active_tags) for tag, flag in TAG_TO_FLAG.items()}


def _batter_is_off_captain(event: EventObj) -> bool:
    """True if the batter is a captain-class character (has a captain star hit)
    who is NOT this game's designated captain -- so a lone star can't be spent on
    their captain swing (see the Walu-tech check in _inputs_from_event)."""
    if BatterAttributes.from_name(event.batter()).captain_star_hit_pitch == 0:
        return False
    stat = event.rioStat
    team_str = stat.getTeamString(event.batting_team(), event.batter_roster_loc())
    return stat.statJson["Character Game Stats"][team_str].get("Captain") != 1


def _inputs_from_event(event: EventObj, active_tags=frozenset()) -> HitInputs:
    """Build HitInputs from a stat-file contact event.

    Mirrors the JS `useStatFileValues`. Requires the event to have contact
    (raises otherwise). Bunts (swing "None" with contact) are not supported.
    """
    pitch = event.pitch_dict()
    contact = event.contact_dict()
    if not contact:
        raise ValueError(f"Event {event.event_num()} has no contact to simulate")

    # Categorical fields may be decoded strings or encoded ints; coerce to codes
    # so the simulator works against either stat-file flavor.
    swing_code = G.to_encoded(G.TYPE_OF_SWING, pitch.get("Type of Swing"))
    if swing_code not in (1, 2, 3):  # 1 Slap, 2 Charge, 3 Star (0 None / 4 Bunt unsupported)
        raise ValueError(
            f"Unsupported swing type {pitch.get('Type of Swing')!r} (bunts not supported)"
        )

    charge_up = float(contact.get("Charge Power Up", 0.0))
    charge_down = float(contact.get("Charge Power Down", 0.0))

    # "Walu tech": an old-game bug where a star swing attempted without enough
    # stars to spend silently becomes a regular swing (charge if the batter was
    # charging, else slap) with charge-down forced to 0. The event is still
    # recorded as Type of Swing "Star" though no star is used, so detect it here.
    # Insufficient stars = the batting team has none, or has exactly one but the
    # batter is a captain-class character who isn't this game's captain (their
    # captain swing can't be fueled by that lone star). Fixed in newer games.
    if swing_code == 3:
        stars = event.team_stars(event.batting_team())
        if stars == 0 or (stars == 1 and _batter_is_off_captain(event)):
            swing_code = 2  # regular Charge swing...
            charge_down = 0.0  # ...with charge-down forced to 0 (the power benefit)

    pitch_code = G.to_encoded(G.PITCH_TYPE, pitch.get("Pitch Type"))  # 0 Curve/1 Charge/2 ChangeUp
    if pitch_code == 0:
        pitch_type_val = 0
    elif pitch_code == 1:
        charge_code = G.to_encoded(G.CHARGE_PITCH_TYPE, pitch.get("Charge Type"))  # 2 Slider/3 Perfect
        pitch_type_val = 1 if charge_code == 2 else 2
    else:
        pitch_type_val = 3

    batting_team = event.half_inning()
    pitching_team = event.pitching_team()
    batter_starred = bool(event.rioStat.isStarred(batting_team, event.batter_roster_loc()))
    pitcher_starred = bool(event.rioStat.isStarred(pitching_team, event.pitcher_roster_loc()))

    up, down, left, right = G.stick_directions(contact.get("Input Direction - Stick"))

    # Toy Field's ground plane sits higher; Bowser Castle / Toy Field skid.
    stadium_code = G.to_encoded(G.STADIUM_ID_TO_NAME, event.rioStat.stadium())
    ground_y = T.GROUND_Y_TOY_FIELD if stadium_code == 0x6 else T.GROUND_Y_DEFAULT
    bounce = stadium_code in T.BOUNCING_STADIUM_IDS

    return HitInputs(
        batter_name=event.batter(),
        pitcher_name=event.pitcher(),
        pitch_type_val=pitch_type_val,
        pos_x=pitch.get("Bat Contact Pos - X"),
        ball_x=contact.get("Ball Contact Pos - X"),
        ball_z=float(contact.get("Ball Contact Pos - Z", 0.0)),
        batter_hand=G.to_encoded(G.HAND, event.batter_hand()),  # 0 Right/1 Left == T.Righty/T.Lefty
        swing=T.Charge if swing_code == 2 else T.Slap,
        is_star=swing_code == 3,
        charge_up=charge_up,
        charge_down=charge_down,
        chem_links=event.chem_links_on_base(),
        frame=_int_no_commas(contact.get("Frame of Swing Upon Contact")),
        input_up=up,
        input_down=down,
        input_left=left,
        input_right=right,
        easy_batting=False,  # not recorded in stat files
        batter_stars_on=batter_starred,
        pitcher_stars_on=pitcher_starred,
        ground_y=ground_y,
        bounce=bounce,
        rng1=_int_no_commas(contact.get("RNG1")),
        rng2=_int_no_commas(contact.get("RNG2")),
        rng3=_int_no_commas(contact.get("RNG3")),
        **_mod_flags_from_tags(active_tags),
    )


def simulate_hit_from_event(event: EventObj, active_tags=frozenset()) -> HitResult:
    """Build HitInputs from a stat-file contact event and simulate it.

    ``active_tags`` is the set of gecko-mod tag names active for the match (see
    rio_tags); recognized mods (TAG_TO_FLAG) are modeled instead of diverging.
    """
    return simulate_hit(_inputs_from_event(event, active_tags))


def simulate_hit_trajectory(inputs: HitInputs, frames: int) -> list:
    """Full bounce-inclusive (x, y, z) trajectory integrated for ``frames`` frames.

    Unlike ``simulate_hit`` -- whose ``HitResult.trajectory`` stops at the
    wall-free aerial landing -- this continues through ground contacts using the
    bounce/skid physics (per ``HitInputs.bounce``). Intended for testing, e.g.
    walking a grounder along the ground to a known hang time. Returns
    ``frames + 1`` points (index 0 is the contact point, index ``frames`` is the
    position after ``frames`` integration steps).
    """
    batter = BatterAttributes.from_name(inputs.batter_name, inputs.batter_stars_on)
    pitcher = PitcherAttributes.from_name(inputs.pitcher_name, inputs.pitcher_stars_on)
    sim = _HitSim(batter, pitcher, inputs)
    sim._pipeline()
    return sim._build_trajectory(max_frames=frames)


def simulate_hit_trajectory_from_event(event: EventObj, frames: int,
                                       active_tags=frozenset()) -> list:
    """``simulate_hit_trajectory`` for a stat-file contact event."""
    return simulate_hit_trajectory(_inputs_from_event(event, active_tags), frames)

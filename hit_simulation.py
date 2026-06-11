"""Port of the MSSB batting calculator (index.js) -> hit info + trajectory.

Pipeline (per the JS): parse -> calculateContact -> calculateHorizontalAngle ->
calculateVerticalAngle -> calculateHitPower -> convertPowerToVelocity ->
calculateHitGround. Given the three RNG seeds it is fully deterministic, so a
recorded event's RNG1/RNG2/RNG3 reproduces that event's contact exactly.

Public API:
    simulate_hit(HitInputs) -> HitResult            # pure core
    simulate_hit_from_event(EventObj) -> HitResult  # stat-file adapter

Character attributes are loaded by NAME from character_attributes_stoff.csv (the
star-OFF table == the JS `stats` base values); the JS's flat +50 superstar buff
is applied to slap/charge power (batter) and cursed ball (pitcher). This mirrors
the calculator rather than pyrio's measured `ston` table, so the port reproduces
the calculator/game; swap the loader to `ston` later if desired.

Notes / known JS quirks carried over:
  - Moonshot (`AtBat_MoonShot`) is unreachable here: the JS hardcodes
    starsForBatter = 4, so the moonshot branch (needs >= 5) never runs. Its
    undefined `AtBat_MoonShotMultiplier` therefore never matters.
  - Super curve is keyed by character NAME (hit_sim_tables.SUPER_CURVE_CHARACTERS)
    instead of the JS's hardcoded char ids.
"""
from __future__ import annotations

import csv
import math
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

from . import hit_sim_tables as T
from .stat_file_parser import EventObj

_STOFF_CSV = Path(__file__).parent / "character_attributes_stoff.csv"
_SUPERSTAR_BUFF = 50  # JS batterStarsOnIncrease / pitcherStarsOnIncrease

# JS leaves AtBat_MoonShotMultiplier undefined; the branch is unreachable here
# (starsForBatter is hardcoded 4), so this value is never actually used.
_MOONSHOT_MULTIPLIER = 1.0

_HORIZ_TRAJ = {"Mid": 0, "Pull": 1, "Push": 2}
_VERT_TRAJ = {"Mid": 0, "High": 1, "Low": 2}
_CONTACT_TYPE_NAMES = ["Left Sour", "Left Nice", "Perfect", "Right Nice", "Right Sour"]


# ---------------------------------------------------------------- JS helpers

def _jfloor(x: float) -> int:
    """The JS `floor` is Math.trunc (toward zero), not Math.floor."""
    return math.trunc(x)


def _to_int32(x: int) -> int:
    x &= 0xFFFFFFFF
    return x - 0x100000000 if x & 0x80000000 else x


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
    global _attr_rows
    if _attr_rows is None:
        with open(_STOFF_CSV, newline="") as f:
            _attr_rows = {row["Character"]: row for row in csv.DictReader(f)}
    return _attr_rows


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
    def from_name(cls, name: str, stars_on: bool = False) -> "BatterAttributes":
        row = _load_attr_rows()[name]
        buff = _SUPERSTAR_BUFF if stars_on else 0
        cap, ncs = T.BATTER_STAR_FIELDS[name]
        return cls(
            name=name,
            slap_hit_power=int(row["Slap Hit Power"]) + buff,
            charge_power=int(row["Charge Hit Power"]) + buff,
            slap_contact_size=int(row["Slap Contact Size Multiplier"]),
            charge_contact_size=int(row["Charge Contact Size Multiplier"]),
            bunting=int(row["Bunting"]),
            horizontal_trajectory=_HORIZ_TRAJ[row["Horizontal Hit Trajectory"]],
            vertical_trajectory=_VERT_TRAJ[row["Vertical Hit Trajectory"]],
            captain_star_hit_pitch=cap,
            non_captain_star_swing=ncs,
            horizontal_range_near=float(row["Horizontal Range Near"]),
            horizontal_range_far=float(row["Horizontal Range Far"]),
            trimmed_bat=int(float(row["Trimmed Bat"])),
            pitching_height=float(row["Pitching Height"]),
            has_super_curve=name in T.SUPER_CURVE_CHARACTERS,
        )


@dataclass
class PitcherAttributes:
    name: str
    cursed_ball: int

    @classmethod
    def from_name(cls, name: str, stars_on: bool = False) -> "PitcherAttributes":
        row = _load_attr_rows()[name]
        buff = _SUPERSTAR_BUFF if stars_on else 0
        return cls(name=name, cursed_ball=int(row["Cursed Ball"]) + buff)


# ---------------------------------------------------------------- I/O structs

@dataclass
class HitInputs:
    batter_name: str
    pitcher_name: str
    # pitch: 0 Curve, 1 Charge(Slider), 2 Perfect Charge, 3 ChangeUp
    pitch_type_val: int
    pos_x: float                 # batter X at contact
    ball_x: float                # ball X at contact
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
    trajectory: list = field(repr=False)     # list of (x, y, z) per frame


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
        self.trajectory: list = []

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
            cbp = 100.0 * (diff / self.b.horizontal_range_far) + 100.0
        else:
            cbp = -(100.0 * (diff / self.b.horizontal_range_near) - 100.0)
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

    # -- calculateHitGround --
    def calculate_hit_ground(self):
        px, py, pz = 0.0, self.b.pitching_height, 0.0
        vx, vy, vz = self.ballVelocity
        ax, ay, az = self.ballAcceleration
        air = T.AIR_RESISTANCE
        grav = T.GRAVITY

        points = []
        while py > 0:
            points.append((px, py, pz))
            px += vx
            py += vy
            pz += vz
            vx = vx * air + ax
            vy = (vy - grav) * air + ay
            vz = vz * air + az
        self.trajectory = points

    # -- run the whole pipeline --
    def run(self) -> HitResult:
        if not self.hit_ball():
            raise ValueError("These inputs would not make contact with the ball")
        self.calculate_contact()
        self.calculate_horizontal_angle()
        self.calculate_vertical_angle()
        self.calculate_hit_power()
        self.convert_power_to_velocity()
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
            trajectory=self.trajectory,
        )


# ---------------------------------------------------------------- public API

def simulate_hit(inputs: HitInputs) -> HitResult:
    """Run the full pipeline for an explicit set of inputs."""
    batter = BatterAttributes.from_name(inputs.batter_name, inputs.batter_stars_on)
    pitcher = PitcherAttributes.from_name(inputs.pitcher_name, inputs.pitcher_stars_on)
    return _HitSim(batter, pitcher, inputs).run()


def _int_no_commas(value) -> int:
    return int(str(value).replace(",", "")) if value is not None else 0


def simulate_hit_from_event(event: EventObj) -> HitResult:
    """Build HitInputs from a stat-file contact event and simulate it.

    Mirrors the JS `useStatFileValues`. Requires the event to have contact
    (raises otherwise). Bunts (swing "None" with contact) are not supported.
    """
    pitch = event.pitch_dict()
    contact = event.contact_dict()
    if not contact:
        raise ValueError(f"Event {event.event_num()} has no contact to simulate")

    swing_type = pitch.get("Type of Swing")
    if swing_type not in ("Slap", "Charge", "Star"):
        raise ValueError(f"Unsupported swing type {swing_type!r} (bunts not supported)")

    pitch_name = pitch.get("Pitch Type")
    if pitch_name == "Curve":
        pitch_type_val = 0
    elif pitch_name == "Charge":
        pitch_type_val = 1 if pitch.get("Charge Type") == "Slider" else 2
    else:
        pitch_type_val = 3

    batting_team = event.half_inning()
    pitching_team = event.pitching_team()
    batter_starred = bool(event.rioStat.isStarred(batting_team, event.batter_roster_loc()))
    pitcher_starred = bool(event.rioStat.isStarred(pitching_team, event.pitcher_roster_loc()))

    stick = contact.get("Input Direction - Stick", "") or ""

    inputs = HitInputs(
        batter_name=event.batter(),
        pitcher_name=event.pitcher(),
        pitch_type_val=pitch_type_val,
        pos_x=pitch.get("Bat Contact Pos - X"),
        ball_x=contact.get("Ball Contact Pos - X"),
        batter_hand=T.Righty if event.batter_hand() == "Right" else T.Lefty,
        swing=T.Charge if swing_type == "Charge" else T.Slap,
        is_star=swing_type == "Star",
        charge_up=float(contact.get("Charge Power Up", 0.0)),
        charge_down=float(contact.get("Charge Power Down", 0.0)),
        chem_links=event.chem_links_on_base(),
        frame=_int_no_commas(contact.get("Frame of Swing Upon Contact")),
        input_up="Up" in stick,
        input_down="Down" in stick,
        input_left="Left" in stick,
        input_right="Right" in stick,
        easy_batting=False,  # not recorded in stat files
        batter_stars_on=batter_starred,
        pitcher_stars_on=pitcher_starred,
        rng1=_int_no_commas(contact.get("RNG1")),
        rng2=_int_no_commas(contact.get("RNG2")),
        rng3=_int_no_commas(contact.get("RNG3")),
    )
    return simulate_hit(inputs)

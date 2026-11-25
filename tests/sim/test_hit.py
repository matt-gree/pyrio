"""The hit simulation's interface and the game's rules it applies."""

from __future__ import annotations

from dataclasses import replace

import pytest

from pyrio import (
    CaptainStar,
    Character,
    ChargeType,
    ContactType,
    Hand,
    InputDirection,
    MoonshotStatus,
    PitchType,
    Stadium,
    SwingType,
)
from pyrio.sim import (
    TAG_TO_MOD,
    HitInputs,
    HitOverrides,
    HitResult,
    Mod,
    simulate_all_zones,
    simulate_hit,
    simulate_trajectory,
)

BASE = HitInputs(
    batter=Character.MARIO,
    pitcher=Character.MARIO,
    pitch=PitchType.CURVE,
    swing=SwingType.CHARGE,
    hand=Hand.RIGHT,
    batter_x=0.0,
    ball_x=0.0,
    charge_up=1.0,
    charge_down=1.0,
)
STAR = replace(BASE, swing=SwingType.STAR, charge_up=0.0, charge_down=0.0)


def same_hit(a: HitResult, b: HitResult) -> bool:
    return (a.contact_type, a.power, a.trajectory) == (b.contact_type, b.power, b.trajectory)


# --- the result ------------------------------------------------------------------


def test_a_centred_charge_swing_is_perfect():
    hit = simulate_hit(BASE)
    assert hit.contact_type is ContactType.PERFECT
    assert hit.contact_absolute == 100.0
    assert hit.trajectory[0] == (0.0, Character.MARIO.attributes.pitching_height, 0.0)
    assert hit.landing == hit.trajectory[-1]
    assert hit.hang_frames == len(hit.trajectory)
    assert hit.distance == pytest.approx((hit.landing[0] ** 2 + hit.landing[2] ** 2) ** 0.5)
    assert hit.apex_height >= hit.trajectory[0][1]
    assert hit.star_swing is None
    assert hit.moonshot is MoonshotStatus.NONE
    assert hit.garlic_trajectory is None


def test_out_of_reach_raises():
    with pytest.raises(ValueError, match="reach"):
        simulate_hit(replace(BASE, ball_x=2.0))


def test_the_ground_comes_from_the_stadium():
    mario = simulate_hit(BASE).trajectory
    toy = simulate_hit(replace(BASE, stadium=Stadium.TOY_FIELD)).trajectory
    assert min(p[1] for p in mario) == 0.15
    assert min(p[1] for p in toy) == 0.35
    assert toy[-1][1] == 0.35  # Toy Field's floor has holes, so no blanket bounce
    assert mario[-1][1] > 0.15  # Mario Stadium's bounces


def test_simulate_trajectory_runs_a_fixed_number_of_frames():
    points = simulate_trajectory(BASE, 400)
    assert len(points) == 401
    assert points[: simulate_hit(BASE).hang_frames] == simulate_hit(BASE).trajectory


def test_simulate_all_zones_gives_five_hits():
    hits = simulate_all_zones(BASE)
    assert len(hits) == 5
    assert len({h.vertical_angle_raw for h in hits}) > 1


def test_overrides_force_their_decision():
    assert simulate_hit(replace(BASE, overrides=HitOverrides(power=999))).power == 999
    forced = simulate_hit(replace(BASE, overrides=HitOverrides(horizontal_angle_raw=0x500)))
    assert forced.horizontal_angle_raw == 0x500


# --- validation ------------------------------------------------------------------


@pytest.mark.parametrize("swing", [SwingType.BUNT, SwingType.NONE])
def test_only_slap_charge_and_star_swings(swing: SwingType):
    with pytest.raises(ValueError, match="only slap, charge, star"):
        replace(BASE, swing=swing)


def test_a_charge_pitch_needs_its_charge_type():
    with pytest.raises(ValueError, match="charge type"):
        replace(BASE, pitch=PitchType.CHARGE)
    with pytest.raises(ValueError, match="charge type"):
        replace(BASE, charge=ChargeType.SLIDER)
    replace(BASE, pitch=PitchType.CHARGE, charge=ChargeType.PERFECT)
    replace(BASE, charge=ChargeType.NONE)  # the stat file's "N/A" for a curve


@pytest.mark.parametrize(
    ("field", "value"), [("stars", 6), ("stars", -1), ("chem_links_on_base", 4)]
)
def test_counts_are_range_checked(field: str, value: int):
    with pytest.raises(ValueError, match=field):
        replace(BASE, **{field: value})


# --- star swings: the game's calculateHitVariables --------------------------------


def test_a_captain_spends_one_star_on_their_captain_star_swing():
    hit = simulate_hit(replace(STAR, stars=1, is_captain=True))
    assert hit.star_swing is CaptainStar.FIREBALL


def test_a_captain_class_batter_who_is_not_captain_needs_two_stars():
    assert simulate_hit(replace(STAR, stars=1)).star_swing is None
    assert simulate_hit(replace(STAR, stars=2)).star_swing is CaptainStar.FIREBALL


def test_anyone_else_spends_one_star_on_their_own_star_swing():
    for batter in Character:
        if batter.attributes.captain_star is not None:
            continue
        hit = simulate_hit(replace(STAR, batter=batter, stars=1))
        assert hit.star_swing is batter.attributes.star_swing, batter


def test_without_the_stars_a_star_swing_is_a_plain_swing_from_zero_charge():
    for stars in (0, 1):
        slap = simulate_hit(replace(STAR, stars=stars))
        assert same_hit(slap, simulate_hit(replace(BASE, swing=SwingType.SLAP, charge_up=0.0)))
        charging = simulate_hit(replace(STAR, stars=stars, charge_up=0.5))
        expect = simulate_hit(replace(BASE, charge_up=0.0, charge_down=0.0))
        assert same_hit(charging, expect)


def test_a_star_swing_starts_from_zero_charge():
    a = simulate_hit(replace(STAR, stars=3, charge_up=0.7, charge_down=1.0))
    b = simulate_hit(replace(STAR, stars=3))
    assert same_hit(a, b)


def test_a_fully_charged_five_star_swing_is_a_moonshot():
    hit = simulate_hit(replace(STAR, stars=5, charge_up=1.0))
    assert hit.moonshot is MoonshotStatus.MOONSHOT
    assert hit.star_swing is None
    four = simulate_hit(replace(STAR, stars=4, charge_up=1.0))
    assert four.moonshot is MoonshotStatus.NONE
    assert hit.power > simulate_hit(replace(BASE, charge_up=0.0, charge_down=0.0)).power


def test_a_moonshot_without_perfect_contact_fails():
    hit = simulate_hit(replace(STAR, stars=5, charge_up=1.0, ball_x=-0.7))
    assert hit.contact_type is not ContactType.PERFECT
    assert hit.moonshot is MoonshotStatus.FAILED


def test_captain_star_effects():
    bowser = simulate_hit(replace(STAR, batter=Character.BOWSER, stars=1, is_captain=True))
    assert bowser.star_swing is CaptainStar.KILLER_BALL
    assert bowser.ball_energy == bowser.power * 4
    wario = simulate_hit(replace(STAR, batter=Character.WARIO, stars=1, is_captain=True))
    assert wario.garlic_trajectory
    assert wario.garlic_trajectory[0] in wario.trajectory


# --- mods ------------------------------------------------------------------------


def test_tag_to_mod():
    assert TAG_TO_MOD["Remove slice"] is Mod.REMOVE_SLICE
    assert TAG_TO_MOD["Fix Non-red Toad Hitboxes and Bat Reach"] is Mod.FIX_NON_RED_TOAD_REACH
    assert set(TAG_TO_MOD.values()) == set(Mod)


def test_remove_slice_sends_an_early_charge_contact_foul():
    early = replace(BASE, contact_frame=2)
    sliced = simulate_hit(early)
    fixed = simulate_hit(replace(early, mods=frozenset({Mod.REMOVE_SLICE})))
    assert sliced.horizontal_angle_raw == 0x400  # dead up the middle
    assert fixed.horizontal_angle_raw != 0x400


def test_the_toad_reach_fix_applies_only_to_non_red_toads():
    mod = frozenset({Mod.FIX_NON_RED_TOAD_REACH})
    blue = replace(BASE, batter=Character.TOAD_B, ball_x=-0.6)
    assert not same_hit(simulate_hit(blue), simulate_hit(replace(blue, mods=mod)))
    red = replace(blue, batter=Character.TOAD_R)
    assert same_hit(simulate_hit(red), simulate_hit(replace(red, mods=mod)))


def test_a_tired_pitcher_loses_the_cursed_ball():
    nice = replace(BASE, ball_x=0.1)
    fresh = simulate_hit(replace(nice, pitcher_stamina=4))
    assert fresh.contact_type is ContactType.NICE_RIGHT
    assert simulate_hit(nice).power == fresh.power
    assert simulate_hit(replace(nice, pitcher_stamina=3)).power > fresh.power


def test_a_captain_star_pitch_is_fully_cursed():
    nice = replace(BASE, ball_x=0.1)
    assert Character.MARIO.attributes.cursed_ball < 100
    star = replace(nice, is_star_pitch=True)
    assert simulate_hit(star).power < simulate_hit(nice).power
    assert simulate_hit(replace(star, pitcher_stamina=3)).power == simulate_hit(star).power
    # A non-captain star pitch keeps the pitcher's cursed ball, tired or not.
    boo = replace(star, pitcher=Character.BOO, pitcher_stamina=3)
    assert simulate_hit(boo).power == simulate_hit(replace(nice, pitcher=Character.BOO)).power


def test_the_stick_and_hand_move_the_hit():
    late = replace(BASE, contact_frame=8)
    push = simulate_hit(replace(late, stick=InputDirection.RIGHT))
    assert push.horizontal_angle_raw == simulate_hit(late).horizontal_angle_raw - 200
    lefty = simulate_hit(replace(BASE, hand=Hand.LEFT))
    assert lefty.horizontal_angle_raw != simulate_hit(BASE).horizontal_angle_raw

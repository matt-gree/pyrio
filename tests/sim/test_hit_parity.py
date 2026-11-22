"""The ported hit simulation against the pre-1.0 one, number for number.

Transitional: this pins ``pyrio.sim`` to ``pyrio.hit_simulation`` while both
exist, so the port is proven to change nothing. Step 7 deletes the old module
and this file with it; ``test_from_event.py``, against the recorded contacts,
takes over.

The star-swing resolution is new (the old module took the outcome as inputs),
so the adapter below restates the game's rules to drive the old module; the
rules themselves are tested in ``test_hit.py``.
"""

from __future__ import annotations

import random
from dataclasses import replace
from typing import Any

import pytest

from pyrio import (
    Character,
    ChargeType,
    Hand,
    InputDirection,
    PitchType,
    Stadium,
    SwingType,
)
from pyrio import hit_simulation as legacy
from pyrio.sim import (
    HitInputs,
    HitOverrides,
    HitResult,
    Mod,
    simulate_all_zones,
    simulate_hit,
    simulate_trajectory,
)

_PITCH_CODES = {
    (PitchType.CURVE, None): 0,
    (PitchType.CHARGE, ChargeType.SLIDER): 1,
    (PitchType.CHARGE, ChargeType.PERFECT): 2,
    (PitchType.CHANGE_UP, None): 3,
    (PitchType.CHARGE, ChargeType.CAPTAIN_STAR): 4,
}


def to_legacy(inputs: HitInputs) -> Any:
    """The old module's inputs for the same hit."""
    charge_up, charge_down = inputs.charge_up, inputs.charge_down
    swing = 1 if inputs.swing is SwingType.CHARGE else 0
    is_star = dinger = False
    if inputs.swing is SwingType.STAR:
        swing = 1 if charge_up > 0.0 else 0
        fully_charged = charge_up >= 1.0
        charge_up = charge_down = 0.0
        if inputs.stars == 0:
            pass
        elif fully_charged and inputs.stars >= 5:
            is_star = dinger = True
        elif (
            inputs.batter.attributes.captain_star is None or inputs.is_captain or inputs.stars >= 2
        ):
            is_star = True
    o = inputs.overrides
    s1, s2, s3 = inputs.seeds
    return legacy.HitInputs(
        batter_name=inputs.batter.label,
        pitcher_name=inputs.pitcher.label,
        pitch_type_val=_PITCH_CODES[inputs.pitch, inputs.charge],
        pos_x=inputs.batter_x,
        ball_x=inputs.ball_x,
        ball_z=inputs.ball_z,
        batter_hand=inputs.hand.id,
        swing=swing,
        is_star=is_star,
        five_star_dinger=dinger,
        charge_up=charge_up,
        charge_down=charge_down,
        chem_links=inputs.chem_links_on_base,
        frame=inputs.contact_frame,
        input_up=InputDirection.UP in inputs.stick,
        input_down=InputDirection.DOWN in inputs.stick,
        input_left=InputDirection.LEFT in inputs.stick,
        input_right=InputDirection.RIGHT in inputs.stick,
        easy_batting=inputs.is_easy_batting,
        batter_stars_on=inputs.batter_is_superstar,
        pitcher_stars_on=inputs.pitcher_is_superstar,
        # The old module's own stadium constants, not geometry's.
        ground_y=0.35 if inputs.stadium is Stadium.TOY_FIELD else 0.15,
        bounce=inputs.stadium.id in {0, 2, 3, 4, 5},
        fix_non_red_toad_reach=Mod.FIX_NON_RED_TOAD_REACH in inputs.mods,
        remove_slice=Mod.REMOVE_SLICE in inputs.mods,
        banana_hit_start_frame=o.banana_start_frame,
        banana_hit_end_frame=o.banana_end_frame,
        banana_direction=None if o.banana_hand is None else o.banana_hand.id,
        garlic_spread=o.garlic_spread_rad,
        garlic_direction=None
        if o.garlic_real_ball_to_left is None
        else int(o.garlic_real_ball_to_left),
        rng1=s1,
        rng2=s2,
        rng3=s3,
        overrides=legacy.HitOverrides(
            vertical_zone=o.vertical_zone,
            horizontal_angle=o.horizontal_angle_raw,
            vertical_angle=o.vertical_angle_raw,
            power=o.power,
        ),
    )


def from_legacy(old: Any) -> HitInputs:
    """New inputs for a hit the old module was given, as from a stat file."""
    pitch, charge = next(k for k, v in _PITCH_CODES.items() if v == old.pitch_type_val)
    stick = InputDirection(0)
    for flag, direction in (
        (old.input_up, InputDirection.UP),
        (old.input_down, InputDirection.DOWN),
        (old.input_left, InputDirection.LEFT),
        (old.input_right, InputDirection.RIGHT),
    ):
        if flag:
            stick |= direction
    if old.ground_y == 0.35:
        stadium = Stadium.TOY_FIELD
    elif not old.bounce:
        stadium = Stadium.BOWSER_CASTLE
    else:
        stadium = Stadium.MARIO_STADIUM
    if old.is_star:
        swing, stars, charge_up = SwingType.STAR, 5, 1.0 if old.five_star_dinger else 0.0
        charge_down = 0.0
    else:
        swing = SwingType.CHARGE if old.swing == 1 else SwingType.SLAP
        stars, charge_up, charge_down = 0, old.charge_up, old.charge_down
    return HitInputs(
        batter=Character(old.batter_name),
        pitcher=Character(old.pitcher_name),
        pitch=pitch,
        charge=charge,
        swing=swing,
        hand=Hand(old.batter_hand),
        stick=stick,
        batter_x=old.pos_x,
        ball_x=old.ball_x,
        ball_z=old.ball_z,
        charge_up=charge_up,
        charge_down=charge_down,
        contact_frame=old.frame,
        chem_links_on_base=old.chem_links,
        stars=stars,
        is_captain=True,
        batter_is_superstar=old.batter_stars_on,
        pitcher_is_superstar=old.pitcher_stars_on,
        is_easy_batting=old.easy_batting,
        stadium=stadium,
        mods=frozenset(
            mod
            for mod, on in (
                (Mod.FIX_NON_RED_TOAD_REACH, old.fix_non_red_toad_reach),
                (Mod.REMOVE_SLICE, old.remove_slice),
            )
            if on
        ),
        seeds=(old.rng1, old.rng2, old.rng3),
    )


def assert_same(new: HitResult, old: Any) -> None:
    assert new.contact_type.id == old.contact_type
    assert new.contact_absolute == old.contact_absolute
    assert new.contact_quality == old.contact_quality
    assert new.horizontal_angle_raw == old.horizontal_angle
    assert new.vertical_angle_raw == old.vertical_angle
    assert new.horizontal_angle_deg == old.horizontal_angle_deg
    assert new.vertical_angle_deg == old.vertical_angle_deg
    assert new.power == old.power
    assert new.velocity_per_frame == old.velocity
    assert new.acceleration_per_frame == old.acceleration
    assert new.ball_energy == old.ball_energy
    assert new.landing == old.landing
    assert new.distance == old.distance
    assert new.hang_frames == old.hang_frames
    assert new.trajectory == tuple(old.trajectory)
    old_garlic = None if old.garlic_trajectory is None else tuple(old.garlic_trajectory)
    assert new.garlic_trajectory == old_garlic


def random_inputs(rng: random.Random) -> HitInputs:
    pitch, charge = rng.choice(list(_PITCH_CODES))
    batter_x = rng.uniform(-1.2, 1.2)
    overrides = HitOverrides()
    if rng.random() < 0.15:
        overrides = HitOverrides(
            vertical_zone=rng.choice([None, 0, 1, 2, 3, 4]),
            horizontal_angle_raw=rng.choice([None, rng.randrange(0x200, 0x600)]),
            vertical_angle_raw=rng.choice([None, rng.randrange(-200, 900)]),
            power=rng.choice([None, rng.randrange(50, 250)]),
            banana_start_frame=rng.choice([None, rng.randrange(0, 40)]),
            banana_end_frame=rng.choice([None, rng.randrange(40, 200)]),
            banana_hand=rng.choice([None, Hand.RIGHT, Hand.LEFT]),
            garlic_spread_rad=rng.choice([None, rng.uniform(0.1, 0.4)]),
            garlic_real_ball_to_left=rng.choice([None, True, False]),
        )
    return HitInputs(
        batter=rng.choice(list(Character)),
        pitcher=rng.choice(list(Character)),
        pitch=pitch,
        charge=charge,
        swing=rng.choice([SwingType.SLAP, SwingType.CHARGE, SwingType.STAR, SwingType.STAR]),
        hand=rng.choice(list(Hand)),
        stick=InputDirection(rng.randrange(16)),
        batter_x=batter_x,
        ball_x=batter_x + rng.uniform(-0.95, 0.45),
        ball_z=rng.uniform(-1.0, 1.0),
        charge_up=rng.choice([0.0, 0.0, 0.35, 0.8, 1.0, 1.0]),
        charge_down=rng.choice([0.0, 0.5, 1.0, rng.random()]),
        contact_frame=rng.choice([*range(2, 11), *range(15)]),
        chem_links_on_base=rng.randrange(4),
        stars=rng.randrange(6),
        is_captain=rng.random() < 0.5,
        batter_is_superstar=rng.random() < 0.3,
        pitcher_is_superstar=rng.random() < 0.3,
        is_easy_batting=rng.random() < 0.2,
        stadium=rng.choice(list(Stadium)),
        mods=frozenset(m for m in Mod if rng.random() < 0.3),
        seeds=(rng.randrange(32768), rng.randrange(32768), rng.randrange(32768)),
        overrides=overrides,
    )


SPREAD = 3000


def test_simulate_hit_matches_the_old_module_over_a_spread_of_inputs():
    rng = random.Random(20261121)
    made_contact = 0
    for _ in range(SPREAD):
        inputs = random_inputs(rng)
        try:
            old = legacy.simulate_hit(to_legacy(inputs))
        except ValueError:
            with pytest.raises(ValueError, match="reach"):
                simulate_hit(inputs)
            continue
        assert_same(simulate_hit(inputs), old)
        made_contact += 1
    assert made_contact > SPREAD * 0.6  # guard against a vacuous pass


def test_every_batter_and_captain_star_matches():
    for batter in Character:
        for stars, is_captain, charge_up in ((5, True, 0.0), (5, False, 1.0), (1, False, 0.0)):
            inputs = HitInputs(
                batter=batter,
                pitcher=Character.MARIO,
                pitch=PitchType.CURVE,
                swing=SwingType.STAR,
                hand=Hand.RIGHT,
                batter_x=0.0,
                ball_x=0.0,
                stars=stars,
                is_captain=is_captain,
                charge_up=charge_up,
            )
            assert_same(simulate_hit(inputs), legacy.simulate_hit(to_legacy(inputs)))


def test_simulate_trajectory_matches():
    rng = random.Random(7)
    checked = 0
    while checked < 200:
        inputs = random_inputs(rng)
        frames = rng.randrange(1, 400)
        try:
            old = legacy.simulate_hit_trajectory(to_legacy(inputs), frames)
        except ValueError:
            continue
        assert simulate_trajectory(inputs, frames) == tuple(old)
        checked += 1


def test_simulate_all_zones_matches():
    rng = random.Random(11)
    checked = 0
    while checked < 60:
        inputs = random_inputs(rng)
        try:
            old = legacy.simulate_hit_all_vertical_zones(to_legacy(inputs))
        except ValueError:
            continue
        new = simulate_all_zones(inputs)
        assert len(new) == len(old) == 5
        for a, b in zip(new, old, strict=True):
            assert_same(a, b)
        checked += 1


def test_recorded_contacts_match(recorded_legacy_inputs: list[Any]):
    assert len(recorded_legacy_inputs) > 50
    for old_inputs in recorded_legacy_inputs:
        inputs = from_legacy(old_inputs)
        assert_same(simulate_hit(inputs), legacy.simulate_hit(old_inputs))


def test_recorded_contacts_survive_a_round_trip(recorded_legacy_inputs: list[Any]):
    # to_legacy(from_legacy(x)) reproduces x's simulation: the two adapters agree.
    for old_inputs in recorded_legacy_inputs:
        again = to_legacy(from_legacy(old_inputs))
        assert_same(simulate_hit(from_legacy(old_inputs)), legacy.simulate_hit(again))


def test_overrides_are_frozen_defaults():
    inputs = HitInputs(
        batter=Character.MARIO,
        pitcher=Character.MARIO,
        pitch=PitchType.CURVE,
        swing=SwingType.SLAP,
        hand=Hand.RIGHT,
        batter_x=0.0,
        ball_x=0.0,
    )
    forced = replace(inputs, overrides=HitOverrides(power=999))
    assert simulate_hit(forced).power == 999

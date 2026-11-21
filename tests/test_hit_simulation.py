import pathlib

import pyrio
from pyrio import simulate_hit_from_event
from pyrio.hit_sim_validation import validate_statobj
from pyrio.hit_simulation import HitInputs, HitOverrides, simulate_hit, simulate_hit_all_vertical_zones
from pyrio.stat_file_parser import EventObj

FIXTURES = pathlib.Path(__file__).parent / "fixtures"
DECODED = FIXTURES / "decoded.20260618T191655_SpiceOrange-Vs-MattGree_3896251267.json"
ENCODED = FIXTURES / "20260618T191655_SpiceOrange-Vs-MattGree_3896251267.json"

_BASE_INPUTS = dict(
    batter_name="Mario", pitcher_name="Mario", pitch_type_val=0,
    pos_x=0.0, ball_x=0.0, batter_hand=0, swing=1,
    rng1=7769, rng2=5359, rng3=1828,
)


def _first_contact_index(sf):
    for i, ev in enumerate(sf.events()):
        pitch = ev.get("Pitch", {})
        if pitch.get("Contact") and pitch.get("Type of Swing") in ("Slap", "Charge", "Star"):
            return i
    raise AssertionError("no contact event in fixture")


def test_simulate_hit_from_event_returns_result():
    sf = pyrio.load_stat_file(DECODED)
    result = simulate_hit_from_event(EventObj(sf, _first_contact_index(sf)))
    assert result.contact_absolute > 0
    assert result.contact_type_name


def test_validation_harness_reproduces_recorded_contacts():
    # validate_statobj re-simulates every contact via its recorded RNG seeds and
    # compares the result field-by-field to what the game recorded.
    rep = validate_statobj(pyrio.load_stat_file(DECODED))
    assert rep.contact_events > 50
    # the deterministic contact-stage outputs must reproduce exactly
    for name in ("contact_type", "contact_absolute", "contact_quality", "power", "vertical_angle"):
        assert rep.fields[name].failures == 0, f"{name}: {rep.fields[name].failures} mismatch(es)"
    # every field near-perfect; a single mod-affected slice diverges on angle/velocity
    assert all(st.rate >= 0.98 for st in rep.fields.values())


def test_validation_is_source_agnostic():
    dec = validate_statobj(pyrio.load_stat_file(DECODED))
    enc = validate_statobj(pyrio.load_stat_file(ENCODED))
    assert {n: st.failures for n, st in dec.fields.items()} == \
           {n: st.failures for n, st in enc.fields.items()}


def test_hit_overrides_force_power():
    result = simulate_hit(HitInputs(**_BASE_INPUTS, overrides=HitOverrides(power=999)))
    assert result.power == 999


def test_bowser_bullet_star_quadruples_ball_energy():
    inputs = dict(_BASE_INPUTS, batter_name="Bowser", is_star=True, charge_up=1.0)
    result = simulate_hit(HitInputs(**inputs))
    assert result.ball_energy == result.power * 4


def test_wario_garlic_star_splits_the_trajectory():
    inputs = dict(_BASE_INPUTS, batter_name="Wario", is_star=True, charge_up=1.0)
    result = simulate_hit(HitInputs(**inputs))
    assert result.garlic_trajectory
    assert result.garlic_trajectory[0] != result.trajectory[0]


def test_five_star_attempt_moonshot_boosts_power():
    inputs = dict(_BASE_INPUTS, is_star=True, charge_up=1.0)
    normal = simulate_hit(HitInputs(**inputs)).power
    dinger = simulate_hit(HitInputs(**inputs, five_star_attempt=True)).power
    assert dinger > normal


def test_charged_star_pitch_type_is_accepted():
    result = simulate_hit(HitInputs(**dict(_BASE_INPUTS, pitch_type_val=4)))
    assert result.power > 0


def test_simulate_hit_all_vertical_zones_covers_five_zones():
    results = simulate_hit_all_vertical_zones(HitInputs(**_BASE_INPUTS))
    assert len(results) == 5
    assert len({r.vertical_angle for r in results}) > 1

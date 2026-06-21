import pathlib

import pyrio
from pyrio import simulate_hit_from_event
from pyrio.hit_sim_validation import validate_statobj
from pyrio.stat_file_parser import EventObj

FIXTURES = pathlib.Path(__file__).parent / "fixtures"
DECODED = FIXTURES / "decoded.20260618T191655_SpiceOrange-Vs-MattGree_3896251267.json"
ENCODED = FIXTURES / "20260618T191655_SpiceOrange-Vs-MattGree_3896251267.json"


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

import pathlib

import pyrio
from pyrio import simulate_hit_from_event
from pyrio.stat_file_parser import EventObj

FIXTURES = pathlib.Path(__file__).parent / "fixtures"
DECODED = FIXTURES / "decoded.20260618T191655_SpiceOrange-Vs-MattGree_3896251267.json"
ENCODED = FIXTURES / "20260618T191655_SpiceOrange-Vs-MattGree_3896251267.json"


def _contact_event_indices(sf):
    out = []
    for i, ev in enumerate(sf.events()):
        pitch = ev.get("Pitch", {})
        if pitch.get("Contact") and pitch.get("Type of Swing") in ("Slap", "Charge", "Star"):
            out.append(i)
    return out


def test_sim_reproduces_recorded_contact():
    sf = pyrio.load_stat_file(DECODED)
    idxs = _contact_event_indices(sf)
    assert len(idxs) > 50  # a real game's worth of contacts
    events = sf.events()
    angle_matches = 0
    for i in idxs:
        contact = events[i]["Pitch"]["Contact"]
        result = simulate_hit_from_event(EventObj(sf, i))
        # the contact stage is deterministic from the RNG seeds -> exact
        assert abs(result.contact_absolute - float(contact["Contact Absolute"])) < 1e-2
        assert abs(result.contact_quality - float(contact["Contact Quality"])) < 1e-3
        if result.horizontal_angle == int(str(contact["Horiz Angle"]).replace(",", "")):
            angle_matches += 1
    # near-perfect; a single documented JS-quirk edge case is tolerated
    assert angle_matches / len(idxs) >= 0.95


def test_sim_is_source_agnostic():
    dec = pyrio.load_stat_file(DECODED)
    enc = pyrio.load_stat_file(ENCODED)
    for i in _contact_event_indices(dec):
        rd = simulate_hit_from_event(EventObj(dec, i))
        re_ = simulate_hit_from_event(EventObj(enc, i))
        assert rd.contact_absolute == re_.contact_absolute
        assert rd.contact_quality == re_.contact_quality
        assert rd.horizontal_angle == re_.horizontal_angle

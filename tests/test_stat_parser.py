import pathlib

import pyrio
from pyrio import StatObj, Character

FIXTURES = pathlib.Path(__file__).parent / "fixtures"
ENCODED = FIXTURES / "20260618T191655_SpiceOrange-Vs-MattGree_3896251267.json"
DECODED = FIXTURES / "decoded.20260618T191655_SpiceOrange-Vs-MattGree_3896251267.json"


def _fake_stat():
    # No "Version" key -> old team-string format ("Team 0 Roster N")
    cgs = {f"Team 0 Roster {i}": {"CharID": i} for i in range(9)}
    return {"Character Game Stats": cgs}


def test_character_accessor_returns_value_objects():
    sf = StatObj(_fake_stat())
    c = sf.character(0, 3)
    assert isinstance(c, Character)
    assert c.id == 3
    assert str(c) == "Diddy"


def test_character_accessor_returns_full_roster():
    sf = StatObj(_fake_stat())
    roster = sf.character(0)
    assert len(roster) == 9
    assert all(isinstance(x, Character) for x in roster)
    assert [int(x) for x in roster] == list(range(9))


def test_characterName_alias_still_works():
    sf = StatObj(_fake_stat())
    assert sf.characterName(0, 3) == sf.character(0, 3)


def test_character_accessor_is_source_agnostic():
    # Same game, stored as int ids (encoded) vs name strings (decoded).
    enc = pyrio.load_stat_file(ENCODED)
    dec = pyrio.load_stat_file(DECODED)
    assert enc.character(0, 0) == dec.character(0, 0)
    assert enc.character(0, 0) == Character(2, "DK")
    # whole roster matches across both representations
    assert enc.character(0) == dec.character(0)

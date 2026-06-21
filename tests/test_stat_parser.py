import pathlib

import pyrio
from pyrio import (
    StatObj, Character, Stadium, PitchType, FinalResult, Hand, RunnerObj, DeadBallReason,
)
from pyrio.stat_file_parser import EventObj

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


def test_stadium_accessor_is_source_agnostic():
    enc = pyrio.load_stat_file(ENCODED)   # StadiumID stored as int 1
    dec = pyrio.load_stat_file(DECODED)   # StadiumID stored as "Bowser Castle"
    assert enc.stadium() == dec.stadium() == Stadium(1, "Bowser Castle")


def test_event_pitch_type_is_source_agnostic():
    enc = pyrio.load_stat_file(ENCODED)   # 'Pitch Type' stored as int
    dec = pyrio.load_stat_file(DECODED)   # 'Pitch Type' stored as name
    idx = next(i for i, ev in enumerate(enc.events()) if "Pitch" in ev)
    enc_pt = EventObj(enc, idx).pitch_type()
    dec_pt = EventObj(dec, idx).pitch_type()
    assert isinstance(enc_pt, PitchType)
    assert enc_pt == dec_pt


def test_result_of_ab_is_source_agnostic():
    enc = pyrio.load_stat_file(ENCODED)   # 'Result of AB' stored as int
    dec = pyrio.load_stat_file(DECODED)   # 'Result of AB' stored as name
    idx = next(i for i, ev in enumerate(enc.events()) if "Result of AB" in ev)
    enc_r = EventObj(enc, idx).result_of_AB()
    dec_r = EventObj(dec, idx).result_of_AB()
    assert isinstance(enc_r, FinalResult)
    assert enc_r == dec_r


def test_batting_hand_is_source_agnostic():
    enc = pyrio.load_stat_file(ENCODED)   # 'Batting Hand' stored as int
    dec = pyrio.load_stat_file(DECODED)   # 'Batting Hand' stored as name
    enc_h = enc.battingHand(0, 0)
    dec_h = dec.battingHand(0, 0)
    assert isinstance(enc_h, Hand)
    assert enc_h == dec_h


def test_runnerobj_is_source_agnostic():
    enc = pyrio.load_stat_file(ENCODED)   # 'Runner Char Id' stored as int
    dec = pyrio.load_stat_file(DECODED)   # 'Runner Char Id' stored as name
    idx = next(i for i, ev in enumerate(enc.events())
               if isinstance(ev.get("Runner Batter"), dict))
    er = EventObj(enc, idx).runner(0)
    dr = EventObj(dec, idx).runner(0)
    assert isinstance(er, RunnerObj)
    assert isinstance(er.character(), Character)
    assert er.character() == dr.character()      # Character source-agnostic
    assert er.initial_base() == dr.initial_base()
    assert er.result_base() == dr.result_base()
    assert er.total_bases() == er.result_base() - er.initial_base()
    assert isinstance(er.is_out(), bool)


def test_dead_ball_reason_source_agnostic():
    enc = pyrio.load_stat_file(ENCODED)
    dec = pyrio.load_stat_file(DECODED)
    idx = next(i for i, ev in enumerate(enc.events()) if "Dead Ball Reason" in ev)
    enc_d = EventObj(enc, idx).dead_ball_reason()
    dec_d = EventObj(dec, idx).dead_ball_reason()
    assert isinstance(enc_d, DeadBallReason)
    assert enc_d == dec_d

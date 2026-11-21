import pathlib

import pytest

import pyrio
from pyrio import StatObj, RunnerObj
from pyrio.rio_value import Character, Stadium, PitchType, FinalResult, Hand, DeadBallReason
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
    assert isinstance(er.out_location(), int)


def test_misc_stat_accessors():
    enc = pyrio.load_stat_file(ENCODED)
    dec = pyrio.load_stat_file(DECODED)
    assert enc.netplay() == 1
    assert enc.loaded_from_hud() == 0
    idx = next(i for i, ev in enumerate(enc.events())
               if "Pitch" in ev and ev["Pitch"].get("Pitcher Char Id") is not None)
    ep = EventObj(enc, idx).pitch_pitcher()
    dp = EventObj(dec, idx).pitch_pitcher()
    assert isinstance(ep, Character)
    assert ep == dp


def test_dead_ball_reason_source_agnostic():
    enc = pyrio.load_stat_file(ENCODED)
    dec = pyrio.load_stat_file(DECODED)
    idx = next(i for i, ev in enumerate(enc.events()) if "Dead Ball Reason" in ev)
    enc_d = EventObj(enc, idx).dead_ball_reason()
    dec_d = EventObj(dec, idx).dead_ball_reason()
    assert isinstance(enc_d, DeadBallReason)
    assert enc_d == dec_d


# --- GameID base, and the version comparison it depends on ---------------------

def test_game_id_is_decimal_before_2_3():
    # The fixture is Version 2.2.0 and its filename carries the same id, so the
    # expected value is independent of the parser.
    dec = pyrio.load_stat_file(DECODED)
    assert dec.version() == "2.2.0"
    assert dec.gameID() == 3896251267
    assert dec.hexGameID() is False


def test_game_id_is_hex_from_2_3():
    # Rio 2.3.0 writes lowercase hex via gameIDToHex.
    stat = StatObj({"Version": "2.3.0", "GameID": "e84a9bc3"})
    assert stat.hexGameID() is True
    assert stat.gameID() == 0xE84A9BC3


def test_game_id_hex_boundary_is_2_3_0():
    assert StatObj({"Version": "2.2.9", "GameID": "10"}).gameID() == 10
    assert StatObj({"Version": "2.3.0", "GameID": "10"}).gameID() == 16


def test_version_before_matches_numbers_not_strings():
    # The prefixed and suffixed releases an exact-string match misses.
    assert StatObj({"Version": "Pre 0.1.7"}).versionBefore(2, 3)
    assert StatObj({"Version": "0.1.7.a"}).versionBefore(2, 3)
    assert StatObj({}).versionBefore(2, 3)                 # missing key
    assert StatObj({"Version": None}).versionBefore(2, 3)   # present but null
    assert StatObj({"Version": "Unknown"}).versionBefore(2, 3)
    # 1.9.5 vs 1.9.6 and the no-patch form, where off-by-one-release hurts.
    assert StatObj({"Version": "1.9.5"}).versionBefore(1, 9, 6)
    assert not StatObj({"Version": "1.9.6"}).versionBefore(1, 9, 6)
    assert not StatObj({"Version": "2.3"}).versionBefore(2, 3)
    assert not StatObj({"Version": "2.10.0"}).versionBefore(2, 3)


def test_statobj_captain_returns_the_captain():
    """captain() iterated characterGameStats(), which is a dict, so it indexed
    a string key and raised TypeError on every call."""
    import json
    for path in (ENCODED, DECODED):
        with open(path) as f:
            stat = StatObj(json.load(f))
        for team in (0, 1):
            cap = stat.captain(team)
            assert isinstance(cap, Character)
            assert cap.attributes.is_captain


def test_statobj_captain_returns_none_when_no_captain():
    cgs = {
        f"Team {t} Roster {i}": {"CharID": i, "Team": t, "Captain": 0}
        for t in (0, 1)
        for i in range(9)
    }
    stat = StatObj({"Character Game Stats": cgs})
    assert stat.captain(0) is None
    assert stat.captain(1) is None


# ---------------------------------------------------------------------------
# Rio 2.3.0 swapped at-bat ids 5 and 6: decoded labels need version context
# ---------------------------------------------------------------------------

def _ab_event(version, raw):
    j = {"Events": [{"Result of AB": raw}]}
    if version is not None:
        j["Version"] = version
    return EventObj(StatObj(j), 0).result_of_AB()


def test_legacy_decoded_ab_labels_are_version_corrected():
    """A pre-2.3.0 decoded file spells id 5 "Caught"; 2.3.0 spells it
    "Caught line-drive". The label alone cannot say which, so the file's
    version decides."""
    for version in ("2.2.0", "1.9.5", None):      # None: unknown == legacy
        assert _ab_event(version, "Caught").id == 5
        assert _ab_event(version, "Caught line-drive").id == 6


def test_modern_decoded_ab_labels_are_taken_at_face_value():
    for version in ("2.3.0", "2.4.0"):
        assert _ab_event(version, "Caught").id == 6
        assert _ab_event(version, "Caught line-drive").id == 5


def test_encoded_ab_ids_are_never_version_corrected():
    """Stored numbers did not change, only the decoded text, so an encoded id
    must pass through untouched whatever the version."""
    for version in ("2.2.0", "1.9.5", "2.3.0", "2.4.0", None):
        assert _ab_event(version, 5).id == 5
        assert _ab_event(version, 6).id == 6


def test_other_ab_labels_are_unaffected_by_the_correction():
    for version in ("2.2.0", "2.3.0"):
        assert _ab_event(version, "Single").id == 7
        assert _ab_event(version, "HR").id == 10
        assert _ab_event(version, "Foul catch").id == 16


def test_encoded_and_decoded_fixtures_agree_on_every_result():
    """The two fixtures are the same 2.2.0 game, one stored as ids and one as
    the old labels. Before the version correction they disagreed on 28 of 211
    events -- every caught ball and line drive in the game."""
    import json
    with open(ENCODED) as f:
        enc = StatObj(json.load(f))
    with open(DECODED) as f:
        dec = StatObj(json.load(f))
    for i in range(enc.final_event() + 1):
        assert EventObj(enc, i).result_of_AB() == EventObj(dec, i).result_of_AB(), (
            f"event {i} differs between the encoded and decoded copies"
        )


# --- per-position defensive counts -------------------------------------------

def test_batters_per_position_reads_the_current_key():
    sf = pyrio.load_stat_file(DECODED)
    counts = [sf.battersPerPosition(t, r) for t in (0, 1) for r in range(9)]
    assert all(isinstance(c, dict) for c in counts)
    assert sum(sum(c.values()) for c in counts) > 0


def test_outs_per_position_is_empty_dict_when_no_outs():
    # Four characters in this game recorded no outs; the client writes [] for them.
    sf = pyrio.load_stat_file(DECODED)
    counts = [sf.outsPerPosition(t, r) for t in (0, 1) for r in range(9)]
    assert counts.count({}) == 4
    assert all(isinstance(c, dict) for c in counts)


def test_pitches_per_position_explains_the_1_9_2_rename():
    sf = pyrio.load_stat_file(DECODED)
    with pytest.raises(ValueError, match="battersPerPosition"):
        sf.pitchesPerPosition(0, 0)


def test_pitches_per_position_still_reads_pre_1_9_2_files():
    stats = {"Defensive Stats": {"Pitches Per Position": [{"P": 87, "1B": 3}]}}
    sf = StatObj({"Version": "1.9.1", "Character Game Stats": {"Team 0 Roster 0": stats}})
    assert sf.pitchesPerPosition(0, 0) == {"P": 87, "1B": 3}

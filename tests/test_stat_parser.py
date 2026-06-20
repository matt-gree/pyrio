from pyrio import StatObj, Character


def _fake_stat():
    # No "Version" key -> old team-string format ("Team 0 Roster N")
    cgs = {f"Team 0 Roster {i}": {"CharID": i} for i in range(9)}
    return {"Character Game Stats": cgs}


def test_character_accessor_returns_value_objects():
    sf = StatObj(_fake_stat())
    c = sf.character(0, 3)
    assert isinstance(c, Character)
    assert c == 3
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

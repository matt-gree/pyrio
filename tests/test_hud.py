import json
import pathlib

import pytest

from pyrio import HudObj, Stadium, TeamName, Character, Position, Hand, RunnerObj

FIXTURES = pathlib.Path(__file__).parent / "fixtures"
ENCODED = FIXTURES / "hud.json"            # ids stored as ints
DECODED = FIXTURES / "decoded.hud.json"    # ids stored as name strings


def _load(path):
    with open(path) as f:
        return HudObj(json.load(f))


def test_hud_game_settings_source_agnostic():
    enc, dec = _load(ENCODED), _load(DECODED)
    assert enc.stadium() == dec.stadium() == Stadium(1, "Bowser Castle")
    assert isinstance(enc.logo(0), TeamName)
    assert enc.logo(0) == dec.logo(0)                       # Away Logo
    assert enc.logo(1) == dec.logo(1) == TeamName(3, "Mario Heroes")
    assert enc.innings_selected() == 9
    assert enc.first_batting_team() == 0
    assert enc.star_skills_on() is True
    assert enc.mercy_on() is True
    assert enc.inning_scores(0) == [0, 6, 2, 0, 0, 0, 0, 1, 0]


def test_hud_per_character_source_agnostic():
    enc, dec = _load(ENCODED), _load(DECODED)
    assert enc.character(0, 0) == dec.character(0, 0) == Character(2, "DK")
    assert isinstance(enc.position(0, 0), Position)
    assert enc.position(0, 0) == dec.position(0, 0)         # 2B
    assert enc.fielding_hand(0, 0) == dec.fielding_hand(0, 0)
    assert enc.batting_hand(0, 0) == dec.batting_hand(0, 0) == Hand(1, "Left")
    assert enc.is_superstar(0, 0) is False
    assert enc.captain(0) == dec.captain(0) == Character(9, "Bowser")


def test_hud_runner_source_agnostic():
    enc, dec = _load(ENCODED), _load(DECODED)
    r_enc, r_dec = enc.runner(1), dec.runner(1)            # Runner 1B
    assert isinstance(r_enc, RunnerObj)
    assert r_enc.character() == r_dec.character() == Character(9, "Bowser")
    assert r_enc.is_out() is False


def test_hud_misc_accessors():
    enc = _load(ENCODED)
    assert enc.port(0) == 0 and enc.port(1) == 1
    assert enc.previous_event() is not None
    assert enc.batter_roster_location() == 2          # current batter
    assert enc.batter_roster_location(0) == 2         # Away due-up
    assert enc.batter_roster_location(1) == 6         # Home due-up


def test_hud_positions_and_due_up():
    enc = _load(ENCODED)
    dec = _load(DECODED)
    # Away pitcher (position P) is roster slot 5 (Noki(G))
    assert enc.roster_id_at_position(0, "P") == 5
    assert enc.roster_id_at_position(0, 0) == enc.roster_id_at_position(0, "P")
    assert enc.team_positions(0) == dec.team_positions(0)
    assert enc.team_positions(0)[0] == 5
    du = enc.due_up(0)
    assert len(du) == 9 and all(isinstance(c, Character) for c in du)
    assert du[0] == enc.character(0, enc.batter_roster_location(0))
    with pytest.raises(ValueError):
        enc.roster_id_at_position(0, "ZZ")

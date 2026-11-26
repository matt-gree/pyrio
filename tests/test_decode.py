"""The decoder, one test (or more) per version rule, over a fixture matrix of eras.

Fixtures under ``fixtures/stat_files/<version>/`` are real files from the Rio
repos, except those named ``synthetic.*``: no real file exists for 1.9.2-1.9.4
or 2.3.0, so those are rewritten from real files to that version's writer.
"""

from __future__ import annotations

import copy
import io
import json
import re
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import pytest

from pyrio import (
    AtBatResult,
    Character,
    ChargeType,
    Fielding,
    ManualSelect,
    MoonshotStatus,
    OutType,
    Pitch,
    Position,
    PrimaryContactResult,
    SecondaryContactResult,
    Side,
    Stadium,
    StatFileError,
    SwingType,
    Version,
    read_game,
    read_hud,
)

FIXTURES = Path(__file__).parent / "fixtures"
STAT_FILES = FIXTURES / "stat_files"

V0_1_7A = STAT_FILES / "0.1.7a/demo.DemoUser1-Vs-PeacockSavior.json"
V1_9_3 = STAT_FILES / "1.9.3/synthetic.MaybeJon-Vs-PeacockSlayer.json"
V1_9_5 = STAT_FILES / "1.9.5/20230315T212151_MaybeJon-Vs-PeacockSlayer_1867546158.json"
V1_9_5_OLD_LAYOUT = STAT_FILES / "1.9.5/game_785756763.json"
V1_9_6_CRASH = STAT_FILES / "1.9.6/crash.decode.20230831T151058_MattGree-Vs-samn_345471771.json"
V2_0_2_QUIT = STAT_FILES / "2.0.2/decoded.20231114T143512_Flatbread-Vs-MattGree_153176676.json"
V2_0_2_MERCY = STAT_FILES / "2.0.2/decoded.20240127T163640_Clutch1908-Vs-Baltor33_1908774040.json"
V2_1_1 = STAT_FILES / "2.1.1/20260219T212721_MattGree-Vs-Baltor33_1189820580.json"
V2_2_0 = FIXTURES / "20260618T191655_SpiceOrange-Vs-MattGree_3896251267.json"
V2_2_0_DECODED = FIXTURES / "decoded.20260618T191655_SpiceOrange-Vs-MattGree_3896251267.json"
V2_3_0 = STAT_FILES / "2.3.0/synthetic.SpiceOrange-Vs-MattGree.json"

MATRIX = [
    V0_1_7A,
    V1_9_3,
    V1_9_5,
    V1_9_5_OLD_LAYOUT,
    V1_9_6_CRASH,
    V2_0_2_QUIT,
    V2_0_2_MERCY,
    V2_1_1,
    V2_2_0,
    V2_2_0_DECODED,
    V2_3_0,
]


def load(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text())


def test_matrix_covers_every_fixture():
    on_disk = set(STAT_FILES.rglob("*.json"))
    assert on_disk, "no fixtures found"
    assert on_disk <= set(MATRIX)


# --- Every era -----------------------------------------------------------------------


@pytest.mark.parametrize("path", MATRIX, ids=lambda p: f"{p.parent.name}/{p.name[:30]}")
def test_every_era_decodes_consistently(path: Path):
    game = read_game(path)
    assert len(game.away.roster) == len(game.home.roster) == 9
    for team in (game.away, game.home):
        assert [spot.index for spot in team.roster] == list(range(9))
        assert all(spot.side is team.side for spot in team.roster)
        assert sum(spot.is_captain for spot in team.roster) == 1
        # Runs counted event by event add up to the final score.
        runs = sum(h.runs for h in game.half_innings if h.batting_side is team.side)
        assert runs == team.score
    for event in game.events:
        assert event.game_id == game.id
        assert event.batter_spot.side is event.state.batting_side
        assert event.pitcher_spot.side is event.state.batting_side.other
        assert event.catcher_spot.side is event.state.batting_side.other
        assert event.runners[0].start_base == 0
        if event.fielding is not None:
            assert event.fielding.spot.side is event.state.batting_side.other


def test_sources_a_path_a_file_or_a_dict():
    by_path = read_game(V1_9_5)
    assert read_game(str(V1_9_5)) == by_path
    assert read_game(load(V1_9_5)) == by_path
    with V1_9_5.open("rb") as binary:
        assert read_game(binary) == by_path
    assert read_game(io.StringIO(V1_9_5.read_text())) == by_path


# --- (c) First supported version ------------------------------------------------------


def test_files_without_a_version_are_refused():
    data = load(V0_1_7A)
    del data["Version"]
    with pytest.raises(StatFileError, match=r"0\.1\.6 or earlier"):
        read_game(data)


def test_versions_before_0_1_7_are_refused():
    data = load(V0_1_7A)
    data["Version"] = "0.1.6"
    with pytest.raises(StatFileError, match=r"from Rio 0\.1\.7 on"):
        read_game(data)


def test_an_unparseable_version_is_an_error_not_a_guess():
    data = load(V2_2_0)
    data["Version"] = "nightly"
    with pytest.raises(StatFileError, match="Version"):
        read_game(data)


# --- (b) Team numbers flipped at 1.9.2 ------------------------------------------------


def test_before_1_9_2_team_0_is_home():
    game = read_game(V0_1_7A)
    data = load(V0_1_7A)
    team_1 = data["Character Game Stats"]["Team 1 Roster 0"]
    assert game.away.roster[0].character is Character(team_1["CharID"])
    assert game.away.player == "DemoUser1"
    assert game.away.captain.character is Character.WARIO
    assert game.home.captain.character is Character.DAISY
    first = game.events[0]
    assert first.state.batting_side is Side.AWAY
    assert first.batter_spot is game.away.roster[0]


def test_from_1_9_2_team_0_is_away():
    # The same file read as 1.9.2 puts the other roster on the away side.
    data = load(V0_1_7A)
    data["Version"], data["GameID"] = "1.9.2", "3718403951"
    data["Events"] = data["Events"][:1]  # later ones hold 0.1.7's uninitialised fielder actions
    for spot in data["Character Game Stats"].values():
        defense = spot["Defensive Stats"]
        defense["Batters Per Position"] = defense.pop("Pitches Per Position")
    flipped = read_game(data)
    original = read_game(V0_1_7A)
    assert [s.character for s in flipped.away.roster] == [s.character for s in original.home.roster]


# --- (b) Captains crossed in 1.9.2-1.9.4 ---------------------------------------------


def test_1_9_2_to_1_9_4_captain_flags_belong_to_the_other_team():
    synthetic = read_game(V1_9_3)
    real = read_game(V1_9_5)
    assert synthetic.away.captain.character is real.away.captain.character is Character.MARIO
    assert synthetic.home.captain.character is real.home.captain.character is Character.WALUIGI
    assert synthetic.away == real.away
    assert synthetic.home == real.home


def test_a_team_needs_exactly_one_captain():
    data = load(V2_2_0)
    data["Character Game Stats"]["Away Roster 0"]["Captain"] = 1
    with pytest.raises(StatFileError, match="2 captains"):
        read_game(data)


# --- (a) Renamed keys: whichever name the file has -----------------------------------


def test_team_roster_keys_up_to_1_9_4():
    assert read_game(V1_9_3).version == Version(1, 9, 3)


def test_a_1_9_5_file_with_the_1_9_4_layout_still_reads():
    game = read_game(V1_9_5_OLD_LAYOUT)
    assert game.version == Version(1, 9, 5)
    assert game.tag_set_id is None
    assert game.away.player == "AWAY_PLAYER"


def test_pitches_per_position_before_1_9_2():
    spot = read_game(V0_1_7A).home.roster[0]
    assert spot.batters_per_position is None
    assert spot.pitches_per_position == {Position.CENTER_FIELD: 54}


def test_batters_per_position_from_1_9_2():
    spot = read_game(V2_2_0).away.roster[0]
    assert spot.pitches_per_position is None
    assert spot.batters_per_position == {Position.SECOND_BASE: 42}
    assert spot.batter_outs_per_position == {Position.SECOND_BASE: 24}
    assert spot.outs_per_position == {Position.SECOND_BASE: 3}


# --- (b) GameID: hex, then decimal, then hex -------------------------------------------


def test_game_id_is_hex_up_to_0_1_8_with_grouping_commas():
    assert load(V0_1_7A)["GameID"] == "dd,9e5,76f"
    assert read_game(V0_1_7A).id == 0xDD9E576F


def test_game_id_is_decimal_from_0_1_9_to_2_2_0():
    assert read_game(V2_2_0).id == 3896251267
    assert read_game(V1_9_5).id == 1867546158  # written "1,867,546,158"


def test_game_id_is_hex_from_2_3_0():
    assert read_game(V2_3_0).id == 0x9F3C2A1B5D7E4F60


# --- (c) Fielder fields that older clients didn't record ------------------------------


def test_manual_select_is_unknown_before_1_9_2():
    fieldings = [e.fielding for e in read_game(V0_1_7A).events if e.fielding is not None]
    assert fieldings
    assert all(f.manual_select is None for f in fieldings)


def test_manual_select_from_1_9_2():
    fielding = read_game(V2_2_0).events[0].fielding
    assert fielding is not None
    assert fielding.manual_select is ManualSelect.CLOSEST_TO_BALL


def test_fielder_action_and_jump_are_unknown_before_0_1_9():
    # 0.1.7 left them uninitialised: this file has actions like 137 that don't exist.
    fieldings = [e.fielding for e in read_game(V0_1_7A).events if e.fielding is not None]
    assert all(f.action is None and f.jumped is None for f in fieldings)
    later = read_game(V2_2_0).events[0].fielding
    assert later is not None
    assert later.action is not None
    assert later.jumped is False


def fielding_at(data: dict[str, Any], index: int) -> Fielding:
    fielding = read_game(copy.deepcopy(data)).events[index].fielding
    assert fielding is not None
    return fielding


def pitch_at(data: dict[str, Any], index: int) -> Pitch:
    pitch = read_game(copy.deepcopy(data)).events[index].pitch
    assert pitch is not None
    return pitch


def first_fielder(data: dict[str, Any]) -> tuple[int, dict[str, Any]]:
    for index, event in enumerate(data["Events"]):
        fielder = event.get("Pitch", {}).get("Contact", {}).get("First Fielder")
        if fielder is not None:
            return index, fielder
    raise AssertionError("no fielded ball")


def test_a_bobbling_fielders_position_is_unknown_before_0_1_9():
    # 0.1.7 and 0.1.8 never set it: real files have positions like 137.
    data = load(V0_1_7A)
    index, fielder = first_fielder(data)
    fielder.update({"Fielder Bobble": 3, "Fielder Position": 137})
    assert fielding_at(data, index).position is None
    fielder["Fielder Bobble"] = 0
    with pytest.raises(StatFileError, match="not a valid Position"):
        read_game(copy.deepcopy(data))
    fielder["Fielder Position"] = 3
    assert fielding_at(data, index).position is Position.SECOND_BASE


def test_a_bobbling_fielders_position_from_0_1_9():
    data = load(V2_2_0)
    index, fielder = first_fielder(data)
    fielder["Fielder Bobble"] = 3
    assert fielding_at(data, index).position is not None


def test_a_pitch_with_no_swing_before_0_1_9():
    # 0.1.7.a and 0.1.8 wrote no "Type of Swing" for a pitch that hit the batter.
    data = load(V0_1_7A)
    del data["Events"][0]["Pitch"]["Type of Swing"]
    assert pitch_at(data, 0).swing is SwingType.NONE
    data = load(V2_2_0)
    del data["Events"][0]["Pitch"]["Type of Swing"]
    with pytest.raises(StatFileError, match="Type of Swing: missing"):
        read_game(data)


def test_star_pitch_is_a_raw_byte_before_0_1_8():
    data = load(V0_1_7A)
    data["Events"][0]["Pitch"]["Star Pitch"] = 3
    assert pitch_at(data, 0).is_star
    data["Version"] = "0.1.8"
    with pytest.raises(StatFileError, match="expected 0 or 1, got 3"):
        read_game(data)


def test_trailing_commas_are_repaired(tmp_path: Path):
    # 0.1.7-0.1.8 crash and quit files end their events with "},\n  ]".
    data = load(V0_1_7A)
    text, count = re.subn(r"\}(\s*\])", r"},\1", json.dumps(data, indent=2), count=1)
    assert count == 1
    broken = tmp_path / "crash.json"
    broken.write_text(text)
    with pytest.raises(json.JSONDecodeError):
        json.loads(text)
    assert read_game(broken) == read_game(data)


# --- (b) At-bat result labels 5 and 6 before 2.3.0 ------------------------------------


def test_decoded_and_encoded_2_2_0_files_decode_alike():
    encoded, decoded = read_game(V2_2_0), read_game(V2_2_0_DECODED)
    assert encoded.away == decoded.away
    assert encoded.home == decoded.home
    assert encoded.events == decoded.events
    assert encoded.result == decoded.result


def test_caught_labels_are_swapped_before_2_3_0():
    data = load(V2_2_0_DECODED)
    assert data["Events"][2]["Result of AB"] == "Caught line-drive"
    assert read_game(data).events[2].result is AtBatResult.CAUGHT


def test_caught_labels_are_right_from_2_3_0():
    data = load(V2_2_0_DECODED)
    data["Version"] = "2.3.0"
    data["GameID"] = "e83bb983"
    assert read_game(data).events[2].result is AtBatResult.CAUGHT_LINE_DRIVE


# --- (b) Contact results before 2.3.0 --------------------------------------------------


def contact_of(data: dict[str, Any], index: int):
    contact = read_game(data).events[index].contact
    assert contact is not None
    return contact


def test_force_out_secondary_is_corrected_before_2_3_0():
    data = load(V2_2_0)
    raw = data["Events"][10]
    assert raw["Runner Batter"]["Out Type"] == OutType.FORCE.id
    assert raw["Pitch"]["Contact"]["Contact Result - Secondary"] == 2  # "Out-tag"
    assert contact_of(data, 10).secondary_result is SecondaryContactResult.OUT_FORCE
    data["Version"], data["GameID"] = "2.3.0", "e83bb983"
    assert contact_of(data, 10).secondary_result is SecondaryContactResult.OUT_TAG


def test_tag_out_secondary_is_corrected_before_2_3_0():
    data = load(V2_2_0)
    raw = data["Events"][10]
    raw["Runner Batter"]["Out Type"] = OutType.TAG.id
    raw["Pitch"]["Contact"]["Contact Result - Secondary"] = 3  # "Foul"
    assert contact_of(data, 10).secondary_result is SecondaryContactResult.OUT_TAG


def test_sac_fly_primary_is_corrected_before_2_3_0():
    data = load(V2_2_0)
    assert data["Events"][59]["Result of AB"] == AtBatResult.SACRIFICE_FLY.id
    assert contact_of(data, 59).primary_result is PrimaryContactResult.OUT
    data["Version"], data["GameID"] = "2.3.0", "e83bb983"
    assert contact_of(data, 59).primary_result is PrimaryContactResult.FAIR


def test_foul_logged_fair_is_corrected_before_2_3_0():
    data = load(V2_2_0)
    raw = data["Events"][2]  # a contact, made into a foul bunt for strike three
    raw["Result of AB"] = AtBatResult.STRIKEOUT.id
    raw["Pitch"]["Contact"]["Contact Result - Primary"] = PrimaryContactResult.FAIR.id
    raw["Pitch"]["Contact"]["Contact Result - Secondary"] = SecondaryContactResult.OUT_CAUGHT.id
    contact = contact_of(data, 2)
    assert contact.primary_result is PrimaryContactResult.FOUL
    assert contact.secondary_result is SecondaryContactResult.FOUL


def test_foul_logged_fair_needs_the_next_event_to_continue_the_at_bat():
    data = load(V2_2_0)
    raw = data["Events"][2]
    raw["Result of AB"] = AtBatResult.NONE.id
    raw["Pitch"]["Contact"]["Contact Result - Primary"] = PrimaryContactResult.FAIR.id
    raw["Pitch"]["Contact"]["Contact Result - Secondary"] = SecondaryContactResult.OUT_CAUGHT.id
    # Event 3 is the next batter, so this isn't a foul.
    assert contact_of(data, 2).primary_result is PrimaryContactResult.FAIR
    following = data["Events"][3]
    for key in ("Inning", "Half Inning", "Batter Roster Loc", "Outs", "Balls"):
        following[key] = raw[key]
    following["Strikes"] = raw["Strikes"] + 1
    assert contact_of(data, 2).primary_result is PrimaryContactResult.FOUL


# --- (b) Ids a decoded file couldn't name ----------------------------------------------


def first_pitch_index(data: dict[str, Any]) -> int:
    return next(i for i, e in enumerate(data["Events"]) if "Contact" in e.get("Pitch", {}))


def test_undecodable_values_are_read_as_their_id():
    data = load(V2_2_0_DECODED)
    index = first_pitch_index(data)
    pitch = data["Events"][index]["Pitch"]
    pitch["Charge Type"] = "Unable to Decode. Invalid Value (1)."
    pitch["Contact"]["Contact Result - Secondary"] = "Unable to Decode. Invalid Value (255)."
    event = read_game(data).events[index]
    assert event.pitch is not None
    assert event.pitch.charge_type is ChargeType.CAPTAIN_STAR
    assert event.contact is not None
    assert event.contact.secondary_result is SecondaryContactResult.NONE


def test_old_stadium_labels_still_read():
    assert load(V2_0_2_MERCY)["StadiumID"] == "Yoshi's Island"
    assert read_game(V2_0_2_MERCY).stadium is Stadium.YOSHI_PARK


# --- Moonshots --------------------------------------------------------------------------


def test_failed_moonshots_from_2_3_0():
    moonshots = [e.contact.moonshot for e in read_game(V2_3_0).events if e.contact is not None]
    assert MoonshotStatus.FAILED in moonshots


# --- Runners ------------------------------------------------------------------------------


def test_every_runner_scores_on_a_home_run():
    data = load(V2_1_1)
    raw = data["Events"][41]
    assert raw["Result of AB"] == AtBatResult.HOME_RUN.id
    assert raw["Runner Batter"]["Runner Result Base"] == 0  # unwritten before 2.2.0
    event = read_game(data).events[41]
    assert event.runs == 2
    assert all(runner.scored for runner in event.runners)
    assert [runner.bases_advanced for runner in event.runners] == [4, 1]


def test_a_runner_put_out_has_no_end_base():
    event = read_game(V2_2_0).events[2]
    batter = event.runners[0]
    assert batter.is_out
    assert batter.out_type is OutType.CAUGHT
    assert batter.end_base is None
    assert batter.bases_advanced == 0


def test_event_numbers_that_wrap_past_255_are_unwrapped():
    data = load(V2_2_0)
    events = data["Events"]
    offset = 256 - 10  # renumber so the byte wraps ten events in, as a long game's does
    for i, raw in enumerate(events):
        raw["Event Num"] = (i + offset) % 256
    numbers = [event.number for event in read_game(data).events]
    assert numbers == list(range(offset, offset + len(events)))


# --- Tag sets, quitters, times, results -------------------------------------------------


def test_tag_set_id():
    assert read_game(V2_2_0).tag_set_id == 198
    assert read_game(V2_3_0).tag_set_id is None  # -1
    assert read_game(V0_1_7A).tag_set_id is None  # no key before 1.9.5
    data = load(V2_2_0)
    data["TagSetID"] = ""  # 1.9.6-2.2.0 for none
    assert read_game(data).tag_set_id is None


def test_1_9_5_empty_tag_set_id_is_repaired(tmp_path: Path):
    text = V1_9_5.read_text().replace('"TagSetID": 3,', '"TagSetID": ,')
    assert '"TagSetID": ,' in text
    broken = tmp_path / "broken.json"
    broken.write_text(text)
    assert read_game(broken).tag_set_id is None


def test_quitters():
    assert read_game(V2_2_0).result.quit_by is None
    assert read_game(V2_0_2_QUIT).result.quit_by is Side.HOME
    assert read_game(V1_9_6_CRASH).result.crashed
    assert read_game(V2_3_0).result.crashed  # encoded 2
    assert read_game(V0_1_7A).result.quit_by is None  # "" in 0.1.7


def test_0_1_7_wrote_the_quitter_as_a_raw_character():
    text = V0_1_7A.read_text().replace('"Quitter Team": ""', '"Quitter Team": "\x01"')
    assert read_game(io.StringIO(text)).result.quit_by is Side.AWAY
    data = load(V0_1_7A)
    data["Quitter Team"] = "\x00"
    assert read_game(data).result.quit_by is Side.HOME


def test_times_are_utc_from_encoded_files_and_naive_from_decoded():
    encoded, decoded = read_game(V2_2_0), read_game(V2_2_0_DECODED)
    assert encoded.start_time == datetime.fromtimestamp(1781826637, tz=UTC)
    assert decoded.start_time == datetime(2026, 6, 18, 18, 50, 37)
    assert decoded.start_time.tzinfo is None


def test_mercy():
    assert read_game(V2_0_2_MERCY).result.is_mercy
    assert not read_game(V2_2_0).result.is_mercy
    assert not read_game(V2_0_2_QUIT).result.is_mercy


def test_an_away_mercy_win_ends_with_the_home_team_batting():
    # The mercy file is a home win in the bottom of the first; flip the score.
    data = load(V2_0_2_MERCY)
    data["Away Score"], data["Home Score"] = 10, 0
    assert read_game(data).result.is_mercy
    # Cut off before the home half, the game can't have ended on the mercy rule.
    data["Events"] = [e for e in data["Events"] if e["Half Inning"] == 0]
    assert not read_game(data).result.is_mercy


def test_walkoffs_in_extra_innings():
    for path, result in ((V2_1_1, AtBatResult.DOUBLE), (V1_9_5, AtBatResult.SINGLE)):
        game = read_game(path)
        assert game.innings_played > game.innings_selected
        walkoff = game.walkoff
        assert walkoff is not None
        assert walkoff is game.events[-1]
        assert walkoff.result is result
    assert read_game(V2_2_0).walkoff is None
    assert read_game(V2_0_2_MERCY).walkoff is None


# --- Errors ----------------------------------------------------------------------------------


def test_errors_say_where():
    data = load(V2_2_0)
    del data["Events"][3]["Pitch"]["Type of Swing"]
    with pytest.raises(StatFileError) as caught:
        read_game(data)
    assert caught.value.key == "Events[3].Pitch.Type of Swing"
    assert "missing" in str(caught.value)


def test_errors_name_the_file(tmp_path: Path):
    bad = tmp_path / "bad.json"
    bad.write_text("[1, 2]")
    with pytest.raises(StatFileError) as caught:
        read_game(bad)
    assert caught.value.path == str(bad)
    bad.write_text("{")
    with pytest.raises(StatFileError, match="not valid JSON"):
        read_game(bad)


def test_bad_values_are_stat_file_errors():
    data = load(V2_2_0)
    data["Events"][0]["Batter Roster Loc"] = 9
    with pytest.raises(StatFileError, match="out of range"):
        read_game(copy.deepcopy(data))
    data = load(V2_2_0)
    data["StadiumID"] = 99
    with pytest.raises(StatFileError, match="not a valid Stadium"):
        read_game(data)
    data = load(V2_2_0)
    data["Quitter Team"] = 7
    with pytest.raises(StatFileError, match="quitter"):
        read_game(data)


def test_stat_file_error_is_a_value_error():
    assert issubclass(StatFileError, ValueError)


# --- HUD files --------------------------------------------------------------------------------


def test_hud_encoded_and_decoded_alike():
    encoded = read_hud(FIXTURES / "hud.json", version="2.2.0")
    decoded = read_hud(FIXTURES / "decoded.hud.json", version=Version(2, 2, 0))
    assert encoded == decoded
    assert encoded.game_id == 3896251267
    assert encoded.event_number == 210
    assert encoded.is_play_over
    assert encoded.state.inning == 9
    assert encoded.away.score == 9
    assert (encoded.away_port, encoded.port(Side.HOME)) == (0, 1)
    assert encoded.home_inning_runs == (0, 0, 0, 2, 5, 0, 3, 2, 0)
    assert encoded.batter_spot is encoded.away.roster[2]
    assert encoded.fielding_positions[encoded.away.roster[0]] is Position.SECOND_BASE
    assert str(encoded.state.bases) == "123"


def test_hud_before_2_2_0_has_no_header():
    data = load(FIXTURES / "hud.json")
    for key in ("GameID", "TagSetID", "StadiumID", "Innings Selected", "Away Logo", "Home Logo"):
        del data[key]
    hud = read_hud(data, version="2.1.1")
    assert hud.game_id is None
    assert hud.stadium is None
    assert hud.away_logo is None


def test_hud_play_is_the_stat_file_event():
    # The fixture's HUD file is the last frame Rio wrote for the fixture game.
    hud = read_hud(FIXTURES / "hud.json", version="2.2.0")
    game = read_game(FIXTURES / "20260618T191655_SpiceOrange-Vs-MattGree_3896251267.json")
    assert hud.play == game.events[-1]
    assert hud.play is not None
    assert hud.play.state is hud.state
    assert hud.runners == hud.play.runners


def test_hud_pitch_thrown_file_has_no_play():
    data = load(FIXTURES / "hud.json")
    data["Event Num"] = "211"
    hud = read_hud(data, version="2.2.0")
    assert not hud.is_play_over
    assert hud.play is None
    assert not hud.is_game_over


def test_hud_before_2_2_0_has_no_play():
    data = load(FIXTURES / "hud.json")
    del data["GameID"]
    assert read_hud(data, version="2.1.1").play is None


def test_hud_fielder():
    hud = read_hud(FIXTURES / "hud.json", version="2.2.0")
    pitcher = hud.fielder(Position.PITCHER)
    assert pitcher is not None
    assert pitcher.side is Side.HOME
    assert hud.fielder(Position.SECOND_BASE, Side.AWAY) is hud.away.roster[0]
    assert hud.play is not None
    assert hud.play.catcher_spot is hud.fielder(Position.CATCHER)


def walk_off(data: dict[str, Any]) -> dict[str, Any]:
    """The fixture's last frame as a bottom-of-the-9th solo home run at 12-12."""
    data = copy.deepcopy(data)
    data["Half Inning"] = 1
    data["Away Score"] = data["Home Score"] = 12
    data["Outs"], data["Num Outs During Play"] = 1, 0
    for key in ("Runner 1B", "Runner 2B", "Runner 3B"):
        data.pop(key, None)
    batter = data["Runner Batter"]
    batter.update(
        {"Runner Roster Loc": 2, "Out Type": 0, "Out Location": 0, "Runner Result Base": 4}
    )
    data["Batter Roster Loc"] = 2
    data["Previous Event"]["Result of AB"] = 10
    data["Previous Event"]["RBI"] = 1
    for spot in range(9):  # the away side allowed 12, the home run makes 13
        stats = data[f"Away Roster {spot}"]["Defensive Stats"]
        stats["Runs Allowed"] = 13 if spot == 0 else 0
    return data


def test_hud_walk_off():
    hud = read_hud(walk_off(load(FIXTURES / "hud.json")), version="2.2.0")
    assert hud.play is not None
    assert hud.play.runs == 1
    assert (hud.away.score, hud.home.score) == (12, 13)
    assert hud.state.home_score == 12
    assert hud.home_inning_runs is not None
    assert hud.home_inning_runs[8] == 1
    assert hud.is_game_over


@pytest.mark.parametrize(
    ("inning", "outs_during_play", "home_score_after", "over"),
    [
        (9, 0, 12, False),  # still level in the bottom of the 9th
        (8, 0, 13, False),  # home ahead mid-half, before the last inning
        (8, 2, 13, False),  # the 8th ends with home ahead: the 9th is still played
        (5, 2, 22, True),  # the 5th ends with home 10 ahead: the mercy rule
        (9, 2, 12, False),  # the 9th ends level: extra innings
    ],
)
def test_hud_game_over(inning: int, outs_during_play: int, home_score_after: int, over: bool):
    data = walk_off(load(FIXTURES / "hud.json"))
    data["Inning"], data["Num Outs During Play"] = inning, outs_during_play
    data["Home Score"] = home_score_after - 1  # a solo home run
    data["Away Roster 0"]["Defensive Stats"]["Runs Allowed"] = home_score_after
    hud = read_hud(data, version="2.2.0")
    assert hud.home.score == home_score_after
    assert hud.is_game_over is over


def test_hud_mercy_rule_off():
    data = walk_off(load(FIXTURES / "hud.json"))
    data["Inning"], data["Num Outs During Play"], data["Mercy On"] = 5, 2, 0
    data["Home Score"] = 21
    data["Away Roster 0"]["Defensive Stats"]["Runs Allowed"] = 22
    assert not read_hud(data, version="2.2.0").is_game_over


def test_hud_runs_from_runners_when_stats_disagree():
    data = walk_off(load(FIXTURES / "hud.json"))
    data["Away Roster 0"]["Defensive Stats"]["Runs Allowed"] = 0  # a resumed game's stats
    hud = read_hud(data, version="2.2.0")
    assert hud.play is not None
    assert hud.play.runs == 1


def test_hud_version_must_parse():
    with pytest.raises(StatFileError):
        read_hud(FIXTURES / "hud.json", version="soon")


def test_dickballs():
    game = read_game(V2_1_1)
    assert [e.number for e in game.events if e.pitch and e.pitch.is_dickball] == [79, 85]


def test_bunts_before_2_3_0_are_read_from_the_contact():
    # The fixture game's one contacted pitch with no swing logged was a bunt.
    game = read_game(FIXTURES / "20260618T191655_SpiceOrange-Vs-MattGree_3896251267.json")
    bunts = [e for e in game.events if e.pitch and e.pitch.swing is SwingType.BUNT]
    assert len(bunts) == 1
    assert bunts[0].contact is not None
    assert not any(e.pitch and e.pitch.swing is SwingType.NONE and e.contact for e in game.events)


def test_a_2_3_0_file_keeps_its_swing_none():
    data = load(STAT_FILES / "2.3.0/synthetic.SpiceOrange-Vs-MattGree.json")
    event = next(e for e in data["Events"] if "Contact" in e.get("Pitch", {}))
    event["Pitch"]["Type of Swing"] = 0
    game = read_game(data)
    assert any(e.pitch and e.pitch.swing is SwingType.NONE and e.contact for e in game.events)

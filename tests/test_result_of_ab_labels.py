"""Project Rio 2.3.0 corrected the result labels it writes to match the game.

A decoded file keeps the labels the version that wrote it used, so the same
game result reaches pyrio under two different names depending on the file's
age. These pin the correction: one id means one thing, whichever Rio wrote it.

Ported from main's test of the same name. prep's value objects are strict --
an unknown label raises -- so without the correction an older file would not
load at all, and a swapped one would load as the *wrong* result silently.
"""
import json
import pathlib

import pytest

from pyrio.rio_value import Tables, FinalResult, SecondaryContactResult
from pyrio.stat_file import EventObj, StatObj

FIXTURES = pathlib.Path(__file__).parent / "fixtures"


def event_with(result, version=None) -> EventObj:
    stat_json = {'Events': [{'Result of AB': result}]}
    if version is not None:
        stat_json['Version'] = version
    return EventObj(StatObj(stat_json), 0)


@pytest.mark.parametrize('written, expected', [
    ('Caught', 'Caught line-drive'),
    ('Caught line-drive', 'Caught'),
    ('Error - Input', 'Error'),
    ('Error - Chem', 'Fielders Choice'),
    ('Single', 'Single'),
])
def test_older_files_are_corrected(written, expected):
    assert event_with(written, '2.2.0').result_of_AB().name == expected


@pytest.mark.parametrize('label', ['Caught', 'Caught line-drive', 'Error', 'Fielders Choice'])
def test_current_files_are_left_alone(label):
    assert event_with(label, '2.3.0').result_of_AB().name == label


def test_old_error_labels_are_renamed_on_any_version():
    # A pure rename needs no version gate: neither old name exists in 2.3.0,
    # so the string itself says which era wrote it.
    assert event_with('Error - Chem', '2.3.0').result_of_AB().name == 'Fielders Choice'


@pytest.mark.parametrize('version, before', [
    (None, True),
    ('0.1.7a', True),
    ('1.9.2', True),
    ('2.2.0', True),
    ('2.3.0', False),
    ('2.3.1', False),
    ('2.10.0', False),
    ('3.0.0', False),
])
def test_version_cutoff(version, before):
    assert event_with('None', version).rioStat.versionBefore(2, 3, 0) is before


@pytest.mark.parametrize('version', ['2.2.0', '2.3.0'])
def test_every_corrected_label_is_a_known_result(version):
    known = set(Tables.FINAL_RESULT.values())
    for written in ['Caught', 'Caught line-drive', 'Error - Input', 'Error - Chem']:
        assert event_with(written, version).result_of_AB().name in known


def test_unset_secondary_contact_result_decodes():
    assert SecondaryContactResult.from_raw(255).name == 'None'


# --- the ids, not just the names -------------------------------------------
# The names alone cannot catch a swap: both are valid labels in both eras. The
# id is what downstream code joins on, so that is what has to be right.

def test_a_pre_2_3_caught_line_drive_is_id_6():
    assert event_with('Caught line-drive', '2.2.0').result_of_AB().id == 6


def test_a_2_3_caught_line_drive_is_id_5():
    assert event_with('Caught line-drive', '2.3.0').result_of_AB().id == 5


def test_the_2_2_0_fixture_decodes_its_caught_balls_as_id_6():
    """The real file this suite ships is 2.2.0, and it is full of the swapped
    label -- so it is the case the correction exists for."""
    path = FIXTURES / "decoded.20260618T191655_SpiceOrange-Vs-MattGree_3896251267.json"
    stat = StatObj(json.loads(path.read_text()))
    assert stat.versionBefore(2, 3, 0) is True
    line_drives = [
        EventObj(stat, n).result_of_AB()
        for n, e in enumerate(stat.events())
        if e.get('Result of AB') == 'Caught line-drive'
    ]
    assert line_drives, "fixture no longer carries the swapped label"
    assert {r.id for r in line_drives} == {6}
    assert {r.name for r in line_drives} == {'Caught'}


def test_encoded_ids_are_never_corrected():
    """An encoded file holds the game's own id, which never changed."""
    for version in ('2.2.0', '2.3.0'):
        assert event_with(5, version).result_of_AB().id == 5
        assert event_with(6, version).result_of_AB().id == 6

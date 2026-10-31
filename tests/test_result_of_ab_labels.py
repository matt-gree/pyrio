"""Project Rio 2.3.0 corrected the "Result of AB" labels to match the game's
AT_BAT_RESULT. Decoded files keep the labels they were written with, so a file
from any version has to land on the same LookupDicts.FINAL_RESULT names.

An unknown label is a KeyError in EventSearch, which would stop an older file
from loading at all.
"""
import pytest

from pyrio.lookup import LookupDicts
from pyrio.stat_file_parser import EventObj, StatObj


def event_with(result: str, version: str = None) -> EventObj:
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
    assert event_with(written, '2.2.0').result_of_AB() == expected


@pytest.mark.parametrize('label', ['Caught', 'Caught line-drive', 'Error', 'Fielders Choice'])
def test_current_files_are_left_alone(label):
    assert event_with(label, '2.3.0').result_of_AB() == label


def test_old_error_labels_are_renamed_on_any_version():
    assert event_with('Error - Chem', '2.3.0').result_of_AB() == 'Fielders Choice'


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
    assert event_with('None', version).rioStat.versionBefore2_3() is before


@pytest.mark.parametrize('version', ['2.2.0', '2.3.0'])
def test_every_corrected_label_is_a_known_result(version):
    results = set(LookupDicts.FINAL_RESULT.values())
    for written in ['Caught', 'Caught line-drive', 'Error - Input', 'Error - Chem']:
        assert event_with(written, version).result_of_AB() in results


def test_unset_secondary_contact_result_decodes():
    assert LookupDicts.SECONDARY_CONTACT_RESULT[255] == 'None'

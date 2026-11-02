"""EventSearch reads every event in a file, so anything odd in one has to be sorted
into the search rather than stop the file from loading.
"""
import pytest

from pyrio.stat_file_parser import EventSearch, StatObj


def game_file(charge_type: str = 'N/A') -> dict:
    return {
        'Version': '2.2.0',
        'Away Score': 0,
        'Home Score': 0,
        'Innings Played': 1,
        'Character Game Stats': {f'{team} Roster {slot}': {'CharID': f'{team} {slot}'}
                                 for team in ('Away', 'Home') for slot in range(9)},
        'Events': [{
            'Inning': 1, 'Half Inning': 0, 'Away Score': 0, 'Home Score': 0, 'Balls': 0,
            'Strikes': 0, 'Outs': 0, 'Star Chance': 0, 'Pitcher Stamina': 9,
            'Chemistry Links on Base': 0, 'Pitcher Roster Loc': 0, 'Batter Roster Loc': 0,
            'RBI': 0, 'Num Outs During Play': 0, 'Result of AB': 'None',
            'Runner Batter': {'Out Type': 'None', 'Steal': 'None'},
            'Pitch': {
                'Pitch Type': 'Charge', 'Charge Type': charge_type, 'Star Pitch': 0,
                'In Strikezone': 1, 'Type of Swing': 'Slap',
                'Ball Position - Strikezone': 0.0,
            },
        }],
    }


def game_file_with_first_fielder(character: str) -> dict:
    stat_file = game_file()
    stat_file['Events'][0]['Pitch']['Contact'] = {
        'Type of Contact': 'Nice - Left',
        'Input Direction - Stick': 'Left',
        'Frame of Swing Upon Contact': 4,
        'Star Swing Five-Star': 'None',
        'Ball Contact Pos - X': 0.0,
        'Ball Contact Pos - Z': 0.0,
        'First Fielder': {
            'Fielder Character': character,
            'Fielder Position': 'SS',
            'Fielder Bobble': 'None',
            'Fielder Action': 'None',
            'Fielder Manual Selected': 'No Selected Char',
        },
    }
    return stat_file


def test_first_fielder_on_a_roster():
    search = EventSearch(StatObj(game_file_with_first_fielder('Home 3')))
    assert search.characterFieldingEvents('Home 3') == {0}


def test_first_fielder_not_on_a_roster():
    search = EventSearch(StatObj(game_file_with_first_fielder('Toad(Y)')))
    assert search.characterFieldingEvents('Toad(Y)') == {0}
    assert search.characterAtBatEvents('Toad(Y)') == set()
    assert search.positionFieldingEvents('SS') == {0}


def test_character_who_never_appears_has_no_events():
    assert EventSearch(StatObj(game_file())).characterFieldingEvents('Luigi') == set()


@pytest.mark.parametrize('label', ['Charged Captain Star', 'ChargedStar', 'Unable to Decode. Invalid Value (1).'])
def test_every_charged_captain_star_label_is_searchable(label):
    search = EventSearch(StatObj(game_file(label)))
    assert search._charge_type_dict['Charged Captain Star'] == {0}

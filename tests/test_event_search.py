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


@pytest.mark.parametrize('label', ['Charged Captain Star', 'ChargedStar', 'Unable to Decode. Invalid Value (1).'])
def test_every_charged_captain_star_label_is_searchable(label):
    search = EventSearch(StatObj(game_file(label)))
    assert search._charge_type_dict['Charged Captain Star'] == {0}

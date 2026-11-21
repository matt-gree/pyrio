"""EventSearch has to load a file it cannot fully make sense of.

Its buckets are sized from the game's own summary fields, and those can
disagree with the events: an unfinished game's final score and "Innings
Played" sit BEHIND what a live event reports, a quit file's last event never
got an out count, and a fielder is logged separately from the rosters so he
may be on neither team. Each of those used to raise and take the whole file
with it.

Ported from main's 047a4fd and ee1dd08, which fixed them with setdefault.
"""
import pytest

import pathlib

from pyrio.rio_value import Tables
from pyrio.stat_file import EventSearch, StatObj, UNFINISHED_PLAY_NUM_OUTS

FIXTURES = pathlib.Path(__file__).parent / 'fixtures'
DECODED = 'decoded.20260618T191655_SpiceOrange-Vs-MattGree_3896251267.json'

ROSTER = {f'{side} Roster {spot}': {
    'CharID': 0 if side == 'Away' else 1,     # Mario / Luigi
    'Captain': 1 if spot == 0 else 0,
    'Superstar': 0,
    'Batting Hand': 'Right',
    'Fielding Hand': 'Right',
    'Offensive Stats': {}, 'Defensive Stats': {},
} for side in ('Away', 'Home') for spot in range(9)}


def event(**over):
    base = {
        'Inning': 1, 'Half Inning': 0, 'Batter Roster Loc': 0,
        'Pitcher Roster Loc': 0, 'Away Score': 0, 'Home Score': 0,
        'Balls': 0, 'Strikes': 0, 'Outs': 0, 'Num Outs During Play': 0,
        'RBI': 0, 'Pitcher Stamina': 10, 'Star Chance': 0,
        'Chemistry Links on Base': 0, 'Away Stars': 0, 'Home Stars': 0,
        'Result of AB': 'Strikeout', 'Pitch': {},
    }
    base.update(over)
    return base


def stat_with(events, **top):
    payload = {
        'Version': '2.3.0', 'StadiumID': 'Mario Stadium',
        'Away Score': 0, 'Home Score': 0, 'Innings Selected': 9,
        'Innings Played': 1, 'Quitter Team': 'None',
        'Character Game Stats': ROSTER, 'Events': events,
    }
    payload.update(top)
    return StatObj(payload)


def test_a_live_score_ahead_of_the_final_score_still_loads():
    # The summary says 0-0; the event says someone is up 3. An unfinished game.
    search = EventSearch(stat_with([event(**{'Away Score': 3})]))
    assert search is not None


def test_an_inning_past_innings_played_still_loads():
    search = EventSearch(stat_with([event(Inning=7)], **{'Innings Played': 1}))
    assert search is not None


def test_an_event_that_never_finished_is_not_indexed_by_its_out_count():
    search = EventSearch(stat_with([
        event(**{'Num Outs During Play': 1}),
        event(**{'Num Outs During Play': UNFINISHED_PLAY_NUM_OUTS}),
    ]))
    # The real out count is searchable; the sentinel is not a bucket.
    assert 0 in search._outs_during_event_dict or 1 in search._outs_during_event_dict
    assert UNFINISHED_PLAY_NUM_OUTS not in search._outs_during_event_dict


def test_a_fielder_on_neither_roster_still_loads_and_stays_searchable():
    """Built from the real fixture rather than by hand: EventSearch indexes
    most of a contact event unconditionally, so a minimal fake tests the
    fixture's own gaps instead of this fix."""
    import copy
    import json

    raw = json.loads((FIXTURES / DECODED).read_text())
    rosters = {c['CharID'] for c in raw['Character Game Stats'].values()}

    off_roster = next(name for cid, name in Tables.CHAR_NAME.items()
                      if name not in rosters)

    fielded = None
    for ev in raw['Events']:
        first = (ev.get('Pitch', {}).get('Contact') or {}).get('First Fielder')
        if first:
            fielded = first
            break
    assert fielded, 'fixture has no fielded contact to retag'

    doctored = copy.deepcopy(raw)
    for ev in doctored['Events']:
        first = (ev.get('Pitch', {}).get('Contact') or {}).get('First Fielder')
        if first:
            first['Fielder Character'] = off_roster
            break

    search = EventSearch(StatObj(doctored))          # must not raise
    fielding = [c for c, actions in search.character_action_dict.items()
                if actions['Fielding'] and c.name == off_roster]
    assert fielding, f'{off_roster} fielded but is not searchable'

"""simulate_contacts covers every contact the simulator can reproduce, bunts
included, whichever way the stat file logged them. Contacts it can't reproduce
are skipped rather than failing the whole game.

Ported from main.
"""
from pyrio import hit_analysis, hit_simulation
from pyrio.stat_file import StatObj


class _Stat(StatObj):
    """A stat file with just enough in it for simulate_contacts to build records.

    prep resolves the batter through StatObj.character(), which reads
    "Character Game Stats", so the roster is supplied as data rather than by
    overriding an accessor (main's version overrode characterName, which prep
    does not use on this path).
    """

    def player(self, teamNum):
        return 'Player'


def _stat(events):
    roster = {f"{side} Roster {spot}": {"CharID": 0}      # 0 = Mario
              for side in ("Away", "Home") for spot in range(9)}
    # 2.3.0: picks the newer "Away/Home Roster N" team keys, and is the era
    # that logs a bunt as its own swing type.
    return _Stat({'Version': '2.3.0', 'Events': events,
                  'Character Game Stats': roster})


def _event(swing, contact=True):
    pitch = {'Type of Swing': swing}
    if contact:
        pitch['Contact'] = {'Contact Result - Primary': 'Fair',
                            'Contact Result - Secondary': 'Bunt'}
    return {
        'Inning': 1, 'Half Inning': 0, 'Batter Roster Loc': 0, 'RBI': 0,
        'Result of AB': 'Bunt', 'Pitch': pitch,
    }


def _simulate(monkeypatch, events, simulate=lambda event: object()):
    monkeypatch.setattr(hit_simulation, 'simulate_hit_from_event', simulate)
    return hit_analysis.simulate_contacts(_stat(events))


def test_both_bunt_labels_are_simulated(monkeypatch):
    records = _simulate(monkeypatch, [_event('Bunt'), _event('None'), _event('Slap')])
    assert [record.swing for record in records] == ['Bunt', 'None', 'Slap']


def test_a_pitch_without_contact_is_skipped(monkeypatch):
    assert _simulate(monkeypatch, [_event('None', contact=False)]) == []


def test_a_contact_the_simulator_rejects_is_skipped(monkeypatch):
    def reject_bunts(event):
        if event.pitch_dict()['Type of Swing'] == 'Bunt':
            raise ValueError('These inputs would not make contact with the ball')
        return object()

    records = _simulate(monkeypatch, [_event('Bunt'), _event('Slap')], reject_bunts)
    assert [record.swing for record in records] == ['Slap']

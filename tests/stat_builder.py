"""Builds minimal stat file dicts for StatObj tests.

Every roster slot gets zeroed stats; pass overrides to set the ones a test needs.
"""

OFFENSIVE_KEYS = ['At Bats', 'Hits', 'Singles', 'Doubles', 'Triples', 'Homeruns', 'Successful Bunts',
                  'Sac Flys', 'Strikeouts', 'Walks (4 Balls)', 'Walks (Hit)', 'RBI', 'Bases Stolen',
                  'Star Hits']
DEFENSIVE_KEYS = ['Batters Faced', 'Runs Allowed', 'Earned Runs', 'Batters Walked', 'Batters Hit',
                  'Hits Allowed', 'HRs Allowed', 'Pitches Thrown', 'Stamina', 'Was Pitcher',
                  'Strikeouts', 'Star Pitches Thrown', 'Big Plays', 'Outs Pitched']
OLD_TEAM_STRUCTURE = ['Pre 0.1.7', '0.1.7a', '0.1.8', '0.1.9', '1.9.1', '1.9.2', '1.9.3', '1.9.4']


def slot_key(version, file_team, roster):
    """The Character Game Stats key for a team as the file itself numbers it."""
    if version in OLD_TEAM_STRUCTURE:
        return f'Team {file_team} Roster {roster}'
    return f"{'Away' if file_team == 0 else 'Home'} Roster {roster}"


def make_stat(version='2.3.0', overrides=None):
    """overrides maps (file_team, roster) to {'Offensive Stats': {...}, 'Defensive Stats': {...}},
    where file_team is the team number as written in the file."""
    overrides = overrides or {}
    chars = {}
    for team in (0, 1):
        for roster in range(9):
            slot = {
                'CharID': f'Char{team}{roster}',
                'Captain': 1 if roster == 0 else 0,
                'Offensive Stats': {k: 0 for k in OFFENSIVE_KEYS},
                'Defensive Stats': {k: 0 for k in DEFENSIVE_KEYS},
            }
            slot['Defensive Stats'].update({'Batters Per Position': [], 'Batter Outs Per Position': [],
                                            'Outs Per Position': []})
            for section, values in overrides.get((team, roster), {}).items():
                slot[section].update(values)
            chars[slot_key(version, team, roster)] = slot
    return {'Version': version, 'Character Game Stats': chars}

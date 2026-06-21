"""HudObj: view over a live-game HUD snapshot."""
from __future__ import annotations

from typing import Optional

from ..lookup import (
    LookupDicts, Lookup, Character, Stadium,
    PitchType, ChargeType, SwingType, ContactType,
    FinalResult, PrimaryContactResult, SecondaryContactResult,
    OutType, StealType, PitchResult,
    Hand, Position, FielderAction, FielderBobble, ManualSelect, TeamName,
)
from .error_checking import ErrorChecker
from .runner import RunnerObj


class HudObj:
    def __init__(self, hud_json: dict):
        self.hud_json = hud_json
        self.event_number = self.hud_json['Event Num']

    def event_integer(self) -> int:
        return int(str(self.event_number)[:-1])

    def player(self, teamNum: int) -> str:
        ErrorChecker.check_team_num(teamNum)
        if teamNum == 0:
            return self.hud_json['Away Player']
        elif teamNum == 1:
            return self.hud_json['Home Player']
    
    def inning(self) -> int:
        return self.hud_json['Inning']
    
    def half_inning(self) -> int:
        return self.hud_json['Half Inning']
    
    def inning_float(self) -> float:
        return float(self.hud_json['Inning'] + 0.5*self.hud_json['Half Inning'])
    
    def score(self, teamNum: int) -> int:
        ErrorChecker.check_team_num(teamNum)
        team_string = "Away" if teamNum == 0 else "Home"
        
        return self.hud_json[f'{team_string} Score']
    
    def balls(self) -> int:
        return self.hud_json['Balls']
    
    def strikes(self) -> int:
        return self.hud_json['Strikes']
    
    def outs(self) -> int:
        return self.hud_json['Outs']
    
    def star_chance(self) -> int:
        return self.hud_json['Star Chance']
    
    def team_stars(self, teamNum: int) -> int:
        ErrorChecker.check_team_num(teamNum)
        team_string = "Away" if teamNum == 0 else "Home"
        
        return self.hud_json[f'{team_string} Stars']
    
    def pitcher_stamina(self) -> int:
        return self.hud_json['Pitcher Stamina']
    
    def chem_on_base(self) -> int:
        return self.hud_json['Chemistry Links on Base']
    
    def outs_during_play(self) -> int:
        return self.hud_json['Num Outs During Play']
    
    def pitcher_roster_location(self) -> int:
        return self.hud_json['Pitcher Roster Loc']
    
    def batter_roster_location(self, teamNum: Optional[int] = None) -> int:
        # no teamNum -> current batter; otherwise the given team's due-up batter
        if teamNum is None:
            return self.hud_json['Batter Roster Loc']
        ErrorChecker.check_team_num(teamNum)
        team_string = "Away" if teamNum == 0 else "Home"
        return self.hud_json[f'{team_string} Batter Roster Loc']

    def port(self, teamNum: int) -> int:
        ErrorChecker.check_team_num(teamNum)
        team_string = "Away" if teamNum == 0 else "Home"
        return self.hud_json[f'{team_string} Port']

    def previous_event(self) -> Optional[dict]:
        """Raw 'Previous Event' sub-object from the HUD, or None if absent."""
        return self.hud_json.get('Previous Event')
    
    def runner_on_first(self) -> bool:
        return bool(self.hud_json.get('Runner 1B'))

    def runner_on_second(self) -> bool:
        return bool(self.hud_json.get('Runner 2B'))

    def runner_on_third(self) -> bool:
        return bool(self.hud_json.get('Runner 3B'))

    def runner_char_name(self, base: int) -> str:
        """Return the character name of the runner on the given base (1, 2, or 3), or '' if empty."""
        runner = self.hud_json.get(f'Runner {base}B')
        if runner and isinstance(runner, dict):
            return runner.get('Runner Char Id', '')
        return ''

    def team_roster_str(self, teamNum: int, rosterNum: int):
        ErrorChecker.check_team_num(teamNum)
        ErrorChecker.check_roster_num(rosterNum)
        team_string = "Away" if teamNum == 0 else "Home"
        return f'{team_string} Roster {rosterNum}'
    
    def character_offensive_stats(self, teamNum: int, rosterNum: int):
        ErrorChecker.check_team_num(teamNum)
        ErrorChecker.check_roster_num(rosterNum)
        return self.hud_json[self.team_roster_str(teamNum, rosterNum)]['Offensive Stats']
    
    def character_defensive_stats(self, teamNum: int, rosterNum: int):
        ErrorChecker.check_team_num(teamNum)
        ErrorChecker.check_roster_num(rosterNum)
        return self.hud_json[self.team_roster_str(teamNum, rosterNum)]['Defensive Stats']

    # --- game settings ---
    def stadium(self) -> Stadium:
        return Lookup.stadium(self.hud_json["StadiumID"])

    def logo(self, teamNum: int) -> TeamName:
        # the team's logo/team-name selection
        ErrorChecker.check_team_num(teamNum)
        team_string = "Away" if teamNum == 0 else "Home"
        return Lookup.team_name(self.hud_json[f'{team_string} Logo'])

    def first_batting_team(self) -> int:
        return self.hud_json['First Batting Team']

    def star_skills_on(self) -> bool:
        return bool(self.hud_json['Star Skills On'])

    def mercy_on(self) -> bool:
        return bool(self.hud_json['Mercy On'])

    def innings_selected(self) -> int:
        return self.hud_json['Innings Selected']

    def inning_scores(self, teamNum: int) -> list[int]:
        ErrorChecker.check_team_num(teamNum)
        team_string = "Away" if teamNum == 0 else "Home"
        return self.hud_json.get(f'{team_string} Inning Scores', [])

    # --- per-character ---
    def _player(self, teamNum: int, rosterNum: int) -> dict:
        return self.hud_json[self.team_roster_str(teamNum, rosterNum)]

    def character(self, teamNum: int, rosterNum: int) -> Character:
        return Lookup.character(self._player(teamNum, rosterNum)['CharID'])

    def position(self, teamNum: int, rosterNum: int) -> Position:
        return Lookup.position(self._player(teamNum, rosterNum)['Fielding Position'])

    def fielding_hand(self, teamNum: int, rosterNum: int) -> Hand:
        return Lookup.hand(self._player(teamNum, rosterNum)['Fielding Hand'])

    def batting_hand(self, teamNum: int, rosterNum: int) -> Hand:
        return Lookup.hand(self._player(teamNum, rosterNum)['Batting Hand'])

    def is_superstar(self, teamNum: int, rosterNum: int) -> bool:
        return bool(self._player(teamNum, rosterNum)['Superstar'])

    def captain(self, teamNum: int) -> Character:
        return self.character(teamNum, self.captain_index(teamNum))

    def runner(self, base: int) -> Optional[RunnerObj]:
        """RunnerObj on the given base (0 = batter-runner), or None if empty."""
        runner_str = 'Runner Batter' if base == 0 else f'Runner {base}B'
        runner_json = self.hud_json.get(runner_str)
        return RunnerObj(runner_json) if isinstance(runner_json, dict) else None

    def roster(self, teamNum: int) -> dict:
        roster_dict = {}
        for i in range(9):
            player = self.hud_json[self.team_roster_str(teamNum, i)]
            roster_dict[i] = {}
            roster_dict[i]['captain'] = player['Captain']
            roster_dict[i]['char_id'] = player['CharID']

        return roster_dict
    
    def inning_end(self) -> bool:
        return self.hud_json['Outs'] + self.hud_json['Num Outs During Play'] == 3
    
    def event_result(self) -> str:
        if str(self.hud_json['Event Num'])[-1] == 'b':
            return self.hud_json['Result of AB']
        
        return 'In Play'
    
    def captain_index(self, teamNum: int) -> int:
        ErrorChecker.check_team_num(teamNum)
        for i in range(9):
            if self.hud_json[self.team_roster_str(teamNum,i)]['Captain'] == 1:
                return int(i)
        raise Exception(f'No captain on teamNum {teamNum}')
    
    def batting_team(self):
        return self.half_inning()
    
    def fielding_team(self):
        return abs(self.half_inning()-1)

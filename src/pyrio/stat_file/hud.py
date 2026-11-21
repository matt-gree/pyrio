"""HudObj: view over a live-game HUD snapshot."""
from __future__ import annotations

from typing import Optional

from ..rio_value import (
    Tables, Character, Stadium,
    PitchType, ChargeType, SwingType, ContactType,
    FinalResult, PrimaryContactResult, SecondaryContactResult,
    OutType, StealType, PitchResult,
    Hand, Position, FielderAction, FielderBobble, ManualSelect, TeamName,
)
from .error_checking import ErrorChecker
# Shared with StatObj.isMercy, so the live and post-hoc predicates cannot drift.
from .stat_obj import MERCY_MARGIN
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
        return Stadium.from_raw(self.hud_json["StadiumID"])

    def logo(self, teamNum: int) -> TeamName:
        # the team's logo/team-name selection
        ErrorChecker.check_team_num(teamNum)
        team_string = "Away" if teamNum == 0 else "Home"
        return TeamName.from_raw(self.hud_json[f'{team_string} Logo'])

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
        return Character.from_raw(self._player(teamNum, rosterNum)['CharID'])

    def position(self, teamNum: int, rosterNum: int) -> Position:
        return Position.from_raw(self._player(teamNum, rosterNum)['Fielding Position'])

    def fielding_hand(self, teamNum: int, rosterNum: int) -> Hand:
        return Hand.from_raw(self._player(teamNum, rosterNum)['Fielding Hand'])

    def batting_hand(self, teamNum: int, rosterNum: int) -> Hand:
        return Hand.from_raw(self._player(teamNum, rosterNum)['Batting Hand'])

    def is_superstar(self, teamNum: int, rosterNum: int) -> bool:
        return bool(self._player(teamNum, rosterNum)['Superstar'])

    def captain(self, teamNum: int) -> Character:
        return self.character(teamNum, self.captain_index(teamNum))

    def due_up(self, teamNum: Optional[int] = None) -> list[Character]:
        """Batting order starting from the current batter (defaults to the batting team)."""
        if teamNum is None:
            teamNum = self.batting_team()
        ErrorChecker.check_team_num(teamNum)
        start = self.batter_roster_location(teamNum)
        return [self.character(teamNum, (start + i) % 9) for i in range(9)]

    def team_positions(self, teamNum: int) -> list[int]:
        """Roster slot at each fielding position, indexed 0=P,1=C,...,8=RF (-1 if unset)."""
        ErrorChecker.check_team_num(teamNum)
        positions = [-1] * 9
        for roster_num in range(9):
            pos = self.position(teamNum, roster_num)
            if 0 <= pos.id <= 8:
                positions[pos.id] = roster_num
        return positions

    def roster_id_at_position(self, teamNum: int, position) -> int:
        """Roster slot playing the given position (int 0-8 or a name like 'SS')."""
        ErrorChecker.check_team_num(teamNum)
        ErrorChecker.check_position(position)
        pos_id = position if isinstance(position, int) else Position.from_raw(position).id
        return self.team_positions(teamNum)[pos_id]

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
    
    def event_resolved(self) -> bool:
        """Whether this frame was written at a play's RESOLUTION.

        Project Rio writes two frames per event: one while the play is in
        flight (``Event Num`` "120") and one when it resolves ("120b"). Only
        the second describes a completed play — which is why ``Previous Event``
        on a "…b" frame is that very event and not the one before it.
        """
        return str(self.hud_json.get('Event Num', '')).endswith('b')

    def inning_end(self) -> bool:
        """Whether the play on THIS frame ends the half-inning.

        ONLY A RESOLVED FRAME MAY ADD THE TWO OUT FIELDS. ``Outs`` is the
        half's count and ``Num Outs During Play`` is what the current play
        added, so the sum is the question — but between resolutions ``Outs``
        has already absorbed the last play while ``Num Outs During Play`` still
        describes it, and adding them counts one out twice. That answered "the
        half is over" with two outs and a batter at the plate, which is
        invisible until some other condition is also met: a board sitting on a
        10-run mercy margin flipped to Final and back to Live with every HUD
        write, once per in-flight frame after the second out. Measured over 773
        stat files: the sum is never wrong on a resolved event, and 533 of
        those games contain at least one in-flight frame where it is.

        In flight, ``Outs`` alone is authoritative — and it resets at three, so
        it answers False for every frame of a half that is still being played.

        >= rather than == : a play that records more outs than the half had
        left still ends the half, and a predicate that answers False there
        fails silently — nothing downstream can tell "the half is not over"
        from "we could not tell".
        """
        outs = self.hud_json['Outs']
        if not self.event_resolved():
            return outs >= 3
        return outs + self.hud_json['Num Outs During Play'] >= 3

    def game_over(self) -> bool:
        """Whether this frame is the last one of the game.

        MSB's HUD has no end-of-game event: the frame recording the final out
        (or the winning run) is simply the last one written, and the next event
        belongs to the next game. So "is this game over" is a question about ONE
        frame, answered with no history — which is also what lets a caller
        re-derive it from a stale file on disk after a restart.

        REGULATION AND MERCY ARE THE SAME RULE at two margins. Both say an
        unnecessary half-inning is not played, and both give the team batting
        second its chance to respond:

          - after the TOP half, the bottom is skipped only if the team batting
            second is ALREADY ahead — by any margin once regulation is complete,
            or by the mercy margin at any point in the game. A team batting
            first that goes ahead by 10 does not end it; the other side bats.
          - after the BOTTOM half, the game ends if the scores differ in
            regulation, or if either side leads by the mercy margin. A tie in
            regulation goes to extras.
          - a walk-off ends play mid-half, without a third out.

        Sides are resolved through ``first_batting_team`` rather than
        away/home, which are not interchangeable with batting order.

        Deliberately conservative: anything it cannot establish resolves to
        False, so it answers late rather than calling a game that is still being
        played — which is also why a half-inning boundary is only read off a
        RESOLVED frame (see ``inning_end``). Quits and disconnects are NOT detectable here — the file just
        stops — and are the stat file's to report (``StatObj.wasQuit``).
        """
        innings = self.innings_selected()
        if not innings:
            return False

        first_t = self.first_batting_team()
        if first_t not in (0, 1):
            return False
        second_t = 1 - first_t
        # Positive = the team batting second is ahead.
        lead = self.score(second_t) - self.score(first_t)

        regulation = self.inning() >= innings
        # The half the team batting SECOND is in. ``half_inning`` is the
        # BATTING TEAM's away/home id (``batting_team`` returns the same
        # number), which is only "top/bottom" while the away team bats first —
        # so deriving this from away/home inverted both halves of the rule for
        # a game where HOME batted first: the walk-off branch, which has no
        # ``inning_end`` gate at all, fired through the first-batting team's
        # half, and a real walk-off in the second-batting team's half was
        # missed. Same reason the scores resolve through ``first_batting_team``.
        bottom = self.half_inning() == second_t

        # Walk-off. Only reachable in regulation or later: if the team batting
        # second were already ahead going into this half, the half would not be
        # being played at all (the skip-bottom branch below).
        if bottom and regulation and lead > 0:
            return True

        if not self.inning_end():
            return False

        if not bottom:
            return lead > 0 and (regulation or lead >= MERCY_MARGIN)

        return (regulation and lead != 0) or abs(lead) >= MERCY_MARGIN
    
    def event_result(self) -> str:
        # `Result of AB` lives on `Previous Event`, which on a resolved frame
        # IS this event — read from the top level and this raised KeyError on
        # exactly the frames it claims to describe.
        if self.event_resolved():
            return (self.hud_json.get('Previous Event') or {}).get('Result of AB', 'In Play')

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

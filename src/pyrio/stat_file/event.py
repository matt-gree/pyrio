"""EventObj: a read-only view over a single stat-file event row."""
from __future__ import annotations

from typing import Optional

from ..rio_value import (
    Character, PitchType, ChargeType, SwingType, ContactType,
    FinalResult, PrimaryContactResult, SecondaryContactResult,
    Position, FielderAction, FielderBobble, ManualSelect, DeadBallReason,
)
from .error_checking import ErrorChecker
from .stat_obj import StatObj
from .runner import RunnerObj


class EventObj():
    def __init__(self, rioStat: StatObj, eventNum: int):
        self.rioStat = rioStat
        self.all_events = rioStat.events()
        if abs(eventNum) > len(self.all_events):
            raise IndexError(f'Invalid event num: Event {eventNum} does not exist in game')
        self.eventDict = self.all_events[eventNum]

    def safe_int(self, value) -> Optional[int]:
        """
        Tries to safely convert a str to an integer.

        Args:
        - value: The value to be converted to an integer.

        Returns:
        - The integer value if the conversion is successful.
        - None if the value cannot be converted to an integer.
        """
        if value is None:
            return None
        if isinstance(value, int):
            return value  # Return if it's already an integer
        elif isinstance(value, str):
            try:
                return int(value)  # Try converting a string to an integer
            except ValueError:
                raise ValueError(f"Value '{value}' is not a valid integer.")

        # If it's neither a string nor an integer, raise an exception
        raise ValueError(f"{value}' cannot be converted to an integer.")

    def event_num(self) -> int:
        return self.eventDict['Event Num']

    def inning(self) -> int:
        # returns the ininng from a specified event
        return self.eventDict["Inning"]

    def half_inning(self) -> int:
        # returns the half ininng from a specified event
        return self.eventDict["Half Inning"]

    def score(self, teamNum: int) -> int:
        ErrorChecker.check_team_num(teamNum)
        if teamNum == 0:
            return self.eventDict['Away Score']
        else:
            return self.eventDict['Home Score']

    def balls(self) -> int:
        # returns the ininng from a specified event
        return self.eventDict["Balls"]

    def strikes(self) -> int:
        # returns the strikes from a specified event
        return self.eventDict["Strikes"]

    def outs(self) -> int:
        # returns the ininng from a specified event
        return self.eventDict["Outs"]

    def star_chance(self) -> int:
        return self.eventDict['Star Chance']

    def team_stars(self, teamNum: int) -> int:
        ErrorChecker.check_team_num(teamNum)
        if teamNum == 0:
            return self.eventDict['Away Stars']
        else:
            return self.eventDict['Home Stars']

    def pitcher_stamina(self) -> int:
        return self.eventDict['Pitcher Stamina']

    def chem_links_on_base(self) -> int:
        return self.eventDict["Chemistry Links on Base"]

    def batting_team(self) -> int:
        return self.half_inning()

    def pitching_team(self) -> int:
        return abs(self.half_inning() - 1)

    def pitcher_roster_loc(self) -> int:
        return self.eventDict['Pitcher Roster Loc']

    def pitcher(self) -> Character:
        return self.rioStat.character(self.pitching_team(), self.eventDict['Pitcher Roster Loc'])

    def batter_roster_loc(self) -> int:
        return self.eventDict['Batter Roster Loc']

    def batter(self) -> Character:
        return self.rioStat.character(self.batting_team(), self.eventDict['Batter Roster Loc'])

    def batter_hand(self) -> int:
        return self.rioStat.battingHand(self.batting_team(), self.eventDict['Batter Roster Loc'])

    def catcher(self) -> Character:
        return self.rioStat.character(self.batting_team(), self.eventDict['Catcher Roster Loc'])

    def rbi(self) -> int:
        # returns the rbi from a specified event
        return self.eventDict['RBI']

    def num_outs_during_play(self) -> int:
        return self.eventDict['Num Outs During Play']

    def result_of_AB(self) -> FinalResult:
        """The at-bat result, with pre-2.3.0 labels corrected on read.

        Only the decoded (string) form needs correcting. An encoded file holds
        the game's own id, which never changed -- it was Rio's label table that
        had 5 and 6 the wrong way round, so the maps match names only and an id
        passes straight through.
        """
        return FinalResult.from_raw(
            self.rioStat.correctedResultLabel(self.eventDict['Result of AB']))

    def dead_ball_reason(self) -> Optional[DeadBallReason]:
        """Why the ball went dead this event, or None if the field is absent."""
        return DeadBallReason.from_raw(self.eventDict.get('Dead Ball Reason'))

    def runners(self) -> set[str]:
        return set(self.eventDict).intersection(['Runner 1B', 'Runner 2B', 'Runner 3B'])

    def bool_runner_on_base(self, baseNum: int) -> int:
        """
        checks if a runner is on the supplied base number
        if -1 is provided, then all bases will be checked
        """
        ErrorChecker.check_base_num(baseNum)
        if baseNum == -1:
            for i in range(1,4):
                if self.bool_runner_on_base(i) == 1:
                    return 1
            return 0

        runner_str = f'Runner {baseNum}B'
        return 1 if self.eventDict.get(runner_str) else 0

    def runner_dict(self, baseNum: int) -> dict:
        ErrorChecker.check_base_num(baseNum)
        if baseNum == 0:
            runner_str = 'Runner Batter'
        else:
            runner_str = f'Runner {baseNum}B'
        return self.eventDict.get(runner_str, {})

    def runner(self, base_num: int) -> Optional[RunnerObj]:
        """RunnerObj on the given base (0 = batter-runner), or None if empty."""
        runner_json = self.runner_dict(base_num)
        return RunnerObj(runner_json) if runner_json else None

    def bool_steal(self, base_num: int) -> int:
        """
        Checks if a runner is stealing from the supplied base number.
        If -1 is provided, then all bases will be checked.
        """
        ErrorChecker.check_base_num(base_num)

        if base_num == -1:  # Check all bases for a steal
            for i in range(1, 4):
                if self.bool_steal(i) == 1:
                    return 1
            return 0

        runner_data = self.runner_dict(base_num)
        return 1 if runner_data and runner_data.get('Steal') != 'None' else 0

    def pitch_dict(self) -> dict:
        """
        Returns an empty dict if no pitch in event
        """
        return self.eventDict.get('Pitch', {})

    def pitch_pitcher(self) -> Optional[Character]:
        """Pitcher for this pitch (from the pitch sub-dict), or None if no pitch."""
        return Character.from_raw(self.pitch_dict().get('Pitcher Char Id'))

    def pitch_pitcher_team(self) -> Optional[int]:
        """Team num (0/1) of the pitcher for this pitch, or None if no pitch."""
        return self.pitch_dict().get('Pitcher Team Id')

    def pitch_type(self) -> Optional[PitchType]:
        """
        Returns None if no pitch in event
        """
        return PitchType.from_raw(self.pitch_dict().get('Pitch Type'))

    def charge_type(self) -> Optional[ChargeType]:
        """
        Returns None if no pitch in event
        """
        return ChargeType.from_raw(self.pitch_dict().get('Charge Type'))

    def star_pitch(self) -> Optional[int]:
        """
        Returns None if no pitch in event
        """
        return self.pitch_dict().get('Star Pitch')

    def pitch_speed(self) -> Optional[int]:
        """
        Returns None if no pitch in event
        """
        return self.pitch_dict().get('Pitch Speed')

    def ball_position_strikezone(self) -> Optional[float]:
        """
        Returns None if no pitch in event
        """
        return self.pitch_dict().get('Ball Position - Strikezone')

    def in_strikezone(self) -> Optional[int]:
        """
        Returns None if no pitch in event
        """
        return self.pitch_dict().get('In Strikezone')

    def bat_contact_position_x(self) -> Optional[float]:
        """
        Returns None if no pitch in event
        """
        return self.pitch_dict().get('Bat Contact Pos - X')

    def bat_contact_position_z(self) -> Optional[float]:
        """
        Returns None if no pitch in event
        """
        return self.pitch_dict().get('Bat Contact Pos - Z')

    def dickball(self) -> Optional[int]:
        """
        Returns None if no pitch in event
        """
        return self.pitch_dict().get('DB')

    def type_of_swing(self) -> Optional[SwingType]:
        """
        Returns None if no pitch in event
        """
        return SwingType.from_raw(self.pitch_dict().get('Type of Swing'))

    def contact_dict(self) -> dict:
        """
        Returns an empty dict if no contact in event
        """
        return self.pitch_dict().get('Contact', {})

    def type_of_contact(self) -> Optional[ContactType]:
        """
        Returns None if no contact in event
        """
        return ContactType.from_raw(self.contact_dict().get('Type of Contact'))

    def charge_power_up(self) -> Optional[int]:
        """
        Returns None if no contact in event
        """
        return self.contact_dict().get('Charge Power Up')

    def charge_power_down(self) -> Optional[int]:
        """
        Returns None if no contact in event
        """
        return self.contact_dict().get('Charge Power Down')

    def five_star_swing(self) -> Optional[int]:
        """
        Returns None if no contact in event
        """
        return self.contact_dict().get('Star Swing Five-Star')

    def input_direction_push_or_pull(self) -> Optional[str]:
        """
        Returns None if no contact in event
        """
        return self.contact_dict().get('Input Direction - Push/Pull')

    def stick_input_direction(self) -> Optional[str]:
        """
        Returns None if no contact in event
        """
        return self.contact_dict().get('Input Direction - Stick')

    def contact_frame(self) -> Optional[int]:
        """
        Returns None if no contact in event
        """
        return self.safe_int(self.contact_dict().get('Frame of Swing Upon Contact'))

    def ball_power(self) -> Optional[int]:
        """
        Returns None if no contact in event
        """
        return self.safe_int(self.contact_dict().get('Ball Power'))

    def vert_angle(self) -> Optional[int]:
        """
        Returns None if no contact in event.
        """
        return self.safe_int(self.contact_dict().get('Vert Angle'))

    def horiz_angle(self) -> Optional[int]:
        """
        Returns None if no contact in event.
        """
        return self.safe_int(self.contact_dict().get('Horiz Angle'))

    def contact_absolute(self) -> Optional[float]:
        """
        Returns None if no contact in event.
        """
        return self.contact_dict().get('Contact Absolute')

    def contact_quality(self) -> Optional[float]:
        """
        Returns None if no contact in event.
        """
        return self.contact_dict().get('Contact Quality')

    def rng(self) -> tuple[Optional[int], Optional[int], Optional[int]]:
        """
        Returns None if no contact in event.
        Returns a vector (rng1, rng2, rng3) of RNG components.
        """
        rng1 = self.safe_int(self.contact_dict().get('RNG1'))
        rng2 = self.safe_int(self.contact_dict().get('RNG2'))
        rng3 = self.safe_int(self.contact_dict().get('RNG3'))
        return (rng1, rng2, rng3)

    def ball_velocity(self) -> tuple:
        """
        Returns None if no contact in event.
        Returns a vector (x, y, z) of ball velocity components.
        """
        x = self.contact_dict().get('Ball Velocity - X')
        y = self.contact_dict().get('Ball Velocity - Y')
        z = self.contact_dict().get('Ball Velocity - Z')
        return (x, y, z)

    def ball_contact_position(self) -> tuple:
        """
        Returns None if no contact in event.
        Returns a vector (x, z) of ball contact position components.
        """
        x = self.contact_dict().get('Ball Contact Pos - X')
        z = self.contact_dict().get('Ball Contact Pos - Z')
        return (x, z)

    def ball_landing_position(self) -> tuple:
        """
        Returns None if no contact in event.
        Returns a vector (x, y, z) of ball landing position components.
        """
        x = self.contact_dict().get('Ball Landing Position - X')
        y = self.contact_dict().get('Ball Landing Position - Y')
        z = self.contact_dict().get('Ball Landing Position - Z')
        return (x, y, z)

    def ball_max_height(self) -> Optional[float]:
        """
        Returns None if no contact in event.
        """
        return self.contact_dict().get('Ball Max Height')

    def ball_hang_time(self) -> Optional[int]:
        """
        Returns None if no contact in event.
        """
        return self.safe_int(self.contact_dict().get('Ball Hang Time'))

    def contact_result_primary(self) -> Optional[PrimaryContactResult]:
        """
        Returns None if no contact in event.
        """
        return PrimaryContactResult.from_raw(self.contact_dict().get('Contact Result - Primary'))

    def contact_result_secondary(self) -> Optional[SecondaryContactResult]:
        """
        Returns None if no contact in event.
        """
        raw = self.contact_dict().get('Contact Result - Secondary')
        if raw is None:
            return None
        return SecondaryContactResult.from_raw(self.rioStat.correctedResultLabel(raw))

    def first_fielder_dict(self) -> dict:
        """
        Returns an empty dict if no first fielder in event
        """
        return self.contact_dict().get('First Fielder', {})

    def first_fielder_roster_loc(self) -> Optional[int]:
        """
        Returns None if no first fielder in event.
        """
        return self.first_fielder_dict().get('Fielder Roster Location')

    def first_fielder_position(self) -> Optional[Position]:
        """
        Returns None if no first fielder in event.
        """
        return Position.from_raw(self.first_fielder_dict().get('Fielder Position'))

    def first_fielder_character(self) -> Optional[Character]:
        """
        Returns None if no first fielder in event.
        """
        return Character.from_raw(self.first_fielder_dict().get('Fielder Character'))

    def first_fielder_action(self) -> Optional[FielderAction]:
        """
        Returns None if no first fielder in event.
        """
        return FielderAction.from_raw(self.first_fielder_dict().get('Fielder Action'))

    def first_fielder_jump(self) -> Optional[str]:
        """
        Returns None if no first fielder in event.
        """
        return self.first_fielder_dict().get('Fielder Jump')

    def fielder_swap(self) -> Optional[str]:
        """
        Returns None if no first fielder in event.
        """
        return self.first_fielder_dict().get('Fielder Swap')

    def first_fielder_maunual_selected(self) -> Optional[ManualSelect]:
        """
        Returns None if no first fielder in event.
        """
        return ManualSelect.from_raw(self.first_fielder_dict().get('Fielder Manual Selected'))

    def first_fielder_location(self) -> tuple:
        """
        Returns None if no first fielder in event.
        Returns a vector (x, y, z) of fielder position components.
        """
        x = self.first_fielder_dict().get('Fielder Position - X')
        y = self.first_fielder_dict().get('Fielder Position - Y')
        z = self.first_fielder_dict().get('Fielder Position - Z')
        return (x, y, z)

    def first_fielder_bobble(self) -> Optional[FielderBobble]:
        """
        Returns None if no first fielder in event.
        """
        return FielderBobble.from_raw(self.first_fielder_dict().get('Fielder Bobble'))

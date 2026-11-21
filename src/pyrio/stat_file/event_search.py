"""EventSearch: inverted-index queries over all events in a stat file."""
from __future__ import annotations

from .event import EventObj
from .stat_obj import StatObj
from ..rio_value import (
    Tables, Character, PitchType, ChargeType, SwingType,
    ContactType, FinalResult, Position,
)


class EventSearch():
    def __init__(self, rioStat: StatObj):
        self.debug_mode = False

        self.rioStat: StatObj = rioStat

        # Buckets keyed on value objects, so they line up with what the
        # EventObj accessors return (FinalResult, Position, ...).
        self._result_of_AB_dict: dict[FinalResult, set[int]] = {FinalResult.from_raw(i): set() for i in Tables.FINAL_RESULT}
        self._first_fielder_position_dict: dict[Position, set[int]] = {Position.from_raw(i): set() for i in Tables.POSITION if i is not None}
        self._pitch_type_dict: dict[PitchType, set[int]] = {PitchType.from_raw(i): set() for i in Tables.PITCH_TYPE}
        self._charge_type_dict: dict[ChargeType, set[int]] = {ChargeType.from_raw(i): set() for i in Tables.CHARGE_TYPE}
        self._swing_type_dict: dict[SwingType, set[int]] = {SwingType.from_raw(i): set() for i in Tables.TYPE_OF_SWING}
        self._contact_type_dict: dict[ContactType, set[int]] = {ContactType.from_raw(i): set() for i in Tables.CONTACT_TYPE}
        # Stick input has no value object; keep it keyed on the raw decoded string.
        self._input_direction_dict: dict[str, set[int]] = {value: set() for value in Tables.INPUT_DIRECTION.values()}

        self._rbi_dict: dict[int, set[int]] = {i: set() for i in range(5)}
        self._inning_dict: dict[int, set[int]] = {i: set() for i in range(1, self.rioStat.inningsPlayed()+1)}
        self._away_score_dict: dict[int, set[int]] = {i: set() for i in range(0, self.rioStat.score(0)+1)}
        self._home_score_dict: dict[int, set[int]] = {i: set() for i in range(0, self.rioStat.score(1)+1)}
        self._balls_dict: dict[int, set[int]] = {i: set() for i in range(4)}
        self._strikes_dict: dict[int, set[int]] = {i: set() for i in range(5)}
        self._outs_in_inning_dict: dict[int, set[int]] = {i: set() for i in range(3)}
        self._half_inning_dict: dict[int, set[int]] = {i: set() for i in range(2)}
        self._chem_on_base_dict: dict[int, set[int]] = {i: set() for i in range(4)}
        self._runners_on_base_dict: dict[int, set[int]] = {i: set() for i in range(4)}
        self._pitcher_stamina_dict: dict[int, set[int]] = {i: set() for i in range(11)}
        self._star_chance_dict: dict[int, set[int]] = {i: set() for i in range(2)}
        self._outs_during_event_dict: dict[int, set[int]] = {i: set() for i in range(4)}
        self._pitch_in_strikezone_dict: dict[int, set[int]] = {i: set() for i in range(2)}
        self._contact_frame_dict: dict[int, set[int]] = {i: set() for i in range(11)}
        self._ball_position_strikezone: dict[int, set[int]] = {}
        self._x_ball_contact_pos: dict[int, set[int]] = {}

        self._steal: set[int] = set()
        self._star_pitch: set[int] = set()
        self._bobble: set[int] = set()
        self._fireball_burn: set[int] = set()
        self._five_star_dinger: set[int] = set()
        self._sliding_catch: set[int] = set()
        self._wall_jump: set[int] = set()
        self._manual_character_selection: set[int] = set()
        self._first_pitch_of_AB: set[int] = set()
        self._last_pitch_of_AB: set[int] = set()
        self._home_team_winning: set[int] = set()
        self._away_team_winning: set[int] = set()
        self._game_tied: set[int] = set()
        self._lead_changed: set[int] = set()

        self.character_action_dict: dict[Character, dict[str, set[int]]] = {}
        for characterDict in self.rioStat.characterGameStats().values():
            self.character_action_dict[Character.from_raw(characterDict['CharID'])] = {
                'AtBat': set(),
                'Pitching': set(),
                'Fielding': set()
            }

        for eventNum, event in enumerate(self.rioStat.events()):
            # Older versions of rio overflowed past event 255, this is fixed in a later version
            # When using the search function, it is ideal for events to be singly identified.
            rioEventNum = eventNum % 256
            currentEvent = EventObj(rioStat, eventNum)

            batting_team = currentEvent.half_inning()
            fielding_team = abs(batting_team-1)

            batter = currentEvent.batter()
            pitcher = currentEvent.pitcher()

            self.character_action_dict[batter]['AtBat'].add(eventNum)
            self.character_action_dict[pitcher]['Pitching'].add(eventNum)

            self._away_score_dict[currentEvent.score(0)].add(eventNum)
            self._home_score_dict[currentEvent.score(1)].add(eventNum)

            if currentEvent.score(0) > currentEvent.score(1):
                self._away_team_winning.add(eventNum)
            elif currentEvent.score(0) < currentEvent.score(1):
                self._home_team_winning.add(eventNum)
            else:
                self._game_tied.add(eventNum)

            if (currentEvent.score(batting_team) + currentEvent.rbi() > currentEvent.score(fielding_team)) and (currentEvent.score(batting_team) <= currentEvent.score(fielding_team)):
                self._lead_changed.add(eventNum)

            self._outs_in_inning_dict[currentEvent.outs()].add(eventNum)
            self._chem_on_base_dict[currentEvent.chem_links_on_base()].add(eventNum)
            self._strikes_dict[currentEvent.strikes()].add(eventNum)
            self._balls_dict[currentEvent.balls()].add(eventNum)
            self._inning_dict[currentEvent.inning()].add(eventNum)
            self._rbi_dict[currentEvent.rbi()].add(eventNum)
            self._pitcher_stamina_dict[currentEvent.pitcher_stamina()].add(eventNum)
            self._star_chance_dict[currentEvent.star_chance()].add(eventNum)
            self._outs_during_event_dict[currentEvent.num_outs_during_play()].add(eventNum)

            self._half_inning_dict[currentEvent.half_inning()].add(eventNum)
            self._result_of_AB_dict[currentEvent.result_of_AB()].add(eventNum)

            if currentEvent.bool_runner_on_base(-1) == 0:
                self._runners_on_base_dict[0].add(eventNum)
            else:
                for i in range(1,4):
                    if currentEvent.bool_runner_on_base(i):
                        self._runners_on_base_dict[i].add(eventNum)

            if currentEvent.bool_steal(-1):
                self._steal.add(eventNum)


            if not currentEvent.pitch_dict():
                continue

            if currentEvent.balls() == 0 and currentEvent.strikes() == 0:
                self._first_pitch_of_AB.add(eventNum)

            if currentEvent.result_of_AB().name != 'None':
                self._last_pitch_of_AB.add(eventNum)

            try:
                self._pitch_type_dict[currentEvent.pitch_type()].add(eventNum)
            except KeyError:
                if self.debug_mode:
                    print(f'{self.rioStat.gameID()}, {eventNum}: Pitch Type: {currentEvent.pitch_type()}')

            try:
                self._charge_type_dict[currentEvent.charge_type()].add(eventNum)
            except KeyError:
                if self.debug_mode:
                    print(f'{self.rioStat.gameID()}, {eventNum}: Charge Type: {currentEvent.charge_type()}')

            self._pitch_in_strikezone_dict[currentEvent.in_strikezone()].add(eventNum)
            self._swing_type_dict[currentEvent.type_of_swing()].add(eventNum)

            if currentEvent.star_pitch() == 1:
                self._star_pitch.add(eventNum)

            # Banded at two decimal places
            rounded_strikezone_x_pos = round(currentEvent.ball_position_strikezone(), 2)

            if rounded_strikezone_x_pos not in self._ball_position_strikezone:
                self._ball_position_strikezone[rounded_strikezone_x_pos] = set()

            self._ball_position_strikezone[rounded_strikezone_x_pos].add(eventNum)

            if not currentEvent.contact_dict():
                continue

            self._contact_type_dict[currentEvent.type_of_contact()].add(eventNum)
            self._input_direction_dict[currentEvent.stick_input_direction()].add(eventNum)
            self._contact_frame_dict[currentEvent.contact_frame()].add(eventNum)


            if currentEvent.five_star_swing() == 1:
                self._five_star_dinger.add(eventNum)

            # Banded at two decimal places

            x_ball_contact_postion = round(currentEvent.ball_contact_position()[0], 2)

            if x_ball_contact_postion not in self._x_ball_contact_pos:
                self._x_ball_contact_pos[x_ball_contact_postion] = set()

            self._x_ball_contact_pos[x_ball_contact_postion].add(eventNum)

            if not currentEvent.first_fielder_dict():
                continue

            self.character_action_dict[currentEvent.first_fielder_character()]['Fielding'].add(eventNum)

            if currentEvent.first_fielder_bobble().name != 'None':
                self._bobble.add(eventNum)

            if currentEvent.first_fielder_bobble().name == 'Fireball':
                self._fireball_burn.add(eventNum)

            if currentEvent.first_fielder_action().name == 'Sliding':
                self._sliding_catch.add(eventNum)

            if currentEvent.first_fielder_action().name == 'Walljump':
                self._wall_jump.add(eventNum)

            self._first_fielder_position_dict[currentEvent.first_fielder_position()].add(eventNum)

            if currentEvent.first_fielder_maunual_selected().name != 'No Selected Char':
                self._manual_character_selection.add(eventNum)

    # --- value-object bucket resolvers -------------------------------------
    # Accept a canonical name (or id) and return the matching event bucket,
    # so the query methods below read in terms of names while the indices stay
    # keyed on value objects.
    def _ab_bucket(self, name) -> set[int]:
        return self._result_of_AB_dict[FinalResult.from_raw(name)]

    def _pitch_bucket(self, name) -> set[int]:
        return self._pitch_type_dict[PitchType.from_raw(name)]

    def _charge_bucket(self, name) -> set[int]:
        return self._charge_type_dict[ChargeType.from_raw(name)]

    def _swing_bucket(self, name) -> set[int]:
        return self._swing_type_dict[SwingType.from_raw(name)]

    def _contact_bucket(self, name) -> set[int]:
        return self._contact_type_dict[ContactType.from_raw(name)]

    def __errorCheck_fielder_pos(self, fielderPos) -> None:
        # tells if fielderPos is valid
        if fielderPos.upper() not in Tables.POSITION.values():
            raise ValueError(f"Invalid fielder position {fielderPos}. Function accepts {Tables.POSITION.values()}")

    def __errorCheck_baseNum(self, baseNum: int) -> None:
        # tells if baseNum is valid representing 1st, 2nd and 3rd base
        if abs(baseNum) not in [0,1,2,3]:
            raise ValueError(f'Invalid base num {baseNum}. Function only accepts base numbers of -3 to 3.')

    def __errorCheck_halfInningNum(self, halfInningNum: int) -> None:
        if halfInningNum not in [0,1]:
            raise ValueError(f'Invalid Half Inning num {halfInningNum}. Function only accepts half inning numbers of 0 or 1.')

    def __errorCheck_outsNum(self, outsNum: int) -> None:
        # tells if outsNum is valid; negatives select "this many outs or more"
        if abs(outsNum) not in [0,1,2]:
            raise ValueError(f'Invalid outs num {outsNum}. Function only accepts outs numbers of -2 to 2.')

    def noneResultEvents(self) -> set[int]:
        # returns a set of events who's result is none
        return self._ab_bucket('None')

    def strikeoutResultEvents(self) -> set[int]:
        # returns a set of events where the result is a strikeout
        return self._ab_bucket('Strikeout')

    def walkResultEvents(self, include_hbp=True, include_bb=True) -> set[int]:
        # returns a set of events where the batter recorded a type of hit
        # can be used to reutrn just walks or just hbp
        # defaults to returning both
        if include_hbp & include_bb:
            return self._ab_bucket('Walk (HBP)') | self._ab_bucket('Walk (BB)')
        if include_hbp:
            return self._ab_bucket('Walk (HBP)')
        if include_bb:
            return self._ab_bucket('Walk (BB)')
        else:
            return set()

    def outResultEvents(self) -> set[int]:
        # returns a set of events where the result is out
        return self._ab_bucket('Out')

    def caughtResultEvents(self) -> set[int]:
        # returns a set of events where the result is caught
        return self._ab_bucket('Caught')

    def caughtLineDriveResultsEvents(self) -> set[int]:
        # returns a set of events where the result is caught line drive
        return self._ab_bucket('Caught line-drive')

    def hitResultEvents(self, numberOfBases=0) -> set[int]:
        # returns a set of events where the batter recorded a type of hit
        # can return singles, doubles, triples, HRs or all hits
        # returns all hits if numberOfBases is not 1-4
        if numberOfBases == 1:
            return self._ab_bucket('Single')
        elif numberOfBases == 2:
            return self._ab_bucket('Double')
        elif numberOfBases == 3:
            return self._ab_bucket('Triple')
        elif numberOfBases == 4:
            return self._ab_bucket('HR')
        else:
            return self._ab_bucket('Single') | self._ab_bucket('Double') | self._ab_bucket('Triple') | self._ab_bucket('HR')

    def inputErrorResultEvents(self) -> set[int]:
        # returns a set of events where the result is a input error
        return self._ab_bucket('Error - Input')

    def chemErrorResultEvents(self) -> set[int]:
        # returns a set of events where the result is a chem error
        return self._ab_bucket('Error - Chem')

    def buntResultEvents(self) -> set[int]:
        #returns a set of events of successful bunts
        return self._ab_bucket('Bunt')

    def sacFlyResultEvents(self) -> set[int]:
        #returns a set of events of sac flys
        return self._ab_bucket('SacFly')

    def groundBallDoublePlayResultEvents(self) -> set[int]:
        # returns a set of events where the result is a ground ball double play
        return self._ab_bucket('Ground ball double Play')

    def foulCatchResultEvents(self) -> set[int]:
        # returns a set of events where the result is a foul catch
        return self._ab_bucket('Foul catch')

    def allOutResultEvents(self) -> set[int]:
        # returns a set of events where the result is any type of out
        return set().union(
            self.strikeoutResultEvents(),
            self.outResultEvents(),
            self.caughtResultEvents(),
            self.caughtLineDriveResultsEvents(),
            self.sacFlyResultEvents(),
            self.groundBallDoublePlayResultEvents(),
            self.foulCatchResultEvents()
        )

    def stealEvents(self) -> set[int]:
        # returns a set of events where an steal happened
        # types of steals: None, Ready, Normal, Perfect
        return self._steal

    def starPitchEvents(self) -> set[int]:
        # returns a set of events where a star pitch is used
        return self._star_pitch

    def bobbleEvents(self) -> set[int]:
        # returns a set of events where any kind of bobble occurs
        # Bobble types: "None" "Slide/stun lock" "Fumble", "Bobble",
        # "Fireball", "Garlic knockout" "None"
        return self._bobble

    def fireballBurnEvents(self) -> set[int]:
        # returns a set of events where a fireball burn bobble occurs
        return self._fireball_burn

    def fiveStarDingerEvents(self) -> set[int]:
        # returns a set of events where a five star dinger occurs
        return self._five_star_dinger

    def slidingCatchEvents(self) -> set[int]:
        # returns a set of events where the fielder made a sliding catch
        # not to be confused with the character ability sliding catch
        return self._sliding_catch

    def wallJumpEvents(self) -> set[int]:
        # returns a set of events where the fielder made a wall jump
        return self._wall_jump

    def firstFielderPositionEvents(self, location_abbreviation) -> set[int]:
        # returns a set of events where the first fielder on the ball
        # is the one provided in the function argument
        pos = Position.from_raw(location_abbreviation)
        if pos not in self._first_fielder_position_dict:
            raise ValueError(f'Invalid roster arg {location_abbreviation}. Function only accepts location abbreviations {[p.name for p in self._first_fielder_position_dict]}')
        return self._first_fielder_position_dict[pos]

    def manualCharacterSelectionEvents(self) -> set[int]:
        # returns a set of events where a fielder was manually selected
        return self._manual_character_selection

    def runnerOnBaseEvents(self, baseNums: list) -> set[int]:
        # returns a set of events where runners were on the specified bases
        # the input baseNums is a list of three numbers -3 to 3
        # the numbers indicate what base the runner is to appear on
        # if the base number is positive, then the returned events will all have a runner
        # on that base.
        # if the base number is negative, then the returned events will not care whether a runner
        # appears on that base or not
        # if the base number is not provided, then the returned events will not have a runner
        # on that base.
        # examples: baseNums = [1,2] will return events that had runners only on both 1st and 2nd base
        # baseNums = [1,2, -3] will return events that had runners on both 1st or 2nd whether or not a runner is on 3rd
        # baseNums = [-1, -2, -3] will return events any time any runners are on any base
        # baseNums = [-1, -2, 0] will return events with no runners, or runners on first or second, but none that have runners on 3rd

        for num in baseNums:
            self.__errorCheck_baseNum(num)

        if len(baseNums) > 3:
            raise ValueError('Too many baseNums provided. runnerOnBaseEvents accepts at most 3 bases')

        if baseNums == [0]:
            return self._runners_on_base_dict[0]

        runner_on_base = self._runners_on_base_dict

        exclude_bases = [1,2,3]
        required_bases = []
        optional_bases = []
        for i in baseNums:
            if abs(i) in exclude_bases:
                exclude_bases.remove(abs(i))
            if i > 0:
                required_bases.append(i)
            else:
                optional_bases.append(abs(i))

        if required_bases and (0 in optional_bases):
            raise ValueError(f'The argument 0 may only be provided alongside optional arguments or itself')

        if required_bases:
            # Start from every event and narrow to those with a runner on each
            # required base. Optional bases mean "don't care", so they are not
            # unioned in -- they are simply left out of exclude_bases above.
            result = set(range(self.rioStat.final_event() + 1))
            for base in required_bases:
                result.intersection_update(runner_on_base[base])
        else:
            result = set()
            for base in optional_bases:
                result = result.union(runner_on_base[base])

        if exclude_bases:
            for base in exclude_bases:
                result.difference_update(runner_on_base[base])

        return result

    def listInputHandling(self, inputList, class_variable, to_zero=False) -> set[int]:
        # Used with class variables that have integer keys
        result = set()
        for i in inputList:
            if abs(i) not in class_variable:
                continue
            if i >= 0:
                result = result.union(class_variable[i])
            else:
                if to_zero:
                    for j in range(0, abs(i)):
                        result = result.union(class_variable[j])
                else:
                    for j in range(abs(i), max(class_variable)+1):
                        result = result.union(class_variable[j])

        return result

    def inningEvents(self, inningNum) -> set[int]:
        inningNumList = inningNum if isinstance(inningNum, (list, set)) else [inningNum]
        # returns a set of events that occurered in the inning input
        # negative inputs return all events after the specified inning
        return self.listInputHandling(inningNumList, self._inning_dict)

    def awayTeamWinningEvents(self) -> set[int]:
        return self._away_team_winning

    def homeTeamWinningEvents(self) -> set[int]:
        return self._home_team_winning

    def gameTiedEvents(self) -> set[int]:
        return self._game_tied

    def awayScoreEvents(self, awayScore) -> set[int]:
        # returns a set of events that occurered with the away score
        # negative inputs return all events with an away score greater than or equal to the input
        # inputting a list or set will return the all events that match the numbers in the list
        awayScoreList = awayScore if isinstance(awayScore, (list, set)) else [awayScore]
        return self.listInputHandling(awayScoreList, self._home_score_dict)

    def homeScoreEvents(self, homeScore) -> set[int]:
        # returns a set of events that occurered with the home score
        # negative inputs return all events with a home score greater than or equal to the input
        # inputting a list or set will return the all events that match the numbers in the list
        homeScoreList = homeScore if isinstance(homeScore, (list, set)) else [homeScore]
        return self.listInputHandling(homeScoreList, self._home_score_dict)

    def ballEvents(self, ballNum) -> set[int]:
        # returns a set of events that occurered with the number of balls in the count
        # negative inputs return all events with a ball count greater than or equal to the input
        # inputting a list or set will return the all events that match the numbers in the list
        ballNumList = ballNum if isinstance(ballNum, (list, set)) else [ballNum]
        return self.listInputHandling(ballNumList, self._balls_dict)

    def strikeEvents(self, strikeNum) -> set[int]:
        # returns a set of events that occurered with the number of strikes in the count
        # negative inputs return all events with a strike count greater than or equal to the input
        # inputting a list or set will return the all events that match the numbers in the list
        strikeNumList = strikeNum if isinstance(strikeNum, (list, set)) else [strikeNum]
        return self.listInputHandling(strikeNumList, self._strikes_dict)

    def chemOnBaseEvents(self, chemNum) -> set[int]:
        # returns a set of events that occurered with the number of chem on base
        # negative inputs return all events with a chem count greater than or equal to the input
        # inputting a list or set will return the all events that match the numbers in the list
        chemNumList = chemNum if isinstance(chemNum, (list, set)) else [chemNum]
        return self.listInputHandling(chemNumList, self._chem_on_base_dict)

    def rbiEvents(self, rbiNum) -> set[int]:
        # returns a set of events that occurered with the number of chem on base
        # negative inputs return all events with a chem count greater than or equal to the input
        # inputting a list or set will return the all events that match the numbers in the list
        rbiNumList = rbiNum if isinstance(rbiNum, (list, set)) else [rbiNum]
        return self.listInputHandling(rbiNumList, self._rbi_dict)


    def halfInningEvents(self, halfInningNum: int) -> set[int]:
          self.__errorCheck_halfInningNum(halfInningNum)
          return self._half_inning_dict[halfInningNum]

    def outsInInningEvents(self, outsNum: int) -> set[int]:
        # negative inputs return all events with that many outs OR MORE
        self.__errorCheck_outsNum(outsNum)
        if outsNum >= 0:
            return self._outs_in_inning_dict[outsNum]
        else:
            result = set()
            for i in range(abs(outsNum), 3):
                result = result.union(self._outs_in_inning_dict[i])
            return result

    def pitcherStaminaEvents(self, stamina) -> set[int]:
        # returns a set of events that occurered with the number of pitcher stamina
        # negative inputs return all events with a stamina LESS THAN or equal to the input
        # inputting a list or set will return the all events that match the numbers in the list
        staminaList = stamina if isinstance(stamina, (list, set)) else [stamina]
        return self.listInputHandling(staminaList, self._pitcher_stamina_dict, to_zero=True)

    def starChanceEvents(self, isStarChance=True) -> set[int]:
        if isStarChance:
            return self._star_chance_dict[1]
        return self._star_chance_dict[0]

    def numOutsDuringPlayEvents(self, numOuts) -> set[int]:
         numOutsList = numOuts if isinstance(numOuts, (list, set)) else [numOuts]
         return self.listInputHandling(numOutsList, self._outs_during_event_dict)

    def curvePitchTypeEvents(self) -> set[int]:
        return self._pitch_bucket('Curve')

    def chargePitchTypeEvents(self) -> set[int]:
        return self._pitch_bucket('Charge')

    def sliderPitchTypeEvents(self) -> set[int]:
        return self._charge_bucket('Slider')

    def perfectChargePitchTypeEvents(self) -> set[int]:
        return self._charge_bucket('Perfect')

    def changeUpPitchTypeEvents(self) -> set[int]:
        return self._pitch_bucket('ChangeUp')

    def pitchTypeEvents(self, pitchType) -> set[int]:
        pitchTypeList = pitchType if isinstance(pitchType, (list, set)) else [pitchType]

        result = set()
        for pitch in pitchTypeList:
            if pitch.lower() == 'curve':
                result = result.union(self.curvePitchTypeEvents())
            elif pitch.lower() == 'charge':
                result = result.union(self.chargePitchTypeEvents())
            elif pitch.lower() == 'slider':
                result = result.union(self.sliderPitchTypeEvents())
            elif pitch.lower() == 'perfect':
                result = result.union(self.perfectChargePitchTypeEvents())
            elif pitch.lower() == 'changeup':
                result = result.union(self.changeUpPitchTypeEvents())
            else:
                raise ValueError(f'{pitch} is not a valid pitch type. Curve, Charge, Slider, Perfect, and ChangeUp are accepted.')

        return result

    def inStrikezoneEvents(self) -> set[int]:
        return self._pitch_in_strikezone_dict[1]

    def noneSwingTypeEvents(self) -> set[int]:
        return self._swing_bucket('None')

    def slapSwingTypeEvents(self) -> set[int]:
        return self._swing_bucket('Slap')

    def chargeSwingTypeEvents(self) -> set[int]:
        return self._swing_bucket('Charge')

    def starSwingTypeEvents(self) -> set[int]:
        return self._swing_bucket('Star')

    def buntSwingTypeEvents(self) -> set[int]:
        return self._swing_bucket('Bunt')

    def swingTypeEvents(self, swingType) -> set[int]:
        swingTypeList = swingType if isinstance(swingType, (list, set)) else [swingType]

        result = set()
        for swing in swingTypeList:
            if swing.lower() == 'none':
                result = result.union(self.noneSwingTypeEvents())
            elif swing.lower() == 'slap':
                result = result.union(self.slapSwingTypeEvents())
            elif swing.lower() == 'charge':
                result = result.union(self.chargeSwingTypeEvents())
            elif swing.lower() == 'star':
                result = result.union(self.starSwingTypeEvents())
            elif swing.lower() == 'bunt':
                result = result.union(self.buntSwingTypeEvents())
            else:
                raise ValueError(f'{swing} is not a valid swing type. None, Slap, Charge, Star, and Bunt are accepted.')

        return result

    def niceContactTypeEvents(self, side='b') -> set[int]:
        if side == 'b':
            return self._contact_bucket('Nice - Left') | self._contact_bucket('Nice - Right')
        if side == 'l':
            return self._contact_bucket('Nice - Left')
        if side == 'r':
            return self._contact_bucket('Nice - Right')
        raise ValueError(f"Invalid side '{side}'. Must be 'b', 'l', or 'r'.")

    def perfectContactTypeEvents(self) -> set[int]:
         return self._contact_bucket('Perfect')

    def sourContactTypeEvents(self, side='b') -> set[int]:
        if side == 'b':
            return self._contact_bucket('Sour - Left') | self._contact_bucket('Sour - Right')
        if side == 'l':
            return self._contact_bucket('Sour - Left')
        if side == 'r':
            return self._contact_bucket('Sour - Right')
        raise ValueError(f"Invalid side '{side}'. Must be 'b', 'l', or 'r'.")

    def contactTypeEvents(self, contactType) -> set[int]:
        contactTypeList = contactType if isinstance(contactType, (list, set)) else [contactType]

        result = set()
        for contact in contactTypeList:
            if contact.lower() == 'sour':
                result = result.union(self.sourContactTypeEvents())
            elif contact.lower() == 'nice':
                result = result.union(self.niceContactTypeEvents())
            elif contact.lower() == 'perfect':
                result = result.union(self.perfectContactTypeEvents())
            else:
                raise ValueError(f'{contact} is not a valid contact type. Sour, Nice, and Perfect are accepted.')

        return result

    def inputDirectionEvents(self, input_directions) -> set[int]:
        return self._input_direction_dict[input_directions]

    def contactFrameEvents(self, contactFrame) -> set[int]:
        # returns a set of contacts that occurered on the specified frame
        # negative inputs return all events with a strike count greater than or equal to the input
        # inputting a list or set will return the all events that match the numbers in the list
        contactFrameList = contactFrame if isinstance(contactFrame, (list, set)) else [contactFrame]
        return self.listInputHandling(contactFrameList, self._contact_frame_dict)

    def characterAtBatEvents(self, char_id) -> set[int]:
        # returns a set of events where the input character was at bat
        # returns an empty set if the character was not in the game
        # rather than raising an error
        character = Character.from_raw(char_id)
        if character not in self.character_action_dict:
            return set()
        return self.character_action_dict[character]['AtBat']

    def characterPitchingEvents(self, char_id) -> set[int]:
        # returns a set of events where the input character was pitching
        # returns an empty set if the character was not in the game
        # rather than raising an error
        character = Character.from_raw(char_id)
        if character not in self.character_action_dict:
            return set()
        return self.character_action_dict[character]['Pitching']

    def characterFieldingEvents(self, char_id) -> set[int]:
        # returns a set of events where the input character is the first fielder
        # returns an empty set if the character was not in the game
        # rather than raising an error
        character = Character.from_raw(char_id)
        if character not in self.character_action_dict:
            return set()
        return self.character_action_dict[character]['Fielding']

    def positionFieldingEvents(self, fielderPos) -> set[int]:
        # returns a set of events where the input fielding pos is the first fielder
        # raises an error when the imput fielding pos is not valid
        self.__errorCheck_fielder_pos(fielderPos)
        return self._first_fielder_position_dict[Position.from_raw(fielderPos)]

    def walkoffEvents(self) -> set[int]:
        final_event = EventObj(self.rioStat, self.rioStat.final_event())
        # returns a set of events of game walkoffs
        if final_event.rbi() != 0:
            return set([self.rioStat.final_event()])
        return set()

    def playerBattingEvents(self, playerBatting) -> set[int]:
        if playerBatting.lower() == self.rioStat.player(0).lower():
            return self.halfInningEvents(0)
        elif playerBatting.lower() == self.rioStat.player(1).lower():
            return self.halfInningEvents(1)
        else:
            return set()

    def playerPitchingEvents(self, playerPitching) -> set[int]:
        if playerPitching.lower() == self.rioStat.player(0).lower():
            return self.halfInningEvents(1)
        elif playerPitching.lower() == self.rioStat.player(1).lower():
            return self.halfInningEvents(0)
        else:
            return set()

    def ballPositionStrikezoneEvents(self, minimimum_ball_pos) -> set[int]:
        result = set()
        for key in self._ball_position_strikezone:
            if abs(key) >= abs(minimimum_ball_pos):
                result = result.union(set(self._ball_position_strikezone[key]))
        return result

    def ballContactPositionEvents(self, minimimum_ball_pos) -> set[int]:
        result = set()
        for key in self._x_ball_contact_pos:
            if abs(key) >= abs(minimimum_ball_pos):
                result = result.union(set(self._x_ball_contact_pos[key]))
        return result

    def firstPitchOfABEvents(self) -> set[int]:
        return self._first_pitch_of_AB

    def lastPitchOfABEvents(self) -> set[int]:
        return self._last_pitch_of_AB

    def leadChangedEvents(self) -> set[int]:
        return self._lead_changed

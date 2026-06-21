"""StatObj: read-only view over a decoded Project Rio stat file."""
from __future__ import annotations

from datetime import datetime
from typing import Optional, Union

from ..lookup import (
    LookupDicts, Lookup, Character, Stadium,
    PitchType, ChargeType, SwingType, ContactType,
    FinalResult, PrimaryContactResult, SecondaryContactResult,
    OutType, StealType, PitchResult,
    Hand, Position, FielderAction, FielderBobble, ManualSelect, TeamName,
)
from .error_checking import ErrorChecker


class StatObj:
    def __init__(self, statJson: dict):
        self.statJson = statJson

    def gameID(self) -> int:
        # returns it in int form
        return int(self.statJson["GameID"].replace(',', ''), 16)

    def game_mode(self) -> int:
        """Game mode id for this game (the stat file's raw TagSetID).

        Resolve to a human-readable mode/community name via CompleterCache.
        """
        return self.statJson["TagSetID"]

    def netplay(self) -> Optional[int]:
        """1 if the game was played over netplay, else 0 (None if absent)."""
        return self.statJson.get("Netplay")

    def loaded_from_hud(self) -> Optional[int]:
        """1 if the stat file was loaded from a HUD capture (None if absent)."""
        return self.statJson.get("Loaded from HUD")

    # should look to convert to unix or some other standard date fmt
    def startDate(self) -> datetime:
        return datetime.strptime(self.statJson["Date - Start"], "%a %b %d %H:%M:%S %Y")

    def endDate(self) -> datetime:
        return datetime.strptime(self.statJson["Date - End"], "%a %b %d %H:%M:%S %Y")

    def version(self) -> str:
        return self.statJson.get('Version', 'Pre 0.1.7')

    def stadium(self) -> Stadium:
        # returns the stadium that was played on
        return Lookup.stadium(self.statJson["StadiumID"])
    
    def teamNumVersionCorrection(self, teamNum: int) -> int:
        # For Project Rio versions pre 1.9.2
        # teamNum: 0 == home team, 1 == away team
        # For Project Rio versions 1.9.2 and later
        # teamNum: 0 == away team, 1 == home team

        ErrorChecker.check_team_num(teamNum)


        VERSION_LIST_HOME_AWAY_FLIPPED = ["Pre 0.1.7", "0.1.7a", "0.1.8", "0.1.9", "1.9.1"]

        if self.version() in VERSION_LIST_HOME_AWAY_FLIPPED:
            return abs(teamNum-1)
        
        return teamNum


    def player(self, teamNum: int) -> str:
        teamNum = self.teamNumVersionCorrection(teamNum)
        if teamNum == 0:
            return self.statJson["Away Player"]
        else:
            return self.statJson["Home Player"]


    def score(self, teamNum: int) -> int:
        teamNum = self.teamNumVersionCorrection(teamNum)

        if teamNum == 0:
            return self.statJson["Away Score"]
        else:
            return self.statJson["Home Score"]
        
    def winning_team(self) -> int:
        # returns the team number of the winning team
        if self.score(0) > self.score(1):
            return 0
        elif self.score(1) > self.score(0):
            return 1
        else:
            return -1  # tie game

    def inningsSelected(self) -> int:
        # returns how many innings were selected for the game
        return self.statJson["Innings Selected"]

    def inningsPlayed(self) -> int:
        # returns how many innings were played in the game
        return self.statJson["Innings Played"]

    def isMercy(self) -> bool:
        # returns if the game ended in a mercy or not
        return self.inningsSelected() - self.inningsPlayed() >= 1 and abs(self.score(0) - self.score(1)) > 10

    def wasQuit(self) -> bool:
        # returns if the game was quit out early
        return self.statJson["Quitter Team"] != ""

    def quitter(self) -> str:
        # returns the name of the quitter if the game was quit. empty string if no quitter
        return self.statJson["Quitter Team"]

    def ping(self) -> int:
        # returns average ping of the game
        return self.statJson["Average Ping"]

    def lagspikes(self) -> int:
        # returns number of lag spikes in a game
        return self.statJson["Lag Spikes"]

    def characterGameStats(self) -> dict:
        # returns the full dict of character game stats as shown in the stat file
        return self.statJson["Character Game Stats"]

    def isSuperstarGame(self) -> bool:
        # returns if the game has any superstar characters in it
        isStarred = False
        charStats = self.characterGameStats()
        for character in charStats:
            if charStats[character]["Superstar"] == 1:
                isStarred = True
        return isStarred

    def getTeamString(self, teamNum: int, rosterNum: int) -> str:
        ErrorChecker.check_team_num(teamNum)
        ErrorChecker.check_roster_num(rosterNum)

        VERSION_LIST_OLD_TEAM_STRUCTURE = ["Pre 0.1.7", "0.1.7a", "0.1.8", "0.1.9", "1.9.1", "1.9.2", "1.9.3", "1.9.4"]
        if self.version() in VERSION_LIST_OLD_TEAM_STRUCTURE:
            return f"Team {teamNum} Roster {rosterNum}"

        # Newer Version Format
        teamStr = "Away" if teamNum == 0 else "Home"
        return f"{teamStr} Roster {rosterNum}"
    
    def getRosterDict(self, teamNum: int) -> dict[int, str]:
        # returns a dict of rosterNum: characterName for the given team
        teamNum = self.teamNumVersionCorrection(teamNum)
        rosterDict = {}
        for x in range(0, 9):
            rosterDict[x] = self.statJson["Character Game Stats"][self.getTeamString(teamNum, x)]["CharID"]
        return rosterDict

    def character(self, teamNum: int, rosterNum: int = -1) -> Character | list[Character]:
        """Character(s) on a team as Character value objects.

        With no rosterNum, returns all 9 roster spots as a list. Each Character
        behaves like its char id under int()/== and its name under str().
        teamNum: 0 == home team, 1 == away team
        rosterNum: 0 -> 8 for each roster spot, or -1 (default) for the whole team
        """
        ErrorChecker.check_team_num(teamNum)
        ErrorChecker.check_roster_num(rosterNum)
        if rosterNum == -1:
            return [
                Lookup.character(self.statJson["Character Game Stats"][self.getTeamString(teamNum, x)]["CharID"])
                for x in range(0, 9)
            ]
        return Lookup.character(self.statJson["Character Game Stats"][self.getTeamString(teamNum, rosterNum)]["CharID"])

    def characterName(self, teamNum: int, rosterNum: int = -1) -> Character | list[Character]:
        """Deprecated alias for character(); returns Character value object(s)."""
        return self.character(teamNum, rosterNum)

    def isStarred(self, teamNum: int, rosterNum: int = -1) -> bool:
        # returns if a character is starred
        # if no arg, returns if any character on the team is starred
        # rosterNum: optional (no arg == all characters on team), 0 -> 8 for each of the 9 roster spots
        teamNum = self.teamNumVersionCorrection(teamNum)
        ErrorChecker.check_roster_num(rosterNum)
        if rosterNum == -1:
            for x in range(0, 9):
                if self.statJson["Character Game Stats"][self.getTeamString(teamNum, x)]["Superstar"] == 1:
                    return True
            return False
        else:
            return self.statJson["Character Game Stats"][self.getTeamString(teamNum, rosterNum)]["Superstar"] == 1

    def captain(self, teamNum: int) -> str:
        # returns name of character who is the captain
        teamNum = self.teamNumVersionCorrection(teamNum)
        captain = ""
        for character in self.characterGameStats():
            if character["Captain"] == 1 and int(character["Team"]) == teamNum:
                captain = character["CharID"]
        return captain

    def offensiveStats(self, teamNum: int, rosterNum: int = -1) -> Union[dict, list[dict]]:
        # grabs offensive stats of a character as seen in the stat json
        # if no roster provided, returns a list of all character's offensive stats
        # rosterNum: optional (no arg == all characters on team), 0 -> 8 for each of the 9 roster spots
        teamNum = self.teamNumVersionCorrection(teamNum)
        ErrorChecker.check_roster_num(rosterNum)
        if rosterNum == -1:
            oStatList = []
            for x in range(0, 9):
                oStatList.append(self.statJson["Character Game Stats"][self.getTeamString(teamNum, x)]["Offensive Stats"])
            return oStatList
        else:
            return self.statJson["Character Game Stats"][self.getTeamString(teamNum, rosterNum)]["Offensive Stats"]

    def defensiveStats(self, teamNum: int, rosterNum: int = -1) -> Union[dict, list[dict]]:
        # grabs defensive stats of a character as seen in the stat json
        # if no roster provided, returns a list of all character's defensive stats
        # rosterNum: optional (no arg == all characters on team), 0 -> 8 for each of the 9 roster spots
        teamNum = self.teamNumVersionCorrection(teamNum)
        ErrorChecker.check_roster_num(rosterNum)
        if rosterNum == -1:
            dStatList = []
            for x in range(0, 9):
                dStatList.append(self.statJson["Character Game Stats"][self.getTeamString(teamNum, x)]["Defensive Stats"])
            return dStatList
        else:
            return self.statJson["Character Game Stats"][self.getTeamString(teamNum, rosterNum)]["Defensive Stats"]

    def fieldingHand(self, teamNum: int, rosterNum: int) -> Hand:
        # returns fielding handedness of character
        # rosterNum: 0 -> 8 for each of the 9 roster spots
        teamNum = self.teamNumVersionCorrection(teamNum)
        ErrorChecker.check_roster_num_no_neg(rosterNum)
        return Lookup.hand(self.statJson["Character Game Stats"][self.getTeamString(teamNum, rosterNum)]["Fielding Hand"])

    def battingHand(self, teamNum: int, rosterNum: int) -> Hand:
        # returns batting handedness of character
        # rosterNum: 0 -> 8 for each of the 9 roster spots
        teamNum = self.teamNumVersionCorrection(teamNum)
        ErrorChecker.check_roster_num_no_neg(rosterNum)
        return Lookup.hand(self.statJson["Character Game Stats"][self.getTeamString(teamNum, rosterNum)]["Batting Hand"])

    # defensive stats
    def era(self, teamNum: int, rosterNum: int = -1) -> float:
        # tells the era of a character
        # if no character given, returns era of that team
        # rosterNum: optional (no arg == all characters on team), 0 -> 8 for each of the 9 roster spots
        teamNum = self.teamNumVersionCorrection(teamNum)
        return 9 * float(self.runsAllowed(teamNum, rosterNum)) / self.inningsPitched(teamNum, rosterNum)

    def battersFaced(self, teamNum: int, rosterNum: int = -1) -> int:
        # tells how many batters were faced by character
        # if no character given, returns batters faced by that team
        # rosterNum: optional (no arg == all characters on team), 0 -> 8 for each of the 9 roster spots
        teamNum = self.teamNumVersionCorrection(teamNum)
        if rosterNum == -1:
            total = 0
            for x in range(0, 9):
                total += self.defensiveStats(teamNum, x)["Batters Faced"]
            return total
        else:
            return self.defensiveStats(teamNum, rosterNum)["Batters Faced"]

    def runsAllowed(self, teamNum: int, rosterNum: int = -1) -> int:
        # tells how many runs a character allowed when pitching
        # if no character given, returns runs allowed by that team
        # rosterNum: optional (no arg == all characters on team), 0 -> 8 for each of the 9 roster spots
        teamNum = self.teamNumVersionCorrection(teamNum)
        if rosterNum == -1:
            total = 0
            for x in range(0, 9):
                total += self.defensiveStats(teamNum, x)["Runs Allowed"]
            return total
        else:
            return self.defensiveStats(teamNum, rosterNum)["Runs Allowed"]

    def battersWalked(self, teamNum: int, rosterNum: int = -1) -> int:
        # tells how many walks a character allowed when pitching
        # if no character given, returns walks by that team
        # rosterNum: optional (no arg == all characters on team), 0 -> 8 for each of the 9 roster spots
        teamNum = self.teamNumVersionCorrection(teamNum)
        return self.battersWalkedBallFour(teamNum, rosterNum) + self.battersHitByPitch(teamNum, rosterNum)

    def battersWalkedBallFour(self, teamNum: int, rosterNum: int = -1) -> int:
        # returns how many times a character has walked a batter via 4 balls
        # if no character given, returns how many times the team walked via 4 balls
        # rosterNum: optional (no arg == all characters on team), 0 -> 8 for each of the 9 roster spots
        teamNum = self.teamNumVersionCorrection(teamNum)
        if rosterNum == -1:
            total = 0
            for x in range(0, 9):
                total += self.defensiveStats(teamNum, x)["Batters Walked"]
            return total
        else:
            return self.defensiveStats(teamNum, rosterNum)["Batters Walked"]

    def battersHitByPitch(self, teamNum: int, rosterNum: int = -1) -> int:
        # returns how many times a character walked a batter by hitting them by a pitch
        # if no character given, returns walked via HBP for the team
        # rosterNum: optional (no arg == all characters on team), 0 -> 8 for each of the 9 roster spots
        teamNum = self.teamNumVersionCorrection(teamNum)
        if rosterNum == -1:
            total = 0
            for x in range(0, 9):
                total += self.defensiveStats(teamNum, x)["Batters Hit"]
            return total
        else:
            return self.defensiveStats(teamNum, rosterNum)["Batters Hit"]

    def hitsAllowed(self, teamNum: int, rosterNum: int = -1) -> int:
        # returns how many hits a character allowed as pitcher
        # if no character given, returns how many hits a team allowed
        # rosterNum: optional (no arg == all characters on team), 0 -> 8 for each of the 9 roster spots
        teamNum = self.teamNumVersionCorrection(teamNum)
        if rosterNum == -1:
            total = 0
            for x in range(0, 9):
                total += self.defensiveStats(teamNum, x)["Hits Allowed"]
            return total
        else:
            return self.defensiveStats(teamNum, rosterNum)["Hits Allowed"]

    def homerunsAllowed(self, teamNum: int, rosterNum: int = -1) -> int:
        # returns how many homeruns a character allowed as pitcher
        # if no character given, returns how many homeruns a team allowed
        # rosterNum: optional (no arg == all characters on team), 0 -> 8 for each of the 9 roster spots
        teamNum = self.teamNumVersionCorrection(teamNum)
        if rosterNum == -1:
            total = 0
            for x in range(0, 9):
                total += self.defensiveStats(teamNum, x)["HRs Allowed"]
            return total
        else:
            return self.defensiveStats(teamNum, rosterNum)["HRs Allowed"]

    def pitchesThrown(self, teamNum: int, rosterNum: int = -1) -> int:
        # returns how many pitches a character threw
        # if no character given, returns how many pitches a team threw
        # rosterNum: optional (no arg == all characters on team), 0 -> 8 for each of the 9 roster spots
        teamNum = self.teamNumVersionCorrection(teamNum)
        if rosterNum == -1:
            total = 0
            for x in range(0, 9):
                total += self.defensiveStats(teamNum, x)["Pitches Thrown"]
            return total
        else:
            return self.defensiveStats(teamNum, rosterNum)["Pitches Thrown"]

    def stamina(self, teamNum: int, rosterNum: int = -1) -> int:
        # returns final pitching stamina of a pitcher
        # if no character given, returns total stamina of a team
        # rosterNum: optional (no arg == all characters on team), 0 -> 8 for each of the 9 roster spots
        teamNum = self.teamNumVersionCorrection(teamNum)
        if rosterNum == -1:
            total = 0
            for x in range(0, 9):
                total += self.defensiveStats(teamNum, x)["Stamina"]
            return total
        else:
            return self.defensiveStats(teamNum, rosterNum)["Stamina"]
        
    def wasPitcher(self, teamNum: int, rosterNum: int) -> bool:
        # returns if a character was a pitcher
        # rosterNum: 0 -> 8 for each of the 9 roster spots
        teamNum = self.teamNumVersionCorrection(teamNum)
        ErrorChecker.check_roster_num_no_neg(rosterNum)
        return self.defensiveStats(teamNum, rosterNum)["Was Pitcher"] == 1

    def strikeoutsPitched(self, teamNum: int, rosterNum: int = -1) -> int:
        # returns how many strikeouts a character pitched
        # if no character given, returns how mnany strikeouts a team pitched
        # rosterNum: optional (no arg == all characters on team), 0 -> 8 for each of the 9 roster spots
        teamNum = self.teamNumVersionCorrection(teamNum)
        if rosterNum == -1:
            total = 0
            for x in range(0, 9):
                total += self.defensiveStats(teamNum, x)["Strikeouts"]
            return total
        else:
            return self.defensiveStats(teamNum, rosterNum)["Strikeouts"]

    def starPitchesThrown(self, teamNum: int, rosterNum: int = -1) -> int:
        # returns how many star pitches a character threw
        # if no character given, returns how many star pitches a team threw
        # rosterNum: optional (no arg == all characters on team), 0 -> 8 for each of the 9 roster spots
        teamNum = self.teamNumVersionCorrection(teamNum)
        if rosterNum == -1:
            total = 0
            for x in range(0, 9):
                total += self.defensiveStats(teamNum, x)["Star Pitches Thrown"]
            return total
        else:
            return self.defensiveStats(teamNum, rosterNum)["Star Pitches Thrown"]

    def bigPlays(self, teamNum: int, rosterNum: int = -1) -> int:
        # returns how many big plays a character had
        # if no character given, returns how many big plays a team had
        # rosterNum: optional (no arg == all characters on team), 0 -> 8 for each of the 9 roster spots
        teamNum = self.teamNumVersionCorrection(teamNum)
        if rosterNum == -1:
            total = 0
            for x in range(0, 9):
                total += self.defensiveStats(teamNum, x)["Big Plays"]
            return total
        else:
            return self.defensiveStats(teamNum, rosterNum)["Big Plays"]

    def outsPitched(self, teamNum: int, rosterNum: int = -1) -> int:
        # returns how many outs a character was pitching for
        # if no character given, returns how many outs a team pitched for
        # rosterNum: optional (no arg == all characters on team), 0 -> 8 for each of the 9 roster spots
        teamNum = self.teamNumVersionCorrection(teamNum)
        if rosterNum == -1:
            total = 0
            for x in range(0, 9):
                total += self.defensiveStats(teamNum, x)["Outs Pitched"]
            return total
        else:
            return self.defensiveStats(teamNum, rosterNum)["Outs Pitched"]

    def inningsPitched(self, teamNum: int, rosterNum: int = -1) -> float:
        # returns how many innings a character was pitching for
        # if no character given, returns how many innings a team pitched for
        # rosterNum: optional (no arg == all characters on team), 0 -> 8 for each of the 9 roster spots
        teamNum = self.teamNumVersionCorrection(teamNum)
        return float(self.outsPitched(teamNum, rosterNum)) / 3

    def pitchesPerPosition(self, teamNum: int, rosterNum: int) -> dict:
        # returns a dict which tracks how many pitches a character was at a position for
        # rosterNum: 0 -> 8 for each of the 9 roster spots
        teamNum = self.teamNumVersionCorrection(teamNum)
        ErrorChecker.check_roster_num_no_neg(rosterNum)
        return self.defensiveStats(teamNum, rosterNum)["Pitches Per Position"][0]

    def outsPerPosition(self, teamNum: int, rosterNum: int) -> dict:
        # returns a dict which tracks how many outs a character was at a position for
        # rosterNum: 0 -> 8 for each of the 9 roster spots
        teamNum = self.teamNumVersionCorrection(teamNum)
        ErrorChecker.check_roster_num_no_neg(rosterNum)
        return self.defensiveStats(teamNum, rosterNum)["Outs Per Position"][0]

    # offensive stats

    def atBats(self, teamNum: int, rosterNum: int = -1) -> int:
        # returns how many at bats a character had
        # if no character given, returns how many at bats a team had
        # rosterNum: optional (no arg == all characters on team), 0 -> 8 for each of the 9 roster spots
        teamNum = self.teamNumVersionCorrection(teamNum)
        if rosterNum == -1:
            total = 0
            for x in range(0, 9):
                total += self.offensiveStats(teamNum, x)["At Bats"]
            return total
        else:
            return self.offensiveStats(teamNum, rosterNum)["At Bats"]

    def hits(self, teamNum: int, rosterNum: int = -1) -> int:
        # returns how many hits a character had
        # if no character given, returns how many hits a team had
        # rosterNum: optional (no arg == all characters on team), 0 -> 8 for each of the 9 roster spots
        teamNum = self.teamNumVersionCorrection(teamNum)
        if rosterNum == -1:
            total = 0
            for x in range(0, 9):
                total += self.offensiveStats(teamNum, x)["Hits"]
            return total
        else:
            return self.offensiveStats(teamNum, rosterNum)["Hits"]

    def singles(self, teamNum: int, rosterNum: int = -1) -> int:
        # returns how many singles a character had
        # if no character given, returns how many singles a team had
        # rosterNum: optional (no arg == all characters on team), 0 -> 8 for each of the 9 roster spots
        teamNum = self.teamNumVersionCorrection(teamNum)
        if rosterNum == -1:
            total = 0
            for x in range(0, 9):
                total += self.offensiveStats(teamNum, x)["Singles"]
            return total
        else:
            return self.offensiveStats(teamNum, rosterNum)["Singles"]

    def doubles(self, teamNum: int, rosterNum: int = -1) -> int:
        # returns how many doubles a character had
        # if no character given, returns how many doubles a team had
        # rosterNum: optional (no arg == all characters on team), 0 -> 8 for each of the 9 roster spots
        teamNum = self.teamNumVersionCorrection(teamNum)
        if rosterNum == -1:
            total = 0
            for x in range(0, 9):
                total += self.offensiveStats(teamNum, x)["Doubles"]
            return total
        else:
            return self.offensiveStats(teamNum, rosterNum)["Doubles"]

    def triples(self, teamNum: int, rosterNum: int = -1) -> int:
        # returns how many triples a character had
        # if no character given, returns how many triples a teams had
        # rosterNum: optional (no arg == all characters on team), 0 -> 8 for each of the 9 roster spots
        teamNum = self.teamNumVersionCorrection(teamNum)
        if rosterNum == -1:
            total = 0
            for x in range(0, 9):
                total += self.offensiveStats(teamNum, x)["Triples"]
            return total
        else:
            return self.offensiveStats(teamNum, rosterNum)["Triples"]

    def homeruns(self, teamNum: int, rosterNum: int = -1) -> int:
        # returns how many homeruns a character had
        # if no character given, returns how many homeruns a team had
        # rosterNum: optional (no arg == all characters on team), 0 -> 8 for each of the 9 roster spots
        teamNum = self.teamNumVersionCorrection(teamNum)
        if rosterNum == -1:
            total = 0
            for x in range(0, 9):
                total += self.offensiveStats(teamNum, x)["Homeruns"]
            return total
        else:
            return self.offensiveStats(teamNum, rosterNum)["Homeruns"]

    def buntsLanded(self, teamNum: int, rosterNum: int = -1) -> int:
        # returns how many successful bunts a character had
        # if no character given, returns how many successful bunts a team had
        # rosterNum: optional (no arg == all characters on team), 0 -> 8 for each of the 9 roster spots
        teamNum = self.teamNumVersionCorrection(teamNum)
        if rosterNum == -1:
            total = 0
            for x in range(0, 9):
                total += self.offensiveStats(teamNum, x)["Successful Bunts"]
            return total
        else:
            return self.offensiveStats(teamNum, rosterNum)["Successful Bunts"]

    def sacFlys(self, teamNum: int, rosterNum: int = -1) -> int:
        # returns how many sac flys a character had
        # if no character given, returns how many sac flys a team had
        # rosterNum: optional (no arg == all characters on team), 0 -> 8 for each of the 9 roster spots
        teamNum = self.teamNumVersionCorrection(teamNum)
        if rosterNum == -1:
            total = 0
            for x in range(0, 9):
                total += self.offensiveStats(teamNum, x)["Sac Flys"]
            return total
        else:
            return self.offensiveStats(teamNum, rosterNum)["Sac Flys"]

    def strikeouts(self, teamNum: int, rosterNum: int = -1) -> int:
        # returns how many times a character struck out when batting
        # if no character given, returns how many times a team struck out when batting
        # rosterNum: optional (no arg == all characters on team), 0 -> 8 for each of the 9 roster spots
        teamNum = self.teamNumVersionCorrection(teamNum)
        if rosterNum == -1:
            total = 0
            for x in range(0, 9):
                total += self.offensiveStats(teamNum, x)["Strikeouts"]
            return total
        else:
            return self.offensiveStats(teamNum, rosterNum)["Strikeouts"]

    def walks(self, teamNum: int, rosterNum: int) -> int:
        # returns how many times a character was walked when batting
        # if no character given, returns how many times a team was walked when batting
        # rosterNum: optional (no arg == all characters on team), 0 -> 8 for each of the 9 roster spots
        teamNum = self.teamNumVersionCorrection(teamNum)
        return self.walksBallFour(teamNum, rosterNum) + self.walksHitByPitch(teamNum, rosterNum)

    def walksBallFour(self, teamNum: int, rosterNum: int = -1) -> int:
        # returns how many times a character was walked via 4 balls when batting
        # if no character given, returns how many times a team was walked via 4 balls when batting
        # rosterNum: optional (no arg == all characters on team), 0 -> 8 for each of the 9 roster spots
        teamNum = self.teamNumVersionCorrection(teamNum)
        if rosterNum == -1:
            total = 0
            for x in range(0, 9):
                total += self.offensiveStats(teamNum, x)["Walks (4 Balls)"]
            return total
        else:
            return self.offensiveStats(teamNum, rosterNum)["Walks (4 Balls)"]

    def walksHitByPitch(self, teamNum: int, rosterNum: int = -1) -> int:
        # returns how many times a character was walked via hit by pitch when batting
        # if no character given, returns how many times a team was walked via hit by pitch when batting
        # rosterNum: optional (no arg == all characters on team), 0 -> 8 for each of the 9 roster spots
        teamNum = self.teamNumVersionCorrection(teamNum)
        if rosterNum == -1:
            total = 0
            for x in range(0, 9):
                total += self.offensiveStats(teamNum, x)["Walks (Hit)"]
            return total
        else:
            return self.offensiveStats(teamNum, rosterNum)["Walks (Hit)"]

    def rbi(self, teamNum: int, rosterNum: int = -1) -> int:
        # returns how many RBI's a character had
        # if no character given, returns how many RBI's a team had
        # rosterNum: optional (no arg == all characters on team), 0 -> 8 for each of the 9 roster spots
        teamNum = self.teamNumVersionCorrection(teamNum)
        if rosterNum == -1:
            total = 0
            for x in range(0, 9):
                total += self.offensiveStats(teamNum, x)["RBI"]
            return total
        else:
            return self.offensiveStats(teamNum, rosterNum)["RBI"]

    def basesStolen(self, teamNum: int, rosterNum: int = -1) -> int:
        # returns how many times a character successfully stole a base
        # if no character given, returns how many times a team successfully stole a base
        # rosterNum: optional (no arg == all characters on team), 0 -> 8 for each of the 9 roster spots
        teamNum = self.teamNumVersionCorrection(teamNum)
        if rosterNum == -1:
            total = 0
            for x in range(0, 9):
                total += self.offensiveStats(teamNum, x)["Bases Stolen"]
            return total
        else:
            return self.offensiveStats(teamNum, rosterNum)["Bases Stolen"]

    def starHitsUsed(self, teamNum: int, rosterNum: int = -1) -> int:
        # returns how many star hits a character used
        # if no character given, returns how many star hits a team used
        # rosterNum: optional (no arg == all characters on team), 0 -> 8 for each of the 9 roster spots
        teamNum = self.teamNumVersionCorrection(teamNum)
        if rosterNum == -1:
            total = 0
            for x in range(0, 9):
                total += self.offensiveStats(teamNum, x)["Star Hits"]
            return total
        else:
            return self.offensiveStats(teamNum, rosterNum)["Star Hits"]

    # complicated stats

    def battingAvg(self, teamNum: int, rosterNum: int = -1) -> float:
        # returns the batting average of a character
        # if no character given, returns the batting average of a team
        # rosterNum: optional (no arg == all characters on team), 0 -> 8 for each of the 9 roster spots
        teamNum = self.teamNumVersionCorrection(teamNum)
        nAtBats = self.atBats(teamNum, rosterNum)
        nHits = self.hits(teamNum, rosterNum)
        return float(nHits) / float(nAtBats)

    def obp(self, teamNum: int, rosterNum: int = -1) -> float:
        # returns the on base percentage of a character
        # if no character given, returns the on base percentage of a team
        # rosterNum: optional (no arg == all characters on team), 0 -> 8 for each of the 9 roster spots
        teamNum = self.teamNumVersionCorrection(teamNum)
        nAtBats = self.atBats(teamNum, rosterNum)
        nHits = self.hits(teamNum, rosterNum)
        nWalks = self.walks(teamNum, rosterNum)
        return float(nHits + nWalks) / float(nAtBats)

    def slg(self, teamNum: int, rosterNum: int = -1) -> float:
        # returns the SLG of a character
        # if no character given, returns the SLG of a team
        # rosterNum: optional (no arg == all characters on team), 0 -> 8 for each of the 9 roster spots
        teamNum = self.teamNumVersionCorrection(teamNum)
        nAtBats = self.atBats(teamNum, rosterNum)
        nSingles = self.singles(teamNum, rosterNum)
        nDoubles = self.doubles(teamNum, rosterNum)
        nTriples = self.triples(teamNum, rosterNum)
        nHomeruns = self.homeruns(teamNum, rosterNum)
        nWalks = self.walks(teamNum, rosterNum)
        return float(nSingles + nDoubles * 2 + nTriples * 3 + nHomeruns * 4) / float(nAtBats - nWalks)

    def ops(self, teamNum: int, rosterNum: int = -1) -> float:
        # returns the OPS of a character
        # if no character given, returns the OPS of a team
        # rosterNum: optional (no arg == all characters on team), 0 -> 8 for each of the 9 roster spots
        teamNum = self.teamNumVersionCorrection(teamNum)
        return self.obp(teamNum, rosterNum) + self.slg(teamNum, rosterNum)
    
    def events(self) -> list[dict]:
        return self.statJson['Events']

    def final_event(self) -> int:
        return len(self.events())-1

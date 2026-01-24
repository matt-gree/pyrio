from .lookup import LookupDicts
from datetime import datetime

'''
Intended to parse "decoded" files which would be present on a user's computer

How to use:
- import RioStatLib obviously
- open a Rio stat json file
- convert from json string to obj using json.loads(jsonStr)
- create StatObj with your stat json obj using the following:
	myStats = RioStatLib.StatObj(jsonObj)
- call any of the built-in methods to get some stats

- ex:
	import RioStatLib
	import json
	with open("path/to/RioStatFile.json", "r") as jsonStr:
		jsonObj = json.loads(jsonStr)
		myStats = RioStatLib.StatObj(jsonObj)
		homeTeamOPS = myStats.ops(0)
		awayTeamSLG = myStats.slg(1)
		booERA = myStats.era(0, 4) # Boo in this example is the 4th character on the home team

Team args:
- arg == 0 means team0 which is the away team (home team for Project Rio pre 1.9.2)
- arg == 1 means team1 which is the home team (away team for Project Rio 1.9.2 and later)
- arg == -1 or no arg provided means both teams (if function allows) (none currently accept this, but it might be added in the future)

Roster args:
- arg == 0 -> 8 for each of the 9 roster spots
- arg == -1 or no arg provided means all characters on that team (if function allows)

# For Project Rio versions pre 1.9.2
# teamNum: 0 == home team, 1 == away team
# For Project Rio versions 1.9.2 and later
# teamNum: 0 == away team, 1 == away home
# rosterNum: optional (no arg == all characters on team), 0 -> 8 for each of the 9 roster spots
'''

class ErrorChecker:
    @staticmethod
    def check_team_num(teamNum: int):
        """Checks if the team number is valid (either 0 or 1)."""
        if teamNum != 0 and teamNum != 1:
            raise Exception(
                f'Invalid team arg {teamNum}. Function only accepts team args of 0 (home team) or 1 (away team).')

    @staticmethod
    def check_roster_num(rosterNum: int):
        """Checks if the roster number is valid (between -1 and 8). Allows -1."""
        if rosterNum < -1 or rosterNum > 8:
            raise Exception(f'Invalid roster arg {rosterNum}. Function only accepts roster args of 0 to 8.')

    @staticmethod
    def check_roster_num_no_neg(rosterNum: int):
        """Checks if the roster number is valid (between 0 and 8). Does not allow -1."""
        if rosterNum < 0 or rosterNum > 8:
            raise Exception(f'Invalid roster arg {rosterNum}. Function only accepts roster args of 0 to 8.')

    @staticmethod
    def check_base_num(baseNum: int):
        """Checks if the base number is valid (between 1 and 3) or -1."""
        if (baseNum < -1 or baseNum > 3):
            raise Exception(f'Invalid base arg {baseNum}. Function only accepts base args of -1 to 3')

# create stat obj
class StatObj:
    def __init__(self, statJson: dict):
        self.statJson = statJson

    def gameID(self):
        # returns it in int form
        return int(self.statJson["GameID"].replace(',', ''), 16)

    # should look to convert to unix or some other standard date fmt
    def startDate(self):
        return datetime.strptime(self.statJson["Date - Start"], "%a %b %d %H:%M:%S %Y")
    
    def endDate(self):
        return datetime.strptime(self.statJson["Date - End"], "%a %b %d %H:%M:%S %Y")

    def version(self):
        return self.statJson.get('Version', 'Pre 0.1.7')

    def stadium(self):
        # returns the stadium that was played on
        old_stadium_names = {
            "Bowser's Castle": "Bowser Castle",
            "Wario's Palace": "Wario Palace",
            "Yoshi's Island": "Yoshi Park",
            "Peach's Garden": "Peach Garden",
            "DK's Jungle":  "DK Jungle"
        }
        
        return old_stadium_names.get(self.statJson["StadiumID"], self.statJson["StadiumID"])
    
    def teamNumVersionCorrection(self, teamNum: int):
        # For Project Rio versions pre 1.9.2
        # teamNum: 0 == home team, 1 == away team
        # For Project Rio versions 1.9.2 and later
        # teamNum: 0 == away team, 1 == home team

        ErrorChecker.check_team_num(teamNum)


        VERSION_LIST_HOME_AWAY_FLIPPED = ["Pre 0.1.7", "0.1.7a", "0.1.8", "0.1.9", "1.9.1"]

        if self.version() in VERSION_LIST_HOME_AWAY_FLIPPED:
            return abs(teamNum-1)
        
        return teamNum


    def player(self, teamNum: int):
        teamNum = self.teamNumVersionCorrection(teamNum)
        if teamNum == 0:
            return self.statJson["Away Player"]
        else:
            return self.statJson["Home Player"]


    def score(self, teamNum: int):
        teamNum = self.teamNumVersionCorrection(teamNum)

        if teamNum == 0:
            return self.statJson["Away Score"]
        elif teamNum == 1:
            return self.statJson["Home Score"]
        
    def winning_team(self):
        # returns the team number of the winning team
        if self.score(0) > self.score(1):
            return 0
        elif self.score(1) > self.score(0):
            return 1
        else:
            return -1  # tie game

    def inningsSelected(self):
        # returns how many innings were selected for the game
        return self.statJson["Innings Selected"]

    def inningsPlayed(self):
        # returns how many innings were played in the game
        return self.statJson["Innings Played"]

    def isMercy(self):
        # returns if the game ended in a mercy or not
        if self.inningsSelected() - self.inningsPlayed() >= 1 and abs(self.score(0) - self.score(1)) > 10:
            return True
        else:
            return False

    def wasQuit(self):
        # returns if the same was quit out early
        if self.statJson["Quitter Team"] == "":
            return False
        else:
            return True

    def quitter(self):
        # returns the name of the quitter if the game was quit. empty string if no quitter
        return self.statJson["Quitter Team"]

    def ping(self):
        # returns average ping of the game
        return self.statJson["Average Ping"]

    def lagspikes(self):
        # returns number of lag spikes in a game
        return self.statJson["Lag Spikes"]

    def characterGameStats(self):
        # returns the full dict of character game stats as shown in the stat file
        return self.statJson["Character Game Stats"]

    def isSuperstarGame(self):
        # returns if the game has any superstar characters in it
        isStarred = False
        charStats = self.characterGameStats()
        for character in charStats:
            if charStats[character]["Superstar"] == 1:
                isStarred = True
        return isStarred

    def getTeamString(self, teamNum: int, rosterNum: int):
        ErrorChecker.check_team_num(teamNum)
        ErrorChecker.check_roster_num(rosterNum)

        VERSION_LIST_OLD_TEAM_STRUCTURE = ["Pre 0.1.7", "0.1.7a", "0.1.8", "0.1.9", "1.9.1", "1.9.2", "1.9.3", "1.9.4"]
        if self.version() in VERSION_LIST_OLD_TEAM_STRUCTURE:
            return f"Team {teamNum} Roster {rosterNum}"

        # Newer Version Format
        teamStr = "Away" if teamNum == 0 else "Home"
        return f"{teamStr} Roster {rosterNum}"
    
    def getRosterDict(self, teamNum: int):
        # returns a dict of rosterNum: characterName for the given team
        teamNum = self.teamNumVersionCorrection(teamNum)
        rosterDict = {}
        for x in range(0, 9):
            rosterDict[x] = self.statJson["Character Game Stats"][self.getTeamString(teamNum, x)]["CharID"]
        return rosterDict

    def characterName(self, teamNum: int, rosterNum: int = -1):
        # returns name of specified character
        # if no roster spot is provided, returns a list of characters on a given team
        # teamNum: 0 == home team, 1 == away team
        # rosterNum: optional (no arg == all characters on team), 0 -> 8 for each of the 9 roster spots
        ErrorChecker.check_team_num(teamNum)
        ErrorChecker.check_roster_num(rosterNum)
        if rosterNum == -1:
            charList = []
            for x in range(0, 9):
                charList.append(self.statJson["Character Game Stats"][self.getTeamString(teamNum, x)]["CharID"])
            return charList
        else:
            return self.statJson["Character Game Stats"][self.getTeamString(teamNum, rosterNum)]["CharID"]

    def isStarred(self, teamNum: int, rosterNum: int = -1):
        # returns if a character is starred
        # if no arg, returns if any character on the team is starred
        # rosterNum: optional (no arg == all characters on team), 0 -> 8 for each of the 9 roster spots
        teamNum = self.teamNumVersionCorrection(teamNum)
        ErrorChecker.check_roster_num(rosterNum)
        if rosterNum == -1:
            for x in range(0, 9):
                if self.statJson["Character Game Stats"][self.getTeamString(teamNum, x)]["Superstar"] == 1:
                    return True
        else:
            if self.statJson["Character Game Stats"][self.getTeamString(teamNum, rosterNum)]["Superstar"] == 1:
                return True
            else:
                return False

    def captain(self, teamNum: int):
        # returns name of character who is the captain
        teamNum = self.teamNumVersionCorrection(teamNum)
        captain = ""
        for character in self.characterGameStats():
            if character["Captain"] == 1 and int(character["Team"]) == teamNum:
                captain = character["CharID"]
        return captain

    def offensiveStats(self, teamNum: int, rosterNum: int = -1):
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

    def defensiveStats(self, teamNum: int, rosterNum: int = -1):
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

    def fieldingHand(self, teamNum: int, rosterNum: int):
        # returns fielding handedness of character
        # rosterNum: 0 -> 8 for each of the 9 roster spots
        teamNum = self.teamNumVersionCorrection(teamNum)
        ErrorChecker.check_roster_num_no_neg(rosterNum)
        return self.statJson["Character Game Stats"][self.getTeamString(teamNum, rosterNum)]["Fielding Hand"]

    def battingHand(self, teamNum: int, rosterNum: int):
        # returns batting handedness of character
        # rosterNum: 0 -> 8 for each of the 9 roster spots
        teamNum = self.teamNumVersionCorrection(teamNum)
        ErrorChecker.check_roster_num_no_neg(rosterNum)
        return self.statJson["Character Game Stats"][self.getTeamString(teamNum, rosterNum)]["Batting Hand"]

    # defensive stats
    def era(self, teamNum: int, rosterNum: int = -1):
        # tells the era of a character
        # if no character given, returns era of that team
        # rosterNum: optional (no arg == all characters on team), 0 -> 8 for each of the 9 roster spots
        teamNum = self.teamNumVersionCorrection(teamNum)
        return 9 * float(self.runsAllowed(teamNum, rosterNum)) / self.inningsPitched(teamNum, rosterNum)

    def battersFaced(self, teamNum: int, rosterNum: int = -1):
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

    def runsAllowed(self, teamNum: int, rosterNum: int = -1):
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

    def battersWalked(self, teamNum: int, rosterNum: int = -1):
        # tells how many walks a character allowed when pitching
        # if no character given, returns walks by that team
        # rosterNum: optional (no arg == all characters on team), 0 -> 8 for each of the 9 roster spots
        teamNum = self.teamNumVersionCorrection(teamNum)
        return self.battersWalkedBallFour(teamNum, rosterNum) + self.battersHitByPitch(teamNum, rosterNum)

    def battersWalkedBallFour(self, teamNum: int, rosterNum: int = -1):
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

    def battersHitByPitch(self, teamNum: int, rosterNum: int = -1):
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

    def hitsAllowed(self, teamNum: int, rosterNum: int = -1):
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

    def homerunsAllowed(self, teamNum: int, rosterNum: int = -1):
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

    def pitchesThrown(self, teamNum: int, rosterNum: int = -1):
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

    def stamina(self, teamNum: int, rosterNum: int = -1):
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
        
    def wasPitcher(self, teamNum: int, rosterNum: int):
        # returns if a character was a pitcher
        # rosterNum: 0 -> 8 for each of the 9 roster spots
        teamNum = self.teamNumVersionCorrection(teamNum)
        ErrorChecker.check_roster_num_no_neg(rosterNum)
        if self.defensiveStats(teamNum, rosterNum)["Was Pitcher"] == 1:
            return True
        else:
            return False

    def strikeoutsPitched(self, teamNum: int, rosterNum: int = -1):
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

    def starPitchesThrown(self, teamNum: int, rosterNum: int = -1):
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

    def bigPlays(self, teamNum: int, rosterNum: int = -1):
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

    def outsPitched(self, teamNum: int, rosterNum: int = -1):
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

    def inningsPitched(self, teamNum: int, rosterNum: int = -1):
        # returns how many innings a character was pitching for
        # if no character given, returns how many innings a team pitched for
        # rosterNum: optional (no arg == all characters on team), 0 -> 8 for each of the 9 roster spots
        teamNum = self.teamNumVersionCorrection(teamNum)
        return float(self.outsPitched(teamNum, rosterNum)) / 3

    def pitchesPerPosition(self, teamNum: int, rosterNum: int):
        # returns a dict which tracks how many pitches a character was at a position for
        # rosterNum: 0 -> 8 for each of the 9 roster spots
        teamNum = self.teamNumVersionCorrection(teamNum)
        ErrorChecker.check_roster_num_no_neg(rosterNum)
        return self.defensiveStats(teamNum, rosterNum)["Pitches Per Position"][0]

    def outsPerPosition(self, teamNum: int, rosterNum: int):
        # returns a dict which tracks how many outs a character was at a position for
        # rosterNum: 0 -> 8 for each of the 9 roster spots
        teamNum = self.teamNumVersionCorrection(teamNum)
        ErrorChecker.check_roster_num_no_neg(rosterNum)
        return self.defensiveStats(teamNum, rosterNum)["Outs Per Position"][0]

    # offensive stats

    def atBats(self, teamNum: int, rosterNum: int = -1):
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

    def hits(self, teamNum: int, rosterNum: int = -1):
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

    def singles(self, teamNum: int, rosterNum: int = -1):
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

    def doubles(self, teamNum: int, rosterNum: int = -1):
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

    def triples(self, teamNum: int, rosterNum: int = -1):
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

    def homeruns(self, teamNum: int, rosterNum: int = -1):
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

    def buntsLanded(self, teamNum: int, rosterNum: int = -1):
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

    def sacFlys(self, teamNum: int, rosterNum: int = -1):
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

    def strikeouts(self, teamNum: int, rosterNum: int = -1):
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

    def walks(self, teamNum: int, rosterNum: int):
        # returns how many times a character was walked when batting
        # if no character given, returns how many times a team was walked when batting
        # rosterNum: optional (no arg == all characters on team), 0 -> 8 for each of the 9 roster spots
        teamNum = self.teamNumVersionCorrection(teamNum)
        return self.walksBallFour(teamNum, rosterNum) + self.walksHitByPitch(teamNum, rosterNum)

    def walksBallFour(self, teamNum: int, rosterNum: int = -1):
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

    def walksHitByPitch(self, teamNum: int, rosterNum: int = -1):
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

    def rbi(self, teamNum: int, rosterNum: int = -1):
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

    def basesStolen(self, teamNum: int, rosterNum: int = -1):
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

    def starHitsUsed(self, teamNum: int, rosterNum: int = -1):
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

    def battingAvg(self, teamNum: int, rosterNum: int = -1):
        # returns the batting average of a character
        # if no character given, returns the batting average of a team
        # rosterNum: optional (no arg == all characters on team), 0 -> 8 for each of the 9 roster spots
        teamNum = self.teamNumVersionCorrection(teamNum)
        nAtBats = self.atBats(teamNum, rosterNum)
        nHits = self.hits(teamNum, rosterNum)
        return float(nHits) / float(nAtBats)

    def obp(self, teamNum: int, rosterNum: int = -1):
        # returns the on base percentage of a character
        # if no character given, returns the on base percentage of a team
        # rosterNum: optional (no arg == all characters on team), 0 -> 8 for each of the 9 roster spots
        teamNum = self.teamNumVersionCorrection(teamNum)
        nAtBats = self.atBats(teamNum, rosterNum)
        nHits = self.hits(teamNum, rosterNum)
        nWalks = self.walks(teamNum, rosterNum)
        return float(nHits + nWalks) / float(nAtBats)

    def slg(self, teamNum: int, rosterNum: int = -1):
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

    def ops(self, teamNum: int, rosterNum: int = -1):
        # returns the OPS of a character
        # if no character given, returns the OPS of a team
        # rosterNum: optional (no arg == all characters on team), 0 -> 8 for each of the 9 roster spots
        teamNum = self.teamNumVersionCorrection(teamNum)
        return self.obp(teamNum, rosterNum) + self.slg(teamNum, rosterNum)
    
    def events(self):
        return self.statJson['Events']

    def final_event(self):
        return len(self.events())-1
    

class EventSearch():
    def __init__(self, rioStat: StatObj):
        self.debug_mode = False

        self.rioStat: StatObj = rioStat

        self._result_of_AB_dict: dict[str, set[int]] = {value: set() for value in LookupDicts.FINAL_RESULT.values()}
        self._first_fielder_position_dict: dict[str, set[int]] = {value: set() for value in LookupDicts.POSITION.values()}
        self._pitch_type_dict: dict[str, set[int]] = {value: set() for value in LookupDicts.PITCH_TYPE.values()}
        self._charge_type_dict: dict[str, set[int]] = {value: set() for value in LookupDicts.CHARGE_TYPE.values()}
        self._swing_type_dict: dict[str, set[int]] = {value: set() for value in LookupDicts.TYPE_OF_SWING.values()}
        self._contact_type_dict: dict[str, set[int]] = {value: set() for value in LookupDicts.CONTACT_TYPE.values()}
        self._input_direction_dict: dict[str, set[int]] = {value: set() for value in LookupDicts.INPUT_DIRECTION.values()}

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

        self.character_action_dict: dict[str, dict[str, set[int]]] = {}
        for characterDict in self.rioStat.characterGameStats().values():
            self.character_action_dict[characterDict['CharID']] = {
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

            if currentEvent.result_of_AB() != 'None':
                self._last_pitch_of_AB.add(eventNum)
           
            try:
                self._pitch_type_dict[currentEvent.pitch_type()].add(eventNum)
            except:
                if self.debug_mode:
                    print(f'{self.rioStat.gameID()}, {eventNum}: Pitch Type: {currentEvent.pitch_type()}')

            try:
                self._charge_type_dict[currentEvent.charge_type()].add(eventNum)
            except:
                if self.debug_mode:
                    print(f'{self.rioStat.gameID()}, {eventNum}: Charge Type: {currentEvent.pitch_type()}')

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

            if currentEvent.first_fielder_bobble() != 'None':
                self._bobble.add(eventNum)

            if currentEvent.first_fielder_action() == 'Sliding':
                self._sliding_catch.add(eventNum)

            if currentEvent.first_fielder_action() == 'Walljump':
                self._wall_jump.add(eventNum)

            self._first_fielder_position_dict[currentEvent.first_fielder_position()].add(eventNum)

            if currentEvent.first_fielder_maunual_selected() != 'No Selected Char':
                self._manual_character_selection.add(eventNum)
    
    def __errorCheck_fielder_pos(self, fielderPos):
        # tells if fielderPos is valid
        if fielderPos.upper() not in LookupDicts.POSITION.values():
            raise Exception(f"Invalid fielder position {fielderPos}. Function accepts {LookupDicts.POSITION.values()}")

    def __errorCheck_baseNum(self, baseNum: int):
        # tells if baseNum is valid representing 1st, 2nd and 3rd base
        if abs(baseNum) not in [0,1,2,3]:
            raise Exception(f'Invalid base num {baseNum}. Function only accepts base numbers of -3 to 3.')

    def __errorCheck_halfInningNum(self, halfInningNum: int):
        if halfInningNum not in [0,1]:
            raise Exception(f'Invalid Half Inning num {halfInningNum}. Function only accepts base numbers of 0 or 1.')

    def noneResultEvents(self):
        # returns a set of events who's result is none
        return self._result_of_AB_dict['None']
    
    def strikeoutResultEvents(self):
        # returns a set of events where the result is a strikeout
        return self._result_of_AB_dict['Strikeout']
    
    def walkResultEvents(self, include_hbp=True, include_bb=True):
        # returns a set of events where the batter recorded a type of hit
        # can be used to reutrn just walks or just hbp
        # defaults to returning both
        if include_hbp & include_bb:
            return self._result_of_AB_dict['Walk (HBP)'] | self._result_of_AB_dict['Walk (BB)']
        if include_hbp:
            return self._result_of_AB_dict['Walk (HBP)']
        if include_bb:
            return self._result_of_AB_dict['Walk (BB)']
        else:
            return set()
        
    def outResultEvents(self):
        # returns a set of events where the result is out
        return self._result_of_AB_dict['Out']

    def caughtResultEvents(self):
        # returns a set of events where the result is caught
        return self._result_of_AB_dict['Caught']
    
    def caughtLineDriveResultsEvents(self):
        # returns a set of events where the result is caught line drive
        return self._result_of_AB_dict['Caught line-drive']

    def hitResultEvents(self, numberOfBases=0):
        # returns a set of events where the batter recorded a type of hit
        # can return singles, doubles, triples, HRs or all hits
        # returns all hits if numberOfBases is not 1-4
        if numberOfBases == 1:
            return self._result_of_AB_dict['Single']
        elif numberOfBases == 2:
            return self._result_of_AB_dict['Double']
        elif numberOfBases == 3:
            return self._result_of_AB_dict['Triple']
        elif numberOfBases == 4:
            return self._result_of_AB_dict['HR']
        else:
            return self._result_of_AB_dict['Single'] | self._result_of_AB_dict['Double'] | self._result_of_AB_dict['Triple'] | self._result_of_AB_dict['HR']

    def inputErrorResultEvents(self):
        # returns a set of events where the result is a input error
        return self._result_of_AB_dict['Error - Input']
    
    def chemErrorResultEvents(self):
        # returns a set of events where the result is a chem error
        return self._result_of_AB_dict['Error - Chem']

    def buntResultEvents(self):
        #returns a set of events of successful bunts
        return self._result_of_AB_dict['Bunt']
    
    def sacFlyResultEvents(self):
        #returns a set of events of sac flys
        return self._result_of_AB_dict['SacFly']
    
    def groundBallDoublePlayResultEvents(self):
        # returns a set of events where the result is a ground ball double play
        return self._result_of_AB_dict['Ground ball double Play']
    
    def foulCatchResultEvents(self):
        # returns a set of events where the result is a foul catch
        return self._result_of_AB_dict['Foul catch']
    
    def allOutResultEvents(self):
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

    def stealEvents(self):
        # returns a set of events where an steal happened
        # types of steals: None, Ready, Normal, Perfect
        return self._steal
    
    def starPitchEvents(self):
        # returns a set of events where a star pitch is used
        return self._star_pitch
    
    def bobbleEvents(self):
        # returns a set of events where any kind of bobble occurs
        # Bobble types: "None" "Slide/stun lock" "Fumble", "Bobble", 
        # "Fireball", "Garlic knockout" "None"
        return self._bobble
    
    def fiveStarDingerEvents(self):
        # returns a set of events where a five star dinger occurs
        return self._five_star_dinger
    
    def slidingCatchEvents(self):
        # returns a set of events where the fielder made a sliding catch
        # not to be confused with the character ability sliding catch
        return self._sliding_catch
    
    def wallJumpEvents(self):
        # returns a set of events where the fielder made a wall jump
        return self._wall_jump
    
    def firstFielderPositionEvents(self, location_abbreviation):
        # returns a set of events where the first fielder on the ball
        # is the one provided in the function argument
        if location_abbreviation not in self._first_fielder_position_dict.keys():
            raise Exception(f'Invalid roster arg {location_abbreviation}. Function only location abbreviations {self._first_fielder_position_dict.keys()}')
        return self._first_fielder_position_dict[location_abbreviation]
    
    def manualCharacterSelectionEvents(self):
        # returns a set of events where a fielder was manually selected
        return self._manual_character_selection
    
    def runnerOnBaseEvents(self, baseNums: list):
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
            raise Exception('Too many baseNums provided. runnerOnBaseEvents accepts at most 3 bases')

        if baseNums == [0]:
            return self._runners_on_base_dict['None']

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
            raise Exception(f'The argument 0 may only be provided alongside optional arguments or itself')

        if required_bases:
            print('required_bases')
            result = set(range(self.eventFinal()+1))
            for base in required_bases:
                result.intersection_update(runner_on_base[base])
        else:
            result = set()

        if not result:
            for base in optional_bases:
                result = result.union(runner_on_base[base])

        if exclude_bases:
            for base in exclude_bases:
                result.difference_update(runner_on_base[base])

        return result

    def listInputHandling(self, inputList, class_variable, to_zero=False):
        # Used with class variables that have integer keys
        result = set()
        for i in inputList:
            if abs(i) not in class_variable.keys():
                continue
            if i >= 0:
                result = result.union(class_variable[i])
            else:
                if to_zero:
                    for j in range(0, abs(i)):
                        result = result.union(class_variable[j])
                else:
                    for j in range(abs(i), max(class_variable.keys())+1):
                        result = result.union(class_variable[j])
                     
        return result

    def inningEvents(self, inningNum):
        inningNumList = inningNum if isinstance(inningNum, (list, set)) else [inningNum]
        # returns a set of events that occurered in the inning input
        # negative inputs return all events after the specified inning
        return self.listInputHandling(inningNumList, self._inning_dict)
    
    def awayTeamWinningEvents(self):
        return self._away_team_winning
    
    def homeTeamWinningEvents(self):
        return self._home_team_winning
    
    def gameTiedEvents(self):
        return self._game_tied
    
    def awayScoreEvents(self, awayScore):
        # returns a set of events that occurered with the away score
        # negative inputs return all events with an away score greater than or equal to the input
        # inputting a list or set will return the all events that match the numbers in the list
        awayScoreList = awayScore if isinstance(awayScore, (list, set)) else [awayScore]
        return self.listInputHandling(awayScoreList, self._home_score_dict)
    
    def homeScoreEvents(self, homeScore):
        # returns a set of events that occurered with the home score
        # negative inputs return all events with a home score greater than or equal to the input
        # inputting a list or set will return the all events that match the numbers in the list
        homeScoreList = homeScore if isinstance(homeScore, (list, set)) else [homeScore]
        return self.listInputHandling(homeScoreList, self._home_score_dict)
    
    def ballEvents(self, ballNum):
        # returns a set of events that occurered with the number of balls in the count
        # negative inputs return all events with a ball count greater than or equal to the input
        # inputting a list or set will return the all events that match the numbers in the list
        ballNumList = ballNum if isinstance(ballNum, (list, set)) else [ballNum]
        return self.listInputHandling(ballNumList, self._balls_dict)
    
    def strikeEvents(self, strikeNum):
        # returns a set of events that occurered with the number of strikes in the count
        # negative inputs return all events with a strike count greater than or equal to the input
        # inputting a list or set will return the all events that match the numbers in the list
        strikeNumList = strikeNum if isinstance(strikeNum, (list, set)) else [strikeNum]
        return self.listInputHandling(strikeNumList, self._strikes_dict)

    def chemOnBaseEvents(self, chemNum):
        # returns a set of events that occurered with the number of chem on base
        # negative inputs return all events with a chem count greater than or equal to the input
        # inputting a list or set will return the all events that match the numbers in the list
        chemNumList = chemNum if isinstance(chemNum, (list, set)) else [chemNum]
        return self.listInputHandling(chemNumList, self._chem_on_base_dict)
        
    def rbiEvents(self, rbiNum):
        # returns a set of events that occurered with the number of chem on base
        # negative inputs return all events with a chem count greater than or equal to the input
        # inputting a list or set will return the all events that match the numbers in the list
        rbiNumList = rbiNum if isinstance(rbiNum, (list, set)) else [rbiNum]
        return self.listInputHandling(rbiNumList, self._rbi_dict)
        

    def halfInningEvents(self, halfInningNum: int):
          self.__errorCheck_halfInningNum(halfInningNum)
          return self._half_inning_dict[halfInningNum]
    
    def outsInInningEvents(self, outsNum: int):
        self.__errorCheck_halfInningNum(outsNum)
        if outsNum >= 0:
            return self._outs_in_inning_dict[outsNum]
        else:
            result = set()
            for i in range(abs(outsNum), 3):
                result = result.union(self._outs_in_inning_dict[i])
            return result
        
    def pitcherStaminaEvents(self, stamina):
        # returns a set of events that occurered with the number of pitcher stamina
        # negative inputs return all events with a stamina LESS THAN or equal to the input
        # inputting a list or set will return the all events that match the numbers in the list
        staminaList = stamina if isinstance(stamina, (list, set)) else [stamina]
        return self.listInputHandling(staminaList, 'Pitcher Stamina', to_zero=True)

    def starChanceEvents(self, isStarChance=True):
        if isStarChance:
            return self._star_chance_dict[1]
        return self._star_chance_dict[0]

    def numOutsDuringPlayEvents(self, numOuts):
         numOutsList = numOuts if isinstance(numOuts, (list, set)) else [numOuts]
         return self.listInputHandling(numOutsList, self._outs_during_event_dict)

    def curvePitchTypeEvents(self):
        return self._pitch_type_dict['Curve']
    
    def chargePitchTypeEvents(self):
        return self._pitch_type_dict['Charge']

    def sliderPitchTypeEvents(self):
        return self._charge_type_dict['Slider']

    def perfectChargePitchTypeEvents(self):
        return self._charge_type_dict['Perfect']

    def changeUpPitchTypeEvents(self):
        return self._pitch_type_dict['ChangeUp']
    
    def pitchTypeEvents(self, pitchType):
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
                raise Exception(f'{pitch} is not a valid pitch type. Curve, Charge, Slider, Perfect, and ChangeUp are accepted.')
        
        return result

    def inStrikezoneEvents(self):
        return self._pitch_in_strikezone_dict[1]

    def noneSwingTypeEvents(self):
        return self._swing_type_dict['None']

    def slapSwingTypeEvents(self):
        return self._swing_type_dict['Slap']

    def chargeSwingTypeEvents(self):
        return self._swing_type_dict['Charge']

    def starSwingTypeEvents(self):
        return self._swing_type_dict['Star']

    def buntSwingTypeEvents(self):
        return self._swing_type_dict['Bunt']
    
    def swingTypeEvents(self, swingType):
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
                raise Exception(f'{swing} is not a valid swing type. None, Slap, Charge, Star, and Bunt are accepted.')
        
        return result
    
    def niceContactTypeEvents(self, side='b'):
        if side == 'b':
            return self._contact_type_dict['Nice - Left'] | self._contact_type_dict['Nice - Right']
        if side == 'l':
            return self._contact_type_dict['Nice - Left']
        if side == 'r':
            return self._contact_type_dict['Nice - Right']
        
    def perfectContactTypeEvents(self):
         return self._contact_type_dict['Perfect']

    def sourContactTypeEvents(self, side='b'):
        if side == 'b':
            return self._contact_type_dict['Sour - Left'] | self._contact_type_dict['Sour - Right']
        if side == 'l':
            return self._contact_type_dict['Sour - Left']
        if side == 'r':
            return self._contact_type_dict['Sour - Right']

    def contactTypeEvents(self, contactType):
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
                raise Exception(f'{contact} is not a valid contact type. Sour, Nice, and Perfect are accepted.')
        
        return result

    def inputDirectionEvents(self, input_directions):
        return self._input_direction_dict[input_directions]

    def contactFrameEvents(self, contactFrame):
        # returns a set of contacts that occurered on the specified frame
        # negative inputs return all events with a strike count greater than or equal to the input
        # inputting a list or set will return the all events that match the numbers in the list
        contactFrameList = contactFrame if isinstance(contactFrame, (list, set)) else [contactFrame]
        return self.listInputHandling(contactFrameList, self._contact_frame_dict)

    def characterAtBatEvents(self, char_id):
        # returns a set of events where the input character was at bat
        # returns an empty set if the character was not in the game
        # rather than raising an error
        if char_id not in self.character_action_dict.keys():
            return set()
        return self.character_action_dict[char_id]['AtBat']
    
    def characterPitchingEvents(self, char_id):
        # returns a set of events where the input character was pitching
        # returns an empty set if the character was not in the game
        # rather than raising an error
        if char_id not in self.character_action_dict.keys():
            return set()
        return self.character_action_dict[char_id]['Pitching']
    
    def characterFieldingEvents(self, char_id):
        # returns a set of events where the input character is the first fielder
        # returns an empty set if the character was not in the game
        # rather than raising an error
        if char_id not in self.character_action_dict.keys():
            return set()
        return self.character_action_dict[char_id]['Fielding']
    
    def positionFieldingEvents(self, fielderPos):
        # returns a set of events where the input fielding pos is the first fielder
        # raises an error when the imput fielding pos is not valid
        self.__errorCheck_fielder_pos(fielderPos)
        return self._first_fielder_position_dict[fielderPos.upper()]
    
    def walkoffEvents(self):
        final_event = EventObj(self.rioStat, self.rioStat.final_event())
        # returns a set of events of game walkoffs
        if final_event.rbi() != 0:
            return set([self.rioStat.final_event()])
        return set()
    
    def playerBattingEvents(self, playerBatting):
        if playerBatting.lower() == self.rioStat.player(0).lower():
            return self.halfInningEvents(0)
        elif playerBatting.lower() == self.rioStat.player(1).lower():
            return self.halfInningEvents(1)
        else:
            return set()
        
    def playerPitchingEvents(self, playerPitching):
        if playerPitching.lower() == self.rioStat.player(0).lower():
            return self.halfInningEvents(1)
        elif playerPitching.lower() == self.rioStat.player(1).lower():
            return self.halfInningEvents(0)
        else:
            return set()
        
    def ballPositionStrikezoneEvents(self, minimimum_ball_pos):
        result = set()
        for key in self._ball_position_strikezone:
            if abs(key) >= abs(minimimum_ball_pos):
                result = result.union(set(self._ball_position_strikezone[key]))
        return result
    
    def ballContactPositionEvents(self, minimimum_ball_pos):
        result = set()
        for key in self._x_ball_contact_pos:
            if abs(key) >= abs(minimimum_ball_pos):
                result = result.union(set(self._x_ball_contact_pos[key]))
        return result
    
    def firstPitchOfABEvents(self):
        return self._first_pitch_of_AB
    
    def lastPitchOfABEvents(self):
        return self._last_pitch_of_AB
    
    def leadChangedEvents(self):
        return self._lead_changed
    

        

class EventObj():
    def __init__(self, rioStat: StatObj, eventNum: int):
        self.rioStat = rioStat
        self.all_events = rioStat.events()
        if abs(eventNum) > len(self.all_events):
            raise Exception(f'Invalid event num: Event {eventNum} does not exist in game')
        self.eventDict = self.all_events[eventNum]

    def safe_int(self, value):
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
        
    def event_num(self):
        return self.eventDict['Event Num']

    def inning(self):
        # returns the ininng from a specified event
        return self.eventDict["Inning"]
    
    def half_inning(self):
        # returns the half ininng from a specified event
        return self.eventDict["Half Inning"]
    
    def score(self, teamNum: int):
        ErrorChecker.check_team_num(teamNum)
        if teamNum == 0:
            return self.eventDict['Away Score']
        else:
            return self.eventDict['Home Score']
        
    def balls(self):
        # returns the ininng from a specified event
        return self.eventDict["Balls"]
    
    def strikes(self):
        # returns the strikes from a specified event
        return self.eventDict["Strikes"]
    
    def outs(self):
        # returns the ininng from a specified event
        return self.eventDict["Outs"]
    
    def star_chance(self):
        return self.eventDict['Star Chance']
    
    def team_stars(self, teamNum: int):
        ErrorChecker.check_team_num(teamNum)
        if teamNum == 0:
            return self.eventDict['Away Stars']
        else:
            return self.eventDict['Home Stars']
        
    def pitcher_stamina(self):
        return self.eventDict['Pitcher Stamina']
    
    def chem_links_on_base(self):
        return self.eventDict["Chemistry Links on Base"]
    
    def batting_team(self):
        return self.half_inning()
    
    def pitching_team(self):
        return abs(self.half_inning() - 1)
    
    def pitcher_roster_loc(self):
        return self.eventDict['Pitcher Roster Loc']
    
    def pitcher(self):
        return self.rioStat.characterName(self.pitching_team(), self.eventDict['Pitcher Roster Loc'])
    
    def batter_roster_loc(self):
        return self.eventDict['Batter Roster Loc']
        
    def batter(self):
        return self.rioStat.characterName(self.batting_team(), self.eventDict['Batter Roster Loc'])
    
    def batter_hand(self):
        return self.rioStat.battingHand(self.batting_team(), self.eventDict['Batter Roster Loc'])
    
    def catcher(self):
        return self.rioStat.characterName(self.batting_team(), self.eventDict['Catcher Roster Loc'])
    
    def rbi(self):
        # returns the rbi from a specified event
        return self.eventDict['RBI']
    
    def num_outs_during_play(self):
        return self.eventDict['Num Outs During Play']
    
    def result_of_AB(self):
        return self.eventDict['Result of AB']
    
    def runners(self):
        return set(self.eventDict.keys()).intersection(['Runner 1B', 'Runner 2B', 'Runner 3B'])
    
    def bool_runner_on_base(self, baseNum: int):
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
    
    def runner_dict(self, baseNum: int):
        ErrorChecker.check_base_num(baseNum)
        if baseNum == 0:
            runner_str = 'Runner Batter'
        else:
            runner_str = f'Runner {baseNum}B'
        return self.eventDict.get(runner_str, {})
    
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
    
    def pitch_dict(self):
        """
        Returns an empty dict if no pitch in event
        """
        return self.eventDict.get('Pitch', {})
    
    def pitch_type(self):
        """
        Returns None if no pitch in event
        """
        return self.pitch_dict().get('Pitch Type')
    
    def charge_type(self):
        """
        Returns None if no pitch in event
        """
        return self.pitch_dict().get('Charge Type')
    
    def star_pitch(self):
        """
        Returns None if no pitch in event
        """
        return self.pitch_dict().get('Star Pitch')
    
    def pitch_speed(self):
        """
        Returns None if no pitch in event
        """
        return self.pitch_dict().get('Pitch Speed')
    
    def ball_position_strikezone(self):
        """
        Returns None if no pitch in event
        """
        return self.pitch_dict().get('Ball Position - Strikezone')
    
    def in_strikezone(self):
        """
        Returns None if no pitch in event
        """
        return self.pitch_dict().get('In Strikezone')
    
    def bat_contact_position_x(self):
        """
        Returns None if no pitch in event
        """
        return self.pitch_dict().get('Bat Contact Pos - X')
    
    def bat_contact_position_z(self):
        """
        Returns None if no pitch in event
        """
        return self.pitch_dict().get('Bat Contact Pos - Z')
    
    def dickball(self):
        """
        Returns None if no pitch in event
        """
        return self.pitch_dict().get('DB')
    
    def type_of_swing(self):
        """
        Returns None if no pitch in event
        """
        return self.pitch_dict().get('Type of Swing')

    def contact_dict(self):
        """
        Returns an empty dict if no contact in event
        """
        return self.pitch_dict().get('Contact', {})

    def type_of_contact(self):
        """
        Returns None if no contact in event
        """
        return self.contact_dict().get('Type of Contact')

    def charge_power_up(self):
        """
        Returns None if no contact in event
        """
        return self.contact_dict().get('Charge Power Up')

    def charge_power_down(self):
        """
        Returns None if no contact in event
        """
        return self.contact_dict().get('Charge Power Down')

    def five_star_swing(self):
        """
        Returns None if no contact in event
        """
        return self.contact_dict().get('Star Swing Five-Star')

    def input_direction_push_or_pull(self):
        """
        Returns None if no contact in event
        """
        return self.contact_dict().get('Input Direction - Push/Pull')

    def stick_input_direction(self):
        """
        Returns None if no contact in event
        """
        return self.contact_dict().get('Input Direction - Stick')

    def contact_frame(self):
        """
        Returns None if no contact in event
        """
        return self.safe_int(self.contact_dict().get('Frame of Swing Upon Contact'))

    def ball_power(self):
        """
        Returns None if no contact in event
        """
        return self.safe_int(self.contact_dict().get('Ball Power'))

    def vert_angle(self):
        """
        Returns None if no contact in event.
        """
        return self.safe_int(self.contact_dict().get('Vert Angle'))

    def horiz_angle(self):
        """
        Returns None if no contact in event.
        """
        return self.safe_int(self.contact_dict().get('Horiz Angle'))

    def contact_absolute(self):
        """
        Returns None if no contact in event.
        """
        return self.contact_dict().get('Contact Absolute')

    def contact_quality(self):
        """
        Returns None if no contact in event.
        """
        return self.contact_dict().get('Contact Quality')

    def rng(self):
        """
        Returns None if no contact in event.
        Returns a vector (rng1, rng2, rng3) of RNG components.
        """
        rng1 = self.safe_int(self.contact_dict().get('RNG1'))
        rng2 = self.safe_int(self.contact_dict().get('RNG2'))
        rng3 = self.safe_int(self.contact_dict().get('RNG3'))
        return (rng1, rng2, rng3)

    def ball_velocity(self):
        """
        Returns None if no contact in event.
        Returns a vector (x, y, z) of ball velocity components.
        """
        x = self.contact_dict().get('Ball Velocity - X')
        y = self.contact_dict().get('Ball Velocity - Y')
        z = self.contact_dict().get('Ball Velocity - Z')
        return (x, y, z)

    def ball_contact_position(self):
        """
        Returns None if no contact in event.
        Returns a vector (x, z) of ball contact position components.
        """
        x = self.contact_dict().get('Ball Contact Pos - X')
        z = self.contact_dict().get('Ball Contact Pos - Z')
        return (x, z)

    def ball_landing_position(self):
        """
        Returns None if no contact in event.
        Returns a vector (x, y, z) of ball landing position components.
        """
        x = self.contact_dict().get('Ball Landing Position - X')
        y = self.contact_dict().get('Ball Landing Position - Y')
        z = self.contact_dict().get('Ball Landing Position - Z')
        return (x, y, z)

    def ball_max_height(self):
        """
        Returns None if no contact in event.
        """
        return self.contact_dict().get('Ball Max Height')

    def ball_hang_time(self):
        """
        Returns None if no contact in event.
        """
        return self.safe_int(self.contact_dict().get('Ball Hang Time'))

    def contact_result_primary(self):
        """
        Returns None if no contact in event.
        """
        return self.contact_dict().get('Contact Result - Primary')

    def contact_result_secondary(self):
        """
        Returns None if no contact in event.
        """
        return self.contact_dict().get('Contact Result - Secondary')

    def first_fielder_dict(self):
        """
        Returns an empty dict if no first fielder in event
        """
        return self.contact_dict().get('First Fielder', {})
    
    def first_fielder_roster_loc(self):
        """
        Returns None if no first fielder in event.
        """
        return self.first_fielder_dict().get('Fielder Roster Location')

    def first_fielder_position(self):
        """
        Returns None if no first fielder in event.
        """
        return self.first_fielder_dict().get('Fielder Position')

    def first_fielder_character(self):
        """
        Returns None if no first fielder in event.
        """
        return self.first_fielder_dict().get('Fielder Character')

    def first_fielder_action(self):
        """
        Returns None if no first fielder in event.
        """
        return self.first_fielder_dict().get('Fielder Action')

    def first_fielder_jump(self):
        """
        Returns None if no first fielder in event.
        """
        return self.first_fielder_dict().get('Fielder Jump')

    def fielder_swap(self):
        """
        Returns None if no first fielder in event.
        """
        return self.first_fielder_dict().get('Fielder Swap')

    def first_fielder_maunual_selected(self):
        """
        Returns None if no first fielder in event.
        """
        return self.first_fielder_dict().get('Fielder Manual Selected')

    def first_fielder_location(self):
        """
        Returns None if no first fielder in event.
        Returns a vector (x, y, z) of fielder position components.
        """
        x = self.first_fielder_dict().get('Fielder Position - X')
        y = self.first_fielder_dict().get('Fielder Position - Y')
        z = self.first_fielder_dict().get('Fielder Position - Z')
        return (x, y, z)

    def first_fielder_bobble(self):
        """
        Returns None if no first fielder in event.
        """
        return self.first_fielder_dict().get('Fielder Bobble')
    

class HudObj:
    def __init__(self, hud_json: dict):
        self.hud_json = hud_json
        self.event_number = self.hud_json['Event Num']

    def event_integer(self):
        return int(str(self.event_number)[:-1])

    def player(self, teamNum: int):
        ErrorChecker.check_team_num(teamNum)
        if teamNum == 0:
            return self.hud_json['Away Player']
        elif teamNum == 1:
            return self.hud_json['Home Player']
    
    def inning(self):
        return self.hud_json['Inning']
    
    def half_inning(self):
        return self.hud_json['Half Inning']
    
    def inning_float(self):
        return float(self.hud_json['Inning'] + 0.5*self.hud_json['Half Inning'])
    
    def score(self, teamNum: int):
        ErrorChecker.check_team_num(teamNum)
        team_string = "Away" if teamNum == 0 else "Home"
        
        return self.hud_json[f'{team_string} Score']
    
    def balls(self):
        return self.hud_json['Balls']
    
    def strikes(self):
        return self.hud_json['Strikes']
    
    def outs(self):
        return self.hud_json['Outs']
    
    def star_chance(self):
        return self.hud_json['Star Chance']
    
    def team_stars(self, teamNum: int):
        ErrorChecker.check_team_num(teamNum)
        team_string = "Away" if teamNum == 0 else "Home"
        
        return self.hud_json[f'{team_string} Stars']
    
    def pitcher_stamina(self):
        return self.hud_json['Pitcher Stamina']
    
    def chem_on_base(self):
        return self.hud_json['Chemistry Links on Base']
    
    def outs_during_play(self):
        return self.hud_json['Num Outs During Play']
    
    def pitcher_roster_location(self):
        return self.hud_json['Pitcher Roster Loc']
    
    def batter_roster_location(self):
        return self.hud_json['Batter Roster Loc']
    
    def runner_on_first(self):
        return bool(self.hud_json.get('Runner 1B'))
    
    def runner_on_second(self):
        return bool(self.hud_json.get('Runner 2B'))
    
    def runner_on_third(self):
        return bool(self.hud_json.get('Runner 3B'))

    def team_roster_str_list(self, teamNum: int):
        ErrorChecker.check_team_num(teamNum)
        team_string = "Away" if teamNum == 0 else "Home"
        team_roster_str_list = []
        for i in range (9):
             team_roster_str_list.append(f'{team_string} Roster {i}')
        
        return team_roster_str_list

    def roster(self, teamNum: int):
        roster_dict = {}
        for player in self.team_roster_str_list(teamNum):
            player_index = int(player[-1])
            roster_dict[player_index] = {}
            roster_dict[player_index]['captain'] = self.hud_json[player]['Captain']
            roster_dict[player_index]['char_id'] = self.hud_json[player]['CharID']

        return roster_dict
    
    def inning_end(self):
        if self.hud_json['Outs'] + self.hud_json['Num Outs During Play'] == 3:
            return True
        return False
    
    def event_result(self):
        if str(self.hud_json['Event Num'])[-1] == 'b':
            return self.hud_json['Result of AB']
        
        return 'In Play'
    
    def captain_index(self, teamNum: int):
        ErrorChecker.check_team_num(teamNum)
        for player in self.team_roster_str_list(teamNum):
            if self.hud_json[player]['Captain'] == 1:
                return int(player[-1])
        raise Exception(f'No captain on teamNum {teamNum}')

    
'''
    "Event Num": 50,
      "Inning": 3,
      "Half Inning": 1,
      "Away Score": 0,
      "Home Score": 1,
      "Balls": 0,
      "Strikes": 1,
      "Outs": 1,
      "Star Chance": 0,
      "Away Stars": 0,
      "Home Stars": 0,
      "Pitcher Stamina": 9,
      "Chemistry Links on Base": 0,
      "Pitcher Roster Loc": 8,
      "Batter Roster Loc": 2,
      "Catcher Roster Loc": 4,
      "RBI": 0,
      "Num Outs During Play": 0,
      "Result of AB": "None",
      "Runner Batter": {
        "Runner Roster Loc": 2,
        "Runner Char Id": "Waluigi",
        "Runner Initial Base": 0,
        "Out Type": "None",
        "Out Location": 0,
        "Steal": "None",
        "Runner Result Base": 0
      },
      "Runner 1B": {
        "Runner Roster Loc": 1,
        "Runner Char Id": "Luigi",
        "Runner Initial Base": 1,
        "Out Type": "None",
        "Out Location": 0,
        "Steal": "None",
        "Runner Result Base": 1
      },
      "Runner 2B": {
        "Runner Roster Loc": 0,
        "Runner Char Id": "Baby Mario",
        "Runner Initial Base": 2,
        "Out Type": "None",
        "Out Location": 0,
        "Steal": "None",
        "Runner Result Base": 2
      },
      "Pitch": {
        "Pitcher Team Id": 0,
        "Pitcher Char Id": "Dixie",
        "Pitch Type": "Charge",
        "Charge Type": "Slider",
        "Star Pitch": 0,
        "Pitch Speed": 162,
        "Ball Position - Strikezone": -0.260153,
        "In Strikezone": 1,
        "Bat Contact Pos - X": -0.134028,
        "Bat Contact Pos - Z": 1.5,
        "DB": 0,
        "Type of Swing": "Slap",
        "Contact": {
          "Type of Contact":"Nice - Right",
          "Charge Power Up": 0,
          "Charge Power Down": 0,
          "Star Swing Five-Star": 0,
          "Input Direction - Push/Pull": "Towards Batter",
          "Input Direction - Stick": "Right",
          "Frame of Swing Upon Contact": "2",
          "Ball Power": "139",
          "Vert Angle": "158",
          "Horiz Angle": "1,722",
          "Contact Absolute": 109.703,
          "Contact Quality": 0.988479,
          "RNG1": "4,552",
          "RNG2": "5,350",
          "RNG3": "183",
          "Ball Velocity - X": -0.592068,
          "Ball Velocity - Y": 0.166802,
          "Ball Velocity - Z": 0.323508,
          "Ball Contact Pos - X": -0.216502,
          "Ball Contact Pos - Z": 1.5,
          "Ball Landing Position - X": -45.4675,
          "Ball Landing Position - Y": 0.176705,
          "Ball Landing Position - Z": 17.4371,
          "Ball Max Height": 4.23982,
          "Ball Hang Time": "89",
          "Contact Result - Primary": "Foul",
          "Contact Result - Secondary": "Foul"
        }
      }
    },
    '''

if __name__ == '__main__':
    print({value: set() for value in LookupDicts.FINAL_RESULT.values()})
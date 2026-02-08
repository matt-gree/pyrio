# Nuche17 Feb 2026
# From a directory of stat files, creates a pitch-level data set and exports to CSV.

from . import stat_file_parser
import json
import csv
import os
from pathlib import Path

dataRows = []
prevEv = {}

#  Helper generator to load StatObjs from a directory.
def load_statobjs_from_directory(directory):
    for filename in os.listdir(directory):
        if "decoded" not in filename:
            continue

        path = os.path.join(directory, filename)
        if not os.path.isfile(path):
            continue

        with open(path, "r") as f:
            jsonObj = json.load(f)
            yield stat_file_parser.StatObj(jsonObj)

def pitch_rows_from_statobj(sf, include_character_attributes=False):
    """
    Yield pitch-level rows for a StatObj.
    Optionally appends pitcher and batter character attributes.
    """
    if include_character_attributes:
        _load_character_attributes()

    prevEv = {}

    for ev in sf.events():
        if "Pitch" not in ev:
            continue

        batterIndex = ev["Half Inning"]
        pitcherIndex = 1 - batterIndex

        eventNumber = ev["Event Num"]

        pitchingPlayer = sf.player(pitcherIndex)
        battingPlayer = sf.player(batterIndex)

        pitchingCharacter = sf.characterName(
            pitcherIndex, ev["Pitcher Roster Loc"]
        )
        battingCharacter = sf.characterName(
            batterIndex, ev["Batter Roster Loc"]
        )

        # Strip variants (e.g. "Mario (Fireball)" -> "Mario")
        def strip_variant(name):
            idx = name.find("(")
            return name if idx == -1 else name[:idx]

        pitchingCharacterNoVariant = strip_variant(pitchingCharacter)
        battingCharacterNoVariant = strip_variant(battingCharacter)

        pitcherStarred = sf.isStarred(pitcherIndex, ev["Pitcher Roster Loc"])
        batterStarred = sf.isStarred(batterIndex, ev["Batter Roster Loc"])

        inning = ev["Inning"]
        halfInning = ev["Half Inning"]

        if halfInning == 0:
            pitchingScore = ev["Home Score"]
            battingScore = ev["Away Score"]
            pitchingStars = ev["Home Stars"]
            battingStars = ev["Away Stars"]
        else:
            pitchingScore = ev["Away Score"]
            battingScore = ev["Home Score"]
            pitchingStars = ev["Away Stars"]
            battingStars = ev["Home Stars"]

        balls = ev["Balls"]
        strikes = ev["Strikes"]
        outs = ev["Outs"]

        starChance = ev["Star Chance"]
        stamina = ev["Pitcher Stamina"]
        chemistry = ev["Chemistry Links on Base"]

        battingOrder = ev["Batter Roster Loc"]
        batterHand = sf.battingHand(batterIndex, ev["Batter Roster Loc"])

        # Count runners on base
        runners = sum(
            base in ev for base in ("Runner 1B", "Runner 2B", "Runner 3B")
        )


        pitchType = ev["Pitch"]["Pitch Type"]
        pitchXPos = ev["Pitch"]["Ball Position - Strikezone"]
        pitchInZone = ev["Pitch"]["In Strikezone"]
        swingType = ev["Pitch"]["Type of Swing"]
        batterPosX = ev["Pitch"]["Bat Contact Pos - X"]
        batterPosZ = ev["Pitch"]["Bat Contact Pos - Z"]
        rBIs = ev["RBI"]
        result = ev["Result of AB"]

        gameID = sf.gameID()
        gameMode = sf.gameMode()
        stadium = sf.stadium()

        # Base pitch row (unchanged schema)
        row = [
            eventNumber,
            pitchingPlayer,
            battingPlayer,
            pitchingCharacter,
            battingCharacter,
            pitchingCharacterNoVariant,
            battingCharacterNoVariant,
            pitcherStarred,
            batterStarred,
            inning,
            halfInning,
            pitchingScore,
            battingScore,
            pitchingStars,
            battingStars,
            balls,
            strikes,
            outs,
            starChance,
            stamina,
            chemistry,
            battingOrder,
            batterHand,
            runners,
            pitchType,
            pitchXPos,
            pitchInZone,
            swingType,
            batterPosX,
            batterPosZ,
            rBIs,
            result,
            gameID,
            gameMode,
            stadium
        ]

        # Optional: append character attributes
        if include_character_attributes:
            if pitcherStarred == 0:
                pitcher_attrs = _CHAR_ATTRS_STOFF.get(pitchingCharacter)
            else:
                pitcher_attrs = _CHAR_ATTRS_STON.get(pitchingCharacter)

            if batterStarred == 0:
                batter_attrs = _CHAR_ATTRS_STOFF.get(battingCharacter)
            else:
                batter_attrs = _CHAR_ATTRS_STON.get(battingCharacter)

            for attrs in (pitcher_attrs, batter_attrs):
                if attrs:
                    row.extend(attrs[col] for col in _CHAR_ATTR_COLUMNS)
                else:
                    row.extend([""] * len(_CHAR_ATTR_COLUMNS))

        yield row
        prevEv = ev


BASE_HEADER = [
    'eventNumber',
    'pitchingPlayer',
    'battingPlayer',
    'pitchingCharacter',
    'battingCharacter',
    'pitchingCharacterNoVariant',
    'battingCharacterNoVariant',
    'pitcherStarred',
    'batterStarred',
    'inning',
    'halfInning',
    'pitchingScore',
    'battingScore',
    'pitchingStars',
    'battingStars',
    'balls',
    'strikes',
    'outs',
    'starChance',
    'stamina',
    'chemistry',
    'battingOrder',
    'batterHand',
    'runners',
    'pitchType',
    'pitchXPos',
    'pitchInZone',
    'swingType',
    'batterPosX',
    'batterPosZ',
    'rBIs',
    'result',
    'gameID',
    'gameMode',
    'stadium'
]

# for option to load character attributes data if the user would like to append it to the pitch data rows.
_CHAR_ATTRS_STOFF = None
_CHAR_ATTRS_STON = None
_CHAR_ATTR_COLUMNS = None

def _load_character_attributes():
    global _CHAR_ATTRS_STOFF, _CHAR_ATTRS_STON, _CHAR_ATTR_COLUMNS

    if _CHAR_ATTRS_STOFF is not None and _CHAR_ATTRS_STON is not None:
        return

    data_path = Path(__file__).parent / "character_attributes_stoff.csv"

    attrs_stoff = {}
    with open(data_path, newline="") as f:
        reader = csv.DictReader(f)
        _CHAR_ATTR_COLUMNS = reader.fieldnames[1:]  

        for row in reader:
            name = row["Character"]
            attrs_stoff[name] = row

    _CHAR_ATTRS_STOFF = attrs_stoff

    data_path = Path(__file__).parent / "character_attributes_ston.csv"

    attrs_ston = {}
    with open(data_path, newline="") as f:
        reader = csv.DictReader(f)
        _CHAR_ATTR_COLUMNS = reader.fieldnames[1:]  

        for row in reader:
            name = row["Character"]
            attrs_ston[name] = row

    _CHAR_ATTRS_STON = attrs_ston

def make_header(include_char_attrs=False):
    header = BASE_HEADER.copy()

    if include_char_attrs:
        for prefix in ("pitcher", "batter"):
            for col in _CHAR_ATTR_COLUMNS:
                header.append(f"{prefix}_{col}")

    return header

def write_pitch_csv(statobjs, output_path, include_character_attributes=False,):
    if include_character_attributes:
        _load_character_attributes()

    header = make_header(include_character_attributes)

    with open(output_path, "w", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(header)

        for sf in statobjs:
            for row in pitch_rows_from_statobj(sf, include_character_attributes=include_character_attributes):
                writer.writerow(row)


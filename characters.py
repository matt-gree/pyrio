import csv
from .lookup import Lookup, LookupDicts, CAPTAINS
import os


charNameDict = {}
char_name_list = []

char_lookup = Lookup().lookup

file_path = os.path.join(os.path.dirname(__file__), 'CharNames.csv')
with open(file_path, 'r') as file:
    reader = csv.reader(file)
    for row in reader:
        char_name_list.append(row)

# convert list of lists to kv objects format {<name>: <csv Index>}
for i, sublist in enumerate(char_name_list):
    for name in sublist:
        charNameDict[name] = i

def userInputToCharacter(userInput):
    if userInput.lower() not in charNameDict.keys():
        raise Exception(f'{userInput} is an invalid character name')
    return char_lookup(LookupDicts.CHAR_NAME, charNameDict[userInput.lower()])

def is_captain(character):
    if userInputToCharacter(character) in CAPTAINS:
        return True
    
    return False

if __name__ == '__main__':
    print(userInputToCharacter('luigi'))
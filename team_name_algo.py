from .characters import is_captain
from .lookup import CHAR_TO_SIMPLIFIED, SIMPLIFIED_TO_CLASS

In_Game_Team_Names = {
        'Mario':[{'Name':'Mario Heroes'},
                {'Name':'Mario Fireballs'},
                {'Name': 'Mario Sunshines', 'Characters':['Luigi', 'Monty', 'Pianta', 'Noki']},
                {'Name': 'Mario All Stars', 'Characters':['Peach', 'Yoshi', 'Donkey Kong', 'Bowser']}],

        'Luigi':[{'Name': 'Luigi Gentlemen'},
                {'Name': 'Luigi Vacuums'},
                {'Name': 'Luigi Mansioneers', 'Characters':['Bowser', 'Toad', 'Boo', 'King Boo']},
                {'Name': 'Luigi Leapers', 'Characters':['Waluigi', 'Diddy', 'Daisy', 'Baby Luigi']}],

        'Peach':[{'Name': 'Peach Roses'},
                {'Name': 'Peach Dynasties'},
                {'Name': 'Peach Monarchs', 'Characters':['Daisy', 'Toad', 'Toadsworth', 'Toadette']},
                {'Name': 'Peach Princesses', 'Characters':['Mario', 'Bowser', 'Baby Mario', 'Bowser Jr']}],

        'Daisy':[{'Name': 'Daisy Lillies'},
                {'Name': 'Daisy Cupids'},
                {'Name': 'Daisy Queen Bees', 'Characters':['Peach', 'Dixie Kong', 'Toadette', 'Noki']},
                {'Name': 'Daisy Petals', 'Characters':['Birdo', 'Dixie Kong', 'Wario', 'Petey']}], 

        'Yoshi':[{'Name': 'Yoshi Eggs'},
                {'Name': 'Yoshi Speed Stars'},
                {'Name': 'Yoshi Islanders', 'Characters':['Birdo', 'Baby Mario', 'Baby Luigi', 'Shy Guy']},
                {'Name': 'Yoshi Flutters', 'Characters':['Boo', 'King Boo', 'Paratroopa', 'Paragoomba']}],

        'Birdo':[{'Name': 'Birdo Beauties'},
                {'Name': 'Birdo Models'},
                {'Name': 'Birdo Bows', 'Characters':['Mario', 'Luigi', 'Peach', 'Toad']},
                {'Name': 'Birdo Fans', 'Characters':['Yoshi', 'Shy Guy', 'Goomba', 'Koopa']}],

        'Wario':[{'Name': 'Wario Garlics'},
                {'Name': 'Wario Steakheads'},
                {'Name': 'Wario Greats', 'Characters':['Waluigi', 'King Boo', 'Magikoopa', 'Petey']},
                {'Name': 'Wario Beasts', 'Characters':['DK', 'Bowser', 'Bowser Jr', 'Bro']}],

        'Waluigi':[{'Name': 'Waluigi Mystiques'},
                {'Name': 'Waluigi Smart Alecks'},
                {'Name': 'Waluigi Flankers', 'Characters':['King Boo', 'Wario', 'Magikoopa', 'Dry Bones']},
                {'Name': 'Waluigi Mashers', 'Characters':['Mario', 'Luigi', 'Toadsworth', 'Wario']}],

        'DK':[{'Name': 'DK Explorers'},
            {'Name': 'DK Wild Ones'},
            {'Name': 'DK Kongs', 'Characters':['Diddy', 'Dixie', 'Goomba', 'Koopa']},
            {'Name': 'DK Animals', 'Characters':['Yoshi', 'Bowser', 'Monty', 'Petey']}],

        'Diddy':[{'Name': 'Diddy Survivors'},
                {'Name': 'Diddy Ninjas'},
                {'Name': 'Diddy Tails', 'Characters':['Yoshi', 'Birdo', 'Dixie', 'Boo']},
                {'Name': 'Diddy Red Caps', 'Characters':['Mario', 'Birdo', 'Baby Mario', 'Toadette']}],

        'Bowser':[{'Name': 'Bowser Flames'},
                {'Name': 'Bowser Blue Shells'},
                {'Name': 'Bowser Monsters', 'Characters':['Bowser Jr', 'Bry Bones', 'Bro']},
                {'Name': 'Bowser Black Stars', 'Characters':['Waluigi', 'Wario', 'Petey', 'Bro']}],

        'Bowser Jr':[{'Name': 'Jr Fangs'},
                    {'Name': 'Jr Bombers'},
                    {'Name': 'Jr Pixies', 'Characters':['Diddy', 'Boo', 'Shy Guy', 'Goomba']},
                    {'Name': 'Jr Rookies', 'Characters':['Diddy', 'Dixie', 'Baby Mario', 'Baby Luigi']},]
}

In_Game_Team_Names_List = []

for teams in In_Game_Team_Names.values():
    for entry in teams:
        name = entry.get("Name")
        if name:
            In_Game_Team_Names_List.append(name)

def team_name(roster: list[str], captain: str) -> str:
    if '' in roster:
        return ''
    
    if not is_captain(captain):
        return ''
    
    simplified_roster = []
    for character in roster:
        simplified_roster.append(CHAR_TO_SIMPLIFIED[character])

    running_total = 0
    for character in In_Game_Team_Names[captain][2]['Characters']:
        running_total += simplified_roster.count(character)

    if running_total >= 4:
        return In_Game_Team_Names[captain][2]['Name']

    running_total = 0
    for character in In_Game_Team_Names[captain][3]['Characters']:
        running_total += simplified_roster.count(character)

    if running_total >= 4:
        return In_Game_Team_Names[captain][3]['Name']

    class_roster = []
    for character in roster:
        class_roster.append(SIMPLIFIED_TO_CLASS[CHAR_TO_SIMPLIFIED[character]])

    class_count_dict = {'Balance': class_roster.count('Balance'),
                    'Technique': class_roster.count('Technique'),
                    'Speed': class_roster.count('Speed'),
                    'Power': class_roster.count('Power')}

    captain_class = SIMPLIFIED_TO_CLASS[CHAR_TO_SIMPLIFIED[captain]]

    class_list = ['Balance', 'Technique', 'Speed', 'Power']

    class_list.remove(captain_class)
    
    if ((class_count_dict[captain_class] > class_count_dict[class_list[0]]) and
        (class_count_dict[captain_class] > class_count_dict[class_list[1]]) and
        (class_count_dict[captain_class] > class_count_dict[class_list[2]])):
        return In_Game_Team_Names[captain][1]['Name']

    return In_Game_Team_Names[captain][0]['Name']
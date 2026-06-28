from .lookup import is_captain, lookup

TEAM_NAMES_DICT = {
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

in_game_team_names_list = []

for teams in TEAM_NAMES_DICT.values():
    for entry in teams:
        name = entry.get("Name")
        if name:
            in_game_team_names_list.append(name)

def team_name(roster: list[str], captain: str) -> str:
    if '' in roster:
        return ''
    
    if not is_captain(captain):
        return ''
    
    simplified_roster = []
    for character in roster:
        simplified_roster.append(lookup("simplified_name", character))

    running_total = 0
    for character in TEAM_NAMES_DICT[captain][2]['Characters']:
        running_total += simplified_roster.count(character)

    if running_total >= 4:
        return TEAM_NAMES_DICT[captain][2]['Name']

    running_total = 0
    for character in TEAM_NAMES_DICT[captain][3]['Characters']:
        running_total += simplified_roster.count(character)

    if running_total >= 4:
        return TEAM_NAMES_DICT[captain][3]['Name']

    class_roster = []
    for character in roster:
        class_roster.append(lookup("char_class", lookup("simplified_name", character)))

    class_count_dict = {'Balance': class_roster.count('Balance'),
                    'Technique': class_roster.count('Technique'),
                    'Speed': class_roster.count('Speed'),
                    'Power': class_roster.count('Power')}

    captain_class = lookup("char_class", lookup("simplified_name", captain))

    class_list = ['Balance', 'Technique', 'Speed', 'Power']

    class_list.remove(captain_class)
    
    if ((class_count_dict[captain_class] > class_count_dict[class_list[0]]) and
        (class_count_dict[captain_class] > class_count_dict[class_list[1]]) and
        (class_count_dict[captain_class] > class_count_dict[class_list[2]])):
        return TEAM_NAMES_DICT[captain][1]['Name']

    return TEAM_NAMES_DICT[captain][0]['Name']
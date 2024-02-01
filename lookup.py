# def lookup(dictionary):
#     def decorator(func):
#         def wrapper(search_term, auto_print=False):
#             def single_lookup(term):
#                 str_term = str(term).lower()
#                 adjusted = {str(k).lower(): str(v).lower() for k, v in dictionary.items()}
#
#                 if str_term in adjusted:
#                     return dictionary[int(term)] if isinstance(term, int) else dictionary[term]
#                 elif str_term in adjusted.values():
#                     return [key for key, value in dictionary.items() if value.lower() == str_term][0]
#                 else:
#                     return f"Invalid ID or Name: {term}"
#
#             result = [single_lookup(term) for term in search_term] if isinstance(search_term, list) else single_lookup(
#                 search_term)
#
#             if auto_print:
#                 print(result)
#             else:
#                 return result
#
#         return wrapper
#
#     return decorator
"""Refactoring of RioStatConverter to a class. The lookup class allows for bidirectional conversion
(argument of 0 returns Mario; argument of "Mario" returns 0)."""
# should try to standardize the string version of these names if possible to match with dataframe(s)
class LookupDicts:
    CHAR_NAME = 'char_name'
    STADIUM = 'stadium'
    CONTACT_TYPE = 'contact_type'
    HAND = 'hand'
    HAND_BOOL = 'hand_bool'
    INPUT_DIRECTION = 'input_direction'
    PITCH_TYPE = 'pitch_type'
    CHARGE_TYPE = 'charge_type'
    TYPE_OF_SWING = 'type_of_swing'
    POSITION = 'position'
    FIELDER_ACTIONS = 'fielder_actions'
    FIELDER_BOBBLES = 'fielder_bobbles'
    STEAL_TYPE = 'steal_type'
    OUT_TYPE = 'out_type'
    PITCH_RESULT = 'pitch_result'
    PRIMARY_CONTACT_RESULT = 'primary_contact_result'
    SECONDARY_CONTACT_RESULT = 'secondary_contact_result'
    FINAL_RESULT = 'final_result'
    MANUAL_SELECT = 'manual_select'

# todo - more complete error handling
class Lookup:
    def __init__(self):
        self.dictionaries = {
            LookupDicts.CHAR_NAME: {
            0: "Mario",
            1: "Luigi",
            2: "DK",
            3: "Diddy",
            4: "Peach",
            5: "Daisy",
            6: "Yoshi",
            7: "Baby Mario",
            8: "Baby Luigi",
            9: "Bowser",
            10: "Wario",
            11: "Waluigi",
            12: "Koopa(G)",
            13: "Toad(R)",
            14: "Boo",
            15: "Toadette",
            16: "Shy Guy(R)",
            17: "Birdo",
            18: "Monty",
            19: "Bowser Jr",
            20: "Paratroopa(R)",
            21: "Pianta(B)",
            22: "Pianta(R)",
            23: "Pianta(Y)",
            24: "Noki(B)",
            25: "Noki(R)",
            26: "Noki(G)",
            27: "Bro(H)",
            28: "Toadsworth",
            29: "Toad(B)",
            30: "Toad(Y)",
            31: "Toad(G)",
            32: "Toad(P)",
            33: "Magikoopa(B)",
            34: "Magikoopa(R)",
            35: "Magikoopa(G)",
            36: "Magikoopa(Y)",
            37: "King Boo",
            38: "Petey",
            39: "Dixie",
            40: "Goomba",
            41: "Paragoomba",
            42: "Koopa(R)",
            43: "Paratroopa(G)",
            44: "Shy Guy(B)",
            45: "Shy Guy(Y)",
            46: "Shy Guy(G)",
            47: "Shy Guy(Bk)",
            48: "Dry Bones(Gy)",
            49: "Dry Bones(G)",
            50: "Dry Bones(R)",
            51: "Dry Bones(B)",
            52: "Bro(F)",
            53: "Bro(B)",
        },
            LookupDicts.STADIUM: {
                0: "Mario Stadium",
                1: "Bowser Castle",
                2: "Wario Palace",
                3: "Yoshi Park",
                4: "Peach Garden",
                5: "DK Jungle",
                6: "Toy Field"
            },
            LookupDicts.CONTACT_TYPE: {
                255: "Miss",
                0: "Sour - Left",
                1: "Nice - Left",
                2: "Perfect",
                3: "Nice - Right",
                4: "Sour - Right"
            },
            LookupDicts.HAND: {
                0: "Left",
                1: "Right"
            },
            LookupDicts.HAND_BOOL: {
                True: "Left",
                False: "Right"
            },
            LookupDicts.INPUT_DIRECTION: {
                0: "None",
                1: "Left",
                2: "Right",
                4: "Down",
                5: "Down and Left",
                6: "Down and Right",
                8: "Up",
                9: "Up and Left",
                10: "Up and Right"
            },
            LookupDicts.PITCH_TYPE: {
                0: "Curve",
                1: "Charge",
                2: "ChangeUp"
            },
            LookupDicts.CHARGE_TYPE: {
                0: "N/A",
                2: "Slider",
                3: "Perfect"
            },
            LookupDicts.TYPE_OF_SWING: {
                0: "None",
                1: "Slap",
                2: "Charge",
                3: "Star",
                4: "Bunt"
            },
            LookupDicts.POSITION: {
                0: "P",
                1: "C",
                2: "1B",
                3: "2B",
                4: "3B",
                5: "SS",
                6: "LF",
                7: "CF",
                8: "RF",
                255: "Inv",
                None: "None"
            },
            LookupDicts.FIELDER_ACTIONS: {
                0: "None",
                2: "Sliding",
                3: "Walljump",
            },
            LookupDicts.FIELDER_BOBBLES: {
                0: "None",
                1: "Slide/stun lock",
                2: "Fumble",
                3: "Bobble",
                4: "Fireball",
                16: "Garlic knockout",
                255: "None"
            },
            LookupDicts.STEAL_TYPE: {
                0: "None",
                1: "Ready",
                2: "Normal",
                3: "Perfect",
                55: "None"
            },
            LookupDicts.OUT_TYPE: {
                0: "None",
                1: "Caught",
                2: "Force",
                3: "Tag",
                4: "Force Back",
                16: "Strike-out",
            },
            LookupDicts.PITCH_RESULT: {
                0: "HBP",
                1: "BB",
                2: "Ball",
                3: "Strike-looking",
                4: "Strike-swing",
                5: "Strike-bunting",
                6: "Contact",
                7: "Unknown"
            },
            LookupDicts.PRIMARY_CONTACT_RESULT: {
                0: "Out",
                1: "Foul",
                2: "Fair",
                3: "Fielded",
                4: "Unknown"
            },
            LookupDicts.SECONDARY_CONTACT_RESULT: {
                0: "Out-caught",
                1: "Out-force",
                2: "Out-tag",
                3: "foul",
                7: "Single",
                8: "Double",
                9: "Triple",
                10: "HR",
                11: "Error - Input",
                12: "Error - Chem",
                13: "Bunt",
                14: "SacFly",
                15: "Ground Ball Double Play",
                16: "Foul catch",
            },
            LookupDicts.FINAL_RESULT: {
                0: "None",
                1: "Strikeout",
                2: "Walk (BB)",
                3: "Walk HBP",
                4: "Out",
                5: "Caught (Anything Else)",
                6: "Caught (Line Drive)",
                7: "Single",
                8: "Double",
                9: "Triple",
                10: "HR",
                11: "Error Input",
                12: "Error Chem",
                13: "Bunt",
                14: "Sac Fly",
                15: "Ground Ball Double Play",
                16: "Foul Catch"
            },
            LookupDicts.MANUAL_SELECT: {
                0: "No Selected Char",
                1: "Selected Other Char",
                2: "Selected This Char",
                None: "None"
            }
        }

    def _lookup(self, dictionary, search_term):
        def single_lookup(term):
            if isinstance(term, str) and term.isdigit():
                term = int(term)

            str_term = str(term).lower()
            adjusted_dict = {str(k).lower(): str(v).lower() for k, v in dictionary.items()}

            if str_term in adjusted_dict:
                return dictionary[int(term)] if isinstance(term, int) else dictionary[term]
            elif str_term in adjusted_dict.values():
                return [key for key, value in dictionary.items() if value.lower() == str_term][0]
            else:
                return f"Invalid ID or Name: {term}"

        if isinstance(search_term, list):

            return [single_lookup(term) for term in search_term]
        else:
            return single_lookup(search_term)

    def lookup(self, dictionary_name, search_term, auto_print=False):
        dictionary = self.dictionaries.get(dictionary_name)
        if not dictionary:
            raise ValueError(f"Dictionary {dictionary_name} not found.")

        result = self._lookup(dictionary, search_term)
        if auto_print:
            print(result)
        return result

# lookup_instance = Lookup()

# sample usage
"""
print(lookup_instance.lookup(LookupDicts.CHAR_NAME, 'mario'))
"""
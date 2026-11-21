"""Canonical MSB asset filename lists.

Ported from main together with assets.py. The captain list is the interesting
part: main kept a hardcoded lookup.CAPTAINS, and prep derives it from the
"Captain Character" column of the attribute table, so this pins that the two
agree.
"""
from pyrio import assets
from pyrio.rio_value import Tables
from pyrio.team_name_algo import in_game_team_names_list

# main's lookup.CAPTAINS, verbatim, as the thing to agree with.
MAIN_CAPTAINS = ['Mario', 'Luigi', 'DK', 'Diddy', 'Peach', 'Daisy', 'Yoshi',
                 'Bowser', 'Wario', 'Waluigi', 'Birdo', 'Bowser Jr']


def _names(filenames):
    return [Tables.CHAR_NAME[int(f.removesuffix('.png'))] for f in filenames]


def test_every_character_has_a_filename():
    names = assets.required_character_filenames()
    assert len(names) == len(Tables.CHAR_NAME)
    assert names[0] == '0.png'
    assert all(f.endswith('.png') for f in names)


def test_captains_are_derived_not_listed():
    assert _names(assets.required_captain_filenames()) == MAIN_CAPTAINS


def test_captains_are_a_subset_of_characters_in_the_same_id_space():
    assert set(assets.required_captain_filenames()) <= set(
        assets.required_character_filenames())


def test_team_filenames_cover_the_in_game_team_names():
    assert len(assets.required_team_filenames()) == len(in_game_team_names_list)


def test_game_icons_include_the_superstar_badge():
    assert 'superstar.png' in assets.required_game_icon_filenames()

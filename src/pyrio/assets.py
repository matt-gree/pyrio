"""Canonical asset filename lists for Mario Superstar Baseball.

Use these to validate that a user-supplied MSB image asset pack is complete.
Each helper returns the expected ``.png`` filenames (no path) for one asset
category; consumers do their own filesystem checks.

Character and captain art are keyed by the canonical HUD character id
(``Tables.CHAR_NAME``, 0-53) rather than by name -- captains are just a
12-member subset of that same id space. Team logos have no HUD-native id, so
they are keyed by their index into ``in_game_team_names_list`` (0-47), an id
space pyrio itself defines.

Ported from main, where the captain list came from ``lookup.CAPTAINS``. prep
has no such list by design: a captain is a character whose attribute row says
so, so this reads ``is_captain`` off the attribute table instead.
"""
from .constants.character_data import character_attributes
from .rio_value import Tables
from .team_name_algo import in_game_team_names_list


def required_character_filenames() -> list[str]:
    """Character art filenames keyed by canonical HUD character id,
    e.g. ['0.png', '1.png', ..., '53.png'].

    Shared by any character-art folder (icons, portraits, ...), since they all
    use the same id space.
    """
    return [f"{char_id}.png" for char_id in sorted(Tables.CHAR_NAME)]


def required_captain_filenames() -> list[str]:
    """Captain art filenames, in the same id space as
    required_character_filenames() -- captains are characters."""
    return [f"{char_id}.png" for char_id in sorted(Tables.CHAR_NAME)
            if character_attributes(char_id).is_captain]


def required_team_filenames() -> list[str]:
    """All MSB in-game team logo filenames, keyed by index into
    in_game_team_names_list (0-47)."""
    return [f"{i}.png" for i in range(len(in_game_team_names_list))]


def required_game_icon_filenames() -> list[str]:
    """Miscellaneous in-game icons: the bat/glove batting-team indicator, the
    superstar badge, and any future game UI sprites."""
    return ["bat.png", "glove.png", "superstar.png"]

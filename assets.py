"""Canonical asset filename lists for Mario Superstar Baseball.

Use these to validate that a user-supplied MSB image asset pack is
complete. Each helper returns the expected `.png` filenames (no path)
for one asset category. Consumers do their own filesystem checks.

Character and captain art are keyed by the canonical HUD character id
(`LookupDicts.CHAR_NAME`, 0-53) rather than by name — captains are just a
12-member subset of that same id space. Team logos have no HUD-native id,
so they're keyed by their index into `in_game_team_names_list` (0-47),
an id space pyrio itself defines.
"""
from .lookup import CAPTAINS, LookupDicts
from .team_name_algo import in_game_team_names_list


def required_character_filenames() -> list[str]:
    """Character art filenames keyed by canonical HUD character id,
    e.g. ['0.png', '1.png', ..., '53.png']. Shared by any character-art
    folder (icons, portraits, ...) since they all use the same id space."""
    return [f"{char_id}.png" for char_id in sorted(LookupDicts.CHAR_NAME)]


def required_captain_filenames() -> list[str]:
    """Captain art filenames, keyed by the same character id space as
    required_character_filenames() — captains are characters."""
    name_to_id = {name: char_id for char_id, name in LookupDicts.CHAR_NAME.items()}
    return [f"{name_to_id[name]}.png" for name in CAPTAINS]


def required_team_filenames() -> list[str]:
    """All MSB in-game team logo filenames, keyed by index into
    in_game_team_names_list (0-47)."""
    return [f"{i}.png" for i in range(len(in_game_team_names_list))]


def required_game_icon_filenames() -> list[str]:
    """Miscellaneous in-game icons (bat/glove for batting/pitching team
    indicator, superstar badge, and any future game UI sprites)."""
    return ["bat.png", "glove.png", "superstar.png"]

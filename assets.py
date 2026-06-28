"""Canonical asset filename lists for Mario Superstar Baseball.

Use these to validate that a user-supplied MSB image asset pack is
complete. Each helper returns the expected `.png` filenames (no path)
for one asset category. Consumers do their own filesystem checks.
"""
from .lookup import LookupDicts
from .team_name_algo import in_game_team_names_list


def required_character_filenames() -> list[str]:
    """All character icon filenames, e.g. ['Mario.png', 'Luigi.png', ...]."""
    return [f"{name}.png" for name in LookupDicts.CHAR_NAME.values()]


def required_team_filenames() -> list[str]:
    """All MSB in-game team logo filenames produced by team_name_algo."""
    return [f"{name}.png" for name in in_game_team_names_list]


def required_game_icon_filenames() -> list[str]:
    """Miscellaneous in-game icons (bat/glove for batting/pitching team
    indicator, superstar badge, and any future game UI sprites)."""
    return ["bat.png", "glove.png", "superstar.png"]

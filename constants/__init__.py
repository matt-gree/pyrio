"""Static data and constants for the project.

Contents:
  - game_constants      : encoded->decoded lookup tables + superstar modifiers
  - hit_sim_tables      : character-independent lookup tables for the hit sim
  - character_attributes: per-character base (star-OFF) attributes (CSV)
  - stadiums/           : per-stadium boundary coordinate files

Apply ``game_constants.SUPERSTAR_STAT_MODIFIERS`` to the base attributes to get
star-ON values, rather than keeping a separate star-ON table.
"""

from pathlib import Path

from . import game_constants

_DIR = Path(__file__).parent

# Per-character base (star-OFF) attribute table.
CHARACTER_ATTRIBUTES_CSV = _DIR / "character_attributes.csv"

# Directory of per-stadium boundary coordinate files.
STADIUMS_DIR = _DIR / "stadiums"

__all__ = [
    "game_constants",
    "CHARACTER_ATTRIBUTES_CSV",
    "STADIUMS_DIR",
]
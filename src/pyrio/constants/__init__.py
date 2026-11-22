"""Static data and constants for the project.

Contents:
  - game_constants      : encoded->decoded lookup tables for the hit sim
  - hit_sim_tables      : character-independent lookup tables for the hit sim
  - character_data      : AttributeSpec registry + CharacterAttributes (CSV-backed)
  - character_attributes.csv : per-character base (star-OFF) attributes
  - STADIUMS_DIR        : per-stadium boundary coordinate files (in pyrio.geometry)

Use ``character_data.character_attributes(char).with_superstar()`` for star-ON
values rather than keeping a separate star-ON table.
"""

from pathlib import Path

from . import game_constants
from . import character_data
from .character_data import (
    AttributeSpec, ATTRIBUTES, CharacterAttributes, character_attributes,
)

_DIR = Path(__file__).parent

# Per-character base (star-OFF) attribute table.
CHARACTER_ATTRIBUTES_CSV = _DIR.parent / "_data" / "character_attributes.csv"

# Directory of per-stadium boundary coordinate files, named by stadium label.
STADIUMS_DIR = _DIR.parent / "geometry" / "_data" / "outlines"


def stadium_coord_path(stadium_id):
    """Path to a stadium's boundary-coordinate file by encoded stadium id.

    Returns None for stadiums without a boundary file (e.g. Toy Field).
    """
    from .._codes import Stadium

    fname = game_constants.STADIUM_ID_TO_COORD_FILE.get(stadium_id)
    return STADIUMS_DIR / f"{Stadium(stadium_id).label}.txt" if fname else None


__all__ = [
    "game_constants",
    "character_data",
    "AttributeSpec",
    "ATTRIBUTES",
    "CharacterAttributes",
    "character_attributes",
    "CHARACTER_ATTRIBUTES_CSV",
    "STADIUMS_DIR",
    "stadium_coord_path",
]
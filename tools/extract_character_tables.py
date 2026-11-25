"""Write the per-character batting-box and fielding columns of character_attributes.csv.

The columns come straight from the game, through the decomp (mssb-dtk):

  BatterHitbox[54]          src/game/match_setup/character_constants.c
      Vertical Range Front/Back, Bat Offset X/Z, Box Move Speed. Also checked
      against the columns pyrio already had from the same struct (Horizontal
      Range Near/Far, Pitching Height, Trimmed Bat).
  hitByPitchHitboxes[0x60]  character_constants.c, indexed by
  characterStaticIndexes    main.dol 0x800E8558 (.requirementRow, see pitcher.c's
                            hit-by-pitch check)
      Hit By Pitch Depth, Plate Side and Far Side, in centimetres as the game keeps them.
  FielderHitboxConsts[55][8] character_constants.c, scaled by
  charSizeMultipliers       main.dol 0x800E8300, as roster_init.c does
      Dive Range (column 6 of the hitbox row).

Usage:
    python tools/extract_character_tables.py [path/to/mssb-dtk] [--check]

Defaults to ../mssb-dtk. ``--check`` writes nothing and fails if the CSV differs.
"""

from __future__ import annotations

import csv
import io
import pathlib
import re
import struct
import sys
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import Callable

_HERE = pathlib.Path(__file__).resolve().parent
_CSV = _HERE.parent / "src" / "pyrio" / "_data" / "character_attributes.csv"
_CHARACTERS = 54

_CHAR_SIZE_MULTIPLIERS = 0x800E8300  # f32[54][2]
# 6-byte records: variantGroup, trackerIdx, requirementRow, ...
_CHARACTER_STATIC_INDEXES = 0x800E8558


def f32(x: float) -> float:
    value: float = struct.unpack("f", struct.pack("f", x))[0]
    return value


def shortest(x: float) -> str:
    """The shortest decimal that reads back as the same single-precision float."""
    for digits in range(1, 10):
        text = f"{x:.{digits}g}"
        if f32(float(text)) == f32(x):
            return text
    return repr(x)


def c_table(source: str, declaration: str) -> list[str]:
    """The numbers inside a C array initializer, in order."""
    start = source.index(declaration)
    body = source[source.index("{", start) : source.index("};", start)]
    return re.findall(r"0x[0-9A-Fa-f]+|-?\d+(?:\.\d+)?f?", body)


def number(token: str) -> float:
    token = token.rstrip("f")
    return float(int(token, 16)) if token.startswith("0x") else float(token)


def dol_reader(path: pathlib.Path) -> Callable[[int, int], bytes]:
    data = path.read_bytes()
    offsets = struct.unpack(">18I", data[0:72])
    addresses = struct.unpack(">18I", data[72:144])
    sizes = struct.unpack(">18I", data[144:216])

    def read(address: int, length: int) -> bytes:
        for offset, start, size in zip(offsets, addresses, sizes, strict=True):
            if start <= address < start + size:
                return data[offset + address - start : offset + address - start + length]
        raise ValueError(f"{address:#x} is in no section of {path}")

    return read


def extract(dtk: pathlib.Path) -> dict[int, dict[str, str]]:
    source = (dtk / "src/game/match_setup/character_constants.c").read_text(encoding="utf-8")
    read = dol_reader(dtk / "orig/GYQE01/sys/main.dol")

    batter = [number(t) for t in c_table(source, "BatterReachStruct BatterHitbox[54]")]
    hit_by_pitch = [number(t) for t in c_table(source, "u8 hitByPitchHitboxes[0x60]")]
    fielder = [number(t) for t in c_table(source, "s16 FielderHitboxConsts[55][8]")]
    sizes = struct.unpack(">108f", read(_CHAR_SIZE_MULTIPLIERS, 54 * 8))
    indexes = read(_CHARACTER_STATIC_INDEXES, 54 * 6)

    columns: dict[int, dict[str, str]] = {}
    for char in range(_CHARACTERS):
        reach = batter[9 * char : 9 * char + 9]
        near, far, front, back, bat_x, bat_z, move, pitching, trimmed = reach
        row = indexes[6 * char + 2] * 3
        depth, inside, outside = hit_by_pitch[row : row + 3]
        dive = f32(f32(0.01 * fielder[8 * char + 6]) * sizes[2 * char])
        columns[char] = {
            # already in the sheet: checked, not written
            "Horizontal Range Near": shortest(near),
            "Horizontal Range Far": shortest(far),
            "Pitching Height": shortest(pitching),
            "Trimmed Bat": str(int(trimmed)),
            # new
            "Vertical Range Front": shortest(front),
            "Vertical Range Back": shortest(back),
            "Bat Offset X": shortest(bat_x),
            "Bat Offset Z": shortest(bat_z),
            "Box Move Speed": shortest(move),
            "Hit By Pitch Depth": str(int(depth)),
            "Hit By Pitch Plate Side": str(int(inside)),
            "Hit By Pitch Far Side": str(int(outside)),
            "Dive Range": shortest(dive),
        }
    return columns


_CHECKED = ("Horizontal Range Near", "Horizontal Range Far", "Pitching Height", "Trimmed Bat")


def main(argv: list[str]) -> int:
    check = "--check" in argv
    args = [a for a in argv if not a.startswith("--")]
    dtk = pathlib.Path(args[0]) if args else _HERE.parent.parent / "mssb-dtk"
    columns = extract(dtk)

    text = _CSV.read_text(encoding="utf-8")
    rows = list(csv.DictReader(io.StringIO(text)))
    fieldnames = list(rows[0])
    for row in rows:
        new = columns[int(row["CharId"])]
        for name in _CHECKED:
            if float(row[name]) != float(new[name]):
                raise SystemExit(
                    f"{row['Character']}: {name} is {row[name]}, the game has {new[name]}"
                )
        for name, value in new.items():
            if name not in _CHECKED:
                row[name] = value
    for name in columns[0]:
        if name not in fieldnames:
            fieldnames.append(name)

    out = io.StringIO()
    writer = csv.DictWriter(out, fieldnames=fieldnames, lineterminator="\n")
    writer.writeheader()
    writer.writerows(rows)
    if check:
        if out.getvalue() != text:
            print("character_attributes.csv is out of date; run without --check", file=sys.stderr)
            return 1
        print("character_attributes.csv matches the game")
        return 0
    _CSV.write_text(out.getvalue(), encoding="utf-8")
    print(f"wrote {len(rows)} rows to {_CSV.relative_to(_HERE.parent)}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))

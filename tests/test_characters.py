"""Characters, families, the names people type, and per-character attributes."""

import csv
import io
from dataclasses import replace
from importlib.resources import files

import pytest

from pyrio import (
    Ability,
    CaptainStar,
    Character,
    CharacterClass,
    CharacterFamily,
    Hand,
    Stadium,
    StarPitch,
    TeamName,
    UnknownCodeError,
    UnknownNameError,
)
from pyrio._characters import _stems, _variant_forms
from pyrio._names import nicknames, normalize

# --- families ---------------------------------------------------------------

MULTI_VARIANT = {
    CharacterFamily.KOOPA: (Character.KOOPA_G, Character.KOOPA_R),
    CharacterFamily.TOAD: (
        Character.TOAD_R,
        Character.TOAD_B,
        Character.TOAD_Y,
        Character.TOAD_G,
        Character.TOAD_P,
    ),
    CharacterFamily.SHY_GUY: (
        Character.SHY_GUY_R,
        Character.SHY_GUY_B,
        Character.SHY_GUY_Y,
        Character.SHY_GUY_G,
        Character.SHY_GUY_BK,
    ),
    CharacterFamily.PARATROOPA: (Character.PARATROOPA_R, Character.PARATROOPA_G),
    CharacterFamily.PIANTA: (Character.PIANTA_B, Character.PIANTA_R, Character.PIANTA_Y),
    CharacterFamily.NOKI: (Character.NOKI_B, Character.NOKI_R, Character.NOKI_G),
    CharacterFamily.BRO: (Character.BRO_H, Character.BRO_F, Character.BRO_B),
    CharacterFamily.MAGIKOOPA: (
        Character.MAGIKOOPA_B,
        Character.MAGIKOOPA_R,
        Character.MAGIKOOPA_G,
        Character.MAGIKOOPA_Y,
    ),
    CharacterFamily.DRY_BONES: (
        Character.DRY_BONES_GY,
        Character.DRY_BONES_G,
        Character.DRY_BONES_R,
        Character.DRY_BONES_B,
    ),
}


def test_counts():
    assert len(Character) == 54
    assert len(CharacterFamily) == 32


def test_multi_variant_families_are_pinned():
    # Membership comes from the label's "Name(Variant)" form, so a relabelled
    # character would move silently without this.
    assert {f: f.variants for f in CharacterFamily if f.has_variants} == MULTI_VARIANT


def test_every_character_is_in_exactly_one_family():
    members = [c for family in CharacterFamily for c in family.variants]
    assert sorted(members) == list(Character)
    for character in Character:
        assert character in character.family.variants


def test_families_sort_by_first_variant_id():
    assert list(CharacterFamily) == sorted(CharacterFamily, key=lambda f: f.variants[0])
    assert sorted([CharacterFamily.DRY_BONES, CharacterFamily.MARIO]) == [
        CharacterFamily.MARIO,
        CharacterFamily.DRY_BONES,
    ]


@pytest.mark.parametrize("family", list(CharacterFamily), ids=str)
def test_a_family_exposes_only_what_its_variants_share(family: CharacterFamily):
    for variant in family.variants:
        assert variant.attributes.character_class is family.character_class
        assert variant.is_captain is family.is_captain
        assert variant.attributes.abilities == family.abilities


def test_family_constructor_is_strict():
    assert CharacterFamily("shy guy") is CharacterFamily.SHY_GUY
    for value in ("Toad(B)", "toad blue", Character.TOAD_B):
        with pytest.raises(UnknownCodeError):
            CharacterFamily(value)


def test_family_and_character_are_distinct():
    assert Character.MARIO.family is CharacterFamily.MARIO
    assert Character.MARIO != CharacterFamily.MARIO


# --- parsing ----------------------------------------------------------------

# A bare family name (or contested shorthand) names one chosen variant. Decided
# on 2026-11-21 to settle disagreements between pyrio's and RioBot's tables.
DEFAULTS = [
    ("koopa", Character.KOOPA_R),
    ("pianta", Character.PIANTA_R),
    ("noki", Character.NOKI_G),
    ("bones", Character.DRY_BONES_G),
    ("drybones", Character.DRY_BONES_G),
    ("para", Character.PARATROOPA_G),
    ("parag", Character.PARATROOPA_G),
    ("paratroopa", Character.PARATROOPA_G),
    ("pt", Character.TOAD_P),
    ("bb", Character.BRO_B),
    ("toad", Character.TOAD_R),
    ("shyguy", Character.SHY_GUY_R),
    ("magikoopa", Character.MAGIKOOPA_B),
    ("mag", Character.MAGIKOOPA_B),
    ("bro", Character.BRO_H),
]


@pytest.mark.parametrize(("text", "character"), DEFAULTS)
def test_decided_defaults(text: str, character: Character):
    assert Character.parse(text) is character


def test_every_multi_variant_family_declares_its_default():
    for family in MULTI_VARIANT:
        assert family.default in family.variants


@pytest.mark.parametrize(
    ("text", "character"),
    [
        ("Bowser Jr.", Character.BOWSER_JR),
        ("bowser-jr", Character.BOWSER_JR),
        ("BOWSER JR", Character.BOWSER_JR),
        ("Diddy Kong", Character.DIDDY),
        ("Petey Piranha", Character.PETEY),
        ("Toad (Red)", Character.TOAD_R),
        ("toad(r)", Character.TOAD_R),
        ("r!toad", Character.TOAD_R),
        ("toad blue", Character.TOAD_B),
        ("teardrop", Character.TOAD_B),
        ("grey bones", Character.DRY_BONES_GY),
        ("gray dry bones", Character.DRY_BONES_GY),
        ("Hammer Bro", Character.BRO_H),
        ("boomerang bro", Character.BRO_B),
        ("Shy Guy(Bk)", Character.SHY_GUY_BK),
        ("bluemag", Character.MAGIKOOPA_B),
    ],
)
def test_parse(text: str, character: Character):
    assert Character.parse(text) is character


def test_family_parse():
    assert CharacterFamily.parse("koopa") is CharacterFamily.KOOPA
    assert CharacterFamily.parse("bones") is CharacterFamily.DRY_BONES
    assert CharacterFamily.parse("teardrop") is CharacterFamily.TOAD


def test_parse_suggests_on_a_miss():
    with pytest.raises(UnknownNameError) as info:
        Character.parse("peech")
    assert info.value.suggestions == ("Peach",)
    assert "did you mean Peach?" in str(info.value)
    assert isinstance(info.value, UnknownCodeError)


def test_strict_constructor_does_not_take_nicknames():
    with pytest.raises(UnknownCodeError):
        Character("bj")
    with pytest.raises(UnknownCodeError):
        Character("b")


# --- the nickname data ------------------------------------------------------


def test_nickname_data_names_only_real_labels():
    data = nicknames()
    for label in data["characters"]:
        Character(label)
    for label, entry in data["families"].items():
        family = CharacterFamily(label)
        assert family.has_variants, f"{label} has one character; list its names under characters"
        assert Character(entry["default"]).family is family
    for label in data["stadiums"]:
        Stadium(label)


def test_curated_nicknames_are_not_generated_already():
    """A nickname the rules already produce is dead weight in the data file."""
    generated = {normalize(name) for name in _variant_forms()}
    generated |= {normalize(c.label) for c in Character}
    generated |= {normalize(stem) for f in CharacterFamily for stem in _stems(f)}
    curated = [n for names in nicknames()["characters"].values() for n in names]
    assert sorted(n for n in curated if normalize(n) in generated) == []


def test_stadium_nicknames_are_not_labels_or_aliases():
    known = {normalize(s.label) for s in Stadium}
    known |= {normalize(a) for s in Stadium for a in s._aliases if isinstance(a, str)}
    curated = [n for names in nicknames()["stadiums"].values() for n in names]
    assert sorted(n for n in curated if normalize(n) in known) == []


def test_every_name_resolves():
    # Building the index raises if two names collide.
    for label, names in nicknames()["characters"].items():
        for name in names:
            assert Character.parse(name) is Character(label)


# --- attributes -------------------------------------------------------------


def _sheet() -> list[dict[str, str]]:
    text = files("pyrio").joinpath("_data/character_attributes.csv").read_text(encoding="utf-8")
    return list(csv.DictReader(io.StringIO(text)))


def test_attribute_sheet_matches_the_enum():
    assert {int(row["CharId"]): row["Character"] for row in _sheet()} == {
        c.id: c.label for c in Character
    }


def test_sample_attributes():
    bowser = Character.BOWSER.attributes
    assert bowser.character_class is CharacterClass.POWER
    assert bowser.is_captain
    assert bowser.captain_star is CaptainStar.KILLER_BALL
    assert bowser.batting_stance is Hand.LEFT
    assert Character.TOAD_B.attributes.captain_star is None
    assert Character.TOAD_B.attributes.star_pitch is StarPitch.CHANGE_UP
    assert Ability.WALL_JUMP in Character.MARIO.attributes.abilities


def test_superstar():
    base = Character.TOAD_B.attributes
    star = base.with_superstar()
    assert not base.is_superstar
    assert star.is_superstar
    assert star.speed == base.speed + 50  # no ceiling
    assert star.curve == min(base.curve + 50, 100)
    assert star.weight == base.weight  # not boosted
    assert star.with_superstar() is star


def test_captains_are_the_logo_captains():
    captains = {c for c in Character if c.is_captain}
    assert captains == {team.captain for team in TeamName}
    assert len(captains) == 12


def test_batting_box_and_fielding_attributes_come_from_the_game():
    mario = Character.MARIO.attributes
    assert mario.vertical_range_front == -0.2
    assert mario.vertical_range_back == 1.5
    assert mario.bat_offset == (-2.1, -1.0)
    assert mario.box_move_speed == 0.05
    assert (mario.hit_by_pitch_depth, mario.hit_by_pitch_plate_side) == (0.8, 0.7)
    assert mario.hit_by_pitch_far_side == 0.1
    assert mario.dive_range == 1.652  # 140 * 1.18 (Mario's size) / 100
    assert Character.DK.attributes.dive_range == 3.33


def test_bat_reach_depends_on_a_trimmed_bat():
    assert Character.MARIO.attributes.bat_reach == (-0.85, 0.15)
    assert Character.DK.attributes.has_trimmed_bat
    assert Character.DK.attributes.bat_reach == (-0.35, 0.35)


def test_jogging_speed_follows_speed_and_superstar():
    mario = Character.MARIO.attributes
    assert mario.speed == 50
    assert mario.jogging_speed == pytest.approx(0.12)
    assert mario.with_superstar().jogging_speed == pytest.approx(0.133)  # speed 100
    paragoomba = Character.PARAGOOMBA.attributes
    assert paragoomba.speed == 70
    assert paragoomba.jogging_speed == pytest.approx(0.125)
    slow = replace(mario, speed=55)
    assert slow.jogging_speed == pytest.approx((0.12 + 0.124) / 2)

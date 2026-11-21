"""Characters, families, the names people type, and per-character attributes."""

import csv
import io
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
        assert variant.attributes.char_class is family.char_class
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
    assert bowser.char_class is CharacterClass.POWER
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


def test_attributes_match_the_pre_1_0_loader():
    """Transitional: the new records against constants/character_data, until step 7 deletes it."""
    from pyrio.constants.character_data import character_attributes

    for character in Character:
        for new, old in (
            (character.attributes, character_attributes(character.id)),
            (
                character.attributes.with_superstar(),
                character_attributes(character.id).with_superstar(),
            ),
        ):
            assert new.char_class.label == old.char_class
            assert new.is_captain == old.is_captain
            assert {a.label for a in new.abilities} == old.abilities
            assert new.fielding_arm.label == old.fielding_arm
            assert new.batting_stance.label == old.batting_stance
            assert new.horizontal_hit_trajectory.label == old.horizontal_hit_trajectory
            assert new.vertical_hit_trajectory.label == old.vertical_hit_trajectory
            assert (new.captain_star.label if new.captain_star else "") == old.captain_star_pitch
            assert new.star_pitch.label == old.non_captain_star_pitch
            assert new.star_swing.label == old.non_captain_star_hit
            assert new.has_super_curve == old.super_curve
            assert new.has_trimmed_bat == bool(old.trimmed_bat)
            assert new.has_wall_splat == old.wall_splat
            assert new.select_screen_order == old.css_sort
            for name in (
                "weight", "curve_ball_speed", "fast_ball_speed", "curve", "cursed_ball",
                "curve_control", "pitching_height", "throwing_power", "speed", "slap_hit_power",
                "charge_hit_power", "bunting", "slap_contact_size_multiplier",
                "charge_contact_size_multiplier", "horizontal_range_near", "horizontal_range_far",
            ):  # fmt: skip
                assert getattr(new, name) == getattr(old, name), (character, name)

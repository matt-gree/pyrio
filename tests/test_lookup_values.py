import pytest

from pyrio import (
    Character, BaseCharacter, RioValue, Tables, Stadium,
    PitchType, ChargeType, SwingType, ContactType,
    FinalResult, PrimaryContactResult, SecondaryContactResult,
    OutType, StealType, PitchResult,
    Hand, Position, FielderAction, FielderBobble, ManualSelect, TeamName,
    DeadBallReason,
    RioError, RioAPIError, UnknownRioValueError,
    lookup, userInputToCharacter,
)


def test_value_to_value_equality_only():
    c = Character(0, "Mario")
    assert c == Character(0, "Mario")     # same type + id
    assert c != Character(1, "Luigi")
    assert c != 0                         # never equal to a raw int
    assert c != "Mario"                   # never equal to a raw str
    assert c != True


def test_explicit_conversions():
    c = Character(0, "Mario")
    assert int(c) == 0
    assert str(c) == "Mario"
    assert f"{c}" == "Mario"
    assert c.id == 0 and c.name == "Mario"
    assert repr(c) == "Character(0, 'Mario')"


def test_cross_type_inequality():
    # same id, different value-object type -> not equal
    assert Character(0, "Mario") != RioValue(0, "Mario")


def test_hash_and_set_membership_are_value_based():
    assert hash(Character(5, "Daisy")) == hash(Character(5, "Daisy"))
    assert Character(5, "Daisy") in {Character(5, "Daisy")}
    assert Character(5, "Daisy") not in {5}        # not interchangeable with int
    assert 5 not in {Character(5, "Daisy")}


def test_character_properties_variant():
    pianta = Character.from_raw(0x16)  # Pianta(R)
    assert pianta.name == "Pianta(R)"
    assert pianta.name_no_variant == "Pianta"
    assert pianta.hex == "0x16"
    # char_class / is_captain now live on the attribute record.
    assert pianta.attributes.char_class == "Power"
    assert pianta.attributes.is_captain is False


def test_character_properties_captain():
    mario = Character.from_raw("mario")
    assert mario.id == 0
    assert mario.attributes.char_class == "Balance"
    assert mario.attributes.is_captain is True


def test_lookup_character_by_id_name_and_alias():
    assert Character.from_raw(5) == Character.from_raw("Daisy")
    assert Character.from_raw("daisy").id == 5  # case-insensitive alias


def test_lookup_character_rejects_unknown():
    with pytest.raises(ValueError):
        Character.from_raw("not a character")
    with pytest.raises(ValueError):
        Character.from_raw(999)


def test_exception_hierarchy():
    # RioError is the root of everything pyrio deliberately raises;
    # UnknownRioValueError dual-inherits so legacy ValueError handlers survive.
    assert issubclass(RioAPIError, RioError)
    assert issubclass(UnknownRioValueError, RioError)
    assert issubclass(UnknownRioValueError, ValueError)


def test_unknown_values_raise_unknown_rio_value_error():
    with pytest.raises(UnknownRioValueError):
        Character.from_raw("not a character")
    with pytest.raises(UnknownRioValueError):
        Character.from_raw(999)
    with pytest.raises(UnknownRioValueError):
        Stadium.from_raw("Not A Stadium")
    with pytest.raises(UnknownRioValueError):
        userInputToCharacter("not a character")
    with pytest.raises(UnknownRioValueError):
        lookup("not_a_table", 0)


def test_unknown_value_caught_by_value_error_and_rio_error():
    # Both the pre-1.0 ``except ValueError`` contract and the new
    # ``except RioError`` root must catch resolution failures.
    with pytest.raises(ValueError):
        Character.from_raw("not a character")
    with pytest.raises(RioError):
        Character.from_raw("not a character")
    with pytest.raises(ValueError):
        Stadium.from_raw(Character.from_raw("Mario"))   # cross-type resolution
    with pytest.raises(RioError):
        Stadium.from_raw(Character.from_raw("Mario"))
    with pytest.raises(ValueError):
        PitchType.from_raw("Knuckleball")
    with pytest.raises(RioError):
        PitchType.from_raw("Knuckleball")


def test_lookup_stadium_by_id_name_and_legacy():
    s = Stadium.from_raw(1)
    assert isinstance(s, Stadium)
    assert s.id == 1 and s.name == "Bowser Castle"
    assert Stadium.from_raw("Bowser Castle") == s        # by name
    assert Stadium.from_raw("Bowser's Castle") == s      # legacy name alias
    assert Stadium.from_raw("1") == s                    # digit string


def test_lookup_stadium_rejects_unknown():
    with pytest.raises(ValueError):
        Stadium.from_raw("Not A Stadium")


def test_from_raw_is_idempotent_on_its_own_type():
    # Re-feeding a value object to its own from_raw returns it unchanged, so
    # code holding value objects can pass them wherever raw ids/names go.
    mario = Character.from_raw("Mario")
    assert Character.from_raw(mario) is mario
    stadium = Stadium.from_raw(1)
    assert Stadium.from_raw(stadium) is stadium
    toad = BaseCharacter.from_raw("Toad")
    assert BaseCharacter.from_raw(toad) is toad


def test_from_raw_rejects_other_value_types():
    # A value object of a different type is an error, not an accidental
    # name-string lookup (a BaseCharacter names no single Character variant).
    with pytest.raises(ValueError):
        Stadium.from_raw(Character.from_raw("Mario"))
    with pytest.raises(ValueError):
        Character.from_raw(BaseCharacter.from_raw("Toad"))


def test_base_character_from_raw_accepts_character():
    # Character -> BaseCharacter is a well-defined narrowing (drop the variant).
    assert BaseCharacter.from_raw(Character.from_raw("Toad(B)")) == BaseCharacter.from_raw("Toad")


def test_team_name_captain_and_role():
    # Logo ids encode the captain (id // 4) and role (id % 4) structurally.
    fireballs = TeamName.from_raw("Mario Fireballs")
    assert fireballs.captain == Character.from_raw("Mario")
    assert fireballs.role == "class_team"
    assert TeamName.from_raw("Mario Sunshines").role == "signature"
    assert TeamName.from_raw("Mario Heroes").role == "default"
    assert TeamName.from_raw("Jr Fangs").captain == Character.from_raw("Bowser Jr")
    # Every logo's captain is a captain, and each captain owns exactly 4 logos.
    per_captain = {}
    for logo_id in Tables.TEAM_NAME:
        team = TeamName.from_raw(logo_id)
        assert team.captain.attributes.is_captain
        per_captain.setdefault(team.captain, []).append(team)
    assert all(len(teams) == 4 for teams in per_captain.values())
    assert len(per_captain) == 12


def test_input_direction_matches_stickvec_bitmask():
    # Canonical "StickVec" decoder: 0x1 Left, 0x2 Right, 0x4 Down, 0x8 Up, '+'-joined.
    def stickvec(value):
        parts = []
        if value & 0x1:
            parts.append("Left")
        if value & 0x2:
            parts.append("Right")
        if value & 0x4:
            parts.append("Down")
        if value & 0x8:
            parts.append("Up")
        return "+".join(parts)

    assert Tables.INPUT_DIRECTION == {v: stickvec(v) for v in range(16)}


def test_pitch_event_type_factories():
    assert isinstance(PitchType.from_raw(0), PitchType)
    assert PitchType.from_raw(0).name == "Curve"
    assert PitchType.from_raw(0) == PitchType.from_raw("Curve")   # id == name input
    assert ChargeType.from_raw(0).name == "N/A"
    assert SwingType.from_raw(1).name == "Slap"
    assert ContactType.from_raw(255).name == "Miss"
    assert ContactType.from_raw("Perfect").id == 2


def test_value_factories_pass_through_none():
    assert PitchType.from_raw(None) is None
    assert ChargeType.from_raw(None) is None
    assert SwingType.from_raw(None) is None
    assert ContactType.from_raw(None) is None


def test_factories_tolerate_capitalization_drift():
    # Decoded client casing may drift; resolution is case-insensitive and the
    # value object always carries the canonical name.
    assert PitchType.from_raw("changeup").name == "ChangeUp"
    assert PitchType.from_raw("CURVE") == PitchType.from_raw("Curve")
    assert ContactType.from_raw("perfect").name == "Perfect"
    assert Stadium.from_raw("bowser CASTLE").name == "Bowser Castle"


def test_result_type_factories():
    assert isinstance(OutType.from_raw(1), OutType)
    assert FinalResult.from_raw(7).name == "Single"
    assert FinalResult.from_raw(7) == FinalResult.from_raw("Single")
    assert PrimaryContactResult.from_raw(1).name == "Foul"
    assert SecondaryContactResult.from_raw(7).name == "Single"
    assert OutType.from_raw(1).name == "Caught"
    assert StealType.from_raw(2).name == "Normal"
    assert PitchResult.from_raw(0).name == "HBP"
    assert FinalResult.from_raw(None) is None


def test_roster_and_fielding_factories():
    assert Hand.from_raw(0).name == "Right"
    assert Hand.from_raw(1).name == "Left"
    assert Hand.from_raw("Left").id == 1            # canonical 0=Right, 1=Left
    assert Position.from_raw(0).name == "P"
    assert Position.from_raw("RF").id == 8
    assert ManualSelect.from_raw(1).name == "Pitcher"
    assert TeamName.from_raw(2).name == "Mario Fireballs"
    assert TeamName.from_raw("Jr Fangs").id == 47
    # round-trip without hardcoding ids for the action/bobble tables
    assert isinstance(FielderAction.from_raw("Sliding"), FielderAction)
    assert FielderAction.from_raw("Sliding").name == "Sliding"
    assert isinstance(FielderBobble.from_raw("Fumble"), FielderBobble)
    assert FielderBobble.from_raw("Fumble").name == "Fumble"
    assert Hand.from_raw(None) is None
    assert isinstance(DeadBallReason.from_raw(1), DeadBallReason)
    assert DeadBallReason.from_raw(1).name == "Home Run"
    assert DeadBallReason.from_raw("Foul Ball").id == 2
    assert DeadBallReason.from_raw(None) is None


# ---------------------------------------------------------------------------
# Regression: lookup() was case-insensitive in only one direction
# ---------------------------------------------------------------------------

def test_lookup_is_case_insensitive_in_both_directions():
    """id->name matched the raw term, so a lowercased key fell through.

    lookup(CHAR_NAME, 'mario') resolved (name->id, which lowercased) but
    lookup(SIMPLIFIED_NAME, 'mario') returned the "Invalid" sentinel, because
    there the term matches a *key*, and the key branch did not lowercase.
    """
    assert lookup(Tables.CHAR_NAME, "mario") == 0
    assert lookup(Tables.SIMPLIFIED_NAME, "mario") == "Mario"
    assert lookup(Tables.SIMPLIFIED_NAME, "TOAD(R)") == "Toad"
    assert lookup(Tables.STADIUM, "bowser castle") == 1
    # id -> name still wins over name -> id, and ints are untouched
    assert lookup(Tables.CHAR_NAME, 0) == "Mario"
    assert lookup(Tables.CHAR_NAME, "0") == "Mario"
    # a genuine miss still reports the sentinel
    assert str(lookup(Tables.CHAR_NAME, 999)).startswith("Invalid")
    assert str(lookup(Tables.CHAR_NAME, "Mendelbrot")).startswith("Invalid")


def test_lookup_handles_non_str_keys_and_values():
    # HAND_BOOL is keyed on bools; POSITION has a None key whose value is "None"
    assert lookup(Tables.HAND_BOOL, True) == "Left"
    assert lookup(Tables.HAND_BOOL, "true") == "Left"
    assert lookup(Tables.POSITION, "None") == "None"


# ---------------------------------------------------------------------------
# Regression: RioValue accepted an id/name pair its table contradicts
# ---------------------------------------------------------------------------

def test_value_object_rejects_inconsistent_pair():
    """Equality is by (type, id), so a wrong name compared equal to the right
    one and silently misreported itself under str()."""
    with pytest.raises(UnknownRioValueError):
        Character(0, "Bowser")
    with pytest.raises(UnknownRioValueError):
        Stadium(1, "Mario Stadium")
    with pytest.raises(UnknownRioValueError):
        Character(999, "Mario")


def test_value_object_accepts_consistent_pair():
    assert Character(0, "Mario").name == "Mario"
    assert Stadium(1, "Bowser Castle").id == 1
    assert Position(None, "None").name == "None"      # None is a real key
    # the bare base class has no table and stays unvalidated on purpose
    assert RioValue(0, "Mario").name == "Mario"


def test_from_raw_still_builds_every_value_class():
    # from_raw resolves to the canonical name first, so validation is a no-op
    assert Character.from_raw("bowser") == Character(9, "Bowser")
    assert Stadium.from_raw("Bowser's Castle") == Stadium(1, "Bowser Castle")
    for cls, table in [
        (PitchType, Tables.PITCH_TYPE), (ChargeType, Tables.CHARGE_TYPE),
        (SwingType, Tables.TYPE_OF_SWING), (ContactType, Tables.CONTACT_TYPE),
        (FinalResult, Tables.FINAL_RESULT), (OutType, Tables.OUT_TYPE),
        (PrimaryContactResult, Tables.PRIMARY_CONTACT_RESULT),
        (SecondaryContactResult, Tables.SECONDARY_CONTACT_RESULT),
        (StealType, Tables.STEAL_TYPE), (PitchResult, Tables.PITCH_RESULT),
        (Hand, Tables.HAND), (Position, Tables.POSITION),
        (FielderAction, Tables.FIELDER_ACTIONS),
        (FielderBobble, Tables.FIELDER_BOBBLES),
        (ManualSelect, Tables.MANUAL_SELECT), (TeamName, Tables.TEAM_NAME),
        (DeadBallReason, Tables.DEAD_BALL_REASON),
    ]:
        for raw_id in table:
            if raw_id is None:
                continue
            assert cls.from_raw(raw_id).id == raw_id


# ---------------------------------------------------------------------------
# Project Rio 2.3.0 result-table corrections (+ PR #170 for id 12)
# ---------------------------------------------------------------------------

def test_final_result_5_and_6_are_the_corrected_way_round():
    """The game assigns 5 when Hit_VerticalAngle <= 160 (the flat, low-apex
    ball) and 6 above it, so 5 is the line drive. Rio <= 2.2.0 had the two
    labels swapped; pyrio followed it until 2.3.0."""
    assert Tables.FINAL_RESULT[5] == "Caught line-drive"
    assert Tables.FINAL_RESULT[6] == "Caught"
    assert FinalResult.from_raw(5).name == "Caught line-drive"
    assert FinalResult.from_raw(6).name == "Caught"
    assert FinalResult.from_raw("Caught").id == 6
    assert FinalResult.from_raw("Caught line-drive").id == 5


def test_result_tables_match_2_3_0():
    for table in (Tables.FINAL_RESULT, Tables.SECONDARY_CONTACT_RESULT):
        assert table[11] == "Error"
        assert table[12] == "Batter safe, throw elsewhere"
    # 0x10 is unreachable as a secondary result (they are only copied up to
    # DOUBLE_PLAY), so 2.3.0 dropped it there; it survives in FINAL_RESULT.
    assert 16 not in Tables.SECONDARY_CONTACT_RESULT
    assert Tables.FINAL_RESULT[16] == "Foul catch"
    assert Tables.SECONDARY_CONTACT_RESULT[255] == "None"
    with pytest.raises(UnknownRioValueError):
        SecondaryContactResult.from_raw(16)


def test_charge_type_has_charged_captain_star():
    """id 1 was missing, so from_raw(1) raised -- which took out EventSearch
    construction for the whole file, since its guard catches only KeyError."""
    assert Tables.CHARGE_TYPE[1] == "Charged Captain Star"
    assert ChargeType.from_raw(1).name == "Charged Captain Star"
    assert ChargeType.from_raw("Charged Captain Star").id == 1


def test_legacy_result_labels_still_resolve():
    """Decoded files from Rio <= 2.2.0 carry the old labels for ids 11 and 12.
    Those were renamed at a stable id, so they resolve unambiguously."""
    for cls in (FinalResult, SecondaryContactResult):
        assert cls.from_raw("Error - Input").id == 11
        assert cls.from_raw("Error - Chem").id == 12
        # and the canonical spellings, obviously
        assert cls.from_raw("Error").id == 11
        assert cls.from_raw("Batter safe, throw elsewhere").id == 12

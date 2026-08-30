"""HudObj.game_over — MSB's end-of-game rule read off a single HUD frame.

The HUD has no end-of-game event: the frame recording the final out (or the
winning run) is simply the last one written. So the predicate is stateless, and
these tests are frames rather than sequences.

Regulation and mercy are the same rule at two margins — an unnecessary
half-inning is not played, and the team batting second always gets to respond —
so both are exercised through the same three boundaries: after the top, after
the bottom, and mid-half for a walk-off.
"""
import pytest

from pyrio.stat_file_parser import MERCY_MARGIN, HudObj


def frame(*, inning=1, half=0, outs=0, outs_in_play=0, away=0, home=0,
          innings_selected=9, first_batting=0):
    """A HUD frame carrying only the fields game_over reads."""
    return HudObj({
        "Event Num": "1",
        "Inning": inning,
        "Half Inning": half,
        "Outs": outs,
        "Num Outs During Play": outs_in_play,
        "Away Score": away,
        "Home Score": home,
        "Innings Selected": innings_selected,
        "First Batting Team": first_batting,
    })


# The third out of a half-inning: Outs (before the play) + outs the play made.
THIRD_OUT = {"outs": 2, "outs_in_play": 1}


# ----- regulation -----------------------------------------------------------

def test_a_fresh_game_is_not_over():
    assert frame().game_over() is False


def test_mid_game_third_out_is_not_the_end():
    assert frame(inning=4, half=1, away=3, home=1, **THIRD_OUT).game_over() is False


def test_the_bottom_is_skipped_when_the_team_batting_second_leads():
    # Top of the 9th ends with home ahead — the bottom is unnecessary.
    assert frame(inning=9, half=0, away=6, home=14, **THIRD_OUT).game_over() is True


def test_the_bottom_is_played_when_the_team_batting_FIRST_leads():
    # Away ahead after the top of the 9th: home still gets to respond.
    assert frame(inning=9, half=0, away=14, home=6, **THIRD_OUT).game_over() is False


def test_regulation_ends_after_the_bottom_half():
    assert frame(inning=9, half=1, away=7, home=4, **THIRD_OUT).game_over() is True


def test_a_regulation_tie_goes_to_extras():
    assert frame(inning=9, half=1, away=5, home=5, **THIRD_OUT).game_over() is False


def test_extra_innings_end_the_same_way():
    assert frame(inning=11, half=1, away=5, home=6, **THIRD_OUT).game_over() is True


# ----- walk-off -------------------------------------------------------------

def test_a_walk_off_ends_play_without_a_third_out():
    # Bottom of the 9th, home takes the lead, nobody out.
    assert frame(inning=9, half=1, outs=1, away=5, home=6).game_over() is True


def test_the_bottom_of_the_ninth_continues_while_home_trails():
    assert frame(inning=9, half=1, outs=1, away=6, home=5).game_over() is False


def test_a_tie_in_the_bottom_of_the_ninth_is_not_a_walk_off():
    assert frame(inning=9, half=1, outs=1, away=5, home=5).game_over() is False


# ----- mercy ----------------------------------------------------------------

def test_mercy_ends_an_early_game_after_the_bottom_half():
    assert frame(inning=3, half=1, away=0, home=MERCY_MARGIN,
                 **THIRD_OUT).game_over() is True


def test_mercy_applies_to_the_team_batting_first_too_after_the_bottom():
    assert frame(inning=3, half=1, away=MERCY_MARGIN, home=0,
                 **THIRD_OUT).game_over() is True


def test_mercy_skips_the_bottom_for_the_team_batting_second():
    assert frame(inning=3, half=0, away=0, home=MERCY_MARGIN,
                 **THIRD_OUT).game_over() is True


def test_the_team_batting_first_leading_by_the_margin_still_lets_home_respond():
    # THE ASYMMETRY: away up 10 after the top does NOT end it. This is the same
    # "chance to respond" that makes the 9th play its bottom half.
    assert frame(inning=3, half=0, away=MERCY_MARGIN, home=0,
                 **THIRD_OUT).game_over() is False


def test_one_run_short_of_the_margin_is_not_a_mercy():
    assert frame(inning=3, half=1, away=0, home=MERCY_MARGIN - 1,
                 **THIRD_OUT).game_over() is False


def test_the_margin_is_inclusive():
    """`> 10` was the dead isMercy's test and would miss a game mercied by
    exactly the rule's margin."""
    assert frame(inning=3, half=1, away=0, home=MERCY_MARGIN,
                 **THIRD_OUT).game_over() is True


def test_mercy_applies_from_the_first_inning():
    assert frame(inning=1, half=1, away=0, home=MERCY_MARGIN,
                 **THIRD_OUT).game_over() is True


def test_mercy_needs_the_half_to_be_over():
    # Mid-inning 10-run lead: answers late (at the third out) rather than
    # calling a game that may still be being played.
    assert frame(inning=3, half=1, outs=1, away=0,
                 home=MERCY_MARGIN).game_over() is False


# ----- batting order, not away/home ------------------------------------------

def test_sides_resolve_through_first_batting_team():
    """With HOME batting first, the responding side is AWAY — so an away lead
    after the top is what skips the bottom."""
    assert frame(inning=9, half=0, away=14, home=6,
                 first_batting=1, **THIRD_OUT).game_over() is True
    assert frame(inning=9, half=0, away=6, home=14,
                 first_batting=1, **THIRD_OUT).game_over() is False


# ----- degenerate frames ------------------------------------------------------

@pytest.mark.parametrize("bad", [None, 0])
def test_a_frame_without_innings_selected_is_never_over(bad):
    assert frame(inning=9, half=1, away=7, home=4,
                 innings_selected=bad, **THIRD_OUT).game_over() is False


def test_an_unreadable_batting_order_is_never_over():
    assert frame(inning=9, half=1, away=7, home=4,
                 first_batting=-1, **THIRD_OUT).game_over() is False


def test_a_play_recording_more_outs_than_the_half_had_left_still_ends_it():
    """`inning_end` is >= 3, not == 3: a predicate that answers False for an
    over-count fails silently, and nothing downstream can tell that from 'the
    half is not over'."""
    assert frame(inning=9, half=1, outs=2, outs_in_play=2,
                 away=7, home=4).game_over() is True

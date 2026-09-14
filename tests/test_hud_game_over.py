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
          innings_selected=9, first_batting=0, event="1b"):
    """A HUD frame carrying only the fields game_over reads.

    ``event`` defaults to a RESOLVED event num ("1b"). Rio writes two frames
    per event and only the resolved one describes a completed play; this helper
    defaulted to the in-flight spelling ("1"), so every frame here was one the
    predicate must decline to read a half-inning boundary off — which is how
    the double-counted out below went untested.
    """
    return HudObj({
        "Event Num": event,
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


# ----- in-flight frames -------------------------------------------------------
#
# `Outs` is the half's count and `Num Outs During Play` is the current play's,
# so only a resolved frame ("…b") may add them. In flight, `Outs` has already
# absorbed the last play while `Num Outs During Play` still describes it.

IN_FLIGHT = {"event": "43"}


def test_an_in_flight_frame_does_not_double_count_the_last_out():
    """THE BUG: two outs, a batter at the plate, and a 10-run margin read as a
    mercy — so the board flipped Final/Live with every HUD write."""
    assert frame(inning=6, half=1, outs=2, outs_in_play=1,
                 away=12, home=1, innings_selected=7,
                 **IN_FLIGHT).game_over() is False


def test_the_same_frame_resolved_is_a_mercy():
    assert frame(inning=6, half=1, outs=2, outs_in_play=1,
                 away=12, home=1, innings_selected=7).game_over() is True


def test_an_in_flight_frame_still_sees_a_walk_off():
    """The walk-off branch asks about the score, not the outs, so it answers on
    any frame — a run that ends a game does not wait for a resolution."""
    assert frame(inning=9, half=1, outs=1, away=5, home=6,
                 **IN_FLIGHT).game_over() is True


def test_an_in_flight_frame_at_the_end_of_regulation_is_not_over():
    assert frame(inning=9, half=1, outs=2, outs_in_play=1, away=7, home=4,
                 **IN_FLIGHT).game_over() is False


# ----- batting order, not away/home ------------------------------------------
#
# `Half Inning` is the BATTING TEAM's away/home id, not top/bottom: with HOME
# batting first, half 1 is the TOP and half 0 is the bottom.

HOME_FIRST = {"first_batting": 1}


def test_the_top_is_the_first_batting_teams_half():
    """Home bats first, so the responding side is AWAY: an away lead after the
    top skips the bottom, and a home lead does not."""
    assert frame(inning=9, half=1, away=14, home=6,
                 **HOME_FIRST, **THIRD_OUT).game_over() is True
    assert frame(inning=9, half=1, away=6, home=14,
                 **HOME_FIRST, **THIRD_OUT).game_over() is False


def test_the_first_batting_team_still_gets_its_whole_half():
    """THE INVERSION: half 1 read as "the bottom" put the walk-off branch —
    which has no third-out gate — over the whole of HOME's half, so a game with
    away ahead in regulation was Final from the first pitch of the top."""
    assert frame(inning=9, half=1, outs=1, away=7, home=4,
                 **HOME_FIRST).game_over() is False


def test_the_bottom_is_the_second_batting_teams_half():
    # Away bats second here, so a third out in half 0 ends a decided game.
    assert frame(inning=9, half=0, away=6, home=14,
                 **HOME_FIRST, **THIRD_OUT).game_over() is True


def test_a_walk_off_belongs_to_whoever_bats_second():
    # Away takes the lead in its own half — the mirror of the home walk-off.
    assert frame(inning=9, half=0, outs=1, away=6, home=5,
                 **HOME_FIRST).game_over() is True
    assert frame(inning=9, half=0, outs=1, away=5, home=6,
                 **HOME_FIRST).game_over() is False


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

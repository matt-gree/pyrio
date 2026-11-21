"""pyrio.ratings: Glicko-2 with Rio web's parameters, pinned against the server.

The expected values below were produced by running Rio web's own rating code,
``app/glicko2.py`` in ProjectRio-web at commit ``d4bf233``, imported straight from
a checkout in a throwaway script: ``Player(rating, rd, vol).update_player(...)``,
the call ``calc_elo`` makes (``app/views/populate_db.py:1140-1144``). Each tuple is
``(player, [(opponent rating, opponent rd, score), ...], (rating, rd, vol))``.
Opponents' volatilities don't enter the update.
"""

import math

import pytest

from pyrio.ratings import Rating, update, win_probability

# Rio web's app/glicko2.py, unmodified.
SERVER = [
    (
        (1500, 300, 0.06),
        [(1500, 300, 1)],
        (1634.9820026067493, 254.46918206051373, 0.0599999991651172),
    ),
    (
        (1500, 300, 0.06),
        [(1500, 300, 0)],
        (1365.0179973932507, 254.46918206051373, 0.0599999991651172),
    ),
    (
        (1620, 85, 0.06),
        [(1480, 140, 1)],
        (1631.9595103138877, 83.79519130448318, 0.059998729685518164),
    ),
    (
        (1620, 85, 0.06),
        [(1480, 140, 0)],
        (1595.0216897506436, 83.79525781318914, 0.06000208719488284),
    ),
    (
        (1480, 140, 0.06),
        [(1620, 85, 1)],
        (1546.3501468496816, 131.98961124628204, 0.06000316508037847),
    ),
    (
        (1350, 45, 0.059),
        [(1352, 47, 1)],
        (1355.9947301617858, 45.759202582972044, 0.05899961492709206),
    ),
    (
        (1850, 60, 0.0601),
        [(1200, 250, 1)],
        (1850.8438397654336, 60.791466942389334, 0.0600996596197031),
    ),
    (
        (1850, 60, 0.0601),
        [(1200, 250, 0)],
        (1834.1785515575027, 60.7916437248929, 0.0601056278264964),
    ),
    (
        (1000, 200, 0.03),
        [(2200, 30, 1)],
        (1228.8315058233616, 199.93266879995818, 0.030001639552528672),
    ),
    (
        (2200, 30, 0.09),
        [(1850, 30, 0)],
        (2194.2421197261774, 33.76357259409583, 0.09000311383704587),
    ),
    (
        (1500, 350, 0.06),
        [(1700, 300, 1), (1400, 60, 0)],
        (1463.5809700796017, 228.13788806178093, 0.0599957003691623),
    ),
    (
        (1550, 120, 0.06),
        [(1500, 300, 1), (1600, 90, 0), (1580, 75, 1)],
        (1578.4186449940014, 106.28537773993452, 0.05999473890884947),
    ),
]

# The same code with the volatility step's mu**2 replaced by phi**2, as the paper
# has it: ``self.__rating`` became ``self.__rd`` in the three ``math.pow(..., 2)``
# terms of ``_newVol`` (lines 102, 106 and 108). Nothing else changed, so this
# isolates the solver: Rio web's Newton iteration against pyrio's Illinois step.
SERVER_WITH_PHI = [
    (
        (1500, 300, 0.06),
        [(1500, 300, 1)],
        (1634.9820012146188, 254.46918074828562, 0.05999964205839072),
    ),
    (
        (1500, 300, 0.06),
        [(1500, 300, 0)],
        (1365.0179987853812, 254.46918074828562, 0.05999964205839072),
    ),
    (
        (1620, 85, 0.06),
        [(1480, 140, 1)],
        (1631.9595102597104, 83.79519111468522, 0.05999872010382404),
    ),
    (
        (1620, 85, 0.06),
        [(1480, 140, 0)],
        (1595.0216864937067, 83.79526327624568, 0.060002362974078974),
    ),
    (
        (1480, 140, 0.06),
        [(1620, 85, 1)],
        (1546.350136647798, 131.98960109903481, 0.06000221844348532),
    ),
    (
        (1350, 45, 0.059),
        [(1352, 47, 1)],
        (1355.9947337818521, 45.75921639938383, 0.05899998237817125),
    ),
    (
        (1850, 60, 0.0601),
        [(1200, 250, 1)],
        (1850.843839734829, 60.791465839989726, 0.06009962240070413),
    ),
    (
        (1850, 60, 0.0601),
        [(1200, 250, 0)],
        (1834.1785295762725, 60.79168595473891, 0.06010705342805539),
    ),
    (
        (1000, 200, 0.03),
        [(2200, 30, 1)],
        (1228.8315060647137, 199.93266890539428, 0.030001662898604915),
    ),
    (
        (2200, 30, 0.09),
        [(1850, 30, 0)],
        (2194.241384242447, 33.765728922830675, 0.09003012678713944),
    ),
    (
        (1500, 350, 0.06),
        [(1700, 300, 1), (1400, 60, 0)],
        (1463.5809689730722, 228.1378915275685, 0.05999812382001683),
    ),
    (
        (1550, 120, 0.06),
        [(1500, 300, 1), (1600, 90, 0), (1580, 75, 1)],
        (1578.4186483543301, 106.28538402372827, 0.05999534739355513),
    ),
]


def _update(player: tuple[float, float, float], games: list[tuple[float, float, int]]) -> Rating:
    return update(Rating(*player), [(Rating(r, rd), score) for r, rd, score in games])


@pytest.mark.parametrize(("player", "games", "expected"), SERVER_WITH_PHI)
def test_matches_the_server_arithmetic(player, games, expected):
    # Tight: the two root-finders agree to within the paper's tolerance.
    got = _update(player, games)
    assert got.rating == pytest.approx(expected[0], abs=1e-5)
    assert got.rd == pytest.approx(expected[1], abs=1e-5)
    assert got.volatility == pytest.approx(expected[2], abs=1e-7)


@pytest.mark.parametrize(("player", "games", "expected"), SERVER)
def test_close_to_the_unmodified_server(player, games, expected):
    # The server's mu**2 slip moves its volatility by up to 3e-5 for one game, and
    # rating and rd by under 0.003 (worst over a 7,776-case grid: 7.4e-4, 2.2e-3
    # and 2.7e-5, all in the 2200-vs-1850 row). The server stores rating and rd
    # as integers, so the visible difference is at most an occasional point.
    got = _update(player, games)
    assert got.rating == pytest.approx(expected[0], abs=1e-3)
    assert got.rd == pytest.approx(expected[1], abs=2.5e-3)
    assert got.volatility == pytest.approx(expected[2], abs=3e-5)


def test_glickman_worked_example():
    # Glickman, "Example of the Glicko-2 system" (revised 2012), section 3: a 1500
    # (RD 200, volatility 0.06) player beats a 1400 and loses to a 1550 and a 1700,
    # with tau 0.5. The paper gives mu' = -0.2069, phi' = 0.8722 and sigma' = 0.05999
    # on Glicko-2's scale; its r' = 1464.06 and RD' = 151.52 are those rounded
    # values converted back, so the check is on the scale the paper rounds in.
    got = update(
        Rating(1500, 200, 0.06),
        [(Rating(1400, 30), 1), (Rating(1550, 100), 0), (Rating(1700, 300), 0)],
    )
    assert (got.rating - 1500) / 173.7178 == pytest.approx(-0.2069, abs=5e-5)
    assert got.rd / 173.7178 == pytest.approx(0.8722, abs=5e-5)
    assert got.volatility == pytest.approx(0.05999, abs=1e-5)


@pytest.mark.parametrize(
    ("player", "games"),
    [
        # Rio web's Newton loop never ends on this one: it alternates forever.
        (
            (1416.849620202383, 207.71884079084515, 0.1467236472838479),
            [(1973.7126947306142, 111.5724191088662, 1)],
        ),
        # And raises OverflowError on this one, starting its iteration from x = 0.
        (
            (815.6641138168283, 186.58711446834593, 0.05818145853200542),
            [
                (2574.551428801871, 149.63114066255167, 1),
                (2254.3636464713745, 43.45225594630422, 1),
                (2206.5495365233796, 56.59416187788518, 1),
            ],
        ),
    ],
)
def test_converges_where_the_server_loop_does_not(player, games):
    after = _update(player, games)
    assert after.rating > player[0]
    assert all(map(math.isfinite, (after.rating, after.rd, after.volatility)))


def test_new_player_is_the_server_default():
    # app/consts.py:43-45 in ProjectRio-web.
    assert Rating() == Rating(1500, 300, 0.06)


def test_winner_and_loser_move_symmetrically():
    a, b = Rating(), Rating()
    winner, loser = update(a, [(b, 1)]), update(b, [(a, 0)])
    assert winner.rating - 1500 == pytest.approx(1500 - loser.rating)
    assert winner.rd == loser.rd


def test_booleans_are_scores():
    a, b = Rating(1620, 85), Rating(1480, 140)
    assert update(a, [(b, True)]) == update(a, [(b, 1)])
    assert update(a, [(b, False)]) == update(a, [(b, 0.0)])


def test_no_games_only_grows_the_deviation():
    before = Rating(1650, 80, 0.06)
    after = update(before, [])
    scale = 173.7178
    assert after.rating == before.rating
    assert after.volatility == before.volatility
    assert after.rd == pytest.approx(math.sqrt((80 / scale) ** 2 + 0.06**2) * scale)


def test_score_outside_zero_to_one_is_rejected():
    with pytest.raises(ValueError, match="score"):
        update(Rating(), [(Rating(), 2)])


@pytest.mark.parametrize(
    ("fields", "match"),
    [
        ({"rd": 0}, "rd"),
        ({"rd": -10}, "rd"),
        ({"volatility": 0}, "volatility"),
        ({"rating": math.nan}, "rating"),
        ({"rd": math.inf}, "rd"),
    ],
)
def test_invalid_rating_is_rejected(fields, match):
    with pytest.raises(ValueError, match=match):
        Rating(**fields)


def test_rating_is_frozen():
    with pytest.raises(AttributeError):
        Rating().rating = 1600  # type: ignore[misc]


def test_win_probability_even_match():
    assert win_probability(Rating(1600, 50), Rating(1600, 200)) == pytest.approx(0.5)


def test_win_probabilities_add_to_one():
    a, b = Rating(1825, 70), Rating(1555, 200)
    assert win_probability(a, b) + win_probability(b, a) == pytest.approx(1)


def test_win_probability_matches_glicko_formula():
    # Glickman, "The Glicko system" (1995): on the 1500 scale with q = ln 10 / 400,
    # E = 1 / (1 + 10 ** (-g(sqrt(RD_A**2 + RD_B**2)) * (r_A - r_B) / 400)).
    q = math.log(10) / 400
    g = 1 / math.sqrt(1 + 3 * q**2 * (70**2 + 68**2) / math.pi**2)
    expected = 1 / (1 + 10 ** (-g * (1825 - 1555) / 400))
    assert win_probability(Rating(1825, 70), Rating(1555, 68)) == pytest.approx(expected)


def test_uncertainty_pulls_toward_even():
    sure = win_probability(Rating(1800, 40), Rating(1500, 40))
    unsure = win_probability(Rating(1800, 300), Rating(1500, 300))
    assert 0.5 < unsure < sure

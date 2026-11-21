"""Glicko-2 ratings, with Project Rio's ladder parameters.

Rio web runs the official ladders, so the parameters here are the server's. The
server treats each game as its own rating period: both players are updated from
their pre-game ratings, one result each::

    from pyrio import ratings

    winner, loser = ratings.Rating(), ratings.Rating(1620, 85)
    winner, loser = (
        ratings.update(winner, [(loser, 1)]),
        ratings.update(loser, [(winner, 0)]),
    )

The algorithm is Glickman's, as revised in 2012
(http://www.glicko.net/glicko/glicko2.pdf). Where the server's code departs from
the paper (see ``_volatility``), pyrio follows the paper: a game moves the two
apart by under 0.003 in rating and rd, and under 3e-5 in volatility.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import Iterable

__all__ = ["Rating", "update", "win_probability"]

# Rio web's ladder parameters, ProjectRio-web at d4bf233. The server builds every
# new ladder entry from app/consts.py:43-45 (rating 1500, RD 300, volatility 0.06),
# not from the RD 350 default in app/glicko2.py:47, and tau is app/glicko2.py:29.
_TAU = 0.5
_START_RATING = 1500.0
_START_RD = 300.0
_START_VOLATILITY = 0.06

# Glicko-2's internal scale: mu = (rating - 1500) / 173.7178, phi = rd / 173.7178.
# The paper and the server both use this rounding of 400 / ln 10.
_SCALE = 173.7178
# The paper's convergence tolerance for the volatility step.
_EPSILON = 0.000001


@dataclass(frozen=True, slots=True)
class Rating:
    """A player's Glicko-2 rating: ``rating`` on the familiar 1500 scale, its
    deviation ``rd``, and ``volatility``, how erratic the player's results are.

    ``Rating()`` is a new player on Rio web's ladders.
    """

    rating: float = _START_RATING
    rd: float = _START_RD
    volatility: float = _START_VOLATILITY

    def __post_init__(self) -> None:
        if not math.isfinite(self.rating):
            raise ValueError(f"rating must be finite, got {self.rating!r}")
        if not (math.isfinite(self.rd) and self.rd > 0):
            raise ValueError(f"rd must be positive, got {self.rd!r}")
        if not (math.isfinite(self.volatility) and self.volatility > 0):
            raise ValueError(f"volatility must be positive, got {self.volatility!r}")


def update(rating: Rating, results: Iterable[tuple[Rating, float]]) -> Rating:
    """The rating after one rating period.

    ``results`` holds one ``(opponent, score)`` pair per game, where ``opponent``
    is the opponent's rating going into the period and ``score`` is 1 for a win
    and 0 for a loss (``True`` and ``False`` work too). With no results, only the
    deviation grows, as for a player who sat the period out. Rio web never does
    that: it rates game by game and leaves inactive players alone.
    """
    games = [(_mu(opponent), _phi(opponent), float(score)) for opponent, score in results]
    for _, _, score in games:
        if not 0 <= score <= 1:
            raise ValueError(f"score must be between 0 and 1, got {score!r}")

    mu, phi, sigma = _mu(rating), _phi(rating), rating.volatility
    if not games:
        return Rating(rating.rating, math.sqrt(phi**2 + sigma**2) * _SCALE, sigma)

    # Steps 3 and 4: the estimated variance v and improvement delta.
    weighted: list[tuple[float, float, float]] = []
    for mu_j, phi_j, score in games:
        g = _g(phi_j)
        weighted.append((g, _expected(mu, mu_j, g), score))
    v = 1 / sum(g**2 * e * (1 - e) for g, e, _ in weighted)
    improvement = sum(g * (score - e) for g, e, score in weighted)
    delta = v * improvement

    # Steps 5 to 8.
    sigma = _volatility(phi, sigma, v, delta)
    phi_star = math.sqrt(phi**2 + sigma**2)
    phi = 1 / math.sqrt(1 / phi_star**2 + 1 / v)
    mu += phi**2 * improvement
    return Rating(mu * _SCALE + _START_RATING, phi * _SCALE, sigma)


def win_probability(player: Rating, opponent: Rating) -> float:
    """The chance that ``player`` beats ``opponent``.

    Both deviations count, combined as ``sqrt(rd**2 + opponent_rd**2)``
    (Glickman, "The Glicko system", 1995), so the two players' chances add to 1.
    This is Glicko's expected score; baseball has no draws, so it is the win
    probability.
    """
    phi = math.hypot(_phi(player), _phi(opponent))
    return _expected(_mu(player), _mu(opponent), _g(phi))


def _mu(rating: Rating) -> float:
    return (rating.rating - _START_RATING) / _SCALE


def _phi(rating: Rating) -> float:
    return rating.rd / _SCALE


def _g(phi: float) -> float:
    return 1 / math.sqrt(1 + 3 * phi**2 / math.pi**2)


def _expected(mu: float, mu_j: float, g: float) -> float:
    return 1 / (1 + math.exp(-g * (mu - mu_j)))


def _volatility(phi: float, sigma: float, v: float, delta: float) -> float:
    """Step 5: the new volatility, the root of ``f`` found by the Illinois method.

    This is the 2012 revision's bracketing step. Rio web still has the original
    paper's Newton iteration, which loops until two iterates are exactly equal.
    Near the root the iterates can alternate between two adjacent floats forever,
    and starting from ``x = 0`` they can overflow, so that loop has no guaranteed
    end (``tests/test_ratings.py`` has a case of each). The bracket here always
    holds the root and stops at the paper's tolerance.

    ``f`` uses ``phi**2``, as the paper does. Rio web's loop (and pre-1.0
    pyrio's) uses ``mu**2`` there, a slip carried over from the pyglicko2 code
    both were copied from, so its volatilities come out slightly different.
    """
    a = math.log(sigma**2)

    def f(x: float) -> float:
        ex = math.exp(x)
        return ex * (delta**2 - phi**2 - v - ex) / (2 * (phi**2 + v + ex) ** 2) - (x - a) / _TAU**2

    low = a
    if delta**2 > phi**2 + v:
        high = math.log(delta**2 - phi**2 - v)
    else:
        k = 1
        while f(a - k * _TAU) < 0:
            k += 1
        high = a - k * _TAU
    f_low, f_high = f(low), f(high)
    while abs(high - low) > _EPSILON:
        new = low + (low - high) * f_low / (f_high - f_low)
        f_new = f(new)
        if f_new * f_high <= 0:
            low, f_low = high, f_high
        else:
            f_low /= 2
        high, f_high = new, f_new
    return math.exp(low / 2)

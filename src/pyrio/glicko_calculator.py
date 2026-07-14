import math

SCALE = 173.7178
BASE = 1500.0

def g(phi: float) -> float:
    """Glicko-2 g(phi) function."""
    return 1 / math.sqrt(1 + (3 * phi**2) / (math.pi**2))

def glicko2_win_probability(rating_1: float, rating_2: float, rd_2: float) -> float:
    """
    Calculate the win probability of Player 1 against Player 2
    using the Glicko-2 system (expected score).
    Only the opponent's RD is used in the g() function.

    :param rating_1: Rating of Player 1
    :param rating_2: Rating of Player 2
    :param rd_2: Rating deviation of Player 2
    
    :return: Probability of Player 1 winning
    """
    # Convert to Glicko-2 scale
    mu_1 = (rating_1 - BASE) / SCALE
    mu_2 = (rating_2 - BASE) / SCALE
    phi_2 = rd_2 / SCALE

    E1 = 1 / (1 + math.exp(-g(phi_2) * (mu_1 - mu_2)))
    return E1

# Example usage
def main():
    rating_1 = 1825  # Player 1 rating
    rating_2 = 1555  # Player 2 rating
    rd_1 = 70        # not needed for probability
    rd_2 = 68        # opponent's RD

    win_probability_player_1 = glicko2_win_probability(rating_1, rating_2, rd_2)

    print(f"Win probability for Player 1: {win_probability_player_1:.4f}")
    print(f"Win probability for Player 2: {1 - win_probability_player_1:.4f}")

if __name__ == "__main__":
    main()
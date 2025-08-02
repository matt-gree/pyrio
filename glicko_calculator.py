import math

def g(x):
    """Glicko-2 g(x) function."""
    return 1 / math.sqrt(1 + (3 * x**2) / (math.pi**2))

def glicko2_win_probability(rating_1, rating_2, rd_1, rd_2):
    """
    Calculate the win probability of Player 1 against Player 2
    using the Glicko-2 rating system.
    
    :param rating_1: Rating of Player 1
    :param rating_2: Rating of Player 2
    :param rd_1: Rating deviation of Player 1
    :param rd_2: Rating deviation of Player 2
    
    :return: Probability of Player 1 winning
    """
    # Calculate the expected outcome for Player 2
    A = g(math.sqrt(rd_1**2 + rd_2**2)) * (rating_2 - rating_1)
    expected_score_player_2 = 1 / (1 + math.exp(-A))  # This is the probability of Player 2 winning
    expected_score_player_1 = 1 - expected_score_player_2  # Probability of Player 1 winning
    
    return expected_score_player_1

# Example usage
def main():
    # Example Glicko-2 ratings
    rating_1 = 1638  # Player 1 rating
    rating_2 = 1122  # Player 2 rating
    rd_1 = 150      # Player 1 rating deviation
    rd_2 = 150      # Player 2 rating deviation
    
    win_probability_player_1 = glicko2_win_probability(rating_1, rating_2, rd_1, rd_2)
    
    print(f"Win probability for Player 1: {win_probability_player_1:.4f}")
    print(f"Win probability for Player 2: {1 - win_probability_player_1:.4f}")

if __name__ == "__main__":
    main()
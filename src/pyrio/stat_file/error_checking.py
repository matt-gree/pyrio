"""Argument validation shared by the stat-file views."""
from __future__ import annotations


class ErrorChecker:
    @staticmethod
    def check_team_num(teamNum: int) -> None:
        """Checks if the team number is valid (either 0 or 1)."""
        if teamNum != 0 and teamNum != 1:
            raise Exception(
                f'Invalid team arg {teamNum}. Function only accepts team args of 0 (away team) or 1 (home team).')

    @staticmethod
    def check_roster_num(rosterNum: int) -> None:
        """Checks if the roster number is valid (between -1 and 8). Allows -1."""
        if rosterNum < -1 or rosterNum > 8:
            raise ValueError(f'Invalid roster arg {rosterNum}. Function only accepts roster args of 0 to 8.')

    @staticmethod
    def check_roster_num_no_neg(rosterNum: int) -> None:
        """Checks if the roster number is valid (between 0 and 8). Does not allow -1."""
        if rosterNum < 0 or rosterNum > 8:
            raise ValueError(f'Invalid roster arg {rosterNum}. Function only accepts roster args of 0 to 8.')

    @staticmethod
    def check_base_num(baseNum: int) -> None:
        """Checks if the base number is valid (between 1 and 3) or -1."""
        if (baseNum < -1 or baseNum > 3):
            raise ValueError(f'Invalid base arg {baseNum}. Function only accepts base args of -1 to 3')

    @staticmethod
    def check_position(position) -> None:
        """Checks position is an int 0-8 or a valid position-name string."""
        valid_int = isinstance(position, int) and not isinstance(position, bool) and 0 <= position <= 8
        valid_str = position in ("P", "C", "1B", "2B", "3B", "SS", "LF", "CF", "RF")
        if not (valid_int or valid_str):
            raise ValueError(
                f'Invalid position arg {position}. Accepts 0-8 or a position name '
                f'(P, C, 1B, 2B, 3B, SS, LF, CF, RF).')

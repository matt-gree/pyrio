"""StatObj.wasQuit reads "Quitter Team". The emulator decodes it as Home, Away, Crash or
None, and encoded files store the raw 0, 1, 2 or 255.
"""
import pytest

from pyrio.stat_file_parser import StatObj


@pytest.mark.parametrize('quitter', ['', 'None', 255])
def test_normal_game_was_not_quit(quitter):
    assert StatObj({'Quitter Team': quitter}).wasQuit() is False


@pytest.mark.parametrize('quitter', ['Home', 'Away', 0, 1])
def test_quit_game(quitter):
    assert StatObj({'Quitter Team': quitter}).wasQuit() is True


@pytest.mark.parametrize('quitter', ['Crash', 2])
def test_crash_counts_as_quit(quitter):
    assert StatObj({'Quitter Team': quitter}).wasQuit() is True

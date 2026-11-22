"""Every script in examples/ runs against a fixture, so the examples can't rot."""

from __future__ import annotations

import pathlib
import subprocess
import sys

import pytest

ROOT = pathlib.Path(__file__).parent.parent
EXAMPLES = ROOT / "examples"
FIXTURES = pathlib.Path(__file__).parent / "fixtures"
GAME = FIXTURES / "20260618T191655_SpiceOrange-Vs-MattGree_3896251267.json"


def run(script: str, *args: str) -> str:
    result = subprocess.run(
        [sys.executable, str(EXAMPLES / script), *args],
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0, result.stderr
    return result.stdout


def test_every_example_is_tested():
    tested = {"box_score.py", "spray_chart.py", "character_batting.py", "game_summary.py"}
    assert {p.name for p in EXAMPLES.glob("*.py")} == tested


def test_box_score():
    out = run("box_score.py", str(GAME))
    assert "Bowser Castle" in out
    assert "SpiceOrange" in out
    assert "IP" in out


def test_spray_chart(tmp_path: pathlib.Path):
    out = tmp_path / "spray.svg"
    run("spray_chart.py", str(GAME), "-o", str(out), "--fouls")
    assert out.read_text(encoding="utf-8").startswith("<svg")


def test_character_batting():
    pytest.importorskip("pandas")
    out = run("character_batting.py", str(FIXTURES / "stat_files"))
    assert "games" in out
    assert "avg" in out


def test_game_summary(tmp_path: pathlib.Path):
    pytest.importorskip("matplotlib")
    out = tmp_path / "summary.png"
    stdout = run("game_summary.py", str(GAME), "-o", str(out))
    assert out.read_bytes().startswith(b"\x89PNG")
    assert "HARDEST HIT" in stdout

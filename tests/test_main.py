import json
import subprocess
import sys
from pathlib import Path

import pytest

from pyrio.__main__ import main

FIXTURES = Path(__file__).parent / "fixtures"
GAME_PATH = FIXTURES / "20260618T191655_SpiceOrange-Vs-MattGree_3896251267.json"
CRASH_PATH = (
    FIXTURES / "stat_files/1.9.6/crash.decode.20230831T151058_MattGree-Vs-samn_345471771.json"
)


def test_decode_prints_a_box_score(capsys: pytest.CaptureFixture[str]):
    assert main(["decode", str(GAME_PATH)]) == 0
    out = capsys.readouterr().out
    assert "Game 3896251267  (Rio 2.2.0)" in out
    assert "SpiceOrange 9, MattGree 12  (final, 9 of 9 innings)" in out
    assert "Bowser (C)" in out
    assert "Events" not in out


def test_decode_events(capsys: pytest.CaptureFixture[str]):
    assert main(["decode", "--events", str(CRASH_PATH)]) == 0
    out = capsys.readouterr().out
    assert "(crashed, 1 of 9 innings)" in out
    assert "Events" in out
    assert "-> Single" in out


def test_decode_json(capsys: pytest.CaptureFixture[str]):
    assert main(["decode", "--json", str(GAME_PATH)]) == 0
    assert json.loads(capsys.readouterr().out)["id"] == 3896251267


def test_decode_hud(capsys: pytest.CaptureFixture[str]):
    assert main(["decode", "--hud", "2.2.0", str(FIXTURES / "hud.json")]) == 0
    assert json.loads(capsys.readouterr().out)["event_number"] == 210


def test_errors_exit_1(tmp_path: Path, capsys: pytest.CaptureFixture[str]):
    bad = tmp_path / "bad.json"
    bad.write_text("{}")
    assert main(["decode", str(bad)]) == 1
    assert "pyrio:" in capsys.readouterr().err
    assert main(["decode", str(tmp_path / "missing.json")]) == 1


def test_runs_as_a_module():
    out = subprocess.run(
        [sys.executable, "-m", "pyrio", "decode", str(GAME_PATH)],
        capture_output=True,
        text=True,
        check=True,
    ).stdout
    assert out.startswith("Game 3896251267")

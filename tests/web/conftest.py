"""Shared setup for the ``pyrio.web`` tests. They need the ``web`` extra and respx."""

from __future__ import annotations

import importlib.util
import json
from pathlib import Path

import pytest

# A core-only install has neither; skip this folder rather than fail it.
if importlib.util.find_spec("httpx") is None or importlib.util.find_spec("respx") is None:
    collect_ignore_glob = ["test_*.py"]

FIXTURES = Path(__file__).parent.parent / "fixtures" / "web"
BASE = "https://api.projectrio.app"


def load(name: str) -> object:
    return json.loads((FIXTURES / name).read_text())


@pytest.fixture
def contract():
    """Loads a contract fixture from tests/fixtures/web by file name (see its README)."""
    return load


@pytest.fixture(autouse=True)
def no_retry_wait(monkeypatch: pytest.MonkeyPatch) -> None:
    """Retries happen at once in tests."""
    if importlib.util.find_spec("httpx") is not None:
        monkeypatch.setattr("pyrio.web._base.retry_delay", lambda attempt: 0.0)

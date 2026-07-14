"""Entry points for loading decoded stat files into StatObj instances."""
from __future__ import annotations

import fnmatch
import json
import warnings
from pathlib import Path
from typing import Iterator, Union

from .stat_obj import StatObj


def load_stat_file(path: Union[str, Path]) -> StatObj:
    """Read a single decoded stat-file JSON from disk and wrap it in a StatObj."""
    with open(path, "r") as f:
        return StatObj(json.load(f))


def iter_stat_files(
    directory: Union[str, Path],
    pattern: str = "*decoded*",
    skip_errors: bool = False,
) -> Iterator[StatObj]:
    """Yield a StatObj for each decoded stat file in ``directory``.

    pattern: filename glob selecting stat files (default matches Rio's
        ``decoded`` naming). Pass ``"*"`` to load every file.
    skip_errors: if True, unreadable or malformed files are warned about and
        skipped instead of raising.
    """
    directory = Path(directory)
    for path in sorted(directory.iterdir()):
        if not path.is_file():
            continue
        if not fnmatch.fnmatch(path.name, pattern):
            continue
        try:
            yield load_stat_file(path)
        except (OSError, json.JSONDecodeError) as exc:
            if skip_errors:
                warnings.warn(f"Skipping stat file {path.name}: {exc}")
                continue
            raise

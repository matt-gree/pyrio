"""``DiskCache``: an opt-in JSON cache for Rio web's reference data."""

from __future__ import annotations

import hashlib
import json
import os
import tempfile
import time
from datetime import timedelta
from pathlib import Path
from typing import cast

__all__ = ["DiskCache"]


class DiskCache:
    """Responses to reference-data calls, kept as JSON files in a folder you choose.

    Pass one to a client, ``RioClient(cache=DiskCache("~/.cache/rio", ttl=3600))``,
    and the tag-set, tag and user listings are served from it until they're
    ``ttl`` old (seconds or a ``timedelta``). Nothing else is cached, and
    without a cache every call goes to the server.

    The folder is created on the first write, never at construction. Entries
    are plain JSON, never pickle, so a file someone else put there can't run
    code.
    """

    def __init__(self, path: str | os.PathLike[str], *, ttl: float | timedelta = 3600) -> None:
        seconds = ttl.total_seconds() if isinstance(ttl, timedelta) else float(ttl)
        if seconds <= 0:
            raise ValueError(f"ttl must be positive, got {ttl!r}")
        self.path = Path(path).expanduser()
        self.ttl = seconds

    def __repr__(self) -> str:
        return f"DiskCache({str(self.path)!r}, ttl={self.ttl:g})"

    def _file(self, key: str) -> Path:
        return self.path / f"{hashlib.sha256(key.encode()).hexdigest()}.json"

    def get(self, key: str) -> object | None:
        """The JSON stored under ``key``, or ``None`` if it's missing, expired or unreadable."""
        try:
            loaded: object = json.loads(self._file(key).read_text(encoding="utf-8"))
        except (OSError, ValueError):
            return None
        if not isinstance(loaded, dict):
            return None
        entry = cast(dict[str, object], loaded)
        if entry.get("key") != key:
            return None
        stored_at = entry.get("stored_at")
        if not isinstance(stored_at, int | float) or time.time() - stored_at > self.ttl:
            return None
        return entry.get("body")

    def set(self, key: str, body: object) -> None:
        """Store ``body`` under ``key``, replacing the file atomically."""
        self.path.mkdir(parents=True, exist_ok=True)
        entry = {"key": key, "stored_at": time.time(), "body": body}
        fd, temp = tempfile.mkstemp(dir=self.path, suffix=".tmp")
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as handle:
                json.dump(entry, handle)
            Path(temp).replace(self._file(key))
        except BaseException:
            Path(temp).unlink(missing_ok=True)
            raise

    def clear(self) -> None:
        """Delete every entry this cache wrote."""
        if not self.path.is_dir():
            return
        for file in self.path.glob("*.json"):
            if len(file.stem) == 64:
                file.unlink(missing_ok=True)

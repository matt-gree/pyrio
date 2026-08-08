"""Client-side cache for the Rio API's reference data (tags, users, game modes).

WHAT THIS IS FOR. Not to spare the server — it is to spare the CALLER. Every
lookup here answers from memory or disk immediately; the network happens when
there is nothing to answer with, or quietly in the background when what we have
has aged. A consumer should never wait on this cache to be correct, only to
exist.

That goal shapes three decisions:

  LAZY, PER SECTION. The three endpoints behind this cache are independent, and
  most callers want one of them. Asking for the game-mode map fetches game modes
  — not 9,600 users and a tag table as well. Construction touches the network
  never; the first *use* of a section is what fetches it.

  STALE WINS. An expired section is still served, immediately, while a refresh
  runs behind it. Expiry means "this is worth updating", not "make the caller
  wait". Only a section we have never seen blocks, because there is nothing else
  to hand back.

  A MISSING CACHE IS A CACHE MISS. Never an exception. The file is a cache; if
  it is absent, truncated, or written by an incompatible version, the answer is
  to fetch again — not to take the client down with it.

Storage is JSON, written atomically. JSON because a cache that cannot be read by
the next version of pandas is not a cache, and because unpickling a file off
disk is a code-execution primitive nobody asked for. Atomically because the
in-place write was itself the main way this file got corrupted.
"""
import json
import logging
import os
import tempfile
import threading
import time

import pandas as pd

logger = logging.getLogger(__name__)

# Cache-file format. Bump when a section's payload shape changes; an unknown
# version reads as "no cache" rather than as garbage.
_FORMAT_VERSION = 2


class CompleterCache:
    """Caches reference data (users, tags, game modes) from the Rio API.

    Accepts a RioWeb client instance. Each section refreshes independently when
    it expires (default: 1 day); ``refresh_cache()`` forces all of them.

    Args:
        client: a RioWeb instance.
        cache_dir: directory for the cache file.
        cache_expiration_days: age after which a section is refreshed.
        background_refresh: serve stale data and refresh in a background thread.
            Set False to refresh inline instead (deterministic, for tests).
    """

    def __init__(self, client, cache_dir: str = 'cache', cache_expiration_days: int = 1,
                 background_refresh: bool = True):
        self.client = client
        self.cache_dir = cache_dir
        self.cache_expiration_days = cache_expiration_days
        self.background_refresh = background_refresh
        self.cache_file = os.path.join(cache_dir, 'cache.json')

        os.makedirs(self.cache_dir, exist_ok=True)

        # section -> {"fetched_at": epoch_seconds, "payload": {...}}
        self._sections: dict[str, dict] = {}
        self._lock = threading.RLock()
        self._in_flight: set[str] = set()
        self._tags_df = None          # memoised; rebuilt when tags change

        self._load()                  # disk only — never the network

    # -- section definitions ------------------------------------------------
    #
    # One entry per endpoint. Keeping the fetchers here (rather than inline in
    # the accessors) is what lets every accessor be one line and share the
    # fresh/stale/absent logic.

    def _fetch_tags(self) -> dict:
        return {'rows': self.client.list_tags()['Tags']}

    def _fetch_users(self) -> dict:
        return {'users_dict': self.client.list_users()['users']}

    def _fetch_game_modes(self) -> dict:
        response = self.client.list_game_modes()
        return {'game_mode_dict': {t['name']: t['id'] for t in response['Tag Sets']}}

    @property
    def _fetchers(self) -> dict:
        return {
            'tags': self._fetch_tags,
            'users': self._fetch_users,
            'game_modes': self._fetch_game_modes,
        }

    # -- the fresh / stale / absent decision ---------------------------------

    def _is_stale(self, entry: dict) -> bool:
        age = time.time() - entry.get('fetched_at', 0)
        return age > self.cache_expiration_days * 86400

    def _payload(self, section: str) -> dict:
        """The section's data, fetching only if we have nothing at all."""
        with self._lock:
            entry = self._sections.get(section)

        if entry is None:
            return self._refresh_section(section)

        if self._is_stale(entry):
            if self.background_refresh:
                self._refresh_in_background(section)
            else:
                return self._refresh_section(section)

        return entry['payload']

    def _refresh_section(self, section: str) -> dict:
        """Fetch one section and store it. Returns the new payload.

        On failure, returns whatever we already had — a stale answer beats an
        exception for every caller of this class.
        """
        with self._lock:
            if section in self._in_flight:
                existing = self._sections.get(section)
                if existing is not None:
                    return existing['payload']
            self._in_flight.add(section)
        try:
            payload = self._fetchers[section]()
        except Exception:
            logger.warning("failed to refresh %r section of the Rio cache", section, exc_info=True)
            with self._lock:
                entry = self._sections.get(section)
            return entry['payload'] if entry else {}
        finally:
            with self._lock:
                self._in_flight.discard(section)

        with self._lock:
            self._sections[section] = {'fetched_at': time.time(), 'payload': payload}
            if section == 'tags':
                self._tags_df = None
        self._save()
        return payload

    def _refresh_in_background(self, section: str) -> None:
        with self._lock:
            if section in self._in_flight:
                return
        threading.Thread(
            target=self._refresh_section, args=(section,),
            name=f"rio-cache-refresh-{section}", daemon=True,
        ).start()

    # -- persistence ---------------------------------------------------------

    def _load(self) -> None:
        """Read the cache file. Any problem with it means "no cache"."""
        try:
            with open(self.cache_file, 'r', encoding='utf-8') as f:
                blob = json.load(f)
            if blob.get('version') != _FORMAT_VERSION:
                return
            sections = blob.get('sections')
            if isinstance(sections, dict):
                self._sections = {
                    k: v for k, v in sections.items()
                    if isinstance(v, dict) and 'payload' in v
                }
        except FileNotFoundError:
            pass
        except Exception:
            logger.warning("unreadable Rio cache at %s; refetching", self.cache_file, exc_info=True)

    def _save(self) -> None:
        """Write the cache file atomically.

        Temp file in the same directory then os.replace, so a process that dies
        mid-write leaves the previous cache intact instead of a truncated file
        that the next load has to reject.
        """
        with self._lock:
            blob = {'version': _FORMAT_VERSION, 'sections': self._sections}
        tmp_path = None
        try:
            fd, tmp_path = tempfile.mkstemp(dir=self.cache_dir, suffix='.tmp')
            with os.fdopen(fd, 'w', encoding='utf-8') as f:
                json.dump(blob, f)
            os.replace(tmp_path, self.cache_file)
        except Exception:
            logger.warning("could not write the Rio cache to %s", self.cache_file, exc_info=True)
            if tmp_path and os.path.exists(tmp_path):
                try:
                    os.remove(tmp_path)
                except OSError:
                    pass

    # -- public accessors ----------------------------------------------------
    #
    # Unchanged signatures and return types. Each one now costs exactly the
    # endpoint behind it.

    def return_tags_df(self) -> pd.DataFrame:
        rows = self._payload('tags').get('rows', [])
        with self._lock:
            if self._tags_df is None:
                # Built on demand, not stored: a DataFrame is what forced the
                # pickle, and only this accessor wants one.
                df = pd.DataFrame(rows)
                self._tags_df = df.set_index('id') if 'id' in df.columns else df
            return self._tags_df

    def communities(self) -> list[str]:
        return [r['name'] for r in self._payload('tags').get('rows', [])
                if r.get('type') == 'Community']

    def users_dictionary(self) -> dict:
        return self._payload('users').get('users_dict', {})

    def users(self) -> list:
        return list(self.users_dictionary().values())

    def tags_dictionary(self) -> dict:
        return {r['name']: r['id'] for r in self._payload('tags').get('rows', [])
                if r.get('type') in ('Gecko Code', 'Component')}

    def game_mode_dictionary(self) -> dict:
        return self._payload('game_modes').get('game_mode_dict', {})

    def refresh_cache(self) -> None:
        """Force an update of every section.

        The one place that still fetches everything, because it is the one place
        the caller has explicitly asked for everything.
        """
        for section in self._fetchers:
            self._refresh_section(section)
        logger.info("Rio cache refreshed")
